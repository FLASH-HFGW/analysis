"""Read-only storage consolidation report based on Run3 receipts and GFAL evidence."""
import argparse
import json
from pathlib import Path
import re

from autoreco import get_run_number, state_path
from googletool import open_google_sheet, read_all_records
from run3_cycle import BASE, final_url, local
from run3_storage import PRODUCTION, gfal, verify


def load_states(scope):
    root = BASE / scope
    local(root)
    if not root.is_dir():
        return {}
    states = {}
    for folder in root.iterdir():
        if re.fullmatch(r"\d{5,}", folder.name):
            path = state_path(folder)
            local(path)
            if path.is_file():
                states[int(folder.name)] = json.loads(path.read_text())
    return states


def collect_gfal_evidence(input_path, output_path):
    """Worker-only mode, with t1 and a small JSON containing expected receipts."""
    checks = json.loads(input_path.read_text())
    names = [line.strip() for line in gfal("ls", PRODUCTION).splitlines()]
    verified, errors = {}, {}
    for uri, expected in checks.items():
        if not uri.startswith(PRODUCTION + "/"):
            raise ValueError("evidence URL outside canonical Run3 directory")
        try:
            verified[uri] = verify(uri, expected)
        except (ValueError, RuntimeError) as exc:
            errors[uri] = str(exc)
    output_path.write_text(json.dumps(dict(names=names, verified=verified, errors=errors), indent=2))


def consolidation(prod, migration, rows, evidence=None):
    verified = (evidence or {}).get("verified", {})
    errors = (evidence or {}).get("errors", {})
    known = set()
    runs = []
    for run in sorted(set(prod) | set(migration) | set(rows)):
        old_url = final_url(PRODUCTION, run)
        new_url = final_url(PRODUCTION, run, True)
        known.update((old_url.rsplit("/", 1)[-1], new_url.rsplit("/", 1)[-1]))
        original = prod.get(run, {}).get("publication", {})
        current = migration.get(run, prod.get(run, {}))
        publication = current.get("publication", {})
        old = original if original.get("url") == old_url else {}
        val = publication.get("validation", {})
        if publication.get("url") != new_url or current.get("phase") != "verified":
            status = "invalid" if current.get("phase") == "failed" else "root_missing"
        elif publication.get("root_schema") != "3.1":
            status = "incompatible"
        elif (not publication.get("validated") or not all(val.get(key) for key in
              ("bor_bytes", "eor_bytes", "banks", "thermometers", "roundtrip_equal")) or new_url in errors):
            status = "invalid"
        else:
            status = "root_verified"
        row = rows.get(run, {})
        sheet_current = (str(row.get("reco_version", "")).strip() == "3.1"
                         and str(row.get("reco_output_path", "")).strip() == new_url)
        def agrees(url, expected):
            actual = verified.get(url)
            return actual and all(actual.get(k) == expected.get(k)
                                  for k in ("remote_size", "remote_adler32"))
        can_remove = bool(old and status == "root_verified" and sheet_current
                          and val.get("hdf5_reference_datasets_equal", 0) >= 37
                          and agrees(old_url, old) and agrees(new_url, publication))
        runs.append(dict(run=run, status=status, logbook_current=sheet_current,
                         hdf5_candidate=old_url if old else None,
                         hdf5_eligible=can_remove, reclaimable_bytes=old["size"] if can_remove else 0))
    names = (evidence or {}).get("names", [])
    return dict(runs=runs, reclaimable_bytes=sum(row["reclaimable_bytes"] for row in runs),
                extra_or_partial_files=sorted(name for name in names if name not in known),
                remote_evidence_supplied=evidence is not None)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--remote-evidence", type=Path)
    p.add_argument("--export-evidence-requests", type=Path)
    p.add_argument("--worker-evidence", type=Path, help="Worker-only GFAL evidence input")
    args = p.parse_args()
    if args.worker_evidence:
        collect_gfal_evidence(args.worker_evidence, args.output)
        return
    prod, migration = load_states("production"), load_states("root-migration")
    rows = {run: row for row in read_all_records(open_google_sheet())
            if (run := get_run_number(row)) is not None and run >= 1148}
    result = consolidation(prod, migration, rows,
                           json.loads(args.remote_evidence.read_text()) if args.remote_evidence else None)
    args.output.write_text(json.dumps(result, indent=2))
    if args.export_evidence_requests:
        checks = {}
        for state in (*prod.values(), *migration.values()):
            receipt = state.get("publication")
            if receipt and state.get("phase") == "verified":
                checks[receipt["url"]] = receipt
        args.export_evidence_requests.write_text(json.dumps(checks, indent=2))
    print(f"{len(result['runs'])} runs; {result['reclaimable_bytes']} bytes documented for later approval")


if __name__ == "__main__":
    main()
