"""Rebuild v18 from frozen v17, adding simulation and binned Rayleigh fits."""
from pathlib import Path
import sys,json,copy,hashlib,shutil
import numpy as np
from scipy.optimize import minimize_scalar
sys.path.insert(0,'/home/mazzitel/HFGW/analysis/reporting')
sys.path.insert(0,'/tmp/v18-python-deps')
import pptx
import slide_deck as sd
import matplotlib.pyplot as plt
import h5py,cairosvg
BASE=Path('/home/mazzitel/HFGW/analysis-work/Run2/reports/iq_noise_summary_v17')
SIM=Path('/home/mazzitel/HFGW/analysis/simulation')
OUT=Path('/home/mazzitel/HFGW/analysis-work/Run2/reports/iq_noise_summary_v18')
OUT.mkdir(exist_ok=True); A=OUT/'assets'; A.mkdir(exist_ok=True)
D=OUT/'data';D.mkdir(exist_ok=True)
old=json.loads((BASE/'slide_model.json').read_text()); snap=json.loads((BASE/'data/snapshot.json').read_text())
h5=Path(snap['run680_v2']['path'])
deck=sd.Deck()
def page(title,subtitle,lines=None,notes='',source='Source: simulation scripts and saved metrics; provenance in data/v18_provenance.json.'):
 s=deck.new(title,subtitle,source,notes)
 s['footer']='SIMULATION / MODEL CHECK | DECK v18'
 if lines:deck.bullets(s,.8,1.95,11.7,lines,20,.25)
 return s
# Retain methods, put simulation before the first single-run result (v17 slide 9).
deck.slides=copy.deepcopy(old[:8])
s=page('Simulation: separate cavity and receiver contributions','Controlled theoretical scenarios before interpreting measured IQ data',notes='Steps 1–3 include a coherent tone. Steps 4–5 remove it and change cavity parameters; they are a separate thermal experiment, not a one-parameter continuation.')
for x,title,body,col in [(.7,'THERMAL CAVITY','100 mK · 8.8 GHz\nQ0 = 50,000 · β = 1\nQL = 25,000\nLorentzian PSD',sd.COLORS[0]),(4.8,'RECEIVER NOISE','Step 4: absent\nStep 5: independent\ncomplex Gaussian noise\nSadd = kB Tadd',sd.COLORS[2]),(8.9,'COMMON READOUT','Ideal I/Q · IF 1 MHz\nLPF: 1.9 MHz, order 4\nADC: 5 MS/s, 16 bit\nAssumed range ±5 V',sd.COLORS[1])]:
 deck.rect(s,x,2.1,3.7,2.5,'#FFFFFF');deck.text(s,x+.15,2.3,3.4,.5,title,19,True,col);deck.text(s,x+.15,3,3.4,1.4,body,18)
for x in (4.4,8.5):deck.text(s,x,3.15,.4,.5,'→',23)
deck.text(s,.8,5,11.7,1.3,'Step 4: thermal cavity → readout. Step 5: add receiver noise after the cavity response, before the common LPF. No coherent tone in either scenario.\nGain = 140 dB: arbitrary numerical scaling, held fixed for the comparison.',20)
s=page('Simulation assumptions and the thesis input','Illustrative receiver prior; applicability to July run conditions remains to be established',[
 'Valeria Spasiano thesis: Tn = 3.955 ± 0.468 K; G = 67.81 ± 0.39 dB, measured in a dedicated configuration without TWPA.',
 'Step 5 uses Tn as an equivalent input noise parameter: Sadd = kB Tn. It keeps the arbitrary 140 dB gain of Step 4.',
 'The assumed LPF and ADC range are not measured instrument responses. Receiver noise is lumped into one independent source.',
 'The thermal-only model omits vacuum and receiver-added noise. Do not add a separate vacuum term to measured Tn without checking its convention.'
],source='Source: Spasiano thesis, Eqs. 6.1–6.2 and conclusion p.132; simulation step4/step5 READMEs.')
for step,folder,svg,title,sub,caption in [
 (4,SIM/'step4/FLASH_step04_thermal_model','step04_thermal_baseline.svg','Step 4: thermal cavity only','No coherent tone · theoretical 100 mK bath · no receiver-added noise','Expected: circular IQ cloud, Rayleigh amplitude and uniform phase. Correlation is set by the cavity and readout.'),
 (5,SIM/'step5/FLASH_step05_receiver_noise','step05_signal_noise_budget.svg','Step 5: add receiver noise','Same thermal realization and readout · independent receiver noise added','In this model the cavity is 0.0203% of integrated noise power. This fraction is not a measurement of Run 680.')]:
 path=A/f'step{step}.png';cairosvg.svg2png(url=str(folder/svg),write_to=str(path),output_width=2200)
 s=page(title,sub);deck.image(s,.55,1.75,12.2,4.65,path);deck.text(s,.75,6.42,11.8,.4,caption,12)
