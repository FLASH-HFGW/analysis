"""Compare independent nominal and kz-hybrid PSDs on the archived run-680 grid."""
import argparse
import hashlib
import importlib.util
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import firwin

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("step9c", HERE.parent / "step9c/build.py")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
FS = prior.FS
TAPS = firwin(2001, 25000, fs=FS, window=("kaiser", 8.6))
TERMS = ("main", "image", "cavity")
COLORS = {"observed": "#202633", "hybrid": "#6a47a0", "nominal": "#147d83"}


def write(name, rows):
    # Use the shared numeric CSV convention, with nonfinite fields empty.
    prior.write_csv(HERE/name, rows)


def analog(mode, f, physical, gain_db, x, k):
    main = prior.response(prior.SCI, mode, f)
    image = prior.response(prior.SCI, mode, f, -1) if mode else None
    nominal_main = 10**(main["summed_IQ_dB"]/10)
    nominal_image = 10**(image["summed_IQ_dB"]/10) if mode else np.zeros_like(f)
    hybrid_main = (np.interp(f, x, k, left=0, right=0)*.01)**2
    ratio = prior.image_ratio(mode, main, image)
    hybrid_image = np.where(hybrid_main == 0, 0, hybrid_main*ratio)
    kappa_i = 2*np.pi*physical["f0_hz"]/physical["q0"]
    kappa_t = kappa_i*(1+physical["kappa1"]+physical["kappa2"])
    lo = prior.SCI["LO1_MHz"]+prior.SCI["LO2_MHz"][mode]
    center = physical["f0_hz"]-round(lo*1e6)
    photon = prior.HPLANCK*physical["f0_hz"]
    theta = photon/np.expm1(photon/(prior.KB*physical["temperature_k"]))
    wall = theta*kappa_i**2*physical["kappa2"]/((kappa_t/2)**2+(2*np.pi*(f-center))**2)
    factor = prior.R*10**(gain_db/10)
    electronic = factor*prior.KB*3.955

    def components(main_power, image_power):
        return dict(main=electronic*main_power, image=electronic*image_power,
                    cavity=factor*wall*main_power)

    return components(hybrid_main, hybrid_image), components(nominal_main, nominal_image)


def predict(mode, f, physical, gain, x, k):
    hybrid, nominal = analog(mode, f, physical, gain, x, k)
    hybrid_alias = {key: np.zeros_like(f) for key in TERMS}
    nominal_alias = {key: np.zeros_like(f) for key in TERMS}
    nominal_alias_on_kz = {key: np.zeros_like(f) for key in TERMS}
    for m in (-1, 1):
        af = f+m*FS
        ah, an = analog(mode, af, physical, gain, x, k)
        in_kz = (x[0] <= af) & (af <= x[-1])
        for key in TERMS:
            hybrid_alias[key] += ah[key]
            nominal_alias[key] += an[key]
            nominal_alias_on_kz[key] += np.where(in_kz, an[key], 0)
    tail = {key: np.zeros_like(f) for key in TERMS}
    tail_known = np.zeros(len(f), dtype=int)
    lpf_max = prior.HW["BLP-1.9+"]["f_MHz"][-1]*1e6
    max_order = int(np.floor(lpf_max/FS+.5))
    for m in range(-max_order, max_order+1):
        if abs(m) <= 1:
            continue
        _, values = analog(mode, f+m*FS, physical, gain, x, k)
        known = np.logical_and.reduce([np.isfinite(values[key]) for key in TERMS])
        tail_known += known
        for key in TERMS:
            tail[key][known] += values[key][known]
    return dict(hybrid=hybrid, nominal=nominal, hybrid_alias=hybrid_alias,
                nominal_alias=nominal_alias, nominal_alias_on_kz=nominal_alias_on_kz,
                nominal_supported_tail=tail), tail_known


