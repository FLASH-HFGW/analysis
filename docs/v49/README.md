# HFGW analysis v49

Consolidated English presentation. Parts I–IV preserve the frozen 65-slide v48, including the original experimental and low-frequency studies and the approved Step 9A–9E calibration. The appendix adds Part V (Step 10A–10D), Part VI (conditional strain and PBH results) and Part VII (conclusions and experimental roadmap). Original visible page numbers are preserved on the inherited pages.

Complete products are local under `../analysis-work/Run2/reports/iq_noise_summary_v49/`. The folder contains PDF, editable PPTX, indexed figures and vectors when available, numerical figure data or source selectors, the detailed slide ledger, validation and SHA-256 manifests. The figure index includes a shortlist for a later 20-minute talk. Physical benchmark tables, waveforms and figures are under `../analysis-work/Run2/simulation/v49_hfgw/`. The pre-existing numerical dependencies stay at their original locations and are cited in each figure's ledger. The published tree contains light reference material only.

Cavity geometry and field use the Spasiano thesis benchmark. Run-specific magnet state and the numerical gravitational overlap grids remain unavailable. The conditional scale, PSD conventions, signal support, coherent transfer and independent validation are documented in the [physics README](../../simulation/v49_hfgw/README.md).

## Reproduction

From the repository checkout, with NumPy, SciPy, h5py, Matplotlib, Pillow, python-pptx, pypdf and Poppler:

```bash
OPENBLAS_NUM_THREADS=1 python3 simulation/v49_hfgw/run.py ../analysis-work/Run2 /path/to/new-physics
OPENBLAS_NUM_THREADS=1 python3 reporting/iq_noise_summary_v49/build.py ../analysis-work/Run2 /path/to/new-physics /path/to/new-v49
```

Use fresh output directories. The presentation builder checks the archived v48 hashes before assembling either file.
