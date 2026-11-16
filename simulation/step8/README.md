# Step 8 — prima ipotesi fisica di soppressione LF

Nuovo modello separato, basato sulla diagnostica DC dello step 7, commit
`29c10aca03c5009b9351d69f3f10442c6b4dca61`. Non modifica sorgenti scientifici,
prodotti o risultati degli step precedenti. **Nessun fit di fc, epsilon o guadagno**:
i parametri iniziali sono indicativi e gli scarti dai dati vengono conservati.

## Ipotesi iniziale e distinzione dalla DC coerente

Risposta in potenza alla frequenza primaria u:

```
F(u) = (u² + epsilon*fc²)/(u² + fc²)
fc = 12,500 Hz
epsilon = 0.02
```

Una realizzazione analogica stabile e causale è
`H(u)=(i*u+sqrt(epsilon)*fc)/(i*u+fc)`, quindi |H|²=F. Il guadagno ad alta
frequenza è unitario; a DC la potenza residua è 2%, l'ampiezza sqrt(0.02).
**Epsilon descrive la PSD del rumore vicino a zero, non DC²/AC²**. La media
complessa coerente estratta dalla v2 è una quantità diversa e non fissa epsilon.

Il polo LF ha tempo `1/(2*pi*fc)=12.7324 us`. Non è il tempo di circa un
microsecondo estratto dal fit esponenziale dei massimi dell'autocorrelazione
completa: quel fit descrive una parte della risposta totale, incluso il LPF.
Non si sottrae un offset dalla covarianza per migliorare artificialmente l'accordo.

## Dove agisce il filtro

Si applica la risposta LF **alla IF primaria**, prima della seconda conversione:
`u=f_finale+f_LO_secondario`. Il piano di frequenza è verificato contro i BOR
riutilizzati dalla diagnostica step 7:

| Modo | IF primaria alla cavità | LO secondario | IF finale alla cavità | Centro del notch nel piano finale |
| --- | ---: | ---: | ---: | ---: |
| TM010 | 1.250 MHz | 0 | 1.250 MHz | 0 |
| TM011 | 44.971 MHz | 43.723 MHz | 1.248 MHz | −43.723 MHz |
| TM012 | 105.313 MHz | 104.057 MHz | 1.256 MHz | −104.057 MHz |

LO primario = 8.735869 GHz. Per TM011/012 la soppressione è fuori dalla banda
finale acquisita: non viene imposta una depressione artificiale a zero in tutti
i modi. Le frequenze di cavità e gli accoppiamenti restano quelli misurati dello
step 6; la IF di cavità qui è ricavata dagli LO, senza cambiare i dati precedenti.
La seconda conversione resta una traslazione scalare ideale, non una matrice
completa con tutte le immagini e le correlazioni I/Q.

## Separare risposta di calibrazione e risposta nella presa dati

Le curve kz integrate specifiche per modo contengono già mixer, filtri e la
risposta LF della configurazione di **calibrazione**. Non si assume che la
configurazione dati a 20 dB abbia la stessa forma di quella di calibrazione a60dB.

La decomposizione non è misurata separatamente e deve restare esplicita:

```
kz_cal(f) = kz_envelope(f) * sqrt(Fcal(f))
kz_data(f) = 0.01 * kz_envelope(f) * sqrt(Fdata(f + LO_secondario))
```

Nel codice lo 0.01 è applicato alle curve una sola volta prima della fattorizzazione.
Per TM010 l'inviluppo, entro ±300 kHz, interpola linearmente le due spalle della
curva misurata; fuori coincide con kz_cal. Si definisce quindi esattamente
`Fcal=|kz_cal/kz_envelope|²`. Per TM011/012 si conserva la curva senza rimuovere
una depressione non osservata in quella banda. Questo è un **de-embedding
condizionale**, non la misura di un filtro LF o un nuovo fit della calibrazione.

Si sostituisce Fcal con Fdata. La semplice moltiplicazione `kz_cal*sqrt(Fdata)`
conterebbe due volte il notch: è mostrata solo come controllo errato separato.
Controlli a spalle ±200 e ±500 kHz quantificano la non unicità del baseline;
nessuno viene selezionato a posteriori per ottenere il tempo più vicino ai dati.
Non è identificabile dalla sola curva kz quale componente fisico produca il notch.

**LPF:** la risposta finale misurata è già contenuta in kz_envelope. Non viene
moltiplicata una seconda volta per un Butterworth ideale a 1.9 MHz. La risposta
misurata, incluso il roll-off, entra nella PSD analogica prima del campionamento.
Si sommano gli alias f−fs, f e f+fs nel supporto dello sweep, con fs=5 MS/s;
fuori dallo sweep resta l'assunzione di risposta nulla. Il contributo alias alla
potenza prevista è circa 3.4–4.5%: non viene eliminato o ignorato.

## Normalizzazione assoluta congelata

