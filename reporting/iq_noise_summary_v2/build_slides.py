#!/usr/bin/env python3
"""Build the English IQ-noise draft as editable PPTX, PDF and Markdown."""
import csv
import json
import math
from pathlib import Path
import sys
import textwrap
from datetime import datetime
from zoneinfo import ZoneInfo
import matplotlib.dates as mdates

DEPS = Path('/tmp/codex-pptx-deps')
if DEPS.exists():
    sys.path.insert(0, str(DEPS))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import LogNorm
import matplotlib.patheffects as pe
from matplotlib.patches import Circle, Rectangle
from matplotlib import font_manager
from PIL import Image, ImageFont
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

ROOT = Path(__file__).resolve().parents[2]
WORK = Path('/home/mazzitel/HFGW/analysis-work/Run2')
RUNTIME = Path('/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2')
PUBLISHED = Path('/home/mazzitel/flash-data/analysis/autoreco/Run2')
OUT = WORK/'reports/iq_noise_summary_v2'
OUT.mkdir(parents=True, exist_ok=True)
GLOBAL = PUBLISHED/'noise_global'
ASSETS = OUT/'assets'
ASSETS.mkdir(exist_ok=True)
G = json.loads((GLOBAL/'global_noise.json').read_text())
S = json.loads((GLOBAL/'campaign_summary.json').read_text())
ROWS = list(csv.DictReader((GLOBAL/'runs.csv').open()))
Z = np.load(GLOBAL/'global_noise.npz')
PILOT = np.load(PUBLISHED/'noise_by_run/run00680_noise.npz')
RUN680 = json.loads((PUBLISHED/'noise_by_run/run00680_noise.json').read_text())
TZ = ZoneInfo('Europe/Rome')
RUN_MIDTIMES = {}
for _run in range(680,940):
    _d=json.loads((PUBLISHED/'noise_by_run'/f'run{_run:05d}_noise.json').read_text())
    _events=_d['events']
    RUN_MIDTIMES[_run]=datetime.fromtimestamp((_events[0]['midas_timestamp']+_events[-1]['midas_timestamp'])/2,TZ)
assert all(RUN_MIDTIMES[b]>RUN_MIDTIMES[a] for a,b in zip(range(680,939),range(681,940)))

B = json.loads((RUNTIME/'noise_performance/pass2/comparison_100events.json').read_text())
TIMES = list(csv.DictReader((RUNTIME/'noise_global/worker_stage_times.csv').open()))
MODES = ['TM010','TM011','TM012']
COLORS = ['#007F86','#7657A6','#D98726']
NAVY, INK, MUTED, BG = '#14283F','#24364B','#66768A','#F5F7FB'
W,H = 13.333333,7.5
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.spines.top':False,
 'axes.spines.right':False,'axes.labelcolor':INK,'text.color':INK,'axes.edgecolor':'#A5B2C0',
 'xtick.color':INK,'ytick.color':INK,'figure.facecolor':'white','axes.facecolor':'white',
 'legend.frameon':False,'axes.titlesize':14})


def figsave(fig,name):
    fig.savefig(ASSETS/(name+'.png'),dpi=210,bbox_inches='tight',facecolor='white')
    fig.savefig(ASSETS/(name+'.pdf'),bbox_inches='tight',facecolor='white')
    plt.close(fig)
    return ASSETS/(name+'.png')


