import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hpc import noise_pilot


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


if __name__ == '__main__':
    unittest.main()
