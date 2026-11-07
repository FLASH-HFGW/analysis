import numpy as np
import midas.file_reader
from datetime import datetime
import os
import argparse
import matplotlib.pyplot as plt

# ------------------------------------------------------------
# Parametri da riga di comando
# ------------------------------------------------------------
parser = argparse.ArgumentParser(
    description="Legge un file MIDAS, ricostruisce I/Q dei modi TM e salva ampiezza, fase e FFT complessa."
)

parser.add_argument("--path", required=True,
                    help="Directory contenente i file MIDAS, es: ~/flash-data/data/LNF/")

parser.add_argument("--run", required=True, type=int,
                    help="Numero run, es: 123")

parser.add_argument("--fft-out", default="/home/mazzitel/HFGW/analysis-work/Run2/staging/examples/fft_plots",
                    help="Directory dove salvare i plot")

parser.add_argument("--max-fft-events", type=int, default=10,
                    help="Numero massimo di eventi SPEC da processare, default 10")

parser.add_argument("--fs", type=float, default=5e6,
                    help="Sampling frequency [Hz], default 5e6")

parser.add_argument("--input-range", type=float, default=5.0,
                    help="Input range ADC in Volt, es. 5 per +/-5 V, default 5")

parser.add_argument("--iq-sign", type=int, default=+1, choices=[+1, -1],
                    help="Convenzione I/Q: +1 usa I + jQ, -1 usa I - jQ, default +1")

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
# Definizione coppie I/Q
# ------------------------------------------------------------
# CH0 e CH5: I/Q TM010
# CH1 e CH3: I/Q TM011
# CH2 e CH4: I/Q TM012
# CH6: PPS
iq_modes = {
    "TM010": {"I": 0, "Q": 5},
    "TM011": {"I": 1, "Q": 3},
    "TM012": {"I": 2, "Q": 4},
}

pps_channel = 6


