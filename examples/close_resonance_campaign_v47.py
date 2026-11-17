"""Apply provenance-validated PSD coordinates and identify cached thermometers.

Updates new copies only. No raw reconstruction, physical fit, gain change or toy
modification. New temperature medians use original observations in SPEC bounds.
"""
from pathlib import Path
import argparse,csv,json,shutil
import h5py,numpy as np
from scipy.signal import firwin
from resonance_reference_and_campaign import WORK,FS,MODES,OFFSETS,ELECTRONIC,sha,read_rows,response_power,correlations

RUNTIME=WORK.parent.parent/'analysis-runtime/autoreco/Run2'
BASE=WORK/'diagnostics/resonance_reference_campaign_v5_20261117'
VERIFY=WORK/'diagnostics/frequency_sensor_closure_v47_20261117'
TEMPS=RUNTIME/'thermometers/thermometers_00680_00939.csv'
# Physical identities are operator-supplied; bank labels/indices are checked below.
SENSORS={
 'T15':('Temp_AVS',15,'T4','RF cavity — Dale1.5K','mK',17),
 'T16':('Temp_AVS',16,'T5','Mixing Chamber — CMN143','mK',18),
 'T17':('Temp_AVS',17,'T6','Mixing Chamber — CMN130','mK',19),
 'Mercury4K':('Temp_Mercury',4,'Diode_4K_T K','4 K plate — diode (HEMT-stage proxy)','K',None),
 'Mercury50K':('Temp_Mercury',2,'Pt_50K_T K','50 K plate — Pt','K',None),
 'MercuryMagnet':('Temp_Mercury',12,'RuO2_Mag_T K','Magnet — RuO₂ (4 K stage)','K',None),
 'AVSStill':('Temp_AVS',11,'T0','Still','mK',None),
 'AVS50mK':('Temp_AVS',12,'T1','50 mK plate','mK',None),
 'AVSTWPA':('Temp_AVS',13,'T2','TWPA — TT2107','mK',None),
 'AVSNoiseSource':('Temp_AVS',14,'T3','Noise source — TT1922','mK',None),
 'MercuryMCdiode':('Temp_Mercury',8,'Diode_MC_T K','MC diode (quality screening required)','K',None),
 'MercuryHeatSwitch':('Temp_Mercury',10,'Pt_HeatSwitch_T K','Heat-switch Pt','K',None),
}

