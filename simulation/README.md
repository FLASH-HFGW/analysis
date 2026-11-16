# Toy simulation FLASH — modello, convenzioni e riproducibilità

Sorgenti, configurazioni, documentazione e controlli sono in questa directory.
Dati misurati, curve numeriche ricostruite, HDF5/NPZ, figure e risultati restano
fuori da Git in `analysis-work/Run2/`. Non confondere una previsione condizionale
con una misura indipendente della catena.

## Percorsi e stato dei modelli

| Percorso | Scopo e stato |
| --- | --- |
| `step1/`, `step2/`, `step3/` | Sviluppo didattico: tono coerente, rumore filtrato, rumore elettronico. Parametri nominali storici. |
| `step4/FLASH_step04_thermal_model/` | Emissione termica della cavità senza tono, guadagno arbitrario per visualizzazione. |
| `step5/FLASH_step05_receiver_noise/` | Aggiunge il rumore equivalente del ricevitore; riusa esattamente la realizzazione dello step 4. La copia sorgente dello step 4 sotto `step5/` conserva la dipendenza relativa originale. |
| `step6/` | Parametri misurati della cavità e termometria; ADC/guadagno nominali storici. Include `parameters.json`, validatore e controlli fisici. |
| `toy_measured_response/` | Evoluzione con curve specifiche per modo e full-run; ipotesi storica di guadagno 67.4 dB, superata per il confronto principale. |
| `toy_calibrated_20261116/` | Scenario alternativo calibrazione fisica ±2 V e dati ±2 V; conservato, non adottato. |
| **`toy_ODB_cal5_data2_LF_20261116/`** | **Riferimento attuale:** calibrazione ±5 V, dati ±2 V da ODB, RF 103.4 dB, LF 60→20 dB. |
| `presentation_steps1_6_v41/` | Short common-input presentation examples through step6; current physical/ADC normalization, shared sources, explicit ADC markers. Historical steps unchanged. |
| `step7/` | Test analitico della dipendenza della forma LF dall'impostazione: contrae la risposta centrale, senza fit o variazioni dei guadagni. |
| `step8/` | Ipotesi LF fisica iniziale fc=12.5kHz, epsilon=0.02; IF primaria, calibrazione separata, confronto congiunto PSD/correlazione/medie. Nessun fit LF o guadagno. |
| `run620_comparison/`, `thesis_comparison/` | Confronti esplorativi e scenari storici, non sostituiscono il riferimento attuale. |

I README dei singoli step documentano lo stato storico del relativo codice;
le convenzioni attuali sono quelle indicate qui per il riferimento attuale.

## Modello fisico

Si simula l'inviluppo complesso, senza campionare la portante RF a circa 8.7 GHz.
Per ciascun modo, frequenza f0, Q0 e accoppiamenti kappa1/kappa2 vengono dalla
Tabella 6.1 della tesi di Valeria Spasiano. Si usa
`QL = Q0/(1+kappa1+kappa2)`, con smorzamento interno `ki=2*pi*f0/Q0` e totale
`kt=ki*(1+kappa1+kappa2)`. La sorgente termica interna è trasferita alla porta 2;
la porta 1 contribuisce allo smorzamento, senza inventare una sorgente incidente.
L'energia termica disponibile è `h*f0/expm1(h*f0/(kB*T))`, senza sommare un termine
di vuoto al rumore equivalente misurato. T=40.422386 mK proviene dal sensore AVS T15
nel run 680. L'opzione 30 mK dello step 6 è uno scenario distinto.

Il ricevitore è una sorgente gaussiana complessa indipendente, riferita all'ingresso,
con densità equivalente `kB*Tn`, Tn=3.955 ± 0.468 K. È una misura nella configurazione
senza TWPA, applicata condizionalmente ai tre modi. Non è un modello microscopico
dei singoli amplificatori. Il toy attuale moltiplica sia questa sorgente sia quella
di cavità per la stessa risposta scalare misurata: è un limite importante.
Le PSD analogiche nel supporto misurato vengono ripiegate per gli alias prima
della sintesi a 5 MS/s; fuori dallo sweep si assume risposta nulla.

## Convenzioni di normalizzazione e guadagno

- `z=I-iQhardware`, Qeff=-Qhardware. La coniugazione inverte frequenze e parte
  immaginaria della correlazione, non la sua parte reale.
- Tensione complessa: `E|z|²/R = integrale S_P(f) df`, R=50 ohm. PSD complessa
  bilatera; nessun fattore 2 aggiunto implicitamente. La scala Rayleigh di un
  rumore proprio è `sigma_q=sqrt(E|z|²/2)`.
- Le tre curve `kz(f)` sono distinte; si usa il coefficiente integrato del tono,
  non un'unica calibrazione per tutti i modi. Le curve sono input esterni derivati
  dalle acquisizioni, non dati da includere nel repository.
- RF 103.4 dB include il secondo FET da 36 dB: non sottrarlo come già contenuto
  nelle calibrazioni. La risposta di Valeria chiarisce che quel FET non vi entra.
- LF esterni: 60 dB durante la calibrazione, 20 dB nei dati. Al momento
  `kz_data = kz_cal/100`, cioè -40 dB in guadagno e fattore 1e-4 in potenza.
  Se si mantiene kz_cal invariato, il guadagno equivalente è 63.4 dB; non
  concatenarlo nuovamente con 103.4 dB. Il vecchio 67.4 dB era un'ipotesi diversa.
