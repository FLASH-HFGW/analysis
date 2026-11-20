# Runbook finale Run3 ROOT v3.1

La definizione scientifica è congelata a `f91b99b`. Il branch locale
`autoreco-run3-root31-release` aggiunge solo il rilascio e il ciclo automatico.
L'esito del test reale, lo schema e l'inventario sono in
[iq_root_v31.md](iq_root_v31.md).

## Attivazione dalla shell PSGE

La dipendenza con SHA-256 verificata e le ricevute del test 1422 sono già
nella directory locale ext4 `/home/mazzitel/HFGW/analysis-runtime/autoreco/Run3/root31`.
La procedura legge lo script direttamente dal branch Git locale.

```bash
set -o pipefail
repo=/home/mazzitel/HFGW/analysis
runtime=/home/mazzitel/HFGW/analysis-runtime/autoreco/Run3

git -C "$repo" show autoreco-run3-root31-release:autoreco/activate_root31.sh |
  bash -s -- "$runtime/root31/validation-1422" "$runtime/root31/uproot-py39.tgz"
```

Il rilascio verifica ricevuta, versione e SHA-256, applica il fast-forward
sotto il lock di produzione e aggiorna atomicamente solo le chiavi ROOT
della configurazione locale. Conserva gli altri valori, compresi
`enabled`, i limiti ordinari 20/20, mapping e retry. L'adozione del 1422
usa la ricevuta già valida e richiede che il riferimento HDF5 corrente
corrisponda ancora a quello usato dal test. Gli altri stati e i payload
HDF5 già nel Condor spool mantengono la loro destinazione originale.
Da quel momento ogni nuovo job normale staggia il codice dal checkout
attivo e la dipendenza dal runtime persistente; lo scratch del worker
serve soltanto durante il job. Il percorso `/tmp` resta estraneo
all'esecuzione della produzione.

## Cron, avvio e monitoraggio

Usare la voce esistente, già installata:

```cron
*/5 * * * * /home/mazzitel/HFGW/analysis/autoreco/run_autoreco_cron_configured.sh --run3 --cron
```

Il cron esegue prima la produzione (20 slot), poi riconcilia e riempie
fino a 40 slot di migrazione, sotto lo stesso lock ma con runtime e contatori
separati. Il primo tick dopo l'attivazione avvia entrambe le code. Quando
la coda si svuota il ciclo resta disponibile per gli ultimi HDF5 in arrivo
e smette di sottomettere appena non ci sono più finali HDF5 eleggibili.
I job HDF5 già in esecuzione entrano nel ciclo appena riconciliati, con
coda chiusa e destinazione HDF5 registrata nel logbook. Le righe ROOT
già verificate escono dalla discovery. Solo la verifica del finale ROOT
abilita l'aggiornamento di versione/percorso; la migrazione preserva
`reco_done`.

```bash
wrapper=/home/mazzitel/HFGW/analysis/autoreco/run_autoreco_cron_configured.sh
runtime=/home/mazzitel/HFGW/analysis-runtime/autoreco/Run3
tail -f "$runtime/logs/autoreco-$(date +%F).log"
condor_q -constraint 'FlashRun3Attempt isnt undefined' -af ClusterId JobStatus HoldReason FlashRun3Attempt
"$wrapper" --run3 --migrate-root --dry-run
```

Un ciclo manuale immediato facoltativo usa `"$wrapper" --run3 --cron`.
Il dry-run distingue i run eleggibili, quelli in attesa, i job pianificati
e gli aggiornamenti proposti al logbook. Un run in attesa può essere ancora
in acquisizione o privo di una ricevuta HDF5 definitiva. Non usare una
seconda voce cron o un loop in terminale.

## Fallimenti

Per un run consultare `$runtime/root-migration/NNNNN/job_state.json`
e i log dell'identificativo `attempt`. Confrontare `condor_q CLUSTER.0`
e `condor_history CLUSTER.0 -limit 1 -af JobStatus ExitCode`.
Il ciclo ritenta i fallimenti terminali fino a `max_attempts`. Gli Held
restano protetti finché si chiarisce la causa e si decide il rilascio o
la rimozione dell'esatto job. Prima di rimuovere un Held verificare lo
stato e l'eventuale ricevuta. Al tick successivo il ciclo riconcilia la
history. Per tentativi esauriti, correggere la causa e approvare
esplicitamente un aumento del limite configurato. In caso di submit
ambiguo, riconciliare l'identificativo del tentativo con coda/history
prima di ritentare. Conservare file di stato e prodotto canonico.

## Analisi locale

Per Python 3.9 estrarre la dipendenza persistente in una directory
locale e usare i pacchetti scientifici CVMFS come nel worker. I file
scientifici devono essere già disponibili localmente.

```bash
repo=/home/mazzitel/HFGW/analysis
runtime=/home/mazzitel/HFGW/analysis-runtime/autoreco/Run3
mkdir -p "$runtime/root31/python"
tar -xzf "$runtime/root31/uproot-py39.tgz" -C "$runtime/root31/python"
export PYTHONPATH="$runtime/root31/python:/cvmfs/sft-flash.infn.it/package/python3.9/site-packages"
python3.9 "$repo/examples/analyze_iq_run.py" /local/run01422_iq_v3.1.root /local/report-1422
python3.9 "$repo/examples/analyze_iq_history.py" /local/staged --output /local/history
```

## Completamento e consolidamento futuro

Il completamento richiede: nessun HDF5 precedente ancora attivo, nessun job
di migrazione attivo, zero eleggibili nel dry-run e nessun HDF5 verificato
con ROOT mancante, incompatibile, non valido o disallineato nel logbook.
Controllare anche i falliti, perché esaurire i retry non dimostra
completamento.

```bash
repo=/home/mazzitel/HFGW/analysis
runtime=/home/mazzitel/HFGW/analysis-runtime/autoreco/Run3
out="$runtime/root31"
export PYTHONPATH="$repo/autoreco:/cvmfs/mazzitel-personalrepo.infn.it/package/python3.9/site-packages"
/usr/bin/python3 "$repo/autoreco/root_storage_dry_run.py" \
  --output "$out/consolidation.json" --export-evidence-requests "$out/gfal-checks.json"
jq '[.runs[] | select(.hdf5_candidate != null and (.status != "root_verified" or (.logbook_current | not)))]' \
  "$out/consolidation.json"
```

Per una futura stima con checksum recenti, passare `gfal-checks.json`
a `root_storage_dry_run.py --worker-evidence` su un worker con t1 e
rileggere il risultato locale con `--remote-evidence`. Il dry-run
verifica logbook e ricevute e elenca HDF5 eleggibili e temporanei senza
rimuoverli. HDF5 e raw MIDAS vengono conservati; una cancellazione
richiederebbe un'altra autorizzazione.

**Operazione ancora necessaria:** eseguire una volta il comando di
attivazione dalla shell PSGE. Il cron e la produzione attiva non sono
stati modificati durante la preparazione.
