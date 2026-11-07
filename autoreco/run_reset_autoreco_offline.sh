#!/bin/bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

AUTORECO_DIR="/home/mazzitel/HFGW/analysis/autoreco"

exec /usr/bin/python3 "$AUTORECO_DIR/reset_autoreco_offline.py" "$@"
