import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'examples/hpc/submit_one_run.sh'


class HpcSubmitTests(unittest.TestCase):
    def setup_commands(self, root, token_rc=0, lifetime=90000):
        binary = root / 'bin'
        binary.mkdir()
        token = binary / 'oidc-token'
        token.write_text('''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
Path(os.environ['TOKEN_CALL']).write_text(json.dumps(sys.argv[1:]))
if int(os.environ['TOKEN_RC']): sys.exit(int(os.environ['TOKEN_RC']))
print('job-private-token')
print('https://issuer.invalid')
print(os.environ['TOKEN_EXPIRY'])
''')
        sbatch = binary / 'sbatch'
        sbatch.write_text('''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
Path(os.environ['SUBMIT_CAPTURE']).write_text(json.dumps({'args':sys.argv[1:],
    'token':os.environ['BEARER_TOKEN'],'run':os.environ['HFGW_RUN'],
    'events':os.environ['HFGW_MAX_EVENTS'],'repo':os.environ['HFGW_REPO_ROOT']}))
print('4321;hpc-cluster')
''')
        token.chmod(0o755)
        sbatch.chmod(0o755)
        return dict(os.environ, PATH=str(binary) + ':' + os.environ['PATH'],
            HFGW_SLURM_LOG_DIR=str(root / 'logs'),
            HFGW_RUNTIME_ROOT=str(root / 'runtime'), BEARER_TOKEN='shell-original-token',
            TOKEN_CALL=str(root / 'token-call.json'), SUBMIT_CAPTURE=str(root / 'submission.json'),
            TOKEN_RC=str(token_rc), TOKEN_EXPIRY=str(int(time.time()) + lifetime))

    def test_submission_uses_private_token_and_run_options(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = self.setup_commands(root)
            result = subprocess.run(['bash', str(SCRIPT), '00680', '--time', '02:00:00',
                '--max-events', '100'], cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            capture = json.loads((root / 'submission.json').read_text())
            self.assertEqual(capture['token'], 'job-private-token')
            self.assertEqual(capture['run'], '680')
            self.assertEqual(capture['events'], '100')
            self.assertEqual(capture['repo'], str(ROOT))
            self.assertIn('--time=02:00:00', capture['args'])
            self.assertIn('--account=cygno', capture['args'])
            self.assertEqual(json.loads((root / 'token-call.json').read_text()), ['--all', '--time=86400', 'flash'])
            self.assertNotIn('job-private-token', result.stdout + result.stderr)
            self.assertIn('4321', result.stdout)

    def test_sourcing_does_not_modify_parent_token_or_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = self.setup_commands(root)
            env['HFGW_RUN'] = '999'
            command = 'source "$1" 680; printf "parent:%s:%s\\n" "$BEARER_TOKEN" "$HFGW_RUN"'
            result = subprocess.run(['bash', '-c', command, 'test', str(SCRIPT)],
                env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('parent:shell-original-token:999', result.stdout)
            self.assertEqual(json.loads((root / 'submission.json').read_text())['token'], 'job-private-token')

    def test_token_failure_never_submits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = self.setup_commands(root, token_rc=7)
            result = subprocess.run(['bash', str(SCRIPT), '680'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 7)
            self.assertFalse((root / 'submission.json').exists())

    def test_short_token_is_reported_and_never_submitted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = self.setup_commands(root, lifetime=3600)
            result = subprocess.run(['bash', str(SCRIPT), '680'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 21)
            self.assertIn('less than the requested', result.stderr)
            self.assertFalse((root / 'submission.json').exists())

    def test_invalid_run_never_requests_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = self.setup_commands(root)
            result = subprocess.run(['bash', str(SCRIPT), 'not-a-run'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse((root / 'token-call.json').exists())

    def test_expired_token_is_never_accepted_by_clock_tolerance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = self.setup_commands(root, lifetime=-5)
            result = subprocess.run(['bash', str(SCRIPT), '680', '--token-time', '1'],
                env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 21)
            self.assertFalse((root / 'submission.json').exists())


if __name__ == '__main__':
    unittest.main()
