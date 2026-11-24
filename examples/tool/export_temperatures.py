#!/usr/bin/env python3
"""Export date (ISO UTC), Unix time and temperatures across inclusive run range."""
import argparse
import csv
from datetime import datetime, timezone
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from iq_products import open_product

COLUMNS = ("run", "root_file", "date_utc", "unix_time", "channel", "unit",
           "temperature", "temperature_K", "valid_positive",
           "within_adc_header_coverage")

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--directory", type=Path, required=True)
    ap.add_argument("--start", type=int, required=True, help="first run inclusive")
    ap.add_argument("--end", type=int, required=True, help="last run inclusive")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--pattern", default="run{run:05d}_iq_v3.1.root")
    ap.add_argument("--valid-only", action="store_true")
    args = ap.parse_args()
    if args.start < 0 or args.start > args.end:
        ap.error("require 0 <= start <= end")
    if not args.directory.is_dir():
        ap.error(f"directory not found: {args.directory}")
    if args.output.exists():
        ap.error(f"refusing to overwrite {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = missing = errors = 0
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        out = csv.DictWriter(stream, fieldnames=COLUMNS)
        out.writeheader()
        for run in range(args.start, args.end + 1):
            path = args.directory / args.pattern.format(run=run)
            if not path.is_file():
                missing += 1
                print(f"WARNING missing {path}", file=sys.stderr)
                continue
            try:
                with open_product(path) as p:
                    if p.run != run:
                        raise ValueError(f"expected run {run}, found {p.run}")
                    for channel, unit, timestamps, values in p.temperatures():
                        for t, value in zip(timestamps, values):
                            t, value = int(t), float(value)
                            valid = math.isfinite(value) and value > 0
                            if args.valid_only and not valid:
                                continue
                            out.writerow(dict(run=run, root_file=str(path),
                                date_utc=datetime.fromtimestamp(t, tz=timezone.utc).isoformat(),
                                unix_time=t, channel=channel, unit=unit,
                                temperature=value,
                                temperature_K=value * (0.001 if unit == "mK" else 1),
                                valid_positive=int(valid),
                                within_adc_header_coverage=int(p.time_start <= t < p.time_stop)))
                            rows += 1
            except (OSError, ValueError, KeyError, ImportError, OverflowError) as exc:
                errors += 1
                print(f"ERROR {path}: {exc}", file=sys.stderr)
    print(f"Wrote {rows} measurements to {args.output}; missing={missing} errors={errors}")
    return int(errors > 0)

if __name__ == "__main__":
    raise SystemExit(main())
