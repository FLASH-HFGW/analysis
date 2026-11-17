"""Check source identities, fixed normalization, lag scales and presentation scope."""
from pathlib import Path
import json,hashlib,sys
import numpy as np,h5py
sys.path.insert(0,'/tmp/v18-python-deps')
from pptx import Presentation
REPO=Path(__file__).resolve().parents[2];WORK=REPO.parent/'analysis-work/Run2'
S=WORK/'simulation/presentation_steps1_6_v43';O=WORK/'reports/iq_noise_summary_v43_partI'
m=json.loads((S/'metrics.json').read_text());v=json.loads((O/'validation.json').read_text())
assert all(m['checks'].values())
old=json.loads((WORK/'simulation/presentation_steps1_6_v41/metrics.json').read_text())
assert m['configuration']==old['configuration']
assert m['metrics']==old['metrics']
for filename,digest in m['input_sha256'].items():assert hashlib.sha256(Path(filename).read_bytes()).hexdigest()==digest
for name in ['calibration_reconstruction','physical_parameters']:
 path=Path(m['configuration'][name]);assert hashlib.sha256(path.read_bytes()).hexdigest()==old['input_sha256'][str(path)]
with h5py.File(S/'short_examples.h5') as h:
 a=h['step3/analog_ADC_V'][:];b=h['step4/analog_ADC_V'][:];c=h['step5/analog_ADC_V'][:]
 assert np.array_equal(c,a+b)
 assert max(abs((c-a)-b))<1e-15
 assert set(h['step3/components'])=={'receiver'}
 for key in ['step3','step5','step6_TM010','step6_TM011','step6_TM012']:
  g=h[key+'/ADC_g1'][:51]
  r=v['correlation_zooms'][key];lo,hi=r['limits']
  assert np.all((g[1:].real>lo)&(g[1:].real<hi)&(g[1:].imag>lo)&(g[1:].imag<hi))
  assert r['sample_spacing_ns']==200
slides=json.loads((O/'slide_model.json').read_text());titles=[s['title'] for s in slides]
assert len(slides)==14
assert titles[2]=='Absolute normalization — From physical noise to ADC voltage'
assert titles[4]=='Step 1 — Coherent tone'
assert all('no gain fit' not in t.lower() and 'no data fits' not in t.lower() and 'step 7' not in t.lower() and 'step 8' not in t.lower() for t in titles)
assert len(Presentation(O/'iq_noise_summary_v43_partI.pptx').slides)==14
for s in slides:
 for item in s['items']:
  if item['kind']=='image':assert Path(item['path']).is_file()
  if item['kind']=='text':assert len(item['text'].splitlines())*item['size']*1.15/72<=item['h']+.13
print('PASS: source sum, residual, fixed physical parameters/calibration, source hashes, Re/Im zoom limits, 200 ns lags, 14-slide PPTX and scope.')
