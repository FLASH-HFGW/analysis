"""Recover calibration sweeps from ODB and archived spectra; no fitted gain correction."""
from pathlib import Path
import sys,json,csv,hashlib,concurrent.futures
sys.path.insert(0,'/cvmfs/sft-flash.infn.it/package/midas/python')
import midas.file_reader
import numpy as np
from scipy.interpolate import interp1d
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path('/home/mazzitel/flash-data');RAW=ROOT/'data/LNF';FFT=ROOT/'analysis/autoreco/Run2/fft_by_run'
OUT=Path('/home/mazzitel/HFGW/analysis-work/Run2/diagnostics/normalization_audit_20261114');OUT.mkdir(parents=True,exist_ok=True)
MODES=['TM010','TM011','TM012'];N=16384;actualN=N-1;fs=5e6;df=fs/actualN;freq=np.fft.fftshift(np.fft.fftfreq(actualN,1/fs));rows=[]
def read(run):
 p=RAW/f'run{run:05d}.mid.gz';npz=FFT/f'run{run:05d}.npz'
 if not p.exists() or not npz.exists():return None
 f=midas.file_reader.MidasFile(str(p),use_numpy=True);odb=f.get_bor_odb_dump().data;e=odb['Equipment'];lo=e['LocalOscill']['Variables'];nb=e['NetBox']['Settings']
 with np.load(npz,allow_pickle=False) as a:
  peaks=[float(np.max(a[f'fft_amp_mode{i}_SPECs'])) for i in range(3)];mode=int(np.argmax(peaks));spect=a[f'fft_amp_mode{mode}_SPECs'];idx=int(np.argmax(spect));nf=int(a['n_fft_done'])
 window=np.hanning(actualN);enbw=actualN*np.sum(window**2)/np.sum(window)**2
 # Integrate the tone and subtract local broadband background, avoiding peak scalloping.
 inds=(np.arange(idx-12,idx+13)%len(spect));baseline=float(np.median(spect))
 tone_integral=float(np.sum(spect[inds]-baseline)/enbw)
 power=float(lo['power Pump']);rf=float(lo['freq Pump']);vrf2=50*1e-3*10**(power/10)
 return dict(run=run,mode=MODES[mode],rf_tone_hz=rf,generator_power_dbm=power,rs_hz=float(lo['freq RS']),teled1_hz=float(lo['freq Teled Ch1']),teled2_hz=float(lo['freq Teled Ch2']),peak_if_hz=float(freq[idx]),peak_v2=peaks[mode],kz_peak_from_archived_spectrum=float(np.sqrt(peaks[mode]/vrf2)),kz_integrated_tone=float(np.sqrt(max(tone_integral,0)/vrf2)),adc_range_mV=nb['Channel_range_mV'],n_events=nf,raw_path=str(p),fft_path=str(npz))
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
 for item in pool.map(read,range(406,591)):
  if item is not None:rows.append(item)
# Metadata, not descriptions, defines tone frequencies. Reject startup configurations.
valid=[r for r in rows if r['generator_power_dbm']==-60 and 8.72e9<r['rf_tone_hz']<8.85e9 and r['adc_range_mV'][:6]==[5000]*6]
# Deduplicate repeated frequencies, using median of repeated observations. Keep source runs.
curves={}
for mode in MODES:
 candidates=[r for r in valid if r['mode']==mode];grid=[]
 for rf in sorted({r['rf_tone_hz'] for r in candidates}):
  same=[r for r in candidates if r['rf_tone_hz']==rf];grid.append(dict(rf_hz=rf,if_hz=float(np.median([r['peak_if_hz'] for r in same])),kz=float(np.median([r['kz_peak_from_archived_spectrum'] for r in same])),kz_integrated=float(np.median([r['kz_integrated_tone'] for r in same])),runs=[r['run'] for r in same]))
 curves[mode]=grid
