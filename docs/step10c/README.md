# Step 10C — Full-run statistical validation and complementary spectrum

Step 10C extends the approved Step 10B estimators over all run 680. H and N have the frozen Step 10A responses. External FET 36 dB, VNA L5 by mode, Tn = 3.955 K, thermal poles at the physical IFs, equal incoherent RF-band PSD and secondary folding remain fixed. H and N share Gaussian draws source-by-source and alias-by-alias for paired comparison. Each mode and block has a reproducible independent seed. The six Step 10A controls were already verified at Step 10B and remain distinct from this ensemble.

## Population and streaming

The reader consumes run 680 to EOF and requires 1000 SPECs of 1048576 samples. End-to-end metadata are in the local event ledger. The selected BOR fields and first eight SPEC hashes are checked against v47. As in Step 10B, each SPEC contributes four non-overlapping 262144-sample blocks at 5 MS/s, using signed int16 words, 4/65535 V/count and z = I−iQhardware. Each mode/population contains 4000 blocks and 1048576000 complex samples, or 209.7152 seconds of acquired samples. The FIR views each contain 12908 retained complex samples per block and 51632000 per population, mode and band. No estimator crosses a block or SPEC boundary.

The mask is identical to Step 10B: a rectangular FFT on the **ADC** block and projection onto the Step 10A common support (251659 bins, absolute IF ≥ 100 kHz). This includes DC removal, and is applied again after quantization for the toys. Step 10A component PSDs are re-evaluated and checked for element-wise agreement with the frozen arrays. FIRs share the same coefficients, signed centers, guards, decimation and segment centering as Step 10B. Zero-padding and denominator N−lag are retained for the linear complex ACF. Block projection is periodic and nonlocal. These statistics describe the selected population and retain their own conventions alongside the earlier unmasked full-run products. They do not characterize the missing LF hardware response.

The raw decoder and a bounded worker queue keep only a few SPECs in memory. Workers reduce contiguous blocks in acquisition order. Full-resolution mean spectra and grouped histograms, ACFs and spectral means are stored, without saving any simulated or measured time series. PSDs are rectangular, bilateral and in V²/Hz ADC. Cluster spectra average 128 bins for storage. The stored full-resolution PSD and complementary means use all individual FFT bins.

## Observables and uncertainties

For every mode, population and band, the [observables](observables.csv) distinguish the arithmetic mean of 4000 block RMS values from the RMS of the aggregate block mean-square. Absolute RMS, I and Q variance, their signed covariance, complex pseudocovariance, amplitude and phase distributions, circular phase increments and linear complex ACF use the Step 10B definitions. Dimensional quantities retain ADC units. The proper Gaussian reference has per-quadrature variance RMS²/2, at the N analytical RMS for the corresponding masked band. Shape-only distributions divide by each block's own RMS and compare with the dimensionless Rayleigh and uniform-phase references. No hardware or science gain is refitted.

The local tables retain per-block data. Error summaries use the dispersion across means of 20 consecutive SPECs (50 groups) and a sensitivity check with 40 SPECs (25 groups), as well as block and SPEC spreads. They account descriptively for local dependence, without IID sample error bars or an assertion of independence at longer lags. The simulated populations are stationary by construction; grouping does not establish stationarity of the experimental run.

## Complementary spectrum and PSD–ACF closure

Let X[k] be the centered block's **unitary** FFT, with signed bin f = k Fs/N and the conjugate partner indexed by (−k) mod N. The complementary estimator is X[k] X[−k]/Fs in V²/Hz, without conjugating the second factor. It is even as a complex spectrum. Positive and negative halves describe the same pairs; the bilateral integral counts every bin once. DC and Nyquist are self-pairs. DC is removed by the mask.

With Δf = Fs/N, summing Δf C[k] gives the block time mean of z². In the sign convention used here this is var(I)−var(Q)−2i cov(I,Qhardware). The code checks this identity for every block and after averaging. Proper stationary H and N have theoretical complementary spectrum zero. Their finite-run residuals and 20-SPEC group variation are shown separately. For a physical interpretation a frequency-resolved phase-preserving I/Q calibration is required. A nonzero C does not localize its cause or imply coherence across cavity modes.

