#!/bin/bash
# One input run; only the small result bundle is returned through HTCondor.
set -Eeuo pipefail
[[ $# -eq 2 && $2 =~ ^[0-9]+$ ]] || { echo 'Usage: worker INPUT_PATH RUN' >&2; exit 2; }
INPUT_PATH=$1
RUN=$((10#$2))
RUN_NAME=$(printf 'run%05d' "$RUN")
JOB_ROOT=$PWD
mkdir -p "$JOB_ROOT/results"
WORKDIR=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-$PWD}/thermometers.XXXXXX")
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH="/cvmfs/mazzitel-personalrepo.infn.it/package/midas/python:/cvmfs/mazzitel-personalrepo.infn.it/package/python3.9/site-packages:${PYTHONPATH:-}"
export X509_CERT_DIR=/cvmfs/grid.cern.ch/etc/grid-security/certificates
export SSL_CERT_DIR="$X509_CERT_DIR"
REMOTE="davs://xfer-archive.cr.cnaf.infn.it:8443/${INPUT_PATH}/${RUN_NAME}.mid.gz"
finish() {
    rc=$?
    trap - EXIT
    python3 "$JOB_ROOT/thermometers_batch.py" pack --run "$RUN" \
        --input-url "$REMOTE" --exit-code "$rc" \
        --output "$WORKDIR/${RUN_NAME}.csv" \
        --bundle "$JOB_ROOT/results/${RUN_NAME}_thermometers.zip" || rc=1
    rm -rf -- "$WORKDIR"
    exit "$rc"
}
trap finish EXIT
if ! command -v gfal-copy >/dev/null 2>&1; then
    if ! command -v module >/dev/null 2>&1 && [[ -f /etc/profile.d/modules.sh ]]; then
        source /etc/profile.d/modules.sh
    fi
    module use /cvmfs/mazzitel-personalrepo.infn.it/modules/modulefiles/x86_64-el9
    module load gfal/1.9.0
fi
export BEARER_TOKEN
BEARER_TOKEN=$(jq -er '.access_token | select(type == "string" and length > 0)' "${_CONDOR_CREDS}/t1.use")
echo "[download start] $RUN_NAME $(date -u +%FT%TZ)"
gfal-copy "$REMOTE" "$WORKDIR/${RUN_NAME}.mid.gz"
echo "[extraction start] $RUN_NAME $(date -u +%FT%TZ)"
python3 "$JOB_ROOT/extract_thermometers.py" "$WORKDIR/${RUN_NAME}.mid.gz" \
    --output "$WORKDIR/${RUN_NAME}.csv"
echo "[extraction complete] $RUN_NAME $(date -u +%FT%TZ)"
