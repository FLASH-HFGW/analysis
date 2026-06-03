#!/bin/bash
# sposatere l'env su CVMFS
MIDAS_PATH="/cvmfs/mazzitel-personalrepo.infn.it/package/midas/python"
FLLIB_PATH="/cvmfs/mazzitel-personalrepo.infn.it/FLASH/lib/fllib"
PACKAGE_PATH="/cvmfs/mazzitel-personalrepo.infn.it/package/python3.9/site-packages/"
export CACHE_BASE="./"

mkdir -p "$CACHE_BASE/matplotlib"
mkdir -p "$CACHE_BASE/xdg-cache"
mkdir -p "$CACHE_BASE/xdg-config"

export MPLCONFIGDIR="$CACHE_BASE/matplotlib"
export XDG_CACHE_HOME="$CACHE_BASE/xdg-cache"
export XDG_CONFIG_HOME="$CACHE_BASE/xdg-config"

ls /cvmfs/mazzitel-personalrepo.infn.it/package/
echo 'env:'
export PYTHONPATH="${PACKAGE_PATH}:${MIDAS_PATH}:${FLLIB_PATH}:${PYTHONPATH}"
export BEARER_TOKEN="$(jq -r .access_token "${_CONDOR_CREDS}/t1.use")"
env
# pip list
echo "--------------------------------------"
echo "Arguments: $@"
echo "--------------------------------------"

fname=$(printf 'run%05d.mid.gz' "$2")
date
gfal-copy davs://xfer-archive.cr.cnaf.infn.it:8443/$1/$fname .
date
echo "--------------------------------------"
echo "run:"
# python3 print_bank.py --path ./ --run $1
python3 -V
python3 fft_chank.py --path ./ --run $2 --fft-out ./$2.out
gfal-copy $2.out davs://xfer-archive.cr.cnaf.infn.it:8443/$3/$2.out
echo "--------------------------------------"
echo "files:"
ls -lsrth

rm $fname 