"""Isolated Run3 cycle using existing HTCondor submission and state helpers."""
import argparse
from collections import Counter
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from types import SimpleNamespace
import uuid

from autoreco import (SubmissionError, get_run_number, parse_integer, runs_to_reconstruct, save_state,
                      state_path, submit_job, transfer_job_data, update_reco_done_batch)
from googletool import get_headers, open_google_sheet, read_all_records
from noise_jobs import build_iq_v3_jobs, check_run3_inputs
from notify import Notifier, approval_message, approval_url
import recovery as persistent
from run3_storage import PILOT, PRODUCTION, RAW

BASE = Path("/home/mazzitel/HFGW/analysis-runtime/autoreco/Run3")
ROOT_ARCHIVE = Path("/home/mazzitel/flash-data/analysis/autoreco/Run3")
RAW_ARCHIVE = Path("/home/mazzitel/flash-data/data/LNF")
ARCHIVE_MOUNT = Path("/home/mazzitel/flash-data")
ANALYSIS = Path(__file__).resolve().parents[1] / "examples/analyze_midas_iq_v3.py"
ARTIFACT = re.compile(r"(script\.sh|submit\.sub|iq_v3_job\.json|publication\.json|"
                      r"submit_error\.json|run\d+_job_status\.json|"
                      r"analyze_midas_iq_v3\.py|iq_acquisition_metadata\.py|"
                      r"iq_compact_spectra\.py|run3_storage\.py|iq_thermometers\.py|extract_thermometers\.py|"
                      r"iq_root\.py|iq_root_worker\.py|iq_midas_aux\.py|uproot-py39\.tgz|"
                      r"(stdout|stderr)-\d+\.\d+\.txt|output-\d+\.\d+\.log)")


def local(path):
    if not (path == BASE or BASE in path.parents) or ".." in path.parts:
        raise ValueError(f"unexpected runtime path: {path}")
    if any(part.is_symlink() for part in (*reversed(path.parents), path)):
        raise ValueError(f"symlink in runtime path: {path}")
    ancestor = path
    while not ancestor.exists():
        ancestor = ancestor.parent
    fs = subprocess.check_output(["findmnt", "-T", str(ancestor), "-no", "FSTYPE"], text=True).strip()
    if fs not in {"ext4", "xfs", "btrfs"}:
        raise ValueError(f"runtime filesystem is not approved local storage: {fs}")


def condor_query(command, attempt):
    return json.loads(subprocess.check_output(
        [command, "-constraint", f'FlashRun3Attempt == "{attempt}"',
         "-attributes", "ClusterId,JobStatus,ExitCode,ExitBySignal", "-json"],
        text=True).strip() or "[]")


def lookup(attempt):
    jobs = condor_query("condor_q", attempt)
    if jobs:
        return "active", jobs
    return "history", condor_query("condor_history", attempt)


def clean_attempt(directory, *, dry_run, keep_logs=False):
    local(directory)
    for path in directory.iterdir():
        if keep_logs and re.match(r"^(stdout|stderr|output)-", path.name):
            continue
        if ARTIFACT.fullmatch(path.name) and not path.is_symlink() and path.is_file():
            print(f"{'would remove' if dry_run else 'remove'} {path}")
            if not dry_run:
                path.unlink()


def workdir(run_dir, attempt, run):
    if not re.fullmatch(r"[0-9a-f]{32}", attempt):
        raise ValueError("invalid attempt identifier")
    path = run_dir / attempt / f"{run:05d}"
    local(path)
    return path


def validate_receipt(receipt, completion, run, url, attempt):
    checksum = receipt.get("local_adler32", "")
    if (receipt.get("url") != url or receipt.get("run") != run
            or receipt.get("attempt") != attempt or receipt.get("validated") is not True
            or type(receipt.get("size")) is not int or receipt["size"] <= 0
            or receipt.get("remote_size") != receipt["size"]
            or not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{8}", checksum)
            or receipt.get("remote_adler32") != checksum
            or completion.get("run") != run or completion.get("exit_code") != 0
            or completion.get("status") != "success"
            or (url.endswith(".root") and receipt.get("root_schema") != "3.1")):
        raise ValueError("invalid Run3 publication receipt")


