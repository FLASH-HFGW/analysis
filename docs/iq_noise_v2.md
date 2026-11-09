# IQ noise v2: DC, guadagno nominale e trend comuni

## Preparazione della produzione massiva

Il piano è registrato in [noise_v2_production_plan.json](../config/noise_v2_production_plan.json).
Su richiesta esplicita dell'utente del 9 novembre, la produzione HTC v2 è
stata accodata prima della correzione dell'affinità: 248 nuovi job, priorità
`-10`, con i 12 run HPC riservati al riuso. La priorità inferiore lascia la v1
avanti nell'ordinamento dello stesso utente. Il limite 248 conta anche i job
in attesa: non dichiara 248 CPU fisiche disponibili. La correzione CPU rimane
pendente e il limite operativo efficiente resta da misurare.

Il 9 novembre sei job diagnostici (3192–3197) hanno osservato, su due host
fisici, sette e tre analisi pronte a calcolare ma tutte vincolate alla CPU 0.
I probe assegnati dallo scheduler alla CPU 1 hanno ricevuto circa il 98% di CPU.
I 95 nomi `offload-*` identificano ambienti contenitore, non dimostrano la
disponibilità di 95 nodi fisici indipendenti. Non sono state cambiate affinità
dei processi di produzione né impostazioni della facility.

Per correggere l'efficienza della produzione v2 si deve coordinare l'assegnazione CPU fra
contenitori esterni e scheduler interno, rispettando i core fisici allocati.
Si verificano poi su più host: affinità, rapporto CPU/wall di un carico CPU-bound,
tempi di un run completo, memoria, download e pubblicazione verificata.
Solo dopo si sceglie il limite operativo e si aumenta la concorrenza per gradi.
Spostare tutti i job sulla CPU 1 riprodurrebbe la stessa contesa.

Le prove complete sono conservate nell'area runtime esterna a Git:
`noise_cpu_diagnostic_20261109/diagnosis.md`, `summary.json` e i `diagnostic.json`.

La campagna è `noise_fullrange_v2_20261109`, intervallo 680–939. Il controller
usa `--reuse-directory` e `--reuse-runs` per aspettare e importare i dodici run
del pilot HPC. Verifica EOF, configurazione, riferimento e checksum della
calibrazione prima di copiarli e pubblicarli nella directory GPFS della nuova
campagna. Gli altri run vengono sottomessi una volta sola. `--keep-recovering`
conserva il recupero/pubblicazione dei job riusciti anche se altri job vanno in
errore; non li rilascia o risottomette automaticamente e non produce un report
finale incompleto. Il recupero della v1 continua senza nuove sottomissioni.

La v2 mantiene I−iQ, il flusso continuo tra SPEC e i nove FIR della v1.
Non modifica i prodotti v1 né i sorgenti congelati della produzione HTC in corso.
Il nuovo prodotto si chiama `runNNNNN_noise_v2.h5`.

## Definizioni

Per ogni modo si misura nella prima passata la media complessa dell'intero run
selezionato, `mu = mean(I − iQ)`. La seconda passa ai filtri `z_ac = z − mu`.
Non si centrano separatamente gli SPEC e non si filtra via una deriva temporale:
le variazioni lente all'interno del run vengono conservate. Ogni run ha la sua
media; non si assume continuità di fase, oscillatore o stato FIR tra run distinti.
Con `--max-events`, la media riguarda solo il sottoinsieme selezionato e
`reached_eof=false`: il report di produzione rifiuta questi prodotti parziali.

Le quantità a banda intera sono:

* componente costante: `DC² = |mu|²`;
* fluttuazioni: `AC² = mean(|z − mu|²)`;
* quadrato RMS totale: `RMS² = DC² + AC²`.

La varianza complessa è aggiornata con momenti centrati combinabili, evitando
la cancellazione numerica di due potenze quasi uguali. `AC RMS` non è la
deviazione standard dell'inviluppo `|z|` usata dalla v1. Le quantità quadratiche
sono in V²: non sono automaticamente potenze RF in watt.

La sottrazione avviene **prima** di demodulazione e FIR. Non si sottrae la
media dell'uscita di ciascuna banda al suo RMS principale: così un tono coerente
centrato nella banda viene conservato. I momenti complessi dell'uscita sono
comunque salvati, con una decomposizione separata. L'ENBW effettiva del FIR,
bilatera, è `fs * sum(h²) / sum(h)²`, distinta dalla larghezza nominale 50 kHz.

## Calibrazione nominale confermata

[noise_calibration_v2.json](../config/noise_calibration_v2.json) conserva:

| Stadio | Guadagno nominale |
| --- | ---: |
| Linea criogenica | 67 dB |
| FET aggiuntivo, esterno alla misura precedente | 36 dB |
| Downconversion netta, incluse attenuazioni | circa 40 dB |
| Totale | circa 143 dB |

La cascata e i confini degli stadi sono stati confermati dall'utente il
9 novembre 2026, sulla base della comunicazione di Valeria.
Per le ampiezze si divide per `10^(143/20) = 1.4125e7`; per le quantità
quadratiche si divide per `10^(143/10) = 1.9953e14`.

