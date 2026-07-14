import numpy as np

# CuPy viene usato solo se --fft-backend gpu/auto lo richiede.
try:
    import cupy as cp
except ImportError:
    cp = None
import midas.file_reader
from datetime import datetime
import os
import argparse
# from concurrent.futures import ProcessPoolExecutor, as_completed
# import matplotlib.pyplot as plt
# matplotlib.use("Agg")
import gc


# ------------------------------------------------------------
# Parametri da riga di comando
# ------------------------------------------------------------
parser = argparse.ArgumentParser(
    description="Legge un file MIDAS e calcola solo FFT complessa I/Q dei modi TM."
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
                    help="Numero di suddivisione del chunk acquisito 209ms/nchunk = ms su cui fare FFT. Deve essere una potenza di 2")

parser.add_argument("--no-window", action="store_true",
                    help="Disabilita finestra Hann")
parser.add_argument(
    "--mode-workers",
    type=int,
    default=0,
    help="Numero processi paralleli per i modi IQ. Default: uno per modo, limitato ai CPU disponibili"
)

parser.add_argument("--verbose", action="store_true", default=0,
                    help="Verbose output")

parser.add_argument("--fft-backend", choices=["auto", "cpu", "gpu"], default="auto",
                    help="Backend FFT: auto usa CuPy se disponibile, gpu richiede CuPy/CUDA, cpu usa NumPy")

parser.add_argument("--gpu-device", type=int, default=0,
                    help="Indice GPU CUDA da usare con CuPy")

args = parser.parse_args()


def configure_fft_backend(requested_backend: str, gpu_device: int):
    """Seleziona NumPy o CuPy per la FFT."""
    if requested_backend == "cpu":
        return np, "cpu"

    if cp is None:
        if requested_backend == "gpu":
            raise RuntimeError("--fft-backend gpu richiesto, ma CuPy non è installato")
        print("CuPy non disponibile: uso FFT CPU/NumPy")
        return np, "cpu"

    try:
        cp.cuda.Device(gpu_device).use()
        # Forza una piccola operazione per intercettare subito problemi CUDA/driver.
        _ = cp.asarray([0], dtype=cp.float32).sum().item()
        print(f"Uso FFT GPU/CuPy su device CUDA {gpu_device}")
        return cp, "gpu"
    except Exception as exc:
        if requested_backend == "gpu":
            raise RuntimeError(f"Impossibile inizializzare CuPy/CUDA sul device {gpu_device}") from exc
        print(f"CuPy presente ma GPU non inizializzabile ({exc}); uso FFT CPU/NumPy")
        return np, "cpu"


xp, fft_backend = configure_fft_backend(args.fft_backend, args.gpu_device)


outdir = args.out_dir
fft_out = os.path.expanduser(outdir)
os.makedirs(fft_out, exist_ok=True)

number_chunks = args.number_chunks


run = args.run
path = os.path.expanduser(args.path)

fname = "run%05d.mid.gz" % run
full_name = os.path.join(path, fname)

print("Reading:", full_name)

mf = midas.file_reader.MidasFile(full_name)

# ------------------------------------------------------------
# Leggi ODB BOR e ricostruisci Event ID -> Equipment name
# ------------------------------------------------------------
equipment_by_event_id = {}

odb = mf.get_bor_odb_dump().data

try:
    run_description = odb["Experiment"]["Run Parameters"]["Run description"]
    print("Run_description:", run_description)
    equipments = odb["Equipment"]
    for eq_name, eq_data in equipments.items():
        event_id = eq_data["Common"]["Event ID"]
        equipment_by_event_id[int(event_id, 16)] = eq_name
        print("Found equipment:", eq_name, "Event ID:", event_id)
except Exception:
    print("WARNING: no BOR ODB dump found")
    odb = None

import re
from datetime import datetime, timezone, timedelta


TZ_OFFSETS = {
    "UTC": 0,
    "GMT": 0,
    "CET": 1,    # UTC+1
    "CEST": 2,   # UTC+2
}


def tgps_bank_to_string(arr):
    """
    Converte l'array ASCII del bank MIDAS TGPS in stringa.
    Rimuove gli zeri finali/null bytes.
    """
    return ''.join(chr(int(x)) for x in arr if x != 0)


