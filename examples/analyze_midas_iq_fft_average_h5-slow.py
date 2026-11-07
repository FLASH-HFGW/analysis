#!/usr/bin/env python3

import os
import re
import gc
import argparse
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import h5py
import midas.file_reader


# ============================================================
# Parser
# ============================================================

parser = argparse.ArgumentParser(
    description=(
        "Legge un file MIDAS e salva FFT mediate in un unico HDF5. "
        "Versione async/bounded per usare 8 worker senza accumulare raw events in RAM."
    )
)

parser.add_argument("--path", required=True,
                    help="Directory contenente i file MIDAS, es: ~/flash-data/data/LNF/")

parser.add_argument("--run", required=True, type=int,
                    help="Numero run, es: 386")

parser.add_argument("--fs", type=float, default=5e6,
                    help="Sampling frequency [Hz]. Default: 5e6")

parser.add_argument("--input-range", type=float, default=5.0,
                    help="Input range ADC in Volt, es. 5 per +/-5 V. Default: 5")

parser.add_argument("--iq-sign", type=int, default=+1, choices=[+1, -1],
                    help="Convenzione I/Q: +1 usa I + jQ, -1 usa I - jQ. Default: +1")

parser.add_argument(
    "--iq-modes",
    default="TM010:0,1;TM011:2,3;TM012:4,5",
    help=(
        "Definizione modi I/Q. Default: 'TM010:0,1;TM011:2,3;TM012:4,5'. "
        "Per replicare il vecchio script: 'TM010:0,1;TM011:2,3;TM012:3,5'"
    )
)

parser.add_argument("--pps-channel", type=int, default=6,
                    help="Canale PPS. Default: 6")

parser.add_argument("--max-spec-events", type=int, default=0,
                    help="Numero massimo di eventi SPEC da leggere. Default: 0 = tutti.")


# ------------------------------------------------------------
# Media
# ------------------------------------------------------------

avg_group = parser.add_mutually_exclusive_group()

avg_group.add_argument(
    "--avg-events",
    type=int,
    default=None,
    help=(
        "Numero di eventi SPEC da mediare per blocco. "
        "Esempio: 5 eventi da ~208 ms fanno circa 1 secondo. "
        "Default: 5 se non usi --avg-seconds o --avg-all."
    )
)

avg_group.add_argument(
    "--avg-seconds",
    type=float,
    default=None,
    help="Durata temporale del blocco di media in secondi."
)

avg_group.add_argument(
    "--avg-all",
    action="store_true",
    help="Media tutti gli eventi SPEC del file in un unico blocco."
)

parser.add_argument(
    "--acc-dtype",
    default="float64",
    choices=["float64", "float32"],
    help="Tipo accumulatore per sum_power. float64 = più preciso, float32 = meno RAM. Default: float64."
)


# ------------------------------------------------------------
# Output HDF5
# ------------------------------------------------------------

parser.add_argument("--h5-out", default="/home/mazzitel/HFGW/analysis-work/Run2/staging/examples/fft_average_h5",
                    help="Directory dove salvare il file HDF5. Default: fft_average_h5")

parser.add_argument("--h5-name", default=None,
                    help="Nome file HDF5 di output. Default: runXXXXX_fft_average.h5")

parser.add_argument("--h5-compression", default="gzip",
                    choices=["gzip", "lzf", "none"],
                    help="Compressione HDF5. Default: gzip")

parser.add_argument("--h5-gzip-level", type=int, default=3,
                    help="Livello gzip HDF5. Default: 3")

parser.add_argument(
    "--h5-chunk-freq",
    type=int,
    default=1048576,
    help="Numero di bin di frequenza per chunk HDF5. Non cambia la risoluzione. Default: 1048576"
)

parser.add_argument("--flush-every", type=int, default=5,
                    help="Flush del file HDF5 ogni N blocchi mediati. Default: 5")


# ------------------------------------------------------------
# Cosa salvare
# ------------------------------------------------------------

parser.add_argument(
    "--save-complex-mean",
    action="store_true",
    help=(
        "Salva anche la media complessa coerente mean(FFT), come real/imag. "
        "Utile solo se la fase è significativa/stabile."
    )
)

parser.add_argument(
    "--save-rms-amp",
    action="store_true",
    help="Salva anche sqrt(mean_power). È derivabile da mean_power, ma può essere comodo."
)


# ------------------------------------------------------------
# FFT
# ------------------------------------------------------------

parser.add_argument("--no-window", action="store_true",
                    help="Disabilita finestra Hann. Default: Hann abilitata.")


# ------------------------------------------------------------
# Parallelismo
# ------------------------------------------------------------

parser.add_argument(
    "--workers",
    type=int,
    default=8,
    help="Numero worker paralleli per job FFT evento×modo. Default: 8"
)

