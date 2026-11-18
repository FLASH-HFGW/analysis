# Step 10C — Numerical results

All comparisons use masked ADC blocks. H and N are paired Monte Carlo populations.

| Mode | Mean block RMS, data / H / N (mV) | Aggregate RMS, data / H / N (mV) | Data/H and data/N (dB) | Data/N central FIR (dB) |
| --- | ---: | ---: | ---: | ---: |
| TM010 | 31.728079 / 26.604278 / 27.229335 | 31.728096 / 26.604291 / 27.229350 | +1.530 / +1.328 | +0.829 |
| TM011 | 20.328162 / 17.382721 / 18.270936 | 20.328172 / 17.382730 / 18.270945 | +1.360 / +0.927 | +0.465 |
| TM012 | 13.452814 / 10.877112 / 11.660384 | 13.452821 / 10.877118 / 11.660390 | +1.846 / +1.242 | +0.770 |

## Complementary power and first-lag covariance

| Mode | Population | Re pseudo / AC² | Im pseudo / AC² | Re g₁ at 0.2 µs | Positive and negative PSD contributions to Re g₁ |
| --- | --- | ---: | ---: | ---: | ---: |
| TM010 | data | -0.025358 | -0.031729 | -0.061366 | +0.285788 / -0.347153 |
| TM010 | H | -0.000007 | +0.000014 | -0.072997 | +0.277715 / -0.350713 |
| TM010 | N | -0.000013 | +0.000025 | +0.049063 | +0.321563 / -0.272500 |
| TM011 | data | -0.036229 | -0.030072 | -0.052368 | +0.288728 / -0.341095 |
| TM011 | H | -0.000020 | +0.000028 | -0.048690 | +0.290080 / -0.338769 |
| TM011 | N | -0.000029 | +0.000034 | +0.051095 | +0.322321 / -0.271227 |
| TM012 | data | -0.028459 | -0.030640 | -0.052190 | +0.288776 / -0.340966 |
| TM012 | H | -0.000022 | +0.000013 | -0.050030 | +0.289462 / -0.339492 |
| TM012 | N | -0.000007 | +0.000019 | +0.048058 | +0.320963 / -0.272904 |

Largest absolute complementary contributions in data, with the signs retained:

| Mode | Re-leading absolute IF range (MHz) | Re contribution (V²) | Im-leading absolute IF range (MHz) | Im contribution (V²) |
| --- | --- | ---: | --- | ---: |
| TM010 | 1.75–2.50 | -9.2356e-06 | 1.75–2.50 | -1.0425e-05 |
| TM011 | 1.75–2.50 | -6.1650e-06 | 1.75–2.50 | -3.9707e-06 |
| TM012 | 1.75–2.50 | -1.4927e-06 | 1.75–2.50 | -1.7704e-06 |

## Full-band empirical tails at 5 RMS

| Mode | Population | Threshold frame | Samples | Episodes | Fraction (where supported) |
| --- | --- | --- | ---: | ---: | ---: |
| TM010 | H | shape | 0 | 0 | — |
| TM010 | H | absolute | 0 | 0 | — |
| TM010 | N | shape | 0 | 0 | — |
| TM010 | N | absolute | 0 | 0 | — |
| TM010 | data | shape | 0 | 0 | — |
| TM010 | data | absolute | 6 | 6 | — |
| TM011 | H | shape | 0 | 0 | — |
| TM011 | H | absolute | 0 | 0 | — |
| TM011 | N | shape | 1 | 1 | — |
| TM011 | N | absolute | 1 | 1 | — |
| TM011 | data | shape | 0 | 0 | — |
| TM011 | data | absolute | 3 | 3 | — |
| TM012 | H | shape | 1 | 1 | — |
| TM012 | H | absolute | 0 | 0 | — |
| TM012 | N | shape | 1 | 1 | — |
| TM012 | N | absolute | 1 | 1 | — |
| TM012 | data | shape | 0 | 0 | — |
| TM012 | data | absolute | 7 | 7 | — |

Each full-band row uses 1048576000 eligible observations. Episode boundaries are censored as shown in the tail table.

Maximum aggregated PSD–ACF closure residual: 1.735e-18 V².

Maximum aggregated complementary closure residual: 2.033e-20 V².
