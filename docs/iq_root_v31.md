# Run3 ROOT v3.1 — format, calibration and operational runbook

This is the **canonical technical reference** for FLASH native ROOT v3.1 products. A short path index is retained in `docs/ROOT_V3_1_FORMAT.md` on the analysis branch for compatibility. For command-line inspection see [`examples/tool/README.md`](../examples/tool/README.md).

## MIDAS TWPA Run 1422 inventory

Read-only GFAL job 4201 produced a per-event audit with examples, serial numbers, timestamp intervals, payload sizes and ODB values in `/tmp/flash-root-inventory.RcyBIV/results/inventory.json`. MIDAS timestamps are Unix seconds. ROOT preserves MIDAS numeric bank types and associates each bank with its event header through an event index.

| Equipment (ID) | Bank (type) | Content | Events | Bytes/event; total | HDF5 v3 | ROOT v3.1 |
|---|---|---|---:|---:|---|---|
| LocalOscill (7) | LOSC (DOUBLE, 10) | Eight LO/pump setpoints, frequencies and output settings | 1 | 64; 64 | Analogous BOR fields only | Original payload, BOR/EOR |
| Temp_Mercury (10) | INPT (FLOAT, 9) | 13 values and ODB schema | 12 | 52; 624 | Yes | Thermometer group and original bank |
| Temp_FP (11) | INPT (FLOAT, 9) | 20 values and ODB schema | 12 | 80; 960 | Yes | Thermometer group and original bank |
| Temp_AVS (12) | INPT (FLOAT, 9) | 25 values and ODB schema | 12 | 100; 1200 | Yes | Thermometer group and original bank |
| timestampGPS (2) | TGPS (BYTE, 3) | 80-byte GPS reference | 212 | 80; 16960 | Payload and timing | Exact payload/header, v3 timing |
| NetBox (1) | SPE0–SPE5 (WORD, 4) | 1,048,576 ADC samples/channel | 1,000 each | 2,097,152; 2,097,152,000 each | Derived observables | Derived observables, inventory and headers, **raw ADC samples excluded** |
| NetBox (1) | SPGP (DWORD, 6) | 790 empty banks, 209 pairs and one single word | 1,000 | 0/4/8; 1676 | Decoded PPS/diagnostics | All payloads, including empty/incomplete |
| MIDAS (0x8000) | BOR | Byte-exact ODB snapshot | 1 | 1086305 | Selected ADC/LO/mapping fields | Complete, SHA-256, event index |
| MIDAS (0x8001) | EOR | Byte-exact ODB snapshot | 1 | 1085303 | EOR flag | Complete, SHA-256, event index |
| CryoSwitch (4), SA (5), VNA (6) | — | ODB-configured equipment | 0 | 0 | VNA/SA settings not represented | Snapshot and calibration metadata |

The transient Run 1145 included SPE6, and v3 retains its PPS measurements; SPE6 was absent in Run 1422. The schema records a channel's inventory and detector result whenever SPE6 occurs, while excluding ADC waveforms. Legacy SPEC waveforms are excluded likewise. Other banks, including unknown types, retain their original bytes. Headers, event indices, bank names, types and lengths permit later decoding. No interpolation or new PPS-to-UTC precision is claimed.

## Calibration and RF-coordinate provenance

- **VNA BOR:** nominal references at 8.744560, 8.787249 and 8.846287 GHz. VNA settings include S21, 2,001 points, 2 MHz span, IFBW 300 Hz and −58 dBm. `vnaCalib` retains 2,001 values per real/imaginary component of S11/S12/S21/S22 traces with different ODB dates. Compact numeric copies are browsable under `Calibration/measurements`.
- **VNA/Fit:** requested parameters include f0, Q0, beta1/beta2 and amplitudes; request, result and references are preserved. An initial model/guess is not a measured Q. The original outcome is not assigned to additional modes: its explicit reference concerns Mode3.
- **TWPA:** the BOR records pump enabled at 7.891 GHz and `power Pump` setting −6.1, with `With_TWPA=True`. `twpaCalib` contains scan boundaries, maximum ODB S21 of 23.693951 and conditions at that maximum. A map maximum is **not** a gain curve applicable to PSD correction; the pump setting is not independently calibrated output power.
- **Absent run measurements:** Run 1422 contains no bank with VNA traces, injected tones or magnetic-field measurements. The snapshot contains LO/pump setpoints, VNA configuration and SA attenuation, not an in-run measurement of gain, total attenuation or magnetic field B. Missing references remain marked as missing. See [`frequency_coordinates_run680_audit.md`](frequency_coordinates_run680_audit.md) for the historical coordinate audit.
- **External calibration files:** GFAL listed 106 files in `flash/data/LNF/calib/`. The three Mode3 references under `VNA/Fit/Output` and `twpaPumpMap_LocalOscill_2026-11-19_12-04-23.txt` were found by exact basename. ROOT records snapshots, ODB paths, original text, URLs, file stats and Adler32. Files with no explicit relationship remain unassociated; proximity in time alone is insufficient. External files are not embedded. Nominal IF/RF coordinates use the documented model only, and are marked unavailable when inconsistent.
- **ADC:** scale and I/Q convention come from BOR and explicit configuration. PSD remains expressed in V²/Hz at the ADC. No RF gain correction or conversion to strain is performed.

