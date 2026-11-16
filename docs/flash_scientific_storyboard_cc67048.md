# FLASH scientific presentation — proposed storyboard

**Planning document only. No new slides, presentation files, scientific plots, fits, or reconstructions have been produced for this proposal.**

Scientific baseline reviewed: `cc6704818a3c7ac7387deddb5ef3b2666dff2883` (`cc67048`).
The local v40 presentation, its slide model and selected rendered PDF pages were inspected;
older v17/v19/v21/v34/v37 models were checked to identify the provenance of retained results.
All titles, messages and proposed slide content below are in English.

## Editorial decision

Use a **55-slide scientific master storyboard**, plus **10 backup slides**. This is a complete
source presentation, not a prescribed talk duration. The four chapters are independent:

| Range | Chapter | Purpose |
| --- | --- | --- |
| 1–2 | Opening | Questions and hierarchy of evidence |
| 3–16 | Part I — Toy simulation: construction of the physical model | Stop at the three-mode cavity + receiver model (internal step6) |
| 17–30 | Part II — Experimental noise characterization | Report data without invoking agreement with the toy |
| 31–42 | Part III — Toy simulation vs experimental data | Introduce empirical readout normalization and preserve discrepancies |
| 43–55 | Part IV — Possible explanations and model limitations | Present internal steps7/8 only as subsequent hypothesis tests |
| A1–A10 | Backup | Estimator details, provenance, uncertainty and computing performance |

Internal step numbers belong in provenance notes, not in the slide titles. The coherent tone
is a calibration/validation input and is absent from every thermal/receiver noise prediction.
HPC/HTC performance and Python profiling are retained in backup; they do not interrupt the
physical argument.

### Two reference objects, explicitly distinguished

- **M6**: physical source model through internal step6, with cavity bath, independently
  generated equivalent receiver noise, a declared assumed LPF and sampling. No LF-notch
  repair, offset fitted to data, image correction or added slow noise.
- **M6+C**: the same source architecture mapped to the detector using the independently
  acquired, mode-specific calibration curves and the adopted gain/range conventions.
  Calibration is introduced in PartIII. It is not presented as a discovery of a posteriori
  science-noise features. The published calibrated reference is `C6` below.
- **H7/H8**: tests motivated by observed discrepancies; never substituted retrospectively
  for M6 or M6+C. The finite-LF model is explicitly an initial, unfitted hypothesis.

The historical `step6` ADC plots used143dB nominal gain and±5V; they are not the final
calibrated reference. Their physical input-plane arrays and parameter table remain valuable.
The future common-conditions rendering must be a **parallel, documented presentation
series**, leaving all original products unchanged. Until it exists, show published C6 as an
archived baseline with its exact input assumptions, not as a silently redefined simulation.

## Status and processing legend

- **RETAIN**: keep scientific numbers/results; a new layout may still be needed.
- **UPDATE**: change presentation, labels, units or selection from existing arrays; no new fit.
- **ADD / REUSE RESULTS**: new slide built from numerical products that already exist.
- **COMPUTE**: numerical derivation or a parallel common-input simulation is still required;
  not executed for this storyboard. Tasks N01–N08 are specified after the slide list.

Every proposed slide must carry a footer with population, reference plane, acquisition
interval, processing/centering, and source identifier. Slides comparing two populations
must show the same estimator and axes, preferably in adjacent panels. Do not use different
bin widths to create an apparent shape discrepancy.

## Evidence labels, units and visual conventions

Use badges **THEORY**, **MONTE CARLO**, **MEASURED DATA**, **MEASURED CALIBRATION**,
**CONDITIONAL INPUT**, and **POST-COMPARISON HYPOTHESIS**. Theory and MC are different
curves, not interchangeable words. A data-derived response hypothesis is not a measured
transfer function.

| Role | Stable colour / style |
| --- | --- |
| Cavity bath/source | cyan `#43a1ed` |
| Equivalent receiver source | orange `#ed812a` |
| Total toy/MC | purple `#7657A6` |
| Experimental data | teal `#007F86` |
| Analytic expectation / equation curve | navy `#263952`, dashed where useful |
| Input versus output | retain source colour; solid/dashed or separate panels |
| I versus Qeff | filled/open markers or solid/dashed; do not repurpose source colours |
| Different modes | fixed labelled rows/facets, not a competing colour scheme |

Quantitative plots must come from saved arrays or declared numerical calculations. A
chain diagram explains topology; it must not impersonate a measured PSD. Use common time
segments and common stochastic draws wherever the source definition permits. Reusing the
same integer seed is not sufficient when array length, grid or filtering changes: the
underlying Gaussian draws themselves must be shared and the exact reuse tested.

Physical input-plane units and ADC units are separate. For the construction, prefer actual
input-plane V²/Hz or W/Hz and explicitly dimensionless distribution coordinates. A safe
known calibration tone can be shown at ADC scale. Do not multiply the tiny thermal-only
waveform by an undisclosed display gain to make it visible. If an arbitrary illustrative
gain is retained, label it on every affected panel and exclude it from all absolute tables.
Quantize the **sum** of the sources once; separately quantized contributions need not add.

## Source registry

Paths beginning `SRC/` refer to `/home/mazzitel/HFGW/analysis/`.
Paths beginning `RUN2/` refer to `/home/mazzitel/HFGW/analysis-work/Run2/`.
Historical numerical outputs under `SRC/simulation/step1–5` are local generated products,
not a request to add those files to Git.

| ID | Verified source / products | Scope and caveat |
| --- | --- | --- |
| V40 | `RUN2/reports/iq_noise_summary_v40/{slide_model.json,iq_noise_summary_v40.pdf,assets/,data/}` | 51slides; bodies9–25 current, several inherited notes/appendices historical |
| V21 | `RUN2/reports/iq_noise_summary_v21/slide_model.json`; frozen reference below | Original run680 PSD and covariance/fit reference; preserve measured result |
| S1 | `SRC/simulation/step1/validate_step01.py`, local `step01_arrays.npz` | Coherent numerical validation; historicalADC±5V,65536coding |
| S2/S3 | `SRC/simulation/step{2,3}/validate_step0{2,3}.py`, local arrays/figures | Historical tone+noise examples, not thermal-only science runs |
| S4 | `SRC/simulation/step4/FLASH_step04_thermal_model/` | Thermal-only,100mK,f0=8.8GHz,arbitrary140dB,ADC±5V |
| S5 | `SRC/simulation/step5/FLASH_step05_receiver_noise/` | Exactly reuses S4 cavity, adds equivalent receiver noise |
| S6 | `SRC/simulation/step6/{parameters.json,validate_step06.py,README.md}`; `RUN2/simulation/step6/{metrics.json,step06_simulation.h5,assets/}` | Physical three-mode model;20ms,34checks; historical143dB/±5V/1MHz assumptions |
| C6 | `SRC/simulation/toy_ODB_cal5_data2_LF_20261116/simulate_full_run.py`; matching `RUN2/simulation/` directory with `metrics.json`, `toy_full_run680.h5`, `comparison/*.npz`, `comparison/comparison.json` | Fresh209.7152s/mode,LF60→20dB,RF103.4dB,ADCcal5/science2V; no LF shape repair |
| D260 | `RUN2/reports/noise_fullrange_v2_20261109/runNNNNN_noise_v2.h5`, `dc_ac_temperature_by_run.csv`, merged products | 260complete runs680–939; stored voltages historically±5V; correct once from ODB |
| FROZEN | `RUN2/staging/legacy-repository/autoreco/noise_continuous/periodicity_run680/{periodicity_diagnostic.npz,positive_envelope_fit.json}`; `SRC/examples/fit_iq_correlation_decay.py` | First5SPEC only, original Hann PSD and linear covariance, signed-maxima fit |
| CAL | `RUN2/diagnostics/normalization_audit_20261114/calibration_reconstruction.json` | Three distinct curves reconstructed from archived calibration tone FFTs;±5V scale already applied |
| PERMODE | `RUN2/diagnostics/per_mode_calibration_audit_20261116/{README.md,summary.json,three_distinct_calibration_curves.png}` | Confirms three curves and unverified common LF/RF/Tn factors |
| AUDIT | `RUN2/diagnostics/TM010_response_audit_20261115/` |18raw tone runs; image/IQ tests and five disjoint run680 windows; some amplitude predictions historical |
| H7 | `SRC/simulation/step7/`; matching `RUN2/simulation/step7/` | Conditional frequency contraction, no physical circuit identification |
| DDC | `SRC/simulation/step7/dc_longterm_diagnostic/`; matching `RUN2/simulation/step7/dc_longterm_diagnostic/` |260v2moment products andBORs;16SPEC of680/693/909/939; no full-run raw rebuild |
| IQCENT | `RUN2/simulation/step7/central_iq_spectra/{spectral_matrix.npz,summary.json,central_iq_spectra.png}` | Original first5SPEC; I/Q/cross spectrum reconstructs frozen complex PSD |
| SWEEP | `RUN2/simulation/step7/sweep_constraints/{summary.json,sweep_constraints_all_modes.png,TM010_unsampled_center.png}` | Actual tone points, central gap and noise-response mismatch |
| H8 | `SRC/simulation/step8/{model.py,parameters.json,run_initial.py,report_initial.py,README.md}`; `RUN2/simulation/step8_LF_initial_20261116/` | Initialfc12.5kHz/epsilon0.02,8tests,two16-SPEC MCs/mode; no parameter fit |
| THESIS | `RUN2/reports/Tesi_Valeria_Spasiano.pdf` | Fig5.2 chain;§§5.1–5.2 mixing/calibration;Table6.1 cavity;Figs6.3–6.4 frequency-dependent gain/Tn |

