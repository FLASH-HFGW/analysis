"""Tabulate signed complex-tone responses and compare archived I/Q diagnostics."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
MODES = ("TM010", "TM011", "TM012")


def read(path):
    return json.loads(path.read_text())


def save(name, rows):
    with (HERE/name).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: format(value, ".11g") if isinstance(value, (float, np.floating))
                          else value for key, value in row.items()} for row in rows)


def powers(main, image):
    return dict(main_ADC_V2=main, conjugate_ADC_V2=image, pair_ADC_V2=main+image,
                conjugate_over_main=image/main)


def sweeps(source, audit, directory):
    n, fs = 16383, 5e6
    f = np.fft.fftshift(np.fft.fftfreq(n, 1/fs))
    window = np.hanning(n)
    enbw = n*np.sum(window**2)/window.sum()**2
    observations = {r["run"]:r for r in source["sweep_observations"]}
    rows = []
    for index, mode in enumerate(MODES):
        reference = {r["run"]:r for r in audit["curves"][mode]}
        offset = source["comparison"][mode]["rf_if_offset_hz"]
        for point in source["curves"][mode]:
            for run in point["runs"]:
                meta = observations[run]
                assert meta["mode"] == mode and meta["adc_range_mV"][:6] == [5000]*6
                assert meta["generator_power_dbm"] == -60 and meta["rf_tone_hz"] == point["rf_hz"]
                incident = 1e-3*10**(meta["generator_power_dbm"]/10)
                vref2 = 50*incident
                with np.load(directory/f"run{run:05d}.npz") as spectrum:
                    y = spectrum[f"fft_amp_mode{index}_SPECs"].astype(float)
                    assert len(y) == n and float(spectrum["fs"]) == fs
                main = int(np.argmax(y))
                conj = int(np.argmin(abs(f+f[main])))
                main_bins = (main+np.arange(-12,13))%n
                conj_bins = (conj+np.arange(-12,13))%n
                assert not np.intersect1d(main_bins, conj_bins).size
                background = np.median(y)
                main_v2 = np.sum(y[main_bins]-background)/enbw
                conjugate_unclipped = np.sum(y[conj_bins]-background)/enbw
                conjugate_v2 = max(0, conjugate_unclipped)
                if run in reference:
                    assert np.isclose(main_v2/vref2, reference[run]["kz_main"]**2, rtol=1e-7)
                    assert np.isclose(conjugate_v2/vref2, reference[run]["kz_image"]**2, rtol=1e-7)
                input_if = point["rf_hz"]-offset
                folded_if = (input_if+fs/2)%fs-fs/2
                assert abs(f[main]-folded_if) < fs/n
                rows.append(dict(mode=mode, run=run, representative=int(run in reference),
                                 RF_hz=point["rf_hz"], input_IF_hz=input_if,
                                 unaliased=int(abs(input_if)<fs/2), main_peak_IF_hz=f[main],
                                 conjugate_peak_IF_hz=f[conj], generator_nominal_W=incident,
                                 **powers(main_v2, conjugate_v2),
                                 conjugate_unclipped_ADC_V2=conjugate_unclipped,
                                 Hplus_power=main_v2/vref2, conjugate_transfer_power=conjugate_v2/vref2,
                                 pair_transfer_power=(main_v2+conjugate_v2)/vref2))
    return rows


def independent(audit):
    rows = []
    for r in audit["raw_calibration_checks"]:
        a = r["tone_I_over_Q_amplitude"]
        error = r["quadrature_phase_error_deg"]
        cross = 2*a*np.cos(np.deg2rad(error))
        ratio = (a*a+1-cross)/(a*a+1+cross)
        chunk = r["raw_chunk_image_to_main_power"]
        coherent = r["raw_image_to_main_power"]
        main = r["kz_raw_chunk_main"]**2
        image = r["kz_raw_chunk_image"]**2
        q_power = (main+image)/(a*a+1)
        rows.append(dict(mode=r["mode"], run=r["run"], input_IF_hz=r["input_IF_hz"],
                         I_over_Q_amplitude=a, quadrature_error_deg=error, formula_ratio=ratio,
                         coherent_ratio=coherent, chunk_ratio=chunk,
                         formula_minus_coherent=ratio-coherent, formula_minus_chunk=ratio-chunk,
                         chunk_main_power=main, chunk_conjugate_power=image,
                         chunk_pair_power=main+image, I_gain_RMS=a*np.sqrt(q_power),
                         Q_gain_RMS=np.sqrt(q_power),
                         I_ADC_RMS_V=a*np.sqrt(q_power*50e-9), Q_ADC_RMS_V=np.sqrt(q_power*50e-9)))
    return rows


def signed_pairs(rows):
    result = []
    for row in rows:
        opposite = [r for r in rows if r["mode"] == row["mode"]
                    and abs(r["input_IF_hz"]+row["input_IF_hz"])<1
                    and r["unaliased"]]
        if row["unaliased"] and len(opposite) == 1:
            mate, = opposite
            main, image = row["Hplus_power"], mate["conjugate_transfer_power"]
            result.append(dict(mode=row["mode"], output_IF_hz=row["input_IF_hz"],
                               main_input_run=row["run"], conjugate_input_run=mate["run"],
                               Hplus_power=main, Hminus_power=image, white_input_transfer_power=main+image,
                               same_tone_pair_transfer_power=row["pair_transfer_power"]))
    return result


def science(work):
    base = work/"simulation"
    step7 = read(base/"step7/central_iq_spectra/summary.json")
    step8 = read(base/"step8_LF_initial_20261116/metrics.json")
    intervals = read(base/"step7/dc_longterm_diagnostic/interval_results.json")["runs"]["680"]
    audit = read(work/"diagnostics/TM010_response_audit_20261115/audit.json")
    bands, diagnostics = [], []
    for mode in MODES:
        for b in step7["modes"][mode]["bands"]:
            lo, hi = b["band_hz"]
            bands.append(dict(mode=mode, low_hz=lo, high_hz=hi,
                              **{k:v for k,v in b.items() if k!="band_hz"}))
        q = intervals[mode]["distribution"]
        denom = q["var_I_ADC_V2"]+q["var_Qeff_ADC_V2"]
        re = (q["var_I_ADC_V2"]-q["var_Qeff_ADC_V2"])/denom
        im = 2*q["cov_IQ_ADC_V2"]/denom
        assert np.isclose(abs(complex(re,im)), q["pseudo_covariance_ratio"])
        m = step8["modes"][mode]
        diagnostics.append(dict(mode=mode, sample_count=q["samples"], pseudo_re_over_AC2=re,
                                pseudo_im_over_AC2=im, pseudo_abs_over_AC2=abs(complex(re,im)),
                                step8_science_min_ratio=m["data_shape_metrics"]["min_smoothed_ratio"],
                                step8_model_min_ratio=m["shape_metrics"]["min_smoothed_ratio"],
                                step8_science_width_hz=m["data_shape_metrics"]["full_half_deficit_width_hz"],
                                step8_model_width_hz=m["shape_metrics"]["full_half_deficit_width_hz"],
                                **audit["results"][mode]["band_ratios"]["50000"]))
    return bands, diagnostics


def figures(tones, details, pairs, bands):
    fig, axes = plt.subplots(3,2, figsize=(11,9), sharex=True)
    for mode, ax in zip(MODES, axes):
        rows = [r for r in tones if r["mode"]==mode and r["unaliased"]]
        fold = [r for r in pairs if r["mode"]==mode]
        f = [r["input_IF_hz"]/1e6 for r in rows]
        for key, label in (("Hplus_power","Principale"),("conjugate_transfer_power","Coniugato"),
                           ("pair_transfer_power","Somma dallo stesso tono")):
            ax[0].semilogy(f,[r[key] for r in rows],".",ms=4,label=label)
        for key, label in (("Hplus_power","Principale"),("white_input_transfer_power","Due IF d’ingresso")):
            ax[1].semilogy([r["output_IF_hz"]/1e6 for r in fold],[r[key] for r in fold],
                           ".",ms=4,label=label)
        ax[0].set(title=mode,ylabel="Potenza / potenza generatore")
        ax[1].set_title(mode+" · trasferimento PSD bianca")
    for ax in axes[-1]:
        ax.set_xlabel("IF firmata (MHz)")
    for ax in axes[0]:
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(HERE/"tone_transfer.png",dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8,4.7))
    checks = [r for r in details if r["mode"]=="TM010"]
    shoulders = [r for r in checks if abs(r["input_IF_hz"])>1e6]
    for key, label, color in (("I","I","#167b84"),("Q","Q","#9051a1")):
        field = key+"_gain_RMS"
        ref = np.mean([r[field]**2 for r in shoulders])
        ax.semilogx([abs(r["input_IF_hz"])/1e3 for r in checks],
                    [r[field]**2/ref for r in checks], "o", color=color,label=f"Tono {label} (entrambe le IF)")
        for j, b in enumerate(r for r in bands if r["mode"]=="TM010"):
            ax.hlines(b[key+"_power_over_own_plateau"],max(.2,b["low_hz"]/1e3),
                      b["high_hz"]/1e3,color=color,ls="--",label=f"Science {label} (media di banda)" if not j else None)
    ax.set(xlabel="|IF| (kHz)", ylabel="Potenza relativa alla propria spalla / plateau",
           title="TM010 · calibrazione e science con estimatori distinti",yscale="log")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(HERE/"tm010_quadratures.png",dpi=150)
    plt.close(fig)


def main(work, archive_dir):
    diag = work/"diagnostics"
    source = read(diag/"normalization_audit_20261114/calibration_reconstruction.json")
    audit = read(diag/"TM010_response_audit_20261115/raw_calibration_verified.json")
    tones = sweeps(source,audit,archive_dir)
    details = independent(audit)
    pairs = signed_pairs([r for r in tones if r["representative"]])
    bands, diagnostics = science(work)
    for name, rows in (("tones.csv",tones),("iq_checks.csv",details),("signed_pairs.csv",pairs),
                       ("science_bands.csv",bands),("science_diagnostics.csv",diagnostics)):
        save(name, rows)
    figures(tones,details,pairs,bands)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work",type=Path)
    parser.add_argument("archive_dir",type=Path)
    args = parser.parse_args()
    main(args.work,args.archive_dir)
