"""Validate v47 and write numerical, per-observable and per-slide provenance reports."""
from pathlib import Path
import json,csv,hashlib,shutil,sys
import numpy as np,h5py
from scipy.stats import spearmanr
R=Path('/home/mazzitel/HFGW');W=R/'analysis-work/Run2';O=W/'reports/iq_noise_summary_v47';A=W/'diagnostics/v47_primary_audit_20261117';C=W/'diagnostics/resonance_campaign_primary_v47_20261117';V=W/'diagnostics/frequency_sensor_closure_v47_20261117';P=W/'reports/noise_fullrange_v2_20261109';D=O/'data';D.mkdir(exist_ok=True)
def read(p):
 with open(p) as f:return list(csv.DictReader(f))
def write(p,rows):
 with open(p,'w') as f:
  z=csv.DictWriter(f,fieldnames=list(rows[0]));z.writeheader();z.writerows(rows)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=json.loads((C/'results.json').read_text());v=json.loads((V/'verification.json').read_text());assert v['status']=='validated' and v['runs_audited']==260
sys.path.insert(0,str(R/'analysis/examples'));from verify_fft_coordinates_v47 import reflect_shifted
psdchecks=[]
for run in v['corrected_runs']:
 src=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/fft_by_run')/f'run{run:05d}.npz';dst=V/'corrected_fft_by_run'/src.name
 with np.load(src) as old,np.load(dst) as new:
  for mode in range(3):
   x=old[f'fft_amp_mode{mode}_SPECs'];y=new[f'fft_amp_mode{mode}_SPECs'];assert len(x)==16383 and np.array_equal(reflect_shifted(x),y)
   psdchecks.append(dict(run=run,mode='TM01'+str(mode),source=str(src),source_sha256=sha(src),corrected=str(dst),corrected_sha256=sha(dst),exact_reindex=True,power_preserved=bool(np.sum(x)==np.sum(y) or np.isclose(np.sum(x),np.sum(y),rtol=1e-14))))
write(D/'seven_PSD_reindex_validation.csv',psdchecks)
full=read(A/'fullband_v2.csv');raw=read(A/'raw_statistics_v2.csv');band=read(A/'electronic_bands_v2.csv');temp=read(C/'temperatures_by_run.csv');modes=['TM010','TM011','TM012']
# Independently verify inherited DC and moments against primary v2; no fit and no raw read.
old={(int(x['run']),x['mode']):x for x in read(W/'simulation/step7/dc_longterm_diagnostic/longterm.csv')};dcverify=[]
for row in full:
 for key in ('AC2_ADC_V2','DC2_ADC_V2','total2_ADC_V2','mean_I_ADC_V','mean_Qeff_ADC_V','t15_mK','t16_mK','t17_mK'):
  x=float(row[key]);y=float(old[(int(row['run']),row['mode'])][key]);ok=np.isclose(x,y,rtol=2e-12,atol=1e-16);dcverify.append(dict(run=row['run'],mode=row['mode'],field=key,abs_error=abs(x-y),passed=bool(ok)))
