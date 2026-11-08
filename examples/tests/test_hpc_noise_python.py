import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]


class NoisePythonTests(unittest.TestCase):
    def select(self, root, venv=False):
        binary=root/'bin';binary.mkdir()
        for name in ('module','python3.9'):
            p=binary/name;p.write_text('#!/bin/bash\nexit 0\n');p.chmod(0o755)
        cvmfs=root/'cvmfs';(cvmfs/'modules/modulefiles/x86_64-el9').mkdir(parents=True)
        runtime=root/'runtime'
        selected=runtime/'environments/noise_py39_v1/bin/python'
        if venv:
            selected.parent.mkdir(parents=True)
            selected.write_text('#!/bin/bash\nexit 0\n');selected.chmod(0o755)
        env=dict(os.environ,PATH=str(binary)+':'+os.environ['PATH'],HFGW_REPO_ROOT=str(ROOT),
                 HFGW_RUNTIME_ROOT=str(runtime),HFGW_CVMFS_ROOT=str(cvmfs))
        for key in ('HFGW_PYTHON','HFGW_NOISE_VENV'):env.pop(key,None)
        command='source "$HFGW_REPO_ROOT/examples/hpc/noise_python.sh"; printf "selected=%s\\npath=%s\\n" "$HFGW_PYTHON" "$PYTHONPATH"'
        r=subprocess.run(['bash','-e','-c',command],env=env,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        return dict(line.split('=',1) for line in r.stdout.splitlines() if line.startswith(('selected=','path='))),selected

    def test_defaults_to_available_python39_without_assuming_python311(self):
        with tempfile.TemporaryDirectory() as directory:
            data,_=self.select(Path(directory))
            self.assertEqual(data['selected'],'python3.9')
            self.assertNotIn('python3.11',data['path'])

    def test_prefers_shared_user_venv_and_its_scipy_over_cvmfs(self):
        with tempfile.TemporaryDirectory() as directory:
            data,selected=self.select(Path(directory),venv=True)
            self.assertEqual(data['selected'],str(selected))
            self.assertTrue(data['path'].startswith(str(selected.parent.parent/'lib/python3.9/site-packages')+':'))


if __name__=='__main__':unittest.main()