s=page('What these simulations change in the analysis','An amplitude distribution alone cannot identify the physical noise source',[
 'For zero-mean circular complex Gaussian IQ: I and Q have equal variance σ², amplitude A = |z| is Rayleigh, and phase is uniform.',
 'Both cavity noise and Gaussian receiver noise can have Rayleigh amplitudes. Their spectra and correlations carry additional information.',
 'Fit the positive amplitude A, keeping the Rayleigh location fixed at zero. Fit σ; derive mean(A), std(A) and RMS(A).',
 'Check complex offsets, IQ balance, drift and tails. Nonzero coherent offset suggests a Rice model; unequal quadrature variances also break Rayleigh.',
 'A +3σA threshold is descriptive. It is not a Gaussian false-alarm probability for Rayleigh amplitudes.'
])
# Replace original amplitude Gaussian comparison with full histogram binned likelihood.
rows=[];fig,axs=plt.subplots(3,2,figsize=(13,8),gridspec_kw={'width_ratios':[1.25,1]})
with h5py.File(h5) as f:
 for j,mode in enumerate(('TM010','TM011','TM012')):
  g=f['modes/'+mode]; mean=float(f['summary/modes/'+mode+'/mean_amplitude_v'][()])
  edges=g['noise_edges_v'][:]+mean;edges[np.abs(edges)<1e-14]=0
  assert edges.min()>=0
  n=g['noise_counts'][:].astype(float);N=n.sum();lo=edges[:-1];hi=edges[1:]
  def probs(sig):
   aa=lo**2/(2*sig**2);dd=(hi**2-lo**2)/(2*sig**2)
   return np.exp(-aa)*(-np.expm1(-dd))
  def objective(ls):
   sig=np.exp(ls);aa=lo**2/(2*sig**2);dd=(hi**2-lo**2)/(2*sig**2)
   return float(-np.sum(n*(-aa+np.log(-np.expm1(-dd)))))
  init=np.sqrt(np.sum(n*((lo+hi)/2)**2)/N/2)
  fit=minimize_scalar(objective,bounds=(np.log(init/5),np.log(init*5)),method='bounded',options={'xatol':1e-12});assert fit.success
  sig=float(np.exp(fit.x));expected=N*probs(sig);cdf=np.cumsum(n)/N;model=1-np.exp(-hi**2/(2*sig**2));distance=float(np.max(np.abs(cdf-model)))
  dc=f['dc_removed/modes/'+mode];offset=float(np.hypot(dc['mean_i_v'][()],dc['mean_q_v'][()]))
  row=dict(mode=mode,n=int(N),sigma_v=sig,location_v=0,model_mean_v=sig*np.sqrt(np.pi/2),model_std_v=sig*np.sqrt((4-np.pi)/2),model_rms_v=sig*np.sqrt(2),empirical_mean_v=mean,complex_offset_v=offset,offset_over_sigma=offset/sig,cdf_edge_max_distance=distance)
  rows.append(row)
  np.savez(D/f'{mode}_rayleigh_histogram.npz',amplitude_edges_v=edges,counts=n,expected_counts=expected)
  ax=axs[j,0];mid=(lo+hi)/2;ax.stairs(n,edges*1e3,color='#007F86',label='Full-run counts');ax.plot(mid*1e3,expected,color='#D98726',label='Rayleigh binned MLE');ax.set_yscale('log');ax.set_ylim(.5,max(n)*2);ax.set_title(f'{mode}: σ = {sig*1e3:.3f} mV; CDF gap = {distance:.4f}');ax.set_ylabel('Counts / bin');ax.legend(fontsize=8)
  ax=axs[j,1];t=(np.arange(len(g['envelope_mean_v']))+.5)*209.7152/len(g['envelope_mean_v']);ax.fill_between(t,g['envelope_min_v'][:]*1e3,g['envelope_max_v'][:]*1e3,color='#007F86',alpha=.25,label='Interval min–max');ax.plot(t,g['envelope_mean_v'][:]*1e3,lw=.6,label='Interval mean');ax.set_ylabel('Amplitude [mV]');ax.set_title(mode+' · full-run time history');ax.legend(fontsize=8)
 axs[-1,0].set_xlabel('Positive amplitude A [mV at ADC]');axs[-1,1].set_xlabel('Acquired time [s]')
