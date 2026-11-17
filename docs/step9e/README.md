# Step 9E — Low-frequency I/Q transfer and conjugate leakage

Diagnostica derivata da Step 9D, commit `1ac1533`. Usa le esportazioni FFT dei toni, le 18 verifiche indipendenti e i prodotti science già archiviati. La baseline v47.1 e gli Step 9A–9D restano congelati.

## Potenze assolute dei toni

[tones.csv](tones.csv) contiene tutti i **183 run di tono accettati** nei prodotti di calibrazione, su 182 frequenze distinte per modo e frequenza. Il punto ripetuto è conservato separatamente. Nella verifica contro il prodotto storico si usa lo stesso run rappresentativo per ciascun punto. A ogni run si leggono gli spettri complessi in potenza già salvati e si integrano due finestre disgiunte di 25 bin attorno al massimo e al suo speculare. Si sottrae la mediana spettrale, dividendo poi per ENBW Hann 1.50009156 bin, con FFT di 16383 campioni. Si conserva il valore coniugato prima dell'eventuale troncamento a zero dopo la sottrazione del fondo. Le potenze ricavate riproducono numericamente i punti del prodotto di verifica precedente. I picchi principali corrispondono alle IF previste entro un bin, includendo il ripiegamento oltre Nyquist. [Riduzione originaria](../../tools/diagnostics/audit_TM010_response.py)

Le colonne ADC sono tensioni quadratiche integrate, in V². Si usa il piano nominale del generatore di **−60 dBm = 1 nW**, `Vref² = 50 Ω × 1 nW = 5×10⁻⁸ V²`. Dividere per `Vref²` dà il rapporto di potenza riferito a 50 Ω, equivalentemente `P_ADC,50Ω / P_gen,nom`. La somma delle due righe spettrali è l'energia del tono in I e Q. Non si usa un fattore due ulteriore. La calibrazione ADC è già a ±5 V. La perdita generatore–Marki resta indeterminata e nessuno scenario cavi è applicato. Le righe oltre ±2.5 MHz conservano la IF analogica d'ingresso e la frequenza digitale del picco. Queste righe restano fuori dall'inferenza a due bande e dai grafici di trasferimento, perché i bin di uscita sono aliased. [Audit del piano del tono](../step9c/README.md)

## Chiusura I/Q e risposta delle quadrature

Siano `A_I, A_Q` le ampiezze delle due sinusoidi reali e δ l'errore rispetto alla quadratura ideale. Nel lato principale le due contribuzioni complesse si sommano, nel coniugato si sottraggono. Le potenze sono proporzionali a `A_I² + A_Q² ± 2 A_I A_Q cos δ`, con lo stesso prefattore. Per `a = A_I/A_Q` si ottiene:

```text
r = (a² + 1 − 2 a cos δ) / (a² + 1 + 2 a cos δ)
```

In [iq_checks.csv](iq_checks.csv), sulle 18 verifiche archiviate, il massimo scarto assoluto fra formula e rapporto coerente è **1.6e−16**, atteso perché entrambi derivano dalle stesse ampiezze sinusoidali. Il confronto indipendente con l'integrale dei chunk dà un massimo scarto assoluto **9.17e−5** sul rapporto lineare. È una verifica di compatibilità numerica, senza incertezze strumentali sufficienti per un test statistico.

Dapprima si ricava la potenza totale del tono dai chunk, `P_pair = P_main + P_conj` in V². Si usa l'ampiezza relativa (a) della verifica coerente per ripartirla in `V_Q,RMS² = P_pair/(1+a²)` e `V_I,RMS² = a² V_Q,RMS²`. I moduli `V_I,Q,RMS / V_ref,RMS` e i volt RMS sono riportati per le 18 righe. Il procedimento assume che il rapporto coerente rappresenti anche la potenza integrata dei chunk. Per gli altri toni le due potenze del segnale complesso da sole non separano le uscite I e Q.

Per **TM010**, usando la media delle potenze alle spalle ±1.033 MHz come riferimento per ciascuna quadratura:

| IF del tono | I / spalla I | Q / spalla Q | Somma / spalla della somma |
| --- | ---: | ---: | ---: |
| −147.54 kHz | 99.8% | 76.2% | 87.8% |
| −49.18 kHz | 91.7% | 24.9% | 57.8% |
| +49.18 kHz | 91.7% | 24.8% | 57.8% |
| +147.54 kHz | 99.9% | 76.2% | 87.9% |

Ai punti misurati il calo del tono riguarda soprattutto Q, con un calo minore in I ai punti più vicini a zero. A +49.18 kHz la potenza coniugata vale il 23.34% della principale. Sommare i due bin recupera la potenza redistribuita fra segni, mentre la coppia conserva solo il 57.8% della potenza di spalla. La perdita complessiva e lo spostamento di potenza sono quindi effetti distinti. [Grafico delle quadrature](tm010_quadratures.png)

## Risposta firmata e PSD diagnostica

Una mappa lineare sulle due quadrature reali può agire sia su (x) sia su (x^*). Infatti si possono riscrivere le quadrature di ingresso come ((x+x^*)/2) e ((x-x^*)/(2i)). Sostituendole nelle due equazioni lineari di uscita e componendo (z=I-iQ), si ottiene la forma a due coefficienti. Con la convenzione Fourier firmata:

