#!/usr/bin/env python3
"""FLASH step 2: one common coherent on-resonance tone + complex Gaussian RF noise.
The 8.737 GHz carrier is never sampled numerically; RF is represented by its
analytic complex envelope at a 40 MHz simulation rate. Cavity response is
applied to the noise envelope; I/Q mixing, analog LPF, sampling and ADC follow.
"""
import json
from pathlib import Path
import numpy as np
import scipy.signal as sig
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
FR=8.737119e9; QL=29306.; FIF=1e6; FLO=FR-FIF
FS_HI=40e6; FS_ADC=5e6; DEC=8; DURATION=400e-6
B_RF=10e6; FC_LPF=1.9e6; LP_ORDER=4; ADC_BITS=16; ADC_RANGE=5.0
TAU=QL/(np.pi*FR); LINEWIDTH=FR/QL; SEED=20261112
N=int(FS_HI*DURATION); NADC=N//DEC
assert N%DEC==0
th=np.arange(N)/FS_HI; ta=th[::DEC]; df=np.fft.fftfreq(N,1/FS_HI)
rng=np.random.default_rng(SEED)

# Flat-band, zero-mean, complex Gaussian RF envelope (no aliased 8.7-GHz carrier).
base=rng.normal(size=N)+1j*rng.normal(size=N)
B=np.fft.fft(base)
B[np.abs(df)>B_RF/2]=0
n_rf=np.fft.ifft(B)
n_rf=n_rf/np.sqrt(np.mean(abs(n_rf)**2))  # unit RMS complex RF noise
H_cavity=1/(1+1j*2*np.pi*df*TAU)
n_cavity=np.fft.ifft(np.fft.fft(n_rf)*H_cavity)

# Steady-state coherent carrier of amplitude 1 on resonance, identical baseline.
tone_env=np.ones(N,dtype=complex)

def analog_lpf_complex(z):
    # Analog Butterworth transfer H(j*2πf), applied to periodic steady-state record.
    b,a=sig.butter(LP_ORDER, 2*np.pi*FC_LPF,btype='low',analog=True,output='ba')
    _,h=sig.freqs(b,a,worN=2*np.pi*df)
    return np.fft.ifft(np.fft.fft(z)*h)

def acquire(envelope):
    z_if=envelope*np.exp(1j*2*np.pi*FIF*th)
    z_filt=analog_lpf_complex(z_if)
    z_sample=z_filt[::DEC]
    lsb=2*ADC_RANGE/(2**ADC_BITS)
    def quant(x):return np.clip(np.rint(x/lsb)*lsb,-ADC_RANGE,ADC_RANGE-lsb)
    z_adc=quant(z_sample.real)+1j*quant(z_sample.imag)
    # Data convention z=I-iQ : Q measured is -imag(z)
    return z_if,z_filt,z_sample,z_adc,lsb

z0_if,z0_filt,z0_pre,z0_adc,lsb=acquire(tone_env)
z1_if,z1_filt,z1_pre,z1_adc,_=acquire(tone_env+n_cavity)
zn_if,zn_filt,zn_pre,zn_adc,_=acquire(n_cavity)

# Robust spectral statistics using FFT and same normalization for all branches.
def power_by_freq(x):return abs(np.fft.fft(x))**2/len(x)**2
P_RF=power_by_freq(n_rf); P_CAV=power_by_freq(n_cavity)
P_pre=power_by_freq(zn_filt)
P_adc=power_by_freq(zn_adc)
f_adc=np.fft.fftfreq(NADC,1/FS_ADC)

# noise baseline testing; deterministic seed, exact transfer identity, independent ADC error bound
band=(abs(df)<=B_RF/2)
noise_rms_rf=float(np.sqrt(np.mean(abs(n_rf)**2)))
noise_rms_cavity=float(np.sqrt(np.mean(abs(n_cavity)**2)))
noise_rms_adc=float(np.sqrt(np.mean(abs(zn_adc)**2)))
mean_noise_adc=float(abs(np.mean(zn_adc)))
quant_error=float(max(np.max(abs(z1_adc.real-z1_pre.real)),np.max(abs(z1_adc.imag-z1_pre.imag))))

