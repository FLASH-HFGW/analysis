"""Stream complete SPECs through the Step 10B estimators with bounded parallelism."""
import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

import h5py
import numpy as np
from scipy.fft import ifft

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("step10b",HERE.parent/"step10b/run.py")
setup=importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)

BASE=setup.model
FS,N=setup.FS,setup.N
MODES=setup.MODES
POPS=("data","H","N")
EDGES_MHZ=(0,.1,.25,.5,1,1.25,1.75,2.5)


def events(path,audit,count):
    sys.path.insert(0,"/cvmfs/sft-flash.infn.it/package/midas/python")
    from midas.file_reader import MidasFile
    sys.path.insert(0,str(setup.ROOT/"examples"))
    from iq_acquisition_metadata import extract_coordinates
    reader=MidasFile(str(path),use_numpy=True)
    i=0
    try:
        odb=reader.get_bor_odb_dump().data
        meta=extract_coordinates(odb,-1,path,int(reader.event.header.timestamp))
        assert meta["selected_ODB_sha256"]==audit["metadata"]["selected_ODB_sha256"]
        assert meta["fs_hz"]==FS and [meta["modes"][m]["ADC_peak_V"] for m in MODES]==[2]*3
        for ev in reader:
            if ev.header.is_midas_internal_event() or "SPEC" not in ev.banks:
                continue
            bank=np.asarray(ev.banks["SPEC"].data,dtype=np.uint16)
            frame=bank.view(np.int16).reshape(-1,8)
            info=dict(spec=i,serial=int(ev.header.serial_number),timestamp=int(ev.header.timestamp),
                      samples=len(frame),sha256=hashlib.sha256(bank.tobytes()).hexdigest())
            assert len(frame)==4*N and i<count
            if i<len(audit["events"]):
                assert info["sha256"]==audit["SPEC_bank_sha256"][i]
                assert all(info[k]==audit["events"][i][k] for k in ("serial","timestamp","samples"))
            yield frame[:,:6].copy(),info
            i+=1
    finally:
        reader.file.close()
    assert i==count,i


def plan(work, previous, cfg):
    cal=work/"diagnostics/normalization_audit_20261114/calibration_reconstruction.json"
    phy=work/"simulation/step6/metrics.json"
    config=setup.read(previous/"metrics.json")
    for p in (cal,phy):
        assert BASE.sha(p)==next(v for k,v in config["input_sha256"].items() if Path(k).name==p.name)
    source,physical=setup.read(cal),setup.read(phy)["mode_results"]
    f=np.fft.fftfreq(N,1/FS)
    kept=np.arange(2000,N-2000,20)
    band_rows=BASE.prior.csv_read(setup.ROOT/"docs/step9d/integrals.csv")
    definitions={}
    with h5py.File(previous/"series.h5") as old:
        np.testing.assert_array_equal(f,old["signed_IF_Hz"][:])
        for i,m in enumerate(MODES):
            x,k=BASE.prior.curve(source,m)
            p,mask=BASE.analytical(i,f,physical[m],config["modes"][m]["RF_gain_dB"],x,k)
            np.testing.assert_array_equal(mask,old[f"{m}/common_spectral_mask"][:])
            p[...,~mask]=0
            for j,name in enumerate(("H","N")):
                np.testing.assert_array_equal(p[j],old[f"{m}/{name}/expected_component_PSD_V2_Hz"][:])
            expected={"full":np.sqrt(FS*np.mean(p[1].sum(axis=(0,1))))}
            filters={}
            for offset,c in BASE.bands_for(m,band_rows):
                band=str(int(offset))
                h=BASE.ref.TAPS*np.exp(2j*np.pi*c/FS*np.arange(len(BASE.ref.TAPS)))
                response=BASE.fft(h,N)
                filters[band]=(response,np.exp(-2j*np.pi*np.remainder(kept*c/FS,1)))
                expected[band]=np.sqrt(FS*np.mean(p[1].sum(axis=(0,1))*abs(response)**2))
            definitions[m]=(mask,filters,expected,np.sqrt(FS*p),p.sum(axis=(1,2)))
    return f,kept,definitions


