# v47 — consolidated experimental-noise characterization

The v47 delivers 53 English slides. The primary scientific data are the complete 260 v2 HDF5 products, runs680–939. Prior versions, raw files, archived FFTs and the earlier v47 are preserved. The earlier v47 is saved as `iq_noise_summary_v47_before_primary_audit_20261117`.

## Deliverables

- `iq_noise_summary_v47.pdf` and `.pptx`: presentation; approved scientific slides1–24 preserved, sensor naming on15 updated.
- `run680_resonance_comparison_supplement.pdf`: every resonance band, empirical distributions and analytical PSD/covariance.
- `slide_observable_provenance.csv`: all49v46 and all53v47 slides, source statements, numeric datasets, software, IQ/DC/ADC/population scope.
- `data/observable_provenance.csv`: per-observable definitions and explicit exceptions.
- `data/inherited_intermediate_inventory.csv`: hashed intermediate products fromv17,v37,v40,v44,v45.
- `data/fullband_v2.csv`, `raw_statistics_v2.csv`, `electronic_bands_v2.csv`: directv2 numerical exports.
- `data/normalized_amplitude_moments_v2.csv`, `phase_increment_moments_v2.csv`: dimensionless moments and continuous circular increments.
- `data/campaign_band_powers.csv`:5460resonance-band powers from validated signed PSDs, actual FIR response.
- `data/temperatures_by_run.csv`, `sensor_inventory.json`, `temperature_SPEC_bounds_provenance.json`.
- `validation_complete.json`, `validation_report.md`, `seven_PSD_report.md`, `temperature_mapping.md`, `changes_from_v46.md`.

The complete empirical distributions (198MB) remain at `analysis-work/Run2/diagnostics/v47_primary_audit_20261117/primary_v2_distributions.h5`. Counts are copied fromv2, never synthesized from moments/PSD. Histogram voltage edges are corrected once; copied nested global_statistics remains in native stored units and is explicitly distinguished from corrected CSV exports. No empirical full-band abs(z−mean(z)) histogram is claimed.

## Reproduction

Requires existing scientific data and approved model inputs, plus NumPy,SciPy,h5py,Matplotlib,Pillow,python-pptx,pypdf,pdftoppm. Scientific inputs remain outsideGit. In this environment PPTX/PDF helpers are under `/tmp/v18-python-deps` and `/tmp/v46-pdf-deps`.

1. Reuse the validated `frequency_sensor_closure_v47_20261117` and `resonance_campaign_closed_v47_20261117` products; do not rerun their raw checks unless evidence changes.
2. `python3 tools/diagnostics/consolidate_v47.py` extracts v2; run only if primary audit products are absent/stale. `python3 tools/diagnostics/complete_v1_audit_v47.py` compares only the missing v1 runs.
3. `PYTHONPATH=/tmp/v18-python-deps:/tmp/v46-pdf-deps python3 reporting/iq_noise_summary_v47/build_slides.py`
4. `PYTHONPATH=/tmp/v18-python-deps:/tmp/v46-pdf-deps python3 tools/diagnostics/finalize_v47.py`
5. `python3 tools/diagnostics/document_v47.py`
6. `python3 -m unittest examples.tests.test_frequency_closure_v47 -v`

Sources for targeted raw verification and sensor closure are versioned as `examples/verify_fft_coordinates_v47.py` and `examples/close_resonance_campaign_v47.py`. Reusing their existing results avoids duplicate raw processing. All new scientific tables use ADC V,V² or dimensionless units; no new143dBinput-referred quantities are generated. Approved model Tn,gain,kz and full-run simulations are unchanged. PartIV is absent.