The inverse DFT of the bilateral PSD, multiplied by Fs, gives the circular ACF. The relation to the linear estimator is R_linear(l) = [N R_circular(l) − wrap(l)]/(N−l), with wrap(l) the sum of the l wrapped endpoint products. Both the direct finite-record ACF and the wrap term are checked at lags 0–128. For analytical H and N the inverse DFT gives the expected periodic covariance. A finite-record estimator of the unquantized periodic process has the same expectation at each lag. ADC rounding and projection are present in the empirically measured toy statistics.

For the first lag, the real numerator is the integral of S(f) cos(2π f/Fs), with a positive weight below 1.25 MHz in absolute IF and a negative weight above. The [interval table](spectral_intervals.csv) partitions the common mask about this sign change and reports the contribution to normalized first-lag covariance together with the real/imaginary integrated complementary spectrum. The [closure table](spectral_closure.csv) reports the right and left sides numerically. This decomposition uses no fit and preserves the observed sign of the first-lag real ACF.

## Tails through 5 RMS

The [tail table](tail_counts.csv) reports eligible samples and counts for 2, 3, 4 and 5 RMS, in both fixed ADC thresholds (N's analytical RMS) and per-block shape thresholds. It reports the number of SPECs and 20-SPEC groups with exceedances and grouped dispersion of the fractions. Fractions are suppressed unless there are at least 20 points across at least four SPECs and four groups. Counts always remain visible. This gate is descriptive and does not establish an effective number of independent tail draws.

An episode is a consecutive sequence of above-threshold samples within a processed block. Episodes touching boundaries are separately flagged as censored. They are never merged across boundaries of the periodic projection or across SPECs. These counts are clustered sample excursions and do not estimate detector false-trigger rates.

## Full-run findings

[Numeric results](results.md) distinguish mean block RMS and aggregate RMS. The maximum difference between the two reported full-band RMS estimators is 0.000017 mV in this run. Model N is closer in absolute full-band power in every mode, with data/N residuals +1.328, +0.927 and +1.242 dB. In the central FIR the residuals are +0.829, +0.465 and +0.770 dB.

Model H remains closer in complex full-band ACF. The largest change in the real first lag when replacing H by N is the reduced negative weight from |IF| = 1.75–2.50 MHz, which raises normalized Re g₁ by 0.0841, 0.0713 and 0.0702 for the three modes in order. The intervals below 1.25 MHz also shift the balance toward positive values. Both real and imaginary complementary integrals are largest in absolute value in the 1.75–2.50 MHz interval for all modes. Full-band amplitude CDF distances from Rayleigh are at most 4.47e−4 in the data, alongside markedly nonzero signed pseudocovariance. [Distribution diagnostics](distribution_diagnostics.csv)

## What a bidirectional model would need

A scattering/noise-wave treatment would need complex, frequency- and operating-condition-dependent multiport S matrices, both directions of propagation, actual terminations and temperatures, mixer translation matrices including sideband and LO phasing, and noise-wave auto- and cross-covariance matrices referenced to consistent planes. It would have to propagate reflections and reverse noise through the L5/FET/readout chain and the cavity, with a stable loaded network and a consistently thermalized passive environment. Independent VNA scalar gains, kz magnitudes, nominal component curves and the measured output C(f) do not determine these inputs. In particular, the available measurements do not separate reverse-propagating amplifier noise, mismatches or source correlations from I/Q conversion and loading. Those constraints require independent complex characterization in science configuration. This study does not implement that model or modify any source term.

## Reproduction and products

Full products are at `../analysis-work/Run2/simulation/step10c/`, including HDF5 statistics, detailed per-block CSV, events, local graphs and SHA-256 manifest. GitHub holds only code, configuration, this documentation, light tables and [a small diagnostic graph](spectral_diagnostics.png). Run locally with the validated MIDAS reader, NumPy, SciPy, h5py and Matplotlib:

```bash
OPENBLAS_NUM_THREADS=1 python3 simulation/step10c/run.py \
  ../analysis-work/Run2 ~/flash-data/data/LNF/run00680.mid.gz \
  ../analysis-work/Run2/simulation/step10a /path/to/new-output --workers 7
python3 simulation/step10c/report.py /path/to/new-output docs/step10c
```

No model parameters are fit or changed. Baselines, earlier steps and presentations are preserved.
