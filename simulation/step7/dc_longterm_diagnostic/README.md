# Step 7 — DC long-term e origine della depressione TM010

Diagnostica separata, senza modificare ricostruzione, calibrazione o prodotti
scientifici originali. Riutilizza i **260 prodotti v2 completi dei run 680–939**.
Legge solo i metadati BOR dei raw per i range ADC e gli stati hardware; per le
verifiche sulle forme d'onda legge **16 SPEC iniziali per ciascuno dei run
680, 693, 909, 939**: 3.3554432 s/run, 64 SPEC in totale. I run sono scelti dagli
estremi temporali e dal minimo/massimo del rapporto DC²/AC² del TM010 già estratto.
Non vengono eseguite nuove ricostruzioni di produzione.

## Definizioni verificate nei sorgenti originali

Riferimenti: `examples/analyze_midas_iq_noise.py`, `examples/iq_noise_v2.py`,
`docs/iq_noise_v2.md` e i cinque test originali `examples/tests/test_iq_noise_v2.py`.

- `z=I-iQhardware`. `mean_q_v` esportata dalla v2 è **Im(mean(z))=-mean(Qhardware)**.
  I grafici delle tensioni hardware e quelli del piano complesso hanno quindi
  etichette diverse ed esplicite; fase DC = arg(mean(z)).
- `mu=mean(z)` sull'intero run selezionato nella prima passata; la seconda
  sottrae **una sola media per run prima dei FIR**, conservando le derive interne.
  Nessun centraggio per SPEC nell'analisi scientifica.
- `DC²=|mu|²`, `AC²=mean(|z-mu|²)`, `total²=DC²+AC²`. La varianza è ottenuta da
  momenti centrati combinabili, non da sottrazione instabile di potenze grandi.
- Le quantità quadratiche sono in **V²**, non in watt RF. AC RMS è sqrt(AC²),
  non la deviazione standard dell'inviluppo dell'analisi storica v1.
- I gruppi storici e gli istogrammi globali delle ampiezze conservano il segnale
  precedente alla sottrazione della DC. Gli istogrammi dell'inviluppo traslato
  della v1 non rappresentano il modulo di z-mu e non vengono usati come tali.

## Unità e calibrazione: nessun guadagno adattato

Tutti i BOR controllati riportano **±2 V sui sei canali IQ**, contro ±5 V usati
nella conversione salvata nei prodotti v2. La diagnostica corregge una sola volta
le tensioni di un fattore **0.4**, i quadrati di **0.16**; i raw usano direttamente
`4/65535 V/count`. La correzione è verificata per ogni run/coppia di canali,
non assunta dal solo run 680. Il rapporto DC²/AC² e la fase non cambiano.

Il guadagno salvato resta il valore **nominale 143 dB**: le tensioni equivalenti
input-referred sono ottenute dividendo per 10^(143/20), i quadrati per
10^(143/10). Non si applicano kz o altri guadagni insieme a questo fattore.
Queste quantità nominali non sono una nuova calibrazione fisica di modo o frequenza.
Il CSV separa esplicitamente colonne ADC e nominal input; nessun fit di guadagno.

## Cosa viene calcolato

### 1. Long-term, 260 run

`longterm.py` legge i momenti full-run e la tabella termometrica già esistente,
con timestamp di acquisizione, non orari di ricostruzione. Genera:

- medie I e Qhardware prima della sottrazione, modulo e fase della DC;
- DC², AC², totale² e DC²/AC²;
- traiettoria del centro IQ nel piano I,Qeff con tempo di acquisizione;
- una vista della DC nominal input distinta dalle tensioni ADC.

I colori mantengono le convenzioni precedenti: dati teal `#007F86`, modello
purple `#7657A6`, teoria navy `#263952`, controlli/fit arancio `#e36e18`, sorgenti
I/Q cyan `#43a1ed` e orange `#ed812a`. Il gradiente della traiettoria codifica
esplicitamente il tempo e non sostituisce l'identità dei modi.

### 2. Correlazioni e controlli delle derive

Per ciascun modo, componenti e modulo DC sono confrontati con AC² e T15/T16/T17;
sono studiate anche le componenti dei modi fra loro e gli stati hardware numerici.
Si riportano Pearson sui livelli, Pearson sui residui di trend temporali lineari
**e cubici**, e Pearson delle differenze fra run consecutivi. Si escludono differenze
attraverso intervalli temporali oltre tre volte il passo mediano.
Nessun p-value iid, nessuna attribuzione causale. I residui di un trend scelto non
rimuovono necessariamente ogni deriva comune. Il rapporto DC²/AC² contiene AC²
al denominatore: la sua correlazione con AC² ha anche un accoppiamento matematico.

Le impostazioni LO registrate nei BOR, il range ADC e il guadagno nominale sono
costanti: le loro correlazioni non sono identificabili, non sono poste uguali a
zero. Non sono stati individuati monitor numerici per-run dei guadagni fisici
RF/LF nei campi hardware esaminati. I BOR sono snapshot registrati: non provano
che un amplificatore sia rimasto stabile o che non vi siano state variazioni
interne ai run. I flag on/off sono riportati, non reinterpretati come misure RF.

