#!/usr/bin/env python3
"""Compare fixed symmetric IQ power bands, without assuming a resonance peak.

FFT arrays store mean squared Fourier amplitudes, not complex coefficients.
The frequency axis uses the actual FFT length (legacy metadata is off by one).
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

MODES = ('TM010', 'TM011', 'TM012')


def band_statistics(frequency, power, center, offset, width, dc_guard):
    values = []
    for shift in (-offset, 0., offset):
        mask = ((np.abs(frequency - center - shift) <= width / 2)
                & (np.abs(frequency) > dc_guard))
        if mask.sum() < 3:
            raise ValueError('Band outside coverage or fewer than three valid bins')
        values.append(float(np.mean(power[mask], dtype=np.float64)))
    left, middle, right = values
    return dict(left_power=left, center_power=middle, right_power=right,
                asymmetry=(right-left)/(right+left) if right+left else float('nan'),
                wings_over_center=(right+left)/(2*middle) if middle else float('nan'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--runs', type=Path, required=True)
    p.add_argument('--center-hz', type=float, default=0.)
    p.add_argument('--offsets-hz', type=float, nargs='+', default=[100e3, 250e3, 500e3, 1e6])
    p.add_argument('--width-hz', type=float, default=50e3)
    p.add_argument('--dc-guard-hz', type=float, default=1000.)
    a = p.parse_args()
    if (not all(np.isfinite(x) for x in [a.center_hz, a.width_hz, a.dc_guard_hz, *a.offsets_hz])
            or a.width_hz <= 0 or a.dc_guard_hz < 0
            or any(x <= a.width_hz for x in a.offsets_hz)):
        p.error('Require finite parameters, positive width, nonnegative guard and offsets > width')
    runs = sorted({int(x.split('#')[0].strip()) for x in a.runs.read_text().splitlines()
                   if x.split('#')[0].strip()})
    rows, missing = [], []
    for run in runs:
        path = a.input / f'run{run:05d}.npz'
        if not path.exists():
            missing.append(run)
            continue
        with np.load(path, allow_pickle=False) as d:
            for mode, name in enumerate(MODES):
                power = np.asarray(d[f'fft_amp_mode{mode}_SPECs'], dtype=float)
                if power.ndim != 1 or not np.all(np.isfinite(power)) or np.any(power < 0):
                    raise ValueError(f'Invalid power: {path}, {name}')
                fs = float(d['fs'])
                if not np.isfinite(fs) or fs <= 0:
                    raise ValueError(f'Invalid sampling rate: {path}')
                freq = np.fft.fftshift(np.fft.fftfreq(power.size, 1/fs))
                for offset in a.offsets_hz:
                    rows.append(dict(run=run, mode=name, offset_hz=offset,
                        **band_statistics(freq, power, a.center_hz, offset,
                                          a.width_hz, a.dc_guard_hz)))
    if not rows:
        p.error('No available spectra')
    a.output.mkdir(parents=True, exist_ok=True)
    with (a.output/'sidebands.csv').open('w') as stream:
        w = csv.DictWriter(stream, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 3, figsize=(16, 11), sharex=True)
    summary = {}
    for mode, name in enumerate(MODES):
        summary[name] = {}
        for offset in a.offsets_hz:
            rr = [r for r in rows if r['mode'] == name and r['offset_hz'] == offset]
            x = [r['run'] for r in rr]
            label = f'{offset/1e3:g} kHz'
            for side, style in [('left_power','--'), ('right_power','-')]:
                y = np.sqrt([r[side] for r in rr]); y /= np.median(y)
                axes[mode,0].plot(x, y, style, label=label+(' L' if style=='--' else ' R'), lw=.8)
            for col, key in [(1,'asymmetry'), (2,'wings_over_center')]:
                axes[mode,col].plot(x, [r[key] for r in rr], label=label, lw=.8)
            summary[name][label] = dict(asymmetry_min=min(r['asymmetry'] for r in rr),
                asymmetry_max=max(r['asymmetry'] for r in rr))
        for col, title in enumerate(('sqrt(mean band power) / campaign median', '(R-L)/(R+L)', '(R+L)/(2C)')):
            axes[mode,col].set_title(name+' · '+title)
            axes[mode,col].set_xlabel('Run (acquisition order; not elapsed time)')
            axes[mode,col].grid(alpha=.25)
        axes[mode,0].legend(fontsize=6, ncol=2)
        axes[mode,1].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(a.output/'sidebands.png', dpi=160); plt.close(fig)
    report = dict(requested_runs=len(runs), available_runs=len(runs)-len(missing), missing_runs=missing,
        center_hz=a.center_hz, width_hz=a.width_hz, dc_guard_hz=a.dc_guard_hz,
        offsets_hz=a.offsets_hz, summary=summary,
        limitations=['Power-only products: spectral phase unavailable.',
          'Band amplitudes are sqrt(mean squared FFT coefficient), not calibrated integrated RMS.',
          'Zero denotes baseband origin, not a measured resonance center.',
          'Asymmetry can also reflect electronics; no resonance shift or thermal causality inferred.',
          'Run spectra average the full run; no within-run evolution or timestamps inferred.'])
    (a.output/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
