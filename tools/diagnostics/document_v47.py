"""Write reviewable reports from completed v47 validations, without scientific recomputation."""
from pathlib import Path
import json,csv,shutil
R=Path('/home/mazzitel/HFGW/analysis');W=R.parent/'analysis-work/Run2';O=W/'reports/iq_noise_summary_v47';D=O/'data';A=W/'diagnostics/v47_primary_audit_20261117';docs=R/'docs/v47';docs.mkdir(exist_ok=True)
v=json.loads((O/'validation_complete.json').read_text());v1=json.loads((D/'v1_v2_dataset_comparison.json').read_text());sensors=v['temperature_mapping']
# Correct the obsolete early-stage summary using the completed published-v1 extension.
p=D/'consolidation_validation.json';c=json.loads(p.read_text());c['v1_compared_runs']=v1['compared_runs'];c['v1_missing_runs']=v1['missing_v1_runs'];c['v1_dataset_mismatches']=sum(x['different'] for x in v1['datasets'].values());p.write_text(json.dumps(c,indent=2))
p=O/'slide_observable_provenance.csv'
with p.open() as f:rr=list(csv.DictReader(f))
for row in rr:
 i=int(row['slide'])
 if (row['version']=='v46' and 25<=i<=28) or (row['version']=='v47' and 25<=i<=29):
  row['observable_families']='resonance_empirical_run680;approved_toy';row['numeric_sources']='resonance_bank_pilot_v1_20261117/run00680_resonance.h5; resonance_campaign_primary_v47_20261117/expectations_and_campaign.h5; results.json'
with p.open('w') as f:
 wr=csv.DictWriter(f,fieldnames=rr[0]);wr.writeheader();wr.writerows(rr)
