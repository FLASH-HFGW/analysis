# Resonance-band reference and long-term power analysis — 17 November 2026

The approved toy, its physical inputs, ADC conversion, gain, measured kz response and previous products are unchanged. No MIDAS raw input, stochastic simulation, new physical fit or hardware response is used here. The independent pilot remains the time-domain run-680 reference. Outputs are outside Git under `../analysis-work/Run2/diagnostics/resonance_reference_campaign_v5_20261117/`; earlier development calculations are preserved.

## Reference planes and analytical prediction

The numerical inputs are those frozen by the approved v43 Part I: its `metrics.json` configuration, the physical cavity parameters in `simulation/step6/metrics.json` in the work tree and the per-mode `calibration_reconstruction.json` used by that version. Their checksums are verified against the approved full-run reference ledger. RF amplitude gain is `10^(103.4/20)`; science/calibration LF amplitude ratio is `0.01`; calibration ADC range is ±5 V, science ADC range ±2 V. The measured mode-dependent integrated-tone kz includes the existing readout filtering. **No additional LPF, step-7/8 LF modification or new hardware transfer function is cascaded.**

With `κi = 2π f0/Q0`, `κ2 = κi β2`, `κtot = κi(1+β1+β2)` and `Θ = h f0 / [exp(h f0/kBT)−1]`, the approved complex RMS-equivalent voltage spectra are

```
Sc(f) = R Θ κi κ2 / [(κtot/2)² + (2π(f−fIF,fit))²] × |G_RF × 0.01 kzcal(f)|²
Se(f) = R kB Tn × |G_RF × 0.01 kzcal(f)|²
```

`R=50 Ω`, `Tn=3.955 K`, and the original measured run-680 T15 input remain fixed. The source emits no coherent tone in the scientific noise model. Sum analog aliases `f + j fs`, j=−1,0,+1 exactly as in the approved Part I. kz is zero beyond its measured/interpolated support; this limitation is retained, not extrapolated or repaired.

Both spectra are bilateral, in **ADC V²/Hz**. They describe total complex power `E|z|²`, not a single-quadrature PSD, dBm or input-referred RF watts. The FIR-band powers are

```
Pc,b = ∫ Sc(f) |Hb(f)|² df
Pe,b = ∫ Se(f) |Hb(f)|² df
Ptotal,b = Pc,b + Pe,b
RMSb = sqrt(Ptotal,b); sigma_R,b = sqrt(Ptotal,b/2)
```

Integration uses the actual 2001-tap Kaiser-8.6 FIR, 25 kHz design cutoff, 50 kHz nominal full width, ENBW 47,428.80681855 Hz. The frequencies of both data and reference filters are BOR nominal centers plus seven offsets 0, ±100, ±250 and ±500 kHz. Grid refinement 262,144→524,288 points checks integration convergence. Integrating the complete unfiltered theoretical spectrum reproduces the **approved Part-I** expected powers. A separate receiver/thermal power is retained for every band.

The physical cavity pole remains at its fitted RF frequency. It is **not moved to the BOR filter center**:

| Mode | BOR nominal VNA RF [GHz] | Fitted cavity RF [GHz] | Primary LO [GHz] | Secondary LO [MHz] | BOR digital IF [MHz] | Fitted cavity IF [MHz] |
|---|---:|---:|---:|---:|---:|---:|
| TM010 | 8.737119 | 8.737119 | 8.735869 | 0 (no secondary mixer) | +1.250 | +1.250 |
| TM011 | 8.780842 | 8.780840 | 8.735869 | 43.723 | +1.250 | +1.248 |
| TM012 | 8.841176 | 8.841182 | 8.735869 | 104.057 | +1.250 | +1.256 |

**Archived-reference distinction:** the historical full-run generator contains `af−1e6` for its tiny cavity thermal term; the approved Part-I theoretical arrays instead use the physical `f0−LO1−LO2`. New analytic calculations reproduce the approved Part-I expectation, including its fitted pole position. They do not rerun, overwrite or silently alter that archived full-run toy or the approved Part-II slides. The new comparison is explicitly separate. No electronic normalization is changed to compensate for this distinction.

## Run-680 comparison