# ------------------------------------------------------------
# Funzione analisi I/Q
# ------------------------------------------------------------
def analyze_iq_mode(
    volt,
    t,
    fs,
    run,
    event_number,
    mode_name,
    ch_i,
    ch_q,
    iq_sign,
    outdir
):
    """
    Costruisce z(t)=I+jQ oppure I-jQ, calcola ampiezza,
    fase e FFT complessa, poi salva due plot.
    """

    I = volt[:, ch_i]
    Q = volt[:, ch_q]

    # Rimozione offset DC separatamente su I e Q
    I0 = I - np.mean(I)
    Q0 = Q - np.mean(Q)

    # Segnale complesso
    z = I0 + 1j * iq_sign * Q0

    # Ampiezza e fase
    amp_t = np.abs(z)
    phase_t = np.unwrap(np.angle(z))

    # FFT complessa
    Nsamp = len(z)
    window = np.hanning(Nsamp)

    z_w = z * window

    Z = np.fft.fftshift(np.fft.fft(z_w))
    freq = np.fft.fftshift(np.fft.fftfreq(Nsamp, d=1.0 / fs))

    # Normalizzazione ampiezza FFT
    # Per segnale complesso non si usa il fattore 2 single-sided.
    fft_amp = np.abs(Z) / np.sum(window)

    fft_phase = np.angle(Z)

    # Picco principale, evitando eventualmente la DC centrale
    dc_index = Nsamp // 2

    fft_amp_no_dc = fft_amp.copy()
    guard_bins = 2

    i0 = max(0, dc_index - guard_bins)
    i1 = min(Nsamp, dc_index + guard_bins + 1)
    fft_amp_no_dc[i0:i1] = 0.0

    imax = np.argmax(fft_amp_no_dc)

    print(
        "%s | event = %s | peak freq = %.6f Hz | peak amp = %.6e V"
        % (mode_name, event_number, freq[imax], fft_amp[imax])
    )

    # --------------------------------------------------------
    # Plot 1: ampiezza e fase nel tempo
    # --------------------------------------------------------
    fig, ax = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    ax[0].plot(t, amp_t)
    ax[0].set_ylabel("|I+jQ| [V]")
    ax[0].set_title("%s amplitude - event %s" % (mode_name, event_number))
    ax[0].grid(True)

    ax[1].plot(t, phase_t)
    ax[1].set_xlabel("Time [s]")
    ax[1].set_ylabel("Unwrapped phase [rad]")
    ax[1].set_title("%s phase - event %s" % (mode_name, event_number))
    ax[1].grid(True)

    fig.tight_layout()

    out_time = os.path.join(
        outdir,
        "run%05d_event%08d_%s_amp_phase.png"
        % (run, event_number, mode_name)
    )

    fig.savefig(out_time, dpi=150)
    plt.close(fig)

    print("Saved time plot:", out_time)

    # --------------------------------------------------------
    # Plot 2: FFT complessa
    # --------------------------------------------------------
    fig, ax = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    ax[0].plot(freq, fft_amp)
    ax[0].set_ylabel("|FFT| [V]")
    ax[0].set_title("%s complex FFT amplitude - event %s" % (mode_name, event_number))
    ax[0].grid(True)
    ax[0].set_yscale("log")

    ax[1].plot(freq, fft_phase)
    ax[1].set_xlabel("Frequency [Hz]")
    ax[1].set_ylabel("FFT phase [rad]")
    ax[1].set_title("%s complex FFT phase - event %s" % (mode_name, event_number))
    ax[1].grid(True)

    fig.tight_layout()

    out_fft = os.path.join(
        outdir,
        "run%05d_event%08d_%s_complex_fft.png"
        % (run, event_number, mode_name)
    )

    fig.savefig(out_fft, dpi=150)
    plt.close(fig)

    print("Saved FFT plot:", out_fft)

    # --------------------------------------------------------
    # Salvataggio numerico opzionale
    # --------------------------------------------------------
    out_npz = os.path.join(
        outdir,
        "run%05d_event%08d_%s_iq_analysis.npz"
        % (run, event_number, mode_name)
    )

    np.savez_compressed(
        out_npz,
        t=t,
        I=I,
        Q=Q,
        I0=I0,
        Q0=Q0,
        z=z,
        amplitude_time=amp_t,
        phase_time=phase_t,
        freq=freq,
        fft_complex=Z,
        fft_amplitude=fft_amp,
        fft_phase=fft_phase,
        peak_freq=freq[imax],
        peak_amp=fft_amp[imax],
    )

    print("Saved numerical output:", out_npz)


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

    # --------------------------------------------------------
    # Analisi SPEC
    # NOTA: qui non deve stare dentro l'if event_number % 1000
    # altrimenti processi solo gli eventi multipli di 1000.
    # --------------------------------------------------------
    if "SPEC" in event.banks and n_fft_done < args.max_fft_events:

        inputRange = args.input_range
        Nch = 8
        fs = args.fs

        # Decode Spectrum digitizer
        u = np.asarray(event.banks["SPEC"].data, dtype=np.uint16)  # 0..65535
        s = u.view(np.int16)                                       # -32768..32767

        Nsamp = s.size // Nch

        if Nsamp <= 1:
            print("WARNING: evento SPEC troppo corto, salto")
            continue

        frames = s[:Nsamp * Nch].reshape(Nsamp, Nch)               # [time, ch]

        # Conversione ADC -> Volt
        volt = frames.astype(np.float64) * (2.0 * inputRange / 65536.0)

        # Tempo
        t = np.arange(Nsamp) / fs

        print("----------------------------------------")
        print("Processing SPEC event:", event_number)
        print("Nsamp:", Nsamp)
        print("fs:", fs, "Hz")
        print("duration:", Nsamp / fs, "s")
        print("----------------------------------------")

        # PPS, se vuoi controllarlo
        pps = volt[:, pps_channel]
        pps_min = np.min(pps)
        pps_max = np.max(pps)

        print(
            "PPS CH%d | min = %.6f V | max = %.6f V"
            % (pps_channel, pps_min, pps_max)
        )

        # Analisi dei tre modi
        for mode_name, chs in iq_modes.items():

            analyze_iq_mode(
                volt=volt,
                t=t,
                fs=fs,
                run=run,
                event_number=event_number,
                mode_name=mode_name,
                ch_i=chs["I"],
                ch_q=chs["Q"],
                iq_sign=args.iq_sign,
                outdir=fft_out
            )

        n_fft_done += 1

print("DONE")