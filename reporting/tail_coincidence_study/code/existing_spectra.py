"""Selected five-run PSD summaries; no raw data and no new RF fits."""
from pathlib import Path
import sys,json,csv,time
import numpy as np
from scipy.ndimage import median_filter
R=Path(__file__).resolve().parents[3];O=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'examples'));from iq_products import open_product
inv=json.load(open(O/'data/inventory.json'));rows=[];curves=[];series=[];requested=0;start=time.perf_counter()
for item in inv['runs']:
 if item['status']!='metadata_valid':continue
 run=item['run']
 with open_product(item['ROOT_path']) as p:
  f=p.file;freq=p.edges[:-1]+p.widths/2;source=f.file.file.source if hasattr(f,'file') else None
  for mode in ['TM010','TM011','TM012']:
   wp=f[f'spectra/{mode}/window_psd'][:].astype(float);assert wp.shape==(209,50000);background=np.maximum(median_filter(wp.mean(0),size=201,mode='nearest'),1e-30);bb=np.median(wp[:,abs(freq)>=100000]/background[abs(freq)>=100000],axis=1);focus={'TM010':-28000,'TM011':1250000,'TM012':-492750}[mode];mask=abs(freq-focus)<20000;mean=wp.mean(0);ratio=mean/background;local=wp[:,mask]/(bb[:,None]*background[mask]);center=np.argmin(abs(freq-focus));occup=float(np.mean(wp[:,center]/(bb*background[center])>3));near=np.flatnonzero(abs(freq-focus)<=1000);best=near[np.argmax(ratio[near])];occ_best=float(np.mean(wp[:,best]/(bb*background[best])>3));rows.append(dict(run=run,mode=mode,region_center_hz=focus,best_100Hz_bin_hz=float(freq[best]),mean_local_ratio=float(ratio[best]),occupancy_ratio_gt3=occ_best,reference_bin_occupancy=occup,scope='descriptive100Hz bin screen,209 complete seconds; no coherence or significance claim'))
   for k in np.flatnonzero(mask):curves.append(dict(run=run,mode=mode,frequency_hz=float(freq[k]),mean_PSD_V2_Hz=float(mean[k]),mean_local_ratio=float(ratio[k])))
   for i in range(len(wp)):series.append(dict(run=run,mode=mode,window=i,received_s=float(p.windows['received_index'][i]/p.fs),broadband_relative_scale=float(bb[i]),focus_bin_ratio=float(wp[i,best]/(bb[i]*background[best])),window_mean_power_V2=float(wp[i]@p.widths)))
  # Reader requested bytes are available through RootNode.file (uproot ReadOnlyDirectory).
  try:requested+=f.file.file.source.num_requested_bytes
  except Exception:pass
 print('ARCHIVED_SPECTRA',run,flush=True)
for name,a in [('spectral_persistence.csv',rows),('spectral_focus_curves.csv',curves),('spectral_window_series.csv',series)]:
 with (O/'tables'/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(a[0]),lineterminator='\n');w.writeheader();w.writerows(a)
(O/'validation/spectral_reads.json').write_text(json.dumps({'wall_s':time.perf_counter()-start,'requested_bytes_if_available':requested,'raw_reads':False,'runs':[r['run'] for r in inv['runs']],'estimated_new_remote_compressed_PSD_bytes':316336698,'full_ROOT_copies':False},indent=2))
