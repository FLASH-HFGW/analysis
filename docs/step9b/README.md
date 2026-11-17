# Step 9B — Funzione di trasferimento nominale della downconversion

Studio indipendente da v47.1 e dai risultati di calibrazione di Step 9A. Il piano di ingresso è il connettore RF del Marki. Il piano di uscita è il carico nominale 50 Ω a valle del BLP, al connettore ADC nell'ipotesi di terminazione adattata. Il bilancio è lineare, a piccolo segnale e condizionato alle configurazioni sotto. L5, FET, risposta del front-end ADC, quantizzazione, alias del campionamento e rumori additivi sono fuori da questo trasferimento analogico. Le sorgenti numeriche sono specifiche del costruttore e metadati di configurazione.

## Dati e dominio di validità

Le tabelle effettivamente utilizzate sono in [manufacturer.json](manufacturer.json). L'interpolazione è lineare in dB e frequenza per i dati Mini-Circuits, lineare in dB e log-frequenza per FEMTO. Celle vuote indicano punti senza stima numerica. I dati tipici e le interpolazioni tra punti sparsi non definiscono tolleranze di produzione. [Inventario e originali archiviati](../hardware/README.md)

| Parte | Modulo e condizioni nominali | Fase e ritardo |
| --- | --- | --- |
| Marki MMIQ-0520H | Conversion loss 12 dB tipica, 15 dB max per singola uscita con l'altra terminata, RF e LO 5–20 GHz, IF fino a 200 MHz, LO +19 dBm nominale. Si usa il valore tabulato nella banda. I grafici di sweep RF con IF fissa a 91 MHz non costituiscono una mappa al LO fisso dei run. | Balance tipico 0.4 dB e 2°, IR 35 dBc con combiner nelle condizioni Marki. Fase di conversione per porta non nota. |
| FEMTO DHPVA-101 | Guadagno in tensione 20 o 60 dB, accuratezza nominale ±0.15 dB a 50 Ω. Risposta tipica digitalizzata dal grafico di p. 4 per l'assetto a 100 MHz, incluso il tratto misurato appena oltre 100 MHz. Modalità 10 MHz e accoppiamento sono sconosciuti per entrambe le sessioni. | Nessun dato di fase usato. Il riferimento a una forma approssimativamente Bessel non specifica un filtro completo. |
| ZSC-4-1+ | Interpolazione delle quattro perdite totali S→uscita, già comprensive della divisione. Media in dB come valore nominale dato il cablaggio ignoto, min/max fra le uscite riportati separatamente. 0.1–200 MHz, 50 Ω. | Sbilanciamento relativo di fase riportato nella tabella. Fase assoluta e ritardo non determinati. |
| SIF-40+ | Passband specificata 35–49 MHz, tabella di perdita 1–400 MHz. La stima fuori passband è una semplice interpolazione, particolarmente debole quando i punti sono distanti. | Ritardo di gruppo tipico tabulato. |
| SBP-101+ | Passband specificata 94–108 MHz, tabella 1–3300 MHz; entro passband i punti di modulo sono a 94, 101, 108 MHz. | Ritardo di gruppo tipico tabulato. |
| ZAD-1-1+ | Si usa la perdita tipica midband di 4.83 dB (+7 dBm LO), limite midband 7.5 dB. RF/LO ammessi 0.1–500 MHz, IF DC–500 MHz. La tabella di sweep usa IF = 30 MHz e frequenze RF e LO entrambe variabili, quindi è riportata come diagnostica e non applicata come misura della risposta a LO fisso e IF 0–2.5 MHz. | Fase e asimmetria di conversione tra bande laterali non disponibili. Il modello assegna la stessa perdita tipica scalare a entrambe. |
| BLP-1.9+ | Passband specificata DC–1.9 MHz con perdita <1 dB. La tabella tipica parte a 0.10 MHz e dà **8.32 dB a 2.5 MHz**, mentre la specifica riporta **3 dB nominali** lì. L'inviluppo numerico segue la tabella, senza colmare DC–0.10 MHz o imporre un cutoff ideale. | Ritardo tabulato, con alcune frequenze ripetute alla precisione stampata. Si mostrano i punti originali senza scegliere un ordinamento sub-bin artificiale. |

