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
  --analysis KIND      fft (default) or noise (I-iQ, filtered bands, HDF5)
  --reference FILE     Common amplitude reference required for noise
  --resource KIND      noise allocation: cpu (no GPU) or gpu (legacy default)
  --product-version V  noise scientific version: v1 (default) or v2
  --calibration FILE   Explicit normalization JSON, required for v2; frozen at submission
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
PARTITION="${HFGW_SLURM_PARTITION:-}"
QOS="${HFGW_SLURM_QOS:-normal}"
TOKEN_TIME=86400
OIDC_ACCOUNT=flash
MAX_EVENTS=99999999
WALLTIME=''
LOG_DIR="${HFGW_SLURM_LOG_DIR:-$HOME/slurm_logs}"
ANALYSIS_KIND=fft
RESOURCE=gpu
PRODUCT_VERSION=v1
CALIBRATION=''
REFERENCE="${HFGW_NOISE_REFERENCE:-}"
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --account|--partition|--qos|--token-time|--oidc-account|--max-events|--time|--log-dir|--analysis|--reference|--resource|--product-version|--calibration)
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
                --analysis) ANALYSIS_KIND=$2 ;;
                --reference) REFERENCE=$2 ;;
                --resource) RESOURCE=$2 ;;
                --product-version) PRODUCT_VERSION=$2 ;;
                --calibration) CALIBRATION=$2 ;;
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
[[ "$RESOURCE" == cpu || "$RESOURCE" == gpu ]] || { echo 'Resource must be cpu or gpu' >&2; exit 2; }
if [[ "$ANALYSIS_KIND" != noise && "$RESOURCE" != gpu ]]; then
    echo '--resource cpu is supported only for --analysis noise' >&2; exit 2
fi
if [[ -z "$PARTITION" ]]; then
    if [[ "$RESOURCE" == cpu ]]; then PARTITION=CPU; else PARTITION=GPU; fi
fi
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
[[ "$PRODUCT_VERSION" == v1 || "$PRODUCT_VERSION" == v2 ]] || { echo 'Product version must be v1 or v2' >&2; exit 2; }
if [[ "$PRODUCT_VERSION" == v2 ]]; then
    [[ "$ANALYSIS_KIND" == noise && -f "$CALIBRATION" ]] || {
        echo 'v2 requires --analysis noise and --calibration FILE' >&2; exit 2;
    }
elif [[ -n "$CALIBRATION" ]]; then
    echo '--calibration requires --product-version v2' >&2; exit 2
fi
JOB_SCRIPT="$REPO_ROOT/examples/hpc/job.sh"
case "$ANALYSIS_KIND" in
    fft) ;;
    noise)
        export HFGW_NOISE_RESOURCE="$RESOURCE"
        JOB_SCRIPT="$REPO_ROOT/examples/hpc/noise_job.sh"
        [[ -f "$JOB_SCRIPT" && -n "$REFERENCE" && -f "$REFERENCE" ]] || {
            echo 'Noise requires noise_job.sh and --reference FILE' >&2; exit 2;
        }
        export HFGW_NOISE_REFERENCE="$(readlink -f -- "$REFERENCE")"
        export HFGW_NOISE_PRODUCT_VERSION="$PRODUCT_VERSION"
        unset HFGW_NOISE_CALIBRATION
        if [[ "$PRODUCT_VERSION" == v2 ]]; then
            # A queued job must not observe later edits to normalization or sources.
            SNAPSHOT_ROOT="${HFGW_RUNTIME_ROOT:-$HOME/HFGW/analysis-runtime/autoreco/Run2}/noise_submission_sources"
            mkdir -p "$SNAPSHOT_ROOT"
            SNAPSHOT=$(mktemp -d "$SNAPSHOT_ROOT/v2-run${RUN}.XXXXXX")
            for module in analyze_midas_iq_noise.py iq_noise_statistics.py iq_noise_io.py analyze_iq_filtered_bands.py iq_noise_v2.py; do
                cp -- "${HFGW_NOISE_SOURCE_DIR:-$REPO_ROOT/examples}/$module" "$SNAPSHOT/"
            done
            cp -- "$CALIBRATION" "$SNAPSHOT/noise_calibration.json"
            cp -- "$HFGW_NOISE_REFERENCE" "$SNAPSHOT/noise_reference.json"
            export HFGW_NOISE_SOURCE_DIR="$SNAPSHOT"
            export HFGW_NOISE_CALIBRATION="$SNAPSHOT/noise_calibration.json"
            export HFGW_NOISE_REFERENCE="$SNAPSHOT/noise_reference.json"
        fi
        [[ -n "$WALLTIME" ]] || WALLTIME=03:00:00
        ;;
    *) echo 'Analysis must be fft or noise' >&2; exit 2 ;;
esac
[[ -f "$JOB_SCRIPT" ]]
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
if [[ "$ANALYSIS_KIND" == noise ]]; then
    if [[ "$RESOURCE" == gpu ]]; then
        SBATCH_ARGS+=(--gres=gpu:1)
    else
        # CPU requests must not inherit GPU resources from a previous allocation.
        unset SBATCH_GRES SBATCH_GPUS SBATCH_GPUS_PER_NODE SBATCH_GPUS_PER_SOCKET SBATCH_GPUS_PER_TASK SBATCH_TRES_PER_TASK
    fi
fi
JOB_RESPONSE=$(sbatch "${SBATCH_ARGS[@]}" "$JOB_SCRIPT")
JOB_ID=${JOB_RESPONSE%%;*}
[[ $JOB_ID =~ ^[0-9]+$ ]] || { echo 'Unexpected sbatch response; check squeue before retrying' >&2; exit 22; }
printf 'Submitted job %s: run %s, account %s, partition %s, QoS %s\n' "$JOB_ID" "$RUN" "$ACCOUNT" "$PARTITION" "$QOS"
printf 'Monitor: squeue -j %s\n' "$JOB_ID"
printf 'Stdout: %s/JOB_%s.out\nStderr: %s/JOB_%s.err\n' "$LOG_DIR" "$JOB_ID" "$LOG_DIR" "$JOB_ID"
if [[ "$ANALYSIS_KIND" == noise ]]; then
    printf 'Results: %s/JOB_%s/\n' "${HFGW_NOISE_OUTPUT_ROOT:-$HOME/HFGW/analysis-work/Run2/reports/noise_temperature_pilot_v1_20261108/jobs}" "$JOB_ID"
else
    printf 'Results: %s/benchmarks/slurm/JOB_%s/\n' "${HFGW_RUNTIME_ROOT:-$HOME/HFGW/analysis-runtime/autoreco/Run2}" "$JOB_ID"
fi
)
