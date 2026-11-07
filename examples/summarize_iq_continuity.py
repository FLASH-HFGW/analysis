#!/usr/bin/env python3
"""Audit completed continuity repairs against original run statistics."""
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
BASE=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/noise_continuous')

def summarize():
    report={'requested_runs':260,'corrected_runs':0,'missing_runs':[],
            'amplitude_conclusion':'amplitude moments, thresholds and sample exceedance counts unchanged in every corrected run',
            'modes':{m:{'added_pairs':{str(l):0 for l in (1,10,100)},'joined_local_episodes':{str(k):0 for k in (3,5,7)},
                        'max_circular_moment_change':{str(l):0. for l in (1,10,100)}} for m in ('TM010','TM011','TM012')}}
    for run in range(680,940):
        p=BASE/'by_run'/f'{run:05d}'/f'run{run:05d}_noise.json'
        if not p.exists():report['missing_runs'].append(run);continue
        new=json.loads(p.read_text());old=json.loads((Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/job_to_submit_noise')/f'{run:05d}'/p.name).read_text())
        assert new['global_statistics']['schema']==2 and new['reached_eof']
        assert new['samples']==old['samples'] and new['events']==old['events']
        for mode,acc in report['modes'].items():
            a,b=(d['global_statistics']['modes'][mode] for d in (old,new))
            for key in ('n','mean','m2','valid_phase','thresholds_v'):assert a[key]==b[key],(run,mode,key)
            for kind,stats in b['exceedances'].items():
                for k,ep in stats.items():
                    for key in ('samples_above','duration_samples','peak_v'):assert ep[key]==a['exceedances'][kind][k][key]
            for k in acc['joined_local_episodes']:
                acc['joined_local_episodes'][k]+=a['exceedances']['local'][k]['episodes']-b['exceedances']['local'][k]['episodes']
            for lag in acc['added_pairs']:
                x,y=a['delta_circular'][lag],b['delta_circular'][lag]
                acc['added_pairs'][lag]+=y['pairs']-x['pairs']
                delta=abs(complex(y['cos_sum'],y['sin_sum'])/y['pairs']-complex(x['cos_sum'],x['sin_sum'])/x['pairs'])
                acc['max_circular_moment_change'][lag]=max(acc['max_circular_moment_change'][lag],delta)
        report['corrected_runs']+=1
    report['complete']=not report['missing_runs']
    (BASE/'continuity_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    text=f"""# Updated conclusions — 2 November 2026

Amplitude results cover all 260 complete runs (680–939), with 272.63 billion
complex samples per mode and 15.15 hours of acquired time. Continuous-run
corrections have been recovered and audited for {report['corrected_runs']}/260 runs.

- Absolute mean amplitude drifts together across the three modes: 2.6–3.3%
  maximum/minimum span. Amplitude variance spans 5.3–6.6%. A constant absolute
  noise level across the campaign is not supported by these descriptive results.
- The coefficient of variation and the local +3 sigma sample fractions vary
  much less. This supports approximate scale stability of selected marginal
  statistics; it does not establish stationary tails or covariance.
- Rayleigh magnitude noise is a much closer tail baseline than Gaussian
  amplitude noise. The per-run scale is estimated from E[A²]/2. Observed/Rayleigh
  count ratios across modes span 0.993–1.006 at +3 sigma, 0.973–1.035 at +5 sigma,
  and 0.935–1.105 at +7 sigma. This is an in-sample descriptive model comparison,
  not proof of independent Gaussian IQ or a goodness-of-fit/significance test.
- The empirical 3/5/7 sigma thresholds are mean(A)+k std(A). A threshold crossing
  is a sample exceedance, not an independently established physical event.
- The 1% mean-square-level stability horizon has a median observed bracket of
  106.5–110.1 minutes, but its shortest observed bracket is 10.7–14.2 minutes.
  This tolerance-dependent level metric is not a universal stationarity or
  decorrelation time; late windows are right censored.
- All SPEC blocks within one run are continuous. Corrections preserve amplitude
  moments, thresholds and sample counts in every audited run. They restore
  cumulative phase and add cross-SPEC lag pairs / join boundary episodes.
- Unwrapped phase winding is convention dependent near zero amplitude and does
  not by itself identify a coherent oscillation. The first 1.048576 s of run 680
  shows broadband spectral structure and short alternating correlations; this
  limited diagnostic does not rule out weak or transient tones elsewhere.

Next scientific steps: estimate windowed covariance and PSD on continuous
streams, assess amplitude-model residuals and dependence before assigning
uncertainty, and compare common drift with gain/environmental metadata.

Missing corrected runs: {report['missing_runs'] if report['missing_runs'] else 'none'}.
Original run products are preserved; no mixed-schema phase aggregate is used.
"""
    (BASE/'CONCLUSIONS.md').write_text(text)
    return report

if __name__=='__main__':print(json.dumps(summarize(),indent=2))