FEMTO, digitalizzazione riproducibile a 120 dpi con `pdftoppm -f 4 -l 4 -r 120 -png docs/hardware/de-dhpva-101.pdf femto`. Le coordinate orizzontali selezionate sono in `sample_x_px`. La scala è `f[MHz] = 10^((x−413)/76−3)`. Per ciascun x si legge la riga del tratto rosso/arancio più saturo nella finestra da −2 a +18 px rispetto alla riga di plateau (844 a 20 dB, 756 a 60 dB), usando `R−B` con `R>G+10` e `R−B>14`. La scala verticale è 120 dB/264 px. La risoluzione è circa 0.45 dB per pixel; spessore, antialias e griglia introducono ulteriore incertezza di lettura. I due tratti provengono dal grafico tipico e sono ancorati ai guadagni nominali. Le cifre di calcolo nel CSV non rappresentano l'accuratezza del dispositivo.

Non erano presenti Touchstone negli originali locali. I cataloghi Mini-Circuits indicano materiale S-parameters per alcuni modelli, ma le pagine dirette e i tentativi di download dal dominio del costruttore hanno restituito HTTP 403 nell'ambiente. Nessun file Touchstone originale è stato verificato o incorporato. Gli S-parametri lineari dei mixer, se recuperati, richiederebbero comunque una misura di conversione pompata per fissare la risposta fra frequenze diverse. [Catalogo SIF](https://www.minicircuits.com/WebStore/dashboard.html?model=SIF-40%2B), [catalogo SBP](https://www.minicircuits.com/WebStore/dashboard.html?model=SBP-101%2B), [catalogo splitter](https://www.minicircuits.com/WebStore/dashboard.html?model=ZSC-4-1%2B)

Il ritardo di gruppo è `−(1/2π) dφ/df`. Si conservano le misure dei tre filtri separatamente in [group_delay.png](group_delay.png); anche una loro integrazione fisserebbe la fase relativa soltanto entro il supporto e a meno di una costante. Le altre fasi, i ritardi di cablaggio e le fasi dei LO impediscono di assegnare un ritardo o una risposta complessa all'intera catena.

## Configurazioni e percorsi

Le frequenze provengono dai BOR ODB già estratti nell'audit di normalizzazione (`run500_calibration_odb_fields.json`, `run680_calibration_odb_fields.json`) e dal registro `frequency_coordinates_audit_20261117/calibration_comparison.json`. Guadagni FEMTO dalla comunicazione dell'operatore riportata nel README hardware. I +19 dBm primari e i livelli secondari sono setpoint, con potenza consegnata ai mixer non verificata.

| Assetto | LO1 (MHz) | LO2 TM010/011/012 (MHz) | IF primaria alle frequenze fisiche della Tab. 6.1 (MHz) | IF finale (MHz) | FEMTO |
| --- | ---: | --- | --- | --- | ---: |
| Calibrazione tono | 8734.910 | bypass / 44.160 / 104.390 | 2.209 / 45.930 / 106.272 | 2.209 / 1.770 / 1.882 | 60 dB |
| Run 680 | 8735.869 | bypass / 43.723 / 104.057 | 1.250 / 44.971 / 105.313 | 1.250 / 1.248 / 1.256 | 20 dB |

Le frequenze RF fisiche di valutazione sono 8737.119, 8780.840, 8841.182 MHz. Si usano le differenze fra frequenze sintetizzate, senza il piccolo scarto della pendenza osservata nell'audit del tono. Al variare di f finale si valutano Marki a RF = LO1 + u e IF = |u|, FEMTO/splitter/BPF a |u|, ZAD con RF d'ingresso |u|, LO = LO2, IF = |f|, e BLP a |f|. Per il percorso principale `u=f+LO2`; nel bypass `u=f`. Il valore tipico a 100 MHz FEMTO comporta circa 3.1–3.2 dB di calo in TM012 alle frequenze della tabella. Se era selezionato 10 MHz, le due IF superiori superano il cutoff nominale e il foglio non fornisce la risposta utilizzabile in quella condizione. Il modello a 100 MHz è quindi uno scenario esplicito, privo di una banda d'incertezza per lo switch. Per AC/DC il costruttore dà un bordo inferiore commutabile DC/10 Hz. In TM010 la finestra sotto 100 kHz è priva di risposta numerica dello splitter in entrambi i casi; per gli altri modi l'IF primaria attraversa il FEMTO a decine di MHz anche a f finale zero.

