import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import recovery
import run3_cycle as run3


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.raw = self.base / "raw"
        self.raw.mkdir()
        self.products = self.base / "products"
        self.products.mkdir()
        self.row = dict(run=681, filename="run00681.mid.gz", events=1000,
                        rucio_status=0, reco_done=4, reco_version="1.1",
                        reco_output_path="previous", auto_reco="")
        (self.raw / self.row["filename"]).write_bytes(b"fixture")
        self.policy = recovery.options(dict(max_attempts=2, persistent_recovery={}))

    def admit(self, **values):
        return recovery.admission(dict(self.row, **values), 681, self.raw, self.products, [])

    def test_discovery_uses_event_scope_and_storage_instead_of_reconstruction_counter(self):
        for status in (-1, 0, 4, "", None):
            self.assertEqual(self.admit(reco_done=status), "waiting_capacity")
        self.assertEqual(self.admit(events=999), "below_event_threshold")
        self.assertEqual(self.admit(events=""), "event_count_unknown")
        self.assertEqual(self.admit(rucio_status=2), "raw_unavailable")
        self.assertEqual(self.admit(reco_version="3.1"), "publication_missing_operator_review")
        self.assertEqual(self.admit(auto_reco=-2), "operator_excluded")
        self.assertEqual(self.admit(auto_reco=-1), "invalid_control")
        self.assertEqual(self.admit(auto_reco=0), "waiting_capacity")
        (self.products / "run00681_iq_v3.1.root").touch()
        self.assertEqual(self.admit(), "root_present_needs_evidence")

    def test_exhausted_attempts_require_cooldown_and_terminal_history(self):
        failed = dict(phase="failed", attempt_number=2, failed_at=10)
        jobs = [dict(JobStatus=4, ExitCode=1)]
        cooldown = recovery.DEFAULT_COOLDOWN + 10
        self.assertEqual(recovery.retry(failed, cooldown-1, self.policy, "history", jobs)[0],
                         "reconstruction_cooldown")
        self.assertEqual(recovery.retry(failed, cooldown, self.policy, "history", jobs)[1], (2, 0, 0))
        self.assertIsNone(recovery.retry(failed, cooldown, self.policy, "active", jobs)[1])
        self.assertIsNone(recovery.retry(failed, cooldown, self.policy, "history", [dict(JobStatus=4, ExitCode=0)])[1])
        self.assertIsNone(recovery.retry(failed, cooldown, self.policy, "history", [dict(JobStatus=3)])[1])
        self.assertIsNone(recovery.retry(failed, cooldown, self.policy, "history", [dict(JobStatus=3, ExitCode=0)])[1])
        self.assertEqual(recovery.retry(dict(failed, recovery_episode=3), cooldown, self.policy, "history", jobs)[0],
                         "automatic_recovery_exhausted")

    def test_authentication_does_not_consume_scientific_attempts(self):
        submit = dict(phase="submitting", attempt_number=2, episode_attempts=2, submission_failures=1)
        evidence = ("authentication_required", 10)
        self.assertEqual(recovery.retry(submit, 11, self.policy, "history", [], evidence)[0],
                         "authentication_required")
        self.assertEqual(recovery.retry(submit, 5000, self.policy, "history", [], evidence)[1], (1, 1, 1))
        for source, jobs, diagnosis in (("active", [], evidence), ("history", [{}], evidence),
                                        ("history", [], ("submission_failure", 10)), ("history", [], None)):
            self.assertIsNone(recovery.retry(submit, 5000, self.policy, source, jobs, diagnosis)[1])
        self.assertEqual(recovery.retry(dict(submit, submission_failures=3), 5000, self.policy,
                                        "history", [], evidence)[0], "submission_recovery_exhausted")
        self.assertIsNone(recovery.retry(dict(submit, cluster=123), 5000, self.policy,
                                        "history", [], evidence)[1])

    def test_operator_change_at_submit_time_is_respected(self):
        root = self.base / "production"
        root.mkdir()
        headers = list(self.row)
        sheet = Mock()
        sheet.batch_get.return_value = [[headers], [list(dict(self.row, auto_reco=-2).values())]]
        settings = dict(run_min=1148, reco_version="3.0", output_format="root", max_attempts=2,
                        persistent_recovery={}, failure_days=7, max_active=20,
                        max_submit_per_cycle=20, deferred_runs=[], split_pairs={})
        with patch.object(run3, "BASE", self.base), patch.object(run3, "RAW_ARCHIVE", self.raw), \
             patch.object(run3, "ROOT_ARCHIVE", self.products), \
             patch.object(run3, "ARCHIVE_MOUNT", SimpleNamespace(is_mount=lambda: True)), \
             patch.object(run3, "local"), patch.object(run3, "open_google_sheet", return_value=sheet), \
             patch.object(run3, "get_headers", return_value=headers), \
             patch.object(run3, "read_all_records", return_value=[self.row]), \
             patch.object(run3, "prepare", return_value=root / "submit.sub"), \
             patch.object(run3, "save_state") as save, patch.object(run3, "submit_job") as submit:
            run3.cycle(root, settings, SimpleNamespace(pilot=False, gc_dry_run=False))
        sheet.batch_get.assert_called_once_with(["1:1", "2:2"])
        save.assert_not_called()
        submit.assert_not_called()

    def test_changed_or_missing_control_header_fails_closed(self):
        sheet = Mock()
        headers = list(self.row)
        values = list(dict(self.row, auto_reco=-2).values())
        moved = [headers[-1], *headers[:-1]]
        sheet.batch_get.return_value = [[moved], [[values[-1], *values[:-1]]]]
        self.assertIsNone(run3.current_admission_row(sheet, 2, 681, self.row["filename"]))
        sheet.batch_get.return_value = [[headers[:-1]], [values[:-1]]]
        self.assertIsNone(run3.current_admission_row(sheet, 2, 681, self.row["filename"]))
        sheet.batch_get.return_value = [[headers], [values[:-1]]]  # Sheets omits trailing blanks.
        self.assertIsNotNone(run3.current_admission_row(sheet, 2, 681, self.row["filename"]))

    def test_exclusion_is_applied_at_discovery_and_reenable_keeps_retry_limits(self):
        options = dict(run_min=681, reco_version="3.1", output_format="root")
        row = dict(self.row, reco_done=0, auto_reco=-2)
        self.assertFalse(run3.discover([row], options)[1])
        row["auto_reco"] = 0
        self.assertIn(681, run3.discover([row], options)[1])
        failed = dict(phase="failed", attempt_number=6, recovery_episode=3,
                      episode_attempts=2, failed_at=1)
        self.assertEqual(recovery.retry(failed, 100000, self.policy, "history",
                                       [dict(JobStatus=4, ExitCode=1)])[0],
                         "automatic_recovery_exhausted")

    def test_diagnostic_with_acceptance_marker_is_uncertain(self):
        run_dir = self.base / "00681"
        state = dict(attempt="a"*32, phase="submitting")
        evidence = run_dir / state["attempt"] / "00681"
        evidence.mkdir(parents=True)
        error = evidence / "submit_error.json"
        error.write_text(json.dumps(dict(exit_code=1, stdout="1 job submitted to cluster 100.",
                                        stderr="Please visit: https://condor.psge.cloud.infn.it/key/example")))
        with patch.object(run3, "BASE", self.base), patch.object(run3, "local"):
            self.assertIsNone(run3.submit_diagnosis(run_dir, state, 681))

    def test_older_attempt_still_in_queue_blocks_retry(self):
        history = [{"attempt": "a"*32}, {"attempt": "b"*32}]
        with patch.object(run3, "condor_query", side_effect=[[], [{"JobStatus": 2}]]) as query:
            self.assertTrue(run3.prior_attempt_active(history))
            self.assertEqual([call.args[1] for call in query.call_args_list], ["a"*32, "b"*32])

    def test_missing_rows_remain_in_durable_observations(self):
        path = self.base / "observations.json"
        recovery.save_observations(path, {"681": "raw_unavailable", "682": "validated"})
        recovery.save_observations(path, {"683": "operator_excluded"})
        self.assertEqual(json.loads(path.read_text()),
                         {"681": "missing_logbook_row", "683": "operator_excluded"})


if __name__ == "__main__":
    unittest.main()
