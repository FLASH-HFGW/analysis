#!/usr/bin/env python3
"""Update the IQ slides from an explicit snapshot of published v1 pilot runs.

Retain the historical 260-run context; replace its closing slide with measured
filtered-band/temperature figures. Missing pilot runs are always shown explicitly.
Generated figures, numeric tables, PDF and editable PPTX stay outside Git.
"""
import argparse
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'examples'), str(ROOT / 'reporting')]
import slide_deck as slides
import h5py
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from scipy.stats import rankdata
from iq_noise_io import read_summary
from report_noise_temperature import temperatures_by_run, summarize_product, write_csv, pearson

WORK = Path('/home/mazzitel/HFGW/analysis-work/Run2/reports')
PUBLISHED = Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/noise_temperature_pilot_minus1_20261108')
MODES = ['TM010', 'TM011', 'TM012']
TZ = ZoneInfo('Europe/Rome')
COLORS = slides.COLORS
OFFSETS = [1e5, 2.5e5, 5e5, 1e6]
SIDECOLORS = ['#3B82B8', '#007F86', '#A46E18', '#965F96']
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.grid': True, 'grid.alpha': .2, 'legend.frameon': False})


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load_snapshot(published, out):
    data = out / 'data'
    data.mkdir(parents=True, exist_ok=True)
    preset = json.loads((ROOT / 'config/noise_temperature_pilot.json').read_text())
    inputs = published / 'noise_temperature_pilot_scientific_inputs.h5'
    if digest(inputs) != preset['inputs_sha256']:
        raise ValueError('Temperature/reference input does not match its pinned checksum')
    with h5py.File(inputs, 'r') as source:
        for name in ('noise_reference.json', 'temperatures.csv', 'temperatures.schema.json'):
            (data / name).write_bytes(source['inputs'][name][:].tobytes())
    paths = sorted(published.glob('run*_noise_v1.h5'))
    runs = [int(p.name[3:8]) for p in paths]
    if len(runs) < 3 or not set(runs).issubset(preset['runs']):
        raise ValueError('Need at least three complete runs from the declared pilot')
    temperatures = temperatures_by_run(data / 'temperatures.csv', set(range(680, 940)))
    rows, metadata, configs = [], {}, []
    for run, path in zip(runs, paths):
        summary = read_summary(path)
        if (summary.get('status') != 'success' or not summary.get('reached_eof')
                or summary.get('iq_sign') != -1 or summary.get('product_version') != 'v1'):
            raise ValueError('Invalid published result: ' + str(path))
        with h5py.File(path, 'r') as source:
            cfg = source['filtered_bands/config']
            configs.append({k: np.asarray(cfg[k][()]).tolist() for k in
                            ('fs_hz', 'iq_sign', 'width_hz', 'taps', 'decimation', 'offsets_hz', 'centers_hz')})
        metadata[run] = dict(path=str(path), sha256=digest(path), samples=int(summary['samples']),
                             events=len(summary['events']), acquired_s=summary['acquired_duration_s'],
                             mean_amplitude_v={mode: summary['modes'][mode]['mean_amplitude_v'] for mode in MODES},
                             config_id=summary['global_statistics']['config_id'])
        rows.extend(summarize_product(path, run, temperatures[run], product_version='v1'))
    if any(cfg != configs[0] for cfg in configs) or len({d['config_id'] for d in metadata.values()}) != 1:
        raise ValueError('Run configurations differ')
    if any(r[f't{i}_observations'] == 0 for r in rows for i in (15, 16, 17)):
        raise ValueError('Missing in-run temperature observations')
    if len(rows) != len(runs) * 3 * 9:
        raise ValueError('Not exactly nine bands per mode and run')
    write_csv(data / 'bands_temperature_by_run.csv', rows)
    snapshot = dict(built_rome=datetime.now(TZ).isoformat(), runs=runs,
                    expected_runs=preset['runs'], missing_runs=sorted(set(preset['runs']) - set(runs)),
                    product_version='v1', iq_sign=-1, metadata=metadata, filtered_config=configs[0],
                    inputs_sha256=preset['inputs_sha256'],
                    scope='Published complete pilot runs only; incomplete runs are never extrapolated.')
    (data / 'snapshot.json').write_text(json.dumps(snapshot, indent=2) + '\n')
    return rows, temperatures, snapshot


