"""Convert and validate the ROOT worker product before using existing GFAL publication."""
import hashlib
import json
from pathlib import Path
import re
import sys
import time

import h5py
import uproot

from iq_midas_aux import FILE_REF
from iq_root import assert_equal_datasets, convert, load_root, validate_roundtrip
from run3_storage import ENDPOINT, RAW, gfal, local_identity, publish, size, validate_product, verify


def external_references(field_json):
    """Resolve exact ODB file references; do not assign measurements by proximity."""
    fields = json.loads(field_json)
    result = []
    for snapshot, values in fields.items():
        for key, value in values.items():
            if not isinstance(value, str) or not re.search("file|path|cali|fit/output", key, re.I):
                continue
            for entry in value.splitlines():
                match = FILE_REF.search(entry.strip())
                if not match:
                    continue
                url = f"{ENDPOINT}/{RAW}/calib/{match[1]}"
                info = gfal("stat", url, missing=True)
                item = dict(snapshot=snapshot, odb_key=key, original=entry)
                if info is None:
                    item["status"] = "reference_not_found_in_calib_directory"
                else:
                    item.update(url=url, stat=info, adler32=gfal("sum", url, "ADLER32").split()[-1],
                                status="matched_exact_basename")
                result.append(item)
    return result


def group_complete(hdf):
    group = hdf["thermometers"]
    if not bool(group.attrs["scan_reached_eor"]):
        raise ValueError("temperature extraction did not reach EOR")
    result = {}
    for item in group.values():
        schema = json.loads(item.attrs["channels_json"])
        name = schema["equipment"]
        result[name] = result.get(name, 0) + len(item["events"])
    return result


def check_root(path, run):
    with uproot.open(path) as file:
        manifest = json.loads(str(file["__iq_schema__"]))
        if manifest["product_schema"] != "3.1":
            raise ValueError("wrong ROOT product schema")
        root = load_root(file)
        if (int(root["metadata"].attrs["run_number"]) != run
                or not root["quality"].attrs["saw_eor"]
                or not root["thermometers"].attrs["scan_reached_eor"]
                or not len(root["timing/windows"])):
            raise ValueError("incomplete ROOT product")
        for node in ("odb/BOR/0", "odb/EOR/0"):
            item = root[node]
            if hashlib.sha256(item[:].tobytes()).hexdigest() != item.attrs["sha256"]:
                raise ValueError(f"ODB checksum mismatch: {node}")
        for key in ("adc_json", "odb_fields_json", "nominal_coordinates_json", "external_references_json"):
            json.loads(root["calibration"].attrs[key])
        banks, values = root["midas_aux/banks"], root["midas_aux/payload"]
        for row in banks[:]:
            if row["offset"] >= 0 and row["offset"]+row["bytes"] > len(values):
                raise ValueError("truncated archived bank")
        return set(name for name, doc in root.objects.items() if "dtype" in doc)


def compare_root(candidate, previous, run):
    names = check_root(candidate, run)
    if names != check_root(previous, run):
        raise ValueError("existing ROOT objects differ")
    with uproot.open(candidate) as a, uproot.open(previous) as b:
        x, y = load_root(a), load_root(b)
        for group, keys in {
            "metadata": ("pairs_json", "bor_settings_json", "bor_lo_json", "fs_hz", "iq_convention"),
            "calibration": ("adc_json", "odb_fields_json", "nominal_coordinates_json", "external_references_json"),
            "provenance": ("raw_url", "raw_size", "root_schema_version")}.items():
            for key in keys:
                if x[group].attrs[key] != y[group].attrs[key]:
                    raise ValueError(f"existing ROOT {group}/{key} differs")
        assert_equal_datasets(x, y, names)


def make_root(intermediate, settings, run, raw_url):
    validate_product(intermediate, run)
    started = time.perf_counter()
    with h5py.File(intermediate, "r+") as hdf:
        calibrate = hdf["calibration"]
        refs = external_references(calibrate.attrs["odb_fields_json"])
        calibrate.attrs["external_references_json"] = json.dumps(refs, sort_keys=True)
        calibrate.attrs["external_reference_policy"] = "Explicit ODB links only; unreferenced files unassociated"
        provenance = hdf.create_group("provenance")
        provenance.attrs.update(raw_url=raw_url, raw_size=hdf["metadata"].attrs["source_size_bytes"],
                                root_schema_version="3.1", software_commit=hdf["metadata"].attrs["software_commit"])
        thermo = group_complete(hdf)
        aux = hdf["midas_aux"]
        counts = dict(banks=len(aux["banks"]), events=len(aux["events"]), auxiliary_bytes=len(aux["payload"]),
                      bor_bytes=sum(len(d) for d in hdf["odb/BOR"].values()),
                      eor_bytes=sum(len(d) for d in hdf["odb/EOR"].values()),
                      windows=int(hdf["quality"].attrs["valid_windows"]), thermometers=thermo,
                      thermometers_complete=bool(hdf["thermometers"].attrs["complete"]),
                      calibration_references=refs,
                      analysis_wall_s=float(hdf["quality"].attrs["wall_s"]))
    if settings.get("reference"):
        reference = intermediate.parent/"reference.h5"
        original = settings["reference"]
        gfal("copy", "-K", "ADLER32", original["url"], reference.resolve().as_uri())
        identity = verify(original["url"], local_identity(reference))
        if any(original[key] != identity[key] for key in ("size", "local_adler32")):
            raise ValueError("authoritative HDF5 reference changed")
        validate_product(reference, run)
        with h5py.File(reference) as old, h5py.File(intermediate) as modern:
            names = []
            def keep(name, node):
                if isinstance(node, h5py.Dataset):
                    names.append(name)
            old.visititems(keep)
            counts["hdf5_reference_datasets_equal"] = assert_equal_datasets(old, modern, names)
    output = intermediate.with_suffix(".root")
    convert(intermediate, output, codec="zstd", native=True)
    counts["roundtrip_equal"] = validate_roundtrip(intermediate, output)
    check_root(output, run)
    identity = publish(output, settings["url"], probe=settings.get("probe", False), run=run)
    counts["conversion_validation_publication_wall_s"] = time.perf_counter()-started
    return identity, counts


if __name__ == "__main__":
    path, settings, run, raw = sys.argv[1:]
    settings = json.loads(settings)
    identity, counts = make_root(Path(path), settings, int(run), raw)
    Path("publication.json").write_text(json.dumps(dict(
        url=settings["url"], run=int(run), attempt=settings["attempt"], validated=True,
        root_schema="3.1", validation=counts, **identity), indent=2))