def figures():
    paths={}
    fig,axes=plt.subplots(1,2,figsize=(9.6,3.8))
    m='TM010';c=PILOT[m+'_iq_counts'];ie=PILOT[m+'_iq_i_edges_v'];qe=PILOT[m+'_iq_q_edges_v']
    axes[0].pcolormesh(ie,qe,np.ma.masked_equal(c.T,0),norm=LogNorm(1,max(2,int(c.max()))),cmap='magma')
    for k,key,color,style in ((3,'amplitude_threshold_v','#CE2752','--'),(5,'amplitude_threshold_5sigma_v','#7657A6',':'),(7,'amplitude_threshold_7sigma_v','#248D48','-.')):
        ring=Circle((0,0),float(PILOT[m+'_'+key]),fill=False,color=color,linestyle=style,lw=1.7,label=f'+{k}σ',zorder=4)
        ring.set_path_effects([pe.Stroke(linewidth=3.4,foreground='white'),pe.Normal()]);axes[0].add_patch(ring)
    axes[0].legend(loc='upper right',fontsize=9)
    axes[0].set_title('All-sample density')
    cls=PILOT[m+'_peak_sigma_class']
    for k,color,marker,label in ((3,'#CE2752','o','3–5σ'),(5,'#7657A6','x','5–7σ'),(7,'#248D48','*','>7σ')):
        mask=cls==k;axes[1].scatter(PILOT[m+'_peak_i_v'][mask],PILOT[m+'_peak_q_signed_v'][mask],s=5 if k!=7 else 25,color=color,marker=marker,label=label,rasterized=True)
    axes[1].legend(fontsize=9);axes[1].set_title('Selected interval maxima')
    lim=max(abs(ie[0]),abs(ie[-1]),float(PILOT[m+'_amplitude_threshold_7sigma_v']))*1.04
    for ax in axes:
        ax.set(xlabel='I [V]',ylabel='−Q [V]',xlim=(-lim,lim),ylim=(-lim,lim));ax.set_aspect('equal')
    fig.tight_layout();paths['iq']=figsave(fig,'iq_density_and_maxima')

    fig,axes=plt.subplots(3,2,figsize=(12.2,5.5))
    e_time=np.r_[PILOT['envelope_start_sample'],RUN680['samples']]/RUN680['fs_hz']
    centers=PILOT['envelope_sample_indices']/RUN680['fs_hz']
    for row,(mode,color) in enumerate(zip(MODES,COLORS)):
        counts=PILOT[mode+'_noise_counts'];edges=PILOT[mode+'_noise_edges_v']*1000
        axes[row,0].stairs(counts,edges,color=color,lw=.9)
        for k,key,cc,style in ((3,'amplitude_threshold_v','#CE2752','--'),(5,'amplitude_threshold_5sigma_v','#7657A6',':'),(7,'amplitude_threshold_7sigma_v','#248D48','-.')):
            threshold=float(PILOT[mode+'_'+key]);mu=RUN680['modes'][mode]['mean_amplitude_v']
            axes[row,0].axvline(1000*(threshold-mu),color=cc,lw=.8,ls=style)
            axes[row,1].axhline(threshold*1000,color=cc,lw=.8,ls=style,label=f'+{k}σ')
        axes[row,0].set_yscale('log');axes[row,0].set_ylim(bottom=.5)
        axes[row,0].set(xlabel='A − run mean(A) [mV]',ylabel='Samples',title=mode+' · amplitude fluctuations')
        lo=PILOT[mode+'_envelope_min_v']*1000;hi=PILOT[mode+'_envelope_max_v']*1000
        axes[row,1].fill_between(e_time,np.r_[lo,lo[-1]],np.r_[hi,hi[-1]],step='post',color=color,alpha=.2,label='Min–max')
        axes[row,1].plot(centers,PILOT[mode+'_envelope_mean_v']*1000,color='#D98726',lw=.75,label='Interval mean')
        axes[row,1].set(xlabel='Cumulative acquired time [s]',ylabel='Amplitude [mV]',title=mode+' · time history',xlim=(0,RUN680['samples']/RUN680['fs_hz']))
        if row==0:legend_handles,legend_labels=axes[row,1].get_legend_handles_labels()
        for ax in axes[row]:ax.tick_params(labelsize=9);ax.xaxis.label.set_size(10);ax.yaxis.label.set_size(10);ax.title.set_size(11)
    fig.legend(legend_handles,legend_labels,fontsize=8,ncol=5,loc='upper center',bbox_to_anchor=(.74,1.0))
    fig.tight_layout(rect=(0,0,1,.94),h_pad=1.0);paths['run_amplitude']=figsave(fig,'run680_amplitude')

    fig,axes=plt.subplots(3,2,figsize=(12.2,5.5))
    breaks=np.flatnonzero(np.diff(PILOT['event_index'])!=0)+1
    trace_t=np.insert(PILOT['time_s'],breaks,np.nan)
    for row,(mode,color) in enumerate(zip(MODES,COLORS)):
        counts=PILOT['global_'+mode+'_phase'];edges=PILOT['phase_edges_rad']
        axes[row,0].stairs(counts/counts.mean(),edges,color=color,lw=.8,baseline=None)
        axes[row,0].axhline(1,color=MUTED,lw=.7,ls='--')
        axes[row,0].set(xlabel='Absolute wrapped phase [rad]',ylabel='Counts / uniform',title=mode+' · phase distribution',xlim=(-np.pi,np.pi))
        axes[row,1].plot(trace_t,np.insert(PILOT[mode+'_delta_phase_rad'],breaks,np.nan),color=color,lw=.45)
        axes[row,1].set(xlabel='Cumulative acquired time [s]',ylabel='Δφ [rad]',title=mode+' · relative unwrapped phase',xlim=(0,RUN680['samples']/RUN680['fs_hz']))
        for ax in axes[row]:ax.tick_params(labelsize=9);ax.xaxis.label.set_size(10);ax.yaxis.label.set_size(10);ax.title.set_size(11)
    fig.tight_layout(h_pad=1.0);paths['run_phase']=figsave(fig,'run680_phase')

    fig,axes=plt.subplots(1,2,figsize=(10.5,3.8))
    e=PILOT['phase_edges_rad'];c=PILOT['global_TM010_phase'];axes[0].stairs(c/c.mean(),e,color=COLORS[0])
    axes[0].axhline(1,color=MUTED,lw=.8,ls='--');axes[0].set(xlabel='Absolute phase [rad]',ylabel='Counts / uniform expectation',title='TM010 · run 680 only',ylim=(.55,1.55))
    for angle in np.arange(-4,5)*np.pi/4:axes[0].axvline(angle,color=MUTED,alpha=.18,lw=.7)
    for lag,color in zip((1,10,100),COLORS):
        c=PILOT['global_TM010_delta_'+str(lag)];axes[1].stairs(c/c.sum()/np.diff(e),e,color=color,label=f'{lag/G["config"]["fs_hz"]*1e6:g} μs')
    axes[1].axhline(1/(2*np.pi),ls='--',lw=.8,color=MUTED,label='Uniform')
    axes[1].set(xlabel='Wrapped Δφ [rad]',ylabel='Probability density',title='Phase increments',ylim=(.145,.17));axes[1].legend(fontsize=10)
    fig.tight_layout();paths['phase']=figsave(fig,'phase_diagnostics')

    def clock_axis(ax):
        ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[0,3,6,9,12,15,18,21],tz=TZ))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b\n%H:%M',tz=TZ))
        ax.set_xlim(RUN_MIDTIMES[680],RUN_MIDTIMES[939])
        ax.set_xlabel('Local time · Europe/Rome (CEST, UTC+2)')
        ax.tick_params(axis='x',labelsize=10)
    fig,ax=plt.subplots(figsize=(9.3,4.1))
    for mode,color in zip(MODES,COLORS):
        records=[r for r in ROWS if r['mode']==mode]
        dates=[RUN_MIDTIMES[int(r['run'][3:])] for r in records]
        a=np.array([float(r['mean_amplitude_v']) for r in records])
        ax.plot(dates,100*(a/a[0]-1),color=color,lw=2,label=mode)
    ax.axvline(RUN_MIDTIMES[898],color=MUTED,ls='--',lw=1)
    ax.annotate('Run 898\n'+RUN_MIDTIMES[898].strftime('%d %b %H:%M'),xy=(RUN_MIDTIMES[898],3.04),xytext=(-8,-3),textcoords='offset points',ha='right',fontsize=10)
    ax.set_ylabel('Mean amplitude change from run 680 [%]');clock_axis(ax)
    ax.legend(ncol=3,loc='upper left');ax.grid(axis='y',alpha=.2)
    fig.tight_layout();paths['drift']=figsave(fig,'common_amplitude_drift_clock')

    fig,axes=plt.subplots(1,2,figsize=(10.7,4))
    for mode,color in zip(MODES,COLORS):
        records=[r for r in ROWS if r['mode']==mode]
        dates=[RUN_MIDTIMES[int(r['run'][3:])] for r in records]
        for ax,kind in zip(axes,('local','reference')):
            ax.plot(dates,[100*float(r[kind+'_3sigma_fraction']) for r in records],color=color,lw=1.8,label=mode)
    axes[0].set(title='Local +3σ threshold',ylim=(.555,.571));axes[1].set(title='Fixed +3σ reference threshold',ylim=(.54,.80))
    for ax in axes:
        ax.set_ylabel('Fraction above threshold [%]');clock_axis(ax);ax.xaxis.label.set_size(10)
        ax.grid(axis='y',alpha=.2);ax.legend(fontsize=10)
    fig.tight_layout();paths['thresholds']=figsave(fig,'local_vs_fixed_thresholds_clock')

    fig,ax=plt.subplots(figsize=(8.3,4.1));ks=np.array([3,5,7])
    for mode,color in zip(MODES,COLORS):
        st=G['modes'][mode];a=[st['exceedances']['local'][str(k)]['samples_above']/st['n'] for k in ks]
        ax.plot(ks,a,'o-',color=color,label=mode,lw=2)
    ax.plot(ks,[.5*math.erfc(k/math.sqrt(2)) for k in ks],'x--',color=MUTED,label='Gaussian upper tail: comparison only',lw=1.5)
    ax.set_yscale('log');ax.set(xlabel='k in threshold μA + kσA',ylabel='Fraction of samples above threshold',xticks=ks,ylim=(3e-13,2e-2));ax.grid(axis='y',alpha=.2);ax.legend(fontsize=10,loc='lower left')
    fig.tight_layout();paths['tails']=figsave(fig,'tail_fractions')

    fig,ax=plt.subplots(figsize=(8.4,3.8));names=['Earlier version\n1 thread','Optimized\n3 mode threads'];left=np.zeros(2)
    for key,label,color in [('pass1','Pass 1',COLORS[0]),('pass2','Pass 2',COLORS[1]),('plots','Plots',COLORS[2])]:
        v=np.array([B['previous_timings'][key]['wall_s'],B['new_timings'][key]['wall_s']]);ax.barh(names,v,left=left,label=label,color=color,height=.48);left+=v
    for y,total in enumerate([B['previous_timings']['total']['wall_s'],B['new_timings']['total']['wall_s']]):ax.text(total+3,y,f'{total:.1f} s',va='center',fontsize=13,fontweight='bold')
    ax.set(xlabel='Elapsed time [s]',xlim=(0,200));ax.invert_yaxis();ax.legend(ncol=3,loc='upper center',bbox_to_anchor=(.5,1.18));fig.tight_layout();paths['speed']=figsave(fig,'interactive_speedup')

    fig,ax=plt.subplots(figsize=(8.6,3.8))
    values=[np.asarray([float(r[k+'_minutes']) for r in TIMES]) for k in ('download','analysis','upload')]
    boxes=ax.boxplot(values,patch_artist=True,showfliers=False,widths=.5)
    ax.set_xticks([1,2,3],['Download','Analysis','Upload'])
    for patch,color in zip(boxes['boxes'],COLORS):patch.set_facecolor(color);patch.set_alpha(.7)
    ax.set_yscale('log');ax.set(ylabel='Elapsed time [min] · log scale',ylim=(.008,120));ax.grid(axis='y',alpha=.2)
    for pos,v in enumerate(values,1):ax.text(pos,np.median(v)*1.35,f'median {np.median(v):.2f} min',ha='center',fontsize=11)
    fig.tight_layout();paths['workers']=figsave(fig,'worker_stage_times')
    return paths


