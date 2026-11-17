# Step 9C — Calibrazione misurata, risposta nominale e folding RF

Studio derivato da [Step 9B](../step9b/README.md), commit `c132e08`. La risposta nominale, le misure di tono e le previsioni condizionali sono disponibili separatamente. Il confronto con run 680 usa soltanto i prodotti v47 già approvati. L'integrazione riproduce la potenza analitica del toy archiviata prima della sintesi e della quantizzazione. La baseline v47.1, le calibrazioni e tutti i prodotti precedenti sono preservati.

## Tono e piani di riferimento

Il dato osservato è la risposta complessa in volt ADC del tono, ridotta al modulo RMS. Il denominatore è **223.607 µV RMS**, da −60 dBm nominali su 50 Ω. La tesi §5.2, Eq. 5.13–5.14, dichiara il setpoint. Il registro ODB archiviato associa il setpoint a `/Equipment/LocalOscill/Variables/power Pump` e la frequenza a `freq Pump`. Per esempio il run 500 (TM011) registra −60 dBm a 8779.217541 MHz e ADC ±5 V. La ricostruzione archiviata dà (k_z=80.0953) con integrazione, equivalente a 17.910 mV RMS ADC. Il picco da solo dà 70.7664, pari a 15.824 mV RMS. Tutti i punti e i run sorgente sono in [tone_points.csv](tone_points.csv).

La riduzione congelata costruisce (z=I-iQ) nella convenzione fisica e usa la potenza complessa integrata, non la potenza di una quadratura. L'archivio usa FFT Hann effettiva di 16383 campioni, con normalizzazione coerente. La procedura di ricostruzione somma 25 bin intorno al massimo (±12), sottrae la mediana spettrale per bin e divide per ENBW Hann 1.50009156 bin prima della radice. Il fattore ENBW recupera la potenza distribuita fra i bin e riduce lo scalloping rispetto al solo massimo. Le tensioni della calibrazione sono già in scala ADC ±5 V, (10/65535) V/code. I prodotti scientifici approvati sono in scala fisica ±2 V, (4/65535) V/code. La conversione di range non entra nuovamente nel rapporto. Gli estremi dei toni con picchi aliased usano la coordinata analogica (f_{RF}-LO_1-LO_2), come nella baseline. [Sorgente della riduzione](../../tools/diagnostics/reconstruct_daq_calibration.py), [registro v47.1](../v47_1/dependency_registry.json)

Il budget hardware parte dal connettore RF del Marki e termina su carico adattato da 50 Ω al BLP. Il ledger di normalizzazione del 16 novembre esclude il FET esterno dal percorso del tono. La tesi e i BOR non localizzano il nodo di iniezione rispetto al connettore RF del Marki con precisione sufficiente per fissare il livello incidente. Mancano misura di perdita o attenuazione fra generatore e Marki, disadattamento e misura di carico al piano ADC. Il confronto assoluto è quindi **condizionale all'equivalenza dei piani**, con potenza incidente nominale pari al setpoint. Se esistesse una perdita intermedia (L(f)) in dB, l'ampiezza rilevata rispetto al generatore sarebbe quella riferita al Marki moltiplicata per (10^{-L(f)/20}). Nessuna correzione è stata dedotta dal confronto. [Audit dei piani hardware](../hardware/README.md), [Step 9A](../step9a/README.md)

La convenzione è (P_{in}=V_{in,RMS}^2/50), (V_{z,RMS}^2=E|z|^2=V_{I,RMS}^2+V_{Q,RMS}^2). Nello scenario I/Q ideale l'ampiezza del tono complesso è (sqrt 2) volte la singola quadratura. Si usa perciò la colonna `summed_IQ_dB` di Step 9B. Si conservano l'assegnazione funzionale condizionale dei BPF e la curva FEMTO a 100 MHz. L5 e FET non figurano nelle curve di trasferimento coerente. La potenza del tono già convertito incorpora la conversion loss alla porta, senza un ulteriore fattore mixer.

## Confronti coerenti

- **Pari IF.** Si confrontano (|H_c(f)|) con (k_z(f)), (|H_s(f)|) con (0.01k_z(f)) e (|H_s(f)/H_c(f)|). Le RF sono diverse perché i LO differiscono. Il BLP è comune alla stessa IF, quindi si cancella nel rapporto anche dove il suo modulo assoluto è sconosciuto. In TM010 coincidono anche IF primaria e frequenza sullo splitter. Marki viene rappresentato dalla stessa conversion loss nominale nella banda. Resta il rapporto FEMTO, valutabile dal grafico a partire da circa 1 kHz.
- **Pari RF.** Si fissa la RF science associata a (f), si valuta la calibrazione a (f_c=f+Delta), con (Delta=(LO_1+LO_2)_s-(LO_1+LO_2)_c), pari a +959/+522/+626 kHz. Si confronta (|H_c(f_c)|) con (k_z(f_c)) e (|H_s(f)|) con (0.01k_z(f_c)). Il rapporto include il BLP alle due coordinate distinte. I valori nominali sono valutati oltre Nyquist solo come risposte analogiche dei componenti tabulati.

