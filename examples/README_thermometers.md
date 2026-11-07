# Estrazione dei termometri da MIDAS

Per la versione con job separati per run e unione finale vedere
[README_thermometers_batch.md](README_thermometers_batch.md).

`extract_thermometers.py` cerca la bank **INPT** nei file MIDAS. La documentazione
allegata e i file reali usano questo nome a quattro caratteri, non `INPUT`.
Legge la mappa Event ID → equipment e i nomi dei canali dall'ODB di ogni file.
Le tre famiglie documentate sono:

| Equipment | Valori numerici nella bank |
|---|---:|
| Temp_Mercury | 13 |
| Temp_AVS | 25 |
| Temp_FP | 20 |

La data in formato stringa dei log originari non fa parte della bank numerica.
Vengono conservati tutti i valori: temperature, resistenze, pressioni, correnti,
stati, canali inutilizzati e tempi interni. Per le due voci dei diodi Mercury
la documentazione dice Ohm nel titolo ma V nella descrizione: l'estrattore non
sceglie un'unità e non esegue conversioni. Le etichette ODB restano nello schema.

## Esecuzione su tutti i file

Dalla directory del repository:

```bash
bash examples/run_extract_thermometers.sh
```

Il wrapper configura le librerie MIDAS da CVMFS. Per default cerca ricorsivamente
`.mid`, `.mid.gz`, `.mid.bz2` e `.mid.lz4` sotto
`/home/mazzitel/flash-data/data/LNF`, senza modificare alcun input.
L'output è esclusivamente locale:

`/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/thermometers/thermometers.csv`

Per scegliere directory, file, intervallo di run o destinazione:

```bash
bash examples/run_extract_thermometers.sh /percorso/dati \
  --run-range 680 939 \
  --output /percorso/locale/thermometers.csv

bash examples/run_extract_thermometers.sh /percorso/run01135.mid.gz \
  --output /percorso/locale/prova.csv
```

`--no-recursive` limita la ricerca al primo livello. `--max-files N` e
`--max-records-per-file N` servono per prove limitate: quest'ultima opzione
marca il file come `limited`, senza dichiararlo completamente elaborato.

## Struttura del CSV

Una riga rappresenta **una bank acquisita**, non un campione interpolato di
tutti gli strumenti. Le colonne degli altri equipment restano vuote.
L'ordinamento finale è cronologico per timestamp dell'evento, anche fra file.

- `time_unix`, `time_utc`: timestamp Unix dell'header MIDAS e corrispondente UTC;
- `run`, `equipment`, `event_id`, `event_serial`, `bank`: provenienza del campione;
- `schema_id`, `source_file`, `source_status`: schema dei canali e stato dell'input;
- `Temp_Mercury__ch00__TIME_seconds`, ecc.: i valori nell'ordine della bank,
  con prefisso dell'equipment e indice a base zero per evitare nomi ambigui.

Il tempo numerico interno di Mercury/AVS è conservato come canale grezzo:
la sua epoca non è specificata nell'allegato. Il programma non lo tratta come
tempo Unix e non lo sostituisce al timestamp MIDAS. I valori float32 della bank
non acquistano precisione aggiuntiva durante l'esportazione.

`thermometers.schema.json` conserva nomi e unità ODB, descrizioni e unità del
documento quando il numero di canali corrisponde. Il `schema_id` di ogni riga
identifica lo schema applicato. Canali aggiuntivi vengono conservati senza
attribuire loro nomi fisici o unità non verificati. Se manca l'ODB, piccoli eventi
INPT vengono comunque conservati con equipment `event_ID` e canali generici;
i piccoli eventi degli altri equipment vengono controllati per non perdere bank
INPT con nomi di equipment diversi; i grandi eventi SPEC non sono decodificati.

## Ripresa e integrità

Il file locale `thermometers.sqlite` è un checkpoint: rilanciando lo stesso
comando i file completi con stessa dimensione e data di modifica non vengono
riletti. `--force` impone la rilettura. Gli input selezionati da quel comando
determinano il CSV esportato; altri file presenti nel checkpoint non vi entrano.

Se un input è troncato o danneggiato, i campioni validi già incontrati restano
nel CSV con `source_status=partial`, e il programma termina con codice 1 dopo
aver esaminato gli altri file. Il report JSON riporta l'errore per ciascun input.
Un nuovo tentativo rimpiazza quelle righe, senza duplicarle. Un'interruzione
mantiene i file già completati, esporta i dati committati e restituisce codice 130.

Nei file compressi saltare le bank SPEC evita la creazione degli enormi array,
ma richiede comunque di decomprimere il flusso attraversato: la scansione di
tutto l'archivio può essere lunga. Il checkpoint serve anche per questo.
Non vengono effettuate sottomissioni in coda né scritture su GPFS.
