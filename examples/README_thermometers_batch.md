# Termometri in batch — run 680–939

La campagna usa 260 job HTCondor indipendenti. Ogni job scarica un solo MIDAS
in scratch, estrae INPT e restituisce un piccolo ZIP tramite la spool HTCondor.
Non pubblica file su GPFS. Richiede 1 CPU, 2 GB di memoria e 40 GB di scratch.
Il controllo locale limita le sottomissioni a quattro job simultanei, recupera
i risultati e produce il CSV unico dopo la verifica di tutti i 260 run.

La directory locale predefinita della campagna è:

`/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/thermometers_batch_00680_00939/`

Questa directory è distinta dall'estrazione interattiva: non si condividono né
CSV né SQLite. Non eseguire entrambi i flussi per gli stessi run senza motivo:
verrebbero letti gli stessi input due volte. Il risultato del batch resta nella
directory batch e non sovrascrive il CSV dell'esecuzione interattiva.

## Comandi

Dalla directory del repository, preparazione senza sottomettere:

```bash
bash examples/run_thermometers_batch.sh prepare
```

Il programma congela in `sources/` una copia dei sorgenti con SHA256 e prepara
directory e submit separati per run. Rilanciare `prepare` non azzera gli stati.
Per un altro intervallo usare sia `--run-range START END` sia una nuova
`--campaign-dir /percorso/locale/campagna`.

Quando si desidera effettivamente avviare la coda:

```bash
bash examples/run_thermometers_batch.sh watch --submit --max-active 4
```

Il controllo va lasciato attivo in un terminale persistente. Non usa CPU per
l'analisi: ogni 60 secondi controlla la coda, recupera i job completati e riempie
gli slot disponibili. Senza `--submit` recupera soltanto quelli già inviati.
`--once` esegue un solo ciclo. `--poll-seconds N` cambia l'intervallo.
L'autenticazione richiesta da HTCondor va completata prima delle sottomissioni.
Ctrl+C ferma il controllo locale; i job già in coda continuano e vengono
ritrovati al riavvio del controllo, anche dopo una chiusura imprevista.

Stato locale, senza sottomettere o contattare i worker:

```bash
bash examples/run_thermometers_batch.sh status
```

Il file `status.json` contiene l'ultimo riepilogo del controllo. Per ogni run
sono conservati `job_state.json`, submit, log e risultati. I pacchetti recuperati
sono in `NNNNN/results/runNNNNN_thermometers.zip` e includono CSV, SQLite,
schema, report e `job_result.json` con run, URL di provenienza e checksum.

## Unione finale

L'unione parte automaticamente solo quando tutti i run sono completi.
Può essere richiesta anche esplicitamente:

```bash
bash examples/run_thermometers_batch.sh merge
```

Risultato:

`thermometers_batch_00680_00939/thermometers_00680_00939.csv`

Il CSV contiene tutte le osservazioni ordinate per tempo e la colonna `run`.
I percorsi temporanei dei worker sono sostituiti dagli URL degli input originali.
Il merge ricostruisce un SQLite unico, valida i checksum, la completezza di ogni
input e il run delle osservazioni. Non interpola letture e non duplica righe
se viene ripetuto. Se manca un run, rifiuta il merge e preserva l'output precedente.
`merge_status.json` viene scritto soltanto dopo il completamento dell'unione.

## Errori e nuovi tentativi

Un job held o un pacchetto non valido ferma le nuove sottomissioni; i job già
avviati non vengono interrotti. Consultare log, `job_state.json` e `condor_q`.
Dopo aver risolto la causa, per riprovare soltanto un run fallito:

```bash
bash examples/run_thermometers_batch.sh retry --run 680
bash examples/run_thermometers_batch.sh watch --submit --max-active 4
```

`retry` senza `--run` prepara tutti i falliti. Archivia stato e pacchetto
precedenti sotto `_attempts/`; rimuove dalla coda solo eventuali job del medesimo
run e della medesima campagna. Non altera i risultati completi degli altri run.
