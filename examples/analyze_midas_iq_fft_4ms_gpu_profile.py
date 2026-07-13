#!/usr/bin/env python3
import argparse
import csv
import gc
import json
import os
import re
import time
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

import numpy as np

# CuPy viene usato solo se --fft-backend gpu/auto lo richiede.
try:
    import cupy as cp
except ImportError:
    cp = None

import midas.file_reader


# ============================================================
# Utility logging / profiling
# ============================================================

def log(msg: str = ""):
    print(msg, flush=True)


def human_bytes(n):
    if n is None:
        return "n/a"
    n = float(n)
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if abs(n) < 1024.0:
            return f"{n:.2f} {unit}"
        n /= 1024.0
    return f"{n:.2f} PiB"


class Profiler:
    """
    Profiler leggero a sezioni.

    Note importanti per GPU:
    - Le chiamate CUDA sono spesso asincrone.
    - Per misurare davvero il tempo GPU bisogna sincronizzare prima/dopo
      la regione cronometrata.
    - Questo profiler sincronizza solo dove viene richiesto sync=True.
    """

    def __init__(self, enabled=False, sync_fn=None):
        self.enabled = bool(enabled)
        self.sync_fn = sync_fn or (lambda: None)
        self.times = defaultdict(float)
        self.counts = defaultdict(int)
        self.t0_wall = time.perf_counter()
        self.t0_cpu = time.process_time()

    @contextmanager
    def section(self, name: str, sync: bool = False):
        if not self.enabled:
            yield
            return

        if sync:
            self.sync_fn()

        t0 = time.perf_counter()
        try:
            yield
        finally:
            if sync:
                self.sync_fn()
            dt = time.perf_counter() - t0
            self.times[name] += dt
            self.counts[name] += 1

    def add(self, name: str, dt: float):
        if not self.enabled:
            return
        self.times[name] += float(dt)
        self.counts[name] += 1

    def wall_total(self):
        return time.perf_counter() - self.t0_wall

    def cpu_total(self):
        return time.process_time() - self.t0_cpu

    def snapshot(self, n_fft_done: int):
        wall = self.wall_total()
        cpu = self.cpu_total()
        rows = []

        for name, seconds in sorted(self.times.items(), key=lambda kv: kv[1], reverse=True):
            count = self.counts.get(name, 0)
            rows.append({
                "section": name,
                "seconds": seconds,
                "count": count,
                "seconds_per_call": seconds / count if count else 0.0,
                "seconds_per_SPEC": seconds / n_fft_done if n_fft_done else 0.0,
                "percent_wall": 100.0 * seconds / wall if wall > 0 else 0.0,
            })

        return {
            "wall_total_seconds": wall,
            "cpu_process_seconds": cpu,
            "cpu_process_over_wall": cpu / wall if wall > 0 else 0.0,
            "n_fft_done": n_fft_done,
            "rows": rows,
        }

    def print_summary(self, n_fft_done: int, title: str = "TIMING SUMMARY"):
        if not self.enabled:
            return

        snap = self.snapshot(n_fft_done)
        wall = snap["wall_total_seconds"]
        cpu = snap["cpu_process_seconds"]

        log("")
        log(f"========== {title} ==========")
        log(f"wall_total_seconds      : {wall:.3f}")
        log(f"cpu_process_seconds     : {cpu:.3f}")
        log(f"cpu_process/wall        : {snap['cpu_process_over_wall']:.3f}")
        log(f"n_fft_done              : {n_fft_done}")
        log("")
        log(f"{'section':34s} {'seconds':>12s} {'count':>10s} {'s/call':>12s} {'s/SPEC':>12s} {'%wall':>9s}")
        log("-" * 96)

        for r in snap["rows"]:
            log(
                f"{r['section']:34s} "
                f"{r['seconds']:12.3f} "
                f"{r['count']:10d} "
                f"{r['seconds_per_call']:12.6f} "
                f"{r['seconds_per_SPEC']:12.6f} "
                f"{r['percent_wall']:8.2f}%"
            )

        log("=" * 96)
        log("")

    def write_csv(self, path: str, n_fft_done: int):
        if not self.enabled:
            return

        snap = self.snapshot(n_fft_done)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "section",
                    "seconds",
                    "count",
                    "seconds_per_call",
                    "seconds_per_SPEC",
                    "percent_wall",
                    "wall_total_seconds",
                    "cpu_process_seconds",
                    "cpu_process_over_wall",
                    "n_fft_done",
                ],
            )
            writer.writeheader()

            for r in snap["rows"]:
                row = dict(r)
                row["wall_total_seconds"] = snap["wall_total_seconds"]
                row["cpu_process_seconds"] = snap["cpu_process_seconds"]
                row["cpu_process_over_wall"] = snap["cpu_process_over_wall"]
                row["n_fft_done"] = snap["n_fft_done"]
                writer.writerow(row)

    def write_json(self, path: str, n_fft_done: int, extra=None):
        if not self.enabled:
            return

        snap = self.snapshot(n_fft_done)
        if extra is not None:
            snap["extra"] = extra

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

        with open(path, "w") as f:
            json.dump(snap, f, indent=2)


