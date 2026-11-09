"""Check weighted band statistics and observed-only temperature matching."""
import copy
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from iq_noise_io import build_results, save_results_h5, read_results_h5
from noise_temperature_pilot import validate, cycle, prepare
import noise_temperature_pilot as pilot
from report_noise_temperature import pearson, summarize_product, temperatures_by_run, report


def product(path, run=680, sign=-1, complete=True):
    summary = dict(input=f'run{run:05d}.mid.gz', status='success', reached_eof=complete,
                   iq_sign=sign, samples=4, events=[{'midas_timestamp': 10}, {'midas_timestamp': 20}])
    events = dict(n=np.array([1, 3]), rms_v=np.array([2., 4.]), mean_amplitude_v=np.array([1., 3.]),
                  phase_resultant=np.ones(2), phase_mean_rad=np.array([0., np.pi]),
                  increment_resultant=np.ones(2), increment_mean_rad=np.zeros(2),
                  increment_pairs=np.array([1, 3]), event_timestamp_unix=np.array([10, 20]))
    offsets = [-1e6, -5e5, -25e4, -1e5, 0., 1e5, 25e4, 5e5, 1e6]
    bands = {f'band_{i:02d}': dict(offset_hz=offset, events=copy.deepcopy(events))
             for i, offset in enumerate(offsets)}
    filtered = dict(config=dict(iq_sign=sign, offsets_hz=offsets),
                    modes={mode: copy.deepcopy(bands) for mode in ('TM010', 'TM011', 'TM012')})
    save_results_h5(path, build_results(summary, {}, filtered))


