#!/bin/bash
# Compatibility entrypoint for the old four-argument payload.
set -euo pipefail
[[ $# -eq 4 ]] || { echo 'Usage: script.sh INPUT_PATH RUN SCRATCH_ROOT MAX_EVENTS' >&2; exit 2; }
export HFGW_INPUT_PATH=$1 HFGW_RUN=$2 HFGW_SCRATCH_ROOT=$3 HFGW_MAX_EVENTS=$4
HFGW_REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
export HFGW_REPO_ROOT
exec bash "$HFGW_REPO_ROOT/examples/hpc/job.sh"
