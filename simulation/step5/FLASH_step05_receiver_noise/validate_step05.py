#!/usr/bin/env python3
"""Step 5 — incremental receiver-added input-referred noise, anchored to Step 4.

The physical cavity source and its *exact* sampled voltage from step04 are reused.
Receiver-added noise is an independent complex white Gaussian source injected AFTER
cavity transfer, referred to the pre-gain input (not a physical location of one component).
Both sources share a common *arbitrary theoretical* gain, IF LPF, and ADC.

This models equivalent receiver noise phenomenologically, NOT HEMT+TWPA stage physics.
"""
import json, shutil
from pathlib import Path
import numpy as np
from scipy import constants, signal, stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

OUT=Path(__file__).resolve().parent
SRC=OUT.parent/'FLASH_step04_thermal_model'
OUT.mkdir(parents=True,exist_ok=True)
STEP04=np.load(SRC/'step04_arrays.npz')
BASE_PARAMS=json.load(open(SRC/'metrics.json'))
p=BASE_PARAMS['parameters']
SEED=20261113
# Quoted from Valeria Spasiano master's thesis, section 6.1 and conclusion (p. 132)
T_add_K=3.955
T_add_unc_K=0.468
G_measured_dB=67.81
G_measured_unc_dB=0.39
# Do not silently replace step04's gain with experimental chain gain; fair comparison.
G_model_dB=p['ideal_gain_power_dB']
G_model_power=10**(G_model_dB/10)
R=p['R_ohm']; f_lpf=p['LPF_cutoff_Hz']; lpf_order=p['LPF_order']
fs_analog=p['analog_simulation_rate_Hz']; fs_adc=p['ADC_sample_rate_Hz']
T_s=1/fs_adc; ds=int(fs_analog/fs_adc)
t=STEP04['t_s']; N_adc=len(t); N=N_adc*ds; df=fs_analog/N
freq=np.fft.fftfreq(N,d=1/fs_analog)
# White equivalent receiver noise over ±5 MHz of complex IF band;
# choose wide enough to include LPF transition, not from cavity's narrow resonance.
B_elec=10e6
S_add_WHz=constants.k*T_add_K
support=np.abs(freq)<=B_elec/2
S_in=np.where(support, S_add_WHz, 0.)
S_elec_before_lp=R*G_model_power*S_in
z0,poles,k0=signal.butter(lpf_order,2*np.pi*f_lpf,output='zpk',analog=True)
_,H_lpf=signal.freqs_zpk(z0,poles,k0,worN=2*np.pi*freq)
S_elec_after_lpf=S_elec_before_lp*np.abs(H_lpf)**2
# Independently generated complex circular noise, normalized to stated absolute PSD
rng=np.random.default_rng(SEED)
xi=(rng.standard_normal(N)+1j*rng.standard_normal(N))/np.sqrt(2)
X_elec=N*np.sqrt(S_elec_before_lp*df)*xi
Y_elec=X_elec*H_lpf
# Equivalent input-referred receiver noise entering after cavity and through final LPF.
z_elec_analog=np.fft.ifft(Y_elec)
z_elec_sample=z_elec_analog[::ds].copy()
# Exactly the analog cavity waveform already used in Step 4
z_cav_sample=STEP04['noise_at_adc_ideal_V']
assert len(z_cav_sample)==N_adc
z_total_preADC=z_cav_sample+z_elec_sample
step=p['ADC_peak_full_scale_V']*2/(2**p['ADC_bits'])
peak=p['ADC_peak_full_scale_V']
def digitize(z):
    def q(x):return np.clip(np.round(x/step)*step,-peak,peak-step)
    return q(z.real)+1j*q(z.imag)
z_cav_adc=digitize(z_cav_sample)
z_elec_adc=digitize(z_elec_sample)
z_total_adc=digitize(z_total_preADC)
# The residual in the actual ADC is not exactly the separately quantized noise.
z_residual_adc=z_total_adc-z_cav_adc

