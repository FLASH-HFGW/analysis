"""Separate narrow measured notch from whole-window DC subtraction; no science outputs changed."""
from pathlib import Path
import sys,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0,'/cvmfs/sft-flash.infn.it/package/midas/python');import midas.file_reader
R=Path('/home/mazzitel/HFGW/analysis-work/Run2');O=R/'diagnostics/TM010_notch_model_review_20261116';O.mkdir(parents=True,exist_ok=True);fr=midas.file_reader.MidasFile('/home/mazzitel/flash-data/data/LNF/run00680.mid.gz',use_numpy=True);parts=[]
for ev in fr:
 if ev.header.is_midas_internal_event() or 'SPEC' not in ev.banks:continue
 parts.append(np.asarray(ev.banks['SPEC'].data,dtype=np.uint16).view(np.int16).reshape(-1,8)[:,:2].copy())
 if len(parts)==5:break
x=np.concatenate(parts);del parts;n=len(x);fs=5e6;z=(x[:,0].astype(float)-1j*x[:,1].astype(float))*4/65535;w=np.hanning(n);f=np.fft.fftshift(np.fft.fftfreq(n,1/fs));norm=fs*np.sum(w*w);pc=np.fft.fftshift(abs(np.fft.fft((z-z.mean())*w))**2/norm);pr=np.fft.fftshift(abs(np.fft.fft(z*w))**2/norm);sel=(abs(f)>1e3)&(abs(f)<2e5);rel=np.max(abs(pc[sel]-pr[sel])/np.maximum(pc[sel],1e-99));group=256;ff=f.reshape(-1,group).mean(axis=1);p=pc.reshape(-1,group).mean(axis=1);raw=pr.reshape(-1,group).mean(axis=1)
with np.load(R/'staging/legacy-repository/autoreco/noise_continuous/periodicity_run680/periodicity_diagnostic.npz') as a:np.testing.assert_allclose(p,(a['TM010_periodogram_v2_per_hz']*.16).reshape(-1,group).mean(axis=1),rtol=1e-11,atol=1e-24)
a=np.load(R/'diagnostics/TM010_response_audit_20261115/TM010_response_audit.npz');ft=a['frequency_hz'];pt=a['scalar_expected_PSD'];pl=(abs(ff)>.5e6)&(abs(ff)<1.5e6);tl=(abs(ft)>.5e6)&(abs(ft)<1.5e6);pn=p/np.mean(p[pl]);rn=raw/np.mean(raw[pl]);tn=pt/np.mean(pt[tl]);ann=np.arange(0,300001,1000);cent=(ann[:-1]+ann[1:])/2
# Descriptive notch width: first outward crossing of half the low-frequency deficit.
def width(f,y):
 vals=np.array([np.mean(y[(abs(f)>=lo)&(abs(f)<hi)]) for lo,hi in zip(ann[:-1],ann[1:])]);smooth=np.convolve(np.pad(vals,(2,2),mode='edge'),np.ones(5)/5,mode='valid');bottom=float(np.min(smooth[cent<20000]));threshold=(1+bottom)/2;idx=np.flatnonzero(smooth>=threshold);fc=float(cent[idx[0]]) if len(idx) else None;return dict(min_smoothed_ratio=bottom,half_deficit_level=threshold,half_deficit_halfwidth_hz=fc,full_width_hz=2*fc if fc else None),smooth
wd,dd=width(ff,pn);wt,tt=width(ft,tn)
fig,axs=plt.subplots(2,3,figsize=(12.5,6.3))
for j,(fx,y,title) in enumerate(((ff,pn,'Data: original mean subtraction'),(ff,rn,'Data: no mean subtraction'),(ft,tn,'Toy: expected filtered-noise PSD'))):
 for i,lim in enumerate((250000,25000)):
  axs[i,j].plot(fx/1000,10*np.log10(y),lw=.6,color='#7657A6' if j==2 else '#007F86');axs[i,j].set(title=title,xlabel='IF [kHz]',ylabel='Power / plateau [dB]',xlim=(-lim/1000,lim/1000),ylim=(-35,12));axs[i,j].axhline(0,color='gray',lw=.5)
fig.tight_layout();fig.savefig(O/'notch_mean_subtraction_check.png',dpi=185);plt.close(fig)
result=dict(scope='Diagnostic only; original first5SPEC analysis preserved',samples=n,duration_s=n/fs,global_complex_mean_v=[float(z.mean().real),float(z.mean().imag)],max_relative_PSD_change_with_mean_subtraction_above1kHz=float(rel),data_width=wd,toy_width=wt,width_definition='Symmetric1kHz annuli,5-bin moving mean; first outward crossing of half-deficit level; descriptive, not a fitted hardware cutoff',findings=['The measured notch extends well beyond the spectral scale1/T≈0.954Hz of a single whole-window mean subtraction.','Removing or retaining the global mean leaves the kHz-wide measured notch essentially unchanged; the centered PSD reproduces the original v21 reference.','The active toy multiplies cavity and all equivalent receiver noise by one combined measured magnitude response. This puts all receiver noise upstream of every modeled response feature.','A flat noise floor added after all filtering would also fill the very deep data minimum near zero. To retain a narrow deep notch, distributed noise needs a downstream common narrow response, or the science-setting response itself must be narrower.'],model_alternatives=['Frequency-dependent physical transfer at science LF setting, rather than gain-only scaling of the calibration response.','Distributed receiver/LF/mixer noise injection points and downstream response per source.','Vector I/Q response including image leakage and cross-spectra instead of scalar magnitude-only filtering.','Actual low-frequency electronics coupling/feedback/high-pass stages; do not replace this by subtracting a covariance offset.'],non_explanations=['Uniform RF/LF gain rescales PSD but not relative notch width.','Subtracting one complex mean over1.049s does not explain a kHz-wide notch.','More Monte Carlo samples do not remove a discrepancy reproduced by expected PSD/covariance.'])
(O/'summary.json').write_text(json.dumps(result,indent=2));np.savez_compressed(O/'processing_check.npz',frequency_hz=ff,data_centered_relative=pn,data_uncentered_relative=rn,toy_frequency_hz=ft,toy_expected_relative=tn,radial_frequency_hz=cent,data_smoothed=dd,toy_smoothed=tt);print(json.dumps(result,indent=2))