assert all(x['passed'] for x in dcverify);write(D/'legacy_DC_vs_primary_v2.csv',dcverify)
# Longterm dimensionless moments, phase increments and direct Pearson/Spearman controls.
shapes=[];increments=[];cor=[];spans={}
for mode in modes:
 f=[x for x in full if x['mode']==mode];a=[x for x in raw if x['mode']==mode];t=np.array([float(x['time_unix']) for x in f]);power=np.array([float(x['AC2_ADC_V2']) for x in f]);X=np.column_stack([np.ones(260),(t-t.mean())/t.std()])
 for x,y in zip(f,a):
  mu=float(y['mean_amplitude_v']);sd=float(y['amplitude_noise_rms_v']);total=float(x['total2_ADC_V2']);shapes.append(dict(run=int(x['run']),mode=mode,mean_amplitude_ADC_V=mu,std_amplitude_ADC_V=sd,CV=sd/mu,mean_over_raw_RMS=mu/np.sqrt(total),amplitude_second_moment_over_mean_squared=total/mu**2,Rayleigh_CV=float(np.sqrt((4-np.pi)/np.pi))))
 spans[mode]=dict(fullband_RMS_span_percent=float(100*(np.sqrt(power.max()/power.min())-1)),**r['noise_spans'][mode])
 for sensor in [k for k in temp[0] if k not in ('run','time_unix')]:
  try:s=np.array([float(x[sensor]) for x in temp])
  except ValueError:continue
  good=np.isfinite(s)&(s>0)&np.isfinite(power)
  if good.sum()<3 or np.ptp(s[good])==0:continue
  def pair(x,y):return dict(Pearson=float(np.corrcoef(x,y)[0,1]),Spearman=float(spearmanr(x,y).statistic))
  s=s[good];p=power[good];clock=X[good];sp=s-clock@np.linalg.lstsq(clock,s,rcond=None)[0];pp=p-clock@np.linalg.lstsq(clock,p,rcond=None)[0]
  for kind,values in [('raw',pair(s,p)),('linear_clock_control',pair(sp,pp)),('first_differences',pair(np.diff(s),np.diff(p)))]:cor.append(dict(mode=mode,sensor=sensor,diagnostic=kind,paired_n=len(s) if kind!='first_differences' else len(s)-1,**values))
with h5py.File(A/'primary_v2_distributions.h5') as h:
 for run in range(680,940):
  for mode in modes:
   g=h[f'run{run:05d}/global_statistics/{mode}/delta_circular']
   for lag in g:
    n=int(g[lag+'/pairs'][()]);c=float(g[lag+'/cos_sum'][()]);s=float(g[lag+'/sin_sum'][()]);increments.append(dict(run=run,mode=mode,lag_samples=int(lag),lag_s=int(lag)/5e6,pairs=n,circular_resultant=np.hypot(c,s)/n,mean_increment_rad=np.arctan2(s,c),source_dataset=f'summary/global_statistics/modes/{mode}/delta_circular/{lag}'))
write(D/'normalized_amplitude_moments_v2.csv',shapes);write(D/'phase_increment_moments_v2.csv',increments);write(D/'fullband_temperature_correlations_v2.csv',cor)
# Copy compact primary tables and evidence. Large empirical arrays stay in external audit directory.
for name in ['fullband_v2.csv','raw_statistics_v2.csv','electronic_bands_v2.csv','legacy_table_comparison.csv','consolidation_validation.json','primary_input_sha256.json','v1_v2_dataset_comparison.json','inventory_status.json']:
 shutil.copy2(A/name,D/name)
for name in ['sensor_inventory.json','temperatures_by_run.csv','temperature_SPEC_bounds_provenance.json','campaign_band_powers.csv']:
 shutil.copy2(C/name,D/name)