# theory and quality tests
P_cav_theory=BASE_PARAMS['expected_ADC_RMS_V_after_LPF']**2
P_elec_theory=float(np.sum(S_elec_after_lpf)*df)
P_total_theory=P_cav_theory+P_elec_theory
P_cav=float(np.mean(abs(z_cav_sample)**2))
P_elec=float(np.mean(abs(z_elec_sample)**2))
P_total=float(np.mean(abs(z_total_preADC)**2))
P_total_adc=float(np.mean(abs(z_total_adc)**2))
cross=np.mean(z_cav_sample*np.conjugate(z_elec_sample))
frac_cav=P_cav_theory/P_total_theory
alias_fraction=float(np.sum(S_elec_after_lpf[np.abs(freq)>=fs_adc/2])*df/P_elec_theory)
checks={}
def check(name, passed, detail=''):
    checks[name]={'passed':bool(passed),'detail':detail}
check('step04_exact_analog_cavity_reused',np.array_equal(STEP04['noise_at_adc_ideal_V'],z_cav_sample))
check('step04_exact_quantized_cavity_reused',np.array_equal(STEP04['z_adc_V'],z_cav_adc),'No cavity regeneration or seed change')
check('no_coherent_tone',True,'No sinusoid generated in source code')
check('receiver_noise_after_cavity',True,'Independent Gaussian source is not multiplied by H_cavity')
check('same_ideal_gain',G_model_dB==p['ideal_gain_power_dB'])
check('same_sample_rate',fs_adc==5e6)
check('same_temperature_cavity',p['T_cavity_K']==0.100)
check('same_ADC_quantization', np.max(abs(z_total_adc.real/step-np.round(z_total_adc.real/step)))<1e-8)
check('no_adc_clipping',max(np.max(abs(z_total_preADC.real)),np.max(abs(z_total_preADC.imag)))<peak)
check('additive_before_adc',np.allclose(z_total_preADC-z_cav_sample,z_elec_sample,rtol=5e-12,atol=2e-15))
check('thermal_power_preserved',abs(P_cav/P_cav_theory-1)<.05,f'{P_cav/P_cav_theory-1:+.2%}')
check('electronics_power_from_PSD',abs(P_elec/P_elec_theory-1)<.03,f'{P_elec/P_elec_theory-1:+.2%}')
check('total_power_from_PSD',abs(P_total/P_total_theory-1)<.03,f'{P_total/P_total_theory-1:+.2%}')
check('cross_term_small',abs(2*np.real(cross))/P_total_theory<.012,f'cross/total={2*np.real(cross)/P_total_theory:+.3%}')
check('electronics_overwhelms_cavity',P_elec_theory>100*P_cav_theory)
check('receiver_is_white_before_LPF',np.all(S_elec_before_lp[support]==S_elec_before_lp[support][0]))
check('finite_ADC',np.isfinite(z_total_adc).all())
check('ADC_decomposition_error_bounded',max(np.max(abs((z_total_adc-z_cav_adc-z_elec_adc).real)),np.max(abs((z_total_adc-z_cav_adc-z_elec_adc).imag))) <= 2*step+1e-12)

# Marginals / complex correlation
z_center=z_total_adc-np.mean(z_total_adc)
P_center=np.mean(abs(z_center)**2)
proper=abs(np.mean(z_center*z_center))/P_center
imbalance=abs(np.var(z_center.real)-np.var(z_center.imag))/P_center
mean_over=np.abs(np.mean(z_total_adc))/np.sqrt(P_total_adc)
check('I_Q_same_variance',imbalance<.04,f'{imbalance:.4%}')
check('proper_complex_noise',proper<.04,f'{proper:.4f}')
check('mean_near_zero',mean_over<.03,f'{mean_over:.4f}')
# properly subsample to avoid falsely assuming independent adjacent samples
marg=z_total_adc[::60]
sigma=np.sqrt(P_total_adc/2)
D_amp,p_amp=stats.kstest(abs(marg),stats.rayleigh(scale=sigma).cdf)
D_phase,p_phase=stats.kstest((np.angle(marg)+np.pi)/(2*np.pi),'uniform')
check('Rayleigh_marginal_KS',p_amp>1e-4,f'p={p_amp:.4f}, N={len(marg)}')
check('uniform_phase_KS',p_phase>1e-4,f'p={p_phase:.4f}, N={len(marg)}')

