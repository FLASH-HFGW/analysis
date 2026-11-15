"""v22: ODB-correct ADC units and a declared alternative calibration reference plane."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import sys,json,shutil,re,hashlib
import numpy as np,h5py
sys.path.insert(0,'/tmp/v18-python-deps')
import pptx
sys.path.insert(0,'/home/mazzitel/HFGW/analysis/reporting')
import slide_deck as sd
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
BASE=Path('/home/mazzitel/HFGW/analysis-work/Run2/reports/iq_noise_summary_v21')
OUT=BASE.with_name('iq_noise_summary_v22');OUT.mkdir(exist_ok=True);A=OUT/'assets';A.mkdir(exist_ok=True);D=OUT/'data';D.mkdir(exist_ok=True)
TOY=Path('/home/mazzitel/HFGW/analysis-work/Run2/simulation/toy_measured_response')
AUDIT=Path('/home/mazzitel/HFGW/analysis-work/Run2/diagnostics/normalization_audit_20261114')
shutil.copytree(BASE/'data',D/'previous_revision',dirs_exist_ok=True)
shutil.copytree(TOY,D/'toy_model',ignore=shutil.ignore_patterns('assets'),dirs_exist_ok=True)
for name in ('campaign_ADC_ranges.json','calibration_reconstruction.json','thesis_reference_plane_review.json','campaign_ADC_corrected_summary.csv'):shutil.copy2(AUDIT/name,D/name)
old=json.loads((BASE/'slide_model.json').read_text());deck=sd.Deck();deck.slides=old
m=json.loads((TOY/'metrics.json').read_text());modes=m['results'];colors=sd.COLORS
snap=json.loads((BASE/'data/baseline_v17/snapshot.json').read_text());H5=Path(snap['run680_v2']['path'])
source='Sources: BOR ODB (range applied by frontend); reconstructed tone calibration; thesis Ch.5–6. Gain reference plane is an explicit hypothesis.'
def new(title,subtitle,notes='',src=source):
 temp=sd.Deck();s=temp.new(title,subtitle,src,notes);s['footer']='TOY SIMULATION | EXPLICIT NORMALIZATION HYPOTHESIS | DECK v22';return s

def figsave(fig,name):
 p=A/(name+'.png');fig.tight_layout();fig.savefig(p,dpi=180);plt.close(fig);return p

def replace_image(s,p):
 for item in s['items']:
  if item['kind']=='image':item['path']=str(p)

def set_text(s,old_start,text,size=None):
 for item in s['items']:
  if item['kind']=='text' and item['text'].startswith(old_start):
   item['text']=sd.wrap(text,item['w'],size or item['size'])
   if size:item['size']=size
# Definitions: replace scalar input normalization with the actual spectral prescription.
s=deck.slides[3]
set_text(s,'σA =','σA = std(A) differs from RMS_AC. ADC range is read per run/channel from the ODB.\nInput power per FFT bin = ADC V²/bin ÷ [50 Ω × kz(f)² × 10^(67.4/10)], under the stated gain hypothesis.',13)
s['notes']='Science IQ channels are ±2 V, calibration IQ channels ±5 V. Use 2*range/65535 V/count. kz is mode/frequency dependent; a scalar 143 dB division is not used for current absolute comparisons. Noise-window normalization and coherent-tone calibration are handled separately.'
# ODB validation scope on the storage page, without misrepresenting legacy HDF5 units.
set_text(deck.slides[6],'GPFS publication','Current plots correct archived HDF5 ADC voltages by ×0.4, using the verified ODB ranges.',15)
# Page 9: known inputs and the selected alternative plane.
s=new('Toy simulation: measured inputs and response',
 'Three cavity modes · T = 40.422 mK · receiver Tn = 3.955 ± 0.468 K · no coherent tone',
 'Cavity frequency/Q/coupling from thesis Table6.1; temperature from observed run680 T15. Receiver temperature is inherited, not fitted. Measured integrated-tone kz replaces the assumed fourth-order LPF; no extra LPF is multiplied into kz. Upstream gain67.4dB assumes the additional36dB FET is already included in the measured DAQ response. The thesis explicitly prescribes103.4dB separately; the alternative used here is not demonstrated by agreement alone.')
blocks=[(.6,'THERMAL CAVITY','Measured f₀, Q₀, κ₁, κ₂\nObserved AVS T15',colors[0]),(3.85,'RECEIVER NOISE','Equivalent Tn = 3.955 K\nWhite input-referred PSD',colors[2]),(7.1,'GAIN + DAQ RESPONSE','67.4 dB upstream*\nMeasured kz(f), per mode',colors[1]),(10.35,'ADC','Science ±2 V, 16 bit\nCalibration ±5 V; 5 MS/s',sd.NAVY)]
for x,title,text,col in blocks:
 deck.rect(s,x,1.85,2.95,1.25,'#FFFFFF');deck.text(s,x+.1,2,2.75,.35,title,12,True,col);deck.text(s,x+.1,2.5,2.75,.6,text,12)
for x in (3.54,6.79,10.04):deck.text(s,x,2.3,.3,.4,'→',20)
xs=[.75,2.05,3.85,5.1,7.25,9.15,11.15];ws=[1.2,1.7,1.2,2,1.7,1.8,1.8]
for x,w,t in zip(xs,ws,['Mode','f₀ [GHz]','Q₀','κ₁ / κ₂','Q loaded','FWHM [kHz]','τ cavity [μs]']):deck.text(s,x,3.5,w,.4,t,13,True)
for j,(mode,r) in enumerate(modes.items()):
 vals=[mode,f"{r['f0_hz']/1e9:.6f}",f"{r['q0']:,.0f}",f"{r['kappa1']:.4g} / {r['kappa2']:.2f}",f"{r['ql']:,.0f}",f"{r['fwhm_hz']/1e3:.2f}",f"{r['tau_amplitude_s']*1e6:.3f}"]
 for x,w,t in zip(xs,ws,vals):deck.text(s,x,4.15+j*.55,w,.4,t,14)
deck.text(s,.8,5.95,11.7,.7,'*Hypothesis: the calibration tone traversed the external 36 dB FET, so its gain is already in kz. Remaining RF gain = 103.4 − 36 = 67.4 dB. Confirmation is required.',16)
deck.slides[8]=s
# Page10: editable native diagram and a prominent open question.
s=new('Normalization hypothesis: the critical injection point',
 'Question to resolve: was the −60 dBm calibration tone injected before or after the external RF FET?',
 m['assumption']+' '+m['open_question']+' The thesis prescribed calibration keeps103.4dB and kz separate; dropping36dB is an explicit alternative, chosen for the comparison without fitting per-mode gains. A closer result is not proof of the injection node.')
blocks=[(.65,2.35,2.5,'CAVITY + READOUT LINE','Upstream gain ≈67.4 dB',colors[0]),(3.65,2.35,2.2,'EXTERNAL RF FET','Gain ≈36 dB',colors[2]),(6.4,2.35,3.,'I/Q + FILTERS','Frequency-dependent response',colors[1]),(10,2.35,2.65,'ADC','Calibration ±5 V; science ±2 V',sd.NAVY)]
for x,y,w,title,text,col in blocks:
 deck.rect(s,x,y,w,1.15,'#FFFFFF');deck.text(s,x+.1,y+.15,w-.2,.35,title,12,True,col);deck.text(s,x+.1,y+.72,w-.2,.32,text,10)
for x in (3.2,5.95,9.5):deck.text(s,x,2.8,.4,.4,'→',23)
deck.text(s,3.15,1.65,1.,.5,'A ↓',21,True,colors[2]);deck.text(s,5.9,1.65,1.,.5,'B ↓',21,True,colors[2])
deck.rect(s,3.4,2.1,.025,.7,colors[2]);deck.rect(s,6.15,2.1,.025,.7,colors[2])
deck.text(s,.8,4.05,11.7,.8,'A: tone crosses the FET → kz includes its gain → use 67.4 dB upstream.\nB: tone bypasses the FET → keep the FET separate → use 103.4 dB upstream.',19)
deck.rect(s,.7,5.25,11.9,1.25,'#FFFFFF');deck.text(s,.9,5.42,11.5,.85,'ASSUMPTION USED: A — kz already includes the external 36 dB FET.\nUse 67.4 dB upstream. No per-mode gain is fitted.\nThe injection point remains unconfirmed; residual differences are retained.',17,True,colors[0])
deck.slides[9]=s
# Page11: per-mode expected numbers under the same declared hypothesis.
s=new('Toy simulation: expected observables',
 'Measured kz(f) replaces the ideal LPF · all numbers use the confirmed ±2 V science ADC range',
 '20ms stationary complex Gaussian realization. Measured transfer magnitude, integrated-tone calibration with Hann ENBW accounted for. Response outside measured roughly±3MHz range set tozero; modeled aliasing included within that range. No measured transfer phase or calibrated transient response is asserted. Tn remains an assumed applicable thesis measurement.')
p=A/'toy_expected_observables.png';shutil.copy2(TOY/'assets/toy_expected_observables.png',p);deck.image(s,.5,1.75,12.3,3.2,p)
heads=['Mode','σ [mV ADC]','mean(A) [mV]','std(A) [mV]','RMS(A) [mV]'];xs=[.8,2.8,5.3,7.8,10.3]
for x,t in zip(xs,heads):deck.text(s,x,5.1,2.4,.4,t,13,True)
for j,(mode,r) in enumerate(modes.items()):
 for x,t in zip(xs,[mode]+[f'{r[k]*1e3:.3f}' for k in ('sigma_adc_v','mean_amplitude_adc_v','std_amplitude_adc_v','rms_adc_v')]):deck.text(s,x,5.65+j*.34,2.4,.3,t,14)
deck.text(s,.8,6.7,11.7,.2,'Phase: uniform, p(φ)=1/(2π); covariance is predicted separately for each measured mode response.',10)
deck.slides[10]=s
# Full-run raw amplitude histogram and time envelope with corrected ADC scale.
fits=json.loads((BASE/'data/rayleigh_fit.json').read_text())['fits']
for r in fits:
 for k in ('sigma_v','model_mean_v','model_std_v','model_rms_v','empirical_mean_v','complex_offset_v'):r[k]*=.4
fig,axs=plt.subplots(3,2,figsize=(13,8))
with h5py.File(H5) as h:
 for j,r in enumerate(fits):
  mode=r['mode'];a=np.load(BASE/'data'/f'{mode}_rayleigh_histogram.npz');edges=a['amplitude_edges_v']*.4;n=a['counts'];expected=a['expected_counts']
  ax=axs[j,0];ax.stairs(n,edges*1e3,color=colors[j]);ax.plot((edges[:-1]+edges[1:])*500,expected,color='#D98726',label='Rayleigh fit');ax.set_yscale('log');ax.set_ylim(.5,max(n)*2);ax.set(title=f"{mode} · σ={r['sigma_v']*1e3:.3f} mV",ylabel='Counts / bin');ax.legend(fontsize=8)
  g=h['modes/'+mode];t=(np.arange(len(g['envelope_mean_v']))+.5)*209.7152/len(g['envelope_mean_v']);ax=axs[j,1];ax.fill_between(t,g['envelope_min_v'][:]*400,g['envelope_max_v'][:]*400,color=colors[j],alpha=.25);ax.plot(t,g['envelope_mean_v'][:]*400,color=colors[j],lw=.5);ax.set(title=mode+' · interval mean and min–max',ylabel='ADC amplitude [mV]')
 axs[-1,0].set_xlabel('ADC amplitude [mV]');axs[-1,1].set_xlabel('Acquired time [s]')
p=figsave(fig,'run680_rayleigh_ADC_corrected');replace_image(deck.slides[12],p);deck.slides[12]['subtitle']='Full run · 1,048,576,000 samples/mode · ADC range ±2 V validated from ODB'
for item in deck.slides[12]['items']:
 if item['kind']=='text' and item['y']==1.12:item['text']=sd.wrap(deck.slides[12]['subtitle'],item['w'],item['size'])
# Fit comparison: only ADC units, no unsupported scalar input-equivalent volts.
s=new('Amplitude fit versus toy simulation',
 'Same ADC units and declared normalization hypothesis · one common gain choice, no mode-by-mode tuning')
heads=['Mode','Fit σ [mV]','Toy σ [mV]','Toy / fit','Measured RMS [mV]','Toy RMS [mV]'];xs=[.7,2.15,4.2,6.2,8.2,10.65]
for x,t in zip(xs,heads):deck.text(s,x,2,2.1,.7,t,14,True)
for j,r in enumerate(fits):
 t=modes[r['mode']];vals=[r['mode'],f"{r['sigma_v']*1e3:.3f}",f"{t['sigma_adc_v']*1e3:.3f}",f"{t['sigma_adc_v']/r['sigma_v']:.3f}",f"{t['observed_ac_rms_adc_v']*1e3:.3f}",f"{t['rms_adc_v']*1e3:.3f}"]
 for x,v in zip(xs,vals):deck.text(s,x,3+j*.6,2.1,.4,v,18)
deck.text(s,.8,5.15,11.7,1.3,'RMS residuals: TM010 +33.5%, TM011 +4.7%, TM012 −3.0%.\nAgreement improves under hypothesis A; this does not independently establish the calibration plane. TM010 still differs materially. Rayleigh shape alone does not identify the noise source.',19)
deck.slides[13]=s
# IQ density / maxima, exact count grid with corrected axis units.
with h5py.File(H5) as h:
 g=h['modes/TM010'];fig,axs=plt.subplots(1,2,figsize=(12,4.6));c=g['iq_counts'][:];xx=g['iq_i_edges_v'][:]*400;yy=g['iq_q_edges_v'][:]*400
 axs[0].pcolormesh(xx,yy,c.T,norm=LogNorm(vmin=1,vmax=c.max()),cmap='magma');axs[0].set_title('All-sample IQ density')
 cls=g['peak_sigma_class'][:]
 for k,col in ((3,colors[0]),(5,colors[1]),(7,colors[2])):
  mask=cls==k;axs[1].scatter(g['peak_i_v'][:][mask]*400,g['peak_q_signed_v'][:][mask]*400,s=4,color=col,label=f'Class {k}')
 axs[1].set_title('Selected interval maxima');axs[1].legend(fontsize=8)
 for ax in axs:ax.set(xlabel='I at ADC [mV]',ylabel='−Q at ADC [mV]');ax.set_aspect('equal','box')
 p=figsave(fig,'IQ_density_ADC_corrected');replace_image(deck.slides[16],p)
# Continuous spectrum: shift dimensional power only; normalized covariance unchanged.
period=Path('/home/mazzitel/HFGW/analysis-work/Run2/staging/legacy-repository/autoreco/noise_continuous/periodicity_run680/periodicity_diagnostic.npz')
fig,axs=plt.subplots(3,2,figsize=(12.5,7.2))
with np.load(period) as data:
 f=data['frequency_hz'];lags=data['lag_s']
 for j,mode in enumerate(modes):
  power=data[mode+'_periodogram_v2_per_hz']*.16;factor=256
  ff=f.reshape(-1,factor).mean(axis=1);pp=power.reshape(-1,factor).mean(axis=1)
  axs[j,0].plot(ff/1e6,10*np.log10(pp),lw=.8,color=colors[j]);axs[j,0].set(title=mode+' · first 5 SPEC',ylabel='PSD [dBV²/Hz]')
  g=data[mode+'_normalized_covariance'];axs[j,1].plot(lags[1:51]*1e6,g.real[1:51],'.-',ms=2,color=colors[j]);axs[j,1].set(title=mode+' · normalized covariance',ylabel='Re g₁')
 axs[-1,0].set_xlabel('Complex baseband [MHz]');axs[-1,1].set_xlabel('Lag [μs]')
p=figsave(fig,'spectral_check_ADC_corrected')
s=new('Run 680: spectrum and temporal correlations',
 'First five continuous SPEC · 1.048576 s · PSD corrected for the ±2 V ADC range',
 'Power spectral density uses correct Hann energy normalization; covariance spans SPEC boundaries with one mean removed. Displayed spectrum is frequency-averaged for readability. No fitted decay is identified with a deterministic oscillation period.')
deck.image(s,.55,1.75,12.2,4.85,p);deck.slides[18]=s
# Actual measured-response covariance compared against data, same scope as before.
fig,axs=plt.subplots(1,2,figsize=(12.5,3.5))
with np.load(period) as data,h5py.File(TOY/'toy_simulation.h5') as toy:
 lag=toy['lag_s'][:]
 for mode,col in zip(modes,colors):
  pred=toy[mode+'/g1_expected'][:];obs=data[mode+'_normalized_covariance'][:51]
  for ax,part in zip(axs,(np.real,np.abs)):
   ax.plot(lag[1:]*1e6,part(obs[1:]),color=col,lw=1.2,label=mode+' data');ax.plot(lag[1:]*1e6,part(pred[1:]),'--',color=col,lw=1.2,label=mode+' toy')
 for ax in axs:ax.set_xlabel('Lag [μs]');ax.legend(fontsize=8);ax.grid(alpha=.2)
 axs[0].set_ylabel('Re g₁');axs[1].set_ylabel('|g₁|')
p=figsave(fig,'toy_coherence_comparison');s=deck.slides[19];replace_image(s,p)
set_text(s,'At 0.2','At 0.2 μs, toy/data |g₁|: TM010 0.0511/0.0271; TM011 0.0179/0.0107; TM012 0.0085/0.0094.\nThe measured DAQ response improves the comparison, with residual mode-dependent differences.',17)
s['source']='Sources: first five SPEC continuous covariance; toy simulation with measured kz(f), hypothesis A. Scalar gain changes do not affect g₁.'
# DC comparison, same samples and filters, both voltage axes corrected.
metrics=json.loads((BASE/'data/baseline_v17/run680_v2_dc_comparison.json').read_text());fig,ax=plt.subplots(figsize=(10,3.7));x=np.arange(3)
ax.bar(x-.17,[r['central_v1_mv']*.4 for r in metrics],.34,color=colors[1],label='DC retained');ax.bar(x+.17,[r['central_v2_mv']*.4 for r in metrics],.34,color=colors[0],label='One run mean removed');ax.set(xticks=x,xticklabels=[r['mode'] for r in metrics],ylabel='Central-band RMS at ADC [mV]');ax.legend();p=figsave(fig,'run680_dc_ADC_corrected');replace_image(deck.slides[20],p)
set_text(deck.slides[20],'Normalization is separate','ADC values use ODB ±2 V. DC-removal percentages are unchanged; RF normalization uses kz(f) and hypothesis A.',14)
# Current findings and actionable uncertainty, without obsolete missing-kz/scalar-gain language.
for s in deck.slides:
 for item in s['items']:
  if item['kind']=='text':
   text=item['text']
   if 'nominal simulated scale' in text:text='Toy/data agreement depends on the stated gain-plane hypothesis; amplitude and coherence still differ by mode.'
   if 'Obtain numerical kz' in text:text='Confirm the tone injection node and the stages included in kz(f).'
   if 'Compare against independent gain' in text:text='Validate the injection reference plane and an independent noise calibration.'
   item['text']=sd.wrap(text,item['w'],item['size'])
  if item['kind']=='image':
   path=Path(item['path']);dst=A/path.name
   if path!=dst:shutil.copy2(path,dst)
   item['path']=str(dst)
  if item['kind']=='text' and item['y']==.38:
   while len(sd.wrap(item['text'],item['w']*.88,item['size']).splitlines())>1:item['size']-=1
 s['footer']=s.get('footer','IQ NOISE STUDY').replace('v21','v22')
 s['notes']+=' Current ADC correction: all 260 science runs have ±2 V on six IQ channels, while tone calibration has ±5 V. Dimensional ADC quantities shown here apply factor0.4 to legacy voltage or0.16 to legacy mean-square voltage. Dimensionless trends/counts/phase/coherence are unchanged. Current absolute comparison assumes the extra36dB RF FET is included in measured kz and uses67.4dB upstream; this is not an independently validated calibration.'
 s['notes']=s['notes'].replace('v18 interpretation:','Amplitude-model interpretation:')
# Correct diagram source wording retained as native slide shapes.
(D/'rayleigh_fit_ADC_corrected.json').write_text(json.dumps(dict(method='Full-run binned MLE, location fixed0; exact unit rescaling after ODB validation',fits=fits),indent=2))
(D/'normalization_hypothesis.json').write_text(json.dumps(dict(ADC_science_peak_V=2,ADC_calibration_peak_V=5,RF_gain_used_db=67.4,RF_gain_thesis_db=103.4,stage_excluded_db=36,assumption=m['assumption'],open_question=m['open_question'],not_independently_calibrated=True,model_to_data_rms={k:v['model_to_measured_ac_rms'] for k,v in modes.items()}),indent=2))
(D/'revision.json').write_text(json.dumps(dict(parent=str(BASE),model_sha256=hashlib.sha256((TOY/'metrics.json').read_bytes()).hexdigest(),slides=len(deck.slides),changes='ODB-correct ADC scale, reconstructed measured transfer response, declared gain-plane assumption, native critical-point diagram, corrected dimensional figures; no per-mode fitted gain.'),indent=2))
assert len(deck.slides)==35
sd.export(deck,OUT,'v22',datetime.now(ZoneInfo('Europe/Rome')).strftime('%-d %B %Y'))
(OUT/'README.md').write_text('# IQ noise summary v22\n\n35 slides. Current scientific plots apply ODB ±2 V to science and ±5 V to tone calibration. Toy simulation uses measured integrated-tone kz and assumes its response already contains the extra36dB FET; upstream gain67.4dB. This alternative is selected for the comparison, not proven by it. Slide10 shows the critical injection node and explicit question. ADC-dimensional figures rebuilt; dimensionless relative trends remain unchanged. Legacy HDF5 files remain archived in their original scaling; corrected summaries and derived figures are versioned here.\n')
