"""HDF5 storage for unfiltered, energy-preserving IQ spectra."""
from math import ceil

import numpy as np
from scipy.fft import fft
from time import perf_counter


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
            start, stop = ceil(low) - self.first_hz, ceil(high) - self.first_hz
            if not 0 <= start < stop <= n:
                raise ValueError(f"band [{low}, {high}) has invalid FFT-bin bounds")
            self.bands.append((start, stop))
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
        after = np.sum(density.astype(np.float64) * self.widths)
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


class ShortSpectra:
    """Incoherent PSD averages of contiguous, independently centered IQ blocks."""

    length = 16384

    def __init__(self, fs, modes, compression, workers):
        self.fs = fs
        self.compression = compression
        self.workers = workers
        self.hann = np.hanning(self.length).astype(np.float32)
        self.sums = {mode: np.zeros((2, self.length), np.float64) for mode in modes}
        self.energy = {mode: np.zeros(2, np.float64) for mode in modes}
        self.centered = np.empty((64, self.length), np.complex64)
        self.carry = {mode: np.empty(self.length, np.complex64) for mode in modes}
        self.fill = self.segments = self.discarded = 0
        self.elapsed_s = 0.
        self.window_energy = (float(self.length), np.sum(self.hann**2, dtype=np.float64))

    def feed(self, buffers, size):
        started = perf_counter()
        n = self.length
        count, tail = divmod(self.fill + size, n)
        for mode, z in buffers.items():
            carry = self.carry[mode]
            offset = 0
            if self.fill:
                offset = min(n - self.fill, size)
                carry[self.fill:self.fill + offset] = z[:offset]
                if count:
                    self.accumulate(mode, carry.reshape(1, n))
            if not self.fill or count:
                while offset + n <= size:
                    end = offset + min(len(self.centered), (size - offset)//n)*n
                    self.accumulate(mode, z[offset:end].reshape(-1, n))
                    offset = end
                carry[:tail] = z[offset:size]
        self.fill = tail
        self.segments += count
        self.elapsed_s += perf_counter() - started

    def accumulate(self, mode, source):
        block = self.centered[:len(source)]
        np.subtract(source, source.mean(axis=1, dtype=np.complex128, keepdims=True),
                    out=block)
        for index in range(2):
            if index:
                np.multiply(block, self.hann, out=block)
            self.energy[mode][index] += np.sum(np.abs(block)**2, dtype=np.float64)
            transformed = fft(block, axis=1, workers=self.workers, overwrite_x=bool(index))
            self.sums[mode][index] += np.sum(np.abs(transformed)**2, axis=0, dtype=np.float64)

    def break_segment(self):
        self.discarded += self.fill
        self.fill = 0

    def finish(self, group, received):
        self.break_segment()
        n = self.length
        if self.segments*n + self.discarded != received:
            raise ValueError("short PSD sample count does not match received samples")
        group.attrs.update(segment_samples=n, segments_per_mode=self.segments,
                           used_samples_per_mode=self.segments*n,
                           residual_samples_per_mode=self.discarded,
                           frequency_spacing_hz=self.fs/n, processing_s=self.elapsed_s,
                           population="complete contiguous nonoverlapping segments; complex mean removed",
                           normalization="mean(|FFT(w*(z-mean(z)))|^2/(fs*sum(w^2))); two-sided")
        group.create_dataset("frequency_hz", data=np.fft.fftshift(np.fft.fftfreq(n, 1/self.fs)))
        for index, name in enumerate(("rectangular", "hann")):
            window = group.create_group(name)
            energy = self.window_energy[index]
            window_sum = np.sum(self.hann, dtype=np.float64) if index else n
            window.attrs.update(window="symmetric Hann" if index else "rectangular",
                                enbw_hz=self.fs*energy/window_sum**2,
                                sum_squared_weights=energy)
            for mode in self.sums:
                if self.segments:
                    psd = self.sums[mode][index] / (self.segments*self.fs*energy)
                    expected = self.energy[mode][index] / (self.segments*energy)
                    psd = np.fft.fftshift(psd).astype(np.float32)
                    observed = psd.sum(dtype=np.float64)*self.fs/n
                    error = abs(observed-expected)/expected if expected else 0.
                    if not np.isfinite(error) or error > 1e-5:
                        raise ValueError(f"short PSD Parseval validation failed for {mode}/{name}")
                else:
                    psd = np.full(n, np.nan, np.float32)
                    expected = error = np.nan
                dataset = window.create_dataset(mode, data=psd, compression=self.compression)
                dataset.attrs.update(unit="V^2/Hz", weighted_mean_square_v2=expected,
                                     parseval_relative_error=error)
