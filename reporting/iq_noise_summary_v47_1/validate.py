"""Validate and document the frozen v47.1 editorial/table-only revision."""
from pathlib import Path
import json,csv,hashlib,sys,shutil
R=Path(__file__).resolve().parents[2];W=R.parent/'analysis-work/Run2';B=W/'reports/iq_noise_summary_v47';O=B.with_name('iq_noise_summary_v47_1');DOC=R/'docs/v47_1';DOC.mkdir(exist_ok=True)
sys.path[:0]=['/tmp/v18-python-deps','/tmp/v46-pdf-deps'];from pypdf import PdfReader;from pptx import Presentation
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
v=json.loads((O/'validation.json').read_text());changed=set(v['modified_slides']);a=PdfReader(B/'iq_noise_summary_v47.pdf');b=PdfReader(O/'iq_noise_summary_v47_1.pdf');pa=Presentation(B/'iq_noise_summary_v47.pptx');pb=Presentation(O/'iq_noise_summary_v47_1.pptx');assert len(a.pages)==len(b.pages)==len(pa.slides)==len(pb.slides)==53
unchanged=[n for n in range(1,54) if n not in changed]
for n in unchanged:
 assert a.pages[n-1].get_contents().get_data()==b.pages[n-1].get_contents().get_data(),n
 assert pa.slides[n-1].element.xml==pb.slides[n-1].element.xml,n
 assert sha(B/f'slide_{n:02d}.png')==sha(O/f'slide_{n:02d}.png'),n
ledger=json.loads((O/'input_sha256.json').read_text());assert all(sha(p)==h for p,h in ledger.items())
baseledger=json.loads((B/'validation.json').read_text())['input_sha256'];model=W/'simulation/presentation_steps1_6_v43/metrics.json';assert sha(model)==baseledger[str(model)]
reg=json.loads((O/'dependency_registry.json').read_text());assert all(sha(x['file'])==x['sha256'] for x in reg.values())
with (O/'slide_observable_provenance.csv').open() as f:rows=list(csv.DictReader(f))
assert {int(x['slide']) for x in rows}==set(range(1,54));assert len(rows)==152
# Check required qualifiers and no unintentional page geometry changes.
model=json.loads((O/'slide_model.json').read_text());text=lambda n:' '.join(x['text'] for x in model[n-1]['items'] if x['kind']=='text')
assert '2.4–3.2 ppm' in text(26) and 'predicted electronic noise dominates by roughly 3 ppm' not in text(26)
assert '1.048576 s' in text(28) and '209.7152 s' in text(28) and '20 µs' in text(28)
assert '10–11 observed readings per run' in text(53) and 'per SPEC interval' not in text(53)
assert 'estimator mismatch' in text(49) and 'instantaneous' in text(49)
for s in model:
 for it in s['items']:assert it['x']>=0 and it['y']>=0 and it['x']+it['w']<=13.35 and it['y']+it['h']<=7.51
