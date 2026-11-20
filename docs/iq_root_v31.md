# Run3 ROOT v3.1

## Inventario del MIDAS TWPA 1422

Job GFAL in sola lettura 4201. Il rapporto per evento, con esempi, seriali,
intervalli timestamp, dimensioni e valori ODB, è in
`/tmp/flash-root-inventory.RcyBIV/results/inventory.json`. Timestamp MIDAS
in secondi Unix. Per payload e inventario ROOT si conserva il tipo MIDAS
numerico e si collega ogni bank all'header tramite l'indice di evento.

| Equipment (ID) | Bank (tipo) | Contenuto | Eventi | Byte/evento; totale | HDF5 v3 | ROOT v3.1 |
|---|---|---|---:|---:|---|---|
| LocalOscill (7) | LOSC (DOUBLE, 10) | Otto setpoint LO/pump, frequenze e impostazioni di uscita | 1 | 64; 64 | Solo campi analoghi dal BOR | Payload originale e BOR/EOR |
| Temp_Mercury (10) | INPT (FLOAT, 9) | 13 valori, schema ODB | 12 | 52; 624 | Sì | Gruppo termometri e bank esatta |
| Temp_FP (11) | INPT (FLOAT, 9) | 20 valori, schema ODB | 12 | 80; 960 | Sì | Gruppo termometri e bank esatta |
| Temp_AVS (12) | INPT (FLOAT, 9) | 25 valori, schema ODB | 12 | 100; 1200 | Sì | Gruppo termometri e bank esatta |
| timestampGPS (2) | TGPS (BYTE, 3) | 80 byte di riferimento GPS | 212 | 80; 16960 | Payload e timing | Payload e header esatti, timing v3 |
| NetBox (1) | SPE0–SPE5 (WORD, 4) | 1.048.576 campioni ADC per canale | 1000 ciascuna | 2097152; 2097152000 ciascuna | Osservabili elaborati | Osservabili, inventario e header; esclusione dei campioni raw |
| NetBox (1) | SPGP (DWORD, 6) | 790 vuote, 209 coppie e una parola singola | 1000 | 0/4/8; 1676 | PPS decodificabili e diagnostica | Tutti i payload, anche vuoti o incompleti |
| MIDAS (0x8000) | BOR | Snapshot ODB byte per byte | 1 | 1086305 | ADC, LO, mapping e altri campi selezionati | Integrale, SHA-256 e indice evento |
| MIDAS (0x8001) | EOR | Snapshot ODB byte per byte | 1 | 1085303 | Flag EOR | Integrale, SHA-256 e indice evento |
| CryoSwitch (4), SA (5), VNA (6) | — | Equipment configurati in ODB | 0 | 0 | Configurazione VNA/SA non riportata | Snapshot e metadati di calibrazione |

Nel transitorio 1145 era presente SPE6 e v3 ne conserva la misura di PPS.
Nel 1422 il canale è assente. Il nuovo schema mantiene l'inventario quando
SPE6 compare e il risultato del detector, in coerenza con l'esclusione delle
forme d'onda ADC. SPEC legacy è esclusa allo stesso modo. Le altre bank,
anche sconosciute, sono archiviate come bytes originali. Header, indice,
nome, tipo e dimensione permettono la decodifica successiva. Nessuna
interpolazione o precisione PPS–UTC nuova.

## Calibrazioni

- BOR VNA: riferimenti nominali 8.744560, 8.787249 e 8.846287 GHz. Le
  variabili VNA includono S21, 2001 punti, span 2 MHz, IFBW 300 Hz e –58 dBm.
  Il blocco `vnaCalib` contiene 2001 valori per componente reale e
  immaginaria delle tracce S11/S12/S21/S22, con date ODB differenti. Le
  copie numeriche compatte sono navigabili in `Calibration/measurements`.
- `VNA/Fit` conserva richiesta con f0, Q0, beta1/beta2 e ampiezze, risultato
  e riferimenti. Il modello/guess della richiesta non costituisce un Q
  misurato. Si conserva il risultato originale senza assegnarlo a più
  modi: il riferimento esplicito osservato riguarda Mode3.
