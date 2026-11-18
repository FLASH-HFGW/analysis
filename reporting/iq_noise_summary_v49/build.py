"""Consolidate the immutable v48 presentation and append Parts V–VII."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

import h5py
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pptx import Presentation

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"reporting/iq_noise_summary_v48"))
spec=importlib.util.spec_from_file_location("frozen_v48",ROOT/"reporting/iq_noise_summary_v48/build.py")
frozen=importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen)
from figures import make_figures as v48_figures

sd=frozen.sd
MODES=("TM010","TM011","TM012")
POPS=("data","H","N")
COLORS=("#007f86","#7657a6","#d98726")
NAMES=("Run 680","Hybrid H","Nominal N")
START=65
V48_HASH={
    "pdf":"f06133c4937c85ee38ce25501922828dfef792a19e4c44289f9acaf461a1aaa9",
    "pptx":"b86e79be215bc3e276c1d7bc955e031c39517fe3e699e076248773da677c7adb",
}


def sha(p):
    d=hashlib.sha256()
    with p.open("rb") as s:
        for b in iter(lambda:s.read(2**20),b""):
            d.update(b)
    return d.hexdigest()


def read(p):
    with p.open(newline="") as stream:
        return list(csv.DictReader(stream))


def write(p,rows):
    with p.open("w",newline="") as stream:
        w=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def curves(work,out):
    p=work/"simulation/step10c/statistics.h5"
    fig,ax=plt.subplots(2,3,figsize=(13,5.2),layout="constrained")
    sampled=[]
    with h5py.File(p) as h:
        f=np.fft.fftshift(h["frequency_Hz"][:])
        mask=np.fft.fftshift(h["common_mask"][:])
        for j,m in enumerate(MODES):
            for pop,label,col in zip(POPS,NAMES,COLORS):
                g=h[f"mean/{m}/{pop}/full"]
                s=np.fft.fftshift(g["PSD"][:])
                for left,select in enumerate((mask&(f<0),mask&(f>0))):
                    ix=np.flatnonzero(select)
                    ix=ix[:len(ix)//128*128].reshape(-1,128)
                    x,y=f[ix].mean(axis=1),s[ix].mean(axis=1)
                    ax[0,j].semilogy(x/1e6,y,color=col,label=label if left==0 else None)
                    sampled.extend(dict(mode=m,population=pop,observable="PSD_V2_Hz",x_Hz=x0,value=y0)
                                   for x0,y0 in zip(x,y))
                a=g["acf"][:101]
                for v,style,name in ((a.real,"-","Re"),(a.imag,"--","Im"),(abs(a),":","abs")):
                    x=np.arange(len(v))/5
                    ax[1,j].plot(x,v,style,color=col,lw=.95)
                    sampled.extend(dict(mode=m,population=pop,observable="ACF_"+name,x_Hz="",value=y0,lag_us=x0)
                                   for x0,y0 in zip(x,v))
            ax[0,j].set(title=m,xlabel="Signed IF (MHz)")
            ax[1,j].set(xlabel="Lag (µs)",xlim=(0,15))
    ax[0,0].set_ylabel("PSD (V²/Hz ADC)")
    ax[1,0].set_ylabel("Complex ACF: Re / Im / modulus")
    ax[0,0].legend(fontsize=8)
    for row in sampled:
        row.setdefault("lag_us","")
    write(out/"fullrun_PSD_ACF_data.csv",sampled)
    for ext in ("png","pdf"):
        fig.savefig(out/f"fullrun_PSD_ACF.{ext}",dpi=200)
    plt.close(fig)
    return out/"fullrun_PSD_ACF.png"


def band_figure(out):
    data=read(ROOT/"docs/step10c/observables.csv")
    vals=[r for r in data if r["observable"]=="RMS_aggregate_V" and r["band"]!="full"]
    fig,axs=plt.subplots(1,3,figsize=(12,3.6),layout="constrained")
    for m,ax in zip(MODES,axs):
        for p,label,c in zip(POPS,NAMES,COLORS):
            sel=sorted((r for r in vals if r["mode"]==m and r["population"]==p),key=lambda r:int(r["band"]))
            ax.errorbar([float(r["band"])/1000 for r in sel],[float(r["mean"])*1000 for r in sel],
                        yerr=[float(r["cluster_SE"])*1000 for r in sel],fmt="o-",color=c,label=label,ms=4)
        ax.set(title=m,xlabel="Offset from resonance (kHz)",ylabel="Aggregate RMS (mV ADC)")
    axs[0].legend(fontsize=8)
    for ext in ("png","pdf"):
        fig.savefig(out/f"fullrun_bands.{ext}",dpi=200)
    plt.close(fig)
    write(out/"fullrun_bands_data.csv",vals)
    return out/"fullrun_bands.png"


def slides(physics,figs,work):
    deck=sd.Deck()
    ledger=[]
    index=[]

    def page(part,title,subtitle,notes,src):
        n=START+len(deck.slides)+1
        s=deck.new(title,subtitle,"Source details and SHA-256 are listed in the v49 slide/observable ledger.",notes)
        s["footer"]=f"HFGW | v49 | {part}"
        for obs,path,selection in src:
            ledger.append(dict(slide=n,title=title,observable=obs,file=str(path),selector=selection,sha256=sha(path),
                               limitation=notes))
        return s

    def txt(s,y,lines,size=17):
        for t in lines:
            h=max(.34,len(sd.wrap(t,12,size).splitlines())*size*1.15/72+.06)
            deck.text(s,.65,y,12,h,t,size)
            y+=h+.13
        assert y<=6.98,(s["title"],y)

    def table(s,y,headers,data,widths,size=15,step=.52):
        for j,row in enumerate((headers,*data)):
            x=.65
            for val,w in zip(row,widths):
                deck.text(s,x,y+j*step,w-.08,step,str(val),size,j==0,sd.NAVY if j==0 else sd.INK)
                x+=w

    def graph(s,asset,sources,meaning,limits,y=1.58,h=4.85):
        deck.image(s,.52,y,12.3,h,asset)
        index.append(dict(file=asset.name,title=s["title"],result=meaning,
                          numerical_source=sources,limitations=limits,slide=START+len(deck.slides),
                          shortlist_20min=int(asset.stem in ("fullrun_bands","fullrun_PSD_ACF","eta","strain_asd","fast","reach"))))

    def d(name):
        return ROOT/"docs"/name

    def q(name):
        return physics/(name+".csv")

    A=d("step10c/observables.csv")
    C=d("step10c/spectral_closure.csv")
    I=d("step10d/eta_intervals.csv")
    P=d("step10d/high_IF_components.csv")
    T=d("step10c/tail_counts.csv")
    V="PART V · UPDATED NOISE MODEL AND STATISTICAL VALIDATION"
    VI="PART VI · PRELIMINARY HFGW SENSITIVITY AND ASTROPHYSICAL BENCHMARKS"
    VII="PART VII · CONCLUSIONS AND FUTURE DEVELOPMENTS"
    params=read(q("apparatus"))
    mono=read(q("monochromatic"))
    bench=read(q("benchmarks"))

    s=page(V,"Part V — Updated noise model","The readout alternatives share independently established RF inputs",
           "Proper Gaussian stationary independent generators in disjoint bands. Equal RF image and main PSD is a conditional assumption. Parameters remain frozen.",
           [("H and N transfer budgets",d("step9d/README.md"),"Due catene analitiche"),("Time-domain validation configuration",d("step10a/README.md"),"Physical model and mask")])
    txt(s,1.85,["H: measured integrated kz × 0.01 in amplitude. Nominal image/main power ratio for secondary folding.",
                 "N: nominal absolute direct and secondary-image hardware transfer. No kz normalization.",
                 "Both use modal VNA L5, a nominal 36 dB FET, Tn = 3.955 K and the physical cavity thermal poles.",
                 "RF PSD equality across the main and image bands is unverified. The noise PSD includes ADC aliases from orders 0 and ±1.",
                 "A scalar power response does not determine a complex I/Q transfer matrix."])

    s=page(V,"Common selection for data and simulations","Step 10A verifies synthesis. Steps 10B and 10C apply the same selection after digitization.",
           "Here filtering refers to diagnostic spectral projection, not to an astrophysical matched filter. Periodic block projection removes DC and the excluded band.",
           [("Six short ADC checks",d("step10a/validation.csv"),"six mode/model rows, expected and ADC RMS"),("Full-run observed and modeled population",work/"simulation/step10c/population.json","samples, mask, estimators"),("Block comparison",d("step10b/README.md"),"Popolazione; Proiezione")])
    graph(s,figs/"step10a_validation.png","Step 10A validation.csv","Short H/N simulations pass the analytical power checks.","One realization per mode/model",1.56,3.3)
    txt(s,4.97,["First test: 262144 samples at 5 MS/s, one ADC rounding after analog summation. RMS agreement within 0.16%.",
                 "Full run: 1000 SPEC × 4 blocks = 1,048,576,000 complex samples per mode and population.",
                 "Same post-ADC support |IF| ≥ 100 kHz. Statistics are grouped in 20-SPEC clusters, with a 40-SPEC sensitivity check."],14)

    s=page(V,"N is closer in absolute ADC power","All seven resonance FIR bands retain an excess in the selected science population",
           "Bars are descriptive grouped SE, not independent ADC sample errors. The seven centers use Step 10C signed BOR coordinates. Aggregate RMS is sqrt(mean block power).",
           [("Absolute FIR RMS and SD",A,"RMS_aggregate_V, cluster_SE; seven FIR bands"),("Absolute full-run results",d("step10c/results.md"),"aggregate and mean block RMS")])
    graph(s,figs/"fullrun_bands.png","Step 10C observables.csv","N is closer in all seven bands for each mode.","Masked block FIR, not legacy unmasked FIR",1.64,3.7)
    txt(s,5.47,["Full-band aggregate RMS (mV ADC), data/H/N: 31.728/26.604/27.229, 20.328/17.383/18.271, 13.453/10.877/11.660.",
                 "Central data/N power excess: +0.829/+0.465/+0.770 dB. All 21 band residuals remain below 1 dB."],14)

    s=page(V,"H better preserves spectral shape and complex ACF","Absolute PSD and first-lag covariance expose different strengths of H and N",
           "The linear finite-record ACF is checked against the IFFT of the PSD with the endpoint wrap term removed. Full spectra remain in local Step 10C HDF5.",
           [("Bilateral PSD and complex ACF",work/"simulation/step10c/statistics.h5","mean/{mode}/{population}/full/PSD and acf"),("First-lag spectral decomposition",d("step10c/spectral_intervals.csv"),"lag1_Re_over_full_power"),("Closure errors",C,"ACF_max_closure_error_V2 and lag1_Re_linear")])
    graph(s,figs/"fullrun_PSD_ACF.png","Step 10C HDF5; fullrun_PSD_ACF_data.csv","H reproduces signed covariance more closely.","No interpretation of missing LF response",1.58,4.3)
    txt(s,6.02,["Re g₁(0.2 µs) is −0.061/−0.052/−0.052 in data, negative in H and positive in N. The edge from 1.75–2.50 MHz drives most of the H–N difference."],14)

    s=page(V,"Near-Rayleigh amplitude coexists with I/Q impropriety","Shape averages and covariance probe different properties",
           "Circular phase increments are compared at lags 1, 10, 100. One-dimensional Rayleigh agreement does not establish circularity. Complex z sign is hardware-convention I minus iQ.",
           [("Rayleigh and phase distances",d("step10c/distribution_diagnostics.csv"),"band=full; amplitude/phase/IQ diagnostics"),("I/Q moments, phase and increments",A,"var_I_V2,var_Qhardware_V2, covariances, phase/increments"),("Run-680 distribution figure",work/"simulation/step10c/TM010_distributions.png","approved aggregate I/Q, phase and absolute amplitude")])
    graph(s,figs/"TM010_distributions.png","Step 10C aggregated histograms","TM010 joint shape differs despite a near-Rayleigh amplitude.","Block-normalized I/Q and fixed nominal absolute reference shown separately",1.58,4.12)
    txt(s,5.83,["Data amplitude CDF distances are ≤4.47×10⁻⁴ after shape normalization. Signed pseudo / power is ≈−0.025…−0.036 − i(0.030…0.032). Proper toys average close to zero."],14)

    s=page(V,"Complementary spectrum varies across IF","I/Q covariance gives equivalent diagnostics, while constant mixing fails",
           "Equivalent angles are diagnostic moments, not calibrated transfer. Across frequencies the real part varies substantially while the imaginary part is nearly flat with a resolved TM010 edge shift.",
           [("η intervals and grouped spread",I,"exact bins and paired cluster uncertainty"),("Equivalent covariance angles",d("step10d/iq_covariance.csv"),"data; equivalent_phase_error_hardware_deg"),("Constant real-linear map test",d("step10d/constant_map.csv"),"symmetric PSD variation and η")])
    graph(s,figs/"eta.png","Step 10D complementary intervals and binned η","Real η varies strongly, imaginary η is nearly flat.","No complex transfer inferred",1.54,4.40)
    txt(s,6.04,["Equivalent quadrature errors: −1.82°, −1.72°, −1.76°. A constant map on proper H or N would give constant η and preserve symmetric PSD shape."],14)

    s=page(V,"High-IF residuals and rare excursions","Separate model alias attribution from the measured ADC total",
           "Tail counts and episode lengths are conditional on the block projection. No trials or trigger interpretation. Alias attribution is within predictions, not a measured decomposition.",
           [("Resolved high-IF contributions",P,"1.75–2.50 and 2.25–2.50 MHz"),("Threshold fractions, dispersion and episodes",T,"full and FIR; shape and fixed thresholds 2–5 RMS"),("Finite sample tails",d("step10c/results.md"),"5 RMS counts and residuals")])
    graph(s,figs/"high_IF.png","Step 10D high-IF components; Step 9B BLP table","High-IF science is flatter than N.","Loaded BLP phase, ADC analog filtering and aliases are not independently measured",1.59,3.05)
    txt(s,4.71,["ADC aliases explain 51% / 62% / 78% of integrated H–N separation at 1.75–2.50 MHz. Data/N reaches about 5 dB at the highest interval.",
                 "Through 4 block RMS the observed counts are broadly consistent with the proper model populations at the available resolution.",
                 "At 5 RMS: no shape exceedances in data. Fixed N thresholds give 6/3/7 samples, insufficient for a fraction. Episodes are separately censored at block edges."],14)

    s=page(VI,"Part VI — Preliminary HFGW sensitivity","QUAX GHz geometry and run-680 noise | a conditional normalization",
           "Spasiano Chapters 3, 6, 7 and GravNet Eq. 7. The run-680 BOR did not independently establish the magnet state.",
           [("QUAX geometry, mode and RF parameters",q("apparatus"),"all rows"),("Thesis and GravNet provenance",physics/"thesis_and_BOR_evidence.json","geometry, field, BOR inspection and unavailable overlaps")])
    table(s,1.86,("Mode","RF (GHz)","Loaded Q","Bandwidth (kHz)","Readout fraction"),
          [(r["mode"],f'{float(r["RF_Hz"])/1e9:.6f}',f'{float(r["QL"]):.0f}',
            f'{float(r["bandwidth_Hz"])/1e3:.1f}',f'{float(r["kappa2_over_total"]):.4f}') for r in params],
          (1.6,2.1,2,3,3),15)
    txt(s,4.30,["Thesis geometry: 0.139 L with tuning rod. Central 8.5 T and 6.73 T RMS are thesis reference values.",
                 "Pport = K h², K = readout fraction × ω B² QL C_GW V / (2 μ₀). C_GW depends on mode, sky direction and polarization.",
                 "The numerical sky grids and run-specific field state were not recovered. C_GW = 0.01 is an explicit reference, not a measured QUAX coupling."],15)

    s=page(VI,"Equivalent strain from measured ADC noise","The measured noise PSD is divided by the coherent direct-path response",
           "ADC PSD is signed complex bilateral. One-sided real narrowband equivalent ASD is the plotted complex ASD divided by sqrt(2), in the stated physical peak-tone convention. No signal folding gain is used.",
           [("ASD versus physical RF",q("strain_asd"),"both calibrated magnitude hypotheses; common mask"),("Conversion equations and planes",ROOT/"simulation/v49_hfgw/README.md","Strain conversion and normalization")])
    graph(s,figs/"strain_asd.png","strain_asd.csv","Mode-dependent ASD referred to coherent port response.","Reference C_GW and B; only supported first-Nyquist direct template",1.64,3.85)
    txt(s,5.57,["ASD = √S_ADC / |√(50 Ω × RF power gain × K) H_direct L|. Noise includes observed alias and image terms. Coherent signal leakage and aliased contributions are outside the template.",
                 "Thresholds scale as 6.73 T/B × √(0.01/C_GW) × √(0.139 L/V). A direction null removes sensitivity."],14)

    s=page(VI,"Monochromatic sensitivity at fixed coherent time","A known-phase ideal matched statistic | amplitude SNR ρ",
           "ρ²=2∫|s̃|²/Sz df for the known real template amplitude and proper noise. A rectangular coherent average has ENBW 1/T. No detection probability or statistical trials correction.",
           [("Coherent time scaling and local PSD statistics",q("monochromatic"),"seconds, ENBW, center ASD, h_rho1 and h_rho5")])
    graph(s,figs/"monochromatic.png","monochromatic.csv","Threshold decreases as T⁻¹/² under coherent assumptions.","209.7152 s is equivalent acquired time, not a verified continuous coherence interval",1.65,3.58)
    lines=[]
    for m in MODES:
        rr=[r for r in mono if r["mode"]==m and float(r["seconds"])==1.]
        lines.append(m+" · 1 s ρ=1 H/N: "+" / ".join(f'{float(r["h_rho1_white_center"]):.3g}' for r in rr))
    txt(s,5.35,lines,14)

    s=page(VI,"Transient sensitivity includes cavity dynamics","Rectangular strain envelope at resonance, filtered over known IF support",
           "Duration pulses use exact transform T sinc(νT), weighted by the causal cavity magnitude and the measured PSD. Time-domain phase is conditional on the readout hypothesis.",
           [("Rectangular pulse sensitivity",q("transient"),"both models; 1 ns–10 ms"),("Normalization and phase assumptions",ROOT/"simulation/v49_hfgw/README.md","Strain conversion")])
    graph(s,figs/"transient.png","transient.csv","Brief strains pay a bandwidth and ring-up penalty.","Ideal known-phase discriminator; efficiency and FAR not calibrated",1.68,4.25)
    txt(s,6.04,["The ideal threshold uses the supported-band integral. It is a template sensitivity and does not imply a validated trigger."],14)

    s=page(VI,"PBH mass fixes amplitude and sweep rate","Leading-order circular equal-mass inspiral at 1 AU",
           "Face-on peak amplitude of one polarization. Individual mass explicitly distinguished from total and chirp mass. The other polarization would require a complex directional overlap.",
           [("PBH normalization and comparison to GravNet",ROOT/"simulation/v49_hfgw/README.md","Inspiral models and checks"),
            ("ISCO, elapsed passage and reference 1 AU strain",q("reach"),"mass, ISCO, crossing times and strain")])
    txt(s,1.88,["Use individual mass m, total mass 2m and chirp mass 2⁻¹⁄⁵ m. The grid spans 10⁻¹⁵ to 10⁻⁷ solar masses.",
                 "SI leading-order chirp and strain reproduce the GravNet frequency and mass scalings. The printed Eq. 5 coefficient is compatible with individual mass.",
                 "The approximately 4% Eq. 8 prefactor difference is kept as a convention check. Characteristic strain (Eq. 9) is not the time-domain drive.",
                 "The Schwarzschild ISCO lies above the modeled band. The upper mass edge is still a leading-order benchmark, with no merger or spin validation.",
                 "Larger m increases h as m⁵⁄³ while the bandwidth crossing time decreases as m⁻⁵⁄³."])

    for kind in ("slow","intermediate","fast"):
        r=next(x for x in bench if x["kind"]==kind and x["model"]=="N")
        s=page(VI,f"TM010 · {kind} PBH passage at 1 AU","Incident strain, causal cavity response and absolute ADC snapshots",
               "The cavity drive is the local linear chirp, with one causal pole and normalized to the stationary port power. H/N use only coherent direct electronics, with zero additional phase. Simulated ADC noise is reused from Step 10A; measured PSD sets the matched weighting.",
               [("Benchmark amplitude, crossing, extracted power and energy",q("benchmarks"),f"kind={kind}; H,N"),
                ("Coherent ADC waveform and noise overlay H",physics/f"{kind}_H_ADC.npz","time, isolated and noise overlay, template, incident, cavity"),
                ("Coherent ADC waveform and noise overlay N",physics/f"{kind}_N_ADC.npz","time, isolated and noise overlay, template, incident, cavity")])
        graph(s,figs/f"{kind}.png",f"benchmarks.csv, {kind}_H/N_ADC.npz","Dynamic and steady cavity power are distinct.","Local linear chirp; constant overlap; real readout phase unmeasured",1.54,4.68)
        txt(s,6.28,[f'Individual mass {float(r["individual_mass_Msun"]):.3g} M☉ · crossing/τ = {float(r["crossing_over_tau"]):.3g} · extracted energy {float(r["energy_port_J"]):.3g} J · ideal N ρ = {float(r["ideal_snr_1AU"]):.3g}.'],12)

    s=page(VI,"A threshold illustration is a separate injection","The 1 AU signals remain at their physical normalization",
           "ρ=5 here is an ideal known-phase reference, not an experimental detection threshold. The noise overlay uses the same nominal Step 10A realization. Gain and noise are not adjusted to improve visibility.",
           [("Illustrative strain and distance from normalized template",q("benchmarks"),"illustrative_rho5_distance_AU and illustrative_rho5_peak_strain"),
            ("Isolated and superposed ADC injection",physics/"fast_N_ADC.npz","same arrays for slow and intermediate N benchmark files")])
    graph(s,figs/"illustrative.png","benchmarks.csv; *_N_ADC.npz","Known-template SNR 5 can be below visual noise in a short snapshot.","Illustrative equivalent distance only; no trials or efficiency",1.64,4.25)
    txt(s,6.04,["Illustrative N distances for slow/intermediate/fast: 6.92×10⁻¹¹ / 1.01×10⁻⁷ / 1.02×10⁻⁶ AU. They are separate from the 1 AU benchmarks."],14)

    s=page(VI,"Conditional PBH distance reach","Ideal known-phase SNR 1 and 5 from the observed ADC noise PSD",
           "This reach follows a local linear chirp benchmark, not a source population prediction. Directional C_GW, field in run 680 and complex readout calibration remain open.",
           [("Distance curves, H and N",q("reach"),"all masses, all modes; reach_rho1_AU,reach_rho5_AU"),
            ("Dynamic conservation and convergence",physics/"validation.json","matched-grid, ring and convolution checks")])
    graph(s,figs/"reach.png","reach.csv","SNR grows approximately as m⁵⁄⁶ at fixed distance.","Leading-order circular inspiral, common mask, conditional field/overlap",1.64,4.10)
    txt(s,5.98,["The increase in incident strain outweighs the shorter crossing in this ideal normalization. Detection efficiency and false-alarm rates are unmeasured."],15)

    s=page(VII,"Part VII — Detector model: a work in progress","A physically motivated and experimentally constrained detector model — a constructive work in progress",
           "Preserves the approved historical toy and independent H/N diagnostics. Complements the new conditional signal sensitivity.",
           [("Full-run supported and residual observables",d("step10c/results.md"),"full report"),("Residual identifiability",d("step10d/README.md"),"Constant I/Q map; Back-action")])
    txt(s,1.87,["Reproduced: major noise scales, nearly Rayleigh amplitude, many narrow-band statistics and much of the complex ACF in H.",
                 "Partial: N improves absolute level. H preserves more of the measured spectral and temporal shape.",
                 "Unresolved: high-IF roll-off and aliases, frequency-dependent I/Q impropriety, TM010 LF response, and absolute tone reference planes.",
                 "The measurements constrain residuals, yet do not separate loads, reflections, downstream sources, leakage or reverse noise."])

    s=page(VII,"Hardware measurements needed for a causal model","Separate readout transfer, source spectra and any back-action",
           "The following effects are roadmap items. None is introduced as a fitted or identified contribution in v49.",
           [("Complex and reverse-path measurement roadmap",d("step10d/README.md"),"Back-action, reflections and noise waves"),
            ("Open hardware planes and settings",d("hardware/README.md"),"inventory and characterization"),
            ("Calibration recovery",d("step9a/README.md"),"RF missing data")])
    txt(s,1.87,["Recover original RF source calibrations, field history and directional GW maps. Calibrate installed FET, cables, attenuation, phase and delays.",
                 "Measure loaded BLP, ADC analog bandwidth and aliases, I/Q complex responses versus frequency, mixer translation and LO phase/power.",
                 "Measure impedances, terminations and bidirectional scattering through the circulator and cryogenic chain.",
                 "Use noise waves with correlated sources, distributed noise and reverse transfer. Test back-action and separate wall temperature, mode occupation and receiver noise temperature."],16)

    s=page(VII,"From conditional sensitivity to a validated search","Templates and triggering need independent calibration before interpretation",
           "This closes the current study. No detector threshold, false-alarm rate, source rate, or exclusion has been inferred.",
           [("Current sensitivity assumptions",ROOT/"simulation/v49_hfgw/README.md","Strain conversion and checks"),
            ("Coincidence design context",ROOT/"simulation/v49_hfgw/README.md","GravNet citation")])
    txt(s,1.90,["Validate complex polarization and directional response and the complete ADC signal path.",
                 "Develop covariance-aware matched filters and trigger algorithms. Use software and hardware injections to measure template recovery.",
                 "Measure detection efficiency and false alarm rate across configurations, including nonstationarity and correlated episodes.",
                 "Extend to a synchronized coincidence search with GravNet when the single-detector calibration is established."])
    return deck,ledger,index


def exports(work,physics,out):
    figs=out/"figures"
    figs.mkdir()
    ledger47=read(ROOT/"docs/v47_1/slide_observable_provenance.csv")
    ledger48=read(ROOT/"docs/v48/slide_observable_provenance.csv")
    archive=work/"reports/iq_noise_summary_v47_1"
    names=json.loads((archive/"slide_model.json").read_text())
    index=[]
    keys47=[("file","sha256","datasets_or_columns"),ledger47]
    keys48=[("repository_path","source_sha256","selection_and_fields"),ledger48]
    previous=[]
    for keys,rows in (keys47,keys48):
        for r in rows:
            p=Path(r[keys[0]])
            if not p.is_absolute():
                p=ROOT/p
            previous.append(dict(slide=r["slide"],title=r["title"],observable=r["observable"],
                                 file=str(p),selector=r[keys[2]],sha256=r[keys[1]],
                                 limitation=r.get("limitations","Inherited v48 approved observable")))
    for i,s in enumerate(names,1):
        for item in s["items"]:
            if item["kind"]!="image":
                continue
            p=Path(item["path"])
            # Local exported copies retain source pixels and companion vectors.
            target=figs/f"s{i:02d}_{p.stem}.png"
            with Image.open(p) as im:
                im.save(target)
            for ext in ("pdf","svg"):
                if p.with_suffix("."+ext).is_file():
                    shutil.copy2(p.with_suffix("."+ext),target.with_suffix("."+ext))
            sroot=str(p)
            citations=sorted({(q["file"],q["selector"]) for q in previous if int(q["slide"])==i})
            index.append(dict(file=target.name,title=s["title"],result=s.get("subtitle","") or s["title"],
                              numerical_source=" | ".join(a+" "+b for a,b in citations),
                              limitations="Frozen v47.1 original asset; see provenance and original notes. "+sroot,
                              slide=i,shortlist_20min=int(i in (4,26,46,49))))
    with TemporaryDirectory(prefix="v49-assets-") as d:
        assets=v48_figures(Path(d))
        old=dict(vna=(56,"Independent L5 fits"),components=(58,"Manufacturer transfer responses"),
                 coherent=(59,"Nominal to measured coherent level"),folding=(60,"Secondary mixer RF folding"),
                 psd=(62,"Independent ADC PSD predictions"),bands=(63,"Seven FIR bandwidth comparisons"),
                 iq=(64,"Calibration versus science quadratures"))
        for k,path in assets.items():
            slide,title=old[k]
            target=figs/f"s{slide:02d}_{path.name}"
            shutil.copy2(path,target)
            citations=sorted({(q["file"],q["selector"]) for q in previous if int(q["slide"])==slide})
            index.append(dict(file=target.name,title=title,result=title,
                              numerical_source=" | ".join(a+" "+b for a,b in citations),
                              limitations="Approved v48 conditional model or plotted result; see cited selectors.",
                              slide=slide,shortlist_20min=int(slide in (56,62,64))))
    for name,p in {
        "step10a_validation.png":ROOT/"docs/step10a/validation.png",
        "eta.png":ROOT/"docs/step10d/eta.png","high_IF.png":ROOT/"docs/step10d/high_IF.png",
        **{f"{m}_distributions.png":work/f"simulation/step10c/{m}_distributions.png" for m in MODES},
        **{p.name:p for p in physics.iterdir() if p.suffix in (".pdf",".png")},
    }.items():
        shutil.copy2(p,figs/name)
    curves(work,figs)
    band_figure(figs)
    return figs,previous,index


def table_validation(physics):
    mono=read(physics/"monochromatic.csv")
    trans=read(physics/"transient.csv")
    reach=read(physics/"reach.csv")
    mono_error=max(abs(float(r["h_rho1_white_center"])*np.sqrt(2*float(r["seconds"])) /
                       float(r["center_complex_strain_ASD"])-1) for r in mono)
    pulse_diffs=[]
    impulse_diffs=[]
    mass_diffs=[]
    for m in MODES:
        for model in ("H","N"):
            t=sorted((r for r in trans if r["mode"]==m and r["model"]==model),key=lambda r:float(r["seconds"]))
            nominal=next(r for r in mono if r["mode"]==m and r["model"]==model and
                         float(r["seconds"])==float(t[-1]["seconds"]))
            pulse_diffs.append(abs(float(t[-1]["h_rho1_rectangular"])/float(nominal["h_rho1_white_center"])-1))
            u=[float(r["seconds"])*float(r["h_rho1_rectangular"]) for r in t[:2]]
            impulse_diffs.append(abs(u[0]/u[1]-1))
            rr=[r for r in reach if r["mode"]==m and r["model"]==model]
            def col(k):
                return np.array([float(r[k]) for r in rr])
            np.testing.assert_allclose(col("reach_rho1_AU"),5*col("reach_rho5_AU"),rtol=1e-14)
            mratio=col("individual_mass_Msun")/float(rr[0]["individual_mass_Msun"])
            mass_diffs.append(float(np.max(abs(col("reach_rho1_AU")/(mratio**(5/6)*
                                float(rr[0]["reach_rho1_AU"]))-1))))
    assert mono_error<1e-14 and max(pulse_diffs)<.0001 and max(impulse_diffs)<.001 and max(mass_diffs)<1e-12
    return dict(monochromatic_scaling_max_relative=mono_error,
                long_rectangular_vs_center_limit_max_relative=max(pulse_diffs),
                short_rectangular_impulse_scaling_max_relative=max(impulse_diffs),
                distance_reach_mass_scaling_max_relative=max(mass_diffs))


def build(work,physics,out):
    baseline=work/"reports/iq_noise_summary_v48"
    base={ext:baseline/f"iq_noise_summary_v48.{ext}" for ext in ("pdf","pptx")}
    assert all(sha(p)==V48_HASH[ext] for ext,p in base.items())
    out.mkdir(parents=True,exist_ok=False)
    figs,previous,figure_rows=exports(work,physics,out)
    appendix,ledger,new_index=slides(physics,figs,work)
    figure_rows.extend(new_index)
    total=START+len(appendix.slides)
    frozen.COUNT=START
    frozen.TOTAL=total
    files={ext:out/f"iq_noise_summary_v49.{ext}" for ext in ("pdf","pptx")}
    with TemporaryDirectory(prefix="v49-") as d:
        temp=Path(d)
        extension=temp/"appendix"
        sd.export(appendix,extension,"v49_appendix","18 November 2026",page_offset=START,total_pages=total)
        shutil.copy2(extension/"contact_sheet.png",out/"parts_v_vii_contact_sheet.png")
        original,final=PdfReader(base["pdf"]),None
        writer=PdfWriter()
        writer.append_pages_from_reader(original)
        writer.append_pages_from_reader(PdfReader(extension/"iq_noise_summary_v49_appendix.pdf"))
        with files["pdf"].open("wb") as stream:
            writer.write(stream)
        final=PdfReader(files["pdf"])
        assert len(original.pages)==START and len(final.pages)==total
        assert all(a.get_contents().get_data()==b.get_contents().get_data() for a,b in zip(original.pages,final.pages))
        frozen.compare_rendering(base["pdf"],files["pdf"],temp)
        members=frozen.append_pptx(base["pptx"],extension/"iq_noise_summary_v49_appendix.pptx",files["pptx"])
        pres=Presentation(files["pptx"])
        assert len(pres.slides)==total
        for i,s in enumerate(appendix.slides,START):
            assert pres.slides[i].shapes[1].text.replace("\n"," ")==s["title"]
            norm=lambda value:"".join(c for c in value if c.isalnum())
            assert norm(s["title"]) in norm(final.pages[i].extract_text())
    write(out/"figure_index.csv",figure_rows)
    write(out/"slide_observable_provenance.csv",previous+ledger)
    shutil.copytree(physics,out/"physics_tables",ignore=shutil.ignore_patterns("*.npz","*.png","*.pdf"))
    for file in ("README.md","meeting_figure_shortlist.md"):
        shutil.copy2(ROOT/"docs/v49"/file,out/file)
    report=dict(slides=total,reused_v48=START,new_slides=total-START,
                base_sha256=V48_HASH,pdf_content_streams_preserved=START,pixel_matched_pages=START,
                original_PPTX_members_identical=members,
                figure_index_entries=len(figure_rows),provenance_rows=len(previous)+len(ledger),
                physics=json.loads((physics/"validation.json").read_text()),
                table_validation=table_validation(physics),
                visual_plot_data="all old plots retained; new plots from approved aggregations or physical benchmarks")
    (out/"validation.json").write_text(json.dumps(report,indent=2)+"\n")
    (out/"validation_report.md").write_text(f"""# v49 validation report

