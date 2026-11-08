#!/bin/bash
# Source on both login and worker: the available system interpreter is Python 3.9.
source "$HFGW_REPO_ROOT/examples/hpc/environment.sh"
NOISE_VENV="${HFGW_NOISE_VENV:-${HFGW_RUNTIME_ROOT:-$HOME/HFGW/analysis-runtime/autoreco/Run2}/environments/noise_py39_v1}"
if [[ -z ${HFGW_PYTHON:-} ]]; then
    if [[ -x "$NOISE_VENV/bin/python" ]]; then
        HFGW_PYTHON="$NOISE_VENV/bin/python"
    else
        HFGW_PYTHON=python3.9
    fi
fi
if ! command -v "$HFGW_PYTHON" >/dev/null 2>&1; then
    echo "Interpreter unavailable: $HFGW_PYTHON. Run: bash examples/hpc/run_noise_pilot.sh setup-env" >&2
    return 11
fi
if [[ "$HFGW_PYTHON" == "$NOISE_VENV/bin/python" ]]; then
    export PYTHONPATH="$NOISE_VENV/lib/python3.9/site-packages:$PYTHONPATH"
fi
export HFGW_PYTHON
