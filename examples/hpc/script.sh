#!/bin/bash
set -Eeuo pipefail
set -x

echo "======================================"
echo "script.sh started at: $(date)"
echo "Host: $(hostname)"
echo "PWD: $(pwd)"
echo "Arguments: $@"
echo "======================================"

# ------------------------------------------------------
# Check arguments
# Usage:
#   script.sh <remote_dir> <run_number> <workdir> <max_fft_events>
#
# Example:
#   script.sh flash/data/LNF 388 /tmp 99999999
# ------------------------------------------------------

if [[ $# -ne 4 ]]; then
    echo "ERROR: wrong number of arguments."
    echo "Usage: $0 <remote_dir> <run_number> <workdir> <max_fft_events>"
    exit 10
fi

REMOTE_DIR="$1"
RUN_NUMBER="$2"
WORKDIR="$3"
MAX_FFT_EVENTS="$4"

mkdir -p "$WORKDIR"

fname=$(printf 'run%05d.mid.gz' "$RUN_NUMBER")
INPUT_FILE="${WORKDIR}/${fname}"

echo "REMOTE_DIR      = $REMOTE_DIR"
echo "RUN_NUMBER      = $RUN_NUMBER"
echo "WORKDIR         = $WORKDIR"
echo "MAX_FFT_EVENTS  = $MAX_FFT_EVENTS"
echo "INPUT_FILE      = $INPUT_FILE"

# ------------------------------------------------------
# Load environment
# ------------------------------------------------------

# In alcuni cluster 'module' è già disponibile.
# In altri serve inizializzarlo esplicitamente.
if ! command -v module >/dev/null 2>&1; then
    if [[ -f /etc/profile.d/modules.sh ]]; then
        source /etc/profile.d/modules.sh
    fi
fi

module use /cvmfs/mazzitel-personalrepo.infn.it/modules/modulefiles/x86_64-el9
module load gfal/1.9.0
module load oidc-agent/5.3.6

MIDAS_PATH="/cvmfs/mazzitel-personalrepo.infn.it/package/midas/python"
FLLIB_PATH="/cvmfs/mazzitel-personalrepo.infn.it/FLASH/lib/fllib"
PACKAGE_PATH="/cvmfs/mazzitel-personalrepo.infn.it/package/python3.9/site-packages"

export PYTHONPATH="${PACKAGE_PATH}:${MIDAS_PATH}:${FLLIB_PATH}:${PYTHONPATH:-}"

export X509_CERT_DIR=/cvmfs/grid.cern.ch/etc/grid-security/certificates
export SSL_CERT_DIR="$X509_CERT_DIR"

# Cache locali, utili per matplotlib/config in batch mode
# export MPLCONFIGDIR="${WORKDIR}/matplotlib-cache"
# export XDG_CACHE_HOME="${WORKDIR}/xdg-cache"
# export XDG_CONFIG_HOME="${WORKDIR}/xdg-config"

# mkdir -p "$MPLCONFIGDIR" "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME"

# echo "PYTHONPATH       = $PYTHONPATH"
# echo "X509_CERT_DIR    = $X509_CERT_DIR"
# echo "MPLCONFIGDIR     = $MPLCONFIGDIR"

# ------------------------------------------------------
# GPU diagnostics
# ------------------------------------------------------

echo "--------------------------------------"
echo "GPU diagnostics"
echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-unset}"

if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi
else
    echo "WARNING: nvidia-smi not found"
fi

echo "--------------------------------------"

# ------------------------------------------------------
# Token
# ------------------------------------------------------

echo "Getting OIDC token..."

if ! export BEARER_TOKEN="$(oidc-token flash)"; then
    echo "ERROR: failed to obtain OIDC token with: oidc-token flash"
    exit 20
fi

if [[ -z "${BEARER_TOKEN:-}" ]]; then
    echo "ERROR: BEARER_TOKEN is empty"
    exit 21
fi

echo "OIDC token acquired."

# ------------------------------------------------------
# Input file
# ------------------------------------------------------

echo "--------------------------------------"
echo "Checking input file"
echo "Expected file: $INPUT_FILE"

if [[ -f "$INPUT_FILE" ]]; then
    echo "Input file already exists:"
    ls -lh "$INPUT_FILE"
else
    echo "Input file not found locally."
    echo "Copying from CNAF archive..."

    SRC_URL="davs://xfer-archive.cr.cnaf.infn.it:8443/${REMOTE_DIR}/${fname}"

    echo "Source:      $SRC_URL"
    echo "Destination: $WORKDIR/"

    gfal-copy "$SRC_URL" "$WORKDIR/"

    echo "Copy completed at: $(date)"
fi

if [[ ! -f "$INPUT_FILE" ]]; then
    echo "ERROR: input file still missing after copy attempt: $INPUT_FILE"
    echo "Contents of WORKDIR:"
    ls -lah "$WORKDIR"
    exit 30
fi

echo "Input file found:"
ls -lh "$INPUT_FILE"

echo "--------------------------------------"
echo "Python diagnostics"

which python3.9
python3.9 -V

echo "--------------------------------------"
echo "Starting analysis at: $(date)"

python3.9 /home/mazzitel/analysis/examples/analyze_midas_iq_fft_4ms-gpu.py \
    --path "$WORKDIR/" \
    --run "$RUN_NUMBER" \
    --out-dir "$WORKDIR/" \
    --max-fft-events "$MAX_FFT_EVENTS"

rc=$?

echo "--------------------------------------"
echo "Python exit code: $rc"
echo "Analysis finished at: $(date)"

echo "Output files in WORKDIR:"
ls -lsrth "$WORKDIR"

echo "======================================"
echo "script.sh finished at: $(date)"
echo "======================================"

exit "$rc"
