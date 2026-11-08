import sys
from pathlib import Path
import numpy as np
import unittest
from unittest import mock
from scipy.signal import firwin, lfilter
from numpy.testing import assert_allclose
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyze_iq_filtered_bands import BandFilter, FilterWorkspace, statistics


def test_streaming_matches_one_block():
    rng = np.random.default_rng(42)
    z = rng.normal(size=40000)+1j*rng.normal(size=40000)
    first = BandFilter(5e6, 100e3, 50e3)
    t, full = first.process(z)
    second = BandFilter(5e6, 100e3, 50e3)
    parts = [second.process(v) for v in np.split(z,[101,8000,17003])]
    assert_allclose(np.concatenate([v[0] for v in parts]),t)
    assert_allclose(np.concatenate([v[1] for v in parts]),full,atol=1e-12)


def test_tones_and_phase_increment():
    fs = 5e6
    n = np.arange(50000)
    z = np.exp(2j*np.pi*102e3*n/fs)
    t, y = BandFilter(fs,100e3,50e3).process(z)
    result = statistics(y,None)
    assert_allclose(result['rms_v'],1,atol=1e-4)
    assert_allclose(result['increment_mean_rad'],2*np.pi*2000*20/fs,atol=1e-10)
    _, rejected = BandFilter(fs,-100e3,50e3).process(z)
    assert np.sqrt(np.mean(abs(rejected)**2)) < 1e-4


class FilterTests(unittest.TestCase):
    def test_streaming_matches_one_block(self):
        test_streaming_matches_one_block()

    def test_tones_and_phase_increment(self):
        test_tones_and_phase_increment()

    def test_matches_independent_causal_filter_at_irregular_spec_boundaries(self):
        rng = np.random.default_rng(91)
        z = rng.normal(size=12003) + 1j*rng.normal(size=12003)
        z[2001] += 20j
        for fs,center,width,taps,decimation in [(5e6,0,50e3,2001,20),
                                               (5e6,100e3,50e3,2001,20),
                                               (2e6,-321e3,70e3,51,5)]:
            with self.subTest(center=center,taps=taps):
                n=np.arange(len(z),dtype=np.int64)
                oscillator=np.exp(-2j*np.pi*np.remainder(n*center/fs,1.))
                reference=lfilter(firwin(taps,width/2,fs=fs,window=('kaiser',8.6)),[1.],z*oscillator)
                indices=n[(n%decimation==0)&(n>=taps-1)]
                band=BandFilter(fs,center,width,taps,decimation)
                blocks=[band.process(part) for part in np.split(z,[0,1,2000,2001,2002,2103,5500,len(z)])]
                actual_t=np.concatenate([t for t,_ in blocks]);actual=np.concatenate([v for _,v in blocks])
                assert_allclose(actual_t,(indices-(taps-1)/2)/fs,rtol=0,atol=0)
                assert_allclose(actual,reference[indices],rtol=2e-12,atol=2e-13)

    def test_shared_modes_reuse_oscillator_and_fir_spectrum_without_crosstalk(self):
        import analyze_iq_filtered_bands as filters
        rng=np.random.default_rng(17)
        signals=[rng.normal(size=8192)+1j*rng.normal(size=8192) for _ in range(3)]
        workspace=FilterWorkspace()
        bands=[BandFilter(5e6,100e3,50e3,101,20,workspace=workspace) for _ in signals]
        original_exp=np.exp
        with mock.patch.object(filters,'fft',wraps=filters.fft) as transforms, \
             mock.patch.object(filters.np,'exp',wraps=original_exp) as oscillators:
            outputs=[band.process(z) for band,z in zip(bands,signals)]
        self.assertEqual(oscillators.call_count,1)
        self.assertEqual(transforms.call_count,4)  # Three data FFTs, one shared kernel.
        for z,(times,actual) in zip(signals,outputs):
            n=np.arange(len(z));mixed=z*original_exp(-2j*np.pi*np.remainder(n*100e3/5e6,1.))
            expected=lfilter(bands[0].h,[1.],mixed)[100::20]
            assert_allclose(actual,expected,rtol=2e-12,atol=2e-13)

    def test_shared_workspace_does_not_mix_different_kernels(self):
        rng=np.random.default_rng(11);z=rng.normal(size=4000)+1j*rng.normal(size=4000)
        workspace=FilterWorkspace()
        for width in [50e3,80e3,50e3]:
            band=BandFilter(5e6,0,width,101,20,workspace=workspace)
            _,actual=band.process(z)
            assert_allclose(actual,lfilter(band.h,[1.],z)[100::20],rtol=2e-12,atol=2e-13)


if __name__ == '__main__':
    unittest.main()
