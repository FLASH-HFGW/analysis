"""Matched historical envelope fits for step 7, with a five-SPEC MC check.

Run from any directory. Scientific products remain outside the source repository.
"""
from pathlib import Path
import csv, hashlib, json, sys, time
import numpy as np
from scipy.fft import fft, ifft, next_fast_len
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
SOURCE=Path(__file__).resolve()
sys.path.insert(0,str(SOURCE.parents[2]/'examples'))
from fit_iq_correlation_decay import fit_upper_envelope
R=Path('/home/mazzitel/HFGW/analysis-work/Run2');O=R/'simulation/step7/decay_times';O.mkdir(parents=True,exist_ok=True)
scanpath=R/'simulation/step7/expected_response_scan.npz'
physpath=R/'simulation/step6/metrics.json'
old=R/'staging/legacy-repository/autoreco/noise_continuous/periodicity_run680'
reference=json.loads((old/'positive_envelope_fit.json').read_text())['modes']
phys=json.loads(physpath.read_text())['mode_results']
scan=np.load(scanpath); original=np.load(old/'periodicity_diagnostic.npz')
lag=scan['lag_s']; us=lag*1e6; fs=5e6;B=2**20;L=65537;M=next_fast_len(B+L-1);N=5*B
windows={'primary_0p3_4':(.3,4.),'sensitivity_0p3_3':(.3,3.),'sensitivity_0p3_5':(.3,5.),'sensitivity_0p7_4':(.7,4.)}
alphas=[1.,.5,.25,.1];rows=[];arrays={};report={'status':'running','modes':{}};start=time.perf_counter()
def fits(g):
 out={}
 for key,win in windows.items():
  try:
   f=fit_upper_envelope(us,g.real,window=win)
   f['near_tau_bound']=bool(f['tau_us']>=99 or f['tau_us']<=.00101)
   out[key]=f
  except (ValueError,RuntimeError) as ex:out[key]={'error':str(ex)}
 return out

