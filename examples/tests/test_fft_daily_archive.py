import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import types
import unittest
from unittest import mock
from zipfile import ZipFile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "examples"))
sys.path.insert(0, str(ROOT / "autoreco"))
import fft_daily_archive as daily
import autoreco as ar


def make_window(path, start, index=1, value=1):
    np.savez_compressed(path, window_start=start, window_stop=start + 1,
        window_seconds=1., window_index=index,
        fft_amp_mode0_SPECs=np.array([value, 2., 3.]), n_fft_done=4,
        number_chunks=64, fs=5e6)


class DailyArchiveTests(unittest.TestCase):
    def test_lossless_midnight_grouping_and_run_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "run00001_fft_1s.npz"
            second = root / "run00001_fft_2s.npz"
            make_window(first, 1767225599.)  # 2025-12-31 23:59:59 UTC
            make_window(second, 1767225600., 2)
            summary = root / "run00001.npz"
            np.savez_compressed(summary, x=np.array([1, 2, 3]))
            archives = daily.consolidate([first, second, summary], root / "daily")
            self.assertEqual([p.name for p in archives], ["fft_2025-12-31.zip", "fft_2026-01-01.zip"])
            restored = {}
            for path in archives:
                doc = daily.verify(path)
                with ZipFile(path) as archive:
                    for name in doc["entries"]:
                        restored[name] = archive.read(name)
            for source in (first, second, summary):
                self.assertEqual(restored[source.name], source.read_bytes())
            with daily.load_product(root / "daily", first.name) as archived, \
                 daily.load_product(root, first.name) as raw:
                np.testing.assert_array_equal(archived["fft_amp_mode0_SPECs"], raw["fft_amp_mode0_SPECs"])

    def test_rerun_removes_old_windows_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "run00001_fft_1s.npz"
            second = root / "run00001_fft_2s.npz"
            other = root / "run00002_fft_1s.npz"
            make_window(first, 1767225599.)
            make_window(second, 1767225600., 2)
            make_window(other, 1767225599.)
            daily.consolidate([first, second, other], root / "daily")
            make_window(first, 1767225599., value=9)
            for _ in range(2):
                daily.consolidate([first], root / "daily", replace_runs=True)
            names = set()
            for path in (root / "daily").glob("*.zip"):
                names.update(daily.verify(path)["entries"])
            self.assertEqual(names, {first.name, other.name})

    def test_undated_summary_and_nonfinite_time_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary = root / "run00001.npz"
            np.savez_compressed(summary, x=1)
            with self.assertRaisesRegex(ValueError, "No dated window"):
                daily.consolidate([summary], root / "daily")
            with self.assertRaises(ValueError):
                daily.utc_day(float("nan"))

    def test_bundle_manifest_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run00001_fft_windows.zip"
            bundle = daily.RunBundle(path)
            bundle.add("run00001_fft_1s.npz", window_start=1767225600.,
                window_stop=1767225601., window_index=1, window_seconds=1.)
            bundle.close()
            doc = daily.verify(path)
            doc["entries"]["run00001_fft_1s.npz"]["sha256"] = "bad"
            with ZipFile(path) as source:
                data = source.read("run00001_fft_1s.npz")
            with ZipFile(path, "w") as output:
                output.writestr("run00001_fft_1s.npz", data)
                output.writestr("manifest.json", json.dumps(doc))
            with self.assertRaisesRegex(ValueError, "checksum"):
                daily.verify(path)

    def test_worker_bundle_preserves_the_legacy_npz_outputs(self):
        # Exercise the actual writer and accumulation loop with fixed processed
        # events; MIDAS decoding and multiprocessing are independent of storage.
        class Reader:
            def __init__(self, *args): pass
            def get_bor_odb_dump(self): return types.SimpleNamespace(data={})

        class Pool:
            def __init__(self, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def imap(self, *args, **kwargs):
                for index in range(3):
                    yield {"has_spec": True, "has_tgps": False, "event_number": index,
                        "tdaq": 1767225599. + index, "trigger": None, "nsamp": 1048576,
                        "fft": {mode: {"amp": np.arange(4.) + mode + 1,
                                       "fs_meta": 5e6} for mode in range(3)}}

        reader = types.ModuleType("midas.file_reader")
        reader.MidasFile = Reader
        midas = types.ModuleType("midas")
        midas.file_reader = reader
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kind in ("npz", "daily-zip"):
                args = ["analysis", "--path", directory, "--run", "1", "--out-dir", str(root / kind),
                    "--fft-window-seconds", "1", "--fft-output-format", kind, "--mode-workers", "1"]
                with mock.patch.dict(sys.modules, {"midas": midas, "midas.file_reader": reader}), \
                     mock.patch("multiprocessing.Pool", Pool), mock.patch.object(sys, "argv", args):
                    runpy.run_path(str(ROOT / "examples/analyze_midas_iq_fft_4ms_paral-pipe.py"))
            bundle_path = root / "daily-zip/run00001_fft_windows.zip"
            doc = daily.verify(bundle_path)
            self.assertEqual(len(doc["entries"]), 4)
            self.assertEqual(list((root / "daily-zip").glob("*.npz")), [])
            with ZipFile(bundle_path) as archive:
                for legacy in (root / "npz").glob("*.npz"):
                    with np.load(legacy) as old, np.load(io.BytesIO(archive.read(legacy.name))) as new:
                        self.assertEqual(old.files, new.files)
                        for key in old.files:
                            np.testing.assert_array_equal(old[key], new[key])

    def test_daily_job_only_returns_bundle_and_transfers_its_module(self):
        with tempfile.TemporaryDirectory() as directory:
            files = ar.build_htcondor_files([1], Path(directory), "flash/data", "flash/fft",
                100, 4, ROOT / "examples/analyze_midas_iq_fft_4ms_paral-pipe.py", -1, 64, 1.)
            submit = files[0][1].read_text()
            self.assertIn("fft_daily_archive.py", submit)
            self.assertIn("transfer_output_files = fft_daily_pending\n", submit)
            self.assertIn("mv", files[0][0].read_text())

    def test_incomplete_bundle_cannot_complete_a_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "run00001_fft_windows.zip"
            bundle = daily.RunBundle(path)
            bundle.add("run00001_fft_1s.npz", window_start=1767225600.,
                window_stop=1767225601., window_index=1, window_seconds=1.)
            bundle.close()
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                daily.consolidate([path], root / "daily")

    def test_publish_failure_keeps_job_retryable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / "00001"
            run.mkdir()
            ar.save_state(run, {"run_number": 1, "status": "daily_ready", "output_path": "flash/fft"})
            args = types.SimpleNamespace(output_dir=root, read_only=True)
            with mock.patch.object(ar, "run_command", return_value=types.SimpleNamespace(returncode=1)):
                ar.finalize_daily_jobs(args, [])
            self.assertEqual(ar.load_state(run)["status"], "daily_ready")
            with mock.patch.object(ar, "run_command", return_value=types.SimpleNamespace(returncode=0)):
                ar.finalize_daily_jobs(args, [])
            self.assertEqual(ar.load_state(run)["status"], "read_only_completed")


if __name__ == "__main__":
    unittest.main()
