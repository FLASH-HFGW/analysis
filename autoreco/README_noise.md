# Campagna rumore IQ con autoreco

La campagna riusa `autoreco.py`: selezione dal logbook, riconoscimento dei job
attivi, sottomissione, recupero degli output e stato persistente. La nuova
modalità è `--analysis-kind noise`; il payload legge il run fino a EOF.

Configurazione in `run_autoreco_noise_configured.sh`:

- Run **680–939 inclusi**, 260 richiesti.
- Directory locale e lock separati: `job_to_submit_noise`.
- Output remoto: `flash/analysis/autoreco/Run2/noise_by_run`.
- `--read-only --ignore-reco-done`: legge il logbook senza modificare lo stato
  FFT, selezionando anche run già ricostruiti. Resta il filtro `rucio_status=0`.
- Segno IQ -1, fs 5 MHz, ADC +/-5 V; 4 CPU (3 thread), 4 GB RAM, 100 GB disco per job.

Gli script esistenti in `examples/htc`, i job cron e la configurazione offline
FFT restano quelli precedenti. Non è necessario modificare il crontab.

## Preparazione e avvio

Dalla radice del repository:

```bash
autoreco/run_autoreco_noise_configured.sh --prepare-only
```

Questa modalità genera le directory per i run espliciti senza aprire il
logbook, interrogare HTCondor o inviare job. I 260 job sono già preparati.
Non rigenera directory che hanno già un `job_state.json`.

Verifica locale di un submit, senza OAuth e senza sottomissione:

```bash
cd /home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/job_to_submit_noise/00680
/usr/bin/condor_submit -dry-run /tmp/noise-submit.ads \
  -append 'use_oauth_services =' submit.sub
```

Il percorso assoluto evita l’alias locale `condor_submit='condor_submit -spool'`,
che altrimenti aggiunge lo spool anche al dry-run. La sottomissione reale
dell’autoreco usa esplicitamente `-spool`, come previsto.

Avvio della campagna, dalla radice:

```bash
autoreco/run_autoreco_noise_configured.sh
```

Per recuperare quelli completati, ripetere lo stesso comando. Per iniziare da
un solo run e attendere il completamento:

```bash
autoreco/run_autoreco_noise_configured.sh --run 680 --wait
```

`--wait` segue i job sottomessi dalla singola invocazione, come l'autoreco
esistente. `--retry-failed` riprova quelli falliti. Non usare i reset destinati
alle directory FFT per questa campagna.

La preparazione non verifica disponibilità: la sottomissione reale legge il
logbook ed esclude run assenti o con `rucio_status` diverso da zero.

## Payload e output

Il payload usa CVMFS, GFAL e il servizio OAuth `t1`. Il submit trasferisce
analisi, modulo statistiche e una copia del riferimento in ogni directory job.
Il MIDAS viene scaricato nel disco locale e rimosso al termine. Il nuovo payload produce e pubblica un solo `runNNNNN_noise.h5`, recuperato
anche da HTCondor nella directory locale del run. Contiene array, metadati,
configurazione, riferimento e figure PNG incorporate; non pubblica sidecar
NPZ/JSON/PNG. Gli errori causano exit code non
nullo e hold. `runNNNNN_job_status.json` registra l'esito del payload.
Prima di marcare un job noise riuscito l'autoreco verifica JSON completo,
numero del run, riferimento e presenza del NPZ.

## Riferimento fisso

`noise_reference.json` è derivato dai **100 eventi pilota** già analizzati del
run 680, non dal run completo. Le soglie fisse sono media e RMS del pilota:
`media_pilota + k * RMS_pilota`, con k = 3, 5, 7. I conteggi locali usano invece
media e RMS del singolo run completo. I due conteggi restano separati.
Il pilota usava +1: essendo il riferimento basato solo sull’ampiezza, i suoi
momenti valgono anche per -1; fase e IQ sono ricalcolati dai job con -1.

Per creare un riferimento da uno o più riepiloghi compatibili:

