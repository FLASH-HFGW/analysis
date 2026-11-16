"""Matched run620/run680 exploratory pipeline, explicitly limited to20 SPEC events."""
from pathlib import Path
import os,sys,runpy,json
ROOT=Path('/home/mazzitel/HFGW');OUT=ROOT/'analysis-work/Run2/simulation/run620_comparison';OUT.mkdir(parents=True,exist_ok=True)
S=ROOT/'analysis-runtime/autoreco/Run2/noise_three_wn_benchmark_20261114T182101/sources'
sys.path[:0]=[str(S),'/cvmfs/sft-flash.infn.it/package/midas/python']
import midas.file_reader
for run in (620,680):
 raw=Path('/home/mazzitel/flash-data/data/LNF')/f'run{run:05d}.mid.gz';d=OUT/f'run{run:05d}';d.mkdir(exist_ok=True)
 reader=midas.file_reader.MidasFile(str(raw),use_numpy=True);odb=reader.get_bor_odb_dump().data
 settings=odb['Equipment']['NetBox']['Settings'];(d/'ADC_settings.json').write_text(json.dumps(settings,indent=2))
 assert settings['Channel_range_mV'][:6]==[2000]*6
 sys.argv=[str(S/'analyze_midas_iq_noise.py'),str(raw),'--out-dir',str(d),'--global-reference',str(S/'noise_reference.json'),'--iq-sign','-1','--mode-workers','1','--phase-lags','1','10','100','--h5-only','--filtered-bands','--product-version','v2','--calibration',str(S/'noise_calibration.json'),'--max-events','20']
 runpy.run_path(sys.argv[0],run_name='__main__')