parser.add_argument(
    "--mode-workers",
    type=int,
    default=None,
    help="Alias deprecato di --workers."
)

parser.add_argument(
    "--max-inflight-jobs",
    type=int,
    default=16,
    help=(
        "Numero massimo di job FFT contemporaneamente pendenti/in memoria. "
        "Default: 16. Usa 8 se hai poca RAM, 16-24 se hai RAM sufficiente."
    )
)

parser.add_argument("--verbose", action="store_true",
                    help="Verbose output")

args = parser.parse_args()


# ============================================================
# Validazione
# ============================================================

if args.max_spec_events < 0:
    raise ValueError("--max-spec-events deve essere >= 0. Usa 0 per tutti.")

if args.fs <= 0:
    raise ValueError("--fs deve essere > 0")

if args.input_range <= 0:
    raise ValueError("--input-range deve essere > 0")

if args.h5_gzip_level < 0 or args.h5_gzip_level > 9:
    raise ValueError("--h5-gzip-level deve essere tra 0 e 9")

if args.h5_chunk_freq <= 0:
    raise ValueError("--h5-chunk-freq deve essere > 0")

if args.flush_every <= 0:
    raise ValueError("--flush-every deve essere > 0")

if args.avg_events is None and args.avg_seconds is None and not args.avg_all:
    args.avg_events = 5

if args.avg_events is not None and args.avg_events <= 0:
    raise ValueError("--avg-events deve essere > 0")

if args.avg_seconds is not None and args.avg_seconds <= 0:
    raise ValueError("--avg-seconds deve essere > 0")

if args.mode_workers is not None:
    args.workers = args.mode_workers

if args.workers <= 0:
    raise ValueError("--workers deve essere > 0")

if args.max_inflight_jobs <= 0:
    raise ValueError("--max-inflight-jobs deve essere > 0")

if args.max_inflight_jobs < args.workers:
    print(
        "WARNING: --max-inflight-jobs < --workers. "
        "I worker non saranno sempre saturi."
    )


# ============================================================
# Configurazione
# ============================================================

run = args.run
path = os.path.expanduser(args.path)
fs = float(args.fs)
input_range = float(args.input_range)
iq_sign = int(args.iq_sign)
verbose = bool(args.verbose)

Nch = 8
pps_channel = int(args.pps_channel)

scale = np.float32(2.0 * input_range / 65536.0)
acc_dtype = np.float64 if args.acc_dtype == "float64" else np.float32

fname = "run%05d.mid.gz" % run
full_name = os.path.join(path, fname)

h5_out = os.path.expanduser(args.h5_out)
os.makedirs(h5_out, exist_ok=True)

if args.h5_name is None:
    h5_name = os.path.join(h5_out, "run%05d_fft_average.h5" % run)
else:
    h5_name = os.path.expanduser(args.h5_name)
    if not os.path.isabs(h5_name):
        h5_name = os.path.join(h5_out, h5_name)

os.makedirs(os.path.dirname(os.path.abspath(h5_name)), exist_ok=True)


# ============================================================
# Parse modi I/Q
# ============================================================

def parse_iq_modes(spec):
    """
    Esempio:
      'TM010:0,1;TM011:2,3;TM012:4,5'
    """
    out = {}

    for item in spec.split(";"):
        item = item.strip()
        if not item:
            continue

        name, chans = item.split(":")
        ci, cq = chans.split(",")

        name = name.strip()
        ci = int(ci)
        cq = int(cq)

        if ci < 0 or ci >= Nch or cq < 0 or cq >= Nch:
            raise ValueError(f"Canali fuori range per {name}: {ci}, {cq}")

        out[name] = (ci, cq)

    if not out:
        raise ValueError("Nessun modo I/Q valido in --iq-modes")

    return out


iq_modes = parse_iq_modes(args.iq_modes)
mode_names = list(iq_modes.keys())
nmodes = len(mode_names)

print("Reading:", full_name)
print("Output HDF5:", h5_name)
print("IQ modes:", iq_modes)
print("Average all:", args.avg_all)
print("Average by events:", args.avg_events)
print("Average by seconds:", args.avg_seconds)
print("Workers:", args.workers)
print("Max inflight jobs:", args.max_inflight_jobs)
print("Accumulator dtype:", args.acc_dtype)
print("Compression:", args.h5_compression, args.h5_gzip_level)
print("Save complex mean:", args.save_complex_mean)
print("Save RMS amp:", args.save_rms_amp)
print("Use Hann window:", not args.no_window)


# ============================================================
# TGPS helpers
# ============================================================

TZ_OFFSETS = {
    "UTC": 0,
    "GMT": 0,
    "CET": 1,
    "CEST": 2,
}


