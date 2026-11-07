#!/usr/bin/env python3
"""Aggrega risultati IQ completi; crea anche riferimenti fissi da run pilota."""
import argparse
import csv
import json
import math
from pathlib import Path
import re

import numpy as np

from iq_noise_statistics import MODES, SIGMAS, SCHEMA, config_id, merge_moments, empty_episodes, merge_episodes, tail


def read_inputs(paths):
    found = []
    for path in paths:
        found.extend(sorted(path.rglob('run*_noise.json')) if path.is_dir() else [path])
    if not found:
        raise ValueError('Nessun riepilogo trovato')
    rows, ids = [], set()
    for path in found:
        data = json.loads(path.read_text())
        name = Path(data['input']).name.split('.mid')[0]
        if name in ids:
            raise ValueError('Run duplicato: ' + name)
        ids.add(name)
        rows.append((path, data, name))
    return sorted(rows, key=lambda row: row[2])


def create_reference(rows, output):
    first = rows[0][1]
    ref = {'schema': SCHEMA, **{key: first[key] for key in ('fs_hz', 'input_range_v', 'iq_sign')},
           'provenance': [str(path) for path, _, _ in rows],
           'purpose': 'fixed baseline for comparable thresholds; not recomputed per target run', 'modes': {}}
    for _, data, _ in rows:
        if any(data[key] != ref[key] for key in ('fs_hz', 'input_range_v', 'iq_sign')):
            raise ValueError('Run pilota con configurazioni incompatibili')
    for mode in MODES:
        n, mean, m2 = 0, 0., 0.
        for _, data, _ in rows:
            nb = int(data['samples'])
            st = data['modes'][mode]
            if nb <= 0:
                raise ValueError('Run pilota vuoto')
            mb, rms = st['mean_amplitude_v'], st['amplitude_noise_rms_v']
            if not np.isfinite(mb) or not np.isfinite(rms) or rms < 0:
                raise ValueError('Momenti pilota non validi')
            n, mean, m2 = merge_moments(n, mean, m2, nb, mb, nb * rms**2)
        ref['modes'][mode] = {'samples': n, 'mean_amplitude_v': mean,
                               'amplitude_noise_rms_v': math.sqrt(m2 / n)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(ref, indent=2, allow_nan=False) + '\n')
    print('Riferimento fisso scritto in', output)


