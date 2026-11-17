"""Build a matched nominal downconversion budget from manufacturer data only."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
MODES = ("TM010", "TM011", "TM012")
BPF = (None, "SIF-40+", "SBP-101+")
COLORS = ("#177d85", "#9562a5", "#bd661c")


def between(x, xp, yp):
    return np.interp(x, xp, yp, left=np.nan, right=np.nan)


def filter_loss(data, name, f):
    if name is None:
        return np.zeros_like(f)
    table = data[name]
    return between(f, table["f_MHz"], table["loss_dB"])


def response(data, setting, mode, final, side=1):
    """side=-1 is the RF image from the negative primary-IF band."""
    final = np.asarray(final, dtype=float)
    lo1 = setting["LO1_MHz"]
    lo2 = setting["LO2_MHz"][mode]
    if lo2 == 0 and side != 1:
        raise ValueError("TM010 has no secondary mixer")
    primary_signed = final + side * lo2
    rf = lo1 + primary_signed
    primary, final_abs = abs(primary_signed), abs(final)
    marki = data["MMIQ-0520H"]
    marki_valid = ((marki["RF_LO_min_MHz"] <= rf) & (rf <= marki["RF_LO_max_MHz"]) &
                   (marki["RF_LO_min_MHz"] <= lo1 <= marki["RF_LO_max_MHz"]) &
                   (primary <= marki["low_IF_band_max_MHz"]))
    marki_loss = np.where(marki_valid, marki["typical_CL_per_quadrature_dB"], np.nan)
    femto = data["DHPVA-101"]
    gain = setting["FEMTO_dB"]
    femto_gain = gain + between(np.log10(np.maximum(primary, 1e-15)),
                               np.log10(femto["f_MHz"]), femto[f"relative_{gain}_dB"])
    divider = data["ZSC-4-1+"]
    divider_loss = np.stack([between(primary, divider["f_MHz"], divider[f"S{i}_loss_dB"])
                             for i in range(1, 5)])
    bpf = filter_loss(data, BPF[mode], primary)
    swapped = filter_loss(data, BPF[3-mode] if mode else None, primary)
    zad_valid = (lo2 >= .1) & (lo2 <= 500) & (primary >= .1) & (primary <= 500) & (final_abs <= 500)
    zad = np.where(zad_valid, data["ZAD-1-1+"]["midband_typical_loss_dB"], np.nan) if lo2 else np.zeros_like(final)
    lpf = filter_loss(data, "BLP-1.9+", final_abs)
    split_mean = divider_loss.mean(axis=0)
    nominal = femto_gain - marki_loss - split_mean - bpf - zad - lpf
    i_label = femto_gain - marki_loss - split_mean - swapped - zad - lpf
    return dict(final_MHz=final, rf_MHz=rf, primary_signed_MHz=primary_signed,
                marki_CL_dB=marki_loss, femto_gain_100MHz_dB=femto_gain,
                splitter_mean_loss_dB=split_mean, splitter_min_loss_dB=divider_loss.min(axis=0),
                splitter_max_loss_dB=divider_loss.max(axis=0), bpf_functional_loss_dB=bpf,
                bpf_I_drawing_loss_dB=swapped, zad_CL_midband_typical_dB=zad, lpf_loss_dB=lpf,
                I_functional_dB=nominal, Q_functional_dB=nominal,
                I_drawing_dB=i_label, Q_drawing_dB=nominal,
                Vq_over_VRF=10**(nominal/20), Pq_over_PRF=10**(nominal/10),
                z_norm_over_VRF=np.sqrt(2)*10**(nominal/20),
                summed_IQ_P_over_PRF=2*10**(nominal/10), summed_IQ_dB=nominal+10*np.log10(2),
                drawing_sum_IQ_dB=10*np.log10(10**(i_label/10) + 10**(nominal/10)))


def scalar_rows(prefix, columns):
    for values in zip(*columns.values()):
        yield {**prefix, **{key: format(v, ".11g") if np.isfinite(v) else ""
                            for key, v in zip(columns, values)}}


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def plot_components(data, out):
    fig, axes = plt.subplots(3, 2, figsize=(11, 10))
    ax = axes.flat
    m = data["MMIQ-0520H"]
    ax[0].hlines([m["typical_CL_per_quadrature_dB"], m["max_CL_per_quadrature_dB"]], 0, 200,
                 colors=["#177d85", ".55"], linestyles=["-", "--"])
    ax[0].set(title="Marki · tipica e max, RF e LO 5–20 GHz", xlabel="IF₁ (MHz)", ylabel="Conversion loss (dB)")
    femto = data["DHPVA-101"]
    for gain in (20, 60):
        ax[1].semilogx(femto["f_MHz"], gain+np.array(femto[f"relative_{gain}_dB"]), ".-", label=f"{gain} dB")
    ax[1].axvline(100, ls=":", color=".5")
    ax[1].set(title="FEMTO · curva tipica digitalizzata, 100 MHz", xlabel="IF₁ (MHz)", ylabel="Guadagno (dB)")
    ax[1].legend()
    d = data["ZSC-4-1+"]
    for n in range(1, 5):
        ax[2].semilogx(d["f_MHz"], d[f"S{n}_loss_dB"], ".-", label=f"S→{n}")
    ax[2].set(title="ZSC · perdita totale per uscita", xlabel="IF₁ (MHz)", ylabel="Perdita (dB)")
    ax[2].legend()
    for label in BPF[1:]:
        d = data[label]
        ax[3].plot(d["f_MHz"], d["loss_dB"], ".-", label=label)
    ax[3].set(title="BPF · specifiche tabulate", xlim=(30, 115), xlabel="IF₁ (MHz)", ylabel="Perdita (dB)")
    ax[3].legend()
    d = data["ZAD-1-1+"]
    ax[4].plot(d["rf_MHz"], d["loss_dB"], ".-", label="IF = 30 MHz")
    ax[4].hlines(d["midband_typical_loss_dB"], .2, 250, color=".55", ls="--", label="Tipica midband")
    ax[4].set(title="ZAD · sweep con RF e LO variabili", xlabel="RF del secondo mixer (MHz)", ylabel="Conversion loss (dB)")
    ax[4].legend()
    d = data["BLP-1.9+"]
    ax[5].plot(d["f_MHz"], d["loss_dB"], ".-", label="Tabella tipica")
    ax[5].plot(2.5, 3, "x", label="Specifica nominale")
    ax[5].set(title="BLP · risposta tabulata", xlim=(0, 5), xlabel="IF finale (MHz)", ylabel="Perdita (dB)")
    ax[5].legend()
    fig.tight_layout()
    fig.savefig(out / "components.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(11, 3.3))
    for name, ax in zip((*BPF[1:], "BLP-1.9+"), axes):
        d = data[name]
        ax.plot(d["delay_f_MHz"], d["delay_ns"], "o", ms=3)
        if name == "SIF-40+":
            ax.set_xlim(30, 55)
        ax.set(title=name, xlabel="Frequenza (MHz)", ylabel="Ritardo di gruppo (ns)")
    fig.tight_layout()
    fig.savefig(out / "group_delay.png", dpi=150)
    plt.close(fig)


def build(data, out):
    grid = np.round(np.linspace(-2.5, 2.5, 1001), 6)
    rows, centers = [], []
    fig, axes = plt.subplots(3, 2, figsize=(11, 9), sharex=True)
    for column, (name, setting) in enumerate(data["settings"].items()):
        for mode, label in enumerate(MODES):
            ax = axes[mode, column]
            center_f = data["cavity_rf_MHz"][mode] - setting["LO1_MHz"] - setting["LO2_MHz"][mode]
            for side in ((1,) if mode == 0 else (1, -1)):
                path = "main" if side == 1 else "secondary_image"
                prefix = dict(setting=name, mode=label, path=path)
                result = response(data, setting, mode, grid, side)
                rows.extend(scalar_rows(prefix, result))
                centers.extend(scalar_rows(prefix, response(data, setting, mode, [center_f], side)))
                ax.plot(grid, result["I_functional_dB"], color=COLORS[mode],
                        ls="-" if side == 1 else "--", label=path)
                if side == 1 and mode:
                    ax.plot(grid, result["I_drawing_dB"], color=".4", ls=":", label="I con BPF da schema")
            ax.axvline(center_f, lw=1, color=".7")
            ax.axvspan(-.1, .1, color=".92", zorder=-2)
            ax.set(title=f"{name} · {label}", ylabel="Guadagno/quadratura (dB)", xlim=(-2.5, 2.5))
            ax.legend(loc="lower left", fontsize=7)
    for ax in axes[-1]:
        ax.set_xlabel("IF finale firmata (MHz)")
    fig.tight_layout()
    fig.savefig(out / "end_to_end.png", dpi=150)
    plt.close(fig)
    write_csv(out / "response.csv", rows)
    write_csv(out / "gain_budget.csv", centers)
    plot_components(data, out)


if __name__ == "__main__":
    build(json.loads((HERE / "manufacturer.json").read_text()), HERE)