# Cross-spectral reconstruction: filtered noise covariance equals inverse Fourier PSD.
x=zn_adc-np.mean(zn_adc)
lag1_time=np.vdot(x[:-1],x[1:])/np.vdot(x,x) * (len(x)/(len(x)-1))
ifft_cov=np.fft.ifft(abs(np.fft.fft(x))**2)/len(x)
lag1_fft=ifft_cov[1]/ifft_cov[0]

# Spectrum maximum above Nyquist before ADC (measures possible alias feedthrough)
alias_fraction=float(P_pre[np.abs(df)>=FS_ADC/2].sum()/P_pre.sum())

checks={
 'input_RF_spectrum_inside_10MHz':bool(P_RF[~band].sum()<1e-20),
 'RF_noise_complex_RMS_is_one':bool(abs(noise_rms_rf-1)<1e-12),
 'cavity_halfpower_at_FWHM_over_2':bool(np.isclose(abs(1/(1+1j*np.pi*LINEWIDTH*TAU))**2,.5,atol=1e-12)),
 'cavity_noise_is_attenuated':bool(noise_rms_cavity<0.4*noise_rms_rf),
 'cavity_output_equals_frequency_domain_filter':bool(np.max(abs(np.fft.fft(n_cavity)-np.fft.fft(n_rf)*H_cavity))<1e-8),
 'same_coherent_tone_baseline':bool(np.max(abs(z0_adc-z1_adc+zn_adc))<4*lsb),
 'ADC_per_quadrature_error_le_half_LSB':bool(quant_error<=lsb/2+1e-12),
 'noise_zero_mean_output_approx':bool(mean_noise_adc<0.04*noise_rms_adc),
 'tone_FFT_peak_at_plus_1MHz':bool(abs(f_adc[np.argmax(abs(np.fft.fft(z0_adc)))]-FIF)<1),
 'sampled_noise_has_nonzero_variance':bool(noise_rms_adc>0.04),
 'covariance_IFT_PSD_matches_lag1':bool(abs(lag1_time-lag1_fft)<2e-3),
 'LPF_attenuates_aliasing_content':bool(alias_fraction<0.02),
 'noise_changes_constellation':bool(np.std(abs(z1_adc))>0.025),
 'no_ADC_clipping':bool(max(abs(z1_pre.real).max(),abs(z1_pre.imag).max())<ADC_RANGE),
}
if not all(checks.values()):
    raise AssertionError('FAILED: '+str({k:v for k,v in checks.items() if not v}))