def summarize_coeff(x,y,t):
    keep=np.isfinite(x)&np.isfinite(y)&np.isfinite(t)
    if keep.sum()<3 or np.ptp(x[keep])==0 or np.ptp(y[keep])==0:return {'n':int(keep.sum()),'status':'unavailable or constant'}
    return {'n':int(keep.sum()),'status':'descriptive association, no causal inference',**correlations(x[keep],y[keep],t[keep])}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError(a.output)
 a.output.mkdir(parents=True)
 r=json.loads((BASE/'results.json').read_text());verification=json.loads((VERIFY/'verification.json').read_text());assert verification['status']=='validated' and verification['runs_audited']==260
 ledger=r['input_sha256'].copy()
 for path in [BASE/'results.json',BASE/'expectations_and_campaign.h5',VERIFY/'verification.json',TEMPS,TEMPS.with_suffix('.schema.json'),Path(__file__).resolve(),Path(__file__).with_name('resonance_reference_and_campaign.py'),Path(__file__).with_name('extract_thermometers.py'),Path(__file__).with_name('plot_thermometers_history.py'),Path(__file__).with_name('report_noise_temperature.py')]:ledger[str(path)]=sha(path)
 metadata=json.loads(TEMPS.with_suffix('.schema.json').read_text());schemas=metadata['schemas'];columns={};sensorinfo={}
 for identifier,schema in schemas.items():
  columns[identifier]={}
  for alias,(equipment,index,label,physical,unit,operator) in SENSORS.items():
   if schema['equipment']!=equipment:continue
   channel=next(c for c in schema['channels'] if c['index']==index)
   assert channel['odb_name']==label and channel['unit']==unit and schema['documented_layout_length_matches']
   columns[identifier][alias]=channel['column']
   sensorinfo[alias]={'equipment':equipment,'bank':'INPT','zero_based_bank_index':index,'ODB_name':label,'physical_name':physical,'unit':unit,'operator_sensor_number':operator,'unit_source':channel['unit_source'],'schema_id':identifier,'ODB_event_id':schema['event_id']}
 # Check original BOR names, affine conversions and bank payload length on all ten raw controls.
 for run in verification['corrected_runs']+verification['controls']:
  path=VERIFY/f'run{run:05d}_raw_check.json';raw=json.loads(path.read_text());ledger[str(path)]=sha(path)
  for alias,info in sensorinfo.items():
   eq=raw['temperature_ODB'][info['equipment']];settings=eq['Settings'];ix=info['zero_based_bank_index']
   assert settings['Names Input'][ix]==info['ODB_name']
   assert settings['Input Factor'][ix]==1 and settings['Input Offset'][ix]==0 and not settings['Input Formula'][ix]
   assert len(eq['BOR_Input']) in (13,25)
 observations={run:{s:[] for s in SENSORS} for run in range(680,940)}
 with open(TEMPS) as stream:
  for row in csv.DictReader(stream):
   run=int(row['run'])
   if run not in observations or row['source_status']!='complete':continue
   for alias,column in columns.get(row['schema_id'],{}).items():
    value=float(row[column]) if row[column] else np.nan
    observations[run][alias].append((float(row['time_unix']),value))
 oldtemps=read_rows(WORK/'reports/iq_noise_summary_v17/data/v2_campaign/dc_ac_temperature_by_run.csv')
 old={int(x['run']):x for x in oldtemps if x['mode']=='TM010'};temperature_rows=[];metadata_records=[]
 for run in range(680,940):
  path=WORK/f'reports/noise_fullrange_v2_20261109/run{run:05d}_noise_v2.h5'
  with h5py.File(path) as h:
   assert h['summary/iq_sign'][()]==-1 and h['summary/reached_eof'][()]
   timestamps=h['filtered_bands/modes/TM010/band_04/events/event_timestamp_unix'][:]
   start,stop=float(timestamps.min()),float(timestamps.max())
  metadata_records.append({'run':run,'source_h5':str(path),'start':start,'stop':stop,'size':path.stat().st_size,'mtime_ns':path.stat().st_mtime_ns})
  rr={'run':run,'SPEC_start_unix':start,'SPEC_stop_unix':stop}
  for alias in SENSORS:
   values=np.array([v for t,v in observations[run][alias] if start<=t<=stop])
   keep=np.isfinite(values)&(values>0)
   valid=values[keep]
   rr[alias]=float(np.median(valid)) if len(valid) else np.nan
   rr[alias+'_observations']=len(values);rr[alias+'_valid_positive']=len(valid)
   if alias in ['T15','T16','T17']:
    np.testing.assert_allclose(rr[alias],float(old[run][alias.lower()+'_median_mk']),rtol=0,atol=0)
    assert len(valid)==int(old[run][alias.lower()+'_observations'])
  temperature_rows.append(rr)
 for alias in SENSORS:
  values=np.array([row[alias] for row in temperature_rows]);counts=np.array([row[alias+'_valid_positive'] for row in temperature_rows]);finite=values[np.isfinite(values)]
  sensorinfo[alias]['quality']={'runs_with_valid_positive_median':len(finite),'observations_total_in_SPEC_span':sum(row[alias+'_observations'] for row in temperature_rows),'valid_positive_observations':int(counts.sum()),'observations_per_run_min':int(counts.min()),'observations_per_run_max':int(counts.max()),'median_min':float(finite.min()) if len(finite) else None,'median_max':float(finite.max()) if len(finite) else None,'distinct_run_medians':len(np.unique(finite)),'calibration_precision':'Recorded float32 and documented units; no new thermometer calibration/accuracy estimate.'}
 sensorinfo['Mercury4K']['interpretation']='Thermometer on the 4K plate. Thesis places HEMT on 4K stage; not a direct HEMT junction/case measurement.'
 sensorinfo['MercuryMCdiode']['interpretation']='Recorded zero values are invalid temperature readings, not evidence of a0K mixing chamber; excluded from correlations.'
 # Clone prior analytical reference exactly; update only seven measured PSD integrals.
 out=a.output/'expectations_and_campaign.h5';shutil.copy2(BASE/'expectations_and_campaign.h5',out)
 coeff=firwin(2001,25000,fs=FS,window=('kaiser',8.6))
 with h5py.File(out,'r+') as h:
  for run in verification['corrected_runs']:
   path=VERIFY/'corrected_fft_by_run'/f'run{run:05d}.npz';ledger[str(path)]=sha(path)
   with np.load(path) as archive:
    assert archive['iq_sign']==-1 and archive['original_iq_sign']==1
    for mi,m in enumerate(MODES):
     arr=archive[f'fft_amp_mode{mi}_SPECs'].astype(float);n=len(arr);window=np.hanning(n);enbw=FS*sum(window**2)/sum(window)**2
     peak=h[m+'/ADC_peak_V'][run-680];psd=np.fft.ifftshift(arr)*(peak/5)**2/enbw
     centers=h[m+'/centers_IF_hz'][run-680];power=response_power(coeff,centers,n)@psd*(FS/n)
     controls=response_power(coeff,ELECTRONIC,n)@psd*(FS/n)
     h[m+'/power_ADC_V2'][run-680]=power;h[m+'/archived_electronic_power_ADC_V2'][run-680]=controls
  time=h['time_unix'][:];dctable=read_rows(WORK/'simulation/step7/dc_longterm_diagnostic/longterm.csv');dc={m:sorted([x for x in dctable if x['mode']==m],key=lambda x:int(x['run'])) for m in MODES}
  r['correlations']={};r['full_band_temperature_correlations']={};r['electronic_temperature_correlations']={};r['noise_spans']={};r['between_mode_correlations']={}
  for m in MODES:
   power=h[m+'/power_ADC_V2'][:];legacy=h[m+'/electronic_power_ADC_V2'][:];controls=h[m+'/archived_electronic_power_ADC_V2'][:]
   err=controls/legacy-1;h[m+'/electronic_control_relative_error'][:]=err;h[m+'/shared_window_power_relative_error'][:]=err[:,8]
   v=r['validation'][m];v['v46_allarchive_screen']=dict(v);v['qualified_descriptive_use']=True
   v.update(accepted=True,signed_coordinate_selected_n=260,shared_1MHz_power_error_percent_median=float(np.median(err[:,8])*100),min=float(err[:,8].min()*100),max=float(err[:,8].max()*100),selected_max_abs_power_error_percent=float(np.max(abs(err[:,8]))*100),selected_median_power_error_percent=float(np.median(err[:,8])*100),selected_first_last_difference_percentage_points=float(100*(err[-1,8]-err[0,8])),selected_error_vs_time=correlations(err[:,8],time,time)['raw'],runs_outside_1pct=[],decision='All260 coordinates validated by execution arguments and byte-identical artifacts; seven sign-corrected copies use exact conjugation reindexing confirmed on original SPEC. No empirical gain correction.')
   v['all_nonzero_electronic_max_abs_power_error_percent']=float(np.max(abs(err[:,[0,1,2,3,5,6,7,8]]))*100)
   assert v['selected_max_abs_power_error_percent']<.11 and v['all_nonzero_electronic_max_abs_power_error_percent']<.15
   r['correlations'][m]={f'offset_{int(off)}':{alias:summarize_coeff(power[:,bi],np.array([x[alias] for x in temperature_rows]),time) for alias in SENSORS} for bi,off in enumerate(OFFSETS)}
   full=np.array([float(x['AC2_ADC_V2']) for x in dc[m]])
   r['full_band_temperature_correlations'][m]={alias:summarize_coeff(full,np.array([x[alias] for x in temperature_rows]),time) for alias in SENSORS}
   r['electronic_temperature_correlations'][m]={f'offset_{int(off)}':{alias:summarize_coeff(legacy[:,bi],np.array([x[alias] for x in temperature_rows]),time) for alias in SENSORS} for bi,off in enumerate(ELECTRONIC)}
   span=lambda z:float(100*(np.sqrt(np.max(z)/np.min(z))-1))
   cs=power[:,3]/np.delete(power,3,axis=1).mean(axis=1)
   r['noise_spans'][m]={'full_band_RMS_max_over_min_percent':span(full),'resonance_mean_side_RMS_max_over_min_percent':span(np.delete(power,3,axis=1).mean(axis=1)),'electronic_mean_side_RMS_max_over_min_percent':span(np.delete(legacy,4,axis=1).mean(axis=1)),'resonance_central_over_side_relative_span_percent':float(100*np.ptp(cs/cs[0])),'resonance_each_band_RMS_span_percent':[span(power[:,i]) for i in range(7)]}
  for bank in ['resonance','electronic','full_band']:
   arr={m:(h[m+'/power_ADC_V2'][:,3] if bank=='resonance' else h[m+'/electronic_power_ADC_V2'][:,4] if bank=='electronic' else np.array([float(x['AC2_ADC_V2']) for x in dc[m]])) for m in MODES}
   r['between_mode_correlations'][bank]={a+'_'+b:correlations(arr[a],arr[b],time) for a,b in [('TM010','TM011'),('TM010','TM012'),('TM011','TM012')]}
  h['valid_signed_coordinate_mask'][:]=True
  newaudit={'available_runs':260,'included_n':260,'included_runs':list(range(680,940)),'quarantined_runs':[],'corrected_runs':verification['corrected_runs'],'reflection_is_proven':True,'sign_correction_applied':True,'correction_kind':'Lossless frequency reindexing from documentedIQ+1;no gain or curve fit','verification_source':str(VERIFY/'verification.json'),'scope':'All260resonance runs;originalelectronic/fullband260 unchanged'}
  r['coordinate_audit']=newaudit;h.attrs['coordinate_audit_json']=json.dumps(newaudit)
  r['scope']='All260 archived full-run spectra with verified coordinates; seven corrected copies; no complete raw reconstruction or new toy.';h.attrs['scope']=r['scope']
  with open(a.output/'campaign_band_powers.csv','w') as stream:
   fields=['run','time_unix','mode','offset_hz','center_IF_hz','power_ADC_V2','RMS_ADC_V','RMS_change_from_run680_percent','signed_coordinate_validated','PSD_source']+list(SENSORS)
   writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
   for mi,m in enumerate(MODES):
    pp=h[m+'/power_ADC_V2'][:]
    for ri,run in enumerate(range(680,940)):
     for bi,off in enumerate(OFFSETS):writer.writerow(dict(run=run,time_unix=time[ri],mode=m,offset_hz=int(off),center_IF_hz=h[m+'/centers_IF_hz'][ri,bi],power_ADC_V2=pp[ri,bi],RMS_ADC_V=np.sqrt(pp[ri,bi]),RMS_change_from_run680_percent=100*(np.sqrt(pp[ri,bi]/pp[0,bi])-1),signed_coordinate_validated=True,PSD_source='validated conjugate copy' if run in verification['corrected_runs'] else 'original verified I-iQ archive',**{k:temperature_rows[ri][k] for k in SENSORS}))
 r['temperature_sensor_inventory']=sensorinfo;r['input_sha256']=ledger;r['coordinate_verification_source']=str(VERIFY/'verification.json');r['limitations']=[s for s in r['limitations'] if 'Seven NPZ' not in s]
 r['limitations'].append('HEMT-stage temperature is measured on4Kplate,not onHEMT; correlations are descriptive and cannot separate gain/noise-temperature contributions.')
 assert all(sha(p)==v for p,v in ledger.items())
 (a.output/'results.json').write_text(json.dumps(r,indent=2)+'\n');(a.output/'sensor_inventory.json').write_text(json.dumps(sensorinfo,indent=2)+'\n');(a.output/'temperature_SPEC_bounds_provenance.json').write_text(json.dumps(metadata_records,indent=2)+'\n')
 with open(a.output/'temperatures_by_run.csv','w') as stream:
  wr=csv.DictWriter(stream,fieldnames=temperature_rows[0]);wr.writeheader();wr.writerows(temperature_rows)
 print('CLOSED all260;validated sensoraliases;toy preserved;no raw reconstruction',flush=True)
 for alias,info in sensorinfo.items():print(alias,info['physical_name'],info['quality'],flush=True)
 print('Noise spans',json.dumps(r['noise_spans']),flush=True)
if __name__=='__main__':main()