def tgps_bank_to_string(arr):
    return ''.join(chr(int(x)) for x in arr if int(x) != 0)


def tgps_string_to_unix(stime):
    m = re.search(
        r"(?P<date>\d{4}-\d{2}-\d{2})\s+"
        r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})\s+"
        r"(?P<tz>[A-Z]{2,4})",
        stime
    )

    if m is None:
        raise ValueError(f"Formato TGPS non riconosciuto: {stime!r}")

    year, month, day = map(int, m.group("date").split("-"))
    hour = int(m.group("hour"))
    minute = int(m.group("minute"))
    second = int(m.group("second"))
    tz_name = m.group("tz")

    if tz_name not in TZ_OFFSETS:
        raise ValueError(f"Timezone non riconosciuta: {tz_name}")

    tz = timezone(timedelta(hours=TZ_OFFSETS[tz_name]))

    dt_local = datetime(
        year, month, day,
        hour, minute, second,
        tzinfo=tz
    )

    return int(dt_local.timestamp())


def tgps_bank_to_unix(arr):
    stime = tgps_bank_to_string(arr)
    return tgps_string_to_unix(stime)


# ============================================================
# PPS helper
# ============================================================

def lengths_above_threshold(x: np.ndarray, threshold: float):
    if x.ndim != 1:
        raise ValueError("L'array deve essere 1D")

    above = x > threshold

    if not np.any(above):
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64)

    d = np.diff(above.astype(np.int8))

    starts = np.where(d == 1)[0] + 1
    ends = np.where(d == -1)[0] + 1

    if above[0]:
        starts = np.r_[0, starts]

    if above[-1]:
        ends = np.r_[ends, len(x)]

    lengths = ends - starts

    return starts.astype(np.int64), lengths.astype(np.int64)


# ============================================================
# FFT helpers
# ============================================================

def find_peak_excluding_dc(power, freq, guard_bins=2):
    """
    Picco sulla potenza media, escludendo alcuni bin attorno a DC.
    """
    nsamp = len(power)
    dc_index = nsamp // 2

    i0 = max(0, dc_index - guard_bins)
    i1 = min(nsamp, dc_index + guard_bins + 1)

    best_idx = None
    best_val = -np.inf

    if i0 > 0:
        il = int(np.argmax(power[:i0]))
        vl = float(power[il])
        if vl > best_val:
            best_val = vl
            best_idx = il

    if i1 < nsamp:
        ir_rel = int(np.argmax(power[i1:]))
        ir = i1 + ir_rel
        vr = float(power[ir])
        if vr > best_val:
            best_val = vr
            best_idx = ir

    if best_idx is None:
        best_idx = int(np.argmax(power))
        best_val = float(power[best_idx])

    return float(freq[best_idx]), best_val, int(best_idx)


def complex_fft_power_job(
    frames_adc,
    mode_index,
    mode_name,
    ch_i,
    ch_q,
    scale,
    iq_sign,
    window,
    coherent_gain,
    save_complex_mean=False,
):
    """
    Calcola FFT complessa per un evento e un modo.

    Ritorna:
      mode_index
      power = |FFT/coherent_gain|^2, float32
      real/imag opzionali della FFT normalizzata, float32
    """
    I = frames_adc[:, ch_i].astype(np.float32)
    Q = frames_adc[:, ch_q].astype(np.float32)

    I *= scale
    Q *= scale

    I -= np.float32(np.mean(I, dtype=np.float64))
    Q -= np.float32(np.mean(Q, dtype=np.float64))

    z = I.astype(np.complex64)
    z += (1j * iq_sign) * Q.astype(np.complex64)

    del I, Q

    if window is not None:
        z *= window

    Z = np.fft.fft(z)
    del z

    Z = np.fft.fftshift(Z)
    Z /= float(coherent_gain)

    power = (Z.real * Z.real + Z.imag * Z.imag).astype(np.float32)

    if save_complex_mean:
        real = Z.real.astype(np.float32)
        imag = Z.imag.astype(np.float32)
    else:
        real = None
        imag = None

    del Z

    return {
        "mode_index": int(mode_index),
        "mode_name": mode_name,
        "power": power,
        "real": real,
        "imag": imag,
    }


# ============================================================
# HDF5 helpers
# ============================================================

def h5_compression_kwargs(args):
    if args.h5_compression == "none":
        return {}

    if args.h5_compression == "lzf":
        return {
            "compression": "lzf",
            "shuffle": True,
        }

    if args.h5_compression == "gzip":
        return {
            "compression": "gzip",
            "compression_opts": args.h5_gzip_level,
            "shuffle": True,
        }

    raise ValueError("Compressione HDF5 non riconosciuta")


