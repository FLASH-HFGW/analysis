# FLASH/QUAX — VNA Calibration and Cavity Characterization

This 15-slide scientific presentation consolidates the Phase A inventory,
fit extension, validity audit, cavity timeline and Run 1429 spectral pilot.
The editable PPTX contains native text, notes and table cells rendered as
editable shapes. The measured and fitted plots are embedded figures.

## Regeneration

From the repository root, with Python 3.9 or newer and DejaVu Sans installed:

```sh
python -m pip install python-pptx==1.0.2 matplotlib Pillow
python reporting/vna_calibration_20261125/generate.py --output /tmp/vna-deck
```

The bundled PNGs and `source_snapshot.json` are sufficient for regeneration
away from PSGE. The PDF and PPTX are rendered from the same slide model
with the repository's shared scientific deck renderer. PowerPoint font
substitution can produce small visual differences from the PDF.

To verify and refresh the bundle directly from the read-only analysis outputs:

```sh
python reporting/vna_calibration_20261125/generate.py \
  --work /home/mazzitel/HFGW/analysis-work \
  --reference /home/mazzitel/HFGW/worktrees/run2-run3-pilot/comparison/root-pilot/rf-calibration
```

The snapshot records source paths and SHA-256 hashes. The source directories
cover Phase A, the VNA fit extension, the validity-interval audit, the
cavity-characterization timeline and the Run 1429 VNA/PSD pilot. Regeneration
reads those sources without writing to them. No raw measurements or ROOT/HDF5
products are bundled.

## Deck contents

The six scientific figures are the three Run 1429 mode fits (measured and
fitted magnitudes, wrapped phase and fractional residuals), the fitted
resonance and loaded-Q timelines, and the TM012 VNA-versus-ADC-PSD comparison.
The three accompanying CSVs cover fit quality, association coverage and
TM012 conditional intervals. All six selected plots were available.

See [the scientific summary](SUMMARY.md) for the conclusions and limitations.

Validation reopened the PPTX with python-pptx, checked 15 slide titles
against the corresponding PDF pages and verified all shape bounds.
All 15 exported PDF pages were rasterized and visually reviewed.
A separate regeneration produced identical PPTX slide XML and media,
and identical PDF page rasters. Microsoft PowerPoint or LibreOffice
rendering was unavailable on the validation host.
