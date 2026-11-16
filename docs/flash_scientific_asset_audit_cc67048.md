# Asset and slide audit for the FLASH storyboard

Review baseline: cc67048. Planning only; no new deck or numerical scientific result.

## Existing v40 slides: keep, update, move, or replace

| v40 | Existing title | Disposition | New destination | Reason / restriction |
| ---: | --- | --- | --- | --- |
| 1 | Three-mode IQ noise: data and questions | UPDATE | 1–2 | New scope and evidence hierarchy |
| 2 | From MIDAS to verified scientific products | BACKUP | A7 | Provenance pipeline |
| 3 | Code structure: reading, analysis and export | BACKUP | A7/A9 | Code architecture and profiling |
| 4 | Definitions: raw amplitude, DC and AC are different | UPDATE | 19–20 | Fix stale notes; preserve raw versus complex-centred definitions |
| 5 | Frequency bands and DC: what are we selecting? | UPDATE | 6,20,26 | Keep band definitions; do not present an illustrative drawing as measured PSD |
| 6 | Outputs: a small number of aggregate products | BACKUP | A7 | Product organization |
| 7 | Inside the HDF5: data, context and figures together | BACKUP | A7 | HDF5 schema |
| 8 | HPC / HTC: elapsed time and measured CPU use | BACKUP | A8/A9 | Retain benchmark efficiencies; separate wall time and Python function timings |
| 9 | Toy simulation: measured inputs and response | SPLIT / UPDATE | 3,9,16,31–33 | Separate physical model from calibration |
| 10 | Calibration normalization: FET, LF gain and ADC ranges | UPDATE | 17,32,43 | Visible current normalization usable; historical notes elsewhere are not |
| 11 | Toy simulation: updated expected observables | SPLIT / UPDATE | 10–16,31 | Its full-run calibrated predictions belong to PartIII |
| 12 | What these simulations change in the analysis | REPLACE | 16,30,42 | Avoid putting model conclusions before independent data |
| 13 | Amplitude distributions: updated toy and original run680 | UPDATE | 12,24,35–36 | Separate raw Rice and centred Rayleigh; exact threshold audit |
| 14 | Amplitude fits: updated scale versus unchanged data | UPDATE | 34–35 | Separate raw RMS, AC RMS and descriptive Rayleigh RMS |
| 15 | Phase distributions: fresh toy versus original run680 | UPDATE | 13,25,37 | Common absolute phase and population labels |
| 16 | Phase: circular summary and independent fits | BACKUP / UPDATE | 25,37,A2 | Existing descriptive angular fits only; no new fit for agreement |
| 17 | IQ populations: full-run updated toy and run680 | UPDATE | 10,22,24,36 | Common axes; counts independent of marker subsampling |
| 18 | IQ diagnostics: same full-run populations | RETAIN NUMBERS | 11,24,42 | Measured balance and pseudo-covariance remain real discrepancies |
| 19 | Time samples: updated toy and original data | UPDATE | 10,24,35 | Shared time scale and decimation labels |
| 20 | Power spectra: updated toy versus original run680 | RETAIN DATA / UPDATE | 27,38 | Frozen PSD and full-range display preserved |
| 21 | Spectral summaries: unchanged data estimator | RETAIN / UPDATE | 20,38,A3 | PSD RMS is a windowed spectral quantity, not full-run AC RMS |
| 22 | Temporal correlation: original run680 fit and updated toy | RETAIN DATA FIT | 39–40 | Preserve original signed-maxima fit and0–10us display |
| 23 | Temporal correlation: updated complex magnitude | BACKUP | A4 | Magnitude fit is not signed-envelope fit |
| 24 | Temporal correlation: matched quantitative comparison | RETAIN / UPDATE | 39–42 | Include imaginary covariance and exact scope |
| 25 | Updated normalization: does the toy agree with run680? | SPLIT / UPDATE | 34,42,54 | Retain disagreement, avoid treating normalization as the only test |
| 26 | Run 680 v2: the DC contribution is measurable | UPDATE | 19,22–24 | Replace old normalization text with full260-run DC diagnostic |
| 27 | Merge compatible summaries, not disconnected streams | BACKUP | A7 | Merge compatibility, not physical phase continuity across runs |
| 28 | Complete v2 campaign: raw level and AC fluctuations | RETAIN RELATIVE DATA | 18,21 | Dimensionless changes valid; correct unit-bearing values |
| 29 | Local and fixed thresholds tell different stories | RETAIN / UPDATE | 29,36 | Threshold definitions explicit |
| 30 | Amplitude tails: use a magnitude-noise baseline | UPDATE | 12,29,36 | Rayleigh reference not Gaussian amplitude significance |
| 31 | Noise stability depends on the statistic | RETAIN / UPDATE | 21,30 | State meanA/varianceA/CV versus complexAC definitions |
| 32 | An operational time scale for level stability | BACKUP | A10 | Operational level-stability time is not covariance or averaging time |
| 33 | Ensemble conclusions and next steps | REPLACE | 30,42,54 | Separate empirical and model conclusions |
| 34 | Complete runs: common origin and relative drift | RETAIN RELATIVE DATA | 21 | Matched acquisition timestamps and thermal units |
| 35 | Nine frequency bands: common origin and drift | RETAIN RELATIVE DATA | 26 | Nine bands, not nine cavity modes |
| 36 | Removing DC changes the central-band drift | RETAIN RELATIVE DATA | 23,26 | Run-mean subtraction changes a constant, not all LF noise |
| 37 | Temperature associations after removing run DC | UPDATE | 21,49 | Add cubic trend/differences; no causal temperature statement |
| 38 | Compare with the common trend, without calling it gain | BACKUP / UPDATE | A10 | Common trend includes the mode itself; not measured gain |
| 39 | DC removal changes the thermal comparison | RETAIN / UPDATE | 23,26,30 | Dimensionless results retained; updated interpretation |
| 40 | Upper-maximum fit statistics and5μs sensitivity | RETAIN | 40,A4 | Primary fit and window sensitivity separate |
| 41 | Supplementary magnitude-envelope fit statistics | BACKUP | A4 | Weak modulus fits not promoted to physical poles |
| 42 | TM010: measured IQ response exposes limits of the scalar toy | UPDATE | 43,47,54 | Mix of confirmed IQ evidence and historical scalar predictions |
| 43 | Phase peaks: angle reference, quantization and offset | UPDATE | 13,25,37,A2 | Angle axis is not temporal frequency |
| 44 | Python function profile: total time and time per SPEC | BACKUP | A9 | 50SPEC profile: inclusive totals versus perSPEC distinguished |
| 45 | HPC 4407: where the three-worker time is spent | BACKUP | A8/A9 | HPC runtime attribution |
| 46 | Profiling: overhead, thread coverage and next changes | BACKUP | A9 | Unimplemented optimizations remain proposals |
| 47 | Why the TM010 toy covariance is mostly negative at short lags | UPDATE | 38–39,44,50–51 | Historical gain-dependent numbers not current baseline |
| 48 | TM010 calibration: raw IQ imbalance and image leakage | RETAIN RELATIVE / UPDATE | 44,47 | Raw IQ and image evidence robust; refresh historical absolute-response labels |
| 49 | TM010 mismatch persists across the run | RETAIN | 18,27,A6 | Five disjoint windows only, not260-run PSD census |
| 50 | Revised toy architecture: sidebands and noise-source locations | UPDATE | 43,48,53,55 | Replace obsolete67.4dB reference and separate noise-location hypothesis |
| 51 | ODB ranges: current comparison and previous ADC interpretation | BACKUP | A2 | Superseded2V/2V scenario stays historical, not equally adopted |

