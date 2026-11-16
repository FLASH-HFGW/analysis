"""Part I only: 10 slides, common-layout short steps1–6 and absolute mapping."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,sys
import numpy as np,h5py
from scipy import signal,stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
sys.path.insert(0,'/tmp/v18-python-deps');sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import slide_deck as sd
REPO=Path(__file__).resolve().parents[2];WORK=Path('/home/mazzitel/HFGW/analysis-work/Run2');SIM=WORK/'simulation/presentation_steps1_6_v41';OUT=WORK/'reports/iq_noise_summary_v41_partI';A=OUT/'assets';D=OUT/'data';A.mkdir(parents=True,exist_ok=True);D.mkdir(exist_ok=True)
m=json.loads((SIM/'metrics.json').read_text());assert m['all_checks_passed'];cfg=m['configuration'];fs=cfg['fs_hz'];N=cfg['samples_per_example'];C=dict(cavity='#43a1ed',injected='#43a1ed',receiver='#ed812a',tone='#263952',total='#7657A6',theory='#263952',data='#007F86');modes=['TM010','TM011','TM012'];mode_ls=['-','--',':'];mode_mk=['o','s','^']
plt.rcParams.update({'font.size':10,'axes.titlesize':11,'axes.labelsize':10,'xtick.labelsize':8.5,'ytick.labelsize':8.5,'legend.fontsize':8,'axes.grid':True,'grid.alpha':.18,'lines.linewidth':1.1,'savefig.facecolor':'white'})
h=h5py.File(SIM/'short_examples.h5','r');t=h['time_s'][:];f=h['frequency_hz'][:];lag=np.arange(501)/fs
manifest=[]
def save(fig,name):
 fig.savefig(A/(name+'.png'),dpi=210);fig.savefig(A/(name+'.pdf'));plt.close(fig);return A/(name+'.png')
def gallery(keys,name):
 fig,axs=plt.subplots(2,3,figsize=(12.9,4.85));fig.subplots_adjust(left=.065,right=.985,bottom=.115,top=.91,hspace=.64,wspace=.34)
 for j,key in enumerate(keys):
  g=h[key];z=g['analog_ADC_V'][:];adc=g['quantized_ADC_V'][:];rms=np.sqrt(g.attrs['expected_total_power_V2']);ls=mode_ls[j];marker=mode_mk[j];label=modes[j] if len(keys)>1 else 'ADC';nshow=24
  # Same native positions and physical main axes in all six stage figures.
  ax=axs[0,0];ax.plot(t[:nshow]*1e6,z.real[:nshow]*1e3,color=C['total'],alpha=.38,ls=ls);ax.plot(t[:nshow]*1e6,z.imag[:nshow]*1e3,color=C['total'],alpha=.38,ls=ls)
  ax.plot(t[:nshow]*1e6,adc.real[:nshow]*1e3,marker,ms=3.7,color=C['total'],ls='none',label=label+' I');ax.plot(t[:nshow]*1e6,adc.imag[:nshow]*1e3,marker,ms=3.7,mfc='white',mec=C['total'],ls='none',label=label+' Qeff');ax.set(title='Sampled I/Q: ADC markers',xlabel='Time [us]',ylabel='Voltage [mV ADC]',xlim=(0,t[nshow-1]*1e6),ylim=(-140,140))
  ax=axs[0,1];xx=adc[:1200];ax.scatter(xx.real*1e3,xx.imag*1e3,s=4,marker=marker,color=C['total'],alpha=.2,label=label);ax.set(title='IQ constellation: same ADC axes',xlabel='I [mV ADC]',ylabel='Qeff [mV ADC]',xlim=(-140,140),ylim=(-140,140));ax.set_aspect('equal',adjustable='box')
  ax=axs[0,2];edges=np.linspace(0,5,101);raw=abs(adc)/rms;analog=abs(z)/rms
  count=np.histogram(raw,edges)[0];den=count/(N*np.diff(edges));ax.stairs(np.maximum(den,1e-6),edges,color=C['total'],ls=ls,label=label);ca=np.histogram(analog,edges)[0];ax.stairs(np.maximum(ca/(N*np.diff(edges)),1e-6),edges,color=C['theory'],alpha=.55,ls='--' if len(keys)==1 else ls,label='Pre-quantization' if len(keys)==1 else None)
  if key in ['step4','step5'] or key.startswith('step6'):
   x=np.linspace(.001,5,400);ax.plot(x,2*x*np.exp(-x*x),color=C['theory'],ls=':',lw=1,label='Rayleigh (continuous)' if j==0 else None)
  ax.set(title='Amplitude distribution: shape only',xlabel='A / predicted pre-ADC RMS',ylabel='Probability density',xlim=(0,5),ylim=(1e-3,60),yscale='log')
  ax=axs[1,0];edges=np.linspace(-np.pi,np.pi,65);valid=abs(adc)>0
  if valid.any():
   cc=np.histogram(np.angle(adc[valid]),edges)[0];ax.stairs(np.maximum(cc/(cc.sum()*np.diff(edges)),1e-5),edges,color=C['total'],ls=ls,label=label)
  cp=np.histogram(np.angle(z[abs(z)>0]),edges)[0];ax.stairs(np.maximum(cp/(cp.sum()*np.diff(edges)),1e-5),edges,color=C['theory'],alpha=.45,ls='--' if len(keys)==1 else ls)
  if key in ['step4','step5'] or key.startswith('step6'):ax.axhline(1/(2*np.pi),color=C['theory'],ls=':',lw=.8)
  ax.set(title='Phase: zero-amplitude ADC samples excluded',xlabel='arg(I + i Qeff) [rad]',ylabel='Density [rad^-1]',xlim=(-np.pi,np.pi),ylim=(1e-3,5),yscale='log',xticks=[-np.pi,0,np.pi],xticklabels=['-pi','0','pi'])
  ax=axs[1,1]
  for comp in g['components']:
   zz=g['components'][comp][:];fp,pp=signal.welch(zz,fs,window=np.hanning(16384),nperseg=16384,noverlap=0,return_onesided=False,detrend=False);order=np.argsort(fp)
   if len(keys)==1:ax.plot(fp[order]/1e6,10*np.log10(np.maximum(pp[order],1e-30)),color=C[comp],lw=.7,label={'cavity':'Wall bath','injected':'Injected probe noise','receiver':'Receiver','tone':'Calibration probe'}[comp])
  fp,pp=signal.welch(adc,fs,window=np.hanning(16384),nperseg=16384,noverlap=0,return_onesided=False,detrend=False);order=np.argsort(fp);ax.plot(fp[order]/1e6,10*np.log10(np.maximum(pp[order],1e-30)),color=C['total'],ls=ls,lw=.9,label=label+' total')
  ax.set(title='PSD: same Hann estimator',xlabel='Final IF [MHz]',ylabel='PSD [dB V^2/Hz]',xlim=(-2.5,2.5),ylim=(-190,-30))
  ax=axs[1,2];gg=g['ADC_g1'][:];ga=g['analog_g1'][:];sel=lag<=10e-6;ax.plot(lag[sel]*1e6,gg[sel].real,color=C['total'],ls=ls,label=label+' Re');
  if len(keys)==1:
   ax.plot(lag[sel]*1e6,gg[sel].imag,color=C['total'],ls=':',label='ADC Im');ax.plot(lag[sel]*1e6,ga[sel].real,color=C['theory'],ls='--',alpha=.6,label='Pre-ADC Re')
  ax.set(title='Complex normalized autocorrelation',xlabel='Lag [us]',ylabel='g1',xlim=(0,10),ylim=(-1.05,1.05));ax.axhline(0,color='#888888',lw=.5)
 # Insets are explicit physical zooms, never hidden gain rescaling.
 if keys==['step2'] or keys==['step4']:
  g=h[keys[0]];z=g['analog_ADC_V'][:];q=g['quantized_ADC_V'][:];thermal=keys==['step4'];factor=1e6 if thermal else 1e3;unit='uV' if thermal else 'mV';lim=85 if thermal else 8
  inz=axs[0,0].inset_axes([.48,.55,.5,.39]);inz.plot(t[:24]*1e6,z.real[:24]*factor,color=C['cavity'],lw=.8);inz.plot(t[:24]*1e6,q.real[:24]*factor,'o',color=C['total'],ms=2.4);inz.set(ylim=(-lim,lim),title='Explicit zoom ['+unit+']');inz.tick_params(labelsize=6);inz.title.set_fontsize(7)
  inz=axs[0,1].inset_axes([.51,.55,.47,.4]);inz.scatter(z.real[:800]*factor,z.imag[:800]*factor,color=C['cavity'],s=2,alpha=.2);inz.scatter(q.real[:800]*factor,q.imag[:800]*factor,color=C['total'],s=3,alpha=.3);inz.set(xlim=(-lim,lim),ylim=(-lim,lim),title='Zoom ['+unit+']');inz.tick_params(labelsize=6);inz.title.set_fontsize(7)
 for ax in axs.flat:
  handles,labels=ax.get_legend_handles_labels()
  if handles:ax.legend(fontsize=6.4,loc='best',framealpha=.85,handlelength=1.8)
 return save(fig,name)
# Six gallery figures, positions and principal limits identical.
for i in range(1,6):gallery([f'step{i}'],f'step{i}_common_panels')
gallery(['step6_'+mode for mode in modes],'step6_common_panels')
# Three measured calibration curves; no hypothetical LF modification.
cal=json.loads(Path(cfg['calibration_reconstruction']).read_text());fig,axs=plt.subplots(1,2,figsize=(7.2,3.2));cols=[C['total']]*3
for mi,(mode,col) in enumerate(zip(modes,cols)):
 pts=cal['curves'][mode];off=cal['comparison'][mode]['rf_if_offset_hz'];x=np.array([p['rf_hz']-off for p in pts]);k=np.array([p['kz_integrated'] for p in pts]);order=np.argsort(x);x=x[order];k=k[order]
 axs[0].plot(x/1e6,k,'.',ls=mode_ls[mi],color=col,ms=2.5,label=mode);axs[1].plot(x/1e6,k/100,'.',ls=mode_ls[mi],color=col,ms=2.5,label=mode)
axs[0].set(title='Measured calibration setting (60 dB LF)',xlabel='Calibration final IF [MHz]',ylabel='kz,cal [V / RF RMS V]',xlim=(-2.5,2.5));axs[1].set(title='Nominal science mapping (20 dB LF)',xlabel='Final IF [MHz]',ylabel='kz,data = kz,cal / 100',xlim=(-2.5,2.5));axs[0].legend(fontsize=8);fig.tight_layout();save(fig,'calibration_mapping')
# Reference-observable overview: existing short arrays, no fits.
fig,axs=plt.subplots(2,2,figsize=(12.2,4.7));fig.subplots_adjust(left=.07,right=.98,bottom=.13,top=.91,hspace=.65,wspace=.3)
for mi,mode in enumerate(modes):
 g=h['step6_'+mode];q=g['quantized_ADC_V'][:];z=g['analog_ADC_V'][:];P=g.attrs['expected_total_power_V2'];ls=mode_ls[mi]
 radii=np.linspace(0,12,180);amp2=abs(q-q.mean())**2/P;cc=np.array([np.mean(amp2>v) for v in radii]);ok=cc>20/len(q);axs[0,0].plot(radii[ok],np.log(cc[ok]),color=C['total'],ls=ls,label=mode)
 gg=g['ADC_g1'][:];axs[1,0].plot(lag[1:51]*1e6,gg[1:51].real,color=C['total'],ls=ls,label=mode+' Re');axs[1,0].plot(lag[1:51]*1e6,gg[1:51].imag,color=C['theory'],ls=ls,alpha=.7,label=mode+' Im')
 S=g['PSD_expected_ADC_V2_Hz'][:];co=fs*np.fft.ifft(S);sizes=np.array([8,32,128,512,2048,8192]);v=[];vm=[]
 for size in sizes:
  k=np.arange(1,size);pred=(size*co[0].real+2*np.sum((size-k)*co[k].real))/size**2;v.append(pred-fs*S[0]/N);means=q[:N//size*size].reshape(-1,size).mean(axis=1);vm.append(np.mean(abs(means-means.mean())**2))
 axs[1,1].loglog(sizes/fs,np.array(v)/P,color=C['theory'],ls=ls);axs[1,1].loglog(sizes/fs,np.array(vm)/P,mode_mk[mi],color=C['total'],ms=4,label=mode)
 g=h['step6_TM010'];q=g['quantized_ADC_V'][:]
for length,ls in zip([1,10,100],mode_ls):
 good=(abs(q[length:])>0)&(abs(q[:-length])>0);delta=np.angle(q[length:][good]*q[:-length][good].conj());cnt,e=np.histogram(delta,np.linspace(-np.pi,np.pi,65));axs[0,1].stairs(cnt/cnt.sum()/np.diff(e),e,color=C['total'],ls=ls,label=f'lag {length/fs*1e6:g} us')
xx=np.linspace(0,12);axs[0,0].plot(xx,-xx,color=C['theory'],ls=':',label='Rayleigh expectation');axs[0,0].set(title='Amplitude CCDF (centered ADC)',xlabel='A^2 / predicted pre-ADC power',ylabel='log P(amplitude > A)',xlim=(0,12),ylim=(-12,0));axs[0,1].set(title='TM010 phase increments: nonzero endpoints',xlabel='Wrapped phase increment [rad]',ylabel='Density [rad^-1]',xlim=(-np.pi,np.pi));axs[1,0].set(title='Receiver-dominated g1: short-lag detail',xlabel='Lag [us]',ylabel='g1',xlim=(0,10),ylim=(-.08,.05));axs[1,1].set(title='Variance of block means: short record only',xlabel='Integration time [s]',ylabel='Variance / predicted pre-ADC power')
for ax in axs.flat:ax.legend(fontsize=7,ncol=2)
save(fig,'reference_observables')
# Native slide assembly.
deck=sd.Deck()
def page(title,subtitle,source,notes):
 s=deck.new(' ',subtitle,source,notes);s['title']=title;s['footer']='FLASH | PART I ONLY | v41 | SHORT TOY EXAMPLES';return s
def textbox(s,x,y,w,height,text,size=16,bold=False,color=sd.INK):deck.text(s,x,y,w,height,text,size,bold,color)
def table(s,heads,rows,x=.65,y=3.65,widths=None,size=13,rowh=.42):
 widths=widths or [12/len(heads)]*len(heads)
 for i,row in enumerate([heads]+rows):
  xx=x
  for value,ww in zip(row,widths):textbox(s,xx,y+i*rowh,ww-.05,rowh,str(value),size,i==0);xx+=ww
s=page('Toy simulation: calibration to physical noise','Part I review draft | six progressive steps, one physical scale and one measured readout map','Common-input short simulations, 52.4288 ms per example; no science reconstruction or full-run MC.','Only Part I is assembled. Later data section will include the two requested additional slides on long-term DC/AC and experimental amplitude/phase/increment distributions. No comparison or posterior LF hypotheses enter this draft.')
deck.bullets(s,.75,1.9,11.7,['Steps 1–3: validate the acquisition chain with a known probe; identify every injected calibration source.','Steps 4–6: switch the validation sources off; retain thermal cavity emission and equivalent receiver noise.','Use measured cavity parameters, shared noise draws, physical ADC units and explicit sampled points.','Map the source model through measured per-mode kz. No arbitrary display gain, gain fit or additional LF correction.'],19,.22)
textbox(s,.8,6.15,11.5,.5,'Repeated panels: ADC I/Q • IQ cloud • amplitude • phase • PSD • complex autocorrelation',16,True,C['total'])
s=page('One physical model, one readout convention','Shared physical inputs throughout: T = 40.422 mK; receiver Tn = 3.955 K (conditional)','Thesis Table 6.1 and Fig. 5.2; observed run680 T15; ODB ADC/LO settings; reconstructed integrated-tone calibration.','The measured response includes the final mixer/LPF path. It is used once in every common-input example, with nominal LF60→20dB amplitude factor0.01. Receiver Tn applicability and mode-independent RF gain remain assumptions. Measured kz contains the calibration response; no step7/8 change is applied. All noise distributions are referenced to the same matched complex-voltage convention E|z|²/R=available integrated PSD.')
boxes=[('Cavity / probe',C['cavity']),('RF gain\n103.4 dB',C['theory']),('IQ + LF\n60 → 20 dB',C['receiver']),('Mode paths\nmeasured kz',C['total']),('ADC\n±2 V; 5 MS/s',C['theory'])]
for j,(txt,col) in enumerate(boxes):
 xx=.7+j*2.52;deck.rect(s,xx,1.95,2.24,.95,'#FFFFFF');deck.rect(s,xx,1.95,2.24,.05,col);textbox(s,xx+.1,2.1,2.04,.65,txt,16,True,col)
 if j<4:textbox(s,xx+2.28,2.22,.22,.35,'→',17)
textbox(s,.7,3.12,12,.45,'Thermal bath and equivalent receiver noise are independent; the calibration probe is absent in steps 4–6.',15)
rows=[]
for mode in modes:
 p=m['metrics'][mode];rows.append([mode,f"{p['f0_hz']/1e9:.6f}",f"{p['q0']:,.0f}",f"{p['kappa1']:.6g} / {p['kappa2']:.3g}",f"{p['final_IF_hz']/1e6:.3f}",f"{p['tau_cavity_us']:.3f}"])
table(s,['Mode','f0 [GHz]','Q0','kappa1 / kappa2','Final IF [MHz]','Cavity tau [us]'],rows,y=3.85,size=12,rowh=.47)
textbox(s,.7,6.02,12,.6,'z = I − i Qhardware = I + i Qeff    |    ADC step = 4/65535 V = 61.036 uV    |    no fitted gain',16,True)
stepinfo=[('Step 1 — A coherent tone validates I/Q acquisition','Known synthetic RF probe; cavity bypassed; no stochastic science sources.','Calibration probe: -115 dBm at the declared RF input plane. Markers are ADC samples; lines connect pre-quantization values.'),('Step 2 — Cavity response and readout filtering','Same probe plus controlled injected noise; actual port-1 → port-2 cavity transfer.','The weak input coupling reduces the transmitted probe. The inset is a labelled physical zoom, not an added gain.'),('Step 3 — Receiver noise in the validation chain','Keep the same injected-noise draw and probe; add an independent receiver-noise draw.','The receiver realization is reused exactly in step 5. The probe is still a calibration input, not scientific noise.'),('Step 4 — Thermal emission: calibration sources off','No probe, no injected validation noise, no receiver yet; physical wall bath at 40.422 mK.','Pre-ADC thermal RMS ≈14.6 uV; about99.3% of ADC complex samples quantize to zero. Do not expect ADC Rayleigh statistics here.'),('Step 5 — Thermal cavity plus receiver noise','Same wall-bath realization as step 4; same independent receiver realization as step 3.','Quantize the sum once. Thermal and receiver ADC streams do not add exactly after separate quantization.'),('Step 6 — One physical model, three cavity modes','TM010 is unchanged from step 5; add independently drawn TM011 and TM012 with their measured parameters.','Modes: TM010 solid/circle; TM011 dashed/square; TM012 dotted/triangle. All three retain their physical amplitude.')]
for i,(title,sub,caption) in enumerate(stepinfo,1):
 scope='CALIBRATION / VALIDATION' if i<=3 else 'SCIENCE NOISE | NO COHERENT TONE'
 keys=[f'step{i}'] if i<6 else ['step6_'+mo for mo in modes]
 s=page(title,sub,'52.4288 ms; same ADC/readout mapping. Colours: cavity/injected noise cyan, receiver orange, total ADC purple, probe/theory navy.',scope+'\n'+caption+'\nSame six panel positions and main axes for every step. I uses filled markers and Qeff hollow markers. The trace shows24consecutive ADC instants; IQ drawing uses a declared subset. Amplitude axes are divided by predicted pre-ADC RMS for shape comparison only; absolute levels are not rescaled. PSD uses16384-sample symmetric Hann segments and fs*sum(w²), no per-segment detrending; g1 uses one record mean and linear FFT covariance divided byN−lag. Phase excludes exactly-zero ADC amplitudes. The analog-source phase is not claimed to include the measured phase of the full readout.')
 deck.image(s,.42,1.7,12.48,4.7,A/f'step{i}_common_panels.png')
 # A concise same-position numerical strip below each figure.
 if i<6:
  g=h['step'+str(i)];pre=np.sqrt(g.attrs['MC_analog_power_V2'])*1e3;adc=np.sqrt(g.attrs['MC_ADC_power_V2'])*1e3;unitline=f'MC pre-ADC RMS = {pre:.5g} mV   |   MC digitized RMS = {adc:.5g} mV   |   Valid phase fraction = {1-g.attrs["ADC_zero_fraction"]:.4f}'
 else:unitline='Expected pre-ADC RMS [mV]:  TM010 27.173   |   TM011 13.701   |   TM012 8.406'
 textbox(s,.65,6.32,12.05,.26,unitline,12,True,C['total']);textbox(s,.65,6.62,12.05,.26,caption,10.5)
 s['subtitle']=scope+' | '+sub
 # visible subtitle replaces original text, with fixed smaller font.
 for it in s['items']:
  if it['kind']=='text' and it['y']==1.12:it['text']=sd.wrap(s['subtitle'],it['w'],12);it['size']=12
s=page('Absolute normalization: measured kz, no gain fit','Same measured mapping in every example; no additional hypothetical LF response','Integrated-tone calibration curves per mode; RF103.4dB; nominal LF60→20dB ratio; ODB cal±5V/science±2V.','The arbitrary140dB and nominal143dB examples are not used. Calibration kz was already converted with10/65535V/count and receives no extra factor0.4. We applykz_data=kz_cal/100 and RFgain103.4dB once. The extra36dB FET is outside the tone calibration and already included in the RF budget. The measured response replaces any assumed LPF; multiplying another LPF would double count it. Unverified common Tn, RF gain and LF shape ratio remain conditional assumptions. Probe power -115dBm is a synthetic validation setting, not the recorded -60dBm calibration tone.')
deck.image(s,.6,1.85,7.8,3.75,A/'calibration_mapping.png')
deck.bullets(s,8.7,1.9,4.,['RF gain: 103.4 dB; second FET counted once.','LF: kz,data = kz,cal / 100.','ADC: calibration ±5 V; science ±2 V.','Measured readout includes LPF; no extra LPF.'],15,.16)
rows=[]
for mo in modes:
 p=m['metrics'][mo];rows.append([mo,f"{p['thermal_RMS_expected_ADC_V']*1e6:.3f}",f"{p['receiver_RMS_expected_ADC_V']*1e3:.3f}",f"{p['total_RMS_expected_ADC_V']*1e3:.3f}",f"{p['sigma_q_expected_ADC_V']*1e3:.3f}"])
table(s,['Mode','Wall RMS [uV]','Receiver RMS [mV]','Total RMS [mV]','sigma_q [mV]'],rows,y=5.55,widths=[1.5,2.45,2.55,2.55,2.55],size=11,rowh=.28)
textbox(s,.7,6.76,12,.15,'Expected continuous pre-ADC values. Histogram shape-normalization never changes this absolute budget.',9)
s=page('Reference-noise observables: no data fits','Same short examples; no coherent tone and no LF correction introduced to match the data','52.4288ms examples; predicted source PSD and sampled MC. Block means use at least32blocks; no long-time extrapolation.','Rayleigh and uniform-phase expectations refer to the proper continuous Gaussian model. ADC quantization is simulated explicitly. The variance expectation uses the covariance implied by the sampled PSD, with finite-record mean removal. It is not an imported step8 LF model. No experimental data, new fits or full-run simulations are used here. Original measured covariance and comparison results remain untouched. Future assembly adds the approved experimental DC/AC and amplitude/phase/increment slides before the unchanged comparison and possible-explanations sections.')
deck.image(s,.5,1.72,12.3,4.75,A/'reference_observables.png')
textbox(s,.7,6.48,11.9,.35,'Receiver Tn, common RF gain and the LF setting ratio remain conditional inputs; offsets and IQ imbalance are not fitted.',12)
# Ensure no title wraps into the subtitle; font size is adjusted only for native title.
for s in deck.slides:
 for it in s['items']:
  if it['kind']=='text' and it['y']==.38:
   it['size']=28
   while len(sd.wrap(s['title'],it['w']*.84,it['size']).splitlines())>1:it['size']-=1
   it['text']=s['title']
 for it in s['items']:
  if it['kind']=='text':
   needed=len(it['text'].splitlines())*it['size']*1.15/72
   assert needed<=it['h']+.13,(s['title'],it['text'],needed,it['h'])
manifest=[{'slide':i,'title':s['title'],'simulation_input':str(SIM/'metrics.json'),'figures':[it['path'] for it in s['items'] if it['kind']=='image'],'scope':'PartI only; source model/calibrated readout; no scientific data comparison'} for i,s in enumerate(deck.slides,1)]
(D/'slide_provenance.json').write_text(json.dumps(manifest,indent=2));(D/'short_examples_metrics.json').write_text((SIM/'metrics.json').read_text());(D/'parameters.json').write_text(json.dumps(cfg,indent=2));h.close()
sd.export(deck,OUT,'v41_partI',datetime.now(ZoneInfo('Europe/Rome')).strftime('%-d %B %Y'))
(OUT/'README.md').write_text('# v41 — Part I only\n\n10 slides: six common-layout calibration/science stages, physical inputs and absolute mapping. Short52.4288ms examples only; no new fits, raw science reconstruction or full-run MC.\n\nSee the versioned source README for definitions and caveats. Numerical arrays remain in '+str(SIM)+'. Expected thermal-only RMS is below one ADC step; explicit microvolt insets and continuous-versus-quantized curves preserve this physical fact.\n\nSubsequent parts are not assembled; the two approved additional data slides remain scheduled.\n')
print('SOURCE',hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
