#!/usr/bin/env python3
"""Stream MIDAS IQ through identical demodulated FIR bands; export event summaries."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from scipy.signal import firwin, fftconvolve


class BandFilter:
    """Causal FIR, continuous oscillator/state and global decimation grid."""
    def __init__(self, fs, center, width, taps=2001, decimation=20):
        if taps % 2 != 1 or taps < 3 or decimation < 1:
            raise ValueError('Odd taps >=3 and positive decimation required')
        if not 0 < width/2 < fs/(2*decimation) or abs(center)+width/2 >= fs/2:
            raise ValueError('Band/decimation outside Nyquist coverage')
        self.h = firwin(taps, width/2, fs=fs, window=('kaiser', 8.6))
        self.tail = np.zeros(taps-1, complex)
        self.n = 0
        self.fs, self.center, self.decimation = fs, center, decimation

    def process(self, z):
        indices = self.n + np.arange(len(z), dtype=np.int64)
        mixed = z * np.exp(-2j*np.pi*np.remainder(indices*self.center/self.fs, 1.))
        extended = np.r_[self.tail, mixed]
        filtered = fftconvolve(extended, self.h, mode='valid')
        keep = (indices % self.decimation == 0) & (indices >= len(self.h)-1)
        self.tail = extended[-len(self.tail):].copy()
        self.n += len(z)
        # Time refers to the center of the linear-phase FIR support.
        return (indices[keep]-(len(self.h)-1)/2)/self.fs, filtered[keep]


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
    filters = {(m,o): BandFilter(a.fs,c+o,a.width_hz,a.taps,a.decimation)
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
                for m in range(3):
                    z = (frames[:,2*m].astype(float) + 1j*a.iq_sign*frames[:,2*m+1])*(2*a.input_range/65535)
                    for o in offsets:
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
                        writer.writerow(row)
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