- Pump effettivamente registrato in BOR: abilitato, 7,891 GHz e –6,1
  (campo ODB power Pump). `With_TWPA=True`. `twpaCalib` conserva limiti
  della scansione, massimo S21 ODB 23,693951 e condizioni del massimo.
  Il massimo della mappa non è una curva di guadagno applicabile alla PSD.
- Nessuna bank di traccia VNA, tono iniettato o misura di campo magnetico
  è presente nel 1422. Lo snapshot include setpoint LO/pump, configurazione
  VNA e attenuazione SA, senza dimostrare la misura in-run del guadagno,
  dell'attenuazione complessiva o di B. I riferimenti non osservati sono
  lasciati mancanti. L'audit storico delle coordinate è in
  [frequency_coordinates_run680_audit.md](frequency_coordinates_run680_audit.md).
- GFAL ha elencato 106 file in `flash/data/LNF/calib/`. I tre riferimenti
  Mode3 in `VNA/Fit/Output` e la mappa
  `twpaPumpMap_LocalOscill_2026-11-19_12-04-23.txt` esistono per basename
  esatto. ROOT registra snapshot, percorso ODB, stringa originale, URL,
  stat e Adler32. File privi di legame esplicito rimangono non associati;
  una data vicina non basta a identificarli. I file esterni non sono
  incorporati. La convenzione nominale IF/RF usa solo la mappa prevista
  dal modello documentato e riporta l'indisponibilità se incompatibile.
- Scala ADC e I/Q provengono dal BOR e dalla configurazione esplicita;
  la PSD resta in V²/Hz all'ADC. Nessuna correzione RF o conversione in strain.

L'estensione archivia circa 2,19 MB prima degli indici e delle copie
numeriche compatte, prima di ZSTD. I raw ADC originali esclusi pesano
12,58 GB non compressi. Poiché gli HDF5 v3 non contengono gli ODB integrali,
per la migrazione si rigenera dai raw con **lo stesso** codice scientifico
e si confrontano byte per byte tutti i dataset HDF5 esistenti prima della
pubblicazione ROOT. Il percorso è lo stesso della produzione nuova e non
richiede un ulteriore backfill dei termometri.

## Layout e lettura

TTrees nativi con ZSTD 4, chiavi `Acquisition`, `Calibration`,
`TM010`/`TM011`/`TM012`, `Timing`, `Thermometers`, `SlowControl`,
`ODB`, `Provenance`. Per esempio `TM010/Spectra/window_psd` è una riga
per finestra e `Acquisition/SpectralAxes/window_bin_edges_hz` contiene
i bordi condivisi. `short_rectangular` e `short_hann` usano l'asse
`Acquisition/ShortFFT/frequency_hz`. Le statistiche, anomalie e istogrammi
restano tipizzati. Il TObjString `__iq_schema__` conserva dtypes e
attributi esatti e mappa i nomi logici compatibili con il lettore comune.
Le cartelle `Attributes` (oggetti TObjString) sono consultabili in TBrowser.
I dati vengono salvati una volta sola: la visualizzazione usa gli alberi
e gli assi, senza duplicare le PSD in istogrammi.

```bash
PYTHONPATH=/path/to/uproot:examples python examples/analyze_iq_run.py /local/run01422_iq_v3.1.root /local/run1422-report
PYTHONPATH=/path/to/uproot:examples python examples/analyze_iq_history.py /local/staged --output /local/history
```

Fornire file locali già trasferiti dal worker, in ROOT o HDF5. Le tabelle
di calibrazione e l'inventario delle bank sono nel JSON del singolo run;
la storia usa quantità lineari e gruppi con coordinate compatibili.

## Rilascio e migrazione

Il passaggio richiede il test ROOT reale riuscito con ricevuta GFAL.
Lo schema ROOT usa `runNNNNN_iq_v3.1.root` in Run3, mentre gli HDF5
mantengono il loro nome. La modalità ROOT si attiva localmente nel file
configurazione con `output_format: "root"`, `root_dependencies` e
`root_dependencies_sha256`. Il pacchetto Uproot per Python 3.9 va copiato
sul filesystem locale della UI e viene trasferito come dipendenza software
da 4,3 MB. Al worker rimangono download, pubblicazione GFAL e token t1.
Nello spool rientrano solo ricevute e log.

