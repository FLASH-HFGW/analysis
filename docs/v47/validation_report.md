# Validation report — 17 November 2026

- Complete primary v2 campaign:260runs,780run–mode rows; each1048576000complexsamples/mode and1000SPEC.
- DC²+AC²=totalRMS²:maximum relative residual1.55e-16.
- Legacy correctedDC/AC/mean/temperature table:6240numeric checks passed; primary tables regenerated directly fromv2.
- Electronic band rows7020; resonance band rows5460; resonance coordinates validated260/260.
- PSD versus all eight noncentral electronic bands:max differences(TM010/011/012)0.09671%,0.10734%,0.10316%. This small estimator discrepancy is retained, not empirically corrected.
- Electronic powers previously reconstructed from relative tables versus directv2:max relative difference3.4e−15.
- Compared originalv1HDF5 withv2 for94available runs, dataset by dataset.166v1originals are absent on available local/connected storage, listed inJSON; equivalence is not asserted there. No v1reconstruction launched.
- Historical raw-statistics table compared for35880values across all260runs:114differences, confined to3sigmaepisode counts/rates(57count/rate pairs). Sample-above-threshold counts and fractions agree. Newv47usesv2episodes; no global v1/v2identity assertion.
-31nonidentical dataset/run cases among availablev1HDF5; differences concern phase increments (runs680and727) and one run-relative TM011 phase histogram (run680). Absolute global phase histograms agree where compared. Dataset names, differences and runIDs are in`v1_v2_dataset_comparison.json`. All phase-increment observables in v47 are v2.
- PDF/PPTX both53pages; native PPTXtext preserved; no new physical model, fit, gain adjustment, Tnchange or full-runsimulation.

## Main numerical findings

Full-band RMS max/min spans:TM0102.63769%,TM0112.74912%,TM0123.25845%. Resonance central/side relative spans:0.32750%,0.23552%,0.24411%. These are measured variations, not gain measurements.

| Mode | Full-band data/toy RMS | Resonance data/toy RMS | Thermal RMS[µV ADC] | Thermal power[ppm] |
|---|---:|---:|---:|---:|
|TM010|1.187181|1.172852|4.749595|3.236425|
|TM011|1.514352|1.533161|2.185571|2.821138|
|TM012|1.633754|1.634596|1.256173|2.428824|

Full-band and resonance discrepancies are almost equal within each mode; this is not a measurement of missing gain. Predicted thermal power remains2.4–3.2ppm even at resonance. The observed negative temperature association does not match the positive temperature derivative of cavity emission at fixed conditions. Common gain/receiver-noise/electronic-state changes remain unresolved hypotheses.

## Residual limitations

- Fine512×512IQhistograms and empirical fitted-Rayleigh-threshold counts use existing full-run raw diagnostics because standardv2stores256×256grids and different thresholds. No counts are reconstructed from aPSD.
- Full-band PSD,g1 and phenomenological characteristic times are existing selected1.048576swindows; these are separate from full-run amplitudes and campaign summaries. Existing fitted times are not newly fitted and are not cavity decay measurements.
- Oldfull-runtoy thermal pole1MHz differs from the approved analytic physicalf0−LO1−LO2coordinates. It is preserved and documented, not silently corrected or resimulated. Its thermal contribution is tiny but the inconsistency remains real.
- Narrowbandg1 is dominated by50kHzFIR(≈20µs), not cavitydecay(≈1µs). Samples:full-band200ns;decimated4µs.
- Temperature labels are verified byODB/INPTschema and targetedrawrecords; physical identities follow operator identification. The4Kplate is aHEMTstage proxy, not aHEMTdevice temperature. Calibrationaccuracy is not newly established.
- Correlations usePearson/Spearman with direct time-colored plots; clock residuals and first differences are diagnostics, not causal/physical response fits.
