"""v47: frozen v45 slides 1–24, separate resonance comparison, revised campaign.
Only existing products and explicitly documented analytic/table calculations.
"""
from pathlib import Path
import copy, csv, hashlib, io, json, shutil, subprocess, sys, tempfile, zipfile
import h5py
import numpy as np
from scipy.stats import spearmanr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import Normalize
from PIL import Image
sys.path.insert(0,'/tmp/v18-python-deps')
from pptx import Presentation
from pptx.dml.color import RGBColor
REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'reporting'))
import slide_deck as sd
W=REPO.parent/'analysis-work/Run2'
OLD=W/'reports/iq_noise_summary_v45'
OUT=W/'reports/iq_noise_summary_v47'
CALC=W/'diagnostics/resonance_campaign_primary_v47_20261117'
PRIMARY=W/'diagnostics/v47_primary_audit_20261117'
PILOT=W/'diagnostics/resonance_bank_pilot_v1_20261117'
A=OUT/'assets'; A.mkdir(parents=True,exist_ok=True)
MODES=['TM010','TM011','TM012']; DATA='#007F86'; TOY='#7657A6'; THERMAL='#43a1ed'; ELECTRONIC='#ed812a'; NAVY='#263952'
OFF=np.array([-500,-250,-100,0,100,250,500]); EO=np.array([-1000,-500,-250,-100,0,100,250,500,1000]); LS=['-','--',':','-.',(0,(6,2)),(0,(2,2)),(0,(1,1))]
ledger={}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def track(p): p=Path(p); ledger[str(p)]=sha(p); return p
def js(p): return json.loads(track(p).read_text())
def rows(p):
 with open(track(p)) as f: return list(csv.DictReader(f))
track(__file__);track(REPO/'reporting/slide_deck.py')
prior=js(OLD/'slide_model.json'); previous_provenance=js(OLD/'slide_provenance.json')
result=js(CALC/'results.json'); short=js(W/'simulation/presentation_steps1_6_v43/metrics.json')
assert all(v['qualified_descriptive_use'] for v in result['validation'].values()), 'Documented PSD proxy decision required'
for name in ['iq_noise_summary_v45.pdf','iq_noise_summary_v45.pptx']: track(OLD/name)
dcr=rows(PRIMARY/'fullband_v2.csv')
runs=rows(PRIMARY/'raw_statistics_v2.csv')
DCR={m:sorted([r for r in dcr if r['mode']==m],key=lambda r:int(r['run'])) for m in MODES}
RR={m:sorted([r for r in runs if r['mode']==m],key=lambda r:int(r['run'].replace('run',''))) for m in MODES}
col=lambda rr,key:np.array([float(r[key]) for r in rr])
valid=np.isin(np.arange(680,940),result['coordinate_audit']['included_runs'])
clock=col(DCR['TM010'],'time_unix'); time=(clock-clock[0])/3600
norm=Normalize(time.min(),time.max()); cmap='viridis'
TEMP_ROWS=rows(CALC/'temperatures_by_run.csv')
NAMES={15:'RF cavity — Dale1.5K (T15)',16:'Mixing Chamber\nCMN143 (T16)',17:'Mixing Chamber\nCMN130 (T17)'}
SHORT={15:'RF cavity/T15',16:'MC-CMN143/T16',17:'MC-CMN130/T17'}
X=np.column_stack([np.ones(260),(time-time.mean())/time.std()]); residual=lambda x:x-X@np.linalg.lstsq(X,x,rcond=None)[0]
pearson=lambda x,y:float(np.corrcoef(x,y)[0,1]); spearman=lambda x,y:float(spearmanr(x,y).statistic)
plt.rcParams.update({'font.size':9,'axes.titlesize':10,'axes.labelsize':9,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':6.3,'axes.grid':True,'grid.alpha':.18,'lines.linewidth':.9})
figures={}; derived={'temperature':{},'between_modes':{},'band_stability':{},'sensor_positions':result['temperature_sensor_inventory']}
def grid(nr=2,nc=3,h=4.5):
 fig,axs=plt.subplots(nr,nc,figsize=(12.6,h),squeeze=False)
 fig.subplots_adjust(left=.065,right=.965,bottom=.14,top=.93,hspace=.65,wspace=.4)
 return fig,axs
def save(fig,name):
 p=A/(name+'.png');fig.savefig(p,dpi=200,facecolor='white');fig.savefig(p.with_suffix('.pdf'));plt.close(fig);figures[name]=p;return p
def timecolor(fig,axs):
 cb=fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=cmap),ax=axs.ravel().tolist(),fraction=.014,pad=.025);cb.set_label('Campaign clock [h]',fontsize=8);cb.ax.tick_params(labelsize=7)
def scatter(ax,x,y,title,xlabel,ylabel):
 keep=np.isfinite(x)&np.isfinite(y)
 ax.scatter(x[keep],y[keep],c=time[keep],cmap=cmap,norm=norm,s=8,alpha=.8,rasterized=True)
 ax.set(title=title,xlabel=xlabel,ylabel=ylabel)
 ax.text(.03,.97,f'Pearson r={pearson(x[keep],y[keep]):+.3f}\nSpearman ρ={spearman(x[keep],y[keep]):+.3f}',transform=ax.transAxes,va='top',fontsize=7,bbox={'facecolor':'white','edgecolor':'none','alpha':.85})

track(CALC/'expectations_and_campaign.h5');track(PILOT/'run00680_resonance.h5')
h=h5py.File(CALC/'expectations_and_campaign.h5','r');pilot=h5py.File(PILOT/'run00680_resonance.h5','r')
P={m:np.where(valid[:,None],h[m+'/power_ADC_V2'][:],np.nan) for m in MODES};EP={m:h[m+'/electronic_power_ADC_V2'][:] for m in MODES}
# Four additional single-run pages. Every other band has its own supplemental panel.
fig,axs=grid()
for i,m in enumerate(MODES):
 r=result['modes'][m];td=np.array(r['data_RMS_ADC_V']);tt=np.array(r['toy_RMS_ADC_V'])
 ax=axs[0,i];ax.plot(OFF,td*1e3,'o-',color=DATA,label='Data');ax.plot(OFF,tt*1e3,'s--',color=TOY,label='Reference total');ax.plot(OFF,np.array(r['electronic_RMS_ADC_V'])*1e3,':',color=ELECTRONIC,label='Electronic');ax.set(title=m,xlabel='Offset from BOR reference [kHz]',ylabel='RMS [mV ADC]');ax.legend()
 ax=axs[1,i];ax.plot(OFF,np.array(r['data_moment_sigma_q_ADC_V'])*1e3,'o-',color=DATA,label='Data moment scale');ax.plot(OFF,np.array(r['toy_sigma_q_ADC_V'])*1e3,'s--',color=TOY,label='Toy σ = RMS/√2');ax.set(title=m,xlabel='Offset [kHz]',ylabel='Quadrature σ [mV ADC]');ax.legend()
