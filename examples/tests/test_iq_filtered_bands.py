import sys
from pathlib import Path
import numpy as np
from numpy.testing import assert_allclose
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyze_iq_filtered_bands import BandFilter, statistics


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


if __name__ == '__main__':
    test_streaming_matches_one_block()
    test_tones_and_phase_increment()
    print('2 checks passed')
