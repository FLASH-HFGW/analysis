# Tail clustering and cross-mode coincidence study

Selected runs:680 historical reference;1429/1529/1629/1729 Run3-B. Initial milestone is a five-run metadata/temperature inventory. Only1429 is authorized as the next streaming pilot; expansion is held at the timing/resource checkpoint.

Canonical directories: code, data, figures, tables, presentation, validation. PDFs/PPTX and raw/pilot arrays are local only; compact CSV/JSON, source, tests and selected lightweight PNGs may be committed. No raw, ROOT, credentials or full waveforms in Git. Earlier untracked analysis packages are intentionally not staged by this task.

Integrity scope: selected raw sizes and gzip headers checked; full gzip CRC cannot be certified without a complete pass. ROOT schema, recorded sample counts, serial continuity and BOR/EOR SHA256 are checked. This is not a full-file checksum of the three non-staged remote ROOTs. Missing/incomplete selected runs are not substituted.

Shared received-sample indices permit acquisition-domain comparisons. All Run3-B SPGP intervals contain a near-two-second gap; UTC remains unanchored, and channel/group-delay calibration is unavailable. No independent physical-event or absolute UTC significance claims.

Temperature roles follow docs/v47/temperature_mapping.md where archived channel labels agree. Run3 wiring continuity is not independently established. Zero sensors are invalid;4Kplate is a HEMT-stage proxy, not junction thermometry. Readings outside acquisition-header support remain in the source table but are excluded from associations.

The tracked reporting/slide_deck.py is byte-identical to the v50 renderer. Plots will use observable-oriented panels with three modes side by side. The specific status-meeting-v10 source was not located; that layout convention follows the user's instruction, not a claim to have read an unavailable template.

Completed checkpoint: run1429 streaming extraction, exact-count/RMS validation, gap and coincidence controls, five-run ordered-PSD screen, temperatures and small proper Gaussian pilot. See validation/REPORT.md. Rebuild compact validation with code/validate.py (requires the local detailed-bin CSV), figures/presentation with code/report.py (no raw reads). The inventory and existing_spectra scripts access archived ROOT metadata/PSD only; pilot1429.py is the sole raw reader and should not be rerun unnecessarily. Postprocess uses local detailed bins. A fresh reproduction of those local-only intermediate bins requires the explicitly documented raw pass.

## Dataset 2 longitudinal extension

The longitudinal study reuses Run 1429 and writes separate products under
`tables/longitudinal/`, `figures/longitudinal/`, `validation/longitudinal/` and
`presentation/longitudinal/`. See [the longitudinal validation report](validation/LONGITUDINAL_REPORT.md)
for the acquisition-time selection, validation, I/O estimate and results. The original
checkpoint deck and manifest are retained.

From the study's `code/` directory, with NumPy, SciPy, h5py, Uproot, MIDAS, Matplotlib
and python-pptx available:

- `python select_longitudinal.py` cross-checks the live archive listings and selected gzip headers
  against the saved Run3-B B1 inventory at `reporting/run3b_longitudinal/data/inventory.json`.
  The compact candidate and selection tables retain the audited timestamps.
- `python stream_longitudinal.py RUN [RUN ...]` processes an approved batch of at most
  five selected runs sequentially, skipping Run 1429 and runs with a completed receipt.
- `python test_algorithms.py`, `python test_longitudinal.py` and
  `python validate_longitudinal.py` check the saved pilot behavior and the new batch.
- `python report_longitudinal.py` rebuilds the presentation and its manifest from
  saved compact products. The PDF and PPTX remain local under `presentation/longitudinal/`.

The raw and archived ROOT inputs are read through the existing archive mount. No
full waveform, raw cache or new ROOT copy is needed.

## Completed Dataset 2 sample

The complete 24-run analysis, including the Run 1670 retune comparison, is
documented in [the final validation report](validation/LONGITUDINAL_FINAL_REPORT.md).
The compact final tables and figures use the `longitudinal_final/` subdirectories.
The final PDF and PPTX remain local under `presentation/longitudinal_final/`.
Run `code/final_longitudinal.py` followed by `code/report_final_longitudinal.py`
with the dependencies above to rebuild the final report from the saved tables.
The earlier longitudinal manifest belongs to the initial scientific checkpoint
`fc07e65b`, where its initial coverage statuses and cumulative validation are pinned.

## Run 1670 targeted diagnostic

The [Run 1670 scientific report](validation/run1670/REPORT.md), compact tables,
figures and manifest document the retune timing and separately validated raw pass.
The PDF and PPTX are local under `presentation/run1670/`. Rebuild from the
completed compact outputs with `code/validate1670.py`, `code/change1670.py`
and `code/report1670.py`. The earlier complete longitudinal manifest refers
to the longitudinal checkpoint at `d81a13c`. Its outputs and selection are
retained. The shared reader's optional observers preserve its default behavior.
