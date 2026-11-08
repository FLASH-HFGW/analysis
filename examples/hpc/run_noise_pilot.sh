#!/bin/bash
set -Eeuo pipefail
set +x
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ ${1:-} == setup-env ]]; then
    shift
    exec bash "$SCRIPT_DIR/setup_noise_environment.sh" "$@"
fi
export HFGW_REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/noise_python.sh"
exec "$HFGW_PYTHON" "$SCRIPT_DIR/noise_pilot.py" "$@"
