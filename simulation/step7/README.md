# Step 7 — ipotesi di risposta LF dipendente dall'impostazione

Test separato della prima ipotesi sulla depressione centrale dello spettro.
Il riferimento è `toy_ODB_cal5_data2_LF_20261116`, con ADC e guadagni invariati.
Non vengono modificati i dati del run 680 o le slide.

## Variazione controllata

Comprimi orizzontalmente la sola risposta centrale entro ±300 kHz con fattori
alpha = 1, 0.5, 0.25, 0.1. Per |f| < 300 kHz si valuta la risposta misurata a
sign(f) min(|f|/alpha, 300 kHz); fuori da questo intervallo resta identica.
Alpha=1 è il controllo. La scelta 300 kHz e i fattori sono ipotesi esplorative,
non parametri misurati o risultati di un fit. La mappa può creare raccordi
artificiali e non rappresenta ancora un circuito elettronico.

Restano fissi: calibrazione per modo, guadagno RF, rapporto nominale LF,
rumore equivalente, cavità, alias e segno IQ. Nessuna normalizzazione ai dati.
Si applica lo stesso test ai tre modi per includere controlli indipendenti.
Una eventuale risposta reale può dipendere anche dalla frequenza primaria IF.

## Calcolo e confronto

Si calcolano PSD attesa e autocorrelazione normalizzata tramite Wiener–Khinchin.
Per questa verifica non serve generare un intero run Monte Carlo.
Il run 680 viene letto dai risultati originali conservati: spettro primo 5 SPEC,
Hann e bin visualizzati da 256 punti; autocorrelazione originale invariata.
Il modello è una previsione analitica, non una realizzazione con uguale rumore
statistico del periodogramma. Le larghezze a metà depressione sono descrittive,
non frequenze di taglio fisiche; il livello di metà dipende dalla profondità.

Esecuzione: `OPENBLAS_NUM_THREADS=1 python3 test_lf_response.py`

Risultati: `/home/mazzitel/HFGW/analysis-work/Run2/simulation/step7/`
con `metrics.json`, `expected_response_scan.npz`, `lf_response_sensitivity.png`.

Un miglioramento verifica la plausibilità dell'ipotesi di forma, non dimostra
che il cambio 60→20 dB sia la causa. Per attribuirla occorre una misura della
risposta LF nelle due impostazioni. Profondità e forma I/Q restano verifiche
separate; non introdurre altri termini per mascherare questo limite.

## Tempi con lo stesso stimatore dei dati

Dopo il test della risposta eseguire:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 simulation/step7/compare_decay_times.py
python3 simulation/step7/summarize_decay_times.py
```

Il primo script importa il fit storico da `examples/fit_iq_correlation_decay.py`,
verifica la riproduzione esatta dei tempi archiviati del run 680, applica lo stesso
fit ai valori attesi e a 5 SPEC simulati per ogni variante. Finestra principale
0.3–4 us, sensibilità 0.3–3, 0.3–5, 0.7–4 us. Il grafico conserva l'asse 0–10 us.
Il MC usa FIR e overlap-save della simulazione completa, ADC ±2 V e semi uguali
fra le varianti per un confronto appaiato. Alpha=1 deve riprodurre la correlazione
della realizzazione di riferimento. Si verifica inoltre la covarianza FFT con
somme dirette a lag selezionati e l'assenza di clipping.

I prodotti restano in `analysis-work/Run2/simulation/step7/decay_times/`:
`fit_results.json`, `decay_times.csv`, `short_MC_comparison.npz`,
`matched_decay_fits.png`, `fit_window_sensitivity.png`, `decay_times_summary.md`.

Il fit del TM010 originale è scarsamente descrittivo: il suo parametro tau non
va interpretato fisicamente. La contrazione migliora la struttura temporale,
ma non risolve simultaneamente larghezza spettrale e tempo estratto. Anche gli
altri modi mostrano dipendenza dalla finestra nella previsione analitica:
il singolo esponenziale approssima la risposta totale. Questa scansione non
fornisce un intervallo di confidenza; un solo MC non è un ensemble di incertezze.
