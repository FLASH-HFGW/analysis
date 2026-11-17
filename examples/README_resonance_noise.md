# Separate electronic and resonance-centered noise products

The original nine-band DC-centered analysis and its 260-run products are unchanged. The approved toy and all presentation versions are unchanged; v46 remains paused. This addition prepares and validates a resonance bank and processes **only run 680**. Reading BOR metadata of all 260 runs does not reconstruct their SPEC streams.

## Scientific objectives and output separation

- **Electronic/DC bank:** existing centers 0 and offsets 0/±100/±250/±500/±1000 kHz, width 50 kHz. Preserve its full historical products, with the original v2 input-run-mean convention, for DC/electronic depression and long-term spectral stability.
- **Resonance ROI bank:** derive the signed main-branch center from each run's BOR VNA RF frequency and primary/secondary LO. Use seven offsets 0/±100/±250/±500 kHz, width 50 kHz. It describes the measured noise in the physical resonance region; it does not prove that the small cavity thermal component dominates the measured electronics.
- No default resonance frequency is accepted. Missing/nonfinite RF, LO, sampling or ADC-range metadata, inconsistent I/Q ranges, or bands outside digital Nyquist cause an error.

`iq_acquisition_metadata.py` reads the first BOR event only. For I−iQ, `center = f_VNA − f_LO1 − f_LO2`; for the conjugate convention its sign reverses. TM010 has no secondary mixer by documented topology, not an inferred missing value. Original frequency/acquisition fields, their original names/values and timestamps are preserved as JSON; structured units/provenance and derived coordinates are also stored. No full BOR with unrelated equipment/network fields is published.

The nominal VNA reference recorded in ODB is explicitly **not** an in-run physical resonance fit or a measurement of resonance drift. The frozen cavity-fit/thesis parameters remain in a distinct HDF5 group and are never substituted for BOR-derived filter centers. For the current records, ODB gives +1.250 MHz for all modes, whereas the frozen reference gives +1.250/+1.248/+1.256 MHz.

## BOR configuration audit of all 260 runs

```sh
OPENBLAS_NUM_THREADS=1 python examples/audit_iq_bor_coordinates.py \
  --raw-dir /home/mazzitel/flash-data/data/LNF \
  --output /path/to/new/bor_audit_680_939.h5
```

Read-only first-event extraction, no SPEC analysis. The completed audit of 680–939 found one configuration for every VNA reference, LO, sample rate and ADC range: fRF=8737.119/8780.842/8841.176 MHz, LO1=8735.869 MHz, LO2=0/43.723/104.057 MHz; fs=5 MS/s, six IQ ranges ±2 V. All derived centers are +1.250 MHz. This establishes stable **recorded settings**, not absence of physical cavity-frequency drift. Each run's original selected metadata and derived coordinates are saved separately in the audit HDF5.

## PSD-first assessment without a new waveform reconstruction

```sh
OPENBLAS_NUM_THREADS=1 python examples/preview_resonance_psd.py \
  --raw /home/mazzitel/flash-data/data/LNF/run00680.mid.gz \
  --fft /home/mazzitel/flash-data/analysis/autoreco/Run2/fft_by_run/run00680.npz \
  --old-h5 /path/to/original/run00680_noise_v2.h5 --output /new/existing_PSD_preview.json
```

The command reads only BOR plus the existing full-run spectrum. The legacy FFT has actual length 16,383, despite the old 16,384 frequency descriptor. Use the actual grid, two-sided Hann coherent-power to PSD conversion through its ENBW **in Hz**, and physical ±2 V conversion once (old archive used ±5 V). Weight this PSD by the actual FIR magnitude squared, not an ideal rectangular 50 kHz window. No gain correction is fitted.

The existing full-run PSD predicts central RMS about **3.098/1.995/1.317 mV ADC**. On the existing +1 MHz control window its predicted power differs from the saved v2 product by −0.0275%, +0.0715%, +0.00448%. The source FFT subtracts per-chunk means, unlike the v2 run-mean convention, and is an averaged finite-resolution estimator. Thus it supplies an initial power assessment, not filtered-IQ histograms, phase, correlations or an exact waveform replay. No phase is reconstructed from power-only products.

## Filter implementation and signal preservation

