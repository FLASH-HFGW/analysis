"""Freeze v47.1: targeted wording/layout changes, two primary-v2 figures, explicit provenance."""
from pathlib import Path
import json,csv,copy,hashlib,shutil,sys,io
import numpy as np,h5py
from scipy.stats import spearmanr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
sys.path[:0]=['/tmp/v18-python-deps','/tmp/v46-pdf-deps']
from pptx import Presentation
from pptx.dml.color import RGBColor
from pypdf import PdfReader,PdfWriter
R=Path(__file__).resolve().parents[2];W=R.parent/'analysis-work/Run2';BASE=W/'reports/iq_noise_summary_v47';OUT=BASE.with_name('iq_noise_summary_v47_1');OUT.mkdir(exist_ok=True);A=OUT/'assets';A.mkdir(exist_ok=True);D=OUT/'data';D.mkdir(exist_ok=True)
sys.path.insert(0,str(R/'reporting'));import slide_deck as sd
M=['TM010','TM011','TM012'];TEAL='#007F86';NAVY='#263952';SHORT=['Cavity (T15) [mK]','MC-CMN143 (T16) [mK]','MC-CMN130 (T17) [mK]']
def rows(p):
 with open(p) as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
ledger={}
def track(p):p=Path(p);ledger[str(p)]=sha(p);return p
track(__file__);track(BASE/'slide_model.json');track(BASE/'iq_noise_summary_v47.pdf');track(BASE/'iq_noise_summary_v47.pptx')
full=rows(track(BASE/'data/fullband_v2.csv'));raw=rows(track(BASE/'data/raw_statistics_v2.csv'));F={m:[x for x in full if x['mode']==m] for m in M};T={m:[x for x in raw if x['mode']==m] for m in M}
col=lambda a,k:np.array([float(x[k]) for x in a]);clock=col(F[M[0]],'time_unix');time=(clock-clock[0])/3600;norm=Normalize(time.min(),time.max());design=np.column_stack([np.ones(260),(time-time.mean())/time.std()]);resid=lambda x:x-design@np.linalg.lstsq(design,x,rcond=None)[0]
model=copy.deepcopy(json.loads((BASE/'slide_model.json').read_text()));changed={26,28,31,42,46,48,49,50,53,34,43};validation={'numeric_checks':{},'modified_slides':sorted(changed)}
plt.rcParams.update({'font.size':8,'axes.titlesize':9,'axes.labelsize':8,'xtick.labelsize':7,'ytick.labelsize':7,'axes.grid':True,'grid.alpha':.18,'lines.linewidth':.9})
def save(fig,name):p=A/(name+'.png');fig.savefig(p,dpi=200,facecolor='white');fig.savefig(p.with_suffix('.pdf'));plt.close(fig);return p
def image(n,p):
 s=model[n-1];old=next(x for x in s['items'] if x['kind']=='image');x,y,w,h=(old[k] for k in ['x','y','w','h']);s['items'].remove(old);sd.Deck().image(s,x,y,w,h,p)
def replace(n,contains,text,size=None):
 it=next(x for x in model[n-1]['items'] if x['kind']=='text' and contains in x['text']);it['text']=sd.wrap(text,it['w'],size or it['size']);it['size']=size or it['size']
def caption(n,text,size=11):
 s=model[n-1];it=next((x for x in s['items'] if x['kind']=='text' and abs(x['y']-6.37)<.02),None)
 if it:it.update(text=sd.wrap(text,it['w'],size),size=size,h=.62)
 else:sd.Deck().text(s,.65,6.32,12.05,.65,text,size)
# Three temperature scatter figures; independently allocated colorbar and wider row spacing.
with h5py.File(track(W/'diagnostics/resonance_campaign_primary_v47_20261117/expectations_and_campaign.h5')) as h:
 resonance={m:h[m+'/power_ADC_V2'][:,3] for m in M}
