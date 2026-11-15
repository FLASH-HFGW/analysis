# Toy simulation with measured DAQ response

Run `python3 validate_toy_response.py`. Outputs are separated in
`/home/mazzitel/HFGW/analysis-work/Run2/simulation/toy_measured_response/`.

The science data use the confirmed ODB ADC range ±2 V, while the DAQ tone
calibration used ±5 V. The ADC scale is `2*range/65535` V/count. The measured
per-mode response comes from integrated calibration tones (with Hann equivalent
noise bandwidth accounted for); it replaces the previously assumed LPF.

## Explicit, unconfirmed reference-plane assumption

Assume the calibration tone traversed the external 36 dB RF FET. Its gain is then
included in kz(f), so apply only `103.4−36=67.4 dB` upstream. The thesis prescribed
calibration instead keeps 103.4 dB and kz separate. Both reference choices are
recorded; the 67.4 dB hypothesis is selected for this comparison because it is the
specified physical-stage alternative closer to observations. It is not established
by that agreement and no per-mode gain is fitted. The actual injection node and
intervening losses remain the open question.

No arbitrary 60 dB or per-mode amplitude correction is introduced. RF source
power −60 dBm remains a calibration-tone setting, not a gain subtraction.

## Limits

Response magnitude is measured; phase is unavailable. The stationary covariance
is predicted from the PSD; no causal transient response is asserted. Response
outside the measured approximately ±3 MHz sweep is set to zero. Aliasing is
included only within that modeled support. Receiver Tn=3.955±0.468 K is inherited
from the thesis configuration, not independently fitted here. Quoted expected
values use its central value; ±0.468 K alone corresponds to approximately ±5.9%
RMS uncertainty when receiver dominated and does not include gain/response errors.

Cavity physical parameters and observed run680 temperature are retained. The
intrinsic-wall thermal term is included with both external-port damping rates;
incident-port noise and a full correlated quantum receiver model remain absent.

Fifteen numerical checks verify generated power, covariance, ADC clipping and
marginal distributions. They test implementation of the declared model, not the
truth of the reference-plane hypothesis.