| Mode | Data central RMS [mV ADC] | Reference central RMS [mV ADC] | Data/reference RMS | Thermal-only central RMS [µV ADC] | Reference Rayleigh sigma [mV ADC] |
|---|---:|---:|---:|---:|---:|
| TM010 | 3.096471 | 2.640121 | 1.17285 | 4.74960 | 1.866847 |
| TM011 | 1.994989 | 1.301226 | 1.53316 | 2.18557 | 0.920106 |
| TM012 | 1.317534 | 0.806031 | 1.63460 | 1.25617 | 0.569950 |

Thermal fractions of central-band power are only 3.24e−6, 2.82e−6 and 2.43e−6. The electronics therefore dominate; a near-flat resonance-region spectrum does not measure cavity thermal noise. Absolute disagreement is retained.

Data sigma is the **moment-equivalent** scale `sqrt(AC²/2)`, not a new Rayleigh fit or a claim that the observed quadratures are exactly circular Gaussian. Data output means remain in the raw amplitude histograms. The analytic proper Gaussian model predicts Rayleigh amplitudes without additional parameters. Absolute density panels preserve the scale mismatch; shape-only CCDF panels separately use each population's moment scale. No measured amplitude distribution or CCDF is reconstructed from a measured PSD.

The analytic model is continuous Gaussian voltage before quantization. The approved ADC and pilot ADC conversion remain unchanged. As a diagnostic only, the independent-white uniform-quantization estimate `2 LSB²/12 × sum(h²)` is 0.85e−6, 3.48e−6 and 9.07e−6 of reference central-band power. This approximation is documented, **not added or fitted** as an adjustable floor.

The filtered theoretical PSD includes the 20 decimation aliases and the expected symmetric-Hann Welch smoothing. Each PSD is plotted using **its own** stored frequency ordering: archived pilot frequencies are fftshifted; analytical frequencies use numpy native FFT order. Integrating either theoretical output spectrum returns the same band power. Output sampling is **250 kS/s, 4 µs**. Complex ensemble covariance is the inverse Fourier transform of the input PSD times |Hb|², demodulated by the actual center. This is compared with the pilot's existing **uncentered** total correlation on its first-five-SPEC window (1.048576 s input coverage minus startup transient). It is not a full-run covariance measurement or a fitted intrinsic cavity time. Full-run measured amplitude histograms and filtered Welch PSDs retain their separate 209.7152 s scope.

All 21 bands have separate amplitude/PSD/complex-correlation panels and a separate source-breakdown page in the v46 four-page supplement. `run680_reference_band_statistics.csv` gives every RMS/sigma and source fraction in physical units. Results JSON retains all seven RMS/sigma values, separate source powers and central/symmetric ratios. Central/side is central power divided by the arithmetic mean of six noncentral resonance-band powers; symmetric ratio is P(+d)/P(−d). No ratios are forced to one.

## Archived PSD campaign audit: 260 available, 253 usable without coordinate ambiguity

All 260 full-run NPZs exist, each declaring 1000 SPEC, 64 chunks per SPEC, 5 MS/s and 1,048,576 samples per SPEC. Actual spectra have **16,383** points, despite a descriptor saying 16,384. The actual odd-length FFT grid and its Hann ENBW (457.819558 Hz) are used. Coherent-normalized archived power is divided by ENBW Hz and multiplied once by `(ADCpeakBOR/5)²`. Do not treat the archive as a rectangular-band integral or multiply by ENBW again. The source's chunk-mean subtraction differs from the historical v2 whole-run mean subtraction, so archived central bins cannot restore the original DC.

The first audit compared the shared +1 MHz band (new offset −250 kHz) against the historical continuous-filter powers of **all 260 runs**. Initial strict 1% power-error and 0.25-percentage-point endpoint screens were recorded without applying any correction. TM010 failed the 1% screen in runs 692 and 894. This failure is retained in `results.json`; the threshold was not relaxed to certify the full sample.

A second comparison used **all eight nonzero electronic bands in all three modes**. The same seven runs match the known historical signed windows much better after frequency reflection:

**691, 692, 743, 746, 876, 894, 921.**

The diagnostic compares RMS fractional discrepancies across eight powers; a reflection candidate has direct discrepancy >0.08% and reflected discrepancy less than 0.4 times the direct value. All three modes independently identify the same seven runs. For TM010 the eight-band direct discrepancies are ≈0.50–0.58%, versus ≈0.02–0.04% after reflection. This is strong evidence **consistent with** a different IQ sign/frequency orientation, not independent execution metadata proving a conjugation. Historical HDF5 summaries/configuration and the campaign manifest explicitly record iq_sign=−1; the original NPZs do not store IQ sign. Searches did not recover an independent NPZ execution command fixing the seven signs.

