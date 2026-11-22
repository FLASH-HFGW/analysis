# QUAX/FLASH — Contesto tecnico persistente

**Versione:** 2026-11-22 / baseline 1  
**Scopo:** handover tra conversazioni ChatGPT e sessioni Codex.  
**Regola:** separare risultati verificati, informazioni storiche da verificare e attività pianificate. Questo file **non autorizza modifiche alla produzione**.

## 1. Perimetro e stato

Repository: https://github.com/FLASH-HFGW/analysis

Due workstream distinti:

- **A — Benchmark Run2–Run3:** produrre un ROOT **v3.1** di riferimento per il **run 680**, conforme allo schema della produzione Run3 e confrontabile con il benchmark storico della presentazione v50 (`v50-homogeneous-comparison`). Non ripetere né modificare il lavoro v50.
- **B — Futuro autoreco leggero:** pipeline rapida con FFT ogni **1 s**, segnalazione preliminare di anomalie statistiche (senza filtri per ora) e salvataggio **HDF5 almeno per run**. Non mischiare questo sviluppo con il benchmark A.

**Al 22 novembre 2026:** il prompt per il run 680 è stato consegnato a Codex, che ha ripreso a funzionare dopo un blocco dell'interfaccia; **l'esito definitivo è ancora da verificare**. L'analisi scientifica approfondita resta temporaneamente sospesa in attesa di nuovi dati TWPA. Non assumere che il ROOT 680 sia già stato generato.

## 2. DAQ e convenzioni — da verificare contro il codice e il raw

- Acquisizione **MIDAS**; run 680 in formato storico **`SPEC`**.
- Verificare: conversione ADC da **BOR**, mappatura I/Q, convenzione del segno di Q, **PPS**, **ODB**, **EOR**.
- Mapping storicamente riportato: **TM010 I=CH0/Q=CH5; TM011 I=CH1/Q=CH3; TM012 I=CH2/Q=CH4; CH6=PPS**.
- Campionamento di riferimento riportato: **5 MS/s**, intervallo **200 ns**; validare per ciascun run.
- Osservabili: ampiezza, fase, FFT complessa, PSD, RMS, momenti, diagnostiche di fase.
- Benchmark storico approvato: **`v50-homogeneous-comparison`**. Non modificarlo.

## 3. Workstream A — specifiche run 680

Input: **`run00680.mid.gz`**. Usare algoritmi e schema **ROOT v3.1** già validati per Run3; nessuno schema incompatibile.

Verifiche:
1. Compatibilità del formato `SPEC` con v3.1: ADC/BOR, mapping I/Q, segno Q, PPS, ODB.
2. Conteggi attesi **per modo**, da verificare sul raw: **1.048.576.000 campioni**, **209 finestre complete da 1 s**, **3.576.000 campioni residui**, **64.000 blocchi short FFT**.
3. EOR, normalizzazioni e **Parseval**.
4. Confronto **RMS, momenti e PSD** con risultati storici, distinguendo scala ADC, finestre FFT e maschera spettrale v50.
5. Verificare riutilizzo di istogrammi di fase, incrementi di fase e autocorrelazione **lineare** dal benchmark v50. Se serve rielaborare, produrre diagnostiche **separate** dal ROOT v3.1 standard.
6. Consegnare percorso del ROOT prodotto e rapporto sintetico con verifiche numeriche, provenienza e limiti.

### Vincoli assoluti

- Worktree e branch Git **isolati**.
- **Non modificare la produzione Run3**: checkout operativo, `autoreco_run3.json`, cron, orchestratore, wrapper, file ROOT/HDF5 pubblicati, logbook.
- Nessuna sottomissione attraverso il ciclo autoreco ordinario.
- Non pubblicare il run 680 nella directory canonica `Run3`; se necessario, nuova area di riferimento **Run2**, senza sovrascrivere nulla.
- Se necessario **un solo job HTCondor isolato**, con GFAL/token t1 sul Worker Node, scratch dedicato e dipendenze da CVMFS; evitare installazioni locali permanenti.
- **Non elaborare altri run, non modificare né riavviare la produzione.**

**Stato delle evidenze:** obiettivi, numeri attesi e vincoli sono riportati dal prompt dell'utente; compatibilità SPEC, conteggi effettivi, validazione Parseval, percorso del ROOT ed esito Codex **restano da verificare**.

## 4. Workstream B — autoreco leggero, non ancora avviato

FFT ogni **1 s**, esecuzione veloce, segnalazione di possibili anomalie statistiche senza filtri attivi, output HDF5 almeno per run. Riutilizzare soltanto convenzioni scientifiche accertate. Misurare separatamente tempi di lettura/decodifica e FFT; formato HDF5, soglie e architettura sono da definire.

## 5. Informazioni diagnostiche non scientifiche

- L'estensione Codex VS Code ha temporaneamente mostrato `This RpcImportHook was already disposed`, poi ha ripreso; non confondere il problema dell'interfaccia con un risultato scientifico.
- Il 22/11 risultavano **20 job HTCondor idle (4800–4819)** relativi ai run **1724–1762**, non al 680. Nessuna azione su tali job è autorizzata dal benchmark.
- I rollout Codex sono archiviati in `~/.codex/sessions/`, ma non sostituiscono la verifica di file, commit e prodotti.

## 6. Protocollo di aggiornamento

Dopo ogni risultato significativo di Codex:
1. Leggere la risposta e **verificare** prodotti, commit e percorsi.
2. Aggiornare soltanto stato, risultati confermati, incertezze e prossime azioni, indicando **data, branch/commit, path, comandi e provenienza**.
3. Non promuovere ipotesi o output non verificati a risultati acquisiti.
4. Tenere separati benchmark v3.1 e sviluppo autoreco HDF5.
5. Versionare in Git su branch documentale, evitando credenziali/token, dati personali e grandi file generati.
6. Per un nuovo contesto ChatGPT/Codex usare questo documento e l'ultimo esito Codex; iniziare con la ricognizione dello stato, prima di modificare.

## 7. Prossima azione

Attendere l'esito del prompt Codex per il run 680. Verificare worktree/branch, modifiche, ROOT e collocazione, conteggi, Parseval, confronti v50 e **assenza di modifiche alla produzione Run3**. Aggiornare quindi questo documento.
