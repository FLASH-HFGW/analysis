"""Aggregate the completed 24-run sample and explain the LO retuning."""
from collections import Counter, defaultdict
import csv
import hashlib
import json

import numpy as np

from report_longitudinal import baseline, read_csv, read_json, STUDY, MODES, csv_write

TABLES = STUDY/'tables'
FINAL = TABLES/'longitudinal_final'
VALIDATION = STUDY/'validation'
FS = 5_000_000
REF = 1429
RETUNE = 1670
WINDOWS = (1, 2, 5, 10, 100)
TEMPS = {'Temp_AVS:15':'Cavity', 'Temp_AVS:13':'TWPA stage', 'Temp_AVS:16':'MC plate 1',
         'Temp_AVS:17':'MC plate 2', 'Temp_Mercury:4':'4 K stage'}
PAIR_NAMES = ('TM010--TM011', 'TM010--TM012', 'TM011--TM012', 'triple')


def write(name, rows):
    assert rows
    csv_write(FINAL/f'{name}.csv', list(rows[0]), rows)


def epoch(run):
    return 'pre' if run < RETUNE else 'post'


def span(values):
    return [float(np.min(values)), float(np.median(values)), float(np.max(values))]


def normalize_kind(kind):
    return 'triple' if kind == '--'.join(MODES) else kind


