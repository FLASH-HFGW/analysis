"""v44: append experimental characterization and frozen step6 comparison to v43.

Reads saved summaries/histograms only. No raw access, fits, reconstruction or simulation.
Original Part I PDF pages and PPTX slides are copied, never re-rendered.
"""
from pathlib import Path
import copy,csv,hashlib,io,json,shutil,subprocess,sys,zipfile
import numpy as np,h5py
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap,LogNorm
sys.path.insert(0,'/tmp/v18-python-deps')
from pptx import Presentation
from pptx.dml.color import RGBColor
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO/'reporting'));import slide_deck as sd
W=REPO.parent/'analysis-work/Run2';B=W/'reports/iq_noise_summary_v43_partI';V40=W/'reports/iq_noise_summary_v40';OUT=W/'reports/iq_noise_summary_v44';A=OUT/'assets';A.mkdir(parents=True,exist_ok=True)
S=W/'simulation/toy_ODB_cal5_data2_LF_20261116';CAMP=W/'reports/iq_noise_summary_v17/data/v2_campaign';DC=W/'simulation/step7/dc_longterm_diagnostic/longterm.csv';LEG=W/'staging/gpfs_noise_v0_20261108/originals';H5=W/'reports/noise_v2_development_20261109/run680_full_published/run00680_noise_v2.h5'
MODES=['TM010','TM011','TM012'];DATA='#007F86';TOY='#7657A6';THERMAL='#43a1ed';ELECTRONIC='#ed812a';NAVY='#263952';GRAY='#66768A'
inputs={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def track(p):p=Path(p);inputs[str(p)]=sha(p);return p
def js(p):return json.loads(track(p).read_text())
def rows(p):
 with open(track(p)) as f:return list(csv.DictReader(f))
track(Path(__file__));track(REPO/'reporting/slide_deck.py')
original=js(B/'slide_model.json');track(B/'iq_noise_summary_v43_partI.pdf');track(B/'iq_noise_summary_v43_partI.pptx');track(W/'simulation/presentation_steps1_6_v43/short_examples.h5')
short=js(W/'simulation/presentation_steps1_6_v43/metrics.json');metrics=js(S/'metrics.json');comp=js(S/'comparison/comparison.json');amps=js(V40/'data/amplitude_comparison_updated.json');iqstats=js(V40/'data/IQ_comparison_updated.json');norm=js(V40/'data/current_normalization.json');tails=js(LEG/'noise_continuous/amplitude_model_comparison.json');globalmeta=js(LEG/'noise_global/global_noise.json');summary=js(LEG/'noise_global/campaign_summary.json');findings=js(CAMP/'pilot_findings.json')['findings'];dcr=rows(DC);bands=rows(CAMP/'band_rms_relative_to_run680.csv');runs=rows(LEG/'noise_global/runs.csv')
assert metrics['RF_gain_db']==short['configuration']['RF_gain_db']==103.4
assert metrics['LF_kz_amplitude_factor']==short['configuration']['LF_data_over_cal_amplitude']==.01
assert metrics['ADC_peak_V']==short['configuration']['ADC_peak_V']==2
for k in ['physical_parameters','calibration_reconstruction']:
 p=track(short['configuration'][k]);assert inputs[str(p)]==metrics['input_sha256'][str(p)]
assert len({int(x['run']) for x in dcr})==260
fulliq={mode:np.load(track(V40/'data'/f'full_iq_data_{mode}.npz')) for mode in MODES};pairs={mode:np.load(track(S/'comparison'/f'{mode}_comparison.npz')) for mode in MODES};glob=np.load(track(LEG/'noise_global/global_noise.npz'))
track(H5);track(S/'toy_full_run680.h5');data=h5py.File(H5,'r');toy=h5py.File(S/'toy_full_run680.h5','r')
IQ_VMAX=max([int(fulliq[mo]['hist'].max()) for mo in MODES]+[int(toy[mo+'/IQ_counts'][:].max()) for mo in MODES])
DCMODE={mo:sorted([r for r in dcr if r['mode']==mo],key=lambda x:int(x['run'])) for mo in MODES};start=float(DCMODE['TM010'][0]['time_unix']);hours=lambda rr:np.array([(float(x['time_unix'])-start)/3600 for x in rr]);col=lambda rr,k:np.array([float(x[k]) for x in rr]);time=hours(DCMODE['TM010']);sc=.4
plt.rcParams.update({'font.size':9,'axes.titlesize':10,'axes.labelsize':9,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':7,'axes.grid':True,'grid.alpha':.18,'lines.linewidth':.85})
cmapD=LinearSegmentedColormap.from_list('data',['white',DATA]);cmapT=LinearSegmentedColormap.from_list('toy',['white',TOY])
def save(fig,name):
 fig.savefig(A/(name+'.png'),dpi=210,facecolor='white');fig.savefig(A/(name+'.pdf'));plt.close(fig);return A/(name+'.png')
def grid(nr,nc,w=12.6,h=4.8):
 fig,axs=plt.subplots(nr,nc,figsize=(w,h),squeeze=False);fig.subplots_adjust(left=.065,right=.985,bottom=.2 if h<3 else .12,top=.93,hspace=.8 if nr>2 else .62,wspace=.42);return fig,axs

def stairs(ax,e,c,color,label,scale=1,ls='-'):
 density=c/c.sum()/np.diff(e)/scale;ax.stairs(np.maximum(density,1e-15),e*scale,color=color,ls=ls,label=label)
def iq(ax,edges,hist,color,limit=200):
 cm=cmapD if color==DATA else cmapT
 ax.pcolormesh(edges*1000,edges*1000,np.ma.masked_equal(hist.T,0),norm=LogNorm(vmin=1,vmax=IQ_VMAX),cmap=cm,rasterized=True)
 ax.set(xlim=(-limit,limit),ylim=(-limit,limit),xlabel='I [mV ADC]',ylabel='Qeff [mV ADC]');ax.set_aspect('equal',adjustable='box')
def legend(ax,**kw):ax.legend(framealpha=.8,**kw)
figures={}
# Long-term measured levels and temperatures, ADC only.
fig,axs=grid(3,2)
for i,mo in enumerate(MODES):
 rr=DCMODE[mo];ax=axs[i,0];ax.plot(time,np.sqrt(col(rr,'total2_ADC_V2'))*1000,color=DATA,label='Raw RMS');ax.plot(time,np.sqrt(col(rr,'AC2_ADC_V2'))*1000,color=DATA,ls='--',label='AC RMS');ax.set(title=mo+' — full-band level',ylabel='RMS [mV ADC]');legend(ax,ncol=2)
 ax=axs[i,1];sensor=['t15_mK','t16_mK','t17_mK'][i];ax.plot(time,col(rr,sensor),color=DATA);ax.set(title=sensor.replace('_',' '),ylabel='Temperature [mK]')
for ax in axs[-1]:ax.set_xlabel('Elapsed acquisition clock time [h]')
figures['stability']=save(fig,'exp_campaign_stability')
# One empirical DC/AC page, no hardware or response hypotheses.
fig,axs=grid(3,4,h=4.9)
for i,mo in enumerate(MODES):
 rr=DCMODE[mo];ax=axs[i,0];ax.plot(time,col(rr,'mean_I_ADC_V')*1000,color=DATA,label='mean I');ax.plot(time,col(rr,'mean_Qeff_ADC_V')*1000,color=DATA,ls='--',label='mean Qeff');ax.set(title=mo+' — complex mean',ylabel='DC [mV ADC]');legend(ax,ncol=2,fontsize=6)
 ax=axs[i,1];ax.plot(time,col(rr,'DC_abs_ADC_V')*1000,color=DATA,label='|mu|');ax.set(title='DC magnitude / phase',ylabel='|mu| [mV ADC]');other=ax.twinx();other.plot(time,col(rr,'DC_phase_rad'),color=DATA,ls=':',alpha=.75);other.set_ylabel('arg(mu) [rad]',fontsize=7);other.tick_params(labelsize=6)
 ax=axs[i,2]
 for key,label,ls in [('DC2_ADC_V2','DC²',':'),('AC2_ADC_V2','AC²','--'),('total2_ADC_V2','Total²','-')]:ax.semilogy(time,col(rr,key),color=DATA,ls=ls,label=label)
 ax.set(title='Squared-voltage decomposition',ylabel='Mean square [V² ADC]');legend(ax,ncol=3,fontsize=5.5)
 ax=axs[i,3];ax.plot(time,col(rr,'DC2_over_AC2'),color=DATA);ax.set(title='DC relative to AC',ylabel='DC² / AC²')
for ax in axs[-1]:ax.set_xlabel('Elapsed acquisition clock time [h]')
figures['dc']=save(fig,'exp_campaign_DC_AC')
fig,axs=grid(3,3,h=4.9)
offsets=sorted({float(r['offset_hz']) for r in bands})
for ax,off in zip(axs.flat,offsets):
 for i,mo in enumerate(MODES):
  rr=sorted([r for r in bands if r['mode']==mo and float(r['offset_hz'])==off],key=lambda r:int(r['run']));assert len(rr)==260
  ax.plot(time,col(rr,'change_pct'),color=DATA,ls=['-','--',':'][i],label=mo)
 ax.set(title=f'Offset {off/1000:+g} kHz',ylim=(-1,4),ylabel='RMS change [%]');legend(ax,ncol=3,fontsize=5.5)
for ax in axs[-1]:ax.set_xlabel('Elapsed acquisition clock time [h]')
figures['bands']=save(fig,'exp_nine_bands')
# Selected-run IQ and quadratures; full campaign pooled amplitude histogram.
fig,axs=grid(3,3,h=5.1)
for i,mo in enumerate(MODES):
 a=fulliq[mo];e=a['edges'];c=a['hist'];iq(axs[i,0],e,c,DATA);axs[i,0].set_title(mo+' IQ — run 680')
 ax=axs[i,1];stairs(ax,e,c.sum(axis=1),DATA,'I',1000);stairs(ax,e,c.sum(axis=0),DATA,'Qeff',1000,'--');ax.set(title=mo+' quadratures — run 680',xlabel='Voltage [mV ADC]',ylabel='Density [mV^-1]',xlim=(-110,110));legend(ax)
 ax=axs[i,2];e=glob['amplitude_edges_v']*sc;c=glob['global_'+mo+'_amp'];stairs(ax,e,c,DATA,'260 runs',1000);ax.set(title=mo+' amplitude — campaign',xlabel='Raw |z| [mV ADC]',ylabel='Density [mV^-1]',xlim=(0,180),ylim=(1e-9,.15),yscale='log')
figures['distributions']=save(fig,'exp_IQ_quadratures_amplitude')
fig,axs=grid(2,3)
for i,mo in enumerate(MODES):
 e=data['arrays/phase_edges_rad'][:];p=data['arrays/global_'+mo+'_phase'][:];ax=axs[0,i];stairs(ax,e,p,DATA,'Absolute phase');ax.axhline(1/(2*np.pi),color=NAVY,ls=':',label='Uniform');ax.set(title=mo+' — absolute phase',xlabel='arg(z) [rad]',ylabel='Density [rad^-1]',xlim=(-np.pi,np.pi));legend(ax)
 ax=axs[1,i]
 for lag,ls in zip([1,10,100],['-','--',':']):stairs(ax,e,data[f'arrays/global_{mo}_delta_{lag}'][:],DATA,f'{lag/5:g} us',ls=ls)
 ax.set(title=mo+' — phase increments',xlabel='arg[z(t+lag) z*(t)] [rad]',ylabel='Density [rad^-1]',xlim=(-np.pi,np.pi));legend(ax,ncol=3,fontsize=6)
figures['phase']=save(fig,'exp_phase_increments')
fig,axs=grid(1,3,h=2.4)
for i,mo in enumerate(MODES):
 rr=sorted([r for r in runs if r['mode']==mo],key=lambda x:x['run']);ax=axs[0,i]
 for label,key,ls in [('Local','local_3sigma_fraction','-'),('Fixed reference','reference_3sigma_fraction','--')]:ax.plot(time,col(rr,key)*100,color=DATA,ls=ls,label=label)
 ax.set(title=mo+' — threshold k = 3',xlabel='Elapsed acquisition clock time [h]',ylabel='Samples above threshold [%]',ylim=(.5,.8));legend(ax)
figures['tails']=save(fig,'exp_threshold_rates')
# Experimental PSD and complex correlation: existing single-run selected window.
fig,axs=grid(2,3)
for i,mo in enumerate(MODES):
 a=pairs[mo];f=a['frequency_hz']/1e6;ax=axs[0,i];ax.plot(f,10*np.log10(a['data_psd_v2_hz']),color=DATA,lw=.55);ax.set(title=mo+' — measured PSD',xlabel='Complex frequency [MHz]',ylabel='PSD [dB V²/Hz ADC]',xlim=(-2.5,2.5),ylim=(-135,-85))
 g=a['data_g1'];lag=a['lag_s']*1e6;sel=(lag>0)&(lag<=10);ax=axs[1,i]
 ax.plot(lag[sel],g.real[sel],'o-',color=DATA,ms=2.4,label='Re g1');ax.plot(lag[sel],g.imag[sel],'s--',color=DATA,mfc='white',ms=2.4,label='Im g1');ax.axhline(0,color=GRAY,lw=.5);ax.set(title=mo+' — nonzero-lag correlation',xlabel='Lag [us]',ylabel='g1',xlim=(0,10),ylim=(-.08,.08));legend(ax,ncol=2)
figures['experimental_psd']=save(fig,'exp_PSD_and_complex_g1')
# Reference comparison: absolute amplitudes and shape are separate.
fig,axs=grid(2,3)
for i,mo in enumerate(MODES):
 g=toy[mo];te=g['amplitude_edges_v'][:];tc=g['amplitude_counts'][:];mean=float(data['summary/modes/'+mo+'/mean_amplitude_v'][()])*sc;de=data['modes/'+mo+'/noise_edges_v'][:]*sc+mean;dc=data['modes/'+mo+'/noise_counts'][:];ax=axs[0,i]
 for e,c,color,label in [(de,dc,DATA,'Data'),(te,tc,TOY,'Toy')]:stairs(ax,e,c,color,label,1000)
 ax.set(title=mo+' — absolute amplitude',xlabel='Raw |z| [mV ADC]',ylabel='Density [mV^-1]',xlim=(0,180),ylim=(1e-9,.15),yscale='log');legend(ax)
 ax=axs[1,i]
 for e,c,color,pop in [(de,dc,DATA,'data'),(te,tc,TOY,'toy')]:
  sigma=amps[mo][pop]['sigma_v'];cc=np.r_[np.cumsum(c[::-1])[::-1],0]/c.sum();x=e**2/(2*sigma**2);ok=(cc>0)&(x<19);ax.plot(x[ok],np.log(cc[ok]),color=color,label=pop)
 x=np.linspace(0,19);ax.plot(x,-x,':',color=NAVY,label='Rayleigh');ax.set(title='Shape only: each saved sigma',xlabel='A² / (2 sigma_fit²)',ylabel='log P(amplitude > A)',xlim=(0,19),ylim=(-20,0));legend(ax,ncol=3,fontsize=6)
figures['amp_comparison']=save(fig,'compare_amplitude_and_CCDF')
fig,axs=grid(3,3,h=5.2)
for i,mo in enumerate(MODES):
 iq(axs[0,i],fulliq[mo]['edges'],fulliq[mo]['hist'],DATA);axs[0,i].set_title(mo+' — data IQ')
 iq(axs[1,i],toy[mo+'/IQ_edges_v'][:],toy[mo+'/IQ_counts'][:],TOY);axs[1,i].set_title(mo+' — toy IQ')
 ax=axs[2,i];e=data['arrays/phase_edges_rad'][:];stairs(ax,e,data['arrays/global_'+mo+'_phase'][:],DATA,'Data');stairs(ax,toy[mo+'/phase_edges_rad'][:],toy[mo+'/phase_counts'][:],TOY,'Toy');ax.axhline(1/(2*np.pi),color=NAVY,ls=':',label='Uniform');ax.set(title=mo+' — absolute phase',xlabel='arg(z) [rad]',ylabel='Density [rad^-1]',xlim=(-np.pi,np.pi));legend(ax,ncol=3,fontsize=5.8)
figures['IQcomparison']=save(fig,'compare_IQ_and_phase')
fig,axs=grid(2,3)
for i,mo in enumerate(MODES):
 a=pairs[mo];f=a['frequency_hz']/1e6
 for j in [0,1]:
  ax=axs[j,i]
  for pop,c in [('data',DATA),('toy',TOY)]:ax.plot(f,10*np.log10(a[pop+'_psd_v2_hz']),color=c,lw=.55,label=pop)
  ax.set(title=mo+(' — full spectrum' if j==0 else ' — central zoom'),xlabel='Complex frequency [MHz]',ylabel='PSD [dB V²/Hz ADC]',xlim=(-2.5,2.5) if j==0 else (-.2,.2),ylim=(-140,-85));legend(ax,ncol=2)
figures['PSDcomparison']=save(fig,'compare_full_and_central_PSD')
fig,axs=grid(3,3,h=5.25)
zoom_limits={}
for i,mo in enumerate(MODES):
 a=pairs[mo];lag=a['lag_s']*1e6;sel=(lag>=0)&(lag<=10);pos=(lag>0)&(lag<=10)
 for pop,c in [('data',DATA),('toy',TOY)]:
  g=a[pop+'_g1'];ax=axs[0,i];ax.plot(lag[sel],g.real[sel],'o-',color=c,ms=2,label=pop+' Re');ax.plot(lag[sel],g.imag[sel],'s--',mfc='white',color=c,ms=2,label=pop+' Im')
  for j,part in [(1,'real'),(2,'imag')]:
   vals=getattr(g,part);axs[j,i].plot(lag[pos],vals[pos],'o-' if part=='real' else 's--',mfc=c if part=='real' else 'white',color=c,ms=2.5,label=pop)
   assert abs(vals[pos]).max()<(.08 if part=='real' else .02)
 ax=axs[0,i];ax.set(title=mo+' — Re / Im common scale',ylim=(-1.05,1.05),ylabel='g1',xlim=(0,10));legend(ax,ncol=2,fontsize=5.2)
 for j,part in [(1,'Re'),(2,'Im')]:
  ax=axs[j,i];ax.set(title=mo+' — '+part+' positive lag',ylim=(-.08,.08) if part=='Re' else (-.02,.02),ylabel=part+' g1',xlim=(0,10));ax.axhline(0,color=GRAY,lw=.5);legend(ax,ncol=2,fontsize=6)
 axs[2,i].set_xlabel('Lag [us]');zoom_limits[mo]={'Re':[-.08,.08],'Im':[-.02,.02]}
figures['g1comparison']=save(fig,'compare_complex_g1_sampled')
# Saved fits are drawn only within their existing fit interval, no optimization.
fig,axs=grid(1,3,h=2.6)
for i,mo in enumerate(MODES):
 a=pairs[mo];lag=a['lag_s']*1e6;pos=(lag>0)&(lag<=10);ax=axs[0,i]
 for pop,c in [('data',DATA),('toy',TOY)]:
  ax.plot(lag[pos],a[pop+'_g1'].real[pos],'o-',color=c,ms=2,label=pop)
  f=comp['modes'][mo][pop+'_upper_fit']
  if f['tau_us']>=.2 and f['r_squared_on_selected_peaks']>=.7:
   tt=np.linspace(f['plot_range_us'][0],4,150);ax.plot(tt,f['offset']+f['amplitude']*np.exp(-tt/f['tau_us']),color=NAVY,ls='--' if pop=='toy' else '-',lw=1.2,label=pop+' saved fit')
 ax.set(title=mo+' — signed upper maxima',xlabel='Lag [us]',ylabel='Re g1',xlim=(0,10),ylim=(-.08,.08));legend(ax,ncol=2,fontsize=6)
figures['times']=save(fig,'compare_saved_characteristic_times')
D=sd.Deck();provenance=[]
def page(title,sub,scope,sources,notes=''):
 s=D.new(' ',sub,sources,notes+'\nScope: '+scope);s['title']=title;s['items'][1]['text']=title;s['items'][1]['size']=25;s['footer']='FLASH | v44 | '+('PART II — EXPERIMENTAL DATA' if len(D.slides)<=9 else 'PART III — TOY VS DATA')
 provenance.append({'slide':14+len(D.slides),'title':title,'scope':scope,'source':sources});return s
def txt(s,x,y,w,ht,t,size=15,bold=False,color=sd.INK):D.text(s,x,y,w,ht,t,size,bold,color)
def table(s,heads,rr,y=2,widths=None,size=12,rowh=.48,headh=.65):
 widths=widths or [12/len(heads)]*len(heads)
 for i,row in enumerate([heads]+rr):
  yy=y if i==0 else y+headh+(i-1)*rowh;x=.65
  for val,w in zip(row,widths):txt(s,x,yy,w-.08,headh if i==0 else rowh,str(val),size,i==0);x+=w

def image(s,key,y=1.75,ht=4.45):D.image(s,.4,y,12.55,ht,figures[key])
def caption(s,t,size=12):txt(s,.65,6.37,12.05,.44,t,size)
# PART II: independent experimental characterization.
s=page('Experimental dataset and analysis methodology','Part II | consolidated 260-run campaign; selected-window diagnostics are labelled separately.','Campaign 680–939 plus explicitly selected run/window products.','v2 campaign pilot_findings.json; original campaign coverage; iq_noise_v2.py definitions; active v40 comparison metadata.',
 '15.1461h is summed acquired duration, not wall-clock coverage. Runs are not concatenated into a continuous phase/correlation stream. The stored legacy summaries used±5V; actual science±2V conversion is applied exactly once, factor0.4 voltage/0.16 squared. Run means are removed before nine FIR paths; no per-SPEC centering. Available full-campaign amplitude summaries are invariant under that continuity/DC-analysis revision. Selected spectra/correlation do not establish campaign-wide stationarity.')
D.bullets(s,.75,1.9,11.75,['260 complete runs (680–939), 260,000 SPEC; 272.62976 billion complex samples per mode. Acquired time 15.1461 h; each run 209.7152 s.','5 MS/s, 16 bit, physical ADC range ±2 V; Δ = 4/65535 V = 61.036 uV. z = I − iQhardware = I + iQeff.','DC = mu = mean(z) per run; DC² = |mu|². AC² = mean|z − mu|². Raw RMS² = DC² + AC²; these are squared voltages, not RF watts.','sigma is the Rayleigh quadrature-scale parameter; std(|z|) and AC RMS are different quantities.','Campaign trends use 260 run summaries. PSD and g1 comparisons use the existing 1.048576 s window in run 680; distribution scopes are stated per figure.'],size=17,gap=.17)
s=page('Long-term noise stability and temperature evolution','Campaign: 260 runs | measured levels and temperatures versus acquisition clock.','All 260 runs, one full-run level/temperature summary per point.','Corrected longterm.csv; consolidated v2 findings; T15/T16/T17 observed sensor summaries.',
 'No nominal input-referred gain is used to label the measured ADC levels. Curves are raw/AC RMS, not amplitude standard deviations. Temperature associations share time trends and are not causal attribution.')
image(s,'stability');caption(s,'AC RMS spans: TM010 2.64%; TM011 2.75%; TM012 3.26%. Temperature association alone does not establish causality.')
s=page('Long-term DC and AC evolution','Campaign: 260 runs | offsets, phase and squared-voltage decomposition remain distinct.','All 260 runs; complex mean computed separately for each entire run.','Measured v2 complex moments and ODB-corrected longterm.csv; no nominal gain correction.',
 'I/Q DC plotted in ADC volts; phase is arg(I+iQeff). Solid magnitude and dotted phase share time but separate y axes. Total²=DC²+AC²; raw/AC curves may almost coincide because DC power is small. DC/AC ratio is displayed explicitly. Slow offsets and drifting AC coexist; no model of their origin is introduced.')
image(s,'dc');caption(s,'DC changes in magnitude and direction while AC power also drifts. Run-mean subtraction preserves slower fluctuations within each run.')
s=page('Frequency-resolved noise stability','Campaign: nine 50 kHz nominal bands; identical frequency offsets and common drift scale.','260 v2 runs per mode/band; DC-removal before/after comparison only in the paired 12-run pilot.','v2 band_rms_relative_to_run680.csv and pilot_findings.json; same FIR settings.',
 'Offsets−1000,−500,−250,−100,0,+100,+250,+500,+1000kHz. 2001tap FIR, decimation20. ENBW is not automatically50kHz. Curves show percent RMS change relative to run680 for each mode-band pair, not per-mode equalized absolute amplitudes. Before/after endpoint comparison uses paired pilot, not260 v1 runs.')
image(s,'bands',ht=4.3);caption(s,'Paired-pilot center-band endpoint drift, before → after DC removal: TM010 −0.49 → +1.06%; TM011 −7.10 → +0.89%; TM012 +1.07 → +1.08%.',11)
s=page('Experimental amplitude and IQ distributions','Amplitude: pooled 260 runs | IQ and quadratures: complete run 680, with finer saved bins.','Amplitude272.63billion samples/mode; selected IQ/quadratures1.048576billion samples/mode.','Global amplitude histogram (amplitude-invariant legacy summary); full_iq_data_MODE.npz; ODB ADC conversion.',
 'Marginals are projections of existing full-run512×512 IQ histograms, not new fitted Gaussians. Raw IQ is not centered. Counts retain their original binning; one TM012 sample lies outside the saved IQ rectangle. Pooled amplitude mixes changing run scales, so it is not treated as a single stationary sample. No new fit or raw read.')
image(s,'distributions');caption(s,'Quadrature and IQ panels describe run 680, not the whole campaign. The pooled amplitude contains the measured long-term scale drift.',11)
s=page('Experimental phase and phase increments','Complete run 680 | absolute angle, plus increments at 0.2, 2 and 20 us.','Selected full run680,209.7152s; continuous v2 statistics across SPEC, no joining of runs.','run00680_noise_v2.h5 arrays/global_MODE_phase and delta_1/10/100; absolute I−iQ convention.',
 'Use the full-stream absolute-phase histogram, not the diagnostic histogram rotated to the first valid sample. Endpoints with zero amplitude have undefined phase and are excluded by the stored estimator. Continuous v2 increment products are used; old campaign increment arrays omit SPEC-boundary pairs and are not substituted. No campaign-pooled angular conclusion is claimed.')
image(s,'phase');caption(s,'Angle histograms and phase increments are different observables. Zero-amplitude phases are excluded; no per-run phase alignment is applied.')
s=page('Amplitude tails and rare events','Campaign: local and fixed thresholds answer different questions.','260 runs; local thresholds per run, fixed thresholds from the saved pilot reference.','amplitude_model_comparison.json; runs.csv; campaign_summary.json; original amplitude counts unchanged.',
 'Tlocal=empirical mean(A)+k std(A), Treference=fixed baseline mean(A)+k baseline std(A), from the saved100SPEC run680 pilot (not statistically independent of all campaign data). Rayleigh expectations sum Nrun exp(−Tlocal²/(2srun²)), srun²=E[A²]/2. These are in-sample moment-based expectations, not new fits. Counts count samples, not independent events. Run correlations invalidate naive independent-sample detection significance. This local empirical convention differs from PartIII fitted-Rayleigh thresholds.')
image(s,'tails',y=1.68,ht=2.25)
rr=[]
for mo in MODES:
 vals=[]
 for k in ['3','5','7']:
  v=tails['modes'][mo][k];vals.append(f"{v['observed']:,} / {v['rayleigh_expected']:,.0f}")
 rr.append([mo]+vals)
table(s,['Mode','Local k=3: observed / Rayleigh','Local k=5: observed / Rayleigh','Local k=7: observed / Rayleigh'],rr,y=4.05,widths=[.95,3.9,3.8,3.35],size=11,rowh=.38,headh=.55)
fixed7=[globalmeta['modes'][mo]['exceedances']['reference']['7']['samples_above'] for mo in MODES]
txt(s,.65,5.92,12.05,.3,'Fixed-reference k=7 counts: '+ ' / '.join(f'{n:,}' for n in fixed7)+' (TM010 / TM011 / TM012).',11)
caption(s,'Counts are samples above empirical local thresholds. A fixed-reference excess can reflect a changing scale; neither rate is a detection significance.',11)
s=page('Experimental PSD and temporal correlations','Selected 1.048576 s window in run 680 | measured spectra and signed complex g1.','Five continuous SPEC, not full-campaign or full-run PSD/covariance.','Existing active step6 comparison MODE_comparison.npz: unchanged measured arrays; original v21 estimator.',
 'PSD uses original full-window Hann periodogram, display bins244.14Hz. Covariance is the original mean-subtracted finite-window complex estimator, normalized by R[0]. Plot0.2–10us with actual200ns delays; negative real values are retained. Existing descriptive signed-upper-maxima decay fits are summarized separately; no new fit.')
image(s,'experimental_psd');caption(s,'Saved upper-maxima decay times: TM010 0.926 us; TM011 1.419 us; TM012 1.385 us. These describe this selected window, not campaign stationarity.')
s=page('Experimental findings','Measured properties before any comparison with the toy.','Long-term entries:260runs; decay-time entries:selected1.048576s run680 window.','Consolidated v2 findings, corrected DC moments, original signed-upper-maxima fits.',
 'No hardware cause, LF-response modification or simulation-derived explanation is advanced. Stable normalized amplitude statistics do not prove stationary independent Gaussian IQ. All times and samples retain their original estimator scopes.')
rr=[]
for mo in MODES:
 dc_ratio=col(DCMODE[mo],'DC2_over_AC2');f=comp['modes'][mo]['data_upper_fit'];rr.append([mo,f"{findings[mo]['fullband_ac_span_pct']:.2f}%",f"{dc_ratio.min():.2g} – {dc_ratio.max():.2g}",f"{f['tau_us']:.3f}",f"{f['r_squared_on_selected_peaks']:.3f}"])
table(s,['Mode','Campaign AC RMS span','Campaign DC²/AC² range','Selected decay [us]','Selected fit R²'],rr,y=1.95,widths=[1.0,2.6,3.2,2.7,2.5],size=12)
D.bullets(s,.8,4.3,11.7,['The three modes share long-term level drift; DC magnitude/phase and AC power evolve separately.','Local amplitude tails remain close to Rayleigh expectations, with mode-dependent residuals; fixed thresholds track scale drift.','Selected-run IQ/phase structure, the central TM010 spectral deficit and nonzero-lag complex correlations are measurable features.'],size=17,gap=.17)
# PART III: only the frozen reference normalization, no alternate LF response.
s=page('Absolute noise amplitude','Part III | step 6 reference versus run 680, with unchanged Part I normalization.','Expected step6 continuous RMS; complete209.7152s toy and data moments/fitted amplitude scale.','Active full-run step6 metrics; v40 saved Rayleigh fit parameters; corrected v2 raw and AC moments.',
 'Same physical inputs/calibration checksums as PartI. RF103.4dB, kzscience=.01 kzcal, calibration±5V/science±2V. Data raw RMS differs from AC RMS by measured DC; Rayleigh sigma comes from the saved raw-amplitude fit. Values are not recomputed as RMS/sqrt2 for noncentered data. No gain or noise-temperature normalization to data. No new fit.')
rr=[]
for mo in MODES:
 r=metrics['results'][mo];d=DCMODE[mo][0];pred=short['metrics'][mo]['total_RMS_expected_ADC_V'];raw=np.sqrt(float(d['total2_ADC_V2']));ac=np.sqrt(float(d['AC2_ADC_V2']));rr.append([mo,f'{pred*1000:.3f}',f'{raw*1000:.3f}',f'{ac*1000:.3f}',f"{r['sigma_expected_v']*1000:.3f}",f"{amps[mo]['data']['sigma_v']*1000:.3f}",f'{ac/pred:.3f}'])
table(s,['Mode','Expected RMS\n[mV ADC]','Data raw RMS\n[mV ADC]','Data AC RMS\n[mV ADC]','Expected sigma\n[mV ADC]','Data fit sigma\n[mV ADC]','Data AC / toy'],rr,y=2,widths=[.95,1.85,1.9,1.9,1.8,1.8,1.8],size=12,headh=.85)
D.bullets(s,.8,4.75,11.7,['Absolute amplitudes are low in the reference toy for every mode; the discrepancy is mode dependent.','Raw RMS, AC RMS and Rayleigh sigma are different measurements. Mean-square noise is in V² ADC; no RF watts are inferred here.','The numerical calibration and physical parameters are the approved Part I values.'],size=17,gap=.2)
s=page('Amplitude distributions and statistical tails','Absolute amplitude above; separately normalized CCDF below tests shape only.','Full209.7152s toy and run680 populations,1,048,576,000samples per mode/population.','Saved full-run amplitude histograms and existing Rayleigh scales; toy metrics and full_iq_counts data entries.',
 'Top panels retain ADC millivolts and identical axes. Bottom CCDF uses each population own saved sigma, explicitly shape-only; this must not conceal the absolute discrepancy. No refit, goodness-of-fit p-value or independent sample claim. Raw amplitude is not globally recentered. Fitted-Rayleigh threshold T=muR+k stdR uses saved sigma; this differs from empirical per-run thresholds in PartII. Full-run centered histogram is unavailable and is not synthesized.')
image(s,'amp_comparison',ht=4.2)
prob={k:float(np.exp(-(.5*np.pi**.5*2**.5+k*np.sqrt((4-np.pi)/2))**2/2)) for k in [3,5,7]}
counts=js(V40/'data/full_iq_counts.json')
caption(s,'Rayleigh T = muR + k stdR: P3=0.0056275; P5=3.51494e−5; P7=3.94382e−8. >7 counts toy/data: 35/37, 58/40, 36/42 (TM010/011/012); expectation ≈41.35.',10.8)
s=page('IQ distributions and phase structure','Full run 680 versus full-run reference | raw IQ and absolute angles, without phase alignment.','Complete209.7152s populations; one saved IQ-grid outlier for data TM012.','Original full_iq_data_MODE.npz; current step6 toy IQ/phase histograms; v2 absolute global phase counts.',
 'Same physical IQ axes for every displayed population. IQ grid uses all in-range samples; color intensities use common log-count limits across all six populations and are not a gain rescaling. Data normalized pseudocovariance≈.041/.047/.042 versus toy≈few×10−5 in existing binned estimator. Toy complete-run increment histograms at matching lags are not available; no marginal-phase result is substituted for that missing comparison. Data increments are shown independently in PartII.')
image(s,'IQcomparison',ht=4.2);caption(s,'Data var(I)/var(Qeff): 0.950 / 0.931 / 0.945; toy ≈1. Matching full-run toy phase-increment histograms are unavailable; comparison is not inferred.',10.8)
s=page('Power spectral density','Same estimator, duration, ADC units and frequency axes; central regions are shown explicitly.','Matched selected1.048576s windows; not full-run or campaign-pooled PSDs.','Existing active comparison NPZ: full-window Hann,244.14Hz display bins, verified I−iQ convention.',
 'Absolute PSD is not renormalized. Both populations have identical frequency grids, full-band limits and central zoom±200kHz. TM010 discrepancy is presented without interpretation; no later LF/splitter model is included. No new spectral fit or raw reconstruction.')
image(s,'PSDcomparison');caption(s,'The reference TM010 central deficit is broader than the measured deficit. Higher-mode spectra also retain their absolute-level mismatch.')
s=page('Complex autocorrelation','Re and Im shown separately; full scale above, positive-lag zooms below.','Matched selected1.048576s windows; every plotted lag is sampled at200ns.','Existing active data/toy complex covariance arrays; no smoothing, fit or lag interpolation.',
 'g1=R[k]/R[0] uses the same archived estimator for data and toy. Zero lag is retained in full-scale row and excluded from zoom rows. Re extrema are checked against±.08 and Im against±.02; the same limits apply to data and toy for all modes. Multiplicative linear gain cancels, so this is a shape comparison, distinct from absolute PSD/RMS. No inferred long-time stationarity.')
image(s,'g1comparison',ht=4.4);caption(s,'Markers: actual delays every 0.2 us. Negative Re(g1) and the imaginary component remain visible; zoom limits contain all displayed samples.',11)
s=page('Characteristic times','Preserve the original signed-upper-maxima fits; distinguish these times from intrinsic cavity poles.','Existing upper-maxima fits on0.3–4us; plot extends to10us; cavity times from fixed physical inputs.','Saved comparison.json data_upper_fit/toy_upper_fit; original step6 physical parameters; no fit executed.',
 'Only saved reliable curves are drawn within their original fit interval. TM010 toy tau=.0349us is below one200ns sample and R²=.360: mark unresolved, not a physical time. Other upper-maxima fits are descriptive finite-window C+Aexp(−t/tau), C free; R² refers to selected maxima, not every covariance point. Different envelope estimators yield different numbers and are not mixed. No standard errors invented.')
image(s,'times',y=1.7,ht=2.45)
rr=[]
for mo in MODES:
 r=comp['modes'][mo];tf=r['toy_upper_fit'];df=r['data_upper_fit'];good=tf['tau_us']>=.2 and tf['r_squared_on_selected_peaks']>=.7
 rr.append([mo,f"{short['metrics'][mo]['tau_cavity_us']:.3f}",f"{df['tau_us']:.3f}",f"{tf['tau_us']:.3f}" if good else 'unresolved',f"{df['r_squared_on_selected_peaks']:.3f} / {tf['r_squared_on_selected_peaks']:.3f}"])
table(s,['Mode','Intrinsic cavity tau [us]','Data fitted tau [us]','Toy fitted tau [us]','Fit R² data / toy'],rr,y=4.25,widths=[1.05,2.75,2.7,2.7,2.8],size=12,rowh=.39,headh=.63)
caption(s,'TM010 toy: formal tau≈0.035 us, below sampling, R²=0.360 → unresolved. Cavity pole, fitted decay and level-stability time are different observables.',11)
s=page('Summary of agreements and discrepancies','Reference step 6 only | quantitative evidence and explicit comparison limits.','Amplitude/IQ:full run680; g1/time/PSD:matched1.048576s windows; no campaign-wide model test.','Saved reference comparison and corrected run680 moments; no response modification, new fit or renormalization.',
 'Partial Rayleigh-shape agreement does not establish correct absolute scale or independent Gaussian IQ. Values report existing finite-window estimators without new uncertainty claims. The unresolved discrepancies remain results. No PartIV or physical cause is assembled.')
ratio=[];rmse=[]
for mo in MODES:
 ac=np.sqrt(float(DCMODE[mo][0]['AC2_ADC_V2']));pred=short['metrics'][mo]['total_RMS_expected_ADC_V'];ratio.append(f'{ac/pred:.3f}')
 a=pairs[mo];sel=(a['lag_s']>0)&(a['lag_s']<=10e-6);rmse.append(f"{np.sqrt(np.mean(abs(a['data_g1'][sel]-a['toy_g1'][sel])**2)):.4f}")
rr=[['AC RMS data / prediction',*ratio,'Not reproduced'],['Raw-amplitude CDF edge gap',*[f"{amps[mo]['data']['CDF_edge_gap']:.2g}" for mo in MODES],'Near Rayleigh shape'],['Data IQ pseudocov. ratio',*[f"{iqstats[mo]['data']['pseudo_ratio']:.3f}" for mo in MODES],'Toy ≈ few ×10^-5'],['Complex g1 RMSE (0.2–10 us)',*rmse,'Shape mismatch remains'],['Saved fitted tau: data / toy [us]','0.926 / unresolved','1.419 / 1.322','1.385 / 1.278','Partial; TM010 fails'],['Central PSD structure','Broader in toy','Level low','Level low','Not fully reproduced'],['Matching full-run phase increments','Unavailable','Unavailable','Unavailable','Not assessed']]
table(s,['Observable','TM010','TM011','TM012','Assessment'],rr,y=1.9,widths=[3.35,2.05,2.05,2.05,2.5],size=10.5,rowh=.47,headh=.54)
caption(s,'Approximate marginal-shape agreement coexists with absolute-level, IQ and temporal/spectral discrepancies. No correction has been adjusted to remove them.',11)
assert len(D.slides)==16
for s in D.slides:
 for it in s['items']:
  if it['kind']=='text' and it['y']==.38:
   while len(sd.wrap(s['title'],it['w']*.87,it['size']).splitlines())>1:it['size']-=1
   it['text']=s['title']
# Render ONLY Parts II and III. The original 14 slides are appended from the approved files.
TAIL=OUT/'parts_II_III';sd.export(D,TAIL,'v44_parts_II_III','17 November 2026',page_offset=14,total_pages=30)
subprocess.run(['pdfunite',str(B/'iq_noise_summary_v43_partI.pdf'),str(TAIL/'iq_noise_summary_v44_parts_II_III.pdf'),str(OUT/'iq_noise_summary_v44.pdf')],check=True)
base=Presentation(B/'iq_noise_summary_v43_partI.pptx');extra=Presentation(TAIL/'iq_noise_summary_v44_parts_II_III.pptx');RNS='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
for src in extra.slides:
 dst=base.slides.add_slide(base.slide_layouts[6]);dst.background.fill.solid();dst.background.fill.fore_color.rgb=RGBColor.from_string(sd.BG.lstrip('#'))
 for sh in src.shapes:
  el=copy.deepcopy(sh.element)
  for node in el.iter():
   for attr in [RNS+'embed',RNS+'link']:
    old=node.get(attr)
    if old:
     rel=src.part.rels[old]
     if rel.reltype.endswith('/image'):
      _,new=dst.part.get_or_add_image_part(io.BytesIO(rel.target_part.blob));node.set(attr,new)
     else:raise ValueError('Unexpected shape relationship '+rel.reltype)
  dst.shapes._spTree.insert_element_before(el,'p:extLst')
 dst.notes_slide.notes_text_frame.text=src.notes_slide.notes_text_frame.text
base.save(OUT/'iq_noise_summary_v44.pptx')
# Verify first fourteen slide XML parts remain byte-identical, including original page counters.
with zipfile.ZipFile(B/'iq_noise_summary_v43_partI.pptx') as old,zipfile.ZipFile(OUT/'iq_noise_summary_v44.pptx') as new:
 for i in range(1,15):assert old.read(f'ppt/slides/slide{i}.xml')==new.read(f'ppt/slides/slide{i}.xml'),i
for i in range(1,15):shutil.copy2(B/f'slide_{i:02d}.png',OUT/f'slide_{i:02d}.png')
for i in range(1,17):shutil.copy2(TAIL/f'slide_{i:02d}.png',OUT/f'slide_{i+14:02d}.png')
from PIL import Image
sheet=Image.new('RGB',(640*3,360*10),'white')
for i in range(30):
 with Image.open(OUT/f'slide_{i+1:02d}.png') as im:sheet.paste(im.resize((640,360)),((i%3)*640,(i//3)*360))
sheet.save(OUT/'contact_sheet.png')
(OUT/'slide_model.json').write_text(json.dumps(original+D.slides,indent=2,ensure_ascii=False)+'\n')
(OUT/'slides_en.md').write_text((B/'slides_en.md').read_text()+'\n\n'+(TAIL/'slides_en.md').read_text())
validation={'slides':30,'PartI_slides':14,'PartII_slides':9,'PartIII_slides':7,'PartI_XML_byte_identical':True,'PartI_rendered_previews_copied':True,'new_fits':False,'new_simulations':False,'new_raw_reads':False,'step6_normalization_matches_PartI':True,'g1_positive_lag_zoom_limits':zoom_limits,'input_sha256':inputs,'new_slide_provenance':provenance,'not_comparable':['Matching full-run toy phase-increment histograms unavailable','No new full-run complex-mean-centered amplitude histogram; raw amplitude shape is labelled as such','Selected PSD/g1 window is not a260-run model comparison']}
assert all(sha(p)==v for p,v in inputs.items()),'An input changed during rendering'
(OUT/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
(OUT/'slide_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
data.close();toy.close();print('v44 complete: unchanged Part I14 + experimental9 + reference comparison7 =30slides.')
