# FFT raccolte per giorno di acquisizione

`flash:analysis/autoreco/Run2/fft_by_1sec/` contiene un file
`fft_YYYY-MM-DD.zip` per giorno UTC. Il raggruppamento usa il timestamp
`window_start` dell'acquisizione, non la data di elaborazione o del file.
Una finestra che attraversa mezzanotte appartiene al giorno in cui inizia.
Il riepilogo completo `runNNNNN.npz` appartiene al primo giorno del run.

Ogni ZIP conserva i singoli NPZ originali, compressi come prima e senza
modificare array, normalizzazioni, finestre o metadati. Il contenitore usa
ZIP64 senza ricomprimere gli NPZ. `manifest.json` elenca per ogni membro run,
giorno, timestamp delle finestre, dimensione e SHA256. Non vengono mediate
insieme le finestre di un giorno: ogni spettro resta accessibile separatamente.

## Produzione futura

Con `--fft-window-seconds` positivo, lo script FFT produce di default un
bundle per run nel disco scratch del worker. Il payload lo restituisce
tramite HTCondor in `fft_daily_pending`, senza pubblicare i piccoli NPZ.
Lo script e il modulo `examples/fft_daily_archive.py` sono entrambi trasferiti
al worker. Con finestre disabilitate il comportamento precedente è conservato.
Nell'uso interattivo la directory predefinita è locale, sotto
`analysis-runtime/autoreco/Run2/examples/fft`; i bundle si consolidano poi
con il comando riportato sotto. `--fft-output-format npz` mantiene il formato
separato per eventuali prove locali.

Durante il recupero, autoreco raccoglie i bundle pronti per destinazione e
invoca il consolidamento una sola volta per ciclo. Un lock locale protegge
l'aggiornamento degli archivi; i worker non scrivono in un archivio condiviso.
La cache autorevole del coordinatore è in
`/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/fft_daily/flash/analysis/autoreco/Run2/fft_by_1sec/`.
Se la cache manca, gli archivi già pubblicati vengono recuperati prima del merge.

La pubblicazione usa un nome temporaneo, controlla il contenuto remoto con
SHA256, poi rinomina il file finale. Solo dopo la pubblicazione riuscita il job
diventa completato. Se fallisce, resta `daily_ready` e riprova al ciclo seguente.
Un rilancio sostituisce tutti gli elementi dei run ricalcolati, anche se produce
meno finestre o cambia giorno, preservando gli altri run dell'archivio.
I job già nello spool mantengono il vecchio payload; per loro va consolidata
la produzione recuperata. Gli stati terminali precedenti non vengono resettati
automaticamente durante la migrazione.

## Leggere una finestra senza estrarre il giorno intero

```python
import io
import numpy as np
from zipfile import ZipFile

with ZipFile("fft_2026-07-28.zip") as archive:
    with np.load(io.BytesIO(archive.read("run00940_fft_17s.npz"))) as data:
        spectrum = data["fft_amp_mode0_SPECs"]
```

Il lettore `examples.fft_daily_archive.load_product(directory, name)` cerca
automaticamente sia NPZ separati sia membri dei contenitori giornalieri.
`examples/analyze_manyruns_output.py` usa questo lettore.

Lo script dei grafici accetta anche il contenitore:

```bash
python autoreco/plot_fft_npz.py /percorso/fft_2026-07-28.zip \
  --member run00940_fft_17s.npz --raw --output-dir /percorso/locale/grafici
```

Per ricostruire contenitori da NPZ recuperati in locale:

```bash
python examples/fft_daily_archive.py /percorso/npz \
  --directory /percorso/locale/archivi
```

Aggiungere `--remote flash:analysis/autoreco/Run2/fft_by_1sec` per pubblicare,
e `--replace-runs` soltanto quando gli input comprendono tutti i nuovi prodotti
dei run da sostituire. Lo strumento non cancella gli NPZ di ingresso.
La rimozione degli originali storici su GPFS avviene solo dopo la verifica dei
contenitori pubblicati. Inventario e rapporti della migrazione restano in locale.
