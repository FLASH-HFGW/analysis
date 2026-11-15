"""Exact full-run IQ tail counts and density; deterministic replay of frozen toy."""
from pathlib import Path
import sys,json,time
import numpy as np,h5py
from scipy.fft import fft,ifft,next_fast_len
R=Path('/home/mazzitel/HFGW');O=R/'analysis-work/Run2/reports/iq_noise_summary_v31/data';O.mkdir(parents=True,exist_ok=True)
S=R/'analysis-work/Run2/simulation/toy_full_run680';m=json.loads((S/'comparison.json').read_text());names=list(m['results']);fit=next((R/'analysis-work/Run2/reports/iq_noise_summary_v25/data').rglob('rayleigh_fit_ADC_corrected.json'));sd={x['mode']:x['sigma_v'] for x in json.loads(fit.read_text())['fits']};st={k:v['sigma_fit_v'] for k,v in m['results'].items()};r=np.sqrt(np.pi/2)+np.array([3,5,7])*np.sqrt((4-np.pi)/2)
N=512;limits={k:1.12*max(sd[k],st[k])*r[-1] for k in names};state={}
for pop in ('toy','data'):
 for k in names:state[pop,k]=dict(hist=np.zeros((N,N),np.int64),counts=np.zeros(3,np.int64),n=0,tail=[],outside=0)
def add(pop,k,z):
 s=state[pop,k];a=abs(z);sig=(st if pop=='toy' else sd)[k];s['counts']+=np.count_nonzero(a[:,None]>sig*r,axis=0);s['n']+=len(z)
 lim=limits[k];ix=np.floor((z.real+lim)*N/(2*lim)).astype(np.int64);iy=np.floor((z.imag+lim)*N/(2*lim)).astype(np.int64);ok=(ix>=0)&(ix<N)&(iy>=0)&(iy<N);s['outside']+=int((~ok).sum());s['hist']+=np.bincount(ix[ok]*N+iy[ok],minlength=N*N).reshape(N,N)
 s['tail'].append(z[a>sig*r[1]])
def persist():
 report={}
 for (pop,k),s in state.items():
  if not s['n']:continue
  assert int(s['hist'].sum())+s['outside']==s['n']
  np.savez_compressed(O/f'full_iq_{pop}_{k}.npz',hist=s['hist'],edges=np.linspace(-limits[k],limits[k],N+1),tail=np.concatenate(s['tail']),counts=s['counts'],samples=s['n'])
  report[f'{pop}_{k}']=dict(samples=s['n'],above_3_5_7=s['counts'].tolist(),sigma_v=(st if pop=='toy' else sd)[k],outside_plot=s['outside'])
 (O/'full_iq_counts.json').write_text(json.dumps(report,indent=2))
sys.path.insert(0,'/cvmfs/sft-flash.infn.it/package/midas/python');import midas.file_reader
reader=midas.file_reader.MidasFile('/home/mazzitel/flash-data/data/LNF/run00680.mid.gz',use_numpy=True)
for ie,event in enumerate(reader):
 if event.header.is_midas_internal_event() or 'SPEC' not in event.banks:continue
 frames=np.asarray(event.banks['SPEC'].data,dtype=np.uint16).view(np.int16).reshape(-1,8)
 for i,k in enumerate(names):add('data',k,(frames[:,2*i].astype(float)-1j*frames[:,2*i+1].astype(float))*(4/65535))
 if ie%100==0:print('RAW',ie,state['data',names[0]]['n'],flush=True)
persist();print('RAW complete',flush=True)
# Replay the exact seed/filter/block sequence of simulate_full_run.py; skip covariance.
c=json.loads((R/'analysis-work/Run2/diagnostics/normalization_audit_20261114/calibration_reconstruction.json').read_text());p=json.loads((R/'analysis-work/Run2/simulation/step6/metrics.json').read_text())['mode_results'];fs=5e6;target=1048576000;B=2**20;L=65537;M=next_fast_len(B+L-1);design=2**20;f=np.fft.fftfreq(design,1/fs)
with h5py.File(S/'toy_full_run680.h5') as orig:
 for index,(k,phys) in enumerate(p.items()):
  pts=c['curves'][k];offset=c['comparison'][k]['rf_if_offset_hz'];xx=np.array([v['rf_hz']-offset for v in pts]);kk=np.array([v['kz_integrated'] for v in pts]);order=np.argsort(xx);xx=xx[order];kk=kk[order];ps=np.zeros(design)
  for alias in (-1,0,1):
   ff=f+alias*fs;resp=np.interp(ff,xx,kk,left=0,right=0);ki=2*np.pi*phys['f0_hz']/phys['q0'];kt=ki*(1+phys['kappa1']+phys['kappa2']);th=6.62607015e-34*phys['f0_hz']/np.expm1(6.62607015e-34*phys['f0_hz']/(1.380649e-23*phys['temperature_k']))
   ps+=50*10**(67.4/10)*(1.380649e-23*3.955+th*ki**2*phys['kappa2']/((kt/2)**2+(2*np.pi*(ff-1e6))**2))*resp**2
  imp=np.fft.fftshift(ifft(np.sqrt(fs*ps)));fir=imp[design//2-L//2:design//2+L//2+1];H=fft(fir,M);rng=np.random.default_rng(20261115+100*index)
  def white(n):return (rng.standard_normal(n)+1j*rng.standard_normal(n))/np.sqrt(2)
  history=white(L-1);ac=np.zeros(4096,np.int64);ae=orig[k+'/amplitude_edges_v'][:]
  for block in range((target+B-1)//B):
   n=min(B,target-block*B);inp=np.r_[history,white(n)];z=ifft(fft(inp,M)*H)[L-1:L-1+n];history=inp[-(L-1):].copy();step=4/65535;z=(np.clip(np.round(z.real/step),-32768,32767)+1j*np.clip(np.round(z.imag/step),-32768,32767))*step
   if block==0:assert np.array_equal(z[:100000],orig[k+'/first_100000_adc_v'][:])
   add('toy',k,z);ac+=np.histogram(abs(z),ae)[0]
   if block%100==0:print(k,block,flush=True)
  assert np.array_equal(ac,orig[k+'/amplitude_counts'][:]);persist();print(k,'verified identical full-run toy',flush=True)
print('COMPLETE',flush=True)
