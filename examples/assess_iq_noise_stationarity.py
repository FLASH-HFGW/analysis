#!/usr/bin/env python3
"""Stationarity screening from full-run moments and saved interval means.

This is descriptive: no p-values or full weak-stationarity claim are produced.
"""
import argparse
import csv
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np

MODES=('TM010','TM011','TM012')
COLORS=('#007F86','#7657A6','#D98726')


def assess(root, out):
    records=[]
    for path in sorted(root.glob('*/run*_noise.json')):
        data=json.loads(path.read_text())
        if data.get('status')!='success' or not data.get('reached_eof'):
            raise ValueError('Incomplete run: '+str(path))
        run=int(path.parent.name)
        events=data['events'];clock=(events[0]['midas_timestamp']+events[-1]['midas_timestamp'])/2
        with np.load(path.with_suffix('.npz'),allow_pickle=False) as arrays:
            start=arrays['envelope_start_sample'];stop=arrays['envelope_stop_sample']
            weights=stop-start;centers=(start+stop-1)/2/data['fs_hz'];duration=data['samples']/data['fs_hz']
            for mode in MODES:
                st=data['modes'][mode];mu=st['mean_amplitude_v'];sd=st['amplitude_noise_rms_v']
                means=arrays[mode+'_envelope_mean_v']
                if mu<=0 or sd<0:raise ValueError('Invalid amplitude moments')
                np.testing.assert_allclose(np.average(means,weights=weights),mu,rtol=1e-12,atol=1e-14)
                first=centers<.1*duration;last=centers>=.9*duration
                if not first.any() or not last.any():raise ValueError('Not enough interval means')
                early=float(np.average(means[first],weights=weights[first]))
                late=float(np.average(means[last],weights=weights[last]))
                centered_time=centers-np.average(centers,weights=weights)
                slope=float(np.sum(weights*centered_time*(means-mu))/np.sum(weights*centered_time**2))
                row={'run':run,'mode':mode,'timestamp_unix':clock,'samples':data['samples'],
                     'mean_amplitude_v':mu,'std_amplitude_v':sd,'variance_amplitude_v2':sd*sd,
                     'mean_square_iq_v2':mu*mu+sd*sd,'amplitude_cv':sd/mu,
                     'within_run_first_decile_mean_v':early,'within_run_last_decile_mean_v':late,
                     'within_run_decile_difference_percent':100*(late-early)/mu,
                     'within_run_linear_change_percent':100*slope*duration/mu,
                     'interval_width_s':float(np.median(weights)/data['fs_hz'])}
                for lag,stlag in data['global_statistics']['modes'][mode]['delta_circular'].items():
                    if stlag['pairs']:
                        row['phase_circular_real_lag'+lag]=stlag['cos_sum']/stlag['pairs']
                        row['phase_circular_imag_lag'+lag]=stlag['sin_sum']/stlag['pairs']
                records.append(row)
    if not records:raise ValueError('No full-run results found')
    out.mkdir(parents=True,exist_ok=True)
    columns=list(dict.fromkeys(k for r in records for k in r))
    with (out/'stationarity_by_run.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(records)
    summary={'run_count':len(records)//3,'scope':'descriptive moment and shape stability; not a formal stationarity test',
             'mean_square_definition':'E[|I-jQ|^2] = Var(A) + E[A]^2, in V^2, not power in watts',
             'within_run_definition':'weighted means of saved intervals in the first and last 10% of acquired time; decile edges resolved to one saved interval',
             'phase_definition':'E[exp(i*(phi[n+lag]-phi[n]))]; phase-only circular statistic, not IQ autocovariance',
             'limitations':['No Gaussian assumption is required for these descriptive moments.',
                            'Stable coefficient of variation does not prove a stable full distribution or covariance.',
                            'Within-run interval variances and full IQ autocovariance/PSD are not stored in the current outputs.',
                            'No independent-sample assumption or uncertainty based on raw N is made.',
                            'Normalization can hide physical scale drift; inspect raw and normalized metrics together.'],
             'reference':'https://www.itl.nist.gov/div898/handbook/pmc/section4/pmc442.htm','modes':{}}
    for mode in MODES:
        rows=[r for r in records if r['mode']==mode];stats={}
        for key in ('mean_amplitude_v','std_amplitude_v','variance_amplitude_v2','mean_square_iq_v2','amplitude_cv'):
            x=np.asarray([r[key] for r in rows]);lo=int(x.argmin());hi=int(x.argmax())
            stats[key]={'min':float(x[lo]),'max':float(x[hi]),'median':float(np.median(x)),
                        'span_percent':float(100*(x[hi]/x[lo]-1)),'min_run':rows[lo]['run'],'max_run':rows[hi]['run']}
        for key in ('within_run_decile_difference_percent','within_run_linear_change_percent'):
            x=np.asarray([r[key] for r in rows]);stats[key]={'median_signed':float(np.median(x)),
                'median_abs':float(np.median(abs(x))),'p95_abs':float(np.percentile(abs(x),95)),
                'max_abs':float(np.max(abs(x))),'max_abs_run':rows[int(np.argmax(abs(x)))]['run']}
        summary['modes'][mode]=stats
    (out/'stationarity_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    plots(records,out)
    return summary


def plots(records,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    tz=ZoneInfo('Europe/Rome')
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    def clock(ax):
        ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[0,3,6,9,12,15,18,21],tz=tz))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b\n%H:%M',tz=tz))
        ax.set_xlabel('Local time · Europe/Rome (CEST)');ax.grid(alpha=.18)
    fig,axes=plt.subplots(3,3,figsize=(17,11),squeeze=False)
    for row,(mode,color) in enumerate(zip(MODES,COLORS)):
        rows=[r for r in records if r['mode']==mode];t=[datetime.fromtimestamp(r['timestamp_unix'],tz) for r in rows]
        for col,(key,title) in enumerate((('mean_amplitude_v','Mean amplitude'),('variance_amplitude_v2','Amplitude variance'),('amplitude_cv','Normalized shape: std(A) / mean(A)'))):
            x=np.array([r[key] for r in rows]);axes[row,col].plot(t,100*(x/x[0]-1),color=color)
            axes[row,col].set(title=mode+' · '+title,ylabel='Change relative to run 680 [%]');clock(axes[row,col])
    fig.suptitle('Across-run stationarity screening: raw moments drift, coefficient of variation is much more stable')
    fig.tight_layout();fig.savefig(out/'raw_vs_normalized_stability.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(12,8),squeeze=False)
    for mode,color in zip(MODES,COLORS):
        rows=[r for r in records if r['mode']==mode];t=[datetime.fromtimestamp(r['timestamp_unix'],tz) for r in rows]
        p=np.array([r['mean_square_iq_v2'] for r in rows]);axes[0,0].plot(t,100*(p/p[0]-1),color=color,label=mode)
        axes[1,0].plot(t,[r['within_run_decile_difference_percent'] for r in rows],color=color,label=mode,lw=.8)
    axes[0,0].set(title='Mean-square IQ amplitude: E[A²]',ylabel='Change from run 680 [%]')
    axes[1,0].set(title='Within-run mean stability: last vs first acquired-time decile',ylabel='Difference / full-run mean [%]')
    for ax in axes.flat:clock(ax);ax.axhline(0,color='gray',ls='--',lw=.6);ax.legend(ncol=3)
    fig.tight_layout();fig.savefig(out/'time_scale_comparison.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(3,3,figsize=(17,10),squeeze=False)
    for row,(mode,color) in enumerate(zip(MODES,COLORS)):
        rows=[r for r in records if r['mode']==mode];t=[datetime.fromtimestamp(r['timestamp_unix'],tz) for r in rows]
        for col,lag in enumerate((1,10,100)):
            axes[row,col].plot(t,[r['phase_circular_real_lag'+str(lag)] for r in rows],color=color,label='Re Cφ')
            axes[row,col].plot(t,[r['phase_circular_imag_lag'+str(lag)] for r in rows],color='gray',lw=.8,label='Im Cφ')
            axes[row,col].set(title=mode+' · phase-only lag '+str(lag)+' samples',ylabel='Circular increment moment');clock(axes[row,col]);axes[row,col].legend(fontsize=8)
    fig.suptitle('Phase-only dependence across runs — not a full IQ autocovariance test')
    fig.tight_layout();fig.savefig(out/'phase_dependence_screening.png',dpi=160);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir',type=Path,default=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/job_to_submit_noise'))
    parser.add_argument('--out-dir',type=Path,default=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/noise_stationarity'))
    args=parser.parse_args();summary=assess(args.input_dir,args.out_dir)
    print('Screened',summary['run_count'],'runs. Results:',args.out_dir)
    for mode,st in summary['modes'].items():
        print(mode,'mean span %.3f%%, amplitude variance span %.3f%%, CV span %.4f%%, median absolute within-run mean shift %.5f%%'%
              (st['mean_amplitude_v']['span_percent'],st['variance_amplitude_v2']['span_percent'],st['amplitude_cv']['span_percent'],st['within_run_decile_difference_percent']['median_abs']))


if __name__=='__main__':main()