checks=v['numeric_checks'];v.update(version='v47.1',PDF_pages=53,PPTX_pages=53,unchanged_pages=unchanged,unchanged_PDF_content_exact=True,unchanged_preview_hashes=True,approved_model_metrics_hash_unchanged=True,primary_input_hashes_unchanged=True,explicit_provenance_rows=len(rows),explicit_dependency_definitions=len(reg),provenance_inference='Explicit slide-number/observable registry; no title keyword classification',slide46_compared_numeric_values=24*260,slide48_compared_fraction_values=18*260,slide48_compared_threshold_values=18*260,slide48_compared_Rayleigh_predictions=18*260,slide46_max_absolute_reproduction_error=max(x['max_abs_error'] for x in checks['slide46']),slide48_max_fraction_difference=max(x['max_fraction_difference'] for x in checks['slide48']),slide48_max_threshold_difference_ADC_V=max(x['max_threshold_ADC_V_difference'] for x in checks['slide48']),slide48_max_Rayleigh_probability_difference=max(x['max_Rayleigh_probability_difference'] for x in checks['slide48']))
(O/'validation.json').write_text(json.dumps(v,indent=2))
readme='''# v47.1 — frozen experimental-noise baseline

This is a limited revision of the approved v47 (commit275f754). It contains53 English slides. Every v47 product is preserved. No raw reconstruction, new simulation, fit, RF calibration, Tn/gain/kz change or theoretical hardware transfer function is introduced.

## Deliverables

- `iq_noise_summary_v47_1.pdf` and `iq_noise_summary_v47_1.pptx`.
- `validation.json` and `validation_report.md`.
- `slide_observable_provenance.csv`:152 explicit slide/observable/dependency rows covering all53slides.
- `dependency_registry.json`:32 input definitions with actual files, hashes, dataset/column names, available software/configuration, population, IQ, DC and ADC conventions, and primary versus historical-exception status. All referenced HDF5, NPZ, CSV and JSON fields are checked.
- `slide_dependency_map.json`: manually specified component map for each slide; no title-keyword inference. Composite slides list independent dependencies for AC moments, temperatures, PSDs, amplitude statistics and toy results.
- `input_sha256.json`, `data/` and five updated PNG/PDF figures under `assets/`.

## Limited changes

- Slide26 states the cavity thermal contribution is only2.4–3.2ppm of predicted total power.
- Slide28 separates full-runPSD(209.7152s) from measured initial-windowg1(1.048576s), and retains the≈20µsFIR scale and4µs lag sampling.
- Slides31,42,50 use shorter temperature-axis names, enlarged panel spacing and a separate colorbar. Complete physical sensor names remain in slide53 and in v47 temperature documentation.
- Slides46and48 figures are regenerated directly from unchanged primaryv2CSV tables, with numerical reproduction checks. No threshold is redefined.
- Slide49 qualifies per-mille spectral changes by the residual PSD/FIR estimator mismatch (maximum≈0.108%inpower), without promoting that mismatch into a calibrated uncertainty floor.
- Slides34,43,49 distinguish correlations of run-level noise powers from instantaneous cross-mode I/Q correlations or coherence, which were not measured.
- Slide53 states10–11readings per run within theSPEC-timestamp acquisition interval.

Only11PDFpages/PPTXslides are replaced. The other42retain exact PDF content streams, native PPTX slideXML and preview hashes. Unchanged pages retain their original v47 footer, preserving the approved pages; this final container and changed pages are labeledv47.1.

## Reproduction

Use existing approved v47 products and the dependencies listed in the registry. No science reconstruction is needed. Requires NumPy,SciPy,h5py,Matplotlib,Pillow,python-pptx,pypdf; the existing environment helpers are available under `/tmp/v18-python-deps` and `/tmp/v46-pdf-deps`.

```bash
PYTHONPATH=/tmp/v18-python-deps:/tmp/v46-pdf-deps python3 reporting/iq_noise_summary_v47_1/build_slides.py
python3 reporting/iq_noise_summary_v47_1/provenance.py
PYTHONPATH=/tmp/v18-python-deps:/tmp/v46-pdf-deps python3 reporting/iq_noise_summary_v47_1/validate.py
```

## Preserved scientific limitations

The old full-run toy places the cavity thermal pole at1MHz, unlike the approved physicalf0−LO1−LO2coordinates. This inconsistency is preserved and documented; it is not silently corrected or resimulated. Tn remains3.955K, with unchanged RF gains and calibratedkz. The full-band selected-window diagnostics and high-resolution empirical IQ/fitted-threshold products remain explicit historical exceptions where standardv2does not provide those estimators. The originalv47 limitations, including incomplete availability of originalv1HDF5, remain valid. This revision does not re-open or extend the approved experimental characterization.
'''
# Ensure standard typographic spacing in review documents.
for before,after in [('commit275f754','commit 275f754'),('53 English','53 English'),('all53slides','all 53 slides'),('Slide26','Slide 26'),('Slide28','Slide 28'),('Slides31,42,50','Slides 31, 42 and 50'),('slide53','slide 53'),('Slides46and48','Slides 46 and 48'),('Slide49','Slide 49'),('Slides34,43,49','Slides 34, 43 and 49'),('Slide53','Slide 53'),('Only11PDFpages/PPTXslides','Only 11 PDF pages/PPTX slides'),('other42retain','other 42 retain'),('Tn remains3.955K','Tn remains 3.955 K'),('at1MHz','at 1 MHz'),('2.4–3.2ppm','2.4–3.2 ppm'),('per run within theSPEC','per run within the SPEC')]:readme=readme.replace(before,after)
(O/'README.md').write_text(readme);(DOC/'README.md').write_text(readme)
report=f'''# v47.1 validation — 17 November 2026

-53PDFpages and53nativePPTXslides;42unchangedpages have identicalPDFcontent,slideXMLand previewhashes.
-11changedpages:26,28,31,34,42,43,46,48,49,50,53. No other content changed.
-All tracked primary CSVs and approved model metrics retain their original hashes.
-Slide46:6240 DC/AC/magnitude/phase/ratio values checked against previous results; maximum absolute difference{v['slide46_max_absolute_reproduction_error']:.3g} (floating-point roundoff; mixed observable units).
-Slide48:4680 empirical fractions reproduce exactly;4680 stored thresholds unchanged exactly;4680 moment-based Rayleigh predictions agree with maximum difference{v['slide48_max_Rayleigh_probability_difference']:.3g}. No new fit or threshold selection.
-Explicit provenance:152rows,32inputdefinitions,all53slides covered. Input file hashes and named datasets/JSONpaths/CSVcolumns validated.
-Scatterplot panels have separate axes labels and colorbar; short sensor names used consistently. Complete names remain unchanged in the sensor table/documentation.
-No raw reads, simulations, new fits or new transfer-function construction.

Correlations are run-level noise-power associations, not measured instantaneous I/Q correlations/coherence. Per-mille spectral changes are qualified by the residual PSD/FIR estimator discrepancy, not assigned a new physical uncertainty. The archived toy thermal-pole inconsistency remains explicit. This is the reproducible experimental baseline frozen before independent RF/electronics work.
'''
(O/'validation_report.md').write_text(report);(DOC/'validation_report.md').write_text(report)
for name in ['validation.json','slide_dependency_map.json','dependency_registry.json','slide_observable_provenance.csv']:shutil.copy2(O/name,DOC/name)
# Keep a compact numerical check artifact distinct from provenance metadata.
(O/'data/reproduction_checks.json').write_text(json.dumps(checks,indent=2))
(O/'deliverable_checksums.json').write_text(json.dumps({str(p.relative_to(O)):sha(p) for p in O.iterdir() if p.is_file() and p.name!='deliverable_checksums.json'},indent=2))
print('Validated v47.1:53pages,42preserved,152explicitprovenance rows',flush=True)
