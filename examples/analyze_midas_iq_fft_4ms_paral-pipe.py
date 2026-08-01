import numpy as np
import midas.file_reader
from datetime import datetime
import os
import argparse
#from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import Pool
from itertools import islice
import matplotlib.pyplot as plt
# matplotlib.use("Agg")
import gc


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
    event_number,
    outdir,
    plot_points,
    use_window=True,
    ):
    """
    Costruisce z[n] = I[n] + j*iq_sign*Q[n],
    rimuove DC su I e Q, calcola FFT complessa e salva plot leggero.
    """
    fft_amp_chunks = None
    nstep = int(nsamp/number_chunks)

    #print(nsamp, number_chunks, nstep, nsamp/number_chunks)
    for nchunk in range(number_chunks):
    
        # Converti solo i due canali necessari
        I = frames[nchunk*nstep:(nchunk+1)*nstep-1, ch_i].astype(np.float32)
        Q = frames[nchunk*nstep:(nchunk+1)*nstep-1, ch_q].astype(np.float32)
    
        # Rimozione offset DC separata su I e Q
        I -= np.float32(np.mean(I, dtype=np.float64))
        Q -= np.float32(np.mean(Q, dtype=np.float64))
    
        # Segnale complesso baseband
        z = (I + 1j * iq_sign * Q).astype(np.complex64)
    
        # Libera I/Q, z contiene già tutto
        del I, Q
    
        # # Finestra
        if use_window:
            window = np.hanning(nstep-1).astype(np.float32)
            coherent_gain = np.sum(window, dtype=np.float64)
            #print(len(z), len(window))
            z *= window
            del window
        else:
            coherent_gain = float(nstep)

        # FFT complessa bidirezionale
        Z = np.fft.fft(z)
        del z
    
        Z = np.fft.fftshift(Z)
    
        freq = np.fft.fftshift(
            np.fft.fftfreq(nstep, d=1.0 / fs)
        ).astype(np.float32)
    
        # Ampiezza complessa normalizzata
        # Niente fattore 2, perché è una FFT complessa two-sided.
        fft_amp = ((np.abs(Z) / coherent_gain).astype(np.float32))**2 # da scommetare in caso di uso dell hanning window
        #fft_amp = (np.abs(Z)).astype(np.float32)
        
        # Non serve tenere Z se salviamo solo modulo/picco
        del Z
    
        # # Cerca picco evitando DC
        # dc_index = nstep // 2
        # fft_amp_for_peak = fft_amp.copy()

            
        if fft_amp_chunks is None:
            fft_amp_chunks = fft_amp
        else:
            fft_amp_chunks += fft_amp
            
        del fft_amp
        gc.collect()
        
    return fft_amp_chunks, [freq[0], freq[-1], len(freq)]

def event_payload_generator(mf):
    for event in mf:

        if event.header.is_midas_internal_event():
            continue
        if verbose:
            print(equipment_by_event_id.get(event.header.event_id, "UNKNOWN"))
        payload = {
            "event_number": event.header.serial_number,
            "event_id": event.header.event_id,
            "equipment_name" : equipment_by_event_id.get(event.header.event_id, "UNKNOWN"),
            "timestamp": event.header.timestamp,
            "banks": {
                name: np.asarray(bank.data).copy()
                for name, bank in event.banks.items()
            },
        }

        yield payload

def parallel_f(payload):

    results = {
        "event_number": payload["event_number"],
        "event_id" : payload["event_id"],
        "equipment_name" : payload["equipment_name"],
        "tdaq" : payload["timestamp"],
        "has_spec": False,
        "has_tgps": False,
        "fft": {},
        "tgps": None,
        "trigger": None,
        "error": False,
        "nsamp": None,
    }


    if results["event_number"] % 100 == 0:
        print("Event # %s | ID %s | equipment %s " %
              (results["event_number"], results["event_id"], results["equipment_name"]))

    # --------------------------------------------------------
    # Processa solo eventi SPEC
    # --------------------------------------------------------
    if "SPEC" in payload["banks"]:
        results["has_spec"] = True

            
        if verbose:
            print("----------------------------------------")
            print("Processing SPEC event:", results["event_number"])
    
        # Decode Spectrum digitizer
        u = np.asarray(payload["banks"]["SPEC"].data, dtype=np.uint16)
        s = u.view(np.int16) 
    
        nsamp = s.size // Nch
        results["nsamp"]=nsamp
    
        if nsamp <= 1:
            print("WARNING: evento SPEC troppo corto, salto")
            results["error"] = True
            return results
        #
        # Reshape solo della porzione usata
        # volt contine i canali ordinati di lunghezza nsamp (209ms)
        volt = s[:nsamp * Nch].reshape(nsamp, Nch) * scale 

        
 ##################################################################
        pps = volt[:, pps_channel].astype(np.float32)
        if verbose:
            print("PPS CH6 | min = %.6f V | max = %.6f V"
                % (np.min(pps), np.max(pps)))
        start, length=lengths_above_threshold(pps, 2.5) 

        if len(length)>0:
            tr_second = np.argmax(length > 4000)
            results["trigger"] = int(start[tr_second])
            if verbose:
                print(
                    "PPS >>> Trigger: %d PPS CH6 | min = %.6f V | max = %.6f V"
                    % (results["trigger"], np.min(pps), np.max(pps)))

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
                event_number=results["event_number"],
                outdir=outdir,
                plot_points=args.plot_points,
                use_window=not args.no_window,
            )

            results["fft"][ch] = {"amp":fft_amp_chunks, 
                                  "fs_meta":fs_meta }
            
            
        del volt, s, u
        gc.collect()
        
    if "TGPS" in payload["banks"]:
        results["has_tgps"] = True
        arr = payload["banks"]["TGPS"].data
        results["tgps"] = tgps_bank_to_unix(arr)
        
    return results


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

