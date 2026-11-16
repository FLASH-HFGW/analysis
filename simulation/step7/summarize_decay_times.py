"""Tabulate matched decay fits and show window dependence (products outside Git)."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path('/home/mazzitel/HFGW/analysis-work/Run2/simulation/step7/decay_times')
r=json.loads((R/'fit_results.json').read_text());lines=['# Step 7: confronto dei tempi','',
'Fit originale sui massimi superiori di Re(g1), C+A exp(-t/tau), 0.3–4 us. Tutti i tempi in microsecondi.',
'La previsione attesa e il MC a 5 SPEC sono distinti. Una singola realizzazione non misura una incertezza.', '',
'| Modo | Cavità | Run 680 | Toy originale atteso | alpha=0.5 atteso | alpha=0.25 atteso | alpha=0.1 atteso | alpha=0.1 MC 5 SPEC |',
'| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
fig,axs=plt.subplots(1,3,figsize=(14,4.5))
for ax,(mode,v) in zip(axs,r['modes'].items()):
 def tau(x):return x['primary_0p3_4']['tau_us']
 variants=v['variants'];values=[v['cavity_amplitude_tau_us'],tau(v['data'])]+[tau(variants[f'alpha_{a:g}']['expected']) for a in [1,.5,.25,.1]]+[tau(variants['alpha_0.1']['five_SPEC_MC'])]
 cells=[f'{x:.3f}' for x in values]
 if mode=='TM010':cells[2]='non descrittivo (R²=0.343)'
 lines.append('| '+mode+' | '+' | '.join(cells)+' |')
 for label,fs,color in [('Run 680',v['data'],'black'),('Original expected',variants['alpha_1']['expected'],'#007F86'),('alpha=0.1 expected',variants['alpha_0.1']['expected'],'#D98726')]:
  ax.plot(range(4),[f['tau_us'] for f in fs.values()],'o-',label=label,color=color)
 ax.axhline(v['cavity_amplitude_tau_us'],color='gray',ls='--',label='Cavity only')
 ax.set(title=mode,ylabel='Fitted tau [us]',xticks=range(4),xticklabels=['0.3–4','0.3–3','0.3–5','0.7–4'],xlabel='Fit interval [us]');ax.legend(fontsize=8);ax.grid(alpha=.2)
lines += ['', '## Sensibilità alla finestra','', '| Modo | Run 680: min–max | alpha=0.1 atteso: min–max |','| --- | ---: | ---: |']
for mode,v in r['modes'].items():
 spans=[]
 for fs in [v['data'],v['variants']['alpha_0.1']['expected']]:
  ts=[f['tau_us'] for f in fs.values()];spans.append(f'{min(ts):.3f}–{max(ts):.3f}')
 lines.append('| '+mode+' | '+' | '.join(spans)+' |')
lines += ['', 'Questi intervalli descrivono la dipendenza dalla scelta della finestra, non barre di errore.', '',
'## Interpretazione', '',
'- Il toy originale TM010 non ha un inviluppo esponenziale adeguato nella finestra: il valore numerico ~0.034 us non è un tempo di decadimento fisico interpretabile.',
'- La contrazione della depressione migliora la struttura temporale del TM010 senza riscalare i guadagni. Tuttavia alpha=0.1 (larghezza vicina ai dati) dà un tempo atteso maggiore del dato; alpha=0.5 avvicina il tempo ma lascia la depressione troppo larga. Non è un accordo simultaneo.',
'- La realizzazione a 5 SPEC verifica lo stimatore, con rumore e ADC. Non selezionare una variante sulla base della sola fluttuazione favorevole del suo tau MC.',
'- I tempi di TM011/012 sono simili ai dati nella finestra primaria, ma entrambi mostrano una marcata dipendenza dalla finestra, anche nella previsione priva di fluttuazioni: il singolo esponenziale è una descrizione approssimata della risposta totale.',
'- Il tempo QL/(pi*f0) riguarda la sola cavità. Il ricevitore domina la potenza di questo toy: la somiglianza numerica non dimostra che il fit misuri il tempo intrinseco della cavità.',
'- Nessuna modifica all’analisi originale del run 680; nessun nuovo modello di rumore introdotto.']
(R/'decay_times_summary.md').write_text('\n'.join(lines)+'\n')
fig.tight_layout();fig.savefig(R/'fit_window_sensitivity.png',dpi=180);plt.close(fig)
print('\n'.join(lines))