def synthesize(S,index):
 # Identical full-run reference synthesis, five blocks, paired noise across alpha.
 imp=np.fft.fftshift(ifft(np.sqrt(fs*S)));n=len(S)
 fir=imp[n//2-L//2:n//2+L//2+1];H=fft(fir,M)
 target=fs*np.mean(S);power=np.sum(abs(fir)**2)
 assert abs(power/target-1)<.001
 rng=np.random.default_rng(20261115+100*index)
 def white(n):return (rng.standard_normal(n)+1j*rng.standard_normal(n))/np.sqrt(2)
 history=white(L-1);parts=[];step=4/65535;clipped=0
 for block in range(5):
  inp=np.r_[history,white(B)];z=ifft(fft(inp,M)*H)[L-1:L-1+B];history=inp[-(L-1):].copy()
  ci=np.round(z.real/step);cq=np.round(z.imag/step)
  clipped+=int(np.count_nonzero((ci<-32768)|(ci>32767)|(cq<-32768)|(cq>32767)))
  parts.append((np.clip(ci,-32768,32767)+1j*np.clip(cq,-32768,32767))*step)
 assert clipped==0
 z=np.concatenate(parts);del parts;z-=z.mean()
 co=ifft(abs(fft(z,2*N))**2)[:201]/(N-np.arange(201));g=co/co[0].real
 for k in (1,2,20,200):np.testing.assert_allclose(co[k],np.mean(z[k:]*z[:-k].conj()),rtol=1e-9,atol=1e-14)
 w=np.hanning(N);P=np.fft.fftshift(abs(fft(z*w))**2/(fs*np.sum(w*w)))
 ff=np.fft.fftshift(np.fft.fftfreq(N,1/fs)).reshape(-1,256).mean(axis=1)
 return g,ff,P.reshape(-1,256).mean(axis=1),float(power/target-1)

fig,axs=plt.subplots(3,4,figsize=(17,10),sharex=True,sharey=True)
for index,(mode,p) in enumerate(phys.items()):
 data=original[mode+'_normalized_covariance'];df=fits(data)
 assert df['primary_0p3_4']['tau_us']==reference[mode]['tau_us']
 modeout={'cavity_amplitude_tau_us':1e6*p['ql']/(np.pi*p['f0_hz']),'data':df,'variants':{}}
 curves={'Data':(data,df)}
 for alpha in alphas:
  key=f'alpha_{alpha:g}';g=scan[f'{mode}_{key}_g1'];expected=fits(g)
  S=np.fft.ifftshift(scan[f'{mode}_{key}_psd'])
  gm,ff,psd,firerr=synthesize(S,index);empirical=fits(gm)
  assert np.max(abs(gm[:11]-g[:11]))<.003
  # alpha=1 must reproduce the frozen baseline, including the random realization.
  if alpha==1:
   baseline=np.load(R/f'simulation/toy_ODB_cal5_data2_LF_20261116/comparison/{mode}_comparison.npz')
   np.testing.assert_allclose(gm,baseline['toy_g1'],rtol=1e-9,atol=1e-12)
  modeout['variants'][key]={'expected':expected,'five_SPEC_MC':empirical,'FIR_power_relative_error':firerr}
  arrays[f'{mode}_{key}_mc_g1']=gm;arrays[f'{mode}_{key}_mc_psd']=psd
  curves[f'Expected {alpha:g}']=(g,expected)
  if alpha==.1:curves['MC 0.1']=(gm,empirical)
  for pop,fsfit in [('expected',expected),('five_SPEC_MC',empirical)]:
   primary=fsfit['primary_0p3_4']
   taus=[v['tau_us'] for v in fsfit.values() if 'tau_us' in v]
   rows.append(dict(mode=mode,population=pop,alpha=alpha,cavity_tau_us=modeout['cavity_amplitude_tau_us'],tau_us=primary.get('tau_us'),offset=primary.get('offset'),r2=primary.get('r_squared_on_selected_peaks'),tau_window_min_us=min(taus) if taus else None,tau_window_max_us=max(taus) if taus else None))
  report['modes'][mode]=modeout
  (O/'progress.json').write_text(json.dumps({'mode':mode,'alpha':alpha,'elapsed_s':time.perf_counter()-start}))
  print(mode,key,'expected',expected['primary_0p3_4'].get('tau_us'),'MC',empirical['primary_0p3_4'].get('tau_us'),flush=True)
 for col,title in enumerate(['Data','Expected 1','Expected 0.1','MC 0.1']):
  g,fitset=curves[title];ax=axs[index,col];ax.plot(us,g.real,lw=.9,color='#007F86')
  fit=fitset['primary_0p3_4']
  if 'tau_us' in fit:
   tt=np.linspace(fit['plot_range_us'][0],4,300)
   ax.plot(tt,fit['offset']+fit['amplitude']*np.exp(-tt/fit['tau_us']),color='#D98726',lw=2,label=f"tau={fit['tau_us']:.3f} us; R2={fit['r_squared_on_selected_peaks']:.3f}")
   ax.scatter(fit['peak_lag_us'],fit['peak_covariance'],s=13,color='#D98726');ax.legend(fontsize=7)
  ax.set(title=f'{mode}: {title}',xlim=(0,10),ylim=(-.08,.05),xlabel='Lag [us]',ylabel='Re g1');ax.axhline(0,color='gray',lw=.5);ax.grid(alpha=.2)
 report['modes'][mode]=modeout
fig.suptitle('Same historical fit: signed upper maxima, C + A exp(-t/tau), 0.3-4 us',fontsize=13)
fig.tight_layout();fig.savefig(O/'matched_decay_fits.png',dpi=180);plt.close(fig)
arrays['lag_s']=lag;arrays['mc_frequency_hz']=ff
np.savez_compressed(O/'short_MC_comparison.npz',**arrays)
with (O/'decay_times.csv').open('w') as out:
 writer=csv.DictWriter(out,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
report.update(status='complete',samples_per_mode_per_variant=N,duration_s=N/fs,wall_s=time.perf_counter()-start,fit_method='Original fit_upper_envelope; signed maxima incl negative, C free; primary0.3-4us; plot0-10us',windows_us=windows,MC_method='65537 tap overlap-save FIR, random prehistory, shared baseline seeds across alpha, ADC +/-2V; one paired realization per variant',limitations=['Window sensitivity is not a confidence interval','Single MC realization is an estimator check, not an uncertainty ensemble','Cavity tau is not automatically the total receiver-noise envelope tau','A good temporal fit does not validate the assumed LF hardware transfer'],input_sha256={str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in [SOURCE,scanpath,physpath,old/'periodicity_diagnostic.npz',old/'positive_envelope_fit.json',SOURCE.parents[2]/'examples/fit_iq_correlation_decay.py']})
(O/'fit_results.json').write_text(json.dumps(report,indent=2));print('COMPLETE',flush=True)
