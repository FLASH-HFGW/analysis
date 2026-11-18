# Step 10D — Spectral and I/Q residual diagnostics

Read-only analysis of Step 10C aggregates, commit 84b434f. Step 9D and 10A supply only their already computed spectral components for the high-IF budget. The BLP curve is the archived Step 9B manufacturer table. No new raw reads, noise draws or corrective calibration. All results are conditional on the common post-ADC mask and the frozen H/N responses.

## Normalized complementary spectrum

For the signed DFT, η(f) = 2 C(f) / [S(f)+S(−f)]. The ratio is even and is undefined in the masked interval |IF| < 100 kHz. Spectral curves use the ratio of sums over 128 neighboring positive bins and their exact mirrored PSD bins, without averaging individual ratios. For each symmetric interval B, η_B = ∫_B C / ∫_B S. This equals the power-weighted local η over B. The primary interval estimates use the exact Step 10C grid. Group dispersion uses 50 groups of 20 consecutive SPECs, assigning pre-aggregated 128-bin groups by their centers. Boundary bins therefore differ slightly from the exact interval definition. The paired difference between the group interval and the same group's full-mask η is also reported, with SD-derived descriptive SE. These are comparative spreads, not tests based on independent ADC samples or assumed independent spectral bins. [η plot](eta.png), [interval estimates and group dispersion](eta_intervals.csv)

| Mode | Re η over the intervals | Im η over the intervals | Edge Re difference from paired full mask |
| --- | ---: | ---: | ---: |
| TM010 | −0.03004 to −0.02390 | −0.03199 to −0.03106 | −0.00468 ± 0.00008 |
| TM011 | −0.06053 to −0.02967 | −0.03015 to −0.02994 | −0.02435 ± 0.00009 |
| TM012 | −0.03819 to −0.01201 | −0.03080 to −0.03054 | +0.01649 ± 0.00008 |

Edge corresponds to |IF| = 2.25–2.50 MHz. Re η is strongly frequency dependent in all three modes, with opposite trends near the edge for TM011 and TM012. Im η is much flatter. TM010 nevertheless shows a resolved edge shift of +0.00066 ± 0.00010 against its paired full-mask value. The smaller Im excursions in TM011/TM012 are comparable to a few descriptive SEs and are not evidence of exact constancy. H and N serve as finite-sample controls for the theoretically zero complementary spectrum of a proper process.

## Moment-equivalent covariance and phase

The matrix is in hardware axes (I,Qhardware), with z = I−iQhardware. Its RMS amplitude ratio is sqrt(var I / var Q), and rho = cov(I,Q)/sqrt(var I var Q). As a sinusoidal diagnostic only, if Q hardware leads I by π/2 + δ, rho = −sin δ. Thus δ = −asin rho in the hardware convention. Changing the sign of Q reverses rho and the signed error in the opposite quadrature convention. The principal axes diagonalize the covariance, with angles measured from +I toward +Qhardware modulo 180°. The two RMS values are square roots of the eigenvalues. These are effective broadband output moments and cannot distinguish gain/phase imbalance, colored sources or correlated noise. [Covariance table](iq_covariance.csv)

| Mode | I/Q RMS | ρ (hardware Q) | Equivalent δ | Major/minor RMS (mV) | Major axis |
| --- | ---: | ---: | ---: | ---: | ---: |
| TM010 | 0.9750 | 0.03174 | −1.82° | 22.886 / 21.975 | 64.32° |
| TM011 | 0.9644 | 0.03009 | −1.72° | 14.709 / 14.032 | 70.15° |
| TM012 | 0.9719 | 0.03065 | −1.76° | 9.709 / 9.312 | 66.44° |

The integrated η equals the temporal complex pseudocovariance divided by total centered power. The CSV precision around cancellation is included in the numerical cross-check.

## Constant I/Q map test

For proper input x with PSD P, a constant real-linear I/Q map is z = a x + b x*. With disjoint proper spectral increments:

```text
S(f) = |a|² P(f) + |b|² P(−f)
C(f) = ab [P(f) + P(−f)]
η(f) = 2ab / (|a|²+|b|²)
```

