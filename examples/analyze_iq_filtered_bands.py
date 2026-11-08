#!/usr/bin/env python3
"""Stream MIDAS IQ through identical demodulated FIR bands; export event summaries."""
import argparse
import csv
import json
from pathlib import Path
from collections import OrderedDict
import numpy as np
from scipy.signal import firwin
from scipy.fft import fft, ifft, next_fast_len

FILTER_IMPLEMENTATION = 'shared-oscillator-cached-fir-fft-v1'


class FilterWorkspace:
    """Bounded caches shared by synchronous filters, never by different runs.

    Only one sample grid/oscillator is retained. Process equal centres together
    to reuse it across modes without retaining nine full-size complex arrays.
    Two kernel spectra cover changing event lengths with bounded memory.
    """
    def __init__(self):
        self._grid_key = self._selection_key = self._oscillator_key = None
        self._kernels = OrderedDict()

    def grid(self, start, size):
        key = (start, size)
        if key != self._grid_key:
            self._indices = start + np.arange(size, dtype=np.int64)
            self._grid_key = key
        return self._indices

    def selection(self, start, size, fs, taps, decimation):
        key = (start, size, fs, taps, decimation)
        if key != self._selection_key:
            first = max(start, taps - 1)
            first += (-first) % decimation
            self._take = np.arange(max(0, first-start), size, decimation, dtype=np.int64)
            self._times = (self.grid(start, size)[self._take] - (taps-1)/2) / fs
            self._selection_key = key
        return self._times, self._take

    def oscillator(self, start, size, fs, center):
        if center == 0:
            return None
        key = (start, size, fs, center)
        if key != self._oscillator_key:
            indices = self.grid(start, size)
            self._oscillator = np.exp(-2j*np.pi*np.remainder(indices*center/fs, 1.))
            self._oscillator_key = key
        return self._oscillator

    def kernel(self, coefficients, length):
        key = (coefficients.tobytes(), length)
        if key not in self._kernels:
            # Same complex transform and padding used by fftconvolve for IQ.
            self._kernels[key] = fft(coefficients, length)
            if len(self._kernels) > 2:
                self._kernels.popitem(last=False)
        self._kernels.move_to_end(key)
        return self._kernels[key]


class BandFilter:
    """Causal FIR, continuous oscillator/state and global decimation grid."""
    def __init__(self, fs, center, width, taps=2001, decimation=20, workspace=None):
        if taps % 2 != 1 or taps < 3 or decimation < 1:
            raise ValueError('Odd taps >=3 and positive decimation required')
        if not 0 < width/2 < fs/(2*decimation) or abs(center)+width/2 >= fs/2:
            raise ValueError('Band/decimation outside Nyquist coverage')
        self.h = firwin(taps, width/2, fs=fs, window=('kaiser', 8.6))
        self.tail = np.zeros(taps-1, complex)
        self.n = 0
        self.fs, self.center, self.decimation = fs, center, decimation
        self.workspace = workspace if workspace is not None else FilterWorkspace()

    def process(self, z):
        if not len(z):
            return np.empty(0), np.empty(0, dtype=complex)
        oscillator = self.workspace.oscillator(self.n, len(z), self.fs, self.center)
        mixed = z if oscillator is None else z * oscillator
        extended = np.r_[self.tail, mixed]
        length = next_fast_len(len(extended) + len(self.h) - 1)
        transformed = fft(extended, length)
        transformed *= self.workspace.kernel(self.h, length)
        convolved = ifft(transformed)
        # Valid linear convolution: exactly the newly acquired samples.
        filtered = convolved[len(self.h)-1:len(self.h)-1+len(z)]
        times, take = self.workspace.selection(self.n, len(z), self.fs, len(self.h), self.decimation)
        self.tail = extended[-len(self.tail):].copy()
        self.n += len(z)
        # Time refers to the center of the linear-phase FIR support.
        return times, filtered[take]


