#!/usr/bin/env python3
"""Print frequency coordinates and PSD values from FLASH ROOT/HDF5 v3 products.

The stored quantities are power spectral densities (V^2/Hz), not complex
FFT coefficients. Only window_psd retains individual 1-second time windows.
"""
import argparse
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from iq_products import open_product

MODES = ("TM010", "TM011", "TM012")
SPECTRA = ("window_psd", "short_hann", "short_rectangular", "mean_psd")


def coordinates(product, spectrum):
    """Return frequency centers and widths appropriate to the stored product."""
    if spectrum.startswith("short_"):
        frequencies = np.asarray(product.file["short_psd/frequency_hz"][:])
        return frequencies, np.full_like(frequencies, product.fs / len(frequencies),
                                         dtype=np.float64)
    if spectrum == "window_psd":
        edges = np.asarray(product.edges, dtype=np.float64)
        return (edges[:-1] + edges[1:]) / 2, np.asarray(product.widths)
    # The mean PSD uses the original 1-Hz FFT grid.
    return np.asarray(product.frequency(), dtype=np.float64), None


def dataset(product, mode, spectrum):
    if spectrum == "window_psd":
        return product.file[f"spectra/{mode}/window_psd"]
    if spectrum == "mean_psd":
        return product.file[f"spectra/{mode}/mean_psd"]
    return product.file[f"short_psd/{spectrum[len('short_'):]}/{mode}"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", type=Path, nargs="+", help="local ROOT v3.1 or HDF5 v3 products")
    parser.add_argument("--spectrum", choices=SPECTRA, default="window_psd",
                        help="stored PSD representation (default: window_psd)")
    parser.add_argument("--mode", choices=(*MODES, "all"), default="all")
    parser.add_argument("--n", type=int, default=10, help="number of first bins to print")
    parser.add_argument("--window", type=int, default=0,
                        help="zero-based 1-second window index, for window_psd only")
    parser.add_argument("--all-windows", action="store_true",
                        help="print every 1-second window (window_psd only)")
    args = parser.parse_args()
    if args.n < 1 or args.window < 0:
        parser.error("--n must be positive and --window nonnegative")
    if args.spectrum != "window_psd" and (args.all_windows or args.window):
        parser.error("--window and --all-windows only apply to --spectrum window_psd")

    failed = False
    for path in args.files:
        try:
            with open_product(path) as product:
                freqs, widths = coordinates(product, args.spectrum)
                selected = MODES if args.mode == "all" else (args.mode,)
                n = min(args.n, len(freqs))
                print(f"# file={path} run={product.run} fs_Hz={product.fs:g}")
                print(f"# spectrum={args.spectrum} frequency_bins={len(freqs)} "
                      "units=Hz; PSD units=V^2/Hz")
                print(f"frequency_hz[:{n}] = {freqs[:n].tolist()}")
                if widths is not None:
                    print(f"bin_width_hz[:{n}] = {widths[:n].tolist()}")

                for mode in selected:
                    ds = dataset(product, mode, args.spectrum)
                    shape = ds.shape
                    if args.spectrum == "window_psd":
                        if len(shape) != 2 or shape[1] != len(freqs):
                            raise ValueError(f"{mode}: unexpected PSD shape {shape}")
                        count = shape[0]
                        if not args.all_windows and args.window >= count:
                            raise ValueError(f"{mode}: window {args.window} outside 0..{count-1}")
                        print(f"# {mode}: {count} ordered 1-second PSD windows, {shape[1]} bins each")
                        windows = range(count) if args.all_windows else (args.window,)
                        for i in windows:
                            values = np.asarray(ds[i:i + 1, :n])[0]
                            received = int(product.windows["received_index"][i])
                            print(f"{mode} window={i} acquired_s={received/product.fs:.6f} "
                                  f"psd[:{n}]={values.tolist()}")
                    else:
                        if len(shape) != 1 or shape[0] != len(freqs):
                            raise ValueError(f"{mode}: unexpected PSD shape {shape}")
                        values = np.asarray(ds[:n])
                        print(f"# {mode}: one time-averaged PSD, {shape[0]} bins")
                        print(f"{mode} psd[:{n}]={values.tolist()}")
        except (OSError, ValueError, KeyError, ImportError, IndexError) as error:
            print(f"ERROR {path}: {error}", file=sys.stderr)
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
