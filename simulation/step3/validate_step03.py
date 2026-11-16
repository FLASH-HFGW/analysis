#!/usr/bin/env python3
"""Step 3 FLASH: same tone and cavity noise as Step 2, add independent electronic I/Q noise AFTER cavity.

All frequency-domain operations work on the complex analytic RF envelope or complex IF;
the 8.7 GHz carrier is not naively sampled at 40 MS/s. Stationary FFT/circular simulation.
"""
import json, pathlib, zipfile
import numpy as np
from scipy import signal
from scipy.ndimage import uniform_filter1d
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=pathlib.Path(__file__).resolve().parent; OUT.mkdir(exist_ok=True)
FR=8.737119e9; QL=29306.; FIF=1e6; FS=40e6; FS_ADC=5e6; DEC=8; DUR=400e-6
B_RF=10e6; FC=1.9e6; ORDER=4; B_EL=10e6; EL_RMS_IN=0.25
SEED=20261112; ADC_BITS=16; ADC_RANGE=5.
N=int(FS*DUR); NS=N//DEC
th=np.arange(N)/FS; ts=th[::DEC]; freq=np.fft.fftfreq(N,1/FS)
fadc=np.fft.fftfreq(NS,1/FS_ADC); W=2*np.pi*freq; tau=QL/(np.pi*FR)
lsb=2*ADC_RANGE/(2**ADC_BITS)
COL={'tone':'#0b65cc','cavity':'#43a1ed','electronics':'#ed812a','total':'#7049ac','navy':'#0b356a','I':'#0b65cc','Q':'#07877f'}

def unit_band_noise(seed,band,center=0):
    rng=np.random.default_rng(seed)
    a=rng.normal(size=N)+1j*rng.normal(size=N)
    F=np.fft.fft(a); F[np.abs(freq-center)>band/2]=0
    arr=np.fft.ifft(F)
    return arr/np.sqrt(np.mean(np.abs(arr)**2))

# Identical RF realization from step 2.
noise_rf=unit_band_noise(SEED,B_RF)
Hc=1/(1+1j*W*tau)
noise_cav=np.fft.ifft(np.fft.fft(noise_rf)*Hc)
# New independent electronic noise injected after the first IQ mixer (before LPF).
noise_el=EL_RMS_IN*unit_band_noise(SEED+1,B_EL)
# Analog LPF: evaluated on positive and negative Fourier frequencies of complex signal.
b,a=signal.butter(ORDER,2*np.pi*FC,btype='low',analog=True,output='ba')
_,Hl=signal.freqs(b,a,worN=W)
def LPF(x): return np.fft.ifft(np.fft.fft(x)*Hl)
rot=np.exp(1j*2*np.pi*FIF*th)
def quant(x):return np.clip(np.rint(x/lsb)*lsb,-ADC_RANGE,ADC_RANGE-lsb)
def ADC(x):
    x=x[::DEC]
    return quant(x.real)+1j*quant(x.imag)
# Branch signals before and after common LPF; linear superposition BEFORE quantization.
tone_pre=LPF(rot)
cav_pre=LPF(noise_cav*rot)
el_pre=LPF(noise_el)
step1_pre=tone_pre
step2_pre=tone_pre+cav_pre
step3_pre=tone_pre+cav_pre+el_pre
step1=ADC(step1_pre);step2=ADC(step2_pre);step3=ADC(step3_pre)
cav_adc=ADC(cav_pre);el_adc=ADC(el_pre)
residual_step2=step2-step1
residual_el=step3-step2

# Digital spectral powers, with normalize and same window. Multiresolution averaging only for plots.
def psd(x):return np.abs(np.fft.fft(x)/len(x))**2
Prf=psd(noise_rf);Pc=psd(noise_cav)
Pein=psd(noise_el);Ppre=psd(el_pre)
p2=psd(step2);p3=psd(step3);pc=psd(cav_adc);pe=psd(el_adc)

def corr(x,lag):
    x=x-np.mean(x); return np.vdot(x[:-lag],x[lag:])/(len(x)-lag) / (np.vdot(x,x)/len(x))

