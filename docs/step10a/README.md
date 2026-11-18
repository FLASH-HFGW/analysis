# Step 10A — Updated time-domain noise simulation

Six short realizations at 5 MS/s, one per mode and model, with 262144 complex samples each (52.4288 ms). The simulation is a diagnostic of the common-mask Step 9D predictions. It uses baseband-equivalent signed frequency coordinates and the frozen v48 ancestry at commit `1769aef`.

## Physical model and mask

The source function `analog` from [Step 9D](../step9d/build.py) is evaluated directly at the new FFT bins f and f ± 5 MHz. Model H uses integrated measured kz × 0.01 in voltage and the nominal secondary-image/main power ratio. Model N uses the nominal Step 9B transfer powers of the main and image paths. kz does not normalize Model N. Its support is used only in the shared mask inherited from Step 9D. Both models use the approved simultaneous VNA L5 by mode, 36 dB nominal FET and Tn = 3.955 K. The assumed RF electronic spectra are white, equal and incoherent in the disjoint input regions. The science LO plan maps the main and secondary-image inputs to LO1 + f + LO2 and LO1 + f − LO2. The thermal cavity stays on the main path with poles at the physical final IFs **1.250, 1.248 and 1.256 MHz**. The historical toy is preserved.

The mask retains **251659 / 262144 bins (96.0003%)** in every mode. Both models are projected onto |f| ≥ 100 kHz, matching the common support criterion in Step 9D. This projection defines the diagnostic input to the inverse FFT. Response below 100 kHz remains uncharacterized. The historical compact analog tone-sweep support used for Model H aliases is inherited from Step 9D. Model N aliases use the nominal response. Alias orders 0 and ±1 are included. Higher orders and the unknown full alias tail remain outside this short test, as in the primary Step 9D comparison. No interpolation bridges DC or resamples the archived Step 9D PSD. The old grid is re-evaluated separately only to verify the implementation against the archived per-path PSD, with maximum relative difference 5.34e−10 on nonzero entries.

## Synthesis and checks

For each mode there are independent, proper complex Gaussian draws for each source and alias order. Model H and N reuse the same standardized draw for the corresponding source and order, giving a paired comparison. Different modes use independent seeds. Cavity, primary RF noise and secondary image remain separate for every alias order. TM010 has zero secondary-image contribution by topology.

For bilateral voltage PSD S in V²/Hz, unitary FFT coefficients are drawn as `sqrt(Fs · S[k]) · (G₁+iG₂)/sqrt(2)`, where G₁ and G₂ are independent unit normals. Thus the expected time-domain mean square is `Δf · sum(S[k])`. Inverse transforms return periodic, band-limited diagnostic realizations. No carrier is sampled. These responses specify powers for proper Gaussian sources and do not determine the complex hardware phases, I/Q matrix, or instrument noise correlations.

All analog source traces are summed in volts before a single ADC quantization. Counts store I and hardware Q, with complex reconstruction `z = (Icounts − i Qcounts) × 4/65535 V`, using signed 16-bit counts and ±2 V range. Validation checks source and summed Parseval, the FFT of the analog sum, absence of analog amplitude outside the mask, zero clipping, component cross-covariances, quantization error bounds and equivalence of time-domain circular FIR power and its spectral integral. Aliases are checked per term on the old grid and synthesized separately on the new grid. Quantization is nonlinear and produces a small out-of-mask contribution. The quantized time series and all its derived quantities retain this contribution. The PSD plot averages 128 bins separately on each side of the common mask.

Expected finite-record power variation is computed from independent exponential bin powers, with standard deviation `Δf · sqrt(sum((w[k] S[k])²))` for weights w (unit or FIR magnitude squared). Cross-covariance and pseudocovariance use their corresponding Gaussian second moments. The observed deviations are sample fluctuations, while the deterministic equality and bound checks validate implementation. The largest analog full-band and seven-band deviations are **1.49** and **1.65** expected sample SD. The maximum per-source power deviation is **2.33 SD**. Quantization error is about **24.9 µV RMS** per complex sample, with no clipping. The out-of-mask quantized power fraction is at most **2.09e−7**.

| Mode | H expected / quantized RMS (mV ADC) | N expected / quantized RMS (mV ADC) |
| --- | ---: | ---: |
| TM010 | 26.604 / 26.608 | 27.229 / 27.241 |
| TM011 | 17.383 / 17.408 | 18.271 / 18.299 |
| TM012 | 10.877 / 10.883 | 11.660 / 11.663 |

Temporal validation compares only the simulations and their analytical expectations on the common mask. No temporal comparison is made with unmasked experimental data. Cable scenarios, additional noise sources, I/Q imbalance, empirical corrections and fitted parameters are outside this test.

## Deliverables and reproduction

- [Validation table](validation.csv), [seven FIR bands](bands.csv), [separate source and alias powers](components.csv), [validation plot](validation.png).
- Local directory `../analysis-work/Run2/simulation/step10a/` contains `series.h5`, configuration, full metrics, tables and six per-mode/model diagnostic figures. The figures cover I/Q, constellation, amplitude, phase, absolute bilateral PSD and complex autocorrelation. The HDF5 stores the signed frequency grid, common mask, source voltage series indexed by alias and source, summed analog series, I/Q ADC counts, PSDs and autocorrelations. Sample time is the sample index divided by Fs.
- The seven v48 deliverables from the approved commit were also verified and copied to the usual local report directory, with a local SHA-256 manifest. The previously published v48 history is preserved. The time series and large simulation artifacts are local.

From the repository root, with NumPy, SciPy, h5py and Matplotlib, provide a fresh output path:

```bash
OPENBLAS_NUM_THREADS=1 python3 simulation/step10a/run.py ../analysis-work/Run2 /path/to/new-step10a
python3 simulation/step10a/summarize.py /path/to/new-step10a/metrics.json docs/step10a
```
