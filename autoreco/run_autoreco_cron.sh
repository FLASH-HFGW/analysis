#!/bin/bash
set -euo pipefail

AUTORECO_DIR="/home/mazzitel/HFGW/analysis/autoreco"
PACKAGE_PATH="/cvmfs/mazzitel-personalrepo.infn.it/package/python3.9/site-packages"
MIDAS_PATH="/cvmfs/mazzitel-personalrepo.infn.it/package/midas/python"
FLLIB_PATH="/cvmfs/mazzitel-personalrepo.infn.it/FLASH/lib/fllib"

export PATH="/usr/local/bin:/usr/bin:/bin:/home/mazzitel/.local/bin"
export PYTHONPATH="${PACKAGE_PATH}:${MIDAS_PATH}:${FLLIB_PATH}"

cd "$AUTORECO_DIR"
exec /usr/bin/python3 ./autoreco.py "$@"
