#!/usr/bin/env python3
"""Genera plot degli spettri FFT prodotti da autoreco."""

import argparse
import os
import re
from pathlib import Path
from typing import Iterable, List

import numpy as np


MODE_NAMES = {
    0: "TM010",
    1: "TM011",
    2: "TM012",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plotta gli spettri FFT contenuti nei file runNNNNN.npz "
            "prodotti da autoreco."
        )
    )
    parser.add_argument(
        "inputs",
        type=Path,
        nargs="+",
        help="uno o più file .npz oppure directory che li contengono",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("fft_plots"),
        help="directory dei PNG prodotti (default: ./fft_plots)",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="cerca file .npz ricorsivamente nelle directory",
    )
    parser.add_argument(
        "--modes",
        type=int,
        nargs="+",
        choices=(0, 1, 2),
        default=(0, 1, 2),
        help="modi da plottare (default: 0 1 2)",
    )
    parser.add_argument(
        "--db",
        action="store_true",
        help="mostra la potenza in dB (10*log10)",
    )
    parser.add_argument(
        "--linear-y",
        action="store_true",
        help="usa una scala Y lineare; il default è logaritmico",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="non normalizza per numero di eventi e chunk",
    )
    parser.add_argument("--fmin", type=float, help="frequenza minima [Hz]")
    parser.add_argument("--fmax", type=float, help="frequenza massima [Hz]")
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="risoluzione dei PNG (default: 150)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="mostra interattivamente ogni figura",
    )
    args = parser.parse_args()

    if args.fmin is not None and args.fmax is not None:
        if args.fmin >= args.fmax:
            parser.error("--fmin deve essere minore di --fmax")
    if args.dpi <= 0:
        parser.error("--dpi deve essere maggiore di zero")
    return args


def find_npz_files(inputs: Iterable[Path], recursive: bool) -> List[Path]:
    files = set()
    pattern = "**/*.npz" if recursive else "*.npz"
    for item in inputs:
        item = item.expanduser()
        if item.is_file():
            if item.suffix.lower() != ".npz":
                raise ValueError(f"Il file non è .npz: {item}")
            files.add(item.resolve())
        elif item.is_dir():
            files.update(path.resolve() for path in item.glob(pattern))
        else:
            raise FileNotFoundError(f"Input non trovato: {item}")
    return sorted(files)


def scalar(data, key: str, default):
    if key not in data:
        return default
    value = np.asarray(data[key])
    return value.item() if value.size == 1 else value


def frequency_axis(data, size: int) -> np.ndarray:
    """Ricostruisce l'asse usando la lunghezza reale dello spettro."""
    fs = float(scalar(data, "fs", 5e6))
    return np.fft.fftshift(np.fft.fftfreq(size, d=1.0 / fs))


def run_label(path: Path) -> str:
    match = re.search(r"run0*(\d+)", path.stem, flags=re.IGNORECASE)
    return f"run {int(match.group(1)):05d}" if match else path.stem


def plot_file(path: Path, args, plt) -> Path:
    with np.load(path, allow_pickle=False) as data:
        available = [
            mode
            for mode in args.modes
            if f"fft_amp_mode{mode}_SPECs" in data
        ]
        if not available:
            raise KeyError(
                f"{path}: nessuno spettro trovato per i modi richiesti"
            )

        n_events = int(scalar(data, "n_fft_done", 1))
        n_chunks = int(scalar(data, "number_chunks", 1))
        normalization = n_events * n_chunks
        if normalization <= 0:
            normalization = 1

        fig, axes = plt.subplots(
            len(available),
            1,
            figsize=(12, 3.6 * len(available)),
            sharex=True,
            squeeze=False,
        )
        axes = axes[:, 0]

        for ax, mode in zip(axes, available):
            key = f"fft_amp_mode{mode}_SPECs"
            power = np.asarray(data[key], dtype=np.float64)
            if power.ndim != 1 or power.size == 0:
                raise ValueError(f"{path}: {key} non è un array 1D valido")
            if not args.raw:
                power = power / normalization

            freq = frequency_axis(data, power.size)
            mask = np.ones(freq.size, dtype=bool)
            if args.fmin is not None:
                mask &= freq >= args.fmin
            if args.fmax is not None:
                mask &= freq <= args.fmax
            if not np.any(mask):
                raise ValueError(
                    f"{path}: nessun punto nella finestra richiesta"
                )

            x = freq[mask] / 1e6
            y = power[mask]
            ylabel = "Power [V²]"
            if args.db:
                positive = y[y > 0]
                floor = (
                    np.min(positive)
                    if positive.size
                    else np.finfo(np.float64).tiny
                )
                y = 10.0 * np.log10(np.maximum(y, floor))
                ylabel = "Power [dB(V²)]"

            ax.plot(x, y, linewidth=0.8)
            ax.set_ylabel(ylabel)
            ax.set_title(f"{MODE_NAMES[mode]} (mode {mode})")
            ax.grid(True, alpha=0.3)
            if not args.db and not args.linear_y:
                ax.set_yscale("log")

        axes[-1].set_xlabel("Frequency [MHz]")
        normalization_text = (
            "raw sum"
            if args.raw
            else f"average over {n_events} events × {n_chunks} chunks"
        )
        fig.suptitle(f"{run_label(path)} — {normalization_text}")
        fig.tight_layout()

        args.output_dir.mkdir(parents=True, exist_ok=True)
        output = args.output_dir / f"{path.stem}_fft.png"
        fig.savefig(output, dpi=args.dpi)
        if args.show:
            plt.show()
        plt.close(fig)
        return output


def main() -> None:
    args = parse_args()

    cache_dir = Path("/tmp") / f"autoreco-matplotlib-{os.getuid()}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir))

    import matplotlib

    if not args.show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    files = find_npz_files(args.inputs, args.recursive)
    if not files:
        raise RuntimeError("Nessun file .npz trovato")

    failures = 0
    for path in files:
        try:
            output = plot_file(path, args, plt)
            print(f"{path} -> {output}")
        except (KeyError, ValueError, OSError) as exc:
            failures += 1
            print(f"ERRORE {path}: {exc}")

    print(f"Plot creati: {len(files) - failures}; errori: {failures}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
