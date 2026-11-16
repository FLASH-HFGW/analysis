# FLASH Gedankenexperiment — Step 2 (reproducible)

## Reproduce

```bash
python validate_step02.py
```

Dependencies: Python 3, NumPy, SciPy and Matplotlib. The code writes numerical
arrays (`step02_arrays.npz`), measured outputs (`results.json`) and the two
figures (`step02_validated.png`, `step02_phase_correlation.png`).

## What is held fixed relative to Step 1

TM010 model resonance: 8.737119 GHz, QL=29306. Steady coherent tone at cavity
resonance, complex amplitude 1. LO chosen 1 MHz lower, so IF=+1 MHz.
5 MS/s ADC, 16 bits, bipolar assumed ±5 V.

## What changes in Step 2

Added complex zero-mean Gaussian noise with *flat RF input spectrum* across
10 MHz, centered at the cavity resonance, and input complex RMS = 1 a.u.
The cavity transfer 1/(1+i 2π Δf τ) (τ=QL/(π fr)) filters that noise.
Both the steady tone and filtered noise then go through an ideal I/Q mixer,
**assumed** 4th-order analog Butterworth LPF at 1.9 MHz, and 5 MS/s ADC.

An envelope simulation at 40 MHz is used instead of sampling the 8.7 GHz RF
carrier. The stationary process is synthesized by Fourier masking and filtered
in the Fourier domain (periodic steady state). This does NOT simulate source
switch-on, thermal cavity emission, input-output noise correlations, real
mixer imbalance, additive amplifier noise or the measured frequency response.

## Interpretation

The RF input has a flat 10 MHz wide spectrum, but the resonator narrows the
cavity-output noise PSD to a Lorentzian profile (~298 kHz FWHM in power).
The coherently driven tone produces five phase-synchronous clusters at
fIF/fs = 1/5. Gaussian noise broadens them radially and angularly. This does
not by itself demonstrate sidebands or out-of-band noise.

Markers show *actual ADC samples*, with thin lines only joining consecutive
samples. Phase residual is the wrapped angle of the event-vs-baseline complex
ratio, here referring to added noise, not an injected transient.

## Validation

14 assertions verify RF band limits, Gaussian-noise RMS, cavity response,
linear superposition to within quantization, quantization bounds, tone IF,
noise variance, covariance/PSD consistency, analog LPF's alias rejection,
and no clipping. They validate this mathematical implementation, **not the
real instrument**. For finer validation inspect results.json and test the
independent software modules against measured calibration data.