```bash
python3 examples/aggregate_iq_noise.py /home/mazzitel/flash-data/analysis/autoreco/Run2/examples/noise_results/run00680_noise.json \
  --make-reference /home/mazzitel/HFGW/analysis-work/Run2/references/noise_reference.json
```

Il riferimento combina media e varianza pesandole per i campioni. Accetta anche
i vecchi riepiloghi; per l'aggregazione sono invece necessari i nuovi output.
Cambiare riferimento richiede una nuova campagna con directory/output separati
oppure una ripetizione intenzionale dei job precedenti, evitando di mescolarli.

## Aggregazione

Dopo aver recuperato i job, dalla radice:

```bash
python3 examples/aggregate_iq_noise.py /home/mazzitel/flash-data/analysis/autoreco/Run2/job_to_submit_noise \
  --expected-runs config/noise_runs.txt --out-dir /home/mazzitel/flash-data/analysis/autoreco/Run2/noise_global
```

`noise_runs.txt` elenca 680–939. Il controllo richiede tutti e soli quei run;
se il logbook ne esclude alcuni, predisporre una lista esplicita dei run attesi
invece di ignorare silenziosamente quelli mancanti. L'aggregazione rifiuta
duplicati, output vecchi/incompleti e configurazioni incompatibili. Per prove
intenzionalmente limitate esiste `--allow-partial`: i run parziali sono elencati.

Output:

- `runs.csv`: una riga per run e modo con media, RMS, frazioni sopra soglia,
  episodi, tassi per secondo acquisito, durata massima e massimo dell'ampiezza.
- `global_noise.json`: momenti globali pesati, conteggi/episodi e statistiche
  circolari di delta fase.
- `global_noise.npz`: istogrammi sommati di ampiezza, IQ, fase e delta fase.
- `global_distributions.png`, `global_iq.png`, `run_trends.png`: distribuzioni
  e confronti tra run.

## Definizioni

I bin globali sono comuni: 65536 per ampiezza sull'intervallo ADC fisico, 256 per
asse IQ e 1024 per fase/delta fase. Il NPZ li conserva tutti; il grafico globale
dell'ampiezza mostra tutti i bin nell’intervallo popolato. Gli istogrammi dettagliati per
run restano separati. La fase globale è `atan2(iq_sign*Q,I)`, senza sottrarre
la fase iniziale del run.

Delta fase è `arg[z(n+lag)*conj(z(n))]`, calcolata con angoli per stabilità,
a ritardi di 1, 10, 100 campioni (0.2, 2, 20 microsecondi con 5 MHz). Non si
formano coppie tra eventi. Campioni di ampiezza nulla sono esclusi dalla fase;
i campioni piccoli restano presenti e possono avere fase dominata dal rumore.

Un episodio è un gruppo consecutivo di campioni strettamente sopra soglia.
Attraversa i confini SPEC dello stesso run e viene interrotto solo tra run. Sono episodi osservati, senza
correzioni per banda o tempo morto. Durate e tassi usano tempo **acquisito**,
non tempo di calendario.

I conteggi locali e di riferimento sono esatti. Per le soglie ricavate dai
momenti della popolazione aggregata, non note durante i job, il riepilogo dà
un **limite inferiore/superiore** determinato dal bin della soglia. Per conteggi
esatti si può creare un riferimento dall'intera campagna e rieseguire i job.
Le aspettative gaussiane restano confronti teorici, non ipotesi verificate.

Separare campagne con guadagni, cablaggio o condizioni sperimentali diversi:
i controlli automatici coprono i parametri di analisi, non tutti quelli hardware.

## Verifiche

```bash
python3 -m unittest discover -s examples/tests -p 'test_iq_noise_statistics.py'
python3 -m unittest discover -s examples/tests -p 'test_autoreco_noise.py'
```

Oltre alle prove integrate su segnali noti è stata eseguita una prova reale
limitata a due eventi del run 680, con output separato in
`/tmp/noise-multirun-real-validation`. La preparazione locale non avvia analisi
complete né sottomette la campagna.

