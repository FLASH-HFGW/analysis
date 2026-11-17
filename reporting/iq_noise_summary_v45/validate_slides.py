"""Read-only validation of population separation, table calculations and Part I identity."""
from pathlib import Path
import csv,hashlib,json,subprocess,sys,tempfile,zipfile
import numpy as np,h5py
sys.path.insert(0,'/tmp/v18-python-deps')
from pptx import Presentation
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO/'reporting'));import slide_deck as sd
W=REPO.parent/'analysis-work/Run2';B=W/'reports/iq_noise_summary_v43_partI';O=W/'reports/iq_noise_summary_v45';C=W/'reports/iq_noise_summary_v17/data/v2_campaign'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
 with open(p) as f:return list(csv.DictReader(f))
v=json.loads((O/'validation.json').read_text());s=json.loads((O/'slide_model.json').read_text());old=json.loads((B/'slide_model.json').read_text());p=json.loads((O/'slide_provenance.json').read_text());d=json.loads((O/'derived_from_existing_tables.json').read_text())
assert len(s)==34 and s[:14]==old
assert len(Presentation(O/'iq_noise_summary_v45.pptx').slides)==34
info=subprocess.run(['pdfinfo',str(O/'iq_noise_summary_v45.pdf')],capture_output=True,text=True,check=True).stdout
assert any(line.split(':',1)[1].strip()=='34' for line in info.splitlines() if line.startswith('Pages:'))
for name,digest in v['input_sha256'].items():assert sha(name)==digest,name
with zipfile.ZipFile(B/'iq_noise_summary_v43_partI.pptx') as a,zipfile.ZipFile(O/'iq_noise_summary_v45.pptx') as b:
 for name in a.namelist():
  if name.startswith(('ppt/slides/','ppt/notesSlides/','ppt/media/')):assert a.read(name)==b.read(name),name
for i in range(1,15):assert sha(B/f'slide_{i:02d}.png')==sha(O/f'slide_{i:02d}.png')
assert len(p)==20
for x in p[:10]:assert x['section']=='II' and x['run_ids']==[680] and x['toy_comparison']
for x in p[10:]:assert x['section']=='III' and x['run_ids']==list(range(680,940)) and not x['toy_comparison']
# None of the original pooled experimental figures can enter the single-run chapter.
for x in p[:10]:
 for image in x['figures']:assert not any(t in Path(image).name for t in ['exp_IQ_quadratures_amplitude','campaign','nine_band','longterm','threshold_rates'])
for i,slide in enumerate(s[14:],15):
 assert len(sd.wrap(slide['source'],11.8,7.5).splitlines())==1,i
 for item in slide['items']:
  if item['kind']=='text':assert len(item['text'].splitlines())*item['size']*1.15/72<=item['h']+.13,(i,item['text'])
  if item['kind']=='image':assert Path(item['path']).is_file()
assert v['PartIV']==0 and not v['new_raw_reads'] and not v['new_simulations'] and not v['new_physical_fits']
# Recalculate the allowed table-only statistical controls independently.
rr=rows(W/'simulation/step7/dc_longterm_diagnostic/longterm.csv');trend=rows(C/'trend_diagnostics.csv');cr=rows(C/'dc_ac_temperature_by_run.csv')
mo=['TM010','TM011','TM012'];g={m:sorted([r for r in rr if r['mode']==m],key=lambda r:int(r['run'])) for m in mo};arr=lambda r,k:np.array([float(x[k]) for x in r]);time=arr(g[mo[0]],'time_unix');clock=(time-time.mean())/time.std();X=np.column_stack([np.ones(len(clock)),clock]);res=lambda y:y-X@np.linalg.lstsq(X,y,rcond=None)[0]
for m in mo:
 assert len(g[m])==260
 power=arr(g[m],'AC2_ADC_V2')*1e6
 for sensor in [15,16,17]:
  temp=arr(g[m],f't{sensor}_mK');actual=d['temperature_correlations'][m+'_'+str(sensor)];assert np.isclose(actual['r_raw'],np.corrcoef(temp,power)[0,1],atol=1e-12);assert np.isclose(actual['r_after_linear_time'],np.corrcoef(res(temp),res(power))[0,1],atol=1e-12)
  saved=next(r for r in trend if r['mode']==m and r['metric']=='ac_squared_v2' and int(r['sensor'])==sensor);assert np.isclose(actual['r_after_linear_time'],float(saved['r_temperature_after_linear_time']),atol=1e-10)
assert d['band_coordinates']['configuration_centers_hz']==[0,0,0]
assert d['band_coordinates']['nominal_width_hz']==50000
assert np.isclose(d['band_coordinates']['ENBW_hz'],47428.80681855164,atol=1e-8)
for m in mo:
 fif=d['band_coordinates']['cavity_nominal_final_IF_hz'][m];intervals=d['band_coordinates']['intervals'][m];assert len(intervals)==9
 for r in intervals:
  assert r['nominal_upper_IF_hz']-r['nominal_lower_IF_hz']==50000
  assert r['nominal_center_detuning_hz']==r['center_IF_hz']-fif
 assert max(r['nominal_upper_IF_hz'] for r in intervals)<fif
 assert all(v['band_power_checks'][m].values())
# Source-normalization checksum equality rather than a data-tuned scale.
full=json.loads((W/'simulation/toy_ODB_cal5_data2_LF_20261116/metrics.json').read_text());short=json.loads((W/'simulation/presentation_steps1_6_v43/metrics.json').read_text())
assert full['RF_gain_db']==short['configuration']['RF_gain_db']==103.4
assert full['LF_kz_amplitude_factor']==short['configuration']['LF_data_over_cal_amplitude']==.01
assert full['ADC_peak_V']==short['configuration']['ADC_peak_V']==2
for key in ['physical_parameters','calibration_reconstruction']:
 name=short['configuration'][key];assert sha(name)==full['input_sha256'][name]
with tempfile.TemporaryDirectory(prefix='v45_pdf_identity_') as tmp:
 tmp=Path(tmp)
 for prefix,src in [('old',B/'iq_noise_summary_v43_partI.pdf'),('new',O/'iq_noise_summary_v45.pdf')]:subprocess.run(['pdftoppm','-f','1','-l','14','-scale-to','320','-png',str(src),str(tmp/prefix)],capture_output=True,check=True)
 aa=sorted(tmp.glob('old-*.png'));bb=sorted(tmp.glob('new-*.png'));assert len(aa)==len(bb)==14
 for a,b in zip(aa,bb):assert sha(a)==sha(b),(a.name,b.name)
print('PASS:34slides;PartI PDF pixels/PPTX parts unchanged;run680-only PartII;260-run-only PartIII;correct band IF/detunings/ENBW and powers;temperature controls match saved coefficients;normalization/input hashes unchanged;no raw reads/simulation/physical fit/PartIV.')
