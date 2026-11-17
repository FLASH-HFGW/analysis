# Verification of seven archived PSDs

The distinct FFTpipeline is not v2noise reconstruction. Runs691,692,743,746,876,894,921 were executed withiq_sign=+1; the other253with−1. Provenance checks tie archived products to byte-identical job artifacts and logged arguments. Historical software reportsreco_version1.1; exact frozen-sourceSHAis unavailable, so byte-identical historical software is not claimed.

Existing targetedchecks read8originalSPEC from each of these7runs and controls680,681,939. ExplicitI−iQ and I+iQ transforms satisfy exact conjugation/reindexing to numerical precision, separately for all3modes. Final validation independently confirms all21correctedarrays equal the exact reflected originals; no similarity-based correction or fitted rescaling.

Originalarchives remain unchanged. Correctedcopies:analysis-work/Run2/diagnostics/frequency_sensor_closure_v47_20261117/corrected_fft_by_run/.

EachSPEC contains64chunks originally16384samples, with the lastsample dropped:actualFFTlength16383. Frequencycoordinates are reconstructed for16383, including correct odd-lengthreflection andFFTshiftordering. Hann coherentamplitudenormalization is converted toPSD usingfs*sum(w²)/sum(w)²; equivalentnoisebandwidth≈457.82Hz, or1.50009156FFTbins. ADCvoltagefactor2/5appliedonce; per-chunkmeans are removed. PSDpower is integrated with actualKaiser8.6FIR2001tap|H|²,50kHznominal,ENBW47428.8068Hz.

All260signedcoordinates now pass. Comparison against eight noncentralv2electronicbands has max powerdifferences<0.108%. DCband is not used for identitychecks because full-runv2DCsubtraction differs from per-chunkFFTmeanremoval. The residual estimator discrepancy is recorded without empirical correction. No new complete rawrun was reconstructed.

Machine evidence:data/FFT_coordinate_verification.json,data/seven_PSD_reindex_validation.csv and the originalraw_checkJSONs referenced byverification.json. No empirical amplitude/phase/taildistribution is inferred from thesePSDs.