# ============================================================
# Parametri da riga di comando
# ============================================================

parser = argparse.ArgumentParser(
    description="Legge un file MIDAS e calcola FFT complessa I/Q dei modi TM, con profiling I/O/CPU/GPU."
)

parser.add_argument("--path", required=True,
                    help="Directory contenente i file MIDAS, es: ~/flash-data/data/LNF/")

parser.add_argument("--run", required=True, type=int,
                    help="Numero run, es: 123")

parser.add_argument("--out-dir", default="./",
                    help="Directory dove salvare le FFT")

parser.add_argument("--max-fft-events", type=int, default=999999999,
                    help="Numero massimo di eventi SPEC da processare")

parser.add_argument("--fs", type=float, default=5e6,
                    help="Sampling frequency [Hz]")

parser.add_argument("--input-range", type=float, default=5.0,
                    help="Input range ADC in Volt, es. 5 per +/-5 V")

parser.add_argument("--iq-sign", type=int, default=+1, choices=[+1, -1],
                    help="Convenzione I/Q: +1 usa I + jQ, -1 usa I - jQ")

parser.add_argument("--plot-points", type=int, default=50000,
                    help="Numero massimo di punti da plottare nella FFT")

parser.add_argument("--number-chunks", type=int, default=64,
                    help="Numero di suddivisioni del chunk acquisito 209ms/nchunk. Deve essere una potenza di 2")

parser.add_argument("--no-window", action="store_true",
                    help="Disabilita finestra Hann")

parser.add_argument("--mode-workers", type=int, default=0,
                    help="Parametro mantenuto per compatibilità; in questa versione non usa multiprocessing")

parser.add_argument("--verbose", action="store_true", default=False,
                    help="Verbose output")

parser.add_argument("--fft-backend", choices=["auto", "cpu", "gpu"], default="auto",
                    help="Backend FFT: auto usa CuPy se disponibile, gpu richiede CuPy/CUDA, cpu usa NumPy")

parser.add_argument("--gpu-device", type=int, default=0,
                    help="Indice GPU CUDA da usare con CuPy")

# ----------------------------
# Profiling / diagnostica
# ----------------------------
parser.add_argument("--profile", action="store_true",
                    help="Abilita profiling interno con timer per I/O, decode, PPS, CPU->GPU, FFT, GPU->CPU, save")

parser.add_argument("--profile-every", type=int, default=100,
                    help="Stampa un summary parziale ogni N eventi SPEC. 0 disabilita i summary parziali")

parser.add_argument("--profile-csv", default=None,
                    help="Path CSV dove salvare il profiling finale. Default: <out-dir>/profile_runXXXXX.csv")

parser.add_argument("--profile-json", default=None,
                    help="Path JSON dove salvare il profiling finale. Default: <out-dir>/profile_runXXXXX.json")

parser.add_argument("--gc-every", type=int, default=0,
                    help="Esegue gc.collect() ogni N eventi SPEC. 0 = disabilitato. Per riprodurre vecchio comportamento usa 1")

