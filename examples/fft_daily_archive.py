"""Lossless daily containers for FFT NPZ products (acquisition dates in UTC)."""

import argparse
from contextlib import ExitStack
import fcntl
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from zipfile import ZIP_STORED, ZipFile

import numpy as np


FORMAT = "fft-daily-npz-v1"
INDEX = "manifest.json"
RCLONE_CONFIG = "/cvmfs/mazzitel-personalrepo.infn.it/FLASH/config/rclone.conf"


def utc_day(timestamp):
    timestamp = float(timestamp)
    if not math.isfinite(timestamp) or timestamp <= 0:
        raise ValueError("Invalid acquisition timestamp")
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")


def metadata(name, data, day=None):
    if Path(name).name != name or not re.fullmatch(r"run\d+(?:_fft_\d+s)?\.npz", name):
        raise ValueError("Unsupported FFT member: " + name)
    record = {"run": int(re.match(r"run(\d+)", name)[1]),
              "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    with np.load(io.BytesIO(data), allow_pickle=False) as arrays:
        if "window_start" in arrays.files:
            for key in ("window_start", "window_stop", "window_seconds", "window_index"):
                record[key] = arrays[key].item()
            record["day"] = utc_day(record["window_start"])
        elif day:
            record["day"] = day
        else:
            raise ValueError("Run summary requires an acquisition date: " + name)
    return record


class RunBundle:
    """Worker-local bundle; the coordinator alone writes the daily archives."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.archive = ZipFile(self.path, "w", compression=ZIP_STORED, allowZip64=True)
        self.entries = {}

    def add(self, name, day=None, **arrays):
        buffer = io.BytesIO()
        np.savez_compressed(buffer, **arrays)
        data = buffer.getvalue()
        record = metadata(name, data, day)
        if name in self.entries:
            raise ValueError("Duplicate bundle entry: " + name)
        self.archive.writestr(name, data)
        self.entries[name] = record

    def close(self):
        self.archive.writestr(INDEX, json.dumps({"format": FORMAT, "entries": self.entries}))
        self.archive.close()


def read_index(archive):
    doc = json.loads(archive.read(INDEX))
    if doc.get("format") != FORMAT:
        raise ValueError("Unsupported FFT archive format")
    names = archive.namelist()
    if len(names) != len(set(names)) or set(names) != set(doc["entries"]) | {INDEX}:
        raise ValueError("Duplicate or unindexed archive members")
    return doc


def load_product(directory, name):
    """Read one legacy NPZ or one NPZ inside a daily container."""
    directory = Path(directory)
    if Path(name).name != name:
        raise ValueError("Expected an NPZ basename")
    raw = directory / name
    if raw.is_file():
        return np.load(raw, allow_pickle=False)
    for path in sorted(directory.glob("fft_????-??-??.zip")):
        with ZipFile(path) as archive:
            if name in archive.namelist():
                return np.load(io.BytesIO(archive.read(name)), allow_pickle=False)
    raise FileNotFoundError(name)


def verify(path):
    with ZipFile(path) as archive:
        doc = read_index(archive)
        for name, record in doc["entries"].items():
            if not re.fullmatch(r"run\d+(?:_fft_\d+s)?\.npz", name):
                raise ValueError("Invalid FFT member name: " + name)
            if int(re.match(r"run(\d+)", name)[1]) != record["run"]:
                raise ValueError("Run number mismatch: " + name)
            if "window_start" in record and utc_day(record["window_start"]) != record["day"]:
                raise ValueError("Acquisition date mismatch: " + name)
            if "date" in doc and record["day"] != doc["date"]:
                raise ValueError("FFT stored in the wrong daily archive: " + name)
            data = archive.read(name)
            if len(data) != record["size"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
                raise ValueError("FFT checksum mismatch: " + name)
    return doc


def remote_command(*args):
    subprocess.run(["rclone", *map(str, args), "--config", RCLONE_CONFIG], check=True)


def publish(path, remote):
    """Upload to a temporary object, verify its contents, then rename it."""
    target = remote.rstrip("/") + "/" + path.name
    temporary = target + ".uploading"
    remote_command("copyto", path, temporary)
    digest = hashlib.sha256()
    with subprocess.Popen(["rclone", "cat", temporary, "--config", RCLONE_CONFIG],
                          stdout=subprocess.PIPE) as process:
        for block in iter(lambda: process.stdout.read(1024 * 1024), b""):
            digest.update(block)
        if process.wait() != 0:
            raise RuntimeError("Remote archive verification failed")
    with path.open("rb") as stream:
        expected = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            expected.update(block)
    if digest.digest() != expected.digest():
        raise ValueError("Remote archive SHA256 mismatch")
    remote_command("moveto", temporary, target, "--ignore-times")


def seed_remote_archives(directory, remote):
    """A fresh local cache must not erase already published runs."""
    remote_command("mkdir", remote)
    result = subprocess.run(["rclone", "lsf", remote, "--files-only",
        "--include", "fft_????-??-??.zip", "--config", RCLONE_CONFIG],
        check=True, text=True, capture_output=True)
    for name in result.stdout.splitlines():
        if not re.fullmatch(r"fft_\d{4}-\d{2}-\d{2}\.zip", name):
            raise ValueError("Unexpected daily archive name: " + name)
        path = directory / name
        if not path.exists():
            temporary = directory / (name + ".download")
            remote_command("copyto", remote.rstrip("/") + "/" + name, temporary)
            verify(temporary)
            os.replace(temporary, path)


def consolidate(sources, directory, remote=None, replace_runs=False):
    """Merge raw NPZ or worker bundles; retain every original NPZ byte.

    The lock covers read/modify/write and remote publication. Atomic local
    replacements never append duplicate ZIP entries. Retries always republish
    the touched days, including after a previous upload failure.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".fft_daily.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if remote:
            seed_remote_archives(directory, remote)
        additions = {}
        summaries = []
        run_days = {}
        # References avoid keeping the scientific arrays of a whole day in RAM.
        for source in sorted(map(Path, sources)):
            if source.suffix == ".zip":
                doc = verify(source)
                bundle_run = re.fullmatch(r"run(\d+)_fft_windows\.zip", source.name)
                if bundle_run:
                    run = int(bundle_run[1])
                    if {record["run"] for record in doc["entries"].values()} != {run} or (
                            f"run{run:05d}.npz" not in doc["entries"]):
                        raise ValueError("Incomplete or mismatched worker bundle: " + str(source))
                records = [(name, record, (source, name)) for name, record in doc["entries"].items()]
            else:
                data = source.read_bytes()
                if re.fullmatch(r"run\d+\.npz", source.name):
                    summaries.append(source)
                    continue
                record = metadata(source.name, data)
                records = [(source.name, record, (source, None))]
            for name, record, reference in records:
                key = (record["day"], name)
                if key in additions:
                    raise ValueError("Duplicate FFT input: " + name)
                additions[key] = (record, reference)
                if "window_start" in record:
                    run = record["run"]
                    timestamp = record["window_start"]
                    run_days[run] = min(run_days.get(run, timestamp), timestamp)
        for source in summaries:
            run = int(re.match(r"run(\d+)", source.name)[1])
            if run not in run_days:
                raise ValueError("No dated window for run summary: " + source.name)
            record = metadata(source.name, source.read_bytes(), utc_day(run_days[run]))
            key = (record["day"], source.name)
            if key in additions:
                raise ValueError("Duplicate run summary: " + source.name)
            additions[key] = (record, (source, None))
        runs = {record["run"] for record, _ in additions.values()}
        days = {day for day, _ in additions}
        if replace_runs:
            for path in directory.glob("fft_????-??-??.zip"):
                with ZipFile(path) as archive:
                    doc = read_index(archive)
                if any(record["run"] in runs for record in doc["entries"].values()):
                    days.add(doc["date"])
        published = []
        for day in sorted(days):
            path = directory / ("fft_" + day + ".zip")
            entries = {}
            references = {}
            if path.exists():
                with ZipFile(path) as archive:
                    doc = read_index(archive)
                for name, record in doc["entries"].items():
                    if not replace_runs or record["run"] not in runs:
                        entries[name] = record
                        references[name] = (path, name)
            for (entry_day, name), (record, reference) in additions.items():
                if entry_day != day:
                    continue
                if name in entries and entries[name]["sha256"] != record["sha256"]:
                    raise ValueError("Changed FFT requires --replace-runs: " + name)
                entries[name], references[name] = record, reference
            fd, temporary_name = tempfile.mkstemp(prefix=path.name + ".", dir=directory)
            os.close(fd)
            temporary = Path(temporary_name)
            try:
                with ExitStack() as stack, ZipFile(temporary, "w", compression=ZIP_STORED, allowZip64=True) as output:
                    opened = {}
                    for name in sorted(entries):
                        source, member = references[name]
                        if member:
                            if source not in opened:
                                opened[source] = stack.enter_context(ZipFile(source))
                            data = opened[source].read(member)
                        else:
                            data = source.read_bytes()
                        if hashlib.sha256(data).hexdigest() != entries[name]["sha256"]:
                            raise ValueError("Source changed during consolidation: " + name)
                        output.writestr(name, data)
                    output.writestr(INDEX, json.dumps({"format": FORMAT, "date": day,
                        "timezone": "UTC", "entries": entries}, sort_keys=True))
                verify(temporary)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            if remote:
                publish(path, remote)
            published.append(path)
        return published


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--remote", help="rclone destination, e.g. flash:analysis/autoreco/Run2/fft_by_1sec")
    parser.add_argument("--replace-runs", action="store_true")
    args = parser.parse_args()
    sources = []
    for path in args.inputs:
        sources.extend(sorted(path.glob("*.npz")) if path.is_dir() else [path])
    for path in consolidate(sources, args.directory, args.remote, args.replace_runs):
        print(path)


if __name__ == "__main__":
    main()
