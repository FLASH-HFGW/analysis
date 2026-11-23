# FLASH Dataset 2 longitudinal scientific report

## Coverage and integrity

All 24 timestamp-selected runs passed raw validation. The original Run 1429 and the initial three receipts were reused. The other twenty runs were read once each, in five chronological four-run batches. CRC and EOR, raw/archive sample indices and counts, serial continuity, ADC conversion, exposure, ROOT RMS and sparse-group consistency were checked. PPS pulse lists and rejections agreed with the archive. Timing comparisons remain in received-sample coordinates. No absolute UTC or inter-channel group delay is calibrated.

Runs 1429–1748 span 19 h 20 min 53 s from first BOR to last EOR. The sample represents twenty nearest-hour points, 1529/1629/1729 controls and the reconstructed endpoint. Intermediate reconstruction gaps and later raw-only runs remain separate. ROOT-only controls 1669, 1670 and 1671 bracket the retune without a raw pass.

## Tail rates and clustered samples

| Mode | Epoch | ADC RMS (mV), median | Integrated PSD (V²), median | T3 / T5 / T7 rates per s, medians | T7 / matched Gaussian, min / median / max |
|---|---|---:|---:|---:|---:|
| TM010 | pre | 23.0605 | 0.000531801 | 3.539e+04 / 597 / 6.523 | 12.183 / 12.899 / 13.354 |
| TM010 | post | 23.3322 | 0.000544387 | 3.523e+04 / 588.4 / 6.18 | 12.148 / 12.618 / 13.555 |
| TM011 | pre | 14.9367 | 0.000223102 | 3.308e+04 / 346.7 / 1.173 | 2.820 / 3.229 / 3.444 |
| TM011 | post | 15.0624 | 0.000226872 | 3.307e+04 / 345.2 / 1.173 | 2.815 / 3.268 / 3.389 |
| TM012 | pre | 9.2189 | 8.49875e-05 | 3.657e+04 / 545.6 / 3.643 | 13.625 / 14.863 / 16.066 |
| TM012 | post | 9.2694 | 8.59251e-05 | 3.654e+04 / 545 / 3.591 | 13.558 / 14.568 / 15.408 |

The selected runs bracketing the retune have TM012 T7/Gaussian ratios 13.625 (1666) and 14.846 (1676). The epoch medians are 14.863 and 14.568.

The Gaussian expectations use measured mean and covariance and are marginal sample counts. The epoch medians describe the sample and can reflect smooth time trends and settings shared with the retune. Neither the sample ratios nor the shifted tuple counts are independent-event significance estimates.

For the local RMS diagnostic, the original threshold is multiplied by the RMS of each one-second interval divided by full-run RMS. The common-support result counts above the larger of that threshold and the original global threshold. Where the scaled threshold is lower, missing below-global amplitudes make the result a lower bound. The exact-local exposure fraction and all 1 s counts are retained. Cluster multiplicity and peak distributions are tabulated in 10 s bins for all seven tested gaps.

## Coincidences

| Window (µs) | Tuple | Observed | Shifted mean | Shifted range |
|---:|---|---:|---:|---:|
| 1 | TM010--TM011 | 5 | 0.05 | 0–1 |
| 1 | TM010--TM012 | 1 | 0.15 | 0–1 |
| 1 | TM011--TM012 | 1 | 0.00 | 0–0 |
| 1 | triple | 0 | 0.00 | 0–0 |
| 2 | TM010--TM011 | 5 | 0.15 | 0–1 |
| 2 | TM010--TM012 | 1 | 0.45 | 0–2 |
| 2 | TM011--TM012 | 1 | 0.00 | 0–0 |
| 2 | triple | 0 | 0.00 | 0–0 |
| 5 | TM010--TM011 | 5 | 0.40 | 0–3 |
| 5 | TM010--TM012 | 1 | 1.30 | 0–3 |
| 5 | TM011--TM012 | 1 | 0.15 | 0–2 |
| 5 | triple | 0 | 0.00 | 0–0 |
| 10 | TM010--TM011 | 5 | 0.90 | 0–3 |
| 10 | TM010--TM012 | 5 | 3.20 | 0–6 |
| 10 | TM011--TM012 | 1 | 0.35 | 0–2 |
| 10 | triple | 0 | 0.00 | 0–0 |
| 100 | TM010--TM011 | 12 | 8.10 | 2–13 |
| 100 | TM010--TM012 | 24 | 23.95 | 15–33 |
| 100 | TM011--TM012 | 7 | 5.35 | 1–11 |
| 100 | triple | 0 | 0.00 | 0–0 |

