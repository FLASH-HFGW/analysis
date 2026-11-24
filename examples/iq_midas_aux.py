"""Lossless MIDAS auxiliary payload archive for the ROOT serialization stage."""
import hashlib
import json
import re

import numpy as np
from midas import endian_format_flag
from midas.event import Bank, all_bank_header_size
from midas.file_reader import MidasFile, Odb

from iq_acquisition_metadata import PAIRS, extract_coordinates
from extract_thermometers import equipment_map

EVENT = np.dtype([("event_id", "u2"), ("trigger_mask", "u2"), ("serial", "u4"),
                  ("time_unix", "u4"), ("body_bytes", "u4")])
BANK = np.dtype([("event_index", "u8"), ("name", "S4"), ("tid", "u4"),
                 ("bytes", "u4"), ("offset", "i8")])
DIGITIZER_BANKS = {"SPEC", *(f"SPE{i}" for i in range(8))}
CALIBRATION = re.compile(r"vna|cali|resona|(?:^|[ _])q(?:[ _0-9]|$)|gain|atten|twpa|pump|magnet|inject|power|signal|field|sweep|tone|run description|with_lo", re.I)
FILE_REF = re.compile(r"(?:^|/)(?:calib/)?([-\w.]+\.(?:csv|txt|s[1-9]p[1-9]|dat|json|npz))$", re.I)


class Archive:
    def __init__(self, output):
        self.root = output.create_group("midas_aux")
        self.root.attrs.update(schema_version="1", byte_order=endian_format_flag,
                               absent_payload_offset=-1)
        self.payload = self.root.create_dataset("payload", shape=(0,), maxshape=(None,),
                                                chunks=(65536,), dtype="u1")
        self.odb = output.create_group("odb")
        self.calibration = output.create_group("calibration", track_order=True)
        self.event_rows, self.bank_rows, self.special = [], [], []
        self.bor = None
        self.bor_timestamp = None
        self.fields = {}

    def copy_payload(self, raw):
        offset = len(self.payload)
        if len(raw):
            self.payload.resize(offset + len(raw), axis=0)
            self.payload[offset:] = np.frombuffer(raw, dtype="u1")
        return offset

    def record(self, event, body):
        h = event.header
        row = len(self.event_rows)
        self.event_rows.append((h.event_id, h.trigger_mask, h.serial_number,
                                h.timestamp, h.event_data_size_bytes))
        if h.is_midas_internal_event():
            if h.is_bor_event() or h.is_eor_event():
                document = Odb(body).data
                key = "BOR" if h.is_bor_event() else "EOR"
                group = self.odb.require_group(key)
                snapshot = group.create_dataset(str(len(group)), data=np.frombuffer(body, dtype="u1"))
                snapshot.attrs.update(event_index=row, sha256=hashlib.sha256(body).hexdigest())
                fields = calibration_fields(document)
                for source, values in tuple(fields.items()):
                    if isinstance(values, list) and len(values) >= 16:
                        array = np.asarray(values)
                        if array.dtype.kind in "biuf" and array.ndim == 1:
                            leaf = hashlib.sha256(source.encode()).hexdigest()[:12]
                            dataset = self.calibration.create_dataset(f"measurements/{key}/{leaf}", data=array)
                            dataset.attrs.update(odb_path=source, snapshot=key)
                            fields[source] = {"dataset": dataset.name, "samples": len(array)}
                self.fields[key] = fields
                if key == "BOR" and self.bor is None:
                    self.bor = document
                    self.bor_timestamp = int(h.timestamp)
            else:
                self.special.append((row, self.copy_payload(body), len(body)))
            return
        offset = all_bank_header_size
        while offset < len(body) - 4:
            bank = Bank()
            end = offset + event.get_bank_header_size()
            bank.fill_header_from_bytes(body[offset:end], event.is_bank_32(), event.is_bank_data_64bit_aligned())
            end_payload = end + bank.size_bytes
            if end_payload > len(body):
                raise ValueError("truncated MIDAS bank")
            omitted = h.event_id == 1 and bank.name in DIGITIZER_BANKS
            archived = -1 if omitted else self.copy_payload(memoryview(body)[end:end_payload])
            self.bank_rows.append((row, bank.name.encode("ascii"), bank.type, bank.size_bytes, archived))
            offset = end_payload + bank.get_expected_padding()

    def finish(self, meta, eor):
        if self.bor is None or "EOR" not in self.odb or not eor:
            raise ValueError("full auxiliary archive requires BOR and EOR")
        self.root.create_dataset("events", data=np.asarray(self.event_rows, dtype=EVENT))
        self.root.create_dataset("banks", data=np.asarray(self.bank_rows, dtype=BANK))
        self.root.create_dataset("internal_messages", data=np.asarray(self.special, dtype=[
            ("event_index", "u8"), ("offset", "u8"), ("bytes", "u8")]))
        mapping = {key: value["equipment"] for key, value in equipment_map(self.bor).items()}
        self.root.attrs.update(equipment_json=json.dumps(mapping, sort_keys=True),
                               excluded_payload="event 1 digitizer banks; see timing/pps_waveform for SPE6")
        self.calibration.attrs["odb_fields_json"] = json.dumps(self.fields, sort_keys=True)
        self.calibration.attrs["adc_json"] = json.dumps(dict(
            sample_rate_hz=float(meta["fs_hz"]), ranges=json.loads(meta["bor_settings_json"])["Channel_range_mV"],
            range_unit="mV peak", adc_bits=16, scale_v_per_count="2*peak_voltage/65535",
            pairs=json.loads(meta["pairs_json"]), iq_convention=meta["iq_convention"],
            source="/Equipment/NetBox/Settings (BOR), metadata/pairs_json"))
        compatible = json.loads(meta["pairs_json"]) == {k:list(p) for k,p in PAIRS.items()}
        try:
            if not compatible:
                raise ValueError("mapping differs from the documented coordinate model")
            coords = extract_coordinates(self.bor, iq_sign=-1, bor_timestamp=self.bor_timestamp)
        except ValueError as exc:
            coords = dict(status="unavailable", reason=str(exc))
        self.calibration.attrs["nominal_coordinates_json"] = json.dumps(coords, sort_keys=True)
        self.calibration.attrs["psd_reference"] = "ADC voltage; no RF correction"


def calibration_fields(document):
    fields = {}

    def visit(obj, path):
        for key, value in obj.items():
            if key.endswith("/key"):
                continue
            full = f"{path}/{key}"
            if isinstance(value, dict):
                visit(value, full)
            elif CALIBRATION.search(full) or (isinstance(value, str) and FILE_REF.search(value)):
                fields[full] = value
    for name in ("Equipment", "Experiment", "Runinfo"):
        if name in document:
            visit(document[name], "/" + name)
    return fields


class CapturingReader(MidasFile):
    def __init__(self, path, archive):
        self.archive = archive
        super().__init__(path, use_numpy=True)

    def read_this_event_body(self):
        self.file.seek(self.this_event_payload_offset)
        n = self.event.header.event_data_size_bytes
        body = self.file.read(n)
        if len(body) != n:
            raise EOFError("truncated MIDAS event")
        self.event.unpack_body(body, 0, self.use_numpy)
        self.archive.record(self.event, body)
        return self.event
