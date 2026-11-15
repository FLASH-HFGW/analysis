"""Validate full-run output and plot independent full-population amplitude fits."""
from pathlib import Path
import json
import numpy as np,h5py
from scipy.stats import rayleigh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path('/home/mazzitel/HFGW/analysis-work/Run2');OUT=ROOT/'simulation/toy_full_run680'
DATA=ROOT/'reports/noise_v2_development_20261109/run680_full_published/run00680_noise_v2.h5'
def report():
 m=json.loads((OUT/'metrics.json').read_text());assert m['status']=='complete';assert len(m['results'])==3
 fig,axs=plt.subplots(3,2,figsize=(13,7.5))
 with h5py.File(OUT/'toy_full_run680.h5') as toy,h5py.File(DATA) as data:
  for i,(mode,r) in enumerate(m['results'].items()):
   assert r['samples']==1048576000 and r['checks_passed']
   e=toy[mode+'/amplitude_edges_v'][:];c=toy[mode+'/amplitude_counts'][:];assert int(c.sum())==1048576000
   mean=float(data['summary/modes/'+mode+'/mean_amplitude_v'][()])*.4;ed=(data['modes/'+mode+'/noise_edges_v'][:])*.4+mean;cd=data['modes/'+mode+'/noise_counts'][:];assert int(cd.sum())==1048576000
   # Existing independently verified full-run exact-bin fit, already rescaled to actual ADC units.
   fits=json.loads((ROOT/'reports/iq_noise_summary_v22/data/rayleigh_fit_ADC_corrected.json').read_text())['fits'];fit=next(x for x in fits if x['mode']==mode)
   for j,(edges,counts,sigma,mu,std,rms,color,label) in enumerate([(e,c,r['sigma_fit_v'],r['mean_amplitude_v'],r['std_amplitude_v'],r['rms_v'],'#7657A6','Toy'),(ed,cd,fit['sigma_v'],mean,float(data['summary/modes/'+mode+'/amplitude_noise_rms_v'][()])*.4,float(data['dc_removed/modes/'+mode+'/total_rms_v'][()])*.4,'#007F86','Run680')]):
    ax=axs[i,j];density=counts/counts.sum()/np.diff(edges)/1000;ax.stairs(density,edges*1000,color=color);xx=np.linspace(0,max(e[np.flatnonzero(c)[-1]+1],ed[-1]),1000);ax.plot(xx*1000,rayleigh(scale=sigma).pdf(xx)/1000,'--',color='#263952',lw=1)
    ax.set(title=mode+' · '+label,xlabel='Amplitude [mV ADC]',ylabel='Density [mV⁻¹]',yscale='log',ylim=(1e-9,.1),xlim=(0,max(e[np.flatnonzero(c)[-1]+1],ed[-1])*1000))
    ax.text(.98,.97,f'N={int(counts.sum()):,}\nσ={sigma*1000:.3f} mV\nmean={mu*1000:.3f} mV\nstd={std*1000:.3f} mV\nRMS={rms*1000:.3f} mV',transform=ax.transAxes,ha='right',va='top',fontsize=8,bbox=dict(facecolor='white',alpha=.9))
   r['data_rms_v']=float(data['dc_removed/modes/'+mode+'/total_rms_v'][()])*.4;r['data_sigma_fit_v']=fit['sigma_v'];r['toy_data_sigma_relative_difference']=r['sigma_fit_v']/fit['sigma_v']-1
 fig.tight_layout();fig.savefig(OUT/'full_run_amplitude_comparison.png',dpi=180);plt.close(fig)
 (OUT/'comparison.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
if __name__=='__main__':report()
