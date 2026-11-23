from pathlib import Path
import json,csv,collections
import numpy as np
O=Path(__file__).resolve().parents[1];read=lambda n:list(csv.DictReader(open(O/'tables'/n)));M=['TM010','TM011','TM012'];inv=json.load(open(O/'data/inventory.json'));thresholds=json.load(open(O/'data/frozen_thresholds.json'))
def write(name,rows):
 with (O/'tables'/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
bins=read('pilot1429_binned_statistics.csv');one=[r for r in bins if r['nominal_bin_ms']=='1000'];write('pilot1429_1s.csv',one);lookup={(r['mode'],int(round(float(r['start_received_s'])*100))):r for r in bins if r['nominal_bin_ms']=='10'}
hits=read('pilot1429_T7_samples.csv');enriched=[]
for r in hits:
 b=lookup[r['mode'],int(r['index'])//50000];enriched.append(dict(**r,local_RMS_10ms_V=float(b['RMS_V']),amplitude_over_local_RMS=float(r['amplitude_V'])/float(b['RMS_V'])))
write('pilot1429_T7_with_local_RMS.csv',enriched)
ctx=read('pilot1429_cross_mode_context.csv');conditional=[]
for a in M:
 th=thresholds['1429'][a]['sigma_Rayleigh_V']*(np.sqrt(np.pi/2)+7*np.sqrt((4-np.pi)/2));sel=[r for r in ctx if float(r['A_'+a+'_V'])>th]
 for b in M:
  if b==a:continue
  sigma=thresholds['1429'][b]['sigma_Rayleigh_V'];v=np.array([float(r['A_'+b+'_V'])/sigma for r in sel]);peak=np.array([float(r['max100us_'+b+'_V'])/sigma for r in sel]);r7=np.sqrt(np.pi/2)+7*np.sqrt((4-np.pi)/2);conditional.append(dict(seed_mode=a,other_mode=b,samples=len(v),median_other_A_over_sigma=float(np.median(v)),p95_other_A_over_sigma=float(np.quantile(v,.95)),median_other_max100us_over_sigma=float(np.median(peak)),fraction_other_T7_at_seed=float(np.mean(v>r7)),fraction_other_T7_within100us=float(np.mean(peak>r7)),scope='conditional acquisition-index amplitudes; no joint-noise null or calibrated delay'))
write('pilot1429_conditional_other_modes.csv',conditional)
groups=read('pilot1429_clusters.csv');sensitivity=[]
for m in M:
 for gap in sorted(set(int(r['gap_nonexceeding_samples']) for r in groups)):
  g=[r for r in groups if r['mode']==m and int(r['gap_nonexceeding_samples'])==gap];sensitivity.append(dict(mode=m,gap_nonexceeding_samples=gap,gap_nonexceeding_us=gap/5,groups=len(g),maximum_multiplicity=max(int(r['multiplicity']) for r in g),largest_duration_us=max(int(r['duration_samples']) for r in g)/5))
write('pilot1429_cluster_sensitivity.csv',sensitivity)
temps=read('temperatures.csv');channels=sorted(set(r['channel'] for r in temps));medians=[]
for rec in inv['runs']:
 for ch in channels:
  a=[r for r in temps if int(r['run'])==rec['run'] and r['channel']==ch and r['sensor_value_valid']=='True' and r['within_ADC_header_coverage']=='True']
  if a:medians.append(dict(run=rec['run'],channel=ch,documented_role=a[0]['documented_role'],n=len(a),median_K=float(np.median([float(r['value_K']) for r in a])),start_unix=rec['start_unix'],role_qualification='documented mapping, Run3 wiring not independently verified'))
write('temperature_run_medians.csv',medians)
def corr(a,b):return float(np.corrcoef(a,b)[0,1]) if len(a)>2 and np.std(a)>0 and np.std(b)>0 else None
associations=[]
for ch in channels:
 selected=[next((r for r in medians if int(r['run'])==run and r['channel']==ch),None) for run in [1429,1529,1629,1729]]
 if any(r is None for r in selected):continue
 t=np.array([r['median_K'] for r in selected]);dt=np.diff([r['start_unix'] for r in selected])/3600
 for mode in M:
  rms=np.array([next(x for x in inv['runs'] if x['run']==run)['fullrun_attributes'][mode]['rms_V'] for run in [1429,1529,1629,1729]])
  associations.append(dict(channel=ch,mode=mode,population='four Run3-B runs;680 excluded',N_levels=4,Pearson_levels=corr(t,rms),N_first_differences=3,Pearson_first_differences=corr(np.diff(t),np.diff(rms)),time_intervals_h=';'.join(map(str,dt)),scope='exploratory, no causal claim or significance; first differences are not time derivatives'))
write('temperature_crossrun_RMS_associations.csv',associations)
within=[]
for ch in channels:
 tr=[r for r in temps if r['run']=='1429' and r['channel']==ch and r['sensor_value_valid']=='True' and r['within_ADC_header_coverage']=='True'];
 if len(tr)<4:continue
 for mode in M:
  b=[r for r in one if r['mode']==mode];x=[];yr=[];yc=[]
  for t in tr:
   sec=float(t['time_from_first_ADC_header_s']);sel=[r for r in b if abs(float(r['start_received_s'])+.5-sec)<10]
   if not sel:continue
   exposure=np.array([float(r['exposure_s']) for r in sel]);x.append(float(t['value_K']));yr.append(np.sqrt(np.average([float(r['RMS_V'])**2 for r in sel],weights=exposure)));yc.append(sum(int(r['T7_count']) for r in sel)/exposure.sum())
  within.append(dict(run=1429,channel=ch,mode=mode,N=len(x),RMS_Pearson_levels=corr(x,yr),T7_rate_Pearson_levels=corr(x,yc),RMS_Pearson_first_differences=corr(np.diff(x),np.diff(yr)),T7_rate_Pearson_first_differences=corr(np.diff(x),np.diff(yc)),timing='approximate header-relative +/-10s support; unanchored UTC, serial latency not calibrated',scope='autocorrelated slow-control association; no significance; cluster rate equals T7 sample rate for the tested singleton groups'))
write('pilot1429_temperature_associations.csv',within)
print('POSTPROCESS COMPLETE')
