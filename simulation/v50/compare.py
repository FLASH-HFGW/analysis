"""Homogeneous figure families and quantitative model contrasts on the Step 10C mask."""
import argparse,csv,json,sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import h5py,numpy as np
from scipy.fft import ifft

from v0 import c,b,N,FS,B
sys.path.insert(0,str(b.ROOT/"examples"))
from fit_iq_correlation_decay import fit_upper_envelope

POPS=("data","v0","H","N")
LABELS={"data":"Run 680","v0":"Toy v0","H":"Toy v1 · H","N":"Model N"}
COLOR=dict(zip(POPS,("#007F86","#263952","#7657A6","#D98726")))
BANDS=("full","-500000","-250000","-100000","0","100000","250000","500000")
METRICS=("power_V2","RMS_V","var_I_V2","var_Qhardware_V2","cov_I_Qhardware_V2","pseudo_real_V2",
         "pseudo_imag_V2","pseudo_abs_relative","amplitude_mean_over_RMS","amplitude_fourth_over_RMS4",
         "mean_amplitude_V","amplitude_sd_V","rayleigh_CDF_max_diff","phase_resultant",
         "phase_increment_cos_1","phase_increment_sin_1","acf_real_1","acf_imag_1","acf_abs_1")
FAMILIES={
 "times":"I/Q time series", "iq":"Absolute and normalized I/Q constellations",
 "amplitude":"Amplitude, Rayleigh and phase", "increments":"Circular phase increments",
 "spectra":"Absolute PSD, PSD shape and complementary spectrum", "acf":"Complex autocorrelation",
 "fits":"Upper-maxima correlation fits", "bands":"Full-band and resonance-band statistics"
}


def write(out,name,rows):
    with (out/(name+".csv")).open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def read(path):
    return c.BASE.prior.csv_read(path)


