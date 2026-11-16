"""Fresh full-run ADC-quantized toy: calibration±5V/science±2V and LF60→20dB."""
from pathlib import Path
import json,time,hashlib
import numpy as np,h5py
from scipy.fft import fft,ifft,next_fast_len
from scipy.optimize import minimize_scalar
R=Path('/home/mazzitel/HFGW');ROOT=R/'analysis-work/Run2';OUT=ROOT/'simulation/toy_ODB_cal5_data2_LF_20261116';OUT.mkdir(parents=True,exist_ok=True)
CAL=ROOT/'diagnostics/normalization_audit_20261114/calibration_reconstruction.json';PHY=ROOT/'simulation/step6/metrics.json';c=json.load(open(CAL));p=json.load(open(PHY))['mode_results'];fs=5e6;target=1048576000;B=2**20;L=65537;M=next_fast_len(B+L-1);design=2**20;f=np.fft.fftfreq(design,1/fs);muq=np.sqrt(np.pi/2);sdq=np.sqrt((4-np.pi)/2);radii=muq+np.array([3,5,7])*sdq
report=dict(status='running',samples_per_mode=target,duration_s=target/fs,RF_gain_db=103.4,second_FET_in_calibration=False,LF_calibration_gain_db=60,LF_science_gain_db=20,LF_kz_amplitude_factor=.01,calibration_ADC_peak_V_adopted=5,calibration_ADC_peak_V_in_ODB=5,calibration_range_source='User chooses recorded ODB ranges2026-11-16: calibration±5V, science±2V; frontend applies ODB',archived_kz_amplitude_correction=1.,kz_science_over_archived_kz=.01,ADC_peak_V=2,ADC_lsb_V=4/65535,receiver_Tn_K=3.955,method='Continuous overlap-save FIR with random prehistory, fresh ADC quantization, exact full-run moments/histograms/IQ/tail samples; original5SPEC spectral/covariance estimator saved separately',assumptions=['LF gain change modeled as amplitude factor only; frequency-response shape may depend on gain setting.','Scalar main-tone response retained as baseline; known TM010 image/imbalance limitations not concealed.','No noise-temperature, per-mode gain or added-noise fit to data.'],results={})
start=time.perf_counter();reference=ROOT/'reports/iq_noise_summary_v37/data'
with h5py.File(OUT/'toy_full_run680.h5','w') as h:
 for index,(mode,phys) in enumerate(p.items()):
  pts=c['curves'][mode];offset=c['comparison'][mode]['rf_if_offset_hz'];xx=np.array([r['rf_hz']-offset for r in pts]);kk=np.array([r['kz_integrated'] for r in pts])*.01;order=np.argsort(xx);xx=xx[order];kk=kk[order];S=np.zeros(design)
  for alias in (-1,0,1):
   af=f+alias*fs;resp=np.interp(af,xx,kk,left=0,right=0);ki=2*np.pi*phys['f0_hz']/phys['q0'];kt=ki*(1+phys['kappa1']+phys['kappa2']);th=6.62607015e-34*phys['f0_hz']/np.expm1(6.62607015e-34*phys['f0_hz']/(1.380649e-23*phys['temperature_k']))
   S+=50*10**(103.4/10)*(1.380649e-23*3.955+th*ki**2*phys['kappa2']/((kt/2)**2+(2*np.pi*(af-1e6))**2))*resp**2
  imp=np.fft.fftshift(ifft(np.sqrt(fs*S)));fir=imp[design//2-L//2:design//2+L//2+1];H=fft(fir,M);P=float(np.mean(S)*fs);Pf=float(np.sum(abs(fir)**2));assert abs(Pf/P-1)<.001;theory=ifft(S)[:201];theory/=theory[0];sig=np.sqrt(P/2);rng=np.random.default_rng(20261115+100*index)
  def white(n):return (rng.standard_normal(n)+1j*rng.standard_normal(n))/np.sqrt(2)
  history=white(L-1);ae=np.linspace(0,max(.05,12*sig),4097);pe=np.linspace(-np.pi,np.pi,1025);ac=np.zeros(4096,np.int64);pc=np.zeros(1024,np.int64);edges=np.load(reference/f'full_iq_data_{mode}.npz')['edges'];N=len(edges)-1;iqc=np.zeros((N,N),np.int64);sumz=0j;suma=sumabs2=sumI2=sumQ2=sumIQ=0.;clipped=zeros=outside=0;candidates=[];tail=[];prefix=[];t0=time.perf_counter();cpu=time.process_time()
  for block in range(1000):
   inp=np.r_[history,white(B)];z=ifft(fft(inp,M)*H)[L-1:L-1+B];history=inp[-(L-1):].copy();step=4/65535;ci=np.round(z.real/step);cq=np.round(z.imag/step);clipped+=int(np.count_nonzero((ci<-32768)|(ci>32767)|(cq<-32768)|(cq>32767)));z=(np.clip(ci,-32768,32767)+1j*np.clip(cq,-32768,32767))*step
   if block<5:prefix.append(np.column_stack((ci,cq)).astype(np.int16))
   amp=abs(z);ac+=np.histogram(amp,ae)[0];pc+=np.histogram(np.angle(z[amp>0]),pe)[0];zeros+=int(np.count_nonzero(amp==0));sumz+=z.sum();suma+=float(amp.sum());sumabs2+=float(np.sum(amp**2));sumI2+=float(np.sum(z.real**2));sumQ2+=float(np.sum(z.imag**2));sumIQ+=float(np.sum(z.real*z.imag));candidates.append(amp[amp>radii[0]*sig*.98]);tail.append(z[amp>radii[1]*sig*.98]);ix=np.floor((z.real-edges[0])/(edges[-1]-edges[0])*N).astype(np.int64);iy=np.floor((z.imag-edges[0])/(edges[-1]-edges[0])*N).astype(np.int64);ok=(ix>=0)&(ix<N)&(iy>=0)&(iy<N);outside+=int((~ok).sum());iqc+=np.bincount(ix[ok]*N+iy[ok],minlength=N*N).reshape(N,N)
   if block%50==0 or block==999:
    pr=dict(mode=mode,samples=(block+1)*B,target=target,mode_wall_s=time.perf_counter()-t0,total_wall_s=time.perf_counter()-start);(OUT/'progress.json').write_text(json.dumps(pr));print(json.dumps(pr),flush=True)
  assert ac.sum()==target and pc.sum()+zeros==target and clipped==0 and iqc.sum()+outside==target
  lo=ae[:-1];hi=ae[1:]
  def objective(logsig):
   ss=np.exp(logsig);a=lo**2/(2*ss**2);dd=(hi**2-lo**2)/(2*ss**2);return float(-np.sum(ac*(-a+np.log(-np.expm1(-dd)))))
  opt=minimize_scalar(objective,bounds=(np.log(sig/2),np.log(sig*2)),method='bounded');assert opt.success;sf=float(np.exp(opt.x));assert abs(sf/sig-1)<.01;cand=np.concatenate(candidates);tails=np.concatenate(tail);assert radii[0]*sf>radii[0]*sig*.98 and radii[1]*sf>radii[1]*sig*.98;exceed=np.count_nonzero(cand[:,None]>radii*sf,axis=0);tails=tails[abs(tails)>radii[1]*sf];mu=sumz/target;power=sumabs2/target;assert abs(power/P-1)<.003;vi=sumI2/target-mu.real**2;vq=sumQ2/target-mu.imag**2;cov=sumIQ/target-mu.real*mu.imag
  counts5=np.concatenate(prefix);z5=(counts5[:,0].astype(float)+1j*counts5[:,1].astype(float))*step;centered=z5-z5.mean();n=len(z5);co=ifft(abs(fft(centered,2*n))**2)[:201]/(n-np.arange(201));g=co/co[0].real;assert np.max(abs(g[:11]-theory[:11]))<.003
  row=dict(samples=target,sigma_fit_v=sf,sigma_expected_v=float(sig),mean_amplitude_v=suma/target,std_amplitude_v=float(np.sqrt(power-(suma/target)**2)),rms_v=float(np.sqrt(power)),mean_i_v=float(mu.real),mean_q_v=float(mu.imag),ac_rms_v=float(np.sqrt(power-abs(mu)**2)),var_i_v2=float(vi),var_q_v2=float(vq),cov_iq_v2=float(cov),pseudo_covariance_ratio=float(abs(complex(vi-vq,2*cov))/(vi+vq)),phase_valid_samples=int(pc.sum()),zero_amplitude_samples=zeros,thresholds_3_5_7_v=(radii*sf).tolist(),samples_above_3_5_7=exceed.tolist(),expected_power_v2=P,FIR_power_relative_error=Pf/P-1,clipped_samples=clipped,IQ_outside=outside,wall_s=time.perf_counter()-t0,cpu_s=time.process_time()-cpu,checks_passed=True)
  grp=h.create_group(mode)
  values=dict(amplitude_edges_v=ae,amplitude_counts=ac,phase_edges_rad=pe,phase_counts=pc,IQ_edges_v=edges,IQ_counts=iqc,tail_above_5sigma_v=tails,first_5SPEC_ADC_counts=counts5,g1_5SPEC=g,g1_expected=theory,lag_s=np.arange(201)/fs,first_100000_adc_v=z5[:100000])
  for key,v in values.items():grp.create_dataset(key,data=v,compression='gzip')
  grp.attrs['metrics_json']=json.dumps(row);h.flush();report['results'][mode]=row;(OUT/'metrics.json').write_text(json.dumps(report,indent=2));print(mode,json.dumps(row),flush=True)
  del prefix,counts5,z5,centered,co,candidates,cand,tail,tails,values
 report['status']='complete';report['wall_s']=time.perf_counter()-start;report['input_sha256']={str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in (CAL,PHY,Path(__file__))};h.attrs['metadata_json']=json.dumps(report)
(OUT/'metrics.json').write_text(json.dumps(report,indent=2));print('COMPLETE',flush=True)
