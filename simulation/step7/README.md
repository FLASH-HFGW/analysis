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

## Punti realmente misurati dello sweep

`python3 simulation/step7/inspect_sweep_constraints.py` produce confronti separati
fra PSD originale dei dati e risposta al tono, mostrando i punti di calibrazione
e l'intervallo centrale non campionato. Le potenze sono normalizzate ciascuna al
proprio plateau |IF|=0.5–1.5 MHz: è un confronto di forma, non di guadagno assoluto.
Prodotti esterni in `analysis-work/Run2/simulation/step7/sweep_constraints/`.

Il gap centrale non permette di ricostruire un minimo stretto. Tuttavia la
attenuazione TM010 esiste già ai punti misurati vicini: non può dipendere soltanto
dall'interpolazione nel gap. La contrazione dello step 7 modifica anche la risposta
alle frequenze campionate, quindi richiede una risposta diversa nelle condizioni
scientifiche, non una semplice interpolazione alternativa degli stessi dati.
Il rumore può inoltre avere sorgenti e risposta I/Q differenti dal tono.

## Matrice spettrale I/Q della depressione centrale

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 simulation/step7/inspect_central_iq_spectra.py
```

Legge i primi 5 SPEC raw del run 680, una media globale per quadratura, Hann
simmetrica e PSD bilatera. Ricostruisce e verifica contro l'archivio originale
entrambi i lati dello spettro: con C=FFT(I) conj(FFT(Qhardware)),
`S_z(+f)=S_I+S_Q-2 Im(C)` e `S_z(-f)=S_I+S_Q+2 Im(C)`.
Le matrici vengono mediate su 256 bin prima di calcolare il coefficiente
incrociato normalizzato; la coerenza di un singolo periodogramma non sarebbe
una misura informativa. DC e Nyquist sono esclusi da questo raggruppamento.

Prodotti esterni in `analysis-work/Run2/simulation/step7/central_iq_spectra/`:
`central_iq_spectra.png`, `spectral_matrix.npz`, `summary.json`.
Il minimo del TM010 è già presente nelle due PSD separate, con larghezze
simili; non è prodotto dalla combinazione complessa I-iQ. Nelle bande esaminate
il termine incrociato non spiega la grande depressione. Questo orienta verso
una risposta comune in forma alle due quadrature (non necessariamente un unico
componente fisico) e/o alla collocazione del rumore. Non identifica uno stadio
hardware specifico e non elimina gli effetti I/Q osservati nei toni.

## DC long-term e controlli della depressione

La diagnostica separata [dc_longterm_diagnostic/README.md](dc_longterm_diagnostic/README.md)
riusa i 260 prodotti v2 dei run 680–939 e limita le verifiche raw a 16 SPEC di
quattro run. Comprende trend DC/AC, controlli delle derive nelle correlazioni,
PSD con tre centraggi e quattro durate FFT, medie a blocchi e Rice/Rayleigh
a parametri misurati. I risultati numerici e le figure restano fuori da Git.
