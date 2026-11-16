"""Short, common-input examples; preserves every historical simulation/product.

Calibration examples1–3 use a known port1 probe (step1 bypasses the cavity),
then actual port1→port2 response. Examples4–6 switch validation sources OFF.
All use the identical measured readout mapping, absolute gain and ADC.
"""
from pathlib import Path
import json,hashlib
import numpy as np,h5py
from scipy.fft import fft,ifft
HERE=Path(__file__).resolve().parent;cfg=json.loads((HERE/'parameters.json').read_text());O=Path(cfg['output']);O.mkdir(parents=True,exist_ok=True)
phys=json.loads(Path(cfg['physical_parameters']).read_text())['mode_results'];cal=json.loads(Path(cfg['calibration_reconstruction']).read_text())
n=cfg['samples_per_example'];fs=cfg['fs_hz'];f=np.fft.fftfreq(n,1/fs);t=np.arange(n)/fs;R=cfg['resistance_ohm'];G=10**(cfg['RF_gain_db']/20);step=2*cfg['ADC_peak_V']/cfg['ADC_counts_denominator'];checks={};results={};metrics={}
def check(name,ok):
 checks[name]=bool(ok)
 if not ok:raise AssertionError(name)
def quantize(z):
 ci=np.round(z.real/step);cq=np.round(z.imag/step)
 check('no_clipping_'+str(len(checks)),np.all((ci>=-32768)&(ci<=32767)&(cq>=-32768)&(cq<=32767)))
 q=(np.clip(ci,-32768,32767)+1j*np.clip(cq,-32768,32767))*step
 check('half_LSB_error_'+str(len(checks)),max(abs((q-z).real).max(),abs((q-z).imag).max())<=step/2+1e-14)
 return q
for mi,(mode,p) in enumerate(phys.items()):
 pts=cal['curves'][mode];offset=cal['comparison'][mode]['rf_if_offset_hz'];xx=np.array([q['rf_hz']-offset for q in pts]);kk=np.array([q['kz_integrated'] for q in pts])*.01;ix=np.argsort(xx);xx=xx[ix];kk=kk[ix]
 kfun=lambda ff:np.interp(ff,xx,kk,left=0,right=0)
 fif=p['f0_hz']-cfg['primary_LO_hz']-cfg['secondary_LO_hz'][mode];ki=2*np.pi*p['f0_hz']/p['q0'];k1=ki*p['kappa1'];k2=ki*p['kappa2'];kt=ki+k1+k2;theta=6.62607015e-34*p['f0_hz']/np.expm1(6.62607015e-34*p['f0_hz']/(1.380649e-23*p['temperature_k']))
 rngc=np.random.default_rng(cfg['seed_cavity_and_probe']+100*mi);rnge=np.random.default_rng(cfg['seed_receiver']+100*mi)
 Xc=np.zeros(n,complex);Xe=np.zeros(n,complex);Xp=np.zeros(n,complex);Sc=np.zeros(n);Se=np.zeros(n);Sp=np.zeros(n)
 for alias in [-1,0,1]:
  af=f+alias*fs;readout=G*kfun(af);det=af-fif
  # Stable causal pole under numpy's forward exp(-i*omega*t) convention.
  Hbath=np.sqrt(ki*k2)/(kt/2+2j*np.pi*det);H12=np.sqrt(k1*k2)/(kt/2+2j*np.pi*det)
  xi=(rngc.standard_normal(n)+1j*rngc.standard_normal(n))/np.sqrt(2);eta=(rnge.standard_normal(n)+1j*rnge.standard_normal(n))/np.sqrt(2)
  # Identical underlying cavity/probe draws shared across corresponding stages.
  ac=np.sqrt(n*fs*R*theta)*readout*Hbath;ae=np.sqrt(n*fs*R*1.380649e-23*cfg['receiver_Tn_K'])*readout;ap=np.sqrt(n*fs*R*1.380649e-23*cfg['validation_injected_noise_equivalent_K'])*readout*H12
  Xc+=ac*xi;Xe+=ae*eta;Xp+=ap*xi;Sc+=abs(ac)**2/(n*fs);Se+=abs(ae)**2/(n*fs);Sp+=abs(ap)**2/(n*fs)
 cavity=ifft(Xc);receiver=ifft(Xe);probe_noise=ifft(Xp);total=cavity+receiver
 mu_tone=np.sqrt(R*10**((cfg['validation_probe_dBm']-30)/10))*G*kfun(fif);tone=mu_tone*np.exp(2j*np.pi*fif*t+.37j);H0=np.sqrt(k1*k2)/(kt/2);through=tone*H0
 if mode=='TM010':
  stages=[('step1',tone,{'tone':tone},np.zeros(n),abs(mu_tone)**2),('step2',through+probe_noise,{'tone':through,'injected':probe_noise},Sp,abs(mu_tone*H0)**2),('step3',through+probe_noise+receiver,{'tone':through,'injected':probe_noise,'receiver':receiver},Sp+Se,abs(mu_tone*H0)**2),('step4',cavity,{'cavity':cavity},Sc,0.),('step5',total,{'cavity':cavity,'receiver':receiver},Sc+Se,0.)]
  for label,z,components,S,tonepower in stages:results[label]=dict(z=z,adc=quantize(z),components=components,S=S,tonepower=tonepower)
 results['step6_'+mode]=dict(z=total,adc=quantize(total),components={'cavity':cavity,'receiver':receiver},S=Sc+Se,tonepower=0.)
 pred=float(fs*np.mean(Sc+Se));meas=float(np.mean(abs(total)**2));check(mode+'_total_power_PSD',abs(meas/pred-1)<.025);check(mode+'_cavity_power_PSD',abs(np.mean(abs(cavity)**2)/(fs*np.mean(Sc))-1)<.08)
 metrics[mode]=dict(final_IF_hz=fif,physical_temperature_K=p['temperature_k'],f0_hz=p['f0_hz'],q0=p['q0'],ql=p['ql'],kappa1=p['kappa1'],kappa2=p['kappa2'],tau_cavity_us=p['tau_amplitude_s']*1e6,thermal_RMS_expected_ADC_V=float(np.sqrt(fs*np.mean(Sc))),receiver_RMS_expected_ADC_V=float(np.sqrt(fs*np.mean(Se))),total_RMS_expected_ADC_V=float(np.sqrt(pred)),total_RMS_MC_ADC_V=float(np.sqrt(meas)),sigma_q_expected_ADC_V=float(np.sqrt(pred/2)),tone_bypass_ADC_V=float(mu_tone),tone_cavity_ADC_V=float(mu_tone*H0))
