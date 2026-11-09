import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class HpcNoiseTests(unittest.TestCase):
    def run_job(self, root, download_rc=0, analysis_rc=0, version='v1'):
        binary = root / 'bin'
        binary.mkdir()
        (root / 'cvmfs/modules/modulefiles/x86_64-el9').mkdir(parents=True)
        commands = {
            'module': '#!/bin/bash\nexit 0\n',
            'gfal-copy': '#!/bin/bash\necho transfer >> "$TEST_CALLS"\n'
                         'if [[ $DOWNLOAD_RC != 0 ]]; then exit "$DOWNLOAD_RC"; fi\n'
                         'printf raw > "$2"\n',
            'srun': '#!/bin/bash\necho srun >> "$TEST_CALLS"\nexec "$@"\n',
            'python3.9': '''#!/usr/bin/python3
import json, os, sys
from pathlib import Path
if sys.argv[1] == '-c' or sys.argv[1].endswith('check_noise_environment.py'):
    Path(os.environ['ENV_CAPTURE']).write_text(json.dumps({'pythonpath':os.environ['PYTHONPATH']}))
    sys.exit(0)
Path(os.environ['ANALYSIS_ARGS']).write_text(json.dumps(sys.argv[1:]))
out = Path(sys.argv[sys.argv.index('--out-dir')+1])
suffix = '_v2' if sys.argv[sys.argv.index('--product-version')+1] == 'v2' else ''
(out/('run00680_noise'+suffix+'.h5')).write_bytes(b'simulated-HDF5')
if '--calibration' in sys.argv:
    Path(os.environ['CALIBRATION_CAPTURE']).write_text(Path(sys.argv[sys.argv.index('--calibration')+1]).read_text())
print('analysis diagnostics')
sys.exit(int(os.environ['ANALYSIS_RC']))
''',
        }
        for name, contents in commands.items():
            p = binary / name
            p.write_text(contents)
            p.chmod(0o755)
        reference = root / 'reference.json'
        reference.write_text('{"iq_sign": -1}')
        calibration = root/'calibration.json'
        calibration.write_text('{"total_db":20}')
        env = dict(os.environ, PATH=str(binary)+':'+os.environ['PATH'], SLURM_JOB_ID='1234', HFGW_RUN='680',
                   HFGW_REPO_ROOT=str(ROOT), HFGW_CVMFS_ROOT=str(root/'cvmfs'),
                   HFGW_NOISE_REFERENCE=str(reference), HFGW_NOISE_SOURCE_DIR=str(ROOT/'examples'),
                   HFGW_NOISE_OUTPUT_ROOT=str(root/'results'), HFGW_SCRATCH_ROOT=str(root/'scratch'),
                   HFGW_PYTHON='python3.9', HFGW_MAX_EVENTS='99999999', ENV_CAPTURE=str(root/'environment.json'),
                   HFGW_NOISE_PRODUCT_VERSION=version,HFGW_NOISE_CALIBRATION=str(calibration),
                   CALIBRATION_CAPTURE=str(root/'calibration-used.json'),
                   BEARER_TOKEN='private-test-token', TEST_CALLS=str(root/'calls'),
                   ANALYSIS_ARGS=str(root/'args.json'), DOWNLOAD_RC=str(download_rc), ANALYSIS_RC=str(analysis_rc))
        result = subprocess.run(['bash',str(ROOT/'examples/hpc/noise_job.sh')],env=env,capture_output=True,text=True)
        return result, root/'results/JOB_1234'

    def test_full_noise_run_uses_minus_iq_and_filters_with_one_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, out = self.run_job(root)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            args = json.loads((root/'args.json').read_text())
            self.assertEqual(args[args.index('--iq-sign')+1], '-1')
            self.assertIn('--filtered-bands',args)
            self.assertIn('--h5-only',args)
            self.assertEqual(args[args.index('--product-version')+1], 'v1')
            paths=json.loads((root/'environment.json').read_text())['pythonpath'].split(':')
            self.assertEqual(paths[0],str(root/'cvmfs/package/python3.9/site-packages'))
            self.assertFalse(any('python3.11' in p for p in paths))
            self.assertNotIn('--max-events',args)
            self.assertEqual((root/'calls').read_text().count('transfer'),1)
            self.assertTrue((out/'run00680_noise.h5').exists())
            self.assertFalse(list(out.glob('*.mid*')))
            self.assertEqual(list((root/'scratch').iterdir()),[])
            self.assertNotIn('private-test-token',result.stdout+result.stderr)

    def test_transfer_failure_preserves_exit_status_and_does_not_analyze(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            result,out=self.run_job(root,download_rc=17)
            self.assertEqual(result.returncode,17)
            self.assertNotIn('srun',(root/'calls').read_text())
            self.assertEqual(json.loads((out/'job_status.json').read_text())['exit_code'],17)

    def test_v2_worker_passes_selected_calibration_to_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            result,out=self.run_job(root,version='v2')
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            args=json.loads((root/'args.json').read_text())
            self.assertEqual(args[args.index('--product-version')+1],'v2')
            self.assertIn('--calibration',args)
            self.assertEqual(json.loads((root/'calibration-used.json').read_text())['total_db'],20)
            self.assertTrue((out/'run00680_noise_v2.h5').is_file())

    def test_failed_analysis_keeps_diagnostics_and_scratch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            result,out=self.run_job(root,analysis_rc=27)
            self.assertEqual(result.returncode,27)
            self.assertIn('analysis diagnostics',(out/'analysis.log').read_text())
            self.assertEqual(json.loads((out/'job_status.json').read_text())['exit_code'],27)
            self.assertTrue(list((root/'scratch').glob('noise-1234.*')))


if __name__ == '__main__':
    unittest.main()
