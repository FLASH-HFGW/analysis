# Persistent handover: FLASH tail and coincidence study

## Run 1670 targeted diagnostic · 23 November 2026

- Scientific milestone `3409be09bee5fc085d759a64c0f2139ad5c0ceb5` on the pilot branch. Run 1670 is a separate targeted analysis. Existing Run 1429 and the completed 24-run sample remain intact.
- SHA256-verified ODB and LOSC evidence dates the retune before BOR. On 21 November 2026 UTC the primary RS changed 8,743,664,000 → 8,743,655,000 Hz at 08:21:56, Teledyne CH1 43,331,000 → 43,330,000 Hz at 08:21:59, and CH2 102,179,000 → 102,199,000 Hz at 08:22:02. Run 1670 BOR was 08:24:31. VNA nominal setpoints were written at 08:21:26. The LocalOscill device control path is identifiable from the reference source. Operator versus automatic attribution and the physical application timestamps remain unresolved.
- The validated raw pass produced T7 totals 1244 / 221 / 766 for TM010/TM011/TM012. Full-run moments and 100 ms/1 s exact rates, histograms, sparse tuples and shifted controls are archived. The v50 centered complex ACF and Hann PSD use the first 1.048576 s only.
- The TM012 peak tracked +29 kHz at the boundary, consistent with the image-coordinate displacement. The within-run joint block screen found 18 candidate observable/scan combinations at both block sizes. A common change near 117–119 s lowered mean RMS by about 0.46–0.53% and integrated PSD by about 0.91–1.06%. Neither T7 rate nor the TM012 tracked line ratio passed both exploratory screens. This is a descriptive diagnostic. The archive has a single LOSC snapshot per run and no continuous LO readback.
- One full pass used 9.326 GB and 716.3 s raw wall time. A bounded five-event read supplied the finer prefix constellation. No adjacent raws were processed. Adjacent ROOT data bracket the retune. No full waveforms were retained.
- Separate report under `reporting/tail_coincidence_study/presentation/run1670/` and scientific summary at `reporting/tail_coincidence_study/validation/run1670/REPORT.md`. Open issues are retune attribution, image response versus internal mixing and calibrated channel delays.


## Completed Dataset 2 study · 24 validated Run3-B acquisitions

- Final scientific report commit `93074e1a72a8d1a842267572554b217410c578fb` on `run2-run3-pilot-design-20261122`. All 24 selected runs passed CRC, EOR, raw/ROOT timing, serial, ADC, counts, RMS and sparse clustering checks. The four earlier passes were reused. PPS timing remains acquisition-domain only, with absolute UTC and channel delays unresolved.
- The TM012 leading non-DC feature moved from -492.7505 to -463.7505 kHz at Run 1670, with high occupancy on both sides. The +29 kHz shift matches the image-coordinate prediction under the −9/+20 kHz primary/secondary LO changes. The main-branch fixed-RF prediction is −11 kHz. Source identity, image conversion gain and the separation of independent intensity effects remain unresolved.
- Five TM010–TM011 pairs share exactly the same received sample index in five runs, versus a range of 0–1 under the pooled 1 µs shifted controls. No triples were found. Shared digitizer/readout disturbances and timing calibration require follow-up before physical interpretation.
- Median T7/Gaussian before → after: TM010 12.90 → 12.62, TM011 3.23 → 3.27, TM012 14.86 → 14.57. These are marginal count comparisons on correlated samples. They do not establish retune, line or thermal causation, or independent-event significance.
- The 20-run continuation used 186.47 GB compressed raw, 52.0 min process wall, 49.9 min CPU and 571.4 MiB peak RSS. Scope and transfer-counter limitations are in the validation report.
- Final English deck: `reporting/tail_coincidence_study/presentation/longitudinal_final/`. See `reporting/tail_coincidence_study/validation/LONGITUDINAL_FINAL_REPORT.md` for plots, tables, manifest and method. Earlier reports and Run 1429 products are preserved.
- Next scientific work: test independent LO motion with both sidebands and develop a time-dependent joint correlated-noise null before interpreting tails or coincidences physically.

The following checkpoints are historical.

## Dataset 2 longitudinal initial batch — 23 November 2026

- Active checkpoint: the hourly selection and validated runs 1446, 1463 and 1480 are in the commit that adds this section. Run 1429 was reused without a new raw pass.
- Dataset 2 origin is Run 1429 at 2026-11-20 17:44:07 UTC. The available reconstruction ends with Run 1748 at 2026-11-21 13:05:00 UTC. There are 24 selected runs, including the 1529/1629/1729 controls and Run 1748. Live listings show 314 reconstructed runs and raw-only 1749–1910 beyond the cutoff, plus six ROOT gaps before it.
- Selection, diagnostics, receipts and the separate English PDF/PPTX are documented in `reporting/tail_coincidence_study/validation/LONGITUDINAL_REPORT.md`. The original 17-slide checkpoint remains available. New PDF/PPTX files are under `reporting/tail_coincidence_study/presentation/longitudinal/`.
- The three successful raw passes used 27,946,454,470 compressed bytes and 456.9 s, with 571.4 MiB peak process RSS. The initial interrupted 1446 pass was retried after handling the archived PPS defect. PPS remains qualified for acquisition-domain timing only.
- Remaining batch execution is held for review. Recommended next runs are 1497, 1513, 1529 and 1530. Later science should retain the RF epoch boundary at Run 1670 and use stronger correlated-noise nulls before interpreting statistical significance.

The sections below document the preceding Run 1429 checkpoint.

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
