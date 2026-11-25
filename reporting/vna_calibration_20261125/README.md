# FLASH/QUAX — VNA Calibration and Cavity Characterization

This 64-slide scientific presentation consolidates the Phase A inventory,
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
away from PSGE, together with the frozen acquisition snapshot. The PDF and PPTX are rendered from the same slide model
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

## Acquisition dates and candidate windows

The source is [FLASH-logbook, worksheet log](https://docs.google.com/spreadsheets/d/1dBHc4fwQgmx092ohra6Y-ueF_BpOPVk26BNhi5dCRnM/edit#gid=0).
The frozen snapshot was acquired at 2026-11-25 15:19:27 UTC. It contains
1,814 canonical acquisition rows from Run 680 through Run 2558.
Only run number, sheet row and the two acquisition epochs are stored.
The original date strings were checked against those epochs in the sheet's
Europe/Rome timezone. UTC display dates are derived from Unix epochs.
The snapshot SHA-256 is in `source_snapshot.json`.

If authorized logbook access and the repository's gspread environment are
available, `snapshot_logbook.py` can read the same worksheet into a **new**
path. Refreshing the committed acquisition snapshot is a separate decision.

The primary chronology interprets unzoned VNA filenames as Europe/Rome
and converts them to UTC. The alternate scenario treats unverified
filename clocks as UTC while preserving independently verified clocks.
For each mode, the window starts at the end of the triplet's last
trace and closes at the first trace of the next fitted triplet.
A run must begin at or after the opening and end strictly before the
closing. Runs crossing a boundary are listed separately. The final
window is right-censored at the last dated acquisition in the snapshot.
The JSON carries the actual run membership and both boundary records;
the CSV has explicit first and last start/end times under both hypotheses.

The primary chronology covers all 1,814 dated acquisitions per mode
across 35 nonempty windows. Six windows have no complete runs. Thirty-three
of the 41 windows change membership under the alternate clock hypothesis.
This chronological coverage is separate from the 1,784-run scientific
association census. A temporal interval does not establish calibration
selection or applicability. The existing evidence-supported conditional
intervals are carried separately in the table.

The dB metric is `20 log10(Abs21)`, where `Abs21` is the dimensionless
S21 magnitude-model amplitude from the original simultaneous fit, referenced
to unit amplitude. It is neither the measured value at resonance nor a
receiver gain calibration. The optional resonance shift is relative to
the first in-scope fitted triplet of the same mode under the primary clock
interpretation. The reference fit ID is recorded in every row.

## Deck contents

The 12-slide overview precedes 11 chronological table slides and 41
full-page fit panels. Every available original fit plot is included,
with measured and fitted magnitudes, wrapped phase and fractional
residuals. The overview retains the Run 1429 TM012 VNA-versus-ADC-PSD
comparison and the regenerated resonance and loaded-Q plots. Run 680
is excluded from both timelines and remains in the table and fit
appendix under **Historical reference**.

See [the scientific summary](SUMMARY.md) for the conclusions and limitations.

Validation reopened the PPTX with python-pptx, checked all 64 slide titles
against the corresponding PDF pages and verified all shape bounds.
All 64 exported PDF pages were rasterized and visually reviewed.
A separate regeneration produced identical PPTX slide XML and media,
and identical PDF page rasters. Microsoft PowerPoint or LibreOffice
rendering was unavailable on the validation host.
