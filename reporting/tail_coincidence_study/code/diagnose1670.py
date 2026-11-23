"""Single-pass Run 1670 diagnostic, preserving the validated raw reader."""
import json
from pathlib import Path
import sys
import time
import resource

import numpy as np
from scipy.fft import fft, ifft, next_fast_len

from stream_longitudinal import (MODES, FS, SCALE, STUDY, archived_inputs, csv_write,
                                 gaussian_tail, group_products, stream, write_json)
sys.path.insert(0, str(STUDY.parents[1]/'examples'))
from fit_iq_correlation_decay import fit_upper_envelope

RUN = 1670
N = 1048576000
BIN = 500000
PREFIX = 5*2**20
LAGS = (1, 10, 100)
TABLES = STUDY/'tables/run1670'
RECEIPT = STUDY/'validation/run1670/stream.json'
PHASE_BINS = 128


def save(name, rows, fields=None):
    csv_write(TABLES/f'{name}.csv', fields or list(rows[0]), rows)


class Observer:
    def __init__(self):
        self.moments = np.zeros((3, 8, (N+BIN-1)//BIN))
        self.constellation = np.zeros((3,128,128), dtype=np.int64)
        self.amplitude = np.zeros((3,1024), dtype=np.int64)
        self.phase = np.zeros((3,4,PHASE_BINS),dtype=np.int64)
        self.history = [np.empty(0, complex) for _ in MODES]
        self.prefix = np.empty((3,PREFIX),complex)
        self.spectral = []

    def __call__(self, j, received, iraw, qraw, amp, cuts, positions):
        i = iraw*SCALE
        q = -(qraw*SCALE)
        z = i+1j*q
        for k, x in enumerate((i,q,i*i,q*q,i*q,amp)):
            self.moments[j,k,positions] += np.add.reduceat(x,cuts[:-1])
        self.constellation[j] += np.bincount(
            ((iraw.astype(np.int32)+32768)//512)*128+(32767-qraw.astype(np.int32))//512,
            minlength=128**2).reshape(128,128)
        ab = np.minimum((amp/(np.sqrt(8)/1024)).astype(np.int32),1023)
        self.amplitude[j] += np.bincount(ab,minlength=1024)
        if received < PREFIX:
            count = min(len(z), PREFIX-received)
            self.prefix[j,received:received+count] = z[:count]
        phase = np.angle(z)
        valid = amp>0
        self.phase[j,0] += self.hist_phase(phase[valid])
        self.moments[j,6,positions] += np.add.reduceat(np.where(valid,np.cos(phase),0),cuts[:-1])
        self.moments[j,7,positions] += np.add.reduceat(np.where(valid,np.sin(phase),0),cuts[:-1])
        both = np.r_[self.history[j],z]
        h = len(self.history[j])
        for k, lag in enumerate(LAGS,1):
            start = max(h,lag)
            pair = both[start:]*both[start-lag:len(both)-lag].conj()
            self.phase[j,k] += self.hist_phase(np.angle(pair[pair!=0]))
        self.history[j] = both[-max(LAGS):].copy()

    @staticmethod
    def hist_phase(x):
        ix = np.clip(((x+np.pi)*(PHASE_BINS/(2*np.pi))).astype(np.int32),0,PHASE_BINS-1)
        return np.bincount(ix,minlength=PHASE_BINS)

    def spectrum(self, mode, f, wp, bg, scale):
        # Retain the two measured TM012 bins and compact dominant-peak/band summaries.
        fixed = {'old_IF':-492750.5,'new_IF':-463750.5,'main_branch_prediction':-503750.5}
        if mode != 'TM012':
            fixed = {'mode_reference': -28000 if mode=='TM010' else 1250000}
        for name, center in fixed.items():
            ix = int(np.argmin(abs(f-center)))
            for sec,p in enumerate(wp[:,ix]):
                self.spectral.append(dict(mode=mode, second=sec, kind=name, frequency_Hz=f[ix],
                                          PSD_V2_Hz=p, normalized_ratio=p/(bg[ix]*scale[sec])))


def describe(sums, n):
    i,q,ii,qq,iq,a,pc,ps = sums/n
    vi,vq,cov = ii-i*i,qq-q*q,iq-i*q
    variance = vi+vq
    return dict(mean_I_V=i, mean_Q_V=q, RMS_V=np.sqrt(ii+qq), var_I_V2=vi,
                var_Q_V2=vq,cov_I_Q_V2=cov,mean_amplitude_V=a,
                properness_ratio=np.hypot(vi-vq,2*cov)/variance,
                pseudo_real_V2=vi-vq,pseudo_imag_V2=2*cov,
                phase_mean_cos=pc,phase_mean_sin=ps)


def prefix_products(prefix):
    psd, acf, fits = [], [], []
    for mode, trace in zip(MODES,prefix):
        x=trace-trace.mean()
        w=np.hanning(len(x))
        density=abs(fft(x*w))**2/(FS*np.dot(w,w))
        expected=np.dot(abs(x)**2,w*w)/np.dot(w,w)
        np.testing.assert_allclose(density.sum()*FS/PREFIX,expected,rtol=1e-10)
        freq=np.fft.fftshift(np.fft.fftfreq(PREFIX,1/FS)).reshape(-1,256).mean(axis=1)
        power=np.fft.fftshift(density).reshape(-1,256).mean(axis=1)
        psd.extend(dict(mode=mode,frequency_Hz=f,PSD_V2_Hz=p) for f,p in zip(freq,power))
        c=ifft(abs(fft(x,next_fast_len(2*PREFIX-1)))**2)[:201]/(PREFIX-np.arange(201))
        np.testing.assert_allclose(c[0].real,np.mean(abs(x)**2),rtol=1e-10)
        g=c/c[0].real
        for lag in LAGS:
            np.testing.assert_allclose(c[lag],np.mean(x[lag:]*x[:-lag].conj()),rtol=1e-9,atol=1e-14)
        lag_us=np.arange(201)/FS*1e6
        fit=fit_upper_envelope(lag_us,g.real)
        first=next((float(lag_us[j]) for j in range(1,197) if np.all(abs(g[j:j+5])<.01)),None)
        fits.append(dict(mode=mode,upper_envelope=fit,first_five_below_0p01_us=first))
        acf.extend(dict(mode=mode,lag_samples=k,lag_us=t,g_real=v.real,g_imag=v.imag,g_abs=abs(v))
                   for k,(t,v) in enumerate(zip(lag_us,g)))
    save('prefix_PSD',psd)
    save('prefix_ACF',acf)
    return fits


def main():
    if RECEIPT.exists():
        raise SystemExit('Validated Run 1670 receipt already exists')
    started=time.monotonic()
    raw=Path('/home/mazzitel/flash-data/data/LNF/run01670.mid.gz')
    root=Path('/home/mazzitel/flash-data/analysis/autoreco/Run3/run01670_iq_v3.1.root')
    before=raw.stat()
    with raw.open('rb') as f:
        assert f.read(3)==b'\x1f\x8b\x08'
    row=dict(run=RUN,samples=N,raw_path=str(raw),root_path=str(root),
             raw_bytes=before.st_size,raw_mtime_ns=before.st_mtime_ns)
    o=Observer()
    thresholds, diagnostics, psd, temps, adc, pps, breaks, requested, root_wall, lines = archived_inputs(row,o.spectrum)
    assert len(adc)==1000 and adc['samples'].sum()==N
    print('ROOT preflight complete',requested,flush=True)
    counts,powers,exposure,indices,amps,receipt=stream(
        row,thresholds,adc,pps,breaks,bin_samples=BIN,observer=o)
    # CRC, EOR, sample/serial and PPS validation completed before any scientific export.
    peaks,groups,tuples,controls,coincidence=group_products(indices,amps,N)
    summaries, series, hits, amplitude, phase, constellation = [],[],[],[],[],[]
    for j,(mode,d) in enumerate(zip(MODES,diagnostics)):
        m=describe(o.moments[j].sum(axis=1),N)
        for k,root_key,sign in [('mean_I_V','mean_I_V',1),('mean_Q_V','mean_Qhardware_V',-1),
                ('var_I_V2','var_I_V2',1),('var_Q_V2','var_Q_V2',1),
                ('cov_I_Q_V2','cov_I_Qhardware_V2',-1),('RMS_V','rms_V',1)]:
            np.testing.assert_allclose(m[k],sign*d['moments'][root_key],rtol=1e-6,atol=1e-13)
        np.testing.assert_allclose(o.moments[j,2]+o.moments[j,3],powers[j],rtol=1e-12)
        total=counts[j].sum(axis=1)
        assert total[2]==len(indices[j]) and np.all(amps[j]>thresholds[j,2])
        assert o.amplitude[j].sum()==o.constellation[j].sum()==N
        expected=N*gaussian_tail(thresholds[j,2],d['moments'],8192)
        np.testing.assert_allclose(expected,N*gaussian_tail(thresholds[j,2],d['moments'],4096),rtol=1e-9)
        summaries.append(dict(mode=mode,samples=N,**m,T3=int(total[0]),T5=int(total[1]),T7=int(total[2]),
                       sigma_Rayleigh_V=d['sigma'],T3_V=thresholds[j,0],T5_V=thresholds[j,1],
                       T7_V=thresholds[j,2],matched_expected_T7=expected,matched_ratio=total[2]/expected,
                       primary_clusters=len(peaks[j]),full_band_PSD_V2=d['full_band_psd_power_V2']))
        for factor in (1,10):
            for a in range(0,len(exposure),factor):
                b=min(a+factor,len(exposure))
                n=int(exposure[a:b].sum())
                c=counts[j,:,a:b].sum(axis=1)
                series.append(dict(mode=mode,nominal_bin_s=factor*BIN/FS,start_s=a*BIN/FS,
                                   samples=n,**describe(o.moments[j,:,a:b].sum(axis=1),n),
                                   T3=int(c[0]),T5=int(c[1]),T7=int(c[2])))
        hits.extend(dict(mode=mode,index=i,amplitude_V=a) for i,a in zip(indices[j],amps[j]))
        survival=N
        width=np.sqrt(8)/1024
        for k,count in enumerate(o.amplitude[j]):
            left=k*width/d['sigma']
            right=(k+1)*width/d['sigma']
            amplitude.append(dict(mode=mode,left_A_over_sigma=left,
                                  normalized_PDF=count/N/(right-left),observed_CCDF=survival/N,
                                  Rayleigh_CCDF=np.exp(-left**2/2),count=count))
            survival-=count
        for k,label in enumerate(('phase','increment_1','increment_10','increment_100')):
            items=o.phase[j,k]
            phase.extend(dict(mode=mode,kind=label,angle_rad=-np.pi+(b+.5)*2*np.pi/PHASE_BINS,
                             count=c,mass=c/items.sum()) for b,c in enumerate(items))
        for bi,bq in np.argwhere(o.constellation[j]):
            constellation.append(dict(mode=mode,I_V=(bi*512-32512)*SCALE,
                       Q_V=(bq*512-32511)*SCALE,count=o.constellation[j,bi,bq]))
    save('summary',summaries); save('time_series',series); save('T7_samples',hits)
    save('clusters',groups); save('pairs',tuples,['window_us','kind','indices','separation_us'])
    save('coincidence_summary',coincidence); save('time_shifts',controls)
    save('amplitude',amplitude); save('phase',phase); save('constellation',constellation)
    save('spectral_seconds',psd); save('line_seconds',o.spectral); save('full_band_lines',lines)
    save('temperature',temps)
    fits=prefix_products(o.prefix)
    receipt.update(complete=True,raw_path=str(raw),root_path=str(root),root_requested_bytes=requested,
                   root_wall_s=root_wall,prefix_samples=PREFIX,prefix_wall_s=PREFIX/FS,
                   phase_valid_counts=o.phase.sum(axis=2),correlation=fits,
                   raw_waveforms_retained=False,peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   total_wall_s=time.monotonic()-started,
                   cpu_s=resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime)
    write_json(RECEIPT,receipt)
    print('RUN 1670 VALIDATED',[(r['mode'],r['T3'],r['T5'],r['T7']) for r in summaries],flush=True)


if __name__=='__main__':
    main()
