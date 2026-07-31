#!/usr/bin/env python3
import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from googletool import (
    ensure_column,
    get_headers,
    open_google_sheet,
    read_all_records,
)

AUTORECO_DIR = Path(__file__).resolve().parent
JOBS_DIR = AUTORECO_DIR / "job_to_submit"
LOCK_PATH = AUTORECO_DIR / ".autoreco.lock"
STATE_FILENAME = "job_state.json"
DEFAULT_OUTPUT_PATH = "flash/analysis/autoreco/Run2/fft_by_run"
TERMINAL_STATUSES = {"sheet_updated", "read_only_completed"}
SCRIPT_TEMPLATE = r"""#!/bin/bash
set -euo pipefail

# sposatere l'env su CVMFS ##############################
MIDAS_PATH="/cvmfs/mazzitel-personalrepo.infn.it/package/midas/python"
FLLIB_PATH="/cvmfs/mazzitel-personalrepo.infn.it/FLASH/lib/fllib"
PACKAGE_PATH="/cvmfs/mazzitel-personalrepo.infn.it/package/python3.9/site-packages/"
# questa parte serve per usare matplotlibe
export CACHE_BASE="./"

mkdir -p "$CACHE_BASE/matplotlib"
mkdir -p "$CACHE_BASE/xdg-cache"
mkdir -p "$CACHE_BASE/xdg-config"

export MPLCONFIGDIR="$CACHE_BASE/matplotlib"
export XDG_CACHE_HOME="$CACHE_BASE/xdg-cache"
export XDG_CONFIG_HOME="$CACHE_BASE/xdg-config" 
##########################################################
# controllo del worker node
echo "=== CPU before OMP limits ==="
nproc
env -u OMP_NUM_THREADS -u OMP_THREAD_LIMIT nproc
grep -E 'Cpus_allowed|Cpus_allowed_list' /proc/self/status

echo "=== CPU after OMP limits ==="
nproc
env -u OMP_NUM_THREADS -u OMP_THREAD_LIMIT nproc
python3 - <<'PY'
import os
print("os.cpu_count():", os.cpu_count())
print("affinity:", len(os.sched_getaffinity(0)), sorted(os.sched_getaffinity(0)))
PY

echo "=== Linux memory ==="
free -h
cat /proc/meminfo | egrep 'MemTotal|MemAvailable'

echo '--- set packege e authorization token'
export PYTHONPATH="${PACKAGE_PATH}:${MIDAS_PATH}:${FLLIB_PATH}:${PYTHONPATH:-}"
# refresh token befor copy
export BEARER_TOKEN="$(jq -r .access_token "${_CONDOR_CREDS}/t1.use")"
# echo '-- debug print env:'
# env

echo "--------------------------------------"
echo "Arguments: $@"
echo "--------------------------------------"

# $1: input path, $2: run, $3: output path, $4: max events
# $5: analysis script, $6: number of workers, $7: IQ sign
# $8: number of chunks (durata FFT = durata evento / number of chunks)
# $9: durata delle finestre temporali aggiuntive; 0 le disabilita
fname=$(printf 'run%05d.mid.gz' "$2")

echo ">> Start coping ${fname}: `date`"
gfal-copy davs://xfer-archive.cr.cnaf.infn.it:8443/$1/$fname .
ls -hl ./$fname 
echo ">> End coping: `date`"
echo "--------------------------------------"
echo "Python version: `python3 -V`"
echo "run:"

python3 "$5" \
  --path ./ \
  --run "$2" \
  --max-fft-events "$4" \
  --mode-workers "$6" \
  --iq-sign "$7" \
  --number-chunks "$8" \
  --fft-window-seconds "$9"
  
echo "run complited, `date`, list of files:"
ls -lsrth

echo ">> Output coping: `date`"
# refresh token befor copy
export BEARER_TOKEN="$(jq -r .access_token "${_CONDOR_CREDS}/t1.use")"
# se vuoi la directory
for out_npz in run$(printf '%05d' "$2")*.npz; do
  gfal-copy -f -r "$out_npz" "davs://xfer-archive.cr.cnaf.infn.it:8443/$3/$out_npz"
done
echo "--------------------------------------"


rm -f "$fname"
""" + " "
DEFAULT_ANALYSIS_SCRIPT_DIR = AUTORECO_DIR.parent / "examples"
DEFAULT_ANALYSIS_SCRIPT_NAME = "analyze_midas_iq_fft_4ms_paral-pipe.py"