def legacy_values(path,cfg):
    values={}
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            g=values.setdefault((row["mode"],"v0",row["band"]),{})
            for k,val in row.items():
                if val and k not in ("mode","population","band","SPEC","subblock"):
                    g.setdefault(k,[]).append(float(val))
    assert len(values)==24 and all(len(a)==4000 for g in values.values() for a in g.values())
    p=b.ROOT/"simulation/step10c"
    import importlib.util
    spec=importlib.util.spec_from_file_location("report10c",p/"report.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.summary({k:{name:np.array(a) for name,a in g.items()} for k,g in values.items()},cfg)


def snapshots(work,raw,cfg):
    audit=b.read(work/"diagnostics/frequency_sensor_closure_v47_20261117/run00680_raw_check.json")
    prefix=c.events(raw,audit,1)
    try:
        first,info=next(prefix)
    finally:
        prefix.close()
    _,_,definitions=c.plan(work,work/"simulation/step10a",cfg)
    result={}
    with h5py.File(work/"simulation/toy_ODB_cal5_data2_LF_20261116/toy_full_run680.h5") as old:
        for i,m in enumerate(c.MODES):
            mask,_,_,root,_=definitions[m]
            seg=first[:N].astype(float)
            v=old[f"{m}/first_5SPEC_ADC_counts"][:N].astype(float)
            d={"data":b.LSB*(seg[:,2*i]-1j*seg[:,2*i+1]),"v0":b.LSB*(v[:,0]+1j*v[:,1])}
            rng=np.random.default_rng(np.random.SeedSequence([cfg["seed"],i,0]))
            g=(rng.standard_normal(root.shape[1:])+1j*rng.standard_normal(root.shape[1:]))/np.sqrt(2)
            for j,p in enumerate(("H","N")):
                d[p]=b.digitize(ifft((root[j]*g).sum(axis=(0,1)),norm="ortho"))
            result[m]={p:b.projection(z,mask)[0][:200] for p,z in d.items()}
    return result,info


def classify(f):
    if "tau_us" not in f:return "fit failed"
    if f["tau_us"]<.2:return "below sample spacing"
    if f["tau_us"]>=95:return "at or near upper bound"
    if f["r_squared_on_selected_peaks"]<.5:return "poor descriptive fit"
    return "resolved descriptive fit"


def fit(g,window=(.3,4.)):
    try:
        return fit_upper_envelope(np.arange(len(g))/5,g.real,window=window)
    except (ValueError,RuntimeError,FloatingPointError) as err:
        return {"error":str(err)}


def fit_results(h,h0,allg,work,out):
    rows=[]; estimates={}; serialized={}
    phys=b.read(work/"simulation/step6/metrics.json")["mode_results"]
    for m in c.MODES:
        for p in POPS:
            g=allg[m,p,"full"]["acf"]
            val=fit(g)
            estimates[m,p]=val
            if p=="v0":
                groups=np.stack([a[:] for a in h0[f"cluster_acf/{m}"].values()])
            else:
                groups=np.stack([r[f"{m}/{p}/full/acf"][:] for r in h["clusters"].values()])
            np.testing.assert_allclose(groups.mean(axis=0),g,atol=2e-14)
            n=len(groups)
            jk=[fit((n*g-one)/(n-1)) for one in groups]
            valid=[r for r in jk if classify(r)=="resolved descriptive fit"]
            sd={}
            if len(valid)==n and classify(val)=="resolved descriptive fit":
                for name in ("tau_us","amplitude","offset"):
                    a=np.array([r[name] for r in valid])
                    sd[name]=np.sqrt((n-1)*np.mean((a-a.mean())**2))
            windows=[fit(g,w) for w in ((.3,3),(.3,5),(.7,4))]
            cavity=phys[m]["q0"]/(1+phys[m]["kappa1"]+phys[m]["kappa2"])/(np.pi*phys[m]["f0_hz"])*1e6
            rows.append(dict(mode=m,population=p,fit_status=classify(val),window_us="0.3–4",
                             tau_us=val.get("tau_us",""),amplitude=val.get("amplitude",""),offset=val.get("offset",""),
                             r2_selected_maxima=val.get("r_squared_on_selected_peaks",""),
                             tau_jackknife_SE_us=sd.get("tau_us",""),amplitude_jackknife_SE=sd.get("amplitude",""),
                             offset_jackknife_SE=sd.get("offset",""),resolved_jackknife_count=len(valid),
                             selected_maxima=len(val.get("peak_indices",[])),cavity_amplitude_decay_us=cavity,
                             error=val.get("error","")))
            serialized[f"{m}/{p}"]=dict(primary=val,window_sensitivity=windows,jackknife=jk)
    write(out,"fits",rows)
    (out/"fit_details.json").write_text(json.dumps(serialized,indent=2)+"\n")
    return estimates


def diagnostics(g,axis,mask):
    f=axis
    p=g["PSD"]
    a=g["acf"]
    return dict(iq_absolute=g["iq_absolute"],iq_shape=g["iq_shape"],amplitude_absolute=g["amplitude_absolute"],
                amplitude_shape=g["amplitude_shape"],phase=g["phase"],phase_increment_1=g["phase_increment_1"],
                phase_increment_10=g["phase_increment_10"],phase_increment_100=g["phase_increment_100"],
                PSD_absolute=p[mask],PSD_shape=p[mask]/p[mask].sum(),
                ACF_real=a[1:].real,ACF_imag=a[1:].imag,ACF_mod=abs(a[1:]),
                complementary_real=g["complementary"][mask].real,complementary_imag=g["complementary"][mask].imag)


def compare_metrics(allg,obs,tails,f,mask,out):
    rows=[]
    full={key:r for r in obs for key in [(r["mode"],r["population"],r["band"],r["observable"])]}
    for m in c.MODES:
        ref=diagnostics(allg[m,"data","full"],f,mask)
        for p in POPS[1:]:
            x=diagnostics(allg[m,p,"full"],f,mask)
            for k,v in x.items():
                y=ref[k]
                d=np.sqrt(np.mean(abs(v-y)**2))
                shape=k.startswith(("iq","amplitude","phase")) or k=="PSD_shape"
                if shape:
                    d=(abs(v-y).sum()+abs(v.sum()-y.sum()))/2
                rows.append(dict(mode=m,population=p,band="full",observable=k,distance=d,
                                 signed_difference="",difference_over_cluster_SE="",
                                 metric="total variation including outside bins" if shape else "pointwise RMSE (descriptive)"))
            for band in BANDS:
                for name in (*METRICS,"RMS_aggregate_V"):
                    d=full[m,"data",band,name]
                    r=full[m,p,band,name]
                    delta=float(r["mean"])-float(d["mean"])
                    se=np.hypot(float(d["cluster_SE"]),float(r["cluster_SE"]))
                    rows.append(dict(mode=m,population=p,band=band,observable=name,distance=abs(delta),
                                     signed_difference=delta,difference_over_cluster_SE=delta/se if se else "",
                                     metric="absolute difference; descriptive grouped SE"))
    lookup={(r["mode"],r["population"],r["band"],r["threshold_kind"],str(r["multiple_RMS"])):r for r in tails}
    for (m,p,band,kind,t),r in lookup.items():
        if p=="data":continue
        d=lookup[m,"data",band,kind,t]
        for name in ("sample_fraction","episodes"):
            if name=="sample_fraction" and (int(r["estimable"])==0 or int(d["estimable"])==0):
                continue
            delta=float(r[name])-float(d[name])
            rows.append(dict(mode=m,population=p,band=band,observable=f"{kind}_{t}RMS_{name}",
                             distance=abs(delta),signed_difference=delta,difference_over_cluster_SE="",
                             metric="same eligible population; no tail extrapolation"))
    anchor={(r["mode"],r["band"],r["observable"]):r["distance"] for r in rows if r["population"]=="v0"}
    for r in rows:
        orig=anchor.get((r["mode"],r["band"],r["observable"]))
        r["distance_minus_v0"]=r["distance"]-orig if orig is not None else ""
    write(out,"model_evolution",rows)


def plots(m,g,short,ref,axes_data,fitv,obs,tails,out,families=FAMILIES):
    f,mask,amp,iq,phase=axes_data
    span=lambda e:(e[1:]+e[:-1])/2
    ix=np.flatnonzero(mask[np.argsort(f)])
    blocks=[i[:len(i)//128*128].reshape(-1,128) for i in np.split(ix,np.flatnonzero(np.diff(ix)>1)+1) if len(i)>=128]
    sort=np.argsort(f)
    fs=f[sort]
    psd_floor=max(min(g[p]["PSD"][mask].mean() for p in POPS)*.018,1e-20)
    psd_ceiling=max(max(g[p]["PSD"][mask]) for p in POPS)*1.15
    tmax=max(np.max(abs(short[p])) for p in POPS)*1e3*1.1
    max_increment=max(np.max(g[p][f"phase_increment_{lag}"])/np.diff(phase)[0] for p in POPS for lag in (1,10,100))*1.08
    qmax=max(g[p][k].max() for p in POPS for k in ("iq_absolute","iq_shape"))
    cmax=1.1*max(np.max(abs(g[p]["complementary"])) for p in POPS)
    psmax=max(g[p]["PSD"][mask].max()/g[p]["PSD"][mask].mean() for p in POPS)*1.12
    ampmax=max(max(g[p][k])/np.diff(amp)[0] for p in POPS for k in ("amplitude_absolute","amplitude_shape"))*1.1
    phmax=max(max(g[p]["phase"])/np.diff(phase)[0] for p in POPS)*1.15
    target={(r["population"],r["band"],r["observable"]):float(r["mean"])
            for r in obs if r["mode"]==m}
    tail_lookup={(r["population"],str(r["multiple_RMS"])):r for r in tails if r["mode"]==m and r["band"]=="full" and r["threshold_kind"]=="shape"}
    bm=max(target[p,k,"RMS_aggregate_V"] for p in POPS for k in BANDS[1:])*1e3
    pm=max(target[p,k,"pseudo_abs_relative"] for p in POPS for k in BANDS)
    emax=max(int(tail_lookup[p,t]["episodes"]) for p in POPS for t in ("2","3","4","5"))
    for variant in ("all","v0","H","N"):
        use=POPS if variant=="all" else ("data",variant)
        for key,title in families.items():
            shape={"times":(1,2),"iq":(2,len(use)),"amplitude":(2,2),"increments":(1,3),
                   "spectra":(2,2),"acf":(1,3),"fits":(1,2),"bands":(2,2)}[key]
            fig,ax=plt.subplots(*shape,squeeze=False,figsize=(3.8*shape[1],2.8*shape[0]),layout="constrained")
            a=ax.flat
            if key=="iq":
                for k,kind in enumerate(("iq_absolute","iq_shape")):
                    e=iq*(ref*1e3 if k==0 else 1)
                    unit="mV ADC" if k==0 else "own RMS"
                    for j,p in enumerate(use):
                        # Log10 probability per identical 2D histogram cell.
                        ax[k,j].imshow(np.log10(np.maximum(g[p][kind].T,1e-8)),origin="lower",
                                       extent=[e[0],e[-1],e[0],e[-1]],aspect="equal",vmin=-7,vmax=np.log10(qmax))
                        ax[k,j].set(title=LABELS[p] if k==0 else "",xlabel=f"I ({unit})",ylabel=f"Q hardware ({unit})")
            else:
                for p in use:
                    z=g[p]
                    kw=dict(color=COLOR[p],lw=1,label=LABELS[p])
                    if key=="times":
                        t=np.arange(len(short[p]))/5
                        for j,y in enumerate((short[p].real,-short[p].imag)):
                            a[j].plot(t,y*1e3,**kw)
                            a[j].set(title=("I","Q hardware")[j],xlabel="Time in first block (µs)",ylabel="mV ADC",ylim=(-tmax,tmax))
                    elif key=="amplitude":
                        a[0].plot(span(amp)*ref*1e3,z["amplitude_absolute"]/np.diff(amp)/(ref*1e3),**kw)
                        a[1].plot(span(amp),z["amplitude_shape"]/np.diff(amp),**kw)
                        a[2].plot(span(phase),z["phase"]/np.diff(phase),**kw)
                        a[3].semilogy(span(amp),np.where(1-np.cumsum(z["amplitude_shape"])>20/(4000*N),
                                                           1-np.cumsum(z["amplitude_shape"]),np.nan),**kw)
                    elif key=="increments":
                        for j,lag in enumerate((1,10,100)):
                            a[j].plot(span(phase),z[f"phase_increment_{lag}"]/np.diff(phase),**kw)
                            a[j].set(title=f"Lag {lag} samples",xlabel="Circular phase increment (rad)",ylim=(0,max_increment))
                    elif key=="spectra":
                        p0=z["PSD"]
                        for j,y in enumerate((p0,p0/p0[mask].mean(),z["complementary"].real,z["complementary"].imag)):
                            for s,ind in enumerate(blocks):
                                fun=a[j].semilogy if j<2 else a[j].plot
                                fun(fs[ind].mean(axis=1)/1e6,y[sort][ind].mean(axis=1),color=COLOR[p],lw=1,label=LABELS[p] if s==0 else None)
                    elif key=="acf":
                        acf=z["acf"]
                        for j,y in enumerate((acf.real,acf.imag,abs(acf))):
                            a[j].plot(np.arange(len(y))/5,y,**kw)
                            a[j].set(title=("Real","Imaginary","Modulus")[j],xlabel="Lag (µs)",xlim=(0,10),ylim=(-.2 if j<2 else 0,1.02))
                    elif key=="fits":
                        acf=z["acf"].real
                        val=fitv[p]
                        a[0].plot(np.arange(len(acf))[1:]/5,acf[1:],**kw)
                        if "tau_us" in val:
                            a[1].plot(val["peak_lag_us"],val["peak_covariance"],"o",color=COLOR[p],ms=3,label=LABELS[p])
                        if classify(val)=="resolved descriptive fit":
                            t=np.linspace(val["peak_lag_us"][0],4,120)
                            a[1].plot(t,val["offset"]+val["amplitude"]*np.exp(-t/val["tau_us"]),color=COLOR[p])
                    elif key=="bands":
                        a[0].plot(range(7),[1e3*target[p,k,"RMS_aggregate_V"] for k in BANDS[1:]],"o-",ms=4,**kw)
                        a[1].plot(range(8),[target[p,k,"pseudo_abs_relative"] for k in BANDS],"o-",ms=4,**kw)
                        a[2].plot([0],[1e3*target[p,"full","RMS_aggregate_V"]],"o",**kw)
                        rr=[tail_lookup[p,str(t)] for t in (2,3,4,5)]
                        a[3].plot([2,3,4,5],[int(r["episodes"]) for r in rr],"o-",ms=4,**kw)
                if key=="amplitude":
                    rr=span(amp)
                    a[1].plot(rr,2*rr*np.exp(-rr**2),"--",color=".5",label="Proper Rayleigh")
                    a[2].axhline(1/(2*np.pi),color=".5",ls="--")
                    a[3].semilogy(rr,np.exp(-rr**2),"--",color=".5")
                    for j,(x,y) in enumerate((("mV ADC","Density (1/mV)"),("Amplitude / own RMS","Density"),("Phase (rad)","Density"),("Amplitude / own RMS","Empirical CCDF (≥20 samples)"))):
                        a[j].set(xlabel=x,ylabel=y)
                    a[0].set(xlim=(0,5*ref*1e3),ylim=(0,ampmax/ref/1e3))
                    a[1].set(xlim=(0,5),ylim=(0,ampmax))
                    a[2].set(xlim=(-np.pi,np.pi),ylim=(0,phmax))
                    a[3].set(ylim=(2e-8,1),xlim=(0,5))
                if key=="spectra":
                    for j,(label,limit) in enumerate(zip(("PSD (V²/Hz ADC)","PSD / own mean","Re C (V²/Hz)","Im C (V²/Hz)"),
                          ((psd_floor,psd_ceiling),(.02,psmax),(-cmax,cmax),(-cmax,cmax)))):
                        a[j].set(xlabel="Signed IF (MHz)",ylabel=label,ylim=limit,xlim=(-2.5,2.5))
                if key=="fits":
                    a[0].set(xlim=(.2,10),ylim=(-.18,.13),xlabel="Lag (µs)",ylabel="Real ACF")
                    a[1].set(xlim=(.3,4),ylim=(-.025,.16),xlabel="Lag (µs)",ylabel="Selected maxima and fit")
                if key=="bands":
                    a[0].set(xticks=range(7),xticklabels=[str(int(k)//1000) for k in BANDS[1:]],xlabel="Offset (kHz)",ylabel="RMS (mV ADC)",ylim=(0,bm*1.12))
                    a[1].set(xticks=range(8),xticklabels=["Full"]+[str(int(k)//1000) for k in BANDS[1:]],ylabel="Mean |pseudo| / power",ylim=(0,pm*1.12))
                    a[2].set(xticks=[0],xticklabels=["Full-band"],ylabel="RMS (mV ADC)",ylim=(0,tmax))
                    a[3].set(yscale="symlog",ylim=(-.2,emax*1.4),xlabel="Sample threshold / own RMS",ylabel="Episodes (not independent triggers)")
                a[0].legend(fontsize=8)
            fig.suptitle(f"{m} · {title} · "+("all populations" if variant=="all" else LABELS[variant]))
            for ext in ("png","pdf"):
                fig.savefig(out/f"{m}_{key}_{variant}.{ext}",dpi=165)
            plt.close(fig)


def run(work,raw,products):
    root=work/"simulation/step10c"
    cfg=b.read(root/"population.json")["config"]
    hpath=root/"statistics.h5"
    v0path=products/"v0_statistics.h5"
    expected=b.read(root/"sha256.json")
    for n in ("statistics.h5","all_observables.csv","tail_counts.csv","population.json"):
        assert c.BASE.sha(root/n)==expected[n]
    out=products/"figures"
    out.mkdir(exist_ok=False)
    v0rows,v0tail=legacy_values(products/"v0_blocks.csv",cfg)
    obs=read(root/"all_observables.csv")+v0rows
    tails=read(root/"tail_counts.csv")+v0tail
    frozen=work/"simulation/toy_ODB_cal5_data2_LF_20261116"
    saved=b.read(frozen/"metrics.json")["results"]
    legacy=b.read(frozen/"comparison/comparison.json")["modes"]
    historic=[]
    for mode in c.MODES:
        check=next(r["mean"] for r in v0rows if r["mode"]==mode and r["band"]=="full" and r["observable"]=="pre_projection_V2")
        np.testing.assert_allclose(check,float(saved[mode]["rms_v"])**2,rtol=1e-11)
        for pop,key in (("data","data_upper_fit"),("v0","toy_upper_fit")):
            rec=legacy[mode][key]
            historic.append(dict(mode=mode,population=pop,tau_us=rec["tau_us"],amplitude=rec["amplitude"],
                                 offset=rec["offset"],r2_selected_maxima=rec["r_squared_on_selected_peaks"],
                                 status=classify(rec),scope="v49 slide 23 original five-SPEC unmasked comparison"))
    write(products,"observables",obs)
    write(products,"tails",tails)
    write(products,"historical_fits",historic)
    short,info=snapshots(work,raw,cfg)
    with h5py.File(hpath) as h,h5py.File(v0path) as h0:
        f=h["frequency_Hz"][:]
        mask=h["common_mask"][:]
        assert len(f)==N and mask.sum()==251659
        edges=(f,mask,h["amplitude_edges"][:],h["IQ_edges"][:],h["phase_edges"][:])
        allg={}
        for mode in c.MODES:
            for p in POPS:
                g=(h0 if p=="v0" else h)[f"mean/{mode}/{p}/full"]
                allg[mode,p,"full"]={k:v[:] for k,v in g.items()}
                s=allg[mode,p,"full"]["PSD"]
                assert np.count_nonzero(s[~mask])==0
                rms=next(float(r["mean"]) for r in obs if r["mode"]==mode and r["population"]==p
                         and r["band"]=="full" and r["observable"]=="RMS_aggregate_V")
                np.testing.assert_allclose(FS*np.mean(s),rms**2,rtol=5e-11)
        fitv=fit_results(h,h0,allg,work,products)
        compare_metrics(allg,obs,tails,f,mask,products)
        for mode in c.MODES:
            ref=b.read(root/"population.json")["proper_reference_RMS_V"][mode]["full"]
            plots(mode,{p:allg[mode,p,"full"] for p in POPS},short[mode],ref,edges,
                  {p:fitv[mode,p] for p in POPS},obs,tails,out)
            for p in POPS:
                z=short[mode][p]
                np.savez_compressed(products/f"{mode}_{p}_time_panel.npz",I_ADC_V=z.real,
                                    Qhardware_ADC_V=-z.imag,time_s=np.arange(len(z))/FS)
    assert len(list(out.glob("*.png")))==96 and len(list(out.glob("*.pdf")))==96
    (products/"validation.json").write_text(json.dumps(dict(SPECs=1000,blocks_per_mode_population=4000,
        samples_per_mode_population=1048576000,post_ADC_common_bins=251659,matched_PSD_RMS_passed=True,
        historical_v0_full_RMS_reproduced=True,v0_first_five_SPEC_exact=b.read(products/"validation_v0.json"),
        snapshot_SPEC=info,figure_count=96,reused_approved_full_populations=["data","H","N"],
        input_sha256={str(p):c.BASE.sha(p) for p in (hpath,root/"all_observables.csv",root/"tail_counts.csv",
            root/"population.json",frozen/"metrics.json",frozen/"comparison/comparison.json",v0path)}),indent=2)+"\n")


def refresh_fits(work,products):
    source=work/"simulation/step10c"
    obs=read(products/"observables.csv")
    tails=read(products/"tails.csv")
    with h5py.File(source/"statistics.h5") as h,h5py.File(products/"v0_statistics.h5") as h0:
        g={(m,p,"full"):{k:v[:] for k,v in (h0 if p=="v0" else h)[f"mean/{m}/{p}/full"].items()}
           for m in c.MODES for p in POPS}
        fits=fit_results(h,h0,g,work,products)
        axes=tuple(h[k][:] for k in ("frequency_Hz","common_mask","amplitude_edges","IQ_edges","phase_edges"))
        for m in c.MODES:
            samples={}
            for p in POPS:
                with np.load(products/f"{m}_{p}_time_panel.npz") as z:
                    samples[p]=z["I_ADC_V"]-1j*z["Qhardware_ADC_V"]
            rms=b.read(source/"population.json")["proper_reference_RMS_V"][m]["full"]
            plots(m,{p:g[m,p,"full"] for p in POPS},samples,rms,axes,{p:fits[m,p] for p in POPS},
                  obs,tails,products/"figures",families={"fits":FAMILIES["fits"]})


if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("work","raw","products"):
        p.add_argument(x,type=Path)
    p.add_argument("--fits-only",action="store_true",help="Refresh only matched fit tables and plots without opening raw data")
    a=p.parse_args()
    if a.fits_only:
        refresh_fits(a.work,a.products)
    else:
        run(a.work,a.raw,a.products)
