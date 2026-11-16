"""Limited raw checks: first 16 SPEC in four preselected runs, plus synthetic controls."""
from pathlib import Path
import csv,hashlib,json,sys,time,gc
import numpy as np,h5py
from scipy import signal,stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import *
sys.path.insert(0,'/cvmfs/sft-flash.infn.it/package/midas/python');import midas.file_reader
OUT.mkdir(parents=True,exist_ok=True)
config=json.loads((OUT/'longterm_summary.json').read_text());selected=config['selected_runs'];long=list(csv.DictReader((OUT/'longterm.csv').open()))
report={'status':'running','raw_scope':'First16SPEC only per selected run; no full-run reconstruction','runs':{},'synthetic':{}};allrows=[];arr={};start=time.perf_counter()
nffts=[2**14,2**18,SPEC,4*SPEC];treatments=['none','global','spec'];styles={'none':('#777777','-'),'global':(COLORS['data'],'-'),'spec':(COLORS['fit'],'--')}

def shape_analysis(z,label,axes):
 metrics=[];cached={}
 for nf in nffts:
  for treatment in treatments:
   f,pi,pq,sp,sm,c=spectral_matrix(z,nf,treatment)
   for name,p in [('I',pi),('Qeff',pq),('complex_symmetric',(sp+sm)/2)]:
    m=notch_metrics(f,p);m.update(nfft=nf,FFT_duration_s=nf/FS,FFT_df_hz=FS/nf,treatment=treatment,quantity=name)
    metrics.append(m)
   # Deficit centroid from +/-50kHz, excluding the unresolved central +/-500Hz.
   mask=(f>=500)&(f<50000);plateau=np.mean((sp+sm)[(f>.5e6)&(f<1.5e6)])/2
   wp=np.maximum(1-sp[mask]/plateau,0);wm=np.maximum(1-sm[mask]/plateau,0)
   metrics[-1]['deficit_centroid_hz']=float(np.sum(f[mask]*(wp-wm))/np.sum(wp+wm)) if np.sum(wp+wm)>0 else None
   # Keep plotting products small; full-resolution metrics calculated above.
   group=max(1,len(f)//20000);cut=len(f)//group*group
   ff=f[:cut].reshape(-1,group).mean(axis=1)
   ps=[p[:cut].reshape(-1,group).mean(axis=1) for p in [pi,pq,(sp+sm)/2]]
   if nf==4*SPEC or (nf==2**14 and treatment=='global'):
    for ax,p in zip(axes,ps):
     plateau=np.mean(p[(ff>.5e6)&(ff<1.5e6)]);col,ls=styles[treatment];ls=':' if nf==2**14 else ls
     ax.plot(ff/1000,10*np.log10(np.maximum(p/plateau,1e-30)),color=col,ls=ls,lw=.8,label=f'{treatment}, Tfft={nf/FS:.4g}s')
   if nf==4*SPEC:
    cached[treatment]=ps[2]
    for name,p in zip(['I','Q','complex'],ps):arr[f'{label}_{treatment}_{name}_PSD']=p
    arr[f'{label}_frequency_hz']=ff
  print(label,'FFT',nf,'done',flush=True)
 for ax,name in zip(axes,['I','Qeff','complex symmetric']):
  ax.set(title=label+' — '+name,xlim=(0,100),ylim=(-40,15),xlabel='|Frequency| [kHz]',ylabel='PSD / own plateau [dB]');ax.grid(alpha=.2);ax.legend(fontsize=6)
 # Absolute differences outside central kHz use smoothed periodograms, not unstable point ratios.
 sel=(ff>1000)&(ff<100000)
 centered=cached['global'];changes={}
 for treatment in ['none','spec']:
  changes[treatment]=float(np.sum(abs(cached[treatment][sel]-centered[sel]))/np.sum(centered[sel]))
 return dict(metrics=metrics,relative_L1_PSD_change_1_100kHz=changes)

def distributions(z,label,axraw,axac,fullrow=None):
 mu=z.mean();ac=float(np.mean(abs(z-mu)**2));sigma=np.sqrt(ac/2);nu=abs(mu)
 bins=np.linspace(0,8*sigma+nu,2049);amp=abs(z);h,_=np.histogram(amp,bins);edges=bins[1:];cdf=np.cumsum(h)/len(z);rice=stats.rice(b=nu/sigma,scale=sigma)
 d_raw=float(np.max(abs(cdf-rice.cdf(edges))))
 centered=abs(z-mu);h2,_=np.histogram(centered,bins);cdf2=np.cumsum(h2)/len(z);ray=stats.rayleigh(scale=sigma);d_ac=float(np.max(abs(cdf2-ray.cdf(edges))))
 centers=(bins[:-1]+bins[1:])/2;axraw.stairs(h/len(z)/np.diff(bins)*sigma,bins/sigma,color=COLORS['data'],label='Raw amplitude');axraw.plot(centers/sigma,rice.pdf(centers)*sigma,color=COLORS['theory'],ls='--',label='Rice: measured offset and AC');axraw.set(xlabel='A / sigma_q',ylabel='Density',title=label+f': raw; nu/sigma={nu/sigma:.3g}',xlim=(0,7));axraw.legend(fontsize=7)
 cc=1-cdf2;valid=(cc>max(20/len(z),1e-7))&(cc<.9999)
 axac.plot(edges[valid]**2/ac,np.log(cc[valid]),color=COLORS['data'],label='Centered empirical CCDF');xx=np.linspace(0,15,100);axac.plot(xx,-xx,color=COLORS['theory'],ls='--',label='Rayleigh prediction');axac.set(title=label+': centered',xlabel='A² / AC²',ylabel='log P(amplitude > A)',xlim=(0,15),ylim=(-16,0));axac.legend(fontsize=7)
 vi=float(np.var(z.real));vq=float(np.var(z.imag));cov=float(np.mean((z.real-mu.real)*(z.imag-mu.imag)))
 return dict(samples=len(z),mu_I_ADC_V=float(mu.real),mu_Qeff_ADC_V=float(mu.imag),DC2_ADC_V2=float(nu**2),AC2_ADC_V2=ac,sigma_q_ADC_V=float(sigma),nu_over_sigma=float(nu/sigma),raw_Rice_max_binned_CDF_distance=d_raw,centered_Rayleigh_max_binned_CDF_distance=d_ac,pseudo_covariance_ratio=float(abs(complex(vi-vq,2*cov))/(vi+vq)),var_I_ADC_V2=vi,var_Qeff_ADC_V2=vq,cov_IQ_ADC_V2=cov,mean_deviation_from_fullrun_ADC_V=float(abs(mu-complex(float(fullrow['mean_I_ADC_V']),float(fullrow['mean_Qeff_ADC_V'])))) if fullrow else None,method='No distribution fit: nu=abs(mean interval z),sigma²=AC²/2; binned CDF discrepancy, no iid p-value',tail_limit='CCDF shown only with >=20 observed expected-count resolution; no extreme-tail significance')

for run in selected:
 raw=Path('/home/mazzitel/flash-data/data/LNF')/f'run{run:05d}.mid.gz';reader=midas.file_reader.MidasFile(str(raw),use_numpy=True);parts=[]
 for ev in reader:
  if ev.header.is_midas_internal_event() or 'SPEC' not in ev.banks:continue
  parts.append(np.asarray(ev.banks['SPEC'].data,dtype=np.uint16).view(np.int16).reshape(-1,8)[:,:6].copy())
  if len(parts)==16:break
 reader.file.close();x=np.concatenate(parts);del parts;assert len(x)==16*SPEC
 fig,axes=plt.subplots(3,3,figsize=(15,10));fig2,axes2=plt.subplots(3,2,figsize=(11,11));fig3,axes3=plt.subplots(3,2,figsize=(12,10));rr={}
 for mi,mode in enumerate(MODES):
  row=next(r for r in long if int(r['run'])==run and r['mode']==mode);scale=2*float(row['physical_ADC_peak_V'])/65535
  z=(x[:,2*mi].astype(float)-1j*x[:,2*mi+1])*scale;label=f'run{run}_{mode}'
  shape=shape_analysis(z,label,axes[mi]);dist=distributions(z,label,*axes2[mi],fullrow=row)
  stability=mean_variance(z,[128,512,2048,8192,32768,131072,524288,SPEC,2*SPEC]);sm=z.reshape(-1,SPEC).mean(axis=1)
  axes3[mi,0].plot((np.arange(len(sm))+.5)*SPEC/FS,sm.real*1e3,color=COLORS['I'],label='I');axes3[mi,0].plot((np.arange(len(sm))+.5)*SPEC/FS,sm.imag*1e3,color=COLORS['Q'],label='Qeff');axes3[mi,0].axhline(float(row['mean_I_ADC_V'])*1e3,color=COLORS['I'],ls=':');axes3[mi,0].axhline(float(row['mean_Qeff_ADC_V'])*1e3,color=COLORS['Q'],ls=':');axes3[mi,0].set(title=label+' SPEC means; dotted=full-run',xlabel='Time in interval [s]',ylabel='Mean [mV ADC]');axes3[mi,0].legend(fontsize=7)
  t=np.array([r['time_s'] for r in stability]);v=np.array([r['variance_means_v2'] for r in stability]);prediction=np.array([r['PSD_prediction_v2'] for r in stability]);resolved=np.array([r['PSD_resolves_boxcar'] for r in stability]);ax=axes3[mi,1];ax.loglog(t,v,'o-',color=COLORS['data'],label='Variance of block means');ax.loglog(t,[r['white_prediction_v2'] for r in stability],':',color='#777777',label='AC² / block samples');ax.loglog(t,prediction,'--',color=COLORS['toy'],label='Welch-PSD prediction');ax.scatter(t[~resolved],prediction[~resolved],marker='x',color=COLORS['fit'],label='PSD LF unresolved');ax.set(title=label,xlabel='Integration time [s]',ylabel='Variance [V² ADC]');ax.legend(fontsize=6)
  # Full-run Rice check reuses saved amplitude histogram and full-run v2 moments.
  with h5py.File(INPUT/f'run{run:05d}_noise_v2.h5') as h:
   fac=float(row['voltage_correction']);e=h['arrays/amplitude_edges_v'][:]*fac;counts=h[f'arrays/global_{mode}_amp'][:];total=counts.sum();assert total==int(row['samples']);sig=np.sqrt(float(row['AC2_ADC_V2'])/2);nu=float(row['DC_abs_ADC_V']);pred=stats.rice(b=nu/sig,scale=sig).cdf(e[1:]);emp=np.cumsum(counts)/total
   fullrice=dict(samples=int(total),sigma_q_ADC_V=float(sig),nu_ADC_V=nu,max_binned_CDF_distance=float(np.max(abs(emp-pred))),source='Existing full-run global amplitude histogram, v2 DC and AC; no raw reread',no_fit=True)
  rr[mode]=dict(shape=shape,distribution=dist,fullrun_Rice=fullrice,mean_stability=stability,SPEC_mean_I_ADC_V=sm.real.tolist(),SPEC_mean_Qeff_ADC_V=sm.imag.tolist())
  allrows.extend(dict(run=run,mode=mode,**m) for m in shape['metrics']);print('Finished',label,flush=True);del z;gc.collect()
 for fg,name in [(fig,'PSD_centering'),(fig2,'Rice_Rayleigh'),(fig3,'DC_stability')]:fg.tight_layout();fg.savefig(OUT/f'run{run}_{name}.png',dpi=160);plt.close(fg)
 report['runs'][str(run)]=rr;np.savez_compressed(OUT/f'run{run}_spectra.npz',**arr);arr={};(OUT/'interval_results.json').write_text(json.dumps(report,indent=2));del x;gc.collect()
# Synthetic controls: same number of samples and exact processing; offset after HP.
rng=np.random.default_rng(20261116);n=16*SPEC;offset=.001+.002j
white=.02*(rng.standard_normal(n+65536)+1j*rng.standard_normal(n+65536))
sos=signal.butter(1,12500,fs=FS,btype='highpass',output='sos');hp=signal.sosfilt(sos,white)[65536:]+offset;white=white[65536:]+offset
fig,axes=plt.subplots(2,3,figsize=(15,7));fig2,axes2=plt.subplots(2,2,figsize=(11,7))
for j,(label,z) in enumerate([('white_constant_offset',white),('highpass_constant_offset',hp)]):
 report['synthetic'][label]=dict(shape=shape_analysis(z,label,axes[j]),distribution=distributions(z,label,*axes2[j]),mean_stability=mean_variance(z,[128,512,2048,8192,32768,131072,524288,SPEC,2*SPEC]))
for fg,name in [(fig,'synthetic_PSD_centering'),(fig2,'synthetic_Rice_Rayleigh')]:fg.tight_layout();fg.savefig(OUT/(name+'.png'),dpi=160);plt.close(fg)
np.savez_compressed(OUT/'synthetic_spectra.npz',**arr)
keys=sorted(set().union(*(r.keys() for r in allrows)))
with (OUT/'notch_metrics.csv').open('w') as stream:
 writer=csv.DictWriter(stream,keys);writer.writeheader();writer.writerows(allrows)
report.update(status='complete',wall_s=time.perf_counter()-start,raw_SPEC_read_per_run=16,samples_per_run_interval=16*SPEC,synthetic_model='Proper complex white Gaussian sigmaq=0.02 V, offset0.001+0.002j V; alternative causal first-order HP12.5kHz then same offset; warmup65536 discarded',limitations=['Only first3.3554432s of4runs; not a full-run DC stationarity test','SPEC means retained only as diagnostic; original v2 full-run centering unchanged','At long integration times finite Welch resolution cannot predict mean variance reliably; crosses mark unresolved values','Rice/Rayleigh require proper isotropic stationary Gaussian quadratures; measured anisotropy reported','No iid p-values: temporal correlations, quantization, drift and parameter estimation matter'],source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('common.py')]})
(OUT/'interval_results.json').write_text(json.dumps(report,indent=2));print('COMPLETE',flush=True)
