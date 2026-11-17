# v45 — separate the single-run comparison from long-term stability

The presentation contains **34 slides: 14 unchanged Part I, 10 run-680 comparison slides, 10 long-term experimental slides**. Part IV is not assembled. All earlier versions and scientific products are preserved. Only saved products/tables are read; no MIDAS raw input, stochastic replay, full-run simulation, extended reconstruction, new covariance estimator or physical-response fit is used.

## Statistical population and ordering

| Slides | Section / observable | Population |
|---|---|---|
| 1–14 | Approved Part I | Exact v43 PDF pages and PowerPoint slide/relationship/note/media parts |
| 15 | Run conditions, temperatures and nominal parameters | Run 680 only, 209.7152 s, 1000 SPEC, 1,048,576,000 complex instants per mode |
| 16 | Absolute normalization and noise amplitude | Same run and corresponding existing step-6 reference; raw RMS, AC RMS and Rayleigh sigma distinct |
| 17 | Quadrature distributions and raw IQ | Complete run 680 and existing full-run toy; same IQ axes and log-count limits |
| 18 | Amplitude distributions and Rayleigh CCDF | Complete run 680/reference histograms; absolute axes separate from shape-only CCDF |
| 19 | Phase and phase increments | Complete run 680; full-run toy marginal phase only; comparable toy increments unavailable |
| 20 | Tail counts and thresholds | Complete run 680/reference; existing fitted-Rayleigh threshold convention and counts |
| 21–23 | PSD, complex autocorrelation and characteristic times | Matched selected 1.048576 s windows; original estimators and archived fits |
| 24 | Single-run agreements and discrepancies | Every quantity retains its full-run or selected-window scope; no campaign distribution enters |
| 25 | Campaign temperatures and absolute noise | All 260 full-run summaries, runs 680–939; 15.1461 acquired hours, 272,629,760,000 complex instants per mode |
| 26 | Direct AC-power/temperature scatter | All 260 matched run summaries per mode and sensor, with raw and linear-time-controlled correlations |
| 27 | Noise-level correlations between modes | All 260 matched runs; raw powers and clock-linear residuals plotted separately |
| 28 | Exact frequency-band coordinates | Configuration common to all validated v2 runs; resonance coordinates are nominal, not remeasured per run |
| 29 | Nine-band evolution | 260 runs × 3 modes × 9 bands; original relative-RMS table |
| 30 | Central/side and symmetric-side ratios | All 260 runs; reconstructed measured per-band power, cross-checked against existing central/side table |
| 31 | Shared level trend and residual shape | All 260 runs; existing descriptive common trend, no independent gain inference |
| 32 | DC magnitude, quadratures, phase and power | All 260 run means and AC moments |
| 33 | Normalized amplitude-shape stability | All 260 amplitude-moment summaries; CV is a proxy, not a complete standardized-distribution test |
| 34 | Local/fixed-threshold probability stability | All 260 run-level fractions at k=3/5/7; existing thresholds, with descriptive moment-based Rayleigh expectations |

Every appended slide has an external entry in `slide_provenance.json`, including section, exact run IDs, scope, product citations, estimator notes and figure paths. A complete SHA-256 input ledger is in `validation.json`. Full mathematical derivations/check values and every band's nominal IF/detuning interval are in `derived_from_existing_tables.json`. Long citation text is preserved in notes/the ledger rather than covering the visible footer.

## Frozen reference and Part I preservation

Part I is copied from `../analysis-work/Run2/reports/iq_noise_summary_v43_partI/`. Its plot assets and simulation are not regenerated. The approved PDF pages are joined directly with the new pages using `pdfunite`; native PowerPoint slides are appended to the original deck. Original page counters/footers stay unchanged. First-fourteen slide, relationship, note and media parts are checked byte-identical; PDF pages are checked for identical rendered pixels. Source simulation products and previous reports are protected by input hashes.