shutil.copy2(V/'verification.json',D/'FFT_coordinate_verification.json')
# Explicit observable families: definitions, availability and estimator scope.
families=[
 ('complex_DC_AC','dc_removed/modes/MODE/{mean_i_v,mean_q_v,dc_squared_v2,ac_squared_v2,total_squared_v2}','v2','One whole-run complex mean; DC²+AC²=total²; no perSPEC reset','1000SPEC,1048576000complexsamples/mode/run','voltage×0.4; squared×0.16 once'),
 ('amplitude_histogram','arrays/global_MODE_amp; arrays/amplitude_edges_v','v2','A_raw=abs(z); empirical65536bins; no synthetic distribution','Full-run empirical counts','Edges×0.4; counts unchanged'),
 ('centered_envelope','modes/MODE/noise_counts; noise_edges_v','v2','A_centered=abs(z)-mean(abs(z)); NOT abs(z-mean(z))','Full-run empirical counts','Edges×0.4'),
 ('DC_subtracted_amplitude','Not stored as full empirical marginal in standard v2','exception','Only AC RMS available; do not reconstruct an empirical abs(z-mean(z)) histogram from moments','Unavailable full-band empirical marginal','No invented histogram'),
 ('amplitude_moments_CV','summary/global_statistics/modes/MODE/{n,mean,m2}','v2','std(A)=sqrt(m2/n),CV=std/mean; Rayleighsigma distinct','Full-run raw amplitudes','Mean/std×0.4; CV invariant'),
 ('phase','arrays/global_MODE_phase; arrays/phase_edges_rad','v2','Absolute atan2(-Qhardware,I); zero amplitudes excluded','Full-run valid phase samples','Radians invariant'),
 ('phase_increment','arrays/global_MODE_delta_LAG; summary/global_statistics/modes/MODE/delta_circular','v2','Circular increments; continuity acrossSPEC; invalidzero pairs excluded','Valid pairs; lags1,10,100','Radians invariant'),
 ('IQ','arrays/global_MODE_iq; arrays/iq_edges_v','v2','256×256 empirical absoluteI/signedQ grid','Full-run allcomplexsamples','Edges×0.4; counts unchanged'),
 ('threshold_counts','summary/global_statistics/modes/MODE/{exceedances,thresholds_v}','v2','LocalmeanA+kstdA versus saved fixedpilot; continuous episode boundaries','Full-run k3,5,7; samples are correlated','Threshold/peak×0.4; counts/fractions invariant'),
 ('electronic_bands','filtered_bands/modes/MODE/band_NN/{complex_moments,events}','v2','0±100±250±500±1000kHz;50kHzFIR;ENBW47428.8068Hz;whole-runinputDCremoved','260runs×3×9; continuous FIR acrossSPEC','SavedV²×0.16 once'),
 ('resonance_bands','resonance_campaign_primary_v47_20261117/expectations_and_campaign.h5','autorecoFFT + BOR + validatednewdiagnostic','Actual2001tapFIR|H|² integration; nominal+1.250MHz and0±100±250±500kHz','All260validatedfull-runPSDs; not empirical amplitude/phase/tails','RawFFTstored5V→2V×0.16; HannENBW corrected once'),
 ('resonance_empirical_run680','resonance_bank_pilot_v1_20261117/run00680_resonance.h5','newdiagnostic','Existing full-run empirical filtered amplitudes/PSD;g1 selected first5SPEC','Run6801000SPEC amplitudes;g1first5SPEC','PhysicalADC2V,already corrected; no×0.4 again'),
 ('temperature','thermometers CSV/schema + v2SPECtimestampbounds; sensor_inventory.json','cachedINPT + v2 + targetedBORchecks','Run medians insideSPECbounds; no interpolation','260runs;10–11observations/run/sensor','DocumentedmK/K;operator17/18/19 tied to names,not inferred order'),
 ('selected_PSD_g1','toy_ODB_cal5_data2_LF_20261116/comparison/*_comparison.npz','validatednewdiagnostic exception','Selected1.048576s contiguous run680 window; I-iQ;HannPSD and complexcovariance','5SPEC data/toy; not full-run or260runPSD','SavedphysicalADCunits; do not rescale again'),
 ('fullrun_fine_IQ_and_fitted_threshold_counts','iq_noise_summary_v40/data/full_iq_data_MODE.npz;full_iq_counts.json','validatednewdiagnostic exception','512×512 rawIQhist and empirical counts at existing fitted-Rayleigh thresholds, unavailable on256grid/v2fixedthresholds','Complete1048576000samplepopulation; existing only, no newfit','SavedphysicalADCunits; TM012onegridoutlier retained'),
 ('approved_toy','presentation_steps1_6_v43; toy_ODB_cal5_data2_LF_20261116','approvedmodel','Tn3.955K,RFgain,kzunchanged; thermal/electronicindependentpower terms','Existingshort/full-runrealizations plus analytic expectations','No newgain,Tn,hardware fit or full-runsimulation')]
