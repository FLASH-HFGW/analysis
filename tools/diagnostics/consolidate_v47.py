"""Consolidate existing v2 statistical products; no raw reads or physical fits."""
from pathlib import Path
import csv,json,hashlib,shutil
import h5py,numpy as np
R=Path('/home/mazzitel/HFGW');W=R/'analysis-work/Run2';OUT=W/'diagnostics/v47_primary_audit_20261117';OUT.mkdir(exist_ok=True)
V2=W/'reports/noise_fullrange_v2_20261109';V1=W/'reports/noise_fullrange_v1_20261109';C=W/'diagnostics/resonance_campaign_closed_v47_20261117';M=['TM010','TM011','TM012']
def read(p):
 with open(p) as f:return list(csv.DictReader(f))
def write(name,rr):
 with open(OUT/name,'w') as f:
  wr=csv.DictWriter(f,fieldnames=list(rr[0]));wr.writeheader();wr.writerows(rr)
def scalar(h,p):
 v=h[p][()];return v.decode() if isinstance(v,bytes) else v.item() if isinstance(v,np.generic) else v
old=read(W/'simulation/step7/dc_longterm_diagnostic/longterm.csv');old={(int(v['run']),v['mode']):v for v in old}
legacy=read(W/'staging/gpfs_noise_v0_20261108/originals/noise_global/runs.csv');legacy={(int(v['run'].replace('run','')),v['mode']):v for v in legacy}
temps={int(v['run']):v for v in read(C/'temperatures_by_run.csv')}
full=[];raw=[];bands=[];diffs=[];checks=[];ledger={};missing=[];dataset_diff={};v1count=0
# HDF5 stores all requested empirical histograms; copy them without reconstructing distributions.
with h5py.File(OUT/'primary_v2_distributions.h5','w') as archive:
 archive.attrs['normalization']='Edges scaled once by2/saved input_range_v; counts unchanged. Centered envelope is not DC-subtracted complex amplitude.'
 for run in range(680,940):
  path=V2/f'run{run:05d}_noise_v2.h5';ledger[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
  p1=V1/f'run{run:05d}_noise.h5'
  if not p1.exists():
   candidates=list((W/'reports').glob(f'*pilot*/*run{run:05d}_noise.h5'));p1=candidates[0] if candidates else p1
  v1=h5py.File(p1) if p1.exists() else None
  if v1:v1count+=1
  else:missing.append(run)
  with h5py.File(path) as h:
   scale=2/float(scalar(h,'summary/input_range_v'));n=int(scalar(h,'summary/samples'));fs=float(scalar(h,'summary/fs_hz'));events=json.loads(scalar(h,'summary/events'));clock=.5*(events[0]['midas_timestamp']+events[-1]['midas_timestamp'])
   assert scalar(h,'summary/iq_sign')==-1 and scalar(h,'summary/reached_eof') and n==1048576000
   keys=[]
   def collect(name,o):
    if isinstance(o,h5py.Dataset) and (name.startswith('arrays/') or name.startswith('modes/') or name.startswith('summary/global_statistics/modes/') or name.startswith('summary/modes/')):keys.append(name)
   h.visititems(collect)
   if v1:
    for name in keys:
     if name not in v1:continue
     x=h[name][()];y=v1[name][()]
     if np.shape(x)!=np.shape(y):ok=False;err=None
     elif np.asarray(x).dtype.kind in 'biufc' and np.asarray(y).dtype.kind in 'biufc':
      ok=np.array_equal(x,y,equal_nan=True);err=float(np.nanmax(abs(np.asarray(x,dtype=complex)-np.asarray(y,dtype=complex)))) if np.size(x) else 0.
     else:ok=np.array_equal(x,y);err=None
     rec=dataset_diff.setdefault(name,dict(compared=0,different=0,max_abs_error=0.,different_runs=[]));rec['compared']+=1
     if not ok:rec['different']+=1;rec['different_runs'].append(run)
     if err is not None:rec['max_abs_error']=max(rec['max_abs_error'],err)
   gg=archive.create_group(f'run{run:05d}');gg.attrs['source']=str(path);gg.attrs['ADC_voltage_scale_applied_once']=scale
   for name in ['arrays','summary/global_statistics/modes']:
    h.copy(name,gg,name='arrays' if name=='arrays' else 'global_statistics')
   for name in gg['arrays']:
    if name.endswith('_v'):
     ds=gg['arrays/'+name];ds[:]=ds[:]*scale
   for mode in M:
    st=h['summary/global_statistics/modes/'+mode];dc=h['dc_removed/modes/'+mode];mean=float(st['mean'][()]);std=np.sqrt(float(st['m2'][()])/int(st['n'][()]));row=dict(old[(run,mode)])
    row.update(run=run,mode=mode,time_unix=clock,samples=n,physical_ADC_peak_V=2,stored_ADC_peak_V=2/scale,voltage_correction=scale)
    for key,ds in [('AC2_ADC_V2','ac_squared_v2'),('DC2_ADC_V2','dc_squared_v2'),('total2_ADC_V2','total_squared_v2')]:row[key]=float(dc[ds][()])*scale**2
    row['AC_rms_ADC_V']=np.sqrt(row['AC2_ADC_V2']);row['DC_abs_ADC_V']=np.sqrt(row['DC2_ADC_V2']);row['mean_I_ADC_V']=float(dc['mean_i_v'][()])*scale;row['mean_Qeff_ADC_V']=float(dc['mean_q_v'][()])*scale;row['mean_Qhardware_ADC_V']=-row['mean_Qeff_ADC_V']
    for sensor in (15,16,17):row[f't{sensor}_mK']=float(temps[run][f'T{sensor}'])
    # Remove inherited nominal-input quantities entirely from new scientific tables.
    row={k:v for k,v in row.items() if 'nominal' not in k and not k.startswith('LO_')}
    full.append(row);r=dict(run=f'run{run:05d}',mode=mode,complete=True,samples=n,acquired_duration_s=n/fs,mean_amplitude_v=mean*scale,amplitude_noise_rms_v=std*scale)
    for pop in ['local','reference']:
     for sig in ('3','5','7'):
      b=st[f'exceedances/{pop}/{sig}'];prefix=f'{pop}_{sig}sigma_';above=int(b['samples_above'][()]);episodes=int(b['episodes'][()]);peak=scalar(h,f'summary/global_statistics/modes/{mode}/exceedances/{pop}/{sig}/peak_v')
      r.update({prefix+'threshold_v':float(st[f'thresholds_v/{pop}/{sig}'][()])*scale,prefix+'samples_above':above,prefix+'episodes':episodes,prefix+'peak_v':float(peak)*scale if peak is not None else '',prefix+'fraction':above/n,prefix+'episodes_per_acquired_s':episodes/(n/fs),prefix+'longest_s':float(b['longest_samples'][()])/fs})
    raw.append(r)
    for key,value in r.items():
     if key not in legacy[(run,mode)] or key in ('run','mode','complete'):continue
     try:
      a=float(legacy[(run,mode)][key]);factor=scale if key.endswith('_v') else 1;expected=a*factor;err=abs(float(value)-expected);checks.append(dict(run=run,mode=mode,observable=key,abs_difference=err,passed=bool(np.isclose(float(value),expected,rtol=1e-12,atol=1e-14))))
     except (TypeError,ValueError):pass
    for bi in range(9):
     b=h[f'filtered_bands/modes/{mode}/band_{bi:02d}'];p=float(b['complex_moments/total_squared_v2'][()])*scale**2;ac=float(b['complex_moments/ac_squared_v2'][()])*scale**2
     bands.append(dict(run=run,mode=mode,band=bi,center_hz=float(b['center_hz'][()]),offset_hz=float(b['offset_hz'][()]),ENBW_hz=float(b['fir_enbw_two_sided_hz'][()]),power_ADC_V2=p,AC_power_ADC_V2=ac,RMS_ADC_V=np.sqrt(p),samples=int(b['complex_moments/n'][()]),source=str(path),dataset=f'filtered_bands/modes/{mode}/band_{bi:02d}/complex_moments/total_squared_v2'))
    g=gg.create_group(mode)
    for name in ['iq_counts','iq_i_edges_v','iq_q_edges_v','noise_counts','noise_edges_v','phase_counts','phase_edges_rad']:
     a=h[f'modes/{mode}/{name}'][()];a=a*scale if name.endswith('_v') else a;g.create_dataset(name,data=a,compression='gzip')
    g.attrs['noise_edges_definition']='A_centered = abs(z)-mean(abs(z)); not abs(z-mean(z))'
   if v1:v1.close()
  if run%40==0:print('Audited',run,flush=True)
write('fullband_v2.csv',full);write('raw_statistics_v2.csv',raw);write('electronic_bands_v2.csv',bands);write('legacy_table_comparison.csv',checks)
(OUT/'v1_v2_dataset_comparison.json').write_text(json.dumps(dict(compared_runs=v1count,missing_v1_runs=missing,datasets=dataset_diff),indent=2))
(OUT/'primary_input_sha256.json').write_text(json.dumps(ledger,indent=2))
# Replace inherited electronic powers in a separate, traceable copy, never original products.
CNEW=W/'diagnostics/resonance_campaign_primary_v47_20261117';CNEW.mkdir(exist_ok=True)
for p in C.iterdir():
 if p.is_file():shutil.copy2(p,CNEW/p.name)
result=json.loads((CNEW/'results.json').read_text());bandmap={(v['run'],v['mode'],v['band']):v['power_ADC_V2'] for v in bands};closure={}
with h5py.File(CNEW/'expectations_and_campaign.h5','r+') as h:
 for mode in M:
  p=np.array([[bandmap[(run,mode,i)] for i in range(9)] for run in range(680,940)]);prev=h[mode+'/electronic_power_ADC_V2'][:];closure[mode]=dict(max_relative_difference=float(np.max(abs(p/prev-1))));h[mode+'/electronic_power_ADC_V2'][:]=p
  err=h[mode+'/archived_electronic_power_ADC_V2'][:]/p-1;h[mode+'/electronic_control_relative_error'][:]=err;h[mode+'/shared_window_power_relative_error'][:]=err[:,8]
 h.attrs['primary_electronic_source']=str(V2);h.attrs['fullband_source']=str(OUT/'fullband_v2.csv')
result['primary_v2_audit']=str(OUT);result['electronic_source']='Direct260v2HDF5complex_moments/total_squared_v2,ADCfactor0.16appliedonce';(CNEW/'results.json').write_text(json.dumps(result,indent=2))
summary=dict(complete_v2_runs=260,fullband_rows=len(full),raw_statistic_rows=len(raw),electronic_band_rows=len(bands),v1_compared_runs=v1count,v1_missing_runs=missing,v1_dataset_mismatches=sum(v['different'] for v in dataset_diff.values()),legacy_table_checks=len(checks),legacy_table_failures=sum(not v['passed'] for v in checks),electronic_replacement=closure,no_raw_reads=True,no_new_nominal_input_quantities=True)
(OUT/'consolidation_validation.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
