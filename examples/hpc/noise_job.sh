#!/bin/bash
# The tested LNF association is cygno/GPU; IQ calculations themselves use CPU.
#SBATCH --job-name=noise_iq_v1
#SBATCH --partition=GPU
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --mem=4G
#SBATCH --time=03:00:00

set -Eeuo pipefail
set +x
: "${SLURM_JOB_ID:?Run through submit_one_run.sh --analysis noise}"
: "${HFGW_REPO_ROOT:?Repository path required}"
: "${HFGW_RUN:?Run required}"
: "${HFGW_NOISE_REFERENCE:?Common reference required}"
: "${BEARER_TOKEN:?Token must be exported from the login node}"
source "$HFGW_REPO_ROOT/examples/hpc/environment.sh"
[[ $HFGW_RUN =~ ^[0-9]+$ ]] || exit 2
RUN=$((10#$HFGW_RUN))
NAME=$(printf 'run%05d' "$RUN")
PYTHON="${HFGW_PYTHON:-python3.9}"
SOURCE_DIR="${HFGW_NOISE_SOURCE_DIR:-$HFGW_REPO_ROOT/examples}"
OUT_ROOT="${HFGW_NOISE_OUTPUT_ROOT:-$HOME/HFGW/analysis-work/Run2/reports/noise_temperature_pilot_v1_20261108/jobs}"
OUTDIR="$OUT_ROOT/JOB_${SLURM_JOB_ID}"
SCRATCH_ROOT="${HFGW_SCRATCH_ROOT:-${SLURM_TMPDIR:-/tmp/$USER}}"
mkdir -p "$SCRATCH_ROOT" "$OUTDIR"
WORKDIR=$(mktemp -d "$SCRATCH_ROOT/noise-${SLURM_JOB_ID}.XXXXXX")
finish() {
    rc=$?
    trap - EXIT
    set +e
    copy_rc=0
    for file in "$WORKDIR"/*.h5 "$WORKDIR"/analysis.log; do
        [[ -f "$file" ]] || continue
        cp -p -- "$file" "$OUTDIR/" || copy_rc=1
    done
    if [[ $rc -eq 0 && $copy_rc -ne 0 ]]; then rc=$copy_rc; fi
    printf '{"run":%d,"job_id":"%s","exit_code":%d,"iq_sign":-1}\n' \
        "$RUN" "$SLURM_JOB_ID" "$rc" > "$OUTDIR/job_status.json.tmp"
    mv -- "$OUTDIR/job_status.json.tmp" "$OUTDIR/job_status.json"
    # Remove this job's unique scratch only after analysis and persistent copying succeed.
    if [[ $rc -eq 0 ]]; then rm -rf -- "$WORKDIR"; fi
    echo "Noise job finished: exit=$rc; results=$OUTDIR; scratch=$WORKDIR"
    exit "$rc"
}
trap finish EXIT
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONUNBUFFERED=1 MPLCONFIGDIR="$WORKDIR/matplotlib"
export XDG_CACHE_HOME="$WORKDIR/xdg-cache" XDG_CONFIG_HOME="$WORKDIR/xdg-config"
for module in analyze_midas_iq_noise.py iq_noise_statistics.py iq_noise_io.py analyze_iq_filtered_bands.py; do
    cp -- "$SOURCE_DIR/$module" "$WORKDIR/"
done
cp -- "$HFGW_NOISE_REFERENCE" "$WORKDIR/noise_reference.json"
# Check the numerical dependencies before transferring a full MIDAS.
"$PYTHON" -c 'import numpy, scipy, h5py, matplotlib, midas.file_reader'
URL="davs://xfer-archive.cr.cnaf.infn.it:8443/${HFGW_INPUT_PATH:-flash/data/LNF}/${NAME}.mid.gz"
echo "Download $NAME $(date -u +%FT%TZ)"
gfal-copy "$URL" "$WORKDIR/${NAME}.mid.gz.part"
[[ -s "$WORKDIR/${NAME}.mid.gz.part" ]] || exit 30
mv -- "$WORKDIR/${NAME}.mid.gz.part" "$WORKDIR/${NAME}.mid.gz"
echo "Analyze I-iQ $NAME $(date -u +%FT%TZ)"
ARGS=("$WORKDIR/${NAME}.mid.gz" --out-dir "$WORKDIR" \
    --global-reference "$WORKDIR/noise_reference.json" --iq-sign -1 \
    --mode-workers 1 --h5-only --filtered-bands --product-version v1)
if [[ ${HFGW_MAX_EVENTS:-99999999} != 99999999 ]]; then
    ARGS+=(--max-events "$HFGW_MAX_EVENTS")
fi
srun "$PYTHON" -u "$WORKDIR/analyze_midas_iq_noise.py" "${ARGS[@]}" > "$WORKDIR/analysis.log" 2>&1
