"""Fit the nine July 24 VNA sweeps and propagate scalar gains to frozen ADC integrals."""
import argparse
import csv
import hashlib
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import least_squares

TABLE = [(8737119000, 52490, .001122, .79),
         (8780840000, 53800, .071, .73),
         (8841182000, 38730, .0566, .50)]
PORTS = ("12", "21", "22")


def intrinsic(f, f0, q0, k1, k2, q, literal):
    x = q0 * 2 * (f - f0) / f0
    a = 1 + k1 + k2
    transmission = 2 * np.sqrt(k1 * k2) / (a + 1j*x)
    reflection = (k2**2 - (1 + k1**2 if literal else (1+k1)**2)
                  - (x+q)**2 - 2j*k2*x) / (a*a + x*x)
    return np.array([transmission, transmission, reflection])


def fit(f, measured, tab, free, literal, branch=None):
    f0, q0, k1, k2 = tab
    weights = np.sqrt(np.mean(measured**2, axis=1))[:, None]

    def unpack(p):
        if free:
            return f0 + 1000*p[4], q0*np.exp(p[5]), k1, np.exp(p[6]), p[3]
        return f0, q0, k1, k2, p[3]

    def model(p):
        return np.exp(p[:3, None])*abs(intrinsic(f, *unpack(p), literal))

    def residual(p):
        return ((model(p)-measured)/weights).ravel()

    response = abs(intrinsic(f, *tab, 0, literal))
    amp = (response*measured).sum(axis=1)/(response**2).sum(axis=1)
    candidates = []
    for q in (0, -.5, .5):
        for coupling in ((k2, 1.5) if free and branch is None else
                         (min(k2, .9*(1+k1)),) if branch == "under" else
                         (1.5*(1+k1),) if branch == "over" else (k2,)):
            start = [*np.log(amp), q]
            bounds = ([-30]*3+[-2], [30]*3+[2])
            if free:
                start += [0, 0, np.log(coupling)]
                bounds[0].extend([-250, -np.log(5), np.log(.03)])
                bounds[1].extend([250, np.log(5), np.log(5)])
                if branch == "under":
                    bounds[1][-1] = np.log(1+k1)
                if branch == "over":
                    bounds[0][-1] = np.log(1+k1)
            result = least_squares(residual, start, bounds=bounds, x_scale="jac")
            if result.success:
                candidates.append(result)
    best = min(candidates, key=lambda result: result.cost)
    p = best.x
    # Frequency-ordered Bartlett HAC sandwich, separate acquisitions per port.
    jac = best.jac
    bread = np.linalg.pinv(jac.T @ jac)
    meat = np.zeros_like(bread)
    for scores in (jac * best.fun[:, None]).reshape(3, len(f), len(p)):
        meat += scores.T @ scores
        for lag in range(1, 51):
            cross = scores[lag:].T @ scores[:-lag]
            meat += (1-lag/51)*(cross + cross.T)
    cov = bread @ meat @ bread
    contrast = np.r_[-1, 1, 1, np.zeros(len(p)-3)]*10/np.log(10)
    plus = abs(contrast)
    predicted = model(p)
    return dict(f0_hz=unpack(p)[0], Q0=unpack(p)[1], k1=k1, k2=unpack(p)[3], q=p[3],
                **{f"Abs{port}": a for port, a in zip(PORTS, np.exp(p[:3]))},
                **{f"Abs{port}_se": a*s for port, a, s in
                   zip(PORTS, np.exp(p[:3]), np.sqrt(np.maximum(0, np.diag(cov)[:3])))},
                L5_dB=contrast @ p, L5_stat_se_dB=np.sqrt(max(0, contrast @ cov @ contrast)),
                plus_dB=plus @ p, fit_ratio_dB=20*np.log10(np.exp(p[1]-p[0])),
                active_bounds=int(np.count_nonzero(best.active_mask)), jac_rank=np.linalg.matrix_rank(jac),
                relative_RMS=np.sqrt(np.mean(best.fun**2)),
                **{f"relative_RMS_S{port}": r for port, r in zip(PORTS,
                   np.sqrt(np.mean(((predicted-measured)/weights)**2, axis=1))) }), predicted


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(archive, out):
    rows, adc, traces, local, branches = [], [], [], [], []
    with (out.parent / "comparison.csv").open() as stream:
        baseline = list(csv.DictReader(stream))
    for index, tab in enumerate(TABLE, 1):
        mode = f"TM01{index-1}"
        arrays = []
        for port in PORTS:
            path, = archive.glob(f"S{port}cav_modo{index}_2026-07-24_*.txt")
            arrays.append(np.loadtxt(path))
            traces.append(dict(mode=mode, port=port, file=path.name,
                               sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        f = arrays[0][:, 0]
        assert all(np.array_equal(a[:, 0], f) for a in arrays)
        measured = np.array([np.hypot(a[:, 1], a[:, 2]) for a in arrays])
        detuning = (f-tab[0])/1e6
        ratio = 20*np.log10(measured[1]/measured[0])
        width = tab[0]*(1+tab[2]+tab[3])/tab[1]
        center = abs(f-tab[0]) <= width/2
        statistics = dict(ratio_center_median_dB=np.median(ratio[center]),
                          ratio_center_p16_dB=np.percentile(ratio[center], 16),
                          ratio_center_p84_dB=np.percentile(ratio[center], 84),
                          ratio_center_slope_dB_per_MHz=np.polyfit(detuning[center], ratio[center], 1)[0])
        for branch in ("under", "over"):
            result, _ = fit(f, measured, tab, True, False, branch)
            branches.append(dict(mode=mode, branch=branch, **result))
        fig, axes = plt.subplots(3, 2, figsize=(10, 9), sharex=True)
        for i, port in enumerate(PORTS):
            axes[i, 0].plot(detuning, measured[i], color=".65", label=f"S{port} VNA")
        styles = {"fixed_eq610": "--", "fixed_eq69": ":", "free_eq69": "-",
                  "free_eq610": "-."}
        for name, style in styles.items():
            result, predicted = fit(f, measured, tab, name.startswith("free"), name.endswith("610"))
            ratio_check = statistics["ratio_center_median_dB"]/2 + 10*np.log10(result["Abs22"])
            rows.append(dict(mode=mode, fit=name, **result, **statistics,
                             L5_from_direct_ratio_and_fit22_dB=ratio_check))
            if name == "free_eq69":
                with np.errstate(divide="ignore"):
                    local_gain = result["L5_dB"] + 10*np.log10(
                        measured[1]*measured[2]*predicted[0] /
                        (predicted[1]*predicted[2]*measured[0]))
                for indices in np.array_split(np.flatnonzero(center), 7):
                    local.append(dict(mode=mode, rf_Hz=np.mean(f[indices]),
                                      samples=len(indices), L5_apparent_median_dB=np.median(local_gain[indices]),
                                      ratio_median_dB=np.median(ratio[indices])))
            for i in range(3):
                axes[i, 0].plot(detuning, predicted[i], style, lw=1, label=name)
                axes[i, 1].plot(detuning, predicted[i]-measured[i], style, lw=.7)
            scale = 10**((result["L5_dB"] + 36 - 103.4)/10)
            for row in (r for r in baseline if r["mode"] == mode):
                electronic, thermal = (float(row[f"baseline_{key}_V2"]) for key in ("electronic", "cavity"))
                adc.append(dict(mode=mode, fit=name, region=row["region"], offset_hz=row["offset_hz"],
                                center_IF_hz=row["center_IF_hz"], total_RF_dB=result["L5_dB"]+36,
                                power_scale=scale, power_relative_stat_se=np.log(10)/10*result["L5_stat_se_dB"],
                                baseline_electronic_V2=electronic, baseline_cavity_V2=thermal,
                                electronic_V2=electronic*scale, cavity_V2=thermal*scale))
        axes[0, 0].legend(fontsize=7)
        axes[0, 1].set_title("Residuo modello − misura")
        for ax in axes[-1]:
            ax.set_xlabel("Frequenza rispetto a Tab. 6.1 (MHz)")
        fig.suptitle(mode + " · modulo VNA lineare")
        fig.tight_layout()
        fig.savefig(out / f"{mode}.png", dpi=140)
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.plot(detuning, ratio, lw=.8, label="S21/S12 misurato")
        ax.axvspan(detuning[center][0], detuning[center][-1], alpha=.12)
        for row in rows[-4:]:
            ax.axhline(row["fit_ratio_dB"], ls=styles[row["fit"]], label=row["fit"])
        ax.set(xlabel="Frequenza rispetto a Tab. 6.1 (MHz)", ylabel="Rapporto (dB)", title=mode)
        ax.legend(fontsize=7, ncol=2)
        fig.tight_layout()
        fig.savefig(out / f"{mode}_ratio.png", dpi=140)
        plt.close(fig)
    write_csv(out / "fits.csv", rows)
    write_csv(out / "adc.csv", adc)
    write_csv(out / "traces.csv", traces)
    write_csv(out / "local.csv", local)
    write_csv(out / "branches.csv", branches)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    main(parser.parse_args().archive, Path(__file__).resolve().parent)
