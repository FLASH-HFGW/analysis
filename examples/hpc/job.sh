#!/bin/bash

#SBATCH --job-name=test_gpu
#SBATCH --partition=GPU
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=20G
#SBATCH --time=01:00:00
#SBATCH --output=/home/mazzitel/slurm_logs/JOB_%j.out
#SBATCH --error=/home/mazzitel/slurm_logs/JOB_%j.err
#SBATCH --mail-type=ALL
#SBATCH --mail-user=giovanni.mazzitelli@lnf.infn.it

set -Eeuo pipefail

echo "======================================"
echo "Job started at: $(date)"
echo "Job ID: ${SLURM_JOB_ID}"
echo "Submit dir: ${SLURM_SUBMIT_DIR}"
echo "Host: $(hostname)"
echo "SLURM_NODELIST: ${SLURM_NODELIST}"
echo "CUDA_VISIBLE_DEVICES: ${CUDA_VISIBLE_DEVICES:-unset}"
echo "======================================"

# ------------------------------------------------------
# User parameters
# ------------------------------------------------------

REMOTE_DIR="flash/data/LNF"
RUN_NUMBER="388"
MAX_FFT_EVENTS="99999999"

# ANALYSIS_SCRIPT="/home/mazzitel/analysis/examples/analyze_midas_iq_fft_4ms-gpu.py"
ANALYSIS_SCRIPT="/home/mazzitel/analysis/examples/analyze_midas_iq_fft_4ms_gpu_profile.py"

# Usa una workdir dedicata sul /tmp locale del nodo.
# Meglio di /tmp diretto, perché evita collisioni tra job.
WORKDIR="/tmp/${USER}/JOB_${SLURM_JOB_ID}"

# Directory persistente su filesystem condiviso per eventuali output finali/log utili.
OUTDIR="${SLURM_SUBMIT_DIR}/results/JOB_${SLURM_JOB_ID}"

mkdir -p "$WORKDIR"
mkdir -p "$OUTDIR"
mkdir -p /home/mazzitel/slurm_logs

fname=$(printf 'run%05d.mid.gz' "$RUN_NUMBER")
INPUT_FILE="${WORKDIR}/${fname}"

echo "REMOTE_DIR      = $REMOTE_DIR"
echo "RUN_NUMBER      = $RUN_NUMBER"
echo "MAX_FFT_EVENTS  = $MAX_FFT_EVENTS"
echo "WORKDIR         = $WORKDIR"
echo "OUTDIR          = $OUTDIR"
echo "INPUT_FILE      = $INPUT_FILE"
echo "ANALYSIS_SCRIPT = $ANALYSIS_SCRIPT"

# ------------------------------------------------------
# Environment
# ------------------------------------------------------

echo "--------------------------------------"
echo "Loading environment"

if ! command -v module >/dev/null 2>&1; then
    if [[ -f /etc/profile.d/modules.sh ]]; then
        source /etc/profile.d/modules.sh
    fi
fi

module use /cvmfs/mazzitel-personalrepo.infn.it/modules/modulefiles/x86_64-el9
module load gfal/1.9.0
module load rclone/1.74.2 

MIDAS_PATH="/cvmfs/mazzitel-personalrepo.infn.it/package/midas/python"
FLLIB_PATH="/cvmfs/mazzitel-personalrepo.infn.it/FLASH/lib/fllib"
PACKAGE_PATH="/cvmfs/mazzitel-personalrepo.infn.it/package/python3.9/site-packages"

export PYTHONPATH="${PACKAGE_PATH}:${MIDAS_PATH}:${FLLIB_PATH}:${PYTHONPATH:-}"

export X509_CERT_DIR=/cvmfs/grid.cern.ch/etc/grid-security/certificates
export SSL_CERT_DIR="$X509_CERT_DIR"

export MPLCONFIGDIR="${WORKDIR}/matplotlib-cache"
export XDG_CACHE_HOME="${WORKDIR}/xdg-cache"
export XDG_CONFIG_HOME="${WORKDIR}/xdg-config"

mkdir -p "$MPLCONFIGDIR" "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME"

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"
export NUMEXPR_NUM_THREADS="$OMP_NUM_THREADS"

echo "PYTHONPATH             = $PYTHONPATH"
echo "OMP_NUM_THREADS        = $OMP_NUM_THREADS"
echo "MPLCONFIGDIR           = $MPLCONFIGDIR"

echo "--------------------------------------"
echo "Checking commands"

which python3.9
python3.9 -V

if ! command -v gfal-copy >/dev/null 2>&1; then
    echo "ERROR: gfal-copy not found after module load"
    module list || true
    exit 11
fi

which gfal-copy

# ------------------------------------------------------
# GPU diagnostics
# ------------------------------------------------------

