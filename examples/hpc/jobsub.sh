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
set -x

echo "Job started on:"
date

echo "Job ID: $SLURM_JOB_ID"
echo "Submit dir: $SLURM_SUBMIT_DIR"
echo "Running on node:"
hostname

echo "SLURM_NODELIST: $SLURM_NODELIST"
echo "CUDA_VISIBLE_DEVICES: $CUDA_VISIBLE_DEVICES"

echo "GPU status:"
nvidia-smi

echo "Starting application..."

srun /home/mazzitel/analysis/examples/hpc/script.sh flash/data/LNF 388 /tmp 99999999
rc=$?

echo "srun exit code: $rc"

echo "Job finished on:"
date

exit "$rc"