Review also used `SRC/docs/iq_noise_v2.md`, `SRC/examples/{analyze_midas_iq_noise.py,
iq_noise_v2.py,iq_noise_statistics.py,report_noise_v2.py}`, calibration configuration,
and the updated simulation README. Valeria's LF/FET clarification is a supplied personal
communication recorded in the project documentation, not a statement to attribute verbatim
to the thesis. Her recalled ADC range conflicts with the inspected BOR; the adopted
scientific convention remains the ODB range, explicitly documented.

## Slide-by-slide storyboard


### Opening

#### 01. FLASH noise: from a physical reference model to experimental constraints

- **Scientific message:** Separate a generative model, measured noise, a matched comparison, and subsequent explanatory hypotheses.
- **Numerical visuals:** One clean title with the three modes and four chapter labels; no model/data agreement plot.
- **Equations / quantities:** No equation.
- **Provenance:** Dataset D260; source baseline cc67048.
- **Existing material:** v40:1
- **Disposition:** **UPDATE**. Required processing: None.

#### 02. Four questions, four levels of evidence

- **Scientific message:** What do we predict independently? What do we measure? Where do they agree? Which additional measurements distinguish the explanations?
- **Numerical visuals:** Four-column roadmap with badges THEORY, MC, DATA, CONDITIONAL CALIBRATION, and POST-COMPARISON HYPOTHESIS.
- **Equations / quantities:** M6 → instrument mapping C → measured observables; H7/H8 remain a separate branch.
- **Provenance:** S6, C6, D260, H7, H8.
- **Existing material:** v40:1,12,25,33,50: replace the interleaved narrative.
- **Disposition:** **ADD**. Required processing: None.


### Part I — Toy simulation: construction of the physical model

#### 03. A generative model, not a fit to the science noise

- **Scientific message:** The reference contains a cavity bath, an independent equivalent receiver source, assumed readout filtering and sampling. The coherent tone is a separate validation input and is then switched off.
- **Numerical visuals:** Source-to-observable diagram with a tone-validation bypass; explicitly cross out the tone in every noise-only stage. No measured TM010 notch or LF repair.
- **Equations / quantities:** z = z_cavity + z_receiver; z_tone = 0 in all scientific noise examples.
- **Provenance:** S1–S6; the diagram is a model specification, not numerical evidence.
- **Existing material:** v19:9–13 and v40:9: reuse architecture, remove calibrated-response and post-comparison content.
- **Disposition:** **UPDATE**. Required processing: None.

#### 04. A coherent tone validates the I/Q convention

- **Scientific message:** A known tone tests quadrature sign, phase rotation, FFT orientation and ADC conversion. Five samples per cycle at 1 MHz is a deliberate numerical test, not a claim about the actual science IF.
- **Numerical visuals:** Three panels: I and Qhardware versus time; circular IQ trajectory; signed FFT with its known peak. Use a safe, declared calibration amplitude at the ADC.
- **Equations / quantities:** z = I − iQhardware; z(t) = A exp(i2π f_IF t); q = 4/65535 V/count for the science-range demonstration.
- **Provenance:** S1: step01_arrays.npz and validate_step01.py; regenerate the pedagogical ADC panel with ±2 V and the common coding convention.
- **Existing material:** No direct v40 equivalent; historical step1 figure exists.
- **Disposition:** **ADD + COMPUTE**. Required processing: N01,N02.

#### 05. The cavity sets a response time, not the receiver noise level

- **Scientific message:** The driven resonator and thermal-bath transfer share a pole but have different amplitude normalizations. The cavity amplitude-decay time must not be identified with every fitted readout decay.
- **Numerical visuals:** Numerically evaluated complex response and Lorentzian power response, with loaded linewidth and amplitude time for the three modes; use no arbitrary gain inference.
- **Equations / quantities:** Q_L = Q0/(1+kappa1+kappa2); Δf = f0/Q_L; tau_A = Q_L/(π f0). abs(H_bath)² = k_i k_2/[(k_tot/2)²+(2πδf)²]; any complex-response phase uses one declared Fourier convention.
- **Provenance:** S2,S4,S6; thesis Table6.1.
- **Existing material:** v40:9 parameter table supplies values, not a ready response figure.
- **Disposition:** **ADD + COMPUTE**. Required processing: N01,N02.

#### 06. Down-conversion, filtering and sampling change the observed process

- **Scientific message:** Represent an RF envelope rather than sampling a GHz carrier. An analog LPF precedes sampling; alias power is retained. A later empirical response replaces the assumed LPF, rather than multiplying it twice.
- **Numerical visuals:** Three numerical spectra before LPF, after LPF, and folded into the ADC band, plus a short sampled trace. Hardware frequency values are identified as configured inputs.
- **Equations / quantities:** S_sampled(f) = Σ_m S_analog(f+m fs); fs = 5 MS/s. Assumed LPF: fourth-order Butterworth, fc = 1.9 MHz.
- **Provenance:** S2–S6 arrays and folded spectra; actual LO settings DDC/hardware.json.
- **Existing material:** v40:5 only contributes band/axis definitions; do not reuse its qualitative spectrum as evidence.
- **Disposition:** **ADD + COMPUTE**. Required processing: N01,N02.

#### 07. Thermal cavity emission without a coherent tone

- **Scientific message:** The physical wall bath produces stochastic emission governed by thermal occupation and the output coupling. It is not a broadened calibration tone.
- **Numerical visuals:** Bath, cavity-output and filtered thermal PSD on physical input-plane axes; one IQ cloud and a trace inset. Small thermal levels are shown before quantization, without secretly increasing the physical gain.
- **Equations / quantities:** Theta(f0,T) = h f0/[exp(h f0/kB T)−1]; S_cav = Theta |H_bath|².
- **Provenance:** S4 concept and S6 thermal-only arrays; current T15 = 40.422386 mK. Historical S4 used100mK and140dB display gain and cannot be pasted as the current normalization.
- **Existing material:** v19:11: concept only; numerical panel must be updated.
- **Disposition:** **UPDATE + COMPUTE**. Required processing: N01,N02.

#### 08. Equivalent receiver noise is added after the cavity response

- **Scientific message:** Receiver-added noise is independent and input-referred; it is not multiplied by the cavity Lorentzian. The quoted Tn belongs to a particular no-TWPA measurement configuration.
- **Numerical visuals:** Cavity-only, receiver-only and sum PSD using the same cavity realization and an independent receiver realization; shared axes or explicitly labelled logarithmic physical units.
- **Equations / quantities:** S_total = S_cav + kB Tn before shared readout; Tn = 3.955 ± 0.468 K, conditional applicability.
- **Provenance:** S5 exact reuse of S4 cavity samples; S6 separates the two physical contributions.
- **Existing material:** v19:12 and v40:9 architecture: update numerical scales and qualifications.
- **Disposition:** **UPDATE + COMPUTE**. Required processing: N01,N02.

#### 09. Three measured cavity modes, one explicitly conditional receiver model

- **Scientific message:** The cavity frequencies, Q0 and couplings are mode-specific. A common receiver Tn and an assumed LPF are hypotheses, not three independently measured readouts.
- **Numerical visuals:** Parameter table with separate columns for independently measured quantities, observed T15, and conditional/common assumptions. Include QL, linewidth, cavity time; no claim of equal calibrations.
- **Equations / quantities:** TM010 tau_A = 1.068 us; TM011 = 1.083 us; TM012 = 0.896 us.
- **Provenance:** S6/parameters.json; thesis Table6.1; run680 thermometry; thesis Figs6.3–6.4 for configuration dependence.
- **Existing material:** v40:9: retain cavity table; replace stale notes and move kz/gain ledger to PartIII.
- **Disposition:** **UPDATE**. Required processing: N01.

#### 10. Noise I/Q traces and constellations follow from the source model

- **Scientific message:** The sum remains a stochastic complex process. Cavity-only and receiver-dominated traces must not be compared using independently chosen hidden scales.
- **Numerical visuals:** Rows for source contributions, columns for a shared time segment and IQ density. I uses filled and Qeff open markers in the source colour; all plotted time points are identified as sampled or decimated.
- **Equations / quantities:** E|z|² = Var(I)+Var(Qeff) for centered noise.
- **Provenance:** S6 input_cavity_after_assumed_LPF_v, input_receiver_after_assumed_LPF_v, input_total_after_assumed_LPF_v; common realization N01.
- **Existing material:** v40:17,19 layout can be reused; their calibrated full-run data are not PartI inputs.
- **Disposition:** **ADD + COMPUTE**. Required processing: N01,N02.

#### 11. Gaussian quadratures and circularity are testable assumptions

