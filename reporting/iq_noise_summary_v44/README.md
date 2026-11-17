# v44 — approved Part I, experimental characterization, reference comparison

## Deliverable and scope

Thirty English slides: **14 unchanged Part I + 9 Part II + 7 Part III**. Part IV is deliberately not assembled pending scientific and graphical review. The structure follows the compact index approved in commit `132d888`, with the later source definitions and experimental DC/AC and distribution additions. Part II splits amplitude/IQ and phase/increments into two readable pages.

| Slides | Section | Statistical scope |
|---|---|---|
| 1–14 | Approved Part I | Exact original v43 pages/slides; short source realizations and absolute normalization preserved |
| 15 | Dataset and methodology | 260 complete runs 680–939; 15.1461 acquired hours; 272,629,760,000 complex samples per mode |
| 16–18 | Long-term levels, temperatures, DC/AC and nine bands | 260 full v2 run summaries; before/after DC-removal endpoint comparison explicitly restricted to paired 12-run pilot |
| 19 | Amplitude, quadratures and IQ | Pooled 260-run amplitude; finer IQ/marginal histograms from complete run 680 |
| 20 | Phase and phase increments | Continuous v2 full run 680; absolute angle and lags 0.2/2/20 µs, zero-amplitude endpoints excluded |
| 21 | Rare tails and thresholds | Existing campaign-local and fixed-reference counts/rates; empirical threshold definitions retained |
| 22 | Experimental PSD and complex g1 | Selected 1.048576 s = five continuous SPEC in run 680 |
| 23 | Experimental findings | Campaign findings distinguished from selected-window times |
| 24–26 | Absolute amplitude, distributions, IQ/phase comparison | Existing full-run step 6 toy and complete run 680: 209.7152 s, 1,048,576,000 samples per mode/population |
| 27–29 | PSD, complex g1 and characteristic times | Original matched 1.048576 s window and archived fits; no new fit |
| 30 | Agreements and discrepancies | Scope-qualified quantitative scorecard; unavailable comparisons explicitly identified |

## Preservation of Part I

The builder **does not execute** the v43 generator or simulation. It copies the approved v43 PDF pages using `pdfunite` and appends new native slides to the original PowerPoint. First-fourteen slide XML is asserted byte-identical. Original slide relationships, notes and embedded images are checked by the validator. Their original v43 footer/page counters are intentionally retained; new slides carry v44 and global page numbers 15–30.

Original v43 slide-model entries and preview PNGs are copied unchanged. Original simulation HDF5, PDF/PPTX and all numeric inputs are hashed before and after the build. Scientific curves, parameters, normalization and old reports are read-only inputs. Generated scientific/presentation products remain outside Git.

## Evidence and normalization

The active original full-run reference is:

`../analysis-work/Run2/simulation/toy_ODB_cal5_data2_LF_20261116/`

Its calibration and physical-parameter checksums are required to match those inherited by the approved Part I. RF gain remains 103.4 dB, `kz_science = 0.01 kz_cal`, calibration ADC ±5 V and science ADC ±2 V. No other transfer function, per-mode gain, noise temperature or response correction is introduced. The current full-run histograms and matched covariance/PSD arrays are used; stale old toy arrays copied into historical presentation directories are not substituted.

Experimental long-term ADC moments come from the already corrected `longterm.csv` in the existing DC diagnostic. Although that file is stored under an earlier diagnostic directory, only its experimental per-run columns are used: no step 7 simulation, control, fit or interpretation is introduced. Nominal input-referred columns (including the old nominal 143 dB gain) are not used in presentation plots.

The saved older amplitude summaries are invariant under the later continuity/DC analysis revision. Their amplitude axes use the established factor **0.4 in voltage, 0.16 in squared voltage** to convert the stored ±5 V convention to physical science ±2 V. Counts do not change. Their campaign phase-increment arrays are not used: those omit SPEC-boundary pairs. Instead slide 20 uses full-stream v2 absolute-phase/increment arrays for run 680. The relative-to-first-sample phase histograms are not mixed with absolute angles.

### Quantities and thresholds kept distinct

