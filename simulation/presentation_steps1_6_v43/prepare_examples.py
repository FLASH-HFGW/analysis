"""Reorganize existing short realizations only; no random draws or new simulation."""
from pathlib import Path
import hashlib,json
import numpy as np,h5py
from scipy.fft import fft,ifft
REPO=Path(__file__).resolve().parents[2]
WORK=REPO.parent/'analysis-work/Run2'
SRC=WORK/'simulation/presentation_steps1_6_v41'
OUT=WORK/'simulation/presentation_steps1_6_v43'
OUT.mkdir(parents=True,exist_ok=True)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def covariance(z,nlag=501):
 a=z-z.mean();n=len(a)
 return ifft(abs(fft(a,2*n))**2)[:nlag]/(n-np.arange(nlag))
source_hash=digest(SRC/'short_examples.h5');m=json.loads((SRC/'metrics.json').read_text());cfg=m['configuration'];fs=cfg['fs_hz'];checks={}
with h5py.File(SRC/'short_examples.h5','r') as src,h5py.File(OUT/'short_examples.h5','w') as dst:
 for key in src:
  if key!='step3':src.copy(key,dst)
 receiver=src['step5/components/receiver'][:];thermal=src['step4/analog_ADC_V'][:];total=src['step5/analog_ADC_V'][:]
 step=2*cfg['ADC_peak_V']/cfg['ADC_counts_denominator']
 q=(np.round(receiver.real/step)+1j*np.round(receiver.imag/step))*step
 assert max(abs(receiver.real).max(),abs(receiver.imag).max())<cfg['ADC_peak_V']-step
 S=src['step5/PSD_expected_ADC_V2_Hz'][:]-src['step4/PSD_expected_ADC_V2_Hz'][:]
 assert S.min()>=0
 g=dst.create_group('step3')
 for key,z in [('analog_ADC_V',receiver),('quantized_ADC_V',q),('PSD_expected_ADC_V2_Hz',S),('components/receiver',receiver)]:g.create_dataset(key,data=z,compression='gzip')
 for label,z in [('analog',receiver),('ADC',q)]:
  co=covariance(z);g.create_dataset(label+'_g1',data=co/co[0].real)
 P=fs*S.mean()
 for key,v in {'expected_total_power_V2':P,'expected_sigma_q_V':np.sqrt(P/2),'tone_power_V2':0.,'ADC_zero_fraction':np.mean(abs(q)==0),'MC_analog_power_V2':np.mean(abs(receiver)**2),'MC_ADC_power_V2':np.mean(abs(q)**2),'ADC_valid_phase_samples':np.count_nonzero(abs(q)>0)}.items():g.attrs[key]=v
 residual=total-receiver;err=residual-thermal
 diag=dst.create_group('diagnostics');diag.create_dataset('step5_minus_step3_analog_ADC_V',data=residual,compression='gzip')
 cr=covariance(receiver);ct=covariance(thermal);cs=covariance(total)
 weight=(cr+ct)/(cr[0].real+ct[0].real)
 for key,z in [('receiver_covariance',cr),('thermal_covariance',ct),('total_covariance',cs),('power_weighted_g1',weight),('finite_realization_cross_covariance',cs-cr-ct)]:diag.create_dataset(key,data=z)
 checks['step3_exact_receiver_of_step5']=bool(np.array_equal(g['analog_ADC_V'][:],dst['step5/components/receiver'][:]))
 checks['step4_exact_thermal_of_step5']=bool(np.array_equal(thermal,dst['step5/components/cavity'][:]))
 checks['step5_exact_analog_source_sum']=bool(np.array_equal(total,receiver+thermal))
 checks['step5_quantized_once']=bool(np.array_equal(dst['step5/quantized_ADC_V'][:],(np.round(total.real/step)+1j*np.round(total.imag/step))*step))
 checks['residual_agrees_with_step4_float_tolerance']=bool(np.max(abs(err))<1e-15)
 checks['step6_TM010_unchanged']=bool(np.array_equal(total,dst['step6_TM010/analog_ADC_V'][:]))
 for key in ['step1','step2','step4','step5','step6_TM010','step6_TM011','step6_TM012']:
  checks[key+'_preserved_arrays']=all(np.array_equal(src[key][name][:],dst[key][name][:]) for name in ['analog_ADC_V','quantized_ADC_V','PSD_expected_ADC_V2_Hz','analog_g1','ADC_g1'])
 checks['no_tone_or_injected_noise_in_steps3_6']=all(set(dst[key]['components'])<=set(['receiver','cavity']) and dst[key].attrs['tone_power_V2']==0 for key in ['step3','step4','step5','step6_TM010','step6_TM011','step6_TM012'])
 notes={'residual_max_abs_error_V':float(abs(err).max()),'residual_RMS_error_V':float(np.sqrt(np.mean(abs(err)**2))),'thermal_RMS_V':float(np.sqrt(np.mean(abs(thermal)**2))),'receiver_sample_power_V2':float(cr[0].real),'thermal_sample_power_V2':float(ct[0].real),'weighted_sum_vs_total_max_g1_difference':float(np.max(abs(weight-cs/cs[0].real))),'explanation':'Independent-source ensemble covariance adds; a finite shared realization retains cross-covariance. No cross term was removed or fitted.'}
assert all(checks.values());assert digest(SRC/'short_examples.h5')==source_hash
m['reference_input_sha256']=m['input_sha256'].copy()
m.update(schema='flash-partI-v43-reused-realizations',checks=checks,all_checks_passed=True,diagnostics=notes,preparation='No new draws: reuse v41; step3 is existing receiver alone; original step5 quantizes exact source sum once.',input_sha256={str(SRC/'short_examples.h5'):source_hash,str(SRC/'metrics.json'):digest(SRC/'metrics.json')},reference_planes={**m['reference_planes'],'validation':'steps1–2 only: coherent probe and optional controlled injected noise','science':'steps3–6: validation sources OFF; receiver alone, wall alone, then sum and three modes'})
(OUT/'metrics.json').write_text(json.dumps(m,indent=2)+'\n')
print(json.dumps({'checks':checks,'diagnostics':notes},indent=2))