parser.add_argument("--free-gpu-pool-every", type=int, default=0,
                    help="Libera memory pool CuPy ogni N eventi SPEC. 0 = mai nel loop; consigliato per performance")

args = parser.parse_args()

log("Python profiling-enabled script")
log("Parsed arguments:")
for k, v in sorted(vars(args).items()):
    log(f"  {k}: {v}")


# ============================================================
# Backend FFT
# ============================================================

def configure_fft_backend(requested_backend: str, gpu_device: int):
    """Seleziona NumPy o CuPy per la FFT."""
    if requested_backend == "cpu":
        return np, "cpu"

    if cp is None:
        if requested_backend == "gpu":
            raise RuntimeError("--fft-backend gpu richiesto, ma CuPy non è installato")
        log("CuPy non disponibile: uso FFT CPU/NumPy")
        return np, "cpu"

    try:
        cp.cuda.Device(gpu_device).use()
        _ = cp.asarray([0], dtype=cp.float32).sum().item()
        log(f"Uso FFT GPU/CuPy su device CUDA {gpu_device}")
        log(f"CuPy version: {cp.__version__}")
        log(f"CUDA device count: {cp.cuda.runtime.getDeviceCount()}")
        log(f"CUDA runtime version: {cp.cuda.runtime.runtimeGetVersion()}")
        log(f"CUDA driver version: {cp.cuda.runtime.driverGetVersion()}")
        return cp, "gpu"
    except Exception as exc:
        if requested_backend == "gpu":
            raise RuntimeError(f"Impossibile inizializzare CuPy/CUDA sul device {gpu_device}") from exc
        log(f"CuPy presente ma GPU non inizializzabile ({exc}); uso FFT CPU/NumPy")
        return np, "cpu"


xp, fft_backend = configure_fft_backend(args.fft_backend, args.gpu_device)


def sync_gpu():
    if fft_backend == "gpu":
        cp.cuda.Stream.null.synchronize()


def gpu_snapshot():
    if fft_backend != "gpu":
        return {}

    sync_gpu()

    free_mem, total_mem = cp.cuda.runtime.memGetInfo()
    mem_pool = cp.get_default_memory_pool()
    pinned_pool = cp.get_default_pinned_memory_pool()

    return {
        "gpu_mem_free_bytes": int(free_mem),
        "gpu_mem_total_bytes": int(total_mem),
        "cupy_pool_used_bytes": int(mem_pool.used_bytes()),
        "cupy_pool_total_bytes": int(mem_pool.total_bytes()),
        "cupy_pinned_free_blocks": int(pinned_pool.n_free_blocks()),
    }


prof = Profiler(enabled=args.profile, sync_fn=sync_gpu)


# ============================================================
# Setup path / file
# ============================================================

outdir = os.path.expanduser(args.out_dir)
os.makedirs(outdir, exist_ok=True)

number_chunks = args.number_chunks
run = args.run
path = os.path.expanduser(args.path)

fname = "run%05d.mid.gz" % run
full_name = os.path.join(path, fname)

profile_csv = args.profile_csv or os.path.join(outdir, f"profile_run{run:05d}.csv")
profile_json = args.profile_json or os.path.join(outdir, f"profile_run{run:05d}.json")

log(f"Reading: {full_name}")
log(f"Output dir: {outdir}")
log(f"Profile CSV: {profile_csv}")
log(f"Profile JSON: {profile_json}")

if args.profile and fft_backend == "gpu":
    snap = gpu_snapshot()
    log("Initial GPU memory:")
    log(f"  GPU free/total: {human_bytes(snap['gpu_mem_free_bytes'])} / {human_bytes(snap['gpu_mem_total_bytes'])}")
    log(f"  CuPy pool used/total: {human_bytes(snap['cupy_pool_used_bytes'])} / {human_bytes(snap['cupy_pool_total_bytes'])}")


with prof.section("midas_open_file"):
    mf = midas.file_reader.MidasFile(full_name)


# ============================================================
# Leggi ODB BOR e ricostruisci Event ID -> Equipment name
# ============================================================

