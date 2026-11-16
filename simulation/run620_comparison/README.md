# Thesis → run620 → run680

`thesis_model.py` generates a distinct toy with30mK,103.4dB, measured integrated-tone response, receiver3.955K and actual±5V digitization, including clipping. No36dB subtraction. These assumptions do not constitute independent validation of the analog gain. It predicts about1.9% complex samples clipped for TM010.

`analyze.py` runs the same frozen v2 pipeline with one worker on the first20SPEC events of620 and680. Both original BOR ODBs show±2V on IQ channels and5MS/s. Frozen pipeline uses historical±5V voltage units; plotted ADC voltages are multiplied by0.4 (squared quantities by0.16). This is an exploratory matched sample; full-run620 production is not included. HDF5 retains filters, phase, IQ, DC and event metadata. No GPFS publication.

Outputs: analysis-work/Run2/simulation/run620_comparison. Deck generator: reporting/iq_noise_summary_v27/build_slides.py. Both scripts require the established external scientific inputs and frozen-source snapshot, not distributed through Git.