metrics={
 'version':'validated-step02-v1',
 'model':'single-pole cavity, steady coherent tone plus independently generated flat 10MHz RF Gaussian noise, ideal mixer, 4th-order analog Butterworth LPF, 16-bit ADC',
 'settings':{'fr_hz':FR,'QL_model':QL,'IF_hz':FIF,'LO_hz':FLO,'RF_noise_B_hz':B_RF,'RF_noise_rms_input':1,'coherent_tone_rms_envelope':1,'fs_simulation_hz':FS_HI,'fs_ADC_hz':FS_ADC,'analog_lpf_order':LP_ORDER,'analog_lpf_fc_hz':FC_LPF,'ADC_bits':ADC_BITS,'ADC_range_plus_minus_v':ADC_RANGE,'duration_s':DURATION,'N_ADC_samples':NADC,'random_seed':SEED},
 'derived':{'cavity_linewidth_hz':LINEWIDTH,'cavity_tau_amplitude_s':TAU,'ADC_lsb_v':lsb},
 'observed':{'RF_noise_rms':noise_rms_rf,'cavity_filtered_noise_rms':noise_rms_cavity,'sampled_noise_rms':noise_rms_adc,'ADC_noise_mean_magnitude':mean_noise_adc,'quantization_max_per_quadrature_v':quant_error,'lag1_corr_complex_real':float(lag1_fft.real),'lag1_corr_complex_imag':float(lag1_fft.imag),'pre_ADC_outside_nyquist_power_fraction':alias_fraction,'amplitude_std_step01':float(np.std(abs(z0_adc))),'amplitude_std_step02':float(np.std(abs(z1_adc))),'adc_max_abs_step02':float(max(abs(z1_pre.real).max(),abs(z1_pre.imag).max()))},
 'tests':checks,
 'limitations':['This model does not include electronics-induced additive noise or measured calibration response.','The linear resonator model is applied to the RF noise envelope; steady tone is assumed at equilibrium.','Flat 10MHz RF bandwidth is BEFORE the cavity, not preserved at the ADC.','The analog LPF is a stated 4th-order Butterworth approximation, not a measured transfer.','The finite simulation uses periodic FFT filtering to represent stationary signals; no startup transient.','The ADC quantizer is modeled as independent ideal 16-bit channels ±5 V (not instrument-calibrated).']
}
(HERE/'results.json').write_text(json.dumps(metrics,indent=2)+'\n')
np.savez_compressed(HERE/'step02_arrays.npz',t_adc_s=ta,baseband_freq_hz=df,adc_freq_hz=f_adc,n_rf=n_rf,n_cavity=n_cavity,z0_adc=z0_adc,z1_adc=z1_adc,zn_adc=zn_adc,z0_pre=z0_pre,z1_pre=z1_pre,RF_noise_PSD=P_RF,cavity_noise_PSD=P_CAV,ADC_noise_power=P_adc)

NAVY='#0b356a'; BLUE='#0b65cc'; CYAN='#43a1ed'; ORANGE='#ed812a'
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axs=plt.subplots(2,3,figsize=(15,9),constrained_layout=True)
fig.suptitle('FLASH Gedankenexperiment | Validated step 2 — same tone + 10 MHz RF Gaussian noise',fontsize=17,color=NAVY,fontweight='bold')
# spectra from equivalent RF offset; averaging to reduce scatter for presentation
from scipy.ndimage import uniform_filter1d
order=np.argsort(df); fsort=df[order]/1e6
for ax,px,title in [(axs[0,0],P_RF,'Generated RF noise (±5 MHz)'),(axs[0,1],P_CAV,'Noise after resonant cavity')]:
    sp=uniform_filter1d(px[order],size=37,mode='nearest')
    ax.plot(fsort,10*np.log10(np.maximum(sp,1e-17)),color=BLUE,lw=1.2)
    ax.axvline(-LINEWIDTH/2/1e6,color=ORANGE,ls=':',alpha=.8)
    ax.axvline(LINEWIDTH/2/1e6,color=ORANGE,ls=':',alpha=.8)
    ax.set(xlabel='RF offset from resonance (MHz)',ylabel='Power per FFT bin (dB, a.u.)',title=title,xlim=(-7,7))
