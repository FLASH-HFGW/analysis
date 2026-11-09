#!/usr/bin/env python3
"""Compare complete v2 DC/AC products with temperature, time and a common trend."""
import argparse
import hashlib
import json
from pathlib import Path

import h5py
import numpy as np

from iq_noise_io import read_summary, save_results_h5
from iq_noise_v2 import trend_diagnostics
from report_noise_temperature import temperatures_by_run, write_csv

MODES = ('TM010','TM011','TM012')


def report(paths, temperatures, output):
    paths = sorted(map(Path,paths))
    summaries = [read_summary(p) for p in paths]
    runs = [int(Path(s['input']).name[3:8]) for s in summaries]
    if not paths or len(set(runs)) != len(runs):
        raise ValueError('Need unique complete v2 runs')
    data = temperatures_by_run(temperatures,set(runs))
    rows, hashes, calibration_ids, configs = [], {}, set(), set()
    for run,path,summary in zip(runs,paths,summaries):
        if (summary.get('product_version') != 'v2' or not summary.get('reached_eof')
                or summary.get('status') != 'success' or summary.get('iq_sign') != -1):
            raise ValueError('Need complete I-iQ v2 products: '+str(path))
        events = summary['events']
        start,stop = min(e['midas_timestamp'] for e in events),max(e['midas_timestamp'] for e in events)
        temp = {}
        for sensor in (15,16,17):
            observations = [v for t,v in data[run][sensor] if start<=t<=stop]
            if not observations:
                raise ValueError(f'No in-run temperature for run {run}, sensor {sensor}')
            temp[f't{sensor}_median_mk'] = float(np.median(observations))
            temp[f't{sensor}_observations'] = len(observations)
        hashes[str(run)] = hashlib.sha256(path.read_bytes()).hexdigest()
        with h5py.File(path,'r') as source:
            calibration_ids.add(source['dc_removed/calibration/sha256'].asstr()[()])
            cfg=source['filtered_bands/config']
            configs.add(json.dumps({k:np.asarray(cfg[k][()]).tolist() for k in
                                   ('fs_hz','taps','decimation','width_hz','offsets_hz','centers_hz')}))
            gain=float(source['dc_removed/calibration/voltage_gain'][()])
            for mode in MODES:
                full=source['dc_removed/modes/'+mode]
                row=dict(run=run, mode=mode, spec_midpoint_unix=(start+stop)/2, **temp)
                for key in ('mean_i_v','mean_q_v','dc_squared_v2','ac_squared_v2',
                            'total_squared_v2','ac_rms_v','ac_rms_input_v'):
                    row[key]=float(full[key][()])
                bands = list(source['filtered_bands/modes/'+mode].values())
                offsets=sorted(float(b['offset_hz'][()]) for b in bands)
                if offsets!=[-1e6,-5e5,-2.5e5,-1e5,0.,1e5,2.5e5,5e5,1e6]:
                    raise ValueError('Expected nine default v2 bands per mode')
                central=next(b for b in bands if b['offset_hz'][()]==0)
                # Input DC is removed, but a band-centre coherent signal is retained.
                row['central_squared_v2']=float(central['complex_moments/total_squared_v2'][()])
                row['side_squared_v2']=float(np.mean([b['complex_moments/total_squared_v2'][()]
                                                    for b in bands if b['offset_hz'][()]!=0]))
                row['central_rms_input_v']=np.sqrt(row['central_squared_v2'])/gain
                row['side_rms_input_v']=np.sqrt(row['side_squared_v2'])/gain
                rows.append(row)
    if len(calibration_ids)!=1 or len(configs)!=1:
        raise ValueError('Incompatible calibration or filter configuration across runs')
    rows.sort(key=lambda r:(r['spec_midpoint_unix'],r['run'],r['mode']))
    ordered_runs=list(dict.fromkeys(r['run'] for r in rows))
    baseline={mode:next(r for r in rows if r['mode']==mode) for mode in MODES}
    common={}
    for run in ordered_runs:
        group=[r for r in rows if r['run']==run]
        ratios=[np.sqrt(r['side_squared_v2']/baseline[r['mode']]['side_squared_v2']) for r in group]
        if any(v<=0 or not np.isfinite(v) for v in ratios):
            raise ValueError('Cannot form positive common sideband trend')
        common[run]=float(np.exp(np.median(np.log(ratios))))
    trends=[]
    for row in rows:
        row['common_side_amplitude_ratio']=common[row['run']]
        row['central_relative_after_common']=np.sqrt(row['central_squared_v2']/baseline[row['mode']]['central_squared_v2'])/common[row['run']]
        row['side_relative_after_common']=np.sqrt(row['side_squared_v2']/baseline[row['mode']]['side_squared_v2'])/common[row['run']]
    for mode in MODES:
        group=[r for r in rows if r['mode']==mode]
        for metric in ('ac_squared_v2','dc_squared_v2','central_squared_v2','side_squared_v2',
                       'central_relative_after_common','side_relative_after_common'):
            for sensor in (15,16,17):
                diagnostics=trend_diagnostics([r[metric] for r in group],
                      [r[f't{sensor}_median_mk'] for r in group],[r['spec_midpoint_unix'] for r in group])
                trends.append(dict(mode=mode,metric=metric,sensor=sensor,**diagnostics))
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    write_csv(output/'dc_ac_temperature_by_run.csv',rows)
    write_csv(output/'trend_diagnostics.csv',trends)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,2,figsize=(12,9))
    first=rows[0]['spec_midpoint_unix']
    for i,mode in enumerate(MODES):
        group=[r for r in rows if r['mode']==mode]
        hours=[(r['spec_midpoint_unix']-first)/3600 for r in group]
        for metric,label in [('ac_rms_input_v','Full-band AC'),('central_rms_input_v','Central band'),('side_rms_input_v','Mean sideband')]:
            axes[i,0].plot(hours,[r[metric]*1e9 for r in group],'o-',label=label)
        axes[i,0].set(ylabel=mode+' nominal input RMS [nV]')
        for metric,label in [('central_relative_after_common','Central/common'),('side_relative_after_common','Side/common')]:
            axes[i,1].plot(hours,[r[metric] for r in group],'o-',label=label)
        axes[i,1].set(ylabel=mode+' relative amplitude')
    for ax in axes.flat:
        ax.set_xlabel('Acquisition clock time [h]')
        ax.legend(fontsize=8)
        ax.grid(alpha=.2)
    fig.suptitle('v2: DC removed; common trend is not a measured gain')
    fig.tight_layout()
    image=output/'dc_ac_common_trend.png'
    fig.savefig(image,dpi=160)
    plt.close(fig)
    summary=dict(product_version='v2',runs=ordered_runs,calibration_sha256=next(iter(calibration_ids)),
        common_trend_definition='Median log sideband amplitude ratio across three modes relative to first run; includes each target mode; descriptive, not an independent gain measurement',
        limitations=['Nominal constant gain; no time-dependent gain telemetry or frequency-dependent kz correction.',
                     'DC removal does not separate amplifier/ADC offsets from a physical coherent DC signal.',
                     'Time-conditioned correlations remove only a linear trend; no p-values or causal interpretation.',
                     'No RF watts or noise temperature inferred from equivalent complex volts.'])
    packaged=dict(schema_version=1,product_version='v2',summary=summary,
        tables=dict(dc_ac_temperature_by_run=rows,trend_diagnostics=trends),
        provenance=dict(run_sha256=hashes,temperature_sha256=hashlib.sha256(temperatures.read_bytes()).hexdigest(),
                        temperature_schema_sha256=hashlib.sha256(temperatures.with_suffix('.schema.json').read_bytes()).hexdigest()),
        figures={image.name:dict(format='png',data=np.frombuffer(image.read_bytes(),dtype=np.uint8))})
    save_results_h5(output/'noise_temperature_comparison_v2.h5',packaged)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('products',type=Path,nargs='+')
    parser.add_argument('--temperatures',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(report(args.products,args.temperatures,args.output),indent=2))
