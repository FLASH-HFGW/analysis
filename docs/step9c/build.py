"""Step 9C, using archived calibration and analytical quadrature only."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import firwin

HERE = Path(__file__).resolve().parent
HW_DIR = HERE.parent / "step9b"
spec = importlib.util.spec_from_file_location("hardware9b", HW_DIR / "build.py")
hw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hw)
HW = json.loads((HW_DIR / "manufacturer.json").read_text())
CAL = HW["settings"]["calibration"]
SCI = HW["settings"]["run680"]
FS = 5e6
TONE_SCALE = .01
R = 50
KB = 1.380649e-23
HPLANCK = 6.62607015e-34
MODES = hw.MODES
OFFSETS = (-1, 0, 1)


def json_read(path):
    return json.loads(path.read_text())


def csv_read(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(name, rows):
    with (HERE / name).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: (format(value, ".11g") if np.isfinite(value) else "")
                             if isinstance(value, (float, np.floating)) else value
                             for key, value in row.items()})


def amplitude_db(x):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 20*np.log10(x)


def pow_db(x):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10*np.log10(x)


def response(setting, mode, f, side=1):
    return hw.response(HW, setting, mode, np.asarray(f)/1e6, side)


def upstream(r):
    return (r["femto_gain_100MHz_dB"]-r["marki_CL_dB"]-r["splitter_mean_loss_dB"]
            -r["bpf_functional_loss_dB"]-r["zad_CL_midband_typical_dB"])


def correction_db(mode, science, calibration, same_if):
    if not same_if:
        return science["summed_IQ_dB"]-calibration["summed_IQ_dB"]
    if mode == 0:
        # Same primary IF, shared Marki and splitter cancel with final BLP.
        return science["femto_gain_100MHz_dB"]-calibration["femto_gain_100MHz_dB"]
    # Same final IF, so BLP cancels, including below its tabulated magnitude.
    return upstream(science)-upstream(calibration)


def image_ratio(mode, science, image):
    if mode == 0:
        return np.zeros_like(science["final_MHz"])
    # Common final BLP cancels. Both products are referenced to one RF input PSD.
    return 10**((upstream(image)-upstream(science))/10)


def curve(source, mode):
    offset = source["comparison"][mode]["rf_if_offset_hz"]
    pts = sorted(source["curves"][mode], key=lambda r: r["rf_hz"])
    return (np.array([r["rf_hz"]-offset for r in pts]),
            np.array([r["kz_integrated"] for r in pts]))


def coherent(index, x, k):
    f = np.arange(-2500000, 2500001, 5000)
    ref = 1250000
    fs = np.r_[f, ref]
    sc = response(SCI, index, fs)
    table = []
    for coordinate in ("IF", "RF"):
        offset_hz = round((SCI["LO1_MHz"] + SCI["LO2_MHz"][index] -
                           CAL["LO1_MHz"] - CAL["LO2_MHz"][index])*1e6)
        fc = fs if coordinate == "IF" else fs+offset_hz
        ca = response(CAL, index, fc)
        ks = between(fc, x, k)
        kc_db, s_db, c_db = amplitude_db(ks), sc["summed_IQ_dB"], ca["summed_IQ_dB"]
        ratio_db = correction_db(index, sc, ca, coordinate == "IF")
        values = dict(science_IF_hz=fs, calibration_IF_hz=fc, science_RF_MHz=sc["rf_MHz"],
                      calibration_RF_MHz=ca["rf_MHz"], kz=ks, kz_science_scalar=ks*TONE_SCALE,
                      HW_calibration_dB=c_db, HW_science_dB=s_db, HW_science_over_cal_dB=ratio_db,
                      excess_transfer_over_LF_setting_dB=ratio_db+40,
                      HW_cal_over_kz_dB=c_db-kc_db, HW_science_over_scaled_kz_dB=s_db-kc_db+40)
        for key in ("kz", "HW_calibration_dB", "HW_science_dB", "HW_science_over_cal_dB"):
            series = kc_db if key == "kz" else values[key]
            values[key+"_shape_from_1250kHz_dB"] = series-series[-1]
        table.extend(dict(mode=MODES[index], comparison=coordinate, **dict(zip(values, r)))
                     for r in list(zip(*values.values()))[:-1])
    return table


def between(x, xp, yp):
    return np.interp(x, xp, yp, left=np.nan, right=np.nan)


def spectrum(index, x, k, phys, gain_db, n):
    f = np.fft.fftfreq(n, 1/FS)
    mode = MODES[index]
    delta = round((SCI["LO1_MHz"]+SCI["LO2_MHz"][index] -
                   CAL["LO1_MHz"]-CAL["LO2_MHz"][index])*1e6)
    ki = 2*np.pi*phys["f0_hz"]/phys["q0"]
    kt = ki*(1+phys["kappa1"]+phys["kappa2"])
    hv = HPLANCK*phys["f0_hz"]
    theta = hv/np.expm1(hv/(KB*phys["temperature_k"]))
    scales = {name: np.zeros_like(f) for name in
              ("A","B","C_IF","C_RF","D","E_IF","E_RF","D_rho_0p5","D_rho_2")}
    thermal = {name: v.copy() for name, v in scales.items()}
    alias_electronic = {name: v.copy() for name, v in scales.items()}
    image_electronic = {name: v.copy() for name, v in scales.items()}
    for alias in OFFSETS:
        af = f + alias*FS
        direct = np.interp(af, x, k, left=0, right=0)*TONE_SCALE
        mapped = between(af+delta, x, k)
        nominal = response(SCI, index, af)
        image = None if index == 0 else response(SCI, index, af, -1)
        ratio = image_ratio(index, nominal, image)
        same_if = 10**(correction_db(index, nominal, response(CAL, index, af), True)/10)
        same_rf = 10**(correction_db(index, nominal, response(CAL, index, af+delta), False)/10)
        # A/B use the frozen compact-support convention. RF translation also uses
        # the shifted sweep's endpoints, while overlaps missing either sweep stay unknown.
        original_active = (af >= x[0]) & (af <= x[-1])
        shifted_active = (af+delta >= x[0]) & (af+delta <= x[-1])
        coupled_if = np.where(original_active, direct**2*same_if*1e4, 0)
        coupled_rf = np.where(original_active | shifted_active, mapped**2*same_rf, 0)
        direct2 = direct**2
        gain = 10**(gain_db/10)
        main = dict(A=direct2*10**(103.4/10), B=direct2*gain,
                    C_IF=coupled_if*gain, C_RF=coupled_rf*gain, D=direct2*gain,
                    E_IF=coupled_if*gain, E_RF=coupled_rf*gain,
                    D_rho_0p5=direct2*gain, D_rho_2=direct2*gain)
        wall = theta*ki**2*phys["kappa2"]/((kt/2)**2+(2*np.pi*(af-1e6))**2)
        for name, factor in main.items():
            rho = {"D":1, "E_IF":1, "E_RF":1, "D_rho_0p5":.5, "D_rho_2":2}.get(name, 0)
            primary = R*KB*3.955*factor
            image_part = np.where(factor == 0, 0, primary*ratio*rho) if rho else np.zeros_like(f)
            scales[name] += primary + image_part
            image_electronic[name] += image_part
            thermal[name] += R*wall*factor
            if alias:
                alias_electronic[name] += primary + image_part
    return f, scales, thermal, alias_electronic, image_electronic


def summarize(mode, n, result, comparison):
    f, electronic, thermal, aliases, images = result
    taps = firwin(2001, 25000, fs=FS, window=("kaiser",8.6))
    rows = []
    for band in comparison:
        is_full = band["region"] == "full"
        center = None if is_full else float(band["center_IF_hz"])
        weight = (np.ones(n) if is_full else
                  abs(np.fft.fft(taps*np.exp(2j*np.pi*center/FS*np.arange(taps.size)), n))**2)
        observed = float(band["run680_V2"])
        for name in electronic:
            known = np.isfinite(electronic[name]) & np.isfinite(thermal[name])
            w = weight[known]*(FS/n)
            contribution = lambda values: np.sum(values[known]*w)
            pe, pt = contribution(electronic[name]), contribution(thermal[name])
            pb = contribution(electronic["B"]+thermal["B"])
            pa = contribution(electronic["A"]+thermal["A"])
            complete = bool(known.all())
            rows.append(dict(mode=mode, scenario=name, region=band["region"],
                             offset_hz=band["offset_hz"], center_IF_hz=band["center_IF_hz"],
                             complete_on_model_support=int(complete),
                             known_IF_fraction=known.mean(), known_FIR_weight_fraction=weight[known].sum()/weight.sum(),
                             known_A_power_fraction=pa/(np.sum(weight*(electronic["A"]+thermal["A"]))*FS/n),
                             electronic_V2=pe, cavity_V2=pt, RMS_ADC_V=np.sqrt(pe+pt),
                             image_electronic_V2=contribution(images[name]),
                             ADC_alias_electronic_V2=contribution(aliases[name]),
                             A_on_same_intervals_V2=pa, B_on_same_intervals_V2=pb,
                             model_over_B_same_intervals_dB=pow_db((pe+pt)/pb),
                             data_full_window_V2=observed,
                             data_over_model_dB=pow_db(observed/(pe+pt)) if complete else np.nan,
                             data_over_model_upper_bound_dB=pow_db(observed/(pe+pt)) if not complete else np.nan))
    return rows


def main(work):
    cal_path = work / "diagnostics/normalization_audit_20261114/calibration_reconstruction.json"
    phys_path = work / "simulation/step6/metrics.json"
    toy_path = work / "simulation/toy_ODB_cal5_data2_LF_20261116/metrics.json"
    source, physical, toy = (json_read(p) for p in (cal_path, phys_path, toy_path))
    for path in (cal_path, phys_path):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        frozen = {Path(key).name: value for key, value in toy["input_sha256"].items()}
        assert digest == frozen[path.name], path
    comparison = csv_read(HERE.parent / "step9a/comparison.csv")
    gains = {r["mode"]: float(r["L5_dB"])+36 for r in csv_read(HERE.parent / "step9a/vna/fits.csv")
             if r["fit"] == "free_eq69"}
    coherent_rows, power_rows, psd_rows, fold_rows = [], [], [], []
    fig, axes = plt.subplots(3, 2, figsize=(11, 9), sharex=True)
    shape_fig, shape_axes = plt.subplots(3, 2, figsize=(11, 9), sharex=True)
    psd_fig, psd_ax = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    fold_fig, fold_ax = plt.subplots(figsize=(8, 4))
    for index, mode in enumerate(MODES):
        x, k = curve(source, mode)
        rows = coherent(index, x, k)
        coherent_rows.extend(rows)
        for col, coordinate in enumerate(("IF", "RF")):
            subset = [r for r in rows if r["comparison"] == coordinate]
            ax = axes[index, col]
            fx = [r["science_IF_hz"]/1e6 for r in subset]
            for field, label in (("HW_calibration_dB","HW cal"), ("kz","kz cal"),
                                 ("HW_science_dB","HW sci"), ("kz_science_scalar","0.01 kz cal")):
                v = np.array([r[field] for r in subset])
                ax.plot(fx, amplitude_db(v) if field.startswith("kz") else v, label=label)
            ax.set(title=f"{mode} · stessa {coordinate}", ylabel="Modulo complesso (dB)")
            shape_ax = shape_axes[index, col]
            for field, label in (("HW_calibration_dB", "HW cal"), ("kz", "kz cal"),
                                 ("HW_science_dB", "HW sci")):
                v = [r[field+"_shape_from_1250kHz_dB"] for r in subset]
                shape_ax.plot(fx, v, label=label)
            shape_ax.plot(fx, [r["excess_transfer_over_LF_setting_dB"] for r in subset],
                          ls="--", label="Trasferibilità oltre −40 dB")
            shape_ax.set(title=f"{mode} · stessa {coordinate}", ylabel="Forma o rapporto (dB)")
            if index == 0:
                ax.legend(ncol=2, fontsize=8)
                shape_ax.legend(ncol=2, fontsize=8)
        regions = [r for r in comparison if r["mode"] == mode]
        mode_phys = physical["mode_results"][mode]
        n = 2**20
        result = spectrum(index, x, k, mode_phys, gains[mode], n)
        powers = summarize(mode, n, result, regions)
        coarse = 2**18
        check = summarize(mode, coarse, spectrum(index, x, k, mode_phys, gains[mode], coarse), regions)
        for row, control in zip(powers, check):
            err = abs(row["electronic_V2"]/control["electronic_V2"]-1)
            row["quadrature_grid_relative_difference"] = err
            assert err < .005, (mode, row, control)
        power_rows.extend(powers)
        base = next(r for r in powers if r["scenario"] == "A" and r["region"] == "full")
        assert np.isclose(base["electronic_V2"]+base["cavity_V2"], toy["results"][mode]["expected_power_v2"], rtol=1e-10)
        f, pe, pt, alias_e, img_e = result
        plot_indices = np.fft.fftshift(np.arange(n))[::1024]
        for name in pe:
            for j in plot_indices:
                psd_rows.append(dict(mode=mode, scenario=name, IF_hz=f[j],
                                     electronic_V2_per_Hz=pe[name][j], cavity_V2_per_Hz=pt[name][j],
                                     image_V2_per_Hz=img_e[name][j], alias_electronic_V2_per_Hz=alias_e[name][j]))
            if name in ("A", "B", "C_RF", "D", "E_RF"):
                psd_ax[index].semilogy(f[plot_indices]/1e6, pe[name][plot_indices], label=name)
        psd_ax[index].set(title=mode, ylabel="PSD elettr. (V²/Hz)")
        psd_ax[index].legend(ncol=5, fontsize=8)
        grid = np.arange(-3000000, 3000001, 5000)
        main_hw = response(SCI, index, grid)
        image_hw = response(SCI, index, grid, -1) if index else None
        ratio = image_ratio(index, main_hw, image_hw)
        fold_ax.plot(grid/1e6, pow_db(1+ratio), label=mode)
        for j, ff in enumerate(grid):
            fold_rows.append(dict(mode=mode, analog_final_IF_hz=ff, RF_main_MHz=main_hw["rf_MHz"][j],
                                  RF_image_MHz=image_hw["rf_MHz"][j] if index else "",
                                  image_main_power=ratio[j], rho_0p5_fold_dB=pow_db(1+.5*ratio[j]),
                                  rho_1_fold_dB=pow_db(1+ratio[j]), rho_2_fold_dB=pow_db(1+2*ratio[j])))
    for ax in (*axes[-1], *shape_axes[-1]):
        ax.set_xlabel("IF finale science (MHz)")
    psd_ax[-1].set_xlabel("IF ADC (MHz)")
    fold_ax.set(xlabel="IF finale analogica (MHz)", ylabel="Folding white RF (dB)")
    fold_ax.legend()
    for plot, name in ((fig, "coherent"), (shape_fig, "shape"), (psd_fig, "psd"), (fold_fig, "folding")):
        plot.tight_layout()
        plot.savefig(HERE/f"{name}.png", dpi=150)
    tone_rows = []
    for mode in MODES:
        offset = source["comparison"][mode]["rf_if_offset_hz"]
        for point in source["curves"][mode]:
            tone_rows.append(dict(mode=mode, rf_hz=point["rf_hz"], fft_peak_signed_IF_hz=point["if_hz"],
                                  nominal_unfolded_IF_hz=point["rf_hz"]-offset,
                                  kz_peak=point["kz"], kz_integrated=point["kz_integrated"],
                                  tone_ADC_RMS_V=point["kz_integrated"]*np.sqrt(50e-9),
                                  source_runs=" ".join(map(str, point["runs"]))))
    for name, rows in (("tone_points.csv", tone_rows), ("coherent.csv", coherent_rows), ("powers.csv", power_rows),
                       ("psd.csv", psd_rows), ("folding.csv", fold_rows)):
        write_csv(name, rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path, help="Path to analysis-work/Run2 frozen products")
    main(parser.parse_args().work)