# The empirical IF-to-RF mapping is derived from each tone, not assumed at 1 MHz.
# The user confirmed that the frontend applied the saved ADC ranges.
mf=midas.file_reader.MidasFile(str(RAW/'run00680.mid.gz'),use_numpy=True)
science_ranges=mf.get_bor_odb_dump().data['Equipment']['NetBox']['Settings']['Channel_range_mV']
assert science_ranges[:6]==[2000]*6
summary={};fig,axs=plt.subplots(2,3,figsize=(15,8))
rfcenter={'TM010':8.737119e9,'TM011':8.780840e9,'TM012':8.841182e9}
with np.load(FFT/'run00680.npz') as run680:
 for i,mode in enumerate(MODES):
  grid=curves[mode];ff=np.array([r['if_hz'] for r in grid]);kk=np.array([r['kz'] for r in grid]);rf=np.array([r['rf_hz'] for r in grid])
  # ±3 MHz calibration tones alias outside ±2.5 MHz. Only unaliased central points can define interpolation.
  # Fit RF-vs-IF slope on the central tone sequence, retaining the largest connected linear branch.
  ordered=sorted(grid,key=lambda r:r['rf_hz']);groups=[];current=[]
  for r in ordered:
   if current and abs(r['if_hz']-current[-1]['if_hz'])>5e5:groups.append(current);current=[]
   current.append(r)
  if current:groups.append(current)
  central=max(groups,key=len);xf=np.array([r['if_hz'] for r in central]);yr=np.array([r['rf_hz'] for r in central]);slope,offset=np.polyfit(xf,yr,1)
  residual=float(np.max(abs(yr-(slope*xf+offset))))
  assert abs(abs(slope)-1)<.005
  assert residual<2000
  use=np.array([abs(r['rf_hz']-offset)<2.45e6 for r in ordered]);central=[r for r,u in zip(ordered,use) if u]
  xx=np.array([r['if_hz'] for r in central]);yy=np.array([r['kz'] for r in central]);order=np.argsort(xx);xx=xx[order];yy=yy[order]
  # Stored spectra use Hann coherent-amplitude normalization: dividing by ENBW gives noise power/bin.
  window=np.hanning(actualN);enbw_bins=actualN*np.sum(window**2)/np.sum(window)**2
  fdata=freq
  # The archived FFT was produced using fixed ±5 V. Correct its squared amplitude.
  science_scale=float(science_ranges[2*i])/5000
  assert science_ranges[2*i]==science_ranges[2*i+1]
  spec=run680[f'fft_amp_mode{i}_SPECs'].astype(float)*science_scale**2
  kval=np.interp(fdata,xx,yy,left=np.nan,right=np.nan)
  calibrated_archived=spec/(50*10**(103.4/10)*kval**2)
  calibrated_noise=calibrated_archived/enbw_bins
  # A changed science-run LO shifts resonance IF; archived IQ sign is +. Use both signed plateaus and central band.
  mask=(abs(fdata)>0.5e6)&(abs(fdata)<1.5e6)&np.isfinite(calibrated_noise)
  v=float(np.median(calibrated_noise[mask]));from scipy import constants
  target=constants.k*3.985*df
  integrated=np.array([r['kz_integrated'] for r in central])[order]
  kval_integrated=np.interp(fdata,xx,integrated,left=np.nan,right=np.nan)
  noise_integrated=spec/(50*10**(103.4/10)*kval_integrated**2)/enbw_bins
  integrated_power=float(np.median(noise_integrated[mask]))
  without_extra36=integrated_power*10**(36/10)
  summary[mode]=dict(science_adc_range_mV=science_ranges[2*i],archived_amplitude_correction=science_scale,archived_power_correction=science_scale**2,median_power_using_integrated_tone_kz_w_bin=integrated_power,noise_temperature_if_RF_gain103_4_k=integrated_power/(1.380649e-23*df),noise_temperature_if_RF_gain67_4_k=without_extra36/(1.380649e-23*df),without_extra36_status='Diagnostic alternative reference plane only: assumes the additional 36 dB stage is already included in kz. Not confirmed, not applied to scientific products.',n_unique_frequencies=len(grid),source_runs=[r['run'] for r in candidates] if False else sorted({n for r in grid for n in r['runs']}),rf_if_slope=float(slope),rf_if_offset_hz=float(offset),rf_if_max_residual_hz=residual,kz_plateau_median=float(np.median(yy[abs(xx)<1.5e6])),hann_enbw_bins=float(enbw_bins),median_power_w_bin_with_thesis_RF_gain_and_reconstructed_kz=v,thesis_kBT_power_w_bin=float(target),thesis_over_reconstruction=float(target/v),scope='Full-run archived run680; diagnostic interpolation of peak-based calibration, within central calibration band. Historical Hann normalization explicitly removed for noise.',calibration='Provisional: generator -60 dBm at recorded source, unknown losses/reference plane; science ADC ODB range differs; no scalar correction fitted.')
  axs[0,i].plot((rf-rf.mean())/1e6,kk,'.-',lw=.7);axs[0,i].set(title=mode+' calibration from recorded tone',xlabel='Tone offset from sweep center [MHz]',ylabel='kz (amplitude)')
  axs[1,i].plot(fdata/1e6,calibrated_noise,color='#007F86',lw=.7);axs[1,i].axhline(target,color='#D98726',ls='--',label='Thesis kBT Δf');axs[1,i].set_yscale('log');axs[1,i].set(xlabel='Complex IF [MHz]',ylabel='Noise power / FFT bin [W]',title=mode+' provisional calibration');axs[1,i].legend(fontsize=8)
  np.savez(OUT/f'{mode}_reconstructed_calibration.npz',tone_rf_hz=rf,tone_if_hz=ff,kz_peak=kk,run680_if_hz=fdata,run680_calibrated_noise_w_bin=calibrated_noise)
fig.tight_layout();fig.savefig(OUT/'calibration_reconstruction.png',dpi=180);plt.close(fig)
report=dict(raw_directory=str(RAW),fft_directory=str(FFT),calibration_ADC_scale_volts_per_count=float(np.float32(10/65535)),science_ADC_scale_volts_per_count=float(np.float32(4/65535)),science_range_source='BOR ODB; frontend application confirmed by user',sweep_observations=rows,curves=curves,comparison=summary,limitations=['VNA S-parameter files are separate from DAQ conversion-tone calibration.','The historical FFT drops the last sample of each 16384-sample chunk (actual FFT length 16383) while saving a 16384-point frequency descriptor.','Hann coherent gain normalization gives ENBW≈1.5 bins for broadband noise.','Peak-only tone calibration has scalloping/leakage dependence; exact calibration should fit/integrate the tone and separate coherent gain from noise bandwidth.','ADC ODB ranges differ: calibration ±5 V, run680 IQ ±2 V. Frontend application confirmed by user; archived run680 V² corrected by (2/5)².','Original 143 dB input-equivalent quantities and fixed-±5 V science ADC quantities require revision. Generator setting alone does not establish incident power at the calibration reference plane.','No gain rescaling or arbitrary factor1000 applied.'])
(OUT/'calibration_reconstruction.json').write_text(json.dumps(report,indent=2));print(json.dumps(summary,indent=2))
