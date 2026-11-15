from pathlib import Path
import sys,json,numpy as np
sys.path.insert(0,'/cvmfs/sft-flash.infn.it/package/midas/python');import midas.file_reader
P=Path('/home/mazzitel/HFGW/analysis-work/Run2/diagnostics/TM010_response_audit_20261115');fr=midas.file_reader.MidasFile('/home/mazzitel/flash-data/data/LNF/run00680.mid.gz',use_numpy=True);parts=[]
for ev in fr:
 if ev.header.is_midas_internal_event() or 'SPEC' not in ev.banks:continue
 parts.append(np.asarray(ev.banks['SPEC'].data,dtype=np.uint16).view(np.int16).reshape(-1,8).copy())
 if len(parts)==5:break
x=np.concatenate(parts);n=len(x);w=np.hanning(n);f=np.fft.rfftfreq(n,1/5e6);out={}
for mi,mode in enumerate(('TM010','TM011','TM012')):
 i=x[:,mi*2].astype(float)*4/65535;q=x[:,mi*2+1].astype(float)*4/65535;i-=i.mean();q-=q.mean();I=np.fft.rfft(i*w);Q=np.fft.rfft(q*w);rows={}
 for center in (5e4,1.5e5,1e6):
  mask=abs(f-center)<10000;pi=float(np.sum(abs(I[mask])**2));pq=float(np.sum(abs(Q[mask])**2));cross=np.sum(I[mask]*np.conj(Q[mask]))/np.sqrt(pi*pq);rows[str(int(center))]=dict(noise_I_over_Q_RMS=float(np.sqrt(pi/pq)),normalized_cross_real=float(cross.real),normalized_cross_imag=float(cross.imag))
 out[mode]=rows
(P/'science_IQ_cross_spectra.json').write_text(json.dumps(dict(scope='Original first5 SPEC, unchanged raw samples; extra I/Q noise diagnostic at5MHz ADC±2V',modes=out),indent=2));print(json.dumps(out,indent=2))
