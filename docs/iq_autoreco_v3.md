# Autoreco IQ v3 lightweight

Il pilot parte da main `d90f820` sul branch `autoreco-v3-lightweight`. Il payload legge il BOR e poi gli eventi MIDAS in sequenza. Il file HDF5 temporaneo è scritto nella directory di destinazione e pubblicato con un collegamento atomico dopo la chiusura. Una destinazione esistente causa errore.

## Esecuzione

```bash
export PYTHONPATH=/cvmfs/sft-flash.infn.it/package/midas/python
python examples/analyze_midas_iq_v3.py INPUT.mid.gz OUTPUT.h5
PYTHONPATH=examples python -m unittest discover -s examples -p test_iq_autoreco_v3.py
```

Il formato SPE richiede il mapping I/Q esplicito tramite `--split-pairs` in assenza di mapping dal BOR. Per i soli confronti diagnostici dei pilot 1145 e 1148 è stato passato `'{"TM010":[0,1],"TM011":[2,3],"TM012":[4,5]}'`. Nel formato SPEC il fallback è il mapping storico. Un eventuale `IQ_channel_pairs` nel blocco NetBox Settings ha precedenza. Questa chiave è supportata dal decoder come input strutturato e non è stata osservata nei BOR dei pilot.

L'orchestratore esistente prepara un job singolo con `--analysis-kind iq-v3 --prepare-only --read-only --run 1145 --max-events 30 --output-dir /tmp/IQ-PILOT` e la stessa mappa tramite `--iq-v3-split-pairs`. Il wrapper riusa download e credenziali del payload noise. Il job trasferisce il prodotto tramite lo spool Condor. La preparazione locale è passata. Il dry-run Condor ha richiesto autenticazione OAuth interattiva.

## HDF5 1.0

| Percorso | Contenuto |
|---|---|
| `metadata` | Run, layout e numero di canali presenti, percorso/dimensione/mtime sorgente, commit, configurazione e provenienza del mapping, snapshot NetBox e LO dal BOR. |
| `timing/windows` | Una riga per FFT. Segmento, indice di ricezione e seriale/offset originali del primo e ultimo campione, inclusivi. `received_s` è il tempo nominale dei campioni validi ricevuti, calcolato con il rate BOR. UTC è NaN con qualità `unanchored`. |
| `timing/{pps,spgp,tgps}` | Impulsi dal canale 6 quando presente, coppie indice/durata SPGP osservate, payload TGPS e timestamp del relativo header MIDAS in secondi Unix. |
| `spectra` | Asse bilatero condiviso in Hz, in ordine FFT. Dataset per modo con riga per finestra. |
| `statistics` | Dataset per modo con riga per finestra e aggregati come attributi. Unità nei nomi dei campi. Indice del picco locale, conteggi a fondo scala per componente ed errore relativo di Parseval. |
| `anomalies/<modo>` | Tabelle `episodes` e `population` per finestra e soglia, con indici di ricezione, durate in campioni e picchi in V. |
| `quality` | Errori di bank e salti di seriale, contatori di finestre e campioni, presenza EOR, confronto esatto SPGP e misure processo. |
| `histograms` | Gruppo riservato, vuoto nel pilot. |

Ogni canale fisico usa i bit signed int16 e il fattore `2 × range_di_picco_V / 65535` derivato dal BOR. Il segnale complesso è `I − iQhardware`. La pseudocovarianza normalizzata usa `E[(z−E[z])²] / E[|z−E[z]|²]`. Le statistiche aggregate si riferiscono alla popolazione delle sole finestre complete.

Una finestra contiene esattamente `N = fs` campioni consecutivi. I confini delle bank attraversano le finestre se le seriali sono consecutive e il layout e le bank IQ sono coerenti. Un salto di seriale o una bank IQ non valida chiude il segmento e scarta l'eventuale finestra incompleta. Il contatore degli scarti riguarda code di campioni validi già ricevuti. Rimane da verificare la continuità fisica in presenza di perdite invisibili alle seriali. Le anomalie in SPGP e TGPS sono registrate per la qualità di timing.

