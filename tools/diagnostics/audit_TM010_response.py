"""Read-only audit of complex-tone image response and independent run680 windows."""
from pathlib import Path
import sys,json,time
import numpy as np
from scipy.optimize import nnls
sys.path.insert(0,'/cvmfs/sft-flash.infn.it/package/midas/python');import midas.file_reader
R=Path('/home/mazzitel/HFGW/analysis-work/Run2');RAW=Path('/home/mazzitel/flash-data/data/LNF');ARCH=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/fft_by_run');O=R/'diagnostics/TM010_response_audit_20261115';O.mkdir(parents=True,exist_ok=True)
c=json.load(open(R/'diagnostics/normalization_audit_20261114/calibration_reconstruction.json'));phys=json.load(open(R/'simulation/step6/metrics.json'))['mode_results'];names=['TM010','TM011','TM012'];fs=5e6;N=16383;freq=np.fft.fftshift(np.fft.fftfreq(N,1/fs));w=np.hanning(N);enbw=N*np.sum(w*w)/np.sum(w)**2;df=fs/N;curves={};observations=[];rawrows=[];odb={}
for mode in names:
 mi=names.index(mode);off=c['comparison'][mode]['rf_if_offset_hz'];out=[]
 for pt in c['curves'][mode]:
  run=pt['runs'][0];obs=next(v for v in c['sweep_observations'] if v['run']==run)
  with np.load(ARCH/f'run{run:05d}.npz') as a:s=a[f'fft_amp_mode{mi}_SPECs'].astype(float)
  idx=int(np.argmax(s));mirror=int(np.argmin(abs(freq+freq[idx])));base=float(np.median(s));main=float(np.sum(s[np.arange(idx-12,idx+13)%N]-base)/enbw);im=max(0,float(np.sum(s[np.arange(mirror-12,mirror+13)%N]-base)/enbw));vref=50e-3*10**(obs['generator_power_dbm']/10)
  row=dict(run=run,input_IF_hz=pt['rf_hz']-off,peak_IF_hz=float(freq[idx]),kz_main=float(np.sqrt(main/vref)),kz_image=float(np.sqrt(im/vref)),image_to_main_power=im/main,kz_pair=float(np.sqrt((main+im)/vref)));out.append(row);observations.append(dict(mode=mode,**row))
 curves[mode]=out
 # Raw direct sinusoid fit checks near the notch and at shoulders, independently of archived FFT.
 targets=(-1e6,-1.5e5,-5e4,5e4,1.5e5,1e6);selected={min(out,key=lambda v:abs(v['input_IF_hz']-t))['run'] for t in targets}
 for run in sorted(selected):
  ref=next(v for v in out if v['run']==run);fr=midas.file_reader.MidasFile(str(RAW/f'run{run:05d}.mid.gz'),use_numpy=True);bor=fr.get_bor_odb_dump().data;nb=bor['Equipment']['NetBox']['Settings'];lo=bor['Equipment']['LocalOscill']['Variables'];odb[str(run)]={'range_mV':nb['Channel_range_mV'],'sampling_MS':nb['Sampling_rate_MS'],'RS_hz':lo['freq RS'],'Teled1_hz':lo['freq Teled Ch1'],'Teled2_hz':lo['freq Teled Ch2'],'IQ_convention':'Raw I-jQ matches archived dominant-tone sign; verified directly','additional_ADC_response_settings':'No coupling/filter/impedance fields present in saved NetBox settings'}
  for ev in fr:
   if ev.header.is_midas_internal_event() or 'SPEC' not in ev.banks:continue
   frames=np.asarray(ev.banks['SPEC'].data,dtype=np.uint16).view(np.int16).reshape(-1,8);break
  scale=2*nb['Channel_range_mV'][2*mi]/1000/65535;ii=frames[:,2*mi].astype(float)*scale;qq=-frames[:,2*mi+1].astype(float)*scale;z=ii+1j*qq;n=len(z);win=np.hanning(n);F=np.fft.fft(z*win);f=np.fft.fftfreq(n,1/fs);mask=abs(f-ref['input_IF_hz'])<2000;inds=np.flatnonzero(mask);idx=inds[np.argmax(abs(F[inds]))];log=np.log(abs(F[np.arange(idx-1,idx+2)%n]));frac=.5*(log[0]-log[2])/(log[0]-2*log[1]+log[2]);tone=f[idx]+frac*fs/n;t=np.arange(n)/fs;phase=2*np.pi*tone*t;X=np.column_stack((np.cos(phase),np.sin(phase),np.ones(n)));coef=np.linalg.lstsq(X,np.column_stack((ii,qq)),rcond=None)[0];ai,bi=coef[:2,0];aq,bq=coef[:2,1];A=(ai+bq+1j*(aq-bi))/2;B=(ai-bq+1j*(aq+bi))/2;vref=50e-3*10**(-60/10);amp_i=np.hypot(ai,bi);amp_q=np.hypot(aq,bq);phase_error=(np.arctan2(-bq,aq)-np.arctan2(-bi,ai)+np.pi/2+np.pi)%(2*np.pi)-np.pi
  chunks=z.reshape(-1,16384)[:,:-1];chunks=chunks-chunks.mean(axis=1,keepdims=True);spec=np.fft.fftshift(np.mean(abs(np.fft.fft(chunks*w,axis=1)/w.sum())**2,axis=0));pk=int(np.argmax(spec));imidx=int(np.argmin(abs(freq+freq[pk])));bg=np.median(spec);pm=np.sum(spec[np.arange(pk-12,pk+13)%N]-bg)/enbw;pi=max(0,np.sum(spec[np.arange(imidx-12,imidx+13)%N]-bg)/enbw)
  row=dict(kz_raw_chunk_main=float(np.sqrt(pm/vref)),kz_raw_chunk_image=float(np.sqrt(pi/vref)),raw_chunk_to_archive_main_ratio=float(np.sqrt(pm/vref)/ref['kz_main']),raw_chunk_image_to_main_power=float(pi/pm),coherent_fit_note='Whole-SPEC coherent amplitude can lose power from tone phase noise; chunk-integrated power is the absolute-calibration cross-check',mode=mode,run=run,input_IF_hz=ref['input_IF_hz'],fitted_tone_IF_hz=float(tone),kz_raw_main=float(abs(A)/np.sqrt(vref)),kz_raw_image=float(abs(B)/np.sqrt(vref)),kz_raw_pair=float(np.sqrt(abs(A)**2+abs(B)**2)/np.sqrt(vref)),raw_image_to_main_power=float(abs(B/A)**2),tone_I_over_Q_amplitude=float(amp_i/amp_q),quadrature_phase_error_deg=float(np.degrees(phase_error)),raw_to_archived_main_ratio=float(abs(A)/np.sqrt(vref)/ref['kz_main']),max_ADC_count=int(np.max(abs(frames[:,:6].astype(np.int32)))),samples=n);rawrows.append(row);print('CAL RAW',mode,run,'image/main',row['raw_image_to_main_power'],'I/Q',row['tone_I_over_Q_amplitude'],flush=True)
