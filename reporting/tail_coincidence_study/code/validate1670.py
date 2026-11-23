"""Validate Run 1670 saved populations, exposures, clusters and archived timing."""
from collections import Counter
import json

import numpy as np

from change1670 import read
from diagnose1670 import MODES, N, RECEIPT, STUDY, save


def main():
    receipt=json.loads(RECEIPT.read_text())
    checks={}
    for key in ('complete','gzip_CRC','EOR','PPS_matches_ROOT'):
        checks[key]=receipt[key] is True
    checks['sample_count_and_serials']=receipt['samples']==N and receipt['serial_gaps']==0
    phase=read('phase')
    amplitude=read('amplitude')
    constellation=read('constellation')
    clusters=read('clusters')
    hits=read('T7_samples')
    traces=read('time_series')
    gaps=(0,2,5,8,10,25,50)
    for summary in read('summary'):
        mode=summary['mode']
        for bin_s in ('0.1','1.0'):
            subset=[r for r in traces if r['mode']==mode and r['nominal_bin_s']==bin_s]
            assert sum(int(r['samples']) for r in subset)==N
            for k in ('T3','T5','T7'):
                assert sum(int(r[k]) for r in subset)==int(summary[k])
            rms=np.sqrt(sum(float(r['RMS_V'])**2*int(r['samples']) for r in subset)/N)
            np.testing.assert_allclose(rms,float(summary['RMS_V']),rtol=1e-13)
        selected=[r for r in hits if r['mode']==mode]
        ix=[int(r['index']) for r in selected]
        assert len(ix)==int(summary['T7']) and ix==sorted(set(ix)) and ix[0]>=0 and ix[-1]<N
        for gap in gaps:
            assert sum(int(r['multiplicity']) for r in clusters if
                       r['mode']==mode and int(r['gap'])==gap)==len(ix)
        assert sum(int(r['count']) for r in constellation if r['mode']==mode)==N
        assert sum(int(r['count']) for r in amplitude if r['mode']==mode)==N
        assert sum(int(r['count']) for r in phase if r['mode']==mode and r['kind']=='phase')<=N
        # Express the exact binned survival using integer sample counts throughout.
        left=N
        for r in amplitude:
            if r['mode']==mode:
                r['observed_CCDF']=left/N
                left-=int(r['count'])
        assert left==0
        checks[f'{mode}_complete_populations']=True
    save('amplitude',amplitude)
    tuples=Counter((r['window_us'],r['kind']) for r in read('pairs'))
    shifts=read('time_shifts')
    for r in read('coincidence_summary'):
        key=r['window_us'],r['kind']
        observed=[int(s['count']) for s in shifts if (s['window_us'],s['kind'])==key]
        assert len(observed)==20 and tuples[key]==int(r['count'])
        np.testing.assert_allclose(np.mean(observed),float(r['shifted_mean']),rtol=1e-12)
    checks['sparse_coincidences_and_controls']=True
    assert all(checks.values())
    (STUDY/'validation/run1670/checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    print(checks)


if __name__=='__main__':
    main()