# PSD and correlations, matched to the same window/time sampling.
S_cav_analog_theory=None  # step04 only archives ADC theoretical PSD moments and correlations
f_w, psd_cav=signal.welch(z_cav_adc,fs=fs_adc,nperseg=8192,noverlap=4096,return_onesided=False)
_,psd_ele=signal.welch(z_elec_adc,fs=fs_adc,nperseg=8192,noverlap=4096,return_onesided=False)
_,psd_all=signal.welch(z_total_adc,fs=fs_adc,nperseg=8192,noverlap=4096,return_onesided=False)
order=np.argsort(f_w)
lag=np.arange(35)
def corr(z):
    u=z-np.mean(z)
    vals=np.array([np.vdot(u[:len(u)-L],u[L:])/(len(u)-L) for L in lag])
    return vals/vals[0]
Rc=corr(z_cav_adc);Re=corr(z_elec_adc); Rt=corr(z_total_adc)
# Theory from sum of the two independently generated processes, at ADC lag spacing
S_cav_v_theory=np.zeros_like(freq)
f_if=p['IF_Hz']; f0=p['f_res_Hz']; Q0=p['Q0']; beta=p['coupling_beta']
k_i=2*np.pi*f0/Q0;k_e=beta*k_i;kappa=k_i+k_e
occ=1/np.expm1(constants.h*f0/(constants.k*p['T_cavity_K']))
S_cav_bath=constants.h*f0*occ
band_cav=np.abs(freq-f_if)<=p['bath_bandwidth_Hz']/2
Hc=np.sqrt(k_i*k_e)/(kappa/2-1j*2*np.pi*(freq-f_if))
S_cav_v_theory=R*G_model_power*S_cav_bath*band_cav*np.abs(Hc)**2*np.abs(H_lpf)**2
S_combined=S_cav_v_theory+S_elec_after_lpf
Rc_pred=np.array([np.sum(S_cav_v_theory*np.exp(2j*np.pi*freq*(L/fs_adc)))*df for L in lag]);Rc_pred/=Rc_pred[0]
Re_pred=np.array([np.sum(S_elec_after_lpf*np.exp(2j*np.pi*freq*(L/fs_adc)))*df for L in lag]);Re_pred/=Re_pred[0]
Rt_pred=np.array([np.sum(S_combined*np.exp(2j*np.pi*freq*(L/fs_adc)))*df for L in lag]);Rt_pred/=Rt_pred[0]
error_max=np.max(abs(Rt[:11]-Rt_pred[:11]))
check('autocorr_matches_theory',error_max<.025,f'max |delta| first 10 lags={error_max:.5f}')
check('alias_fraction_recorded',0<=alias_fraction<.1,f'{alias_fraction:.3%} of receiver pre-ADC noise > Nyquist')
check('PSD_step04_matches_saved_Welch',np.allclose(psd_cav,STEP04['PSD_measured_V2_Hz']))

C={'tone':'#0b65cc','cavity':'#43a1ed','electronics':'#ed812a','total':'#7049ac','prediction':'#263952','text':'#102c50'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':11,'axes.labelsize':10,
    'axes.grid':True,'grid.alpha':.25,'figure.facecolor':'white','savefig.facecolor':'white'})
def save(fig,name):
    fig.savefig(OUT/name,dpi=195,bbox_inches='tight')
    fig.savefig(OUT/name.replace('.png','.svg'),bbox_inches='tight')
    plt.close(fig)

# Figure 1: physical hierarchy and same-time, same-axes samples
fig=plt.figure(figsize=(17.0,10.4))
fig.suptitle('Step 5 — Thermal cavity emission + receiver-added noise (no coherent tone)',fontsize=18,fontweight='bold',color=C['text'])
gs=GridSpec(2,3,figure=fig,left=.055,right=.985,bottom=.095,top=.895,hspace=.35,wspace=.24)
ax=fig.add_subplot(gs[0,0])
# input-referred PSD in kelvin units (thermal cavity occupancy effective etc.)
offset=np.linspace(-2.5,2.5,1200)*1e6
Hoffset=np.sqrt(k_i*k_e)/(kappa/2-1j*2*np.pi*offset)
thermal_shape=(S_cav_bath/constants.k)*abs(Hoffset)**2
ax.plot(offset/1e6,thermal_shape,color=C['cavity'],lw=2.5,label='Thermal cavity contribution')
ax.axhline(T_add_K,color=C['electronics'],lw=2,label='Equivalent added noise (flat)')
ax.plot(offset/1e6,thermal_shape+T_add_K,color=C['total'],lw=2,label='Total (before LPF)')
ax.set(xlabel='Frequency offset from resonance (MHz)',ylabel='Input-referred noise PSD / kB (K)',title='Noise budget, referred to receiver input')
ax.legend(fontsize=8,loc='upper left')

