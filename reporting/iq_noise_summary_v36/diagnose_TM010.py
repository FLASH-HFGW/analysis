from pathlib import Path
import numpy as np,json
R=Path('/home/mazzitel/HFGW/analysis-work/Run2');O=R/'diagnostics/toy_TM010_notch_20261115';O.mkdir(parents=True,exist_ok=True)
c=json.load(open(R/'diagnostics/normalization_audit_20261114/calibration_reconstruction.json'));p=json.load(open(R/'simulation/step6/metrics.json'))['mode_results']['TM010'];mode='TM010';N=2**20;fs=5e6;f=np.fft.fftfreq(N,1/fs);off=c['comparison'][mode]['rf_if_offset_hz'];pts=c['curves'][mode];xx=np.array([r['rf_hz']-off for r in pts]);kk=np.array([r['kz_integrated'] for r in pts]);order=np.argsort(xx);xx=xx[order];kk=kk[order]
# Sensitivity only: replace central response by interpolation between measured shoulders.
shoulders=abs(xx)>=.5e6;flat=kk.copy();flat[~shoulders]=np.interp(xx[~shoulders],xx[shoulders],kk[shoulders]);spectra=[];gs=[]
for curve in (kk,flat):
 S=np.zeros(N)
 for alias in (-1,0,1):
  af=f+alias*fs;resp=np.interp(af,xx,curve,left=0,right=0);ki=2*np.pi*p['f0_hz']/p['q0'];kt=ki*(1+p['kappa1']+p['kappa2']);th=6.62607015e-34*p['f0_hz']/np.expm1(6.62607015e-34*p['f0_hz']/(1.380649e-23*p['temperature_k']))
  S+=50*10**(67.4/10)*(1.380649e-23*3.955+th*ki**2*p['kappa2']/((kt/2)**2+(2*np.pi*(af-1e6))**2))*resp**2
 g=np.fft.ifft(S)[:201];g/=g[0];gs.append(g);spectra.append(S)
np.savez_compressed(O/'response_sensitivity.npz',IF_hz=xx,kz_measured=kk,kz_notch_filled=flat,lag_us=np.arange(201)/5,original_expected_g1=gs[0],notch_filled_expected_g1=gs[1])
result=dict(scope='Diagnostic expected covariance only; no change to active toy or measured run680 analysis',response='Measured kz_integrated TM010, squared in toy PSD',central_kz=float(np.interp(0,xx,kk)),shoulder_kz=float(np.interp(0,xx,flat)),relative_central_power=float((np.interp(0,xx,kk)/np.interp(0,xx,flat))**2),original_Re_lag_0p2=float(gs[0][1].real),original_Re_lag_0p4=float(gs[0][2].real),notch_filled_Re_lag_0p2=float(gs[1][1].real),notch_filled_Re_lag_0p4=float(gs[1][2].real),interpretation='A central PSD deficit adds a negative short-lag component to the covariance; zero mean does not imply positive-lag covariance oscillates symmetrically about zero. g1(0)=1, omitted in the zoom.',limitation='Measured coherent-tone response and input-referred receiver-noise placement may not reproduce the observed noise PSD. This test identifies the mechanism in the toy, not the physical origin of the calibration notch.')
(O/'diagnosis.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
