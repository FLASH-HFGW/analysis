import unittest

import numpy as np

from analyze_iq_history import pooled_statistics
from iq_products import binned_pairs


class IQAnalysisTests(unittest.TestCase):
    def test_history_pools_unequal_exposures_and_between_run_offsets(self):
        def entry(samples, mean):
            return dict(stats=dict(temporal_samples=samples, mean_I_V=mean,
                                   mean_Qhardware_V=mean, var_I_V2=2, var_Q_V2=3,
                                   cov_I_Qhardware_V2=1))
        pooled = pooled_statistics([entry(1, 0), entry(3, 4)])
        self.assertEqual(pooled["mean_i_v"], 3)
        self.assertEqual(pooled["var_i_v2"], 5)
        self.assertEqual(pooled["covariance_v2"], 4)
        self.assertAlmostEqual(pooled["ac_rms_v"], np.sqrt(11))

    def test_require_distinct_overlapping_thermometer_bins(self):
        ts = np.arange(12)*60
        self.assertEqual(binned_pairs(ts[:-1], ts[:-1], ts, ts)["r"], None)
        self.assertAlmostEqual(binned_pairs(ts, -ts, ts, ts)["r"], -1)


if __name__ == "__main__":
    unittest.main()
