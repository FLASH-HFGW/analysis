from pathlib import Path
import json
import numpy as np
import midas.file_reader
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path('/home/mazzitel/HFGW/analysis');out=Path('/home/mazzitel/HFGW/analysis-work/Run2/analysis/noise_stationarity/run680_periodicity')
out.mkdir(parents=True,exist_ok=True)
fs=5e6;limit=5;maxlag=200
modes={'TM010':(0,1),'TM011':(2,3),'TM012':(4,5)}
states={m:{'power':None,'cov_sum':np.zeros(maxlag+1,dtype=complex),'peak_frequencies':[],'peak_bin_fractions':[],'trace':None} for m in modes}
reader=midas.file_reader.MidasFile('/home/mazzitel/flash-data/data/LNF/run00680.mid.gz',use_numpy=True)
seen=0
for event in reader:
 if event.header.is_midas_internal_event() or 'SPEC' not in event.banks:continue
 frames=np.asarray(event.banks['SPEC'].data,dtype=np.uint16).view(np.int16).reshape(-1,8)
 n=len(frames);window=np.hanning(n);freq=np.fft.fftfreq(n,1/fs)
 for mode,(ci,cq) in modes.items():
  st=states[mode];z=(frames[:,ci].astype(float)-1j*frames[:,cq].astype(float))*10/65535;z-=z.mean()
  if st['trace'] is None:st['trace']=z[:250].copy()
  spectrum=np.fft.fft(z*window);power=abs(spectrum)**2/(fs*np.sum(window**2))
  if st['power'] is None:st['power']=np.zeros_like(power)
  st['power']+=power
  k=int(power.argmax());st['peak_frequencies'].append(float(freq[k]));st['peak_bin_fractions'].append(float(power[k]/power.sum()))
  cov=np.fft.ifft(abs(np.fft.fft(z,2*n))**2)[:maxlag+1]
  st['cov_sum']+=cov/(n-np.arange(maxlag+1))
 seen+=1
 if seen>=limit:break
report={'input':'run00680.mid.gz','events_SPEC':seen,'sampling_hz':fs,'samples_per_event':n,'periodogram_bin_hz':fs/n,
        'method':'event-wise DC removal, Hann-windowed periodograms averaged; zero-padded linear covariance normalized at zero lag; no cross-event pairs',
        'scope':'first five SPEC events only; no formal line-significance test; no claim that weak/transient periodic components are absent','modes':{}}
fig,axes=plt.subplots(3,3,figsize=(17,10),squeeze=False)
arrays={}
for row,(mode,st) in enumerate(states.items()):
 power=np.fft.fftshift(st['power']/seen);f=np.fft.fftshift(freq);cov=st['cov_sum']/seen;acf=cov/cov[0].real
 # Average neighboring PSD bins for display only, retain full resolution in NPZ.
 factor=256;display=power.reshape(-1,factor).mean(axis=1);displayf=f.reshape(-1,factor).mean(axis=1)
 axes[row,0].plot(displayf/1e6,10*np.log10(display),lw=.8)
 axes[row,0].set(title=mode+' · averaged IQ spectrum',xlabel='Baseband frequency [MHz]',ylabel='PSD [dB V²/Hz]')
 axes[row,1].plot(np.arange(1,maxlag+1)/fs*1e6,acf[1:].real,'.-',ms=2,lw=.8,label='Re normalized covariance')
 axes[row,1].axhline(0,color='gray',lw=.6)
 axes[row,1].set(title=mode+' · short-lag autocorrelation (R[0]=1)',xlabel='Lag [μs]',ylabel='Re R[lag] / R[0]',xlim=(0,10));axes[row,1].grid(alpha=.2)
 trace=st['trace'];tt=np.arange(len(trace))/fs*1e6
 axes[row,2].plot(tt,trace.real*1000,lw=.7,label='I');axes[row,2].plot(tt,trace.imag*1000,lw=.7,label='−Q',alpha=.7)
 axes[row,2].set(title=mode+' · first 10 μs of event 0',xlabel='Time [μs]',ylabel='IQ [mV]',xlim=(0,10));axes[row,2].legend(fontsize=8)
 report['modes'][mode]={'largest_bin_frequency_hz_by_event':st['peak_frequencies'],
     'largest_bin_fraction_of_integrated_periodogram_by_event':st['peak_bin_fractions'],
     'normalized_covariance_real_lags_1_to_20':acf[1:21].real.tolist(),
     'normalized_covariance_abs_at_10us':float(abs(acf[50])),
     'normalized_covariance_abs_at_40us':float(abs(acf[200]))}
 arrays[mode+'_mean_periodogram_v2_per_hz']=power;arrays[mode+'_normalized_covariance']=acf
 arrays[mode+'_first_event_trace']=trace
arrays['frequency_hz']=f;arrays['lag_s']=np.arange(maxlag+1)/fs
fig.suptitle('Run 680 · first five SPEC events · IQ = I − jQ · spectrum and covariance test periodic structure')
fig.tight_layout();fig.savefig(out/'periodicity_diagnostic.png',dpi=160);plt.close(fig)
np.savez_compressed(out/'periodicity_diagnostic.npz',**arrays)
(out/'periodicity_diagnostic.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2),flush=True)
