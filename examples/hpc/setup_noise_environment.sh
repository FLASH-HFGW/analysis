#!/bin/bash
set -Eeuo pipefail
set +x
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/environment.sh"
NOISE_VENV="${HFGW_NOISE_VENV:-${HFGW_RUNTIME_ROOT:-$HOME/HFGW/analysis-runtime/autoreco/Run2}/environments/noise_py39_v1}"
BOOTSTRAP_PYTHON="${HFGW_BOOTSTRAP_PYTHON:-python3.9}"
command -v "$BOOTSTRAP_PYTHON" >/dev/null
if [[ ! -x "$NOISE_VENV/bin/python" ]]; then
    mkdir -p "$(dirname -- "$NOISE_VENV")"
    "$BOOTSTRAP_PYTHON" -m venv "$NOISE_VENV"
fi
"$NOISE_VENV/bin/python" -c 'import sys; assert sys.version_info[:2] == (3, 9), "The IQ venv must use Python 3.9"'
export PYTHONPATH="$NOISE_VENV/lib/python3.9/site-packages:$PYTHONPATH"
export MPLCONFIGDIR="$NOISE_VENV/matplotlib-cache"
PIP_ARGS=(--only-binary=:all: --no-deps)
if [[ -n ${HFGW_NOISE_WHEELHOUSE:-} ]]; then
    PIP_ARGS+=(--no-index --find-links "$HFGW_NOISE_WHEELHOUSE")
else
    PIP_ARGS+=(--index-url https://pypi.org/simple)
fi
"$NOISE_VENV/bin/python" -m pip install "${PIP_ARGS[@]}" -r "$SCRIPT_DIR/noise-requirements.txt"
"$NOISE_VENV/bin/python" "$SCRIPT_DIR/check_noise_environment.py"
echo "Shared user environment ready: $NOISE_VENV"
