"""Part I v43: reused source realizations, explicit transfer and sampled correlations."""
from pathlib import Path
import copy,hashlib,json,sys,shutil
import numpy as np,h5py
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0,'/tmp/v18-python-deps')
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO/'reporting'));import slide_deck as sd
WORK=REPO.parent/'analysis-work/Run2';SIM=WORK/'simulation/presentation_steps1_6_v43';OUT=WORK/'reports/iq_noise_summary_v43_partI';A=OUT/'assets';A.mkdir(parents=True,exist_ok=True)
m=json.loads((SIM/'metrics.json').read_text());assert m['all_checks_passed'];cfg=m['configuration'];fs=cfg['fs_hz'];N=cfg['samples_per_example'];h=h5py.File(SIM/'short_examples.h5','r');t=h['time_s'][:];lags=np.arange(51)/fs*1e6
C={'cavity':'#43a1ed','injected':'#43a1ed','receiver':'#ed812a','tone':'#263952','total':'#7657A6','theory':'#263952'}
MC=sd.COLORS;MODES=['TM010','TM011','TM012'];zoom_checks={}
plt.rcParams.update({'font.size':9,'axes.titlesize':10,'axes.labelsize':9,'xtick.labelsize':7.5,'ytick.labelsize':7.5,'legend.fontsize':6.5,'axes.grid':True,'grid.alpha':.18,'lines.linewidth':.9})
def save(fig,name):
 p=A/(name+'.png');fig.savefig(p,dpi=230,facecolor='white');fig.savefig(p.with_suffix('.pdf'));plt.close(fig);return p

def curve(ax,x,y,col,label,imag=False,ms=2.6):
 ax.plot(x,y,color=col,marker='s' if imag else 'o',markersize=ms,markerfacecolor='white' if imag else col,linestyle='--' if imag else '-',linewidth=.8,label=label)

def corr(ax,g,key,color,zoom=False):
 g=g[:51];idx=slice(1,None) if zoom else slice(None)
 curve(ax,lags[idx],g.real[idx],color,'Re(g1)')
 curve(ax,lags[idx],g.imag[idx],color,'Im(g1)',True)
 lo,hi=(-.08,.08) if zoom else (-1.05,1.05)
 if zoom:
  actual=max(abs(g[1:].real).max(),abs(g[1:].imag).max());lim=max(.08,float(actual)*1.12);lo,hi=-lim,lim
  zoom_checks[key]={'max_abs_positive_lag':float(actual),'limits':[lo,hi],'no_clipping':bool(actual<hi),'sample_spacing_ns':1e9/fs}
 ax.set(xlim=(.15 if zoom else 0,10),ylim=(lo,hi),ylabel='g1',xlabel='Lag [us]')
 ax.axhline(0,color='#888888',lw=.5)
 ax.legend(loc='upper right',ncol=2,fontsize=6)

