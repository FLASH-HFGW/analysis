# Generatori di report

Solo i sorgenti dei generatori sono versionati qui. Output PPTX/PDF, immagini,
asset, Markdown renderizzato e modelli JSON delle slide sono salvati in:

`/home/mazzitel/HFGW/analysis-work/Run2/reports/iq_noise_summary_vN/`

`iq_noise_summary_v5/build_slides.py` è il generatore richiamato dal finalizer
corrente. Le versioni v1–v4 sono mantenute come sorgenti storici e possono
richiedere i prodotti e gli schemi delle rispettive analisi. Non vanno considerate
generatori intercambiabili con la versione corrente.

I documenti precedentemente prodotti sono stati conservati nell'area esterna.
Il generatore legge dati scientifici e metriche di runtime, senza salvarli in Git.

`iq_noise_summary_v6/build_slides.py` aggiorna manualmente la presentazione con
un'istantanea dei prodotti scientifici `v1` già pubblicati su GPFS e il confronto
con le temperature AVS. Conserva le prime 19 slide storiche della v5 e sostituisce
la conclusione con sei slide del pilot, indicando run disponibili e mancanti.
Riusa l'impaginazione in `slide_deck.py` e le immagini del PPTX v5 conservato,
senza dipendere dai vecchi sidecar rimossi durante la migrazione HDF5.

```bash
python3 reporting/iq_noise_summary_v6/build_slides.py
```

PPTX, PDF, anteprime, figure esportabili PNG/PDF, tabelle numeriche e checksum
degli input sono salvati in `analysis-work/Run2/reports/iq_noise_summary_v6/`.
Il report preliminare non viene pubblicato con il nome del confronto finale
della campagna HPC. La correlazione termica è descrittiva e resta distinta
dall'effetto del tempo, degli offset DC e della risposta strumentale.

`iq_noise_summary_v9/build_slides.py` riorganizza la narrazione: obiettivo e
dataset in una slide, diagramma del flusso, definizioni, output e contenuto HDF5;
poi singolo run, aggregazione dei run e temperature, ciascuno con conclusioni
e prossimi passi. Riusa le figure v8 con provenienza e ambito espliciti e
aggiunge il confronto DC v1/v2 del run 680 completo. Non mescola il dataset
storico a banda intera (260 run), il pilot filtrato v1 (12 run) e la prova v2.

```bash
python3 reporting/iq_noise_summary_v9/build_slides.py
```

Il generatore richiede PPTX/modello v8 e i due HDF5 del run 680; i percorsi
sono parametrizzabili con `--baseline`, `--v1`, `--v2` e `--out`. Salva anche
checksum degli input, tabella numerica DC e corrispondenza con le vecchie slide.
Il diagramma a blocchi e il testo sono elementi nativi modificabili nel PPTX.

La v10 aggiunge una slide sui tempi HTC/HPC, prima dei risultati del singolo
run. Legge i timer HDF5 e i timestamp di download dai primi job HTC completati;
il confronto HPC usa il run 680 e gli accounting Slurm riportati dall'utente.
I numeri, gli hash degli input e i limiti del confronto sono salvati in
`data/execution_timings.json`. Il campione non è un benchmark controllato fra
24, 48 e 90 job né fra hardware identico.

```bash
python3 reporting/iq_noise_summary_v9/build_slides.py --include-timings \
  --version v10 --out /home/mazzitel/HFGW/analysis-work/Run2/reports/iq_noise_summary_v10
```

La v11 corregge l'interpretazione delle risorse con la diagnosi misurata:
gli ambienti offload campionati condividono host fisici e più analisi vengono
vincolate alla stessa CPU 0. La slide sui tempi include le prove di affinità,
il risultato dei probe sulla CPU 1 e il requisito di validare l'allocazione
prima di scalare la produzione massiva v2. Copia misure e hash in
`data/affinity_diagnosis.json`.

```bash
python3 reporting/iq_noise_summary_v9/build_slides.py --include-timings \
  --affinity-diagnostics /home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/noise_cpu_diagnostic_20261109 \
  --version v11 --out /home/mazzitel/HFGW/analysis-work/Run2/reports/iq_noise_summary_v11
```

La v12 include tutti i dodici HDF5 v2 pubblicati, validati separatamente dalla
v1, e aggiorna la sezione termica con: ampiezze AC riferite all'ingresso nominale,
nove bande dopo sottrazione della media complessa del run, confronto v1/v2,
correlazioni prima/dopo rimozione del trend temporale lineare e residui dopo
divisione per il trend comune descrittivo. Il trend comune non è un guadagno
misurato indipendentemente. Tabelle, figure, HDF5 aggregato e checksum sono in
`data/v2_pilot/`. La slide 11 rigenera il grafico storico con etichette esplicite
per lag e autocovarianza normalizzata; conserva il suo ambito di cinque SPEC.

```bash
python3 reporting/iq_noise_summary_v9/build_slides.py --include-timings \
  --affinity-diagnostics /home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/noise_cpu_diagnostic_20261109 \
  --v2-pilot-directory /home/mazzitel/HFGW/analysis-work/Run2/reports/pilot_v2_snapshot_20261109 \
  --periodicity-directory /home/mazzitel/HFGW/analysis-work/Run2/staging/legacy-repository/autoreco/noise_continuous/periodicity_run680 \
  --version v12 --out /home/mazzitel/HFGW/analysis-work/Run2/reports/iq_noise_summary_v12
```
