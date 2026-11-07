# SLURM LNF — accesso diretto CVMFS/GFAL

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
