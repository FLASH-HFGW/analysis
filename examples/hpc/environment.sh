#!/bin/bash
# Shared environment for the LNF SLURM workers. Source this file.
if [[ -n ${HFGW_CVMFS_ROOT:-} ]]; then
    CVMFS_ROOT=$HFGW_CVMFS_ROOT
elif [[ -d /cvmfs/sft-flash.infn.it/modules/modulefiles/x86_64-el9 ]]; then
    CVMFS_ROOT=/cvmfs/sft-flash.infn.it
else
    CVMFS_ROOT=/cvmfs/mazzitel-personalrepo.infn.it
fi
MODULE_DIR="$CVMFS_ROOT/modules/modulefiles/x86_64-el9"
[[ -d "$MODULE_DIR" ]] || { echo "CVMFS modules unavailable: $MODULE_DIR" >&2; return 11; }
if ! command -v module >/dev/null 2>&1; then
    [[ ! -f /etc/profile.d/modules.sh ]] || source /etc/profile.d/modules.sh
fi
command -v module >/dev/null 2>&1 || { echo 'Environment Modules is unavailable' >&2; return 11; }
module use "$MODULE_DIR"
module load gfal/1.9.0
PYTHON_VERSION="${HFGW_PYTHON_VERSION:-3.9}"
[[ "$PYTHON_VERSION" =~ ^[0-9]+\.[0-9]+$ ]] || { echo 'Invalid HFGW_PYTHON_VERSION' >&2; return 11; }
PACKAGE_PATH="$CVMFS_ROOT/package/python${PYTHON_VERSION}/site-packages"
# The 3.11 collection has the numerical extensions, while packaging/dateutil/six
# are currently published in the 3.9 collection as pure Python dependencies.
if [[ "$PYTHON_VERSION" == 3.11 ]]; then
    PACKAGE_PATH="$PACKAGE_PATH:$CVMFS_ROOT/package/python3.9/site-packages"
fi
export PYTHONPATH="$PACKAGE_PATH:$CVMFS_ROOT/package/midas/python:$CVMFS_ROOT/FLASH/lib/fllib:${PYTHONPATH:-}"
export X509_CERT_DIR=/cvmfs/grid.cern.ch/etc/grid-security/certificates
export SSL_CERT_DIR="$X509_CERT_DIR"
export PYTHONDONTWRITEBYTECODE=1
echo "CVMFS environment: $CVMFS_ROOT"