# time series
sel=(ta>=100e-6)&(ta<105e-6); t_us=(ta[sel]-100e-6)*1e6
ax=axs[0,2]; ax.plot(t_us,z1_adc.real[sel],color=BLUE,alpha=.45,lw=1)
ax.plot(t_us,-z1_adc.imag[sel],color=CYAN,alpha=.45,lw=1)
ax.scatter(t_us,z1_adc.real[sel],s=28,color=BLUE,zorder=4,label='I[n] sample')
ax.scatter(t_us,-z1_adc.imag[sel],s=28,marker='s',color=CYAN,zorder=4,label='Q[n] sample')
ax.set(xlabel='Time in 5 µs window (µs)',ylabel='Voltage (a.u.)',title='I, Q: sampled lines + visible markers');ax.legend(fontsize=8)
# constellation compare exactly same time window and all samples step 1 vs 2
ax=axs[1,0]
ax.scatter(z1_adc.real,-z1_adc.imag,s=5,color=CYAN,alpha=.18,label='tone + Gaussian RF noise')
ax.scatter(z0_adc[:5].real,-z0_adc[:5].imag,s=50,color=ORANGE,zorder=5,label='five tone-only positions')
ax.set(title='Constellation: identical tone + noise',xlabel='I',ylabel='Q',xlim=(-1.6,1.6),ylim=(-1.6,1.6));ax.set_aspect('equal');ax.legend(fontsize=7,loc='lower left')
# amplitude and phase
ax=axs[1,1]; k=np.flatnonzero(sel)
ax.plot(t_us,abs(z0_adc[k]),color=ORANGE,lw=1.5,ls='--',label='|z| tone-only')
ax.plot(t_us,abs(z1_adc[k]),color=BLUE,alpha=.5,lw=1,label='|z| tone+noise')
ax.scatter(t_us,abs(z1_adc[k]),s=19,color=BLUE)
ax.set(xlabel='Time (µs)',ylabel='Amplitude |z[n]| (a.u.)',title='Amplitude (tone vs tone + noise)')
ax.legend(fontsize=8)
# FFT: coherent peak plus noise floor
ax=axs[1,2]
ff=np.fft.fft(z1_adc)/NADC; ff0=np.fft.fft(z0_adc)/NADC
ix=np.argsort(f_adc)
ax.plot(f_adc[ix]/1e6,20*np.log10(np.maximum(abs(ff[ix]),1e-8)),color=BLUE,lw=.8,label='tone + noise')
ax.plot(f_adc[ix]/1e6,20*np.log10(np.maximum(abs(ff0[ix]),1e-8)),color=ORANGE,alpha=.5,lw=.8,label='tone only')
ax.set(xlabel='IF frequency (MHz)',ylabel='FFT magnitude (dB ref. 1)',title='ADC complex FFT (noise bandwidth narrowed)',ylim=(-145,4),xlim=(-2.5,2.5));ax.legend(fontsize=8)
for ax in axs.flat: ax.grid(alpha=.22)
fig.savefig(HERE/'step02_validated.png',dpi=170);fig.savefig(HERE/'step02_validated.svg');plt.close(fig)
print('PASS',sum(checks.values()),'/',len(checks))
print('noise RMS RF',noise_rms_rf,'cavity',noise_rms_cavity,'ADC',noise_rms_adc)
print('lag1 complex covariance',lag1_fft,'pre-ADC alias band fraction',alias_fraction)

