"""Read the official acquisition logbook and retain only run and timing fields."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from googletool import SHEET_KEY, open_google_sheet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    sheet = open_google_sheet()
    zone = sheet.spreadsheet.fetch_sheet_metadata()["properties"]["timeZone"]
    rows = []
    exclusions = []
    for index, source in enumerate(sheet.get_all_records(), 2):
        match = re.fullmatch(r"run(\d+)\.mid\.gz", str(source.get("filename", "")).strip())
        if not match or int(match[1]) < 680:
            continue
        run = int(match[1])
        try:
            start, end = (int(source[field]) for field in ("start_epoch", "end_epoch"))
            if not 0 < start <= end:
                raise ValueError("Invalid or unfinished epoch range")
            for epoch, field in ((start, "start_date"), (end, "end_date")):
                display = datetime.strptime(source[field], "%a %b %d %H:%M:%S %Y")
                local = datetime.fromtimestamp(epoch, ZoneInfo(zone)).replace(tzinfo=None)
                if display != local:
                    raise ValueError(f"{field} disagrees with epoch under {zone}")
        except (ValueError, TypeError, KeyError) as error:
            exclusions.append(dict(run=run, sheet_row=index, reason=str(error)))
            continue
        rows.append(dict(run=run, sheet_row=index, start_epoch=start, end_epoch=end))
    groups = {}
    for row in rows:
        groups.setdefault(row["run"], []).append(row)
    for run, group in groups.items():
        if len({(r["start_epoch"], r["end_epoch"]) for r in group}) > 1:
            exclusions.append(dict(run=run, sheet_row=[r["sheet_row"] for r in group],
                                   reason="Conflicting duplicate acquisition epochs"))
    excluded_runs = {r["run"] for r in exclusions}
    rows = [group[0] for run, group in groups.items() if run not in excluded_runs]
    rows.sort(key=lambda record: (record["start_epoch"], record["run"]))
    with args.output.open("x") as stream:
        json.dump(dict(spreadsheet=sheet.spreadsheet.title, spreadsheet_id=SHEET_KEY,
                       worksheet=sheet.title, gid=sheet.id, display_timezone=zone,
                       retrieved_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       fields=["start_epoch", "end_epoch"], rows=rows, exclusions=exclusions),
                  stream, indent=2)
        stream.write("\n")
    print(f"{len(rows)} acquisitions; {len(exclusions)} exclusions")


if __name__ == "__main__":
    main()
