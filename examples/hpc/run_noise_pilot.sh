#!/bin/bash
set -Eeuo pipefail
set +x
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/environment.sh"
exec "${HFGW_PYTHON:-python3.9}" "$SCRIPT_DIR/noise_pilot.py" "$@"
