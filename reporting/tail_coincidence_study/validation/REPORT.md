# Validation and execution checkpoint — 23 November 2026

All checks in checks.json passed, including four clustering/coincidence unit tests. Every 10 ms,100 ms and1 s population reproduces the exact T7 totals and exposure; exposure-weighted RMS agrees with archived full-run ROOT RMS within relative1e-6. Sparse context indices equal the union of the three hit lists. Gap tests include chunk partitioning, inclusive boundaries and rejection of a false triple formed by a pair chain.

Run1429:1,048,576,000 samples/mode,1000 events, EOR and gzip CRC-checked EOF. Exact T7 counts1368/232/827 equal the previously archived totals. For680 only the earlier exact totals37/40/42 are reused: no new raw timing or independent reconstruction is claimed. Other raws have only header-level integrity checks. ADC, I/Q, pump, timestamps and PPS evidence are in inventory.json. Missing temporal products are not replaced with zeros.

Theoretical proper zero-mean Rayleigh marginal expectations per full run are5,900,862.861 atT3,36,856.836 atT5,41.354 atT7. These are expectations, not independent-event significance predictions. Nonzero mean, measured improper quadrature covariance and changing variance require separate null models. The small proper Gaussian pilot validates only variance/coarse PSD/properness; it is not a covariance-matched or full-duration tail test.

All tested T7 groups are singletons for gaps0,2,5,8,10,25,50 non-exceeding samples. No pair or triple through10µs. At100µs one010–012 pair at sample674054353 and674054729 (75.2µs separation), amplitudes0.11513848V and0.03921677V. Corresponding shift control mean1.1, range0–3. The20 shifted trials are descriptive, not an iid null or p-value. Exposure after protected1ms edges:209.7132s. Delay/UTC calibration is absent; no independent physical-event interpretation.

Spectra:209 ordered1s windows/run, three modes, native100Hz products. Local baseline is a201-bin frequency median; occupancy threshold ratio>3 is a descriptive screen. TM012 bin−492750.5Hz has208/209 occupancy for1429/1529/1629 and no comparable structure in1729. No temporal causal link to tails is established. No new filtering or RF corrections.

Temperature values retain timestamps/units/quality flags. Historical sensor mapping is documented but Run3 wiring is not independently verified. Mercury4K is stage thermometry, not the HEMT junction. Within-run ±10s comparisons use approximate header-relative support; no UTC precision claim. Across-run coefficients use only four Run3-B levels or three first differences and have no significance or causal interpretation.

## Measured resources

Raw1429:9,310,514,217 compressed bytes;159.765s wall;266,672KiB maximum RSS (260.4MiB). Process rchar9,317,660,690B;wchar7,416,577B. Kernel read_bytes262,144B is not a network/FUSE transfer measurement. No full waveform retention.

Archived spectral reads:12.720s wall;528,599,951 requested ROOT bytes, including local references; estimated new remote compressed PSD payload316,336,698B. No full ROOT copies. Null pilot1.814s. No aggregate peak memory for all separate processes is inferred from the raw-reader measurement.

All-five raw size49,421,548,426B. Remaining three Run3-B raws27,980,214,936B: roughly8min at the pilot rate, subject to FUSE/cache variability;680 would add12.13GB and roughly3.5min. Streaming reader memory expected below0.5GiB, compact outputs below50MB/run; no compressed raw cache required. No further raw expansion was performed.

## Reporting and repository policy

17 English slides generated with the unchanged tracked v50 renderer, SHA2564a0f88f561b510df7ca961ab320c807c4dd20f4505b5016e9e0196a2a541e4cc. Observable-based three-mode columns, with pair/temperature panels explicitly labeled when columns instead identify pairs/sensors. PPTX text and layout are editable; scientific figure sources are code/report.py plus CSV tables. Earlier reports remain untouched.

PDF/PPTX/previews, pilot NPZ, logs and the4.6MB detailed bin CSV remain local and excluded from Git. Compact per-second bins and sparse timing/cluster/context CSVs are tracked. No raw, ROOT, secrets, HTCondor jobs, production edits, calibration edits or RF gain corrections.

Next action: review PPS/channel-delay limitations and streaming I/O strategy, then approve continuation to the three remaining Run3-B raws. Validate covariance-matched and variance-modulated null pilots before expensive full-run ensembles.