# Additional phase and correlation diagnostics, same realization and samples.
phi0=np.unwrap(np.angle(z0_adc))
phi1=np.unwrap(np.angle(z1_adc))
phase_residual=np.angle(z1_adc*np.conj(z0_adc))
fig2,ax2=plt.subplots(1,3,figsize=(14.5,4.5),constrained_layout=True)
fig2.suptitle('Step 2 | Phase deviations and cavity-induced temporal correlations',color=NAVY,fontweight='bold',fontsize=15)
sl=(ta>=100e-6)&(ta<105e-6)
ax2[0].plot((ta[sl]-100e-6)*1e6,phi0[sl]-phi0[sl][0],ls='--',lw=1.6,c=ORANGE,label='tone-only')
ax2[0].plot((ta[sl]-100e-6)*1e6,phi1[sl]-phi1[sl][0],lw=1,c=BLUE,alpha=.6,label='tone + noise')
ax2[0].scatter((ta[sl]-100e-6)*1e6,phi1[sl]-phi1[sl][0],s=18,c=BLUE)
ax2[0].set(xlabel='Time (µs)',ylabel='Unwrapped phase (rad)',title='Phase evolution');ax2[0].legend(fontsize=8)
ax2[1].plot((ta[sl]-100e-6)*1e6,phase_residual[sl],lw=1,c=ORANGE)
ax2[1].scatter((ta[sl]-100e-6)*1e6,phase_residual[sl],s=22,c=ORANGE)
ax2[1].set(xlabel='Time (µs)',ylabel='arg(z_noise+tone × conj(z_tone)) (rad)',title='Phase deviation from same tone')
lag_samples=np.arange(0,41)
cc=np.array([np.vdot(x[:-j],x[j:])/(len(x)-j) if j>0 else np.vdot(x,x)/len(x) for j in lag_samples]);cc/=cc[0]
ax2[2].plot(lag_samples*1e6/FS_ADC,np.abs(cc),'-o',ms=3,c=BLUE,label='|R|')
ax2[2].plot(lag_samples*1e6/FS_ADC,np.real(cc),'-s',ms=3,c=ORANGE,alpha=.8,label='Re(R)')
ax2[2].set(xlabel='Lag (µs)',ylabel='Normalized complex covariance',title='Correlated Gaussian noise');ax2[2].legend(fontsize=8)
for ax in ax2:ax.grid(alpha=.22)
fig2.savefig(HERE/'step02_phase_correlation.png',dpi=170)
fig2.savefig(HERE/'step02_phase_correlation.svg');plt.close(fig2)

readme='''# FLASH Gedankenexperiment — Step 2 (reproducible)

## Reproduce

```bash
python validate_step02.py
```

Dependencies: Python 3, NumPy, SciPy and Matplotlib. The code writes numerical
arrays (`step02_arrays.npz`), measured outputs (`results.json`) and the two
figures (`step02_validated.png`, `step02_phase_correlation.png`).

## What is held fixed relative to Step 1

TM010 model resonance: 8.737119 GHz, QL=29306. Steady coherent tone at cavity
resonance, complex amplitude 1. LO chosen 1 MHz lower, so IF=+1 MHz.
5 MS/s ADC, 16 bits, bipolar assumed ±5 V.

## What changes in Step 2

Added complex zero-mean Gaussian noise with *flat RF input spectrum* across
10 MHz, centered at the cavity resonance, and input complex RMS = 1 a.u.
The cavity transfer 1/(1+i 2π Δf τ) (τ=QL/(π fr)) filters that noise.
Both the steady tone and filtered noise then go through an ideal I/Q mixer,
**assumed** 4th-order analog Butterworth LPF at 1.9 MHz, and 5 MS/s ADC.

An envelope simulation at 40 MHz is used instead of sampling the 8.7 GHz RF
carrier. The stationary process is synthesized by Fourier masking and filtered
in the Fourier domain (periodic steady state). This does NOT simulate source
switch-on, thermal cavity emission, input-output noise correlations, real
mixer imbalance, additive amplifier noise or the measured frequency response.

## Interpretation

The RF input has a flat 10 MHz wide spectrum, but the resonator narrows the
cavity-output noise PSD to a Lorentzian profile (~298 kHz FWHM in power).
The coherently driven tone produces five phase-synchronous clusters at
fIF/fs = 1/5. Gaussian noise broadens them radially and angularly. This does
not by itself demonstrate sidebands or out-of-band noise.

Markers show *actual ADC samples*, with thin lines only joining consecutive
samples. Phase residual is the wrapped angle of the event-vs-baseline complex
ratio, here referring to added noise, not an injected transient.

## Validation

14 assertions verify RF band limits, Gaussian-noise RMS, cavity response,
linear superposition to within quantization, quantization bounds, tone IF,
noise variance, covariance/PSD consistency, analog LPF's alias rejection,
and no clipping. They validate this mathematical implementation, **not the
real instrument**. For finer validation inspect results.json and test the
independent software modules against measured calibration data.
'''
(HERE/'README.md').write_text(readme)