def init_h5_file(
    h5_name,
    args,
    run,
    run_description,
    fs,
    nsamp,
    freq,
    iq_modes,
    input_range,
    iq_sign,
    use_window,
):
    mode_names_local = list(iq_modes.keys())
    nmodes_local = len(mode_names_local)
    nfreq = len(freq)

    comp = h5_compression_kwargs(args)
    str_dtype = h5py.string_dtype(encoding="utf-8")

    h5 = h5py.File(h5_name, "w")

    h5.attrs["run"] = int(run)
    h5.attrs["run_description"] = str(run_description) if run_description else ""
    h5.attrs["fs"] = float(fs)
    h5.attrs["nsamp"] = int(nsamp)
    h5.attrs["df"] = float(fs / nsamp)
    h5.attrs["input_range"] = float(input_range)
    h5.attrs["iq_sign"] = int(iq_sign)
    h5.attrs["use_window"] = bool(use_window)
    h5.attrs["n_channels"] = int(Nch)
    h5.attrs["pps_channel"] = int(pps_channel)
    h5.attrs["average_type"] = "mean_power"
    h5.attrs["average_definition"] = "mean(|FFT/coherent_gain|^2)"
    h5.attrs["fft_type"] = "complex_two_sided_fftshift"
    h5.attrs["save_complex_mean"] = bool(args.save_complex_mean)
    h5.attrs["save_rms_amp"] = bool(args.save_rms_amp)
    h5.attrs["acc_dtype"] = str(args.acc_dtype)
    h5.attrs["workers"] = int(args.workers)
    h5.attrs["max_inflight_jobs"] = int(args.max_inflight_jobs)

    if args.avg_all:
        h5.attrs["average_mode"] = "all"
    elif args.avg_events is not None:
        h5.attrs["average_mode"] = "events"
        h5.attrs["average_events"] = int(args.avg_events)
    else:
        h5.attrs["average_mode"] = "seconds"
        h5.attrs["average_seconds"] = float(args.avg_seconds)

    h5.create_dataset(
        "mode_names",
        data=np.array(mode_names_local, dtype=object),
        dtype=str_dtype,
    )

    h5.create_dataset(
        "ch_i",
        data=np.array([iq_modes[m][0] for m in mode_names_local], dtype=np.int16),
    )

    h5.create_dataset(
        "ch_q",
        data=np.array([iq_modes[m][1] for m in mode_names_local], dtype=np.int16),
    )

    h5.create_dataset(
        "fft_freq",
        data=freq.astype(np.float32),
        **comp,
    )

    # Metadata blocchi
    for name, dtype in [
        ("block_index", np.int64),
        ("n_events", np.int64),
        ("event_first", np.int64),
        ("event_last", np.int64),
        ("midas_timestamp_start", np.int64),
        ("midas_timestamp_end", np.int64),
        ("tgps_unix_start", np.int64),
        ("tgps_unix_end", np.int64),
        ("pps_trigger_first", np.int64),
        ("pps_trigger_last", np.int64),
        ("pps_min", np.float32),
        ("pps_max", np.float32),
    ]:
        h5.create_dataset(
            name,
            shape=(0,),
            maxshape=(None,),
            chunks=(1024,),
            dtype=dtype,
        )

    h5.create_dataset(
        "tgps_string_start",
        shape=(0,),
        maxshape=(None,),
        chunks=(1024,),
        dtype=str_dtype,
    )

    h5.create_dataset(
        "tgps_string_end",
        shape=(0,),
        maxshape=(None,),
        chunks=(1024,),
        dtype=str_dtype,
    )

    # Picchi sulla potenza media
    h5.create_dataset(
        "peak_freq",
        shape=(0, nmodes_local),
        maxshape=(None, nmodes_local),
        chunks=(1024, nmodes_local),
        dtype=np.float64,
        **comp,
    )

    h5.create_dataset(
        "peak_power",
        shape=(0, nmodes_local),
        maxshape=(None, nmodes_local),
        chunks=(1024, nmodes_local),
        dtype=np.float32,
        **comp,
    )

    h5.create_dataset(
        "peak_rms_amp",
        shape=(0, nmodes_local),
        maxshape=(None, nmodes_local),
        chunks=(1024, nmodes_local),
        dtype=np.float32,
        **comp,
    )

    h5.create_dataset(
        "peak_index",
        shape=(0, nmodes_local),
        maxshape=(None, nmodes_local),
        chunks=(1024, nmodes_local),
        dtype=np.int64,
        **comp,
    )

    chunk_freq = min(int(args.h5_chunk_freq), nfreq)

    h5.create_dataset(
        "mean_power",
        shape=(0, nmodes_local, nfreq),
        maxshape=(None, nmodes_local, nfreq),
        chunks=(1, 1, chunk_freq),
        dtype=np.float32,
        **comp,
    )

    if args.save_rms_amp:
        h5.create_dataset(
            "rms_amp",
            shape=(0, nmodes_local, nfreq),
            maxshape=(None, nmodes_local, nfreq),
            chunks=(1, 1, chunk_freq),
            dtype=np.float32,
            **comp,
        )

    if args.save_complex_mean:
        h5.create_dataset(
            "mean_fft_real",
            shape=(0, nmodes_local, nfreq),
            maxshape=(None, nmodes_local, nfreq),
            chunks=(1, 1, chunk_freq),
            dtype=np.float32,
            **comp,
        )

        h5.create_dataset(
            "mean_fft_imag",
            shape=(0, nmodes_local, nfreq),
            maxshape=(None, nmodes_local, nfreq),
            chunks=(1, 1, chunk_freq),
            dtype=np.float32,
            **comp,
        )

    return h5


