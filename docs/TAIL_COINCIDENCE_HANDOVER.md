# Persistent handover: tail coincidence study

Date:23 November2026. Worktree:/home/mazzitel/HFGW/worktrees/run2-run3-pilot. Branch:run2-run3-pilot-design-20261122. Production/main untouched.

Inventory milestone: selected runs680/1429/1529/1629/1729 all available,1,048,576,000 samples/mode,209.7152s, own ADC±2V and I−iQhardware mapping0/1,2/3,4/5 checked. Raw total49,421,548,426B. Full raw CRC pending except later pilot; gzip headers only checked initially. All four Run3-B PPS sequences contain an approximately2s interval and many4999999-sample intervals. Do not claim precise UTC or calibrated channel delay.

Archived temperatures extracted with original labels, units, quality and time-support flags. MC/cavity/TWPA roles use the documented historical mapping with explicit Run3-wiring qualification; invalid zero Mercury channels excluded from future associations.

Next milestone: implement/test bounded1429 raw timing extraction, check exact T7 totals1368/232/827, save sparse indices/bin summaries/cluster sensitivity and acquisition-domain coincidences. Do not expand to the other raw runs until the PPS/resource checkpoint is reviewed. A small coarse-PSD Gaussian pilot may validate normalization but is not a full-run T7 significance test.

Git policy: stage only this task's reporting/tail_coincidence_study and this handover. Preserve earlier unrelated untracked work. PDFs/PPTX/pilot binary arrays remain local and ignored. No raw, ROOT, secrets or credentials staged. Record actual push outcomes, not inferred success. Inventory commit SHA will be recorded in the subsequent milestone; final commit SHA and push receipt will be reported separately because a commit cannot embed its own hash.