## Source-level cautions verified in the review

- v40 has51slides. Several inherited notes still state the superseded extra-FET-in-kz /67.4dB hypothesis, although the visible updated normalization slide uses103.4dB and LF60→20dB. Rewrite notes as well as visible body text.
- Several inherited data slides carry a blanket historical-toy footer. Their dimensionless data may be current and scientifically reusable; audit by source array and unit, not by the footer alone.
- Local reporting/iq_noise_summary_v38, v39 and v40 generator directories were untracked at cc67048. Existing rendered products were inspected, but those local generators must not be cited as tracked content of that commit. Earlier tracked generators and the simulation/diagnostic sources provide independent provenance.
- Parts of the rendering have very small multi-panel text. Reuse arrays and the broad layout; avoid pasting tiny pre-rendered tables when a native table or two slides is clearer.
- v21 remains the measured PSD/covariance reference, not the reference for current absolute toy calibration. Old data curves are preserved with the single documented ADC correction.
- S1–S3 keep a coherent tone; S4–S6 do not. Reordering conceptual stages must not silently carry that tone into the scientific noise model.
- S4/S5 arbitrary140dB and S6 nominal143dB ADC plots are historical teaching/scenario products, not the current absolute calibrated prediction.
- Old measured raw amplitude histograms cannot be converted to exact centered-amplitude histograms by subtracting their mean amplitude. Full complex centering needs samples or a separately validated representation.

## Verified quantitative assets to reuse in Part IV

| Source | Existing numerical figure / arrays | Intended storyboard use |
| --- | --- | --- |
| DDC | `longterm_DC_AC.png; IQ_center_trajectory.png` | 22–23 |
| DDC | `correlation_controls.png; between_modes_DC_correlations.png` | 21,49 |
| DDC | `run*_PSD_centering.png; centering_low_frequency_zoom.png; synthetic_PSD_centering.png` | 45 |
| DDC | `run*_DC_stability.png; synthetic_mean_stability.png; interval_results.json` | 28,41,49 |
| DDC | `run*_Rice_Rayleigh.png; fullrun_fixed_distribution_residuals.png` | 24,35 |
| IQCENT | `central_iq_spectra.png; spectral_matrix.npz` | 45 |
| SWEEP | `sweep_constraints_all_modes.png; TM010_unsampled_center.png` | 44 |
| H7 | `decay_times/matched_decay_fits.png; fit_window_sensitivity.png` | 40backup,54; contraction is not a measured hardware response |
| H8 | `PSD_and_complex_correlation.png; negative_covariance_tail.png` | 51 |
| H8 | `epsilon_crossover.png; mean_variance_vs_data.png; normalized_mean_variance_all_selected_runs.png` | 52 |
| H8 | `interpretations_and_double_counting.png; absolute_PSD_and_response_planes.png` | 50,53 |
| H8 | `calibration_factorization_sensitivity.png` | 50,54 |
| H8 | `fixed_normalization_amplitude_vs_data.png; MC_distributions.png` | 54andbackup; not the PartIII reference |

Paths for these IDs are in the source registry of [the main storyboard](flash_scientific_storyboard_cc67048.md). All assets above already existed before this planning task. A reuse recommendation is not permission to replace historical results.