def append_h5_average_block(
    h5,
    block_index,
    meta,
    mean_power,
    peak_freq,
    peak_power,
    peak_rms_amp,
    peak_index,
    rms_amp=None,
    mean_real=None,
    mean_imag=None,
    flush=False,
):
    i = h5["block_index"].shape[0]

    nmodes_local = h5["mean_power"].shape[1]
    nfreq = h5["mean_power"].shape[2]

    one_datasets = [
        "block_index",
        "n_events",
        "event_first",
        "event_last",
        "midas_timestamp_start",
        "midas_timestamp_end",
        "tgps_unix_start",
        "tgps_unix_end",
        "pps_trigger_first",
        "pps_trigger_last",
        "pps_min",
        "pps_max",
        "tgps_string_start",
        "tgps_string_end",
    ]

    for name in one_datasets:
        h5[name].resize((i + 1,))

    for name in ["peak_freq", "peak_power", "peak_rms_amp", "peak_index"]:
        h5[name].resize((i + 1, nmodes_local))

    h5["mean_power"].resize((i + 1, nmodes_local, nfreq))

    if "rms_amp" in h5:
        h5["rms_amp"].resize((i + 1, nmodes_local, nfreq))

    if "mean_fft_real" in h5:
        h5["mean_fft_real"].resize((i + 1, nmodes_local, nfreq))
        h5["mean_fft_imag"].resize((i + 1, nmodes_local, nfreq))

    first = meta[0]
    last = meta[-1]

    h5["block_index"][i] = int(block_index)
    h5["n_events"][i] = int(len(meta))
    h5["event_first"][i] = int(first["event_number"])
    h5["event_last"][i] = int(last["event_number"])
    h5["midas_timestamp_start"][i] = int(first["midas_timestamp"])
    h5["midas_timestamp_end"][i] = int(last["midas_timestamp"])
    h5["tgps_unix_start"][i] = int(first["tgps_unix"])
    h5["tgps_unix_end"][i] = int(last["tgps_unix"])
    h5["pps_trigger_first"][i] = int(first["pps_trigger"])
    h5["pps_trigger_last"][i] = int(last["pps_trigger"])
    h5["pps_min"][i] = np.float32(min(ev["pps_min"] for ev in meta))
    h5["pps_max"][i] = np.float32(max(ev["pps_max"] for ev in meta))
    h5["tgps_string_start"][i] = str(first["tgps_string"])
    h5["tgps_string_end"][i] = str(last["tgps_string"])

    h5["peak_freq"][i, :] = peak_freq
    h5["peak_power"][i, :] = peak_power
    h5["peak_rms_amp"][i, :] = peak_rms_amp
    h5["peak_index"][i, :] = peak_index

    h5["mean_power"][i, :, :] = mean_power

    if "rms_amp" in h5:
        if rms_amp is None:
            raise RuntimeError("rms_amp richiesto ma None")
        h5["rms_amp"][i, :, :] = rms_amp

    if "mean_fft_real" in h5:
        if mean_real is None or mean_imag is None:
            raise RuntimeError("mean complex richiesto ma None")
        h5["mean_fft_real"][i, :, :] = mean_real
        h5["mean_fft_imag"][i, :, :] = mean_imag

    if flush:
        h5.flush()


# ============================================================
# Accumulatore streaming async/bounded
# ============================================================

def start_accumulator(nmodes_local, nfreq, save_complex_mean=False):
    acc = {
        "n_events": 0,
        "meta": [],
        "sum_power": np.zeros((nmodes_local, nfreq), dtype=acc_dtype),
        "sum_real": None,
        "sum_imag": None,
    }

    if save_complex_mean:
        acc["sum_real"] = np.zeros((nmodes_local, nfreq), dtype=acc_dtype)
        acc["sum_imag"] = np.zeros((nmodes_local, nfreq), dtype=acc_dtype)

    return acc


