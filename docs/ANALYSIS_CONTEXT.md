# QUAX/FLASH — Contesto persistente dell'analisi

## Run 1670 targeted diagnostic · 23 November 2026

- Scientific milestone `3409be09bee5fc085d759a64c0f2139ad5c0ceb5` on the pilot branch. Run 1670 is a separate targeted analysis. Existing Run 1429 and the completed 24-run sample remain intact.
- SHA256-verified ODB and LOSC evidence dates the retune before BOR. On 21 November 2026 UTC the primary RS changed 8,743,664,000 → 8,743,655,000 Hz at 08:21:56, Teledyne CH1 43,331,000 → 43,330,000 Hz at 08:21:59, and CH2 102,179,000 → 102,199,000 Hz at 08:22:02. Run 1670 BOR was 08:24:31. VNA nominal setpoints were written at 08:21:26. The LocalOscill device control path is identifiable from the reference source. Operator versus automatic attribution and the physical application timestamps remain unresolved.
- The validated raw pass produced T7 totals 1244 / 221 / 766 for TM010/TM011/TM012. Full-run moments and 100 ms/1 s exact rates, histograms, sparse tuples and shifted controls are archived. The v50 centered complex ACF and Hann PSD use the first 1.048576 s only.
- The TM012 peak tracked +29 kHz at the boundary, consistent with the image-coordinate displacement. The within-run joint block screen found 18 candidate observable/scan combinations at both block sizes. A common change near 117–119 s lowered mean RMS by about 0.46–0.53% and integrated PSD by about 0.91–1.06%. Neither T7 rate nor the TM012 tracked line ratio passed both exploratory screens. This is a descriptive diagnostic. The archive has a single LOSC snapshot per run and no continuous LO readback.
- One full pass used 9.326 GB and 716.3 s raw wall time. A bounded five-event read supplied the finer prefix constellation. No adjacent raws were processed. Adjacent ROOT data bracket the retune. No full waveforms were retained.
- Separate report under `reporting/tail_coincidence_study/presentation/run1670/` and scientific summary at `reporting/tail_coincidence_study/validation/run1670/REPORT.md`. Open issues are retune attribution, image response versus internal mixing and calibrated channel delays.


## Completed Dataset 2 study · 24 validated Run3-B acquisitions

- Final scientific report commit `93074e1a72a8d1a842267572554b217410c578fb` on `run2-run3-pilot-design-20261122`. All 24 selected runs passed CRC, EOR, raw/ROOT timing, serial, ADC, counts, RMS and sparse clustering checks. The four earlier passes were reused. PPS timing remains acquisition-domain only, with absolute UTC and channel delays unresolved.
- The TM012 leading non-DC feature moved from -492.7505 to -463.7505 kHz at Run 1670, with high occupancy on both sides. The +29 kHz shift matches the image-coordinate prediction under the −9/+20 kHz primary/secondary LO changes. The main-branch fixed-RF prediction is −11 kHz. Source identity, image conversion gain and the separation of independent intensity effects remain unresolved.
- Five TM010–TM011 pairs share exactly the same received sample index in five runs, versus a range of 0–1 under the pooled 1 µs shifted controls. No triples were found. Shared digitizer/readout disturbances and timing calibration require follow-up before physical interpretation.
- Median T7/Gaussian before → after: TM010 12.90 → 12.62, TM011 3.23 → 3.27, TM012 14.86 → 14.57. These are marginal count comparisons on correlated samples. They do not establish retune, line or thermal causation, or independent-event significance.
- The 20-run continuation used 186.47 GB compressed raw, 52.0 min process wall, 49.9 min CPU and 571.4 MiB peak RSS. Scope and transfer-counter limitations are in the validation report.
- Final English deck: `reporting/tail_coincidence_study/presentation/longitudinal_final/`. See `reporting/tail_coincidence_study/validation/LONGITUDINAL_FINAL_REPORT.md` for plots, tables, manifest and method. Earlier reports and Run 1429 products are preserved.
- Next scientific work: test independent LO motion with both sidebands and develop a time-dependent joint correlated-noise null before interpreting tails or coincidences physically.

The following checkpoints are historical.

## Approved Dataset 2 completion

The approved 24-run selection is processed in chronological batches. Run 1429 and the initial three validated runs are reused.

