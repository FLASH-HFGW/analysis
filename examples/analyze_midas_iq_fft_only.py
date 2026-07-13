import numpy as np
import midas.file_reader
from datetime import datetime
import os
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import matplotlib.pyplot as plt
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

parser.add_argument("--fft-out", default="fft_plots",
                    help="Directory dove salvare i plot FFT")

parser.add_argument("--max-fft-events", type=int, default=1,
                    help="Numero massimo di eventi SPEC da processare")

parser.add_argument("--fs", type=float, default=5e6,
                    help="Sampling frequency [Hz]")

parser.add_argument("--input-range", type=float, default=5.0,
                    help="Input range ADC in Volt, es. 5 per +/-5 V")

parser.add_argument("--iq-sign", type=int, default=+1, choices=[+1, -1],
                    help="Convenzione I/Q: +1 usa I + jQ, -1 usa I - jQ")

parser.add_argument("--plot-points", type=int, default=50000,
                    help="Numero massimo di punti da plottare nella FFT")

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

args = parser.parse_args()


fft_out = os.path.expanduser(args.fft_out)
os.makedirs(fft_out, exist_ok=True)

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
    "TM010": (0, 1),
    "TM011": (2, 3),
    "TM012": (3, 5),
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
def complex_fft_only(
    frames,
    mode_name,
    ch_i,
    ch_q,
    fs,
    input_range,
    iq_sign,
    run,
    event_number,
    outdir,
    plot_points,
    use_window=True,
):
    """
    Costruisce z[n] = I[n] + j*iq_sign*Q[n],
    rimuove DC su I e Q, calcola FFT complessa e salva plot leggero.
    """

    nsamp = frames.shape[0]

    # Converti solo i due canali necessari
    I = frames[:, ch_i].astype(np.float32)
    Q = frames[:, ch_q].astype(np.float32)

    # Rimozione offset DC separata su I e Q
    I -= np.float32(np.mean(I, dtype=np.float64))
    Q -= np.float32(np.mean(Q, dtype=np.float64))

    # Segnale complesso baseband
    z = (I + 1j * iq_sign * Q).astype(np.complex64)

    # Libera I/Q, z contiene già tutto
    del I, Q

    # Finestra
    if use_window:
        window = np.hanning(nsamp).astype(np.float32)
        coherent_gain = np.sum(window, dtype=np.float64)
        z *= window
        del window
    else:
        coherent_gain = float(nsamp)

    # FFT complessa bidirezionale
    Z = np.fft.fft(z)
    del z

    Z = np.fft.fftshift(Z)

    freq = np.fft.fftshift(
        np.fft.fftfreq(nsamp, d=1.0 / fs)
    ).astype(np.float32)

    # Ampiezza complessa normalizzata
    # Niente fattore 2, perché è una FFT complessa two-sided.
    fft_amp = (np.abs(Z) / coherent_gain).astype(np.float32)

    # Non serve tenere Z se salviamo solo modulo/picco
    del Z

    # Cerca picco evitando DC
    dc_index = nsamp // 2
    fft_amp_for_peak = fft_amp.copy()

    guard_bins = 2
    i0 = max(0, dc_index - guard_bins)
    i1 = min(nsamp, dc_index + guard_bins + 1)
    fft_amp_for_peak[i0:i1] = 0.0

    imax = int(np.argmax(fft_amp_for_peak))
    peak_freq = float(freq[imax])
    peak_amp = float(fft_amp[imax])
    idx = np.arange(nsamp, dtype=np.int64)
    if verbose:
        print(
            "%s | event = %s | peak freq = %.6f Hz | peak amp = %.6e V"
            % (mode_name, event_number, peak_freq, peak_amp)
        )
        
        # # Plot sottocampionato
        # if nsamp > plot_points:
        #     idx = np.linspace(0, nsamp - 1, plot_points).astype(np.int64)
            
    
        # fig, ax = plt.subplots(1, 1, figsize=(10, 5))
    
        # ax.plot(freq[idx], fft_amp[idx])
        # ax.set_xlabel("Frequency [Hz]")
        # ax.set_ylabel("|FFT| [V]")
        # ax.set_title(
        #     "%s complex FFT - run %05d event %08d"
        #     % (mode_name, run, event_number)
        # )
        # ax.grid(True)
        # ax.set_yscale("log")
    
        # fig.tight_layout()
    
        # out_png = os.path.join(
        #     outdir,
        #     "run%05d_event%08d_%s_complex_fft.png"
        #     % (run, event_number, mode_name)
        # )
    
        # fig.savefig(out_png, dpi=150)
        # plt.close(fig)
    
        # if verbose:
        #     print("Saved FFT plot:", out_png)

    # Summary leggero
    out_npz = os.path.join(
        outdir,
        "run%05d_event%08d_%s_fft_summary.npz"
        % (run, event_number, mode_name)
    )

    np.savez_compressed(
        out_npz,
        mode=mode_name,
        run=run,
        event_number=event_number,
        fs=fs,
        nsamp=nsamp,
        df=fs / nsamp,
        iq_sign=iq_sign,
        peak_freq=peak_freq,
        peak_amp=peak_amp,
        ch_i=ch_i,
        ch_q=ch_q,
        sa=fft_amp[idx],
    )
    if verbose:
        print("Saved summary:", out_npz)

    del freq, fft_amp, fft_amp_for_peak, idx
    gc.collect()


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

executor = ProcessPoolExecutor(max_workers=mode_workers)

try:
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
            
            # Reshape solo della porzione usata
            volt = s[:nsamp * Nch].reshape(nsamp, Nch) * scale 
    #######
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
    #######    
            # # FFT dei tre modi
            # for mode_name, (ch_i, ch_q) in iq_modes.items():
        
            #     complex_fft_only(
            #         frames=volt,
            #         mode_name=mode_name,
            #         ch_i=ch_i,
            #         ch_q=ch_q,
            #         fs=fs,
            #         input_range=input_range,
            #         iq_sign=args.iq_sign,
            #         run=run,
            #         event_number=event_number,
            #         outdir=fft_out,
            #         plot_points=args.plot_points,
            #         use_window=not args.no_window,
            #     )
        
            # n_fft_done += 1
    
            futures = []
    
            for mode_name, (ch_i, ch_q) in iq_modes.items():
                fut = executor.submit(
                    complex_fft_only,
                    frames=volt,
                    mode_name=mode_name,
                    ch_i=ch_i,
                    ch_q=ch_q,
                    fs=fs,
                    input_range=input_range,
                    iq_sign=args.iq_sign,
                    run=run,
                    event_number=event_number,
                    outdir=fft_out,
                    plot_points=args.plot_points,
                    use_window=not args.no_window,
                )
                futures.append((mode_name, fut))

                # Aspetta che tutti i modi IQ dell'evento siano completati
            for mode_name, fut in futures:
                try:
                    fut.result()
                    # print("DONE FFT mode:", mode_name, "event:", event_number)
                except Exception:
                    print("ERROR in FFT mode:", mode_name, "event:", event_number)
                    raise
        
            # Incrementa UNA volta per evento SPEC processato
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
finally:
    executor.shutdown(wait=True)
        
print("DONE")