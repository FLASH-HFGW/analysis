#!/usr/bin/env python3
"""Reorder the noise story: methods/storage, single run, ensemble, temperature.

Retain the provenance of historical plots, add current output definitions and
one validated full-run v2 example. Scientific v1/v2 are distinct from deck v9.
"""
import argparse
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'reporting'),str(ROOT/'examples')]
import slide_deck as slides
import h5py
import numpy as np
import matplotlib.pyplot as plt
from noise_temperature_pilot import validate
from iq_noise_io import read_summary

WORK=Path('/home/mazzitel/HFGW/analysis-work/Run2/reports')


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def timing_snapshot(output,campaign):
    rows=[]
    for path in sorted(output.glob('run*_noise.h5')):
        s=read_summary(path)
        if s.get('status')!='success' or not s.get('reached_eof') or s.get('product_version')!='v1':
            continue
        run=int(path.name[3:8]);t=s['performance']['timings']['total']
        state=json.loads((campaign/f'{run:05d}/state.json').read_text())
        log=campaign/f'{run:05d}/stdout-{state["cluster"]}.0.txt'
        marks={k:datetime.fromisoformat(v.replace('Z','+00:00')) for k,v in
               re.findall(r'^(Download|Analysis|Complete) run\d+ (\S+)',log.read_text(),re.M)}
        rows.append(dict(run=run,cluster=state['cluster'],analysis_min=t['wall_s']/60,
                         cpu_wall_pct=100*t['cpu_s']/t['wall_s'],
                         download_min=(marks['Analysis']-marks['Download']).total_seconds()/60,
                         product_sha256=sha(path),log_sha256=sha(log)))
    if not rows:raise ValueError('No complete current HTC timing evidence')
    return dict(built_rome=datetime.now(ZoneInfo('Europe/Rome')).isoformat(),htc_runs=rows,
        hpc_source='User-provided sacct and worker logs for jobs 4297 and 4311; v2 HDF5 performance for run 680.',
        hpc=[dict(label='HPC v1 before optimization',job=4297,analysis_min=(106*60+58)/60,download_min=215/60,cpu_wall_pct=100*6361/6418),
             dict(label='HPC v1 optimized',job=4311,analysis_min=(71*60+56)/60,download_min=119/60,cpu_wall_pct=100*4278/4316)],
        limitations='Early completed HTC subset, not a matched-run/hardware benchmark or a controlled 24/48/90-job scaling test. CPU/wall is process accounting, not hypervisor telemetry.')


def affinity_snapshot(root):
    observations=[];hashes={}
    for path in sorted(root.glob('affinity-*/diagnostic.json')):
        observed=json.loads(path.read_text())
        host=observed['host']
        probe=root/host/'diagnostic.json'
        measured=json.loads(probe.read_text())
        pinned=[p for p in observed['processes'] if p['affinity']=='0' and p['state']=='R (running)']
        observations.append(dict(offload_host=host,production_processes_on_cpu0=len(pinned),
                                 distinct_outer_cgroups=len({p['cgroup'] for p in pinned}),
                                 probe_affinity=measured['affinity'],probe_cpu_wall_pct=measured['cpu_wall_pct'],
                                 scheduler_settings=observed['settings']))
        hashes[str(path)]=sha(path);hashes[str(probe)]=sha(probe)
    if len(observations)<2:raise ValueError('Need two-host affinity evidence')
    return dict(observations=observations,source_sha256=hashes,
        conclusion='Runnable analyses in distinct offload cgroups share CPU 0 on sampled physical hosts; scheduler-assigned CPU 1 probes receive ~98% CPU. No production affinity was changed.',
        scope='Two sampled physical hosts; does not map all 95 offload environments or establish a controlled throughput benchmark.')


