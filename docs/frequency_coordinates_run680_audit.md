# Run 680 frequency-coordinate audit

17 November 2026. Read-only verification. The v46 work is paused; no slide, scientific source, filter configuration or existing result was modified, and no reconstruction, filter execution, simulation or physical fit was run.

## 1. Finding: the production bank inherited the zero-center default

The frequencies needed to derive physical IF centers were present in the acquisition BOR/ODB. The long-term analysis **did not read those VNA/LO fields to configure the filters**. It constructed the IQ signals from SPEC and used the command-line defaults:

- [analyze_midas_iq_noise.py](../examples/analyze_midas_iq_noise.py), parser: `--band-centers-hz`, default `[0.,0.,0.]`.
- `FilteredBandChecks.__init__`: each filter center is `args.band_centers_hz[mode]+offset`.
- All 260 **prepared** scripts in `analysis-runtime/autoreco/Run2/noise_fullrange_v2_20261109/NNNNN/script.sh` omit the center option. The final campaign includes 248 HTC reconstructions and 12 reused HPC runs; 260 prepared scripts do not mean 260 executed HTC jobs.
- [HPC launcher](../examples/hpc/noise_job.sh): likewise enables filtered bands without passing mode centers.
- The frozen sources match their production manifest SHA-256 entries. Existing HDF5 configurations confirm the actual centers `[0,0,0]`.

The original [band documentation](iq_sidebands.md), introduced with commit `4244758` on 8 November, explicitly describes an exploratory survey about electronic zero, does not equate zero with resonance and leaves the physical centers to be defined. There is no documented automatic resonance-centering decision. Thus zero was an intentional *default for that diagnostic*, inherited by the launches, rather than a center derived from acquisition metadata. These products must not be described as resonance-centered noise measurements or as an isolated electronics-noise measurement.

## 2. Direct BOR read and calibration-file comparison

The BOR/ODB was read directly from `/home/mazzitel/flash-data/data/LNF/run00680.mid.gz` using `MidasFile.get_bor_odb_dump()`. That method reads only the first BOR event. The uncompressed position after it was 1,066,138 bytes; no SPEC event was analyzed. The reader was then closed.

Recorded fields:

- `/Equipment/LocalOscill/Variables/freq RS`: **8,735,869,000 Hz**.
- `/Equipment/LocalOscill/Variables/freq Teled Ch1`: **43,723,000 Hz**.
- `/Equipment/LocalOscill/Variables/freq Teled Ch2`: **104,057,000 Hz**.
- `/Equipment/VNA/vnaCalib/freq_mode1`: **8,737,119,000 Hz**.
- `/Equipment/VNA/vnaCalib/freq_mode2`: **8,780,842,000 Hz**.
- `/Equipment/VNA/vnaCalib/freq_mode3`: **8,841,176,000 Hz**.
- NetBox sampling: **5 MS/s**; six IQ channel ranges **±2 V**.
- `VNA/vnaCalib/Auto_detect=false`: these are recorded calibration/reference frequencies, not a new automatic tracking measurement during run 680.

The nine latest cavity-calibration files dated **24 July 2026**, before acquisition, were read from `data/LNF/calib/`: S12/S21/S22 for each of modes 1–3. Each has 2001 frequency points, 1 kHz spacing and a 2 MHz span. Their RF grid centers match the three ODB VNA fields exactly:

| Mode | VNA frequency interval [MHz] | Scan center / ODB RF [MHz] | Representative S21 file |
|---|---:|---:|---|
| TM010 | 8736.119–8738.119 | 8737.119 | `S21cav_modo1_2026-07-24_17-15-46.txt` |
| TM011 | 8779.842–8781.842 | 8780.842 | `S21cav_modo2_2026-07-24_17-24-34.txt` |
| TM012 | 8840.176–8842.176 | 8841.176 | `S21cav_modo3_2026-07-24_17-36-13.txt` |

**Important qualification:** a scan center is an explicitly recorded RF reference, not itself a newly fitted resonance peak. No peak/line-shape fit was performed here. These coordinates reconstruct the expected resonance position from the stored reference; they do not independently measure instantaneous resonance drift from the run-680 noise.

## 3. Requested comparison table: calibration RF, science LOs, ODB IF and actual filter center

For the documented main conversion branch and analysis convention `z=I−iQhardware`,

`f_IF = f_RF − f_LO1 − f_LO2`, with `f_LO2=0` for TM010.