familyrows=[dict(observable=x[0],numeric_dataset=x[1],reconstruction=x[2],estimator_DC_continuity=x[3],population=x[4],ADC_normalization=x[5],IQ='z=I-iQhardware') for x in families];write(D/'observable_provenance.csv',familyrows)
# Complete slide census, including every v46 slide and every v47 slide.
slide_records=[]
for version in ['v46','v47']:
 model=json.loads((W/f'reports/iq_noise_summary_{version}/slide_model.json').read_text())
 for i,s in enumerate(model):
  title=s['title'];low=(title+' '+s.get('source','')).lower();fams=[]
  for terms,fam in [(['amplitude','rayleigh','shape'],'amplitude_moments_CV'),(['phase','increment'],'phase_increment'),(['quadrature','constellation','iq '],'IQ'),(['threshold','tails'],'threshold_counts'),(['temperature','sensor','cryogenic'],'temperature'),(['electronic bands'],'electronic_bands'),(['resonance'],'resonance_bands'),(['dc ','noise level','stability','correlation','normalization'],'complex_DC_AC')]:
   if any(t in low for t in terms):fams.append(fam)
  if i<14:fams=['approved_toy']
  if 'power spectral density' in low or 'complex autocorrelation'==title.lower() or 'characteristic times' in low:fams=['selected_PSD_g1']
  if 'quadrature distributions' in low:fams=['fullrun_fine_IQ_and_fitted_threshold_counts','IQ']
  if 'amplitude tails' in low:fams=['fullrun_fine_IQ_and_fitted_threshold_counts','threshold_counts']
  if (version=='v46' and 25<=i+1<=28) or (version=='v47' and 25<=i+1<=29):fams=['resonance_empirical_run680','approved_toy']
  if not fams:fams=['approved_toy'] if i<14 else ['complex_DC_AC']
  assets=[it['path'] for it in s['items'] if it['kind']=='image'];notes=s.get('notes','')
  slide_records.append(dict(version=version,slide=i+1,title=title,observable_families=';'.join(fams),actual_image_files=';'.join(assets),original_source_statement=s.get('source',''),original_estimator_notes=notes,numeric_sources=';'.join(x[1] for x in families if x[0] in fams),scientific_primary='Primaryv2; exceptions explicitly specified' if version=='v47' else 'Historicalv46: source statement retained; superseded wherev2available',software='v2:continuous-run-valid-phase-mode-threads-v3; per-runSHAledger; FFTv1.1 executedIQparameter audited',IQ='I-iQhardware; seven archivedIQ+ copies reflected by exact proven identity',ADC='Physical2V; stored5V factors0.4/0.16 once unless productalreadyphysical',population='See per-observable scope and original notes; never infer empirical distribution fromPSD'))
write(O/'slide_observable_provenance.csv',slide_records)
# Numeric traces for inherited presentation versions and exact file-level inputs.
inherited=[]
for version in ['v17','v37','v40','v44','v45']:
 p=W/f'reports/iq_noise_summary_{version}';files=[x for x in p.rglob('*') if x.is_file() and x.suffix in ('.json','.csv','.npz','.h5') and 'previous_revision' not in str(x)]
 for f in files:
  inherited.append(dict(version=version,path=str(f),sha256=sha(f),role='Historicalintermediate;retainedimmutable. v47primarydatareplacedbyv2; highresolution/selectedwindowexceptionsdocumented.'))
write(D/'inherited_intermediate_inventory.csv',inherited)
# Exact numerical summary and residual limitations.
v1=json.loads((A/'v1_v2_dataset_comparison.json').read_text());legacy=read(A/'legacy_table_comparison.csv');different=[x for x in legacy if x['passed']=='False'];short=json.loads((W/'simulation/presentation_steps1_6_v43/metrics.json').read_text());ratios=[]
for mode in modes:
 x=next(z for z in full if int(z['run'])==680 and z['mode']==mode);rr=r['modes'][mode];ratios.append(dict(mode=mode,fullband_data_over_toy_RMS=np.sqrt(float(x['AC2_ADC_V2']))/short['metrics'][mode]['total_RMS_expected_ADC_V'],resonance_data_over_toy_RMS=rr['data_over_toy_RMS'][3],thermal_RMS_ADC_uV=rr['thermal_RMS_ADC_V'][3]*1e6,thermal_power_ppm=rr['thermal_power_fraction'][3]*1e6))