The auxiliary extension occupies approximately 2.19 MB before indices/compact numeric copies and ZSTD compression. The excluded raw ADC samples amount to 12.58 GB uncompressed. Because HDF5 v3 does not carry complete ODB snapshots, migration regenerates the output from raw files **using the same scientific code**, comparing all existing HDF5 datasets byte-for-byte before publishing ROOT. This follows the normal new-production path and does not require an additional thermometer backfill.

## Native ROOT layout and logical reader paths

Native TTrees use ZSTD level 4. Top-level directories are `Acquisition`, `Calibration`, `TM010`/`TM011`/`TM012`, `Timing`, `Thermometers`, `SlowControl`, `ODB` and `Provenance`. For example, `TM010/Spectra/window_psd` contains one row per ordered one-second window; `Acquisition/SpectralAxes/window_bin_edges_hz` provides shared bin edges. `short_rectangular` and `short_hann` use `Acquisition/ShortFFT/frequency_hz`. Statistics, anomalies and histograms remain typed. `__iq_schema__` is a TObjString holding exact dtypes/attributes and the mapping to logical paths used by the common reader. `Attributes` TObjStrings are accessible from TBrowser. Data are stored once; display relies on trees and axes, without duplicating PSDs as histograms.

### Common logical paths

The supported Python reader `examples/iq_products.py` calls `examples/iq_root.py` to map native ROOT objects to HDF5-style logical paths.

| Logical path | Meaning |
|---|---|
| `metadata` attributes | Run, sampling frequency and ADC/IQ settings |
| `spectra/<mode>/window_psd` | Ordered one-second power spectral density, typically 209 × 50,000, 100 Hz resolution, V²/Hz |
| `spectra/window_bin_edges_hz` | Signed frequency-bin edges |
| `spectra/window_bin_width_hz` | Per-bin bandwidth |
| `timing/windows` | Received-sample starting indices for ordered windows |
| `timing/digitizer_events` | Digitizer event headers including `header_unix_s` |
| `thermometers/<equipment>/events` | Structured thermometer event array with `time_unix` field |
| `thermometers/<equipment>/values` | Temperatures by event and channel |
| `thermometers/<equipment>` attribute `channels_json` | Channel indices, ODB names and units (K/mK) |
| `statistics/<mode>` attributes | Full-run means, RMS, I/Q covariance and other moments |

Normally there are 209 complete one-second PSD windows; the leftover fraction of the run contributes to **full-run statistics** but is not an extra complete PSD window. **`window_psd` stores powers, not complex FFT coefficients.** The 16,384-sample short FFT powers are available only as averages: their individual chronological ordering is not preserved.

Read a bounded spectrum slice and thermometer samples without loading complete 50,000-bin spectra:

```python
import sys
sys.path.insert(0, "examples")
from iq_products import open_product

with open_product("/path/to/run01429_iq_v3.1.root") as product:
    print(product.file["spectra/TM010/window_psd"][0:1, :10][0])
    for name, unit, unix_times, temperatures in product.temperatures():
        print(name, unit, unix_times[:2], temperatures[:2])
```

The thermometer timestamps are slow-control/event-header Unix seconds, **not PPS-calibrated ADC timestamps**. Hardware identity for Run3 sensor connections has not been independently verified. Sensor mapping details are in `docs/v47/temperature_mapping.md` on branches containing that study.

### Analysis reader examples

