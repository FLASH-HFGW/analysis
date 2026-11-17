# Step 9A — Ricostruzione L5 dagli sweep VNA del 24 luglio 2026

Questo studio estende il commit `d90f820` e usa la [baseline v47.1](../../v47_1/README.md), commit `1b2cb10`. Le sole osservazioni usate nel fit sono i nove sweep VNA identificati in [traces.csv](traces.csv), con basename e SHA-256. Per ogni modo i tre sweep hanno la stessa griglia, 2001 punti a passo 1 kHz. Si stimano i moduli dai dati complessi. Le curve originali, i fit e i residui con segno sono nei PNG per modo. Gli sweep coprono 2 MHz per ramo, mentre la prima banda di Nyquist è larga 5 MHz. L'effetto ADC riportato sotto assume quindi un guadagno scalare.

## Modello e fit

Si usa `δ = 2(f−f0)/f0` (detuning a banda stretta), `x = Q0 δ` e `a = 1+κ1+κ2`. Dalle Eq. 6.4–6.8, `S12_cav = S21_cav = 2√(κ1κ2)/(a+jx)`. In riflessione, la Eq. 6.9 richiede a q=0 il numeratore reale `κ2²−(1+κ1)²−x²` sul denominatore `a²+x²`, con parte immaginaria `−2κ2 x/(a²+x²)`. Nella Eq. 6.10 trascritta compare invece `1+κ1²`. Si valutano entrambe le espressioni, mantenendo in ciascuna la prescrizione della Eq. 6.10 `x² → (x+q)²` nel numeratore reale e lasciando invariati denominatore e parte immaginaria. q è adimensionale e libero. La funzione `intrinsic` restituisce le tre risposte complesse. La Eq. 6.11 e le Eq. 6.7–6.8 moltiplicano i moduli per coefficienti Abs positivi.

I fit `fixed_eq610` e `fixed_eq69` fissano f0, Q0, κ1 e κ2 alla Tab. 6.1. I fit `free_*` liberano f0, Q0 e κ2 simultaneamente, mantenendo κ1 fisso come nella tabella. Con scale di trasmissione libere, larghezza caricata e profondità di riflessione vincolano combinazioni dei parametri e non bastano per separare robustamente entrambi gli accoppiamenti. Si minimizza la somma dei quadrati in modulo lineare, normalizzando ogni traccia al suo RMS misurato per dare lo stesso peso relativo ai tre sweep. In assenza di incertezze strumentali questo obiettivo fornisce residui RMS relativi, senza un χ² calibrato. I multistart esplorano entrambi i lati dell'accoppiamento critico. `eq69` identifica la forma algebricamente coerente a q=0, con q libero nel fit.

| Modo | L5 fisso, eq69 (dB) | L5 simultaneo, eq69 (dB) | Controllo col più, simultaneo (dB) | RMS relativo fisso → simultaneo |
| --- | ---: | ---: | ---: | ---: |
| TM010 | 67.288 ± 0.022 | 67.306 ± 0.015 | −7.024 | 4.71% → 4.62% |
| TM011 | 66.636 ± 0.010 | 66.637 ± 0.004 | −14.181 | 1.49% → 1.39% |
| TM012 | 66.801 ± 0.009 | 66.803 ± 0.010 | −14.845 | 1.66% → 1.65% |

I ± sono errori standard locali condizionati alla parametrizzazione, al peso e agli sweep, stimati con covarianza sandwich HAC Bartlett di 50 lag (50 kHz), separata per porta e propagata con la covarianza completa dei log Abs. Un solo sweep per porta non consente di stimare la ripetibilità. Residui strutturati, rumore di S12, correlazione oltre 50 kHz, scelte di modello, deriva tra sweep sequenziali, piani VNA e calibrazione strumentale possono contribuire a uno scarto sistematico. Le differenze fra modelli sono riportate esplicitamente e non combinate con gli errori statistici.

