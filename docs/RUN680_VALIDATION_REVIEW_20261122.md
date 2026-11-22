# Run 680 — review documentale dei rapporti ROOT v3.1

**Data:** 2026-11-22  
**Fonte:** trascrizione di `validation_report.md` e `validation.json` fornita dall'utente, originariamente pubblicati in `davs://xfer-archive.cr.cnaf.infn.it:8443/flash/analysis/autoreco/Run2-references/root-v3.1/`.  
**Livelli di evidenza:** (a) affermazioni dei rapporti Codex; (b) verifiche indipendenti *aritmetiche* eseguite sui valori trascritti. **Nessun accesso diretto al ROOT, raw MIDAS o WebDAV dal revisore.**

## Identità e provenienza — riportate dai documenti

- ROOT: `run00680_iq_v3.1.root`, 155913555 byte, SHA-256 `498116d3dd22e4d9bb5bb23d5416ff3f75606652da082c0cae7ecdec913ddc89`, Adler-32 `326612db`.
- Raw: `/home/mazzitel/flash-data/data/LNF/run00680.mid.gz`, 12130819273 byte, SHA-256 `e18268a6f04b1dca2f1039718bc04ec8d46bf6234702367f4a0f9cae7c509ee8`.
- Software: commit `3fb591aa5da378cc3c4aa1170837b8362e85b03a`; worktree `/home/mazzitel/HFGW/worktrees/run680-root31-reference`, branch `run680-root31-reference-20261122`.
- Esecuzione: `isolated UI scratch`, wall **326.835832725 s**, CPU **373.698530115 s**, Max RSS **739672 KiB**; HTCondor `4820.0` non partito (0 starts), poi rimosso.
- Pubblicazione dichiarata: `rclone WebDAV`, copia su nome temporaneo univoco, rename immutabile e verifica mediante download/confronto byte; **questi passaggi non sono stati ripetuti dal revisore**.
- Scratch intermedio HDF5: 189791706 byte, SHA-256 `180e07baa4ada7d1ee6d7f73de0b98cb2ad9e6a09e10ae6a93ff49f3f49ea1d8`; non confonderlo con il prodotto finale.
- ODB: BOR 1066122 byte SHA-256 `a5b659067c0c8e23be2716081fc8a9f15b1f12438e07661772886b66d5d54a55`; EOR 1065617 byte SHA-256 `ce099631702a46cd01532bda54392685e04cae217192944a632c51f68e0f7302`.
- Isolamento Run3 dichiarato nei safeguards JSON; non verificato indipendentemente nel filesystem/cron.

## Mapping e quantità — dai rapporti

- MIDAS storico `SPEC`, 8 canali `int16`; TM010 0/1, TM011 2/3, TM012 4/5, PPS su canale SPEC 6; la mappa è **specifica del formato storico**, non quella degli altri run.
- BOR ADC ±2 V, `4/65535 V/count = 6.103608758678569e-05 V/count`, `z = I - iQhardware`.
- Campioni per modo 1048576000; 209 finestre complete da 5000000, residuo 3576000; 64000 short FFT da 16384, residuo zero; PPS 210 con intervalli di 5000000.
- MIDAS: 1000 eventi di acquisizione, 1251 eventi totali, 1249 bank, auxiliary payload 19808 byte, 36 misure termometriche, EOR presente, 0 breaks.
- ROOT schema 3.1, roundtrip 67/67 e 67 dataset tipizzati leggibili.
- Massimo errore relativo Parseval per finestre da 1 s: **1.271317063e-07** (TM011). Short FFT: **7.177749370e-08** (rettangolare TM010), con Hann/rectangular riportati separatamente.

## Confronto storico v50 — dai rapporti

| Modo | RMS v3.1 mV | PSD mascherata v3.1 mV | PSD v50 mV | Differenza relativa |
|---|---:|---:|---:|---:|
| TM010 | 32.262765 | 31.728019 | 31.728096 | -2.419562832e-06 |
| TM011 | 20.783883 | 20.328180 | 20.328172 | +3.457861557e-07 |
| TM012 | 13.733291 | 13.452812 | 13.452821 | -6.786324903e-07 |

- Riferimento v50: **4000 blocchi non sovrapposti × 262144** campioni, maschera `|IF| >= 100 kHz`, **251659/262144** bin.
- Prodotto v3.1: **209 finestre** da 5000000 campioni (griglia e popolazioni diverse); il PSD mascherato è un confronto diagnostico, non l'RMS full-band.
- Medie I/Q, RMS totale e AC, media/deviazione di `|z|` entro ~1e-9 relativo rispetto al riferimento storico dopo fattore di scala **2/5** e inversione di segno Q. Per la media I di TM012 il JSON riporta `-3.220932976e-08` relativo: meno piccolo delle altre differenze ma compatibile con una media quasi nulla.
- Momenti 3 e 4 disponibili nel ROOT v3.1 ma non in forma scalare lossless nel riferimento v50; fase, incrementi di fase e ACF lineare rimangono diagnostiche v50 separate, non ricostruibili dal solo ROOT v3.1.

## Normalizzazioni dichiarate

- FFT 1 s: `bilateral rectangular PSD, FFT/N; integral includes DC`; **la formula testuale non definisce da sola ogni fattore di conversione in V²/Hz**: per completa riproducibilità conservare codice e configurazioni riferiti dal commit.
- Short FFT: `mean(|FFT(w*(z-mean(z)))|² / (fs * sum(w²)))`, **two-sided**; trattamento della DC differente (rimozione della media nello short).
- Massimo errore relativo di aggregazione riportato: **3.415283965e-10**.

## Controlli aritmetici indipendenti sui dati trascritti

1. `209*5000000 + 3576000 = 1048576000` (**OK**).
2. `64000*16384 = 1048576000` (**OK**).
3. `4000*262144 = 1048576000` (**OK**).
4. 210 PPS implicano 209 distanze consecutive; un intervallo costante di 5000000 è coerente con 209 s complete (**OK** come coerenza, non verifica della traccia PPS).
5. Controllate in modo indipendente sui numeri JSON le identità `ac_rms² = var_I + var_Q` (precisione floating-point) e `rms² = var_I + var_Q + mean_I² + mean_Q²` (scostamento relativo fino a circa **1.5e-9**, attribuibile alla precisione delle statistiche archiviate; non equivale a leggere il raw).
6. Gli scostamenti PSD stampati sono inferiori a 2.5 ppm in modulo (**OK**).

## Conclusione e limiti

**Revisione documentale superata:** i documenti sono tra loro coerenti e descrivono un prodotto ROOT v3.1 riproducibile con identificatori, convenzioni, conteggi, normalizzazioni e confronti v50 adeguatamente documentati.

**Non certificati dal revisore:** effettiva raggiungibilità WebDAV, contenuto e checksum dei file remoti, conteggi riletti dal raw, dati ROOT 67/67, integrità del checkout e produzione Run3. Queste verifiche richiederebbero accesso ai file/ambiente e non sono necessarie per avviare una discussione progettuale separata sull'autoreco leggero.

**Prossimo passo facoltativo:** controllo remoto *read-only* di dimensione e SHA-256 del ROOT, senza rielaborare run 680. **Nessun job richiesto.**
