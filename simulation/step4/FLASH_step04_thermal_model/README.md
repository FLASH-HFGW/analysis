# FLASH — theoretical thermal cavity baseline (Step 4)

This is **NOT** calibrated to any FLASH/QUAX data. The tone from Steps 1–3 is removed.

Reproduce with `python validate_step04.py` (requires NumPy, SciPy, Matplotlib).

Inputs: 100 mK thermal bath, single TM010-like resonator f0=8.8 GHz Q0=50,000, beta=1, loaded Q=25,000.
Complex Gaussian bath with 10 MHz bandwidth around resonance; generated from theoretical Bose–Einstein occupancy n(T).
The cavity transfer has a Lorentzian PSD and complex causal single-pole response.
Downconversion is implemented by placing its equivalent complex envelope at 1 MHz IF,
without creating the full 8.8 GHz carrier. A 4th-order analog Butterworth LPF at 1.9 MHz
is applied before 5 MS/s complex ADC sampling. I and Q use 16 bit quantization over ±5 V.

**Important:** An arbitrary ideal noiseless 140 dB gain is used to make the thermal output visible
on the ADC voltage scale. This is a numerical thought experiment, not a complete quantum-consistent
phase-insensitive amplifier model. Vacuum noise, incident-port noise and amplifier noise are deliberately
NOT included yet. The cryogenic thermal emission alone vanishes as T -> 0, whereas a real linear coherent
receiver's measured noise need not vanish, owing to vacuum and amplifier-added contributions.

The signal has **no coherent tone** and no five phase clusters. IQ points form a circular
Gaussian cloud, amplitude is Rayleigh, phase is uniform. Short-lag complex correlation
oscillates at the IF while its envelope decays approximately with tau=Q_L/(pi*f0).

Power unit convention: spectral density S_P in W/Hz at a 50 ohm load,
with E[|z|²]/R = integral S_P(f) df for an analytic complex voltage signal.

Expected numerical checks are recorded in metrics.json; reproducible data saved in NPZ.
