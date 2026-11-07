# Autoreco

`autoreco.py` lavora a passate ed è adatto a essere richiamato da cron:

1. recupera i job HTCondor già sottomessi;
2. trasferisce e verifica quelli completati;
3. aggiorna `reco_done` sul Google Sheet;
4. sottomette solo i run con `rucio_status=0`, `reco_done=0` e senza
   un job attivo;
5. salva lo stato in `/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/job_to_submit/RUN/job_state.json`.

La versione richiesta viene letta da `reco_requested_version` (oppure
da `--reco-version`, con default `1.0`). Dopo un job riuscito viene salvata
in `reco_version`.

I file prodotti vengono copiati per default in
`flash/analysis/autoreco/Run2/fft_by_run`. Il percorso effettivamente usato
viene salvato nella colonna `reco_output_path` del Google Sheet dopo il
completamento del job.

Un lock (`.autoreco.lock`) impedisce a due invocazioni di lavorare
contemporaneamente.

## Esecuzione

Una singola passata, come farà cron:

```bash
./run_autoreco_cron.sh --run-min 0
```

Per un singolo run:

```bash
./run_autoreco_cron.sh --run 900
```

Per attendere nello stesso processo fino al completamento:

```bash
./run_autoreco_cron.sh --run 900 --wait
```

Per scegliere una cartella di output diversa:

```bash
./run_autoreco_cron.sh --run 900 \
  --output-folder flash/analysis/autoreco/Run2/fft_by_run_test
```

`--output-path` è un alias equivalente di `--output-folder`.

Per scegliere esplicitamente lo script di analisi:

```bash
./run_autoreco_cron.sh --run 900 \
  --analysis-script-dir /home/mazzitel/HFGW/analysis/examples \
  --analysis-script-name analyze_midas_iq_fft_4ms_paral-pipe.py
```

Per risottomettere esplicitamente un job terminato con errore:

```bash
./run_autoreco_cron.sh --run 900 --retry-failed
```

Lo stato del tentativo fallito viene conservato nella directory del run.

## Esecuzione manuale senza scritture sul database

Per usare una configurazione separata, senza modificare il Google Sheet:

```bash
./run_autoreco_offline_configured.sh --run 900 --wait
```

`run_autoreco_offline_configured.sh` contiene i parametri della
configurazione manuale e usa una directory job e un lock separati da cron.
L'opzione `--read-only` legge il Google Sheet per selezionare i run, ma non
aggiunge colonne e non aggiorna `reco_done`, `reco_version` o
`reco_output_path`. La configurazione offline usa anche
`--ignore-reco-done`, così può analizzare nuovamente run già completati
dall'autoreco online. Lo stato locale viene marcato `read_only_completed`.

La durata delle FFT si configura nello stesso file con
`--number-chunks N`: lo script divide l'evento acquisito, lungo circa
209 ms, in `N` parti. Per esempio, `--number-chunks 64` produce FFT di
circa 3,27 ms. `N` deve essere una potenza di 2.

Con `--fft-window-seconds 1` vengono conservati il riepilogo del run e le
medie consecutive da circa un secondo (`run00402_fft_1s.npz`, ecc.) come membri
di archivi giornalieri `fft_YYYY-MM-DD.zip`, non come file separati su GPFS.
La configurazione automatica lascia questa funzione disabilitata; quella
offline la abilita. Dettagli in [README_fft_daily.md](README_fft_daily.md).

Per ripetere l'elaborazione offline dopo una modifica alla configurazione:

```bash
./run_reset_autoreco_offline.sh --run 940
./run_reset_autoreco_offline.sh --run-range 940 950
./run_reset_autoreco_offline.sh --run-min 940
```

Il reset non apre e non modifica il Google Sheet. Le directory locali
selezionate vengono spostate sotto
`/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/job_to_submit_offline/_reset_archive/TIMESTAMP`, senza essere cancellate.
Il comando non può essere eseguito mentre autoreco offline detiene il lock.

## Crontab

Creare prima la directory dei log:

```bash
mkdir -p /home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/logs
```

Quindi aggiungere con `crontab -e`:

```cron
*/5 * * * * /home/mazzitel/HFGW/analysis/autoreco/run_autoreco_cron_configured.sh >> /home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/logs/autoreco.log 2>&1
```

