import numpy as np
import midas.file_reader
from datetime import datetime
import os
import h5py

# =========================
# INPUT / PATHS
# =========================
run = int(input("run number [int] "))

home = os.path.expanduser("~")
path = home + '/flash-data/data/LNF'
fname = ('/run%05d.mid.gz' % run)
# from optparse import OptionParser
# parser = OptionParser(usage='usage: %prog\t endpont ')
# parser.add_option('-v','--verbose', dest='verbose', action="store_true", default=False, help='verbose output;');
# (options, args) = parser.parse_args()
# verbose = options.verbose


# =========================
# Digitizer / decode params
# =========================
inputRange = 5.0     # [V]
Nch        = 8
fs         = 5e6     # [Hz]
NFFT_CH    = 6       # primi 6 canali
Nsamp_fixed = 655360
Nfreq_fixed = Nsamp_fixed // 2 + 1   # 327681

# =========================
# OUTPUT HDF5
# =========================
out_dir = os.path.join("./", "h5")
os.makedirs(out_dir, exist_ok=True)
h5_name = os.path.join(out_dir, f"run{run:05d}.h5")

# =========================
# Helpers
# =========================
def decode_spec_to_volt(bank_data_uint16: np.ndarray,
                        Nch: int,
                        inputRange: float,
                        fs: float):
    """
    Copia la tua decodifica:
    uint16 -> int16 view -> reshape [Nsamp, Nch] -> volt
    """
    u = np.asarray(bank_data_uint16, dtype=np.uint16)  # 0..65535
    s = u.view(np.int16)                               # -32768..32767
    Nsamp = s.size // Nch
    frames = s[:Nsamp * Nch].reshape(Nsamp, Nch)       # [time, ch]
    volt = frames.astype(np.float64) * (2.0 * inputRange / 65536.0)
    t = np.arange(Nsamp, dtype=np.float64) / fs
    return volt, t, Nsamp

def rfft_mag(x: np.ndarray, fs: float):
    """
    x: waveform 1D
    returns:
      f: frequency axis [Hz]
      mag: |rfft| float32
    """
    x = np.asarray(x, dtype=np.float64)
    x = x - np.mean(x)              # remove DC
    w = np.hanning(x.size)          # Hann window
    xw = x * w

    X = np.fft.rfft(xw)
    mag = np.sqrt(X.real * X.real + X.imag * X.imag).astype(np.float32)
    f = np.fft.rfftfreq(x.size, d=1.0 / fs)
    return f, mag

def append_1d(ds, values):
    """
    Appende un blocco 1D a un dataset HDF5 estendibile.
    """
    values = np.asarray(values)
    old_n = ds.shape[0]
    new_n = old_n + values.shape[0]
    ds.resize((new_n,))
    ds[old_n:new_n] = values

def append_2d(ds, values):
    """
    Appende un blocco 2D a un dataset HDF5 estendibile lungo asse 0.
    values shape = (n_new, ncols)
    """
    values = np.asarray(values)
    old_n = ds.shape[0]
    new_n = old_n + values.shape[0]
    ds.resize((new_n, ds.shape[1]))
    ds[old_n:new_n, :] = values

# =========================
# Open MIDAS
# =========================
mf = midas.file_reader.MidasFile(path + fname)

# ODB info
odb = mf.get_bor_odb_dump().data
try:
    Run_description = odb['Experiment']['Run Parameters']['Run description']
    print('Run_description:', Run_description)
except Exception:
    Run_description = ""
    print('WARNING: no run description')

# =========================
# Batch config
# =========================
# Ogni evento salva ~6 x 327681 float32 = ~7.5 MB solo FFT
# Quindi batch piccolo
BATCH_SIZE = 5

# =========================
# Buffers
# =========================
buf_event = []
buf_event_id = []
buf_timestamp = []
buf_has_spec = []
buf_spec_nsamp = []
buf_spec_fs = []

# 6 canali FFT separati
buf_fft = [[] for _ in range(NFFT_CH)]   # buf_fft[0] ... buf_fft[5]

if os.path.exists(h5_name):
    os.remove(h5_name)

