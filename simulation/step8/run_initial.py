"""Unfitted step8 LF predictions and short MC, using only existing data products."""
from pathlib import Path
import hashlib,json,sys,time
import numpy as np,h5py
from scipy.fft import fft,ifft,next_fast_len
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from model import LFModel,lf_power,ideal_mean_variance,mean_variance_from_psd
SOURCE=Path(__file__).resolve();REPO=SOURCE.parents[2]
sys.path.insert(0,str(REPO/'examples'));from fit_iq_correlation_decay import fit_upper_envelope
sys.path.insert(0,str(REPO/'simulation/step7/dc_longterm_diagnostic'));from common import notch_metrics,COLORS
cfg=json.loads(SOURCE.with_name('parameters.json').read_text());model=LFModel(cfg);O=Path(cfg['output']);O.mkdir(parents=True,exist_ok=True)
DC=Path(cfg['DC_diagnostic']);diag=json.loads((DC/'interval_results.json').read_text());lt=list(__import__('csv').DictReader((DC/'longterm.csv').open()))
# Confirm recorded science LO states against the previous read-only BOR diagnostic.
hw=next(h for h in json.loads((DC/'hardware.json').read_text()) if h['run']==680)['LO']
assert cfg['primary_LO_hz']==hw['freq RS']
assert cfg['LF_primary_offset_hz']['TM011']==hw['freq Teled Ch1']
assert cfg['LF_primary_offset_hz']['TM012']==hw['freq Teled Ch2']
fs=cfg['fs_hz'];B=2**20;L=65537;M=next_fast_len(B+L-1);n=B;f=np.fft.fftfreq(n,1/fs);lag=np.arange(201)/fs
sizes=np.array([128,512,2048,8192,32768,131072,524288,B,2*B]);T=sizes/fs
report={'status':'running','fit_LF_parameters':False,'initial_parameters':cfg,'modes':{},'interpretations':'Same total Gaussian PSD. Two-source interpretation specifies equivalent shaped downstream noise; microscopic location is not identified.'};arrays={};start=time.perf_counter()

