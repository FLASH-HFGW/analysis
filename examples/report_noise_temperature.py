#!/usr/bin/env python3
"""Descriptive per-run filtered-IQ/temperature comparison, without p-values.

Use only complete I-iQ products. Temperature medians use actual observations
of the same run inside the SPEC timestamp span; no interpolation/extrapolation.
"""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path

import h5py
import numpy as np
from scipy.stats import rankdata

from iq_noise_io import read_summary, build_results, save_results_h5
from plot_thermometers_history import SENSORS


def temperatures_by_run(path, runs):
    metadata = json.loads(path.with_suffix('.schema.json').read_text())
    mappings = {}
    for identifier, schema in metadata['schemas'].items():
        if schema['equipment'].casefold() != 'temp_avs':
            continue
        if not schema.get('documented_layout_length_matches'):
            raise ValueError('Unverified AVS channel layout')
        columns = {}
        for index, _ in SENSORS:
            channels = [c for c in schema['channels'] if c['index'] == index]
            if len(channels) != 1 or channels[0]['unit'].strip().casefold() != 'mk':
                raise ValueError(f'Invalid temperature channel {index}')
            columns[index] = channels[0]['column']
        mappings[identifier] = columns
    if not mappings:
        raise ValueError('No verified Temp_AVS schema')
    data = defaultdict(lambda: defaultdict(list))
    with path.open(newline='') as stream:
        for row in csv.DictReader(stream):
            run = int(row['run'])
            if run not in runs or row['source_status'] != 'complete':
                continue
            columns = mappings.get(row['schema_id'])
            if not columns:
                continue
            timestamp = float(row['time_unix'])
            for index, column in columns.items():
                value = float(row[column]) if row[column] else np.nan
                if np.isfinite(value) and np.isfinite(timestamp):
                    data[run][index].append((timestamp, value))
    return data


def pearson(x, y):
    x, y = np.asarray(x), np.asarray(y)
    valid = np.isfinite(x) & np.isfinite(y)
    x, y = x[valid], y[valid]
    if len(x) < 3 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def write_csv(path, rows):
    if not rows:
        raise ValueError(f'No rows for {path}')
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def summarize_product(path, run, temperatures, product_version=None):
    summary = read_summary(path)
    if product_version and summary.get('product_version') != product_version:
        raise ValueError(f'Wrong scientific product version: {path}')
    if summary.get('iq_sign') != -1 or not summary.get('reached_eof') or summary.get('status') != 'success':
        raise ValueError(f'Incomplete or wrong IQ convention: {path}')
    if Path(summary['input']).name.split('.mid')[0] != f'run{run:05d}':
        raise ValueError(f'Wrong run: {path}')
    rows = []
    with h5py.File(path, 'r') as source:
        config = source['filtered_bands/config']
        if config['iq_sign'][()] != -1:
            raise ValueError('Filtered bands do not use I-iQ')
        for mode in ('TM010', 'TM011', 'TM012'):
            for band in source[f'filtered_bands/modes/{mode}'].values():
                events = band['events']
                n = events['n'][:]
                rms = events['rms_v'][:]
                if not len(n) or n.sum() <= 0 or not np.all(np.isfinite(rms)):
                    raise ValueError(f'Missing filtered samples: {path}')
                phase = events['phase_resultant'][:] * np.exp(1j * events['phase_mean_rad'][:])
                delta = events['increment_resultant'][:] * np.exp(1j * events['increment_mean_rad'][:])
                weights = events['increment_pairs'][:]
                mean_delta = np.average(delta, weights=weights)
                timestamps = events['event_timestamp_unix'][:]
                start, stop = float(timestamps.min()), float(timestamps.max())
                row = dict(run=run, mode=mode, offset_hz=float(band['offset_hz'][()]),
                           spec_start_unix=start, spec_stop_unix=stop,
                           spec_midpoint_unix=(start + stop) / 2,
                           samples=int(n.sum()), events=len(n),
                           rms_v=float(np.sqrt(np.average(rms**2, weights=n))),
                           mean_amplitude_v=float(np.average(events['mean_amplitude_v'][:], weights=n)),
                           phase_resultant=float(abs(np.average(phase, weights=n))),
                           increment_mean_rad=float(np.angle(mean_delta)),
                           increment_resultant=float(abs(mean_delta)),
                           event_rms_cv=float(rms.std() / rms.mean()))
                for index, _ in SENSORS:
                    points = [(t, v) for t, v in temperatures.get(index, []) if start <= t <= stop]
                    values = [v for _, v in points]
                    row[f't{index}_median_mk'] = float(np.median(values)) if values else None
                    row[f't{index}_min_mk'] = float(np.min(values)) if values else None
                    row[f't{index}_max_mk'] = float(np.max(values)) if values else None
                    row[f't{index}_observations'] = len(points)
                rows.append(row)
    return rows


