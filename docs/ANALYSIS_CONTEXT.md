# QUAX/FLASH — Contesto persistente dell'analisi

**Aggiornamento:** 2026-11-22 · baseline 2
**Repository:** https://github.com/FLASH-HFGW/analysis
**Fonte dell'ultimo aggiornamento:** risposta finale Codex riportata dall'utente il 22/11/2026. **I file remoti non sono stati ancora verificati indipendentemente da ChatGPT.**

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

Codex dichiara rispettati i vincoli: nessuna modifica alla produzione Run3, a `autoreco_run3.json`, cron, orchestratore, wrapper, logbook, ROOT/HDF5 pubblicati; nessun altro run elaborato. Il job HTCondor isolato `4820.0` non è partito (`NumJobStarts=0`) ed è stato rimosso; elaborazione svolta in altro modo secondo il rapporto, da chiarire soltanto se rilevante alla provenienza.

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

## 6. Stato e prossime azioni

**A:** produzione run 680 dichiarata completata da Codex; **rimane l'eventuale verifica esterna di esistenza/checksum del ROOT e lettura integrale di validation_report.md e validation.json**. Nessuna ricostruzione ulteriore richiesta.

**B:** discutere la nuova autoreco leggera, una volta chiuso il controllo documentale: specificare HDF5, FFT 1 s, semantica statistiche/anomalie, prestazioni della lettura MIDAS e distinzione delle convenzioni tra `SPEC` e Run3. Non anticipare implementazione senza piano.

**Procedura di handover:** dopo nuovi risultati scientifici aggiornare data, provenienza, branch/commit, percorsi, numeri, osservabili, incertezze e prossima azione su questo file, con nuovo commit sul branch documentale. Non presentare risultati solo riferiti da Codex come verificati direttamente da ChatGPT.
