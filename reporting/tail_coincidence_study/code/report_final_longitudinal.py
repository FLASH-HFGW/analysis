"""Render the final 24-run English longitudinal deck from compact tables."""
import hashlib
import json
import re

import matplotlib.pyplot as plt
import numpy as np

from final_longitudinal import FINAL, MODES, STUDY, VALIDATION, read_csv, read_json
from report_longitudinal import Deck, export

FIGURES = STUDY/'figures/longitudinal_final'
PRESENTATION = STUDY/'presentation/longitudinal_final'
COLOR = ('#007F86','#7657A6','#D98726')


def resource_summary():
    batches = [read_json(p) for p in sorted((VALIDATION/'completion').glob('*.json'))]
    assert len(batches)==5 and all(b['all_passed'] for b in batches)
    new = [r for batch in batches for r in batch['resources']]
    assert len(new)==20
    all_passes = read_json(VALIDATION/'longitudinal_batch.json')
    ref = read_json(VALIDATION/'pilot1429.json')
    extra = read_json(VALIDATION/'retune_archive.json')
    return dict(
        continuation_runs=[r['run'] for r in new],
        continuation_raw_bytes=sum(r['raw_bytes'] for r in new),
        continuation_raw_wall_s=sum(r['raw_wall_s'] for r in new),
        continuation_cpu_s=sum(r['cpu_user_s']+r['cpu_system_s'] for r in new),
        continuation_process_wall_s=sum(r['process_wall_s'] for r in new),
        continuation_rchar=sum(r['process_io']['rchar'] for r in new),
        continuation_kernel_read_bytes=sum(r['process_io']['read_bytes'] for r in new),
        selected_raw_bytes=all_passes['successful_raw_input_bytes']+ref['compressed_bytes'],
        selected_raw_wall_s=all_passes['successful_raw_wall_s']+ref['wall_s'],
        peak_RSS_KiB=max(all_passes['peak_RSS_KiB'],ref['max_rss_kib']),
        root_requested_bytes=all_passes['root_requested_bytes']+sum(r['root_requested_bytes'] for r in extra),
        root_wall_s=all_passes['root_wall_s']+sum(r['wall_s'] for r in extra),
        root_scope='23 run inputs plus seven ROOT-only spectral supplements; earlier inventory/PSD reads excluded',
        errors='Earlier interrupted Run 1446 attempt excluded; no repeat reads of completed raws',
        mount='read-only fuse.rclone; physical network/mount bytes unavailable')


