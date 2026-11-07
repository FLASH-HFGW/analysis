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
    description="Legge un file MIDAS e calcola FFT complessa I/Q full-resolution dei modi TM."
)

parser.add_argument(
    "--path",
    required=True,
    help="Directory contenente i file MIDAS, es: ~/flash-data/data/LNF/"
)

parser.add_argument(
    "--run",
    required=True,
    type=int,
    help="Numero run, es: 123"
)

parser.add_argument(
    "--fs",
    type=float,
    default=5e6,
    help="Sampling frequency [Hz]. Default: 5e6"
)

parser.add_argument(
    "--input-range",
    type=float,
    default=5.0,
    help="Input range ADC in Volt, es. 5 per +/-5 V. Default: 5"
)

parser.add_argument(
    "--iq-sign",
    type=int,
    default=+1,
    choices=[+1, -1],
    help="Convenzione I/Q: +1 usa I + jQ, -1 usa I - jQ. Default: +1"
)

parser.add_argument(
    "--max-fft-events",
    type=int,
    default=0,
    help="Numero massimo di eventi SPEC da processare. Default: 0 = tutti."
)

# ----------------------------
# Output HDF5
# ----------------------------

parser.add_argument(
    "--h5-out",
    default="/home/mazzitel/HFGW/analysis-work/Run2/staging/examples/h5",
    help="Directory dove salvare il file HDF5 (default sotto Run2/examples/h5)"
)

parser.add_argument(
    "--h5-name",
    default=None,
    help="Nome file HDF5 di output. Default: runXXXXX_fft_summary.h5"
)

parser.add_argument(
    "--h5-compression",
    default="lzf",
    choices=["lzf", "gzip", "none"],
    help="Compressione HDF5. Default: lzf"
)

parser.add_argument(
    "--h5-gzip-level",
    type=int,
    default=1,
    help="Livello gzip HDF5, usato solo con --h5-compression gzip. Default: 1"
)

parser.add_argument(
    "--h5-chunk-freq",
    type=int,
    default=262144,
    help="Numero di bin di frequenza per chunk HDF5. Non cambia la risoluzione."
)

parser.add_argument(
    "--flush-every",
    type=int,
    default=10,
    help="Flush del file HDF5 ogni N eventi SPEC salvati. Default: 10"
)

# ----------------------------
# Cosa salvare
# ----------------------------

parser.add_argument(
    "--save-phase",
    action="store_true",
    help="Salva anche la fase della FFT complessa in radianti."
)

parser.add_argument(
    "--save-real-imag",
    action="store_true",
    help="Salva anche parte reale e immaginaria normalizzate della FFT complessa."
)

# ----------------------------
# FFT
# ----------------------------

parser.add_argument(
    "--no-window",
    action="store_true",
    help="Disabilita finestra Hann. Default: Hann abilitata."
)

# ----------------------------
# Parallelismo sui modi
# ----------------------------

parser.add_argument(
    "--mode-workers",
    type=int,
    default=0,
    help="Numero worker paralleli per i modi IQ. Default: 0 = uno per modo, limitato ai CPU."
)

# ----------------------------
# Plot diagnostici opzionali
# ----------------------------

parser.add_argument(
    "--make-plots",
    action="store_true",
    help="Genera anche plot diagnostici. Default: disabilitato."
)

parser.add_argument(
    "--plot-points",
    type=int,
    default=50000,
    help="Numero massimo di punti nei plot diagnostici. Non cambia i dati HDF5."
)

parser.add_argument(
    "--fft-out",
    default="/home/mazzitel/HFGW/analysis-work/Run2/staging/examples/fft_plots",
    help="Directory dove salvare eventuali plot se --make-plots è attivo."
)

parser.add_argument(
    "--verbose",
    action="store_true",
    help="Verbose output"
)

args = parser.parse_args()


# ============================================================
# Validazione argomenti
# ============================================================

if args.max_fft_events < 0:
    raise ValueError("--max-fft-events deve essere >= 0. Usa 0 per tutti gli eventi.")

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


# ============================================================
# Configurazione base
# ============================================================

run = args.run
path = os.path.expanduser(args.path)
fs = float(args.fs)
input_range = float(args.input_range)
iq_sign = int(args.iq_sign)
verbose = bool(args.verbose)

