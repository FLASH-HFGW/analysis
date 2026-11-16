"""Initial step8 report; no parameter optimization and no original-data writes."""
from pathlib import Path
import json,hashlib,sys
import numpy as np,h5py
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from model import LFModel,lf_power
SOURCE=Path(__file__).resolve();cfg=json.loads(SOURCE.with_name('parameters.json').read_text());O=Path(cfg['output']);r=json.loads((O/'metrics.json').read_text());assert r['status']=='complete' and not r['fit_LF_parameters']
model=LFModel(cfg);diag=json.loads((Path(cfg['DC_diagnostic'])/'interval_results.json').read_text());a=np.load(O/'expected_predictions.npz');colors={'data':'#007F86','toy':'#7657A6','theory':'#263952','fit':'#e36e18'};fs=cfg['fs_hz'];f=np.fft.ifftshift(a['frequency_hz']);p=2*np.pi*cfg['fc_hz'];analyses={}
fig,axs=plt.subplots(1,3,figsize=(15,5));fig2,ax2=plt.subplots(1,3,figsize=(15,4.5));fig3,ax3=plt.subplots(1,2,figsize=(12,4.5))
for j,(mode,v) in enumerate(r['modes'].items()):
 tt=np.array(v['integration_times_s']);modelvar=np.array(v['mean_variance_finite_record_population_V2']);power=v['predicted_AC2_ADC_V2']
 for run,runv in diag['runs'].items():
  d=runv[mode];var=np.array([q['variance_means_v2'] for q in d['mean_stability']]);ac=d['distribution']['AC2_ADC_V2'];axs[j].loglog(tt,var/ac,'o-',ms=3,lw=.7,label='Data '+run,alpha=.7)
 axs[j].loglog(tt,modelvar/power,'--',lw=1.7,color=colors['toy'],label='Initial model / own AC²');axs[j].set(title=mode,xlabel='Integration time [s]',ylabel='Variance of means / AC²');axs[j].grid(alpha=.2);axs[j].legend(fontsize=7)
 d=np.load(Path(cfg['reference_toy'])/'comparison'/f'{mode}_comparison.npz');lag=d['lag_s'];S=np.fft.ifftshift(a[mode+'_PSD']);base=model.sampled(mode,f,interpretation='no_LF');full=np.fft.ifft(S);full/=full[0].real;diff=np.fft.ifft(S-base)*fs/power
 ax2[j].plot(lag*1e6,d['data_g1'].real,color=colors['data'],label='Data Re g1');ax2[j].plot(np.arange(501)/fs*1e6,full[:501].real,color=colors['toy'],label='Model Re g1');ax2[j].plot(np.arange(501)/fs*1e6,diff[:501].real,color=colors['fit'],ls='--',label='LF covariance deficit / total variance');ax2[j].set(title=mode,xlabel='Lag [us]',ylabel='Normalized covariance',xlim=(2,100),ylim=(-.015,.004));ax2[j].grid(alpha=.2);ax2[j].legend(fontsize=6)
 t=a[mode+'_integration_time_s'];slope=a[mode+'_local_log_slope'];mask=(t>1e-4)&(t<1e-2);cross=float(t[mask][np.argmin(abs(slope[mask]+1.5))])
 analyses[mode]=dict(full_response_slope_minus1p5_time_s=cross if mode=='TM010' else None,mean_variance_normalized_model_over_data_at_longest_T=float((modelvar[-1]/power)/(v['data_mean_variance_V2'][-1]/diag['runs']['680'][mode]['distribution']['AC2_ADC_V2'])),LF_covariance_tau_s=1/p,MC_power_fraction_errors={k:x['AC2_ADC_V2']/x['expected_AC2_ADC_V2']-1 for k,x in v['MC'].items()})
