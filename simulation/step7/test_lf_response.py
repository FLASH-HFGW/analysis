"""Step 7: conditional LF-response shape scan; no fit or change to measured data."""
from pathlib import Path
import json, hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path('/home/mazzitel/HFGW/analysis-work/Run2')
O=R/'simulation/step7'; O.mkdir(parents=True,exist_ok=True)
calpath=R/'diagnostics/normalization_audit_20261114/calibration_reconstruction.json'
physpath=R/'simulation/step6/metrics.json'
c=json.loads(calpath.read_text()); phys=json.loads(physpath.read_text())['mode_results']
fs=5e6; n=2**20; f=np.fft.fftfreq(n,1/fs); fc=300e3
alphas=[1.,.5,.25,.1]; results={}; arrays={}
fig,axs=plt.subplots(3,3,figsize=(15,11))
for j,(mode,p) in enumerate(phys.items()):
 pts=c['curves'][mode]; offset=c['comparison'][mode]['rf_if_offset_hz']
 xx=np.array([r['rf_hz']-offset for r in pts]); kk=np.array([r['kz_integrated'] for r in pts])*.01
 order=np.argsort(xx);xx=xx[order];kk=kk[order]
 ki=2*np.pi*p['f0_hz']/p['q0'];kt=ki*(1+p['kappa1']+p['kappa2'])
 th=6.62607015e-34*p['f0_hz']/np.expm1(6.62607015e-34*p['f0_hz']/(1.380649e-23*p['temperature_k']))
 d=np.load(R/f'simulation/toy_ODB_cal5_data2_LF_20261116/comparison/{mode}_comparison.npz')
 fd=d['frequency_hz'];pd=d['data_psd_v2_hz'];plateau=lambda ff,ss:np.mean(ss[(abs(ff)>.5e6)&(abs(ff)<1.5e6)])
 axs[0,j].plot(fd/1e3,10*np.log10(pd/plateau(fd,pd)),color='black',lw=.6,label='Run 680 (unchanged)')
 axs[1,j].plot(d['lag_s']*1e6,d['data_g1'].real,color='black',label='Run 680')
 results[mode]={};base=None
 for alpha in alphas:
  S=np.zeros(n)
  for alias in (-1,0,1):
   af=f+alias*fs
   # Compress only the central measured response feature. Outside fc unchanged.
   mapped=np.where(abs(af)<fc,np.sign(af)*np.minimum(abs(af)/alpha,fc),af)
   response=np.interp(mapped,xx,kk,left=0,right=0)
   source=50*10**(103.4/10)*(1.380649e-23*3.955+th*ki**2*p['kappa2']/((kt/2)**2+(2*np.pi*(af-1e6))**2))
   S+=source*response**2
  if base is None:base=S.copy()
  np.testing.assert_array_equal(S[abs(f)>=fc],base[abs(f)>=fc])
  assert np.all(np.isfinite(S)) and np.all(S>=0)
  g=np.fft.ifft(S)[:201];g/=g[0].real
  sf=np.fft.fftshift(f);ss=np.fft.fftshift(S);ratio=ss/plateau(sf,ss)
  ann=np.arange(0,300001,1000);cent=(ann[:-1]+ann[1:])/2
  vals=np.array([np.mean(ratio[(abs(sf)>=lo)&(abs(sf)<hi)]) for lo,hi in zip(ann[:-1],ann[1:])])
  smooth=np.convolve(np.pad(vals,(2,2),mode='edge'),np.ones(5)/5,mode='valid');bottom=float(min(smooth[cent<20000]));cross=np.flatnonzero(smooth>=(1+bottom)/2)
  width=float(2*cent[cross[0]]) if len(cross) else None
  key=f'alpha_{alpha:g}';results[mode][key]=dict(compression=alpha,rms_v=float(np.sqrt(fs*np.mean(S))),descriptive_full_width_hz=width,central_smoothed_power_ratio=bottom,real_g1_at_0p4us=float(g[2].real))
  arrays[f'{mode}_{key}_psd']=ss;arrays[f'{mode}_{key}_g1']=g
  axs[0,j].plot(sf/1e3,10*np.log10(np.maximum(ratio,1e-15)),label=f'alpha={alpha:g}',lw=1)
  axs[1,j].plot(np.arange(201)/fs*1e6,g.real,label=f'alpha={alpha:g}')
  # Analytical response alone, normalized at +300 kHz; not an inferred hardware transfer.
  grid=np.linspace(-fc,fc,2001);mapped=np.sign(grid)*np.minimum(abs(grid)/alpha,fc)
  rr=np.interp(mapped,xx,kk,left=0,right=0);ref=np.interp(fc,xx,kk)
  axs[2,j].plot(grid/1e3,(rr/ref)**2,label=f'alpha={alpha:g}')
 axs[0,j].set(title=mode,xlabel='IF [kHz]',ylabel='PSD / plateau [dB]',xlim=(-300,300),ylim=(-35,5))
 axs[1,j].set(xlabel='Lag [us]',ylabel='Re g1',xlim=(0,5),ylim=(-.15,.2));axs[1,j].axhline(0,color='gray',lw=.5)
 axs[2,j].set(xlabel='IF [kHz]',ylabel='Response power / value at +300 kHz')
 for ax in axs[:,j]:ax.legend(fontsize=7);ax.grid(alpha=.2)
arrays['frequency_hz']=np.fft.fftshift(f);arrays['lag_s']=np.arange(201)/fs
fig.suptitle('Step 7: hypothetical LF-response contraction; fixed gains and noise sources',fontsize=14)
fig.tight_layout();fig.savefig(O/'lf_response_sensitivity.png',dpi=170);plt.close(fig)
report=dict(status='complete',type='Analytical expected PSD and covariance sensitivity scan, not a calibrated LF20 response or data fit',reference='toy_ODB_cal5_data2_LF_20261116',modified_only='Central scalar response shape within +/-300 kHz',mapping='f_map=sign(f)*min(abs(f)/alpha,300kHz) inside +/-300kHz; identity outside',alphas=alphas,notes=['alpha=1 reproduces baseline response','No amplitude matching, additional noise, IQ correction or change to measured estimator','Expected spectra suffice for first hypothesis; no full-run MC generated','Half-deficit widths are descriptive and use each model own depth','Compression may produce artificial corners; this is a sensitivity parameterization, not a circuit model'],results=results,input_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [calpath,physpath,Path(__file__)]})
(O/'metrics.json').write_text(json.dumps(report,indent=2));np.savez_compressed(O/'expected_response_scan.npz',**arrays)
print(json.dumps(results,indent=2))
