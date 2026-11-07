#!/bin/bash
#SBATCH --job-name=test_gfal
#SBATCH --partition=CPU
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --output=/home/mazzitel/slurm_logs/GFAL_%j.out
#SBATCH --error=/home/mazzitel/slurm_logs/GFAL_%j.err
set -euo pipefail
REPO_ROOT="${HFGW_REPO_ROOT:-${SLURM_SUBMIT_DIR:-$PWD}}"
while [[ ! -f "$REPO_ROOT/examples/hpc/environment.sh" ]]; do
    [[ "$REPO_ROOT" != / && "$REPO_ROOT" != . ]] || { echo 'Set HFGW_REPO_ROOT' >&2; exit 10; }
    REPO_ROOT=$(dirname -- "$REPO_ROOT")
done
source "$REPO_ROOT/examples/hpc/environment.sh"
[[ -n ${BEARER_TOKEN:-} ]] || { echo 'Export BEARER_TOKEN before sbatch' >&2; exit 20; }
command -v gfal-ls
gfal-ls -l "${HFGW_GFAL_TEST_URL:-davs://xfer-archive.cr.cnaf.infn.it:8443/flash/data/LNF/}"
# Set a small file URL explicitly to test a download as well as directory access.
if [[ ${HFGW_GFAL_TEST_DOWNLOAD:-0} == 1 ]]; then
    : "${HFGW_GFAL_TEST_URL:?Set a small file URL for the download test}"
    TEST_DIR=$(mktemp -d "${SLURM_TMPDIR:-/tmp}/gfal-test.XXXXXX")
    trap 'rm -rf -- "$TEST_DIR"' EXIT
    gfal-copy "$HFGW_GFAL_TEST_URL" "$TEST_DIR/input"
    [[ -s "$TEST_DIR/input" ]]
fi
echo 'Direct CVMFS/GFAL test completed'
