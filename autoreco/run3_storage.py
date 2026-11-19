"""GFAL publication and verification shared by the Run3 worker and submit host."""
import re
import subprocess
import uuid
import zlib

ENDPOINT = "davs://xfer-archive.cr.cnaf.infn.it:8443"
RAW = "flash/data/LNF"
PRODUCTION = ENDPOINT + "/flash/analysis/autoreco/Run3"
PILOT = ENDPOINT + "/flash/analysis/autoreco/Run3-pilot"


def gfal(tool, *args, missing=False):
    result = subprocess.run(["gfal-" + tool, *map(str, args)], capture_output=True, text=True)
    if result.returncode:
        if missing and re.search(r"(?i)\b404\b|no such file or directory", result.stderr):
            return None
        raise RuntimeError(f"gfal-{tool}: {result.stderr.strip()}")
    return result.stdout


def size(url, missing=False):
    info = gfal("stat", url, missing=missing)
    return None if info is None else int(re.search(r"(?m)^\s*Size:\s*(\d+)", info)[1])


def verify(url, identity):
    if size(url) != identity["size"]:
        raise ValueError(f"remote size mismatch: {url}")
    checksum = gfal("sum", url, "ADLER32").split()[-1].lower().zfill(8)
    if checksum != identity["adler32"]:
        raise ValueError(f"remote checksum mismatch: {url}")


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



def publish(path, destination, *, probe=False):
    """Verify the remote payload before and after atomic promotion."""
    checksum = 1
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024*1024), b""):
            checksum = zlib.adler32(block, checksum)
    identity = dict(size=path.stat().st_size, adler32=f"{checksum:08x}")
    directory = destination.rsplit("/", 1)[0]
    gfal("mkdir", "-p", directory)
    if size(destination, missing=True) is not None:
        verify(destination, identity)
        return identity
    staged = destination + ".partial-" + uuid.uuid4().hex
    second = staged + "-probe"
    print(f"GFAL staging: {staged}", flush=True)
    try:
        gfal("copy", "-K", "ADLER32", path.resolve().as_uri(), staged)
        verify(staged, identity)
        if probe:
            # Test collision semantics only against private pilot temporaries.
            gfal("copy", "-K", "ADLER32", path.resolve().as_uri(), second)
            try:
                gfal("rename", staged, second)
            except RuntimeError:
                verify(staged, identity)
                verify(second, identity)
            else:
                raise RuntimeError("endpoint rename overwrites destinations")
        if size(destination, missing=True) is None:
            gfal("rename", staged, destination)
        verify(destination, identity)
    finally:
        for temporary in (staged, second) if probe else (staged,):
            if size(temporary, missing=True) is not None:
                gfal("rm", temporary)
    return identity
