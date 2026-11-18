"""Short, periodic complex Gaussian realizations of Step 9D on its common mask."""
import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.fft import fft, ifft

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("step9d", ROOT/"docs/step9d/build.py")
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)
prior = ref.prior
FS = ref.FS
MODELS = ("H", "N")
TERMS = ref.TERMS
ORDERS = (-1, 0, 1)


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analytical(index, f, physical, gain, x, k):
    # Use the Step 9D source function at each unaliased analog coordinate.
    estimates = np.stack([
        [[result[key] for key in TERMS]
         for result in ref.analog(index, f+order*FS, physical, gain, x, k)]
        for order in ORDERS
    ], axis=1)
    mask = np.isfinite(estimates).all(axis=(0,1,2)) & (f>=x[0]) & (f<=x[-1])
    return estimates, mask


def verify_archive(index, physical, gain, x, k, old):
    """Re-evaluate the Step 9D grid as an oracle check, without using it for synthesis."""
    f = np.array([float(r["IF_hz"]) for r in old])
    p, mask = analytical(index, f, physical, gain, x, k)
    np.testing.assert_array_equal(mask, [r["common_mask"]=="1" for r in old])
    worst = 0.
    for model, name in enumerate(("hybrid", "nominal")):
        for order, values in (("", p[model,1]), ("_alias", p[model,0]+p[model,2])):
            for name_term, value in zip(TERMS, values):
                reported = np.array([float(r[f"{name}{order}_{name_term}"])
                                     if r[f"{name}{order}_{name_term}"] else np.nan for r in old])
                np.testing.assert_array_equal(np.isfinite(value), np.isfinite(reported))
                use = np.isfinite(value)
                np.testing.assert_allclose(value[use], reported[use], rtol=2e-7, atol=1e-25)
                nz = use & (reported>0)
                if nz.any():
                    worst=max(worst,float(np.max(abs(value[nz]/reported[nz]-1))))
    return worst


def integrate(model, realization, weight):
    expected = FS/model.size*np.sum(weight*model)
    measured = FS/model.size*np.sum(weight*realization)
    se = FS/model.size*np.linalg.norm(weight*model)
    return dict(expected_V2=expected, analog_V2=measured,
                expected_RMS_V=np.sqrt(expected), analog_RMS_V=np.sqrt(measured),
                expected_power_sample_sd_V2=se,
                z_score=(measured-expected)/se if se else 0.)


def validate_independence(coefficients, psd):
    n = psd.shape[-1]
    z_scores = []
    flat_coeff = coefficients.reshape(-1,n)
    flat_psd = psd.reshape(-1,n)
    for i in range(len(flat_coeff)):
        for j in range(i):
            cross = np.mean(flat_coeff[i]*np.conj(flat_coeff[j]))
            se = FS/n*np.sqrt(np.sum(flat_psd[i]*flat_psd[j]))
            if se:
                z_scores.append(float(abs(cross)/se))
            else:
                assert cross==0
    return max(z_scores,default=0.)


