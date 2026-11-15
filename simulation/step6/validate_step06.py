#!/usr/bin/env python3
"""Step 6: measured cavity/thermometry, conditional measured Tn, nominal ADC chain.

Retains Step 5 source architecture and exact TM010 seeds. Two external ports
contribute to damping; only the intrinsic wall bath is explicitly synthesized.
The receiver is lumped independent input-referred noise, not a noise-wave model.
Never fit gain or Tn to the observed run to hide a model/data discrepancy.
"""
import argparse,csv,hashlib,json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import h5py,numpy as np
from scipy import constants,signal,stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SOURCE=Path(__file__).resolve().parent
C={'cavity':'#43a1ed','receiver':'#ed812a','total':'#7049ac','expected':'#263952','data':'#007F86'}

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def run(out,temperature):
 cfg=json.loads((SOURCE/'parameters.json').read_text());cal=json.loads(Path(cfg['calibration']).read_text())
 out.mkdir(parents=True,exist_ok=True);assets=out/'assets';assets.mkdir(exist_ok=True)
 checks={}
 def check(name,ok,detail=''):
  checks[name]={'passed':bool(ok),'detail':detail}
  if not ok:raise AssertionError(name+': '+detail)
 with Path(cfg['temperature_table']).open() as stream:
  table=[r for r in csv.DictReader(stream) if int(r['run'])==680]
 check('temperature_covers_three_modes',len(table)==3)
 observed_temp=float(table[0]['t15_median_mk'])/1000
 check('temperature_is_shared_measurement',all(float(r['t15_median_mk'])/1000==observed_temp for r in table))
 temp=observed_temp if temperature=='run680' else .03
 with h5py.File(cfg['run680_h5']) as f:
  adc_peak=float(f['summary/input_range_v'][()]);measured_gain=float(f['dc_removed/calibration/configuration/total_db'][()])
  observed={mode:dict(ac_rms_adc_v=float(f[f'dc_removed/modes/{mode}/ac_rms_v'][()]),raw_rms_adc_v=float(f[f'dc_removed/modes/{mode}/total_rms_v'][()])) for mode in cfg['modes']}
 check('nominal_gain_matches_scientific_product',np.isclose(cal['total_db'],measured_gain))
 check('gain_stages_not_double_counted',np.isclose(sum(cal['stages_db'].values()),cal['total_db']) and not cal['frequency_response_applied'])
 fs=cfg['analog_fs_hz'];fsadc=cfg['adc_fs_hz'];dt=cfg['duration_s'];N=round(fs*dt);stride=round(fs/fsadc);df=fs/N
 check('integer_sampling_ratio',np.isclose(stride*fsadc,fs))
 f=np.fft.fftfreq(N,1/fs);t=np.arange(N//stride)/fsadc;lags=np.arange(51)/fsadc
 z,p,k=signal.butter(cfg['lpf_order_assumed'],2*np.pi*cfg['lpf_cutoff_hz'],analog=True,output='zpk')
 _,lpf=signal.freqs_zpk(z,p,k,worN=2*np.pi*f)
 support=abs(f)<=cfg['source_bandwidth_hz_assumed']/2
 bathsupport=abs(f-cfg['if_hz'])<=cfg['source_bandwidth_hz_assumed']/2
 resistance=cfg['resistance_ohm'];gain_adc=10**(cal['total_db']/20);gain_rf=10**(cfg['rf_gain_db']/20)
 adcstep=2*adc_peak/2**cfg['adc_bits']
 def quantize(a):return np.clip(np.round(a.real/adcstep)*adcstep,-adc_peak,adc_peak-adcstep)+1j*np.clip(np.round(a.imag/adcstep)*adcstep,-adc_peak,adc_peak-adcstep)
 def draw(seed):
  rng=np.random.default_rng(seed)
  return (rng.standard_normal(N)+1j*rng.standard_normal(N))/np.sqrt(2)
 def thermal_transfer(f0,q0,k1,k2,T):
  ki=2*np.pi*f0/q0;kt=ki*(1+k1+k2)
  H=np.sqrt(ki*(ki*k2))/(kt/2-1j*2*np.pi*(f-cfg['if_hz']))
  occupation=1/np.expm1(constants.h*f0/(constants.k*T))
  return H,constants.h*f0*occupation
 def covariance(a):
  a=a-a.mean();v=np.array([np.vdot(a[:len(a)-j],a[j:])/(len(a)-j) for j in range(len(lags))]);return v/v[0]
 def theory_corr(S):
  r=np.fft.ifft(S)[np.arange(len(lags))*stride];return r/r[0]
 def save(fig,name):
  fig.savefig(assets/(name+'.png'),dpi=180,bbox_inches='tight');fig.savefig(assets/(name+'.svg'),bbox_inches='tight');plt.close(fig)
 # Backward validation: exact Step 5 TM010 sources before changing parameters.
 H5,S5=thermal_transfer(8.8e9,50000,0,1,.1)
 xi0=draw(cfg['seed_cavity']);eta0=draw(cfg['seed_receiver'])
 oldc=np.fft.ifft(N*np.sqrt(resistance*1e14*S5*bathsupport*df)*xi0*H5*lpf)[::stride]
 olde=np.fft.ifft(N*np.sqrt(resistance*1e14*constants.k*cfg['receiver_tn_k']*support*df)*eta0*lpf)[::stride]
 with np.load(Path(cfg['step5'])/'step05_arrays.npz') as old:
  check('reproduces_step5_cavity_before_changes',np.allclose(oldc,old['z_cavity_preADC_V'],rtol=1e-11,atol=1e-13))
  check('reproduces_step5_receiver_before_changes',np.allclose(olde,old['z_electronics_preADC_V'],rtol=1e-11,atol=1e-13))
 rows={};arr={};npz=dict(t_s=t,lag_s=lags)
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.grid':True,'grid.alpha':.2})
 for index,(mode,mp) in enumerate(cfg['modes'].items()):
  H,Sp=thermal_transfer(mp['f0_hz'],mp['q0'],mp['kappa1'],mp['kappa2'],temp)
  xi=xi0 if index==0 else draw(cfg['seed_cavity']+100*index)
  eta=eta0 if index==0 else draw(cfg['seed_receiver']+100*index)
  Sc=resistance*Sp*bathsupport*abs(H)**2
  Se=resistance*constants.k*cfg['receiver_tn_k']*support
  Xc=N*np.sqrt(resistance*Sp*bathsupport*df)*xi*H
  Xe=N*np.sqrt(Se*df)*eta
  cav=np.fft.ifft(Xc*lpf)[::stride];ele=np.fft.ifft(Xe*lpf)[::stride];total=cav+ele
  rf_before_if_filter=np.fft.ifft((Xc+Xe)*gain_rf)[::stride]
  nominal_pre=total*gain_adc;adc=quantize(nominal_pre)
  # Input-referred samples are the primary stochastic observables; ADC is conditional.
  theory_c=Sc*abs(lpf)**2;theory_e=Se*abs(lpf)**2;theory=theory_c+theory_e
  pc=float(theory_c.sum()*df);pe=float(theory_e.sum()*df);power=pc+pe
  actual=float(np.mean(abs(total)**2));sigma=np.sqrt(power/2);gth=theory_corr(theory);g=covariance(total);gadc=covariance(adc)
  ql=mp['q0']/(1+mp['kappa1']+mp['kappa2']);width=mp['f0_hz']/ql;tau=1/(np.pi*width)
  alias=float(theory[abs(f)>=fsadc/2].sum()*df/power)
  below=float(abs(cfg['receiver_tn_uncertainty_k']/cfg['receiver_tn_k'])*pe/power/2)
  sample=total[::60];fit_sigma=float(np.sqrt(np.mean(abs(total)**2)/2));phase_resultant=float(abs(np.mean(np.exp(1j*np.angle(total)))))
  d_ray=float(stats.kstest(abs(sample),stats.rayleigh(scale=sigma).cdf).statistic)
  d_phase=float(stats.kstest((np.angle(sample)+np.pi)/(2*np.pi),'uniform').statistic)
  err=float(np.max(abs(g[:11]-gth[:11])))
  pseud=float(abs(np.mean((total-total.mean())**2))/np.var(total))
  check(mode+'_two_port_loaded_Q',ql<mp['q0'] and mp['kappa1']>0 and mp['kappa2']>0)
  check(mode+'_power_matches_PSD',abs(actual/power-1)<.03,f'relative error {actual/power-1:+.4%}')
  check(mode+'_thermal_power_matches_PSD',abs(np.mean(abs(cav)**2)/pc-1)<.08)
  check(mode+'_proper_IQ',pseud<.025)
  check(mode+'_circular_marginals',d_ray<.04 and d_phase<.04,f'Rayleigh D={d_ray:.4f}; uniform-phase D={d_phase:.4f}, thinned by 60; no p-values')
  check(mode+'_covariance_matches_inverse_PSD',err<.025,f'max first 10 lags error={err:.5f}')
  clipping=float(np.mean((abs(nominal_pre.real)>adc_peak-adcstep)|(abs(nominal_pre.imag)>adc_peak-adcstep)))
  check(mode+'_no_ADC_clipping',clipping==0)
  check(mode+'_ADC_error_half_LSB',max(np.max(abs((adc-nominal_pre).real)),np.max(abs((adc-nominal_pre).imag)))<=adcstep/2+1e-12)
  check(mode+'_ADC_grid',np.allclose(adc.real/adcstep,np.round(adc.real/adcstep)))
  rows[mode]=dict(**mp,temperature_k=temp,ql=ql,fwhm_hz=width,tau_amplitude_s=tau,
   effective_thermal_temperature_k=Sp/constants.k,cavity_input_power_v2=pc,receiver_input_power_v2=pe,cavity_fraction=pc/power,
   sigma_expected_input_v=float(sigma),sigma_fit_input_v=fit_sigma,mean_amplitude_expected_input_v=float(sigma*np.sqrt(np.pi/2)),std_amplitude_expected_input_v=float(sigma*np.sqrt((4-np.pi)/2)),rms_expected_input_v=float(np.sqrt(power)),
   rms_nominal_ADC_v=float(np.sqrt(power)*gain_adc),sigma_nominal_ADC_v=float(sigma*gain_adc),rf_output_rms_before_IF_filter_v=float(np.sqrt((Sc+Se).sum()*df)*gain_rf),
   rms_uncertainty_relative_from_Tn_only=below,full_calibration_uncertainty_available=False,
   phase_density_expected_per_rad=1/(2*np.pi),phase_resultant_expected=0.,phase_resultant_simulated=phase_resultant,
   correlation_expected_lag1=[float(gth[1].real),float(gth[1].imag)],correlation_simulated_lag1=[float(g[1].real),float(g[1].imag)],
   alias_power_fraction=alias,pseudocovariance_ratio=pseud,clipping_fraction=clipping,
   observed_run680=observed[mode],nominal_sim_to_measured_ac_rms_ratio=float(np.sqrt(power)*gain_adc/observed[mode]['ac_rms_adc_v']))
  fw,psd=signal.welch(total,fs=fsadc,nperseg=8192,noverlap=4096,return_onesided=False)
  # Explicitly fold the theoretical analog PSD onto the digitizer band.
  def psd_at(ff):
   ki=2*np.pi*mp['f0_hz']/mp['q0'];kt=ki*(1+mp['kappa1']+mp['kappa2'])
   h2=ki*ki*mp['kappa2']/((kt/2)**2+(2*np.pi*(ff-cfg['if_hz']))**2)
   return (resistance*Sp*(abs(ff-cfg['if_hz'])<=cfg['source_bandwidth_hz_assumed']/2)*h2+resistance*constants.k*cfg['receiver_tn_k']*(abs(ff)<=cfg['source_bandwidth_hz_assumed']/2))/(1+(ff/cfg['lpf_cutoff_hz'])**(2*cfg['lpf_order_assumed']))
  folded=sum(psd_at(fw+j*fsadc) for j in range(-3,4))
  arrays=dict(input_cavity_after_assumed_LPF_v=cav,input_receiver_after_assumed_LPF_v=ele,input_total_after_assumed_LPF_v=total,rf_output_before_IF_filter_v=rf_before_if_filter,nominal_adc_prequantization_v=nominal_pre,nominal_adc_quantized_v=adc,psd_frequency_hz=fw,psd_measured_input_v2_hz=psd,psd_folded_expected_input_v2_hz=folded,g1_expected=gth,g1_simulated=g,g1_nominal_adc=gadc)
  arr[mode]=arrays
  fig,axs=plt.subplots(2,3,figsize=(16,8.5));fig.suptitle(f'Step 6 — {mode}: measured cavity parameters; conditional receiver and nominal ADC',fontsize=15)
  offset=np.linspace(-2.5e6,2.5e6,1000);ki=2*np.pi*mp['f0_hz']/mp['q0'];kt=ki*(1+mp['kappa1']+mp['kappa2']);thermal=Sp/constants.k*ki**2*mp['kappa2']/((kt/2)**2+(2*np.pi*offset)**2)
  axs[0,0].plot(offset/1e6,thermal,color=C['cavity']);axs[0,0].set(xlabel='RF offset [MHz]',ylabel='Thermal PSD / kB [K]',title=f'Wall thermal emission only · T={temp*1e3:.3f} mK')
  order=np.argsort(fw);axs[0,1].plot(fw[order]/1e6,10*np.log10(psd[order]),color=C['total'],label='Simulated');axs[0,1].plot(fw[order]/1e6,10*np.log10(folded[order]),'--',color=C['expected'],label='Theory including aliases');axs[0,1].set(xlabel='Complex IF [MHz]',ylabel='Input-referred PSD [dBV²/Hz]',title='Total dominated by assumed receiver');axs[0,1].legend(fontsize=8)
  mask=(t>=.006)&(t<.006005);tt=(t[mask]-.006)*1e6
  axs[0,2].plot(tt,adc[mask].real,'o-',color=C['total'],label='I (filled)');axs[0,2].plot(tt,adc[mask].imag,'o--',mfc='white',color=C['total'],label='Qeff (hollow)');axs[0,2].set(xlabel='Time [μs]',ylabel='Nominal ADC voltage [V]',title=f'143 dB nominal chain · not fully calibrated');axs[0,2].legend(fontsize=8)
  axs[1,0].scatter(total.real[::10]*1e9,total.imag[::10]*1e9,s=2,alpha=.15,color=C['total']);axs[1,0].set(xlabel='I equivalent input [nV]',ylabel='Qeff equivalent input [nV]',title='Circular complex noise');axs[1,0].set_aspect('equal','box')
  bins=np.linspace(0,np.quantile(abs(total)*1e9,.9999),75);axs[1,1].hist(abs(total)*1e9,bins=bins,density=True,color=C['total'],alpha=.4);xx=np.linspace(0,bins[-1],250);axs[1,1].plot(xx,stats.rayleigh(scale=sigma*1e9).pdf(xx),color=C['expected']);axs[1,1].set(xlabel='Amplitude equivalent input [nV]',ylabel='Density [nV⁻¹]',title=f'Rayleigh: expected σ={sigma*1e9:.2f} nV')
  axs[1,2].hist(np.angle(sample),bins=45,density=True,color=C['total'],alpha=.4);axs[1,2].axhline(1/(2*np.pi),color=C['expected'],ls='--');axs[1,2].set(xlabel='Phase [rad]',ylabel='Density [rad⁻¹]',title='Uniform phase expectation')
  fig.text(.04,.012,'No coherent tone. Qeff = imaginary part of z = −Qhardware under I−iQ convention. ADC and IQ balance remain nominal/ideal.',fontsize=9)
  fig.tight_layout(rect=(0,.04,1,.95));save(fig,f'step06_{mode}_observables')
 # Shared phase/covariance predictions and model/data amplitude discrepancy.
 fig,axs=plt.subplots(1,3,figsize=(16,4.8))
 for mode,col in zip(rows,['#007F86','#7657A6','#D98726']):
  axs[0].plot(lags[1:]*1e6,abs(arr[mode]['g1_expected'][1:]),'--',color=col,label=mode+' theory');axs[0].plot(lags[1:]*1e6,abs(arr[mode]['g1_simulated'][1:]),'.',ms=3,color=col)
  axs[1].plot(lags[1:]*1e6,arr[mode]['g1_expected'][1:].real,'--',color=col,label=mode+' theory');axs[1].plot(lags[1:]*1e6,arr[mode]['g1_simulated'][1:].real,'.',ms=3,color=col)
 axs[0].set(xlabel='Lag [μs]',ylabel='|g₁|',title='Temporal first-order coherence');axs[1].set(xlabel='Lag [μs]',ylabel='Re g₁',title='Normalized centered covariance')
 for ax in axs[:2]:ax.legend(fontsize=8)
 names=list(rows);x=np.arange(len(names));axs[2].bar(x-.18,[rows[k]['rms_nominal_ADC_v'] for k in names],.36,color=C['total'],label='Step 6 nominal ADC');axs[2].bar(x+.18,[observed[k]['ac_rms_adc_v'] for k in names],.36,color=C['data'],label='Run 680 AC RMS');axs[2].set(xticks=x,xticklabels=names,ylabel='Complex RMS [V]',title='Unfitted model–data comparison');axs[2].legend(fontsize=8)
 fig.suptitle('Step 6: predicted phase/coherence and nominal amplitude scale',fontsize=15);fig.tight_layout();save(fig,'step06_coherence_and_data_comparison')
 # Step 5 -> Step 6: show measured parameter replacements and surviving assumptions.
 fig,axs=plt.subplots(1,2,figsize=(15,5.8),gridspec_kw={'width_ratios':[1.35,1]})
 axs[0].axis('off')
 cells=[['f0 [GHz]','8.800',*[f'{r["f0_hz"]/1e9:.6f}' for r in rows.values()]],
        ['Q0','50,000',*[f'{r["q0"]:,.0f}' for r in rows.values()]],
        ['kappa1 / kappa2','0 / 1',*[f'{r["kappa1"]:.4g} / {r["kappa2"]:.3g}' for r in rows.values()]],
        ['QL','25,000',*[f'{r["ql"]:,.0f}' for r in rows.values()]],
        ['T cavity [mK]','100',*[f'{temp*1e3:.3f}' for r in rows.values()]],
        ['Tn [K]','3.955',*['3.955 (conditional)']*3],
        ['ADC gain [dB]','140 arbitrary',*['143 nominal']*3]]
 tableplot=axs[0].table(cellText=cells,colLabels=['Parameter','Step 5','Step 6 TM010','Step 6 TM011','Step 6 TM012'],loc='center',cellLoc='center',colWidths=[.20,.18,.21,.21,.21]);tableplot.auto_set_font_size(False);tableplot.set_fontsize(8);tableplot.scale(1,2.1)
 with np.load(Path(cfg['step5'])/'step05_arrays.npz') as previous:
  lag5=previous['lags_s'];corr5=previous['corr_theory_total']
 axs[1].plot(lag5[1:]*1e6,abs(corr5[1:]),'k--',lw=2,label='Step 5 expected')
 for mode,col in zip(rows,['#007F86','#7657A6','#D98726']):axs[1].plot(lags[1:]*1e6,abs(arr[mode]['g1_expected'][1:]),color=col,label='Step 6 '+mode)
 axs[1].set(xlabel='Lag [μs]',ylabel='|g₁|',title='Receiver assumption still dominates correlation');axs[1].legend(fontsize=8)
 fig.suptitle('Step 5 → Step 6: measured cavity and temperature, explicit calibration limits',fontsize=14)
 fig.text(.04,.025,'RF gain 103.4 dB is a separate reference plane. Numerical kz(f) is missing: the full ADC prediction remains nominal.',fontsize=10)
 fig.tight_layout(rect=(0,.065,1,.94));save(fig,'step06_step5_transition')
 # Quantitative step transition, no hidden rescaling.
 report=dict(schema='flash-step06-results-v1',built_rome=datetime.now(ZoneInfo('Europe/Rome')).isoformat(),status='measured-cavity-and-thermometry; conditional-Tn; nominal-ADC',temperature_source=temperature,temperature_k=temp,run680_observed_temperature_k=observed_temp,temperature_sensor='AVS T15',observations=int(table[0]['t15_observations']),nominal_ADC_gain_db=cal['total_db'],thesis_RF_gain_db=cfg['rf_gain_db'],adc_peak_v=adc_peak,adc_bits=cfg['adc_bits'],ADC_lsb_v=adcstep,mode_results=rows,checks=checks,tests_passed=sum(x['passed'] for x in checks.values()),tests_total=len(checks),all_passed=all(x['passed'] for x in checks.values()),
  conventions=dict(voltage='Analytic complex matched-load voltage: E|z|²/R = integrated available PSD, as Step 5; kz must use the same RMS convention.',iq='z=I+iQeff with Qeff=-Qhardware for the I-iQ convention; complex conjugation reverses frequency and imaginary covariance signs.',thermal='Intrinsic wall thermal emission through output port 2; port 1 adds damping; incident-port noise and correlations not modeled.',gain='RF gain 103.4 dB and nominal full ADC gain 143 dB are alternative reference planes, never cascaded.'),
  missing_calibration=['Numerical per-mode kz(f) curves and their uncertainties','Run-matched receiver Tn and full-chain gain uncertainty','Measured LPF response and IQ imbalance/offset','Independently confirmed ADC range and voltage/impedance convention'],
  limitations=['Thesis cavity fit and no-TWPA Tn are not proven simultaneous with run 680.','One Tn value is applied to all modes conditionally; no noise-wave, reflected input-noise or full quantum receiver model.','Measured T15 physical temperature does not independently calibrate mode thermal occupation.','Do not interpret nominal ADC disagreement as a measured gain or receiver-noise correction.','Source bandwidth 10 MHz, ideal I/Q and fourth-order LPF shape remain assumptions.','No extra vacuum term is added to effective receiver Tn; potential double counting avoided.'])
 paths=[SOURCE/'parameters.json',Path(__file__),Path(cfg['thesis']),Path(cfg['calibration']),Path(cfg['temperature_table']),Path(cfg['run680_h5']),Path(cfg['step5'])/'validate_step05.py',Path(cfg['step5'])/'metrics.json',Path(cfg['step5'])/'step05_arrays.npz']
 report['input_sha256']={str(p):sha(p) for p in paths}
 (out/'metrics.json').write_text(json.dumps(report,indent=2))
 with h5py.File(out/'step06_simulation.h5','w') as h:
  h.attrs['schema']='flash-step06-v1';h.attrs['calibration_status']=report['status'];h.attrs['metadata_json']=json.dumps(report)
  h.create_dataset('time_s',data=t);h.create_dataset('lag_s',data=lags)
  for mode,arrays in arr.items():
   g=h.create_group(mode)
   for key,a in arrays.items():g.create_dataset(key,data=a,compression='gzip',shuffle=True)
  g=h.create_group('step5_reference_TM010');g.create_dataset('cavity_preADC_v',data=oldc,compression='gzip');g.create_dataset('receiver_preADC_v',data=olde,compression='gzip')
 with (out/'expected_parameters.csv').open('w') as stream:
  keys=['f0_hz','q0','kappa1','kappa2','temperature_k','ql','fwhm_hz','tau_amplitude_s','effective_thermal_temperature_k','cavity_fraction','sigma_expected_input_v','sigma_fit_input_v','rms_expected_input_v','rms_nominal_ADC_v','nominal_sim_to_measured_ac_rms_ratio']
  writer=csv.DictWriter(stream,fieldnames=['mode']+keys);writer.writeheader()
  for mode,r in rows.items():writer.writerow(dict(mode=mode,**{k:r[k] for k in keys}))
 (out/'README.md').write_text('# Step 6: measured cavity parameters, conditional receiver, nominal ADC\n\nSource: '+str(SOURCE)+'\n\nTemperature scenario: '+temperature+'; '+f'{temp*1e3:.6f} mK.\n\nThe Step 5 architecture and TM010 random seeds are preserved and backward-validated sample by sample before changing parameters. All three measured cavity modes are modeled with both external-port damping rates. Receiver Tn=3.955±0.468 K is conditional on the thesis no-TWPA setup. RF gain 103.4 dB and nominal total gain 143 dB refer to different planes, never cascaded.\n\nThe ADC prediction is NOT fully calibrated: numerical kz(f), measured transfer functions and run-matched noise calibration are missing. No gain or noise parameter is fitted to force agreement with Run 680. Thermal emission alone and receiver noise are saved separately.\n\nOutputs: step06_simulation.h5 (arrays, expected/empirical covariance and folded spectra), metrics.json (checks, provenance, limitations), expected_parameters.csv, assets/ figures.\n')
 print('Output:',out);print('Checks:',report['tests_passed'],'/',report['tests_total']);print('Temperature:',temp*1000,'mK')
 for mode,r in rows.items():print(mode,'QL=',r['ql'],'FWHM kHz=',r['fwhm_hz']/1e3,'sigma input nV=',r['sigma_expected_input_v']*1e9,'nominal ADC RMS=',r['rms_nominal_ADC_v'],'model/data=',r['nominal_sim_to_measured_ac_rms_ratio'])
 return report

if __name__=='__main__':
 cfg=json.loads((SOURCE/'parameters.json').read_text());parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--out',type=Path,default=Path(cfg['default_output']))
 parser.add_argument('--temperature',choices=['run680','thesis30mK'],default='run680')
 args=parser.parse_args();run(args.out,args.temperature)
