"""Build the targeted Run 1670 report from compact tables and receipts."""
import csv
import hashlib
import json
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from change1670 import read
from diagnose1670 import MODES, STUDY, FS, save
from report_longitudinal import Deck, export, baseline

VALIDATION=STUDY/'validation/run1670'
FIGURES=STUDY/'figures/run1670'
PRESENTATION=STUDY/'presentation/run1670'
C=('#007F86','#7657A6','#D98726')


def info(path):
    return json.loads(path.read_text())


def main():
    FIGURES.mkdir(exist_ok=True)
    deck=Deck()
    receipt=info(VALIDATION/'stream.json')
    scan=info(VALIDATION/'change_scan.json')
    summaries=read('summary')
    chronology=read('LO_chronology')
    traces=read('time_series')
    one=[r for r in traces if r['nominal_bin_s']=='1.0']
    short=[r for r in traces if r['nominal_bin_s']=='0.1']
    changes=read('change_scan')
    strong=[]
    for r in changes:
        if r['block_s']!='5':
            continue
        other=next(s for s in changes if s['block_s']=='10' and
                   (s['mode'],s['observable'])==(r['mode'],r['observable']))
        for kind in ('step','trend'):
            key=f'familywise_{kind}_fraction'
            if max(float(r[key]),float(other[key]))<=.05:
                strong.append((r['mode'],r['observable'],kind,int(r['split_s']),float(r[key]),float(other[key])))
    rms_step = [r for r in changes if r['block_s']=='10' and r['observable']=='RMS_V']
    power_step = [r for r in changes if r['block_s']=='10' and r['observable']=='full_band_PSD_V2']
    def percent(rows):
        return ' / '.join(f"{100*(float(r['mean_after'])/float(r['mean_before'])-1):+.2f}%"
                          for r in rows)
    steps = dict(rms=percent(rms_step),power=percent(power_step))
    comparison=[]
    raw_compare={1429:baseline(),1670:summaries}
    for run in (1666,1676):
        raw_compare[run]=info(STUDY/f'validation/longitudinal/{run}.json')['modes']
    archive=read('ROOT_comparison')
    track={}
    for run in (1429,1669,1670,1671):
        with (STUDY/f'tables/retune/{run}_full_band_lines.csv').open() as stream:
            q=csv.DictReader(stream)
            track[run]=next(r for r in q if r['mode']=='TM012' and r['screen']=='full_band_rank'
                            and abs(float(r['IF_Hz']))>=500)
    for run in (1429,1666,1669,1670,1671,1676):
        for mode in MODES:
            raw=next((r for r in raw_compare.get(run,[]) if r['mode']==mode),{})
            archived=next((r for r in archive if r['run']==str(run) and r['mode']==mode),{})
            rms=archived.get('RMS_V',raw.get('RMS_V',raw.get('rms_V')))
            line=track.get(run,{}) if mode=='TM012' else {}
            comparison.append(dict(run=run,mode=mode,RMS_V=rms,T3=raw.get('T3'),T5=raw.get('T5'),
                 T7=raw.get('T7'),T7_Gaussian_ratio=raw.get('matched_ratio',raw.get('matched_T7_ratio')),
                 line_Hz=line.get('IF_Hz'),occupancy=line.get('occupancy_count'),
                 raw_scope=('validated existing or targeted analysis' if raw else 'ROOT only')))
    save('comparison',comparison)

    def slide(title,sub,notes):
        s=deck.new(title,sub,source='FLASH Run3-B · archived ROOT and one Run 1670 raw pass',notes=notes)
        s['footer']='FLASH RUN3-B  |  RUN 1670 TARGETED STUDY'
        return s

    def text(title,sub,items):
        s=slide(title,sub,' '.join(items))
        deck.bullets(s,.65,1.85,12,items,size=19,gap=.22)

    def plot(name,title,sub,xlabel,ylabel,draw,notes):
        f,axes=plt.subplots(1,3,figsize=(15,5.0),layout='constrained')
        for mode,ax in zip(MODES,axes):
            draw(mode,ax)
            ax.set(title=mode,xlabel=xlabel,ylabel=ylabel)
            ax.grid(alpha=.18)
            if ax.get_legend_handles_labels()[1]:
                ax.legend(fontsize=8)
        path=FIGURES/f'{name}.png'
        f.savefig(path,dpi=145)
        plt.close(f)
        deck.image(slide(title,sub,notes),.5,1.72,12.3,4.95,path)

    def lines(source,x,fields):
        def draw(mode,ax):
            q=[r for r in source if r['mode']==mode]
            for j,(key,label,scale) in enumerate(fields):
                t=[float(r[x]) for r in q if r[key]!='']
                y=[float(r[key])*scale for r in q if r[key]!='']
                ax.plot(t,y,lw=1,color=C[j%len(C)],label=label)
        return draw

    text('FLASH Run 1670 targeted diagnostic','Archived LO transition and a complete 209.7152 s acquisition',
         ['Run 1670 is an additional targeted analysis. The 24-run study and Run 1429 reference remain in place.',
          'One full raw pass produced I/Q moments, distribution histograms, phase observables and exact sparse tail products.',
          'The archived 1 s PSD covers 209 complete seconds. The v50 PSD and complex linear ACF use only the first 1.048576 s.'])
    text('Three LO values changed between runs','ODB key last-written times · 21 November 2026 UTC',
         ['Rohde & Schwarz primary: 8,743,664,000 → 8,743,655,000 Hz at 08:21:56.',
          'Teledyne CH1: 43,331,000 → 43,330,000 Hz at 08:21:59.',
          'Teledyne CH2: 102,179,000 → 102,199,000 Hz at 08:22:02.',
          'Run 1670 BOR, beginning LOSC record and EOR agree on the new settings. LocalOscill applies settings to the instruments. The initiating actor is unknown.'])
    text('Acquisition and RF configuration','Verified archived settings',
         ['The documented frontend uses a Rohde & Schwarz SMA100B, a Teledyne T3AFG500 and a Keysight EXG pump.',
          'Pump on/off, 7.891 GHz and power setting −6.1 match the neighboring records. Same ADC scale, 5 MS/s and three I/Q pairs.',
          'The nominal RF setpoints move by −9, −10 and +11 kHz; the nominal digital centers stay at +1.25 MHz.',
          'The VNA nominal setpoints and Completed status were written at 08:21:26, 30 s before the first LO write.',
          'LOSC is a single beginning-of-run ODB snapshot. The archive supplies no continuous hardware frequency readback.'])
    constellation=read('constellation')
    def iq(mode,ax):
        q=[r for r in constellation if r['mode']==mode]
        ax.scatter([float(r['I_V'])*1000 for r in q],[float(r['Q_V'])*1000 for r in q],
                   c=np.log10([int(r['count']) for r in q]),s=7,cmap='viridis')
        ax.set(xlim=(-105,105),ylim=(-105,105),aspect='equal')
    plot('IQ_constellation','Full-run I/Q constellation','Color represents log₁₀ samples per ADC bin',
         'I (mV)','−Q hardware (mV)',iq,'All samples contribute to the full 128 × 128 ADC grid. Display focuses on the central region.')
    fine=read('prefix_IQ')
    def prefix_iq(mode,ax):
        q=[r for r in fine if r['mode']==mode]
        ax.scatter([float(r['I_mV']) for r in q],[float(r['Q_mV']) for r in q],
                   c=np.log10([int(r['count']) for r in q]),s=5,cmap='viridis')
        ax.set(aspect='equal')
    plot('prefix_IQ','Fine I/Q constellation of the v50 prefix','First 1.048576 s only · 1 mV bins',
         'I (mV)','−Q hardware (mV)',prefix_iq,
         'Fine display is restricted to the selected prefix. The coarse constellation and marginal distributions use the full run.')
    def marginal(mode,ax):
        q=[r for r in constellation if r['mode']==mode]
        for key,c in zip(('I_V','Q_V'),C):
            a={}
            for r in q:
                a[float(r[key])*1000]=a.get(float(r[key])*1000,0)+int(r['count'])
            x=sorted(a)
            ax.step(x,np.array([a[k] for k in x])/sum(a.values()),where='mid',label=key[0],color=c)
        ax.set(xlim=(-105,105),yscale='log')
    plot('IQ_marginals','Full-run I and Q marginals','Common ADC bin width','Voltage (mV)','Bin probability',
         marginal,'Q denotes minus hardware Q. Moments and pseudo-covariance appear in the summary table.')
    amp=read('amplitude')
    for name,key,title,ylabel in [('PDF','normalized_PDF','Normalized amplitude PDF','Normalized density'),
                                 ('CCDF','observed_CCDF','Normalized amplitude CCDF','Survival probability')]:
        def ampdraw(mode,ax):
            q=[r for r in amp if r['mode']==mode and float(r['left_A_over_sigma'])<=10]
            x=np.array([float(r['left_A_over_sigma']) for r in q])
            y=np.array([float(r[key]) for r in q])
            ax.step(x,np.where(y>0,y,np.nan),where='post',label='Measured',color=C[0])
            center=x+(x[1]-x[0])/2 if name=='PDF' else x
            ax.plot(center,np.exp(-center**2/2)*(center if name=='PDF' else 1),label='Rayleigh',color=C[1])
            ax.set_yscale('log')
        plot(name,title,'Amplitude scaled by the v50 histogram-fit Rayleigh parameter','|z| / σ',ylabel,
             ampdraw,'Binned full-run distributions. Exact T3/T5/T7 counts use the native amplitudes before histogramming.')
    phase=read('phase')
    def phasedraw(mode,ax):
        for kind,color in zip(('phase','increment_1','increment_10','increment_100'),(*C,'#555555')):
            q=[r for r in phase if r['mode']==mode and r['kind']==kind]
            ax.plot([float(r['angle_rad']) for r in q],[float(r['mass']) for r in q],label=kind,color=color,lw=1)
    plot('phase','Full-run phase and phase increments','Lags 1, 10 and 100 samples','Angle (rad)','Bin probability',
         phasedraw,'Phase increments use angle(z[t] conj(z[t−lag])) and cross contiguous MIDAS event boundaries. Zero amplitudes are excluded.')
    plot('means','One-second I/Q means','Includes the final partial second','Received time (s)','Mean (mV)',
         lines(one,'start_s',[('mean_I_V','I',1000),('mean_Q_V','Q',1000)]),
         'Time coordinates are based on received samples, with calibrated channel delays unavailable.')
    plot('covariance','One-second variances and covariance','Full-run time coverage','Received time (s)','Variance or covariance (mV²)',
         lines(one,'start_s',[('var_I_V2','Var I',1e6),('var_Q_V2','Var Q',1e6),('cov_I_Q_V2','Cov I,Q',1e6)]),
         'Properness and circular phase means are available for each window.')
    plot('phase_time','Time-resolved circular phase moments','One-second unit-phasor means','Received time (s)','Mean phasor component',
         lines(one,'start_s',[('phase_mean_cos','Real',1),('phase_mean_sin','Imaginary',1)]),
         'Zero amplitudes contribute zero to the vectors. Full-run phase histograms exclude zeros.')
    def rms(mode,ax):
        for rows,label,color in [(short,'100 ms',C[0]),(one,'1 s',C[1])]:
            q=[r for r in rows if r['mode']==mode]
            ax.plot([float(r['start_s']) for r in q],[1000*float(r['RMS_V']) for r in q],
                    alpha=.65,lw=.8,label=label,color=color)
    plot('RMS_time','RMS throughout Run 1670','100 ms and 1 s disjoint bins, exposure-correct final bin',
         'Received time (s)','RMS (mV)',rms,'Weighted volt-squared sums agree with the archived full-run RMS.')
    def rates(mode,ax):
        for rows,label,color in [(short,'100 ms',C[0]),(one,'1 s',C[1])]:
            q=[r for r in rows if r['mode']==mode]
            ax.plot([float(r['start_s']) for r in q],[int(r['T7'])*FS/int(r['samples']) for r in q],
                    lw=.7,alpha=.6,label=label,color=color)
    plot('T7_time','Exact T7 rate through the run','Sparse samples and clusters retained separately',
         'Received time (s)','T7 samples/s',rates,'T3 and T5 counts at both bin sizes are in the time-series table.')
    def rates_all(mode,ax):
        q=[r for r in one if r['mode']==mode]
        for order,c in zip((3,5,7),C):
            y=np.array([int(r[f'T{order}'])*FS/int(r['samples']) for r in q])
            ax.plot([float(r['start_s']) for r in q],np.where(y>0,y,np.nan),
                    lw=.8,color=c,label=f'T{order}')
        ax.set_yscale('log')
    plot('tails_1s','Exact T3, T5 and T7 rates','One-second bins with measured exposure',
         'Received time (s)','Samples/s',rates_all,
         'Zero rates are omitted on the logarithmic axis and retained in the tables.')
    plot('prefix_PSD','v50 selected-prefix PSD','Mean-subtracted Hann estimator over the first 5,242,880 samples',
         'Signed frequency (Hz)','PSD (V²/Hz)',
         lambda mode,ax:(lines(read('prefix_PSD'),'frequency_Hz',[('PSD_V2_Hz','Prefix PSD',1)])(mode,ax),
                         ax.set_yscale('log')),
         '1.048576 s only. The ordered ROOT PSD below spans 209 complete 1 s windows.')
    plot('prefix_ACF','v50 selected-prefix complex linear ACF','Centered linear covariance normalized at lag zero',
         'Lag (µs)','Normalized covariance',
         lines(read('prefix_ACF'),'lag_us',[('g_real','Real',1),('g_imag','Imaginary',1),('g_abs','Magnitude',1)]),
         'FFT zero-padding and N−lag normalization. Upper-envelope time constants and first persistent magnitude crossing are descriptive.')
    plot('ordered_PSD_power','Ordered ROOT PSD power','209 complete one-second PSD windows',
         'Received time (s)','Integral (V²)',
         lines(read('spectral_seconds'),'received_s',[('power_V2','Full band',1)]),
         'Native 100 Hz archived products, integrated over the full sampled band.')
    def spectral_draw(mode,ax):
        bins=read('line_seconds')
        kinds=sorted({r['kind'] for r in bins if r['mode']==mode})
        for kind,c in zip(kinds,C):
            q=[r for r in bins if r['kind']==kind and r['mode']==mode]
            ax.plot([int(r['second']) for r in q],[float(r['normalized_ratio']) for r in q],
                    lw=.8,label=kind,color=c)
        ax.axhline(3,color='#666666',linestyle=':',lw=1)
    plot('line_time','Narrowband features during Run 1670','TM012 old IF, new IF and main-branch prediction',
         'Received time (s)','Normalized local ratio',spectral_draw,
         'The leading full-band non-DC TM012 peak shifts +29 kHz with high occupancy. The main-branch prediction is −11 kHz.')
    def peak_view(mode,ax):
        q=[r for r in read('full_band_lines') if r['mode']==mode and r['screen']=='full_band_rank']
        x=np.array([float(r['IF_Hz'])/1e6 for r in q])
        y=np.array([float(r['mean_ratio']) for r in q])
        occ=np.array([int(r['occupancy_count'])/int(r['windows']) for r in q])
        ax.scatter(x,y,s=14+30*occ,c=occ,cmap='viridis',vmin=0,vmax=1)
        ax.set(xlim=(-2.5,2.5),yscale='log')
    plot('archived_peaks','Full-band archived narrowband candidates',
         'Top 50 local maxima per mode · color and size encode occupancy',
         'Signed digital frequency (MHz)','Mean / local background',peak_view,
         'Native 100 Hz PSD products over all 209 complete windows. The screen includes all sampled frequencies.')
    def stages(mode,ax):
        q=read('temperature')
        t0=int(datetime.fromisoformat(next(r['first_adc_utc'] for r in archive
                                           if r['run']=='1670')).timestamp())
        for ch in dict.fromkeys(r['channel'] for r in q):
            a=[r for r in q if r['channel']==ch and r['usable']=='True']
            ax.plot([int(r['time_unix'])-t0 for r in a],[float(r['value_K']) for r in a],
                    'o-',markersize=3,label=':'.join(ch.split(':')[:2]))
        ax.set_yscale('log')
    plot('temperatures','Cryogenic temperature evolution','Shared sensors shown under each mode','Seconds from first ADC header',
         'Temperature (K)',stages,'Cavity, TWPA stage, two mixing chamber sensors and the 4 K stage proxy, subject to sensor mapping and timestamp support.')
    text('Within-run change diagnostics','Joint maximum across modes, observables and scan types',
         [f'{scan["tested_series"]} time series, 999 permutations and contiguous 5 s and 10 s blocks.',
          f'{len(strong)} candidates crossed both exploratory familywise thresholds. The common power step occurs at 117–119 s.',
          f'Mean RMS steps TM010 / TM011 / TM012: {steps["rms"]}. Integrated PSD: {steps["power"]}.',
          'The screen did not flag T7 rate or the TM012 line ratio at this boundary.',
          f'TM012 line-ratio Spearman coefficients: {scan["TM012_line_T7_spearman"]:.3f} with T7 and {scan["TM012_line_RMS_spearman"]:.3f} with RMS.',
          'Short blocks preserve dependence within blocks. They cannot establish stationarity or an LO setting change. Temperature sampling was too sparse for this screen.'])
    def compare(mode,ax):
        q=[r for r in comparison if r['mode']==mode]
        ax.scatter([r['run'] for r in q],[1000*float(r['RMS_V']) for r in q],color=C[0])
        ax.tick_params(axis='x',rotation=40)
    plot('adjacent_RMS','Run 1670 against the reference and neighbors','Adjacent 1669 and 1671 use only archived ROOT',
         'Run','RMS (mV)',compare,'The comparison table keeps raw-derived T7 counts separate from ROOT-only neighboring summaries.')
    neighbor=read('ROOT_neighbor_RMS')
    def neighbor_view(mode,ax):
        for run,color in zip(('1669','1670','1671'),C):
            q=[r for r in neighbor if r['mode']==mode and r['run']==run]
            y=np.array([float(r['RMS_V']) for r in q])
            ax.plot([int(r['second']) for r in q],(y/y[:100].mean()-1)*100,
                    lw=.8,color=color,label=run)
        ax.axvline(118,color='#555555',linestyle=':',lw=1)
    plot('neighbor_RMS_time','Comparison of within-run RMS with neighboring ROOTs',
         'Each run is normalized by its first 100 archived one-second RMS values',
         'Received time (s)','RMS change (%)',neighbor_view,
         'The dotted line indicates 118 s for visual orientation. Only Run 1670 was subjected to the exploratory change screen.')
    coincidences=read('coincidence_summary')
    def coincidence_view(mode,ax):
        kinds=sorted({r['kind'] for r in coincidences if mode in r['kind']})
        for j,(kind,color) in enumerate(zip(kinds,C)):
            q=[r for r in coincidences if r['kind']==kind]
            x=np.arange(len(q))+(.24*(j-1))
            ax.bar(x,[int(r['count']) for r in q],width=.24,color=color,alpha=.62,label=kind)
            ax.scatter(x,[float(r['shifted_mean']) for r in q],s=15,marker='x',color='#303030')
        ax.set_xticks(range(5),[1,2,5,10,100])
        ax.set_ylim(bottom=0)
    plot('coincidences','Observed and shifted cross-mode counts',
         'Bars show measured tuples · crosses show the 20-shift mean',
         'Coincidence window (µs)','Peak tuples',coincidence_view,
         'The triple row is included in all three panels. Full ranges, protected exposure and sparse indices are retained.')
    text('Tail counts and cross-mode timing','Observable summaries in TM010 / TM011 / TM012 order',
         ['T7 counts: '+' / '.join(r['T7'] for r in summaries)+'.',
          'Observed / matched Gaussian: '+' / '.join(f'{float(r["matched_ratio"]):.2f}' for r in summaries)+'.',
          'Cross-mode comparisons use peaks and 20 shifted controls at 1, 2, 5, 10 and 100 µs.',
          'Counts are in the received-sample domain. A Gaussian marginal expectation does not assign independent-event significance.'])

    report(chronology,comparison,summaries,receipt,scan,strong,coincidences,track,steps)
    export(deck,PRESENTATION,version='run1670_targeted',prepared='23 November 2026')
    slides=PRESENTATION/'slides_en.md'
    slides.write_text(slides.read_text().replace('24–25 July 2026','21 November 2026'))
    packages=[*FIGURES.glob('*.png'),*PRESENTATION.glob('*'),
              *(STUDY/'tables/run1670').glob('*.csv'),*VALIDATION.glob('*'),
              *(STUDY/'code').glob('*1670.py'),STUDY/'code/stream_longitudinal.py',
              STUDY/'code/algorithms.py',STUDY.parent/'slide_deck.py']
    (STUDY/'run1670_manifest.json').write_text(json.dumps(dict(
        reference_commit='d81a13cec127f7a49ae448572b120fa22d5924d1',run=1670,
        files=[dict(path=str(p.relative_to(STUDY.parent)),bytes=p.stat().st_size,
                    sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                    local_only=PRESENTATION in p.parents) for p in sorted(packages) if p.is_file()]),indent=2)+'\n')


