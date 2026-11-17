# Part I v43 — explicit source progression, frozen physical reference

This presentation revision reuses the saved v41 short realizations (262,144 complex instants, 52.4288 ms at 5 MS/s). No new random draws, full-run simulation, fit, raw reconstruction or step 7/8 response is used. Historical sources and products are preserved.

## Active sources

| Step | Coherent tone | Injected validation noise | Cavity wall bath | Equivalent receiver |
|---|---|---|---|---|
| 1 | on, cavity bypass | off | off | off |
| 2 | on, port 1→2 | on, port 1→2 | off | off |
| 3 | off | off | off | on |
| 4 | off | off | on | off |
| 5 | off | off | exact step 4 draw | exact step 3 draw |
| 6 | off | off | on, all three modes | on, all three modes |

Step 3 is extracted from the existing receiver component, with the original science ADC quantization applied to that source alone. It no longer contains the coherent probe or injected test noise present in v41/v42 step 3. Step 5 was already the required pre-quantization sum, so its analog and ADC arrays are retained exactly. TM010 in step 6 remains exactly step 5. All analog, digitized, PSD and correlation arrays for steps 1, 2, 4, 5 and the three modes of step 6 are checked for equality with v41. Their physical parameters and calibration are unchanged.

## Physical map and conventions

Use the v41 matched complex RMS-equivalent convention, `E|z|²/R = available integrated power`, R=50 Ω and `z=I−iQhardware=I+iQeff`. The wall bath has available PSD `h f0/[exp(h f0/kB T)−1]` and transfer `Hb=sqrt(ki k2)/(kt/2+i2π detuning)`. The coherent/injected port-1 validation input instead uses `H12=sqrt(k1 k2)/(kt/2+i2π detuning)`. Rates and source temperatures are inherited without alteration. The receiver uses the same equivalent flat `kB Tn`, Tn=3.955 K, after the cavity transfer and before the fixed readout.

For matched physical volts, the same readout is applied once:

`V_ADC(f) = 10^(103.4/20) × kz_cal(f) × 0.01 × V_physical(f)`.

Equivalently, for available source PSD at the cavity-output/equivalent-receiver plane,

`S_ADC(f) = 50 × 10^(103.4/10) × |0.01 kz_cal(f)|² × S_physical(f)`.

The factor 0.01 is the 60→20 dB LF gain ratio, with unchanged frequency-shape assumption. The measured per-mode kz includes the mixer/LPF response and calibration ±5 V conversion, 10/65535 V/count. No extra 0.4, component insertion loss, extra LPF, hypothetical LF response or normalization adjustment is applied. Science uses ±2 V, 4/65535 V/count, separately on I and Qeff. The reference response support, alias treatment, phase convention and parameters remain the same. Receiver noise temperature and RF gain applicability to the modes remain conditional assumptions, not newly measured results.

## Residual and covariance checks

`z5 = z3 + z4` is verified exactly as constructed. The reverse floating-point subtraction `z5−z3` matches `z4` within 8.44e−18 V maximum complex error (1.29e−18 V RMS error); its physical RMS is 14.63751 µV. Plots use actual µV, including the floating-point error panel with scientific axis notation. No numerical display gain is introduced. Subtracting independently quantized streams is not used.

Covariance uses one complex mean per entire example and linear FFT covariance divided by N−lag, as before. With source-centered powers Pe and Pc, the independent-source prediction is `(Pe ge + Pc gc)/(Pe+Pc)`. Sample cross-covariances do not vanish exactly, so the finite-record normalized total differs from this sum by up to 3.41e−6. This is reported rather than removed. Pc/(Pe+Pc)≈2.89e−7 explains why adding the thermal source has little visible effect on the total correlation or RMS. The model amplitudes are not changed to make this contribution more visible.

For stages 3, 5 and all three mode examples, plot Re and Im at all 200 ns lags on the common ±1.05 scale and in a positive-lag zoom. Displayed nonzero-lag values are checked against both zoom limits; ±0.08 suffices in all cases. Thermal-only correlation remains on the full scale because its oscillations exceed ±0.08.

## Reproduction

```sh
OPENBLAS_NUM_THREADS=1 python simulation/presentation_steps1_6_v43/prepare_examples.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python reporting/iq_noise_summary_v43_partI/build_slides.py
OPENBLAS_NUM_THREADS=1 python reporting/iq_noise_summary_v43_partI/validate_partI.py
```

Inputs and outputs stay outside Git in `../analysis-work/Run2/simulation/presentation_steps1_6_v41/` and the separate `presentation_steps1_6_v43/` directory. The original physical configuration and hashes are retained in the v43 metrics. Sources and documentation alone are versioned; short arrays and rendered figures remain external.
