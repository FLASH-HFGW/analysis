"""Conditional HFGW sensitivity and absolute PBH benchmarks for QUAX GHz."""
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
from scipy.constants import G, c, mu_0, astronomical_unit, parsec
from scipy.integrate import quad, trapezoid
from scipy.special import erfcx

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location("step9d",ROOT/"docs/step9d/build.py")
ref=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)
prior=ref.prior
MSUN=1.988409870698051e30
MODES=prior.MODES
MODELS=("H","N")
FS=ref.FS
R=50
COLORS=("#007f86","#7657a6","#d98726")


def write(out,name,rows):
    with (out/(name+".csv")).open("w",newline="") as s:
        w=csv.DictWriter(s,fieldnames=list(rows[0]),lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as s:
        for b in iter(lambda:s.read(2**20),b""):h.update(b)
    return h.hexdigest()


def source(m,f,distance):
    """m is the individual mass in solar masses. Return face-on polarization peak."""
    tau=G*MSUN*(2**(-1/5)*m)/c**3
    chirp=96/5*np.pi**(8/3)*tau**(5/3)*f**(11/3)
    h=4*tau**(5/3)*(np.pi*f)**(2/3)*c/distance
    isco=c**3/(6**1.5*np.pi*G*2*m*MSUN)
    return h,chirp,isco


def lorentz(nu,b):
    return 1/(1+2j*nu/b)


def envelope(t,rate,gamma):
    """Causal exponential convolution of a locally linear, horizon-free chirp."""
    root=np.sqrt(-1j*np.pi*rate)
    z=(gamma+2j*np.pi*rate*t)/(2*root)
    return gamma*np.sqrt(np.pi)/(2*root)*np.exp(1j*np.pi*rate*t*t)*erfcx(z)


def transfer(i,arch,p,x,k,cfg,gain):
    mode=MODES[i]
    f0=p["f0_hz"]
    fc=f0-round((prior.SCI["LO1_MHz"]+prior.SCI["LO2_MHz"][i])*1e6)
    beta=p["kappa2"]/(1+p["kappa1"]+p["kappa2"])
    ql=p["q0"]/(1+p["kappa1"]+p["kappa2"])
    b=f0/ql
    K=beta*(2*np.pi*f0)/(2*mu_0)*cfg["field_reference_T"]**2*ql*cfg["volume_m3"]*cfg["conditional_CGW"]
    f=arch["frequency_Hz"][:]
    nu=f-fc
    mask=arch["common_mask"][:]
    direct=np.array([np.interp(f,x,k,left=np.nan,right=np.nan)*.01,
                     10**(prior.response(prior.SCI,i,f)["summed_IQ_dB"]/20)])
    valid=mask&np.isfinite(direct).all(axis=0)&(f>0)
    # Conditional upper RF input channel only. Negative, aliased and image inputs
    # are excluded from coherent gain. Their noise remains in the observed PSD.
    g=direct*np.sqrt(R*10**(gain/10)*K)
    measured=arch[f"mean/{mode}/data/full/PSD"][:]
    order=np.argsort(f)
    ix=order[valid[order]]
    nbin=128
    use=ix[:len(ix)//nbin*nbin].reshape(-1,nbin)
    sf=f[use].mean(axis=1)
    smooth=np.interp(f,sf,measured[use].mean(axis=1))
    valid&=(f>=sf[0])&(f<=sf[-1])
    assert valid[np.argmin(abs(nu))]
    L=lorentz(nu,b)
    return dict(f=f,fc=fc,f0=f0,nu=nu,b=b,ql=ql,beta=beta,K=K,g=g,direct=direct,
                valid=valid,smooth=smooth,L=L,Fs=FS,peak_gain=g[:,np.argmin(abs(nu))],
                cavity=p["temperature_k"],gain=gain)


def plots(out,asd,mono,trans,reach):
    fig,axes=plt.subplots(1,3,figsize=(12,3.5),layout="constrained")
    for i,(mode,ax) in enumerate(zip(MODES,axes)):
        for m,col in zip(MODELS,COLORS):
            rr=[r for r in asd if r["mode"]==mode and r["model"]==m]
            ax.semilogy([r["offset_Hz"]/1e3 for r in rr],[r["complex_strain_ASD_per_sqrt_Hz"] for r in rr],color=col,label=m)
        ax.set(title=mode,xlabel="RF offset (kHz)",ylabel="Equivalent strain ASD (1/√Hz)")
    axes[0].legend()
    save(fig,out,"strain_asd")
    for name,rows,x,ys,xlabel,ylabel in (
        ("monochromatic",mono,"seconds",("h_rho1_white_center",),"Coherent time (s)","Peak strain at ρ = 1"),
        ("transient",trans,"seconds",("h_rho1_rectangular",),"Rectangular strain duration (s)","Peak strain at ρ = 1"),
        ("reach",reach,"individual_mass_Msun",("reach_rho1_AU","reach_rho5_AU"),"Individual PBH mass (solar masses)","Conditional distance (AU)")):
        fig,axes=plt.subplots(1,3,figsize=(12,3.5),layout="constrained")
        for mode,ax in zip(MODES,axes):
            for m,col in zip(MODELS,COLORS):
                rr=[r for r in rows if r["mode"]==mode and r["model"]==m]
                for j,y in enumerate(ys):
                    ax.loglog([r[x] for r in rr],[r[y] for r in rr],color=col,ls="-" if j==0 else "--",
                              marker="." if name!="reach" else None,label=f"{m} · ρ={5 if j else 1}")
            ax.set(title=mode,xlabel=xlabel,ylabel=ylabel)
        axes[0].legend(fontsize=8)
        save(fig,out,name)


def save(fig,out,name):
    fig.savefig(out/(name+".png"),dpi=200)
    fig.savefig(out/(name+".pdf"))
    plt.close(fig)


def benchmark(out,kind,m,t,cfg,noise,checks):
    f,fc,nu,b=t["f"],t["fc"],t["nu"],t["b"]
    h,rate,isco=source(m,t["f0"],cfg["distance_AU"]*astronomical_unit)
    gamma=np.pi*b
    crossing=b/rate
    tau=1/gamma
    power=t["K"]*h*h
    energy=power*np.pi*b/(2*rate)
    ii=np.argsort(nu)
    # Independent quadrature validates the area and the impulse/adiabatic scales.
    u=np.linspace(-1000,1000,40001)
    area=trapezoid(1/(1+u*u),u)*b/2
    assert abs(area/(np.pi*b/2)-1)<.001
    limit=max(100*crossing,25*tau)
    dense=np.linspace(-limit,limit,80001)
    physical_area=trapezoid(abs(envelope(dense,rate,gamma))**2,dense)
    exact_area=np.pi*b/(2*rate)
    assert abs(physical_area/exact_area-1)<.006
    checks[kind+"_time_integral_over_Lorentz_energy"]=float(physical_area/exact_area)
    if kind=="slow":
        adiabatic=abs(envelope(0,rate,gamma))
        assert abs(adiabatic-1)<1e-4
        checks["slow_center_dynamic_over_static_amplitude"]=float(adiabatic)
    elif kind=="fast":
        # Impulse response immediately after the crossing, several coherence times later.
        tt=.32*tau
        impulse=gamma/np.sqrt(rate)*np.exp(-gamma*tt)
        ratio=abs(envelope(tt,rate,gamma))/impulse
        assert abs(ratio-1)<.08
        checks["fast_ring_vs_impulse_amplitude_at_0p32tau"]=float(ratio)
    else:
        direct=complex(*(quad(lambda v:np.exp(-v)*fn(np.pi*rate*(v*tau)**2),0,25,
                        epsabs=1e-10,limit=1000)[0] for fn in (np.cos,np.sin)))
        error=abs(envelope(0,rate,gamma)-direct)
        assert error<3e-7
        checks["intermediate_direct_complex_convolution_error"]=float(error)
    xphys=np.linspace(-5*max(crossing,tau),10*max(crossing,tau),3001)
    y=envelope(xphys,rate,gamma)
    assert np.isfinite(y).all()
    time=np.arange(-4096,4096)/FS
    result=[]
    fig,axes=plt.subplots(3,2,figsize=(11,8),layout="constrained")
    source_t=np.linspace(-3*crossing,3*crossing,401)
    freq_inc=t["f0"]+rate*source_t
    strain_inc=source(m,freq_inc,cfg["distance_AU"]*astronomical_unit)[0]
    axes[0,0].plot(source_t*1e6,(freq_inc-t["f0"])/1e3,color=COLORS[0],label="Frequency offset")
    axes[0,0].set(xlabel="Time from passage (µs)",ylabel="RF offset (kHz)")
    ax=axes[0,0].twinx()
    ax.plot(source_t*1e6,strain_inc,ls=":",color=COLORS[1])
    ax.set_ylabel("Incident polarization strain")
    axes[0,1].plot(xphys*1e6,power*abs(y)**2,color=COLORS[0],label="Dynamic")
    axes[0,1].plot(xphys*1e6,power*abs(lorentz(rate*xphys,b))**2,ls=":",color=COLORS[2],label="Instantaneous steady state")
    axes[0,1].set(xlabel="Time from passage (µs)",ylabel="Readout power (W)")
    axes[0,1].legend(fontsize=8)
    for j,(name,col) in enumerate(zip(MODELS,COLORS)):
        valid=t["valid"]
        # Local linear chirp has exactly the Fresnel spectrum h/sqrt(rate).
        sf=np.zeros(len(f),complex)
        sf[valid]=h/np.sqrt(rate)*np.exp(1j*np.pi/4-1j*np.pi*nu[valid]**2/rate)*t["g"][j,valid]*t["L"][valid]
        df=FS/len(f)
        rho=np.sqrt(2*df*np.sum(abs(sf[valid])**2/t["smooth"][valid]))
        if kind=="slow":
            # Adiabatic electronics at the instantaneous IF for this short snapshot.
            gg=np.interp(rate*time,nu[ii],t["g"][j,ii])
            signal=gg*h*envelope(time,rate,gamma)*np.exp(2j*np.pi*fc*time)
        else:
            ss=np.fft.fftshift(np.fft.ifft(sf))*FS
            np.testing.assert_allclose(np.sum(abs(ss)**2)/FS,df*np.sum(abs(sf)**2),rtol=2e-12)
            center=len(ss)//2
            signal=ss[center-4096:center+4096]
        cn=noise[f"TM010/{name}/adc_counts_I_Qhardware"][:len(time)].astype(float)
        z=(cn[:,0]-1j*cn[:,1])*(4/65535)
        injection=signal*(cfg["matched_filter_reference_SNR"]/rho)
        axes[1,0].plot(time*1e6,abs(signal)*1e6,color=col,label=name)
        keep=abs(time)<(20e-6 if kind!="slow" else 60e-6)
        if j==0:
            px=axes[1,0].twinx()
            chosen=keep & (abs(signal)>.03*np.max(abs(signal)))
            px.plot(time[chosen]*1e6,np.angle(signal[chosen]*np.exp(-2j*np.pi*fc*time[chosen])),ls=":",lw=.7,color=".4")
            px.set_ylabel("H carrier-removed phase (rad)",color=".4")
            axes[1,1].plot(time[keep]*1e6,signal.real[keep]*1e6,lw=.7,label="I")
            axes[1,1].plot(time[keep]*1e6,-signal.imag[keep]*1e6,lw=.7,label="Q hardware")
            axes[2,0].plot(time[keep]*1e6,(z+signal).real[keep]*1e3,lw=.7,label="Physical signal + H noise")
            axes[2,0].plot(time[keep]*1e6,(z+injection).real[keep]*1e3,lw=.7,alpha=.55,label="ρ=5 illustrative + same noise")
            axes[2,1].semilogy(nu[ii][valid[ii]]/1e3,abs(sf[ii][valid[ii]])**2,color=col,label=name)
        else:
            axes[2,1].semilogy(nu[ii][valid[ii]]/1e3,abs(sf[ii][valid[ii]])**2,color=col,label=name)
        np.savez_compressed(out/f"{kind}_{name}_ADC.npz",time_s=time,signal_ADC_V=signal,
                            signal_amplitude_ADC_V=abs(signal),signal_phase_rad=np.angle(signal),
                            simulated_noise_ADC_V=z,physical_plus_noise_ADC_V=z+signal,
                            illustrative_plus_noise_ADC_V=z+injection,illustrative_isolated_ADC_V=injection,
                            analog_cavity_time_s=xphys,cavity_complex_sqrt_W=np.sqrt(power)*y,
                            incident_time_s=source_t,incident_frequency_Hz=freq_inc,incident_strain=strain_inc,
                            template_frequency_Hz=f,template_ADC_V_s=sf,measured_noise_V2_per_Hz=t["smooth"])
        result.append(dict(kind=kind,mode="TM010",model=name,individual_mass_Msun=m,
                           total_mass_Msun=2*m,chirp_mass_Msun=2**(-1/5)*m,isco_Hz=isco,
                           center_strain=h,chirp_Hz_per_s=rate,crossing_s=crossing,amplitude_tau_s=tau,
                           crossing_over_tau=crossing/tau,steady_port_W=power,
                           peak_dynamic_port_W=power*np.max(abs(y)**2),energy_port_J=energy,
                           peak_snapshot_ADC_V=np.max(abs(signal)),ideal_snr_1AU=rho,
                           modeled_port_energy_fraction=(df*np.sum(abs(t["L"][valid])**2))/(np.pi*b/2),
                           illustrative_rho5_distance_AU=rho/5*cfg["distance_AU"],
                           illustrative_rho5_peak_strain=h*5/rho))
    axes[1,0].set(xlabel="ADC snapshot time (µs)",ylabel="Isolated amplitude (µV)")
    axes[1,1].set(xlabel="Time (µs)",ylabel="Isolated H I/Q (µV ADC)")
    axes[2,0].set(xlabel="Time (µs)",ylabel="I with simulated noise (mV ADC)")
    axes[2,1].set(xlabel="RF offset (kHz)",ylabel="Template energy spectrum (V² s²)",xlim=(-650,650))
    for ax in (axes[1,0],axes[1,1],axes[2,0],axes[2,1]):
        ax.legend(fontsize=7)
    fig.suptitle(f"TM010 · {kind} inspiral · physical normalization at 1 AU")
    save(fig,out,kind)
    return result


def run(work,out,cfgfile):
    cfg=json.loads(cfgfile.read_text())
    out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(HERE/"evidence.json",out/"thesis_and_BOR_evidence.json")
    shutil.copy2(HERE/"README.md",out/"README.md")
    shutil.copy2(cfgfile,out/"config.json")
    phy=work/"simulation/step6/metrics.json"
    cal=work/"diagnostics/normalization_audit_20261114/calibration_reconstruction.json"
    fit=ROOT/"docs/step9a/vna/fits.csv"
    archive=work/"simulation/step10c/statistics.h5"
    noise_path=work/"simulation/step10a/series.h5"
    source_rows=prior.json_read(cal)
    physical=prior.json_read(phy)["mode_results"]
    gains={r["mode"]:float(r["L5_dB"])+36 for r in prior.csv_read(fit) if r["fit"]=="free_eq69"}
    asd,mono,trans,reach,pars,checks=[],[],[],[],[],{}
    with h5py.File(archive) as arch,h5py.File(noise_path) as noise:
        for i,m in enumerate(MODES):
            x,k=prior.curve(source_rows,m)
            t=transfer(i,arch,physical[m],x,k,cfg,gains[m])
            f,nu,b=t["f"],t["nu"],t["b"]
            valid=t["valid"]
            at=np.argmin(abs(nu))
            pars.append(dict(mode=m,RF_Hz=t["f0"],physical_IF_Hz=t["fc"],B_rms_reference_T=cfg["field_reference_T"],
                             V_m3=cfg["volume_m3"],CGW_reference=cfg["conditional_CGW"],
                             Q0=physical[m]["q0"],QL=t["ql"],kappa1=physical[m]["kappa1"],kappa2=physical[m]["kappa2"],
                             kappa2_over_total=t["beta"],bandwidth_Hz=b,amplitude_tau_s=1/(np.pi*b),
                             cavity_wall_proxy_K=t["cavity"],VNA_plus_FET_dB=t["gain"],K_port_W_per_h2=t["K"]))
            assert np.isclose(abs(lorentz(b/2,b))**2,.5)
            for j,name in enumerate(MODELS):
                g=t["g"][j]
                coeff=abs(g[valid]*t["L"][valid])**2/t["smooth"][valid]
                vnu=nu[valid]
                delta=FS/len(f)
                normal=np.sqrt(t["smooth"][at])/g[at]
                groups=arch["clusters"]
                ps=[]
                # Group means were stored in the matching shifted 128-bin grid.
                stencil=np.argmin(abs(arch["cluster_frequency_Hz"][:]-t["fc"]))
                for node in groups.values():
                    ps.append(node[f"{m}/data/full/PSD"][stencil])
                for idx in np.flatnonzero(valid)[::128]:
                    asd.append(dict(mode=m,model=name,RF_Hz=t["f0"]+nu[idx],offset_Hz=nu[idx],
                                    PSD_ADC_V2_per_Hz=t["smooth"][idx],
                                    port_PSD_W_per_Hz=t["smooth"][idx]/(R*10**(gains[m]/10)*t["direct"][j,idx]**2),
                                    complex_strain_ASD_per_sqrt_Hz=np.sqrt(t["smooth"][idx])/abs(g[idx]*t["L"][idx])))
                asd.append(dict(mode=m,model=name,RF_Hz=t["f0"],offset_Hz=0.,PSD_ADC_V2_per_Hz=t["smooth"][at],
                                port_PSD_W_per_Hz=t["smooth"][at]/(R*10**(gains[m]/10)*t["direct"][j,at]**2),
                                complex_strain_ASD_per_sqrt_Hz=normal))
                for T in cfg["monochromatic_seconds"]:
                    mono.append(dict(mode=m,model=name,seconds=T,ENBW_Hz=1/T,
                                     center_complex_strain_ASD=normal,
                                     PSD_cluster_relative_SE=np.std(ps,ddof=1)/np.sqrt(len(ps))/np.mean(ps),
                                     VNA_stat_SE_dB=next(float(r["L5_stat_se_dB"]) for r in prior.csv_read(fit)
                                                         if r["mode"]==m and r["fit"]=="free_eq69"),
                                     h_rho1_white_center=normal/np.sqrt(2*T),h_rho5_white_center=5*normal/np.sqrt(2*T)))
                for T in cfg["transient_seconds"]:
                    weight=(T*np.sinc(vnu*T))**2
                    value=2*delta*np.dot(weight,coeff)
                    trans.append(dict(mode=m,model=name,seconds=T,h_rho1_rectangular=1/np.sqrt(value),
                                      h_rho5_rectangular=5/np.sqrt(value)))
                for mass in np.geomspace(cfg["pbh_individual_mass_min_Msun"],cfg["pbh_individual_mass_max_Msun"],81):
                    h,d,isco=source(mass,t["f0"],astronomical_unit)
                    assert isco>t["f0"]+np.max(abs(vnu))
                    rho=h*np.sqrt(2*delta*np.sum(coeff)/d)
                    reach.append(dict(mode=m,model=name,individual_mass_Msun=mass,total_mass_Msun=2*mass,
                                      chirp_rate_Hz_s=d,h_at_1AU=h,ISCO_Hz=isco,crossing_s=b/d,
                                      crossing_over_tau=np.pi*b*b/d,reach_rho1_AU=rho,reach_rho5_AU=rho/5))
                # Convergence of the readout-weighted Fresnel integral at 2x bin width.
                sorted_coeff=coeff[np.argsort(vnu)]
                rel=abs(2*sorted_coeff[::2].sum()/sorted_coeff.sum()-1)
                assert rel<.001
                checks[f"{m}_{name}_matched_grid_relative"]=rel
            if i==0:
                bench=[]
                _,rate_ref,_=source(1e-15,t["f0"],astronomical_unit)
                mid=1e-15*(np.pi*b*b/rate_ref)**.6
                for label,mass in (("slow",cfg["pbh_individual_mass_min_Msun"]),("intermediate",mid),
                                   ("fast",cfg["fast_benchmark_individual_Msun"])):
                    bench.extend(benchmark(out,label,mass,t,cfg,noise,checks))
    asd.sort(key=lambda r:(r["mode"],r["model"],r["offset_Hz"]))
    for name,rr in (("apparatus",pars),("strain_asd",asd),("monochromatic",mono),
                    ("transient",trans),("reach",reach),("benchmarks",bench)):
        write(out,name,rr)
    plots(out,asd,mono,trans,reach)
    fig,axes=plt.subplots(2,3,figsize=(12,5.5),layout="constrained")
    for j,kind in enumerate(("slow","intermediate","fast")):
        with np.load(out/f"{kind}_N_ADC.npz") as a:
            tm=a["time_s"]*1e6
            keep=abs(tm)<(60 if kind=="slow" else 20)
            axes[0,j].plot(tm[keep],a["illustrative_isolated_ADC_V"].real[keep]*1e3,color=COLORS[1],lw=.8)
            axes[1,j].plot(tm[keep],a["illustrative_plus_noise_ADC_V"].real[keep]*1e3,color=COLORS[0],lw=.8)
        axes[0,j].set_title(kind.title())
        axes[1,j].set_xlabel("Time from passage (µs)")
    axes[0,0].set_ylabel("Isolated injection I (mV ADC)")
    axes[1,0].set_ylabel("Injection + simulated noise I (mV ADC)")
    fig.suptitle("Illustrative known-phase ρ = 5 · conditional distances · Model N")
    save(fig,out,"illustrative")
    h,d,_=source(1e-9/2,1e9,astronomical_unit)
    h8=source(1e-12,1e9,1000*parsec)[0]
    checks.update(eq5_SI_individual_1e_minus9_GHz_per_s=source(1e-9,1e9,astronomical_unit)[1]/1e9,
                  eq5_SI_total_1e_minus9_GHz_per_s=d/1e9,eq8_SI_individual_1e_minus12_at_kpc=h8,
                  benchmark_checks="adiabatic, impulse, direct intermediate convolution, Lorentz area and ADC Parseval",
                  input_sha256={str(p):digest(p) for p in (phy,cal,fit,archive,noise_path,cfgfile)})
    (out/"validation.json").write_text(json.dumps(checks,indent=2)+"\n")


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("work",type=Path)
    ap.add_argument("out",type=Path)
    a=ap.parse_args()
    run(a.work,a.out,HERE/"config.json")
