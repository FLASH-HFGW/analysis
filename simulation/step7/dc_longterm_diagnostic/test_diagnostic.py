"""Meaningful checks of the diagnostic estimators, without experimental data."""
import sys,unittest
from pathlib import Path
import numpy as np
from scipy import stats
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import spectral_matrix,association,notch_metrics,FS
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'examples'))
from iq_noise_v2 import ComplexMoments

class DiagnosticChecks(unittest.TestCase):
 def test_ADC_rescaling_preserves_v2_decomposition(self):
  rng=np.random.default_rng(3);z=(rng.normal(size=40000)+1j*rng.normal(size=40000))*.02+.003-.001j
  saved=ComplexMoments();saved.update(z/0.4);v=saved.export()
  self.assertAlmostEqual(v['dc_squared_v2']*.16,abs(z.mean())**2,places=16)
  self.assertAlmostEqual(v['ac_squared_v2']*.16,np.mean(abs(z-z.mean())**2),places=16)
  self.assertAlmostEqual(v['total_squared_v2']*.16,np.mean(abs(z)**2),places=16)

 def test_spectral_matrix_reconstructs_I_minus_iQ(self):
  n=16384;k=300;rng=np.random.default_rng(4);t=np.arange(n)
  z=np.exp(2j*np.pi*k*t/n)+.05*(rng.normal(size=n)+1j*rng.normal(size=n))
  f,pi,pq,plus,minus,c=spectral_matrix(z,n,'none',spec=n)
  w=np.hanning(n);direct=abs(np.fft.fft(z*w))**2/(FS*np.sum(w*w))
  np.testing.assert_allclose(plus,direct[:n//2+1],rtol=1e-8,atol=1e-20)
  np.testing.assert_allclose(minus[1:-1],direct[-1:n//2:-1],rtol=1e-8,atol=1e-20)
  self.assertGreater(plus[k],100*minus[k])

 def test_mean_subtraction_only_affects_dc_and_hann_neighbours_for_constant(self):
  n=65536;rng=np.random.default_rng(7);z=.02*(rng.normal(size=n)+1j*rng.normal(size=n))+.1+.05j
  f,*before=spectral_matrix(z,n,'none',spec=n);_,*after=spectral_matrix(z,n,'global',spec=n)
  mask=f>2000
  np.testing.assert_allclose(before[2][mask],after[2][mask],rtol=2e-4,atol=1e-16)

 def test_SPEC_centering_is_diagnostic_and_does_not_mutate_input(self):
  rng=np.random.default_rng(8);z=rng.normal(size=32768)+1j*rng.normal(size=32768);copy=z.copy()
  spectral_matrix(z,4096,'spec',spec=8192)
  np.testing.assert_array_equal(z,copy)

 def test_time_trend_is_not_a_residual_correlation(self):
  rng=np.random.default_rng(10);t=np.arange(1000,dtype=float);x=t+rng.normal(size=len(t));y=2*t+rng.normal(size=len(t))
  a=association(x,y,t);self.assertGreater(a['pearson'],.99);self.assertLess(abs(a['after_time_degree_1']),.1)

 def test_Rice_reduces_to_Rayleigh_at_zero_offset(self):
  x=np.linspace(0,8,1000)
  np.testing.assert_allclose(stats.rice(b=0,scale=.7).sf(x),stats.rayleigh(scale=.7).sf(x),atol=1e-14)
  np.testing.assert_allclose(stats.rayleigh(scale=.7).logsf(x),-x*x/(2*.7**2),atol=1e-13)

if __name__=='__main__':unittest.main()
