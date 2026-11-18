"""Reports and numerical closure checks for the streamed Step 10C reduction."""
import argparse
import csv
import json
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.fft import ifft
from scipy.special import ndtr

MODES=("TM010","TM011","TM012")
POPS=("data","H","N")
BANDS=("full","-500000","-250000","-100000","0","100000","250000","500000")
COLORS={"data":"#007F86","H":"#7657A6","N":"#D98726"}
EDGES=(0,.1,.25,.5,1,1.25,1.75,2.5)
FOCUS=("RMS_V","power_V2","var_I_V2","var_Qhardware_V2","cov_I_Qhardware_V2",
       "pseudo_real_V2","pseudo_imag_V2","pseudo_real_relative","pseudo_imag_relative","pseudo_abs_relative",
       "amplitude_mean_over_RMS","amplitude_fourth_over_RMS4","mean_amplitude_V","amplitude_sd_V",
       "rayleigh_CDF_max_diff","phase_resultant","phase_increment_cos_1","phase_increment_sin_1",
       "acf_real_1","acf_imag_1","acf_abs_1","acf_real_10","acf_imag_10","acf_abs_10")


def write(path,rows):
    with path.open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator="\n")
        writer.writeheader()
        writer.writerows({k:format(v,".12g") if isinstance(v,(float,np.floating)) else v
                          for k,v in row.items()} for row in rows)


def read_blocks(local,cfg):
    n=cfg["spec_count"]*4
    values={}
    with (local/"blocks.csv").open(newline="") as stream:
        for row in csv.DictReader(stream):
            key=(row["mode"],row["population"],row["band"])
            columns=[k for k,v in row.items() if v and k not in ("mode","population","band","SPEC","subblock")]
            if key not in values:
                values[key]={c:np.full(n,np.nan) for c in columns}
            i=4*int(row["SPEC"])+int(row["subblock"])
            for c in columns:
                values[key][c][i]=float(row[c])
    assert len(values)==72 and all(np.isfinite(a).all() for d in values.values() for a in d.values())
    return values


def dispersion(v, size):
    blocks=v.reshape(-1,size)
    means=blocks.mean(axis=1)
    return means.std(ddof=1)/np.sqrt(len(means))


def summary(values,cfg):
    size=4*cfg["cluster_SPECs"]
    result,tail=[],[]
    for (m,p,band),v in sorted(values.items()):
        key=dict(mode=m,population=p,band=band)
        # Distinguish arithmetic mean of block RMS from RMS of all sample powers.
        for name,a in v.items():
            if name.startswith("tail_"):
                continue
            result.append(dict(**key,observable=name,mean=a.mean(),block_SD=a.std(ddof=1),
                               SPEC_SD=a.reshape(-1,4).mean(axis=1).std(ddof=1),
                               cluster_SE=dispersion(a,size),double_cluster_SE=dispersion(a,size*2)))
        for alias,a in (("RMS_aggregate_V",v["power_V2"]),):
            mean=np.sqrt(a.mean())
            result.append(dict(**key,observable=alias,mean=mean,block_SD="",
                               SPEC_SD="",cluster_SE=dispersion(a,size)/(2*mean),
                               double_cluster_SE=dispersion(a,size*2)/(2*mean)))
        samples=v["samples"]
        for multiple in cfg["threshold_multiples_RMS"]:
            for kind in ("shape","absolute"):
                stem=f"tail_{kind}_{multiple}"
                counts=v[stem+"_count"]
                episodes=v[stem+"_episodes"]
                n=int(counts.sum())
                eligible=int(samples.sum())
                clusters=int(np.count_nonzero(counts.reshape(-1,size).sum(axis=1)))
                specs=int(np.count_nonzero(counts.reshape(-1,4).sum(axis=1)))
                good=n>=cfg["min_tail_count"] and specs>=cfg["min_tail_spec_groups"] and clusters>=4
                tail.append(dict(**key,threshold_kind=kind,multiple_RMS=multiple,
                                 fixed_threshold_V=multiple*v["proper_reference_RMS_V"][0] if kind=="absolute" else "",
                                 samples_above=n,eligible_samples=eligible,
                                 SPECs_with_exceedances=specs,clusters_with_exceedances=clusters,
                                 episodes=int(episodes.sum()),left_censored=int(v[stem+"_left_censored"].sum()),
                                 right_censored=int(v[stem+"_right_censored"].sum()),estimable=int(good),
                                 sample_fraction=n/eligible if good else "",
                                 sample_fraction_cluster_SE=dispersion(counts/samples,size) if good else "",
                                 sample_fraction_double_cluster_SE=dispersion(counts/samples,size*2) if good else "",
                                 block_episode_count_SD=episodes.std(ddof=1),
                                 cluster_episode_count_SD=episodes.reshape(-1,size).sum(axis=1).std(ddof=1)))
    return result,tail