save(fig,'run680_resonance_absolute')
fig,axs=grid()
for i,m in enumerate(MODES):
 g=pilot[f'filter_banks/resonance_ROI/modes/{m}/band_03'];e=g['amplitude_edges_V'][:];counts=g['amplitude_counts'][:];s=result['modes'][m]['toy_sigma_q_ADC_V'][3]
 x=np.linspace(0,max(e[-1],5*s),1000);ax=axs[0,i];ax.stairs(np.maximum(counts/counts.sum()/np.diff(e)/1000,1e-15),e*1000,color=DATA,label='Data full run');ax.plot(x*1e3,x/s**2*np.exp(-x*x/(2*s*s))/1000,color=TOY,label='Analytic toy');ax.set(title=m+' central-band amplitude',xlabel='A [mV ADC]',ylabel='Density [mV^-1]',yscale='log',ylim=(1e-7,2));ax.legend()
 ac=np.cumsum(counts[::-1])[::-1]/counts.sum();sigma_data=result['modes'][m]['data_moment_sigma_q_ADC_V'][3];ax=axs[1,i];ccdf_ok=ac>0;ax.plot(e[:-1][ccdf_ok]**2/(2*sigma_data**2),np.log(ac[ccdf_ok]),color=DATA,label='Data: own moment σ');ax.plot([0,18],[0,-18],color=TOY,ls='--',label='Gaussian toy: ln CCDF = −x');ax.set(title=m+' shape-only CCDF',xlabel='A² / (2σ²)',ylabel='ln P(A > threshold)',xlim=(0,18),ylim=(-18,0));ax.legend()
save(fig,'run680_resonance_amplitude_CCDF')
fig,axs=grid(3,3,h=5.05)
for i,m in enumerate(MODES):
 g=pilot[f'filter_banks/resonance_ROI/modes/{m}/band_03'];t=h[f'{m}/analytic_reference/band_03'];freq=g['PSD_frequency_baseband_hz'][:];order=np.argsort(freq);ax=axs[0,i]
 for ff,ps,color,label in [(freq,g['PSD_total_V2_Hz'][:],DATA,'Data full-run Welch'),(t['output_frequency_hz'][:],t['output_Welch_expected_ADC_V2_Hz'][:],TOY,'Toy expected Welch')]:
  oo=np.argsort(ff);ax.plot(ff[oo]/1e3,10*np.log10(np.maximum(ps[oo],1e-30)),color=color,label=label)
 ax.set(title=m+' central PSD — passband zoom',xlabel='Band-relative frequency [kHz]',ylabel='dB V²/Hz ADC',xlim=(-35,35),ylim=(-125,-90));ax.legend(fontsize=5.3)
 lag=g['selected_lag_s'][:]*1e6;gd=g['selected_total_g1'][:];gt=t['g1'][:];sel=lag<=120
 for j,part in [(1,'real'),(2,'imag')]:
  ax=axs[j,i];ax.plot(lag[sel],getattr(gd,part)[sel],'o-',ms=2,color=DATA,label='Data first 5 SPEC');ax.plot(lag[sel],getattr(gt,part)[sel],'s--',mfc='white',ms=2,color=TOY,label='Analytic toy');ax.set(xlabel='Lag [µs]; markers every 4 µs',ylabel=('Re' if j==1 else 'Im')+' g1',xlim=(0,120),ylim=(-.4,1.04) if j==1 else (-.02,.02));ax.legend(fontsize=5.3)
save(fig,'run680_resonance_PSD_g1')
fig,axs=grid()
for i,m in enumerate(MODES):
 r=result['modes'][m];ax=axs[0,i]
 for j,(pop,c) in enumerate([('data',DATA),('toy',TOY)]):ax.plot(j,r['central_over_mean_six'][pop],'o',ms=7,color=c,label=pop)
 ax.set(title=m+' central / mean six sides',xticks=[0,1],xticklabels=['Data','Toy'],ylabel='Power ratio',xlim=(-.5,1.5));ax.axhline(1,color=NAVY,ls=':');ax.legend()
 ax=axs[1,i]
 for pop,c,mk in [('data',DATA,'o'),('toy',TOY,'s')]:ax.plot([100,250,500],[r['symmetric_ratios'][pop][str(d)] for d in [100000,250000,500000]],mk+'-',color=c,label=pop)
 ax.axhline(1,color=NAVY,ls=':');ax.set(title=m+' symmetric power ratios',xlabel='Offset magnitude [kHz]',ylabel='P(+d) / P(−d)',xticks=[100,250,500]);ax.legend()
save(fig,'run680_resonance_ratios')
# Detailed all-band comparison stays separate from the main presentation.
with PdfPages(OUT/'run680_resonance_comparison_supplement.pdf') as pdf:
 for m in MODES:
  fig,axs=plt.subplots(7,3,figsize=(12.6,15));fig.subplots_adjust(left=.07,right=.98,bottom=.05,top=.95,hspace=.8,wspace=.4)
  for bi,off in enumerate(OFF):
   g=pilot[f'filter_banks/resonance_ROI/modes/{m}/band_{bi:02d}'];t=h[f'{m}/analytic_reference/band_{bi:02d}'];r=result['modes'][m];s=r['toy_sigma_q_ADC_V'][bi];e=g['amplitude_edges_V'][:];c=g['amplitude_counts'][:];x=np.linspace(0,max(e[-1],6*s),600)
   ax=axs[bi,0];ax.stairs(c/c.sum()/np.diff(e)/1e3,e*1e3,color=DATA,label='Data');ax.plot(x*1e3,x/s**2*np.exp(-x*x/(2*s*s))/1e3,color=TOY,label='Toy');ax.set(title=f'{off:+g} kHz amplitude',xlabel='A [mV ADC]',ylabel='Density [mV^-1]');ax.legend()
   ax=axs[bi,1];f=g['PSD_frequency_baseband_hz'][:];order=np.argsort(f)
   for ff,ps,color in [(f,g['PSD_total_V2_Hz'][:],DATA),(t['output_frequency_hz'][:],t['output_Welch_expected_ADC_V2_Hz'][:],TOY)]:
    oo=np.argsort(ff);ax.plot(ff[oo]/1e3,10*np.log10(np.maximum(ps[oo],1e-30)),color=color)
   ax.set(title='Filtered PSD',xlabel='Band-relative f [kHz]',ylabel='dB V²/Hz',xlim=(-50,50),ylim=(-180,-90))
   ax=axs[bi,2];lag=g['selected_lag_s'][:]*1e6;sel=lag<=120
   for co,color in [(g['selected_total_g1'][:],DATA),(t['g1'][:],TOY)]:ax.plot(lag[sel],co.real[sel],'o-',ms=1.5,color=color);ax.plot(lag[sel],co.imag[sel],'s--',ms=1.5,mfc='white',color=color)
   ax.set(title='Re solid / Im dashed g1',xlabel='Lag [µs]; 4 µs samples',ylabel='g1',ylim=(-.4,1.05))
  fig.suptitle(m+' — all seven bands: data teal; approved analytic reference purple\nFull-run amplitudes/PSD; first 5 SPEC measured g1; no fits or amplitude rescaling',fontsize=13);pdf.savefig(fig);plt.close(fig)
 # Separate source powers for every band: no artificial gain, common physical units.
 fig,axs=grid()
 source_rows=[]
 for i,m in enumerate(MODES):
  rr=result['modes'][m]
  for key,color,marker,label in [('thermal_RMS_ADC_V',THERMAL,'o','Cavity thermal'),('electronic_RMS_ADC_V',ELECTRONIC,'s','Electronic'),('toy_RMS_ADC_V',TOY,'^','Total')]:
   axs[0,i].semilogy(OFF,np.array(rr[key])*1e6,marker+'-',color=color,label=label)
  axs[0,i].set(title=m+' reference source RMS',xlabel='Offset [kHz]',ylabel='RMS [µV ADC]');axs[0,i].legend()
  axs[1,i].semilogy(OFF,rr['thermal_power_fraction'],'o-',color=THERMAL);axs[1,i].set(title=m+' thermal fraction',xlabel='Offset [kHz]',ylabel='Pcavity / Ptotal')
  for bi,off in enumerate(OFF):
   source_rows.append({'mode':m,'offset_hz':int(off*1000),**{key:rr[key][bi] for key in ['data_RMS_ADC_V','toy_RMS_ADC_V','data_moment_sigma_q_ADC_V','toy_sigma_q_ADC_V','thermal_RMS_ADC_V','electronic_RMS_ADC_V','thermal_power_fraction','data_over_toy_RMS']}})
 fig.suptitle('Approved reference: separate physical source powers in all 21 bands',fontsize=13,y=.995);pdf.savefig(fig);save(fig,'run680_reference_source_breakdown')
 with open(OUT/'run680_reference_band_statistics.csv','w') as stream:
  writer=csv.DictWriter(stream,fieldnames=source_rows[0]);writer.writeheader();writer.writerows(source_rows)
