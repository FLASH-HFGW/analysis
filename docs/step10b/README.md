# Step 10B — Experimental statistical comparison of the updated noise models

Confronto fra run 680 e i modelli H (ibrido) e N (hardware nominale) approvati in Step 10A, commit eee8e7e. Restano fissi Tn = 3.955 K, L5 VNA per modo e FET da 36 dB, poli termici alle IF fisiche e folding RF/ADC. H conserva kz × 0.01 e N usa il livello del solo hardware nominale. I modelli assumono PSD RF uguale nelle bande e sorgenti gaussiane proprie e incoerenti. Nessun parametro è stato adattato.

## Popolazione

I prodotti verificati del prefisso v47 e degli audit LF contengono PSD, statistiche e prodotti filtrati, senza la serie I/Q non filtrata richiesta. Il reader si è fermato dopo i primi **16 SPEC** di run 680, seriali **0–15**, timestamp MIDAS **1784909100–1784909104** (secondi interi). La decodifica validata interpreta le parole uint16 come int16 su otto canali interlacciati, con coppie 0–1, 2–3, 4–5, 4/65535 V/count e z = I−iQhardware. L'hash ODB e hash, seriali, timestamp e lunghezze dei primi otto SPEC sono verificati contro v47. [Registro dei 16 SPEC](population.csv)

Ogni SPEC da 1048576 campioni per modo dà quattro blocchi adiacenti di **262144** campioni, con indici iniziali 0, 262144, 524288 e 786432. Nessun blocco o coppia di campioni attraversa un confine SPEC. Totale **64 blocchi**, **16777216 campioni per modo** a 5 MS/s, equivalenti a **3.3554432 s** di campioni acquisiti. I prodotti full-run restano separati. Si mantiene in memoria un solo SPEC.

Si generano **64 blocchi indipendenti per modello e modo** della stessa durata. H e N condividono le estrazioni corrispondenti per il confronto appaiato. Blocchi, sorgenti e ordini alias sono indipendenti nel generatore. Le PSD per componente ricavate con le funzioni Step 10A/9D coincidono elemento per elemento con quelle salvate da Step 10A. I sei ADC originali di Step 10A passano nella stessa catena come [controlli](step10a_controls.csv), esclusi dall’ensemble.

## Proiezione, stimatori e riferimenti

- Ogni blocco **già ADC** riceve la stessa proiezione DFT firmata a 262144 punti (passo 19.0735 Hz), con 251659 bin conservati, |IF| ≥ 100 kHz. Per le toy questo avviene dopo maschera analogica e quantizzazione singola, eliminando anche la piccola componente fuori maschera dovuta alla quantizzazione.
- La proiezione tratta ciascun blocco come periodico e rimuove DC insieme al resto della banda esclusa. Si verifica Parseval fra potenze iniziale, rigettata e conservata. La potenza DC è tabulata separatamente. Scartando 2000 campioni per lato dopo la proiezione, la potenza media per popolazione e modo varia meno dello 0.008%. Il controllo del bordo è descrittivo. La proiezione resta non locale.
- La PSD bilatera è il periodogramma rettangolare dei blocchi già proiettati, modulo quadrato della FFT unitaria diviso per Fs, in V²/Hz ADC. I grafici calcolano medie in potenza su gruppi di 128 bin per lato senza attraversare la maschera. L'ACF è lineare con zero padding, divisore N−lag e nessun accoppiamento fra blocchi. Si conserva in V² e normalizzata al lag zero. Gli incrementi di fase circolari ai lag 1, 10 e 100 usano coppie valide dentro il blocco.
- I FIR usano i 2001 coefficienti Kaiser 8.6 e i sette centri BOR di Step 9D. Si applica la convoluzione a centro firmato, si scartano 2000 input per lato per evitare il wrap del FIR, si demodula e si decima ×20. Si rimuove la media di ogni segmento FIR. Restano **12908 campioni per banda e blocco** a 250 kS/s, **826112 per banda e popolazione** per modo. La fase di demodulazione è riferita all'inizio del blocco. Istogrammi, momenti e ACF FIR usano questi segmenti.
- Le grandezze assolute restano in volt ADC e V². Bin e soglie assolute condividono l'RMS analitico **N** della stessa maschera e banda, riportato come proper_reference_RMS_V nel prodotto completo. I volt simulati non sono riscalati. Le statistiche di forma usano il proprio RMS di blocco. Il riferimento gaussiano proprio ha varianza per quadratura RMS²/2, fase uniforme e CDF Rayleigh 1−exp(−u²), con u = |z|/RMS. Gli incrementi dipendono dalla correlazione temporale e si confrontano con l'ensemble.

