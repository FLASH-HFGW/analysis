#!/bin/bash
#SBATCH --job-name=test_cupy
#SBATCH --partition=GPU
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=/home/mazzitel/slurm_logs/CUPY_%j.out
#SBATCH --error=/home/mazzitel/slurm_logs/CUPY_%j.err

set -euo pipefail

REPO_ROOT="${HFGW_REPO_ROOT:-${SLURM_SUBMIT_DIR:-$PWD}}"
while [[ ! -f "$REPO_ROOT/examples/hpc/environment.sh" ]]; do
    [[ "$REPO_ROOT" != / && "$REPO_ROOT" != . ]] || { echo 'Set HFGW_REPO_ROOT' >&2; exit 10; }
    REPO_ROOT=$(dirname -- "$REPO_ROOT")
done
source "$REPO_ROOT/examples/hpc/environment.sh"

echo "Host: $(hostname)"
echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-unset}"
which python3.9
python3.9 -V

python3.9 - <<'PY'
import cupy as cp
print("CuPy:", cp.__version__)
print("CUDA devices:", cp.cuda.runtime.getDeviceCount())
print("Runtime:", cp.cuda.runtime.runtimeGetVersion())
print("Driver:", cp.cuda.runtime.driverGetVersion())

cp.cuda.Device(0).use()
x = cp.arange(1024*1024, dtype=cp.float32)
y = cp.fft.fft(x)
cp.cuda.Stream.null.synchronize()

print("CuPy FFT test OK")
PY