# Revised Part III. Temporal coloring is descriptive and never a physical temperature fit.
fig,axs=grid(3,3,h=4.9)
for i,m in enumerate(MODES):
 power=col(DCR[m],'AC2_ADC_V2')*1e6
 for j,s in enumerate([15,16,17]):
  temp=col(DCR[m],f't{s}_mK');scatter(axs[i,j],temp,power,f'{m} versus {SHORT[s]}',NAMES[s]+' [mK]','AC² [mV² ADC]');derived['temperature'][m+'_'+str(s)]={'Pearson':pearson(temp,power),'Spearman':spearman(temp,power)}
timecolor(fig,axs);save(fig,'fullband_temperature')
fig,axs=grid(1,3,h=3.05)
for i,(a,b) in enumerate([('TM010','TM011'),('TM010','TM012'),('TM011','TM012')]):
 x=col(DCR[a],'AC2_ADC_V2')*1e6;y=col(DCR[b],'AC2_ADC_V2')*1e6;scatter(axs[0,i],x,y,a+' / '+b,a+' AC² [mV² ADC]',b+' AC² [mV² ADC]');derived['between_modes'][a+'_'+b]={'Pearson':pearson(x,y),'Spearman':spearman(x,y)}
timecolor(fig,axs);save(fig,'fullband_mode_correlations')
fig,axs=grid(1,3,h=3.25)
f=np.linspace(-2.5e6,2.5e6,12000)
for i,m in enumerate(MODES):
 ax=axs[0,i];r=short['metrics'][m];fc=r['final_IF_hz'];gamma=r['f0_hz']/r['ql']/2;lor=1/(1+((f-fc)/gamma)**2)
 ax.plot(f/1e6,lor,color=NAVY,label='Cavity Lorentzian, peak = 1');ax.axvline(0,color=DATA,ls=':',label='Electronic zero');ax.axvline(1.25,color='#66768A',ls='--',label='BOR nominal resonance')
 for off in EO:ax.plot([(off-25)/1000,(off+25)/1000],[-.12,-.12],color=DATA,lw=6,solid_capstyle='butt')
 for off in OFF:ax.plot([1.25+(off-25)/1000,1.25+(off+25)/1000],[-.25,-.25],color=DATA,lw=4,solid_capstyle='butt')
 ax.text(-2.4,-.13,'DC bands',fontsize=6,va='center',color=DATA);ax.text(-2.4,-.26,'Resonance bands',fontsize=6,va='center',color=DATA)
 ax.set(title=m+' signed final I−iQ IF',xlabel='Digital frequency [MHz]',ylabel='Illustrative cavity response',xlim=(-2.5,2.5),ylim=(-.35,1.08));ax.legend(fontsize=5.5,loc='upper left')