def statistics(z, previous):
    amp = np.abs(z)
    good = amp > 0
    unit = z[good]/amp[good]
    resultant = np.mean(unit) if len(unit) else complex(np.nan, np.nan)
    pairs = np.r_[previous, z] if previous is not None else z
    valid = (np.abs(pairs[:-1]) > 0) & (np.abs(pairs[1:]) > 0)
    delta = pairs[1:][valid]*np.conj(pairs[:-1][valid])
    increment = np.mean(delta/np.abs(delta)) if len(delta) else complex(np.nan, np.nan)
    return dict(n=len(z), mean_amplitude_v=float(amp.mean()), rms_v=float(np.sqrt(np.mean(amp**2))),
                phase_mean_rad=float(np.angle(resultant)), phase_resultant=float(abs(resultant)),
                increment_mean_rad=float(np.angle(increment)), increment_resultant=float(abs(increment)),
                increment_pairs=int(valid.sum()))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('file', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--fs', type=float, default=5e6)
    p.add_argument('--input-range', type=float, default=5.)
    p.add_argument('--iq-sign', type=int, choices=(-1,1), default=-1)
    p.add_argument('--offsets-hz', nargs='+', type=float, default=[100e3,250e3,500e3,1e6])
    p.add_argument('--width-hz', type=float, default=50e3)
    p.add_argument('--centers-hz', nargs=3, type=float, default=[0.,0.,0.])
    p.add_argument('--taps', type=int, default=2001)
    p.add_argument('--decimation', type=int, default=20)
    p.add_argument('--max-events', type=int)
    a = p.parse_args()
    if (not all(np.isfinite(v) for v in [a.fs,a.input_range,a.width_hz,*a.centers_hz,*a.offsets_hz])
            or a.fs <= 0 or a.input_range <= 0 or any(v <= a.width_hz for v in a.offsets_hz)
            or (a.max_events is not None and a.max_events <= 0)):
        p.error('Invalid sampling, bands or event limit')
    offsets = sorted(set([0.] + [s*v for v in a.offsets_hz for s in [-1,1]]))
    workspace = FilterWorkspace()
    filters = {(m,o): BandFilter(a.fs,c+o,a.width_hz,a.taps,a.decimation,workspace=workspace)
               for m,c in enumerate(a.centers_hz) for o in offsets}
    previous = {key:None for key in filters}
    import midas.file_reader
    reader = midas.file_reader.MidasFile(str(a.file), use_numpy=True)
    a.output.mkdir(parents=True, exist_ok=True)
    events = samples = 0
    eof = True
    with (a.output/'bands.csv').open('w') as stream:
        writer = None
        try:
            for event in reader:
                if event.header.is_midas_internal_event() or 'SPEC' not in event.banks:
                    continue
                raw = np.asarray(event.banks['SPEC'].data, dtype=np.uint16)
                if raw.size == 0 or raw.size % 8:
                    raise ValueError('Invalid SPEC size')
                frames = raw.view(np.int16).reshape(-1,8)
                signals = [(frames[:,2*m].astype(float) + 1j*a.iq_sign*frames[:,2*m+1])*(2*a.input_range/65535)
                           for m in range(3)]
                event_rows = {}
                for o in offsets:
                    for m, z in enumerate(signals):
                        key = (m,o)
                        t, filtered = filters[key].process(z)
                        if not len(filtered):
                            continue
                        row = dict(mode=('TM010','TM011','TM012')[m], offset_hz=o,
                                   center_hz=a.centers_hz[m]+o, event=events,
                                   serial=int(event.header.serial_number),
                                   event_timestamp_unix=int(event.header.timestamp),
                                   acquired_start_s=float(t[0]), acquired_stop_s=float(t[-1]),
                                   **statistics(filtered, previous[key]))
                        previous[key] = filtered[-1]
                        if writer is None:
                            writer = csv.DictWriter(stream, fieldnames=list(row)); writer.writeheader()
                        event_rows[key] = row
                # Preserve the historical CSV order despite processing equal
                # band centres together to share the oscillator across modes.
                for key in sorted(event_rows):
                    writer.writerow(event_rows[key])
                events += 1; samples += len(frames)
                if events % 100 == 0:
                    stream.flush(); print(f'{events} SPEC; {samples/a.fs:.3f} s acquired', flush=True)
                if a.max_events is not None and events >= a.max_events:
                    eof = False
                    break
        finally:
            close = getattr(reader, 'close', None)
            if close is not None:
                close()
    if not events:
        raise ValueError('No SPEC events')
    doc = dict(input=str(a.file), events=events, samples=samples, reached_eof=eof,
               configuration={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
               phase='Phase of demodulated filtered IQ; no coherent excitation reference.',
               lag_seconds=a.decimation/a.fs,
               filter='Unity-DC-gain Kaiser FIR; causal state and oscillator continuous across SPEC; initial transient discarded.',
               implementation=FILTER_IMPLEMENTATION,
               time='Acquired sample time corrected for FIR group delay. Event timestamp stored separately; no subsecond wall-clock inferred.',
               caveats=['No input DC subtraction: center band includes offsets.',
                        'Same bandwidth and filter for every band; no brick-wall band assumption.',
                        'Circular phase mean is uninformative when resultant is near zero.',
                        'No phase significance or independent-sample errors inferred.',
                        'Continuity across SPEC assumes contiguous acquisition as in existing IQ analysis.'])
    (a.output/'summary.json').write_text(json.dumps(doc,indent=2)+'\n')
    print(json.dumps({k:doc[k] for k in ['events','samples','reached_eof']}))


if __name__ == '__main__':
    main()
