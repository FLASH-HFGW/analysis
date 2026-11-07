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
: "${SLURM_JOB_ID:?Run this script through sbatch or an allocated SLURM job}"
REPO_ROOT="${HFGW_REPO_ROOT:-${SLURM_SUBMIT_DIR:-$PWD}}"
while [[ ! -f "$REPO_ROOT/examples/hpc/environment.sh" ]]; do
    [[ "$REPO_ROOT" != / && "$REPO_ROOT" != . ]] || { echo 'Cannot locate repository; set HFGW_REPO_ROOT' >&2; exit 10; }
    REPO_ROOT=$(dirname -- "$REPO_ROOT")
done
source "$REPO_ROOT/examples/hpc/environment.sh"

REMOTE_DIR="${HFGW_INPUT_PATH:-flash/data/LNF}"
RUN_NUMBER="${HFGW_RUN:-388}"
MAX_FFT_EVENTS="${HFGW_MAX_EVENTS:-99999999}"
[[ "$RUN_NUMBER" =~ ^[0-9]+$ ]] || { echo 'HFGW_RUN must be a run number' >&2; exit 2; }
RUN_NUMBER=$((10#$RUN_NUMBER))
ANALYSIS_SCRIPT="${HFGW_ANALYSIS_SCRIPT:-$REPO_ROOT/examples/analyze_midas_iq_fft_4ms_gpu_profile.py}"
[[ -f "$ANALYSIS_SCRIPT" ]] || { echo "Missing analysis script: $ANALYSIS_SCRIPT" >&2; exit 40; }
PYTHON="${HFGW_PYTHON:-python3.9}"
command -v "$PYTHON" >/dev/null
command -v gfal-copy >/dev/null
command -v nvidia-smi >/dev/null
[[ -n ${BEARER_TOKEN:-} ]] || { echo 'Export BEARER_TOKEN from the login node before sbatch' >&2; exit 20; }

SCRATCH_ROOT="${HFGW_SCRATCH_ROOT:-${SLURM_TMPDIR:-/tmp/${USER}}}"
RUNTIME_ROOT="${HFGW_RUNTIME_ROOT:-$HOME/HFGW/analysis-runtime/autoreco/Run2}"
WORKDIR="$SCRATCH_ROOT/JOB_${SLURM_JOB_ID}"
OUTDIR="$RUNTIME_ROOT/benchmarks/slurm/JOB_${SLURM_JOB_ID}"
mkdir -p "$WORKDIR" "$OUTDIR"
fname=$(printf 'run%05d.mid.gz' "$RUN_NUMBER")
INPUT_FILE="$WORKDIR/$fname"
SRC_URL="davs://xfer-archive.cr.cnaf.infn.it:8443/${REMOTE_DIR}/${fname}"
GPU_MON_PID=''

finish() {
    rc=$?
    trap - EXIT
    set +e
    if [[ -n "$GPU_MON_PID" ]]; then
        kill "$GPU_MON_PID" 2>/dev/null
        wait "$GPU_MON_PID" 2>/dev/null
    fi
    copy_rc=0
    while IFS= read -r -d '' result; do
        cp -p -- "$result" "$OUTDIR/" || copy_rc=1
    done < <(find "$WORKDIR" -maxdepth 1 -type f ! -name "$fname" ! -name "$fname.part" -print0)
    if [[ $rc -eq 0 && $copy_rc -ne 0 ]]; then rc=$copy_rc; fi
    printf '{"run":%d,"job_id":"%s","exit_code":%d}\n' "$RUN_NUMBER" "$SLURM_JOB_ID" "$rc" > "$OUTDIR/job_status.json"
    echo "Job finished: exit=$rc; local benchmark results: $OUTDIR"
    exit "$rc"
}
trap finish EXIT

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS" MKL_NUM_THREADS="$OMP_NUM_THREADS" NUMEXPR_NUM_THREADS="$OMP_NUM_THREADS"
export MPLCONFIGDIR="$WORKDIR/matplotlib-cache"
export XDG_CACHE_HOME="$WORKDIR/xdg-cache" XDG_CONFIG_HOME="$WORKDIR/xdg-config"
mkdir -p "$MPLCONFIGDIR" "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME"
echo "Job $SLURM_JOB_ID on $(hostname); repository: $REPO_ROOT"
echo "Input: $SRC_URL; scratch: $WORKDIR"
nvidia-smi
"$PYTHON" -V

if [[ ! -s "$INPUT_FILE" ]]; then
    # Exactly one remote transfer. A failed transfer never becomes a cached input.
    rm -f -- "$INPUT_FILE.part"
    gfal-copy "$SRC_URL" "$INPUT_FILE.part"
    [[ -s "$INPUT_FILE.part" ]] || { echo 'Downloaded input is empty' >&2; exit 30; }
    mv -- "$INPUT_FILE.part" "$INPUT_FILE"
fi
nvidia-smi --query-gpu=timestamp,index,name,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw \
    --format=csv -l 1 > "$WORKDIR/gpu_usage_${SLURM_JOB_ID}.csv" &
GPU_MON_PID=$!
srun "$PYTHON" "$ANALYSIS_SCRIPT" \
    --path "$WORKDIR/" --run "$RUN_NUMBER" --out-dir "$WORKDIR/" \
    --max-fft-events "$MAX_FFT_EVENTS" --fft-backend gpu --gpu-device 0 \
    --profile --profile-every 100 --gc-every 0 --free-gpu-pool-every 0
