"""Analytic approved-reference band predictions and archived-PSD campaign powers.

No MIDAS input, random draws, response fits or gain adjustment. New output only.
"""
from pathlib import Path
import argparse, csv, hashlib, json
import h5py
import numpy as np
from scipy.signal import firwin
from scipy.stats import pearsonr, spearmanr

MODES = ('TM010', 'TM011', 'TM012')
OFFSETS = np.array([-500000, -250000, -100000, 0, 100000, 250000, 500000])
ELECTRONIC = np.array([-1000000, -500000, -250000, -100000, 0, 100000, 250000, 500000, 1000000])
REPO = Path(__file__).resolve().parents[1]
WORK = REPO.parent / 'analysis-work/Run2'
PILOT = WORK / 'diagnostics/resonance_bank_pilot_v1_20261117'
FS = 5e6


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    with open(path) as stream:
        return list(csv.DictReader(stream))


def correlations(x, y, clock):
    """Descriptive raw, first-difference and linear-clock-controlled associations."""
    X = np.column_stack((np.ones(len(clock)), (clock-clock.mean())/clock.std()))
    residual = lambda z: z-X@np.linalg.lstsq(X, z, rcond=None)[0]
    coef = lambda a, b: {'Pearson': float(pearsonr(a, b).statistic), 'Spearman': float(spearmanr(a, b).statistic)}
    return {'raw': coef(x, y), 'first_differences': coef(np.diff(x), np.diff(y)),
            'linear_clock_residuals': coef(residual(x), residual(y))}


def reference_psd(freq, mode, configuration, physical, calibration):
    """Exactly the approved Part-I alias-folded scalar kz model, ADC V²/Hz."""
    p = physical['mode_results'][mode]
    rows = calibration['curves'][mode]
    offset = calibration['comparison'][mode]['rf_if_offset_hz']
    xx = np.array([r['rf_hz']-offset for r in rows])
    kk = np.array([r['kz_integrated'] for r in rows])*configuration['LF_data_over_cal_amplitude']
    order = np.argsort(xx)
    ki = 2*np.pi*p['f0_hz']/p['q0']
    kt = ki*(1+p['kappa1']+p['kappa2'])
    cavity_if = p['f0_hz']-configuration['primary_LO_hz']-configuration['secondary_LO_hz'][mode]
    theta = 6.62607015e-34*p['f0_hz']/np.expm1(6.62607015e-34*p['f0_hz']/(1.380649e-23*p['temperature_k']))
    thermal = np.zeros_like(freq, dtype=float)
    receiver = np.zeros_like(freq, dtype=float)
    for alias in (-1, 0, 1):
        af = freq+alias*FS
        readout2 = 10**(configuration['RF_gain_db']/10)*np.interp(af, xx[order], kk[order], left=0, right=0)**2
        thermal += configuration['resistance_ohm']*theta*ki**2*p['kappa2']/((kt/2)**2+(2*np.pi*(af-cavity_if))**2)*readout2
        receiver += configuration['resistance_ohm']*1.380649e-23*configuration['receiver_Tn_K']*readout2
    return thermal, receiver