All twenty circular shifts use identical offsets across runs; the pooled control table sums corresponding offsets. The results describe accidental-background scale and preserve the protected exposure, with tuples allowed to share clusters.

## The TM012 line across the Run 1670 LO retune

The leading non-DC spectral bin is at -492,750.5 Hz before and -463,750.5 Hz after the retune. ROOT-only controls show the transition between 1669 and 1670 and persistence at 1671. The full 5 MHz screen used the native 100 Hz ordered PSD, ranked local maxima against a 201-bin median, and measured occupancy using the checkpoint's per-window normalization.

Pre-retune versus post-retune occupancy ranges are 208–209 / 209 and 206–209 / 209. Local ratio min / median / max is 3.631 / 3.675 / 3.723 before and 3.589 / 3.615 / 3.645 after. Mean excess power of the selected 100 Hz bin, in V² at the ADC, has min / median / max 4.435e-09 / 4.582e-09 / 4.663e-09 before and 4.316e-09 / 4.495e-09 / 4.544e-09 after. This bin-level comparison retains the local background and does not estimate calibrated RF power.

The verified main conversion coordinate is fRF = LO₁ + LO₂ + fADC. The −9 kHz primary and +20 kHz secondary steps predict −11 kHz in digital frequency for a fixed RF tone on that branch. The observed +29 kHz is consistent with the alternate image coordinate fADC + LO₁ − LO₂, which gives the same nominal 8.6409922495 GHz in both epochs. The alternate coordinate is a mixing hypothesis, separate from the verified main-branch calibration. The strength and occupancy support a corresponding feature, but an image response and a retune-linked internal mixing product both remain possible.

The full-band table records ranked candidates as well as the old IF and both ±11 kHz neighborhoods. The original bin loses occupancy, while the displaced bin retains it. The two epoch summaries cannot isolate an independent intensity effect from gain, line-bin alignment, thermal conditions, or elapsed-time changes.

## Temperatures and next tests

The five stage channels are archived with measurement validity and timing support. Run median/minimum/maximum tables describe within-run variation and between-run evolution. Pump settings remain fixed in the selected metadata. The 4 K sensor measures a stage and is used as a stage proxy. Correlation with temperatures or the retune cannot establish a physical cause.

An independent two-LO sweep with injected tones at both sidebands would test the image-coordinate explanation and measure conversion gain near the line. A separate joint noise diagnostic should use time-dependent per-mode means and improper covariance, temporal correlation and cross-channel dependence; preserve the observed line and timing gaps in sensitivity checks before interpreting tail and coincidence significance.

## Input and resources

The continuation used 186,474,829,005 compressed bytes, 3120.938 s process wall and 2991.674 s CPU. Total successful raw input across the 24 runs was 223,731,797,692 bytes over 3613.313 s raw streaming. Peak process RSS was 571.4 MiB. The scoped ROOT reads requested 2,963,895,208 bytes in 116.882 s. CPU was timed for the continuation. The physical mount traffic and early Run 1446 retry bytes are unavailable.

The complete English deck is available locally under `presentation/longitudinal_final/`. Compact CSVs, code, validation receipts and the manifest are versioned. The earlier decks remain in their original paths, with the initial longitudinal manifest tied to its checkpoint commit.
