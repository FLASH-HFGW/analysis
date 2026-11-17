# v43 — Part I only

14 English slides: active-source table; documented hardware chain; absolute normalization before the steps; cavity/readout transfer explanation; steps 1–5; step 5 covariance and analog-residual diagnostic; step 6 on three separate mode pages; reference correlations and amplitude CCDF in separate mode panels.

The repeated six panels are sampled I/Q, IQ constellation, amplitude, phase, PSD and complex autocorrelation. Main physical axes remain common. Thermal/weak-source insets explicitly label their physical units. ADC markers use filled I circles and hollow Qeff squares at 200 ns spacing. Autocorrelation markers also occur at every 200 ns. Stages 3, 5 and each stage-6 mode retain the common full correlation scale and add a separate positive-lag zoom; both Re and Im are shown and checked for clipping. Step 5 also shows the separate analog source correlations, power-weighted sum and exact analog residual.

The source palette remains cavity/injected noise blue, receiver orange, total purple and analytic/probe navy. The documented mode palette is TM010 teal, TM011 purple, TM012 orange; mode pages and reference small multiples use these colors without overplotting the modes. The source-contribution curves retain their source colors.

Stage definitions, normalization equations, assumptions, numerical checks and reproduction commands: [simulation README](../../simulation/presentation_steps1_6_v43/README.md).

The build only postprocesses saved short arrays. No new stochastic simulation, fit, full-run processing, experimental analysis, or stage 7/8 response is included. Previous versions remain intact. The hardware diagram is copied from v42, whose reference inventory remains unchanged. The absolute-normalization title is “Absolute normalization — From physical noise to ADC voltage”; no fit-related slogans appear in slide titles.

Generated outputs: `../analysis-work/Run2/reports/iq_noise_summary_v43_partI/`, including PDF, editable PPTX, previews, slide model and validation report. Source hashes and array-equality checks distinguish the deliberate new step-3 selection from the preserved reference realizations. No generated numerical products are versioned.
