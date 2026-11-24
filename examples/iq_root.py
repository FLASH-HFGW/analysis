"""Experimental ROOT serialization for the numeric v3 HDF5 schema."""
import argparse
import base64
import json
import os
from pathlib import Path
import resource
import tempfile
import time

import numpy as np


def encode_attr(value):
    if isinstance(value, str):
        return {"text": value}
    array = np.asarray(value)
    if array.dtype.hasobject:
        raise TypeError("unsupported object-valued attribute")
    return dict(dtype=array.dtype.str, shape=array.shape,
                data=base64.b64encode(array.tobytes()).decode("ascii"))


def decode_attr(doc):
    if "text" in doc:
        return doc["text"]
    x = np.frombuffer(base64.b64decode(doc["data"]), dtype=doc["dtype"]).reshape(doc["shape"])
    return x[()] if not x.ndim else x


def describe_dtype(dtype):
    if dtype.names is None:
        return dtype.str
    fields = []
    for name in dtype.names:
        field, offset = dtype.fields[name][:2]
        base, shape = field.subdtype or (field, ())
        fields.append((name, base.str, shape, offset))
    return {"fields": fields, "itemsize": dtype.itemsize}


def dtype_of(desc, annotations=None):
    if isinstance(desc, str):
        return np.dtype(desc)
    names, formats, offsets = [], [], []
    for name, base, shape, offset in desc["fields"]:
        names.append(name)
        dt = np.dtype(base)
        if annotations and name in annotations:
            dt = np.dtype(dt, metadata=annotations[name])
        formats.append(np.dtype((dt, tuple(shape))) if shape else dt)
        offsets.append(offset)
    return np.dtype(dict(names=names, formats=formats, offsets=offsets, itemsize=desc["itemsize"]))


def columns(dtype, shape):
    for i, name in enumerate(dtype.names or (None,)):
        base = dtype[name] if name is not None else dtype
        if base.subdtype:
            base, extra = base.subdtype
        else:
            extra = ()
        dims = (*shape, *extra)
        prefix = name if name is not None else "value"
        if base.kind == "c":
            yield name, prefix + "_real", np.dtype(f"f{base.itemsize//2}"), dims, "real"
            yield name, prefix + "_imag", np.dtype(f"f{base.itemsize//2}"), dims, "imag"
        elif base.kind in "SV":
            yield name, prefix + "_bytes", np.dtype("u1"), (*dims, base.itemsize), "bytes"
        elif base.kind in "buif":
            yield name, prefix, base.newbyteorder("="), dims, "value"
        else:
            raise TypeError(f"unsupported ROOT dataset dtype {base}")


def to_columns(rows, fields):
    data = {}
    for field, branch, base, shape, part in fields:
        vals = rows[field] if field is not None else rows
        if part == "bytes":
            vals = np.ascontiguousarray(vals).view(np.uint8).reshape(len(rows), *shape)
        elif part != "value":
            vals = getattr(vals, part)
        data[branch] = np.asarray(vals, dtype=base)
    return data