def finalize_verified(run_dir, state, directory, dry_run, queue, preserve_diagnostics=False):
    if queue:
        if len(queue) != 1:
            return True
        job = queue[0]
        if (not state.get("cluster") or str(job.get("ClusterId")) != str(state["cluster"]) or job["JobStatus"] != 4
                or job.get("ExitCode") != 0 or job.get("ExitBySignal")):
            return True
        if dry_run:
            print(f"would remove completed Condor job {state['cluster']}.0")
            return True
        cluster = int(state["cluster"])
        attempt = state["attempt"]
        constraint = (f'ClusterId == {cluster} && ProcId == 0 && JobStatus == 4 '
                      f'&& ExitCode == 0 && FlashRun3Attempt == "{attempt}"')
        subprocess.run(["condor_rm", "-constraint", constraint], check=True)
        if condor_query("condor_q", attempt):
            return True
    if preserve_diagnostics:
        if not dry_run and not state.get("queue_closed"):
            state["queue_closed"] = True
            save_state(run_dir, state)
        return False
    keep_logs = time.time() - state["verified_at"] < 30*86400
    clean_attempt(directory, dry_run=dry_run, keep_logs=keep_logs)
    if not dry_run:
        state.update(queue_closed=True, payload_cleaned=True, logs_cleaned=not keep_logs)
        save_state(run_dir, state)
    return False


def reconcile(run_dir, state, run, url, retention, dry_run, notifier=None, max_attempts=2,
              preserve_diagnostics=False):
    """Return True if the run still occupies a slot."""
    attempt = state["attempt"]
    directory = workdir(run_dir, attempt, run)
    incident = f"{run_dir.parent.name}:{run}"
    reference = state_path(run_dir)
    if dry_run:
        notifier = None
    if state["phase"] == "verified":
        age = time.time() - state["verified_at"]
        if state.get("queue_closed"):
            if state.get("logs_cleaned") or (state.get("payload_cleaned") and age < 30*86400):
                return False
            queue = []
        else:
            source, jobs = lookup(attempt)
            queue = jobs if source == "active" else []
        return finalize_verified(run_dir, state, directory, dry_run, queue, preserve_diagnostics)
    source, jobs = lookup(attempt)
    if len(jobs) != 1:
        return state["phase"] not in ("verified", "failed") or source == "active"
    job = jobs[0]
    if notifier:
        if job["JobStatus"] == 5:
            notifier.fault(f"hold:{incident}:{attempt}", "HTCondor HOLD",
                           f"Cluster {job['ClusterId']} is held. Inspect its HoldReason locally.",
                           reference, run=run)
        else:
            notifier.resolved(f"hold:{incident}:{attempt}", "HTCondor HOLD cleared",
                              f"Cluster {job['ClusterId']} is observed outside HOLD.",
                              reference, run=run)
    succeeded = job["JobStatus"] == 4 and job.get("ExitCode") == 0 and not job.get("ExitBySignal")
    if source == "active":
        if not succeeded:
            return True
        if state["phase"] != "verified" and not state.get("output_retrieved"):
            if dry_run:
                return True
            transfer_job_data(str(job["ClusterId"]), directory)
            state.update(output_retrieved=True, cluster=job["ClusterId"])
            save_state(run_dir, state)
        # Completed spooled jobs can remain in the queue after retrieval.
    if succeeded:
        receipt = directory / "publication.json"
        status = directory / f"run{run:05d}_job_status.json"
        local(receipt)
        local(status)
        if not (receipt.is_file() and status.is_file()):
            if notifier:
                notifier.fault(f"publication:{incident}", "ROOT publication evidence missing",
                               "Condor completed successfully, but the local receipt or status file is missing.",
                               reference, run=run, after=2)
            return True
        try:
            identity = json.loads(receipt.read_text())
            completion = json.loads(status.read_text())
            validate_receipt(identity, completion, run, url, attempt)
        except Exception as error:
            if notifier:
                notifier.fault(f"publication:{incident}", "ROOT publication verification failed",
                               "Publication receipt or completion evidence failed validation.",
                               reference, run=run, error=error)
            raise
        if dry_run:
            return source == "active"
        state.update(phase="verified", publication=identity, cluster=job["ClusterId"],
                     verified_at=time.time())
        save_state(run_dir, state)
        if notifier:
            for key in (f"publication:{incident}", f"reconstruction:{incident}",
                        f"reconstruction:{incident}:exhausted"):
                notifier.resolved(key, "ROOT recovery verified",
                                  "A reconstruction completed and its publication receipt passed validation.",
                                  reference, run=run)
        return finalize_verified(run_dir, state, directory, dry_run,
                                 jobs if source == "active" else [], preserve_diagnostics)
    if job["JobStatus"] not in (3, 4):
        return True
    if state["phase"] != "failed" and not dry_run:
        state.update(phase="failed", failed_at=time.time(), cluster=job["ClusterId"])
        save_state(run_dir, state)
    episode_count = state.get("episode_attempts", state.get("attempt_number", 0))
    episode = state.get("recovery_episode", 1)
    episode_key = f":episode:{episode}" if episode > 1 else ""
    if notifier and episode_count >= min(2, max_attempts):
        exhausted = episode_count >= max_attempts
        notifier.fault(f"reconstruction:{incident}" + episode_key + (":exhausted" if exhausted else ""),
                       "ROOT reconstruction retries exhausted" if exhausted else "Repeated ROOT reconstruction failure",
                       f"Episode {episode}, attempt {state['attempt_number']} ended unsuccessfully. "
                       "Inspect worker diagnostics locally. To exclude the run, set auto_reco = -2.",
                       reference, run=run)
    if not preserve_diagnostics and state.get("failed_at", time.time()) + retention*86400 <= time.time():
        clean_attempt(directory, dry_run=dry_run)
    return False


