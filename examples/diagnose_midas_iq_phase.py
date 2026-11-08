#!/usr/bin/env python3
"""Confronto del binning di fase e delle fasce di ampiezza su dati MIDAS reali."""
import argparse
import json
from pathlib import Path

import numpy as np

from analyze_midas_iq_noise import MODES, positive_int


def wrap(phase):
    return (phase + np.pi) % (2 * np.pi) - np.pi


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('summary', type=Path, help='JSON prodotto da analyze_midas_iq_noise.py')
    parser.add_argument('--file', type=Path, help='Override del percorso MIDAS nel JSON')
    parser.add_argument('--max-events', type=positive_int, help='Default: stessi eventi del riepilogo')
    parser.add_argument('--out-dir', type=Path)
    args = parser.parse_args()
    from iq_noise_io import read_summary
    meta = read_summary(args.summary)
    source = args.file or Path(meta['input'])
    limit = args.max_events or len(meta['events'])
    out = args.out_dir or args.summary.parent
    out.mkdir(parents=True, exist_ok=True)
    scale = 2 * meta['input_range_v'] / 65535
    definitions = {'512': (512, 0.), '1024': (1024, 0.),
                   '2048': (2048, 0.), '1024_shifted': (1024, np.pi / 1024)}
    states = {}
    for mode in MODES:
        stat = meta['modes'][mode]
        a_rms = np.hypot(stat['mean_amplitude_v'], stat['amplitude_noise_rms_v'])
        states[mode] = {'reference': None, 'amplitude_rms_v': float(a_rms),
            'hist': {key: np.zeros(n, dtype=np.int64) for key, (n, _) in definitions.items()},
            'bands': np.zeros((3, 1024), dtype=np.int64), 'n': 0, 'zeros': 0,
            'octant_counts': np.zeros(8, dtype=np.int64)}
    import midas.file_reader
    reader = midas.file_reader.MidasFile(str(source))
    seen = 0
    try:
        for event in reader:
            if event.header.is_midas_internal_event() or 'SPEC' not in event.banks:
                continue
            if seen < len(meta['events']) and int(event.header.serial_number) != meta['events'][seen]['serial']:
                raise ValueError('La sequenza degli eventi non corrisponde al riepilogo')
            raw = np.asarray(event.banks['SPEC'].data, dtype=np.uint16)
            if not raw.size or raw.size % 8:
                raise ValueError('Bank SPEC non valido')
            frames = raw.view(np.int16).reshape(-1, 8)
            for mode, (ci, cq) in MODES.items():
                st = states[mode]
                i = frames[:, ci].astype(float) * scale
                q = frames[:, cq].astype(float) * scale * meta['iq_sign']
                amp = np.hypot(i, q)
                valid = amp > 0
                theta = np.arctan2(q[valid], i[valid])
                st['zeros'] += int((~valid).sum())
                st['n'] += len(theta)
                if st['reference'] is None and len(theta):
                    st['reference'] = float(theta[0])
                if not len(theta):
                    continue
                phase = wrap(theta - st['reference'])
                for key, (bins, shift) in definitions.items():
                    edges = np.linspace(-np.pi + shift, np.pi + shift, bins + 1)
                    shifted = wrap(phase - shift) + shift
                    st['hist'][key] += np.histogram(shifted, bins=edges)[0]
                # Fasce riferite all'ampiezza RMS globale, non al rumore RMS.
                av = amp[valid]
                band_id = np.searchsorted([0.5 * st['amplitude_rms_v'],
                                          1.5 * st['amplitude_rms_v']], av, side='right')
                for band in range(3):
                    st['bands'][band] += np.histogram(phase[band_id == band], bins=1024, range=(-np.pi, np.pi))[0]
                st['octant_counts'] += np.histogram(theta, bins=8, range=(-np.pi, np.pi))[0]
            seen += 1
            if seen % 10 == 0:
                print('Letti %d/%d eventi SPEC' % (seen, limit), flush=True)
            if seen >= limit:
                break
    finally:
        close = getattr(reader, 'close', None)
        if close is not None:
            close()
    if not seen:
        raise RuntimeError('Nessun evento SPEC')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 3, figsize=(19, 11), squeeze=False)
    saved = {}
    result = {'input': str(source), 'events': seen, 'phase': 'wrapped relative to first valid sample; direct atan2, no unwrap',
              'band_definition': 'A < 0.5*A_rms; 0.5*A_rms <= A < 1.5*A_rms; A >= 1.5*A_rms; A_rms from input summary', 'modes': {}}
    try:
        for row, (mode, st) in enumerate(states.items()):
            details = {'valid_samples': st['n'], 'zero_amplitude_samples': st['zeros'],
                       'phase_reference_rad': st['reference'], 'amplitude_rms_v': st['amplitude_rms_v'],
                       'band_samples': st['bands'].sum(axis=1).tolist()}
            for key, (bins, shift) in definitions.items():
                edges = np.linspace(-np.pi + shift, np.pi + shift, bins + 1)
                counts = st['hist'][key]
                assert counts.sum() == st['n']
                saved[mode + '_' + key + '_counts'] = counts
                saved[mode + '_' + key + '_edges_rad'] = edges
                ax = axes[row, 0] if key in ('512', '1024', '2048') else axes[row, 1]
                ax.stairs(counts / max(1, counts.mean()), edges, label=key, alpha=0.8)
            edges = np.linspace(-np.pi, np.pi, 1025)
            c = st['hist']['1024']
            axes[row, 1].stairs(c / max(1, c.mean()), edges, label='1024 original', alpha=0.8)
            for band, label in enumerate(('A < 0.5 A_rms', '0.5–1.5 A_rms', 'A >= 1.5 A_rms')):
                counts = st['bands'][band]
                axes[row, 2].stairs(counts / max(1, counts.mean()), edges,
                                    label='%s (N=%d)' % (label, counts.sum()), alpha=0.8)
                saved[mode + '_band%d_counts' % band] = counts
            saved[mode + '_band_edges_rad'] = edges
            for col, title in enumerate(('Numero di bin', 'Bordi spostati di mezzo bin', 'Fasce di ampiezza')):
                ax = axes[row, col]
                ax.set(title=mode + ': ' + title, xlabel='Wrapped delta phase [rad]',
                       ylabel='Counts / uniform expectation', xlim=(-np.pi, np.pi))
                ax.axhline(1, color='gray', linewidth=0.5)
                for angle in np.arange(-4, 5) * np.pi / 4:
                    if st['reference'] is not None:
                        ax.axvline(float(wrap(angle - st['reference'])), color='gray', alpha=0.3, linewidth=0.5)
                ax.legend(fontsize=7)
            result['modes'][mode] = details
        fig.suptitle('%s — %d events; all samples; linear Y; gray lines: ADC axes/diagonals' % (source.name, seen))
        fig.tight_layout()
        stem = out / (source.name.split('.mid')[0] + '_phase_diagnostic')
        fig.savefig(str(stem) + '.png', dpi=150)
    finally:
        plt.close(fig)
    np.savez_compressed(str(stem) + '.npz', **saved)
    Path(str(stem) + '.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Risultati: %s' % stem, flush=True)


if __name__ == '__main__':
    main()
