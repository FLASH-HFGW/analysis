# Persistent handover: FLASH tail and coincidence study

Session closed: 23 November 2026. Worktree: `/home/mazzitel/HFGW/worktrees/run2-run3-pilot`. Branch: `run2-run3-pilot-design-20261122`. Origin: `https://github.com/FLASH-HFGW/analysis.git`. Main and production were not modified. No scientific computation or raw processing was repeated during session closure.

## Committed milestones and execution state

- Five-run inventory: `6135b2863cd5493ecf79d0fa4d104a2922e232dc`, pushed.
- Scientific streaming/report checkpoint: `30fd84ac09ef1644708e2117041b7b9f0a21c9e3`, pushed and independently confirmed with `git ls-remote`. Before this closure documentation update, HEAD/upstream divergence was 0/0 and all 51 task-package files were tracked without modifications.
- This closure commit changes this handover only. Its final SHA is recorded in the session response and ignored local `reporting/tail_coincidence_study/validation/git_receipt.json`; a commit cannot embed its own SHA.
- Only Run 1429 received a new sequential raw pass. Do not restart it unnecessarily. No new raw passes on 680, 1529, 1629 or 1729; expansion is held at the timing/resource checkpoint.

## Five-run inventory and integrity

Runs 680/1429/1529/1629/1729 are all available: 1,048,576,000 samples per mode, 209.7152 s, 5 MHz, ADC range ±2 V, conversion 4/65535 V/count, complex convention I − iQhardware, channel pairs 0/1, 2/3, 4/5. Archived serial continuity and shared digitizer indices were checked. 680 is the historical no-TWPA reference; the four Run3-B samples have archived pump-on/TWPA configuration (7.891 GHz, pump setting −6.1; do not infer a calibrated physical pump power).

Inventory paths, own-run configurations, full-run moment attributes, original timing and temperature evidence: `reporting/tail_coincidence_study/data/inventory.json` and `tables/inventory.csv`. Raw files: `/home/mazzitel/flash-data/data/LNF/runNNNNN.mid.gz`. ROOT 680/1429 use existing `comparison/root-pilot/inputs/` copies; the other ROOTs are under `/home/mazzitel/flash-data/analysis/autoreco/Run3/` as recorded in inventory.json.

All selected ROOT schemas/metadata and BOR/EOR hashes were checked, and ordered PSD branches were read; this is not a full-file checksum. Only 1429 raw has CRC-checked normal gzip EOF, 1000 events and EOR. Other raws have gzip-header checks only. Never silently substitute runs or promote header integrity to full CRC validation.

## Validated Run 1429 results

- Exact T7 counts TM010/TM011/TM012: **1368 / 232 / 827**, matching prior archived totals. Earlier Run 680 counts **37 / 40 / 42** were reused, not newly reconstructed.
- Frozen v50 thresholds: Tn = σR[√(π/2) + n√((4−π)/2)], applied to uncentered amplitude. Proper zero-mean marginal full-run expectations: T3 5,900,862.861; T5 36,856.836; T7 41.354. These are not independent-event significance estimates.
- All groups are singletons at tested non-exceeding gaps 0, 2, 5, 8, 10, 25, 50 samples (0–10 µs). Default gaps 10/8/8 samples use prior correlation-scale proxies, not proof of independence. One-sample group duration is not a physical pulse duration.
- No double or triple coincidences through 10 µs. At 100 µs: one TM010–TM012 pair, indices 674054353/674054729, separation 75.2 µs, amplitudes 0.11513848/0.03921677 V. Twenty shift controls: corresponding mean 1.1, range 0–3. All triples are zero. Edge-protected exposure 209.7132 s. Peak tuples may share groups; shifts provide descriptive controls, not iid p-values.
- Sparse other-mode instantaneous amplitudes and ±100 µs maxima were retained, with no waveform retention. Their different selections must remain explicit.
- Saved validation: four algorithm tests pass; every 10 ms/100 ms/1 s binning preserves exact totals/exposure and weighted RMS agrees with archived full-run RMS within relative 1e-6. Sparse context indices equal the union of hits. See `validation/checks.json` and `validation/REPORT.md`.

## Spectral persistence and temperature findings

All five runs were screened using 209 ordered complete 1 s PSD windows, native 100 Hz products, 201-bin local median background. TM012 at −492750.5 Hz exceeds local PSD ratio 3 in **208/209 windows** in 1429, 1529 and 1629; mean ratios 3.723/3.697/3.631. No corresponding enhancement by this screen in 680 or 1729. This is a descriptive occupancy screen, not a coherence/significance test. Frequency precision is limited by the archived binning. Association with tails remains unestablished without further temporal extraction. No filtering or RF corrections were applied.