echo "--------------------------------------"
echo "GPU diagnostics"

if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi
else
    echo "WARNING: nvidia-smi not found"
fi

# ------------------------------------------------------
# Bearer token
# ------------------------------------------------------

echo "--------------------------------------"
echo "Checking BEARER_TOKEN"

# Non stampare mai il token nei log.
if [[ -z "${BEARER_TOKEN:-}" ]]; then
    echo "ERROR: BEARER_TOKEN is not set."
    echo "Submit with:"
    echo '  export BEARER_TOKEN="$(oidc-token flash --time=3600)"'
    echo '  sbatch --export=ALL,BEARER_TOKEN jobsub.sh'
    exit 20
fi

echo "BEARER_TOKEN is set, length: ${#BEARER_TOKEN}"

# ------------------------------------------------------
# Input copy
# ------------------------------------------------------

echo "--------------------------------------"
echo "Input file preparation"

SRC_URL="davs://xfer-archive.cr.cnaf.infn.it:8443/${REMOTE_DIR}/${fname}"

echo "Source:      $SRC_URL"
echo "Destination: $INPUT_FILE"


if [[ -f "$INPUT_FILE" ]]; then
    echo "Input file already exists:"
    ls -lh "$INPUT_FILE"
else
    echo "Copying input file at: $(date)"

    set +e
    # gfal-copy "$SRC_URL" "$INPUT_FILE"
    # rclone --config=/cvmfs/mazzitel-personalrepo.infn.it/FLASH/config/rclone.conf copy flash:${REMOTE_DIR}/${fname} "$INPUT_FILE"
    cp /home/mazzitel/testdata/run00388.mid.gz "$INPUT_FILE"
    copy_rc=$?
    set -e

    echo "gfal-copy exit code: $copy_rc"

    if [[ "$copy_rc" -ne 0 ]]; then
        echo "ERROR: gfal-copy failed"
        echo "WORKDIR content:"
        ls -lah "$WORKDIR" || true
        exit "$copy_rc"
    fi
fi

if [[ ! -f "$INPUT_FILE" ]]; then
    echo "ERROR: input file missing after copy: $INPUT_FILE"
    ls -lah "$WORKDIR" || true
    exit 30
fi

echo "Input file ready:"
ls -lh "$INPUT_FILE"

# ------------------------------------------------------
# Run analysis
# ------------------------------------------------------

echo "--------------------------------------"
echo "Starting Python analysis at: $(date)"

if [[ ! -f "$ANALYSIS_SCRIPT" ]]; then
    echo "ERROR: analysis script not found: $ANALYSIS_SCRIPT"
    exit 40
fi

GPU_LOG="${OUTDIR}/gpu_usage_${SLURM_JOB_ID}.csv"

echo "Starting GPU monitor: $GPU_LOG"

nvidia-smi \
    --query-gpu=timestamp,index,name,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw \
    --format=csv \
    -l 1 \
    > "$GPU_LOG" &

GPU_MON_PID=$!

set +e

srun python3.9 "$ANALYSIS_SCRIPT" \
    --path "$WORKDIR/" \
    --run "$RUN_NUMBER" \
    --out-dir "$WORKDIR/" \
    --max-fft-events "$MAX_FFT_EVENTS" \
    --fft-backend gpu \
    --gpu-device 0 \
    --profile \
    --profile-every 100 \
    --gc-every 0 \
    --free-gpu-pool-every 0

# srun python3.9 "$ANALYSIS_SCRIPT" \
#     --path "$WORKDIR/" \
#     --run "$RUN_NUMBER" \
#     --out-dir "$WORKDIR/" \
#     --max-fft-events "$MAX_FFT_EVENTS" \
#     --fft-backend gpu \
#     --gpu-device 0

python_rc=$?

set -e

kill "$GPU_MON_PID" 2>/dev/null || true
wait "$GPU_MON_PID" 2>/dev/null || true

echo "GPU monitor saved in: $GPU_LOG"

echo "Python/srun exit code: $python_rc"
echo "Analysis finished at: $(date)"

# ------------------------------------------------------
# Collect output
# ------------------------------------------------------

echo "--------------------------------------"
echo "WORKDIR content after analysis:"
ls -lsrth "$WORKDIR" || true

echo "Copying selected outputs to OUTDIR: $OUTDIR"

# Copia tutto tranne il file MIDAS di input, per evitare di salvare file enormi inutilmente.
find "$WORKDIR" -maxdepth 1 -type f ! -name "$fname" -exec cp -v {} "$OUTDIR/" \; || true

echo "OUTDIR content:"
ls -lsrth "$OUTDIR" || true

echo "--------------------------------------"
echo "Job finished at: $(date)"
echo "Final exit code: $python_rc"
echo "======================================"

exit "$python_rc"
