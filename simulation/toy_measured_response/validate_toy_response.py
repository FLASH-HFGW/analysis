"""Toy simulation with measured DAQ response and an explicit gain-plane hypothesis."""
from pathlib import Path
import json,hashlib
import numpy as np,h5py
from scipy import constants,stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
AUDIT=Path('/home/mazzitel/HFGW/analysis-work/Run2/diagnostics/normalization_audit_20261114')
OLD=Path('/home/mazzitel/HFGW/analysis-work/Run2/simulation/step6/metrics.json')
OUT=Path('/home/mazzitel/HFGW/analysis-work/Run2/simulation/toy_measured_response');OUT.mkdir(parents=True,exist_ok=True)
A=OUT/'assets';A.mkdir(exist_ok=True)
cal=json.loads((AUDIT/'calibration_reconstruction.json').read_text());physical=json.loads(OLD.read_text());modes=physical['mode_results']
fs=50e6;fsadc=5e6;duration=.02;N=round(fs*duration);stride=10;freq=np.fft.fftfreq(N,1/fs);df=fs/N;lags=np.arange(51)/fsadc
R=50.;Tn=3.955;Gdb=67.4;G=10**(Gdb/10);seed=20261113
checks={};results={};arrays={}
def check(name,ok):
 checks[name]=bool(ok)
 if not ok:raise AssertionError(name)
def g1(z):
 z=z-z.mean();r=np.array([np.vdot(z[:len(z)-k],z[k:])/(len(z)-k) for k in range(51)]);return r/r[0]
for i,(mode,p) in enumerate(modes.items()):
 points=cal['curves'][mode];rf=np.array([x['rf_hz'] for x in points]);offset=cal['comparison'][mode]['rf_if_offset_hz']
 tone_if=rf-offset;kz=np.array([x['kz_integrated'] for x in points]);order=np.argsort(tone_if);tone_if=tone_if[order];kz=kz[order]
 response=np.interp(freq,tone_if,kz,left=0.,right=0.)
 # Measured response replaces, rather than multiplies, the former assumed LPF.
 ki=2*np.pi*p['f0_hz']/p['q0'];kt=ki*(1+p['kappa1']+p['kappa2']);f_if=1e6
 thermal=constants.h*p['f0_hz']/np.expm1(constants.h*p['f0_hz']/(constants.k*p['temperature_k']))
 Sc=thermal*ki**2*p['kappa2']/((kt/2)**2+(2*np.pi*(freq-f_if))**2)
 Sreceiver=np.full(N,constants.k*Tn)
 psd=R*G*(Sc+Sreceiver)*response**2
 power=float(psd.sum()*df);sigma=np.sqrt(power/2)
 rng=np.random.default_rng(seed+100*i);xi=(rng.standard_normal(N)+1j*rng.standard_normal(N))/np.sqrt(2)
 # Realization at the sampled IF; total process only, no asserted transfer phase.
 z=np.fft.ifft(N*np.sqrt(psd*df)*xi)[::stride];adc_lsb=4/65535
 counts=np.round(z.real/adc_lsb)+1j*np.round(z.imag/adc_lsb)
 clipped=np.mean((abs(counts.real)>32767)|(abs(counts.imag)>32767));check(mode+'_no_clipping',clipped==0)
 zadc=np.clip(counts.real,-32768,32767)*adc_lsb+1j*np.clip(counts.imag,-32768,32767)*adc_lsb
 theory=np.fft.ifft(psd)[np.arange(51)*stride];theory/=theory[0];measured=g1(zadc)
 actual=float(np.mean(abs(zadc)**2));check(mode+'_PSD_power',abs(actual/power-1)<.04);check(mode+'_covariance',np.max(abs(theory[:11]-measured[:11]))<.03)
 subset=zadc[::60];check(mode+'_Rayleigh',stats.kstest(abs(subset),stats.rayleigh(scale=sigma).cdf).statistic<.05);check(mode+'_phase',stats.kstest((np.angle(subset)+np.pi)/(2*np.pi),'uniform').statistic<.05)
 observed=p['observed_run680']['ac_rms_adc_v']*.4
 alias=float(psd[abs(freq)>=fsadc/2].sum()/psd.sum())
 low=abs(freq)<=2e6;tail=float(psd[~low].sum()/psd.sum())
 results[mode]=dict(f0_hz=p['f0_hz'],q0=p['q0'],kappa1=p['kappa1'],kappa2=p['kappa2'],ql=p['ql'],fwhm_hz=p['fwhm_hz'],tau_amplitude_s=p['tau_amplitude_s'],temperature_k=p['temperature_k'],sigma_adc_v=float(sigma),mean_amplitude_adc_v=float(sigma*np.sqrt(np.pi/2)),std_amplitude_adc_v=float(sigma*np.sqrt((4-np.pi)/2)),rms_adc_v=float(np.sqrt(power)),observed_ac_rms_adc_v=float(observed),model_to_measured_ac_rms=float(np.sqrt(power)/observed),coherence_lag1_real=float(theory[1].real),coherence_lag1_abs=float(abs(theory[1])),alias_fraction_within_sweep=alias,modeled_power_fraction_outside_2MHz=tail,calibration_IF_min_hz=float(tone_if[0]),calibration_IF_max_hz=float(tone_if[-1]),effective_kz_rms_over5MHz=float(np.sqrt(np.sum(response**2)*df/5e6)))
 arrays[mode]=dict(nominal_adc=zadc,g1_expected=theory,g1_simulated=measured,tone_if_hz=tone_if,kz_integrated=kz)
 # Values for both gain hypotheses are recorded, without data-driven scalar adjustment.
 results[mode]['rms_if_RF103_4_v']=float(np.sqrt(power)*10**(36/20))
