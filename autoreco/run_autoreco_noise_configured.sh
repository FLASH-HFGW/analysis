#!/bin/bash
set -euo pipefail
AUTORECO_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SELECTION=(--run-range 680 939)
for argument in "$@"; do
    case "$argument" in
        --run|--run=*|--run-range|--run-range=*|--run-min|--run-min=*) SELECTION=();;
    esac
done
exec "$AUTORECO_DIR/run_autoreco_cron.sh" \
    --read-only --ignore-reco-done \
    --analysis-kind noise \
    --output-dir "/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/job_to_submit_noise" \
    --input-path flash/data/LNF \
    --output-folder flash/analysis/autoreco/Run2/noise_by_run \
    --analysis-script-dir "$AUTORECO_DIR/../examples" \
    --analysis-script-name analyze_midas_iq_noise.py \
    --noise-reference "/home/mazzitel/HFGW/analysis-work/Run2/references/noise_reference.json" \
    --reco-version noise-1.0 --iq-sign -1 --cpus 4 \
    "${SELECTION[@]}" "$@"
