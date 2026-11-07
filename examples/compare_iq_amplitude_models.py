#!/usr/bin/env python3
"""Descriptive Rayleigh/Gaussian tail comparison at empirical amplitude thresholds."""
import json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/noise_continuous');MODES=('TM010','TM011','TM012')
def compare():
 rows=[json.loads(p.read_text()) for p in sorted((Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/job_to_submit_noise')).glob('*/run*_noise.json'))]
 assert len(rows)==260 and all(d['reached_eof'] for d in rows)
 report={'runs':260,'scope':'amplitude-only; invariant under continuity correction',
 'model':'Rayleigh marginal amplitude if centered isotropic Gaussian IQ; not proof of Gaussian/independent IQ',
 'scale_estimation':'per-run s^2 = E[A^2]/2 = (mean(A)^2 + Var(A))/2 from the same samples',
 'tail_prediction':'sum over runs of N_run exp(-T_run^2/(2 s_run^2)); local empirical T_run=mean(A)+k std(A)',
 'limitations':'in-sample moment-based descriptive comparison; no goodness-of-fit p-value or independent-sample uncertainty; residuals may reflect calibration, drift or distribution shape',
 'modes':{}}
 for mode in MODES:
  report['modes'][mode]={}
  for k in (3,5,7):
   n=observed=0;expected=0.
   for d in rows:
    st=d['global_statistics']['modes'][mode];mu=st['mean'];var=st['m2']/st['n'];t=st['thresholds_v']['local'][str(k)]
    n+=st['n'];observed+=st['exceedances']['local'][str(k)]['samples_above']
    expected+=st['n']*math.exp(-t*t/(mu*mu+var))
   report['modes'][mode][str(k)]={'samples':n,'observed':observed,'rayleigh_expected':expected,
      'observed_fraction':observed/n,'rayleigh_fraction':expected/n,'observed_over_rayleigh':observed/expected,
      'gaussian_fraction':.5*math.erfc(k/math.sqrt(2))}
 (OUT/'amplitude_model_comparison.json').write_text(json.dumps(report,indent=2)+'\n')
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(1,2,figsize=(11,4))
 colors=('#007F86','#7657A6','#D98726');ks=(3,5,7)
 for mode,color in zip(MODES,colors):
  values=report['modes'][mode]
  axes[0].plot(ks,[values[str(k)]['observed_fraction'] for k in ks],'o-',color=color,label=mode+' observed')
  axes[0].plot(ks,[values[str(k)]['rayleigh_fraction'] for k in ks],'--',color=color,alpha=.7)
  axes[1].plot(ks,[values[str(k)]['observed_over_rayleigh'] for k in ks],'o-',color=color,label=mode)
 axes[0].plot(ks,[.5*math.erfc(k/math.sqrt(2)) for k in ks],'x:',color='gray',label='Gaussian comparison')
 axes[0].set_yscale('log');axes[0].set(ylabel='Fraction above empirical amplitude threshold',title='Solid: observed · dashed: Rayleigh');axes[0].legend(fontsize=8)
 axes[1].axhline(1,color='gray',ls='--',lw=1);axes[1].set(ylabel='Observed / Rayleigh prediction',title='Residuals: not a significance test',ylim=(.9,1.15));axes[1].legend(fontsize=9)
 for ax in axes:ax.set(xlabel='k in threshold mean(A) + k std(A)',xticks=ks);ax.grid(alpha=.2)
 fig.tight_layout();fig.savefig(OUT/'amplitude_model_comparison.png',dpi=180);plt.close(fig)
 return report
if __name__=='__main__':compare()
