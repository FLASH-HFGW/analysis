"""Independent physics checks: no experimental inputs or generated artifacts."""
import unittest
import numpy as np

class PhysicalConventions(unittest.TestCase):
    def test_constant_gain_cancels_normalized_covariance(self):
        rng=np.random.default_rng(17)
        z=rng.normal(size=8192)+1j*rng.normal(size=8192)
        def g(a):
            a=a-a.mean()
            r=np.array([np.vdot(a[:len(a)-k],a[k:])/(len(a)-k) for k in range(32)])
            return r/r[0]
        np.testing.assert_allclose(g(z),g(z*37*np.exp(.7j)),atol=1e-14)

    def test_lorentzian_has_expected_amplitude_decay_time(self):
        fs=100e6;n=2**18;tau=1e-6
        f=np.fft.fftfreq(n,1/fs)
        psd=1/(1+(2*np.pi*f*tau)**2)
        corr=np.fft.ifft(psd).real;corr/=corr[0]
        # Exclude the origin where finite bandwidth truncates the Lorentzian.
        lags=np.arange(20,201); times=lags/fs
        measured=-1/np.polyfit(times,np.log(corr[lags]),1)[0]
        self.assertAlmostEqual(measured/tau,1,delta=.002)

    def test_parseval_complex_psd_and_rayleigh_scale(self):
        n=2**16;fs=5e6;rng=np.random.default_rng(23);sigma=.02
        z=sigma*(rng.normal(size=n)+1j*rng.normal(size=n))
        psd=abs(np.fft.fft(z))**2/(fs*n)
        self.assertAlmostEqual(float(psd.sum()*fs/n),float(np.mean(abs(z)**2)),places=15)
        self.assertAlmostEqual(float(np.sqrt(np.mean(abs(z)**2)/2))/sigma,1,delta=.01)

    def test_narrow_spectral_deficit_has_longer_correlation_scale(self):
        fs=5e6;n=2**18;f=np.fft.fftfreq(n,1/fs)
        # Gaussian deficit has negative covariance away from zero, with width
        # in time inversely proportional to its spectral width.
        def corr(width):
            return np.fft.ifft(1-.5*np.exp(-.5*(f/width)**2)).real
        broad=corr(1e5);narrow=corr(1e4)
        self.assertLess(broad[1],0);self.assertLess(narrow[1],0)
        self.assertGreater(abs(narrow[50]/narrow[1]),abs(broad[50]/broad[1]))

if __name__=='__main__':unittest.main()
