"""Freeze v21 measured results and apply identical estimators to the frozen toy prefix."""
from pathlib import Path
import sys,json,hashlib
import numpy as np,h5py
from scipy.fft import fft,ifft,next_fast_len
from scipy.optimize import least_squares
from scipy.signal import find_peaks
R=Path('/home/mazzitel/HFGW');ROOT=R/'analysis-work/Run2';OUT=ROOT/'diagnostics/v21_toy_comparison_verified_IQ_20261115';OUT.mkdir(exist_ok=True,parents=True)
OLD=ROOT/'staging/legacy-repository/autoreco/noise_continuous/periodicity_run680';CAL=ROOT/'diagnostics/normalization_audit_20261114/calibration_reconstruction.json';PHY=ROOT/'simulation/step6/metrics.json';SIM=ROOT/'simulation/toy_full_run680'
sys.path.insert(0,str(R/'analysis/examples'));from fit_iq_correlation_decay import fit_upper_envelope
c=json.loads(CAL.read_text());p=json.loads(PHY.read_text())['mode_results'];oldfits=json.loads((OLD/'positive_envelope_fit.json').read_text())['modes'];fs=5e6;target=5*2**20;B=2**20;L=65537;M=next_fast_len(B+L-1);design=2**20;f=np.fft.fftfreq(design,1/fs);N=target;w=np.hanning(N);freq=np.fft.fftshift(np.fft.fftfreq(N,1/fs));group=256;ff=freq.reshape(-1,group).mean(axis=1);lag=np.arange(201)/fs;report={'data_reference':str(OLD),'samples':N,'duration_s':N/fs,'ADC_science_peak_V':2,'data_voltage_correction':.4,'data_PSD_correction':.16,'RF_gain_db':67.4,'toy_hypothesis':'Extra36dB FET included in kz; same frozen full-run toy, no gain refit','estimator':'Original v21: one complex mean, symmetric Hann full-stream periodogram, linear zero-padded covariance divided by N-lag','fit':'Original upper local maxima of signed Re(g1), C free including negative; primary0.3–4us unchanged;5us sensitivity separate','modes':{}}
with np.load(OLD/'periodicity_diagnostic.npz') as old,h5py.File(SIM/'toy_full_run680.h5') as orig:
 for index,(mode,phys) in enumerate(p.items()):
  pts=c['curves'][mode];offset=c['comparison'][mode]['rf_if_offset_hz'];xx=np.array([v['rf_hz']-offset for v in pts]);kk=np.array([v['kz_integrated'] for v in pts]);order=np.argsort(xx);xx=xx[order];kk=kk[order];S=np.zeros(design)
  for alias in (-1,0,1):
   af=f+alias*fs;resp=np.interp(af,xx,kk,left=0,right=0);ki=2*np.pi*phys['f0_hz']/phys['q0'];kt=ki*(1+phys['kappa1']+phys['kappa2']);th=6.62607015e-34*phys['f0_hz']/np.expm1(6.62607015e-34*phys['f0_hz']/(1.380649e-23*phys['temperature_k']))
   S+=50*10**(67.4/10)*(1.380649e-23*3.955+th*ki**2*phys['kappa2']/((kt/2)**2+(2*np.pi*(af-1e6))**2))*resp**2
  impulse=np.fft.fftshift(ifft(np.sqrt(fs*S)));fir=impulse[design//2-L//2:design//2+L//2+1];H=fft(fir,M);rng=np.random.default_rng(20261115+100*index)
  def white(n):return (rng.standard_normal(n)+1j*rng.standard_normal(n))/np.sqrt(2)
  history=white(L-1);parts=[]
  for block in range(5):
   inp=np.r_[history,white(B)];z=ifft(fft(inp,M)*H)[L-1:L-1+B];history=inp[-(L-1):].copy();step=4/65535;z=(np.clip(np.round(z.real/step),-32768,32767)+1j*np.clip(np.round(z.imag/step),-32768,32767))*step
   if block==0:assert np.array_equal(z[:100000],orig[mode+'/first_100000_adc_v'][:])
   parts.append(z)
  # Raw calibration confirms archived and frozen toy I-jQ convention; no conjugation needed.
  z=np.concatenate(parts);del parts;z-=z.mean();power=np.abs(np.fft.fft(z*w))**2/(fs*np.sum(w*w));power=np.fft.fftshift(power);toy_rms=float(np.sqrt(power.sum()*fs/N));toy_psd=power.reshape(-1,group).mean(axis=1);del power
  cov=np.fft.ifft(abs(np.fft.fft(z,2*N))**2)[:201]/(N-np.arange(201));tg=cov/cov[0].real
  for k in (1,2,5,20,200):np.testing.assert_allclose(cov[k],np.sum(z[k:]*np.conj(z[:-k]))/(N-k),rtol=1e-10,atol=1e-13)
  dg=old[mode+'_normalized_covariance'];dp=old[mode+'_periodogram_v2_per_hz']*.16;data_rms=float(np.sqrt(dp.sum()*fs/N));data_psd=dp.reshape(-1,group).mean(axis=1)
  fd=fit_upper_envelope(lag*1e6,dg.real);ft=fit_upper_envelope(lag*1e6,tg.real);assert abs(fd['tau_us']-oldfits[mode]['tau_us'])<1e-8
  fm={}
  for pop,g in [('data',dg),('toy',tg)]:
   q=abs(g);idx=np.unique(np.r_[1,find_peaks(q)[0]]);idx=idx[(idx>0)&(lag[idx]*1e6<=5.000001)];tt=lag[idx]*1e6;yy=q[idx]
   def model(v):return v[2]+v[0]*np.exp(-tt/v[1])
   sol=least_squares(lambda v:model(v)-yy,[max(yy),1.,min(.09,np.median(q[51:]))],bounds=([0,.05,0],[2,30,.1]));res=yy-model(sol.x);r2=1-float(np.sum(res**2)/np.sum((yy-yy.mean())**2));fm[pop]=dict(A=float(sol.x[0]),tau_us=float(sol.x[1]),C=float(sol.x[2]),R2=r2,RMSE=float(np.sqrt(np.mean(res**2))),lag_us=tt.tolist(),scope='Supplemental |g1| local-maxima fit through5us, not a replacement of original v21 signed upper-maximum fit')
  np.savez_compressed(OUT/f'{mode}_comparison.npz',lag_s=lag,data_g1=dg,toy_g1=tg,frequency_hz=ff,data_psd_v2_hz=data_psd,toy_psd_v2_hz=toy_psd)
  report['modes'][mode]=dict(data_upper_fit=fd,toy_upper_fit=ft,data_upper_fit_5us=fit_upper_envelope(lag*1e6,dg.real,window=(.3,5.)),toy_upper_fit_5us=fit_upper_envelope(lag*1e6,tg.real,window=(.3,5.)),modulus_fits=fm,data_PSD_rms_v=data_rms,toy_PSD_rms_v=toy_rms,measured_covariance_exactly_original=True,original_tau_us=oldfits[mode]['tau_us'])
  print(mode,'original tau reproduced',fd['tau_us'],'toy tau',ft['tau_us'],flush=True)
report['input_sha256']={str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in (OLD/'periodicity_diagnostic.npz',OLD/'positive_envelope_fit.json',CAL,PHY)};(OUT/'comparison.json').write_text(json.dumps(report,indent=2));print('COMPLETE',flush=True)
