#!/usr/bin/env python3
import warnings
warnings.simplefilter("ignore", FutureWarning)

from typing import Dict, Any, Optional, List


# ----------------------------------------------------------------------
# Google Sheet configuration
# ----------------------------------------------------------------------

SERVICE_ACCOUNT_JSON = "/home/mazzitel/.logbook-478712-cffc1d289aa8.json"
SHEET_KEY = "1dBHc4fwQgmx092ohra6Y-ueF_BpOPVk26BNhi5dCRnM"
WORKSHEET_NAME = "log"


# ----------------------------------------------------------------------
# Google Sheet connection
# ----------------------------------------------------------------------

def open_google_sheet():
    """
    Autenticazione tramite service account e apertura del worksheet.
    """
    try:
        import gspread
    except ImportError as exc:
        raise RuntimeError(
            "Il pacchetto 'gspread' non e installato. "
            "Installarlo con: pip install gspread"
        ) from exc

    gc = gspread.service_account(
        filename=SERVICE_ACCOUNT_JSON
    )

    sh = gc.open_by_key(
        SHEET_KEY
    )

    ws = sh.worksheet(
        WORKSHEET_NAME
    )

    return ws


# ----------------------------------------------------------------------
# Header handling
# ----------------------------------------------------------------------

def get_headers(ws) -> List[str]:
    """
    Restituisce gli header presenti nella prima riga.
    """

    return ws.row_values(1)


def find_col(headers: List[str], col_name: str) -> int:
    """
    Restituisce il numero di colonna Google Sheet (1-based).

    Esempio:
        headers = ["run", "filename", "rucio_status"]
        find_col(headers, "filename") -> 2
    """

    try:
        return headers.index(col_name) + 1

    except ValueError:
        raise RuntimeError(
            f"Colonna '{col_name}' non trovata. "
            f"Header presenti: {headers}"
        )


def ensure_column(ws, column_name: str) -> List[str]:
    """
    Aggiunge column_name alla fine degli header se non esiste.

    Se il worksheet non ha abbastanza colonne fisiche,
    espande prima la griglia.

    Restituisce la lista aggiornata degli header.
    """

    headers = get_headers(ws)

    if not headers:
        raise RuntimeError(
            "Il Google Sheet non contiene una riga di header."
        )

    if column_name in headers:
        return headers

    new_col = len(headers) + 1

    print(
        f"Google Sheet: colonna '{column_name}' non presente "
        f"-> aggiunta nella colonna {new_col}"
    )

    # Espansione fisica del worksheet se necessario
    if ws.col_count < new_col:

        print(
            f"Google Sheet: espansione colonne "
            f"da {ws.col_count} a {new_col}"
        )

        ws.resize(
            cols=new_col
        )

    ws.update_cell(
        1,
        new_col,
        column_name
    )

    headers.append(
        column_name
    )

    return headers


# ----------------------------------------------------------------------
# Reading
# ----------------------------------------------------------------------

def read_all_records(ws) -> List[Dict[str, Any]]:
    """
    Legge tutte le righe del worksheet utilizzando
    la prima riga come header.
    """

    return ws.get_all_records()


def build_sheet_index(ws) -> Dict[str, Dict[str, Any]]:
    """
    Costruisce un indice basato sul campo 'filename'.

    Esempio:

        index["run00591.mid.gz"] = {
            "row": 27,
            "rucio_status": 0,
            "local_file": 1,
            "record": {...}
        }

    Il numero di riga è quello reale del Google Sheet.
    """

    records = ws.get_all_records()

    index: Dict[str, Dict[str, Any]] = {}

    for row_number, rec in enumerate(
        records,
        start=2
    ):

        fname = str(
            rec.get("filename", "")
        ).strip()

        if not fname:
            continue

        index[fname] = {
            "row": row_number,
            "rucio_status": rec.get(
                "rucio_status",
                ""
            ),
            "local_file": rec.get(
                "local_file",
                ""
            ),
            "record": rec,
        }

    return index


# ----------------------------------------------------------------------
# Writing
# ----------------------------------------------------------------------

def update_field(
    ws,
    headers: List[str],
    row: int,
    field: str,
    value: Any
) -> None:
    """
    Modifica un singolo campo di una riga.

    Esempio:
        update_field(
            ws,
            headers,
            27,
            "local_file",
            0
        )
    """

    col = find_col(
        headers,
        field
    )

    if field in {"reco_version", "reco_requested_version"}:
        # update_cell usa USER_ENTERED e Google Sheets trasformerebbe
        # automaticamente "1.0" nel numero 1. RAW preserva il tipo stringa.
        from gspread import Cell
        from gspread.utils import ValueInputOption

        ws.update_cells(
            [Cell(row, col, str(value))],
            value_input_option=ValueInputOption.raw,
        )
    else:
        ws.update_cell(
            row,
            col,
            value
        )


def update_fields(
    ws,
    headers: List[str],
    row: int,
    updates: Dict[str, Any]
) -> None:
    """
    Modifica più campi della stessa riga.

    Esempio:

        update_fields(
            ws,
            headers,
            27,
            {
                "rucio_status": 0,
                "local_file": 0
            }
        )
    """

    from gspread import Cell
    from gspread.utils import ValueInputOption

    cells = [
        Cell(
            row,
            find_col(headers, field),
            str(value)
            if field in {"reco_version", "reco_requested_version"}
            else value,
        )
        for field, value in updates.items()
    ]
    ws.update_cells(
        cells,
        value_input_option=ValueInputOption.raw,
    )


# ----------------------------------------------------------------------
# Utility
# ----------------------------------------------------------------------

def parse_rucio_status(raw: Any) -> Optional[int]:
    """
    Converte il contenuto di rucio_status in int.

    Gestisce:
        0
        0.0
        "0"
        "0.0"
        1
        "1"

    Restituisce None se il valore non è interpretabile.
    """

    if raw is None:
        return None

    value = str(raw).strip()

    if value == "":
        return None

    if value.lower() in {
        "nan",
        "none",
        "null",
        "n/a"
    }:
        return None

    try:
        return int(
            float(value)
        )

    except (ValueError, TypeError):
        return None