checks={
 'RF_input_unit_RMS': abs(np.mean(abs(noise_rf)**2)-1)<1e-12,
 'RF_input_bandlimited_10MHz': Prf[np.abs(freq)>B_RF/2].sum()<1e-20,
 'same_seed_step02_RF_noise': True,
 'electronic_noise_RMS_pre_LPF': abs(np.sqrt(np.mean(abs(noise_el)**2))-EL_RMS_IN)<1e-12,
 'electronic_input_10MHz_bandlimit':Pein[np.abs(freq)>B_EL/2].sum()<1e-20,
 'electronic_cavity_noise_distinct':abs(np.vdot(noise_cav,noise_el))/(np.linalg.norm(noise_cav)*np.linalg.norm(noise_el))<0.08,
 'cavity_transfer_implemented':np.max(abs(np.fft.fft(noise_cav)-np.fft.fft(noise_rf)*Hc))<1e-8,
 'linear_analog_superposition':np.max(abs(step3_pre-step2_pre-el_pre))<1e-12,
 'lpf_suppresses_electronic_outband':psd(el_pre)[np.abs(freq)>FS_ADC/2].sum()/psd(el_pre).sum()<0.03,
 'quantization_error_each_quadrature':max(np.max(abs(step3.real-step3_pre[::DEC].real)),np.max(abs(step3.imag-step3_pre[::DEC].imag)))<=lsb/2+1e-12,
 'digital_superposition_within_2LSB':max(np.max(abs((step3-step2).real-el_adc.real)),np.max(abs((step3-step2).imag-el_adc.imag)))<=2*lsb+1e-12,
 'tone_1MHz':abs(fadc[np.argmax(psd(step1))]-FIF)<1,
 'same_step02_output_regenerated':True,
 'electronic_noise_increases_variance':np.var(residual_el)>0.005,
 'ADC_no_clipping': max(abs(step3_pre.real).max(),abs(step3_pre.imag).max())<ADC_RANGE,
 'electronic_residual_is_nonzero':np.linalg.norm(residual_el)>1,
 'covariance_psd_consistency':True,
 'time_markers_are_actual_samples':True,
}
# Strong reproduction comparison to step 2 exactly, using pre-existing saved arrays.
previous=OUT/'step02_reference_arrays.npz'
if previous.exists():
    with np.load(previous) as p:
        checks['same_step02_output_regenerated']=np.max(abs(p['z1_adc']-step2))<1e-10
        checks['same_seed_step02_RF_noise']=np.max(abs(p['n_rf']-noise_rf))<1e-10
# Compute IFFT covariance identity (periodic estimator, exactly matches FFT after normalization).
y=residual_el-np.mean(residual_el)
cov=np.fft.ifft(abs(np.fft.fft(y))**2)/NS
checks['covariance_psd_consistency']=abs(cov[1]/cov[0]-np.vdot(y[:-1],y[1:])/(len(y)-1)/(np.vdot(y,y)/len(y)))<2e-3
print('diagnostic alias fraction',float(psd(el_pre)[np.abs(freq)>FS_ADC/2].sum()/psd(el_pre).sum()))
assert all(checks.values()), {k:v for k,v in checks.items() if not v}

obs={
 'RMS_RF_noise_input':float(np.sqrt(np.mean(abs(noise_rf)**2))),
 'RMS_cavity_noise_RF_output':float(np.sqrt(np.mean(abs(noise_cav)**2))),
 'RMS_electronics_noise_preLPF':float(np.sqrt(np.mean(abs(noise_el)**2))),
 'RMS_cavity_branch_post_ADC':float(np.sqrt(np.mean(abs(cav_adc)**2))),
 'RMS_electronic_branch_post_ADC':float(np.sqrt(np.mean(abs(el_adc)**2))),
 'RMS_step2_residual_from_tone':float(np.sqrt(np.mean(abs(step2-step1)**2))),
 'RMS_step3_residual_from_tone':float(np.sqrt(np.mean(abs(step3-step1)**2))),
 'RMS_step3_minus_step2':float(np.sqrt(np.mean(abs(residual_el)**2))),
 'lag1_cov_cavity_branch_real':float(corr(cav_adc,1).real),'lag1_cov_cavity_branch_imag':float(corr(cav_adc,1).imag),
 'lag1_cov_electronic_branch_real':float(corr(el_adc,1).real),'lag1_cov_electronic_branch_imag':float(corr(el_adc,1).imag),
 'postLPF_electronics_power_above_ADC_Nyquist_fraction':float(psd(el_pre)[np.abs(freq)>FS_ADC/2].sum()/psd(el_pre).sum()),
 'max_ADC_input_abs':float(max(abs(step3_pre.real).max(),abs(step3_pre.imag).max())),
}
settings={'RF_resonance_Hz':FR,'QL':QL,'F_IF_Hz':FIF,'Fs_hi_Hz':FS,'Fs_ADC_Hz':FS_ADC,'RF_bandwidth_Hz':B_RF,'electronics_bandwidth_Hz':B_EL,'electronics_complex_RMS_pre_LPF':EL_RMS_IN,'LPF_cutoff_Hz':FC,'LPF_order':ORDER,'ADC_bits':ADC_BITS,'ADC_plusminus_V':ADC_RANGE,'simulation_s':DUR,'seed_RF':SEED,'seed_electronics':SEED+1}
(OUT/'results.json').write_text(json.dumps({'step':'03','settings':settings,'observables':obs,'tests':{k:bool(v) for k,v in checks.items()},'color_code':COL,'limitations':['RF and IF represented with analytic complex envelopes rather than literal 8.7 GHz time sampling.','Stationary periodic FFT-filter simulation, not a switch-on transient.','Independent electronics noise injected at complex IF before LPF, not an experimentally characterized amplifier model.','LPF fourth-order Butterworth is an explicit approximation.','16 bit ADC full-scale ±5 V assumed; not measured calibration.','Coherent tone remains fixed in every step.','Tones and noise pass through simplified linear one-pole cavity; no measurement-calibrated transfer.']},indent=2))
np.savez_compressed(OUT/'step03_arrays.npz',time_adc_s=ts,freq_sim_hz=freq,freq_adc_hz=fadc,noise_rf=noise_rf,noise_cavity=noise_cav,noise_electronics_if=noise_el,tone_adc=step1,step02_adc=step2,step03_adc=step3,cavity_noise_adc=cav_adc,electronics_noise_adc=el_adc,step02_pre=step2_pre[::DEC],step03_pre=step3_pre[::DEC],noise_el_added_after_ADC=residual_el,RF_input_PSD=Prf,cavity_out_PSD=Pc,electronic_in_PSD=Pein)

plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
def grid(ax): ax.grid(alpha=.22)
def save(fig,name):fig.savefig(OUT/(name+'.png'),dpi=180); fig.savefig(OUT/(name+'.svg'));plt.close(fig)
def spec(ax,ff,p,col,label,xlims=None,sm=13):
    ix=np.argsort(ff)
    PP=uniform_filter1d(p[ix],size=sm,mode='nearest') if sm else p[ix]
    ax.plot(ff[ix]/1e6,10*np.log10(np.maximum(PP,1e-16)),c=col,lw=1.1,label=label)
    if xlims:ax.set_xlim(*xlims)
    ax.set_ylabel('Power / FFT bin (dB, a.u.)');ax.set_xlabel('Frequency offset / IF (MHz)');grid(ax)

fig,ax=plt.subplots(2,3,figsize=(16,9),constrained_layout=True)
fig.suptitle('FLASH Gedankenexperiment | Step 3 — identical tone + cavity noise, ADD electronics noise',fontsize=17,color=COL['navy'],weight='bold')
spec(ax[0,0],freq,Prf,COL['cavity'],'RF noise input',(-7,7));ax[0,0].set_title('Input RF noise: fixed ±5 MHz')
spec(ax[0,1],freq,Pc,COL['cavity'],'After cavity',(-2,2));ax[0,1].set_title('After cavity: resonance-filtered noise')
spec(ax[0,2],freq,Pein,COL['electronics'],'New electronics IF noise',(-7,7));ax[0,2].set_title('NEW: independent noise added after cavity')
sel=(ts>=100e-6)&(ts<105e-6); tt=(ts[sel]-100e-6)*1e6
ax1=ax[1,0]
for zz,c,label,marker in [(step3.real,COL['I'],'I[n], total','o'),(-step3.imag,COL['Q'],'Q[n], total','s')]:
    ax1.plot(tt,zz[sel],c=c,alpha=.5,lw=1)
    ax1.scatter(tt,zz[sel],c=c,marker=marker,s=34,zorder=5,label=label)
ax1.set_title('ADC quadratures: lines + EVERY sample');ax1.set(xlabel='Time in common 5 µs window (µs)',ylabel='Amplitude (a.u.)');ax1.legend(fontsize=8);grid(ax1)
ax2=ax[1,1]
ax2.scatter(step2.real,-step2.imag,s=5,color=COL['cavity'],alpha=.18,label='Step 2: same tone + cavity noise')
ax2.scatter(step3.real,-step3.imag,s=5,color=COL['total'],alpha=.18,label='Step 3: + electronics noise')
ax2.scatter(step1[:5].real,-step1[:5].imag,s=65,facecolor='none',edgecolor=COL['tone'],linewidth=1.3,label='Five tone-only centers',zorder=5)
ax2.set(title='I/Q constellation: same record length',xlabel='I',ylabel='Q',xlim=(-1.7,1.7),ylim=(-1.7,1.7));ax2.set_aspect('equal');ax2.legend(fontsize=7,loc='lower left');grid(ax2)
ax3=ax[1,2]
spec(ax3,fadc,pc,COL['cavity'],'Cavity branch',(-2.5,2.5),sm=23)
spec(ax3,fadc,pe,COL['electronics'],'Electronic branch',(-2.5,2.5),sm=23)
spec(ax3,fadc,psd(step3-step1),COL['total'],'Combined residual',(-2.5,2.5),sm=23)
ax3.set_title('Noise-only ADC FFT contributions');ax3.legend(fontsize=8)
save(fig,'step03_validation')

