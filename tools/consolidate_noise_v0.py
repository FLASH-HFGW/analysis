#!/usr/bin/env python3
"""Consolidate historical GPFS noise sidecars, preserving a verified local backup.

Stage first; publish verifies a fresh remote download before retiring originals.
FFT products are outside this migration. Different scientific schemas stay separate.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from functools import partial
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'examples'))
from iq_noise_io import build_results, save_results_h5, read_results_h5, flattened_arrays

REMOTE = 'davs://xfer-archive.cr.cnaf.infn.it:8443/flash/analysis/autoreco/Run2'
COLLECTIONS = ('noise_by_run', 'noise_by_run_continuous', 'noise_continuous', 'noise_global')


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def plan(root):
    jobs = []
    for collection in COLLECTIONS[:3]:
        base = root / collection
        used = set()
        for summary in sorted(base.rglob('run*_noise.json')):
            files = [summary.with_suffix('.npz'), summary,
                     summary.with_suffix('.png'), summary.with_name(summary.stem + '_iq.png')]
            if not all(p.is_file() for p in files):
                raise ValueError('Incomplete sidecars: ' + str(summary))
            used.update(files)
            parent = Path(collection) / 'by_run' if collection == 'noise_continuous' else Path(collection)
            jobs.append({'kind': 'run', 'sources': [str(p.relative_to(root)) for p in files],
                         'output': str(parent / (summary.stem + '_v0.h5'))})
        extras = sorted(p for p in base.rglob('*') if p.is_file() and p not in used
                        and not p.name.endswith('_v0.h5'))
        if extras:
            jobs.append({'kind': 'attachments', 'sources': [str(p.relative_to(root)) for p in extras],
                         'output': collection + '/noise_analysis_v0.h5'})
    extras = sorted(p for p in (root / 'noise_global').rglob('*') if p.is_file()
                    and not p.name.endswith('_v0.h5'))
    if extras:
        jobs.append({'kind': 'attachments', 'sources': [str(p.relative_to(root)) for p in extras],
                     'output': 'noise_global/noise_global_v0.h5'})
    return jobs


def stage_job(root, work, job):
    records = []
    for relative in job['sources']:
        source, backup = root / relative, work / 'originals' / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        content = source.read_bytes()
        checksum = hashlib.sha256(content).hexdigest()
        if backup.exists():
            if sha(backup) != checksum:
                raise ValueError('Backup/source mismatch: ' + relative)
        else:
            backup.write_bytes(content)
        records.append({'path': relative, 'bytes': len(content), 'sha256': checksum})
    paths = [work / 'originals' / r for r in job['sources']]
    if job['kind'] == 'run':
        summary_path = next(p for p in paths if p.suffix == '.json')
        summary = json.loads(summary_path.read_text())
        if summary.get('status') != 'success' or not summary.get('reached_eof'):
            raise ValueError('Incomplete reconstruction: ' + str(summary_path))
        with np.load(summary_path.with_suffix('.npz'), allow_pickle=False) as archive:
            arrays = {key: archive[key] for key in archive.files}
        result = build_results(summary, arrays)
        result['figures'] = {p.stem: {'format': 'png', 'data': np.frombuffer(p.read_bytes(), dtype=np.uint8)}
                             for p in paths if p.suffix == '.png'}
        # Preserve exact JSON text as well as its structured representation.
        result['original_metadata'] = {'filename': summary_path.name,
                                      'data': np.frombuffer(summary_path.read_bytes(), dtype=np.uint8)}
    else:
        result = build_results({}, {})
        result['attachments'] = {}
        for record, path in zip(records, paths):
            # Numeric keys avoid slashes in original file paths becoming HDF5 groups.
            result['attachments'][str(len(result['attachments']))] = {
                'path': record['path'], 'data': np.frombuffer(path.read_bytes(), dtype=np.uint8)}
    result['migration'] = {'tag': 'v0', 'operation': 'lossless packaging; no recomputation', 'sources': records}
    output = work / 'products' / job['output']
    output.parent.mkdir(parents=True, exist_ok=True)
    save_results_h5(output, result)
    restored = read_results_h5(output)
    if job['kind'] == 'run':
        np.testing.assert_equal(restored['summary'], summary)
        decoded = flattened_arrays(restored)
        if set(decoded) != set(arrays):
            raise ValueError('Changed array names')
        for key, value in arrays.items():
            np.testing.assert_equal(decoded[key], value, err_msg=key)
            if np.asarray(decoded[key]).dtype != value.dtype:
                raise ValueError('Changed dtype: ' + key)
        for key, figure in result['figures'].items():
            np.testing.assert_array_equal(restored['figures'][key]['data'], figure['data'])
        np.testing.assert_array_equal(restored['original_metadata']['data'], result['original_metadata']['data'])
    else:
        for key, attachment in result['attachments'].items():
            np.testing.assert_array_equal(restored['attachments'][key]['data'], attachment['data'])
    job.update(records=records, bytes=output.stat().st_size, sha256=sha(output))
    return job


def command(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, timeout=180)


def write_manifest(work, manifest):
    temporary = work / 'manifest.json.tmp'
    temporary.write_text(json.dumps(manifest, indent=2) + '\n')
    temporary.replace(work / 'manifest.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2'))
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--stage', action='store_true')
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--retire-originals', action='store_true')
    args = parser.parse_args()
    work = args.work.resolve(); work.mkdir(parents=True, exist_ok=True)
    manifest_path = work / 'manifest.json'
    if args.stage:
        jobs = plan(args.root)
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            if manifest['root'] != str(args.root) or manifest.get('staged_complete'):
                raise ValueError('Different root or staging already complete')
            done = {j['output']: j for j in manifest['jobs']}
            for job in jobs:
                if job['output'] in done:
                    previous = done[job['output']]
                    if job['sources'] != previous['sources'] or sha(work/'products'/job['output']) != previous['sha256']:
                        raise ValueError('Changed staging plan or product')
            jobs = [j for j in jobs if j['output'] not in done]
        else:
            manifest = {'root': str(args.root), 'tag': 'v0', 'jobs': [], 'created_unix': time.time()}
        total = len(manifest['jobs']) + len(jobs)
        print('Staging %d remaining containers (%d total)' % (len(jobs), total), flush=True)
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for job in pool.map(partial(stage_job, args.root, work), jobs):
                manifest['jobs'].append(job)
                write_manifest(work, manifest)
                index = len(manifest['jobs'])
                if index % 20 == 0 or index == total:
                    print('Staged and verified %d/%d' % (index, total), flush=True)
        manifest['staged_complete'] = True
        write_manifest(work, manifest)
    if args.publish or args.retire_originals:
        manifest = json.loads(manifest_path.read_text())
        if not manifest.get('staged_complete') or manifest['root'] != str(args.root):
            raise ValueError('Staging incomplete or source root changed')
        if args.publish:
            def publish(job):
                if job.get('remote_verified'):
                    return job
                source = work / 'products' / job['output']
                if sha(source) != job['sha256']:
                    raise ValueError('Staged product changed: ' + str(source))
                remote = REMOTE + '/' + job['output']
                exists = subprocess.run(['gfal-stat', remote], stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, timeout=60).returncode == 0
                returned = work / 'remote_checks' / job['output']
                returned.parent.mkdir(parents=True, exist_ok=True)
                returned.unlink(missing_ok=True)
                if not exists:
                    command('gfal-copy', '-p', '-K', 'ADLER32', source.as_uri(), remote)
                command('gfal-copy', remote, returned.as_uri())
                if sha(returned) != job['sha256']:
                    raise ValueError('Remote verification failed: ' + remote)
                returned.unlink()
                return job
            pending = [j for j in manifest['jobs'] if not j.get('remote_verified')]
            completed = len(manifest['jobs']) - len(pending)
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                for job in pool.map(publish, pending):
                    job['remote_verified'] = True
                    completed += 1
                    write_manifest(work, manifest)
                    if completed % 20 == 0 or completed == len(manifest['jobs']):
                        print('Published and downloaded/verified %d/%d' % (completed, len(manifest['jobs'])), flush=True)
        if args.retire_originals:
            if not all(j.get('remote_verified') for j in manifest['jobs']):
                raise ValueError('Not all containers have been remotely verified')
            # Verify all local backups and current originals before deleting any source.
            def check_sources(job):
                for record in job['records']:
                    if sha(work / 'originals' / record['path']) != record['sha256']:
                        raise ValueError('Local backup changed: ' + record['path'])
                    current = args.root / record['path']
                    if current.exists() and sha(current) != record['sha256']:
                        raise ValueError('Source changed: ' + str(current))
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                list(pool.map(check_sources, manifest['jobs']))
            print('All source and backup hashes verified; retiring legacy sidecars', flush=True)
            def retire(job):
                urls = [REMOTE + '/' + r['path'] for r in job['records']
                        if (args.root / r['path']).exists()]
                if urls:
                    command('gfal-rm', *urls)
                return job
            pending = [j for j in manifest['jobs'] if not j.get('retired')]
            completed = len(manifest['jobs']) - len(pending)
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                for job in pool.map(retire, pending):
                    job['retired'] = True
                    completed += 1
                    write_manifest(work, manifest)
                    if completed % 20 == 0 or completed == len(manifest['jobs']):
                        print('Retired originals %d/%d' % (completed, len(manifest['jobs'])), flush=True)
            # Only remove directories actually empty on the remote endpoint.
            removed = manifest.setdefault('removed_empty_directories', [])
            directories = sorted((p for c in COLLECTIONS for p in (args.root/c).rglob('*') if p.is_dir()),
                                 key=lambda p: len(p.parts), reverse=True)
            import gfal2
            context = gfal2.creat_context()
            for directory in directories:
                relative = str(directory.relative_to(args.root))
                listing = subprocess.run(['gfal-ls', REMOTE + '/' + relative], capture_output=True, text=True, timeout=60)
                if listing.returncode == 0 and not listing.stdout.strip():
                    context.rmdir(REMOTE + '/' + relative)  # Fails if nonempty; never recursive.
                    removed.append(relative)
                    write_manifest(work, manifest)
            print('Removed %d empty directories' % len(removed), flush=True)


if __name__ == '__main__':
    main()
