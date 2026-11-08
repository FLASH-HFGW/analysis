#!/usr/bin/env python3
"""Prepare and monitor the 12-run IQ pilot on the LNF Slurm login node.

No submission occurs without `watch --submit`. At most four jobs are submitted
at once, each obtaining a fresh token through the tested one-run launcher.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'examples'))
from noise_temperature_pilot import RUNS, SOURCE_NAMES, save, now


def execute(args, env=None):
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


def prepare(args):
    campaign = args.campaign.resolve()
    if (campaign / 'manifest.json').exists():
        print('Existing campaign preserved:', campaign)
        return
    if not args.reference or not args.temperatures:
        raise ValueError('prepare requires --reference and --temperatures')
    reference = json.loads(args.reference.read_text())
    if reference['iq_sign'] != -1:
        raise ValueError('The shared reference must use I-iQ')
    sources = campaign / 'sources'
    sources.mkdir(parents=True, exist_ok=True)
    for name in (*SOURCE_NAMES, 'report_noise_temperature.py', 'plot_thermometers_history.py'):
        shutil.copy2(ROOT / 'examples' / name, sources / name)
    shutil.copy2(args.reference, sources / 'noise_reference.json')
    shutil.copy2(args.temperatures, sources / 'temperatures.csv')
    shutil.copy2(args.temperatures.with_suffix('.schema.json'), sources / 'temperatures.schema.json')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / 'jobs').mkdir(exist_ok=True)
    for run in RUNS:
        save(campaign / f'run{run:05d}.json', dict(run=run, status='prepared'))
    manifest = dict(runs=RUNS, iq_sign=-1, output=str(output), created_utc=now(),
                    source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources.iterdir()},
                    scheduler='slurm', host='hpc-slurmui-010.lnf.infn.it',
                    note='CPU IQ calculations; tested association cygno/GPU reserves one GPU per job')
    save(campaign / 'manifest.json', manifest)
    print('Prepared runs:', ', '.join(map(str, RUNS)))
    print('State:', campaign)
    print('Results:', output)


def verify_sources(campaign, manifest):
    for name, digest in manifest['source_sha256'].items():
        if hashlib.sha256((campaign / 'sources' / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Frozen source changed: {name}; use a new campaign')


def cycle(args, manifest):
    campaign = args.campaign.resolve()
    output = Path(manifest['output'])
    states = {r: json.loads((campaign / f'run{r:05d}.json').read_text()) for r in manifest['runs']}
    queued = {}
    if any(s['status'] == 'submitted' for s in states.values()):
        for line in execute(['squeue', '-h', '-u', os.environ['USER'], '-o', '%A %T']).splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0].isdigit():
                queued[int(parts[0])] = parts[1]
    for run, state in states.items():
        if state['status'] != 'submitted':
            continue
        directory = output / 'jobs' / f'JOB_{state["job_id"]}'
        status_file = directory / 'job_status.json'
        if status_file.exists():
            result = json.loads(status_file.read_text())
            try:
                if result['exit_code'] != 0 or result['run'] != run:
                    raise ValueError(f'Worker failed: {result}')
                from noise_temperature_pilot import validate
                source = directory / f'run{run:05d}_noise.h5'
                validate(source, run)
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                destination = output / source.name
                if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                    raise ValueError(f'Different existing result: {destination}')
                if not destination.exists():
                    temporary = destination.with_suffix('.h5.tmp')
                    shutil.copy2(source, temporary)
                    temporary.replace(destination)
                state.update(status='complete', completed_utc=now(), sha256=digest)
            except Exception as exc:
                state.update(status='failed', error=str(exc))
        elif state['job_id'] not in queued:
            accounting = execute(['sacct', '-X', '-n', '-j', str(state['job_id']), '--format=State,ExitCode', '-P'])
            if accounting.strip():
                slurm_state = accounting.split('|', 1)[0].strip().split()[0].rstrip('+')
                if slurm_state in ('FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL', 'PREEMPTED', 'BOOT_FAIL', 'COMPLETED'):
                    state.update(status='failed', error=f'Slurm {slurm_state}, missing job_status.json: {accounting.strip()}')
        save(campaign / f'run{run:05d}.json', state)
    failed = [r for r, s in states.items() if s['status'] == 'failed']
    active = sum(s['status'] == 'submitted' for s in states.values())
    if args.submit and not failed:
        for run, state in states.items():
            if active >= args.max_active:
                break
            if state['status'] != 'prepared':
                continue
            env = os.environ.copy()
            env.update(HFGW_NOISE_SOURCE_DIR=str(campaign / 'sources'), HFGW_NOISE_OUTPUT_ROOT=str(output / 'jobs'))
            command = ['bash', str(ROOT / 'examples/hpc/submit_one_run.sh'), str(run), '--analysis', 'noise',
                       '--reference', str(campaign / 'sources/noise_reference.json'), '--token-time', str(args.token_time),
                       '--time', args.time, '--account', args.account, '--partition', args.partition, '--qos', args.qos]
            response = execute(command, env=env)
            (campaign / f'run{run:05d}_submission.log').write_text(response)
            match = re.search(r'Submitted job (\d+):', response)
            if not match:
                raise ValueError('Unexpected launcher response; check squeue before retrying')
            state.update(status='submitted', job_id=int(match[1]), submitted_utc=now())
            save(campaign / f'run{run:05d}.json', state)
            active += 1
            print(response, flush=True)
    status = dict(counts=dict(Counter(s['status'] for s in states.values())), failed_runs=failed,
                  active=active, queue_states=queued, updated_utc=now())
    save(campaign / 'status.json', status)
    print(json.dumps(status), flush=True)
    return status


def main():
    home = Path.home() / 'HFGW'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'watch', 'status', 'report'])
    parser.add_argument('--campaign', type=Path, default=home / 'analysis-runtime/autoreco/Run2/noise_temperature_pilot_slurm_20261108')
    parser.add_argument('--output', type=Path, default=home / 'analysis-work/Run2/reports/noise_temperature_pilot_minus1_20261108')
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--temperatures', type=Path)
    parser.add_argument('--submit', action='store_true')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--max-active', type=int, default=4)
    parser.add_argument('--token-time', type=int, default=3600)
    parser.add_argument('--time', default='03:00:00')
    parser.add_argument('--account', default=os.environ.get('HFGW_SLURM_ACCOUNT', 'cygno'))
    parser.add_argument('--partition', default=os.environ.get('HFGW_SLURM_PARTITION', 'GPU'))
    parser.add_argument('--qos', default=os.environ.get('HFGW_SLURM_QOS', 'normal'))
    args = parser.parse_args()
    if args.max_active < 1 or args.token_time < 1:
        parser.error('Concurrency and token time must be positive')
    if args.command == 'prepare':
        prepare(args)
        return
    manifest = json.loads((args.campaign / 'manifest.json').read_text())
    if args.command == 'status':
        states = [json.loads((args.campaign / f'run{r:05d}.json').read_text()) for r in manifest['runs']]
        print(json.dumps(dict(Counter(s['status'] for s in states)), indent=2))
        return
    verify_sources(args.campaign, manifest)
    if args.command == 'watch':
        import fcntl
        with (args.campaign / 'watch.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            while True:
                status = cycle(args, manifest)
                if status['failed_runs']:
                    raise RuntimeError('Failed runs; further submissions stopped: ' + str(status['failed_runs']))
                if status['counts'].get('complete') == len(manifest['runs']):
                    break
                if args.once:
                    return
                time.sleep(60)
    # Use the frozen reporting source and frozen temperature observations too.
    sys.path.insert(0, str(args.campaign / 'sources'))
    from report_noise_temperature import report
    report(Path(manifest['output']), args.campaign / 'sources/temperatures.csv', manifest['runs'])


if __name__ == '__main__':
    main()
