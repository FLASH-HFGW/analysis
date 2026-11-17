"""Compare only missing local v1 runs against published originals; never duplicate earlier comparisons."""
from pathlib import Path
import json,h5py,numpy as np
R=Path('/home/mazzitel/HFGW');W=R/'analysis-work/Run2';O=W/'diagnostics/v47_primary_audit_20261117';p=O/'v1_v2_dataset_comparison.json';d=json.loads(p.read_text());remaining=[];sources={}
for run in d['missing_v1_runs']:
 roots=[Path('/home/mazzitel/flash-data/analysis/autoreco/Run2')/v for v in ['noise_fullrange_v1_20261109','noise_temperature_pilot_minus1_20261108','noise_temperature_pilot_v2_20261109']][:2]
 candidates=[root/f'run{run:05d}_noise_v1.h5' for root in roots];v1=next((x for x in candidates if x.exists()),None)
 if v1 is None:remaining.append(run);continue
 with h5py.File(v1) as a,h5py.File(W/f'reports/noise_fullrange_v2_20261109/run{run:05d}_noise_v2.h5') as b:
  for name,v in d['datasets'].items():
   if name not in a or name not in b:continue
   x=b[name][()];y=a[name][()];v['compared']+=1
   if np.shape(x)!=np.shape(y):ok=False;err=None
   elif np.asarray(x).dtype.kind in 'biufc' and np.asarray(y).dtype.kind in 'biufc':
    ok=np.array_equal(x,y,equal_nan=True);err=float(np.nanmax(abs(np.asarray(x,dtype=complex)-np.asarray(y,dtype=complex)))) if np.size(x) else 0.
   else:ok=np.array_equal(x,y);err=None
   if not ok:v['different']+=1;v['different_runs'].append(run)
   if err is not None:v['max_abs_error']=max(v['max_abs_error'],err)
 d['compared_runs']+=1;sources[str(run)]=str(v1)
 if run%40==0:print(run,flush=True)
d['missing_v1_runs']=remaining;d['additional_published_v1_sources']=sources;p.write_text(json.dumps(d,indent=2));print('Compared',d['compared_runs'],'missing',remaining,flush=True)
