# v46 — separate full-band, electronic and resonance-region noise

The English presentation has **49 slides**: v45 slides 1–24 preserved exactly; four separate run-680 resonance-region reference comparisons; eighteen revised long-term slides; three statistical-control appendices. Part IV and new hardware transfer functions are not assembled.

The publication is external: `../analysis-work/Run2/reports/iq_noise_summary_v46/iq_noise_summary_v46.{pdf,pptx}`. The four-page `run680_resonance_comparison_supplement.pdf` supplies separate amplitude/PSD/complex-correlation panels for every one of the 21 resonance bands, plus a separate thermal/electronic source-power page. Previous versions and scientific products are retained. The builder does not run simulations, waveform reconstruction or physical fits.

## Slide map and populations

| Slides | Content | Population |
|---|---|---|
| 1–14 | Approved Part I | Exact approved v45/v43 content; no regeneration |
| 15–24 | Approved original Part II | Exact v45 run-680 comparison; no regeneration |
| 25–28 | Additional resonance-region comparison | Full run-680 filtered amplitudes/PSD/powers; first-five-SPEC measured g1 (1.048576 s input); approved Part-I analytic reference |
| 29–31 | Temperatures, full-band AC power, direct temperature/mode correlations | All 260 original run summaries; Pearson and Spearman; time-colored scatter |
| 32 | Digital/RF frequency conventions and both filter banks | Common recorded BOR references; separate fitted physical cavity frequencies |
| 33–35 | Electronic DC-centered absolute baseline, relative evolution, power ratios | Existing nine-band analysis, all 260 runs |
| 36 | Archived-PSD validation and coordinate audit | All 260 PSDs; seven unresolved frequency orientations visibly flagged |
| 37–41 | Resonance-centered RMS, temperature/mode associations and ratios | **253 signed-overlap-compatible runs**; seven explicit gaps, not silently repaired |
| 42 | Temporal stability of the two banks | Historical electronic bank: 260 runs; resonance bank: 253 compatible runs |
| 43–45 | DC, normalized amplitude-shape proxy, local/fixed thresholds | Existing full-band time-domain summaries, all 260 runs; not inferred from PSDs |
| 46 | Long-term findings | Scope distinctions and remaining limitations |
| 47–49 | Clock-controlled scatter and descriptive common trend | Original 260-run full-band tables; statistical controls only, no gain measurement |

The required editorial changes are applied: direct temperature scatter carries Pearson/Spearman and time color without temperature-response fits; raw mode correlations remain in the main section; clock residuals and the common trend are moved to the appendix; full-band CV includes the Rayleigh line `sqrt((4−pi)/pi)=0.5227232`; local/fixed thresholds and sample-versus-independent-event counts are explicit. T15/T16/T17 physical sensor locations were not identified in the supplied hardware documents, so their labels are retained without assigning cryostat stages.

The frequency diagram spans −2.5 to +2.5 MHz, marks electronic zero, both banks and the separate unit-peak cavity Lorentzian. Electronic windows are at 0, ±100, ±250, ±500 and ±1000 kHz; resonance windows use BOR +1.250 MHz plus 0, ±100, ±250 and ±500 kHz. Both have nominal full width 50 kHz and effective FIR ENBW 47.4288068 kHz. The cavity Lorentzian is illustrative, not a physical thermal/electronic power ratio. Thermal noise remains negligible relative to the electronic reference. No filter is changed. Historical central-band powers exclude the removed whole-run input mean; they retain residual LF fluctuations and output means.

## Numerical reference and non-negotiable limitations

Detailed equations, exact RF/LO/IF table, normalization, source separation, RMS/sigma definitions, archive normalization, numerical checks and reproduction commands are in [the calculation README](../../examples/README_resonance_reference_campaign.md).

- The new analytic prediction reproduces the approved **Part-I** expected spectrum and uses its physical fitted cavity poles, with BOR-derived filter centers. The archived full-run generator's distinct fixed-1-MHz thermal term is documented rather than silently changed. Approved slides and numerical products remain untouched.
- Analytic amplitudes are proper-Gaussian/Rayleigh expectations, not fitted data or empirical distributions derived from PSDs. Data sigma is moment-equivalent `sqrt(AC²/2)`. ADC units and source powers remain absolute.
- Filtered data and theory use output 250 kS/s and 4 µs lags; each FFT uses its own saved frequency ordering. Filter-shaped correlations are not cavity decay fits. Stopband PSD ranges and every band are in the supplement; the main PSD panel zooms the passband/transition.
- The seven archives **691, 692, 743, 746, 876, 894, 921** match known signed electronic windows better after reflection in all three modes, but lack independent IQ-sign provenance. Reflection is unproven and **not applied**. They are excluded from resonance trends/correlations; original full-band/DC-centered results stay at 260 runs.
- On the remaining 253 runs the maximum shared-window discrepancy is 0.0852%, 0.0942% and 0.1032% in power. This supports descriptive powers, not arbitrarily precise shape changes. The failed original strict 1% all-archive screen remains recorded; no threshold relaxation or normalization correction is used to conceal it.
- Correlations are associations, not causal or independent-sample significance statements. First-difference/clock-control values are saved separately. There is no temperature-response law fit.
- Long-term resonance amplitude/phase/increment distributions, coherent phase/means, tails and independent events would require filtered waveform products. None is inferred from the campaign PSDs and no remaining raw reconstruction was launched.

## Preservation, rendering and checks

The first 24 PDF pages are joined directly from v45 without rasterization. Optional `pypdf` (installed under `/tmp/v46-pdf-deps`) preserves shared PDF resources and keeps the export compact; a Poppler extraction/join fallback is available. The first 24 native PPTX slides, relationships, notes and their images are retained. Their historical footers/page counters stay unchanged by design. Updated pages use the approved palette: experimental teal, reference purple, thermal cyan/blue, receiver orange, analytic navy. A neutral gray marker identifies coordinate ambiguity.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python reporting/iq_noise_summary_v46/build_slides.py
OPENBLAS_NUM_THREADS=1 python reporting/iq_noise_summary_v46/validate_slides.py
```

The builder reads existing products and the coordinate-assessed calculation under `../analysis-work/Run2/diagnostics/resonance_reference_campaign_v5_20261117/`. It exports PDF, editable PPTX, slide previews/contact sheet, an English slide list/notes, per-page provenance, table-derived statistics and input checksums. Rebuilding only replaces v46 exports; old versions and simulation inputs are never changed.

Validation checks final PDF rendered pixels for all first 24 pages; approved native PPTX parts and related images; page counts; frozen source/input hashes; FIR power source addition; sigma/power identities; numerical integration convergence; theoretical output PSD integrals and normalized complex covariance; 4 µs sampling; and explicit 253-versus-260 provenance. Numerical regression tests cover white-noise FIR energy, known-frequency tone/band identification, fitted physical cavity coordinates and quarantine without mutation.

Only the new calculation/reporting sources, tests and documentation are published in Git. Numerical products and presentation binaries remain in the external work tree. Further hardware modeling and Part IV await scientific review.
