# Confronto preliminare delle bande IQ

`examples/survey_iq_sidebands.py` confronta potenza media in bande fisse,
centrate allo zero baseband e a offset simmetrici. Non identifica lo zero
con la frequenza di risonanza e non esegue fit di risonanza.

```bash
python examples/survey_iq_sidebands.py \
  --input /home/mazzitel/flash-data/analysis/autoreco/Run2/fft_by_run \
  --runs config/noise_runs.txt --output /tmp/iq_sidebands_680_939
```

Produce CSV, riepilogo JSON e grafico. Default: bande larghe 50 kHz,
offset ±100, ±250, ±500 e ±1000 kHz, esclusione |f| ≤ 1 kHz.
L'asse usa `fs` e la lunghezza reale dell'array: il codice storico
trasformava blocchi lunghi nstep-1, salvando metadati per nstep.
Le ampiezze visualizzate sono sqrt(potenza media di banda), normalizzate
alla propria mediana di campagna; non sono RMS integrati calibrati.

Prima esecuzione: 260/260 run disponibili, 680–939, tutti e tre i modi.
Le ali mostrano una deriva comune di circa 3% in ampiezza equivalente.
L'asimmetria (R-L)/(R+L) non mostra una deriva altrettanto evidente;
TM010 presenta anche inversioni isolate da esaminare nei dati originali.
Il rapporto ali/centro cambia leggermente, soprattutto in TM010:
non basta quindi assumere una riscalatura perfettamente uniforme.
Questi risultati non misurano uno spostamento della risonanza e non
escludono un suo contributo. La risposta strumentale non è separata.

Restano da fare: asse temporale con timestamp di acquisizione, finestre
intra-run, definizione del centro fisico dei modi e analisi IQ filtrata
per fase/correlazione. I prodotti FFT attuali contengono solo potenza:
non consentono di ricostruire la fase complessa. Una fase di rumore
non equivale alla fase della risposta a un'eccitazione coerente.
La correlazione termica va eseguita dopo aver definito queste osservabili.

Verifica sintetica: `python examples/tests/test_iq_sidebands.py` controlla
che un guadagno comune conservi asimmetria e rapporto ali/centro, che una
traslazione di un profilo simmetrico produca asimmetria e che le bande
fuori copertura siano rifiutate.

## IQ filtrati

L'utente ha specificato la fase degli IQ filtrati in bande simmetriche.
`analyze_iq_filtered_bands.py` demodula ogni banda e applica lo stesso FIR
Kaiser da 2001 coefficienti, larghezza nominale 50 kHz, decimazione 20.
Stato FIR e oscillatore sono continui tra SPEC. Si scarta il transitorio
iniziale e si corregge il tempo acquisito per il ritardo di gruppo.
Le statistiche per SPEC comprendono ampiezza media, RMS, media circolare
e risultante della fase, media circolare e risultante degli incrementi
al ritardo di 4 microsecondi, con conteggi di campioni e coppie.
La fase è riferita all'oscillatore di ciascuna banda, non a un'eccitazione.
La banda centrale include eventuali offset DC; non è equivalente alla
banda centrale con esclusione DC dello screening FFT precedente.

```bash
python examples/run_iq_filtered_campaign.py \
  --runs config/noise_runs.txt \
  --input /home/mazzitel/flash-data/data/LNF \
  --output /tmp/iq_filtered_campaign_680_939
```

Il runner conserva una copia dello script, elabora un run per volta,
usa directory `.pending` e promuove i risultati solo a EOF raggiunto.
Una nuova invocazione riprende saltando i run completi; una versione
sorgente diversa richiede una directory nuova. Il file `COMPLETE.json`
compare solo alla conclusione della selezione intera. I log separati
per run consentono di distinguere un processo attivo da un errore.
La prima campagna separata dell'8 novembre 2026 usava I+iQ ed è stata fermata.
I suoi risultati temporanei sono conservati; per le nuove ricostruzioni si usa
I−iQ (`--iq-sign -1`), ora default degli analizzatori. Il pilot distribuito su
12 run usa l'analisi integrata in `analyze_midas_iq_noise.py --filtered-bands --h5-only`.
La procedura Slurm è descritta in [examples/hpc/README.md](../examples/hpc/README.md).

`python examples/tests/test_iq_filtered_bands.py` verifica equivalenza
tra stream spezzato e blocco unico, trasmissione/reiezione dei toni
e incremento di fase noto dopo demodulazione.

## Implementazione ottimizzata dei filtri v1

Il filtro fisico resta lo stesso: coefficienti FIR, demodulazione, transitorio,
griglia di decimazione e stato tra SPEC non cambiano. `FilterWorkspace` conserva
al massimo due FFT del kernel e un oscillatore/griglia alla volta; bande con lo
stesso centro vengono elaborate insieme nei tre modi. In questo modo la FFT
del FIR e l'esponenziale complesso non vengono ricalcolati per ogni modo.
Il tag scientifico resta `v1`; `filtered_bands/config/implementation` identifica
il kernel `shared-oscillator-cached-fir-fft-v1` per la riproducibilità.

I test confrontano il risultato con un FIR causale indipendente (`lfilter`),
includendo blocchi di dimensioni irregolari, bordi del transitorio, banda DC,
offset negativi e condivisione del workspace tra modi e kernel diversi.