I parametri dell'esecuzione automatica sono raccolti, su più righe, in
`run_autoreco_cron_configured.sh`: selezione dei run, percorsi di input e
output, directory e nome dello script di analisi, versione, numero massimo
di eventi, CPU e segno IQ (`--iq-sign`, valori ammessi `+1` e `-1`).

Una voce del crontab deve restare su una singola riga: le continuazioni con
`\` non sono supportate dal formato crontab. Non usare `&`: cron avvia già
il comando senza terminale.

## Richiedere una nuova ricostruzione

Run singolo, versione predefinita `1.0`:

```bash
./run_reset_reco.sh --run 900
```

Intervallo con una versione diversa:

```bash
./run_reset_reco.sh --run-range 900 910 --reco-version 2.0
```

Il comando imposta `reco_done=0` e `reco_requested_version`. Alla passata
successiva cron sottomette i job; al completamento `reco_version` contiene
la versione realmente prodotta.

## Plot degli output FFT

Per generare il plot dei tre modi da un singolo file:

```bash
./plot_fft_npz.py /home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/job_to_submit/00591/run00591.npz
```

Per elaborare tutti i file presenti in una directory e salvare i PNG in
una directory scelta:

```bash
./plot_fft_npz.py /percorso/degli/npz \
  --output-dir /home/mazzitel/flash-data/analysis/autoreco/Run2/fft_plots \
  --db
```

Il plot normalizza per `n_fft_done * number_chunks`. Usare `--raw` per
visualizzare le somme salvate senza normalizzazione, `--fmin` e `--fmax`
per limitare l'intervallo in Hz e `--modes` per scegliere i modi.

## Posizione degli output

Le FFT temporali in `fft_by_1sec` sono raccolte per giorno UTC in archivi ZIP:
vedi [formato, recupero e produzione giornaliera](README_fft_daily.md).

Solo i risultati scientifici (array, grafici e riepiloghi dell’analisi) vanno in
`/home/mazzitel/flash-data/analysis/autoreco/Run2`. Log, lock, stati, payload, cache e input di lavoro restano locali in
`/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2`.
Il repository contiene script, notebook, README e configurazioni sorgenti.
I risultati delle code si pubblicano con `gfal-copy`; nessun log o stato viene pubblicato su GPFS.

## File operativi e continuità dei job

La directory locale `/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2`
contiene tutto il ciclo di sottomissione e controllo: `job_to_submit`,
`job_to_submit_offline`, `job_to_submit_noise`, file `.sub`, payload, riferimenti
trasferiti ai worker, stati JSON, archivi dei tentativi, lock, log e cache.
Questi file piccoli non devono essere archiviati su GPFS. Anche gli stati e i
payload di riparazione noise (`noise_continuous/jobs` e `sources`) restano locali.
Gli stati esistenti non vanno rigenerati né sovrascritti durante un recupero.
Il cron va riattivato solo esplicitamente, con redirezione dei log sul disco locale.

### Preparazione della prossima elaborazione

La precedente `job_to_submit` su GPFS è stata verificata e rimossa:
i risultati FFT sono conservati in `fft_by_run`, mentre una copia completa,
inclusi input e storico, resta nella `job_to_submit` locale di `analysis-runtime`.
Il prossimo rilancio completo, dopo le modifiche agli script, riutilizzerà le
destinazioni scientifiche esistenti (`--output-folder`) sovrascrivendo i risultati,
come richiesto. Per gli stati usare una directory locale di campagna distinta
(`--output-dir`) oppure archiviare e resettare esplicitamente gli stati precedenti:
gli stati terminali esistenti possono altrimenti impedire il rilancio.
Lo storico locale recuperato resta disponibile fino al completamento del nuovo giro.
Non sono stati resettati stati, riattivati cron o sottomessi nuovi job.

### Storico offline e noise

Tutte le directory `job_to_submit*` appartengono al disco locale di
`analysis-runtime/autoreco/Run2`, inclusi archivi dei reset e diagnostica.
Il recupero del 6 novembre 2026 conserva in locale anche i risultati rimasti
nelle vecchie directory dei job: 43.821 file offline e 1.584 file noise.
L'archivio offline include risultati precedenti ai reset che non hanno una copia
equivalente in `fft_by_1sec`: conservarlo e non sovrascriverlo per il rilancio.
Le destinazioni scientifiche correnti sono `fft_by_run`, `fft_by_1sec` e
`noise_by_run`; non usare directory `job_to_submit*` come destinazioni remote.
