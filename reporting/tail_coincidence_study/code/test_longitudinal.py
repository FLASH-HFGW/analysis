"""Regression checks against committed Run 1429 sparse products."""
import csv
from collections import Counter
import unittest

import numpy as np

from stream_longitudinal import MODES, STUDY, gaussian_tail, group_products


class LongitudinalTest(unittest.TestCase):
    def test_checkpoint_grouping_and_shifts(self):
        def read(name):
            with (STUDY/'tables'/name).open() as stream:
                return list(csv.DictReader(stream))
        hits = read('pilot1429_T7_samples.csv')
        indices = [np.array([int(r['index']) for r in hits if r['mode'] == m]) for m in MODES]
        amps = [np.array([float(r['amplitude_V']) for r in hits if r['mode'] == m]) for m in MODES]
        _, groups, _, controls, summary = group_products(indices, amps, 1048576000)
        expected_groups = read('pilot1429_clusters.csv')
        self.assertEqual(Counter((g['mode'], g['gap'], g['peak'], g['multiplicity']) for g in groups),
                         Counter((g['mode'], int(g['gap_nonexceeding_samples']),
                                  int(g['peak']), int(g['multiplicity'])) for g in expected_groups))
        expected_controls = read('pilot1429_time_shift_controls.csv')
        def key(r):
            return (int(r['window_us']), r['kind'].replace('triple', '--'.join(MODES)),
                    int(r['shift_samples']), int(r['count']))
        self.assertEqual(Counter(map(key, controls)), Counter(map(key, expected_controls)))
        expected_summary = read('pilot1429_coincidence_summary.csv')
        def unshifted(r):
            return (int(r['window_us']), r['kind'].replace('triple', '--'.join(MODES)),
                    int(r['count']))
        self.assertEqual(Counter(map(unshifted, summary)),
                         Counter(map(unshifted, expected_summary)))

    def test_gaussian_integral_reduces_to_rayleigh(self):
        moments = dict(mean_I_V=0, mean_Qhardware_V=0, var_I_V2=1,
                       var_Q_V2=1, cov_I_Qhardware_V2=0)
        for radius in (1, 3, 5, 7):
            self.assertAlmostEqual(gaussian_tail(radius, moments, 4096) /
                                   np.exp(-radius**2/2), 1.0, places=12)


if __name__ == '__main__':
    unittest.main()