# Contrast calibration double counting directly; no amplitude matching.
mode='TM010';x=np.linspace(-100e3,100e3,4001);base=model.sampled(mode,x,interpretation='no_LF');s=model.sampled(mode,x);wrong=model.sampled(mode,x,interpretation='double_counting_control')
for values,label,c in [(s,'Replace calibration LF (initial hypothesis)',colors['toy']),(wrong,'Incorrect multiplication of old kz by new LF',colors['fit'])]:ax3[0].plot(x/1e3,values,label=label,color=c)
ax3[0].set(xlabel='Final IF [kHz]',ylabel='Absolute PSD [V² ADC/Hz]',title='TM010: avoid applying the notch twice');ax3[0].legend(fontsize=7)
ax3[1].plot(x/1e3,lf_power(x,cfg['fc_hz'],cfg['epsilon']),color=colors['toy'],label='Finite-DC shelf');ax3[1].plot(x/1e3,(1-cfg['epsilon'])*lf_power(x,cfg['fc_hz'],0)+cfg['epsilon'],color=colors['fit'],ls='--',label='Weighted HP + independent floor');ax3[1].set(xlabel='Primary IF [kHz]',ylabel='S/S0',title='Exactly equal spectra; not identifiable from Gaussian noise');ax3[1].legend(fontsize=7)
for fg,name in [(fig,'normalized_mean_variance_all_selected_runs'),(fig2,'negative_covariance_tail'),(fig3,'interpretations_and_double_counting')]:
 for ax in fg.axes:ax.grid(alpha=.2)
 fg.tight_layout();fg.savefig(O/(name+'.png'),dpi=180);plt.close(fg)
# Compare measured full-run raw amplitude distribution in fixed ADC units.
manifest=json.loads((Path(cfg['DC_diagnostic'])/'product_manifest.json').read_text());datafile=next(Path(x['path']) for x in manifest if x['path'].endswith('run00680_noise_v2.h5'))
longterm=list(__import__('csv').DictReader((Path(cfg['DC_diagnostic'])/'longterm.csv').open()));amplitude_checks={}
fig,axs=plt.subplots(3,2,figsize=(12,10))
from scipy import stats
with h5py.File(datafile) as h:
 for j,(mode,v) in enumerate(r['modes'].items()):
  row=next(x for x in longterm if int(x['run'])==680 and x['mode']==mode);fac=float(row['voltage_correction']);edges=h['arrays/amplitude_edges_v'][:]*fac;counts=h[f'arrays/global_{mode}_amp'][:];centers=(edges[:-1]+edges[1:])/2;nu=float(row['DC_abs_ADC_V']);sigma=np.sqrt(v['predicted_AC2_ADC_V2']/2);sdata=np.sqrt(float(row['AC2_ADC_V2'])/2)
  expected=stats.rice(b=nu/sigma,scale=sigma);measured_moments=stats.rice(b=nu/sdata,scale=sdata);cdf=np.cumsum(counts)/counts.sum();visible=edges[1:]<6*sdata
  amplitude_checks[mode]=dict(raw_data_vs_initial_model_Rice_CDF_distance=float(np.max(abs(cdf-expected.cdf(edges[1:])))),raw_data_vs_measured_moment_Rice_CDF_distance=float(np.max(abs(cdf-measured_moments.cdf(edges[1:])))))
  axs[j,0].stairs(counts/counts.sum()/np.diff(edges)/1000,edges*1000,color=colors['data'],label='Data raw amplitude');xx=np.linspace(0,6*sdata,800);axs[j,0].plot(xx*1000,expected.pdf(xx)/1000,color=colors['toy'],label='Initial model Rice; fixed ADC normalization');axs[j,0].set(title=mode,xlabel='Amplitude [mV ADC]',ylabel='Density [1/mV]',xlim=(0,6*sdata*1000));axs[j,0].legend(fontsize=7)
  axs[j,1].plot(edges[1:][visible]*1000,(cdf-expected.cdf(edges[1:]))[visible],color=colors['toy'],label='Data CDF - initial-model Rice');axs[j,1].plot(edges[1:][visible]*1000,(cdf-measured_moments.cdf(edges[1:]))[visible],color=colors['data'],label='Data CDF - measured-moment Rice (shape only)');axs[j,1].set(title=mode,xlabel='Amplitude [mV ADC]',ylabel='CDF residual');axs[j,1].legend(fontsize=7)
