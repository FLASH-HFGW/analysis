# FLASH — compact scientific presentation index

Proposal replacing the 55-slide structure of commit67ecfae. The scientific storyboard and
asset audit from that commit are retained as technical documentation. This index proposes
28 main slides; existing methodological, calibration-history and computing details remain
supplementary material. Titles below are in English. No new analysis, fit, full-run simulation
or presentation has been produced to prepare this index.

## I — Toy simulation: progressive construction (1–10)

| # | Title | Scientific message | Figure to use |
| ---: | --- | --- | --- |
| 1 | **FLASH noise: model, measurements and open questions** | Follow a single story: construct the toy, characterize data, compare, then test explanations. | Four-part roadmap, with the three cavity modes identified. |
| 2 | **The acquisition chain and the quantities we measure** | Distinguish the physical sources from their mapping through the instrument; define I−iQ and ADC units once. | Simplified chain from v40:10 / thesis Fig5.2, with cavity, receiver, IQ mixer, LF amplifiers, mode paths and ADC. |
| 3 | **Step 1 — A coherent tone validates I/Q acquisition** | A known calibration tone verifies sign, quadrature, frequency translation and sampling; it is not permanent science noise. | Step1 time traces, IQ circle and signed FFT, with current ADC convention. **★** |
| 4 | **Step 2 — The resonant cavity and readout filtering** | Show the response of the resonator and how filtering/down-conversion changes a known input; the tone remains a validation probe only. | Step2 response/PSD panels and sampled I/Q; show the declared calibration probe separately from stochastic input. **★** |
| 5 | **Step 3 — Separating filtered input noise and receiver noise** | Introduce the equivalent electronic contribution in the validation chain without confusing it with cavity emission. | Step3 component spectra and shared-realization trace; label the coherent probe explicitly. **★** |
| 6 | **Step 4 — Thermal cavity emission: no coherent tone** | Replace the validation input with physical cavity thermal emission; the tone is now absent. | Thermal-only PSD, stochastic I/Q trace and IQ cloud using the common physical inputs. **★** |
| 7 | **Step 5 — Add equivalent receiver noise** | Add an independent receiver source to the same cavity realization; retain the total physical noise budget. | Cavity, receiver and total PSD with common axes; IQ or time-trace inset. **★** |
| 8 | **Step 6 — The three-mode physical model** | Use the thesis cavity parameters and measured temperature; state the common receiver-noise assumption. | Updated physical-parameter table from v40:9 and three-mode source-budget panels. **★** |
| 9 | **Mapping the toy onto the real acquisition chain** | Measured, mode-specific kz maps the toy to ADC; RF103.4dB, LF60→20dB and ADC ranges are applied once, without hypothetical LF changes. | Current v40:10 normalization diagram plus the three distinct calibration curves from the per-mode audit. |
| 10 | **Expected observables of the reference toy** | The noise model predicts approximately Gaussian quadratures, Rayleigh amplitude, angular statistics, PSD and complex correlation. | Selected current v40:11/13/15 panels and saved step6 arrays; concise observable summary, no step7/8 curves. |

## II — Experimental data: consolidated long-term results (11–14)

| # | Title | Scientific message | Figure to use |
| ---: | --- | --- | --- |
| 11 | **The experimental dataset and analysis definitions** |260complete runs680–939; distinguish raw amplitude from DC and complex-mean-subtracted AC. | v40:28 coverage headline plus the essential definitions from v40:4; label smaller PSD/correlation windows separately. |
| 12 | **Noise level and temperature over the campaign** | Noise and temperatures drift; temporal association alone does not establish causality. | Consolidated v40:28/34/37 long-term level and temperature panels. |
| 13 | **Frequency-resolved stability and run-mean subtraction** | The central band and sidebands provide complementary stability diagnostics; removing a mean does not remove all LF fluctuations. | v40:35/36/39 nine-band and raw-versus-AC centre-band trends; use ADC or relative quantities. |
| 14 | **Distribution stability and rare tails** | Stable normalized shapes can coexist with changing absolute levels; local and fixed thresholds tell different stories. | v40:29/30/31 local/fixed rates and shape-stability summary; retain the exact published threshold definitions and counts. |

## III — Original toy simulation versus data (15–20)