```bash
PYTHONPATH=/path/to/uproot:examples python examples/analyze_iq_run.py /local/run01422_iq_v3.1.root /local/run1422-report
PYTHONPATH=/path/to/uproot:examples python examples/analyze_iq_history.py /local/staged --output /local/history
```

Use ROOT/HDF5 files staged locally from the worker. The run JSON includes calibration tables and bank inventory; history processing uses linear observables and compatible frequency-coordinate groups.

## Release and ROOT migration

Production release requires a successful real ROOT test with a GFAL receipt. ROOT outputs use `runNNNNN_iq_v3.1.root` in Run3; HDF5 outputs keep their original naming. Select ROOT mode in local configuration through `output_format: "root"`, `root_dependencies` and `root_dependencies_sha256`. Uproot for Python 3.9 is staged on the UI local filesystem and transferred as an approximately 4.3 MB software dependency. Workers retain GFAL download/publish and t1 token handling; only receipts and logs return through spool.

Normal production retains the 20/20 limits. `--migrate-root` runs in a separate runtime while using the same production lock/cycle and `migration_max_active` (default 40). It selects verified completed HDF5 products no longer queued, whose record still points to HDF5. Already-submitted HDF5 jobs keep their expected URLs and become eligible after completion. After verified migration, `reco_version` and `reco_output_path` are updated, retaining `reco_done`.

```bash
autoreco/run_autoreco_cron_configured.sh --run3 --migrate-root --dry-run
autoreco/run_autoreco_cron_configured.sh --run3 --migrate-root
```

Repeat the migration cycle to reconcile the queue and fill available slots. The normal cron needs no modification. Monitor `production` and `root-migration` runtime directories and `condor_q -constraint 'FlashRun3Attempt isnt undefined'`.

## Read-only consolidation audit

```bash
PYTHONPATH=autoreco:/cvmfs/mazzitel-personalrepo.infn.it/package/python3.9/site-packages \
  /usr/bin/python3 autoreco/root_storage_dry_run.py \
  --output /tmp/run3-consolidation.json --export-evidence-requests /tmp/run3-gfal-checks.json
```

The report distinguishes absent, incompatible, invalid and verified items. Deletion-eligibility fields require recent worker-side checksums (`--worker-evidence`), scientific equivalence and an already updated logbook. Pass worker evidence as `--remote-evidence` to estimate recoverable bytes and identify residual temporary names. Without fresh remote evidence, eligible deletions are **zero bytes**. This command deletes neither raw nor HDF5 files.

## Validated end-to-end result and release references

The real Run 1422 MIDAS test (job 4202) completed with exit code zero. Slot wall time was 642 s; scientific analysis took 370.51 s and conversion/validation/publication 32.02 s. ROOT size was **156,901,974 bytes**, with identical local/remote Adler32 **721868e3**.

All **43 pre-existing HDF5 datasets** and all **67 round-trip datasets** compared identically. The archive preserved 1,251 event headers, 7,249 bank records, 21,484 auxiliary payload bytes, both ODB snapshots and 12 readings from each of three thermometer families. The final ROOT product was opened by the worker using Uproot. ROOT C++ and PyROOT read the native layout locally using a verification file derived from Run 1148; that is **not** a second full end-to-end run. The production receipt is at `/tmp/flash-root31-e2e.5LBPzL/01422/publication.json`.

For activation, automatic migration in the existing cron and operational checks, consult the [final Run3 ROOT v3.1 runbook](run3_root31_runbook.md). The actual dry run selected 272 runs and 40 initial jobs without writing the sheet. The verified HDF5 in that snapshot represents 51.24 GB potentially recoverable. Consolidation without post-migration remote evidence still classifies **zero bytes deletable**.

## Read-only CLI utilities

Standalone tools are under [`examples/tool/`](../examples/tool/README.md), with historical command paths maintained as documented there.

```bash
python examples/tool/print_window_fft.py /path/to/run01429_iq_v3.1.root
python examples/tool/export_temperatures.py --directory /path/to/Run3 --start 1429 --end 1446 --output temperatures.csv
```

The first command prints the first ten **one-second PSD** bins for each mode by default. The second exports timestamped temperatures from the selected ROOT run interval. The underlying reader modules remain in `examples/`.

This is the canonical format and operational reference; the per-file `__iq_schema__` remains authoritative for object names, types and dimensions.
