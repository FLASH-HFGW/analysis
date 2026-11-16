"""Thesis-prescription toy:103.4dB, measured kz,30mK, ±5V digitization; no fitted gain."""
from pathlib import Path
import json,numpy as np
from scipy import constants
ROOT=Path('/home/mazzitel/HFGW');D=ROOT/'analysis-work/Run2/simulation/run620_comparison';D.mkdir(exist_ok=True)
cal=json.loads((ROOT/'analysis-work/Run2/diagnostics/normalization_audit_20261114/calibration_reconstruction.json').read_text());old=json.loads((ROOT/'analysis-work/Run2/simulation/toy_measured_response/metrics.json').read_text())
fs=50e6;N=1000000;f=np.fft.fftfreq(N,1/fs);df=fs/N;rows={}
for i,(mode,p) in enumerate(old['results'].items()):
 c=cal['curves'][mode];x=np.array([v['rf_hz'] for v in c])-cal['comparison'][mode]['rf_if_offset_hz'];y=np.array([v['kz_integrated'] for v in c]);idx=np.argsort(x);resp=np.interp(f,x[idx],y[idx],left=0,right=0)
 ki=2*np.pi*p['f0_hz']/p['q0'];kt=ki*(1+p['kappa1']+p['kappa2']);th=constants.h*p['f0_hz']/np.expm1(constants.h*p['f0_hz']/(constants.k*.030));Sc=th*ki**2*p['kappa2']/((kt/2)**2+(2*np.pi*(f-1e6))**2)
 psd=50*10**(103.4/10)*(Sc+constants.k*3.955)*resp**2
 rng=np.random.default_rng(20261115+i);z=np.fft.ifft(N*np.sqrt(psd*df)*(rng.normal(size=N)+1j*rng.normal(size=N))/np.sqrt(2))[::10];lsb=10/65535;qr=np.round(z.real/lsb);qi=np.round(z.imag/lsb);clip=(qr>32767)|(qr< -32768)|(qi>32767)|(qi< -32768);adc=(np.clip(qr,-32768,32767)+1j*np.clip(qi,-32768,32767))*lsb
 np.savez(D/(mode+'_thesis_toy.npz'),analog=z,adc=adc)
 rows[mode]=dict(analog_expected_rms_v=float(np.sqrt(psd.sum()*df)),analog_sample_rms_v=float(np.sqrt(np.mean(abs(z)**2))),digitized_rms_v=float(np.sqrt(np.mean(abs(adc)**2))),clipped_complex_sample_fraction=float(clip.mean()))
(D/'thesis_model.json').write_text(json.dumps(dict(temperature_K=.030,receiver_K=3.955,RF_gain_dB=103.4,ADC_peak_V=5,model='Thesis prescription, measured integrated-tone response. No 36dB subtraction. Response is an input, not independent validation. All three modes inherit the receiver temperature. No coherent tone added to thermal-noise model.',results=rows),indent=2))
print(rows)