def run_rows(selection):
    data = defaultdict(list)
    baseline_modes = {r['mode']: r for r in baseline()}
    freeze = read_json(STUDY/'data/frozen_thresholds.json')['1429']
    for row in selection:
        run = row['run']
        hour = row['since_start_s']/3600
        context = dict(run=run, hour=hour, epoch=epoch(run))
        folder = TABLES/'longitudinal'/str(run)
        ref = run == REF
        if ref:
            diagnostics = [baseline_modes[m] for m in MODES]
            seconds = [dict(mode=s['mode'], second=int(float(s['start_received_s'])),
                            samples=round(float(s['exposure_s'])*FS), RMS_V=s['RMS_V'],
                            T7=s['T7_count']) for s in read_csv(TABLES/'pilot1429_1s.csv')]
            hits = read_csv(TABLES/'pilot1429_T7_samples.csv')
            groups = read_csv(TABLES/'pilot1429_clusters.csv')
            pairs = read_csv(TABLES/'pilot1429_coincidence_summary.csv')
            shifts = read_csv(TABLES/'pilot1429_time_shift_controls.csv')
            thermo = [dict(t, usable=str(t['sensor_value_valid']==t['within_ADC_header_coverage']=='True'))
                      for t in read_csv(TABLES/'temperatures.csv') if t['run']=='1429']
        else:
            receipt = read_json(VALIDATION/'longitudinal'/f'{run}.json')
            assert receipt['checks_passed'] and receipt['samples'] == row['samples']
            diagnostics = receipt['modes']
            seconds = read_csv(folder/'seconds.csv')
            hits = read_csv(folder/'T7_samples.csv')
            groups = read_csv(folder/'clusters.csv')
            pairs = read_csv(folder/'coincidence_summary.csv')
            shifts = read_csv(folder/'time_shifts.csv')
            thermo = read_csv(folder/'temperatures.csv')
        mode_settings = row['lo']
        for j, d in enumerate(diagnostics):
            mode = d['mode']
            duration = row['samples']/FS
            local = [s for s in seconds if s['mode']==mode]
            global_rms = d['rms_V']
            threshold = (freeze[mode]['sigma_Rayleigh_V']*(np.sqrt(np.pi/2)+7*np.sqrt((4-np.pi)/2))
                         if ref else d['thresholds_V'][2])
            assert sum(int(s['samples']) for s in local) == row['samples']
            weights = {int(s['second']):float(s['RMS_V'])/global_rms for s in local}
            support = {i for i, factor in weights.items() if factor>=1}
            raw_hits = [h for h in hits if h['mode']==mode]
            kept = Counter()
            for hit in raw_hits:
                bin_i = int(hit['index'])//FS
                kept[bin_i] += float(hit['amplitude_V']) > threshold*max(1,weights[bin_i])
            assert len(raw_hits)==d['T7']
            for s in local:
                bin_i = int(s['second'])
                n = int(s['samples'])
                data['seconds'].append(dict(**context, mode=mode, second=bin_i, samples=n,
                                            RMS_V=float(s['RMS_V']), T3=s.get('T3',''), T5=s.get('T5',''),
                                            T7=int(s['T7']), common_support_T7=kept[bin_i],
                                            local_threshold_V=threshold*weights[bin_i],
                                            exact_local_threshold=bin_i in support))
            secondary = 0 if j==0 else mode_settings[f'freq Teled Ch{j}']
            data['modes'].append(dict(**context, mode=mode, samples=row['samples'],
                                      RMS_V=global_rms, PSD_power_V2=d['full_band_psd_power_V2'],
                                      T3=d['T3'], T5=d['T5'], T7=d['T7'],
                                      T3_per_s=d['T3']/duration, T5_per_s=d['T5']/duration,
                                      T7_per_s=d['T7']/duration, Gaussian_T7=d['matched_expected_T7'],
                                      T7_Gaussian_ratio=d['matched_T7_ratio'],
                                      T7_common_support=sum(kept.values()),
                                      T7_local_exact_exposure_fraction=sum(
                                          int(s['samples']) for s in local
                                          if int(s['second']) in support)/row['samples'],
                                      groups=d['cluster_count'], group_rate_Hz=d['cluster_rate_Hz'],
                                      fixed_IF_occupancy=d['reference_occupancy'],
                                      pump_on=row['daq']['pump_on'], pump_Hz=row['daq']['pump_hz'],
                                      pump_setting=row['daq']['pump_power_setting'],
                                      primary_LO_Hz=mode_settings['freq RS'], secondary_LO_Hz=secondary))
            group_counts = Counter()
            for group in groups:
                if group['mode']!=mode:
                    continue
                gap = int(group['gap_nonexceeding_samples' if ref else 'gap'])
                group_counts[gap, int(group['multiplicity']), int(group['peak'])//(10*FS)] += 1
            for (gap, multiplicity, time_bin), value in sorted(group_counts.items()):
                data['clusters'].append(dict(**context, mode=mode, gap=gap, multiplicity=multiplicity,
                                             received_start_s=10*time_bin, clusters=value))
            for gap in (0,2,5,8,10,25,50):
                assert sum(m*n for (g,m,t),n in group_counts.items() if g==gap)==d['T7']
        for pair in pairs:
            kind = normalize_kind(pair['kind'])
            data['coincidences'].append(dict(**context, kind=kind, window_us=int(pair['window_us']),
                count=int(pair['count']), exposure_s=float(pair['exposure_s']),
                rate_Hz=float(pair['rate_Hz']),
                shifted_mean=float(pair['time_shift_mean' if ref else 'shifted_mean']),
                shifted_min=int(pair['time_shift_min' if ref else 'shifted_min']),
                shifted_max=int(pair['time_shift_max' if ref else 'shifted_max'])))
        for shift in shifts:
            data['shifts'].append(dict(**context, kind=normalize_kind(shift['kind']),
                window_us=int(shift['window_us']), shift_samples=int(shift['shift_samples']),
                count=int(shift['count'])))
        values = defaultdict(list)
        for t in thermo:
            name = ':'.join(t['channel'].split(':')[:2])
            if t['usable']=='True' and name in TEMPS:
                values[name].append(float(t['value_K']))
        for channel, temperatures in values.items():
            low, med, high = span(temperatures)
            data['temperature'].append(dict(**context, channel=channel, stage=TEMPS[channel],
                minimum_K=low, median_K=med, maximum_K=high, readings=len(temperatures)))
    return data


def spectral_rows(selection, extras):
    controls = {r['run']:r for r in extras if r['run'] not in {s['run'] for s in selection}}
    selected = {r['run']:r for r in selection}
    candidates, track = [], []
    for run in sorted(selected.keys() | controls.keys()):
        old = TABLES/'retune'/f'{run}_full_band_lines.csv'
        rows = read_csv(old if old.exists() else TABLES/'longitudinal'/str(run)/'full_band_lines.csv')
        for r in rows:
            candidates.append(dict(run=run, epoch=epoch(run), selected=run in selected, **r))
        mode_rows = [r for r in rows if r['mode']=='TM012']
        leading = next(r for r in mode_rows if r['screen']=='full_band_rank' and abs(float(r['IF_Hz']))>=500)
        if run in selected:
            lo1 = selected[run]['lo']['freq RS']
            lo2 = selected[run]['lo']['freq Teled Ch2']
        else:
            c = controls[run]
            lo1, lo2 = c['LO_primary_Hz'], c['LO_secondary_TM012_Hz']
        center = float(leading['IF_Hz'])
        mean = float(leading['mean_PSD_V2_Hz'])
        bg = float(leading['local_background_V2_Hz'])
        row = dict(run=run, epoch=epoch(run), selected=run in selected,
                   IF_Hz=center, primary_LO_Hz=lo1, secondary_LO_Hz=lo2,
                   main_branch_RF_Hz=lo1+lo2+center, image_coordinate_RF_Hz=lo1-lo2+center,
                   mean_PSD_V2_Hz=mean, background_V2_Hz=bg, excess_bin_power_V2=(mean-bg)*100,
                   local_ratio=float(leading['mean_ratio']), occupancy=int(leading['occupancy_count']),
                   windows=int(leading['windows']))
        for model in ('fixed_IF', 'fixed_RF_nominal', 'opposite_shift'):
            values = next(r for r in mode_rows if r['screen']==model+'_local_max')
            row[f'{model}_nearby_peak_Hz'] = float(values['IF_Hz'])
            row[f'{model}_nearby_peak_ratio'] = float(values['mean_ratio'])
            row[f'{model}_nearby_peak_occupancy'] = int(values['occupancy_count'])
        track.append(row)
    return candidates, track


def aggregate(data, track):
    epochs = []
    for mode in MODES:
        for epoch_name in ('pre','post'):
            q = [r for r in data['modes'] if r['mode']==mode and r['epoch']==epoch_name]
            row = dict(mode=mode, epoch=epoch_name, runs=len(q))
            for field in ('RMS_V','PSD_power_V2','T3_per_s','T5_per_s','T7_per_s',
                          'T7_Gaussian_ratio','group_rate_Hz','T7_local_exact_exposure_fraction'):
                spread = span([r[field] for r in q])
                row.update({f'{field}_{k}':v for k,v in zip(('min','median','max'),spread)})
            epochs.append(row)
    coincidence = []
    for window in WINDOWS:
        for kind in PAIR_NAMES:
            q = [r for r in data['coincidences'] if r['window_us']==window and r['kind']==kind]
            assert len(q)==24
            controls = defaultdict(int)
            for r in data['shifts']:
                if r['kind']==kind and r['window_us']==window:
                    controls[r['shift_samples']] += r['count']
            assert len(controls)==20
            count, exposure = sum(r['count'] for r in q), sum(r['exposure_s'] for r in q)
            coincidence.append(dict(window_us=window, kind=kind, count=count, exposure_s=exposure,
                  rate_Hz=count/exposure, shifted_mean=float(np.mean(list(controls.values()))),
                  shifted_min=min(controls.values()), shifted_max=max(controls.values())))
    line_epochs = []
    for key in ('pre','post'):
        q = [r for r in track if r['epoch']==key and r['selected']]
        row = dict(epoch=key, runs=len(q))
        for field in ('IF_Hz','main_branch_RF_Hz','image_coordinate_RF_Hz','occupancy','local_ratio',
                      'mean_PSD_V2_Hz','background_V2_Hz','excess_bin_power_V2'):
            row[field] = span([r[field] for r in q])
        line_epochs.append(row)
    return epochs, coincidence, line_epochs


def main():
    selection = read_json(STUDY/'data/longitudinal_selection.json')['selected']
    assert len(selection)==24 and all(r['status'].startswith('raw_validated') for r in selection)
    FINAL.mkdir(exist_ok=True)
    data = run_rows(selection)
    candidates, track = spectral_rows(selection, read_json(VALIDATION/'retune_archive.json'))
    epochs, pair, line = aggregate(data, track)
    for name, rows in data.items():
        write(name, rows)
    write('spectral_candidates', candidates)
    write('tm012_retune_track', track)
    write('mode_epoch_summary', epochs)
    write('pooled_coincidences', pair)
    result = dict(selected_runs=[r['run'] for r in selection], retune_line_epochs=line,
                  all_sample_validations_passed=True, raw_exceptions=[], root_only_controls=[1669,1670,1671],
                  existing_pilot_reference=REF)
    (VALIDATION/'longitudinal_final.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__ == '__main__':
    main()
