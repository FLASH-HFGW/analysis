# Tail clustering and cross-mode coincidence study

Selected runs:680 historical reference;1429/1529/1629/1729 Run3-B. Initial milestone is a five-run metadata/temperature inventory. Only1429 is authorized as the next streaming pilot; expansion is held at the timing/resource checkpoint.

Canonical directories: code, data, figures, tables, presentation, validation. PDFs/PPTX and raw/pilot arrays are local only; compact CSV/JSON, source, tests and selected lightweight PNGs may be committed. No raw, ROOT, credentials or full waveforms in Git. Earlier untracked analysis packages are intentionally not staged by this task.

Integrity scope: selected raw sizes and gzip headers checked; full gzip CRC cannot be certified without a complete pass. ROOT schema, recorded sample counts, serial continuity and BOR/EOR SHA256 are checked. This is not a full-file checksum of the three non-staged remote ROOTs. Missing/incomplete selected runs are not substituted.

Shared received-sample indices permit acquisition-domain comparisons. All Run3-B SPGP intervals contain a near-two-second gap; UTC remains unanchored, and channel/group-delay calibration is unavailable. No independent physical-event or absolute UTC significance claims.

Temperature roles follow docs/v47/temperature_mapping.md where archived channel labels agree. Run3 wiring continuity is not independently established. Zero sensors are invalid;4Kplate is a HEMT-stage proxy, not junction thermometry. Readings outside acquisition-header support remain in the source table but are excluded from associations.

The tracked reporting/slide_deck.py is byte-identical to the v50 renderer. Plots will use observable-oriented panels with three modes side by side. The specific status-meeting-v10 source was not located; that layout convention follows the user's instruction, not a claim to have read an unavailable template.

Completed checkpoint: run1429 streaming extraction, exact-count/RMS validation, gap and coincidence controls, five-run ordered-PSD screen, temperatures and small proper Gaussian pilot. See validation/REPORT.md. Rebuild compact validation with code/validate.py (requires the local detailed-bin CSV), figures/presentation with code/report.py (no raw reads). The inventory and existing_spectra scripts access archived ROOT metadata/PSD only; pilot1429.py is the sole raw reader and should not be rerun unnecessarily. Postprocess uses local detailed bins. A fresh reproduction of those local-only intermediate bins requires the explicitly documented raw pass.
