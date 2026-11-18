"""Summarize paired Step 10B observables without sample-IID error bars."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

MODES=("TM010","TM011","TM012")
POPS=("data","H","N")
COLORS={"data":"#007F86","H":"#7657A6","N":"#D98726"}
BANDS=("full","-500000","-250000","-100000","0","100000","250000","500000")
FOCUS=("RMS_V","var_I_V2","var_Qhardware_V2","cov_I_Qhardware_V2","pseudo_real_V2","pseudo_imag_V2",
       "pseudo_real_relative","pseudo_imag_relative","pseudo_abs_relative","mean_amplitude_V",
       "amplitude_sd_V","amplitude_mean_over_RMS","amplitude_fourth_over_RMS4","rayleigh_CDF_max_diff",
       "phase_resultant","phase_increment_cos_1","phase_increment_sin_1",
       "phase_increment_resultant_1","acf_real_1","acf_imag_1","acf_abs_1",
       "acf_real_10","acf_imag_10","acf_abs_10","guard_trimmed_to_full_power","removed_DC_V2",
       "rejected_V2")
NAMES={"data":"Run 680","H":"Hybrid","N":"Nominal"}


def write(path,rows):
    with path.open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def summarize(records,cfg):
    groups=defaultdict(list)
    for r in records:
        groups[r["mode"],r["population"],r["band"]].append(r)
    estimates, tails, controls = [], [], []
    for (mode,pop,band), rr in sorted(groups.items()):
        assert [r["block"] for r in rr]==list(range(len(rr)))
        prefix=dict(mode=mode,population=pop,band=band)
        if pop.endswith("10A"):
            r,=rr
            controls.append({**prefix,**{k:r[k] for k in ("samples","RMS_V","pseudo_abs_relative",
                            "rayleigh_CDF_max_diff","acf_real_1","acf_imag_1")}})
            continue
        assert len(rr)==cfg["spec_count"]*4
        for key in (k for k in rr[0] if k not in
                    ("mode","population","band","SPEC_group","block","samples") and not k.startswith("tail_")):
            values=np.array([r[key] for r in rr])
            spec=values.reshape(-1,4).mean(axis=1)
            cluster=spec.reshape(-1,2).mean(axis=1)
            estimates.append(dict(**prefix,observable=key,mean=values.mean(),
                                  block_SD=values.std(ddof=1),SPEC_SD=spec.std(ddof=1),
                                  SPEC_SE_descriptive=spec.std(ddof=1)/np.sqrt(len(spec)),
                                  two_SPEC_SE_descriptive=cluster.std(ddof=1)/np.sqrt(len(cluster)),
                                  four_SPEC_SE_descriptive=(spec.reshape(-1,4).mean(axis=1).std(ddof=1)
                                    /np.sqrt(len(spec)//4)) if len(spec)%4==0 and len(spec)>4 else "",
                                  blocks=len(values),clusters=len(cluster)))
        total=sum(r["samples"] for r in rr)
        for multiple in cfg["threshold_multiples_RMS"]:
            for kind in ("shape","absolute"):
                counts=np.array([r[f"tail_{kind}_{multiple}_count"] for r in rr])
                spec=(counts.reshape(-1,4).sum(axis=1)>0).sum()
                supported=counts.sum()>=cfg["min_tail_count"] and spec>=cfg["min_tail_spec_groups"]
                tails.append(dict(**prefix,threshold_kind=kind,multiple_RMS=multiple,
                                  fixed_threshold_V=multiple*rr[0]["proper_reference_RMS_V"] if kind=="absolute" else "",
                                  exceedance_samples=int(counts.sum()),eligible_samples=total,SPEC_with_exceedances=spec,
                                  supported=int(supported),fraction=counts.sum()/total if supported else "",
                                  two_SPEC_fraction_SE_descriptive=(counts.reshape(-1,8).sum(axis=1)/(rr[0]["samples"]*8)).std(ddof=1)
                                  /np.sqrt(len(counts)//8) if supported else ""))
    return estimates,tails,controls


def statistics_plots(h,out):
    amp=h["amplitude_edges_over_reference_RMS"][:]
    iq=h["iq_edges_over_reference_RMS"][:]
    phase=h["phase_edges_rad"][:]
    frequency=np.fft.fftshift(h["frequency_Hz"][:])
    mask=np.fft.fftshift(h["common_mask"][:])
    mid=lambda a:(a[1:]+a[:-1])/2
    for m in MODES:
        fig,axes=plt.subplots(3,3,figsize=(13,9),layout="constrained")
        a=axes.flat
        for pop in POPS:
            g=h[f"{m}/{pop}/full"]
            label=NAMES[pop]
            color=COLORS[pop]
            rms=float(g.attrs["reference"])
            p=np.fft.fftshift(g["PSD"][:],axes=-1)
            for opposite,region in enumerate((mask&(frequency<0),mask&(frequency>0))):
                ix=np.flatnonzero(region)
                ix=ix[:len(ix)//128*128].reshape(-1,128)
                yy=p[:,ix].mean(axis=-1)
                xf=frequency[ix].mean(axis=1)/1e6
                a[0].semilogy(xf,yy.mean(axis=0),color=color,lw=1,label=label if not opposite else None)
                a[0].fill_between(xf,np.quantile(yy,.16,axis=0),np.quantile(yy,.84,axis=0),color=color,alpha=.12)
            lags=np.arange(g["acf"].shape[-1])/5
            acf=g["acf"][:].mean(axis=0)
            a[1].plot(lags,acf.real,color=color,lw=1,label=label)
            a[1].plot(lags,acf.imag,color=color,lw=1,ls="--")
            a[1].plot(lags,abs(acf),color=color,lw=.8,ls=":")
            a[2].plot(mid(amp)*rms*1e3,g["amplitude_absolute"][:].mean(axis=0)/np.diff(amp)/(rms*1e3),color=color,label=label)
            a[3].plot(mid(amp),g["amplitude_shape"][:].mean(axis=0)/np.diff(amp),color=color,label=label)
            a[4].plot(mid(phase),g["phase"][:].mean(axis=0)/np.diff(phase),color=color,label=label)
            for lag,style in ((1,"-"),(10,"--"),(100,":")):
                a[5].plot(mid(phase),g[f"phase_increment_{lag}"][:].mean(axis=0)/np.diff(phase),color=color,ls=style)
            panel=a[6+POPS.index(pop)]
            counts=g["iq_absolute"][:].mean(axis=0)
            panel.imshow(np.log10(np.maximum(counts.T,1e-7)),extent=[iq[0]*rms*1e3,iq[-1]*rms*1e3]*2,
                         origin="lower",vmin=-6,vmax=-2.7,cmap="viridis",aspect="equal")
            panel.set(title=label+" · absolute I/Q",xlabel="I (mV)",ylabel="Q hardware (mV)")
        a[3].plot(mid(amp),h["proper_reference_rayleigh_bin_probability"][:]/np.diff(amp),color=".4",ls="--")
        a[4].axhline(1/(2*np.pi),color=".4",ls="--")
        a[0].set(title="Rectangular bilateral PSD",xlabel="Signed IF (MHz)",ylabel="V²/Hz ADC")
        a[0].legend(fontsize=8)
        a[1].set(title="Complex ACF: Re / Im / modulus",xlabel="Lag (µs)",ylabel="Normalized ACF")
        a[2].set(title="Amplitude in ADC units",xlabel="mV ADC")
        a[3].set(title="Amplitude shape · dashed Rayleigh",xlabel="Amplitude / block RMS")
        a[4].set(title="Phase · dashed proper reference",xlabel="rad")
        a[5].set(title="Circular increments · lags 1 / 10 / 100",xlabel="rad")
        fig.suptitle(m+" · masked blocks")
        fig.savefig(out/f"{m}_full.png",dpi=135)
        plt.close(fig)

        fig,axes=plt.subplots(4,7,figsize=(17,8),layout="constrained")
        for j,band in enumerate(BANDS[1:]):
            for pop in POPS:
                g=h[f"{m}/{pop}/{band}"]
                color=COLORS[pop]
                acf=g["acf"][:].mean(axis=0)
                lag=np.arange(len(acf))*4
                axes[0,j].plot(mid(amp),g["amplitude_shape"][:].mean(axis=0)/np.diff(amp),color=color)
                axes[1,j].plot(lag,acf.real,color=color)
                axes[1,j].plot(lag,acf.imag,color=color,ls="--")
                axes[1,j].plot(lag,abs(acf),color=color,ls=":")
                axes[1,j].set_xlim(0,200)
                axes[2,j].plot(mid(phase),g["phase"][:].mean(axis=0)/np.diff(phase),color=color)
                axes[3,j].plot(mid(phase),g["phase_increment_1"][:].mean(axis=0)/np.diff(phase),color=color)
            axes[0,j].plot(mid(amp),h["proper_reference_rayleigh_bin_probability"][:]/np.diff(amp),ls=":",color=".4")
            axes[0,j].set_title(f"{int(band)/1000:+.0f} kHz")
        for j,label in enumerate(("Amplitude / RMS","Complex g₁ (µs)","Phase (rad)","Δ phase, lag 1 (rad)")):
            axes[j,0].set_ylabel(label)
        fig.suptitle(m+" · seven FIR bands · run 680 (teal), H (purple), N (orange)")
        fig.savefig(out/f"{m}_FIR.png",dpi=125)
        plt.close(fig)


def light_plot(rows,out):
    table={(r["mode"],r["population"],r["band"],r["observable"]):r for r in rows}
    fig,axes=plt.subplots(1,2,figsize=(9,3.6),layout="constrained")
    for j,pop in enumerate(POPS):
        for ax,key,scale in zip(axes,("RMS_V","pseudo_abs_relative"),(1000,1)):
            selected=[table[m,pop,"full",key] for m in MODES]
            ax.errorbar(np.arange(3)+.14*(j-1),[r["mean"]*scale for r in selected],
                        yerr=[r["two_SPEC_SE_descriptive"]*scale for r in selected],fmt="o",
                        color=COLORS[pop],label=NAMES[pop],ms=5,capsize=3)
            ax.set(xticks=range(3),xticklabels=MODES)
    axes[0].set_ylabel("Masked RMS (mV ADC)")
    axes[1].set_ylabel("Mean per-block |pseudo| / power")
    axes[0].legend(fontsize=8)
    fig.savefig(out/"comparison.png",dpi=135)
    plt.close(fig)


def distribution_diagnostics(h):
    rows=[]
    prob=h["proper_reference_IQ_bin_probability"][:]
    proper=np.outer(prob,prob)
    rayleigh=np.cumsum(h["proper_reference_rayleigh_bin_probability"][:])
    for m in MODES:
        for band in BANDS:
            data=h[f"{m}/data/{band}"]
            for pop in POPS:
                g=h[f"{m}/{pop}/{band}"]
                joint=g["iq_shape"][:].mean(axis=0)
                acf=g["acf"][:].mean(axis=0)
                residual=acf-data["acf"][:].mean(axis=0)
                phase=g["phase"][:].mean(axis=0)
                rows.append(dict(mode=m,band=band,population=pop,
                    IQ_total_variation_from_proper=.5*(abs(joint-proper).sum()+abs(joint.sum()-proper.sum())),
                    amplitude_CDF_max_diff_from_Rayleigh=np.max(abs(np.cumsum(g["amplitude_shape"][:].mean(axis=0))-rayleigh)),
                    phase_total_variation_from_uniform=.5*abs(phase-1/len(phase)).sum(),
                    ACF_complex_RMSE_vs_data_lags_1_128=np.sqrt(np.mean(abs(residual[1:])**2))))
    return rows


def main(local, light):
    cfg=json.loads((local/"population.json").read_text())
    records=json.loads((local/"block_metrics.json").read_text())
    rows,tails,controls=summarize(records,cfg["config"])
    light.mkdir(exist_ok=True,parents=True)
    write(local/"all_observables.csv",rows)
    write(light/"observables.csv",[r for r in rows if r["observable"] in FOCUS])
    write(light/"tail_counts.csv",tails)
    write(light/"step10a_controls.csv",controls)
    write(light/"population.csv",cfg["events"])
    with h5py.File(local/"statistics.h5","r+") as h:
        for m in MODES:
            for pop in POPS:
                for band,v in cfg["proper_reference_RMS_V"][m].items():
                    h[f"{m}/{pop}/{band}"].attrs["reference"]=v
        write(light/"distribution_diagnostics.csv",distribution_diagnostics(h))
        statistics_plots(h,local)
    light_plot(rows,light)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("local",type=Path)
    parser.add_argument("light",type=Path)
    a=parser.parse_args()
    main(a.local,a.light)