The symmetric PSD shape is invariant up to one constant gain. The normalized antisymmetric shape changes only by a real factor with magnitude sqrt(1−|η|²). Its sign depends on the orientation of the real map. The observed η excludes the exact constant-map description for either proper H or proper N. Also, on the common mask, the normalized symmetric PSD total-variation distances from data are **0.0050–0.0113** for H and **0.0812–0.0890** for N. A constant I/Q map cannot remove these differences. [Constant-map diagnostics](constant_map.csv), [intervals](constant_map_intervals.csv)

For descriptive residuals only, the diagnostic uses the global η from the output moments and the analytical input shape. The two possible signs of the odd term are reported separately. Neither a complex gain calibration nor a fitted PSD correction is used. Global moments fix combinations such as ab and the ratio of principal spreads, while input phase, overall level and orientation need independent reference information. Frequency-dependent mixing, nonproper input, correlated or downstream noise cannot be disentangled using these spectra and moments alone.

## Absolute high-IF budget

[High-IF components](high_IF_components.csv) integrates the archived Step 10A analytical terms on the exact Step 10C grid with no rescaling. Step 9D independently gives the same bin-interval totals within 0.025% for the broad interval on its odd FFT grid. Origin is tracked separately as direct main, direct secondary RF image, ADC aliases of each, and thermal cavity. The nominal and hybrid simulations use the same RF normalization and image/main hypothesis.

| Mode | Data/H (dB) | Data/N (dB) | Alias fraction H / N | Data/N, 2.25–2.50 MHz (dB) |
| --- | ---: | ---: | ---: | ---: |
| TM010 | +1.491 | +2.552 | 14.19% / 3.91% | +5.429 |
| TM011 | +1.400 | +2.050 | 11.93% / 3.90% | +4.921 |
| TM012 | +1.870 | +2.327 | 11.27% / 3.92% | +5.161 |

Below 2 MHz within this comparison, N is closer in absolute power. The 2.25–2.50 MHz deficit drives the broad-band reversal. Direct RF image power is near direct main power for TM011/TM012, and TM010 lacks the secondary image. The direct-term H–N difference explains about 49/38/22% of their integrated high-IF separation, respectively. The balance comes predominantly from their different calculated ADC aliases. This attribution is within the two predictions. The observed ADC PSD does not resolve those sources independently.

The nominal BLP table has 0.40 dB loss at 1.8 MHz, 2.93 dB at 2.3 MHz and 8.32 dB at 2.5 MHz, while the nominal cutoff summary gives 3 dB at 2.5 MHz. The steep tabulated roll-off is consistent with the shape of N. The flatter measured total ADC PSD is inconsistent with N's predicted edge attenuation **under its fixed upstream and loading assumptions**. This comparison does not measure the installed BLP response. Complex source/load mismatch, cables and ADC input response can alter loaded magnitude and phase, including beyond Nyquist where they affect alias contributions. Independent swept measurements at the ADC plane and complex reflection/termination measurements are required to separate these effects. [Absolute PSD and tabulated BLP response](high_IF.png)

## Back-action, reflections and noise waves

Step 10C establishes a nonzero output complementary spectrum and shape/level residuals. This evidence alone provides neither a reverse-path measurement nor a decomposition into reflections, mixer conversion imbalance, correlated receiver noise, and back-action. A future bidirectional calculation needs calibrated complex multiport scattering in both directions, installed cable phases and terminations, detector input impedance, LO-pumped conversion matrices including sidebands, noise-wave auto/cross spectra, and relevant temperatures at common planes. In particular, establishing back-action would require measuring reverse noise and its transfer back to and from the cavity under science loading. No such model or substitute correction is introduced here.

## Reproduction

The complete products, including the binned η curves and input hashes, live in `../analysis-work/Run2/simulation/step10d/`. Run from the checkout with NumPy, h5py and Matplotlib and choose a new output directory:

```bash
python3 simulation/step10d/analyze.py ../analysis-work/Run2/simulation /path/to/new-step10d
```
