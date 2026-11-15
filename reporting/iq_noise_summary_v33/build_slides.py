"""Restore 10us plots, make 5us fits explicit; add efficiencies and threaded profiles."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,sys,shutil
import numpy as np,h5py
sys.path.insert(0,'/tmp/v18-python-deps');import pptx
sys.path.insert(0,'/home/mazzitel/HFGW/analysis/reporting');import slide_deck as sd
import matplotlib.pyplot as plt
R=Path('/home/mazzitel/HFGW');BASE=R/'analysis-work/Run2/reports/iq_noise_summary_v32';OUT=BASE.with_name('iq_noise_summary_v33');OUT.mkdir(exist_ok=True);A=OUT/'assets';D=OUT/'data';A.mkdir(exist_ok=True);shutil.copytree(BASE/'data',D,dirs_exist_ok=True)
deck=sd.Deck();deck.slides=json.loads((BASE/'slide_model.json').read_text());fits=json.loads((D/'correlation_fits.json').read_text());names=['TM010','TM011','TM012']
def textset(s,y,txt,size=None):
 for item in s['items']:
  if item['kind']=='text' and abs(item['y']-y)<1e-6:item['text']=sd.wrap(txt,item['w'],size or item['size']);item['size']=size or item['size']
def table(s,heads,rows,y=1.9,size=12,widths=None):
 widths=widths or [11.9/len(heads)]*len(heads)
 for i,row in enumerate([heads]+rows):
  xx=.7
  for txt,w in zip(row,widths):deck.text(s,xx,y if i==0 else y+.85+(i-1)*.45,w-.08,.65 if i==0 else .43,str(txt),size,i==0);xx+=w
for pageid,kind in ((21,'real'),(22,'modulus')):
 fig,axs=plt.subplots(3,2,figsize=(13,7.2))
 for i,mode in enumerate(names):
  a=np.load(D/f'{mode}_covariance_pair.npz');t=a['lag_s'][1:]*1e6;mask=t<=5.000001
  for j,(key,pop,col) in enumerate((('toy_g1','toy','#7657A6'),('data20ms_g1','run680','#007F86'))):
   z=a[key][1:];y=z.real if kind=='real' else abs(z);p=fits[f'{mode}_{pop}_{kind}']['parameters'];tt=t[mask]
   pred=p['C']+p['A']*np.exp(-tt/p['tau_us'])*(np.cos(2*np.pi*p['frequency_MHz']*tt+p['phase_rad']) if kind=='real' else 1)
   ax=axs[i,j];ax.axvspan(5,10,color='#8792a0',alpha=.09);ax.plot(t,y,'o-',ms=3,lw=.8,color=col,label=pop);ax.plot(tt,pred,'--',color='#ed7118',lw=2.3,label='Fit ≤5 μs',zorder=6)
   ax.set(title=mode+' · '+pop,xlabel='Lag [μs]',ylabel='Re g₁' if kind=='real' else '|g₁|',xlim=(0,10));ax.legend(fontsize=7,loc='upper right')
  low=min(ax.get_ylim()[0] for ax in axs[i]);high=max(ax.get_ylim()[1] for ax in axs[i])
  for ax in axs[i]:ax.set_ylim(low,high)
 fig.tight_layout();path=A/f'correlation_10us_fit5us_{kind}.png';fig.savefig(path,dpi=190);plt.close(fig)
 for item in deck.slides[pageid]['items']:
  if item['kind']=='image':item['path']=str(path)
 textset(deck.slides[pageid],1.12,'Original 0–10 μs lag range · orange dashed fit restricted to 0 < lag ≤ 5 μs · decay times at right',13)
 textset(deck.slides[pageid],6.55,'Orange dashed curve: fit evaluated on the measured lag grid, only through 5 μs. Shaded region is excluded from fitting.',10)
# Efficiency uses an explicit worker-count denominator, distinct from speedup/N.
rec=json.loads((D/'hpc_JOB_4407/benchmark_summary.json').read_text());jobs=json.loads((D/'four_job_timings.json').read_text());rows=[];eff=[]
for label,w,t in [('HPC · 1 worker',1,rec['timings_1worker']),('HPC 4407 · 3 workers*',3,rec['timings_3workers'])]:
 v=t['total'];r=v['cpu_s']/v['wall_s'];rows.append([label,f"{v['wall_s']/60:.1f}",f"{v['cpu_s']/60:.1f}",f'{r:.3f}',f'{100*r/w:.1f}']);eff.append(dict(label=label,workers=w,CPU_efficiency_percent=100*r/w))
for job in jobs:
 v=job['timings']['total'];r=v['cpu_s']/v['wall_s'];w=job['workers'];rows.append([f"HTC {job['job']} · {w} worker",f"{v['wall_s']/60:.1f}",f"{v['cpu_s']/60:.1f}",f'{r:.3f}',f'{100*r/w:.1f}']);eff.append(dict(label=str(job['job']),workers=w,CPU_efficiency_percent=100*r/w))
s=deck.slides[7];s['items']=[x for x in s['items'] if not(x['kind']=='text' and x['y']>=1.8)];table(s,['Configuration','Elapsed [min]','CPU [min]','Mean cores','ηworker [%]'],rows,widths=[4.1,2.,2.,1.8,2.],size=13)
deck.text(s,.8,5.65,11.7,.45,'ηworker = CPU time / (workers × elapsed time). HPC: 40.7%; HTC3454: 38.3%. This measures CPU use per worker; apparent HPC scaling efficiency (1.16/3) is 38.6%.',12)
deck.text(s,.8,6.2,11.7,.45,'* HPC affinity probe lists 4 logical CPUs; physical-core allocation and original HPC hardware are unverified. Scaling ratios are not controlled speedups. Run duration: 209.7 s; HPC analysis: 17.8–20.6× longer.',12)
(D/'CPU_efficiencies.json').write_text(json.dumps(dict(definition='CPU time / (mode_workers * elapsed)',rows=eff,apparent_HPC_scaling_efficiency=rec['elapsed_ratio']/3),indent=2))
# Threaded profile outputs are inserted once all three runs have completed.
PRO=R/'analysis-work/Run2/diagnostics/worker_profile_20261115'
if not all((PRO/k/'instrumentation.json').exists() for k in ('profile_1workers','profile_3workers','timing_3workers')):raise RuntimeError('Waiting for complete worker profiles')
shutil.copytree(PRO,D/'worker_profile',dirs_exist_ok=True)
# Profile summary generated separately after validating the three runs.
summary=json.loads((PRO/'summary.json').read_text())
def page(title,subtitle):
 temp=sd.Deck();ss=temp.new(' ',subtitle,source='50 SPEC of run680; frozen benchmark sources; local VM, fixed guest-CPU affinity; main and worker cProfile + wall/thread-CPU timers.');ss['title']=title;h=next(x for x in ss['items'] if x['kind']=='text' and x['y']==.38);h['text']=title
 while len(sd.wrap(title,h['w']*.88,h['size']).splitlines())>1:h['size']-=1
 return ss
s=page('Code profile: the dominant path is outside the worker pool','Measured on 50 SPEC = 10.49 s acquired · main thread and all mode threads profiled')
table(s,['Measured scope','1 worker [s]','3 workers [s]','Interpretation'],summary['scope_rows'],y=1.85,widths=[4.2,2.1,2.1,3.5],size=12)
deck.text(s,.8,5.7,11.7,.85,summary['conclusion'],14);deck.slides[43]=s
s=page('Profiling: overhead, thread coverage and next changes','Timing scopes are cumulative and overlap; worker wall times cannot be added to main-thread wall time')
table(s,['Run','Pass1 [s]','Pass2 [s]','CPU / wall','ηworker'],summary['run_rows'],y=1.85,size=12)
deck.text(s,.8,4.75,11.7,1.6,summary['next_steps'],15);deck.slides.append(s)
for ss in deck.slides:
 ss['footer']=ss.get('footer','IQ NOISE STUDY').replace('v32','v33')
 for item in ss['items']:
  if item['kind']=='image':
   src=Path(item['path']);dst=A/src.name
   if src!=dst:shutil.copy2(src,dst)
   item['path']=str(dst)
sd.export(deck,OUT,'v33',datetime.now(ZoneInfo('Europe/Rome')).strftime('%-d %B %Y'))
(OUT/'README.md').write_text('# v33\n\nSlides22/23 restore full10us lag range while drawing fits only to5us. Slide8 includes explicit per-worker CPU efficiencies and apparent scaling efficiency. Slide44 replaced with new main+thread profiling and an appendix records overhead/control results. Full profiling evidence under data/worker_profile.\n')
