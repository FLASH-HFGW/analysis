"""Small coarse-PSD proper Gaussian validation, not full-run tail significance."""
from pathlib import Path
import sys,json,csv,time
import numpy as np
R=Path(__file__).resolve().parents[3];O=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'examples'));from iq_products import open_product
N=2**18;FS=5e6;REPS=24;rng=np.random.default_rng(20261123);rows=[];start=time.perf_counter()
with open_product(R/'comparison/root-pilot/inputs/run01429_iq_v3.1.root') as p:
 f=p.file;ff=f['short_psd/frequency_hz'][:];native=np.fft.fftshift(np.fft.fftfreq(N,1/FS))
 for mode in ['TM010','TM011','TM012']:
  a=f['statistics/'+mode].attrs;mu=complex(a['mean_I_V'],-a['mean_Qhardware_V']);variance=a['var_I_V2']+a['var_Q_V2'];short=f['short_psd/rectangular/'+mode][:];target=np.interp(native,ff,short);target*=variance/(target.sum()*FS/N);expected=np.fft.ifftshift(target);obs=np.zeros(N);totalpower=0.;pseudo=0j;counts=np.zeros(3,np.int64);sigma=json.load(open(O/'data/frozen_thresholds.json'))['1429'][mode]['sigma_Rayleigh_V'];thr=sigma*(np.sqrt(np.pi/2)+np.array([3,5,7])*np.sqrt((4-np.pi)/2))
  for rep in range(REPS):
   X=np.sqrt(FS*N*expected/2)*(rng.standard_normal(N)+1j*rng.standard_normal(N));z=np.fft.ifft(X)+mu;step=4/65535;z=(np.clip(np.rint(z.real/step),-32768,32767)+1j*np.clip(np.rint(z.imag/step),-32768,32767))*step;center=z-z.mean();obs+=abs(np.fft.fft(center))**2/(FS*N);totalpower+=np.mean(abs(center)**2);pseudo+=np.mean(center**2);amp=abs(z);counts+=np.array([np.count_nonzero(amp>t) for t in thr])
  measured=np.fft.fftshift(obs/REPS);block=512;mt=measured.reshape(-1,block).mean(1);tt=target.reshape(-1,block).mean(1);error=float(np.median(abs(mt-tt)/tt));varerror=abs(totalpower/REPS-variance)/variance;proper=abs(pseudo)/(totalpower);assert error<.08 and varerror<.02 and proper<.03
  rows.append(dict(run=1429,mode=mode,model='proper complex Gaussian; coarse short-PSD shape; measured deterministic mean; quantized',seed=20261123,replicates=REPS,samples_per_rep=N,total_samples=REPS*N,total_duration_s=REPS*N/FS,variance_relative_error=varerror,median_coarse_PSD_relative_error=error,properness_abs=proper,T3_count=int(counts[0]),T5_count=int(counts[1]),T7_count=int(counts[2]),scope='periodic independent short records; no joined boundary clusters; insufficient exposure for full-run T7 or coincidence inference; observed improper covariance not matched'))
with (O/'tables/null_pilot.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
(O/'validation/null_pilot.json').write_text(json.dumps({'elapsed_s':time.perf_counter()-start,'rows':rows,'validated':'PSD/variance/properness only','observed_IQ_covariance_matched':False,'full_length_significance':False},indent=2));print('NULL PILOT VALIDATED')
