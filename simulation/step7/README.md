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
