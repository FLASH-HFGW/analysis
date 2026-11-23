"""Rebuild the checkpoint presentation from compact products; no raw access."""
from pathlib import Path
import sys,json,csv,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parents[1];sys.path.insert(0,str(O.parents[0]));from slide_deck import Deck,export
M=['TM010','TM011','TM012'];R=[680,1429,1529,1629,1729];C=['#777777','#007F86','#7657A6','#D98726','#B84662']
read=lambda n:list(csv.DictReader(open(O/'tables'/n)))
inv=json.load(open(O/'data/inventory.json'));frozen=json.load(open(O/'data/frozen_thresholds.json'))
(O/'figures').mkdir(exist_ok=True);D=Deck()
def text(title,subtitle,lines,source='Inventory and checkpoint validation'):
 s=D.new(title,subtitle,source=source,notes=' '.join(lines));D.bullets(s,.65,1.85,12,lines,size=20,gap=.22)
def axes(rows=1):
 fig,ax=plt.subplots(rows,3,figsize=(15,5.2),squeeze=False,layout='constrained')
 for j,m in enumerate(M):ax[0,j].set_title(m)
 for a in ax.flat:a.grid(alpha=.2)
 return fig,ax
def save(fig,name,title,subtitle,notes):
 p=O/'figures'/(name+'.png');fig.savefig(p,dpi=155);plt.close(fig)
 s=D.new(title,subtitle,source='tables/; code/report.py; ADC-plane quantities; no RF corrections',notes=notes);D.image(s,.5,1.72,12.3,4.95,p)
text('FLASH: tails, persistence and coincidences','Five-run inventory; validated streaming pilot on Run 1429',[
 'Historical reference: Run 680 without TWPA. Run3-B samples: 1429, 1529, 1629 and 1729.',
 'Only Run 1429 has newly extracted exceedance timing. Other raw passes are held at the timing / I/O checkpoint.',
 'All levels are measured at the ADC plane. No gain correction, filtering or production changes.'])
text('Coverage and timing qualification','All five products available; raw integrity has different validation depths',[
 'Each run: 1,048,576,000 samples per mode; 209.7152 s; 5 MHz. ADC range ±2 V; conversion 4/65535 V/count.',
 'Complex convention: I − iQ(hardware); channel pairs 0/1, 2/3, 4/5. Archived serial continuity and shared indices checked.',
 'Run 1429 raw reached CRC-checked EOF and EOR. Other raws: gzip headers only; ROOT schema, metadata and BOR/EOR checked.',
 'Run3 PPS has an approximately 2 s gap and 4,999,999-sample intervals. UTC anchoring and channel delays remain uncalibrated.'])
fig,ax=axes()
for j,m in enumerate(M):
 vals=[r['fullrun_attributes'][m]['rms_V']*1000 for r in inv['runs']];ax[0,j].bar(list(map(str,R)),vals,color=C);ax[0,j].set_ylabel('Full-run RMS (mV)')
save(fig,'RMS_five_runs','Full-run RMS across the five runs','Historical Run 680 is separate from the four-run TWPA campaign.','Archived full-run statistics include residual samples beyond the 209 complete seconds; no causal attribution.')
fig,ax=axes()
for j,m in enumerate(M):
 y=[frozen[str(r)][m]['T7_exact_count'] for r in [680,1429]];ax[0,j].bar(['680 archived','1429 verified'],y,color=C[:2]);ax[0,j].set_ylabel('T7 sample count / full run')
save(fig,'T7_totals','Exact T7 sample counts','Runs 1529 / 1629 / 1729: timing and exact threshold extraction pending.','T7 is mean plus seven amplitude standard deviations of the fitted Rayleigh distribution; counts are not independent events.')
text('Statistical baseline and interpretation','Frozen v50 amplitude thresholds; no independent-sample significance',[
 'Tn = σR [√(π/2) + n √((4−π)/2)], n = 3, 5, 7; the raw uncentered amplitude is tested.',
 'For a zero-mean proper Gaussian marginal: E[count] = N exp[−Tn²/(2σR²)]. Temporal coloring changes count variance and clustering.',
 'Measured mean, quadrature covariance, time-dependent variance and ADC quantization can change the marginal tail model.',
 'A large T7 count alone does not distinguish Gaussian variance modulation, spectral interference or nonlinear readout.'])
b=read('pilot1429_1s.csv');fig,ax=axes(3)
for j,m in enumerate(M):
 q=[r for r in b if r['mode']==m];t=[float(r['start_received_s']) for r in q];rate=[int(r['T7_count'])/float(r['exposure_s']) for r in q]
 ax[0,j].plot(t,[1000*float(r['RMS_V']) for r in q]);ax[0,j].set_ylabel('RMS (mV)')
 for k in [1,2]:ax[k,j].plot(t,rate);ax[k,j].set_ylabel('T7 samples/s' if k==1 else 'Singleton groups/s');ax[k,j].set_xlabel('Received sample time (s)')
