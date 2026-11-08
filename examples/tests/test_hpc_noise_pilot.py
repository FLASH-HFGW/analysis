import argparse
import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hpc import noise_pilot
from iq_noise_io import build_results, save_results_h5


class SlurmPilotTests(unittest.TestCase):
    def prepare(self, root):
        reference = root / 'reference.json'
        reference.write_text('{"iq_sign": -1}')
        temperatures = root / 'temperatures.csv'
        temperatures.write_text('run,time_unix\n')
        temperatures.with_suffix('.schema.json').write_text('{}')
        args = argparse.Namespace(campaign=root/'campaign', output=root/'output',
            reference=reference, temperatures=temperatures, submit=False,
            max_active=2, token_time=3600, time='03:00:00', account='cygno', partition='GPU', qos='normal')
        noise_pilot.prepare(args)
        return args, json.loads((args.campaign/'manifest.json').read_text())

    def test_prepare_and_read_only_cycle_never_contact_scheduler(self):
        with tempfile.TemporaryDirectory() as directory:
            args, manifest = self.prepare(Path(directory))
            with mock.patch.object(noise_pilot, 'execute', side_effect=AssertionError('Unexpected scheduler call')):
                noise_pilot.verify_sources(args.campaign, manifest)
                status = noise_pilot.cycle(args, manifest)
            self.assertEqual(status['counts'], {'prepared': 12})
            (args.campaign/'sources/noise_reference.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Frozen source changed'):
                noise_pilot.verify_sources(args.campaign, manifest)

    def test_retry_archives_failures_without_submitting_or_changing_other_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            args,manifest=self.prepare(Path(directory))
            for run,job in [(680,4293),(704,4294)]:
                (args.campaign/f'run{run:05d}.json').write_text(json.dumps(dict(run=run,status='failed',job_id=job,error='scipy missing')))
            with mock.patch.object(noise_pilot,'execute',return_value='') as command:
                noise_pilot.retry_failed(args.campaign,manifest)
            self.assertEqual(command.call_count,1)
            self.assertEqual(command.call_args.args[0][0],'squeue')
            for run,job in [(680,4293),(704,4294)]:
                state=json.loads((args.campaign/f'run{run:05d}.json').read_text())
                self.assertEqual(state['status'],'prepared')
                self.assertNotIn('job_id',state)
                archived=json.loads((args.campaign/f'attempts/run{run:05d}_JOB_{job}.json').read_text())
                self.assertEqual(archived['error'],'scipy missing')
                self.assertEqual(len(state['previous_attempts']),1)
            untouched=json.loads((args.campaign/'run00727.json').read_text())
            self.assertEqual(untouched,dict(run=727,status='prepared'))

    def test_retry_refuses_a_job_still_visible_in_slurm(self):
        with tempfile.TemporaryDirectory() as directory:
            args,manifest=self.prepare(Path(directory))
            p=args.campaign/'run00680.json'
            p.write_text(json.dumps(dict(run=680,status='failed',job_id=4293)))
            before=p.read_bytes()
            with mock.patch.object(noise_pilot,'execute',return_value='4293\n'):
                with self.assertRaisesRegex(ValueError,'active Slurm job'):
                    noise_pilot.retry_failed(args.campaign,manifest)
            self.assertEqual(p.read_bytes(),before)

    def test_rolling_submission_limits_jobs_and_requests_fresh_tokens_via_launcher(self):
        with tempfile.TemporaryDirectory() as directory:
            args, manifest = self.prepare(Path(directory))
            args.submit = True
            with mock.patch.object(noise_pilot, 'execute', side_effect=['Submitted job 500: run 680\n',
                                                                      'Submitted job 501: run 704\n']) as command:
                status = noise_pilot.cycle(args, manifest)
            self.assertEqual(command.call_count, 2)
            self.assertEqual(status['counts'], {'submitted': 2, 'prepared': 10})
            for call in command.call_args_list:
                argv = call.args[0]
                self.assertEqual(argv[argv.index('--analysis')+1], 'noise')
                self.assertEqual(argv[argv.index('--token-time')+1], '3600')
                self.assertEqual(call.kwargs['env']['HFGW_NOISE_SOURCE_DIR'],str(args.campaign/'sources'))

    def test_failed_result_stops_new_submissions(self):
        with tempfile.TemporaryDirectory() as directory:
            args, manifest = self.prepare(Path(directory))
            state = args.campaign/'run00680.json'
            state.write_text(json.dumps(dict(run=680, status='submitted', job_id=500)))
            jobdir = args.output/'jobs/JOB_500'
            jobdir.mkdir()
            (jobdir/'job_status.json').write_text('{"run":680,"exit_code":17}')
            args.submit=True
            with mock.patch.object(noise_pilot,'execute',return_value='500 RUNNING\n') as command:
                status=noise_pilot.cycle(args,manifest)
            self.assertEqual(command.call_count,1)
            self.assertEqual(command.call_args.args[0][0],'squeue')
            self.assertEqual(status['failed_runs'],[680])
            self.assertEqual(status['counts'],{'failed':1,'prepared':11})

    def test_cpu_selection_reaches_the_launcher_without_forcing_gpu_partition(self):
        with tempfile.TemporaryDirectory() as directory:
            args,manifest=self.prepare(Path(directory))
            args.submit=True;args.resource='cpu';args.partition=None;args.max_active=1
            with mock.patch.object(noise_pilot,'execute',return_value='Submitted job 500: run 680\n') as command:
                noise_pilot.cycle(args,manifest)
            argv=command.call_args.args[0]
            self.assertEqual(argv[argv.index('--resource')+1],'cpu')
            self.assertNotIn('--partition',argv)
            state=json.loads((args.campaign/'run00680.json').read_text())
            self.assertEqual(state['resource'],'cpu')

    def test_prepare_bootstraps_external_inputs_without_committing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            args,_=self.prepare(root)
            inputs=build_results({'purpose':'noise_temperature_pilot_inputs','iq_sign':-1},{})
            inputs['inputs']={name:np.frombuffer((root/name).read_bytes(),dtype=np.uint8)
                              for name in ('reference.json','temperatures.csv','temperatures.schema.json')}
            inputs['inputs']['noise_reference.json']=inputs['inputs'].pop('reference.json')
            args.campaign=root/'new-campaign';args.reference=None;args.temperatures=None
            def fetched(url,destination,digest):
                self.assertTrue(url.startswith('davs://'))
                self.assertEqual(len(digest),64)
                save_results_h5(destination,inputs)
            with mock.patch.object(noise_pilot,'fetch',side_effect=fetched) as download:
                noise_pilot.prepare(args)
            self.assertEqual(download.call_count,1)
            reference=json.loads((args.campaign/'sources/noise_reference.json').read_text())
            self.assertEqual(reference['iq_sign'],-1)
            manifest=json.loads((args.campaign/'manifest.json').read_text())
            self.assertIn('noise_temperature_pilot_minus1_20261108',manifest['gpfs_url'])

    def test_publication_failure_retries_without_resubmitting_scientific_job(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);args,manifest=self.prepare(root)
            state=args.campaign/'run00680.json'
            state.write_text(json.dumps(dict(run=680,status='submitted',job_id=500)))
            jobdir=args.output/'jobs/JOB_500';jobdir.mkdir()
            (jobdir/'job_status.json').write_text('{"run":680,"exit_code":0}')
            (jobdir/'run00680_noise.h5').write_bytes(b'simulated-valid-HDF5')
            args.submit=True
            with mock.patch('noise_temperature_pilot.validate',return_value={}), \
                 mock.patch.object(noise_pilot,'execute',return_value='500 RUNNING\n') as scheduler, \
                 mock.patch.object(noise_pilot,'publish',side_effect=RuntimeError('Temporary authentication failure')):
                status=noise_pilot.cycle(args,manifest)
            self.assertEqual(scheduler.call_count,1)
            self.assertEqual(status['publication_pending'],[680])
            self.assertEqual(status['failed_runs'],[])
            args.submit=False
            remote=dict(url=manifest['gpfs_url']+'/run00680_noise_v1.h5',
                        sha256=hashlib.sha256(b'simulated-valid-HDF5').hexdigest())
            with mock.patch('noise_temperature_pilot.validate',return_value={}), \
                 mock.patch.object(noise_pilot,'execute',side_effect=AssertionError('No resubmission expected')), \
                 mock.patch.object(noise_pilot,'publish',return_value=remote) as published:
                status=noise_pilot.cycle(args,manifest)
            self.assertTrue(published.call_args.args[1].endswith('/run00680_noise_v1.h5'))
            self.assertEqual(status['counts'],{'complete':1,'prepared':11})
            self.assertEqual(json.loads(state.read_text())['gpfs'],remote)


if __name__ == '__main__':
    unittest.main()
