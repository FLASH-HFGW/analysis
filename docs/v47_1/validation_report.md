# v47.1 validation — 17 November 2026

-53PDFpages and53nativePPTXslides;42unchangedpages have identicalPDFcontent,slideXMLand previewhashes.
-11changedpages:26,28,31,34,42,43,46,48,49,50,53. No other content changed.
-All tracked primary CSVs and approved model metrics retain their original hashes.
-Slide46:6240 DC/AC/magnitude/phase/ratio values checked against previous results; maximum absolute difference2.17e-18 (floating-point roundoff; mixed observable units).
-Slide48:4680 empirical fractions reproduce exactly;4680 stored thresholds unchanged exactly;4680 moment-based Rayleigh predictions agree with maximum difference1.91e-17. No new fit or threshold selection.
-Explicit provenance:152rows,32inputdefinitions,all53slides covered. Input file hashes and named datasets/JSONpaths/CSVcolumns validated.
-Scatterplot panels have separate axes labels and colorbar; short sensor names used consistently. Complete names remain unchanged in the sensor table/documentation.
-No raw reads, simulations, new fits or new transfer-function construction.

Correlations are run-level noise-power associations, not measured instantaneous I/Q correlations/coherence. Per-mille spectral changes are qualified by the residual PSD/FIR estimator discrepancy, not assigned a new physical uncertainty. The archived toy thermal-pole inconsistency remains explicit. This is the reproducible experimental baseline frozen before independent RF/electronics work.
