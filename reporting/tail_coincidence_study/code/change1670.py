"""One-second familywise exploratory scans with two contiguous block sizes."""
import csv
import json
from collections import defaultdict

import numpy as np
from scipy.stats import spearmanr

from diagnose1670 import MODES, STUDY, TABLES, FS, RECEIPT, save


def read(name):
    with (TABLES/f'{name}.csv').open() as stream:
        return list(csv.DictReader(stream))


def scores(x):
    n=len(x)
    splits=np.arange(20,n-19)
    left=np.cumsum(x,axis=0)[splits-1]
    contrast=abs(left)*np.sqrt(n/(splits*(n-splits)))[:,None]
    candidates=contrast.argmax(axis=0)
    ramp=np.arange(n,dtype=float)-(n-1)/2
    drift=abs(ramp@x)/np.linalg.norm(ramp)
    return contrast.max(axis=0), splits[candidates], drift


def main():
    statement=json.loads(RECEIPT.read_text())
    assert statement['complete'] and statement['gzip_CRC'] and statement['PPS_matches_ROOT']
    variables = ('mean_I_V','mean_Q_V','RMS_V','var_I_V2','var_Q_V2',
                 'cov_I_Q_V2','properness_ratio','T7','phase_mean_cos','phase_mean_sin')
    sec = [r for r in read('time_series') if float(r['nominal_bin_s'])==1 and int(r['samples'])==FS]
    psd=read('spectral_seconds')
    spectral=read('line_seconds')
    keys, rows = [], []
    for mode in MODES:
        q=[r for r in sec if r['mode']==mode]
        assert len(q)==209
        for k in variables:
            keys.append((mode,k)); rows.append([float(r[k]) for r in q])
        for label,source in [('full_band_PSD_V2', [float(r['power_V2']) for r in psd if r['mode']==mode]),
                             ('line_ratio', [float(r['normalized_ratio']) for r in spectral if
                             r['mode']==mode and r['kind']==('new_IF' if mode=='TM012' else 'mode_reference')])]:
            keys.append((mode,label)); rows.append(source)
    raw=np.transpose(rows)
    keep=raw.std(axis=0)>0
    raw,keys=raw[:,keep],[k for k,good in zip(keys,keep) if good]
    x=(raw-raw.mean(axis=0))/raw.std(axis=0)
    observed,splits,trend=scores(x)
    result=[]
    for block in (5,10):
        rng=np.random.default_rng(1670+block)
        blocks=[np.arange(i,min(i+block,len(x))) for i in range(0,len(x),block)]
        null=[]
        for _ in range(999):
            order=np.concatenate([blocks[j] for j in rng.permutation(len(blocks))])
            step, _, drift=scores(x[order])
            null.append(max(step.max(),drift.max()))
        null=np.array(null)
        for j,(mode,name) in enumerate(keys):
            at=splits[j]
            result.append(dict(mode=mode,observable=name,block_s=block,split_s=int(at),
                  step_score=observed[j],mean_before=raw[:at,j].mean(),mean_after=raw[at:,j].mean(),
                  trend_score=trend[j],familywise_step_fraction=(1+sum(null>=observed[j]))/1000,
                  familywise_trend_fraction=(1+sum(null>=trend[j]))/1000))
    save('change_scan',result)
    q=[int(r['T7']) for r in sec if r['mode']=='TM012']
    r=[float(r['normalized_ratio']) for r in spectral if r['mode']=='TM012' and r['kind']=='new_IF']
    z=[float(r['RMS_V']) for r in sec if r['mode']=='TM012']
    assoc=dict(seconds=209,TM012_line_T7_spearman=float(spearmanr(q,r).statistic),
               TM012_line_RMS_spearman=float(spearmanr(z,r).statistic),
               method='Exploratory rank coefficients; no iid inference. Block permutations preserve short-range dependence within blocks only.',
               tested_series=len(keys),permutations=999,blocks_s=[5,10],
               test_family='maximum over standardized abrupt splits (20 seconds per side), linear trend, and all retained observables/modes')
    (STUDY/'validation/run1670/change_scan.json').write_text(json.dumps(assoc,indent=2)+'\n')
    print(assoc)


if __name__=='__main__':
    main()
