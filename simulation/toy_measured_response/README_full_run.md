# Full-run toy simulation

Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 simulate_full_run.py`.
Then run `python3 report_full_run.py`.

Results are separated in `/home/mazzitel/HFGW/analysis-work/Run2/simulation/toy_full_run680/`.

Each mode has exactly 1,048,576,000 samples at 5 MS/s (209.7152 seconds).
The v24 gain-plane hypothesis and measured magnitude response are retained.
Analog PSD contributions within the measured sweep are folded onto the sampled
frequency band before designing a complex FIR spectral factor. A 65,537-tap
factor is checked against the target power and first 50 covariance lags.
Overlap-save convolution preserves the white-noise history across every block.
Random prehistory initializes a stationary realization, not a zero-padded start.

Histograms and raw complex moments are accumulated over the whole run. Covariance
includes cross-block pairs and is centered with exact global mean and endpoint
corrections. Quantization uses ±2 V and 4/65535 V/count; clipping is checked.
Only 100,000 example samples per mode are retained. Other outputs are aggregate
histograms, fitted Rayleigh scale, moments, empirical and expected covariance.

No gain is adjusted per mode. Response outside the measured sweep is still assumed
zero; phase is not measured; the extra-FET reference plane remains conditional.
