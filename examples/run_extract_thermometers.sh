#!/bin/bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
MIDAS_PATH=/cvmfs/mazzitel-personalrepo.infn.it/package/midas/python
PACKAGE_PATH=/cvmfs/mazzitel-personalrepo.infn.it/package/python3.9/site-packages
export PYTHONPATH="${MIDAS_PATH}:${PACKAGE_PATH}${PYTHONPATH:+:${PYTHONPATH}}"
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec /usr/bin/python3 "$SCRIPT_DIR/extract_thermometers.py" "$@"
