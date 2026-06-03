import numpy as np
import midas.file_reader
from datetime import datetime
import os
import argparse

# ------------------------------------------------------------
# Parametri da riga di comando
# ------------------------------------------------------------
parser = argparse.ArgumentParser(description="Legge un file MIDAS e stampa gli equipment/bank incontrati.")
parser.add_argument("--path", required=True, help="Directory contenente i file MIDAS, es: ~/flash-data/QUAX/TEST")
parser.add_argument("--run", required=True, type=int, help="Numero run, es: 123")
args = parser.parse_args()

run = args.run
path = os.path.expanduser(args.path)

fname = "run%05d.mid.gz" % run
full_name = os.path.join(path, fname)

print("Reading:", full_name)

mf = midas.file_reader.MidasFile(full_name)

# ------------------------------------------------------------
# Leggi ODB BOR e ricostruisci Event ID -> Equipment name
# ------------------------------------------------------------
equipment_by_event_id = {}

try:
    odb = mf.get_bor_odb_dump().data

    try:
        Run_description = odb["Experiment"]["Run Parameters"]["Run description"]
        print("Run_description:", Run_description)
    except Exception:
        print("WARNING: no run description")

    try:
        equipments = odb["Equipment"]

        for eq_name, eq_data in equipments.items():
            try:
                event_id = eq_data["Common"]["Event ID"]
                equipment_by_event_id[int(event_id)] = eq_name
                print("Found equipment:", eq_name, "Event ID:", event_id)
            except Exception:
                pass

    except Exception:
        print("WARNING: no Equipment section in ODB")

except Exception:
    print("WARNING: no BOR ODB dump found")
    odb = None


# ------------------------------------------------------------
# Loop eventi
# ------------------------------------------------------------
seen_equipments = set()

for event in mf:

    if event.header.is_midas_internal_event():
        print("Saw a special event")
        continue

    event_id = event.header.event_id
    equipment_name = equipment_by_event_id.get(event_id, "UNKNOWN")

    bank_names = ", ".join(b.name for b in event.banks.values())
    event_number = event.header.serial_number
    event_timestamp = event.header.timestamp
    event_time = datetime.fromtimestamp(event_timestamp).strftime("%Y-%m-%d %H:%M:%S")

    # Stampa quando incontra un equipment nuovo
    if equipment_name not in seen_equipments:
        seen_equipments.add(equipment_name)

        print("----------------------------------------")
        print("New equipment found")
        print("Equipment:", equipment_name)
        print("Event ID:", event_id)
        print("Event number:", event_number)
        print("Timestamp:", event_time)
        print("Banks:", bank_names)
        print("----------------------------------------")

    # Debug periodico
    if event_number % 1000 == 0:
        print("Event # %s of type ID %s, equipment %s, contains banks %s" %
              (event_number, event_id, equipment_name, bank_names))

        print("Received event with timestamp %s containing banks %s" %
              (event_timestamp, bank_names))

        print("Event # %s at %s, banks %s" %
              (event_number,
               datetime.utcfromtimestamp(event_timestamp).strftime("%Y-%m-%d %H:%M:%S"),
               bank_names))

    # Stampa i bank name dell'evento
    for bank_name, bank in event.banks.items():
        print(bank_name)

#         if "SPEC" in bank_name:
#             ########################### put your code ##################################
#             # example decode Spectrum digitizer
#             # ------------
#             inputRange = 5
#             Nch = 8
#             fs = 5e6
#             # ------------
#             u = np.asarray(event.banks["SPEC"].data, dtype=np.uint16)  # 0..65535
#             s = u.view(np.int16)                                       # -32768..32767
#             Nsamp = s.size // Nch
#             frames = s[:Nsamp * Nch].reshape(Nsamp, Nch)  # [time, ch]
#             volt = frames.astype(np.float64) * (2.0 * inputRange / 65536.0)
#             t = np.arange(Nsamp) / fs  # [s]
#
#             if event_number % 100 == 0:
#                 print("-----------------------")
#                 print(event.header.timestamp, event_number, "data:", event.banks["SPEC"].data[:10])
#                 print("> ch0, first 5 sample >", volt[:5, 0])
#
#             #############################################################################

print("DONE")
