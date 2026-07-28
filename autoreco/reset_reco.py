#!/usr/bin/env python3
"""Richiede una nuova ricostruzione modificando il Google Sheet."""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

from googletool import (
    ensure_column,
    get_headers,
    open_google_sheet,
    read_all_records,
    update_fields,
)

AUTORECO_DIR = Path(__file__).resolve().parent
JOBS_DIR = AUTORECO_DIR / "job_to_submit"


def parse_integer(raw: Any) -> Optional[int]:
    try:
        return int(float(str(raw).strip()))
    except (TypeError, ValueError):
        return None


def get_run_number(record: Dict[str, Any]) -> Optional[int]:
    return parse_integer(record.get("run"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rimette reco_done a 0 e richiede una versione di reco."
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--run", type=int, metavar="N")
    selection.add_argument(
        "--run-range",
        type=int,
        nargs=2,
        metavar=("MIN", "MAX"),
    )
    parser.add_argument(
        "--reco-version",
        default="1.0",
        metavar="VERSION",
        help="versione richiesta (default: 1.0)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=JOBS_DIR,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    if args.run_range and args.run_range[0] > args.run_range[1]:
        parser.error("MIN non può essere maggiore di MAX")
    if not args.reco_version.strip():
        parser.error("--reco-version non può essere vuota")
    return args


def selected(run_number: int, args: argparse.Namespace) -> bool:
    if args.run is not None:
        return run_number == args.run
    return args.run_range[0] <= run_number <= args.run_range[1]


def archive_terminal_state(output_dir: Path, run_number: int) -> None:
    run_dir = output_dir / f"{run_number:05d}"
    path = run_dir / "job_state.json"
    if not path.is_file():
        return
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise RuntimeError(f"Stato non leggibile: {path}")

    status = state.get("status")
    if status not in ("sheet_updated", "failed"):
        raise RuntimeError(
            f"Run {run_number}: esiste già un job non terminale "
            f"(stato {status}, cluster {state.get('cluster_id')})"
        )
    cluster_id = state.get("cluster_id", "unknown")
    archived = run_dir / f"job_state.reset-{cluster_id}.json"
    path.replace(archived)
    print(f"Run {run_number}: stato precedente archiviato in {archived}")


def main() -> None:
    args = parse_args()
    worksheet = open_google_sheet()
    ensure_column(worksheet, "reco_version")
    headers = ensure_column(worksheet, "reco_requested_version")
    records = read_all_records(worksheet)

    matches = []
    for row_number, record in enumerate(records, start=2):
        run_number = get_run_number(record)
        if run_number is not None and selected(run_number, args):
            matches.append((row_number, run_number))

    if not matches:
        raise RuntimeError("Nessun run corrispondente trovato nel foglio")

    for row_number, run_number in matches:
        archive_terminal_state(args.output_dir.resolve(), run_number)
        update_fields(
            worksheet,
            headers,
            row_number,
            {
                "reco_requested_version": args.reco_version.strip(),
                # reco_done è il commit marker e viene scritto per ultimo.
                "reco_done": 0,
            },
        )
        print(
            f"Run {run_number}: reco_done=0, versione richiesta "
            f"{args.reco_version.strip()}"
        )


if __name__ == "__main__":
    main()