def gallery(key,name,mode=None):
 g=h[key];z=g['analog_ADC_V'][:];q=g['quantized_ADC_V'][:];rms=np.sqrt(g.attrs['expected_total_power_V2']);col=MC[MODES.index(mode)] if mode else C['total']
 fig=plt.figure(figsize=(13.2,5.2));gs=fig.add_gridspec(2,3,left=.06,right=.988,bottom=.1,top=.93,hspace=.63,wspace=.34)
 axs=[fig.add_subplot(gs[i,j]) for i,j in [(0,0),(0,1),(0,2),(1,0),(1,1)]]
 ax=axs[0]
 for vals,imag in [(z.real,False),(z.imag,True)]:ax.plot(t[:24]*1e6,vals[:24]*1e3,color=col,alpha=.4,ls='--' if imag else '-')
 ax.plot(t[:24]*1e6,q.real[:24]*1e3,'o',color=col,ms=3,label='I: filled ADC')
 ax.plot(t[:24]*1e6,q.imag[:24]*1e3,'s',mfc='white',mec=col,ms=3,label='Qeff: open ADC')
 ax.set(title='Sampled I / Qeff',xlabel='Time [us]',ylabel='Voltage [mV ADC]',xlim=(0,4.6),ylim=(-140,140));ax.legend(loc='lower left')
 ax=axs[1];ax.scatter(q.real[:1200]*1e3,q.imag[:1200]*1e3,color=col,s=4,alpha=.25);ax.set(title='IQ constellation',xlabel='I [mV ADC]',ylabel='Qeff [mV ADC]',xlim=(-140,140),ylim=(-140,140));ax.set_aspect('equal',adjustable='box')
 ax=axs[2];edges=np.linspace(0,5,101)
 for vals,color,label,ls in [(q,col,'ADC','-'),(z,C['theory'],'Analog','--')]:
  c=np.histogram(abs(vals)/rms,edges)[0];ax.stairs(np.maximum(c/(len(vals)*np.diff(edges)),1e-7),edges,color=color,ls=ls,label=label)
 if key not in ['step1','step2']:
  xx=np.linspace(.001,5,350);ax.plot(xx,2*xx*np.exp(-xx*xx),':',color=C['theory'],label='Rayleigh')
 ax.set(title='Amplitude distribution',xlabel='A / predicted analog RMS',ylabel='Density',xlim=(0,5),ylim=(1e-3,60),yscale='log');ax.legend()
 ax=axs[3];edges=np.linspace(-np.pi,np.pi,65)
 for vals,color,ls,label in [(q,col,'-','ADC: nonzero only'),(z,C['theory'],'--','Analog')]:
  nz=abs(vals)>0;c=np.histogram(np.angle(vals[nz]),edges)[0];ax.stairs(np.maximum(c/(c.sum()*np.diff(edges)),1e-7),edges,color=color,ls=ls,label=label)
 if key not in ['step1','step2']:ax.axhline(1/(2*np.pi),color=C['theory'],ls=':',lw=.7)
 ax.set(title='Phase distribution',xlabel='arg(I + i Qeff) [rad]',ylabel='Density [rad^-1]',xlim=(-np.pi,np.pi),ylim=(1e-3,5),yscale='log',xticks=[-np.pi,0,np.pi],xticklabels=['-pi','0','pi']);ax.legend()
 ax=axs[4]
 for comp in g['components']:
  f,p=signal.welch(g['components'][comp][:],fs,window=np.hanning(16384),nperseg=16384,noverlap=0,return_onesided=False,detrend=False);ix=np.argsort(f)
  ax.plot(f[ix]/1e6,10*np.log10(np.maximum(p[ix],1e-30)),color=C[comp],lw=.65,label={'cavity':'Cavity thermal','receiver':'Electronic','injected':'Injected test noise','tone':'Coherent tone'}[comp])
 f,p=signal.welch(q,fs,window=np.hanning(16384),nperseg=16384,noverlap=0,return_onesided=False,detrend=False);ix=np.argsort(f)
 ax.plot(f[ix]/1e6,10*np.log10(np.maximum(p[ix],1e-30)),color=col,lw=.8,label='Total ADC')
 ax.set(title='Power spectral density',xlabel='Final IF [MHz]',ylabel='PSD [dB V^2/Hz]',xlim=(-2.5,2.5),ylim=(-190,-30));ax.legend(loc='lower left')
 if key in ['step3','step5'] or key.startswith('step6'):
  sub=gs[1,2].subgridspec(2,1,hspace=.68);ax0=fig.add_subplot(sub[0]);ax1=fig.add_subplot(sub[1]);corr(ax0,g['ADC_g1'][:],key+'_full',col);corr(ax1,g['ADC_g1'][:],key,col,True)
  ax0.set_title('Complex autocorrelation: common scale',fontsize=9);ax0.set_xlabel('');ax1.set_title('Positive-lag zoom; ADC markers every 0.2 us',fontsize=8)
 else:
  ax0=fig.add_subplot(gs[1,2]);corr(ax0,g['ADC_g1'][:],key,col);ax0.set_title('Complex autocorrelation')
  ax0.plot(lags,g['analog_g1'][:51].real,color=C['theory'],ls=':',alpha=.6,label='Analog Re')
 if key in ['step2','step4']:
  thermal=key=='step4';factor=1e6 if thermal else 1e3;lim=85 if thermal else 8;unit='uV' if thermal else 'mV'
  ax=axs[0].inset_axes([.5,.58,.48,.37]);ax.plot(t[:24]*1e6,z.real[:24]*factor,color=C['cavity'],lw=.7);ax.plot(t[:24]*1e6,q.real[:24]*factor,'o',color=col,ms=2);ax.set(ylim=(-lim,lim),title='Physical zoom ['+unit+']');ax.tick_params(labelsize=5);ax.title.set_fontsize(6)
  ax=axs[1].inset_axes([.5,.57,.48,.4]);ax.scatter(z.real[:800]*factor,z.imag[:800]*factor,color=C['cavity'],s=2,alpha=.2);ax.scatter(q.real[:800]*factor,q.imag[:800]*factor,color=col,s=3,alpha=.35);ax.set(xlim=(-lim,lim),ylim=(-lim,lim),title='Zoom ['+unit+']');ax.tick_params(labelsize=5);ax.title.set_fontsize(6)
 return save(fig,name)

