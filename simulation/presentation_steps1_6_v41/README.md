# Common short examples for Part I, v41

This is a new, separate presentation series. Historical steps1–8, run680 data,
full-run toys and all previous reports remain unchanged. The examples contain
262,144 complex ADC instants each, at5MS/s: **52.4288ms**, not a full run.
There are no new fits, experimental raw reconstruction or LF-response repairs.

## Progressive construction and common parameters

All stages use the final measured TM010 cavity parameters: f0=8.737119GHz,
Q0=52,490, kappa1=0.001122, kappa2=0.79, physical T=40.422386mK; step6 adds
TM011/TM012 with their thesis parameters. Actual IFs from the already extracted
LO settings are1.250/1.248/1.256MHz. Receiver Tn=3.955K is an inherited equivalent
no-TWPA measurement, applied conditionally to the modes, not fitted to these data.

- **Step1:** a known synthetic coherent probe, **−115dBm**, validates the readout
  with the cavity bypassed. It is a safe numerical test input, not the recorded
  −60dBm calibration acquisition. The reference source plane is explicit.
- **Step2:** the same source plus controlled injected Gaussian probe noise passes
  through the actual port1→port2 response. The injected generator setting has
  equivalent noise PSD kB×3.955K; it is a validation input, not wall thermal noise.
  The weak input coupling is retained, not normalized to unity to conceal loss.
- **Step3:** preserve the exact probe/injected-noise realization and add an
  independent equivalent receiver-noise realization.
- **Step4:** switch **both** validation sources off, and receiver off. Use only
  intrinsic wall-bath emission, with Bose–Einstein thermal energy and both-port
  damping. No coherent tone, no extra vacuum term, no arbitrary140dB gain.
- **Step5:** reuse the exact step4 wall-bath realization and the exact receiver
  realization of step3. Quantize their sum once.
- **Step6:** retain TM010 exactly unchanged from step5, and add independent draws
  for the other measured modes. No nominal143dB readout scale is introduced.

The unit complex-Gaussian spectral draws for the injected probe noise and wall
bath are shared where applicable; their physical source PSD and transfer differ.
The receiver draw is reused exactly. Seeds alone do not substitute for these
array-equality checks. Independent modes have separate draws.

## Physical and instrumental normalization

The convention is matched complex RMS-equivalent volts,
`E(abs(z)^2)/R = integrated available noise PSD`, R=50ohm.
`z=I-iQhardware=I+iQeff`. Plot Qeff explicitly: it is −Qhardware.

Cavity thermal transfer uses `sqrt(ki*k2)/(kt/2+i2*pi*detuning)` and driven probe
transfer uses `sqrt(k1*k2)/(kt/2+i2*pi*detuning)`, with rates
`k1=ki*kappa1`, `k2=ki*kappa2`, `kt=ki+k1+k2`. The causal cavity phase sign is
stated under numpy's forward exp(−iωt) convention. The measured scalar readout
magnitude has no calibrated phase; phase0 is chosen for stationary synthesis.
This does not establish the transient phase of every physical stage.

**The same readout map is applied once in every stage:** RF103.4dB and the
measured per-mode integrated-tone kz multiplied by0.01 for LF60→20dB. The
measured readout contains the LPF/mixer response; no extra Butterworth is applied.
Calibration kz already has the±5V count conversion. It gets no additional0.4.
Science ADC uses±2V and4/65535V/count, independently on I and Qeff. Aliases within
the measured response support are folded before synthesis. Response beyond the
sweep remains zero as in the existing calibrated reference.

No hypothetical change of LF response, high-pass, image correction, DC offset,
new noise floor or per-mode gain fit is included. The common Tn, RF gain and
frequency-independent LF setting ratio remain conditional assumptions.
Expected total RMS is27.173/13.701/8.406mV ADC, consistent with the existing
calibrated full-run reference. Differences of the short MC realization are
finite-sample fluctuations, not newly fitted normalization factors.

## Thermal-only ADC limitation is shown, not hidden

Thermal-only pre-ADC RMS is about14.61uV for TM010, below the61.04uV ADC step.
About99.34% of the complex ADC samples in this short realization are exactly
zero. The analog field is approximately proper Gaussian; the isolated digitized
field is **not** therefore a well-resolved Gaussian/Rayleigh population. Its
phase is defined only for the remaining nonzero samples. The figures display
this fact with labelled microvolt insets and separate continuous/ADC curves.
Adding receiver noise in step5 also changes the quantization behavior. Separately
quantized source streams must not be added to produce the final ADC stream.

## Figure conventions

Six recurring panels: sampled I/Q, IQ cloud, amplitude density, phase density,
PSD and complex g1. Main axes and positions are fixed across steps; step2 and
step4 have explicitly labelled physical zooms. There is no hidden display gain.
Markers are actual quantized ADC samples: filled I, open Qeff. Lines connect
pre-quantization values on the same sample grid; they are not an invented dense
continuous waveform. The IQ display uses consecutive samples, avoiding aliasing
of the calibration circle by a plotting stride.

Amplitude-density horizontal axes use A divided by the **predicted pre-ADC RMS**
for shape comparison only; a separate strip gives physical pre/post-ADC RMS.
Histograms and phase plots use fixed bins and scales; exactly-zero ADC phases
are excluded. PSD uses a16384sample symmetric Hann estimator, no automatic
segment mean removal, bilateral normalization fs×sum(w²). Covariance uses a
single record mean and linear FFT pairs divided by N−lag, with no fitted decay.
The block-mean overview is restricted to times with at least32blocks and uses
the same sampled-source covariance with finite-record mean removal.

Palette: wall/injected source cyan, receiver orange, total ADC purple, probe
and analytic reference navy. I/Q use marker fill; modes use solid/dashed/dotted
and circle/square/triangle. Calibration-mode curves preserve the total/readout
colour and use line style, rather than reassigning source colours to modes.

## Reproduction and outputs

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 simulation/presentation_steps1_6_v41/simulate_examples.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 reporting/iq_noise_summary_v41_partI/build_slides.py
OPENBLAS_NUM_THREADS=1 python3 reporting/iq_noise_summary_v41_partI/validate_partI.py
```

Only sources, configuration and documentation belong in Git. Numerical outputs:
`analysis-work/Run2/simulation/presentation_steps1_6_v41/short_examples.h5` and
`metrics.json`. Presentation products are separate under
`analysis-work/Run2/reports/iq_noise_summary_v41_partI/`.
The31simulation checks cover shared draws, source powers and ADC behavior;
validation additionally verifies the absolute budget against the existing
full-run reference, absence of tones from science stages, source sums and scope.