def synthesize(mode,index,interpretation,Sfull):
 source_spectra=[Sfull] if interpretation=='shelf' else [sum(model.analog(mode,f+a*fs,interpretation='no_LF')*(1-cfg['epsilon'])*lf_power(f+a*fs+cfg['LF_primary_offset_hz'][mode],cfg['fc_hz'],0) for a in (-1,0,1)),cfg['epsilon']*model.sampled(mode,f,interpretation='no_LF')]
 np.testing.assert_allclose(sum(source_spectra),Sfull,rtol=1e-14,atol=1e-24)
 rngs=[np.random.default_rng(20261117+index*100+interpretation.count('two')*10+j) for j in range(len(source_spectra))]
 def white(rng,length):return (rng.standard_normal(length)+1j*rng.standard_normal(length))/np.sqrt(2)
 histories=[white(rng,L-1) for rng in rngs];Hs=[];fir_errors=[]
 for S in source_spectra:
  impulse=np.fft.fftshift(ifft(np.sqrt(fs*S)));fir=impulse[n//2-L//2:n//2+L//2+1];Hs.append(fft(fir,M));fir_errors.append(float(np.sum(abs(fir)**2)/(fs*np.mean(S))-1))
  assert abs(fir_errors[-1])<.001
 row=next(r for r in lt if int(r['run'])==680 and r['mode']==mode);mu=complex(float(row['mean_I_ADC_V']),float(row['mean_Qeff_ADC_V']));step=2*cfg['ADC_peak_V']/cfg['ADC_counts_denominator'];parts=[];clipped=0
 for block in range(16):
  z=np.zeros(B,complex)
  for j,rng in enumerate(rngs):
   inp=np.r_[histories[j],white(rng,B)];z+=ifft(fft(inp,M)*Hs[j])[L-1:L-1+B];histories[j]=inp[-(L-1):].copy()
  z+=mu;ci=np.round(z.real/step);cq=np.round(z.imag/step);clipped+=int(np.count_nonzero((ci<-32768)|(ci>32767)|(cq<-32768)|(cq>32767)));parts.append((np.clip(ci,-32768,32767)+1j*np.clip(cq,-32768,32767))*step)
 assert clipped==0
 z=np.concatenate(parts);del parts
 sample_mu=z.mean();AC=float(np.mean(abs(z-sample_mu)**2));power=float(fs*np.mean(Sfull));sigma=np.sqrt(power/2)
 stability=[]
 for size in sizes:
  means=z[:len(z)//size*size].reshape(-1,size).mean(axis=1);stability.append(float(np.mean(abs(means-means.mean())**2)))
 z5=z[:5*B]-z[:5*B].mean();nn=len(z5);co=ifft(abs(fft(z5,2*nn))**2)[:201]/(nn-np.arange(201));g=co/co[0].real
 for k in (1,2,20,200):np.testing.assert_allclose(co[k],np.mean(z5[k:]*z5[:-k].conj()),rtol=1e-9,atol=1e-14)
 w=np.hanning(nn);P=np.fft.fftshift(abs(fft(z5*w))**2/(fs*np.sum(w*w)));ff=np.fft.fftshift(np.fft.fftfreq(nn,1/fs)).reshape(-1,256).mean(axis=1);pp=P.reshape(-1,256).mean(axis=1)
 edges=np.linspace(0,8*sigma+abs(mu),2049);hraw=np.histogram(abs(z),edges)[0];hac=np.histogram(abs(z-sample_mu),edges)[0];cdfraw=np.cumsum(hraw)/len(z);cdfac=np.cumsum(hac)/len(z)
 # Distribution predictions use model power and the independently measured injected offset.
 rice=stats.rice(b=abs(mu)/sigma,scale=sigma);ray=stats.rayleigh(scale=sigma)
 out=dict(samples=len(z),expected_AC2_ADC_V2=power,AC2_ADC_V2=AC,DC_expected_ADC_V=[mu.real,mu.imag],DC_measured_ADC_V=[sample_mu.real,sample_mu.imag],quantization_complex_variance_approx_V2=step**2/6,FIR_power_errors=fir_errors,clipped=clipped,variance_block_means_V2=stability,raw_Rice_binned_CDF_distance=float(np.max(abs(cdfraw-rice.cdf(edges[1:])))),centered_Rayleigh_binned_CDF_distance=float(np.max(abs(cdfac-ray.cdf(edges[1:])))),upper_envelope_fit=fit_upper_envelope(lag*1e6,g.real),real_g1_min_0p2_10us=float(g[1:51].real.min()))
 np.savez_compressed(O/f'{mode}_{interpretation}_MC.npz',lag_s=lag,g1=g,frequency_hz=ff,PSD_ADC_V2_Hz=pp,amplitude_edges_ADC_V=edges,raw_amplitude_counts=hraw,centered_amplitude_counts=hac,first_100000_ADC_V=z[:100000],block_time_s=T)
 return out,g,ff,pp,edges,hraw,hac

fig,axs=plt.subplots(3,3,figsize=(15,11));fig2,ax2=plt.subplots(1,3,figsize=(15,4.7));fig3,ax3=plt.subplots(3,2,figsize=(12,10));fig4,ax4=plt.subplots(3,2,figsize=(12,10));fig5,ax5=plt.subplots(1,3,figsize=(14,4))
for index,mode in enumerate(model.phys):
 S=model.sampled(mode,f);S2=model.sampled(mode,f,interpretation='two_sources');np.testing.assert_allclose(S,S2,rtol=1e-14,atol=1e-24)
 noLF=model.sampled(mode,f,interpretation='no_LF');old=model.sampled(mode,f,interpretation='old_calibration');wrong=model.sampled(mode,f,interpretation='double_counting_control')
 theory=ifft(S)[:201];theory/=theory[0].real
 arrays[mode+'_PSD']=np.fft.fftshift(S);arrays[mode+'_g1']=theory
 d=np.load(Path(cfg['reference_toy'])/'comparison'/f'{mode}_comparison.npz');fd=d['frequency_hz'];pd=d['data_psd_v2_hz'];dg=d['data_g1'];sf=np.fft.fftshift(f);ss=np.fft.fftshift(S)
 plateau=lambda ff,p:float(np.mean(p[(abs(ff)>.5e6)&(abs(ff)<1.5e6)]))
 shape=notch_metrics(abs(sf),ss);data_shape=notch_metrics(abs(fd),pd)
 # Direct PSD integration resolves arbitrarily small frequencies with smooth model.
 spectrum=lambda ff:model.sampled(mode,ff)
 vv=np.array([mean_variance_from_psd(spectrum,int(size),fs) for size in sizes]);vrecord=mean_variance_from_psd(spectrum,16*B,fs);vpopulation=vv-vrecord
 convergence=[mean_variance_from_psd(spectrum,int(size),fs,256)/value-1 for size,value in zip(sizes,vv)];assert max(abs(np.array(convergence)))<.003
 gd=diag['runs']['680'][mode];vd=np.array([r['variance_means_v2'] for r in gd['mean_stability']]);data_power=gd['distribution']['AC2_ADC_V2']
 empirical={}
 for interpretation in ['shelf','two_sources']:
  empirical[interpretation],gm,ff,pp,e,hr,ha=synthesize(mode,index,interpretation,S)
  if interpretation=='shelf':
   axs[index,0].plot(ff/1e3,10*np.log10(pp/plateau(ff,pp)),color=COLORS['toy'],alpha=.35,lw=.5,label='Shelf MC')
   centers=(e[:-1]+e[1:])/2;sig=np.sqrt(fs*np.mean(S)/2)
   ax4[index,0].stairs(ha/ha.sum()/np.diff(e)*sig,e/sig,color=COLORS['toy'],label='MC centered');xx=np.linspace(0,7,400);ax4[index,0].plot(xx,stats.rayleigh.pdf(xx),color=COLORS['theory'],ls='--',label='Rayleigh prediction');ax4[index,0].set(title=mode,xlabel='A / predicted sigma_q',ylabel='Density');ax4[index,0].legend(fontsize=7)
   cc=1-np.cumsum(ha)/ha.sum();ok=(cc>20/ha.sum())&(cc<.9999);ax4[index,1].plot(e[1:][ok]**2/(2*sig**2),np.log(cc[ok]),color=COLORS['toy'],label='MC CCDF');xx=np.linspace(0,15);ax4[index,1].plot(xx,-xx,color=COLORS['theory'],ls='--');ax4[index,1].set(title=mode,xlabel='A² / predicted AC²',ylabel='log CCDF');ax4[index,1].legend(fontsize=7)
  ax2[index].loglog(T,empirical[interpretation]['variance_block_means_V2'],'o',ms=4,label=interpretation+' MC',color=COLORS['toy'] if interpretation=='shelf' else COLORS['fit'])
 # Compare analytic prediction and data, both shape and fixed absolute units.
 axs[index,0].plot(fd/1e3,10*np.log10(pd/plateau(fd,pd)),color=COLORS['data'],lw=.6,label='Data');axs[index,0].plot(sf/1e3,10*np.log10(ss/plateau(sf,ss)),color=COLORS['toy'],lw=1,label='Initial prediction');axs[index,0].set(title=mode+' relative PSD',xlim=(-100,100),ylim=(-35,5),xlabel='Final IF [kHz]',ylabel='PSD / own plateau [dB]');axs[index,0].legend(fontsize=7)
 axs[index,1].plot(lag*1e6,dg.real,color=COLORS['data'],label='Data');axs[index,1].plot(lag*1e6,theory.real,color=COLORS['toy'],label='Initial prediction');axs[index,1].set(title=mode+' Re g1',xlim=(0,10),ylim=(-.08,.05),xlabel='Lag [us]');axs[index,1].legend(fontsize=7)
 axs[index,2].plot(lag*1e6,dg.imag,color=COLORS['data'],label='Data');axs[index,2].plot(lag*1e6,theory.imag,color=COLORS['toy'],label='Initial prediction');axs[index,2].set(title=mode+' Im g1',xlim=(0,10),ylim=(-.08,.08),xlabel='Lag [us]');axs[index,2].legend(fontsize=7)
 ax2[index].loglog(T,vd,'o-',color=COLORS['data'],label='Data run680');ax2[index].loglog(T,vpopulation,'--',color=COLORS['theory'],label='Sampled PSD, finite-record correction');ax2[index].set(title=mode,xlabel='Integration time [s]',ylabel='Variance of means [V² ADC]');ax2[index].legend(fontsize=6)
 ax3[index,0].plot(fd/1e3,pd,color=COLORS['data'],lw=.6,label='Data');ax3[index,0].plot(sf/1e3,ss,color=COLORS['toy'],lw=.8,label='Fixed normalization model');ax3[index,0].set(title=mode+' absolute PSD',xlim=(-100,100),xlabel='Final IF [kHz]',ylabel='PSD [V² ADC/Hz]');ax3[index,0].legend(fontsize=7)
 original,base,calLF=model.response(mode,sf);LF=lf_power(sf+cfg['LF_primary_offset_hz'][mode],cfg['fc_hz'],cfg['epsilon']);ax3[index,1].plot(sf/1e3,calLF,label='Fcal extracted conditionally',color=COLORS['fit']);ax3[index,1].plot(sf/1e3,LF,label='Fdata initial',color=COLORS['toy']);ax3[index,1].set(title=mode+' calibration vs science LF',xlim=(-350,350),ylim=(0,1.1),xlabel='Final IF [kHz]',ylabel='Relative LF power response');ax3[index,1].legend(fontsize=7)
 sensitivity={}
 for bridge in cfg['bridge_sensitivity_halfwidths_hz']:
  sb=model.sampled(mode,f,bridge=bridge);gb=ifft(sb)[:201];gb/=gb[0].real;sensitivity[str(int(bridge))]=dict(rms_ADC_V=float(np.sqrt(fs*np.mean(sb))),g1_real_0p4us=float(gb[2].real),upper_fit=fit_upper_envelope(lag*1e6,gb.real));ax5[index].plot(lag*1e6,gb.real,label=f'Bridge +/-{bridge/1e3:g} kHz')
 ax5[index].plot(lag*1e6,dg.real,color=COLORS['data'],label='Data');ax5[index].set(title=mode+' factorization sensitivity',xlim=(0,5),ylim=(-.08,.05),xlabel='Lag [us]');ax5[index].legend(fontsize=7)
 plateauS=plateau(sf,ss);pnoalias=float(np.mean(model.analog(mode,f))*fs);power=float(fs*np.mean(S));mu=float(np.mean(S));psd0=float(model.sampled(mode,np.array([0.]))[0])
 primary_cavity=model.phys[mode]['f0_hz']-cfg['primary_LO_hz'];final_cavity=primary_cavity-cfg['LF_primary_offset_hz'][mode]
 # Model amplitude predictions in ADC units; no rescaling to observed noise.
 report['modes'][mode]=dict(primary_cavity_IF_hz=primary_cavity,final_cavity_IF_hz=final_cavity,LF_notch_mapped_final_hz=-cfg['LF_primary_offset_hz'][mode],predicted_AC2_ADC_V2=power,predicted_RMS_ADC_V=float(np.sqrt(power)),data_first16SPEC_RMS_ADC_V=float(np.sqrt(data_power)),data_fullrun_RMS_ADC_V=float(np.sqrt(float(next(r for r in lt if int(r['run'])==680 and r['mode']==mode)['AC2_ADC_V2']))),alias_fraction=float((power-pnoalias)/power),center_PSD_over_plateau=float(psd0/plateauS),shape_metrics=shape,data_shape_metrics=data_shape,complex_g1_RMSE_0p2_10us=float(np.sqrt(np.mean(abs(theory[1:51]-dg[1:51])**2))),real_g1_min_0p2_10us=float(theory[1:51].real.min()),data_real_g1_min_0p2_10us=float(dg[1:51].real.min()),expected_upper_fit=fit_upper_envelope(lag*1e6,theory.real),data_upper_fit=fit_upper_envelope(lag*1e6,dg.real),integration_times_s=T.tolist(),mean_variance_ensemble_V2=vv.tolist(),mean_variance_finite_record_population_V2=vpopulation.tolist(),data_mean_variance_V2=vd.tolist(),variance_short_time_log_slope=float(np.polyfit(np.log(T[:3]),np.log(vpopulation[:3]),1)[0]),data_variance_short_time_log_slope=float(np.polyfit(np.log(T[:3]),np.log(vd[:3]),1)[0]),integration_max_relative_change_doubled_tail_cutoff=float(max(abs(np.array(convergence)))),bridge_sensitivity=sensitivity,MC=empirical,double_counting_control_center_over_plateau=float(wrong[0]/plateau(f,wrong)))
 # Numerical matched-filter curves for transition over a wider T range, not raw-derived PSD extrapolation.
 denseN=np.unique(np.round(fs*np.geomspace(2e-6,2.,100)).astype(int));denseT=denseN/fs
 denseV=np.array([mean_variance_from_psd(spectrum,int(size),fs) for size in denseN])
 arrays[mode+'_integration_time_s']=denseT;arrays[mode+'_mean_variance_V2']=denseV;arrays[mode+'_local_log_slope']=np.gradient(np.log(denseV),np.log(denseT))
 (O/'metrics.json').write_text(json.dumps(report,indent=2));print('Finished',mode,'RMS',np.sqrt(power),'slope',report['modes'][mode]['variance_short_time_log_slope'],flush=True)
for fg,name in [(fig,'PSD_and_complex_correlation'),(fig2,'mean_variance_vs_data'),(fig3,'absolute_PSD_and_response_planes'),(fig4,'MC_distributions'),(fig5,'calibration_factorization_sensitivity')]:
 for ax in fg.axes:ax.grid(alpha=.2)
 fg.tight_layout();fg.savefig(O/(name+'.png'),dpi=170);plt.close(fg)
arrays['frequency_hz']=np.fft.fftshift(f);arrays['lag_s']=lag
np.savez_compressed(O/'expected_predictions.npz',**arrays)
# Explicit floor crossover, and epsilon=0 control at fixed fc, no refit.
fig,axs=plt.subplots(1,2,figsize=(12,4.5));tt=np.geomspace(1e-6,2,400);tc=(1-cfg['epsilon'])/(2*np.pi*cfg['fc_hz']*cfg['epsilon'])
for eps,col in [(0.,'#777777'),(cfg['epsilon'],COLORS['toy'])]:
 vv=ideal_mean_variance(tt,1,cfg['fc_hz'],eps);axs[0].loglog(tt,vv,label=f'Ideal epsilon={eps:g}',color=col);axs[1].semilogx(tt,np.gradient(np.log(vv),np.log(tt)),label=f'Ideal epsilon={eps:g}',color=col)
for mode in model.phys:axs[1].semilogx(arrays[mode+'_integration_time_s'],arrays[mode+'_local_log_slope'],label=mode+' sampled full response',lw=.9)
for ax in axs:ax.axvline(tc,color=COLORS['fit'],ls=':',label=f'Ideal crossover {tc*1e3:.3f} ms');ax.grid(alpha=.2);ax.legend(fontsize=7);ax.set_xlabel('Integration time [s]')
axs[0].set_ylabel('Variance / ideal S0');axs[1].set(ylabel='Local log slope',ylim=(-2.2,-.7));fig.tight_layout();fig.savefig(O/'epsilon_crossover.png',dpi=180);plt.close(fig)
report.update(status='complete',wall_s=time.perf_counter()-start,ideal_crossover_s=tc,LPF_implementation='Measured final mixer/LPF response retained in kz envelope; no extra Butterworth applied. LF modeled at primary IF before final translation and alias sum.',calibration_factorization='TM010 original kz = envelope * sqrt(Fcal); fixed linear shoulder bridge +/-300kHz defines conditional envelope. Replace Fcal with Fdata, never multiply twice. TM011/012 retain measured envelope.',source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [SOURCE,SOURCE.with_name('model.py'),SOURCE.with_name('parameters.json'),Path(cfg['calibration_reconstruction']),Path(cfg['cavity_parameters']),DC/'interval_results.json',DC/'hardware.json']},limitations=['Initial fc/epsilon are indicative, not fitted; smoothed depth is not equal to exact F(0).','Calibration LF de-embedding is conditional; bridge sensitivity is model uncertainty, not a fit.','Stationary Gaussian PSD cannot distinguish shelf from suitably shaped independent-noise decomposition.','The exact two-source equality defines an equivalent downstream PSD proportional to the baseline spectrum; flat microscopic receiver noise is the receiver-dominated approximation.','Scalar mode mapping approximates secondary conversion and ignores vector image/IQ response and per-run slow drift.','Baseline magnitude does not measure phase of every stage. The LF shelf itself has a stable causal realization.','No full-run MC or new measured raw reconstruction; data reused from prior steps.'])
(O/'metrics.json').write_text(json.dumps(report,indent=2));print('COMPLETE',flush=True)