La finestra rettangolare conserva la DC e la media complessa. Con `X = FFT(z) / N`, `--product fft` conserva `X` in complex64 e V. Il default salva solo la PSD float32 `|X|² N/fs` in V²/Hz, bilatera e senza fattore due. L'integrale numerico usando la larghezza `fs/N` equivale a `mean(|z|²)`, inclusa la DC.

La soglia è `|z − mean(z)| > k × sqrt(mean(|z − mean(z)|²))` per finestra, con `k` configurabile e default 4, 5, 6. Gli episodi sono sequenze consecutive entro la finestra applicabile e vengono troncati al cambio di finestra, dove cambia la soglia locale. La tabella popolazione include i casi senza escursioni. Sono candidati statistici.

## Timing dei pilot

- 1145 contiene SPE0–SPE6 e SPGP. Il confronto su sette coppie mostra indice SPGP sempre un campione prima del fronte SPE6 a 2,5 V. SPGP riporta 5000 campioni per tutti gli impulsi, il detector misura 4999 o 5000. Gli intervalli ricostruiti dal detector sono 4.999.999 o 5.000.000 campioni. Il PPS analogico legacy richiede oltre 4000 campioni sopra 2,5 V e conserva lo stato attraverso confini contigui.
- I payload TGPS del 1145 contengono testo con timezone CET e marcature successive a cadenza di un secondo. Nei primi record il timestamp nel testo è un secondo avanti rispetto all'header MIDAS convertito in CET. Il primo TGPS precede il primo evento SPE nel file. L'associazione tra fronte, timestamp GPS e latenza di registrazione resta da verificare sul frontend. SPGP è salvato come dato diagnostico.
- Il 1148 è un run distinto con `With_TWPA=True` nel BOR. Le bank dei primi 30 eventi hanno SPE0–SPE5 e SPGP. Il decoder conserva i sei canali effettivi e segnala l'assenza della forma d'onda PPS.
- Il segno I/Q e il mapping configurato sono coperti dal test a tono sintetico. Il riferimento storico legacy è in [audit del 680](frequency_coordinates_run680_audit.md). Per SPE serve una conferma del cablaggio o un tono acquisito noto.

## Benchmark compressione

Primi cinque eventi del 1145, una finestra per ciascuno dei tre modi, PSD, filesystem locale. Tempi end-to-end includono decompressione MIDAS, analisi e scrittura HDF5.

| Codec | HDF5 MB | Wall s | CPU s | Picco RSS MiB |
|---|---:|---:|---:|---:|
| Nessuno | 103,09 | 1,78 | 1,76 | 532 |
| LZF | 100,21 | 2,27 | 2,18 | 533 |
| gzip default | 94,71 | 3,84 | 3,79 | 532 |

Il default senza compressione privilegia il throughput. Il calcolo di Parseval nelle misure di benchmark e nei pilot brevi ha dato un errore relativo massimo inferiore a 1,3 × 10⁻⁷.

## Pilot

Il throughput è misurato in milioni di campioni ricevuti per secondo di wall clock, contando un solo campione temporale per frame indipendentemente da quanti canali contiene. I pilot 1145 e 1148 sono stati eseguiti in parallelo localmente.

| Run | Eventi | Finestre | Scarti ricevuti | Wall s | CPU s | RSS MiB | HDF5 MB | MS/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1145 completo | 30 | 6 | 1.457.280 | 12,63 | 12,38 | 556 | 417,69 | 2,49 |
| 1148 TWPA, estratto | 30 | 6 | 1.457.280 | 12,45 | 12,25 | 551 | 417,68 | 2,53 |

I prodotti del pilot e del benchmark sono in `/tmp/iqv3.k0hv3K`. Nei due estratti SPE non sono state rilevate interruzioni di seriale o bank malformate. Il 1145 ha terminato con EOR. In tutti i prodotti il tempo UTC delle finestre resta non ancorato.
