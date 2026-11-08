#!/usr/bin/env python3
"""Distribuzioni delle fluttuazioni di ampiezza IQ e fase per tutto il run MIDAS.

La sottrazione della media riguarda l'ampiezza, non I e Q. Non vengono
applicati filtri o rimozioni di deriva: le fluttuazioni includono quindi
anche eventuali segnali e derive presenti nella banda acquisita.
"""
import argparse
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from statistics import NormalDist
from pathlib import Path

import numpy as np

from iq_noise_io import build_results, save_results_h5, read_results_h5, flattened_arrays

from iq_noise_statistics import RunStatistics, make_config, uniform_histogram, uniform_histogram2d

MODES = {"TM010": (0, 1), "TM011": (2, 3), "TM012": (4, 5)}


def analyze_mode(i, q, iq_sign=1, phase_state=None):
    """Ampiezza e unwrap continuo nel run; stato separato per modo e passata."""
    z = i + 1j * iq_sign * q
    amplitude = np.hypot(i, q)
    # A=0 rende la fase indefinita, ma non interrompe lo stream acquisito.
    # Unwrap dei campioni validi adiacenti con convenzione del salto minimo;
    # nessuna pretesa di ricostruire rotazioni non risolte vicino all'origine.
    phase = np.full(amplitude.shape, np.nan)
    valid = amplitude > 0
    angles = np.angle(z[valid])
    if len(angles):
        if phase_state is not None and phase_state.get("last") is not None:
            unwrapped = np.unwrap(np.r_[phase_state["last"], angles])[1:]
        else:
            unwrapped = np.unwrap(angles)
        phase[valid] = unwrapped
        if phase_state is not None:
            phase_state["last"] = float(unwrapped[-1])
    return amplitude, amplitude - amplitude.mean(), phase


def gaussian_tail(sigma):
    return 0.5 * math.erfc(sigma / math.sqrt(2))


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Il valore deve essere positivo")
    return number


