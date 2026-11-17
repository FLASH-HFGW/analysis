"""Explicit slide-number/observable dependency registry. No title keyword inference."""
from pathlib import Path
import csv,json,hashlib
import h5py,numpy as np
R=Path(__file__).resolve().parents[2];W=R.parent/'analysis-work/Run2';B=W/'reports/iq_noise_summary_v47';O=B.with_name('iq_noise_summary_v47_1');M=['TM010','TM011','TM012'];D=O/'data';D.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def expand(prefix,fields):return [f'{prefix}/{f}' for f in fields]
reg={}
def dep(name,file,fields,role,version,config,population,DC,ADC,upstream=None,notes=''):
 file=Path(file);assert file.exists(),file
 reg[name]=dict(file=str(file),sha256=sha(file),datasets_or_columns=fields,role=role,reconstruction_version=version,configuration=config,statistical_population=population,IQ='z = I − i Q_hardware',DC_treatment=DC,ADC_normalization=ADC,upstream=upstream or [],limitations=notes)
V2=W/'reports/noise_fullrange_v2_20261109';ledger=B/'data/primary_input_sha256.json';sources=json.loads(ledger.read_text());assert len(sources)==260
manifest=R.parent/'analysis-runtime/autoreco/Run2/noise_fullrange_v2_20261109/manifest.json';software=json.loads(manifest.read_text());sourcecfg=dict(manifest=str(manifest),manifest_sha256=sha(manifest),analysis_flags=software['analysis_flags'],frozen_source_sha256=software['source_sha256'],implementation='continuous-run-valid-phase-mode-threads-v3',fs_hz=5e6,IQsign=-1)
upv2=[dict(file=p,sha256=h) for p,h in sources.items()]
with h5py.File(V2/'run00680_noise_v2.h5') as h:
 bandcfg={k:(h['filtered_bands/config/'+k][()].decode() if isinstance(h['filtered_bands/config/'+k][()],bytes) else np.asarray(h['filtered_bands/config/'+k][()]).tolist()) for k in ['continuity','dc_removal','decimation','fs_hz','implementation','input_range_v','iq_sign','offsets_hz','taps','width_hz']}
 dep('V2_RUN680',V2/'run00680_noise_v2.h5',['summary/events','summary/fs_hz','summary/input_range_v','summary/iq_sign','summary/samples','summary/performance/implementation']+[f'dc_removed/modes/{m}/{f}' for m in M for f in ['mean_i_v','mean_q_v','ac_squared_v2','dc_squared_v2','total_squared_v2']], 'primary experimental','v2',sourcecfg,'Run680:1000SPEC;1048576000complex samples/mode','One mean over entire run','Stored ±5V voltage×0.4; power×0.16 once')
 dep('V2_PHASE',V2/'run00680_noise_v2.h5',['arrays/phase_edges_rad']+[f'arrays/global_{m}_{suffix}' for m in M for suffix in ['phase','delta_1','delta_10','delta_100']], 'primary experimental','v2',sourcecfg,'Run680 full valid phases/pairs; lags0.2,2,20µs','Absolute phase, no per-run rotation; increments continuous acrossSPEC','Angles/counts invariant')
 dep('FULL',B/'data/fullband_v2.csv',['run','mode','time_unix','mean_I_ADC_V','mean_Qeff_ADC_V','DC2_ADC_V2','AC2_ADC_V2','total2_ADC_V2','t15_mK','t16_mK','t17_mK'], 'primary experimental export','v2',sourcecfg,'260runs×3modes','One complex mean per run; DC²+AC²=total²','Already physical ADC V/V²; no second factor',upv2,'Temperature columns join verified INPT medians; use TEMP dependency for that measurement.')
 reg['FULL']['upstream_datasets']=[f'dc_removed/modes/{m}/{f}' for m in M for f in ['mean_i_v','mean_q_v','ac_squared_v2','dc_squared_v2','total_squared_v2']]+['summary/events']
 dep('RAW',B/'data/raw_statistics_v2.csv',['run','mode','samples','mean_amplitude_v','amplitude_noise_rms_v']+[f'{pop}_{k}sigma_{field}' for pop in ['local','reference'] for k in [3,5,7] for field in ['threshold_v','samples_above','fraction','episodes']], 'primary experimental export','v2',sourcecfg,'260runs×3modes;all full-run sample counts','RawA=abs(z);centered envelope≠abs(z−mean(z)); continuous episodes','Already physical ADC V; counts/fractions invariant',upv2)
 reg['RAW']['upstream_datasets']=[f'summary/global_statistics/modes/{m}/{f}' for m in M for f in ['mean','m2','n','thresholds_v/local/3','thresholds_v/local/5','thresholds_v/local/7','thresholds_v/reference/3','thresholds_v/reference/5','thresholds_v/reference/7']]+[f'summary/global_statistics/modes/{m}/exceedances/{pop}/{k}/{field}' for m in M for pop in ['local','reference'] for k in [3,5,7] for field in ['samples_above','episodes']]
 dep('ELECTRONIC',B/'data/electronic_bands_v2.csv',['run','mode','band','center_hz','offset_hz','ENBW_hz','power_ADC_V2','AC_power_ADC_V2','RMS_ADC_V','samples','source','dataset'], 'primary experimental export','v2',bandcfg,'260runs×3modes×9bands','Whole-run input complex DC removed; continuous FIR anddecimation acrossSPEC','Already physical ADC V²; savedV²×0.16 once',upv2)
 reg['ELECTRONIC']['upstream_datasets']=[f'filtered_bands/modes/{m}/band_{bi:02d}/complex_moments/{f}' for m in M for bi in range(9) for f in ['n','total_squared_v2','ac_squared_v2']]
 dep('TEMP',B/'data/temperatures_by_run.csv',['run','SPEC_start_unix','SPEC_stop_unix','T15','T16','T17','Mercury4K','Mercury50K','MercuryMagnet'], 'primary cached experimental INPT joined tov2 bounds','originalINPT / verifiedschema',dict(sensor_inventory=str(B/'data/sensor_inventory.json'),SPECbounds=str(B/'data/temperature_SPEC_bounds_provenance.json'),INPTcsv=str(R.parent/'analysis-runtime/autoreco/Run2/thermometers/thermometers_00680_00939.csv'),INPTschema=str(R.parent/'analysis-runtime/autoreco/Run2/thermometers/thermometers_00680_00939.schema.json')),'260run medians;10–11readings/run withinSPECtimestamps','Not applicable','Recorded mK or K; no ADC voltage scaling',notes='Physicalidentity fromoperator;mapping throughODB/INPTindices;4Kplate is only aHEMTstageproxy.')
 dep('SENSORS',B/'data/sensor_inventory.json',['T15','T16','T17','Mercury4K','Mercury50K','MercuryMagnet','T15/quality','T16/quality','T17/quality'], 'primary mapping evidence','originalODB/INPTschema',dict(extraction_code=str(R/'examples/extract_thermometers.py'),raw_check_records=str(W/'diagnostics/frequency_sensor_closure_v47_20261117')),'260runs; targetedBOR/INPTrecords on10alreadyverifiedrawprefixes','Not applicable','DocumentedmK/K; no newcalibration')
 CALC=W/'diagnostics/resonance_campaign_primary_v47_20261117';RES=CALC/'expectations_and_campaign.h5';CFG=dict(centers_IF_hz=1250000,offsets_hz=[-500000,-250000,-100000,0,100000,250000,500000],FIR_taps=2001,window='Kaiser8.6',nominal_width_hz=50000,ENBW_hz=47428.80681855164,decimation=20,output_fs_hz=250000,FFT_samples=16383,fs_hz=5000000,Hann_ENBW_bins=1.5000915639116104)
 dep('RESONANCE',RES,[f'{m}/{f}' for m in M for f in ['power_ADC_V2','centers_IF_hz','electronic_control_relative_error','shared_window_power_relative_error']], 'diagnostic exception: validated archived PSD integration','autorecoFFT v1.1; separatefromnoisev2',CFG,'260full-run archived PSDs; each1000SPEC×64FFTs','Per-chunk I/Q mean removed byFFT; not identicalv2whole-runDCestimator','HistoricalFFTpower×0.16 andHannENBW correction once',notes='Seven documentedIQ+copies losslessly reflected. No empirical distributions/counts derivedfromPSD.')
 verification=B/'data/FFT_coordinate_verification.json';j=json.loads(verification.read_text());reg['RESONANCE']['upstream']=[dict(file=z['archive'],sha256=z['archive_sha256'],executed_IQsign=z['iq_sign']) for z in j['execution_provenance']]
 reg['RESONANCE']['coordinate_verification']=str(verification);reg['RESONANCE']['corrected_copies']=str(W/'diagnostics/frequency_sensor_closure_v47_20261117/corrected_fft_by_run')
 dep('ANALYTIC',RES,[f'{m}/analytic_reference/band_{bi:02d}/{f}' for m in M for bi in range(7) for f in ['output_frequency_hz','output_PSD_ADC_V2_Hz','output_Welch_expected_ADC_V2_Hz','lag_s','g1']], 'approved analytical expectation','approved step6 reference, FIRintegrals',CFG,'Stationary expected7bands×3modes; not MonteCarlo empirical populations','Zero-mean thermal/electronic stochastic components','PhysicalADC V²/Hz',notes='Includes decimationaliases and expectedHannWelchsmoothing; no fit,newresponseor gainchange.')
 dep('RESONANCE_METRICS',CALC/'results.json',['modes','noise_spans','validation','full_band_temperature_correlations','electronic_temperature_correlations','correlations','between_mode_correlations','temperature_sensor_inventory'], 'derived experimental statistics + approved analytical expectations','validatedv47closure',CFG,'260runs plusrun680 analyticcomparison','Definition depends onbank, explicitlyseparated','PhysicalADCunits; no additional scaling')
 PILOT=W/'diagnostics/resonance_bank_pilot_v1_20261117/run00680_resonance.h5'
 dep('PILOT',PILOT,[f'filter_banks/resonance_ROI/modes/{m}/band_{bi:02d}/{f}' for m in M for bi in range(7) for f in ['amplitude_edges_V','amplitude_counts','PSD_frequency_baseband_hz','PSD_total_V2_Hz','selected_lag_s','selected_total_g1']], 'diagnostic exception: empirical resonance-band products','existingresonance_bank_pilot_v1; distinctfromstandardv2',CFG,'Fullrun680amplitude/PSD209.7152s;g1initial5SPEC1.048576s','Rawfilteredoutputamplitudes andtotalcovariance; nooutputmeanremoval','AlreadyphysicalADC2V; nofactor0.4 again')
 S=W/'simulation/presentation_steps1_6_v43';settings=json.loads((S/'metrics.json').read_text())['configuration'];dep('MODEL',S/'metrics.json',['configuration','metrics'], 'approved model parameters/expectedmoments','approvedsteps1–6v43',settings,'Existing52.4288msexamples andanalyticalmoments','Independentzero-mean source powers,exceptcoherentstep1/2','PhysicalADC±2V;Tn3.955K,RF103.4dB,kzandLFfactor0.01 unchanged')
 dep('SHORT',S/'short_examples.h5',['time_s','frequency_hz']+[f'{g}/{f}' for g in ['step1','step2','step3','step4','step5','step6_TM010','step6_TM011','step6_TM012'] for f in ['analog_ADC_V','quantized_ADC_V','PSD_expected_ADC_V2_Hz','ADC_g1']]+expand('diagnostics',['thermal_covariance','receiver_covariance','total_covariance','finite_realization_cross_covariance','power_weighted_g1','step5_minus_step3_analog_ADC_V']), 'approved model storedrealizations','approvedsteps1–6v43',settings,'262144samples/example;5MS/s;52.4288ms','Perstepcoherent/thermal/electronic components keptseparate','AlreadyphysicalADCunits')
 TOY=W/'simulation/toy_ODB_cal5_data2_LF_20261116';dep('TOYFULL',TOY/'toy_full_run680.h5',[f'{m}/{f}' for m in M for f in ['IQ_counts','IQ_edges_v','amplitude_counts','amplitude_edges_v','phase_counts','phase_edges_rad','g1_5SPEC','lag_s']], 'approved historical model realization','archivedfull-runtoy',dict(metrics=str(TOY/'metrics.json'),receiver_Tn_K=3.955,RF_gain_db=103.4,LF_kz_amplitude_factor=.01,ADC_peak_V=2),'1048576000samples/mode209.7152s;selectedg1window','Modelzero-mean exceptfinite-realizationmean','AlreadyphysicalADCunits',notes='Knownthermalpoleat1MHz,notapprovedf0−LO1−LO2; documented,notrerunorcorrected.')
 dep('TOYMETRICS',TOY/'metrics.json',['results','samples_per_mode','duration_s','RF_gain_db','LF_kz_amplitude_factor','receiver_Tn_K'], 'approved model fullrunstatistics','archivedfull-runtoy',dict(source=str(TOY/'toy_full_run680.h5')),'Full-run empiricaltoy counts/moments; existing only','SameasTOYFULL','AlreadyphysicalADCunits',notes='Fieldslistedinclude receiverTnfromMODELifnotstoredinthisJSON;notclaimedasmetadataabsentfield.')
 dep('HW',R/'docs/hardware/README.md',['Hardwareinventoryandoriginaldatasheetcitations'], 'documentary input, no numerical experimental observable','approvedhardwaredocumentation',{},'Notapplicable','Notapplicable','Notapplicable')
 dep('KZ',Path(settings['calibration_reconstruction']),['curves','comparison','calibration_ADC_scale_volts_per_count'], 'approved measuredcalibration input','existingtonecalibrationreconstruction',dict(reference_to_MODEL=settings),'Measuredtonefrequencysweep; no newtransfermodel','Coherenttonecalibration,notthermalempiricaldistribution','Approvedkz/LFnormalizationunchanged')
 # Fine IQ, amplitude pairs and selected-window arrays are explicit exceptions, one file per mode.
 for m in M:
  V40=W/'reports/iq_noise_summary_v40/data'
  dep('FINE_'+m,V40/f'full_iq_data_{m}.npz',['hist','edges','tail','counts','samples'], 'historical diagnostic exception: finerempiricalgrid/fittedthresholds','existingfull-runrawdiagnostic',dict(grid_bins=512,counts_reference=str(V40/'full_iq_counts.json'),software_snapshot='Not archivedinNPZ; sourceprovenanceinv40, exactexecutedSHAunavailable'),'Fullrun6801048576000samples','RawI/signedQ; nomeansubtraction','PhysicalADCunits; TM012oneout-of-grid sample')
  dep('AMP_'+m,V40/f'{m}_amplitude_pair.npz',['edges_adc_v','data_counts','toy_counts'], 'historical diagnostic exception: rendered pairedhistogram','savedv40pairedhistograms',dict(parameter_file=str(V40/'amplitude_comparison_updated.json')),'Originalmatchedfullrunpopulationcounts asretainedinv47','Rawamplitudes; bincenteredCCDFusesexistingfit','PhysicalADCvoltageedges; no newfit or rescaling')
  dep('WINDOW_'+m,TOY/f'comparison/{m}_comparison.npz',['frequency_hz','data_psd_v2_hz','toy_psd_v2_hz','lag_s','data_g1','toy_g1'], 'historical diagnostic exception: selectedwindowPSD/covariance','originalselected-windowdiagnostic; analyticallyvalidatedv47',dict(duration_s=1.048576,fs_hz=5e6,PSDdisplay_bin_hz=244.140625,window='Hann',original_provenance=str(W/'staging/legacy-repository/autoreco/noise_continuous/periodicity_run680')),'Initial5continuousSPEC; notfull-runPSD/covariance','Selectedwindowmeanremoved; normalizedcomplexcovariance','AlreadyphysicalADC V²/Hz; no extra0.4')
 dep('RAYLEIGHFIT',W/'reports/iq_noise_summary_v40/data/amplitude_comparison_updated.json',[f'{m}/data/{k}' for m in M for k in ['sigma_v','mean_v','std_v','RMS_v']], 'historical diagnostic exception: existing savedfitresults','existingbinnedRayleighfits; no newfit',{},'Fullrun680histograms','Rawamplitude,notACmarginal','PhysicalADCunits')
 dep('FITTEDCOUNTS',W/'reports/iq_noise_summary_v40/data/full_iq_counts.json',[f'data_{m}/{k}' for m in M for k in ['above_3_5_7','sigma_v','samples','outside_plot']], 'historical diagnostic exception: empiricalcounts atfittedRayleighthresholds','existingfull-runrawdiagnostic',{},'1048576000samplecounts; notindependenttrials','Rawamplitude; thresholdsdifferfromlongtermlocal/fixedones','PhysicalADCunits; thresholdsnotchanged')
 dep('TIMES',TOY/'comparison/comparison.json',[f'modes/{m}/{k}' for m in M for k in ['data_upper_fit','toy_upper_fit','modulus_fits']], 'historical diagnostic exception: retainedphenomenologicalfits','existingselected-upper-maxima fits,noneexecutedinv47.1',dict(selected_peak_interval_us=[.3,4],fit_causality='Phenomenologicalnotintrinsiccavitydecay'),'Selected1.048576swindows','Signedcomplexcovariance,normalizedafterwindowmeanremoval','Dimensionlessg1;timeµs')
 dep('V2_SHAPES',B/'data/normalized_amplitude_moments_v2.csv',['run','mode','CV','mean_amplitude_ADC_V','std_amplitude_ADC_V','mean_over_raw_RMS','amplitude_second_moment_over_mean_squared'], 'primary v2 derivedmoments','v2',sourcecfg,'260runs×3modes','Rawamplitude moments; notACamplitude','PhysicalADCunitsandinvariantratios',upv2)
 dep('FFT_VERIFY',B/'data/FFT_coordinate_verification.json',['status','runs_audited','job_iq_sign_counts','corrected_runs','raw_checks','execution_provenance'], 'validated archived pipeline provenance','FFTsoftwarev1.1; loggedexecutedIQsign;exactsourceSHAunavailable',CFG,'260archives;8SPECfrom7suspectsand3controls alreadychecked','FFTper-chunkDCremoved','RecordedhistoricalADC5V; correctedpoweronce')
 # Validation records for newly plotted curves and the estimator-difference qualifier.
 dep('FIGCHECK',O/'validation.json',['numeric_checks/slide46','numeric_checks/slide48'], 'v47.1 numerical reproduction evidence','v47.1table-onlyrevision',{},'All260runs×3modes; no rawprocessing','Definitionsunchanged','No additional conversion beyondprimaryCSV')
