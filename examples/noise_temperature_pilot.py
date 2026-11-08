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


def prepare(campaign, output, temperatures):
    path = campaign / 'manifest.json'
    if path.exists():
        return json.loads(path.read_text())
    for run in RUNS:
        if not (Path('/home/mazzitel/flash-data/data/LNF') / f'run{run:05d}.mid.gz').is_file():
            raise ValueError(f'Missing input run {run}')
    sources = campaign / 'sources'
    sources.mkdir(parents=True, exist_ok=True)
    reference = Path('/home/mazzitel/HFGW/analysis-work/Run2/references/noise_reference.json')
    if json.loads(reference.read_text())['iq_sign'] != -1:
        raise ValueError('Reference must use I-iQ')
    for name in SOURCE_NAMES:
        shutil.copy2(ROOT / 'examples' / name, sources / name)
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
    tag = campaign.name
    output.mkdir(parents=True, exist_ok=True)
    preset = json.loads((ROOT / 'config/noise_temperature_pilot.json').read_text())
    manifest = dict(runs=RUNS, iq_sign=-1, tag=tag, output=str(output.resolve()), created_utc=now(),
                    product_version='v1', gpfs_url=preset['output_url'], submissions_paused=True,
                    temperatures=str(sources / 'temperatures.csv'),
                    source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sources.iterdir() if p.is_file()},
                    analysis_flags=['--iq-sign', '-1', '--h5-only', '--filtered-bands'],
                    resources=dict(cpus_per_job=1, memory='4GB', disk='60GB'))
    for run in RUNS:
        directory = campaign / f'{run:05d}'
        directory.mkdir(exist_ok=True)
        (directory / 'script.sh').write_text(script)
        (directory / 'script.sh').chmod(0o755)
        transfer = ','.join('../sources/' + name for name in (*SOURCE_NAMES, 'noise_reference.json'))
        (directory / 'submit.sub').write_text(f'''executable = script.sh
arguments = {run}
output = stdout-$(ClusterId).$(ProcID).txt
error = stderr-$(ClusterId).$(ProcID).txt
log = output-$(ClusterId).$(ProcID).log
request_cpus = 1
request_memory = 4GB
request_disk = 60GB
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
+NoiseProductVersion = "v1"
queue
''')
        save(directory / 'state.json', dict(run=run, status='prepared'))
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
            result = directory / 'results' / f'run{run:05d}_noise.h5'
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
    active = sum(j['JobStatus'] in (1, 2, 4, 5, 6, 7) for j in jobs)
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
                  failed_runs=failures, queue_counts=dict(Counter(str(j['JobStatus']) for j in jobs)))
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
    args = parser.parse_args()
    if args.max_active < 1:
        parser.error('--max-active must be positive')
    if args.command == 'prepare':
        print(json.dumps(prepare(args.campaign, args.output, args.temperatures), indent=2))
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
                raise RuntimeError(f'Failed runs: {status["failed_runs"]}; no further submissions')
            if status['counts'].get('complete') == len(manifest['runs']):
                break
            if args.once:
                return
            time.sleep(60)
    from report_noise_temperature import report
    output = Path(manifest['output'])
    report(output, Path(manifest['temperatures']), manifest['runs'], product_version=manifest.get('product_version'))
    if manifest.get('gpfs_url'):
        from iq_noise_publish import publish
        remote = publish(output / 'noise_temperature_comparison.h5',
                         manifest['gpfs_url'].rstrip('/') + '/noise_temperature_comparison_v1.h5',
                         args.campaign / 'remote_checks')
        save(args.campaign / 'gpfs_comparison.json', remote)


if __name__ == '__main__':
    main()
