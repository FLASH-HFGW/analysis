#!/usr/bin/env python3
"""Descriptive exponential fits to upper autocorrelation maxima."""
import json
from pathlib import Path
import numpy as np
from scipy.signal import find_peaks
from scipy.optimize import curve_fit

def fit_positive_envelope(lag_us, covariance, window=(.3,4.), tail_start_us=20.):
    t=np.asarray(lag_us,dtype=float);y=np.asarray(covariance,dtype=float)
    tail=y[t>=tail_start_us]
    if len(tail)<10:raise ValueError('Insufficient long-lag samples for a noise-floor estimate')
    floor=float(1.4826*np.median(abs(tail-np.median(tail))))
    peaks=find_peaks(y)[0]
    peaks=peaks[(t[peaks]>=window[0])&(t[peaks]<=window[1])&(y[peaks]>3*floor)]
    if len(peaks)<3:raise ValueError('Fewer than three resolved positive maxima')
    def model(x,a,tau):return a*np.exp(-x/tau)
    p,_=curve_fit(model,t[peaks],y[peaks],p0=(float(y[peaks[0]]),1.),
                  bounds=([0.,.001],[np.inf,100.]),maxfev=10000)
    pred=model(t[peaks],*p);residual=y[peaks]-pred
    r2=1-float(np.sum(residual**2)/np.sum((y[peaks]-y[peaks].mean())**2))
    return {'model':'upper positive-peak envelope A exp(-lag/tau), without offset',
            'amplitude':float(p[0]),'tau_us':float(p[1]),'r_squared_on_selected_peaks':r2,
            'peak_indices':peaks.tolist(),'peak_lag_us':t[peaks].tolist(),
            'peak_covariance':y[peaks].tolist(),'selected_range_us':[float(t[peaks[0]]),float(t[peaks[-1]])],
            'search_window_us':list(window),'noise_floor_mad':floor,'peak_selection':'local maxima > 3 robust tail-noise scales; exclude lag zero',
            'noise_tail_start_us':tail_start_us,
            'limitations':'descriptive 1/e decay time of selected positive peaks; not a full covariance model, period, stationarity time or independent-sample confidence interval'}

def fit_upper_envelope(lag_us, covariance, window=(.3,4.)):
    """Fit all upper local maxima in the window, including zero/negative values."""
    t=np.asarray(lag_us,dtype=float);y=np.asarray(covariance,dtype=float)
    peaks=find_peaks(y)[0]
    peaks=peaks[(t[peaks]>=window[0])&(t[peaks]<=window[1]+1e-12)]
    if len(peaks)<4:raise ValueError('Fewer than four upper maxima for a three-parameter fit')
    def model(x,a,tau,c):return c+a*np.exp(-x/tau)
    p,_=curve_fit(model,t[peaks],y[peaks],p0=(.04,1.,-.004),
                  bounds=([0.,.001,-1.],[np.inf,100.,1.]),maxfev=20000)
    pred=model(t[peaks],*p)
    return {'model':'upper-envelope local maxima: C + A exp(-lag/tau)',
            'amplitude':float(p[0]),'tau_us':float(p[1]),'offset':float(p[2]),
            'r_squared_on_selected_peaks':float(1-np.sum((y[peaks]-pred)**2)/np.sum((y[peaks]-y[peaks].mean())**2)),
            'peak_indices':peaks.tolist(),'peak_lag_us':t[peaks].tolist(),'peak_covariance':y[peaks].tolist(),
            'selected_range_us':[float(t[peaks[0]]),float(t[peaks[-1]])],
            'search_window_us':list(window),'plot_range_us':[float(t[peaks[0]]),float(window[1])],
            'peak_selection':'all local maxima in window, including weak and negative upper maxima; lag zero excluded; no positive-value censoring',
            'limitations':'descriptive finite-window 1/e decay of the exponential component relative to fitted C; C is not an inferred infinite-lag covariance; no independent-sample confidence interval; not an oscillation period or stationarity time'}

def main():
    root=Path(__file__).resolve().parents[1]
    source=Path('/home/mazzitel/flash-data/analysis/autoreco/Run2/noise_continuous/periodicity_run680/periodicity_diagnostic.npz')
    with np.load(source) as z:
        result={'version':2,'input':str(source),'scope':'first 1.048576 s of run 680, five continuous SPEC blocks',
                'modes':{m:fit_upper_envelope(z['lag_s']*1e6,z[m+'_normalized_covariance'].real)
                         for m in ('TM010','TM011','TM012')}}
    dest=source.with_name('positive_envelope_fit.json')
    if dest.exists():
        old=json.loads(dest.read_text())
        archive=dest.with_name('positive_envelope_fit_three_peaks.json')
        if 'modes' not in old and not archive.exists():archive.write_text(dest.read_text())
    dest.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