| # | Title | Scientific message | Figure to use |
| ---: | --- | --- | --- |
| 15 | **Absolute amplitude: prediction versus measurement** | Keep the latest adopted normalization and show the residual scale differences without gain adjustments. | v40:13/14/25 amplitude histograms and compact RMS/Rayleigh-scale table; raw RMS and AC RMS labelled separately. |
| 16 | **Phase and IQ shape: agreement and differences** | The scalar toy is nearly circular and centred; measured offsets, imbalance and angular structure remain visible. | v40:15/17/18 phase/IQ panels and balance table; retain one stated phase convention. |
| 17 | **Power spectra: the TM010 discrepancy** | The original calibrated toy predicts a much broader central depression than the data. | Unchanged v40:20/21 matched PSD arrays, full range and TM010 central zoom, with common axes. |
| 18 | **Complex autocorrelation, including negative values** | Compare real and imaginary parts; negative Re(g1) is allowed but its shape must follow the correct PSD. | Original v40:22/24 covariance arrays; render the imaginary part from the existing saved complex arrays. |
| 19 | **Characteristic times and fit limitations** | Preserve the original data fits and distinguish fitted envelope times from cavity poles and averaging times. | v40:22/40 signed-upper-maximum fits and table;0.3–4us fits,0–10us display; mark the original toy TM010 fit unresolved. |
| 20 | **What the reference reproduces—and what it does not** | Keep approximate distribution-shape agreement, absolute-level discrepancies, IQ differences and the TM010 spectral/correlation failure in one scorecard. | Reorganized v40:25 summary, populated only with existing results; no step7/8 modification of the reference. |

## IV — Possible explanations and limits (21–28)

| # | Title | Scientific message | Figure to use |
| ---: | --- | --- | --- |
| 21 | **Calibration and science use different LF settings** | The nominal60→20dB correction is known; equality of the frequency-response shapes is not demonstrated. | Reuse the simplified chain, highlighting the LF amplifiers and their calibration/science settings; per-mode primary IF labels. |
| 22 | **What the calibration sweep resolves near zero** | The central interval is unsampled, but attenuation already exists at measured nearby points: interpolation alone cannot explain the whole mismatch. | Existing step7 sweep-constraints figure with actual tone points and the shaded±49.18kHz gap, alongside the measured noise zoom. |
| 23 | **DC offset is not the origin of the broad depression** | A persistent, drifting IQ centre coexists with the AC notch; centring does not create a25kHz deficit. | Existing DC trajectory/trend and no/global/SPEC-centering controls; separate-I/Q PSD inset if space permits. |
| 24 | **The averaging law provides an independent clue** | At short times TM010 approaches T^-2 behaviour while the other modes follow roughly T^-1; slower components remain at longer times. | Existing step7 block-mean variance and white/HP controls; slopes≈−1.89 versus≈−1, with interval and resolution limits. |
| 25 | **IQ imbalance and noise-source locations matter** | Tone transfer and noise transfer need not be identical: image leakage and noise introduced between stages are distinct missing ingredients. | v40:48 main/image table plus the simplified stage-noise diagram from v40:50, with current normalization labels. |
| 26 | **A primary-IF high-pass: a physical hypothesis** | A common LF response can affect only TM010 inside the final acquired band; this is a hypothesis introduced after the comparison. | Existing analytic response F=(f²+epsilon fc²)/(f²+fc²), fc12.5kHz,epsilon0.02, with primary/final IF mapping and the simplified chain. |
| 27 | **Step 8: improvements from the initial LF model** | The narrow notch, negative covariance and crossover towards T^-1 emerge without fitting parameters or changing the original reference. | Existing step8 PSD/correlation comparison and analytic crossover figure; width27versus25kHz and crossover≈0.61ms. |
| 28 | **Remaining discrepancies and discriminating measurements** | Step8 is not a solution: depth, long-time variance, complex IQ response and absolute levels still disagree; noise spectra alone do not locate an independent source uniquely. | Existing step8 residual scorecard: depth15.1versus17.6dB and normalized long-time variance≈31times too low; end with dense complex sweeps at both LF settings and stage-noise/gain monitoring. |

## Only indispensable outstanding numerical work

**★ Common-conditions figures for steps1–6.** Reuse the saved physical components and
realizations wherever compatible. Where historical inputs differ, regenerate only the
short pedagogical examples needed to show the progressive construction with one set of
physical parameters, unit conventions and current ADC coding. Remove arbitrary140dB and
nominal143dB ADC figures from the main presentation. Show physical input-plane quantities
before the measured kz mapping, then ADC quantities after that mapping; do not introduce a
new display gain to make the thermal trace visible. The tone amplitude remains a declared
calibration probe, not a stochastic scientific component.

All other proposed figures and numerical conclusions already exist. Cropping/splitting
panels, extracting the imaginary covariance, applying the documented ADC conversion once,
standardizing bins/colours and rebuilding tables from saved arrays are **figure preparation**,
not a new analysis campaign. Keep the original measured curves, fits and counts unchanged;
resolve labels using the existing technical audit rather than launching new fits or counts.
No new full-run simulation, extended raw reconstruction, baseline mean-variance campaign,
full-run centred histogram or new angular fit is required for this28-slide presentation.

Supplementary material can retain the detailed normalization/threshold audit, fit-window
sensitivity, additional diagnostics, the two equivalent LF-noise interpretations and the
HPC/HTC/Python profiling results. N01–N08 and G1–G14 remain technical documentation, not
separate presentation topics. No new reference-model acronyms are introduced in the slides.
