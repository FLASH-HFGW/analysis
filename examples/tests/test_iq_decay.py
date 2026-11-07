import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fit_iq_correlation_decay import fit_positive_envelope, fit_upper_envelope

class DecayFitTests(unittest.TestCase):
    def test_recovers_exponential_envelope_of_alternating_covariance(self):
        t=np.arange(201)*.2
        y=.03*np.exp(-t/.7)*np.cos(2*np.pi*t/.4)
        fit=fit_positive_envelope(t,y)
        self.assertAlmostEqual(fit['tau_us'],.7,places=4)
        self.assertTrue(all(x>0 for x in fit['peak_covariance']))
        self.assertNotIn(0,fit['peak_indices'])

    def test_does_not_fit_unresolved_or_absent_positive_peaks(self):
        t=np.arange(201)*.2
        with self.assertRaisesRegex(ValueError,'Fewer than three'):
            fit_positive_envelope(t,-np.exp(-t))

class UpperEnvelopeFitTests(unittest.TestCase):
    def test_recovers_decay_and_negative_baseline_through_four_us(self):
        t=np.arange(201)*.2
        y=-.006+.03*np.exp(-t/.8)*np.cos(2*np.pi*t/.4)
        fit=fit_upper_envelope(t,y)
        self.assertAlmostEqual(fit['tau_us'],.8,places=4)
        self.assertAlmostEqual(fit['offset'],-.006,places=6)
        self.assertEqual(fit['plot_range_us'][1],4.)
        self.assertGreaterEqual(fit['selected_range_us'][1],3.99)
        self.assertTrue(any(x<0 for x in fit['peak_covariance']))

    def test_rejects_no_resolved_upper_maxima(self):
        t=np.arange(201)*.2
        with self.assertRaisesRegex(ValueError,'Fewer than four'):
            fit_upper_envelope(t,np.exp(-t))

if __name__=='__main__':unittest.main()