def prepare(root, run, pairs, url, probe, attempt, settings=None, reference=None):
    config = dict(url=url, probe=probe, attempt=attempt)
    if url.endswith(".root"):
        config.update(format="root", dependencies=settings["root_dependencies"],
                      dependencies_sha256=settings["root_dependencies_sha256"])
        if reference:
            config["reference"] = reference
    submit = build_iq_v3_jobs([run], root, RAW, ANALYSIS, pairs, None, 1,
                              publication=config, attempt=attempt)[0][1]
    check_run3_inputs(submit)
    return submit


def final_url(destination, run, root=False):
    return f"{destination}/run{run:05d}_iq_v3" + (".1.root" if root else ".h5")


def migration_inputs(records):
    """Select released logbook rows that still point to a completed canonical HDF5."""
    inputs = {}
    for run, record in records.items():
        uri = final_url(PRODUCTION, run)
        done = parse_integer(record.get("reco_done"))
        if (done is None or done < 1 or parse_integer(record.get("rucio_status")) != 0
                or str(record.get("filename", "")).strip() != f"run{run:05d}.mid.gz"
                or str(record.get("reco_output_path", "")).strip() != uri
                or str(record.get("reco_requested_version") or "").strip() not in ("", "3.0", "3.1")):
            continue
        path = state_path(BASE / "production" / f"{run:05d}")
        local(path)
        if not path.is_file():
            continue
        state = json.loads(path.read_text())
        if state.get("phase") != "verified" or not state.get("queue_closed"):
            continue
        validate_receipt(state["publication"], dict(run=run, exit_code=0, status="success"),
                         run, uri, state["attempt"])
        inputs[run] = dict(reference=state["publication"], reco_done=done,
                           expected_version=str(record.get("reco_version", "")).strip())
    return inputs


def late_rucio_row(record):
    """An explicitly unreconstructed row whose archived raw has been released."""
    return (parse_integer(record.get("reco_done")) == -1
            and parse_integer(record.get("rucio_status")) == 0
            and not any(str(record.get(key) or "").strip()
                        for key in ("reco_version", "reco_output_path")))


def discover(records, settings):
    minimum = settings["run_min"]
    by_run = {}
    for record in records:
        run = get_run_number(record)
        if run is not None and run >= minimum:
            if run in by_run:
                raise ValueError(f"duplicate logbook run: {run}")
            by_run[run] = record
    criteria = SimpleNamespace(run=None, run_min=minimum, ignore_reco_done=False)
    eligible = dict(runs_to_reconstruct(by_run.values(), criteria))
    if settings.get("output_format") == "root" and settings.get("late_rucio_recovery"):
        late = {run: f"run{run:05d}.mid.gz" for run, row in by_run.items()
                if late_rucio_row(row) and row.get("filename") == f"run{run:05d}.mid.gz"
                and str(row.get("reco_requested_version") or "").strip() in ("", "3.1")}
        if late and not ARCHIVE_MOUNT.is_mount():
            raise RuntimeError("Tier-1 archive mount unavailable for late Rucio discovery")
        for run, filename in late.items():
            try:
                if (RAW_ARCHIVE / filename).stat().st_size > 0:
                    eligible[run] = filename
            except FileNotFoundError:
                continue
    # The worker resolves raw names from the run number and supports one profile.
    for run, filename in list(eligible.items()):
        requested = str(by_run[run].get("reco_requested_version") or "").strip()
        if filename != f"run{run:05d}.mid.gz" or requested not in ("", settings["reco_version"]):
            print(f"Run {run}: filename or requested reconstruction version requires review")
            del eligible[run]
    return by_run, eligible


