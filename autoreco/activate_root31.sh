#!/usr/bin/env bash
# Manual release only. No worker submission and no cron changes.
set -euo pipefail
receipt_dir=${1:?Supply the directory containing the verified ROOT test receipts}
bundle=${2:?Supply the validated uproot-py39.tgz archive}
repo=/home/mazzitel/HFGW/analysis
runtime=/home/mazzitel/HFGW/analysis-runtime/autoreco/Run3
release=$(git -C "$repo" rev-parse --verify refs/heads/autoreco-run3-root31-release)
sha=27e6410933869f9bc1faf90be7fcd6dfc55b99671d5c9629bca0349474939323

/usr/bin/python3 - "$receipt_dir" <<'PY'
import json
import sys
from pathlib import Path

base = Path(sys.argv[1])
r = json.loads((base / "publication.json").read_text())
s = json.loads((base / f'run{r["run"]:05d}_job_status.json').read_text())
v = r["validation"]
assert r["validated"] is True and r["root_schema"] == "3.1"
assert r["size"] == r["remote_size"] and r["local_adler32"] == r["remote_adler32"]
assert s["exit_code"] == 0 and s["status"] == "success" and s["run"] == r["run"]
assert v["hdf5_reference_datasets_equal"] >= 37 and v["roundtrip_equal"] >= 37
assert v["bor_bytes"] and v["eor_bytes"] and v["banks"]
assert all(v["thermometers"][name] > 0 for name in ("Temp_AVS", "Temp_FP", "Temp_Mercury"))
PY
[[ $(sha256sum "$bundle" | cut -d' ' -f1) == "$sha" ]]
deps="$runtime/root31/uproot-py39.tgz"

flock -x "$runtime/production/.autoreco.lock" bash -s -- "$repo" "$release" "$bundle" "$deps" "$sha" <<'BASH'
set -euo pipefail
git -C "$1" merge --ff-only "$2"
if [[ ! -f "$4" ]] || ! cmp -s "$3" "$4"; then
    install -D -m 0644 "$3" "$4"
fi
/usr/bin/python3 - "$1/config/autoreco_run3.json" "$4" "$5" <<'PY'
import json
import os
import sys
import tempfile
from pathlib import Path

path = Path(sys.argv[1])
settings = json.loads(path.read_text())
settings.update(output_format="root", root_dependencies=sys.argv[2],
                root_dependencies_sha256=sys.argv[3], migration_auto=True)
settings.setdefault("migration_max_active", 40)
fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".root31-config-")
try:
    with os.fdopen(fd, "w") as stream:
        json.dump(settings, stream, indent=2)
        stream.write("\n")
    os.chmod(temporary, path.stat().st_mode & 0o777)
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
BASH
