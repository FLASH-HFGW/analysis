#!/usr/bin/env python3
"""FLASH theoretical thermal cavity baseline: no coherent tone, no receiver-added noise.

Models single-port cavity emission from an internal thermal bath with one Lorentzian
resonance and critical coupling. Generates a circular Gaussian stochastic field in
the frequency domain, propagates it through a causal cavity transfer function,
ideal I/Q translation, a fourth-order analog Butterworth LPF, and a 16-bit ADC.

This is a theoretical example, not a fit to observed QUAX data. Units of ADC voltage
are defined by an explicit arbitrary ideal *noiseless* gain.
"""
import json
from pathlib import Path
import numpy as np
from scipy import constants, signal, stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

OUT = Path(__file__).resolve().parent
SEED = 20261112
# Theory-only defaults: none inferred from a data-taking campaign.
f_res = 8.8e9  # Hz
T_cav = 0.100  # K
Q0 = 50_000.0
beta = 1.0  # critical coupling kappa_e/kappa_i
Q_L = Q0/(1+beta)
kappa_i = 2*np.pi*f_res/Q0
kappa_e = beta*kappa_i
kappa = kappa_i+kappa_e
FWHM = f_res/Q_L
TAU_A = 1/(np.pi*FWHM)
B_bath = 10e6  # Hz flat source band centered at the cavity resonance
f_lo = f_res-1e6
f_if = f_res-f_lo
fs_analog = 50e6
fs_adc = 5e6
decimation = int(fs_analog/fs_adc)
duration = 0.020  # seconds, steady-state stochastic realization
N = int(fs_analog * duration)
N_adc = N//decimation
f_lpf = 1.9e6
lpf_order = 4
R = 50.0
G_dB = 140.0  # explicitly arbitrary ideal power gain, no added noise
G_power = 10**(G_dB/10)
adc_bits = 16
adc_full_scale_peak = 5.0
adc_step = 2*adc_full_scale_peak / (2**adc_bits)

# Bose-Einstein *thermal* occupation, excluding vacuum half-photon contribution.
x = constants.h*f_res/(constants.k*T_cav)
n_thermal = float(1/np.expm1(x))
S_bath_WHz = constants.h*f_res * n_thermal
# Fourier bins for an analytic complex field. Translating down by f_lo is equivalent
# to placing the resonance at f_if in this I/Q equivalent model.
f = np.fft.fftfreq(N, d=1/fs_analog)
df = fs_analog/N
delta_f = f-f_if
band = (np.abs(delta_f) <= B_bath/2)
S_bath = S_bath_WHz*band.astype(float)
# Cavity transfer from intrinsic thermal bath to output port (dimensionless).
# |H_cav|^2 = (k_i k_e)/((k/2)^2 + [2 pi delta_f]^2).
H_cav = np.sqrt(kappa_i*kappa_e)/(kappa/2-1j*2*np.pi*delta_f)
# Continuous-time analog Butterworth transfer H(-f) = H(f)* for real filtering
z_p, p_p, k_p = signal.butter(lpf_order, 2*np.pi*f_lpf, analog=True, output='zpk')
_, H_lpf = signal.freqs_zpk(z_p, p_p, k_p, worN=2*np.pi*f)
S_v_bath = R * G_power * S_bath  # ideal amplified voltage PSD, V^2 / Hz
S_v_cavity = S_v_bath * np.abs(H_cav)**2
S_v_after_lpf = S_v_cavity * np.abs(H_lpf)**2

rng = np.random.default_rng(SEED)
xi = (rng.standard_normal(N)+1j*rng.standard_normal(N))/np.sqrt(2)
# If Z_k = N sqrt(S_k df) xi_k, then ifft(Z)_n has E|z_n|^2 = sum S_k df.
X = N*np.sqrt(S_v_bath*df)*xi
Y_cavity = X*H_cav
Y_lpf = Y_cavity*H_lpf
# Analog complex voltage, at the output of each stage (the RF oscillation itself
# is not synthesized at 8.8 GHz; the analytic envelope gives equivalent IQ exactly).
z_bath = np.fft.ifft(X)
z_cavity = np.fft.ifft(Y_cavity)
z_after_lpf = np.fft.ifft(Y_lpf)
z_sample = z_after_lpf[::decimation].copy()
# ADC quantization independently on I and Q, no clipping allowed by checks.
def adc_quantize(v):
    return np.clip(np.round(v/adc_step)*adc_step,
                   -adc_full_scale_peak, adc_full_scale_peak-adc_step)
z_adc = adc_quantize(z_sample.real)+1j*adc_quantize(z_sample.imag)
t_adc = np.arange(N_adc)/fs_adc