ax=fig.add_subplot(gs[0,1])
eps=1e-20
for S,col,label,lw in [(psd_cav,C['cavity'],'Cavity only',2),(psd_ele,C['electronics'],'Receiver-added only',1.4),(psd_all,C['total'],'Total ADC',1.5)]:
    ax.plot(f_w[order]/1e6,10*np.log10(np.maximum(S[order],eps)),color=col,lw=lw,label=label)
ax.set(xlabel='Complex IF frequency (MHz)',ylabel='PSD (dBV²/Hz)',title='Digitized spectra: same exact sample window')
ax.legend(fontsize=8)

# time series: each sample marker visible; source colors are fixed; I solid and Q dashed/hollow
valid=(t>=.006)&(t<.006005)
xx=(t[valid]-.006)*1e6
for index,(arr,col,ttl) in enumerate([(z_cav_adc,C['cavity'],'Step 4 unchanged: cavity noise'),(z_total_adc,C['total'],'Step 5: cavity + electronics')]):
    ax=fig.add_subplot(gs[0,2] if index==0 else gs[1,0])
    ia=arr[valid].real;qa=arr[valid].imag
    ax.plot(xx,ia,marker='o',ms=5.2,mew=.75,mec='white',lw=1.15,color=col,label='I[n] (filled markers)')
    ax.plot(xx,qa,marker='o',ms=5.2,mfc='white',mec=col,mew=1.6,lw=1.1,ls='--',color=col,label='Q[n] (hollow markers)')
    ax.set(xlabel='Time (µs)',ylabel='Voltage (V)',title=ttl)
    ax.legend(fontsize=8,loc='upper right');ax.set_xlim(0,5)

ax=fig.add_subplot(gs[1,1])
idx=np.arange(0,N_adc,5)
ax.scatter(z_total_adc.real[idx],z_total_adc.imag[idx],s=2.7,alpha=.12,c=C['total'],label='Total ADC',rasterized=True)
ax.scatter(z_cav_adc.real[idx],z_cav_adc.imag[idx],s=2.6,alpha=.20,c=C['cavity'],label='Cavity only',rasterized=True)
ax.set(xlabel='I (V)',ylabel='Q (V)',title='IQ constellations — common axis scale')
ax.set_aspect('equal','box');ax.legend(fontsize=8,loc='upper right')

ax=fig.add_subplot(gs[1,2])
vals=abs(z_total_adc)
bins=np.linspace(0,np.quantile(vals,.9995),65)
ax.hist(vals,bins=bins,density=True,color=C['total'],alpha=.45,label='Total amplitude')
xx2=np.linspace(0,bins[-1],200)
ax.plot(xx2,stats.rayleigh(scale=sigma).pdf(xx2),lw=2,color=C['prediction'],label='Rayleigh (same RMS)')
ax.set(xlabel='Amplitude |z| (V)',ylabel='Probability density (V⁻¹)',title='Gaussian IQ → Rayleigh amplitude')
ax.legend(fontsize=8)
fig.text(.055,.028,f'Theory: cavity 100 mK, f₀=8.800 GHz, QL=25,000, beta=1  |  Receiver Tadd={T_add_K:.3f}±{T_add_unc_K:.3f} K (Valeria; no TWPA)  |  Same ideal 140 dB numerical gain  |  5 MS/s, 16 bit',fontsize=9,color=C['text'])
save(fig,'step05_signal_noise_budget.png')

fig, axes=plt.subplots(2,2,figsize=(15,9.5))
fig.suptitle('Step 5 — Phase statistics and correlation: unchanged cavity + added readout noise',fontsize=17,color=C['text'],weight='bold')
ax=axes[0,0]
for arr,c,label in [(z_cav_adc,C['cavity'],'Cavity'),(z_elec_adc,C['electronics'],'Electronic'),(z_total_adc,C['total'],'Total')]:
    ax.hist(np.angle(arr[::40]),bins=np.linspace(-np.pi,np.pi,50),density=True,histtype='step',lw=1.8,color=c,label=label)
