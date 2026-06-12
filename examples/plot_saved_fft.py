import argparse
import os
import numpy as np
import matplotlib.pyplot as plt


def npz_get_scalar(data, key, default=None):
    if key not in data:
        return default

    value = data[key]

    if isinstance(value, np.ndarray):
        if value.shape == ():
            return value.item()
        if value.size == 1:
            return value.reshape(-1)[0].item()

    return value


def make_subsample_indices(n, max_points=None, step=None):
    """
    Restituisce gli indici per ridurre il numero di punti plottati.
    - Se step è definito, prende un punto ogni 'step'.
    - Altrimenti, se max_points è definito, usa al massimo max_points punti.
    - Altrimenti usa tutti i punti.
    """
    if n <= 0:
        return np.array([], dtype=np.int64)

    if step is not None:
        step = int(step)
        if step <= 0:
            raise ValueError("--step deve essere > 0")
        return np.arange(0, n, step, dtype=np.int64)

    if max_points is not None:
        max_points = int(max_points)
        if max_points <= 0:
            raise ValueError("--max-points deve essere > 0")

        if n > max_points:
            return np.linspace(0, n - 1, max_points).astype(np.int64)

    return np.arange(n, dtype=np.int64)


def main():
    parser = argparse.ArgumentParser(
        description="Apre un file .npz FFT summary, ricostruisce l'asse frequenze e plotta la FFT."
    )

    parser.add_argument("file", help="File .npz da plottare")

    parser.add_argument("--out", default=None,
                        help="Nome file PNG di output. Default: <file>_plot.png")

    parser.add_argument("--show", action="store_true",
                        help="Mostra il plot a schermo")

    parser.add_argument("--db", action="store_true",
                        help="Plot in dB: 20*log10(|FFT|)")

    parser.add_argument("--linear", action="store_true",
                        help="Usa scala lineare invece di log, se non usi --db")

    parser.add_argument("--fmin", type=float, default=None,
                        help="Frequenza minima da plottare [Hz]")

    parser.add_argument("--fmax", type=float, default=None,
                        help="Frequenza massima da plottare [Hz]")

    parser.add_argument("--max-points", type=int, default=None,
                        help="Numero massimo di punti da plottare dopo eventuale filtro fmin/fmax")

    parser.add_argument("--step", type=int, default=None,
                        help="Subsample: plotta un punto ogni STEP dopo eventuale filtro fmin/fmax")

    parser.add_argument("--no-peak", action="store_true",
                        help="Non disegnare la linea verticale sul picco salvato")

    args = parser.parse_args()

    in_file = os.path.expanduser(args.file)

    if not os.path.exists(in_file):
        raise FileNotFoundError(f"File non trovato: {in_file}")

    data = np.load(in_file, allow_pickle=True)

    required = ["fs", "nsamp", "idx", "sa"]

    missing = [key for key in required if key not in data]
    if missing:
        raise KeyError(f"File .npz incompleto. Mancano queste chiavi: {missing}")

    fs = float(npz_get_scalar(data, "fs"))
    nsamp = int(npz_get_scalar(data, "nsamp"))

    idx = np.asarray(data["idx"], dtype=np.int64)
    amp = np.asarray(data["sa"], dtype=np.float64)

    if idx.size != amp.size:
        raise ValueError(
            f"Dimensione non coerente: idx ha {idx.size} punti, sa ha {amp.size} punti"
        )

    if np.any(idx < 0) or np.any(idx >= nsamp):
        raise ValueError("idx contiene indici fuori range rispetto a nsamp")

    # Ricostruzione asse frequenza completo e poi selezione degli indici salvati
    freq_full = np.fft.fftshift(np.fft.fftfreq(nsamp, d=1.0 / fs))
    freq = freq_full[idx]

    # Libera l'asse completo, che può essere grande
    del freq_full

    mode = npz_get_scalar(data, "mode", "UNKNOWN")
    run = npz_get_scalar(data, "run", None)
    event_number = npz_get_scalar(data, "event_number", None)
    df = npz_get_scalar(data, "df", fs / nsamp)
    iq_sign = npz_get_scalar(data, "iq_sign", None)
    peak_freq = npz_get_scalar(data, "peak_freq", None)
    peak_amp = npz_get_scalar(data, "peak_amp", None)
    ch_i = npz_get_scalar(data, "ch_i", None)
    ch_q = npz_get_scalar(data, "ch_q", None)

    # Finestra in frequenza opzionale
    mask = np.ones_like(freq, dtype=bool)

    if args.fmin is not None:
        mask &= freq >= args.fmin

    if args.fmax is not None:
        mask &= freq <= args.fmax

    freq_plot = freq[mask]
    amp_plot = amp[mask]

    if freq_plot.size == 0:
        raise ValueError("Nessun punto da plottare nella finestra di frequenza richiesta.")

    # Ulteriore subsample scelto da riga di comando
    sub_idx = make_subsample_indices(
        n=freq_plot.size,
        max_points=args.max_points,
        step=args.step,
    )

    freq_plot = freq_plot[sub_idx]
    amp_plot = amp_plot[sub_idx]

    # Unità asse frequenze: automatico
    max_abs_f = np.max(np.abs(freq_plot))

    if max_abs_f >= 1e6:
        f_scale = 1e6
        f_unit = "MHz"
    elif max_abs_f >= 1e3:
        f_scale = 1e3
        f_unit = "kHz"
    else:
        f_scale = 1.0
        f_unit = "Hz"

    freq_display = freq_plot / f_scale

    # Ampiezza lineare o dB
    if args.db:
        eps = np.finfo(np.float64).tiny
        y = 20.0 * np.log10(np.maximum(amp_plot, eps))
        ylabel = "|FFT| [dB]"
    else:
        y = amp_plot
        ylabel = "|FFT| [V]"

    title_parts = [str(mode), "complex FFT"]

    if run is not None:
        title_parts.append(f"run {int(run):05d}")

    if event_number is not None:
        title_parts.append(f"event {int(event_number):08d}")

    title = " - ".join(title_parts)

    info_lines = [
        f"fs = {fs:g} Hz",
        f"Nsamp = {nsamp}",
        f"df = {float(df):g} Hz",
        f"saved points = {idx.size}",
        f"plotted points = {freq_plot.size}",
    ]

    if iq_sign is not None:
        info_lines.append(f"iq_sign = {int(iq_sign)}")

    if ch_i is not None and ch_q is not None:
        info_lines.append(f"I = CH{int(ch_i)}, Q = CH{int(ch_q)}")

    subtitle = " | ".join(info_lines)

    fig, ax = plt.subplots(1, 1, figsize=(11, 6))

    ax.plot(freq_display, y)
    ax.set_xlabel(f"Frequency [{f_unit}]")
    ax.set_ylabel(ylabel)
    ax.set_title(title + "\n" + subtitle)
    ax.grid(True)

    if not args.linear and not args.db:
        ax.set_yscale("log")

    # Linea sul picco salvato
    if not args.no_peak and peak_freq is not None and peak_amp is not None:
        peak_freq = float(peak_freq)
        peak_amp = float(peak_amp)

        in_range = True

        if args.fmin is not None and peak_freq < args.fmin:
            in_range = False

        if args.fmax is not None and peak_freq > args.fmax:
            in_range = False

        if in_range:
            peak_x = peak_freq / f_scale

            if args.db:
                eps = np.finfo(np.float64).tiny
                peak_y = 20.0 * np.log10(max(peak_amp, eps))
            else:
                peak_y = peak_amp

            ax.axvline(peak_x, linestyle="--", linewidth=1.2)
            ax.annotate(
                f"peak = {peak_freq:.6g} Hz",
                xy=(peak_x, peak_y),
                xytext=(10, 10),
                textcoords="offset points",
                fontsize=9,
                arrowprops=dict(arrowstyle="->", linewidth=0.8),
            )

    fig.tight_layout()

    if args.out is None:
        base, _ = os.path.splitext(in_file)
        out_file = base + "_plot.png"
    else:
        out_file = os.path.expanduser(args.out)

    fig.savefig(out_file, dpi=150)
    print("Saved plot:", out_file)

    if args.show:
        plt.show()
    else:
        plt.close(fig)


if __name__ == "__main__":
    main()