from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

import recovery
import recovery_sheet as sync


class RecoverySheetTests(unittest.TestCase):
    base = ["run", "filename", "events", "auto_reco"]
    headers = base + list(sync.COLUMNS) + [sync.CONTROL]

    def row(self, run=1143, **values):
        return dict(run=run, filename=f"run{run:05d}.mid.gz", events=1000,
                    auto_reco="", **values)

    def test_status_vocabulary_and_retry_time(self):
        self.assertEqual(sync.view("validated"), ("completed", "", ""))
        self.assertEqual(sync.view("running"), ("running", "", ""))
        self.assertEqual(sync.view("idle")[0], "pending")
        self.assertEqual(sync.view("reconstruction_cooldown", 86400)[::2],
                         ("cooling_down", "1970-01-02T00:00:00+00:00"))
        self.assertEqual(sync.view("authentication_required")[0], "authentication_blocked")
        self.assertEqual(sync.view("operator_excluded")[0], "manually_excluded")

    def test_plan_missing_headers_and_does_not_write(self):
        rows = {1143: (12, self.row())}
        preview = sync.plan(self.base, rows, rows, {"1143": "historical_hold"}, {})
        self.assertEqual([r["value"] for r in preview["append_headers"]], [*sync.COLUMNS, sync.CONTROL])
        self.assertEqual(preview["proposed_rows"][0]["cells"][0],
                         dict(cell="E12", column="auto_reco_status", old="", new="blocked"))
        sheet = Mock()
        with self.assertRaises(ValueError):
            sync.apply(sheet, preview)
        sheet.batch_update.assert_not_called()

    def test_changed_only_bounded_batch_and_next_cycle(self):
        rows = {r: (r-1100, self.row(r)) for r in range(1143, 1146)}
        status = {"1143": "validated", "1144": "running", "1145": "historical_hold"}
        p = sync.plan(self.headers, rows, rows, status, {}, limit=2)
        self.assertEqual([r["run"] for r in p["first_batch"]], [1144, 1145])
        self.assertEqual(p["deferred_rows"], 1)
        sheet = Mock()
        sync.apply(sheet, p)
        sheet.batch_update.assert_called_once()
        cells = sheet.batch_update.call_args.args[0]
        self.assertEqual([cell["range"] for cell in cells], ["E44", "E45", "F45"])
        self.assertEqual(sheet.batch_update.call_args.kwargs, {"raw": True})
        updated = {run: (i, dict(row)) for run, (i, row) in rows.items()}
        for item in p["first_batch"]:
            for cell in item["cells"]:
                updated[item["run"]][1][cell["column"]] = cell["new"]
        p2 = sync.plan(self.headers, updated, updated, status, {})
        self.assertEqual([r["run"] for r in p2["proposed_rows"]], [1143])

    def test_conflicts_on_operator_change_row_movement_or_status_edit(self):
        before = {1143: (2, self.row())}
        for updated in ((3, self.row()), (2, dict(self.row(), auto_reco=-2)),
                        (2, self.row(auto_reco_release="root31:01143")),
                        (2, self.row(auto_reco_status="some other observation"))):
            p = sync.plan(self.headers, before, {1143: updated}, {"1143": "running"}, {})
            self.assertEqual(p["conflicts"], [1143])
            self.assertFalse(p["proposed_rows"])

    def test_recovered_run_clears_previous_error_and_retry_time(self):
        old = self.row(auto_reco_status="cooling_down",
                       auto_reco_error="Scientific episode exhausted",
                       auto_reco_next_retry="2026-11-28T00:00:00+00:00")
        rows = {1143: (2, old)}
        p = sync.plan(self.headers, rows, rows, {"1143": "validated"}, {})
        self.assertEqual({cell["column"]: cell["new"] for cell in p["first_batch"][0]["cells"]},
                         dict(auto_reco_status="completed", auto_reco_error="", auto_reco_next_retry=""))

    def test_explicit_release_never_overrides_manual_exclusion_or_version_conflict(self):
        with TemporaryDirectory() as path:
            archive = Path(path)
            row = dict(self.row(), rucio_status=0)
            (archive / row["filename"]).touch()
            self.assertEqual(recovery.admission(row, 1143, archive, archive, []), "historical_hold")
            row[sync.CONTROL] = "root31:01143"
            (archive / row["filename"]).write_bytes(b"fixture")
            self.assertEqual(recovery.admission(row, 1143, archive, archive, []), "waiting_capacity")
            row["reco_requested_version"] = "1.1"
            self.assertEqual(recovery.admission(row, 1143, archive, archive, []), "requested_version_conflict")
            row["auto_reco"] = -2
            self.assertEqual(recovery.admission(row, 1143, archive, archive, []), "operator_excluded")