## Fluttuazioni e code

Si riportano SD fra blocchi e fra medie SPEC, più errori descrittivi della media per gruppi di 1, 2 e 4 SPEC consecutivi. Il grafico principale usa otto gruppi da due SPEC. I grafici PSD mostrano i quantili 16/84% delle medie di gruppo. Queste misure evitano l'ipotesi di campioni IID. La dipendenza su tempi più lunghi resta indeterminata in questo prefisso.

Le [code empiriche](tail_counts.csv) contano campioni oltre 2, 3 e 4 RMS, con soglie fisse in volt (riferimento N) e soglie di forma (RMS per blocco). Si riporta la frazione con almeno 20 superamenti distribuiti in almeno quattro SPEC o gruppi simulati omologhi. Altrimenti si conservano solo conteggio e popolazione. In forma full-band a 3 RMS, i dati danno **2120/1980/2094** superamenti in TM010/011/012, con frazioni vicine alle toy. A 4 RMS danno **1/2/1**, insufficienti per stimare la probabilità. Le frazioni sono per campione e non definiscono episodi o falsi trigger.

## Risultati

| Modo | RMS dati / H / N (mV ADC) | Dati / H / N, centrale (mV ADC) | Dati/N full (dB) | Dati/N centrale (dB) |
| --- | ---: | ---: | ---: | ---: |
| TM010 | 31.697 / 26.598 / 27.223 | 3.096 / 2.615 / 2.820 | +1.322 | +0.812 |
| TM011 | 20.320 / 17.383 / 18.271 | 1.993 / 1.703 / 1.891 | +0.923 | +0.455 |
| TM012 | 13.449 / 10.876 / 11.659 | 1.320 / 1.083 / 1.208 | +1.241 | +0.770 |

- **Livello assoluto.** N è più vicino ai dati in full-band e in tutte e sette le bande per ciascun modo. Lo scarto dati/N nelle sette bande va da **0.36 a 0.99 dB**. Restano differenze di livello e di forma della PSD.
- **Forma e correlazioni.** La CDF di ampiezza full-band aggregata dei dati dista dalla Rayleigh al massimo **5.9×10⁻⁴** sullo spazio normalizzato. La distribuzione congiunta I/Q e la fase conservano differenze più evidenti. H riproduce meglio l'ACF complessa full-band in tutti i modi, con RMSE sui lag 1–128 di **0.00087–0.00269**, contro **0.0161–0.0174** per N. Al primo lag la parte reale nei dati è circa **−0.052 a −0.062**, negativa come H, mentre N dà **+0.048 a +0.051**. Nei FIR centrali il valore è circa 0.94 per tutti, sulla scala temporale del FIR.
- **Pseudocovarianza.** Per z = I−iQhardware si usa var(I)−var(Q)−2i cov(I,Q), centrata per blocco. Il modulo normalizzato medio per blocco full-band è **0.04036 / 0.04727 / 0.04168** nei dati, contro **0.00252–0.00277** nelle toy proprie. Nei dati persistono entrambe le componenti firmate. Nelle toy le medie firmate sono vicine a zero e il modulo ha un fondo positivo da campione finito. Nei FIR la popolazione effettiva è inferiore e il solo modulo campionario centrale non separa nettamente dati e toy. I risultati non identificano una matrice I/Q e non usano correlazioni di potenza per inferire coerenza istantanea fra modi.

## Prodotti e riproduzione

[Osservabili e dispersioni](observables.csv), [diagnostica di forma e ACF](distribution_diagnostics.csv), [grafico sintetico](comparison.png). La directory locale `../analysis-work/Run2/simulation/step10b/` contiene anche metriche per blocco, tutti gli osservabili, metadati, HDF5 di istogrammi/PSD/ACF aggregati e sei grafici dettagliati full-band e FIR. Le serie temporali dell'ensemble e dei dati non vengono persistite.

Dalla radice, con NumPy, SciPy, h5py, Matplotlib e il reader MIDAS dell'ambiente:

```bash
OPENBLAS_NUM_THREADS=1 python3 simulation/step10b/run.py \
  ../analysis-work/Run2 ~/flash-data/data/LNF/run00680.mid.gz \
  ../analysis-work/Run2/simulation/step10a /path/to/fresh-step10b
python3 simulation/step10b/report.py /path/to/fresh-step10b docs/step10b
```

Lo studio si ferma a Step 10B. Nessun fit, ricostruzione full-run, simulazione full-run o presentazione.