def spectral(h,values,fs):
    f=h["frequency_Hz"][:]
    n=len(f)
    df=fs/n
    c1=np.cos(2*np.pi*f/fs)
    regions=[]
    closure=[]
    for m in MODES:
        for name in ("data","H","N","H_analytic","N_analytic"):
            analytical=name.endswith("_analytic")
            row=dict(mode=m,population=name)
            if analytical:
                p=h[f"analytical/{m}/{name[0]}/PSD"][:]
                c=np.zeros_like(p,dtype=complex)
            else:
                group=h[f"mean/{m}/{name}/full"]
                p=group["PSD"][:]
                c=group["complementary"][:]
                temporal=complex(values[m,name,"full"]["pseudo_real_V2"].mean(),
                                 values[m,name,"full"]["pseudo_imag_V2"].mean())
                recovered=df*c.sum()
                np.testing.assert_allclose(recovered,temporal,atol=1e-19,rtol=1e-10)
                cyc=fs*ifft(p)[:len(group["acf_V2"])]
                lag=np.arange(len(cyc))
                prediction=(n*cyc-group["ACF_wrap_V2_sum"][:])/(n-lag)
                acf=group["acf_V2"][:]
                np.testing.assert_allclose(prediction,acf,atol=1e-17,rtol=1e-9)
                alternating={k:df*c[freqmask].sum() for k,freqmask in
                             (("negative",f<0),("positive",f>0))}
                # Per-group spectra are averages of 128 consecutive bins in full signed order.
                per_cluster=np.array([g[f"{m}/{name}/full/complementary"][:].sum()*df*128
                                      for g in h["clusters"].values()])
                np.testing.assert_allclose(per_cluster.mean(),recovered,atol=1e-19,rtol=1e-10)
                closure.append(dict(**row,PSD_integrated_V2=df*p.sum(),
                                   pseudo_temporal_real_V2=temporal.real,pseudo_temporal_imag_V2=temporal.imag,
                                   pseudo_spectral_real_V2=recovered.real,pseudo_spectral_imag_V2=recovered.imag,
                                   pseudo_real_cluster_SE_V2=per_cluster.real.std(ddof=1)/len(per_cluster)**.5,
                                   pseudo_imag_cluster_SE_V2=per_cluster.imag.std(ddof=1)/len(per_cluster)**.5,
                                   negative_half_pseudo_real_V2=alternating["negative"].real,
                                   positive_half_pseudo_real_V2=alternating["positive"].real,
                                   ACF_max_closure_error_V2=np.max(abs(prediction-acf)),
                                   pseudo_closure_error_V2=abs(recovered-temporal),
                                   lag1_Re_circular=cyc[1].real/cyc[0].real,
                                   lag1_Re_linear=acf[1].real/acf[0].real,
                                   lag1_Im_linear=acf[1].imag/acf[0].real))
            all_power=df*np.sum(p)
            for lo,hi in zip(EDGES,EDGES[1:]):
                q=(abs(f)>=lo*1e6)&(abs(f)<hi*1e6)
                if hi==EDGES[-1]:
                    q|=abs(f)==hi*1e6
                pv=df*p[q].sum()
                contribution=df*np.sum(p[q]*c1[q])
                cv=df*c[q].sum()
                regions.append(dict(**row,abs_IF_low_MHz=lo,abs_IF_high_MHz=hi,
                                    power_V2=pv,power_fraction=pv/all_power,
                                    lag1_Re_numerator_V2=contribution,lag1_Re_over_full_power=contribution/all_power,
                                    pseudo_real_V2=cv.real,pseudo_imag_V2=cv.imag))
            np.testing.assert_allclose(sum(r["lag1_Re_over_full_power"] for r in regions[-(len(EDGES)-1):]),
                                       fs*ifft(p)[1].real/all_power,atol=1e-14)
    return closure,regions


