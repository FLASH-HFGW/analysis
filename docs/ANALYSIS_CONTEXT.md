# QUAX/FLASH — Contesto persistente dell'analisi

**Aggiornamento:** 2026-11-22 · baseline 12 (nine conditional RF fits)
**Repository:** https://github.com/FLASH-HFGW/analysis
**Fonti:** risposta finale Codex e trascrizione completa di `validation_report.md` e `validation.json` fornita dall'utente il 22/11/2026. [Review documentale](RUN680_VALIDATION_REVIEW_20261122.md). **I file raw e ROOT remoti non sono stati verificati direttamente da ChatGPT.**

## 1. Workstream separati

- **A — Benchmark Run2–Run3 / run 680:** prodotto ROOT v3.1 di riferimento, secondo Codex generato, validato e pubblicato. **Non modificare il benchmark storico v50** (`v50-homogeneous-comparison`).
- **B — Evoluzione autoreco leggero:** non ancora avviata. FFT ogni 1 s, rilevazione preliminare di anomalie statistiche senza filtri, HDF5 almeno per run. Non mescolare questo sviluppo con il benchmark A.
- Analisi scientifiche TWPA approfondite temporaneamente sospese in attesa di nuove acquisizioni.

## 2. Run 680 — prodotto di riferimento (dichiarato da Codex)

**Input:** `run00680.mid.gz`; MIDAS storico `SPEC`.

**ROOT v3.1 pubblicato:**

`davs://xfer-archive.cr.cnaf.infn.it:8443/flash/analysis/autoreco/Run2-references/root-v3.1/run00680_iq_v3.1.root`

- Dimensione: **155.913.555 byte**
- SHA-256: `498116d3dd22e4d9bb5bb23d5416ff3f75606652da082c0cae7ecdec913ddc89`
- Adler-32: `326612db`
- Schema ROOT: **3.1**
- Commit di riferimento dell'elaborazione: `3fb591aa5da378cc3c4aa1170837b8362e85b03a`
- Rapporti remoti nella medesima directory: `validation_report.md` e `validation.json`.

**Ambiente isolato:** worktree `/home/mazzitel/HFGW/worktrees/run680-root31-reference`; branch `run680-root31-reference-20261122`.

Codex dichiara rispettati i vincoli: nessuna modifica alla produzione Run3, a `autoreco_run3.json`, cron, orchestratore, wrapper, logbook, ROOT/HDF5 pubblicati; nessun altro run elaborato. Il job HTCondor isolato `4820.0` non è partito (`NumJobStarts=0`) ed è stato rimosso; `validation.json` indica elaborazione **isolated UI scratch** (wall 326,836 s; CPU 373,699 s; max RSS 739672 KiB).

## 3. MIDAS SPEC run 680 — convenzioni accertate nel rapporto Codex

- 8 canali `int16`.
- **Mapping storico SPEC:** TM010 **CH0/CH1**; TM011 **CH2/CH3**; TM012 **CH4/CH5** (I/Q rispettivamente). **Non confondere con il mapping di altre campagne/DAQ** riportato in precedenza: TM010 CH0/CH5, TM011 CH1/CH3, TM012 CH2/CH4, CH6 PPS. Le convenzioni sono specifiche del formato/run.
- Scala ADC da BOR: **±2 V**, **4/65535 V/count**.
- Convenzione complessa: **`I - iQhardware`**.
- 5.000.000 campioni/s; 200 ns/campione per le finestre verificate.

## 4. Verifiche numeriche riferite da Codex

- **1.048.576.000 campioni per modo**, **209 finestre complete da 5.000.000**, residuo **3.576.000**.
- **64.000 short FFT** da 16.384 campioni, senza residuo.
- EOR presente; nessun break o salto seriale.
- **210 PPS** con separazione esatta di **5.000.000 campioni**.
- BOR/EOR archiviati integralmente e verificati con SHA-256.
- Termometri: **12 letture per ciascuna famiglia**.
- Round-trip ROOT: **67/67 dataset identici**.
- Errore massimo Parseval: **1,27×10⁻⁷** sulle FFT da 1 s e **7,18×10⁻⁸** sulle short FFT.

### Confronto con benchmark v50