equipment_by_event_id = {}

with prof.section("midas_get_bor_odb_dump"):
    odb = mf.get_bor_odb_dump().data

try:
    with prof.section("parse_bor_odb_dump"):
        run_description = odb["Experiment"]["Run Parameters"]["Run description"]
        log(f"Run_description: {run_description}")
        equipments = odb["Equipment"]
        for eq_name, eq_data in equipments.items():
            event_id = eq_data["Common"]["Event ID"]
            equipment_by_event_id[int(event_id, 16)] = eq_name
            log(f"Found equipment: {eq_name} Event ID: {event_id}")
except Exception:
    log("WARNING: no BOR ODB dump found")
    odb = None


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
    """Converte l'array ASCII del bank MIDAS TGPS in stringa."""
    return ''.join(chr(int(x)) for x in arr if x != 0)


def tgps_string_to_unix(stime):
    """Estrae data/ora/timezone dalla stringa TGPS e restituisce Unix time."""
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
# Definizione coppie I/Q
# ============================================================

iq_modes = {
    "TM010": (0, 1, 0),
    "TM011": (2, 3, 1),
    "TM012": (4, 5, 2),
}

pps_channel = 6

if args.mode_workers > 0:
    mode_workers = args.mode_workers
else:
    mode_workers = min(len(iq_modes.items()), os.cpu_count() or 1)

log(f"Mode workers parameter: {mode_workers}")
log(f"fft_backend: {fft_backend}")


# ============================================================
# Cerca segnali sopra soglia
# ============================================================

def lengths_above_threshold(x: np.ndarray, threshold: float) -> np.ndarray:
    if x.ndim != 1:
        raise ValueError("L'array deve essere 1D")

    above = x > threshold
    if not np.any(above):
        return np.array([], dtype=int), np.array([], dtype=int)

    d = np.diff(above.astype(np.int8))

    starts = np.where(d == 1)[0] + 1
    ends = np.where(d == -1)[0] + 1

    if above[0]:
        starts = np.r_[0, starts]
    if above[-1]:
        ends = np.r_[ends, len(x)]

    lengths = ends - starts
    return starts, lengths


# ============================================================
# FFT complessa con profiling fine CPU/GPU
# ============================================================

