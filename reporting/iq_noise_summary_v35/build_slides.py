"""Preserve v21 run680 analysis; add matched toy comparison and explicit profile units."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import sys,json,shutil
import numpy as np,h5py
sys.path.insert(0,'/tmp/v18-python-deps');import pptx
sys.path.insert(0,'/home/mazzitel/HFGW/analysis/reporting');import slide_deck as sd
import matplotlib.pyplot as plt
R=Path('/home/mazzitel/HFGW');BASE=R/'analysis-work/Run2/reports/iq_noise_summary_v34';OUT=BASE.with_name('iq_noise_summary_v35');OUT.mkdir(exist_ok=True);A=OUT/'assets';D=OUT/'data';A.mkdir(exist_ok=True);shutil.copytree(BASE/'data',D,dirs_exist_ok=True)
Q=R/'analysis-work/Run2/diagnostics/v21_toy_comparison_20261115';shutil.copytree(Q,D/'v21_reference_comparison',dirs_exist_ok=True);report=json.loads((Q/'comparison.json').read_text());names=list(report['modes']);deck=sd.Deck();deck.slides=json.loads((BASE/'slide_model.json').read_text());colors={'toy':'#7657A6','data':'#007F86'}
def textset(s,y,txt,size=None):
 for x in s['items']:
  if x['kind']=='text' and abs(x['y']-y)<1e-6:x['text']=sd.wrap(txt,x['w'],size or x['size']);x['size']=size or x['size']
def page(title,subtitle,source):
 dd=sd.Deck();s=dd.new(' ',subtitle,source);s['title']=title;head=next(v for v in s['items'] if v['kind']=='text' and v['y']==.38);head['text']=title
 while len(sd.wrap(title,head['w']*.88,head['size']).splitlines())>1:head['size']-=1
 return s
def table(s,heads,rows,widths=None,y=1.9,size=12,step=.48):
 widths=widths or [11.9/len(heads)]*len(heads)
 for i,row in enumerate([heads]+rows):
  xx=.7
  for txt,w in zip(row,widths):deck.text(s,xx,y if i==0 else y+.85+(i-1)*step,w-.08,.65 if i==0 else .47,str(txt),size,i==0);xx+=w

def image(fig,name):
 fig.tight_layout();p=A/(name+'.png');fig.savefig(p,dpi=190);plt.close(fig);return p

def replace(s,p):
 for x in s['items']:
  if x['kind']=='image':x['path']=str(p)
def clean_tau(f):return 'n.r.' if f['tau_us']<.2 or f['r_squared_on_selected_peaks']<.7 else f"{f['tau_us']:.3f}"
# Original v21 full-stream periodogram and normalized covariance remain the measured reference.
fig,axs=plt.subplots(3,2,figsize=(13,7.2));arrays={m:np.load(Q/f'{m}_comparison.npz') for m in names}
for i,m in enumerate(names):
 a=arrays[m]
 for j,pop in enumerate(('toy','data')):
  axs[i,j].plot(a['frequency_hz']/1e6,10*np.log10(a[pop+'_psd_v2_hz']),color=colors[pop],lw=.45);axs[i,j].set(title=m+' · '+('run680 · original v21' if pop=='data' else 'toy'),xlabel='Baseband frequency [MHz] · I−jQ',ylabel='PSD [dBV²/Hz]',xlim=(-2.5,2.5))
 low=min(ax.get_ylim()[0] for ax in axs[i]);high=max(ax.get_ylim()[1] for ax in axs[i])
 for ax in axs[i]:ax.set_ylim(low,high)
p=image(fig,'spectra_original_v21_vs_toy');replace(deck.slides[19],p);textset(deck.slides[19],1.12,'Original run680 spectrum + same-estimator toy · 5 continuous SPEC = 1.048576 s each · display bins 244 Hz',13);textset(deck.slides[19],6.55,'v21 Hann full-stream periodogram retained: original 0.954 Hz bins averaged in groups of 256 for display. ADC correction only: PSD ×0.16.',10);deck.slides[19]['source']='Original v21 periodicity_diagnostic.npz, scientific ADC ±2V; frozen toy prefix in the same I−jQ convention. Provenance in data/v21_reference_comparison.'
s=page('Spectral comparison: original estimator retained','One full-stream periodogram per population · same sample count, Hann normalization and display bins','Original v21 spectrum rescaled by0.16 for ADC ±2V; same estimator applied to toy under67.4dB+kz hypothesis.')
rows=[]
for m,r in report['modes'].items():rows.append([m,f"{r['toy_PSD_rms_v']*1000:.3f}",f"{r['data_PSD_rms_v']*1000:.3f}",f"{20*np.log10(r['toy_PSD_rms_v']/r['data_PSD_rms_v']):+.2f}",'1.048576','244.14'])
table(s,['Mode','Toy PSD RMS\n[mV ADC]','Data PSD RMS\n[mV ADC]','Toy/data\npower [dB]','Duration\n[s]','Display bin\n[Hz]'],rows)
deck.text(s,.8,5.3,11.7,1.,'Measured PSD values are the original v21 arrays times the ADC power correction0.16; no spectral reanalysis or gain fit is applied to the data. The toy alone is processed with the identical original estimator. One mean is removed over the whole continuous stream.',16);deck.slides[20]=s
# Original signed upper-maximum fit; supplement modulus without replacing original observable.
fitrows=[];modrows=[]
for pageid,kind in ((21,'upper'),(22,'modulus')):
 fig,axs=plt.subplots(3,2,figsize=(13,7.2))
 for i,m in enumerate(names):
  a=arrays[m];lag=a['lag_s']*1e6
  for j,pop in enumerate(('toy','data')):
   g=a[pop+'_g1'];y=g.real if kind=='upper' else abs(g);r=report['modes'][m];ax=axs[i,j];ax.plot(lag[1:51],y[1:51],'o-',color=colors[pop],ms=2.4,lw=.7,label='Re g₁' if kind=='upper' else '|g₁|')
   if kind=='upper':
    f=r[pop+'_upper_fit'];tt=np.linspace(f['plot_range_us'][0],4,300);pred=f['offset']+f['amplitude']*np.exp(-tt/f['tau_us']);ax.plot(tt,pred,color='#e36e18',lw=1.8,label='Upper-maxima fit ≤4 μs');ax.scatter(f['peak_lag_us'],f['peak_covariance'],s=20,facecolors='none',edgecolors='#e36e18',zorder=6)
    if clean_tau(f)=='n.r.':ax.text(.98,.56,'Toy exponential not resolved',transform=ax.transAxes,ha='right',fontsize=6.5)
    f5=r[pop+'_upper_fit_5us'];fitrows.append([m,pop,clean_tau(f),f"{f['r_squared_on_selected_peaks']:.3f}",clean_tau(f5),f"{f5['r_squared_on_selected_peaks']:.3f}"])
   else:
    f=r['modulus_fits'][pop];tt=np.linspace(min(f['lag_us']),5,300);ax.plot(tt,f['C']+f['A']*np.exp(-tt/f['tau_us']),'--',color='#e36e18',lw=1.8,label='Magnitude envelope ≤5 μs');modrows.append([m,pop,f"{f['tau_us']:.3f}"+('*' if f['R2']<.7 else ''),f"{f['RMSE']:.4f}",f"{f['R2']:.3f}"])
   ax.set(title=m+' · '+('run680 · original v21' if pop=='data' else 'toy'),xlabel='Time separation [μs]',ylabel='Re R[k]/R[0]' if kind=='upper' else '|R[k]/R[0]|',xlim=(0,10));ax.axhline(0,color='#66768A',lw=.5);ax.legend(fontsize=6,loc='upper right')
  low=min(ax.get_ylim()[0] for ax in axs[i]);high=max(ax.get_ylim()[1] for ax in axs[i])
  for ax in axs[i]:ax.set_ylim(low,high)
 p=image(fig,'correlation_v21_'+kind)
 if kind=='upper':
  s=page('Temporal correlation: original run680 fit versus toy','Original v21 signed covariance and upper maxima retained · C+A exp(−lag/τ), with C free · primary fit0.3–4μs','Original v21 normalized covariance and fits unchanged; same five-SPEC estimator and fit applied to the frozen toy prefix.')
 else:s=page('Temporal correlation: complex magnitude comparison','Same original five-SPEC covariance · supplementary |g₁| envelope fit only through5μs','Magnitude of original normalized covariance and matched toy; supplemental fit does not replace the original signed-upper-maximum result.')
 deck.image(s,.45,1.7,9.1,4.85,p);deck.text(s,9.8,2.,3.,.5,'τ [μs] · '+('v21 method' if kind=='upper' else '|g₁| envelope'),14,True)
 for xx,ww,txt in ((9.8,1.,'Mode'),(10.9,.85,'Toy'),(11.9,.85,'Data')):deck.text(s,xx,2.85,ww,.45,txt,12,True)
 for i,m in enumerate(names):
  r=report['modes'][m]
  if kind=='upper':vals=[clean_tau(r[pop+'_upper_fit']) for pop in ('toy','data')]
  else:vals=[f"{r['modulus_fits'][pop]['tau_us']:.3f}"+('*' if r['modulus_fits'][pop]['R2']<.7 else '') for pop in ('toy','data')]
  for xx,ww,txt in ((9.8,1.,m),(10.9,.85,vals[0]),(11.9,.85,vals[1])):deck.text(s,xx,3.5+i*.6,ww,.45,txt,12)
 deck.text(s,9.8,5.45,3.,1.,'Data τ exactly reproduces v21.\nn.r.: exponential not resolved.\n5μs sensitivity in appendix.' if kind=='upper' else '* Weak single-exponential description (R²<0.7).\n5 SPEC =1.049s per population.',11)
 deck.text(s,.75,6.55,11.9,.3,'All signed upper maxima, including weak/negative ones; no absolute value and no C≥0 constraint. C is a finite-window baseline.' if kind=='upper' else 'Full lag range0–10μs retained; orange curve stops at5μs. Decay times are descriptive, not a full covariance model.',10);deck.slides[pageid]=s
s=page('Temporal correlation: same reference window and estimator','Run680 retains the original v21 values · toy uses the same 5,242,880-sample estimator','Exact original v21 covariance arrays; normalized covariance is invariant under the scalar ADC voltage correction.')
rows=[]
for m in names:
 a=arrays[m];dg=a['data_g1'];tg=a['toy_g1'];rows.append([m,f'{tg[1].real:.5f}',f'{dg[1].real:.5f}',f'{abs(tg[1]):.5f}',f'{abs(dg[1]):.5f}',f'{np.sqrt(np.mean((tg[1:51].real-dg[1:51].real)**2)):.5f}',f'{np.sqrt(np.mean((abs(tg[1:51])-abs(dg[1:51]))**2)):.5f}'])
table(s,['Mode','Toy Re g₁\nat0.2μs','Data Re g₁\nat0.2μs','Toy |g₁|\nat0.2μs','Data |g₁|\nat0.2μs','Re RMSE\n0.2–10μs','|g₁| RMSE\n0.2–10μs'],rows,size=11)
deck.text(s,.8,5.3,11.7,.9,'The measured covariance is not recomputed on a shorter sample. Full-run amplitude/phase and IQ-tail comparisons remain based on the complete209.7152s run and toy. These temporal/spectral diagnostics retain the original1.048576s window.',16);deck.slides[23]=s
s=page('Original v21 upper-maximum fits and5μs sensitivity','Primary0.3–4μs fit unchanged · extending to5μs is a separately labeled sensitivity check','fit_upper_envelope: all signed local maxima; C free, including negative. Same fitting function and arrays as original v21 for data.')
table(s,['Mode','Population','τ≤4μs','R²≤4μs','τ≤5μs','R²≤5μs'],fitrows,y=1.85)
deck.text(s,.8,6.,11.7,.6,'n.r.: poor or sub-sample exponential fit; raw fit parameters remain in data/. Original measured τ=0.926/1.419/1.385μs. No new gain or shape parameter is fitted to make the toy agree.',14);deck.slides[39]=s
s=page('Supplementary magnitude-envelope fits','|g₁| from the same original1.049s covariance · local-maxima fit≤5μs; separate observable from v21 signed upper maxima','Matched five-SPEC covariance; supplementary A exp(−lag/τ)+C magnitude-envelope fits.')
table(s,['Mode','Population','τ [μs]','RMSE','R²'],modrows,y=1.85)
deck.text(s,.8,6.,11.7,.6,'* R²<0.7: a single exponential describes the magnitude maxima poorly. These values do not replace the original v21 signed-upper-maximum decay times.',14);deck.slides[40]=s
# Bring IQ diagnostics into agreement with the full-run IQ plot, preserving the histogram estimator.
SIM=R/'analysis-work/Run2/simulation/toy_full_run680';tm=json.loads((SIM/'metrics.json').read_text())['results'];H5=R/'analysis-work/Run2/reports/noise_v2_development_20261109/run680_full_published/run00680_noise_v2.h5';iqrows=[]
with h5py.File(H5) as h:
 for m in names:
  vals={}
  for pop in ('toy','data'):
   a=np.load(D/f'full_iq_{pop}_{m}.npz');n=a['hist'];e=a['edges'];cc=(e[:-1]+e[1:])/2;cnt=float(n.sum());si=float((n.sum(axis=1)*cc).sum());sq=float((n.sum(axis=0)*cc).sum());sii=float((n.sum(axis=1)*cc**2).sum());sqq=float((n.sum(axis=0)*cc**2).sum());siq=float(np.sum(n*cc[:,None]*cc[None,:]));tail=a['tail'];out=(abs(tail.real)>e[-1])|(abs(tail.imag)>e[-1]);z=tail[out];cnt+=len(z);si+=z.real.sum();sq+=z.imag.sum();sii+=np.sum(z.real**2);sqq+=np.sum(z.imag**2);siq+=np.sum(z.real*z.imag);vi=sii/cnt-(si/cnt)**2;vq=sqq/cnt-(sq/cnt)**2;cov=siq/cnt-si*sq/cnt**2
   if pop=='toy':r=tm[m];ratio=np.hypot(r['mean_i_v'],r['mean_q_v'])/np.sqrt(r['rms_v']**2-r['mean_i_v']**2-r['mean_q_v']**2)
   else:g=h['dc_removed/modes/'+m];ratio=np.hypot(g['mean_i_v'][()],g['mean_q_v'][()])/g['ac_rms_v'][()]
   vals[pop]=(vi/vq,abs(complex(vi-vq,2*cov))/(vi+vq),ratio)
  iqrows.append([m]+[f'{vals[pop][k]:.4f}' for k in range(3) for pop in ('toy','data')])
s=page('IQ diagnostics: full-run balance, circularity and offset','Same full-run populations as slide17 · bin-center covariance estimator; exact complex offsets','All full_iq histograms plus any out-of-range tail sample; full-run exact means and RMS from frozen products.')
table(s,['Mode','Toy varI/varQ','Data varI/varQ','Toy pseudo-\ncov. ratio','Data pseudo-\ncov. ratio','Toy |μ|\n/RMS_AC','Data |μ|\n/RMS_AC'],iqrows,size=11)
deck.text(s,.8,5.3,11.7,.9,'Each population contains1,048,576,000 samples per mode. Full-run amplitude, phase and tail counts remain unchanged. Histogram bin-center estimates describe quadrature balance; exact full-run moments determine offset/RMS.',16);deck.slides[17]=s
textset(deck.slides[24],5.29,'Full run:209.7152s for amplitude, phase and IQ tails. Original v21 window:1.048576s for spectra and covariance; the toy is processed identically. The original run680 results are the reference.',18)
for i in (14,15):deck.slides[i]['source']='Complete run680 and toy:1,048,576,000 samples/mode; full-run amplitude/phase products and ADC ±2V normalization.'
# Profile timings are totals across50 SPEC; show average per SPEC explicitly.
summary=json.loads((D/'worker_profile/summary.json').read_text());sc=summary['instrumentation']['profile_3workers']['scopes'];fft=sc['band_fft']['wall_s']+sc['band_ifft']['wall_s'];rows=[]
for label,op,total,scope in [('FilteredBandChecks.update','All27 filters, all3 modes',sc['filtered_bands.serial']['wall_s'],'wall · parent'),('BandFilter.process','Mixing + FIR + decimation',sc['BandFilter.process']['wall_s'],'wall · nested'),('scipy.fft.fft / ifft','Fourier convolution',fft,'wall · nested'),('FilterWorkspace.oscillator','Complex np.exp oscillator',sc['oscillator']['wall_s'],'wall · nested'),('RunStatistics.update','Histograms, thresholds, phase',sc['RunStatistics.update']['thread_cpu_s'],'CPU · workers')]:rows.append([label,op,f'{total:.2f}',f'{total/50:.3f}',scope])
s=page('Python function profile: total time and time per SPEC','Totals measured on50 SPEC =10.48576s acquired ·1 SPEC =0.2097152s ·3 modes included','Local Python program profile with3 workers; main+all worker cProfile and wall/thread-CPU timers. These are not per-WN benchmark timings.')
table(s,['Python function','Operation','Total50 SPEC\n[s]','Average /SPEC\n[s]','Scope'],rows,widths=[3.35,3.55,1.55,1.65,1.8],y=1.85,size=11,step=.6)
deck.text(s,.8,5.95,11.7,.7,'84.4s is the total for50 SPEC, not one SPEC:1.69s/SPEC for all27 filters. FFT/IFFT and oscillator times are included in that total. Cumulative parent/child times must not be added.',14);deck.slides[43]=s
# Remove obsolete comparison values from active metadata; retain old diagnostic files as history only.
(D/'active_comparison.json').write_text(json.dumps(dict(reference='Original v21 run680 periodicity NPZ + upper-maximum fits, preserved exactly',comparison_source='v21_reference_comparison/comparison.json',primary_window_s=1.048576,primary_fit_us=[.3,4.],sensitivity_fit_us=[.3,5.],full_run_samples_per_mode=1048576000,ADC_volt_factor=.4,ADC_PSD_factor=.16,RF_gain_db=67.4,normalization_hypothesis='Extra36dB FET already included in kz; conditional, no new fitted correction',older_20ms_files='Archived historical diagnostics, not used in current spectral/covariance slides'),indent=2))
# Normalize prose spacing without touching scientific arrays or filesystem paths.
import re
def prose(txt):
 for old,new in [('run680','run 680'),('All27','All 27'),('all27','all 27'),('all3','all 3'),('for50','for 50'),('on50','on 50'),('Total50','Total 50'),('fit0.3','fit 0.3'),('primary0.3','primary 0.3'),('through5','through 5'),('fit≤','fit ≤'),('complete209','complete 209'),('original1.','original 1.'),('SPEC:1','SPEC: 1'),('selecting1/20','selecting 1/20')]:txt=txt.replace(old,new)
 txt=re.sub(r'(?<=\d)(?=(?:μs|ms|s|dB|Hz|V|SPEC)\b)',' ',txt)
 txt=re.sub(r'=(?=\d)','= ',txt)
 return txt
for slide in deck.slides:
 for key in ('subtitle','source'):slide[key]=prose(slide.get(key,''))
 for item in slide['items']:
  if item['kind']=='text':item['text']=prose(item['text'])
for ss in deck.slides:
 ss['footer']=ss.get('footer','IQ NOISE STUDY').replace('v34','v35')
 for x in ss['items']:
  if x['kind']=='image':
   src=Path(x['path']);dst=A/src.name
   if src!=dst:shutil.copy2(src,dst)
   x['path']=str(dst)
sd.export(deck,OUT,'v35',datetime.now(ZoneInfo('Europe/Rome')).strftime('%-d %B %Y'))
(OUT/'README.md').write_text('# v35\n\nRestores original v21 measured spectrum, covariance and signed upper-maximum fits; only established ADC dimensional rescaling applies. Adds same-five-SPEC toy with unchanged full-run Monte Carlo parameters and normalization hypothesis. Original measured tau values reproduced exactly. Preserves full-run amplitude/phase/IQ-tail comparisons, profiling and efficiencies. Main fit0.3–4us is preserved;5us sensitivity explicitly separate. Profile timings now label total50SPEC and average perSPEC. Active methods and provenance in data/active_comparison.json and data/v21_reference_comparison/. Old20ms diagnostics retained only as history.\n')