def evidence(work):
    path = work/"diagnostics/TM010_response_audit_20261115/raw_calibration_verified.json"
    archive = prior.json_read(path)
    rows = []
    for mode, records in archive["curves"].items():
        for r in records:
            rows.append(dict(mode=mode, estimator="archived_spectrum", run=r["run"],
                             input_IF_hz=r["input_IF_hz"], output_peak_IF_hz=r["peak_IF_hz"],
                             image_main_power=r["image_to_main_power"],
                             I_over_Q_amplitude="", quadrature_phase_error_deg=""))
    for r in archive["raw_calibration_checks"]:
        rows.append(dict(mode=r["mode"], estimator="archived_raw_check", run=r["run"],
                         input_IF_hz=r["input_IF_hz"], output_peak_IF_hz=r["fitted_tone_IF_hz"],
                         image_main_power=r["raw_chunk_image_to_main_power"],
                         I_over_Q_amplitude=r["tone_I_over_Q_amplitude"],
                         quadrature_phase_error_deg=r["quadrature_phase_error_deg"]))
    return rows


def plot_tones(rows):
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6), sharey=True)
    for mode, ax in zip(prior.MODES, axes):
        for source, marker, label in (("archived_spectrum", ".", "Sweep FFT archiviato"),
                                      ("archived_raw_check", "x", "Verifica indipendente archiviata")):
            selected = [r for r in rows if r["mode"] == mode and r["estimator"] == source
                        and abs(r["input_IF_hz"]) < 2.5e6]
            ax.plot([r["input_IF_hz"]/1e6 for r in selected],
                    [prior.pow_db(r["image_main_power"]) for r in selected],
                    marker, label=label)
        ax.set(title=mode, xlabel="IF analogica del tono (MHz)")
    axes[0].set_ylabel("Coniugato / principale (dB di potenza)")
    axes[-1].legend(fontsize=7, loc="upper right")
    fig.tight_layout()
    fig.savefig(HERE/"tone_audit.png", dpi=150)
    plt.close(fig)


