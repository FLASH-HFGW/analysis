#!/usr/bin/env python3
"""PSD and linear covariance of one continuous 5-SPEC stream (no SPEC reset)."""
from pathlib import Path
import json
import numpy as np
import midas.file_reader
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
OUT=Path('/home/mazzitel/HFGW/analysis-work/Run2/analysis/noise_continuous/periodicity_run680');OUT.mkdir(parents=True,exist_ok=True)
fs=5e6;limit=5;maxlag=200
modes={'TM010':(0,1),'TM011':(2,3),'TM012':(4,5)}
blocks=[]
reader=midas.file_reader.MidasFile('/home/mazzitel/flash-data/data/LNF/run00680.mid.gz',use_numpy=True)
try:
 for event in reader:
  if event.header.is_midas_internal_event() or 'SPEC' not in event.banks:continue
  blocks.append(np.asarray(event.banks['SPEC'].data,dtype=np.uint16).view(np.int16).reshape(-1,8).copy())
  if len(blocks)==limit:break
finally:
 close=getattr(reader,"close",None)
 if close is not None:close()
frames=np.concatenate(blocks);del blocks
n=len(frames);window=np.hanning(n);freq=np.fft.fftfreq(n,1/fs)
report={'input':'run00680.mid.gz','SPEC_blocks':limit,'continuous_samples':n,'duration_s':n/fs,'sampling_hz':fs,'periodogram_bin_hz':fs/n,
 'method':'single continuous stream across five SPEC blocks; one mean removed over stream; Hann periodogram; zero-padded linear covariance divided by N-lag; boundary pairs included',
 'scope':'first 1.048576 s of run 680; full-run phase is handled separately; no formal spectral-line significance test','modes':{}}
fig,axes=plt.subplots(3,3,figsize=(17,10),squeeze=False);arrays={}
for row,(mode,(ci,cq)) in enumerate(modes.items()):
 z=(frames[:,ci].astype(float)-1j*frames[:,cq].astype(float))*10/65535
 z-=z.mean();power=abs(np.fft.fft(z*window))**2/(fs*np.sum(window**2))
 cov=np.fft.ifft(abs(np.fft.fft(z,2*n))**2)[:maxlag+1]/(n-np.arange(maxlag+1));acf=cov/cov[0].real
 k=int(power.argmax());f=np.fft.fftshift(freq);power=np.fft.fftshift(power)
 factor=256;pf=power.reshape(-1,factor).mean(axis=1);ff=f.reshape(-1,factor).mean(axis=1)
 axes[row,0].plot(ff/1e6,10*np.log10(pf),lw=.8)
 axes[row,0].set(title=mode+' · continuous-stream IQ spectrum',xlabel='Baseband frequency [MHz]',ylabel='PSD [dB V²/Hz]')
 axes[row,1].plot(np.arange(1,maxlag+1)/fs*1e6,acf[1:].real,'.-',ms=2,lw=.8)
 axes[row,1].axhline(0,color='gray',lw=.6)
 axes[row,1].set(title=mode+' · linear autocorrelation',xlabel='Lag [μs]',ylabel='Re R[lag] / R[0]',xlim=(0,10));axes[row,1].grid(alpha=.2)
 trace=z[:250];tt=np.arange(len(trace))/fs*1e6
 axes[row,2].plot(tt,trace.real*1000,lw=.7,label='I');axes[row,2].plot(tt,trace.imag*1000,lw=.7,label='−Q',alpha=.7)
 axes[row,2].set(title=mode+' · first 10 μs',xlabel='Continuous time [μs]',ylabel='IQ [mV]',xlim=(0,10));axes[row,2].legend(fontsize=8)
 # Direct sum checks include SPEC boundaries and exclude circular FFT wraparound.
 for lag in (1,2,5,20,200):
  direct=np.sum(z[lag:]*np.conj(z[:-lag]))/(n-lag)
  np.testing.assert_allclose(cov[lag],direct,rtol=1e-10,atol=1e-13)
 report['modes'][mode]={'largest_periodogram_bin_hz':float(freq[k]),'largest_bin_fraction':float(power.max()/power.sum()),
  'normalized_covariance_real_lags_1_to_20':acf[1:21].real.tolist(),
  'abs_normalized_covariance_10us':float(abs(acf[50])), 'abs_normalized_covariance_40us':float(abs(acf[200]))}
 arrays[mode+'_periodogram_v2_per_hz']=power;arrays[mode+'_normalized_covariance']=acf
arrays['frequency_hz']=f;arrays['lag_s']=np.arange(maxlag+1)/fs
fig.suptitle('Run 680 · first 1.048576 s as ONE continuous stream · SPEC boundaries included')
fig.tight_layout();fig.savefig(OUT/'periodicity_diagnostic.png',dpi=160);plt.close(fig)
np.savez_compressed(OUT/'periodicity_diagnostic.npz',**arrays)
(OUT/'periodicity_diagnostic.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2),flush=True)