# Full-run archived noise comparison: original archive read only; known ADC/ENBW corrections.
with np.load(ARCH/'run00680.npz') as arc:
 noise={m:arc[f'fft_amp_mode{i}_SPECs'].astype(float)*.16/(enbw*df) for i,m in enumerate(names)}
# Expected PSD variants: existing scalar response, image-inclusive response and shape-only floor sensitivity.
M=2**20;ff=np.fft.fftfreq(M,1/fs);results={};variant={}
for mode in names:
 rows=sorted(curves[mode],key=lambda v:v['input_IF_hz']);xx=np.array([v['input_IF_hz'] for v in rows]);aa=np.array([v['kz_main'] for v in rows]);bb=np.array([v['kz_image'] for v in rows]);p=phys[mode];preds=[]
 for include_image in (False,True):
  S=np.zeros(M)
  for alias in (-1,0,1):
   fff=ff+alias*fs;A=np.interp(fff,xx,aa,left=0,right=0);B=np.interp(-fff,xx,bb,left=0,right=0) if include_image else 0
   ki=2*np.pi*p['f0_hz']/p['q0'];kt=ki*(1+p['kappa1']+p['kappa2']);th=6.62607015e-34*p['f0_hz']/np.expm1(6.62607015e-34*p['f0_hz']/(1.380649e-23*p['temperature_k']));inputPSD=1.380649e-23*3.955+th*ki**2*p['kappa2']/((kt/2)**2+(2*np.pi*(fff-1e6))**2);mirrorPSD=1.380649e-23*3.955+th*ki**2*p['kappa2']/((kt/2)**2+(2*np.pi*(-fff-1e6))**2)
   S+=50*10**(67.4/10)*(A*A*inputPSD+B*B*mirrorPSD)
  preds.append(S)
 sel=(abs(freq)>5e3)&(abs(freq)<1.5e6);order=np.argsort(ff);base=np.interp(freq,ff[order],preds[0][order]);pair=np.interp(freq,ff[order],preds[1][order]);plateau=(abs(freq)>.5e6)&(abs(freq)<1.5e6);ratio=pair/np.median(pair[plateau]);data=noise[mode];norm=float(np.median(data[plateau]));X=np.column_stack((ratio[sel],np.ones(sel.sum())));co,_=nnls(X,data[sel]/norm);diag=norm*(co[0]*ratio+co[1]);frac=float(co[0]/co.sum())
 bands={}
 for center in (5e4,1.5e5,3.5e5,1e6):
  mask=abs(abs(freq)-center)<10000;bands[str(int(center))]=dict(data_relative_plateau=float(np.mean(data[mask])/np.mean(data[plateau])),scalar_relative_plateau=float(np.mean(base[mask])/np.mean(base[plateau])),image_relative_plateau=float(np.mean(pair[mask])/np.mean(pair[plateau])))
 stats=[]
 for S in preds:
  g=np.fft.ifft(S)[:51];g/=g[0];stats.append(dict(RMS_v=float(np.sqrt(np.mean(S)*fs)),Re_g1_0p2=float(g[1].real),Re_g1_0p4=float(g[2].real)));
 floor=co[1]*norm;scale=co[0]*norm/np.median(pair[plateau]);shapePSD=scale*preds[1]+floor;g=np.fft.ifft(shapePSD)[:51];g/=g[0]
 results[mode]=dict(band_ratios=bands,scalar=stats[0],image_inclusive=stats[1],shape_only_floor_fit=dict(template_fraction=frac,constant_fraction=1-frac,coefficient_template=float(co[0]),coefficient_constant=float(co[1]),RMSE_relative_plateau=float(np.sqrt(np.mean(((diag-data)[sel]/norm)**2))),template_condition_number=float(np.linalg.cond(X)),scope='Diagnostic shape fit only; constant component does not locate physical noise and coefficients are not measured gain/noise temperatures; no change to active toy'),noise_Re_g1_0p2_with_diagnostic_floor=float(g[1].real))
 np.savez_compressed(O/f'{mode}_response_audit.npz',frequency_hz=freq,noise_PSD=data,scalar_expected_PSD=base,image_expected_PSD=pair,shape_floor_diagnostic_PSD=diag,analog_IF_hz=xx,kz_main=aa,kz_image=bb,scalar_expected_g1=np.fft.ifft(preds[0])[:51]/np.mean(preds[0]),image_expected_g1=np.fft.ifft(preds[1])[:51]/np.mean(preds[1]))
