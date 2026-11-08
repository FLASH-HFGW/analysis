#!/usr/bin/env python3
"""Prepare, submit, recover and report one-pass SPEC-continuity repairs.

Uses autoreco's noise storage conventions and isolated job directories. The
original noise campaign and read-only logbook states are never modified.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
BASE=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/noise_continuous')
WORKBASE=Path('/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/noise_continuous')

def write_state(path,state):
    state['updated_utc']=datetime.now(timezone.utc).isoformat()
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(state,indent=2)+'\n');tmp.replace(path)

def prepare(run):
    directory=WORKBASE/'jobs'/f'{run:05d}';directory.mkdir(parents=True,exist_ok=True)
    state_path=directory/'repair_state.json'
    if state_path.exists():return directory,json.loads(state_path.read_text())
    sources=WORKBASE/'sources';sources.mkdir(exist_ok=True)
    for name in ('correct_iq_noise_continuity.py','analyze_midas_iq_noise.py','iq_noise_statistics.py','iq_noise_io.py'):
        target=sources/name
        if not target.exists():shutil.copy2(ROOT/'examples'/name,target)
    original=Path('/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/job_to_submit_noise')/f'{run:05d}'
    name=f'run{run:05d}_noise'
    transfer=[sources/n for n in ('correct_iq_noise_continuity.py','analyze_midas_iq_noise.py','iq_noise_statistics.py','iq_noise_io.py')]+[original/(name+ext) for ext in ('.json','.npz')]
    # Reuse environment/authentication/download/upload conventions of noise_job.sh.
    worker=(ROOT/'autoreco/noise_job.sh').read_text()
    env=worker[worker.index('export PYTHONPATH='):worker.index('command -v "$PYTHON"')]
    script='''#!/bin/bash
set -Eeuo pipefail
RUN_NUMBER=$1
RUN_NAME=$(printf 'run%05d' "$RUN_NUMBER")
JOB_ROOT=$PWD
PYTHON=${NOISE_PYTHON:-python3}
WORKDIR=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-$PWD}/continuity.XXXXXX")
trap 'rm -rf -- "$WORKDIR"' EXIT
export MPLCONFIGDIR="$WORKDIR/matplotlib"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
'''+env+'''
export BEARER_TOKEN
BEARER_TOKEN=$(jq -er '.access_token | select(type == "string" and length > 0)' "${_CONDOR_CREDS}/t1.use")
gfal-copy "davs://xfer-archive.cr.cnaf.infn.it:8443/flash/data/LNF/${RUN_NAME}.mid.gz" "$WORKDIR/${RUN_NAME}.mid.gz"
"$PYTHON" -u correct_iq_noise_continuity.py "${RUN_NAME}_noise.json" "$WORKDIR/${RUN_NAME}.mid.gz" --out-dir results
BEARER_TOKEN=$(jq -er '.access_token | select(type == "string" and length > 0)' "${_CONDOR_CREDS}/t1.use")
REMOTE=davs://xfer-archive.cr.cnaf.infn.it:8443/flash/analysis/autoreco/Run2/noise_by_run_continuous
gfal-mkdir -p "$REMOTE"
for suffix in _noise.npz _noise.png _noise_iq.png _noise.json; do
 gfal-copy -f "$JOB_ROOT/results/${RUN_NAME}${suffix}" "$REMOTE/${RUN_NAME}${suffix}"
done
'''
    (directory/'script.sh').write_text(script);(directory/'script.sh').chmod(0o755)
    (directory/'submit.sub').write_text(f'''executable = script.sh
arguments = {run}
output = stdout-$(ClusterId).$(ProcID).txt
error = stderr-$(ClusterId).$(ProcID).txt
log = output-$(ClusterId).$(ProcID).log
request_cpus = 1
request_memory = 4GB
request_disk = 40GB
transfer_executable = Yes
transfer_input_files = {','.join(os.path.relpath(p,directory) for p in transfer)}
transfer_output_files = results
should_transfer_files = Yes
when_to_transfer_output = ON_EXIT
want_io_proxy = true
use_oauth_services = t1
t1_oauth_permissions = profile,email,openid,offline_access
on_exit_hold = (ExitBySignal == True) || (ExitCode != 0)
+JobBatchName = "noise-continuity-v2"
queue
''')
    state={'run':run,'status':'prepared','schema':2,'cpus':1,'method':'one raw pass; preserve amplitude products'}
    write_state(state_path,state);return directory,state


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--submit',action='store_true');p.add_argument('--recover',action='store_true')
    p.add_argument('--retry-removed',action='store_true',help='Retry missing outputs only if history confirms removal');p.add_argument('--status',action='store_true');p.add_argument('--run-range',type=int,nargs=2,default=(680,939))
    args=p.parse_args();WORKBASE.mkdir(parents=True,exist_ok=True);counts={};queue={}
    if args.recover or args.status or args.retry_removed:
        query=subprocess.run(['/usr/bin/condor_q','-json','-constraint','JobBatchName == "noise-continuity-v2"',
                              '-attributes','ClusterId,JobStatus,HoldReason'],text=True,capture_output=True)
        if query.returncode:raise RuntimeError(query.stderr)
        queue={row['ClusterId']:row for row in json.loads(query.stdout or '[]')}
    for run in range(args.run_range[0],args.run_range[1]+1):
        name=f'run{run:05d}_noise';destination=BASE/'by_run'/f'{run:05d}'
        if (destination/(name+'.json')).exists():
            counts['corrected']=counts.get('corrected',0)+1;continue
        directory,state=prepare(run);state_path=directory/'repair_state.json'
        if args.recover and state.get('cluster') and (queue.get(state['cluster'],{}).get('JobStatus')==4 or (directory/'results'/(name+'.json')).exists()):
            result=subprocess.run(['/usr/bin/condor_transfer_data',str(state['cluster'])],cwd=directory,check=False,capture_output=True,text=True)
            (directory/'recovery.log').write_text(result.stdout+result.stderr)
            results=directory/'results'
            if (results/(name+'.json')).exists():
                doc=json.loads((results/(name+'.json')).read_text())
                if doc['global_statistics']['schema']!=2:raise ValueError('Invalid recovered schema')
                published=destination
                destination=WORKBASE/'by_run'/f'{run:05d}'
                destination.mkdir(parents=True,exist_ok=True)
                shutil.copy2(results/(name+'.npz'),destination/(name+'.npz'))
                sys.path.insert(0,str(ROOT/'examples'))
                import numpy as np
                from correct_iq_noise_continuity import replot
                with np.load(destination/(name+'.npz')) as z:arrays={key:z[key] for key in z.files}
                replot(arrays,doc,destination/name)
                doc['plot_revision']=2
                (destination/(name+'.json')).write_text(json.dumps(doc,indent=2,allow_nan=False)+'\n')
                remote='davs://xfer-archive.cr.cnaf.infn.it:8443/flash/analysis/autoreco/Run2/'+str(published.relative_to(BASE.parent))
                for output in destination.glob(name+'.*'):
                    subprocess.run(['gfal-copy','-p','-f','-K','ADLER32',output.as_uri(),remote+'/'+output.name],check=True)
                for output in destination.glob(name+'_iq.png'):
                    subprocess.run(['gfal-copy','-p','-f','-K','ADLER32',output.as_uri(),remote+'/'+output.name],check=True)
                state['status']='corrected';write_state(state_path,state)
        if args.retry_removed and state.get('cluster') and state['cluster'] not in queue:
            history=subprocess.run(['/usr/bin/condor_history',str(state['cluster']),'-limit','1','-json',
                                    '-attributes','JobStatus,RemoveReason,LastHoldReason'],text=True,capture_output=True,check=True)
            rows=json.loads(history.stdout or '[]')
            if rows and rows[0].get('JobStatus')==3:
                state.setdefault('previous_attempts',[]).append({'cluster':state['cluster'],**rows[0]})
                state['status']='prepared';write_state(state_path,state)
        if args.submit and state['status']=='prepared':
            result=subprocess.run(['/usr/bin/condor_submit','-spool','-terse','submit.sub'],cwd=directory,text=True,capture_output=True)
            (directory/'submission.log').write_text(result.stdout+result.stderr)
            if result.returncode:
                print(result.stdout+result.stderr,file=sys.stderr)
                raise RuntimeError(f'Submission failed for run {run}; see {directory}/submission.log')
            state.update(status='submitted',cluster=int(result.stdout.strip().split()[0].split('.')[0]));write_state(state_path,state)
            print(f'Run {run}: submitted cluster {state["cluster"]}',flush=True)
        label=('corrected' if state['status']=='corrected' else {1:'idle',2:'running',4:'completed_pending_recovery',5:'held'}.get(queue.get(state.get('cluster'),{}).get('JobStatus'),state['status']))
        counts[label]=counts.get(label,0)+1
    write_state(WORKBASE/'campaign_status.json',{'counts':counts,'requested_runs':list(args.run_range)})
    print(json.dumps(counts,indent=2))

if __name__=='__main__':main()
