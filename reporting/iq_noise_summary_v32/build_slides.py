"""Add verified HPC4407 measurements without rerunning scientific analyses."""
from pathlib import Path
import sys,json,shutil,hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np,h5py
sys.path.insert(0,'/tmp/v18-python-deps');import pptx
sys.path.insert(0,'/home/mazzitel/HFGW/analysis/reporting');import slide_deck as sd
R=Path('/home/mazzitel/HFGW');BASE=R/'analysis-work/Run2/reports/iq_noise_summary_v31';OUT=BASE.with_name('iq_noise_summary_v32');OUT.mkdir(exist_ok=True);D=OUT/'data';A=OUT/'assets';A.mkdir(exist_ok=True);shutil.copytree(BASE/'data',D,dirs_exist_ok=True)
P=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/noise_hpc_3workers/JOB_4407');old=R/'analysis-work/Run2/reports/noise_v2_development_20261109/run680_full_published/run00680_noise_v2.h5';E=D/'hpc_JOB_4407';E.mkdir(exist_ok=True)
for n in ('job_status.json','step_affinity.json','analysis.log','cpu_environment.txt'):shutil.copy2(P/n,E/n)
status=json.loads((P/'job_status.json').read_text());assert status['exit_code']==0
def timing(h):return {k:{v:float(h[f'summary/performance/timings/{k}/{v}'][()]) for v in ('wall_s','cpu_s')} for k in ('pass1','pass2','plots','total')}
with h5py.File(old) as x,h5py.File(P/'run00680_noise_v2.h5') as y:
 t1,t3=timing(x),timing(y);assert y['summary/performance/mode_workers'][()]==3
 assert x['summary/samples'][()]==y['summary/samples'][()]==1048576000
 assert x['summary/reached_eof'][()] and y['summary/reached_eof'][()]
 assert x['summary/performance/implementation'][()]==y['summary/performance/implementation'][()]
 checks={}
 for mode in ('TM010','TM011','TM012'):
  for name in ('noise_counts','phase_counts','samples_above_7sigma'):
   path=f'modes/{mode}/{name}';checks[path]=bool(np.array_equal(x[path][()],y[path][()]));assert checks[path]
rec=dict(job=4407,run=680,workers=3,status=status,affinity=json.loads((P/'step_affinity.json').read_text()),CPU_model='AMD EPYC 9654 96-Core Processor',timings_1worker=t1,timings_3workers=t3,elapsed_ratio=t1['total']['wall_s']/t3['total']['wall_s'],CPU_time_ratio=t3['total']['cpu_s']/t1['total']['cpu_s'],scientific_checks=checks,source=str(P),h5_sha256=hashlib.sha256((P/'run00680_noise_v2.h5').read_bytes()).hexdigest(),limitation='3 mode workers verified. Affinity probe lists4 logical CPU IDs; physical core mapping and Slurm allocation record unavailable. Original HPC hardware unknown, so elapsed ratio is not a controlled parallel speedup.')
(E/'benchmark_summary.json').write_text(json.dumps(rec,indent=2))
deck=sd.Deck();deck.slides=json.loads((BASE/'slide_model.json').read_text())
def page(title,sub,source,notes=''):
 d=sd.Deck();s=d.new(' ',sub,source,notes=notes);s['title']=title
 hdr=next(x for x in s['items'] if x['kind']=='text' and x['y']==.38);hdr['text']=title
 while len(sd.wrap(title,hdr['w']*.88,hdr['size']).splitlines())>1:hdr['size']-=1
 return s
def table(s,headers,rows,y=1.9,size=13,widths=None):
 widths=widths or [11.9/len(headers)]*len(headers);xx=.7
 for head,w in zip(headers,widths):deck.text(s,xx,y,w-.08,.65,head,size,True);xx+=w
 for i,row in enumerate(rows):
  xx=.7
  for val,w in zip(row,widths):deck.text(s,xx,y+.85+i*.45,w-.08,.43,str(val),size);xx+=w
