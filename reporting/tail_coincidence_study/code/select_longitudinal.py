"""Select Dataset 2 hourly points using validated archived BOR timestamps."""
import csv
import hashlib
import json
from pathlib import Path
import re

STUDY = Path(__file__).resolve().parents[1]
ARCHIVE = Path('/home/mazzitel/flash-data')
BASE = STUDY.parents[1] / 'reporting/run3b_longitudinal/data/inventory.json'
ROOT = ARCHIVE / 'analysis/autoreco/Run3'
RAW = ARCHIVE / 'data/LNF'
FIRST = 1429
CONTROLS = {1529, 1629, 1729}


def listing(directory, pattern):
    return {int(match[1]): p for p in directory.iterdir()
            if (match := re.fullmatch(pattern, p.name)) and int(match[1]) >= FIRST}


def main():
    source = BASE.read_bytes()
    archived = {r['run']: r for r in json.loads(source)['runs']}
    roots = listing(ROOT, r'run(\d+)_iq_v3\.1\.root')
    raws = listing(RAW, r'run(\d+)\.mid\.gz')
    unknown = set(roots) - {r for r, row in archived.items()
                            if row['status'] == 'validated_complete'}
    if unknown:
        raise ValueError(f'Refresh ROOT metadata inventory for {sorted(unknown)}')
    reference = archived[FIRST]
    candidates = [archived[r] for r in roots.keys() & raws.keys()
                  if archived[r]['DAQ'] == reference['DAQ']]
    epoch = reference['start_unix']
    last = max(candidates, key=lambda row: row['start_unix'])
    targets = {}
    for seconds in range(0, last['start_unix'] - epoch + 1, 3600):
        nearest = min(candidates, key=lambda row: (
            abs(row['start_unix'] - epoch - seconds), row['start_unix'], row['run']))
        targets.setdefault(nearest['run'], []).append(seconds // 3600)
    selected = []
    for row in sorted(candidates, key=lambda x: x['start_unix']):
        run = row['run']
        if run not in targets and run not in CONTROLS | {FIRST, last['run']}:
            continue
        stat = raws[run].stat()
        if (stat.st_size != row['archived_raw_bytes'] or
                roots[run].stat().st_size != row['root_size']):
            raise ValueError(f'Archive size changed for {run}')
        with raws[run].open('rb') as stream:
            if stream.read(3) != b'\x1f\x8b\x08':
                raise ValueError(f'Invalid gzip header for {run}')
        receipt_path = STUDY/'validation'/'longitudinal'/f'{run}.json'
        raw_validated = receipt_path.exists() and json.loads(
            receipt_path.read_text())['checks_passed']
        selected.append(dict(run=run, start_utc=row['start_utc'], end_utc=row['stop_utc'],
                             since_start_s=row['start_unix']-epoch,
                             hourly_targets=targets.get(run, []), control=run in CONTROLS,
                             endpoint=run in {FIRST, last['run']}, raw_bytes=stat.st_size,
                             raw_mtime_ns=stat.st_mtime_ns, raw_path=str(raws[run]),
                             root_path=str(roots[run]), samples=row['received_samples'],
                             daq=row['DAQ'], lo=row['LO'],
                             status='raw_validated_checkpoint' if run == FIRST else
                             'raw_validated_longitudinal' if raw_validated else
                             'ROOT metadata validated; raw size and gzip header verified'))
    result = dict(source_sha256=hashlib.sha256(source).hexdigest(),
                  source_snapshot=json.loads(source)['summary']['inventory_utc'],
                  selection_basis='Nearest archived MIDAS BOR timestamp to each hourly target',
                  dataset_start_utc=reference['start_utc'], last_eligible=last['run'],
                  reconstructed_count=len(roots), raw_count=len(raws),
                  reconstructed_end_utc=last['stop_utc'],
                  compatible_candidates=len(candidates),
                  raw_only_gaps=sorted(r for r in raws.keys()-roots.keys() if r < max(roots)),
                  later_raw_only=sorted(r for r in raws if r > max(roots)),
                  selected_raw_bytes=sum(r['raw_bytes'] for r in selected),
                  pilot_compressed_bytes_per_s=9310514217/159.765,
                  remaining_raw_bytes=sum(r['raw_bytes'] for r in selected if r['run'] != FIRST),
                  selected=selected)
    (STUDY/'data/longitudinal_selection.json').write_text(json.dumps(result, indent=2)+'\n')
    fields = ['run', 'start_utc', 'end_utc', 'since_start_s', 'hourly_targets',
              'control', 'endpoint', 'raw_bytes', 'status']
    with (STUDY/'tables/longitudinal_selection.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(selected)
    configuration = [
        dict(run=r['run'], start_utc=r['start_utc'], TWPA=r['daq']['with_twpa'],
             pump_on=r['daq']['pump_on'], pump_hz=r['daq']['pump_hz'],
             archived_pump_setting=r['daq']['pump_power_setting'],
             primary_LO_hz=r['lo']['freq RS'], secondary_LO1_hz=r['lo']['freq Teled Ch1'],
             secondary_LO2_hz=r['lo']['freq Teled Ch2'])
        for r in selected
    ]
    with (STUDY/'tables/longitudinal_configuration.csv').open('w') as stream:
        writer = csv.DictWriter(stream, list(configuration[0]))
        writer.writeheader()
        writer.writerows(configuration)
    with (STUDY/'tables/longitudinal_raw_only.csv').open('w') as stream:
        writer = csv.writer(stream)
        writer.writerow(['run', 'status'])
        writer.writerows((r, state) for category, state in (
            ('raw_only_gaps', 'ROOT gap inside reconstruction range'),
            ('later_raw_only', 'later raw listing; no ROOT reconstruction'))
            for r in result[category])
    candidate_fields = ['run', 'start_utc', 'stop_utc', 'start_unix', 'stop_unix',
                        'root_size', 'archived_raw_bytes', 'hard_configuration']
    with (STUDY/'tables/longitudinal_candidates.csv').open('w') as stream:
        writer = csv.DictWriter(stream, candidate_fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(sorted(candidates, key=lambda row: row['start_unix']))
    print([r['run'] for r in selected], result['remaining_raw_bytes'])


if __name__ == '__main__':
    main()