def condensed(rows, runs):
    result = {}
    for mode in MODES:
        points = []
        for run in runs:
            group = [r for r in rows if r['mode'] == mode and r['run'] == run]
            central = next(r for r in group if r['offset_hz'] == 0)
            side = [r for r in group if r['offset_hz'] != 0]
            power = float(np.mean([r['rms_v']**2 for r in side]))
            points.append(dict(run=run, time=central['spec_midpoint_unix'],
                               cavity_mk=central['t15_median_mk'], cmn143_mk=central['t16_median_mk'],
                               cmn130_mk=central['t17_median_mk'], central_rms_v=central['rms_v'],
                               side_rms_v=np.sqrt(power), side_power_v2=power,
                               central_power_v2=central['rms_v']**2, phase_R=central['phase_resultant']))
        result[mode] = points
    return result


def statistics(points, rows):
    result = {}
    for mode, group in points.items():
        first, last = group[0], group[-1]
        temp = [r['cavity_mk'] for r in group]
        times = [r['time'] for r in group]
        side = np.array([r['side_power_v2'] for r in group])
        center = np.array([r['central_power_v2'] for r in group])
        asym = []
        for run in [r['run'] for r in group]:
            for offset in OFFSETS:
                left = next(r for r in rows if r['run'] == run and r['mode'] == mode and r['offset_hz'] == -offset)['rms_v']**2
                right = next(r for r in rows if r['run'] == run and r['mode'] == mode and r['offset_hz'] == offset)['rms_v']**2
                asym.append((right - left) / (right + left))
        result[mode] = dict(side_rms_change_pct=100*(last['side_rms_v']/first['side_rms_v']-1),
                            central_rms_change_pct=100*(last['central_rms_v']/first['central_rms_v']-1),
                            side_power_change_pct=100*(side[-1]/side[0]-1),
                            central_power_change_pct=100*(center[-1]/center[0]-1),
                            r_side_power_temperature=pearson(temp, side),
                            rho_side_power_temperature=pearson(rankdata(temp), rankdata(side)),
                            r_side_power_time=pearson(times, side),
                            r_temperature_time=pearson(times, temp),
                            r_central_power_temperature=pearson(temp, center),
                            r_side_power_temperature_without_first=pearson(temp[1:], side[1:]),
                            max_absolute_side_asymmetry_pct=100*max(map(abs, asym)),
                            central_phase_R_first=first['phase_R'], central_phase_R_last=last['phase_R'])
    return result


