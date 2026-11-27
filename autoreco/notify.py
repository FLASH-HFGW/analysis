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
from urllib.parse import parse_qsl, urlsplit

WEBHOOK = Path("/home/mazzitel/.config/flash-autoreco/discord-webhook")
APPROVAL_HOST = "condor.psge.cloud.infn.it"
URL_TEXT = r"https?://[^\s<>\x22\x27\[\]{}()`*]+"
VISIT_PROMPT = re.compile(r"(?m)^[ \t]*Please visit:[ \t]*\n?[ \t]*"
                          r"(?:[<`*]+|\[[^\]\n]*\]\()?(?P<url>" + URL_TEXT + r")")


def prompt_text(output):
    return output.replace(r"\r\n", "\n").replace(r"\n", "\n").replace("\r\n", "\n")


def approval_url(output):
    """Accept only an unambiguous URL from an explicit Condor challenge."""
    output = prompt_text(output)
    prompts = {match["url"] for match in VISIT_PROMPT.finditer(output)}
    context = re.sub(URL_TEXT, "", output)
    if not prompts and not re.search(r"authenticat|authoriz|approv|secure sign.in", context, re.I):
        return None
    links = set()
    for match in re.finditer(URL_TEXT, output):
        candidate = match[0]
        following = output[match.end():]
        leading = output[:match.start()]
        if following and not following[0].isspace():
            closing = following[0]
            opening = {">": "<", ")": "](", '"': '"', "'": "'"}.get(closing)
            if closing in "`*":
                opening = re.match(r"[`*]+", following)[0]
            if not opening or not leading.endswith(opening):
                continue
        try:
            url = urlsplit(candidate)
        except ValueError:
            continue
        if (url.scheme != "https" or url.netloc not in (APPROVAL_HOST, APPROVAL_HOST + ":443")
                or url.fragment or not re.fullmatch(r"/key/[A-Za-z0-9._~+=-]*", url.path)
                or (url.path == "/key/" and not url.query)
                or any(segment in (".", "..") for segment in url.path.split("/"))
                or any(re.search(r"redirect|return|next|url|target|destination", key, re.I)
                       or "://" in value for key, value in parse_qsl(url.query))
                or any(c in candidate for c in ("\\", "`", "*", "|"))):
            continue
        links.add(candidate)
    if len(links) != 1 or (prompts and prompts != links):
        return None
    return links.pop()


def approval_message(output, link):
    """Include only recognized challenge lines and show the URL separately as a link."""
    output = prompt_text(output)
    lines = []
    if re.search(r"(?m)^[ \t]*Submitting job\(s\)[.]?[ \t]*$", output):
        lines.append("Submitting job(s)")
    greeting = re.search(r"(?m)^[ \t]*(Hellow, [A-Za-z0-9_.-]+\.)[ \t]*$", output)
    if greeting:
        lines.append(greeting[1])
    if any(match["url"] == link for match in VISIT_PROMPT.finditer(output)):
        lines.append(f"Please visit: {link}")
    action = "Action required: Open the authorization URL and approve the HTCondor request."
    return "HTCondor message:\n```\n" + "\n".join(lines) + "\n```\n" + action if lines else action


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