def measures(z, expected, cfg, rate, X=None):
    row, curves=setup.stats(z,expected,cfg,rate,X)
    amp=abs(z-z.mean())
    for multiple in cfg["threshold_multiples_RMS"]:
        for kind,rms in (("shape",row["RMS_V"]),("absolute",expected)):
            above=amp>multiple*rms
            starts=int(above[0])+np.count_nonzero(above[1:] & ~above[:-1])
            key=f"tail_{kind}_{multiple}"
            assert np.count_nonzero(above)==row[key+"_count"]
            row[key+"_episodes"]=int(starts)
            row[key+"_left_censored"]=int(above[0])
            row[key+"_right_censored"]=int(above[-1])
    return row,curves


def process(frame,info,definitions,kept,cfg,mirror):
    curves={}
    scalars={}
    for k in range(4):
        index=4*info["spec"]+k
        block=frame[k*N:(k+1)*N].astype(float)
        for i,m in enumerate(MODES):
            mask,filters,ref,root,_=definitions[m]
            rng=np.random.default_rng(np.random.SeedSequence([cfg["seed"],i,index]))
            # Each analog source and alias gets a distinct proper draw; H/N share draws.
            draws=(rng.standard_normal(root.shape[1:])+1j*rng.standard_normal(root.shape[1:]))/np.sqrt(2)
            for j,pop in enumerate(POPS):
                if pop=="data":
                    z=setup.LSB*(block[:,2*i]-1j*block[:,2*i+1])
                else:
                    z=setup.digitize(ifft((root[j-1]*draws).sum(axis=(0,1)),norm="ortho"))
                masked,X,proj=setup.projection(z,mask)
                row,arr=measures(masked,ref["full"],cfg,FS,X)
                comp=X*X[mirror]/FS
                cyc=FS*ifft(arr["PSD"])[:cfg["acf_lags"]+1]
                centered=masked-masked.mean()
                L=cfg["acf_lags"]
                wrap=np.r_[0,np.convolve(centered[:L],centered[-L:][::-1].conj())[:L]]
                corrected=(N*cyc-wrap)/(N-np.arange(L+1))
                diff=np.max(abs(corrected-arr["acf_V2"]))
                p_err=abs(FS*np.mean(comp)-complex(row["pseudo_real_V2"],row["pseudo_imag_V2"]))
                assert diff<1e-12*row["power_V2"] and p_err<1e-12*row["power_V2"]
                arr["complementary"]=comp
                arr["ACF_circular_V2"]=cyc
                arr["ACF_wrap_V2_sum"]=wrap
                row.update(proj,PSD_ACF_max_error_V2=diff,complementary_pseudo_error_V2=p_err)
                collect(curves,scalars,(m,pop,"full"),row,arr)
                for band,(response,osc) in filters.items():
                    filt=ifft(X*response,norm="ortho")[kept]*osc
                    row,arr=measures(filt,ref[band],cfg,FS/20)
                    collect(curves,scalars,(m,pop,band),row,arr)
    return info,curves,scalars


def collect(curves,scalars,key,row,arr):
    scalars.setdefault(key,[]).append(row)
    accumulate(curves.setdefault(key,{}),arr)


def accumulate(dest,src):
    for key,value in src.items():
        if key in dest:
            dest[key]+=value
        else:
            dest[key]=value.copy()


def save_cluster(h,cluster,group,nspec):
    node=h.create_group(f"clusters/{cluster:03d}")
    node.attrs["SPECs"]=nspec
    for key,curves in group.items():
        g=node.require_group("/".join(key))
        for name,v in curves.items():
            if name in ("PSD","complementary"):
                s=np.fft.fftshift(v)
                v=s.reshape(-1,128).mean(axis=1)
            g.create_dataset(name,data=v/(4*nspec),compression="lzf")


