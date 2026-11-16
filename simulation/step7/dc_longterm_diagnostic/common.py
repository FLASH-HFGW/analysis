"""Pure diagnostic estimators; never change the reconstruction or its products."""
from pathlib import Path
import numpy as np
from scipy import signal,stats
ROOT=Path('/home/mazzitel/HFGW');WORK=ROOT/'analysis-work/Run2'
INPUT=WORK/'reports/noise_fullrange_v2_20261109'
OUT=WORK/'simulation/step7/dc_longterm_diagnostic'
MODES=('TM010','TM011','TM012')
COLORS=dict(data='#007F86',toy='#7657A6',theory='#263952',fit='#e36e18',I='#43a1ed',Q='#ed812a')
FS=5e6;SPEC=2**20

def association(x,y,t):
 x,y,t=map(lambda a:np.asarray(a,float),(x,y,t));ok=np.isfinite(x)&np.isfinite(y)&np.isfinite(t);x,y,t=x[ok],y[ok],t[ok]
 def corr(a,b):
  if len(a)<5 or np.std(a)<1e-14 or np.std(b)<1e-14:return None
  return float(np.corrcoef(a,b)[0,1])
 out={'n':len(x),'pearson':corr(x,y)}
 if len(x)<8:return out
 x=(x-x.mean())/max(np.std(x),1e-100);y=(y-y.mean())/max(np.std(y),1e-100);t=(t-t.mean())/max(np.std(t),1e-100)
 for degree in (1,3):
  A=np.polynomial.polynomial.polyvander(t,degree)
  xr=x-A@np.linalg.lstsq(A,x,rcond=None)[0];yr=y-A@np.linalg.lstsq(A,y,rcond=None)[0]
  out[f'after_time_degree_{degree}']=corr(xr,yr)
 # Nearby consecutive observations only; no differencing across large gaps.
 dt=np.diff(t);positive=dt[dt>0];near=(dt>0)&(dt<3*np.median(positive)) if len(positive) else np.zeros(len(dt),bool)
 out['first_difference']=corr(np.diff(x)[near],np.diff(y)[near]);out['difference_pairs']=int(near.sum())
 return out

def spectral_matrix(z,nfft,treatment='global',spec=SPEC):
 """Welch nonoverlap, symmetric Hann. Centering precedes FFT windowing."""
 z=np.asarray(z);n=len(z)//nfft*nfft;z=z[:n]
 if treatment=='global':z=z-z.mean()
 elif treatment=='spec':
  if len(z)%spec:raise ValueError('Diagnostic SPEC centering needs full SPEC blocks')
  z=z.reshape(-1,spec);z=z-z.mean(axis=1,keepdims=True);z=z.reshape(-1)
 elif treatment!='none':raise ValueError(treatment)
 w=np.hanning(nfft);blocks=z.reshape(-1,nfft);I=np.fft.rfft(blocks.real*w,axis=1);Q=np.fft.rfft(blocks.imag*w,axis=1)
 # Here Q is Qeff=Im(z), unlike hardware-Q in earlier scripts.
 norm=FS*np.sum(w*w);pi=np.mean(abs(I)**2,axis=0)/norm;pq=np.mean(abs(Q)**2,axis=0)/norm;c=np.mean(I*Q.conj(),axis=0)/norm
 plus=pi+pq+2*c.imag;minus=pi+pq-2*c.imag
 return np.fft.rfftfreq(nfft,1/FS),pi,pq,plus,minus,c

def notch_metrics(f,p):
 """Describe symmetric notch by annular median/means, no gain adjustment."""
 plateau=np.mean(p[(f>.5e6)&(f<1.5e6)]);edges=np.arange(0,300001,1000);cent=(edges[:-1]+edges[1:])/2
 vals=np.array([np.mean(p[(f>=lo)&(f<hi)])/plateau if np.any((f>=lo)&(f<hi)) else np.nan for lo,hi in zip(edges[:-1],edges[1:])]);valid=np.isfinite(vals)
 if valid.sum()<10:return {'resolved':False}
 vals=np.interp(cent,cent[valid],vals[valid]);smooth=np.convolve(np.pad(vals,(2,2),mode='edge'),np.ones(5)/5,mode='valid');idx=np.argmin(smooth[cent<30000]);bottom=float(smooth[idx]);cross=np.flatnonzero((cent>=cent[idx])&(smooth>=(1+bottom)/2))
 return dict(resolved=True,min_smoothed_ratio=bottom,depth_db=float(-10*np.log10(max(bottom,1e-30))),full_half_deficit_width_hz=float(2*cent[cross[0]]) if len(cross) and bottom<.8 else None,minimum_abs_frequency_hz=float(cent[idx]),plateau_v2_hz=float(plateau))

def mean_variance(z,blocksizes):
 """Variance of nonoverlap means and PSD-predicted variance using Welch continuum.

Prediction uses independently shorter Welch segments (2**18) on globally centered
record, no per-segment detrending. Integrate bilateral PSD times exact discrete
boxcar squared response. Very low frequencies below Welch df remain unresolved.
 """
 z=z-z.mean();nps=2**18
 f,p=signal.welch(z,FS,window=np.hanning(nps),nperseg=nps,noverlap=0,detrend=False,return_onesided=False,scaling='density')
 rows=[]
 for size in blocksizes:
  count=len(z)//size
  if count<8:continue
  means=z[:count*size].reshape(count,size).mean(axis=1);measured=float(np.mean(abs(means-means.mean())**2))
  response=(np.sinc(f*size/FS)/np.sinc(f/FS))**2
  predicted=float(np.sum(p*response)*FS/nps)
  rows.append(dict(samples=size,time_s=size/FS,blocks=count,variance_means_v2=measured,white_prediction_v2=float(np.mean(abs(z)**2)/size),PSD_prediction_v2=predicted,PSD_df_hz=FS/nps,PSD_resolves_boxcar=bool(FS/nps<.2*FS/size)))
 return rows