class PilotTests(unittest.TestCase):
    def test_new_range_campaign_freezes_sources_and_existing_pause_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / 'inputs'
            inputs.mkdir()
            for run in (680, 681):
                (inputs / f'run{run:05d}.mid.gz').touch()
            reference = root / 'reference.json'
            reference.write_text('{"iq_sign": -1}')
            temperatures = root / 'temperatures.csv'
            temperatures.write_text('run,time_unix\n')
            temperatures.with_suffix('.schema.json').write_text('{}')
            with mock.patch.object(pilot, 'INPUT_ROOT', inputs), mock.patch.object(pilot, 'REFERENCE', reference):
                manifest = prepare(root/'campaign', root/'output', temperatures, [681, 680],
                                   'davs://example/new-range', True)
                self.assertEqual(manifest['runs'], [680, 681])
                self.assertFalse(manifest['submissions_paused'])
                self.assertEqual(manifest['gpfs_url'], 'davs://example/new-range')
                worker = (root/'campaign/00680/script.sh').read_text()
                self.assertIn('check_noise_environment.py', worker)
                self.assertIn('HFGW_CVMFS_ROOT=/cvmfs/sft-flash.infn.it', worker)
                self.assertIn('check_noise_environment.py', (root/'campaign/00680/submit.sub').read_text())
                paused = prepare(root/'paused', root/'output2', temperatures, [680])
                self.assertTrue(paused['submissions_paused'])
                reused = prepare(root/'paused', root/'output2', temperatures, [680,681],
                                 'davs://example/changed', True)
                self.assertEqual(reused, paused)
                custom = json.loads((pilot.ROOT/'config/noise_calibration_v2.json').read_text())
                custom.update(stages_db={'custom_total':20.},total_db=20.)
                custom_path = root/'custom-gain.json'
                custom_path.write_text(json.dumps(custom))
                v2 = prepare(root/'v2',root/'output-v2',temperatures,[680],
                             'davs://example/v2',False,'v2',custom_path)
                self.assertEqual(v2['product_version'],'v2')
                self.assertTrue(v2['submissions_paused'])
                worker=(root/'v2/00680/script.sh').read_text()
                self.assertIn('--product-version v2 --calibration noise_calibration.json',worker)
                self.assertTrue((root/'v2/sources/iq_noise_v2.py').is_file())
                self.assertIn('noise_calibration.json',v2['source_sha256'])
                custom_path.write_text('{}')
                self.assertEqual(json.loads((root/'v2/sources/noise_calibration.json').read_text())['total_db'],20.)

    def test_paused_campaign_cannot_submit(self):
        with self.assertRaisesRegex(ValueError, 'paused'):
            cycle(Path('/unused'), {'submissions_paused': True}, 4, True)

    def test_statistics_use_sample_weights_and_observed_time_window(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'run00680_noise.h5'
            product(p)
            validate(p, 680)
            points = {15: [(9, 999), (10, 2), (15, 4), (20, 6), (21, 999)],
                      16: [(9, 100), (21, 100)], 17: [(15, 8)]}
            rows = summarize_product(p, 680, points)
            self.assertEqual(len(rows), 27)
            row = rows[0]
            self.assertAlmostEqual(row['rms_v'], np.sqrt(13))
            self.assertAlmostEqual(row['mean_amplitude_v'], 2.5)
            self.assertAlmostEqual(row['phase_resultant'], .5)
            self.assertEqual(row['t15_median_mk'], 4)
            self.assertEqual(row['t15_observations'], 3)
            self.assertIsNone(row['t16_median_mk'])
            self.assertEqual(row['t16_observations'], 0)

    def test_reject_wrong_sign_partial_and_wrong_run(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'run00680_noise.h5'
            for sign, complete in [(1, True), (-1, False)]:
                product(p, sign=sign, complete=complete)
                with self.assertRaises(ValueError):
                    validate(p, 680)
                with self.assertRaises(ValueError):
                    summarize_product(p, 680, {})
            product(p)
            with self.assertRaises(ValueError):
                validate(p, 681)

    def test_versioned_pipeline_rejects_untagged_products(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'run00680_noise.h5'
            product(p)
            with self.assertRaisesRegex(ValueError,'product version'):
                validate(p,680,product_version='v1')
            tagged=read_results_h5(p)
            tagged['summary']['product_version']='v1'
            tagged['product_version']='v1'
            save_results_h5(p,tagged)
            validate(p,680,product_version='v1')

    def test_temperature_schema_and_complete_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'temperatures.csv'
            schema = dict(equipment='Temp_AVS', documented_layout_length_matches=True,
                          channels=[dict(index=i, column=f't{i}', unit='mK') for i in (15, 16, 17)])
            path.with_suffix('.schema.json').write_text(json.dumps({'schemas': {'avs': schema}}))
            runs = [680, 704, 727]
            with path.open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=['run', 'schema_id', 'source_status', 'time_unix', 't15', 't16', 't17'])
                writer.writeheader()
                for j, run in enumerate(runs):
                    product(root / f'run{run:05d}_noise.h5', run=run)
                    for t in [5, 15, 25]:
                        writer.writerow(dict(run=run, schema_id='avs', source_status='complete', time_unix=t,
                                             t15=10+j, t16=20+j, t17=30+j))
            grouped = temperatures_by_run(path, set(runs))
            self.assertEqual(len(grouped[680][15]), 3)
            result = report(root, path, runs)
            self.assertEqual(result['joined_rows'], 81)
            self.assertEqual(result['runs_missing_temperatures'], [])
            comparison = read_results_h5(root / 'noise_temperature_comparison.h5')
            self.assertEqual(len(comparison['tables']['bands_temperature_by_run']), 81)
            self.assertEqual(comparison['summary']['iq_sign'], -1)
            self.assertTrue(comparison['figures']['central_rms_vs_temperature.png']['data'].tobytes().startswith(b'\x89PNG'))
            for name in ['bands_temperature_by_run.csv', 'temperature_correlations.csv',
                         'central_rms_vs_temperature.png', 'band_rms_by_run.png', 'comparison_summary.json']:
                self.assertGreater((root / name).stat().st_size, 0)
            self.assertIsNone(pearson([1, 1, 1], [1, 2, 3]))
            self.assertIsNone(pearson([1, 2], [1, 2]))
            self.assertAlmostEqual(pearson([1, 2, 3], [2, 4, 6]), 1)


if __name__ == '__main__':
    unittest.main()
