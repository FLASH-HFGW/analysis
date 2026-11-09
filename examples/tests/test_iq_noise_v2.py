"""DC decomposition, nominal dB conversion and continuous v2 filtering."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np
from scipy.signal import lfilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from iq_noise_v2 import ComplexMoments, load_calibration, trend_diagnostics
from analyze_midas_iq_noise import FilteredBandChecks, MODES
from iq_noise_io import save_results_h5, read_results_h5
from report_noise_v2 import report

CONFIG = Path(__file__).resolve().parents[2]/'config/noise_calibration_v2.json'


class V2Tests(unittest.TestCase):
    def test_stable_global_complex_variance_preserves_between_spec_changes(self):
        z = np.r_[np.full(31, 1e6+2e6j), np.full(73, 1e6+2e6j+1-2j)]
        moments = ComplexMoments()
        for chunk in np.split(z, [31, 40]):
            moments.update(chunk)
        result = moments.export(10.)
        self.assertAlmostEqual(result['ac_squared_v2'], np.mean(abs(z-z.mean())**2), places=10)
        self.assertGreater(result['ac_squared_v2'], 0)
        self.assertAlmostEqual(result['mean_i_input_v'], z.mean().real/10)
        self.assertAlmostEqual(result['ac_squared_input_v2'], result['ac_squared_v2']/100)
        self.assertAlmostEqual(result['total_squared_v2'], result['dc_squared_v2']+result['ac_squared_v2'])

    def test_gain_stages_and_no_double_counted_frequency_calibration(self):
        c = load_calibration(CONFIG)
        self.assertAlmostEqual(c['voltage_gain'], 10**(143/20))
        self.assertAlmostEqual(c['squared_voltage_gain'], 10**(143/10), delta=1.)
        config = json.loads(CONFIG.read_text())
        for field, value in [('total_db', 103.), ('frequency_response_applied', True)]:
            changed = dict(config, **{field:value})
            with tempfile.TemporaryDirectory() as directory:
                p = Path(directory)/'gain.json'
                p.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    load_calibration(p)

    def test_filter_matches_independent_run_centered_causal_reference(self):
        args = SimpleNamespace(fs=10000., iq_sign=-1, input_range=5., band_offsets_hz=[1000.],
                               band_centers_hz=[0.,0.,0.], band_width_hz=500., band_taps=51, band_decimation=2)
        rng = np.random.default_rng(14)
        frames = rng.integers(-100,100,(557,8),dtype=np.int16)
        frames[:203,:6] += 700
        frames[203:,:6] += 1100
        z = {mode:(frames[:,i]+1j*args.iq_sign*frames[:,q])*(10/65535) for mode,(i,q) in MODES.items()}
        moments = {mode:ComplexMoments() for mode in MODES}
        for mode in MODES:
            for chunk in np.split(z[mode],[203]):
                moments[mode].update(chunk)
        filters = FilteredBandChecks(args)
        filters.remove_run_dc(moments,load_calibration(CONFIG))
        filters.update(frames[:203],0,0,10)
        filters.update(frames[203:],1,1,20)
        exported = filters.export()
        n = np.arange(len(frames))
        take = (n>=50)&(n%2==0)
        for (mode,index),band in filters.filters.items():
            centered = z[mode]-z[mode].mean()
            mixed = centered*np.exp(-2j*np.pi*np.remainder(n*band.center/args.fs,1.))
            expected = lfilter(band.h,[1.],mixed)[take]
            actual = exported['modes'][mode][f'band_{index:02d}']
            expected_moments = ComplexMoments()
            expected_moments.update(expected)
            self.assertAlmostEqual(actual['complex_moments']['total_squared_v2'],
                                   expected_moments.export()['total_squared_v2'],places=14)
            self.assertEqual(actual['complex_moments']['n'],len(expected))
            np.testing.assert_allclose(actual['events']['rms_input_v'],
                                       actual['events']['rms_v']/10**(143/20))

    def test_time_conditioning_and_degenerate_temperature(self):
        rng = np.random.default_rng(4)
        x = np.arange(50.)
        t = -x+rng.normal(size=len(x))
        y = 4*x+2*t
        result = trend_diagnostics(y,t,x)
        self.assertAlmostEqual(result['r_temperature_after_linear_time'],1.)
        self.assertIsNone(trend_diagnostics(y,-x,x)['r_temperature_after_linear_time'])

    def test_complete_report_preserves_common_trend_and_rejects_partial_runs(self):
        calibration=load_calibration(CONFIG)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            temperatures=root/'temperatures.csv'
            temperatures.write_text('run,schema_id,source_status,time_unix,t15,t16,t17\n'+
                ''.join(f'{680+i},avs,complete,{100+i*10}, {40-i}, {32-i}, {39-i}\n' for i in range(5)))
            temperatures.with_suffix('.schema.json').write_text(json.dumps(dict(schemas=dict(avs=dict(
                equipment='Temp_AVS',documented_layout_length_matches=True,
                channels=[dict(index=i,column=f't{i}',unit='mK') for i in (15,16,17)])))))
            products=[]
            for i in range(5):
                moments=ComplexMoments()
                moments.update(np.array([1+2j,2+3j])*(1+i*.01))
                cfg=dict(fs_hz=5e6,taps=2001,decimation=20,width_hz=5e4,
                         offsets_hz=[-1e6,-5e5,-2.5e5,-1e5,0.,1e5,2.5e5,5e5,1e6],centers_hz=[0.,0.,0.])
                mode_moments={m:moments.export(calibration['voltage_gain']) for m in MODES}
                bands={m:{f'band_{j:02d}':dict(offset_hz=offset,complex_moments=moments.export())
                       for j,offset in enumerate(cfg['offsets_hz'])} for m in MODES}
                payload=dict(schema_version=1,product_version='v2',
                    summary=dict(input=f'run{680+i:05d}.mid.gz',product_version='v2',reached_eof=True,
                        status='success',iq_sign=-1,events=[dict(midas_timestamp=100+i*10)]),
                    dc_removed=dict(calibration=calibration,modes=mode_moments),
                    filtered_bands=dict(config=cfg,modes=bands))
                path=root/f'run{680+i:05d}_noise_v2.h5'
                save_results_h5(path,payload)
                products.append(path)
            summary=report(products,temperatures,root/'report')
            self.assertEqual(summary['runs'],list(range(680,685)))
            result=read_results_h5(root/'report/noise_temperature_comparison_v2.h5')
            rows=result['tables']['dc_ac_temperature_by_run']
            for row in rows:
                self.assertAlmostEqual(row['side_relative_after_common'],1.)
                self.assertAlmostEqual(row['common_side_amplitude_ratio'],1+(row['run']-680)*.01)
            payload['summary']['reached_eof']=False
            save_results_h5(products[-1],payload)
            with self.assertRaisesRegex(ValueError,'complete'):
                report(products,temperatures,root/'partial')


if __name__ == '__main__':
    unittest.main()
