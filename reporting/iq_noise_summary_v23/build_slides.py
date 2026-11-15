"""Separate toy/run panels and matched observable/fit summaries, without population overlays."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import sys,json,copy,shutil,hashlib
import numpy as np,h5py
from scipy.optimize import minimize_scalar,brentq
from scipy.special import i0e,i1e
from scipy import signal
sys.path.insert(0,'/tmp/v18-python-deps')
import pptx
sys.path.insert(0,'/home/mazzitel/HFGW/analysis/reporting')
import slide_deck as sd
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
BASE=Path('/home/mazzitel/HFGW/analysis-work/Run2/reports/iq_noise_summary_v22')
OUT=BASE.with_name('iq_noise_summary_v23');OUT.mkdir(exist_ok=True);A=OUT/'assets';A.mkdir(exist_ok=True);D=OUT/'data';D.mkdir(exist_ok=True)
TOY=Path('/home/mazzitel/HFGW/analysis-work/Run2/simulation/toy_measured_response')
H5=Path('/home/mazzitel/HFGW/analysis-work/Run2/reports/noise_v2_development_20261109/run680_full_published/run00680_noise_v2.h5')
PERIOD=Path('/home/mazzitel/HFGW/analysis-work/Run2/staging/legacy-repository/autoreco/noise_continuous/periodicity_run680/periodicity_diagnostic.npz')
FFT=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/fft_by_run/run00680.npz')
RAW=Path('/home/mazzitel/flash-data/data/LNF/run00680.mid.gz')
old=json.loads((BASE/'slide_model.json').read_text());deck=sd.Deck();deck.slides=copy.deepcopy(old[:12])
shutil.copytree(BASE/'data',D/'previous_revision',dirs_exist_ok=True)
m=json.loads((TOY/'metrics.json').read_text());names=list(m['results']);toy={};obs={};results={};NFFT=16383;FS=5e6
COL={'toy':'#7657A6','data':'#007F86'}
with h5py.File(TOY/'toy_simulation.h5') as h:
 for mode in names:toy[mode]=h[mode+'/nominal_adc'][:]
# A consecutive raw window permits genuinely sampled I/Q traces and equal-length correlation estimators.
sys.path.insert(0,'/cvmfs/sft-flash.infn.it/package/midas/python');import midas.file_reader
reader=midas.file_reader.MidasFile(str(RAW),use_numpy=True)
odb=reader.get_bor_odb_dump().data;ranges=odb['Equipment']['NetBox']['Settings']['Channel_range_mV']
assert ranges[:6]==[2000]*6
for event in reader:
 if event.header.is_midas_internal_event() or 'SPEC' not in event.banks:continue
 frames=np.asarray(event.banks['SPEC'].data,dtype=np.uint16).view(np.int16).reshape(-1,8)
 for j,mode in enumerate(names):
  obs[mode]=(frames[:100000,2*j].astype(float)-1j*frames[:100000,2*j+1].astype(float))*float(np.float32(4/65535))
 break
assert all(len(x)==100000 for x in obs.values())
source='Sources: saved toy samples (20 ms); run 680 raw/scientific products with ODB ±2 V. Same 67.4 dB + measured kz hypothesis as slide 10.'
def page(title,subtitle,notes=''):
 s=deck.new(' ',subtitle,source,notes);s['title']=title
 header=next(x for x in s['items'] if x['kind']=='text' and x['y']==.38);header['text']=title
 while len(sd.wrap(title,header['w']*.88,header['size']).splitlines())>1:header['size']-=1
 s['footer']='TOY vs RUN 680 | SEPARATE POPULATIONS | DECK v23';return s

def save(fig,name):
 p=A/(name+'.png');fig.tight_layout();fig.savefig(p,dpi=180);plt.close(fig);return p

def picture(title,subtitle,path,caption='',notes=''):
 s=page(title,subtitle,notes);deck.image(s,.5,1.7,12.3,4.85,path)
 if caption:deck.text(s,.75,6.55,11.9,.25,caption,11)
 return s

def table(title,subtitle,heads,rows,note,notes=''):
 s=page(title,subtitle,notes);width=11.9/len(heads)
 for j,head in enumerate(heads):deck.text(s,.7+j*width,1.95,width-.12,.8,head,13,True)
 for i,row in enumerate(rows):
  for j,val in enumerate(row):deck.text(s,.7+j*width,3+i*.58,width-.12,.45,str(val),16)
 deck.text(s,.8,5.3,11.7,1.25,note,17)
 return s

def pairfig():
 fig,axs=plt.subplots(3,2,figsize=(12.8,7.2))
 for i,mode in enumerate(names):
  axs[i,0].set_title(mode+' · toy simulation',fontsize=11,color=COL['toy']);axs[i,1].set_title(mode+' · run 680',fontsize=11,color=COL['data'])
 return fig,axs

def binned_fit(edges,n):
 lo=edges[:-1];hi=edges[1:];init=np.sqrt(np.average(((lo+hi)/2)**2,weights=n)/2)
 def objective(logs):
  sig=np.exp(logs);a=lo**2/(2*sig**2);delta=(hi**2-lo**2)/(2*sig**2)
  return float(-np.sum(n*(-a+np.log(-np.expm1(-delta)))))
 fit=minimize_scalar(objective,bounds=(np.log(init/5),np.log(init*5)),method='bounded',options={'xatol':1e-12})
 assert fit.success
 return float(np.exp(fit.x))
# 13: empirical amplitude densities, separate panels; fits reported on next page, no model/data overlay.
fig,axs=pairfig()
with h5py.File(H5) as h:
 for i,mode in enumerate(names):
  group=h['modes/'+mode];mean=float(h['summary/modes/'+mode+'/mean_amplitude_v'][()])
  edges=(group['noise_edges_v'][:]+mean)*.4;edges[abs(edges)<1e-12]=0;counts=group['noise_counts'][:]
  if max(abs(toy[mode]))>=edges[-1]:
   oldlen=len(edges);step=edges[1]-edges[0];extra=np.arange(edges[-1]+step,max(abs(toy[mode]))+2*step,step);edges=np.r_[edges,extra];counts=np.r_[counts,np.zeros(len(extra),dtype=counts.dtype)]
  tcounts=np.histogram(abs(toy[mode]),edges)[0];assert tcounts.sum()==len(toy[mode]);assert counts.sum()==1048576000
  sig_t=binned_fit(edges,tcounts);sig_d=binned_fit(edges,counts)
  actual_total=float(h['dc_removed/modes/'+mode+'/total_rms_v'][()])*.4
  results[mode]=dict(amplitude=dict(toy_n=int(tcounts.sum()),data_n=int(counts.sum()),toy_fitted_sigma_adc_v=sig_t,data_fitted_sigma_adc_v=sig_d,toy_expected_sigma_adc_v=m['results'][mode]['sigma_adc_v'],toy_empirical_rms_adc_v=float(np.sqrt(np.mean(abs(toy[mode])**2))),data_raw_rms_adc_v=actual_total,data_ac_rms_adc_v=m['results'][mode]['observed_ac_rms_adc_v'],toy_data_sigma_pct=100*(sig_t/sig_d-1)))
  for ax,n,col in [(axs[i,0],tcounts,COL['toy']),(axs[i,1],counts,COL['data'])]:
   ax.stairs(n/n.sum()/np.diff(edges)/1000,edges*1000,color=col);ax.set_yscale('log');ax.set(xlabel='ADC amplitude [mV]',ylabel='Density [mV⁻¹]',xlim=(0,edges[-1]*1000),ylim=(1e-8,.1));ax.grid(alpha=.15)
  np.savez(D/(mode+'_amplitude_pair.npz'),edges_adc_v=edges,toy_counts=tcounts,data_counts=counts)
p=save(fig,'amplitude_separate');picture('Amplitude distributions: toy simulation and run 680','Separate empirical densities · identical axes per mode · no population superposition',p,'Toy: 100,000 samples (20 ms). Data: 1,048,576,000 samples (full run); unequal tail sensitivity.',notes='Each population is independently fitted with exact-bin Rayleigh likelihood and location fixed0. Fit curves are deliberately omitted from the panels; the next slide reports parameters. ADC scaling follows the ODB. Adjacent samples are correlated; no iid errors or tail-significance claim.')
rows=[]
for mode,r in results.items():
 a=r['amplitude'];rows.append([mode,f"{a['toy_expected_sigma_adc_v']*1e3:.3f}",f"{a['toy_fitted_sigma_adc_v']*1e3:.3f}",f"{a['data_fitted_sigma_adc_v']*1e3:.3f}",f"{a['toy_data_sigma_pct']:+.1f}%",f"{a['toy_empirical_rms_adc_v']*1e3:.3f}",f"{a['data_raw_rms_adc_v']*1e3:.3f}"])
table('Amplitude fits: parameters obtained from each population','Same binned Rayleigh MLE · location fixed at zero · no gain refitting', ['Mode','Expected toy\nσ [mV]','Fitted toy\nσ [mV]','Fitted data\nσ [mV]','Toy−data\nσ difference','Toy sample\nRMS [mV]','Data sample\nRMS [mV]'],rows,'Theoretical prediction, finite-sample toy fit and data fit are distinct. σ is the Rayleigh scale (quadrature std under circular Gaussian IQ), not std(A). Population sizes differ; no iid fit uncertainty is inferred.')
# Phase: separate empirical histograms, descriptive circular parameters.
def phase_summary(counts,edges):
 centers=(edges[:-1]+edges[1:])/2;v=np.sum(counts*np.exp(1j*centers))/counts.sum();R=float(abs(v))
 kappa=0. if R<1e-12 else float(brentq(lambda k:i1e(k)/i0e(k)-R,1e-12,100))
 return dict(n=int(counts.sum()),resultant=R,kappa_von_mises_mle=kappa,mean_phase_relative_rad=float(np.angle(v)))
fig,axs=pairfig()
with h5py.File(H5) as h:
 for i,mode in enumerate(names):
  edges=h['modes/'+mode+'/phase_edges_rad'][:];dc=h['modes/'+mode+'/phase_counts'][:];z=toy[mode];tc=np.histogram(np.angle(z[abs(z)>0]),edges)[0]
  pt=phase_summary(tc,edges);pd=phase_summary(dc,edges);results[mode]['phase']=dict(toy=pt,data=pd,uniform_expected_resultant=0.)
  ymax=max(np.max(tc/tc.sum()/np.diff(edges)),np.max(dc/dc.sum()/np.diff(edges)))*1.06
  # Coarsen only the displayed histogram; metrics use the original 1024 bins.
  group=8
  for ax,n,col in ((axs[i,0],tc,COL['toy']),(axs[i,1],dc,COL['data'])):
   coarse=n.reshape(-1,group).sum(axis=1);ee=edges[::group];ax.stairs(coarse/coarse.sum()/np.diff(ee),ee,color=col);ax.set(xlabel='Wrapped phase [rad]',ylabel='Density [rad⁻¹]',xlim=(-np.pi,np.pi),ylim=(0,.25));ax.grid(alpha=.15)
  np.savez(D/(mode+'_phase_pair.npz'),edges_rad=edges,toy_counts=tc,data_counts=dc)
p=save(fig,'phase_separate');picture('Phase distributions: toy simulation and run 680','Separate phase histograms · common density axes · uniform expectation = 0.15915 rad⁻¹',p,'Metrics use the original bins; display groups 8 bins. Zero-amplitude samples excluded.',notes='A constant phase-reference change rotates the mean angle but preserves resultant magnitude and fitted kappa. Absolute mean phases are therefore not compared. No overlay and no iid goodness-of-fit p-value.')
rows=[]
for mode,r in results.items():
 p=r['phase'];rows.append([mode,f"{p['toy']['resultant']:.5f}",f"{p['data']['resultant']:.5f}",f"{p['toy']['kappa_von_mises_mle']:.5f}",f"{p['data']['kappa_von_mises_mle']:.5f}"])
table('Phase: circular summary and independent fits','Von Mises fits summarize first-harmonic phase preference; they do not explain narrow angular features', ['Mode','Toy resultant\nR₁','Data resultant\nR₁','Toy fitted\nκ','Data fitted\nκ'],rows,'Uniform population: R₁ = 0 and κ = 0. R₁ = |mean exp(iφ)|; κ is the von Mises concentration. Finite toy samples give nonzero estimates. Mean phase depends on reference and is not compared.',notes='Both fits use histogram-midpoint weighted circular moments and solve I1(kappa)/I0(kappa)=R1. This is a descriptive fit, not a claim that the measured phase distribution is von Mises or that all phase structure is captured.')
# IQ: population comparison and normalized central-moment diagnostics.
def iq_metrics(counts,x,y,mean_exact=None,rms_exact=None):
 xc=(x[:-1]+x[1:])/2;yc=(y[:-1]+y[1:])/2;n=counts.sum();mx=np.sum(counts*xc[:,None])/n;my=np.sum(counts*yc[None,:])/n
 vx=float(np.sum(counts*(xc[:,None]-mx)**2)/n);vy=float(np.sum(counts*(yc[None,:]-my)**2)/n);cov=float(np.sum(counts*(xc[:,None]-mx)*(yc[None,:]-my))/n)
 return dict(variance_ratio_I_over_Q=vx/vy,pseudocovariance_ratio=float(np.hypot(vx-vy,2*cov)/(vx+vy)),mean_over_ac_rms=float(abs(mean_exact)/rms_exact) if mean_exact is not None else float(np.hypot(mx,my)/np.sqrt(vx+vy)))
fig,axs=plt.subplots(2,3,figsize=(12.8,6.4))
for i,mode in enumerate(names):
 axs[0,i].set_title(mode+' · toy simulation',fontsize=11,color=COL['toy']);axs[1,i].set_title(mode+' · run 680',fontsize=11,color=COL['data'])
with h5py.File(H5) as h:
 for i,mode in enumerate(names):
  g=h['modes/'+mode];xx=g['iq_i_edges_v'][:]*.4;yy=g['iq_q_edges_v'][:]*.4;counts=np.histogram2d(obs[mode].real,obs[mode].imag,bins=(xx,yy))[0]
  # Expand with empty edge bins if the toy has a wider cloud; preserve data bin alignment.
  def expand(edges,minimum,maximum):
   step=edges[1]-edges[0];left=max(0,int(np.ceil((edges[0]-minimum)/step)));right=max(0,int(np.ceil((maximum-edges[-1])/step)))
   return np.r_[edges[0]-np.arange(left,0,-1)*step,edges,edges[-1]+np.arange(1,right+1)*step],left,right
  xnew,lx,rx=expand(xx,toy[mode].real.min(),toy[mode].real.max());ynew,ly,ry=expand(yy,toy[mode].imag.min(),toy[mode].imag.max());counts=np.pad(counts,((lx,rx),(ly,ry)));xx=xnew;yy=ynew
  tc=np.histogram2d(toy[mode].real,toy[mode].imag,bins=(xx,yy))[0];assert tc.sum()==len(toy[mode])
  dcg=h['dc_removed/modes/'+mode];mu=obs[mode].mean();rms=float(np.sqrt(np.mean(abs(obs[mode]-mu)**2)));mut=toy[mode].mean();rmst=float(np.sqrt(np.mean(abs(toy[mode]-mut)**2)))
  results[mode]['iq']=dict(toy=iq_metrics(tc,xx,yy,mut,rmst),data=iq_metrics(counts,xx,yy,mu,rms),method='Quadrature variance and pseudocovariance from same bin-center estimator. Both means/AC RMS use exact moments of matched 20ms windows.')
  for ax,n in ((axs[0,i],tc),(axs[1,i],counts)):
   prob=n/n.sum();ax.pcolormesh(xx*1000,yy*1000,np.ma.masked_where(prob==0,prob).T,cmap='magma',norm=LogNorm(vmin=1e-6,vmax=.002));ax.set(xlabel='I [mV ADC]',ylabel='Signed Q [mV ADC]',xlim=(xx[0]*1000,xx[-1]*1000),ylim=(yy[0]*1000,yy[-1]*1000));ax.set_aspect('equal','box')
p=save(fig,'IQ_separate');picture('IQ populations: toy simulation and run 680','Toy above, run 680 below · matched 20 ms populations · same axes and color normalization',p,'100,000 samples per population; common bins. Equal sample sizes avoid unequal visibility of sparsely populated tails.')
rows=[]
for mode,r in results.items():
 q=r['iq'];rows.append([mode,f"{q['toy']['variance_ratio_I_over_Q']:.4f}",f"{q['data']['variance_ratio_I_over_Q']:.4f}",f"{q['toy']['pseudocovariance_ratio']:.4f}",f"{q['data']['pseudocovariance_ratio']:.4f}",f"{q['toy']['mean_over_ac_rms']:.4f}",f"{q['data']['mean_over_ac_rms']:.4f}"])
table('IQ diagnostics: balance, circularity and complex offset','Matched 20 ms populations · identical bin-center variance estimator · exact sample means', ['Mode','Toy var(I)\n/ var(Q)','Data var(I)\n/ var(Q)','Toy pseudo-\ncov. ratio','Data pseudo-\ncov. ratio','Toy |μ|\n/ RMS_AC','Data |μ|\n/ RMS_AC'],rows,'Circular centered Gaussian expectation: variance ratio 1, pseudocovariance ratio 0, complex mean 0. Variance/circularity use common histogram bins; offset/RMS uses exact moments of the two 20 ms windows.')
# Consecutive ADC samples: no resampling or fictitious time interpolation.
fig,axs=pairfig()
for i,mode in enumerate(names):
 limit=max(np.max(abs(toy[mode][:25].real)),np.max(abs(toy[mode][:25].imag)),np.max(abs(obs[mode][:25].real)),np.max(abs(obs[mode][:25].imag)))*1100
 for ax,z in ((axs[i,0],toy[mode]),(axs[i,1],obs[mode])):
  t=np.arange(25)/FS*1e6;ax.plot(t,z[:25].real*1000,'o-',ms=3,color='#0b65cc',label='I');ax.plot(t,z[:25].imag*1000,'o--',ms=3,mfc='white',color='#07877f',label='Signed Q');ax.set(xlabel='Time within displayed window [μs]',ylabel='ADC [mV]',ylim=(-limit,limit));ax.legend(fontsize=8)
p=save(fig,'samples_separate');picture('Time samples: toy simulation and run 680','Separate arbitrary 5 μs windows · 25 consecutive samples · 0.2 μs spacing',p,'Lines only join acquired/generated samples. Windows have no common physical phase or time alignment.')
# Spectra: independently averaged toy/data spectra, no overlay.
fig,axs=pairfig();window=np.hanning(NFFT);enbw=NFFT*np.sum(window**2)/window.sum()**2;df=FS/NFFT
with np.load(FFT) as archive:
 for i,mode in enumerate(names):
  f,psdt=signal.welch(toy[mode],fs=FS,window=window,nperseg=NFFT,noverlap=0,detrend='constant',return_onesided=False,scaling='density');order=np.argsort(f);f=f[order];psdt=psdt[order]
  psdd=archive[f'fft_amp_mode{i}_SPECs'].astype(float)*.16/(enbw*df)
  assert len(psdd)==len(psdt)
  # Match displayed smoothing in both columns; leave the final incomplete frequency group out of display only.
  group=32;stop=len(f)//group*group;ff=f[:stop].reshape(-1,group).mean(axis=1)
  tplot=psdt[:stop].reshape(-1,group).mean(axis=1);dplot=psdd[:stop].reshape(-1,group).mean(axis=1)
  all_db=np.r_[10*np.log10(tplot),10*np.log10(dplot)];lim=(np.percentile(all_db,1)-2,np.percentile(all_db,99)+2)
  for ax,pp,col in ((axs[i,0],tplot,COL['toy']),(axs[i,1],dplot,COL['data'])):ax.plot(ff/1e6,10*np.log10(pp),color=col,lw=.8);ax.set(xlabel='Complex IF [MHz]',ylabel='PSD [dBV²/Hz]',ylim=lim,xlim=(-2.5,2.5))
  pt=float(psdt.sum()*df);pd=float(psdd.sum()*df)
  centroid_t=float(np.sum(f*psdt)/np.sum(psdt));centroid_d=float(np.sum(f*psdd)/np.sum(psdd))
  results[mode]['spectrum']=dict(fft_samples=NFFT,fft_bin_hz=df,hann_ENBW_bins=float(enbw),toy_chunks=len(toy[mode])//NFFT,data_chunks=int(archive['n_fft_done'])*64,toy_PSD_RMS_adc_v=float(np.sqrt(pt)),data_PSD_RMS_adc_v=float(np.sqrt(pd)),toy_data_power_db=float(10*np.log10(pt/pd)),toy_spectral_centroid_hz=centroid_t,data_spectral_centroid_hz=centroid_d,IQ_convention='Same displayed sign as archived IQ+ FFT; Re/abs covariance and marginal metrics are invariant to conjugation.')
  np.savez(D/(mode+'_spectra_pair.npz'),frequency_hz=f,toy_psd_adc_v2_hz=psdt,data_psd_adc_v2_hz=psdd)
p=save(fig,'spectra_separate');picture('Power spectra: toy simulation and run 680','Separate averaged PSDs · same FFT length, Hann noise normalization and frequency smoothing',p,'Toy: 6 chunks. Data: 64,000 chunks. Unequal averaging explains different visual roughness.',notes='Historical archive drops one sample per16384 chunk: actual FFT length16383. Its frequency grid is reconstructed accordingly, and coherent-gain Hann normalization is converted to noise density using ENBW. Science V² scaled0.16 from validated ODB. No RF power inference is needed for this ADC-domain comparison.')
rows=[]
for mode,r in results.items():
 p=r['spectrum'];rows.append([mode,f"{p['toy_PSD_RMS_adc_v']*1000:.3f}",f"{p['data_PSD_RMS_adc_v']*1000:.3f}",f"{p['toy_data_power_db']:+.2f}",p['toy_chunks'],f"{p['data_chunks']:,}"])
table('Spectral summaries: same estimator and explicit averaging','Integrated PSD is compared in ADC units; no extra gain factor is fitted', ['Mode','Toy √∫PSD\n[mV ADC]','Data √∫PSD\n[mV ADC]','Toy/data\npower [dB]','Toy FFT\nchunks','Data FFT\nchunks'],rows,'FFT length 16,383; Δf = 305.194 Hz; Hann ENBW ≈ 1.5001 bins. Chunk-wise DC removal and finite-window weighting make spectral RMS slightly different from full-run time-domain RMS. No deterministic tone is inferred from spectral roughness.')
# Temporal covariance: equal-length raw windows, shared estimator, separate Re and modulus pages.
def covariance(z):
 z=z-z.mean();size=1<<(2*len(z)-1).bit_length();r=np.fft.ifft(abs(np.fft.fft(z,size))**2)[:51]/(len(z)-np.arange(51))
 for j in (1,10):np.testing.assert_allclose(r[j],np.vdot(z[:-j],z[j:])/(len(z)-j),rtol=1e-10,atol=1e-14)
 return r/r[0]
lag=np.arange(51)/FS;corr={}
with np.load(PERIOD) as ref:
 for mode in names:
  gt=covariance(toy[mode]);gd=covariance(obs[mode]);gr=ref[mode+'_normalized_covariance'][:51];corr[mode]=(gt,gd)
  results[mode]['coherence']=dict(scope='Matched first20ms windows,100000 samples each; one mean removed; unbiased N-lag covariance normalized at lag0. Full1.048576s data reference recorded separately.',toy_lag1_real=float(gt[1].real),data_lag1_real=float(gd[1].real),toy_lag1_abs=float(abs(gt[1])),data_lag1_abs=float(abs(gd[1])),data_reference1s_lag1_real=float(gr[1].real),data_reference1s_lag1_abs=float(abs(gr[1])),toy_data_Re_RMSE_0p2_to10us=float(np.sqrt(np.mean((gt[1:].real-gd[1:].real)**2))))
  np.savez(D/(mode+'_covariance_pair.npz'),lag_s=lag,toy_g1=gt,data20ms_g1=gd,data1sec_reference_g1=gr)
for name,part,label in [('real',np.real,'Re g₁'),('modulus',np.abs,'|g₁|')]:
 fig,axs=pairfig()
 for i,mode in enumerate(names):
  gt,gd=corr[mode];vals=np.r_[part(gt[1:]),part(gd[1:])];lo=min(0,float(vals.min())*1.15);hi=float(vals.max())*1.15
  if hi<=lo:hi=lo+.01
  for ax,g,col in ((axs[i,0],gt,COL['toy']),(axs[i,1],gd,COL['data'])):ax.plot(lag[1:]*1e6,part(g[1:]),'o-',ms=2.6,lw=.8,color=col);ax.axhline(0,color='#bbbbbb',lw=.5);ax.set(xlabel='Lag [μs]',ylabel=label,ylim=(lo,hi));ax.grid(alpha=.15)
 p=save(fig,'covariance_'+name+'_separate');picture('Temporal correlation: '+('signed real part' if name=='real' else 'complex magnitude'), 'Separate 20 ms populations · identical estimator and lag grid · 0.2 μs spacing',p, 'g₁(0)=1, omitted to resolve nonzero lags. '+('Re g₁ can be negative.' if name=='real' else '|g₁| is nonnegative by definition.'),notes='No single-exponential decay time is fitted to these oscillatory/nonmonotonic curves. The real part and magnitude are distinct observables. Scalar gain and ADC rescaling do not change normalized covariance.')
rows=[]
for mode,r in results.items():
 c=r['coherence'];rows.append([mode,f"{c['toy_lag1_real']:+.4f}",f"{c['data_lag1_real']:+.4f}",f"{c['toy_lag1_abs']:.4f}",f"{c['data_lag1_abs']:.4f}",f"{c['data_reference1s_lag1_abs']:.4f}",f"{c['toy_data_Re_RMSE_0p2_to10us']:.4f}"])
table('Temporal correlation: quantitative comparison','Sampled g₁ at 0.2 μs; full 1.048576 s run-window reference included', ['Mode','Toy\nRe g₁','Data 20 ms\nRe g₁','Toy\n|g₁|','Data 20 ms\n|g₁|','Data 1.05 s\n|g₁|','Re g₁ RMSE\n0.2–10 μs'],rows,'Matched windows isolate estimator/sample-size differences. The longer data window checks stability of the comparison. Oscillatory curves are compared at actual sampled lags; no artificial common coherence-time fit is imposed.')
s=page('Toy simulation versus run 680: what is reproduced?', 'Distribution shape, scale, phase preference and temporal structure are separate tests')
deck.bullets(s,.8,1.95,11.7,[
 'Amplitude: independent Rayleigh fits quantify the scale mismatch; the toy is broader for TM010 and closer for the other modes.',
 'Phase and IQ: compare circular preference, quadrature balance and complex offsets separately. A nearly Rayleigh amplitude does not ensure a uniform phase.',
 'Spectra and covariance: measured response improves the comparison, but residual structures remain. Scalar gain cannot repair normalized temporal correlations.',
 'The 67.4 dB + kz reference-plane assumption remains conditional. Agreement in some observables does not prove the tone injection node.',
 'Toy samples cover 20 ms. Full-run amplitude/phase and long-window data references are explicitly labeled; no iid p-values or rare-tail equivalence are claimed.'
],18,.2)
# Keep the DC-removal diagnostic, then the campaign/temperature section; do not imply the zero-offset toy tests data DC removal.
s=copy.deepcopy(old[20]);s['notes']+=' Data-only diagnostic: the present toy has no injected DC offset, so it does not calibrate this DC-removal comparison.';deck.slides.append(s)
deck.slides+=copy.deepcopy(old[22:])
# Copy referenced assets and retain consistent audience-facing headers/footers.
for s in deck.slides:
 s['footer']=s.get('footer','IQ NOISE STUDY').replace('v22','v23')
 for item in s['items']:
  if item['kind']=='image':
   path=Path(item['path']);dest=A/path.name
   if path!=dest:shutil.copy2(path,dest)
   item['path']=str(dest)
  if item['kind']=='text' and item['y']==.38:
   while len(sd.wrap(item['text'],item['w']*.88,item['size']).splitlines())>1:item['size']-=1
report=dict(methods=dict(amplitude='Independent exact-bin Rayleigh MLE, location0, common bin edges per mode. No population overlays.',phase='Histogram-based circular resultant; independent von Mises concentration MLE used as first-harmonic summary.',IQ='Matched20ms windows, same bin-center variance and pseudocovariance estimator; exact means/AC RMS.',spectrum='Same FFT length16383, Hann energy normalization; archive frequency descriptor corrected; toy6chunks/data64000chunks.',coherence='Matched20ms raw windows, same sample spacing and unbiased covariance estimator; additional1.05s reference.'),gain_hypothesis=m['assumption'],results=results,provenance={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (TOY/'metrics.json',TOY/'toy_simulation.h5',BASE/'slide_model.json',Path(__file__))})
(D/'toy_run680_comparison.json').write_text(json.dumps(report,indent=2))
assert len(deck.slides)==39,len(deck.slides)
sd.export(deck,OUT,'v23',datetime.now(ZoneInfo('Europe/Rome')).strftime('%-d %B %Y'))
(OUT/'README.md').write_text('# IQ noise summary v23\n\n39 slides. From slide13: separate toy/run680 empirical amplitude, phase, IQ, actual samples, spectra and signed/modulus covariance panels, with independent fits and quantitative tables. No toy/data population overlays. Matching scopes, averaging and estimator limits are explicit. The gain-plane hypothesis and ADC correction are retained from v22. Campaign/temperature relative-trend slides remain unchanged. Comparison arrays and fitted values are in data/toy_run680_comparison.json and paired NPZ files.\n')
print(json.dumps({mode:r['amplitude'] for mode,r in results.items()},indent=2))