Rimangono i valori del toy di riferimento `toy_ODB_cal5_data2_LF_20261116`:
RF103.4dB, Tn3.955K, rapporto di ampiezza LF dati/calibrazione0.01, impedenza50ohm,
calibrazione ADC±5V e dati ADC±2V, `4/65535 V/count` per la quantizzazione dati.
Non si adatta un guadagno globale o per modo. Riempire la depressione cambiando
la forma può modificare fisicamente l'integrale della PSD: non si rinormalizza
quel cambiamento per mantenere arbitrariamente il vecchio RMS.

Le previsioni sono in V ADC e V² ADC/Hz, non in watt RF già calibrati. I confronti
PSD/plateau o varianza/AC² sono osservabili di forma esplicitamente etichettati,
non fattori applicati ai dati o alla normalizzazione assoluta. Le figure in unità
assolute mostrano anche gli scarti di ampiezza che restano.

## Due interpretazioni dello stesso spettro

L'identità è

```
F(u) = (1-epsilon)*u²/(u²+fc²) + epsilon.
```

1. Una sorgente gaussiana propria con PSD Sbase attraversa la risposta shelf H.
2. Due sorgenti gaussiane proprie indipendenti: ramo passa-alto con PSD
   `(1-epsilon)*Sbase*HP` e residuo `epsilon*Sbase`.

I pesi di potenza sommano a uno: non si aggiunge un nuovo budget di rumore libero
sopra al Tn fissato. A parità di Gaussianità, media e PSD, le due interpretazioni
hanno la stessa autocorrelazione, varianza delle medie e distribuzione Rice/Rayleigh.
Questi osservabili **non possono identificarle separatamente**.

L'equivalenza esatta specifica anche la forma della sorgente equivalente residua:
non è rumore bianco aggiunto dopo LPF/ADC, ma rumore con la stessa risposta
successiva del baseline. Nel regime dominato dal ricevitore è interpretabile come
rumore equivalente dopo LF e prima dei filtri successivi. Il piccolo contributo
di cavità è incluso nella fattorizzazione matematica del totale; per un modello
microscopico le singole sorgenti e i loro piani andranno separati. Non si afferma
che la sorgente equivalente così costruita sia una temperatura fisica misurata.
Una risposta coerente a un tono LF o la conoscenza della posizione delle sorgenti
potrebbero distinguere le interpretazioni, a differenza della sola PSD gaussiana.

La DC ADC osservata viene aggiunta come offset costante **dopo** la sintesi del
rumore, uguale nelle due costruzioni. Non è usata per regolare epsilon o il rumore.
La sua posizione fisica reale resta da identificare.

## Varianza delle medie e transizione

Per il limite ideale con baseline bianco bilatero S0 e banda infinita:

```
V(T) = S0 * [epsilon/T
       + (1-epsilon)*(1-exp(-2*pi*fc*T))/(2*pi*fc*T²)]
```

A tempi intermedi domina approssimativamente il termine T^-2; con epsilon0.02
l’intervallo è limitato e la pendenza locale non raggiunge esattamente−2.
A tempi lunghi il residuo introduce
T^-1. L'uguaglianza dei termini asintotici è
`Tcross=(1-epsilon)/(2*pi*fc*epsilon)=0.623887 ms`. Con epsilon=0 non compare
questa transizione e il limite resta T^-2. Per gli stessi presupposti ideali,
la covarianza del rumore ha termine negativo
`-(1-epsilon)*pi*fc*S0*exp(-2*pi*fc*|tau|)` oltre alla delta bianca; il LPF modifica
l'origine e la risposta breve, senza eliminare la coda LF.

La previsione completa integra la PSD campionata per la risposta quadratica del
boxcar discreto. Risolve esplicitamente le prime128 oscillazioni, poi integra su
griglia logaritmica la coda con sin² mediato a1/2. Il raddoppio del limite a256
verifica la convergenza: errore relativo sotto0.3% nei punti confrontati.
Questo evita di estrapolare una PSD Welch a griglia troppo grossolana verso DC.
Per il confronto con la varianza di popolazione di K medie consecutive si usa
`V(T)-V(K*T)`, includendo la rimozione della media finita del record.

## Simulazioni e dati riutilizzati

Per entrambe le interpretazioni si generano **16 SPEC per modo**, 3.3554432s,
con sorgenti indipendenti, FIR spettrale65537, overlap-save, preistoria casuale,
ADC±2V e controllo del clipping. Si verificano perdita di potenza FIR e
covarianza FFT contro somme dirette. Le due realizzazioni non sono un ensemble
di incertezze e non devono dare statistiche numericamente identiche.

Il modello LF dispone della realizzazione causale H; la sintesi stazionaria usa
fattori spettrali equivalenti e non pretende di misurare la fase dell'intera catena.
Non si simula un transiente di accensione o la portante RF a GHz.
La PSD analitica è quella del rumore analogico campionato; il MC include anche
la quantizzazione. Il suo piccolo contributo bianco stimato è registrato separatamente
e non controlla la transizione con epsilon0.02. Il controllo epsilon0 senza
transizione riguarda il limite ideale, senza il pavimento di quantizzazione.

