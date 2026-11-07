import json,numpy as np,midas.file_reader
from pathlib import Path
root=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/noise_continuous');p=root/'by_run/00680/run00680_noise.npz'
out=Path('/home/mazzitel/HFGW/analysis-work/Run2/analysis/noise_continuous');out.mkdir(parents=True,exist_ok=True)
z=np.load(p);blocks=[]
reader=midas.file_reader.MidasFile('/home/mazzitel/flash-data/data/LNF/run00680.mid.gz',use_numpy=True)
for event in reader:
 if event.header.is_midas_internal_event() or 'SPEC' not in event.banks:continue
 blocks.append(np.asarray(event.banks['SPEC'].data,dtype=np.uint16).view(np.int16).reshape(-1,8).copy())
 if len(blocks)==3:break
f=np.concatenate(blocks);report={}
for mode,(ci,cq) in zip(('TM010','TM011','TM012'),((0,1),(2,3),(4,5))):
 i=f[:,ci].astype(float)*(10/65535);q=f[:,cq].astype(float)*(10/65535)
 value=i+1j*-1*q;valid=np.hypot(i,q)>0
 phase=np.full(len(f),np.nan);phase[valid]=np.unwrap(np.angle(value[valid]));ref=phase[np.flatnonzero(valid)[0]];phase-=ref
 sel=z['sample_indices']<len(f);actual=z[mode+'_delta_phase_rad'][sel];expected=phase[z['sample_indices'][sel]]
 print(mode,'error',np.nanmax(abs(actual-expected)))
 np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-7,equal_nan=True)
 peak=z[mode+'_peak_delta_phase_rad']+ref
 angle=np.arctan2(z[mode+'_peak_q_signed_v'],z[mode+'_peak_i_v'])
 error=np.abs((peak-angle+np.pi)%(2*np.pi)-np.pi)
 report[mode]={'first_three_SPEC_concatenation_max_error_rad':float(np.nanmax(abs(actual-expected))), 'all_peak_phase_modulo_max_error_rad':float(np.nanmax(error))}
(out/'run680_phase_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