Per TM010 il fit simultaneo preferisce di poco la soluzione sovraccoppiata (Q0 circa 64291, κ2 1.267), mentre la soluzione sottoaccoppiata (κ2 0.792) conserva l'accoppiamento della tesi. Gli RMS sono 4.6153% e 4.6163%, con differenza su L5 di circa 0.00006 dB. Per TM011 e TM012 il minimo coerente è sottoaccoppiato, con spostamenti f0 di +2.34 e −0.71 kHz e Q0 di circa 53531 e 38697. Il fit libero pesa tutti e tre gli sweep e può peggiorare il singolo residuo di riflessione anche se migliora l'obiettivo totale. La forma letterale Eq. 6.10 cambia L5 fino a 0.040 dB fra i fit fissi. [fits.csv](fits.csv) riporta tutti gli Abs, q, parametri e residui per porta, con [branches.csv](branches.csv) per le soluzioni vincolate ai due lati dell'accoppiamento critico.

## Controllo algebrico e dipendenza dalla frequenza

Si ricava `GL5 = 10 log10(Abs21 × Abs22 / Abs12)`; il controllo usa invece il prodotto di tutti e tre gli Abs. Il rapporto misurato `20 log10(|S21|/|S12|)` cancella il modulo intrinseco reciproco se i piani VNA sono compatibili. Misura `GL5−GL1`, quindi per ricavare L5 serve ancora la riflessione. Nella larghezza caricata nominale attorno a f0 le mediane sono 123.861, 123.239 e 123.347 dB, contro 123.859, 123.244 e 123.418 dB dai fit simultanei eq69. Sostituire il rapporto del fit con la mediana diretta cambia L5 di circa +0.001, −0.003 e −0.036 dB tenendo Abs22. I grafici del rapporto mostrano la dispersione e [fits.csv](fits.csv) riporta percentili e pendenze centrali descrittive (−0.026, −0.006 e +0.007 dB/MHz).

[local.csv](local.csv) divide la stessa finestra in sette intervalli e riporta le mediane del guadagno apparente, calcolato punto per punto dopo divisione per le risposte intrinseche del fit simultaneo eq69. L'escursione picco-picco delle mediane è circa 0.20, 0.42 e 0.11 dB. Residui di cavità e dei percorsi confluiscono nello stesso diagnostico. Queste variazioni non identificano la pendenza del solo L5 e non vengono estrapolate sul resto della banda ADC.

## Propagazione analitica all'ADC

Si assume Tn = 3.955 K e FET esterno = 36 dB, con piani compatibili tra uscita L5, FET e ingresso della downconversion. Il valore nominale del FET entra una volta. [adc.csv](adc.csv) riusa i termini analitici congelati dal [confronto Step 9A](../comparison.csv), full-band e sette bande FIR, moltiplicandoli per `10^((GL5+36−103.4)/10)`. kz, il polo termico, il rapporto LF e tutti gli integrali di riferimento rimangono quelli della baseline. La potenza della cavità viene scalata dal guadagno ed è riportata separatamente. Gli errori ADC sono relativi a un sigma, dal solo fit VNA; gli errori di FET, Tn e piani restano non quantificati.

Con il fit simultaneo eq69 i guadagni RF totali sono 103.306, 102.637 e 102.803 dB. Le potenze elettroniche full-band sono **7.226×10⁻⁴**, **1.575×10⁻⁴** e **6.158×10⁻⁵ V² ADC**, con variazioni **−2.14%, −16.11% e −12.85%**. Gli stessi fattori si applicano alle sette bande per l'ipotesi scalare. Nessun dato scientifico entra nella stima del guadagno.

## Riproduzione

Dalla radice del repository, con NumPy, SciPy e Matplotlib:

```bash
OPENBLAS_NUM_THREADS=1 python3 docs/step9a/vna/fit.py "$HOME/flash-data/data/LNF/calib"
```
