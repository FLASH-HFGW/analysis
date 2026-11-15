"""Publish the verified 36-slide revision with distinct v19 artifact names."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,shutil,hashlib,sys
sys.path.insert(0,'/tmp/v18-python-deps')
import pptx
sys.path.insert(0,'/home/mazzitel/HFGW/analysis/reporting')
import slide_deck as sd
base=Path('/home/mazzitel/HFGW/analysis-work/Run2/reports/iq_noise_summary_v18')
out=base.with_name('iq_noise_summary_v19');out.mkdir(exist_ok=True)
shutil.copytree(base/'assets',out/'assets',dirs_exist_ok=True)
shutil.copytree(base/'data',out/'data',dirs_exist_ok=True)
deck=sd.Deck();deck.slides=json.loads((base/'slide_model.json').read_text())
assert len(deck.slides)==36
assert 'expected scale' in deck.slides[14]['title']
for slide in deck.slides:
 slide['footer']=slide.get('footer','IQ NOISE STUDY').replace('v18','v19')
 for item in slide['items']:
  if item['kind']=='image':
   src=Path(item['path']);dst=out/'assets'/src.name
   assert dst.is_file()
   item['path']=str(dst)
  if item['kind']=='text' and item['y']==.38:
   while len(sd.wrap(item['text'],item['w'],item['size']).splitlines())>1:item['size']-=1
sd.export(deck,out,'v19',datetime.now(ZoneInfo('Europe/Rome')).strftime('%-d %B %Y'))
(out/'data/v19_revision.json').write_text(json.dumps(dict(source=str(base),source_model_sha256=hashlib.sha256((base/'slide_model.json').read_bytes()).hexdigest(),slides=36,changes='Distinct v19 names for the verified expectations/fit/phase/temporal-coherence revision; scientific values unchanged.'),indent=2))
(out/'README.md').write_text('# IQ noise summary v19\n\n36 slides. Slide 12: expected thermal/receiver amplitude, phase and temporal coherence. Slide 15: Rayleigh scale comparison. Slide 16: measured/expected phase. Slide 21: measured/expected temporal covariance. Scientific values unchanged from the updated v18.\n')
