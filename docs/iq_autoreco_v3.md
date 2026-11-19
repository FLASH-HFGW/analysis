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

## HDF5 1.2

| Percorso | Contenuto |
|---|---|
| `metadata` | Run, layout e numero di canali presenti, percorso/dimensione/mtime sorgente, commit, configurazione e provenienza del mapping, snapshot NetBox e LO dal BOR. |
| `timing/windows` | Una riga per FFT. Segmento, indice di ricezione e seriale/offset originali del primo e ultimo campione, inclusivi. `received_s` è il tempo nominale dei campioni validi ricevuti, calcolato con il rate BOR. UTC è NaN con qualità `unanchored`. |
| `timing/{pps,spgp,tgps}` | PPS da SPEC CH6 per legacy e da SPGP per SPE. SPGP conserva le coppie nel formato sorgente. TGPS conserva payload, timestamp dell’header in secondi Unix e numero di campioni ricevuti prima del record. |
| `timing/{pps_waveform,digitizer_events}` | Confronto analogico dove disponibile e registro ADC con seriale, timestamp MIDAS, indice iniziale, lunghezza e segmento. |
| `spectra` | Default compatto con PSD media per run e PSD aggregata per finestra. I diagnostici full spectrum conservano l’asse bilatero condiviso in ordine FFT. |
| `statistics` | Dataset per modo con riga per finestra e aggregati come attributi. Unità nei nomi dei campi. Indice del picco locale, conteggi a fondo scala per componente ed errore relativo di Parseval. |
| `anomalies/<modo>` | Tabelle `episodes` e `population` per finestra e soglia, con indici di ricezione, seriali e offset ADC di inizio e picco, durate in campioni e picchi in V. |
| `quality` | Errori di bank e salti di seriale, contatori di finestre e campioni, presenza EOR, confronto esatto SPGP e misure processo. |
| `histograms` | Per modo, bordi e conteggi per 512 classi lineari dell’ampiezza complessa, da zero al massimo ADC con i range BOR del modo. |

Ogni canale fisico usa i bit signed int16 e il fattore `2 × range_di_picco_V / 65535` derivato dal BOR. Il segnale complesso è `I − iQhardware`. La pseudocovarianza normalizzata usa `E[(z−E[z])²] / E[|z−E[z]|²]`. Gli aggregati temporali e gli istogrammi includono tutti i campioni validi ricevuti, comprese le code prima delle discontinuità e a fine run. I momenti parziali sono combinati pesando per numero di campioni. FFT, PSD ed escursioni catalogate usano le sole finestre complete. `quality` espone `temporal_samples`, `spectral_samples` e il numero di code; `discarded_samples` indica gli esclusi dalla popolazione spettrale.

Una finestra contiene esattamente `N = fs` campioni consecutivi. I confini delle bank attraversano le finestre se le seriali sono consecutive e il layout e le bank IQ sono coerenti. Un salto di seriale o una bank IQ non valida chiude il segmento e scarta l'eventuale finestra incompleta. Il contatore degli scarti riguarda code di campioni validi già ricevuti. Rimane da verificare la continuità fisica in presenza di perdite invisibili alle seriali. Le anomalie in SPGP e TGPS sono registrate per la qualità di timing.

La finestra rettangolare conserva la DC e la media complessa. Con `X = FFT(z) / N`, `--product fft` conserva `X` in complex64 e V. `--product psd` salva la PSD float32 completa `|X|² N/fs` in V²/Hz, bilatera e senza fattore due. L'integrale numerico usando la larghezza `fs/N` equivale a `mean(|z|²)`, inclusa la DC.

La soglia è `|z − mean(z)| > k × sqrt(mean(|z − mean(z)|²))` per finestra, con `k` configurabile e default 4, 5, 6. Gli episodi sono sequenze consecutive entro la finestra applicabile e vengono troncati al cambio di finestra, dove cambia la soglia locale. La tabella popolazione include i casi senza escursioni. Sono candidati statistici.

## Timing dei pilot

