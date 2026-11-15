"""v20: replace the execution slide with a scoped CPU-time diagnosis."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import sys,json,shutil,hashlib
import numpy as np
sys.path.insert(0,'/tmp/v18-python-deps')
import pptx
sys.path.insert(0,'/home/mazzitel/HFGW/analysis/reporting')
import slide_deck as sd
base=Path('/home/mazzitel/HFGW/analysis-work/Run2/reports/iq_noise_summary_v19')
out=base.with_name('iq_noise_summary_v20');out.mkdir(exist_ok=True)
for name in ('assets','data'):shutil.copytree(base/name,out/name,dirs_exist_ok=True)
deck=sd.Deck();deck.slides=json.loads((base/'slide_model.json').read_text())
assert len(deck.slides)==36
r=json.loads((out/'data/baseline_v17/execution_timings.json').read_text())['htc_runs']
med=lambda k:float(np.median([x[k] for x in r]))
cpu=float(np.median([x['analysis_min']*x['cpu_wall_pct']/100 for x in r]))
temp=sd.Deck();s=temp.new('HTC slowdown: one requested core, partial CPU use',
 'Measured production snapshot · analysis time only · download, queue and publication excluded',
 'Sources: 248 HTC v2 HDF5/log records; HPC run 680 timers; submitted job settings; affinity probes on two hosts.',
 'All compared jobs use one requested CPU and mode_workers=1. Each table column reports a separate median for HTC; the ratio of medians need not equal the median CPU/wall. HPC and HTC differ in hardware and run populations. CPU/wall measures process CPU accumulation, not its cause. Affinity probes establish CPU-0 contention on two sampled hosts, not a complete mapping of the pool. No controlled 1-versus-3-core speedup or causal attribution of all lost wall time has been measured.')
s['footer']='EXECUTION | MEASURED DIAGNOSIS | DECK v20'
deck.text(s,.75,1.85,11.8,.5,'The completed campaign used 1 CPU and 1 mode worker per job.',21,True,sd.COLORS[0])
xs=[.8,5.8,8.2,10.6];ws=[4.8,2.2,2.2,2.1]
for x,w,label in zip(xs,ws,['Evidence','Elapsed [min]','CPU [min]','CPU / elapsed']):deck.text(s,x,2.65,w,.4,label,15,True)
vals=[['HTC v2 · median of 248 runs',f'{med("analysis_min"):.1f}',f'{cpu:.1f}',f'{med("cpu_wall_pct"):.1f}%'],['HPC v2 · run 680','72.2','71.5','99.1%']]
for j,row in enumerate(vals):
 for x,w,val in zip(xs,ws,row):deck.text(s,x,3.25+j*.6,w,.45,val,19)
deck.text(s,.8,4.7,11.7,.85,'Observed: HTC accumulated about 71 CPU-minutes over 215 elapsed minutes.\nCPU-0 contention was measured on two sampled hosts; this is not a three-core scaling test.',19)
deck.rect(s,.7,5.9,11.9,.75,'#FFFFFF')
deck.text(s,.9,6.02,11.5,.5,'Next: verify assigned cores; benchmark the same run with 1 versus 3 mode workers.',18,True,sd.COLORS[0])
deck.slides[7]=s
for slide in deck.slides:
 slide['footer']=slide.get('footer','IQ NOISE STUDY').replace('v19','v20')
 for item in slide['items']:
  if item['kind']=='image':
   item['path']=str(out/'assets'/Path(item['path']).name);assert Path(item['path']).is_file()
  if item['kind']=='text' and item['y']==.38:
   while len(sd.wrap(item['text'],item['w'],item['size']).splitlines())>1:item['size']-=1
sd.export(deck,out,'v20',datetime.now(ZoneInfo('Europe/Rome')).strftime('%-d %B %Y'))
(out/'data/v20_execution_revision.json').write_text(json.dumps(dict(source=str(base),source_model_sha256=hashlib.sha256((base/'slide_model.json').read_bytes()).hexdigest(),htc_runs=len(r),htc_median_elapsed_min=med('analysis_min'),htc_median_cpu_min=cpu,htc_median_cpu_wall_pct=med('cpu_wall_pct'),requested_cpus=1,mode_workers=1,scope='Presentation revision only; no jobs submitted. A matched 1/3-core benchmark remains to be performed.'),indent=2))
(out/'README.md').write_text('# IQ noise summary v20\n\n36 slides. Slide 8 now separates elapsed and CPU time, explicitly states the single-core production configuration, and proposes a controlled 1/3-worker test. Scientific simulation, fits and comparisons unchanged from v19.\n')
