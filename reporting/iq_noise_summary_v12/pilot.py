"""Validated complete v2 pilot figures and the explanatory covariance labels."""
import csv
from datetime import datetime
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

import h5py
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable

from noise_temperature_pilot import validate
from report_noise_v2 import report
from report_noise_temperature import temperatures_by_run, write_csv

MODES=('TM010','TM011','TM012')
COLORS=('#007F86','#7657A6','#D98726')
TZ=ZoneInfo('Europe/Rome')


def figures(directory,baseline,out,sha):
    paths=sorted(directory.glob('run*_noise_v2.h5'))
    runs=[int(p.name[3:8]) for p in paths]
    expected=[680,704,727,751,774,798,821,845,868,892,915,939]
    if runs!=expected:raise ValueError('Need exactly the twelve complete v2 pilot runs')
    metadata={}
    for run,path in zip(runs,paths):
        summary=validate(path,run,'v2')
        metadata[str(run)]=dict(sha256=sha(path),samples=summary['samples'],events=len(summary['events']))
    temperature=baseline/'data/temperatures.csv'
    report_dir=out/'data/v2_pilot'
    report(paths,temperature,report_dir)
    with (report_dir/'dc_ac_temperature_by_run.csv').open() as stream:
        rows=[{k:v if k=='mode' else float(v) for k,v in r.items()} for r in csv.DictReader(stream)]
    with (report_dir/'trend_diagnostics.csv').open() as stream:trends=list(csv.DictReader(stream))
    with (baseline/'data/bands_temperature_by_run.csv').open() as stream:v1=list(csv.DictReader(stream))
    grouped={m:[r for r in rows if r['mode']==m] for m in MODES}
    first=grouped['TM010'][0]['spec_midpoint_unix']
    hours=np.array([(r['spec_midpoint_unix']-first)/3600 for r in grouped['TM010']])
    assets=out/'assets';pictures={};findings={}
    def save(fig,name):
        path=assets/(name+'.png')
        fig.savefig(path,dpi=200,bbox_inches='tight',facecolor='white')
        fig.savefig(assets/(name+'.pdf'),bbox_inches='tight',facecolor='white')
        plt.close(fig);pictures[name]=path
    for mode in MODES:
        old=sorted([r for r in v1 if r['mode']==mode and float(r['offset_hz'])==0],key=lambda r:int(r['run']))
        if [int(r['run']) for r in old]!=expected:raise ValueError('v1 pilot coverage differs')
        a,b=grouped[mode][0],grouped[mode][-1]
        diagnostics=next(r for r in trends if r['mode']==mode and r['metric']=='central_squared_v2' and r['sensor']=='15')
        findings[mode]=dict(central_v1_change_pct=100*(float(old[-1]['rms_v'])/float(old[0]['rms_v'])-1),
            central_v2_change_pct=100*(b['central_rms_input_v']/a['central_rms_input_v']-1),
            side_v2_change_pct=100*(b['side_rms_input_v']/a['side_rms_input_v']-1),
            fullband_ac_change_pct=100*(b['ac_rms_input_v']/a['ac_rms_input_v']-1),
            dc_squared_change_pct=100*(b['dc_squared_v2']/a['dc_squared_v2']-1),
            central_after_common_pct=100*(b['central_relative_after_common']-1),
            r_central_temperature=float(diagnostics['r_temperature']),
            r_central_temperature_after_time=float(diagnostics['r_temperature_after_linear_time']))

    raw_t=temperatures_by_run(temperature,set(range(680,940)))
    fig,axes=plt.subplots(2,1,figsize=(12,5.1),sharex=True,gridspec_kw={'height_ratios':[1,1.15]})
    for sensor,label,color in [(15,'Cavity',COLORS[0]),(16,'CMN143',COLORS[1]),(17,'CMN130',COLORS[2])]:
        points=sorted(p for run in raw_t.values() for p in run[sensor])
        axes[0].plot([datetime.fromtimestamp(t,TZ) for t,_ in points],[v for _,v in points],lw=1,color=color,label=label)
    axes[0].set_ylabel('Observed AVS temperature [mK]');axes[0].legend(ncol=3,fontsize=9)
    for mode,color in zip(MODES,COLORS):
        g=grouped[mode]
        axes[1].plot([datetime.fromtimestamp(r['spec_midpoint_unix'],TZ) for r in g],
                     [100*(r['ac_rms_input_v']/g[0]['ac_rms_input_v']-1) for r in g],
                     'o-',color=color,ms=4,label=mode)
    relative=np.array([[100*(r['ac_rms_input_v']/grouped[mode][0]['ac_rms_input_v']-1)
                        for r in grouped[mode]] for mode in MODES])
    write_csv(report_dir/'ac_rms_relative_to_run680.csv',[
        dict(run=int(r['run']),mode=mode,spec_midpoint_unix=r['spec_midpoint_unix'],
             change_pct=float(relative[i,j]),mode_range_min_pct=float(relative[:,j].min()),
             mode_range_max_pct=float(relative[:,j].max()))
        for i,mode in enumerate(MODES) for j,r in enumerate(grouped[mode])])
    times=[datetime.fromtimestamp(r['spec_midpoint_unix'],TZ) for r in grouped['TM010']]
    axes[1].fill_between(times,relative.min(axis=0),relative.max(axis=0),color='#AAB3BD',alpha=.2,
                         label='Min–max across modes',zorder=0)
    axes[1].axhline(0,color='#66768A',lw=.6)
    for run,r in zip(runs,grouped['TM010']):
        change=100*(r['ac_rms_input_v']/grouped['TM010'][0]['ac_rms_input_v']-1)
        axes[1].annotate(str(run),(datetime.fromtimestamp(r['spec_midpoint_unix'],TZ),change),
                         xytext=(0,7),textcoords='offset points',ha='center',fontsize=8)
    axes[1].legend(ncol=4,fontsize=8,loc='upper left')
    axes[1].margins(y=.24)
    axes[1].set(ylabel='RMS change from run 680 [%]',xlabel='Acquisition clock time · Europe/Rome (CEST)')
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%d %b\n%H:%M',tz=TZ))
    fig.suptitle('Common starting level: each mode is referenced to its own run 680 RMS')
    fig.tight_layout();save(fig,'v2_temperature_and_ac')

    fig,axes=plt.subplots(3,1,figsize=(12,5.3),sharex=True)
    for ax,mode in zip(axes,MODES):
        for index,offset in enumerate((-1e6,-5e5,-2.5e5,-1e5,0,1e5,2.5e5,5e5,1e6)):
            values=[]
            for path in paths:
                with h5py.File(path) as source:
                    events=source[f'filtered_bands/modes/{mode}/band_{index:02d}/events']
                    values.append(float(np.sqrt(np.average(events['rms_input_v'][:]**2,weights=events['n'][:])))*1e9)
            ax.plot(hours,values,'o-' if offset==0 else '--' if offset<0 else '-',
                    lw=1.5 if offset==0 else .8,ms=2,label=f'{offset/1000:+g} kHz',
                    color='#24364B' if offset==0 else ('#3B82B8','#007F86','#A46E18','#965F96')[int(np.where(np.array([1e5,2.5e5,5e5,1e6])==abs(offset))[0][0])])
        ax.set_ylabel(mode+'\nRMS [nV]')
    axes[0].legend(ncol=5,fontsize=8,loc='lower center',bbox_to_anchor=(.5,1.02))
    axes[-1].set_xlabel('Acquisition clock time from run 680 [h]')
    fig.tight_layout();save(fig,'v2_nine_band_levels')

    fig,axes=plt.subplots(1,3,figsize=(12,4.1),sharex=True,sharey=True)
    for ax,mode,color in zip(axes,MODES,COLORS):
        old=sorted([r for r in v1 if r['mode']==mode and float(r['offset_hz'])==0],key=lambda r:int(r['run']))
        raw=np.array([float(r['rms_v']) for r in old])
        central=np.array([r['central_rms_input_v'] for r in grouped[mode]])
        side=np.array([r['side_rms_input_v'] for r in grouped[mode]])
        for values,label,style,c in [(raw,'v1 centre: DC retained','--','#7657A6'),
                                    (central,'v2 centre: run DC removed','o-','#24364B'),
                                    (side,'v2 mean sideband RMS','s-','#007F86')]:
            ax.plot(hours,100*(values/values[0]-1),style,color=c,label=label,ms=3)
        ax.set(title=mode,xlabel='Acquisition clock time [h]');ax.axhline(0,color='#999999',lw=.5)
    axes[0].set_ylabel('RMS change from run 680 [%]')
    axes[1].legend(fontsize=8,loc='lower center',bbox_to_anchor=(.5,1.08))
    fig.tight_layout();save(fig,'v1_v2_central_drift')

    fig,axes=plt.subplots(3,2,figsize=(12,5.7));norm=Normalize(hours.min(),hours.max())
    for i,mode in enumerate(MODES):
        g=grouped[mode];temp=np.array([r['t15_median_mk'] for r in g])
        for j,(key,label) in enumerate([('central_squared_v2','DC-removed centre'),('side_squared_v2','Mean sideband')]):
            power=np.array([r[key] for r in g]);change=100*(power/power[0]-1)
            d=next(r for r in trends if r['mode']==mode and r['metric']==key and r['sensor']=='15')
            ax=axes[i,j];ax.plot(temp,change,lw=.6,color='#AAB3BD')
            ax.scatter(temp,change,c=hours,norm=norm,cmap='viridis',s=30)
            ax.set(title=f"{mode} {label}: r={float(d['r_temperature']):+.2f}; r|time={float(d['r_temperature_after_linear_time']):+.2f}",
                   ylabel='Mean-square change [%]')
            ax.title.set_fontsize(9)
    for ax in axes[-1]:ax.set_xlabel('Observed in-run cavity temperature [mK]')
    fig.subplots_adjust(hspace=.62,wspace=.3,right=.91,top=.94,bottom=.1)
    cax=fig.add_axes([.93,.15,.012,.7]);fig.colorbar(ScalarMappable(norm=norm,cmap='viridis'),cax=cax,label='Acquisition time [h]')
    save(fig,'v2_temperature_associations')

    fig,axes=plt.subplots(1,3,figsize=(12,4.1),sharex=True,sharey=True)
    for ax,mode,color in zip(axes,MODES,COLORS):
        g=grouped[mode]
        for metric,label,style,c in [('central_relative_after_common','Centre / common','o-','#24364B'),
                                    ('side_relative_after_common','Side / common','s-',color)]:
            ax.plot(hours,[100*(r[metric]-1) for r in g],style,color=c,ms=3,label=label)
        ax.axhline(0,color='#999999',lw=.5);ax.set(title=mode,xlabel='Acquisition clock time [h]')
    axes[0].set_ylabel('Residual relative amplitude [%]');axes[1].legend(fontsize=9)
    fig.suptitle('Common trend estimated from these same three modes; not an independent gain measurement',fontsize=11)
    fig.tight_layout();save(fig,'v2_common_trend_residuals')

    snapshot=dict(runs=runs,metadata=metadata,findings=findings,
        limitations='Nominal constant gain; twelve selected runs; time and temperature covary; linear-time conditioning and common-trend division are descriptive, not causal gain corrections.')
    (report_dir/'pilot_findings.json').write_text(json.dumps(snapshot,indent=2)+'\n')
    return pictures,findings,snapshot