def build(baseline,v1,v2,out,version='v9',timings=None,affinity=None,v2_pilot=None,periodicity_directory=None):
    out.mkdir(parents=True,exist_ok=True)
    assets=out/'assets';assets.mkdir(exist_ok=True)
    data=out/'data';data.mkdir(exist_ok=True)
    shutil.copytree(baseline/'data',data/'baseline_v8',dirs_exist_ok=True)
    old=json.loads((baseline/'slide_model.json').read_text())
    original=slides.Presentation(baseline/'iq_noise_summary_v8.pptx')
    with h5py.File(v2) as source:
        gain=float(source['dc_removed/calibration/configuration/total_db'][()])
    pilot_data=periodicity_data=None
    if v2_pilot is not None:
        from iq_noise_summary_v12 import pilot
        pilot_pictures,pilot_findings,pilot_data=pilot.figures(v2_pilot,baseline,out,sha)
    deck=slides.Deck();mapping=[]
    def page(title,subtitle,section,notes='',source='Source: current analysis code and versioned HDF5 products; rebuild provenance in data/snapshot.json.'):
        s=deck.new(title,subtitle,source,notes)
        s['footer']=section+' | DECK '+version
        return s
    def reuse(number,section,subtitle=None):
        s=copy.deepcopy(old[number-1])
        pictures=[p for p in original.slides[number-1].shapes if p.shape_type==13]
        items=[item for item in s['items'] if item['kind']=='image']
        if len(pictures)!=len(items):raise ValueError('Image/model mismatch')
        for i,(picture,item) in enumerate(zip(pictures,items)):
            path=assets/f'baseline_{number:02d}_{i}.{picture.image.ext}'
            path.write_bytes(picture.image.blob);item['path']=str(path)
        if subtitle:
            for item in s['items']:
                if item['kind']=='text' and item['text']==s['subtitle']:item['text']=subtitle
            s['subtitle']=subtitle
        s['footer']=section+' | DECK '+version
        deck.slides.append(s)
        mapping.append(dict(slide=len(deck.slides),baseline_v8_slide=number,title=s['title']))
    def conclusions(title,section,findings,next_steps,source,notes=''):
        s=page(title,'Measured findings and the next checks are kept separate.',section,notes,source)
        deck.text(s,.7,1.95,5.6,.5,'What we observe',23,True,slides.COLORS[0])
        deck.text(s,7.,1.95,5.6,.5,'What to do next',23,True,slides.COLORS[1])
        deck.bullets(s,.7,2.65,5.6,findings,18,.22)
        deck.bullets(s,7.,2.65,5.6,next_steps,18,.22)
        return s

    s=page('Three-mode IQ noise: data and questions',
           'Run 2 · 24–25 July 2026 · TM010 / TM011 / TM012 · I − iQ','SCOPE',
           'Merged former opening and dataset slides. Historical full-band results cover 260 runs; the complete v1 filtered pilot covers 12 selected runs. '
           'The current v1 production and v2 pilot must not be confused with those historical datasets.')
    deck.card(s,.7,1.95,3.8,'260 runs','680–939 · historical full-band sample')
    deck.card(s,4.75,1.95,3.8,'5 MHz','Three IQ streams · 16-bit ADC',slides.COLORS[1])
    deck.card(s,8.8,1.95,3.8,'209.715 s','Per run · clock-time gaps retained',slides.COLORS[2])
    deck.bullets(s,.8,3.6,11.8,[
        'Measure amplitude, phase, IQ structure, threshold exceedances and filtered-band levels.',
        'Separate within-run fluctuations, between-run drift and temperature associations.',
        '1,000 SPEC per run; 1,048,576 complex samples per SPEC and mode.',
        ('Evidence sets: 260 historical full-band runs; 12 complete filtered v1 and v2 pilot runs.' if pilot_data is not None
         else 'Evidence sets: 260 historical full-band runs; 12 complete filtered v1 runs; one full-run v2 example here.')
    ],19,.2)

    s=page('From MIDAS to verified scientific products',
           'Two numerical passes; stream state is continuous inside each run.','METHODS',
           'Native editable blocks. The raw download occurs once; the local input is read twice. '
           'The monitor validates and publishes recovered HDF5s, including a fresh remote checksum verification. '
           'HPC workers save persistent results first; publication needs a running controller.')
    xs=[.55,3.75,6.95,10.15]
    def block(x,y,title,detail,color):
        deck.rect(s,x,y,2.65,1.55,'#FFFFFF')
        deck.rect(s,x,y,.06,1.55,color)
        deck.text(s,x+.17,y+.14,2.3,.43,title,17,True,color)
        deck.text(s,x+.17,y+.7,2.3,.7,detail,12)
    top=[('Raw MIDAS','Large .mid.gz\nSPEC + auxiliary events'),('Local scratch','One input download\nper job'),
         ('Pass 1','Run moments / ranges\nv2: complex run mean'),('Pass 2','Statistics + FIR bands\nv2: subtract run DC')]
    for x,(title,detail) in zip(xs,top):block(x,1.95,title,detail,slides.COLORS[0])
    for x in (3.32,6.52,9.72):deck.text(s,x,2.48,.4,.5,'→',25,True)
    bottom=[('Campaign merge','Compatible run summaries\n+ observed temperatures'),('GPFS publication','Copy aggregate file\nDownload / SHA-256 check'),
            ('Recover + validate','EOF, counts, convention\nversion and configuration'),('Per-run HDF5','Statistics, arrays, config\nand embedded figures')]
    for x,(title,detail) in zip(xs,bottom):block(x,4.2,title,detail,slides.COLORS[1])
    deck.text(s,11.2,3.55,.5,.55,'↓',25,True)
    for x in (3.32,6.52,9.72):deck.text(s,x,4.73,.4,.5,'←',25,True)
    deck.text(s,.7,6.1,11.9,.5,'Reset only between runs. Local scratch is cleaned after success; persistent HDF5 copies are retained.',15)

    s=page('Code structure: reading, analysis and export',
           'analyze_midas_iq_noise.py orchestrates reading, statistics, filtering and HDF5 export.','METHODS | CODE',
           'Pass 1 computes raw amplitude statistics and, in v2, ComplexMoments for the complete selected run. '
           'Pass 2 retains raw RunStatistics for comparison and feeds run-mean-subtracted IQ to FilteredBandChecks in v2. '
           'BandFilter preserves FIR tails and oscillator sample position across SPEC; FilterWorkspace shares bounded caches. '
           'Exports contain independent raw and DC-removed definitions; iq_noise_io serializes the result and embedded figures.')
    deck.rect(s,.7,1.85,11.9,.85,'#FFFFFF')
    deck.text(s,.95,2.,11.4,.4,'main(): arguments → reference / calibration → run configuration',22,True,slides.COLORS[0])
    deck.text(s,2.15,2.73,.5,.45,'↓',25,True)
    code_blocks=[(.7,'PASS 1 · establish run moments',
                  'MidasFile(..., use_numpy=True)\nanalyze_mode()\nComplexMoments.update() [v2]\n→ run means, ranges and traces',slides.COLORS[0]),
                 (4.7,'PASS 2 · process the stream',
                  'process_second_mode()\nRunStatistics.update()\nFilteredBandChecks.update()\nBandFilter.process()',slides.COLORS[1]),
                 (8.7,'EXPORT · one scientific file',
                  'RunStatistics.export()\nFilteredBandChecks.export()\nbuild_results()\nsave_results_h5()',slides.COLORS[2])]
    for x,title,body,color in code_blocks:
        deck.rect(s,x,3.25,3.55,2.45,'#FFFFFF')
        deck.rect(s,x,3.25,.06,2.45,color)
        deck.text(s,x+.17,3.43,3.18,.65,title,17,True,color)
        deck.text(s,x+.17,4.3,3.18,1.05,body,13)
    for x in (4.28,8.28):deck.text(s,x,4.3,.4,.5,'→',25,True)
    deck.text(s,.8,6.,11.7,.65,
              'Statistics: iq_noise_statistics.py · DC/AC: iq_noise_v2.py\nFIR bands: analyze_iq_filtered_bands.py · HDF5: iq_noise_io.py',15)

    s=page('Definitions: raw amplitude, DC and AC are different',
           'v1 and v2 share the raw convention; filtered v2 removes one complex mean per run.','METHODS',
           'Amplitude standard deviation in v1 is not the complex AC RMS in v2. No mean is removed separately per SPEC. '
           'The band-output coherent mean is retained in the principal filtered RMS. '
           'The nominal scalar normalization does not also apply frequency-dependent kz.')
    cards=[(.7,1.9,'Complex signal',slides.COLORS[0],'z = I − jQ     [V]',
            'I and Q are the measured voltage quadratures.'),
           (6.8,1.9,'Envelope and phase',slides.COLORS[1],'A = |z|     [V]\nφ = arg(z)     [rad]',''),
           (.7,4.,'Run DC and complex AC',slides.COLORS[2],
            'μz = mean_run(z)     [V]\nzAC = z − μz     [V]\nRMS_AC = √mean(|zAC|²)     [V]',''),
           (6.8,4.,'Mean-square voltages',slides.NAVY,
            'PDC = |μz|²     [V²]\nPAC = mean(|zAC|²)     [V²]\nPtotal = PDC + PAC     [V²]','')]
    for x,y,title,color,formula,detail in cards:
        deck.rect(s,x,y,5.8,1.85,'#FFFFFF')
        deck.rect(s,x,y,.06,1.85,color)
        deck.text(s,x+.2,y+.14,5.3,.4,title,19,True,color)
        deck.text(s,x+.2,y+.69,5.3,1.05,formula,20)
        if detail:deck.text(s,x+.2,y+1.3,5.3,.4,detail,13)
    deck.text(s,.8,6.12,11.7,.6,
              f'σA = std(A) differs from RMS_AC. Nominal gain: {gain:g} dB, specified in the calibration JSON.\nVoltages ÷ 10^(GdB/20); mean-square voltages ÷ 10^(GdB/10); phase unchanged. V² are not RF watts.',14)

    s=page('Outputs: a small number of aggregate products',
           'Current production formats; legacy NPZ/JSON/PNG sidecars are not the publication target.','PRODUCTS',
           'Scientific product versions v1/v2 differ from the presentation version. Per-run v1 worker output is renamed with _v1 at publication. '
           'Comparison HDF5s include tables, figures and provenance. A final comparison requires the complete campaign.')
    outputs=[('PER RUN','runNNNNN_noise_v1.h5 / runNNNNN_noise_v2.h5','Raw diagnostics; bands; v2 DC/AC and calibration.'),
             ('CAMPAIGN','noise_temperature_comparison_v1.h5 / _v2.h5','Weighted per-run tables, temperature associations and figures.'),
             ('FROZEN INPUTS','noise_temperature_pilot_scientific_inputs.h5','Shared reference and temperature CSV/schema, pinned by checksum.'),
             ('LOCAL WORK','Logs / job states / report assets / PDF + PPTX','Operational records and review artifacts; not loose GPFS science outputs.')]
    for i,(label,name,detail) in enumerate(outputs):
        y=1.9+i*1.12
        deck.text(s,.75,y,2.,.4,label,14,True,slides.COLORS[i%3])
        deck.text(s,2.8,y,9.8,.4,name,17,True)
        deck.text(s,2.8,y+.46,9.8,.45,detail,16)

    s=page('Inside the HDF5: data, context and figures together',
           'Storage convention: GPFS holds large raw files and aggregated scientific products.','PRODUCTS',
           'This is the project storage convention, not a claim that GPFS enforces a universal minimum file size. '
           'The example tree is from the actual v2 run 680. Historical raw groups remain explicitly raw in a v2 file. '
           'PNG payloads are stored as uint8 datasets; list-of-record metadata may be JSON encoded in HDF5.')
    deck.rect(s,.65,1.95,6.2,3.6,'#FFFFFF')
    deck.text(s,.85,2.12,5.8,.4,'run00680_noise_v2.h5',18,True,slides.COLORS[0])
    groups=[('Version tags','schema_version / product_version'),('summary','Metadata + raw statistics'),
            ('arrays','Shared sample / time arrays'),('modes','Raw IQ, histograms and traces'),
            ('filtered_bands','Configuration + 3 modes × 9 bands'),('dc_removed','Full-band DC/AC moments + gain'),
            ('figures','Embedded PNG byte arrays')]
    for i,(name,detail) in enumerate(groups):
        y=2.72+i*.36
        deck.text(s,1.05,y,2.15,.34,name,14,True)
        deck.text(s,3.3,y,3.25,.34,detail,12)
    deck.bullets(s,7.2,2.,5.4,[
        'One scientific file per run; comparison tables and figures in one campaign HDF5.',
        'Keep versions, units, configuration, calibration and provenance together.',
        'Scratch, watch logs and loose plot files stay in local work areas.'
    ],18,.25)
    deck.text(s,.8,5.95,11.6,.65,'GPFS publication copies and verifies the HDF5; it does not delete persistent local copies.',17,True)

    if timings is not None:
        (data/'execution_timings.json').write_text(json.dumps(timings,indent=2)+'\n')
        rows=timings['htc_runs']
        median=lambda key:float(np.median([r[key] for r in rows]))
        with h5py.File(v2) as source:
            wall=float(source['summary/performance/timings/total/wall_s'][()])
            cpu=float(source['summary/performance/timings/total/cpu_s'][()])
        s=page('HTC and HPC: per-run time versus pool throughput',
            f'One CPU per job · HTC: first {len(rows)} completed v1 runs · HPC: run 680 · not a matched hardware benchmark',
            'EXECUTION | MEASURED SNAPSHOT',timings['limitations']+' '
            'HPC timing uses the srun step; HTC and v2 use Python analysis timers, including plots. '
            'Queue waiting and final controller publication are excluded. A low CPU/wall ratio identifies time outside process CPU; it does not diagnose whether scheduling, throttling or I/O caused it.',
            'Sources: user-provided Slurm accounting (4297, 4311), v2 run 680 HDF5, current HTC HDF5/logs; data/execution_timings.json.')
        if affinity is not None:
            (data/'affinity_diagnosis.json').write_text(json.dumps(affinity,indent=2)+'\n')
            s['notes']+=' '+affinity['conclusion']+' '+affinity['scope']
            s['source']='Sources: Slurm/HDF5 timers; HTC logs; measured offload affinity and CPU probes. Evidence and hashes in data/.'
        headings=[(.7,4.5,'Evidence'),(5.2,2.0,'Analysis [min]'),(7.8,2.2,'Download [min]'),(10.55,2.,'CPU / wall')]
        for x,w,label in headings:deck.text(s,x,1.95,w,.4,label,15,True)
        values=[(r['label'],f"{r['analysis_min']:.1f}",f"{r['download_min']:.1f}",f"{r['cpu_wall_pct']:.1f}%") for r in timings['hpc']]
        values += [('HPC v2: full run',f'{wall/60:.1f}','—',f'{100*cpu/wall:.1f}%'),
                   (f'HTC v1: median of {len(rows)}',f"{median('analysis_min'):.1f}",f"{median('download_min'):.1f}",f"{median('cpu_wall_pct'):.1f}%")]
        for i,row in enumerate(values):
            for (x,w,_),value in zip(headings,row):deck.text(s,x,2.55+i*.51,w,.4,value,17)
        fast=[r for r in rows if r['cpu_wall_pct']>=90]
        slow=[r for r in rows if r['cpu_wall_pct']<90]
        findings=[
            f'HTC variability: {len(fast)} completed runs near full CPU use; {len(slow)} below 90%. Cause not measured; this is not a controlled 24/48/90-job scaling test.',
            'HPC: unused GPU reserved; cygno/CPU access rejected. HTC: 95 workers × 8 CPUs, but ~6 GB RAM permits one current 4-GB job per worker.',
            'Tokens do not cap job count; a persistent monitor publishes results. Next: diagnose CPU availability and measure campaign throughput.'
        ]
        if affinity is not None:
            counts=sorted(r['production_processes_on_cpu0'] for r in affinity['observations'])
            findings=[
                f'Measured contention on two physical hosts: {counts[0]} and {counts[-1]} analyses pinned to CPU 0; scheduler-assigned CPU 1 probes reached ~98% CPU.',
                '95 offload environments are not 95 physical nodes. HPC reserves an unused GPU; cygno access to the CPU partition was rejected.',
                'Before mass v2: coordinate outer/inner CPU affinity, benchmark allocated cores, then scale. Tokens do not impose a four-job cap.'
            ]
        deck.bullets(s,.8,4.9,11.8,findings,15,.12)

    # Single-run section: retain the measured figures and their original scope.
    for number in (4,5,6,7):reuse(number,'SINGLE RUN | RAW DIAGNOSTICS')
    reuse(9,'SINGLE RUN | SPECTRAL CHECK',
          'Run 680 · first five SPEC blocks (1.049 s) · continuous-stream spectrum and covariance.')
    if periodicity_directory is not None:
        from iq_noise_summary_v12 import pilot
        plot,periodicity_data=pilot.periodicity(periodicity_directory,assets,sha)
        spectral=deck.slides[-1]
        for item in spectral['items']:
            if item['kind']=='image':item['path']=str(plot)
        deck.text(spectral,10.15,5.55,2.55,.98,
                  'Lag = time separation.\n1 sample = 0.2 μs.\nRe R / R0 = real\nnormalized covariance.\nZero lag = 1 (not shown).',11)
        spectral['notes']+=' '+periodicity_data['definition']+' Positive: concordant IQ fluctuations; negative: opposite; zero: no linear real-part correlation, not statistical independence.'

    s1=validate(v1,680,'v1');s2=validate(v2,680,'v2')
    metrics=[]
    with h5py.File(v1) as a,h5py.File(v2) as b:
        if s1['samples']!=s2['samples']:raise ValueError('v1/v2 sample scopes differ')
        gain=float(b['dc_removed/calibration/configuration/total_db'][()])
        for mode in ('TM010','TM011','TM012'):
            def central(source):
                group=source[f'filtered_bands/modes/{mode}/band_04/events']
                return float(np.sqrt(np.average(group['rms_v'][:]**2,weights=group['n'][:])))
            before,after=central(a),central(b)
            metrics.append(dict(mode=mode,central_v1_mv=before*1e3,central_v2_mv=after*1e3,
                                change_pct=100*(after/before-1)))
        h5_roots=list(b)
    (data/'run680_v2_dc_comparison.json').write_text(json.dumps(metrics,indent=2)+'\n')
    fig,ax=plt.subplots(figsize=(10,3.7))
    x=np.arange(3)
    ax.bar(x-.17,[r['central_v1_mv'] for r in metrics],.34,label='v1: DC retained',color='#7657A6')
    ax.bar(x+.17,[r['central_v2_mv'] for r in metrics],.34,label='v2: one run mean removed',color='#007F86')
    for i,row in enumerate(metrics):ax.text(i,max(row['central_v1_mv'],row['central_v2_mv'])+.1,f"{row['change_pct']:+.2f}%",ha='center')
    ax.set(xticks=x,xticklabels=[r['mode'] for r in metrics],ylabel='Central-band RMS at ADC [mV]',ylim=(0,7.1))
    ax.legend(ncol=2,loc='upper right');ax.spines[['top','right']].set_visible(False)
    fig.tight_layout();path=assets/'run680_dc_comparison.png';fig.savefig(path,dpi=200);plt.close(fig)
    s=page('Run 680 v2: the DC contribution is measurable',
           f'Full run · {len(s2["events"]):,} SPEC · same samples and filters · before / after run-DC removal',
           'SINGLE RUN | v2',
           f'Complete validated v2 product, normalized with nominal {gain:g} dB; bars retain ADC volts to isolate DC subtraction. '
           'This one run does not yet establish temperature behaviour or a campaign-wide DC correction.',
           'Source: complete published run00680_noise_v1.h5 and run00680_noise_v2.h5; hashes in snapshot.json.')
    deck.image(s,.8,1.85,11.8,4.15,path)
    deck.text(s,.9,6.1,11.5,.5,f'Normalization is separate: current nominal gain {gain:g} dB; equivalent input volts, not calibrated RF power.',16)
    conclusions('Single-run conclusions and next steps','SINGLE RUN | CONCLUSIONS',[
        'Amplitude tails and IQ maxima depend on the population being plotted.',
        'Phase winding alone does not identify a coherent periodic signal.',
        f"Run-DC removal changes central TM011 RMS by {next(r['change_pct'] for r in metrics if r['mode']=='TM011'):+.2f}% in run 680."
    ],[
        ('Use the complete v2 pilot to separate complex offsets from fluctuations.' if pilot_data is not None else 'Complete the v2 pilot and retain DC/AC separately for every mode.'),
        'Validate the magnitude-noise model and low-amplitude phase artefacts.',
        'Obtain numerical kz(f) curves before a full RF calibration.'
    ],'Source: run 680 raw diagnostics, five-SPEC spectral check, and complete run 680 v2.',
       'The RMS change is calculated on the same full run. No repeating-tone or calibrated-temperature claim is made.')

    s=page('Merge compatible summaries, not disconnected streams',
           'Ensemble statistics preserve sample weighting and the boundaries between runs.','ENSEMBLE | METHOD',
           'The historical 260-run amplitude context is retained as a separately identified evidence set. '
           'Histograms are added only with compatible edges; moment merging includes between-run mean differences. '
           'Within-run phase/episode histories are never joined across independent runs.')
    deck.bullets(s,.9,2.,11.5,[
        'Validate EOF, run identity, IQ sign, sample counts, scientific version and configuration.',
        'Sum common-bin counts; merge sample-weighted moments with between-run mean terms.',
        'Keep local thresholds distinct from thresholds based on the fixed run-680 pilot reference.',
        'Never mix raw v1 and DC-removed v2 filtered statistics in the same aggregate.',
        'Preserve per-run time and temperature summaries; do not treat all samples as independent observations.'
    ],20,.28)
    for number in (11,12,14,17,18):reuse(number,'ENSEMBLE | HISTORICAL 260-RUN CONTEXT')
    conclusions('Ensemble conclusions and next steps','ENSEMBLE | CONCLUSIONS',[
        'The three mean amplitudes share a strong drift across 260 runs.',
        'Stable normalized shape does not imply constant level or full stationarity.',
        'Threshold exceedances are descriptive counts, not detection significance.'
    ],[
        'Compare current filtered reconstruction with the historical full-band baseline.',
        'Separate mean complex offsets, AC variance and coherent-band contributions.',
        'Test a common trend without labelling it as independently measured gain.'
    ],'Source: historical 260-run summaries retained from v5/v8; current v1 production is a separate campaign.')

    if pilot_data is not None:
        pilot.append(deck,page,pilot_pictures,pilot_findings)
    else:
        for number in (20,21,22,23,24):reuse(number,'TEMPERATURE | COMPLETE 12-RUN v1 PILOT')
        reuse(25,'TEMPERATURE | COMPLETE 12-RUN v1 PILOT')
        s=deck.slides[-1]
        for item in s['items']:
            if item['kind']=='text' and item['text']==s['title']:item['text']='Temperature: conclusions and next steps'
            elif item['kind']=='text' and item['text'].startswith('Next:'):
                item['text']=slides.wrap('Next: complete the DC-removed v2 pilot; compare temperature with time and common trends; calibrate the frequency response.',item['w'],item['size'])
        s['title']='Temperature: conclusions and next steps'
        s['notes']+=' v2 currently contributes one full-run example only; no mixed-version thermal regression is shown.'

    stamp=datetime.now(ZoneInfo('Europe/Rome')).isoformat()
    snapshot=dict(built_rome=stamp,deck_version=version,baseline=str(baseline),
        baseline_model_sha256=sha(baseline/'slide_model.json'),baseline_pptx_sha256=sha(baseline/'iq_noise_summary_v8.pptx'),
        run680_v1=dict(path=str(v1),sha256=sha(v1)),run680_v2=dict(path=str(v2),sha256=sha(v2)),
        h5_roots_v2=h5_roots,scientific_gain_db=gain,
        scopes=dict(historical_full_band_runs=260,filtered_v1_pilot_runs=12,v2_runs_used_here=pilot_data['runs'] if pilot_data else [680]),
        reused_slide_mapping=mapping,
        affinity_diagnosis_included=affinity is not None,
        v2_pilot=pilot_data,periodicity=periodicity_data,
        note='Reorganization draft; baseline charts remain tied to their original evidence sets; v2 is not merged into v1.')
    (data/'snapshot.json').write_text(json.dumps(snapshot,indent=2)+'\n')
    slides.export(deck,out,version=version,prepared=datetime.now(ZoneInfo('Europe/Rome')).strftime('%-d %B %Y'))
    (out/'README.md').write_text(f'# IQ noise summary {version} — reorganized narrative\n\n'
        'Scope/methods/storage → single run and conclusions → ensemble and conclusions → temperatures and conclusions.\n'
        'Scientific evidence sets are labelled separately; full v2 pilot inclusion is recorded in data/snapshot.json.\n'
        'Diagram blocks and text are editable in PPTX. Numerical comparison and provenance are in data/.\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,default=WORK/'iq_noise_summary_v8')
    parser.add_argument('--v1',type=Path,default=WORK/'pilot_snapshot_20261109/run00680_noise_v1.h5')
    parser.add_argument('--v2',type=Path,default=WORK/'noise_v2_development_20261109/run680_full_published/run00680_noise_v2.h5')
    parser.add_argument('--out',type=Path,default=WORK/'iq_noise_summary_v9')
    parser.add_argument('--version',default='v9')
    parser.add_argument('--include-timings',action='store_true')
    parser.add_argument('--affinity-diagnostics',type=Path)
    parser.add_argument('--v2-pilot-directory',type=Path)
    parser.add_argument('--periodicity-directory',type=Path)
    parser.add_argument('--htc-output',type=Path,default=WORK/'noise_fullrange_v1_20261109')
    parser.add_argument('--htc-campaign',type=Path,default=Path('/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/noise_fullrange_v1_20261109'))
    args=parser.parse_args()
    timings=timing_snapshot(args.htc_output,args.htc_campaign) if args.include_timings else None
    affinity=affinity_snapshot(args.affinity_diagnostics) if args.affinity_diagnostics else None
    if affinity is not None and timings is None:parser.error('--affinity-diagnostics requires --include-timings')
    build(args.baseline,args.v1,args.v2,args.out,args.version,timings,affinity,args.v2_pilot_directory,args.periodicity_directory)