| Modo | RMS v3.1 | PSD con maschera v50 | PSD v50 | Differenza |
|---|---:|---:|---:|---:|
| TM010 | 32,262765 mV | 31,728019 mV | 31,728096 mV | −2,42 ppm |
| TM011 | 20,783883 mV | 20,328180 mV | 20,328172 mV | +0,35 ppm |
| TM012 | 13,733291 mV | 13,452812 mV | 13,452821 mV | −0,68 ppm |

Secondo Codex, medie I/Q, RMS totale e AC, media e deviazione standard di `|z|` coincidono con il riferimento storico dopo scala ADC **2/5** e convenzione del segno Q, con differenze relative ~**10⁻⁹**. I momenti di ordine 3 e 4 sono nel ROOT v3.1 ma non esistono equivalenti scalari lossless nel prodotto storico.

Gli istogrammi di fase, gli incrementi di fase e l'autocorrelazione **lineare** v50 restano benchmark diagnostici separati. Il ROOT v3.1 standard non mantiene le fasi campione-per-campione né le FFT complesse: una ridefinizione di queste osservabili richiede diagnostica distinta sul raw, non una modifica allo schema ROOT v3.1.

## 5. Vincoli permanenti

- **Non modificare la produzione Run3** (checkout, config, cron, orchestratore, wrapper, logbook, dati già pubblicati).
- Usare worktree e branch isolati per nuove elaborazioni.
- Nessun run aggiuntivo senza richiesta esplicita; non pubblicare riferimenti Run2 in area Run3.
- Archiviare risultati verificabili (checksum, percorsi, commit, metodi, report), non credenziali, token o dati raw in Git.
- Non introdurre modifiche allo schema ROOT v3.1 validato senza decisione esplicita.


### Policy storage/I-O FLASH (vincolo permanente, confermato dall'utente il 22/11/2026)

- **GPFS:** destinato **esclusivamente a prodotti scientifici**, in genere file grandi **>100 MB**. La dimensione è un criterio indicativo, non una deroga alla natura scientifica del prodotto: non scrivere log/config/documentazione su GPFS, anche se voluminosi.
- **GFAL:** tutti i **prodotti scientifici generati dai job** devono essere gestiti/pubblicati/trasferiti tramite **GFAL**; non utilizzare il mount `rclone` come meccanismo di pubblicazione dei risultati. Il mount può essere usato in **sola lettura** per accedere a dati scientifici già presenti; se necessario, copiare gli input su scratch locale, senza modificare gli originali.
- **Storage locale:** log, configurazioni, manifest, report, tabelle piccole, figure leggere, script, file di controllo e metadati di esecuzione rimangono **locali**, fuori da GPFS. Il codice e la documentazione appropriata si versionano su Git, senza committare prodotti ingombranti o credenziali.
- I job devono scrivere prima in **scratch isolato** e pubblicare tramite GFAL solamente i prodotti scientifici previsti. Non collocare automaticamente tutti gli output in GPFS.
- Questa regola vale anche per il **pilota Run2–Run3** e prevale sulle indicazioni precedenti troppo generiche su output in area comparativa o sul mount `rclone`.

## 6. Stato e prossime azioni

**A:** produzione run 680 dichiarata completata da Codex; `validation_report.md` e `validation.json` sono stati esaminati attraverso le trascrizioni fornite dall'utente; **verifiche aritmetiche indipendenti sui valori riportati superate** (conteggi, PPS compatibili, relazioni RMS-varianze, differenze ppm). La review integrale è in [RUN680_VALIDATION_REVIEW_20261122.md](RUN680_VALIDATION_REVIEW_20261122.md). **Rimane facoltativa la verifica read-only di esistenza/checksum del ROOT remoto**. Nessuna ricostruzione ulteriore richiesta.

**B:** discutere la nuova autoreco leggera, una volta chiuso il controllo documentale: specificare HDF5, FFT 1 s, semantica statistiche/anomalie, prestazioni della lettura MIDAS e distinzione delle convenzioni tra `SPEC` e Run3. Non anticipare implementazione senza piano.

**Procedura di handover:** dopo nuovi risultati scientifici aggiornare data, provenienza, branch/commit, percorsi, numeri, osservabili, incertezze e prossima azione su questo file, con nuovo commit sul branch documentale. Non presentare risultati solo riferiti da Codex come verificati direttamente da ChatGPT.

