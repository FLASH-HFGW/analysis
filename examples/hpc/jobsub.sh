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
set -euo pipefail
REPO_ROOT="${HFGW_REPO_ROOT:-${SLURM_SUBMIT_DIR:-$PWD}}"
while [[ ! -f "$REPO_ROOT/examples/hpc/job.sh" ]]; do
    [[ "$REPO_ROOT" != / && "$REPO_ROOT" != . ]] || { echo 'Set HFGW_REPO_ROOT' >&2; exit 10; }
    REPO_ROOT=$(dirname -- "$REPO_ROOT")
done
export HFGW_REPO_ROOT="$REPO_ROOT"
exec bash "$REPO_ROOT/examples/hpc/job.sh"
