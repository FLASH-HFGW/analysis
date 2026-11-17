"""Inventory existing primary v2 HDF5 without raw reconstruction or mutations."""
from pathlib import Path
import json,csv,hashlib
import h5py,numpy as np
ROOT=Path('/home/mazzitel/HFGW');BASE=ROOT/'analysis-work/Run2/reports/noise_fullrange_v2_20261109';OUT=ROOT/'analysis-work/Run2/diagnostics/v47_primary_audit_20261117';OUT.mkdir(exist_ok=True)
rows=[];inventory=[]
for run in range(680,940):
 p=BASE/f'run{run:05d}_noise_v2.h5'
 if not p.exists():raise FileNotFoundError(p)
 with h5py.File(p) as h:
  def val(name):
   x=h[name][()];return x.decode() if isinstance(x,bytes) else x.item() if isinstance(x,np.generic) else str(x)
  meta={k:val('summary/'+k) for k in ('input_range_v','iq_sign','samples','reached_eof','product_version')}
  meta['events']=len(json.loads(val('summary/events')))
  for mode in ('TM010','TM011','TM012'):
   g=h['dc_removed/modes/'+mode];dc=float(g['dc_squared_v2'][()]);ac=float(g['ac_squared_v2'][()]);total=float(g['total_squared_v2'][()]);err=abs(total-dc-ac)/max(total,1e-300)
   assert err<1e-10,(run,mode,err)
   factor=2/float(meta['input_range_v']);rows.append(dict(run=run,mode=mode,source=str(p),**meta,voltage_factor_to_actual_2V=factor,total_RMS_ADC_V=np.sqrt(total)*factor,AC_RMS_ADC_V=np.sqrt(ac)*factor,DC_squared_ADC_V2=dc*factor**2,identity_relative_error=err))
  if run==680:
   def visit(name,o):
    if isinstance(o,h5py.Dataset):inventory.append(dict(path=name,shape=list(o.shape),dtype=str(o.dtype)))
   h.visititems(visit)
with (OUT/'primary_v2_moments.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(OUT/'schema_run680.json').write_text(json.dumps(inventory,indent=2))
(OUT/'inventory_status.json').write_text(json.dumps(dict(runs=260,mode_rows=len(rows),range=[680,939],source=str(BASE),scope='Initial inventory and DC+AC identity check only. Does not certify per-slide provenance, v1 equivalence, frequency/band closure or presentation readiness.',normalization='Scale saved voltage by2/input_range_v exactly once; inspect derived product metadata before applying elsewhere.',max_identity_error=max(r['identity_relative_error'] for r in rows)),indent=2))
print(OUT)