save(fig,'pilot_timeline','Run 1429: RMS and tail timing','One-second bins; exposure-corrected final partial bin.','All tested T7 clusters are singletons, so group and sample count rates coincide; not physical-event rates. Acquisition-domain time only.')
g=read('pilot1429_cluster_sensitivity.csv');fig,ax=axes()
for j,m in enumerate(M):
 q=[r for r in g if r['mode']==m];ax[0,j].plot([float(r['gap_nonexceeding_us']) for r in q],[int(r['groups']) for r in q],'o-');ax[0,j].set_xlabel('Allowed non-exceeding gap (µs)');ax[0,j].set_ylabel('T7 groups')
save(fig,'gap_sensitivity','Clustering is insensitive over the tested gaps','0–50 non-exceeding samples (0–10 µs); boundaries handled in sample-index space.','Groups have multiplicity one and duration one sample (0.2 µs), not the physical pulse duration. Default gaps 10/8/8 samples use prior correlation-scale proxies, not an independence criterion.')
co=read('pilot1429_coincidence_summary.csv');fig,ax=axes();pairs=['TM010--TM011','TM010--TM012','TM011--TM012']
for j,pair in enumerate(pairs):
 q=[r for r in co if r['kind']==pair];x=np.array([float(r['window_us']) for r in q]);a=ax[0,j];a.set_title(pair);a.fill_between(x,[float(r['time_shift_min']) for r in q],[float(r['time_shift_max']) for r in q],alpha=.2,label='20-shift range');a.plot(x,[float(r['time_shift_mean']) for r in q],'o-',label='Shift mean');a.plot(x,[int(r['count']) for r in q],'s-',label='Observed');a.set_xscale('log');a.set_xlabel('Peak coincidence window (µs)');a.set_ylabel('Peak tuples');a.legend(fontsize=8)
save(fig,'coincidence_controls','Run 1429: double and triple coincidences','No pairs or triples through 10 µs; one TM010–TM012 pair at 100 µs.','The observed pair has separation 75.2 µs. At 100 µs the corresponding shift mean is 1.1 (range 0–3). All triple counts are zero. Shifts are descriptive controls, not a stationary null p-value; protect 1 ms edges, exposure 209.7132 s.')
fig,ax=axes()
for j,pair in enumerate(pairs):
 a=ax[0,j];a.set_title(pair);a.set_xlim(0,209.7152);a.set_ylim(-.3,1.3);a.set_yticks([1],['100 µs pairs']);a.set_xlabel('Received sample time (s)')
 if j==1:a.vlines(674054353/5e6,0,1,color=C[1]);a.text(.05,.8,'One pair; Δt = 75.2 µs',transform=a.transAxes)
 else:a.text(.2,.5,'No observed pairs',transform=a.transAxes)
save(fig,'coincidence_timeline','Coincidence timelines in acquisition coordinates','All three-mode coincidences: none at every tested window.','Not UTC or cavity-time coincidences. Windows at 1–2 µs are comparable to correlation proxies and not calibrated relative to channel group delays.')
ctx=read('pilot1429_conditional_other_modes.csv');fig,ax=axes()
for j,m in enumerate(M):
 q=[r for r in ctx if r['seed_mode']==m];x=np.arange(2);a=ax[0,j];a.bar(x-.18,[float(r['median_other_A_over_sigma']) for r in q],.36,label='At seed');a.bar(x+.18,[float(r['median_other_max100us_over_sigma']) for r in q],.36,label='Maximum ±100 µs');a.set_xticks(x,[r['other_mode'] for r in q]);a.set_ylabel('Median amplitude / σR');a.legend(fontsize=8)
save(fig,'conditional_amplitudes','Other-mode amplitudes around T7 samples','Columns identify the seed mode; comparison includes subthreshold amplitudes.','Conditional medians are descriptive. Window maxima have a different selection population from instantaneous amplitudes; no joint-noise null or calibrated channel delays.')
sp=read('spectral_focus_curves.csv');fig,ax=axes()
for j,m in enumerate(M):
 for run,c in zip(R,C):
  q=[r for r in sp if r['mode']==m and int(r['run'])==run];ax[0,j].plot([float(r['frequency_hz'])/1000 for r in q],[float(r['mean_local_ratio']) for r in q],label=str(run),color=c)
 ax[0,j].set_xlabel('Electronic frequency (kHz)');ax[0,j].set_ylabel('Mean PSD / local median');ax[0,j].legend(fontsize=8)
