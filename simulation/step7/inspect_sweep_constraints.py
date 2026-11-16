"""Show which central response features are actually constrained by tone sweeps."""
from pathlib import Path
import hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path('/home/mazzitel/HFGW/analysis-work/Run2');O=R/'simulation/step7/sweep_constraints';O.mkdir(parents=True,exist_ok=True)
calpath=R/'diagnostics/normalization_audit_20261114/calibration_reconstruction.json'
scanpath=R/'simulation/step7/expected_response_scan.npz'
c=json.loads(calpath.read_text());scan=np.load(scanpath)
fig,axs=plt.subplots(3,2,figsize=(13,10));report={'modes':{}}
for row,(mode,pts) in enumerate(c['curves'].items()):
 offset=c['comparison'][mode]['rf_if_offset_hz']
 x=np.array([p['rf_hz']-offset for p in pts]);k=np.array([p['kz_integrated'] for p in pts]);order=np.argsort(x);x=x[order];k=k[order]
 assert np.all(np.diff(x)>0)
 neg=float(x[x<0].max());pos=float(x[x>0].min());gap=(neg,pos)
 grid=np.linspace(-350e3,350e3,7001);power=np.interp(grid,x,k)**2
 # Normalize response and measured noise independently to the same frequency region.
 normgrid=np.linspace(-1.5e6,1.5e6,30001);plateau=(abs(normgrid)>.5e6)&(abs(normgrid)<1.5e6)
 knorm=np.mean(np.interp(normgrid,x,k)[plateau]**2)
 pn=k*k/knorm;curve=power/knorm
 dpath=R/f'simulation/toy_ODB_cal5_data2_LF_20261116/comparison/{mode}_comparison.npz';d=np.load(dpath)
 f=d['frequency_hz'];p=d['data_psd_v2_hz'];dnorm=np.mean(p[(abs(f)>.5e6)&(abs(f)<1.5e6)]);pr=p/dnorm
 close=np.argsort(abs(x))[:6];points=[]
 for i in sorted(close,key=lambda i:x[i]):
  select=abs(f-x[i])<5e3
  points.append(dict(IF_hz=float(x[i]),runs=pts[order[i]]['runs'],calibration_response_power_relative=float(pn[i]),data_noise_power_relative_10kHz_band=float(np.mean(pr[select])),data_bins_in_band=int(select.sum())))
 results=dict(no_tone_points_between_hz=list(gap),gap_hz=pos-neg,median_sweep_step_hz=float(np.median(np.diff(x))),central_points=points)
 for col in range(2):
  ax=axs[row,col];ax.axvspan(neg/1e3,pos/1e3,color='#e9c46a',alpha=.23,label='No calibration tone points')
  ax.axvline(neg/1e3,color='gray',ls=':',lw=.7);ax.axvline(pos/1e3,color='gray',ls=':',lw=.7)
  if col==0:
   ax.plot(f/1e3,10*np.log10(pr),color='#007F86',lw=.65,label='Run 680: original PSD')
   ax.set_title(mode+' — measured noise')
  else:
   ax.plot(grid/1e3,10*np.log10(curve),color='#007F86',lw=1.4,label='Scalar tone-response interpolation')
   ax.scatter(x/1e3,10*np.log10(pn),color='black',s=25,zorder=4,label='Measured calibration tone points')
   mapped=np.sign(grid)*np.minimum(abs(grid)/.1,300e3)
   mapped=np.where(abs(grid)<300e3,mapped,grid)
   alt=np.interp(mapped,x,k)**2/knorm
   ax.plot(grid/1e3,10*np.log10(alt),color='#D98726',lw=1.2,ls='--',label='Step 7 alpha=0.1: hypothetical science response')
   ax.set_title(mode+' — tone response (not noise PSD)')
  ax.set(xlim=(-350,350),ylim=(-35,5),xlabel='IF relative to first LO / mapped mode [kHz]',ylabel='Power / own plateau [dB]');ax.grid(alpha=.2);ax.legend(fontsize=7,loc='lower left')
 report['modes'][mode]=results
fig.suptitle('Measured noise and tone response: independent plateau normalization; no absolute-gain comparison',fontsize=12)
fig.tight_layout();fig.savefig(O/'sweep_constraints_all_modes.png',dpi=180);plt.close(fig)
# Exact low-frequency zoom preserves the measured data and reveals the unsampled interval.
fig,axs=plt.subplots(1,2,figsize=(12,4.5))
mode='TM010';pts=c['curves'][mode];off=c['comparison'][mode]['rf_if_offset_hz'];x=np.array([p['rf_hz']-off for p in pts]);k=np.array([p['kz_integrated'] for p in pts]);order=np.argsort(x);x=x[order];k=k[order]
d=np.load(R/f'simulation/toy_ODB_cal5_data2_LF_20261116/comparison/{mode}_comparison.npz');f=d['frequency_hz'];p=d['data_psd_v2_hz'];dn=np.mean(p[(abs(f)>.5e6)&(abs(f)<1.5e6)])
for ax in axs:ax.axvspan(-49.180327869,49.180327869,color='#e9c46a',alpha=.23);ax.set(xlim=(-75,75),ylim=(-35,3),xlabel='IF [kHz]',ylabel='Power / own plateau [dB]');ax.grid(alpha=.2)
axs[0].plot(f/1e3,10*np.log10(p/dn),color='#007F86',lw=.8);axs[0].set_title('TM010: measured noise; central dip resolved')
ng=np.linspace(-1.5e6,1.5e6,30001);mask=(abs(ng)>.5e6)&(abs(ng)<1.5e6);norm=np.mean(np.interp(ng,x,k)[mask]**2);g=np.linspace(-75e3,75e3,1501)
axs[1].plot(g/1e3,10*np.log10(np.interp(g,x,k)**2/norm),color='#007F86',label='Interpolation');axs[1].scatter(x/1e3,10*np.log10(k*k/norm),color='black',label='Calibration points');axs[1].set_title('TM010: no tone points inside +/-49.18 kHz');axs[1].legend()
fig.tight_layout();fig.savefig(O/'TM010_unsampled_center.png',dpi=180);plt.close(fig)
report.update(status='complete',normalization='Each population divided by its own mean power in |IF|=0.5–1.5 MHz; response plateau from fine interpolation grid. Shape comparison only; not amplitude fitting.',findings=['The central approximately98.36kHz interval has no tone measurement; linear interpolation cannot identify a narrower central notch.','TM010 attenuation is already present at the measured points near +/-49kHz and +/-148kHz, so the broad depression cannot be attributed solely to interpolation across the central gap.','Step7 compression changes the response at measured tone frequencies too. It requires a different science-state response; it is not simply a permissible interpolation of the same sweep.','Tone response and science noise PSD are different observables; a mismatch can also indicate distributed noise or IQ/image response, not necessarily a changing scalar transfer.'],input_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),calpath,scanpath]})
(O/'summary.json').write_text(json.dumps(report,indent=2))
lines=['# Vincoli dello sweep sulla depressione centrale','',report['normalization'],'','| Modo | IF [kHz] | Risposta tono / plateau | PSD rumore / plateau (banda 10 kHz) |','| --- | ---: | ---: | ---: |']
for m,v in report['modes'].items():
 for q in v['central_points']:lines.append(f"| {m} | {q['IF_hz']/1e3:.2f} | {q['calibration_response_power_relative']:.4f} | {q['data_noise_power_relative_10kHz_band']:.4f} |")
lines+=['']+['- '+s for s in report['findings']]
(O/'summary.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