Nch = 8
pps_channel = 6

scale = np.float32(2.0 * input_range / 65536.0)

fname = "run%05d.mid.gz" % run
full_name = os.path.join(path, fname)

h5_out = os.path.expanduser(args.h5_out)
os.makedirs(h5_out, exist_ok=True)

if args.h5_name is None:
    h5_name = os.path.join(h5_out, "run%05d_fft_summary.h5" % run)
else:
    h5_name = os.path.expanduser(args.h5_name)
    if not os.path.isabs(h5_name):
        h5_name = os.path.join(h5_out, h5_name)

os.makedirs(os.path.dirname(os.path.abspath(h5_name)), exist_ok=True)

if args.make_plots:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fft_out = os.path.expanduser(args.fft_out)
    os.makedirs(fft_out, exist_ok=True)
else:
    plt = None
    fft_out = None


# ============================================================
# Modi I/Q
# ============================================================

iq_modes = {
    "TM010": (0, 1),
    "TM011": (2, 3),
    "TM012": (3, 5),
}

mode_names = list(iq_modes.keys())
nmodes = len(mode_names)

if args.mode_workers > 0:
    mode_workers = args.mode_workers
else:
    mode_workers = min(nmodes, os.cpu_count() or 1)

print("Reading:", full_name)
print("Output HDF5:", h5_name)
print("Mode workers:", mode_workers)
print("Save phase:", args.save_phase)
print("Save real/imag:", args.save_real_imag)
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
    """
    Converte array ASCII MIDAS TGPS in stringa.
    Rimuove null bytes.
    """
    return ''.join(chr(int(x)) for x in arr if int(x) != 0)


def tgps_string_to_unix(stime):
    """
    Estrae data/ora/timezone dalla stringa TGPS e restituisce Unix time.

    Esempio:
      '2026-05-27 15:03:17 CET  32214700000020260527140361187 ...'
    """
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
    """
    Restituisce start e lunghezze dei segmenti consecutivi con x > threshold.
    """
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

def find_peak_excluding_dc(fft_amp, freq, guard_bins=2):
    """
    Trova il picco escludendo alcuni bin attorno alla DC.
    Non fa copie grandi dell'array.
    """
    nsamp = len(fft_amp)
    dc_index = nsamp // 2

    i0 = max(0, dc_index - guard_bins)
    i1 = min(nsamp, dc_index + guard_bins + 1)

    best_idx = None
    best_amp = -np.inf

    if i0 > 0:
        il = int(np.argmax(fft_amp[:i0]))
        al = float(fft_amp[il])
        if al > best_amp:
            best_amp = al
            best_idx = il

    if i1 < nsamp:
        ir_rel = int(np.argmax(fft_amp[i1:]))
        ir = i1 + ir_rel
        ar = float(fft_amp[ir])
        if ar > best_amp:
            best_amp = ar
            best_idx = ir

    if best_idx is None:
        best_idx = int(np.argmax(fft_amp))
        best_amp = float(fft_amp[best_idx])

    return float(freq[best_idx]), best_amp, int(best_idx)


