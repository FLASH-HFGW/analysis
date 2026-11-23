"""Validate compact streaming outputs without reading MIDAS or ROOT."""
from pathlib import Path
import csv,json,math,hashlib,unittest,sys
import numpy as np
O=Path(__file__).resolve().parents[1];read=lambda n:list(csv.DictReader(open(O/'tables'/n)))
inv=json.load(open(O/'data/inventory.json'));f=json.load(open(O/'data/frozen_thresholds.json'));checks={}
b=read('pilot1429_binned_statistics.csv');hits=read('pilot1429_T7_samples.csv');ctx=read('pilot1429_cross_mode_context.csv');N=1048576000
checks['context_is_exact_hit_union']=set(int(r['index']) for r in ctx)==set(int(r['index']) for r in hits)
rows=[]
for m in ['TM010','TM011','TM012']:
 count=f['1429'][m]['T7_exact_count'];checks[m+'_hit_total']=sum(r['mode']==m for r in hits)==count
 for ms in [10,100,1000]:
  a=[r for r in b if r['mode']==m and int(r['nominal_bin_ms'])==ms];exp=sum(float(r['exposure_s']) for r in a);tot=sum(int(r['T7_count']) for r in a);rms=math.sqrt(sum(float(r['exposure_s'])*float(r['RMS_V'])**2 for r in a)/exp);root=next(r for r in inv['runs'] if r['run']==1429)['fullrun_attributes'][m]['rms_V'];checks[m+f'_{ms}ms_exposure_counts_RMS']=abs(exp-N/5e6)<1e-8 and tot==count and abs(rms/root-1)<1e-6
 for run in ['680','1429']:
  for n in [3,5,7]:
   k=math.sqrt(math.pi/2)+n*math.sqrt((4-math.pi)/2);rows.append(dict(run=run,mode=m,threshold='T'+str(n),threshold_V=f[run][m]['sigma_Rayleigh_V']*k,proper_zero_mean_expected_count=N*math.exp(-k*k/2),observed_exact_T7=f[run][m]['T7_exact_count'] if n==7 else '',qualification='marginal proper zero-mean Gaussian reference; no independent-sample significance'))
with (O/'tables/theoretical_thresholds.csv').open('w') as out:w=csv.DictWriter(out,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
suite=unittest.defaultTestLoader.discover(str(O/'code'),pattern='test_algorithms.py');result=unittest.TextTestRunner().run(suite);checks['algorithm_unit_tests']=result.wasSuccessful()
assert all(checks.values()),checks
out={'checks':checks,'all_passed':True,'raw_reads_in_validation':0,'qualification':'Existing 680 totals reused, not newly reconstructed. Raw CRC verified only for1429. No physical/UTC coincidence claim.'}
(O/'validation/checks.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
