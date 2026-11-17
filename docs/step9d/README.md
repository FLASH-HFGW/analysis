# Step 9D — Independent hardware noise prediction

Confronto fra due previsioni elettroniche indipendenti nel livello di downconversion, sullo stesso asse firmato della PSD archiviata di run 680. Entrambe usano i guadagni RF VNA approvati da Step 9A, il FET nominale da 36 dB e Tn = 3.955 K. Le incertezze sistematiche di guadagno, cablaggio, piani e stato effettivo dell'hardware restano quelle documentate. Lo studio deriva da Step 9C, commit `1c5e173`. v47.1, i dati e i prodotti precedenti restano congelati.

## Due catene analitiche

- **Ibrido.** Riusa lo scenario D di Step 9C. Per il ramo principale si usa la potenza di trasferimento `|0.01 kz(f)|²` e per il ramo immagine si moltiplica per `|H_image,science / H_main,science|²` di Step 9B. Il valore 0.01 agisce in ampiezza e rappresenta il passaggio da 60 a 20 dB. Sono mantenuti i LO science e la convenzione di supporto kz dell'ibrido congelato. Le correzioni di trasferibilità C/E restano scenari distinti di Step 9C.
- **Nominale.** Usa direttamente le due potenze di trasferimento assolute `|H_main,science|²` e `|H_image,science|²` di Step 9B, con la mappa BPF funzionale e FEMTO a 100 MHz. Il risultato nominale principale non usa kz per il livello né per stabilire il supporto dei propri alias. La tabella include anche una colonna diagnostica con il nominale ristretto al supporto degli alias kz per isolare la differenza di supporto.

Per entrambi, la PSD elettronica bilatera in V²/Hz è `50 · 10^(G_RF/10) · k_B · 3.955 K` moltiplicato per la potenza di trasferimento del percorso. G_RF = 103.306/102.637/102.803 dB. La convenzione è `E|I−iQ|²/50` per la potenza equivalente su 50 Ω. L'ingresso RF alle due bande del Marki è assunto bianco, con uguale PSD e bande incoerenti. Il termine immagine descrive il folding del secondo mixer da `u=f−LO2`; il principale viene da `u=f+LO2`. TM010 bypassa il secondo mixer. Il rapporto immagine assume I/Q ideali e LO secondari comuni in fase.

La cavità usa lo spettro lorentziano termico del modello approvato e solo il ramo principale. Il polo in questa analisi è alla IF fisica `f0−LO1−LO2`, cioè **1.250, 1.248 e 1.256 MHz**. L'ampiezza termica dipende dalla risposta dei due modelli e non entra nel folding elettronico. Il polo storico a 1 MHz resta nei prodotti precedenti. Il modello non aggiunge contributi di mixer, FEMTO o ADC e non duplica la perdita di conversione o il guadagno RF.

## PSD misurata, maschera e alias

Si legge `run00680.npz` dall'archivio `fft_by_run` con 1000 SPEC. Il registro v47 verifica I−iQ e identità col prodotto del job. SHA-256 verificato `27b0c97373134a0fcfeb018412a91eefd91631ad894dbc35a94e86e1e86f271c`. Dopo `ifftshift`, si usa la griglia effettiva a **16383** bin, passo circa 305.19 Hz, ADC fs = 5 MHz. Si applica una volta `(2/5)²` in potenza e si divide per l'ENBW Hann, circa 457.82 Hz. Le sette integrazioni della PSD misurata senza maschera riproducono le tabelle v47. Il full-band qui è la PSD archiviata con sottrazione della media per chunk, distinta dal momento AC v2 full-run. I modelli sono PSD analitiche valutate sui bin di quella griglia, senza smoothing o riscalamento sulla misura.

La [tabella PSD](psd.csv) mantiene distinte le tre componenti main, image e cavity, sia nella prima zona di Nyquist sia per gli alias `f ± 5 MHz`. Questi tre ordini sono usati nel confronto principale. L'ibrido conserva il supporto compatto storico di kz per gli alias; il nominale valuta gli ordini ±1 sulle tabelle originali, comprese le perdite BLP fino a 7.5 MHz quando richieste. La maschera comune esclude ogni bin con risposta diretta o contributo richiesto indeterminato. In pratica esclude `|f| < 100 kHz` per tutti i modi (BLP privo di modulo tipico, oltre allo splitter per TM010). Dati, ibrido e nominale sono integrati **sugli stessi bin** con pesi unitari o con i sette FIR Kaiser 8.6 a 2001 tap già usati da v47. La copertura è 96.002% dei bin e pressoché tutto il peso delle bande delle risonanze. Le regioni escluse restano visibili come interruzioni nel [grafico](comparison.png).

