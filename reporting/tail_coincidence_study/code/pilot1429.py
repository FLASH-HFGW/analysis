"""Single bounded raw pass. Saves sparse features, never complete waveforms."""
from pathlib import Path
import sys,json,time,resource,csv
import numpy as np
R=Path(__file__).resolve().parents[3];O=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'examples'));from analyze_midas_iq_v3 import decode
from algorithms import clusters,coincidences
import midas.file_reader
T=time.perf_counter();FS=5000000;N=1048576000;BIN=50000;W=500;M=['TM010','TM011','TM012'];inv=json.load(open(O/'data/inventory.json'));record=next(r for r in inv['runs'] if r['run']==1429);src=Path(record['raw_path']);assert src.stat().st_size==record['raw_bytes'];sig=np.array([json.load(open(O/'data/frozen_thresholds.json'))['1429'][m]['sigma_Rayleigh_V'] for m in M]);threshold=sig*(np.sqrt(np.pi/2)+7*np.sqrt((4-np.pi)/2));nb=(N+BIN-1)//BIN;sums=np.zeros((3,nb));maxima=np.zeros((3,nb));cnt=np.zeros((3,nb),np.int64);exposure=np.zeros(nb,np.int64);ixs=[[] for _ in M];amps=[[] for _ in M];contexts=[];tail=np.empty((3,0));pending=np.empty(0,np.int64);received=0;events=0;last=None;eor=False;context_left_truncated=0
with midas.file_reader.MidasFile(str(src),use_numpy=True) as reader:
 odb=reader.get_bor_odb_dump().data;adc=odb['Equipment']['NetBox']['Settings'];sc=np.asarray(adc['Channel_range_mV'])*.002/65535;assert int(odb['Runinfo']['Run number'])==1429 and float(adc['Sampling_rate_MS'])*1e6==FS
 for ev in reader:
  if ev.header.event_id==0x8001:eor=True
  if ev.header.event_id!=1:continue
  serial=ev.header.serial_number
  if last is not None and serial!=last+1:raise ValueError('discontinuity: stop pilot, do not join histories')
  last=serial;layout,ch=decode(ev.banks);assert layout=='SPE';size=len(ch[0]);assert all(len(c)==size for c in ch);a=np.array([np.hypot(ch[2*j].astype(float)*sc[2*j],ch[2*j+1].astype(float)*sc[2*j+1]) for j in range(3)]);hits=[]
  cuts=np.r_[0,np.arange(BIN-received%BIN,size,BIN),size];cuts=np.unique(cuts);bins=(received+cuts[:-1])//BIN;exposure[bins]+=np.diff(cuts)
  for j in range(3):
   hit=np.flatnonzero(a[j]>threshold[j]);ixs[j].append(received+hit);amps[j].append(a[j,hit]);hits.extend((received+hit).tolist());cnt[j]+=np.bincount((received+hit)//BIN,minlength=nb);sums[j,bins]+=np.add.reduceat(a[j]*a[j],cuts[:-1]);maxima[j,bins]=np.maximum(maxima[j,bins],np.maximum.reduceat(a[j],cuts[:-1]))
  combined=np.concatenate([tail,a],axis=1);origin=received-tail.shape[1];allhits=np.unique(np.r_[pending,np.asarray(hits,np.int64)]);ready=allhits[allhits<received+size-W];pending=allhits[allhits>=received+size-W]
  for h in ready:
   c=int(h-origin);lo=max(0,c-W);hi=min(combined.shape[1],c+W+1);contexts.append([int(h),*combined[:,c].tolist(),*combined[:,lo:hi].max(1).tolist(),bool(c-W<0)])
  tail=combined[:,-2*W:].copy();received+=size;events+=1
  if events%100==0:print('PILOT1429',events,'elapsed',time.perf_counter()-T,flush=True)
 for h in pending:
  c=int(h-(received-tail.shape[1]));lo=max(0,c-W);contexts.append([int(h),*tail[:,c].tolist(),*tail[:,lo:].max(1).tolist(),True])
assert eor and received==N and events==1000 and exposure.sum()==N
indices=[np.concatenate(x) for x in ixs];amplitudes=[np.concatenate(a) for a in amps];totals=[len(x) for x in indices];assert totals==[1368,232,827],totals
assert src.stat().st_size==record['raw_bytes'] and src.stat().st_mtime_ns==record['raw_mtime_ns']
# Sparse sample times and all grouping scales, including measured proxies of8/10 samples.
features=[];group_rows=[];main=[]
for j,mode in enumerate(M):
 for idx,amp in zip(indices[j],amplitudes[j]):features.append(dict(run=1429,mode=mode,index=int(idx),received_s=idx/FS,amplitude_V=float(amp),T7_V=threshold[j],UTC='unanchored'))
 for gap in sorted(set([0,2,5,8,10,25,50])):
  groups=clusters(indices[j],amplitudes[j],gap)
  for k,g in enumerate(groups):group_rows.append(dict(run=1429,mode=mode,gap_nonexceeding_samples=gap,cluster_id=k,**g))
 main.append(clusters(indices[j],amplitudes[j],[10,8,8][j]))
# Acquisition-index coincidence controls. Cluster peak tuples, not unique events.
peaks0=[np.array([g['peak'] for g in groups]) for groups in main];coinc=[];summary=[];margin=5000;duration=(N-2*margin)/FS;controls=[];shifts=[int(FS*v)+137 for v in [.1,.2,.5,1,2,5,10,20,40,60]];shifts=shifts+[-s for s in shifts]
for us in [1,2,5,10,100]:
 w=int(round(us*FS/1e6));sel=[np.flatnonzero((p>=margin)&(p<N-margin)) for p in peaks0];p=[a[b] for a,b in zip(peaks0,sel)];pair,tri=coincidences(p,w);data={f'{M[a]}--{M[b]}':len(v) for (a,b),v in pair.items()};data['triple']=len(tri)
 for (aa,bb),tuples in pair.items():
  for i,j in tuples:
   ga=main[aa][sel[aa][i]];gb=main[bb][sel[bb][j]];coinc.append(dict(run=1429,window_us=us,kind=f'{M[aa]}--{M[bb]}',peak_a=int(p[aa][i]),peak_b=int(p[bb][j]),peak_c='',separation_us=(int(p[bb][j])-int(p[aa][i]))/5,amplitude_a_V=ga['maximum'],amplitude_b_V=gb['maximum'],amplitude_c_V=''))
 for i,j,k in tri:
  pp=[p[0][i],p[1][j],p[2][k]];coinc.append(dict(run=1429,window_us=us,kind='triple',peak_a=int(pp[0]),peak_b=int(pp[1]),peak_c=int(pp[2]),separation_us=(max(pp)-min(pp))/5,amplitude_a_V=main[0][sel[0][i]]['maximum'],amplitude_b_V=main[1][sel[1][j]]['maximum'],amplitude_c_V=main[2][sel[2][k]]['maximum']))
 ctr={key:[] for key in data}
 for shift in shifts:
  pp=[np.sort((peaks0[j]+[0,shift,-shift][j])%N) for j in range(3)];pp=[a[(a>=margin)&(a<N-margin)] for a in pp];pc,tc=coincidences(pp,w);cc={f'{M[a]}--{M[b]}':len(v) for (a,b),v in pc.items()};cc['triple']=len(tc)
  for key,v in cc.items():ctr[key].append(v);controls.append(dict(window_us=us,kind=key,shift_samples=shift,count=v,exposure_s=duration))
 for key,value in data.items():summary.append(dict(run=1429,window_us=us,kind=key,count=value,rate_Hz=value/duration,exposure_s=duration,time_shift_mean=float(np.mean(ctr[key])),time_shift_median=float(np.median(ctr[key])),time_shift_min=min(ctr[key]),time_shift_max=max(ctr[key]),interpretation='peak-tuple acquisition-domain count; shifts are descriptive, not iid p-values'))
def write(name,rows,fields=None):
 with (O/'tables'/name).open('w') as f:w=csv.DictWriter(f,fieldnames=fields or list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
write('pilot1429_T7_samples.csv',features);write('pilot1429_clusters.csv',group_rows);write('pilot1429_coincidence_summary.csv',summary);write('pilot1429_time_shift_controls.csv',controls);write('pilot1429_coincidences.csv',coinc,fields=['run','window_us','kind','peak_a','peak_b','peak_c','separation_us','amplitude_a_V','amplitude_b_V','amplitude_c_V'])
write('pilot1429_cross_mode_context.csv',[dict(zip(['index','A_TM010_V','A_TM011_V','A_TM012_V','max100us_TM010_V','max100us_TM011_V','max100us_TM012_V','context_truncated'],r)) for r in contexts])
binrows=[]
for factor in [1,10,100]:
 for j,mode in enumerate(M):
  for start in range(0,nb,factor):
   stop=min(nb,start+factor);n=exposure[start:stop].sum();binrows.append(dict(run=1429,mode=mode,nominal_bin_ms=10*factor,start_received_s=start*BIN/FS,exposure_s=n/FS,T7_count=int(cnt[j,start:stop].sum()),RMS_V=float(np.sqrt(sums[j,start:stop].sum()/n)),maximum_V=float(maxima[j,start:stop].max())))
write('pilot1429_binned_statistics.csv',binrows)
np.savez_compressed(O/'data/pilot_1429_bins.npz',counts=cnt,power_sum=sums,maxima=maxima,exposure_samples=exposure,sigma=sig,threshold=threshold)
result={'run':1429,'raw_path':str(src),'compressed_bytes':record['raw_bytes'],'raw_CRC':'Python gzip reader reached normal EOF; member CRC checked','EOR':eor,'events':events,'samples':received,'T7_totals':totals,'matches_saved_totals':True,'main_cluster_counts':[len(x) for x in main],'group_gap_nonexceeding_samples':[10,8,8],'coincidence_windows_us':[1,2,5,10,100],'coincidence_semantics':'all peak tuples satisfying inclusive max-minus-min window; tuples may share clusters','channel_delay_calibrated':False,'UTC_precision_validated':False,'time_shift_controls':20,'edge_margin_samples':margin,'context_halfwidth_samples':W,'future_runs_processed':[],'wall_s':time.perf_counter()-T,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'process_io':Path('/proc/self/io').read_text(),'waveforms_retained':False}
(O/'validation/pilot1429.json').write_text(json.dumps(result,indent=2));print('COMPLETE',json.dumps(result),flush=True)