- **Scientific message:** Rayleigh amplitude requires centered, isotropic proper Gaussian I/Q. Gaussian marginals alone are insufficient.
- **Numerical visuals:** I/Q marginal histograms with analytic zero-mean Gaussian curves; covariance ellipse and pseudo-covariance summary. A numerical histogram is required, not just a cartoon ellipse.
- **Equations / quantities:** sigma_q² = E|z|²/2; eta = |E[(z−mu)²]|/E|z−mu|².
- **Provenance:** S6 numerical samples and saved pseudo-covariance; no new Gaussian-fit parameters are needed.
- **Existing material:** v40:18 contributes definitions only.
- **Disposition:** **ADD + COMPUTE**. Required processing: N02.

#### 12. Rayleigh amplitude and a linearized survival function

- **Scientific message:** For the stated proper Gaussian model, the amplitude law and its tail are predicted by the quadrature variance. They are not Gaussian amplitude significance levels.
- **Numerical visuals:** Amplitude histogram with a parameter-free Rayleigh prediction and log CCDF versus A²/(2 sigma_q²). Include a small threshold-probability table with the convention written out.
- **Equations / quantities:** p(A)=A/sigma_q² exp[−A²/(2sigma_q²)]; log P(A>a)=−a²/(2sigma_q²).
- **Provenance:** S6 samples; analytic law. T_k=mu_R+k sigma_A,R gives tail probabilities0.0056275,3.51494e−5,3.94382e−8 for k=3,5,7.
- **Existing material:** v40:13 table/format reusable, not its calibrated scale or fitted data.
- **Disposition:** **UPDATE + COMPUTE**. Required processing: N02,N04.

#### 13. Uniform phase does not imply independent phase increments

- **Scientific message:** A centered proper model has uniform marginal phase; filtered noise can retain short-lag phase dependence. Angular peaks are not LO-frequency peaks.
- **Numerical visuals:** Absolute phase histogram and wrapped increment histograms at lags1,10,100 samples, with common angular bins and valid-pair counts. Show the effect of ADC separately from the continuous model.
- **Equations / quantities:** phi=arg(z); Δphi_l=arg[z(n+l)z*(n)], defined only for nonzero endpoints.
- **Provenance:** S6 arrays allow phase/increment derivation; S1 tone is no longer present.
- **Existing material:** v40:15,16,43: reuse conventions, not the data-comparison panels.
- **Disposition:** **ADD + COMPUTE**. Required processing: N01,N02,N03.

#### 14. PSD and complex autocorrelation are two views of the same model

- **Scientific message:** The total covariance is set by the full observed spectrum. Its real part can be negative; its imaginary part encodes spectral asymmetry.
- **Numerical visuals:** Three-mode PSD and Re/Im g1 with analytic expectations and finite-MC estimates; include g1(0)=1 or state clearly that the origin is omitted. No LF-notch hypothesis is added.
- **Equations / quantities:** C(tau)=∫S_z(f)exp(i2πf tau)df; g1=C/C(0).
- **Provenance:** S6 psd_folded_expected_input_v2_hz, g1_expected and g1_simulated.
- **Existing material:** v40:11,22–24 only supply a layout; actual values there belong to C6, not pure M6.
- **Disposition:** **ADD + COMPUTE**. Required processing: N01,N02.

#### 15. The variance of averages depends on the full PSD

- **Scientific message:** A decrease proportional to1/T is a white-noise limit, not a universal rule. Averaging time, cavity time and operational run-to-run stability are different concepts.
- **Numerical visuals:** Numerical V(T) integrated from the model PSD, MC block-mean variance where enough blocks exist, and a clearly labelled white reference. Do not extrapolate a coarse PSD grid to long T.
- **Equations / quantities:** V(T)=∫S_z(f)|W_T(f)|²df; discrete boxcar response used for sampled data.
- **Provenance:** S6 spectra and traces; reuse the validated integration method from H8 as a numerical tool with LF disabled, not as an added physical model.
- **Existing material:** No ready M6-only figure; v40:32 is an operational tolerance time, not this observable.
- **Disposition:** **ADD + COMPUTE**. Required processing: N02,N05.

#### 16. Freeze the reference before looking at the discrepancies

- **Scientific message:** The construction ends at the three-mode cavity-plus-equivalent-receiver model. Readout calibration comes later; LF repair, additive offsets and vector-IQ refinements are not silently included.
- **Numerical visuals:** Model specification card listing sources, reference planes, independent inputs, assumptions, missing physics and generated observable set. Clearly declare that there is no permanent coherent tone.
- **Equations / quantities:** M6: physical source model + assumed LPF + sampling; no H7/H8 terms.
- **Provenance:** S6 plus the common-presentation configuration proposed in N01.
- **Existing material:** Replace v40:12, whose mixed model/data interpretation comes too early.
- **Disposition:** **ADD**. Required processing: None.


### Part II — Experimental noise characterization

#### 17. The experiment: three distinct readout paths

- **Scientific message:** Show the measured acquisition architecture without using simulation agreement to validate it. TM010 is directly acquired after LPF; the other modes undergo additional band selection and conversion.
- **Numerical visuals:** Simplified native diagram faithful to thesis Fig5.2, channel map and actual primary/final IF table. Science ADC±2V is an instrumental setting.
- **Equations / quantities:** z=I−iQhardware; primary IFs1.250,44.971,105.313MHz; final cavity IFs1.250,1.248,1.256MHz.
- **Provenance:** THESIS Fig5.2; DDC/hardware.json; D260 settings.
- **Existing material:** v40:10 chain can be simplified; remove gain-accounting discussion until PartIII.
- **Disposition:** **UPDATE**. Required processing: None.

#### 18. The 260-run dataset and its coverage

- **Scientific message:** Campaign-level statements use complete validated products. PSD, covariance and raw-window checks have smaller, explicitly stated coverage.
- **Numerical visuals:** Timeline680–939, completeness count and a coverage matrix:260full runs, run680 five-SPEC reference, four16-SPEC diagnostics, five disjoint windows inside run680.
- **Equations / quantities:** 260 × 1,048,576,000 complex samples/mode;15.15h acquired versus15.33h span.
- **Provenance:** D260; DDC/product_manifest.json; AUDIT windows.
- **Existing material:** v40:28 headline and27 completeness logic; keep technical merge mechanics in backup.
- **Disposition:** **UPDATE**. Required processing: None.

#### 19. Raw amplitude, complex DC and AC fluctuations are different observables

- **Scientific message:** The original raw histograms and the v2 complex-mean-subtracted products must not be relabelled as the same population.
- **Numerical visuals:** Definitions with a measured numerical example from run680 and a coordinate-shift diagram; show ADC units, not nominal143dB values as calibrated input noise.
- **Equations / quantities:** mu=<z>; DC²=|mu|²; AC²=<|z−mu|²>; raw RMS²=DC²+AC². |z|−<|z|> is not |z−mu|.
- **Provenance:** examples/iq_noise_v2.py and iq_noise_statistics.py; D260 moments; DDC conversion audit.
- **Existing material:** v40:4,26: update stale normalization notes and use correct physical ADC values.
- **Disposition:** **UPDATE**. Required processing: None.

#### 20. Estimator definitions are part of each measurement

- **Scientific message:** State the mean subtraction, time selection, FFT window, bin averaging, lag normalization and valid-sample rules before interpreting plots.
- **Numerical visuals:** Compact estimator matrix: full-run moments/histograms; original five-SPEC Hann periodogram; linear covariance; continuous causal FIR bands.
- **Equations / quantities:** T5=1.048576s; Δf_native≈0.954Hz; display256-bin means≈244.14Hz. C[k] divides by N−k.
- **Provenance:** D260; frozen v21 diagnostic; examples/fit_iq_correlation_decay.py and band config.
- **Existing material:** v40:4,5,21,24 plus backup estimator details; replot any qualitative spectrum only as an explicitly labelled definition.
- **Disposition:** **UPDATE**. Required processing: None.

#### 21. Noise level and temperature evolve through the campaign

- **Scientific message:** The levels drift by a few percent; similar histories do not establish temperature causality or measured gain variation.
- **Numerical visuals:** Aligned acquisition-time panels for AC RMS, raw mean amplitude, and T15/T16/T17; relative curves may reuse existing assets, with physical ADC level anchors.
- **Equations / quantities:** Relative levels reference run680, with denominator stated; correlations remain descriptive.
- **Provenance:** D260/dc_ac_temperature_by_run.csv; DDC/longterm.csv; existing v2 campaign aggregates.
- **Existing material:** v40:28,31,34,37,38: consolidate and remove stale historical footers.
- **Disposition:** **UPDATE**. Required processing: N06.

#### 22. The centre of the IQ distribution moves with time

- **Scientific message:** DC is a measured vector with magnitude and direction; its long-term changes are not the fast thermal or receiver variance.
- **Numerical visuals:** Mean I and Qhardware versus time, plus IQ-centre trajectories in I,Qeff for all modes, coloured by acquisition time.
- **Equations / quantities:** mu_I=<I>; mu_Qeff=−<Qhardware>; arg(mu) uses the same complex convention.
- **Provenance:** DDC/longterm_DC_AC.png and IQ_center_trajectory.png, derived from all260v2 products.
- **Existing material:** v40:26 only covered run680; replace with the complete long-term diagnostic.
- **Disposition:** **ADD / REUSE RESULTS**. Required processing: N06.

