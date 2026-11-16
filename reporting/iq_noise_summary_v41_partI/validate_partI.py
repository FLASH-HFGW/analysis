"""Read-only validation of normalization, shared examples and presentation scope."""
from pathlib import Path
import json,sys,hashlib
import numpy as np,h5py
sys.path.insert(0,'/tmp/v18-python-deps');from pptx import Presentation
R=Path('/home/mazzitel/HFGW/analysis-work/Run2');S=R/'simulation/presentation_steps1_6_v41';O=R/'reports/iq_noise_summary_v41_partI';meta=json.loads((S/'metrics.json').read_text());cfg=meta['configuration'];old=json.loads((R/'simulation/toy_ODB_cal5_data2_LF_20261116/metrics.json').read_text());checks={}
def check(name,ok):
 checks[name]=bool(ok)
 if not ok:raise AssertionError(name)
check('all_31_simulation_checks',meta['all_checks_passed'] and len(meta['checks'])==31)
check('short_only',cfg['samples_per_example']/cfg['fs_hz']<.1)
check('physical_gain_no_display_factor',cfg['RF_gain_db']==103.4 and cfg['LF_data_over_cal_amplitude']==.01)
check('correct_ADC_range_and_coding',cfg['ADC_peak_V']==2 and cfg['ADC_counts_denominator']==65535)
for mode,p in meta['metrics'].items():
 check(mode+'_absolute_budget_matches_existing_reference',abs(p['total_RMS_expected_ADC_V']**2/old['results'][mode]['expected_power_v2']-1)<1e-5)
with h5py.File(S/'short_examples.h5') as h:
 check('step5_step6_exact_ADC',np.array_equal(h['step5/quantized_ADC_V'][:],h['step6_TM010/quantized_ADC_V'][:]))
 for label in ['step4','step5','step6_TM010','step6_TM011','step6_TM012']:check(label+'_tone_absent',h[label].attrs['tone_power_V2']==0 and 'tone' not in h[label+'/components'])
 check('thermal_below_ADC_step_not_artificially_amplified',h['step4'].attrs['ADC_zero_fraction']>.98 and np.sqrt(h['step4'].attrs['expected_total_power_V2'])<4/65535)
 step=4/65535
 for label in ['step1','step2','step3','step4','step5','step6_TM010','step6_TM011','step6_TM012']:
  z=h[label+'/analog_ADC_V'][:];q=h[label+'/quantized_ADC_V'][:]
  check(label+'_component_sum_preserved',np.allclose(z,sum(h[label+'/components/'+key][:] for key in h[label+'/components']),rtol=1e-12,atol=1e-16))
  check(label+'_ADC_grid',np.max(abs(q.real/step-np.rint(q.real/step)))<1e-9)
prs=Presentation(O/'iq_noise_summary_v41_partI.pptx');check('PartI_10slides_only',len(prs.slides)==10)
for i,s in enumerate(prs.slides):
 check('slide_'+str(i+1)+'_in_bounds',all(sh.left>=0 and sh.top>=0 and sh.left+sh.width<=prs.slide_width+10000 and sh.top+sh.height<=prs.slide_height+10000 for sh in s.shapes))
for path,expected in meta['input_sha256'].items():check('unchanged_input_'+Path(path).name,hashlib.sha256(Path(path).read_bytes()).hexdigest()==expected)
report=dict(status='passed',checks=checks,total=len(checks),simulation_checks=len(meta['checks']),no_new_fits=True,no_full_run_simulation=True,no_measured_raw_reconstruction=True)
(O/'validation.json').write_text(json.dumps(report,indent=2));print('VALIDATED',len(checks),'checks +',len(meta['checks']),'simulation checks')