def tgps_string_to_unix(stime):
    """
    Estrae data, ora, minuto, secondo e timezone dalla stringa TGPS
    e restituisce il tempo Unix in secondi.

    Esempio stringa:
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
    """
    Funzione completa: prende direttamente event.banks['TGPS'].data
    e restituisce il timestamp Unix.
    """
    stime = tgps_bank_to_string(arr)
    return tgps_string_to_unix(stime)


# ------------------------------------------------------------
# Definizione coppie I/Q
# ------------------------------------------------------------
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

print("Mode workers:", mode_workers)



# ------------------------------------------------------------
# Cerca segnali sopra soglia
# ------------------------------------------------------------
def lengths_above_threshold(x: np.ndarray, threshold: float) -> np.ndarray:

    if x.ndim != 1:
        raise ValueError("L'array deve essere 1D")

    above = x > threshold
    if not np.any(above):
        return np.array([], dtype=int), np.array([], dtype=int)

    d = np.diff(above.astype(np.int8))

    starts = np.where(d == 1)[0] + 1
    ends   = np.where(d == -1)[0] + 1

    # Gestione bordi
    if above[0]:
        starts = np.r_[0, starts]
    if above[-1]:
        ends = np.r_[ends, len(x)]

    lengths = ends - starts

    return starts, lengths

# ------------------------------------------------------------
# FFT complessa leggera
# ------------------------------------------------------------
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

    Se xp è cupy, tutta la parte FFT resta su GPU e viene riportato su CPU
    solo il vettore finale fft_amp_chunks, così np.savez_compressed resta invariato.
    """
    if number_chunks <= 0:
        raise ValueError("number_chunks deve essere > 0")

    nstep = nsamp // number_chunks
    if nstep <= 1:
        raise ValueError(f"Chunk troppo corto: nsamp={nsamp}, number_chunks={number_chunks}")

    # Usa solo un numero intero di chunk. L'eventuale resto finale viene ignorato.
    nuse = nstep * number_chunks
    nfft = nstep

    # Frequenze sempre su CPU: sono piccole e servono solo come metadato/output.
    freq = np.fft.fftshift(np.fft.fftfreq(nfft, d=1.0 / fs)).astype(np.float32)

    # Trasferisce/organizza in blocco i soli canali I/Q del modo corrente.
    # Shape: (number_chunks, nstep)
    I = xp.asarray(frames[:nuse, ch_i], dtype=xp.float32).reshape(number_chunks, nstep)
    Q = xp.asarray(frames[:nuse, ch_q], dtype=xp.float32).reshape(number_chunks, nstep)

    # Rimozione DC per chunk, separata su I e Q.
    I = I - xp.mean(I, axis=1, keepdims=True, dtype=xp.float64).astype(xp.float32)
    Q = Q - xp.mean(Q, axis=1, keepdims=True, dtype=xp.float64).astype(xp.float32)

    z = (I + (1j * iq_sign) * Q).astype(xp.complex64)
    del I, Q

    if use_window:
        window = xp.hanning(nfft).astype(xp.float32)
        coherent_gain = float(xp.sum(window, dtype=xp.float64).get() if xp is cp else xp.sum(window, dtype=xp.float64))
        z *= window[None, :]
        del window
    else:
        coherent_gain = float(nfft)

    # FFT complessa two-sided su tutti i chunk in parallelo.
    Z = xp.fft.fft(z, axis=1)
    del z
    Z = xp.fft.fftshift(Z, axes=1)

    # Somma sui chunk: equivalente al loop precedente, ma vettorializzato.
    fft_amp_chunks = xp.sum((xp.abs(Z) / coherent_gain).astype(xp.float32) ** 2, axis=0).astype(xp.float32)
    del Z

    # np.savez_compressed vuole array NumPy; copiamo solo il risultato finale.
    if xp is cp:
        fft_amp_chunks = cp.asnumpy(fft_amp_chunks)
        cp.get_default_memory_pool().free_all_blocks()
        cp.get_default_pinned_memory_pool().free_all_blocks()

    return fft_amp_chunks, [float(freq[0]), float(freq[-1]), int(len(freq))]





