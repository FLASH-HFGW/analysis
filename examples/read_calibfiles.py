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

parser.add_argument("--run", required=True, default=0,
                    help="Run number")
args = parser.parse_args()

path = os.path.expanduser(args.path)
outdir = args.out_dir

run = int(args.run)
fft_amp_mode0_SPECs_fin = None
fft_amp_mode1_SPECs_fin = None
fft_amp_mode2_SPECs_fin = None
fft_freq_mode0 = None
fft_freq_mode1 = None
fft_freq_mode2 = None


file_npz = path+"/run%05d_calib.npz"%(run)  

# Apertura del file
data = np.load(file_npz, allow_pickle=True)
tot_evt_num = data["n_fft_done"].item()
print(tot_evt_num)
#################debug
#tot_evt_num = 1

#Syntax is data[name of the saved variable][event_id][amp for V^2 or fs meta for metadata frequency]
#if fs_meta then the last bracket is [first frequency, last frequency, length of the array]

for event in range(0,tot_evt_num):
    dictiona_data0=data["fft_amp_mode0_SPECs"].item()
    dictiona_data1=data["fft_amp_mode1_SPECs"].item()
    dictiona_data2=data["fft_amp_mode2_SPECs"].item()
    #print(event, dictiona_data1[0])


    fft_amp_mode0_SPECs_fin = dictiona_data0[event]["amp"]
    fft_freq_mode0 = np.linspace(dictiona_data0[event]["fs_meta"][0],dictiona_data0[event]["fs_meta"][1],dictiona_data0[event]["fs_meta"][2]-1)


    fft_amp_mode1_SPECs_fin = dictiona_data1[event]["amp"]
    fft_freq_mode1 = np.linspace(dictiona_data1[event]["fs_meta"][0],dictiona_data1[event]["fs_meta"][1],dictiona_data1[event]["fs_meta"][2]-1)


    fft_amp_mode2_SPECs_fin = dictiona_data2[event]["amp"]
    fft_freq_mode2 = np.linspace(dictiona_data2[event]["fs_meta"][0],dictiona_data2[event]["fs_meta"][1],dictiona_data2[event]["fs_meta"][2]-1)

#Plottamiz
plt.plot(fft_freq_mode0, fft_amp_mode0_SPECs_fin)
plt.show()


print("DONE")