def reset_accumulator(acc):
    acc["n_events"] = 0
    acc["meta"].clear()
    acc["sum_power"].fill(0.0)

    if acc["sum_real"] is not None:
        acc["sum_real"].fill(0.0)
        acc["sum_imag"].fill(0.0)


def submit_event_fft_jobs(
    futures,
    executor,
    frames_adc,
    window,
    coherent_gain,
):
    """
    Sottomette nmodes job FFT per l'evento corrente.
    La reference a frames_adc resta viva dentro i future finché i job non finiscono.
    """
    for mode_index, mode_name in enumerate(mode_names):
        ch_i, ch_q = iq_modes[mode_name]

        fut = executor.submit(
            complex_fft_power_job,
            frames_adc=frames_adc,
            mode_index=mode_index,
            mode_name=mode_name,
            ch_i=ch_i,
            ch_q=ch_q,
            scale=scale,
            iq_sign=iq_sign,
            window=window,
            coherent_gain=coherent_gain,
            save_complex_mean=args.save_complex_mean,
        )

        futures.add(fut)


def consume_future_result(fut, futures, acc):
    """
    Consuma un future FFT completato e accumula subito il risultato.
    """
    futures.remove(fut)

    res = fut.result()
    mi = res["mode_index"]

    acc["sum_power"][mi, :] += res["power"]

    if args.save_complex_mean:
        acc["sum_real"][mi, :] += res["real"]
        acc["sum_imag"][mi, :] += res["imag"]

    del res["power"]

    if res.get("real") is not None:
        del res["real"]

    if res.get("imag") is not None:
        del res["imag"]

    del res


def drain_completed_futures(futures, acc):
    """
    Consuma tutti i future già completati, senza bloccare.
    """
    done = [f for f in futures if f.done()]

    for fut in done:
        consume_future_result(fut, futures, acc)


def drain_until_below_limit(futures, acc, max_inflight_jobs):
    """
    Se ci sono troppi job in-flight, aspetta e consuma risultati
    fino a tornare sotto soglia.
    """
    while len(futures) >= max_inflight_jobs:
        fut = next(as_completed(futures))
        consume_future_result(fut, futures, acc)


def drain_all_futures(futures, acc):
    """
    Aspetta tutti i job pendenti del blocco corrente.
    Necessario prima di finalizzare un blocco.
    """
    while futures:
        fut = next(as_completed(futures))
        consume_future_result(fut, futures, acc)


def should_flush_by_events(acc):
    if args.avg_all:
        return False

    if args.avg_events is None:
        return False

    return acc["n_events"] >= args.avg_events


def should_flush_by_seconds(acc, new_time_for_grouping):
    if args.avg_all:
        return False

    if args.avg_seconds is None:
        return False

    if acc["n_events"] == 0:
        return False

    t0 = acc["meta"][0]["time_for_grouping"]
    return (new_time_for_grouping - t0) >= args.avg_seconds


def finalize_accumulator(acc, block_index, h5, freq, flush=False):
    """
    Scrive il blocco medio su HDF5 e resetta l'accumulatore.
    Chiamare solo dopo drain_all_futures().
    """
    if acc is None or acc["n_events"] == 0:
        return False

    n_avg = float(acc["n_events"])

    mean_power = (acc["sum_power"] / n_avg).astype(np.float32)

    if args.save_rms_amp:
        rms_amp = np.sqrt(mean_power).astype(np.float32)
    else:
        rms_amp = None

    if args.save_complex_mean:
        mean_real = (acc["sum_real"] / n_avg).astype(np.float32)
        mean_imag = (acc["sum_imag"] / n_avg).astype(np.float32)
    else:
        mean_real = None
        mean_imag = None

    peak_freq = np.zeros(nmodes, dtype=np.float64)
    peak_power = np.zeros(nmodes, dtype=np.float32)
    peak_rms_amp = np.zeros(nmodes, dtype=np.float32)
    peak_index = np.zeros(nmodes, dtype=np.int64)

    for mi in range(nmodes):
        pf, pp, pi = find_peak_excluding_dc(mean_power[mi, :], freq, guard_bins=2)
        peak_freq[mi] = pf
        peak_power[mi] = np.float32(pp)
        peak_rms_amp[mi] = np.float32(np.sqrt(pp))
        peak_index[mi] = int(pi)

    append_h5_average_block(
        h5=h5,
        block_index=block_index,
        meta=acc["meta"],
        mean_power=mean_power,
        peak_freq=peak_freq,
        peak_power=peak_power,
        peak_rms_amp=peak_rms_amp,
        peak_index=peak_index,
        rms_amp=rms_amp,
        mean_real=mean_real,
        mean_imag=mean_imag,
        flush=flush,
    )

    print(
        "Saved averaged block %d | n_events=%d | event %d -> %d"
        % (
            block_index,
            acc["n_events"],
            acc["meta"][0]["event_number"],
            acc["meta"][-1]["event_number"],
        )
    )

    del mean_power
    del peak_freq, peak_power, peak_rms_amp, peak_index

    if rms_amp is not None:
        del rms_amp

    if mean_real is not None:
        del mean_real

    if mean_imag is not None:
        del mean_imag

    reset_accumulator(acc)
    gc.collect()

    return True