parser.add_argument("--fft-window-seconds", type=float, default=0,
                    help="Salva anche una FFT media per ogni finestra temporale di questa durata; 0 disabilita")

parser.add_argument("--no-window", action="store_true",
                    help="Disabilita finestra Hann")
parser.add_argument(
    "--mode-workers",
    type=int,
    default=8,
    help="Numero processi paralleli per i modi IQ. Default: uno per modo, limitato ai CPU disponibili"
)

parser.add_argument("--verbose", action="store_true", default=0,
                    help="Verbose output")

args = parser.parse_args()

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

verbose    = args.verbose

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

# try:
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





# ------------------------------------------------------------
# Loop eventi
# ------------------------------------------------------------
seen_equipments = set()
n_fft_done = 0
trigger    = -1 
triggerp   = -1 
stimep     = ""


input_range = float(args.input_range)
print(input_range)
scale = np.float32(2.0 * input_range / 65535)      # 2^16-1 =65535
iq_sign=args.iq_sign

Nch = 8
fs = args.fs
fft_amp_mode0_SPECs = None
fft_amp_mode1_SPECs = None
fft_amp_mode2_SPECs = None
MAX_WORKERS = 8
nsamp = None
pps_sample = {}
tgps = {}
window_index = 1
window_start = None
window_fft = [None, None, None]
window_n_fft_done = 0


def save_time_window(index, start, stop, amplitudes, count):
    if count <= 0:
        return

    out_window_npz = os.path.join(
        outdir,
        "run%05d_fft_%ds.npz" % (run, index),
    )

    normalization = number_chunks * count
    mean_amplitudes = [
        amplitude / normalization
        for amplitude in amplitudes
    ]

    np.savez_compressed(
        out_window_npz,
        fft_amp_mode0_SPECs=mean_amplitudes[0],
        fft_freq_mode0=fft_freq_mode0,
        fft_amp_mode1_SPECs=mean_amplitudes[1],
        fft_freq_mode1=fft_freq_mode1,
        fft_amp_mode2_SPECs=mean_amplitudes[2],
        fft_freq_mode2=fft_freq_mode2,
        n_fft_done=count,
        fs=fs,
        nsamp=nsamp,
        number_chunks=number_chunks,
        window_index=index,
        window_start= start,
        window_stop=stop,
        window_seconds=args.fft_window_seconds,
    )
    print(
        "Saved time-window summary:",
        out_window_npz,
        "(events:", count, ")",
    )


with Pool(processes=args.mode_workers) as pool:

    # L'ordine temporale è necessario per costruire finestre consecutive.
    iterator = (
        pool.imap(
            parallel_f,
            event_payload_generator(mf),
            chunksize=1,
        )
        if args.fft_window_seconds > 0
        else pool.imap_unordered(
            parallel_f,
            event_payload_generator(mf),
            chunksize=1,
        )
    )
    for results in iterator:
        if verbose:
            print(results)
        if (n_fft_done >= args.max_fft_events):
            break
        if results["has_spec"]:
            if fft_amp_mode0_SPECs is None:
                fft_amp_mode0_SPECs = results["fft"][0]["amp"]
                fft_freq_mode0 = results["fft"][0]["fs_meta"]
            else:
                fft_amp_mode0_SPECs += results["fft"][0]["amp"]
    
            if fft_amp_mode1_SPECs is None:
                fft_amp_mode1_SPECs = results["fft"][1]["amp"]
                fft_freq_mode1 = results["fft"][1]["fs_meta"]
            else:
                fft_amp_mode1_SPECs += results["fft"][1]["amp"]

            if fft_amp_mode2_SPECs is None:
                fft_amp_mode2_SPECs = results["fft"][2]["amp"]
                fft_freq_mode2 = results["fft"][2]["fs_meta"]
            else:
                fft_amp_mode2_SPECs += results["fft"][2]["amp"]

            n_fft_done += 1
            pps_sample[results["event_number"]] = results["trigger"]

            if args.fft_window_seconds > 0:
                event_time = float(results["tdaq"])
                if window_start is None:
                    window_start = event_time
                while (
                    window_n_fft_done > 0
                    and event_time
                    >= window_start + args.fft_window_seconds
                ):
                    save_time_window(
                        window_index,
                        window_start,
                        window_start + args.fft_window_seconds,
                        window_fft,
                        window_n_fft_done,
                    )
                    window_index += 1
                    window_start += args.fft_window_seconds
                    window_fft = [None, None, None]
                    window_n_fft_done = 0

                for mode in range(3):
                    amplitude = results["fft"][mode]["amp"]
                    if window_fft[mode] is None:
                        window_fft[mode] = amplitude.copy()
                    else:
                        window_fft[mode] += amplitude
                window_n_fft_done += 1



        if results["has_tgps"]:
            tgps[results["event_number"]] = results["tgps"]
            
        nsamp = results["nsamp"]
        del results


if args.fft_window_seconds > 0 and window_n_fft_done > 0:
    save_time_window(
        window_index,
        window_start,
        window_start + args.fft_window_seconds,
        window_fft,
        window_n_fft_done,
    )

                
    
        
#k=1000/(2*50) # tine conto dei 50 Home e posta tutto in mWatt. Senza questo salva in V^2
k=1

fft_amp_mode0_SPECs = fft_amp_mode0_SPECs*k/(number_chunks*n_fft_done)
fft_amp_mode1_SPECs = fft_amp_mode1_SPECs*k/(number_chunks*n_fft_done)
fft_amp_mode2_SPECs = fft_amp_mode2_SPECs*k/(number_chunks*n_fft_done)

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

)
if verbose:
    print("Saved summary:", out_npz)
        
print("DONE")