- Runs 1497, 1513, 1529, 1530 validated and committed as `2feba817618161f19fa80fb5a2a8308e0f65d7b4`.


## Active checkpoint · Dataset 2 hourly Run3-B sample

- Scientific checkpoint `fc07e65b7190bdee1f8222bfa897bd9a8caca000` was pushed and independently verified on `run2-run3-pilot-design-20261122`.
- Run 1429 is reused. Runs 1446, 1463 and 1480 passed the initial batch. The 24-run selection uses actual archived acquisition times through Run 1748. Raw-only 1749–1910 is outside the reconstructed study.
- Successful raw streams used 27.95 GB, 456.9 s and 571.4 MiB peak RSS. Recorded PPS defects matched archived ROOT validation and timing remains in the received-sample domain.
- Selection, presentation paths, results and provenance are in [the longitudinal report](../reporting/tail_coincidence_study/validation/LONGITUDINAL_REPORT.md) and the [persistent handover](TAIL_COINCIDENCE_HANDOVER.md).
- The remaining twenty runs were subsequently approved. Preserve completed runs, including the existing 17-slide checkpoint, and keep future changes on the pilot branch.
- Runs 1547, 1564, 1581, 1598 validated and committed as `77c5984c41f6df2dfdb15378e770741742d124ce`.
- Runs 1615, 1629, 1632, 1649 validated and committed as `312338442e010b208723e098e678a9f2622dabfd`.
- Runs 1666, 1676, 1692, 1709 validated and committed as `d1c01c0faa141fc2144a8de8f60233e5ebe02261`.
- Runs 1727, 1729, 1743, 1748 validated and committed as `5e1c5e00f2146c7baeaec402ccbf1e43110e48b9`.

The remainder records the earlier scientific context.

**Aggiornamento:** 2026-11-23 · baseline 13 (consolidamento in branch operativo e checkpoint T7/cross-mode 1429)
**Repository:** https://github.com/FLASH-HFGW/analysis
**Fonti:** risposta finale Codex e trascrizione completa di `validation_report.md` e `validation.json` fornita dall'utente il 22/11/2026. [Review documentale (branch archivio)](https://github.com/FLASH-HFGW/analysis/blob/docs/flash-analysis-context-20261122/docs/RUN680_VALIDATION_REVIEW_20261122.md). **I file raw e ROOT remoti non sono stati verificati direttamente da ChatGPT.**

**DOCUMENTO CANONICO DI HANDOVER:** branch `run2-run3-pilot-design-20261122`, percorso `docs/ANALYSIS_CONTEXT.md`. Questo documento preserva le baseline 1–12 del precedente branch documentale e aggiunge un aggiornamento cronologico al termine. **I riferimenti storici alle attività “non ancora avviate” descrivono lo stato al 22 novembre e sono superati dai checkpoint successivi.** Il documento sui fit e sulle calibrazioni resta di valore storico; i risultati del pilota 1429 sono documentati dai file versionati sotto `reporting/tail_coincidence_study/`.

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


## 15. Reporting e analisi statistica Run 680 / Run3-B (22–23 novembre 2026)

**Provenienza:** risposte Codex comunicate dall'utente, presentazioni PDF fornite nella chat, e checkpoint tecnici del branch operativo. I prodotti grandi PDF/PPTX sono spesso locali; non inferire la loro disponibilità su GitHub dal solo percorso.

