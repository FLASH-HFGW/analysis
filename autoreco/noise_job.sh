#!/bin/bash
# Payload della modalità noise di autoreco.py.
set -Eeuo pipefail
# Args iniziali compatibili con il riconoscimento dei job dell'autoreco.
if [[ ( $# -ne 6 && $# -ne 7 ) || ! $2 =~ ^[0-9]+$ ]]; then
    echo "Usage: $0 <input_path> <run> <output_path> <analysis_script> <reference_json> <iq_sign> [mode_workers]" >&2
    exit 2
fi
INPUT_PATH=$1
RUN_NUMBER=$((10#$2))
OUTPUT_PATH=$3
ANALYSIS_SCRIPT=$4
REFERENCE=$5
IQ_SIGN=$6
MODE_WORKERS=${7:-1}
JOB_ROOT=$PWD
PYTHON=${NOISE_PYTHON:-python3.9}
WORKDIR=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-$PWD}/noise-work.XXXXXX")
RUN_NAME=$(printf 'run%05d' "$RUN_NUMBER")
export MPLCONFIGDIR="$WORKDIR/matplotlib"
export XDG_CACHE_HOME="$WORKDIR/xdg-cache"
export XDG_CONFIG_HOME="$WORKDIR/xdg-config"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONUNBUFFERED=1
finish() {
    rc=$?
    trap - EXIT
    printf '{"run":%d,"exit_code":%d,"status":"%s"}\n' "$RUN_NUMBER" "$rc" \
        "$([[ $rc -eq 0 ]] && echo success || echo failed)" > "$JOB_ROOT/${RUN_NAME}_job_status.json"
    rm -rf -- "$WORKDIR"
    exit "$rc"
}
trap finish EXIT
export PYTHONPATH="/cvmfs/sft-flash.infn.it/package/python3.9/site-packages:/cvmfs/sft-flash.infn.it/package/midas/python:/cvmfs/sft-flash.infn.it/FLASH/lib/fllib"
export PYTHONNOUSERSITE=1
export X509_CERT_DIR=/cvmfs/grid.cern.ch/etc/grid-security/certificates
export SSL_CERT_DIR="$X509_CERT_DIR"
if ! command -v gfal-copy >/dev/null 2>&1; then
    if ! command -v module >/dev/null 2>&1 && [[ -f /etc/profile.d/modules.sh ]]; then
        source /etc/profile.d/modules.sh
    fi
    module use /cvmfs/sft-flash.infn.it/modules/modulefiles/x86_64-el9
    module load gfal/1.9.0
fi
command -v "$PYTHON"
[[ -f "$REFERENCE" ]]
[[ -n ${_CONDOR_CREDS:-} ]]
export BEARER_TOKEN
BEARER_TOKEN=$(jq -er '.access_token | select(type == "string" and length > 0)' "${_CONDOR_CREDS}/t1.use")
echo "Starting $RUN_NAME on $(hostname) at $(date -u +%FT%TZ)"
echo "[timing] download start $(date -u +%FT%TZ)"
raw_url="davs://xfer-archive.cr.cnaf.infn.it:8443/${INPUT_PATH}/${RUN_NAME}.mid.gz"
if [[ "$REFERENCE" == iq_v3_job.json ]] && jq -e '.publication != null' "$REFERENCE" >/dev/null; then
    "$PYTHON" - "$raw_url" "$WORKDIR/${RUN_NAME}.mid.gz" <<'PYTHON'
import sys
from pathlib import Path
from run3_storage import download_raw
download_raw(sys.argv[1], Path(sys.argv[2]))
PYTHON
else
    gfal-copy "$raw_url" "$WORKDIR/${RUN_NAME}.mid.gz"
fi
echo "[timing] download end / analysis start $(date -u +%FT%TZ)"
if [[ "$REFERENCE" == iq_v3_job.json && "$OUTPUT_PATH" == pilot ]]; then
    limit=$(jq -r '.max_events // empty' "$REFERENCE")
    product=$(jq -er '.product // "compact"' "$REFERENCE")
    limit_args=()
    if [[ -n "$limit" ]]; then
        limit_args=(--max-events "$limit")
    fi
    bin_hz=$(jq -er '.bin_hz // 100' "$REFERENCE")
    pairs=$(jq -c '.split_pairs' "$REFERENCE")
    publication=$(jq -c '.publication // empty' "$REFERENCE")
    output_file="$JOB_ROOT/${RUN_NAME}_iq_v3.h5"
    if [[ -n "$publication" ]]; then
        output_file="$WORKDIR/${RUN_NAME}_iq_v3.h5"
    fi
    "$PYTHON" "$ANALYSIS_SCRIPT" "$WORKDIR/${RUN_NAME}.mid.gz" \
        "$output_file" --product "$product" --bin-hz "$bin_hz" "${limit_args[@]}" --split-pairs "$pairs" \
        --software-commit "$IQ_SIGN" --workers "$MODE_WORKERS"
    if [[ -n "$publication" ]]; then
        rm -- "$WORKDIR/${RUN_NAME}.mid.gz"
        BEARER_TOKEN=$(jq -er '.access_token | select(type == "string" and length > 0)' "${_CONDOR_CREDS}/t1.use")
        "$PYTHON" - "$output_file" "$publication" "$RUN_NUMBER" <<'PYTHON'
import json, sys
from pathlib import Path
from run3_storage import publish, validate_product
settings = json.loads(sys.argv[2])
path = Path(sys.argv[1])
validate_product(path, int(sys.argv[3]))
identity = publish(path, settings["url"], probe=settings["probe"], run=int(sys.argv[3]))
Path("publication.json").write_text(json.dumps(dict(url=settings["url"], run=int(sys.argv[3]),
                                                attempt=settings["attempt"], validated=True, **identity)))
PYTHON
    fi
    exit 0
fi
"$PYTHON" "$ANALYSIS_SCRIPT" "$WORKDIR/${RUN_NAME}.mid.gz" \
    --out-dir "$JOB_ROOT" --global-reference "$REFERENCE" --iq-sign "$IQ_SIGN" \
    --mode-workers "$MODE_WORKERS" --phase-lags 1 10 100 --h5-only --filtered-bands --product-version v1
echo "[timing] analysis end / upload start $(date -u +%FT%TZ)"
# Stessa pubblicazione dell'autoreco FFT, in una cartella dedicata al rumore.
BEARER_TOKEN=$(jq -er '.access_token | select(type == "string" and length > 0)' "${_CONDOR_CREDS}/t1.use")
REMOTE="davs://xfer-archive.cr.cnaf.infn.it:8443/${OUTPUT_PATH}"
gfal-mkdir -p "$REMOTE"
gfal-copy -K ADLER32 "$JOB_ROOT/${RUN_NAME}_noise.h5" "$REMOTE/${RUN_NAME}_noise_v1.h5"
gfal-copy "$REMOTE/${RUN_NAME}_noise_v1.h5" "$WORKDIR/remote_noise_v1.h5"
"$PYTHON" -c 'import hashlib,sys; from pathlib import Path; assert hashlib.sha256(Path(sys.argv[1]).read_bytes()).digest() == hashlib.sha256(Path(sys.argv[2]).read_bytes()).digest(), "GPFS SHA-256 mismatch"' \
    "$JOB_ROOT/${RUN_NAME}_noise.h5" "$WORKDIR/remote_noise_v1.h5"
echo "[timing] upload end $(date -u +%FT%TZ)"
