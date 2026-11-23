# FLASH Run 1670 targeted scientific report

## Recorded LO chronology

| ODB variable under /Equipment/LocalOscill/Variables | 1669 (Hz) | 1670 and 1671 (Hz) | 1670 BOR key last-written UTC |
|---|---:|---:|---|
| freq RS | 8,743,664,000 | 8,743,655,000 | 2026-11-21T08:21:56+00:00 |
| freq Teled Ch1 | 43,331,000 | 43,330,000 | 2026-11-21T08:21:59+00:00 |
| freq Teled Ch2 | 102,179,000 | 102,199,000 | 2026-11-21T08:22:02+00:00 |

The preceding EOR was 2026-11-21T07:59:49+00:00. Run 1670 BOR was 2026-11-21T08:24:31+00:00, and its one LOSC bank was recorded at 2026-11-21T08:24:31+00:00. SHA256-verified BOR/EOR and archived LOSC frequencies agree per run. The writes precede BOR and are bracketed by the neighboring runs. Physical application timestamps and short excursions between logged snapshots cannot be recovered.

The locally archived LocalOscill frontend reference shows Rohde & Schwarz SMA100B, Teledyne T3AFG500 channels 1 and 2, and Keysight EXG pump handlers. The periodic frontend applies changed ODB settings to the devices and handles output toggles at run boundaries. Its LOSC bank records ODB, with no continuous frequency readback. The reference identifies the control path. The deployed source version, exact hardware write times and operator versus automation attribution are unresolved. The nominal VNA setpoints and Auto_detect_status Completed were written at 08:21:26 UTC, 30 seconds before the first LO write. That sequence is consistent with updated resonance settings preceding retuning. The snapshot alone cannot identify the actor or whether the LO setting was applied by an automatic retune workflow.

Pump frequency, setting and logged enabled state at BOR/EOR are unchanged (7.891 GHz, −6.1, enabled). The pump on/off key was written between runs, so intermediate pump behavior is unresolved. Primary LO power setting 19 and both 4 Vpp secondary settings are unchanged. Archived digital centers remain +1.25 MHz, and nominal RF setpoints move −9/−10/+11 kHz. Sampling stays 5 MS/s with ADC ±2 V and channel pairs (0,1), (2,3), (4,5), complex convention I−iQhardware. The archived NetBox settings and With_LO/With_TWPA flags have no value changes across the tested snapshots.

## Full-run statistics

| Mode | RMS (mV) | Improperness ratio | Exact T3 / T5 / T7 | T7 / matched Gaussian | Prefix ACF envelope τ (µs) |
|---|---:|---:|---:|---:|---:|
| TM010 | 23.23967 | 0.14216 | 7335189 / 119563 / 1244 | 11.927 | 0.753 |
| TM011 | 15.04444 | 0.11316 | 6905328 / 71122 / 221 | 2.951 | 1.438 |
| TM012 | 9.25498 | 0.06080 | 7612966 / 112398 / 766 | 14.858 | 1.411 |

Means, variances, covariance and RMS match ROOT within numerical tolerances. Distributions cover all samples; phase products exclude zero amplitudes. The exact sparse counts and covariance-matched Gaussian marginal ratios carry no independent-event significance. The complex ACF and Hann periodogram use the first 5 × 2²⁰ samples only. The full-run ordered ROOT coverage is 209 complete seconds at 100 Hz resolution. Prefix envelope times describe resolved local maxima and have no independent uncertainty model.

## Changes within the acquisition

The exploratory scan considered 36 series on 209 complete seconds. It compared abrupt splits with at least 20 s on each side and linear trends against the joint family maximum of 999 aligned block permutations, repeated at 5 s and 10 s. 18 candidates passed both exploratory thresholds (0.05). The last 0.7152 s remains in the raw summaries but is outside the equal-exposure test. Longer-range dependence, block exchangeability and unobserved configuration changes limit inference.

The shared change near 117–119 s lowers mean RMS by -0.53% / -0.53% / -0.46% and integrated PSD by -1.06% / -1.06% / -0.91% in TM010/TM011/TM012 order. Variance components change at matching times. Neither T7 rate nor the TM012 tracked line ratio passed both thresholds. Near 49 s, TM012 mean Q and its circular phase sine shift together. The sparse thermometry does not time-resolve the shared power change. The archive supplies no coincident LO readback; these changes cannot date an LO retune.