# Save intermediate evidence before the long raw-file scan.
report=dict(status='calibration_complete',scope='Read-only TM010 model audit; original run680 analysis and active toy unchanged',calibration_curves=curves,raw_calibration_checks=rawrows,recorded_ODB=odb,results=results,limitations=['Calibration and science ADC ranges differ; LO frequencies also differ. ODB does not record coupling/analog filter settings.','Image-inclusive PSD requires proper independent equal-sideband input noise; no complex transfer phase inferred from archived power alone.','A fitted flat floor is only a diagnostic, not an established downstream-noise model.','Exact I/Q response requires complex/matrix calibration and confirmation of setup/reference plane.'],science_windows=[])
(O/'audit.json').write_text(json.dumps(report,indent=2));print('CALIBRATION AUDIT COMPLETE',flush=True)
# Five disjoint windows test stability only; do not replace the original v21 first-window analysis.
starts=(0,245,495,745,995);blocks=[];window_index=0;seen=0;reader=midas.file_reader.MidasFile(str(RAW/'run00680.mid.gz'),use_numpy=True)
for event in reader:
 if event.header.is_midas_internal_event() or 'SPEC' not in event.banks:continue
 if seen in range(starts[window_index],starts[window_index]+5):blocks.append(np.asarray(event.banks['SPEC'].data,dtype=np.uint16).view(np.int16).reshape(-1,8).copy())
 if seen==starts[window_index]+4:
  frames=np.concatenate(blocks);blocks=[];rows={};n=len(frames);win=np.hanning(n);f=np.fft.fftshift(np.fft.fftfreq(n,1/fs));group=256
  for mi,mode in enumerate(names):
   z=(frames[:,2*mi].astype(float)-1j*frames[:,2*mi+1].astype(float))*4/65535;z-=z.mean();S=np.fft.fftshift(abs(np.fft.fft(z*win))**2/(fs*np.sum(win*win)));g=np.fft.ifft(abs(np.fft.fft(z,2*n))**2)[:51]/(n-np.arange(51));g/=g[0].real;pl=(abs(f)>.5e6)&(abs(f)<1.5e6);central=abs(abs(f)-5e4)<10000;rows[mode]=dict(RMS_AC_v=float(np.sqrt(np.mean(abs(z)**2))),central_50k_over_plateau=float(np.mean(S[central])/np.mean(S[pl])),Re_g1_0p2=float(g[1].real),Re_g1_0p4=float(g[2].real));np.savez_compressed(O/f'window_{starts[window_index]:04d}_{mode}.npz',frequency_hz=f.reshape(-1,group).mean(axis=1),PSD=S.reshape(-1,group).mean(axis=1),g1=g)
  report['science_windows'].append(dict(first_SPEC=starts[window_index],duration_s=n/fs,modes=rows));(O/'audit.json').write_text(json.dumps(report,indent=2));print('SCIENCE WINDOW',starts[window_index],rows,flush=True);window_index+=1
  if window_index==len(starts):break
 seen+=1
report['status']='complete';(O/'audit.json').write_text(json.dumps(report,indent=2));print('COMPLETE',flush=True)
