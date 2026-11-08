# Configurazioni sorgenti

Questa directory contiene scelte e parametri del software, non metadati
generati dai job. `noise_runs.txt` dichiara i run attesi della campagna noise.

Il baseline numerico misurato è esterno:

`/home/mazzitel/HFGW/analysis-work/Run2/references/noise_reference.json`

Il launcher noise passa esplicitamente quel percorso. Il baseline precedente
è stato conservato senza cambiare i valori. I test creano riferimenti sintetici
temporanei, senza dipendere dalle misure reali.

## Pilot IQ e temperature

`noise_temperature_pilot.json` fissa selezione dei run, convenzione I−iQ,
destinazione GPFS e URL/SHA-256 del contenitore scientifico di riferimento e
temperature. Il contenitore e i dati misurati restano su GPFS; Git conserva
soltanto la configurazione necessaria per recuperarli e verificarli.