#### 23. DC power is small but its instrumental effects need not be

- **Scientific message:** Separate DC², AC², total quadratic voltage, phase of the DC vector and their ratio; distinguish raw from centered phase and centre-band measurements.
- **Numerical visuals:** Selected rows from DDC long-term figure, including DC phase, powers and DC²/AC²; retain common ADC units.
- **Equations / quantities:** DC²/AC² ≈2.65e−5–2.25e−4 (TM010),7.09e−4–3.67e−3 (TM011),9.27e−6–6.69e−5 (TM012).
- **Provenance:** DDC/longterm.csv and README; D260.
- **Existing material:** v40:26,36,39: update/expand; do not reuse old nominal input-referred values as physical RF values.
- **Disposition:** **ADD / REUSE RESULTS**. Required processing: N06.

#### 24. Measured quadratures and amplitude laws before and after centering

- **Scientific message:** Use Gaussian/Rice/Rayleigh as explicit statistical reference laws with moment-based parameters, not as claims that the real IQ noise is exactly circular.
- **Numerical visuals:** Measured I/Q marginals, raw amplitude with fixed-moment Rice reference, and centered CCDF against A². Keep full-run raw and16-SPEC centered panels separately labelled.
- **Equations / quantities:** nu=|mu|; sigma_q²=AC²/2. Report pseudo-covariance≈4–5% rather than assuming it away.
- **Provenance:** D260 raw global amplitude/IQ histograms; DDC/run*_Rice_Rayleigh.png and fullrun_fixed_distribution_residuals.png.
- **Existing material:** v40:13,17,18 can supply measured data panels; new DC diagnostic supplies Rice reference.
- **Disposition:** **UPDATE + COMPUTE**. Required processing: N03,N06.

#### 25. Measured phase and phase increments are separate diagnostics

- **Scientific message:** Angular quantization, a nonzero IQ centre, and temporal dependence have different signatures. An angular histogram is not a modulation-frequency spectrum.
- **Numerical visuals:** Raw absolute phase and lag1/10/100 increment histograms from saved global arrays; add campaign summaries of circular resultants. Centered-window phase is a separate, newly labelled diagnostic.
- **Equations / quantities:** Raw lags0.2,2,20us; filtered increments4us belong to a different bandwidth and sample rate.
- **Provenance:** D260 arrays/global_*_phase and global_*_delta_{1,10,100}; phase_reference metadata; v40 phase diagnostic.
- **Existing material:** v40:15,16,43: data panels only, use one common absolute phase convention.
- **Disposition:** **UPDATE + COMPUTE**. Required processing: N03,N06.

#### 26. Frequency-resolved stability and the effect of removing the run mean

- **Scientific message:** The nine analysis windows are electronic-frequency bands, not additional cavity resonances or demonstrated modulation sidebands. Removing a single run mean does not high-pass an entire band.
- **Numerical visuals:** Measured nine-band relative levels and raw-versus-v2 centre-band drift, with temperature association kept descriptive.
- **Equations / quantities:** Offsets0,±100,±250,±500,±1000kHz; nominal width50kHz;2001tap FIR;decimation20; use measured ENBW.
- **Provenance:** D260 filtered_bands/config and events; v2 campaign tables.
- **Existing material:** v40:5,35,36,39: keep dimensionless results and update labels.
- **Disposition:** **UPDATE**. Required processing: None.

#### 27. Measured spectra and complex correlations: a representative view

- **Scientific message:** State what the data show before invoking a model: a narrow TM010 centre deficit, mode-dependent spectra and finite-lag correlations.
- **Numerical visuals:** Data-only PSD and Re/Im g1 for run680; small inset on the four-run notch-width check or five disjoint windows. Keep the original full spectral range.
- **Equations / quantities:** g1(0)=1; signed Re g1 is not a positive-only coherence measure.
- **Provenance:** Frozen v21 PSD/covariance; DDC spectra; AUDIT windows; raw ADC correction once.
- **Existing material:** v21:19 and v40:20–24,49: retain measured arrays and original display estimator; remove toy panels.
- **Disposition:** **UPDATE / REUSE RESULTS**. Required processing: N06.

#### 28. Averaging reveals coloured noise and slow changes

- **Scientific message:** At short times TM010 averages differently from the other modes; at long times the finite-record and PSD-resolution limits must remain visible.
- **Numerical visuals:** Data-only V(T) for four representative runs and SPEC-mean traces; label the white reference as a null limit, not a fitted theory.
- **Equations / quantities:** Short-range log slopes≈−1.89 for TM010 and≈−1 for TM011/012,25.6–409.6us.
- **Provenance:** DDC interval_results.json and run*_DC_stability.png; data cover16SPEC/run only.
- **Existing material:** No old equivalent: v40:32 is an operational tolerance metric and must not be substituted.
- **Disposition:** **ADD / REUSE RESULTS**. Required processing: N06.

#### 29. Tail counts need an explicit threshold convention

- **Scientific message:** Separate local empirical thresholds, fixed historical thresholds and a Rayleigh reference probability. Counts of samples, episodes and selected plotting markers are different quantities.
- **Numerical visuals:** Full-campaign local/fixed rate trends and a run680 rare-tail table with actual thresholds and counts; all count denominators stated.
- **Equations / quantities:** T_emp,k=mean(A)+k std(A); T_R,k=mu_R+k sigma_A,R. P_R(A>T)=exp[−T²/(2sigma_q²)].
- **Provenance:** D260 summary/global_statistics thresholds and exceedances; existing campaign arrays.
- **Existing material:** v40:29,30 and17 rare-tail annotations: retain exact measured counts but audit their threshold labels.
- **Disposition:** **UPDATE**. Required processing: N04,N06.

#### 30. Experimental findings, without a simulation explanation

- **Scientific message:** End the independent data chapter with empirical constraints: drifting level and IQ centre, approximate Gaussian-family distributions, a robust TM010 notch, and slow components in averaging.
- **Numerical visuals:** Five-row evidence table, each row labelled by coverage260runs/4windows/run680; no model prediction and no causal thermal conclusion.
- **Equations / quantities:** No additional fit. Distinguish microsecond covariance, subsecond averaging and minute-scale level stability.
- **Provenance:** D260, DDC, AUDIT; conclusions restricted to measured coverage.
- **Existing material:** v40:33 plus the latest DC diagnostic conclusions; replace older provisional statements.
- **Disposition:** **UPDATE**. Required processing: None.


### Part III — Toy simulation vs experimental data

#### 31. A matched comparison requires a declared model and population

- **Scientific message:** Compare the frozen source model plus independently measured readout calibration, not the later LF hypothesis. Match processing and distinguish full-run raw, full-run moments, and short centered samples.
- **Numerical visuals:** Model card M6+C and a population/estimator ledger beside the frozen data references.
- **Equations / quantities:** M6+C = M6 source PSD propagated through empirical response and ADC; H7/H8 excluded.
- **Provenance:** S6 and C6; D260; frozen comparison/comparison.json.
- **Existing material:** v40:11–14,20–24: reuse numerical scope but restructure the introduction.
- **Disposition:** **ADD**. Required processing: N01,N03,N05.

#### 32. Absolute normalization: one reference plane at a time

- **Scientific message:** RF gain, LF setting ratio, ADC range and calibration coefficient are distinct factors. The second36dB FET is outside the tone calibration and is included once in103.4dB RF gain.
- **Numerical visuals:** Simplified chain with marked tone-injection plane; numerical conversion/gain ledger; measured versus conditional labels.
- **Equations / quantities:** k_data=k_cal/100; ADC cal10/65535, science4/65535 V/count. Equivalent gain63.4dB only when keeping k_cal unchanged. Never cascade143dB with kz.
- **Provenance:** C6 metrics, calibration reconstruction, ODB audit, Valeria clarification; thesis Fig5.2 and §5.2.
- **Existing material:** v40:10: retain the current visible chain, remove superseded speaker notes throughout the deck.
- **Disposition:** **UPDATE**. Required processing: None.

#### 33. Three calibration curves, and assumptions they do not determine

- **Scientific message:** The software already uses distinct kz curves. Common RF gain, common Tn and a frequency-independent LF20/60 ratio remain unverified across modes.
- **Numerical visuals:** Numerical three-curve plot with calibration tone points, RF-to-IF mapping and a measured/assumed table. No fitted per-mode amplitude factor.
- **Equations / quantities:** kz_cal near1.033MHz≈157.989,76.743,47.355; the factor0.01 is common by hypothesis.
- **Provenance:** CAL and PERMODE/three_distinct_calibration_curves.png; thesis Figs6.3–6.4.
- **Existing material:** v40:9,10 and the separate per-mode audit: add explicit curves.
- **Disposition:** **ADD / REUSE RESULTS**. Required processing: None.

#### 34. Absolute RMS and Rayleigh scale are not yet reproduced