## 7. Pilota comparativo Run2–Run3 — completato secondo Codex (22/11/2026)

**Fonte:** rapporto sintetico di Codex inoltrato dall'utente; i prodotti locali indicati non sono stati aperti direttamente da ChatGPT. **Run analizzati esclusivamente:** 680 (Run2), 1148 (Run3-A 1148–1422), 1429 (Run3-B dal 1429). Sono *casi pilota*, non campioni dimostrati rappresentativi delle campagne.

**Worktree:** `/home/mazzitel/HFGW/worktrees/run2-run3-pilot`; branch `run2-run3-pilot-design-20261122`. Rapporto `comparison/root-pilot/REPORT.md`, figure in `comparison/root-pilot/figures/`, tabelle `comparison/root-pilot/tables/{statistics,line_candidates}.csv`, manifest `comparison/root-pilot/manifest.json`. Tutti i percorsi sono locali: non assumere che i file siano già su GitHub.

**RMS totale, mV, calcolato su 209 finestre complete:**

| Modo | Run 680 | Run 1148 | Run 1429 |
|---|---:|---:|---:|
| TM010 | 32,2627 | 22,7850 | 22,7870 |
| TM011 | 20,7839 | 14,7795 | 14,7899 |
| TM012 | 13,7333 | 8,0356 | 9,1010 |

**Variazione della potenza integrata Run 1429 vs 1148**, dichiarata da Codex: TM010 **+0,0175%**, TM011 **+0,1408%**, TM012 **+28,2746%**. Spettralmente: in TM010, 1148 presenta strutture strette fortemente ridotte in 1429, con fondo simile; in TM012, 1429 presenta un livello broadband maggiore. Sono osservazioni **al piano ADC**, non conclusioni sull'origine fisica del rumore.

**Qualità e risorse dichiarate:** schema/convenzioni e copie SHA-256 verificati da Codex; Parseval max circa `1,27e-7`; due comandi scientifici ~15 s, RAM max 660 MiB, file copiati 469,7 MB, spazio finale ~457 MiB. Nessun raw MIDAS, nessun HTCondor, nessuna modifica produzione. Traffico fisico GPFS non direttamente misurato.

**Limitazioni:** ROOT standard non conserva distribuzioni I/Q, fasi per campione, incrementi di fase e ACF lineare. Il benchmark completo v50 su questi osservabili non è ancora replicato; richiede diagnostica raw separata o prodotti storici già esistenti. Non dichiarare completata quella parte del confronto.

**Prossime attività:** esaminare `REPORT.md`, `statistics.csv` e `line_candidates.csv` (eventualmente tramite push sul branch del pilota, senza dati grandi); valutare numericamente le caratteristiche delle righe TM010 e del rumore TM012, le bande e differenze di hardware/guadagno. Solo dopo definire estensione temporale alle campagne e diagnostica di fase/ACF. Applicare sempre la policy GPFS/GFAL/locale.

## 8. Audit calibrazione pilota 680 / 1148 / 1429 — Codex, 22/11/2026

**Fonte:** risposta Codex inoltrata dall'utente; rapporto completo locale `/home/mazzitel/HFGW/worktrees/run2-run3-pilot/comparison/root-pilot/CALIBRATION_AUDIT.md`, **non letto direttamente** da ChatGPT.