- 1145 contiene SPE0–SPE6 e SPGP. Il detector a pendenza del notebook, applicato alle forme d’onda SPE6 dei 30 eventi, riproduce tutte le sette coppie SPGP e gli eventi senza impulsi. Rispetto al fronte SPE6 a 2,5 V, SPGP è sempre un campione prima. SPGP riporta 5000 campioni per tutti gli impulsi, il detector misura 4999 o 5000. Gli intervalli ricostruiti dal detector sono 4.999.999 o 5.000.000 campioni. Il PPS analogico legacy richiede oltre 4000 campioni sopra 2,5 V e conserva lo stato attraverso confini contigui.
- I payload TGPS del 1145 contengono testo con timezone CET e marcature successive a cadenza di un secondo. Nei primi record il timestamp nel testo è un secondo avanti rispetto all'header MIDAS convertito in CET. Il primo TGPS precede il primo evento SPE nel file. L'associazione tra fronte, timestamp GPS e latenza di registrazione resta da verificare sul frontend. Il frontend ha confermato che SPGP contiene l’indice locale del fronte di salita e la durata dell’impulso, nominalmente 5000 campioni. Nel 1145 SPE6 serviva alla verifica del fronte. Dal 1148 il decoder usa direttamente SPGP e SPE6 è assente.
- Il 1148 è un run distinto con `With_TWPA=True` nel BOR. Le bank dei primi 30 eventi hanno SPE0–SPE5 e SPGP. Il decoder conserva i sei canali effettivi e segnala l'assenza della forma d'onda PPS.
- Il segno I/Q e il mapping configurato sono coperti dal test a tono sintetico. Il riferimento storico legacy è in [audit del 680](frequency_coordinates_run680_audit.md). Per SPE serve una conferma del cablaggio o un tono acquisito noto.

## Benchmark compressione

Primi cinque eventi del 1145, una finestra per ciascuno dei tre modi, PSD, filesystem locale. Tempi end-to-end includono decompressione MIDAS, analisi e scrittura HDF5.

| Codec | HDF5 MB | Wall s | CPU s | Picco RSS MiB |
|---|---:|---:|---:|---:|
| Nessuno | 103,09 | 1,78 | 1,76 | 532 |
| LZF | 100,21 | 2,27 | 2,18 | 533 |
| gzip default | 94,71 | 3,84 | 3,79 | 532 |

Scrittura isolata dei tre spettri della prima finestra, con gli stessi chunk e chiusura HDF5 inclusa. Nessun codec 0,05 s / 62,92 MB, LZF 0,58 s / 60,05 MB, gzip 2,21 s / 54,54 MB.

Il default senza compressione privilegia il throughput. Il calcolo di Parseval nelle misure di benchmark e nei pilot brevi ha dato un errore relativo massimo inferiore a 1,3 × 10⁻⁷.

## Pilot

Il throughput è misurato in milioni di campioni ricevuti per secondo di wall clock, contando un solo campione temporale per frame indipendentemente da quanti canali contiene. I pilot 1145 e 1148 sono stati eseguiti in parallelo localmente.

| Run | Eventi | Finestre | Scarti ricevuti | Wall s | CPU s | RSS MiB | HDF5 MB | MS/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 680 completo | 1.000 | 209 | 3.576.000 | 384,23 | 378,42 | 565 | 13.190,08 | 2,73 |
| 1145 completo | 30 | 6 | 1.457.280 | 12,63 | 12,38 | 556 | 417,69 | 2,49 |
| 1148 TWPA, estratto | 30 | 6 | 1.457.280 | 12,45 | 12,25 | 551 | 417,68 | 2,53 |

I prodotti del pilot e del benchmark sono in `/tmp/iqv3.k0hv3K`. Nei due pilot SPE non sono state rilevate interruzioni di seriale o bank malformate. Il 1145 ha terminato con EOR. In tutti i prodotti il tempo UTC delle finestre resta non ancorato.

Il 680 ha raggiunto EOR senza salti di seriale o bank malformate. I 210 impulsi PPS misurati sono distanziati esattamente di 5.000.000 campioni. Errore massimo di Parseval pari a 1,28 × 10⁻⁷.

