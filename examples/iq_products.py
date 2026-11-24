"""Local read-only IQ product access shared by run and history reports."""
from collections import Counter
from contextlib import contextmanager
import json
from pathlib import Path

import h5py
import numpy as np


def json_value(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, np.generic):
        return json_value(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (tuple, list, np.ndarray)):
        return [json_value(v) for v in value]
    if isinstance(value, dict):
        return {k: json_value(v) for k, v in value.items()}
    return value


def write_json(path, obj):
    path.write_text(json.dumps(json_value(obj), indent=2, allow_nan=False) + "\n")


class Product:
    def __init__(self, file):
        self.file = file
        self.metadata = dict(file["metadata"].attrs)
        self.fs = self.metadata["fs_hz"]
        self.run = int(self.metadata["run_number"])
        self.spectra = file["spectra"]
        if self.spectra.attrs.get("profile") != "compact":
            raise ValueError("expected v3 compact spectra")
        self.modes = tuple(file["statistics"].keys())
        self.windows = file["timing/windows"][:]
        self.widths = self.spectra["window_bin_width_hz"][:]
        self.edges = self.spectra["window_bin_edges_hz"][:]
        adc = file["timing/digitizer_events"][:]
        self.time_start = int(adc["header_unix_s"][0])
        self.time_stop = int(adc["header_unix_s"][-1]) + 1
        # Use logging timestamps for environmental monitoring, not PPS UTC.
        keys = np.searchsorted(adc["received_index"], self.windows["received_index"], side="right") - 1
        self.window_headers = adc["header_unix_s"][keys]

    def frequency(self):
        attrs = self.spectra.attrs
        return attrs["frequency_first_hz"] + attrs["frequency_spacing_hz"] * np.arange(attrs["frequency_count"])

    def window_power(self, mode):
        data = self.spectra[mode]["window_psd"]
        return np.concatenate([np.asarray(data[i:i+16], dtype=float) @ self.widths
                               for i in range(0, len(data), 16)]) if len(data) else np.empty(0)

    def temperatures(self):
        for group in self.file.get("thermometers", {}).values():
            doc = json.loads(group.attrs["channels_json"])
            for ch in doc["channels"]:
                if ch["unit"] in ("K", "mK"):
                    yield (f'{doc["equipment"]}:{ch["index"]}:{ch["odb_name"]}', ch["unit"],
                           group["events"]["time_unix"], group["values"][:, ch["index"]])

    def apparatus(self):
        cal = self.file.get("calibration")
        aux = self.file.get("midas_aux")
        result = {}
        if cal is not None:
            result["calibration"] = {name: json.loads(cal.attrs[name]) for name in
                ("adc_json", "odb_fields_json", "nominal_coordinates_json", "external_references_json")
                if name in cal.attrs}
            result["psd_reference"] = cal.attrs.get("psd_reference")
        if aux is not None:
            eq = json.loads(aux.attrs["equipment_json"])
            events, banks = aux["events"][:], aux["banks"][:]
            counts, archived_bytes = Counter(), Counter()
            for bank in banks:
                event = str(events[bank["event_index"]]["event_id"])
                key = (eq.get(event, "unknown"), event, bank["name"].decode("ascii"))
                counts[key] += 1
                archived_bytes[key] += int(bank["bytes"]) if bank["offset"] >= 0 else 0
            result["bank_inventory"] = [
                dict(equipment=k[0], event_id=int(k[1]), bank=k[2],
                     count=counts[k], archived_bytes=archived_bytes[k]) for k in sorted(counts)]
        return result

    def excursions(self, mode):
        rows = self.file[f"anomalies/{mode}/population"][:]
        return {str(k): {name: int(rows[name][rows["threshold_rms"] == k].sum()) for name in
                         ("observed_samples", "above_samples", "episodes")}
                for k in np.unique(rows["threshold_rms"])}


@contextmanager
def open_product(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("stage the product locally first")
    if path.suffix == ".root":
        import uproot
        from iq_root import load_root

        with uproot.open(path) as file:
            yield Product(load_root(file))
    else:
        with h5py.File(path, "r") as file:
            yield Product(file)


def binned_pairs(t1, x, t2, y, seconds=60):
    def bins(t, values):
        keys = np.asarray(t) // seconds
        return {int(k): float(np.mean(values[(keys == k) & np.isfinite(values)]))
                for k in np.unique(keys[np.isfinite(values)])}
    xs, ys = bins(t1, np.asarray(x)), bins(t2, np.asarray(y))
    common = sorted(xs.keys() & ys.keys())
    if len(common) < 12:
        return {"matched_bins": len(common), "r": None}
    a, b = np.array([(xs[t], ys[t]) for t in common]).T
    return {"matched_bins": len(common),
            "r": float(np.corrcoef(a, b)[0, 1]) if a.std() and b.std() else None}
