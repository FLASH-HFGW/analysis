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
    'events':os.environ['HFGW_MAX_EVENTS'],'repo':os.environ['HFGW_REPO_ROOT'],
    'product_version':os.environ.get('HFGW_NOISE_PRODUCT_VERSION'),
    'calibration':os.environ.get('HFGW_NOISE_CALIBRATION'),
    'source_dir':os.environ.get('HFGW_NOISE_SOURCE_DIR'),
    'sbatch_gres':os.environ.get('SBATCH_GRES'),'sbatch_gpus':os.environ.get('SBATCH_GPUS')}))
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

    def test_noise_selects_separate_payload_and_three_hour_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = self.setup_commands(root, lifetime=4000)
            reference = root / 'reference.json'
            reference.write_text('{"iq_sign": -1}')
            result = subprocess.run(['bash', str(SCRIPT), '680', '--analysis', 'noise',
                '--reference', str(reference), '--token-time', '3600'],
                env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            capture = json.loads((root / 'submission.json').read_text())
            self.assertEqual(capture['args'][-1], str(ROOT / 'examples/hpc/noise_job.sh'))
            self.assertIn('--time=03:00:00', capture['args'])
            self.assertIn('--gres=gpu:1', capture['args'])
            self.assertNotIn('job-private-token', result.stdout + result.stderr)

    def test_noise_cpu_profile_does_not_request_or_inherit_gpus(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);env=self.setup_commands(root,lifetime=4000)
            env.pop('HFGW_SLURM_PARTITION',None)
            env.update(SBATCH_GRES='gpu:1',SBATCH_GPUS='1')
            reference=root/'reference.json';reference.write_text('{"iq_sign": -1}')
            result=subprocess.run(['bash',str(SCRIPT),'680','--analysis','noise','--resource','cpu',
                '--reference',str(reference),'--token-time','3600'],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            capture=json.loads((root/'submission.json').read_text())
            self.assertIn('--partition=CPU',capture['args'])
            self.assertFalse(any(a.startswith(('--gres=','--gpus=')) for a in capture['args']))
            self.assertIsNone(capture['sbatch_gres']);self.assertIsNone(capture['sbatch_gpus'])
            worker=(ROOT/'examples/hpc/noise_job.sh').read_text()
            self.assertNotIn('#SBATCH --gres',worker)
            self.assertNotIn('#SBATCH --partition',worker)

    def test_cpu_profile_is_not_applied_to_the_fft_gpu_program(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);env=self.setup_commands(root)
            result=subprocess.run(['bash',str(SCRIPT),'680','--resource','cpu'],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertFalse((root/'token-call.json').exists())

    def test_noise_missing_reference_never_requests_token(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = self.setup_commands(root)
            env.pop('HFGW_NOISE_REFERENCE', None)
            result = subprocess.run(['bash', str(SCRIPT), '680', '--analysis', 'noise'],
                env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse((root / 'token-call.json').exists())

    def test_v2_normalization_is_explicit_and_frozen_before_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);env=self.setup_commands(root,lifetime=4000)
            env.pop('HFGW_NOISE_SOURCE_DIR',None)
            reference=root/'reference.json';reference.write_text('{"iq_sign": -1}')
            calibration=root/'custom-gain.json'
            calibration.write_text('{"stages_db":{"custom":20},"total_db":20}')
            original=calibration.read_bytes()
            result=subprocess.run(['bash',str(SCRIPT),'680','--analysis','noise',
                '--reference',str(reference),'--product-version','v2',
                '--calibration',str(calibration),'--token-time','3600'],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            capture=json.loads((root/'submission.json').read_text())
            self.assertEqual(capture['product_version'],'v2')
            frozen=Path(capture['calibration'])
            self.assertNotEqual(frozen,calibration)
            calibration.write_text('{"total_db":999}')
            self.assertEqual(frozen.read_bytes(),original)
            self.assertTrue((Path(capture['source_dir'])/'iq_noise_v2.py').is_file())

    def test_v2_missing_normalization_never_requests_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);env=self.setup_commands(root)
            result=subprocess.run(['bash',str(SCRIPT),'680','--analysis','noise','--product-version','v2'],
                env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertFalse((root/'token-call.json').exists())

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