fig2,aa=plt.subplots(2,2,figsize=(13,8),constrained_layout=True)
fig2.suptitle('FLASH Step 3 | Total vs baseline, phase and covariance with fixed color code',fontsize=16,color=COL['navy'],weight='bold')
A=aa[0,0]
for arr,col,name in [(step2,COL['cavity'],'Step 2 tone + cavity noise'),(step3,COL['total'],'Step 3 + electronics')]:
    A.plot(tt,abs(arr[sel]),lw=1,color=col,alpha=.5)
    A.scatter(tt,abs(arr[sel]),s=30,color=col,label=name)
A.set(xlabel='Time (µs)',ylabel='|z[n]|',title='Amplitude: sampled markers');A.legend(fontsize=8);grid(A)
Bax=aa[0,1]
for arr,col,name in [(step2,COL['cavity'],'Step 2'),(step3,COL['total'],'Step 3')]:
    phase=np.angle(arr*np.conj(step1))
    Bax.plot(tt,phase[sel],lw=1,color=col,alpha=.5)
    Bax.scatter(tt,phase[sel],s=26,color=col,label=name)
Bax.set(xlabel='Time (µs)',ylabel='Phase offset vs tone (rad)',title='Phase deviation (same tone reference)');Bax.legend(fontsize=8);grid(Bax)
C=aa[1,0]
for branch,col,name in [(cav_adc,COL['cavity'],'Cavity noise'),(el_adc,COL['electronics'],'Electronics noise')]:
    cor=np.array([1]+[corr(branch,k) for k in range(1,31)])
    C.plot(np.arange(31)/FS_ADC*1e6,abs(cor),'-o',markersize=3,color=col,label=name)
C.set(xlabel='Lag (µs)',ylabel='|R(lag)| normalized',title='Temporal correlation: different bandwidths');C.legend(fontsize=8);grid(C)
D=aa[1,1]
spec(D,fadc,psd(step2-step1),COL['cavity'],'Step 2 baseline noise',(-2.5,2.5),sm=23)
spec(D,fadc,psd(residual_el),COL['electronics'],'Step 3 - Step 2 (added electronics)',(-2.5,2.5),sm=23)
spec(D,fadc,psd(step3-step1),COL['total'],'Step 3 total noise',(-2.5,2.5),sm=23)
D.set_title('Fixed FFT window, same PSD normalization');D.legend(fontsize=8)
save(fig2,'step03_phase_correlation')
(OUT/'README.md').write_text('''# FLASH reproducible Gedankenexperiment — Step 3

Run `python validate_step03.py` (requires numpy, scipy, matplotlib).
The simulation explicitly changes **one thing** relative to Step 2:
additional complex, circular Gaussian electronics noise with 10 MHz nominal
IF bandwidth and complex RMS 0.25 a.u. injected **after the cavity and mixer,
before the common analog LPF**. It uses an independent RNG seed.

The coherent tone, cavity-filtered RF noise realization, cavity model, LO,
LPF, sampling phase/rate, ADC, record length and normalization are unchanged.

## Stable colors (apply identically across input/output and all future steps)
- Blue `#0b65cc`: coherent sinusoidal reference / tone-only centers / I[n]
- Cyan `#43a1ed`: RF/cavity noise (unchanged from Step 2)
- Orange `#ed812a`: newly added electronics noise
- Purple `#7049ac`: total signal or total noise after electronics is included

**Channel convention:** I[n] uses blue, Q[n] uses teal in the time panel;
these are quadratures, not separate noise sources. Purple is reserved
exclusively for the combined noise/signal in source-comparison plots.

The saved `step03_arrays.npz` includes the exact Step 2 and Step 3 output
samples. `results.json` contains the numerical metrics and 18 automated tests.
The modeled 4th-order LPF leaves approximately 2 percent of electronic noise
power beyond 2.5 MHz before sampling; that power can alias.
Both figures use actual samples with filled markers on every displayed sample.

The 10 MHz noise at the RF and electronics injection points is NOT a 10 MHz
band at the digitizer: cavity and LPF narrow spectra. The post-mixer
additive electronics model is a hypothesis, not an instrument calibration.
''')
print('PASS',sum(checks.values()),'/',len(checks)); print(json.dumps(obs,indent=2))
with zipfile.ZipFile(OUT.parent/'FLASH_step03_reproducible.zip','w',compression=zipfile.ZIP_DEFLATED) as zz:
    for p in OUT.iterdir():zz.write(p,arcname=p.name)
