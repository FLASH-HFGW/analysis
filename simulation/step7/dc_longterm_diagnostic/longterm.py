"""Reuse 260 existing v2 moment products; read BOR metadata only from raw."""
from pathlib import Path
import csv,hashlib,json,sys
import numpy as np,h5py
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import *
sys.path.insert(0,'/cvmfs/sft-flash.infn.it/package/midas/python');import midas.file_reader
OUT.mkdir(parents=True,exist_ok=True)
temp={}
with (INPUT/'dc_ac_temperature_by_run.csv').open() as stream:
 for row in csv.DictReader(stream):temp[(int(row['run']),row['mode'])]=row
rows=[];hardware=[];manifest=[]
for run in range(680,940):
 path=INPUT/f'run{run:05d}_noise_v2.h5';raw=Path('/home/mazzitel/flash-data/data/LNF')/f'run{run:05d}.mid.gz'
 reader=midas.file_reader.MidasFile(str(raw),use_numpy=True);odb=reader.get_bor_odb_dump().data;reader.file.close()
 settings=odb['Equipment']['NetBox']['Settings'];ranges=np.asarray(settings['Channel_range_mV'][:6],float)/1000
 lo={k:v for k,v in odb['Equipment'].get('LocalOscill',{}).get('Variables',{}).items() if '/key' not in k and isinstance(v,(int,float,str,bool))}
 hw={'run':run,'sampling_rate_MS':settings.get('Sampling_rate_MS'),'ADC_peak_V':ranges.tolist(),'LO':lo};hardware.append(hw)
 with h5py.File(path) as h:
  assert h['summary/reached_eof'][()] and h['summary/iq_sign'][()]==-1
  savedrange=float(h['summary/input_range_v'][()]);gain=float(h['dc_removed/calibration/voltage_gain'][()]);gain_db=float(h['dc_removed/calibration/configuration/total_db'][()])
  for mi,mode in enumerate(MODES):
   assert ranges[2*mi]==ranges[2*mi+1]
   factor=ranges[2*mi]/savedrange;g=h['dc_removed/modes/'+mode];v={k:float(g[k][()]) for k in g if k!='n'}
   i=v['mean_i_v']*factor;qeff=v['mean_q_v']*factor;dc=v['dc_squared_v2']*factor**2;ac=v['ac_squared_v2']*factor**2;total=v['total_squared_v2']*factor**2
   np.testing.assert_allclose(dc,i*i+qeff*qeff,rtol=1e-12);np.testing.assert_allclose(total,dc+ac,rtol=1e-12)
   tr=temp.get((run,mode),{});ts=float(tr.get('spec_midpoint_unix',np.nan))
   row=dict(run=run,mode=mode,time_unix=ts,mean_I_ADC_V=i,mean_Qhardware_ADC_V=-qeff,mean_Qeff_ADC_V=qeff,DC_abs_ADC_V=np.sqrt(dc),DC_phase_rad=np.arctan2(qeff,i),DC2_ADC_V2=dc,AC2_ADC_V2=ac,total2_ADC_V2=total,DC2_over_AC2=dc/ac,mean_I_nominal_input_V=i/gain,mean_Qeff_nominal_input_V=qeff/gain,DC_abs_nominal_input_V=np.sqrt(dc)/gain,AC_rms_nominal_input_V=np.sqrt(ac)/gain,DC2_nominal_input_V2=dc/gain**2,AC2_nominal_input_V2=ac/gain**2,total2_nominal_input_V2=total/gain**2,nominal_gain_db=gain_db,stored_ADC_peak_V=savedrange,physical_ADC_peak_V=ranges[2*mi],voltage_correction=factor,samples=int(g['n'][()]))
   for sensor in ('t15','t16','t17'):row[sensor+'_mK']=float(tr.get(sensor+'_median_mk',np.nan))
   for k,val in lo.items():
    if isinstance(val,(int,float)):row['LO_'+k]=val
   rows.append(row)
 stat=path.stat();manifest.append(dict(path=str(path),size=stat.st_size,mtime_ns=stat.st_mtime_ns))
 if run%30==0:print('Read v2 + BOR',run,flush=True)
keys=sorted(set().union(*(r.keys() for r in rows)))
with (OUT/'longterm.csv').open('w') as stream:
 writer=csv.DictWriter(stream,keys);writer.writeheader();writer.writerows(rows)
