# SLURM LNF — accesso diretto CVMFS/GFAL

## Pilot IQ filtrato e temperature

Il flusso IQ usa **Python 3.9**, già presente sui worker LNF. I pacchetti CVMFS
3.11 non comprendono l'interprete: non si presume più che `python3.11` esista.
NumPy, SciPy, h5py, Matplotlib e MIDAS provengono interamente da CVMFS FLASH:
`/cvmfs/sft-flash.infn.it/package/python3.9/site-packages/` e dal percorso MIDAS
dello stesso repository. Anche i nuovi payload HTC puntano a CVMFS FLASH.
Non è previsto un setup pip o un venv. I vecchi percorsi venv vengono ignorati;
`PYTHONPATH` viene ricostruito e la user-site viene disabilitata.

Il controllo di ambiente verifica che ciascuna libreria scientifica sia stata
caricata da CVMFS, anche sul worker prima del download MIDAS. Se SciPy non è
ancora propagato o viene trovato fuori CVMFS, il flusso si ferma prima del calcolo.
Il comando `check-env` può essere ripetuto dopo la propagazione della pubblicazione.

Prima di sottomettere si può provare l'ambiente, senza job o download MIDAS:

```bash
bash examples/hpc/run_noise_pilot.sh check-env
```

Il controllo stampa interprete, versioni e percorsi e prova una convoluzione,
un HDF5 compresso e una figura PNG. Viene eseguito automaticamente anche
all'avvio di `watch --submit`, prima di contattare lo scheduler.

`submit_one_run.sh` conserva il percorso FFT predefinito. La nuova opzione
`--analysis noise` seleziona invece `noise_job.sh`, con ricostruzione completa
`analyze_midas_iq_noise.py --iq-sign -1 --filtered-bands --h5-only`.
Entrambi i payload, HPC e HTC, passano `--product-version v1`: il tag è
registrato nel riepilogo e nella radice dell'HDF5. Su GPFS il nome finale è
`runNNNNN_noise_v1.h5`, un file completo per run con le figure incorporate.
Richiede il riferimento di ampiezza condiviso, disponibile anche nel pacchetto
trasferibile del pilot sotto `config/noise_reference.json`:

```bash
bash examples/hpc/submit_one_run.sh 680 --analysis noise \
  --reference config/noise_reference.json --token-time 3600 --time 03:00:00
```

La modalità noise usa 1 CPU e 4 GB RAM, con limite predefinito di tre ore.
`--resource cpu` seleziona per default la partizione `CPU` e non richiede GPU.
Anche eventuali richieste GPU ereditate tramite variabili `SBATCH_*` vengono
rimosse nel sottoprocesso di sottomissione. Il payload non contiene più una
direttiva GPU: la richiesta viene aggiunta dal launcher solo con `--resource gpu`.

Per compatibilità con l'associazione già provata, il default resta
`--resource gpu`, partizione `GPU`: riserva una GPU, ma il programma IQ calcola
sulla CPU. Il percorso FFT GPU rimane distinto e non accetta `--resource cpu`.
L'uso della partizione CPU richiede che l'account sia autorizzato sulla facility;
la presenza della partizione sul nodo non dimostra da sola l'autorizzazione.

### Benchmark CPU isolato

La prova locale sul run 680, limitata a 10 SPEC con Python 3.9 e librerie
FLASH CVMFS, confronta i sorgenti precedenti con il FIR ottimizzato:
tempo totale 61,7 → 48,4 s (−22%), seconda passata 45,8 → 32,3 s (−29%).
Le statistiche non filtrate sono identiche; quelle filtrate differiscono solo
per arrotondamenti numerici (fase entro 9,4e-15 rad). È una misura breve locale,
da confermare su un run completo HPC. Il picco di memoria osservato sale da
circa 437 a 487 MiB: si conserva la richiesta Slurm di 4 GB.

Dopo il pull, usando il riferimento già congelato nella campagna, si può
misurare una ricostruzione parziale senza pubblicarla su GPFS:

