"""Synthetic regressions for the lightweight MIDAS pilot."""
from types import SimpleNamespace
import unittest

import h5py
import numpy as np

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
                  for serial, words in ((0, []), (1, [1, 2, 7, 2]), (3, [8, 2]))]
        with h5py.File("test", "w", driver="core", backing_store=False) as f:
            process(events, odb, f, args)
            self.assertEqual(f["timing"].attrs["pps_source"], "SPGP")
            self.assertEqual(f["timing/pps"]["received_index"].tolist(), [9, 15])
            self.assertEqual(len(f["timing/pps_waveform"]), 0)
            self.assertEqual(len(f["quality/breaks"]), 2)
            self.assertEqual(f["timing/windows"]["segment"].tolist(), [0, 0, 1])

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
        for kind, product in (("SPEC", "psd"), ("SPE", "fft")):
            def pack(data):
                if kind == "SPEC":
                    return {"SPEC": bank(data.flatten(), 5)}
                return {f"SPE{i}": bank(data[:, i], 5) for i in range(7)} | {
                    "SPGP": bank(np.empty(0, np.uint32), 6)}
            args = SimpleNamespace(compression=None, max_events=10,
                                   thresholds=[4], product=product, workers=1)
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
                np.testing.assert_allclose(f["spectra/mode"][0], expected, atol=1e-8)
                self.assertEqual(np.argmax(abs(x[1:])) + 1, 8)
                self.assertLess(f["statistics/mode"][0]["parseval_relative_error"], 1e-6)
                a = f["anomalies/mode/episodes"][0]
                self.assertEqual((a["received_index"], a["duration_samples"]), (27, 1))
                self.assertEqual(f["anomalies/mode/population"][0]["above_samples"], 1)


if __name__ == "__main__":
    unittest.main()
