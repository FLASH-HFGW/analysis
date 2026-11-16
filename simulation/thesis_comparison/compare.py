"""Compare thesis residual estimator and explicit ADC/gain scenarios without gain fitting."""
from pathlib import Path
import json,hashlib,sys,copy,subprocess
import numpy as np
from scipy import constants,signal,stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
ROOT=Path('/home/mazzitel/HFGW');OUT=ROOT/'analysis-work/Run2/simulation/thesis_comparison';OUT.mkdir(parents=True,exist_ok=True)
m=json.loads((ROOT/'analysis-work/Run2/simulation/toy_measured_response/metrics.json').read_text())
# Same residual estimator, analytical averaged-periodogram sampling. Independent rectangular FFT bins.
# No measured thesis smooth background is imported or fitted.
fs=5e6;nfft=16384;df=fs/nfft;M=259*1000*64;dt=M*nfft/fs;T=3.985
f=np.arange(-488,489)*df;power=constants.k*T*df;sig=power/np.sqrt(M)
rng=np.random.default_rng(20261115);P=rng.gamma(M,power/M,len(f));bg=signal.savgol_filter(P,201,4);res=(P-bg)/sig
mu,sd=stats.norm.fit(res);chi=float(np.mean(res**2));coeff=signal.savgol_coeffs(201,4);expected=np.sqrt(1-2*coeff[100]+sum(coeff**2))
# Fixed seed ensemble quantifies variation/correlation of the estimator, not a fitted correction.
ens=[]
for _ in range(500):
 p=rng.gamma(M,power/M,len(f));r=(p-signal.savgol_filter(p,201,4))/sig;ens.append([r.mean(),r.std(),np.mean(r*r)])
np.savez(OUT/'residual_samples.npz',frequency_offset_hz=f,power_w_bin=P,background_w_bin=bg,residual=res,ensemble=np.array(ens))
fig,ax=plt.subplots(figsize=(7,4));ax.hist(res,bins=np.linspace(-3.5,3.5,36),density=True,color='#007F86',alpha=.55,label=f'Simulation: μ={mu:.3f}, σ={sd:.3f}')
x=np.linspace(-3.5,3.5,500);ax.plot(x,stats.norm.pdf(x,mu,sd),color='#007F86');ax.plot(x,stats.norm.pdf(x,-.005,.967),'--',color='#D98726',label='Thesis Fig.6.7 fit: μ=−0.005, σ=0.967')
ax.set(xlabel='(Power − Savitzky–Golay background) / σDicke',ylabel='Density',title='Same residual estimator; independent simulated population');ax.legend(fontsize=9);fig.tight_layout();fig.savefig(OUT/'residual_comparison.png',dpi=180);plt.close(fig)
rows=[]
for mode,v in m['results'].items():
 obs=v['observed_ac_rms_adc_v'];pred=v['rms_if_RF103_4_v'];rows.append(dict(mode=mode,observed_confirmed_2V_rms_v=obs,predicted_103p4_rms_v=pred,predicted_67p4_rms_v=v['rms_adc_v'],ratio_103p4_correct_ADC=pred/obs,ratio_103p4_counterfactual_5V_reinterpretation=pred/(obs*2.5),ratio_67p4_correct_ADC=v['rms_adc_v']/obs))
fig,axs=plt.subplots(1,3,figsize=(12,3.6))
for ax,r in zip(axs,rows):
 vals=[r['observed_confirmed_2V_rms_v'],r['predicted_67p4_rms_v'],r['predicted_103p4_rms_v']];ax.bar(['Data\n±2 V','Model\n67.4 dB','Model\n103.4 dB'],vals,color=['#24364B','#007F86','#D98726']);ax.set_yscale('log');ax.set(title=r['mode'],ylabel='Analog/ADC-input AC RMS [V]');ax.grid(axis='y',alpha=.2)
fig.tight_layout();fig.savefig(OUT/'absolute_normalization.png',dpi=180);plt.close(fig)
# Crop only the published figure from the rendered PDF page; retain source page too.
subprocess.run(['pdftoppm','-f','119','-l','119','-scale-to','1500','-png','-singlefile',str(ROOT/'analysis-work/Run2/reports/Tesi_Valeria_Spasiano.pdf'),str(OUT/'thesis_pdf119')],check=True)
im=Image.open(OUT/'thesis_pdf119.png');im.crop((170,165,895,565)).save(OUT/'thesis_fig6p7.png')
report=dict(residual_test=dict(thesis_figure='6.7, printed p114 / PDF119',thesis_mu=-.005,thesis_mu_error=.031,thesis_sigma=.967,thesis_sigma_error=.022,thesis_mean_square=.9347,simulation_mu=float(mu),simulation_sigma=float(sd),simulation_mean_square=chi,SG_interior_expected_sigma=float(expected),ensemble_sigma_95pct=np.percentile(np.array(ens)[:,1],[2.5,97.5]).tolist(),fft_samples=nfft,df_hz=df,averages=M,integration_s=dt,T_total_K=T,SG_window=201,SG_order=4,limitations='Statistical estimator check with flat kBT continuum and independent rectangular FFT bins, not full analog-chain simulation or reproduction of measured smooth spectrum. Thesis Ttot is an input, not an independently predicted normalization. Hann bin correlations are not modeled. No coherent tone in this noise test.'),normalization_scenarios=rows,conclusions=['Removing36dB hypothesis means retain103.4dB; predicted amplitude grows by10^(36/20)=63.096.','Reinterpreting identical ADC counts at5V instead of2V increases data voltage by2.5, not63.096. Counterfactual only: run680 actual ODB is2V.','Changing physical ADC range with correct volts/count does not rescale unclipped analog voltage, only quantization/clipping.','No actual5V thesis noise run with matched science data has been identified; tone sweep5V is calibration, not thermal-noise validation.','Shape agreement in dimensionless residuals cannot validate absolute gain.'],source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'analysis-work/Run2/reports/Tesi_Valeria_Spasiano.pdf']})
(OUT/'comparison.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