def parse_integer(raw: Any) -> Optional[int]:
    """Converte valori numerici provenienti dal foglio in interi."""
    if raw is None:
        return None

    value = str(raw).strip()
    if not value:
        return None

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def get_run_number(record: Dict[str, Any]) -> Optional[int]:
    """Legge il run dalla colonna run, usando il filename come fallback."""
    run_number = parse_integer(record.get("run"))
    if run_number is not None:
        return run_number

    filename = str(record.get("filename", "")).strip()
    match = re.search(r"run0*(\d+)", filename, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def run_is_selected(run_number: int, args: argparse.Namespace) -> bool:
    if args.run is not None:
        return run_number == args.run
    if args.run_min is not None:
        return run_number >= args.run_min

    run_start, run_end = args.run_range
    return run_start <= run_number <= run_end


def files_to_reconstruct(
    records: Iterable[Dict[str, Any]],
    args: argparse.Namespace,
) -> Iterable[str]:
    for _, filename in runs_to_reconstruct(records, args):
        yield filename


def runs_to_reconstruct(
    records: Iterable[Dict[str, Any]],
    args: argparse.Namespace,
) -> Iterable[Tuple[int, str]]:
    for record in records:
        run_number = get_run_number(record)
        rucio_status = parse_integer(record.get("rucio_status"))
        reco_done = parse_integer(record.get("reco_done"))
        filename = str(record.get("filename", "")).strip()

        if (
            run_number is not None
            and rucio_status == 0
            and (reco_done == 0 or args.ignore_reco_done)
            and filename
            and run_is_selected(run_number, args)
        ):
            yield run_number, filename


def log_rucio_warnings(
    records: Iterable[Dict[str, Any]],
    args: argparse.Namespace,
) -> None:
    """Segnala i run selezionati che non sono disponibili via Rucio."""
    for record in records:
        run_number = get_run_number(record)
        if run_number is None or not run_is_selected(run_number, args):
            continue
        rucio_status = parse_integer(record.get("rucio_status"))
        if rucio_status != 0:
            raw_status = record.get("rucio_status", "")
            filename = str(record.get("filename", "")).strip()
            print(
                f"WARNING: run {run_number} ({filename or 'filename assente'}): "
                f"rucio_status={raw_status!r}; job non sottomesso"
            )


def build_htcondor_files(
    run_numbers: Iterable[int],
    output_dir: Path,
    input_path: str,
    output_path: str,
    max_events: int,
    request_cpus: int,
    analysis_script: Path,
    iq_sign: int,
    number_chunks: int,
    fft_window_seconds: float,
) -> List[Tuple[Path, Path]]:
    """Crea una directory con script e submit file per ciascun run."""
    runs = sorted(set(run_numbers))
    if not runs:
        raise ValueError("nessun run da inserire nel submit file")

    generated_files: List[Tuple[Path, Path]] = []
    for run_number in runs:
        run_dir = output_dir / f"{run_number:05d}"
        run_dir.mkdir(parents=True, exist_ok=True)

        generated_script = run_dir / "script.sh"
        generated_submit = run_dir / "submit.sub"
        analysis_script_path = os.path.relpath(
            analysis_script,
            start=run_dir,
        )
        analysis_script_name = analysis_script.name
        generated_script.write_text(SCRIPT_TEMPLATE, encoding="utf-8")
        generated_script.chmod(0o755)

        submit_content = f"""job_cpus                = {request_cpus}

executable              = script.sh
#
# path, runnumber, output folder, events/stream to average
#
arguments               = {input_path} {run_number} {output_path} {max_events} {analysis_script_name} $(job_cpus) {iq_sign} {number_chunks} {fft_window_seconds}
#
output                  = stdout-$(ClusterId).$(ProcID).txt
error                   = stderr-$(ClusterId).$(ProcID).txt
log                     = output-$(ClusterId).$(ProcID).log
request_cpus            = $(job_cpus)
transfer_executable     = Yes
transfer_input_files    = {analysis_script_path}
should_transfer_files   = Yes
when_to_transfer_output = ON_EXIT
want_io_proxy           = true
use_oauth_services      = t1
t1_oauth_permissions    = profile,email,openid,offline_access
queue
"""
        generated_submit.write_text(submit_content, encoding="utf-8")
        generated_files.append((generated_script, generated_submit))

    return generated_files


def run_command(
    command: List[str],
    cwd: Path,
    show_output: bool = True,
) -> subprocess.CompletedProcess:
    """Esegue un comando HTCondor e mostra il suo output."""
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if show_output and result.stdout:
        print(result.stdout, end="")
    if show_output and result.stderr:
        print(result.stderr, end="")
    return result


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def state_path(run_dir: Path) -> Path:
    return run_dir / STATE_FILENAME


def save_state(run_dir: Path, state: Dict[str, Any]) -> None:
    """Salva lo stato in modo atomico, per poter riprendere dopo un crash."""
    path = state_path(run_dir)
    temporary = path.with_suffix(".tmp")
    state["updated_at"] = utc_now()
    temporary.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_state(run_dir: Path) -> Optional[Dict[str, Any]]:
    path = state_path(run_dir)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Stato non leggibile {path}: {exc}")
        return None


def get_job_status(cluster_id: str, run_dir: Path) -> Optional[int]:
    """Legge lo stato dalla coda; restituisce None se il job non è presente."""
    result = run_command(
        ["condor_q", f"{cluster_id}.0", "-af", "JobStatus"],
        cwd=run_dir,
        show_output=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"condor_q fallito per il cluster {cluster_id} "
            f"(exit code {result.returncode})"
        )
    output = result.stdout.strip()
    if not output:
        return None
    try:
        return int(output.split()[0])
    except ValueError as exc:
        raise RuntimeError(
            f"JobStatus non valido per il cluster {cluster_id}: {output}"
        ) from exc


def discover_existing_jobs(
    selected: Iterable[Tuple[int, str]],
    output_dir: Path,
    input_path: str,
    output_path: str,
) -> None:
    """Recupera job creati da versioni precedenti che non avevano uno state."""
    wanted = {run_number: filename for run_number, filename in selected}
    missing = {
        run_number
        for run_number in wanted
        if not state_path(output_dir / f"{run_number:05d}").is_file()
    }
    if not missing:
        return

    result = run_command(
        ["condor_q", "-af", "ClusterId", "JobStatus", "Args"],
        cwd=output_dir,
        show_output=False,
    )
    if result.returncode != 0:
        print("Impossibile cercare job HTCondor preesistenti.")
        return

    found: Dict[int, Tuple[int, int]] = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        try:
            cluster_id = int(fields[0])
            status = int(fields[1])
            run_number = int(fields[3])
        except ValueError:
            continue
        if (
            run_number not in missing
            or fields[2] != input_path
            or fields[4] != output_path
        ):
            continue
        previous = found.get(run_number)
        if previous is None or cluster_id > previous[0]:
            found[run_number] = (cluster_id, status)

    for run_number, (cluster_id, status) in found.items():
        run_dir = output_dir / f"{run_number:05d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        save_state(
            run_dir,
            {
                "run_number": run_number,
                "filename": wanted[run_number],
                "cluster_id": str(cluster_id),
                "status": "submitted",
                "discovered": True,
                "condor_status": status,
                "target_reco_done": 1,
                "output_path": output_path,
                "created_at": utc_now(),
            },
        )
        print(
            f"Run {run_number}: recuperato cluster preesistente {cluster_id}"
        )