text='''# v47 — consolidated experimental-noise characterization

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
'''
(O/'README.md').write_text(text);(docs/'README.md').write_text(text)
report=f'''# Validation report — 17 November 2026

- Complete primary v2 campaign:260runs,780run–mode rows; each1048576000complexsamples/mode and1000SPEC.
- DC²+AC²=totalRMS²:maximum relative residual{v['maximum_DC_identity_relative_error']:.3g}.
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
'''
for x in v['absolute_comparison']:report+=f"|{x['mode']}|{x['fullband_data_over_toy_RMS']:.6f}|{x['resonance_data_over_toy_RMS']:.6f}|{x['thermal_RMS_ADC_uV']:.6f}|{x['thermal_power_ppm']:.6f}|\n"
report+='''
Full-band and resonance discrepancies are almost equal within each mode; this is not a measurement of missing gain. Predicted thermal power remains2.4–3.2ppm even at resonance. The observed negative temperature association does not match the positive temperature derivative of cavity emission at fixed conditions. Common gain/receiver-noise/electronic-state changes remain unresolved hypotheses.

## Residual limitations

- Fine512×512IQhistograms and empirical fitted-Rayleigh-threshold counts use existing full-run raw diagnostics because standardv2stores256×256grids and different thresholds. No counts are reconstructed from aPSD.
- Full-band PSD,g1 and phenomenological characteristic times are existing selected1.048576swindows; these are separate from full-run amplitudes and campaign summaries. Existing fitted times are not newly fitted and are not cavity decay measurements.
- Oldfull-runtoy thermal pole1MHz differs from the approved analytic physicalf0−LO1−LO2coordinates. It is preserved and documented, not silently corrected or resimulated. Its thermal contribution is tiny but the inconsistency remains real.
- Narrowbandg1 is dominated by50kHzFIR(≈20µs), not cavitydecay(≈1µs). Samples:full-band200ns;decimated4µs.
- Temperature labels are verified byODB/INPTschema and targetedrawrecords; physical identities follow operator identification. The4Kplate is aHEMTstage proxy, not aHEMTdevice temperature. Calibrationaccuracy is not newly established.
- Correlations usePearson/Spearman with direct time-colored plots; clock residuals and first differences are diagnostics, not causal/physical response fits.
'''
(O/'validation_report.md').write_text(report);(docs/'validation_report.md').write_text(report)
psd='''# Verification of seven archived PSDs

The distinct FFTpipeline is not v2noise reconstruction. Runs691,692,743,746,876,894,921 were executed withiq_sign=+1; the other253with−1. Provenance checks tie archived products to byte-identical job artifacts and logged arguments. Historical software reportsreco_version1.1; exact frozen-sourceSHAis unavailable, so byte-identical historical software is not claimed.

Existing targetedchecks read8originalSPEC from each of these7runs and controls680,681,939. ExplicitI−iQ and I+iQ transforms satisfy exact conjugation/reindexing to numerical precision, separately for all3modes. Final validation independently confirms all21correctedarrays equal the exact reflected originals; no similarity-based correction or fitted rescaling.

Originalarchives remain unchanged. Correctedcopies:analysis-work/Run2/diagnostics/frequency_sensor_closure_v47_20261117/corrected_fft_by_run/.

EachSPEC contains64chunks originally16384samples, with the lastsample dropped:actualFFTlength16383. Frequencycoordinates are reconstructed for16383, including correct odd-lengthreflection andFFTshiftordering. Hann coherentamplitudenormalization is converted toPSD usingfs*sum(w²)/sum(w)²; equivalentnoisebandwidth≈457.82Hz, or1.50009156FFTbins. ADCvoltagefactor2/5appliedonce; per-chunkmeans are removed. PSDpower is integrated with actualKaiser8.6FIR2001tap|H|²,50kHznominal,ENBW47428.8068Hz.

All260signedcoordinates now pass. Comparison against eight noncentralv2electronicbands has max powerdifferences<0.108%. DCband is not used for identitychecks because full-runv2DCsubtraction differs from per-chunkFFTmeanremoval. The residual estimator discrepancy is recorded without empirical correction. No new complete rawrun was reconstructed.

Machine evidence:data/FFT_coordinate_verification.json,data/seven_PSD_reindex_validation.csv and the originalraw_checkJSONs referenced byverification.json. No empirical amplitude/phase/taildistribution is inferred from thesePSDs.
'''
(O/'seven_PSD_report.md').write_text(psd);(docs/'seven_PSD_report.md').write_text(psd)
t='''# Temperature sensor mapping and data quality

| Operator sensor | Physical identity | Equipment | ODB name | Zero-based INPT index | Alias | Unit |
|---|---|---|---|---:|---|---|
|17|RF cavity — Dale1.5K, RuO₂|Temp_AVS|T4|15|T15|mK|
|18|Mixing Chamber plate — CMN143|Temp_AVS|T5|16|T16|mK|
|19|Mixing Chamber plate — CMN130|Temp_AVS|T6|17|T17|mK|

Operator numbers are not bank indices. Identity is checked through original equipment/eventID,bankINPTlength,ODBlabel,extractioncodechannelindex andschema. It is not inferred from ordering17→15 alone. Physicalnames follow operator identification; electronicsmapping is verified independently.

All three channels have260valid positive runmedians,10–11observations perSPECinterval. UnitsmK are documented by the channelmap; an empty ODBunitfield is not independent calibration. Medians use cached originalINPTobservations insidev2SPECtimestampbounds with no interpolation. OriginalschemaIDandindices remain in sensor_inventory.json.

Additional measured stage sensors include4Kplate(Mercuryindex4,Diode_4K_T K),50Kplate(index2,Pt_50K_T K),magnet(index12,RuO2_Mag_T K),still(AVS11),50mKplate(AVS12),TWPA(AVS13),noise source(AVS14)andheat switch(Mercury10). Full coverage, ranges and quality flags are retained in sensor_inventory.json. MercuryMCdiode(index8) is zero throughout and excluded.

The4Kplate diode spans3.9912–4.0569K with260valid medians. TheHEMTis documented at4Kstage; this is a stage-temperature proxy, not case/junctionthermometry. CavityPearson associations are strongest among the original3mKsensors; adding4Kplate yields stronger negative correlations. Neither is interpreted as causal. Additionalstagecorrelations are available in fullband_temperature_correlations_v2.csv and resonance/electronic correlations in results.json.
'''
(O/'temperature_mapping.md').write_text(t);(docs/'temperature_mapping.md').write_text(t)
changes='''# Changes from v46

- Preserve approved PartI and run680scientificslides1–24; slide15changes physicalsensornames only.
- Rebase full-bandmoments,CV,thresholds and9electronicbands directly to260v2HDF5; retain v1comparisondifferences instead of assuming identity.
- Close signedPSDcoordinates for7provenIQ+products; all260runs now enter resonance-centeredcampaignplots with actualFIRweighting.
- Add explicit full-band versus centralresonanceabsoluteRMSratios and conditionalthermalRMS/powerfractions.
- Clarify50kHzFIRtimescale versus intrinsiccavitydecay; preserve full-runthermalpoleinconsistency in documentation.
- ReplaceT15/T16/T17genericnames with verified physicalsensoridentities and add4K/50K/magnetstageplots and descriptive4Kcorrelations.
- Quantify commonRMSdrift and much smaller resonanceshapechanges. No physicalcausalfit, hardwaremodel, newTn/gain/kz orPartIV.
- Keep commontrend and clockcontrols in appendix;53pages total versus49inv46.
- Add complete per-slide/per-observableprovenance, inheritedinputinventory, validationCSV/JSON and reproducibility instructions.
- Preserve earlier v47snapshot and everypreviousversion.
'''
(O/'changes_from_v46.md').write_text(changes);(docs/'changes_from_v46.md').write_text(changes)
# Publish compact numerical and provenance evidence in Git; bulky scientific arrays remain external.
for name in ['observable_provenance.csv','absolute_fullband_resonance_comparison.csv','noise_spans.json','consolidation_validation.json']:
 shutil.copy2(D/name,docs/name)
shutil.copy2(O/'validation_complete.json',docs/'validation_complete.json');shutil.copy2(O/'slide_observable_provenance.csv',docs/'slide_observable_provenance.csv')
print('Documentation complete:',O,docs)