- PDF and PPTX contain {total} slides. The first {START} preserve all v48 content and reproduce pixel-identically in the PDF. Original content streams match after assembly in a new PDF container. {members} original PowerPoint package members match exactly, with only package indexes changed.
- New slide titles, native PowerPoint text, speakers' notes and figure payloads were verified. Parts V–VII append {total-START} slides.
- {len(previous)+len(ledger)} provenance rows and {len(figure_rows)} figure index rows link plots and numbers to explicit files and selectors. Numerical products from v48 and previous steps are unchanged.
- Physics checks cover the analytic area, dynamic energy, converged noise-weighted integral, direct complex convolution, limits, Parseval and ISCO. Numerical results are in validation.json. All reference-field/overlap, readout and statistical limitations are explicit.
- No new science sample reconstruction, corrective fit, noise parameter adjustment or astrophysical exclusion.
""")
    def portable(path):
        p=Path(path)
        if p.is_relative_to(ROOT):
            return str(p.relative_to(ROOT))
        return str(p)
    inputs={portable(p):sha(p) for p in base.values()}
    # Previously frozen references carry their approved recorded hashes.
    inputs.update({portable(r["file"]):r["sha256"] for r in previous+ledger if r["sha256"]})
    inputs.update({portable(p):sha(p) for p in (Path(__file__),ROOT/"reporting/slide_deck.py",
                         ROOT/"reporting/iq_noise_summary_v48/build.py",ROOT/"reporting/iq_noise_summary_v48/figures.py")})
    inputs.update(report["physics"]["input_sha256"])
    outputs={str(p.relative_to(out)):sha(p) for p in out.rglob("*") if p.is_file()}
    (out/"sha256.json").write_text(json.dumps(dict(inputs=inputs,outputs=outputs),indent=2)+"\n")
    print(f"{total} slides, {len(figure_rows)} indexed figures, {len(previous)+len(ledger)} provenance rows")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("work","physics","out"):
        parser.add_argument(name,type=Path)
    a=parser.parse_args()
    build(a.work,a.physics,a.out)