fig.tight_layout();fitplot=A/'run680_rayleigh.png';fig.savefig(fitplot,dpi=180);plt.close(fig)
s=page('Run 680: amplitude versus fitted Rayleigh model','Three modes · full run · 1,048,576,000 samples per mode · ADC volts',notes='Binned multinomial maximum likelihood with exact integrated Rayleigh bin probabilities. Histogram edges store A minus the empirical mean; add that mean back before fitting. Location fixed to zero. Counts are correlated in time, so no iid fit uncertainty or goodness-of-fit p-value is reported.',source='Source: complete run00680_noise_v2.h5; data/*_rayleigh_histogram.npz and rayleigh_fit.json.')
deck.image(s,.55,1.7,12.2,4.95,fitplot)
s=page('Rayleigh fit: parameters and adequacy checks','One fitted scale per mode; location fixed to the physical amplitude origin',source='Source: full-run v2 histograms and DC moments; reproducible fit and CDF-edge diagnostics in data/.')
headers=['Mode','σ [mV]','E[A] [mV]','std(A) [mV]','|mean z| / σ','CDF gap']
xs=[.8,2.5,4.3,6.5,8.9,11.1]
for x,h in zip(xs,headers):deck.text(s,x,2,2,.6,h,15,True)
for j,r in enumerate(rows):
 vals=[r['mode'],f"{r['sigma_v']*1000:.3f}",f"{r['model_mean_v']*1000:.3f}",f"{r['model_std_v']*1000:.3f}",f"{r['offset_over_sigma']:.4f}",f"{r['cdf_edge_max_distance']:.4f}"]
 for x,val in zip(xs,vals):deck.text(s,x,2.8+j*.55,2,.5,val,18)
deck.text(s,.8,4.7,11.7,1.7,'p(A) = A/σ² exp[−A²/(2σ²)], A ≥ 0; RMS(A) = √2 σ.\nσ is the model quadrature std; it is not std(A). CDF gap = largest absolute empirical–model CDF difference at histogram edges.\nTemporal correlation and drift prevent an iid interpretation of fit errors or p-values. A fitted curve is a diagnostic, not proof of Rayleigh noise or a thermal origin.',19)
# Keep subsequent measured slides, update explicit model caveats.
deck.slides+=copy.deepcopy(old[9:])
for s in deck.slides:
 s['footer']=s.get('footer','IQ NOISE STUDY').replace('v17','v18')
 for item in s['items']:
  if item['kind']=='image':
   path=Path(item['path'])
   if BASE in path.parents:
    dest=A/path.name
    if not dest.exists():shutil.copy2(path,dest)
    item['path']=str(dest)
 s['notes']+=' v18 interpretation: amplitude thresholds in units of empirical std(A) are descriptive, not Gaussian significance. Rayleigh requires centered circular Gaussian IQ; spectra and receiver calibration are needed for source attribution.'
(D/'rayleigh_fit.json').write_text(json.dumps(dict(method='Exact-bin multinomial maximum likelihood, loc=0; no iid errors or p-values',fits=rows),indent=2))
inputs=[h5,BASE/'slide_model.json',Path('/home/mazzitel/HFGW/analysis-work/Run2/reports/Tesi_Valeria_Spasiano.pdf')]+list(SIM.rglob('metrics.json'))+list(SIM.rglob('README.md'))+list(SIM.rglob('validate_step*.py'))
(D/'v18_provenance.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},indent=2))
shutil.copytree(BASE/'data',D/'baseline_v17',dirs_exist_ok=True)
# Fit long inherited titles within the common heading area.
for slide in deck.slides:
 for item in slide['items']:
  if item['kind']=='text' and item['y']==.38:
   item['text']=slide['title']
   while len(sd.wrap(item['text'],item['w'],item['size']).splitlines())>1:
    item['size']-=1
  if item['kind']=='text' and 'Validate the magnitude-noise model' in item['text']:
   item['text']=sd.wrap('Check Rayleigh residuals, rare tails and low-amplitude phase artefacts.',item['w'],item['size'])
from expectations import update
update(deck,OUT,SIM,h5,rows)
sd.export(deck,OUT,'v18','14 November 2026')
(OUT/'README.md').write_text('v18: frozen v17 plus simulation assumptions, thermal-only and receiver-noise scenarios, and full-run binned Rayleigh MLE. No raw scientific HDF5 is modified. Baseline evidence and provenance retained in data/baseline_v17.\n')
print(json.dumps(rows,indent=2))
