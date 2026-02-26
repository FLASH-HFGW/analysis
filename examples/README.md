# MIDAS File Reader Example (Python)

## Overview

This script demonstrates how to:

- Open a compressed MIDAS file (`.mid.gz`)
- Retrieve the Begin-of-Run (BOR) ODB snapshot
- Loop over events
- Inspect and decode MIDAS banks
- Decode waveform data from a `SPEC` bank (digitizer example)

---

## MIDAS Concepts

### ODB (Online DataBase)

At the beginning of a run, MIDAS can store a snapshot of the ODB inside the data file (BOR event).

odb = mf.get_bor_odb_dump().data

odb is a nested Python dictionary containing the experiment configuration at run start.

Example: odb['Experiment']['Run Parameters']['Run description'] 

This allows associating raw data with the run configuration used during acquisition.

### MIDAS Banks
Each MIDAS event may contain multiple banks.

A bank:
- Has a name (e.g. SPEC, MERC, ...)
- Contains raw binary data
- Represents data from a specific subsystem (digitizer, scaler, trigger, etc.)

#### Script Workflow
- Ask for a run number
- Open runXXXXX.mid.gz
- Read BOR ODB and print the run description (if available)
- Loop over events:
-   Skip internal MIDAS events
-   Periodically print event information
-   If a SPEC bank is present:
-     Interpret data as int16
-     Reshape into [Nsamples, Nchannels]
-     Convert ADC counts to Volts
-     Build time axis from sampling frequency
-     Print debug samples periodically

- Extending to Other Banks

### Requirements
- Python 3
- numpy
- midas Python bindings
