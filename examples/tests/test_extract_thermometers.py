import csv
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import extract_thermometers as therm


def event(identifier, timestamp, values=None, fail=False, size=128):
    return {'identifier': identifier, 'timestamp': timestamp, 'values': values,
            'fail': fail, 'size': size}


class Reader:
    def __init__(self, events, odb):
        self.events = events
        self.odb = odb
        self.file = io.BytesIO(b'\0' * sum(16 + e['size'] for e in events))
        self.next_event_offset = 0
        self.index = 0
        self.decoded = []

    def __enter__(self): return self
    def __exit__(self, *args): self.file.close()

    def get_bor_odb_dump(self):
        if self.odb is None:
            raise RuntimeError('No BOR')
        return types.SimpleNamespace(data=self.odb)

    def read_next_event_header(self):
        self.file.seek(self.next_event_offset)
        if self.index == len(self.events):
            return None
        self.current = self.events[self.index]
        self.index += 1
        self.file.read(16)
        self.next_event_offset += 16 + self.current['size']
        header = types.SimpleNamespace(event_id=self.current['identifier'],
            timestamp=self.current['timestamp'], serial_number=self.index,
            event_data_size_bytes=self.current['size'], is_midas_internal_event=lambda: False)
        self.event = types.SimpleNamespace(header=header)
        return self.event

    def read_this_event_body(self):
        self.decoded.append(self.current['identifier'])
        if self.current['fail']:
            raise EOFError('Damaged bank')
        self.file.seek(self.next_event_offset)
        self.event.banks = {'INPT': types.SimpleNamespace(data=self.current['values'])}
        return self.event


def odb():
    return {'Equipment': {
        'Temp_Mercury': {'Common': {'Event ID': '0x000a'}},
        'Temp_FP': {'Common': {'Event ID': 11}},
        'Temp_AVS': {'Common': {'Event ID': '12'}},
        'NetBox': {'Common': {'Event ID': 1}}}}


class ThermometerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.connection = sqlite3.connect(':memory:')
        therm.initialize(self.connection)

    def tearDown(self):
        self.connection.close()
        self.temporary.cleanup()

    def source(self, events):
        path = self.root / 'run00001.mid'
        path.write_bytes(b'\0' * sum(16 + e['size'] for e in events))
        self.connection.execute('INSERT OR IGNORE INTO selected_sources VALUES(?)', (str(path),))
        self.connection.commit()
        return path

    def scan(self, path, events, mapping=None):
        reader = Reader(events, odb() if mapping is None else mapping)
        result = therm.extract_file(self.connection, path, ['INPT'], 'test',
            reader_factory=lambda *args, **kwargs: reader)
        return result, reader

    def test_all_channels_time_order_and_no_forward_fill(self):
        mercury = [3873992960.] + list(range(12))
        events = [event(1, 99, size=70000), event(12, 102, list(range(25))),
                  event(10, 100, mercury), event(11, 101, list(range(20)))]
        path = self.source(events)
        result, reader = self.scan(path, events)
        self.assertEqual(result, 'complete')
        self.assertNotIn(1, reader.decoded)
        output = self.root / 'temperatures.csv'
        report = therm.export(self.connection, output)
        self.assertEqual(report['records'], 3)
        self.assertEqual(report['value_columns'], 58)
        with output.open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual([int(row['time_unix']) for row in rows], [100, 101, 102])
        time_column = next(key for key in rows[0] if key.startswith('Temp_Mercury__ch00'))
        self.assertEqual(float(rows[0][time_column]), mercury[0])
        self.assertEqual(rows[1][time_column], '')
        self.assertEqual(rows[0]['time_utc'], '1970-01-01T00:01:40+00:00')

    def test_resume_does_not_decode_complete_files(self):
        events = [event(10, 100, list(range(13)))]
        path = self.source(events)
        self.scan(path, events)
        result = therm.extract_file(self.connection, path, ['INPT'], 'test',
            reader_factory=lambda *a, **k: self.fail('Cached source was reopened'))
        self.assertEqual(result, 'cached')
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM readings').fetchone()[0], 1)

    def test_damaged_file_keeps_tagged_records_and_retry_replaces_them(self):
        events = [event(10, 100, list(range(13))), event(12, 101, fail=True)]
        path = self.source(events)
        self.assertEqual(self.scan(path, events)[0], 'partial')
        report = therm.export(self.connection, self.root / 'partial.csv')
        self.assertEqual(report['source_status_counts'], {'partial': 1})
        self.assertEqual(report['records'], 1)
        events[1]['fail'] = False
        events[1]['values'] = list(range(25))
        self.assertEqual(self.scan(path, events)[0], 'complete')
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM readings').fetchone()[0], 2)

    def test_extra_channels_are_preserved_without_assumed_units(self):
        events = [event(10, 100, list(range(14)))]
        path = self.source(events)
        self.scan(path, events)
        report = therm.export(self.connection, self.root / 'extra.csv')
        self.assertEqual(report['value_columns'], 14)
        schema = json.loads(self.connection.execute('SELECT document FROM schemas').fetchone()[0])
        self.assertFalse(schema['documented_layout_length_matches'])
        self.assertEqual(schema['channels'][-1]['unit'], '')

    def test_unknown_inpt_event_is_preserved_without_equipment_assumptions(self):
        events = [event(42, 100, [1., 2.])]
        path = self.source(events)
        reader = Reader(events, None)
        status = therm.extract_file(self.connection, path, ['INPT'], 'test',
            reader_factory=lambda *a, **k: reader)
        self.assertEqual(status, 'complete')
        schema = json.loads(self.connection.execute('SELECT document FROM schemas').fetchone()[0])
        self.assertEqual(schema['equipment'], 'event_42')
        self.assertEqual(len(schema['channels']), 2)

    def test_selected_inputs_do_not_export_unrelated_cached_files(self):
        events = [event(10, 100, list(range(13)))]
        path = self.source(events)
        self.scan(path, events)
        self.connection.execute('DELETE FROM selected_sources')
        self.connection.execute('INSERT INTO selected_sources VALUES(?)', ('/pending/run00002.mid',))
        report = therm.export(self.connection, self.root / 'selected.csv')
        self.assertEqual(report['records'], 0)
        self.assertEqual(report['source_status_counts'], {'pending': 1})

    def test_inpt_with_different_equipment_name_is_not_lost(self):
        events = [event(42, 100, [7., 8.])]
        path = self.source(events)
        mapping = {'Equipment': {'OtherThermometer': {'Common': {'Event ID': 42},
                    'Settings': {'Names Input': ['Probe A', 'Probe B']}}}}
        self.assertEqual(self.scan(path, events, mapping)[0], 'complete')
        schema = json.loads(self.connection.execute('SELECT document FROM schemas').fetchone()[0])
        self.assertEqual(schema['equipment'], 'OtherThermometer')
        self.assertEqual(schema['channels'][0]['odb_name'], 'Probe A')


if __name__ == '__main__':
    unittest.main()
