"""Bounded Run3-B extraction using the checkpoint's amplitude and peak-tuple rules."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys
import time
import resource

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import ndtr
from scipy.ndimage import median_filter

from algorithms import clusters, coincidences
from select_longitudinal import STUDY
from retune_spectra import screen

sys.path.insert(0, str(STUDY.parents[1] / 'examples'))
from analyze_midas_iq_v3 import bank, decode
from iq_products import open_product, write_json
from midas.file_reader import MidasFile

MODES = ('TM010', 'TM011', 'TM012')
FS = 5_000_000
GAPS = (10, 8, 8)
SCALE = 4 / 65535
MARGIN = 5000
ORDERS = np.array([3, 5, 7])


def fit_sigma(edges, counts):
    low, high = edges[:-1], edges[1:]
    init = np.sqrt(np.average(((low + high) / 2)**2, weights=counts) / 2)

    def objective(log_sigma):
        variance = np.exp(2 * log_sigma)
        return -np.dot(counts, -low**2/(2*variance) +
                       np.log(-np.expm1(-(high**2-low**2)/(2*variance))))

    fit = minimize_scalar(objective, bounds=(np.log(init/5), np.log(init*5)),
                          method='bounded', options={'xatol': 1e-12})
    assert fit.success
    return np.exp(fit.x)


def gaussian_tail(radius, moments, angles):
    # Same radial integral as the archived matched-marginal diagnostic.
    mu = np.array([moments['mean_I_V'], -moments['mean_Qhardware_V']])
    cross = -moments['cov_I_Qhardware_V2']
    cov = np.array([[moments['var_I_V2'], cross], [cross, moments['var_Q_V2']]])
    assert np.all(np.linalg.eigvalsh(cov) > 0)
    inv = np.linalg.inv(cov)
    theta = np.arange(angles)*2*np.pi/angles
    unit = np.column_stack((np.cos(theta), np.sin(theta)))
    a = np.einsum('ni,ij,nj->n', unit, inv, unit)
    b = unit @ inv @ mu
    c = mu @ inv @ mu
    h = radius - b/a
    integral = np.exp(-.5*(c-b*b/a)) * (
        np.exp(-.5*a*h*h)/a + b/a*np.sqrt(2*np.pi/a)*ndtr(-np.sqrt(a)*h))
    return integral.mean()/np.sqrt(np.linalg.det(cov))


def csv_write(path, fields, rows):
    with path.open('w') as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)


def archived_inputs(row, spectral_observer=None):
    started = time.monotonic()
    with open_product(row['root_path']) as product:
        root = product.file
        assert product.run == row['run'] and product.fs == FS
        adc = root['timing/digitizer_events'][:]
        pps = root['timing/pps'][:]
        archived_breaks = root['quality/breaks'][:]
        thresholds, diagnostics, spectra, temperatures = [], [], [], []
        full_band = []
        freq = product.edges[:-1] + product.widths/2
        for mode, focus in zip(MODES, (-28000, 1250000, -492750)):
            moments = dict(root[f'statistics/{mode}'].attrs)
            hist = f'histograms/{mode}'
            counts = root[f'{hist}/amplitude_counts'][:]
            assert counts.sum() == moments['temporal_samples'] == row['samples']
            sigma = fit_sigma(root[f'{hist}/amplitude_edges_v'][:], counts)
            thresholds.append(sigma*(np.sqrt(np.pi/2)+ORDERS*np.sqrt((4-np.pi)/2)))
            wp = root[f'spectra/{mode}/window_psd'][:].astype(float)
            assert wp.shape == (209, 50000)
            mean = wp.mean(axis=0)
            bg = np.maximum(median_filter(mean, size=201, mode='nearest'), 1e-30)
            broadband = abs(freq) >= 100000
            scale = np.median(wp[:, broadband]/bg[broadband], axis=1)
            if spectral_observer is not None:
                spectral_observer(mode, freq, wp, bg, scale)
            full_band.extend(screen(mode, freq, wp, bg, scale))
            nearby = np.flatnonzero(abs(freq-focus) <= 1000)
            best = nearby[np.argmax((mean/bg)[nearby])]
            ref = np.argmin(abs(freq-focus))
            best_ratio = wp[:, best]/(scale*bg[best])
            ref_ratio = wp[:, ref]/(scale*bg[ref])
            power = wp @ product.widths
            diagnostics.append(dict(mode=mode, sigma=sigma, rms_V=moments['rms_V'],
                                    full_band_psd_power_V2=power.mean(),
                                    reference_bin_hz=freq[ref], reference_occupancy=np.mean(ref_ratio>3),
                                    strongest_bin_hz=freq[best], strongest_occupancy=np.mean(best_ratio>3),
                                    moments=moments))
            spectra.extend(dict(mode=mode, received_s=i, power_V2=p,
                                best_ratio=b, reference_ratio=r)
                           for i, (p, b, r) in enumerate(zip(power, best_ratio, ref_ratio)))
        for name, unit, timestamps, values in product.temperatures():
            if ':'.join(name.split(':')[:2]) not in {
                'Temp_AVS:13', 'Temp_AVS:15', 'Temp_AVS:16', 'Temp_AVS:17', 'Temp_Mercury:4'
            }:
                continue
            temperatures.extend(dict(channel=name, time_unix=int(t), value_K=float(v) *
                                     (0.001 if unit == 'mK' else 1),
                                     usable=bool(np.isfinite(v) and v > 0 and
                                                 product.time_start <= t < product.time_stop))
                                for t, v in zip(timestamps, values))
        requested = root.file.file.source.num_requested_bytes
    return np.array(thresholds), diagnostics, spectra, temperatures, adc, pps, archived_breaks, requested, time.monotonic()-started, full_band


def stream(row, thresholds, adc, pps, archived_breaks, *, bin_samples=FS, observer=None):
    n = row['samples']
    bins = (n + bin_samples - 1)//bin_samples
    counts = np.zeros((3, 3, bins), dtype=np.int64)
    powers = np.zeros((3, bins))
    exposure = np.zeros(bins, dtype=np.int64)
    indices, amplitudes = [[], [], []], [[], [], []]
    source = Path(row['raw_path'])
    before = source.stat()
    assert (before.st_size, before.st_mtime_ns) == (row['raw_bytes'], row['raw_mtime_ns'])
    received = event_count = 0
    pulses, pps_breaks = [], []
    eor = False
    started = time.monotonic()
    a_io = proc_io()
    with MidasFile(str(source), use_numpy=True) as reader:
        odb = reader.get_bor_odb_dump().data
        settings = odb['Equipment']['NetBox']['Settings']
        assert int(odb['Runinfo']['Run number']) == row['run']
        assert settings['Channel_range_mV'][:6] == [2000]*6
        assert float(settings['Sampling_rate_MS'])*1e6 == FS
        for event in reader:
            header = event.header
            if header.event_id == 0x8001:
                eor = True
            if header.event_id != 1:
                continue
            assert not eor
            layout, channels = decode(event.banks)
            size = len(channels[0])
            expected = adc[event_count]
            assert layout == 'SPE' and len(channels) >= 6
            assert (received, size, header.serial_number, header.timestamp) == tuple(
                int(expected[key]) for key in ('received_index','samples','serial','header_unix_s'))
            if event_count:
                assert header.serial_number == last_serial + 1
            try:
                words = bank(event.banks, 'SPGP', {6: 4})
                if (words.size % 2 or np.any(words[::2] >= size) or
                        np.any(words[1::2] == 0) or
                        np.any(np.diff(words[::2].astype(np.int64)) <= 0)):
                    raise ValueError('invalid SPGP index/width pairs')
            except ValueError as error:
                pps_breaks.append((header.serial_number, str(error)))
            else:
                pulses.extend((received+int(i), int(w)) for i, w in words.reshape(-1, 2))
            cuts = np.unique(np.r_[0, np.arange(bin_samples-received%bin_samples, size, bin_samples), size])
            positions = (received + cuts[:-1])//bin_samples
            exposure[positions] += np.diff(cuts)
            for j in range(3):
                amplitude = np.hypot(channels[2*j].astype(float)*SCALE,
                                     channels[2*j+1].astype(float)*SCALE)
                powers[j, positions] += np.add.reduceat(amplitude**2, cuts[:-1])
                for k in (0, 1):
                    counts[j,k,positions] += np.add.reduceat(amplitude > thresholds[j,k], cuts[:-1], dtype=np.int64)
                hits = np.flatnonzero(amplitude > thresholds[j,2])
                indices[j].append(received + hits)
                amplitudes[j].append(amplitude[hits])
                counts[j,2] += np.bincount((received+hits)//bin_samples, minlength=bins)
                if observer is not None:
                    observer(j, received, channels[2*j], channels[2*j+1], amplitude, cuts, positions)
            received += size
            event_count += 1
            last_serial = header.serial_number
            if event_count % 200 == 0:
                print(row['run'], event_count, round(time.monotonic()-started, 1), flush=True)
        # Explicit EOF read also ensures the gzip trailer is checked.
        assert reader.file.read(1) == b''
    after = source.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    assert eor and received == n == exposure.sum() and event_count == len(adc)
    assert pulses == [(int(p['received_index']), int(p['width_samples'])) for p in pps]
    assert pps_breaks == [(int(b['serial']), b['reason'].decode()) for b in archived_breaks]
    intervals = np.diff([i for i, _ in pulses])
    assert np.all(intervals > 0)
    assert np.all(counts[:,0] >= counts[:,1]) and np.all(counts[:,1] >= counts[:,2])
    a_end = proc_io()
    receipt = dict(run=row['run'], compressed_bytes=before.st_size,
                   raw_wall_s=time.monotonic()-started, events=event_count, samples=received,
                   EOR=eor, gzip_CRC=True, serial_gaps=0, ADC_V_per_count=SCALE,
                   PPS_intervals=dict(Counter(map(int, intervals))), PPS_matches_ROOT=True, PPS_rejected_records=pps_breaks,
                   utc_anchored=False, channel_delay_calibrated=False,
                   process_io={key:a_end[key]-a_io[key] for key in a_end},
                   peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return counts, powers, exposure, list(map(np.concatenate, indices)), list(map(np.concatenate, amplitudes)), receipt


def proc_io():
    return {key: int(value) for key, value in
            (line.split(':') for line in Path('/proc/self/io').read_text().splitlines())}


def group_products(indices, amplitudes, n):
    peaks, groups = [], []
    for j, mode in enumerate(MODES):
        for gap in (0, 2, 5, 8, 10, 25, 50):
            collection = clusters(indices[j], amplitudes[j], gap)
            assert sum(g['multiplicity'] for g in collection) == len(indices[j])
            groups.extend(dict(mode=mode, gap=gap, **g) for g in collection)
            if gap == GAPS[j]:
                peaks.append(np.array([g['peak'] for g in collection], dtype=np.int64))
    shifts = [int(FS*v)+137 for v in (.1,.2,.5,1,2,5,10,20,40,60)]
    tuples, controls, summary = [], [], []
    for window in (1, 2, 5, 10, 100):
        data = {}
        for shift in [0, *shifts, *(-s for s in shifts)]:
            shifted = [np.sort((p + offset) % n) for p, offset in zip(peaks, (0,shift,-shift))]
            selected = [p[(p >= MARGIN) & (p < n-MARGIN)] for p in shifted]
            pairs, triples = coincidences(selected, window*5)
            for modes, hits in [*pairs.items(), ((0,1,2), triples)]:
                kind = '--'.join(MODES[j] for j in modes)
                if shift:
                    data[kind][1].append(len(hits))
                    controls.append(dict(window_us=window, kind=kind, shift_samples=shift, count=len(hits)))
                else:
                    data[kind] = (len(hits), [])
                    for hit in hits:
                        samples = [int(selected[j][k]) for j,k in zip(modes,hit)]
                        tuples.append(dict(window_us=window, kind=kind, indices=samples,
                                           separation_us=(max(samples)-min(samples))/5))
        for kind, (count, shifted_counts) in data.items():
            duration = (n-2*MARGIN)/FS
            summary.append(dict(window_us=window, kind=kind, count=count, exposure_s=duration,
                                rate_Hz=count/duration, shifted_mean=np.mean(shifted_counts),
                                shifted_min=min(shifted_counts), shifted_max=max(shifted_counts)))
    return peaks, groups, tuples, controls, summary


def process(row):
    run = row['run']
    dest = STUDY/'tables'/'longitudinal'/str(run)
    receipt_file = STUDY/'validation'/'longitudinal'/f'{run}.json'
    if run == 1429 or receipt_file.exists():
        return
    thresholds, diagnostics, spectra, temps, adc, pps, archived_breaks, requested, root_wall, full_band = archived_inputs(row)
    counts, powers, exposure, indices, amps, receipt = stream(row, thresholds, adc, pps, archived_breaks)
    totals = counts.sum(axis=2)
    peaks, groups, tuples, controls, coincidence_summary = group_products(indices, amps, row['samples'])
    seconds, hits = [], []
    for j, mode in enumerate(MODES):
        d = diagnostics[j]
        rms = np.sqrt(powers[j].sum()/exposure.sum())
        np.testing.assert_allclose(rms, d['rms_V'], rtol=1e-6)
        assert totals[j,2] == len(indices[j])
        assert np.all(np.diff(indices[j]) > 0) and np.all(amps[j] > thresholds[j,2])
        expected = row['samples']*gaussian_tail(thresholds[j,2], d['moments'], 4096)
        refined = row['samples']*gaussian_tail(thresholds[j,2], d.pop('moments'), 8192)
        np.testing.assert_allclose(expected, refined, rtol=1e-9)
        d.update(T3=int(totals[j,0]), T5=int(totals[j,1]), T7=int(totals[j,2]),
                 T7_rate_Hz=totals[j,2]*FS/row['samples'], matched_expected_T7=expected,
                 matched_T7_ratio=totals[j,2]/expected, cluster_count=len(peaks[j]),
                 cluster_rate_Hz=len(peaks[j])*FS/row['samples'], thresholds_V=thresholds[j].tolist())
        hits.extend(dict(mode=mode, index=i, amplitude_V=a) for i,a in zip(indices[j], amps[j]))
        seconds.extend(dict(mode=mode, second=i, samples=n, RMS_V=np.sqrt(powers[j,i]/n),
                            T3=counts[j,0,i], T5=counts[j,1,i], T7=counts[j,2,i],
                            T7_rate_Hz=counts[j,2,i]*FS/n) for i,n in enumerate(exposure))
    dest.mkdir(parents=True, exist_ok=True)
    for name, fields, rows in (
        ('seconds', list(seconds[0]), seconds), ('T7_samples', ['mode','index','amplitude_V'], hits),
        ('clusters', ['mode','gap','start','end','peak','maximum','multiplicity','duration_samples'], groups),
        ('coincidences', ['window_us','kind','indices','separation_us'], tuples),
        ('time_shifts', list(controls[0]), controls),
        ('coincidence_summary', list(coincidence_summary[0]), coincidence_summary),
        ('full_band_lines', list(full_band[0]), full_band),
        ('spectral_seconds', list(spectra[0]), spectra),
        ('temperatures', ['channel','time_unix','value_K','usable'], temps),
    ):
        csv_write(dest/f'{name}.csv', fields, rows)
    receipt.update(root_requested_bytes=requested, root_wall_s=root_wall, modes=diagnostics,
                   checks_passed=True, waveforms_retained=False)
    receipt_file.parent.mkdir(parents=True, exist_ok=True)
    pending = receipt_file.with_suffix('.tmp')
    write_json(pending, receipt)
    pending.replace(receipt_file)
    print('VALIDATED', run, totals.tolist(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', type=int, nargs='+')
    args = parser.parse_args()
    if len(set(args.runs)) != len(args.runs) or len(args.runs) > 5:
        parser.error('Specify up to five distinct selected runs')
    selected = {r['run']: r for r in json.loads(
        (STUDY/'data/longitudinal_selection.json').read_text())['selected']}
    for run in args.runs:
        process(selected[run])


if __name__ == '__main__':
    main()