```text
Z(f) = H+(f) X(f) + H−(f) X*(-f)

Tono all'ingresso +f: uscita +f da H+(+f), uscita −f da H−(−f).
Tono all'ingresso −f: uscita −f da H+(−f), uscita +f da H−(+f).

S_z(f) = |H+(f)|² S_x(f) + |H−(f)|² S_x(−f)
```

L'ultima relazione assume bande incorrelate nel termine coniugato, come per un ingresso proprio. Per stimare la PSD a +f si usano il principale del tono +f **e il coniugato del tono −f**. La somma dei bin per un singolo tono misura invece potenza di uscita a due frequenze. I coefficienti coniugati qui sono distinti dal folding di bande RF diverse causato dal secondo mixer, studiato negli Step 9C–9D.

[signed_pairs.csv](signed_pairs.csv) contiene 150 valutazioni firmate, accoppiando le frequenze rappresentative opposte entro 1 Hz e mantenendo solo coppie entro Nyquist. Le colonne H+ e H− sono moduli quadratici. L'ultima somma per PSD è il trasferimento puntuale per un ipotetico ingresso bianco e proprio, senza assumerne l'ampiezza. Per TM010 a −49.18 e +49.18 kHz risulta rispettivamente **14107** e **14792** (potenza normalizzata al generatore). La somma delle due uscite di ciascun singolo tono è invece circa **14448** e **14450**. Le due operazioni coincidono solo se la risposta coniugata ha un modulo simmetrico. [Grafico dei toni e delle coppie firmate](tone_transfer.png)

Le potenze non permettono di predire lo spettro complementare complesso. Per un ingresso proprio, la correlazione fra (Z(f)) e (Z(-f)) dipende dai prodotti complessi `H+(f) H−(−f) Sx(f)` e `H−(f) H+(−f) Sx(−f)`. Integrandoli si ottiene la pseudocovarianza. Servono le fasi dei prodotti e la loro dipendenza dalla frequenza.

## Confronti science, Step 7 e Step 8

- **Science Step 7.** I prodotti in [science_bands.csv](science_bands.csv) mostrano la depressione in entrambe le quadrature TM010 con semilarghezza a metà deficit di **12.5 kHz** per ciascuna. A 0–1 kHz, I e Q valgono **0.00705 e 0.00707** dei rispettivi plateau; a 40–60 kHz valgono **0.941 e 0.934**. In quest'ultima banda il rapporto RMS science I/Q è circa **0.981**, mentre quello del tono a +49.18 kHz è **1.897**. I rapporti science sono medie di banda normalizzate al plateau di ciascun canale. I toni sono punti normalizzati alle spalle, quindi il confronto è descrittivo.
- **PSD e leakage.** Nell'audit precedente, intorno a 50 kHz su entrambi i lati, i rapporti al plateau erano **0.944 science**, **0.472 scalare** e **0.585 includendo il coniugato**. Sono risultati archiviati del confronto di forma, con il suo estimatore e la sua interpolazione storica. Il calcolo nuovo usa solo coppie puntuali. Recuperare il coniugato attenua la depressione prevista intorno a 50 kHz, lasciando una differenza rispetto a science.
- **Pseudocovarianza.** Per il primo intervallo di 16 SPEC di run 680, [science_diagnostics.csv](science_diagnostics.csv) riporta `E[(z−μ)²]/AC²`, da varianze e covarianza archiviate in Step 7. I moduli sono **0.0404, 0.0470, 0.0416** per TM010/011/012. Per TM010 la parte reale è **−0.0249**, l'immaginaria **−0.0318**. È un momento aggregato sull'intervallo e la banda ADC, non una misura locale del rapporto coniugato né una stima della matrice I/Q.
- **Step 8.** La diagnostica archiviata del modello LF dà un minimo smussato di **0.0308** del plateau e una larghezza a metà deficit di **27 kHz** per TM010, contro **0.0173** e **25 kHz** science. Il modello descrive una depressione di entrambe le quadrature in termini di PSD equivalente. La presente verifica non identifica il componente fisico che la produce.

La griglia dei toni ha passo circa **98.36 kHz** e i punti più vicini sono **±49.18 kHz**. Non risolve la depressione science di larghezza circa 25 kHz. Non si interpola tra i due toni vicino a DC e non si introduce una risposta in quell'intervallo. Calibrazione e science differiscono per LO, guadagno FEMTO (60/20 dB) e range ADC (±5/±2 V). Gli stati AC/DC e 10/100 MHz non sono verificati. I prodotti archiviano moduli e 18 errori di quadratura in calibrazione; manca una caratterizzazione complessa su frequenze appaiate nel reale assetto science. Il confronto non localizza la causa della depressione né trasferisce lo sbilanciamento del tono al rumore science.

## Riproduzione

Con NumPy e Matplotlib:

```bash
python3 docs/step9e/build.py ../analysis-work/Run2 ~/flash-data/analysis/autoreco/Run2/fft_by_run
```

Lo script apre soltanto gli archivi FFT dei toni accettati e i JSON di calibrazione, Step 7 e Step 8. I dati science entrano come diagnostica preesistente. Nessun file raw, fit, Monte Carlo o nuova ricostruzione.