ax.axhline(1/(2*np.pi),color=C['prediction'],ls='--',label='Uniform')
ax.set(xlabel='Phase arg(z) (rad)',ylabel='Probability density (rad⁻¹)',title='No preferred absolute phase');ax.legend(fontsize=8)
ax=axes[0,1]
for Rarr,col,label in [(Rc,C['cavity'],'Cavity'),(Re,C['electronics'],'Electronics'),(Rt,C['total'],'Total')]:
    ax.plot(lag*T_s*1e6,abs(Rarr),'.-',lw=1.8,ms=5,color=col,label=label)
ax.plot(lag*T_s*1e6,abs(Rt_pred),color=C['prediction'],ls='--',lw=1.5,label='Total: from PSD')
ax.set(xlabel='Lag (µs)',ylabel='|R(τ)| / R(0)',title='Temporal correlation (complex magnitude)');ax.legend(fontsize=8)
ax=axes[1,0]
for Rarr,col,label in [(Rc,C['cavity'],'Cavity'),(Re,C['electronics'],'Electronics'),(Rt,C['total'],'Total')]:
    ax.plot(lag*T_s*1e6,np.real(Rarr),'.-',lw=1.5,ms=3.5,color=col,label=label)
ax.set(xlabel='Lag (µs)',ylabel='Re R(τ) / R(0)',title='Real-part correlations');ax.legend(fontsize=8)
ax=axes[1,1]
ax.bar(['Cavity','Electronics','Total'],[np.sqrt(P_cav),np.sqrt(P_elec),np.sqrt(P_total)],color=[C['cavity'],C['electronics'],C['total']])
ax.set(ylabel='Analog RMS (V)',title='Power adds; RMS does not')
for i,(y,v) in enumerate(zip([np.sqrt(P_cav),np.sqrt(P_elec),np.sqrt(P_total)],[P_cav,P_elec,P_total])):
    ax.text(i,y+.017,f'{y:.4f} V',ha='center',fontsize=10)
fig.text(.06,.012, f'Equivalent electronics PSD: kB × Tadd. Tadd is input-referred, NOT the cavity temperature. The measured {G_measured_dB:.2f} dB amplifier gain is reported but NOT used in this controlled Step-4 comparison.',fontsize=9,color=C['text'])
fig.tight_layout(rect=(0,.045,1,.94));save(fig,'step05_phase_correlation.png')

# output metrics and reproducible arrays
output={'model':'Step4 thermal cavity + post-cavity lumped input-referred Gaussian receiver added noise -> common LPF -> ADC',
        'tone_present':False,'cavity_temperature_K':p['T_cavity_K'],
        'reference_thesis':{'source':'Valeria Spasiano, QUAX@LNF master thesis, dedicated no-TWPA configuration; conclusion p.132',
               'T_add_input_referred_K':T_add_K,'T_add_uncertainty_K':T_add_unc_K,
               'gain_measured_dB':G_measured_dB,'gain_measured_uncertainty_dB':G_measured_unc_dB,
               'note':'Tn of a specific measured configuration, used here only as indicative model parameter'},
        'numerical_setup':{'seed_cavity':p['seed'],'seed_electronics':SEED,
               'gain_dB_unmodified_from_step04':G_model_dB,'B_electronics_Hz':B_elec,
               'ADC_bits':p['ADC_bits'],'ADC_fs_Hz':fs_adc,'LPF_Hz':f_lpf,
               'ADC_peak_full_scale_V':peak,'ADC_step_V':step},
        'noise_rms_voltage':{'cavity_analog':np.sqrt(P_cav),'receiver_analog':np.sqrt(P_elec),
               'total_analog':np.sqrt(P_total),'total_ADC':np.sqrt(P_total_adc)},
        'noise_power':{'cavity_expected':P_cav_theory,'receiver_expected':P_elec_theory,
               'total_expected':P_total_theory,'cavity_power_fraction':frac_cav},
        'stats':{'electronic_noise_Nyquist_alias_fraction_pre_ADC':alias_fraction,
              'correlation_lag1_cavity':[Rc[1].real,Rc[1].imag],
              'correlation_lag1_receiver':[Re[1].real,Re[1].imag],
              'correlation_lag1_total':[Rt[1].real,Rt[1].imag],
              'max_corr_error_lags0to10':error_max,
              'phase_KS_p':p_phase,'rayleigh_KS_p':p_amp},
        'tests':checks,'tests_passed':sum(x['passed'] for x in checks.values()),'tests_total':len(checks),
        'all_passed':all(x['passed'] for x in checks.values())}

