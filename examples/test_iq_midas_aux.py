"""Test exact auxiliary bytes and omission of digitizer payloads."""
import h5py
from midas import TID_BYTE, TID_WORD
from midas.event import Event
import unittest

from iq_midas_aux import Archive


class ArchiveTests(unittest.TestCase):
    def test_bank_offsets_and_raw_unknown_bank(self):
        event = Event()
        event.header.event_id = 1
        event.header.serial_number = 42
        event.header.timestamp = 1784909100
        event.create_bank("SPE0", TID_WORD, [100, 1000])
        event.create_bank("UNKN", TID_BYTE, bytes([0, 255, 42]))
        packed = event.pack()
        decoded = Event()
        decoded.unpack(packed, use_numpy=True)
        with h5py.File("memory", "w", driver="core", backing_store=False) as f:
            archive = Archive(f)
            archive.record(decoded, packed[16:])
            self.assertEqual(archive.event_rows[0][2], 42)
            self.assertEqual(archive.bank_rows[0][-1], -1)
            self.assertEqual(archive.bank_rows[1][-1], 0)
            self.assertEqual(archive.payload[:].tobytes(), bytes([0,255,42]))
