"""Resolve archived FFT signs using job provenance, byte hashes and original SPECs.

No curve-matching sign selection; no full campaign/raw reconstruction. Corrected
copies are lossless frequency reindexings of seven documented +1 products.
"""
from pathlib import Path
import argparse,hashlib,json,sys,time
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from iq_acquisition_metadata import extract_coordinates,MODES

REPO=Path(__file__).resolve().parents[1];WORK=REPO.parent/'analysis-work/Run2'
RUNTIME=REPO.parent/'analysis-runtime/autoreco/Run2'
RAW=Path('/home/mazzitel/flash-data/data/LNF')
ARCHIVE=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/fft_by_run')
SUSPECT=[691,692,743,746,876,894,921]
CONTROLS=[680,681,939]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def reflect_shifted(power):
    """P_conjugate(f)=P_original(-f), correct for odd AND even FFT lengths."""
    n=power.shape[-1]
    return np.fft.fftshift(np.take(np.fft.ifftshift(power,axes=-1),(-np.arange(n))%n,axis=-1),axes=-1)

def spectrum_from_frames(frames,peak=2.):
    # Match archived 64 x (16384-1) sample Hann segments and signed ADC decoding.
    nstep=len(frames)//64;assert len(frames)==1048576 and nstep==16384
    channels=frames[:,:6].reshape(64,nstep,6)[:,:-1].astype(np.float32)
    channels*=np.float32(2*peak/65535)
    channels-=np.mean(channels,axis=1,dtype=np.float64).astype(np.float32)[:,None,:]
    z=(channels[:,:,::2]-1j*channels[:,:,1::2]).astype(np.complex64)
    win=np.hanning(nstep-1).astype(np.float32)
    fminus=np.fft.fft(z*win[None,:,None],axis=1)
    fplus=np.fft.fft(z.conj()*win[None,:,None],axis=1)
    minus=np.fft.fftshift(np.mean(abs(fminus)**2,axis=0),axes=0).T
    plus=np.fft.fftshift(np.mean(abs(fplus)**2,axis=0),axes=0).T
    # Algebraic check on identical acquired samples, not similarity to another run.
    error=float(np.max(abs(minus-reflect_shifted(plus)))/np.max(minus))
    assert error<1e-12
    return minus/(5e6*np.sum(win.astype(float)**2)),error