def slabs(shape, dtype):
    count = shape[0] if shape else 1
    row_size = dtype.itemsize * int(np.prod(shape[1:], dtype=np.int64))
    step = max(1, 8 * 2**20 // max(1, row_size))
    for i in range(0, count, step):
        yield slice(i, min(count, i+step))


def native_path(name):
    """Map the stable, logical reader paths onto ROOT directories."""
    parts = name.split("/")
    kind = parts[0]
    if kind == "spectra" and len(parts) > 2:
        return "/".join((parts[1], "Spectra", *parts[2:]))
    if kind == "short_psd" and len(parts) == 3:
        return f"{parts[2]}/Spectra/short_{parts[1]}"
    if kind in ("statistics", "histograms", "anomalies") and len(parts) >= 2:
        dirs = {"statistics": "Statistics", "histograms": "Histograms", "anomalies": "Anomalies"}
        tail = parts[2:] or ["windows"]
        return "/".join((parts[1], dirs[kind], *tail))
    areas = {"metadata": "Acquisition", "quality": "Acquisition/Quality",
             "spectra": "Acquisition/SpectralAxes", "short_psd": "Acquisition/ShortFFT",
             "midas_aux": "SlowControl", "odb": "ODB", "calibration": "Calibration",
             "timing": "Timing", "thermometers": "Thermometers", "provenance": "Provenance"}
    return "/".join((areas.get(kind, kind), *parts[1:]))


def convert(source, output, codec="zlib", native=False):
    import h5py
    import uproot

    if output.exists():
        raise FileExistsError(output)
    compression = {"none": None, "zlib": uproot.ZLIB(4), "zstd": uproot.ZSTD(4)}[codec]
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        candidate = Path(temp) / "output.root"
        with h5py.File(source) as h5, uproot.recreate(candidate, compression=compression, initial_directory_bytes=65536) as root:
            schema = {}
            directories = {"": root}
            written = set()

            def directory(key):
                if key not in directories:
                    parent, _, name = key.rpartition("/")
                    directories[key] = directory(parent).mkdir(name, initial_directory_bytes=4096)
                return directories[key]

            def copy(name, item):
                doc = schema[name] = {"attrs": {k: encode_attr(v) for k, v in item.attrs.items()}}
                if not isinstance(item, h5py.Dataset):
                    if native and name:
                        group_path = native_path(name)
                        # Some logical groups distribute their datasets among modes.
                        if name.startswith(("statistics/", "spectra/")):
                            group_path = name.split("/")[1] + "/Metadata/" + name.split("/")[0]
                        directory(group_path)["Attributes"] = json.dumps(json_attrs(item.attrs))
                    return
                shape, dtype = item.shape, item.dtype
                key = native_path(name) if native else name.replace("/", "__")
                doc.update(shape=shape, dtype=describe_dtype(dtype), key=key)
                annotations = {field: dict(dtype[field].metadata) for field in (dtype.names or ())
                               if dtype[field].metadata}
                if annotations:
                    doc["field_annotations"] = annotations
                if dtype.metadata:
                    doc["dtype_annotations"] = dict(dtype.metadata)
                fields = list(columns(dtype, shape[1:]))
                parent, _, leaf = key.rpartition("/")
                branch_dir = directory(parent)
                if key in written:
                    raise ValueError(f"ROOT key collision for {name}")
                written.add(key)
                tree = branch_dir.mktree(leaf, {branch: np.dtype((base, dims)) if dims else base
                                          for _, branch, base, dims, _ in fields})
                for section in slabs(shape, dtype):
                    rows = item[section] if shape else np.asarray(item[()]).reshape(1)
                    tree.extend(to_columns(rows, fields))
            copy("", h5)
            h5.visititems(copy)
            root["__iq_schema__"] = json.dumps({"version": 1, "product_schema": "3.1" if native else "experimental", "objects": schema})
        os.link(candidate, output)


class RootNode:
    def __init__(self, file, objects, path=""):
        self.file, self.objects, self.path = file, objects, path
        doc = objects[path]
        self.attrs = {k: decode_attr(v) for k, v in doc["attrs"].items()}
        if "dtype" in doc:
            self.shape = tuple(doc["shape"])
            self.dtype = dtype_of(doc["dtype"], doc.get("field_annotations"))
            if "dtype_annotations" in doc:
                self.dtype = np.dtype(self.dtype, metadata=doc["dtype_annotations"])
            self.columns = list(columns(self.dtype, self.shape[1:]))

    def keys(self):
        prefix = self.path + "/" if self.path else ""
        return [k[len(prefix):] for k in self.objects if k.startswith(prefix) and k != self.path
                and "/" not in k[len(prefix):]]

    def values(self):
        return [self[k] for k in self.keys()]

    def __contains__(self, key):
        return (self.path + "/" + key if self.path else key) in self.objects

    def get(self, key, default=None):
        return self[key] if key in self else default

    def __len__(self):
        return self.shape[0]

    def read(self, selection, field=None):
        if isinstance(selection, slice):
            start, stop, stride = selection.indices(self.shape[0])
        elif isinstance(selection, (int, np.integer)):
            if not -self.shape[0] <= selection < self.shape[0]:
                raise IndexError(selection)
            start = int(selection) % self.shape[0]
            stop, stride = start + 1, 1
        else:
            start, stop, stride = 0, self.shape[0] if self.shape else 1, 1
        if stride < 0:
            return self.read(slice(None), field)[selection]
        dtype = self.dtype if field is None else self.dtype[field]
        result = np.empty((max(0, stop-start), *self.shape[1:]), dtype=dtype)
        tree = self.file[self.objects[self.path]["key"]]
        for name, branch, _, _, part in self.columns:
            if field is not None and name != field:
                continue
            values = tree[branch].array(entry_start=start, entry_stop=max(start, stop), library="np")
            dest = result[name] if field is None and name is not None else result
            if part == "bytes":
                dest[...] = values.view(dest.dtype).reshape(dest.shape)
            elif part == "value":
                dest[...] = values
            else:
                getattr(dest, part)[...] = values
        if isinstance(selection, (int, np.integer)) or not self.shape:
            return result[0]
        return result[::stride] if isinstance(selection, slice) else result[selection]

    def __getitem__(self, key):
        if hasattr(self, "dtype"):
            if isinstance(key, str):
                return self.read(slice(None), key)
            if isinstance(key, tuple) and key:
                data = self.read(key[0])
                return data[key[1:] if isinstance(key[0], (int, np.integer))
                            else (slice(None), *key[1:])]
            return self.read(key)
        path = self.path + "/" + key if self.path else key
        return RootNode(self.file, self.objects, path)


def load_root(file):
    manifest = json.loads(str(file["__iq_schema__"]))
    if manifest["version"] != 1:
        raise ValueError("unsupported ROOT IQ schema")
    return RootNode(file, manifest["objects"])


def json_attrs(attrs):
    """Readable ROOT attributes (the manifest retains their exact types)."""
    def value(x):
        if isinstance(x, bytes):
            return x.decode("utf-8", errors="backslashreplace")
        if isinstance(x, np.generic):
            return value(x.item())
        if isinstance(x, np.ndarray):
            return [value(y) for y in x]
        if isinstance(x, float) and not np.isfinite(x):
            return None
        return x
    return {k: value(v) for k, v in attrs.items()}


def assert_equal_datasets(reference, candidate, names):
    count = 0
    for name in names:
        a, b = reference[name], candidate[name]
        if a.shape != b.shape or a.dtype != b.dtype:
            raise ValueError(f"different shape or dtype at {name}")
        for section in slabs(a.shape, a.dtype):
            a_data, b_data = (a[section], b[section]) if a.shape else (a[()], b[()])
            if np.asarray(a_data).tobytes() != np.asarray(b_data).tobytes():
                raise ValueError(f"different data at {name}")
        count += 1
    return count


def validate_roundtrip(source, output):
    import h5py
    import uproot

    with h5py.File(source) as hdf, uproot.open(output) as native:
        root = load_root(native)
        paths = [""]
        hdf.visit(paths.append)
        if set(paths) != set(root.objects):
            raise ValueError("ROOT lossy object inventory")
        datasets = []
        for path in paths:
            original = hdf[path] if path else hdf
            other = root[path] if path else root
            if set(original.attrs) != set(other.attrs):
                raise ValueError(f"ROOT attributes differ at {path}")
            for key in original.attrs:
                np.testing.assert_equal(original.attrs[key], other.attrs[key])
            if isinstance(original, h5py.Dataset):
                datasets.append(path)
        return assert_equal_datasets(hdf, root, datasets)


def benchmark(hdf, root):
    import h5py
    import uproot

    with h5py.File(hdf) as source, uproot.open(root) as target:
        product = load_root(target)
        paths = [path for path, doc in product.objects.items() if "dtype" in doc]
        for reader, label in ((source, "h5"), (product, "root")):
            t = time.perf_counter()
            cpu = time.process_time()
            for name in paths:
                ds = reader[name]
                for section in slabs(ds.shape, ds.dtype):
                    _ = ds[section] if ds.shape else ds[()]
            wall, cpu_elapsed = time.perf_counter()-t, time.process_time()-cpu
            t = time.perf_counter()
            for mode in ("TM010", "TM011", "TM012"):
                reader[f"spectra/{mode}/window_psd"][0:1]
            print(label, "full_wall_s", wall, "full_cpu_s", cpu_elapsed,
                  "select_wall_s", time.perf_counter()-t, flush=True)
        for name, doc in product.objects.items():
            ds, other = (source[name] if name else source), (product[name] if name else product)
            for key, value in ds.attrs.items():
                np.testing.assert_equal(value, other.attrs[key])
            if "dtype" not in doc:
                continue
            assert ds.dtype == other.dtype and ds.shape == other.shape
            for section in slabs(ds.shape, ds.dtype):
                a = ds[section] if ds.shape else ds[()]
                b = other[section] if ds.shape else other[()]
                if np.asarray(a).tobytes() != np.asarray(b).tobytes():
                    raise ValueError(f"ROOT data differ at {name}")
        print("datasets_verified", len(paths), "rss_kib", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--codec", choices=("none", "zlib", "zstd"), default="zstd")
    p.add_argument("--benchmark", action="store_true")
    a = p.parse_args()
    if a.benchmark:
        benchmark(a.source, a.output)
    else:
        t, cpu = time.perf_counter(), time.process_time()
        convert(a.source, a.output, a.codec)
        print("bytes", a.output.stat().st_size, "wall_s", time.perf_counter()-t,
              "cpu_s", time.process_time()-cpu, "rss_kib", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


if __name__ == "__main__":
    main()
