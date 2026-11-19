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
import uuid

from autoreco import save_state, state_path, submit_job, transfer_job_data
from noise_jobs import build_iq_v3_jobs, check_run3_inputs
from run3_storage import ENDPOINT, PILOT, PRODUCTION, RAW, size, verify

BASE = Path("/home/mazzitel/HFGW/analysis-runtime/autoreco/Run3")
ANALYSIS = Path(__file__).resolve().parents[1] / "examples/analyze_midas_iq_v3.py"
ARTIFACT = re.compile(r"(script\.sh|submit\.sub|iq_v3_job\.json|publication\.json|"
                      r"submit_error\.json|run\d+_job_status\.json|"
                      r"analyze_midas_iq_v3\.py|iq_acquisition_metadata\.py|"
                      r"iq_compact_spectra\.py|run3_storage\.py|"
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


def reconcile(run_dir, state, run, url, retention, dry_run):
    """Return True if the run still occupies a slot."""
    attempt = state["attempt"]
    directory = workdir(run_dir, attempt, run)
    if state["phase"] == "verified":
        age = time.time() - state["verified_at"]
        if state.get("logs_cleaned") or (state.get("payload_cleaned") and age < 30*86400):
            return False
    source, jobs = lookup(attempt)
    if source == "active" and len(jobs) == 1:
        job = jobs[0]
        if (job["JobStatus"] == 4 and job.get("ExitCode") == 0
                and not job.get("ExitBySignal") and not dry_run
                and state["phase"] != "verified" and not state.get("output_retrieved")):
            transfer_job_data(str(job["ClusterId"]), directory)
            state.update(output_retrieved=True, cluster=job["ClusterId"])
            save_state(run_dir, state)
    if source == "active" or len(jobs) != 1:
        return state["phase"] not in ("verified", "failed") or source == "active"
    job = jobs[0]
    succeeded = job["JobStatus"] == 4 and job.get("ExitCode") == 0 and not job.get("ExitBySignal")
    if succeeded:
        if state["phase"] != "verified":
            receipt = directory / "publication.json"
            status = directory / f"run{run:05d}_job_status.json"
            local(receipt)
            local(status)
            if not (receipt.is_file() and status.is_file()):
                return True
            identity = json.loads(receipt.read_text())
            completion = json.loads(status.read_text())
            if identity["url"] != url or completion["run"] != run or completion["exit_code"] != 0:
                raise ValueError("unexpected publication receipt")
        else:
            identity = state["publication"]
        verify(url, identity)
        if not dry_run and state["phase"] != "verified":
            state.update(phase="verified", publication=identity, cluster=job["ClusterId"],
                         verified_at=time.time())
            save_state(run_dir, state)
        if state["phase"] == "verified":
            keep_logs = time.time() - state["verified_at"] < 30*86400
            clean_attempt(directory, dry_run=dry_run, keep_logs=keep_logs)
            if not dry_run:
                state.update(payload_cleaned=True, logs_cleaned=not keep_logs)
                save_state(run_dir, state)
        return False
    if state["phase"] == "verified" or job["JobStatus"] not in (3, 4):
        return True
    if size(url, missing=True) is not None:
        print(f"Run {run}: final exists after failed job; manual reconciliation required")
        return True
    if state["phase"] != "failed" and not dry_run:
        state.update(phase="failed", failed_at=time.time(), cluster=job["ClusterId"])
        save_state(run_dir, state)
    if state.get("failed_at", time.time()) + retention*86400 <= time.time():
        clean_attempt(directory, dry_run=dry_run)
    return False


def prepare(root, run, pairs, url, probe, attempt):
    submit = build_iq_v3_jobs([run], root, RAW, ANALYSIS, pairs, None, 1,
                              publication={"url": url, "probe": probe}, attempt=attempt)[0][1]
    check_run3_inputs(submit)
    return submit


def cycle(root, settings, args):
    destination = PILOT if args.pilot else PRODUCTION
    runs = [1148] if args.pilot else sorted(set(settings["closed_runs"]))
    if any(type(run) is not int or run < 1148 for run in runs):
        raise ValueError("invalid ready-run number")
    active = 0
    waiting = []
    known = set(runs)
    for directory in root.iterdir():
        if re.fullmatch(r"\d{5,}", directory.name):
            local(directory)
            known.add(int(directory.name))
    for run in sorted(known):
        url = f"{destination}/run{run:05d}_iq_v3.h5"
        run_dir = root / f"{run:05d}"
        local(run_dir)
        state_file = state_path(run_dir)
        if state_file.is_symlink():
            raise ValueError(f"symlink state: {state_file}")
        if state_file.exists():
            state = json.loads(state_file.read_text())
            occupied = reconcile(run_dir, state, run, url, settings["failure_days"], args.gc_dry_run)
            active += occupied
            if not occupied and state["phase"] in ("failed", "verified"):
                for previous in state.get("previous", []):
                    source, jobs = lookup(previous["attempt"])
                    if (source == "history" and len(jobs) == 1
                            and jobs[0]["JobStatus"] in (3, 4)
                            and previous["failed_at"] + settings["failure_days"]*86400 <= time.time()):
                        clean_attempt(workdir(run_dir, previous["attempt"], run), dry_run=args.gc_dry_run)
            if (not occupied and state["phase"] == "failed"
                    and state["attempt_number"] < settings["max_attempts"] and run in runs):
                history = state.get("previous", []) + [
                    {key: state[key] for key in ("attempt", "failed_at")}]
                waiting.append((run, url, state["attempt_number"] + 1, history))
        elif run in runs:
            waiting.append((run, url, 1, []))
    if args.gc_dry_run:
        return
    for run, url, number, history in waiting[:max(0, settings["max_active"] - active)]:
        if size(url, missing=True) is not None:
            print(f"Run {run}: existing final requires manual reconciliation")
            continue
        raw = f"{ENDPOINT}/{RAW}/run{run:05d}.mid.gz"
        if not size(raw, missing=True):
            continue
        run_dir = root / f"{run:05d}"
        attempt = uuid.uuid4().hex
        directory = workdir(run_dir, attempt, run)
        submit = prepare(directory.parent, run, settings["split_pairs"], url, args.pilot, attempt)
        state = dict(attempt=attempt, attempt_number=number, phase="submitting", previous=history)
        save_state(run_dir, state)
        state.update(cluster=submit_job(submit), phase="submitted")
        save_state(run_dir, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--gc-dry-run", action="store_true")
    parser.add_argument("--cron", action="store_true")
    args = parser.parse_args()
    settings = json.loads(args.config.read_text())
    if not 1 <= settings["max_active"] <= 4 or settings["failure_days"] < 7 or settings["max_attempts"] < 1:
        parser.error("invalid Run3 concurrency or retention")
    if args.prepare_only and not args.pilot:
        parser.error("only the isolated pilot supports prepare-only")
    if not (args.pilot or settings["enabled"]):
        parser.error("production requires explicit activation in the local configuration")
    if not args.pilot:
        pilot_state = state_path(BASE / "pilot/01148")
        local(pilot_state)
        if (not pilot_state.is_file() or
                json.loads(pilot_state.read_text()).get("phase") != "verified"):
            parser.error("production requires a verified isolated pilot")
    root = BASE / ("pilot" if args.pilot else "production")
    local(root)
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".autoreco.lock"
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
            account = settings.get("submit_oidc_account")
            if account and not os.environ.get("BEARER_TOKEN"):
                os.environ["BEARER_TOKEN"] = subprocess.check_output(
                    ["oidc-token", account], text=True).strip()
            cycle(root, settings, args)


if __name__ == "__main__":
    main()