def check_raw(task):
    run,output,maxspec=task;output=Path(output);start=time.monotonic()
    sys.path.insert(0,'/cvmfs/sft-flash.infn.it/package/midas/python');import midas.file_reader
    raw=RAW/f'run{run:05d}.mid.gz';reader=midas.file_reader.MidasFile(str(raw),use_numpy=True)
    odb=reader.get_bor_odb_dump().data;meta=extract_coordinates(odb,-1,raw,int(reader.event.header.timestamp))
    spectra=[];events=[];bank_hash=[];inpt=[];errors=[]
    try:
        for ev in reader:
            if ev.header.is_midas_internal_event():continue
            if 'INPT' in ev.banks:inpt.append({'event_id':int(ev.header.event_id),'timestamp':int(ev.header.timestamp),'values':np.asarray(ev.banks['INPT'].data,float).tolist()})
            if 'SPEC' not in ev.banks:continue
            bank=np.asarray(ev.banks['SPEC'].data,dtype=np.uint16)
            frames=bank.view(np.int16).reshape(-1,8)
            psd,error=spectrum_from_frames(frames,meta['modes']['TM010']['ADC_peak_V'])
            assert all(meta['modes'][m]['ADC_peak_V']==2 for m in MODES)
            spectra.append(psd);errors.append(error)
            events.append({'serial':int(ev.header.serial_number),'timestamp':int(ev.header.timestamp),'samples':len(frames)})
            bank_hash.append(hashlib.sha256(bank.tobytes()).hexdigest())
            if len(events)==maxspec:break
    finally:reader.file.close()
    assert len(events)==maxspec
    power=np.mean(spectra,axis=0);freq=np.fft.fftshift(np.fft.fftfreq(power.shape[1],1/5e6))
    np.savez_compressed(output/f'run{run:05d}_prefix_IminusQ.npz',frequency_hz=freq,PSD_ADC_V2_Hz=power)
    record={'run':run,'scope':f'first {maxspec} original SPEC only; no stationarity or full-run spectrum claim',
        'events':events,'SPEC_bank_sha256':bank_hash,'metadata':meta,'max_exact_conjugation_relative_error':max(errors),
        'IQ_convention':'I-iQhardware','ADC_scale_V_per_count':4/65535,'elapsed_s':time.monotonic()-start,
        'temperature_ODB':{k:{'Event_ID':v['Common']['Event ID'],'Settings':v.get('Settings',{}),'BOR_Input':v.get('Variables',{}).get('Input')} for k,v in odb['Equipment'].items() if k.startswith('Temp_')},
        'observed_prefix_INPT':inpt}
    (output/f'run{run:05d}_raw_check.json').write_text(json.dumps(record,indent=2)+'\n')
    print('raw check',run,'SPEC',len(events),'conjugation error',max(errors),flush=True)
    return record

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--prefix-SPEC',type=int,default=8);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    a.output.mkdir(parents=True);corrected=a.output/'corrected_fft_by_run';corrected.mkdir()
    provenance=[];ledger={str(Path(__file__).resolve()):sha(__file__)}
    for run in range(680,940):
        directory=RUNTIME/'job_to_submit'/f'{run:05d}';statepath=directory/'job_state.json';state=json.loads(statepath.read_text());arch=ARCHIVE/f'run{run:05d}.npz';jobcopy=directory/arch.name
        assert sha(jobcopy)==sha(arch),'Execution artifact differs from archive'
        cluster=state['cluster_id'];stdout=directory/f'stdout-{cluster}.0.txt';text=stdout.read_text()
        argsline=next(s for s in text.splitlines() if s.startswith('Arguments: '));args=argsline.split()[1:]
        assert int(args[1])==run and int(args[6])==state['iq_sign']
        expected=1 if run in SUSPECT else -1;assert state['iq_sign']==expected and state['reco_version']=='1.1'
        entry={'run':run,'iq_sign':state['iq_sign'],'reco_version':state['reco_version'],'cluster_id':cluster,
            'job_state':str(statepath),'stdout':str(stdout),'Arguments':argsline,'archive':str(arch),'archive_sha256':sha(arch),
            'job_artifact':str(jobcopy),'job_artifact_sha256':sha(jobcopy),'artifact_identical':True}
        provenance.append(entry)
        for path in [statepath,stdout,arch]:ledger[str(path)]=sha(path)
    # Source family records explicit parameter use and ADC denominator; exact historical source SHA is unavailable.
    source=REPO/'examples/analyze_midas_iq_fft_4ms_paral-pipe.py';ledger[str(source)]=sha(source)
    for path in [REPO/'examples/iq_acquisition_metadata.py']:ledger[str(path)]=sha(path)
    with ProcessPoolExecutor(max_workers=3) as pool:
        checks=list(pool.map(check_raw,[(run,str(a.output),a.prefix_SPEC) for run in SUSPECT+CONTROLS]))
    for run in SUSPECT:
        path=ARCHIVE/f'run{run:05d}.npz'
        with np.load(path) as z:arrays={k:z[k] for k in z.files}
        for mi in range(3):
            key=f'fft_amp_mode{mi}_SPECs';before=arrays[key];after=reflect_shifted(before)
            assert np.array_equal(reflect_shifted(after),before) and np.sum(after,dtype=float)==np.sum(before,dtype=float)
            arrays[key]=after
        arrays['iq_sign']=np.array(-1);arrays['original_iq_sign']=np.array(1)
        arrays['provenance_json']=np.array(json.dumps({'source':str(path),'source_sha256':sha(path),'operation':'exact FFT conjugation frequency reindexing, no amplitude correction','actual_NFFT':len(after),'source_reco_version':'1.1','source_job_state':str(RUNTIME/'job_to_submit'/f'{run:05d}'/'job_state.json'),'source_convention_proven_by':'job arguments, byte-identical execution artifact, signed original-SPEC check','new_convention':'I-iQhardware','original_archives_preserved':True}))
        np.savez_compressed(corrected/path.name,**arrays)
    result={'status':'validated','runs_audited':260,'job_iq_sign_counts':{'minus1':253,'plus1':7},'corrected_runs':SUSPECT,'controls':CONTROLS,
        'software_difference':'All jobs report reco_version1.1 and same script family; documented differing parameter iq_sign. Exact executed source snapshot SHA absent; do not claim byte-identical historical software.',
        'archive_identity_verified':True,'raw_full_runs_reconstructed':0,'raw_prefix_SPEC_per_run':a.prefix_SPEC,
        'correction':'Lossless Pminus(f)=Pplus(-f), with actual odd N=16383. Preserve all powers and normalization, not an empirical curve match.',
        'raw_checks':[{'run':r['run'],'max_exact_conjugation_relative_error':r['max_exact_conjugation_relative_error']} for r in checks],
        'execution_provenance':provenance,'input_sha256':ledger}
    assert all(sha(p)==v for p,v in ledger.items())
    (a.output/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print('VALIDATED all260signs;7correctedcopies;originalsunchanged',flush=True)
if __name__=='__main__':main()