def build():
    candidate_timing = read_csv(STUDY/'tables/longitudinal_candidates.csv')
    origin = int(next(r['start_unix'] for r in candidate_timing if r['run']=='1429'))
    retune = (int(next(r['start_unix'] for r in candidate_timing if r['run']=='1670'))-origin)/3600

    def table(name):
        return read_csv(FINAL/f'{name}.csv')

    data = {name:table(name) for name in ('modes','seconds','clusters','coincidences',
            'temperature','tm012_retune_track','spectral_candidates','mode_epoch_summary',
            'pooled_coincidences','close_pairs')}
    result = read_json(VALIDATION/'longitudinal_final.json')
    resources = resource_summary()
    (VALIDATION/'longitudinal_resources.json').write_text(json.dumps(resources,indent=2)+'\n')
    deck = Deck()
    FIGURES.mkdir(exist_ok=True)
    source = 'FLASH Dataset 2 · ADC-plane observables · longitudinal_final tables'

    def text(title, subtitle, lines):
        page = deck.new(title, subtitle, source=source, notes=' '.join(lines))
        page['footer'] = 'FLASH RUN3-B  |  DATASET 2 LONGITUDINAL STUDY'
        deck.bullets(page,.65,1.85,12,lines,size=19,gap=.22)

    def plot(name, title, subtitle, ylabel, draw, notes, temporal=True):
        fig, axes = plt.subplots(1,3,figsize=(15,5.2), layout='constrained')
        for mode, ax in zip(MODES, axes):
            draw(mode, ax)
            ax.set(title=mode, ylabel=ylabel)
            if temporal:
                ax.axvline(retune, color='#777777', linestyle=':', lw=1)
                ax.set_xlabel('Dataset 2 elapsed acquisition time (h)')
            ax.grid(alpha=.2)
            if ax.get_legend_handles_labels()[1]:
                ax.legend(fontsize=8)
        path = FIGURES/f'{name}.png'
        fig.savefig(path,dpi=145)
        plt.close(fig)
        page = deck.new(title,subtitle,source=source,notes=notes)
        page['footer'] = 'FLASH RUN3-B  |  DATASET 2 LONGITUDINAL STUDY'
        deck.image(page,.5,1.72,12.3,4.95,path)

    def mode_rows(mode, name='modes'):
        return [r for r in data[name] if r['mode']==mode]

    def single(field, marker='o-'):
        def draw(mode, ax):
            q = mode_rows(mode)
            for epoch,c in zip(('pre','post'),COLOR):
                rows=[r for r in q if r['epoch']==epoch]
                ax.plot([float(r['hour']) for r in rows],[float(r[field]) for r in rows],
                        marker,color=c,label=epoch,markersize=4)
        return draw

    text('FLASH Run3-B longitudinal study','24 timestamp-selected acquisitions · Dataset 2',
         ['The sample begins at Run 1429 and ends at the last available reconstruction, Run 1748.',
          'Twenty nearest-hour points, three additional controls and the endpoint cover 19.35 elapsed hours.',
          'All 24 runs have validated tails and coincidence products. Run 1429 was reused from the original checkpoint.',
          'This report compares ADC-plane observables and tests whether the TM012 line follows the LO retune.'])

    def timeline(mode, ax):
        rows=mode_rows(mode)
        controls={1529,1629,1729}
        for kind, color, y in [('Hourly',COLOR[0],0),('Control',COLOR[1],1),('Final',COLOR[2],2)]:
            q=[r for r in rows if (int(r['run'])==1748 if y==2 else int(r['run']) in controls if y==1
                                  else int(r['run']) not in controls|{1748})]
            ax.scatter([float(r['hour']) for r in q],[y]*len(q),s=16,color=color,label=kind)
        ax.set(yticks=[],ylim=(-.7,2.6))
    plot('coverage','Acquisition-time coverage','20–21 November 2026 UTC · dotted line marks Run 1670',
         'Selected acquisitions',timeline,
         'Archive reconstruction contained 314 eligible runs. The 24-run sample is sparse, with exact acquisition times in the selection table. Later raw-only runs are outside coverage.')

    plot('rms','ADC RMS versus acquisition time','Full-run samples including the final partial second',
         'RMS (V)',single('RMS_V'),'The three modes use ADC units. Line segments separate the two archived LO configurations.')
    plot('power','Full-band integrated spectral power','Mean of 209 complete 1 s native PSD products',
         'Integrated PSD (V²)',single('PSD_power_V2'),
         'This is windowed spectral power. Full-run RMS includes the residual; neither statistic is corrected by RF gain.')

    def tails(mode,ax):
        for order,color in zip((3,5,7),COLOR):
            q=mode_rows(mode)
            ax.plot([float(r['hour']) for r in q],[float(r[f'T{order}_per_s']) for r in q],
                    'o',label=f'T{order}',color=color,markersize=4)
        ax.set_yscale('log')
    plot('tail_rates','Exact amplitude exceedance rates','v50 histogram-fit thresholds applied to uncentered amplitude',
         'Samples/s',tails,'Strict greater-than thresholds per run. Exceedances can be time-correlated.')
    plot('gaussian','T7 counts relative to matched Gaussian','Measured mean and full-run I/Q covariance',
         'Observed / expected',single('T7_Gaussian_ratio'),
         'The expectation is a marginal amplitude integral. Exceedance samples are correlated. Counts alone cannot assign independent-event significance.')

    def local(mode,ax):
        q=mode_rows(mode)
        ax.scatter([float(r['hour']) for r in q],
                   [float(r['T7_common_support'])/int(r['T7']) for r in q],
                   s=17,color=COLOR[0],label='Retained T7 fraction')
        ax.scatter([float(r['hour']) for r in q],
                   [float(r['T7_local_exact_exposure_fraction']) for r in q],
                   s=17,color=COLOR[1],label='Exact local exposure')
        ax.set_ylim(0,1.05)
    plot('local','One-second RMS scaling of T7','Use max(global threshold, global threshold × local RMS / run RMS)',
         'Fraction',local,
         'The sparse archive resolves the local threshold where it is at least the original threshold. Else the common-support count is a lower bound. Local RMS is descriptive and may absorb signal or noise variation.')

    def clusters(mode,ax):
        q=mode_rows(mode)
        ax.scatter([float(r['hour']) for r in q],[float(r['group_rate_Hz']) for r in q],
                   s=17,color=COLOR[0],label='Primary groups/s')
        gap=10 if mode=='TM010' else 8
        extra={}
        for r in mode_rows(mode,'clusters'):
            if int(r['gap'])==gap and int(r['multiplicity'])>1:
                extra[r['run']]=extra.get(r['run'],0)+int(r['clusters'])
        ax.scatter([float(r['hour']) for r in q],[extra.get(r['run'],0)/209.7152 for r in q],
                   s=15,color=COLOR[2],label='Multi-hit groups/s')
    plot('clusters','T7 cluster rates and multiplicities','Primary gaps 10 / 8 / 8 non-exceeding samples',
         'Groups/s',clusters,'Sparse peak positions are tabulated in 10 s bins for all seven tested gaps. A group is an operational definition in sample index space.')

    def within(mode,ax):
        q=mode_rows(mode,'clusters')
        for epoch,color in zip(('pre','post'),COLOR):
            runs={r['run'] for r in mode_rows(mode) if r['epoch']==epoch}
            h=np.zeros(21)
            for r in q:
                if r['epoch']==epoch and int(r['gap'])==(10 if mode=='TM010' else 8):
                    h[int(r['received_start_s'])//10]+=int(r['clusters'])
            h /= len(runs)*np.r_[np.repeat(10.,20),9.7152]
            ax.step(np.arange(21)*10,h,where='post',color=color,label=epoch)
        ax.set_xlabel('Received-sample time (s)')
    plot('within_run_clusters','Within-run distribution of primary clusters','Epoch averages over aligned received-sample origins',
         'Groups/s',within,'Each 10 s bin is divided by its actual measured sample exposure.',temporal=False)

    def pairs(mode,ax):
        keys=[k for k in ('TM010--TM011','TM010--TM012','TM011--TM012') if mode in k]+['triple']
        palette = dict(zip(('TM010--TM011','TM010--TM012','TM011--TM012','triple'),
                           (*COLOR,'#666666')))
        for kind in keys:
            color = palette[kind]
            rows=[r for r in data['coincidences'] if r['kind']==kind and r['window_us']=='100']
            ax.plot([float(r['hour']) for r in rows],[float(r['rate_Hz']) for r in rows],
                    'o',ms=4,color=color,label=kind)
            ax.plot([float(r['hour']) for r in rows],
                    [float(r['shifted_mean'])/float(r['exposure_s']) for r in rows],
                    ':',lw=1,color=color)
    plot('coincidences','Cross-mode tuples and time-shift backgrounds',
         '100 µs inclusive peak window · measured dots and shifted means as dotted traces',
         'Tuples/s',pairs,'The same triple counts appear in each panel. Counts at 1, 2, 5, 10 and 100 µs and all 20 shifts are in the tables. Channel/group delay and absolute UTC remain uncalibrated.')

    narrow = [r for r in data['close_pairs'] if r['kind']=='TM010--TM011'
              and float(r['separation_us'])==0]
    observed = next(r for r in data['pooled_coincidences']
                    if r['kind']=='TM010--TM011' and r['window_us']=='1')
    text('Same-sample TM010–TM011 pairs','Acquisition-domain timing at the 1 µs window',
         [f'{len(narrow)} pairs hit the same recorded sample index in runs '+
          ', '.join(r['run'] for r in narrow)+'.',
          f'Pooled shifted controls contain {observed["shifted_min"]}–{observed["shifted_max"]} pairs, mean {float(observed["shifted_mean"]):.2f}.',
          'A shared digitizer or readout disturbance is a testable possibility.',
          'Check proximity to event and PPS boundaries and review channel-delay calibration before assigning a physical interpretation.'])

    def candidates(mode,ax):
        for epoch,color in zip(('pre','post'),COLOR):
            q=[r for r in mode_rows(mode,'spectral_candidates') if r['epoch']==epoch
               and r['screen']=='full_band_rank' and r['selected']=='True']
            ax.scatter([float(r['IF_Hz'])/1e6 for r in q],[float(r['mean_ratio']) for r in q],
                       c=color,label=epoch,s=8,alpha=.45)
        ax.set(xlim=(-2.5,2.5),yscale='log',xlabel='Signed ADC frequency (MHz)')
    plot('full_band','Full-band spectral candidates','Fifty strongest local maxima per mode and run across the native 5 MHz band',
         'Mean / local background',candidates,
         'The background is a 201-bin median of the 100 Hz PSD. Frequencies remain in digital ADC coordinates; pre and post retune are shown distinctly.',temporal=False)

    def occupancy(mode,ax):
        q=mode_rows(mode)
        ax.plot([float(r['hour']) for r in q],[float(r['fixed_IF_occupancy']) for r in q],
                'o',ms=4,label='Original fixed bin',color=COLOR[0])
        if mode=='TM012':
            by_run={r['run']:r for r in q}
            tt=[r for r in data['tm012_retune_track'] if r['selected']=='True']
            ax.plot([float(by_run[r['run']]['hour']) for r in tt],
                    [int(r['occupancy'])/int(r['windows']) for r in tt],
                    'x',label='Leading non-DC bin',color=COLOR[2])
        ax.set_ylim(-.06,1.1)
    plot('persistence','Persistent spectral occupancy','Fraction of 209 seconds above three times the normalized local background',
         'Occupancy',occupancy,'Fixed bins near −28 kHz, +1.25 MHz and −492.75 kHz. The TM012 strongest non-DC bin is tracked through both epochs.')

    def trajectory(mode,ax):
        hours={int(r['run']):(int(r['start_unix'])-origin)/3600 for r in candidate_timing}
        lines={}
        for r in mode_rows(mode,'spectral_candidates'):
            run=int(r['run'])
            if r['screen']=='full_band_rank' and abs(float(r['IF_Hz']))>=500:
                lines.setdefault(run,float(r['IF_Hz'])/1000)
        qq=sorted(lines,key=hours.__getitem__)
        ax.scatter([hours[r] for r in qq],[lines[r] for r in qq],s=15,color=COLOR[0],
                   label='Leading non-DC bin')
        if mode=='TM012':
            rr=[1669,1670,1671]
            ax.scatter([hours[r] for r in rr],[lines[r] for r in rr],
                       s=25,marker='x',color=COLOR[2],label='Adjacent ROOT controls')
            ax.axhline(-503.7505,color=COLOR[1],linestyle='--',lw=1,
                       label='Main-branch post-retune prediction')
            ax.set_ylim(-511,-455)

    plot('line_trajectory','Spectral frequency across the LO step',
         'Leading non-DC bin per run · distinct signed ADC coordinates',
         'Digital frequency (kHz)',trajectory,
         'Non-DC excludes |f| below 500 Hz. Candidate rank uses mean PSD relative to its local background, so a mode can change its leading bin without tracing the same physical source. TM012 includes the adjacent ROOT controls.')
    pre,post=result['retune_line_epochs']
    low=lambda row,key:row[key][0]
    med=lambda row,key:row[key][1]
    high=lambda row,key:row[key][2]
    text('Run 1670 moves the TM012 feature','Three adjacent archived ROOT controls locate the change',
         [f'The leading non-DC bin moves from {med(pre,"IF_Hz")/1000:.4f} to {med(post,"IF_Hz")/1000:.4f} kHz.',
          'Primary LO changes by −9 kHz and the TM012 secondary LO by +20 kHz.',
          'The main sum-LO branch predicts −11 kHz for a fixed RF tone. The measured shift is +29 kHz.',
          f'The image coordinate fADC + LO₁ − LO₂ is {med(pre,"image_coordinate_RF_Hz")/1e9:.10f} GHz before and {med(post,"image_coordinate_RF_Hz")/1e9:.10f} GHz after.',
          f'Occupancy is {low(pre,"occupancy"):.0f}–{high(pre,"occupancy"):.0f} / 209 before and {low(post,"occupancy"):.0f}–{high(post,"occupancy"):.0f} / 209 after.'])

    def temperature(mode,ax):
        for stage in dict.fromkeys(r['stage'] for r in data['temperature']):
            q=[r for r in data['temperature'] if r['stage']==stage]
            y=np.array([float(r['median_K']) for r in q])
            ax.errorbar([float(r['hour']) for r in q],y,
                        yerr=[y-[float(r['minimum_K']) for r in q],
                              [float(r['maximum_K']) for r in q]-y],fmt='o',ms=3,label=stage)
        ax.set_yscale('log')
    plot('temperature','Cryogenic temperature evolution','Shared sensors with within-run min/max and run medians',
         'Temperature (K)',temperature,
         'Positive readings with timing support only. Roles follow documented sensor mappings. The 4 K proxy is stage thermometry; slow-control timing uncertainty prevents subsecond alignment.')

    def lo(mode,ax):
        q=mode_rows(mode)
        first=q[0]
        for field,color in zip(('primary_LO_Hz','secondary_LO_Hz'),COLOR):
            ax.plot([float(r['hour']) for r in q],[(float(r[field])-float(first[field]))/1000 for r in q],
                    'o',ms=4,color=color,label=field.split('_')[0].capitalize()+' LO')
    plot('LO','Archived LO configuration','TWPA pump stayed enabled at 7.891 GHz with recorded setting −6.1',
         'Change from Run 1429 (kHz)',lo,
         'Pump setting is the recorded configuration value. BOR LO/pump status and calibrated RF response are distinct.')

    mode_epoch={(r['mode'],r['epoch']):r for r in data['mode_epoch_summary']}
    t7_pairs=[(float(mode_epoch[m,'pre']['T7_Gaussian_ratio_median']),
               float(mode_epoch[m,'post']['T7_Gaussian_ratio_median'])) for m in MODES]
    text('Interpretation and follow-up','The LO step and tail evolution constrain separate hypotheses',
         ['TM012 frequency follows the image-coordinate prediction at the retune.',
          'Image leakage and another LO-associated mixing product remain plausible source hypotheses.',
          'Median T7/Gaussian before → after: '+', '.join(f'{a:.2f} → {b:.2f}' for a,b in t7_pairs)+
          ' for TM010/TM011/TM012.',
          'The sparse sample and common timing changes limit causal inference about spectral lines, tails or temperatures.',
          'Next tests: independently vary each LO and measure both sidebands; evaluate time-dependent correlated nulls.'])

    text('Validation and resource use','Each new raw run has an independent receipt in the pilot branch',
         ['All selected runs passed sample, ADC, EOR, gzip CRC, serial, exposure, RMS and archived PPS checks.',
          f'Continuation: {resources["continuation_raw_bytes"]/1e9:.2f} GB compressed raw, '
          f'{resources["continuation_process_wall_s"]/60:.1f} min process wall and '
          f'{resources["continuation_cpu_s"]/60:.1f} min CPU.',
          f'Peak RSS {resources["peak_RSS_KiB"]/1024:.1f} MiB. ROOT reads were sparse range requests.',
          'No raw waveform caches. Per-run timestamps, counts, diagnostics and provenance are retained in lightweight files.'])

    export(deck,PRESENTATION,version='tail_coincidence_longitudinal_final',prepared='23 November 2026')
    md=PRESENTATION/'slides_en.md'
    md.write_text(md.read_text().replace('24–25 July 2026','20–21 November 2026'))
    return result,resources,t7_pairs,data


def narrative(result, resources, t7_pairs, data):
    pre, post = result['retune_line_epochs']
    span = lambda a, field: f"{a[field][0]:.4g} / {a[field][1]:.4g} / {a[field][2]:.4g}"
    lines = [
        '# FLASH Dataset 2 longitudinal scientific report', '',
        '## Coverage and integrity', '',
        'All 24 timestamp-selected runs passed raw validation. The original Run 1429 and the initial three receipts were reused. The other twenty runs were read once each, in five chronological four-run batches. CRC and EOR, raw/archive sample indices and counts, serial continuity, ADC conversion, exposure, ROOT RMS and sparse-group consistency were checked. PPS pulse lists and rejections agreed with the archive. Timing comparisons remain in received-sample coordinates. No absolute UTC or inter-channel group delay is calibrated.', '',
        'Runs 1429–1748 span 19 h 20 min 53 s from first BOR to last EOR. The sample represents twenty nearest-hour points, 1529/1629/1729 controls and the reconstructed endpoint. Intermediate reconstruction gaps and later raw-only runs remain separate. ROOT-only controls 1669, 1670 and 1671 bracket the retune without a raw pass.', '',
        '## Tail rates and clustered samples', '',
        '| Mode | Epoch | ADC RMS (mV), median | Integrated PSD (V²), median | T3 / T5 / T7 rates per s, medians | T7 / matched Gaussian, min / median / max |',
        '|---|---|---:|---:|---:|---:|',
    ]
    for r in data['mode_epoch_summary']:
        rates=' / '.join(f"{float(r[f'T{k}_per_s_median']):.4g}" for k in (3,5,7))
        ratios=' / '.join(f"{float(r[f'T7_Gaussian_ratio_{k}']):.3f}" for k in ('min','median','max'))
        lines.append(f"| {r['mode']} | {r['epoch']} | {1000*float(r['RMS_V_median']):.4f} | {float(r['PSD_power_V2_median']):.6g} | {rates} | {ratios} |")
    adjacent = {int(r['run']):float(r['T7_Gaussian_ratio']) for r in data['modes']
                if r['mode']=='TM012' and int(r['run']) in (1666,1676)}
    lines += ['', f"The selected runs bracketing the retune have TM012 T7/Gaussian ratios "
              f"{adjacent[1666]:.3f} (1666) and {adjacent[1676]:.3f} (1676). "
              f"The epoch medians are {t7_pairs[2][0]:.3f} and {t7_pairs[2][1]:.3f}.",
              '', 'The Gaussian expectations use measured mean and covariance and are marginal sample counts. The epoch medians describe the sample and can reflect smooth time trends and settings shared with the retune. Neither the sample ratios nor the shifted tuple counts are independent-event significance estimates.', '',
              'For the local RMS diagnostic, the original threshold is multiplied by the RMS of each one-second interval divided by full-run RMS. The common-support result counts above the larger of that threshold and the original global threshold. Where the scaled threshold is lower, missing below-global amplitudes make the result a lower bound. The exact-local exposure fraction and all 1 s counts are retained. Cluster multiplicity and peak distributions are tabulated in 10 s bins for all seven tested gaps.', '',
              '## Coincidences', '',
              '| Window (µs) | Tuple | Observed | Shifted mean | Shifted range |', '|---:|---|---:|---:|---:|']
    for r in data['pooled_coincidences']:
        lines.append(f"| {r['window_us']} | {r['kind']} | {r['count']} | {float(r['shifted_mean']):.2f} | {r['shifted_min']}–{r['shifted_max']} |")
    lines += ['', 'Five TM010–TM011 pairs within 1 µs were at the exact same received index, in runs 1497, 1547, 1581, 1629 and 1676. Corresponding pooled shift controls ranged from zero to one (mean 0.05). This motivates checking shared digitizer/readout disturbances and acquisition boundaries. The uncalibrated channel timing and descriptive control ensemble preclude a physical-event or significance claim.', '',
              'All twenty circular shifts use identical offsets across runs; the pooled control table sums corresponding offsets. The results describe accidental-background scale and preserve the protected exposure, with tuples allowed to share clusters.', '',
              '## The TM012 line across the Run 1670 LO retune', '',
              f"The leading non-DC spectral bin is at {pre['IF_Hz'][1]:,.1f} Hz before and {post['IF_Hz'][1]:,.1f} Hz after the retune. ROOT-only controls show the transition between 1669 and 1670 and persistence at 1671. The full 5 MHz screen used the native 100 Hz ordered PSD, ranked local maxima against a 201-bin median, and measured occupancy using the checkpoint's per-window normalization.", '',
              f"Pre-retune versus post-retune occupancy ranges are {pre['occupancy'][0]:.0f}–{pre['occupancy'][2]:.0f} / 209 and {post['occupancy'][0]:.0f}–{post['occupancy'][2]:.0f} / 209. Local ratio min / median / max is {span(pre,'local_ratio')} before and {span(post,'local_ratio')} after. Mean excess power of the selected 100 Hz bin, in V² at the ADC, has min / median / max {span(pre,'excess_bin_power_V2')} before and {span(post,'excess_bin_power_V2')} after. This bin-level comparison retains the local background and does not estimate calibrated RF power.", '',
              'The verified main conversion coordinate is fRF = LO₁ + LO₂ + fADC. The −9 kHz primary and +20 kHz secondary steps predict −11 kHz in digital frequency for a fixed RF tone on that branch. The observed +29 kHz is consistent with the alternate image coordinate fADC + LO₁ − LO₂, which gives the same nominal 8.6409922495 GHz in both epochs. The alternate coordinate is a mixing hypothesis, separate from the verified main-branch calibration. The strength and occupancy support a corresponding feature, but an image response and a retune-linked internal mixing product both remain possible.', '',
              'The full-band table records ranked candidates as well as the old IF and both ±11 kHz neighborhoods. The original bin loses occupancy, while the displaced bin retains it. The two epoch summaries cannot isolate an independent intensity effect from gain, line-bin alignment, thermal conditions, or elapsed-time changes.', '',
              '## Temperatures and next tests', '',
              'The five stage channels are archived with measurement validity and timing support. Run median/minimum/maximum tables describe within-run variation and between-run evolution. Pump settings remain fixed in the selected metadata. The 4 K sensor measures a stage and is used as a stage proxy. Correlation with temperatures or the retune cannot establish a physical cause.', '',
              'An independent two-LO sweep with injected tones at both sidebands would test the image-coordinate explanation and measure conversion gain near the line. A separate joint noise diagnostic should use time-dependent per-mode means and improper covariance, temporal correlation and cross-channel dependence; preserve the observed line and timing gaps in sensitivity checks before interpreting tail and coincidence significance.', '',
              '## Input and resources', '',
              f"The continuation used {resources['continuation_raw_bytes']:,} compressed bytes, {resources['continuation_process_wall_s']:.3f} s process wall and {resources['continuation_cpu_s']:.3f} s CPU. Total successful raw input across the 24 runs was {resources['selected_raw_bytes']:,} bytes over {resources['selected_raw_wall_s']:.3f} s raw streaming. Peak process RSS was {resources['peak_RSS_KiB']/1024:.1f} MiB. The scoped ROOT reads requested {resources['root_requested_bytes']:,} bytes in {resources['root_wall_s']:.3f} s. CPU was timed for the continuation. The physical mount traffic and early Run 1446 retry bytes are unavailable.", '',
              'The complete English deck is available locally under `presentation/longitudinal_final/`. Compact CSVs, code, validation receipts and the manifest are versioned. The earlier decks remain in their original paths, with the initial longitudinal manifest tied to its checkpoint commit.']
    (VALIDATION/'LONGITUDINAL_FINAL_REPORT.md').write_text('\n'.join(lines)+'\n')


def manifest():
    inputs = list((STUDY/'tables/longitudinal').glob('*/*.csv'))
    inputs += list((STUDY/'tables/retune').glob('*.csv'))
    inputs += list((VALIDATION/'longitudinal').glob('*.json'))
    inputs += list((VALIDATION/'completion').glob('*.json'))
    inputs += [STUDY/'longitudinal_manifest.json', STUDY/'data/longitudinal_selection.json',
               STUDY/'data/longitudinal_reference.json', STUDY.parent/'slide_deck.py']
    output = list(FINAL.glob('*.csv')) + list(FIGURES.glob('*.png')) + list(PRESENTATION.glob('*'))
    output += [VALIDATION/f for f in ('retune_archive.json','longitudinal_final.json',
               'longitudinal_resources.json','LONGITUDINAL_FINAL_REPORT.md')]
    code = [p for p in (STUDY/'code').glob('*.py') if re.search('longitudinal|retune|algorithms',p.name)]
    files = [dict(path=str(p.relative_to(STUDY.parent)), bytes=p.stat().st_size,
                  sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                  local_only=PRESENTATION in p.parents)
             for p in sorted(set(inputs+output+code)) if p.is_file()]
    (STUDY/'longitudinal_final_manifest.json').write_text(json.dumps(dict(
        initial_scientific_checkpoint='fc07e65b7190bdee1f8222bfa897bd9a8caca000',
        selected_runs=read_json(VALIDATION/'longitudinal_final.json')['selected_runs'],
        files=files),indent=2)+'\n')


if __name__=='__main__':
    narrative(*build())
    manifest()
