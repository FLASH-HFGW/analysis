"""Summarize the separate diagnostic; no original scientific product is written."""
from pathlib import Path
import csv,json,hashlib
import numpy as np,h5py
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import *
lt=json.loads((OUT/'longterm_summary.json').read_text());interval=json.loads((OUT/'interval_results.json').read_text());assert interval['status']=='complete'
rows=list(csv.DictReader((OUT/'longterm.csv').open()));corr=json.loads((OUT/'correlations.json').read_text())
# Heatmaps distinguish associations of levels from short-term increments.
fig,axs=plt.subplots(1,3,figsize=(14,8));names=[];mat=[]
for m in MODES:
 for dc in ['mean_I_ADC_V','mean_Qeff_ADC_V','DC_abs_ADC_V']:
  names.append(m+' '+{'mean_I_ADC_V':'I DC','mean_Qeff_ADC_V':'Qeff DC','DC_abs_ADC_V':'|DC|'}[dc]);mat.append([next(c for c in corr if c['mode']==m and c['x']==dc and c['y']==target) for target in ['AC2_ADC_V2','t15_mK','t16_mK','t17_mK']])
for ax,key,title in zip(axs,['pearson','after_time_degree_3','first_difference'],['Raw levels','After cubic time trend','Consecutive-run differences']):
 values=np.array([[v.get(key,np.nan) for v in line] for line in mat]);im=ax.imshow(values,vmin=-1,vmax=1,cmap='coolwarm',aspect='auto');ax.set(xticks=range(4),xticklabels=['AC²','T15','T16','T17'],yticks=range(len(names)),yticklabels=names,title=title)
 for i in range(len(names)):
  for j in range(4):ax.text(j,i,f'{values[i,j]:.2f}',ha='center',va='center',fontsize=8)
fig.colorbar(im,ax=axs.ravel().tolist(),label='Descriptive Pearson r',shrink=.7);fig.subplots_adjust(left=.12,right=.89,wspace=.6);fig.savefig(OUT/'correlation_controls.png',dpi=170);plt.close(fig)
# Across-mode components in same run; all data already produced.
features=[(m,k) for m in MODES for k in ['mean_I_ADC_V','mean_Qeff_ADC_V']];t=np.array([float(r['time_unix']) for r in rows if r['mode']==MODES[0]])
fig,axs=plt.subplots(1,3,figsize=(15,5))
for ax,key in zip(axs,['pearson','after_time_degree_3','first_difference']):
 vals=np.empty((6,6))
 for i,(m,k) in enumerate(features):
  for j,(mm,kk) in enumerate(features):
   a=[float(r[k]) for r in rows if r['mode']==m];b=[float(r[kk]) for r in rows if r['mode']==mm];vals[i,j]=association(a,b,t).get(key,np.nan)
 im=ax.imshow(vals,vmin=-1,vmax=1,cmap='coolwarm');labels=[m.replace('TM0','')+(' I' if k=='mean_I_ADC_V' else ' Qeff') for m,k in features];ax.set(xticks=range(6),yticks=range(6),xticklabels=labels,yticklabels=labels,title=key);ax.tick_params(axis='x',rotation=60)
