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
PYTHON=${NOISE_PYTHON:-python3}
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
export PYTHONPATH="/cvmfs/mazzitel-personalrepo.infn.it/package/python3.9/site-packages:/cvmfs/mazzitel-personalrepo.infn.it/package/midas/python:/cvmfs/mazzitel-personalrepo.infn.it/FLASH/lib/fllib:${PYTHONPATH:-}"
export X509_CERT_DIR=/cvmfs/grid.cern.ch/etc/grid-security/certificates
export SSL_CERT_DIR="$X509_CERT_DIR"
if ! command -v gfal-copy >/dev/null 2>&1; then
    if ! command -v module >/dev/null 2>&1 && [[ -f /etc/profile.d/modules.sh ]]; then
        source /etc/profile.d/modules.sh
    fi
    module use /cvmfs/mazzitel-personalrepo.infn.it/modules/modulefiles/x86_64-el9
    module load gfal/1.9.0
fi
command -v "$PYTHON"
[[ -f "$REFERENCE" ]]
[[ -n ${_CONDOR_CREDS:-} ]]
export BEARER_TOKEN
BEARER_TOKEN=$(jq -er '.access_token | select(type == "string" and length > 0)' "${_CONDOR_CREDS}/t1.use")
echo "Starting $RUN_NAME on $(hostname) at $(date -u +%FT%TZ)"
echo "[timing] download start $(date -u +%FT%TZ)"
gfal-copy "davs://xfer-archive.cr.cnaf.infn.it:8443/${INPUT_PATH}/${RUN_NAME}.mid.gz" "$WORKDIR/${RUN_NAME}.mid.gz"
echo "[timing] download end / analysis start $(date -u +%FT%TZ)"
"$PYTHON" "$ANALYSIS_SCRIPT" "$WORKDIR/${RUN_NAME}.mid.gz" \
    --out-dir "$JOB_ROOT" --global-reference "$REFERENCE" --iq-sign "$IQ_SIGN" \
    --mode-workers "$MODE_WORKERS" --phase-lags 1 10 100
echo "[timing] analysis end / upload start $(date -u +%FT%TZ)"
# Stessa pubblicazione dell'autoreco FFT, in una cartella dedicata al rumore.
BEARER_TOKEN=$(jq -er '.access_token | select(type == "string" and length > 0)' "${_CONDOR_CREDS}/t1.use")
REMOTE="davs://xfer-archive.cr.cnaf.infn.it:8443/${OUTPUT_PATH}"
gfal-mkdir -p "$REMOTE"
for suffix in _noise.npz _noise.png _noise_iq.png _noise.json; do
    gfal-copy -f "$JOB_ROOT/${RUN_NAME}${suffix}" "$REMOTE/${RUN_NAME}${suffix}"
done
echo "[timing] upload end $(date -u +%FT%TZ)"
