#!/usr/bin/env python3
"""Recover corrected jobs; rebuild global products/slides only at 260/260."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];BASE=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/noise_continuous')

def run(*args):subprocess.run([sys.executable,*map(str,args)],cwd=ROOT,check=True)

def finalize():
    missing=[]
    for n in range(680,940):
        p=BASE/'by_run'/f'{n:05d}'/f'run{n:05d}_noise.json'
        if not p.exists():missing.append(n);continue
        d=json.loads(p.read_text())
        if d['global_statistics']['schema']!=2 or not d['reached_eof']:raise ValueError('Invalid corrected run '+str(n))
    if missing:
        print(f'Correction progress: {260-len(missing)}/260; no mixed-schema aggregation.',flush=True)
        return False
    run('examples/aggregate_iq_noise.py',BASE/'by_run','--out-dir',BASE/'global','--expected-runs','config/noise_runs.txt')
    run('examples/assess_iq_noise_stationarity.py','--input-dir',BASE/'by_run','--out-dir',BASE/'stationarity')
    run('examples/estimate_iq_level_stability_time.py','--input',BASE/'stationarity/stationarity_by_run.csv','--out-dir',BASE/'stationarity')
    run('examples/summarize_iq_continuity.py')
    run('examples/compare_iq_amplitude_models.py')
    run('examples/fit_iq_correlation_decay.py')
    run('reporting/iq_noise_summary_v5/build_slides.py')
    (Path('/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/noise_continuous/finalized.json')).write_text(json.dumps({'runs':260,'schema':2,'status':'success'},indent=2)+'\n')
    print('All corrected global products and slides generated.',flush=True);return True

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--watch',action='store_true');args=p.parse_args()
    while True:
        run('autoreco/repair_noise_continuity.py','--recover')
        if finalize() or not args.watch:break
        time.sleep(60)

if __name__=='__main__':main()
