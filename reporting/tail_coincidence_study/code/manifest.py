"""Hash local deliverables and record provenance without staging binary products."""
from pathlib import Path
import hashlib,json,subprocess
O=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=[]
for folder in ['code','data','tables','figures','presentation','validation']:
 for p in sorted((O/folder).glob('*')):
  if not p.is_file() or p.name in ['manifest.json','git_receipt.json'] or p.suffix in ['.log','.npz']:continue
  files.append(dict(path=str(p.relative_to(O)),bytes=p.stat().st_size,sha256=sha(p),local_only=folder=='presentation' or p.name=='pilot1429_binned_statistics.csv'))
m=dict(branch='run2-run3-pilot-design-20261122',inventory_commit='6135b2863cd5493ecf79d0fa4d104a2922e232dc',source_parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=O,text=True).strip(),renderer='reporting/slide_deck.py',renderer_sha256=sha(O.parent/'slide_deck.py'),raw_passes=[1429],other_runs_scope='ROOT metadata and archived statistics/PSD; gzip headers only',input_metadata='data/inventory.json',frozen_thresholds='data/frozen_thresholds.json',validation='validation/REPORT.md',files=files)
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