[coherent.csv](coherent.csv), [confronto assoluto](coherent.png) e [confronto di forma](shape.png) riportano entrambe le operazioni. Le curve di forma sono differenze in dB rispetto al punto dichiarato (f=1.250) MHz science, per ciascuna curva. La differenza di riferimento compare solo nel grafico diagnostico, mentre il grafico assoluto, i rapporti e l'integrazione non usano alcun riscalamento empirico. Al punto di riferimento la differenza nominale hardware calibrazione / kz è **+0.65/+0.85/+0.91 dB a pari IF** e **−0.84/+0.67/+0.77 dB a pari RF**. L'eccesso del rapporto science/calibrazione rispetto al −40 dB nominale vale **0.00/+0.06/+0.04 dB a pari IF**, contro **+1.69/+0.28/+0.30 dB a pari RF**. Segno e valore dipendono dalla coordinata, in particolare per TM010. La compatibilità del livello assoluto rimane condizionata ai piani di riferimento.

## Folding del mixer secondario

Per I e Q reali, LO comune in fase e quadrature ideali, la moltiplicazione può essere scritta (z_2(t)=2g_2cos(2pi LO_2t+phi)z_1(t)), seguita dal filtro finale. (g_2) qui è l'ampiezza di conversione al singolo prodotto. Il fattore 2 compensa la scomposizione matematica del coseno in esponenziali, quindi non aggiunge guadagno al valore di conversion loss già espresso per prodotto.

```text
Z2(f) = H_BLP(f) g2 [exp(+iφ) Z1(f−LO2) + exp(−iφ) Z1(f+LO2)]
RF_main  = LO1 + f + LO2
RF_image = LO1 + f − LO2
```

Il termine (f-LO_2) è alla IF primaria negativa e proviene dal lato basso di LO1 anche con Marki ideale. La reiezione immagine del Marki, invece, descrive una fuga tra le coordinate coniugate dovuta alla non idealità I/Q. Le alias ADC, infine, sommano frequenze **finali analogiche** distanti multipli di 5 MHz. Le tre operazioni agiscono su coordinate distinte. Modelli con LO secondari sfasati, squilibri o correlazione fra bande richiedono una matrice I/Q e i termini incrociati della PSD. Per rumore stazionario con componenti spettrali disgiunte e incorrelate, i due addendi sommano in potenza.

Nel caso bianco con PSD RF uguale all'ingresso Marki, (r(f)=|H_{image,s}(f)/H_{main,s}(f)|^2) e la moltiplicazione della sola PSD elettronica è (1+ho r(f)), con (ho=P_{RF,image}/P_{RF,main}). Il comune BLP si cancella. I valori nominali a LO reali sono in [folding.csv](folding.csv) e [folding.png](folding.png). (ho=1) è l'ipotesi di partenza, non un valore ricavato dai dati. Per il bypass TM010 non c'è un secondo mixer e (r=0). La densità dell'immagine include implicitamente qualunque differenza RF a monte del Marki, che non è determinata dai guadagni L5 misurati alle risonanze. Il termine termico della singola cavità resta sul ramo principale.

## Scenari analitici

A ogni frequenza analogica si usa (mathrm{PSD}_{e}=50,k_B(3.955,mathrm K),10^{G_{RF}/10}|K(f)|^2[1+ho r(f)]). La cavità usa il proprio spettro fisico al posto di (k_B T_n) e il solo ramo principale. Per riprodurre esattamente la toy full-run, in tutti gli scenari si mantiene il suo polo termico storico a 1 MHz, distinto dalla versione analitica a IF fisica documentata in Step 9A. È una scelta di confronto congelato e il contributo è tabulato a parte.

| Scenario | Guadagno RF | Fattore coerente (K) | Elettronica immagine |
| --- | --- | --- | --- |
| A | 103.4 dB | (0.01k_z(f)) | assente |
| B | L5 VNA per modo + 36 dB | come A | assente |
| C_IF | come B | (k_z(f)|H_s(f)/H_c(f)|) | assente |
| C_RF | come B | (k_z(f_c)|H_s(f)/H_c(f_c)|) | assente |
| D | come B | come B | moltiplicatore (1+r(f)) |
| E_IF / E_RF | come B | rispettivo C | moltiplicatore (1+r(f)) |

Per il VNA si usano i fit simultanei `free_eq69` approvati. I rapporti nominali C/E contengono già il cambio 60→20 dB. D/E moltiplicano la PSD coerente principale del proprio scenario per il rapporto immagine; l'intero hardware non viene concatenato a kz. D è valutato anche per (ho=0.5,2). Queste alternative lasciano invariata la PSD main e quantificano l'effetto di PSD RF differenti.