- **Reporting:** standard scientifico **v50** (commit storico `3184f64`, renderer condiviso `reporting/slide_deck.py`), lingua **inglese**, layout per **osservabile con tre modi TM010/TM011/TM012 affiancati** nello stile presentazione status v10. Organizzazione canonica sotto `reporting/`, non in directory arbitrarie del pilota. Presentazione 3-run completa da 65 slide; confronto 680/1429 dettagliato da 51 slide con due slide sui guadagni L5; riepilogo multimodo v10-style separato. Non sostituire report di dettaglio con sintesi.
- Campagne: **Run2 storico 680–939** (260 run; il 680 è benchmark). **Run3-A 1148–1422** (272 ROOT di 275 nel primo censimento). **Run3-B da 1429** (314 ROOT su 320 fino al censimento 1748, più acquisizioni successive da verificare). Le cifre di inventario sono **istantanee**, non copertura definitiva della campagna. Due dataset Run3 del 19–21 novembre 2026 con TWPA in configurazioni equivalenti; Dataset 1 escluso dalle nuove analisi per eccesso di rumore in banda; Dataset 2 selezionato. Non supporre che “configurazioni equivalenti” implichi identiche distribuzioni di rumore.
- Per il confronto a due run, valori L5 condizionali VNA **in dB**: TM010 680=67.474, 1429=81.025, Δ=+13.551; TM011 66.657→76.612, Δ=+9.955; TM012 66.874→75.307, Δ=+8.433. Nessuna covarianza affidabile; **non** equivalgono a guadagno TWPA isolato o cavità→ADC; nessuna correzione PSD.
- Statistiche v50 replicabili: istogrammi I/Q, ampiezza/Rayleigh e CCDF, fase/incrementi, conteggi T3/T5/T7, PSD, ACF complessa lineare, tempi caratteristici. Le statistiche full-run includono ~1,048,576,000 campioni/209.7152 s; PSD/ACF storico v50 sui primi 5,242,880 campioni/1.048576 s; PSD archiviate ROOT mediate su 209 finestre complete da 1 s. Non confondere le popolazioni.

## 16. Diagnostica code Rayleigh — evidenza precedente allo streaming

**Origine:** `reporting/rayleigh_tail_diagnostics/` (rapporto 15 slide riferito da Codex, allegato in chat).

- Soglia T7 v50 sulla distribuzione di ampiezza, con **41.354** superamenti attesi per 1,048,576,000 campioni sotto un'ipotesi marginale Rayleigh ideale; conteggi **680 = 37/40/42**, **1429 = 1368/232/827** per TM010/TM011/TM012. Sono **campioni correlati**, non eventi indipendenti né significatività in sigma.
- Un controllo gaussiano marginale che include medie/covarianza I/Q prevede per il 1429 ~**107.5 / 75.0 / 51.5**, ancora sotto ai conteggi; non costituisce una null distribution temporale. Impropriety |P|/C nel 680 ~0.0407/0.0469/0.0418, nel 1429 ~0.1453/0.1135/0.0606.
- I 1-s PSD ordinati sono utilizzabili a **100 Hz**, mentre le FFT corte 16,384 campioni sono disponibili soltanto come **medie temporali**: lo spettrogramma a 3.2768 ms non si ricostruisce dal ROOT standard. In 1429 si osserva una componente persistente TM012 circa **−492.75 kHz**. Per causalità tra righe e code serve ulteriore controllo.
- A livello 1 s, massimi al livello T7 in **208/130/206 di 209** finestre per 1429, ma i massimi archiviati / episodi preesistenti usano altre soglie e **non** ricostruiscono da soli i cluster T7 reali. PPS Run3 presenta peculiarità; usare solo gli indici di acquisizione per confronti provvisori fra modi.

## 17. Checkpoint Codex di streaming Run 1429 — 23 novembre 2026

**Fonte direttamente verificata su GitHub:** `reporting/tail_coincidence_study/README.md`, `validation/REPORT.md`, `manifest.json`, branch operativo `run2-run3-pilot-design-20261122`. Checkpoint comunicato da Codex: **commit `30fd84a`**, preceduto dall'inventario `6135b28`. Contenuti del report tecnico riletti direttamente da ChatGPT.