def synthesize(group, psd, draws, f, mask, cfg, centers):
    n = len(f)
    # unitary FFT coefficients have mean squared magnitude Fs*S for bilateral PSD S.
    coeff = np.sqrt(FS*psd)*draws
    components = ifft(coeff,axis=-1,norm="ortho")
    analog = components.sum(axis=(0,1))
    combined = coeff.sum(axis=(0,1))
    theory = psd.sum(axis=(0,1))
    realized = abs(combined)**2/FS
    expected_rms = np.sqrt(FS*np.mean(theory))
    np.testing.assert_allclose(fft(analog,norm="ortho"),combined,atol=1e-13,rtol=1e-11)
    power = np.mean(abs(analog)**2)
    np.testing.assert_allclose(power,FS*np.mean(realized),rtol=5e-14)
    np.testing.assert_allclose(np.mean(abs(components)**2,axis=-1),
                               np.mean(abs(coeff)**2,axis=-1),rtol=5e-14)
    assert np.count_nonzero(combined[~mask])==0 and abs(analog.mean())<1e-15
    lsb = 2*cfg["ADC_peak_V"]/(2**cfg["ADC_bits"]-1)
    signed = np.column_stack((analog.real,-analog.imag))
    rounded = np.rint(signed/lsb)
    bound = 2**(cfg["ADC_bits"]-1)
    clips = np.count_nonzero((rounded < -bound)|(rounded > bound-1))
    assert clips==0
    counts = rounded.astype(np.int16)
    assert np.max(abs(counts*lsb-signed)) <= lsb/2+1e-15
    adc = lsb*(counts[:,0].astype(float)-1j*counts[:,1].astype(float))
    quant_error = adc-analog
    adc_coeff = fft(adc,norm="ortho")
    adc_psd = abs(adc_coeff)**2/FS
    adc_power = np.mean(abs(adc)**2)
    np.testing.assert_allclose(adc_power,FS*np.mean(adc_psd),rtol=5e-14)
    error_power = np.mean(abs(quant_error)**2)
    assert abs(adc_power-power)<=2*np.sqrt(power*error_power)+error_power
    correlation_theory = ifft(theory)*FS
    correlation_adc = ifft(adc_psd)*FS
    correlation_analog = ifft(realized)*FS
    np.testing.assert_allclose(correlation_analog[0].real,power,rtol=5e-14)
    covariance = np.mean((analog-analog.mean())**2)
    covariance_adc = np.mean((adc-adc.mean())**2)
    mirror = (-np.arange(n))%n
    pseudo_se = FS/n*np.sqrt(2*np.sum(theory*theory[mirror]))
    power_metrics = integrate(theory,realized,np.ones(n))
    bands = []
    for offset,center in centers:
        taps = ref.TAPS*np.exp(2j*np.pi*center/FS*np.arange(len(ref.TAPS)))
        response_power = abs(fft(taps,n))**2
        row = integrate(theory,realized,response_power)
        measured = FS*np.mean(response_power*adc_psd)
        timedomain = ifft(adc_coeff*fft(taps,n),norm="ortho")
        np.testing.assert_allclose(np.mean(abs(timedomain)**2),measured,rtol=5e-14)
        bands.append(dict(offset_Hz=offset,center_IF_Hz=center,ADC_V2=measured,
                          ADC_RMS_V=np.sqrt(measured),**row))
    sources = []
    for i,order in enumerate(ORDERS):
        for j,term in enumerate(TERMS):
            sources.append(dict(alias_order=order,source=term,**integrate(
                           psd[i,j],abs(coeff[i,j])**2/FS,np.ones(n))))
    limit = cfg["stochastic_limit_sigma"]
    assert abs(covariance)/pseudo_se < limit
    cross_sigma = validate_independence(coeff,psd)
    assert cross_sigma < limit
    assert max(abs(r["z_score"]) for r in [power_metrics,*bands,*sources]) < limit

    for name, values in {
        "analog_components_V":components, "analog_sum_V":analog, "adc_counts_I_Qhardware":counts,
        "expected_component_PSD_V2_Hz":psd, "analog_psd_V2_Hz":realized,"adc_psd_V2_Hz":adc_psd,
        "acf_expected_V2":correlation_theory[:513], "acf_analog_V2":correlation_analog[:513],
        "acf_adc_V2":correlation_adc[:513],
    }.items():
        group.create_dataset(name,data=values,compression="lzf",shuffle=True)
    result = dict(**power_metrics, ADC_V2=adc_power, ADC_RMS_V=np.sqrt(adc_power),
                  adc_mean_I_V=float(adc.mean().real),adc_mean_Qhardware_V=float(-adc.mean().imag),
                  clips=int(clips),LSB_V=lsb,quantization_error_RMS_V=np.sqrt(error_power),
                  adc_outside_mask_fraction=FS*np.sum(adc_psd[~mask])/n/adc_power,
                  pseudo_real_V2=covariance.real,pseudo_imag_V2=covariance.imag,
                  normalized_pseudo_abs=abs(covariance)/power,normalized_adc_pseudo_abs=abs(covariance_adc)/adc_power,
                  pseudo_over_expected_sample_sd=abs(covariance)/pseudo_se,
                  max_source_cross_covariance_over_sample_sd=cross_sigma,
                  components=sources,bands=bands)
    results_plot(group.name.rsplit("/",2)[-2:],analog,adc,f,mask,theory,adc_psd,
                 correlation_theory,correlation_adc,expected_rms,Path(group.file.filename).parent)
    return result