def figure_paths(rows, temperatures, snapshot, points, out):
    assets = out / 'assets'
    assets.mkdir(exist_ok=True)
    paths = {}
    def save(fig, name):
        fig.savefig(assets / (name + '.png'), dpi=200, bbox_inches='tight', facecolor='white')
        fig.savefig(assets / (name + '.pdf'), bbox_inches='tight', facecolor='white')
        plt.close(fig)
        paths[name] = assets / (name + '.png')
    runs = snapshot['runs']
    base = points['TM010'][0]['time']
    hours = np.array([(r['time']-base)/3600 for r in points['TM010']])
    scope = f"Pilot: {len(runs)}/{len(snapshot['expected_runs'])} planned runs; {runs[0]}–{runs[-1]}"
    fig, axes = plt.subplots(2, 1, figsize=(12, 5.1), gridspec_kw={'height_ratios': [2, 1]}, sharex=True)
    for sensor, label, color in [(15, 'Cavity', COLORS[0]), (16, 'CMN143 mixing chamber', COLORS[1]), (17, 'CMN130 mixing chamber', COLORS[2])]:
        raw = sorted(p for run in temperatures.values() for p in run[sensor])
        axes[0].plot([datetime.fromtimestamp(t, TZ) for t, _ in raw], [v for _, v in raw], color=color, lw=1, label=label)
    for mode, color in zip(MODES, COLORS):
        x = [datetime.fromtimestamp(p['time'], TZ) for p in points[mode]]
        y = [snapshot['metadata'][run]['mean_amplitude_v'][mode]*1000 for run in runs]
        axes[1].plot(x, y, 'o-', color=color, ms=4, lw=1.2, label=mode)
    for run, p in zip(runs, points['TM010']):
        axes[1].annotate(str(run), (datetime.fromtimestamp(p['time'], TZ),
                          snapshot['metadata'][run]['mean_amplitude_v']['TM010']*1000),
                          xytext=(0, 7), textcoords='offset points', fontsize=8, ha='center')
    axes[0].set(ylabel='Observed AVS temperature [mK]')
    axes[0].legend(loc='upper right', ncol=3, fontsize=9)
    axes[1].set(ylabel='Mean |I − iQ| [mV]', xlabel='Acquisition date/time · Europe/Rome (CEST)')
    axes[1].legend(loc='upper right', ncol=3, fontsize=9)
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%d %b\n%H:%M', tz=TZ))
    fig.suptitle(scope + ' · full-band mean amplitudes of selected runs', fontsize=12)
    fig.tight_layout(); save(fig, 'pilot_temperature_coverage')

    fig, axes = plt.subplots(3, 1, figsize=(12, 5.3), sharex=True)
    for ax, mode in zip(axes, MODES):
        for offset, color in zip(OFFSETS, SIDECOLORS):
            for sign, style in [(-1, '--'), (1, '-')]:
                values = sorted([r for r in rows if r['mode'] == mode and r['offset_hz'] == sign*offset], key=lambda r:r['run'])
                ax.plot(hours, [r['rms_v']*1000 for r in values], style, color=color, lw=1.2,
                        label=f'{sign*offset/1000:+g} kHz')
        ax.plot(hours, [r['central_rms_v']*1000 for r in points[mode]], 'o-', color='#26364B', ms=3, lw=1.8, label='0 kHz (includes DC)')
        ax.set_ylabel(mode+'\nRMS [mV]')
    axes[0].legend(ncol=5, fontsize=8, loc='lower center', bbox_to_anchor=(.5, 1.02))
    axes[-1].set_xlabel('Elapsed acquisition clock time from run 680 midpoint [h]')
    fig.tight_layout(); save(fig, 'filtered_band_rms_absolute')

    fig, axes = plt.subplots(1, 3, figsize=(12, 4.1), sharex=True, sharey=True)
    for ax, mode, color in zip(axes, MODES, COLORS):
        central = np.array([r['central_rms_v'] for r in points[mode]])
        side = np.array([r['side_rms_v'] for r in points[mode]])
        ax.plot(hours, 100*(central/central[0]-1), 'o-', color='#26364B', label='Central 50 kHz; includes DC')
        ax.plot(hours, 100*(side/side[0]-1), 's-', color=color, label='Eight sidebands: RMS equivalent')
        ax.axhline(0, lw=.6, color='#9AA5B4')
        ax.set(title=mode, xlabel='Elapsed clock time [h]')
    axes[0].set_ylabel('RMS change relative to run 680 [%]')
    axes[1].legend(loc='lower center', bbox_to_anchor=(.5, 1.12), fontsize=9)
    fig.tight_layout(); save(fig, 'filtered_band_relative_drift')

    fig, axes = plt.subplots(3, 2, figsize=(12, 5.6))
    norm = Normalize(float(hours.min()), float(hours.max()))
    for i, mode in enumerate(MODES):
        temp = [r['cavity_mk'] for r in points[mode]]
        for j, (metric, label) in enumerate([('central_power_v2', 'Central 50 kHz'), ('side_power_v2', 'Mean sideband power')]):
            power = np.array([r[metric] for r in points[mode]])
            change = 100*(power/power[0]-1)
            ax = axes[i, j]
            ax.plot(temp, change, lw=.6, color='#AAB3BD')
            ax.scatter(temp, change, c=hours, norm=norm, cmap='viridis', s=33, zorder=3)
            for r, x, y in zip(runs, temp, change):
                if r in (runs[0], runs[len(runs)//2], runs[-1]):
                    ax.annotate(str(r), (x, y), xytext=(3, 4), textcoords='offset points', fontsize=8)
            ax.set(title=f'{mode} · {label} · Pearson r = {pearson(temp,power):+.3f}', ylabel='Power change [%]')
            ax.title.set_fontsize(10)
    for ax in axes[-1]: ax.set_xlabel('In-run median cavity temperature [mK]')
    fig.subplots_adjust(hspace=.6, wspace=.25, right=.91, top=.94, bottom=.1)
    cax=fig.add_axes([.93,.15,.012,.7])
    fig.colorbar(ScalarMappable(norm=norm,cmap='viridis'),cax=cax,label='Elapsed acquisition clock time [h]')
    save(fig, 'noise_power_vs_cavity_temperature')

    fig, axes = plt.subplots(3, 2, figsize=(12, 5.3), sharex=True)
    for i, (mode, color) in enumerate(zip(MODES, COLORS)):
        axes[i,0].plot(hours, [r['phase_R'] for r in points[mode]], 'o-', color=color, ms=4)
        axes[i,0].set(ylabel=mode+' · phase R', ylim=(0,.6))
        for offset, sidecolor in zip(OFFSETS,SIDECOLORS):
            values=[]
            for run in runs:
                left=next(r for r in rows if r['run']==run and r['mode']==mode and r['offset_hz']==-offset)['rms_v']**2
                right=next(r for r in rows if r['run']==run and r['mode']==mode and r['offset_hz']==offset)['rms_v']**2
                values.append(100*(right-left)/(right+left))
            axes[i,1].plot(hours,values,'.-',color=sidecolor,label=f'±{offset/1000:g} kHz')
        axes[i,1].axhline(0,color='#8A96A3',lw=.6)
        axes[i,1].set(ylabel='A_side [%]', ylim=(-.65,.65))
    axes[0,0].set_title('Central-band phase resultant; 0 = no first-harmonic direction',fontsize=10)
    axes[0,1].set_title('Symmetric sidebands: (P+ − P−)/(P+ + P−)',fontsize=10)
    axes[0,1].legend(fontsize=8,ncol=2)
    for ax in axes[-1]: ax.set_xlabel('Elapsed acquisition clock time [h]')
    fig.tight_layout(); save(fig,'phase_and_sideband_symmetry')
    return paths


def historical_deck(baseline, out, version='v6'):
    model=json.loads((baseline/'slide_model.json').read_text())
    original=slides.Presentation(baseline/'iq_noise_summary_v5.pptx')
    assets=out/'assets';assets.mkdir(exist_ok=True)
    for index, slide in enumerate(model[:-1]):
        pictures=[shape for shape in original.slides[index].shapes if shape.shape_type==13]
        items=[item for item in slide['items'] if item['kind']=='image']
        if len(pictures)!=len(items):raise ValueError('Historical PPTX/model image count differs')
        for number,(picture,item) in enumerate(zip(pictures,items)):
            path=assets/f'historical_slide_{index+1:02d}_{number}.{picture.image.ext}'
            path.write_bytes(picture.image.blob);item['path']=str(path)
        slide['footer']=f'HISTORICAL 260-RUN CONTEXT · v5 | UPDATED DECK {version}'
        slide['notes']='Historical 260-run result retained from the 2 November v5 deck.\n'+slide['notes']
    deck=slides.Deck();deck.slides=copy.deepcopy(model[:-1])
    return deck


def append_pilot(deck, paths, snapshot, points, stats, version='v6', prepared='9 November 2026'):
    n=len(snapshot['runs']); expected=len(snapshot['expected_runs']); label=f'v1 PILOT · {n}/{expected} RUNS'
    source='Source: published runNNNNN_noise_v1.h5; pinned AVS metadata; snapshot.json and numeric tables.'
    def page(title, subtitle, notes):
        s=deck.new(title,subtitle,source,notes);s['footer']=label;return s
    s=page('Selected runs: temperatures and mode amplitudes',f'{n}/{expected} planned complete runs · {snapshot["runs"][0]}–{snapshot["runs"][-1]} · I − iQ',
           'Only the published complete v1 runs are included. Missing runs: '+str(snapshot['missing_runs'])+'. '
           'Temperature curves are actual AVS observations from the full campaign. Lower panel: full-band sample mean of |I-iQ| in volts, converted to mV, for each selected complete run and mode; no FIR filtering or DC subtraction. '
           'Run summaries use only finite readings from the same run within SPEC timestamp bounds. No interpolation or extrapolation.')
    deck.image(s,.5,1.75,12.3,4.75,paths['pilot_temperature_coverage'])
    s=page('Nine equal filters per mode',f'{n} complete runs · 50 kHz nominal bands · centre and ±100, ±250, ±500, ±1000 kHz',
           'Causal Kaiser FIR, 2001 taps, decimation 20; FIR state, oscillator and increment pairs remain continuous across SPEC. '
           'Band centres are offsets from baseband zero, not fitted physical resonance centres. '
           'RMS is sqrt(sum(n*rms_event^2)/sum(n)). The central band includes DC offsets; I/Q means are not subtracted. '
           'Dashed and solid lines distinguish negative and positive offsets under I−iQ.')
    deck.image(s,.5,1.8,12.3,4.8,paths['filtered_band_rms_absolute'])
    s=page('Centre and sidebands do not share one scale drift',f'End-to-end comparison: run {snapshot["runs"][0]} → {snapshot["runs"][-1]} · {n}/{expected} pilot runs',
           'Sideband RMS equivalent = sqrt(mean(P_band)) over eight equal filters; this is per-band power, not summed power over their total bandwidth. '
           'The sidebands rise together while the central TM011 band decreases. This contradicts a pure frequency-independent scaling of all measured bands. It does not isolate a physical resonance or distinguish gain, DC and spectral-shape changes.')
    deck.image(s,.55,1.9,12.15,4.45,paths['filtered_band_relative_drift'])
    s=page('Temperature associations are descriptive',f'{n} per-run observations · colours encode time · no independent-sample p-values',
           'Shown quantity is relative mean-square IQ amplitude (power), not amplitude variance after DC subtraction. '
           'Central and sideband powers show different signs of association with cavity temperature. '
           f'Time and temperature co-vary; sideband power also correlates strongly with time. {n} selected runs and many explored bands do not establish causation or independent temperature sensitivity.')
    deck.image(s,.5,1.7,12.25,4.95,paths['noise_power_vs_cavity_temperature'])
    s=page('Phase structure changes mainly in the centre',f'Central phase resultant and symmetric-sideband power balance · {n}/{expected} runs',
           'R is the magnitude of the sample-weighted circular first moment, combined as complex vectors, not an average of angles. '
           'Central phase concentration falls in TM010 and TM011. It can be affected by DC and low-frequency offsets; it is not a phase response to a coherent excitation. '
           'Sideband symmetry is measured as (P_plus-P_minus)/(P_plus+P_minus). Filter-induced adjacent-sample phase correlation is not evidence of a tone.')
    deck.image(s,.5,1.8,12.3,4.85,paths['phase_and_sideband_symmetry'])
    s=page('What the v1 pilot already establishes',f'{n}/{expected} runs available · complete 260-run context is retained on the preceding historical slides',
           'All changes in this table compare the first and last available pilot run only. '
           'The central TM011 decrease accompanies decreasing phase concentration, motivating separation of DC/low-frequency contributions. '
           'Sideband growth while cavity temperature decreases is inconsistent with a model in which fixed gain and that temperature alone set all measured noise power. '
           'Distinguish mean complex offsets from fluctuating power, and control time/gain before interpreting thermal correlations.')
    headings=[(.7,1.4,'Mode'),(2.15,2.0,'Side RMS Δ'),(4.25,2.0,'Central RMS Δ'),(6.6,2.0,'r(side power,T)'),(9.0,3.6,'Central phase R')]
    for x,w,text in headings:deck.text(s,x,2.05,w,.45,text,14,True)
    for i,(mode,color) in enumerate(zip(MODES,COLORS)):
        st=stats[mode];y=2.65+i*.62
        values=[mode,f'{st["side_rms_change_pct"]:+.2f}%',f'{st["central_rms_change_pct"]:+.2f}%',
                f'{st["r_side_power_temperature"]:+.3f}',f'{st["central_phase_R_first"]:.3f} → {st["central_phase_R_last"]:.3f}']
        for (x,w,_),text in zip(headings,values):deck.text(s,x,y,w,.45,text,18,color=color)
    first,last=points['TM010'][0],points['TM010'][-1]
    deck.text(s,.75,4.85,11.9,.55,f'Cavity temperature: {first["cavity_mk"]:.2f} → {last["cavity_mk"]:.2f} mK. Time is a strong confounder.',18,True)
    next_step = 'complete the remaining runs; ' if snapshot['missing_runs'] else 'extend to all 260 runs; '
    deck.text(s,.75,5.65,11.85,.85,'Next: '+next_step+'separate DC from fluctuations; compare temperature and gain with the common time trend.',18)
    title=deck.slides[0]
    for item in title['items']:
        if item['kind']=='text' and 'Version v5' in item['text']:
            item['text']=f'Data: 24–25 July 2026 | Version {version} · {prepared} | Filtered pilot: {n}/{expected} runs'
    title['notes']+=f'\nUpdated {prepared}: {n}/{expected} complete v1 filtered pilot runs appended; final conclusions updated.'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--published',type=Path,default=PUBLISHED)
    parser.add_argument('--baseline',type=Path,default=WORK/'iq_noise_summary_v5')
    parser.add_argument('--out',type=Path,default=WORK/'iq_noise_summary_v6')
    parser.add_argument('--version', default='v6')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    rows,temperatures,snapshot=load_snapshot(args.published,args.out)
    points=condensed(rows,snapshot['runs']);stats=statistics(points,rows)
    (args.out/'data/pilot_findings.json').write_text(json.dumps(stats,indent=2)+'\n')
    write_csv(args.out/'data/condensed_by_run.csv',[dict(mode=mode,**p) for mode in MODES for p in points[mode]])
    paths=figure_paths(rows,temperatures,snapshot,points,args.out)
    prepared=datetime.now(TZ).strftime('%-d %B %Y')
    deck=historical_deck(args.baseline,args.out,args.version)
    append_pilot(deck,paths,snapshot,points,stats,args.version,prepared)
    slides.export(deck,args.out,version=args.version,prepared=prepared)
    (args.out/'README.md').write_text(f'# IQ noise summary {args.version} — preliminary filtered pilot\n\n'
        +f'Published complete runs: {snapshot["runs"]}. Missing planned runs: {snapshot["missing_runs"]}.\n\n'
        +'Historical 260-run context from v5 is retained; six new pilot slides replace the old closing slide. '
        +'New figures are generated only from validated complete I−iQ v1 HDF5 products and pinned same-run AVS observations. '
        +'No causal or detection claim is made. Full data provenance, hashes and coverage are in data/snapshot.json.\n\n'
        +f'Rebuild from the repository: `python3 reporting/iq_noise_summary_v6/build_slides.py --version {args.version} --published {args.published} --out {args.out}`.\n')
    print(json.dumps(stats,indent=2))


if __name__=='__main__':main()