## Prestazioni

Vedi [rapporto sui primi run e ottimizzazioni](/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/noise_performance/REPORT.md).
Le nuove esecuzioni salvano i tempi CPU/wall delle passate in `performance.timings`
e mostrano l’avanzamento ogni 100 eventi. I job già nello spool mantengono la
versione trasferita alla loro sottomissione.

## Seconda passata: parallelismo sui tre modi

Lo script accetta `--mode-workers 1`, `2` oppure `3`. I modi TM010, TM011 e
TM012 hanno accumulatori distinti: fino a tre thread elaborano lo stesso evento
in parallelo, senza copiare gli eventi fra processi. Si attende il completamento
di tutti i modi prima di leggere l'evento successivo. La prima passata rimane
sequenziale. Le statistiche circolari riutilizzano i fasori unitari; i conteggi
locali sono condivisi fra riepilogo del run e aggregazione, senza ricalcolarli.

Prova interattiva su 100 eventi, dalla radice del repository:

```bash
python3 examples/analyze_midas_iq_noise.py   /home/mazzitel/flash-data/data/LNF/run00680.mid.gz   --iq-sign -1 --global-reference /home/mazzitel/HFGW/analysis-work/Run2/references/noise_reference.json   --max-events 100 --mode-workers 3 --out-dir /home/mazzitel/flash-data/analysis/autoreco/Run2/examples/noise_results_test_parallel
```

Per i futuri job autoreco, `--cpus 3` richiede tre CPU e passa tre thread al
payload; una CPU usa un thread, e il numero massimo di thread è tre anche se
vengono richieste più CPU. La configurazione predefinita richiede quattro CPU per
job e usa tre thread: ridurre il tempo del singolo run con tre CPU non garantisce un aumento
del throughput complessivo della campagna a risorse totali fissate.
I job già sottomessi mantengono codice e numero di CPU del loro spool.

I file NPZ conservano gli stessi bin e le stesse statistiche. I conteggi e gli
indici sono invariati; le somme circolari possono differire soltanto per
arrotondamento numerico perché seno e coseno sono calcolati con prodotti di
fasori equivalenti. Il JSON `performance` indica numero di thread e versione
implementativa. Le misure sono nella directory locale `/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/noise_performance/pass2/`.

## Continuità dei campioni e correzione schema 2

Tutti i SPEC dello stesso run sono blocchi consecutivi di un unico stream
a 5 MHz. Non esistono gap ai confini SPEC. Stato unwrap, coppie ai ritardi
e durata degli episodi attraversano questi confini; il raccordo si ferma
tra run, dove possono mancare campioni. Le soglie 3/5/7 sigma sono calcolate
dalla media e dalla deviazione standard dell'ampiezza reale, senza ipotesi
gaussiana.

A=0 rende indefinita la fase: viene mascherata e l'unwrap segue il salto
minimo fra fasi valide. Non misura un numero di rotazioni fisiche garantito
quando l'ampiezza è vicina a zero o la fase varia troppo fra campioni.

La correzione conservativa della campagna usa `repair_noise_continuity.py`
e scrive in `noise_continuous/`, mantenendo gli originali. Una sola lettura
aggiorna fase, coppie e giunzioni degli episodi; i prodotti di ampiezza sono
conservati. Richiede una CPU per job perché questa passata è seriale.

```bash
python autoreco/repair_noise_continuity.py --status
python autoreco/repair_noise_continuity.py --recover
python autoreco/finalize_noise_continuity.py
```

La finalizzazione richiede tutti i 260 run corretti, e rigenera aggregati,
screening della stazionarietà e slide v4 senza mescolare schemi 1 e 2.

## Posizione degli output

