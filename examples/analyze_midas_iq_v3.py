"""Single-pass MIDAS pilot. See docs/iq_autoreco_v3.md."""
import argparse
from bisect import bisect_right
import json
import os
from pathlib import Path
import resource
import subprocess
import tempfile
import time

import h5py
import numpy as np
from scipy.fft import fft

from iq_acquisition_metadata import PAIRS, number
from iq_compact_spectra import CompactSpectra, append_row as append, spectrum_rows


SPLIT = tuple(f"SPE{i}" for i in range(7))
METRICS = ("mean_I_V", "mean_Qhardware_V", "rms_V", "ac_rms_V",
           "mean_abs_V", "std_abs_V", "moment3_abs_V3", "moment4_abs_V4",
           "var_I_V2", "var_Q_V2", "cov_I_Qhardware_V2", "pseudo_real",
           "pseudo_imag", "max_abs_V")


def bank(banks, name, types):
    item = banks.get(name)
    if item is None or item.type not in types:
        raise ValueError(f"missing or invalid {name} MIDAS type")
    data = np.asarray(item.data)
    if data.ndim != 1 or data.dtype.kind not in "iu" or data.dtype.itemsize != types[item.type]:
        raise ValueError(f"invalid {name} payload")
    return data


def decode(banks):
    if "SPEC" in banks:
        if any(name in banks for name in (*SPLIT, "SPGP")):
            raise ValueError("mixed bank layouts")
        raw = bank(banks, "SPEC", {4: 2, 5: 2})
        if not raw.size or raw.size % 8:
            raise ValueError("invalid SPEC length")
        return "SPEC", raw.view(np.int16).reshape(-1, 8).T
    names = SPLIT if "SPE6" in banks else SPLIT[:-1]
    channels = tuple(bank(banks, name, {4: 2, 5: 2}).view(np.int16) for name in names)
    if not channels[0].size or len({len(ch) for ch in channels}) != 1:
        raise ValueError("inconsistent SPE lengths")
    return "SPE", channels


def runs(mask):
    edges = np.flatnonzero(np.diff(mask, prepend=False, append=False))
    return zip(edges[::2], edges[1::2])


class PulseDetector:
    def __init__(self):
        self.pending = None

    def feed(self, mask, serial, start):
        spans = list(runs(mask))
        if self.pending is not None:
            old_serial, old_i, old_start, old_n = self.pending
            if spans and spans[0][0] == 0:
                _, end = spans.pop(0)
                self.pending = (old_serial, old_i, old_start, old_n + end)
                if end == len(mask):
                    return
            yield self.pending
            self.pending = None
        for i, end in spans:
            pulse = (serial, i, start + i, end - i)
            if end == len(mask):
                self.pending = pulse
            else:
                yield pulse


def measure(z, histogram=None):
    amplitude = np.abs(z)
    if histogram is not None:
        edges, counts = histogram
        bins = np.minimum((amplitude * np.float32(len(counts) / edges[-1])).astype(np.int32),
                          len(counts) - 1)
        counts += np.bincount(bins, minlength=len(counts))
    a = amplitude.astype(np.float64)
    i = z.real.astype(np.float64)
    q = -z.imag.astype(np.float64)
    mi, mq = i.mean(), q.mean()
    vi, vq = i.var(), q.var()
    cov = np.mean((i-mi)*(q-mq))
    squared = a*a
    power = squared.mean()
    ac = vi + vq
    peak = int(a.argmax())
    values = (mi, mq, np.sqrt(power), np.sqrt(ac), a.mean(), a.std(),
              np.mean(squared*a), np.mean(squared*squared), vi, vq, cov,
              (vi-vq)/ac if ac else np.nan, -2*cov/ac if ac else np.nan, a[peak])
    return values, peak


def table(group, name, columns):
    d = group.create_dataset(name, shape=(0,), maxshape=(None,), dtype=columns)
    return d