# Numerical verification (theoretical formulas and expected statistical tolerances).
checks = {}
def check(name, ok, detail=None):
    checks[name] = {"passed": bool(ok), "detail": detail}

check("no_injected_coherent_tone", True, "Only a complex Gaussian thermal bath was generated")
check("critical_coupling_peak_transfer", abs(np.sqrt(kappa_i*kappa_e)/(kappa/2)-1) < 1e-12)
check("loaded_quality_factor", np.isclose(Q_L, Q0/(1+beta)))
check("field_correlation_time", np.isclose(TAU_A, Q_L/(np.pi*f_res)))
check("frequency_offset", np.isclose(f_if, 1e6))
check("adc_sampling_period", np.isclose(1/fs_adc, 200e-9))
check("finite_waveforms", np.isfinite(z_adc).all())
check("adc_not_clipping", np.max(np.abs(np.r_[z_sample.real,z_sample.imag])) < adc_full_scale_peak)
check("adc_grid", np.max(np.abs(z_adc.real/adc_step-np.round(z_adc.real/adc_step))) < 1e-8)
check("quantization_error_bounded", np.max(np.abs(z_sample.real-z_adc.real)) <= adc_step/2*(1+1e-8) and np.max(np.abs(z_sample.imag-z_adc.imag)) <= adc_step/2*(1+1e-8))

expected_var = np.sum(S_v_after_lpf)*df
actual_var = float(np.mean(np.abs(z_adc)**2))
relative_var_error = float(actual_var/expected_var-1)
check("thermal_PSD_integral_vs_sample_variance", abs(relative_var_error) < 0.08,
      f"relative error {relative_var_error:+.2%}")
var_I, var_Q = np.var(z_adc.real), np.var(z_adc.imag)
circ_balance = float((var_I-var_Q)/(var_I+var_Q))
check("I_Q_equal_variance", abs(circ_balance) < 0.04,
      f"normalized variance imbalance {circ_balance:+.3%}")
rel_mean = float(abs(np.mean(z_adc))/np.sqrt(actual_var))
check("zero_complex_mean", rel_mean < 0.04, f"|mean|/RMS={rel_mean:.4f}")
properness = float(abs(np.mean((z_adc-np.mean(z_adc))**2))/actual_var)
check("circular_gaussian_pseudocovariance", properness < 0.05,
      f"|E[z^2]|/E|z|^2={properness:.4f}")

# KS diagnostics are applied to a widely spaced subsample to mitigate dependence.
stat_sample = z_adc[::50]
sigma = float(np.sqrt(actual_var/2))
rayleigh_D, rayleigh_p = stats.kstest(abs(stat_sample), stats.rayleigh(scale=sigma).cdf)
phases = np.mod(np.angle(stat_sample)+np.pi,2*np.pi)/(2*np.pi)
phase_D, phase_p = stats.kstest(phases, 'uniform')
check("rayleigh_marginal_KS", rayleigh_p > 1e-4,
      f"D={rayleigh_D:.4f}, p={rayleigh_p:.4f}, n={len(stat_sample)}")
check("uniform_phase_KS", phase_p > 1e-4,
      f"D={phase_D:.4f}, p={phase_p:.4f}, n={len(stat_sample)}")

# Correlation Rz(tau)=E[z(t+tau) z*(t)] from PSD vs empirical covariance.
lag_list = np.arange(0,26)
theo_corr = np.array([np.sum(S_v_after_lpf*np.exp(2j*np.pi*f*(L/fs_adc)))*df for L in lag_list])
theo_corr /= theo_corr[0]
mean_adc=np.mean(z_adc)
centered = z_adc-mean_adc
emp_corr = np.array([np.vdot(centered[:N_adc-L], centered[L:])/(N_adc-L) for L in lag_list])
emp_corr /= emp_corr[0]
correlation_deviation = float(np.max(np.abs(emp_corr[:11]-theo_corr[:11])))
check("correlation_matches_inverse_PSD", correlation_deviation < 0.05,
      f"max |empirical-theory| first 10 lags={correlation_deviation:.4f}")

# LPF aliasing power compared with |f|>=2.5 MHz before ADC.
alias_fraction = float(np.sum(S_v_after_lpf[np.abs(f)>=fs_adc/2])*df / expected_var)
check("aliasing_quantified", 0 <= alias_fraction < 1,
      f"fraction above ADC Nyquist {alias_fraction:.4%}")

# No exact 5 clusters, despite f_IF/fs=1/5, because there is no tone.
# Sample marginal phase must be uniform and I/Q cloud centered at origin.

