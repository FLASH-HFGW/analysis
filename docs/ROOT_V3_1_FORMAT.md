# FLASH ROOT v3.1 — logical product format

The native ROOT v3.1 files are written by `examples/iq_root.py` and read using `examples/iq_products.py`. Each file contains the `__iq_schema__` manifest, which maps the logical HDF5-style dataset paths to native ROOT objects. For example, logical `spectra/TM010/window_psd` maps to native `TM010/Spectra/window_psd`. Avoid assuming these are ordinary flat TTrees; use `open_product()`.

## Useful logical datasets

| Path | Interpretation |
|---|---|
| `metadata` attributes | Run, sampling rate, ADC/IQ conventions |
| `spectra/TM010/window_psd`, `spectra/TM011/window_psd`, `spectra/TM012/window_psd` | Ordered one-second PSDs (usually shape 209 × 50,000; 100 Hz; V²/Hz) |
| `spectra/window_bin_edges_hz` | Signed bin edges |
| `spectra/window_bin_width_hz` | Bin widths |
| `timing/windows` | Received-sample start indices for the one-second windows |
| `timing/digitizer_events` | Digitizer headers and Unix seconds |
| `thermometers/<equipment>/events` | Structured `time_unix` field |
| `thermometers/<equipment>/values` | Samples × thermometer channels |
| `thermometers/<equipment>` attribute `channels_json` | Channel names, indices and K/mK units |
| `statistics/<mode>` attributes | Full-run I/Q moments and covariance, RMS, etc. |

There are normally 209 complete 1-second PSD windows plus a partial remainder contributing to full-run statistics. **One-second window_psd is not an array of complex FFT coefficients.** Individual 16,384-sample short FFT powers are temporally averaged and no per-short-FFT time ordering is preserved in these products.

Read a small slice without loading all 50,000 frequency bins:

```python
import sys
sys.path.insert(0, "examples")
from iq_products import open_product

with open_product("/path/to/run01429_iq_v3.1.root") as product:
    print(product.file["spectra/TM010/window_psd"][0:1, :10][0])
    for channel, unit, timestamps, values in product.temperatures():
        print(channel, unit, timestamps[:2], values[:2])
```

See the two command-line scripts in `examples/tool/`. Thermometer Unix timestamps are header/slow-control timestamps, not PPS-calibrated microsecond timestamps; sensor-to-hardware identification in Run3 is not independently verified. For further detail, see `docs/v47/temperature_mapping.md` and `docs/ANALYSIS_CONTEXT.md`.

This guide documents reader paths confirmed from code; it is not a complete enumeration of all v3.1 groups or a substitute for the per-file `__iq_schema__` manifest.