save(fig,'spectral_focus','Archived spectral structures across five runs','100 Hz products; same local-background diagnostic in every run.','Ratio to 201-bin median background; not a coherence measurement. TM011 region is a nominal IF region, not an established spectral line. No PSD correction.')
p=read('spectral_persistence.csv');fig,ax=axes()
for j,m in enumerate(M):
 q=[r for r in p if r['mode']==m];ax[0,j].bar(list(map(str,R)),[float(r['occupancy_ratio_gt3']) for r in q],color=C);ax[0,j].set_ylim(0,1.05);ax[0,j].set_ylabel('Occupancy: local PSD ratio > 3')
save(fig,'spectral_occupancy','TM012: persistence changes across runs','−492750.5 Hz bin: 208 / 209 seconds in 1429, 1529 and 1629; 0 / 209 in 1729.','Mean local ratios 3.723, 3.697 and 3.631. Run 680 has no corresponding enhancement. Occupancy uses a selected bin in ±1 kHz; 100 Hz averaging limits narrow-line frequency precision. Temporal tail association not established.')
temps=read('temperatures.csv')
for name,channels,labels in [('temperatures',['Temp_AVS:15:T4','Temp_AVS:13:T2','Temp_Mercury:4:Diode_4K_T K'],['Cavity mapping','TWPA-stage mapping','4 K stage proxy']),('mixing_chamber',['Temp_AVS:16:T5','Temp_AVS:17:T6','Temp_AVS:12:T1'],['MC plate CMN143','MC plate CMN130','50 mK plate'])]:
 fig,ax=axes()
 for j,(ch,label) in enumerate(zip(channels,labels)):
  a=ax[0,j];a.set_title(label)
  for run,c in zip(R,C):
   q=[r for r in temps if int(r['run'])==run and r['channel']==ch and r['sensor_value_valid']=='True' and r['within_ADC_header_coverage']=='True'];a.plot([float(r['time_from_first_ADC_header_s']) for r in q],[float(r['value_K']) for r in q],'o-',label=str(run),color=c,markersize=3)
  a.set_xlabel('Time from first ADC header (s)');a.set_ylabel('Temperature (K)');a.legend(fontsize=7)
 save(fig,name,'Archived cryogenic temperatures' if name=='temperatures' else 'Mixing-chamber and plate temperatures','Original sensor values converted from documented K / mK units; invalid zeros excluded.','Sensor roles use docs/v47/temperature_mapping.md; Run3 wiring not independently verified. 4 K sensor is a stage proxy, not a HEMT junction thermometer. Approximate header-relative timing, no microsecond alignment.')
text('Temperature associations: descriptive only','Tables preserve levels, first differences, sample counts and timing qualifications',[
 'Within 1429: archived thermal samples compared to RMS and T7 rates over approximate ±10 s windows; serial/header latency remains uncalibrated.',
 'Across Run3-B: only four run medians and three first differences. Run 680 is excluded from campaign correlations.',
 'Slow-control autocorrelation, shared drifts and unequal run spacings prohibit causal or significance claims.',
 'Tail/cluster versus temperature across all four TWPA runs remains pending the raw extraction checkpoint.'])
text('Validated small null-model pilot','Proper complex Gaussian, archived coarse PSD, measured mean and ADC quantization',[
 '24 independent records × 262,144 samples per mode (1.258 s total). Variance errors <0.06%; median coarse-PSD errors <0.64%.',
 'Properness magnitude <0.0011. This pilot does not reproduce the measured improper I/Q covariance or full-run T7 exposure.',
 'Next controls: match covariance / pseudo-spectrum, slow variance modulation and persistent-line components separately.',
 'No full-length tail, cluster or cross-mode significance is claimed from these short periodic records.'])
text('Checkpoint: validated pilot, expansion held','Do not process the other raw runs before reviewing timing and I/O',[
 'Run 1429: 9.31 GB compressed; 159.8 s wall time; peak RSS 260.4 MiB; exact totals 1368 / 232 / 827.',
 'Three additional Run3-B raws require 27.98 GB sequential reading; a new 680 pass adds 12.13 GB. No waveform cache is needed.',
 'Review PPS interpretation and channel-delay metadata before physical coincidence claims. Sample-index diagnostics remain usable.',
 'Next: authorize / schedule remaining streaming passes, then compare tail rates and spectral persistence across the campaign.'])
export(D,O/'presentation',version='tail_coincidence_checkpoint',prepared='23 November 2026')
md=O/'presentation/slides_en.md';md.write_text(md.read_text().replace('8 November 2026','23 November 2026').replace('Acquisition: 24–25 July 2026.','Acquisition: five selected runs; timestamps in tables/inventory.csv.'))
print('Report slides:',len(D.slides))
