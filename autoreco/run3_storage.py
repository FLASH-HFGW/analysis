"""Run3 worker GFAL operations and shared endpoint constants."""
import json
import os
from pathlib import Path
import tempfile
import re
import subprocess
import uuid
import zlib

ENDPOINT = "davs://xfer-archive.cr.cnaf.infn.it:8443"
RAW = "flash/data/LNF"
PRODUCTION = ENDPOINT + "/flash/analysis/autoreco/Run3"
PILOT = ENDPOINT + "/flash/analysis/autoreco/Run3-pilot"


def gfal(tool, *args, missing=False):
    credentials = Path(os.environ["_CONDOR_CREDS"]) / "t1.use"
    token = json.loads(credentials.read_text())["access_token"]
    if not isinstance(token, str) or not token:
        raise ValueError("HTCondor t1 access token is unavailable")
    result = subprocess.run(["gfal-" + tool, *map(str, args)], capture_output=True, text=True,
                            env=dict(os.environ, BEARER_TOKEN=token))
    if result.returncode:
        if missing and re.search(r"(?i)\b404\b|no such file or directory", result.stderr):
            return None
        raise RuntimeError(f"gfal-{tool}: {result.stderr.strip()}")
    return result.stdout


def size(url, missing=False):
    info = gfal("stat", url, missing=missing)
    return None if info is None else int(re.search(r"(?m)^\s*Size:\s*(\d+)", info)[1])


def download_raw(url, path):
    expected = size(url)
    if expected <= 0:
        raise ValueError(f"raw is empty: {url}")
    gfal("copy", "-K", "ADLER32", url, path.resolve().as_uri())
    if path.stat().st_size != expected or size(url) != expected:
        raise ValueError(f"raw size changed during download: {url}")


def verify(url, identity):
    remote_size = size(url)
    if remote_size != identity["size"]:
        raise ValueError(f"remote size mismatch: {url}")
    checksum = gfal("sum", url, "ADLER32").split()[-1].lower().zfill(8)
    if checksum != identity["local_adler32"]:
        raise ValueError(f"remote checksum mismatch: {url}")
    return dict(identity, remote_size=remote_size, remote_adler32=checksum)


def validate_product(path, run):
    import h5py

    with h5py.File(path, "r") as data:
        quality = data["quality"].attrs
        spectra = data["spectra"]
        short = data["short_psd"]
        windows = len(data["timing/windows"])
        if (data.attrs["schema_version"] != "1.3"
                or data["metadata"].attrs["run_number"] != run
                or not quality["saw_eor"] or windows < 1
                or quality["valid_windows"] != windows
                or spectra.attrs["profile"] != "compact"
                or spectra.attrs["nominal_window_bin_width_hz"] != 100
                or short.attrs["segment_samples"] != 16384
                or short.attrs["segments_per_mode"] < 1):
            raise ValueError("not a complete Run3 compact product")
        for mode in data["statistics"]:
            psd = spectra[mode]
            if (set(psd) != {"mean_psd", "window_psd"}
                    or len(psd["window_psd"]) != windows
                    or len(psd["mean_psd"]) != spectra.attrs["frequency_count"]
                    or any(len(short[kind][mode]) != 16384 for kind in ("rectangular", "hann"))):
                raise ValueError(f"invalid Run3 spectral products for {mode}")



def local_identity(path):
    checksum = 1
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024*1024), b""):
            checksum = zlib.adler32(block, checksum)
    return dict(size=path.stat().st_size, local_adler32=f"{checksum:08x}")


def verify_existing(path, destination, identity, run):
    try:
        return verify(destination, identity)
    except ValueError:
        if run is None:
            raise
    # A repeat reconstruction has different runtime metadata. Reuse only if
    # the existing product has the same scientific inputs and dataset bytes.
    import h5py
    import numpy as np

    with tempfile.TemporaryDirectory(dir=path.parent) as scratch:
        existing = Path(scratch) / "existing.h5"
        gfal("copy", "-K", "ADLER32", destination, existing.as_uri())
        validate_product(existing, run)
        with h5py.File(path, "r") as candidate, h5py.File(existing, "r") as previous:
            for name in ("pairs_json", "bor_settings_json", "bor_lo_json", "source_size_bytes",
                         "iq_convention", "fs_hz", "midas_layout"):
                if candidate["metadata"].attrs[name] != previous["metadata"].attrs[name]:
                    raise ValueError(f"existing Run3 product differs in {name}")

            def compare(name, item):
                other = previous[name]
                if name not in ("metadata", "quality"):
                    for key, value in item.attrs.items():
                        if key != "processing_s":
                            np.testing.assert_equal(value, other.attrs[key])
                if isinstance(item, h5py.Dataset):
                    if item.shape != other.shape or item.dtype != other.dtype:
                        raise ValueError(f"existing Run3 product differs at {name}")
                    for start in range(0, len(item), 16):
                        selection = slice(start, start+16)
                        if item[selection].tobytes() != other[selection].tobytes():
                            raise ValueError(f"existing Run3 product differs at {name}")

            candidate.visititems(compare)
        return verify(destination, local_identity(existing))


def publish(path, destination, *, probe=False, run=None):
    """Verify the remote payload before and after atomic promotion."""
    identity = local_identity(path)
    gfal("mkdir", "-p", destination.rsplit("/", 1)[0])
    if not probe and size(destination, missing=True) is not None:
        return verify_existing(path, destination, identity, run)
    staged = destination + ".partial-" + uuid.uuid4().hex
    second = staged + "-probe"
    print(f"GFAL staging: {staged}", flush=True)
    try:
        gfal("copy", "-K", "ADLER32", path.resolve().as_uri(), staged)
        verify(staged, identity)
        if probe:
            gfal("copy", "-K", "ADLER32", path.resolve().as_uri(), second)
            try:
                gfal("rename", staged, second)
            except RuntimeError:
                verify(staged, identity)
                verify(second, identity)
            else:
                raise RuntimeError("endpoint rename overwrites destinations")
        if size(destination, missing=True) is None:
            try:
                gfal("rename", staged, destination)
            except RuntimeError:
                if size(destination, missing=True) is None:
                    raise
        return verify_existing(path, destination, identity, run)
    finally:
        for temporary in (staged, second) if probe else (staged,):
            if size(temporary, missing=True) is not None:
                gfal("rm", temporary)
