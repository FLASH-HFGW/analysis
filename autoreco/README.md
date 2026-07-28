# Autoreco

`autoreco.py` lavora a passate ed è adatto a essere richiamato da cron:

1. recupera i job HTCondor già sottomessi;
2. trasferisce e verifica quelli completati;
3. aggiorna `reco_done` sul Google Sheet;
4. sottomette solo i run ancora necessari e senza un job attivo;
5. salva lo stato in `job_to_submit/RUN/job_state.json`.

La versione richiesta viene letta da `reco_requested_version` (oppure
da `--reco-version`, con default `1.0`). Dopo un job riuscito viene salvata
in `reco_version`.

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

Per risottomettere esplicitamente un job terminato con errore:

```bash
./run_autoreco_cron.sh --run 900 --retry-failed
```

Lo stato del tentativo fallito viene conservato nella directory del run.

## Crontab

Creare prima la directory dei log:

```bash
mkdir -p /home/mazzitel/HFGW/analysis/autoreco/logs
```

Quindi aggiungere con `crontab -e`:

```cron
*/5 * * * * /home/mazzitel/HFGW/analysis/autoreco/run_autoreco_cron.sh --run-min 0 >> /home/mazzitel/HFGW/analysis/autoreco/logs/autoreco.log 2>&1
```

Non usare `&` nella riga cron: cron avvia già il comando senza terminale.

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
