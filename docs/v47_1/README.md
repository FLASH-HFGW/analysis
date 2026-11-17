# v47.1 — frozen experimental-noise baseline

This is a limited revision of the approved v47 (commit 275f754). It contains53 English slides. Every v47 product is preserved. No raw reconstruction, new simulation, fit, RF calibration, Tn/gain/kz change or theoretical hardware transfer function is introduced.

## Deliverables

- `iq_noise_summary_v47_1.pdf` and `iq_noise_summary_v47_1.pptx`.
- `validation.json` and `validation_report.md`.
- `slide_observable_provenance.csv`:152 explicit slide/observable/dependency rows covering all 53 slides.
- `dependency_registry.json`:32 input definitions with actual files, hashes, dataset/column names, available software/configuration, population, IQ, DC and ADC conventions, and primary versus historical-exception status. All referenced HDF5, NPZ, CSV and JSON fields are checked.
- `slide_dependency_map.json`: manually specified component map for each slide; no title-keyword inference. Composite slides list independent dependencies for AC moments, temperatures, PSDs, amplitude statistics and toy results.
- `input_sha256.json`, `data/` and five updated PNG/PDF figures under `assets/`.

## Limited changes

- Slide 26 states the cavity thermal contribution is only2.4–3.2 ppm of predicted total power.
- Slide 28 separates full-runPSD(209.7152s) from measured initial-windowg1(1.048576s), and retains the≈20µsFIR scale and4µs lag sampling.
- Slides 31, 42 and 50 use shorter temperature-axis names, enlarged panel spacing and a separate colorbar. Complete physical sensor names remain in slide 53 and in v47 temperature documentation.
- Slides 46 and 48 figures are regenerated directly from unchanged primaryv2CSV tables, with numerical reproduction checks. No threshold is redefined.
- Slide 49 qualifies per-mille spectral changes by the residual PSD/FIR estimator mismatch (maximum≈0.108%inpower), without promoting that mismatch into a calibrated uncertainty floor.
- Slides 34, 43 and 49 distinguish correlations of run-level noise powers from instantaneous cross-mode I/Q correlations or coherence, which were not measured.
- Slide 53 states10–11readings per run within the SPEC-timestamp acquisition interval.

Only 11 PDF pages/PPTX slides are replaced. The other 42 retain exact PDF content streams, native PPTX slideXML and preview hashes. Unchanged pages retain their original v47 footer, preserving the approved pages; this final container and changed pages are labeledv47.1.

## Reproduction

Use existing approved v47 products and the dependencies listed in the registry. No science reconstruction is needed. Requires NumPy,SciPy,h5py,Matplotlib,Pillow,python-pptx,pypdf; the existing environment helpers are available under `/tmp/v18-python-deps` and `/tmp/v46-pdf-deps`.

```bash
PYTHONPATH=/tmp/v18-python-deps:/tmp/v46-pdf-deps python3 reporting/iq_noise_summary_v47_1/build_slides.py
python3 reporting/iq_noise_summary_v47_1/provenance.py
PYTHONPATH=/tmp/v18-python-deps:/tmp/v46-pdf-deps python3 reporting/iq_noise_summary_v47_1/validate.py
```

## Preserved scientific limitations

The old full-run toy places the cavity thermal pole at 1 MHz, unlike the approved physicalf0−LO1−LO2coordinates. This inconsistency is preserved and documented; it is not silently corrected or resimulated. Tn remains 3.955 K, with unchanged RF gains and calibratedkz. The full-band selected-window diagnostics and high-resolution empirical IQ/fitted-threshold products remain explicit historical exceptions where standardv2does not provide those estimators. The originalv47 limitations, including incomplete availability of originalv1HDF5, remain valid. This revision does not re-open or extend the approved experimental characterization.