```bash
HFGW_NOISE_OUTPUT_ROOT="$HOME/HFGW/analysis-runtime/autoreco/Run2/benchmarks/noise_cpu_optimized" \
bash examples/hpc/submit_one_run.sh 680 --analysis noise --resource cpu --partition CPU \
  --reference "$HOME/HFGW/analysis-runtime/autoreco/Run2/noise_temperature_pilot_slurm_v1_20261108/sources/noise_reference.json" \
  --max-events 10 --time 00:15:00 --token-time 3600
```

Il risultato ha `reached_eof=false`, resta nel benchmark locale HPC e non viene
gestito dal monitor del pilot. I tempi per passata sono in `summary/performance`
dell'HDF5. `sacct` permette di verificare che `AllocTRES` non contenga GPU.
Una nuova campagna può usare `watch --submit --resource cpu`; `--partition`
consente un override esplicito del nome della partizione.

Per i 12 run 680, 704, 727, 751, 774, 798, 821, 845, 868, 892, 915, 939,
eseguire sulla login HPC, dalla radice del clone Git:

```bash
git pull --ff-only origin main
bash examples/hpc/run_noise_pilot.sh prepare
bash examples/hpc/run_noise_pilot.sh status
# Eseguire il monitor in tmux o in un terminale persistente, quando si vuole avviare:
bash examples/hpc/run_noise_pilot.sh watch --submit --max-active 4 --token-time 3600
```

`prepare` scarica da GPFS l'HDF5 con riferimento e temperature, ne verifica
lo SHA-256 fissato in `config/noise_temperature_pilot.json`, quindi copia
sorgenti e input nell'area locale registrandone i checksum. I dati misurati
non sono in Git. Restano accettati anche `--reference FILE --temperatures CSV`
per specificare entrambi gli input locali.

`prepare` non sottomette. `watch --submit` sottomette al massimo quattro job contemporanei,
recupera i risultati dal filesystem condiviso e avvia i successivi con un token
appena richiesto per ciascun job. In questo modo un unico token da un'ora non
viene riutilizzato per tutti i turni di un array. Il tempo in coda può comunque
farlo scadere prima del download: in quel caso il job fallisce e il monitor ferma
le nuove sottomissioni. Non si conserva il token nei log o negli artefatti.
Il token del worker serve al download iniziale. Il monitor sul login node
ottiene separatamente un token corrente per pubblicare i risultati su GPFS.

Il monitor deve rimanere attivo sul login node: le ricostruzioni girano nei job.
Le campagne già preparate continuano a usare i propri sorgenti congelati:
il pull non sostituisce i filtri dei job già avviati o ancora da inviare in quella
campagna. Per adottare i nuovi filtri creare una nuova directory `--campaign`
e un nuovo `--output`; non modificare le copie congelate a mano.
Per riprenderlo usare lo stesso comando: legge gli stati senza risottomettere
i run già inviati. Un lock impedisce monitor simultanei per la stessa campagna.
`watch --once` esegue un solo controllo senza nuove sottomissioni;
`report` rigenera il confronto dopo che tutti i risultati sono completi.
Una ricostruzione limitata con `--max-events` non è accettata come prodotto completo.

Per riprovare i run falliti dopo una correzione dell'ambiente:

```bash
bash examples/hpc/run_noise_pilot.sh check-env
bash examples/hpc/run_noise_pilot.sh retry-failed
bash examples/hpc/run_noise_pilot.sh watch --submit --max-active 4 --token-time 3600
```

`retry-failed` non sottomette: verifica che i job falliti non siano ancora in
Slurm, archivia i vecchi stati in `attempts/` e rimette in `prepared` solo quei
run. Log, output dei vecchi job, run completi e gli altri run preparati restano
conservati. Non modificare a mano gli stati per riprovare un fallimento.

Stati e log del controllo sono sotto:

`$HOME/HFGW/analysis-runtime/autoreco/Run2/noise_temperature_pilot_slurm_v1_20261108/`

Risultati HDF5 e confronto termico sono sotto:

`$HOME/HFGW/analysis-work/Run2/reports/noise_temperature_pilot_v1_20261108/`