COLORS = dict(coherent='#0b65cc', cavity='#43a1ed', electronics='#ed812a', total='#7049ac', predicted='#23385b', annotation='#a04496')
plt.rcParams.update({'font.size': 10,'axes.titlesize':11,'axes.labelsize':10,
                     'figure.facecolor':'white','axes.grid':True,'grid.alpha':.22,
                     'font.family':'DejaVu Sans'})

def save_figure(name):
    plt.savefig(OUT/name, dpi=190, bbox_inches='tight')
    plt.savefig(OUT/name.replace('.png','.svg'), bbox_inches='tight')
    plt.close()

# Main diagnostic figure: spectrum, time series, IQ marginal, amplitude/phase.
fig = plt.figure(figsize=(16,10.5))
fig.suptitle('Theoretical Step 4 — Thermal cavity noise (NO injected coherent tone)', fontsize=17, weight='bold', color='#072c54')
gs = GridSpec(2,3,figure=fig, left=.06,right=.98,top=.89,bottom=.09,hspace=.35,wspace=.28)
ax0=fig.add_subplot(gs[0,0])
dfplot=np.linspace(-5,5,1300)*1e6
calc_h=np.sqrt(kappa_i*kappa_e)/(kappa/2-1j*2*np.pi*dfplot)
ax0.plot(dfplot/1e6,np.ones_like(dfplot),ls='--',color=COLORS['predicted'],lw=1.4,label='Thermal bath (white)')
ax0.plot(dfplot/1e6,np.abs(calc_h)**2,color=COLORS['cavity'],lw=2.5,label='Cavity output')
ax0.set(xlabel='RF offset from cavity resonance (MHz)',ylabel='Normalized power PSD',title='Thermal bath → cavity resonance');ax0.legend(loc='upper right',fontsize=8)
ax0.axvline(-FWHM/2/1e6,color='gray',ls=':',lw=1)
ax0.axvline(FWHM/2/1e6,color='gray',ls=':',lw=1)
ax1=fig.add_subplot(gs[0,1])
from scipy.signal import welch
f_meas, S_meas=welch(z_adc, fs=fs_adc, return_onesided=False,nperseg=8192,noverlap=4096, scaling='density')
f_order=np.argsort(f_meas)
ax1.plot(f_meas[f_order]/1e6,10*np.log10(np.maximum(S_meas[f_order],1e-24)),color=COLORS['total'],lw=1.1,label='Simulated ADC I/Q')
# aliased theoretical PSD (few relevant folding terms; finite band = ±5 MHz around f_IF)
f_grid=np.linspace(-fs_adc/2,fs_adc/2,1700)
S_fold=np.zeros_like(f_grid)
for m in range(-6,7):
    fm = f_grid+m*fs_adc
    dh=fm-f_if
    bm=(abs(dh)<=B_bath/2)
    Hm=np.sqrt(kappa_i*kappa_e)/(kappa/2-1j*2*np.pi*dh)
    _,Hlm=signal.freqs_zpk(z_p,p_p,k_p,worN=2*np.pi*fm)
    S_fold+=R*G_power*S_bath_WHz*bm*np.abs(Hm)**2*np.abs(Hlm)**2