- Raw RMS: `sqrt(mean|z|²)`; AC RMS: `sqrt(mean|z−mu|²)`; DC²: `|mu|²`. Complex `z=I−iQhardware=I+iQeff`.
- Rayleigh sigma is the existing fitted quadrature-scale parameter, distinct from `std(A)` and AC RMS. A raw-amplitude histogram is not described as a complex-mean-centered histogram.
- Squared-voltage quantities are labelled V² ADC, not inferred RF watts.
- Part II local thresholds use empirical `mean(A)+k std(A)` separately per run. Fixed thresholds use the saved 100-SPEC run-680 pilot baseline, not a new pooled estimate; this baseline is not statistically independent of all campaign data. Campaign Rayleigh expectations are the already saved moment-based sums at those actual thresholds.
- Part III uses the existing fitted-Rayleigh convention `mu_R+k std_R`. Its counts are therefore not silently equated with the empirical local counts in Part II. For k=3/5/7 the analytic probabilities are 0.005627501, 3.514942e−5, 3.943824e−8; expected count at k=7 is about 41.35 per population. Correlated samples do not provide independent-trial detection significances.
- CCDF against `A²/(2 sigma_fit²)` is **shape only**, with each saved sigma explicitly stated. The absolute distributions retain common ADC millivolt axes, and slide 24 preserves the absolute discrepancies.

### Fits and missing observables

Only archived signed-upper-local-maxima fits `C+A exp(−t/tau)` on 0.3–4 µs are used; display remains 0–10 µs. Their R² is computed on the selected maxima, not all covariance samples. The toy TM010 formal tau≈0.035 µs, below the 0.2 µs sampling interval with R²≈0.360, is unresolved and its unreliable fit curve is not displayed. No errors or confidence intervals are invented. Intrinsic cavity amplitude-pole times are separately labelled; different envelope fits from historical files are not mixed into this table.

Existing full-run toy histograms of phase increments at matching lags are unavailable. The presentation states this explicitly; it does not infer increments from a marginal phase distribution. No new full-run centered-amplitude histogram or campaign-wide model covariance is produced. Selected-window results are not promoted to 260-run conclusions.

## Figure conventions

Data teal `#007F86`; toy purple `#7657A6`; thermal cyan/blue `#43a1ed`; electronics orange `#ed812a`; analytic/saved fitted expectations navy `#263952`. Separate mode panels retain identical physical units and axis limits in direct comparisons. Experimental curves with different quantities use solid/dashed/dotted teal. Data/toy complex correlations show all actual 200 ns delays, full scale plus Re ±0.08 and Im ±0.02 nonzero-lag zooms, checked for clipping. The same limits apply to both populations and every mode.

IQ panels retain physical voltage axes and common logarithmic count-density limits for all six data/toy populations; density colors are not a voltage renormalization. One run-680 TM012 sample outside the saved full-IQ rectangle is disclosed. Histogram projections are figure preparation, not new Gaussian fits.

## Build and verification

Use the existing matplotlib/numpy/scipy/h5py/Pillow/python-pptx environment and system `pdfunite`, `pdftoppm`, `pdfinfo`:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python reporting/iq_noise_summary_v44/build_slides.py
OPENBLAS_NUM_THREADS=1 python reporting/iq_noise_summary_v44/validate_slides.py
```

The shared renderer gained optional `page_offset`/`total_pages` arguments with unchanged defaults, only to number the appended pages. No earlier deck is regenerated.

Outputs: `../analysis-work/Run2/reports/iq_noise_summary_v44/iq_noise_summary_v44.pdf` and `.pptx`, plus `slide_model.json`, previews/contact sheet, Markdown, input SHA-256 manifest/validation and slide-by-slide provenance. Intermediate rendered Parts II/III are under `parts_II_III/`. Sources and documentation alone are committed. Original run products, old versions and numerical simulation files are not committed or overwritten.

## Completed review checks

The exported 30-page PDF and 30-slide PowerPoint passed `validate_slides.py`. The first fourteen PDF pages were compared via identical rendered pixels, and all original PowerPoint slide/relationship, note and embedded-media parts were verified byte-identical. The original scientific input checksums, ADC conversion, raw/DC/AC decomposition, amplitude histogram counts, 200 ns lag spacing and real/imaginary zoom bounds passed. Selected new-slide previews and the new-parts contact sheet were visually inspected; table headers and short-figure axis labels were adjusted before final export.

The reference remains below the measured AC RMS by mode-dependent factors: data/prediction ≈1.187, 1.514, 1.634 for TM010/011/012. These discrepancies are reported without gain changes. No laboratory action, reconstruction, fit, stochastic simulation or Part IV assembly was performed.
