#!/usr/bin/env python3
"""Reproducible FLASH Gedankenexperiment Step 1: resonant steady coherent tone.

All numerical operations work with the analytic complex envelope of the RF signal,
not samples of the 8.7 GHz carrier. The RF cavity is a single-pole resonator.
No noise, no injected transient, no unknown hardware response.
"""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
FR_HZ=8.737119e9
QL=29306.0 # Working model value: requires comparison with measured instrument configuration
FIF_HZ=1e6
FLO_HZ=FR_HZ-FIF_HZ
FS_HZ=5e6
DURATION_S=100e-6
FULL_SCALE_V=5.0  # bipolar ADC range [-5, +5) V; explicit modeling assumption
NBITS=16
INPUT_ENVELOPE_V=1.0

# Single pole complex envelope response: H(df)=1/(1+i*2*pi*df*tau)
TAU_S=QL/(np.pi*FR_HZ)
LINEWIDTH_HZ=FR_HZ/QL
TS=1.0/FS_HZ
N=int(round(DURATION_S*FS_HZ))
t=np.arange(N)*TS

def cavity_transfer(detuning_hz):
    return 1.0/(1.0+1j*2*np.pi*detuning_hz*TAU_S)

def ideal_iq_downconversion(envelope, time):
    # Conventions z=I-iQ and Q=-Im(z), consistent with experimental presentation
    z=np.asarray(envelope,dtype=complex)*np.exp(1j*2*np.pi*FIF_HZ*time)
    return z.real, -z.imag

def adc_quantize(x, full_scale=FULL_SCALE_V, bits=NBITS):
    lsb=2*full_scale/2**bits
    return np.clip(np.rint(np.asarray(x)/lsb)*lsb,-full_scale,full_scale-lsb)

# Steady state tone exactly on resonance: H(0)=1; deliberately exclude switch-on transient.
envelope=np.full(N, INPUT_ENVELOPE_V*cavity_transfer(0.0),dtype=complex)
I_analog,Q_analog=ideal_iq_downconversion(envelope,t)
I_adc=adc_quantize(I_analog)
Q_adc=adc_quantize(Q_analog)
z_analog=I_analog-1j*Q_analog
z_adc=I_adc-1j*Q_adc
amplitude=np.abs(z_adc)
phi=np.unwrap(np.angle(z_adc))
fft_analog=np.fft.fft(z_analog)/N
fft_adc=np.fft.fft(z_adc)/N
freq=np.fft.fftfreq(N,d=TS)

# Tests based on analytic expectations. No numerical filtering is applied to an on-resonance,
# steady-state pure tone (because it would add a transient irrelevant to this step).
lsb=2*FULL_SCALE_V/2**NBITS
checks={
 'cavity_on_resonance_unity':bool(np.isclose(cavity_transfer(0),1,atol=1e-14)),
 'cavity_half_power_at_half_linewidth':bool(np.isclose(abs(cavity_transfer(LINEWIDTH_HZ/2))**2,0.5,atol=1e-12)),
 'iq_matches_exact_tone':bool(np.max(np.abs(z_analog-np.exp(1j*2*np.pi*FIF_HZ*t)))<1e-11),
 'adc_I_error_le_half_lsb':bool(np.max(abs(I_adc-I_analog))<=lsb/2+1e-12),
 'adc_Q_error_le_half_lsb':bool(np.max(abs(Q_adc-Q_analog))<=lsb/2+1e-12),
 'adc_complex_amplitude_near_one':bool(np.max(abs(amplitude-1))<1e-4),
 'five_sample_periodicity':bool(np.max(abs(z_adc[5:]-z_adc[:-5]))<1e-10),
 'fft_peak_at_positive_1MHz':bool(np.isclose(freq[np.argmax(abs(fft_adc))],FIF_HZ)),
 'no_false_negative_frequency_peak':bool(abs(fft_adc[np.argmin(abs(freq+FIF_HZ))])<1e-4),
 'phase_slope_approx_2pi_1MHz':bool(abs(np.polyfit(t,phi,1)[0]-2*np.pi*FIF_HZ)<200),
}
if not all(checks.values()):
    raise AssertionError('VALIDATION FAILED: '+str({k:v for k,v in checks.items() if not v}))

