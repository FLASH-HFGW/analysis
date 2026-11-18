"""Matched block statistics for run 680 and the frozen Step 10A models."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import h5py
import numpy as np
from scipy.fft import fft, ifft, next_fast_len
from scipy.special import ndtr

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/"step10a"))
import run as model

FS=model.FS
N=262144
LSB=4/65535
MODES=model.prior.MODES
AMP=np.linspace(0,5,201)
IQ=np.linspace(-4,4,81)
PHASE=np.linspace(-np.pi,np.pi,73)
SOURCES=("data","H","N")
ROOT=HERE.parents[1]


def read(path):
    return json.loads(path.read_text())


def prefix(path, audit, num):
    sys.path.insert(0,"/cvmfs/sft-flash.infn.it/package/midas/python")
    from midas.file_reader import MidasFile
    sys.path.insert(0,str(ROOT/"examples"))
    from iq_acquisition_metadata import extract_coordinates
    reader=MidasFile(str(path),use_numpy=True)
    events=[]
    try:
        odb=reader.get_bor_odb_dump().data
        coords=extract_coordinates(odb,-1,path,int(reader.event.header.timestamp))
        assert coords["selected_ODB_sha256"]==audit["metadata"]["selected_ODB_sha256"]
        assert coords["fs_hz"]==FS
        assert [coords["modes"][m]["ADC_peak_V"] for m in MODES]==[2]*3
        for event in reader:
            if event.header.is_midas_internal_event() or "SPEC" not in event.banks:
                continue
            bank=np.asarray(event.banks["SPEC"].data,dtype=np.uint16)
            frame=bank.view(np.int16).reshape(-1,8)
            row=dict(SPEC_index=len(events),serial=int(event.header.serial_number),
                     timestamp=int(event.header.timestamp),samples=len(frame),
                     bank_sha256=hashlib.sha256(bank.tobytes()).hexdigest())
            assert len(frame)==1048576
            i=len(events)
            if i<len(audit["events"]):
                assert row["bank_sha256"]==audit["SPEC_bank_sha256"][i]
                assert all(row[k]==audit["events"][i][k] for k in ("serial","timestamp","samples"))
            events.append(row)
            yield frame[:,:6],row
            if len(events)==num:
                break
    finally:
        reader.file.close()
    assert len(events)==num


def projection(z, mask):
    X=fft(z,norm="ortho")
    original=np.mean(abs(z)**2)
    rejected=np.sum(abs(X[~mask])**2)/len(z)
    dc=abs(X[0])**2/len(z)
    X[~mask]=0
    y=ifft(X,norm="ortho")
    np.testing.assert_allclose(np.mean(abs(y)**2)+rejected,original,rtol=1e-12)
    assert abs(y.mean())<1e-14
    return y,X,dict(pre_projection_V2=original,rejected_V2=rejected,removed_DC_V2=dc)


def digitize(z):
    code=np.rint(np.stack((z.real,-z.imag))/LSB)
    assert code.min()>=-32768 and code.max()<=32767
    return LSB*(code[0]-1j*code[1])


def stats(z, expected_rms, cfg, sample_hz, spectrum=None):
    z=z-z.mean()
    i,q=z.real,-z.imag
    n=len(z)
    vx=np.mean(i*i)
    vy=np.mean(q*q)
    cv=np.mean(i*q)
    v=vx+vy
    rms=np.sqrt(v)
    pseudo=complex(vx-vy,-2*cv)
    a=abs(z)
    u=a/rms
    hist=np.histogram(u,AMP)[0]
    rayleigh=1-np.exp(-AMP[1:]**2)
    row=dict(samples=n,RMS_V=rms,power_V2=v,var_I_V2=vx,var_Qhardware_V2=vy,
             cov_I_Qhardware_V2=cv,pseudo_real_V2=pseudo.real,pseudo_imag_V2=pseudo.imag,
             pseudo_real_relative=pseudo.real/v,pseudo_imag_relative=pseudo.imag/v,pseudo_abs_relative=abs(pseudo)/v,
             mean_amplitude_V=a.mean(),amplitude_sd_V=a.std(),
             amplitude_mean_over_RMS=u.mean(),amplitude_fourth_over_RMS4=np.mean(u**4),
             rayleigh_CDF_max_diff=np.max(abs(np.cumsum(hist)/n-rayleigh)),
             proper_reference_RMS_V=expected_rms)
    phase=np.angle(z)
    valid=a>0
    unit=np.zeros(n,complex)
    unit[valid]=z[valid]/a[valid]
    phase_mean=np.mean(unit[valid])
    row.update(phase_valid=int(valid.sum()),phase_resultant=abs(phase_mean),
               phase_mean_cos=phase_mean.real,phase_mean_sin=phase_mean.imag)
    arrays=dict(amplitude_shape=hist/n,amplitude_absolute=np.histogram(a/expected_rms,AMP)[0]/n,
                phase=np.histogram(phase[valid],PHASE)[0]/valid.sum())
    ib=np.searchsorted(IQ,i/rms,side="right")-1
    qb=np.searchsorted(IQ,q/rms,side="right")-1
    width=len(IQ)-1
    inside=(ib>=0)&(ib<width)&(qb>=0)&(qb<width)
    arrays["iq_shape"]=np.bincount(ib[inside]*width+qb[inside],minlength=width**2).reshape(width,width)/n
    ib=np.searchsorted(IQ,i/expected_rms,side="right")-1
    qb=np.searchsorted(IQ,q/expected_rms,side="right")-1
    inside=(ib>=0)&(ib<width)&(qb>=0)&(qb<width)
    arrays["iq_absolute"]=np.bincount(ib[inside]*width+qb[inside],minlength=width**2).reshape(width,width)/n
    for lag in cfg["phase_increment_lags"]:
        vmask=valid[lag:]&valid[:-lag]
        delta=(unit[lag:]*unit[:-lag].conj())[vmask]
        avg=delta.mean()
        row.update({f"phase_increment_pairs_{lag}":int(vmask.sum()),f"phase_increment_cos_{lag}":avg.real,
                    f"phase_increment_sin_{lag}":avg.imag,f"phase_increment_resultant_{lag}":abs(avg)})
        arrays[f"phase_increment_{lag}"]=np.histogram(np.angle(delta),PHASE)[0]/len(delta)
    for multiple in cfg["threshold_multiples_RMS"]:
        for label,ref in (("shape",rms),("absolute",expected_rms)):
            row[f"tail_{label}_{multiple}_count"]=int(np.count_nonzero(a>multiple*ref))
    length=next_fast_len(2*n-1)
    X=fft(z,length)
    lag=np.arange(cfg["acf_lags"]+1)
    acf=ifft(abs(X)**2)[:len(lag)]/(n-lag)
    np.testing.assert_allclose(acf[0],v,rtol=1e-13,atol=1e-20)
    arrays["acf"]=acf/v
    arrays["acf_V2"]=acf
    for j in (1,10,100):
        c=acf[j]/v
        row.update({f"acf_real_{j}":c.real,f"acf_imag_{j}":c.imag,f"acf_abs_{j}":abs(c)})
    if spectrum is not None:
        arrays["PSD"]=abs(spectrum)**2/sample_hz
        np.testing.assert_allclose(arrays["PSD"].mean()*sample_hz,v,rtol=1e-12)
    return row,arrays


class Aggregate:
    def __init__(self):
        self.data={}
        self.count={}
    def add(self,key,number,values):
        cluster=number//8
        dest=self.data.setdefault((key,cluster),{})
        for name,a in values.items():
            if name not in dest:
                dest[name]=a.copy()
            else:
                dest[name]+=a
        counter=(key,cluster)
        self.count[counter]=self.count.get(counter,0)+1
    def store(self,h):
        for key in sorted({key for key,_ in self.data}):
            ids=sorted(c for k,c in self.data if k==key)
            group=h.require_group("/".join(key))
            group.attrs["blocks_per_cluster"]=[self.count[key,c] for c in ids]
            for name in self.data[key,ids[0]]:
                values=np.stack([self.data[key,c][name]/self.count[key,c] for c in ids])
                group.create_dataset(name,data=values,compression="lzf")


def execute(work, raw, previous, output, cfg_path):
    cfg=read(cfg_path)
    assert cfg["block_samples"]==N and cfg["spec_count"]<=16
    assert cfg["spec_count"]>=2 and cfg["spec_count"]%2==0
    assert cfg["spec_samples"]==4*N and cfg["fir_decimation"]==20
    diag=work/"diagnostics"
    cal=diag/"normalization_audit_20261114/calibration_reconstruction.json"
    phy=work/"simulation/step6/metrics.json"
    audit=diag/"frequency_sensor_closure_v47_20261117/run00680_raw_check.json"
    source,physical=read(cal),read(phy)["mode_results"]
    previous_metrics=read(previous/"metrics.json")
    for p in (cal,phy):
        assert model.sha(p)==next(v for k,v in previous_metrics["input_sha256"].items() if Path(k).name==p.name)
    frequencies=np.fft.fftfreq(N,1/FS)
    bands=model.prior.csv_read(ROOT/"docs/step9d/integrals.csv")
    kept=np.arange(cfg["fir_edge_guard_input_samples"],N-cfg["fir_edge_guard_input_samples"],cfg["fir_decimation"])
    expected={}
    plan={}
    records=[]
    all_events=[]
    output.mkdir(parents=True,exist_ok=False)
    aggregate=Aggregate()
    with h5py.File(previous/"series.h5") as old:
        np.testing.assert_array_equal(old["signed_IF_Hz"][:],frequencies)
        for mi,mode in enumerate(MODES):
            x,k=model.prior.curve(source,mode)
            p,mask=model.analytical(mi,frequencies,physical[mode],previous_metrics["modes"][mode]["RF_gain_dB"],x,k)
            np.testing.assert_array_equal(mask,old[f"{mode}/common_spectral_mask"][:])
            p[...,~mask]=0
            for idx,name in enumerate(("H","N")):
                np.testing.assert_array_equal(p[idx],old[f"{mode}/{name}/expected_component_PSD_V2_Hz"][:])
            filters={}
            for offset,center in model.bands_for(mode,bands):
                h=model.ref.TAPS*np.exp(2j*np.pi*center/FS*np.arange(len(model.ref.TAPS)))
                filters[str(int(offset))]=(center,fft(h,N),np.exp(-2j*np.pi*np.remainder(kept*center/FS,1)))
            expected[mode]={"full":np.sqrt(FS*np.mean(p[1].sum(axis=(0,1))))}
            for band,(_,response,_) in filters.items():
                expected[mode][band]=np.sqrt(FS*np.mean(p[1].sum(axis=(0,1))*abs(response)**2))
            root=np.sqrt(FS*p)
            plan[mode]=(mask,filters,root)

        def process(mode,pop,block,spec,z):
            mask,filters,_=plan[mode]
            masked,X,project=projection(z,mask)
            row,arrays=stats(masked,expected[mode]["full"],cfg,FS,X)
            guard=cfg["fir_edge_guard_input_samples"]
            inside=np.mean(abs(masked[guard:-guard])**2)
            project["guard_trimmed_to_full_power"]=inside/row["power_V2"]
            records.append(dict(mode=mode,population=pop,block=block,SPEC_group=spec,band="full",**project,**row))
            aggregate.add((mode,pop,"full"),block,arrays)
            for band,(center,response,oscillator) in filters.items():
                # Identical block-start oscillator for both data and toys.
                filtered=ifft(X*response,norm="ortho")[kept]*oscillator
                row,arrays=stats(filtered,expected[mode][band],cfg,FS/cfg["fir_decimation"])
                records.append(dict(mode=mode,population=pop,block=block,SPEC_group=spec,band=band,**row))
                aggregate.add((mode,pop,band),block,arrays)

        for m in MODES:
            for name in ("H","N"):
                counts=old[f"{m}/{name}/adc_counts_I_Qhardware"][:].astype(float)
                process(m,name+"10A",0,0,LSB*(counts[:,0]-1j*counts[:,1]))

        # One SPEC in memory. Each experimental and MC block is processed and discarded.
        for frame,event in prefix(raw,read(audit),cfg["spec_count"]):
            spec=event["SPEC_index"]
            all_events.append(event)
            for sub in range(4):
                index=4*spec+sub
                segment=frame[sub*N:(sub+1)*N].astype(float)
                for mi,mode in enumerate(MODES):
                    z=LSB*(segment[:,2*mi]-1j*segment[:,2*mi+1])
                    process(mode,"data",index,spec,z)
                    root=plan[mode][2]
                    rng=np.random.default_rng(np.random.SeedSequence([cfg["seed"],mi,index]))
                    g=(rng.standard_normal(root.shape[1:])+1j*rng.standard_normal(root.shape[1:]))/np.sqrt(2)
                    for j,name in enumerate(("H","N")):
                        analog=ifft((root[j]*g).sum(axis=(0,1)),norm="ortho")
                        process(mode,name,index,spec,digitize(analog))
            print(f"Processed SPEC {spec+1}/{cfg['spec_count']}",flush=True)
    with h5py.File(output/"statistics.h5","w") as f:
        f["frequency_Hz"]=frequencies
        f["amplitude_edges_over_reference_RMS"]=AMP
        f["iq_edges_over_reference_RMS"]=IQ
        f["phase_edges_rad"]=PHASE
        f["proper_reference_IQ_bin_probability"]=np.diff(ndtr(IQ*np.sqrt(2)))
        f["proper_reference_rayleigh_bin_probability"]=-np.diff(np.exp(-AMP**2))
        f["common_mask"]=plan[MODES[0]][0]
        aggregate.store(f)
    (output/"block_metrics.json").write_text(json.dumps(records,allow_nan=False)+"\n")
    provenance=dict(config=cfg,events=all_events,raw_path=str(raw),bytes=raw.stat().st_size,
                    first_eight_verified_against_v47=True,input_hashes={str(p):model.sha(p) for p in
                    (cal,phy,audit,previous/"metrics.json",previous/"series.h5",cfg_path)},
                    timebase=dict(fs_Hz=FS,fir_sample_rate_Hz=FS/cfg["fir_decimation"],
                                  fir_samples_per_block=len(kept)),proper_reference_RMS_V=expected)
    (output/"population.json").write_text(json.dumps(provenance,indent=2,allow_nan=False)+"\n")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("work","raw","previous","output"):
        parser.add_argument(name,type=Path)
    parser.add_argument("--config",type=Path,default=HERE/"config.json")
    a=parser.parse_args()
    execute(a.work,a.raw,a.previous,a.output,a.config)
