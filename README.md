# FLASH analysis software

Software per ricostruzione MIDAS, analisi scientifica e controllo delle campagne.
Il repository contiene sorgenti, test, configurazioni e documentazione.
Dati acquisiti, risultati, checkpoint, log e prodotti dei report restano esterni.

| Area | Percorso | Contenuto |
|---|---|---|
| Software versionato | `/home/mazzitel/HFGW/analysis` | Questo repository |
| Controllo dei job | `/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2` | Stati, log, payload, spool, cache e benchmark |
| Lavoro scientifico locale | `/home/mazzitel/HFGW/analysis-work/Run2` | Risultati non consolidati, riferimenti numerici, analisi e report |
| Prodotti pubblicati | `/home/mazzitel/flash-data/analysis/autoreco/Run2` | Risultati consolidati su GPFS |
| Input acquisiti | `/home/mazzitel/flash-data/data/LNF` | File MIDAS originali, in sola lettura |

Organizzazione corrente del software:

- `examples/`: estrattori e ricostruzione, analisi, librerie condivise e strumenti batch;
- `autoreco/`: preparazione, sottomissione, recupero e controllo dei job;
- `examples/tests/`: test con input sintetici creati in directory temporanee;
- `tools/diagnostics/`: diagnostiche recuperate dalle vecchie cartelle di output;
- `reporting/`: generatori dei report, senza PDF, immagini o presentazioni prodotte;
- `config/`: selezione dei run e altre configurazioni sorgenti;
- `docs/`: organizzazione del lavoro e convenzioni sui percorsi.

La separazione dei moduli di `examples/` in ricostruzione, analisi e I/O è
descritta in [docs/organization.md](docs/organization.md). I percorsi dei programmi
attualmente utilizzati sono mantenuti durante l'estrazione interattiva in corso.

I notebook sono sorgenti: devono avere output ed execution count vuoti.
Il baseline misurato `noise_reference.json` vive nell'area locale
`analysis-work/Run2/references/`, non in Git. `config/noise_runs.txt` è invece
una selezione sorgente dei run, non uno stato generato dalla coda.

Prima di un commit:

```bash
python3 tools/check_repository.py
```

Il controllo legge l'indice Git e rifiuta dati, metadati dei job, report renderizzati
e notebook eseguiti. La pulizia dei file correnti non riscrive la storia Git.

Istruzioni operative:

- [Autoreco](autoreco/README.md)
- [Ricostruzione noise](autoreco/README_noise.md)
- [FFT raccolte in contenitori](autoreco/README_fft_daily.md)
- [Termometri interattivi](examples/README_thermometers.md)
- [Termometri in batch](examples/README_thermometers_batch.md)
