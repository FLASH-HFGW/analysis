"""Add per-SPEC timing to slide8 and explain the original toy TM010 covariance."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import sys,json,shutil
import numpy as np,h5py
sys.path.insert(0,'/tmp/v18-python-deps');import pptx
sys.path.insert(0,'/home/mazzitel/HFGW/analysis/reporting');import slide_deck as sd
import matplotlib.pyplot as plt
R=Path('/home/mazzitel/HFGW');BASE=R/'analysis-work/Run2/reports/iq_noise_summary_v35';OUT=BASE.with_name('iq_noise_summary_v36');OUT.mkdir(exist_ok=True);A=OUT/'assets';D=OUT/'data';A.mkdir(exist_ok=True);shutil.copytree(BASE/'data',D,dirs_exist_ok=True);deck=sd.Deck();deck.slides=json.loads((BASE/'slide_model.json').read_text())
P=R/'analysis-work/Run2/diagnostics/toy_TM010_notch_20261115';shutil.copytree(P,D/'TM010_response_diagnosis',dirs_exist_ok=True);dg=json.loads((P/'diagnosis.json').read_text())
def textset(s,y,txt,size=None):
 for x in s['items']:
  if x['kind']=='text' and abs(x['y']-y)<1e-6:x['text']=sd.wrap(txt,x['w'],size or x['size']);x['size']=size or x['size']
def page(title,sub,source):
 dd=sd.Deck();s=dd.new(' ',sub,source);s['title']=title;x=next(v for v in s['items'] if v['kind']=='text' and v['y']==.38);x['text']=title
 while len(sd.wrap(title,x['w']*.88,x['size']).splitlines())>1:x['size']-=1
 return s
s=deck.slides[7];s['items']=[v for v in s['items'] if not(v['kind']=='text' and v['y']>=1.8)]
heads=['Configuration','Elapsed [min]','CPU [min]','Mean cores','ηworker [%]'];widths=[4.1,2.,2.,1.8,2.];rows=[];rec=json.loads((D/'hpc_JOB_4407/benchmark_summary.json').read_text())
for label,w,t in [('HPC · 1 worker',1,rec['timings_1worker']),('HPC 4407 · 3 workers*',3,rec['timings_3workers'])]:
 v=t['total'];r=v['cpu_s']/v['wall_s'];rows.append([label,f"{v['wall_s']/60:.1f}",f"{v['cpu_s']/60:.1f}",f'{r:.3f}',f'{100*r/w:.1f}'])
for job in json.loads((D/'four_job_timings.json').read_text()):
 v=job['timings']['total'];r=v['cpu_s']/v['wall_s'];w=job['workers'];rows.append([f"HTC {job['job']} · {w} worker",f"{v['wall_s']/60:.1f}",f"{v['cpu_s']/60:.1f}",f'{r:.3f}',f'{100*r/w:.1f}'])
for i,row in enumerate([heads]+rows):
 xx=.7
 for txt,w in zip(row,widths):deck.text(s,xx,1.8 if i==0 else 2.35+(i-1)*.34,w-.08,.45 if i==0 else .32,txt,12,i==0);xx+=w
for xx,w,txt in ((.7,6.,'Python profile · all 3 modes'),(6.9,2.6,'Total 50 SPEC [s]'),(9.65,2.8,'Average / SPEC [s]')):deck.text(s,xx,4.55,w,.35,txt,12,True)
summary=json.loads((D/'worker_profile/summary.json').read_text());sc=summary['instrumentation']['profile_3workers']['scopes'];timingrows=[['27 filters · FilteredBandChecks.update',sc['filtered_bands.serial']['wall_s']],['↳ FFT/IFFT',sc['band_fft']['wall_s']+sc['band_ifft']['wall_s']],['↳ Oscillators',sc['oscillator']['wall_s']]]
for i,(txt,sec) in enumerate(timingrows):
 for xx,w,t in ((.7,6.,txt),(6.9,2.6,f'{sec:.1f}'),(9.65,2.8,f'{sec/50:.3f}')):deck.text(s,xx,5.02+i*.35,w,.33,t,12)
deck.text(s,.8,6.12,11.7,.27,'Profile: local Python diagnostic, 50 SPEC = 10.49 s acquired. Nested FFT/IFFT and oscillator costs are included in the 27-filter total.',10)
deck.text(s,.8,6.43,11.7,.32,'ηworker=CPU/(workers×elapsed). * HPC physical-core allocation/original hardware unverified; apparent scaling efficiency 38.6% is not a controlled speedup.',10)
s['source']='HPC/HTC production timings above; local 50-SPEC Python function profile below. Different scopes are explicitly separated.'
# Explain the mechanism, without changing any run680 or production-toy arrays.
a=np.load(P/'response_sensitivity.npz');fig,axs=plt.subplots(1,2,figsize=(12.4,3.3));axs[0].plot(a['IF_hz']/1e6,a['kz_measured'],'o-',ms=2,color='#7657A6',label='Response used in toy');axs[0].plot(a['IF_hz']/1e6,a['kz_notch_filled'],'--',color='#e36e18',label='Notch-filled sensitivity only');axs[0].set(xlabel='IF [MHz]',ylabel='kz amplitude conversion',xlim=(-1,1),title='TM010: central conversion-response dip');axs[0].legend(fontsize=8)
t=a['lag_us'];axs[1].plot(t[1:51],a['original_expected_g1'][1:51].real,color='#7657A6',label='Expected: active toy PSD');axs[1].plot(t[1:51],a['notch_filled_expected_g1'][1:51].real,'--',color='#e36e18',label='Expected: notch-filled sensitivity')
with h5py.File(R/'analysis-work/Run2/simulation/toy_full_run680/toy_full_run680.h5') as h:
 full=h['TM010/g1_empirical'][:];expected=h['TM010/g1_expected'][:];assert np.max(abs(full.real-a['original_expected_g1'][:51].real))<.0002;np.testing.assert_allclose(expected.real,a['original_expected_g1'][:51].real,rtol=1e-12,atol=1e-12)
 axs[1].plot(t[1:51],full[1:].real,'.',ms=3,color='#263952',label='Full-run Monte Carlo check')
axs[1].axhline(0,color='gray',lw=.6);axs[1].set(xlabel='Lag [μs]',ylabel='Re g₁',xlim=(0,10),title='Negative component follows the PSD, not the fit');axs[1].legend(fontsize=7);fig.tight_layout();p=A/'TM010_response_covariance_mechanism.png';fig.savefig(p,dpi=190);plt.close(fig)
s=page('Why the TM010 toy covariance is mostly negative at short lags','g₁(0)=1 is omitted in the zoom · normalized covariance is the Fourier transform of the modeled PSD','Measured kz reconstruction; active toy PSD and full-run Monte Carlo; notch-filled curve is a diagnostic sensitivity, not an applied correction.')
deck.image(s,.65,1.7,12.,3.25,p)
deck.text(s,.8,5.05,11.7,.7,'Interpolated central kz≈107 versus shoulders≈159: central power is ≈46% of the shoulder reference. A low-frequency deficit adds a negative short-lag covariance component; zero signal mean does not require symmetric oscillation around zero.',14)
deck.text(s,.8,5.85,11.7,.8,'At 0.4 μs: active toy −0.0028; notch-filled sensitivity +0.0278. The simulation matches its expected covariance. Open model question: does the coherent-tone response apply to all receiver noise, or is downstream noise missing? No response correction is applied.',14)
deck.slides.append(s)
textset(deck.slides[21],6.55,'Original v21 data and fit retained. TM010 toy: central PSD deficit produces negative short-lag covariance; diagnostic explanation in appendix.',10)
for ss in deck.slides:
 ss['footer']=ss.get('footer','IQ NOISE STUDY').replace('v35','v36')
 for x in ss['items']:
  if x['kind']=='image':
   src=Path(x['path']);dst=A/src.name
   if src!=dst:shutil.copy2(src,dst)
   x['path']=str(dst)
sd.export(deck,OUT,'v36',datetime.now(ZoneInfo('Europe/Rome')).strftime('%-d %B %Y'))
(OUT/'README.md').write_text('# v36\n\nSlide8 adds requested total50SPEC/perSPEC timing table, distinct from production benchmarks. Original v21 measured analysis and active toy unchanged. Slide47 diagnoses TM010 short-lag negative covariance via expected PSD and a clearly labeled notch-filled sensitivity test.\n')
print(json.dumps(dg,indent=2))
