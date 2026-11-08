# Pilot IQ filtrato e temperature, run 680–939

La campagna ricostruisce integralmente 12 run distribuiti nell'intervallo:
680, 704, 727, 751, 774, 798, 821, 845, 868, 892, 915, 939.
Usa `analyze_midas_iq_noise.py --iq-sign -1 --filtered-bands --h5-only`,
con lo stesso riferimento di ampiezza per tutti i run. Il segno corrisponde
a **I−iQ** ed è anche il default dei due analizzatori.

Ogni HDF5 contiene statistiche ordinarie, figure PNG incorporate e verifiche
di ampiezza/fase nelle nove bande da 50 kHz per ciascun modo TM010/011/012:
0, ±100, ±250, ±500 e ±1000 kHz. FIR e oscillatore sono continui tra SPEC;
la decimazione è 20 e il FIR ha 2001 coefficienti. Non si sottrae il DC.

## Esecuzione

La campagna attuale ha `submissions_paused=true` nel manifest, per istruzione
dell'utente. Il controller rifiuta `--submit` finché questa sospensione resta attiva.
I comandi seguenti descrivono la procedura generale per una campagna autorizzata.
Prima di sottomettere verificare i worker con `condor_status`: `condor_q` mostra i job.

```bash
python3 examples/noise_temperature_pilot.py prepare
python3 examples/noise_temperature_pilot.py watch --submit
```

`watch` va eseguito in un processo persistente. Limita la concorrenza a quattro
job HTCondor, ciascuno con 1 CPU, 4 GB RAM e 60 GB scratch. Scarica l'input
in scratch tramite le credenziali HTCondor e recupera i risultati mediante spool.
Non modifica input o prodotti GPFS. Non sottomette altri run quando un job fallisce.
Il monitor riparte dagli stati esistenti e impedisce due istanze simultanee.

Sorgenti, riferimento comune e CSV/schema delle temperature vengono copiati
all'atto di `prepare`; il manifest ne conserva gli SHA-256. `prepare` ripetuto
riusa la campagna esistente. Per una diversa configurazione usare una nuova
directory `--campaign` e un nuovo `--output`.

```bash
python3 examples/noise_temperature_pilot.py status
python3 examples/noise_temperature_pilot.py watch --once
python3 examples/noise_temperature_pilot.py report
```

Il secondo comando recupera lo stato corrente senza nuove sottomissioni;
il terzo richiede tutti i risultati completi. Log e stati sono in:

`/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/noise_temperature_pilot_minus1_20261108/`

HDF5 recuperati e confronto finale sono in:

`/home/mazzitel/HFGW/analysis-work/Run2/reports/noise_temperature_pilot_minus1_20261108/`

## Confronto termico

Il report viene prodotto automaticamente al completamento dei 12 run. Usa i
canali AVS 15 (cavità), 16 (CMN143 mixing chamber) e 17 (CMN130 mixing chamber),
con disposizione e unità mK verificate nello schema dell'estrazione.
Per ogni banda si associano soltanto letture finite dello stesso run comprese
tra il primo e l'ultimo timestamp SPEC, senza interpolare o estrapolare.
Si conservano mediana, minimo, massimo e numero delle osservazioni.

File generati:

- `bands_temperature_by_run.csv`: RMS ponderato sui campioni, ampiezza media,
  concentrazione di fase, incrementi e temperature per run/modo/banda;
- `temperature_correlations.csv`: coefficienti di Pearson e Spearman per
  RMS, ampiezza e concentrazione di fase, insieme alle correlazioni col tempo;
- `central_rms_vs_temperature.png`: confronti della banda centrale con i tre sensori;
- `band_rms_by_run.png`: andamento dei livelli delle nove bande;
- `comparison_summary.json`: copertura e limiti di interpretazione.

L'RMS aggregato è `sqrt(sum(n * rms**2) / sum(n))`. Le concentrazioni di fase
si combinano come vettori complessi e non come medie degli angoli.
I coefficienti sono descrittivi: dodici run, dipendenza temporale e confronti
multipli non giustificano una conclusione causale. Non si calcolano p-value
assumendo indipendenza dei campioni filtrati. La banda centrale include offset DC.
