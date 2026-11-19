from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import run3_cycle as run3
import run3_storage as storage


class Run3CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        for target, options in (
            ("BASE", dict(new=self.base)),
            ("subprocess.check_output", dict(return_value="ext4\n")),
        ):
            mock = patch("run3_cycle." + target, **options)
            mock.start()
            self.addCleanup(mock.stop)
        self.run = self.base / "01148"
        self.state = dict(attempt="a"*32, phase="verified", verified_at=time.time(),
                          publication={"size": 100, "adler32": "12345678"})
        self.directory = self.run / self.state["attempt"] / "01148"
        self.directory.mkdir(parents=True)
        self.payload = self.directory / "script.sh"
        self.payload.touch()
        self.url = run3.PILOT + "/run01148_iq_v3.h5"

    def reconcile(self, source, jobs, *, dry_run=False, verify_error=None):
        with patch.object(run3, "lookup", return_value=(source, jobs)), \
             patch.object(run3, "verify", side_effect=verify_error), \
             patch.object(run3, "size", return_value=None):
            return run3.reconcile(self.run, self.state, 1148, self.url, 7, dry_run)

    def test_active_held_and_missing_history_preserve_artifacts(self):
        for code in (1, 2, 4, 5, 6, 7):
            self.assertTrue(self.reconcile("active", [dict(JobStatus=code)]))
        self.reconcile("history", [])
        self.assertTrue(self.payload.exists())

    def test_failed_remote_verification_preserves_payload(self):
        with self.assertRaises(ValueError):
            self.reconcile("history", [dict(JobStatus=4, ExitCode=0)],
                           verify_error=ValueError("bad checksum"))
        self.assertTrue(self.payload.exists())

    def test_verified_cleanup_dry_run_symlink_and_logging(self):
        target = self.base / "outside"
        target.touch()
        link = self.directory / "submit.sub"
        link.symlink_to(target)
        log = self.directory / "stdout-2.0.txt"
        log.touch()
        jobs = [dict(JobStatus=4, ExitCode=0)]
        self.reconcile("history", jobs, dry_run=True)
        self.assertTrue(self.payload.exists())
        self.reconcile("history", jobs)
        self.assertFalse(self.payload.exists())
        self.assertTrue(log.exists() and link.is_symlink() and target.exists())

    def test_failed_retention(self):
        self.state.update(phase="failed", failed_at=time.time())
        jobs = [dict(JobStatus=3)]
        self.reconcile("history", jobs)
        self.assertTrue(self.payload.exists())
        self.state["failed_at"] -= 8*86400
        self.reconcile("history", jobs)
        self.assertFalse(self.payload.exists())

    def test_directory_escape_rejected(self):
        self.directory.rename(self.base / "moved")
        self.directory.symlink_to(self.base / "moved", target_is_directory=True)
        with self.assertRaises(ValueError):
            run3.clean_attempt(self.directory, dry_run=False)
        self.assertTrue((self.base / "moved/script.sh").exists())


class PublicationTests(unittest.TestCase):
    def test_collision_probe(self):
        from urllib.parse import unquote, urlparse

        for overwrites in (True, False):
            with self.subTest(overwrites=overwrites), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "payload.h5"
                path.write_bytes(b"payload")
                final = storage.PILOT + "/run01148_iq_v3.h5"
                remote = {}

                def gfal(tool, *args, missing=False):
                    if tool == "mkdir":
                        return ""
                    if tool == "stat":
                        data = remote.get(args[0])
                        return None if data is None else f" Size: {len(data)}"
                    if tool == "copy":
                        remote[args[-1]] = Path(unquote(urlparse(args[-2]).path)).read_bytes()
                    if tool == "sum":
                        return f"{args[0]} {storage.zlib.adler32(remote[args[0]]):08x}"
                    if tool == "rename":
                        if not overwrites and args[1] in remote:
                            raise RuntimeError("already exists")
                        remote[args[1]] = remote.pop(args[0])
                    if tool == "rm":
                        del remote[args[0]]
                    return ""

                with patch.object(storage, "gfal", side_effect=gfal):
                    if overwrites:
                        with self.assertRaisesRegex(RuntimeError, "overwrites"):
                            storage.publish(path, final, probe=True)
                        self.assertEqual(remote, {})
                    else:
                        storage.publish(path, final, probe=True)
                        self.assertEqual(remote, {final: b"payload"})
                        path.write_bytes(b"different")
                        with self.assertRaises(ValueError):
                            storage.publish(path, final)
                        self.assertEqual(remote, {final: b"payload"})


if __name__ == "__main__":
    unittest.main()
