# Pulizia locale delle campagne noise

`tools/purge_noise_local.py` riconosce le campagne HTC e Slurm dai manifest.
Il comando predefinito produce solo un'anteprima. Non libera job HTCondor,
non rimuove lo spool del servizio e non scrive o elimina nulla su GPFS.

## Cosa viene conservato

* Manifest, sorgenti congelati e loro checksum, riferimento, calibrazione,
  temperature e schema, stati dei run, tentativi, `job_status.json`, ricevute GPFS.
* Tutti i file dei run incompleti, falliti, in hold o in attesa di pubblicazione.
* MIDAS originali, directory montate GPFS/rclone, sorgenti Git, archivi storici,
  slide PDF/PPTX, asset e tabelle dei report. Non sono oggetto di scansione ricorsiva.
* Le copie HDF5 canoniche della campagna finché servono al confronto finale.

## Anteprima

Dalla radice del clone, con Python 3.9 o successivo:

```bash
python3 tools/purge_noise_local.py \
  --campaign "$HOME/HFGW/analysis-runtime/autoreco/Run2/noise_fullrange_v2_20261109"
```

Il riepilogo distingue copie di job, log e prodotti canonici. Il numero di byte
è la dimensione dei candidati, non il risparmio effettivo dopo compressione.
`--report NUOVO_FILE.json` salva anche l'elenco completo e le esclusioni;
il percorso deve essere locale e non esistere già. Di default l'anteprima usa
le ricevute GPFS già verificate; `--verify-remote` esegue anche nuovi download
e controlli SHA-256, senza cancellare file.

I percorsi di cancellazione devono essere sotto `~/HFGW`; con altri layout
si specifica `--local-root /percorso/locale`. Anche con un root esplicito sono
vietati symlink, repository e mount GPFS/FUSE. Il parametro non autorizza una
scansione di file arbitrari: i candidati derivano dai soli stati e nomi previsti.

## Pulizia delle copie duplicate

Quando il monitor è fermo:

```bash
python3 tools/purge_noise_local.py --apply \
  --campaign "$HOME/HFGW/analysis-runtime/autoreco/Run2/noise_fullrange_v2_20261109"
```

Per ogni run completo con ricevuta coerente, lo script verifica l'hash della
copia locale, scarica nuovamente il prodotto remoto con GFAL e ne verifica
lo SHA-256. Solo dopo elimina l'HDF5 duplicato nella directory del job.
La copia canonica nella directory del report rimane disponibile per il merge.

I log dei job riusciti sono compressi in `.gz` con verifica dei byte originari;
le versioni delle librerie, i tempi e le informazioni diagnostiche restano
recuperabili. I log vuoti vengono eliminati e il loro hash rimane nel registro.
Il generatore delle slide legge anche gli stdout compressi. I log globali in
`~/slurm_logs` rimangono fuori da questa pulizia.

Lo script acquisisce lo stesso `watch.lock` del controller: se il monitor è
attivo, `--apply` e `--restore` vengono rifiutati. Non interrompe il monitor o
i job. L'anteprima è invece utilizzabile anche durante una campagna attiva.

## Ritiro delle copie scientifiche canoniche

Il ritiro è possibile soltanto quando **tutti** i run sono completi e il
confronto finale ha una ricevuta GPFS verificata. Prima l'anteprima, poi:

```bash
python3 tools/purge_noise_local.py --retire \
  --campaign "$HOME/HFGW/analysis-runtime/autoreco/Run2/noise_fullrange_v2_20261109"

python3 tools/purge_noise_local.py --retire --apply \
  --campaign "$HOME/HFGW/analysis-runtime/autoreco/Run2/noise_fullrange_v2_20261109"
```

Oltre ai duplicati, questo elimina le copie canoniche HDF5 dei run e del
confronto finale, dopo nuova verifica remota. Non basta la presenza di un file
con lo stesso nome su GPFS: devono coincidere gli hash attesi.

Il registro `local_retention.json` e gli audit in `purge_audit/` conservano
percorsi, hash, dimensioni, destinazioni remote e azioni. Il piano di recupero
è scritto prima delle cancellazioni. Un'interruzione può lasciare una pulizia
parziale, ma i prodotti rimossi rimangono identificabili e recuperabili.

I controller HTC/HPC riconoscono il ritiro e chiedono il ripristino prima di
eseguire nuovamente `watch` o `report`; `status` resta utilizzabile.

## Ripristino e uso sull'HPC

```bash
python3 tools/purge_noise_local.py --restore \
  --campaign "$HOME/HFGW/analysis-runtime/autoreco/Run2/noise_fullrange_v2_20261109"
```

Ripristina da GPFS gli HDF5 canonici e il confronto finale, verificando gli
hash. Non sovrascrive prodotti locali differenti e non ricrea i duplicati dei
job. I log compressi restano leggibili con `gzip -cd FILE.gz`.

Sull'HPC si usa lo stesso script, dopo il pull del software e nell'ambiente
FLASH configurato; per il pilot il parametro è:

```bash
--campaign "$HOME/HFGW/analysis-runtime/autoreco/Run2/noise_temperature_pilot_slurm_v2_20261109"
```

Per `--apply`, `--restore` o `--verify-remote` servono GFAL e credenziali OIDC
FLASH valide. Il token non viene mostrato o scritto nei registri. Lo script
non esegue pubblicazioni: se la copia remota è assente, diversa o inaccessibile,
il controllo fallisce prima di rimuovere i candidati.
