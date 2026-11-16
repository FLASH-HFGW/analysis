# Thesis comparison

Run `python3 simulation/thesis_comparison/compare.py` from the repository. Requires NumPy, SciPy, Matplotlib, Pillow and pdftoppm. Inputs and outputs reside in analysis-work; the script embeds provenance hashes.

This adds a statistical estimator check against Fig6.7 of Valeria Spasiano's thesis, not independent validation of the complete analog-chain toy. Ttotal3.985K and integration settings are inputs. The flat continuum does not model the observed background slope, correlated Hann bins or a coherent calibration tone. Reported simulation variation is an ensemble interval, not a fitted uncertainty from thesis raw data.

The gain/ADC comparison uses run680, whose measured hardware range is ±2V. The ±5V reinterpretation is explicitly counterfactual. No identified matched ±5V thesis thermal-noise dataset is available in this analysis. Prediction at103.4dB is the unsaturated analog value; physical ADC clipping changes the marginal shape and is not applied to the scale table. It cannot be compared as an unclipped ADC distribution.