def submit_job(submit_path: Path) -> str:
    """Sottomette un job in spool e restituisce il ClusterId."""
    result = run_command(
        ["condor_submit", "-spool", submit_path.name],
        cwd=submit_path.parent,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"condor_submit fallito per {submit_path} "
            f"(exit code {result.returncode})"
        )

    match = re.search(
        r"submitted\s+to\s+cluster\s+(\d+)",
        result.stdout,
        flags=re.IGNORECASE,
    )
    if not match:
        raise RuntimeError(
            "ClusterId non trovato nell'output di condor_submit"
        )
    return match.group(1)


def wait_for_job(
    cluster_id: str,
    run_dir: Path,
    poll_interval: int,
) -> None:
    """Attende JobStatus=Completed interrogando condor_q."""
    status_names = {
        1: "Idle",
        2: "Running",
        3: "Removing",
        4: "Completed",
        5: "Held",
        6: "Transferring output",
        7: "Suspended",
    }
    last_status: Optional[int] = None

    while True:
        result = run_command(
            [
                "condor_q",
                f"{cluster_id}.0",
                "-af",
                "JobStatus",
                "HoldReasonCode",
                "HoldReason",
            ],
            cwd=run_dir,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"condor_q fallito per il cluster {cluster_id} "
                f"(exit code {result.returncode})"
            )

        output = result.stdout.strip()
        if not output:
            print(
                f"Cluster {cluster_id}: non ancora visibile in condor_q, "
                f"nuovo controllo tra {poll_interval} secondi"
            )
            time.sleep(poll_interval)
            continue

        fields = output.split(maxsplit=2)
        try:
            status = int(fields[0])
        except ValueError as exc:
            raise RuntimeError(
                f"JobStatus non valido per il cluster {cluster_id}: {output}"
            ) from exc

        if status != last_status:
            status_name = status_names.get(status, f"Sconosciuto ({status})")
            print(f"Cluster {cluster_id}: stato {status_name}")
            last_status = status

        if status == 4:
            return
        if status == 5:
            try:
                hold_reason_code = int(fields[1])
            except (IndexError, ValueError):
                hold_reason_code = 0
            hold_reason = fields[2] if len(fields) > 2 else "non disponibile"

            if (
                hold_reason_code == 16
                or "spooling input data files" in hold_reason.lower()
            ):
                print(
                    f"Cluster {cluster_id}: trasferimento degli input "
                    f"in corso, nuovo controllo tra {poll_interval} secondi"
                )
                time.sleep(poll_interval)
                continue

            raise RuntimeError(
                f"cluster {cluster_id} in Held "
                f"(codice {hold_reason_code}): {hold_reason}"
            )
        if status == 3:
            raise RuntimeError(f"cluster {cluster_id} in rimozione")

        time.sleep(poll_interval)