# Presentation-ready expected distributions and per-mode measured comparison.
colors=['#007F86','#7657A6','#D98726'];fig,axs=plt.subplots(1,3,figsize=(13,3.5))
for (mode,r),col in zip(results.items(),colors):
 x=np.linspace(0,r['sigma_adc_v']*5,300);axs[0].plot(x*1e3,stats.rayleigh(scale=r['sigma_adc_v']).pdf(x)/1e3,color=col,label=mode)
 axs[2].plot(lags[1:]*1e6,abs(arrays[mode]['g1_expected'][1:]),color=col,label=mode)
axs[0].set(xlabel='Amplitude at ADC [mV]',ylabel='Density [mV⁻¹]',title='Expected Rayleigh amplitude');axs[0].legend(fontsize=8)
axs[1].axhline(1/(2*np.pi),color='#263952',lw=2);axs[1].set(xlim=(-np.pi,np.pi),ylim=(0,.2),xlabel='Phase [rad]',ylabel='Density [rad⁻¹]',title='Expected uniform phase')
axs[2].set(xlabel='Lag [μs]',ylabel='|g₁|',title='Expected temporal coherence');axs[2].legend(fontsize=8)
fig.tight_layout();fig.savefig(A/'toy_expected_observables.png',dpi=180);plt.close(fig)
report=dict(status='Toy simulation, conditional gain reference plane; not independently calibrated',RF_gain_assumption_db=Gdb,excluded_gain_db=36.,receiver_Tn_K=Tn,ADC_peak_V=2.,ADC_lsb_V=4/65535,fs_ADC_hz=fsadc,duration_s=duration,results=results,checks=checks,all_checks_passed=all(checks.values()),assumption='The DAQ calibration tone is injected upstream of the additional RF FET, so kz includes that 36 dB stage. Remaining upstream RF gain is 103.4−36=67.4 dB. Chosen as the physically specified alternative closer to observed data, not proven by that agreement.',normalization='Science samples: ADC range ±2 V, scale 4/65535. Calibration: ±5 V, scale10/65535. Calibrated noise power = corrected ADC FFT power / [50 Ω × kz(f)² × 10^(67.4/10)]. Hann noise ENBW corrected separately. kz uses integrated tone, not a scalloping-sensitive single bin.',open_question='Was the DAQ calibration tone injected before or after the additional 36 dB FET? Confirm the injection node and intervening losses.',limitations=['Both gain alternatives are tested; no gain optimized per mode.','The thesis prescription uses 103.4 dB plus kz; the 67.4 dB choice is an explicit alternative reference-plane hypothesis.','Transfer outside the measured approximately ±3 MHz sweep is set to zero; alias fraction covers modeled sweep only.','Response magnitude is measured; phase is not, so no causal transient response is asserted. Stationary covariance follows the PSD.','Remaining frequency/mode-dependent discrepancies are retained; no claim of exact agreement.','Receiver Tn is inherited from the thesis, not fitted or independently validated here.'])
report['input_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (AUDIT/'calibration_reconstruction.json',OLD,Path(__file__))}
(OUT/'metrics.json').write_text(json.dumps(report,indent=2))
with h5py.File(OUT/'toy_simulation.h5','w') as f:
 f.attrs['metadata_json']=json.dumps(report);f.create_dataset('lag_s',data=lags)
 for mode,values in arrays.items():
  g=f.create_group(mode)
  for name,v in values.items():g.create_dataset(name,data=v,compression='gzip')
print(json.dumps(results,indent=2));print('checks',len(checks),report['all_checks_passed'])