figs={key:gallery(key,key) for key in ['step1','step2','step3','step4','step5']}
for mode in MODES:figs['step6_'+mode]=gallery('step6_'+mode,'step6_'+mode,mode)
# Explicit transfer functions, calculated from the unchanged physical parameters.
fig,axs=plt.subplots(1,2,figsize=(12.4,2.2));p=m['metrics']['TM010'];ki=2*np.pi*p['f0_hz']/p['q0'];k1=ki*p['kappa1'];k2=ki*p['kappa2'];kt=ki+k1+k2;d=np.linspace(-.5e6,.5e6,700)
axs[0].plot(d/1e3,abs(np.sqrt(k1*k2)/(kt/2+2j*np.pi*d))**2,color=C['tone'],label='Port 1 → 2: |H12|²')
axs[0].plot(d/1e3,abs(np.sqrt(ki*k2)/(kt/2+2j*np.pi*d))**2,color=C['cavity'],label='Wall bath → port 2: |Hb|²');axs[0].set(xlabel='Detuning from cavity [kHz]',ylabel='Power transfer',yscale='log',ylim=(1e-6,2));axs[0].legend()
cal=json.loads(Path(cfg['calibration_reconstruction']).read_text())
for i,mode in enumerate(MODES):
 pts=cal['curves'][mode];off=cal['comparison'][mode]['rf_if_offset_hz'];x=np.array([v['rf_hz']-off for v in pts]);k=np.array([v['kz_integrated'] for v in pts]);ix=np.argsort(x);axs[1].plot(x[ix]/1e6,k[ix]*.01,color=MC[i],label=mode)
