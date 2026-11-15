"""Prepare three pinned single-core replicas of run 680, without submitting."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,shutil,hashlib
ROOT=Path('/home/mazzitel/HFGW')
OLD=ROOT/'analysis-runtime/autoreco/Run2/noise_fullrange_v2_20261109'
STAMP=datetime.now(ZoneInfo('Europe/Rome')).strftime('%Y%m%dT%H%M%S')
OUT=ROOT/f'analysis-runtime/autoreco/Run2/noise_three_wn_benchmark_{STAMP}'
OUT.mkdir();src=OUT/'sources';src.mkdir()
files=['analyze_midas_iq_noise.py','iq_noise_statistics.py','iq_noise_io.py','analyze_iq_filtered_bands.py','noise_reference.json','check_noise_environment.py','iq_noise_v2.py','noise_calibration.json']
for name in files:shutil.copy2(OLD/'sources'/name,src/name)
slots=json.loads(Path('/tmp/noise_benchmark_slots.json').read_text());selected=[]
for s in slots:
 if s.get('Cpus',0)>=1 and s.get('Memory',0)>=4096 and s.get('Disk',0)>=60*1024*1024 and s.get('State')=='Unclaimed' and s['Machine'] not in [v['Machine'] for v in selected]:selected.append(s)
 if len(selected)==3:break
assert len(selected)==3
probe='''import os,json,time,platform
from pathlib import Path
p=Path('results');p.mkdir(exist_ok=True)
d={'utc_epoch':time.time(),'hostname':platform.node(),'affinity':sorted(os.sched_getaffinity(0)),'pid':os.getpid()}
for name in ('/proc/self/cgroup','/proc/self/status','/sys/fs/cgroup/cpu.max','/sys/fs/cgroup/cpuset.cpus.effective','/proc/sys/kernel/random/boot_id','/sys/devices/virtual/dmi/id/product_uuid'):
 try:d[name]=Path(name).read_text()
 except OSError as e:d[name]=str(e)
for env in ('_CONDOR_MACHINE_AD','_CONDOR_JOB_AD'):
 path=os.environ.get(env)
 if path:
  try:
   allowed=('Machine','Name','Cpus','Memory','AssignedCpus','RequestCpus','SlotID','SlotTypeID','JobBatchName','ClusterId','ProcId')
   d[env]=[line for line in Path(path).read_text().splitlines() if line.partition('=')[0].strip() in allowed]
  except OSError as e:d[env]=str(e)
(p/'execution_environment.json').write_text(json.dumps(d,indent=2))
'''
(src/'record_execution_environment.py').write_text(probe)
files.append('record_execution_environment.py')
base=(OLD/'00693/script.sh').read_text()
base=base.replace('"$PYTHON" check_noise_environment.py','"$PYTHON" check_noise_environment.py\n"$PYTHON" record_execution_environment.py')
# Keep normal timing evidence in HDF5, plus shell timing of the whole command.
base=base.replace('"$PYTHON" -u analyze_midas_iq_noise.py','TIMEFORMAT=\'Analysis timing: real=%R user=%U sys=%S\'\ntime "$PYTHON" -u analyze_midas_iq_noise.py')
jobs=[]
for index,slot in enumerate(selected,1):
 job=OUT/f'wn{index}';job.mkdir();(job/'script.sh').write_text(base);(job/'script.sh').chmod(0o755)
 sub=(OLD/'00693/submit.sub').read_text().replace('arguments = 693','arguments = 680').replace('+NoisePilotRun = 693','+NoisePilotRun = 680').replace('noise_fullrange_v2_20261109',OUT.name)
 sub=sub.replace('transfer_input_files = '+','.join('../sources/'+name for name in files[:-1]),'transfer_input_files = '+','.join('../sources/'+name for name in files))
 sub=sub.replace('queue',f'requirements = (Machine == "{slot["Machine"]}")\nqueue')
 (job/'submit.sub').write_text(sub)
 jobs.append(dict(replica=index,machine=slot['Machine'],run=680,cpus=1,mode_workers=1,directory=str(job)))
manifest=dict(created_rome=datetime.now(ZoneInfo('Europe/Rome')).isoformat(),purpose='Three simultaneous full-run 680 v2 replicas on distinct advertised WN; 1 CPU and 1 mode worker each. Tests per-run time and aggregate throughput under empty queue, not internal 3-worker speedup.',jobs=jobs,source_sha256={name:hashlib.sha256((src/name).read_bytes()).hexdigest() for name in files},published_science=False,limitations='Advertised WN may share a physical host. Do not infer CPU independence from Machine alone. No automatic GPFS publication.')
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
(OUT/'pool_before.json').write_text(json.dumps(slots,indent=2))
shutil.copy2('/tmp/noise_benchmark_queue.json',OUT/'queue_before.json')
(OUT/'README.md').write_text('# Three-WN benchmark\n\nThree identical full-run 680 v2 replicas, pinned to distinct advertised WN, one CPU and one mode worker each. Source snapshot matches production. Results remain local to this diagnostic; no GPFS publication. Use condor_q for status; transferred results/ contain execution_environment.json and HDF5 timings.\n')
Path('/tmp/noise_three_wn_benchmark_path').write_text(str(OUT))
print(OUT)
print(json.dumps(jobs,indent=2))