def report(output, temperatures, runs, product_version=None):
    data = temperatures_by_run(temperatures, set(runs))
    rows = []
    for run in runs:
        rows.extend(summarize_product(output / f'run{run:05d}_noise.h5', run, data[run], product_version))
    write_csv(output / 'bands_temperature_by_run.csv', rows)
    correlations = []
    for mode in ('TM010', 'TM011', 'TM012'):
        for offset in sorted({r['offset_hz'] for r in rows}):
            group = [r for r in rows if r['mode'] == mode and r['offset_hz'] == offset]
            for index, label in SENSORS:
                valid = [r for r in group if r[f't{index}_median_mk'] is not None]
                x = [r[f't{index}_median_mk'] for r in valid]
                elapsed = [r['spec_midpoint_unix'] for r in valid]
                for metric in ('rms_v', 'mean_amplitude_v', 'phase_resultant'):
                    y = [r[metric] for r in valid]
                    correlations.append(dict(mode=mode, offset_hz=offset, sensor=label, metric=metric,
                                             runs=len(valid), pearson_r=pearson(x, y),
                                             spearman_rho=pearson(rankdata(x), rankdata(y)),
                                             metric_vs_time_r=pearson(elapsed, y),
                                             temperature_vs_time_r=pearson(elapsed, x)))
    write_csv(output / 'temperature_correlations.csv', correlations)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 3, figsize=(15, 11), squeeze=False)
    for im, mode in enumerate(('TM010', 'TM011', 'TM012')):
        for it, (index, label) in enumerate(SENSORS):
            ax = axes[im, it]
            valid = [r for r in rows if r['mode'] == mode and r['offset_hz'] == 0
                     and r[f't{index}_median_mk'] is not None]
            x = [r[f't{index}_median_mk'] for r in valid]
            y = [r['rms_v'] * 1000 for r in valid]
            if valid:
                ax.scatter(x, y)
                for r, xx, yy in zip(valid, x, y):
                    ax.annotate(str(r['run']), (xx, yy), fontsize=7, xytext=(3, 3), textcoords='offset points')
            ax.set(xlabel=label, ylabel=f'{mode} central-band RMS [mV]')
            ax.grid(alpha=.25)
    fig.suptitle('I-iQ; 50 kHz central band; temperatures observed within each run')
    fig.tight_layout()
    fig.savefig(output / 'central_rms_vs_temperature.png', dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    for ax, mode in zip(axes, ('TM010', 'TM011', 'TM012')):
        for offset in sorted({r['offset_hz'] for r in rows}):
            group = sorted((r for r in rows if r['mode'] == mode and r['offset_hz'] == offset), key=lambda r: r['run'])
            ax.plot([r['run'] for r in group], [r['rms_v'] * 1000 for r in group], '.-', label=f'{offset/1000:g} kHz')
        ax.set_ylabel(f'{mode} RMS [mV]')
        ax.grid(alpha=.25)
    axes[0].legend(ncol=3, fontsize=8)
    axes[-1].set_xlabel('Run')
    fig.tight_layout()
    fig.savefig(output / 'band_rms_by_run.png', dpi=160)
    plt.close(fig)
    missing = sorted({r['run'] for r in rows if any(r[f't{i}_observations'] == 0 for i, _ in SENSORS)})
    result = dict(runs=runs, iq_sign=-1, bands_per_mode=9, joined_rows=len(rows),
                  temperature_csv=str(temperatures), runs_missing_temperatures=missing,
                  interpretation=[
                      'Exploratory comparison across runs; correlation does not establish causation.',
                      'Temperature medians use only finite observed AVS values of the same run within SPEC timestamp bounds.',
                      'No interpolation or extrapolation. Missing coverage is excluded explicitly.',
                      'No p-values: filtered samples and successive runs are correlated; 12 runs are a small pilot.',
                      'Time correlations are included to expose confounding by the common time trend.',
                      'Many modes, bands and metrics are explored; large coefficients need independent confirmation.',
                      'Central band includes DC offsets. Phase resultant is dimensionless, not evidence of a physical signal.',
                      'Phase concentration is combined with sample-count weights; filtered amplitudes are assumed nonzero.'])
    if product_version:
        result['product_version'] = product_version
    (output / 'comparison_summary.json').write_text(json.dumps(result, indent=2) + '\n')
    import hashlib
    packaged = build_results(result, {})
    if product_version:
        packaged['product_version'] = product_version
    packaged['tables'] = {'bands_temperature_by_run': rows, 'temperature_correlations': correlations}
    packaged['figures'] = {name: {'format': 'png', 'data': np.frombuffer((output / name).read_bytes(), dtype=np.uint8)}
                           for name in ('central_rms_vs_temperature.png', 'band_rms_by_run.png')}
    packaged['provenance'] = {'temperature_csv_sha256': hashlib.sha256(temperatures.read_bytes()).hexdigest(),
                              'temperature_schema_sha256': hashlib.sha256(temperatures.with_suffix('.schema.json').read_bytes()).hexdigest()}
    save_results_h5(output / 'noise_temperature_comparison.h5', packaged)
    print(f'Temperature comparison: {output}', flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('temperatures', type=Path)
    parser.add_argument('--runs', type=int, nargs='+', required=True)
    args = parser.parse_args()
    report(args.output, args.temperatures, args.runs)
