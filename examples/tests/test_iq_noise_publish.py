import hashlib
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
from urllib.parse import urlparse, unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import iq_noise_publish as transfer


class PublicationTests(unittest.TestCase):
    def fake_gfal(self, remote, calls, stat_error=None):
        def run(args, **kwargs):
            calls.append(args)
            if args[0] == 'oidc-token':
                return SimpleNamespace(returncode=0, stdout='private-test-token\n', stderr='')
            if args[0] == 'gfal-stat':
                return SimpleNamespace(returncode=stat_error if stat_error else (0 if args[-1] in remote else 2),
                                       stdout='', stderr='authentication failure' if stat_error else '')
            self.assertEqual(args[0], 'gfal-copy')
            source, target = args[-2:]
            content = Path(unquote(urlparse(source).path)).read_bytes() if source.startswith('file:') else remote[source]
            if target.startswith('file:'):
                Path(unquote(urlparse(target).path)).write_bytes(content)
            else:
                self.assertNotIn(target, remote, 'Existing remote file was overwritten')
                remote[target] = content
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        return run

    def test_publish_verifies_fresh_download_and_reuses_identical_remote(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'run00680_noise.h5'; source.write_bytes(b'scientific-result')
            remote={};calls=[];url='davs://example.invalid/pilot/run00680_noise.h5'
            with mock.patch.object(transfer.subprocess,'run',side_effect=self.fake_gfal(remote,calls)):
                first=transfer.publish(source,url,root/'checks')
                second=transfer.publish(source,url,root/'checks')
            self.assertEqual(first,second)
            self.assertEqual(first['sha256'],hashlib.sha256(source.read_bytes()).hexdigest())
            copies=[c for c in calls if c[0]=='gfal-copy']
            self.assertEqual(sum(c[-1]==url for c in copies),1)
            self.assertEqual(sum(c[-2]==url for c in copies),2)

    def test_remote_conflict_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'result.h5';source.write_bytes(b'new')
            url='davs://example.invalid/pilot/result.h5';remote={url:b'old'};calls=[]
            with mock.patch.object(transfer.subprocess,'run',side_effect=self.fake_gfal(remote,calls)):
                with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):
                    transfer.publish(source,url,root/'checks')
            self.assertEqual(remote[url],b'old')
            self.assertFalse(any(c[0]=='gfal-copy' and c[-1]==url for c in calls))

    def test_authentication_error_is_not_treated_as_missing_remote(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'result.h5';source.write_bytes(b'result');calls=[]
            with mock.patch.object(transfer.subprocess,'run',side_effect=self.fake_gfal({},calls,stat_error=13)):
                with self.assertRaisesRegex(RuntimeError,'Cannot inspect destination'):
                    transfer.publish(source,'davs://example.invalid/result.h5',root/'checks')
            self.assertFalse(any(c[0]=='gfal-copy' for c in calls))

    def test_fetch_requires_the_pinned_checksum_and_cleans_partial_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'inputs.h5';url='davs://example.invalid/inputs.h5'
            with mock.patch.object(transfer.subprocess,'run',side_effect=self.fake_gfal({url:b'inputs'},[])):
                with self.assertRaisesRegex(ValueError,'pinned SHA-256'):
                    transfer.fetch(url,target,'wrong')
                self.assertFalse(target.exists())
                self.assertFalse(target.with_suffix('.h5.part').exists())
                transfer.fetch(url,target,hashlib.sha256(b'inputs').hexdigest())
            self.assertEqual(target.read_bytes(),b'inputs')


if __name__ == '__main__':
    unittest.main()