Archived temperatures retain original channel names, timestamps, K/mK units, converted values and validity/support flags in `tables/temperatures.csv`. Historical role mapping: AVS15 cavity, AVS13 TWPA stage, AVS16/17 MC plates; Mercury4 is a 4 K-stage/HEMT-stage proxy, not junction thermometry. Source: `docs/v47/temperature_mapping.md`; Run3 physical wiring continuity is not independently verified. Invalid zero sensors and readings outside header coverage are excluded from associations. Temperature curves, run medians, within-1429 associations and four-Run3-B correlations are saved. Within-run comparisons use approximate ±10 s support; cross-run levels have N=4 and first differences N=3, exclude 680, and carry no significance or causal claim. Tail/cluster-temperature comparison across all four TWPA runs is pending.

## Known timing and null-model limitations

All Run3-B PPS sequences include an approximately 2 s interval and many 4,999,999-sample intervals. Shared received-sample indices support acquisition-domain comparisons; UTC anchoring and inter-channel/group-delay calibration are unavailable. Do not claim absolute UTC or cavity-time coincidence precision. Windows of 1–2 µs are comparable to prior correlation proxies and not validated against channel delay.

A small proper complex Gaussian pilot (24 × 262,144 samples/mode, 1.258 s total) validates coarse PSD, variance and properness with measured mean/ADC quantization. It does not match measured improper I/Q covariance, slow variance evolution, full-duration T7 exposure or joint cross-mode noise. Do not use it to assign full-run tail/cluster/coincidence significance or blame the TWPA.

## Paths, resources and exact next steps

Canonical package: `reporting/tail_coincidence_study/{code,data,tables,figures,presentation,validation}`. Provenance: `manifest.json` (input locations in inventory, hashes of sources/products). Reporting uses unchanged tracked v50 `reporting/slide_deck.py`. English 17-slide deliverables:

- `presentation/iq_noise_summary_tail_coincidence_checkpoint.pdf`
- `presentation/iq_noise_summary_tail_coincidence_checkpoint.pptx`

Measured raw1429 pass: 9,310,514,217 compressed bytes, 159.765 s wall, 266,672 KiB peak RSS (260.4 MiB). Process rchar 9,317,660,690 B; kernel read_bytes is not network/FUSE traffic. Archived PSD reads: 12.720 s, 528,599,951 requested ROOT bytes including local references, estimated 316,336,698 B new remote compressed PSD payload; no complete ROOT transfers. Null pilot: 1.814 s.

All-five raw size: 49,421,548,426 B. Remaining three Run3-B raws: **27,980,214,936 B**, approximately 8 min at the pilot rate, subject to FUSE/cache variability. Optional new 680 pass adds 12,130,819,273 B (approximately 3.5 min) and should occur only if existing products cannot meet the comparison. Expected streaming RSS below 0.5 GiB and compact output below 50 MB/run; no raw cache required.

Remaining tasks, in order:

1. Review PPS interpretation, shared sample origins and any available channel-delay metadata; retain acquisition-domain qualification unless calibrated independently.
2. Review/approve the 27.98 GB expansion strategy before streaming 1529/1629/1729. Use bounded sequential reading, existing own-run thresholds/statistics, discontinuity checks and CRC/EOR validation. Do not silently reuse 1429 threshold fits for another run.
3. Extract the same sparse T7 indices, 10/100/1000 ms summaries, maxima/local RMS, gap-sensitivity groups, other-mode context and shifted coincidence controls. Verify totals/exposures/RMS per run. Reuse 680 products where sufficient.
4. Compare temporal tail activity with persistent spectral structure and qualified thermal coverage; distinguish levels from first differences and variance drift from local anomalies.
5. Validate covariance/pseudo-spectrum-matched, variance-modulated and narrowband Gaussian null pilots before any costly full-duration simulation. Only then assess count/group distributions with correlated-noise controls.
6. Extend observable-oriented English reporting and manifest incrementally; commit/push each completed milestone. No HTCondor, production changes, RF-calibration changes, permanent filtering or PSD corrections.

## Intentionally uncommitted material

The task's scientific code, tests, compact CSV/JSON, lightweight figures, manifest and validation are committed. Local-only ignored products: PDF/PPTX/slide previews and model under `presentation/`, `data/pilot_1429_bins.npz`, `tables/pilot1429_binned_statistics.csv` (4.6 MB), logs, Python bytecode and `validation/git_receipt.json`. Report source is tracked `code/report.py`; no raw/ROOT/binary cache/secrets are staged.

Pre-existing unrelated untracked directories are preserved unchanged: `comparison/`, `docs/run2-run3-pilot/`, `reporting/rayleigh_tail_diagnostics/`, `reporting/run2_run3_pilot/`, `reporting/run3b_longitudinal/`, `reporting/run680_run1429/`. They include prior-session packages and are outside this closure commit; do not claim the entire worktree is clean or stage them wholesale. No tracked changes should remain after the closure commit.
