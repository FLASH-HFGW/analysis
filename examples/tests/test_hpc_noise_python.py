import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'examples'))
from hpc.check_noise_environment import check_environment


class NoisePythonTests(unittest.TestCase):
    def test_preflight_rejects_a_local_scipy_fallback(self):
        def imported(name):
            return SimpleNamespace(__file__='/old-venv/scipy/__init__.py' if name=='scipy'
                                   else '/cvmfs/sft-flash.infn.it/package/'+name+'/__init__.py')
        with mock.patch.dict(os.environ,{'HFGW_NOISE_CVMFS_ONLY':'1','HFGW_CVMFS_ROOT':'/cvmfs/sft-flash.infn.it'}), \
             mock.patch('hpc.check_noise_environment.importlib.import_module',side_effect=imported):
            with self.assertRaisesRegex(RuntimeError,'scipy was loaded outside FLASH CVMFS'):
                check_environment()

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
        env['HFGW_PYTHON']=str(selected)
        env['HFGW_NOISE_VENV']=str(selected.parent.parent)
        env['PYTHONPATH']=str(selected.parent.parent/'lib/python3.9/site-packages')+':/old/python3.11/site-packages'
        command='source "$HFGW_REPO_ROOT/examples/hpc/noise_python.sh"; printf "selected=%s\\npath=%s\\n" "$HFGW_PYTHON" "$PYTHONPATH"'
        r=subprocess.run(['bash','-e','-c',command],env=env,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        return dict(line.split('=',1) for line in r.stdout.splitlines() if line.startswith(('selected=','path='))),selected

    def test_defaults_to_available_python39_without_assuming_python311(self):
        with tempfile.TemporaryDirectory() as directory:
            data,_=self.select(Path(directory))
            self.assertEqual(data['selected'],'python3.9')
            self.assertNotIn('python3.11',data['path'])

    def test_ignores_old_venv_and_cleans_inherited_package_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            data,selected=self.select(Path(directory),venv=True)
            self.assertEqual(data['selected'],'python3.9')
            self.assertNotIn(str(selected.parent.parent),data['path'])
            self.assertNotIn('python3.11',data['path'])
            self.assertTrue(data['path'].startswith(str(Path(directory)/'cvmfs/package/python3.9/site-packages')+':'))


if __name__=='__main__':unittest.main()