write(D/'absolute_fullband_resonance_comparison.csv',ratios)
report=dict(primary_v2_runs=260,fullband_rows=len(full),electronic_band_rows=len(band),resonance_band_rows=len(read(C/'campaign_band_powers.csv')),maximum_DC_identity_relative_error=json.loads((A/'inventory_status.json').read_text())['max_identity_error'],legacy_DC_checks=len(dcverify),legacy_DC_all_passed=True,v1_hdf5_compared_runs=v1['compared_runs'],missing_v1_hdf5_runs=v1['missing_v1_runs'],v1_statistical_dataset_mismatch_cases=sum(x['different'] for x in v1['datasets'].values()),legacy_raw_checks=len(legacy),legacy_differences=len(different),legacy_difference_observables=sorted(set(x['observable'] for x in different)),PSD_runs=260,PSD_corrected_runs=v['corrected_runs'],PSD_reindex_mode_checks=len(psdchecks),PSD_raw_validation_reused=True,PSD_raw_prefix_SPEC_per_run=8,PSD_raw_control_runs=v['controls'],PSD_vs_eight_electronic_bands_max_percent={m:r['validation'][m]['all_nonzero_electronic_max_abs_power_error_percent'] for m in modes},temperature_mapping=r['temperature_sensor_inventory'],noise_spans=spans,absolute_comparison=ratios,new_raw_reads_this_consolidation=0,new_fullrun_reconstructions=0,new_simulations=0,new_physical_fits=0,PartIV=0,limitations=['Only94 originalv1HDF5available locally/on connected mount; remaining166 not presumed equivalent. HistoricalfullcampaignCSVcomparedfor35880values.','V1/V2phaseincrementandepisodecountsarenotassumedidentical;v2isprimary.','Fine512IQand fittedthresholdcounts and selectedPSD/g1arevalidatedexistingdiagnosticexceptions; standardv2doesnotstorethoseestimators.','Nofullbandempiricalabs(z-mean(z))histogramisavailable; onlyACmoments,notinventeddistributions.','Archivedfullruntoythermalpoleat1MHz differsfromapprovedphysicalIFcoordinates; retaineddocumented,notrerun.','4KplateisHEMT-stageproxy,notdevicejunctiontemperature; sensorcalibrationprecisionnotremeasured.','Correlationsandclockcontrolsaredescriptive,notcausal; no gain/noisetemperaturedecomposition.'])
(O/'validation_complete.json').write_text(json.dumps(report,indent=2));(D/'noise_spans.json').write_text(json.dumps(spans,indent=2))
# Presentation structure/readability checks.
sys.path[:0]=['/tmp/v18-python-deps','/tmp/v46-pdf-deps'];from pptx import Presentation;from pypdf import PdfReader
slides=json.loads((O/'slide_model.json').read_text());prs=Presentation(O/'iq_noise_summary_v47.pptx');pdf=PdfReader(O/'iq_noise_summary_v47.pdf');assert len(slides)==len(prs.slides)==len(pdf.pages);assert len(slide_records)==49+len(slides)
for s in slides:
 for it in s['items']:
  assert it['x']>=0 and it['y']>=0 and it['x']+it['w']<=13.35 and it['y']+it['h']<=7.51
assert not any('Part IV' in s['title'] for s in slides)
report['presentation_pages']=len(slides);report['PDF_PPTX_page_counts_match']=True;(O/'validation_complete.json').write_text(json.dumps(report,indent=2))
print('Validated',len(slides),'slides;',len(full),'fullband rows;',len(band),'electronic rows;',report['resonance_band_rows'],'resonance rows',flush=True)
