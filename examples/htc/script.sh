#!/bin/bash
# sposatere l'env su CVMFS ##############################
MIDAS_PATH="/cvmfs/mazzitel-personalrepo.infn.it/package/midas/python"
FLLIB_PATH="/cvmfs/mazzitel-personalrepo.infn.it/FLASH/lib/fllib"
PACKAGE_PATH="/cvmfs/mazzitel-personalrepo.infn.it/package/python3.9/site-packages/"
# questa parte serve per usare matplotlibe
export CACHE_BASE="./"

mkdir -p "$CACHE_BASE/matplotlib"
mkdir -p "$CACHE_BASE/xdg-cache"
mkdir -p "$CACHE_BASE/xdg-config"

export MPLCONFIGDIR="$CACHE_BASE/matplotlib"
export XDG_CACHE_HOME="$CACHE_BASE/xdg-cache"
export XDG_CONFIG_HOME="$CACHE_BASE/xdg-config" 
##########################################################
# controllo del worker node
echo "=== CPU before OMP limits ==="
nproc
env -u OMP_NUM_THREADS -u OMP_THREAD_LIMIT nproc
grep -E 'Cpus_allowed|Cpus_allowed_list' /proc/self/status

# Limita thread interni delle librerie numeriche
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export PYTHONUNBUFFERED=1

echo "=== CPU after OMP limits ==="
nproc
env -u OMP_NUM_THREADS -u OMP_THREAD_LIMIT nproc
python3 - <<'PY'
import os
print("os.cpu_count():", os.cpu_count())
print("affinity:", len(os.sched_getaffinity(0)), sorted(os.sched_getaffinity(0)))
PY

echo "=== Linux memory ==="
free -h
cat /proc/meminfo | egrep 'MemTotal|MemAvailable'

echo '--- set packege e authorization token'
export PYTHONPATH="${PACKAGE_PATH}:${MIDAS_PATH}:${FLLIB_PATH}:${PYTHONPATH}"
# refresh token befor copy
export BEARER_TOKEN="$(jq -r .access_token "${_CONDOR_CREDS}/t1.use")"
# echo '-- debug print env:'
# env

echo "--------------------------------------"
echo "Arguments: $@"
echo "--------------------------------------"

fname=$(printf 'run%05d.mid.gz' "$2")

echo ">> Start coping ${fname}: `date`"
gfal-copy davs://xfer-archive.cr.cnaf.infn.it:8443/$1/$fname .
ls -hl ./$fname 
echo ">> End coping: `date`"
echo "--------------------------------------"
echo "Python version: `python3 -V`"
echo "run:"

# python3 print_bank.py --path ./ --run $1
# python3 fft_chank.py --path ./ --run $2 --fft-out ./$2.out
#python3 analyze_midas_iq_fft_only.py --path ./ --run $2 --fft-out ./$2.out --max-fft-events $4 --fs 5e6 --input-range 5 --iq-sign 1 --mode-workers $5

#python3 analyze_midas_iq_fft_average_h5_process.py  --path ./ --run $2 --h5-out ./  --avg-all  --workers 8 --max-inflight-events 8  --h5-compression gzip  --h5-gzip-level 3

python3 analyze_midas_iq_fft_4ms.py --path ./  --run "$2" 



  
echo "run complited, `date`, list of files:"
ls -lsrth

echo ">> Output coping: `date`"
# refresh token befor copy
export BEARER_TOKEN="$(jq -r .access_token "${_CONDOR_CREDS}/t1.use")"
# se vuoi la directory
gfal-copy -r $2.out davs://xfer-archive.cr.cnaf.infn.it:8443/$3/$2.out
#gfal-copy ./$2.out/run$(printf '%05d' "$2")_fft_average.h5 davs://xfer-archive.cr.cnaf.infn.it:8443/$3/run$(printf '%05d' "$2")_fft_average.h5
# out_h5="./$2.out/run$(printf '%05d' "$2")_fft_average.h5"

# gfal-copy "$out_h5" \
#   "davs://xfer-archive.cr.cnaf.infn.it:8443/$3/run$(printf '%05d' "$2")_fft_average.h5"
echo "--------------------------------------"


rm $fname 