- **Scientific message:** The model predicts a scale; fitting a distribution parameter for description does not independently validate that prediction. Use AC RMS for centered comparison and raw RMS only for raw amplitudes.
- **Numerical visuals:** Three-mode table with predicted AC RMS, measured full-run AC RMS, measured raw RMS and descriptive Rayleigh scale in separate columns. Show ratios without applying them.
- **Equations / quantities:** Reference C6 RMS≈27.173,13.701,8.406mV; data AC RMS32.260,20.749,13.733mV; data raw RMS32.263,20.784,13.733mV.
- **Provenance:** C6 metrics and D260 dc_removed moments; do not mix v40 fitted raw Rayleigh RMS with AC moments.
- **Existing material:** v40:14,25,51: consolidate and fix metric headings, not the measured values.
- **Disposition:** **UPDATE**. Required processing: N03,N07.

#### 35. Amplitude-shape agreement is different from absolute agreement

- **Scientific message:** Normalized distributions can be approximately Rayleigh even when physical noise levels differ. Raw data with an offset call for a Rice check; centered data call for Rayleigh.
- **Numerical visuals:** Side-by-side toy/data panels in common physical amplitude bins, followed by explicitly dimensionless A/sigma_q and CCDF panels; no free cross-population gain factor.
- **Equations / quantities:** log CCDF versus A²/AC² for centered populations; parameters from each measured/predicted moment set, not a gain adjustment.
- **Provenance:** C6 amplitude_counts; D260 raw counts; DDC centered-window diagnostics.
- **Existing material:** v40:13,14 layouts reusable; centered full-run histogram is not currently archived.
- **Disposition:** **UPDATE + COMPUTE**. Required processing: N03,N04.

#### 36. Tail probabilities and rare counts on comparable definitions

- **Scientific message:** Use the same raw/centered population and threshold formula on both sides. Exact existing counts must not be relabelled as counts at a different fitted threshold.
- **Numerical visuals:** Rayleigh3/5/7 table; side-by-side counts and threshold values. Prefer exact7-tail counts from existing saved tails when possible; report finite-bin bounds otherwise.
- **Equations / quantities:** Rayleigh T_R/sigma_q=3.218723,4.528996,5.839269; p=0.0056275,3.51494e−5,3.94382e−8.
- **Provenance:** C6 saved tail_above_5sigma_v; D260 empirical thresholds/counts; checked threshold mismatch up to0.067% in TM011.
- **Existing material:** v40:13 probability table and17 rare-marker table: update definitions before reuse.
- **Disposition:** **UPDATE + COMPUTE**. Required processing: N04.

#### 37. Angular distributions expose offset, sampling and temporal differences

- **Scientific message:** Compare absolute phase in a common ADC frame and increments at the same lag. A broad measured preference and narrow quantization spikes must not be interpreted as a coherent LO oscillation.
- **Numerical visuals:** Toy/data side-by-side phase and increment histograms using common edges; raw and centered comparisons explicitly separate. Existing von Mises fits remain descriptive backup, not a physical correction.
- **Equations / quantities:** phi=atan2(Qeff,I); valid zero-amplitude mask common; Δphi_l uses matching endpoints and lags.
- **Provenance:** C6 phase_counts and first5SPEC_ADC_counts; D260 global angular arrays; short matched increments require N03.
- **Existing material:** v40:15,16,43: keep angular evidence, update phase origin and scopes.
- **Disposition:** **UPDATE + COMPUTE**. Required processing: N03,N06.

#### 38. The scalar calibrated model predicts a broader TM010 depression

