"""Preserve asynchronous MIDAS thermometer readings using the validated schema."""
import json

import numpy as np

from extract_thermometers import LAYOUTS, channel_schema, equipment_map

HEADER = np.dtype([("time_unix", "<i8"), ("event_id", "<i4"), ("serial", "<i8")])


class Thermometers:
    def __init__(self, odb):
        self.mapping = equipment_map(odb)
        self.schemas = {}
        self.bad = 0

    def observe(self, event):
        if "INPT" not in event.banks:
            return
        header = event.header
        identifier = int(header.event_id)
        info = self.mapping.get(identifier, {})
        equipment = info.get("equipment", f"event_{identifier}")
        values = np.asarray(event.banks["INPT"].data)
        if values.ndim != 1 or values.dtype.kind not in "iuf" or not values.size:
            self.bad += 1
            return
        key = identifier, len(values), values.dtype.str
        if key not in self.schemas:
            schema, document = channel_schema(equipment, identifier, len(values), info)
            self.schemas[key] = schema, document, [], []
        _, _, headers, rows = self.schemas[key]
        headers.append((header.timestamp, identifier, header.serial_number))
        rows.append(values.copy())

    def write(self, output, *, complete, provenance):
        group = output.create_group("thermometers")
        documents = [json.loads(entry[1]) for entry in self.schemas.values()]
        families = {doc["equipment"].casefold() for doc in documents
                    if doc["documented_layout_length_matches"]}
        missing = sorted(set(LAYOUTS) - families)
        group.attrs.update(schema_version="1.0", provenance=provenance,
                           complete=bool(complete and not self.bad and not missing),
                           scan_reached_eor=bool(complete), malformed_banks=self.bad,
                           missing_families_json=json.dumps(missing),
                           readings=sum(len(entry[2]) for entry in self.schemas.values()))
        for (_, _, dtype), (schema, document, headers, values) in self.schemas.items():
            item = group.create_group(f"{schema}_{np.dtype(dtype).name}")
            item.attrs.update(schema_id=schema, channels_json=document, bank="INPT")
            item.create_dataset("events", data=np.asarray(headers, dtype=HEADER))
            item.create_dataset("values", data=np.stack(values))
        return group
