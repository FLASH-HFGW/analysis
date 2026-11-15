# FLASH Step 5 — receiver noise added to Step 4 thermal cavity

**Reproduce:** `python validate_step05.py` (requires numpy, scipy, matplotlib).
The script expects a sibling directory `FLASH_step04_thermal_model/` containing the exact original step04 `step04_arrays.npz` and `metrics.json`.

No coherent tone in either scenario. Cavity thermal signal exactly reused from Step 4, sample by sample.

### Nominal parameters
- Single-mode *theoretical* cavity: 8.8 GHz, T=100 mK, Q0=50,000, beta=1.
- Receiver-added equivalent noise temperature: Tadd=3.955 ± 0.468 K; **indicative** from Spasiano thesis, dedicated configuration without TWPA, p. 132.
- Thesis reports measured gain 67.81 ± 0.39 dB, **not applied** here: changing it would destroy the controlled Step 4 comparison. The model retains Step 4's arbitrary ideal 140 dB gain.
- Added noise source is a white *complex* Gaussian process, input-referred PSD S_add = kB Tadd W/Hz, over [-5,+5] MHz at complex IF, added after cavity response but before the shared 4th-order 1.9 MHz analog LPF.
- The same 5 MS/s, 16-bit ADC is used, with ±5 V nominal range.
- All source colors fixed: cavity cyan, receiver electronics orange, total purple. I has filled and Q hollow sample markers.

### Important limits
This is a **lumped equivalent-input** receiver noise source, not a model of individual HEMT, TWPA, FET, mixer losses or quantization noise temperature. The thesis' Tn is a characteristic of a particular experimental setup, used as an illustrative prior and not assumed applicable to actual run conditions.
The gain 140 dB is purely numerical and does not match the measured 67.81 dB. Tadd often already includes vacuum effects as seen by the receiver; adding another half-photon now would risk double-counting.
A PSD of **kB Tadd** is used as a classical equivalent noise temperature parameter for this thought experiment; this is not an independent microscopic quantum fluctuation model.
An ideal 4th-order LPF is not sufficient to eliminate all >2.5 MHz power: the alias fraction is quantified and retained as a limitation.
Quantization is applied only once to the sum. Separate quantized components do not add sample-by-sample without an error of order LSB.

Machine-readable datasets and test outcomes are in `step05_arrays.npz` and `metrics.json`.