Il confronto usa i momenti ADC del prodotto approvato `run00680_noise_v2.h5` nella campagna `noise_fullrange_v2_20261109`. I suoi volt ADC corrispondono alla scala CLI ±5 V. Applicando il rapporto BOR 2/5 e il segno di Qhardware, le differenze relative su RMS totale e AC sono inferiori a 1,9 ppm per tutti i modi. Le differenze assolute sulle medie I e Q sono inferiori a 0,15 µV. Il riferimento storico comprende 1.048.576.000 campioni, mentre le finestre v3 coprono 1.045.000.000 campioni.

## Consolidamento del 1148

Run completo con EOR, 1000 seriali ADC consecutive e 1.048.576.000 campioni ricevuti. A 5 MS/s sono attese 209 finestre intere e una coda di 3.576.000 campioni. SPGP contiene 209 fronti, tutti con durata 5000 campioni. Intervalli osservati in campioni: 133 × 4.999.999, 74 × 5.000.000 e 1 × 9.999.999 tra seriali 448 e 457. La seriale 452 contiene SPGP con la sola parola `[1043618]`, pari a un indice globale di 474.999.970 sul reticolo PPS atteso. Restano 4958 campioni nella bank, 42 meno della larghezza nominale. Il decoder segnala la bank incompleta e conserva le finestre ADC. La coppia valida registrata manca, mentre la parola solitaria è compatibile con il fronte di un impulso a cavallo del confine. Le seriali e le lunghezze non evidenziano perdite o duplicazioni di blocchi. Una verifica indipendente di perdite interne all’hardware richiede un contatore sorgente.

I 212 record TGPS riportano secondi consecutivi nel testo CET. Convertito in UTC, il testo coincide con l’header in 202 record e vale header + 1 s negli altri 10. Associare per ordine il primo TGPS al primo PPS e saltare la marcatura assente dà record registrati fino a circa 0,39 s di campioni prima del fronte. Il dato dimostra coerenza della cadenza e lascia da confermare quale secondo UTC etichetti ciascun PPS. `utc_unix_s` rimane NaN.

Per Giorgio Dho

- Per il cablaggio TWPA del 1148, quali indici SPE sono I e Qhardware per TM010, TM011 e TM012? È disponibile un run con tono iniettato, indicando RF, LO e segno IF atteso per `I − iQhardware`?
- Quale fronte SPGP corrisponde al secondo scritto nel testo TGPS? Il record etichetta il fronte precedente o quello successivo? Qual è la latenza tra cattura e timestamp MIDAS? Alla seriale 452 SPGP vale `[1043618]`. È la rappresentazione prevista per un impulso che attraversa il confine? In quale bank compare la durata, e c’è un contatore ADC per verificare la continuità fisica?

### HTCondor

Il normale percorso Condor prepara un run esplicito e riusa download DAVS, CVMFS e spool. Per il run completo usare `--iq-v3-full-run`. Il profilo standard è compatto e `--iq-v3-bin-hz` configura i bin; `--iq-v3-product psd` e `--iq-v3-product fft` selezionano i diagnostici completi. Nel job sono richiesti 4 GB RAM, 100 GB disco e una CPU. Il worker valida conteggi e Parseval nell’HDF5 chiuso prima del trasferimento. Il dry-run di una copia senza direttive OAuth ha validato la sintassi. Il submit reale richiede il token `t1`.

Per autorizzare manualmente `t1`, sul submit host eseguire:

```bash
cd /tmp/iqv3-final.7EPljn/condor/01148
condor_submit -dry-run /tmp/iqv3-final.7EPljn/1148.classad submit.sub
```

Aprire nel browser l’URL appena stampato da Condor, autenticarsi con l’account abilitato al servizio e concedere l’autorizzazione richiesta. Quindi ripetere lo stesso comando e verificare che generi il ClassAd. Il dry-run non mette job in coda. Il test del download e del trasferimento su worker resta da fare con un solo job isolato dopo autenticazione.