Part II uses only the active original reference under `../analysis-work/Run2/simulation/toy_ODB_cal5_data2_LF_20261116/`, with the physical-parameter and calibration checksums used by the approved Part I. RF gain 103.4 dB, `kz_science = 0.01 kz_cal`, calibration ±5 V and science ±2 V remain unchanged. No new response, receiver temperature, gain or noise floor is fitted. `z = I − iQhardware = I + iQeff`; matched complex RMS voltages retain their original definitions. The copied-v44 comparison pages are rearranged without changing curves, fits or normalization.

No aggregate 260-run distribution is used in Part II. Its full-run moments/histograms and the 1.048576 s PSD/covariance window are explicitly distinguished. The full-run phase-increment histogram of the reference toy is unavailable, so increments on slide 19 are labelled data-only. Archived upper-maxima fits stay on 0.3–4 µs, with a 0–10 µs display; the sub-sample/poor TM010 toy fit stays unresolved. No fit is executed.

## Long-term inputs and permitted calculations

Inputs are already extracted long-term tables:

- `simulation/step7/dc_longterm_diagnostic/longterm.csv` in the external work tree: only experimental ADC-domain columns, never its old nominal input-referred gain columns or simulated controls;
- `reports/iq_noise_summary_v17/data/v2_campaign/{dc_ac_temperature_by_run.csv,band_rms_relative_to_run680.csv,trend_diagnostics.csv}` in that work tree;
- saved `noise_global/runs.csv` amplitude moments, thresholds and fractions from the original campaign summaries (amplitude quantities/counts are invariant under the later continuity/DC analysis revision);
- only the existing run-680 HDF5 filter configuration and per-band baseline event moments, not any raw stream or a reread of all 260 HDF5 products.

ADC-domain long-term moments are already corrected according to the physical science ±2 V range. Old stored-band/campaign voltage values use the established 0.4 voltage / 0.16 squared-voltage conversion where needed. CV, ratios, rates and correlations are invariant under that uniform ADC conversion. Noise powers shown as V² or mV² ADC are mean-square voltages, not calibrated RF watts.

### Temperature and inter-mode associations

Direct scatter uses measured full-run AC² against each run's observed median T15/T16/T17, with one point per matched run. Pearson `r` is shown together with `r | time`, defined by projecting **both** quantities off an intercept and linear standardized acquisition clock. The nine temperature coefficients are verified against the existing diagnostic table. This is a statistical drift control, not a physical fit of noise to temperature. No new physical parameters or confidence intervals are introduced.

For example, TM010 versus T15 changes from r≈−0.906 to r|time≈−0.616. A residual correlation does not rule out nonlinear common drift, gain changes or other shared conditions. Inter-mode raw AC-power correlations are ≈0.99894–0.99979; after the same linear-time control they remain ≈0.99883–0.99985. They demonstrate co-variation, not a causal direction or a measured gain. No fixed-temperature physical toy is plotted in Part III.

### Exact frequency bands and resonance coordinates

The actual saved `centers_hz` is `[0,0,0]`. Every mode's filter is centered at:

`f_band = 0 + {−1000,−500,−250,−100,0,+100,+250,+500,+1000} kHz`

in the signed final complex IF of `I−iQhardware`. The nominal full width is **50 kHz**, i.e. nominal interval `f_band ±25 kHz`. The source uses `firwin(2001,25000,fs=5e6,window=('kaiser',8.6))`, with decimation 20, output interval 4 µs, continuous state/oscillator across SPEC and initial transient handling as in the existing analysis. Filters are not brick-wall windows. The stored bilateral ENBW is **47,428.80681855164 Hz**.

The fixed nominal cavity centers in final IF are 1.250/1.248/1.256 MHz for TM010/011/012. Every band detuning is `f_band−f_IF,cavity`, and its nominal detuning bounds are that value ±25 kHz. The DC-centered bands therefore have center detunings −1250/−1248/−1256 kHz; the +1000 kHz bands have center detunings −250/−248/−256 kHz. The highest nominal upper edge, 1.025 MHz, is below all three nominal resonances. **“Central” is an electronic DC reference, not the cavity center.** These resonance/LO coordinates are nominal adopted references; no per-run resonance tracking is available or inferred. All 27 interval records are provided in the external derived JSON.

