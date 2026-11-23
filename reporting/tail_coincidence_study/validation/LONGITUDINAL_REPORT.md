# Dataset 2 longitudinal initial checkpoint

## Coverage and I/O estimate

The Dataset 2 origin is the archived MIDAS BOR of Run 1429, 2026-11-20 17:44:07 UTC. The last reconstruction is Run 1748, ending 2026-11-21 13:05:00 UTC. The selection matches each elapsed-hour target from 0 to 19 to the nearest compatible BOR timestamp, then adds the last run and the requested 1529, 1629 and 1729 controls. The largest hourly offset is 2 min 48 s. The candidate and selection tables preserve the underlying timestamps in UTC.

A fresh listing found 314 published ROOT reconstructions and 482 raw files in the acquisition range starting at Run 1429. The saved metadata inventory validated the published products and their common ADC, channel pairing, I/Q convention and TWPA settings. Selected archive sizes still match that inventory and all selected raw gzip headers are readable. Runs 1724, 1726, 1738, 1742, 1745 and 1747 have raws but no published ROOT v3.1 in the reconstructed interval. The later raw-only range 1749–1910 is excluded. Its acquisition timestamps and full raw integrity were not verified here.

The complete selection is 24 runs. The new raw passes would consume 214,421,283,475 compressed bytes (about 61 minutes at the Run 1429 pilot rate). The initial three runs account for 27,946,454,470 compressed bytes, about eight minutes at the pilot rate, before retries and ROOT diagnostics. At about 105 MB of requested archived PSD per new run based on the prior three-run benchmark, budget another roughly 2.4 GB of logical ROOT reads across the full new selection. Physical FUSE/cache and network traffic can differ from both estimates.

## Validation method

Thresholds use the v50 binned Rayleigh maximum-likelihood fit on each run's archived amplitude histogram. The fit applied to the Run 1429 ROOT histograms reproduced all three frozen scales to relative error below 4e-13. The strict amplitude exceedance rule, seven grouping gaps, five coincidence windows, protected edges and twenty circular time shifts follow the pilot. A regression against saved Run 1429 sparse products reproduces the grouping and shifted counts. Its exact T3/T5/T7 totals are reused from the earlier diagnostics. The Run 1429 raw was not reopened.

Each completed raw run must reach gzip CRC-checked EOF and contain EOR. Every digitizer event is compared to the corresponding archived sample origin, size, serial and header time. PPS records and rejections must match the archived ROOT diagnostics. The first attempt at Run 1446 stopped on a malformed PPS record near event serial 452. The retry records defects using the same rejection criteria as the archived reconstruction and still requires uninterrupted digitizer serials. PPS interval distributions and rejected records are reported per run. Coincidence windows describe received-sample indices. UTC and channel/group delay remain uncalibrated.

The matched-Gaussian expectation uses each mode's full-run mean and 2×2 I/Q covariance, with 4096- versus 8192-angle convergence checks. These are marginal sample expectations. They carry no independent-event significance and do not control for within-run variance drift or cross-mode covariance. Archived PSD occupancies use the checkpoint's 201-bin local background and broadband normalization. Thermometers retain their timestamps and coverage flags. Across-run plots use medians and within-run ranges for temperatures. Cryogenic roles follow the archived channel mapping with physical Run3 wiring unverified. The 4 K reading describes the stage.

All selected runs share the archived TWPA pump-on configuration at 7.891 GHz and setting −6.1. Run 1670 marks an archived LO retuning. The initial batch lies entirely in the first RF-coordinate epoch. Correlations do not establish causes.

## Initial results

| Run | T7 count TM010 / TM011 / TM012 | Observed / matched Gaussian | TM012 occupancy | Pairs / triples through 10 µs | Pairs / triples at 100 µs |
|---|---:|---:|---:|---:|---:|
| 1429 (saved) | 1368 / 232 / 827 | 12.72 / 3.09 / 16.07 | 208/209 | 0 / 0 | 1 / 0 |
| 1446 | 1358 / 233 / 824 | 12.69 / 3.10 / 16.00 | 209/209 | 0 / 0 | 2 / 0 |
| 1463 | 1404 / 256 / 722 | 13.35 / 3.40 / 14.04 | 209/209 | 0 / 0 | 1 / 0 |
| 1480 | 1336 / 245 / 785 | 12.47 / 3.25 / 15.26 | 209/209 | 0 / 0 | 1 / 0 |

Every new run passed sample total, serial, CRC, EOR, per-second count/exposure, RMS and PPS-to-ROOT checks. Exact T3/T5/T7 counts and primary and sensitivity-gap groupings are in the tables.

## Measured resources

Successful streams used 27,946,454,470 compressed bytes in 456.9 s. Peak process RSS was 571.4 MiB. ROOT readers requested 317,389,462 bytes in 11.8 s.
Successful raw reads recorded 27,946,454,819 process rchar bytes and 0 kernel read_bytes. The fuse.rclone mount exposes no physical transfer counters in mountstats. The interrupted Run 1446 attempt passed event 400 at 60.8 s before the archived serial 452 PPS defect triggered the original assertion. Its partial bytes and final wall time were not instrumented, so the successful-stream figures exclude that retry overhead.

## Continuation checkpoint

Review before processing further runs. The next chronological batch is 1497 / 1513 / 1529 / 1530 (37.28 GB). This includes the 1529 control and the neighboring +6 h hourly point 1530.