def plot(h,local,light,regions):
    frequency=np.fft.fftshift(h["frequency_Hz"][:])/1e6
    mask=np.fft.fftshift(h["common_mask"][:])
    edges=h["amplitude_edges"][:]
    z=(edges[:-1]+edges[1:])/2
    fig,ax=plt.subplots(3,3,figsize=(12,8),layout="constrained")
    for i,m in enumerate(MODES):
        for pop in POPS:
            g=h[f"mean/{m}/{pop}/full"]
            color=COLORS[pop]
            labels=np.fft.fftshift(g["complementary"][:])
            for j,part in enumerate((labels.real,labels.imag)):
                for signed_side,side in enumerate((frequency<0,frequency>0)):
                    sel=np.flatnonzero(side&mask)
                    sel=sel[:len(sel)//128*128].reshape(-1,128)
                    ax[i,j].plot(frequency[sel].mean(axis=1),part[sel].mean(axis=1),color=color,lw=.8,label=pop if j==0 and signed_side==0 else None)
            rows=[r for r in regions if r["mode"]==m and r["population"]==pop and r["abs_IF_low_MHz"]>=.1]
            x=np.arange(len(rows))+.24*(POPS.index(pop)-1)
            ax[i,2].bar(x,[r["lag1_Re_over_full_power"] for r in rows],.24,color=color,label=pop)
        ax[i,0].set(ylabel=m+" · V²/Hz")
        ax[i,2].set(xticks=range(6),xticklabels=[".1–.25",".25–.5",".5–1","1–1.25","1.25–1.75","1.75–2.5"])
    ax[0,0].set_title("Re complementary spectrum")
    ax[0,1].set_title("Im complementary spectrum")
    ax[0,2].set_title("Contributions to Re g₁ at first lag")
    ax[0,2].legend(fontsize=8)
    for a in ax[-1,:2]:
        a.set_xlabel("Signed IF (MHz)")
    ax[-1,2].set_xlabel("|IF| interval (MHz)")
    fig.savefig(light/"spectral_diagnostics.png",dpi=115)
    plt.close(fig)

    for m in MODES:
        fig,axes=plt.subplots(4,3,figsize=(12,10),layout="constrained")
        for j,p in enumerate(POPS):
            full=h[f"mean/{m}/{p}/full"]
            psd=np.fft.fftshift(full["PSD"][:])
            for side in (frequency<0,frequency>0):
                sel=np.flatnonzero(side&mask)
                sel=sel[:len(sel)//128*128].reshape(-1,128)
                axes[0,j].semilogy(frequency[sel].mean(axis=1),psd[sel].mean(axis=1),color=COLORS[p])
            axes[0,j].set(title=p,xlabel="Signed IF (MHz)",ylabel="PSD [V²/Hz]")
            acf=full["acf"][:]
            for y,ls in ((acf.real,"-"),(acf.imag,"--"),(abs(acf),":")):
                axes[1,j].plot(np.arange(len(y))/5,y,ls,color=COLORS[p])
            axes[1,j].set(xlabel="Lag (µs)",ylabel="Complex ACF")
            axes[2,j].plot(z,full["amplitude_shape"][:]/np.diff(edges),color=COLORS[p])
            axes[2,j].plot(z,2*z*np.exp(-z*z),":",color=".4")
            axes[2,j].set(xlabel="Amplitude / block RMS",ylabel="Density")
            e=h["phase_edges"][:]
            for lag,style in ((1,"-"),(10,"--"),(100,":")):
                axes[3,j].plot((e[1:]+e[:-1])/2,full[f"phase_increment_{lag}"][:]/np.diff(e),style,color=COLORS[p])
            axes[3,j].set(xlabel="Phase increment (rad)",ylabel="Density")
        fig.suptitle(m+" · full-run common mask")
        fig.savefig(local/f"{m}_full.png",dpi=120)
        plt.close(fig)
        fig,axes=plt.subplots(2,7,figsize=(17,4.7),layout="constrained")
        for j,band in enumerate(BANDS[1:]):
            axes[0,j].set_title(f"{int(band)/1000:+.0f} kHz")
            for p in POPS:
                g=h[f"mean/{m}/{p}/{band}"]
                a=g["acf"][:]
                for q,style in ((a.real,"-"),(a.imag,"--"),(abs(a),":")):
                    axes[0,j].plot(np.arange(len(q))*4,q,style,color=COLORS[p])
                axes[1,j].plot(z,g["amplitude_shape"][:]/np.diff(edges),color=COLORS[p])
            axes[0,j].set_xlim(0,240)
        axes[0,0].set_ylabel("Complex ACF vs lag (µs)")
        axes[1,0].set_ylabel("Amplitude / block RMS")
        fig.suptitle(m+" · seven FIR bands")
        fig.savefig(local/f"{m}_FIR.png",dpi=120)
        plt.close(fig)


def distribution_check(h,local):
    amp=h["amplitude_edges"][:]
    axis=h["IQ_edges"][:]
    phase=h["phase_edges"][:]
    marginal=np.diff(ndtr(axis*np.sqrt(2)))
    proper=np.outer(marginal,marginal)
    cdf=1-np.exp(-amp[1:]**2)
    rows=[]
    for m in MODES:
        fig,ax=plt.subplots(3,3,figsize=(11,8),layout="constrained")
        for band in BANDS:
            measured=h[f"mean/{m}/data/{band}"]
            for idx,p in enumerate(POPS):
                g=h[f"mean/{m}/{p}/{band}"]
                iq=g["iq_shape"][:]
                af=g["acf"][:]
                observed=measured["acf"][:]
                phase_mass=g["phase"][:]
                rows.append(dict(mode=m,population=p,band=band,
                                 IQ_binned_TV_vs_proper=.5*(abs(iq-proper).sum()+abs(iq.sum()-proper.sum())),
                                 amplitude_KS_distance_descriptive=np.max(abs(np.cumsum(g["amplitude_shape"][:])-cdf)),
                                 phase_binned_TV_vs_uniform=.5*np.sum(abs(phase_mass-1/len(phase_mass))),
                                 complex_ACF_RMSE_vs_data=np.sqrt(np.mean(abs(af[1:]-observed[1:])**2))))
                if band!="full":
                    continue
                ax[0,idx].imshow(np.log10(np.maximum(iq.T,1e-8)),origin="lower",
                                extent=[axis[0],axis[-1]]*2,vmin=-7,vmax=-2.7,aspect="equal")
                ax[0,idx].set(title=p+" · I/Q shape",xlabel="I / block RMS",ylabel="Q / block RMS")
                ax[1,idx].plot((phase[1:]+phase[:-1])/2,phase_mass/np.diff(phase),color=COLORS[p])
                ax[1,idx].axhline(1/(2*np.pi),color=".35",ls=":")
                ax[1,idx].set(xlabel="Signed phase (rad)",ylabel="Density")
                ax[2,idx].plot((amp[1:]+amp[:-1])/2,g["amplitude_absolute"][:]/np.diff(amp),color=COLORS[p])
                ax[2,idx].set(xlabel="Amplitude / fixed N analytical RMS",ylabel="Density")
        fig.suptitle(m+" · I/Q, phase and fixed-reference amplitude")
        fig.savefig(local/f"{m}_distributions.png",dpi=120)
        plt.close(fig)
    return rows


def results(rows,tails,closure,regions):
    select={(r["mode"],r["population"],r["band"],r["observable"]):r["mean"] for r in rows}
    get=lambda m,p,b,k:select[m,p,b,k]
    lines=["# Step 10C — Numerical results","",
           "All comparisons use masked ADC blocks. H and N are paired Monte Carlo populations.",
           "",
           "| Mode | Mean block RMS, data / H / N (mV) | Aggregate RMS, data / H / N (mV) | Data/H and data/N (dB) | Data/N central FIR (dB) |",
           "| --- | ---: | ---: | ---: | ---: |"]
    for m in MODES:
        def rms(k):
            return " / ".join(f'{1000*get(m,p,"full",k):.6f}' for p in POPS)
        def residual(p,b):
            return 20*np.log10(get(m,"data",b,"RMS_aggregate_V")/get(m,p,b,"RMS_aggregate_V"))
        lines.append(f"| {m} | {rms('RMS_V')} | {rms('RMS_aggregate_V')} | "
                     f"{residual('H','full'):+.3f} / {residual('N','full'):+.3f} | {residual('N','0'):+.3f} |")
    lines.extend(["","## Complementary power and first-lag covariance","",
                  "| Mode | Population | Re pseudo / AC² | Im pseudo / AC² | Re g₁ at 0.2 µs | Positive and negative PSD contributions to Re g₁ |",
                  "| --- | --- | ---: | ---: | ---: | ---: |"])
    for r in closure:
        m,p=r["mode"],r["population"]
        q=[x for x in regions if x["mode"]==m and x["population"]==p]
        pos=sum(x["lag1_Re_over_full_power"] for x in q if x["abs_IF_high_MHz"]<=1.25)
        neg=sum(x["lag1_Re_over_full_power"] for x in q if x["abs_IF_low_MHz"]>=1.25)
        scale=r["PSD_integrated_V2"]
        lines.append(f'| {m} | {p} | {r["pseudo_spectral_real_V2"]/scale:+.6f} | '
                     f'{r["pseudo_spectral_imag_V2"]/scale:+.6f} | {r["lag1_Re_linear"]:+.6f} | {pos:+.6f} / {neg:+.6f} |')
    lines.extend(["","Largest absolute complementary contributions in data, with the signs retained:",
                  "",
                  "| Mode | Re-leading absolute IF range (MHz) | Re contribution (V²) | Im-leading absolute IF range (MHz) | Im contribution (V²) |",
                  "| --- | --- | ---: | --- | ---: |"])
    for m in MODES:
        q=[x for x in regions if x["mode"]==m and x["population"]=="data"]
        def maximum(field):
            r=max(q,key=lambda row:abs(row[field]))
            return f'{r["abs_IF_low_MHz"]:.2f}–{r["abs_IF_high_MHz"]:.2f} | {r[field]:+.4e}'
        lines.append(f'| {m} | {maximum("pseudo_real_V2")} | {maximum("pseudo_imag_V2")} |')
    lines.extend(["","## Full-band empirical tails at 5 RMS","",
                  "| Mode | Population | Threshold frame | Samples | Episodes | Fraction (where supported) |",
                  "| --- | --- | --- | ---: | ---: | ---: |"])
    for r in tails:
        if r["band"]=="full" and r["multiple_RMS"]==5:
            frac=f'{r["sample_fraction"]:.3e}' if r["estimable"] else "—"
            lines.append(f'| {r["mode"]} | {r["population"]} | {r["threshold_kind"]} | '
                         f'{r["samples_above"]} | {r["episodes"]} | {frac} |')
    lines.extend(["","Each full-band row uses 1048576000 eligible observations. Episode boundaries are censored as shown in the tail table.",
                  "",f'Maximum aggregated PSD–ACF closure residual: {max(r["ACF_max_closure_error_V2"] for r in closure):.3e} V².',
                  "",f'Maximum aggregated complementary closure residual: {max(r["pseudo_closure_error_V2"] for r in closure):.3e} V².'])
    return "\n".join(lines)+"\n"


def main(local,light):
    light.mkdir(parents=True,exist_ok=True)
    metadata=json.loads((local/"population.json").read_text())
    cfg=metadata["config"]
    values=read_blocks(local,cfg)
    rows,tails=summary(values,cfg)
    write(local/"all_observables.csv",rows)
    write(light/"observables.csv",[r for r in rows if r["observable"] in FOCUS+("RMS_aggregate_V",)])
    write(light/"tail_counts.csv",tails)
    with h5py.File(local/"statistics.h5") as h:
        closure,regions=spectral(h,values,metadata["Fs_Hz"])
        write(light/"spectral_closure.csv",closure)
        write(light/"spectral_intervals.csv",regions)
        (light/"results.md").write_text(results(rows,tails,closure,regions))
        write(light/"distribution_diagnostics.csv",distribution_check(h,local))
        plot(h,local,light,regions)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("local",type=Path)
    parser.add_argument("light",type=Path)
    a=parser.parse_args()
    main(a.local,a.light)
