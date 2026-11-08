"""Self-contained per-run noise products; legacy NPZ/JSON readers remain supported."""
import json
from contextlib import contextmanager
from collections.abc import Mapping
import numpy as np

MODES = ("TM010", "TM011", "TM012")

def build_results(summary, arrays, filtered_bands=None):
    """Dizionario unico; separa metadati, array comuni e array dei modi."""
    common, modes = {}, {mode: {} for mode in MODES}
    for key, value in arrays.items():
        mode = next((m for m in MODES if key.startswith(m + "_")), None)
        if mode is None:
            common[key] = value
        else:
            modes[mode][key[len(mode) + 1:]] = value
    return {"schema_version": 1, "summary": summary, "arrays": common,
            "modes": modes, "filtered_bands": filtered_bands or {}}


def save_results_h5(path, results):
    """Dizionari -> gruppi, array -> dataset; liste di record -> JSON UTF-8."""
    import h5py
    def write(group, values):
        for key, value in values.items():
            if isinstance(value, dict):
                write(group.create_group(key), value)
            elif value is None or (isinstance(value, list) and
                                   any(isinstance(v, (dict, list)) for v in value)):
                dataset = group.create_dataset(key, data=json.dumps(value),
                                               dtype=h5py.string_dtype("utf-8"))
                dataset.attrs["encoding"] = "json"
            elif isinstance(value, str):
                group.create_dataset(key, data=value, dtype=h5py.string_dtype("utf-8"))
            else:
                array = np.asarray(value)
                if array.dtype.kind == "U":
                    array = array.astype(h5py.string_dtype("utf-8"))
                options = {"compression": "gzip", "shuffle": True} if array.ndim and array.size else {}
                group.create_dataset(key, data=array, **options)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with h5py.File(temporary, "w") as output:
            write(output, results)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def read_results_h5(path):
    import h5py
    def read(node, lists=False):
        if isinstance(node, h5py.Group):
            return {key: read(value, lists) for key, value in node.items()}
        if node.attrs.get("encoding") == "json":
            return json.loads(node.asstr()[()])
        value = node.asstr()[()] if h5py.check_string_dtype(node.dtype) else node[()]
        if isinstance(value, np.ndarray) and lists:
            return value.tolist()
        return value.item() if isinstance(value, np.generic) else value
    with h5py.File(path, "r") as source:
        if source["schema_version"][()] != 1:
            raise ValueError("Unsupported noise HDF5 schema: " + str(path))
        result = {key: read(value, key == "summary") for key, value in source.items()}
    return result


def flattened_arrays(results):
    arrays = dict(results["arrays"])
    for mode, values in results["modes"].items():
        arrays.update({mode + "_" + key: value for key, value in values.items()})
    return arrays


def read_summary(path):
    if path.suffix == ".h5":
        # Only metadata are needed here, not all scientific arrays or figures.
        import h5py
        with h5py.File(path, "r") as source:
            if source["schema_version"][()] != 1:
                raise ValueError("Unsupported noise HDF5 schema")
            def native(node):
                if isinstance(node, h5py.Group):
                    return {key: native(value) for key, value in node.items()}
                if node.attrs.get("encoding") == "json":
                    return json.loads(node.asstr()[()])
                value = node.asstr()[()] if h5py.check_string_dtype(node.dtype) else node[()]
                return value.tolist() if isinstance(value, np.ndarray) else value.item() if isinstance(value, np.generic) else value
            return native(source["summary"])
    return json.loads(path.read_text())


class H5NoiseArrays(Mapping):
    """Flat historical array names, loaded on demand from an open HDF5 file."""
    def __init__(self, source):
        self.datasets = dict(source['arrays'].items())
        for mode, values in source['modes'].items():
            self.datasets.update({mode + '_' + key: value for key, value in values.items()})

    def __getitem__(self, key):
        return self.datasets[key][()]

    def __iter__(self):
        return iter(self.datasets)

    def __len__(self):
        return len(self.datasets)


@contextmanager
def open_noise_arrays(path):
    if path.suffix == ".h5":
        import h5py
        with h5py.File(path, "r") as source:
            yield H5NoiseArrays(source)
    else:
        with np.load(path.with_suffix(".npz"), allow_pickle=False) as source:
            yield source
