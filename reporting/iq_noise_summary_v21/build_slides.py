"""Presentation revision using measured-parameter simulation, without internal stage names."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,hashlib,shutil,sys,re
import numpy as np
import h5py
from scipy import stats
sys.path.insert(0,'/tmp/v18-python-deps')
import pptx
sys.path.insert(0,'/home/mazzitel/HFGW/analysis/reporting')
import slide_deck as sd
import matplotlib.pyplot as plt
BASE=Path('/home/mazzitel/HFGW/analysis-work/Run2/reports/iq_noise_summary_v20')
SIM=Path('/home/mazzitel/HFGW/analysis-work/Run2/simulation/step6')
OUT=BASE.with_name('iq_noise_summary_v21');OUT.mkdir(exist_ok=True)
A=OUT/'assets';A.mkdir(exist_ok=True);D=OUT/'data';D.mkdir(exist_ok=True)
shutil.copytree(BASE/'data',D,dirs_exist_ok=True)
shutil.copytree(SIM,D/'simulation_model',ignore=shutil.ignore_patterns('assets'),dirs_exist_ok=True)
model=json.loads((SIM/'metrics.json').read_text());modes=model['mode_results'];old=json.loads((BASE/'slide_model.json').read_text())
previous=json.loads((BASE/'data/expected_vs_measured.json').read_text())
fits=previous['rayleigh_fits'];phase_rows=previous['full_run_phase'];covrows=previous['five_SPEC_covariance']
deck=sd.Deck();deck.slides=old[:8]
source='Sources: Spasiano thesis Table 6.1 and Ch.5–6; run 680 AVS T15; measured-parameter model and provenance in data/simulation_model/.'
def page(title,subtitle,notes='',src=source):
 s=deck.new(title,subtitle,src,notes);s['footer']='SIMULATION | MEASURED INPUTS / EXPLICIT LIMITS | DECK v21';return s
s=page('Simulation: measured cavity and readout model',
 'TM010 / TM011 / TM012 · cavity temperature 40.422 mK, observed during run 680 · no coherent tone',
 'Two external ports contribute to damping. Intrinsic thermal wall emission couples to measured output port 2. Incident-port noise and correlations are not synthesized. Tn=3.955±0.468 K is measured for the thesis no-TWPA configuration but not established for each mode/run. RF and total nominal ADC gains are distinct reference planes, not cascaded.')
blocks=[(.6,'CAVITY THERMAL EMISSION','Measured f₀, Q₀, κ₁, κ₂\nObserved AVS T15 temperature',sd.COLORS[0]),(3.85,'+ RECEIVER NOISE','Tn = 3.955 ± 0.468 K\nConditional no-TWPA input',sd.COLORS[2]),(7.1,'RF / DOWNCONVERSION','RF gain: 103.4 dB\nTotal ADC: 143 dB nominal',sd.COLORS[1]),(10.35,'SAMPLING','IF 1 MHz · LPF 1.9 MHz\n5 MS/s · 16 bit · ±5 V*',sd.NAVY)]
for x,title,text,col in blocks:
 deck.rect(s,x,1.85,2.95,1.3,'#FFFFFF');deck.text(s,x+.1,2,2.75,.4,title,12,True,col);deck.text(s,x+.1,2.55,2.75,.55,text,12)
for x in (3.54,6.79,10.04):deck.text(s,x,2.35,.32,.4,'→',20)
heads=['Mode','f₀ [GHz]','Q₀','κ₁ / κ₂','Q loaded','FWHM [kHz]','τ cavity [μs]'];xs=[.75,2.05,3.85,5.1,7.25,9.15,11.15];ws=[1.2,1.7,1.2,2.,1.7,1.8,1.8]
for x,w,text in zip(xs,ws,heads):deck.text(s,x,3.55,w,.4,text,13,True)
for j,(mode,r) in enumerate(modes.items()):
 vals=[mode,f"{r['f0_hz']/1e9:.6f}",f"{r['q0']:,.0f}",f"{r['kappa1']:.4g} / {r['kappa2']:.2f}",f"{r['ql']:,.0f}",f"{r['fwhm_hz']/1e3:.2f}",f"{r['tau_amplitude_s']*1e6:.3f}"]
 for x,w,text in zip(xs,ws,vals):deck.text(s,x,4.2+j*.55,w,.4,text,14)
deck.text(s,.8,6,11.7,.65,'Q loaded = Q₀ / (1 + κ₁ + κ₂). *ADC range is the saved analysis setting; independent hardware confirmation is missing. LPF order/shape remains assumed.',15)
s=page('Calibration gaps: what could move the prediction?',
 'Available measurements anchor the cavity; the complete ADC transfer remains uncalibrated',
 'Directions are conditional model sensitivities, not measured corrections. A scalar gain change cannot repair a normalized covariance mismatch. Wider bandwidth may reduce lag-one correlation in this centered white receiver model but increases integrated noise at fixed PSD. Noise-wave correlations, input-port noise and quantum measurement conventions are not fully modeled; their correction has no assigned sign.')
ratios=[r['nominal_sim_to_measured_ac_rms_ratio'] for r in modes.values()];deltas=[-20*np.log10(x) for x in ratios]
deck.bullets(s,.8,1.9,11.7,[
 'Missing numerical kz(f) curves and run-matched receiver/gain calibration: their corrections can increase or decrease the prediction; no sign is established.',
 f'Lower effective gain lowers ADC RMS, leaving normalized phase/coherence unchanged. Explaining the amplitude gap by gain alone would require {deltas[0]:.1f}, {deltas[1]:.1f}, {deltas[2]:.1f} dB changes across the three modes. These are diagnostics, not calibration estimates.',
 'LPF shape is assumed. A wider/flatter admitted band can reduce short-lag coherence but increases broadband power; narrowing the band lowers power but tends to lengthen coherence.',
 'IQ offsets/imbalance and receiver noise may differ by mode. Offsets or unequal quadrature gains can change phase and amplitude shape; their measured corrections are unavailable.',
 'Cavity thermal emission contributes less than 0.00004% of modeled power. Adjusting cavity temperature or Q cannot explain an 18–42× RMS gap while this receiver model dominates.'
],17,.2)
# One result page replaces both previous illustrative simulation pages.
with h5py.File(SIM/'step06_simulation.h5') as h:
 z=h['TM010/input_total_after_assumed_LPF_v'][:];lag=h['lag_s'][:];g=h['TM010/g1_expected'][:];ge=h['TM010/g1_simulated'][:]
r=modes['TM010'];gain=10**(model['nominal_ADC_gain_db']/20);sigma=r['sigma_expected_input_v']*gain
fig,axs=plt.subplots(1,3,figsize=(13,3.5));amp=abs(z)*gain;bins=np.linspace(0,np.quantile(amp,.9999),65)
axs[0].hist(amp,bins=bins,density=True,color='#7049ac',alpha=.4,label='Simulated');x=np.linspace(0,bins[-1],250);axs[0].plot(x,stats.rayleigh(scale=sigma).pdf(x),color='#263952',label='Rayleigh expectation');axs[0].set(xlabel='Nominal ADC amplitude [V]',ylabel='Density [V⁻¹]',title='Amplitude');axs[0].legend(fontsize=8)
axs[1].hist(np.angle(z),bins=50,density=True,color='#7049ac',alpha=.4);axs[1].axhline(1/(2*np.pi),color='#263952',ls='--');axs[1].set(xlabel='Phase [rad]',ylabel='Density [rad⁻¹]',title='Uniform phase')
axs[2].plot(lag[1:]*1e6,abs(g[1:]),'--',color='#263952',label='Expected |g₁|');axs[2].plot(lag[1:]*1e6,abs(ge[1:]),'.',color='#7049ac',label='Simulated');axs[2].set(xlabel='Lag [μs]',ylabel='|g₁|',title='Temporal coherence');axs[2].legend(fontsize=8)
fig.tight_layout();path=A/'simulation_expected_observables.png';fig.savefig(path,dpi=190);plt.close(fig)
s=page('Simulation: expected observables',
 'Three measured cavity modes · conditional receiver model · 143 dB nominal total gain',
 'Values are ensemble expectations, not fitted to Run 680. Receiver-dominated differences between modes are below the displayed precision. Thermal wall emission is included; no additional vacuum term is added to equivalent receiver Tn. τ cavity on the previous page is not the coherence time of the receiver-dominated total signal.')
deck.image(s,.5,1.85,12.3,3.45,path)
expected=[('σ quadrature',sigma),('mean(A)',r['mean_amplitude_expected_input_v']*gain),('std(A)',r['std_amplitude_expected_input_v']*gain),('RMS(A)',r['rms_nominal_ADC_v'])]
for j,(label,value) in enumerate(expected):
 x=.75+j*3.15;deck.text(s,x,5.5,2.9,.35,label+' [V ADC]',14,True);deck.text(s,x,5.95,2.9,.45,f'{value:.4f}',23,True,sd.COLORS[1])
deck.text(s,.8,6.5,11.7,.3,f'σ input ≈ {r["sigma_expected_input_v"]*1e9:.3f} nV; p(φ) = 0.15915 rad⁻¹; |g₁(0.2 μs)| ≈ {abs(complex(*r["correlation_expected_lag1"])):.4f}.',12)
# Retain the later science pages, replacing all comparisons to previous simulations.
deck.slides+=old[12:]
# Amplitude fit comparison: use common ADC units and label nominal scaling.
i=next(i for i,s in enumerate(deck.slides) if s['title'].startswith('Rayleigh fit: expected scale'))
s=page('Amplitude fit: measured scale versus simulation',
 'Run 680 full-run Rayleigh fit · simulation expectations use nominal ADC scaling',
 'Full-run binned MLE loc=0, same fits as preceding revision. Model/fit ratios refer to fitted raw amplitude scale; small differences from AC RMS ratios arise from offsets. Do not infer an absolute gain correction from this comparison.',
 'Sources: full-run v2 histograms and fitted scales; data/rayleigh_fit.json; data/simulation_model/metrics.json.')
heads=['Mode','Fit σ [mV]','Model σ [mV]','Model / fit','Fit σ [nV input]','CDF gap'];xs=[.75,2.25,4.4,6.8,8.7,11.25];ws=[1.3,2.,2.2,1.8,2.3,1.7]
for x,w,text in zip(xs,ws,heads):deck.text(s,x,2,w,.65,text,14,True)
for j,fit in enumerate(fits):
 r=modes[fit['mode']];pred=r['sigma_expected_input_v']*gain
 vals=[fit['mode'],f"{fit['sigma_v']*1e3:.3f}",f'{pred*1e3:.2f}',f"{pred/fit['sigma_v']:.2f}",f"{fit['sigma_v']/gain*1e9:.3f}",f"{fit['cdf_edge_max_distance']:.5f}"]
 for x,w,text in zip(xs,ws,vals):deck.text(s,x,3+j*.6,w,.4,text,18)
deck.text(s,.8,5.1,11.7,1.25,'p(A) = A/σ² exp[−A²/(2σ²)], A ≥ 0; location = 0; RMS(A) = √2 σ.\nThe amplitude shape is close to Rayleigh, while the model scale is much larger.\nA common scalar gain adjustment cannot explain the mode-dependent gaps or repair temporal coherence.',19)
deck.slides.pop();deck.slides[i]=s
# Phase plot: identical uniform null, no internal stage names in its legend.
fig,axs=plt.subplots(1,3,figsize=(13,3.2))
for ax,fit in zip(axs,fits):
 mode=fit['mode'];a=np.load(BASE/'data'/f'{mode}_phase_comparison.npz');edges=a['edges_rad'];counts=a['counts'];ax.stairs(counts/counts.sum()/np.diff(edges),edges,color='#007F86');ax.axhline(1/(2*np.pi),color='#D98726',ls='--',label='Model: uniform phase');pr=next(r for r in phase_rows if r['mode']==mode);ax.set(title=f"{mode}: resultant = {pr['first_resultant_histogram_midpoint']:.4f}",xlabel='Wrapped phase [rad]',ylabel='Density [rad⁻¹]');ax.legend(fontsize=8)
fig.tight_layout();path=A/'phase_expected_measured.png';fig.savefig(path,dpi=180);plt.close(fig)
s=next(s for s in deck.slides if s['title'].startswith('Phase: uniform expectation'))
s['subtitle']='Circular Gaussian model: uniform marginal phase; compare with the complete run'
for item in s['items']:
 if item['kind']=='image':item['path']=str(path)
 if item['kind']=='text' and 'Steps 4 and 5' in item['text']:item['text']=sd.wrap(s['subtitle'],item['w'],item['size'])
s['notes']='Full-run wrapped phase histogram. Model: uniform phase with density 1/(2π), zero population circular resultant. Histogram midpoint resultants are invariant to constant reference phase. Narrow angular features and time correlations require separate checks; no iid p-value is inferred.'
# Covariance comparison uses current per-mode expected curves only.
period=Path('/home/mazzitel/HFGW/analysis-work/Run2/staging/legacy-repository/autoreco/noise_continuous/periodicity_run680/periodicity_diagnostic.npz')
fig,axs=plt.subplots(1,2,figsize=(12.5,3.5))
with np.load(period) as data,h5py.File(SIM/'step06_simulation.h5') as h:
 for mode,color in zip(modes,sd.COLORS):
  observed=data[mode+'_normalized_covariance'][:51];theory=h[mode+'/g1_expected'][:]
  for ax,part in zip(axs,(np.real,np.abs)):
   ax.plot(data['lag_s'][1:51]*1e6,part(observed[1:]),color=color,lw=1.2,label=mode+' measured')
   ax.plot(lag[1:]*1e6,part(theory[1:]),'--',color=color,alpha=.8,label=mode+' expected')
 for ax in axs:ax.set_xlabel('Lag [μs]');ax.grid(alpha=.2);ax.legend(fontsize=7.5)
 axs[0].set_ylabel('Re g₁(τ)');axs[1].set_ylabel('|g₁(τ)|')
fig.tight_layout();path=A/'correlation_expected_measured.png';fig.savefig(path,dpi=180);plt.close(fig)
s=next(s for s in deck.slides if s['title'].startswith('Temporal coherence:'))
for item in s['items']:
 if item['kind']=='image':item['path']=str(path)
 if item['kind']=='text' and 'Step 5 predicts' in item['text']:
  item['text']=sd.wrap('At 0.2 μs, predicted |g₁| ≈ 0.2317; measured |g₁| = 0.0271 / 0.0107 / 0.0094.\nThe assumed readout spectrum is too correlated at this lag. A scalar gain change cannot fix this mismatch.',item['w'],17);item['size']=17
s['source']='Sources: run 680 first five SPEC, 1.048576 s; measured-parameter model covariance. Definition and arrays in data/.'
# Clean internal workflow terminology from all audience-facing slide text and notes.
for s in deck.slides:
 s['footer']=s.get('footer','IQ NOISE STUDY').replace('v20','v21')
 if s['title']=='Single-run conclusions and next steps':
  for item in s['items']:
   if item['kind']=='text' and 'illustrative Step 5' in item['text']:
    item['text']=sd.wrap('Rayleigh describes the global amplitude shape; the nominal simulated scale and short-lag coherence do not match Run 680.',item['w'],16)
 for item in s['items']:
  if item['kind']=='image':
   path=Path(item['path']);dst=A/path.name
   if path!=dst:shutil.copy2(path,dst)
   item['path']=str(dst)
  if item['kind']=='text':
   item['text']=re.sub(r'\bSteps?\s+[456](?:\s*(?:and|/|→)\s*[456])?\b','the simulation',item['text'],flags=re.I)
   if item['y']==.38:
    while len(sd.wrap(item['text'],item['w']*.88,item['size']).splitlines())>1:item['size']-=1
 s['notes']=re.sub(r'\bSteps?\s+[456](?:\s*(?:and|/|→)\s*[456])?\b','the simulation',s['notes'],flags=re.I)
assert len(deck.slides)==35
assert all(not re.search(r'\bstep\s*[456]\b',json.dumps(s),re.I) for s in deck.slides)
# Replace the current comparison manifest while retaining old values only as archived history.
(D/'expected_vs_measured_previous_revision.json').write_text(json.dumps(previous,indent=2))
(D/'expected_vs_measured.json').write_text(json.dumps(dict(model_results=modes,rayleigh_fits=fits,full_run_phase=phase_rows,five_SPEC_covariance=covrows,calibration_status=model['status']),indent=2))
(D/'v21_revision.json').write_text(json.dumps(dict(source=str(BASE),source_model_sha256=hashlib.sha256((BASE/'slide_model.json').read_bytes()).hexdigest(),simulation_metrics_sha256=hashlib.sha256((SIM/'metrics.json').read_bytes()).hexdigest(),slides=35,changes='Measured parameter simulation replaces the two illustrative cases. All expectation comparisons updated; missing calibration directions conditional; internal stage names removed.'),indent=2))
sd.export(deck,OUT,'v21',datetime.now(ZoneInfo('Europe/Rome')).strftime('%-d %B %Y'))
(OUT/'README.md').write_text('# IQ noise summary v21\n\n35 slides. Slides 9–10: measured-parameter model and explicit calibration gaps/directions. Slide 11: one simulation result page with expected values. Subsequent amplitude, phase and temporal-coherence comparisons use the same current model. No internal simulation stage numbers appear in the presentation. Raw scientific products are unchanged.\n')
