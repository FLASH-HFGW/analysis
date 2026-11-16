# FLASH reproducible Gedankenexperiment — Step 3

Run `python validate_step03.py` (requires numpy, scipy, matplotlib).
The simulation explicitly changes **one thing** relative to Step 2:
additional complex, circular Gaussian electronics noise with 10 MHz nominal
IF bandwidth and complex RMS 0.25 a.u. injected **after the cavity and mixer,
before the common analog LPF**. It uses an independent RNG seed.

The coherent tone, cavity-filtered RF noise realization, cavity model, LO,
LPF, sampling phase/rate, ADC, record length and normalization are unchanged.

## Stable colors (apply identically across input/output and all future steps)
- Blue `#0b65cc`: coherent sinusoidal reference / tone-only centers / I[n]
- Cyan `#43a1ed`: RF/cavity noise (unchanged from Step 2)
- Orange `#ed812a`: newly added electronics noise
- Purple `#7049ac`: total signal or total noise after electronics is included

**Channel convention:** I[n] uses blue, Q[n] uses teal in the time panel;
these are quadratures, not separate noise sources. Purple is reserved
exclusively for the combined noise/signal in source-comparison plots.

The saved `step03_arrays.npz` includes the exact Step 2 and Step 3 output
samples. `results.json` contains the numerical metrics and 18 automated tests.
The modeled 4th-order LPF leaves approximately 2 percent of electronic noise
power beyond 2.5 MHz before sampling; that power can alias.
Both figures use actual samples with filled markers on every displayed sample.

The 10 MHz noise at the RF and electronics injection points is NOT a 10 MHz
band at the digitizer: cavity and LPF narrow spectra. The post-mixer
additive electronics model is a hypothesis, not an instrument calibration.
