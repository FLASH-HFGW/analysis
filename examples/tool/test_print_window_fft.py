"""Tests for the one-second PSD rebinning utility."""
import os
import unittest

import numpy as np

from print_window_fft import MODES, open_product, rebin_edges, rebin_psd


class RebinTest(unittest.TestCase):
    def test_overlap_on_nonuniform_grid_and_partial_bin(self):
        edges = [0, 1, 3, 4, 5, 6]
        spectra = [[1, 3, 2, 8, 0], [0, 8, 2, 3, 1]]
        centers, rebinned = rebin_psd(spectra, edges, 2.5)
        np.testing.assert_array_equal(centers, [1.25, 3.75, 5.5])
        np.testing.assert_allclose(rebinned, [[2.2, 4.6, 0], [4.8, 3.6, 1]])
        np.testing.assert_allclose(rebinned @ [2.5, 2.5, 1], np.asarray(spectra) @ np.diff(edges))

    def test_all_grid_shapes_and_quiet_bins(self):
        edges = np.arange(-10., 11.)
        psd = np.full((2, 20), 1e-25)
        psd[:, 0] = [1., 1e10]
        for bin_hz in (0.13, 1., 3.1, 5., 20., 40.):
            with self.subTest(bin_hz=bin_hz):
                target = rebin_edges(edges, bin_hz)
                centers, result = rebin_psd(psd, edges, bin_hz)
                np.testing.assert_allclose(result @ np.diff(target), psd @ np.diff(edges), rtol=1e-14)
                self.assertTrue(np.all(np.diff(centers) > 0))
                self.assertTrue(np.all(result >= 0))
                if bin_hz < 20:
                    np.testing.assert_allclose(result[:, -1], psd[:, -1], atol=0, rtol=1e-14)

    def test_invalid_and_roundoff_negative_input(self):
        np.testing.assert_array_equal(rebin_psd([[1., -1e-16]], [0, 1, 2], 1)[1], [[1, 0]])
        for input_psd, edges, width in (
                ([[1, -0.01]], [0, 1, 2], 1), ([[1, float("nan")]], [0, 1, 2], 1),
                ([[1, 2]], [0, 2, 1], 1), ([[1]], [0, 1], 0),
                ([[1]], [0, 1], float("inf")), ([1], [0, 1], 1)):
            with self.subTest(psd=input_psd, edges=edges, width=width):
                with self.assertRaises(ValueError):
                    rebin_psd(input_psd, edges, width)

    @unittest.skipUnless(os.environ.get("FLASH_RUN1429_ROOT"), "set FLASH_RUN1429_ROOT for real ROOT validation")
    def test_run1429(self):
        width = 305.17578125
        with open_product(os.environ["FLASH_RUN1429_ROOT"]) as product:
            self.assertEqual(product.run, 1429)
            self.assertTrue(np.all(np.diff(product.windows["received_index"]) > 0))
            target = rebin_edges(product.edges, width)
            for mode in MODES:
                # Materialize as float64 before summing to avoid float32 reduction error.
                values = np.asarray(product.file[f"spectra/{mode}/window_psd"][:], dtype=np.float64)
                original = np.sum(values * product.widths, axis=1)
                centers, result = rebin_psd(values, product.edges, width)
                power = np.sum(result * np.diff(target), axis=1)
                self.assertEqual(result.shape, (209, 16384))
                self.assertTrue(np.all(np.diff(centers) > 0))
                self.assertTrue(np.all(result >= 0))
                np.testing.assert_allclose(power, original, rtol=1e-12, atol=0)
                print(f"{mode}: max relative power error {np.max(abs(power/original-1)):.3g}")


if __name__ == "__main__":
    unittest.main()