axs[1].set(xlabel='Final IF [MHz]',ylabel='kz,science = 0.01 kz,cal',xlim=(-2.5,2.5));axs[1].legend();fig.tight_layout();transferfig=save(fig,'unchanged_cavity_and_readout_response')
# Source autocorrelations and the exact analog residual, without display gains.
fig,axs=plt.subplots(2,2,figsize=(12.6,4.9));fig.subplots_adjust(left=.075,right=.985,top=.92,bottom=.12,hspace=.65,wspace=.35)
diag=h['diagnostics'];cr=diag['receiver_covariance'][:51];ct=diag['thermal_covariance'][:51];cs=diag['total_covariance'][:51];weighted=diag['power_weighted_g1'][:51]
for cov,color,name in [(cr,C['receiver'],'Electronic'),(ct,C['cavity'],'Thermal')]:curve(axs[0,0],lags,(cov/cov[0].real).real,color,name+' Re');curve(axs[0,0],lags,(cov/cov[0].real).imag,color,name+' Im',True,2)
axs[0,0].set(title='Separate source correlations',xlabel='Lag [us]',ylabel='Normalized g1',ylim=(-1.05,1.05),xlim=(0,10));axs[0,0].legend(ncol=2)
ax=axs[0,1]
curve(ax,lags[1:],(cs/cs[0].real).real[1:],C['total'],'Analog total Re');curve(ax,lags[1:],(cs/cs[0].real).imag[1:],C['total'],'Analog total Im',True)
ax.plot(lags[1:],weighted.real[1:],color=C['theory'],ls=':',lw=1.7,label='Power-weighted Re');ax.plot(lags[1:],weighted.imag[1:],color=C['theory'],ls='-.',lw=1.4,label='Power-weighted Im')
assert max(abs((cs/cs[0].real)[1:].real).max(),abs((cs/cs[0].real)[1:].imag).max(),abs(weighted[1:].real).max(),abs(weighted[1:].imag).max()) < .08
ax.set(title='Independent-source sum: positive-lag detail',xlabel='Lag [us]',ylabel='g1',ylim=(-.08,.08),xlim=(.15,10));ax.legend(ncol=2)
res=diag['step5_minus_step3_analog_ADC_V'][:];wall=h['step4/analog_ADC_V'][:];sel=slice(0,70)
for vals,c,label,ls in [(res,C['total'],'Residual I','-'),(wall,C['cavity'],'step4 I','--')]:axs[1,0].plot(t[sel]*1e6,vals.real[sel]*1e6,color=c,ls=ls,label=label)
axs[1,0].plot(t[sel]*1e6,res.imag[sel]*1e6,'s--',ms=2,mfc='white',color=C['total'],label='Residual Qeff');axs[1,0].plot(t[sel]*1e6,wall.imag[sel]*1e6,':',color=C['cavity'],label='step4 Qeff')
axs[1,0].plot(t[sel]*1e6,res.real[sel]*1e6,'o',ms=2,color=C['total']);axs[1,0].set(title='Analog residual at ADC plane: I / Qeff',xlabel='Time [us]',ylabel='Voltage [uV ADC]');axs[1,0].legend(ncol=2)
err=(res-wall)*1e6;axs[1,1].plot(t[sel]*1e6,err.real[sel],'.-',ms=2,color=C['total'],label='Re error');axs[1,1].plot(t[sel]*1e6,err.imag[sel],'.--',ms=2,color=C['theory'],label='Im error');axs[1,1].ticklabel_format(axis='y',style='sci',scilimits=(0,0));axs[1,1].set(title='Residual − step4: floating-point error only',xlabel='Time [us]',ylabel='Error [uV ADC]');axs[1,1].legend()
residualfig=save(fig,'step5_source_covariance_and_residual')

D=sd.Deck()
def page(title,sub,notes=''):
 s=D.new(' ',sub,'Frozen v41 physical parameters, measured kz and short realizations; v43 source selection and diagnostic plots.',notes)
 s['title']=title;s['items'][1]['text']=title;s['items'][1]['size']=25;s['footer']='FLASH | PART I ONLY | v43 | SHARED SHORT REALIZATIONS';return s
def text(s,x,y,w,ht,txt,size=15,bold=False,color=sd.INK):D.text(s,x,y,w,ht,txt,size,bold,color)
def table(s,headers,rows,y,widths,size=13,rowh=.47):
 for i,row in enumerate([headers]+rows):
  x=.65
  if i==0:D.rect(s,.55,y-.05,12.2,rowh,'#E8EDF4')
  for item,w in zip(row,widths):text(s,x,y+i*rowh,w-.08,rowh,str(item),size,i==0);x+=w