fig.tight_layout();fig.savefig(OUT/'between_modes_DC_correlations.png',dpi=170);plt.close(fig)
# Full-run fixed-parameter Rice versus zero-offset Rayleigh from existing histograms.
fig,axs=plt.subplots(len(lt['selected_runs']),3,figsize=(14,3*len(lt['selected_runs'])));full_dist=[]
for ri,run in enumerate(lt['selected_runs']):
 with h5py.File(INPUT/f'run{run:05d}_noise_v2.h5') as h:
  for mi,m in enumerate(MODES):
   row=next(r for r in rows if int(r['run'])==run and r['mode']==m);fac=float(row['voltage_correction']);e=h['arrays/amplitude_edges_v'][:]*fac;counts=h[f'arrays/global_{m}_amp'][:];sigma=np.sqrt(float(row['AC2_ADC_V2'])/2);nu=float(row['DC_abs_ADC_V']);emp=np.cumsum(counts)/counts.sum();rice=stats.rice(b=nu/sigma,scale=sigma);ray=stats.rayleigh(scale=sigma)
   dr=emp-rice.cdf(e[1:]);dy=emp-ray.cdf(e[1:]);ax=axs[ri,mi];sel=e[1:]<6*sigma;ax.plot(e[1:][sel]/sigma,dr[sel],color=COLORS['data'],label='Empirical CDF - Rice');ax.plot(e[1:][sel]/sigma,dy[sel],color=COLORS['toy'],label='Empirical CDF - Rayleigh');ax.set(title=f'run{run} {m}',xlabel='A / measured sigma_q',ylabel='CDF residual');ax.grid(alpha=.2);ax.legend(fontsize=7)
   full_dist.append(dict(run=run,mode=m,nu_over_sigma=float(nu/sigma),Rice_CDF_distance=float(np.max(abs(dr))),Rayleigh_raw_CDF_distance=float(np.max(abs(dy)))))
fig.tight_layout();fig.savefig(OUT/'fullrun_fixed_distribution_residuals.png',dpi=160);plt.close(fig)
# Dependence on observed DC: only4runs, descriptive scatter, no causal fit.
fig,axs=plt.subplots(1,3,figsize=(14,4))
selected_shape=[]
for j,m in enumerate(MODES):
 for run,v in interval['runs'].items():
  rr=v[m];row=next(r for r in rows if int(r['run'])==int(run) and r['mode']==m)
  matches=[x for x in rr['shape']['metrics'] if x['quantity']=='complex_symmetric' and x['treatment']=='global' and x['nfft']==4*SPEC];q=matches[0];selected_shape.append(dict(run=int(run),mode=m,**q,DC_abs_ADC_V=float(row['DC_abs_ADC_V'])))
  width=q['full_half_deficit_width_hz']
  if width is not None:axs[j].scatter(float(row['DC_abs_ADC_V'])*1e3,width/1e3,color=COLORS['data']);axs[j].annotate(run,(float(row['DC_abs_ADC_V'])*1e3,width/1e3),fontsize=8)
 axs[j].set(title=m,xlabel='Full-run |DC| [mV ADC]',ylabel='Descriptive dip width [kHz]');axs[j].grid(alpha=.2)
fig.tight_layout();fig.savefig(OUT/'notch_width_vs_DC.png',dpi=170);plt.close(fig)
# Integration-time scaling and synthetic comparison, with no gain fitting.
scalings=[]
fig,axs=plt.subplots(1,2,figsize=(12,4.5))
for run,v in interval['runs'].items():
 for m,a in v.items():
  b=a['mean_stability'];tt=np.array([x['time_s'] for x in b]);vv=np.array([x['variance_means_v2'] for x in b]);slope=float(np.polyfit(np.log(tt[:3]),np.log(vv[:3]),1)[0]);scalings.append(dict(run=int(run),mode=m,short_time_log_slope=slope,time_range_s=[float(tt[0]),float(tt[2])]))
for label,a in interval['synthetic'].items():
 b=a['mean_stability'];tt=np.array([x['time_s'] for x in b]);vv=np.array([x['variance_means_v2'] for x in b]);col=COLORS['data'] if label.startswith('white') else COLORS['toy'];axs[0].loglog(tt,vv,'o-',color=col,label=label)
 axs[1].loglog(tt,[x['variance_means_v2']/x['white_prediction_v2'] for x in b],'o-',color=col,label=label)
axs[0].set(xlabel='Integration time [s]',ylabel='Variance of means [V² ADC]');axs[1].set(xlabel='Integration time [s]',ylabel='Variance / white AC²/N');
for ax in axs:ax.grid(alpha=.2);ax.legend(fontsize=7)
fig.tight_layout();fig.savefig(OUT/'synthetic_mean_stability.png',dpi=170);plt.close(fig)