FONT=font_manager.findfont('DejaVu Sans')
def wrap(text,width,size,bold=False):
    font=ImageFont.truetype(FONT,size=round(size*144/72))
    limit=width*144
    lines=[]
    for paragraph in text.split('\n'):
        if not paragraph:lines.append('');continue
        current=''
        for word in paragraph.split():
            candidate=(current+' '+word).strip()
            if current and font.getlength(candidate)>limit:lines.append(current);current=word
            else:current=candidate
        lines.append(current)
    return '\n'.join(lines)


class Deck:
    def __init__(self):self.slides=[]
    def new(self,title,subtitle='',source='',notes=''):
        slide={'title':title,'subtitle':subtitle,'source':source,'notes':notes,'items':[]};self.slides.append(slide)
        self.rect(slide,0,0,W,.075,'#007F86')
        self.text(slide,.55,.38,12.2,.7,title,30,bold=True,color=NAVY)
        if subtitle:self.text(slide,.58,1.12,12.1,.5,subtitle,14,color=MUTED)
        return slide
    def rect(self,s,x,y,w,h,color):s['items'].append({'kind':'rect','x':x,'y':y,'w':w,'h':h,'color':color})
    def text(self,s,x,y,w,h,text,size=19,bold=False,color=INK):
        wrapped=wrap(text,w,size,bold)
        needed=len(wrapped.splitlines())*size*1.15/72
        if needed>h+.12:raise ValueError(f'Text overflow on {s["title"]}: {text[:60]}, needs {needed:.2f} in, got {h}')
        if x+w>W+.01 or y+h>H+.01:raise ValueError('Item outside slide')
        s['items'].append(dict(kind='text',x=x,y=y,w=w,h=h,text=wrapped,size=size,bold=bold,color=color))
    def image(self,s,x,y,w,h,path):
        with Image.open(path) as im:ratio=im.width/im.height
        if w/h>ratio:nw=h*ratio; x+=(w-nw)/2;w=nw
        else:nh=w/ratio;y+=(h-nh)/2;h=nh
        s['items'].append(dict(kind='image',x=x,y=y,w=w,h=h,path=str(path)))
    def bullets(self,s,x,y,w,items,size=19,gap=.18):
        for text in items:
            wrapped=wrap(text,w-.25,size);height=len(wrapped.splitlines())*size*1.17/72+.05
            self.text(s,x,y,.18,height,'•',size,color=COLORS[0]);self.text(s,x+.25,y,w-.25,height,text,size)
            y+=height+gap
    def card(self,s,x,y,w,value,label,color=COLORS[0]):
        self.rect(s,x,y,w,1.08,'#FFFFFF');self.text(s,x+.18,y+.14,w-.36,.48,value,28,True,color);self.text(s,x+.18,y+.71,w-.36,.28,label,12,color=MUTED)