def json_safe(v):
    if isinstance(v,(np.floating,np.integer)):return v.item()
    if isinstance(v,complex):return [v.real,v.imag]
    raise TypeError(str(type(v)))
with open(OUT/'metrics.json','w') as fo:json.dump(output,fo,indent=2,default=json_safe)
np.savez_compressed(OUT/'step05_arrays.npz', t_s=t,z_cavity_adc_V=z_cav_adc,
    z_cavity_preADC_V=z_cav_sample,z_electronics_preADC_V=z_elec_sample,
    z_electronics_adc_if_digitized_separately_V=z_elec_adc,
    z_total_preADC_V=z_total_preADC,z_total_adc_V=z_total_adc,
    z_ADC_difference_total_minus_cavity_V=z_residual_adc,
    f_IF_fft_Hz=f_w,PSD_cavity_V2Hz=psd_cav,PSD_electronics_V2Hz=psd_ele,PSD_total_V2Hz=psd_all,
    lags_s=lag*T_s,corr_cavity=Rc,corr_electronics=Re,corr_total=Rt,corr_theory_total=Rt_pred)
shutil.copy2(SRC/'step04_arrays.npz',OUT/'step04_reference_arrays.npz')
shutil.copy2(SRC/'metrics.json',OUT/'step04_reference_metrics.json')
(OUT/'README.md').write_text(f'''# FLASH Step 5 — receiver noise added to Step 4 thermal cavity\n\n**Reproduce:** `python validate_step05.py` (requires numpy, scipy, matplotlib).\nThe script expects a sibling directory `FLASH_step04_thermal_model/` containing the exact original step04 `step04_arrays.npz` and `metrics.json`.\n\nNo coherent tone in either scenario. Cavity thermal signal exactly reused from Step 4, sample by sample.\n\n### Nominal parameters\n- Single-mode *theoretical* cavity: 8.8 GHz, T=100 mK, Q0=50,000, beta=1.\n- Receiver-added equivalent noise temperature: Tadd={T_add_K} ± {T_add_unc_K} K; **indicative** from Spasiano thesis, dedicated configuration without TWPA, p. 132.\n- Thesis reports measured gain {G_measured_dB} ± {G_measured_unc_dB} dB, **not applied** here: changing it would destroy the controlled Step 4 comparison. The model retains Step 4's arbitrary ideal 140 dB gain.\n- Added noise source is a white *complex* Gaussian process, input-referred PSD S_add = kB Tadd W/Hz, over [-5,+5] MHz at complex IF, added after cavity response but before the shared 4th-order 1.9 MHz analog LPF.\n- The same 5 MS/s, 16-bit ADC is used, with ±5 V nominal range.\n- All source colors fixed: cavity cyan, receiver electronics orange, total purple. I has filled and Q hollow sample markers.\n\n### Important limits\nThis is a **lumped equivalent-input** receiver noise source, not a model of individual HEMT, TWPA, FET, mixer losses or quantization noise temperature. The thesis' Tn is a characteristic of a particular experimental setup, used as an illustrative prior and not assumed applicable to actual run conditions.\nThe gain 140 dB is purely numerical and does not match the measured 67.81 dB. Tadd often already includes vacuum effects as seen by the receiver; adding another half-photon now would risk double-counting.\nA PSD of **kB Tadd** is used as a classical equivalent noise temperature parameter for this thought experiment; this is not an independent microscopic quantum fluctuation model.\nAn ideal 4th-order LPF is not sufficient to eliminate all >2.5 MHz power: the alias fraction is quantified and retained as a limitation.\nQuantization is applied only once to the sum. Separate quantized components do not add sample-by-sample without an error of order LSB.\n\nMachine-readable datasets and test outcomes are in `step05_arrays.npz` and `metrics.json`.\n''')
for n,c in checks.items():print(('PASS' if c['passed'] else 'FAIL'),n,c['detail'])
print('Summary:',len(checks),sum(c['passed'] for c in checks.values()),'passed')
print('Tadd=',T_add_K,'K RMS electronics=',np.sqrt(P_elec),'RMS cavity=',np.sqrt(P_cav),'RMS total=',np.sqrt(P_total),'alias=',alias_fraction)
assert output['all_passed'],'Tests failed; do not publish as validated'
