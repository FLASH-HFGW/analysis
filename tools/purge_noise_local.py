#!/usr/bin/env python3
"""Plan or apply bounded cleanup of published noise campaigns; default is dry-run.

Never scans raw inputs, snapshots, presentations, arbitrary scratch directories
or GPFS for deletion. Keeps all manifests, frozen sources, states and receipts.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'examples'))


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path,value):
    if path.is_symlink():raise ValueError('Symlink metadata forbidden: '+str(path))
    with tempfile.NamedTemporaryFile(mode='w',prefix=path.name+'.',suffix='.tmp',dir=path.parent,delete=False) as stream:
        temporary=Path(stream.name)
        stream.write(json.dumps(value,indent=2)+'\n')
    try:temporary.replace(path)
    finally:temporary.unlink(missing_ok=True)


def now():
    return datetime.now(timezone.utc).isoformat()


def local(path,roots):
    """Reject symlinks, repository contents and paths outside explicit local roots."""
    path=Path(path).absolute()
    if not any(path.is_relative_to(r.resolve()) for r in roots):
        raise ValueError('Outside local cleanup roots: '+str(path))
    for parent in (path,*path.parents):
        if parent.is_symlink():raise ValueError('Symlink cleanup forbidden: '+str(parent))
        if (parent/'.git').exists():raise ValueError('Repository cleanup forbidden: '+str(path))
    # Explicit local roots do not authorize deleting from mounted scientific storage.
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        fields=line.split();mount=Path(fields[4].replace('\\040',' '))
        filesystem=line.split(' - ',1)[1].split()[0]
        if path.is_relative_to(mount) and (filesystem.startswith('fuse') or filesystem=='gpfs'):
            raise ValueError('Scientific/FUSE mount cleanup forbidden: '+str(path))
    return path


@contextmanager
def exclusive(campaign):
    if (campaign/'watch.lock').is_symlink():raise ValueError('Symlink monitor lock forbidden')
    with (campaign/'watch.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Campaign monitor is active; cleanup/restore refused: '+str(campaign))
        yield


def receipt_ok(receipt,url,sha):
    return (isinstance(receipt,dict) and receipt.get('url')==url and receipt.get('sha256')==sha
            and isinstance(sha,str) and re.fullmatch('[0-9a-f]{64}',sha) is not None)


def plan(campaign,roots,retire=False):
    campaign=local(campaign,roots)
    manifest=read(campaign/'manifest.json')
    output=local(Path(manifest['output']),roots)
    version=manifest.get('product_version')
    if version not in ('v1','v2'):raise ValueError('Only versioned v1/v2 campaigns are supported')
    remote=manifest.get('gpfs_url','').rstrip('/')
    if not remote.startswith('davs://'):raise ValueError('Need explicit GPFS DAVS destination')
    scheduler='slurm' if manifest.get('scheduler')=='slurm' else 'htcondor'
    states={r:read(campaign/f'run{r:05d}.json' if scheduler=='slurm' else campaign/f'{r:05d}/state.json')
            for r in manifest['runs']}
    result=dict(campaign=str(campaign),output=str(output),retire_requested=retire,
                finished=all(s['status']=='complete' for s in states.values()),
                candidates=[],skipped=[],blockers=[])
    def skip(path,reason):result['skipped'].append(dict(path=str(path),reason=reason))
    def add(path,kind,url=None,expected=None):
        path=local(path,roots)
        if not path.exists():return
        if not path.is_file():raise ValueError('Expected a regular file: '+str(path))
        value=digest(path)
        if expected and kind!='log' and value!=expected:
            skip(path,'Local hash differs from publication receipt')
            result['blockers'].append(str(path)+': local hash differs from GPFS receipt');return
        st=path.stat()
        result['candidates'].append(dict(path=str(path),kind=kind,sha256=value,bytes=st.st_size,
                                         mtime_ns=st.st_mtime_ns,device=st.st_dev,inode=st.st_ino,
                                         url=url,remote_sha256=expected))
    for run,state in states.items():
        if state['status']!='complete':
            skip(campaign/f'run{run:05d}', 'Run is not complete: '+state['status']);continue
        url=remote+f'/run{run:05d}_noise_{version}.h5'
        sha=state.get('sha256')
        if not receipt_ok(state.get('gpfs'),url,sha):
            skip(campaign/f'run{run:05d}','Missing or inconsistent verified GPFS receipt')
            if retire:result['blockers'].append(f'run{run:05d}: missing GPFS receipt')
            continue
        name=f'run{run:05d}_noise'+('_v2' if version=='v2' else '')+'.h5'
        job=None
        if scheduler=='slurm' and isinstance(state.get('job_id'),int):
            job=output/'jobs'/f'JOB_{state["job_id"]}'
            add(job/name,'job_product',url,sha)
            add(job/'analysis.log','log',url,sha)
        elif scheduler=='htcondor' and isinstance(state.get('cluster'),int):
            job=campaign/f'{run:05d}'
            add(job/'results'/name,'job_product',url,sha)
            for prefix in ('stdout','stderr','output'):
                suffix='.log' if prefix=='output' else '.txt'
                path=job/f'{prefix}-{state["cluster"]}.0{suffix}'
                add(path,'log',url,sha)
        # Active campaigns still need their canonical inputs for final aggregation.
        if retire and result['finished']:add(output/name,'campaign_product',url,sha)
    if retire:
        if not result['finished']:result['blockers'].append('Campaign is not entirely complete')
        receipt_path=campaign/'gpfs_comparison.json'
        receipt=read(receipt_path) if receipt_path.exists() else {}
        url=remote+f'/noise_temperature_comparison_{version}.h5'
        sha=receipt.get('sha256')
        if not receipt_ok(receipt,url,sha):
            result['blockers'].append('Missing verified final-comparison receipt')
        elif result['finished']:
            comparison=output/('noise_temperature_comparison_v2.h5' if version=='v2' else 'noise_temperature_comparison.h5')
            add(comparison,'comparison',url,sha)
    result['counts']=dict(Counter(c['kind'] for c in result['candidates']))
    result['candidate_bytes']=sum(c['bytes'] for c in result['candidates'])
    return result


def verify_remote(url,sha):
    # Read-only download. fetch never publishes, overwrites or deletes remotely.
    from iq_noise_publish import fetch
    with tempfile.TemporaryDirectory(prefix='noise-purge-verify-') as directory:
        fetch(url,Path(directory)/'verified.h5',sha)


def unchanged(candidate,roots):
    path=local(Path(candidate['path']),roots)
    st=path.stat()
    if (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)!=(candidate['device'],candidate['inode'],candidate['bytes'],candidate['mtime_ns']):
        raise RuntimeError('File changed during cleanup planning: '+str(path))
    if digest(path)!=candidate['sha256']:raise RuntimeError('File hash changed: '+str(path))
    return path


def compact_log(path,expected):
    """Lossless archive; preserve log bytes, library versions, timestamps and errors."""
    if path.stat().st_size==0:
        if expected!=hashlib.sha256(b'').hexdigest():raise ValueError('Empty log hash mismatch')
        path.unlink()
        return None
    archive=path.with_name(path.name+'.gz')
    if archive.is_symlink():raise ValueError('Symlink log archive forbidden')
    if archive.exists():
        with gzip.open(archive,'rb') as stream:
            if hashlib.sha256(stream.read()).hexdigest()!=expected:
                raise ValueError('Existing compressed log differs: '+str(archive))
    else:
        with tempfile.NamedTemporaryFile(prefix=archive.name+'.',suffix='.tmp',dir=path.parent,delete=False) as stream:
            temporary=Path(stream.name)
        try:
            with path.open('rb') as source,temporary.open('wb') as target:
                with gzip.GzipFile(filename='',fileobj=target,mode='wb',mtime=0) as packed:
                    for block in iter(lambda:source.read(1024*1024),b''):packed.write(block)
            with gzip.open(temporary,'rb') as stream:
                if hashlib.sha256(stream.read()).hexdigest()!=expected:raise ValueError('Log compression mismatch')
            temporary.replace(archive)
        finally:temporary.unlink(missing_ok=True)
    if digest(path)!=expected:raise RuntimeError('Log changed while compressing')
    path.unlink()
    return str(archive)


def apply(campaign,roots,retire=False,verifier=verify_remote):
    campaign=local(campaign,roots)
    with exclusive(campaign):
        proposed=plan(campaign,roots,retire)
        if proposed['blockers']:raise ValueError('Cleanup blocked: '+str(proposed['blockers']))
        verified=set()
        for candidate in proposed['candidates']:
            pair=(candidate['url'],candidate['remote_sha256'])
            if pair not in verified:verifier(*pair);verified.add(pair)
        for candidate in proposed['candidates']:unchanged(candidate,roots)
        ledger_path=local(campaign/'local_retention.json',roots)
        ledger=read(ledger_path) if ledger_path.exists() else dict(schema='noise-local-retention-v1',entries=[])
        if retire:ledger['retired']=True
        # Persist recovery instructions before any deletion; safe after interruption.
        transaction=dict(created_utc=now(),retire=retire,candidates=proposed['candidates'])
        audit=campaign/'purge_audit';audit.mkdir(exist_ok=True)
        local(audit,roots)
        save(audit/('plan-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json'),transaction)
        save(ledger_path,ledger)
        for candidate in proposed['candidates']:
            path=unchanged(candidate,roots)
            entry=dict(candidate,planned_utc=now(),action='compress' if candidate['kind']=='log' else 'delete')
            ledger['entries'].append(entry);save(ledger_path,ledger)
            if candidate['kind']=='log':entry['archive']=compact_log(path,candidate['sha256'])
            else:path.unlink()
            entry['completed_utc']=now();save(ledger_path,ledger)
        return proposed


def restore(campaign,roots,fetcher=None):
    if fetcher is None:
        from iq_noise_publish import fetch as fetcher
    campaign=local(campaign,roots)
    with exclusive(campaign):
        ledger_path=local(campaign/'local_retention.json',roots);ledger=read(ledger_path)
        restored=[]
        for entry in ledger['entries']:
            if entry['kind'] not in ('campaign_product','comparison'):continue
            path=local(Path(entry['path']),roots)
            if path.exists():
                if digest(path)!=entry['sha256']:raise ValueError('Refusing to overwrite a changed product: '+str(path))
            else:
                path.parent.mkdir(parents=True,exist_ok=True)
                fetcher(entry['url'],path,entry['sha256'])
                if digest(path)!=entry['sha256']:raise ValueError('Restore checksum mismatch')
            restored.append(str(path))
        ledger['retired']=False;ledger['restored_utc']=now();save(ledger_path,ledger)
        return dict(restored=restored)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',required=True,type=Path)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--apply',action='store_true')
    mode.add_argument('--restore',action='store_true')
    parser.add_argument('--retire',action='store_true',help='Also evict canonical HDF5 caches after complete verified publication')
    parser.add_argument('--verify-remote',action='store_true',help='Fresh SHA-256 remote verification even in dry-run')
    parser.add_argument('--local-root',action='append',type=Path,help='Allowed local root (default: ~/HFGW); never GPFS/FUSE or a repository')
    parser.add_argument('--report',type=Path,help='Write the complete dry-run/action report as JSON')
    args=parser.parse_args();roots=args.local_root or [Path.home()/'HFGW']
    try:
        if args.report:
            target=local(args.report,roots)
            if target.suffix!='.json' or target.exists():
                raise ValueError('--report must name a new JSON file, never an existing file')
        if args.restore:
            if args.retire:parser.error('--restore cannot be combined with --retire')
            result=restore(args.campaign,roots)
        elif args.apply:result=apply(args.campaign,roots,args.retire)
        else:
            result=plan(args.campaign,roots,args.retire)
            if args.verify_remote:
                for url,sha in {(c['url'],c['remote_sha256']) for c in result['candidates']}:verify_remote(url,sha)
            result['dry_run']=True
        if args.report:
            target.parent.mkdir(parents=True,exist_ok=True);save(target,result)
        print(json.dumps({k:v for k,v in result.items() if k not in ('candidates','skipped')},indent=2))
        if result.get('skipped'):print('Skipped/protected:',len(result['skipped']))
    except (ValueError,RuntimeError,OSError) as exc:
        parser.exit(1,str(exc)+'\n')


if __name__=='__main__':main()
