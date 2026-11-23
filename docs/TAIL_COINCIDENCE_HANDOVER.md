# Persistent handover: tail coincidence study

Date:23 November2026. Worktree:/home/mazzitel/HFGW/worktrees/run2-run3-pilot. Branch:run2-run3-pilot-design-20261122. Production/main untouched.

Inventory milestone: selected runs680/1429/1529/1629/1729 all available,1,048,576,000 samples/mode,209.7152s, own ADC±2V and I−iQhardware mapping0/1,2/3,4/5 checked. Raw total49,421,548,426B. Full raw CRC pending except later pilot; gzip headers only checked initially. All four Run3-B PPS sequences contain an approximately2s interval and many4999999-sample intervals. Do not claim precise UTC or calibrated channel delay.

Archived temperatures extracted with original labels, units, quality and time-support flags. MC/cavity/TWPA roles use the documented historical mapping with explicit Run3-wiring qualification; invalid zero Mercury channels excluded from future associations.

Next milestone: implement/test bounded1429 raw timing extraction, check exact T7 totals1368/232/827, save sparse indices/bin summaries/cluster sensitivity and acquisition-domain coincidences. Do not expand to the other raw runs until the PPS/resource checkpoint is reviewed. A small coarse-PSD Gaussian pilot may validate normalization but is not a full-run T7 significance test.

Git policy: stage only this task's reporting/tail_coincidence_study and this handover. Preserve earlier unrelated untracked work. PDFs/PPTX/pilot binary arrays remain local and ignored. No raw, ROOT, secrets or credentials staged. Record actual push outcomes, not inferred success. Inventory commit SHA will be recorded in the subsequent milestone; final commit SHA and push receipt will be reported separately because a commit cannot embed its own hash.

## Completed pilot checkpoint

Inventory milestone committed/pushed as6135b2863cd5493ecf79d0fa4d104a2922e232dc. Run1429 streaming now validated:9.31GB,159.765s,260.4MiB peak RSS; exact T7 totals1368/232/827. All groups singletons over0–10µs non-exceeding gaps. No pairs/triples through10µs; one010–012 pair at100µs (75.2µs separation), shift-control mean1.1. These are acquisition-index diagnostics, not calibrated physical events.

All five archived spectra and temperatures were inspected. TM012−492750.5Hz occupancy208/209 seconds in1429/1529/1629, absent by the same screen in1729. Tail association remains unresolved because no additional raw timing pass was made. Small proper Gaussian null normalization passed; measured covariance and full-run tail null remain future work.

English17-slide PDF/PPTX and lightweight products are under reporting/tail_coincidence_study/. Validation details:validation/REPORT.md and checks.json. Final commit/push SHA is reported in the task response and local ignored validation/git_receipt.json (cannot self-embed in its commit). Local-only files:PDF/PPTX/previews, pilot NPZ, detailed bin CSV, logs and Git receipt. Earlier untracked packages remain untouched.

STOP: no new raw processing of680/1529/1629/1729. Next review timing qualifications and27.98GB remaining Run3-B I/O; then approve/schedule remaining streaming runs. No need for waveform cache. No physical coincidence or causal TWPA inference is justified yet.
