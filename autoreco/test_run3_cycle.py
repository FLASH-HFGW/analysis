import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch

import run3_cycle as run3
import run3_storage as storage
from noise_jobs import check_run3_inputs


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
                          publication={"size": 100, "local_adler32": "12345678"})
        self.directory = self.run / self.state["attempt"] / "01148"
        self.directory.mkdir(parents=True)
        self.payload = self.directory / "script.sh"
        self.payload.touch()
        self.url = run3.PILOT + "/run01148_iq_v3.h5"

    def reconcile(self, source, jobs, *, dry_run=False):
        with patch.object(run3, "lookup", return_value=(source, jobs)):
            return run3.reconcile(self.run, self.state, 1148, self.url, 7, dry_run)

    def test_active_held_and_missing_history_preserve_artifacts(self):
        for code in (1, 2, 4, 5, 6, 7):
            self.assertTrue(self.reconcile("active", [dict(JobStatus=code)]))
        self.reconcile("history", [])
        self.assertTrue(self.payload.exists())

    def test_completed_spooled_job_retrieves_operational_receipts_once(self):
        jobs = [dict(JobStatus=4, ExitCode=0, ClusterId=123)]
        self.state["phase"] = "submitted"
        with patch.object(run3, "transfer_job_data") as transfer:
            self.assertTrue(self.reconcile("active", jobs, dry_run=True))
            transfer.assert_not_called()
            self.assertTrue(self.reconcile("active", jobs))
            self.assertTrue(self.reconcile("active", jobs))
            transfer.assert_called_once_with("123", self.directory)
            self.assertEqual(self.state["phase"], "submitted")

    def test_staging_uses_only_local_inputs_and_small_outputs(self):
        submit = run3.prepare(self.base / "staging", 1148, {"TM010": [0, 1]},
                              self.url, True, "a"*32)
        check_run3_inputs(submit)
        self.assertIn("transfer_output_files = run01148_job_status.json,publication.json",
                      submit.read_text())
        (submit.parent / "iq_compact_spectra.py").unlink()
        with self.assertRaisesRegex(ValueError, "iq_compact_spectra.py"):
            check_run3_inputs(submit)

    def test_receipt_required_and_verified_without_remote_access(self):
        self.state["phase"] = "submitted"
        jobs = [dict(JobStatus=4, ExitCode=0, ClusterId=123)]
        receipt = dict(url=self.url, run=1148, attempt=self.state["attempt"],
                       validated=True, size=100, remote_size=100,
                       local_adler32="12345678", remote_adler32="87654321")
        path = self.directory / "publication.json"
        self.assertTrue(self.reconcile("history", jobs))
        (self.directory / "run01148_job_status.json").write_text(
            json.dumps(dict(run=1148, status="success", exit_code=0)))
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "publication receipt"):
            self.reconcile("history", jobs)
        self.assertTrue(self.payload.exists())
        receipt["remote_adler32"] = receipt["local_adler32"]
        path.write_text(json.dumps(receipt))
        with patch.dict(os.environ, {}, clear=True), patch.object(storage, "gfal") as remote:
            self.assertFalse(self.reconcile("history", jobs))
            remote.assert_not_called()
        self.assertEqual(self.state["phase"], "verified")

    def test_scheduling_without_personal_credentials(self):
        root = self.base / "pilot"
        root.mkdir()
        with patch.dict(os.environ, {}, clear=True), patch.object(storage, "gfal") as remote, \
             patch.object(run3, "submit_job", return_value="123") as submit:
            run3.cycle(root, dict(max_active=1, split_pairs={"TM010": [0, 1]},
                                  failure_days=7, max_attempts=2),
                       SimpleNamespace(pilot=True, gc_dry_run=False))
            remote.assert_not_called()
            submit.assert_called_once()

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
    def test_worker_reads_renewed_credential_for_each_gfal_process(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(os.environ, {"_CONDOR_CREDS": folder, "BEARER_TOKEN": "personal"}, clear=True), \
             patch.object(storage.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="ok")) as call:
            credential = Path(folder) / "t1.use"
            for token in ("synthetic-one", "synthetic-two"):
                credential.write_text(json.dumps({"access_token": token}))
                storage.gfal("stat", "davs://example.invalid/test")
                self.assertEqual(call.call_args.kwargs["env"]["BEARER_TOKEN"], token)
            self.assertEqual(os.environ["BEARER_TOKEN"], "personal")


    def test_existing_product_with_different_runtime_metadata(self):
        import h5py
        from urllib.parse import unquote, urlparse

        with tempfile.TemporaryDirectory() as tmp:
            candidate, existing = (Path(tmp) / name for name in ("candidate.h5", "published.h5"))
            for timestamp, path in enumerate((candidate, existing)):
                with h5py.File(path, "w") as f:
                    meta = f.create_group("metadata")
                    for key in ("pairs_json", "bor_settings_json", "bor_lo_json", "source_size_bytes",
                                "iq_convention", "fs_hz", "midas_layout"):
                        meta.attrs[key] = "same"
                    meta.attrs["runtime"] = timestamp
                    f.create_dataset("spectrum", data=[1, 2, 3])
            url = storage.PILOT + "/run01148_iq_v3.h5"

            def gfal(tool, *args):
                self.assertEqual(tool, "copy")
                Path(unquote(urlparse(args[-1]).path)).write_bytes(existing.read_bytes())

            remote = storage.local_identity(existing)
            def verify(destination, identity):
                self.assertEqual(destination, url)
                if identity != remote:
                    raise ValueError("different file bytes")
                return dict(identity, remote_size=identity["size"],
                            remote_adler32=identity["local_adler32"])

            with patch.object(storage, "gfal", side_effect=gfal), \
                 patch.object(storage, "verify", side_effect=verify), \
                 patch.object(storage, "validate_product"):
                result = storage.verify_existing(candidate, url, storage.local_identity(candidate), 1148)
                self.assertEqual(result["remote_adler32"], remote["local_adler32"])
                with h5py.File(candidate, "r+") as f:
                    f["spectrum"][0] = 5
                with self.assertRaisesRegex(ValueError, "differs at spectrum"):
                    storage.verify_existing(candidate, url, storage.local_identity(candidate), 1148)

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
