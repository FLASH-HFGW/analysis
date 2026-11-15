"""Threshold definitions, phase-reference audit, aligned spectra and correlation fits."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import sys,json,copy,shutil
import numpy as np,h5py
from scipy import signal
from scipy.optimize import least_squares
sys.path.insert(0,'/tmp/v18-python-deps');import pptx
sys.path.insert(0,'/home/mazzitel/HFGW/analysis/reporting');import slide_deck as sd
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.colors import LogNorm
R=Path('/home/mazzitel/HFGW');BASE=R/'analysis-work/Run2/reports/iq_noise_summary_v25';OUT=BASE.with_name('iq_noise_summary_v30');OUT.mkdir(exist_ok=True);A=OUT/'assets';A.mkdir(exist_ok=True);D=OUT/'data';D.mkdir(exist_ok=True)
shutil.copytree(BASE/'data',D,dirs_exist_ok=True);deck=sd.Deck();deck.slides=json.loads((BASE/'slide_model.json').read_text())
SIM=R/'analysis-work/Run2/simulation/toy_full_run680';meta=json.loads((SIM/'comparison.json').read_text());names=list(meta['results']);C={'toy':'#7657A6','data':'#007F86'};FS=5e6
H5=R/'analysis-work/Run2/reports/noise_v2_development_20261109/run680_full_published/run00680_noise_v2.h5'
fitfile=next((BASE/'data').rglob('rayleigh_fit_ADC_corrected.json'));datafits=json.loads(fitfile.read_text())['fits'];sigD={x['mode']:x['sigma_v'] for x in datafits};sigT={k:v['sigma_fit_v'] for k,v in meta['results'].items()}
muq=np.sqrt(np.pi/2);sdq=np.sqrt((4-np.pi)/2);ks=(3,5,7);radii={k:muq+k*sdq for k in ks};probs={k:float(np.exp(-radii[k]**2/2)) for k in ks}
def save(fig,name):
 p=A/(name+'.png');fig.tight_layout();fig.savefig(p,dpi=190);plt.close(fig);return p
def replace(s,p):
 for x in s['items']:
  if x['kind']=='image':x['path']=str(p)
def textset(s,y,t,size=None):
 for x in s['items']:
  if x['kind']=='text' and abs(x['y']-y)<1e-6:x['text']=sd.wrap(t,x['w'],size or x['size']);x['size']=size or x['size']
def page(title,sub,notes=''):
 d=sd.Deck();s=d.new(' ',sub,notes=notes);s['title']=title;header=next(x for x in s['items'] if x['kind']=='text' and x['y']==.38);header['text']=title
 while len(sd.wrap(title,header['w']*.88,header['size']).splitlines())>1:header['size']-=1
 s['footer']='MODEL / DATA AUDIT | v30';return s
def rowtable(s,headers,rows,y=2.,fontsize=14):
 w=11.9/len(headers)
 for j,t in enumerate(headers):deck.text(s,.7+j*w,y,w-.1,.7,t,fontsize,True)
 for i,row in enumerate(rows):
  for j,t in enumerate(row):deck.text(s,.7+j*w,y+1+i*.43,w-.1,.42,str(t),fontsize)
# Completed benchmark evidence, retaining the still-missing new HPC result explicitly.
jobs=json.loads((BASE/'data/four_job_timings.json').read_text());s=page('HPC / HTC: measured CPU demand and elapsed time','Run 680 · analysis only · hardware and affinity differ; this is not a matched-host speedup test')
rows=[['HPC · 1 CPU / 1 worker','72.2','71.5','0.991'],['HPC · 3 CPU / 3 workers','Awaiting output','—','—']]
for j in jobs:
 t=j['timings']['total'];rows.append([f"HTC {j['job']} · {j['cpus']} CPU / {j['workers']} worker",f"{t['wall_s']/60:.1f}",f"{t['cpu_s']/60:.1f}",f"{t['cpu_s']/t['wall_s']:.3f}"])
rowtable(s,['Job / configuration','Elapsed [min]','CPU [min]','Mean CPU cores'],rows,y=1.8,fontsize=13)
deck.text(s,.8,5.85,11.7,.75,'HTC 3451 and 3454 shared physical host tier2-wn004; requested CPUs differ. Job 3454 averaged only 1.15 CPU cores, not three. Hardware/CPU contention prevents attributing the elapsed-time ratio solely to parallelism.',15)
deck.slides[7]=s
# Full-run amplitude panels with own-population Rayleigh thresholds.
fig,axs=plt.subplots(3,2,figsize=(13,7.5));thresholds={}
with h5py.File(SIM/'toy_full_run680.h5') as toy,h5py.File(H5) as data:
 for i,mode in enumerate(names):
  te=toy[mode+'/amplitude_edges_v'][:];tc=toy[mode+'/amplitude_counts'][:];mean=float(data['summary/modes/'+mode+'/mean_amplitude_v'][()])*.4;de=data['modes/'+mode+'/noise_edges_v'][:]*.4+mean;dc=data['modes/'+mode+'/noise_counts'][:]
  xmax=max(te[np.flatnonzero(tc)[-1]+1],de[-1]);thresholds[mode]={}
  for j,(edges,counts,sig,col,label) in enumerate(((te,tc,sigT[mode],C['toy'],'toy'),(de,dc,sigD[mode],C['data'],'run680'))):
   ax=axs[i,j];ax.stairs(counts/counts.sum()/np.diff(edges)/1000,edges*1000,color=col);x=np.linspace(0,xmax,700);from scipy.stats import rayleigh
   ax.plot(x*1000,rayleigh(scale=sig).pdf(x)/1000,'--',color='#263952',lw=1)
   for k,color in zip(ks,['#888888','#d15b37','#222222']):ax.axvline(radii[k]*sig*1000,color=color,ls=':',lw=1,label=f'μR+{k}σA')
   ax.set(title=mode+' · '+label,xlabel='Amplitude [mV ADC]',ylabel='Density [mV⁻¹]',yscale='log',ylim=(1e-9,.1),xlim=(0,xmax*1000));ax.legend(fontsize=6.5)
   thresholds[mode][label]={str(k):float(radii[k]*sig) for k in ks}
p=save(fig,'amplitude_Rayleigh_thresholds');replace(deck.slides[12],p);textset(deck.slides[12],6.55,'Vertical lines: μR + k·stdR(A), k=3,5,7, computed from each population’s fitted Rayleigh scale.',10)
# Small probability table on14; both sigma conventions explicitly separated.
s=deck.slides[13];s['items']=[x for x in s['items'] if not(x['kind']=='text' and x['y']>=5.0)]
for x,t in zip((.8,2.6,5.6,9),('k','Threshold / σquadrature','P(A > μR+kσA)','P(A > kσquadrature)')):deck.text(s,x,4.95,3.0,.4,t,11,True)
for i,k in enumerate(ks):
 for x,t in zip((.8,2.6,5.6,9),(str(k),f'{radii[k]:.4f}',f'{probs[k]:.6g}',f'{np.exp(-k*k/2):.6g}')):deck.text(s,x,5.42+i*.3,3,.28,t,12)
deck.text(s,.8,6.45,11.7,.35,'Lines/circles use μR+kσA. μR=√(π/2)σq; σA=√[(4−π)/2]σq. These are Rayleigh tails, not Gaussian significances.',11)
# Raw sample reference and matched-window spectra.
sys.path.insert(0,'/cvmfs/sft-flash.infn.it/package/midas/python');import midas.file_reader
reader=midas.file_reader.MidasFile('/home/mazzitel/flash-data/data/LNF/run00680.mid.gz',use_numpy=True)
for event in reader:
 if event.header.is_midas_internal_event() or 'SPEC' not in event.banks:continue
 frames=np.asarray(event.banks['SPEC'].data,dtype=np.uint16).view(np.int16).reshape(-1,8);break
obs={};phi0={};toy20={}
with h5py.File(SIM/'toy_full_run680.h5') as h:
 for i,mode in enumerate(names):
  z=(frames[:100000,2*i].astype(float)-1j*frames[:100000,2*i+1].astype(float))*(4/65535);obs[mode]=z;phi0[mode]=float(np.angle(z[np.flatnonzero(abs(z)>0)[0]]));toy20[mode]=h[mode+'/first_100000_adc_v'][:]
# Phase histograms: rotate toy axis to exactly the data's first-sample reference.
fig,axs=plt.subplots(3,2,figsize=(13,7.2));phase_diagnostic={}
with h5py.File(SIM/'toy_full_run680.h5') as t,h5py.File(H5) as d:
 for i,mode in enumerate(names):
  e=t[mode+'/phase_edges_rad'][:];cent=(e[:-1]+e[1:])/2;step=e[1]-e[0];tc=t[mode+'/phase_counts'][:];dc=d['modes/'+mode+'/phase_counts'][:]
  shifted=(cent-phi0[mode]+np.pi)%(2*np.pi)-np.pi;order=np.argsort(shifted)
  axs[i,0].stairs(tc[order]/tc.sum()/step,np.r_[shifted[order]-step/2,shifted[order][-1]+step/2],color=C['toy']);axs[i,1].stairs(dc/dc.sum()/step,e,color=C['data'])
  for j,label in enumerate(('toy','run680')):axs[i,j].set(title=mode+' · '+label,xlabel='Relative phase [rad, same reference]',ylabel='Density [rad⁻¹]',xlim=(-np.pi,np.pi),ylim=(0,.32))
  g=d['dc_removed/modes/'+mode];mu=abs(complex(g['mean_i_v'][()],g['mean_q_v'][()]));rms=float(g['ac_rms_v'][()]);pred=np.sqrt(np.pi)/2*mu/rms;measured=abs(np.sum(dc*np.exp(1j*cent))/dc.sum());phase_diagnostic[mode]=dict(data_reference_phase_rad=phi0[mode],DC_predicted_R1=float(pred),observed_R1=float(measured),peak_spacing_rad=float(np.pi/4))
p=save(fig,'phase_common_reference');replace(deck.slides[14],p);textset(deck.slides[14],1.12,'Full-run histograms · common phase origin: φ = arg(z) − phase of first valid data sample',13);textset(deck.slides[14],6.55,'Axis is angle, not frequency. Toy zero mean lacks broad DC modulation; narrow π/4-spaced peaks are compatible with integer IQ quantization.',10)
s=deck.slides[15];textset(s,5.3,'Small-offset prediction R₁≈(√π/2)|μ|/RMS_AC gives 0.0124 / 0.0517 / 0.0045, versus data 0.0119 / 0.0523 / 0.0046. This accounts for broad phase preference. Narrow angular peaks and LO frequency are separate questions.',16)
# IQ planes with circles, same matched populations and axes; full-run fits define radii.
fig,axs=plt.subplots(2,3,figsize=(12.8,6.4))
for i,mode in enumerate(names):
 limit=1.06*max(sigT[mode],sigD[mode])*radii[7];edges=np.linspace(-limit,limit,257)
 for j,(z,sig,label) in enumerate(((toy20[mode],sigT[mode],'toy'),(obs[mode],sigD[mode],'run680'))):
  n=np.histogram2d(z.real,z.imag,bins=(edges,edges))[0]/len(z);ax=axs[j,i];ax.pcolormesh(edges*1000,edges*1000,np.ma.masked_where(n==0,n).T,norm=LogNorm(vmin=1e-5,vmax=.003),cmap='magma')
  for k,color in zip(ks,['#888888','#d15b37','#222222']):ax.add_patch(Circle((0,0),radii[k]*sig*1000,fill=False,ls='--',lw=.8,color=color,label=f'{k}σA'))
  ax.set(title=mode+' · '+label,xlabel='I [mV ADC]',ylabel='Signed Q [mV ADC]',xlim=(-limit*1000,limit*1000),ylim=(-limit*1000,limit*1000));ax.set_aspect('equal');ax.legend(fontsize=6,loc='upper right')
p=save(fig,'IQ_Rayleigh_circles');replace(deck.slides[16],p);textset(deck.slides[16],6.55,'Radii: μR+3/5/7·σA from each full-run Rayleigh fit; centered at the amplitude origin. Clouds show matched 20 ms windows.',10)
# Same coarser spectral bin and same number of FFT averages in both panels.
fig,axs=plt.subplots(3,2,figsize=(12.8,7.2));spectral={};N=16383;w=np.hanning(N);group=64
for i,mode in enumerate(names):
 powers=[]
 for j,(z,label,col) in enumerate(((toy20[mode],'toy',C['toy']),(np.conj(obs[mode]),'run680',C['data']))):
  f,P=signal.welch(z,fs=FS,window=w,nperseg=N,noverlap=0,detrend='constant',return_onesided=False);order=np.argsort(f);f=f[order];P=P[order];stop=len(f)//group*group;ff=f[:stop].reshape(-1,group).mean(axis=1);pp=P[:stop].reshape(-1,group).mean(axis=1);powers.append(P)
  axs[i,j].plot(ff/1e6,10*np.log10(pp),color=col,lw=.8);axs[i,j].set(title=mode+' · '+label+' · 6 FFT averages',xlabel='Complex IF [MHz]',ylabel='PSD [dBV²/Hz]',xlim=(-2.5,2.5))
 low=min(axs[i,0].get_ylim()[0],axs[i,1].get_ylim()[0]);high=max(axs[i,0].get_ylim()[1],axs[i,1].get_ylim()[1])
 for ax in axs[i]:ax.set_ylim(low,high)
 spectral[mode]=dict(toy_rms_v=float(np.sqrt(powers[0].sum()*FS/N)),data_rms_v=float(np.sqrt(powers[1].sum()*FS/N)),bin_hz=FS/N*group,fft_averages=6)
p=save(fig,'spectra_matched_bins');replace(deck.slides[19],p);textset(deck.slides[19],1.12,'Matched 20 ms windows · same 16,383-sample FFT · 6 averages each · common 19.53 kHz display bins',13);textset(deck.slides[19],6.55,'Both panels use identical frequency bins, smoothing and averaging; common archived I+jQ spectral orientation.',10)
s=deck.slides[20]
for i,(mode,r) in enumerate(spectral.items()):
 vals=[mode,f"{r['toy_rms_v']*1000:.3f}",f"{r['data_rms_v']*1000:.3f}",f"{10*np.log10((r['toy_rms_v']/r['data_rms_v'])**2):+.2f}",'6','6']
 row=sorted([x for x in s['items'] if x['kind']=='text' and abs(x['y']-(3+i*.58))<1e-6],key=lambda x:x['x'])
 for x,v in zip(row,vals):x['text']=v
textset(s,5.3,'Matched 20 ms populations, 6 non-overlapping FFT chunks each. Displayed bin width = 64×305.194 Hz = 19.53 kHz. Hann noise normalization is identical. Remaining spectral differences are not caused by unequal binning or averaging.',16)
# Fit the signed correlation and a descriptive local-maxima envelope separately.
fitrows=[];fitout={}
for pageindex,kind in ((21,'real'),(22,'modulus')):
 fig,axs=plt.subplots(3,2,figsize=(12.8,7.2))
 for i,mode in enumerate(names):
  path=BASE/'data'/f'{mode}_covariance_pair.npz';a=np.load(path);t=a['lag_s'][1:]*1e6
  for j,(key,label,col) in enumerate((('toy_g1','toy',C['toy']),('data20ms_g1','run680',C['data']))):
   y=a[key][1:].real if kind=='real' else abs(a[key][1:]);idx=np.arange(len(t))
   if kind=='real':
    def fun(v):return v[4]+v[0]*np.exp(-t/v[1])*np.cos(2*np.pi*v[2]*t+v[3])
    best=None
    for freq in (.1,.5,1.,1.5,2.,2.4,2.49):
     for tau in (.4,1.5,4.):
      v=[min(.5,max(abs(y))*.9),tau,freq,0 if y[0]>=0 else 3.,0]
      sol=least_squares(lambda v:fun(v)-y,v,bounds=([0,.05,.001,-np.pi,-.1],[2,30,2.499,np.pi,.1]),max_nfev=1500)
      if best is None or np.sum(sol.fun**2)<np.sum(best.fun**2):best=sol
    pred=fun(best.x);parameters=dict(A=float(best.x[0]),tau_us=float(best.x[1]),frequency_MHz=float(best.x[2]),phase_rad=float(best.x[3]),C=float(best.x[4]));npar=5
   else:
    idx=np.unique(np.r_[0,signal.find_peaks(y)[0]]);idx=idx[t[idx]<=6]
    if len(idx)<4:idx=np.arange(len(t))
    def fun(v):return v[2]+v[0]*np.exp(-t/v[1])
    best=least_squares(lambda v:(fun(v)-y)[idx],[max(y),1.,max(0,np.median(y[-15:]))],bounds=([0,.05,0],[2,30,.1]),max_nfev=2000);pred=fun(best.x);parameters=dict(A=float(best.x[0]),tau_us=float(best.x[1]),C=float(best.x[2]));npar=3
   residual=(y-pred)[idx];rmse=float(np.sqrt(np.mean(residual**2)));den=np.sum((y[idx]-y[idx].mean())**2);r2=float(1-np.sum(residual**2)/den) if den else None
   limited=(r2 is not None and r2<.7) or (kind=='real' and (parameters['frequency_MHz']<.0011 or parameters['A']>1.999))
   fitout[f'{mode}_{label}_{kind}']=dict(limited_fit=limited,parameters=parameters,RMSE=rmse,R2=r2,points=len(idx),parameters_count=npar,method='Damped cosine+offset, all nonzero lags' if kind=='real' else 'Exponential+nonnegative floor, local maxima through6us; phenomenological envelope only',caution='No iid parameter error/p-value; oscillation frequency is not identified with LO; inspect residuals and bounds.')
   fitrows.append([mode,label,kind,f"{parameters['tau_us']:.3f}"+('*' if limited else ''),f"{parameters.get('frequency_MHz',float('nan')):.3f}" if kind=='real' else '—',f'{rmse:.4f}',f'{r2:.3f}' if r2 is not None else '—'])
   ax=axs[i,j];ax.plot(t,y,'o-',ms=2.5,lw=.7,color=col);ax.plot(t,pred,'--',color='#263952',lw=1);ax.set(title=mode+' · '+label,xlabel='Lag [μs]',ylabel='Re g₁' if kind=='real' else '|g₁|');ax.text(.98,.95,f"τ={parameters['tau_us']:.3f} μs\nRMSE={rmse:.4f}\nR²={r2:.3f}"+('\n* limited fit' if limited else ''),transform=ax.transAxes,ha='right',va='top',fontsize=7,bbox=dict(facecolor='white',alpha=.85))
  lim=(min(axs[i,0].get_ylim()[0],axs[i,1].get_ylim()[0]),max(axs[i,0].get_ylim()[1],axs[i,1].get_ylim()[1]))
  for ax in axs[i]:ax.set_ylim(lim)
 p=save(fig,'correlation_fit_'+kind);replace(deck.slides[pageindex],p);textset(deck.slides[pageindex],6.55,'Own-population fit: damped cosine + offset; zero lag excluded. Phenomenological parameters, not LO identification.' if kind=='real' else 'Own-population envelope fit: exponential + floor on local maxima (≤6 μs). R² refers to fitted maxima, not all samples.',10)
# Append detailed fit statistics and diagnostics without shifting requested slide numbers.
s=page('Correlation fits: parameters and descriptive statistics','Fits summarize the displayed curves; they are not a measurement of the LO or a universal coherence time')
rowtable(s,['Mode','Population','Fit','τ [μs]','f [MHz]','RMSE','R²'],fitrows[:6],y=1.85,fontsize=12)
deck.text(s,.8,6.0,11.7,.6,'Signed fits: A exp(−τlag/τfit) cos(2πfτlag+φ)+C. * Boundary or R²<0.7: parameters are not robust. No iid parameter errors/p-values; do not identify f with the LO.',14);deck.slides.append(s)
s=page('Magnitude-envelope fits: parameters and fit scope','Local-maxima fit is descriptive; the oscillatory magnitude need not follow one exponential')
rowtable(s,['Mode','Population','Fit','τ [μs]','f [MHz]','RMSE','R²'],fitrows[6:],y=1.85,fontsize=12);deck.text(s,.8,6.,11.7,.55,'Envelope: A exp(−τlag/τfit)+C. Fit scope and residuals must be inspected; * R²<0.7: weak envelope fit. A high peak-fit R² does not validate the full curve.',14);deck.slides.append(s)
s=page('Why TM010 still differs from the toy expectation','The population is now large enough to expose a model discrepancy; its physical cause is not uniquely identified')
deck.bullets(s,.8,1.9,11.7,['Toy/data RMS ratio≈1.335 for TM010: about33.5% in amplitude and78% in power. This is not explained by the former20ms sample-size mismatch.','The equivalent scale change would be about−2.51dB gain, or effective Tn≈2.22K at fixed response. These are diagnostic alternatives, not measured calibrations or corrections applied to the toy.','The common67.4dB reference-plane assumption brings TM011/TM012 closer; it does not guarantee mode-independent absolute calibration. Confirm tone injection, mode response and input-referred noise.','TM010 complex DC offset is only≈1.4% of AC RMS; the thermal-cavity term is tiny in this receiver-dominated model. Neither explains the33.5% scale gap by itself.','Correlation and spectral residuals remain: adjusting one scalar gain would not reproduce their normalized shape.'],18,.2);deck.slides.append(s)
s=page('Phase peaks: angle reference, quantization and offset','An angular histogram is not a frequency spectrum; it does not measure LO rotation')
deck.bullets(s,.8,1.9,11.7,['Data phase is relative to the first valid data sample; toy phase was absolute. The comparison now uses the same reference, without fitting a rotation to make peaks agree.','Integer ADC coordinates give repeated angles atan2(nQ,nI), including axes and diagonals. The strongest narrow peaks in both populations are spaced by roughlyπ/4, consistent with IQ quantization/binning.','Broad phase preference is different: the measured complex offset predicts the observed first-harmonic modulation; the centered toy has no corresponding DC term.','LO/IF rotation must be tested using time evolution and a resolved spectral line. Peaks versus phase angle, or a fitted covariance frequency alone, do not establish a coherent LO tone.'],18,.25);deck.slides.append(s)
s=page('Code profiling: measured local hotspots','cProfile · first20 SPEC · one worker · frozen benchmark sources; production-worker profiling remains to be done')
rowtable(s,['Operation','Cumulative time [s]','Scope'],[['FilteredBandChecks.update','36.117','63.5% of pass2'],['StreamingBand.process','34.778','Inside filtered-band update'],['FFT/ifft backend','25.216','Nested in filtered processing'],['Oscillator generation','7.373','Nested in filtered processing'],['process_second_mode','18.200','32.0% of pass2'],['Pass1 / pass2','8.019 / 56.918','Profiled local execution']],y=1.8,fontsize=13)
deck.text(s,.8,5.95,11.7,.7,'Cumulative times overlap: do not add parent/child rows. Filtered-band update remains outside the mode thread pool. Profile the actual workers before forecasting production speedup or rewriting kernels.',15);deck.slides.append(s)
for s in deck.slides:
 s['footer']=s.get('footer','IQ NOISE STUDY').replace('v25','v30')
 for x in s['items']:
  if x['kind']=='image':
   p=Path(x['path']);dest=A/p.name
   if p!=dest:shutil.copy2(p,dest)
   x['path']=str(dest)
  if x['kind']=='text' and x['y']==.38:
   while len(sd.wrap(x['text'],x['w']*.88,x['size']).splitlines())>1:x['size']-=1
(D/'Rayleigh_thresholds.json').write_text(json.dumps(dict(definition='T_k=Rayleigh mean + k*Rayleigh amplitude std; sigma quadrature is a distinct convention',tail_probabilities=probs,thresholds_adc_v=thresholds),indent=2));(D/'phase_diagnostics.json').write_text(json.dumps(phase_diagnostic,indent=2));(D/'correlation_fits.json').write_text(json.dumps(fitout,indent=2));(D/'spectral_matched_binning.json').write_text(json.dumps(spectral,indent=2))
sd.export(deck,OUT,'v30',datetime.now(ZoneInfo('Europe/Rome')).strftime('%-d %B %Y'))
(OUT/'README.md').write_text('# v30\n\nBased on the current39-slide v25. Rayleigh probabilities/thresholds, common phase origin, IQ radii, matched spectral binning and FFT averaging, descriptive correlation fits, profiling evidence, and TM010 diagnostics. The new HPC three-core output remains pending transfer; no time is fabricated. Other revisions26–29 are preserved.\n')