def content(paths):
    d=Deck()
    s=d.new('Three-resonance IQ noise analysis','Run-by-run reconstruction and a 260-run statistical study',
        'Source: campaign_summary.json; aggregate_checks.json',
        'First English draft for a scientific group meeting. Data acquisition: 24–25 July 2026. Draft prepared 1 November 2026. All results are descriptive; no signal claim is made.')
    d.text(s,.65,2.0,10.7,1.3,'From MIDAS streams to a validated global noise dataset',34,True,NAVY)
    d.text(s,.67,3.45,10.8,.6,'TM010  ·  TM011  ·  TM012',23,color=COLORS[0])
    for x,val,label in ((.65,'260','complete runs'),(4.7,'260,000','SPEC events'),(8.75,'15.15 h','acquired time')):d.card(s,x,4.65,3.7,val,label)
    d.text(s,.68,6.25,11.8,.4,'Data: 24–25 July 2026    |    Preliminary interpretation    |    Draft v2 · 1 November 2026',13,color=MUTED)

    s=d.new('Dataset and acquisition scope','All requested runs, 680–939 inclusive, are present and complete.',
        'Source: quality_checks.json; recovery_report.json; campaign_summary.json',
        '1000 SPEC events per run is the measured event count, not a software limit. In run 680, 1251 total MIDAS events include 1000 SPEC, 212 TGPS, 36 INPT, one LOSC and two internal events. The inventory was verified on that run only.')
    for x,val,label in ((.6,'1,000','SPEC events per run'),(4.85,'1,048,576','samples per SPEC event'),(9.1,'272.6 bn','complex samples per mode')):d.card(s,x,1.9,3.65,val,label)
    d.bullets(s,.72,3.4,7.4,['5 MHz sampling; 209.7152 ms of acquired data per SPEC event.','Three IQ pairs: channels 0–1, 2–3 and 4–5.','Every file was read to EOF; no run was excluded.'],20,.24)
    d.rect(s,8.7,3.4,3.95,2.7,'#E9EFF6')
    d.text(s,8.95,3.65,3.4,.5,'SPEC vs MIDAS events',20,True,NAVY)
    d.text(s,8.95,4.35,3.4,1.45,'Run 680: 1,251 total events, including 1,000 SPEC events. Auxiliary streams are not IQ noise samples.',17)

    s=d.new('Analysis definitions and two-pass reconstruction','A consistent convention is used across the campaign.',
        'Source: analyze_midas_iq_noise.py; iq_noise_statistics.py',
        'The IQ convention is −1: z=I−jQ. Amplitude fluctuations are A−mean(A), without subtracting the I and Q means. Sigma denotes the standard deviation of amplitude. Phase unwrap stays within contiguous nonzero-amplitude segments of each event. No continuity is assumed across acquisitions.')
    d.rect(s,.6,1.95,4.1,3.9,'#FFFFFF')
    for y,text in ((2.2,'z = I − jQ'),(3.0,'A = |z|'),(3.8,'φ = arg(z)'),(4.6,'δA = A − ⟨A⟩')):d.text(s,.95,y,3.5,.65,text,29,True,NAVY)
    d.text(s,5.15,2.05,7.3,.5,'PASS 1  —  establish the run baseline',21,True,COLORS[0])
    d.text(s,5.15,2.75,7.0,.9,'Read samples; compute amplitude moments, data ranges and a decimated time history.',19)
    d.text(s,5.15,4.0,7.3,.5,'PASS 2  —  count with known thresholds',21,True,COLORS[1])
    d.text(s,5.15,4.7,7.0,1.15,'Build exact histograms; count threshold crossings and episodes; calculate phase increments and interval maxima.',19)
    d.text(s,.72,6.3,11.9,.35,'Thresholds: Tₖ = μA + kσA, with k = 3, 5, 7. An episode is split at each SPEC/run boundary.',14,color=MUTED)

    s=d.new('IQ density and selected maxima','Run 680 · TM010 · density and threshold-selected peaks are different populations.',
        'Source: job_to_submit_noise/00680/run00680_noise.npz · full run, 1,000 SPEC events',
        'The temporally subsampled IQ panel has been removed. The left panel uses all samples. The right panel contains only the maximum from each interval above the amplitude thresholds, in exclusive 3–5, 5–7 and >7 sigma classes. Its empty center follows the selection; this is not a second density map or evidence of coherent rotation.')
    d.image(s,.55,1.85,12.25,4.3,paths['iq'])
    d.text(s,1.05,6.3,5.1,.45,'Density: all samples',18,True,NAVY)
    d.text(s,7.05,6.3,5.3,.45,'Maxima: explicitly selected peaks',18,True,NAVY)

    s=d.new('Run 680: amplitude distributions and time histories','All three modes · full run · 1,000 SPEC events · 209.715 s of acquired time.',
        'Source: job_to_submit_noise/00680/run00680_noise.npz and JSON',
        'The left plots show amplitude fluctuations around the full-run mean using every sample. Counts are logarithmic. The right plots show the minimum/maximum envelope and mean in each interval, also calculated from every sample. The envelope is not a raw waveform and the mean is not a selected sample. Interval width is approximately 10.5 ms. Thresholds are mean(A)+3/5/7 standard deviations. The time axis is cumulative acquired time and excludes gaps between events.')
    d.image(s,.52,1.72,12.3,4.65,paths['run_amplitude'])
    d.text(s,.78,6.52,11.8,.3,'Shaded band: all-sample min–max. Orange line: interval mean. Dashed lines: +3σ, +5σ, +7σ.',12.5,color=MUTED)

    s=d.new('Run 680: phase distributions and time histories','All three modes · the same complete run used for the amplitude and IQ examples.',
        'Source: job_to_submit_noise/00680/run00680_noise.npz and JSON',
        'The left plots use absolute atan2(signed Q,I), wrapped to the phase circle, normalized to a uniform histogram. The right plots use relative unwrapped phase within each acquisition. Lines are broken at event boundaries. The inter-event multiples of 2π are not determined, and phase becomes unstable at low amplitude, so jumps are not automatically physical. The histories are decimated for display; histogram counts use all nonzero-amplitude samples. Time is cumulative acquired time, not the clock-time axis used for the campaign trends.')
    d.image(s,.52,1.72,12.3,4.65,paths['run_phase'])
    d.text(s,.78,6.52,11.8,.3,'Histograms: all valid samples. Histories: decimated; unwrap is independent within acquisitions.',12.5,color=MUTED)

    s=d.new('Run 680: interpreting the phase structure','This diagnostic also refers only to run 680, not to the pooled campaign.',
        'Source: run00680_noise.npz · global_TM010_phase and delta arrays are run-level, despite the key prefix',
        'In v1 this slide used pooled campaign data; v2 deliberately uses the full run 680 to keep the examples consistent. Narrow features at axes/diagonals repeat every π/4. Earlier pilot checks changed bin count, shifted bin edges and separated amplitude bands; features strengthened at low amplitude, consistent with quantization/binning. That does not prove every feature is caused by quantization. Phase increment distributions at 2 and 20 microseconds are close to flat, but this alone does not prove full statistical independence.')
    d.image(s,.58,1.85,9.05,4.85,paths['phase'])
    d.bullets(s,9.85,2.12,2.85,['Run 680 only.','Narrow features repeat every 45°.','Pilot checks support quantization / binning effects.','Δφ is close to uniform at 2 and 20 μs.'],16,.24)

    s=d.new('Reproducible reconstruction and global aggregation','The existing autoreco lifecycle was extended with a dedicated noise mode.',
        'Source: autoreco.py; noise_jobs.py; aggregate_iq_noise.py; aggregate_checks.json',
        'The logbook is read-only. Noise states and outputs are separate from FFT reconstruction. Compatible configurations and common bin edges are required for aggregation. Weighted first and second moments are merged, not the average of run RMS values. Global phase uses absolute atan2(signed Q,I), not run-initial phase offsets. Counts remain 64-bit.')
    boxes=[(.65,'SELECT','Run list / logbook'),(3.8,'RECONSTRUCT','HTCondor + local disk'),(6.95,'RECOVER','NPZ, JSON and plots'),(10.1,'AGGREGATE','Checks + global outputs')]
    for x,head,sub in boxes:
        d.rect(s,x,2.0,2.6,1.4,'#FFFFFF');d.text(s,x+.16,2.2,2.3,.35,head,17,True,COLORS[0]);d.text(s,x+.16,2.8,2.3,.5,sub,14)
    d.bullets(s,.85,4.0,11.7,['260/260 successful jobs; complete output files and a single compatible configuration.','Common bins and sample-weighted moments preserve exact global counts.','Local thresholds and fixed pilot-reference thresholds are stored separately.'],20,.3)

    s=d.new('A shared amplitude drift across all three modes','24–25 July 2026 · run mid-times from MIDAS headers · Europe/Rome (CEST).',
        'Source: runs.csv; campaign_summary.json',
        'The time axis uses the midpoint of the first and last SPEC timestamps in each run, not run number or concatenated acquired time. The timezone is Europe/Rome, CEST (UTC+2) for these acquisition dates. MIDAS header timestamps have second-level precision and are not a GPS phase-alignment claim. The plotted change is relative to the mean amplitude of run 680. The reported span uses (maximum/minimum−1), so it is not exactly the height relative to run 680. All modes reach their maximum mean amplitude at run 898. Correlations refer to per-run means; they do not prove a physical cause or sample-by-sample coupling.')
    d.image(s,.55,1.82,9.2,4.95,paths['drift'])
    for y,mode in zip((2.05,3.38,4.71),MODES):d.card(s,10.05,y,2.7,f'{S["modes"][mode]["mean_span_percent"]:.2f}%',mode+' · max/min span',COLORS[MODES.index(mode)])
    d.text(s,.75,6.55,8.8,.3,'Per-run mean correlations: r = 0.99897–0.99983. Cause not yet established.',13,color=MUTED)

    s=d.new('Local and fixed thresholds tell different stories','24–25 July 2026 · actual local time · illustration at +3σ.',
        'Source: runs.csv; campaign_summary.json',
        'The x axis uses the MIDAS-header midpoint of each run, converted to Europe/Rome, CEST (UTC+2), across midnight on 24–25 July 2026. Local threshold = mean and standard deviation of each run. Fixed threshold = amplitude-only baseline from the first 100 SPEC events of pilot run 680. Each run contains the same number of samples. Stable local fractions indicate that a large change in the normalized core/tail shape is not evident at this threshold; extreme tails require separate analysis.')
    d.image(s,.58,1.85,12.15,4.45,paths['thresholds'])
    d.text(s,.8,6.38,11.7,.45,'Stable local rates + changing fixed-reference rates suggest a changing scale, not automatically new transient signals.',17,True,NAVY)

    s=d.new('Amplitude thresholds are not detection significance','Observed exceedances must be compared with a justified amplitude-noise model.',
        'Source: global_noise.json; theoretical Gaussian upper tail from erfc',
        'Observed fractions pool exact local-threshold counts. The Gaussian curve is a mathematical comparison, not a fitted distribution for amplitude. The amplitude of an IQ signal is not guaranteed to be Gaussian. Correlated samples also prevent interpreting raw sample counts as independent trials. No physical excess or detection significance is claimed here.')
    d.image(s,.6,1.9,8.4,4.85,paths['tails'])
    d.bullets(s,9.3,2.2,3.35,['3σ, 5σ and 7σ label amplitude thresholds.','Gaussian tail probabilities do not describe these data by assumption.','Fit the noise model before assigning significance.'],18,.32)

    s=d.new('Measured reconstruction speedup','Controlled local comparison: the same first 100 real SPEC events.',
        'Source: noise_performance/pass2/comparison_100events.json',
        'Earlier one-thread version versus optimized three-thread mode processing on the same local host and same run subset. Includes analysis, plots and NPZ writing, excludes download/upload. Pass 1 is unchanged. All 102 NPZ arrays are exactly identical. Circular moment sums differ only by rounding, with maximum absolute difference 4.54e−9. This is not a worker full-run benchmark. Sixteen automated checks passed at implementation time.')
    d.image(s,.6,2.05,8.65,4.6,paths['speed'])
    d.card(s,9.65,2.15,3.05,'2.55×','faster second pass')
    d.card(s,9.65,3.55,3.05,'−44%','total elapsed time')
    d.text(s,9.7,5.1,2.9,1.1,'102 NPZ arrays unchanged.\nThree mode threads; request 4 CPUs in batch.',16,True,NAVY)

    s=d.new('Worker-node timing: analysis dominated','141 optimized jobs provide timestamped download, analysis and upload stages.',
        'Source: worker_stage_times.csv; worker_stage_times.json',
        'These are distributions across the optimized four-CPU/three-thread cohort, with medians for each separate stage. Median component times need not sum to the median total. Analysis ranged from 19.25 to 75.95 minutes. The old 119 jobs lacked comparable stage timestamps. Hardware, contention and execution conditions differ from the local benchmark; do not attribute campaign timing differences solely to the code.')
    d.image(s,.62,1.95,8.45,4.7,paths['workers'])
    for y,value,label in ((2.1,'2.83 min','median download'),(3.48,'53.33 min','median analysis'),(4.86,'2 s','median upload')):d.card(s,9.5,y,3.15,value,label)

    s=d.new('What is established — and what comes next','The global dataset is validated; the physical interpretation remains open.',
        'Source: campaign_summary.json; quality_checks.json; aggregate_checks.json',
        'Prioritize logbook and environmental metadata to explain the common scale drift. Then compare normalized amplitude distributions and fit the noise model. Phase increments should be studied versus lag and amplitude. Transient candidates require original waveforms, timing and multi-mode coincidence checks; aggregated histograms do not retain sample order.')
    d.rect(s,.65,1.95,5.65,4.7,'#FFFFFF');d.rect(s,6.65,1.95,6.0,4.7,'#E9EFF6')
    d.text(s,.95,2.2,5.1,.45,'Measured',23,True,COLORS[0])
    d.bullets(s,.98,2.95,4.95,['260 complete runs with compatible statistics.','A common 2.6–3.3% amplitude drift.','Stable local +3σ fractions.','Validated, faster reconstruction.'],19,.25)
    d.text(s,6.95,2.2,5.1,.45,'Next analysis steps',23,True,NAVY)
    d.bullets(s,7.0,2.95,5.1,['Correlate drift with temperature, gain and run conditions.','Model normalized amplitude distributions and tails.','Study phase increments versus lag and amplitude.','Check original events for transient coincidences.'],18,.22)
    return d