- **Scientific message:** This is a discrepancy to retain, not a justification for changing the measured spectrum or a gain. The physical normalization mismatch and the shape mismatch are separate.
- **Numerical visuals:** Original full-range spectra and a central zoom, toy/data in adjacent panels with matched axes; optional relative-plateau view clearly labelled.
- **Equations / quantities:** Broad scalar reference width≈247kHz versus data≈25kHz under the declared descriptive estimator.
- **Provenance:** C6 comparison/*.npz; frozen v21 data; processing audit.
- **Existing material:** v40:20,21; preserve their exact measured PSD, binning and Hann estimator.
- **Disposition:** **UPDATE / REUSE RESULTS**. Required processing: None.

#### 39. The full complex autocorrelation must follow the spectrum

- **Scientific message:** Show real and imaginary parts. A negative real component is allowed, but a different negative structure reveals the wrong spectral shape.
- **Numerical visuals:** Three-mode Re/Im g1 side-by-side with shared0–10us axes and long-lag inset; origin explicitly accounted for.
- **Equations / quantities:** g1 is complex; |g1| is a different nonnegative observable; no subtraction of a fitted covariance baseline.
- **Provenance:** C6 comparison arrays; original measured covariance.
- **Existing material:** v40:22–24 and v21:19: retain data; add the imaginary part explicitly.
- **Disposition:** **UPDATE**. Required processing: N06.

#### 40. Characteristic times depend on the estimator and the response

- **Scientific message:** A cavity pole, a signed upper-envelope fit, a magnitude fit and averaging time are not interchangeable. A poor exponential fit is not a reliable decay-time measurement.
- **Numerical visuals:** Historical signed-maxima fit table and curves, cavity tau column separately; fitted ranges shown,0–10us display preserved; sensitivity in backup.
- **Equations / quantities:** C+A exp(−tau/tau_fit), original local maxima0.3–4us, C free. Data0.926/1.419/1.385us; unresolved toy TM010 labelled as such.
- **Provenance:** examples/fit_iq_correlation_decay.py; frozen positive_envelope_fit.json; C6 comparison.json.
- **Existing material:** v40:22,24,40; modulus23/41 moved to backup.
- **Disposition:** **UPDATE / REUSE RESULTS**. Required processing: None.

#### 41. Averaging statistics test more than the short-lag decay

- **Scientific message:** Compare the original calibrated reference against measured V(T) with the same discrete averaging operator and finite-record convention. No LF shelf is included yet.
- **Numerical visuals:** Absolute V(T) and a separate V/AC² view for reference M6+C and four measured windows; MC validation limited to a short shared interval.
- **Equations / quantities:** E[var_pop(block means)]=V(T)−V(KT) for K consecutive equal blocks of a stationary record.
- **Provenance:** DDC measured means; C6 PSD and saved prefix; a new baseline-only prediction is required, not the H8 prediction.
- **Existing material:** No existing v40 result; do not insert step8 curves into the reference comparison.
- **Disposition:** **ADD + COMPUTE**. Required processing: N05.

#### 42. What the reference reproduces, and what it does not

- **Scientific message:** End the comparison with a transparent scorecard before introducing additional hypotheses. Agreement in normalized amplitude shape does not erase wrong absolute levels, IQ balance or LF behavior.
- **Numerical visuals:** Rows: scale; normalized amplitude; raw phase; increment statistics; PSD; Re/Im correlation; fitted times; DC; V(T). Columns: reproduced/partial/not reproduced/not yet evaluated, scope and evidence.
- **Equations / quantities:** No new fit. Do not mark uncomputed matched increment or baseline V(T) tests as agreement.
- **Provenance:** C6+D260+DDC; N03/N05 placeholders visibly marked pending until computed.
- **Existing material:** v40:25: replace the single normalization conclusion with a multidimensional evidence summary.
- **Disposition:** **UPDATE**. Required processing: N03,N05.


### Part IV — Possible explanations and model limitations

#### 43. The LF setting changed between calibration and science acquisition

- **Scientific message:** The nominal60→20dB correction is known, but its frequency-dependent shape is not. This is the first explanatory hypothesis, not an established correction.
- **Numerical visuals:** Measured chain with LF stage highlighted, calibration/science settings and a table of known versus unmeasured quantities.
- **Equations / quantities:** H_LF,20(u)/H_LF,60(u) need not be constant0.01 across primary IF.
- **Provenance:** Valeria clarification; PERMODE audit; thesis Fig5.2.
- **Existing material:** v40:10,42,50: update epistemic labels; no obsolete67.4dB reference plane.
- **Disposition:** **ADD / REUSE RESULTS**. Required processing: None.

#### 44. The sweep does not resolve the central notch, but the broad loss is measured

- **Scientific message:** There are no tone points inside±49.18kHz. Interpolation cannot reveal a25kHz notch, yet low response at measured nearby points prevents blaming the whole discrepancy on interpolation.
- **Numerical visuals:** Use the actual sweep points over the scalar response, separate from the noise spectrum; shade the unsampled interval and show the measured±49kHz values.
- **Equations / quantities:** At±49kHz, tone power≈0.46 of plateau while science-noise power≈0.95 in10kHz bands.
- **Provenance:** SWEEP/sweep_constraints_all_modes.png and TM010_unsampled_center.png; CAL actual points.
- **Existing material:** v40:47,48: update with explicit sampling constraints; do not reuse the old absolute scale.
- **Disposition:** **ADD / REUSE RESULTS**. Required processing: None.

#### 45. The notch exists in each quadrature and survives DC-processing controls

- **Scientific message:** The measured deficit is not a cancellation created by I−iQ and is not created by removing a run mean. Additive DC and an AC spectral notch can coexist.
- **Numerical visuals:** I and Q PSD, imaginary cross contribution, no/global/SPEC-centering controls, and white-plus-offset null. Keep the low-frequency zoom separate from the broad-band view.
- **Equations / quantities:** For hardware Q: S_z(+f)=S_I+S_Q−2Im C_IQ. SPEC-centering changes TM010 PSD1–100kHz by≈1ppm.
- **Provenance:** IQCENT spectral_matrix.npz; DDC centering and synthetic controls.
- **Existing material:** New diagnostics; v40:26/47 are insufficient alone.
- **Disposition:** **ADD / REUSE RESULTS**. Required processing: N06.

#### 46. A primary-IF high-pass can affect only TM010 in the acquired band

- **Scientific message:** The three modes traverse common LF hardware at different primary frequencies. A common physical LF cutoff is not a common notch at final zero.
- **Numerical visuals:** Actual primary/final IF mapping and numerical F(u) evaluated at each mode path; show notch positions outside the final LPF for higher modes.
- **Equations / quantities:** u=f_final+f_LO2; mapped notches0,−43.723,−104.057MHz.
- **Provenance:** H8 parameters/metrics verified against DDC BOR; thesis Fig5.2.
- **Existing material:** v40:9/10 chain can be reused; this frequency-placement argument is new.
- **Disposition:** **ADD / REUSE RESULTS**. Required processing: None.

#### 47. The calibration tone reveals IQ imbalance and image leakage

- **Scientific message:** Near-zero TM010 tones are strongly imbalanced, unlike the science-noise quadratures. A single scalar response is therefore not a complete noise-transfer model.
- **Numerical visuals:** Main/image tone power, gain/phase error table, science I/Q matrix check, and measured/image-inclusive prediction. Keep these as diagnostic extensions.
- **Equations / quantities:** z_out(f)=A(f)z_in(f)+B(f)z_in*(−f)+n_add(f), with source correlations required in general.
- **Provenance:** AUDIT 18calibration runs; tone I/Q≈1.90, phase error≈41deg,image/main≈23%; controls≈0.03%.
- **Existing material:** v40:42,48; retain independently verified relative IQ results, refresh obsolete absolute-reference statements.
- **Disposition:** **UPDATE / REUSE RESULTS**. Required processing: None.

#### 48. Noise generated between stages need not follow the tone response

- **Scientific message:** A calibration tone traverses a path; noise is generated throughout it. Adding a flat floor after every filter would also fill the deep central deficit and is not sufficient on its own.
- **Numerical visuals:** Stage-resolved noise-source diagram with shared downstream filters; use numerical scalar/image comparisons already available, not an unconstrained fitted floor.
- **Equations / quantities:** S_out(f)=Σ_j |H_{j→out}(f)|² S_j(f), plus correlated cross terms where applicable.
- **Provenance:** S6 equivalent-noise approximation; AUDIT; v40:50; H8 interpretation notes.
- **Existing material:** v40:50: rewrite as a conditional architecture with103.4dB bookkeeping.
- **Disposition:** **UPDATE**. Required processing: None.

#### 49. The averaging law motivates LF suppression and exposes slow components

- **Scientific message:** The short-time TM010 slope differs from white noise and from the other modes; the longer-time excess is an additional constraint, not evidence that one simple filter already solves everything.
- **Numerical visuals:** Four-run measured V(T), short-time slopes, white/HP synthetic controls and time-detrended DC/temperature associations.
- **Equations / quantities:** TM010 short slope≈−1.89; white≈−1; illustrative HP≈−1.95. Correlations of levels and differences are separate.
- **Provenance:** DDC interval_results.json, synthetic_mean_stability.png and correlation_controls.png.
- **Existing material:** New diagnostic; replace an inference from the old operational stability time.
- **Disposition:** **ADD / REUSE RESULTS**. Required processing: None.

#### 50. A finite-depth LF response is a testable hypothesis

- **Scientific message:** Introduce the fixed initial LF model after the discrepancies. Separate the calibration response from the science response; the baseline factorization is conditional.
- **Numerical visuals:** Fcal and Fdata curves; pole/zero diagram and a no-double-counting illustration. Parameters fixed, not fitted.
- **Equations / quantities:** F_data(u)=(u²+epsilon fc²)/(u²+fc²), fc12.5kHz,epsilon0.02. kz_cal=k_env sqrt(Fcal); kz_data=0.01 k_env sqrt(Fdata).
- **Provenance:** H8 model.py and parameters.json; fixed±300kHz shoulder factorization with±200/500kHz sensitivity.
- **Existing material:** No old quantitative equivalent; v40:47 mechanism gives context only.
- **Disposition:** **ADD / REUSE RESULTS**. Required processing: None.

#### 51. The initial LF model improves the shape but not every observable

- **Scientific message:** Retain both successes and failures: narrow notch and negative covariance emerge, but depth, complex IQ response, short-time slope and absolute scale still disagree.
- **Numerical visuals:** Numerical H8 PSD/Re/Im correlation panels with unchanged data; concise initial-versus-data table. Reuse without tuning or selecting a favourable baseline.
- **Equations / quantities:** TM010 width27/25kHz; smoothed depth15.1/17.6dB on the frozen five-SPEC estimator; tau maxima1.257/0.926us.
- **Provenance:** H8 PSD_and_complex_correlation.png, metrics.json; reference spectra unchanged.
- **Existing material:** Add after PartIII, not in the original toy construction.
- **Disposition:** **ADD / REUSE RESULTS**. Required processing: N06.

#### 52. A residual floor changes the long-time averaging law

- **Scientific message:** The finite floor produces a crossover towards1/T. This is predicted by the model, but the measured long-time variance still has a much larger slow contribution.
- **Numerical visuals:** H8 epsilon_crossover.png plus absolute and normalized measured/model V(T); clearly separate model extrapolation from observed3.36s records.
- **Equations / quantities:** V(T)=S0[epsilon/T+(1−epsilon)(1−exp(−2πfcT))/(2πfcT²)]. Ideal crossover0.624ms; full response≈0.61ms.
- **Provenance:** H8 metrics and normalized_mean_variance_all_selected_runs.png; data from DDC.
- **Existing material:** New result, no replacement of earlier model/data tables.
- **Disposition:** **ADD / REUSE RESULTS**. Required processing: None.

#### 53. Equal Gaussian spectra do not identify the noise-source location

- **Scientific message:** Finite DC attenuation and a weighted HP branch plus independent downstream-equivalent noise can have identical statistics. The noise observations alone cannot discriminate them.
- **Numerical visuals:** H8 interpretation diagram and two independent-MC checks. State the required downstream shaping and the common total-noise budget.
- **Equations / quantities:** F=epsilon+(1−epsilon)HP; weights sum to1. LF pole time12.732us is distinct from fitted1us envelopes and from coherent ADC DC.
- **Provenance:** H8 interpretations_and_double_counting.png, two-source MC metrics and model.py.
- **Existing material:** v40:50 architecture expanded; no new hardware identification claimed.
- **Disposition:** **ADD / REUSE RESULTS**. Required processing: None.

#### 54. What improved, what remains unresolved

- **Scientific message:** The LF hypothesis is an informative counterexample to the original scalar response, not a final detector model. Calibration factorization, vector IQ and slow nonstationarity remain separate issues.
- **Numerical visuals:** Before/after scorecard M6+C versus H8, with absolute RMS unchanged, V/AC² long-time deficit≈31x, imaginary-correlation discrepancy and baseline-sensitivity range.
- **Equations / quantities:** Increasing epsilon alone makes an already too-shallow notch shallower; no fitted remedy is adopted.
- **Provenance:** C6, H7 decay/sweep diagnostics, H8 metrics; original data fixed.
- **Existing material:** v40:25,42,47–50 conclusions reorganized and updated.
- **Disposition:** **ADD / REUSE RESULTS**. Required processing: None.

#### 55. Measurements that discriminate the hypotheses

- **Scientific message:** Close with specific measurements, reference planes and the observable each one constrains, rather than a promise to tune the simulation.
- **Numerical visuals:** Prioritized matrix: dense complex-IQ sweeps at20/60dB near DC and at the three primary IFs; stage-terminated noise; injected calibrated tone before/after LF; time-resolved gain/temperature/offset logs; repeated long records.
- **Equations / quantities:** Measure H20/H60, main/image transfer matrix and additive-noise contributions independently. Preserve ADC/LO metadata and calibration uncertainties.
- **Provenance:** THESIS chain; CAL sampling gap; PERMODE common-factor audit; DDC slow behavior; H8 non-identifiability.
- **Existing material:** Replaces dispersed next-step bullets in v40:25,33,39,46,50.
- **Disposition:** **ADD**. Required processing: None.

## Backup storyboard — retain detail without breaking the scientific narrative

These are ten explicitly planned backup slides. They are not hidden substitutes for missing
main-deck calculations.

| ID / English title | Scientific message | Numerical visuals and equations | Provenance and disposition |
| --- | --- | --- | --- |
| **A1 — Three operations that must not be called DC removal** | Subtracting mean amplitude, subtracting the complex mean and centering each SPEC are different operations. | A small measured example and definitions `A−mean(A)`, `abs(z−mean(z))`, `z−mean_SPEC(z)`; retain the original v1/v2 semantics. | `analyze_midas_iq_noise.py`, `iq_noise_v2.py`, DDC; **UPDATE** v40:4/26. |
| **A2 — Phase and normalization conventions: adopted and superseded** | Keep the final ADC decision distinct from historical scenarios, and absolute angle distinct from first-valid-sample-referenced angle. | Gain/range ledger and phase-origin table; `2 V_peak/65535`; current5V/2V versus historical2V/2V clearly marked. No old scenario used as evidence for the adopted one. | v40:16/43/51, CAL, C6; **UPDATE**, no new fit. |
| **A3 — Tone calibration and noise PSD have different FFT normalizations** | Coherent-gain correction and noise-window-power correction must not be interchanged. | Exact Hann PSD denominator `fs*sum(w²)`, coherent tone normalization, ENBW≈1.50009bins for the archived16383sample FFT, calibration grid versus science spectral resolution. | Calibration reconstruction, v40:21 and original code; **ADD / REUSE**, verify N07. |
| **A4 — Signed maxima, magnitude fits and window sensitivity** | Preserve historical0.3–4us signed-maxima fit; report0.3–5 and alternative windows as sensitivities, not an improved replacement. | Original curves/table; distinguish `Re(g1)` from `abs(g1)`; original data tau0.926/1.419/1.385us; failed/weak fit labels. | FROZEN, H7/decay_times/fit_results.json; **RETAIN/UPDATE** v40:23/40/41. |
| **A5 — Rare tails: thresholds, samples, episodes and drawing markers** | A drawn point can represent an interval maximum rather than every rare sample. Exact counts need exact threshold provenance. | All3/5/7 thresholds, tail probabilities, counts, episode counts, denominators and bin-edge bounds; no Gaussian-significance language. | D260, C6 tail arrays; **UPDATE** v40:13/17/29/30; N04 required. |
| **A6 — Calibration and intra-run cross-checks** | Independent tone integration and disjoint science windows support robustness, without proving a unique noise-source model. |18raw-tone audit, main/image table, five disjoint run680 windows at SPEC0/245/495/745/995; ratios and full-window definitions. | AUDIT; **RETAIN relative results / UPDATE labels** v40:42/48/49. Historical absolute scalar predictions remain historical. |
| **A7 — Data lineage and compatible products** | Product validation, EOF, configuration matching and acquisition timestamps make the campaign trustworthy; streams are not phase-connected across runs. | Pipeline, HDF5 fields and checksum/source-version manifest; no fictional continuous phase across run boundaries. | v40:2/3/6/7/27, D260, source manifests; **CONSOLIDATE**. |
| **A8 — Reconstruction performance and resource efficiency** | Keep HTC/HPC comparisons with their measured scopes; requested workers are not measured physical core use. | Existing elapsed/CPU/core-use/efficiency table, including three-worker HPC and HTC variants; transfers and code benchmarks labelled separately. | v40:8/45 and original benchmark reports; **RETAIN measured numbers**, no new benchmark. |
| **A9 — Python profiling: where the reconstruction spends time** | The program profile, not WN probes, identifies optimization targets; inclusive child times cannot be added twice. |50SPEC/10.49s input: `FilteredBandChecks.update`84.4s total≈1.688s/SPEC, including FFT/IFFT56.7s and oscillator18.6s; distinguish implemented simulation optimizations from proposed reconstruction work. | v40:44–46 and saved profile; **RETAIN**, no new profiling. |
| **A10 — Operational stability and a descriptive common trend** | A minute-scale tolerance crossing and a common level trend are neither a measured gain nor a microscopic coherence time. | Existing tolerance-bracket table and common-trend residuals; state censoring and that the compared mode contributes to the common median. | v40:31/32/38; **RETAIN definitions**, update stale reference-plane notes. |

## Numerical work still required before producing the presentation

No task below was executed while writing this storyboard. Numerical products must go to a
new external output directory, with source/configuration hashes; no existing step or data
product is overwritten. A new slide layout alone is not a new numerical analysis.

| Task | Work and why it is needed | Inputs / reuse | Proposed validation | Slides / effort class |
| --- | --- | --- | --- | --- |
| **N01 — Common physical and ADC input contract** | Define a parallel presentation-only configuration through M6: shared cavity parameters/temperature, source PSD convention, Gaussian draws, fs, input-plane units and latest ADC coding. Use the known1MHz tone only as a validation setting; declare actual mode IFs separately. Remove permanent tone from noise examples. | Existing S1–S6 code, S6 HDF5, ODB settings; do not mutate historical inputs. Reuse stored source realizations when actually compatible, otherwise store one shared white-noise draw used by all derived stages. | Reproduce original source components under original inputs first; verify power/PSD, source addition before ADC, shared draws and integer ADC mapping. Independent input changes must be listed, not inferred from better data agreement. | 4–16,31; small parallel simulation, not a new raw campaign. |
| **N02 — Complete the observable progression** | Derive consistently rendered time traces, IQ, Gaussian marginals, Rayleigh/CCDF, phase/increments, PSD, Re/Im covariance and block means for cavity-only, receiver-only and total. Existing step figures combine different inputs and lack some observables. | S6 component arrays already provide most underlying numerical samples; S1–S5 provide validation examples. Thermal-only comparisons use physical input-plane axes or explicitly dimensionless shape axes, not hidden display gains. | Common bins and time windows; normalization integrals; properness; nonzero-phase mask; PSD/covariance identity; predicted mean variance with a resolution flag. Quantization only after adding sources. | 4–8,10–15; derived products and short common-input MC if N01 changes inputs. |
| **N03 — Matched raw/centered populations and angular conventions** | Extract matched5-SPEC comparison panels, common I/Q marginals, raw Rice and centered Rayleigh/CCDF, absolute phase and increments. The current full-run C6 HDF5 contains amplitude/phase histograms and a5-SPEC ADC prefix, but no full-run increment histogram. D260 raw amplitude histograms are not centered ones. | C6 saved first5SPEC_ADC_counts, global phase arrays of D260, existing DDC fixed-parameter checks. If exact centered measured samples/curves were not saved, allow only a necessary short prefix reread for the new derived diagnostic; do not claim an exact centered full-run histogram from a2D bin-centre approximation. | Population and duration in each panel; same bin edges/width, valid phase-pair counts, original measured reference untouched. Fixed-moment references are distinguished from descriptive distribution fits already made. | 13,24–25,31,34–37; small derived/sample check. A full-run centered histogram would be a separate larger optional task, not a hidden prerequisite. |
| **N04 — Threshold and tail consistency** | Audit exact empirical versus fitted-Rayleigh thresholds and raw versus centered population. Preserve published data counts; do not label them as newly fitted-threshold counts. For a Rayleigh expectation at an empirical threshold use the actual `T_emp` in `exp(−T_emp²/(2sigma_q²))`. | D260 thresholds/counts; C6 summary moments and saved >5-tail complex samples. Existing data7-tail counts37/40/42 and toy35/58/36 use different threshold constructions and are not automatically a matched test. | Reconstruct actual thresholds and declare any bin-edge count uncertainty. Exact7-count recalculation may use saved tail samples if their stored lower threshold is below the target; do not infer exact3-counts from a coarse histogram. No independent-sample p-value for correlated noise. | 12,29,35–36,A5; typically no raw reread, unless an exact new threshold count is explicitly required later. |
| **N05 — Reference averaging prediction without LF repair** | Compute V(T) for M6 and **M6+C with H8 disabled**, including sampled PSD and finite-record population correction; validate with a short replay of the frozen MC prefix. This result is not currently the H8 calculation. | Existing C6 calibration/source parameters; DDC measured16-SPEC means; adaptive boxcar integration method already tested in H8. Reuse the5-SPEC saved toy to validate replay before extending only to16SPEC. | Compare PSD integration at doubled numerical resolution; white/coloured null controls; `V(T)−V(KT)` where stationary record assumptions apply. Keep analytic expectation and stochastic MC distinct. | 15,31,41–42; no new experimental reconstruction, no full209s MC required. |
| **N06 — Re-render, do not refit** | Split oversized multipanels, standardize colours/labels/bin widths, move performance slides to backup, and build numerical scorecards from existing JSON/CSV/HDF5. Remove stale notes and historical blanket footers. | V40/V21 assets and arrays, D260, DDC, H7/H8 already completed. Relative trends can be retained directly after provenance checks. | Every plotted value traceable to its source; phase origin and Q sign explicit; density integral and counts preserved by rebinning; never upsample a coarse histogram to simulate fine information. | Most UPDATE/ADD-from-existing slides; presentation work plus numerical summaries, no new physics calculation. |
| **N07 — Reference-plane and scope ledger** | Establish a single ledger for ADC/counts, coherent tone normalization, PSD/ENBW, raw/AC moments, Tn applicability, gains and actual versus nominal IF. Explicitly separate the archived M6+C inputs from any parallel refreshed reference. | Source definitions, calibration reconstruction, ODB audit, v40 current body and inherited notes. | Exact ADC rescaling once; raw²=DC²+AC²; model power from PSD; tone/input-RMS convention without an ad hoc3dB factor; no double LPF or FET. | 19–20,31–35,A2–A3; release gate, not a gain-calibration fit. |
| **N08 — Presentation provenance and consistency validation** | Build a per-slide manifest with source commit, data path, hash/version, scope, units, centering, bins and calibration state. Verify body, notes and footers agree. | This storyboard and asset audit; old source manifests. Local untracked v38–v40 generators need a separate documented source snapshot if used for production. | No H7/H8 products in PartI or the reference prediction; no unresolved test marked successful; unchanged original measured-array and fit hashes; no old67.4dB hypothesis in current notes. | Entire deck; source/documentation validation, no new reconstruction. |

### What can be assembled immediately from existing results

- The experiment/campaign chapter, DC trends, band trends and correlation controls largely
  need re-rendering and scope labels, not new measured analysis.
- The current absolute-comparison tables and original PSD/covariance curves can be retained
  with correct raw/AC and population labels. Their disagreements are part of the result.
- The sweep-gap, separate-IQ, DC-processing controls and initial LF model are already
  quantitative. They belong after the discrepancy is established.
- The physical construction needs the most normalization and common-input work; copying
  the old140/143dB,±5V examples would violate the requested consistency.
- A matched **baseline** mean-variance prediction and matched angular/centered-distribution
  panels are genuine missing products. The storyboard does not describe them as complete.

## Normalization and interpretation gates before final slide production

| Gate | Verified issue | Required treatment; no artificial agreement |
| --- | --- | --- |
| **G1 — Identity of the reference** | Historical S6 combines physical source inputs with143dB/±5V and nominal1MHz readout. C6 adds measured curves and the updated range/LF ledger. | PartI ends at M6; PartIII introduces M6+C. If common-input regeneration changes a declared input, use a new parallel version and preserve the archived comparison. |
| **G2 — ADC physical scale** | All260science BORs inspected have±2V on IQ;183calibration source runs used in reconstructed curves have±5V. Existing v2 voltages were stored with±5V. | Science V×0.4 and V²×0.16 once. Raw science scale4/65535, archived calibration10/65535. Ratio/phase/counts unchanged. Do not apply0.4 again to already scaled kz or diagnostics. |
| **G3 — 65535 versus65536** | Historical pedagogical ADC examples quantize with2^16; current data conversion and calibrated MC use65535. | Use the declared current coding for new ADC illustrations; retain old code/results as historical. The tiny numerical distinction is not a tunable normalization fix. |
| **G4 — Gain budget and reference plane** | Arbitrary140dB, nominal143dB, historical67.4dB+kz, and current103.4dB with LF correction are different cases. Stale67.4dB notes remain in v40. | Current case: RF103.4dB, k_data=k_cal/100.63.4dB is only algebraically equivalent when keeping k_cal unchanged. No extra36dB subtraction, no cascade of143dB and kz, no per-mode fitted gains. |
| **G5 — Complex voltage, tone RMS and spectral factors** | The simulation convention is `E(abs(z)²)/R=integral available PSD`; kz uses a known RF RMS tone and complex output. A factor2 cannot be guessed from an amplitude mismatch. | Trace the actual tone-integrated coefficient and reference VRMS through the code; keep available power, real carrier peak and matched complex RMS separate. Do not introduce an ad hoc3dB term. |
| **G6 — Coherent FFT versus noise PSD** | Archived tone chunks contain16383samples despite nominal16384; Hann coherent gain, ENBW and full-window PSD normalization differ. | Keep existing reconstructed integrated-tone kz and audited noise ENBW. The original5-SPEC science estimator remains unchanged; document each denominator. |
| **G7 — Raw, centered and descriptive Rayleigh RMS** | v40 data Rayleigh RMS corresponds to raw total magnitude, while DDC AC RMS removes the complex mean. | Run680 data raw RMS32.262765/20.783883/13.733291mV; AC RMS32.259606/20.748636/13.733116mV. Both are valid but must not be swapped. Preserve full-run versus windowed PSD RMS separately. |
| **G8 — Threshold definitions** | Data published local thresholds use empirical mean(A)+k std(A); toy tail summaries use fitted-Rayleigh moments. Verified relative differences reach about−0.0669% at7 in TM011. | Preserve exact thresholds and exact counts. If comparing to Rayleigh, evaluate probability at the actual threshold; otherwise perform a separately documented matched count. Never silently relabel a rare-tail table. |
| **G9 — Frequency planes and the LPF** | S6/C6 use a nominal1MHz cavity IF; configured final cavity IFs are1.250/1.248/1.256MHz. Calibration and science LO offsets differ. | Pedagogical1MHz tone remains a test. A refreshed physical readout uses the actual map with no shift fitted to a PSD. Measured kz replaces the assumed LPF; it is not multiplied by it again. Record whether the tiny receiver-dominated cavity-IF difference changes the chosen reference. |
| **G10 — Common factors are conditional** | Three distinct kz curves are already used; common RF gain, Tn and LF20/60 ratio do not imply three equal physical chains. Tn was measured without TWPA and its run applicability is not proven. | Label independent cavity/calibration measurements separately from conditional gain/Tn/setting-ratio assumptions. Figures6.3/6.4 motivate frequency dependence but are not permission to invent per-mode numbers. |
| **G11 — Phase and lag convention** | Global phase arrays are absolute atan2; some historical phase figures reference the first valid run sample. Raw lags1/10/100 and filtered4us increments are different observables. | Prefer a common absolute ADC frame for comparison; a fixed coordinate conversion is not a fitted rotation. Preserve valid-pair masks, source lag and signed Q. Keep old phase results as archived if re-rendering the new convention. |
| **G12 — LF hypothesis is not a calibration measurement** | The H8 shoulder bridge conditionally removes the calibration feature before applying Fdata. The central sweep is unsampled; nearby broad loss is measured. | The factorization is explicitly an H8 hypothesis with sensitivity, not part of the M6 source construction or a replacement for measured kz. Avoid double suppression and do not select a shoulder width because it fits tau better. |
| **G13 — Noise floor versus coherent DC** | Epsilon is a stochastic PSD floor, not the observed coherent DC²/AC² ratio. A mean can coexist with an AC notch. | Separate mu, AC spectrum and additive source locations. Do not infer epsilon from a run mean or subtract a covariance constant to fix a negative tail. |
| **G14 — Short-term statistics versus slow drift** | Raw long-term correlations shrink markedly on differences; short-window V(T) contains finite-record limits and long-time slow excess. | Keep linear/cubic trend and difference controls, counts/coverage and finite-record correction. No causal temperature statement or iid significance from hundreds of correlated points. |

Not every gate requires a new measurement before making slides. Known conventions can be
resolved from the code and products; genuinely unmeasured gain/response quantities remain
explicit uncertainties in the presentation. They must not be replaced by fitted values
merely to make an absolute table agree.

## Provisional comparison scorecard to preserve

This is a planning snapshot, not a newly performed analysis. Final values must be read
from the stated source/population after N03–N07.

| Observable | Current reference evidence | Presentation statement |
| --- | --- | --- |
| Absolute level | C6 predicts27.173/13.701/8.406mV; measured AC and raw differ as listed above. | **Not reproduced under adopted common calibration/noise assumptions.** |
| Normalized amplitude family | Approximately Rayleigh/Rice; measured pseudo-covariance≈4–5%, DC nonzero. | **Approximate family agreement, not exact properness or absolute calibration.** |
| Rare counts | Existing exact tables have threshold-convention differences. | **Retain counts; matched significance not established by the current table alone.** |
| Raw marginal phase | Offset preference and ADC quantization matter; centred toy has no measured offset by construction. | **Different; not evidence of a coherent science tone.** |
| Matched phase increments | Data histograms exist; full-run C6 increment histogram is not saved. | **Pending the explicitly scoped matched extraction.** |
| TM011/012 spectral/correlation shape | Much closer than TM010; imaginary correlation remains a useful failure mode. | **Partial agreement; show real and imaginary parts.** |
| TM010 scalar-reference notch | About247kHz versus25kHz measured. | **Not reproduced; retain the discrepancy before showing H7/H8.** |
| Signed envelope times | Data reference preserved; original calibrated toy TM010 is not well described by the exponential. | **No reliable toy TM010 decay from the failed fit.** |
| Coherent DC | Source-only toy assumes zero mean; data have offsets and long-term motion. | **Not included in the reference, not a fitted component.** |
| Baseline mean-variance curve | DDC data exist; M6+C prediction without LF repair is not yet the H8 result. | **Compute N05 before claiming reference agreement or disagreement quantitatively.** |
| H8 initial LF shape | Width27/25kHz, depth15.1/17.6dB; negative correlation emerges. | **Improvement after comparison, not a definitive solution.** |
| H8 long-time averaging | Crossover≈0.61ms predicted; normalized V(0.419s) still≈31times below measured TM010. | **A simple residual white floor is insufficient for all slow behavior.** |

## Production sequence after storyboard review

1. Freeze the reference/input/normalization ledger (N01,N07) and document its differences
   from historical products. Keep all existing results intact.
2. Produce the missing construction observables and matched diagnostic panels (N02–N05)
   in a new external directory. No unconstrained new fit and no new production raw campaign.
3. Assemble/re-render the independent data chapter and the existing post-comparison
   diagnostics (N06), maintaining common palette and source badges.
4. Validate the whole deck against a per-slide numerical/provenance manifest (N08),
   including notes and footers, then render a new versioned presentation.

**Current deliverable stops here: storyboard and asset audit only.** No renderer or new
simulation was run for this proposal; the only rendered pages inspected were from the
already existing v40 PDF. The complete existing-slide disposition is in
[the companion asset audit](flash_scientific_asset_audit_cc67048.md).
