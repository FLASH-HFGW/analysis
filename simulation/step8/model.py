"""Initial, unfitted LF shelf; no experimental or global side effects on import."""
import json
from pathlib import Path
import numpy as np
from scipy.integrate import simpson,trapezoid

def lf_power(f,fc,epsilon):
 f=np.asarray(f,float)
 return (f*f+epsilon*fc*fc)/(f*f+fc*fc)

def lf_transfer(f,fc,epsilon):
 # Stable causal analog shelf: zero=-sqrt(epsilon)*wc, pole=-wc.
 return (1j*np.asarray(f)+np.sqrt(epsilon)*fc)/(1j*np.asarray(f)+fc)

def ideal_mean_variance(T,S0,fc,epsilon):
 T=np.asarray(T,float);a=2*np.pi*fc
 return S0*(epsilon/T+(1-epsilon)*(-np.expm1(-a*T))/(a*T*T))

class LFModel:
 def __init__(self,cfg):
  self.cfg=cfg
  self.cal=json.loads(Path(cfg['calibration_reconstruction']).read_text())
  self.phys=json.loads(Path(cfg['cavity_parameters']).read_text())['mode_results']
  self.curves={}
  for mode,pts in self.cal['curves'].items():
   off=self.cal['comparison'][mode]['rf_if_offset_hz'];xx=np.array([p['rf_hz']-off for p in pts]);kk=np.array([p['kz_integrated'] for p in pts])*cfg['LF_data_over_cal_amplitude'];ix=np.argsort(xx);self.curves[mode]=(xx[ix],kk[ix])
 def response(self,mode,f,bridge=None):
  f=np.asarray(f);x,k=self.curves[mode];original=np.interp(f,x,k,left=0,right=0);base=original.copy()
  # Only TM010 has an observed LF feature in calibration's final-frequency band.
  # Fixed shoulder bridge is a conditional factorization, not a measured LF20 curve.
  if mode=='TM010':
   b=bridge or self.cfg['calibration_bridge_halfwidth_hz'];left=np.interp(-b,x,k);right=np.interp(b,x,k)
   base=np.where(abs(f)<b,left+(right-left)*(f+b)/(2*b),base)
  calLF=np.divide(original**2,base**2,out=np.ones_like(base),where=base>0)
  return original,base,calLF
 def analog(self,mode,f,bridge=None,epsilon=None,interpretation='shelf'):
  cfg=self.cfg;p=self.phys[mode];f=np.asarray(f,float)
  eps=cfg['epsilon'] if epsilon is None else epsilon
  original,base,calLF=self.response(mode,f,bridge)
  primary=f+cfg['LF_primary_offset_hz'][mode];F=lf_power(primary,cfg['fc_hz'],eps)
  ki=2*np.pi*p['f0_hz']/p['q0'];kt=ki*(1+p['kappa1']+p['kappa2'])
  cavityIF=p['f0_hz']-cfg['primary_LO_hz']-cfg['LF_primary_offset_hz'][mode]
  thermal=6.62607015e-34*p['f0_hz']/np.expm1(6.62607015e-34*p['f0_hz']/(1.380649e-23*p['temperature_k']))
  gain=50*10**(cfg['RF_gain_db']/10)
  source=gain*(1.380649e-23*cfg['receiver_Tn_K']+thermal*ki**2*p['kappa2']/((kt/2)**2+(2*np.pi*(f-cavityIF))**2))
  baseline=source*base**2
  if interpretation=='shelf':return baseline*F
  if interpretation=='two_sources':
   hp=lf_power(primary,cfg['fc_hz'],0.)
   return baseline*(1-eps)*hp+baseline*eps
  if interpretation=='old_calibration':return source*original**2
  if interpretation=='double_counting_control':return source*original**2*F
  if interpretation=='no_LF':return baseline
  raise ValueError(interpretation)
 def sampled(self,mode,f,**kwargs):
  # The measured base contains final LPF/mixer response: never add that LPF twice.
  return sum(self.analog(mode,np.asarray(f)+alias*self.cfg['fs_hz'],**kwargs) for alias in (-1,0,1))

def mean_variance_from_psd(spectrum,block_samples,fs,tail_start_cycles=128,points_per_cycle=48):
 """Integrate bilateral sampled PSD against exact discrete boxcar response.

 Resolve first128 sinc oscillations explicitly. Beyond that average sin² to1/2;
 integrate smooth tail on a log grid. Accuracy checked by doubling this cutoff.
 No coarse fixed FFT grid is used to infer sub-Hz noise or long-time variance.
 """
 N=int(block_samples);T=N/fs;fmax=fs/2;edge=min(tail_start_cycles/T,fmax)
 count=max(129,int(np.ceil(edge*T*points_per_cycle))+1);f=np.linspace(0,edge,count)
 window=(np.sinc(f*T)/np.sinc(f/fs))**2
 values=(spectrum(f)+spectrum(-f))*window
 ans=float(simpson(values,x=f))
 if edge<fmax:
  ft=np.geomspace(edge,fmax,12001)
  response=.5/(N*N*np.sin(np.pi*ft/fs)**2)
  ans+=float(trapezoid((spectrum(ft)+spectrum(-ft))*response,ft))
 return ans
