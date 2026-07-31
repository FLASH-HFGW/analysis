import numpy as np
import os
import argparse
import matplotlib.pyplot as plt
# matplotlib.use("Agg")
import gc


# ------------------------------------------------------------
# Parametri da riga di comando
# ------------------------------------------------------------
parser = argparse.ArgumentParser(
    description="Legge un file MIDAS e calcola solo FFT complessa I/Q dei modi TM."
)

parser.add_argument("--path", required=True,
                    help="Directory contenente i file npz, es: ~/flash-data/analysis/users/dho/")

parser.add_argument("--out-dir", default="./",
                    help="Directory dove salvare le FFT")

parser.add_argument(
        "--range",
        dest="run_range",
        nargs=2,
        metavar=("START", "END"),
        help=(
            "Intervallo inclusivo di run. "
            "Esempio: --range 590 600"
        ))
args = parser.parse_args()

path = os.path.expanduser(args.path)
outdir = args.out_dir

run_list=args.run_range
print(run_list)
fft_amp_mode0_SPECs_fin = None
fft_amp_mode1_SPECs_fin = None
fft_amp_mode2_SPECs_fin = None
fft_freq_mode0 = None
fft_freq_mode1 = None
fft_freq_mode2 = None

for run in run_list:
    file_npz = path+"/run%05d.npz"%(run)  

    # Apertura del file
    data = np.load(file_npz)
    if fft_amp_mode0_SPECs_fin is None:
        fft_amp_mode0_SPECs_fin = data["fft_amp_mode0_SPECs"]
        fft_freq_mode0 = data["fft_freq_mode0"]
    else:
        fft_amp_mode0_SPECs_fin += data["fft_amp_mode0_SPECs"]
        
    if fft_amp_mode1_SPECs_fin is None:
        fft_amp_mode1_SPECs_fin = data["fft_amp_mode1_SPECs"]
        fft_freq_mode1 = data["fft_freq_mode1"]
    else:
        fft_amp_mode1_SPECs_fin += data["fft_amp_mode1_SPECs"]
    
    if fft_amp_mode2_SPECs_fin is None:
        fft_amp_mode2_SPECs_fin = data["fft_amp_mode2_SPECs"]
        fft_freq_mode2 = data["fft_freq_mode0"]
    else:
        fft_amp_mode2_SPECs_fin += data["fft_amp_mode2_SPECs"]

run_tot=len(run_list)
fft_amp_mode0_SPECs_fin/=run_tot
fft_amp_mode1_SPECs_fin/=run_tot
fft_amp_mode2_SPECs_fin/=run_tot

out_npz=os.path.join(
    outdir,
    "run%05d-%05d_power.npz"
    % (run_list[0], run_list[-1])
)
np.savez_compressed(out_npz,
    fft_amp_mode0_SPECs=fft_amp_mode0_SPECs_fin,
    fft_freq_mode0=fft_freq_mode0,
    fft_amp_mode1_SPECs=fft_amp_mode1_SPECs_fin,
    fft_freq_mode1=fft_freq_mode1,
    fft_amp_mode2_SPECs=fft_amp_mode2_SPECs_fin,
    fft_freq_mode2=fft_freq_mode2,
)

print("DONE")