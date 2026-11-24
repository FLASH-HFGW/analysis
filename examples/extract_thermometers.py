#!/usr/bin/env python3
"""Extract thermometer INPT banks from MIDAS files into a local time-series CSV.

One row is one acquired bank, without interpolation between asynchronous
equipments. Original channel order and ODB labels are retained in the schema.
An SQLite checkpoint allows interrupted or incremental scans to be resumed.
"""

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import time


DEFAULT_INPUT = Path('/home/mazzitel/flash-data/data/LNF')
DEFAULT_OUTPUT = Path('/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/thermometers/thermometers.csv')
SUFFIXES = ('.mid', '.mid.gz', '.mid.bz2', '.mid.lz4')
VERSION = 1
BASE_COLUMNS = ['time_unix', 'time_utc', 'run', 'equipment', 'event_id',
                'event_serial', 'bank', 'schema_id', 'source_file', 'source_status']

# Numeric bank layouts described in the supplied cold_sc documentation.
# The log-file date string is not present in INPT. No signal is calibrated here.
MERCURY = [
    ('TIME seconds', 's', 'Instrument time; epoch unspecified'),
    ('Pt_50K_T Ohm', 'Ohm', 'Platinum resistance on 50 K plate'),
    ('Pt_50K_T K', 'K', 'Temperature on 50 K plate'),
    ('Diode_4K_T raw', '', 'Diode on 4 K plate: caption says Ohm, description says V'),
    ('Diode_4K_T K', 'K', 'Temperature on 4 K plate'),
    ('unused raw', '', 'Unused channel, preserved'),
    ('unused K', 'K', 'Unused channel, preserved'),
    ('Diode_MC_T raw', '', 'Mixing-chamber diode: caption says Ohm, description says V'),
    ('Diode_MC_T K', 'K', 'Mixing-chamber diode temperature'),
    ('Pt_HeatSwitch_T Ohm', 'Ohm', 'Heat-switch platinum resistance'),
    ('Pt_HeatSwitch_T K', 'K', 'Heat-switch temperature'),
    ('RuO2_Mag_T Ohm', 'Ohm', 'Magnet RuO2 resistance'),
    ('RuO2_Mag_T K', 'K', 'Magnet temperature'),
]
AVS_SENSORS = ['Still', '50mK', 'TT2107_TWPA', 'TT1922_NS', 'Dale1.5K_cavity',
               'CMN143_MC', 'CMN130_MC', 'unused7', 'unused8', 'unused9']
AVS = [('Date2', 's', 'Instrument time; epoch unspecified')]
AVS += [(name + ' R', 'Ohm' if i < 7 else '', 'Resistance' if i < 7 else 'Unused channel, preserved')
        for i, name in enumerate(AVS_SENSORS)]
AVS += [(name + ' T', 'mK' if i < 7 else '', 'Temperature' if i < 7 else 'Unused channel, preserved')
        for i, name in enumerate(AVS_SENSORS)]
