import numpy as np
import midas.file_reader
from datetime import datetime
import os
import argparse
import matplotlib.pyplot as plt

# ------------------------------------------------------------
# Parametri da riga di comando
# ------------------------------------------------------------
parser = argparse.ArgumentParser(description="Legge un file MIDAS e stampa gli equipment/bank incontrati.")
parser.add_argument("--path", required=True, help="Directory contenente i file MIDAS, es: ~/flash-data/QUAX/TEST")
parser.add_argument("--run", required=True, type=int, help="Numero run, es: 123")
parser.add_argument("--fft-out", default="fft_plots", help="Directory dove salvare i plot FFT")
parser.add_argument("--max-fft-events", type=int, default=10, help="Numero massimo di eventi SPEC da processare")
args = parser.parse_args()

fft_out = os.path.expanduser(args.fft_out)
os.makedirs(fft_out, exist_ok=True)

n_fft_done = 0

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
        Run_description = odb["Experiment"]["Run Parameters"]["Run description"]
        print("Run_description:", Run_description)
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


# ------------------------------------------------------------
# Loop eventi
# ------------------------------------------------------------
seen_equipments = set()

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

    # Stampa quando incontra un equipment nuovo
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

    # Debug periodico
    if event_number % 1000 == 0:
        print("Event # %s of type ID %s, equipment %s, contains banks %s" %
              (event_number, event_id, equipment_name, bank_names))

        print("Received event with timestamp %s containing banks %s" %
              (event_timestamp, bank_names))

        print("Event # %s at %s, banks %s" %
              (event_number,
               datetime.utcfromtimestamp(event_timestamp).strftime("%Y-%m-%d %H:%M:%S"),
               bank_names))

    # Stampa i bank name dell'evento

        if "SPEC" in bank_names and n_fft_done < args.max_fft_events:
            ########################### FFT SPEC ch0 ##################################

            # Parametri digitizer
            inputRange = 5      # +/- 5 V
            Nch = 8
            fs = 5e6            # Hz

            # Decode Spectrum digitizer
            u = np.asarray(event.banks["SPEC"].data, dtype=np.uint16)  # 0..65535
            s = u.view(np.int16)                                       # -32768..32767

            Nsamp = s.size // Nch
            if Nsamp <= 1:
                print("WARNING: evento SPEC troppo corto, salto FFT")
                continue

            frames = s[:Nsamp * Nch].reshape(Nsamp, Nch)               # [time, ch]

            # Conversione ADC -> Volt
            volt = frames.astype(np.float64) * (2.0 * inputRange / 65536.0)

            # Tempo
            t = np.arange(Nsamp) / fs                                  # [s]

            # Canale 0
            ch0 = volt[:, 0]

            # Rimuovi DC
            x = ch0 - np.mean(ch0)

            # Finestra per ridurre leakage
            window = np.hanning(Nsamp)
            xw = x * window

            # FFT reale
            fft_ch0 = np.fft.rfft(xw)
            freq = np.fft.rfftfreq(Nsamp, d=1.0 / fs)

            # Ampiezza single-sided in Volt
            amp = np.abs(fft_ch0) * 2.0 / np.sum(window)

            # Non raddoppiare DC
            amp[0] *= 0.5

            # Se Nsamp pari, non raddoppiare Nyquist
            if Nsamp % 2 == 0:
                amp[-1] *= 0.5

            # Picco principale, ignorando DC
            if len(amp) > 1:
                imax = np.argmax(amp[1:]) + 1
                print("SPEC FFT ch0 | event =", event_number,
                      "| peak freq =", freq[imax], "Hz",
                      "| peak amp =", amp[imax], "V")

            # Plot tempo + FFT
            fig, ax = plt.subplots(2, 1, figsize=(10, 7))

            ax[0].plot(t, ch0)
            ax[0].set_xlabel("Time [s]")
            ax[0].set_ylabel("ch0 [V]")
            ax[0].set_title("SPEC ch0 waveform - event %s" % event_number)
            ax[0].grid(True)

            ax[1].plot(freq, amp)
            ax[1].set_xlabel("Frequency [Hz]")
            ax[1].set_ylabel("Amplitude [V]")
            ax[1].set_title("FFT SPEC ch0 - event %s" % event_number)
            ax[1].grid(True)

            # Scala log opzionale sull'asse y, utile se lo spettro ha grande dinamica
            ax[1].set_yscale("log")

            fig.tight_layout()

            outname = os.path.join(
                fft_out,
                "run%05d_event%08d_SPEC_ch0_fft.png" % (run, event_number)
            )

            fig.savefig(outname, dpi=150)
            plt.close(fig)

            print("Saved FFT plot:", outname)

            n_fft_done += 1

            ###########################################################################


            #############################################################################

print("DONE")
