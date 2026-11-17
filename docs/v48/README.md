# v48 — Part IV: RF Calibration and Readout Electronics

The English presentation contains the 53 frozen v47.1 pages followed by 12 new pages, numbered 54–65. The original pages retain their visible pagination and footer. Part IV summarizes the approved Step 9A–9E work through commit `a418b23`. Its comparisons distinguish observed calibration and run-680 quantities, manufacturer specifications and conditional predictions.

- [PDF](iq_noise_summary_v48.pdf)
- [Editable PowerPoint](iq_noise_summary_v48.pptx)
- [Part IV contact sheet](part_iv_contact_sheet.png)
- [Validation report](validation_report.md) and [machine-readable results](validation.json)
- [Slide/observable provenance](slide_observable_provenance.csv)

Part IV includes the independent L5 fits, signed frequency mapping, nominal hardware response, coherent tone comparison, secondary-mixer folding, common-mask noise comparison and TM010 I/Q diagnostics. It retains the uncertainty of equal RF noise PSD in the two bands and the limitations of the generator setpoint, cable path, hardware settings and existing tone spacing. The new thermal comparison uses the physical poles already adopted in Step 9D.

The appendix renderer uses the established v47.1 layout and palette. Composite figures read approved tables with no new inference. VNA fit plot assets retain their data panels and use English marginal captions. Text, tables and speaker notes are native in PowerPoint.

## Reproduction

From the repository root, provide the directory containing the archived v47.1 PDF and PPTX. Dependencies are Python, NumPy, Matplotlib, Pillow, python-pptx, pypdf with incremental writer support, and Poppler `pdftoppm`.

```bash
python3 reporting/iq_noise_summary_v48/build.py \
  ../analysis-work/Run2/reports/iq_noise_summary_v47_1 docs/v48
```

The builder verifies the archived SHA-256 hashes before assembling either deliverable and records new output hashes after the preservation checks.
