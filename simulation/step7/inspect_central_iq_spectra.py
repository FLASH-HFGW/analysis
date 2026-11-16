"""Central IQ spectral matrix from original first-five-SPEC run680 data.

One global mean per hardware quadrature, symmetric Hann, bilateral normalization.
Cross spectrum C=FFT(I)*conj(FFT(Qhardware)); z=I-iQhardware implies
S_z(+f)=S_I+S_Q-2 Im(C), S_z(-f)=S_I+S_Q+2 Im(C).
Average spectral matrices before computing normalized cross statistics.
"""
from pathlib import Path
import hashlib,json,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0,'/cvmfs/sft-flash.infn.it/package/midas/python')
import midas.file_reader
R=Path('/home/mazzitel/HFGW/analysis-work/Run2');O=R/'simulation/step7/central_iq_spectra';O.mkdir(parents=True,exist_ok=True)
raw=Path('/home/mazzitel/flash-data/data/LNF/run00680.mid.gz')
old=R/'staging/legacy-repository/autoreco/noise_continuous/periodicity_run680/periodicity_diagnostic.npz'
fr=midas.file_reader.MidasFile(str(raw),use_numpy=True);parts=[]
for ev in fr:
 if ev.header.is_midas_internal_event() or 'SPEC' not in ev.banks:continue
 parts.append(np.asarray(ev.banks['SPEC'].data,dtype=np.uint16).view(np.int16).reshape(-1,8)[:,:6].copy())
 if len(parts)==5:break
