"""Read-only numerical/provenance checks; render tiny PDFs only to verify Part I identity."""
from pathlib import Path
import csv,hashlib,json,subprocess,sys,tempfile,zipfile
import h5py
import numpy as np
sys.path.insert(0,'/tmp/v18-python-deps')
from pptx import Presentation
REPO=Path(__file__).resolve().parents[2];W=REPO.parent/'analysis-work/Run2';B=W/'reports/iq_noise_summary_v43_partI';O=W/'reports/iq_noise_summary_v44'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
v=json.loads((O/'validation.json').read_text());s=json.loads((O/'slide_model.json').read_text());old=json.loads((B/'slide_model.json').read_text())
assert len(s)==30 and s[:14]==old
assert len(Presentation(O/'iq_noise_summary_v44.pptx').slides)==30
info=subprocess.run(['pdfinfo',str(O/'iq_noise_summary_v44.pdf')],capture_output=True,text=True,check=True).stdout
assert any(line.split(':',1)[1].strip()=='30' for line in info.splitlines() if line.startswith('Pages:'))
for p,d in v['input_sha256'].items():assert sha(p)==d,p
with open(W/'simulation/step7/dc_longterm_diagnostic/longterm.csv') as f:rr=list(csv.DictReader(f))
assert len(rr)==780 and len({int(r['run']) for r in rr})==260
with h5py.File(W/'reports/noise_v2_development_20261109/run680_full_published/run00680_noise_v2.h5') as h:
 for mo in ['TM010','TM011','TM012']:
  r=next(r for r in rr if r['mode']==mo and int(r['run'])==680)
  assert float(r['physical_ADC_peak_V'])==2 and float(r['voltage_correction'])==.4
  assert np.isclose(float(r['total2_ADC_V2']),float(r['DC2_ADC_V2'])+float(r['AC2_ADC_V2']),rtol=1e-12)
  assert np.isclose(float(r['AC2_ADC_V2']),h[f'dc_removed/modes/{mo}/ac_squared_v2'][()]*.16,rtol=1e-12)
  assert h[f'modes/{mo}/noise_counts'][:].sum()==1048576000

with zipfile.ZipFile(B/'iq_noise_summary_v43_partI.pptx') as a,zipfile.ZipFile(O/'iq_noise_summary_v44.pptx') as b:
 for name in a.namelist():
  if name.startswith(('ppt/slides/','ppt/notesSlides/','ppt/media/')):assert a.read(name)==b.read(name),name
for i in range(1,15):assert sha(B/f'slide_{i:02d}.png')==sha(O/f'slide_{i:02d}.png')
for i in range(1,31):assert (O/f'slide_{i:02d}.png').is_file()
assert all(not v[key] for key in ['new_fits','new_simulations','new_raw_reads'])
for mo in ['TM010','TM011','TM012']:
 p=W/'simulation/toy_ODB_cal5_data2_LF_20261116/comparison'/f'{mo}_comparison.npz'
 with np.load(p) as a:
  lag=a['lag_s'];sel=(lag>0)&(lag<=10e-6)
  assert np.allclose(np.diff(lag),200e-9,rtol=0,atol=1e-18)
  for pop in ['data','toy']:
   for part,key in [('real','Re'),('imag','Im')]:
    x=getattr(a[pop+'_g1'],part)[sel];lo,hi=v['g1_positive_lag_zoom_limits'][mo][key];assert x.min()>lo and x.max()<hi
for n,slide in enumerate(s[14:],15):
 for item in slide['items']:
  if item['kind']=='text':assert len(item['text'].splitlines())*item['size']*1.15/72<=item['h']+.13,(n,item['text'])
  if item['kind']=='image':assert Path(item['path']).is_file()
for title in [x['title'] for x in s[14:]]:assert not any(word in title.lower() for word in ['step 7','step 8','splitter','high-pass','possible explanations'])
with tempfile.TemporaryDirectory(prefix='v44_pdf_identity_') as tmp:
 tmp=Path(tmp)
 for prefix,src in [('old',B/'iq_noise_summary_v43_partI.pdf'),('new',O/'iq_noise_summary_v44.pdf')]:
  subprocess.run(['pdftoppm','-f','1','-l','14','-scale-to','320','-png',str(src),str(tmp/prefix)],capture_output=True,check=True)
 a=sorted(tmp.glob('old-*.png'));b=sorted(tmp.glob('new-*.png'));assert len(a)==len(b)==14
 for x,y in zip(a,b):assert sha(x)==sha(y),(x.name,y.name)
print('PASS: 30 PDF/PPTX pages; approved Part I XML/media/notes and PDF pixels unchanged; input hashes; common normalization; all 200 ns samples and zoom limits; no new fits/simulations/raw reads; no Part IV.')
