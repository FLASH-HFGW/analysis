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


def rebin_edges(edges_hz, bin_hz):
    """Build an ascending grid covering the original band, including its last bin."""
    edges = np.asarray(edges_hz, dtype=np.float64)
    if edges.ndim != 1 or len(edges) < 2 or not np.all(np.isfinite(edges)):
        raise ValueError("frequency edges must be a finite one-dimensional array")
    if np.any(np.diff(edges) <= 0):
        raise ValueError("frequency edges must be strictly increasing")
    if not np.isfinite(bin_hz) or bin_hz <= 0:
        raise ValueError("rebin width must be finite and positive")
    span = edges[-1] - edges[0]
    count = span / bin_hz
    if not np.isfinite(count) or count >= np.iinfo(np.intp).max:
        raise ValueError("rebin width would generate too many bins")
    if bin_hz < np.spacing(np.max(np.abs(edges))):
        raise ValueError("rebin width is below the precision of the frequency axis")
    inner = edges[0] + bin_hz * np.arange(1, int(np.ceil(count)))
    # A boundary that rounds to the upper edge needs no additional partial bin.
    target = np.r_[edges[0], inner[inner < edges[-1]], edges[-1]]
    if np.any(np.diff(target) <= 0):
        raise ValueError("rebin width is below the precision of the frequency axis")
    return target


def rebin_psd(psd, edges_hz, bin_hz):
    """Return centers in Hz and a (windows, bins) density matrix in V²/Hz.

    Integrate the piecewise-constant input density on the overlap of the two
    grids. Divide by each output bin's actual width, including the last bin.
    """
    edges = np.asarray(edges_hz, dtype=np.float64)
    target = rebin_edges(edges, bin_hz)
    values = np.asarray(psd, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != len(edges) - 1:
        raise ValueError("PSD must have shape (windows, len(edges_hz) - 1)")
    widths = np.diff(target)
    centers = target[:-1] + widths / 2
    # Precompute the source-bin overlap of each target boundary. Subtracting
    # whole-band cumulative integrals would sacrifice precision in quiet bins.
    start = np.searchsorted(edges, target[:-1], side="right") - 1
    stop = np.searchsorted(edges, target[1:], side="left") - 1
    split = start != stop
    interior = split & (stop > start + 1)
    start_split, stop_split = start[split], stop[split]
    lower_overlap = edges[start_split + 1] - target[:-1][split]
    upper_overlap = target[1:][split] - edges[stop_split]
    source_widths = np.diff(edges)
    bounds = np.column_stack((start[interior] + 1, stop[interior])).ravel()
    result = np.empty((len(values), len(widths)))
    for output, row in zip(result, values):
        if not np.all(np.isfinite(row)):
            raise ValueError("PSD values must be finite")
        tolerance = 32 * np.finfo(row.dtype).eps * np.max(np.abs(row))
        if np.any(row < -tolerance):
            raise ValueError("PSD contains negative values beyond numerical tolerance")
        row = np.maximum(row, 0)
        output[:] = row[start]
        power = row[start_split] * lower_overlap
        power += row[stop_split] * upper_overlap
        if bounds.size:
            # The requested interior ranges are disjoint. Interleave each
            # range's end with the next start, then discard gap reductions.
            sums = np.add.reduceat(row * source_widths, bounds)[::2]
            power[interior[split]] += sums
        output[split] = power / widths[split]
    return centers, result


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
    parser.add_argument("--window", type=int,
                        help="zero-based 1-second window index, for window_psd only")
    parser.add_argument("--all-windows", action="store_true",
                        help="print every 1-second window (window_psd only)")
    parser.add_argument("--rebin-hz", type=float,
                        help="rebin window_psd by overlap integration at this width in Hz")
    args = parser.parse_args()
    if args.n < 1 or (args.window is not None and args.window < 0):
        parser.error("--n must be positive and --window nonnegative")
    if args.spectrum != "window_psd" and (args.all_windows or args.window is not None or args.rebin_hz is not None):
        parser.error("--window, --all-windows and --rebin-hz only apply to --spectrum window_psd")

    window = 0 if args.window is None else args.window
    failed = False
    for path in args.files:
        try:
            with open_product(path) as product:
                freqs, widths = coordinates(product, args.spectrum)
                stored_bins = len(freqs)
                if args.rebin_hz is not None:
                    edges = np.asarray(product.edges)
                    if not np.allclose(np.diff(edges), widths, rtol=1e-12, atol=0):
                        raise ValueError("stored window bin widths disagree with the frequency edges")
                    target = rebin_edges(edges, args.rebin_hz)
                    widths = np.diff(target)
                    freqs = target[:-1] + widths / 2
                selected = MODES if args.mode == "all" else (args.mode,)
                n = min(args.n, len(freqs))
                print(f"# file={path} run={product.run} fs_Hz={product.fs:g}")
                print(f"# spectrum={args.spectrum} frequency_bins={len(freqs)} "
                      "units=Hz; PSD units=V^2/Hz")
                if args.rebin_hz is not None:
                    print(f"# requested_rebin_hz={args.rebin_hz} last_bin_width_hz={widths[-1]}")
                print(f"frequency_hz[:{n}] = {freqs[:n].tolist()}")
                if widths is not None:
                    print(f"bin_width_hz[:{n}] = {widths[:n].tolist()}")

                for mode in selected:
                    ds = dataset(product, mode, args.spectrum)
                    shape = ds.shape
                    if args.spectrum == "window_psd":
                        if len(shape) != 2 or shape[1] != stored_bins:
                            raise ValueError(f"{mode}: unexpected PSD shape {shape}")
                        count = shape[0]
                        if not args.all_windows and window >= count:
                            raise ValueError(f"{mode}: window {window} outside 0..{count-1}")
                        print(f"# {mode}: {count} ordered 1-second PSD windows, {len(freqs)} bins each")
                        windows = range(count) if args.all_windows else (window,)
                        for i in windows:
                            if args.rebin_hz is None:
                                values = np.asarray(ds[i:i + 1, :n])[0]
                            else:
                                _, rebinned = rebin_psd(ds[i:i + 1], edges, args.rebin_hz)
                                values = rebinned[0, :n]
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
