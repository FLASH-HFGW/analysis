"""Best-effort Discord alerts. Call under the Run3 production lock."""
from datetime import datetime, timezone
import http.client
import json
import os
from pathlib import Path
import re
import socket
import stat
import tempfile
import time
from urllib.parse import urlsplit

WEBHOOK = Path("/home/mazzitel/.config/flash-autoreco/discord-webhook")
APPROVAL_HOST = "condor.psge.cloud.infn.it"


def approval_url(output):
    """Accept only an unambiguous URL from an explicit Condor challenge."""
    urls = r"https://[^\s<>\x22\x27\[\]{}()]+"
    context = re.sub(r"https?://\S+", "", output)
    if not re.search(r"authenticat|authoriz|approv|secure sign.in", context, re.I):
        return None
    links = set()
    for candidate in re.findall(urls, output):
        try:
            url = urlsplit(candidate)
        except ValueError:
            continue
        if (url.netloc not in (APPROVAL_HOST, APPROVAL_HOST + ":443") or url.fragment
                or not re.fullmatch(r"/key/[A-Za-z0-9._~/%+=-]*", url.path)
                or (url.path == "/key/" and not url.query)
                or any(segment in (".", "..") for segment in url.path.split("/"))
                or any(c in candidate for c in ("\\", "`", "*", "|"))):
            continue
        links.add(candidate)
    return links.pop() if len(links) == 1 else None


def deliver(message, webhook=WEBHOOK, timeout=3):
    """Send one message without redirects, secret logging or response-body reads."""
    connection = None
    try:
        fd = os.open(webhook, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, encoding="ascii") as secret:
            info = os.fstat(secret.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
                    or info.st_uid != os.getuid()):
                return False
            url = urlsplit(secret.read(2048).strip())
        if (url.scheme != "https" or url.netloc != "discord.com"
                or url.query or url.fragment
                or not re.fullmatch(r"/api/webhooks/\d+/[A-Za-z0-9_.-]+", url.path)):
            return False
        connection = http.client.HTTPSConnection(url.hostname, timeout=timeout)
        body = json.dumps(dict(content=message, allowed_mentions={"parse": []})).encode()
        connection.request("POST", url.path, body, {"Content-Type": "application/json"})
        return connection.getresponse().status == 204
    except (OSError, ValueError, http.client.HTTPException):
        return False
    finally:
        if connection is not None:
            connection.close()


class Notifier:
    """Persist incident counters and successful sends separately from job state."""
    def __init__(self, path, reminder_seconds=0):
        self.path = path
        self.reminder_seconds = reminder_seconds if type(reminder_seconds) is int and reminder_seconds > 0 else 0
        self.delivery_failed = False
        self.reported_exception = None

    def _read(self):
        if self.path.is_symlink():
            raise ValueError("Invalid notification state")
        try:
            return json.loads(self.path.read_text())
        except FileNotFoundError:
            return {}

    def _save(self, records):
        with tempfile.NamedTemporaryFile(mode="w", dir=self.path.parent, delete=False) as handle:
            pending = Path(handle.name)
            try:
                json.dump(records, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
                os.replace(pending, self.path)
            finally:
                pending.unlink(missing_ok=True)

    def _send(self, title, message, run, reference, approval=None):
        if self.delivery_failed:
            return False
        lines = [f"**FLASH autoreco — {title}**",
                 f"UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
                 f"Host: {socket.getfqdn()}"]
        if run is not None:
            lines.append(f"Run: {run:05d}")
        lines.append(message)
        if approval:
            lines.append(f"Authorization: <{approval}>")
        lines.append(f"Local reference: {reference}")
        if deliver("\n".join(lines)):
            return True
        self.delivery_failed = True
        print("FLASH Discord notification could not be delivered.", flush=True)
        return False

    def fault(self, key, title, message, reference, *, run=None, approval=None, after=1, error=None):
        if error is not None:
            self.reported_exception = error
        try:
            records = self._read()
            entry = records.setdefault(key, {"count": 0, "sent": None})
            entry["count"] += 1
            last = entry["sent"]
            now = time.time()
            if entry["count"] >= after and (last is None or
                    (self.reminder_seconds and now-last >= self.reminder_seconds)):
                if self._send(title, message, run, reference, approval):
                    entry["sent"] = now
            self._save(records)
        except Exception:
            print("FLASH Discord notification state unavailable.", flush=True)

    def resolved(self, key, title, proof, reference, *, run=None):
        try:
            records = self._read()
            entry = records.get(key)
            if entry is None:
                return
            if entry["sent"] is None or self._send(title, proof, run, reference):
                del records[key]
                self._save(records)
        except Exception:
            print("FLASH Discord notification state unavailable.", flush=True)
