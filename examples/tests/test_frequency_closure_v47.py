"""Coordinate transforms are identities, not empirical curve corrections."""
from pathlib import Path
import sys,unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_fft_coordinates_v47 import reflect_shifted,spectrum_from_frames

class FrequencyClosureTests(unittest.TestCase):
 def test_reflection_matches_fft_of_conjugate_odd_and_even(self):
  rng=np.random.default_rng(47)
  for n in [16,17,16383,16384]:
   z=rng.normal(size=n)+1j*rng.normal(size=n)
   original=np.fft.fftshift(abs(np.fft.fft(z))**2)
   expected=np.fft.fftshift(abs(np.fft.fft(z.conj()))**2)
   np.testing.assert_allclose(reflect_shifted(original),expected,rtol=2e-12,atol=1e-8)
   np.testing.assert_array_equal(reflect_shifted(reflect_shifted(original)),original)
   np.testing.assert_array_equal(np.sort(reflect_shifted(original)),np.sort(original))
 def test_signed_raw_decoding_places_known_tones_at_positive_frequencies(self):
  n=1048576;t=np.arange(n)/5e6;frames=np.zeros((n,8),dtype=np.int16)
  for j,f in enumerate([750000,1250000,1750000]):
   frames[:,2*j]=np.rint(1000*np.cos(2*np.pi*f*t)).astype(np.int16)
   frames[:,2*j+1]=np.rint(-1000*np.sin(2*np.pi*f*t)).astype(np.int16)
  power,error=spectrum_from_frames(frames)
  freq=np.fft.fftshift(np.fft.fftfreq(power.shape[1],1/5e6))
  for j,f in enumerate([750000,1250000,1750000]):self.assertLess(abs(freq[np.argmax(power[j])]-f),5e6/power.shape[1])
  self.assertLess(error,1e-12)

if __name__=='__main__':unittest.main()