# ------------------------------------------------------------
# Loop eventi
# ------------------------------------------------------------
seen_equipments = set()
n_fft_done = 0
trigger    = -1 
triggerp   = -1 
stimep     = ""
verbose    = args.verbose

input_range = float(args.input_range)
print(input_range)
scale = np.float32(2.0 * input_range / 65535)      # 2^16-1 =65535
iq_sign=args.iq_sign

Nch = 8
fs = args.fs
fft_amp_mode0_SPECs = None
fft_amp_mode1_SPECs = None
fft_amp_mode2_SPECs = None

#executor = ProcessPoolExecutor(max_workers=mode_workers)

# try: 
for event in mf:

    if event.header.is_midas_internal_event():
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

    if event_number % 100 == 0:
        print("Event # %s | ID %s | equipment %s | banks %s" %
              (event_number, event_id, equipment_name, bank_names))

    # --------------------------------------------------------
    # Processa solo eventi SPEC
    # --------------------------------------------------------
    if "SPEC" in event.banks:
    
        if n_fft_done >= args.max_fft_events:
            break

        if verbose:
            print("----------------------------------------")
            print("Processing SPEC event:", event_number)
    
        # Decode Spectrum digitizer
        u = np.asarray(event.banks["SPEC"].data, dtype=np.uint16)
        s = u.view(np.int16) 
    
        nsamp = s.size // Nch
    
        if nsamp <= 1:
            print("WARNING: evento SPEC troppo corto, salto")
            continue
        #
        # Reshape solo della porzione usata
        # volt contine i canali ordinati di lunghezza nsamp (209ms)
        volt = s[:nsamp * Nch].reshape(nsamp, Nch) * scale 

        
##################################################################
        pps = volt[:, pps_channel].astype(np.float32)
        if verbose:
            print(
                "PPS CH6 | min = %.6f V | max = %.6f V"
                % (np.min(pps), np.max(pps)))
        start, length=lengths_above_threshold(pps, 2.5) 
        # print(start, length)
        if len(length)>0:
            tr_second = np.argmax(length > 4000)
            trigger = start[tr_second]
            if verbose:
                print(
                    "PPS >>> Trigger: %d PPS CH6 | min = %.6f V | max = %.6f V"
                    % (trigger, np.min(pps), np.max(pps)))

        del pps
####################################################################    
        # FFT dei tre modi
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
            
        del volt, s, u
        gc.collect()
        
    if "TGPS" in event.banks:
        arr = event.banks["TGPS"].data
        stime = ''.join(chr(x) for x in arr if x != 0)
        if stimep =="":
            stimep=stime
        unix_time = tgps_bank_to_unix(arr)
        print("TGPS Time: %s, %d, %d" % (stimep, trigger, unix_time))
        stimep=stime
        
#k=1000/(2*50) # tine conto dei 50 Home e posta tutto in mWatt. Senza questo salva in V^2
k =1
 
if n_fft_done > 0:
    norm = k / (number_chunks * n_fft_done)
    fft_amp_mode0_SPECs = fft_amp_mode0_SPECs * norm
    fft_amp_mode1_SPECs = fft_amp_mode1_SPECs * norm
    fft_amp_mode2_SPECs = fft_amp_mode2_SPECs * norm
else:
    raise RuntimeError("Nessun evento SPEC processato: non posso salvare FFT mediate")

print(event_number, n_fft_done)

# finally:
#     executor.shutdown(wait=True)


# Summary leggero
out_npz = os.path.join(
    outdir,
    "run%05d.npz"
    % (run)
)

np.savez_compressed(out_npz,
    fft_amp_mode0_SPECs=fft_amp_mode0_SPECs,
    fft_freq_mode0=fft_freq_mode0,
    fft_amp_mode1_SPECs=fft_amp_mode1_SPECs,
    fft_freq_mode1=fft_freq_mode1,
    fft_amp_mode2_SPECs=fft_amp_mode2_SPECs,
    fft_freq_mode2=fft_freq_mode2,
    n_fft_done = n_fft_done,
    fs=fs,
    nsamp=nsamp,
    number_chunks=number_chunks,
    fft_backend=fft_backend,

)
if verbose:
    print("Saved summary:", out_npz)
    
print("DONE")
