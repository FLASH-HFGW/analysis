#!/usr/bin/env python3
"""Aggiorna i metadati dei run già ricostruiti nel Google Sheet."""

import argparse
import json
from pathlib import Path

from googletool import (
    ensure_column,
    get_headers,
    open_google_sheet,
    read_all_records,
    find_col,
)

AUTORECO_DIR = Path(__file__).resolve().parent
JOBS_DIR = AUTORECO_DIR / "job_to_submit"
DEFAULT_OUTPUT_PATH = "flash/analysis/autoreco/Run2/fft_by_run"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-min", type=int, default=591)
    parser.add_argument("--reco-version", default="1.0")
    parser.add_argument("--output-folder", default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def completed_runs(run_min: int) -> set[int]:
    result = set()
    for path in JOBS_DIR.glob("*/job_state.json"):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            run_number = int(state["run_number"])
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            continue
        if (
            run_number >= run_min
            and state.get("status") in {"job_succeeded", "sheet_updated"}
        ):
            result.add(run_number)
    return result


def main() -> None:
    args = parse_args()
    version = args.reco_version.strip()
    output_folder = args.output_folder.strip().rstrip("/")
    if not version or not output_folder:
        raise RuntimeError("Versione e cartella di output non possono essere vuote")

    worksheet = open_google_sheet()
    ensure_column(worksheet, "reco_version")
    ensure_column(worksheet, "reco_output_path")
    headers = get_headers(worksheet)
    completed = completed_runs(args.run_min)
    matches = []

    for row_number, record in enumerate(read_all_records(worksheet), start=2):
        try:
            run_number = int(float(str(record.get("run", "")).strip()))
        except ValueError:
            continue
        if run_number in completed:
            matches.append((row_number, run_number))

    if not args.apply:
        print(
            f"Dry run: {len(matches)} righe da aggiornare "
            f"(run {min(completed)}-{max(completed)})."
        )
        return

    from gspread import Cell
    from gspread.utils import ValueInputOption

    version_col = find_col(headers, "reco_version")
    output_col = find_col(headers, "reco_output_path")
    cells = [
        cell
        for row_number, _ in matches
        for cell in (
            Cell(row_number, version_col, version),
            Cell(row_number, output_col, output_folder),
        )
    ]
    worksheet.update_cells(cells, value_input_option=ValueInputOption.raw)

    print(f"Aggiornate {len(matches)} righe.")


if __name__ == "__main__":
    main()
