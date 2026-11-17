"""Separate resonance-ROI pilot; old DC-bank products are immutable references.

One raw pass for the explicitly requested run only. BOR coordinates fail closed.
No output recentering, no physical fit and no nominal input-referred gain applied.
"""
from pathlib import Path
import argparse,hashlib,json,sys,time
import numpy as np,h5py
from scipy.fft import fft,ifft
from iq_acquisition_metadata import read_bor_coordinates,resonance_centers,MODES,PAIRS
from iq_noise_io import save_results_h5
from iq_noise_v2 import ComplexMoments
from resonance_filter_bank import ResonanceBank
OFFSETS=np.array([-500000,-250000,-100000,0,100000,250000,500000],float)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
class Accumulator:
    def __init__(self,fs,nfft=16384,binwidth=1e-5):
        self.fs=fs;self.nfft=nfft;self.binwidth=binwidth;self.m=ComplexMoments();self.amp_sum=0.;self.hist=np.zeros(4096,np.int64);self.left=np.empty(0,complex);self.p=np.zeros(nfft);self.segments=0;self.w=np.hanning(nfft);self.rows=[];self.window=[]
    def update(self,y,event,keep_window=False):
        self.m.update(y);amp=abs(y);self.amp_sum+=float(amp.sum());counts=np.bincount(np.floor(amp/self.binwidth).astype(np.int64));
        if len(counts)>len(self.hist):self.hist=np.pad(self.hist,(0,len(counts)-len(self.hist)))
        self.hist[:len(counts)]+=counts;self.rows.append((event,len(y),float(np.sqrt(np.mean(amp**2))),float(amp.mean()),float(y.real.mean()),float(y.imag.mean())))
        values=np.r_[self.left,y];nb=len(values)//self.nfft
        if nb:
            f=fft(values[:nb*self.nfft].reshape(nb,self.nfft)*self.w,axis=1);self.p+=np.sum(abs(f)**2,axis=0);self.segments+=nb
        self.left=values[nb*self.nfft:].copy()
        if keep_window:self.window.append(y.copy())
    def export(self):
        moments=self.m.export();counts=self.hist;end=max(1,int(np.flatnonzero(counts)[-1])+1);z=np.concatenate(self.window);n=len(z);lagcount=min(501,n);cov=ifft(abs(fft(z,2*n))**2)[:lagcount]/(n-np.arange(lagcount))
        psd=self.p/(self.segments*self.fs*np.sum(self.w**2))
        events=np.array(self.rows)
        return {'moments_ADC':moments,'amplitude_mean_V':self.amp_sum/self.m.n,'amplitude_edges_V':np.arange(end+1)*self.binwidth,'amplitude_counts':counts[:end],'PSD_frequency_baseband_hz':np.fft.fftshift(np.fft.fftfreq(self.nfft,1/self.fs)),'PSD_total_V2_Hz':np.fft.fftshift(psd),'PSD_segments':self.segments,'PSD_samples_used':self.segments*self.nfft,'PSD_detrend':'none; coherent output mean retained','selected_first5SPEC_output_V':z,'selected_lag_s':np.arange(lagcount)/self.fs,'selected_total_autocovariance_V2':cov,'selected_total_g1':cov/cov[0].real,'selected_scope':'first5inputSPEC;initialFIR transient excluded;no output-mean subtraction','events':{name:events[:,i].astype(np.int64) if i<2 else events[:,i] for i,name in enumerate(['SPEC_index','samples','RMS_ADC_V','mean_amplitude_ADC_V','mean_I_ADC_V','mean_Qeff_ADC_V'])}}