def stream(work,raw,previous,out,cfg,workers):
    f,kept,definitions=plan(work,previous,cfg)
    mirror=(-np.arange(N))%N
    auditpath=work/"diagnostics/frequency_sensor_closure_v47_20261117/run00680_raw_check.json"
    out.mkdir(parents=True,exist_ok=False)
    total,cluster={},{}
    begin=time.monotonic()
    with (out/"events.jsonl").open("w") as event_file, (out/"blocks.csv").open("w",newline="") as scalar_file, h5py.File(out/"statistics.h5","w") as h:
        h["frequency_Hz"]=f
        h["common_mask"]=definitions[MODES[0]][0]
        h["cluster_frequency_Hz"]=np.fft.fftshift(f).reshape(-1,128).mean(axis=1)
        for name,axis in (("amplitude",setup.AMP),("IQ",setup.IQ),("phase",setup.PHASE)):
            h[name+"_edges"]=axis
        for m,(_,_,_,_,psd) in definitions.items():
            for j,p in enumerate(("H","N")):
                h[f"analytical/{m}/{p}/PSD"]=psd[j]
        writer=None
        # Entries are always reduced in SPEC order. Bound in-flight frames.
        def consume(result):
            nonlocal writer,cluster
            info,curves,rows=result
            i=info["spec"]
            event_file.write(json.dumps(info)+"\n")
            for key,arr in curves.items():
                accumulate(total.setdefault(key,{}),arr)
                accumulate(cluster.setdefault(key,{}),arr)
            for (m,p,band),rr in rows.items():
                for b,r in enumerate(rr):
                    flat=dict(mode=m,population=p,band=band,SPEC=i,subblock=b,**r)
                    if writer is None:
                        writer=csv.DictWriter(scalar_file,fieldnames=list(flat),lineterminator="\n")
                        writer.writeheader()
                    writer.writerow(flat)
            size=cfg["cluster_SPECs"]
            if (i+1)%size==0 or i+1==cfg["spec_count"]:
                save_cluster(h,i//size,cluster,i%size+1)
                cluster={}
            if (i+1)%100==0:
                print(f"{i+1}/{cfg['spec_count']} SPEC; {time.monotonic()-begin:.1f}s",flush=True)
        queue=deque()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for frame,info in events(raw,setup.read(auditpath),cfg["spec_count"]):
                queue.append(pool.submit(process,frame,info,definitions,kept,cfg,mirror))
                if len(queue)>=workers+1:
                    consume(queue.popleft().result())
            while queue:
                consume(queue.popleft().result())
        for key,curves in total.items():
            g=h.require_group("mean/"+"/".join(key))
            for name,value in curves.items():
                g.create_dataset(name,data=value/(4*cfg["spec_count"]),compression="lzf")
    (out/"population.json").write_text(json.dumps(dict(config=cfg,Fs_Hz=FS,samples_per_BLOCK=N,
        spectra_per_population_mode=cfg["spec_count"]*4,raw_path=str(raw),raw_size=raw.stat().st_size,
        archive_audit_sha256=BASE.sha(auditpath),step10a_metrics_sha256=BASE.sha(previous/"metrics.json"),
        step10a_series_sha256=BASE.sha(previous/"series.h5"),
        estimator="Identical Step 10B projection, moments, histograms, linear ACF and FIR; added complementary spectrum and tail episodes",
        proper_reference_RMS_V={m:definitions[m][2] for m in MODES}),indent=2)+"\n")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("work","raw","previous","output"):
        parser.add_argument(name,type=Path)
    parser.add_argument("--workers",type=int,default=7)
    parser.add_argument("--config",type=Path,default=HERE/"config.json")
    a=parser.parse_args()
    cfg=setup.read(a.config)
    assert cfg["block_samples"]==N and cfg["spec_samples"]==4*N
    assert cfg["fir_edge_guard_input_samples"]==2000 and cfg["fir_decimation"]==20
    stream(a.work,a.raw,a.previous,a.output,cfg,a.workers)