s=page('HPC / HTC: elapsed time and measured CPU use','Run 680 · full analysis only · excludes transfers · three HPC mode workers now verified','HPC4407 HDF5 performance/log/status/affinity; original HPC v2 HDF5; HTC3451–3454 saved timing records.',notes=rec['limitation'])
rows=[]
for label,t in [('HPC · 1 worker',t1),('HPC 4407 · 3 workers*',t3)]:
 v=t['total'];rows.append([label,f"{v['wall_s']/60:.1f}",f"{v['cpu_s']/60:.1f}",f"{v['cpu_s']/v['wall_s']:.3f}"])
for job in json.loads((D/'four_job_timings.json').read_text()):
 v=job['timings']['total'];rows.append([f"HTC {job['job']} · {job['cpus']} CPU / {job['workers']} worker",f"{v['wall_s']/60:.1f}",f"{v['cpu_s']/60:.1f}",f"{v['cpu_s']/v['wall_s']:.3f}"])
table(s,['Configuration','Elapsed [min]','CPU [min]','Mean CPU cores'],rows,widths=[4.7,2.4,2.4,2.4])
deck.text(s,.8,5.65,11.7,.45,'HPC: 72.2 → 62.4 min (elapsed ratio 1.16×); mean CPU use only 1.22 cores with 3 workers. HTC 3-worker job averaged 1.15 cores. Extra workers provide limited parallel CPU use.',13)
deck.text(s,.8,6.2,11.7,.45,'* HPC affinity probe: 4 logical CPU IDs; physical-core allocation unverified. Original HPC hardware unknown. Hardware, affinity and contention differ: these ratios are not controlled parallel speedups.',12)
deck.slides[7]=s
s=page('HPC 4407: where the three-worker time is spent','Same run, implementation tag and sample count; checked amplitude/phase histograms and 7σ counts are identical','HPC1-worker and4407 HDF5 timings; recorded affinity host hpc-gpu057.lnf.infn.it; EPYC9654.',notes=rec['limitation'])
rows=[]
for k,label in [('pass1','Pass1'),('pass2','Pass2'),('plots','Plots'),('total','Total')]:
 a,b=t1[k],t3[k];rows.append([label,f"{a['wall_s']/60:.2f}",f"{b['wall_s']/60:.2f}",f"{b['cpu_s']/60:.2f}",f"{b['cpu_s']/b['wall_s']:.3f}"])
table(s,['Phase','1 worker wall [min]','3 workers wall [min]','3 workers CPU [min]','Mean cores'],rows,y=1.95,size=13)
deck.text(s,.8,5.15,11.7,.55,'Elapsed time decreases 13.6%, while process CPU time increases 6.5%. Pass2 averages 1.26 cores: the observed execution does not sustain three-core use.',15)
deck.text(s,.8,5.95,11.7,.7,'The local profile identifies filtered-band work outside the mode thread pool. Production per-thread profiling and exact core/SMT affinity are still needed to separate serial work, contention and scheduling effects.',15)
deck.slides.append(s)
for ss in deck.slides:
 ss['footer']=ss.get('footer','IQ NOISE STUDY').replace('v31','v32')
 for item in ss['items']:
  if item['kind']=='image':
   src=Path(item['path']);dst=A/src.name
   if src!=dst:shutil.copy2(src,dst)
   item['path']=str(dst)
(D/'cpu_comparison.md').write_text((D/'cpu_comparison.md').read_text()+'\n\nHPC4407 retrieved:3 workers, wall3742.973s, CPU4571.050s, mean1.221cores; AMD EPYC9654, recorded affinity[76,77,268,269]. Original HPC CPU model remains unknown. No controlled physical-core speedup claim. See hpc_JOB_4407/benchmark_summary.json.\n')
sd.export(deck,OUT,'v32',datetime.now(ZoneInfo('Europe/Rome')).strftime('%-d %B %Y'))
(OUT/'README.md').write_text('# v32\n\nPreserves v31 scientific slides, including full-run IQ tails and5us fits. Slide8 now includes verified HPC4407 timings. Appends detailed pass timings and limitations; records job evidence in data/hpc_JOB_4407.\n')
