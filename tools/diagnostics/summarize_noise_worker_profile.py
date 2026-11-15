from pathlib import Path
import json,h5py,numpy as np,pstats
P=Path('/home/mazzitel/HFGW/analysis-work/Run2/diagnostics/worker_profile_20261115');names=('profile_1workers','profile_3workers','timing_3workers');S={n:json.loads((P/n/'instrumentation.json').read_text()) for n in names};T={}
for n in names:
 with h5py.File(P/n/'run00680_noise_v2.h5') as h:
  T[n]={k:{v:float(h[f'summary/performance/timings/{k}/{v}'][()]) for v in ('wall_s','cpu_s')} for k in ('pass1','pass2','plots','total')};assert h['summary/samples'][()]==52428800
with h5py.File(P/names[0]/'run00680_noise_v2.h5') as ref:
 for n in names[1:]:
  with h5py.File(P/n/'run00680_noise_v2.h5') as h:
   for mode in ('TM010','TM011','TM012'):
    for k in ('noise_counts','phase_counts','iq_counts','samples_above_7sigma'):
     key=f'modes/{mode}/{k}';assert np.array_equal(ref[key][()],h[key][()]),(n,key)
threadfiles=list((P/'profile_3workers').glob('worker_*.pstats'));assert len(threadfiles)==3
calls=0
for f in threadfiles:
 st=pstats.Stats(str(f))
 for (fn,line,name),v in st.stats.items():
  if name=='process_second_mode':calls+=v[1]
assert calls==150,calls
sc1=S[names[0]]['scopes'];sc3=S[names[1]]['scopes'];scc=S[names[2]]['scopes'];t1,t3,tc=(T[n] for n in names)
def row(label,scope,field,meaning):return [label,f'{sc1[scope][field]:.2f}',f'{sc3[scope][field]:.2f}',meaning]
rows=[row('Filtered bands · serial wall','filtered_bands.serial','wall_s',f"{100*sc3['filtered_bands.serial']['wall_s']/t3['pass2']['wall_s']:.1f}% of 3-worker pass2"),row('FIR processing · nested wall','BandFilter.process','wall_s','Inside serial bands'),['FFT+IFFT · nested wall',f"{sum(sc1[k]['wall_s'] for k in ('band_fft','band_ifft')):.2f}",f"{sum(sc3[k]['wall_s'] for k in ('band_fft','band_ifft')):.2f}",'Inside FIR processing'],row('Oscillators · nested wall','oscillator','wall_s','Inside FIR processing'),['Mode workers · CPU sum',f"{sum(v['thread_cpu_s'] for k,v in sc1.items() if k.startswith('process_second_mode:')):.2f}",f"{sum(v['thread_cpu_s'] for k,v in sc3.items() if k.startswith('process_second_mode:')):.2f}",'Parallel part; sum of thread CPU'],row('RunStatistics · nested CPU','RunStatistics.update','thread_cpu_s','Inside mode workers')]
runrows=[]
for label,n,w in [('cProfile · 1 worker',names[0],1),('cProfile · 3 workers',names[1],3),('Timers only · 3 workers',names[2],3)]:
 t=T[n];ratio=t['pass2']['cpu_s']/t['pass2']['wall_s'];runrows.append([label,f"{t['pass1']['wall_s']:.2f}",f"{t['pass2']['wall_s']:.2f}",f'{ratio:.3f}',f'{100*ratio/w:.1f}%'])
fraction=scc['filtered_bands.serial']['wall_s']/tc['pass2']['wall_s'];fft=sum(scc[k]['wall_s'] for k in ('band_fft','band_ifft'))
summary=dict(scope_rows=rows,run_rows=runrows,conclusion=f"The three workers do execute mode tasks; the dominant bank of 27 FIR filters stays serial. Without cProfile, it still takes {scc['filtered_bands.serial']['wall_s']:.1f}/{tc['pass2']['wall_s']:.1f} s ({100*fraction:.1f}%) of pass2. Increasing only mode_workers leaves this cost in place.",next_steps='Priority: optimize the serial filter bank (27 FIR per SPEC; full-rate FFT/IFFT before keeping 1/20 samples). Benchmark decimating/polyphase or batched filtering; preserve continuous FIR state and exact decimation grid.\nThen distribute independent work with safe oscillator/kernel caches. --h5-only still renders and deletes figures, but its ≈13 s/full run is below 0.4%: it cannot explain the hour.\nControl without cProfile confirms the same hotspot; VM timing varies. These are local profiling measurements, not new HPC production timings.',timings=T,instrumentation=S,worker_profile_files=[f.name for f in threadfiles],worker_profiled_task_calls=calls,scientific_checks='Amplitude, phase and IQ histograms and7sigma counts identical across all three 50-SPEC runs',cprofile_off_serial_fraction=fraction,cprofile_off_fft_wall_s=fft)
(P/'summary.json').write_text(json.dumps(summary,indent=2))
lines=['# Worker-aware noise reconstruction profile','','50 SPEC of run680 =52,428,800 samples/mode =10.48576s acquired. Frozen benchmark sources. One local VM; affinity is guest CPUs[0] or[0,1,2], not a claim about hypervisor physical cores. OMP/BLAS threads=1. Main and all3 workers have independent cProfile outputs plus nested wall/thread-CPU timers.','',summary['conclusion'],'','## Measurements','', '| Run | Pass1 wall s | Pass2 wall s | Pass2 CPU/wall | Per-worker CPU efficiency |','|---|---:|---:|---:|---:|']
lines+=['| '+' | '.join(v)+' |' for v in runrows]
lines+=['','Nested times must not be added: FFT/oscillators are inside FIR, inside filtered-band update. Worker wall durations overlap; worker CPU sums are reported explicitly. The control run without cProfile preserves the serial hotspot. A single sequential pair cannot isolate profiler overhead from VM timing variation.','','## Checked outputs','','All3 worker profiles found,150 mode tasks profiled. All three runs have exactly identical amplitude/phase/IQ histograms and7sigma counts.','','## Code locations and next work','','`analyze_midas_iq_noise.py:495–502`: mode futures complete before serial `band_checks.update`. `FilteredBandChecks.update` loops9 frequency offsets×3 modes. `BandFilter.process` computes full FFT and IFFT before selecting decimated output.50 SPEC produce1,350 FIR calls and2,701 FFT/IFFT calls including the cached kernel initialization.','',''+summary['next_steps'],'','Profiles and source hashes are evidence; existing production sources/results were not modified. The ADC normalization is intentionally the frozen benchmark normalization in these timing-only runs.']
(P/'README.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(serial_fraction_control=fraction,FFT_control_s=fft,run_rows=runrows,worker_task_calls=calls),indent=2))
