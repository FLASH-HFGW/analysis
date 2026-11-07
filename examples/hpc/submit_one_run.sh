#!/bin/bash
# Submit from the login node. The subshell also isolates accidental `source` use.
(
set -euo pipefail
set +x

usage() {
    cat <<'HELP'
Usage: submit_one_run.sh RUN [options]

  --account NAME       SLURM account (default: HFGW_SLURM_ACCOUNT or cygno)
  --partition NAME     SLURM partition (default: HFGW_SLURM_PARTITION or GPU)
  --qos NAME           SLURM QoS (default: HFGW_SLURM_QOS or normal)
  --token-time SECONDS  Minimum remaining token lifetime (default: 86400)
  --oidc-account NAME  oidc-agent account (default: flash)
  --max-events N       Maximum SPEC events (default: 99999999, effectively full run)
  --time LIMIT         SLURM walltime override (otherwise job.sh's 01:00:00)
  --log-dir DIR        SLURM stdout/stderr directory (default: $HOME/slurm_logs)
  -h, --help           Show this help

Examples:
  bash examples/hpc/submit_one_run.sh 680
  bash examples/hpc/submit_one_run.sh 680 --time 02:00:00 --token-time 86400
  bash examples/hpc/submit_one_run.sh 388 --max-events 100

The caller's BEARER_TOKEN is unchanged. No token is printed or stored in a file.
HELP
}

RUN=''
ACCOUNT="${HFGW_SLURM_ACCOUNT:-cygno}"
PARTITION="${HFGW_SLURM_PARTITION:-GPU}"
QOS="${HFGW_SLURM_QOS:-normal}"
TOKEN_TIME=86400
OIDC_ACCOUNT=flash
MAX_EVENTS=99999999
WALLTIME=''
LOG_DIR="${HFGW_SLURM_LOG_DIR:-$HOME/slurm_logs}"
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --account|--partition|--qos|--token-time|--oidc-account|--max-events|--time|--log-dir)
            [[ $# -ge 2 && -n $2 ]] || { echo "Missing value for $1" >&2; exit 2; }
            case "$1" in
                --account) ACCOUNT=$2 ;;
                --partition) PARTITION=$2 ;;
                --qos) QOS=$2 ;;
                --token-time) TOKEN_TIME=$2 ;;
                --oidc-account) OIDC_ACCOUNT=$2 ;;
                --max-events) MAX_EVENTS=$2 ;;
                --time) WALLTIME=$2 ;;
                --log-dir) LOG_DIR=$2 ;;
            esac
            shift 2 ;;
        --*) echo "Unknown option: $1" >&2; exit 2 ;;
        *) [[ -z $RUN ]] || { echo 'Specify exactly one run' >&2; exit 2; }; RUN=$1; shift ;;
    esac
done
[[ $RUN =~ ^[0-9]+$ ]] || { usage >&2; exit 2; }
[[ $TOKEN_TIME =~ ^[0-9]+$ && $MAX_EVENTS =~ ^[0-9]+$ ]] || { echo 'Token time and event limit must be positive integers' >&2; exit 2; }
RUN=$((10#$RUN))
TOKEN_TIME=$((10#$TOKEN_TIME))
MAX_EVENTS=$((10#$MAX_EVENTS))
(( TOKEN_TIME > 0 && MAX_EVENTS > 0 )) || { echo 'Token time and event limit must be positive' >&2; exit 2; }
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
[[ -f "$REPO_ROOT/examples/hpc/job.sh" ]]
command -v oidc-token >/dev/null || { echo 'Load oidc-agent on the login node first' >&2; exit 11; }
command -v sbatch >/dev/null

# --all returns token, issuer and expiration in one response. Separate queries
# could observe different tokens if the shared agent refreshes between calls.
TOKEN_INFO=$(oidc-token --all --time="$TOKEN_TIME" "$OIDC_ACCOUNT")
mapfile -t TOKEN_FIELDS <<< "$TOKEN_INFO"
[[ ${#TOKEN_FIELDS[@]} -eq 3 && -n ${TOKEN_FIELDS[0]} && ${TOKEN_FIELDS[2]} =~ ^[0-9]+$ ]] || {
    echo 'Unexpected oidc-token response; job not submitted' >&2; exit 20;
}
[[ ${TOKEN_FIELDS[0]} != *[[:space:]]* ]] || { echo 'Invalid bearer token response' >&2; exit 20; }
TOKEN_EXPIRES=${TOKEN_FIELDS[2]}
TOKEN_REMAINING=$((TOKEN_EXPIRES - $(date +%s)))
TOKEN_DATE=$(date -d "@$TOKEN_EXPIRES" '+%Y-%m-%d %H:%M:%S %Z')
printf 'Token expiration: %s; remaining: %s seconds\n' "$TOKEN_DATE" "$TOKEN_REMAINING"
# Allow one minute for issuance, transport and local clock differences.
if (( TOKEN_REMAINING <= 0 || TOKEN_REMAINING + 60 < TOKEN_TIME )); then
    echo "The service returned less than the requested $TOKEN_TIME seconds; job not submitted." >&2
    echo 'A longer lifetime cannot be forced locally. Choose --token-time explicitly if a shorter margin is acceptable.' >&2
    exit 21
fi
export BEARER_TOKEN="${TOKEN_FIELDS[0]}"
unset TOKEN_INFO TOKEN_FIELDS
export HFGW_RUN="$RUN" HFGW_MAX_EVENTS="$MAX_EVENTS" HFGW_REPO_ROOT="$REPO_ROOT"
mkdir -p "$LOG_DIR"
LOG_DIR=$(cd -- "$LOG_DIR" && pwd)
SBATCH_ARGS=(--parsable --account="$ACCOUNT" --partition="$PARTITION" --qos="$QOS"
    --export=ALL,BEARER_TOKEN --output="$LOG_DIR/JOB_%j.out" --error="$LOG_DIR/JOB_%j.err")
if [[ -n "$WALLTIME" ]]; then SBATCH_ARGS+=(--time="$WALLTIME"); fi
JOB_RESPONSE=$(sbatch "${SBATCH_ARGS[@]}" "$REPO_ROOT/examples/hpc/job.sh")
JOB_ID=${JOB_RESPONSE%%;*}
[[ $JOB_ID =~ ^[0-9]+$ ]] || { echo 'Unexpected sbatch response; check squeue before retrying' >&2; exit 22; }
printf 'Submitted job %s: run %s, account %s, partition %s, QoS %s\n' "$JOB_ID" "$RUN" "$ACCOUNT" "$PARTITION" "$QOS"
printf 'Monitor: squeue -j %s\n' "$JOB_ID"
printf 'Stdout: %s/JOB_%s.out\nStderr: %s/JOB_%s.err\n' "$LOG_DIR" "$JOB_ID" "$LOG_DIR" "$JOB_ID"
printf 'Results: %s/benchmarks/slurm/JOB_%s/\n' "${HFGW_RUNTIME_ROOT:-$HOME/HFGW/analysis-runtime/autoreco/Run2}" "$JOB_ID"
)
