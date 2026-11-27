"""Bounded, opt-in Run3 recovery decisions. The production lock owns their writes."""
import json
import os
import re
import stat
import tempfile
from pathlib import Path

from autoreco import get_run_number, parse_integer

METADATA = ("reco_done", "reco_version", "reco_output_path")
DEFAULT_COOLDOWN = 24 * 60 * 60
DEFAULT_EPISODES = 3  # Includes the initial episode.
DEFAULT_SUBMISSION_LIMIT = 3


def operator_enabled(row):
    """Unknown flag values fail closed; the scheduler never writes this field."""
    flag = row.get("auto_reco")
    return flag is None or (not isinstance(flag, bool) and str(flag).strip() in ("", "0"))


def baseline(row):
    return {key: str(row.get(key, "") if row.get(key) is not None else "").strip()
            for key in METADATA}


def file_exists(path, *, nonempty=False):
    try:
        info = path.stat()
    except FileNotFoundError:
        return False
    return (stat.S_ISREG(info.st_mode) and info.st_size > 0) if nonempty else True


def admission(row, run, raw_archive, root_archive, deferred):
    if not operator_enabled(row):
        return "operator_excluded" if str(row.get("auto_reco")).strip() == "-2" else "invalid_control"
    value = row.get("events")
    if not re.fullmatch(r"[0-9]+", str(value).strip()):
        return "event_count_unknown"
    if int(value) < 1000:
        return "below_event_threshold"
    if run in deferred:
        return "host_deferred"
    if get_run_number(row) != run or row.get("filename") != f"run{run:05d}.mid.gz":
        return "filename_conflict"
    if str(row.get("reco_requested_version") or "").strip() not in ("", "3.1"):
        return "requested_version_conflict"
    if file_exists(root_archive / f"run{run:05d}_iq_v3.1.root"):
        return "root_present_needs_evidence"
    if (str(row.get("reco_version") or "").strip() == "3.1"
            or str(row.get("reco_output_path") or "").endswith("_iq_v3.1.root")):
        return "publication_missing_operator_review"
    if (parse_integer(row.get("rucio_status")) != 0
            or not file_exists(raw_archive / row["filename"], nonempty=True)):
        return "raw_unavailable"
    return "waiting_capacity"


def options(settings):
    policy = settings.get("persistent_recovery")
    if policy is None:
        return None
    keys = {"cooldown_seconds", "max_episodes", "submission_cooldown_seconds", "max_submission_failures"}
    if not isinstance(policy, dict) or set(policy) - keys:
        raise ValueError("Invalid persistent recovery configuration")
    values = dict(cooldown_seconds=DEFAULT_COOLDOWN, max_episodes=DEFAULT_EPISODES,
                  submission_cooldown_seconds=3600, max_submission_failures=DEFAULT_SUBMISSION_LIMIT)
    values.update(policy)
    if any(type(v) is not int or v < 1 for v in values.values()):
        raise ValueError("Persistent recovery limits and cooldowns must be positive integers")
    if settings["max_attempts"] != 2:
        raise ValueError("Persistent recovery requires two immediate attempts per episode")
    return values


def retry(state, now, policy, source, jobs, diagnosed=None):
    """Decide using exact Condor evidence and retain separate scientific counters."""
    episode = state.get("recovery_episode", 1)
    failures = state.get("episode_attempts", state["attempt_number"])
    submit_failures = state.get("submission_failures", 0)
    if state["phase"] == "submitting":
        if source != "history" or jobs or state.get("cluster") or not diagnosed:
            return "submission_uncertain", None
        category, observed_at = diagnosed
        failures = max(failures - 1, 0)
        if submit_failures == 0:
            # A legacy unconfirmed attempt never consumed a scientific slot.
            submit_failures = 1
        if category != "authentication_required":
            return "submission_failure", None
        if submit_failures >= policy["max_submission_failures"]:
            return "submission_recovery_exhausted", None
        if now < observed_at + policy["submission_cooldown_seconds"]:
            return category, None
        return "waiting_capacity", (episode, failures, submit_failures)
    if state["phase"] != "failed":
        return "attempt_pending", None
    if source != "history" or len(jobs) != 1:
        return "terminal_attempt_unconfirmed", None
    job = jobs[0]
    if (job.get("JobStatus") not in (3, 4)
            or (not job.get("ExitBySignal") and not (
                type(job.get("ExitCode")) is int and job["ExitCode"] != 0))):
        return "terminal_attempt_unconfirmed", None
    if failures < 2:
        return "waiting_capacity", (episode, failures, 0)
    if episode >= policy["max_episodes"]:
        return "automatic_recovery_exhausted", None
    if now < state["failed_at"] + policy["cooldown_seconds"]:
        return "reconstruction_cooldown", None
    return "waiting_capacity", (episode + 1, 0, 0)


def save_observations(path, observations):
    """Remember pending runs even if a later logbook snapshot omits a row."""
    if path.is_symlink():
        raise ValueError("Unexpected recovery state symlink")
    try:
        previous = json.loads(path.read_text())
    except FileNotFoundError:
        previous = {}
    previous = {run: "missing_logbook_row" for run, status in previous.items()
                if run not in observations and status != "validated"}
    previous.update(observations)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        try:
            json.dump(previous, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
