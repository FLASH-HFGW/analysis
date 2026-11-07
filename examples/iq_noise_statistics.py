"""Statistiche streaming aggregabili per run MIDAS IQ, senza conservare i campioni."""
import hashlib
import json
import math

import numpy as np

MODES = ('TM010', 'TM011', 'TM012')
SIGMAS = (3, 5, 7)
SCHEMA = 2


def uniform_histogram(values, edges):
    """Stessi bin linspace, percorso NumPy aritmetico anziché sort dei dati."""
    return np.histogram(values, bins=len(edges) - 1,
                        range=(float(edges[0]), float(edges[-1])))[0]


def uniform_histogram2d(x, y, x_edges, y_edges):
    """Densità su griglia uniforme, inclusi correzioni ULP e bordo destro."""
    nx, ny = len(x_edges) - 1, len(y_edges) - 1
    valid = ((x >= x_edges[0]) & (x <= x_edges[-1]) &
             (y >= y_edges[0]) & (y <= y_edges[-1]))
    def indices(values, edges, bins):
        result = ((values - edges[0]) * (bins / (edges[-1] - edges[0]))).astype(np.intp)
        np.minimum(result, bins - 1, out=result)
        # Come np.histogram: [left,right), salvo l'ultimo bin chiuso a destra.
        result -= values < edges[result]
        result += (result < bins - 1) & (values >= edges[result + 1])
        return result
    ix = indices(x[valid], x_edges, nx)
    iy = indices(y[valid], y_edges, ny)
    return np.bincount(ix * ny + iy, minlength=nx * ny).reshape(nx, ny)


def tail(sigma):
    return 0.5 * math.erfc(sigma / math.sqrt(2))


def merge_moments(n, mean, m2, nb, mb, m2b):
    if nb == 0:
        return n, mean, m2
    total = n + nb
    delta = mb - mean
    return total, mean + delta * nb / total, m2 + m2b + delta * delta * n * nb / total


def episodes(mask, amplitude):
    """Episodi contigui nel blocco; il chiamante raccorda i blocchi dello stesso run."""
    edges = np.diff(np.r_[False, mask, False].astype(np.int8))
    starts = np.flatnonzero(edges == 1)
    stops = np.flatnonzero(edges == -1)
    lengths = stops - starts
    return {'samples_above': int(mask.sum()), 'episodes': len(starts),
            'duration_samples': int(lengths.sum()),
            'longest_samples': int(lengths.max()) if len(lengths) else 0,
            'peak_v': float(amplitude[mask].max()) if len(lengths) else None}


def merge_episodes(target, other):
    for key in ('samples_above', 'episodes', 'duration_samples'):
        target[key] += other[key]
    target['longest_samples'] = max(target['longest_samples'], other['longest_samples'])
    if other['peak_v'] is not None:
        target['peak_v'] = max(target['peak_v'] or 0., other['peak_v'])


def empty_episodes():
    return {'samples_above': 0, 'episodes': 0, 'duration_samples': 0,
            'longest_samples': 0, 'peak_v': None}


def make_config(fs, input_range, iq_sign, lags=(1, 10, 100), reference=None):
    config = {'schema': SCHEMA, 'fs_hz': float(fs), 'input_range_v': float(input_range),
              'iq_sign': int(iq_sign), 'phase_lags_samples': sorted(set(map(int, lags))),
              'amplitude_bins': 65536, 'iq_bins': 256, 'phase_bins': 1024,
              'reference': reference, 'stream_continuity': 'within_run'}
    if reference is not None:
        for key in ('fs_hz', 'input_range_v', 'iq_sign'):
            if config[key] != reference[key]:
                raise ValueError('Riferimento incompatibile: ' + key)
        if reference.get('schema') not in (1, SCHEMA):
            raise ValueError('Versione del riferimento non supportata')
        for mode in MODES:
            mean = reference['modes'][mode]['mean_amplitude_v']
            rms = reference['modes'][mode]['amplitude_noise_rms_v']
            if not np.isfinite(mean) or mean < 0 or not np.isfinite(rms) or rms < 0:
                raise ValueError('Riferimento non valido: ' + mode)
    return config


def config_id(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True, allow_nan=False).encode()).hexdigest()


