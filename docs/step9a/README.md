# Step 9A — Calibrazione RF indipendente per modo

Baseline congelata [v47.1](../v47_1/README.md), commit `1b2cb10`, e [prodotti v47](../v47/README.md). Le misure RF identificate consentono un inventario delle tracce e una verifica algebrica, ma mancano i metadati e gli output di fit necessari a una sostituzione per modo. Run 680 entra solo come confronto a valle.

## Inventario e dati mancanti

| Oggetto | Evidenza disponibile | Dato necessario |
| --- | --- | --- |
| Figure 6.3–6.4, tesi di Valeria Spasiano, p. 107 | Cap. 6 §6.1.1, configurazione dedicata senza TWPA in Fig. 6.2 e due risultati globali | Array numerici delle figure, griglia e maschera, fit per frequenza, errori, regola di aggregazione |
| Misure noise-source | Archivio montato `~/flash-data/data/LNF/calib`, 22 file `spectrumAnalyzer_*.txt` del 14, 15 e 27 luglio 2026. Le sei tracce del 27 luglio hanno 2001 punti da 8.55 a 9.05 GHz con passo 250 kHz. Grafico dei livelli originali, con orari di acquisizione | Associazione traccia–temperatura della sorgente, termometria e attenuazione al piano di riferimento, stato switch/TWPA e bias, RBW/ENBW e detector, ripetizioni o errori strumentali, script originale. Le tracce coprono i tre rami ma la loro appartenenza alle figure resta da dimostrare |
| VNA | Stesso archivio, 19 S12, 19 S21, 20 S22; nove sweep complessi del 24 luglio, un tripletto per modo, nel grafico. I timestamp delle curve identificano i file `S{12,21,22}cav_modo{1,2,3}_2026-07-24_*.txt` | Provenienza dei fit simultanei, `Abs12/21/22`, covarianza, modello e selezione delle tracce, script originale iMinuit e registro dei piani VNA. Il cap. 6 presenta un solo punto sperimentale |
| FET esterno | Ledger di normalizzazione del 16 novembre, valore nominale 36 dB, escluso dal percorso del tono kz | Sweep autonomo del secondo FET, bias, temperatura, piani, incertezze e ripetibilità |
| kz | Curve integrate per modo e fattori di conversione già registrati nella [baseline](../v47_1/dependency_registry.json) | Si riusano gli integrali approvati |

Ricerca nei sorgenti e nella storia Git locale (`git log --all -G'Abs12|67\.436' -- '*.py' '*.ipynb'`), nei prodotti `analysis-work/Run2`, nel materiale di lavoro in `/tmp` e nell'archivio LNF montato. Il codice originale del cap. 6 e i suoi output non sono stati identificati. I PNG mostrano misure strumentali, senza digitalizzazioni o fit nuovi.

## Temperatura, guadagno e piani di riferimento

La §6.1 rinvia al metodo multi-temperatura del cap. 4. A ogni frequenza si stima la temperatura equivalente del carico dalla termometria con correzione di Planck e della linea di ingresso, e si converte la potenza dello spectrum analyzer in temperatura equivalente con il prodotto di costante di Boltzmann e larghezza di banda. La regressione `Tout = G (Teff + Tn)` fornisce il guadagno lineare dalla pendenza e Tn dal rapporto intercetta/pendenza. La descrizione del cap. 4 distingue l'errore della media delle ripetizioni al singolo punto e l'incertezza sistematica della perdita di linea. Riporta inoltre RBW diverse (10 kHz nella descrizione delle acquisizioni, 500 kHz presso Eq. 4.16). È necessario il registro strumentale della specifica misura senza TWPA.

Le Eq. 6.1–6.2 riportano **3.955 ± 0.468 K** e **67.81 ± 0.39 dB** senza definire il calcolo dei due ±. La dispersione lungo la frequenza, l'errore sulla media e il contributo sistematico restano indeterminati. I parametri strumentali e le temperature d'esempio del cap. 4 non sono stati trasferiti al cap. 6. Nessuna propagazione probabilistica è giustificata per quei ±.

- **Sorgente → ingresso catena.** Nel metodo della tesi il piano equivalente di ingresso è ottenuto de-embeddando il percorso della sorgente fino al piano d'ingresso del ricevitore (cap. 4, ingresso HEMT). L'equivalenza quantitativa con il connettore di uscita cavità richiede le perdite fra i due piani e le posizioni degli switch della misura del cap. 6.
- **Cavità → L5 → uscita RF calibrata.** Nel modello VNA il piano di ingresso L5 è il porto di uscita cavità, quello di uscita è il riferimento di ricezione VNA lungo L5. L5 include la catena amplificata già percorsa dall'uscita cavità. La pendenza noise-source conta tutti gli stadi fino al piano dello spectrum analyzer. Anche Tn include, riportato all'ingresso, il rumore degli stadi attraversati nella misura. L'uguaglianza dei piani d'uscita VNA e noise-source va verificata con i cablaggi originali.
- **FET aggiuntivo → downconversion → ADC.** La §5.2.3 e l'Eq. 5.33 aggiungono un FET al guadagno del cap. 6. Il ledger di normalizzazione del 16 novembre (chiarimento di Valeria riportato dall'utente, `confirmed_calibration_ledger_20261116.json`) fissa 36 dB per questo secondo FET e lo esclude dal percorso del tono. **67.4 + 36 = 103.4 dB** è coerente con l'arrotondamento di **67.436 + 36 = 103.436 dB**. I **67.81 dB** noise-source darebbero invece **103.81 dB** se il piano d'uscita fosse compatibile. Il contributo di rumore proprio del FET aggiuntivo, riferito a monte, non è documentato separatamente.
- **kz al piano ADC.** Si usa una sola volta `0.01 kz_cal` in ampiezza, con 0.01 dal cambio LF 60→20 dB. Mixer e LPF sono già nella risposta misurata. ADC del tono a ±5 V, ADC dati a ±2 V. `fullband_v2.csv` e `campaign_band_powers.csv` sono già in V ADC fisici.