La tesi `Tesi_Valeria_Spasiano.pdf`, sezioni 5.2.2–5.2.3, riporta un guadagno RF
di 103,4 dB (linea + FET), applicato separatamente da `kz(f)`, risposta complessa
di acquisizione calibrata per ciascun modo. La sezione 6.1 riporta per la linea
67,03 e 67,436 dB con metodi diversi. Il modello nominale v2 usa i valori
arrotondati comunicati: non sostituisce la calibrazione frequenza per frequenza.
I riferimenti precisi sono pagine PDF 102–104 e 117, pagine stampate 97–99 e 112;
il checksum della tesi è conservato nella configurazione.

Non si applica anche `kz` insieme ai 40 dB: conteremmo due volte la
downconversion. Non si assume che le tensioni complesse siano già una tensione
RF RMS calibrata su 50 ohm. Le uscite sono quindi **tensioni complesse equivalenti
riferite all'ingresso con guadagno nominale**, senza conversione in watt o
temperatura di rumore. Non è assegnata un'incertezza assoluta non documentata.
Per una calibrazione fisica completa servono le curve numeriche `kz(f)` dei tre
modi, la loro convenzione di normalizzazione e le impostazioni effettive dei run.

## Prodotto e confronto dei trend

`dc_removed` contiene i momenti complessi a banda intera e la calibrazione con
checksum. `filtered_bands` contiene le statistiche dopo rimozione della DC e
le ampiezze normalizzate; il suo `config` conserva gli offset sottratti.
I gruppi ordinari `summary/modes`, `arrays`, `modes` e le due figure storiche
mantengono le definizioni raw della v1 per confronto; la figura `_dc_ac` è nuova.

`report_noise_v2.py` usa solo run completi con configurazione e calibrazione
compatibili, e temperature osservate nello stesso run entro i timestamp SPEC.
Riporta correlazioni con temperatura e tempo, più la correlazione dei residui
dopo rimozione di un trend temporale **lineare**. Conserva il numero di run e
il condizionamento della matrice tempo/temperatura. Non produce p-value né
attribuzioni causali, soprattutto quando temperatura e tempo sono collineari.

Il trend comune descrittivo è la mediana dei logaritmi dei rapporti di ampiezza
laterale dei tre modi rispetto al primo run. Include il modo confrontato:
la divisione per questo trend è un controllo diagnostico, non una correzione
indipendente del guadagno. Un guadagno fisso di 143 dB non cambia rapporti o
correlazioni; mancano misure del guadagno in funzione del tempo.

## Esecuzione

Nell'ambiente Python 3.9 con librerie FLASH CVMFS già verificato:

```bash
python3.9 examples/analyze_midas_iq_noise.py INPUT/run00680.mid.gz \
  --out-dir OUTPUT/v2 --iq-sign -1 --mode-workers 1 \
  --h5-only --filtered-bands --product-version v2 \
  --calibration config/noise_calibration_v2.json

python3.9 examples/report_noise_v2.py OUTPUT/v2/run*_noise_v2.h5 \
  --temperatures TEMPERATURES/temperatures.csv --output OUTPUT/v2/report
```

Il controller HTC accetta `prepare --product-version v2 --calibration FILE`
con una **nuova** campagna e `--gpfs-url` esplicito, diverso dal pilot v1.
Congela anche modulo v2 e calibrazione, valida e pubblica i file `_v2.h5` e
produce `noise_temperature_comparison_v2.h5`. Come per il pilot originale,
preparare una campagna senza `--authorize-submissions` la lascia sospesa.

Anche il launcher HPC richiede il parametro esplicito, senza scegliere un
guadagno nel payload:

```bash
bash examples/hpc/submit_one_run.sh 680 --analysis noise \
  --product-version v2 --calibration config/noise_calibration_v2.json \
  --reference /percorso/noise_reference.json --token-time 3600
```

Si può scegliere qualsiasi altro JSON di calibrazione compatibile. Per cambiare
il valore nominale si aggiornano `stages_db` e `total_db` nel file scelto, non il
codice dell'analisi. Il launcher HPC copia file, riferimento e sorgenti v2 in
una directory univoca sotto `HFGW_RUNTIME_ROOT/noise_submission_sources` prima
della sottomissione. Modifiche successive al file originale non cambiano un job
già accodato. HTC congela il medesimo parametro alla creazione della campagna;
per cambiare normalizzazione si prepara una nuova campagna. Il worker controlla
la calibrazione prima del download e l'HDF5 ne conserva valori e SHA-256.

Verifica iniziale: 10 SPEC del run 680, librerie FLASH CVMFS Python 3.9.
I 102 dataset ordinari di confronto sono identici alla v1; la somma DC²+AC²
coincide con la potenza quadratica raw. L'RMS centrale TM011 passa da circa
5,95 a 5,05 mV ADC dopo la rimozione della DC. Questi numeri riguardano solo
la prova breve, non l'intero run o la correlazione sui dodici run.
