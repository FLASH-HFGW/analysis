#!/usr/bin/env python3
"""Archivia lo stato locale di autoreco offline senza modificare il DB."""

import argparse
import fcntl
import shutil
from datetime import datetime
from pathlib import Path


AUTORECO_DIR = Path(__file__).resolve().parent
DEFAULT_JOBS_DIR = AUTORECO_DIR / "job_to_submit_offline"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resetta run offline archiviandone le directory locali. "
            "Il Google Sheet non viene aperto né modificato."
        )
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--run", type=int, metavar="N")
    selection.add_argument("--run-min", type=int, metavar="N")
    selection.add_argument(
        "--run-range",
        type=int,
        nargs=2,
        metavar=("MIN", "MAX"),
    )
    parser.add_argument(
        "--jobs-dir",
        type=Path,
        default=DEFAULT_JOBS_DIR,
        help=f"directory dei job offline (default: {DEFAULT_JOBS_DIR})",
    )
    args = parser.parse_args()
    if args.run_range and args.run_range[0] > args.run_range[1]:
        parser.error("MIN non può essere maggiore di MAX")
    return args


def selected(run_number: int, args: argparse.Namespace) -> bool:
    if args.run is not None:
        return run_number == args.run
    if args.run_min is not None:
        return run_number >= args.run_min
    return args.run_range[0] <= run_number <= args.run_range[1]


def main() -> None:
    args = parse_args()
    jobs_dir = args.jobs_dir.expanduser().resolve()
    jobs_dir.mkdir(parents=True, exist_ok=True)

    lock_path = jobs_dir / ".autoreco.lock"
    lock_file = lock_path.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(
            "Autoreco offline è attivo: attendere che termini prima del reset."
        )

    run_dirs = sorted(
        path
        for path in jobs_dir.iterdir()
        if path.is_dir()
        and path.name.isdigit()
        and len(path.name) == 5
        and selected(int(path.name), args)
    )
    if not run_dirs:
        print("Nessuno stato offline da resettare per la selezione richiesta.")
        return

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_dir = jobs_dir / "_reset_archive" / timestamp
    archive_dir.mkdir(parents=True)

    for run_dir in run_dirs:
        destination = archive_dir / run_dir.name
        shutil.move(str(run_dir), str(destination))
        print(f"Run {int(run_dir.name)}: archiviato in {destination}")

    print(
        f"Reset offline completato per {len(run_dirs)} run. "
        "Nessuna scrittura effettuata sul Google Sheet."
    )


if __name__ == "__main__":
    main()
