"""GFAL transfers of scientific files, verified by a fresh SHA-256 download."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def credential_environment():
    token = subprocess.run(['oidc-token', '--time=60', 'flash'], capture_output=True, text=True, timeout=120)
    if token.returncode or not token.stdout.strip():
        raise RuntimeError('Cannot obtain a valid flash token; no transfer performed')
    env = os.environ.copy()
    env['BEARER_TOKEN'] = token.stdout.strip()
    return env


def run(args, env):
    result = subprocess.run(args, env=env, text=True, capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed ({result.returncode}): {result.stderr.strip()}')
    return result


def fetch(url, destination, expected_sha256):
    """Leave no final file if the scientific input's pinned checksum differs."""
    destination = Path(destination)
    temporary = destination.with_suffix(destination.suffix + '.part')
    try:
        temporary.unlink(missing_ok=True)
        run(['gfal-copy', url, temporary.resolve().as_uri()], credential_environment())
        if sha256(temporary) != expected_sha256:
            raise ValueError('Downloaded scientific input does not match its pinned SHA-256')
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def publish(source, url, checks):
    """Do not overwrite existing remote files; verify new or existing content."""
    source, checks = Path(source).resolve(), Path(checks)
    checks.mkdir(parents=True, exist_ok=True)
    expected = sha256(source)
    env = credential_environment()
    stat = subprocess.run(['gfal-stat', url], env=env, capture_output=True, text=True, timeout=60)
    if stat.returncode not in (0, 2):
        raise RuntimeError(f'Cannot inspect destination ({stat.returncode}): {stat.stderr.strip()}')
    if stat.returncode == 2:
        run(['gfal-copy', '-p', '-K', 'ADLER32', source.as_uri(), url], env)
    with tempfile.TemporaryDirectory(prefix='gpfs-verify-', dir=checks) as directory:
        returned = Path(directory) / source.name
        run(['gfal-copy', url, returned.resolve().as_uri()], env)
        if sha256(returned) != expected:
            raise ValueError('Remote SHA-256 mismatch; existing file was not overwritten: ' + url)
    return dict(url=url, sha256=expected, bytes=source.stat().st_size)
