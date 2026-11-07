import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import extract_thermometers as extractor
import thermometers_batch as batch


def result(root, run, timestamp):
    output = root / f'run{run:05d}.csv'
    connection = sqlite3.connect(str(output.with_suffix('.sqlite')))
    extractor.initialize(connection)
    source = f'/worker/run{run:05d}.mid.gz'
    connection.execute('INSERT INTO selected_sources VALUES(?)', (source,))
    identifier = connection.execute('INSERT INTO sources(path,status) VALUES(?,?)', (source, 'complete')).lastrowid
    schema_id, document = extractor.channel_schema('Temp_Mercury', 10, 13, {})
    connection.execute('INSERT INTO schemas VALUES(?,?)', (schema_id, document))
    connection.execute('''INSERT INTO readings(file_id,ordinal,run,timestamp,event_id,serial,bank,schema_id,values_json)
        VALUES(?,?,?,?,?,?,?,?,?)''', (identifier, 1, run, timestamp, 10, 0, 'INPT', schema_id, json.dumps(list(range(13)))))
    connection.commit()
    extractor.export(connection, output)
    connection.close()
    return output


class ThermometerBatchTests(unittest.TestCase):
    def test_prepare_keeps_outputs_local_and_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = batch.prepare(root, 680, 681)
            self.assertEqual(len(batch.states(root, manifest)), 2)
            text = (root / '00680/submit.sub').read_text()
            self.assertIn('transfer_output_files = results', text)
            self.assertIn('request_cpus = 1', text)
            self.assertIn('ThermometerRun = 680', text)
            self.assertNotIn('gfal-copy -f', (root / '00680/script.sh').read_text())
            with self.assertRaisesRegex(ValueError, 'different range'):
                batch.prepare(root, 680, 682)

    def test_pack_and_merge_preserve_all_observations_and_run_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = batch.prepare(root, 680, 681)
            for run, timestamp in [(680, 200), (681, 100)]:
                output = result(root, run, timestamp)
                batch.pack(run, output, batch.bundle_path(root, run), f'davs://test/run{run:05d}.mid.gz', 0)
                self.assertEqual(batch.validate_bundle(batch.bundle_path(root, run), run)['records'], 1)
            path = batch.merge(root, manifest)
            import csv
            with path.open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([int(row['run']) for row in rows], [681, 680])
            self.assertTrue(all(row['source_file'].startswith('davs://test/') for row in rows))
            batch.merge(root, manifest)
            with path.open() as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 2)

    def test_missing_run_does_not_replace_existing_final_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = batch.prepare(root, 680, 681)
            output = root / 'thermometers_00680_00681.csv'
            output.write_text('preserve previous output')
            with self.assertRaises(FileNotFoundError):
                batch.merge(root, manifest)
            self.assertEqual(output.read_text(), 'preserve previous output')

    def test_controller_respects_limit_and_rediscovers_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = batch.prepare(root, 680, 682)
            queued = [{'ClusterId': 100, 'JobStatus': 2, 'ThermometerRun': 680}]
            commands = []
            def execute(command, cwd=None):
                commands.append(command)
                return json.dumps(queued) if command[0] == 'condor_q' else '101.0 - 101.0'
            with mock.patch.object(batch, 'execute', execute):
                batch.cycle(root, manifest, 2, submit=True)
            self.assertEqual(sum(c[0] == 'condor_submit' for c in commands), 1)
            states = batch.states(root, manifest)
            self.assertEqual(states[680]['cluster'], 100)
            self.assertEqual(states[682]['status'], 'prepared')

    def test_held_job_stops_new_submissions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = batch.prepare(root, 680, 681)
            queued = [{'ClusterId': 100, 'JobStatus': 5, 'ThermometerRun': 680, 'HoldReason': 'test failure'}]
            with mock.patch.object(batch, 'execute', return_value=json.dumps(queued)) as command:
                summary = batch.cycle(root, manifest, 4, submit=True)
            self.assertEqual(summary['failed_runs'], [680])
            self.assertFalse(any(c.args[0][0] == 'condor_submit' for c in command.call_args_list))


if __name__ == '__main__':
    unittest.main()