def plot_iq_results(saved, summary, output, x_axis="time"):
    """Tre popolazioni distinte: densità completa, campioni temporali, massimi."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as effects
    from matplotlib.colors import LogNorm
    from matplotlib.patches import Circle

    fig, axes = plt.subplots(3, 3, figsize=(19, 15), squeeze=False)
    x = saved["sample_indices"].astype(float)
    if x_axis == "time":
        x /= summary["fs_hz"]
    color_label = "Continuous run time [s]" if x_axis == "time" else "Cumulative sample"
    try:
        for row, mode in enumerate(MODES):
            counts = saved[mode + "_iq_counts"]
            ie = saved[mode + "_iq_i_edges_v"]
            qe = saved[mode + "_iq_q_edges_v"]
            i, q = saved[mode + "_i_v"], saved[mode + "_q_signed_v"]
            pi, pq = saved[mode + "_peak_i_v"], saved[mode + "_peak_q_signed_v"]
            classes = saved[mode + "_peak_sigma_class"]
            thresholds = ((3, float(saved[mode + "_amplitude_threshold_v"]), "crimson", "--"),
                          (5, float(saved[mode + "_amplitude_threshold_5sigma_v"]), "purple", ":"),
                          (7, float(saved[mode + "_amplitude_threshold_7sigma_v"]), "darkgreen", "-."))
            image = axes[row, 0].pcolormesh(ie, qe, np.ma.masked_equal(counts.T, 0),
                norm=LogNorm(vmin=1, vmax=max(2, int(counts.max()))), cmap="magma", shading="flat")
            fig.colorbar(image, ax=axes[row, 0], label="Samples / IQ bin")
            for sigma, radius, color, style in thresholds:
                circle = Circle((0, 0), radius, fill=False, color=color, linestyle=style,
                    linewidth=1.8, zorder=10, label="+%d sigma: %.4g V" % (sigma, radius))
                circle.set_path_effects([effects.Stroke(linewidth=4, foreground="white"), effects.Normal()])
                axes[row, 0].add_patch(circle)
            axes[row, 0].set_title(mode + ": density (all samples)")
            axes[row, 0].legend(fontsize=7, loc="upper right")
            # Solo i campioni temporali selezionati: nessun massimo aggiunto
            # e nessuna linea che suggerisca una traiettoria ricostruita.
            points = axes[row, 1].scatter(i, q, c=x, cmap="viridis", s=3,
                                         vmin=0, vmax=max(float(x[-1]), 1.))
            fig.colorbar(points, ax=axes[row, 1], label=color_label)
            axes[row, 1].scatter(i[0], q[0], marker="o", s=45, facecolors="none",
                                 edgecolors="red", label="First selected", zorder=4)
            axes[row, 1].scatter(i[-1], q[-1], marker="x", s=35, color="red",
                                 label="Last selected", zorder=4)
            axes[row, 1].legend(fontsize=7)
            axes[row, 1].set_title(mode + ": time-colored samples (subsampled)")
            for sigma, color, marker, label in ((3,"crimson","o","3–5 sigma"),
                                               (5,"purple","x","5–7 sigma"),
                                               (7,"darkgreen","*",">7 sigma")):
                mask = classes == sigma
                axes[row, 2].scatter(pi[mask], pq[mask], color=color, marker=marker,
                    s=7 if sigma != 7 else 30, alpha=0.6 if sigma == 3 else 1.,
                    label="%s: %d intervals" % (label, mask.sum()), zorder=sigma)
            axes[row, 2].set_title(mode + ": interval maxima above thresholds ONLY")
            axes[row, 2].legend(fontsize=7)
            axes[row, 2].text(.02, .02, "Selected maxima; not a density map\nEmpty center follows the amplitude cut",
                transform=axes[row, 2].transAxes, fontsize=7, va="bottom")
            limit = 1.03 * max(abs(ie[0]), abs(ie[-1]), abs(qe[0]), abs(qe[-1]), thresholds[-1][1])
            for ax in axes[row]:
                ax.set(xlabel="I [V]", ylabel="%sQ [V]" % ("" if summary["iq_sign"] == 1 else "-"),
                       xlim=(-limit, limit), ylim=(-limit, limit))
                ax.set_aspect("equal", adjustable="box")
                ax.axhline(0, color="gray", linewidth=.4, alpha=.5)
                ax.axvline(0, color="gray", linewidth=.4, alpha=.5)
        fig.suptitle(Path(summary["input"]).name + " — IQ: separate sampling populations")
        fig.tight_layout()
        fig.savefig(output, dpi=150)
    finally:
        plt.close(fig)


def process_second_mode(mode, channels, frames, states, global_stats, args,
                        buckets, cuts, offset, seen, serial):
    """Aggiorna un solo modo; i tre modi possiedono stati e array distinti."""
    ch_i, ch_q = channels
    amplitude, _, phase = analyze_mode(
        frames[:, ch_i].astype(float) * (2 * args.input_range / 65535),
        frames[:, ch_q].astype(float) * (2 * args.input_range / 65535), args.iq_sign, states[mode]["phase_state_pass2"])
    if states[mode]["reference"] is not None:
        phase -= states[mode]["reference"]
    st = states[mode]
    i = frames[:, ch_i].astype(float) * (2 * args.input_range / 65535)
    q = args.iq_sign * frames[:, ch_q].astype(float) * (2 * args.input_range / 65535)
    event_stats = global_stats.update(mode, i, q, amplitude=amplitude)
    st["iq_counts"] += uniform_histogram2d(i, q, st["iq_edges"], st["iq_edges"])
    valid = amplitude > 0
    relative = np.arctan2(q[valid], i[valid]) - (st["reference"] or 0.)
    wrapped_phase = (relative + np.pi) % (2 * np.pi) - np.pi
    st["phase_counts"] += uniform_histogram(wrapped_phase, st["phase_edges"])
    st["counts"] += uniform_histogram(amplitude, st["amp_edges"])
    # Il marcatore usa campione e fase del vero massimo dell'intervallo.
    for begin, end in zip(cuts[:-1], cuts[1:]):
        bucket = buckets[begin]
        peak = begin + int(np.argmax(amplitude[begin:end]))
        if amplitude[peak] > st["envelope_max"][bucket]:
            st["peak_sample"][bucket] = offset + peak
            st["peak_phase"][bucket] = phase[peak]
            st["peak_i"][bucket] = i[peak]
            st["peak_q"][bucket] = q[peak]
    # Ogni bucket compare in un unico segmento contiguo: riduzione
    # vettoriale, anziché aggiornare il bucket per ogni campione.
    bucket_ids = buckets[cuts[:-1]]
    segment_min = np.minimum.reduceat(amplitude, cuts[:-1])
    segment_max = np.maximum.reduceat(amplitude, cuts[:-1])
    segment_sum = np.add.reduceat(amplitude, cuts[:-1])
    st["envelope_min"][bucket_ids] = np.minimum(st["envelope_min"][bucket_ids], segment_min)
    st["envelope_max"][bucket_ids] = np.maximum(st["envelope_max"][bucket_ids], segment_max)
    st["envelope_sum"][bucket_ids] += segment_sum
    count = event_stats["local"]["3"]["samples_above"]
    count5 = event_stats["local"]["5"]["samples_above"]
    count7 = event_stats["local"]["7"]["samples_above"]
    st["above_7sigma"] += count7
    if count7:
        st["events_above_7sigma"].append({"event_index": seen,
            "serial": serial, "samples_above": count7})
    st["above_5sigma"] += count5
    if count5:
        st["events_above_5sigma"].append({"event_index": seen,
            "serial": serial, "samples_above": count5})
    st["above"] += count
    if count:
        st["events_above"].append({"event_index": seen,
            "serial": serial, "samples_above": count})


class FilteredBandChecks:
    """Statistiche per SPEC con stato FIR e coppie continui tra eventi."""
    def __init__(self, args):
        from analyze_iq_filtered_bands import BandFilter
        offsets = sorted(set([0.] + [sign * v for v in args.band_offsets_hz for sign in (-1, 1)]))
        if not all(np.isfinite(v) for v in [*offsets, *args.band_centers_hz, args.band_width_hz]):
            raise ValueError("Parametri delle bande non finiti")
        if any(v <= args.band_width_hz for v in args.band_offsets_hz):
            raise ValueError("Gli offset devono superare la larghezza di banda")
        self.config = dict(fs_hz=args.fs, iq_sign=args.iq_sign, input_range_v=args.input_range,
                           width_hz=args.band_width_hz, taps=args.band_taps,
                           decimation=args.band_decimation, offsets_hz=offsets,
                           centers_hz=args.band_centers_hz,
                           increment_lag_s=args.band_decimation / args.fs,
                           phase_reference="demodulation oscillator; central band includes DC",
                           continuity="FIR, oscillator and increment pairs continuous across SPEC")
        self.filters = {(mode, index): BandFilter(args.fs, center + offset, args.band_width_hz,
                                                args.band_taps, args.band_decimation)
                        for mode, center in zip(MODES, args.band_centers_hz)
                        for index, offset in enumerate(offsets)}
        self.previous = {key: None for key in self.filters}
        self.rows = {key: [] for key in self.filters}
        self.scale = 2 * args.input_range / 65535
        self.iq_sign = args.iq_sign

    def update(self, frames, event_index, serial, timestamp):
        from analyze_iq_filtered_bands import statistics
        for mode, (ci, cq) in MODES.items():
            z = (frames[:, ci].astype(float) + 1j * self.iq_sign * frames[:, cq]) * self.scale
            for key, band in self.filters.items():
                if key[0] != mode:
                    continue
                t, filtered = band.process(z)
                if not len(filtered):
                    continue
                row = dict(event_index=event_index, serial=serial, event_timestamp_unix=timestamp,
                           acquired_start_s=float(t[0]), acquired_stop_s=float(t[-1]),
                           **statistics(filtered, self.previous[key]))
                self.previous[key] = filtered[-1]
                self.rows[key].append(row)

    def export(self):
        modes = {mode: {} for mode in MODES}
        for (mode, index), rows in self.rows.items():
            modes[mode]["band_%02d" % index] = {
                "offset_hz": self.config["offsets_hz"][index],
                "center_hz": self.filters[mode, index].center,
                "events": {name: np.asarray([row[name] for row in rows]) for name in rows[0]} if rows else {}}
        return {"config": self.config, "modes": modes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="File .mid oppure .mid.gz")
    parser.add_argument("--out-dir", type=Path, default=Path("/home/mazzitel/HFGW/analysis-work/Run2/staging/examples/noise_results"))
    parser.add_argument("--max-events", type=positive_int, default=None,
                        help="Limite opzionale; per default legge tutto il run")
    parser.add_argument("--fs", type=float, default=5e6, help="Campionamento [Hz]")
    parser.add_argument("--input-range", type=float, default=5.0,
                        help="Semintervallo ADC [V], default: +/-5 V")
    parser.add_argument("--iq-sign", type=int, choices=(-1, 1), default=-1,
                        help="Convenzione IQ: default I-iQ (-1)")
    parser.add_argument("--bins", type=positive_int, default=1024,
                        help="Bin per modo sull’intervallo osservato (default: 1024)")
    parser.add_argument("--iq-bins", type=positive_int, default=256,
                        help="Bin per asse della densità IQ (default: 256)")
    parser.add_argument("--plot-points", type=positive_int, default=20000,
                        help="Limite dei campioni temporali salvati e visualizzati")
    parser.add_argument("--x-axis", choices=("samples", "time"), default="time",
                        help="Campioni cumulativi oppure tempo acquisito cumulativo")
    parser.add_argument("--replot-iq", action="store_true",
                        help="Il file posizionale è un NPZ esistente: rigenera solo IQ senza leggere MIDAS")
    parser.add_argument("--mode-workers", type=int, choices=(1, 2, 3), default=1,
                        help="Thread per i tre modi nella seconda passata; default 1, massimo 3")
    parser.add_argument("--global-reference", type=Path,
                        help="JSON di riferimento condiviso per soglie 3/5/7 sigma")
    parser.add_argument("--phase-lags", type=positive_int, nargs="+", default=[1, 10, 100],
                        help="Ritardi per delta fase, in campioni (default: 1 10 100)")
    parser.add_argument("--h5-only", action="store_true", help="Unico output HDF5 con dati, metadati e figure incorporate")
    parser.add_argument("--h5", action="store_true", help="Salva anche il dizionario completo in HDF5 (richiede h5py)")
    parser.add_argument("--filtered-bands", action="store_true", help="Verifiche IQ in bande simmetriche; abilita HDF5 e richiede scipy")
    parser.add_argument("--band-offsets-hz", type=float, nargs="+", default=[100e3, 250e3, 500e3, 1e6])
    parser.add_argument("--band-centers-hz", type=float, nargs=3, default=[0., 0., 0.])
    parser.add_argument("--band-width-hz", type=float, default=50e3)
    parser.add_argument("--band-taps", type=positive_int, default=2001)
    parser.add_argument("--band-decimation", type=positive_int, default=20)
    args = parser.parse_args()
    if not np.isfinite(args.fs) or args.fs <= 0:
        parser.error("--fs deve essere finita e positiva")
    if not np.isfinite(args.input_range) or args.input_range <= 0:
        parser.error("--input-range deve essere finito e positivo")
    if not args.file.is_file():
        parser.error("File di input non trovato: %s" % args.file)

    if args.replot_iq and args.file.suffix == ".h5":
        results = read_results_h5(args.file)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        plot_iq_results(flattened_arrays(results), results["summary"],
                        args.out_dir / (args.file.stem + "_iq.png"), args.x_axis)
        return

    if args.replot_iq:
        summary = json.loads(args.file.with_suffix(".json").read_text())
        args.out_dir.mkdir(parents=True, exist_ok=True)
        with np.load(args.file, allow_pickle=False) as saved:
            plot_iq_results(saved, summary, args.out_dir / (args.file.stem + "_iq.png"), args.x_axis)
        print("Grafico IQ rigenerato dai dati salvati")
        return

    if args.h5 or args.h5_only or args.filtered_bands:
        import h5py  # Fail before scanning MIDAS if the requested writer is unavailable.
    try:
        band_checks = FilteredBandChecks(args) if args.filtered_bands else None
    except ValueError as exc:
        parser.error(str(exc))

    reference = json.loads(args.global_reference.read_text()) if args.global_reference else None
    config = make_config(args.fs, args.input_range, args.iq_sign, args.phase_lags, reference)
    input_stat = args.file.stat()
    analysis_started = (time.perf_counter(), time.process_time())
    timings = {}
    reached_eof = True

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import midas.file_reader

    args.out_dir.mkdir(parents=True, exist_ok=True)
    pass_started = (time.perf_counter(), time.process_time())
    reader = midas.file_reader.MidasFile(str(args.file), use_numpy=True)
    processed = total = stride = 0
    stride = 1
    trace_indices = np.empty(0, dtype=np.int64)
    trace_events = np.empty(0, dtype=np.int64)
    states = {mode: {"n": 0, "mean": 0., "m2": 0., "zeros": 0,
                     "min": np.inf, "max": -np.inf,
                     "iq_low": 0., "iq_high": 0., "i": np.empty(0), "q": np.empty(0),
                     "counts": np.zeros(args.bins, dtype=np.int64),
                     "amplitude": np.empty(0), "phase": np.empty(0), "reference": None,
                     "phase_state_pass1": {}, "phase_state_pass2": {}}
              for mode in MODES}
    events = []
    try:
        for event in reader:
            if event.header.is_midas_internal_event() or "SPEC" not in event.banks:
                continue
            raw = np.asarray(event.banks["SPEC"].data, dtype=np.uint16)
            if raw.size == 0 or raw.size % 8:
                raise ValueError("Bank SPEC vuoto o non divisibile in 8 canali")
            frames = raw.view(np.int16).reshape(-1, 8)
            size = len(frames)
            # Decimazione adattiva: memoria limitata anche per run lunghi.
            while (total + size + stride - 1) // stride > args.plot_points:
                stride *= 2
            keep = trace_indices % stride == 0
            trace_indices = trace_indices[keep]
            trace_events = trace_events[keep]
            local = np.arange((-total) % stride, size, stride, dtype=np.int64)
            trace_indices = np.r_[trace_indices, total + local]
            trace_events = np.r_[trace_events, np.full(len(local), processed)]
            events.append({"serial": int(event.header.serial_number),
                           "start_sample": total, "samples": size,
                           "midas_timestamp": int(event.header.timestamp)})
            for mode, (ch_i, ch_q) in MODES.items():
                st = states[mode]
                amplitude, _, phase = analyze_mode(
                    frames[:, ch_i].astype(float) * (2 * args.input_range / 65535),
                    frames[:, ch_q].astype(float) * (2 * args.input_range / 65535), args.iq_sign, st["phase_state_pass1"])
                i = frames[:, ch_i].astype(float) * (2 * args.input_range / 65535)
                q = args.iq_sign * frames[:, ch_q].astype(float) * (2 * args.input_range / 65535)
                st["iq_low"] = min(st["iq_low"], float(i.min()), float(q.min()))
                st["iq_high"] = max(st["iq_high"], float(i.max()), float(q.max()))
                st["i"] = np.r_[st["i"][keep], i[local]]
                st["q"] = np.r_[st["q"][keep], q[local]]
                finite = np.flatnonzero(np.isfinite(phase))
                if st["reference"] is None and finite.size:
                    st["reference"] = float(phase[finite[0]])
                if st["reference"] is not None:
                    phase -= st["reference"]
                # Varianza combinata stabile, centrata sulla media di tutto il run.
                mean = float(amplitude.mean())
                delta = mean - st["mean"]
                new_n = st["n"] + size
                st["m2"] += float(np.sum((amplitude - mean)**2)) + delta**2 * st["n"] * size / new_n
                st["mean"] += delta * size / new_n
                st["n"] = new_n
                st["zeros"] += int(np.count_nonzero(amplitude == 0))
                st["min"] = min(st["min"], float(amplitude.min()))
                st["max"] = max(st["max"], float(amplitude.max()))
                st["amplitude"] = np.r_[st["amplitude"][keep], amplitude[local]]
                st["phase"] = np.r_[st["phase"][keep], phase[local]]
            total += size
            processed += 1
            if processed % 100 == 0:
                print("Passata 1: %d eventi SPEC, %.1f s wall" % (processed, time.perf_counter() - pass_started[0]), flush=True)
            if args.max_events is not None and processed >= args.max_events:
                reached_eof = False
                break
    finally:
        close = getattr(reader, "close", None)
        if close is not None:
            close()
    timings["pass1"] = {"wall_s": time.perf_counter() - pass_started[0],
                         "cpu_s": time.process_time() - pass_started[1]}
    if not processed:
        raise RuntimeError("Nessun evento SPEC trovato nel file")

    # Seconda lettura: soglia globale nota, conteggio esatto su tutti i
    # campioni (non sui punti decimati né sui bin dell'istogramma).
    envelope_width = max(1, (total + args.plot_points - 1) // args.plot_points)
    envelope_size = (total + envelope_width - 1) // envelope_width
    envelope_start = np.arange(envelope_size, dtype=np.int64) * envelope_width
    envelope_stop = np.minimum(envelope_start + envelope_width, total)
    envelope_indices = (envelope_start + envelope_stop - 1) / 2
    z3 = 3.0
    for st in states.values():
        low, high = st["min"], st["max"]
        if low == high:
            padding = max(2 * args.input_range / 65535, abs(low) * 1e-6)
            low, high = low - padding, high + padding
        padding_iq = max((st["iq_high"] - st["iq_low"]) * 0.03, 2 * args.input_range / 65535)
        st["iq_edges"] = np.linspace(st["iq_low"] - padding_iq,
                                      st["iq_high"] + padding_iq, args.iq_bins + 1)
        st["iq_counts"] = np.zeros((args.iq_bins, args.iq_bins), dtype=np.int64)
        st["amp_edges"] = np.linspace(low, high, args.bins + 1)
        st["envelope_min"] = np.full(envelope_size, np.inf)
        st["envelope_max"] = np.full(envelope_size, -np.inf)
        st["envelope_sum"] = np.zeros(envelope_size)
        st["peak_sample"] = np.full(envelope_size, -1, dtype=np.int64)
        st["peak_phase"] = np.full(envelope_size, np.nan)
        st["peak_i"] = np.full(envelope_size, np.nan)
        st["peak_q"] = np.full(envelope_size, np.nan)
        st["rms"] = float(np.sqrt(st["m2"] / st["n"]))
        st["threshold"] = st["mean"] + z3 * st["rms"]
        st["threshold_5sigma"] = st["mean"] + 5 * st["rms"]
        st["threshold_7sigma"] = st["mean"] + 7 * st["rms"]
        st["above_7sigma"] = 0
        st["events_above_7sigma"] = []
        st["phase_edges"] = np.linspace(-np.pi, np.pi, args.bins + 1)
        st["phase_counts"] = np.zeros(args.bins, dtype=np.int64)
        st["above_5sigma"] = 0
        st["events_above_5sigma"] = []
        st["above"] = 0
        st["events_above"] = []
    global_stats = RunStatistics(config, states)
    print("Seconda lettura: conteggio campioni sopra le soglie +3, +5 e +7 sigma", flush=True)
    reader = midas.file_reader.MidasFile(str(args.file), use_numpy=True)
    pass_started = (time.perf_counter(), time.process_time())
    executor = ThreadPoolExecutor(max_workers=args.mode_workers) if args.mode_workers > 1 else None
    seen = offset = 0
    try:
        for event in reader:
            if event.header.is_midas_internal_event() or "SPEC" not in event.banks:
                continue
            raw = np.asarray(event.banks["SPEC"].data, dtype=np.uint16)
            if raw.size == 0 or raw.size % 8:
                raise ValueError("Bank SPEC vuoto o non divisibile in 8 canali")
            frames = raw.view(np.int16).reshape(-1, 8)
            buckets = (offset + np.arange(len(frames), dtype=np.int64)) // envelope_width
            cuts = np.r_[0, np.flatnonzero(np.diff(buckets)) + 1, len(frames)]
            serial = int(event.header.serial_number)
            if executor is None:
                for mode, channels in MODES.items():
                    process_second_mode(mode, channels, frames, states, global_stats, args,
                                        buckets, cuts, offset, seen, serial)
            else:
                futures = [executor.submit(process_second_mode, mode, channels, frames,
                            states, global_stats, args, buckets, cuts, offset, seen, serial)
                           for mode, channels in MODES.items()]
                # Prima di leggere l'evento successivo tutti i modi devono essere completi.
                for future in futures:
                    future.result()
            if band_checks is not None:
                band_checks.update(frames, seen, serial, int(event.header.timestamp))
            offset += len(frames)
            seen += 1
            if seen % 100 == 0:
                print("Passata 2: %d/%d eventi SPEC, %.1f s wall" %
                      (seen, processed, time.perf_counter() - pass_started[0]), flush=True)
            if seen >= processed:
                break
    finally:
        if executor is not None:
            executor.shutdown(wait=True)
        close = getattr(reader, "close", None)
        if close is not None:
            close()
    timings["pass2"] = {"wall_s": time.perf_counter() - pass_started[0],
                         "cpu_s": time.process_time() - pass_started[1]}
    if seen != processed:
        raise RuntimeError("Il numero di eventi è cambiato durante la seconda lettura")

    final_stat = args.file.stat()
    if (final_stat.st_size, final_stat.st_mtime_ns) != (input_stat.st_size, input_stat.st_mtime_ns):
        raise RuntimeError("Il file MIDAS è cambiato durante l'analisi")
    global_summary, global_arrays = global_stats.export()
    if any(st["n"] != total for st in global_summary["modes"].values()):
        raise RuntimeError("Conteggio campioni diverso tra le due letture")

    stem = args.file.name.split(".mid")[0] + "_noise"
    saved = {"sample_indices": trace_indices, "time_s": trace_indices / args.fs,
             "event_index": trace_events,
             "envelope_start_sample": envelope_start, "envelope_stop_sample": envelope_stop,
             "envelope_sample_indices": envelope_indices}
    saved.update(global_arrays)
    summary = {"input": str(args.file), "status": "success", "reached_eof": reached_eof,
               "selection": {"max_events": args.max_events},
               "input_size_bytes": input_stat.st_size, "input_mtime_ns": input_stat.st_mtime_ns,
               "acquired_duration_s": total / args.fs, "global_statistics": global_summary, "events": events, "samples": total,
               "fs_hz": args.fs, "input_range_v": args.input_range, "iq_sign": args.iq_sign,
               "trace_stride": stride, "histogram_bins": args.bins,
               "iq_bins_per_axis": args.iq_bins,
               "iq_coordinates": "I, iq_sign * Q in volts, no mean subtraction; density uses all samples; trajectory subsampled",
               "amplitude_envelope_width_samples": envelope_width,
               "time_axis": "continuous samples / fs within run; possible gaps only between runs",
               "phase_reference": "first valid run sample; continuous unwrap across SPEC boundaries; zero amplitude masked; minimum-jump unwrap between valid samples",
               "histogram": "all samples; per-mode observed range, edges shifted by global run mean",
               "modes": {}}
    plot_started = (time.perf_counter(), time.process_time())
    fig, axes = plt.subplots(3, 4, figsize=(22, 11), squeeze=False)
    x = trace_indices if args.x_axis == "samples" else trace_indices / args.fs
    xlabel = "Cumulative sample" if args.x_axis == "samples" else "Continuous run time [s]"
    # SPEC è un contenitore: nessuna discontinuità al confine.
    breaks = np.empty(0, dtype=int)
    plot_x = np.insert(x.astype(float), breaks, np.nan)
    try:
        for row, (mode, st) in enumerate(states.items()):
            rms = float(np.sqrt(st["m2"] / st["n"]))
            edges = st["amp_edges"] - st["mean"]
            envelope_mean = st["envelope_sum"] / (envelope_stop - envelope_start)
            saved[mode + "_envelope_mean_v"] = envelope_mean
            saved[mode + "_envelope_min_v"] = st["envelope_min"]
            saved[mode + "_envelope_max_v"] = st["envelope_max"]
            saved[mode + "_peak_sample_indices"] = st["peak_sample"]
            saved[mode + "_peak_delta_phase_rad"] = st["peak_phase"]
            saved[mode + "_noise_counts"] = st["counts"]
            saved[mode + "_noise_edges_v"] = edges
            saved[mode + "_amplitude_v"] = st["amplitude"]
            saved[mode + "_delta_phase_rad"] = st["phase"]
            saved[mode + "_phase_counts"] = st["phase_counts"]
            saved[mode + "_phase_edges_rad"] = st["phase_edges"]
            saved[mode + "_amplitude_threshold_7sigma_v"] = st["threshold_7sigma"]
            saved[mode + "_samples_above_7sigma"] = st["above_7sigma"]
            summary["modes"][mode] = {"mean_amplitude_v": st["mean"],
                "amplitude_noise_rms_v": rms, "zero_amplitude_samples": st["zeros"],
                "gaussian_quantile": NormalDist().cdf(z3), "gaussian_z": z3,
                "amplitude_threshold_v": st["threshold"],
                "samples_above_threshold": st["above"],
                "fraction_above_threshold": st["above"] / st["n"],
                "expected_gaussian_samples_above": gaussian_tail(z3) * st["n"],
                "events_above_threshold": st["events_above"],
                "amplitude_threshold_5sigma_v": st["threshold_5sigma"],
                "samples_above_5sigma": st["above_5sigma"],
                "fraction_above_5sigma": st["above_5sigma"] / st["n"],
                "expected_gaussian_samples_above_5sigma": gaussian_tail(5) * st["n"],
                "events_above_5sigma": st["events_above_5sigma"],
                "amplitude_threshold_7sigma_v": st["threshold_7sigma"],
                "samples_above_7sigma": st["above_7sigma"],
                "fraction_above_7sigma": st["above_7sigma"] / st["n"],
                "expected_gaussian_samples_above_7sigma": gaussian_tail(7) * st["n"],
                "events_above_7sigma": st["events_above_7sigma"],
                "phase_histogram": "wrapped delta phase [-pi, pi), relative to first valid run sample; zero-amplitude samples excluded",
                "phase_histogram_samples": int(st["phase_counts"].sum())}
            saved[mode + "_amplitude_threshold_v"] = st["threshold"]
            saved[mode + "_samples_above_threshold"] = st["above"]
            axes[row, 0].stairs(st["counts"], edges, label="Observed")
            saved[mode + "_amplitude_threshold_5sigma_v"] = st["threshold_5sigma"]
            saved[mode + "_samples_above_5sigma"] = st["above_5sigma"]
            threshold = z3 * rms
            axes[row, 0].axvline(7 * rms, color="darkgreen", linestyle="-.", label="+7 sigma")
            axes[row, 0].axvline(5 * rms, color="purple", linestyle=":", label="+5 sigma")
            axes[row, 0].axvline(threshold, color="crimson", linestyle="--", label="+3 sigma")
            axes[row, 0].axvspan(threshold, max(edges[-1], threshold), color="crimson", alpha=0.12)
            if rms > 0:
                normal = NormalDist(0, rms)
                expected = st["n"] * np.diff([normal.cdf(float(e)) for e in edges])
                axes[row, 0].stairs(expected, edges, color="darkorange", label="Gaussian model")
            axes[row, 0].set_yscale("log")
            axes[row, 0].set_ylim(bottom=0.5)
            occupied = np.flatnonzero(st["counts"])
            if occupied.size:
                axes[row, 0].set_xlim(min(edges[occupied[0]], 0),
                    max(edges[occupied[-1] + 1], 7 * rms) + (edges[1] - edges[0]))
            axes[row, 0].text(0.03, 0.97,
                "N = %d samples / %d events\nAbove +3 sigma: %d (%.4g%%)\nGaussian expectation: %.1f\nAbove +5 sigma: %d (%.4g%%)\nGaussian expectation (+5 sigma): %.3g\nAbove +7 sigma: %d (%.4g%%)\nGaussian expectation (+7 sigma): %.3g" %
                (st["n"], processed, st["above"], 100 * st["above"] / st["n"], gaussian_tail(z3) * st["n"],
                 st["above_5sigma"], 100 * st["above_5sigma"] / st["n"],
                 gaussian_tail(5) * st["n"], st["above_7sigma"],
                 100 * st["above_7sigma"] / st["n"], gaussian_tail(7) * st["n"]),
                transform=axes[row, 0].transAxes, va="top", fontsize=8)
            axes[row, 0].legend(loc="lower left", fontsize=7)
            axes[row, 0].set(xlabel="A - run mean(A) [V]", ylabel="Samples",
                             title="%s: noise RMS %.4g V" % (mode, rms))
            env_edges = np.r_[envelope_start, total].astype(float)
            env_x = envelope_indices.copy()
            if args.x_axis == "time":
                env_edges /= args.fs
                env_x /= args.fs
            axes[row, 1].stairs(st["envelope_max"], env_edges,
                baseline=st["envelope_min"], fill=True, alpha=0.3, label="Min/max (all samples)")
            axes[row, 1].plot(env_x, envelope_mean, linewidth=0.6, label="Interval mean")
            axes[row, 1].set(xlabel=xlabel, ylabel="Amplitude [V]", title=mode)
            axes[row, 3].plot(plot_x, np.insert(st["phase"], breaks, np.nan),
                              linewidth=0.5, marker=".", markersize=1)
            axes[row, 3].set(xlabel=xlabel, ylabel="Delta phase [rad]", title=mode)
            axes[row, 1].axhline(st["threshold"], color="crimson", linestyle="--", linewidth=0.8)
            axes[row, 1].axhline(st["threshold_5sigma"], color="purple", linestyle=":", linewidth=0.8)
            peak_x = st["peak_sample"].astype(float)
            if args.x_axis == "time":
                peak_x /= args.fs
            above = st["envelope_max"] > st["threshold"]
            axes[row, 1].scatter(peak_x[above], st["envelope_max"][above],
                                 color="crimson", s=8, zorder=3, label="Interval peak >3 sigma")
            above5 = st["envelope_max"] > st["threshold_5sigma"]
            axes[row, 1].scatter(peak_x[above5], st["envelope_max"][above5],
                                 color="purple", marker="x", s=12, zorder=4, label="Interval peak >5 sigma")
            axes[row, 1].axhline(st["threshold_7sigma"], color="darkgreen", linestyle="-.", linewidth=0.8)
            above7 = st["envelope_max"] > st["threshold_7sigma"]
            axes[row, 1].scatter(peak_x[above7], st["envelope_max"][above7],
                color="darkgreen", marker="*", s=20, zorder=5, label="Interval peak >7 sigma")
            axes[row, 2].stairs(st["phase_counts"], st["phase_edges"])
            axes[row, 2].set(xlabel="Wrapped delta phase [rad]", ylabel="Samples",
                             title=mode + ": phase distribution", xlim=(-np.pi, np.pi))
            axes[row, 2].set_yscale("log")
            axes[row, 2].set_ylim(bottom=0.5)
            axes[row, 1].legend(fontsize=6, loc="lower left")
            print("%s: mean amplitude = %.6g V, noise RMS = %.6g V" % (mode, st["mean"], rms))
        fig.suptitle("%s — %d events, %d samples (amplitude: all-sample envelope; phase: subsampled)" %
                     (args.file.name, processed, total))
        fig.tight_layout()
        fig.savefig(args.out_dir / (stem + ".png"), dpi=150)
    finally:
        plt.close(fig)
    for mode, st in states.items():
        saved[mode + "_iq_counts"] = st["iq_counts"]
        saved[mode + "_iq_i_edges_v"] = st["iq_edges"]
        saved[mode + "_iq_q_edges_v"] = st["iq_edges"]
        saved[mode + "_i_v"] = st["i"]
        saved[mode + "_q_signed_v"] = st["q"]
        saved[mode + "_peak_i_v"] = st["peak_i"]
        saved[mode + "_peak_q_signed_v"] = st["peak_q"]
        classes = np.zeros(len(st["envelope_max"]), dtype=np.int8)
        for sigma, key in ((3, "threshold"), (5, "threshold_5sigma"), (7, "threshold_7sigma")):
            classes[st["envelope_max"] > st[key]] = sigma
        saved[mode + "_peak_sigma_class"] = classes
        summary["modes"][mode]["iq_peak_markers"] = {
            "definition": "exclusive classes of interval maxima, shown separately from time samples",
            "3_to_5sigma": int(np.count_nonzero(classes == 3)),
            "5_to_7sigma": int(np.count_nonzero(classes == 5)),
            "above_7sigma": int(np.count_nonzero(classes == 7))}
    plot_iq_results(saved, summary, args.out_dir / (stem + "_iq.png"), args.x_axis)
    timings["plots"] = {"wall_s": time.perf_counter() - plot_started[0],
                        "cpu_s": time.process_time() - plot_started[1]}
    save_started = (time.perf_counter(), time.process_time())
    if not args.h5_only:
        np.savez_compressed(args.out_dir / (stem + ".npz"), **saved)
    timings["save_npz"] = {"wall_s": time.perf_counter() - save_started[0],
                           "cpu_s": time.process_time() - save_started[1]}
    timings["total"] = {"wall_s": time.perf_counter() - analysis_started[0],
                        "cpu_s": time.process_time() - analysis_started[1]}
    summary["performance"] = {"implementation": "continuous-run-valid-phase-mode-threads-v3",
                               "mode_workers": args.mode_workers,
                               "scope": "local Python analysis; excludes input download and remote upload",
                               "timings": timings}
    results = build_results(summary, saved, band_checks.export() if band_checks is not None else None)
    figures = [args.out_dir / (stem + suffix) for suffix in (".png", "_iq.png")]
    if args.h5 or args.h5_only or args.filtered_bands:
        results["figures"] = {path.stem: {"format": "png", "data": np.frombuffer(path.read_bytes(), dtype=np.uint8)}
                              for path in figures}
        save_results_h5(args.out_dir / (stem + ".h5"), results)
    print("Tempi analisi: " + json.dumps(timings), flush=True)
    if args.h5_only:
        for path in figures:
            path.unlink()
    else:
        (args.out_dir / (stem + ".json")).write_text(json.dumps(summary, indent=2) + "\n")
    print("Analizzati %d eventi SPEC. Risultati: %s" % (processed, args.out_dir))


if __name__ == "__main__":
    main()
