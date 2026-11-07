#!/usr/bin/env python3
"""Repair schema-1 run products with one raw-data pass; preserve amplitude results.

Original products are never overwritten. Cross-SPEC lag pairs are added exactly;
threshold episodes are joined, and displayed phase is unwrapped continuously.
"""
import argparse
import copy
import json
import time
from pathlib import Path
import numpy as np
from analyze_midas_iq_noise import analyze_mode, plot_iq_results, MODES
from iq_noise_statistics import SCHEMA, config_id, uniform_histogram


def repair_boundary(st, arrays, mode, i, q, a, history, tails, edges):
    """Add only cross-block pairs and join previously split episodes in place."""
    phi = np.arctan2(q, i)
    valid = a > 0
    ui = np.divide(i,a,out=np.zeros_like(a),where=valid)
    uq = np.divide(q,a,out=np.zeros_like(a),where=valid)
    current = (phi,valid,ui,uq)
    old = history.get(mode)
    h = 0 if old is None else len(old[0])
    joined = current if old is None else tuple(np.r_[x,y] for x,y in zip(old,current))
    pp,vv,ii,qq = joined
    for key, stat in st['delta_circular'].items():
        lag = int(key)
        # Right endpoint must belong to the new block, left to its history.
        begin, end = max(h,lag), min(h+len(a),h+lag)
        if begin >= end: continue
        left, right = slice(begin-lag,end-lag),slice(begin,end)
        good=vv[left]&vv[right]
        delta=(pp[right][good]-pp[left][good]+np.pi)%(2*np.pi)-np.pi
        arrays['global_'+mode+'_delta_'+key] += uniform_histogram(delta,edges)
        stat['pairs'] += len(delta)
        stat['cos_sum'] += float(np.sum(ii[right]*ii[left])+np.sum(qq[right]*qq[left]))
        stat['sin_sum'] += float(np.sum(qq[right]*ii[left])-np.sum(ii[right]*qq[left]))
    retain=max(map(int,st['delta_circular']),default=0)
    history[mode]=tuple(x[-retain:].copy() if retain else x[:0].copy() for x in joined)
    for kind,thresholds in st['thresholds_v'].items():
        for k,threshold in thresholds.items():
            mask=a>threshold
            # argmax avoids allocating an index for every below-threshold sample.
            all_above=bool(mask.all())
            head=len(a) if all_above else int(np.argmin(mask))
            tail=len(a) if all_above else int(np.argmin(mask[::-1]))
            key=(mode,kind,k);previous=tails.get(key,0)
            ep=st['exceedances'][kind][k]
            if previous and head:
                ep['episodes']-=1
                ep['longest_samples']=max(ep['longest_samples'],previous+head)
            tails[key]=previous+len(a) if all_above else tail