**No archived spectrum is reflected, rescaled, repaired or overwritten.** The seven ambiguous NPZ integrals remain only as marked diagnostic candidates. Main resonance trends and all resonance correlations exclude them, leaving **253 included runs with seven explicit gaps**. The historical full-band/DC-centered analyses remain **260 runs**, unchanged. The CSV flags `signed_coordinate_validated`, and HDF5 stores `valid_signed_coordinate_mask`; unmasked arrays alone must not be interpreted as 260 verified positive-frequency measurements.

| Mode | Median shared-window error, included runs [% power] | Maximum absolute error, included runs [% power] | Pearson error vs time |
|---|---:|---:|---:|
| TM010 | −0.00442 | 0.08518 | −0.0164 |
| TM011 | −0.00105 | 0.09417 | +0.0275 |
| TM012 | −0.00003 | 0.10316 | +0.1017 |

There is no substantial systematic clock trend in the shared-window discrepancies. These are empirical estimator checks, not calibrated confidence intervals or proof of equivalent accuracy for every new window. They support descriptive narrow-band powers. Variations of ratios at the per-mille level should not be overinterpreted relative to this estimator difference. Large suspect excursions in the excluded runs are not physical drift results.

## Long-term outputs and statistical interpretation

- Absolute RMS, per-pair relative RMS `100(sqrt(P(r)/P(680))−1)`, measured temperatures and acquisition times are in `campaign_band_powers.csv`.
- All seven bands/mode have Pearson and Spearman power–temperature associations, plus first differences and linear-clock residual controls in `results.json`. No noise–temperature response law is fitted; first differences are between successive included runs, with nonuniform gaps, not time derivatives.
- Central resonance mode-pair correlations and central/symmetric power ratios use 253 paired runs; DC-centered counterparts retain all 260 original runs.
- Raw correlations can reflect common drift. For example, TM010 central power versus T15 has raw Pearson r≈−0.904, clock-controlled r≈−0.615, but successive-run-difference r≈−0.094. Neither the raw nor residual coefficient demonstrates causality. Serial dependence precludes independent-sample significance claims.
- Full-band AC, electronic DC-centered windows and resonance-centered windows are separately named, with their own definitions and populations. Electronic ratios average eight noncentral windows; resonance ratios average six. Common-trend normalization is relegated to the presentation appendix and is not a gain measurement.

The original BOR audit shows unchanged nominal VNA/LO references, not a measured absence of physical resonance drift. T15/T16/T17 physical locations could not be identified in the supplied hardware diagram/datasheets; no cryostat-stage assignment is invented.

## What would require waveform processing or additional provenance?

For the seven ambiguous archived spectra, recover their original execution-sign/channel-mapping provenance or an independently signed spectral product. If unavailable, a **limited coordinate verification** on those runs is sufficient to decide orientation; a full 260-run reconstruction is not implied.

Empirical resonance-band amplitude/phase/increment distributions, time-resolved constellations, exceedance counts and independent-event clustering, coherent mean/phase stability, and selected-window or nonstationary complex correlations require time-domain filtered products. A stationary covariance can be estimated from a PSD, but is not a substitute for these measured time-domain diagnostics. The run-680 pilot already supplies its own amplitude/correlation measurements. No reconstruction of the remaining 259 raw runs was launched.

## Reproduction and validation

```sh
OPENBLAS_NUM_THREADS=1 python examples/resonance_reference_and_campaign.py \
  --output /new/resonance_reference_campaign
OPENBLAS_NUM_THREADS=1 python examples/assess_archived_psd_coordinates.py \
  /new/resonance_reference_campaign --output /new/coordinate_checked_campaign
OPENBLAS_NUM_THREADS=1 python -m unittest discover -s examples/tests -p test_resonance_expectations.py -v
OPENBLAS_NUM_THREADS=1 python reporting/iq_noise_summary_v46/build_slides.py
OPENBLAS_NUM_THREADS=1 python reporting/iq_noise_summary_v46/validate_slides.py
```

Calculation tools refuse existing output directories. Source, approved inputs, PSD archives and old summaries are checksum-ledgered. The v46 builder reads the final `...v5_20261117` coordinate-assessed product. It never launches either scientific calculation, simulation or reconstruction. Only source/tests/documentation enter Git. Numerical files, graphs, PDF/PPTX and prior development outputs stay in the external work tree.
