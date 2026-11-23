"""Compact full-band screen using the already-loaded native window PSD."""
import numpy as np
from scipy.signal import find_peaks

ANCHOR = -492750.5
DELTA_LO = 11000


def screen(mode, frequency, power, background, scale):
    mean = power.mean(axis=0)
    ratio = mean / background
    peaks = find_peaks(ratio)[0]
    strongest = peaks[np.argsort(ratio[peaks])[-50:][::-1]]
    groups = [('full_band_rank', int(i)) for i in strongest]
    if mode == 'TM012':
        for name, center in [('fixed_IF', ANCHOR), ('fixed_RF_nominal', ANCHOR-DELTA_LO),
                             ('opposite_shift', ANCHOR+DELTA_LO)]:
            fixed = int(np.argmin(abs(frequency-center)))
            near = np.flatnonzero(abs(frequency-center) <= 500)
            groups += [(name, fixed), (name+'_local_max', int(near[np.argmax(ratio[near])]))]
    return [dict(mode=mode, screen=label, IF_Hz=float(frequency[i]),
                 mean_PSD_V2_Hz=float(mean[i]), local_background_V2_Hz=float(background[i]),
                 mean_ratio=float(ratio[i]), occupancy_count=int(np.sum(power[:, i] /
                     (scale*background[i]) > 3)), windows=len(power))
            for label, i in groups]
