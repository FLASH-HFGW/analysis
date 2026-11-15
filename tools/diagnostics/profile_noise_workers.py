"""Profile frozen analyzer, including mode threads; count nested scopes separately."""
import os,sys,time,json,cProfile,pstats,threading,functools,hashlib,argparse,platform,importlib.util
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,required=True);ap.add_argument('--events',type=int,default=50);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--cprofile',action='store_true');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
b=Path('/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/noise_three_wn_benchmark_20261114T182101/sources');sys.path[:0]=[str(b),'/cvmfs/sft-flash.infn.it/package/midas/python']
allowed=sorted(os.sched_getaffinity(0));chosen=[];cores=set();socket=None
for cpu in allowed:
 root=Path(f'/sys/devices/system/cpu/cpu{cpu}/topology');pkg=int((root/'physical_package_id').read_text());core=int((root/'core_id').read_text())
 if socket is None:socket=pkg
 if (pkg,core) in cores:continue
 cores.add((pkg,core));chosen.append(cpu)
 if len(chosen)==3:break
assert len(chosen)==3
os.sched_setaffinity(0,chosen[:a.workers])
spec=importlib.util.spec_from_file_location('profiled_noise',b/'analyze_midas_iq_noise.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
import numpy,scipy,analyze_iq_filtered_bands as bands
lock=threading.Lock();stats={};profiles={};mainid=threading.get_ident()
def timed(fn,label,worker=False):
 @functools.wraps(fn)
 def run(*args,**kwargs):
  tid=threading.get_ident();prof=None
  if worker and tid!=mainid and a.cprofile:
   if tid not in profiles:profiles[tid]=cProfile.Profile()
   prof=profiles[tid];prof.enable()
  w=time.perf_counter();c=time.thread_time()
  try:return fn(*args,**kwargs)
  finally:
   elapsed=time.perf_counter()-w;cpu=time.thread_time()-c
   if prof:prof.disable()
   key=label+(':'+str(args[0]) if label=='process_second_mode' else '')
   with lock:
    row=stats.setdefault(key,dict(calls=0,wall_s=0.,thread_cpu_s=0.));row['calls']+=1;row['wall_s']+=elapsed;row['thread_cpu_s']+=cpu
    if label=='filtered_bands.serial' and row['calls']%10==0:print('Filtered events',row['calls'],'cumulative wall',round(row['wall_s'],2),flush=True)
 return run
mod.process_second_mode=timed(mod.process_second_mode,'process_second_mode',True)
mod.FilteredBandChecks.update=timed(mod.FilteredBandChecks.update,'filtered_bands.serial')
mod.analyze_mode=timed(mod.analyze_mode,'analyze_mode')
mod.RunStatistics.update=timed(mod.RunStatistics.update,'RunStatistics.update')
bands.BandFilter.process=timed(bands.BandFilter.process,'BandFilter.process')
bands.FilterWorkspace.oscillator=timed(bands.FilterWorkspace.oscillator,'oscillator')
bands.fft=timed(bands.fft,'band_fft');bands.ifft=timed(bands.ifft,'band_ifft')
sys.argv=[str(b/'analyze_midas_iq_noise.py'),'/home/mazzitel/flash-data/data/LNF/run00680.mid.gz','--out-dir',str(a.out),'--global-reference',str(b/'noise_reference.json'),'--iq-sign','-1','--mode-workers',str(a.workers),'--phase-lags','1','10','100','--h5-only','--filtered-bands','--product-version','v2','--calibration',str(b/'noise_calibration.json'),'--max-events',str(a.events)]
# The profiling run preserves the frozen benchmark ADC normalization; it is a timing diagnostic.
p=cProfile.Profile();start=time.perf_counter()
try:
 if a.cprofile:p.enable()
 mod.main()
finally:
 if a.cprofile:p.disable();p.dump_stats(str(a.out/'main.pstats'))
 for tid,prof in profiles.items():prof.dump_stats(str(a.out/f'worker_{tid}.pstats'))
 for path in a.out.glob('*.pstats'):
  with (path.with_suffix('.txt')).open('w') as f:pstats.Stats(str(path),stream=f).strip_dirs().sort_stats('cumtime').print_stats(35)
 env=dict(python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,host=platform.node(),affinity=sorted(os.sched_getaffinity(0)),selected_guest_core_CPUs=chosen,workers=a.workers,events=a.events,cprofile=a.cprofile,elapsed_s=time.perf_counter()-start,source=str(b),source_sha256={q.name:hashlib.sha256(q.read_bytes()).hexdigest() for q in b.glob('*.py')},cgroup={})
 for q in ('/sys/fs/cgroup/cpu.max','/sys/fs/cgroup/cpu.stat','/sys/fs/cgroup/cpu/cpu.cfs_quota_us','/sys/fs/cgroup/cpu/cpu.cfs_period_us'):
  if Path(q).exists():env['cgroup'][q]=Path(q).read_text()
 (a.out/'instrumentation.json').write_text(json.dumps(dict(environment=env,scopes=stats,caution='Nested cumulative scopes overlap. Worker wall sums overlap concurrently; thread_cpu_s is per-thread CPU. Fixed guest-CPU affinity on one VM; hypervisor physical mapping unknown; local software is not HPC production.'),indent=2))
 print('PROFILE COMPLETE',a.out,flush=True)