All values below are MHz. The calibration IF column uses the RF reference in the **24 July cavity VNA files with the actual run-680 LOs**; the separate older DAQ tone-calibration settings are distinguished in section 4.

| Mode | RF calibration / ODB reference | Primary LO, run 680 | Secondary LO, run 680 | IF from VNA-file RF + science LOs | IF from run-680 ODB | Center actually used by nine-band analysis |
|---|---:|---:|---:|---:|---:|---:|
| TM010 | 8737.119000 | 8735.869000 | — | **+1.250000** | **+1.250000** | **0.000000** |
| TM011 | 8780.842000 | 8735.869000 | 43.723000 | **+1.250000** | **+1.250000** | **0.000000** |
| TM012 | 8841.176000 | 8735.869000 | 104.057000 | **+1.250000** | **+1.250000** | **0.000000** |

The first analog IFs are +1.250, +44.973 and +105.307 MHz. The secondary analog conversion brings the latter two to +1.250 MHz.

The **frozen thesis/toy** instead uses RF references 8737.119 / 8780.840 / 8841.182 MHz. With the science LOs these give +1.250 / +1.248 / +1.256 MHz. The −2 kHz (TM011) and +6 kHz (TM012) differences arise from different adopted RF references. Their origin is not inferred here; the frozen model and approved results are unchanged. Neither reference set puts resonance at electronic zero.

## 4. Do not confuse cavity VNA calibration with the earlier DAQ tone calibration

The existing `calibration_reconstruction.json` contains recorded observations for the conversion-tone calibration (runs 408–590, valid per-mode subsets). Its LO state differs from run 680:

| Mode | Primary LO during DAQ tone calibration [MHz] | Secondary LO during that calibration [MHz] | RF electronic zero [MHz] | IF of the same 24-July RF reference under those old LOs [MHz] |
|---|---:|---:|---:|---:|
| TM010 | 8734.910000 | — | 8734.910000 | +2.209000 |
| TM011 | 8734.910000 | 44.160000 | 8779.070000 | +1.772000 |
| TM012 | 8734.910000 | 104.390000 | 8839.300000 | +1.876000 |

The last column is coordinate arithmetic for the *same chosen RF reference*, not a new measured resonance in those older calibration runs: the injected calibration tone was swept. Those IF values must not be imported as run-680 digital centers. The observed RF-to-IF slope in that saved calibration is approximately **+1.000009** for all three modes, not −1.

### Frequency sign

The existing signed raw-tone verification (`TM010_audit/raw_calibration_verified.json`) confirms the I−iQ convention. For example, imposed IF −1,032,786.885 Hz gives fitted main IF −1,032,786.889 Hz. Other saved positive and negative tone checks support the same signed main branch, including TM011/TM012 in `audit.json`. No new raw tone waveform was read or fitted for this audit.

With `numpy.fft`'s forward exp(−iωt) convention, a component `exp(+i2πft)` appears at **+f**. The resonance references above therefore appear near **+1.25 MHz**. Conjugating to I+iQ would reverse signs. IQ imbalance can also produce a mirrored image near −f; the main-branch coordinate is not a claim of perfect image rejection.

## 5. Which frequency metadata are actually in the HDF5 files?

The original run-680 v2 HDF5 was inspected in read-only mode. It contains:

- `summary/fs_hz`, `summary/iq_sign`, CLI voltage-range convention and acquisition coverage;
- `filtered_bands/config/centers_hz=[0,0,0]`, offsets, width, taps, decimation, DC-removal convention;
- actual per-band `center_hz` and `offset_hz`;
- nominal scalar gain configuration and scientific moments/histograms.

It **does not contain the BOR dump, the VNA mode-frequency fields or the LocalOscill LO variables**. The [analysis summary construction](../examples/analyze_midas_iq_noise.py) does not copy them, and the main analysis never reads the BOR to derive filter centers. The [HDF5 exporter](../examples/iq_noise_io.py) packages the provided analysis summary; it cannot restore omitted acquisition fields.

Some relevant metadata had already been extracted **outside the HDF5s**: the later diagnostic `hardware.json` has all 260 LO summaries (same three frequency setpoints throughout), and the normalization audit saved selected run-680 ODB fields. These later JSON diagnostics are not evidence that the original filtering code consumed those values. VNA reference histories for all 260 runs have not been re-extracted in this audit.

A local read-only inventory of 1,596 HDF5 files found 744 standard filtered-bank product copies, all with zero centers; zero nonzero-center products and zero read errors. Duplicates/subsets are included, so this is not 744 independent runs. Remote or custom-format products are outside that inventory.