def process(reader, odb, output, args):
    equipment = odb["Equipment"]
    adc = equipment["NetBox"]["Settings"]
    fs = number(adc["Sampling_rate_MS"], "Sampling_rate_MS") * 1e6
    if not fs.is_integer():
        raise ValueError("one-second sample count must be integral")
    n = int(fs)
    scale = np.asarray(adc["Channel_range_mV"], float) * (0.002 / 65535)
    if scale.ndim != 1 or scale.size < 6 or not np.all(np.isfinite(scale) & (scale > 0)):
        raise ValueError("invalid BOR ADC ranges")
    lo = equipment["LocalOscill"]["Variables"]
    output.attrs["schema_version"] = "1.2"
    meta = output.create_group("metadata")
    meta.attrs.update(fs_hz=fs, iq_convention="I-iQhardware",
                      bor_settings_json=json.dumps(adc),
                      bor_lo_json=json.dumps(lo),
                      run_number=int(odb["Runinfo"]["Run number"]),
                      configuration_json=json.dumps(vars(args), default=str))
    timing = output.create_group("timing")
    timing.attrs.update(utc_quality="unanchored", index_reference="received valid sample ordinal")
    pulse_fields = [(k, "<i8") for k in ("serial", "offset_samples", "received_index", "width_samples")]
    pps = table(timing, "pps", pulse_fields)
    waveform = table(timing, "pps_waveform", pulse_fields)
    digitizer = table(timing, "digitizer_events", [(k, "<i8") for k in (
        "serial", "header_unix_s", "received_index", "samples", "segment")])
    spgp = table(timing, "spgp", [(k, "<i8") for k in ("serial", "offset_samples", "width_samples")])
    gps = table(timing, "tgps", [("serial", "<i8"), ("header_unix_s", "<i8"), ("received_before", "<i8"), ("payload", "u1", (80,))])
    windows = table(timing, "windows", [(k, "<i8") for k in (
        "segment", "received_index", "first_serial", "first_offset_samples",
        "last_serial", "last_offset_samples")] + [("received_s", "<f8"), ("utc_unix_s", "<f8")])
    quality = output.create_group("quality")
    gaps = table(quality, "breaks", [("serial", "<i8"), ("reason", "S160")])
    spectra = output.create_group("spectra")
    compact = None
    if args.product != "compact":
        spectra.attrs["profile"] = args.product
        spectra.create_dataset("frequency_hz", data=np.fft.fftfreq(n, 1/fs))
    stats = output.create_group("statistics")
    anomalies = output.create_group("anomalies")
    histogram_group = output.create_group("histograms")
    histograms = {}
    event_starts, event_serials = [], []
    residual_chunks = 0
    aggregation_max_error = 0.
    layout = None
    channels_present = None
    previous = None
    detector = PulseDetector()
    fill = received = discarded = segment = count = 0
    expected_spgp = []
    observed_spgp = []
    first = None
    totals = {}
    eor = False

    profile = dict(midas_read_s=0., adc_decode_s=0., fft_s=0., statistics_s=0.,
                   anomalies_s=0., hdf5_rows_s=0.)
    def save_residual():
        nonlocal residual_chunks
        if fill:
            started = time.perf_counter()
            for mode, z in buffers.items():
                values, peak = measure(z[:fill], histograms[mode])
                totals[mode].append((fill, first[0], values, peak, *clipped[mode]))
            profile["statistics_s"] += time.perf_counter() - started
            residual_chunks += 1

    events = iter(reader)
    while True:
        started = time.perf_counter()
        event = next(events, None)
        profile["midas_read_s"] += time.perf_counter() - started
        if event is None:
            break
        header = event.header
        if header.is_midas_internal_event():
            eor |= header.is_eor_event()
            continue
        serial = int(header.serial_number)
        banks = event.banks
        if "TGPS" in banks:
            try:
                payload = bank(banks, "TGPS", {3: 1})
                if len(payload) != 80:
                    raise ValueError("invalid TGPS length")
                append(gps, (serial, header.timestamp, received, payload))
            except ValueError as exc:
                append(gaps, (serial, str(exc).encode()))
        if header.event_id != 1:
            continue
        if args.max_events and count >= args.max_events:
            break
        count += 1
        reason = None
        try:
            kind, channels = decode(banks)
            if layout and (kind != layout or len(channels) != channels_present):
                raise ValueError("layout changed")
        except ValueError as exc:
            reason = str(exc)
            channels = None
        if previous is not None and serial != (previous + 1) % 2**32:
            reason = reason or f"serial gap after {previous}"
        previous = serial
        if reason:
            append(gaps, (serial, reason.encode()))
            save_residual()
            discarded += fill
            fill = 0
            segment += 1
            detector = PulseDetector()
        if channels is None:
            continue
        if layout is None:
            layout = kind
            channels_present = len(channels)
            if scale.size < channels_present:
                raise ValueError("missing BOR range for a present channel")
            pairs = adc.get("IQ_channel_pairs") or (PAIRS if layout == "SPEC" else args.split_pairs)
            if not pairs:
                raise ValueError("SPE mapping absent from BOR; provide --split-pairs for diagnostic processing")
            if any(not isinstance(name, str) or not name or "/" in name or len(pair) != 2
                   or any(type(ch) is not int or not 0 <= ch < 6 for ch in pair)
                   or pair[0] == pair[1] for name, pair in pairs.items()):
                raise ValueError("invalid IQ mapping")
            meta.attrs.update(midas_layout=layout, channels_present=channels_present, pairs_json=json.dumps(pairs),
                              mapping_source="BOR" if adc.get("IQ_channel_pairs") else
                              ("legacy historical mapping" if layout == "SPEC" else "explicit pilot configuration"))
            buffers = {m: np.empty(n, np.complex64) for m in pairs}
            clipped = {m: np.zeros(2, dtype=np.int64) for m in pairs}
            if args.product == "compact":
                compact = CompactSpectra(spectra, n, pairs, args)
            for mode, (ci, cq) in pairs.items():
                if compact is None:
                    spectrum_rows(spectra, mode, n, "f4" if args.product == "psd" else "c8",
                                  "V^2/Hz" if args.product == "psd" else "V", args.compression)
                limit = 32768 * np.hypot(scale[ci], scale[cq])
                histograms[mode] = np.linspace(0, limit, 513), np.zeros(512, dtype=np.int64)
                table(stats, mode, [(k, "<f8") for k in METRICS] + [
                    ("peak_offset_samples","<i8"), ("clip_I","<i8"), ("clip_Q","<i8"),
                    ("parseval_relative_error","<f8")])
                group = anomalies.create_group(mode)
                table(group, "episodes", [(k,"<i8") for k in (
                    "window","received_index","duration_samples","peak_received_index",
                    "start_serial","start_offset_samples","peak_serial","peak_offset_samples")] +
                    [("threshold_rms","<f8"),("peak_ac_V","<f8")])
                table(group, "population", [("window","<i8"),("threshold_rms","<f8"),
                      ("observed_samples","<i8"),("above_samples","<i8"),("episodes","<i8")])
                totals[mode] = []
        size = len(channels[0])
        append(digitizer, (serial, header.timestamp, received, size, segment))
        event_starts.append(received)
        event_serials.append(serial)
        if layout == "SPE":
            try:
                words = bank(banks, "SPGP", {6: 4})
                if words.size % 2 or np.any(words[::2] >= size) or np.any(words[1::2] == 0) or np.any(np.diff(words[::2].astype(np.int64)) <= 0):
                    raise ValueError("invalid SPGP index/width pairs")
                for i, width in words.reshape(-1,2):
                    entry = (serial, int(i), int(width))
                    expected_spgp.append(entry)
                    append(spgp, entry)
                    append(pps, (serial, int(i), received + int(i), int(width)))
            except ValueError as exc:
                append(gaps, (serial, str(exc).encode()))
        if len(channels) > 6:
            for pulse in detector.feed(channels[6] > 2.5/scale[6], serial, received):
                if pulse[-1] > 4000:
                    append(waveform, pulse)
                    if layout == "SPEC":
                        append(pps, pulse)
                    observed_spgp.append((pulse[0], pulse[1], pulse[3]))
        offset = 0
        while offset < size:
            if not fill:
                first = (received + offset, serial, offset)
                for c in clipped.values():
                    c.fill(0)
            take = min(n-fill, size-offset)
            started = time.perf_counter()
            for mode, (ci,cq) in pairs.items():
                i, q = (channels[ch][offset:offset+take] for ch in (ci,cq))
                z = buffers[mode][fill:fill+take]
                z.real = i * np.float32(scale[ci])
                z.imag = q * np.float32(-scale[cq])
                for j, raw in enumerate((i,q)):
                    clipped[mode][j] += np.count_nonzero((raw == -32768) | (raw == 32767))
            profile["adc_decode_s"] += time.perf_counter() - started
            fill += take
            offset += take
            if fill < n:
                continue
            window = len(windows)
            append(windows, (segment, *first, serial, offset-1, first[0]/fs, np.nan))
            for mode, z in buffers.items():
                started = time.perf_counter()
                values, peak = measure(z, histograms[mode])
                profile["statistics_s"] += time.perf_counter() - started
                started = time.perf_counter()
                x = fft(z, workers=args.workers, overwrite_x=False) / np.float32(n)
                power = np.abs(x)**2
                expected = values[2]**2
                error = abs(power.sum(dtype=np.float64)-expected)/expected if expected else 0.
                profile["fft_s"] += time.perf_counter() - started
                started = time.perf_counter()
                if compact is not None:
                    aggregation_max_error = max(aggregation_max_error, compact.write(mode, x, power))
                else:
                    append(spectra[mode], power if args.product == "psd" else x)
                row = (*values, peak, *clipped[mode], error)
                append(stats[mode], row)
                totals[mode].append((n, first[0], values, peak, *clipped[mode]))
                profile["hdf5_rows_s"] += time.perf_counter() - started
                started = time.perf_counter()
                ac = np.abs(z - np.complex64(complex(values[0], -values[1])))
                for threshold in args.thresholds:
                    spans = list(runs(ac > threshold*values[3]))
                    rows = []
                    for a,b in spans:
                        local = int(ac[a:b].argmax()) + a
                        start_index, peak_index = first[0]+a, first[0]+local
                        start_event = bisect_right(event_starts, start_index) - 1
                        peak_event = bisect_right(event_starts, peak_index) - 1
                        rows.append((window, start_index, b-a, peak_index,
                                     event_serials[start_event], start_index-event_starts[start_event],
                                     event_serials[peak_event], peak_index-event_starts[peak_event],
                                     threshold, ac[local]))
                    if rows:
                        episodes = anomalies[mode]["episodes"]
                        end = len(episodes)
                        episodes.resize(end + len(rows), axis=0)
                        episodes[end:] = rows
                    append(anomalies[mode]["population"], (window, threshold, n,
                           sum(b-a for a,b in spans), len(spans)))
                profile["anomalies_s"] += time.perf_counter() - started
            fill = 0
        received += size

    if not layout:
        raise ValueError("no valid digitizer events")
    if not eor and not args.max_events:
        raise ValueError("no MIDAS EOR; input may be incomplete")
    save_residual()
    if compact is not None:
        compact.finish(len(windows))
    for mode, rows in totals.items():
        counts, starts, metrics, peaks, clip_i, clip_q = zip(*rows)
        r = np.asarray(metrics)
        weights = np.asarray(counts, dtype=np.float64) / sum(counts)
        mi, mq = weights @ r[:, :2]
        vi = weights @ (r[:,8] + (r[:,0]-mi)**2)
        vq = weights @ (r[:,9] + (r[:,1]-mq)**2)
        cov = weights @ (r[:,10] + (r[:,0]-mi)*(r[:,1]-mq))
        amp = weights @ r[:,4]
        ac = vi+vq
        best = int(r[:,13].argmax())
        aggregate = (mi,mq,np.sqrt(weights @ (r[:,2]**2)), np.sqrt(ac),amp,
                     np.sqrt(weights @ (r[:,5]**2+(r[:,4]-amp)**2)),
                     weights @ r[:,6],weights @ r[:,7],vi,vq,cov,
                     (vi-vq)/ac if ac else np.nan,-2*cov/ac if ac else np.nan,r[best,13])
        stats[mode].attrs.update(dict(zip(METRICS,aggregate)))
        stats[mode].attrs.update(clip_I=int(sum(clip_i)),clip_Q=int(sum(clip_q)),
                                 temporal_samples=sum(counts),
                                 peak_received_index=starts[best]+peaks[best])
        group = histogram_group.create_group(mode)
        edges, hist_counts = histograms[mode]
        group.create_dataset("amplitude_edges_v", data=edges)
        group.create_dataset("amplitude_counts", data=hist_counts)
    quality.attrs.update(spectral_samples=len(windows)*n, temporal_samples=received,
                         residual_chunks=residual_chunks,
                         aggregation_max_relative_error=aggregation_max_error)
    quality.attrs.update(profile)
    timing.attrs["pps_source"] = "SPGP" if layout == "SPE" else "SPEC channel 6"
    timing.attrs["pps_waveform_available"] = channels_present > 6
    quality.attrs.update(events=count, received_samples=received, discarded_samples=discarded+fill,
                         valid_windows=len(windows), saw_eor=eor, spgp_exact_matches=(
                         len(set(expected_spgp) & set(observed_spgp))),
                         continuity_basis="consecutive digitizer serials and valid banks; hardware losses unverified")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--split-pairs", type=json.loads)
    p.add_argument("--product", choices=("compact","psd","fft"), default="compact")
    p.add_argument("--bin-hz", type=int, default=100)
    p.add_argument("--max-psd", action="store_true")
    p.add_argument("--band", type=float, nargs=2, action="append", default=[],
                   metavar=("LOW_HZ", "HIGH_HZ"))
    p.add_argument("--band-product", choices=("psd","fft"), default="psd")
    p.add_argument("--compression", choices=("lzf","gzip"))
    p.add_argument("--thresholds", type=float, nargs="+", default=[4.,5.,6.])
    p.add_argument("--max-events", type=int)
    p.add_argument("--software-commit")
    p.add_argument("--workers", type=int, default=1)
    args = p.parse_args()
    if args.output.exists() or args.output.resolve() == args.source.resolve():
        p.error("output must be a new file")
    if any(not np.isfinite(t) or t <= 0 for t in args.thresholds):
        p.error("thresholds must be finite and positive")
    if args.max_events is not None and args.max_events < 1:
        p.error("max-events must be positive")
    if args.bin_hz <= 0 or any(not np.isfinite([low, high]).all() or low >= high
                               for low, high in args.band):
        p.error("bin width must be positive and band bounds finite and increasing")
    if args.product != "compact" and (args.band or args.max_psd):
        p.error("band and maximum PSD options require --product compact")
    import midas.file_reader
    wall, cpu = time.perf_counter(), time.process_time()
    source_stat = args.source.stat()
    commit = args.software_commit or subprocess.check_output(["git","rev-parse","HEAD"],
                                     cwd=Path(__file__).resolve().parent, text=True).strip()
    fd, path = tempfile.mkstemp(dir=args.output.parent, prefix=f".{args.output.name}.")
    os.close(fd)
    try:
        with midas.file_reader.MidasFile(str(args.source), use_numpy=True) as reader, h5py.File(path,"w") as out:
            odb = reader.get_bor_odb_dump().data
            process(reader, odb, out, args)
            if args.source.stat().st_mtime_ns != source_stat.st_mtime_ns:
                raise ValueError("source changed during processing")
            out["metadata"].attrs.update(source=str(args.source.resolve()),
                 source_size_bytes=source_stat.st_size, source_mtime_ns=source_stat.st_mtime_ns,
                 software_commit=commit)
            out["quality"].attrs.update(wall_s=time.perf_counter()-wall,
                 cpu_s=time.process_time()-cpu, max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        with h5py.File(path, "r") as check:
            n_windows = len(check["timing/windows"])
            if not n_windows or check["quality"].attrs["aggregation_max_relative_error"] > 1e-6 or any(
                len(check["spectra"][mode]["window_psd"] if args.product == "compact"
                    else check["spectra"][mode]) != n_windows
                or len(check["statistics"][mode]) != n_windows
                or not np.all(check["statistics"][mode]["parseval_relative_error"] < 1e-5)
                for mode in check["statistics"]
            ):
                raise ValueError("HDF5 failed window-count or Parseval validation")
        os.link(path,args.output)
    finally:
        os.unlink(path)


if __name__ == "__main__":
    main()