`resonance_filter_bank.py` uses the exact existing real Kaiser FIR: 2001 taps, beta 8.6, 25 kHz design cutoff (50 kHz nominal full width), decimation 20, 47,428.8068 Hz bilateral ENBW. No analog transfer function or physical noise model is added.

The equivalent identity is

`LPF[z[n] exp(−iωn)] = exp(−iωn) × convolution(z, h[k] exp(+iωk))`.

A single input FFT per mode is shared across the seven modulated kernels, and the output oscillator is evaluated only at retained samples. This avoids seven repeated input FFTs and full-rate oscillators without changing the filter. Integer-Hz centers use integer modular phase arithmetic to avoid long-record floating-phase drift. A shared input tail, global sample counter, global decimation grid and oscillator phase persist across all SPEC boundaries. Initial valid sample n=2000, n mod20=0; reported time subtracts the 1000-sample FIR delay. No boundary is individually reset or recentered.

Input preprocessing uses the existing v2 **whole-run input mean**, converted once from the old stored scale to physical BOR ADC volts, so the shared band is directly comparable. This does not remove a physical tone at nonzero +1.25 MHz. **No output mean is subtracted after demodulation.** Total RMS, amplitude histograms, Welch PSD with detrend=False, and total (uncentered) autocorrelation retain a coherent band-center signal. ADC samples are not requantized after filtering.

## Synthetic validation

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest discover -s examples/tests -p test_resonance_bank.py -v
OPENBLAS_NUM_THREADS=1 python -m unittest discover -s examples/tests -p test_iq_filtered_bands.py -v
```

Tests cover all seven known-frequency tones and identification of their bands; coherent center gain and nonzero mean preservation; positive/negative frequency discrimination; no silent metadata defaults; conjugate-IQ sign; changed BOR centers; mismatched ADC ranges/Nyquist rejection; HDF5 metadata round trip; equivalence to independent causal `lfilter` on irregular SPEC boundaries; equivalence with the unchanged legacy `BandFilter`. The original filter tests also remain applicable. This is an implementation validation, not a new physical toy simulation.

## Authorized run-680 pilot

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python examples/analyze_resonance_noise.py \
  /home/mazzitel/flash-data/data/LNF/run00680.mid.gz \
  --electronic-reference /path/to/original/run00680_noise_v2.h5 \
  --thesis-reference /home/mazzitel/HFGW/analysis-work/Run2/simulation/step6/metrics.json \
  --output /new/separate/run00680_resonance.h5 --fft-workers 3
```

The runner refuses an existing output, checks reference run, EOF, IQ sign, sampling and full-run sample count, and freezes source/reference hashes. It does not launch or reconstruct any other run. Old electronic HDF5 and physical reference checksums are checked again before publication. New outputs are isolated under:

`../analysis-work/Run2/diagnostics/resonance_bank_pilot_v1_20261117/`.

### Additive HDF5 layout and units

The generic schema-1 writer/reader is reused without changing old products. New groups:

- `/acquisition_metadata`: original selected BOR JSON/hash, RF/LO frequencies, original ranges, fs, IQ convention, source/units/provenance, per-mode derived IFs/centers. The stored hash covers those selected fields, not the entire raw MIDAS.
- `/physical_reference_thesis_fit`: independent frozen physical reference, with source and SHA; not used to center filters.
- `/filter_banks/electronic_DC_reference`: immutable old product path/hash and original coordinates. Old numerical results remain in their existing complete HDF5; they are not recomputed or overwritten.
- `/filter_banks/resonance_ROI/configuration`: actual coefficients, width, offsets, ENBW, sampling/state/transient definitions.
- `/filter_banks/resonance_ROI/modes/MODE/band_XX`: physical-input coordinates, full-run voltage moments and amplitude histograms, per-SPEC moments/RMS, whole-run filtered Welch PSD and first-five-SPEC filtered values/total covariance.
- `/consistency_with_electronic_bank`: direct per-SPEC RMS comparison with old +1 MHz, identical to new offset −250 kHz under these BOR settings.
- `/provenance`: executed source hashes, old-product hash and the actual physical input mean used.

All new measured quantities are **ADC-equivalent volts**, not RF watts or cavity-input noise. The generic `ComplexMoments.export(gain=1)` compatibility `_input_` aliases inside `moments_ADC` equal ADC-domain quantities and are not an input-referred calibration; review code uses only explicitly ADC-labelled quantities. No nominal 143 dB gain or any other input-referred correction is applied to this pilot.

