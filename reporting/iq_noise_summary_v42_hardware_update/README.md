# v42: hardware documentation update

This is a presentation/documentation revision, not a scientific-analysis revision.

- `docs/hardware/README.md` inventories the original chain, manufacturer specifications, actual settings, experimental evidence, hypotheses and missing measurements. Five original Mini-Circuits datasheets were retrieved from the official manufacturer URLs; supplied Marki/FEMTO originals and the original two-slide chain are preserved.
- The updated 10-slide Part I reuses the v41 slide model. Only slide 2 is replaced with the actual-component functional chain. Slide 9's numerical/graphical normalization is unchanged; its notes reference the new inventory. Other slide content is unchanged apart from version footers.
- A standalone editable chain and a five-slide hardware discussion insert are exported separately. The latter belongs **after** the existing toy/data comparison, not immediately after Part I. It finishes with **Proposed hardware characterization**. This preserves the user's request to review Part I before assembling the remainder of the presentation.
- The existing step 8 PSD/correlation figure is copied without recalculation. Its initial parameters remain phenomenological; they are not attributed to any splitter. No additional transfer function, free parameter, fit or simulation is introduced.
- Model parameters, ADC scaling, kz calibration, gains and absolute normalization are unchanged. Manufacturer component losses are not added to the empirical chain calibration. Source code for steps 1–8 is untouched.

## Build

From the repository root, with the same matplotlib/Pillow/python-pptx environment used for v41:

```sh
python reporting/iq_noise_summary_v42_hardware_update/build_slides.py
```

Inputs are external saved products:

- `../analysis-work/Run2/reports/iq_noise_summary_v41_partI/slide_model.json` and referenced assets;
- `../analysis-work/Run2/simulation/step8_LF_initial_20261116/PSD_and_complex_correlation.png`.

Outputs remain outside Git in `../analysis-work/Run2/reports/`:

- `iq_noise_summary_v42_partI/` — 10-slide PDF/PPTX and previews;
- `iq_noise_chain_v42/` — standalone editable hardware chain;
- `iq_noise_summary_v42_hardware_discussion/` — five-slide discussion PDF/PPTX and previews.

The builder copies numeric plot assets, checks SHA-256 before/after export, asserts unchanged content of Part I slides 1 and 3–10 (except the explanatory note on slide 9), and writes `hardware_update_validation.json`. No numeric products or generated presentation files are versioned. Original hardware reference documents are intentionally versioned as source documentation, distinguished from generated scientific products.

## Review and limits

PDF/PPTX export succeeded for 10+1+5 slides. The chain and discussion contact sheet were visually inspected. Hardware identities from the original drawing are retained, but its I-side BPF labels, original ADC channel ordering and ambiguous RF amplifier identification are not silently treated as verified installation records. Manufacturer typical behavior is not substituted for installed-unit measurements. Some cryogenic/source components lack matching original manufacturer datasheets in the supplied package; the inventory explicitly marks their unsupported specifications unknown rather than borrowing related models. Proposed laboratory work remains future work only.