Prima dell’attivazione, verificare mapping e tono, definire l’ancoraggio UTC e la gestione delle marcature PPS mancanti, completare il job isolato e verificare il rientro HDF5 dallo spool. L’integrazione nelle destinazioni operative e la riattivazione del cron richiedono approvazione esplicita.

### Profilo e parallelismo

Il profilo della baseline sul 1148 individua le statistiche come fase più costosa. Il consolidamento riusa il quadrato dell’ampiezza per i momenti terzo e quarto, con accumulo float64. Su un buffer da 5 milioni di campioni il tempo mediano scende da 0,600 a 0,327 s con concordanza numerica. Le righe delle escursioni sono scritte in blocco per soglia.

Primi 30 eventi, PSD senza compressione, durante le due ricostruzioni complete. Con un worker le fasi contabilizzate richiedono 3,27 s lettura MIDAS inclusi decompressione e parsing, 0,28 s scala ADC e clipping, 1,55 s FFT e potenza, 5,24 s statistiche, 0,72 s escursioni inclusa la scrittura delle relative tabelle e 0,32 s scrittura delle righe spettrali e statistiche. Gli istogrammi restano disattivati. Due worker FFT danno 2,71 MS/s contro 2,65 MS/s con uno, entro la variabilità del campione concorrente. La configurazione del pilot Condor usa una CPU per run. Per aumentare il throughput aggregato conviene provare run indipendenti con concorrenza limitata dal bandwidth di staging e spool.

Verifica locale delle dipendenze del worker con Python 3.9 e CVMFS: MIDAS, NumPy 2.0.2, SciPy 1.13.1, h5py 3.14.0, jq e gfal-copy disponibili.

Prodotti completi, senza compressione, generati come file separati per la sola validazione. Le due elaborazioni locali si sono sovrapposte.

| Prodotto | Dimensione GB decimali | Wall s | CPU s | RSS MiB | MS/s |
|---|---:|---:|---:|---:|---:|
| PSD float32 | 13,191 | 323,83 | 316,60 | 556 | 3,24 |
| FFT complex64 | 26,340 | 353,27 | 332,12 | 555 | 2,97 |

Nel PSD completo, i tempi delle fasi principali sono 146,95 s statistiche, 88,81 s lettura MIDAS, 53,29 s FFT e potenza, 16,03 s escursioni, 10,32 s scrittura spettri e statistiche e 6,80 s conversione ADC. La banda di acquisizione nominale è 5 MS/s.

La rilettura dei due HDF5 ha verificato l’uguaglianza bin per bin della PSD e di `abs(FFT)²` su tutte le 627 righe spettrali, con bin bilateri da 1 Hz ed errore relativo massimo tra potenza integrata e RMS² inferiore a 1,28 × 10⁻⁷. L’inversa complessa ha riprodotto la prima finestra ADC di ciascun modo entro 0,5 µV e la DC concorda con le medie I/Q. Sono stati verificati anche i momenti d’ampiezza della prima finestra, il bilancio delle popolazioni di escursione per tutte le finestre e soglie, e i riferimenti ADC. Sono presenti 209 finestre valide, una coda incompleta e zero finestre scartate per discontinuità ADC. I prodotti locali sono in `/tmp/iqv3-final.7EPljn`.

## Profilo compatto standard

`--product compact` è il default. `spectra/<modo>/mean_psd` è la media aritmetica in potenza lineare delle finestre FFT complete, accumulata in RAM in float64 e conservata in float32. L’asse a 1 Hz è implicito e condiviso tramite gli attributi `frequency_first_hz`, `frequency_spacing_hz` e `frequency_count` di `spectra`, in ordine di frequenza crescente.

