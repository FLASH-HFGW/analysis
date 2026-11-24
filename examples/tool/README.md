# FLASH ROOT v3.1 quick tools

These read-only utilities use the existing `examples/iq_products.py` and `examples/iq_root.py` readers. Requires Python, NumPy, h5py and uproot for ROOT inputs.

## Print the first 10 bins of one-second low-resolution PSD

```bash
python examples/tool/print_window_fft.py /home/mazzitel/flash-data/analysis/autoreco/Run3/run01429_iq_v3.1.root
python examples/tool/print_window_fft.py /path/to/run01429_iq_v3.1.root --mode TM012 --window 1
python examples/tool/print_window_fft.py /path/to/run01429_iq_v3.1.root --all-windows
```

Default: first 10 values of the *first* one-second PSD window, for TM010, TM011 and TM012. `--all-windows` outputs the first 10 per window (209 windows per run normally). An arbitrary list of ROOT files may be supplied.

**Terminology:** `spectra/<mode>/window_psd` stores PSD **powers** (V²/Hz), *not complex FFT coefficients*. The one-second PSD is normally 209 windows × 50,000 bins at 100 Hz resolution. The first ten entries are near the lowest signed electronic frequency (~−2.5 MHz), **not** the ten bins around zero. Short FFTs are stored as averages, without per-FFT chronological order.

## Export temperatures from a run range

```bash
python examples/tool/export_temperatures.py \
  --directory /home/mazzitel/flash-data/analysis/autoreco/Run3 \
  --start 1429 --end 1446 \
  --output temperatures_1429_1446.csv

# Optional: omit zero/negative/invalid readings
python examples/tool/export_temperatures.py \
  --directory /home/mazzitel/flash-data/analysis/autoreco/Run3 \
  --start 1429 --end 1446 --valid-only \
  --output temperatures_valid.csv
```

One CSV row per thermometer reading, with run, source file, UTC ISO date, original Unix timestamp, sensor channel, original temperature/unit, Kelvin, validity and coverage flags. Some runs have multiple readings per sensor. Missing files are reported and skipped. The output file must not already exist. Use `--pattern` to override the filename template.

**Timing caveat:** sensor Unix timestamps are slow-control/header times, not PPS-calibrated ADC times. Physical sensor assignment is documented in `docs/v47/temperature_mapping.md`, but Run3 wiring is not independently verified. Do not infer microsecond coincidence with digitizer samples.