for slide,kind,name in [(31,'full','fullband_temperature'),(42,'resonance','resonance_temperature'),(50,'residual','appendix_temperature_clock_residuals')]:
 fig,axs=plt.subplots(3,3,figsize=(13.4,6.5));fig.subplots_adjust(left=.075,right=.89,bottom=.11,top=.94,hspace=.8,wspace=.55)
 for i,m in enumerate(M):
  power=(resonance[m] if kind=='resonance' else col(F[m],'AC2_ADC_V2'))*1e6
  for j,sensor in enumerate([15,16,17]):
   x=col(F[m],f't{sensor}_mK');y=power
   if kind=='residual':x=resid(x);y=resid(y)
   ax=axs[i,j];ax.scatter(x,y,c=time,cmap='viridis',norm=norm,s=8,alpha=.8,rasterized=True);ax.set(title=m,xlabel=SHORT[j],ylabel=('Residual ' if kind=='residual' else '')+('Band power' if kind=='resonance' else 'AC²')+' [mV² ADC]');ax.text(.03,.97,f'r={np.corrcoef(x,y)[0,1]:+.3f}; ρ={spearmanr(x,y).statistic:+.3f}',transform=ax.transAxes,va='top',fontsize=7,bbox={'facecolor':'white','edgecolor':'none','alpha':.8})
 cb=fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap='viridis'),cax=fig.add_axes([.925,.16,.012,.67]));cb.set_label('Campaign clock [h]');image(slide,save(fig,name))
# Direct primary-v2 DC figure: recompute derived phase/magnitude/ratios from complex moments.
fig,axs=plt.subplots(3,4,figsize=(13.4,5.7));fig.subplots_adjust(left=.065,right=.97,bottom=.13,top=.94,hspace=.65,wspace=.65);dc_checks=[]
legacy_dc={(int(x['run']),x['mode']):x for x in rows(track(W/'simulation/step7/dc_longterm_diagnostic/longterm.csv'))}
for i,m in enumerate(M):
 f=F[m];re=col(f,'mean_I_ADC_V');im=col(f,'mean_Qeff_ADC_V');z=re+1j*im;dc=abs(z)**2;ac=col(f,'AC2_ADC_V2');total=col(f,'total2_ADC_V2');phase=np.angle(z);ratio=dc/ac
 for k,val in [('mean_I_ADC_V',re),('mean_Qeff_ADC_V',im),('DC_abs_ADC_V',abs(z)),('DC_phase_rad',phase),('DC2_ADC_V2',dc),('AC2_ADC_V2',ac),('total2_ADC_V2',total),('DC2_over_AC2',ratio)]:
  ref=np.array([float(legacy_dc[(int(x['run']),m)][k]) for x in f]);error=np.max(abs(val-ref));assert np.allclose(val,ref,rtol=3e-12,atol=1e-15),(m,k,error);dc_checks.append(dict(mode=m,observable=k,max_abs_error=float(error)))
 ax=axs[i,0];ax.plot(time,re*1000,color=TEAL,label='mean I');ax.plot(time,im*1000,'--',color=TEAL,label='mean Qeff');ax.set(title=m+' — complex mean',ylabel='DC [mV ADC]');ax.legend(ncol=2,fontsize=6)
 ax=axs[i,1];ax.plot(time,abs(z)*1000,color=TEAL);ax.set(title='DC magnitude / phase',ylabel='|μ| [mV ADC]');other=ax.twinx();other.plot(time,phase,':',color=TEAL,alpha=.75);other.set_ylabel('arg(μ) [rad]',fontsize=7);other.tick_params(labelsize=6)
 for val,label,ls in [(dc,'DC²',':'),(ac,'AC²','--'),(total,'Total²','-')]:axs[i,2].semilogy(time,val,color=TEAL,ls=ls,label=label)
 axs[i,2].set(title='Squared-voltage decomposition',ylabel='Mean square [V² ADC]');axs[i,2].legend(ncol=3,fontsize=5.5);axs[i,3].plot(time,ratio,color=TEAL);axs[i,3].set(title='DC relative to AC',ylabel='DC² / AC²')