- Codex non ha rilevato errori nella conversione ADC: **ogni run usa BOR del proprio input**, con scale I e Q lette separatamente. Il pilota legge i valori in volt già archiviati nel ROOT, **non riapplica** il fattore del run 680 e non applica correzioni RF. La verifica è su codice e metadati, senza nuova conversione dal raw.
- Tutti e tre i run: TM010 CH0/CH1, TM011 CH2/CH3, TM012 CH4/CH5; intervallo ADC **±2 V per canale**, `4/65535 V/count = 61.0361 µV/count`, campionamento **5 MHz**, convenzione `z=I-iQhardware` (risultato specifico dei tre run verificati, da non generalizzare ad altri run).
- **Run 680:** pump spento; tracce VNA presenti; nessuna calibrazione end-to-end verificata.
- **Run 1148:** pump acceso, `With_TWPA=True`; mappa pump e riferimenti VNA Mode3 documentati; non bastano per definire un guadagno end-to-end dei tre modi.
- **Run 1429:** pump acceso, `With_TWPA=True`; mappa pump documentata; tre riferimenti esterni del fit Mode3 precedentemente segnalati come non reperiti; **l'audit successivo li ha ritrovati**.
- **Non** usare il massimo S21 della TWPA come guadagno di calibrazione applicabile automaticamente alla PSD. `Input_Atten=0` della spectrum analyzer **non** equivale ad attenuazione nulla della catena I/Q.
- Risultati RMS/PSD, istogrammi `|z|` e righe spettrali del pilota confrontabili **solo al piano ADC**, con bande e campioni dichiarati. Non dedurre da essi temperatura di rumore, rumore intrinseco della cavità o sensibilità riferita all'ingresso in assenza di risposta end-to-end per run, modo e frequenza.
- **Conseguenza essenziale:** differenze tra run 680 (pump OFF) e Run3 (pump ON) sono confondibili con il cambiamento della catena RF. Anche TM012 1148→1429 (+28,2746% potenza ADC) non dimostra da sola un cambiamento del rumore fisico.
- Nessuna correzione numerica necessaria al confronto **ADC**; nessuna modifica di prodotti originali. Prima dell'interpretazione fisica: recuperare eventuali curve calibrate di trasferimento/guadagno e condizioni RF.

## 9. Chiarimento hardware: primo stadio FET vs TWPA (22/11/2026)

**Conferma diretta dell'utente:** nelle acquisizioni precedenti, incluso il periodo di Run2 di riferimento, il primo stadio di amplificazione era un **FET**, installato **al posto del TWPA guasto**. Per Run3 (1148 e 1429), i metadati indicano `With_TWPA=True` e pump acceso. **La tesi di Valeria** è indicata dall'utente come fonte storica, ma il testo della tesi non è stato letto direttamente durante questo aggiornamento: non attribuirle valori numerici non verificati.

**Implicazione:** la differenza Run2/Run3 riguarda la **catena analogica di amplificazione**, non solo pump ON/OFF. Non interpretare differenze di RMS/PSD al piano ADC come variazioni di rumore della cavità. Per eventuali correzioni servono guadagno end-to-end e/o noise temperature riferiti a un piano dichiarato, per modo/frequenza/configurazione. Controllare, in sola lettura, le calibrazioni in `/home/mazzitel/flash-data/data/LNF/calib/`; non confondere S21 del solo TWPA con transfer function complessiva.

## 10. Provenienza delle misure VNA per run — verifica richiesta

L'utente segnala che **le bank MIDAS** dovrebbero riportare **l'ultima misura VNA valida**. Questa informazione è **da verificare** in BOR/ODB/bank e nei metadati ROOT, senza dedurre validità da un semplice riferimento o dalla data del file. Per run 680, 1148 e 1429: risalire per ciascun modo a riferimento VNA (timestamp, file, percorso, configurazione), riconciliarlo con `/home/mazzitel/flash-data/data/LNF/calib/`, e distinguere l'ultimo riferimento archiviato dalla calibrazione effettivamente applicabile (FET/TWPA, pump, piano di misura, frequenze). Verificare in particolare i tre riferimenti esterni Mode3 del 1429 segnalati come non reperiti. Nessuna correzione PSD prima della verifica.

## 11. Risultato audit VNA (Codex, 22/11/2026)

**Fonte:** resoconto Codex fornito dall'utente; rapporto completo locale `/home/mazzitel/HFGW/worktrees/run2-run3-pilot/comparison/root-pilot/VNA_REFERENCE_AUDIT.md`, CSV `tables/vna_references.csv`, inventario `vna_file_inventory.json` — **non letti direttamente in questa sessione ChatGPT**.

