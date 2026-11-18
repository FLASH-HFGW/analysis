# v50 — Homogeneous noise-model comparison

The first 85 slides reproduce the approved English v49. The appendix compares run 680 with Toy v0, Toy v1 (hybrid H) and Model N, and includes the approved 260-run campaign strain supplement (54525.952 s). Original visible pagination stays on inherited slides. The complete PDF, editable PPTX, figures and numerical products are local under `../analysis-work/Run2/reports/iq_noise_summary_v50/`. The three model-specific figure sets and the four-population panels are indexed by mode, observable and population. No PDF, PPTX, large NPZ or HDF5 is added to Git.

## Matched populations and estimators

All quantitative comparisons use 4000 nonoverlapping blocks of 262144 complex samples per mode and population at 5 MS/s, four blocks per SPEC, with no statistics or episodes crossing block boundaries. Data, H and N are the approved Step 10C aggregates. Toy v0 is reproduced with its archived 103.4 dB RF scale, Valeria-based kz magnitude and amplitude ratio 0.01, Tn = 3.955 K and historical thermal pole at 1 MHz. The original FIR, overlap-save implementation, random prehistory, random seeds and ADC rounding reproduce the original five archived SPECs exactly. The complete unprojected v0 RMS is checked against the historical aggregate. The comparison does not substitute the updated RF gains, thermal poles or folding into v0.

The same post-ADC DFT projection keeps 251659 bins (|IF| ≥ 100 kHz). This removes DC and excludes the uncharacterized LF interval. It is a periodic diagnostic projection of each block. H and N's frozen analog mask remains part of their own synthesis. The FFT statistic is rectangular and bilateral in V²/Hz ADC, and the complex convention is z=I−iQhardware after the common ±2 V, 16-bit ADC conversion. The exact Step 10B/10C FIR centers, guard, decimation and mean removal are reused. All matched ACF curves use the linear N−lag estimator. Historical unmasked figures and fits remain in the original 85 pages and are separately tabulated.

For the time panels only, the first SPEC bank is read and its hash matched to v47. The first 200 samples of the first projected block are shown in all populations. H and N snapshots are reproduced with the first Step 10C draw; v0 uses the exact archived ADC prefix. Traces are independent noise realizations. No pointwise waveform residual is used as an agreement metric.

## Figures and model-evolution metrics

All plots use common binning and units. The all-population and per-model/data overlays use identical axis limits for each mode and observable. The constellation grid shows paired columns at the same panel dimensions and one shared log-probability scale. Absolute axes use physical ADC voltages and common reference bins; shape axes divide by the individual block RMS. Proper Rayleigh and uniform phase are shape references. Numerical inputs are the original Step 10C and reproduced v0 aggregate arrays, block summary tables and snapshot arrays. The source selector for each family is in the local figure index.

The comparison tables retain signed scalar differences, absolute discrepancies, differences divided by the quadrature sum of the 20-SPEC grouped descriptive SEs, and the change of distance relative to v0. The grouped contrast is a scale diagnostic rather than a p-value. H and N have paired random draws and are not independent model trials. The tables use total variation with the outside-bin mass for histograms and normalized PSD, and pointwise RMSE for PSD in ADC units, complex covariance components and complementary spectra. Histogram distances have no sample-IID error bars. Threshold fractions require the original Step 10C population gates. Consecutive sample excursions remain distinct from triggers. At 5 RMS, unreported fractions carry the observed counts only.

The historical v49 slide 23 procedure is applied to all four matched ACFs. It fits C+A exp(−lag/τ) to the local upper maxima of Re g₁ between 0.3–4 µs. Fit quality is R² on the selected maxima. The archive-compatible alternative windows 0.3–3, 0.3–5 and 0.7–4 µs are tabulated in the local fit details. Leave-one-20-SPEC-group-out uncertainty is reported only when all 50 replicates are resolved. Values below the 0.2 µs sample spacing, solutions within 5% of the upper bound, R² < 0.5 and solver failures are flagged. The latter criteria are descriptive safeguards, not inference thresholds. The cavity amplitude decay QL/(πf₀) is separately listed and is not the noise correlation time.

H and N share the RF gain, equal-image-PSD hypothesis, physical noise sources and thermal poles. N determines downconversion independently from nominal component specifications. Image folding and alias attribution are model decompositions and cannot identify contributions in the measured ADC total. Nonproper data, complex electronics, trigger efficiency and phase stability remain unresolved. The campaign sensitivity remains conditional on field, gravitational overlap and the stated coherence assumptions; no exposure increase is applied to individual PBH transients.

## Summary of the measured comparison

The masked full-band aggregate RMS (mV ADC) is **31.728/26.894/26.604/27.229** in TM010, **20.328/13.421/17.383/18.271** in TM011 and **13.453/8.233/10.877/11.660** in TM012, in data/v0/H/N order. H strongly improves absolute power for TM011 and TM012 and slightly worsens it for TM010. N is closest in absolute full-band level for each mode.

The normalized PSD total variation of H versus v0 improves for TM011 (0.0101 vs 0.0159), stays similar for TM010, and worsens for TM012 (0.0144 vs 0.0098). N is less accurate in PSD shape and real ACF despite its closer overall scale. The nearly Rayleigh marginal amplitude is not a check of circularity. Measured joint I/Q and complementary power residuals persist for every proper model.

After the shared projection, v0 and H do not resolve the historical upper-maxima fit in any mode. N returns descriptive times near 0.75–0.76 µs. Run 680 returns 0.357 µs and 1.478 µs in TM010/011; TM012 is near the 100 µs optimization ceiling and is unresolved. The physical cavity amplitude times remain about 1.068, 1.083 and 0.896 µs. This demonstrates the importance of the matched mask and the fit's sensitivity to covariance shape.

## Reproduction

Use a fresh output folder. Dependencies are the MIDAS reader (first SPEC snapshot only), NumPy, SciPy, h5py, Matplotlib, Pillow, python-pptx, pypdf and Poppler.

```bash
OPENBLAS_NUM_THREADS=1 python3 simulation/v50/v0.py ../analysis-work/Run2 /tmp/new-v50-statistics
OPENBLAS_NUM_THREADS=1 python3 simulation/v50/compare.py ../analysis-work/Run2 \
  ~/flash-data/data/LNF/run00680.mid.gz /tmp/new-v50-statistics
python3 reporting/iq_noise_summary_v50/build.py ../analysis-work/Run2 /tmp/new-v50-statistics /path/to/new-v50
```
