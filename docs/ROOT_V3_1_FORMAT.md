# ROOT v3.1 format — documentation entry point

The complete, canonical ROOT v3.1 product-format reference is [`docs/iq_root_v31.md`](iq_root_v31.md).

This file is retained as a short compatibility entry point for references created during the Run2/Run3 pilot. To avoid inconsistent descriptions of the same schema, all ROOT v3.1 layout details, native paths, ordered 1-second PSD definitions, thermometer schemas, calibration provenance, and migration instructions now live in the canonical guide.

The per-file `__iq_schema__` manifest and the implementations `examples/iq_root.py` and `examples/iq_products.py` remain authoritative for reader and dataset details.

Standalone read-only inspection scripts are described in [`examples/tool/README.md`](../examples/tool/README.md):

```bash
python examples/tool/print_window_fft.py /path/to/run01429_iq_v3.1.root
python examples/tool/export_temperatures.py --directory /path/to/Run3 --start 1429 --end 1446 --output temperatures.csv
```

**Important:** `window_psd` is one-second **power spectral density** (V²/Hz), not complex FFT coefficients. Thermometer timestamps are slow-control Unix seconds and are not automatically PPS-calibrated ADC timestamps.