def report(chronology, comparison, modes, receipt, scan, strong, pairs, track, steps):
    def snapshot(run,snap,key):
        return next(r for r in chronology if r['run']==str(run) and r['snapshot']==snap
                    and r['key'].endswith('/'+key))
    lines=['# FLASH Run 1670 targeted scientific report','',
        '## Recorded LO chronology','',
        '| ODB variable under /Equipment/LocalOscill/Variables | 1669 (Hz) | 1670 and 1671 (Hz) | 1670 BOR key last-written UTC |',
        '|---|---:|---:|---|']
    for key in ('freq RS','freq Teled Ch1','freq Teled Ch2'):
        old=snapshot(1669,'EOR',key); new=snapshot(1670,'BOR',key)
        lines.append(f"| {key} | {float(old['value']):,.0f} | {float(new['value']):,.0f} | {new['last_written_utc']} |")
    lines += ['',f"The preceding EOR was {snapshot(1669,'EOR','freq RS')['event_utc']}. Run 1670 BOR was "
          f"{snapshot(1670,'BOR','freq RS')['event_utc']}, and its one LOSC bank was recorded at "
          f"{snapshot(1670,'LOSC','freq RS')['event_utc']}. SHA256-verified BOR/EOR and archived LOSC frequencies agree per run. "
          'The writes precede BOR and are bracketed by the neighboring runs. Physical application timestamps and short excursions between logged snapshots cannot be recovered.', '',
          'The locally archived LocalOscill frontend reference shows Rohde & Schwarz SMA100B, Teledyne T3AFG500 channels 1 and 2, and Keysight EXG pump handlers. The periodic frontend applies changed ODB settings to the devices and handles output toggles at run boundaries. Its LOSC bank records ODB, with no continuous frequency readback. The reference identifies the control path. The deployed source version, exact hardware write times and operator versus automation attribution are unresolved. The nominal VNA setpoints and Auto_detect_status Completed were written at 08:21:26 UTC, 30 seconds before the first LO write. That sequence is consistent with updated resonance settings preceding retuning. The snapshot alone cannot identify the actor or whether the LO setting was applied by an automatic retune workflow.', '',
          'Pump frequency, setting and logged enabled state at BOR/EOR are unchanged (7.891 GHz, −6.1, enabled). The pump on/off key was written between runs, so intermediate pump behavior is unresolved. Primary LO power setting 19 and both 4 Vpp secondary settings are unchanged. Archived digital centers remain +1.25 MHz, and nominal RF setpoints move −9/−10/+11 kHz. Sampling stays 5 MS/s with ADC ±2 V and channel pairs (0,1), (2,3), (4,5), complex convention I−iQhardware. The archived NetBox settings and With_LO/With_TWPA flags have no value changes across the tested snapshots.', '',
          '## Full-run statistics','',
          '| Mode | RMS (mV) | Improperness ratio | Exact T3 / T5 / T7 | T7 / matched Gaussian | Prefix ACF envelope τ (µs) |',
          '|---|---:|---:|---:|---:|---:|']
    for m,a in zip(modes,receipt['correlation']):
        lines.append(f"| {m['mode']} | {float(m['RMS_V'])*1000:.5f} | {float(m['properness_ratio']):.5f} | {m['T3']} / {m['T5']} / {m['T7']} | {float(m['matched_ratio']):.3f} | {a['upper_envelope']['tau_us']:.3f} |")
    lines += ['', 'Means, variances, covariance and RMS match ROOT within numerical tolerances. Distributions cover all samples; phase products exclude zero amplitudes. The exact sparse counts and covariance-matched Gaussian marginal ratios carry no independent-event significance. The complex ACF and Hann periodogram use the first 5 × 2²⁰ samples only. The full-run ordered ROOT coverage is 209 complete seconds at 100 Hz resolution. Prefix envelope times describe resolved local maxima and have no independent uncertainty model.', '',
          '## Changes within the acquisition','',
          f"The exploratory scan considered {scan['tested_series']} series on 209 complete seconds. It compared abrupt splits with at least 20 s on each side and linear trends against the joint family maximum of 999 aligned block permutations, repeated at 5 s and 10 s. "
          f"{len(strong)} candidates passed both exploratory thresholds (0.05). The last 0.7152 s remains in the raw summaries but is outside the equal-exposure test. "
          'Longer-range dependence, block exchangeability and unobserved configuration changes limit inference.', '']
    lines += [f"The shared change near 117–119 s lowers mean RMS by {steps['rms']} and integrated PSD by "
              f"{steps['power']} in TM010/TM011/TM012 order. Variance components change at matching times. "
              'Neither T7 rate nor the TM012 tracked line ratio passed both thresholds. Near 49 s, TM012 mean Q and its circular phase sine shift together. '
              'The sparse thermometry does not time-resolve the shared power change. The archive supplies no coincident LO readback; these changes cannot date an LO retune.', '']
    if strong:
        lines += [f"- {mode} {obs}, {kind}"+(f" near {split} s" if kind=='step' else '')+
                  f" (adjusted block fractions {p5:.3f}/{p10:.3f})." for mode,obs,kind,split,p5,p10 in strong]+['']
    lines += [f"TM012 line ratio vs T7 rank coefficient {scan['TM012_line_T7_spearman']:.3f}; line ratio vs RMS {scan['TM012_line_RMS_spearman']:.3f}. These are descriptive one-second associations on synchronized received-bin supports. The archived slow-control temperatures are sparse and identified by the existing stage mapping, with relative timing and validity flags. The LO records supply no evidence for an in-run retune.", '',
          '## Adjacent runs and spectral transition','',
          '| Run | TM012 leading non-DC IF (Hz) | Occupancy (/209) |', '|---|---:|---:|']
    for run,r in track.items():
        lines.append(f"| {run} | {float(r['IF_Hz']):,.1f} | {r['occupancy_count']} |")
    lines += ['', 'The +29 kHz displacement agrees with the image-coordinate hypothesis fADC + LO₁ − LO₂, giving 8.6409922495 GHz on either side. A fixed RF tone on the verified main coordinate would move −11 kHz. A retune-linked internal mixing product remains possible. The near-constant line occupancy and the measured within-run associations do not establish a causal relation to amplitude tails.', '',
          'The comparison CSV combines earlier validated raw results for Runs 1429, 1666 and 1676 with targeted Run 1670, and uses only existing ROOT moments for adjacent 1669 and 1671. No adjacent raw was needed to date the retune. A future neighboring raw comparison would require two additional passes totaling 18,648,212,835 compressed bytes.', '',
          '## Coincidence controls','',
          '| Window (µs) | Kind | Observed tuples | Shift mean | Shift range |','|---:|---|---:|---:|---:|']
    for r in pairs:
        lines.append(f"| {r['window_us']} | {r['kind']} | {r['count']} | {float(r['shifted_mean']):.2f} | {r['shifted_min']}–{r['shifted_max']} |")
    lines += ['', 'Each coincidence describes a tuple of cluster peaks in the received index domain, with edge-protected exposure and twenty circular shifts. Absolute UTC, physical coincidences and acquisition-channel skew remain unresolved.', '',
          '## Validation and resource use','',
          f"One complete Run 1670 pass read {receipt['compressed_bytes']:,} compressed bytes over {receipt['raw_wall_s']:.1f} s raw streaming; CPU {receipt['cpu_s']:.1f} s and peak process memory {receipt['peak_RSS_KiB']/1024:.1f} MiB. The main read requested {receipt['root_requested_bytes']:,} logical ROOT bytes. CRC-checked EOF, EOR, archived timing and PPS agreement, exposure and ADC conversion passed. Physical mount traffic was unavailable. No full waveforms were retained. A separate bounded read of the first five Run 1670 events requested {info(VALIDATION/'prefix_view.json')['process_io']['rchar']:,} logical bytes for the finer I/Q display."]
    (VALIDATION/'REPORT.md').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':
    main()
