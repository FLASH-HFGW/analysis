"""Plot and export measurements archived in one local autoreco compact product."""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from iq_products import binned_pairs, open_product, write_json


def table(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(rows.dtype.names)
        writer.writerows(rows.tolist())


def export(source, output):
    output.mkdir(parents=True, exist_ok=True)
    with open_product(source) as p:
        f = p.file
        temps = list(p.temperatures())
        report = dict(run=p.run, metadata=p.metadata, quality=dict(f["quality"].attrs),
                      timing={**dict(f["timing"].attrs), "pps": len(f["timing/pps"]),
                              "tgps": len(f["timing/tgps"])}, modes={}, apparatus=p.apparatus())
        table(output / "pps.csv", f["timing/pps"][:])
        if temps:
            with (output/"temperatures.csv").open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(("channel", "unit", "midas_unix", "value"))
                for name, unit, times, readings in temps:
                    writer.writerows((name, unit, t, value) for t, value in zip(times, readings))
            fig, ax = plt.subplots()
            for label, unit, t, v in temps:
                ax.plot(t-p.time_start, v*(1000 if unit == "K" else 1), ".", label=label)
            ax.set(xlabel="MIDAS header seconds from run start", ylabel="Temperature (mK)")
            ax.legend(fontsize=5)
            fig.savefig(output/"temperatures.png", dpi=140)
            plt.close(fig)
        archived_spectra = {"frequency_hz": p.frequency()}
        if "short_psd" in f:
            archived_spectra["short_frequency_hz"] = f["short_psd/frequency_hz"][:]
        for mode in p.modes:
            values = f[f"statistics/{mode}"]
            table(output/f"{mode}-statistics.csv", values[:])
            table(output/f"{mode}-episodes.csv", f[f"anomalies/{mode}/episodes"][:])
            table(output/f"{mode}-population.csv", f[f"anomalies/{mode}/population"][:])
            power = p.window_power(mode)
            np.savetxt(output/f"{mode}-power.csv", np.c_[p.windows["received_s"], power],
                       delimiter=",", header="received_s,power_v2", comments="")
            report["modes"][mode] = dict(statistics=dict(values.attrs),
                thresholds=p.excursions(mode), temperature_correlations={
                    name: binned_pairs(p.window_headers, power, ts, vals)
                    for name, _, ts, vals in temps})
            fig, axes = plt.subplots(3, 2, figsize=(13, 11), layout="constrained")
            ax = axes.flatten()
            freq = archived_spectra["frequency_hz"]
            psd = archived_spectra[f"{mode}_mean_psd"] = p.spectra[mode]["mean_psd"][:]
            stride = max(1, len(freq)//100000)
            starts = np.arange(0, len(freq), stride)
            ax[0].semilogy(freq[starts], np.maximum.reduceat(psd, starts))
            ax[0].set(xlabel="Frequency (Hz)", ylabel="Full PSD (V²/Hz)")
            if "short_psd" in f:
                short = f["short_psd"]
                for kind in ("rectangular", "hann"):
                    psd_short = archived_spectra[f"{mode}_{kind}"] = short[kind][mode][:]
                    ax[1].semilogy(archived_spectra["short_frequency_hz"], psd_short, label=kind)
                ax[1].legend()
            ax[1].set(xlabel="Frequency (Hz)", ylabel="Short FFT PSD (V²/Hz)")
            t = p.windows["received_s"]
            ax[2].plot(t, power)
            ax[2].set(xlabel="Received sample time (s)", ylabel="Integrated power (V²)")
            spec = p.spectra[mode]["window_psd"][:]
            with np.errstate(divide="ignore"):
                raster = 10*np.log10(spec)
            fig.colorbar(ax[3].imshow(raster, origin="lower", aspect="auto",
                                      extent=[p.edges[0],p.edges[-1],-.5,len(t)-.5]),
                         ax=ax[3], label="dB re V²/Hz")
            ax[3].set(xlabel="Frequency (Hz)", ylabel="FFT window")
            for key in ("mean_I_V", "mean_Qhardware_V", "rms_V", "ac_rms_V"):
                ax[4].plot(t, values[key], label=key)
            ax[4].legend(fontsize=7)
            ax[4].set(xlabel="Received sample time (s)", ylabel="Voltage (V)")
            hist = f.get(f"histograms/{mode}")
            if hist is not None:
                edges, counts = hist["amplitude_edges_v"][:], hist["amplitude_counts"][:]
                ax[5].stairs(counts, edges, label="observed")
                s2 = values.attrs["ac_rms_V"]**2
                if s2 > 0 and counts.sum():
                    # Rayleigh reference for a centered circular complex Gaussian.
                    expected = counts.sum() * -np.diff(np.exp(-edges**2/s2))
                    ax[5].stairs(expected, edges, label="zero-mean circular reference")
                    ax[5].legend(fontsize=7)
                ax[5].set(xlabel="Uncentered amplitude (V)", ylabel="Counts")
            fig.savefig(output/f"{mode}.png", dpi=130)
            plt.close(fig)
        np.savez(output/"spectral_data.npz", **archived_spectra)
        write_json(output/"summary.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    export(args.source, args.output)
