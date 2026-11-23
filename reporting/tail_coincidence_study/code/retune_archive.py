"""Read the missing full-band screens and the ROOT-only retune controls."""
import json
from pathlib import Path
import time

import numpy as np
from scipy.ndimage import median_filter

from retune_spectra import screen
from stream_longitudinal import MODES, STUDY, csv_write, open_product


def main():
    selection = json.loads((STUDY/'data/longitudinal_selection.json').read_text())
    selected = {r['run']: r for r in selection['selected']}
    folder = STUDY/'tables/retune'
    folder.mkdir(exist_ok=True)
    resources = []
    root_dir = Path(selected[1446]['root_path']).parent
    for run in (1429, 1446, 1463, 1480, 1669, 1670, 1671):
        modes = MODES if run in selected else ('TM012',)
        root_path = (Path(selected[run]['root_path']) if run in selected
                     else root_dir/f'run{run:05d}_iq_v3.1.root')
        start = time.monotonic()
        rows = []
        with open_product(root_path) as p:
            assert p.run == run and p.fs == 5e6 and str(p.metadata['iq_convention']) == 'I-iQhardware'
            frequency = p.edges[:-1]+p.widths/2
            lo = json.loads(p.metadata['bor_lo_json'])
            lo_total = lo['freq RS']+lo['freq Teled Ch2']
            assert lo_total == (8845843000 if run < 1670 else 8845854000), lo
            for mode in modes:
                wp = p.file[f'spectra/{mode}/window_psd'][:].astype(float)
                assert wp.shape == (209, 50000)
                mean = wp.mean(axis=0)
                background = np.maximum(median_filter(mean, size=201, mode='nearest'), 1e-30)
                use = abs(frequency) >= 100000
                scale = np.median(wp[:,use]/background[use], axis=1)
                rows.extend(screen(mode,frequency,wp,background,scale))
            requested = p.file.file.file.source.num_requested_bytes
        csv_write(folder/f'{run}_full_band_lines.csv', list(rows[0]), rows)
        resources.append(dict(run=run, source=str(root_path), modes=list(modes),
                              raw_streamed=False, root_requested_bytes=requested,
                              wall_s=time.monotonic()-start, LO_TM012_total_Hz=lo_total,
                              LO_primary_Hz=lo['freq RS'], LO_secondary_TM012_Hz=lo['freq Teled Ch2']))
        print(run, requested, flush=True)
    (STUDY/'validation/retune_archive.json').write_text(json.dumps(resources,indent=2)+'\n')


if __name__ == '__main__':
    main()
