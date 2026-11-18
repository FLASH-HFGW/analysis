"""Matched full-run statistics from the frozen historical overlap-save toy."""
import argparse,csv,importlib.util,json
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import h5py,numpy as np
from scipy.fft import fft,ifft,next_fast_len

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("step10c",HERE.parent/"step10c/run.py")
c=importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
b=c.setup
FS,N=c.FS,c.N
B=2**20
L=65537


def kernel(source,p,mode):
    x,k=c.BASE.prior.curve(source,mode)
    f=np.fft.fftfreq(B,1/FS)
    ki=2*np.pi*p["f0_hz"]/p["q0"]
    kt=ki*(1+p["kappa1"]+p["kappa2"])
    photon=6.62607015e-34*p["f0_hz"]
    theta=photon/np.expm1(photon/(1.380649e-23*p["temperature_k"]))
    S=np.zeros(B)
    for j in (-1,0,1):
        a=f+j*FS
        resp=np.interp(a,x,k*.01,left=0,right=0)
        S+=50*10**(103.4/10)*(1.380649e-23*3.955+theta*ki**2*p["kappa2"]/((kt/2)**2+(2*np.pi*(a-1e6))**2))*resp**2
    fir=np.fft.fftshift(ifft(np.sqrt(FS*S)))[B//2-L//2:B//2+L//2+1]
    return fft(fir,next_fast_len(B+L-1)),float(FS*S.mean())


def white(rng,n):
    return (rng.standard_normal(n)+1j*rng.standard_normal(n))/np.sqrt(2)


def reduce_spec(z,mode,definition,kept,cfg):
    mask,filters,ref,_,_=definition
    arrays={};rows={}
    for j,x in enumerate(z.reshape(4,N)):
        y,X,projection=b.projection(x,mask)
        row,arr=c.measures(y,ref["full"],cfg,FS,X)
        arr["complementary"]=X*X[(-np.arange(N))%N]/FS
        np.testing.assert_allclose(FS*arr["complementary"].mean(),complex(row["pseudo_real_V2"],row["pseudo_imag_V2"]),atol=1e-18)
        c.collect(arrays,rows,(mode,"v0","full"),dict(**row,**projection),arr)
        for band,(response,osc) in filters.items():
            yy=ifft(X*response,norm="ortho")[kept]*osc
            row,arr=c.measures(yy,ref[band],cfg,FS/20)
            c.collect(arrays,rows,(mode,"v0",band),row,arr)
    return arrays,rows


def run(work,out,workers):
    out.mkdir(parents=True,exist_ok=False)
    root=work/"simulation"
    prev=root/"step10a"
    historical=root/"toy_ODB_cal5_data2_LF_20261116"
    cfg=b.read(root/"step10c/population.json")["config"]
    _,kept,definitions=c.plan(work,prev,cfg)
    cal=work/"diagnostics/normalization_audit_20261114/calibration_reconstruction.json"
    phy=root/"step6/metrics.json"
    source,params=b.read(cal),b.read(phy)["mode_results"]
    original=b.read(historical/"metrics.json")
    for path in (cal,phy):
        assert c.BASE.sha(path)==next(v for k,v in original["input_sha256"].items() if Path(k).name==path.name)
    progress={}
    with h5py.File(historical/"toy_full_run680.h5") as old, h5py.File(out/"v0_statistics.h5","w") as h, (out/"v0_blocks.csv").open("w",newline="") as stream, ThreadPoolExecutor(max_workers=workers) as pool:
        writer=None
        for i,mode in enumerate(c.MODES):
            H,P=kernel(source,params[mode],mode)
            assert np.isclose(P,original["results"][mode]["expected_power_v2"],rtol=1e-12)
            rng=np.random.default_rng(20261115+100*i)
            history=white(rng,L-1)
            total,group={},{}
            pending=deque()
            max_error=0
            def consume(done,index):
                nonlocal writer,group
                arrays,rows=done.result()
                for key,arr in arrays.items():
                    c.accumulate(total.setdefault(key,{}),arr)
                    c.accumulate(group.setdefault(key,{}),arr)
                for (_,_,band),rr in rows.items():
                    for j,row in enumerate(rr):
                        flat=dict(mode=mode,population="v0",band=band,SPEC=index,subblock=j,**row)
                        if writer is None:
                            writer=csv.DictWriter(stream,fieldnames=list(flat),lineterminator="\n")
                            writer.writeheader()
                        writer.writerow(flat)
                if (index+1)%20==0:
                    node=h.require_group(f"cluster_acf/{mode}")
                    node.create_dataset(str(index//20),data=group[mode,"v0","full"]["acf"]/80)
                    group={}
            for index in range(1000):
                block=np.r_[history,white(rng,B)]
                z=ifft(fft(block,len(H))*H)[L-1:L-1+B]
                history=block[-L+1:].copy()
                counts=np.rint(np.column_stack([z.real,z.imag])/b.LSB)
                assert counts.min()>=-32768 and counts.max()<=32767
                if index<5:
                    old_counts=old[f"{mode}/first_5SPEC_ADC_counts"][index*B:(index+1)*B]
                    max_error=max(max_error,int(np.max(abs(counts-old_counts))))
                    np.testing.assert_array_equal(counts,old_counts)
                pending.append((pool.submit(reduce_spec,b.LSB*(counts[:,0]+1j*counts[:,1]),mode,definitions[mode],kept,cfg),index))
                if len(pending)>workers:
                    consume(*pending.popleft())
            while pending:consume(*pending.popleft())
            for key,arr in total.items():
                g=h.require_group("mean/"+"/".join(key))
                for name,v in arr.items():g.create_dataset(name,data=v/4000,compression="lzf")
            progress[mode]=dict(historical_expected_V2=P,first_five_SPEC_ADC_count_max_error=max_error,blocks=4000)
            (out/"progress.json").write_text(json.dumps(progress,indent=2)+"\n")
            print(mode,"complete",flush=True)
    (out/"validation_v0.json").write_text(json.dumps(progress,indent=2)+"\n")


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("work",type=Path)
    p.add_argument("out",type=Path)
    p.add_argument("--workers",type=int,default=7)
    a=p.parse_args()
    run(a.work,a.out,a.workers)