# Explicit enumeration: composite slides deliberately list independent sources for each observable.
A={'model_parameters':['MODEL','KZ'],'short_realizations':['SHORT']};fine=['FINE_'+m for m in M];amp=['AMP_'+m for m in M];windows=['WINDOW_'+m for m in M]
S={
1:A,2:{'hardware_inventory':['HW']},3:{'physical_parameters_and_normalization':['MODEL','KZ']},4:{'physical_source_and_response':['MODEL','KZ','SHORT']},
5:{'tone_example':['MODEL','SHORT']},6:{'filtered_tone_example':['MODEL','KZ','SHORT']},7:{'electronic_noise_example':['MODEL','SHORT']},8:{'thermal_noise_example':['MODEL','SHORT']},9:{'combined_source_example':['MODEL','SHORT']},10:{'source_covariances_and_residual':['MODEL','SHORT']},
11:{'TM010_complete_short_model':['MODEL','SHORT']},12:{'TM011_complete_short_model':['MODEL','SHORT']},13:{'TM012_complete_short_model':['MODEL','SHORT']},14:{'expected_reference_moments':['MODEL','SHORT']},
15:{'run680_samples_and_ADC':['V2_RUN680'],'run680_temperature':['TEMP','SENSORS'],'cavity_and_LO_parameters':['MODEL']},
16:{'data_raw_and_AC_RMS':['V2_RUN680'],'data_Rayleigh_scale':['RAYLEIGHFIT'],'toy_expected_RMS':['MODEL'],'toy_fullrun_moments':['TOYMETRICS']},
17:{'data_IQ_and_quadrature_marginals':fine,'toy_IQ_and_marginals':['TOYFULL']},
18:{'paired_raw_amplitude_histograms':amp,'saved_Rayleigh_scales':['RAYLEIGHFIT','TOYMETRICS'],'toy_fullrun_amplitudes':['TOYFULL']},
19:{'absolute_data_phase_and_increments':['V2_PHASE'],'toy_absolute_phase':['TOYFULL']},
20:{'data_empirical_fittedthreshold_counts':['FITTEDCOUNTS','RAYLEIGHFIT'],'toy_empirical_counts':['TOYMETRICS'],'Rayleigh_expectation':['MODEL']},
21:{'selected_PSD_data_and_toy':windows},22:{'selected_g1_data_and_toy':windows},23:{'retained_selectedwindow_characteristic_times':['TIMES'],'intrinsic_cavity_time':['MODEL']},
24:{'data_RMS_and_DC':['V2_RUN680'],'amplitude_fit':['RAYLEIGHFIT'],'toy_expected_and_fullrun':['MODEL','TOYMETRICS'],'selected_PSD_g1_discrepancies':windows+['TIMES']},
25:{'data_seven_band_moments':['PILOT','RESONANCE_METRICS'],'toy_thermal_electronic_total':['ANALYTIC','MODEL','RESONANCE_METRICS']},
26:{'data_fullband_AC_RMS':['V2_RUN680'],'toy_fullband_RMS':['MODEL'],'data_central_resonance_RMS':['PILOT','RESONANCE_METRICS'],'toy_resonance_total_and_thermal':['ANALYTIC','RESONANCE_METRICS']},
27:{'empirical_fullrun_band_amplitudes':['PILOT'],'analytical_band_Rayleigh_CDF':['ANALYTIC','RESONANCE_METRICS']},
28:{'empirical_fullrun_filtered_PSD':['PILOT'],'empirical_initial_window_g1':['PILOT'],'expected_PSD_and_g1':['ANALYTIC','RESONANCE_METRICS']},
29:{'empirical_fullrun_band_ratios':['PILOT','RESONANCE_METRICS'],'analytical_band_ratios':['ANALYTIC','RESONANCE_METRICS']},
30:{'data_total_and_AC_RMS':['FULL'],'measured_cryogenic_temperatures':['TEMP','SENSORS']},
31:{'fullband_AC_power':['FULL'],'measured_cryogenic_temperatures':['TEMP','SENSORS']},
32:{'fullband_AC_power':['FULL'],'additional_stage_temperatures':['TEMP','SENSORS']},
33:{'fullband_AC_power':['FULL'],'sensor_values_and_identity':['TEMP','SENSORS'],'direct_firstdifference_correlation_coefficients':['RESONANCE_METRICS']},
34:{'intermode_runlevel_power_correlations':['FULL']},35:{'nominal_resonance_coordinates':['RESONANCE','FFT_VERIFY'],'electronic_coordinates_and_FIR':['ELECTRONIC'],'illustrative_cavity_Lorentzians':['MODEL']},
36:{'run680_electronic_absolute_baseline':['ELECTRONIC']},37:{'electronic_relative_RMS':['ELECTRONIC']},38:{'electronic_central_side_symmetric_ratios':['ELECTRONIC']},
39:{'archived_PSD_electronic_power_comparison':['RESONANCE','ELECTRONIC','FFT_VERIFY','RESONANCE_METRICS']},
40:{'resonance_absolute_RMS':['RESONANCE']},41:{'resonance_relative_RMS':['RESONANCE']},42:{'resonance_band_power':['RESONANCE'],'measured_temperatures':['TEMP','SENSORS']},43:{'intermode_runlevel_resonance_power':['RESONANCE']},44:{'resonance_central_side_symmetric_ratios':['RESONANCE']},
45:{'electronic_band_stability':['ELECTRONIC'],'resonance_band_stability':['RESONANCE'],'fullband_AC_level':['FULL']},
46:{'complex_mean_magnitude_phase':['FULL'],'DC_AC_total_decomposition':['FULL'],'primary_reproduction_check':['FIGCHECK']},
47:{'raw_amplitude_CV':['RAW','V2_SHAPES']},
48:{'empirical_local_fixed_probabilities':['RAW'],'unchanged_stored_local_fixed_thresholds':['RAW'],'momentbased_Rayleigh_expectations':['RAW'],'primary_reproduction_check':['FIGCHECK']},
49:{'fullband_RMS_drift_and_mode_associations':['FULL'],'electronic_shape_and_level':['ELECTRONIC'],'resonance_shape_and_level':['RESONANCE'],'temperature_associations':['TEMP','SENSORS'],'normalized_moments_and_threshold_sensitivity':['RAW','V2_SHAPES'],'residual_PSD_FIR_discrepancy':['RESONANCE_METRICS','FFT_VERIFY']},
50:{'fullband_power_clock_residuals':['FULL'],'temperature_clock_residuals':['TEMP','SENSORS']},51:{'intermode_runlevel_clock_residuals':['FULL']},52:{'descriptive_electronic_commontrend_and_residualshape':['ELECTRONIC']},53:{'physical_sensor_identity_and_observation_coverage':['SENSORS','TEMP']}}
assert set(S)==set(range(1,54));slides=json.loads((O/'slide_model.json').read_text());result=[]
# Per-observable field selection is explicit, not inferred from title words.
consumed={
 (30,'FULL'):['run','mode','time_unix','total2_ADC_V2','AC2_ADC_V2'],
 (31,'FULL'):['run','mode','time_unix','AC2_ADC_V2'],
 (32,'FULL'):['run','mode','time_unix','AC2_ADC_V2'],
 (33,'FULL'):['run','mode','time_unix','AC2_ADC_V2'],
 (34,'FULL'):['run','mode','time_unix','AC2_ADC_V2'],
 (45,'FULL'):['run','mode','time_unix','AC2_ADC_V2'],
 (46,'FULL'):['run','mode','time_unix','mean_I_ADC_V','mean_Qeff_ADC_V','DC2_ADC_V2','AC2_ADC_V2','total2_ADC_V2'],
 (49,'FULL'):['run','mode','time_unix','AC2_ADC_V2'],
 (50,'FULL'):['run','mode','time_unix','AC2_ADC_V2'],
 (51,'FULL'):['run','mode','time_unix','AC2_ADC_V2'],
 (47,'RAW'):['run','mode','mean_amplitude_v','amplitude_noise_rms_v']}