def plan_logbook_update(run_dir, run, state, record, url, version, dry_run):
    if state.get("status") == "sheet_updated":
        return None
    filename = f"run{run:05d}.mid.gz"
    validate_receipt(state["publication"], dict(run=run, exit_code=0, status="success"),
                     run, url, state["attempt"])
    migration = state.get("migration")
    versions = ("", "3.0", version) if migration else ("", version)
    if (str(record.get("filename", "")).strip() != filename
            or parse_integer(record.get("rucio_status")) != 0
            or str(record.get("reco_requested_version") or "").strip() not in versions):
        print(f"Run {run}: logbook row changed; update deferred")
        return None
    done = parse_integer(record.get("reco_done"))
    baseline = state.get("recovery_baseline") if version == "3.1" and not migration else None
    late = not migration and version == "3.1" and state.get("late_rucio_recovery")
    prior = migration["reco_done"] if migration else -1 if late else 0
    target = prior if migration else max(1, parse_integer(baseline["reco_done"]) or 0) if baseline else 1
    current_path = str(record.get("reco_output_path", "")).strip()
    current_version = str(record.get("reco_version", "")).strip()
    if done == target and current_path == url and current_version == version:
        if not dry_run:
            state["status"] = "sheet_updated"
            save_state(run_dir, state)
        return None
    if (baseline is not None and persistent.baseline(record) != baseline) or (
            baseline is None and done != prior) or (late and baseline is None and not late_rucio_row(record)) or (migration and (current_path != migration["reference"]["url"]
                                        or current_version != migration["expected_version"])):
        print(f"Run {run}: earlier reconstruction references changed; update deferred")
        return None
    return run_dir, dict(state, run_number=run, filename=filename, target_reco_done=target,
                         expected_reco_done=prior if baseline is None else None,
                         reco_version=version, output_path=url)


def submit_diagnosis(run_dir, state, run):
    path = workdir(run_dir, state["attempt"], run) / "submit_error.json"
    local(path)
    try:
        info = json.loads(path.read_text())
    except FileNotFoundError:
        return None
    if type(info.get("exit_code")) is not int or info["exit_code"] == 0:
        return None
    output = info.get("stdout", "") + "\n" + info.get("stderr", "")
    return ("authentication_required" if approval_url(output) else "submission_failure",
            path.stat().st_mtime)


def recovery_records(rows):
    records = {}
    for index, row in enumerate(rows, 2):
        run = get_run_number(row)
        if run is not None and run > 680:
            if run in records:
                raise ValueError(f"Duplicate recovery logbook run {run}")
            records[run] = index, row
    return records


def recovery_alert(notifier, root, run, state, disposition):
    if disposition not in ("automatic_recovery_exhausted", "submission_recovery_exhausted",
                            "submission_uncertain", "submission_failure", "terminal_attempt_unconfirmed",
                            "publication_missing_operator_review", "verified_legacy_state",
                            "root_present_needs_evidence", "logbook_reconciliation_pending"):
        return
    episode = state.get("recovery_episode", 1)
    notifier.fault(f"persistent:{root.name}:{run}:{episode}:{disposition}",
                   "Run3 recovery requires operator review",
                   f"Episode {episode}: {disposition.replace('_', ' ')}. "
                   "To exclude this run, set auto_reco = -2 in its Google logbook row.",
                   state_path(root / f"{run:05d}"), run=run,
                   after=2 if disposition == "logbook_reconciliation_pending" else 1)


def recovery_backlog(eligible, blocked, validated, pending):
    """Count distinct actionable runs and distinguish unverified publications."""
    missing = eligible - validated
    return {
        "awaiting_valid_root": len(missing),
        "actionable_outstanding": len(missing - blocked),
        "permanently_blocked": len(missing & blocked),
        "publication_or_logbook_pending": len(pending),
    }


def recovery_limit(settings, backlog, consistent):
    policy = settings["backlog_recovery"]
    if consistent and backlog["actionable_outstanding"] <= policy["threshold"]:
        return policy["normal_max_active"]
    return settings["max_active"]