`spectra/<modo>/window_psd` contiene una riga per finestra e densità media float32 per bin. I bordi crescenti sono in `spectra/window_bin_edges_hz`, in Hz. Ogni centro FFT a 1 Hz rappresenta una cella di larghezza 1 Hz. Il primo bordo è mezzo Hz sotto il primo centro. `--bin-hz` imposta la larghezza nominale intera (default 100). L’ultimo bin può avere larghezza minore, disponibile con tutte le altre in `spectra/window_bin_width_hz`. La densità di ciascun bin è la somma delle potenze lineari divisa per la sua larghezza effettiva. La somma densità × larghezza conserva la potenza integrata bilatera, DC inclusa, entro l’arrotondamento float32.

Opzioni del payload locale, disattivate per default

- `--max-psd` salva anche il massimo float32 della PSD a 1 Hz per ciascuna frequenza e modo, circa 60 MB per tre modi a 5 MS/s. Le frequenze possono raggiungere il loro massimo in finestre diverse.
- `--band LOW_HZ HIGH_HZ` è ripetibile e salva i centri FFT nell’intervallo semiaperto configurato, a 1 Hz per ogni finestra. `--band-product psd` usa float32 e V²/Hz. `--band-product fft` usa complex64 e V con fase. Ogni dataset `band_N` ha coordinate e limiti richiesti negli attributi. La selezione avviene dopo la FFT bilatera dell’intero segnale.
- `--compression lzf` o `--compression gzip` applica un codec HDF5 lossless. Il default è senza compressione.
- `--product psd` e `--product fft` conservano l’intero spettro per finestra per i diagnostici.

L’asse compatto contiene esattamente gli stessi centri FFT del diagnostico, riordinati. Il mapping e la convenzione di segno conservano la provenienza preesistente. Non sono configurate bande di risonanza per default.

### Benchmark compatto sul 1148 completo

Un’unica passata MIDAS sul run chiuso. Input compresso 9.273.616.774 B, HDF5 standard **187.884.152 B** (2,03% del raw), 307,81 s wall, 3,41 MS/s e 706 MiB di picco RSS. Il benchmark è stato eseguito in parallelo con la lettura del vecchio HDF5 di riferimento. Il controllo di potenza integrata è stato poi semplificato da un prodotto scalare BLAS a una somma float64. Le righe salvate sono identiche, verificate offline, e il tempo riportato è quello della singola esecuzione completa.

Il confronto offline con il PSD completo preesistente ha dato uguaglianza float32 per la PSD media e tutte le 627 righe aggregate. Il massimo errore relativo di conservazione dovuto al rebin è 3,82 × 10⁻¹⁰. Il confronto fra PSD aggregata integrata e RMS² temporale per finestra ha dato un errore massimo di 1,28 × 10⁻⁷. Le 209 FFT coprono 1.045.000.000 campioni. Le statistiche temporali e gli istogrammi contano 1.048.576.000 campioni, inclusa la coda di 3.576.000. Sono stati verificati statistiche per finestra, escursioni e riferimenti ai seriali ADC. Prodotto locale `/tmp/iqv3-final.7EPljn/1148-compact.h5`.

Riscrittura offline dei soli dataset PSD standard con le impostazioni HDF5 del payload

| Codec | MB decimali | Scrittura e chiusura (s) |
|---|---:|---:|
| Nessuno | 185,45 | 0,11 |
| LZF | 185,51 | 1,85 |
| gzip | 155,97 | 7,15 |

Il default resta senza compressione per la velocità. gzip risparmia circa il 16% sui dataset PSD.

### Dimensionamento HTCondor

Con un run da 209,72 s di acquisizione e un worker per run, stimare gli slot con `ceil((307,81 s + 9273,62 MB / B_down + 187,88 MB / B_up) / 209,72 s)`. Le bande sono quelle effettive per job concorrente. La misura locale include la decompressione MIDAS. Con download e upload a 100, 50 o 25 MB/s per job, servono rispettivamente almeno 2, 3 o 4 slot. A 100 MB/s due slot lasciano un margine ridotto per coda e staging. L’ingresso condiviso deve sostenere almeno 44,2 MB/s e lo spool in uscita circa 0,90 MB/s, oltre al margine operativo. Verificare i tempi reali su un job isolato dopo OAuth prima di scegliere la concorrenza operativa.
