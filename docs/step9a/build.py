"""Read frozen analytical powers and plot candidate RF archive traces."""
import argparse
import csv
import json
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

MODES = ("TM010", "TM011", "TM012")
SCALE = 10 ** ((67.81 + 36 - 103.4) / 10)


def run680(path):
    with path.open(newline="") as stream:
        return [row for row in csv.DictReader(stream) if row["run"] == "680"]


def comparison(work, out):
    data = work / "reports/iq_noise_summary_v47/data"
    full = {r["mode"]: r for r in run680(data / "fullband_v2.csv")}
    bands = run680(data / "campaign_band_powers.csv")
    metrics = json.loads((work / "simulation/presentation_steps1_6_v43/metrics.json").read_text())
    archive = work / "diagnostics/resonance_campaign_primary_v47_20261117/expectations_and_campaign.h5"
    rows = []
    with h5py.File(archive) as baseline:
        for mode in MODES:
            model = metrics["metrics"][mode]
            records = [("", "", model["receiver_RMS_expected_ADC_V"] ** 2,
                        model["thermal_RMS_expected_ADC_V"] ** 2, float(full[mode]["AC2_ADC_V2"]))]
            ref = baseline[f"{mode}/analytic_reference"]
            measured = {int(r["offset_hz"]): r for r in bands if r["mode"] == mode}
            assert len(measured) == 7
            for i, offset in enumerate(baseline["offsets_hz"][:]):
                row = measured[offset]
                center = float(row["center_IF_hz"])
                assert center == baseline[f"{mode}/centers_IF_hz"][0, i]
                records.append((offset, center, ref["electronic_power_ADC_V2"][i],
                                ref["thermal_power_ADC_V2"][i], float(row["power_ADC_V2"])))
            for offset, center, electronic, thermal, observed in records:
                rows.append(dict(mode=mode, region="full" if center == "" else "FIR",
                                 offset_hz=offset, center_IF_hz=center,
                                 baseline_electronic_V2=electronic, baseline_cavity_V2=thermal,
                                 run680_V2=observed, baseline_data_over_model_power=observed/(electronic+thermal),
                                 conditional_global_electronic_V2=electronic*SCALE,
                                 conditional_global_cavity_V2=thermal*SCALE,
                                 conditional_data_over_model_power=observed/((electronic+thermal)*SCALE),
                                 independent_mode_electronic_V2=None))
    with (out / "comparison.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def plot_archive(archive, out):
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
    for index, (mode, ax) in enumerate(zip(MODES, axes), 1):
        for parameter in ("S12", "S21", "S22"):
            path, = archive.glob(f"{parameter}cav_modo{index}_2026-07-24_*.txt")
            frequency, real, imag = np.loadtxt(path, unpack=True)
            ax.plot(frequency / 1e9, 20 * np.log10(np.hypot(real, imag)),
                    label=f"{parameter} {path.stem.split('_')[-1]}", lw=1)
        ax.set_title(mode)
        ax.set_xlabel("Frequenza RF (GHz)")
        ax.legend(fontsize=8)
    axes[0].set_ylabel("Modulo misurato (dB)")
    fig.suptitle("Sweep VNA LNF del 24 luglio 2026")
    fig.tight_layout()
    fig.savefig(out / "vna_20260724.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4))
    for path in sorted(archive.glob("spectrumAnalyzer_2026-07-27_*.txt")):
        frequency, level = np.loadtxt(path, unpack=True)
        ax.plot(frequency / 1e9, level, label=path.stem.split("_")[-1], lw=0.8)
    ax.set(xlabel="Frequenza RF (GHz)", ylabel="Livello (unità del file)",
           title="Spectrum analyzer LNF, 27 luglio 2026 · setpoint non identificati")
    ax.legend(ncol=3)
    fig.tight_layout()
    fig.savefig(out / "spectrum_analyzer_20260727.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    output = Path(__file__).resolve().parent
    comparison(args.work, output)
    plot_archive(args.archive, output)
