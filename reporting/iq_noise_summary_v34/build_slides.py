"""Exponential envelope of real correlation and function-level Python profiling."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import sys,json,shutil
import numpy as np
from scipy.signal import find_peaks
from scipy.optimize import least_squares
sys.path.insert(0,'/tmp/v18-python-deps');import pptx
sys.path.insert(0,'/home/mazzitel/HFGW/analysis/reporting');import slide_deck as sd
import matplotlib.pyplot as plt
R=Path('/home/mazzitel/HFGW');BASE=R/'analysis-work/Run2/reports/iq_noise_summary_v33';OUT=BASE.with_name('iq_noise_summary_v34');OUT.mkdir(exist_ok=True);A=OUT/'assets';D=OUT/'data';A.mkdir(exist_ok=True);shutil.copytree(BASE/'data',D,dirs_exist_ok=True)
deck=sd.Deck();deck.slides=json.loads((BASE/'slide_model.json').read_text());names=('TM010','TM011','TM012')
def textset(s,y,txt,size=None):
 for x in s['items']:
  if x['kind']=='text' and abs(x['y']-y)<1e-6:x['text']=sd.wrap(txt,x['w'],size or x['size']);x['size']=size or x['size']
def page(title,subtitle,source):
 temp=sd.Deck();s=temp.new(' ',subtitle,source);s['title']=title;x=next(v for v in s['items'] if v['kind']=='text' and v['y']==.38);x['text']=title
 while len(sd.wrap(title,x['w']*.88,x['size']).splitlines())>1:x['size']-=1
 return s
def table(s,heads,rows,widths,y=1.9,size=12,step=.48):
 for i,row in enumerate([heads]+rows):
  xx=.7
  for v,w in zip(row,widths):deck.text(s,xx,y if i==0 else y+.85+(i-1)*step,w-.08,.65 if i==0 else .47,str(v),size,i==0);xx+=w
fig,axs=plt.subplots(3,2,figsize=(13,7.2));fitout={};rows=[]
for i,mode in enumerate(names):
 a=np.load(D/f'{mode}_covariance_pair.npz');t=a['lag_s'][1:]*1e6
 for j,(key,pop,col) in enumerate((('toy_g1','toy','#7657A6'),('data20ms_g1','run680','#007F86'))):
  y=a[key][1:].real;v=abs(y);idx=np.unique(np.r_[0,find_peaks(v)[0]]);idx=idx[t[idx]<=5.000001];assert len(idx)>=4
  def model(p,tt):return p[2]+p[0]*np.exp(-tt/p[1])
  best=least_squares(lambda p:model(p,t[idx])-v[idx],[max(v),1.,min(.09,np.median(v[t>5]))],bounds=([0,.05,0],[2,30,.1]),max_nfev=3000)
  pred=model(best.x,t[idx]);err=v[idx]-pred;rmse=float(np.sqrt(np.mean(err**2)));r2=float(1-(err**2).sum()/((v[idx]-v[idx].mean())**2).sum());limited=bool(r2<.7 or best.x[1]>29.99)
  row=dict(A=float(best.x[0]),tau_us=float(best.x[1]),C=float(best.x[2]),RMSE=rmse,R2=r2,limited_fit=limited,fit_lag_us=t[idx].tolist(),peak_abs_real=v[idx].tolist(),model='E(t)=A exp(-t/tau)+C; fit local maxima of abs(Re g1), zero lag excluded;0<t<=5us',plot='Signed real correlation plus upper/lower exponential envelopes ±E; envelope is not a fit to oscillation phase')
  fitout[f'{mode}_{pop}']=row;rows.append([mode,pop,f"{row['tau_us']:.3f}"+('*' if limited else ''),f'{rmse:.4f}',f'{r2:.3f}',str(len(idx))])
  ax=axs[i,j];ax.axvspan(5,10,color='#8792a0',alpha=.09);ax.plot(t,y,'o-',ms=3,lw=.8,color=col,label='Re g₁');tt=np.linspace(t[idx][0],5,300);env=model(best.x,tt);ax.plot(tt,env,'--',lw=2,color='#ed7118',label='± exponential envelope');ax.plot(tt,-env,'--',lw=2,color='#ed7118');ax.scatter(t[idx],y[idx],s=17,facecolors='none',edgecolors='#ed7118',zorder=6)
  ax.set(title=mode+' · '+pop,xlabel='Lag [μs]',ylabel='Re g₁ (signed)',xlim=(0,10));ax.legend(fontsize=6.5,loc='upper right')
 low=min(ax.get_ylim()[0] for ax in axs[i]);high=max(ax.get_ylim()[1] for ax in axs[i])
 for ax in axs[i]:ax.set_ylim(low,high)
fig.tight_layout();path=A/'real_correlation_exponential_envelope.png';fig.savefig(path,dpi=190);plt.close(fig)
s=page('Temporal correlation: exponential decay of the oscillations','Dots: signed Re g₁ · orange curves: ±E(t), with E(t)=A exp(−t/τ)+C · envelope fit only through 5 μs','Same separate20ms toy/data windows and lag estimator; local maxima of |Re g1| fitted within0<t≤5us.')
deck.image(s,.45,1.7,9.1,4.85,path)
deck.text(s,9.8,2.,3.,.5,'Envelope τ [μs]',15,True)
for xx,ww,txt in ((9.8,1.,'Mode'),(10.9,.85,'Toy'),(11.9,.85,'Data')):deck.text(s,xx,2.85,ww,.45,txt,12,True)
for i,mode in enumerate(names):
 vals=[f"{fitout[f'{mode}_{pop}']['tau_us']:.3f}"+('*' if fitout[f'{mode}_{pop}']['limited_fit'] else '') for pop in ('toy','run680')]
 for xx,ww,txt in ((9.8,1.,mode),(10.9,.85,vals[0]),(11.9,.85,vals[1])):deck.text(s,xx,3.5+i*.6,ww,.45,txt,12)
deck.text(s,9.8,5.5,3.,.85,'τ describes the decay of oscillation amplitude.\n* Weak fit (R² < 0.7).',11)
deck.text(s,.75,6.55,11.9,.3,'Orange circles identify fitted extrema. The exponential envelope describes amplitude decay; it does not follow the sign changes.',10);deck.slides[21]=s
s=page('Exponential envelope of Re g₁: fitted decay times','Fit E(t)=A exp(−t/τ)+C to local maxima of |Re g₁|, within 0<t≤5 μs; zero lag excluded','Same covariance arrays as slide22; full parameters and selected lags saved in real_exponential_envelope_fits.json.')
table(s,['Mode','Population','τ [μs]','RMSE','R²','Peaks'],rows,[2.,2.4,2.1,2.,2.,1.4],y=1.85)
deck.text(s,.8,6.,11.7,.55,'* R²<0.7: a single exponential describes the peaks poorly. Values are descriptive envelope times; they replace the former damped-cosine times.',14);deck.slides[39]=s
(D/'real_exponential_envelope_fits.json').write_text(json.dumps(fitout,indent=2))
# Program-function profile, not worker-node hardware profiling.
summary=json.loads((D/'worker_profile/summary.json').read_text());sc=summary['instrumentation']['profile_3workers']['scopes'];t=summary['timings']['profile_3workers']['pass2']['wall_s'];fft=sc['band_fft']['wall_s']+sc['band_ifft']['wall_s']
s=page('Python program profile: which functions consume time?','50 SPEC of run680 · 3 workers · measured function times · cumulative rows overlap','Python cProfile main+all3 threads and explicit function wall/thread-CPU timers; local diagnostic run, not WN benchmarking.')
rows=[['FilteredBandChecks.update','Runs 27 filters serially per event',f"{sc['filtered_bands.serial']['wall_s']:.1f}",f"{100*sc['filtered_bands.serial']['wall_s']/t:.1f}%"],['BandFilter.process','Mixes IQ; FIR convolution; decimates',f"{sc['BandFilter.process']['wall_s']:.1f}",'Inside update'],['scipy.fft.fft / ifft','Forward and inverse Fourier transforms',f'{fft:.1f}','Inside FIR'],['FilterWorkspace.oscillator','Builds complex oscillator with np.exp',f"{sc['oscillator']['wall_s']:.1f}",'Inside FIR'],['RunStatistics.update','Histograms, threshold counts, phase stats',f"{sc['RunStatistics.update']['thread_cpu_s']:.1f} CPU",'Inside workers']]
table(s,['Python function','What it does','Time [s]','Share / scope'],rows,[3.65,4.15,1.8,2.3],y=1.85,size=12,step=.6)
deck.text(s,.8,5.95,11.7,.7,'Dominant cost: 27 full-rate FIR filters/event. Each uses FFT+IFFT before selecting 1/20 samples. In the control without cProfile, this serial bank still takes 89.0/113.7 s of pass2 (78%). Parent and child times must not be added.',14);deck.slides[43]=s
for ss in deck.slides:
 ss['footer']=ss.get('footer','IQ NOISE STUDY').replace('v33','v34')
 for x in ss['items']:
  if x['kind']=='image':
   src=Path(x['path']);dst=A/src.name
   if src!=dst:shutil.copy2(src,dst)
   x['path']=str(dst)
sd.export(deck,OUT,'v34',datetime.now(ZoneInfo('Europe/Rome')).strftime('%-d %B %Y'))
(OUT/'README.md').write_text('# v34\n\nSlide22 now shows signed real correlation and smooth exponential upper/lower envelopes fitted to extrema only through5us. Table decay times updated; old damped-cosine fit table replaced. Slide44 explicitly lists Python functions, operations and measured times. Other v33 slides preserved.\n')
print(json.dumps(fitout,indent=2))
