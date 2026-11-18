"""Campaign strain projection from signed, verified, already averaged FFT archives."""
import argparse
import importlib.util
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import brentq

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("v49",ROOT/"simulation/v49_hfgw/run.py")
v49=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v49)
FS=v49.FS
T=1048576*1000/FS
MODES=v49.MODES


def thresholds(s,T,M=1):
    """s is equivalent strain PSD, M equal powers per run of duration T."""
    w=T/s
    return 1/np.sqrt(2*w.sum()),(M/np.dot(w,w))**.25


def run(work,archive,out):
    v47=work/"diagnostics/resonance_campaign_primary_v47_20261117"
    fixes=work/"diagnostics/frequency_sensor_closure_v47_20261117"
    verified=json.loads((fixes/"verification.json").read_text())
    recorded=json.loads((v47/"results.json").read_text())["input_sha256"]
    corrected=set(verified["corrected_runs"])
    assert verified["archive_identity_verified"] and len(corrected)==7
    starts=sorted(json.loads((v47/"temperature_SPEC_bounds_provenance.json").read_text()),
                  key=lambda r:r["start"])
    assert {x["run"] for x in starts}==set(range(680,940))
    groups=[]; hashes={}
    for run_id in range(680,940):
        root=fixes/"corrected_fft_by_run" if run_id in corrected else archive
        path=root/f"run{run_id:05d}.npz"
        digest=v49.digest(path)
        assert digest==recorded[str(path)],path
        hashes[str(path)]=digest
        with np.load(path) as a:
            assert float(a["fs"])==FS and int(a["n_fft_done"])==1000
            if run_id in corrected:
                assert int(a["iq_sign"])==-1
            groups.append([a[f"fft_amp_mode{i}_SPECs"].astype(float) for i in range(3)])
    arr=np.array(groups)
    n=arr.shape[-1]
    assert arr.shape==(260,3,16383) and np.isfinite(arr).all() and (arr>=0).all()
    f=np.fft.fftshift(np.fft.fftfreq(n,1/FS))
    window=np.hanning(n)
    enbw=FS*np.sum(window**2)/window.sum()**2
    arr*=(2/5)**2/enbw
    bands=v49.prior.csv_read(v47/"campaign_band_powers.csv")
    validation_error=0.
    for row in (r for r in bands if r["offset_hz"]=="0"):
        m=MODES.index(row["mode"])
        power=v49.ref.TAPS*np.exp(2j*np.pi*float(row["center_IF_hz"])/FS*np.arange(len(v49.ref.TAPS)))
        w=abs(np.fft.fftshift(np.fft.fft(power,n)))**2
        got=np.dot(w,arr[int(row["run"])-680,m])*FS/n
        validation_error=max(validation_error,abs(got/float(row["power_ADC_V2"])-1))
    assert validation_error<1e-10
    phy=work/"simulation/v49_hfgw/apparatus.csv"
    calpath=work/"diagnostics/normalization_audit_20261114/calibration_reconstruction.json"
    cal=json.loads(calpath.read_text())
    apparatus=v49.prior.csv_read(phy)
    out.mkdir(parents=True,exist_ok=False)
    table,curves,runs=[],[],[]
    fig,axes=plt.subplots(2,3,figsize=(12,6),layout="constrained")
    M=64000
    T_hann=1/enbw
    width=128
    from scipy.ndimage import uniform_filter1d
    for i,(mode,p) in enumerate(zip(MODES,apparatus)):
        f0,fc,b,K,gdb=(float(p[k]) for k in ("RF_Hz","physical_IF_Hz","bandwidth_Hz","K_port_W_per_h2","VNA_plus_FET_dB"))
        x,k=v49.prior.curve(cal,mode)
        terms=(np.interp(f,x,k,left=np.nan,right=np.nan)*.01,
               10**(v49.prior.response(v49.prior.SCI,i,f)["summed_IQ_dB"]/20))
        fsel=(f>=100000+width/2*FS/n)&(f<=2500000-width/2*FS/n)
        S=uniform_filter1d(arr[:,i,:],size=width,axis=-1,mode="nearest")
        center=np.array([np.interp(fc,f,s) for s in S])
        center_asd=np.sqrt(center)
        for j,(name,h) in enumerate(zip(("H","N"),terms)):
            g2=50*10**(gdb/10)*K*h**2*abs(v49.lorentz(f-fc,b))**2
            g0=np.interp(fc,f,g2)
            strain=center/g0
            asd=np.sqrt(strain)
            coh,sc=thresholds(strain,T)
            _,hann=thresholds(strain,T_hann*M,M)
            coh_uniform=np.sqrt(strain.mean()/(2*T*len(strain)))
            sc_uniform=np.sqrt(strain.mean()/T)*len(strain)**(-.25)
            table.append(dict(mode=mode,model=name,physical_RF_Hz=f0,IF_Hz=fc,live_s=260*T,
                              harmonic_ASD=np.sqrt(len(strain)/sum(1/strain)),arithmetic_PSD_ASD=np.sqrt(strain.mean()),
                              ASD_min=asd.min(),ASD_p05=np.percentile(asd,5),ASD_p95=np.percentile(asd,95),ASD_max=asd.max(),
                              ASD_relative_run_SD=asd.std(ddof=1)/asd.mean(),
                              coherent_known_phase_SNR1=coh,coherent_known_phase_SNR5=5*coh,
                              run_power_SNR1=sc,run_power_SNR5=np.sqrt(5)*sc,
                              archive_Hann_power_SNR1=hann,archive_Hann_power_SNR5=np.sqrt(5)*hann,
                              coherent_uniform_penalty=coh_uniform/coh,run_power_uniform_penalty=sc_uniform/sc,
                              coherent_vs_same_estimator_run680=coh/(asd[0]/np.sqrt(2*T*260)),
                              run_power_vs_same_estimator_run680=sc/(asd[0]/np.sqrt(T)*260**(-.25))))
            for ix in np.flatnonzero(fsel & np.isfinite(h))[::8]:
                z=S[:,ix]/g2[ix]
                curves.append(dict(mode=mode,model=name,RF_Hz=f0+f[ix]-fc,
                                   harmonic_ASD=np.sqrt(len(z)/np.sum(1/z)),arithmetic_PSD_ASD=np.sqrt(np.mean(z)),
                                   ASD_p05=np.sqrt(np.percentile(z,5)),ASD_p95=np.sqrt(np.percentile(z,95))))
            if j==0:
                runs.extend(dict(run=680+r,mode=mode,PSD_ADC_V2_Hz=value,
                                 relative_ASD=np.sqrt(value/center.mean())) for r,value in enumerate(center))
            rows=[r for r in curves if r["mode"]==mode and r["model"]==name]
            axes[0,i].semilogy([(r["RF_Hz"]-f0)/1e3 for r in rows],[r["harmonic_ASD"] for r in rows],
                              color=v49.COLORS[j],label=name)
            axes[1,i].plot([0,1,2],[coh,sc,hann],"o",color=v49.COLORS[j],label=name)
        axes[0,i].set(title=mode,xlabel="RF offset (kHz)")
        axes[1,i].set(yscale="log",xticks=[0,1,2],xticklabels=["Coherent","Run powers","Hann powers"])
    axes[0,0].set_ylabel("Weighted strain ASD (1/√Hz)")
    axes[1,0].set_ylabel("Peak strain at ideal SNR = 1")
    axes[0,0].legend()
    fig.savefig(out/"campaign.png",dpi=155)
    fig.savefig(out/"campaign.pdf")
    for name,data in (("summary",table),("asd_curves",curves),("run_noise",runs)):
        v49.write(out,name,data)
    # Independent equal-noise limits; archived Hann powers retain coherent-gain ENBW.
    c,s=thresholds(np.ones(260),T)
    np.testing.assert_allclose(c,1/np.sqrt(2*T*260))
    np.testing.assert_allclose(s,1/(np.sqrt(T)*260**.25))
    span=starts[-1]["stop"]-starts[0]["start"]
    delta=brentq(lambda x:np.sinc(x)-.9,0,.5)
    (out/"validation.json").write_text(json.dumps(dict(runs=260,corrected_runs=sorted(corrected),live_s=260*T,
        timestamp_span_s=span,largest_gap_seconds_resolution_s=max(b["start"]-a["stop"] for a,b in zip(starts,starts[1:])),
        verified_file_count=len(hashes),FIR_780_checks_max_relative_error=validation_error,
        sample_spacing_Hz=FS/n,Hann_ENBW_Hz=enbw,Hann_segments_per_run=M,
        Hann_equivalent_coherent_seconds=T_hann,constant_frequency_error_10pct_live_s_Hz=delta/(260*T),
        constant_frequency_error_10pct_span_Hz=delta/span,
        phase_rms_for_10pct_scale_rad=np.sqrt(-2*np.log(.9)), equal_noise_scaling_verified=True,
        archive_inputs=hashes, config_input_sha256={str(p):v49.digest(p) for p in (phy,calpath,v47/"results.json",
                                     v47/"campaign_band_powers.csv",v47/"temperature_SPEC_bounds_provenance.json")}),indent=2)+"\n")


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("work","archive","out"):
        ap.add_argument(name,type=Path)
    a=ap.parse_args()
    run(a.work,a.archive,a.out)