def append(deck,page,pictures,findings):
    captions=[
        ('Selected runs: common origin and relative drift','12/12 complete v2 runs · every mode starts at 0% in run 680 · actual acquisition dates','v2_temperature_and_ac',
         'One complex mean per run is removed. Lower curves show 100*(AC_RMS_mode(run)/AC_RMS_mode(680)-1), not absolute voltage. '
         'Only the first selected run is the baseline; subsequent runs retain measured differences. Grey fill is the minimum-to-maximum range across three modes, not an uncertainty or stochastic diffusion estimate. '
         'Constant gain cancels in these ratios. Temperatures are actual AVS readings; no interpolated observations.'),
        ('Nine equal frequency bands after DC removal','Three modes × nine nominal 50 kHz filters · continuous FIR state across SPEC','v2_nine_band_levels',
         'Input run mean removed before mixing and FIR. Filter-output coherent means are retained in the principal RMS. Nominal input-referred nV; no RF watts or noise-temperature interpretation.'),
        ('Removing DC changes the central-band drift','Same twelve runs and filters · v1/v2 central RMS compared with the sidebands','v1_v2_central_drift',
         'The v1 central TM011 decline reverses after run-mean subtraction. A changing constant complex component accounted for much of the earlier difference; this does not identify its hardware or physical origin.'),
        ('Temperature associations after removing run DC','12 run summaries · r|time removes an intercept and a linear time trend','v2_temperature_associations',
         'Shown mean-square filtered IQ amplitude is not a fluctuation variance after demodulated-output mean subtraction. Residual Pearson correlations after linear time conditioning are descriptive; no p-values or causal temperature sensitivity.'),
        ('Compare with the common trend, without calling it gain','Common = median log sideband-amplitude ratio across the three measured modes','v2_common_trend_residuals',
         'The target mode contributes to this same common statistic. Division is not independent gain calibration and can suppress shared physical behaviour; measured gain telemetry and numerical kz(f) remain needed.')]
    for title,subtitle,name,notes in captions:
        s=page(title,subtitle,'TEMPERATURE | COMPLETE 12-RUN v2 PILOT',notes,
               'Source: 12 validated published v2 HDF5s; observed AVS data; paired v1 pilot where shown; data/v2_pilot/.')
        deck.image(s,.5,1.8,12.3,4.9,pictures[name])
    s=page('DC removal changes the thermal comparison','End-to-end changes: run 680 → 939 · all twelve pilot runs complete',
           'TEMPERATURE | v2 CONCLUSIONS',
           'DC-removed central RMS and sideband RMS rise similarly. The temperature/time/common-trend comparisons do not identify amplifier gain or causation. '
           'All table changes use the first and last run only; r|time uses all twelve run summaries.',
           'Source: data/v2_pilot/pilot_findings.json and trend_diagnostics.csv; no mixed-version thermal regression.')
    headings=[(.7,1.3,'Mode'),(2.1,2.2,'Centre v1 Δ'),(4.6,2.2,'Centre v2 Δ'),(7.1,2.2,'Side v2 Δ'),(9.6,2.6,'r(centre²,T | time)')]
    for x,w,label in headings:deck.text(s,x,2.,w,.5,label,14,True)
    for i,(mode,color) in enumerate(zip(MODES,COLORS)):
        f=findings[mode]
        values=[mode,f"{f['central_v1_change_pct']:+.2f}%",f"{f['central_v2_change_pct']:+.2f}%",f"{f['side_v2_change_pct']:+.2f}%",f"{f['r_central_temperature_after_time']:+.3f}"]
        for (x,w,_),value in zip(headings,values):deck.text(s,x,2.7+i*.62,w,.45,value,19,color=color)
    deck.text(s,.8,4.95,11.7,.75,'The TM011 decline largely followed its changing complex mean.\nAfter DC removal, central and sideband RMS rise by about 1%.',19,True)
    deck.text(s,.8,5.9,11.7,.75,'Next: validate bulk v2; compare time and independently measured gain; apply numerical frequency-response calibration before physical interpretation.',17)


