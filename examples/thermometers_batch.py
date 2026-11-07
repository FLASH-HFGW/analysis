#!/usr/bin/env python3
"""Prepare, submit, recover and merge isolated HTCondor thermometer jobs."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from zipfile import ZipFile, ZIP_DEFLATED

import extract_thermometers as extractor


DEFAULT_CAMPAIGN = Path('/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/thermometers_batch_00680_00939')
FORMAT = 'thermometers-batch-v1'


def now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, doc):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(doc, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def execute(command, cwd=None):
    result = subprocess.run(list(map(str, command)), cwd=cwd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'{command[0]} failed ({result.returncode}): {result.stderr.strip()}')
    return result.stdout


def bundle_path(campaign, run):
    return campaign / f'{run:05d}' / 'results' / f'run{run:05d}_thermometers.zip'


def pack(run, output, bundle, input_url, exit_code):
    report_path = output.with_suffix('.report.json')
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    products = [output, output.with_suffix('.sqlite'), report_path, output.with_suffix('.schema.json')]
    success = (exit_code == 0 and report.get('source_status_counts') == {'complete': 1}
               and all(path.is_file() for path in products))
    manifest = {'format': FORMAT, 'run': run, 'input_url': input_url, 'exit_code': exit_code,
                'status': 'complete' if success else 'failed', 'records': report.get('records', 0),
                'created_utc': now(), 'files': {}}
    bundle.parent.mkdir(parents=True, exist_ok=True)
    temporary = bundle.with_suffix('.tmp')
    with ZipFile(temporary, 'w', compression=ZIP_DEFLATED) as archive:
        for path in products:
            if path.is_file():
                data = path.read_bytes()
                archive.writestr(path.name, data)
                manifest['files'][path.name] = {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        archive.writestr('job_result.json', json.dumps(manifest))
    temporary.replace(bundle)
    if exit_code == 0 and not success:
        raise ValueError('Extraction did not produce one complete source')


def validate_bundle(path, run):
    with ZipFile(path) as archive:
        names = archive.namelist()
        doc = json.loads(archive.read('job_result.json'))
        if doc.get('format') != FORMAT or doc.get('run') != run or doc.get('status') != 'complete':
            raise ValueError(f'Run {run}: invalid or unsuccessful result bundle')
        if len(names) != len(set(names)) or set(names) != set(doc['files']) | {'job_result.json'}:
            raise ValueError('Duplicate or unindexed bundle members')
        prefix = f'run{run:05d}'
        expected = {prefix + suffix for suffix in ('.csv', '.sqlite', '.report.json', '.schema.json')}
        if set(doc['files']) != expected:
            raise ValueError('Missing or unexpected result files')
        for name, meta in doc['files'].items():
            data = archive.read(name)
            if len(data) != meta['size'] or hashlib.sha256(data).hexdigest() != meta['sha256']:
                raise ValueError('Result checksum mismatch: ' + name)
        report = json.loads(archive.read(prefix + '.report.json'))
        if report.get('source_status_counts') != {'complete': 1} or report.get('records') != doc['records']:
            raise ValueError('Incomplete or inconsistent extraction report')
    return doc


def prepare(campaign, start, stop, input_path='flash/data/LNF'):
    campaign = campaign.resolve()
    campaign.mkdir(parents=True, exist_ok=True)
    manifest_path = campaign / 'campaign.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if (manifest['start'], manifest['stop'], manifest['input_path']) != (start, stop, input_path):
            raise ValueError('Campaign already exists with a different range or input')
        return manifest
    if start < 0 or stop < start or not re.fullmatch(r'[A-Za-z0-9_./-]+', input_path) or '..' in Path(input_path).parts:
        raise ValueError('Invalid run range or input path')
    source_dir = campaign / 'sources'
    source_dir.mkdir(exist_ok=True)
    hashes = {}
    for name in ('extract_thermometers.py', 'thermometers_batch.py', 'thermometers_job.sh'):
        source = Path(__file__).resolve().parent / name
        target = source_dir / name
        shutil.copy2(source, target)
        hashes[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    tag = f'thermometers-{start:05d}-{stop:05d}-' + hashlib.sha256(str(campaign).encode()).hexdigest()[:8]
    for run in range(start, stop + 1):
        directory = campaign / f'{run:05d}'
        directory.mkdir(exist_ok=True)
        shutil.copy2(source_dir / 'thermometers_job.sh', directory / 'script.sh')
        (directory / 'script.sh').chmod(0o755)
        (directory / 'submit.sub').write_text(f'''executable = script.sh
arguments = {input_path} {run}
output = stdout-$(ClusterId).$(ProcID).txt
error = stderr-$(ClusterId).$(ProcID).txt
log = output-$(ClusterId).$(ProcID).log
request_cpus = 1
request_memory = 2GB
request_disk = 40GB
transfer_executable = Yes
transfer_input_files = ../sources/extract_thermometers.py,../sources/thermometers_batch.py
transfer_output_files = results
should_transfer_files = Yes
when_to_transfer_output = ON_EXIT
want_io_proxy = true
use_oauth_services = t1
t1_oauth_permissions = profile,email,openid,offline_access
on_exit_hold = (ExitBySignal == True) || (ExitCode != 0)
+JobBatchName = "{tag}"
+ThermometerRun = {run}
queue
''')
        state_path = directory / 'job_state.json'
        if not state_path.exists():
            save_json(state_path, {'run': run, 'status': 'prepared', 'created_utc': now()})
    manifest = {'format': FORMAT, 'start': start, 'stop': stop, 'input_path': input_path,
                'tag': tag, 'source_sha256': hashes, 'created_utc': now()}
    save_json(manifest_path, manifest)
    return manifest


def states(campaign, manifest):
    return {run: json.loads((campaign / f'{run:05d}' / 'job_state.json').read_text())
            for run in range(manifest['start'], manifest['stop'] + 1)}


def cycle(campaign, manifest, max_active, submit=False):
    jobs = json.loads(execute(['condor_q', '-json', '-constraint', f'JobBatchName == "{manifest["tag"]}"',
        '-attributes', 'ClusterId,JobStatus,HoldReason,ThermometerRun']) or '[]')
    by_run = {}
    for job in jobs:
        if 'ThermometerRun' in job:
            run = int(job['ThermometerRun'])
            if run not in by_run or job['ClusterId'] > by_run[run]['ClusterId']:
                by_run[run] = job
    current = states(campaign, manifest)
    for run, state in current.items():
        directory = campaign / f'{run:05d}'
        if state['status'] == 'complete':
            continue
        if run in by_run:
            state['cluster'] = int(by_run[run]['ClusterId'])
            state['status'] = 'submitted'
        if 'cluster' not in state:
            continue
        result = bundle_path(campaign, run)
        job = by_run.get(run)
        if not result.exists():
            if job and job['JobStatus'] == 5:
                state.update(status='failed', error=job.get('HoldReason', 'Job held'))
            elif job and job['JobStatus'] == 4:
                try:
                    execute(['condor_transfer_data', str(state['cluster'])], cwd=directory)
                except RuntimeError as exc:
                    state['recovery_error'] = str(exc)
            elif not job:
                history = json.loads(execute(['condor_history', str(state['cluster']), '-limit', '1', '-json',
                    '-attributes', 'JobStatus,ExitCode,HoldReason']) or '[]')
                if history and history[0].get('JobStatus') in (3, 5):
                    state.update(status='failed', error=str(history[0]))
                elif history and history[0].get('JobStatus') == 4:
                    try:
                        execute(['condor_transfer_data', str(state['cluster'])], cwd=directory)
                    except RuntimeError as exc:
                        state['recovery_error'] = str(exc)
        if result.exists():
            try:
                doc = validate_bundle(result, run)
                state.update(status='complete', records=doc['records'], completed_utc=now())
            except Exception as exc:
                state.update(status='failed', error=str(exc))
        save_json(directory / 'job_state.json', state)
    failures = [run for run, state in current.items() if state['status'] == 'failed']
    # Keep slots occupied for submitted jobs temporarily absent from condor_q;
    # an eventual-consistency gap must not create excess submissions.
    visible_clusters = {int(job['ClusterId']) for job in jobs}
    active = sum(job['JobStatus'] in (1, 2, 4, 5, 6, 7) for job in jobs)
    active += sum(state['status'] == 'submitted' and state.get('cluster') not in visible_clusters
                  for state in current.values())
    if submit and not failures:
        for run, state in current.items():
            if active >= max_active:
                break
            if state['status'] != 'prepared':
                continue
            directory = campaign / f'{run:05d}'
            try:
                response = execute(['condor_submit', '-spool', '-terse', 'submit.sub'], cwd=directory)
                (directory / 'submission.log').write_text(response)
                match = re.match(r'\s*(\d+)\.', response)
                if not match:
                    raise ValueError('Unexpected condor_submit response: ' + response)
                state.update(status='submitted', cluster=int(match[1]), submitted_utc=now())
                save_json(directory / 'job_state.json', state)
                active += 1
                print(f'Run {run}: submitted cluster {state["cluster"]}', flush=True)
            except Exception as exc:
                state.update(status='failed', error=str(exc))
                save_json(directory / 'job_state.json', state)
                failures.append(run)
                break
    summary = {'counts': dict(Counter(state['status'] for state in current.values())),
               'failed_runs': failures, 'updated_utc': now(), 'max_active': max_active}
    save_json(campaign / 'status.json', summary)
    print(json.dumps(summary), flush=True)
    return summary


def retry(campaign, manifest, chosen=None):
    current = states(campaign, manifest)
    targets = [chosen] if chosen is not None else [r for r, state in current.items() if state['status'] == 'failed']
    for run in targets:
        if run not in current or current[run]['status'] != 'failed':
            raise ValueError('Only failed campaign runs can be retried')
        state = current[run]
        if 'cluster' in state:
            jobs = json.loads(execute(['condor_q', str(state['cluster']), '-json',
                '-attributes', 'ClusterId,JobBatchName,ThermometerRun,JobStatus']) or '[]')
            for job in jobs:
                if job.get('JobBatchName') != manifest['tag'] or job.get('ThermometerRun') != run:
                    raise ValueError('Refusing to alter a job outside this campaign')
            if jobs:
                execute(['condor_rm', str(state['cluster'])])
        directory = campaign / f'{run:05d}'
        archive = directory / '_attempts' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        archive.mkdir(parents=True)
        shutil.copy2(directory / 'job_state.json', archive / 'job_state.json')
        if (directory / 'results').exists():
            shutil.move(str(directory / 'results'), archive / 'results')
        save_json(directory / 'job_state.json', {'run': run, 'status': 'prepared',
            'previous_cluster': state.get('cluster'), 'retry_utc': now()})
        print(f'Run {run}: failed attempt archived, ready to retry', flush=True)


def merge(campaign, manifest):
    runs = list(range(manifest['start'], manifest['stop'] + 1))
    # Validate everything before replacing any previously published local CSV.
    for run in runs:
        validate_bundle(bundle_path(campaign, run), run)
    output = campaign / f'thermometers_{runs[0]:05d}_{runs[-1]:05d}.csv'
    with (campaign / 'merge.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with tempfile.TemporaryDirectory(prefix='merge-', dir=campaign) as temporary:
            temporary = Path(temporary)
            db_path = temporary / 'merged.sqlite'
            connection = sqlite3.connect(str(db_path))
            try:
                extractor.initialize(connection)
                total = 0
                for run in runs:
                    path = bundle_path(campaign, run)
                    doc = validate_bundle(path, run)
                    source_db = temporary / 'input.sqlite'
                    with ZipFile(path) as archive:
                        source_db.write_bytes(archive.read(f'run{run:05d}.sqlite'))
                    source = sqlite3.connect(str(source_db))
                    try:
                        if source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                            raise ValueError(f'Invalid SQLite result for run {run}')
                        rows = source.execute('SELECT DISTINCT run FROM readings').fetchall()
                        if any(row[0] != run for row in rows):
                            raise ValueError(f'Mismatched run in extracted observations: {run}')
                        for schema_id, document in source.execute('SELECT id,document FROM schemas'):
                            connection.execute('INSERT OR IGNORE INTO schemas VALUES(?,?)', (schema_id, document))
                        sources = source.execute('SELECT id,size,mtime_ns,config,status,error,events_scanned FROM sources').fetchall()
                        if len(sources) != 1 or sources[0][4] != 'complete':
                            raise ValueError(f'Incomplete source database for run {run}')
                        old_id, *attributes = sources[0]
                        new_id = connection.execute('''INSERT INTO sources
                            (path,size,mtime_ns,config,status,error,events_scanned) VALUES(?,?,?,?,?,?,?)''',
                            (doc['input_url'], *attributes)).lastrowid
                        connection.execute('INSERT INTO selected_sources VALUES(?)', (doc['input_url'],))
                        records = list(source.execute('''SELECT ordinal,run,timestamp,event_id,serial,bank,schema_id,values_json
                            FROM readings WHERE file_id=?''', (old_id,)))
                        if len(records) != doc['records']:
                            raise ValueError(f'Record count mismatch for run {run}')
                        connection.executemany('''INSERT INTO readings
                            (file_id,ordinal,run,timestamp,event_id,serial,bank,schema_id,values_json)
                            VALUES(?,?,?,?,?,?,?,?,?)''', [(new_id, *row) for row in records])
                        total += len(records)
                    finally:
                        source.close()
                connection.commit()
                report = extractor.export(connection, temporary / output.name)
                if report['records'] != total:
                    raise ValueError('Merged record count mismatch')
            finally:
                connection.close()
            for suffix in ('.schema.json', '.report.json', '.csv'):
                source_path = (temporary / output.name).with_suffix(suffix)
                os.replace(source_path, output.with_suffix(suffix))
            os.replace(db_path, output.with_suffix('.sqlite'))
    save_json(campaign / 'merge_status.json', {'status': 'complete', 'runs': len(runs),
        'records': total, 'csv': str(output), 'completed_utc': now()})
    print(f'Merged {len(runs)} runs, {total} observations: {output}', flush=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'watch', 'status', 'merge', 'pack', 'retry'])
    parser.add_argument('--campaign-dir', type=Path, default=DEFAULT_CAMPAIGN)
    parser.add_argument('--run-range', nargs=2, type=int, default=(680, 939))
    parser.add_argument('--input-path', default='flash/data/LNF')
    parser.add_argument('--max-active', type=int, default=4)
    parser.add_argument('--poll-seconds', type=int, default=60)
    parser.add_argument('--submit', action='store_true')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--run', type=int)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--input-url')
    parser.add_argument('--exit-code', type=int, default=0)
    args = parser.parse_args()
    if args.command == 'pack':
        if None in (args.run, args.output, args.bundle, args.input_url):
            parser.error('pack requires --run, --output, --bundle and --input-url')
        pack(args.run, args.output, args.bundle, args.input_url, args.exit_code)
        return
    if args.max_active < 1 or args.poll_seconds < 1:
        parser.error('Concurrency and polling interval must be positive')
    campaign = args.campaign_dir.expanduser().resolve()
    if args.command == 'prepare':
        prepare(campaign, *args.run_range, args.input_path)
        print(campaign)
        return
    manifest = json.loads((campaign / 'campaign.json').read_text())
    if args.command == 'status':
        print(json.dumps({'counts': dict(Counter(s['status'] for s in states(campaign, manifest).values())),
                          'campaign': str(campaign)}, indent=2))
        return
    if args.command == 'merge':
        merge(campaign, manifest)
        return
    with (campaign / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.command == 'retry':
            retry(campaign, manifest, args.run)
            return
        for name, digest in manifest['source_sha256'].items():
            if hashlib.sha256((campaign / 'sources' / name).read_bytes()).hexdigest() != digest:
                raise ValueError('Campaign source snapshot changed: ' + name)
        while True:
            summary = cycle(campaign, manifest, args.max_active, args.submit)
            if summary['failed_runs']:
                raise SystemExit('Campaign stopped after a failure; see job_state.json and scheduler logs')
            if summary['counts'].get('complete', 0) == manifest['stop'] - manifest['start'] + 1:
                merge(campaign, manifest)
                return
            if args.once:
                return
            time.sleep(args.poll_seconds)


if __name__ == '__main__':
    main()