## 6. No hidden pre-bank translation; what the existing bank selects

`FilteredBandChecks.update` forms the signed IQ stream directly from ADC frames, subtracts the single run mean for v2, then calls each `BandFilter`. The only frequency translation is **inside each band**:

`z_band = LPF[(z−mean_run(z)) exp(−i2π(center+offset)n/fs)]`.

There is no common translation by a cavity frequency before the bank. `fftshift` used for displays does not translate the incoming signal. FIR state, oscillator and decimation continue across SPEC.

The nine actual nominal intervals are centered at **0, ±100, ±250, ±500, ±1000 kHz**, each ±25 kHz, in the original electronic IF. In v2 the constant input run DC is removed; fluctuations in the central ±25 kHz band remain. The original v1 retained the input DC offset. No post-demodulated output mean is removed from the principal band RMS, so a future resonance-center coherent tone would remain in that RMS after translation to output DC.

For the science main branch, the RF zeros corresponding to electronic IF zero are 8735.869 / 8779.592 / 8839.926 MHz. A band at signed IF b selects nominal main RF center `RF_zero+b`, with RF half-width 25 kHz. The RF ranges of the complete nine-band sets are therefore:

| Mode | Lowest nominal main RF edge [MHz] | Highest nominal main RF edge [MHz] | Reference resonance [MHz] |
|---|---:|---:|---:|
| TM010 | 8734.844 | 8736.894 | 8737.119 |
| TM011 | 8778.567 | 8780.617 | 8780.842 |
| TM012 | 8838.901 | 8840.951 | 8841.176 |

These spans contain gaps between the nine windows. Every resonance reference lies **225 kHz above the highest nominal edge**. Thus the bank does not measure the resonance center. Its +1 MHz window samples the −250 kHz flank relative to the recorded reference, not the peak.

The RF mapping above describes the intended main conversion branch. Real secondary mixers can also admit the other first-IF branch; their alternate RF-zero combinations are LO1−LO2=8692.146 MHz and 8631.812 MHz. Actual image weights/rejection require the installed analog response. Sampling also identifies analog IFs modulo 5 MHz; analog LPF rejection is finite. The digital band is not a unique physical RF-source identification when image/alias contributions are present.

## 7. Assessment of a second bank — no implementation

The original bank can remain an **electronic/DC-centered diagnostic**, with a separate resonance-ROI bank configured from an explicitly selected RF reference and the actual per-run LOs. Using run-680 ODB references, the centers would be `[1250000,1250000,1250000]` Hz. The frozen reference instead implies `[1250000,1248000,1256000]` Hz; this distinction must be recorded, not silently overwritten.

Proposed offsets 0, ±100, ±250 and ±500 kHz, full width 50 kHz, span nominal IF **0.725–1.775 MHz** in the ODB-reference case (0.723–1.781 MHz across the frozen-reference cases). These fit within digital Nyquist ±2.5 MHz and the BLP-1.9+ specified DC–1.9 MHz passband (<1 dB), whose nominal −3 dB cutoff is 2.5 MHz. Primary IF ranges are 44.448–45.498 MHz and 104.782–105.832 MHz for TM011/TM012, within SIF-40+ 35–49 MHz and SBP-101+ 94–108 MHz passbands. Manufacturer documents are preserved in `docs/hardware/`, pp.1 / 1–2. This is nominal passband compatibility, not new measured whole-chain flatness or proof of alias/image rejection. FEMTO's nominal 100 MHz bandwidth remains relevant to the ≈105 MHz primary path.

There are no standard-schema local products for a complete resonance-centered bank. Existing full-band FFT/PSD products cover that region, and the existing +1 MHz window coincides with the proposed −250 kHz window when the center is 1.250 MHz. They do not supply the missing resonance-center filtered-IQ history. No spectral integration, new bank or job was executed.

## Evidence retained outside Git

Directory: `/home/mazzitel/HFGW/analysis-work/Run2/diagnostics/frequency_coordinates_audit_20261117/`.

- `run680_BOR_frequency_metadata.json`: directly reread BOR fields; no SPEC read.
- `calibration_comparison.json`: nine VNA files, exact grid centers, science LO mapping, older DAQ LO states.
- `metadata_audit.json`: local HDF5 configuration inventory, prepared-script defaults, frozen-source checks and frequency arithmetic.

These are new verification records only. Existing products and code are untouched. This document does not authorize a change to the frozen simulation, existing band products or presentation.