Il nominale è anche valutato per gli ordini superiori dove **tutti** i componenti nominali necessari sono definiti. Si esaminano fino agli ordini consentiti dalla tabella BLP (200 MHz), applicando anche i limiti degli altri dispositivi. La somma risolta e il numero di ordini validi sono colonne separate; rappresentano solo la parte nota della coda. Gli ordini non coperti restano indeterminati, senza estendere le curve oppure assegnare una risposta nulla. La coda risolta aggiunge al massimo 5.34e−10 V² full-band (TM010), meno di una parte per milione del nominale corrispondente. L'assenza di specifiche impedisce di usare questa cifra come limite superiore dell'intera coda. Il confronto principale resta un confronto condizionale a tre ordini, mentre la PSD acquisita include tutti gli alias fisici.

## Risultati assoluti sulla maschera comune

| Modo | Run 680 full-band (V²) | Ibrido full-band (V²) | Nominale full-band (V²) | Run/ibrido, banda centrale | Run/nominale, banda centrale |
| --- | ---: | ---: | ---: | ---: | ---: |
| TM010 | 1.0067e−3 | 7.0778e−4 | 7.4144e−4 | +1.482 dB | +0.829 dB |
| TM011 | 4.1324e−4 | 3.0218e−4 | 3.3385e−4 | +1.377 dB | +0.465 dB |
| TM012 | 1.8098e−4 | 1.1832e−4 | 1.3597e−4 | +1.716 dB | +0.769 dB |

Il nominale supera l'ibrido full-band di **0.202, 0.433 e 0.604 dB**. I residui run/nominale full-band sulla stessa maschera sono **+1.328, +0.926 e +1.242 dB**. La [tabella degli integrali](integrals.csv) include RMS, copertura e contributi separati. La differenza è descrittiva, con risposta nominale e piani condizionali.

La [sensibilità cavi](cable_sensitivity.csv) riscalerebbe solo l'ibrido di `10^(L/10)` in potenza se il tono avesse una perdita piatta L prima del connettore Marki. Si riportano 0, 0.5, 1, 1.5 e 2 dB, con nominale fisso. Nessun valore di L entra nella previsione principale o è ricavato da run 680. [Verifica del piano del tono in Step 9C](../step9c/README.md)

## Tono coniugato e bilanciamento

La [tabella del tono](tone_audit.csv) e il [grafico](tone_audit.png) riusano `TM010_response_audit_20261115/raw_calibration_verified.json`. Contengono 182 misure di potenza spettrale archiviata, 61/61/60 per modo, e 18 verifiche indipendenti già effettuate, sei per modo. I valori I/Q e di fase esistono solo per queste ultime. A +49.18 kHz il rapporto di potenza coniugato/principale, l'ampiezza I/Q e l'errore di fase sono:

| Modo | Run tono | Potenza coniugata/principale | Ampiezza I/Q | Errore di fase |
| --- | ---: | ---: | ---: | ---: |
| TM010 | 438 | 23.344% | 1.897 | +41.13° |
| TM011 | 499 | 0.0331% | 0.973 | −1.38° |
| TM012 | 560 | 0.0342% | 0.976 | −1.56° |

La fuga al bin coniugato del medesimo tono è evidente per TM010 a bassa IF. È un diagnostico di I/Q sotto le impostazioni della calibrazione, distinto dal rumore RF che i due mixer secondari traslano da una banda d'ingresso diversa. In particolare è visibile nel ramo senza mixer secondario. Questi prodotti non determinano una matrice complessa su tutta la banda in science. Servirebbero risposte complesse I e Q a entrambe le bande RF e relative fasi LO, con gli assetti science e calibrazione verificati e con piani d'ingresso comuni. Nessun coefficiente coniugato è inserito nei due modelli scalari.

## Riproduzione

Con NumPy, SciPy e Matplotlib, dalla radice del repository:

```bash
OPENBLAS_NUM_THREADS=1 python3 docs/step9d/build.py ../analysis-work/Run2 \
  ~/flash-data/analysis/autoreco/Run2/fft_by_run/run00680.npz
```

Lo script legge i parametri fisici di Step 6, le curve kz già archiviate, i registri v47 e i risultati Step 9A–9C. Gli unici dati scientifici utilizzati sono PSD e confronti d'archivio, come osservazioni. Non ricostruisce raw, non esegue fit o Monte Carlo.