s=page('Toy simulation — progressive physical sources','Part I | one absolute scale, one measured readout map, six physical steps',
 'Only steps1–2 contain validation sources. Step3 is existing equivalent receiver alone. Step4 is existing wall bath alone. Step5 reuses exactly those arrays before quantization. Step6 preserves TM010 and extends to other modes. No new draws, fits, full-run simulation or LF modifications.')
rows=[['1','Coherent tone','ON','—','—','—'],['2','Cavity + readout','ON','ON','—','—'],['3','Electronic noise only','OFF','OFF','OFF','ON'],['4','Cavity thermal only','OFF','OFF','ON','OFF'],['5','Thermal + electronic','OFF','OFF','ON','ON'],['6','All three cavity modes','OFF','OFF','ON','ON']]
table(s,['Step','Construction','Tone','Injected test noise','Wall bath','Receiver'],rows,1.95,[.7,3.35,1.1,2.55,1.7,2.6],12,rowh=.53)
text(s,.7,6,11.9,.65,'Step 5 = exact analog step 3 + exact analog step 4; quantize the sum once. Examples: 52.4288 ms, 262,144 complex samples, 5 MS/s.',17,True)
# Retain the hardware chain already documented in v42.
previous=json.loads((WORK/'reports/iq_noise_summary_v42_partI/slide_model.json').read_text());hardware=copy.deepcopy(previous[1]);hardware['footer']='FLASH | PART I ONLY | v43';D.slides.append(hardware)
s=page('Absolute normalization — From physical noise to ADC voltage','Physical source → cavity/output plane → RF gain → measured kz with LF setting correction → ADC',
 'Unchanged matched complex RMS convention E|z|²/R=available integrated power, R=50ohm. G_RF=103.4dB. kz_cal already contains the ±5V conversion and final mixer/LPF response. LF20/60dB amplitude correction is0.01; no response-shape change assumed. Science±2V, calibration±5V as ODB. No extra0.4 or component loss. Readout phase unmeasured, chosen zero as in original stationary synthesis. Sampling aliases within measured support are folded; outside support remains zero.')
text(s,.75,1.85,11.8,.6,'VADC(f) = 10^(103.4/20) × kz,cal(f) × 0.01 × Vphysical(f)',22,True,C['total'])
text(s,.75,2.53,11.8,.85,'SADC(f) = R × 10^(103.4/10) × |0.01 kz,cal(f)|² × Sphysical(f)\nSphysical: available noise [W/Hz] at cavity output / equivalent receiver plane; R = 50 ohm.',16)
text(s,.75,3.55,11.8,.7,'Thermal: Sphysical = [h f0 / (exp(h f0 / kB T) − 1)] × |Hb(f)|²\nElectronic: Sphysical = kB Tn, with Tn = 3.955 K; independent of the wall bath.',16)
text(s,.75,4.52,11.8,.72,'kz,science = kz,cal / 100: LF gain 60 → 20 dB (−40 dB amplitude ratio).\nMeasured kz contains the mixer/LPF chain response; apply it once.',16)
text(s,.75,5.48,11.8,.72,'ADC: calibration ±5 V → 10/65535 V/count; science ±2 V → 4/65535 V/count.\nQuantize I and Qeff separately: Δ = 61.036 uV; z = I − i Qhardware = I + i Qeff.',16)
text(s,.75,6.43,11.8,.3,'Absolute budget, physical parameters and kz are unchanged from v42.',13,True)
s=page('Physical source and transfer functions','The applied response is explicit; the same readout is used for every step.',
 'H12=sqrt(k1*k2)/(kt/2+i2pi*detuning); Hb=sqrt(ki*k2)/(kt/2+i2pi*detuning); ki=2pi*f0/Q0, k1=ki*kappa1,k2=ki*kappa2,kt=ki+k1+k2. No newly fitted response. Figures are direct evaluations of the unchanged model/calibration.')