def complex_fft_chunks(
    frames,
    mode_name,
    ch_i,
    ch_q,
    fs,
    nsamp,
    input_range,
    iq_sign,
    run,
    event_number,
    outdir,
    plot_points,
    use_window=True,
    xp=np,
):
    """
    Costruisce z[n] = I[n] + j*iq_sign*Q[n], rimuove DC su I e Q,
    calcola FFT complessa sui chunk e somma |FFT|^2.

    Profiling interno:
      - fft.freq_cpu
      - fft.h2d_or_array_select
      - fft.dc_remove
      - fft.build_complex
      - fft.window
      - fft.fft
      - fft.fftshift
      - fft.power_reduce
      - fft.d2h_result

    Per GPU le sezioni principali sono sincronizzate per evitare timing
    falsamente piccoli dovuti all'asincronia CUDA.
    """

    if number_chunks <= 0:
        raise ValueError("number_chunks deve essere > 0")

    nstep = nsamp // number_chunks
    if nstep <= 1:
        raise ValueError(f"Chunk troppo corto: nsamp={nsamp}, number_chunks={number_chunks}")

    nuse = nstep * number_chunks
    nfft = nstep
    is_gpu = (xp is cp)

    with prof.section(f"fft.{mode_name}.freq_cpu"):
        freq = np.fft.fftshift(np.fft.fftfreq(nfft, d=1.0 / fs)).astype(np.float32)

    with prof.section(f"fft.{mode_name}.h2d_or_array_select", sync=is_gpu):
        I = xp.asarray(frames[:nuse, ch_i], dtype=xp.float32).reshape(number_chunks, nstep)
        Q = xp.asarray(frames[:nuse, ch_q], dtype=xp.float32).reshape(number_chunks, nstep)

    with prof.section(f"fft.{mode_name}.dc_remove", sync=is_gpu):
        I = I - xp.mean(I, axis=1, keepdims=True, dtype=xp.float64).astype(xp.float32)
        Q = Q - xp.mean(Q, axis=1, keepdims=True, dtype=xp.float64).astype(xp.float32)

    with prof.section(f"fft.{mode_name}.build_complex", sync=is_gpu):
        z = (I + (1j * iq_sign) * Q).astype(xp.complex64)
        del I, Q

    if use_window:
        with prof.section(f"fft.{mode_name}.window", sync=is_gpu):
            window = xp.hanning(nfft).astype(xp.float32)
            if is_gpu:
                coherent_gain = float(xp.sum(window, dtype=xp.float64).get())
            else:
                coherent_gain = float(xp.sum(window, dtype=xp.float64))
            z *= window[None, :]
            del window
    else:
        coherent_gain = float(nfft)

    with prof.section(f"fft.{mode_name}.fft", sync=is_gpu):
        Z = xp.fft.fft(z, axis=1)
        del z

    with prof.section(f"fft.{mode_name}.fftshift", sync=is_gpu):
        Z = xp.fft.fftshift(Z, axes=1)

    with prof.section(f"fft.{mode_name}.power_reduce", sync=is_gpu):
        fft_amp_chunks = xp.sum((xp.abs(Z) / coherent_gain).astype(xp.float32) ** 2, axis=0).astype(xp.float32)
        del Z

    if is_gpu:
        with prof.section(f"fft.{mode_name}.d2h_result", sync=True):
            fft_amp_chunks = cp.asnumpy(fft_amp_chunks)

        # Non liberare la memory pool qui: è una grossa sorgente di overhead.
        # Se serve per debug memoria, usa --free-gpu-pool-every N nel loop eventi.
    else:
        # Per simmetria di profiling.
        with prof.section(f"fft.{mode_name}.d2h_result"):
            pass

    return fft_amp_chunks, [float(freq[0]), float(freq[-1]), int(len(freq))]


# ============================================================
# Loop eventi
# ============================================================

seen_equipments = set()
n_fft_done = 0
trigger = -1
triggerp = -1
stimep = ""
verbose = args.verbose

input_range = float(args.input_range)
log(f"input_range: {input_range}")

scale = np.float32(2.0 * input_range / 65535)      # 2^16-1 =65535
iq_sign = args.iq_sign

Nch = 8
fs = args.fs

fft_amp_mode0_SPECs = None
fft_amp_mode1_SPECs = None
fft_amp_mode2_SPECs = None
fft_freq_mode0 = None
fft_freq_mode1 = None
fft_freq_mode2 = None
nsamp = None
event_number = None

log("Starting event loop")

mf_iter = iter(mf)

