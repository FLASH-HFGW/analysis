"""Destructive cleanup is bounded, verified, recoverable and controller-aware."""
import fcntl
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'examples'))
import purge_noise_local as purge
from noise_temperature_pilot import require_local_products


class PurgeTests(unittest.TestCase):
    def fixture(self,root,scheduler='htcondor',finished=True,version='v2'):
        c=root/'runtime/campaign';o=root/'work/results'
        (c/'sources').mkdir(parents=True);o.mkdir(parents=True)
        (c/'sources/noise_calibration.json').write_text('frozen calibration')
        (c/'sources/analysis.py').write_text('frozen source')
        manifest=dict(runs=[680],product_version=version,gpfs_url='davs://example/science',output=str(o))
        if scheduler=='slurm':manifest['scheduler']='slurm'
        (c/'manifest.json').write_text(json.dumps(manifest))
        payload=b'validated scientific contents'
        sha=hashlib.sha256(payload).hexdigest()
        url=f'davs://example/science/run00680_noise_{version}.h5'
        state=dict(run=680,status='complete' if finished else 'submitted',sha256=sha,
                   gpfs=dict(url=url,sha256=sha,bytes=len(payload)))
        if scheduler=='slurm':
            state['job_id']=500;job=o/'jobs/JOB_500';statefile=c/'run00680.json'
        else:
            state['cluster']=500;job=c/'00680/results';statefile=c/'00680/state.json'
        job.mkdir(parents=True)
        statefile.write_text(json.dumps(state))
        duplicate=job/('run00680_noise_v2.h5' if version=='v2' else 'run00680_noise.h5');duplicate.write_bytes(payload)
        canonical=o/duplicate.name;canonical.write_bytes(payload)
        log=job/'analysis.log' if scheduler=='slurm' else c/'00680/stdout-500.0.txt'
        log.write_text('Python and library versions\nDownload run00680 2026-11-09T10:00:00Z\n')
        (c/'watch.log').write_text('controller state history')
        comparison=o/('noise_temperature_comparison_v2.h5' if version=='v2' else 'noise_temperature_comparison.h5');comparison.write_bytes(b'complete comparison')
        cmp_sha=purge.digest(comparison)
        (c/'gpfs_comparison.json').write_text(json.dumps(dict(url=f'davs://example/science/noise_temperature_comparison_{version}.h5',sha256=cmp_sha)))
        return c,o,duplicate,canonical,log,comparison

    def test_default_plan_is_read_only_and_preserves_reproduction_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);c,o,duplicate,canonical,log,_=self.fixture(root)
            p=purge.plan(c,[root])
            self.assertEqual(p['counts'],dict(job_product=1,log=1))
            self.assertTrue(duplicate.exists());self.assertTrue(log.exists())
            self.assertNotIn(str(canonical),[a['path'] for a in p['candidates']])
            self.assertFalse((c/'local_retention.json').exists())

    def test_verified_duplicates_removed_and_log_archive_is_lossless(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);c,o,duplicate,canonical,log,_=self.fixture(root)
            before=log.read_bytes();verified=[]
            purge.apply(c,[root],verifier=lambda *pair:verified.append(pair))
            self.assertEqual(len(verified),1)
            self.assertFalse(duplicate.exists());self.assertTrue(canonical.exists())
            self.assertFalse(log.exists())
            with gzip.open(log.with_name(log.name+'.gz'),'rb') as source:self.assertEqual(source.read(),before)
            self.assertTrue((c/'sources/analysis.py').exists());self.assertTrue((c/'manifest.json').exists())
            self.assertTrue((c/'gpfs_comparison.json').exists())
            require_local_products(c)

    def test_remote_verification_failure_deletes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);c,o,duplicate,canonical,log,_=self.fixture(root)
            def fail(*args):raise RuntimeError('remote hash differs / unavailable')
            with self.assertRaisesRegex(RuntimeError,'remote hash'):
                purge.apply(c,[root],verifier=fail)
            self.assertTrue(duplicate.exists());self.assertTrue(canonical.exists());self.assertTrue(log.exists())

    def test_retire_requires_complete_campaign_and_verified_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);c,o,duplicate,canonical,log,_=self.fixture(root,finished=False)
            with self.assertRaisesRegex(ValueError,'not entirely complete'):
                purge.apply(c,[root],retire=True,verifier=lambda *args:None)
            self.assertTrue(duplicate.exists());self.assertTrue(log.exists())
            state=c/'00680/state.json';s=json.loads(state.read_text());s['status']='complete';state.write_text(json.dumps(s))
            (c/'gpfs_comparison.json').unlink()
            with self.assertRaisesRegex(ValueError,'final-comparison'):
                purge.apply(c,[root],retire=True,verifier=lambda *args:None)
            self.assertTrue(canonical.exists())

    def test_retired_canonical_products_can_be_restored_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);c,o,duplicate,canonical,log,comparison=self.fixture(root)
            contents={purge.digest(p):p.read_bytes() for p in (canonical,comparison)}
            purge.apply(c,[root],retire=True,verifier=lambda *args:None)
            self.assertFalse(canonical.exists());self.assertFalse(comparison.exists())
            with self.assertRaisesRegex(RuntimeError,'--restore'):require_local_products(c)
            restored=purge.restore(c,[root],fetcher=lambda url,path,sha:path.write_bytes(contents[sha]))
            self.assertEqual(len(restored['restored']),2)
            self.assertEqual(canonical.read_bytes(),contents[purge.digest(canonical)])
            self.assertFalse(duplicate.exists())
            require_local_products(c)

    def test_active_monitor_prevents_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);c,o,duplicate,canonical,log,_=self.fixture(root)
            with (c/'watch.lock').open('w') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaisesRegex(RuntimeError,'monitor is active'):
                    purge.apply(c,[root],verifier=lambda *args:None)
            self.assertTrue(duplicate.exists());self.assertTrue(log.exists())

    def test_mismatched_local_content_and_symlinks_are_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);c,o,duplicate,canonical,log,_=self.fixture(root)
            duplicate.write_bytes(b'changed scientific data')
            with self.assertRaisesRegex(ValueError,'hash differs'):
                purge.apply(c,[root],verifier=lambda *args:None)
            duplicate.unlink();duplicate.symlink_to(canonical)
            with self.assertRaisesRegex(ValueError,'Symlink'):
                purge.plan(c,[root])
            self.assertTrue(canonical.exists())

    def test_hpc_layout_retains_job_status_and_canonical_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);c,o,duplicate,canonical,log,_=self.fixture(root,scheduler='slurm')
            status=duplicate.parent/'job_status.json';status.write_text('{"exit_code":0}')
            purge.apply(c,[root],verifier=lambda *args:None)
            self.assertFalse(duplicate.exists());self.assertTrue(status.exists());self.assertTrue(canonical.exists())

    def test_missing_publication_receipt_and_repository_are_never_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);c,o,duplicate,canonical,log,_=self.fixture(root)
            state=c/'00680/state.json';s=json.loads(state.read_text());s.pop('gpfs');state.write_text(json.dumps(s))
            self.assertEqual(purge.plan(c,[root])['candidates'],[])
            repo=root/'repo';repo.mkdir();(repo/'.git').mkdir();p=repo/'run00680_noise_v2.h5';p.write_bytes(b'protected')
            with self.assertRaisesRegex(ValueError,'Repository'):purge.local(p,[root])

    def test_v1_unversioned_local_filename_uses_versioned_remote_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);c,o,duplicate,canonical,log,_=self.fixture(root,version='v1')
            p=purge.plan(c,[root])
            product=next(a for a in p['candidates'] if a['kind']=='job_product')
            self.assertEqual(Path(product['path']).name,'run00680_noise.h5')
            self.assertTrue(product['url'].endswith('/run00680_noise_v1.h5'))

    def test_empty_logs_are_removed_without_creating_an_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);c,o,duplicate,canonical,log,_=self.fixture(root)
            log.write_bytes(b'')
            purge.apply(c,[root],verifier=lambda *args:None)
            self.assertFalse(log.exists());self.assertFalse(log.with_name(log.name+'.gz').exists())

    def test_file_changed_during_remote_verification_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);c,o,duplicate,canonical,log,_=self.fixture(root)
            def changed(*args):duplicate.write_bytes(b'changed while the remote copy was checked')
            with self.assertRaisesRegex(RuntimeError,'changed during'):
                purge.apply(c,[root],verifier=changed)
            self.assertTrue(duplicate.exists());self.assertTrue(log.exists())

    def test_explicit_local_root_does_not_allow_a_fuse_mount(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            mount=f'12 1 0:12 / {root}/mounted rw - fuse.rclone flash rw\n'
            with mock.patch.object(purge.Path,'read_text',return_value=mount):
                with self.assertRaisesRegex(ValueError,'mount cleanup forbidden'):
                    purge.local(root/'mounted/product.h5',[root])


if __name__=='__main__':unittest.main()
