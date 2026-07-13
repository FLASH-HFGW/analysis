#!/bin/bash
#SBATCH --job-name=test_gpu
#SBATCH --partition=GPU
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=20G
#SBATCH --time=01:00:00
#SBATCH --output=/home/mazzitel/analysis/examples/hpc/JOB.out
#SBATCH --error=/home/mazzitel/analysis/examples/hpc/JOB.err
#SBATCH --mail-type=ALL
#SBATCH --mail-user=giovanni.mazzitelli@lnf.infn.it

set -euxo pipefail

echo "Host:"
hostname

echo "OS:"
cat /etc/os-release

echo "Node list:"
echo "$SLURM_NODELIST"

echo "GPU:"
nvidia-smi || true

ls -lah /cvmfs/mazzitel-personalrepo.infn.it/modules/modulefiles/x86_64-el9
echo "Loading GFAL module..."
module use /cvmfs/mazzitel-personalrepo.infn.it/modules/modulefiles/x86_64-el9
module load gfal/1.9.0

echo "Loaded modules:"
module list

echo "PATH:"
echo "$PATH"

echo "LD_LIBRARY_PATH:"
echo "${LD_LIBRARY_PATH:-}"

echo "Checking GFAL:"
which gfal-copy
which gfal-ls
which python || true
gfal-copy --version
gfal-ls --help | head

echo "Running payload..."
srun --export=ALL -l /home/mazzitel/analysis/examples/htc/script.sh
