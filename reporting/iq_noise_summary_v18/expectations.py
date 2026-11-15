"""Matched definitions for theoretical expectations and measured diagnostics."""
from pathlib import Path
import json,hashlib
import numpy as np
from scipy import constants
import h5py
import matplotlib.pyplot as plt
import slide_deck as sd

def update(deck,out,sim,h5,rows):
 A=out/'assets';D=out/'data'
 m4=json.loads((sim/'step4/FLASH_step04_thermal_model/metrics.json').read_text())
 m5=json.loads((sim/'step5/FLASH_step05_receiver_noise/metrics.json').read_text())
 p=m4['parameters'];fs=p['ADC_sample_rate_Hz'];gain=10**(p['ideal_gain_power_dB']/20)
 # Same 50-Hz frequency grid as the original 20-ms theoretical simulation.
 f=np.fft.fftfreq(round(p['analog_simulation_rate_Hz']*p['duration_s']),1/p['analog_simulation_rate_Hz']);df=1/p['duration_s']
 k_i=2*np.pi*p['f_res_Hz']/p['Q0'];k_e=p['coupling_beta']*k_i
 n=1/np.expm1(constants.h*p['f_res_Hz']/(constants.k*p['T_cavity_K']))
 lp=1/(1+(f/p['LPF_cutoff_Hz'])**(2*p['LPF_order']))
 S4=p['R_ohm']*gain**2*constants.h*p['f_res_Hz']*n*(abs(f-p['IF_Hz'])<=p['bath_bandwidth_Hz']/2)*k_i*k_e/(((k_i+k_e)/2)**2+(2*np.pi*(f-p['IF_Hz']))**2)*lp
 S5=S4+p['R_ohm']*gain**2*constants.k*m5['reference_thesis']['T_add_input_referred_K']*(abs(f)<=m5['numerical_setup']['B_electronics_Hz']/2)*lp
 lags=np.arange(51)/fs
 # IFFT computes the PSD integral for all ADC lags without a large outer product.
 stride=round(p['analog_simulation_rate_Hz']/fs)
 def moments(S):
  power=float(S.sum()*df);g=np.fft.ifft(S)[np.arange(51)*stride];g/=g[0]
  sigma=np.sqrt(power/2)
  return dict(sigma_adc_v=float(sigma),sigma_input_nv=float(sigma/gain*1e9),mean_amplitude_adc_v=float(sigma*np.sqrt(np.pi/2)),std_amplitude_adc_v=float(sigma*np.sqrt((4-np.pi)/2)),rms_adc_v=float(np.sqrt(power)),phase_pdf_per_rad=float(1/(2*np.pi)),phase_first_resultant=0.,g1_lag1_real=float(g[1].real),g1_lag1_abs=float(abs(g[1]))),g
 e4,g4=moments(S4);e5,g5=moments(S5)
 assert np.isclose(e4['rms_adc_v'],m4['expected_ADC_RMS_V_after_LPF'],rtol=1e-10)
 assert np.isclose(e5['rms_adc_v']**2,m5['noise_power']['total_expected'],rtol=1e-10)
 assert np.isclose(g4[1].real,m4['correlation_theory_lag1'][0],rtol=1e-10)
 def new(title,subtitle,source,notes=''):
  temp=sd.Deck();s=temp.new(title,subtitle,source,notes);s['footer']='EXPECTED vs MEASURED | DECK v18';return s
 # Keep page numbers 12 and 15: modify these pages in place, insert additions only later.
 for index,expect in ((10,e4),(11,e5)):
  original=deck.slides[index];image_path=next(i['path'] for i in original['items'] if i['kind']=='image')
  s=new(original['title'],'Theoretical expectations at ADC · same 140 dB numerical gain · no coherent tone','Source: original simulation PSD and metrics; theoretical values recomputed, not fitted to Run 680.')
  deck.image(s,.5,1.9,7.3,4.25,image_path)
  deck.text(s,8,1.9,4.8,.4,'Expected: thermal / + receiver',17,True)
  labels=[('σ [mV ADC]','sigma_adc_v',1e3),('mean(A) [mV ADC]','mean_amplitude_adc_v',1e3),('std(A) [mV ADC]','std_amplitude_adc_v',1e3),('RMS(A) [mV ADC]','rms_adc_v',1e3),('σ [nV nominal input]','sigma_input_nv',1),('p(φ) [rad⁻¹]','phase_pdf_per_rad',1),('|g₁(0.2 μs)|','g1_lag1_abs',1),('Re g₁(0.2 μs)','g1_lag1_real',1)]
  for j,(label,key,mult) in enumerate(labels):
   y=2.55+j*.37;deck.text(s,8,y,2.7,.35,label,12)
   deck.text(s,10.7,y,2.1,.35,f'{e4[key]*mult:.4g} / {e5[key]*mult:.4g}',12,True)
  deck.text(s,.75,6.3,11.9,.5,'Phase: uniform, |⟨exp(iφ)⟩| = 0. g₁ is normalized temporal IQ covariance; g₁(0) = 1.',14)
  s['notes']='Step 4 = thermal only; Step 5 = same cavity + receiver. Values integrate the original model PSD including out-of-Nyquist power before sampling. σ=RMS/√2. Input scaling divides by 10^(140/20); it is not a measured calibration.'
  deck.slides[index]=s
 s=new('Rayleigh fit: expected scale versus Run 680','Compare nominal input units; the model gain and measured-data normalization differ','Source: full-run v2 binned MLE; simulation PSD; data/expected_vs_measured.json.',notes='Simulation 100 mK and 140 dB numerical gain versus data nominal gain 143 dB. No gain fitting or rescaling to force agreement. Simulated cavity, receiver and LPF are illustrative; no absolute calibration inference.')
 heads=['Mode','Fit σ\n[mV ADC]','Fit σ\n[nV input]','Step 4 σ\n[nV input]','Step 5 σ\n[nV input]','Fit /\nStep 5','CDF gap']
 xs=[.65,2.15,3.95,5.75,7.55,9.5,11.25]
 for x,label in zip(xs,heads):deck.text(s,x,2,1.75,.65,label,14,True)
 with h5py.File(h5) as f:data_gain=float(f['dc_removed/calibration/configuration/total_db'][()])
 factor=10**(data_gain/20)
 for j,r in enumerate(rows):
  r['sigma_nominal_input_nv']=r['sigma_v']/factor*1e9;r['sigma_ratio_to_step5']=r['sigma_nominal_input_nv']/e5['sigma_input_nv']
  vals=[r['mode'],f"{r['sigma_v']*1e3:.3f}",f"{r['sigma_nominal_input_nv']:.3f}",f"{e4['sigma_input_nv']:.3f}",f"{e5['sigma_input_nv']:.3f}",f"{r['sigma_ratio_to_step5']:.4f}",f"{r['cdf_edge_max_distance']:.5f}"]
  for x,val in zip(xs,vals):deck.text(s,x,2.95+j*.55,1.75,.45,val,17)
 deck.text(s,.75,4.85,11.8,1.55,f'p(A) = A/σ² exp[−A²/(2σ²)], A ≥ 0; location = 0; RMS(A) = √2 σ.\nSimulation: 140 dB numerical gain, 100 mK; data: nominal {data_gain:g} dB normalization.\nThe assumed Step 5 noise scale is much larger than the fitted data scale. These inputs do not quantitatively describe Run 680. A Rayleigh shape alone does not identify the source.',18)
 deck.slides[14]=s
 # Phase comparison uses the full-run histogram; circular resultant is invariant to phase reference.
 phase_rows=[];fig,axs=plt.subplots(1,3,figsize=(13,3.2))
 with h5py.File(h5) as f:
  for ax,mode in zip(axs,('TM010','TM011','TM012')):
   g=f['modes/'+mode];counts=g['phase_counts'][:].astype(float);edges=g['phase_edges_rad'][:];centers=(edges[:-1]+edges[1:])/2;N=counts.sum();pdf=counts/N/np.diff(edges)
   resultant=float(abs(np.sum(counts*np.exp(1j*centers))/N));expected=N*np.diff(edges)/(2*np.pi)
   row=dict(mode=mode,n_nonzero=int(N),first_resultant_histogram_midpoint=resultant,expected_first_resultant=0.,expected_pdf_per_rad=1/(2*np.pi),max_bin_relative_deviation=float(np.max(abs(counts/expected-1))))
   phase_rows.append(row);ax.stairs(pdf,edges,color='#007F86');ax.axhline(1/(2*np.pi),color='#D98726',ls='--',label='Steps 4 / 5: 1/(2π)');ax.set(title=f'{mode}: |mean exp(iφ)| = {resultant:.4f}',xlabel='Wrapped phase [rad]',ylabel='Density [rad⁻¹]');ax.legend(fontsize=8)
   np.savez(D/f'{mode}_phase_comparison.npz',edges_rad=edges,counts=counts,expected_counts=expected)
 fig.tight_layout();phase_plot=A/'phase_expected_measured.png';fig.savefig(phase_plot,dpi=180);plt.close(fig)
 sphase=new('Phase: uniform expectation versus full-run data','Steps 4 and 5 predict the same marginal phase distribution','Source: full-run v2 phase histograms; data/expected_vs_measured.json.',notes='The HDF5 histogram uses wrapped relative phase. A constant phase reference rotates the circular mean but preserves its magnitude and a uniform null. Resultants are histogram-midpoint estimates. Exactly zero-amplitude samples excluded. No independent-sample KS or other p-value is inferred.')
 deck.image(sphase,.55,1.85,12.2,3.4,phase_plot)
 deck.text(sphase,.8,5.4,11.7,1.1,'Expected p(φ) = 1/(2π) = 0.15915 rad⁻¹; circular resultant = 0.\nA nearly uniform phase does not imply independent samples. Narrow angular features and temporal correlations must be examined separately.',19)
 # Temporal covariance: same archived five-SPEC window as the original analysis.
 period=Path('/home/mazzitel/HFGW/analysis-work/Run2/staging/legacy-repository/autoreco/noise_continuous/periodicity_run680/periodicity_diagnostic.npz')
 corrows=[];fig,axs=plt.subplots(1,2,figsize=(12.5,3.5))
 with np.load(period) as arr:
  t=arr['lag_s'][:51]*1e6
  for mode,color in zip(('TM010','TM011','TM012'),sd.COLORS):
   g=arr[mode+'_normalized_covariance'][:51];assert np.isclose(g[0],1)
   corrows.append(dict(mode=mode,lag1_real=float(g[1].real),lag1_abs=float(abs(g[1]))))
   axs[0].plot(t[1:],g.real[1:],color=color,lw=1,label=mode)
   axs[1].plot(t[1:],abs(g[1:]),color=color,lw=1,label=mode)
  for ax,part in zip(axs,(np.real,np.abs)):
   ax.plot(lags[1:]*1e6,part(g4[1:]),color='#43a1ed',ls='--',label='Step 4 expected')
   ax.plot(lags[1:]*1e6,part(g5[1:]),color='#ed812a',ls='--',label='Step 5 expected')
   ax.set_xlabel('Lag [μs]');ax.legend(fontsize=8);ax.grid(alpha=.2)
 axs[0].set_ylabel('Re g₁(τ)');axs[1].set_ylabel('|g₁(τ)|');fig.tight_layout();corplot=A/'correlation_expected_measured.png';fig.savefig(corplot,dpi=180);plt.close(fig)
 scorr=new('Temporal coherence: expectation versus measured IQ','Measured: first 5 SPEC of Run 680 (1.048576 s); theory: sampled model PSD','Source: archived continuous-stream covariance and original simulation PSD; data/expected_vs_measured.json.',notes='g1(τ)=E[(z(t+τ)−μ)(z(t)−μ)*]/E|z−μ|². Measured archive uses one mean across five continuous SPEC; pairs across boundaries included, normalization N−lag. Real part and magnitude do not change under conjugation of the IQ convention. This is temporal first-order coherence, not inter-mode spectral coherence. All traces have g1(0)=1, omitted from plot. No fit of a common coherence time.')
 deck.image(scorr,.55,1.8,12.2,3.6,corplot)
 vals='; '.join(f"{r['mode']}: {r['lag1_real']:+.4f} / {r['lag1_abs']:.4f}" for r in corrows)
 deck.text(scorr,.75,5.55,11.8,.95,f'At 0.2 μs, measured Re g₁ / |g₁|: {vals}.\nStep 5 predicts Re g₁ ≈ {e5["g1_lag1_real"]:.4f}, |g₁| ≈ {e5["g1_lag1_abs"]:.4f}. The assumed LPF / receiver model does not reproduce the measured short-lag correlation.',16)
 for i in range(len(deck.slides)-1,-1,-1):
  if deck.slides[i]['title']=='Run 680: phase distributions and time histories':deck.slides.insert(i,sphase)
  if deck.slides[i]['title']=='Does run 680 contain a repeating oscillation?':deck.slides.insert(i+1,scorr)
 for slide in deck.slides:
  if slide['title']=='Single-run conclusions and next steps':
   for item in slide['items']:
    if item['kind']=='text' and item['text'].startswith('Amplitude tails'):
     item['text']=sd.wrap('Rayleigh describes the global amplitude shape; the illustrative Step 5 scale and short-lag coherence do not match Run 680.',item['w'],16);item['size']=16
 payload=dict(definitions=dict(g1='E[(z(t+tau)-mu) conj(z(t)-mu)] / E|z-mu|²',phase='Wrapped phase; uniform null; histogram midpoint circular resultant',input_scaling='ADC volts / 10^(gain_dB/20), nominal only'),step4_expected=e4,step5_expected=e5,rayleigh_fits=rows,full_run_phase=phase_rows,five_SPEC_covariance=corrows,data_gain_db=data_gain,simulation_gain_db=p['ideal_gain_power_dB'],limitations='Different temperature, assumed transfer functions and nominal gain normalization; no absolute calibrated prediction for Run 680; no iid errors or p-values.')
 (D/'expected_vs_measured.json').write_text(json.dumps(payload,indent=2))
 np.savez(D/'expected_covariance.npz',lag_s=lags,g1_step4=g4,g1_step5=g5)
 prov=D/'v18_provenance.json';hashes=json.loads(prov.read_text());hashes[str(period)]=hashlib.sha256(period.read_bytes()).hexdigest();hashes[str(Path(__file__))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();prov.write_text(json.dumps(hashes,indent=2))
 print(json.dumps(payload,indent=2))
