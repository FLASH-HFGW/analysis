#!/bin/bash
set -euo pipefail

AUTORECO_DIR="/home/mazzitel/HFGW/analysis/autoreco"

exec "$AUTORECO_DIR/run_autoreco_cron.sh" \
  --run-min 408 \
  --input-path flash/data/LNF \
  --output-folder flash/analysis/autoreco/Run2/fft_by_run \
  --analysis-script-dir /home/mazzitel/HFGW/analysis/examples \
  --analysis-script-name analyze_midas_iq_fft_4ms_paral-pipe.py \
  --reco-version 1.0 \
  --iq-sign -1 \
  --max-events 9999999999 \
  --cpus 8
