"""Independent raw-data Parseval/FFT audit using thesis chunk conventions."""
from pathlib import Path
import sys,json
sys.path.insert(0,'/cvmfs/sft-flash.infn.it/package/midas/python')
import midas.file_reader
import numpy as np,h5py
from scipy import constants
OUT=Path('/home/mazzitel/HFGW/analysis-work/Run2/diagnostics/normalization_audit_20261114');OUT.mkdir(parents=True,exist_ok=True)
RAW=Path('/home/mazzitel/flash-data/data/LNF/run00680.mid.gz')
H5=Path('/home/mazzitel/HFGW/analysis-work/Run2/reports/noise_v2_development_20261109/run680_full_published/run00680_noise_v2.h5')
fs=5e6;N=16384;df=fs/N
modes=['TM010','TM011','TM012'];acc={m:dict(n=0,sum_i=0.,sum_q=0.,sum_sq=0.,sum_chunk_var=0.,sum_fft=0.,spectra=np.zeros(N),chunks=0) for m in modes}
seen=0
reader=midas.file_reader.MidasFile(str(RAW),use_numpy=True)
for event in reader:
 if event.header.is_midas_internal_event() or 'SPEC' not in event.banks:continue
 raw=np.asarray(event.banks['SPEC'].data,dtype=np.uint16)
 frames=raw.view(np.int16).reshape(-1,8)
 assert len(frames)==1048576
 for index,mode in enumerate(modes):
  a=acc[mode];i=frames[:,index*2].astype(float)*(10/65535);q=frames[:,index*2+1].astype(float)*(10/65535);z=i-1j*q
  a['n']+=len(z);a['sum_i']+=i.sum();a['sum_q']+=(-q).sum();a['sum_sq']+=float(np.vdot(z,z).real)
  chunks=z.reshape(-1,N);chunks=chunks-chunks.mean(axis=1,keepdims=True)
  # Thesis: FFT(I) - j FFT(Q) exactly equals FFT(I-jQ).
  F=np.fft.fft(chunks,axis=1);Fsep=np.fft.fft(chunks.real,axis=1)+1j*np.fft.fft(chunks.imag,axis=1)
  assert np.allclose(F,Fsep,rtol=1e-11,atol=1e-11)
  powbin=abs(F)**2/N**2
  timevar=np.mean(abs(chunks)**2,axis=1);freqvar=powbin.sum(axis=1)
  assert np.allclose(timevar,freqvar,rtol=1e-12,atol=1e-16)
  a['sum_chunk_var']+=float(timevar.sum());a['sum_fft']+=float(freqvar.sum());a['spectra']+=powbin.sum(axis=0);a['chunks']+=len(chunks)
 seen+=1
 if seen==5:break
close=getattr(reader,'close',None)
if close is not None:close()
f=np.fft.fftfreq(N,1/fs);rows=[]
with h5py.File(H5) as h:
 for mode in modes:
  a=acc[mode];spec=a.pop('spectra')/a['chunks'];raw_rms=np.sqrt(a['sum_sq']/a['n']);ac_rms=np.sqrt(a['sum_sq']/a['n']-(a['sum_i']/a['n'])**2-(a['sum_q']/a['n'])**2)
  production=float(h[f'dc_removed/modes/{mode}/ac_rms_v'][()])
  # One-sided location is not assumed: report both +/-1 MHz plateaus explicitly.
  plateau={}
  for sign in (-1,1):
   sel=abs(f-sign*1e6)<100e3
   plateau['plus' if sign==1 else 'minus']=float(np.mean(spec[sel]))
  reference=constants.k*3.985*df
  g_rf=10**(103.4/10);gnom=10**(143/10)
  estk={k:float(np.sqrt(v/(50*g_rf*reference))) for k,v in plateau.items()}
  np.savez(OUT/(mode+'_raw_fft_audit.npz'),frequency_hz=f,mean_squared_amplitude_v2_bin=spec,psd_adc_v2_hz=spec/df)
  rows.append(dict(mode=mode,n=a['n'],chunks=a['chunks'],raw_rms_v=float(raw_rms),ac_rms_v=float(ac_rms),production_full_run_ac_rms_v=production,relative_ac_rms_difference_first_five_vs_full=float(ac_rms/production-1),chunk_demeaned_power_v2=a['sum_chunk_var']/a['chunks'],fft_integrated_power_v2=a['sum_fft']/a['chunks'],plateau_mean_v2_bin=plateau,plateau_input_w_bin_using_nominal143db={k:v/(50*gnom) for k,v in plateau.items()},thesis_expected_kBT_w_bin=reference,effective_kz_required_if_thesis_noise_is_correct=estk))
r=dict(input=str(RAW),scope='First five SPEC, 5,242,880 complex samples/mode; compare independently recomputed first-window moments with full-run production, not identical scopes.',method='Signed int16; 10/65535 V/count; z=I-jQ; 64 chunks/event, FFT length16384, per-chunk DC removed, no window; mean |FFT(z)|²/N². Parseval checked for every chunk; complex FFT checked against separate-channel combination.',adc65535_vs65536_amplitude_ratio=65536/65535,fs_hz=fs,fft_n=N,bin_width_hz=df,rows=rows,warning='Required kz is a diagnostic inferred by assuming thesis noise; not a measured calibration. No kz curve digitized or applied.')
(OUT/'audit.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