### 3. PSD e controlli sintetici

`intervals.py` applica tre trattamenti: nessuna sottrazione, media unica sui
16 SPEC analizzati, media per SPEC **solo diagnostica**. Non modifica i raw.
Calcola I, Qeff, i due lati dello spettro complesso e la matrice incrociata.
Con Qeff=Im(z), `C=FFT(I)conj(FFT(Qeff))` e
`S_z(+f)=S_I+S_Q+2 Im(C)`; usando Qhardware il segno cambia.

PSD Welch non sovrapposte, Hann simmetrica, senza detrending automatico ulteriore.
Lunghezze FFT: 16,384; 262,144; 1,048,576; 4,194,304 campioni (circa 3.28 ms,
52.4 ms, 209.7 ms, 838.9 ms). Densità bilatera in V²/Hz; i grafici di forma sono
normalizzati al proprio plateau |f|=0.5–1.5 MHz, non adattati al guadagno dei dati.
Le finestre brevi sono stimate su più segmenti dello stesso intervallo continuo.

Larghezze descrittive: annuli 1 kHz, media mobile di cinque annuli, metà del
proprio deficit rispetto al plateau. La profondità è smussata, non il minimo
puntuale dei bin. Il centro è il baricentro del deficit entro ±50 kHz, escludendo
±500 Hz; dove un notch è assente la coordinata non è un parametro fisico.
Non sono fit di frequenze di taglio, né misure con incertezza indipendente.
Una riga DC residua può alterare i primi bin e la profondità smussata: il suo
comportamento non va confuso con la depressione su decine di kHz.

Controlli sintetici con semi fissi e stesso trattamento: rumore gaussiano bianco
proprio con offset costante; separatamente rumore filtrato con passa-alto causale
primo ordine 12.5 kHz, seguito dallo stesso offset. Il cutoff è illustrativo,
**non ottenuto da un fit al run 680**. Sono scartati 65,536 campioni di warm-up.

### 4. Medie su scale differenti

Blocchi non sovrapposti da 128 a 2,097,152 campioni, almeno otto medie per punto:
25.6 microsecondi–0.41943 s. Si conserva la media complessa per SPEC e si confronta
la varianza delle medie con AC²/N e con l'integrale della PSD per la risposta
quadratica esatta del boxcar discreto. La previsione usa PSD Welch con segmenti
2^18 e non rimuove separatamente la media dei segmenti.

La griglia Welch non risolve la parte a bassissima frequenza richiesta dai tempi
lunghi: i punti sono marcati `PSD LF unresolved`, non interpretati come previsioni
quantitative affidabili. La corrispondenza ai tempi risolti è un controllo interno
sullo stesso intervallo, non una previsione indipendente. A pochi blocchi anche la
varianza empirica è poco precisa e usa la convenzione di popolazione.
Il campione di 3.36 s non determina la stabilità intrarun per tutti i 209.7 s.

### 5. Rice e Rayleigh senza fit arbitrari

Si usa Rice con `nu=|mu|`, `sigma²=AC²/2` dai momenti misurati, senza adattare
parametri o guadagni. Gli istogrammi **full-run raw già salvati** sono riutilizzati
sui quattro run selezionati. Per il segnale dopo la sottrazione della media
complessa si usano i campioni dei brevi intervalli: Rayleigh con sigma misurato.
Il controllo log(CCDF) contro A²/AC² ha previsione `log CCDF=-A²/AC²`.

Rice/Rayleigh esatte richiedono quadrature gaussiane isotrope e proprie. Si riporta
anche il rapporto di pseudo-covarianza: anisotropia, correlazioni, quantizzazione e
derive limitano il modello. Gli scarti CDF binned sono descrittivi, senza p-value
per campioni indipendenti; in CCDF si richiedono almeno 20 conteggi di risoluzione.
Non si usa un istogramma dell'inviluppo meno la sua media per simulare z-mu.

## Risultati e conclusioni della prima esecuzione

1. In circa **15.33 ore** di acquisizione, |DC| varia fra **0.170–0.484 mV** nel
   TM010, **0.567–1.256 mV** nel TM011, **0.0423–0.1159 mV** nel TM012, all'ADC.
   DC²/AC² resta piccolo: rispettivamente circa 2.65e-5–2.25e-4,
   7.09e-4–3.67e-3, 9.27e-6–6.69e-5. Il centro non è costante fra run.
2. Esempio TM010: correlazione |DC|–AC² **−0.971** sui livelli, **−0.635** dopo
   trend cubico, **−0.120** sulle differenze consecutive. |DC|–T15 passa da
   **+0.949** a **+0.332** e **−0.003**. Le associazioni sono fortemente dipendenti
   dalla scala temporale; non dimostrano un effetto causale della temperatura.
