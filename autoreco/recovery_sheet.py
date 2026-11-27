"""Plan small, guarded updates to the operator-facing recovery view."""
from datetime import datetime, timezone

CONTROL = "auto_reco_release"
COLUMNS = ("auto_reco_status", "auto_reco_error", "auto_reco_next_retry")
MAX_ROWS_PER_CYCLE = 120
GUARDS = ("run", "filename", "events", "rucio_status", "reco_done", "reco_version",
          "reco_requested_version", "reco_output_path", "auto_reco", CONTROL, *COLUMNS)

DISPLAY = {
    "validated": ("completed", ""),
    "waiting_capacity": ("pending", ""),
    "attempt_pending": ("pending", "Existing attempt awaiting scheduler reconciliation"),
    "idle": ("pending", "Submitted to HTCondor and waiting for a worker"),
    "running": ("running", ""),
    "hold": ("blocked", "HTCondor HOLD; review the exact attempt"),
    "raw_unavailable": ("blocked", "Tier-1 input unavailable or not released"),
    "authentication_required": ("authentication_blocked", "HTCondor approval required"),
    "authorization_retry_ready": ("authentication_blocked", "Previous approval failed; bounded retry is ready"),
    "reconstruction_cooldown": ("cooling_down", "Scientific episode exhausted; cooldown in progress"),
    "operator_excluded": ("manually_excluded", "Operator set auto_reco = -2"),
    "below_event_threshold": ("excluded", "Fewer than 1,000 acquired events"),
    "historical_hold": ("blocked", "Historical first admission requires operator release"),
    "requested_version_conflict": ("blocked", "Explicit reconstruction request differs from ROOT v3.1"),
    "logbook_reconciliation_pending": ("blocked", "Validated ROOT awaiting logbook reconciliation"),
    "publication_verification_pending": ("pending", "Publication receipt awaiting verification"),
    "migration_attempt_pending": ("pending", "Existing ROOT migration attempt"),
    "automatic_recovery_exhausted": ("blocked", "Scientific recovery limit reached; operator review required"),
    "submission_recovery_exhausted": ("blocked", "Authorization retry cap reached; operator review required"),
}


def view(disposition, retry_at=None):
    status, explanation = DISPLAY.get(disposition, ("blocked", disposition.replace("_", " ").capitalize()))
    next_retry = datetime.fromtimestamp(retry_at, timezone.utc).isoformat(timespec="seconds") if retry_at else ""
    return status, explanation, next_retry


def text(value):
    return "" if value is None else str(value)


def col_name(number):
    result = ""
    while number:
        number, digit = divmod(number - 1, 26)
        result = chr(65 + digit) + result
    return result


def plan(headers, original, current, observations, retry_times, limit=MAX_ROWS_PER_CYCLE):
    if len(set(headers)) != len(headers) or not {"run", "filename", "auto_reco"}.issubset(headers):
        raise ValueError("Invalid recovery status header")
    missing = [column for column in (*COLUMNS, CONTROL) if column not in headers]
    expanded = [*headers, *missing]
    changes, conflicts = [], []
    for run, (row_number, old) in original.items():
        if str(run) not in observations:
            continue
        live_number, live = current.get(run, (None, {}))
        if (live_number != row_number or any(text(old.get(key)) != text(live.get(key)) for key in GUARDS)):
            conflicts.append(run)
            continue
        values = view(observations[str(run)], retry_times.get(run))
        row_changes = []
        for column, value in zip(COLUMNS, values):
            previous = text(live.get(column))
            if previous != value:
                cell = f"{col_name(expanded.index(column) + 1)}{row_number}"
                row_changes.append(dict(cell=cell, column=column, old=previous, new=value))
        if row_changes:
            changes.append(dict(run=run, cells=row_changes))
    changes.sort(key=lambda row: DISPLAY.get(observations[str(row["run"])], ("blocked", ""))[0]
                 in ("completed", "excluded"))
    return dict(append_headers=[dict(cell=f"{col_name(len(headers)+i+1)}1", value=name)
                                for i, name in enumerate(missing)],
                conflicts=conflicts, proposed_rows=changes, first_batch=changes[:limit],
                deferred_rows=max(0, len(changes)-limit))


def apply(worksheet, preview):
    """Send one sparse RAW batch and never write operator or scientific fields."""
    if preview["append_headers"]:
        raise ValueError("Status headers require a separate operator-approved schema change")
    cells = [cell for row in preview["first_batch"] for cell in row["cells"]]
    if any(cell["column"] not in COLUMNS for cell in cells):
        raise ValueError("Unexpected operator-column update")
    if cells:
        worksheet.batch_update([{"range": cell["cell"], "values": [[cell["new"]]]}
                                for cell in cells], raw=True)