Per la **mappa funzionale** si assegnano SIF a TM011 e SBP a TM012 su I e Q, coerentemente con passband e IF. Nello [schema originale, slide 2](../hardware/QUAX_multimode_v2.pptx) l'I è etichettata al contrario. La [tabella del bilancio](gain_budget.csv) e il grafico includono anche la lettura letterale delle etichette, con Q invariata. Alle risonanze di run 680, la perdita BPF prevista in I passa da 0.34 a circa 69 dB per TM011 e da 1.92 a circa 7.9 dB per TM012 usando le tabelle tipiche interpolate. Le cifre in stopband sono indicative. Il confronto verifica la coerenza funzionale delle etichette e lascia aperto il cablaggio installato.

## Guadagno assoluto e immagini

Con tutti i piani adattati a 50 Ω, un guadagno dB per quadratura rappresenta sia `20 log10(Vq_rms/VRF_rms)` sia `10 log10(Pq/PRF)`. Si sommano il guadagno FEMTO e le perdite con segno. Ciascuna conversion loss è definita fra potenza del tono d'ingresso e potenza dell'unico prodotto di conversione misurato alla porta considerata. Nessun ulteriore fattore 1/2 per mixer entra nel bilancio. I valori ADC ±5/±2 V riguardano headroom e codici e non cambiano il guadagno analogico in volt.

Per `z=I−iQ`, il rapporto RMS della norma è `sqrt(GI+GQ)` e la potenza equivalente riferita a 50 Ω è `GI+GQ`, dove GI e GQ sono i singoli guadagni di potenza lineari. Per la mappa funzionale nominale bilanciata ciò equivale a +3.0103 dB. Per lo schema letterale le due potenze possono ancora essere sommate ma la loro somma non specifica l'ampiezza traslata in un singolo bin di z. Il valore di sommatoria può essere letto come guadagno del tono complesso desiderato soltanto con quadratura ideale e LO secondario comune in fase. La definizione RMS è per un tono a IF non nulla, senza inferire l'uscita DC dipendente dalla fase.

| Modo | Calib. dB / quadratura | Calib. dB / z ideale | Run 680 dB / quadratura | Run 680 dB / z ideale |
| --- | ---: | ---: | ---: | ---: |
| TM010 | 39.86 | 42.87 | 1.55 | 4.56 |
| TM011 | 35.38 | 38.39 | −4.33 | −1.32 |
| TM012 | 31.24 | 34.25 | −8.46 | −5.45 |

Nei due rami con ZAD, ciascun mixer reale produce la differenza da entrambe le bande intorno a LO2. Per I o Q reale, a frequenza |f|, le due IF positive candidate sono LO2+|f| e LO2−|f|. In z con LO secondari in fase e I/Q ideali, la traslazione a f riceve due contributi distinti dal primario firmato `u=f+LO2` e `u=f−LO2`. Il secondo è l'immagine RF attorno a **LO1−LO2**, valutata alle stesse frequenze finali e indicata come `secondary_image`. Il suo modulo nominale può essere comparabile al percorso principale perché il BPF reale passa moduli di frequenza simili. L'altra IF positiva LO2−f mappa a −f in z ideale. Errori di fase/gain possono trasferirne il coniugato nello stesso bin di f. Anche il Marki ha reiezione immagine finita, compreso il ramo di bypass. Questi contributi non si possono sommare come fasori senza le loro fasi e senza conoscere i segnali entranti.

Un modello coerente deve propagare le due componenti I/Q, o equivalentemente `[Z(f), Z*(-f)]`, con matrici di conversione per le due frequenze primarie e le fasi dei due LO secondari. Le curve qui sono moduli per tono separato; la perdita tipica ZAD comune e il BPF nominale non forniscono reiezione immagine misurata, né coefficienti complessi univoci. I valori tipici di bilanciamento del solo Marki non fissano questo modello matriciale.

## Prodotti e riproduzione

- [components.png](components.png) e [group_delay.png](group_delay.png) mostrano i contributi dei costruttori. [end_to_end.png](end_to_end.png) usa dB assoluti per quadratura e mostra le regioni mancanti come interruzioni.
- [response.csv](response.csv) copre −2.5…+2.5 MHz a passo 5 kHz per i due assetti e per ciascuna banda di ingresso prevista. [gain_budget.csv](gain_budget.csv) riporta la stessa scomposizione alle IF fisiche, inclusi rapporti lineari di tensione e potenza e lo scenario alternativo per I.
- `build.py` legge solo `manufacturer.json`. Dalla radice del repository, con NumPy e Matplotlib, eseguire `python3 docs/step9b/build.py`. I risultati sono separati dalla calibrazione di tono e pronti per la revisione nominale prima di Step 9C.
