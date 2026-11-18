"""Read-only spectral residual diagnostics from previously reduced products."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MODES = ("TM010", "TM011", "TM012")
POPS = ("data", "H", "N")
LIMITS = (.1, .25, .5, 1., 1.25, 1.75, 2., 2.25, 2.5)
COLORS = ("#007f86", "#7657a6", "#d98726")


def csv_read(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write(out, name, rows):
    with (out/(name+".csv")).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows({k: f"{v:.12g}" if isinstance(v, (float, np.floating)) else v
                     for k,v in r.items()} for r in rows)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(2**20), b""):
            h.update(chunk)
    return h.hexdigest()


def interval(f, lo, hi):
    return (abs(f) >= lo*1e6) & ((abs(f) < hi*1e6) | ((hi == 2.5) & (abs(f) == hi*1e6)))


def ratio(c, p, use):
    return c[...,use].sum(axis=-1)/p[...,use].sum(axis=-1)


def iq(data, pop, mode):
    i = data["var_I_V2"]
    q = data["var_Qhardware_V2"]
    v = data["cov_I_Qhardware_V2"]
    cov = np.array([[i,v],[v,q]])
    eig, axes = np.linalg.eigh(cov)
    major = axes[:,1]
    theta = (np.degrees(np.arctan2(major[1],major[0]))+90)%180-90
    rho = v/np.sqrt(i*q)
    eta = complex(i-q,-2*v)/(i+q)
    return dict(mode=mode,population=pop,var_I_V2=i,var_Qhardware_V2=q,cov_I_Qhardware_V2=v,
                I_over_Q_RMS=np.sqrt(i/q),rho_I_Qhardware=rho,
                equivalent_phase_error_hardware_deg=-np.degrees(np.arcsin(rho)),
                equivalent_phase_error_Qeff_deg=np.degrees(np.arcsin(rho)),
                major_RMS_V=np.sqrt(eig[1]),minor_RMS_V=np.sqrt(eig[0]),major_axis_deg=theta,
                pseudo_real_relative=eta.real,pseudo_imag_relative=eta.imag),eta


def constant_test(m,pop,f,mask,observed,p,eta,c,interval_rows):
    """Moment equivalent constant map, not used to calibrate or predict in volts."""
    mirror=(-np.arange(len(f)))%len(f)
    power=observed.sum()
    target=(observed+observed[mirror])/(2*power)
    observed_odd=(observed-observed[mirror])/(2*power)
    reference=(p+p[mirror])/(2*p.sum())
    orientation=np.sqrt(1-abs(eta)**2)
    odd=orientation*(p-p[mirror])/(2*p.sum())
    # The sign is determined only if an orientation-preserving map is assumed.
    residual_c=c/power-eta*reference
    out=dict(mode=m,input=pop,moment_eta_real=eta.real,moment_eta_imag=eta.imag,
             odd_scale_preserving=orientation,sym_PSD_TV=.5*sum(abs(target-reference)),
             odd_L1_preserving=sum(abs(observed_odd-odd)),odd_L1_reversing=sum(abs(observed_odd+odd)),
             complementary_L1_over_data_power=sum(abs(residual_c[mask])))
    for lo,hi in zip(LIMITS,LIMITS[1:]):
        use=interval(f,lo,hi)&mask
        interval_rows.append(dict(mode=m,input=pop,abs_IF_low_MHz=lo,abs_IF_high_MHz=hi,
                                  data_sym_power_fraction=target[use].sum(),
                                  input_sym_power_fraction=reference[use].sum(),
                                  data_eta_real=ratio(c,observed,use).real,
                                  data_eta_imag=ratio(c,observed,use).imag,
                                  constant_eta_real=eta.real,constant_eta_imag=eta.imag))
    return out


def eta_intervals(f,fc,mask,p,c,gp,gc,m,pop):
    rows=[]
    use_all=abs(fc)>=.1e6
    whole=ratio(gc,gp,use_all)
    for lo,hi in zip(LIMITS,LIMITS[1:]):
        use=interval(f,lo,hi)&mask
        coarse=interval(fc,lo,hi)
        # Group bins are 128-bin averages, assigned by their centers.
        z=ratio(c,p,use)
        grouped=ratio(gc,gp,coarse)
        delta=grouped-whole
        rows.append(dict(mode=m,population=pop,abs_IF_low_MHz=lo,abs_IF_high_MHz=hi,
                         bins=int(use.sum()),group_count=len(grouped),
                         PSD_interval_fraction=p[use].sum()/p.sum(),
                         eta_real=z.real,eta_imag=z.imag,
                         grouped_eta_real_mean=grouped.real.mean(),grouped_eta_imag_mean=grouped.imag.mean(),
                         grouped_eta_real_SD=grouped.real.std(ddof=1),grouped_eta_imag_SD=grouped.imag.std(ddof=1),
                         paired_delta_real_mean=delta.real.mean(),paired_delta_imag_mean=delta.imag.mean(),
                         paired_delta_real_SE=delta.real.std(ddof=1)/np.sqrt(len(delta)),
                         paired_delta_imag_SE=delta.imag.std(ddof=1)/np.sqrt(len(delta))))
    return rows


def components(f,p,c,mode,model,old_rows):
    rows=[]
    df=abs(f[1]-f[0])
    for lo,hi in ((1.75,2.5),(1.75,2.),(2.,2.25),(2.25,2.5)):
        q=interval(f,lo,hi)
        comp=c[:,:,q].sum(axis=-1)*df
        assert comp.shape==(3,3)
        data=p[q].sum()*df
        r=[r for r in old_rows if lo*1e6<=abs(float(r["IF_hz"]))<=hi*1e6 and r["common_mask"]=="1"]
        model9={"H":"hybrid","N":"nominal"}[model]
        step9_power=sum(sum(float(t[f"{model9}{s}_{part}"]) for s in ("","_alias")
                     for part in ("main","image","cavity")) for t in r)*5e6/16383
        total=comp.sum()
        rows.append(dict(mode=mode,model=model,abs_IF_low_MHz=lo,abs_IF_high_MHz=hi,
                         observed_V2=data,ADC_main_direct_V2=comp[1,0],RF_image_direct_V2=comp[1,1],
                         ADC_alias_main_V2=comp[[0,2],0].sum(),ADC_alias_RF_image_V2=comp[[0,2],1].sum(),
                         cavity_direct_V2=comp[1,2],cavity_alias_V2=comp[[0,2],2].sum(),
                         total_10A_V2=total,total_9D_V2=step9_power,
                         observed_over_10A_dB=10*np.log10(data/total)))
    return rows


def run(work,out):
    out.mkdir(parents=True,exist_ok=False)
    cdir=work/"step10c"
    hpath=cdir/"statistics.h5"
    apath=work/"step10a/series.h5"
    moments=cdir/"all_observables.csv"
    psd9=ROOT/"docs/step9d/psd.csv"
    hardware=ROOT/"docs/step9b/manufacturer.json"
    expected=json.loads((cdir/"sha256.json").read_text())
    assert sha(hpath)==expected[hpath.name] and sha(moments)==expected[moments.name]
    assert sha(apath)==json.loads((apath.parent/"sha256.json").read_text())[apath.name]
    old=csv_read(psd9)
    vals={(r["mode"],r["population"],r["observable"]):float(r["mean"])
          for r in csv_read(moments) if r["band"]=="full"}
    fig,axes=plt.subplots(3,2,figsize=(10,7.3),layout="constrained")
    high,axs=plt.subplots(1,3,figsize=(11,3.3),layout="constrained")
    eta_rows,cov_rows,test_rows,test_bands,part_rows,curves=[],[],[],[],[],[]
    with h5py.File(hpath) as h, h5py.File(apath) as a:
        f=h["frequency_Hz"][:]
        fc=h["cluster_frequency_Hz"][:]
        mask=h["common_mask"][:]
        mirror=(-np.arange(len(f)))%len(f)
        np.testing.assert_array_equal(f,a["signed_IF_Hz"][:])
        cluster_ids=list(h["clusters"])
        high_bins=(fc>=1.75e6)&(fc<2.5e6)
        for j,m in enumerate(MODES):
            for pop,color in zip(POPS,COLORS):
                g=h[f"mean/{m}/{pop}/full"]
                p,c=g["PSD"][:],g["complementary"][:]
                clusters=[h[f"clusters/{i}/{m}/{pop}/full"] for i in cluster_ids]
                gp=np.stack([u["PSD"][:] for u in clusters])
                gc=np.stack([u["complementary"][:] for u in clusters])
                row,eta=iq({k:vals[m,pop,k] for k in ("var_I_V2","var_Qhardware_V2","cov_I_Qhardware_V2")},pop,m)
                np.testing.assert_allclose(eta,c.sum()/p.sum(),rtol=2e-9,atol=5e-12)
                cov_rows.append(row)
                eta_rows.extend(eta_intervals(f,fc,mask,p,c,gp,gc,m,pop))
                ix=np.flatnonzero(mask&(f>=0))
                ix=ix[:len(ix)//128*128].reshape(-1,128)
                mf=f[ix].mean(axis=1)/1e6
                z=2*c[ix].sum(axis=1)/(p[ix]+p[mirror[ix]]).sum(axis=1)
                for x,y in zip(mf,z):
                    curves.append(dict(mode=m,population=pop,abs_IF_MHz=x,eta_real=y.real,eta_imag=y.imag))
                for k,y in enumerate((z.real,z.imag)):
                    axes[j,k].plot(mf,y,color=color,lw=.8,label=pop)
                    r=[r for r in eta_rows if r["mode"]==m and r["population"]==pop]
                    field=("real","imag")[k]
                    axes[j,k].errorbar([(r0["abs_IF_low_MHz"]+r0["abs_IF_high_MHz"])/2 for r0 in r],
                                      [r0["eta_"+field] for r0 in r],
                                      yerr=[r0["grouped_eta_"+field+"_SD"] for r0 in r],
                                      fmt=".",color=color,capsize=2,alpha=.7)
                # Paired positive and negative mean power, no renormalization.
                nbin=len(f)//128
                sym=(p+p[mirror])/2
                sym=np.fft.fftshift(sym).reshape(nbin,128).mean(axis=1)
                axs[j].semilogy(fc[high_bins]/1e6,sym[high_bins],color=color,label=pop)
                if pop=="data":
                    observed,complement,eta_data=p,c,eta
                else:
                    theory=h[f"analytical/{m}/{pop}/PSD"][:]
                    test_rows.append(constant_test(m,pop,f,mask,observed,theory,eta_data,complement,test_bands))
                    cc=a[f"{m}/{pop}/expected_component_PSD_V2_Hz"][:]
                    np.testing.assert_allclose(cc.sum(axis=(0,1)),theory,rtol=1e-12,atol=1e-25)
                    part_rows.extend(components(f,observed,cc,m,pop,[r for r in old if r["mode"]==m]))
            for k,lab in enumerate(("Re η","Im η")):
                axes[j,k].set(title=m,ylabel=lab)
                axes[j,k].axhline(0,color=".6",lw=.5)
            axs[j].set(title=m,xlabel="|IF| (MHz)")
    for ax in axes[-1]:
        ax.set_xlabel("|IF| (MHz)")
    axes[0,0].legend(fontsize=8)
    axs[0].set_ylabel("Symmetrized PSD (V²/Hz ADC)")
    axs[0].legend(fontsize=8)
    lp=json.loads(hardware.read_text())["BLP-1.9+"]
    twin=axs[-1].twinx()
    freqs=np.linspace(1.75,2.5,100)
    twin.plot(freqs,np.interp(freqs,lp["f_MHz"],lp["loss_dB"]),ls=":",color=".42")
    twin.set_ylabel("BLP typical loss (dB)",color=".42")
    fig.savefig(out/"eta.png",dpi=120)
    high.savefig(out/"high_IF.png",dpi=120)
    plt.close("all")
    for name,rows in (("eta_intervals",eta_rows),("eta_curves",curves),("iq_covariance",cov_rows),
                      ("constant_map",test_rows),("constant_map_intervals",test_bands),("high_IF_components",part_rows)):
        write(out,name,rows)
    (out/"inputs.json").write_text(json.dumps({str(p):sha(p) for p in (hpath,apath,moments,psd9,hardware)},indent=2)+"\n")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("simulation",type=Path)
    parser.add_argument("out",type=Path)
    args=parser.parse_args()
    run(args.simulation,args.out)
