#!/usr/bin/env python3
"""Print first N bins of the ordered one-second 100-Hz PSD, per mode/window.

This is a power spectral density, not complex FFT coefficients.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from iq_products import open_product

MODES = ("TM010", "TM011", "TM012")

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+", type=Path, help="ROOT v3.1 files")
    ap.add_argument("--mode", choices=(*MODES, "all"), default="all")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--window", type=int, default=0, help="zero-based 1-s window")
    ap.add_argument("--all-windows", action="store_true")
    args = ap.parse_args()
    if args.n < 1 or args.window < 0:
        ap.error("--n must be positive and --window nonnegative")
    errors = 0
    for path in args.files:
        try:
            with open_product(path) as p:
                print(f"# file={path} run={p.run} fs_Hz={p.fs:g}")
                for mode in (MODES if args.mode == "all" else (args.mode,)):
                    ds = p.file[f"spectra/{mode}/window_psd"]
                    if len(ds.shape) != 2:
                        raise ValueError(f"unexpected PSD shape {ds.shape}")
                    nwin, nbin = ds.shape
                    if not args.all_windows and args.window >= nwin:
                        raise ValueError(f"window {args.window} outside 0..{nwin-1}")
                    n = min(args.n, nbin)
                    for i in (range(nwin) if args.all_windows else (args.window,)):
                        vals = ds[i:i+1, 0:n][0]  # bounded, no full PSD load
                        index = int(p.windows["received_index"][i])
                        print(f"{mode} window={i} acquired_s={index/p.fs:.6f} "
                              f"first_{n}_PSD_V2_per_Hz="
                              + ",".join(f"{float(x):.9g}" for x in vals))
                    print(f"# {mode}: {nwin} ordered 1-s windows, {nbin} bins/window; "
                          f"bin_width_Hz={float(p.widths[0]):g}; power PSD not complex FFT")
        except (OSError, ValueError, KeyError, ImportError) as exc:
            errors += 1
            print(f"ERROR {path}: {exc}", file=sys.stderr)
    return int(errors > 0)

if __name__ == "__main__":
    raise SystemExit(main())