while True:
    # Misura il tempo speso nel reader MIDAS, inclusi I/O/decompressione/parsing
    # associati all'avanzamento dell'iteratore.
    with prof.section("midas_next_event"):
        try:
            event = next(mf_iter)
        except StopIteration:
            break

    with prof.section("event_header_and_banknames"):
        if event.header.is_midas_internal_event():
            log("Saw a special event")
            continue

        event_id = event.header.event_id
        equipment_name = equipment_by_event_id.get(event_id, "UNKNOWN")

        bank_names = ", ".join(b.name for b in event.banks.values())
        event_number = event.header.serial_number
        event_timestamp = event.header.timestamp
        event_time = datetime.fromtimestamp(event_timestamp).strftime("%Y-%m-%d %H:%M:%S")

    if equipment_name not in seen_equipments:
        seen_equipments.add(equipment_name)

        log("----------------------------------------")
        log("New equipment found")
        log(f"Equipment: {equipment_name}")
        log(f"Event ID: {event_id}")
        log(f"Event number: {event_number}")
        log(f"Timestamp: {event_time}")
        log(f"Banks: {bank_names}")
        log("----------------------------------------")

    if event_number % 100 == 0:
        log("Event # %s | ID %s | equipment %s | banks %s" %
            (event_number, event_id, equipment_name, bank_names))

    # --------------------------------------------------------
    # Processa solo eventi SPEC
    # --------------------------------------------------------
    if "SPEC" in event.banks:

        if n_fft_done >= args.max_fft_events:
            break

        with prof.section("SPEC_event_total"):

            if verbose:
                log("----------------------------------------")
                log(f"Processing SPEC event: {event_number}")

            # Decode Spectrum digitizer
            with prof.section("SPEC_decode_numpy"):
                u = np.asarray(event.banks["SPEC"].data, dtype=np.uint16)
                s = u.view(np.int16)
                nsamp = s.size // Nch

                if nsamp <= 1:
                    log("WARNING: evento SPEC troppo corto, salto")
                    continue

                # volt contiene i canali ordinati di lunghezza nsamp.
                # Questa moltiplicazione è CPU/NumPy.
                volt = s[:nsamp * Nch].reshape(nsamp, Nch) * scale

            # PPS
            with prof.section("SPEC_pps_threshold"):
                pps = volt[:, pps_channel].astype(np.float32)

                if verbose:
                    log(
                        "PPS CH6 | min = %.6f V | max = %.6f V"
                        % (np.min(pps), np.max(pps))
                    )

                start, length = lengths_above_threshold(pps, 2.5)

                if len(length) > 0:
                    tr_second = np.argmax(length > 4000)
                    trigger = start[tr_second]

                    if verbose:
                        log(
                            "PPS >>> Trigger: %d PPS CH6 | min = %.6f V | max = %.6f V"
                            % (trigger, np.min(pps), np.max(pps))
                        )

                del pps

            # FFT dei tre modi
            with prof.section("SPEC_fft_all_modes_total", sync=(fft_backend == "gpu")):
                for mode_name, (ch_i, ch_q, ch) in iq_modes.items():

                    fft_amp_chunks, fs_meta = complex_fft_chunks(
                        frames=volt,
                        mode_name=mode_name,
                        ch_i=ch_i,
                        ch_q=ch_q,
                        fs=fs,
                        nsamp=nsamp,
                        input_range=input_range,
                        iq_sign=args.iq_sign,
                        run=run,
                        event_number=event_number,
                        outdir=outdir,
                        plot_points=args.plot_points,
                        use_window=not args.no_window,
                        xp=xp,
                    )

                    with prof.section(f"accumulate.{mode_name}"):
                        if ch == 0:
                            if fft_amp_mode0_SPECs is None:
                                fft_amp_mode0_SPECs = fft_amp_chunks
                                fft_freq_mode0 = fs_meta
                            else:
                                fft_amp_mode0_SPECs += fft_amp_chunks
                        elif ch == 1:
                            if fft_amp_mode1_SPECs is None:
                                fft_amp_mode1_SPECs = fft_amp_chunks
                                fft_freq_mode1 = fs_meta
                            else:
                                fft_amp_mode1_SPECs += fft_amp_chunks
                        else:
                            if fft_amp_mode2_SPECs is None:
                                fft_amp_mode2_SPECs = fft_amp_chunks
                                fft_freq_mode2 = fs_meta
                            else:
                                fft_amp_mode2_SPECs += fft_amp_chunks

            n_fft_done += 1

            with prof.section("SPEC_cleanup_python"):
                del volt, s, u

            if args.gc_every > 0 and n_fft_done % args.gc_every == 0:
                with prof.section("gc_collect_forced"):
                    gc.collect()

            if fft_backend == "gpu" and args.free_gpu_pool_every > 0 and n_fft_done % args.free_gpu_pool_every == 0:
                with prof.section("cupy_free_memory_pools", sync=True):
                    cp.get_default_memory_pool().free_all_blocks()
                    cp.get_default_pinned_memory_pool().free_all_blocks()

            if args.profile and args.profile_every > 0 and n_fft_done % args.profile_every == 0:
                prof.print_summary(n_fft_done, title=f"TIMING SUMMARY after {n_fft_done} SPEC events")

                if fft_backend == "gpu":
                    snap = gpu_snapshot()
                    log("GPU memory snapshot:")
                    log(f"  GPU free/total: {human_bytes(snap['gpu_mem_free_bytes'])} / {human_bytes(snap['gpu_mem_total_bytes'])}")
                    log(f"  CuPy pool used/total: {human_bytes(snap['cupy_pool_used_bytes'])} / {human_bytes(snap['cupy_pool_total_bytes'])}")
                    log(f"  CuPy pinned free blocks: {snap['cupy_pinned_free_blocks']}")

    # --------------------------------------------------------
    # TGPS
    # --------------------------------------------------------
    if "TGPS" in event.banks:
        with prof.section("TGPS_parse"):
            arr = event.banks["TGPS"].data
            stime = ''.join(chr(x) for x in arr if x != 0)
            if stimep == "":
                stimep = stime
            unix_time = tgps_bank_to_unix(arr)
            log("TGPS Time: %s, %d, %d" % (stimep, trigger, unix_time))
            stimep = stime


