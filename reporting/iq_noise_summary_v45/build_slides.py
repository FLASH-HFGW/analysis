"""v45: run680+reference first, campaign second. Preserve approved Part I.

Only saved products/tables; no raw access, simulation or physical-response fits.
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
W=REPO.parent/'analysis-work/Run2';B=W/'reports/iq_noise_summary_v43_partI';V44=W/'reports/iq_noise_summary_v44';V40=W/'reports/iq_noise_summary_v40';OUT=W/'reports/iq_noise_summary_v45';A=OUT/'assets';A.mkdir(parents=True,exist_ok=True)
S=W/'simulation/toy_ODB_cal5_data2_LF_20261116';CAMP=W/'reports/iq_noise_summary_v17/data/v2_campaign';DC=W/'simulation/step7/dc_longterm_diagnostic/longterm.csv';LEG=W/'staging/gpfs_noise_v0_20261108/originals';H5=W/'reports/noise_v2_development_20261109/run680_full_published/run00680_noise_v2.h5'
MODES=['TM010','TM011','TM012'];DATA='#007F86';TOY='#7657A6';THERMAL='#43a1ed';ELECTRONIC='#ed812a';NAVY='#263952';GRAY='#66768A';TOTAL=34
inputs={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def track(p):p=Path(p);inputs[str(p)]=sha(p);return p
def js(p):return json.loads(track(p).read_text())
def rows(p):
 with open(track(p)) as f:return list(csv.DictReader(f))
track(Path(__file__));track(REPO/'reporting/slide_deck.py');original=js(B/'slide_model.json');prior=js(V44/'slide_model.json')
for name in ['iq_noise_summary_v43_partI.pdf','iq_noise_summary_v43_partI.pptx']:track(B/name)
track(W/'simulation/presentation_steps1_6_v43/short_examples.h5');short=js(W/'simulation/presentation_steps1_6_v43/metrics.json');metrics=js(S/'metrics.json');comp=js(S/'comparison/comparison.json');amps=js(V40/'data/amplitude_comparison_updated.json');dcr=rows(DC);campaign=rows(CAMP/'dc_ac_temperature_by_run.csv');bands=rows(CAMP/'band_rms_relative_to_run680.csv');runs=rows(LEG/'noise_global/runs.csv');trends=rows(CAMP/'trend_diagnostics.csv');counts=js(V40/'data/full_iq_counts.json');summary=js(LEG/'noise_global/campaign_summary.json')
for name in ['calibration_reconstruction','physical_parameters']:
 p=track(short['configuration'][name]);assert inputs[str(p)]==metrics['input_sha256'][str(p)]
assert metrics['RF_gain_db']==103.4 and metrics['LF_kz_amplitude_factor']==.01 and metrics['ADC_peak_V']==2
track(H5);track(S/'toy_full_run680.h5');data=h5py.File(H5,'r');toy=h5py.File(S/'toy_full_run680.h5','r')
fulliq={mo:np.load(track(V40/'data'/f'full_iq_data_{mo}.npz')) for mo in MODES}
DCMODE={mo:sorted([r for r in dcr if r['mode']==mo],key=lambda x:int(x['run'])) for mo in MODES};CROWS={mo:sorted([r for r in campaign if r['mode']==mo],key=lambda x:int(x['run'])) for mo in MODES};R680={mo:next(r for r in dcr if r['mode']==mo and int(r['run'])==680) for mo in MODES};runids=np.arange(680,940);start=float(DCMODE['TM010'][0]['time_unix']);col=lambda rr,k:np.array([float(x[k]) for x in rr]);time=(col(DCMODE['TM010'],'time_unix')-start)/3600
assert all([int(r['run']) for r in DCMODE[mo]]==runids.tolist() for mo in MODES)
plt.rcParams.update({'font.size':9,'axes.titlesize':10,'axes.labelsize':9,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':6.5,'axes.grid':True,'grid.alpha':.18,'lines.linewidth':.85})
def grid(nr,nc,h=4.8):
 fig,axs=plt.subplots(nr,nc,figsize=(12.6,h),squeeze=False);fig.subplots_adjust(left=.065,right=.985,bottom=.2 if h<3 else .12,top=.86 if h<3 else .93,hspace=.8 if nr>2 else .62,wspace=.45);return fig,axs
def save(fig,name):
 p=A/(name+'.png');fig.savefig(p,dpi=210,facecolor='white');fig.savefig(p.with_suffix('.pdf'));plt.close(fig);return p

def stairs(ax,e,c,color,label,scale=1,ls='-'):
 ax.stairs(np.maximum(c/c.sum()/np.diff(e)/scale,1e-15),e*scale,color=color,ls=ls,label=label)

def pearson(x,y):return float(np.corrcoef(x,y)[0,1])
# Statistical control for common clock drift, not a physical temperature-response fit.
clock=(time-time.mean())/time.std();design=np.column_stack([np.ones(len(clock)),clock])
def residual(x):return x-design@np.linalg.lstsq(design,x,rcond=None)[0]
figures={};derivations={}
# PART II FIGURES: RUN 680 ONLY.
vmax=max([fulliq[mo]['hist'].max() for mo in MODES]+[toy[mo+'/IQ_counts'][:].max() for mo in MODES]);cmaps={DATA:LinearSegmentedColormap.from_list('data',['white',DATA]),TOY:LinearSegmentedColormap.from_list('toy',['white',TOY])}
fig,axs=grid(3,3,h=5.2)
for i,mo in enumerate(MODES):
 for j,pop in enumerate(['data','toy']):
  e=fulliq[mo]['edges'] if pop=='data' else toy[mo+'/IQ_edges_v'][:];c=fulliq[mo]['hist'] if pop=='data' else toy[mo+'/IQ_counts'][:];color=DATA if pop=='data' else TOY;ax=axs[j,i]
  ax.pcolormesh(e*1000,e*1000,np.ma.masked_equal(c.T,0),norm=LogNorm(vmin=1,vmax=vmax),cmap=cmaps[color],rasterized=True);ax.set(title=mo+' — '+pop+' IQ',xlabel='I [mV ADC]',ylabel='Qeff [mV ADC]',xlim=(-200,200),ylim=(-200,200));ax.set_aspect('equal',adjustable='box')
  ax=axs[2,i];stairs(ax,e,c.sum(axis=1),color,pop+' I',1000);stairs(ax,e,c.sum(axis=0),color,pop+' Qeff',1000,'--')
 axs[2,i].set(title=mo+' — quadrature marginals',xlabel='Voltage [mV ADC]',ylabel='Density [mV^-1]',xlim=(-110,110));axs[2,i].legend(ncol=2,fontsize=5.8)
figures['iq']=save(fig,'run680_IQ_and_quadratures')
fig,axs=grid(2,3)
for i,mo in enumerate(MODES):
 e=data['arrays/phase_edges_rad'][:];ax=axs[0,i];stairs(ax,e,data['arrays/global_'+mo+'_phase'][:],DATA,'Data');stairs(ax,toy[mo+'/phase_edges_rad'][:],toy[mo+'/phase_counts'][:],TOY,'Toy');ax.axhline(1/(2*np.pi),color=NAVY,ls=':',label='Uniform');ax.set(title=mo+' — absolute phase',xlabel='arg(I+i Qeff) [rad]',ylabel='Density [rad^-1]',xlim=(-np.pi,np.pi));ax.legend(ncol=3)
 ax=axs[1,i]
 for lag,ls in zip([1,10,100],['-','--',':']):stairs(ax,e,data[f'arrays/global_{mo}_delta_{lag}'][:],DATA,f'Data {lag/5:g} us',ls=ls)
 ax.set(title=mo+' — data phase increments',xlabel='arg[z(t+lag) z*(t)] [rad]',ylabel='Density [rad^-1]',xlim=(-np.pi,np.pi));ax.legend(ncol=3,fontsize=5.8)
figures['phase']=save(fig,'run680_phase_and_increments')
ks=np.array([3,5,7]);radii=np.sqrt(np.pi/2)+ks*np.sqrt((4-np.pi)/2);prob=np.exp(-radii*radii/2);expected=1048576000*prob
fig,axs=grid(1,3,h=2.8)
for i,mo in enumerate(MODES):
 ax=axs[0,i];ax.semilogy(ks,counts['data_'+mo]['above_3_5_7'],'o-',color=DATA,label='Data');ax.semilogy(ks,metrics['results'][mo]['samples_above_3_5_7'],'s--',color=TOY,label='Toy');ax.semilogy(ks,expected,':',color=NAVY,label='Rayleigh expectation');ax.set(title=mo+' — full-run sample counts',xlabel='k in T = mu_R + k std_R',ylabel='Count above threshold',xticks=ks);ax.legend()
figures['tails']=save(fig,'run680_threshold_counts')
# PART III FIGURES: EACH DERIVATION USES ALL260 MATCHED RUN SUMMARIES.
tempstats={}
fig,axs=grid(3,3,h=5.1)
for i,mo in enumerate(MODES):
 rr=DCMODE[mo];P=col(rr,'AC2_ADC_V2')*1e6
 for j,sensor in enumerate([15,16,17]):
  T=col(rr,f't{sensor}_mK');r=pearson(T,P);rt=pearson(residual(T),residual(P));stored=next(x for x in trends if x['mode']==mo and x['metric']=='ac_squared_v2' and int(x['sensor'])==sensor)
  assert np.isclose(r,float(stored['r_temperature']),atol=1e-10);assert np.isclose(rt,float(stored['r_temperature_after_linear_time']),atol=1e-10)
  tempstats[mo+'_'+str(sensor)]={'n':260,'r_raw':r,'r_after_linear_time':rt};ax=axs[i,j];ax.scatter(T,P,color=DATA,s=8,alpha=.5);ax.set(title=f'{mo} vs T{sensor}',xlabel=f'T{sensor} [mK]',ylabel='AC² [mV² ADC]');ax.text(.03,.95,f'r = {r:+.3f}\nr | time = {rt:+.3f}',transform=ax.transAxes,va='top',fontsize=7,bbox=dict(facecolor='white',alpha=.8,edgecolor='none'))
figures['temperature']=save(fig,'campaign_AC_power_vs_temperature');derivations['temperature_correlations']=tempstats
fig,axs=grid(3,2,h=4.9);noise_cor={}
for i,(ma,mb) in enumerate([('TM010','TM011'),('TM010','TM012'),('TM011','TM012')]):
 x=col(DCMODE[ma],'AC2_ADC_V2')*1e6;y=col(DCMODE[mb],'AC2_ADC_V2')*1e6
 for j,(xx,yy,label) in enumerate([(x,y,'Measured power'),(residual(x),residual(y),'Linear-time residuals')]):
  ax=axs[i,j];r=pearson(xx,yy);ax.scatter(xx,yy,color=DATA,s=8,alpha=.5);ax.set(title=f'{ma} / {mb} — {label}; r={r:+.4f}',xlabel=ma+' AC² [mV² ADC]',ylabel=mb+' AC² [mV² ADC]');noise_cor[ma+'_'+mb+'_'+label]=r
figures['mode_correlations']=save(fig,'campaign_between_mode_correlations');derivations['between_mode_correlations']=noise_cor
# Verify exact filter coordinates from the already saved product and source definition.
track(REPO/'examples/analyze_iq_filtered_bands.py');track(REPO/'examples/analyze_midas_iq_noise.py');track(REPO/'reporting/iq_noise_summary_v12/pilot.py');track(REPO/'examples/report_noise_v2.py')
offsets=data['filtered_bands/config/offsets_hz'][:];centers=data['filtered_bands/config/centers_hz'][:];width=float(data['filtered_bands/config/width_hz'][()]);assert np.all(centers==0) and width==50000
fif={mo:short['metrics'][mo]['final_IF_hz'] for mo in MODES};enbw=float(data['filtered_bands/modes/TM010/band_04/fir_enbw_two_sided_hz'][()])
fig,axs=grid(1,3,h=2.5)
for i,mo in enumerate(MODES):
 ax=axs[0,i]
 for off in offsets:
  ax.plot(np.array([off-width/2,off+width/2])/1e6,[0,0],color=DATA,lw=5,solid_capstyle='butt');ax.plot(off/1e6,0,'o',color=DATA,ms=3)
 ax.axvline(fif[mo]/1e6,color=NAVY,ls='--',label='Nominal cavity resonance');ax.set(title=mo+' — final complex IF',xlim=(-1.12,1.38),ylim=(-.4,.4),xlabel='Signed complex IF [MHz]',yticks=[]);ax.legend(loc='upper left',fontsize=6)
figures['bandmap']=save(fig,'campaign_band_coordinates')
# Restore absolute per-band power from saved relative RMS table using only run680 saved baseline.
# This preserves both normalization and the correct square when forming power ratios.
band_power={};baseline={};reconstruction_checks={}
for mi,mo in enumerate(MODES):
 matrix=[];b0=[]
 for bi,off in enumerate(offsets):
  b=data[f'filtered_bands/modes/{mo}/band_{bi:02d}'];assert float(b['center_hz'][()])==off
  e=b['events'];p0=float(np.average(e['rms_v'][:]**2,weights=e['n'][:]))*.16
  rr=sorted([r for r in bands if r['mode']==mo and float(r['offset_hz'])==off],key=lambda r:int(r['run']));assert [int(r['run']) for r in rr]==runids.tolist()
  factor=1+col(rr,'change_pct')/100;assert np.all(factor>0);matrix.append(p0*factor**2);b0.append(p0)
 P=np.array(matrix).T;band_power[mo]=P;baseline[mo]=b0;cr=CROWS[mo]
 assert np.allclose(P[:,4],col(cr,'central_squared_v2')*.16,rtol=1e-10,atol=0)
 assert np.allclose(P[:,np.arange(9)!=4].mean(axis=1),col(cr,'side_squared_v2')*.16,rtol=1e-10,atol=0)
 reconstruction_checks[mo]={'central_agrees_with_existing_table':True,'side_average_agrees_with_existing_table':True}
fig,axs=grid(2,3);ratio_summary={}
for i,mo in enumerate(MODES):
 P=band_power[mo];cs=P[:,4]/P[:,np.arange(9)!=4].mean(axis=1);ax=axs[0,i];ax.plot(time,cs,color=DATA);ax.set(title=mo+' — central / mean side power',xlabel='Elapsed acquisition clock time [h]',ylabel='P(0) / mean[P(side)]');ratio_summary[mo]={'central_over_mean_side_first':float(cs[0]),'central_over_mean_side_last':float(cs[-1]),'symmetric':{}}
 ax=axs[1,i]
 for oi,(off,ls,mk) in enumerate(zip([100000,250000,500000,1000000],['-','--',':','-.'],['o','s','^','d'])):
  ip=np.flatnonzero(offsets==off)[0];im=np.flatnonzero(offsets==-off)[0];ratio=P[:,ip]/P[:,im];ax.plot(time,ratio,color=DATA,ls=ls,marker=mk,markevery=35,ms=2.5,label=f'±{off/1000:g} kHz');ratio_summary[mo]['symmetric'][str(off)]={'first':float(ratio[0]),'last':float(ratio[-1]),'min':float(ratio.min()),'max':float(ratio.max())}
 ax.set(title=mo+' — symmetric-side power ratios',xlabel='Elapsed acquisition clock time [h]',ylabel='P(+offset) / P(−offset)');ax.legend(ncol=2,fontsize=5.7)
figures['ratios']=save(fig,'campaign_central_and_symmetric_ratios');derivations['band_ratios']=ratio_summary;derivations['band_power_reconstruction_checks']=reconstruction_checks
fig,axs=grid(2,3)
common=col(CROWS['TM010'],'common_side_amplitude_ratio')
for i,mo in enumerate(MODES):
 rr=CROWS[mo];P=band_power[mo];side=P[:,np.arange(9)!=4].mean(axis=1);central=P[:,4];sf=np.sqrt(side/side[0]);cf=np.sqrt(central/central[0]);assert np.allclose(col(rr,'common_side_amplitude_ratio'),common)
 ax=axs[0,i];ax.plot(time,sf,color=DATA,label='Side RMS / baseline');ax.plot(time,common,color=DATA,ls='--',label='Common trend');ax.set(title=mo+' — shared level variation',xlabel='Elapsed acquisition clock time [h]',ylabel='Amplitude ratio');ax.legend(fontsize=6)
 ax=axs[1,i];ax.plot(time,100*(cf/common-1),color=DATA,label='Central/common');ax.plot(time,100*(sf/common-1),color=DATA,ls='--',label='Side/common');ax.set(title=mo+' — residual spectral evolution',xlabel='Elapsed acquisition clock time [h]',ylabel='Residual amplitude change [%]');ax.legend(fontsize=6)
 assert np.allclose(cf/common,col(rr,'central_relative_after_common'),rtol=1e-10);assert np.allclose(sf/common,col(rr,'side_relative_after_common'),rtol=1e-10)
figures['global_shape']=save(fig,'campaign_global_level_and_shape')
RUNROWS={mo:sorted([r for r in runs if r['mode']==mo],key=lambda x:x['run']) for mo in MODES};shape_stats={}
fig,axs=grid(1,3,h=2.7)
for i,mo in enumerate(MODES):
 rr=RUNROWS[mo];cv=col(rr,'amplitude_noise_rms_v')/col(rr,'mean_amplitude_v');ax=axs[0,i];ax.plot(time,cv,color=DATA);ax.set(title=mo+' — normalized-shape proxy',xlabel='Elapsed acquisition clock time [h]',ylabel='std(A) / mean(A)');shape_stats[mo]={'CV_min':float(cv.min()),'CV_max':float(cv.max()),'CV_span_percent':float(100*(cv.max()/cv.min()-1))}
figures['shape']=save(fig,'campaign_normalized_shape_proxy');derivations['normalized_shape_proxy']=shape_stats
fig,axs=grid(3,3,h=5.1)
for i,k in enumerate([3,5,7]):
 for j,mo in enumerate(MODES):
  rr=RUNROWS[mo];mu=col(rr,'mean_amplitude_v');std=col(rr,'amplitude_noise_rms_v');s2=(mu**2+std**2)/2;ax=axs[i,j]
  for source,ls in [('local','-'),('reference','--')]:
   rate=col(rr,f'{source}_{k}sigma_fraction');th=col(rr,f'{source}_{k}sigma_threshold_v');pred=np.exp(-th**2/(2*s2));ax.semilogy(time,rate,color=DATA,ls=ls,label='Data '+source);ax.semilogy(time,pred,color=NAVY,ls=ls,alpha=.75,label='Rayleigh '+source)
  ax.set(title=f'{mo} — k={k}',xlabel='Elapsed acquisition clock time [h]',ylabel='P(A > threshold)');ax.legend(ncol=2,fontsize=4.9)
figures['probabilities']=save(fig,'campaign_local_fixed_probabilities')
D=sd.Deck();provenance=[]
def register(s,section,scope,sources,estimator,run_ids):
 s['footer']='FLASH | v45 | PART '+section+' | '+('RUN 680 + STEP 6' if section=='II' else 'LONG-TERM DATA');provenance.append({'slide':14+len(D.slides),'title':s['title'],'section':section,'statistical_population':scope,'run_ids':run_ids,'source_products':sources,'estimator':estimator,'toy_comparison':section=='II'});return s

def page(title,sub,scope,sources,notes=''):
 section='II' if len(D.slides)<10 else 'III'
 s=D.new(' ',sub,'Scope: '+scope+' | Sources: '+sources,notes);s['title']=title;s['items'][1]['text']=title;s['items'][1]['size']=25
 return register(s,section,scope,sources,notes,[680] if section=='II' else runids.tolist())

def reuse(index,title,section,scope,extra_notes='',caption_override=None):
 s=copy.deepcopy(prior[index-1]);D.slides.append(s);s['title']=title;s['notes']+='\nV45: '+extra_notes
 if caption_override:
  for item in s['items']:
   if item['kind']=='text' and abs(item['y']-6.37)<.001:item['text']=sd.wrap(caption_override,item['w'],11);item['size']=11
 s['source']='Scope: '+scope+' | '+s['source']
 return register(s,section,scope,'v44 slide '+str(index)+'; '+s['source'],s['notes'],[680] if section=='II' else runids.tolist())

def txt(s,x,y,w,ht,t,size=15,bold=False,color=sd.INK):D.text(s,x,y,w,ht,t,size,bold,color)
def table(s,heads,rr,y=2,widths=None,size=12,rowh=.46,headh=.65):
 widths=widths or [12/len(heads)]*len(heads)
 for i,row in enumerate([heads]+rr):
  yy=y if i==0 else y+headh+(i-1)*rowh;x=.65
  for val,w in zip(row,widths):txt(s,x,yy,w-.08,headh if i==0 else rowh,str(val),size,i==0);x+=w

def image(s,key,y=1.75,ht=4.4):D.image(s,.4,y,12.55,ht,figures[key])
def caption(s,t,size=11.5):txt(s,.65,6.37,12.05,.44,t,size)
# II — 10 pages, every scientific measurement belongs to run680 only.
s=page('Run 680 — conditions and statistical scope','Part II | one experimental run and its corresponding step 6 reference.','Run680 only:209.7152s; matched PSD/g1 window1.048576s.','run680 v2 summary; measured run680 sensor medians and LO records; approved nominal cavity inputs.',
 'Run680 contains1000SPEC and1,048,576,000 complex samples/mode. Physical ADC±2V,16bit,5MS/s,61.036uV/count. Temperature values are the observed run medians, not a fitted noise temperature. Cavity f0,Q0,kappa are adopted nominal characterization parameters; no new resonance tracking is inferred. ReceiverTn=3.955K is the fixed reference input, not a new in-situ measurement.')
D.bullets(s,.75,1.85,11.7,['Full run: 209.7152 s, 1000 SPEC, 1,048,576,000 complex samples per mode.','ADC: 5 MS/s, 16 bit, ±2 V. z = I − iQhardware = I + iQeff; sample step 200 ns.','Observed median temperatures: T15 = 40.422 mK; T16 = 37.580 mK; T17 = 46.062 mK.','Full-run distributions and moments are separate from the 1.048576 s selected PSD/correlation window.'],size=16,gap=.15)
rr=[]
for mo in MODES:
 p=short['metrics'][mo];rr.append([mo,f"{p['f0_hz']/1e9:.6f}",f"{p['q0']:,.0f}",f"{p['kappa1']:.6g} / {p['kappa2']:.3g}",f"{p['final_IF_hz']/1e6:.3f}"])
table(s,['Mode','Nominal f0 [GHz]','Q0','kappa1 / kappa2','Final IF reference [MHz]'],rr,y=4.25,widths=[1.1,2.75,2.05,3.1,3.0],size=11.5,rowh=.36,headh=.55)
caption(s,'Primary LO 8.735869 GHz; secondary LOs 43.723 / 104.057 MHz. Receiver Tn = 3.955 K is the unchanged toy input.')
s=reuse(24,'Absolute normalization and noise amplitude','II','Complete run680 and corresponding209.7152s reference.',
 'No campaign distribution or campaign fit is used. Same PartI RF103.4dB,kzscience=.01kzcal; cal±5V/science±2V. Raw RMS,AC RMS and Rayleigh sigma stay distinct.')
s['subtitle']='Run 680 and step 6 | physical calibration retained; raw RMS, AC RMS and sigma shown separately.'
for it in s['items']:
 if it['kind']=='text' and it['y']==1.12:it['text']=sd.wrap(s['subtitle'],it['w'],13);it['size']=13
txt(s,.65,1.72,12,.25,'VADC(f) = 10^(103.4/20) × 0.01 × kz,cal(f) × Vphysical(f); science ±2 V, calibration ±5 V.',12,True)
# Add a visible compact mapping without repeating the PartI calibration lecture.
# The original table/bullets are retained, with equation in notes and source for precise provenance.
s['notes']+=' VADC=10^(103.4/20) * 0.01 * kz_cal * Vphysical; ADC science4/65535V/count, calibration10/65535V/count.'
s=page('Quadrature distributions and IQ constellations','Full run 680 versus full-run step 6 | common physical axes and common density scale.','Complete209.7152s populations;1,048,576,000samples per mode/population.','Saved full_iq_data_MODE.npz and current reference toy IQ histograms.',
 'Quadrature densities are projections of existing512×512 full-run IQ counts; no new fit or centered approximation. Common log-count density limits and physical ADC axes are used. One dataTM012 sample lies outside the original IQ rectangle. Empirical pseudo-covariance/imbalance are described, not corrected. No260-run histogram is used.')
image(s,'iq',ht=4.3);caption(s,'Raw IQ is retained. Filled distributions: data teal, toy purple; I solid and Qeff dashed in the marginal-density panels.')
s=reuse(25,'Amplitude distributions and Rayleigh CCDF','II','Full run680 and corresponding209.7152s reference.',
 'Run680 only. Absolute histograms retain common ADC axes. CCDF uses each saved fitted sigma only to expose shape; no amplitude correction. Tail counts move to their own single-run page.',
 'Above: absolute raw |z| in mV ADC. Below: shape-only binned CCDF using each saved sigma. The absolute mismatch is retained.')
s=page('Phase and phase increments','Complete run 680 | absolute phase compared with toy; increments remain explicitly data-only.','Complete209.7152s run680 and full-run reference marginal phase.','v2 arrays/global_MODE_phase and delta_1/10/100; current toy phase_counts.',
 'Both marginal phases use absolute arg(I+iQeff), not relative-to-first-valid-sample histograms. Zero-amplitude endpoints excluded. Data increments are from continuous v2 products at0.2/2/20us. Comparable full-run toy increment histograms are unavailable; no false comparison is inferred or new replay simulation performed.')
image(s,'phase');caption(s,'Comparable full-run toy increment histograms are unavailable. The lower row shows data only; no campaign-pooled angle distribution enters this section.')
s=page('Amplitude tails and counts above threshold','Full-run counts at the existing fitted-Rayleigh thresholds; correlated samples are not independent events.','Run680 and corresponding toy,209.7152s;N=1,048,576,000each.','Existing full_iq_counts data entries; current reference metrics.samples_above_3_5_7; saved Rayleigh sigma.',
 'Tk=sigma*[sqrt(pi/2)+k sqrt((4−pi)/2)] for each population saved Rayleigh scale. This differs from empirical mean(A)+k std(A) per-run thresholds used later for long-term stability. No new event counts or fits. Raw amplitudes are not silently centered. Expectation N exp(−Tk²/(2sigma²)) is marginal, not independent-event significance.')
image(s,'tails',y=1.72,ht=2.55);rr=[]
for mo in MODES:
 a=counts['data_'+mo]['above_3_5_7'];b=metrics['results'][mo]['samples_above_3_5_7'];thresholdD=radii[-1]*amps[mo]['data']['sigma_v']*1000;thresholdT=radii[-1]*metrics['results'][mo]['sigma_fit_v']*1000
 rr.append([mo,*[f'{int(x):,} / {int(y):,}' for x,y in zip(a,b)],f'{thresholdD:.3f} / {thresholdT:.3f}'])
table(s,['Mode','Above k=3\ndata / toy','Above k=5\ndata / toy','Above k=7\ndata / toy','k=7 threshold\ndata / toy [mV]'],rr,y=4.35,widths=[.95,3.0,2.5,2.2,3.25],size=11,rowh=.38,headh=.62)
caption(s,'Rayleigh probabilities P3=0.0056275, P5=3.51494e−5, P7=3.94382e−8; expected k=7 count ≈41.35 in each full-run population.',11)
reuse(27,'Power spectral density','II','Selected1.048576s windows in run680 and reference;244.14Hz display bins.','One estimator and identical signed complex-frequency axes; no full-run or campaign PSD claim.')
reuse(28,'Complex autocorrelation','II','Selected1.048576s windows in run680 and reference;200ns lag spacing.','Archived complex g1 preserved. Re±0.08 and Im±0.02 positive-lag zooms; zero lag retained on common full scale.')
reuse(29,'Characteristic times','II','Selected1.048576s run680/reference windows;existing0.3–4us upper-maxima fits.','No new fit. Unresolved TM010 toy fit remains unresolved; cavity pole, fitted decay and stationarity times remain distinct.')
reuse(30,'Run 680 — agreements and discrepancies','II','Run680 only:full-run amplitudes/IQ;selected1.048576s PSD/g1/times.','This scorecard is a single-run reference comparison. It does not summarize a260-run toy comparison.')
assert len(D.slides)==10
# III — 10 pages, no constant-condition toy comparison.
s=reuse(16,'Campaign temperatures and absolute noise levels','III','All260runs680–939;one full-run summary per mode/run.','Only measured data and sensors; no fixed-condition toy comparison. Coverage15.1461h acquired,272.62976billion complex samples/mode.')
s['subtitle']='Part III | 260 runs, 680–939; 15.1461 acquired hours; measured levels and temperatures.'
for it in s['items']:
 if it['kind']=='text' and it['y']==1.12:it['text']=sd.wrap(s['subtitle'],it['w'],12);it['size']=12
s=page('AC noise power versus measured temperatures','260 matched run summaries | direct scatter and explicit control for common clock drift.','All260runs, each run contributes one median temperature and one AC² per mode.','Corrected longterm.csv; existing trend_diagnostics.csv, ac_squared_v2 rows.',
 'Raw Pearson r and r after removing intercept+linear acquisition time are reproduced from the saved table and verified. They are descriptive associations without causal attribution or independent-sample p-values. Residual association does not exclude nonlinear drift, time-dependent gain or other covarying conditions. No physical temperature-response fit. Units AC²=mV²ADC, not RF watts.')
image(s,'temperature',ht=4.3);caption(s,'r | time removes a linear clock trend from both variables. A residual association is not a demonstrated thermal transfer law; all points are full-run summaries.')
s=page('Correlations between the three noise levels','260 matched runs | compare raw power covariance with linear-time residuals.','All260runs for each of the three mode pairs.','Corrected full-band AC² from longterm.csv; Pearson correlation computed directly from tables.',
 'Left:raw ADC squared-voltage levels. Right:both series projected off intercept+linear standardized acquisition time. No physical response fit, gain correction or causal direction. The residual association can include shared nonlinear temporal structure or other common conditions. No toy curves.')
image(s,'mode_correlations');caption(s,'The same 260 matched runs enter every pair. Common time drift and residual co-variation are reported separately, without assigning a cause.')
s=page('Frequency-band coordinates and effective width','Electronic DC is the reference of the saved filters; nominal resonance is at a different final IF.','Common filter configuration of the260validated v2 runs;reference frequencies are nominal, not tracked per run.','Saved filtered_bands/config and run680 band metadata; filter source; fixed cavity/LO coordinate references.',
 'Actual filter centers are centers_hz(0)+offset. Offsets0,±100,±250,±500,±1000kHz; nominal full width50kHz, half width25kHz; Kaiser8.6 FIR2001taps, decimation20, outputdt4us; stored ENBW47428.8068Hz. These are not brick-wall filters. delta_f=fband−fIF,cavity. Positive1MHz band stops nominally1.025MHz, below all nominal1.248–1.256MHz cavity centers. No frequency tracking or resonance-centered band assumption is made.')
image(s,'bandmap',y=1.7,ht=2.25)
rr=[[mo,f'{fif[mo]/1000:.3f}',f'{-fif[mo]/1000:+.3f}',f'{(1e6-fif[mo])/1000:+.3f}'] for mo in MODES]
table(s,['Mode','Nominal resonance IF [kHz]','DC-band detuning [kHz]','+1000 kHz band detuning [kHz]'],rr,y=4,widths=[1.0,3.6,3.6,3.8],size=11.5,rowh=.34,headh=.6)
txt(s,.7,5.73,11.9,.46,'Band centers: 0, ±100, ±250, ±500, ±1000 kHz. Each nominal interval is center ±25 kHz; detuning = band center − resonance IF.',12)
caption(s,f'ENBW = {enbw/1000:.6f} kHz. “Central” means DC-centered, not resonance-centered; all nine nominal bands lie below resonance.',11.5)
s=reuse(18,'Nine-band noise evolution across the campaign','III','All260runs per mode/band;27run-level curves.','Centers refer to signed final IF around0, not cavity-centered offsets. Before/after DC-removal comparison from12-run pilot is excluded from this full-campaign page.',
 'RMS change relative to run 680 is shown separately for each mode–band pair. Filter centers and widths are defined on the preceding page.')
s['subtitle']='260 runs | nine electronic-frequency bands per mode; each curve is relative to its own run 680 baseline.'
for it in s['items']:
 if it['kind']=='text' and it['y']==1.12:it['text']=sd.wrap(s['subtitle'],it['w'],12);it['size']=12
# Remove the historical12-run pilot assertion from notes/source: not part of this new figure.
s['notes']='Full campaign260runs per curve. Reused nine-band figure only; no pilot DC-removal diagnostic is used on this page. Centers0,±100,±250,±500,±1000kHz; nominal50kHz width. Relative RMS only; no independent gain calibration.'
s['source']='Scope: all260runs680–939 | band_rms_relative_to_run680.csv; original v2 nine-band relative RMS estimator.'
s=page('Central-to-side and symmetric-sideband ratios','260 runs | absolute power ratios preserve fixed instrumental asymmetries.','All260runs;full-run filtered mean-square voltage for each band.','Saved per-band relative RMS table anchored to run680 filtered-event moments; independent central/side table cross-check.',
 'Pband(run)=Pband(680)*(1+change_pct/100)^2. Baseline is sample-weighted mean of saved event rms_v², corrected by.16 to physical ADC V². Central/side=P0/arithmetic mean of all eight side powers. Symmetry ratios=P(+d)/P(−d),d100/250/500/1000kHz. Baseline asymmetry is retained:ratios are not forced to1. Reconstructed central power and mean side power are verified against the complete260-run table. No raw reads or extra noise model.')
image(s,'ratios');caption(s,'Power ratios use squared RMS factors. Central/side averages all eight sidebands; symmetric ratios retain their measured run-680 baseline.')
s=page('Global level changes and spectral-shape evolution','260 runs | a descriptive common trend separates shared level drift from residual ratios.','All260matched run summaries;each target mode contributes to the common trend.','Existing common_side_amplitude_ratio and central/side_relative_after_common; verified from saved band powers.',
 'Common amplitude C(run)=exp(median_m log(sqrt(Pside,m(run)/Pside,m(680)))). Top shows observed side amplitudes and C;bottom divides central/side RMS ratios by C. This is a descriptive normalization diagnostic, not an independently measured gain or causal calibration. Target mode is included, so residual suppression is not independent validation of spectral stability. Physical ADC levels and PartII normalization are not modified.')
image(s,'global_shape');caption(s,'Common trend = median log sideband-amplitude ratio across modes. It includes each target mode; residual changes describe shape, not a calibrated gain correction.')
s=reuse(17,'Long-term DC evolution and phase','III','All260full-run complex means and AC powers.','Use only measured long-term DC/AC moments. No selected-run diagnostic or toy covariance appears.')
s=page('Stability of normalized amplitude shape','260 runs | coefficient of variation is an available shape proxy, not a full distribution test.','All260original complete-run amplitude moment summaries per mode.','runs.csv:mean_amplitude_v and amplitude_noise_rms_v;dimensionless ratios invariant under ADC-scale correction.',
 'CV=std(|z|)/mean(|z|). No pooling of raw histograms substitutes for a time-resolved normalized-distribution test. StableCV is compatible with changing absolute scale and does not prove stationary full distribution, Gaussian IQ or independent samples. Per-run standardized CDF distances are not supplied by these long-term tables and are not claimed. This is not a comparison with a fixed-condition physical toy.')
image(s,'shape',y=1.8,ht=2.65)
rr=[[mo,f"{shape_stats[mo]['CV_min']:.7f}",f"{shape_stats[mo]['CV_max']:.7f}",f"{shape_stats[mo]['CV_span_percent']:.5f}%"] for mo in MODES]
table(s,['Mode','Minimum CV','Maximum CV','max/min CV span'],rr,y=4.65,widths=[1.2,3.3,3.3,4.2],size=12,rowh=.34,headh=.52)
caption(s,'Stable normalized moments coexist with absolute level drift. Full time-resolved standardized histograms are not established by this proxy.',11.5)
s=page('Local and fixed-threshold probability stability','260 runs | empirical threshold conventions and moment-based Rayleigh expectations.','All260runs;sample fractions at k=3,5,7;fixed reference is the saved100SPEC run680 pilot.','runs.csv threshold values/fractions and amplitude moments;no new counts or fit.',
 'LocalT=empirical meanA+k stdA per run;fixedT=pilot meanA+k pilot stdA. This convention differs from the fitted-Rayleigh thresholds in PartII. Navy curves are exp(−T²/(2srun²)),srun²=(meanA²+stdA²)/2,using exactly each existing threshold. They are descriptive in-sample moment expectations, not a physical fixed-temperature toy or independent-trial significance. Reference pilot overlaps campaign,so no statistical independence claim. Rates count samples,not independent transient events.')
image(s,'probabilities',ht=4.3);caption(s,'Teal: observed fractions. Navy: moment-based Rayleigh expectations. Solid: local threshold; dashed: fixed pilot threshold. Shared drift does not establish a cause.',11)
assert len(D.slides)==20
# Reused slides keep scientific content but receive the new title, scope, section and numbering.
for s in D.slides:
 for it in s['items']:
  if it['kind']=='text' and it['y']==.38:
   it['size']=25
   while len(sd.wrap(s['title'],it['w']*.87,it['size']).splitlines())>1:it['size']-=1
   it['text']=s['title']
  if it['kind']=='image':
   src=Path(it['path']);track(src);dst=A/src.name
   if src!=dst:shutil.copy2(src,dst)
   it['path']=str(dst)
# Full per-band interval/detuning provenance, external to Git.
coords={mo:[{'center_IF_hz':float(off),'nominal_lower_IF_hz':float(off-width/2),'nominal_upper_IF_hz':float(off+width/2),'nominal_center_detuning_hz':float(off-fif[mo]),'nominal_lower_detuning_hz':float(off-width/2-fif[mo]),'nominal_upper_detuning_hz':float(off+width/2-fif[mo])} for off in offsets] for mo in MODES}
derivations['band_coordinates']={'configuration_centers_hz':centers.tolist(),'nominal_width_hz':width,'ENBW_hz':enbw,'cavity_nominal_final_IF_hz':fif,'intervals':coords,'reference_limit':'Nominal cavity/LO coordinates; no per-run resonance tracking available.'}
(OUT/'derived_from_existing_tables.json').write_text(json.dumps(derivations,indent=2)+'\n')
# Exact source/figure/population provenance for every appended page.
for s,p in zip(D.slides,provenance):
 p['title']=s['title'];p['source_products']=s['source'];p['estimator']=s['notes'];p['figures']=[it['path'] for it in s['items'] if it['kind']=='image']
 if len(sd.wrap(s['source'],11.8,7.5).splitlines())>1:
  s['notes']+='\nFull source citation: '+s['source'];s['source']='Scope: all260runs | Shared saved filter configuration, run680 band metadata and filter source; nominal resonance/LO coordinates.'
TAIL=OUT/'parts_II_III';sd.export(D,TAIL,'v45_parts_II_III','17 November 2026',page_offset=14,total_pages=TOTAL)
subprocess.run(['pdfunite',str(B/'iq_noise_summary_v43_partI.pdf'),str(TAIL/'iq_noise_summary_v45_parts_II_III.pdf'),str(OUT/'iq_noise_summary_v45.pdf')],check=True)
base=Presentation(B/'iq_noise_summary_v43_partI.pptx');extra=Presentation(TAIL/'iq_noise_summary_v45_parts_II_III.pptx');RNS='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
for src in extra.slides:
 dst=base.slides.add_slide(base.slide_layouts[6]);dst.background.fill.solid();dst.background.fill.fore_color.rgb=RGBColor.from_string(sd.BG.lstrip('#'))
 for sh in src.shapes:
  el=copy.deepcopy(sh.element)
  for node in el.iter():
   for attr in [RNS+'embed',RNS+'link']:
    old=node.get(attr)
    if old:
     rel=src.part.rels[old]
     if rel.reltype.endswith('/image'):_,new=dst.part.get_or_add_image_part(io.BytesIO(rel.target_part.blob));node.set(attr,new)
     else:raise ValueError('Unexpected shape relationship '+rel.reltype)
  dst.shapes._spTree.insert_element_before(el,'p:extLst')
 dst.notes_slide.notes_text_frame.text=src.notes_slide.notes_text_frame.text
base.save(OUT/'iq_noise_summary_v45.pptx')
with zipfile.ZipFile(B/'iq_noise_summary_v43_partI.pptx') as old,zipfile.ZipFile(OUT/'iq_noise_summary_v45.pptx') as new:
 for name in old.namelist():
  if name.startswith(('ppt/slides/','ppt/notesSlides/','ppt/media/')):assert old.read(name)==new.read(name),name
for i in range(1,15):shutil.copy2(B/f'slide_{i:02d}.png',OUT/f'slide_{i:02d}.png')
for i in range(1,21):shutil.copy2(TAIL/f'slide_{i:02d}.png',OUT/f'slide_{i+14:02d}.png')
from PIL import Image
sheet=Image.new('RGB',(640*3,360*12),'white')
for i in range(TOTAL):
 with Image.open(OUT/f'slide_{i+1:02d}.png') as im:sheet.paste(im.resize((640,360)),((i%3)*640,(i//3)*360))
sheet.save(OUT/'contact_sheet.png');(OUT/'slide_model.json').write_text(json.dumps(original+D.slides,indent=2,ensure_ascii=False)+'\n');(OUT/'slides_en.md').write_text((B/'slides_en.md').read_text()+'\n\n'+(TAIL/'slides_en.md').read_text())
assert all(sha(p)==v for p,v in inputs.items()),'An input changed during export'
validation={'slides':TOTAL,'PartI':14,'PartII':10,'PartIII':10,'PartIV':0,'PartI_PPTX_parts_identical':True,'input_sha256':inputs,'new_raw_reads':False,'new_simulations':False,'new_physical_fits':False,'normalization_unchanged':True,'statistical_controls':'Pearson coefficients; projection off intercept+linear acquisition time, verified against existing temperature coefficients. No causal claim.','band_power_checks':reconstruction_checks}
(OUT/'validation.json').write_text(json.dumps(validation,indent=2)+'\n');(OUT/'slide_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n');data.close();toy.close();print('v45 complete:14approved +10single-run +10long-term =34slides;no PartIV.')
