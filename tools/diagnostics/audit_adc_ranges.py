"""Read ADC ranges from BOR for the campaign; do not change saved science."""
from pathlib import Path
import sys,json,csv,concurrent.futures
sys.path.insert(0,'/cvmfs/sft-flash.infn.it/package/midas/python')
import midas.file_reader
RAW=Path('/home/mazzitel/flash-data/data/LNF');OUT=Path('/home/mazzitel/HFGW/analysis-work/Run2/diagnostics/normalization_audit_20261114')
def read(run):
 try:
  f=midas.file_reader.MidasFile(str(RAW/f'run{run:05d}.mid.gz'),use_numpy=True);d=f.get_bor_odb_dump().data
  ranges=d['Equipment']['NetBox']['Settings']['Channel_range_mV']
  return dict(run=run,ranges_mV=ranges,iq_ranges_uniform=len(set(ranges[:6]))==1,iq_peak_range_v=ranges[0]/1000,legacy_amplitude_factor=ranges[0]/5000,legacy_power_factor=(ranges[0]/5000)**2)
 except Exception as e:return dict(run=run,error=str(e))
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:rows=list(ex.map(read,range(680,940)))
(OUT/'campaign_ADC_ranges.json').write_text(json.dumps(dict(frontend_applies_ODB='Confirmed by user',rows=rows),indent=2))
from collections import Counter
print('Errors',[r for r in rows if 'error' in r]);print('IQ ranges mV:',Counter(tuple(r['ranges_mV'][:6]) for r in rows if 'ranges_mV' in r))