def results_plot(label, analog, adc, f, mask, theory, adc_psd, ct, ca, rms, out):
    mode,model = label
    fig, ax = plt.subplots(2,3,figsize=(13,7),layout="constrained")
    inds = np.arange(180)
    for channel,color,name in ((adc.real,"#007F86","I"),(-adc.imag,"#7657A6","Q hardware")):
        ax[0,0].plot(inds/FS*1e6,channel[:len(inds)]*1e3,color=color,label=name,lw=.9)
    ax[0,0].set(xlabel="Time (µs)",ylabel="ADC (mV)",title="First 180 samples")
    ax[0,0].legend(fontsize=8)
    ax[0,1].scatter(adc.real[::67]*1e3,-adc.imag[::67]*1e3,s=2,alpha=.25,color="#007F86")
    ax[0,1].set(xlabel="I (mV ADC)",ylabel="Q hardware (mV ADC)",title="Constellation",aspect="equal")
    ax[0,2].hist(abs(adc)*1e3,bins=75,density=True,histtype="step",color="#007F86")
    v=np.linspace(0,5*rms,250)
    ax[0,2].plot(v*1e3,2*v/rms**2*np.exp(-v**2/rms**2)/1e3,color="#7657A6")
    ax[0,2].set(xlabel="|z| (mV ADC)",ylabel="Density (1/mV)",title="Amplitude and expected Rayleigh")
    ax[1,0].hist(np.angle(adc),bins=60,range=(-np.pi,np.pi),density=True,histtype="step",color="#007F86")
    ax[1,0].axhline(1/(2*np.pi),color="#7657A6")
    ax[1,0].set(xlabel="Phase of z (rad)",ylabel="Density (1/rad)",title="Phase and uniform expectation")
    x, ok, a, t = map(np.fft.fftshift,(f,mask,adc_psd,theory))
    for keep in (ok & (x<0),ok & (x>0)):
        freq, meas, expected = x[keep],a[keep],t[keep]
        end=(len(freq)//128)*128
        means=lambda v: v[:end].reshape(-1,128).mean(axis=1)
        ax[1,1].semilogy(means(freq)/1e6,means(meas),color="#007F86",lw=.8)
        ax[1,1].semilogy(means(freq)/1e6,means(expected),color="#7657A6",lw=1)
    ax[1,1].axvspan(-.1,.1,color=".92")
    ax[1,1].set(xlabel="Signed IF (MHz)",ylabel="PSD (V²/Hz ADC)",title="128-bin averages, common mask")
    lag = np.arange(121)/FS*1e6
    for value, style, color in ((ca,"-","#007F86"),(ct,"--","#7657A6")):
        normalized=value[:len(lag)]/value[0]
        ax[1,2].plot(lag,normalized.real,ls=style,color=color,lw=.9)
        ax[1,2].plot(lag,normalized.imag,ls=style,color=color,lw=.7,alpha=.5)
    ax[1,2].set(xlabel="Lag (µs)",ylabel="Normalized complex ACF",title="Real and imaginary lag response")
    fig.suptitle(f"{mode} · Model {model} | Quantized realization (teal) and expectation (purple)")
    fig.savefig(out/f"{mode}_{model}.png",dpi=130)
    plt.close(fig)


def bands_for(mode, entries):
    bands=sorted((r for r in entries if r["mode"]==mode and r["region"]=="FIR"),
                 key=lambda r:float(r["offset_hz"]))
    assert len(bands)==7
    return [(float(r["offset_hz"]),float(r["center_IF_hz"])) for r in bands]


def run(work, out, config):
    cfg=load(config)
    n=cfg["samples"]
    assert cfg["fs_Hz"]==FS and cfg["ADC_bits"]==16 and tuple(cfg["alias_orders"])==ORDERS
    assert n>=len(ref.TAPS) and n%2==0
    f=np.fft.fftfreq(n,1/FS)
    cal=work/"diagnostics/normalization_audit_20261114/calibration_reconstruction.json"
    phys=work/"simulation/step6/metrics.json"
    toy=work/"simulation/toy_ODB_cal5_data2_LF_20261116/metrics.json"
    checkpoints={Path(k).name:v for k,v in load(toy)["input_sha256"].items()}
    assert all(sha(p)==checkpoints[p.name] for p in (cal,phys))
    source,phy=load(cal),load(phys)["mode_results"]
    fits=ROOT/"docs/step9a/vna/fits.csv"
    grid=ROOT/"docs/step9d/psd.csv"
    integrals=ROOT/"docs/step9d/integrals.csv"
    old=prior.csv_read(grid)
    band_entries=prior.csv_read(integrals)
    gains={r["mode"]:float(r["L5_dB"])+36 for r in prior.csv_read(fits) if r["fit"]=="free_eq69"}
    out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(config,out/"config.json")
    metrics=dict(configuration=cfg,input_sha256={str(p):sha(p) for p in (cal,phys,fits,grid,integrals,
                 ROOT/"docs/step9d/build.py",ROOT/"docs/step9c/build.py",ROOT/"docs/step9b/build.py",
                 ROOT/"docs/step9b/manufacturer.json")},
                 convention="z = I - i Qhardware; bilateral complex PSD; periodic masked realization",
                 modes={})
    with h5py.File(out/"series.h5","w") as h:
        h.attrs["source_order"]=json.dumps(TERMS)
        h.attrs["alias_order"]=json.dumps(ORDERS)
        h.attrs["fs_Hz"]=FS
        h.attrs["ADC_lsb_V"]=2*cfg["ADC_peak_V"]/(2**cfg["ADC_bits"]-1)
        h.create_dataset("signed_IF_Hz",data=f)
        for i,mode in enumerate(prior.MODES):
            x,k=prior.curve(source,mode)
            err=verify_archive(i,phy[mode],gains[mode],x,k,[r for r in old if r["mode"]==mode])
            estimates,mask=analytical(i,f,phy[mode],gains[mode],x,k)
            assert np.array_equal(mask,abs(f)>=100000)
            assert np.all(estimates[...,mask]>=0)
            # Mask acts on both models as a diagnostic frequency projection.
            estimates[...,~mask]=0
            group=h.create_group(mode)
            group.create_dataset("common_spectral_mask",data=mask)
            centers=bands_for(mode,band_entries)
            rng=np.random.default_rng(np.random.SeedSequence([cfg["seed"],i]))
            shape=(len(ORDERS),len(TERMS),n)
            draws=(rng.standard_normal(shape)+1j*rng.standard_normal(shape))/np.sqrt(2)
            lo=prior.SCI["LO1_MHz"]+prior.SCI["LO2_MHz"][i]
            metrics["modes"][mode]=dict(RF_gain_dB=gains[mode],LO1_MHz=prior.SCI["LO1_MHz"],
                                     LO2_MHz=prior.SCI["LO2_MHz"][i],
                                     thermal_IF_Hz=phy[mode]["f0_hz"]-round(lo*1e6),
                                     mask_bins=int(mask.sum()),mask_fraction=mask.mean(),
                                     legacy_grid_max_relative_error=err,
                                     models={model:synthesize(group.create_group(model),estimates[j],
                                             draws,f,mask,cfg,centers) for j,model in enumerate(MODELS)})
            print(f"{mode}: analytical and numerical checks passed",flush=True)
    (out/"metrics.json").write_text(json.dumps(metrics,indent=2,allow_nan=False)+"\n")
    return metrics


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--config",type=Path,default=HERE/"config.json")
    args=parser.parse_args()
    run(args.work,args.output,args.config)