text(s,.7,1.8,12,.85,'Port 1 probe → H12 = sqrt(k1 k2) / [kt/2 + i 2π(f − fIF)] → cavity port 2\nWall thermal bath → Hb = sqrt(ki k2) / [kt/2 + i 2π(f − fIF)] → cavity port 2',16)
text(s,.7,2.82,12,.6,'ki = 2π f0/Q0; k1 = ki κ1; k2 = ki κ2; kt = ki + k1 + k2.\nElectronic noise is equivalent input-referred receiver noise, added after the cavity response.',15)
D.image(s,.7,3.7,11.9,2.1,transferfig)
text(s,.7,6.05,11.8,.6,'TM010: T = 40.422 mK; f0 = 8.737119 GHz; Q0 = 52,490; κ1 = 0.001122; κ2 = 0.79. The science noise contains no coherent tone or injected test noise.',14)
info=[('step1','Step 1 — Coherent tone','Known probe → cavity bypass → readout → ADC','Synthetic −115 dBm probe at the declared RF input plane; no noise source.'),('step2','Step 2 — Cavity response and readout filtering','Same coherent probe + injected test noise → H12 → readout → ADC','Injected test noise is a validation source, not thermal wall emission.'),('step3','Step 3 — Electronic noise only','Equivalent receiver noise, kB Tn → readout → ADC','Tone OFF; injected noise OFF; cavity thermal noise OFF. Same receiver array as step 5.'),('step4','Step 4 — Cavity thermal noise only','Wall-bath thermal noise → Hb → readout → ADC','All other sources OFF. Physical microvolt zoom; thermal-only ADC quantization is visible.'),('step5','Step 5 — Cavity thermal noise + electronic noise','[Exact step 4 analog + exact step 3 analog] → quantize once','The two streams are summed before quantization; separately digitized streams are not added.')]
for key,title,flow,caption in info:
 s=page(title,flow,'Common six panels and common main axes. I filled circles and Qeff hollow squares are actual ADC samples at200ns. g1 uses a single record mean and unbiased linear covariance. Zoom excludes zero lag; limits checked against both components. PSD symmetric Hann16384 no detrending. Amplitude shape scaled only by predicted analog RMS; absolute RMS stated below. Phase excludes exact zero ADC values. '+caption)
 D.image(s,.38,1.7,12.55,4.45,figs[key]);g=h[key];pre=np.sqrt(g.attrs['MC_analog_power_V2']);post=np.sqrt(g.attrs['MC_ADC_power_V2'])
 text(s,.65,6.3,12.05,.28,f'Analog RMS {pre*1e3:.6g} mV ADC | Digitized RMS {post*1e3:.6g} mV | Nonzero ADC fraction {1-g.attrs["ADC_zero_fraction"]:.4f}',12,True,C['total'])
 text(s,.65,6.64,12.05,.22,caption,10.5)
s=page('Step 5 — Source correlations and analog residual','Independent-source covariance adds in expectation; finite realizations retain a cross term.',
 'Power-weighted g1=(Pc*gc+Pe*ge)/(Pc+Pe), using centered source powers in the same record. Sample total covariance additionally includes finite-realization cross covariance; no cross term is removed. Residual is formed before ADC quantization. Difference from step4 is floating-point cancellation only. Error panel remains in physical microvolts, with scientific axis notation. No display gain or fit.')
