# v49 supplement — Campaign strain sensitivity

Uses the 260 verified run FFT products (680–939), including the seven approved sign-corrected copies. No new raw reads, simulations or scientific fits. Each run contributes 209.7152 s of acquisition, for **54525.952 s** live time. The first-to-last SPEC timestamp span is **55405 s**, with inter-run gaps of 3–4 s at integer-second resolution. These timestamps are unsuitable as phase references.

## PSD and conditional signal transfer

The 16383-bin Hann-averaged complex spectra use z = I−iQhardware and the same 0.16 power correction to physical ADC units and Hann ENBW as v47.1. The PSD is bilateral in signed complex IF. All 260 file hashes match the validated ledger. The 780 central FIR powers reproduce the approved table to **5.33×10⁻¹⁵** maximum relative error. A 128-bin running mean (approximately 39.1 kHz) gives local noise density estimates, matching the smoothing scale of v49 but using the archived PSD estimator. Signed bins near DC and the Nyquist edge lack full support for the smoothing and coherent transfer; the curves use the supported positive IF only. Narrow lines within the smoothing bandwidth are not resolved by this projection.

The same conditional v49 transduction is used for both coherent readouts: V = 0.139 L, B_RMS = 6.73 T, and illustrative C_GW = 0.01 per mode. The field and directional/polarization overlaps remain unverified for this exposure. Conversion includes the modal cavity Lorentzian with physical pole and readout branching fraction, VNA L5 + 36 dB FET, and direct-path H = 0.01 kz or N = nominal complex main gain. Constant resonance and transfer parameters are assumed across the campaign. The measured noise PSD already includes whatever RF folding and ADC aliasing are present, without adding those factors to coherent signal gain. Signal leakage/conjugate gain is outside this scalar template. The complex strain ASD scales as (6.73 T/B_RMS) sqrt[(0.01/C_GW)(0.139 L/V)]. The equivalent real one-sided ASD in the peak-tone convention is smaller by sqrt(2). A null overlap removes sensitivity.

Let sᵢ be the equivalent complex strain PSD of run i. The listed harmonic ASD is sqrt(N / Σᵢ 1/sᵢ); sqrt(mean sᵢ) is also tabulated, with 5–95% run ranges. The harmonic ASD is the PSD equivalent of the coherent inverse-noise weighting, not a reconstructed phase-aligned campaign spectrum.

## Integration projections and practicability

- **Coherent ideal:** known-phase amplitude SNR ρ = h sqrt(2 Σᵢ Tᵢ/sᵢ). The reported threshold uses the recorded live times, assuming a phase-matched template across gaps with constant effective C_GW. For ρ = 5 multiply the strain at ρ = 1 by five. A search with unknown phase or template trials needs a different calibrated statistic.
- **Semi-coherent run powers:** one coherent rectangular coefficient per 209.7152 s run, then an inverse-variance weighted sum of powers. For proper Gaussian independent coefficients, normalized power has unit noise variance; a weak signal adds h² Tᵢ/sᵢ. Optimal weights are proportional to Tᵢ/sᵢ, giving power-statistic SNR h² sqrt[Σᵢ (Tᵢ/sᵢ)²]. With equal noise this is the N^(−1/4) strain improvement over one run. It requires phase tracking *within* runs and coefficients not recoverable from the PSD averages.
- **Incoherent archive projection:** combine the already averaged powers of 64000 nominal non-overlapping Hann segments per run. Each segment has ENBW 457.82 Hz and equivalent coherent time 1/ENBW = 2.1843 ms for a bin-centered tone. Under independent powers, the run's averaged normalized power has variance 1/64000, giving the analogous weighted SNR with per-segment sensitivity. This uses the shortest coherence requirement. Bin offset (scalloping), spectral lines, time-dependent Doppler and correlations can reduce the practical sensitivity. Grouping powers does not restore phase. No actual line statistic, background distribution, detection efficiency, FAR or threshold calibration was performed. Both power-statistic columns are for SNR 1; for SNR 5 multiply strain by sqrt(5), with the weak-signal variance convention held fixed.

The fully phase-coherent ideal requires a phase-continuous calibrated LO/ADC timebase, reconstructed sample/record epochs and gaps, gain and phase calibration across all runs, and a tested source-dependent phase model including Doppler and sidereal response. Frequency drift of the detector and the signal would have to be propagated through the time-dependent cavity response. As simple tolerances, a rectangular exposure over the timestamp span loses 10% coherent amplitude at a constant residual frequency error of about **4.52 µHz**, or at independent Gaussian residual phase scatter of about **0.459 rad RMS**. At 1.25 MHz IF the latter corresponds to about **58 ns** of residual timing error *if the LO phase is separately tracked*; it does not relax the RF phase reference requirement. These are single-error illustrations, not a validated coherence budget. Run-power combination relaxes phase alignment across runs but still requires within-run tracking and coverage of the same physical signal.

Neither the coherent nor semi-coherent exposure factor is applied to single PBH transients. The supplement provides conditional projections, not experimental exclusions.

## Results at the physical resonances

Values are H / N. ASD is in strain/√Hz. Thresholds are peak strain at the indicated statistic's SNR 1.

| Mode | Weighted complex ASD | Full coherent ideal | Weighted run powers | Weighted Hann powers |
| --- | ---: | ---: | ---: | ---: |
| TM010 | (6.67 / 6.19)×10⁻²⁰ | (2.02 / 1.87)×10⁻²² | (1.15 / 1.06)×10⁻²¹ | (2.24 / 2.07)×10⁻²⁰ |
| TM011 | (9.71 / 8.75)×10⁻²⁰ | (2.94 / 2.65)×10⁻²² | (1.67 / 1.50)×10⁻²¹ | (3.25 / 2.93)×10⁻²⁰ |
| TM012 | (1.25 / 1.12)×10⁻¹⁹ | (3.79 / 3.40)×10⁻²² | (2.15 / 1.93)×10⁻²¹ | (4.19 / 3.76)×10⁻²⁰ |

The resonance ASD has **0.86%, 0.90%, 1.06%** relative SD across runs. Its campaign-weighted value is **1.55%, 1.62%, 1.92%** higher than the corresponding run-680 same-estimator noise. Weighting improves thresholds by less than **0.04%** over equal weights for this campaign. These measured fluctuations quantify the effect of run-to-run noise variation and are separate from field, overlap and coherent transfer systematics.

[Summary table](summary.csv), [summary graph](campaign.png), [validation and input hashes](validation.json). The full curve and run-by-run tables and PDF graph are stored locally in `../analysis-work/Run2/reports/iq_noise_summary_v49_campaign_supplement/`.

To reproduce with NumPy, SciPy, Matplotlib and h5py:

```bash
OPENBLAS_NUM_THREADS=1 python3 simulation/v49_campaign/run.py \
  ../analysis-work/Run2 ~/flash-data/analysis/autoreco/Run2/fft_by_run /path/to/new-output
```