def main(work, archive_path):
    diag = work/"diagnostics"
    source = prior.json_read(diag/"normalization_audit_20261114/calibration_reconstruction.json")
    physics = prior.json_read(work/"simulation/step6/metrics.json")["mode_results"]
    validation = prior.json_read(diag/"frequency_sensor_closure_v47_20261117/verification.json")
    assert 680 in validation["controls"] and 680 not in validation["corrected_runs"]
    record, = (r for r in validation["execution_provenance"] if r["run"] == 680)
    archive_digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    assert record["iq_sign"] == -1 and record["artifact_identical"]
    assert archive_digest == record["archive_sha256"]
    prior_comparison = prior.csv_read(HERE.parent/"step9a/comparison.csv")
    gains = {r["mode"]:float(r["L5_dB"])+36 for r in
             prior.csv_read(HERE.parent/"step9a/vna/fits.csv") if r["fit"]=="free_eq69"}
    powers, details, cables = [], [], []
    fig, axes = plt.subplots(3, 2, figsize=(12, 9), sharex=True)
    with np.load(archive_path) as archive:
        assert float(archive["fs"]) == FS and int(archive["n_fft_done"]) == 1000
        for i, mode in enumerate(prior.MODES):
            measured = np.fft.ifftshift(archive[f"fft_amp_mode{i}_SPECs"].astype(float))
            n = len(measured)
            assert n == 16383 and np.isfinite(measured).all() and (measured >= 0).all()
            f = np.fft.fftfreq(n, 1/FS)
            window = np.hanning(n)
            enbw = FS*np.sum(window**2)/window.sum()**2
            measured *= (2/5)**2/enbw
            x, k = prior.curve(source, mode)
            parts, tail_known = predict(i, f, physics[mode], gains[mode], x, k)
            models = {}
            for name in ("hybrid", "nominal"):
                models[name] = sum(parts[name].values()) + sum(parts[name+"_alias"].values())
            known = np.isfinite(models["hybrid"]) & np.isfinite(models["nominal"]) & (f>=x[0]) & (f<=x[-1])
            assert known.any() and not known.all()
            total_nominal_tail = sum(parts["nominal_supported_tail"].values())
            on_kz = sum(parts["nominal"].values())+sum(parts["nominal_alias_on_kz"].values())
            ix = np.argsort(f)
            for j in ix:
                details.append(dict(mode=mode, IF_hz=f[j], common_mask=int(known[j]),
                                    observed_ADC_V2_per_Hz=measured[j],
                                    nominal_tail_supported_order_count=tail_known[j],
                                    **{group+"_"+term: values[term][j]
                                       for group,values in parts.items() for term in TERMS}))
            for r in (row for row in prior_comparison if row["mode"]==mode):
                full = r["region"] == "full"
                center = None if full else float(r["center_IF_hz"])
                weight = (np.ones(n) if full else
                          abs(np.fft.fft(TAPS*np.exp(2j*np.pi*center/FS*np.arange(TAPS.size)),n))**2)
                observed_full = np.dot(weight,measured)*FS/n
                if not full:
                    assert np.isclose(observed_full, float(r["run680_V2"]), rtol=1e-8)
                w = weight[known]*FS/n
                def integrate(y):
                    return np.dot(w,y[known])
                obs = integrate(measured)
                hy = integrate(models["hybrid"])
                nom = integrate(models["nominal"])
                powers.append(dict(mode=mode, region=r["region"], offset_hz=r["offset_hz"],
                                   center_IF_hz=r["center_IF_hz"], known_bin_fraction=known.mean(),
                                   FIR_weight_covered=weight[known].sum()/weight.sum(),
                                   observed_full_V2=observed_full, observed_common_V2=obs,
                                   observed_common_RMS_V=np.sqrt(obs),
                                   hybrid_common_V2=hy, nominal_common_V2=nom,
                                   hybrid_common_RMS_V=np.sqrt(hy), nominal_common_RMS_V=np.sqrt(nom),
                                   nominal_over_hybrid_dB=prior.pow_db(nom/hy),
                                   data_over_hybrid_dB=prior.pow_db(obs/hy),
                                   data_over_nominal_dB=prior.pow_db(obs/nom),
                                   nominal_using_kz_alias_support_V2=integrate(on_kz),
                                   nominal_higher_alias_resolved_V2=integrate(total_nominal_tail),
                                   **{group+"_"+term+"_V2":integrate(values[term])
                                      for group,values in parts.items() for term in TERMS}))
                for loss in (0,.5,1,1.5,2):
                    scale = 10**(loss/10)
                    cables.append(dict(mode=mode, region=r["region"], offset_hz=r["offset_hz"],
                                       diagnostic_loss_dB=loss, hybrid_on_Marki_plane_V2=hy*scale,
                                       data_over_shifted_hybrid_dB=prior.pow_db(obs/(hy*scale)),
                                       nominal_V2=nom))
            for name, values in {"observed":measured, **models}.items():
                axes[i,0].semilogy(f[ix]/1e6,np.where(known,values,np.nan)[ix],lw=.9,
                                   color=COLORS[name], label=name)
            for name in ("hybrid","nominal"):
                for term, style in zip(TERMS, ("-", "--", ":")):
                    y = parts[name][term]
                    axes[i,1].semilogy(f[ix]/1e6,np.where(known,y,np.nan)[ix],
                                      color=COLORS[name],ls=style,lw=.9,label=f"{name} {term}")
                alias = parts[name+"_alias"]["main"]+parts[name+"_alias"]["image"]
                axes[i,1].semilogy(f[ix]/1e6,np.where(known,alias,np.nan)[ix],
                                  color=COLORS[name],ls="-.",lw=.9,label=f"{name} alias elettronici")
            for ax in axes[i]:
                ax.set(title=mode,ylabel="PSD ADC (V²/Hz)",xlim=(-2.5,2.5))
        for ax in axes[-1]:
            ax.set_xlabel("IF finale firmata (MHz)")
        axes[0,0].legend(fontsize=8)
        axes[0,1].legend(ncol=2,fontsize=7)
    fig.tight_layout()
    fig.savefig(HERE/"comparison.png",dpi=150)
    write("integrals.csv",powers)
    write("psd.csv",details)
    write("cable_sensitivity.csv",cables)
    tones = evidence(work)
    write("tone_audit.csv",tones)
    plot_tones(tones)
    print("run680 archive SHA-256:",archive_digest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work",type=Path)
    parser.add_argument("archive",type=Path)
    args = parser.parse_args()
    main(args.work,args.archive)