D.image(s,.45,1.7,12.45,4.75,residualfig)
d=m['diagnostics'];text(s,.65,6.3,12,.28,f'Analog residual RMS = {d["thermal_RMS_V"]*1e6:.5f} uV | Max complex error = {d["residual_max_abs_error_V"]:.3g} V',13,True)
text(s,.65,6.65,12,.22,'g1,weighted = (Pe g1,e + Pc g1,c)/(Pe + Pc); Pc/(Pe + Pc) = 2.89 × 10^-7. Cross terms remain finite.',10.5)
for mode in MODES:
 key='step6_'+mode;p=m['metrics'][mode]
 s=page('Step 6 — Complete noise model: '+mode,'Same physical construction; modes shown separately to preserve visibility.',
 'Three separate slides keep the same six panels, common main scales and mode colors without overplotting. All modes display Re and Im at every200ns lag, including positive-lag zoom. TM010 arrays remain exactly step5. Other-mode draws are preserved from v41. Common Tn and RF gain are conditional, unchanged assumptions. No additional response or fit.')
 D.image(s,.38,1.7,12.55,4.45,figs[key]);text(s,.65,6.3,12.05,.3,f'{mode} | Expected RMS {p["total_RMS_expected_ADC_V"]*1e3:.4f} mV ADC | Final IF {p["final_IF_hz"]/1e6:.3f} MHz | Cavity τ {p["tau_cavity_us"]:.3f} us',12,True,MC[MODES.index(mode)])
 text(s,.65,6.64,12.05,.22,f'f0 = {p["f0_hz"]/1e9:.6f} GHz; Q0 = {p["q0"]:,.0f}; κ1 = {p["kappa1"]:.6g}; κ2 = {p["kappa2"]:.3g}. Thermal + electronic only.',10.5)
# Keep existing reference observables, but redraw the correlations below to include all samples without clipping.
fig,axs=plt.subplots(2,3,figsize=(12.8,4.5));fig.subplots_adjust(left=.06,right=.99,top=.9,bottom=.12,hspace=.65,wspace=.34)
for i,mode in enumerate(MODES):
 g=h['step6_'+mode];corr(axs[0,i],g['ADC_g1'][:],mode+'_summary',MC[i],True);axs[0,i].set_title(mode+' — residual complex g1')
 q=g['quantized_ADC_V'][:];rms2=g.attrs['expected_total_power_V2'];v=abs(q-q.mean())**2/rms2;xx=np.linspace(0,12,130);cc=np.array([np.mean(v>x) for x in xx]);valid=cc>20/N
 axs[1,i].plot(xx[valid],np.log(cc[valid]),color=MC[i],label='ADC');axs[1,i].plot(xx,-xx,':',color=C['theory'],label='Rayleigh');axs[1,i].set(title=mode+' — amplitude CCDF',xlabel='A² / predicted analog power',ylabel='log P(amplitude > A)',xlim=(0,12),ylim=(-12,0));axs[1,i].legend()
ref=save(fig,'reference_observables_separated')
s=page('Reference-noise observables','Three modes, separate panels: residual correlation and amplitude CCDF.',
 'No fitted curve. Proper Gaussian/Rayleigh ensemble reference. This is a short example, not a full-run statistical validation. Differences in shape, readout and finite sampling are retained. Original reference model and normalization unchanged. No experimental data or step7/8 included.')
D.image(s,.45,1.8,12.45,4.7,ref);text(s,.7,6.5,11.9,.3,'Every positive-lag marker is an actual sampled delay (200 ns); no mode is hidden by another curve.',12)
# Copy all referenced assets to this version, including any frozen hardware-slide assets.
for s in D.slides:
 for item in s['items']:
  if item['kind']=='image':
   src=Path(item['path'])
   if src.parent!=A:dst=A/src.name;shutil.copy2(src,dst);item['path']=str(dst)
 for it in s['items']:
  if it['kind']=='text' and it['y']==.38:
   it['size']=25
   while len(sd.wrap(s['title'],it['w']*.88,it['size']).splitlines())>1:it['size']-=1
   it['text']=s['title']
assert all(v['no_clipping'] for v in zoom_checks.values())
(OUT/'validation.json').write_text(json.dumps({'source_checks':m['checks'],'analog_residual':m['diagnostics'],'correlation_zooms':zoom_checks,'normalization_unchanged':True,'new_random_draws':False,'new_fits':False,'scope':'Part I only'},indent=2)+'\n')
(OUT/'data').mkdir(exist_ok=True);(OUT/'data/short_examples_metrics.json').write_text(json.dumps(m,indent=2)+'\n')
h.close();sd.export(D,OUT,'v43_partI','17 November 2026')