def complex_fft_result(
    frames_adc,
    mode_index,
    mode_name,
    ch_i,
    ch_q,
    fs,
    scale,
    iq_sign,
    freq,
    window,
    coherent_gain,
    save_phase=False,
    save_real_imag=False,
):
    """
    Calcola FFT complessa I/Q per un modo.

    frames_adc:
      array int16 shape [nsamp, Nch]

    Ritorna:
      dict con ampiezza, picco, ed eventuale fase/reale/immaginario.
    """
    nsamp = frames_adc.shape[0]

    # Converti in Volt solo i due canali necessari.
    I = frames_adc[:, ch_i].astype(np.float32)
    Q = frames_adc[:, ch_q].astype(np.float32)

    I *= scale
    Q *= scale

    # Rimozione offset DC separata su I e Q.
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

    norm = float(coherent_gain)

    fft_amp = (np.abs(Z) / norm).astype(np.float32)

    fft_phase = None
    fft_real = None
    fft_imag = None

    if save_phase:
        fft_phase = np.angle(Z).astype(np.float32)

    if save_real_imag:
        fft_real = (Z.real / norm).astype(np.float32)
        fft_imag = (Z.imag / norm).astype(np.float32)

    del Z

    peak_freq, peak_amp, peak_index = find_peak_excluding_dc(
        fft_amp=fft_amp,
        freq=freq,
        guard_bins=2
    )

    return {
        "mode_index": int(mode_index),
        "mode_name": mode_name,
        "peak_freq": float(peak_freq),
        "peak_amp": float(peak_amp),
        "peak_index": int(peak_index),
        "fft_amp": fft_amp,
        "fft_phase": fft_phase,
        "fft_real": fft_real,
        "fft_imag": fft_imag,
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
    n_channels,
):
    """
    Crea file HDF5 estendibile.
    """
    mode_names_local = list(iq_modes.keys())
    nmodes_local = len(mode_names_local)
    nfreq = len(freq)

    comp = h5_compression_kwargs(args)

    h5 = h5py.File(h5_name, "w")

    # ----------------------------
    # Attributi globali
    # ----------------------------

    h5.attrs["run"] = int(run)
    h5.attrs["run_description"] = str(run_description) if run_description is not None else ""
    h5.attrs["fs"] = float(fs)
    h5.attrs["nsamp"] = int(nsamp)
    h5.attrs["df"] = float(fs / nsamp)
    h5.attrs["input_range"] = float(input_range)
    h5.attrs["iq_sign"] = int(iq_sign)
    h5.attrs["use_window"] = bool(use_window)
    h5.attrs["n_channels"] = int(n_channels)
    h5.attrs["pps_channel"] = int(pps_channel)
    h5.attrs["save_phase"] = bool(args.save_phase)
    h5.attrs["save_real_imag"] = bool(args.save_real_imag)
    h5.attrs["fft_type"] = "complex_two_sided_fftshift"
    h5.attrs["amplitude_normalization"] = "abs(FFT)/coherent_gain"
    h5.attrs["description"] = "Complex I/Q full FFT summary, one HDF5 file per run"

    # ----------------------------
    # Info modi
    # ----------------------------

    str_dtype = h5py.string_dtype(encoding="utf-8")

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

    # ----------------------------
    # Asse frequenze
    # ----------------------------

    h5.create_dataset(
        "fft_freq",
        data=freq.astype(np.float32),
        **comp,
    )

    # ----------------------------
    # Metadata evento
    # ----------------------------

    h5.create_dataset(
        "event_number",
        shape=(0,),
        maxshape=(None,),
        chunks=(1024,),
        dtype=np.int64,
    )

    h5.create_dataset(
        "midas_timestamp",
        shape=(0,),
        maxshape=(None,),
        chunks=(1024,),
        dtype=np.int64,
    )

    h5.create_dataset(
        "pps_trigger",
        shape=(0,),
        maxshape=(None,),
        chunks=(1024,),
        dtype=np.int64,
    )

    h5.create_dataset(
        "pps_min",
        shape=(0,),
        maxshape=(None,),
        chunks=(1024,),
        dtype=np.float32,
    )

    h5.create_dataset(
        "pps_max",
        shape=(0,),
        maxshape=(None,),
        chunks=(1024,),
        dtype=np.float32,
    )

    h5.create_dataset(
        "tgps_unix",
        shape=(0,),
        maxshape=(None,),
        chunks=(1024,),
        dtype=np.int64,
    )

    h5.create_dataset(
        "tgps_string",
        shape=(0,),
        maxshape=(None,),
        chunks=(1024,),
        dtype=str_dtype,
    )

    # ----------------------------
    # Picchi
    # ----------------------------

    h5.create_dataset(
        "peak_freq",
        shape=(0, nmodes_local),
        maxshape=(None, nmodes_local),
        chunks=(1024, nmodes_local),
        dtype=np.float64,
        **comp,
    )

    h5.create_dataset(
        "peak_amp",
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

    # ----------------------------
    # FFT full
    # ----------------------------

    chunk_freq = min(int(args.h5_chunk_freq), nfreq)

    fft_amp = h5.create_dataset(
        "fft_amp",
        shape=(0, nmodes_local, nfreq),
        maxshape=(None, nmodes_local, nfreq),
        chunks=(1, 1, chunk_freq),
        dtype=np.float32,
        **comp,
    )

    # # Alias HDF5 per retro-compatibilità concettuale con il vecchio nome "sa".
    # # Nel vecchio npz: sa = fft_amp.
    # h5["sa"] = fft_amp

    if args.save_phase:
        h5.create_dataset(
            "fft_phase",
            shape=(0, nmodes_local, nfreq),
            maxshape=(None, nmodes_local, nfreq),
            chunks=(1, 1, chunk_freq),
            dtype=np.float32,
            **comp,
        )

    if args.save_real_imag:
        h5.create_dataset(
            "fft_real",
            shape=(0, nmodes_local, nfreq),
            maxshape=(None, nmodes_local, nfreq),
            chunks=(1, 1, chunk_freq),
            dtype=np.float32,
            **comp,
        )

        h5.create_dataset(
            "fft_imag",
            shape=(0, nmodes_local, nfreq),
            maxshape=(None, nmodes_local, nfreq),
            chunks=(1, 1, chunk_freq),
            dtype=np.float32,
            **comp,
        )

    return h5


def append_h5_event(
    h5,
    event_number,
    midas_timestamp,
    pps_trigger,
    pps_min,
    pps_max,
    tgps_unix,
    tgps_string,
    peak_freqs,
    peak_amps,
    peak_indices,
    fft_amps,
    fft_phases=None,
    fft_reals=None,
    fft_imags=None,
    flush=False,
):
    """
    Aggiunge un evento SPEC al file HDF5.
    """
    i = h5["event_number"].shape[0]

    nmodes_local = h5["fft_amp"].shape[1]
    nfreq = h5["fft_amp"].shape[2]

    # Resize metadata
    for name in [
        "event_number",
        "midas_timestamp",
        "pps_trigger",
        "pps_min",
        "pps_max",
        "tgps_unix",
        "tgps_string",
    ]:
        h5[name].resize((i + 1,))

    # Resize array per modo
    for name in ["peak_freq", "peak_amp", "peak_index"]:
        h5[name].resize((i + 1, nmodes_local))

    h5["fft_amp"].resize((i + 1, nmodes_local, nfreq))

    if "fft_phase" in h5:
        h5["fft_phase"].resize((i + 1, nmodes_local, nfreq))

    if "fft_real" in h5:
        h5["fft_real"].resize((i + 1, nmodes_local, nfreq))

    if "fft_imag" in h5:
        h5["fft_imag"].resize((i + 1, nmodes_local, nfreq))

    # Scrittura metadata
    h5["event_number"][i] = int(event_number)
    h5["midas_timestamp"][i] = int(midas_timestamp)
    h5["pps_trigger"][i] = int(pps_trigger)
    h5["pps_min"][i] = np.float32(pps_min)
    h5["pps_max"][i] = np.float32(pps_max)
    h5["tgps_unix"][i] = int(tgps_unix)
    h5["tgps_string"][i] = str(tgps_string)

    h5["peak_freq"][i, :] = peak_freqs
    h5["peak_amp"][i, :] = peak_amps
    h5["peak_index"][i, :] = peak_indices

    # Scrittura FFT
    h5["fft_amp"][i, :, :] = fft_amps

    if "fft_phase" in h5:
        if fft_phases is None:
            raise RuntimeError("Dataset fft_phase presente ma fft_phases=None")
        h5["fft_phase"][i, :, :] = fft_phases

    if "fft_real" in h5:
        if fft_reals is None:
            raise RuntimeError("Dataset fft_real presente ma fft_reals=None")
        h5["fft_real"][i, :, :] = fft_reals

    if "fft_imag" in h5:
        if fft_imags is None:
            raise RuntimeError("Dataset fft_imag presente ma fft_imags=None")
        h5["fft_imag"][i, :, :] = fft_imags

    if flush:
        h5.flush()


# ============================================================
# Plot opzionale
# ============================================================

def save_diagnostic_plot(freq, amp, run, event_number, mode_name, outdir, plot_points):
    if plt is None:
        return

    nsamp = len(freq)

    if nsamp > plot_points:
        idx = np.linspace(0, nsamp - 1, plot_points).astype(np.int64)
    else:
        idx = np.arange(nsamp, dtype=np.int64)

    fig, ax = plt.subplots(1, 1, figsize=(10, 5))

    ax.plot(freq[idx], amp[idx])
    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylabel("|FFT| [V]")
    ax.set_title(
        "%s complex FFT - run %05d event %08d"
        % (mode_name, run, event_number)
    )
    ax.grid(True)
    ax.set_yscale("log")

    fig.tight_layout()

    out_png = os.path.join(
        outdir,
        "run%05d_event%08d_%s_complex_fft.png"
        % (run, event_number, mode_name)
    )

    fig.savefig(out_png, dpi=150)
    plt.close(fig)


# ============================================================
# Leggi MIDAS + ODB
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
n_fft_done = 0

last_tgps_unix = -1
last_tgps_string = ""

h5 = None

executor = ThreadPoolExecutor(max_workers=mode_workers)

try:
    for event in mf:

        if event.header.is_midas_internal_event():
            if verbose:
                print("Saw a special event")
            continue

        event_id = event.header.event_id
        equipment_name = equipment_by_event_id.get(event_id, "UNKNOWN")

        bank_names = ", ".join(b.name for b in event.banks.values())
        event_number = event.header.serial_number
        event_timestamp = event.header.timestamp
        event_time = datetime.fromtimestamp(event_timestamp).strftime("%Y-%m-%d %H:%M:%S")

        if equipment_name not in seen_equipments:
            seen_equipments.add(equipment_name)

            print("----------------------------------------")
            print("New equipment found")
            print("Equipment:", equipment_name)
            print("Event ID:", event_id)
            print("Event number:", event_number)
            print("Timestamp:", event_time)
            print("Banks:", bank_names)
            print("----------------------------------------")

        if verbose and event_number % 100 == 0:
            print(
                "Event # %s | ID %s | equipment %s | banks %s"
                % (event_number, event_id, equipment_name, bank_names)
            )

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

            if args.max_fft_events > 0 and n_fft_done >= args.max_fft_events:
                break

            if verbose:
                print("----------------------------------------")
                print("Processing SPEC event:", event_number)

            # Decode Spectrum digitizer.
            # Teniamo int16 per evitare di creare una matrice Volt enorme.
            u = np.asarray(event.banks["SPEC"].data, dtype=np.uint16)
            s = u.view(np.int16)

            nsamp = s.size // Nch

            if nsamp <= 1:
                print("WARNING: evento SPEC troppo corto, salto")
                continue

            frames_adc = s[:nsamp * Nch].reshape(nsamp, Nch)

            # ----------------------------------------------------
            # PPS sul canale 6
            # ----------------------------------------------------
            pps = frames_adc[:, pps_channel].astype(np.float32)
            pps *= scale

            pps_min = float(np.min(pps))
            pps_max = float(np.max(pps))

            start, length = lengths_above_threshold(pps, 2.5)

            trigger = -1

            if len(length) > 0:
                good = np.where(length > 4000)[0]

                if len(good) > 0:
                    tr_second = int(good[0])
                    trigger = int(start[tr_second])

            if verbose:
                print("PPS CH6 | min = %.6f V | max = %.6f V" % (pps_min, pps_max))
                print("PPS trigger sample:", trigger)

            del pps

            # ----------------------------------------------------
            # Frequenza e finestra full-resolution
            # ----------------------------------------------------
            freq = np.fft.fftshift(
                np.fft.fftfreq(nsamp, d=1.0 / fs)
            ).astype(np.float32)

            if not args.no_window:
                window = np.hanning(nsamp).astype(np.float32)
                coherent_gain = float(np.sum(window, dtype=np.float64))
            else:
                window = None
                coherent_gain = float(nsamp)

            # ----------------------------------------------------
            # Inizializza HDF5 al primo SPEC
            # ----------------------------------------------------
            if h5 is None:
                h5 = init_h5_file(
                    h5_name=h5_name,
                    args=args,
                    run=run,
                    run_description=run_description,
                    fs=fs,
                    nsamp=nsamp,
                    freq=freq,
                    iq_modes=iq_modes,
                    input_range=input_range,
                    iq_sign=iq_sign,
                    use_window=not args.no_window,
                    n_channels=Nch,
                )

                print("Opened HDF5:", h5_name)
                print("FFT nsamp:", nsamp)
                print("FFT df:", fs / nsamp, "Hz")

            # Per un singolo dataset HDF5 3D, nsamp deve rimanere costante.
            if nsamp != int(h5.attrs["nsamp"]):
                raise RuntimeError(
                    "Evento %d ha nsamp=%d diverso dal primo SPEC nsamp=%d. "
                    "Serve gestire gruppi HDF5 separati per lunghezze diverse."
                    % (event_number, nsamp, int(h5.attrs["nsamp"]))
                )

            # ----------------------------------------------------
            # FFT dei modi, in parallelo sui modi
            # ----------------------------------------------------
            nfreq = nsamp

            peak_freqs = np.zeros(nmodes, dtype=np.float64)
            peak_amps = np.zeros(nmodes, dtype=np.float32)
            peak_indices = np.zeros(nmodes, dtype=np.int64)

            fft_amps = np.empty((nmodes, nfreq), dtype=np.float32)

            if args.save_phase:
                fft_phases = np.empty((nmodes, nfreq), dtype=np.float32)
            else:
                fft_phases = None

            if args.save_real_imag:
                fft_reals = np.empty((nmodes, nfreq), dtype=np.float32)
                fft_imags = np.empty((nmodes, nfreq), dtype=np.float32)
            else:
                fft_reals = None
                fft_imags = None

            futures = []

            for mode_index, mode_name in enumerate(mode_names):
                ch_i, ch_q = iq_modes[mode_name]

                fut = executor.submit(
                    complex_fft_result,
                    frames_adc=frames_adc,
                    mode_index=mode_index,
                    mode_name=mode_name,
                    ch_i=ch_i,
                    ch_q=ch_q,
                    fs=fs,
                    scale=scale,
                    iq_sign=iq_sign,
                    freq=freq,
                    window=window,
                    coherent_gain=coherent_gain,
                    save_phase=args.save_phase,
                    save_real_imag=args.save_real_imag,
                )

                futures.append(fut)

            for fut in as_completed(futures):
                res = fut.result()

                mi = res["mode_index"]
                mn = res["mode_name"]

                peak_freqs[mi] = res["peak_freq"]
                peak_amps[mi] = res["peak_amp"]
                peak_indices[mi] = res["peak_index"]

                fft_amps[mi, :] = res["fft_amp"]

                if args.save_phase:
                    fft_phases[mi, :] = res["fft_phase"]

                if args.save_real_imag:
                    fft_reals[mi, :] = res["fft_real"]
                    fft_imags[mi, :] = res["fft_imag"]

                if verbose:
                    print(
                        "%s | event = %s | peak freq = %.6f Hz | peak amp = %.6e V"
                        % (mn, event_number, res["peak_freq"], res["peak_amp"])
                    )

                if args.make_plots:
                    save_diagnostic_plot(
                        freq=freq,
                        amp=res["fft_amp"],
                        run=run,
                        event_number=event_number,
                        mode_name=mn,
                        outdir=fft_out,
                        plot_points=args.plot_points,
                    )

                # Libera il risultato pesante appena copiato.
                del res

            # ----------------------------------------------------
            # Scrittura HDF5 una sola volta per evento
            # ----------------------------------------------------
            append_h5_event(
                h5=h5,
                event_number=event_number,
                midas_timestamp=event_timestamp,
                pps_trigger=trigger,
                pps_min=pps_min,
                pps_max=pps_max,
                tgps_unix=last_tgps_unix,
                tgps_string=last_tgps_string,
                peak_freqs=peak_freqs,
                peak_amps=peak_amps,
                peak_indices=peak_indices,
                fft_amps=fft_amps,
                fft_phases=fft_phases,
                fft_reals=fft_reals,
                fft_imags=fft_imags,
                flush=((n_fft_done + 1) % args.flush_every == 0),
            )

            n_fft_done += 1

            print(
                "Saved SPEC event %d to HDF5 | count %d"
                % (event_number, n_fft_done)
            )

            del u, s, frames_adc
            del freq, window
            del peak_freqs, peak_amps, peak_indices
            del fft_amps, fft_phases, fft_reals, fft_imags

            # Non farlo a ogni evento se vuoi massima velocità.
            # Lo teniamo leggero: ogni 10 eventi.
            if n_fft_done % 10 == 0:
                gc.collect()

finally:
    executor.shutdown(wait=True)

    if h5 is not None:
        h5.flush()
        h5.close()
        print("Closed HDF5:", h5_name)
    else:
        print("WARNING: nessun evento SPEC salvato in HDF5")

print("DONE")