def main():
    p=argparse.ArgumentParser();p.add_argument('raw',type=Path);p.add_argument('--electronic-reference',type=Path,required=True);p.add_argument('--thesis-reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--fft-workers',type=int,default=3);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    source_files=[Path(__file__),Path(__file__).with_name('resonance_filter_bank.py'),Path(__file__).with_name('iq_acquisition_metadata.py')]
    code_hashes={path.name:sha(path) for path in source_files}
    start=time.monotonic();meta=read_bor_coordinates(a.raw);fs=meta['fs_hz'];center_map=resonance_centers(meta);centers=np.array([center_map[m] for m in MODES]);bank=ResonanceBank(fs,centers,workers=a.fft_workers);outfs=fs/bank.decimation
    original_sha=sha(a.electronic_reference);thesis_sha=sha(a.thesis_reference);physical=json.loads(a.thesis_reference.read_text())['mode_results']
    with h5py.File(a.electronic_reference,'r') as old:
        if Path(old['summary/input'].asstr()[()]).name!=a.raw.name:raise ValueError('Reference belongs to a different raw run')
        if not old['summary/reached_eof'][()] or old['summary/iq_sign'][()]!=-1:raise ValueError('Need complete compatible electronic reference')
        if old['summary/fs_hz'][()]!=fs:raise ValueError('Sampling differs from reference')
        stored=float(old['summary/input_range_v'][()]);mu=np.array([complex(old[f'dc_removed/modes/{m}/mean_i_v'][()],old[f'dc_removed/modes/{m}/mean_q_v'][()])*meta['modes'][m]['ADC_peak_V']/stored for m in MODES]);expected_n=int(old['summary/samples'][()]);reference_rms={m:old[f'filtered_bands/modes/{m}/band_08/events/rms_v'][:]*meta['modes'][m]['ADC_peak_V']/stored for m in MODES}
    accum={(m,bi):Accumulator(outfs) for m in MODES for bi in range(7)}
    sys.path.insert(0,'/cvmfs/sft-flash.infn.it/package/midas/python');import midas.file_reader
    r=midas.file_reader.MidasFile(str(a.raw),use_numpy=True);events=samples=0;process_time=0.;scales=np.array([meta['modes'][m]['ADC_V_per_count'] for m in MODES]);progress=a.output.with_suffix('.progress.json')
    try:
        for ev in r:
            if ev.header.is_midas_internal_event() or 'SPEC' not in ev.banks:continue
            frames=np.asarray(ev.banks['SPEC'].data,dtype=np.uint16).view(np.int16).reshape(-1,8)
            z=np.array([(frames[:,ci].astype(float)-1j*frames[:,cq].astype(float))*scales[i]-mu[i] for i,(ci,cq) in enumerate(PAIRS.values())]);before=time.monotonic();t,y=bank.process(z)
            for mi,m in enumerate(MODES):
                for bi in range(7):accum[m,bi].update(y[mi,bi],events,events<5)
            process_time+=time.monotonic()-before;events+=1;samples+=len(frames)
            if events%10==0:
                state={'status':'running','SPEC':events,'samples':samples,'elapsed_s':time.monotonic()-start,'processing_s':process_time,'approx_remaining_s':(time.monotonic()-start)*(expected_n/samples-1)};progress.write_text(json.dumps(state,indent=2)+'\n');print(json.dumps(state),flush=True)
    finally:r.file.close()
    if samples!=expected_n:raise ValueError(f'Incomplete/mismatched run: {samples} vs {expected_n}')
    modes={};checks={}
    for m in MODES:
        modes[m]={}
        for bi,off in enumerate(OFFSETS):
            value=accum[m,bi].export();value.update(offset_from_nominal_resonance_hz=float(off),input_center_hz=center_map[m][bi],nominal_input_interval_hz=[center_map[m][bi]-25000,center_map[m][bi]+25000]);modes[m][f'band_{bi:02d}']=value
            assert int(value['amplitude_counts'].sum())==value['moments_ADC']['n']
        # Exact shared +1MHz input window = new resonance offset -250kHz.
        if center_map[m][1]!=1e6:checks[m]={'shared_window':'not identical; changed BOR coordinates'}
        else:
            current=modes[m]['band_01']['events']['RMS_ADC_V'];old=reference_rms[m];rel=float(np.max(abs(current/old-1)));checks[m]={'shared_window_hz':1e6,'old_offset_hz':1e6,'new_offset_hz':-250000,'max_perSPEC_RMS_relative_difference':rel,'passed':rel<1e-6};assert checks[m]['passed'],checks[m]
    assert sha(a.electronic_reference)==original_sha and sha(a.thesis_reference)==thesis_sha
    assert all(sha(path)==code_hashes[path.name] for path in source_files),'Source changed during processing'
    result={'schema_version':1,'product_version':'resonance-pilot-v1','summary':{'input':str(a.raw),'samples':samples,'events_SPEC':events,'acquired_duration_s':samples/fs,'reached_eof':True,'fs_hz':fs,'filtered_fs_hz':outfs,'iq_sign':-1,'elapsed_s':time.monotonic()-start,'filter_processing_and_statistics_s':process_time,'scope':'run680 only;full-run moments,histograms,Welch PSD;first5SPEC total autocorrelation','input_DC_subtraction':'one full-run input mean from immutable v2 reference, corrected once to physical BOR ADC range','post_demodulation_mean_subtraction':False,'coherent_band_center_signal_retained':True},'acquisition_metadata':meta,'physical_reference_thesis_fit':{'source':str(a.thesis_reference),'sha256':thesis_sha,'usage':'separate physical fitted/nominal reference, never substituted for BOR centers','modes':{m:{k:physical[m][k] for k in ['f0_hz','q0','kappa1','kappa2']} for m in MODES}},'filter_banks':{'electronic_DC_reference':{'source_HDF5':str(a.electronic_reference),'source_sha256':original_sha,'unchanged':True,'centers_hz':[0.,0.,0.],'scope':'existing nine-band long-term products;not reconstructed here'},'resonance_ROI':{'configuration':{'offsets_hz':OFFSETS,'width_hz':50000.,'taps':2001,'FIR_coefficients':bank.h,'FIR_ENBW_two_sided_hz':float(fs*np.sum(bank.h**2)/np.sum(bank.h)**2),'decimation':bank.decimation,'sample_selection':'global n%20==0, n>=2000; time corrected for1000sample group delay','continuity':'input tail and global oscillator phase retained across SPEC','implementation':'shared-input-FFT complex-modulated FIR; phase at retained samples; independently validated against causal lfilter and legacy BandFilter','output_centering':'none'},'modes':modes}},'consistency_with_electronic_bank':checks,'provenance':{'analysis_source_sha256':code_hashes,'electronic_source_sha256':original_sha,'input_mean_I_ADC_V':mu.real,'input_mean_Qeff_ADC_V':mu.imag}}
    save_results_h5(a.output,result);summary={'status':'complete','output':str(a.output),'SPEC':events,'samples':samples,'elapsed_s':time.monotonic()-start,'consistency':checks};progress.write_text(json.dumps(summary,indent=2)+'\n');a.output.with_suffix('.summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