def transfer_job_data(cluster_id: str, run_dir: Path) -> None:
    """Recupera dalla spool i file prodotti dal job concluso."""
    result = run_command(
        ["condor_transfer_data", cluster_id],
        cwd=run_dir,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"condor_transfer_data fallito per il cluster {cluster_id} "
            f"(exit code {result.returncode})"
        )


def job_completed_successfully(cluster_id: str, run_dir: Path) -> bool:
    """Controlla nel log una terminazione normale con exit code zero."""
    log_path = run_dir / f"output-{cluster_id}.0.log"
    if not log_path.is_file():
        print(f"Log HTCondor non trovato: {log_path}")
        return False

    log_content = log_path.read_text(
        encoding="utf-8",
        errors="replace",
    )
    terminated_normally = re.search(
        r"Job terminated\..*?"
        r"Normal termination \(return value 0\)",
        log_content,
        flags=re.DOTALL,
    )
    if not terminated_normally:
        print(
            f"Il cluster {cluster_id} non risulta terminato "
            "normalmente con exit code 0"
        )
        return False
    return True


def stderr_is_empty(cluster_id: str, run_dir: Path) -> bool:
    """Restituisce True solo se lo stderr esiste ed è vuoto."""
    error_path = run_dir / f"stderr-{cluster_id}.0.txt"
    if not error_path.is_file():
        print(f"File di errore non trovato: {error_path}")
        return False
    if error_path.read_text(encoding="utf-8", errors="replace").strip():
        print(f"Il file di errore non è vuoto: {error_path}")
        return False
    return True