# =========================
# Create HDF5 file + datasets
# =========================
with h5py.File(h5_name, "w") as h5f:
    # ---- file attributes / metadata
    h5f.attrs["run"] = run
    h5f.attrs["inputRange_V"] = inputRange
    h5f.attrs["Nch_total"] = Nch
    h5f.attrs["NFFT_CH"] = NFFT_CH
    h5f.attrs["fs_Hz"] = fs
    h5f.attrs["Nsamp_fixed"] = Nsamp_fixed
    h5f.attrs["Nfreq_fixed"] = Nfreq_fixed
    h5f.attrs["Run_description"] = Run_description

    # opzionale: salva asse frequenze una volta sola
    freq_axis = np.fft.rfftfreq(Nsamp_fixed, d=1.0 / fs).astype(np.float64)
    h5f.create_dataset("spec/freq_axis",
                       data=freq_axis,
                       compression="gzip",
                       compression_opts=4)

    # ---- gruppi
    g_events = h5f.require_group("events")
    g_spec = h5f.require_group("spec")

    # chunking: un chunk = un evento
    chunk_rows = 1

    # ---- datasets estendibili 1D
    ds_event = g_events.create_dataset(
        "event",
        shape=(0,), maxshape=(None,), dtype=np.int32,
        chunks=(max(chunk_rows, 1),),
        compression="gzip", compression_opts=4
    )
    ds_event_id = g_events.create_dataset(
        "event_id",
        shape=(0,), maxshape=(None,), dtype=np.int32,
        chunks=(max(chunk_rows, 1),),
        compression="gzip", compression_opts=4
    )
    ds_timestamp = g_events.create_dataset(
        "timestamp",
        shape=(0,), maxshape=(None,), dtype=np.int64,
        chunks=(max(chunk_rows, 1),),
        compression="gzip", compression_opts=4
    )
    ds_has_spec = g_events.create_dataset(
        "has_SPEC",
        shape=(0,), maxshape=(None,), dtype=np.int8,
        chunks=(max(chunk_rows, 1),),
        compression="gzip", compression_opts=4
    )
    ds_spec_nsamp = g_spec.create_dataset(
        "nsamp",
        shape=(0,), maxshape=(None,), dtype=np.int32,
        chunks=(max(chunk_rows, 1),),
        compression="gzip", compression_opts=4
    )
    ds_spec_fs = g_spec.create_dataset(
        "fs",
        shape=(0,), maxshape=(None,), dtype=np.float64,
        chunks=(max(chunk_rows, 1),),
        compression="gzip", compression_opts=4
    )

    # ---- datasets FFT 2D: (Nevents, Nfreq_fixed)
    ds_fft = []
    for ch in range(NFFT_CH):
        ds = g_spec.create_dataset(
            f"fft_ch{ch}",
            shape=(0, Nfreq_fixed),
            maxshape=(None, Nfreq_fixed),
            dtype=np.float32,
            chunks=(chunk_rows, Nfreq_fixed),
            compression="gzip",
            compression_opts=4
        )
        ds_fft.append(ds)

    def flush():
        if len(buf_event) == 0:
            return

        append_1d(ds_event, buf_event)
        append_1d(ds_event_id, buf_event_id)
        append_1d(ds_timestamp, buf_timestamp)
        append_1d(ds_has_spec, buf_has_spec)
        append_1d(ds_spec_nsamp, buf_spec_nsamp)
        append_1d(ds_spec_fs, buf_spec_fs)

        for ch in range(NFFT_CH):
            block = np.stack(buf_fft[ch], axis=0).astype(np.float32)  # (nev_batch, Nfreq_fixed)
            append_2d(ds_fft[ch], block)

        buf_event.clear()
        buf_event_id.clear()
        buf_timestamp.clear()
        buf_has_spec.clear()
        buf_spec_nsamp.clear()
        buf_spec_fs.clear()
        for ch in range(NFFT_CH):
            buf_fft[ch].clear()

    # =========================
    # Main loop events
    # =========================
    for event in mf:
        if event.header.is_midas_internal_event():
            continue

        event_number = int(event.header.serial_number)
        event_id = int(event.header.event_id)
        ts = int(event.header.timestamp)

        # default per evento
        has_spec = 0
        nsamp = -1
        spec_fs = float(fs)
        fft_default = np.full((Nfreq_fixed,), np.nan, dtype=np.float32)
        fft_ch = [fft_default.copy() for _ in range(NFFT_CH)]

        if event_number % 100 == 0:
            bank_names = ", ".join(b.name for b in event.banks.values())
            print(f"Event # {event_number} ID {event_id} banks: {bank_names}")
            print("UTC time:", datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S'))

        # ---- SPEC
        if "SPEC" in event.banks:
            has_spec = 1
            volt, t, nsamp = decode_spec_to_volt(
                event.banks["SPEC"].data,
                Nch=Nch,
                inputRange=inputRange,
                fs=fs
            )

            if nsamp != Nsamp_fixed:
                print(f"WARNING: event {event_number}: nsamp={nsamp} != {Nsamp_fixed}. SPEC marked invalid.")
                has_spec = 0
                nsamp = -1
            else:
                for ch in range(NFFT_CH):
                    _, mag = rfft_mag(volt[:, ch], fs)
                    fft_ch[ch] = mag.astype(np.float32)



        # ---- QUI puoi aggiungere altre bank in futuro
        # if "MERC" in event.banks:
        #     ...
        # if "XXXX" in event.banks:
        #     ...

        # ---- append UNA VOLTA per evento
        buf_event.append(event_number)
        buf_event_id.append(event_id)
        buf_timestamp.append(ts)
        buf_has_spec.append(has_spec)
        buf_spec_nsamp.append(int(nsamp))
        buf_spec_fs.append(float(spec_fs))
        for ch in range(NFFT_CH):
            buf_fft[ch].append(fft_ch[ch])

        if len(buf_event) >= BATCH_SIZE:
            flush()
                        # debug
        if event_number % 50 == 0:
            print("-----------------------")
            print(ts, event_number, "data:", event.banks["SPEC"].data[:10])
            print("> ch0, first 5 sample >", volt[:5, 0])
            # se vuoi interrompere in debug, decommenta:
            # debug_break = True

    # flush finale
    flush()

print("DONE ->", h5_name)