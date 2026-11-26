import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import notify
import run3_cycle as scheduler


class NotificationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.secret = self.root / "webhook"
        self.secret.write_text("https://discord.com/api/webhooks/123/example-secret")
        self.secret.chmod(0o600)
        self.state = self.root / "notification-state.json"
        self.link = "https://condor.psge.cloud.infn.it/key/example-approval"

    def test_delivery_uses_https_and_suppresses_mentions(self):
        with patch.object(notify.http.client, "HTTPSConnection") as connection:
            client = connection.return_value
            client.getresponse.return_value.status = 204
            self.assertTrue(notify.deliver("test", self.secret))
            connection.assert_called_once_with("discord.com", timeout=3)
            verb, path, body, headers = client.request.call_args.args
            self.assertEqual(verb, "POST")
            self.assertTrue(path.startswith("/api/webhooks/"))
            self.assertEqual(json.loads(body), {"content": "test", "allowed_mentions": {"parse": []}})
            self.assertEqual(headers["Content-Type"], "application/json")
            client.close.assert_called_once()

    def test_missing_unreadable_or_insecure_webhook(self):
        with patch.object(notify.http.client, "HTTPSConnection") as connect:
            self.assertFalse(notify.deliver("test", self.root / "missing"))
            with patch.object(notify.os, "open", side_effect=PermissionError("private")):
                self.assertFalse(notify.deliver("test", self.secret))
            self.secret.chmod(0o644)
            self.assertFalse(notify.deliver("test", self.secret))
            connect.assert_not_called()

    def test_timeout_and_http_errors_do_not_leak_secrets(self):
        logs = io.StringIO()
        with contextlib.redirect_stdout(logs), patch.object(notify.http.client, "HTTPSConnection") as conn:
            client = conn.return_value
            client.getresponse.side_effect = TimeoutError("example-secret")
            self.assertFalse(notify.deliver("test", self.secret))
            client.getresponse.side_effect = None
            client.getresponse.return_value.status = 429
            self.assertFalse(notify.deliver("test", self.secret))
        self.assertNotIn("example-secret", logs.getvalue())
        self.assertNotIn("webhooks", logs.getvalue())

    def test_approval_link_requires_explicit_challenge_and_exact_origin(self):
        self.assertEqual(notify.approval_url(f"Please authenticate at:\n{self.link}\n"), self.link)
        self.assertEqual(notify.approval_url(f"Authorize request: <{self.link}?a=1&b=2>"),
                         self.link + "?a=1&b=2")
        for url in (self.link.replace("https", "http"), self.link.replace("/key/", "/other/"),
                    self.link.replace(".it/", ".it.evil.test/"), self.link + "#extra",
                    self.link.replace(".it/", ".it:9000/"), self.link.replace("https://", "https://user@")):
            self.assertIsNone(notify.approval_url("Authorize at " + url), url)
        self.assertIsNone(notify.approval_url("Reference: " + self.link))
        self.assertIsNone(notify.approval_url(f"Authorize at {self.link} {self.link}2"))

    def test_persistent_dedup_distinct_incidents_and_recovery(self):
        with patch.object(notify, "deliver", return_value=True) as send:
            n = notify.Notifier(self.state)
            n.fault("auth", "authentication", "approve", "local", run=1220, approval=self.link)
            notify.Notifier(self.state).fault("auth", "authentication", "approve", "local")
            notify.Notifier(self.state).fault("hold:1220", "HOLD", "inspect", "local", run=1220)
            self.assertEqual(send.call_count, 2)
            self.assertIn(self.link, send.call_args_list[0].args[0])
            self.assertNotIn(self.link, self.state.read_text())
            n.resolved("auth", "restored", "Accepted cluster 123", "local")
            n.resolved("auth", "restored", "Accepted cluster 123", "local")
            self.assertEqual(send.call_count, 3)
            n.fault("auth", "authentication", "approve", "local")
            self.assertEqual(send.call_count, 4)
            self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)

    def test_threshold_reminder_and_retry_after_delivery_failure(self):
        with patch.object(notify, "deliver", side_effect=[False, True, True]) as send, \
             patch.object(notify.time, "time", side_effect=[10, 20, 30, 40, 50]):
            for _ in range(5):
                notify.Notifier(self.state, reminder_seconds=15).fault(
                    "logbook", "logbook", "inspect", "local", after=2)
            self.assertEqual(send.call_count, 3)

    def test_scheduler_keeps_original_failure_and_attempt_state(self):
        production = self.root / "production"
        production.mkdir()
        run = 1220
        run_dir = production / "01220"
        run_dir.mkdir()
        fixture = dict(run=run, filename="run01220.mid.gz", reco_done=0, rucio_status=0)
        settings = dict(run_min=1148, reco_version="3.1", output_format="root",
                        failure_days=7, max_active=20, max_attempts=2,
                        max_submit_per_cycle=20, deferred_runs=[], split_pairs={})
        args = SimpleNamespace(pilot=False, gc_dry_run=False, notifier=notify.Notifier(self.state))
        error = scheduler.SubmissionError("original failure", "", "Authorize at " + self.link)
        logs = io.StringIO()
        with contextlib.redirect_stdout(logs), patch.object(notify, "deliver", return_value=False), \
             patch.object(scheduler, "BASE", self.root), patch.object(scheduler, "local"), \
             patch.object(scheduler, "open_google_sheet"), \
             patch.object(scheduler, "get_headers", return_value=list(fixture) +
                          ["reco_version", "reco_output_path"]), \
             patch.object(scheduler, "read_all_records", return_value=[fixture]), \
             patch.object(scheduler, "prepare", return_value=run_dir / "submit.sub"), \
             patch.object(scheduler, "submit_job", side_effect=error):
            with self.assertRaises(scheduler.SubmissionError) as observed:
                scheduler.cycle(production, settings, args)
        self.assertIs(observed.exception, error)
        self.assertEqual(json.loads(scheduler.state_path(run_dir).read_text())["phase"], "submitting")
        self.assertNotIn(self.link, logs.getvalue())


if __name__ == "__main__":
    unittest.main()
