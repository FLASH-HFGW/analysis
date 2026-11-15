"""Continuous overlap-save Gaussian simulation; streaming full-run summaries."""
from pathlib import Path
import time,json,hashlib
import numpy as np,h5py
from scipy.fft import fft,ifft,next_fast_len
from scipy.optimize import minimize_scalar
ROOT=Path('/home/mazzitel/HFGW/analysis-work/Run2');OUT=ROOT/'simulation/toy_full_run680';OUT.mkdir(exist_ok=True,parents=True)
CAL=ROOT/'diagnostics/normalization_audit_20261114/calibration_reconstruction.json';PHY=ROOT/'simulation/step6/metrics.json'
c=json.loads(CAL.read_text());p=json.loads(PHY.read_text())['mode_results'];fs=5e6;target=1048576000;B=2**20;L=65537;M=next_fast_len(B+L-1);design=2**20;f=np.fft.fftfreq(design,1/fs)
report=dict(status='running',samples_per_mode=target,duration_s=target/fs,method='Continuous overlap-save FIR; folded analog PSD; random prehistory; streaming histograms, moments and boundary-inclusive covariance.',RF_gain_db=67.4,ADC_peak_V=2,assumption='Extra36dB FET already included in kz; conditional reference plane, not independently calibrated.',results={})
startall=time.perf_counter()
with h5py.File(OUT/'toy_full_run680.h5','w') as h5:
 for index,(mode,phys) in enumerate(p.items()):
  pts=c['curves'][mode];offset=c['comparison'][mode]['rf_if_offset_hz'];xx=np.array([r['rf_hz']-offset for r in pts]);kk=np.array([r['kz_integrated'] for r in pts]);order=np.argsort(xx);xx=xx[order];kk=kk[order];S=np.zeros(design)
  for alias in (-1,0,1):
   ff=f+alias*fs;resp=np.interp(ff,xx,kk,left=0,right=0);ki=2*np.pi*phys['f0_hz']/phys['q0'];kt=ki*(1+phys['kappa1']+phys['kappa2']);th=6.62607015e-34*phys['f0_hz']/np.expm1(6.62607015e-34*phys['f0_hz']/(1.380649e-23*phys['temperature_k']))
   S+=50*10**(67.4/10)*(1.380649e-23*3.955+th*ki**2*phys['kappa2']/((kt/2)**2+(2*np.pi*(ff-1e6))**2))*resp**2
  impulse=np.fft.fftshift(ifft(np.sqrt(fs*S)));fir=impulse[design//2-L//2:design//2+L//2+1];P=float(np.mean(S)*fs);Pf=float(np.sum(abs(fir)**2));gexpected=ifft(S)[:51];gexpected/=gexpected[0]
  assert abs(Pf/P-1)<.001
  firg=np.array([np.vdot(fir[:-k],fir[k:])/Pf if k else 1 for k in range(51)]);assert np.max(abs(firg-gexpected))<.001
  H=fft(fir,M);rng=np.random.default_rng(20261115+100*index)
  def white(n):return (rng.standard_normal(n)+1j*rng.standard_normal(n))/np.sqrt(2)
  history=white(L-1);tail=None;first=None;total=0;sumz=0j;sumabs=sumabs2=0.;corr=np.zeros(51,complex);clip=0
  ae=np.linspace(0,.5,4097);pe=np.linspace(-np.pi,np.pi,1025);ac=np.zeros(4096,np.int64);pc=np.zeros(1024,np.int64);t0=time.perf_counter();cpu=time.process_time()
  for block in range((target+B-1)//B):
   n=min(B,target-total);w=white(n);inp=np.r_[history,w];z=ifft(fft(inp,M)*H)[L-1:L-1+n];history=inp[-(L-1):].copy()
   step=4/65535;ci=np.round(z.real/step);cq=np.round(z.imag/step);clip+=int(np.count_nonzero((ci<-32768)|(ci>32767)|(cq<-32768)|(cq>32767)));z=(np.clip(ci,-32768,32767)+1j*np.clip(cq,-32768,32767))*step
   if first is None:first=z[:50].copy();h5.create_dataset(mode+'/first_100000_adc_v',data=z[:100000],compression='gzip')
   amp=abs(z);ac+=np.histogram(amp,ae)[0];pc+=np.histogram(np.angle(z[amp>0]),pe)[0];sumz+=z.sum();sumabs+=float(amp.sum());sumabs2+=float(np.sum(amp**2))
   F=fft(z,next_fast_len(2*n));corr+=ifft(abs(F)**2)[:51]
   if tail is not None:
    for k in range(1,51):corr[k]+=np.sum(z[:k]*np.conj(tail[-k:]))
   tail=z[-50:].copy();total+=n
   if block%25==0 or total==target:
    progress=dict(mode=mode,samples=total,target=target,elapsed_s=time.perf_counter()-t0,overall_elapsed_s=time.perf_counter()-startall)
    (OUT/'progress.json').write_text(json.dumps(progress));print(json.dumps(progress),flush=True)
  assert total==target and ac.sum()==target and clip==0
  mu=sumz/target;center=corr.copy()
  for k in range(51):
   sa=sumz-(tail[-k:].sum() if k else 0);sb=sumz-(first[:k].sum() if k else 0)
   center[k]=(corr[k]-mu*np.conj(sa)-np.conj(mu)*sb+(target-k)*abs(mu)**2)/(target-k)
  g=center/center[0];power=sumabs2/target;assert abs(power/P-1)<.003;assert np.max(abs(g[:11]-gexpected[:11]))<.003
  lo=ae[:-1];hi=ae[1:]
  def objective(logs):
   sig=np.exp(logs);a=lo**2/(2*sig**2);dd=(hi**2-lo**2)/(2*sig**2)
   return float(-np.sum(ac*(-a+np.log(-np.expm1(-dd)))))
  opt=minimize_scalar(objective,bounds=(np.log(np.sqrt(power/2)/2),np.log(np.sqrt(power/2)*2)),method='bounded');assert opt.success
  row=dict(samples=total,mean_amplitude_v=sumabs/target,std_amplitude_v=float(np.sqrt(power-(sumabs/target)**2)),rms_v=float(np.sqrt(power)),mean_i_v=float(mu.real),mean_q_v=float(mu.imag),sigma_fit_v=float(np.exp(opt.x)),expected_power_v2=P,FIR_power_relative_error=Pf/P-1,wall_s=time.perf_counter()-t0,cpu_s=time.process_time()-cpu,clipped_samples=clip,checks_passed=True)
  report['results'][mode]=row
  for name,data in dict(amplitude_edges_v=ae,amplitude_counts=ac,phase_edges_rad=pe,phase_counts=pc,g1_empirical=g,g1_expected=gexpected,lag_s=np.arange(51)/fs).items():h5.create_dataset(mode+'/'+name,data=data)
  h5.flush();(OUT/'metrics.json').write_text(json.dumps(report,indent=2));print(mode,json.dumps(row),flush=True)
 report['status']='complete';report['wall_s']=time.perf_counter()-startall;report['input_sha256']={str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in (CAL,PHY,Path(__file__))};h5.attrs['metadata_json']=json.dumps(report)
(OUT/'metrics.json').write_text(json.dumps(report,indent=2));print('COMPLETE',flush=True)
