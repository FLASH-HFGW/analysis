"""HDF5 storage for unfiltered, energy-preserving IQ spectra."""
import numpy as np


def spectrum_rows(group, name, length, dtype, unit, compression):
    dataset = group.create_dataset(
        name, shape=(0, length), maxshape=(None, length),
        chunks=(1, min(length, 262144)), dtype=dtype, compression=compression)
    dataset.attrs["unit"] = unit
    return dataset


def append_row(dataset, row):
    index = len(dataset)
    dataset.resize(index + 1, axis=0)
    dataset[index] = row


class CompactSpectra:
    def __init__(self, group, n, modes, args):
        self.group = group
        self.compression = args.compression
        self.first_hz = -(n // 2)
        self.starts = np.arange(0, n, args.bin_hz, dtype=np.int64)
        self.widths = np.diff(np.r_[self.starts, n])
        group.attrs.update(profile="compact", frequency_spacing_hz=1,
                           frequency_first_hz=self.first_hz, frequency_count=n,
                           nominal_window_bin_width_hz=args.bin_hz,
                           stored_windows=0)
        group.create_dataset("window_bin_edges_hz",
                             data=self.first_hz - 0.5 + np.r_[self.starts, n])
        group.create_dataset("window_bin_width_hz", data=self.widths)
        self.sums = {mode: np.zeros(n, dtype=np.float64) for mode in modes}
        self.maxima = ({mode: np.zeros(n, dtype=np.float32) for mode in modes}
                       if args.max_psd else {})
        self.bands = []
        self.band_product = args.band_product
        for low, high in args.band:
            start, stop = np.ceil([low, high]).astype(np.int64) - self.first_hz
            if not 0 <= start < stop <= n:
                raise ValueError(f"band [{low}, {high}) has invalid FFT-bin bounds")
            self.bands.append((int(start), int(stop)))
        self.window_rows = {}
        self.band_rows = {}
        for mode in modes:
            mode_group = group.create_group(mode)
            self.window_rows[mode] = spectrum_rows(
                mode_group, "window_psd", len(self.starts), "f4", "V^2/Hz", self.compression)
            self.band_rows[mode] = []
            for index, (start, stop) in enumerate(self.bands):
                complex_band = self.band_product == "fft"
                dataset = spectrum_rows(mode_group, f"band_{index}", stop - start,
                                        "c8" if complex_band else "f4",
                                        "V" if complex_band else "V^2/Hz", self.compression)
                dataset.attrs.update(frequency_first_hz=self.first_hz + start,
                                     frequency_spacing_hz=1,
                                     requested_low_hz=args.band[index][0],
                                     requested_high_hz=args.band[index][1])
                self.band_rows[mode].append(dataset)

    def write(self, mode, x, power):
        # One-second FFTs have df=1 Hz, so |FFT(z)/N|² is also the PSD.
        ordered = np.fft.fftshift(power)
        self.sums[mode] += ordered
        if mode in self.maxima:
            np.maximum(self.maxima[mode], ordered, out=self.maxima[mode])
        density = (np.add.reduceat(ordered, self.starts, dtype=np.float64) /
                   self.widths).astype(np.float32)
        append_row(self.window_rows[mode], density)
        for (start, stop), dataset in zip(self.bands, self.band_rows[mode]):
            if self.band_product == "fft":
                indices = np.arange(self.first_hz + start, self.first_hz + stop)
                append_row(dataset, x[indices])
            else:
                append_row(dataset, ordered[start:stop])
        before = ordered.sum(dtype=np.float64)
        after = np.dot(density.astype(np.float64), self.widths)
        return abs(after - before) / before if before else 0.

    def finish(self, n_windows):
        self.group.attrs["stored_windows"] = n_windows
        for mode, total in self.sums.items():
            group = self.group[mode]
            mean = total / n_windows if n_windows else np.full_like(total, np.nan)
            group.create_dataset("mean_psd", data=mean.astype(np.float32),
                                 compression=self.compression).attrs["unit"] = "V^2/Hz"
            if mode in self.maxima:
                peak = self.maxima[mode]
                if not n_windows:
                    peak.fill(np.nan)
                group.create_dataset("max_psd", data=peak,
                                     compression=self.compression).attrs["unit"] = "V^2/Hz"