fig.tight_layout();fig.savefig(O/'fixed_normalization_amplitude_vs_data.png',dpi=170);plt.close(fig)

summary={'status':'complete','initial_only':True,'fc_hz':cfg['fc_hz'],'epsilon':cfg['epsilon'],'ideal_crossover_s':r['ideal_crossover_s'],'LF_covariance_tau_s':1/p,'mode_checks':analyses,'amplitude_checks':amplitude_checks,'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.parent.glob('*.py')}}
(O/'summary.json').write_text(json.dumps(summary,indent=2))
lines=['# Step 8 — previsione iniziale della soppressione LF','',
'fc=12.5kHz, epsilon=0.02 fissati; nessun fit LF, nessun adattamento di guadagno. Risposta finale LPF/mixer contenuta nell’inviluppo misurato; LF applicata alla IF primaria prima della conversione finale e del ripiegamento alias.','',
'## Risultati simultanei','', '| Modo | Larghezza modello/dati [kHz] | Profondità smussata modello/dati [dB] | RMS modello/dati full-run [mV ADC] | Pendenza varianza breve modello/dati |','| --- | --- | --- | --- | --- |']
for m,v in r['modes'].items():
 w=v['shape_metrics']['full_half_deficit_width_hz'];wd=v['data_shape_metrics']['full_half_deficit_width_hz'];width=f'{w/1000:g}/{wd/1000:g}' if w and wd else 'nessun notch risolto'
 lines.append(f"| {m} | {width} | {v['shape_metrics']['depth_db']:.2f}/{v['data_shape_metrics']['depth_db']:.2f} | {v['predicted_RMS_ADC_V']*1000:.3f}/{v['data_fullrun_RMS_ADC_V']*1000:.3f} | {v['variance_short_time_log_slope']:.3f}/{v['data_variance_short_time_log_slope']:.3f} |")
lines+=['','Le profondità negative dei modi senza notch indicano una lieve eccedenza rispetto al plateau, non una depressione. Larghezza/profondità sono gli stessi descrittori smussati usati nello step7; epsilon non è deducibile direttamente dalla profondità smussata.','',
'## Correlazione complessa','', '| Modo | Min Re g1 modello/dati, 0.2–10us | RMSE complessa | Tau dei massimi modello/dati [us] |','| --- | --- | --- | --- |']
for m,v in r['modes'].items():lines.append(f"| {m} | {v['real_g1_min_0p2_10us']:.5f}/{v['data_real_g1_min_0p2_10us']:.5f} | {v['complex_g1_RMSE_0p2_10us']:.5f} | {v['expected_upper_fit']['tau_us']:.3f}/{v['data_upper_fit']['tau_us']:.3f} |")
lines+=['','Il modello produce la componente negativa LF. Il suo polo ha tempo12.732us; il fit descrittivo dei massimi su0.3–4us misura un’altra caratteristica della risposta totale. La parte immaginaria, soprattutto TM011, non è riprodotta completamente dal modello scalare.','',
'## Transizione delle medie','',f"Transizione ideale a {r['ideal_crossover_s']*1000:.4f}ms. Con risposta completa TM010, pendenza locale circa−1.5 a {analyses['TM010']['full_response_slope_minus1p5_time_s']*1000:.4f}ms. A tempi lunghi la previsione tende a T^-1; con epsilon=0 il controllo ideale resta T^-2.", '',
'La previsione analitica con risposta campionata risolve il limite della griglia Welch dello step7: integrazione adattata al boxcar discreto, oscillazioni iniziali risolte e coda mediata; verifica raddoppiando il limite di coda. La previsione della varianza di popolazione finita sottrae V(durata record).','',
'La transizione è presente nel modello, ma non descrive tutto il comportamento misurato: a0.419s la varianza TM010 prevista è circa '+f"{1/analyses['TM010']['mean_variance_normalized_model_over_data_at_longest_T']:.1f} volte inferiore ai dati anche dopo confronto V/AC². Sono necessarie altre componenti lente o non stazionarietà; non si inventa una correzione qui.", '',
'## Due interpretazioni','',
'F = epsilon+(1-epsilon)*f²/(f²+fc²). Shelf causale H=(i*f+sqrt(epsilon)*fc)/(i*f+fc) oppure somma di due sorgenti gaussiane indipendenti con PSD(1-epsilon)*Sbase*HP e epsilon*Sbase. Due Monte Carlo indipendenti di16SPEC per modo verificano potenza, correlazione, medie e distribuzioni; le fluttuazioni non sono un ensemble di incertezze. Le due costruzioni hanno identica PSD e tutte le statistiche gaussiane corrispondenti: non sono identificabili da questi osservabili.', '',
'La seconda lettura richiede una sorgente equivalente con la stessa risposta successiva del baseline; non è rumore bianco aggiunto dopo ADC/LPF. L’equivalenza esatta del totale comprende anche il piccolo contributo di cavità: una modellazione microscopica deve separarlo. Nel regime dominato dal ricevitore il pavimento corrisponde a rumore equivalente aggiunto dopo LF e prima della risposta successiva.','',
'## Distribuzioni a normalizzazione fissa','',str(amplitude_checks),'','La legge gaussiana propria del modello produce Rice con offset e Rayleigh dopo centraggio; ma la scala assoluta delle ampiezze non coincide con i dati. Il riferimento Rice con i momenti misurati verifica solo la forma e non viene adottato per correggere il modello.','', '## Calibrazione e normalizzazione','',
'Fattorizzazione condizionale TM010: kz_cal = kz_envelope*sqrt(Fcal). Dentro±300kHz l’envelope interpola linearmente le spalle; fuori coincide con la curva misurata. Il modello dati sostituisce Fcal con Fdata; moltiplicare semplicemente kz_cal per sqrt(Fdata) conterebbe due volte la depressione. Controlli±200 e±500kHz documentano la non unicità della fattorizzazione, senza selezionare un valore migliore dai dati.','',
'LPF finale già incluso in kz_envelope: nessuna seconda moltiplicazione Butterworth. Guadagno RF103.4dB, rapporto LF0.01, Tn3.955K, scale ADC±5V calibrazione/±2V dati invariati. Nessun fattore correttivo ai dati o al modello. Le potenze assolute restano diverse.','',
'## Limiti e riproducibilità','',
'- I valori iniziali danno circa27kHz contro25kHz e15.1dB smussati contro17.6dB nel TM010: miglioramento della forma, non accordo simultaneo completo.',
'- La profondità centrale puntuale osservata è maggiore della previsione epsilon=0.02; il suo valore esatto risente anche dell’estimatore e delle fluttuazioni.',
'- Il tempo dei massimi TM010 dipende dal baseline di calibrazione: i controlli sulle spalle danno valori diversi; non è una misura univoca del polo LF.',
'- Il modello resta scalare, proprio/gaussiano e stazionario: non include la covarianza I/Q o le derive lente misurate.',
'- La parte immaginaria della correlazione può evidenziare l’inadeguatezza della risposta al tono come risposta del rumore.',
'- Nessun raw misurato riletto: si riusano i prodotti dei precedenti step; nessun risultato precedente viene scritto.',
'- Tutti i prodotti numerici e le figure restano fuori da Git. Il README sorgente descrive formule, ipotesi, controlli e risultati.']
(O/'README.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