(OUT/'hardware.json').write_text(json.dumps(hardware,indent=2));(OUT/'product_manifest.json').write_text(json.dumps(manifest,indent=2))
fig,axs=plt.subplots(6,3,figsize=(15,17),sharex=True)
fig2,ax2=plt.subplots(1,3,figsize=(14,4));t0=min(r['time_unix'] for r in rows)
for j,mode in enumerate(MODES):
 a=[r for r in rows if r['mode']==mode];t=np.array([(r['time_unix']-t0)/3600 for r in a]);get=lambda k:np.array([r[k] for r in a])
 axs[0,j].plot(t,get('mean_I_ADC_V')*1e3,color=COLORS['I'],label='I');axs[0,j].plot(t,get('mean_Qhardware_ADC_V')*1e3,color=COLORS['Q'],label='Q hardware');axs[0,j].set(title=mode,ylabel='Mean [mV ADC]');axs[0,j].legend()
 axs[1,j].plot(t,get('DC_abs_ADC_V')*1e3,color=COLORS['data']);axs[1,j].set_ylabel('|DC| [mV ADC]')
 axs[2,j].plot(t,get('DC_phase_rad'),'.',color=COLORS['data'],ms=2);axs[2,j].set_ylabel('arg(I-iQ) [rad]')
 for k,label,col in [('DC2_ADC_V2','DC²',COLORS['fit']),('AC2_ADC_V2','AC²',COLORS['data']),('total2_ADC_V2','Total²',COLORS['theory'])]:axs[3,j].plot(t,get(k),label=label,color=col)
 axs[3,j].set_yscale('log');axs[3,j].set_ylabel('Quadratic voltage [V² ADC]');axs[3,j].legend(fontsize=8)
 axs[4,j].plot(t,get('DC2_over_AC2'),color=COLORS['data']);axs[4,j].set_ylabel('DC² / AC²');axs[4,j].set_yscale('log')
 axs[5,j].plot(t,get('DC_abs_nominal_input_V')*1e12,color=COLORS['data']);axs[5,j].set(ylabel='|DC| [pV nominal input]',xlabel='Acquisition time since run680 [h]')
 ax2[j].plot(get('mean_I_ADC_V')*1e3,get('mean_Qeff_ADC_V')*1e3,color=COLORS['data'],lw=.5);s=ax2[j].scatter(get('mean_I_ADC_V')*1e3,get('mean_Qeff_ADC_V')*1e3,c=t,s=9,cmap='viridis');ax2[j].set(title=mode,xlabel='Mean I [mV ADC]',ylabel='Mean Qeff=-Qhardware [mV ADC]');fig2.colorbar(s,ax=ax2[j],label='Acquisition time [h]')
 for ax in axs[:,j]:ax.grid(alpha=.2)
fig.tight_layout();fig.savefig(OUT/'longterm_DC_AC.png',dpi=160);plt.close(fig);fig2.tight_layout();fig2.savefig(OUT/'IQ_center_trajectory.png',dpi=180);plt.close(fig2)
# All correlations preserve DC components, rather than amplitude alone.
correlations=[]
for mode in MODES:
 a=[r for r in rows if r['mode']==mode];t=[r['time_unix'] for r in a]
 for dc in ['mean_I_ADC_V','mean_Qeff_ADC_V','DC_abs_ADC_V','DC2_over_AC2']:
  targets=['AC2_ADC_V2','t15_mK','t16_mK','t17_mK']+[k for k in keys if k.startswith('LO_')]+['nominal_gain_db','physical_ADC_peak_V']
  for target in targets:
   correlations.append(dict(mode=mode,x=dc,y=target,**association([r[dc] for r in a],[r.get(target,np.nan) for r in a],t)))
for mi,m1 in enumerate(MODES):
 for m2 in MODES[mi+1:]:
  a=[r for r in rows if r['mode']==m1];b=[r for r in rows if r['mode']==m2]
  for x in ['mean_I_ADC_V','mean_Qeff_ADC_V','DC_abs_ADC_V']:
   for y in ['mean_I_ADC_V','mean_Qeff_ADC_V','DC_abs_ADC_V']:
    correlations.append(dict(mode=m1+' vs '+m2,x=x,y=y,**association([r[x] for r in a],[r[y] for r in b],[r['time_unix'] for r in a])))
(OUT/'correlations.json').write_text(json.dumps(correlations,indent=2))
# Selection uses existing moments only, with endpoints and extremes of TM010 ratio.
a=[r for r in rows if r['mode']=='TM010'];selected=sorted(set([680,939,min(a,key=lambda r:r['DC2_over_AC2'])['run'],max(a,key=lambda r:r['DC2_over_AC2'])['run']]))
summary=dict(status='complete',runs=260,selected_runs=selected,selection='Endpoints plus minimum/maximum TM010 DC²/AC² in complete v2 products',time_start_unix=t0,time_stop_unix=max(r['time_unix'] for r in rows),ADC_range_states=sorted(set(r['physical_ADC_peak_V'] for r in rows)),voltage_correction_states=sorted(set(r['voltage_correction'] for r in rows)),nominal_gain_db_states=sorted(set(r['nominal_gain_db'] for r in rows)),hardware_unique_values={k:sorted(set(str(h['LO'].get(k)) for h in hardware)) for k in hardware[0]['LO']},missing_temperature_rows={s:sum(not np.isfinite(r[s+'_mK']) for r in rows) for s in ['t15','t16','t17']},gain_limitation='No measured per-run physical LF/RF gains found in selected BOR equipment; nominal stored gain is not an independent hardware monitor',source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('common.py'),ROOT/'analysis/examples/iq_noise_v2.py',ROOT/'analysis/examples/analyze_midas_iq_noise.py']})
(OUT/'longterm_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