def aggregate(rows, out, allow_partial=False, expected_runs=None):
    if expected_runs:
        expected = {int(line.split('#')[0].strip()) for line in expected_runs.read_text().splitlines()
                    if line.split('#')[0].strip()}
        actual = set()
        for _, _, name in rows:
            match = re.fullmatch(r'run(\d+)', name)
            if not match:
                raise ValueError('Identificativo run non riconosciuto: ' + name)
            actual.add(int(match[1]))
        if actual != expected:
            raise ValueError('Lista run diversa: mancanti=%s, extra=%s' % (sorted(expected-actual), sorted(actual-expected)))
    arrays, combined, table, run_names = {}, {}, [], []
    config = None
    for path, data, name in rows:
        if data.get('status') != 'success' or 'global_statistics' not in data:
            raise ValueError('Output precedente o non riuscito; rieseguire analisi: ' + str(path))
        if not data.get('reached_eof') and not allow_partial:
            raise ValueError('Run limitato/incompleto (usare --allow-partial solo intenzionalmente): ' + name)
        gs = data['global_statistics']
        if gs.get('schema') != SCHEMA or gs.get('config_id') != config_id(gs['config']):
            raise ValueError('Schema o firma configurazione non valida: ' + name)
        if config is None:
            config = gs['config']
        elif config_id(config) != config_id(gs['config']):
            raise ValueError('Configurazioni, riferimenti o ritardi incompatibili: ' + name)
        if any(data[key] != config[key] for key in ('fs_hz', 'input_range_v', 'iq_sign')):
            raise ValueError('Metadati incoerenti: ' + name)
        with np.load(path.with_suffix('.npz'), allow_pickle=False) as z:
            for key in ('amplitude_edges_v', 'iq_edges_v', 'phase_edges_rad'):
                edge = z[key]
                if key in arrays and not np.array_equal(arrays[key], edge):
                    raise ValueError('Bin diversi: ' + name + ': ' + key)
                arrays[key] = edge.copy()
            for mode in MODES:
                st = gs['modes'][mode]
                if st['n'] != data['samples'] or st['n'] <= 0:
                    raise ValueError('Conteggio campioni incoerente: ' + name)
                for suffix, expected in [('amp', st['n']), ('iq', st['n']), ('phase', st['valid_phase'])] + [
                        ('delta_' + lag, v['pairs']) for lag, v in st['delta_circular'].items()]:
                    key = 'global_' + mode + '_' + suffix
                    counts = z[key]
                    if counts.dtype.kind not in 'iu' or np.any(counts < 0) or int(counts.sum()) != expected:
                        raise ValueError('Istogramma incoerente: ' + name + ': ' + key)
                    arrays[key] = arrays.get(key, np.zeros_like(counts)) + counts
                if mode not in combined:
                    combined[mode] = {'n': 0, 'mean': 0., 'm2': 0., 'valid_phase': 0,
                        'exceedances': {kind: {k: empty_episodes() for k in values}
                                        for kind, values in st['thresholds_v'].items()},
                        'delta_circular': {lag: {'pairs': 0, 'cos_sum': 0., 'sin_sum': 0.}
                                           for lag in st['delta_circular']}}
                acc = combined[mode]
                acc['n'], acc['mean'], acc['m2'] = merge_moments(
                    acc['n'], acc['mean'], acc['m2'], st['n'], st['mean'], st['m2'])
                acc['valid_phase'] += st['valid_phase']
                row = {'run': name, 'mode': mode, 'complete': bool(data['reached_eof']),
                       'samples': st['n'], 'acquired_duration_s': st['n'] / config['fs_hz'],
                       'mean_amplitude_v': st['mean'], 'amplitude_noise_rms_v': math.sqrt(st['m2']/st['n'])}
                for kind, stats in st['exceedances'].items():
                    for sigma, ep in stats.items():
                        merge_episodes(acc['exceedances'][kind][sigma], ep)
                        prefix = kind + '_' + sigma + 'sigma_'
                        row[prefix+'threshold_v'] = st['thresholds_v'][kind][sigma]
                        for key in ('samples_above', 'episodes', 'peak_v'):
                            row[prefix+key] = ep[key]
                        row[prefix+'fraction'] = ep['samples_above'] / st['n']
                        row[prefix+'episodes_per_acquired_s'] = ep['episodes'] * config['fs_hz'] / st['n']
                        row[prefix+'longest_s'] = ep['longest_samples'] / config['fs_hz']
                for lag, stats in st['delta_circular'].items():
                    for key, value in stats.items():
                        acc['delta_circular'][lag][key] += value
                table.append(row)
        run_names.append(name)
    result = {'schema': SCHEMA, 'config': config, 'config_id': config_id(config), 'runs': run_names,
              'partial_runs': [name for _, d, name in rows if not d['reached_eof']],
              'acquired_duration_s': sum(d['samples']/config['fs_hz'] for _, d, _ in rows),
              'local_thresholds': 'sum of exceedances using each run own mean and sigma; thresholds differ',
              'reference_thresholds': 'fixed thresholds from config reference; exact counts',
              'pooled_threshold_counts': 'bounds from amplitude histogram; boundary bin uncertainty retained',
              'episode_boundary': 'continuous within each run; split only at run boundaries; durations use acquired samples',
              'modes': combined}
    for mode, acc in combined.items():
        acc['amplitude_noise_rms_v'] = math.sqrt(acc['m2']/acc['n'])
        acc['mean_amplitude_v'] = acc['mean']
        bounds = {}
        e, c = arrays['amplitude_edges_v'], arrays['global_'+mode+'_amp']
        for k in SIGMAS:
            threshold = acc['mean'] + k * acc['amplitude_noise_rms_v']
            lower = int(c[e[:-1] > threshold].sum())
            upper = int(c[e[1:] > threshold].sum())
            bounds[str(k)] = {'threshold_v': threshold, 'samples_above_lower_bound': lower,
                              'samples_above_upper_bound': upper, 'gaussian_expected': tail(k)*acc['n']}
        acc['pooled_thresholds'] = bounds
        for lag, stat in acc['delta_circular'].items():
            stat['lag_s'] = int(lag)/config['fs_hz']
            n = stat['pairs']
            stat['mean_rad'] = math.atan2(stat['sin_sum'], stat['cos_sum']) if n else None
            stat['resultant_length'] = min(1., math.hypot(stat['cos_sum'],stat['sin_sum'])/n) if n else None
    out.mkdir(parents=True, exist_ok=True)
    columns = list(dict.fromkeys(k for row in table for k in row))
    with (out/'runs.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns); writer.writeheader(); writer.writerows(table)
    np.savez_compressed(out/'global_noise.npz', **arrays)
    (out/'global_noise.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    plot_results(out, arrays, combined, table, run_names, config)
    print('Aggregati %d run. Risultati: %s' % (len(rows), out))


def plot_results(out, arrays, combined, table, names, config):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 3, figsize=(17, 11), squeeze=False)
    try:
        for row, mode in enumerate(MODES):
            e, c = arrays['amplitude_edges_v'], arrays['global_'+mode+'_amp']
            # Tutti i bin nell'intervallo popolato: evitare di perdere
            # risoluzione raggruppando l'intero intervallo fisico ADC.
            occupied = np.flatnonzero(c)
            if len(occupied):
                lo,hi=int(occupied[0]),int(occupied[-1])+1
                axes[row,0].stairs(c[lo:hi],e[lo:hi+1])
                axes[row,0].set_xlim(e[lo],e[hi])
            axes[row,0].set_yscale('log'); axes[row,0].set_ylim(bottom=.5)
            axes[row,0].set(title=mode+': global amplitude', xlabel='Amplitude [V]', ylabel='Samples')
            axes[row,1].stairs(arrays['global_'+mode+'_phase'], arrays['phase_edges_rad'])
            axes[row,1].set(title=mode+': absolute phase', xlabel='Phase [rad]', ylabel='Samples')
            for lag in config['phase_lags_samples']:
                h=arrays['global_'+mode+'_delta_'+str(lag)]
                if h.sum():
                    density = h/h.sum()/np.diff(arrays['phase_edges_rad'])
                    axes[row,2].stairs(density, arrays['phase_edges_rad'], label='lag %d samples'%lag)
            axes[row,2].set(title=mode+': delta phase', xlabel='Delta phase [rad]', ylabel='Probability density')
            axes[row,2].legend(fontsize=7)
        fig.tight_layout(); fig.savefig(out/'global_distributions.png', dpi=150)
    finally:
        plt.close(fig)
    from matplotlib.colors import LogNorm
    fig_iq, axes_iq = plt.subplots(1, 3, figsize=(16, 5), squeeze=False)
    try:
        for col, mode in enumerate(MODES):
            counts=arrays['global_'+mode+'_iq']
            edges=arrays['iq_edges_v']
            ax=axes_iq[0,col]
            image=ax.pcolormesh(edges,edges,np.ma.masked_equal(counts.T,0),
                norm=LogNorm(vmin=1,vmax=max(2,int(counts.max()))),cmap='magma')
            occupied=np.argwhere(counts>0)
            if len(occupied):
                low=int(occupied.min()); high=int(occupied.max())+1
                ax.set_xlim(edges[low],edges[high]); ax.set_ylim(edges[low],edges[high])
            ax.set(title=mode+': global IQ',xlabel='I [V]',ylabel='Signed Q [V]')
            ax.set_aspect('equal',adjustable='box')
            fig_iq.colorbar(image,ax=ax,label='Samples / bin')
        fig_iq.tight_layout(); fig_iq.savefig(out/'global_iq.png',dpi=150)
    finally:
        plt.close(fig_iq)
    fig, axes = plt.subplots(3, 3, figsize=(17, 10), squeeze=False)
    try:
        for row, mode in enumerate(MODES):
            records=[record for record in table if record['mode']==mode]
            x=np.arange(len(records))
            axes[row,0].plot(x,[r['mean_amplitude_v'] for r in records],'.-',label='Mean')
            axes[row,0].plot(x,[r['amplitude_noise_rms_v'] for r in records],'.-',label='RMS noise')
            axes[row,0].set(title=mode, ylabel='Amplitude [V]'); axes[row,0].legend(fontsize=7)
            for k in SIGMAS:
                for col, kind in ((1,'local'),(2,'reference')):
                    key='%s_%dsigma_fraction'%(kind,k)
                    if key in records[0]: axes[row,col].plot(x,[r[key] for r in records],'.-',label='%d sigma'%k)
            for col,title in ((1,'Local thresholds'),(2,'Fixed reference thresholds')):
                axes[row,col].set(title=title,ylabel='Fraction of samples above threshold')
                axes[row,col].set_yscale('log')
                if axes[row,col].lines: axes[row,col].legend(fontsize=7)
            for ax in axes[row]:
                step=max(1,len(names)//12); ax.set_xticks(x[::step]); ax.set_xticklabels(names[::step],rotation=45,ha='right')
        fig.tight_layout(); fig.savefig(out/'run_trends.png',dpi=150)
    finally:
        plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs',type=Path,nargs='+',help='JSON per run oppure directory da cercare ricorsivamente')
    parser.add_argument('--out-dir',type=Path,default=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/noise_global'))
    parser.add_argument('--make-reference',type=Path,help='Crea solo il riferimento da statistiche pilota, anche formato precedente')
    parser.add_argument('--allow-partial',action='store_true')
    parser.add_argument('--expected-runs',type=Path,help='Lista run richiesta: fallisce se ci sono run mancanti o extra')
    args=parser.parse_args()
    try:
        rows=read_inputs(args.inputs)
        if args.make_reference: create_reference(rows,args.make_reference)
        else: aggregate(rows,args.out_dir,args.allow_partial,args.expected_runs)
    except (ValueError, KeyError, FileNotFoundError) as error:
        parser.exit(2,str(error)+'\n')


if __name__=='__main__':
    main()