# ============================================================
# MIDAS + ODB
# ============================================================

mf = midas.file_reader.MidasFile(full_name)

equipment_by_event_id = {}
run_description = ""

try:
    odb = mf.get_bor_odb_dump().data

    try:
        run_description = odb["Experiment"]["Run Parameters"]["Run description"]
        print("Run_description:", run_description)
    except Exception:
        print("WARNING: no run description")

    try:
        equipments = odb["Equipment"]

        for eq_name, eq_data in equipments.items():
            try:
                event_id = eq_data["Common"]["Event ID"]
                equipment_by_event_id[int(event_id)] = eq_name
                print("Found equipment:", eq_name, "Event ID:", event_id)
            except Exception:
                pass

    except Exception:
        print("WARNING: no Equipment section in ODB")

except Exception:
    print("WARNING: no BOR ODB dump found")
    odb = None


# ============================================================
# Main loop
# ============================================================

seen_equipments = set()

last_tgps_unix = -1
last_tgps_string = ""

n_spec_read = 0
n_blocks_saved = 0
block_index = 0

h5 = None
freq = None
window = None
coherent_gain = None
nsamp_ref = None
acc = None

futures = set()

executor = ThreadPoolExecutor(max_workers=args.workers)

try:
    for event in mf:

        if event.header.is_midas_internal_event():
            if verbose:
                print("Saw a special event")
            continue

        event_id = event.header.event_id
        equipment_name = equipment_by_event_id.get(event_id, "UNKNOWN")

        bank_names = ", ".join(b.name for b in event.banks.values())
        event_number = int(event.header.serial_number)
        event_timestamp = int(event.header.timestamp)

        if equipment_name not in seen_equipments:
            seen_equipments.add(equipment_name)

            event_time = datetime.fromtimestamp(event_timestamp).strftime("%Y-%m-%d %H:%M:%S")

            print("----------------------------------------")
            print("New equipment found")
            print("Equipment:", equipment_name)
            print("Event ID:", event_id)
            print("Event number:", event_number)
            print("Timestamp:", event_time)
            print("Banks:", bank_names)
            print("----------------------------------------")

        # --------------------------------------------------------
        # TGPS
        # --------------------------------------------------------
        if "TGPS" in event.banks:
            arr = event.banks["TGPS"].data

            try:
                stime = tgps_bank_to_string(arr)
                unix_time = tgps_bank_to_unix(arr)

                last_tgps_unix = int(unix_time)
                last_tgps_string = stime

                if verbose:
                    print("TGPS Time:", stime, unix_time)

            except Exception as e:
                print("WARNING: TGPS non parsabile:", e)

        # --------------------------------------------------------
        # SPEC
        # --------------------------------------------------------
        if "SPEC" in event.banks:

            if args.max_spec_events > 0 and n_spec_read >= args.max_spec_events:
                break

            # Copia esplicita sicura del bank SPEC.
            # La copia vive finché i future FFT che la usano non sono completati.
            u = np.array(event.banks["SPEC"].data, dtype=np.uint16, copy=True)
            s = u.view(np.int16)

            nsamp = s.size // Nch

            if nsamp <= 1:
                print("WARNING: evento SPEC troppo corto, salto")
                del u, s
                continue

            if nsamp_ref is None:
                nsamp_ref = int(nsamp)

                freq = np.fft.fftshift(
                    np.fft.fftfreq(nsamp_ref, d=1.0 / fs)
                ).astype(np.float32)

                if not args.no_window:
                    window = np.hanning(nsamp_ref).astype(np.float32)
                    coherent_gain = float(np.sum(window, dtype=np.float64))
                else:
                    window = None
                    coherent_gain = float(nsamp_ref)

                h5 = init_h5_file(
                    h5_name=h5_name,
                    args=args,
                    run=run,
                    run_description=run_description,
                    fs=fs,
                    nsamp=nsamp_ref,
                    freq=freq,
                    iq_modes=iq_modes,
                    input_range=input_range,
                    iq_sign=iq_sign,
                    use_window=not args.no_window,
                )

                acc = start_accumulator(
                    nmodes_local=nmodes,
                    nfreq=nsamp_ref,
                    save_complex_mean=args.save_complex_mean,
                )

                print("Opened HDF5:", h5_name)
                print("FFT nsamp:", nsamp_ref)
                print("FFT df:", fs / nsamp_ref, "Hz")

            if int(nsamp) != nsamp_ref:
                raise RuntimeError(
                    "Evento %d ha nsamp=%d diverso dal primo SPEC nsamp=%d. "
                    "Serve gestire dataset separati per lunghezze diverse."
                    % (event_number, nsamp, nsamp_ref)
                )

            frames_adc = s[:nsamp_ref * Nch].reshape(nsamp_ref, Nch)

            # ----------------------------------------------------
            # PPS
            # ----------------------------------------------------
            pps = frames_adc[:, pps_channel].astype(np.float32)
            pps *= scale

            pps_min = float(np.min(pps))
            pps_max = float(np.max(pps))

            start, length = lengths_above_threshold(pps, 2.5)
            pps_trigger = -1

            if len(length) > 0:
                good = np.where(length > 4000)[0]
                if len(good) > 0:
                    pps_trigger = int(start[int(good[0])])

            del pps

            # ----------------------------------------------------
            # Tempo per grouping
            # ----------------------------------------------------
            if last_tgps_unix > 0:
                time_for_grouping = float(last_tgps_unix)
            else:
                time_for_grouping = float(event_timestamp)

            # Se media per secondi, chiudi il blocco prima di aggiungere
            # l'evento che appartiene al blocco temporale successivo.
            if should_flush_by_seconds(acc, time_for_grouping):
                drain_all_futures(futures, acc)

                wrote = finalize_accumulator(
                    acc=acc,
                    block_index=block_index,
                    h5=h5,
                    freq=freq,
                    flush=((n_blocks_saved + 1) % args.flush_every == 0),
                )

                if wrote:
                    n_blocks_saved += 1
                    block_index += 1

            ev_meta = {
                "event_number": event_number,
                "midas_timestamp": event_timestamp,
                "tgps_unix": int(last_tgps_unix),
                "tgps_string": str(last_tgps_string),
                "pps_trigger": int(pps_trigger),
                "pps_min": float(pps_min),
                "pps_max": float(pps_max),
                "time_for_grouping": time_for_grouping,
            }

            # Conta evento nel blocco e salva solo metadata piccoli.
            acc["meta"].append(ev_meta)
            acc["n_events"] += 1
            n_spec_read += 1

            # Sottometti i job FFT dei modi. I future mantengono viva frames_adc.
            submit_event_fft_jobs(
                futures=futures,
                executor=executor,
                frames_adc=frames_adc,
                window=window,
                coherent_gain=coherent_gain,
            )

            # Libera i nomi locali. I dati restano vivi solo dentro i future.
            del frames_adc, u, s

            # Consuma subito tutto ciò che è già finito.
            drain_completed_futures(futures, acc)

            # Limita la memoria: se troppi job sono in-flight, aspetta alcuni risultati.
            drain_until_below_limit(
                futures=futures,
                acc=acc,
                max_inflight_jobs=args.max_inflight_jobs,
            )

            if verbose:
                print(
                    "Submitted SPEC event %d | block events %d | total SPEC %d | inflight jobs %d"
                    % (event_number, acc["n_events"], n_spec_read, len(futures))
                )

            # Se media per numero eventi, chiudi il blocco dopo avere aggiunto
            # l'evento corrente. Prima bisogna drenare tutti i future del blocco.
            if should_flush_by_events(acc):
                drain_all_futures(futures, acc)

                wrote = finalize_accumulator(
                    acc=acc,
                    block_index=block_index,
                    h5=h5,
                    freq=freq,
                    flush=((n_blocks_saved + 1) % args.flush_every == 0),
                )

                if wrote:
                    n_blocks_saved += 1
                    block_index += 1

            if n_spec_read % 20 == 0:
                gc.collect()

    # Fine file: scrivi ultimo blocco, incluso --avg-all.
    if acc is not None and acc["n_events"] > 0:
        drain_all_futures(futures, acc)

        wrote = finalize_accumulator(
            acc=acc,
            block_index=block_index,
            h5=h5,
            freq=freq,
            flush=True,
        )

        if wrote:
            n_blocks_saved += 1
            block_index += 1

finally:
    # Se un errore avviene prima del drain, proviamo a svuotare i future
    # solo se acc/h5 sono inizializzati. Se c'è già un'eccezione, fut.result()
    # può rilanciarla.
    executor.shutdown(wait=True)

    if h5 is not None:
        h5.flush()
        h5.close()
        print("Closed HDF5:", h5_name)
    else:
        print("WARNING: nessun evento SPEC salvato in HDF5")

print("DONE")
print("SPEC events read:", n_spec_read)
print("Blocks saved:", n_blocks_saved)