#!/bin/bash
set -Eeuo pipefail
set +x
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export HFGW_PYTHON_VERSION=3.11
export HFGW_PYTHON="${HFGW_PYTHON:-python3.11}"
source "$SCRIPT_DIR/environment.sh"
exec "$HFGW_PYTHON" "$SCRIPT_DIR/noise_pilot.py" "$@"
