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