3. Nei quattro intervalli, la larghezza TM010 centrata è circa **25 kHz**, con
   profondità smussata **17.0–17.3 dB** nelle diverse FFT. Il baricentro descrittivo
   è entro circa 0.5 kHz da zero. La DC cambia sostanzialmente, la larghezza no
   alla risoluzione di questo stimatore. TM011/012 non hanno una depressione analoga.
4. Nessuna media vs media globale: PSD sopra 1 kHz invariata alla precisione
   numerica. Il centraggio per SPEC cambia la PSD TM010 integrata in norma L1
   fra 1–100 kHz di circa **0.7–1.1 parti per milione**. Modifica invece i primissimi
   bin. La profondità vicino a zero risente della riga DC e dello smussamento.
5. Il controllo bianco con offset **non produce una depressione larga**. Il
   controllo passa-alto conserva una depressione fisica sotto tutti i trattamenti.
6. Fra 25.6 e 409.6 microsecondi, varianza delle medie TM010 circa **T^-1.89** nei
   quattro run; TM011/012 circa **T^-1**. Controlli sintetici: bianco T^-1.00,
   passa-alto T^-1.95. Alle scale brevi risolte le previsioni dalla PSD seguono
   i valori osservati; alle scale lunghe la risoluzione della previsione è insufficiente.
7. Il segnale ha un offset persistente su più SPEC e una deriva long-term: non è
   ben descritto come la sola media accidentale di rumore bianco a media nulla.
   Ciò non distingue un offset strumentale da ogni possibile rumore molto lento,
   né garantisce stabilità sull'intera durata di ogni run.
8. Rice raw e Rayleigh dopo centraggio sono descrizioni approssimate, non esatte:
   gli scarti CDF sono dell'ordine di 1e-4–1e-3 e la pseudo-covarianza è circa
   4–5% nei brevi intervalli. Nel TM010 nu/sigma è molto piccolo: la correzione
   Rice rispetto a Rayleigh non può spiegare il notch della PSD. L'effetto della
   DC sulla distribuzione raw è più visibile nel TM011.

La depressione larga del toy non è spiegata dalla sottrazione della DC dei dati.
Il comportamento del TM010 è coerente con soppressione fisica delle basse frequenze
in entrambe le quadrature, ma questi controlli non identificano lo stadio.
Un modello con rumore passa-alto e offset aggiunto a valle è compatibile con una
DC non nulla e un notch AC; non è l'unica spiegazione. La posizione delle sorgenti
di rumore e la differenza della risposta LF fra impostazioni restano da verificare.
Non sono stati corretti i guadagni, alterati i fit storici o aggiornate le slide.

## Riproduzione e prodotti

Dalla radice del repository, con NumPy/SciPy/Matplotlib/h5py e lettore MIDAS:

```bash
OPENBLAS_NUM_THREADS=1 python3 simulation/step7/dc_longterm_diagnostic/longterm.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 simulation/step7/dc_longterm_diagnostic/intervals.py
OPENBLAS_NUM_THREADS=1 python3 simulation/step7/dc_longterm_diagnostic/report.py
python3 -m unittest discover -s simulation/step7/dc_longterm_diagnostic -p 'test_*.py' -v
python3 -m unittest discover -s examples/tests -p 'test_iq_noise_v2.py' -v
```

Gli input esterni sono definiti in `common.py`: campagna v2 e CSV termometrico
sotto `analysis-work/Run2/reports/noise_fullrange_v2_20261109/`; raw originali sotto
`/home/mazzitel/flash-data/data/LNF/`. Adattare i percorsi per altri workspace.
I dati non sono inclusi nel repository e i test indipendenti non li richiedono.

Output separati:
`/home/mazzitel/HFGW/analysis-work/Run2/simulation/step7/dc_longterm_diagnostic/`.
Il README generato lì contiene le tabelle complete. Prodotti principali:

- `longterm.csv`, `longterm_summary.json`, `hardware.json`, `product_manifest.json`;
- `longterm_DC_AC.png`, `IQ_center_trajectory.png`;
- `correlations.json`, `correlation_controls.png`, `between_modes_DC_correlations.png`;
- `interval_results.json`, `notch_metrics.csv`, `run*_spectra.npz`;
- `run*_PSD_centering.png`, `run*_DC_stability.png`, `run*_Rice_Rayleigh.png`;
- `synthetic_PSD_centering.png`, `synthetic_mean_stability.png`,
  `synthetic_Rice_Rayleigh.png`, `fullrun_fixed_distribution_residuals.png`;
- `notch_width_vs_DC.png`, `centering_low_frequency_zoom.png`,
  `diagnostic_summary.json`, `README.md` generato.

**Verifiche:** sei nuovi test indipendenti superati e cinque test originali v2
superati. Controllati ADC/DC/AC, segno della ricostruzione spettrale, effetto della
media globale, non mutazione dei campioni e rimozione del trend temporale.
Size e mtime dei 260 HDF5 originali risultano invariati alla fine: controllo
operativo d'integrità, non un confronto crittografico di tutti i dati. Gli hash dei
sorgenti usati sono nei metadati della diagnostica. Git contiene solo sorgenti,
test e documentazione; nessun dato, tabella numerica generata o figura.