for ax in axs[-1]:ax.set_xlabel('Campaign clock [h]')
image(46,save(fig,'primary_v2_campaign_DC_AC'));validation['numeric_checks']['slide46']=dc_checks
# Direct v2 probabilities; thresholds are read, never refitted/recomputed.
legacy_raw={(int(x['run'].replace('run','')),x['mode']):x for x in rows(track(W/'staging/gpfs_noise_v0_20261108/originals/noise_global/runs.csv'))};probchecks=[]
fig,axs=plt.subplots(3,3,figsize=(13.4,6));fig.subplots_adjust(left=.07,right=.97,bottom=.12,top=.94,hspace=.65,wspace=.4)
for i,k in enumerate([3,5,7]):
 for j,m in enumerate(M):
  rr=T[m];mu=col(rr,'mean_amplitude_v');std=col(rr,'amplitude_noise_rms_v');s2=(mu**2+std**2)/2;ax=axs[i,j]
  for pop,ls in [('local','-'),('reference','--')]:
   fraction=col(rr,f'{pop}_{k}sigma_fraction');th=col(rr,f'{pop}_{k}sigma_threshold_v');pred=np.exp(-th**2/(2*s2));old=[legacy_raw[(int(x['run'].replace('run','')),m)] for x in rr];oldth=col(old,f'{pop}_{k}sigma_threshold_v')*.4;oldrate=col(old,f'{pop}_{k}sigma_fraction');olds2=(col(old,'mean_amplitude_v')**2+col(old,'amplitude_noise_rms_v')**2)/2;oldpred=np.exp(-col(old,f'{pop}_{k}sigma_threshold_v')**2/(2*olds2))
   assert np.array_equal(fraction,oldrate);assert np.allclose(th,oldth,rtol=2e-14,atol=1e-15);assert np.allclose(pred,oldpred,rtol=2e-13,atol=1e-20)
   probchecks.append(dict(mode=m,k=k,population=pop,max_fraction_difference=float(np.max(abs(fraction-oldrate))),max_threshold_ADC_V_difference=float(np.max(abs(th-oldth))),max_Rayleigh_probability_difference=float(np.max(abs(pred-oldpred)))))
   ax.semilogy(time,fraction,color=TEAL,ls=ls,label='Data '+pop);ax.semilogy(time,pred,color=NAVY,ls=ls,alpha=.75,label='Rayleigh '+pop)
  ax.set(title=f'{m} — k={k}',xlabel='Campaign clock [h]',ylabel='P(A > threshold)');ax.legend(ncol=2,fontsize=5)
image(48,save(fig,'primary_v2_local_fixed_probabilities'));validation['numeric_checks']['slide48']=probchecks
# Requested scientific wording and explicit population qualifiers.
replace(26,'The discrepancy concerns','Even around resonance, cavity thermal noise accounts for only 2.4–3.2 ppm of the predicted total noise power.')
caption(28,'PSD: full run (209.7152 s). Measured g1: initial 1.048576 s only. FIR scale ≈20 µs dominates cavity decay ≈1 µs; filtered lag samples are 4 µs apart.',10.5)
replace(53,'Each listed sensor has','Each listed sensor has 260 valid run medians and 10–11 observed readings per run, within the acquisition interval defined by the SPEC timestamps. The zero Mercury MC-diode channel is excluded.',12)
replace(49,'Resonance central/side power ratios','Resonance central/side ratios span 0.24–0.33%. Interpret these per-mille changes with the residual PSD–FIR estimator mismatch (≤0.108% power) in mind; this is not a calibrated uncertainty floor.',14)
replace(49,'Mode noise powers are strongly correlated','Run-level mode noise powers co-vary strongly. Full-band, electronic and resonance regions share similar level evolution; instantaneous I/Q cross-mode correlations and coherence were not measured.',14)
for n in [34,43]:caption(n,'These are correlations between run-level noise powers. Instantaneous cross-mode I/Q correlations and signal coherence were not measured.',10.5)
for n in [34,43,49]:model[n-1]['notes']+=' v47.1: all inter-mode correlations here concern run-level noise-power summaries, not instantaneous I/Q correlations or signal coherence.'
model[45]['source']='Primary v2 fullband_v2.csv: complex means, DC², AC², total²; derived DC phase and ratios.';model[47]['source']='Primary v2 raw_statistics_v2.csv: unchanged stored local/fixed thresholds, empirical sample fractions and amplitude moments.'
for n in [46,48]:model[n-1]['notes']+=' v47.1: figure regenerated directly from primary v2 tables; numerical reproduction validated without changing thresholds or estimators.'
# Only changed pages are rendered; other PDF pages and native PPTX slides remain untouched.
patch=sd.Deck();ordered=sorted(changed)
for n in ordered:
 model[n-1]['footer']=model[n-1].get('footer','FLASH | v47').replace('v47','v47.1');patch.slides.append(model[n-1])