# ============================================================
# Normalizzazione e output
# ============================================================

with prof.section("normalization"):
    #k = 1000 / (2 * 50)  # tiene conto dei 50 Ohm e porta tutto in mWatt. Senza questo salva in V^2

    if n_fft_done > 0:
        norm = k / (number_chunks * n_fft_done)
        fft_amp_mode0_SPECs = fft_amp_mode0_SPECs * norm
        fft_amp_mode1_SPECs = fft_amp_mode1_SPECs * norm
        fft_amp_mode2_SPECs = fft_amp_mode2_SPECs * norm
    else:
        raise RuntimeError("Nessun evento SPEC processato: non posso salvare FFT mediate")

log(f"Last event_number: {event_number}")
log(f"n_fft_done: {n_fft_done}")
log(f"fft_backend: {fft_backend}")

out_npz = os.path.join(outdir, "run%05d.npz" % run)

with prof.section("save_npz_compressed"):
    np.savez_compressed(
        out_npz,
        fft_amp_mode0_SPECs=fft_amp_mode0_SPECs,
        fft_freq_mode0=fft_freq_mode0,
        fft_amp_mode1_SPECs=fft_amp_mode1_SPECs,
        fft_freq_mode1=fft_freq_mode1,
        fft_amp_mode2_SPECs=fft_amp_mode2_SPECs,
        fft_freq_mode2=fft_freq_mode2,
        n_fft_done=n_fft_done,
        fs=fs,
        nsamp=nsamp,
        number_chunks=number_chunks,
        fft_backend=fft_backend,
        profile_csv=profile_csv if args.profile else "",
        profile_json=profile_json if args.profile else "",
    )

log(f"Saved summary: {out_npz}")

if fft_backend == "gpu":
    with prof.section("final_gpu_sync", sync=True):
        pass

    if args.profile:
        snap = gpu_snapshot()
        log("Final GPU memory:")
        log(f"  GPU free/total: {human_bytes(snap['gpu_mem_free_bytes'])} / {human_bytes(snap['gpu_mem_total_bytes'])}")
        log(f"  CuPy pool used/total: {human_bytes(snap['cupy_pool_used_bytes'])} / {human_bytes(snap['cupy_pool_total_bytes'])}")
        log(f"  CuPy pinned free blocks: {snap['cupy_pinned_free_blocks']}")

if args.profile:
    extra = {
        "run": run,
        "input_file": full_name,
        "out_npz": out_npz,
        "fft_backend": fft_backend,
        "number_chunks": number_chunks,
        "fs": fs,
        "input_range": input_range,
        "max_fft_events": args.max_fft_events,
        "gc_every": args.gc_every,
        "free_gpu_pool_every": args.free_gpu_pool_every,
    }

    if fft_backend == "gpu":
        extra["gpu_snapshot_final"] = gpu_snapshot()

    prof.print_summary(n_fft_done, title="FINAL TIMING SUMMARY")
    prof.write_csv(profile_csv, n_fft_done)
    prof.write_json(profile_json, n_fft_done, extra=extra)

    log(f"Profile CSV saved: {profile_csv}")
    log(f"Profile JSON saved: {profile_json}")

log("DONE")