### Statistical scopes and comparisons

Input coverage: 209.7152 s, 1000 SPEC, 1,048,576,000 complex ADC instants per mode. Each band retains 52,428,700 filtered instants after the single initial FIR transient, at **4 µs** spacing. Full-run histograms conserve these counts. The Welch estimator uses 16,384 filtered samples, symmetric Hann, no overlap and no segment mean subtraction; final incomplete Welch segment is excluded and its sample count is explicit.

Complex total autocorrelation uses the **first five input SPEC**, 1.048576 s input coverage minus the initial transient in the retained stream, not the full run. This scope is labelled separately from full-run moments/histograms/PSD. Its time structure is dominated by the 50 kHz filter: it must not be read as an intrinsic cavity decay fit. The displayed white-noise-through-FIR covariance is an analytic filter check, not a fitted physical spectrum.

The overlap check compares each full-run per-SPEC RMS with the existing +1 MHz band after the established ADC conversion; acceptance is max relative error <1e−6, allowing different floating arithmetic but no physical normalization change. The new central/side power ratio averages **six resonance sidebands**, whereas the old electronic ratio averaged eight different windows. These two definitions are not interchangeable. Symmetric ratios are P(+offset)/P(−offset).

### Review products

```sh
OPENBLAS_NUM_THREADS=1 python examples/report_resonance_pilot.py /new/run00680_resonance.h5 \
  --preview /new/existing_PSD_preview.json --output /new/review
```

Produces full numerical band statistics, central/symmetric ratios, eight-page PDF and individual images: absolute RMS/PSD predictions, shared-window control, actual FIR response, measured filtered PSD, amplitude densities, selected IQ, Re/Im total covariance and per-band detailed pages. Existing electronic products do not contain equivalent saved filtered waveforms/histograms for every band, so that historical comparison is limited to the observables actually saved; no phase or covariance is invented from their power.

Only new sources/tests/documentation are versioned. All numerical records, HDF5s, graphs and review files remain external. A future full-campaign resonance reconstruction requires review/authorization after this run-680 pilot; none is launched here.

## Completed pilot results (2026-11-17)

The separate run-680 reconstruction completed all 1000 SPEC in 501.44 s wall time. This timing includes this bank's statistics and is not a benchmark of the full original reconstruction pipeline. The seven new synthetic tests and five unchanged legacy filter tests passed. `validate_resonance_pilot.py` passed all completed-product checks, including count conservation, moment identities, PSD integrals, metadata and reference/source hashes.

| Mode | Central-band RMS at ADC (mV) | Central power / mean six sideband powers | Maximum relative per-SPEC RMS difference, shared +1 MHz band |
|---|---:|---:|---:|
| TM010 | 3.096471 | 0.991147 | 1.21e-9 |
| TM011 | 1.994989 | 0.994737 | 1.47e-9 |
| TM012 | 1.317534 | 0.994278 | 1.10e-9 |

The existing full-run FFT products independently predict central RMS values of 3.097516, 1.994737 and 1.317474 mV, respectively. Their estimator differs from the filtered-stream Welch estimator, as documented in the preview. These powers characterize total readout noise in the selected windows; near-unity ratios do not establish a thermal-noise measurement or identify the noise source.

The BOR-only audit covered all 260 runs without reading their SPEC payloads. Selected recorded VNA frequencies/settings, all recorded LO variables, sampling and ADC ranges are constant. VNA auto-detection is recorded as false. These constant nominal references are not measurements of physical resonance drift. The separate `bor_audit_680_939.configuration_states.json` records the distinct original control values; switch/status encodings are not reinterpreted as verified physical hardware states.

Review directory: `/home/mazzitel/HFGW/analysis-work/Run2/diagnostics/resonance_bank_pilot_v1_20261117/review/`. Start with `run680_resonance_review.pdf` (eight pages), `band_statistics.csv` and `summary.json`. The parent directory retains the new HDF5, BOR audit, existing-PSD preview and passed `validation.json`. Previous products, the approved toy simulation and presentation remain untouched by this diagnostic. The v46 and any 260-run resonance reconstruction remain pending scientific review.