La normale produzione mantiene i suoi limiti 20/20. Il percorso
`--migrate-root` usa un runtime separato, lo stesso lock di produzione,
lo stesso ciclo e `migration_max_active` (default 40). Seleziona i finali
HDF5 verificati e usciti dalla coda cui punta ancora il foglio. I job HDF5
già sottomessi conservano il proprio URL atteso e diventano eleggibili
dopo la chiusura. Per ciascuna migrazione verificata si aggiornano
`reco_version` e `reco_output_path`, mantenendo `reco_done`.

```bash
autoreco/run_autoreco_cron_configured.sh --run3 --migrate-root --dry-run
autoreco/run_autoreco_cron_configured.sh --run3 --migrate-root
```

Ripetere il ciclo di migrazione per riconciliare e riempire gli slot.
Il cron ordinario non richiede modifiche. Monitorare le directory
`production` e `root-migration` nel runtime Run3, e la coda
`condor_q -constraint 'FlashRun3Attempt isnt undefined'`.

## Consolidamento soltanto in dry-run

```bash
PYTHONPATH=autoreco:/cvmfs/mazzitel-personalrepo.infn.it/package/python3.9/site-packages \
  /usr/bin/python3 autoreco/root_storage_dry_run.py \
  --output /tmp/run3-consolidation.json --export-evidence-requests /tmp/run3-gfal-checks.json
```

Il rapporto distingue assenti, incompatibili, non validi e verificati;
le colonne di cancellabilità esigono checksum recenti in un'evidenza
prodotta sul worker (modalità `--worker-evidence`), corrispondenza
scientifica e logbook già aggiornato. Passare il JSON restituito dal
worker a `--remote-evidence` per stimare i byte effettivamente
recuperabili e riconoscere nomi o temporanei residui. Senza evidenza
aggiornata risultano zero byte eliminabili. Nessun comando elimina i raw
o gli HDF5.

## Esito reale e comando di rilascio

Il test 4202 sul MIDAS 1422 ha concluso con exit code zero. Tempo sullo
slot 642 s, analisi 370,51 s e conversione/validazione/pubblicazione 32,02 s.
Il ROOT pesa **156.901.974 B**, Adler32 locale/remoto **721868e3**.
Sono identici tutti i **43 dataset HDF5 esistenti** e tutti i **67 dataset**
del round-trip. L'archivio conserva 1.251 header, 7.249 record di bank,
21.484 byte di payload ausiliario, entrambi gli ODB e 12 letture per
ciascuna delle tre famiglie. Il test finale è stato aperto dal worker
con uproot; ROOT C++ e PyROOT hanno letto il layout nativo in locale
su un file di verifica ricavato dal 1148. Non è una seconda esecuzione
end-to-end. La ricevuta operativa si trova in
`/tmp/flash-root31-e2e.5LBPzL/01422/publication.json`.

Il rilascio manuale verifica ricevute e SHA-256 della dipendenza e
applica il fast-forward sotto il lock esistente, conservando gli altri
campi della configurazione. Il cron attivo userà il nuovo formato
dal ciclo successivo e i job già in coda manterranno il loro formato.

```bash
/tmp/flash-run3-root31-release/autoreco/activate_root31.sh \
  /tmp/flash-root31-e2e.5LBPzL/01422 \
  /tmp/flash-root31-build/uproot-py39.tgz
```

Per avviare il loop di migrazione dalla UI dopo il rilascio:

```bash
while /home/mazzitel/HFGW/analysis/autoreco/run_autoreco_cron_configured.sh --run3 --migrate-root; do
  sleep 60
done
```

L'anteprima reale ha selezionato 272 run e 40 job iniziali, senza scrivere
il foglio. L'HDF5 verificato in questa fotografia ammonta a 51,24 GB
potenziali. Il dry-run di consolidamento senza le verifiche remote
successive alla migrazione classifica zero byte eliminabili.
