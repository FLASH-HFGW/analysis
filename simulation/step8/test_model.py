import unittest
import numpy as np
from scipy.integrate import quad
from model import lf_power,lf_transfer,ideal_mean_variance,mean_variance_from_psd,LFModel
class LFPhysicsTests(unittest.TestCase):
 def test_causal_shelf_realizes_power(self):
  f=np.r_[0,np.geomspace(.1,1e8,200)]
  np.testing.assert_allclose(abs(lf_transfer(f,12500,.02))**2,lf_power(f,12500,.02),atol=1e-15)
  self.assertAlmostEqual(lf_power(0,12500,.02),.02)
 def test_independent_sources_keep_same_plateau(self):
  f=np.linspace(-1e6,1e6,10000)
  np.testing.assert_allclose(lf_power(f,12500,.02),.98*lf_power(f,12500,0)+.02,atol=1e-15)
 def test_long_time_transition(self):
  t=np.geomspace(1e-5,1,400);v=ideal_mean_variance(t,1,12500,.02);s=np.gradient(np.log(v),np.log(t))
  self.assertLess(s[80],-1.5);self.assertAlmostEqual(s[-1],-1,delta=.002)
  v0=ideal_mean_variance(t,1,12500,0);self.assertAlmostEqual(np.gradient(np.log(v0),np.log(t))[-1],-2,delta=.001)
 def test_sampled_white_mean_variance(self):
  fs=5e6
  for N in [128,8192,2**21]:
   got=mean_variance_from_psd(lambda f:np.ones_like(f)*2,N,fs)
   self.assertAlmostEqual(got/(2*fs/N),1,delta=.0005)
 def test_numerical_prediction_converges(self):
  fs=5e6;s=lambda f:lf_power(f,12500,.02)/(1+(f/1.9e6)**8)
  for N in [512,32768,2**21]:
   a=mean_variance_from_psd(s,N,fs,128);b=mean_variance_from_psd(s,N,fs,256)
   self.assertAlmostEqual(a/b,1,delta=.002)
 def test_calibration_factorization_reconstructs_measured_curve(self):
  m=LFModel.__new__(LFModel);m.cfg={'calibration_bridge_halfwidth_hz':300000.}
  m.curves={'TM010':(np.array([-1e6,-3e5,-5e4,5e4,3e5,1e6]),np.array([1.,1.,.65,.65,1.,1.]))}
  f=np.linspace(-1e6,1e6,2001);original,base,calLF=m.response('TM010',f)
  np.testing.assert_allclose(base**2*calLF,original**2,atol=1e-15)
  np.testing.assert_array_equal(base[abs(f)>=3e5],original[abs(f)>=3e5])
  index=np.argmin(abs(f));self.assertLess(original[index]**2,.5)
  self.assertAlmostEqual(base[index]**2*lf_power(0,12500,.02),.02)
 def test_negative_covariance_tail_has_LF_pole_time(self):
  fs=5e6;n=2**18;f=np.fft.fftfreq(n,1/fs);baseline=np.exp(-(f/8e5)**2)
  delta=np.fft.ifft((lf_power(f,12500,.02)-1)*baseline).real
  i=round(10e-6*fs);j=round(20e-6*fs)
  self.assertLess(delta[i],0)
  self.assertAlmostEqual(delta[j]/delta[i],np.exp(-2*np.pi*12500*10e-6),delta=.001)
 def test_primary_IF_filter_does_not_notch_other_modes_at_final_zero(self):
  import json
  from pathlib import Path
  cfg=json.loads(Path(__file__).with_name('parameters.json').read_text())
  values={m:float(lf_power(shift,cfg['fc_hz'],cfg['epsilon'])) for m,shift in cfg['LF_primary_offset_hz'].items()}
  self.assertAlmostEqual(values['TM010'],.02)
  self.assertGreater(values['TM011'],.9999999)
  self.assertGreater(values['TM012'],.9999999)
if __name__=='__main__':unittest.main()