# Zoom around the DC-containing display group, without another raw read.
fig,axs=plt.subplots(len(lt['selected_runs']),3,figsize=(14,3*len(lt['selected_runs'])))
for ri,run in enumerate(lt['selected_runs']):
 with np.load(OUT/f'run{run}_spectra.npz') as spectra:
  for mi,m in enumerate(MODES):
   prefix=f'run{run}_{m}';f=spectra[prefix+'_frequency_hz'];ax=axs[ri,mi]
   for treatment,color,style in [('none','#777777','-'),('global',COLORS['data'],'-'),('spec',COLORS['fit'],'--')]:
    power=spectra[prefix+'_'+treatment+'_complex_PSD'];norm=np.mean(power[(f>.5e6)&(f<1.5e6)]);ax.plot(f,10*np.log10(power/norm),color=color,ls=style,label=treatment)
   ax.set(title=f'run{run} {m}',xlim=(0,2000),xlabel='Frequency magnitude [Hz]',ylabel='PSD / plateau [dB]');ax.legend(fontsize=7);ax.grid(alpha=.2)
fig.suptitle('Low-frequency zoom: grouped display bins (~125 Hz); first group contains DC',fontsize=12)
fig.tight_layout();fig.savefig(OUT/'centering_low_frequency_zoom.png',dpi=170);plt.close(fig)

# Ensure original products were left untouched.
manifest=json.loads((OUT/'product_manifest.json').read_text())
for p in manifest:
 stat=Path(p['path']).stat();assert (stat.st_size,stat.st_mtime_ns)==(p['size'],p['mtime_ns'])