Il sottoalbero `jobs/JOB_<id>/` conserva HDF5, log dell'analisi ed esito per ogni
job. Solo un HDF5 validato (fine file, I−iQ, nove bande per modo) viene copiato
nella radice per il report. Un run diventa `complete` solo dopo la pubblicazione
e verifica su GPFS: upload con checksum GFAL, riscaricamento e confronto SHA-256.
Un errore di trasferimento lascia `publication_pending`, conserva il risultato
locale e blocca nuove sottomissioni; il monitor riprova la pubblicazione senza
rilanciare il calcolo. Non sovrascrive file remoti esistenti con contenuto diverso.

La cartella scientifica GPFS autorizzata è:

`flash/analysis/autoreco/Run2/noise_temperature_pilot_minus1_20261108/`

Contiene l'HDF5 degli input, `runNNNNN_noise_v1.h5` per ogni run completato e,
alla fine, `noise_temperature_comparison_v1.h5` con tabelle, figure e provenienza.
Log, stati e ricevute di trasferimento restano sul filesystem HPC.
La pubblicazione avviene a ogni run completato, senza aspettare la fine dei 12 run:
i file sono leggibili dal mount CNAF `~/flash-data/analysis/autoreco/Run2/`.
Le nuove directory di controllo `v1` mantengono separate le copie congelate
delle campagne precedenti; `prepare` non cambia una campagna già preparata.

Lo scratch unico viene eliminato soltanto dopo
analisi e copia riuscite; in caso di errore viene conservato per diagnosi.
Il confronto usa le temperature osservate nello stesso run entro i timestamp
SPEC, con i limiti descritti in [README_noise_temperature_pilot.md](../README_noise_temperature_pilot.md).

## Percorso FFT esistente

Il payload ufficiale è `job.sh`. `jobsub.sh` richiama lo stesso payload dentro
l'allocazione SLURM; `script.sh` mantiene la vecchia interfaccia a quattro argomenti.
I test proxy precedenti non sono necessari per la configurazione diretta.

## Ambiente

`environment.sh` inizializza Environment Modules, abilita il percorso CVMFS e
carica `gfal/1.9.0`. Usa `HFGW_CVMFS_ROOT` se specificato; altrimenti sceglie
`/cvmfs/sft-flash.infn.it` se disponibile, poi il percorso precedente
`/cvmfs/mazzitel-personalrepo.infn.it`. Le librerie MIDAS e Python provengono
dallo stesso mount. Non viene caricato rclone.

Il repository viene cercato a partire da `SLURM_SUBMIT_DIR`, anche quando si
sottomette da `examples/hpc/`. Con un altro layout impostare `HFGW_REPO_ROOT`.
Il repository deve essere leggibile dai worker. Il token viene ottenuto sul
login node ed esportato al job; il payload non stampa né rigenera il token.

## Prova del servizio abilitato sul worker

Dalla directory del clone sulla facility:

```bash
mkdir -p "$HOME/slurm_logs"
# Se necessario, caricare sul login node il modulo oidc-agent già configurato.
(
BEARER_TOKEN=$(oidc-token flash --time=3600)
export BEARER_TOKEN
sbatch --account=cygno --partition=GPU --qos=normal --gres=gpu:1 \
  --export=ALL,BEARER_TOKEN examples/hpc/test_gfal_direct.sh
)
```

Questo test controlla l'accesso alla directory CNAF con `gfal-ls`, senza calcoli
GPU. L'associazione attuale dell'utente è `cygno/GPU`: il comando sovrascrive
quindi la partizione CPU predefinita nel test. Per verificare anche il download, impostare esplicitamente
`HFGW_GFAL_TEST_URL` a un piccolo file e `HFGW_GFAL_TEST_DOWNLOAD=1` prima di
sottomettere. Il file di prova viene scaricato in scratch e poi eliminato.

Per verificare CuPy/CUDA:

```bash
sbatch examples/hpc/test_cupy.sh
```

Il token deve essere valido quando il job parte; il tempo in coda può ridurne
la validità residua. Nessuna di queste istruzioni copia credenziali nel repository.

## Benchmark FFT

```bash
bash examples/hpc/submit_one_run.sh 680
```

Il launcher richiede il token sul login node in un sottoprocesso e lo esporta
soltanto verso `sbatch`: il valore `BEARER_TOKEN` della shell chiamante non cambia,
neppure se il launcher viene accidentalmente eseguito con `source`. La cache
dell'oidc-agent condiviso può comunque aggiornarsi: i token già esportati nella
shell mantengono il loro valore e la loro scadenza originari.

