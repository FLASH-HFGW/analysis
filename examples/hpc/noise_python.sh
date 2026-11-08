#!/bin/bash
# Source on login and worker: Python 3.9 with scientific packages from FLASH CVMFS.
export HFGW_CVMFS_ROOT="${HFGW_CVMFS_ROOT:-/cvmfs/sft-flash.infn.it}"
source "$HFGW_REPO_ROOT/examples/hpc/environment.sh"
export HFGW_PYTHON=python3.9
if ! command -v "$HFGW_PYTHON" >/dev/null 2>&1; then
    echo "Interpreter unavailable: $HFGW_PYTHON" >&2
    return 11
fi
# Replace inherited paths so a previous venv cannot mask CVMFS propagation delays.
export PYTHONPATH="$CVMFS_ROOT/package/python3.9/site-packages:$CVMFS_ROOT/package/midas/python:$CVMFS_ROOT/FLASH/lib/fllib"
export PYTHONNOUSERSITE=1 HFGW_NOISE_CVMFS_ONLY=1
