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
BEARER_TOKEN=$(oidc-token flash --time=3600)
export BEARER_TOKEN
sbatch --export=ALL,BEARER_TOKEN examples/hpc/test_gfal_direct.sh
```

Questo test richiede una CPU, non una GPU, e controlla l'accesso alla directory
CNAF con `gfal-ls`. Per verificare anche il download, impostare esplicitamente
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
export HFGW_RUN=388
export HFGW_MAX_EVENTS=100
sbatch --export=ALL,BEARER_TOKEN examples/hpc/job.sh
```

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
