# Step 6 — parametri misurati, ricevitore condizionale, ADC nominale

> Stato storico dello step 6: le convenzioni nominali qui descritte sono conservate
> per riprodurre questo passaggio. Il confronto attuale usa curve kz distinte per
> modo, calibrazione ±5 V, dati ±2 V e LF 60→20 dB: vedi [README generale](../README.md).

Evoluzione dello step 5. Nessun tono coerente. Sorgenti, configurazione e istruzioni
restano in questa cartella; risultati scientifici e figure sono separati:

`/home/mazzitel/HFGW/analysis-work/Run2/simulation/step6/`

## Riproduzione

```bash
python3 /home/mazzitel/HFGW/analysis/simulation/step6/validate_step06.py
```

Dipendenze: NumPy, SciPy, Matplotlib, h5py. Il default usa la temperatura **misurata
nel run 680**, AVS T15: 40.422386 mK, mediana di 11 osservazioni. Non sostituisce
questa misura con i circa 30 mK descritti genericamente nella tesi. Uno scenario
separato è disponibile, senza sovrascrivere il principale:

```bash
python3 /home/mazzitel/HFGW/analysis/simulation/step6/validate_step06.py \
  --temperature thesis30mK \
  --out /home/mazzitel/HFGW/analysis-work/Run2/simulation/step6_thesis30mK
```

## Modifiche rispetto allo step 5

- Frequenza, Q0 e accoppiamenti delle **tre** risonanze dalla tabella 6.1 della tesi.
- Due porte esterne nel tasso di smorzamento: `QL = Q0/(1+kappa1+kappa2)`.
  La sorgente termica delle pareti è trasferita alla porta 2; la porta 1 contribuisce
  allo smorzamento. Il rumore incidente dalle porte non viene introdotto arbitrariamente.
- Emissione termica calcolata con occupazione Bose–Einstein alla temperatura misurata.
- Rumore equivalente del ricevitore `Tn = 3.955 ± 0.468 K`, misurato nella configurazione
  senza TWPA: la sua applicabilità ai tre modi e al run 680 resta **condizionale**.
- Guadagno RF della tesi **103.4 dB** distinto dal guadagno nominale completo **143 dB**
  usato nell'analisi. Sono piani di riferimento alternativi, non fattori da concatenare.
- Scala ADC ±5 V letta dalla configurazione del prodotto HDF5: è una convenzione
  operativa salvata, non una nuova misura indipendente del range hardware.
- Semi casuali dello step 5 mantenuti per TM010; realizzazioni indipendenti per gli altri modi.
  Prima delle modifiche vengono riprodotti i due contributi analogici dello step 5,
  confrontandoli campione per campione con il suo archivio originale.

## Cosa è e cosa non è calibrato

I parametri di cavità e la termometria provengono da misure; il guadagno RF e Tn
provengono dalle configurazioni documentate nella tesi. Non è dimostrato che tutte
queste misure siano simultanee e corrispondenti alla configurazione del run 680.
La tesi descrive curve **kz(f)** specifiche per modo, ma i valori numerici e le loro
incertezze non sono disponibili nei materiali individuati. Perciò:

- i risultati primari sono riferiti all'ingresso con convenzione esplicita
  `E|z|²/R = integrale PSD`, come nello step 5;
- la previsione all'ADC usa il guadagno **nominale** di 143 dB e va trattata come scenario;
- cutoff LPF 1.9 MHz documentato; forma Butterworth di ordine 4 ancora assunta;
- mixer I/Q ideale, nessun offset o squilibrio inventato, nessuna nuova componente
  di vuoto sommata al Tn equivalente;
- si propaga solo il contributo di incertezza di Tn all'RMS, esplicitamente parziale;
- gain e Tn non sono adattati al run 680 per forzare l'accordo.

Le tracce usano `z = I + i Qeff` con `Qeff = -Qhardware` nella convenzione `I-iQ`;
la coniugazione inverte il segno delle frequenze e della parte immaginaria della
covarianza. La coerenza temporale è `g1(tau)`, normalizzata alla varianza complessa,
non la coerenza spettrale fra modi distinti.

## Risultati e validazione

`metrics.json`: parametri, controlli, confronto col run 680 e SHA-256 degli input.
`step06_simulation.h5`: tutte le tracce e PSD, contributi separati, covarianze attese
ed empiriche, metadati. `expected_parameters.csv`: riepilogo numerico.
`assets/`: figure PNG/SVG per ogni modo e confronto delle correlazioni e delle ampiezze.

La prima esecuzione supera **34/34 controlli**: riproduzione dello step 5, due porte,
potenze contro integrali PSD, circolarità, distribuzioni marginali, covarianza
contro trasformata inversa della PSD, griglia/errore ADC e assenza di clipping
nella realizzazione simulata. Questi controlli validano l'implementazione delle
ipotesi dichiarate, non la corrispondenza assoluta con lo strumento reale.
