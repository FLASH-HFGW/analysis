"""Band-power preview from existing full-run spectra, with no waveform reconstruction."""
from pathlib import Path
import argparse,json
import numpy as np
from scipy.signal import firwin
from iq_acquisition_metadata import read_bor_coordinates,resonance_centers,MODES

def preview(raw,fftfile,old_h5):
    import h5py
    m=read_bor_coordinates(raw);centers=resonance_centers(m);fs=m['fs_hz'];h=firwin(2001,25000,fs=fs,window=('kaiser',8.6));result={}
    with np.load(fftfile) as a,h5py.File(old_h5,'r') as old:
        for mi,mode in enumerate(MODES):
            spec=a[f'fft_amp_mode{mi}_SPECs'].astype(float);n=len(spec);f=np.fft.fftshift(np.fft.fftfreq(n,1/fs));w=np.hanning(n);enbw_hz=fs*np.sum(w*w)/sum(w)**2
            # Archived reconstruction used ±5V. Convert to measured BOR range exactly once.
            corr=(m['modes'][mode]['ADC_peak_V']/5)**2;psd=spec*corr/enbw_hz;df=fs/n
            powers=[]
            for center in centers[mode]:
                response=np.fft.fftshift(np.fft.fft(h*np.exp(2j*np.pi*center*np.arange(len(h))/fs),n));powers.append(float(np.sum(psd*abs(response)**2)*df))
            response=np.fft.fftshift(np.fft.fft(h*np.exp(2j*np.pi*1e6*np.arange(len(h))/fs),n));control=float(np.sum(psd*abs(response)**2)*df)
            measured=float(old[f'filtered_bands/modes/{mode}/band_08/complex_moments/total_squared_v2'][()])*corr
            result[mode]={'centers_hz':centers[mode],'predicted_band_power_V2':powers,'predicted_band_RMS_V':np.sqrt(powers).tolist(),'PSD_integrated_total_RMS_V':float(np.sqrt(np.sum(psd)*df)),'control_1MHz_PSD_power_V2':control,'control_1MHz_existing_v2_power_V2':measured,'control_1MHz_power_relative_difference':control/measured-1,'actual_fft_samples':n,'df_hz':df,'Hann_ENBW_hz':float(enbw_hz)}
    return {'source':str(fftfile),'duration_s':209.7152,'scope':'Existing full-run averaged chunk PSD; filter-weighted expected powers, not reconstructed filtered-IQ distributions/correlations. Chunk means removed in archive; not same as v2 run-mean subtraction.','normalization':'two-sided PSD; actual16383sample FFT grid, not stale16384 descriptor; Hann coherent-power archive converted by ENBW Hz; physical BOR ADC scale once','metadata':m,'modes':result}

def main():
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--fft',type=Path,required=True);p.add_argument('--old-h5',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    r=preview(a.raw,a.fft,a.old_h5);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r['modes'],indent=2))
if __name__=='__main__':main()