assert len(parts)==5
x=np.concatenate(parts);del parts;n=len(x);fs=5e6;assert n==5*2**20
w=np.hanning(n);norm=fs*np.sum(w*w);f=np.fft.rfftfreq(n,1/fs)
# Drop DC and Nyquist before grouping; these real-only bins need separate handling.
inds=np.arange(1,len(f)-1);trim=len(inds)//256*256;inds=inds[:trim]
ff=f[inds].reshape(-1,256).mean(axis=1)
def avg(a):return a[inds].reshape(-1,256).mean(axis=1)
plateau=(ff>.5e6)&(ff<1.5e6)
bands=[(0,1000),(1000,5000),(5000,10000),(10000,20000),(40000,60000),(140000,160000)]
archive=np.load(old);out={'modes':{}};arrays={'frequency_hz':ff}
fig,axs=plt.subplots(3,3,figsize=(15,10))
for mi,mode in enumerate(('TM010','TM011','TM012')):
 i=x[:,2*mi].astype(float)*4/65535;q=x[:,2*mi+1].astype(float)*4/65535;i-=i.mean();q-=q.mean()
 I=np.fft.rfft(i*w);Q=np.fft.rfft(q*w)
 pi=abs(I)**2/norm;pq=abs(Q)**2/norm;cross=I*Q.conj()/norm
 plus=abs(I-1j*Q)**2/norm;minus=abs(I+1j*Q)**2/norm
 np.testing.assert_allclose(plus,pi+pq-2*cross.imag,rtol=1e-10,atol=1e-23)
 np.testing.assert_allclose(minus,pi+pq+2*cross.imag,rtol=1e-10,atol=1e-23)
 # Independent archived full complex FFT: preserve historical estimator exactly.
 ref=np.fft.ifftshift(archive[mode+'_periodogram_v2_per_hz'])*.16
 np.testing.assert_allclose(plus,ref[:len(f)],rtol=1e-8,atol=1e-22)
 np.testing.assert_allclose(minus[1:-1],ref[-1:n//2:-1],rtol=1e-8,atol=1e-22)
 a=avg(pi);b=avg(pq);c=avg(cross);sp=avg(plus);sm=avg(minus);summ=a+b
 rho=c/np.sqrt(a*b);assert np.max(abs(rho))<=1+1e-10
 an=np.mean(a[plateau]);bn=np.mean(b[plateau]);sn=np.mean(summ[plateau]);spn=np.mean(sp[plateau]);smn=np.mean(sm[plateau])
 rows=[]
 for lo,hi in bands:
  sel=(ff>=lo)&(ff<hi);aa=np.mean(a[sel]);bb=np.mean(b[sel]);cc=np.mean(c[sel]);rr=cc/np.sqrt(aa*bb)
  rows.append(dict(band_hz=[lo,hi],display_bins=int(sel.sum()),I_power_over_own_plateau=float(aa/an),Q_power_over_own_plateau=float(bb/bn),I_over_Q_RMS=float(np.sqrt(aa/bb)),cross_real_normalized=float(rr.real),cross_imag_normalized=float(rr.imag),cross_term_over_IplusQ=float(-2*cc.imag/(aa+bb)),plus_power_over_own_plateau=float(np.mean(sp[sel])/spn),minus_power_over_own_plateau=float(np.mean(sm[sel])/smn)))
 # Descriptive positive-side half-deficit widths; independently normalized I/Q.
 def width(y):
  ann=np.arange(0,300001,1000);cent=(ann[:-1]+ann[1:])/2
  vals=np.array([np.mean(y[(ff>=lo)&(ff<hi)]) for lo,hi in zip(ann[:-1],ann[1:])])
  smooth=np.convolve(np.pad(vals,(2,2),mode='edge'),np.ones(5)/5,mode='valid');bottom=float(min(smooth[cent<20000]));crossing=np.flatnonzero(smooth>=(1+bottom)/2)
  return dict(min_smoothed_ratio=bottom,half_deficit_halfwidth_hz=float(cent[crossing[0]]) if len(crossing) and bottom<.8 else None)
 out['modes'][mode]=dict(bands=rows,I_width=width(a/an),Q_width=width(b/bn),original_complex_PSD_reproduced=True)
 for key,v in dict(I_psd=a,Q_psd=b,cross_psd=c,z_plus_psd=sp,z_minus_psd=sm,rho=rho).items():arrays[mode+'_'+key]=v
 ax=axs[mi,0];ax.plot(ff/1e3,10*np.log10(a/an),label='I / I plateau',lw=.8);ax.plot(ff/1e3,10*np.log10(b/bn),label='Q / Q plateau',lw=.8);ax.set(title=mode+' — separate quadratures',ylabel='Relative power [dB]',ylim=(-35,5));ax.legend(fontsize=8)
 ax=axs[mi,1];ax.plot(ff/1e3,rho.real,label='Re rho_IQ',lw=.7);ax.plot(ff/1e3,rho.imag,label='Im rho_IQ',lw=.7);ax.axhline(0,color='gray',lw=.5);ax.set(title=mode+' — averaged cross spectrum',ylabel='C_IQ / sqrt(S_I S_Q)',ylim=(-.3,.3));ax.legend(fontsize=8)
 ax=axs[mi,2];ax.plot(ff/1e3,10*np.log10(sp/sn),label='S_z(+f)',lw=.8);ax.plot(ff/1e3,10*np.log10(sm/sn),label='S_z(-f)',lw=.8);ax.plot(ff/1e3,10*np.log10(summ/sn),label='S_I + S_Q',lw=.8,ls='--');ax.set(title=mode+' — complex reconstruction',ylabel='Power / common plateau [dB]',ylim=(-35,5));ax.legend(fontsize=8)
 for ax in axs[mi]:ax.set(xlim=(0,200),xlabel='Frequency magnitude [kHz]');ax.grid(alpha=.2)
 print(mode,json.dumps(out['modes'][mode]),flush=True)
fig.suptitle('Original run680 first 5 SPEC: global mean, Hann, 256-bin spectral-matrix averages',fontsize=13);fig.tight_layout();fig.savefig(O/'central_iq_spectra.png',dpi=180);plt.close(fig)
np.savez_compressed(O/'spectral_matrix.npz',**arrays)
out.update(status='complete',samples=n,duration_s=n/fs,iq_convention='z=I-iQhardware; C=FFT(I)*conj(FFT(Qhardware)); Splus=SI+SQ-2ImC',processing='One global mean per quadrature; symmetric Hann over5SPEC; fs*sum(w^2) bilateral PSD;256-bin averages excluding DC/Nyquist; no data correction besides physical ADC4/65535',limitations=['rho is computed after spectral averaging; single-bin coherence would trivially be unity','Band ratios and widths are descriptive; no independent-bin statistical significance assigned','Tone IQ imbalance is not by itself a measurement of noise-source covariance'],input_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),old]})
(O/'summary.json').write_text(json.dumps(out,indent=2))