def finish_recovery(path, settings, limit):
    """Atomically restore the normal limit under the caller's production lock."""
    if path.is_symlink() or json.loads(path.read_text()) != settings:
        raise ValueError("Recovery configuration changed during reconciliation")
    restored = dict(settings, max_active=limit)
    del restored["backlog_recovery"]
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(restored, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    print(f"ROOT recovery complete. Restored max_active={limit}.", flush=True)


def publication_disposition(state, run, url, row):
    if state.get("phase") != "verified" or state.get("product_url") != url:
        return "root_present_needs_evidence"
    try:
        validate_receipt(state["publication"], dict(run=run, exit_code=0, status="success"),
                         run, url, state["attempt"])
        size = (ROOT_ARCHIVE / f"run{run:05d}_iq_v3.1.root").stat().st_size
    except (ValueError, KeyError, FileNotFoundError):
        return "publication_missing_operator_review"
    if size != state["publication"]["remote_size"]:
        return "publication_missing_operator_review"
    if (state.get("status") == "sheet_updated" and (parse_integer(row.get("reco_done")) or 0) > 0
            and str(row.get("reco_version")) == "3.1" and row.get("reco_output_path") == url):
        return "validated"
    return "logbook_reconciliation_pending"


def cycle(root, settings, args):
    destination = PILOT if args.pilot else PRODUCTION
    dry_run = getattr(args, "dry_run", False)
    read_only = args.gc_dry_run or dry_run
    notifier = None if read_only else getattr(args, "notifier", None)
    migration = getattr(args, "migrate_root", False)
    root_output = not args.pilot and (migration or settings.get("output_format") == "root")
    recovery = root_output and not migration and "backlog_recovery" in settings
    policy = persistent.options(settings) if root_output and not migration else None
    observations, plans, indexes = {}, {}, {}
    migrations = {}
    records, eligible, updates, rebuilt = {}, {}, [], set()
    if args.pilot:
        runs = {1148}
    else:
        worksheet = open_google_sheet()
        headers = get_headers(worksheet)
        required = {"filename", "rucio_status", "reco_done", "reco_version", "reco_output_path"}
        if policy:
            required |= {"events", "auto_reco"}
        if not required.issubset(headers):
            raise ValueError(f"logbook columns missing: {sorted(required - set(headers))}")
        discover_settings = dict(settings, reco_version="3.1") if root_output else settings
        sheet_rows = read_all_records(worksheet)
        indexes = recovery_records(sheet_rows) if "auto_reco" in headers else {}
        records, eligible = discover(sheet_rows, discover_settings)
        if policy:
            if not ARCHIVE_MOUNT.is_mount():
                raise RuntimeError("Persistent recovery requires the Tier-1 mount")
            records = {run: row for run, (_, row) in indexes.items()}
            observations = {str(run): persistent.admission(
                row, run, RAW_ARCHIVE, ROOT_ARCHIVE, settings["deferred_runs"])
                for run, row in records.items()}
            for run, row in records.items():
                key = str(run)
                if observations[key] not in ("waiting_capacity", "root_present_needs_evidence"):
                    continue
                other = state_path(BASE / "root-migration" / f"{run:05d}")
                if other.is_file():
                    local(other)
                    migrated = json.loads(other.read_text())
                    if observations[key] == "root_present_needs_evidence":
                        observations[key] = publication_disposition(migrated, run, final_url(destination, run, True), row)
                    else:
                        observations[key] = "migration_attempt_pending"
            eligible = {run: row["filename"] for run, row in records.items()
                        if observations[str(run)] == "waiting_capacity"}
        if migration:
            migrations = migration_inputs(records)
            eligible = {run: records[run]["filename"] for run in migrations}
        rebuilt = {run for run, row in records.items()
                   if (parse_integer(row.get("reco_done")) or 0) > 0}
        if migration:
            rebuilt = {run for run, row in records.items()
                       if str(row.get("reco_output_path", "")).strip() == final_url(destination, run, True)}
        runs = {run for run in eligible if run not in settings["deferred_runs"]
                and persistent.operator_enabled(records[run])}
    active = 0
    waiting = []
    blocked = set(settings.get("deferred_runs", ()))
    validated = set()
    pending = set()
    known = set(runs)
    if policy:
        known.update(int(run) for run, value in observations.items()
                     if value in ("publication_missing_operator_review", "root_present_needs_evidence"))
    for directory in root.iterdir():
        if re.fullmatch(r"\d{5,}", directory.name):
            local(directory)
            known.add(int(directory.name))
    for run in sorted(known):
        url = final_url(destination, run, root_output)
        run_dir = root / f"{run:05d}"
        local(run_dir)
        state_file = state_path(run_dir)
        if state_file.is_symlink():
            raise ValueError(f"symlink state: {state_file}")
        if state_file.exists():
            state = json.loads(state_file.read_text())
            # Pre-release submissions have no product_url and still expect HDF5.
            previous_url = state.get("product_url", final_url(destination, run, migration))
            version = "3.1" if previous_url.endswith(".root") else settings["reco_version"]
            notification_options = dict(notifier=notifier, max_attempts=settings["max_attempts"]) if notifier else {}
            if run in records and not persistent.operator_enabled(records[run]):
                notification_options["preserve_diagnostics"] = True
            occupied = reconcile(run_dir, state, run, previous_url, settings["failure_days"], read_only,
                                 **notification_options)
            active += occupied
            if policy and run in records and persistent.operator_enabled(records[run]):
                disposition = observations[str(run)]
                if state["phase"] == "verified":
                    if previous_url == url and disposition == "root_present_needs_evidence":
                        disposition = publication_disposition(state, run, url, records[run])
                    elif run in runs:
                        disposition = "verified_legacy_state"
                elif run in runs or disposition == "root_present_needs_evidence":
                    source, jobs = lookup(state["attempt"])
                    if len(jobs) == 1 and jobs[0]["JobStatus"] == 5:
                        disposition = "hold"
                    elif run in runs and (not occupied or state["phase"] == "submitting"):
                        diagnosis = submit_diagnosis(run_dir, state, run) if state["phase"] == "submitting" else None
                        disposition, plan = persistent.retry(state, time.time(), policy, source, jobs, diagnosis)
                        if plan is not None:
                            plans[run] = plan
                            if occupied:
                                active -= 1
                            prior_state = {key: value for key, value in state.items() if key != "previous"}
                            prior_state.setdefault("failed_at", diagnosis[1] if diagnosis else time.time())
                            waiting.append((run, url, state["attempt_number"] + 1,
                                            state.get("previous", []) + [prior_state]))
                    elif len(jobs) == 1 and jobs[0]["JobStatus"] == 4:
                        disposition = "publication_verification_pending"
                    else:
                        disposition = "attempt_pending"
                observations[str(run)] = disposition
                if disposition in ("automatic_recovery_exhausted", "submission_recovery_exhausted",
                                   "submission_uncertain", "submission_failure", "terminal_attempt_unconfirmed",
                                   "verified_legacy_state"):
                    blocked.add(run)
                if notifier:
                    recovery_alert(notifier, root, run, state, disposition)
            if recovery and not policy and not occupied and state["phase"] == "failed":
                if state["attempt_number"] >= settings["max_attempts"]:
                    blocked.add(run)
            if (not occupied and state["phase"] in ("failed", "verified")
                    and (run not in records or persistent.operator_enabled(records[run]))):
                for previous in state.get("previous", []):
                    source, jobs = lookup(previous["attempt"])
                    if (previous.get("phase") != "submitting" and source == "history" and len(jobs) == 1
                            and jobs[0]["JobStatus"] in (3, 4)
                            and previous["failed_at"] + settings["failure_days"]*86400 <= time.time()):
                        clean_attempt(workdir(run_dir, previous["attempt"], run), dry_run=read_only)
            if state["phase"] == "verified":
                rebuilt.add(run)
                if run in records:
                    update = plan_logbook_update(run_dir, run, state, records[run], previous_url, version, read_only)
                    if update:
                        updates.append(update)
                if recovery and previous_url == url and run in eligible:
                    validate_receipt(state["publication"], dict(run=run, exit_code=0, status="success"),
                                     run, url, state["attempt"])
                    validated.add(run)
                    pending.add(run)  # Eligibility means the live row still requests reconstruction.
            if (not policy and not occupied and state["phase"] == "failed"
                    and state["attempt_number"] < settings["max_attempts"] and run in runs):
                history = state.get("previous", []) + [
                    {key: state[key] for key in ("attempt", "failed_at")}]
                waiting.append((run, url, state["attempt_number"] + 1, history))
        elif run in runs:
            waiting.append((run, url, 1, []))
            if policy:
                plans[run] = (1, 0, 0)
        elif policy and notifier and str(run) in observations:
            recovery_alert(notifier, root, run, {}, observations[str(run)])
    limit = settings.get("migration_max_active", 40) if migration else settings["max_active"]
    late_runs = {run for run in runs if root_output and not migration and late_rucio_row(records[run])}
    for run, _, _, _ in waiting:
        if run in late_runs:
            existing = ROOT_ARCHIVE / f"run{run:05d}_iq_v3.1.root"
            try:
                existing.stat()
            except FileNotFoundError:
                continue
            print(f"Run {run}: existing ROOT publication requires reconciliation; submission deferred")
            runs.remove(run)
    waiting = [entry for entry in waiting if entry[0] in runs]
    finish = False
    if recovery:
        if not records:
            raise ValueError("ROOT recovery cannot use an empty live logbook")
        roots = set()
        for entry in ROOT_ARCHIVE.iterdir():
            match = re.fullmatch(r"run(\d{5,})_iq_v3\.1\.root", entry.name)
            if match:
                roots.add(int(match[1]))
        if not roots:
            raise ValueError("ROOT recovery requires a readable, populated publication archive")
        eligible_runs = set(eligible)
        pending |= eligible_runs & (roots - validated)
        # A verified receipt for an absent archive entry needs investigation.
        consistent = validated <= roots and not (pending - blocked) and not updates
        backlog = recovery_backlog(eligible_runs, blocked, validated & roots, pending)
        jobs = subprocess.check_output(
            ["condor_q", "-constraint", "FlashRun3Attempt isnt undefined", "-af", "JobStatus"],
            text=True)
        queue = Counter(map(int, jobs.split()))
        print("ROOT recovery backlog " + json.dumps(dict(
            backlog, running_jobs=queue[2], idle_jobs=queue[1], held_jobs=queue[5],
            consistent=consistent), sort_keys=True), flush=True)
        limit = recovery_limit(settings, backlog, consistent)
        finish = limit != settings["max_active"]
    slots = max(0, limit - active)
    submissions = waiting[:slots if migration else min(slots, settings.get("max_submit_per_cycle", slots))]
    if policy:
        print("Persistent recovery dispositions: " + json.dumps(Counter(observations.values()), sort_keys=True))
        if not read_only:
            persistent.save_observations(BASE / "persistent-recovery.json", observations)
        if getattr(args, "recovery_report", None):
            with args.recovery_report.open("x") as output:
                json.dump(observations, output, indent=2, sort_keys=True)
                output.write("\n")
    if dry_run:
        print(f"Eleggibili ({len(eligible)}): {sorted(eligible)}")
        print(f"Già ricostruiti ({len(rebuilt)}): {sorted(rebuilt)}")
        pending = sorted(set(records) - rebuilt - {job[0] for job in submissions})
        print(f"In attesa dopo le sottomissioni previste ({len(pending)}): {pending}")
        print(f"Slot occupati da tentativi locali: {active}")
        print(f"Job da sottomettere ({len(submissions)}): {[job[0] for job in submissions]}")
        print("Aggiornamenti logbook:", [
            (state["run_number"], state["target_reco_done"], state["reco_version"], state["output_path"])
            for _, state in updates])
    if read_only:
        return
    if updates:
        try:
            update_reco_done_batch(worksheet, headers, updates)
        except Exception as error:
            if notifier:
                for run_dir, state in updates:
                    run = state["run_number"]
                    notifier.fault(f"logbook:{root.name}:{run}", "Google logbook reconciliation failing",
                                   "Repeated update failures after verified publication.",
                                   state_path(run_dir), run=run, after=2, error=error)
            raise
        if notifier:
            for run_dir, state in updates:
                run = state["run_number"]
                key = f"logbook:{root.name}:{run}"
                if state.get("status") == "sheet_updated":
                    notifier.resolved(key, "Google logbook reconciliation restored",
                                      "The validated publication was written to Google Sheets.",
                                      state_path(run_dir), run=run)
                else:
                    notifier.fault(key, "Google logbook reconciliation pending",
                                   "Repeated reconciliation attempts have not updated the row.",
                                   state_path(run_dir), run=run, after=2)
    if finish and getattr(args, "cron", False):
        finish_recovery(args.config, settings, limit)
    for run, url, number, history in submissions:
        run_dir = root / f"{run:05d}"
        attempt = uuid.uuid4().hex
        directory = workdir(run_dir, attempt, run)
        input_state = migrations.get(run)
        if root_output:
            submit = prepare(directory.parent, run, settings["split_pairs"], url, args.pilot, attempt,
                             settings, input_state["reference"] if input_state else None)
        else:
            submit = prepare(directory.parent, run, settings["split_pairs"], url, args.pilot, attempt)
        state = dict(attempt=attempt, attempt_number=number, phase="submitting", previous=history,
                     product_url=url)
        if run in late_runs:
            state["late_rucio_recovery"] = True
        if input_state:
            state["migration"] = input_state
        if indexes:
            if run not in indexes:
                continue
            values = worksheet.row_values(indexes[run][0])
            fresh = dict(zip(headers, values))
            if (get_run_number(fresh) != run or fresh.get("filename") != records[run]["filename"]
                    or not persistent.operator_enabled(fresh)):
                continue
            if policy:
                if persistent.admission(fresh, run, RAW_ARCHIVE, ROOT_ARCHIVE,
                                        settings["deferred_runs"]) != "waiting_capacity":
                    continue
                other = state_path(BASE / "root-migration" / f"{run:05d}")
                if other.exists():
                    continue
                if history:
                    source, jobs = lookup(history[-1]["attempt"])
                    diagnosis = submit_diagnosis(run_dir, history[-1], run) if history[-1]["phase"] == "submitting" else None
                    _, plan = persistent.retry(history[-1], time.time(), policy, source, jobs, diagnosis)
                    if plan != plans[run]:
                        continue
                episode, attempts, failures = plans[run]
                state.update(recovery_episode=episode, episode_attempts=attempts+1,
                             submission_failures=failures, recovery_baseline=persistent.baseline(fresh))
        save_state(run_dir, state)
        try:
            cluster = submit_job(submit, show_output=False) if notifier else submit_job(submit)
        except SubmissionError as error:
            if policy:
                state["submission_failures"] += 1
                save_state(run_dir, state)
            if notifier:
                output = error.stdout + "\n" + error.stderr
                link = approval_url(output)
                notifier.fault("condor:auth" if link else f"submit:{root.name}:{run}",
                               "HTCondor authentication required" if link else "HTCondor submission failed",
                               approval_message(output, link) if link else
                               "Condor did not confirm submission. Inspect the local submission diagnostics.",
                               submit.parent / "submit_error.json", run=run, approval=link, error=error)
            raise
        state.update(cluster=cluster, phase="submitted")
        if policy:
            state["submission_failures"] = 0
        save_state(run_dir, state)
        if notifier:
            print(f"Run {run}: submitted to cluster {cluster}.", flush=True)
            notifier.resolved("condor:auth", "HTCondor submission restored",
                              f"An authenticated submission was accepted as cluster {cluster}.",
                              state_path(run_dir), run=run)
            notifier.resolved(f"submit:{root.name}:{run}", "HTCondor submission restored",
                              f"The scheduler accepted cluster {cluster}.", state_path(run_dir), run=run)


def scheduled_cycles(root, settings, args):
    cycle(root, settings, args)
    if (args.cron and not args.pilot and settings.get("output_format") == "root"
            and settings.get("migration_auto")):
        migration = BASE / "root-migration"
        local(migration)
        migration.mkdir(exist_ok=True)
        print("Run3 ROOT migration", flush=True)
        # The production lock is already held. Each cycle has its own slot budget.
        cycle(migration, settings, argparse.Namespace(**dict(vars(args), migrate_root=True)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--gc-dry-run", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Anteprima Run3 in sola lettura del logbook")
    parser.add_argument("--recovery-report", type=Path, help="Save the persistent-recovery dry-run dispositions")
    parser.add_argument("--cron", action="store_true")
    parser.add_argument("--migrate-root", action="store_true")
    args = parser.parse_args()
    settings = json.loads(args.config.read_text())
    if args.recovery_report and (not args.dry_run or args.migrate_root or not persistent.options(settings)):
        parser.error("--recovery-report requires a persistent recovery dry run")
    if "backlog_recovery" in settings:
        policy = settings["backlog_recovery"]
        if (policy != {"threshold": 20, "normal_max_active": 20}
                or settings["max_active"] != 60 or settings.get("output_format") != "root"):
            parser.error("invalid ROOT backlog recovery policy")
    if (settings["max_active"] < 1 or settings["max_submit_per_cycle"] < 1
            or settings["failure_days"] < 7 or settings["max_attempts"] < 1):
        parser.error("invalid Run3 concurrency or retention")
    if args.migrate_root and (args.pilot or args.cron or
                              (settings.get("output_format") != "root" and not args.dry_run)):
        parser.error("ROOT migration requires an enabled ROOT configuration, except in dry-run")
    if settings.get("migration_max_active", 40) < 1:
        parser.error("invalid migration concurrency")
    if args.prepare_only and not args.pilot:
        parser.error("only the isolated pilot supports prepare-only")
    if args.dry_run and (args.pilot or args.cron):
        parser.error("--dry-run is for manual production planning")
    if not (args.pilot or args.dry_run or settings["enabled"]):
        parser.error("production requires explicit activation in the local configuration")
    if not args.pilot:
        pilot_state = state_path(BASE / "pilot/01148")
        local(pilot_state)
        if (not pilot_state.is_file() or
                json.loads(pilot_state.read_text()).get("phase") != "verified"):
            parser.error("production requires a verified isolated pilot")
    root = BASE / ("pilot" if args.pilot else "root-migration" if args.migrate_root else "production")
    local(root)
    root.mkdir(parents=True, exist_ok=True)
    lock_dir = BASE / "production" if args.migrate_root else root
    local(lock_dir)
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock = lock_dir / ".autoreco.lock"
    if lock.is_symlink():
        raise ValueError("symlink runtime lock")
    with lock.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if args.dry_run:
                raise SystemExit("Production lock busy. Dry run did not execute.")
            return
        if json.loads(args.config.read_text()) != settings:
            raise SystemExit("Production configuration changed while taking the lock. Retry next cycle.")
        if args.cron:
            logs = BASE / "logs"
            local(logs)
            logs.mkdir(exist_ok=True)
            today = datetime.now().astimezone().date()
            logfile = logs / f"autoreco-{today.isoformat()}.log"
            if not args.gc_dry_run:
                fd = os.open(logfile, os.O_APPEND | os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
                os.dup2(fd, 1)
                os.dup2(fd, 2)
                os.close(fd)
            for entry in logs.iterdir():
                match = re.fullmatch(r"autoreco-(\d{4}-\d{2}-\d{2})\.log", entry.name)
                if match and not entry.is_symlink() and entry.is_file():
                    try:
                        date = datetime.fromisoformat(match[1]).date()
                    except ValueError:
                        continue
                    if (today - date).days >= 30:
                        if args.gc_dry_run:
                            print(f"would remove {entry}")
                        else:
                            entry.unlink()
        if args.prepare_only:
            manual = root / "manual" / uuid.uuid4().hex
            local(manual)
            print(prepare(manual, 1148, settings["split_pairs"],
                          f"{PILOT}/run01148_iq_v3.h5", True, uuid.uuid4().hex))
        else:
            if args.cron and not args.pilot and not args.gc_dry_run:
                args.notifier = Notifier(BASE / "discord-notifications.json",
                                         settings.get("discord_reminder_seconds", 0))
            try:
                scheduled_cycles(root, settings, args)
            except Exception as error:
                notifier = getattr(args, "notifier", None)
                if notifier and notifier.reported_exception is not error:
                    notifier.fault(f"scheduler:{type(error).__name__}", "Run3 scheduler stopped",
                                   "An operational error stopped the current cycle. Inspect the local log.",
                                   logfile)
                raise


if __name__ == "__main__":
    main()