Solo i risultati scientifici (array, grafici e riepiloghi dell’analisi) vanno in
`/home/mazzitel/flash-data/analysis/autoreco/Run2`. Log, lock, stati, payload, cache e input di lavoro restano locali in
`/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2`.
Il repository contiene script, notebook, README e configurazioni sorgenti.
I risultati delle code si pubblicano con `gfal-copy`; nessun log o stato viene pubblicato su GPFS.

### Benchmark e ottimizzazioni

Report di prestazioni, profili, metriche e output di confronto restano in locale:
`/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/noise_performance/`.
Anche i file NPZ, JSON e PNG generati per questi confronti sono artefatti di test,
non risultati della campagna da pubblicare su GPFS. Conservarli come riferimento
per tempi, memoria e correttezza durante le modifiche e il prossimo rilancio.

## Dizionario dei risultati e verifiche IQ filtrate

I nuovi payload HPC e HTC generano prodotti scientifici `v1`, con
`--filtered-bands --product-version v1 --h5-only`. La pubblicazione su GPFS
usa `runNNNNN_noise_v1.h5`: un contenitore per run con statistiche, bande e
PNG incorporati. Il tag `v1` è anche nei metadati. I file storici `*_v0.h5`
restano separati. Il trasferimento viene verificato con riscaricamento SHA-256.

Lo script principale può salvare anche un contenitore HDF5 compresso:

```bash
python examples/analyze_midas_iq_noise.py /percorso/run00680.mid.gz \
  --iq-sign -1 --h5 --out-dir /tmp/noise_h5
```

`--h5-only` produce invece un unico HDF5, incorporando anche le figure
e rimuovendo i PNG temporanei soltanto dopo il salvataggio riuscito. È
l’opzione usata dai nuovi payload autoreco. Un file da 1 MB per run è
accettabile: non si impone una dimensione minima né il raggruppamento di run.
La dimensione effettiva guida eventuali consolidamenti futuri.

`build_results()` in `iq_noise_io.py` costruisce un dizionario con `schema_version`, `summary`,
`arrays` (array comuni e istogrammi globali), `modes` (array per TM010/011/012)
, `filtered_bands` e `figures`. `save_results_h5()` traduce i dizionari in gruppi e gli
array in dataset; `None` e liste di record sono dataset JSON UTF-8 marcati
con attributo `encoding=json`. NPZ, JSON e PNG restano disponibili.
Il riepilogo include `reached_eof`, anche nelle analisi limitate.

Per includere le verifiche per SPEC di ampiezza media, RMS, fase circolare
e incrementi di fase nelle bande simmetriche:

```bash
python examples/analyze_midas_iq_noise.py /percorso/run00680.mid.gz \
  --iq-sign -1 --filtered-bands --max-events 3 --out-dir /tmp/noise_bands
```

`--filtered-bands` abilita automaticamente HDF5. Richiede `h5py`, `scipy` e
`analyze_iq_filtered_bands.py` accanto allo script. Usa la seconda lettura
MIDAS, con FIR, oscillatore e coppie continui fra SPEC. Default: centro 0,
offset ±100/250/500/1000 kHz, larghezza 50 kHz, FIR Kaiser 2001 tap,
decimazione 20; il ritardo degli incrementi è quindi 4 microsecondi.
Si configurano con `--band-centers-hz` (tre centri), `--band-offsets-hz`,
`--band-width-hz`, `--band-taps`, `--band-decimation`.
La fase è riferita all'oscillatore e la banda centrale include DC.
Non viene stimata automaticamente la frequenza fisica di risonanza.

Le colonne sono in `filtered_bands/modes/TM010/band_XX/events/` (e analoghi),
con offset e centro memorizzati nel gruppo della banda. I timestamp MIDAS
sono distinti dal tempo acquisito corretto per il ritardo FIR. I SPEC senza
campioni validi dopo il transitorio non producono righe. Sono conservati
conteggi di campioni e coppie per pesare le statistiche.

Queste opzioni sono disponibili per l'esecuzione diretta: i payload autoreco
attuali continuano a usare NPZ/JSON e non attivano le bande filtrate.