- TM010 mean_I_V, step near 158 s (adjusted block fractions 0.001/0.027).
- TM010 RMS_V, step near 117 s (adjusted block fractions 0.001/0.005).
- TM010 var_I_V2, step near 117 s (adjusted block fractions 0.001/0.005).
- TM010 var_Q_V2, step near 117 s (adjusted block fractions 0.001/0.004).
- TM010 phase_mean_cos, step near 153 s (adjusted block fractions 0.001/0.014).
- TM010 full_band_PSD_V2, step near 117 s (adjusted block fractions 0.001/0.005).
- TM011 RMS_V, step near 117 s (adjusted block fractions 0.001/0.001).
- TM011 var_I_V2, step near 117 s (adjusted block fractions 0.001/0.001).
- TM011 var_Q_V2, step near 117 s (adjusted block fractions 0.001/0.001).
- TM011 var_Q_V2, trend (adjusted block fractions 0.001/0.039).
- TM011 full_band_PSD_V2, step near 117 s (adjusted block fractions 0.001/0.001).
- TM011 full_band_PSD_V2, trend (adjusted block fractions 0.001/0.040).
- TM012 mean_Q_V, step near 49 s (adjusted block fractions 0.001/0.012).
- TM012 RMS_V, step near 119 s (adjusted block fractions 0.001/0.001).
- TM012 var_I_V2, step near 119 s (adjusted block fractions 0.001/0.001).
- TM012 var_Q_V2, step near 119 s (adjusted block fractions 0.001/0.001).
- TM012 phase_mean_sin, step near 49 s (adjusted block fractions 0.001/0.012).
- TM012 full_band_PSD_V2, step near 119 s (adjusted block fractions 0.001/0.001).

TM012 line ratio vs T7 rank coefficient -0.157; line ratio vs RMS -0.047. These are descriptive one-second associations on synchronized received-bin supports. The archived slow-control temperatures are sparse and identified by the existing stage mapping, with relative timing and validity flags. The LO records supply no evidence for an in-run retune.

## Adjacent runs and spectral transition

| Run | TM012 leading non-DC IF (Hz) | Occupancy (/209) |
|---|---:|---:|
| 1429 | -492,750.5 | 208 |
| 1669 | -492,750.5 | 208 |
| 1670 | -463,750.5 | 209 |
| 1671 | -463,750.5 | 209 |

The +29 kHz displacement agrees with the image-coordinate hypothesis fADC + LO₁ − LO₂, giving 8.6409922495 GHz on either side. A fixed RF tone on the verified main coordinate would move −11 kHz. A retune-linked internal mixing product remains possible. The near-constant line occupancy and the measured within-run associations do not establish a causal relation to amplitude tails.

The comparison CSV combines earlier validated raw results for Runs 1429, 1666 and 1676 with targeted Run 1670, and uses only existing ROOT moments for adjacent 1669 and 1671. No adjacent raw was needed to date the retune. A future neighboring raw comparison would require two additional passes totaling 18,648,212,835 compressed bytes.

## Coincidence controls

| Window (µs) | Kind | Observed tuples | Shift mean | Shift range |
|---:|---|---:|---:|---:|
| 1 | TM010--TM011 | 0 | 0.00 | 0–0 |
| 1 | TM010--TM012 | 0 | 0.00 | 0–0 |
| 1 | TM011--TM012 | 0 | 0.00 | 0–0 |
| 1 | TM010--TM011--TM012 | 0 | 0.00 | 0–0 |
| 2 | TM010--TM011 | 0 | 0.05 | 0–1 |
| 2 | TM010--TM012 | 0 | 0.00 | 0–0 |
| 2 | TM011--TM012 | 0 | 0.00 | 0–0 |
| 2 | TM010--TM011--TM012 | 0 | 0.00 | 0–0 |
| 5 | TM010--TM011 | 0 | 0.05 | 0–1 |
| 5 | TM010--TM012 | 0 | 0.05 | 0–1 |
| 5 | TM011--TM012 | 0 | 0.05 | 0–1 |
| 5 | TM010--TM011--TM012 | 0 | 0.00 | 0–0 |
| 10 | TM010--TM011 | 0 | 0.05 | 0–1 |
| 10 | TM010--TM012 | 1 | 0.05 | 0–1 |
| 10 | TM011--TM012 | 0 | 0.05 | 0–1 |
| 10 | TM010--TM011--TM012 | 0 | 0.00 | 0–0 |
| 100 | TM010--TM011 | 0 | 0.10 | 0–1 |
| 100 | TM010--TM012 | 2 | 0.65 | 0–2 |
| 100 | TM011--TM012 | 0 | 0.20 | 0–1 |
| 100 | TM010--TM011--TM012 | 0 | 0.00 | 0–0 |

Each coincidence describes a tuple of cluster peaks in the received index domain, with edge-protected exposure and twenty circular shifts. Absolute UTC, physical coincidences and acquisition-channel skew remain unresolved.

## Validation and resource use

One complete Run 1670 pass read 9,325,942,886 compressed bytes over 716.3 s raw streaming; CPU 714.7 s and peak process memory 1237.0 MiB. The main read requested 105,979,749 logical ROOT bytes. CRC-checked EOF, EOR, archived timing and PPS agreement, exposure and ADC conversion passed. Physical mount traffic was unavailable. No full waveforms were retained. A separate bounded read of the first five Run 1670 events requested 46,825,581 logical bytes for the finer I/Q display.