save(fig,'frequency_coordinates')
# Absolute electronic baseline, and percent evolution per individual mode–band pair.
fig,axs=grid(1,3,h=2.9)
for i,m in enumerate(MODES):axs[0,i].plot(EO,np.sqrt(EP[m][0])*1e3,'o-',color=DATA);axs[0,i].set(title=m+' — run 680',xlabel='Electronic band center [kHz]',ylabel='RMS [mV ADC]',xticks=EO);axs[0,i].tick_params(axis='x',rotation=45)
save(fig,'electronic_absolute_baseline')
def evolution(bank, offsets, name):
 fig,axs=grid(1,3,h=3.0)
 for i,m in enumerate(MODES):
  Pm=bank[m]
  for bi,off in enumerate(offsets):axs[0,i].plot(time,100*(np.sqrt(Pm[:,bi]/Pm[0,bi])-1),color=DATA,ls=LS[bi%7],marker=['o','s','^'][bi//7],markevery=40,ms=2,label=f'{off:+g} kHz')
  axs[0,i].set(title=m,xlabel='Campaign clock [h]',ylabel='RMS change from own run-680 value [%]');axs[0,i].legend(ncol=3,fontsize=5)
 save(fig,name)
evolution(EP,EO,'electronic_relative');evolution(P,OFF,'resonance_relative')
def ratios(bank, offsets, center, name):
 fig,axs=grid()
 for i,m in enumerate(MODES):
  pm=bank[m];cs=pm[:,center]/np.delete(pm,center,axis=1).mean(axis=1);axs[0,i].plot(time,cs,color=DATA);axs[0,i].set(title=m+' central / mean noncentral',xlabel='Campaign clock [h]',ylabel='Power ratio')
  for bi,d in enumerate(sorted(set(abs(offsets))-{0})):
   ip=int(np.flatnonzero(offsets==d)[0]);im=int(np.flatnonzero(offsets==-d)[0]);axs[1,i].plot(time,pm[:,ip]/pm[:,im],color=DATA,ls=LS[bi],label=f'±{d:g} kHz')
  axs[1,i].set(title=m+' symmetric-band ratio',xlabel='Campaign clock [h]',ylabel='P(+offset) / P(−offset)');axs[1,i].legend(ncol=2)
 save(fig,name)
ratios(EP,EO,4,'electronic_ratios');ratios(P,OFF,3,'resonance_ratios')
fig,axs=grid()
for i,m in enumerate(MODES):
 e=100*h[m+'/shared_window_power_relative_error'][:];axs[0,i].plot(time,e,color=DATA);axs[0,i].axhline(0,color=NAVY,ls=':');axs[0,i].set(title=m+' shared +1 MHz control',xlabel='Campaign clock [h]',ylabel='PSD / historical power − 1 [%]')
 v=result['validation'][m];ax=axs[1,i];ax.axis('off');ax.text(.02,.9,'260 / 260 signed coordinates validated\n253 original I−iQ products\n7 documented I+iQ products reindexed\nOriginal archives retained\n\nMedian power error: '+f"{v['selected_median_power_error_percent']:+.4f}%\nMaximum |power error|: {v['selected_max_abs_power_error_percent']:.4f}%\nEight-band maximum |error|: {v['all_nonzero_electronic_max_abs_power_error_percent']:.4f}%",va='top',fontsize=10)
save(fig,'PSD_campaign_validation')
fig,axs=grid(1,3,h=3)
for i,m in enumerate(MODES):
 for bi,off in enumerate(OFF):axs[0,i].plot(time,np.sqrt(P[m][:,bi])*1e3,color=DATA,ls=LS[bi],label=f'{off:+g} kHz')
 axs[0,i].set(title=m,xlabel='Campaign clock [h]',ylabel='RMS [mV ADC]');axs[0,i].legend(ncol=3,fontsize=5)
save(fig,'resonance_absolute')
fig,axs=grid(3,3,h=4.9)
for i,m in enumerate(MODES):
 for j,s in enumerate([15,16,17]):scatter(axs[i,j],col(DCR[m],f't{s}_mK'),P[m][:,3]*1e6,f'{m} resonance / {SHORT[s]}',NAMES[s]+' [mK]','Band power [mV² ADC]')
timecolor(fig,axs);save(fig,'resonance_temperature')
fig,axs=grid(1,3,h=3)
for i,(a,b) in enumerate([('TM010','TM011'),('TM010','TM012'),('TM011','TM012')]):scatter(axs[0,i],P[a][:,3]*1e6,P[b][:,3]*1e6,a+' / '+b,a+' central power [mV² ADC]',b+' central power [mV² ADC]')
timecolor(fig,axs);save(fig,'resonance_mode_correlations')
fig,axs=grid()
for i,m in enumerate(MODES):
 for bank,c,ls,label,center in [(EP,DATA,'-','Electronic DC-centered',4),(P,DATA,'--','Resonance-centered',3)]:
  pp=bank[m];side=np.delete(pp,center,axis=1).mean(axis=1);rel=np.sqrt(side/side[0]);shape=pp[:,center]/side
  axs[0,i].plot(time,100*(rel-1),ls,color=c,label=label);axs[1,i].plot(time,100*(shape/shape[0]-1),ls,color=c,label=label)
  derived['band_stability'][m+'_'+label]={'side_RMS_end_change_percent':float(100*(rel[-1]-1)),'central_to_side_ratio_relative_span_percent':float(100*(np.nanmax(shape/shape[0])-np.nanmin(shape/shape[0])))}
 full=col(DCR[m],'AC2_ADC_V2');axs[0,i].plot(time,100*(np.sqrt(full/full[0])-1),':',color=NAVY,label='Full-band AC RMS')
 axs[0,i].set(title=m+' common level evolution',xlabel='Campaign clock [h]',ylabel='RMS change [%]');axs[0,i].legend(fontsize=5.5)
 axs[1,i].set(title=m+' relative spectral-shape change',xlabel='Campaign clock [h]',ylabel='Change in central / side ratio [%]');axs[1,i].legend(fontsize=5.5)
save(fig,'bank_stability_comparison')
fig,axs=grid(1,3,h=2.9);cvtheory=np.sqrt((4-np.pi)/np.pi)
for i,m in enumerate(MODES):
 cv=col(RR[m],'amplitude_noise_rms_v')/col(RR[m],'mean_amplitude_v');axs[0,i].plot(time,cv,color=DATA,label='Measured CV');axs[0,i].axhline(cvtheory,color=NAVY,ls='--',label='Rayleigh 0.5227232');axs[0,i].set(title=m,xlabel='Campaign clock [h]',ylabel='std(A) / mean(A)');axs[0,i].legend()
save(fig,'normalized_shape_with_Rayleigh')
# Drift controls are kept entirely in an appendix; no temperature-response model.
fig,axs=grid(3,3,h=4.9)
for i,m in enumerate(MODES):
 for j,s in enumerate([15,16,17]):scatter(axs[i,j],residual(col(DCR[m],f't{s}_mK')),residual(col(DCR[m],'AC2_ADC_V2')*1e6),f'{m} / {SHORT[s]} residuals',NAMES[s]+' residual [mK]','Residual AC² [mV² ADC]')
timecolor(fig,axs);save(fig,'appendix_temperature_clock_residuals')
fig,axs=grid(1,3,h=3)
for i,(a,b) in enumerate([('TM010','TM011'),('TM010','TM012'),('TM011','TM012')]):scatter(axs[0,i],residual(col(DCR[a],'AC2_ADC_V2')*1e6),residual(col(DCR[b],'AC2_ADC_V2')*1e6),a+' / '+b+' clock residuals',a+' residual power',b+' residual power')
timecolor(fig,axs);save(fig,'appendix_mode_clock_residuals')
fig,axs=grid(3,2,h=4.9)
for i,m in enumerate(MODES):
 rr=DCR[m];ax=axs[i,0];ax.plot(time,np.sqrt(col(rr,'total2_ADC_V2'))*1000,color=DATA,label='Raw RMS');ax.plot(time,np.sqrt(col(rr,'AC2_ADC_V2'))*1000,'--',color=DATA,label='AC RMS');ax.set(title=m+' full-band noise',ylabel='RMS [mV ADC]');ax.legend(ncol=2)
 sensor=[15,16,17][i];ax=axs[i,1];ax.plot(time,col(rr,f't{sensor}_mK'),color=DATA);ax.set(title=SHORT[sensor],ylabel='Temperature [mK]')
for ax in axs[-1]:ax.set_xlabel('Campaign clock [h]')
save(fig,'campaign_stability_physical')
fig,axs=grid()
for j,(alias,title) in enumerate([('Mercury4K','4 K plate diode — HEMT-stage proxy'),('Mercury50K','50 K plate — Pt'),('MercuryMagnet','Magnet — RuO₂, 4 K stage')]):
 axs[0,j].plot(time,col(TEMP_ROWS,alias),color=DATA);axs[0,j].set(title=title,xlabel='Campaign clock [h]',ylabel='Temperature [K]')
for j,m in enumerate(MODES):scatter(axs[1,j],col(TEMP_ROWS,'Mercury4K'),col(DCR[m],'AC2_ADC_V2')*1e6,m+' full-band AC² versus 4 K plate','4 K plate diode [K]','AC² [mV² ADC]')
timecolor(fig,axs);save(fig,'cryogenic_stage_temperatures')
h.close();pilot.close()
# Native slide assembly.
D=sd.Deck();provenance=[]
def page(title,sub,scope,source,notes,figure=None,caption='',section='III'):
 s=D.new(' ',sub,source,notes);s['title']=title;s['footer']='FLASH | v47 | PART '+section+' | '+('RUN 680 + STEP 6' if section=='II' else 'LONG-TERM DATA' if section=='III' else 'APPENDIX')
 size=25
 while len(sd.wrap(title,12.2,size).splitlines())>1:size-=1
 s['items'][1]['size']=size;s['items'][1]['text']=title
 if figure:D.image(s,.4,1.75,12.55,4.4,figures[figure])
 if caption:D.text(s,.65,6.37,12.05,.5,caption,11)
 provenance.append({'slide':24+len(D.slides),'title':title,'section':section,'statistical_population':scope,'run_ids':[680] if section=='II' else list(range(680,940)),'source_products':source,'estimator':notes,'figures':[it['path'] for it in s['items'] if it['kind']=='image']})
 return s

def reused(index,section,notes,caption=None):
 s=copy.deepcopy(prior[index-1]);D.slides.append(s);s['footer']='FLASH | v47 | PART '+section+' | '+('APPENDIX' if section=='APP' else 'LONG-TERM DATA');s['notes']+='\nV47: '+notes
 if caption:
  for item in s['items']:
   if item['kind']=='text' and abs(item['y']-6.37)<.001:item['text']=sd.wrap(caption,item['w'],11);item['size']=11
 for item in s['items']:
  if item['kind']=='image':
   src=track(item['path']);dst=A/src.name
   if src!=dst:shutil.copy2(src,dst)
   item['path']=str(dst)
 provenance.append({'slide':24+len(D.slides),'title':s['title'],'section':section,'statistical_population':'260 runs 680–939','run_ids':list(range(680,940)),'source_products':'v45 slide '+str(index)+'; '+s['source'],'estimator':s['notes'],'figures':[it['path'] for it in s['items'] if it['kind']=='image']})
 return s

def table(slide,heads,data,y,widths,size=12,rowh=.45):
 for ri,row in enumerate([heads]+data):
  x=.65
  for value,width in zip(row,widths):
   D.text(slide,x,y+ri*rowh,width-.08,rowh,str(value),size,ri==0);x+=width

p='Analytic step-6 expectations and saved run680 resonance pilot; results.json and expectations_and_campaign.h5.'
thermal=', '.join(m+': '+f"{result['modes'][m]['thermal_RMS_ADC_V'][3]*1e6:.3f} µV" for m in MODES)
page('Resonance bands — absolute reference versus run 680','Additional Part II comparison | same BOR centers and implemented 50 kHz FIR; no rescaling.','Full run680:209.7152s;analytic stationary expectation.',p,
 'Integrate separately cavity thermal and receiver PSD times actual FIR magnitude squared. Approved PartI parameters/temperature/gain/kz preserved. All seven centers use BOR+1.250MHz; physical cavity IF remains1.250/1.248/1.256MHz. Moment sigma=sqrt(AC²/2), not an empirical Rayleigh fit. Thermal and electronic powers add; RMS values do not. ADC±2V. Filter output250kS/s,dt4us.',
 'run680_resonance_absolute','Thermal-only central RMS: '+thermal+'. Its tiny power is included in the total; the absolute mismatch is retained.',section='II')
summary_page=page('Absolute noise level — full band and resonance region','Run 680 | the same mode-dependent scale discrepancy appears in two distinct spectral selections.','Run680full-bandmomentsandcentralresonanceband;unchangedapprovedreference.',p,
 'Full-band ratios are the existing approved AC-RMS/reference values, displayed to three decimals. Resonance ratios use the existing analytical PartI FIR integral and run680pilot. No refit or renormalization. Thermal power fractions use separate source integrals; not additive RMS fractions.',section='II')
full_ratios=[np.sqrt(float(DCR[m][0]['AC2_ADC_V2']))/short['metrics'][m]['total_RMS_expected_ADC_V'] for m in MODES]
table(summary_page,['Mode','Full-band data/toy RMS','Resonance data/toy RMS'],[[m,f'{full_ratios[i]:.3f}',f"{result['modes'][m]['data_over_toy_RMS'][3]:.3f}"] for i,m in enumerate(MODES)],1.9,[1.4,5.3,5.3],size=15,rowh=.43)
D.text(summary_page,.7,3.92,12,.35,'Predicted cavity thermal contribution in the central resonance band',17,True)
table(summary_page,['Mode','Thermal RMS [µV ADC]','Thermal / total power [ppm]'],[[m,f"{result['modes'][m]['thermal_RMS_ADC_V'][3]*1e6:.3f}",f"{result['modes'][m]['thermal_power_fraction'][3]*1e6:.2f}"] for m in MODES],4.42,[1.4,5.3,5.3],size=14,rowh=.4)
D.text(summary_page,.7,6.35,12,.5,'The discrepancy concerns the overall noise level; even around resonance, predicted electronic noise dominates by roughly 3 ppm in power.',11)
page('Resonance-band amplitude distributions','Central band shown; all 21 amplitude/PSD/correlation panels are in the separate supplement.','Full-run measured histograms versus analytic Gaussian amplitude expectation.',p,
 'The zero-mean proper Gaussian reference predicts Rayleigh amplitudes with sigma²=Ptotal/2. No fit or gain adjustment. Data moment sigma only standardizes the lower shape-only plot; the upper physical scale retains the absolute mismatch. Data outputmean retained. PSD alone never provides an empirical amplitude distribution.',
 'run680_resonance_amplitude_CCDF','Above: absolute distributions. Below: shape-only ln CCDF versus A²/(2σ²); normalization of the shape axis is not an amplitude calibration.',section='II')
page('Resonance-band PSD and complex autocorrelation','Central bands | identical signed output frequency and lag conventions.','PSD:full run680;measured g1:first5SPEC1.048576s;toy:analytic stationary.',p,
 'Filter output250kS/s,dt4us. Theory includes original sampled PSD and all20decimation aliases; expected Hann Welch smoothing matches full-run PSD estimator. g1=E[z(t+tau)z*(t)]/P; no outputmean removed; analytical covariance is Fourier integral of filtered PSD. Markers every4us. These 50kHz-band correlations are not intrinsic cavity decay fits. All21bands supplied separately.',
 'run680_resonance_PSD_g1','FIR scale 1/B ≈ 20 µs ≫ cavity decay ≈ 1 µs. Filtered g1 agreement is not a cavity-decay measurement; measured lags are 4 µs apart.',section='II')
page('Resonance-band power ratios','Absolute baseline asymmetries retained | no ratio is forced to unity.','Complete run680 filtered powers and analytic reference.',p,
 'Central/side=Pcenter/arithmetic mean of six noncentral resonance bands. Symmetric ratios=P(+d)/P(-d),d100/250/500kHz. Thermal/electronic contributions separately saved. No LF response hypothesis or hardware model introduced.',
 'run680_resonance_ratios','Ratios compare spectral shape; absolute amplitude discrepancies remain on the preceding pages. Cavity thermal noise is negligible in this reference.',section='II')
# Main campaign pages, with the requested editorial changes.
page('Campaign temperatures and absolute noise levels','260 runs | verified physical sensor names; unchanged full-band ADC moments.','All260originalcomplete-runnoiseandthermometer summaries.','Primary260v2HDF5 complex moments;verifiedODB/INPTsensorinventory.',
 'RF cavity uses Temp_AVS INPT index15,ODB T4,Dale1.5K,operator sensor17. MC CMN143 uses index16,ODB T5,operator18. MC CMN130 uses index17,ODB T6,operator19. Alloldtemperaturemedians reproducedexactly; unitsmK. No numericaltemperatureor modelchange.',
 'campaign_stability_physical','RF cavity = T15/T4; Mixing Chamber CMN143 = T16/T5; Mixing Chamber CMN130 = T17/T6. Aliases refer to zero-based INPT indices.')
page('Full-band AC noise power versus temperature','Direct scatter | time-colored points; Pearson and Spearman; no physical response fit.','All260complete-run summaries;one paired point per run/mode/sensor.','Direct v2 complex moments; primary fullband_v2.csv.',
 'AC² is mean-square ADC voltage after one whole-run mean removal. Time color identifies campaign stages. Pearson and Spearman describe associations, not causality; serial dependence and common drift remain. Linear-clock controls moved to appendix.',
 'fullband_temperature','No temperature-response law is assumed. Temporal coloring reveals common campaign evolution; drift controls are reported only in the appendix.')
page('Additional cryogenic temperatures — HEMT-stage proxy','4 K, 50 K and magnet thermometers are available throughout the campaign.','260runs;10–11observationsperruninsideSPECbounds;nointerpolation.','ExistingTemp_Mercury INPT;verifiedODB/schema;thesisPDFp52.',
 'HEMT is thermalized to4Kstage per thesisp52. MercuryINPTindex4 Diode_4K_T K measures4Kplate,not HEMT junctionorcase. 260validrunmedians,3.9912–4.0569K. UnitsKfromdocumentedchannelmap,ODBunitstringsblank. Thermometercalibrationaccuracyunknown. MCdiodechannel8recordszerosandexcluded. Pearson/Spearmanare descriptive,notcausal.',
 'cryogenic_stage_temperatures','The 4 K plate thermometer is a stage proxy, not a direct HEMT thermometer. All shown quantities are observed; zero MC-diode readings are excluded.')
interpret=page('Temperature associations — evidence and limits','Strong campaign associations weaken for successive-run changes; causality remains unresolved.','260matchedrun summaries;Pearson/Spearman;nosignificanceorphysicalfit.','Verifiedsensorinventoryandnewresults.json.',
 'Among original three mK sensors,RFcavity has strongest negative Pearson association; Spearman ranks can be stronger forMC. Including4Kplate gives strongerPearson than cavity. Thermal model emission growswithTbutpredictedfractiononly2.4–3.2ppm; anticorrelationcannotdirectlyidentifycavitythermalemission. RFgain,equivalentreceivernoise and electronicconditionsremainunseparated hypotheses.')
headers=['Mode','RF cavity r','RF cavity ρ','4 K plate r','ΔRF cavity r','Δ4 K plate r']
data=[]
for m in MODES:
 cc=result['full_band_temperature_correlations'][m]['T15'];kk=result['full_band_temperature_correlations'][m]['Mercury4K']
 data.append([m,f"{cc['raw']['Pearson']:+.3f}",f"{cc['raw']['Spearman']:+.3f}",f"{kk['raw']['Pearson']:+.3f}",f"{cc['first_differences']['Pearson']:+.3f}",f"{kk['first_differences']['Pearson']:+.3f}"])
table(interpret,headers,data,1.95,[1.1,2.18,2.18,2.18,2.18,2.18],size=11.5,rowh=.45)
D.bullets(interpret,.75,4.05,11.7,[
 'The cavity has the strongest negative Pearson association among the original three mK sensors; the added 4 K proxy is stronger still.',
 'The predicted cavity emission increases with temperature and contributes only 2.4–3.2 ppm of resonance-band power.',
 'Common evolution in all modes and spectral regions suggests a shared apparatus state; gain and receiver-noise variations cannot yet be separated.'
],size=15,gap=.13)
page('Full-band correlations between noise levels','Three direct mode-pair scatter plots | common acquisition-time color.','All260paired complete-run AC² summaries.','Direct v2 complex moments; primary fullband_v2.csv.',
 'Pearson and Spearman computed from measured full-band AC power. No response fit, gain measurement or causal interpretation. Clock-residual plots are in appendix.',
 'fullband_mode_correlations','The modes co-vary strongly. These associations do not establish their physical cause or measure an electronic gain.')
page('Frequency coordinates — two distinct filter banks','Entire digital band −2.5 to +2.5 MHz | electronic zero and nominal resonance explicitly separated.','Common BOR references of all260runs;physical cavity parameters from approved PartI.','BOR audit680–939;original FIR configuration;approved cavity f0 and QL.',
 'Electronic DC-centered centers0,±100,±250,±500,±1000kHz; resonance centersBOR1.250MHz+0,±100,±250,±500kHz; nominal width50kHz each,ENBW47.4288068kHz. Cavity fit IF1.250/1.248/1.256MHz differs from all-modeBOR1.250MHz. Lorentzian curves have illustrative unit peak, not physical electronic/thermal power ratio. Thermal cavity PSD is negligible versus reference electronic noise.',
 'frequency_coordinates','Teal upper row: electronic bands; lower row: resonance bands. The unit-peak Lorentzian is illustrative, not a thermal/electronic power ratio.')
# Native compact acquisition-coordinate table below a simple figure is kept in notes/README to avoid overcrowding.
page('Electronic bands — absolute run-680 baseline','Nine electronic-frequency bands | physical ADC units before inspecting relative changes.','Fullrun680 filtered sample-weighted mean-square voltages.','Direct v2 run680 complex moments; ADC conversion applied once.',
 'RMS=sqrt(sample-weighted average of perSPEC rms²). Historical DC bank subtracts one whole-run inputmean before mixing/FIR. Therefore the central band excludes the removed runDC, but retains finite-time residual fluctuations and its outputmean. No perSPECmean subtraction. Originalfilter unchanged.',
 'electronic_absolute_baseline','Nominal width 50 kHz; ENBW 47.4288 kHz. The central band excludes the subtracted whole-run DC component; residual LF noise remains.')
page('Electronic bands — relative RMS evolution','Each mode–band pair is referenced to its own run-680 RMS.','260runs×3modes×9bands.','Direct v2 electronic_bands_v2.csv; each baseline from run680.',
 'Displayed100*(RMSmode,band(run)/RMSmode,band(680)-1). These are independent baseline references, not equal physical powers. Absolute baselines are on previous page. No reprocessing or additional filter bank.',
 'electronic_relative','ΔRMSm,b(r) = 100 × [RMSm,b(r) / RMSm,b(680) − 1] %. These bands are referenced to electronic zero, not cavity resonance.')
page('Electronic bands — ratios isolate spectral shape','Central / mean eight noncentral bands, and symmetric electronic-frequency pairs.','All260runs;original continuous filtered moments.','Direct v2 nine-band complex moments; electronic_bands_v2.csv.',
 'Central band excludes removed whole-runDC. P0/mean8sideP and P(+d)/P(-d) cancel a common multiplicative power scale. They can still respond to spectral shape or mode-dependent changes; no gain inference. Absolute asymmetries retained.',
 'electronic_ratios','A common multiplicative level change cancels in these ratios. Central means electronic DC; the eight noncentral bands are not cavity sidebands.')
page('Archived PSDs — campaign validation','260/260 coordinates validated | seven documented I+iQ archives corrected in separate copies.','1000SPEC per archive;all260runs;sharedwindow equalsnew−250kHzband.','Archivedfft_by_runNPZ;BORaudit;historicalv2band+1MHz.',
 'Correct actual16383FFTlength and Hann ENBW; physical BORADCscaling appliedonce. Integrate PSD×actualFIR|H|². No fitted correction. Recoveredjobarguments prove sevenIQ+1products; allremaining253IQ−1. JobNPZcopiesbyteidenticaltoarchives. OriginalSPECprefixcheckscoverallsevenandthreecontrols. ExactPminus(f)=Pplus(−f) reindexing,samepowers,nowall260included. Reco_version1.1forall;actualhistoricalsourcesnapshotSHAmissing. No fittednormalizationcorrection. Chunkmeanremoval affectsDC;validation is awayfromDC. Full time series and summary saved.',
 'PSD_campaign_validation','Execution arguments and byte-identical job artifacts establish the seven sign changes; original-SPEC checks confirm the exact conjugation relation.')
page('Resonance bands — absolute RMS across the campaign','260 runs with verified frequency coordinates; seven corrected copies retain the original absolute normalization.','260verifiedcoordinatePSDs;sevenlosslesslycorrectedcopies;power-onlyintegrals.','Newcampaign_band_powers.csv;archivedNPZandBORaudit.',
 'Same50kHzFIR as pilot. No raw filtering of remaining259runs. Centers use recordedVNA−LO1−LO2 and I−iQsign. Nominal references stable,not physicalresonancetracking. ADCvoltsnotinputreferredRFpower.',
 'resonance_absolute','Seven offsets: 0, ±100, ±250, ±500 kHz. Centers use each run’s BOR; no arbitrary fallback frequency is used.')
page('Resonance bands — relative RMS evolution','260 runs | each pair retains its own physical run-680 baseline.','All260verifiedcoordinatePSDs.','Newcampaign_band_powers.csv.',
 '100*(sqrt(Pband(run)/Pband(680))-1). No normalization fit or fixed-conditiontoy comparison in campaign chapter. The small archivedPSD estimator error is shown on validation page.',
 'resonance_relative','ΔRMSm,b(r) = 100 × [sqrt(Pm,b(r) / Pm,b(680)) − 1] %. The archived-PSD estimator is used consistently for every run.')
page('Resonance-band power versus measured temperatures','260 runs; central band shown | physical sensor names, Pearson and Spearman for all bands.','All260matchedPSD/sensormedianpairs.','Newresults.json correlations;existing sensor table.',
 'No physicaltemperaturefit. RawPearson/Spearman are descriptive. Firstdifferenceandlinearclockcontrolledcoefficients also saved to distinguish common drift,withoutcausalclaims. Serialdependenceprecludesindependenttrialpvalues.',
 'resonance_temperature','Time-colored associations are not evidence of causality. First-difference and clock-controlled coefficients are documented for every band.')
page('Resonance-band correlations between modes','260 runs | central resonance bands; direct scatter with campaign-time color.','All260verifiedcoordinatePSDpowerestimates.','Newresults.jsonbetween_mode_correlations.',
 'CentralbandPADC for eachmode. RawPearson/Spearman and driftcontrols are saved. No temperature/gainfit, causalityor physicalsourceidentification inferred.',
 'resonance_mode_correlations','These correlations concern narrow resonance-centered bands; the full-band AC-power correlations were shown separately.')
page('Resonance bands — central and symmetric power ratios','Central / mean six noncentral bands; symmetric offsets ±100, ±250 and ±500 kHz.','All260verifiedcoordinatePSDs.','Newcampaignpowers;actualFIRweighting.',
 'Ratios computedfromabsolutepowers,notaveragedRMS. Commonmultiplicativescalecancels. Absoluteinstrumentalasymmetryretained. SixsidewindowsdifferfromhistoricaleightDCsidewindows;ratiosnotinterchangeable.',
 'resonance_ratios','Central means the BOR nominal resonance here. Mean side power averages six bands; this definition differs from the electronic bank.')
page('Temporal stability — electronic versus resonance bands','Separate common level evolution from changes in relative spectral shape.','Bothbanks260runs;sevenprovenancevalidatedPSDcopies.','Existing9bandtableandnew7bandpowers.',
 'Top:relativeRMSofmean noncentralbandpower. Bottom:central/sidepower ratio dividedbyownrun680ratio. Each bank usesdifferentwindowsandsidedefinition;thisisastabilitycomparison,notapointwisepoweridentityor gainmeasurement. Shared+1MHzidentitycheckedseparately.',
 'bank_stability_comparison','Full-band, electronic and resonance-region RMS follow nearly the same evolution. Resonance spectral shape varies much less than the absolute level.')
reused(32,'III','Approved experimental DC evolution retained; no PSD-derived DC is substituted.')
page('Stability of normalized amplitude shape','Full-band experimental moments | theoretical Rayleigh coefficient of variation shown.','All260originalfull-runamplitudemoments;notPSDderived.','Direct v2 global amplitude moments; primary raw_statistics_v2.csv.',
 'CV=std(A)/mean(A); Rayleighsqrt((4-pi)/pi)=0.5227232. StableCV is a momentproxy,notproof of fullnormalizeddistributionstationarityorindependentsamples. No resonancebanddistribution inferredfromPSD.',
 'normalized_shape_with_Rayleigh','The Rayleigh reference is CV = sqrt[(4 − π)/π] = 0.5227232. Stable normalized moments do not establish stable full distributions.')
reused(34,'III','Source confirmed numerically against primary260v2 threshold counts; full-range equivalence audit. LocalT=meanA(run)+kstdA(run);fixedT=meanA(pilot680)+kstdA(pilot680). Fractions count samples,not independent events. An adaptive trigger can track scale drift but requires separate event/false-alarm validation.', 'Local: T(r)=mean A(r)+k std A(r). Fixed: saved run-680 pilot threshold. Local adaptation tracks drift; counts are samples, not independent events.')
s=page('Long-term findings','Three distinct scopes: full-band characterization, electronic diagnostics and resonance-region powers.','260runs680–939;resonance amplitudes/phase/tails not reconstructed.','ExistingcampaignsummariesandvalidatedarchivedPSDbandpowers.',
 'Summaryrestrictedtoexperimentalcampaignresults. No toy at constant conditions used to explain long-term variation. No new hardwaretransferfunction,step9orPartIVassembled.')
spans=result['noise_spans']
D.bullets(s,.75,1.8,11.75,[
 'Common RMS variation ≈2.5–3.3%: full-band max/min spans are 2.64%, 2.75% and 3.26% for TM010/011/012.',
 'Mode noise powers are strongly correlated; full-band, electronic and resonance regions share almost the same level evolution.',
 'Resonance central/side power ratios span only 0.33%, 0.24% and 0.24%; the electronic DC region retains mode-dependent shape structure, especially TM010.',
 'Noise is negatively associated with cavity, MC and 4 K-stage temperatures; weaker successive-run associations and common drift preclude a causal conclusion.',
 'Normalized amplitude moments remain stable near Rayleigh expectations. Fixed thresholds respond to level drift, motivating future adaptive triggers.',
 'Common receiver gain and/or equivalent noise-temperature changes remain compatible hypotheses; they cannot currently be separated. No gain or Tn adjustment is applied.'
],size=15,gap=.105)
# Only descriptive statistical controls in appendices.
page('Appendix — temperature correlations after clock control','Both quantities projected off an intercept and linear campaign clock.','260run-levelsummaries;statisticalcontrolonly.','Existinglongterm.csv;descriptivelinearclockprojection.',
 'Not a physicaltemperaturefit. Doesnotremove nonlinearsharedtrendsorotherconfounders;serialdependence retained. Pearson/Spearman of residuals are descriptive.',
 'appendix_temperature_clock_residuals','Removing a linear clock trend is a limited statistical diagnostic; residual association does not demonstrate a physical temperature dependence.',section='APP')
page('Appendix — inter-mode correlations after clock control','Residual scatter is separated from the direct measured-power plots.','260matchedrun-levelsummaries.','Existinglongterm.csv;descriptivelinearclockprojection.',
 'No physicalresponsefit. Residualcorrelationcanretain nonlinearcommoncampaignstructure;notcausality.',
 'appendix_mode_clock_residuals','These residuals are a statistical control, not a physical noise model or gain estimate.',section='APP')
reused(31,'APP','Descriptive common trend,not an independently measured electronic gain. Target modes contribute to the trend; no normalization of the scientific results is changed.', 'The common trend is descriptive and includes the target modes. It must not be interpreted as a measured electronic gain.')
inventory=page('Appendix — verified thermometer identities and coverage','Operator sensor numbers differ from zero-based MIDAS bank indices.','CachedINPTfor260runs;ODBchecksontenoriginalrawprefixes;verifiedhistoricalmedians.','sensor_inventory.json;originalCSV/schema;originalSPEC/HDF5timestampbounds.',
 'No ordering assumption: identity follows equipment,ODBlabel,documentedbridgechannel,originalINPTlayout and unchangedextractioncode. Operatornumbers17/18/19 map by suppliednames,notarraypositions. HEMTstageproxyuses Mercuryindex4. MCdiodezerochannelisexcluded. CorrelationCSVkeepsaliasesandphysicalnames.',section='APP')
table(inventory,['Operator ID','Physical sensor','Equipment / ODB','INPT index','Unit'],[
 ['17','RF cavity — Dale1.5K','AVS / T4','15','mK'],['18','MC — CMN143','AVS / T5','16','mK'],['19','MC — CMN130','AVS / T6','17','mK'],['—','4 K plate diode','Mercury / Diode_4K_T K','4','K'],['—','50 K plate Pt','Mercury / Pt_50K_T K','2','K'],['—','Magnet RuO₂','Mercury / RuO2_Mag_T K','12','K']
],1.9,[1.25,3.4,4.15,1.6,1.6],size=12,rowh=.46)
D.text(inventory,.7,5.55,12,.66,'Each listed sensor has 260 valid run medians and 10–11 observed readings per SPEC interval. The Mercury MC-diode channel is zero throughout and is excluded.',13)
D.text(inventory,.7,6.35,12,.5,'Original aliases T15/T16/T17 are retained for traceability. Stage temperatures are not direct HEMT device temperatures.',11)
# Assets and citations: all new pages get exact external provenance.
for s,p in zip(D.slides,provenance):
 for item in s['items']:
  if item['kind']=='image':track(item['path'])
 p['figures']=[it['path'] for it in s['items'] if it['kind']=='image']
 if len(sd.wrap(s['source'],11.8,7.5).splitlines())>1:s['notes']+='\nFull sources: '+s['source'];s['source']='Existing campaign tables / archived PSDs / approved reference; exact scope and sources in notes and provenance.'
for record in provenance:
 if record['section']=='III' and record['title'].startswith(('Resonance bands','Resonance-band')):record['run_ids']=result['coordinate_audit']['included_runs']
 if record['title'].startswith('Temporal stability'):record['population_by_bank']={'electronic':260,'resonance':260,'quarantined_runs':result['coordinate_audit']['quarantined_runs']}
front=copy.deepcopy(prior[:24]);old_temperature_line='Observed median temperatures: T15 = 40.422 mK; T16 = 37.580 mK; T17 = 46.062 mK.'
new_temperature_line='RF cavity (T15): 40.422 mK; MC–CMN143 (T16): 37.580 mK; MC–CMN130 (T17): 46.062 mK.'
for item in front[14]['items']:
 if item['kind']=='text' and 'T15 =' in item['text']:
  item['text']=sd.wrap(new_temperature_line,item['w'],item['size'])
  assert len(item['text'].splitlines())==1
front[14]['notes']+=' V47: verified physical temperature sensor names only; original numeric values, acquisition and physical model unchanged.'
front_deck=sd.Deck();front_deck.slides=[front[14]]
sd.export(front_deck,OUT/'sensor_label_update','v47_sensor_label','17 November 2026',page_offset=14,total_pages=34)
TOTAL=24+len(D.slides)
TAIL=OUT/'updated_sections';sd.export(D,TAIL,'v47_updated_sections','17 November 2026',page_offset=24,total_pages=TOTAL)
# Copy first24 PDF pages exactly; no regeneration of approved slides.
sys.path.insert(0,'/tmp/v46-pdf-deps')
try:
 from pypdf import PdfReader, PdfWriter
except ImportError:
 raise RuntimeError('pypdf required: install under /tmp/v46-pdf-deps')
else:
 # Reuse each reader's shared objects without rasterization or scientific regeneration.
 writer=PdfWriter();approved_reader=PdfReader(OLD/'iq_noise_summary_v45.pdf')
 updated_reader=PdfReader(TAIL/'iq_noise_summary_v47_updated_sections.pdf')
 sensor_reader=PdfReader(OUT/'sensor_label_update/iq_noise_summary_v47_sensor_label.pdf')
 for index,p in enumerate(list(approved_reader.pages)[:24]):writer.add_page(sensor_reader.pages[0] if index==14 else p)
 for p in updated_reader.pages:writer.add_page(p)
 with open(OUT/'iq_noise_summary_v47.pdf','wb') as stream:writer.write(stream)
# Keep approved native PPTX objects and remove only the old campaign chapter.
base=Presentation(OLD/'iq_noise_summary_v45.pptx')
for rel in list(base.slides._sldIdLst)[24:]:base.part.drop_rel(rel.rId);base.slides._sldIdLst.remove(rel)
changed_native=0
for shape in base.slides[14].shapes:
 if not shape.has_text_frame:continue
 for paragraph in shape.text_frame.paragraphs:
  for run in paragraph.runs:
   if old_temperature_line in run.text:run.text=run.text.replace(old_temperature_line,new_temperature_line);changed_native+=1
assert changed_native==1
base.slides[14].notes_slide.notes_text_frame.text=front[14]['notes']
extra=Presentation(TAIL/'iq_noise_summary_v47_updated_sections.pptx');RNS='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
for src in extra.slides:
 dst=base.slides.add_slide(base.slide_layouts[6]);dst.background.fill.solid();dst.background.fill.fore_color.rgb=RGBColor.from_string(sd.BG.lstrip('#'))
 for shape in src.shapes:
  el=copy.deepcopy(shape.element)
  for node in el.iter():
   for attr in [RNS+'embed',RNS+'link']:
    old=node.get(attr)
    if old:
     rel=src.part.rels[old]
     if rel.reltype.endswith('/image'):_,new=dst.part.get_or_add_image_part(io.BytesIO(rel.target_part.blob));node.set(attr,new)
     else:raise ValueError('Unexpected shape relationship')
  dst.shapes._spTree.insert_element_before(el,'p:extLst')
 dst.notes_slide.notes_text_frame.text=src.notes_slide.notes_text_frame.text
base.save(OUT/'iq_noise_summary_v47.pptx')
for i in range(1,25):shutil.copy2(OUT/'sensor_label_update/slide_01.png' if i==15 else OLD/f'slide_{i:02d}.png',OUT/f'slide_{i:02d}.png')
for i in range(1,len(D.slides)+1):shutil.copy2(TAIL/f'slide_{i:02d}.png',OUT/f'slide_{i+24:02d}.png')
sheet=Image.new('RGB',(640*3,360*int(np.ceil(TOTAL/3))),'white')
for i in range(TOTAL):
 with Image.open(OUT/f'slide_{i+1:02d}.png') as im:sheet.paste(im.resize((640,360)),((i%3)*640,(i//3)*360))
sheet.save(OUT/'contact_sheet.png')
(OUT/'slide_model.json').write_text(json.dumps(front+D.slides,indent=2)+'\n')
(OUT/'slide_provenance.json').write_text(json.dumps([{'slide':i+1,'title':s['title'],'section':'I' if i<14 else 'II','source_products':s.get('source',''),'estimator':s.get('notes',''),'audit':'See complete observable provenance audit'} for i,s in enumerate(front)]+provenance,indent=2)+'\n')
(OUT/'derived_from_existing_tables.json').write_text(json.dumps(derived,indent=2)+'\n')
(OUT/'slides_en.md').write_text('\n'.join(f'{i+1}. {s["title"]}' for i,s in enumerate(front+D.slides))+'\n\n'+(TAIL/'slides_en.md').read_text())
assert all(sha(p)==v for p,v in ledger.items())
(OUT/'validation.json').write_text(json.dumps({'slides':TOTAL,'approved_scientific_slides_preserved':24,'sensor_label_only_update_slides':[15],'PartIV':0,'new_raw_reads_in_builder':False,'raw_prefix_validation_separate':{'SPEC_per_run':8,'runs':[691,692,743,746,876,894,921,680,681,939]},'full_raw_runs_reconstructed':0,'new_simulations':False,'new_physical_fits':False,'normalization_unchanged':True,'input_sha256':ledger,'PSD_validation':result['validation']},indent=2)+'\n')
print('v47 exported:',TOTAL,'slides; prefixscience preserved;sensorlabelslide15updated;all260validated;noPartIV',flush=True)