check('step5_exactly_step6_TM010_analog',np.array_equal(results['step5']['z'],results['step6_TM010']['z']))
check('step5_exactly_step6_TM010_ADC',np.array_equal(results['step5']['adc'],results['step6_TM010']['adc']))
check('step3_receiver_shared_with_step5',np.array_equal(results['step3']['components']['receiver'],results['step5']['components']['receiver']))
check('step2_probe_shared_with_step3',np.array_equal(results['step2']['components']['injected'],results['step3']['components']['injected']))
with h5py.File(O/'short_examples.h5','w') as h:
 h.create_dataset('time_s',data=t);h.create_dataset('frequency_hz',data=f)
 for label,r in results.items():
  g=h.create_group(label);z=r['z'];adc=r['adc'];S=r['S'];P=float(fs*np.mean(S)+r['tonepower']);sigma=np.sqrt(P/2)
  g.create_dataset('analog_ADC_V',data=z,compression='gzip');g.create_dataset('quantized_ADC_V',data=adc,compression='gzip');g.create_dataset('PSD_expected_ADC_V2_Hz',data=S,compression='gzip')
  for name,v in r['components'].items():g.create_dataset('components/'+name,data=v,compression='gzip')
  for prefix,a in [('analog',z),('ADC',adc)]:
   centered=a-a.mean();nn=len(a);cov=ifft(abs(fft(centered,2*nn))**2)[:501]/(nn-np.arange(501));v=float(cov[0].real)
   g.create_dataset(prefix+'_g1',data=cov/v if v>0 else np.full(501,np.nan,dtype=complex))
  g.attrs['expected_total_power_V2']=P;g.attrs['expected_sigma_q_V']=sigma;g.attrs['tone_power_V2']=r['tonepower'];g.attrs['ADC_zero_fraction']=float(np.mean(abs(adc)==0));g.attrs['MC_analog_power_V2']=float(np.mean(abs(z)**2));g.attrs['MC_ADC_power_V2']=float(np.mean(abs(adc)**2));g.attrs['ADC_valid_phase_samples']=int(np.count_nonzero(abs(adc)>0))
  if label.startswith('step6') or label in ('step4','step5'):
   check(label+'_noise_no_coherent_tone',r['tonepower']==0.)
  if label=='step4':print('THERMAL_ONLY',dict(g.attrs),flush=True)
report=dict(status='complete',configuration=cfg,duration_s=n/fs,metrics=metrics,checks=checks,all_checks_passed=all(checks.values()),reference_planes={'source':'matched complex RMS-equivalent voltage; E|z|²/R = available noise power','readout':'RF103.4dB times measured integrated-tone kz/100; no extra LPF','validation':'steps1–3: known injected port1 probe and controlled injected noise; step1 cavity bypass; steps2/3 actual port1→2 response','science':'steps4–6: validation sources OFF; intrinsic wall bath and optional equivalent receiver source','ADC':'z=I-iQhardware; Qeff=Im(z); science±2V with4/65535V/count; calibration kz already±5V'},assumptions=['ReceiverTn common, inherited no-TWPA measurement; not proven run-matched per mode.','LF20/60 amplitude ratio0.01 assumes unchanged response shape.','Scalar readout, no IQ imbalance or DC offsets injected.','No hypothetical LF high-pass or step7/8 correction.','Short stationary frequency-domain examples; not full-run reanalysis.','Causal cavity phase convention explicit; scalar measured readout phase is unknown and chosen zero for stationary synthesis.','Quantization nonlinear: thermal-only ADC does not necessarily retain Gaussian/Rayleigh statistics; no artificial display gain.'],input_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'parameters.json',Path(cfg['physical_parameters']),Path(cfg['calibration_reconstruction'])]})
(O/'metrics.json').write_text(json.dumps(report,indent=2));print(json.dumps(metrics,indent=2));print('CHECKS',sum(checks.values()),'/',len(checks))