metrics={
 'version':'validated-step01-v1',
 'model':'steady-state coherent single RF tone, one-pole cavity response, ideal IQ, 16 bit independent ADC quantization',
 'source_parameters':{'fr_hz':FR_HZ,'QL_assumed':QL,'IF_hz':FIF_HZ,'LO_hz':FLO_HZ,'fs_hz':FS_HZ,'bits':NBITS,'ADC_bipolar_fullscale_v':FULL_SCALE_V,'amplitude_v':INPUT_ENVELOPE_V,'sample_count':N},
 'derived':{'linewidth_hz':LINEWIDTH_HZ,'tau_amplitude_s':TAU_S,'adc_lsb_v':lsb,'phase_advance_rad':2*np.pi*FIF_HZ/FS_HZ,'samples_per_period':FS_HZ/FIF_HZ},
 'observed':{'max_abs_I_error_v':float(np.max(abs(I_adc-I_analog))),'max_abs_Q_error_v':float(np.max(abs(Q_adc-Q_analog))),'max_amplitude_error':float(np.max(abs(amplitude-1))),'max_period_5_difference':float(np.max(abs(z_adc[5:]-z_adc[:-5]))),'fft_peak_hz':float(freq[np.argmax(abs(fft_adc))]),'fft_peak_magnitude':float(np.max(abs(fft_adc)))},
 'tests':checks,
 'notes':['ADC input range is a declared modeling choice, not a validated hardware setting.','The cavity steady-state tone has no ring-down; switch-on/ring-down will be separate experiments.','No Gaussian noise, no sidebands, no transient, no analog LPF included in this first validation.','For the ideal on-resonance tone, its amplitude is normalized to unity; real gain calibration is not modeled.']
}
(HERE/'results.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False)+'\n')
np.savez_compressed(HERE/'step01_arrays.npz',t_s=t,I_analog=I_analog,Q_analog=Q_analog,I_adc=I_adc,Q_adc=Q_adc,z_adc=z_adc,phase_unwrapped_rad=phi,frequency_hz=freq,fft_adc=fft_adc)

NAVY='#0b356a'; BLUE='#0b65cc'; CYAN='#43a1ed'; ORANGE='#ed812a'
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig=plt.figure(figsize=(14,8),facecolor='white',layout='constrained')
axs=fig.subplots(2,3)
fig.suptitle('FLASH Gedankenexperiment | Validated step 1: coherent tone on TM010 resonance',fontsize=17,fontweight='bold',color=NAVY)
# 1. cavity resonance
ax=axs[0,0]; df=np.linspace(-1.2e6,1.2e6,1200)
ax.plot(df/1e3,np.abs(cavity_transfer(df))**2,color=BLUE,lw=2)
ax.axvline(0,color=ORANGE,ls='--',label='tone at resonance')
ax.set(title='Cavity power transfer',xlabel='Offset from resonance (kHz)',ylabel=r'$|H(\Delta f)|^2$');ax.legend(fontsize=8)
# 2 waveform
ax=axs[0,1]; k=np.arange(26)
ax.plot(t[k]*1e6,I_analog[k],color=BLUE,alpha=.4,lw=1)
ax.plot(t[k]*1e6,Q_analog[k],color=CYAN,alpha=.4,lw=1)
ax.scatter(t[k]*1e6,I_adc[k],s=27,color=BLUE,label='I ADC samples',zorder=3)
ax.scatter(t[k]*1e6,Q_adc[k],s=29,marker='s',color=CYAN,label='Q ADC samples',zorder=3)
ax.set(title='I and Q: lines + actual sample markers',xlabel='Time (µs)',ylabel='Voltage (normalized V)',ylim=(-1.25,1.25));ax.legend(fontsize=8)
# constellation
ax=axs[0,2];th=np.linspace(0,2*np.pi,301)
ax.plot(np.cos(th),-np.sin(th),color='#b5d5f3',lw=1.2,label='Ideal circle')
ax.scatter(I_adc[:5],Q_adc[:5],s=55,color=BLUE,zorder=4)
for n in range(5): ax.annotate(str(n),(I_adc[n],Q_adc[n]),xytext=(5,5),textcoords='offset points',fontsize=9)
ax.set(title='Five IQ positions (5 samples/period)',xlabel='I',ylabel='Q',xlim=(-1.3,1.3),ylim=(-1.3,1.3),aspect='equal')
# amplitude
ax=axs[1,0];ax.plot(t[k]*1e6,amplitude[k],color=BLUE,lw=1,alpha=.5)
ax.scatter(t[k]*1e6,amplitude[k],color=BLUE,s=27)
ax.set(title='ADC amplitude: nearly constant',xlabel='Time (µs)',ylabel='|z[n]|',ylim=(0.998,1.002))
# phase
ax=axs[1,1];ax.plot(t[k]*1e6,phi[k],color=ORANGE,lw=1)
ax.scatter(t[k]*1e6,phi[k],color=ORANGE,s=27)
ax.set(title='Unwrapped phase: 2π/5 per sample',xlabel='Time (µs)',ylabel='Phase (rad)')
# FFT
ax=axs[1,2]; sel=(freq>=-2.5e6)&(freq<=2.5e6)
ax.plot(freq[sel]/1e6,20*np.log10(np.maximum(abs(fft_adc[sel]),1e-8)),color=BLUE,lw=1)
ax.axvline(1,color=ORANGE,alpha=.6,ls='--')
ax.set(title='Complex FFT: one line at +1 MHz',xlabel='Frequency (MHz)',ylabel='Magnitude (dB, ref. 1)',ylim=(-165,4))
for ax in axs.flat:ax.grid(alpha=.22)
fig.savefig(HERE/'step01_validated.png',dpi=180)
fig.savefig(HERE/'step01_validated.svg')
plt.close(fig)
print('PASS:',sum(checks.values()),'/',len(checks),'tests')
print('tau_us',TAU_S*1e6,'line_width_kHz',LINEWIDTH_HZ/1e3,'phase_step',2*np.pi/5)
print('adc_LSB',lsb,'max_amplitude_deviation',metrics['observed']['max_amplitude_error'])