def replot(arrays, doc, destination):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fs=doc['fs_hz'];n=doc['samples']
    fig,axes=plt.subplots(3,4,figsize=(22,11),squeeze=False)
    te=np.r_[arrays['envelope_start_sample'],n]/fs
    for row,mode in enumerate(MODES):
        info=doc['modes'][mode]
        axes[row,0].stairs(arrays[mode+'_noise_counts'],arrays[mode+'_noise_edges_v'],lw=.8)
        edges=arrays[mode+'_noise_edges_v'];centers=(edges[:-1]+edges[1:])/2
        sigma=info['amplitude_noise_rms_v']
        if sigma>0:
            model=n*np.diff(edges)*np.exp(-.5*(centers/sigma)**2)/(sigma*np.sqrt(2*np.pi))
            axes[row,0].plot(centers,model,color='darkorange',lw=.9,label='Gaussian comparison')
        ep=doc['global_statistics']['modes'][mode]['exceedances']['local']
        lines=[f'N = {n:,} samples', *[f'> +{k}σ: {ep[str(k)]["samples_above"]:,}' for k in (3,5,7)]]
        axes[row,0].text(.98,.97,'\n'.join(lines),ha='right',va='top',transform=axes[row,0].transAxes,fontsize=7,
                         bbox={'facecolor':'white','alpha':.8,'edgecolor':'none'})
        axes[row,0].set_yscale('log');axes[row,0].set_ylim(bottom=.5)
        axes[row,0].set(xlabel='A − run mean(A) [V]',ylabel='Samples',title=mode+' · amplitude distribution')
        lo,hi=arrays[mode+'_envelope_min_v'],arrays[mode+'_envelope_max_v']
        axes[row,1].fill_between(te,np.r_[lo,lo[-1]],np.r_[hi,hi[-1]],step='post',alpha=.25,label='All-sample min/max')
        axes[row,1].plot(arrays['envelope_sample_indices']/fs,arrays[mode+'_envelope_mean_v'],lw=.8,label='Interval mean')
        for k,key,c,ls in ((3,'amplitude_threshold_v','crimson','--'),(5,'amplitude_threshold_5sigma_v','purple',':'),(7,'amplitude_threshold_7sigma_v','green','-.')):
            threshold=float(arrays[mode+'_'+key])
            axes[row,0].axvline(threshold-info['mean_amplitude_v'],color=c,ls=ls,lw=1,label=f'+{k}σ')
            axes[row,1].axhline(threshold,color=c,ls=ls,lw=1,label=f'+{k}σ')
        classes=arrays[mode+'_peak_sigma_class']
        for k,c,marker,label in ((3,'crimson','o','Interval peak 3–5σ'),(5,'purple','x','Interval peak 5–7σ'),(7,'green','*','Interval peak >7σ')):
            selected=classes==k
            axes[row,1].scatter(arrays[mode+'_peak_sample_indices'][selected]/fs,hi[selected],
                                s=3 if k!=7 else 20,color=c,marker=marker,label=label,zorder=5)
        axes[row,0].legend(fontsize=7,loc='lower left');axes[row,1].legend(fontsize=6,loc='lower left')
        axes[row,1].set(xlabel='Continuous run time [s]',ylabel='Amplitude [V]',title=mode,xlim=(0,n/fs))
        counts=arrays['global_'+mode+'_phase']
        axes[row,2].stairs(counts/counts.mean(),arrays['phase_edges_rad'],lw=.8)
        axes[row,2].axhline(1,color='gray',ls='--',lw=.8)
        axes[row,2].set(xlabel='Absolute wrapped phase [rad]',ylabel='Counts / uniform',title=mode+' · phase distribution')
        axes[row,3].plot(arrays['time_s'],arrays[mode+'_delta_phase_rad'],lw=.6)
        axes[row,3].set(xlabel='Continuous run time [s]',ylabel='Relative unwrapped phase [rad]',title=mode,xlim=(0,n/fs))
    fig.suptitle(Path(doc['input']).name+' · continuous stream within run · phase display decimated')
    fig.tight_layout();fig.savefig(destination.with_suffix('.png'),dpi=150);plt.close(fig)
    plot_iq_results(arrays,doc,destination.with_name(destination.name+'_iq.png'))