def periodicity(directory,assets,sha):
    diag=directory/'periodicity_diagnostic.npz';fitpath=directory/'positive_envelope_fit.json'
    fits=json.loads(fitpath.read_text())
    with np.load(diag,allow_pickle=False) as data:
        frequency=data['frequency_hz'];lag=data['lag_s'];factor=256
        fig,axes=plt.subplots(3,2,figsize=(11,5.7))
        for row,(mode,color) in enumerate(zip(MODES,COLORS)):
            power=data[mode+'_periodogram_v2_per_hz']
            axes[row,0].plot(frequency.reshape(-1,factor).mean(axis=1)/1e6,
                            10*np.log10(power.reshape(-1,factor).mean(axis=1)),color=color,lw=.65)
            axes[row,0].set(title=mode+' · IQ spectrum',xlabel='Baseband frequency [MHz]',ylabel='PSD [dB V²/Hz]')
            acf=data[mode+'_normalized_covariance'];fit=fits['modes'][mode]
            np.testing.assert_allclose(acf[0],1.,atol=1e-12)
            axes[row,1].plot(lag[1:]*1e6,acf[1:].real,'.-',ms=2,lw=.6,color=color)
            tx=np.linspace(*fit['plot_range_us'],250)
            axes[row,1].plot(tx,fit['offset']+fit['amplitude']*np.exp(-tx/fit['tau_us']),color='#E36E18',lw=1.6,
                            label=f"Upper-envelope decay: τ ≈ {fit['tau_us']:.2f} μs")
            axes[row,1].scatter(fit['peak_lag_us'],fit['peak_covariance'],facecolors='none',edgecolors='#E36E18',s=20)
            axes[row,1].axhline(0,color='#66768A',lw=.5)
            axes[row,1].set(title=mode+' · normalized IQ similarity',xlabel='Time separation (lag) [μs]',ylabel='Re R[k] / R[0]',xlim=(0,10))
            axes[row,1].legend(fontsize=6.5)
            for ax in axes[row]:ax.tick_params(labelsize=8);ax.title.set_fontsize(10);ax.xaxis.label.set_size(9);ax.yaxis.label.set_size(9)
        fig.tight_layout();path=assets/'periodicity_explained.png';fig.savefig(path,dpi=200);plt.close(fig)
    return path,dict(npz_sha256=sha(diag),fit_sha256=sha(fitpath),definition='R[k] = sum(z_centered[n+k] * conj(z_centered[n])) / (N-k); plot real(R[k])/R[0]. Lag seconds=k/fs; 0.2 us per sample. Zero lag equals one and is omitted from this zoom.')