Le finestre RF nominali a prima Nyquist in [calibrations.csv](calibrations.csv) sono `LO1 + LO2 ± 2.5 MHz` sul ramo scalare, con LO1 8.735869 GHz e LO2 0/43.723/104.057 MHz. Aliasing analogico e supporto degli sweep kz restano quelli della baseline. Mancano curve Tn/G attribuibili alla configurazione per valutare variazioni anche solo entro queste finestre. Nel CSV le colonne `mode_*` vuote denotano misure mancanti; i valori `thesis_global_*` sono comuni e i ± sono trascritti, con definizione statistica ignota. Il nominale FET proviene dal ledger, il guadagno RF e Tn di baseline dal registro v47.1.

## Segno di L5

La descrizione dei percorsi prima dell'Eq. 6.3 assegna S21 a L3→L5, S22 a L1→L5 e S12 a L1→L3. L'ultima riga dell'Eq. 6.3 nella trascrizione della tesi ripete L1; la descrizione di S12 e quella di Abs12 all'Eq. 6.8 indicano invece L1 e L3. Definendo D come misura meno cavità, la somma delle prime due equazioni meno la terza elimina entrambe le linee di ingresso.

```text
GL5 = (D21 + D22 − D12)/2
GL5 = 10 log10(Abs21 Abs22 / Abs12)
```

Le Eq. 6.12 e 6.13 stampano un più. Un più sarebbe equivalente con D12 definito come cavità meno misura, oppure con Abs12 fattore inverso di correzione; la differenza esplicita in 6.12 e il prefattore moltiplicativo in 6.8 sostengono il segno meno. Con le definizioni scritte, la formula con il più restituisce GL5 + D12. L'incongruenza nel testo è verificabile; resta indeterminato se il risultato numerico provenga da un refuso o dall'applicazione del più nel codice. Nessun valore pubblicato è stato corretto. Con la covarianza dei D ordinati (21,22,12), la varianza di L5 sarebbe `wᵀ Cov(D) w`, con `w=(1,1,−1)/2`. Per gli Abs occorre prima applicare il Jacobiano della trasformazione logaritmica.

I valori pubblicati **67.03 ± 0.15 stat dB** (6.14) e **67.436 ± 0.004 stat dB** (6.15) distano rispettivamente **0.780** e **0.374 dB** dai 67.81 dB. Solo il secondo scarto nominale rientra nei 0.5 dB citati nel testo. Senza covarianza, incertezze di piano e definizione del ± noise-source, il confronto resta descrittivo e non attribuibile ai tre modi.

## Effetto analitico sull'ADC

L'integrando elettronico bilatero per ciascun alias analogico è `50 kB Tn(f_RF) 10^(G_RF(f_RF)/10) |0.01 kz_cal(f_IF)|²`. Si sommano gli alias nel piano digitale e si integra con peso unitario full-band oppure con il modulo quadrato del FIR di banda. Per la cavità si sostituisce `kB Tn` con lo spettro termico lorentziano approvato, nel suo piano di uscita. Tn agisce solo sul termine elettronico. Una variazione del guadagno a monte della downconversion scala entrambi i termini.

[comparison.csv](comparison.csv) contiene 24 righe. Riusa gli integrali full-band analitici Part I v43 e i sette integrali separati dall'archivio v47 `diagnostics/resonance_campaign_primary_v47_20261117/expectations_and_campaign.h5`, con centri BOR di run 680 e FIR Kaiser 8.6 da 2001 tap (larghezza nominale 50 kHz, ENBW 47.429 kHz). I centri esatti sono riportati nel CSV. I dati full-band sono i momenti AC v2 di run 680; le sette bande sono integrali dei PSD v47 con sottrazione della media per chunk. Il riferimento analitico ha il polo della cavità alla IF fisica; il toy full-run congelato colloca il polo a 1 MHz. Il rapporto archiviato run/MC full-band v47.1 è 1.187/1.514/1.634 in RMS; i rapporti qui sono in potenza e usano l'integrale analitico. La diversa posizione del polo influenza la piccola colonna termica.

La colonna indipendente per modo resta vuota. Come controllo di sensibilità globale, a Tn invariata e **solo se** il guadagno noise-source termina a monte dello stesso FET aggiuntivo, 103.81 dB moltiplica ogni integrale per **1.0990** (+9.90% in V², +4.83% in RMS). Questo confronto usa soltanto due numeri pubblicati e il nominale del FET. La potenza full-band run/modello passa da **1.409/2.293/2.669** a **1.282/2.087/2.429**, rispettivamente per TM010/011/012. La sensibilità comune lascia invariati i rapporti fra modi e fra bande del modello.

## Riproduzione

Dalla radice del repository, con NumPy, h5py e Matplotlib installati:

```bash
python3 docs/step9a/build.py ../analysis-work/Run2 ~/flash-data/data/LNF/calib
```

Lo script legge i prodotti congelati e le esportazioni strumentali indicate. Scrive la tabella del confronto e i due grafici nella directory dello studio.
