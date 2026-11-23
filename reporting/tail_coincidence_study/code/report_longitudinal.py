"""Build the longitudinal checkpoint from compact data, without archive reads."""
import csv
import hashlib
import json
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from stream_longitudinal import MODES, STUDY, csv_write, gaussian_tail
sys.path.insert(0, str(STUDY.parent))
from slide_deck import Deck, export

TABLES = STUDY/'tables'
VALIDATION = STUDY/'validation'
FIGURES = STUDY/'figures'/'longitudinal'
PRESENTATION = STUDY/'presentation'/'longitudinal'


def read_csv(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def read_json(path):
    return json.loads(path.read_text())


def baseline():
    inventory = next(r for r in read_json(STUDY/'data/inventory.json')['runs'] if r['run'] == 1429)
    receipt = read_json(VALIDATION/'pilot1429.json')
    thresholds = read_json(STUDY/'data/frozen_thresholds.json')['1429']
    counts = read_json(STUDY/'data/longitudinal_reference.json')['counts']
    spectrum = read_csv(TABLES/'spectral_window_series.csv')
    occupancy = read_csv(TABLES/'spectral_persistence.csv')
    result = []
    for j, mode in enumerate(MODES):
        moments = inventory['fullrun_attributes'][mode]
        sigma = thresholds[mode]['sigma_Rayleigh_V']
        radius = sigma*(np.sqrt(np.pi/2)+7*np.sqrt((4-np.pi)/2))
        expected = receipt['samples']*gaussian_tail(radius, moments, 8192)
        power = [float(r['window_mean_power_V2']) for r in spectrum
                 if r['run']=='1429' and r['mode']==mode]
        occ = next(r for r in occupancy if r['run']=='1429' and r['mode']==mode)
        n = receipt['T7_totals'][j]
        assert n == counts[mode]['T7']
        result.append(dict(mode=mode, T3=counts[mode]['T3'], T5=counts[mode]['T5'], rms_V=moments['rms_V'], full_band_psd_power_V2=np.mean(power),
                           T7=n, T7_rate_Hz=n/inventory['duration_s'], matched_expected_T7=expected,
                           matched_T7_ratio=n/expected, cluster_count=receipt['main_cluster_counts'][j],
                           cluster_rate_Hz=receipt['main_cluster_counts'][j]/inventory['duration_s'],
                           strongest_occupancy=float(occ['occupancy_ratio_gt3']),
                           reference_occupancy=float(occ['reference_bin_occupancy'])))
    return result


def main():
    data = read_json(STUDY/'data/longitudinal_selection.json')
    FIGURES.mkdir(parents=True, exist_ok=True)
    deck = Deck()

    def slide(title, subtitle, notes):
        return deck.new(title, subtitle, source='FLASH Dataset 2 · ADC-plane observables',
                        notes=notes)

    def text(title, subtitle, lines):
        page = slide(title, subtitle, ' '.join(lines))
        deck.bullets(page, .65, 1.85, 12, lines, size=20, gap=.22)

    def plot(key, title, subtitle, ylabel, draw, notes):
        fig, axes = plt.subplots(1, 3, figsize=(15, 5.2), layout='constrained')
        for mode, ax in zip(MODES, axes):
            draw(mode, ax)
            ax.set(title=mode, ylabel=ylabel)
            ax.grid(alpha=.2)
            if ax.get_legend_handles_labels()[1]:
                ax.legend(fontsize=8)
        path = FIGURES/f'{key}.png'
        fig.savefig(path, dpi=145)
        plt.close(fig)
        page = slide(title, subtitle, notes)
        deck.image(page, .5, 1.72, 12.3, 4.95, path)

    rows, pair_rows, seconds, temp_rows = [], [], [], []
    processed = []
    for selection in data['selected']:
        run = selection['run']
        hour = selection['since_start_s']/3600
        dest = TABLES/'longitudinal'/str(run)
        receipt_file = VALIDATION/'longitudinal'/f'{run}.json'
        if run == 1429:
            modes = baseline()
            pair = read_csv(TABLES/'pilot1429_coincidence_summary.csv')
            secs = [dict(mode=r['mode'], second=r['start_received_s'], RMS_V=r['RMS_V'],
                         T7_rate_Hz=float(r['T7_count'])/float(r['exposure_s']))
                    for r in read_csv(TABLES/'pilot1429_1s.csv')]
            temps = [dict(channel=r['channel'], time_unix=r['time_unix'], value_K=r['value_K'],
                          usable=str(r['sensor_value_valid']==r['within_ADC_header_coverage']=='True'))
                     for r in read_csv(TABLES/'temperatures.csv') if r['run']=='1429']
        elif receipt_file.exists():
            modes = read_json(receipt_file)['modes']
            pair = read_csv(dest/'coincidence_summary.csv')
            secs = read_csv(dest/'seconds.csv')
            temps = read_csv(dest/'temperatures.csv')
            processed.append(run)
        else:
            continue
        for d in modes:
            rows.append(dict(run=run, hour=hour, **d))
        for r in pair:
            pair_rows.append(dict(r, run=run, hour=hour))
        seconds.extend(dict(r, run=run) for r in secs)
        thermometer_groups = {}
        for r in temps:
            channel = ':'.join(r['channel'].split(':')[:2])
            if r['usable']=='True' and channel in ('Temp_AVS:15', 'Temp_AVS:13', 'Temp_AVS:16',
                                                     'Temp_AVS:17', 'Temp_Mercury:4'):
                thermometer_groups.setdefault(channel, []).append(float(r['value_K']))
        temp_rows.extend(dict(run=run, hour=hour, channel=ch, median_K=np.median(vals),
                              minimum_K=min(vals), maximum_K=max(vals), readings=len(vals))
                         for ch, vals in thermometer_groups.items())
    csv_write(TABLES/'longitudinal_summary.csv', ['run','hour',*sorted(set().union(*(r.keys() for r in rows))-{'run','hour'})], rows)
    csv_write(TABLES/'longitudinal_thermal_summary.csv',
              ['run','hour','channel','median_K','minimum_K','maximum_K','readings'], temp_rows)
    text('FLASH Run3-B longitudinal checkpoint', 'Hourly sample of the reconstructed portion of Dataset 2', [
        f'{len(data["selected"])} selected runs through {data["last_eligible"]}; validated Run 1429 plus new runs {", ".join(map(str, processed))}.',
        'Selection uses archived acquisition timestamps. Three requested controls and the last eligible run are retained.',
        f'{data["remaining_raw_bytes"]/1e9:.2f} GB of new input in the full selection. Remaining batches await review.',
        'Run 680 remains the historical no-TWPA reference in the earlier checkpoint.'])
    for key, title, label in (
        ('rms_V','Full-run RMS','RMS (V)'),
        ('full_band_psd_power_V2','Full-band spectral power','Mean integrated PSD (V²)'),
        ('T7_rate_Hz','T7 exceedance rate','T7 samples/s'),
        ('matched_T7_ratio','T7 excess relative to matched Gaussian','Observed / expected samples'),
        ('cluster_rate_Hz','T7 cluster rates','Groups/s'),
        ('reference_occupancy','Spectral persistence','Fraction of 1 s windows'),
    ):
        subtitle = {
            'matched_T7_ratio':'Gaussian marginal matched to full-run I/Q mean and covariance',
            'reference_occupancy':'Fixed reference bins near −28 kHz, +1.25 MHz and −492.75 kHz',
            'full_band_psd_power_V2':'Native 100 Hz products, 209 complete one-second windows',
        }.get(key, 'Elapsed hours from the archived Dataset 2 BOR timestamp')
        def draw(mode, ax):
            q = [r for r in rows if r['mode']==mode]
            ax.plot([r['hour'] for r in q], [r[key] for r in q], 'o-', color='#007F86')
            ax.set_xlabel('Dataset 2 time (h)')
        plot(key,title,subtitle,label,draw,
             'Ratios and rates are descriptive. Correlated samples and acquisition-domain clustering require dedicated null controls.')
    def coincidence_draw(mode, ax):
        for kind in ('TM010--TM011','TM010--TM012','TM011--TM012','triple'):
            if mode not in kind and kind!='triple':
                continue
            q = [r for r in pair_rows if r['kind'] in (kind, '--'.join(MODES) if kind=='triple' else kind)
                 and int(r['window_us'])==100]
            ax.plot([r['hour'] for r in q], [float(r['rate_Hz']) for r in q], 'o-', label=kind)
        ax.set_xlabel('Dataset 2 time (h)')
    plot('coincidences','Cross-mode coincidence rates','100 µs inclusive peak-tuple window','Tuples/s',
         coincidence_draw,'Tables also preserve 1, 2, 5 and 10 µs checks and 20 time shifts per window. Triples are shared across the three panels.')
    def within_draw(mode, ax):
        for run in [1429,*processed]:
            q = [r for r in seconds if r['mode']==mode and r['run']==run]
            ax.plot([float(r['second']) for r in q], [float(r['T7_rate_Hz']) for r in q],
                    alpha=.65, label=str(run))
        ax.set_xlabel('Received-sample time (s)')
    plot('within_run','Within-run T7 variability','One-second bins with the final residual weighted by its measured exposure',
         'T7 samples/s',within_draw,'Curves are aligned by received sample origin for visualization. They represent different acquisitions.')
    labels = {'Temp_AVS:15':'Cavity', 'Temp_AVS:13':'TWPA stage', 'Temp_AVS:16':'MC plate 1',
              'Temp_AVS:17':'MC plate 2', 'Temp_Mercury:4':'4 K stage'}
    def temp_draw(mode, ax):
        for channel,label in labels.items():
            q = [r for r in temp_rows if r['channel']==channel]
            if q:
                ax.errorbar([r['hour'] for r in q], [r['median_K'] for r in q],
                            yerr=[[r['median_K']-r['minimum_K'] for r in q],
                                  [r['maximum_K']-r['median_K'] for r in q]],
                            fmt='o-', label=label)
        ax.set(xlabel='Dataset 2 time (h)', yscale='log')
    plot('temperature','Archived cryogenic temperatures','Shared sensors in each panel · run medians with within-run ranges',
         'Temperature (K)',temp_draw,'Roles follow the documented mapping with Run3 wiring unverified. The 4 K reading is stage thermometry. Invalid or unsupported values are excluded.')
    text('Configuration and timing', 'Interpretation stays in the received-sample domain', [
        'Selected acquisitions have archived pump-on TWPA settings at 7.891 GHz and power setting −6.1. The setting is not calibrated power.',
        'The archived LO retuning at Run 1670 separates two RF-coordinate epochs. The current streaming batch precedes that change.',
        'PPS intervals are checked against recorded ROOT data. Absolute UTC and channel/group delays are uncalibrated.',
        'Time-shift controls and covariance-matched Gaussian counts are descriptive. Thermal and spectral associations do not establish causality.'])
    export(deck,PRESENTATION,version='tail_coincidence_longitudinal',prepared='23 November 2026')
    slides_md = PRESENTATION/'slides_en.md'
    slides_md.write_text(slides_md.read_text().replace('24–25 July 2026', '20–21 November 2026'))
    paths = [*FIGURES.glob('*.png'), *PRESENTATION.glob('*'), *TABLES.glob('longitudinal*.csv'),
             *TABLES.glob('longitudinal/*/*.csv'), *VALIDATION.glob('longitudinal/*.json'),
             *STUDY.glob('code/*longitudinal.py'), STUDY/'data/longitudinal_selection.json',
             STUDY/'code/algorithms.py', STUDY.parent/'slide_deck.py']
    manifest = dict(reference_checkpoint='30fd84ac09ef1644708e2117041b7b9f0a21c9e3',
                    processed=processed, selected=[r['run'] for r in data['selected']],
                    files=[dict(path=str(p.relative_to(STUDY.parent)), size=p.stat().st_size,
                                sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                                local_only=PRESENTATION in p.parents)
                           for p in sorted(paths) if p.is_file()])
    (STUDY/'longitudinal_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__ == '__main__':
    main()