AVS += [(name + ' I', 'mA', 'Heater current') for name in ['NoiseSource', 'Still', 'HeatSwitch', 'MC']]
FP = [(name, 'mbar', 'Gas-handling pressure') for name in ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7']]
FP += [('Flow', 'ml/min', 'Mixture circulation flow'), ('Pc', '', 'Unused, preserved')]
FP += [(name, 'mbar', description) for name, description in [
    ('MG0', 'Still pressure'), ('MG1', 'IVC pressure'), ('MG2', 'OVC Pirani pressure'),
    ('MG3', 'P4 mixture pressure'), ('MG4', 'Scroll-pump suction pressure'), ('MG5', 'OVC cold-cathode pressure')]]
FP += [(name, '', 'State/status, preserved without conversion') for name in ['State0', 'State1', 'State2', 'FP Status', 'MG Status']]
LAYOUTS = {'temp_mercury': MERCURY, 'temp_avs': AVS, 'temp_fp': FP}


def get_ci(mapping, key, default=None):
    for name, value in mapping.items():
        if str(name).casefold() == key.casefold():
            return value
    return default


def event_number(value):
    if isinstance(value, int):
        return value
    try:
        return int(str(value), 0)
    except ValueError:
        return int(str(value), 10)


def slug(value):
    return re.sub(r'[^A-Za-z0-9]+', '_', str(value)).strip('_') or 'unnamed'


def equipment_map(odb):
    result = {}
    for name, equipment in get_ci(odb, 'Equipment', {}).items():
        if not isinstance(equipment, dict):
            continue
        identifier = get_ci(get_ci(equipment, 'Common', {}), 'Event ID')
        if identifier is None:
            continue
        settings = get_ci(equipment, 'Settings', {})
        result[event_number(identifier)] = {
            'equipment': name, 'names': get_ci(settings, 'Names Input', []),
            'units': get_ci(settings, 'Unit Input', [])}
    return result


def channel_schema(equipment, identifier, count, odb_info):
    documented = LAYOUTS.get(equipment.casefold(), [])
    documented = documented if len(documented) == count else []
    names = odb_info.get('names') or []
    units = odb_info.get('units') or []
    if not isinstance(names, (list, tuple)):
        names = [names]
    if not isinstance(units, (list, tuple)):
        units = [units]
    channels = []
    for index in range(count):
        fallback = documented[index] if documented else (f'channel_{index}', '', 'Unmapped channel, preserved')
        name = str(names[index]) if index < len(names) else fallback[0]
        odb_unit = str(units[index]) if index < len(units) else ''
        channels.append({'index': index, 'odb_name': name,
            'column': f'{slug(equipment)}__ch{index:02d}__{slug(name)}',
            'unit': odb_unit or fallback[1], 'unit_source': 'ODB' if odb_unit else 'documentation' if documented else 'unknown',
            'description': fallback[2]})
    doc = {'equipment': equipment, 'event_id': identifier, 'channels': channels,
           'odb_names': list(names), 'odb_units': list(units),
           'documented_layout_length_matches': bool(documented),
           'time_reference': 'MIDAS event header Unix seconds; instrument clock unchanged'}
    encoded = json.dumps(doc, sort_keys=True)
    return hashlib.sha256(encoded.encode()).hexdigest(), encoded


def discover(inputs, recursive=True, run_range=None):
    files = set()
    for path in inputs:
        path = path.expanduser()
        if path.is_dir():
            candidates = path.rglob('*') if recursive else path.iterdir()
        elif path.is_file():
            candidates = [path]
        else:
            raise FileNotFoundError(path)
        for candidate in candidates:
            if not candidate.name.endswith(SUFFIXES) or not candidate.is_file():
                continue
            match = re.search(r'run(\d+)', candidate.name, re.IGNORECASE)
            if run_range and (not match or not run_range[0] <= int(match[1]) <= run_range[1]):
                continue
            files.add(candidate.resolve())
    return sorted(files)


def initialize(connection):
    connection.executescript('''
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, size INTEGER,
            mtime_ns INTEGER, config TEXT, status TEXT, error TEXT,
            events_scanned INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS schemas (id TEXT PRIMARY KEY, document TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL,
            ordinal INTEGER, run INTEGER, timestamp INTEGER,
            event_id INTEGER, serial INTEGER, bank TEXT, schema_id TEXT,
            values_json TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS readings_file ON readings(file_id);
        CREATE INDEX IF NOT EXISTS readings_time ON readings(timestamp);
        CREATE TEMP TABLE selected_sources (path TEXT PRIMARY KEY);
    ''')


def extract_file(connection, path, banks, signature, force=False, max_records=None, reader_factory=None):
    if reader_factory is None:
        import midas.file_reader
        reader_factory = midas.file_reader.MidasFile
    stat = path.stat()
    previous = connection.execute('SELECT id,size,mtime_ns,config,status FROM sources WHERE path=?', (str(path),)).fetchone()
    if previous and not force and not max_records and previous[1:] == (stat.st_size, stat.st_mtime_ns, signature, 'complete'):
        return 'cached'
    events = records = 0
    status, error = 'complete', None
    with connection:
        if previous:
            file_id = previous[0]
            connection.execute('DELETE FROM readings WHERE file_id=?', (file_id,))
            connection.execute('UPDATE sources SET size=?,mtime_ns=?,config=?,status=?,error=NULL WHERE id=?',
                               (stat.st_size, stat.st_mtime_ns, signature, 'scanning', file_id))
        else:
            file_id = connection.execute('INSERT INTO sources(path,size,mtime_ns,config,status) VALUES(?,?,?,?,?)',
                (str(path), stat.st_size, stat.st_mtime_ns, signature, 'scanning')).lastrowid
        try:
            with reader_factory(str(path), use_numpy=True) as reader:
                try:
                    odb = reader.get_bor_odb_dump().data
                except RuntimeError:
                    odb = {}
                mapping = equipment_map(odb)
                match = re.search(r'run(\d+)', path.name, re.IGNORECASE)
                run = int(match[1]) if match else get_ci(get_ci(odb, 'Runinfo', {}), 'Run number')
                schemas = {}
                last_progress = time.monotonic()
                while True:
                    expected_offset = reader.next_event_offset
                    if not reader.read_next_event_header():
                        if reader.file.tell() < expected_offset:
                            raise EOFError('Truncated skipped event payload')
                        break
                    header = reader.event.header
                    events += 1
                    if time.monotonic() - last_progress >= 30:
                        print(f'  {events} event headers scanned; {records} thermometer banks', flush=True)
                        last_progress = time.monotonic()
                    if path.suffix == '.mid' and reader.next_event_offset > stat.st_size:
                        raise EOFError('Event payload extends beyond end of MIDAS file')
                    if header.is_midas_internal_event():
                        continue
                    identifier = int(header.event_id)
                    info = mapping.get(identifier, {})
                    equipment = info.get('equipment', f'event_{identifier}')
                    known_thermometer = equipment.casefold() in LAYOUTS
                    # Unknown small events are inspected for INPT; large SPEC
                    # banks are skipped without materializing or decoding them.
                    if not known_thermometer and header.event_data_size_bytes > 65536:
                        continue
                    event = reader.read_this_event_body()
                    if reader.file.tell() != reader.next_event_offset:
                        raise EOFError('Truncated thermometer event payload')
                    for name in banks:
                        if name not in event.banks:
                            continue
                        bank = event.banks[name]
                        values = [float(value) for value in bank.data]
                        key = (identifier, len(values))
                        if key not in schemas:
                            schema_id, document = channel_schema(equipment, identifier, len(values), info)
                            connection.execute('INSERT OR IGNORE INTO schemas VALUES(?,?)', (schema_id, document))
                            schemas[key] = schema_id
                        connection.execute('''INSERT INTO readings
                            (file_id,ordinal,run,timestamp,event_id,serial,bank,schema_id,values_json)
                            VALUES(?,?,?,?,?,?,?,?,?)''',
                            (file_id, events, run, int(header.timestamp), identifier,
                             int(header.serial_number), name, schemas[key], json.dumps(values)))
                        records += 1
                    if max_records and records >= max_records:
                        status = 'limited'
                        break
            final_stat = path.stat()
            if (final_stat.st_size, final_stat.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
                raise RuntimeError('Source file changed during extraction; retry after acquisition completes')
        except Exception as exc:
            # Valid observations preceding a damaged event remain available,
            # explicitly tagged partial. They are replaced on the next retry.
            status, error = 'partial', f'{type(exc).__name__}: {exc}'
        connection.execute('UPDATE sources SET status=?,error=?,events_scanned=? WHERE id=?',
                           (status, error, events, file_id))
    return status


def export(connection, output):
    selection = ' JOIN sources f ON f.id=r.file_id JOIN selected_sources sel ON sel.path=f.path '
    schemas = {identifier: json.loads(document) for identifier, document in connection.execute(
        'SELECT DISTINCT s.id,s.document FROM readings r JOIN schemas s ON s.id=r.schema_id ' + selection)}
    columns = sorted({channel['column'] for schema in schemas.values() for channel in schema['channels']})
    temporary = output.with_name(output.name + '.tmp')
    count = 0
    with temporary.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=BASE_COLUMNS + columns)
        writer.writeheader()
        query = '''SELECT r.timestamp,r.run,r.event_id,r.serial,r.bank,r.schema_id,
                          r.values_json,f.path,f.status FROM readings r ''' + selection + ' ORDER BY r.timestamp,f.path,r.ordinal,r.bank'
        for timestamp, run, identifier, serial, bank, schema_id, values_json, source, status in connection.execute(query):
            schema = schemas[schema_id]
            row = dict(zip(BASE_COLUMNS, [timestamp, datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
                run, schema['equipment'], identifier, serial, bank, schema_id, source, status]))
            values = json.loads(values_json)
            if len(values) != len(schema['channels']):
                raise ValueError('Inconsistent stored channel count')
            row.update({channel['column']: value for channel, value in zip(schema['channels'], values)})
            writer.writerow(row)
            count += 1
    temporary.replace(output)
    metadata = {'time_column': 'time_unix', 'timezone': 'UTC',
        'row_semantics': 'one acquired INPT bank; blank columns belong to other equipments, no forward-fill',
        'instrument_time': 'raw numeric channel; epoch unspecified; no conversion applied',
        'channels': columns, 'schemas': schemas}
    output.with_suffix('.schema.json').write_text(json.dumps(metadata, indent=2) + '\n')
    statuses = Counter()
    files = []
    for path, status, error, scanned in connection.execute('''SELECT s.path,COALESCE(f.status,'pending'),f.error,
            COALESCE(f.events_scanned,0) FROM selected_sources s LEFT JOIN sources f ON s.path=f.path ORDER BY s.path'''):
        statuses[status] += 1
        files.append({'path': path, 'status': status, 'error': error, 'events_scanned': scanned})
    report = {'csv': str(output), 'records': count, 'value_columns': len(columns),
              'source_status_counts': dict(statuses), 'files': files}
    output.with_suffix('.report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='*', type=Path, help='MIDAS files or directories; default: LNF data')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT, help='Local CSV destination')
    parser.add_argument('--no-recursive', action='store_true')
    parser.add_argument('--run-range', nargs=2, type=int, metavar=('START', 'END'))
    parser.add_argument('--bank', action='append', help='Four-character bank name; default INPT')
    parser.add_argument('--force', action='store_true', help='Reprocess even complete cached files')
    parser.add_argument('--max-files', type=int, help='Limit the scan for a local test')
    parser.add_argument('--max-records-per-file', type=int, help='Stop after this many banks; mark source limited')
    args = parser.parse_args()
    banks = sorted(set(args.bank or ['INPT']))
    if any(len(name) != 4 for name in banks):
        parser.error('MIDAS bank names have four characters; thermometer bank is INPT')
    if any(value is not None and value < 1 for value in (args.max_files, args.max_records_per_file)):
        parser.error('Limits must be positive')
    if args.run_range and args.run_range[0] > args.run_range[1]:
        parser.error('Run range must be increasing')
    paths = discover(args.inputs or [DEFAULT_INPUT], not args.no_recursive, args.run_range)
    if args.max_files:
        paths = paths[:args.max_files]
    if not paths:
        parser.error('No MIDAS files found')
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    signature = json.dumps({'version': VERSION, 'banks': banks}, sort_keys=True)
    interrupted = False
    with output.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        connection = sqlite3.connect(str(output.with_suffix('.sqlite')))
        try:
            initialize(connection)
            connection.executemany('INSERT INTO selected_sources VALUES(?)', [(str(path),) for path in paths])
            connection.commit()
            try:
                for index, path in enumerate(paths, 1):
                    print(f'[{index}/{len(paths)}] {path.name}', flush=True)
                    status = extract_file(connection, path, banks, signature, args.force, args.max_records_per_file)
                    print('  ' + status, flush=True)
            except KeyboardInterrupt:
                interrupted = True
                print('Interrupted: exporting committed records; rerun the same command to resume.', file=sys.stderr)
            report = export(connection, output)
        finally:
            connection.close()
    print(f"CSV: {output}; records: {report['records']}; value columns: {report['value_columns']}", flush=True)
    if interrupted:
        raise SystemExit(130)
    if report['source_status_counts'].get('partial'):
        print('Some sources are partial: see the report; valid records are explicitly tagged in the CSV.', file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