- Decisione corrente: fidarsi dell'ODB applicato dal frontend, calibrazione ±5 V
  e run 680 ±2 V. I vecchi FFT di calibrazione usavano già `10/65535 V/count`:
  nessuna ulteriore correzione di 0.4 alle curve. Per i raw del run 680 si usa
  `4/65535 V/count`. I prodotti storici convertiti a ±5 V richiedono una sola
  correzione V×0.4, PSD×0.16. Gli step iniziali usano invece convenzioni ADC
  nominali storiche, esplicite nei rispettivi sorgenti.
- Nessun guadagno o Tn è adattato per forzare l'accordo con il run 680.

## Tempi, spettro e confronto con il run 680

La correlazione normalizzata è `g1(tau)=C(tau)/C(0)`: un fattore di guadagno
costante si cancella. Una risposta dipendente dalla frequenza, o sorgenti con
spettri e pesi relativi differenti, modifica invece anche i tempi apparenti.
Per la sola cavità a singolo polo, il tempo di ampiezza è `QL/(pi*f0)`;
non è automaticamente il tempo del rumore totale dominato dal ricevitore.

L'analisi originale dei dati resta invariata: primi 5 SPEC continui (1.048576 s),
unica media complessa rimossa, Hann simmetrica, periodogramma visualizzato con
medie di 256 bin; covarianza lineare con normalizzazione N-lag e coppie attraverso
i confini SPEC. Il fit storico usa i massimi locali di **Re(g1)** e
`C + A exp(-t/tau)` con C libero, intervallo principale 0.3–4 us. Un confronto
puntuale di g1 nello step 7 non sostituisce quel fit né ne misura il tempo.
Il minimo largo del TM010 non deriva dalla sola sottrazione della media globale.

Per le soglie Rayleigh si usa `T_k=media(A)+k*std(A)` (k=3,5,7), non k*sigma_q.
Le fasi dei campioni di ampiezza esattamente zero sono escluse.

## Ipotesi aperte

1. La variazione LF 60→20 dB potrebbe cambiare la forma della risposta, non solo
   l'ampiezza. Lo step 7 esplora questa possibilità, senza affermare di averla
   misurata. Una contrazione può migliorare g1 e larghezza, lasciando errata la
   profondità del minimo. Servono anche tempi estratti con lo stesso estimatore.
2. Il rumore può essere generato in stadi diversi e attraversare risposte diverse.
   Un fondo bianco aggiunto all'uscita riempirebbe anche il minimo stretto osservato;
   da solo non basta a spiegare simultaneamente larghezza e profondità.
3. Il TM010 mostra squilibrio I/Q e banda immagine nel tono di calibrazione:
   manca una risposta vettoriale e la covarianza delle sorgenti. La sola risposta
   scalare non descrive questi effetti.
4. Guadagno RF, Tn e rapporto LF effettivo possono dipendere dal modo/frequenza.
   Prima della separazione dei modi gli LF vedono IF primarie circa 1.25, 44.971,
   105.313 MHz; non tutti vedono la sola IF finale di circa 1 MHz.
5. Restano da verificare fase della risposta, filtri/coupling reali e supporto
   fuori dallo sweep. Lo step 6 con LPF Butterworth ordine 4 era un'approssimazione.

## Ottimizzazioni già implementate

- Inviluppo complesso anziché portante RF; sintesi tramite fattore spettrale.
- Full-run corrente: FIR complesso di 65,537 coefficienti, convoluzione FFT
  overlap-save a blocchi, storia casuale per l'inizializzazione stazionaria e
  continuità fra blocchi. Controlli su potenza persa nella troncatura del FIR.
- Istogrammi, momenti e conteggi di coda accumulati senza salvare l'intero miliardo
  di campioni; vengono conservati i primi 5 SPEC per gli stimatori spettrali.
- Step 7: PSD e covarianza attese analitiche, senza rigenerare un full-run per
  ogni variante della risposta. Sono previsioni medie, non periodogrammi rumorosi.
- Numero di thread BLAS limitabile a 1 per evitare sovrapposizione non necessaria.
  Questi miglioramenti della simulazione non sono ottimizzazioni già applicate
  al programma di ricostruzione: la profilazione di quest'ultimo è separata.

## Riproduzione e verifiche

Dipendenze principali in `requirements.txt`; alcuni confronti con raw richiedono
anche il lettore MIDAS installato nell'ambiente sperimentale. I percorsi assoluti
presenti negli script descrivono il workspace LNF e vanno adattati altrove.
Il repository contiene il codice, non tutti gli input per una riproduzione offline:
servono termometria, prodotto HDF5 del run, curve kz ricostruite e parametri step 6.

Controlli fisici indipendenti dai dati sperimentali:

```bash
python3 -m unittest discover -s simulation/tests -v
```

Lo step 6 include controlli di regressione campione per campione sullo step 5,
PSD/potenza, due porte, ADC e distribuzioni (34 controlli nella validazione originale):

```bash
python3 simulation/step6/validate_step06.py --out /tmp/flash_step6_validation
OPENBLAS_NUM_THREADS=1 python3 simulation/step7/test_lf_response.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 simulation/toy_ODB_cal5_data2_LF_20261116/simulate_full_run.py
```

Gli step 1–5 storici scrivono prodotti e talvolta README nella loro directory.
Eseguirli in una copia esterna a Git; per lo step 5 generare prima lo step 4
nella directory sorella richiesta dal suo sorgente. Lo step 6 originale richiede
anche quell'archivio step 5. I controlli interni validano l'implementazione delle
ipotesi, non dimostrano la corrispondenza della catena reale.