### Supporto e integrali

La baseline somma i tre contributi (f+mF_s), (m=-1,0,1) e (F_s=5) MHz. A/B conservano esattamente la sua convenzione di supporto compatto fuori dallo sweep analogico kz, fino a circa ±3 MHz. D usa lo stesso supporto e, sugli alias oltre Nyquist, valuta i rapporti upstream dalle tabelle Step 9B. C/E valutano ogni alias alla sua frequenza analogica, con risposta del BLP tabulata anche sopra 2.5 MHz laddove richiesta. Per C_IF/E_IF, un alias attivo con FEMTO non risolto è mancante. Per C_RF/E_RF si tiene l'unione del supporto storico e di quello traslato; se il termine richiesto manca dentro tale unione, il bin resta indeterminato. Anche una perdita hardware ignota su un alias attivo rende indeterminata la somma di quel bin. La convenzione compatta fuori supporto è un'ipotesi ereditata, priva di un limite misurato sulla potenza omessa. Nessun dato hardware mancante dentro il dominio modellato è sostituito con zero.

[powers.csv](powers.csv) riporta potenza elettronica, immagine, alias elettronici, potenza termica e RMS totale. Ci sono integrali per full-band e sette FIR reali Kaiser 8.6 da 2001 coefficienti, centrati sui BOR di run 680. Il confronto nelle bande usa i PSD v47 e in full-band i momenti AC v2. Le righe parziali danno **integrali sulla sola regione coperta** e A/B calcolati sulla stessa maschera. La tabella indica copertura in frequenza, nel peso FIR e nella potenza A. Il rapporto diretto con run 680 è calcolato sulle righe complete, mentre sulle righe parziali è dato solo il limite superiore derivato dalla potenza nota e dalla non negatività della parte mancante. Il supporto full-band è completo nel modello per A/B/D; C_IF/E_IF coprono tutto per TM011/012 e circa il 99.96% dei bin di TM010. C_RF/E_RF coprono **72.82%, 81.56%, 79.48%** dei bin rispettivamente e conservano **71.99%, 80.52%, 78.36%** della potenza A. Le bande centrali per C_RF/E_RF hanno peso FIR coperto pressoché unitario, con code del FIR che impediscono una previsione matematicamente completa. [psd.csv](psd.csv) e [psd.png](psd.png) contengono campioni della PSD bilatera ADC in V²/Hz, con celle vuote per i bin mancanti. Gli integrali usano una griglia separata (2^{20}) e verificano convergenza contro (2^{18}).

### Risultati

| Modo | A full-band elettronica (V²) | B full-band elettronica (V²) | D full-band elettronica (V²) | D/B banda centrale (dB) | Run 680/D banda centrale (dB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| TM010 | 7.384e−4 | 7.226e−4 | 7.226e−4 | 0.000 | 1.482 |
| TM011 | 1.877e−4 | 1.575e−4 | 3.150e−4 | 3.097 | 1.377 |
| TM012 | 7.066e−5 | 6.158e−5 | 1.233e−4 | 3.149 | 1.716 |

La banda centrale restituisce indipendentemente i tre scarti diagnostici attesi prima del trasferimento. Il folding full-band è +3.010/+3.016 dB per TM011/012. A pari IF, E_IF porta gli scarti centrali a +1.313/+1.680 dB nei due modi. A pari RF, E_RF eleva la previsione sulla maschera centrale di +1.493/+3.342/+3.330 dB rispetto a B, inclusa l'immagine. La differenza di TM010 è solo trasferibilità nominale; è sensibile agli offset dei LO e alla perdita BLP vicino al bordo, quindi non identifica una correzione misurata.

Con (ho=0.5) o 2, il folding centrale vale rispettivamente **1.819 o 4.886 dB** per TM011 e **1.854 o 4.956 dB** per TM012. Gli scarti run/modello corrispondenti variano da **+2.655 a −0.413 dB** e da **+3.011 a −0.090 dB**. Il modello non seleziona (ho) in funzione dei dati scientifici.

## Riproduzione

```bash
OPENBLAS_NUM_THREADS=1 python3 docs/step9c/build.py ../analysis-work/Run2
```

Dipendenze NumPy, SciPy e Matplotlib. Gli input esterni sono `diagnostics/normalization_audit_20261114/calibration_reconstruction.json`, `simulation/step6/metrics.json` e `simulation/toy_ODB_cal5_data2_LF_20261116/metrics.json` sotto Run2. Gli hash della calibrazione e dei parametri fisici sono controllati contro il ledger del toy. Il codice legge la funzione nominale Step 9B e le tabelle Step 9A senza modificarle. La potenza full-band A è verificata numericamente contro quella analitica archiviata dal toy, per ciascun modo.
