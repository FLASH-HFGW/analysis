#!/bin/bash
set -euo pipefail

AUTORECO_DIR="/home/mazzitel/HFGW/analysis/autoreco"

# Configurazione manuale/offline: modificare qui i parametri desiderati.
# La selezione del run viene passata da riga di comando, per esempio:
#   ./run_autoreco_offline_configured.sh --run 900 --wait
exec "$AUTORECO_DIR/run_autoreco_cron.sh" \
  --read-only \
  --ignore-reco-done \
  --output-dir "$AUTORECO_DIR/job_to_submit_offline" \
  --input-path flash/data/LNF \
  --output-folder flash/analysis/autoreco/Run2/fft_by_1sec \
  --analysis-script-dir /home/mazzitel/HFGW/analysis/examples \
  --analysis-script-name analyze_midas_iq_fft_4ms_paral-pipe.py \
  --reco-version offline \
  --iq-sign -1 \
  --number-chunks 64 \
  --fft-window-seconds 1 \
  --max-events 9999999999 \
  --cpus 8 \
  "$@"