class RunStatistics:
    def __init__(self, config, local_moments):
        self.config = config
        r = config['input_range_v']
        # Limiti fisici includono -32768 e +32767 con la conversione ADC esistente.
        self.amplitude_edges = np.linspace(0, math.sqrt(2) * r * 65536 / 65535,
                                            config['amplitude_bins'] + 1)
        self.iq_edges = np.linspace(-r * 65536 / 65535, r * 65536 / 65535,
                                    config['iq_bins'] + 1)
        self.phase_edges = np.linspace(-np.pi, np.pi, config['phase_bins'] + 1)
        self.states = {}
        self.history = {}
        self.episode_tails = {}
        for mode in MODES:
            moments = local_moments[mode]
            local = {str(k): moments['mean'] + k * math.sqrt(moments['m2'] / moments['n']) for k in SIGMAS}
            fixed = {}
            if config['reference']:
                ref = config['reference']['modes'][mode]
                fixed = {str(k): ref['mean_amplitude_v'] + k * ref['amplitude_noise_rms_v'] for k in SIGMAS}
            self.states[mode] = {'n': 0, 'mean': 0., 'm2': 0., 'valid_phase': 0,
                'amp': np.zeros(config['amplitude_bins'], dtype=np.int64),
                'iq': np.zeros((config['iq_bins'], config['iq_bins']), dtype=np.int64),
                'phase': np.zeros(config['phase_bins'], dtype=np.int64),
                'delta': {str(lag): np.zeros(config['phase_bins'], dtype=np.int64)
                          for lag in config['phase_lags_samples']},
                'delta_circular': {str(lag): {'pairs': 0, 'cos_sum': 0., 'sin_sum': 0.}
                                   for lag in config['phase_lags_samples']},
                'thresholds_v': {'local': local, 'reference': fixed},
                'exceedances': {kind: {k: empty_episodes() for k in values}
                                for kind, values in (('local', local), ('reference', fixed))}}

    def update(self, mode, i, q, amplitude=None):
        st = self.states[mode]
        a = np.hypot(i, q) if amplitude is None else amplitude
        if not len(a) or not np.isfinite(a).all():
            raise ValueError('Campioni IQ vuoti o non finiti')
        n, mean = len(a), float(a.mean())
        st['n'], st['mean'], st['m2'] = merge_moments(
            st['n'], st['mean'], st['m2'], n, mean, float(np.sum((a - mean)**2)))
        phase = np.arctan2(q, i)
        valid = a > 0
        # Componenti del fasore unitario: calcolate una sola volta per i tre ritardi.
        unit_i = np.divide(i, a, out=np.zeros_like(a), where=valid)
        unit_q = np.divide(q, a, out=np.zeros_like(a), where=valid)
        st['amp'] += uniform_histogram(a, self.amplitude_edges)
        st['iq'] += uniform_histogram2d(i, q, self.iq_edges, self.iq_edges)
        st['phase'] += uniform_histogram(phase[valid], self.phase_edges)
        st['valid_phase'] += int(valid.sum())
        # Conservare solo max(lag) campioni: includere ogni coppia una volta,
        # anche quando lag supera la dimensione del singolo blocco SPEC.
        previous = self.history.get(mode)
        h = 0 if previous is None else len(previous[0])
        if previous is not None:
            phase, valid, unit_i, unit_q = [np.r_[old, new] for old, new in
                zip(previous, (phase, valid, unit_i, unit_q))]
        for lag in self.config['phase_lags_samples']:
            if lag >= len(phase):
                continue
            start = max(h, lag)
            left = slice(start - lag, len(phase) - lag)
            right = slice(start, None)
            good = valid[left] & valid[right]
            # Differenza circolare stabile, nessuna moltiplicazione di ampiezze.
            d = phase[right][good] - phase[left][good]
            delta = (d + np.pi) % (2 * np.pi) - np.pi
            key = str(lag)
            st['delta'][key] += uniform_histogram(delta, self.phase_edges)
            stat = st['delta_circular'][key]
            stat['pairs'] += len(delta)
            # cos(phi1-phi0), sin(phi1-phi0) dai prodotti dei fasori.
            # I fasori nulli contribuiscono zero: stessi endpoint esclusi da good.
            stat['cos_sum'] += float(np.sum(unit_i[right] * unit_i[left]) +
                                     np.sum(unit_q[right] * unit_q[left]))
            stat['sin_sum'] += float(np.sum(unit_q[right] * unit_i[left]) -
                                     np.sum(unit_i[right] * unit_q[left]))
        retain = max(self.config['phase_lags_samples'], default=0)
        self.history[mode] = tuple(x[-retain:].copy() if retain else x[:0].copy()
                                   for x in (phase, valid, unit_i, unit_q))
        event_exceedances = {}
        for kind, thresholds in st['thresholds_v'].items():
            event_exceedances[kind] = {}
            for k, threshold in thresholds.items():
                mask = a > threshold
                current = episodes(mask, a)
                target = st['exceedances'][kind][k]
                merge_episodes(target, current)
                key = (mode, kind, k)
                trailing = self.episode_tails.get(key, 0)
                below = np.flatnonzero(~mask)
                head = int(below[0]) if len(below) else len(mask)
                tail_length = len(mask) - int(below[-1]) - 1 if len(below) else len(mask)
                if trailing and head:
                    target['episodes'] -= 1
                    target['longest_samples'] = max(target['longest_samples'], trailing + head)
                self.episode_tails[key] = (trailing + len(mask) if not len(below)
                                          else tail_length)
                event_exceedances[kind][k] = current
        return event_exceedances

    def export(self):
        arrays = {'amplitude_edges_v': self.amplitude_edges, 'iq_edges_v': self.iq_edges,
                  'phase_edges_rad': self.phase_edges}
        modes = {}
        for mode, st in self.states.items():
            if st['amp'].sum() != st['n'] or st['iq'].sum() != st['n']:
                raise ValueError('Campioni fuori dai bin comuni: ' + mode)
            if st['phase'].sum() != st['valid_phase']:
                raise ValueError('Conteggio fase incoerente: ' + mode)
            modes[mode] = {key: st[key] for key in
                ('n', 'mean', 'm2', 'valid_phase', 'thresholds_v', 'exceedances', 'delta_circular')}
            for key in ('amp', 'iq', 'phase'):
                arrays['global_' + mode + '_' + key] = st[key]
            for lag, counts in st['delta'].items():
                arrays['global_' + mode + '_delta_' + lag] = counts
        return {'schema': SCHEMA, 'config': self.config, 'config_id': config_id(self.config),
                'episode_boundary': 'continuous within each run, including SPEC boundaries; split only between runs',
                'phase_reference': 'absolute atan2(signed Q,I); no run-dependent phase subtraction',
                'modes': modes}, arrays
