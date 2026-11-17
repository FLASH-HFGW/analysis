# Statistical definitions and numerical exceptions

Use z = I − i Q_hardware throughout. Keep three different observables separate:

- A_raw = |z|.
- A_AC = |z − mean(z)|.
- A_centered = |z| − mean(|z|).

The stored `modes/*/noise_counts` describe the third quantity. They are not a histogram of A_AC. Standard v2 stores AC moments but not a full empirical A_AC histogram.

DC² = |mean(z)|²; AC² = mean(|z − mean(z)|²); total RMS² = DC² + AC². Rayleigh sigma is a quadrature scale, not mean amplitude or the standard deviation of amplitude. Empirical amplitude moments and CV are extracted independently from the global amplitude summary.

Historical v2 voltage coordinates were reconstructed using ±5 V, whereas scientific BORs confirm ±2 V. Apply voltage factor 0.4 and mean-square factor 0.16 exactly once. Corrected diagnostic products already in physical ADC units are not scaled again. No new 143 dB nominal input-referred values are produced.

The high-resolution IQ grid and fitted-Rayleigh-threshold counts use existing dedicated empirical diagnostics because the standard v2 grid and stored thresholds differ. Their counts are not derived from a PSD or fitted probability density. These exceptions retain full-run populations and the one TM012 IQ-grid outlier.

The v1 comparison is limited by availability of original products: 94 HDF5 are accessible, 166 are absent. The separate historical campaign CSV permits 35,880 comparisons over all 260 runs. All 114 differences concern episodes/rates at 3 sigma; sample counts and fractions remain equal. Do not extrapolate phase-increment equivalence from amplitude equality.