def update_reco_done_batch(
    worksheet,
    headers: List[str],
    jobs: List[Tuple[Path, Dict[str, Any]]],
) -> int:
    """Aggiorna tutti i job riusciti con una lettura e scrittura batch."""
    if not jobs:
        return 0

    current_records = read_all_records(worksheet)
    records_by_filename = {
        str(record.get("filename", "")).strip(): (row_number, record)
        for row_number, record in enumerate(current_records, start=2)
    }

    from gspread import Cell
    from gspread.utils import ValueInputOption

    version_col = headers.index("reco_version") + 1
    output_col = headers.index("reco_output_path") + 1
    reco_done_col = headers.index("reco_done") + 1
    cells = []
    ready = []

    for run_dir, state in jobs:
        run_number = int(state["run_number"])
        filename = str(state["filename"])
        matching_record = records_by_filename.get(filename)
        if matching_record is None:
            print(
                f"Run {run_number}: filename {filename} non trovato "
                "nel foglio, aggiornamento rimandato"
            )
            continue

        row_number, current_record = matching_record
        current_value = parse_integer(current_record.get("reco_done"))
        if current_value is None:
            print(
                f"Run {run_number}: valore reco_done non valido, "
                "aggiornamento rimandato"
            )
            continue

        target = state.get("target_reco_done")
        if target is None:
            target = current_value + 1
            state["target_reco_done"] = target
        target = int(target)
        reco_version = (
            str(state.get("reco_version", "1.0")).strip() or "1.0"
        )
        output_path = str(state.get("output_path", "")).strip()

        cells.append(Cell(row_number, version_col, reco_version))
        if output_path:
            cells.append(Cell(row_number, output_col, output_path))
        # reco_done è il commit marker logico e viene aggiunto per ultimo.
        cells.append(Cell(row_number, reco_done_col, target))
        ready.append(
            (
                run_dir,
                state,
                run_number,
                filename,
                target,
                reco_version,
                output_path,
            )
        )

    if not ready:
        return 0

    worksheet.update_cells(cells, value_input_option=ValueInputOption.raw)

    for (
        run_dir,
        state,
        run_number,
        filename,
        target,
        reco_version,
        output_path,
    ) in ready:
        message = (
            f"Run {run_number} ({filename}): reco_done verificato a "
            f"{target}, versione {reco_version}"
        )
        if output_path:
            message += f", output {output_path}"
        print(message)
        state["status"] = "sheet_updated"
        state["completed_at"] = utc_now()
        save_state(run_dir, state)

    return len(ready)


