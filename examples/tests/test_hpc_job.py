import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class HpcJobTests(unittest.TestCase):
    def run_job(self, root, entry='job.sh', copy_rc=0, analysis_rc=0):
        binary = root / 'bin'
        binary.mkdir(exist_ok=True)
        module_dir = root / 'cvmfs/modules/modulefiles/x86_64-el9'
        module_dir.mkdir(parents=True, exist_ok=True)
        commands = {
            'module': '#!/bin/bash\nprintf "module %s\\n" "$*" >> "$TEST_CALLS"\n',
            'gfal-copy': '#!/bin/bash\nprintf "gfal-copy %s\\n" "$*" >> "$TEST_CALLS"\n'
                'if [[ $TEST_COPY_RC -ne 0 ]]; then exit "$TEST_COPY_RC"; fi\nprintf input > "$2"\n',
            'nvidia-smi': '#!/bin/bash\necho gpu-monitor\n',
            'srun': '#!/bin/bash\necho srun >> "$TEST_CALLS"\nexec "$@"\n',
            'python3.9': '''#!/bin/bash
if [[ ${1:-} == -V ]]; then echo Python; exit 0; fi
shift
while [[ $# -gt 0 ]]; do
  if [[ $1 == --out-dir ]]; then OUT=$2; fi
  shift
done
printf spectrum > "$OUT/run00388.npz"
printf profile > "$OUT/profile_run00388.csv"
exit "$TEST_ANALYSIS_RC"
''',
        }
        for name, data in commands.items():
            path = binary / name
            path.write_text(data)
            path.chmod(0o755)
        env = dict(os.environ, PATH=str(binary) + ':' + os.environ['PATH'],
            SLURM_JOB_ID='901', SLURM_SUBMIT_DIR=str(ROOT / 'examples/hpc'),
            SLURM_CPUS_PER_TASK='4', HFGW_CVMFS_ROOT=str(root / 'cvmfs'),
            HFGW_SCRATCH_ROOT=str(root / 'scratch'), HFGW_RUNTIME_ROOT=str(root / 'runtime'),
            BEARER_TOKEN='test-token-never-print', TEST_CALLS=str(root / 'calls'),
            TEST_COPY_RC=str(copy_rc), TEST_ANALYSIS_RC=str(analysis_rc))
        env.pop('HFGW_REPO_ROOT', None)
        result = subprocess.run(['bash', str(ROOT / 'examples/hpc' / entry)], cwd=root,
                                env=env, text=True, capture_output=True)
        return result, root / 'runtime/benchmarks/slurm/JOB_901'

    def test_one_gfal_transfer_and_local_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, output = self.run_job(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            calls = (root / 'calls').read_text()
            self.assertEqual(calls.count('gfal-copy '), 1)
            self.assertIn('module load gfal/1.9.0', calls)
            self.assertTrue((output / 'run00388.npz').exists())
            self.assertTrue((output / 'profile_run00388.csv').exists())
            self.assertFalse(any(output.glob('*.mid*')))
            self.assertNotIn('test-token-never-print', result.stdout + result.stderr)

    def test_failed_download_never_runs_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, output = self.run_job(root, copy_rc=17)
            self.assertEqual(result.returncode, 17)
            self.assertNotIn('srun', (root / 'calls').read_text())
            self.assertFalse((root / 'scratch/JOB_901/run00388.mid.gz').exists())
            self.assertEqual(json.loads((output / 'job_status.json').read_text())['exit_code'], 17)

    def test_analysis_failure_preserves_diagnostics_and_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, output = self.run_job(root, analysis_rc=27)
            self.assertEqual(result.returncode, 27)
            self.assertTrue((output / 'profile_run00388.csv').exists())
            self.assertEqual(json.loads((output / 'job_status.json').read_text())['exit_code'], 27)

    def test_old_jobsub_uses_the_same_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            result, output = self.run_job(Path(directory), entry='jobsub.sh')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((output / 'run00388.npz').exists())


if __name__ == '__main__':
    unittest.main()
