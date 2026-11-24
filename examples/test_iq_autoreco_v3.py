"""Synthetic regressions for the lightweight MIDAS pilot."""
from types import SimpleNamespace
import unittest

import h5py
import numpy as np

from iq_compact_spectra import CompactSpectra, ShortSpectra
from analyze_midas_iq_v3 import PulseDetector, decode, process


def bank(data, tid=4):
    return SimpleNamespace(data=data, type=tid)


def event(serial, banks):
    return SimpleNamespace(banks=banks, header=SimpleNamespace(
        serial_number=serial, timestamp=0, event_id=1,
        is_midas_internal_event=lambda: False))


class PilotTests(unittest.TestCase):
    def test_decoder(self):
        raw = np.arange(-16, 16, dtype=np.int16).reshape(-1, 8)
        self.assertEqual(decode({"SPEC": bank(raw.flatten().view(np.uint16))})[0], "SPEC")
        np.testing.assert_equal(decode({"SPEC": bank(raw.flatten(), 5)})[1], raw.T)
        split = {f"SPE{i}": bank(raw[:, i], 5) for i in range(7)}
        np.testing.assert_equal(decode(split)[1], raw.T[:7])
        del split["SPE6"]
        np.testing.assert_equal(decode(split)[1], raw.T[:6])
        split["SPE5"] = bank(np.zeros(2, np.uint16))
        with self.assertRaises(ValueError):
            decode(split)

    def test_boundary_pulse(self):
        detector = PulseDetector()
        self.assertEqual(list(detector.feed([False, True, True], 8, 10)), [])
        self.assertEqual(list(detector.feed([True, False, True, False], 9, 13)),
                         [(8, 1, 11, 3), (9, 2, 15, 1)])

    def test_production_pps(self):
        adc = dict(Sampling_rate_MS=8e-6, Channel_range_mV=[2000]*6,
                   IQ_channel_pairs={"mode": [0, 1]})
        odb = {"Equipment": {"NetBox": {"Settings": adc},
                             "LocalOscill": {"Variables": {}}}, "Runinfo": {"Run number": 1}}
        args = SimpleNamespace(compression=None, max_events=10,
                               thresholds=[4], product="psd", workers=1)
        channels = {f"SPE{i}": bank(np.zeros(8, np.uint16)) for i in range(6)}
        events = [event(serial, channels | {"SPGP": bank(np.array(words, np.uint32), 6)})
                  for serial, words in ((0, []), (1, [1, 2, 7, 2]), (3, [7]))]
        with h5py.File("test", "w", driver="core", backing_store=False) as f:
            process(events, odb, f, args)
            self.assertEqual(f["timing"].attrs["pps_source"], "SPGP")
            self.assertEqual(f["timing/pps"]["received_index"].tolist(), [9, 15])
            self.assertEqual(len(f["timing/pps_waveform"]), 0)
            self.assertEqual(len(f["quality/breaks"]), 2)
            self.assertEqual(f["timing/windows"]["segment"].tolist(), [0, 0, 1])

    def test_short_psd_across_buffers_and_discontinuity(self):
        n = ShortSpectra.length
        fs = 5_000_000
        t = np.arange(n)
        tone = (2 + 3j + np.exp(2j*np.pi*321*t/n)).astype(np.complex64)
        short = ShortSpectra(fs, ["mode"], None, 1)
        source = np.concatenate([tone, 2*tone, np.full(29, 500, dtype=np.complex64)])
        for start, stop in ((0, 5000), (5000, 5010), (5010, n+7), (n+7, len(source))):
            short.feed({"mode": source[start:stop]}, stop-start)
        short.break_segment()
        source = np.concatenate([3*tone, tone[:35]])
        short.feed({"mode": source}, len(source))
        with h5py.File("test", "w", driver="core", backing_store=False) as f:
            short.finish(f, 3*n + 64)
            self.assertEqual(f.attrs["segments_per_mode"], 3)
            self.assertEqual(f.attrs["residual_samples_per_mode"], 64)
            rows = np.stack([tone, 2*tone, 3*tone]).astype(np.complex128)
            rows -= rows.mean(axis=1, keepdims=True)
            for name, weights in (("rectangular", np.ones(n)), ("hann", np.hanning(n))):
                x = np.fft.fftshift(np.fft.fft(rows*weights, axis=1), axes=1)
                expected = np.mean(abs(x)**2, axis=0)/(fs*np.sum(weights**2))
                d = f[name]["mode"]
                np.testing.assert_allclose(d[:], expected, rtol=2e-6, atol=1e-10)
                self.assertEqual(f["frequency_hz"][d[:].argmax()], 321*fs/n)
                self.assertLess(d.attrs["parseval_relative_error"], 2e-7)

    def test_compact_storage(self):
        n = 9
        x = np.arange(n, dtype=np.float32).astype(np.complex64) * (1+2j)
        power = np.abs(x)**2
        ordered = np.fft.fftshift(power)
        for product in ("psd", "fft"):
            args = SimpleNamespace(compression=None, bin_hz=4, max_psd=True,
                                   band=[(-2.5, 2)], band_product=product)
            with h5py.File("test", "w", driver="core", backing_store=False) as f:
                store = CompactSpectra(f, n, ["mode"], args)
                self.assertLess(store.write("mode", x, power), 1e-7)
                self.assertLess(store.write("mode", x*2, power*4), 1e-7)
                store.finish(2)
                np.testing.assert_array_equal(f["window_bin_width_hz"][:], [4, 4, 1])
                np.testing.assert_array_equal(f["window_bin_edges_hz"][:], [-4.5, -0.5, 3.5, 4.5])
                np.testing.assert_allclose(f["mode/mean_psd"][:], ordered*2.5)
                np.testing.assert_array_equal(f["mode/max_psd"][:], ordered*4)
                band = ordered[2:6] if product == "psd" else x[[-2, -1, 0, 1]]
                np.testing.assert_array_equal(f["mode/band_0"][0], band)

    def test_pipeline(self):
        n = 64
        phase = 2 * np.pi * np.arange(n) / 8
        raw = np.zeros((n, 8), np.int16)
        raw[:, 3] = np.rint(150*np.cos(phase)) + 200
        raw[:, 2] = np.rint(-150*np.sin(phase))
        raw[10, 3] += 2000
        adc = dict(Sampling_rate_MS=n/1e6, Channel_range_mV=[2000]*8,
                   IQ_channel_pairs={"mode": [3, 2]})
        odb = {"Equipment": {"NetBox": {"Settings": adc},
                             "LocalOscill": {"Variables": {}}}, "Runinfo": {"Run number": 1}}
        for kind, product in (("SPEC", "psd"), ("SPE", "fft"), ("SPE", "compact")):
            def pack(data):
                if kind == "SPEC":
                    return {"SPEC": bank(data.flatten(), 5)}
                return {f"SPE{i}": bank(data[:, i], 5) for i in range(7)} | {
                    "SPGP": bank(np.empty(0, np.uint32), 6)}
            args = SimpleNamespace(compression=None, max_events=10,
                                   thresholds=[4], product=product, workers=1, bin_hz=10,
                                   max_psd=False, band=[], band_product="psd")
            events = [event(0, pack(raw[:17])), event(2, pack(raw[:32])),
                      event(3, pack(raw[32:]))]
            with self.subTest(kind=kind), h5py.File("test", "w", driver="core", backing_store=False) as f:
                process(events, odb, f, args)
                w = f["timing/windows"][0]
                self.assertEqual((w["first_serial"], w["last_serial"], w["received_index"]), (2, 3, 17))
                self.assertEqual(f["quality"].attrs["discarded_samples"], 17)
                z = (raw[:, 3].astype(float) - 1j*raw[:, 2]) * (4/65535)
                x = np.fft.fft(z)/n
                expected = abs(x)**2 if product == "psd" else x
                if product == "compact":
                    np.testing.assert_allclose(f["spectra/mode/mean_psd"][:],
                                               np.fft.fftshift(abs(x)**2), atol=1e-8)
                    self.assertEqual(f["quality"].attrs["spectral_samples"], 64)
                    self.assertEqual(f["quality"].attrs["temporal_samples"], 81)
                else:
                    np.testing.assert_allclose(f["spectra/mode"][0], expected, atol=1e-8)
                self.assertEqual(f["statistics/mode"].attrs["temporal_samples"], 81)
                self.assertEqual(f["histograms/mode/amplitude_counts"][:].sum(), 81)
                self.assertEqual(np.argmax(abs(x[1:])) + 1, 8)
                self.assertLess(f["statistics/mode"][0]["parseval_relative_error"], 1e-6)
                a = f["anomalies/mode/episodes"][0]
                self.assertEqual((a["received_index"], a["duration_samples"]), (27, 1))
                self.assertEqual(f["anomalies/mode/population"][0]["above_samples"], 1)
                self.assertEqual((a["start_serial"], a["start_offset_samples"]), (2, 10))


if __name__ == "__main__":
    unittest.main()