def reconcile_job(
    run_dir: Path,
    state: Dict[str, Any],
) -> bool:
    """Controlla e finalizza un job. True indica uno stato terminale."""
    run_number = int(state["run_number"])
    cluster_id = str(state["cluster_id"])

    if state.get("status") in TERMINAL_STATUSES:
        return True
    if state.get("status") == "job_succeeded":
        return True

    try:
        status = get_job_status(cluster_id, run_dir)
    except RuntimeError as exc:
        print(f"Run {run_number}: {exc}")
        return False

    if status is None:
        # Dopo condor_transfer_data il job può sparire dalla coda. In quel
        # caso i file locali permettono comunque di completare il recupero.
        if not (run_dir / f"output-{cluster_id}.0.log").is_file():
            print(
                f"Run {run_number}: cluster {cluster_id} non trovato "
                "e log locale assente; riproverò alla prossima esecuzione"
            )
            return False
    elif status in (1, 2, 6, 7):
        print(f"Run {run_number}: cluster {cluster_id} ancora attivo ({status})")
        return False
    elif status == 5:
        print(f"Run {run_number}: cluster {cluster_id} in Held")
        state["status"] = "failed"
        save_state(run_dir, state)
        return True
    elif status == 3:
        print(f"Run {run_number}: cluster {cluster_id} in rimozione")
        return False
    elif status != 4:
        print(f"Run {run_number}: stato HTCondor inatteso {status}")
        return False

    if not (run_dir / f"output-{cluster_id}.0.log").is_file():
        try:
            transfer_job_data(cluster_id, run_dir)
        except RuntimeError as exc:
            print(f"Run {run_number}: {exc}; riproverò")
            return False

    if not job_completed_successfully(cluster_id, run_dir):
        state["status"] = "failed"
        save_state(run_dir, state)
        print(f"Run {run_number}: job fallito, reco_done non aggiornato")
        return True

    # Lo stderr viene segnalato, ma l'exit code del job è la condizione
    # autoritativa. Il nuovo script usa set -e per propagare gli errori.
    error_path = run_dir / f"stderr-{cluster_id}.0.txt"
    if error_path.is_file() and error_path.stat().st_size:
        print(f"Run {run_number}: attenzione, stderr non vuoto: {error_path}")

    state["status"] = "job_succeeded"
    save_state(run_dir, state)
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Trova i file da ricostruire e crea i file per HTCondor."
        )
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--run",
        type=int,
        metavar="N",
        help="seleziona un singolo run",
    )
    selection.add_argument(
        "--run-min",
        type=int,
        metavar="N",
        help="seleziona tutti i run maggiori o uguali a N",
    )
    selection.add_argument(
        "--run-range",
        type=int,
        nargs=2,
        metavar=("MIN", "MAX"),
        help="seleziona un intervallo inclusivo di run",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=JOBS_DIR,
        help=f"directory di base dei job (default: {JOBS_DIR})",
    )
    parser.add_argument(
        "--input-path",
        default="flash/data/LNF",
        help="path remoto dei file MIDAS",
    )
    parser.add_argument(
        "--output-path",
        "--output-folder",
        dest="output_path",
        default=DEFAULT_OUTPUT_PATH,
        help=(
            "cartella remota dei risultati "
            f"(default: {DEFAULT_OUTPUT_PATH})"
        ),
    )
    parser.add_argument(
        "--analysis-script-dir",
        type=Path,
        default=DEFAULT_ANALYSIS_SCRIPT_DIR,
        help=(
            "directory locale dello script di analisi "
            f"(default: {DEFAULT_ANALYSIS_SCRIPT_DIR})"
        ),
    )
    parser.add_argument(
        "--analysis-script-name",
        default=DEFAULT_ANALYSIS_SCRIPT_NAME,
        help=(
            "nome dello script di analisi "
            f"(default: {DEFAULT_ANALYSIS_SCRIPT_NAME})"
        ),
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=9_999_999_999,
        help="numero massimo di eventi",
    )
    parser.add_argument(
        "--cpus",
        type=int,
        default=8,
        help="CPU richieste per ciascun job",
    )
    parser.add_argument(
        "--iq-sign",
        type=int,
        choices=(-1, 1),
        default=1,
        help="segno applicato al canale Q nell'analisi IQ (default: +1)",
    )
    parser.add_argument(
        "--number-chunks",
        type=int,
        default=64,
        metavar="N",
        help=(
            "numero di parti in cui dividere l'evento; la durata FFT è "
            "circa 209 ms / N (default: 64, circa 3.27 ms)"
        ),
    )
    parser.add_argument(
        "--fft-window-seconds",
        type=float,
        default=0,
        metavar="SECONDS",
        help=(
            "salva NPZ medi aggiuntivi per finestre temporali consecutive; "
            "0 disabilita la funzione (default: 0)"
        ),
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=30,
        metavar="SECONDS",
        help="intervallo tra i controlli di condor_q (default: 30)",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help=(
            "resta attivo finché i job di questa invocazione terminano; "
            "senza questa opzione esegue una sola passata, adatta a cron"
        ),
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help=(
            "risottomette i run con stato failed, conservando una copia "
            "dello stato del tentativo precedente"
        ),
    )
    parser.add_argument(
        "--reco-version",
        default="1.0",
        metavar="VERSION",
        help=(
            "versione da usare quando reco_requested_version è vuota "
            "(default: 1.0)"
        ),
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help=(
            "non modifica il Google Sheet; adatto a esecuzioni manuali "
            "con configurazione e directory job separate"
        ),
    )
    parser.add_argument(
        "--ignore-reco-done",
        action="store_true",
        help=(
            "seleziona anche run già ricostruiti; consentito soltanto "
            "insieme a --read-only"
        ),
    )
    args = parser.parse_args()

    if args.run_range and args.run_range[0] > args.run_range[1]:
        parser.error("MIN non puo essere maggiore di MAX")
    if args.max_events <= 0:
        parser.error("--max-events deve essere maggiore di zero")
    if args.cpus <= 0:
        parser.error("--cpus deve essere maggiore di zero")
    if (
        args.number_chunks <= 0
        or args.number_chunks & (args.number_chunks - 1)
    ):
        parser.error("--number-chunks deve essere una potenza di 2 positiva")
    if args.fft_window_seconds < 0:
        parser.error("--fft-window-seconds non può essere negativo")
    if args.ignore_reco_done and not args.read_only:
        parser.error("--ignore-reco-done richiede --read-only")
    if args.poll_interval <= 0:
        parser.error("--poll-interval deve essere maggiore di zero")
    if not args.reco_version.strip():
        parser.error("--reco-version non può essere vuota")
    args.output_path = args.output_path.strip().rstrip("/")
    if not args.output_path:
        parser.error("--output-path non può essere vuoto")
    args.analysis_script_name = args.analysis_script_name.strip()
    if (
        not args.analysis_script_name
        or Path(args.analysis_script_name).name != args.analysis_script_name
    ):
        parser.error(
            "--analysis-script-name deve essere un semplice nome di file"
        )
    args.analysis_script_dir = args.analysis_script_dir.expanduser().resolve()
    args.analysis_script = (
        args.analysis_script_dir / args.analysis_script_name
    )
    if not args.analysis_script.is_file():
        parser.error(
            f"script di analisi non trovato: {args.analysis_script}"
        )

    return args


