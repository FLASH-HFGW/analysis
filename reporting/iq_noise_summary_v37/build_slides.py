"""TM010 model audit: verify raw calibration, image leakage and stable science windows."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import sys,json,shutil
import numpy as np
sys.path.insert(0,'/tmp/v18-python-deps');import pptx
sys.path.insert(0,'/home/mazzitel/HFGW/analysis/reporting');import slide_deck as sd
import matplotlib.pyplot as plt
R=Path('/home/mazzitel/HFGW');BASE=R/'analysis-work/Run2/reports/iq_noise_summary_v36';OUT=BASE.with_name('iq_noise_summary_v37');OUT.mkdir(exist_ok=True);A=OUT/'assets';D=OUT/'data';A.mkdir(exist_ok=True);shutil.copytree(BASE/'data',D,dirs_exist_ok=True)
P=R/'analysis-work/Run2/diagnostics/TM010_response_audit_20261115';Q=R/'analysis-work/Run2/diagnostics/v21_toy_comparison_verified_IQ_20261115';shutil.copytree(P,D/'TM010_audit',dirs_exist_ok=True);shutil.copytree(Q,D/'v21_reference_comparison_verified_IQ',dirs_exist_ok=True);audit=json.load(open(P/'audit.json'));assert audit['status']=='complete';deck=sd.Deck();deck.slides=json.loads((BASE/'slide_model.json').read_text());names=('TM010','TM011','TM012')
def textset(s,y,txt,size=None):
 for x in s['items']:
  if x['kind']=='text' and abs(x['y']-y)<1e-6:x['text']=sd.wrap(txt,x['w'],size or x['size']);x['size']=size or x['size']
def page(title,sub,source):
 dd=sd.Deck();s=dd.new(' ',sub,source);s['title']=title;x=next(v for v in s['items'] if v['kind']=='text' and v['y']==.38);x['text']=title
 while len(sd.wrap(title,x['w']*.88,x['size']).splitlines())>1:x['size']-=1
 return s

def table(s,heads,rows,widths=None,y=1.9,size=12,step=.5):
 widths=widths or [11.9/len(heads)]*len(heads)
 for i,row in enumerate([heads]+rows):
  xx=.7
  for txt,w in zip(row,widths):deck.text(s,xx,y if i==0 else y+.85+(i-1)*step,w-.08,.65 if i==0 else .47,str(txt),size,i==0);xx+=w
# Verified raw sign: archive and native toy use I-jQ. Remove unnecessary toy-only mirror.
fig,axs=plt.subplots(3,2,figsize=(13,7.2))
for i,mode in enumerate(names):
 a=np.load(Q/f'{mode}_comparison.npz')
 for j,pop in enumerate(('toy','data')):
  axs[i,j].plot(a['frequency_hz']/1e6,10*np.log10(a[pop+'_psd_v2_hz']),color='#7657A6' if pop=='toy' else '#007F86',lw=.45);axs[i,j].set(title=mode+' · '+('toy' if pop=='toy' else 'run680 · original v21'),xlabel='Baseband frequency [MHz] · verified I−jQ',ylabel='PSD [dBV²/Hz]',xlim=(-2.5,2.5))
 low=min(ax.get_ylim()[0] for ax in axs[i]);high=max(ax.get_ylim()[1] for ax in axs[i])
 for ax in axs[i]:ax.set_ylim(low,high)
 old=np.load(D/'v21_reference_comparison'/f'{mode}_comparison.npz');assert np.array_equal(a['data_g1'],old['data_g1']);assert np.array_equal(a['data_psd_v2_hz'],old['data_psd_v2_hz']);np.testing.assert_allclose(a['toy_g1'].real,old['toy_g1'].real,atol=2e-15,rtol=2e-13);np.testing.assert_allclose(abs(a['toy_g1']),abs(old['toy_g1']),atol=2e-15,rtol=2e-13)
fig.tight_layout();p=A/'spectra_verified_raw_IQ_convention.png';fig.savefig(p,dpi=190);plt.close(fig)
for x in deck.slides[19]['items']:
 if x['kind']=='image':x['path']=str(p)
deck.slides[19]['source']='Original v21 measured PSD retained with established ADC factor0.16. Raw tones verify archived and native toy I−jQ; previous unnecessary toy spectrum mirror removed. Real/absolute covariance unchanged.'
# Main interpretation reflects evidence, not an arbitrary model correction.
s=page('TM010: measured IQ response exposes limits of the scalar toy','Original run680 analysis retained · active scalar toy preserved · diagnostic image-inclusive prediction evaluated separately','18 raw calibration runs; independently integrated tone/image power; five disjoint science windows; TM010_audit/audit.json.')
deck.bullets(s,.8,1.85,11.7,[
'Raw calibration near +49 kHz: I/Q tone amplitude≈1.90, quadrature error≈41°, image/main power≈23%. Controls TM011/TM012 have≈0.03% image power.',
'The dip exists in measured calibration points. Raw chunk tone power matches archived calibration within0.03% in amplitude; interpolation or a wrong FFT peak is not the principal cause.',
'Including both sidebands raises predicted noise near ±50 kHz from47% to58% of the plateau; measured noise is94%. Image leakage explains only part of the discrepancy.',
'At fixed assumed gain/noise, TM010 RMS is43.07mV (scalar toy),43.27mV (+image), versus≈32.26mV measured. Adding positive noise alone cannot repair both amplitude and spectral shape.',
'The science discrepancy is stable in five windows across the run. Next model must separate main/image response and noise-source locations; no fitted gain or flat floor has been adopted.'
],17,.18);deck.slides[41]=s
# Detailed raw-calibration audit, explicit controls.
s=page('TM010 calibration: raw IQ imbalance and image leakage','Independent raw check on18 calibration runs · near-zero-IF comparison below uses the +49kHz tone','Raw sin/cos IQ fits for relative gain/phase; independent chunk-integrated FFT for absolute tone/image power; same saved ADC range±5V.')
rows=[]
for mode in names:
 r=audit['summary'][mode];rows.append([mode,f"{r['tone_I_over_Q_at_plus50k']:.3f}",f"{r['quadrature_error_deg_at_plus50k']:+.2f}",f"{100*r['image_to_main_power_at_plus50k']:.3f}%",f"{r['noise_to_plateau_at50k']['data_relative_plateau']:.3f}",f"{r['noise_to_plateau_at50k']['scalar_relative_plateau']:.3f}",f"{r['noise_to_plateau_at50k']['image_relative_plateau']:.3f}"])
table(s,['Mode','Tone I/Q\namplitude','Quadrature\nerror [°]','Image/main\npower','Data50k\n/plateau','Scalar toy\n50k/plateau','+image\n50k/plateau'],rows,size=11)
deck.text(s,.8,5.15,11.7,.7,'The thesis routes TM010 directly from the first IQ conversion to the low-pass/ADC path. TM011/TM012 first occupy≈44/104MHz and undergo additional downconversion. They are not identical low-IF calibration paths.',14)
deck.text(s,.8,6.,11.7,.6,'Near50kHz the measured science I/Q noise RMS ratio is0.981, versus1.897 for the calibration tone. The strong tone imbalance is absent from noise. Scalar calibration alone cannot identify noise-source locations; setup/response changes remain possible.',14);deck.slides.append(s)
# Stability without replacing original first-five-SPEC analysis.
s=page('TM010 mismatch persists across the run','Five disjoint5-SPEC windows · each1.048576s · additional diagnostic only; original first-window analysis unchanged','Read-only raw run680 audit; window PSD/covariance arrays saved under data/TM010_audit/.')
rows=[]
for win in audit['science_windows']:
 r=win['modes']['TM010'];rows.append([str(win['first_SPEC']),f"{win['first_SPEC']*1048576/5e6:.1f}",f"{r['RMS_AC_v']*1000:.3f}",f"{r['central_50k_over_plateau']:.4f}",f"{r['Re_g1_0p4']:+.5f}"])
table(s,['First SPEC','Start [s]','AC RMS [mV]','Noise50k/plateau','Re g₁(0.4μs)'],rows,y=1.85,size=12)
r=audit['results']['TM010'];deck.text(s,.8,5.7,11.7,.85,f"Scalar expectation Re g₁(0.4μs)={r['scalar']['Re_g1_0p4']:+.5f}; image-inclusive expectation={r['image_inclusive']['Re_g1_0p4']:+.5f}. All five measured windows remain near+0.021. The discrepancy is not caused by selecting the first20ms or one transient window.",15);deck.slides.append(s)
s=page('Revised toy architecture: sidebands and noise-source locations','Proper independent input sidebands · diagnostic extension only · no fitted gain or added-noise term adopted','Measured main/image tone powers; thesis IQ-imbalance equations and analog chain; conditional67.4dB+kz reference-plane hypothesis retained.')
deck.text(s,.8,1.95,11.7,.8,'Sout(f) = |A(f)|² Sin,+(f) + |B(−f)|² Sin,−(−f) + Sadd(f)',22,True)
deck.bullets(s,.8,3.0,11.7,[
'A: measured main-tone response. B: measured image response. The archived calibration supplies their powers; raw IQ also exposes gain and quadrature errors.',
'Sadd represents noise generated after some calibrated stages. Its physical location and gain must be constrained; a fitted constant floor does not establish a receiver-noise model.',
'The image-inclusive expected PSD is a useful partial correction, but it still misses TM010 shape and scale. A full IQ Monte Carlo needs a response/covariance matrix and a consistent receiver-noise budget.',
'The current full-run toy and all original run680 products remain the baseline. Compare diagnostic alternatives explicitly; do not absorb residuals into a new scalar gain.'
],17,.18);deck.slides.append(s)
# Keep the earlier mechanism slide, now point to the verified calibration evidence.
textset(deck.slides[46],5.85,'The dip is confirmed in raw calibration, with strong IQ imbalance/image leakage near zero IF. Including the image partly fills the modeled deficit but does not reproduce measured noise. The following audit separates verified response errors from unmeasured noise-source assumptions.',14)
# Make active provenance explicit without altering old evidence.
active=json.load(open(D/'active_comparison.json'));active['comparison_source']='v21_reference_comparison_verified_IQ/comparison.json';active['IQ_convention']='Raw calibration verifies I-jQ archive/native toy; previous unnecessary toy-only spectral mirror corrected. Measured arrays and real/modulus covariance unchanged.';active['TM010_audit']='TM010_audit/audit.json; image-inclusive expected PSD only, not replacement of active full-run toy';(D/'active_comparison.json').write_text(json.dumps(active,indent=2))
# Normalize prose spacing only, never filenames or arrays.
import re
def prose(txt):
 for old,new in [('run680','run 680'),('on18','on 18'),('near+','near +'),('within0.03','within 0.03'),('from47','from 47'),('to58','to 58'),('is94','is 94'),('is43','is 43'),('versus≈','versus ≈'),('five disjoint5','five disjoint 5'),('each1.','each 1.'),('first20','first 20'),('ADC±','ADC ±'),('near50','near 50'),('Near50','Near 50'),('is0.','is 0.'),('versus1.','versus 1.'),('Data50k','Data 50k'),('Noise50k','Noise 50k'),('calibration within','calibration within'),('disjoint5-','disjoint 5-'),('at fixed','at fixed')]:txt=txt.replace(old,new)
 return re.sub(r'(?<=\d)(?=(?:μs|ms|s|MHz|kHz|mV|dB|V)\b)',' ',txt)
for ss in deck.slides:
 ss['footer']=ss.get('footer','IQ NOISE STUDY').replace('v36','v37')
 for key in ('source','subtitle'):ss[key]=prose(ss.get(key,''))
 for x in ss['items']:
  if x['kind']=='image':
   src=Path(x['path']);dst=A/src.name
   if src!=dst:shutil.copy2(src,dst)
   x['path']=str(dst)
  if x['kind']=='text':x['text']=prose(x['text'])
sd.export(deck,OUT,'v37',datetime.now(ZoneInfo('Europe/Rome')).strftime('%-d %B %Y'))
(OUT/'README.md').write_text('# v37\n\nTM010 audit: raw IQ imbalance and image leakage verified; original data analysis preserved. Independent chunk-integrated calibration matches archives within0.03% at18 checked points. Five disjoint science windows show stable low-IF discrepancy. Image-inclusive expected PSD partially fills the deficit but does not resolve normalization. No new gain/noise floor adopted. Native toy spectral orientation corrected to raw-verified I-jQ; real/modulus covariance and original measured arrays invariant. Active scalar toy remains the baseline. Evidence and unresolved physical assumptions in data/TM010_audit/README.md.\n')
