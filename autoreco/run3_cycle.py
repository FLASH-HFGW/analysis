"""Isolated Run3 cycle using existing HTCondor submission and state helpers."""
import argparse
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import time
from types import SimpleNamespace
import uuid

from autoreco import (get_run_number, parse_integer, runs_to_reconstruct, save_state,
                      state_path, submit_job, transfer_job_data, update_reco_done_batch)
from googletool import get_headers, open_google_sheet, read_all_records
from noise_jobs import build_iq_v3_jobs, check_run3_inputs
from run3_storage import PILOT, PRODUCTION, RAW

BASE = Path("/home/mazzitel/HFGW/analysis-runtime/autoreco/Run3")
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


def finalize_verified(run_dir, state, directory, dry_run, queue):
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
    keep_logs = time.time() - state["verified_at"] < 30*86400
    clean_attempt(directory, dry_run=dry_run, keep_logs=keep_logs)
    if not dry_run:
        state.update(queue_closed=True, payload_cleaned=True, logs_cleaned=not keep_logs)
        save_state(run_dir, state)
    return False


def reconcile(run_dir, state, run, url, retention, dry_run):
    """Return True if the run still occupies a slot."""
    attempt = state["attempt"]
    directory = workdir(run_dir, attempt, run)
    if state["phase"] == "verified":
        age = time.time() - state["verified_at"]
        if state.get("queue_closed"):
            if state.get("logs_cleaned") or (state.get("payload_cleaned") and age < 30*86400):
                return False
            queue = []
        else:
            source, jobs = lookup(attempt)
            queue = jobs if source == "active" else []
        return finalize_verified(run_dir, state, directory, dry_run, queue)
    source, jobs = lookup(attempt)
    if len(jobs) != 1:
        return state["phase"] not in ("verified", "failed") or source == "active"
    job = jobs[0]
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
            return True
        identity = json.loads(receipt.read_text())
        completion = json.loads(status.read_text())
        validate_receipt(identity, completion, run, url, attempt)
        if dry_run:
            return source == "active"
        state.update(phase="verified", publication=identity, cluster=job["ClusterId"],
                     verified_at=time.time())
        save_state(run_dir, state)
        return finalize_verified(run_dir, state, directory, dry_run,
                                 jobs if source == "active" else [])
    if job["JobStatus"] not in (3, 4):
        return True
    if state["phase"] != "failed" and not dry_run:
        state.update(phase="failed", failed_at=time.time(), cluster=job["ClusterId"])
        save_state(run_dir, state)
    if state.get("failed_at", time.time()) + retention*86400 <= time.time():
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
    prior = migration["reco_done"] if migration else 0
    target = prior if migration else 1
    current_path = str(record.get("reco_output_path", "")).strip()
    current_version = str(record.get("reco_version", "")).strip()
    if done == target and current_path == url and current_version == version:
        if not dry_run:
            state["status"] = "sheet_updated"
            save_state(run_dir, state)
        return None
    if done != prior or (migration and (current_path != migration["reference"]["url"]
                                        or current_version != migration["expected_version"])):
        print(f"Run {run}: earlier reconstruction references changed; update deferred")
        return None
    return run_dir, dict(state, run_number=run, filename=filename, target_reco_done=target,
                         expected_reco_done=prior, reco_version=version, output_path=url)


def cycle(root, settings, args):
    destination = PILOT if args.pilot else PRODUCTION
    dry_run = getattr(args, "dry_run", False)
    read_only = args.gc_dry_run or dry_run
    migration = getattr(args, "migrate_root", False)
    root_output = not args.pilot and (migration or settings.get("output_format") == "root")
    migrations = {}
    records, eligible, updates, rebuilt = {}, {}, [], set()
    if args.pilot:
        runs = {1148}
    else:
        worksheet = open_google_sheet()
        headers = get_headers(worksheet)
        required = {"filename", "rucio_status", "reco_done", "reco_version", "reco_output_path"}
        if not required.issubset(headers):
            raise ValueError(f"logbook columns missing: {sorted(required - set(headers))}")
        discover_settings = dict(settings, reco_version="3.1") if root_output else settings
        records, eligible = discover(read_all_records(worksheet), discover_settings)
        if migration:
            migrations = migration_inputs(records)
            eligible = {run: records[run]["filename"] for run in migrations}
        rebuilt = {run for run, row in records.items()
                   if (parse_integer(row.get("reco_done")) or 0) > 0}
        if migration:
            rebuilt = {run for run, row in records.items()
                       if str(row.get("reco_output_path", "")).strip() == final_url(destination, run, True)}
        runs = set(eligible) - set(settings["deferred_runs"])
    active = 0
    waiting = []
    known = set(runs)
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
            occupied = reconcile(run_dir, state, run, previous_url, settings["failure_days"], read_only)
            active += occupied
            if not occupied and state["phase"] in ("failed", "verified"):
                for previous in state.get("previous", []):
                    source, jobs = lookup(previous["attempt"])
                    if (source == "history" and len(jobs) == 1
                            and jobs[0]["JobStatus"] in (3, 4)
                            and previous["failed_at"] + settings["failure_days"]*86400 <= time.time()):
                        clean_attempt(workdir(run_dir, previous["attempt"], run), dry_run=read_only)
            if state["phase"] == "verified":
                rebuilt.add(run)
                if run in records:
                    update = plan_logbook_update(run_dir, run, state, records[run], previous_url, version, read_only)
                    if update:
                        updates.append(update)
            if (not occupied and state["phase"] == "failed"
                    and state["attempt_number"] < settings["max_attempts"] and run in runs):
                history = state.get("previous", []) + [
                    {key: state[key] for key in ("attempt", "failed_at")}]
                waiting.append((run, url, state["attempt_number"] + 1, history))
        elif run in runs:
            waiting.append((run, url, 1, []))
    limit = settings.get("migration_max_active", 40) if migration else settings["max_active"]
    slots = max(0, limit - active)
    submissions = waiting[:slots if migration else min(slots, settings.get("max_submit_per_cycle", slots))]
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
        update_reco_done_batch(worksheet, headers, updates)
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
        if input_state:
            state["migration"] = input_state
        save_state(run_dir, state)
        state.update(cluster=submit_job(submit), phase="submitted")
        save_state(run_dir, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--gc-dry-run", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Anteprima Run3 in sola lettura del logbook")
    parser.add_argument("--cron", action="store_true")
    parser.add_argument("--migrate-root", action="store_true")
    args = parser.parse_args()
    settings = json.loads(args.config.read_text())
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
            return
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
            cycle(root, settings, args)


if __name__ == "__main__":
    main()