def main() -> None:
    args = parse_args()
    args.output_dir = args.output_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    lock_path = (
        args.output_dir / ".autoreco.lock"
        if args.read_only
        else LOCK_PATH
    )
    lock_file = lock_path.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Un'altra istanza di autoreco è già attiva; esco.")
        return

    worksheet = open_google_sheet()
    if args.read_only:
        print(
            "Modalità read-only: il Google Sheet sarà soltanto letto; "
            "nessuna colonna o cella verrà modificata."
        )
        if args.ignore_reco_done:
            print(
                "Modalità offline: reco_done viene ignorato nella "
                "selezione dei run."
            )
    else:
        ensure_column(worksheet, "reco_version")
        ensure_column(worksheet, "reco_requested_version")
        ensure_column(worksheet, "reco_output_path")
    records = read_all_records(worksheet)
    log_rucio_warnings(records, args)
    selected = list(runs_to_reconstruct(records, args))
    headers = get_headers(worksheet)

    discover_existing_jobs(
        selected,
        args.output_dir,
        args.input_path,
        args.output_path,
    )

    # Prima recupera sempre i job già sottomessi. Questo rende ogni
    # invocazione indipendente dalla sopravvivenza del processo precedente.
    active_runs = set()
    jobs_ready_for_sheet: List[Tuple[Path, Dict[str, Any]]] = []
    for run_number, _ in selected:
        run_dir = args.output_dir / f"{run_number:05d}"
        state = load_state(run_dir)
        if state is None:
            continue
        if state.get("status") in TERMINAL_STATUSES:
            continue
        if state.get("status") == "failed":
            if args.retry_failed:
                cluster_id = str(state.get("cluster_id", "unknown"))
                archived = run_dir / f"job_state.failed-{cluster_id}.json"
                state_path(run_dir).replace(archived)
                print(
                    f"Run {run_number}: tentativo fallito archiviato in "
                    f"{archived}; il run sarà risottomesso"
                )
                continue
            print(
                f"Run {run_number}: job precedente fallito; "
                f"controllare {state_path(run_dir)} o usare --retry-failed"
            )
            active_runs.add(run_number)
            continue
        reconcile_job(run_dir, state)
        refreshed = load_state(run_dir) or state
        if (
            args.read_only
            and refreshed.get("status") == "job_succeeded"
        ):
            refreshed["status"] = "read_only_completed"
            refreshed["completed_at"] = utc_now()
            save_state(run_dir, refreshed)
            print(
                f"Run {run_number}: completato; aggiornamento Google Sheet "
                "saltato (modalità read-only)"
            )
        elif refreshed.get("status") == "job_succeeded":
            jobs_ready_for_sheet.append((run_dir, refreshed))
        if refreshed.get("status") not in TERMINAL_STATUSES:
            active_runs.add(run_number)

    if not args.read_only:
        try:
            update_reco_done_batch(
                worksheet,
                headers,
                jobs_ready_for_sheet,
            )
        except Exception as exc:
            print(
                "Aggiornamento batch del Google Sheet fallito: "
                f"{exc}; riproverò alla prossima esecuzione"
            )

    # Rilegge il foglio: i job appena recuperati potrebbero aver aggiornato
    # reco_done e non devono essere risottomessi.
    records = read_all_records(worksheet)
    selected = [
        item
        for item in runs_to_reconstruct(records, args)
        if item[0] not in active_runs
        and (load_state(args.output_dir / f"{item[0]:05d}") or {}).get(
            "status"
        )
        not in TERMINAL_STATUSES
    ]

    for _, filename in selected:
        print(f"file da ricostruire: {filename}")

    if not selected:
        print("Nessun nuovo file da sottomettere.")
        return

    generated_files = build_htcondor_files(
        run_numbers=(run_number for run_number, _ in selected),
        output_dir=args.output_dir,
        input_path=args.input_path,
        output_path=args.output_path,
        max_events=args.max_events,
        request_cpus=args.cpus,
        analysis_script=args.analysis_script,
        iq_sign=args.iq_sign,
        number_chunks=args.number_chunks,
        fft_window_seconds=args.fft_window_seconds,
    )
    filenames_by_run = {
        run_number: filename
        for record in records
        if (run_number := get_run_number(record)) is not None
        for filename in [str(record.get("filename", "")).strip()]
    }
    submitted_jobs: List[Tuple[int, str, Path, str]] = []
    for script_path, submit_path in generated_files:
        run_number = int(submit_path.parent.name)
        print(f"script HTCondor creato: {script_path}")
        print(f"submit HTCondor creato: {submit_path}")
        filename = filenames_by_run[run_number]
        try:
            cluster_id = submit_job(submit_path)
        except RuntimeError as exc:
            print(f"Run {run_number}: {exc}")
            continue
        print(f"Run {run_number}: sottomesso nel cluster {cluster_id}")
        current_record = next(
            record
            for record in records
            if get_run_number(record) == run_number
        )
        current_reco_done = parse_integer(current_record.get("reco_done"))
        requested_version = str(
            current_record.get("reco_requested_version", "")
        ).strip()
        reco_version = requested_version or args.reco_version.strip()
        save_state(
            submit_path.parent,
            {
                "run_number": run_number,
                "filename": filename,
                "cluster_id": cluster_id,
                "status": "submitted",
                "target_reco_done": (current_reco_done or 0) + 1,
                "reco_version": reco_version,
                "output_path": args.output_path,
                "iq_sign": args.iq_sign,
                "number_chunks": args.number_chunks,
                "fft_window_seconds": args.fft_window_seconds,
                "created_at": utc_now(),
            },
        )
        submitted_jobs.append(
            (
                run_number,
                filename,
                submit_path.parent,
                cluster_id,
            )
        )

    if not args.wait:
        print(
            "Job sottomessi. Una successiva invocazione controllerà "
            "il risultato e aggiornerà reco_done."
        )
        return

    pending = list(submitted_jobs)
    while pending:
        jobs_ready_for_sheet = []
        for run_number, _, run_dir, _ in pending:
            state = load_state(run_dir)
            if state is None:
                continue
            reconcile_job(run_dir, state)
            refreshed = load_state(run_dir) or state
            if (
                args.read_only
                and refreshed.get("status") == "job_succeeded"
            ):
                refreshed["status"] = "read_only_completed"
                refreshed["completed_at"] = utc_now()
                save_state(run_dir, refreshed)
                print(
                    f"Run {run_number}: completato; aggiornamento Google "
                    "Sheet saltato (modalità read-only)"
                )
            elif refreshed.get("status") == "job_succeeded":
                jobs_ready_for_sheet.append((run_dir, refreshed))

        if not args.read_only:
            try:
                update_reco_done_batch(
                    worksheet,
                    headers,
                    jobs_ready_for_sheet,
                )
            except Exception as exc:
                print(
                    "Aggiornamento batch del Google Sheet fallito: "
                    f"{exc}; riproverò"
                )

        next_pending = []
        for item in pending:
            state = load_state(item[2])
            if (
                state is None
                or state.get("status") not in TERMINAL_STATUSES
            ):
                next_pending.append(item)
        pending = next_pending
        if pending:
            time.sleep(args.poll_interval)


if __name__ == "__main__":
    main()