def rgb(color):return RGBColor.from_string(color.lstrip('#'))
def export(deck):
    prs=Presentation();prs.slide_width=Inches(W);prs.slide_height=Inches(H)
    pdf=PdfPages(OUT/'iq_noise_summary_v2.pdf')
    md=['# Three-resonance IQ noise analysis — draft v2','',
        'Prepared: 1 November 2026. Acquisition: 24–25 July 2026.','',
        'Native text and shapes are editable in the PPTX. Scientific plots are generated from the saved numeric outputs.','']
    previews=[]
    for idx,s in enumerate(deck.slides,1):
        slide=prs.slides.add_slide(prs.slide_layouts[6]);slide.background.fill.solid();slide.background.fill.fore_color.rgb=rgb(BG)
        fig=plt.figure(figsize=(W,H),facecolor=BG)
        for item in s['items']:
            x,y,w,h=[item[k] for k in ('x','y','w','h')]
            if item['kind']=='rect':
                sh=slide.shapes.add_shape(1,Inches(x),Inches(y),Inches(w),Inches(h));sh.fill.solid();sh.fill.fore_color.rgb=rgb(item['color']);sh.line.fill.background()
                fig.add_artist(Rectangle((x/W,1-(y+h)/H),w/W,h/H,transform=fig.transFigure,color=item['color'],linewidth=0))
            elif item['kind']=='image':
                slide.shapes.add_picture(item['path'],Inches(x),Inches(y),width=Inches(w),height=Inches(h))
                ax=fig.add_axes([x/W,1-(y+h)/H,w/W,h/H]);ax.imshow(Image.open(item['path']));ax.axis('off')
            else:
                sh=slide.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h));tf=sh.text_frame
                tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0;tf.word_wrap=False
                for n,line in enumerate(item['text'].split('\n')):
                    p=tf.paragraphs[0] if n==0 else tf.add_paragraph();p.text=line;p.space_before=Pt(0);p.space_after=Pt(0);p.line_spacing=1.15
                    p.font.name='Arial';p.font.size=Pt(item['size']);p.font.bold=item['bold'];p.font.color.rgb=rgb(item['color'])
                fig.text(x/W,1-y/H,item['text'],ha='left',va='top',fontsize=item['size'],fontweight='bold' if item['bold'] else 'normal',color=item['color'],linespacing=1.15)
        footer='IQ NOISE STUDY  |  PRELIMINARY · v2'
        for x,text,width in ((.58,footer,5.3),(12.0,f'{idx:02d} / {len(deck.slides):02d}',.8)):
            sh=slide.shapes.add_textbox(Inches(x),Inches(7.12),Inches(width),Inches(.2));sh.text_frame.margin_top=0;sh.text_frame.margin_left=0;p=sh.text_frame.paragraphs[0];p.text=text;p.font.size=Pt(8);p.font.name='Arial';p.font.color.rgb=rgb(MUTED)
            fig.text(x/W,1-7.12/H,text,fontsize=8,va='top',color=MUTED)
        source=wrap(s['source'],11.8,7.5)
        sh=slide.shapes.add_textbox(Inches(.58),Inches(6.91),Inches(12),Inches(.18));sh.text_frame.margin_top=0;sh.text_frame.margin_left=0;p=sh.text_frame.paragraphs[0];p.text=source;p.font.size=Pt(7.5);p.font.name='Arial';p.font.color.rgb=rgb(MUTED)
        fig.text(.58/W,1-6.91/H,source,fontsize=7.5,va='top',color=MUTED)
        slide.notes_slide.notes_text_frame.text=s['notes']+'\n\n'+s['source']
        pdf.savefig(fig,dpi=160)
        preview=OUT/f'slide_{idx:02d}.png';fig.savefig(preview,dpi=100,facecolor=BG);previews.append(preview);plt.close(fig)
        md.extend([f'## {idx:02d}. {s["title"]}','',s['subtitle'],''])
        for item in s['items']:
            if item['kind']=='text' and item['text'] not in (s['title'],s['subtitle']):md.extend([item['text'].replace('\n',' '),''])
        md.extend(['Speaker notes: '+s['notes'],'','Data: '+s['source'],''])
    pdf.close();prs.save(OUT/'iq_noise_summary_v2.pptx')
    (OUT/'slides_en.md').write_text('\n'.join(md)+'\n')
    (OUT/'slide_model.json').write_text(json.dumps(deck.slides,indent=2,ensure_ascii=False)+'\n')
    thumbs=[]
    for path in previews:
        with Image.open(path) as im:thumbs.append(im.resize((640,360)))
    sheet=Image.new('RGB',(640*3,360*math.ceil(len(previews)/3)),'white')
    for n,im in enumerate(thumbs):sheet.paste(im,((n%3)*640,(n//3)*360))
    sheet.save(OUT/'contact_sheet.png')
    print(f'Created {len(deck.slides)} slides: PPTX, PDF, Markdown and previews in {OUT}')


if __name__=='__main__':
    export(content(figures()))
