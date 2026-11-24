# FLASH standalone tools

Standalone inspection/export scripts are organized under `examples/tool/`. Their old paths at `examples/<name>.py` remain executable compatibility wrappers; shared DAQ/product modules and scientific campaign scripts remain in `examples/`.

## ROOT v3.1 tools

```bash
python examples/tool/print_window_fft.py /path/to/run01429_iq_v3.1.root
python examples/tool/print_window_fft.py /path/to/run01429_iq_v3.1.root --mode TM012 --window 1
python examples/tool/export_temperatures.py --directory /path/to/Run3 --start 1429 --end 1446 --output temperatures.csv
```

`print_window_fft.py` prints the first ten bins of the first **one-second PSD** per mode by default, not complex FFT coefficients. Use `--all-windows`, `--window`, `--mode` and `--n`. `export_temperatures.py` writes one row per thermometer reading, including UTC ISO date, Unix timestamp, original unit, temperature in kelvin, and quality flags. Invalid temperature readings are retained unless `--valid-only` is given. It refuses to overwrite a CSV.

Requirements: Python, numpy, h5py and uproot; ROOT reader APIs remain under `examples/iq_products.py` and `examples/iq_root.py`.

## Other moved CLI tools (old paths preserved)

- `print_bank.py` — MIDAS equipment and bank inspection
- `plot_saved_fft.py` — plot saved NPZ FFT summaries
- `read_calibfiles.py` — inspect legacy NPZ calibrations
- `fft_viewer.py` — interactive HDF5 FFT viewer
- `extract_thermometers.py` — extract MIDAS thermometry into CSV, resumable
- `plot_thermometers_history.py` — plot thermometry histories

For the ROOT file schema see [`docs/iq_root_v31.md`](../../docs/iq_root_v31.md). The ODB sensor mapping is in `docs/v47/temperature_mapping.md` on branches where that historical analysis exists. Slow-control Unix timestamps are not calibrated PPS-to-ADC times.