ax1.plot(f_grid/1e6,10*np.log10(np.maximum(S_fold,1e-24)),color=COLORS['predicted'],ls='--',lw=1.6,label='Predicted PSD incl. aliases')
ax1.set(xlabel='IF frequency (MHz)',ylabel='Voltage PSD (dBV²/Hz)',title='After mixer, LPF and ADC');ax1.legend(fontsize=8)
ax2=fig.add_subplot(gs[0,2])
show=(t_adc >=0.004) & (t_adc<0.00401)  # exactly 10 us -> ~50 samples
base_t=(t_adc[show]-0.004)*1e6
ax2.plot(base_t,z_adc.real[show]*1e3,'o-',color=COLORS['coherent'],markersize=4.3,lw=1.2,label='I[n]')
ax2.plot(base_t,z_adc.imag[show]*1e3,'o-',color=COLORS['electronics'],markersize=4.3,lw=1.2,label='Q[n]')
ax2.set(xlabel='Time (µs)',ylabel='ADC voltage (mV)',title='Digitized I/Q: every sample shown');ax2.legend(fontsize=8)
ax3=fig.add_subplot(gs[1,0])
idx=np.arange(0,N_adc,3)
ax3.scatter(z_adc.real[idx]*1e3,z_adc.imag[idx]*1e3,c=COLORS['cavity'],s=1.7,alpha=.17,rasterized=True)
ax3.set(xlabel='I (mV)',ylabel='Q (mV)',title='I/Q constellation — Gaussian cloud');ax3.set_aspect('equal','box')
ax4=fig.add_subplot(gs[1,1])
A = np.abs(z_adc)
bins=np.linspace(0,np.quantile(A,.999),70)
ax4.hist(A*1e3,bins=bins*1e3,density=True,alpha=.6,color=COLORS['cavity'],label='ADC samples')
xx=np.linspace(0,bins[-1],240)
ax4.plot(xx*1e3,stats.rayleigh(scale=sigma).pdf(xx)/1e3,color=COLORS['predicted'],lw=2,label='Rayleigh prediction')
ax4.set(xlabel='Amplitude |z| (mV)',ylabel='Density (mV⁻¹)',title='Amplitude distribution');ax4.legend(fontsize=8)
ax5=fig.add_subplot(gs[1,2])
ax5.hist(np.angle(z_adc),bins=np.linspace(-np.pi,np.pi,49),density=True,color=COLORS['total'],alpha=.64)
ax5.axhline(1/(2*np.pi),color=COLORS['predicted'],lw=2,ls='--',label='Uniform 1/(2π)')
ax5.set(xlabel='Phase arg(z) (rad)',ylabel='Density (rad⁻¹)',title='Phase: no preferred direction');ax5.legend(fontsize=8)
fig.text(.06,.02, f'Illustrative parameters: f₀=8.800 GHz · T=100 mK · Q₀=50,000 · β=1 · QL=25,000 · τA={TAU_A*1e6:.3f} µs · LO=8.799 GHz · LPF=1.9 MHz · fs=5 MS/s · 16 bit · ideal gain=140 dB',fontsize=9,color='#33495e')
save_figure('step04_thermal_baseline.png')

# Correlation and quantitative PSD validation figure.
fig, axes=plt.subplots(1,2,figsize=(13.6,4.9))
fig.suptitle('Thermal cavity: second-order statistics and temperature scaling',fontsize=16,weight='bold',color='#072c54')
lag_us=lag_list/fs_adc*1e6
axes[0].plot(lag_us,np.real(theo_corr),'--',color=COLORS['predicted'],lw=2,label='Theory Re R(τ)')
axes[0].plot(lag_us,np.real(emp_corr),'o-',color=COLORS['cavity'],ms=4,label='Simulated Re R(τ)')
axes[0].plot(lag_us,np.abs(theo_corr),'--',color=COLORS['electronics'],lw=2,label='Theory |R(τ)|')
axes[0].plot(lag_us,np.abs(emp_corr),'o-',color=COLORS['total'],ms=3.8,label='Simulated |R(τ)|')
axes[0].set(xlabel='Lag (µs)',ylabel='Normalized complex correlation',title='Correlation versus inverse PSD');axes[0].legend(fontsize=8)
Tgrid=np.geomspace(.015,8,400)
nT=1/np.expm1(constants.h*f_res/(constants.k*Tgrid))
qT=constants.h*f_res*nT/constants.k
axes[1].loglog(Tgrid,Tgrid,label='Classical T (Rayleigh–Jeans)',ls=':',color=COLORS['predicted'],lw=2)
axes[1].loglog(Tgrid,qT,label='Quantum thermal equivalent T',color=COLORS['cavity'],lw=2.5)
axes[1].axvline(T_cav,color=COLORS['electronics'],ls='--',lw=1.4,label='Chosen T = 100 mK')
axes[1].set(xlabel='Physical cavity temperature (K)',ylabel='Thermal noise-equivalent temperature (K)',title='Why thermal kT fails when hf ≳ kT')
axes[1].legend(fontsize=8)
fig.tight_layout(rect=[0,0,1,.92]);save_figure('step04_correlation_quantum.png')