sd.export(patch,OUT/'changed_pages','v47_1_changes','17 November 2026')
# Correct visible page numbers for each patch, in both PDF and native PPTX, without science changes.
# Export each updated page separately with its original ordinal.
for n in ordered:
 one=sd.Deck();one.slides=[model[n-1]];sd.export(one,OUT/f'page_{n:02d}','v47_1_page','17 November 2026',page_offset=n-1,total_pages=53)
writer=PdfWriter();reader=PdfReader(BASE/'iq_noise_summary_v47.pdf');readers={n:PdfReader(OUT/f'page_{n:02d}/iq_noise_summary_v47_1_page.pdf') for n in ordered}
for i,p in enumerate(reader.pages,1):writer.add_page(readers[i].pages[0] if i in changed else p)
with (OUT/'iq_noise_summary_v47_1.pdf').open('wb') as f:writer.write(f)
prs=Presentation(BASE/'iq_noise_summary_v47.pptx');RNS='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
for n in ordered:
 src=Presentation(OUT/f'page_{n:02d}/iq_noise_summary_v47_1_page.pptx').slides[0];dst=prs.slides[n-1]
 for shape in list(dst.shapes):dst.shapes._spTree.remove(shape.element)
 for shape in src.shapes:
  el=copy.deepcopy(shape.element)
  for node in el.iter():
   old=node.get(RNS+'embed')
   if old:
    rel=src.part.rels[old];assert rel.reltype.endswith('/image');_,new=dst.part.get_or_add_image_part(io.BytesIO(rel.target_part.blob));node.set(RNS+'embed',new)
  dst.shapes._spTree.insert_element_before(el,'p:extLst')
 dst.notes_slide.notes_text_frame.text=model[n-1]['notes']
prs.save(OUT/'iq_noise_summary_v47_1.pptx')
for n in range(1,54):shutil.copy2(OUT/f'page_{n:02d}/slide_01.png' if n in changed else BASE/f'slide_{n:02d}.png',OUT/f'slide_{n:02d}.png')
# Assets of unchanged slides remain immutable explicit references to approved v47.
(OUT/'slide_model.json').write_text(json.dumps(model,indent=2));(OUT/'input_sha256.json').write_text(json.dumps(ledger,indent=2));validation.update(slides=53,no_raw_reads=True,no_simulations=True,no_new_fits=True,model_parameters_changed=False,unchanged_PPTX_slide_XML_exact=all(prs.slides[n-1].element.xml==Presentation(BASE/'iq_noise_summary_v47.pptx').slides[n-1].element.xml for n in range(1,54) if n not in changed));assert validation['unchanged_PPTX_slide_XML_exact']
(OUT/'validation.json').write_text(json.dumps(validation,indent=2));print('v47.1 exported; unchanged native slides verified; numeric checks passed',flush=True)