Nessun nuovo raw sperimentale viene letto. Si riusano:

- PSD e autocorrelazione originali dei primi5SPEC del run680, congelate nel
  confronto del toy precedente;
- medie a blocchi e momenti dei16SPEC di quattro run dalla diagnostica DC step7;
- istogrammi raw full-run e momenti v2 del run680 per Rice in unità ADC;
- curve kz ricostruite, parametri di cavità step6 e snapshot hardware già estratti.

Le distribuzioni MC sono confrontate con Rayleigh dopo centraggio e Rice prima,
con sigma² dalla potenza **prevista** e offset ADC misurato, senza fit di distribuzione.
Il confronto full-run dei dati con Rice a momenti misurati è un controllo di forma
separato: quella scala non sostituisce la previsione assoluta del modello.

## Risultati iniziali: accordo parziale, non una soluzione completa

- La larghezza descrittiva TM010 è circa **27 kHz**, contro **25 kHz** dei dati.
  La profondità smussata prevista è circa **15.1 dB**, contro circa **17.6 dB**:
  epsilon0.02 non riproduce il minimo più profondo. Epsilon è il valore puntuale
  ideale F(0), non il minimo di annuli smussati.
- Il modello produce la coda negativa. Il fit storico sui massimi dà circa
  **1.257us**, contro **0.926us** nei dati TM010. Cambiando le spalle del baseline
  ±200/300/500kHz si ottengono circa1.063/1.257/0.954us: la fattorizzazione
  di calibrazione resta un'incertezza decisiva, non va nascosta scegliendo il caso migliore.
- La pendenza della varianza breve TM010 è circa **−1.783**, contro **−1.892**
  nei dati; TM011/012 restano circa−1. La transizione a T^-1 è verificata nel
  modello completo intorno a **0.61ms**, vicino alla previsione ideale0.624ms.
- A0.419s, anche confrontando V/AC², il modello TM010 è circa **31 volte sotto**
  la varianza osservata. Aumentare semplicemente epsilon renderebbe più superficiale
  un minimo già troppo poco profondo. Il residuo bianco epsilon non descrive da solo tutte
  le componenti lente o la non stazionarietà misurata.
- TM011/012 non sviluppano il notch a zero. La correlazione reale breve è simile
  ai dati, ma la correlazione **complessa** non è completamente riprodotta,
  soprattutto la parte immaginaria del TM011: resta il limite della risposta scalare.
- RMS previsti **27.430/13.701/8.406 mV ADC**, dati full-run v2 corretti
  **32.260/20.749/13.733 mV ADC**. Le distribuzioni hanno la famiglia gaussiana
  attesa nel modello, ma la scala assoluta delle ampiezze resta diversa dai dati.
- I due Monte Carlo verificano l'equivalenza statistica prevista: potenze entro
  circa0.1% dalle previsioni, assenza di clipping, Rice/Rayleigh appropriate per
  il modello proprio gaussiano. Non correggono l'anisotropia I/Q presente nei dati.

Non sono stati effettuati fit successivi di fc/epsilon né aggiunti termini lenti
per ottenere accordo. Un eventuale fit futuro dovrà essere separato da questo
riferimento iniziale e confrontare PSD, correlazione e medie congiuntamente,
con fattorizzazione di calibrazione e covarianza I/Q esplicitamente considerate.

## Riproduzione, test e collocazione dei prodotti

Dalla radice del repository:

```bash
OPENBLAS_NUM_THREADS=1 python3 -m unittest discover -s simulation/step8 -p 'test_*.py' -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 simulation/step8/run_initial.py
OPENBLAS_NUM_THREADS=1 python3 simulation/step8/report_initial.py
```

Dipendenze NumPy, SciPy, Matplotlib, h5py. Percorsi e ipotesi in `parameters.json`.
I test non richiedono dati esterni; per l'esecuzione servono i prodotti sopra
elencati, che non sono inclusi nel repository. Otto test verificano: risposta
causale, equivalenza delle sorgenti, limite bianco, transizione asintotica,
convergenza dell'integrazione, fattorizzazione kz, polo della coda negativa e applicazione alla IF primaria.

Output separati:
`/home/mazzitel/HFGW/analysis-work/Run2/simulation/step8_LF_initial_20261116/`.
Contengono `metrics.json`, `summary.json`, `expected_predictions.npz`, i sei
archivi MC, il README generato e le figure di confronto. Colori coerenti con
le analisi precedenti: dati teal, toy purple, teoria navy, controlli orange.
Tutti i prodotti numerici e grafici restano fuori da Git; nel repository sono
versionati solo sorgenti, configurazione iniziale, test e documentazione.
