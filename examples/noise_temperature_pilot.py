#!/usr/bin/env python3
"""Run an isolated I-iQ/filtered-band pilot through HTCondor and recover HDF5s.

Full-run analysis uses analyze_midas_iq_noise.py, a frozen common reference,
and four simultaneous jobs by default. Raw inputs and published noise products
are never changed. Run `watch` in a persistent process; it resumes from state.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
RUNS = [680, 704, 727, 751, 774, 798, 821, 845, 868, 892, 915, 939]
DEFAULT = Path('/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/noise_temperature_pilot_v1_20261108')
TEMPERATURES = Path('/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/thermometers/thermometers_00680_00939.csv')
RESULTS = Path('/home/mazzitel/HFGW/analysis-work/Run2/reports/noise_temperature_pilot_v1_20261108')
SOURCE_NAMES = ('analyze_midas_iq_noise.py', 'iq_noise_statistics.py',
                'iq_noise_io.py', 'analyze_iq_filtered_bands.py')
INPUT_ROOT = Path('/home/mazzitel/flash-data/data/LNF')
REFERENCE = Path('/home/mazzitel/HFGW/analysis-work/Run2/references/noise_reference.json')


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    temporary.replace(path)


def execute(args, cwd=None):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed: {result.stdout}{result.stderr}')
    return result.stdout


def prepare(campaign, output, temperatures, runs=None, gpfs_url=None, authorize_submissions=False,
            product_version='v1', calibration=None, reuse_directory=None, reuse_runs=None, priority=0):
    path = campaign / 'manifest.json'
    if path.exists():
        return json.loads(path.read_text())
    if product_version not in ('v1','v2'):
        raise ValueError('Unsupported product version')
    if product_version == 'v2':
        from iq_noise_v2 import load_calibration
        if calibration is None or gpfs_url is None:
            raise ValueError('v2 needs an explicit calibration and separate GPFS output directory')
        load_calibration(calibration)
        if gpfs_url.rstrip('/') == json.loads((ROOT/'config/noise_temperature_pilot.json').read_text())['output_url'].rstrip('/'):
            raise ValueError('v2 output must be separate from the v1 pilot')
    runs = sorted(set(RUNS if runs is None else runs))
    reuse_runs = sorted(set(reuse_runs or []))
    if reuse_runs and (product_version != 'v2' or reuse_directory is None or not set(reuse_runs).issubset(runs)):
        raise ValueError('External reuse needs v2, a directory and runs belonging to this campaign')
    if not runs or any(run < 0 for run in runs):
        raise ValueError('Need nonnegative run numbers')
    for run in runs:
        if not (INPUT_ROOT / f'run{run:05d}.mid.gz').is_file():
            raise ValueError(f'Missing input run {run}')
    sources = campaign / 'sources'
    sources.mkdir(parents=True, exist_ok=True)
    reference = REFERENCE
    if json.loads(reference.read_text())['iq_sign'] != -1:
        raise ValueError('Reference must use I-iQ')
    for name in SOURCE_NAMES:
        shutil.copy2(ROOT / 'examples' / name, sources / name)
    extra_sources = []
    if product_version == 'v2':
        shutil.copy2(ROOT/'examples/iq_noise_v2.py',sources/'iq_noise_v2.py')
        shutil.copy2(calibration,sources/'noise_calibration.json')
        extra_sources = ['iq_noise_v2.py','noise_calibration.json']
    shutil.copy2(ROOT / 'examples/hpc/check_noise_environment.py', sources / 'check_noise_environment.py')
    shutil.copy2(reference, sources / 'noise_reference.json')
    shutil.copy2(temperatures, sources / 'temperatures.csv')
    shutil.copy2(temperatures.with_suffix('.schema.json'), sources / 'temperatures.schema.json')
    worker = (ROOT / 'autoreco/noise_job.sh').read_text()
    environment = worker[worker.index('export PYTHONPATH='):worker.index('command -v "$PYTHON"')]
    script = '''#!/bin/bash
set -Eeuo pipefail
RUN_NUMBER=$1
RUN_NAME=$(printf 'run%05d' "$RUN_NUMBER")
JOB_ROOT=$PWD
PYTHON=${NOISE_PYTHON:-python3.9}
mkdir -p results
WORKDIR=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-$PWD}/noise-pilot.XXXXXX")
trap 'rm -rf -- "$WORKDIR"' EXIT
export MPLCONFIGDIR="$WORKDIR/matplotlib"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONUNBUFFERED=1
''' + environment + '''
export HFGW_NOISE_CVMFS_ONLY=1 HFGW_CVMFS_ROOT=/cvmfs/sft-flash.infn.it
"$PYTHON" check_noise_environment.py
export BEARER_TOKEN
BEARER_TOKEN=$(jq -er '.access_token | select(type == "string" and length > 0)' "${_CONDOR_CREDS}/t1.use")
echo "Download $RUN_NAME $(date -u +%FT%TZ)"
gfal-copy "davs://xfer-archive.cr.cnaf.infn.it:8443/flash/data/LNF/${RUN_NAME}.mid.gz" "$WORKDIR/${RUN_NAME}.mid.gz"
echo "Analysis $RUN_NAME $(date -u +%FT%TZ)"
"$PYTHON" -u analyze_midas_iq_noise.py "$WORKDIR/${RUN_NAME}.mid.gz" \
    --out-dir "$JOB_ROOT/results" --global-reference noise_reference.json \
    --iq-sign -1 --mode-workers 1 --phase-lags 1 10 100 --h5-only --filtered-bands --product-version v1
echo "Complete $RUN_NAME $(date -u +%FT%TZ)"
'''
    if product_version == 'v2':
        script = script.replace('--product-version v1','--product-version v2 --calibration noise_calibration.json')
    tag = campaign.name
    output.mkdir(parents=True, exist_ok=True)
    preset = json.loads((ROOT / 'config/noise_temperature_pilot.json').read_text())
    manifest = dict(runs=runs, iq_sign=-1, tag=tag, output=str(output.resolve()), created_utc=now(),
                    product_version=product_version, gpfs_url=gpfs_url or preset['output_url'],
                    submissions_paused=not authorize_submissions,
                    priority=priority, external_runs=reuse_runs,
                    external_directory=str(reuse_directory.resolve()) if reuse_directory else None,
                    temperatures=str(sources / 'temperatures.csv'),
                    source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sources.iterdir() if p.is_file()},
                    analysis_flags=['--iq-sign', '-1', '--h5-only', '--filtered-bands'],
                    resources=dict(cpus_per_job=1, memory='4GB', disk='60GB'))
    for run in runs:
        directory = campaign / f'{run:05d}'
        directory.mkdir(exist_ok=True)
        (directory / 'script.sh').write_text(script)
        (directory / 'script.sh').chmod(0o755)
        transfer = ','.join('../sources/' + name for name in (*SOURCE_NAMES, 'noise_reference.json', 'check_noise_environment.py', *extra_sources))
        (directory / 'submit.sub').write_text(f'''executable = script.sh
arguments = {run}
output = stdout-$(ClusterId).$(ProcID).txt
error = stderr-$(ClusterId).$(ProcID).txt
log = output-$(ClusterId).$(ProcID).log
request_cpus = 1
request_memory = 4GB
request_disk = 60GB
priority = {priority}
transfer_executable = Yes
transfer_input_files = {transfer}
transfer_output_files = results
should_transfer_files = Yes
when_to_transfer_output = ON_EXIT
want_io_proxy = true
use_oauth_services = t1
t1_oauth_permissions = profile,email,openid,offline_access
on_exit_hold = (ExitBySignal == True) || (ExitCode != 0)
+JobBatchName = "{tag}"
+NoisePilotRun = {run}
+NoiseProductVersion = "{product_version}"
queue
''')
        save(directory / 'state.json', dict(run=run, status='external_pending' if run in reuse_runs else 'prepared'))
    save(path, manifest)
    return manifest


def validate(path, run, product_version=None):
    from iq_noise_io import read_summary
    import h5py
    import numpy as np
    summary = read_summary(path)
    if product_version and summary.get('product_version') != product_version:
        raise ValueError(f'Wrong scientific product version: {path}')
    if (summary.get('status') != 'success' or not summary.get('reached_eof')
            or summary.get('iq_sign') != -1 or not summary.get('events') or summary.get('samples', 0) <= 0
            or Path(summary['input']).name.split('.mid')[0] != f'run{run:05d}'):
        raise ValueError(f'Incomplete or wrong-convention result: {path}')
    with h5py.File(path, 'r') as source:
        if product_version and ('product_version' not in source or source['product_version'].asstr()[()] != product_version):
            raise ValueError('Wrong scientific product version in HDF5 root')
        if product_version == 'v2':
            for mode in ('TM010','TM011','TM012'):
                if source[f'dc_removed/modes/{mode}/n'][()] != summary['samples']:
                    raise ValueError('Wrong full-band v2 DC/AC sample count')
            if 'dc_removal' not in source['filtered_bands/config']:
                raise ValueError('Missing v2 DC-removal provenance')
        if source['filtered_bands/config/iq_sign'][()] != -1:
            raise ValueError('Wrong filtered IQ sign')
        expected = np.array([-1e6, -5e5, -25e4, -1e5, 0, 1e5, 25e4, 5e5, 1e6])
        np.testing.assert_array_equal(source['filtered_bands/config/offsets_hz'][:], expected)
        for mode in ('TM010', 'TM011', 'TM012'):
            bands = source[f'filtered_bands/modes/{mode}']
            if len(bands) != 9:
                raise ValueError(f'Missing bands in {mode}')
            for band in bands.values():
                events = band['events']
                if not len(events['n']) or not np.all(np.isfinite(events['rms_v'][:])):
                    raise ValueError(f'Missing or non-finite filtered data in {path}')
    return summary


def cycle(campaign, manifest, max_active, submit):
    if submit and manifest.get('submissions_paused'):
        raise ValueError('Submissions paused by user instruction; do not submit this campaign')
    jobs = json.loads(execute(['condor_q', '-json', '-constraint', f'JobBatchName == "{manifest["tag"]}"',
                              '-attributes', 'ClusterId,JobStatus,HoldReason,NoisePilotRun']) or '[]')
    by_run = {}
    for job in jobs:
        if 'NoisePilotRun' in job:
            run = int(job['NoisePilotRun'])
            if run not in by_run or job['ClusterId'] > by_run[run]['ClusterId']:
                by_run[run] = job
    states = {}
    for run in manifest['runs']:
        directory = campaign / f'{run:05d}'
        state = json.loads((directory / 'state.json').read_text())
        job = by_run.get(run)
        if state['status'] != 'complete':
            if job:
                state.update(cluster=job['ClusterId'], status='submitted')
            suffix = '_v2' if manifest.get('product_version') == 'v2' else ''
            result = directory / 'results' / f'run{run:05d}_noise{suffix}.h5'
            external = run in manifest.get('external_runs',[])
            if external:
                result=Path(manifest['external_directory'])/f'run{run:05d}_noise_v2.h5'
            if state.get('cluster') and not result.exists():
                if job and job['JobStatus'] == 5:
                    state.update(status='failed', error=job.get('HoldReason', 'Job held'))
                elif job and job['JobStatus'] == 4:
                    execute(['condor_transfer_data', str(state['cluster'])], cwd=directory)
                elif not job:
                    history = json.loads(execute(['condor_history', str(state['cluster']), '-limit', '1', '-json',
                                                 '-attributes', 'JobStatus,ExitCode,HoldReason']) or '[]')
                    if history and history[0].get('JobStatus') == 4:
                        execute(['condor_transfer_data', str(state['cluster'])], cwd=directory)
                    elif history and history[0].get('JobStatus') in (3, 5):
                        state.update(status='failed', error=str(history[0]))
            if result.exists():
                try:
                    summary = validate(result, run, product_version=manifest.get('product_version'))
                    if external:
                        import h5py
                        reference=json.loads((campaign/'sources/noise_reference.json').read_text())
                        if summary['global_statistics']['config']['reference'] != reference:
                            raise ValueError('External v2 run uses a different amplitude reference')
                        with h5py.File(result,'r') as source:
                            expected=hashlib.sha256((campaign/'sources/noise_calibration.json').read_bytes()).hexdigest()
                            if source['dc_removed/calibration/sha256'].asstr()[()] != expected:
                                raise ValueError('External v2 run uses a different calibration')
                            cfg=source['filtered_bands/config']
                            if any(cfg[k][()]!=v for k,v in [('fs_hz',5e6),('width_hz',5e4),('taps',2001),('decimation',20)]):
                                raise ValueError('External v2 filters differ from production defaults')
                            if list(cfg['centers_hz'][:]) != [0.,0.,0.]:
                                raise ValueError('External v2 band centers differ')
                    destination = Path(manifest['output']) / result.name
                    digest = hashlib.sha256(result.read_bytes()).hexdigest()
                    if destination.exists():
                        if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                            raise ValueError(f'Existing result differs: {destination}')
                    else:
                        temporary = destination.with_suffix('.h5.tmp')
                        shutil.copy2(result, temporary)
                        temporary.replace(destination)
                    state.update(status='complete', sha256=digest, samples=int(summary['samples']), completed_utc=now())
                    if external:
                        state['reused_from']=str(result)
                except Exception as exc:
                    state.update(status='failed', error=str(exc))
                if state['status'] == 'complete' and manifest.get('gpfs_url'):
                    from iq_noise_publish import publish
                    try:
                        remote_name = result.stem + '_v1.h5' if manifest.get('product_version') == 'v1' else result.name
                        remote = publish(destination, manifest['gpfs_url'].rstrip('/') + '/' + remote_name,
                                         campaign / 'remote_checks')
                        state['gpfs'] = remote
                        state.pop('publication_error', None)
                    except Exception as exc:
                        state.update(status='publication_pending', publication_error=str(exc))
            save(directory / 'state.json', state)
        states[run] = state
    failures = [run for run, state in states.items() if state['status'] == 'failed']
    visible = {int(j['ClusterId']) for j in jobs}
    # Spooled completed jobs remain in condor_q after successful recovery.
    # They reserve a controller place only until recovery/publication completes.
    recovered = {s.get('cluster') for s in states.values() if s['status'] == 'complete'}
    active = sum(j['JobStatus'] in (1, 2, 5, 6, 7)
                 or (j['JobStatus'] == 4 and j['ClusterId'] not in recovered) for j in jobs)
    active += sum(s['status'] == 'submitted' and s.get('cluster') not in visible for s in states.values())
    pending = [r for r, s in states.items() if s['status'] == 'publication_pending']
    if submit and not failures and not pending:
        for run, state in states.items():
            if active >= max_active:
                break
            if state['status'] != 'prepared':
                continue
            directory = campaign / f'{run:05d}'
            response = execute(['condor_submit', '-spool', '-terse', 'submit.sub'], cwd=directory)
            (directory / 'submission.log').write_text(response)
            match = re.match(r'\s*(\d+)\.', response)
            if not match:
                raise ValueError('Unexpected submission response: ' + response)
            state.update(status='submitted', cluster=int(match[1]), submitted_utc=now())
            save(directory / 'state.json', state)
            active += 1
            print(f'Run {run}: submitted cluster {state["cluster"]}', flush=True)
    status = dict(updated_utc=now(), counts=dict(Counter(s['status'] for s in states.values())),
                  failed_runs=failures, active=active, max_active=max_active,
                  queue_counts=dict(Counter(str(j['JobStatus']) for j in jobs)))
    save(campaign / 'status.json', status)
    print(json.dumps(status), flush=True)
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'watch', 'status', 'report'])
    parser.add_argument('--campaign', type=Path, default=DEFAULT)
    parser.add_argument('--output', type=Path, default=RESULTS)
    parser.add_argument('--temperatures', type=Path, default=TEMPERATURES)
    parser.add_argument('--submit', action='store_true')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--max-active', type=int, default=4)
    parser.add_argument('--run-range', nargs=2, type=int, metavar=('FIRST', 'LAST'))
    parser.add_argument('--gpfs-url', help='New campaign scientific output directory')
    parser.add_argument('--authorize-submissions', action='store_true',
                        help='Enable submissions when preparing a new explicitly authorized campaign')
    parser.add_argument('--product-version', choices=['v1','v2'],default='v1')
    parser.add_argument('--calibration',type=Path)
    parser.add_argument('--reuse-directory',type=Path,help='Published v2 pilot directory; external runs are never submitted here')
    parser.add_argument('--reuse-runs',type=int,nargs='+')
    parser.add_argument('--priority',type=int,default=0,help='HTCondor priority within this user; lower waits behind higher priority')
    parser.add_argument('--keep-recovering',action='store_true',
                        help='After failures stop new submissions, but continue recovery/publication of other queued jobs')
    args = parser.parse_args()
    if args.max_active < 1:
        parser.error('--max-active must be positive')
    if args.command == 'prepare':
        if args.run_range and args.run_range[0] > args.run_range[1]:
            parser.error('Invalid run range')
        runs = range(args.run_range[0], args.run_range[1]+1) if args.run_range else None
        print(json.dumps(prepare(args.campaign, args.output, args.temperatures, runs,
                                 args.gpfs_url, args.authorize_submissions,
                                 args.product_version,args.calibration,args.reuse_directory,args.reuse_runs,args.priority), indent=2))
        return
    manifest = json.loads((args.campaign / 'manifest.json').read_text())
    if args.command == 'status':
        print((args.campaign / 'status.json').read_text() if (args.campaign / 'status.json').exists()
              else 'Prepared; no watch cycle yet')
        return
    if args.command == 'watch':
        import fcntl
        lock = (args.campaign / 'watch.lock').open('w')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            status = cycle(args.campaign, manifest, args.max_active, args.submit)
            if status['failed_runs']:
                if not args.keep_recovering:
                    raise RuntimeError(f'Failed runs: {status["failed_runs"]}; no further submissions')
                if not any(status['counts'].get(s,0) for s in ('submitted','publication_pending','external_pending')):
                    print('Recovery finished; failed runs retained, no complete-campaign report generated.',flush=True)
                    return
            if status['counts'].get('complete') == len(manifest['runs']):
                break
            if args.once:
                return
            time.sleep(60)
    from report_noise_temperature import report
    output = Path(manifest['output'])
    if manifest.get('product_version') == 'v2':
        from report_noise_v2 import report as report_v2
        report_v2([output/f'run{run:05d}_noise_v2.h5' for run in manifest['runs']],
                  Path(manifest['temperatures']),output)
        comparison = output/'noise_temperature_comparison_v2.h5'
    else:
        report(output, Path(manifest['temperatures']), manifest['runs'], product_version=manifest.get('product_version'))
        comparison = output/'noise_temperature_comparison.h5'
    if manifest.get('gpfs_url'):
        from iq_noise_publish import publish
        remote = publish(comparison,
                         manifest['gpfs_url'].rstrip('/') + '/noise_temperature_comparison_'+manifest.get('product_version','v1')+'.h5',
                         args.campaign / 'remote_checks')
        save(args.campaign / 'gpfs_comparison.json', remote)


if __name__ == '__main__':
    main()
