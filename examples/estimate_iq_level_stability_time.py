#!/usr/bin/env python3
"""Operational drift horizons, not a full stationarity or decorrelation time."""
import argparse
import csv
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np

MODES=('TM010','TM011','TM012')


def horizons(t, values, tolerance):
    """Accepted/first-failing observed span for each start, all modes required."""
    result=[]
    for i in range(len(t)):
        lo=hi=values[:,i].copy()
        previous=i;cross=None
        for j in range(i+1,len(t)):
            lo=np.minimum(lo,values[:,j]);hi=np.maximum(hi,values[:,j])
            if np.any(hi/lo-1>tolerance):cross=j;break
            previous=j
        result.append({'start_index':i,'last_accepted_index':previous,
            'first_exceedance_index':cross,'right_censored':cross is None,
            'accepted_duration_min':float((t[previous]-t[i])/60),
            'first_exceedance_min':float((t[cross]-t[i])/60) if cross is not None else None,
            'available_followup_min':float((t[-1]-t[i])/60)})
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/noise_stationarity/stationarity_by_run.csv'))
    parser.add_argument('--out-dir',type=Path,default=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/noise_stationarity'))
    args=parser.parse_args()
    rows=list(csv.DictReader(args.input.open()));by={m:sorted([r for r in rows if r['mode']==m],key=lambda r:int(r['run'])) for m in MODES}
    runs=np.array([int(r['run']) for r in by[MODES[0]]]);t=np.array([float(r['timestamp_unix']) for r in by[MODES[0]]])
    assert np.all(np.diff(t)>0)
    for m in MODES:
        np.testing.assert_array_equal(runs,[int(r['run']) for r in by[m]])
        np.testing.assert_array_equal(t,[float(r['timestamp_unix']) for r in by[m]])
    values=np.array([[float(r['mean_square_iq_v2']) for r in by[m]] for m in MODES])
    assert np.all(np.isfinite(values)) and np.all(values>0)
    groups={'all_three_modes':values,**{m:values[i:i+1] for i,m in enumerate(MODES)}}
    flat=[];summary={'metric':'per-run E[A^2] in V^2','criterion':'for every included mode max(P)/min(P)-1 <= tolerance over all run midpoints in the window',
        'sampling_median_min':float(np.median(np.diff(t))/60),
        'interpretation':'operational stability of run-averaged IQ level only; not full stationarity, raw-sample stability or decorrelation time',
        'statistics_scope':'medians and minima over starts with an observed crossing; overlapping windows are not independent trials; no confidence intervals or p-values',
        'groups':{}}
    all_results={}
    for group,v in groups.items():
        summary['groups'][group]={}
        for tolerance in (.001,.005,.01):
            estimates=horizons(t,v,tolerance);observed=[r for r in estimates if not r['right_censored']]
            lo=np.array([r['accepted_duration_min'] for r in observed]);hi=np.array([r['first_exceedance_min'] for r in observed])
            summary['groups'][group][str(tolerance)]={'observed_crossings':len(observed),'right_censored':len(estimates)-len(observed),
                'median_accepted_min':float(np.median(lo)) if len(lo) else None,
                'median_first_exceedance_min':float(np.median(hi)) if len(hi) else None,
                'minimum_accepted_min':float(lo.min()) if len(lo) else None,
                'minimum_first_exceedance_min':float(hi.min()) if len(hi) else None}
            for record in estimates:
                flat.append({'group':group,'tolerance_fraction':tolerance,'start_run':int(runs[record['start_index']]),
                    'start_timestamp_unix':float(t[record['start_index']]),**record})
            if group=='all_three_modes':all_results[tolerance]=estimates
    args.out_dir.mkdir(parents=True,exist_ok=True)
    with (args.out_dir/'level_stability_horizons.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    (args.out_dir/'level_stability_times.json').write_text(json.dumps(summary,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    tz=ZoneInfo('Europe/Rome');dates=[datetime.fromtimestamp(x,tz) for x in t]
    fig,axes=plt.subplots(3,1,figsize=(12,10),squeeze=False)
    for ax,(tol,estimates) in zip(axes.flat,all_results.items()):
        lower=np.array([r['accepted_duration_min'] if not r['right_censored'] else np.nan for r in estimates])
        upper=np.array([r['first_exceedance_min'] if not r['right_censored'] else np.nan for r in estimates])
        ax.fill_between(dates,lower,upper,color='#007F86',alpha=.25,label='Last accepted to first exceeding run')
        ax.plot(dates,upper,color='#007F86',lw=1,label='First observed exceedance')
        censored=[i for i,r in enumerate(estimates) if r['right_censored']]
        ax.scatter([dates[i] for i in censored],[estimates[i]['available_followup_min'] for i in censored],color='gray',marker='x',s=15,label='No crossing before end of data')
        ax.set(title='Allowed IQ mean-square level range: %.1f%% · all three modes'% (100*tol),ylabel='Horizon [min]',ylim=(0,None))
        ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[0,3,6,9,12,15,18,21],tz=tz));ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b\n%H:%M',tz=tz));ax.grid(alpha=.2)
        ax.legend(fontsize=8,ncol=2)
    axes[-1,0].set_xlabel('Window start time · Europe/Rome (CEST)')
    fig.suptitle('Operational level-stability horizon from run averages — not a full stationarity time')
    fig.tight_layout();fig.savefig(args.out_dir/'level_stability_horizons.png',dpi=160);plt.close(fig)
    print(json.dumps(summary['groups']['all_three_modes'],indent=2))


if __name__=='__main__':main()