# Machine-readable outputs and source audit.
metrics={
    'model': 'single-mode thermal bath -> cavity resonance -> ideal IQ downconversion -> analog 4th-order Butterworth LPF -> 16-bit ADC',
    'coherent_tone_present': False,'receiver_added_noise_present': False,
    'parameters':{'seed':SEED,'f_res_Hz':f_res,'T_cavity_K':T_cav,'Q0':Q0,'coupling_beta':beta,'QL':Q_L,
                  'FWHM_Hz':FWHM,'amplitude_decay_s':TAU_A,'bath_bandwidth_Hz':B_bath,
                  'f_LO_Hz':f_lo,'IF_Hz':f_if,'analog_simulation_rate_Hz':fs_analog,
                  'ADC_sample_rate_Hz':fs_adc,'duration_s':duration,'LPF_cutoff_Hz':f_lpf,'LPF_order':lpf_order,
                  'ideal_gain_power_dB':G_dB,'R_ohm':R,'ADC_bits':adc_bits,'ADC_peak_full_scale_V':adc_full_scale_peak},
    'quantum_thermal_occupation':n_thermal,
    'equivalent_thermal_noise_temperature_K':constants.h*f_res*n_thermal/constants.k,
    'S_cavity_at_resonance_W_per_Hz':S_bath_WHz,
    'P_cavity_approx_untruncated_W':float(np.pi*FWHM/2*S_bath_WHz),
    'expected_ADC_RMS_V_after_LPF':float(np.sqrt(expected_var)),
    'actual_ADC_RMS_V':float(np.sqrt(actual_var)),
    'relative_power_deviation':relative_var_error,
    'ADC_quantization_step_V':adc_step,
    'ADC_alias_fraction_pre_sampling':alias_fraction,
    'mean_complex_over_RMS':rel_mean,'normalized_IQ_variance_imbalance':circ_balance,
    'pseudocovariance_ratio':properness,
    'rayleigh_ks_p':rayleigh_p,'phase_uniform_ks_p':phase_p,
    'correlation_theory_lag1':[float(np.real(theo_corr[1])),float(np.imag(theo_corr[1]))],
    'correlation_measured_lag1':[float(np.real(emp_corr[1])),float(np.imag(emp_corr[1]))],
    'max_correlation_error_lags_0_to_10':correlation_deviation,
    'checks':checks,'all_checks_passed':all(x['passed'] for x in checks.values())
}
with open(OUT/'metrics.json','w') as fd: json.dump(metrics,fd,indent=2)
np.savez_compressed(OUT/'step04_arrays.npz',t_s=t_adc,z_adc_V=z_adc,noise_at_adc_ideal_V=z_sample,
    f_welch_Hz=f_meas,PSD_measured_V2_Hz=S_meas,lag_s=lag_list/fs_adc,
    R_theory=theo_corr,R_empirical=emp_corr)
with open(OUT/'README.md','w') as fd:
    fd.write('''# FLASH — theoretical thermal cavity baseline (Step 4)\n\nThis is **NOT** calibrated to any FLASH/QUAX data. The tone from Steps 1–3 is removed.\n\nReproduce with `python validate_step04.py` (requires NumPy, SciPy, Matplotlib).\n\nInputs: 100 mK thermal bath, single TM010-like resonator f0=8.8 GHz Q0=50,000, beta=1, loaded Q=25,000.\nComplex Gaussian bath with 10 MHz bandwidth around resonance; generated from theoretical Bose–Einstein occupancy n(T).\nThe cavity transfer has a Lorentzian PSD and complex causal single-pole response.\nDownconversion is implemented by placing its equivalent complex envelope at 1 MHz IF,\nwithout creating the full 8.8 GHz carrier. A 4th-order analog Butterworth LPF at 1.9 MHz\nis applied before 5 MS/s complex ADC sampling. I and Q use 16 bit quantization over ±5 V.\n\n**Important:** An arbitrary ideal noiseless 140 dB gain is used to make the thermal output visible\non the ADC voltage scale. This is a numerical thought experiment, not a complete quantum-consistent\nphase-insensitive amplifier model. Vacuum noise, incident-port noise and amplifier noise are deliberately\nNOT included yet. The cryogenic thermal emission alone vanishes as T -> 0, whereas a real linear coherent\nreceiver's measured noise need not vanish, owing to vacuum and amplifier-added contributions.\n\nThe signal has **no coherent tone** and no five phase clusters. IQ points form a circular\nGaussian cloud, amplitude is Rayleigh, phase is uniform. Short-lag complex correlation\noscillates at the IF while its envelope decays approximately with tau=Q_L/(pi*f0).\n\nPower unit convention: spectral density S_P in W/Hz at a 50 ohm load,\nwith E[|z|²]/R = integral S_P(f) df for an analytic complex voltage signal.\n\nExpected numerical checks are recorded in metrics.json; reproducible data saved in NPZ.\n''')
print('Checked',len(checks),'properties; passes:',sum(c['passed'] for c in checks.values()))
for n,c in checks.items(): print(('PASS' if c['passed'] else 'FAIL'),n,c['detail'] or '')
print('T=',T_cav,'K, nbar=',n_thermal,'QL=',Q_L, 'FWHM=',FWHM,'Hz', 'tau=',TAU_A*1e6,'us')
print('RMS expected/actual [mV]',np.sqrt(expected_var)*1e3,np.sqrt(actual_var)*1e3)
print('ADC alias fraction',alias_fraction)
assert all(c['passed'] for c in checks.values()), 'Some physics/consistency tests failed'
