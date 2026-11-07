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
