"""Controlli dell'integrazione noise senza accesso a logbook o scheduler."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'autoreco'))
import autoreco as ar


class AutorecoNoiseTests(unittest.TestCase):
    def setUp(self):
        # Deliberately synthetic: tests must not depend on measured campaign data.
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.reference = Path(directory.name) / 'noise_reference.json'
        self.reference.write_text(json.dumps({'schema': 1, 'iq_sign': -1,
            'fs_hz': 5e6, 'input_range_v': 5.0,
            'modes': {mode: {'samples': 100, 'mean_amplitude_v': 1.0,
                'amplitude_noise_rms_v': 0.1} for mode in ('TM010', 'TM011', 'TM012')}}))

    def test_fft_builder_preserves_template(self):
        with tempfile.TemporaryDirectory() as directory:
            files=ar.build_htcondor_files([680],Path(directory),'flash/data/LNF','flash/fft',
                123,8,ROOT/'examples/analyze_midas_iq_noise.py',-1,64,0)
            self.assertEqual(files[0][0].read_text(),ar.SCRIPT_TEMPLATE)
            text=files[0][1].read_text()
            self.assertIn('123 analyze_midas_iq_noise.py $(job_cpus) -1 64 0',text)
            self.assertNotIn('iq_noise_statistics.py',text)

    def test_noise_cpu_request_controls_mode_workers(self):
        with tempfile.TemporaryDirectory() as directory:
            for cpus,workers in ((1,1),(3,3),(4,3),(8,3)):
                files=ar.build_htcondor_files([680],Path(directory)/str(cpus),
                    'flash/data/LNF','flash/noise',999999,cpus,
                    ROOT/'examples/analyze_midas_iq_noise.py',-1,64,0,
                    analysis_kind='noise',noise_reference=self.reference)
                text=files[0][1].read_text()
                self.assertIn('noise_reference.json -1 %d'%workers,text)
                self.assertIn('request_cpus = %d'%cpus,text)
                self.assertIn('--mode-workers "$MODE_WORKERS"',files[0][0].read_text())

    def test_prepare_only_has_no_external_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            argv=['autoreco','--run-range','680','681','--read-only','--ignore-reco-done',
                '--analysis-kind','noise','--iq-sign','-1','--noise-reference',str(self.reference),
                '--analysis-script-dir',str(ROOT/'examples'),'--output-dir',directory,'--prepare-only']
            with mock.patch.object(sys,'argv',argv), \
                 mock.patch.object(ar,'open_google_sheet',side_effect=AssertionError('logbook access')), \
                 mock.patch.object(ar,'run_command',side_effect=AssertionError('scheduler access')), \
                 contextlib.redirect_stdout(io.StringIO()):
                ar.main()
            for run in (680,681):
                p=Path(directory)/('%05d'%run)
                text=(p/'submit.sub').read_text()
                self.assertIn('iq_noise_statistics.py',text)
                self.assertIn('noise_reference.json -1',text)
                self.assertIn('noise_reference.json',text)
                self.assertNotIn('--max-events',(p/'script.sh').read_text())
                self.assertEqual((p/'noise_reference.json').read_bytes(),self.reference.read_bytes())
                self.assertFalse((p/'job_state.json').exists())

    def test_noise_requires_read_only(self):
        with mock.patch.object(sys,'argv',['autoreco','--run','680','--analysis-kind','noise']), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):ar.parse_args()

    def test_submit_failure_persists_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/"submit.sub"; p.touch()
            result=types.SimpleNamespace(returncode=1,stdout="submit output",stderr="ERROR: test failure")
            with mock.patch.object(ar,"run_command",return_value=result):
                with self.assertRaisesRegex(RuntimeError,"submit_error.json"):
                    ar.submit_job(p)
            doc=json.loads(p.with_name("submit_error.json").read_text())
            self.assertEqual(doc["stderr"],"ERROR: test failure")
            self.assertEqual(doc["exit_code"],1)

    def test_noise_stops_after_first_failed_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            argv=['autoreco','--run-range','680','681','--read-only','--ignore-reco-done',
                '--analysis-kind','noise','--iq-sign','-1',
                '--noise-reference',str(self.reference),
                '--analysis-script-dir',str(ROOT/'examples'),'--output-dir',directory]
            records=[{'run':run,'filename':'run%05d.mid.gz'%run,'rucio_status':0,'reco_done':1}
                     for run in (680,681)]
            output=io.StringIO()
            with mock.patch.object(sys,'argv',argv), \
                 mock.patch.object(ar,'open_google_sheet',return_value=object()), \
                 mock.patch.object(ar,'read_all_records',return_value=records), \
                 mock.patch.object(ar,'get_headers',return_value=[]), \
                 mock.patch.object(ar,'discover_existing_jobs'), \
                 mock.patch.object(ar,'submit_job',side_effect=RuntimeError('test failure')) as submit, \
                 contextlib.redirect_stdout(output):
                with self.assertRaises(SystemExit) as caught:ar.main()
            self.assertEqual(caught.exception.code,1)
            self.assertEqual(submit.call_count,1)
            self.assertIn('Nessun nuovo job sottomesso',output.getvalue())
            self.assertFalse(list(Path(directory).glob('*/job_state.json')))

    def test_reconcile_validates_noise_output(self):
        for complete in (False,True):
            with tempfile.TemporaryDirectory() as directory:
                p=Path(directory)
                (p/'output-1.0.log').touch()
                ref=json.loads(self.reference.read_text())
                (p/'noise_reference.json').write_text(json.dumps(ref))
                result={'input':'/tmp/run00680.mid.gz','status':'success','reached_eof':complete,
                        'global_statistics':{'config':{'reference':ref}}}
                (p/'run00680_noise.json').write_text(json.dumps(result))
                (p/'run00680_noise.npz').touch()
                state={'run_number':680,'cluster_id':'1','status':'submitted','analysis_kind':'noise'}
                with mock.patch.object(ar,'get_job_status',return_value=4), \
                     mock.patch.object(ar,'job_completed_successfully',return_value=True), \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertTrue(ar.reconcile_job(p,state))
                self.assertEqual(state['status'],'job_succeeded' if complete else 'failed')


if __name__=='__main__':
    unittest.main()