- Le misure VNA individuate **coprono la frequenza nominale del rispettivo modo**, ma **nessuna è dimostrata calibrazione end-to-end cavità→ADC**: routing, piano di misura, configurazione FET, condizioni della catena non sono verificati.
- **Nessuna bank contenente una misura VNA** negli inventari dei tre run; le tracce provengono dagli **snapshot ODB**. La sezione VNA di BOR/EOR è invariata, salvo `Statistics`.
- **I riferimenti esterni Mode3 del run 1429 risultano ora presenti**; la precedente segnalazione di assenza è superata.
- **S11** mostra aggiornamento del **16 luglio** in tutti e tre i run: non prova una nuova acquisizione VNA durante Run3.
- **Anomalia critica da verificare:** nei run 1148 e 1429 gli array ODB denominati `Real/Imag` corrispondono a sequenze **interlacciate e sfalsate** rispetto alle colonne separate dei file calibrazione. Non trattare tali array ODB come risposta complessa prima di aver chiarito schema e ordine dei dati.
- Non applicare correttivi alle PSD dei ROOT; i confronti esistenti restano soltanto in unità ADC.

**Prossima azione mirata:** chiedere a Codex di indagare il writer/parser della VNA in ODB e confrontare pochi valori indicizzati dai file sorgente, senza nuovi raw o job; determinare se sia un semplice errore di serializzazione/naming, una disposizione prevista o una discrepanza effettiva. Mantenere distinta questa verifica dalla calibrazione RF end-to-end.

## 12. Riscontro diretto nella tesi di Valeria Spasiano (2026)

