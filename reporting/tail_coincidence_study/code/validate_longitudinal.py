"""Read-only cross-check of saved initial-batch CSVs and Run 1429 results."""
import csv
from collections import Counter
import json

import numpy as np

from stream_longitudinal import MODES, STUDY


def verify():
    v = STUDY/'validation'
    table = STUDY/'tables'
    with (v/'checks.json').open() as stream:
        assert json.load(stream)['all_passed']
    receipts = [json.loads(p.read_text()) for p in sorted((v/'longitudinal').glob('*.json'))]
    assert receipts

    def read(path):
        with path.open() as stream:
            return list(csv.DictReader(stream))

    for r in receipts:
        dest = table/'longitudinal'/str(r['run'])
        seconds = read(dest/'seconds.csv')
        counts_by_second = Counter((a['mode'], int(a['index'])//5000000)
                                   for a in read(dest/'T7_samples.csv'))
        assert r['checks_passed'] and r['EOR'] and r['gzip_CRC']
        assert r['serial_gaps'] == 0 and r['PPS_matches_ROOT']
        for mode, d in zip(MODES, r['modes']):
            q = [a for a in seconds if a['mode']==mode]
            assert [int(a['second']) for a in q] == list(range(len(q)))
            assert sum(int(a['samples']) for a in q) == r['samples']
            np.testing.assert_allclose(
                np.sqrt(sum(int(a['samples'])*float(a['RMS_V'])**2 for a in q)/r['samples']),
                d['rms_V'], rtol=1e-6)
            for field in ('T3','T5','T7'):
                assert sum(int(a[field]) for a in q) == d[field]
            assert all(int(a['T7']) == counts_by_second[mode, int(a['second'])] for a in q)
        shifts = read(dest/'time_shifts.csv')
        tuples = read(dest/'coincidences.csv')
        for a in read(dest/'coincidence_summary.csv'):
            key = (a['window_us'], a['kind'])
            counts = [int(b['count']) for b in shifts if (b['window_us'], b['kind']) == key]
            assert len(counts) == 20
            assert sum((b['window_us'], b['kind']) == key for b in tuples) == int(a['count'])
            assert np.isclose(np.mean(counts), float(a['shifted_mean']))
    batch = dict(runs=[r['run'] for r in receipts], all_passed=True,
                 saved_reference=1429, reference_raw_reprocessed=False,
                 successful_raw_input_bytes=sum(r['compressed_bytes'] for r in receipts),
                 successful_raw_wall_s=sum(r['raw_wall_s'] for r in receipts),
                 root_requested_bytes=sum(r['root_requested_bytes'] for r in receipts),
                 root_wall_s=sum(r['root_wall_s'] for r in receipts),
                 process_rchar=sum(r['process_io']['rchar'] for r in receipts),
                 kernel_read_bytes=sum(r['process_io']['read_bytes'] for r in receipts),
                 peak_RSS_KiB=max(r['peak_RSS_KiB'] for r in receipts),
                 mount='fuse.rclone; physical transfer bytes unavailable from mountstats')
    (v/'longitudinal_batch.json').write_text(json.dumps(batch,indent=2)+'\n')
    print(json.dumps(batch, indent=2))


if __name__ == '__main__':
    verify()
