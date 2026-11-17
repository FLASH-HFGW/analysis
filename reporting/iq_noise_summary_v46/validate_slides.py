"""Read-only validation of frozen slides, analytical identities and campaign scope."""
from pathlib import Path
import hashlib,json,re,subprocess,sys,tempfile,zipfile
import h5py,numpy as np
sys.path.insert(0,'/tmp/v18-python-deps')
from pptx import Presentation
REPO=Path(__file__).resolve().parents[2]
W=REPO.parent/'analysis-work/Run2';O=W/'reports/iq_noise_summary_v46';B=W/'reports/iq_noise_summary_v45';C=W/'diagnostics/resonance_reference_campaign_v5_20261117';P=W/'diagnostics/resonance_bank_pilot_v1_20261117'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=json.loads((O/'slide_model.json').read_text());old=json.loads((B/'slide_model.json').read_text());v=json.loads((O/'validation.json').read_text());r=json.loads((C/'results.json').read_text());provenance=json.loads((O/'slide_provenance.json').read_text())
assert len(s)==v['slides']==49 and s[:24]==old[:24]
assert len(Presentation(O/'iq_noise_summary_v46.pptx').slides)==49
info=subprocess.run(['pdfinfo',str(O/'iq_noise_summary_v46.pdf')],capture_output=True,text=True,check=True).stdout
assert re.search(r'Pages:\s+49',info)
assert not v['new_raw_reads'] and not v['new_simulations'] and not v['new_physical_fits'] and v['PartIV']==0 and v['normalization_unchanged']
for path,digest in {**r['input_sha256'],**v['input_sha256']}.items():assert sha(path)==digest,path
# Original native slides, relationships, notes and each related image are unchanged.
with zipfile.ZipFile(B/'iq_noise_summary_v45.pptx') as a,zipfile.ZipFile(O/'iq_noise_summary_v46.pptx') as b:
 for i in range(1,25):
  for name in [f'ppt/slides/slide{i}.xml',f'ppt/slides/_rels/slide{i}.xml.rels',f'ppt/notesSlides/notesSlide{i}.xml',f'ppt/notesSlides/_rels/notesSlide{i}.xml.rels']:
   if name in a.namelist():assert a.read(name)==b.read(name),name
  import xml.etree.ElementTree as ET
  rels=ET.fromstring(a.read(f'ppt/slides/_rels/slide{i}.xml.rels'))
  for rel in rels:
   if rel.attrib.get('Type','').endswith('/image'):
    name='ppt/'+rel.attrib['Target'].replace('../','');assert a.read(name)==b.read(name),name
for i in range(1,25):assert sha(B/f'slide_{i:02d}.png')==sha(O/f'slide_{i:02d}.png')
# The final PDF, not only copied previews, must preserve all approved page pixels.
with tempfile.TemporaryDirectory(prefix='v46_identity_') as tmp:
 tmp=Path(tmp)
 for prefix,src in [('old',B/'iq_noise_summary_v45.pdf'),('new',O/'iq_noise_summary_v46.pdf')]:
  subprocess.run(['pdftoppm','-f','1','-l','24','-scale-to','320','-png',str(src),str(tmp/prefix)],check=True,capture_output=True)
 aa=sorted(tmp.glob('old-*.png'));bb=sorted(tmp.glob('new-*.png'));assert len(aa)==len(bb)==24
 for a,b in zip(aa,bb):assert sha(a)==sha(b),(a.name,b.name)
assert r['coordinate_audit']['included_n']==253
assert r['coordinate_audit']['quarantined_runs']==[691,692,743,746,876,894,921]
assert not r['coordinate_audit']['sign_correction_applied'] and not r['coordinate_audit']['reflection_is_proven']
with h5py.File(C/'expectations_and_campaign.h5') as h,h5py.File(P/'run00680_resonance.h5') as pilot:
 valid=h['valid_signed_coordinate_mask'][:];assert valid.sum()==253
 for m in ['TM010','TM011','TM012']:
  rr=r['modes'][m];group=h[m+'/analytic_reference']
  np.testing.assert_allclose(group['thermal_power_ADC_V2'][:]+group['electronic_power_ADC_V2'][:],group['total_power_ADC_V2'][:],rtol=1e-14)
  np.testing.assert_allclose(np.array(rr['toy_sigma_q_ADC_V'])**2*2,group['total_power_ADC_V2'][:],rtol=1e-14)
  assert rr['integration_refinement_max_relative_difference']<1e-4
  assert r['validation'][m]['selected_max_abs_power_error_percent']<.11
  for bi in range(7):
   tg=group[f'band_{bi:02d}'];power=group['total_power_ADC_V2'][bi]
   assert np.isclose(tg['output_PSD_ADC_V2_Hz'][:].sum()*250000/16384,power,rtol=1e-7)
   assert np.isclose(tg['output_Welch_expected_ADC_V2_Hz'][:].sum()*250000/16384,power,rtol=1e-7)
   assert abs(tg['g1'][0]-1)<1e-12 and np.max(abs(tg['g1'][:]))<=1+1e-12
   np.testing.assert_allclose(np.diff(tg['lag_s'][:]),4e-6,atol=1e-18)
   pg=pilot[f'filter_banks/resonance_ROI/modes/{m}/band_{bi:02d}']
   # Distinct stored FFT orders must be handled by their own frequencies.
   assert np.sort(tg['output_frequency_hz'][:]).tolist()==pg['PSD_frequency_baseband_hz'][:].tolist()
for p in provenance:
 if p['slide'] in range(25,29):assert p['section']=='II' and p['run_ids']==[680]
 if p['title'].startswith(('Resonance bands','Resonance-band')) and p['section']=='III':assert p['run_ids']==r['coordinate_audit']['included_runs']
 for fig in p.get('figures',[]):assert Path(fig).exists()
print('PASS:49slides;first24PDF pixels and PPTX scientific parts unchanged;21 analytic FIR powers/spectra/covariances;253 valid resonance runs with seven explicit exclusions;260 historical runs;all frozen input hashes;no raw/simulation/physical fit/PartIV.')