- Inventario verificato: **680 storico, 1429 / 1529 / 1629 / 1729 TWPA Run3-B**. Ogni run ~**1,048,576,000 campioni/mode**, 209.7152 s, 5 MS/s; I/Q accertati nel set selezionato come CH0/1,2/3,4/5, `z=I−iQhardware`, ADC ±2 V e scala 4/65535 V/count. **Solo il raw 1429 è stato letto completamente con gzip CRC/EOR;** gli altri raw sono stati controllati a livello intestazione/metadati e ROOT, non validati CRC integralmente.
- Run 1429: campioni T7 esatti **1368 / 232 / 827**, rigenerati con lettura streaming e uguali ai totali archiviati. Per run 680 si riutilizzano **37/40/42** senza nuovo pass raw. Finestre 10 ms/100 ms/1 s riproducono esposizione, conteggi, RMS ROOT entro 10⁻⁶ relativo. Test su confini chunk, coppie e falsi tripli completati.
- **Clustering T7:** con gap ammessi 0,2,5,8,10,25,50 campioni non sopra soglia (fino a 10 µs), **tutti i cluster sono singoletti**. Questo non dimostra impulsi fisici di un campione, soltanto l'assenza di T7 ravvicinati secondo le soglie testate.
- **Coincidenze fra modi:** **nessuna coppia/tripla entro 10 µs**; a 100 µs **una coppia TM010–TM012** a indici campione 674054353 e 674054729 (75.2 µs), nessuna tripla; 20 time shifts descrittivi: media ~**1.1 coppie**, range 0–3. Non attribuire significatività fisica. Run3 PPS presenta circa un gap di 2 s e intervalli da 4,999,999 campioni; ancora mancanti allineamento UTC e ritardi di catena.
- **PSD/righe:** su 209 finestre da 1 s per run, il bin **TM012 −492750.5 Hz** supera il rapporto di fondo locale >3 in **208/209** finestre di **1429, 1529 e 1629**, **0/209** in 1729. Indicatore di persistenza spettrale, non di coerenza di fase né causa dimostrata delle code. Altri run non hanno ancora conteggi temporali T7 estratti dai raw.
- **Termometria:** sensori cavità, mixing chamber, TWPA-stage e proxy 4 K archiviati, con unità e valori invalidi trattati; mapping hardware Run3 e latenze slow-control non indipendentemente certificati. Con soli quattro run TWPA, associazioni termiche esplorative e senza causalità. Il proxy 4 K non è termometria della giunzione HEMT.
- **Risorse:** raw 1429 **9,310,514,217 B**, **159.765 s wall**, **260.4 MiB RSS**; restanti 3 raw Run3-B **27,980,214,936 B** di input compressi; eventuale nuovo raw 680 **~12.13 GB**. Output sparsi, nessun salvataggio waveform. Prodotti grandi o intermedi locali esclusi da Git secondo policy.
- **Null model:** piccolo pilot proper Gaussian con 24×262144 campioni/mode; valida PSD grossolana/varianza, **non** covarianza improper né coda T7 full-run. Non riportare p-value o significatività fisiche.
- **Prossima attività approvabile dopo checkpoint:** esaminare PPS/channel delays e budget I/O; estendere in modo incrementale lo streaming ai run Run3-B selezionati per **un run per ora di acquisizione**, con 1429 come baseline, tempi reali da metadati, 1529/1629/1729 come checkpoint aggiuntivi quando disponibili, a batch piccoli con commit/push. **Non** interpretare un run ogni ~17 numeri come sostituto della selezione su timestamp. Obiettivo: andamento longitudinale di RMS, tassi T7/cluster, coincidenze, linea TM012 e temperature.
- **Stop condition:** nessun nuovo raw in questo aggiornamento Git; non toccare produzione, ROOT pubblicati, calibrazioni, main o HTCondor.

## 18. Procedura persistente per ChatGPT e Codex (decisione operativa 23 novembre 2026)

1. **Fonte di verità del handover generale:** `docs/ANALYSIS_CONTEXT.md` su branch `run2-run3-pilot-design-20261122`; report, tabelle e validation specifiche restano sotto `reporting/`. Il vecchio branch `docs/flash-analysis-context-20261122` rimane **archivio storico**, non più branch di aggiornamento attivo.
2. Ogni **milestone scientifica** di Codex termina con **commit e push** di codice, test, report/sorgenti e risultati leggeri nel branch operativo, e aggiornamento contestuale di questo documento. Non includere raw, ROOT scientifici grandi, credenziali né PDF/PPTX ingombranti se esclusi dalla policy. Segnalare eventuale push fallito e file locali non versionati.
3. ChatGPT verifica GitHub direttamente quando serve e aggiorna il medesimo documento per **decisioni e interpretazioni scientifiche** del progetto, distinguendo prove, ipotesi, limitazioni e follow-up. Niente duplicazioni di log separati salvo esigenza reale documentata.
4. In apertura di una nuova sessione Codex: leggere `docs/ANALYSIS_CONTEXT.md`, `reporting/tail_coincidence_study/README.md`, `validation/REPORT.md` e `git status`; evitare riprocessamenti non necessari.
5. Rispettare le politiche di sicurezza e conservazione in §5; una cartella sorgenti locale o output grafico riportato da Codex non equivale a commit effettuato.