for n,components in S.items():
 for obs,deps in components.items():
  for key in deps:
   x=dict(reg[key]);x['datasets_or_columns']=consumed.get((n,key),x['datasets_or_columns'])
   if n==48 and key=='RAW':
    fields=['run','mode']
    if obs=='empirical_local_fixed_probabilities':fields += [f'{pop}_{k}sigma_fraction' for pop in ['local','reference'] for k in [3,5,7]]
    elif obs=='unchanged_stored_local_fixed_thresholds':fields += [f'{pop}_{k}sigma_threshold_v' for pop in ['local','reference'] for k in [3,5,7]]
    else:fields += ['mean_amplitude_v','amplitude_noise_rms_v']+[f'{pop}_{k}sigma_threshold_v' for pop in ['local','reference'] for k in [3,5,7]]
    x['datasets_or_columns']=fields
   result.append(dict(version='v47.1',slide=n,title=slides[n-1]['title'],observable=obs,dependency_id=key,**{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in x.items()}))
# Resolve available artifacts/fields; do not imply unavailable software snapshots exist.
for key,x in reg.items():
 p=Path(x['file'])
 if p.suffix=='.h5':
  with h5py.File(p) as h:
   for ds in x['datasets_or_columns']:assert ds in h,(key,ds)
 elif p.suffix=='.npz':
  with np.load(p) as h:assert all(k in h.files for k in x['datasets_or_columns'])
 elif p.suffix=='.json':
  js=json.loads(p.read_text())
  for field in x['datasets_or_columns']:
   node=js
   for part in field.split('/'):assert part in node,(key,field,part);node=node[part]
 elif p.suffix=='.csv':
  with p.open() as f:fields=next(csv.reader(f));assert all(k in fields for k in x['datasets_or_columns']),(key,fields)
with (O/'slide_observable_provenance.csv').open('w') as f:
 # Registry entries may add explicit upstream-dataset fields; use stable union.
 fields=list(dict.fromkeys(k for row in result for k in row));wr=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');wr.writeheader();wr.writerows(result)
(O/'dependency_registry.json').write_text(json.dumps(reg,indent=2,ensure_ascii=False));(O/'slide_dependency_map.json').write_text(json.dumps(S,indent=2));print('Explicit provenance:',len(result),'dependency rows;',len(reg),'named input definitions;53slides',flush=True)