summary={'status':'complete','short_time_variance_scalings':scalings,'original_260_v2_files_unchanged_by_stat_check':True,'fullrun_distribution_checks':full_dist,'selected_notch_shape':selected_shape,'correlation_limit':'No p-values/causality; time residuals and differences are diagnostics, not independent instrumental identification','block_mean_PSD_limit':'Predictions marked unresolved when Welch df fails to resolve integration window; no long-T precision claimed'}
summary['source_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
(OUT/'diagnostic_summary.json').write_text(json.dumps(summary,indent=2))
lines=['# Step 7 — diagnostica DC long-term e depressione TM010','',
'260 prodotti v2 completi, run680–939, riutilizzati senza modifiche. Range ODB ±2 V; prodotti salvati a ±5 V: tensioni ×0.4 e quadrati ×0.16 una sola volta. Gain nominale143dB, distinto da calibrazione RF fisica.', '',
'## DC long-term','', '| Modo | Min–max DC [mV ADC] | Min–max DC²/AC² |','| --- | ---: | ---: |']
for m in MODES:
 a=[r for r in rows if r['mode']==m];dc=[float(x['DC_abs_ADC_V'])*1e3 for x in a];ratio=[float(x['DC2_over_AC2']) for x in a];lines.append(f'| {m} | {min(dc):.4f}–{max(dc):.4f} | {min(ratio):.3g}–{max(ratio):.3g} |')
lines+=['','## Correlazioni: esempio TM010','', '| Variabili | Livelli | Dopo trend cubico | Differenze consecutive |','| --- | ---: | ---: | ---: |']
for target in ['AC2_ADC_V2','t15_mK','t16_mK','t17_mK']:
 a=next(x for x in corr if x['mode']=='TM010' and x['x']=='DC_abs_ADC_V' and x['y']==target);lines.append(f"| DC vs {target} | {a['pearson']:.3f} | {a['after_time_degree_3']:.3f} | {a['first_difference']:.3f} |")
lines+=['','Le impostazioni LO BOR sono costanti; non è stimabile una loro correlazione con DC. Il guadagno nominale è costante e non costituisce un monitor del guadagno fisico. Le temperature T15/T16/T17 sono disponibili in tutti i run. Nessuna attribuzione causale.', '',
'## Verifiche raw limitate','',
'Primi16SPEC (3.3554432s) dei run '+', '.join(map(str,lt['selected_runs']))+'. FFT16384,262144,1048576,4194304 campioni; Hann, segmenti non sovrapposti. Nessun detrending automatico aggiuntivo. Trattamenti: nessuna media, media unica dell’intervallo, media per SPEC solo diagnostica.', '',
'| Run | Modo | Larghezza [kHz] | Profondità smussata [dB] | Centro deficit [Hz] | Cambiamento PSD con media SPEC, 1–100kHz |','| --- | --- | ---: | ---: | ---: | ---: |']
for q in selected_shape:
 v=interval['runs'][str(q['run'])][q['mode']]['shape'];width=q['full_half_deficit_width_hz'];center=q.get('deficit_centroid_hz');lines.append(f"| {q['run']} | {q['mode']} | {width/1000 if width else 'non risolta/assente'} | {q['depth_db']:.2f} | {center:.1f} | {v['relative_L1_PSD_change_1_100kHz']['spec']:.3g} |")
lines+=['','Il centro è un baricentro descrittivo del deficit entro±50kHz esclusi±500Hz; quando il notch è assente questa coordinata non ha significato fisico. La profondità è da annuli1kHz smussati su5bin: non il singolo minimo spettrale. Una riga DC può alterare i primi bin senza creare una depressione larga.', '',
'## Controlli sintetici','']
for name,v in interval['synthetic'].items():
 q=next(x for x in v['shape']['metrics'] if x['quantity']=='complex_symmetric' and x['treatment']=='global' and x['nfft']==4*SPEC);lines.append(f"- {name}: larghezza={q['full_half_deficit_width_hz']} Hz, profondità smussata={q['depth_db']:.2f}dB; variazione da centraggio SPEC sopra1kHz={v['shape']['relative_L1_PSD_change_1_100kHz']['spec']:.3g}.")
lines+=['','White proper gaussiano con offset costante; controllo separato con passa-alto causale primo ordine12.5kHz e stesso offset aggiunto dopo il filtro. Il cutoff è illustrativo, non misurato. Si applicano esattamente gli stessi stimatori.','',
'## Stabilità delle medie','',
'Le medie complesse sono calcolate su blocchi da128 a2097152campioni, con almeno8blocchi. Varianza delle medie confrontata sia con AC²/N sia con integrale della PSD Welch moltiplicata per la risposta quadratica del boxcar discreto. Il rumore colorato non deve seguire AC²/N. A tempi lunghi la PSD Welch non risolve la regione necessaria: i punti sono marcati e non sono previsioni affidabili. La misura su3.36s non identifica la stabilità intrarun sull’intero209.7s.','',
'## Rice e Rayleigh senza fit di guadagno o distribuzione','',
'Rice usa nu=|media| e sigma²=AC²/2 misurati. Gli istogrammi full-run precedenti alla sottrazione sono riutilizzati sui quattro run. La verifica dopo il centraggio usa i campioni dei brevi intervalli raw: Rayleigh con sigma misurato e log(CCDF) contro A²/AC² (previsione retta di pendenza−1). Anisotropia/covarianza I/Q, ADC, correlazioni temporali e derive impediscono di interpretare uno scarto CDF come un test iid.','',
'| Run | Modo | nu/sigma | Scarto CDF Rice full-run | Scarto CDF Rayleigh raw full-run |','| --- | --- | ---: | ---: | ---: |']
for q in full_dist:lines.append(f"| {q['run']} | {q['mode']} | {q['nu_over_sigma']:.4f} | {q['Rice_CDF_distance']:.4g} | {q['Rayleigh_raw_CDF_distance']:.4g} |")
lines+=['','## Integrità e limiti','',
'- Verificati size/mtime invariati dei260prodotti HDF5 iniziali; nessuna ricostruzione scientifica originale avviata.',
'- Dati, figure, CSV, JSON, NPZ e questo report generato restano fuori da Git. Solo sorgenti, test e README metodologico sono versionati.',
'- Metadati BOR sono snapshot delle impostazioni registrate, non prova del comportamento effettivo o di assenza di variazioni interne al run.',
'- Campione rappresentativo piccolo: le dipendenze fra larghezza e DC sono descrittive, non relazioni causali.',
'- La PSD non determina la posizione fisica del rumore nella catena; non identifica da sola il componente hardware responsabile.']
(OUT/'README.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
