import sys
from pathlib import Path
import numpy as np
from numpy.testing import assert_allclose
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from survey_iq_sidebands import band_statistics


def test_shift_and_gain_have_different_symmetry():
    f = np.linspace(-10, 10, 20001)
    profile = lambda shift: 1 / (1 + ((f-shift)/2)**2)
    baseline = band_statistics(f, profile(0), 0, 3, 1, .01)
    gain = band_statistics(f, 4*profile(0), 0, 3, 1, .01)
    shifted = band_statistics(f, profile(.3), 0, 3, 1, .01)
    assert abs(baseline['asymmetry']) < 1e-12
    assert_allclose(gain['asymmetry'], baseline['asymmetry'], atol=1e-12)
    assert_allclose(gain['wings_over_center'], baseline['wings_over_center'])
    assert shifted['asymmetry'] > .1


def test_uncovered_band_rejected():
    try:
        band_statistics(np.arange(-10,11), np.ones(21), 0, 20, 2, 0)
    except ValueError:
        return
    raise AssertionError('Expected uncovered band rejection')


if __name__ == "__main__":
    test_shift_and_gain_have_different_symmetry()
    test_uncovered_band_rejected()
    print("2 checks passed")