**Fonte letta:** `Search for ultralight dark matter with the QUAX-LNF haloscope experiment` (PDF fornito dall'utente, 149 pagine). Riferimenti alla numerazione delle pagine della tesi.

- **§5.3.2, p. 101:** MIDAS equipment VNA/SA; componenti reali e immaginarie delle calibrazioni sono memorizzate nell'**ODB**. Nessuna descrizione esplicita dell'ordine/interlacciamento degli array `Real/Imag` osservato nei Run3.
- **§6.1.1–6.1.2, pp. 105–112:** misure **S21, S22, S12**, componenti reali/immaginarie acquisite dal VNA; il fit simultaneo è svolto sui **moduli**, non direttamente sulle fasi. La tesi **non risolve** la discrepanza di serializzazione ODB: confrontare codice del frontend con file e ODB, senza assumere l'ordine corretto.
- **§6.1.1, p. 105:** dopo il malfunzionamento TWPA viene caratterizzata una configurazione **senza TWPA**, con **G = (67.81 ± 0.39) dB**, **Tn = (3.955 ± 0.468) K**; il riferimento al run 680 e l'applicabilità quantitativa richiedono riscontro sulla configurazione effettiva.
- **§3.3.4, pp. 53–54:** schema di catena con TWPA al livello più freddo, HEMT a 4 K e **FET a temperatura ambiente**, posto dopo lo stadio criogenico. **Correzione del linguaggio precedente:** non dare per dimostrato che il FET abbia fisicamente sostituito il TWPA nella stessa posizione, né che fosse il primo stadio RF; l'utente conferma una configurazione precedente «FET al posto del TWPA» ma va riconciliata con routing e disegno specifici del run 680.
- **§5.2, pp. 94–99:** coefficiente di correzione della risposta in frequenza della down-conversion `k_z(f)` per modo, distinto dal guadagno complessivo della catena RF. Per correzioni fisiche evitare confusione tra queste calibrazioni.

**Azione:** usare la tesi come riferimento per definizioni e metodo; indagare l'ordine degli array ODB nei frontend/parser. Nessuna correzione applicata a PSD o dati pubblicati.

## 13. Anomalia VNA ODB confermata — diagnosi Codex (22/11/2026)

**Fonte:** rapporto Codex inoltrato dall'utente; diagnosi locale `comparison/root-pilot/VNA_LAYOUT_DIAGNOSIS.md` e campioni `comparison/root-pilot/tables/vna_indexed_samples.csv` nel worktree `run2-run3-pilot`, non letti direttamente da ChatGPT.

- Il difetto si presenta in **tutti e tre i run 680, 1148 e 1429**, non soltanto nei Run3.
- Con vettore dei file VNA interlacciato `F=[Re0, Im0, Re1, Im1, …]`, Codex ha verificato `ODB Real[k]=F[k]` e `ODB Imag[k]=F[k+1]`. Soltanto il primo punto corrisponde alle coppie corrette; gli altri mescolano componenti e frequenze.
- Ipotesi tecnica molto forte (non ancora prova sulla versione storica installata): il binding MIDAS Python su CVMFS converte ndarray tramite puntatore `ctypes` **ignorando gli stride NumPy**, quindi viste `buffer[::2]` e `buffer[1::2]` sarebbero serializzate come sequenze contigue sfalsate.
- Il frontend `Calibration.py` scrive `freq,y1,y2` nel file e passa `y1,y2` a `odb_set`; non applica esplicitamente sfalsamenti. Il parser `FitCall.py` costruisce i moduli `sqrt(Re²+Im²)` dalle colonne della stessa riga **del file originale**, non dagli array ODB sospetti: i fit eseguiti per questo percorso **non sono affetti**. La validità di ogni fit storico resta da verificare rispetto alle versioni e sorgenti realmente usate.
- **RMS/PSD e altri prodotti del pilota ROOT rimangono invariati**: nessuna calibrazione VNA era stata applicata.
- **Rimedio proposto ma non applicato:** validare driver e versione effettiva; materializzare array contigui prima dell'ODB write (oppure correggere il binding); eseguire un test round-trip in ODB *isolato*, mai in produzione. Conservare gli array storici originali e documentarne i limiti; per misure VNA complesse usare i file sorgente attendibili.
- Durante l'indagine è comparsa una chiave SSH di test in un output Codex; l'utente ha precisato che si tratta di una chiave di test, senza impatto operativo dichiarato. **Non archiviare alcun materiale della chiave nel repository.**

## 14. Fit RF S12/S21/S22 sui file originali — risultati Codex (22/11/2026)

**Fonte:** resoconto Codex fornito dall'utente; report completo, `fit_summary.csv`, figure e `fit_details.json` rimangono locali nel worktree `/home/mazzitel/HFGW/worktrees/run2-run3-pilot/comparison/root-pilot/rf-calibration/` e **non sono stati letti direttamente** da ChatGPT.

Codex ha svolto **nove fit simultanei** S12/S21/S22 (tre run × tre modi) sui file VNA originali tramite `FitCall.py`, con tre inizializzazioni per caso. Convergenza dei minimi dichiarata, ma **nessuna covarianza accurata**: i parametri sotto sono **descrittivi e privi di incertezze validate**, non misure definitive; cautela speciale per residui TM010. Interpretare `28.649` nella tabella come **28 649** (separatore migliaia italiano) e non come 28,649.

| Run | Modo | Frequenza risonanza (GHz) | Q caricato (nominale, non validato) |
|---|---|---:|---:|
| 680 | TM010 | 8.737118963 | 28649 |
| 680 | TM011 | 8.780840531 | 29771 |
| 680 | TM012 | 8.841180745 | 24515 |
| 1148 | TM010 | 8.744546604 | 16987 |
| 1148 | TM011 | 8.787252190 | 22523 |
| 1148 | TM012 | 8.846293765 | 10177 |
| 1429 | TM010 | 8.744932701 | 22183 |
| 1429 | TM011 | 8.788242547 | 24498 |
| 1429 | TM012 | 8.847077580 | 12412 |

- Fit condizionali secondo le relazioni dei percorsi della tesi: guadagno **L5 ~66,7–67,5 dB** per run 680 e **~75,3–81,1 dB** per i due Run3. **Non** considerare tali numeri una calibrazione cavità→ADC, in assenza di routing, condizioni FET/TWPA durante sweep e risposta conversione RF/IF/ADC.
- Stime di Q intrinseco, accoppiamenti e guadagni restano **condizionali** alle ipotesi del modello. S11 ricostruibile da file storico ma **non associabile con certezza** ai nove casi contemporanei.
- **Decisione:** non dividere le PSD per guadagno L5 né per |S21|²; non modificare ROOT originali o produzione. I fit rimangono diagnostica RF finché non sia verificata una risposta end-to-end nelle condizioni operative.
- **Prossima azione consigliata:** esaminare i report locali tramite versione Git dei **soli documenti e tabelle leggere** oppure riassunto numerico da Codex; valutare residui, robustezza rispetto a inizializzazioni, definizioni dei piani di misura e disponibilità della calibrazione della down-conversion per eventuale interpretazione quantitativa. Nessun nuovo job necessario per il solo esame.