def correct(source, raw, output):
    import midas.file_reader
    started=time.monotonic();doc=json.loads(source.read_text());gs=doc['global_statistics']
    if gs['schema']!=1: raise ValueError('Repair accepts only original schema-1 products')
    with np.load(source.with_suffix('.npz')) as z: arrays={k:z[k].copy() for k in z.files}
    original=copy.deepcopy(gs)
    gs['schema']=SCHEMA;gs['config']['schema']=SCHEMA
    gs['config']['stream_continuity']='within_run';gs['config_id']=config_id(gs['config'])
    gs['episode_boundary']='continuous within run, including SPEC boundaries; split only between runs'
    states={m:{} for m in MODES};history={};tails={};offset=0;seen=0
    ref={m:None for m in MODES};sums={m:0. for m in MODES}
    signature=(raw.stat().st_size,raw.stat().st_mtime_ns)
    reader=midas.file_reader.MidasFile(str(raw),use_numpy=True)
    try:
        for event in reader:
            if event.header.is_midas_internal_event() or 'SPEC' not in event.banks:continue
            frames=np.asarray(event.banks['SPEC'].data,dtype=np.uint16).view(np.int16).reshape(-1,8)
            if seen>=len(doc['events']):
                if doc['reached_eof']:raise ValueError('Extra SPEC event in raw input')
                break
            old=doc['events'][seen];n=len(frames)
            if (old['serial'],old['start_sample'],old['samples'],old['midas_timestamp']) != (int(event.header.serial_number),offset,n,int(event.header.timestamp)):
                raise ValueError('Raw SPEC metadata differ from original product')
            trace=np.flatnonzero((arrays['sample_indices']>=offset)&(arrays['sample_indices']<offset+n))
            for mode,(ci,cq) in MODES.items():
                i=frames[:,ci].astype(float)*(2*doc['input_range_v']/65535)
                q=frames[:,cq].astype(float)*(2*doc['input_range_v']/65535)
                a,_,phase=analyze_mode(i,q,doc['iq_sign'],states[mode])
                finite=np.flatnonzero(np.isfinite(phase))
                if ref[mode] is None and len(finite):ref[mode]=float(phase[finite[0]])
                if ref[mode] is not None:phase-=ref[mode]
                arrays[mode+'_delta_phase_rad'][trace]=phase[arrays['sample_indices'][trace]-offset]
                indices=arrays[mode+'_peak_sample_indices']
                selected=np.flatnonzero((indices>=offset)&(indices<offset+n))
                arrays[mode+'_peak_delta_phase_rad'][selected]=phase[indices[selected]-offset]
                repair_boundary(gs['modes'][mode],arrays,mode,i,doc['iq_sign']*q,a,history,tails,arrays['phase_edges_rad'])
                sums[mode]+=float(a.sum())
            offset+=n;seen+=1
            if seen%100==0:print(f'{source.stem}: {seen} SPEC, {time.monotonic()-started:.1f} s',flush=True)
    finally:
        close=getattr(reader,"close",None)
        if close is not None:close()
    if seen!=len(doc['events']) or offset!=doc['samples']:raise ValueError('Incomplete raw stream')
    if signature!=(raw.stat().st_size,raw.stat().st_mtime_ns):raise ValueError('Raw file changed')
    for mode in MODES:
        if not np.isclose(sums[mode]/offset,gs['modes'][mode]['mean'],rtol=1e-12,atol=1e-14):
            raise ValueError('Raw amplitude differs from original: '+mode)
        for lag,stat in gs['modes'][mode]['delta_circular'].items():
            if arrays['global_'+mode+'_delta_'+lag].sum()!=stat['pairs']:raise ValueError('Lag histogram mismatch')
        # Amplitude moments, density, phase marginal and sample exceedances unchanged.
        for kind,thresholds in gs['modes'][mode]['exceedances'].items():
            for k,ep in thresholds.items():
                for key in ('samples_above','duration_samples','peak_v'):
                    assert ep[key]==original['modes'][mode]['exceedances'][kind][k][key]
    doc['phase_reference']='first valid run sample; unwrap continuous across SPEC boundaries; zeros masked; minimum-jump unwrap between valid samples'
    doc['time_axis']='continuous samples / fs within run; possible gaps only between runs'
    doc['continuity_correction']={'source':str(source.resolve()),'raw':str(raw.resolve()),'SPEC_events':seen,'wall_s':time.monotonic()-started,'method':'raw continuous unwrap; exact added boundary lag pairs; joined boundary episodes; amplitude products preserved'}
    output.mkdir(parents=True,exist_ok=True);dest=output/source.stem
    np.savez_compressed(dest.with_suffix('.npz'),**arrays)
    replot(arrays,doc,dest)
    # Commit JSON last: campaign resume only accepts a complete product.
    dest.with_suffix('.json').write_text(json.dumps(doc,indent=2,allow_nan=False)+'\n')
    print('Corrected',dest,flush=True)
    return dest.with_suffix('.json')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('raw',type=Path);p.add_argument('--out-dir',type=Path,required=True)
    args=p.parse_args();correct(args.source,args.raw,args.out_dir)

if __name__=='__main__':main()