### Power ratios without suppressing baseline asymmetry

The old per-band table stores `change_pct = 100(RMS_run/RMS_680−1)`, with sample-weighted filtered-event mean squares. Using each measured run-680 band baseline from the saved HDF5:

`P_band(run) = P_band(680) × (1 + change_pct/100)²`.

This is a unit-preserving reconstruction of an already calculated quantity, not a new stochastic/physical analysis. Each reconstructed central power and the arithmetic mean of the eight reconstructed side powers agree with the independently saved complete-campaign central/side table (relative tolerance 1e−10).

- Central/side ratio is `P(0) / mean[P(all eight nonzero bands)]`.
- Symmetric ratios are `P(+d)/P(−d)` for d=100/250/500/1000 kHz.
- Ratios are not forced to unity at run 680. The initial central/side ratios are ≈0.461612, 1.003931, 1.010760; final ratios ≈0.461142, 1.001458, 1.008816.

The shared amplitude trend is the pre-existing median log sideband-amplitude ratio across the three modes relative to run 680. Each target mode contributes to it. Dividing a measured relative level by that descriptive trend is not an independent gain calibration. All physical ADC amplitudes and the absolute calibration remain unchanged.

### Normalized shape and threshold conventions

Long-term shape proxy: `CV=std(A)/mean(A)`. Its max/min spans are ≈0.01190%, 0.01672%, 0.01432% for the three modes. Stable CV does not establish stable full standardized distributions, stationary Gaussian IQ or independent samples. Run-resolved standardized CDF distances are not present in these tables and are not claimed. No pooled distribution is used as a substitute for a time-resolved stability test.

Part III local thresholds use each run's empirical `mean(A)+k std(A)`. Fixed thresholds use the saved 100-SPEC run-680 pilot, which overlaps the campaign. Rayleigh expectations use the existing actual threshold and the moment scale `s_run²=(mean(A)²+std(A)²)/2`, i.e. `exp(−T²/(2s_run²))`; these are descriptive statistical expectations, not a fixed-condition physical toy. Part II instead retains its existing fitted-Rayleigh `mu_R+k std_R` convention. The counts from the two conventions are not mixed. Fractions count samples rather than independent transient events; no independent-trial detection significance or causal attribution is made.

No paired 12-run pilot DC-removal comparison is carried into the full-campaign band page. Any fixed-reference use is labelled as such, rather than promoted to an independent full-campaign measurement.

## Build, outputs and publication

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python reporting/iq_noise_summary_v45/build_slides.py
OPENBLAS_NUM_THREADS=1 python reporting/iq_noise_summary_v45/validate_slides.py
```

Dependencies match v44: numpy/matplotlib/h5py/Pillow/python-pptx and Poppler `pdfunite`, `pdfinfo`, `pdftoppm`. Outputs are external, under `../analysis-work/Run2/reports/iq_noise_summary_v45/`: PDF, editable PPTX, previews, contact sheet, slide model, Markdown, statistical-provenance ledger, input hashes and table-derived diagnostics. Only generator, validation source and documentation are versioned; no experimental data, numerical products or rendered slides enter Git. Prior local changes concerning thesis relocation and older presentation folders are outside this commit's scope.

## Completed verification

The final export passed `validate_slides.py`: 34 PDF pages and 34 PowerPoint slides; first fourteen PDF pages pixel-identical and original PowerPoint slide/relationship/note/media parts byte-identical; Part II provenance restricted to run 680 and Part III to all 260 runs; preserved input checksums and normalization; correct band widths, detunings, ENBW and independent central/side power agreement; temperature-control coefficients reproduced. New-section contact sheets and selected full-size pages were visually reviewed. No previous report or numeric product was overwritten, and Part IV was not assembled.
