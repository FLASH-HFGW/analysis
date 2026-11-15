"""Use complete toy/run populations on amplitude slides13–14; preserve scoped diagnostics."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import sys,json,shutil
sys.path.insert(0,'/tmp/v18-python-deps');import pptx
sys.path.insert(0,'/home/mazzitel/HFGW/analysis/reporting');import slide_deck as sd
BASE=Path('/home/mazzitel/HFGW/analysis-work/Run2/reports/iq_noise_summary_v24');SIM=Path('/home/mazzitel/HFGW/analysis-work/Run2/simulation/toy_full_run680');OUT=BASE.with_name('iq_noise_summary_v25');OUT.mkdir(exist_ok=True)
for n in ('assets','data'):shutil.copytree(BASE/n,OUT/n,dirs_exist_ok=True)
r=json.loads((SIM/'comparison.json').read_text());assert r['status']=='complete'
for mode,v in r['results'].items():assert v['samples']==1048576000 and v['checks_passed']
shutil.copy2(SIM/'full_run_amplitude_comparison.png',OUT/'assets/full_run_amplitude_comparison.png')
for name in ('metrics.json','comparison.json'):shutil.copy2(SIM/name,OUT/'data'/('full_toy_'+name))
deck=sd.Deck();deck.slides=json.loads((BASE/'slide_model.json').read_text())
s=deck.slides[12];s['subtitle']='Full populations: 1,048,576,000 samples per mode in both toy and run 680 · 209.7152 s each'
for item in s['items']:
 if item['kind']=='image':item['path']=str(OUT/'assets/full_run_amplitude_comparison.png')
 if item['kind']=='text' and item['y']==1.12:item['text']=sd.wrap(s['subtitle'],item['w'],item['size'])
 if item['kind']=='text' and item['y']==6.55:item['text']='Independent Rayleigh fits; each panel reports full-population N, fitted σ, empirical mean, std and RMS.'
s['notes']='Whole-run continuous filtered toy simulation, exactly1,048,576,000 samples/mode. Random prehistory and overlap-save preserve cross-block continuity. Covariance includes boundary pairs; ADC clipping and PSD checks pass. Matching the count/duration does not establish the gain-plane hypothesis. Subsequent matched-window diagnostics retain explicitly labeled20ms scopes.'
s=deck.slides[13]
for item in s['items']:
 if item['kind']=='text' and item['y']==1.12:item['text']='Whole-run populations · exact-bin Rayleigh fits · ADC ±2 V · no per-mode gain fitting'
 if item['kind']=='text' and item['y'] in (3,3.58,4.16):pass
# Rows are identified by their y coordinate; replace all seven columns in order.
oldfits=json.loads((BASE/'data/previous_revision/rayleigh_fit_ADC_corrected.json').read_text())['fits']
# v24 keeps the corrected full-run reference under its previous revision archive.
expected=json.loads((BASE/'data/previous_revision/toy_model/metrics.json').read_text())['results']
for i,(mode,v) in enumerate(r['results'].items()):
 data=next(x for x in oldfits if x['mode']==mode)
 vals=[mode,f"{expected[mode]['sigma_adc_v']*1000:.3f}",f"{v['sigma_fit_v']*1000:.3f}",f"{data['sigma_v']*1000:.3f}",f"{100*(v['sigma_fit_v']/data['sigma_v']-1):+.1f}%",f"{v['rms_v']*1000:.3f}",f"{v['data_rms_v']*1000:.3f}"]
 row=sorted([x for x in s['items'] if x['kind']=='text' and abs(x['y']-(3+i*.58))<1e-6],key=lambda x:x['x']);assert len(row)==7
 for item,value in zip(row,vals):item['text']=value
for item in s['items']:
 if item['kind']=='text' and item['y']==5.3:item['text']=sd.wrap('Both populations contain 1,048,576,000 samples per mode. σ is the Rayleigh scale, not std(A). Correlated samples are not independent observations; matching sample counts does not validate rare-event significance.',item['w'],17)
# Full-run phase populations and descriptive concentration fits.
import numpy as np,h5py
from scipy.optimize import brentq
from scipy.special import i0e,i1e
import matplotlib.pyplot as plt
fig,axs=plt.subplots(3,2,figsize=(12.8,7.2));phase_rows={}
with h5py.File(SIM/'toy_full_run680.h5') as toy,h5py.File('/home/mazzitel/HFGW/analysis-work/Run2/reports/noise_v2_development_20261109/run680_full_published/run00680_noise_v2.h5') as obs:
 for i,mode in enumerate(r['results']):
  edges=toy[mode+'/phase_edges_rad'][:];tc=toy[mode+'/phase_counts'][:];dc=obs['modes/'+mode+'/phase_counts'][:];vals=[]
  for j,(counts,col,label) in enumerate(((tc,'#7657A6','toy'),(dc,'#007F86','run680'))):
   cen=(edges[:-1]+edges[1:])/2;R1=float(abs(np.sum(counts*np.exp(1j*cen))/counts.sum()));kap=float(brentq(lambda k:i1e(k)/i0e(k)-R1,1e-12,100));vals.append((R1,kap))
   ee=edges[::8];cc=counts.reshape(-1,8).sum(axis=1);axs[i,j].stairs(cc/cc.sum()/np.diff(ee),ee,color=col);axs[i,j].set(title=mode+' · '+label,xlabel='Wrapped phase [rad]',ylabel='Density [rad⁻¹]',ylim=(0,.25),xlim=(-np.pi,np.pi))
  phase_rows[mode]=vals
fig.tight_layout();phasepath=OUT/'assets/full_run_phase_comparison.png';fig.savefig(phasepath,dpi=180);plt.close(fig)
s=deck.slides[14];s['subtitle']='Full-run phase populations in separate panels · exactly zero amplitudes excluded'
for item in s['items']:
 if item['kind']=='image':item['path']=str(phasepath)
 if item['kind']=='text' and item['y']==1.12:item['text']=sd.wrap(s['subtitle'],item['w'],item['size'])
 if item['kind']=='text' and item['y']==6.55:item['text']='Both populations span 209.7152 s; metrics use 1024 bins and displayed histograms group 8 bins.'
s=deck.slides[15]
for i,(mode,values) in enumerate(phase_rows.items()):
 vals=[mode,f'{values[0][0]:.5f}',f'{values[1][0]:.5f}',f'{values[0][1]:.5f}',f'{values[1][1]:.5f}']
 row=sorted([x for x in s['items'] if x['kind']=='text' and abs(x['y']-(3+i*.58))<1e-6],key=lambda x:x['x']);assert len(row)==5
 for item,value in zip(row,vals):item['text']=value
for i in (12,13,14,15):deck.slides[i]['source']='Sources: full-run continuous toy simulation and run680 HDF5, equal209.7152s duration; ODB ADC±2V; gain-plane hypothesis unchanged.'
(OUT/'data/full_run_phase_fits.json').write_text(json.dumps(phase_rows,indent=2))
for slide in deck.slides:
 slide['footer']=slide.get('footer','').replace('v24','v25')
 for item in slide['items']:
  if item['kind']=='image':item['path']=str(OUT/'assets'/Path(item['path']).name)
sd.export(deck,OUT,'v25',datetime.now(ZoneInfo('Europe/Rome')).strftime('%-d %B %Y'))
(OUT/'README.md').write_text('# v25\n\nSlides13–16 now use full1,048,576,000-sample toy and run680 amplitude/phase populations (phase excludes zeros). Other diagnostic pages retain their explicitly stated20ms or full-data scopes; they are not silently relabeled. The gain-plane hypothesis is unchanged. Full simulation statistics and provenance are copied to data/full_toy_*.json.\n')