I default sono account `cygno`, partizione `GPU`, QoS `normal`, run completo e
validità residua minima del token di 86400 secondi. Il limite SLURM resta quello
di `job.sh`, un'ora, salvo override esplicito:

```bash
bash examples/hpc/submit_one_run.sh 680 --time 02:00:00
bash examples/hpc/submit_one_run.sh 388 --max-events 100
bash examples/hpc/submit_one_run.sh --help
```

Sono disponibili anche `--account`, `--partition`, `--qos`, `--oidc-account`,
`--token-time SECONDI` e `--log-dir`. I default di account/partizione/QoS possono
essere impostati con `HFGW_SLURM_ACCOUNT`, `HFGW_SLURM_PARTITION`, `HFGW_SLURM_QOS`.
Il launcher crea la directory dei log e mostra job ID e percorsi per monitorarlo.

Token e scadenza vengono letti insieme con `oidc-token --all`, senza stampare o
scrivere il token in un file. `--time` non forza l'issuer a concedere una durata
maggiore del proprio massimo: il launcher controlla la scadenza effettiva e non
sottomette se il margine è inferiore a quello richiesto, con 60 secondi di tolleranza.
In quel caso una soglia più breve va scelta esplicitamente con `--token-time`.
Vedi la [documentazione oidc-agent](https://indigo-dc.gitbook.io/oidc-agent/user/oidc-token/options).

Il job scarica il MIDAS una sola volta con GFAL, in un file temporaneo `.part`.
Soltanto dopo il download riuscito e non vuoto lo rinomina come input. Non sono
previsti altri download con rclone o copie da percorsi di test locali.

La ricostruzione usa GPU/CuPy e profiling come nella prova precedente. Scratch
per job, monitor GPU, risultati e diagnosi sono separati. Gli output del benchmark
sono conservati sul filesystem persistente della facility, sotto:

`$HOME/HFGW/analysis-runtime/autoreco/Run2/benchmarks/slurm/JOB_<id>/`

Non vengono pubblicati su GPFS e non vengono scritti nel clone Git. Il file
MIDAS e un eventuale `.part` non vengono copiati tra i risultati. Anche in caso
di errore dell'analisi si conservano le diagnosi disponibili e il codice di uscita.

Variabili opzionali: `HFGW_RUN`, `HFGW_MAX_EVENTS`, `HFGW_INPUT_PATH`,
`HFGW_REPO_ROOT`, `HFGW_CVMFS_ROOT`, `HFGW_RUNTIME_ROOT`, `HFGW_SCRATCH_ROOT`
e `HFGW_ANALYSIS_SCRIPT`. La directory scratch predefinita usa `SLURM_TMPDIR`
quando presente, altrimenti `/tmp/$USER`.

```bash
squeue -u "$USER"
sacct -j JOBID --format=JobID,JobName%20,Partition,State,ExitCode,Elapsed,NodeList%30
cat "$HOME/slurm_logs/JOB_JOBID.out"
```

Le direttive `#SBATCH` dei vecchi script usano `/home/mazzitel/slurm_logs`: creare
la directory prima di `sbatch`; se si usa un altro account, adattare tali direttive.
`jobtest.sh` è il vecchio test diagnostico, non l'entrypoint del nuovo flusso.

## Clone HPC con conflitto dopo stash apply

Conservare la versione locale e lo stash, già creati prima del pull. Per adottare
il payload integrato, salvare anche il file con i marcatori e poi ripristinare
solo quel percorso prima del fast-forward:

```bash
cp -p examples/hpc/job.sh "$HOME/job-hpc-conflict-backup.sh"
git restore --source=HEAD --staged --worktree -- examples/hpc/job.sh
git pull --ff-only origin main
```

I locali `job_proxy.sh` e `test_gfal.sh` non vengono toccati: il nuovo test ha
un altro nome. Non riapplicare lo stesso stash al payload integrato, perché
reintrodurrebbe il conflitto. Mantenerlo come archivio finché i test sulla
facility non sono conclusi. Questa correzione è verificata con simulazioni
locali; la prova effettiva sui worker LAN va eseguita sulla facility.
