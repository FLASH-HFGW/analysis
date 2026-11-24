# FLASH standalone tools

Standalone inspection/export scripts are organized under `examples/tool/`. Old standalone CLI paths remain supported with compatibility wrappers. **Exceptions:** `examples/extract_thermometers.py` remains the intact operational worker because `thermometers_batch.py` imports it and HTCondor ships it standalone; `examples/plot_thermometers_history.py` also retains its importable functions. Both are additionally available in `examples/tool/`. Shared DAQ/product modules remain in `examples/`.

## ROOT v3.1 tools

```bash
# First 10 frequency bins and first window PSD (100 Hz resolution)
python examples/tool/print_window_fft.py /path/to/run01429_iq_v3.1.root

# Average short-FFT Hann PSD (~305.18 Hz resolution, one spectrum per run)
python examples/tool/print_window_fft.py /path/to/run01429_iq_v3.1.root --spectrum short_hann

# Average short-FFT rectangular PSD (~305.18 Hz)
python examples/tool/print_window_fft.py /path/to/run01429_iq_v3.1.root --spectrum short_rectangular

# Full-resolution 1-Hz PSD, averaged over the run
python examples/tool/print_window_fft.py /path/to/run01429_iq_v3.1.root --spectrum mean_psd

# Inspect the first 10 bins in every ordered 1-second window, TM012 only
python examples/tool/print_window_fft.py /path/to/run01429_iq_v3.1.root --spectrum window_psd --mode TM012 --all-windows

python examples/tool/export_temperatures.py --directory /path/to/Run3 --start 1429 --end 1446 --output temperatures.csv
```

`print_window_fft.py` prints the first ten frequency centers and corresponding PSD samples in V²/Hz for each selected mode. Use `--spectrum window_psd|short_hann|short_rectangular|mean_psd`, `--mode`, `--n`, `--window` and `--all-windows`. Only `window_psd` stores separate one-second PSD windows (~100 Hz bins). The short rectangular/Hann PSDs (~305 Hz) are averaged over non-overlapping 16,384-sample blocks across the run; they do not retain individual one-second time order. `mean_psd` is the full-run averaged 1-Hz spectrum. All stored default representations are **power spectral densities**, not complex FFT coefficients.

`export_temperatures.py` writes one row per thermometer reading, including UTC ISO date, Unix timestamp, original unit, temperature in kelvin, and quality flags. Invalid temperature readings are retained unless `--valid-only` is given. It refuses to overwrite a CSV.

Requirements: Python, numpy, h5py and uproot; ROOT reader APIs remain under `examples/iq_products.py` and `examples/iq_root.py`.

## Other moved CLI tools (old paths preserved)

- `print_bank.py` — MIDAS equipment and bank inspection
- `plot_saved_fft.py` — plot saved NPZ FFT summaries
- `read_calibfiles.py` — inspect legacy NPZ calibrations
- `fft_viewer.py` — interactive HDF5 FFT viewer
- `extract_thermometers.py` — extract MIDAS thermometry into CSV, resumable
- `plot_thermometers_history.py` — plot thermometry histories

For the ROOT file schema see [`docs/iq_root_v31.md`](../../docs/iq_root_v31.md). The ODB sensor mapping is in `docs/v47/temperature_mapping.md` on branches where that historical analysis exists. Slow-control Unix timestamps are not calibrated PPS-to-ADC times.