def response_power(coefficients, centers, n):
    k = np.arange(len(coefficients))
    return np.array([abs(np.fft.fft(coefficients*np.exp(2j*np.pi*c*k/FS), n))**2 for c in centers])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fft-dir', type=Path, default=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/fft_by_run'))
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    ledger = {}
    def track(p):
        p = Path(p); ledger[str(p)] = sha(p); return p
    def load(p):
        return json.loads(track(p).read_text())
    track(__file__)
    short = load(WORK/'simulation/presentation_steps1_6_v43/metrics.json')
    cfg = short['configuration']
    physical = load(cfg['physical_parameters']); calibration = load(cfg['calibration_reconstruction'])
    fullmetrics = load(WORK/'simulation/toy_ODB_cal5_data2_LF_20261116/metrics.json')
    for key in ('physical_parameters', 'calibration_reconstruction'):
        assert ledger[cfg[key]] == fullmetrics['input_sha256'][cfg[key]]
    assert cfg['RF_gain_db'] == 103.4 and cfg['LF_data_over_cal_amplitude'] == .01 and cfg['ADC_peak_V'] == 2
    coeff = firwin(2001, 25000, fs=FS, window=('kaiser', 8.6))
    auditpath = track(PILOT/'bor_audit_680_939.h5')
    pilotpath = track(PILOT/'run00680_resonance.h5')
    oldpath = track(WORK/'reports/noise_v2_development_20261109/run680_full_published/run00680_noise_v2.h5')
    dctable = read_rows(track(WORK/'simulation/step7/dc_longterm_diagnostic/longterm.csv'))
    oldbands = read_rows(track(WORK/'reports/iq_noise_summary_v17/data/v2_campaign/band_rms_relative_to_run680.csv'))
    runids = np.arange(680, 940)
    fftpaths = [args.fft_dir/f'run{i:05d}.npz' for i in runids]
    missing = [str(p) for p in fftpaths if not p.exists()]
    if missing:
        raise FileNotFoundError('Missing archived PSDs: '+str(missing))
    table = {m: sorted([r for r in dctable if r['mode']==m], key=lambda r: int(r['run'])) for m in MODES}
    clock = np.array([float(r['time_unix']) for r in table[MODES[0]]])
    result = {'scope': '260 archived full-run PSDs; no new raw reconstruction; run680 analytic reference only',
              'runs': runids.tolist(), 'PSD_files_available': 260, 'new_raw_reads': False, 'new_simulations': False,
              'new_fits': False, 'normalization_adjusted': False, 'modes': {}, 'validation': {}, 'correlations': {},
              'estimator': 'Bilateral archived Hann coherent power divided by actual-length ENBW Hz; BOR ADC range correction once; integral against actual FIR |H|².',
              'limitations': ['PSD powers are second-order estimates, not amplitude/phase/tail measurements.',
                              'Chunk mean subtraction differs from the historical whole-run mean subtraction; do not use archived DC bins to reconstruct DC.',
                              'The BOR references are nominal settings, not tracked physical resonance fits.',
                              'Analytic reference is Gaussian before quantization. No ADC quantization noise is added or fitted.',
                              'Correlations are associations; common temporal drift and serial dependence preclude causal or independent-sample significance claims.']}
    allrows = []
    with h5py.File(auditpath) as audit, h5py.File(pilotpath) as pilot, h5py.File(oldpath) as old, h5py.File(args.output/'expectations_and_campaign.h5', 'w') as output:
        output.attrs['scope'] = result['scope']
        output.create_dataset('runs', data=runids)
        output.create_dataset('time_unix', data=clock)
        output.create_dataset('offsets_hz', data=OFFSETS)
        for mi, mode in enumerate(MODES):
            mgroup = output.create_group(mode)
            adcscale = []; centers_all = []; powers = []; historical = []; control_powers = []
            legacy = np.empty((260, 9))
            for bi, offset in enumerate(ELECTRONIC):
                ev = old[f'filtered_bands/modes/{mode}/band_{bi:02d}/events']
                base = np.average(ev['rms_v'][:]**2, weights=ev['n'][:])*.16
                rows = sorted([r for r in oldbands if r['mode']==mode and float(r['offset_hz'])==offset], key=lambda r: int(r['run']))
                assert [int(r['run']) for r in rows] == runids.tolist()
                legacy[:, bi] = base*(1+np.array([float(r['change_pct']) for r in rows])/100)**2
            shapes = set(); n_events = []; cache = {}
            for ri, (run, path) in enumerate(zip(runids, fftpaths)):
                meta = audit[f'acquisition_metadata/run{run:05d}']
                assert meta['fs_hz'][()] == FS and meta['iq_sign'][()] == -1
                mm = meta[f'modes/{mode}']; center = float(mm['center_digital_IQ_hz'][()])
                peak = float(mm['ADC_peak_V'][()]); centers = center+OFFSETS
                with np.load(track(path)) as archive:
                    arr = archive[f'fft_amp_mode{mi}_SPECs'].astype(float)
                    n = len(arr); assert float(archive['fs']) == FS and np.isfinite(arr).all() and (arr>=0).all()
                    assert int(archive['n_fft_done']) == 1000
                    n_events.append(int(archive['n_fft_done'])); shapes.add(n)
                    window = np.hanning(n)
                    enbw = FS*np.sum(window**2)/window.sum()**2
                    psd = np.fft.ifftshift(arr)*(peak/5)**2/enbw
                    key = (n, center)
                    if key not in cache:
                        cache[key] = (response_power(coeff, centers, n), response_power(coeff, ELECTRONIC, n))
                    power = cache[key][0]@psd*(FS/n)
                    controls = cache[key][1]@psd*(FS/n)
                    # Shared window +1 MHz is explicitly re-evaluated if BOR center changes.
                    shared = float(controls[8])
                    control_powers.append(controls)
                powers.append(power); historical.append(shared); centers_all.append(centers); adcscale.append(peak)
            P = np.array(powers); historical = np.array(historical)
            error = historical/legacy[:, 8]-1
            span = (np.ptp(error))*100
            drift = (error[-1]-error[0])*100
            # Predeclared engineering gate, not fitted acceptance: <=1% every run, <=0.25 percentage-point end-to-end drift.
            accepted = bool(np.max(abs(error)) < .01 and abs(drift) < .25)
            result['validation'][mode] = {'shared_1MHz_power_error_percent_median': float(np.median(error)*100),
                'min': float(error.min()*100), 'max': float(error.max()*100),
                'end_minus_start_percentage_points': float(drift), 'span_percentage_points': float(span),
                'Pearson_error_vs_time': float(pearsonr(clock, error).statistic),
                'Spearman_error_vs_time': float(spearmanr(clock, error).statistic),
                'acceptance_max_power_error_percent': 1., 'acceptance_max_end_drift_percentage_points': .25,
                'accepted': accepted, 'actual_fft_lengths': sorted(shapes), 'SPEC_per_archive': sorted(set(n_events)),
                'runs_outside_1pct': runids[np.abs(error)>.01].tolist(),
                'absolute_error_percentiles': dict(zip(['50','90','95','99','100'], np.percentile(abs(error)*100,[50,90,95,99,100]).tolist())),
                'qualified_descriptive_use': True,
                'decision': 'Use as power-only descriptive proxy with explicit estimator discrepancies and flagged runs. The strict 1% engineering screen is not passed for TM010; no empirical correction or rescaling is applied.'}
            (args.output/'PSD_gate_progress.json').write_text(json.dumps(result['validation'],indent=2)+'\n')
            print(mode, 'archived PSD control', json.dumps(result['validation'][mode]), flush=True)
            for key, value in [('power_ADC_V2', P), ('electronic_power_ADC_V2', legacy), ('centers_IF_hz', centers_all),
                               ('shared_window_power_relative_error', error), ('ADC_peak_V', adcscale), ('archived_electronic_power_ADC_V2', control_powers), ('electronic_control_relative_error', np.array(control_powers)/legacy-1)]:
                mgroup.create_dataset(key, data=value)
            for ri, run in enumerate(runids):
                for bi, off in enumerate(OFFSETS):
                    allrows.append({'run': int(run), 'time_unix': float(clock[ri]), 'mode': mode, 'offset_hz': int(off),
                        'center_IF_hz': float(centers_all[ri][bi]), 'power_ADC_V2': float(P[ri, bi]),
                        'RMS_ADC_V': float(np.sqrt(P[ri, bi])), 'RMS_change_from_run680_percent': float(100*(np.sqrt(P[ri, bi]/P[0, bi])-1)),
                        **{f'T{s}_mK': float(table[mode][ri][f't{s}_mK']) for s in [15,16,17]}})
            result['validation'][mode]['nonzero_electronic_controls'] = {str(int(off)): {'median_power_error_percent': float(np.median(np.array(control_powers)[:,bi]/legacy[:,bi]-1)*100), 'max_abs_power_error_percent': float(np.max(abs(np.array(control_powers)[:,bi]/legacy[:,bi]-1))*100)} for bi,off in enumerate(ELECTRONIC) if off!=0}
            # Analytical reference integrated on the actual implemented band responses.
            n = 2**18; freq = np.fft.fftfreq(n, 1/FS); centers = np.array(centers_all[0])
            sc, se = reference_psd(freq, mode, cfg, physical, calibration)
            response = response_power(coeff, centers, n)
            pc = response@sc*(FS/n); pe = response@se*(FS/n); pt = pc+pe
            sc2, se2 = reference_psd(np.fft.fftfreq(2*n, 1/FS), mode, cfg, physical, calibration)
            refined = response_power(coeff, centers, 2*n)@(sc2+se2)*(FS/(2*n))
            assert np.max(abs(refined/pt-1)) < 1e-4
            # Verify the unmodified reference against Part-I full-band expected powers.
            full_expected = short['metrics'][mode]['total_RMS_expected_ADC_V']**2
            assert np.isclose((sc+se).sum()*FS/n, full_expected, rtol=1e-10)
            tg = mgroup.create_group('analytic_reference')
            for key, value in [('thermal_power_ADC_V2', pc), ('electronic_power_ADC_V2', pe), ('total_power_ADC_V2', pt)]:
                tg.create_dataset(key, data=value)
            bout = FS/20; nf = 16384; ff = np.fft.fftfreq(nf, 1/bout)
            for bi, center in enumerate(centers):
                bg = tg.create_group(f'band_{bi:02d}')
                g = pilot[f'filter_banks/resonance_ROI/modes/{mode}/band_{bi:02d}']
                lag = g['selected_lag_s'][:]
                spec = (sc+se)*response[bi]
                cov = np.fft.ifft(spec)*FS
                idx = np.rint(lag*FS).astype(int)
                g1 = cov[idx]*np.exp(-2j*np.pi*center*lag)/cov[0].real
                # Decimation aliases; digital input periodicity retained. No additional analog LPF.
                so = np.zeros(nf)
                for alias in range(-10,10):
                    delta = ff+alias*bout
                    fi = (center+delta+FS/2)%FS-FS/2
                    cc, ee = reference_psd(fi, mode, cfg, physical, calibration)
                    # Periodic interpolation of a dense numerical FIR response avoids huge outer matrices.
                    hf = abs(np.fft.fft(coeff, 2**19))**2
                    gain = np.interp((delta%FS)/FS*len(hf), np.arange(len(hf)+1), np.r_[hf,hf[0]])
                    so += (cc+ee)*gain
                # Expected periodic Hann Welch smoothing, unit-sum spectral window.
                window = np.hanning(nf); kernel = abs(np.fft.fft(window))**2
                welch = np.fft.ifft(np.fft.fft(so)*np.fft.fft(kernel/kernel.sum())).real
                for key, value in [('output_frequency_hz', ff), ('output_PSD_ADC_V2_Hz', so),
                                   ('output_Welch_expected_ADC_V2_Hz', np.maximum(welch,0)), ('lag_s', lag), ('g1', g1)]:
                    bg.create_dataset(key, data=value)
            measured = np.array([pilot[f'filter_banks/resonance_ROI/modes/{mode}/band_{bi:02d}/moments_ADC/total_squared_v2'][()] for bi in range(7)])
            sigma = np.array([np.sqrt(pilot[f'filter_banks/resonance_ROI/modes/{mode}/band_{bi:02d}/moments_ADC/ac_squared_v2'][()]/2) for bi in range(7)])
            side = lambda x: float(x[3]/x[[0,1,2,4,5,6]].mean())
            sym = lambda x: {str(off): float(x[3+j]/x[3-j]) for j, off in enumerate([100000,250000,500000], 1)}
            result['modes'][mode] = {'centers_IF_hz': centers.tolist(), 'cavity_fit_IF_hz': short['metrics'][mode]['final_IF_hz'],
                'toy_RMS_ADC_V': np.sqrt(pt).tolist(), 'data_RMS_ADC_V': np.sqrt(measured).tolist(),
                'toy_sigma_q_ADC_V': np.sqrt(pt/2).tolist(), 'data_moment_sigma_q_ADC_V': sigma.tolist(),
                'thermal_RMS_ADC_V': np.sqrt(pc).tolist(), 'electronic_RMS_ADC_V': np.sqrt(pe).tolist(),
                'thermal_power_fraction': (pc/pt).tolist(), 'data_over_toy_RMS': np.sqrt(measured/pt).tolist(),
                'central_over_mean_six': {'data': side(measured), 'toy': side(pt)},
                'symmetric_ratios': {'data': sym(measured), 'toy': sym(pt)},
                'integration_refinement_max_relative_difference': float(np.max(abs(refined/pt-1))),
                'PSD_proxy_outlier_runs_over_0p1pct': runids[abs(error)>.001].tolist(),
                'quantization_reference_note': 'Continuous Gaussian prediction; additive independent uniform quantization estimate is not applied. Central-band approximate quantization fraction bound documented separately.',
                'approx_white_quantization_power_over_toy': float((2*(4/65535)**2/12)*np.sum(coeff**2)/pt[3])}
            result['correlations'][mode] = {f'offset_{int(off)}': {f'T{s}': correlations(P[:, bi], np.array([float(r[f't{s}_mK']) for r in table[mode]]), clock) for s in [15,16,17]} for bi,off in enumerate(OFFSETS)}
        result['between_mode_correlations'] = {}
        for bank in ['resonance', 'electronic']:
            array = {m: output[m+'/power_ADC_V2' if bank=='resonance' else m+'/electronic_power_ADC_V2'][:] for m in MODES}
            central = 3 if bank=='resonance' else 4
            result['between_mode_correlations'][bank] = {a+'_'+b: correlations(array[a][:,central], array[b][:,central], clock) for a,b in [('TM010','TM011'),('TM010','TM012'),('TM011','TM012')]}
    with open(args.output/'campaign_band_powers.csv','w') as stream:
        writer = csv.DictWriter(stream,fieldnames=allrows[0]);writer.writeheader();writer.writerows(allrows)
    assert all(sha(p)==v for p,v in ledger.items())
    result['input_sha256'] = ledger
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('COMPLETE',args.output,flush=True)

if __name__=='__main__':
    main()
