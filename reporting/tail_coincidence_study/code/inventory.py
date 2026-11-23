from pathlib import Path
import sys,json,csv,hashlib,time
import numpy as np,uproot
R=Path(__file__).resolve().parents[3];O=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'examples'));from iq_products import open_product,json_value
runs=[680,1429,1529,1629,1729];rows=[];temps=[];t=time.perf_counter()
roles={'Temp_AVS:11':'still (documented mapping)','Temp_AVS:12':'50 mK plate (documented mapping)','Temp_AVS:13':'TWPA stage (documented mapping)','Temp_AVS:14':'noise source (documented mapping)','Temp_AVS:15':'RF cavity (documented mapping)','Temp_AVS:16':'mixing-chamber plate CMN143 (documented mapping)','Temp_AVS:17':'mixing-chamber plate CMN130 (documented mapping)','Temp_Mercury:4':'4 K plate; HEMT-stage proxy, not HEMT case','Temp_Mercury:2':'50 K plate','Temp_Mercury:8':'MC diode; zero readings invalid','Temp_Mercury:12':'magnet','Temp_Mercury:10':'heat switch'}
for run in runs:
 raw=Path(f'/home/mazzitel/flash-data/data/LNF/run{run:05d}.mid.gz');root=(R/'comparison/root-pilot/inputs'/f'run{run:05d}_iq_v3.1.root') if run in [680,1429] else Path(f'/home/mazzitel/flash-data/analysis/autoreco/Run3/run{run:05d}_iq_v3.1.root');row={'run':run,'raw_path':str(raw),'ROOT_path':str(root),'raw_available':raw.is_file(),'ROOT_available':root.is_file()}
 if not raw.is_file() or not root.is_file():row['status']='missing';rows.append(row);continue
 stat=raw.stat();row.update(raw_bytes=stat.st_size,raw_mtime_ns=stat.st_mtime_ns,ROOT_bytes=root.stat().st_size)
 with raw.open('rb') as f:head=f.read(10)
 assert head[:3]==b'\x1f\x8b\x08';row['raw_integrity']='gzip magic/header checked; full CRC/EOF not yet verified'
 with open_product(root) as p:
  f=p.file;meta=p.metadata;quality=dict(f['quality'].attrs);adc=f['timing/digitizer_events'][:];pps=f['timing/pps'][:];bor={}
  for tag in ['BOR','EOR']:
   a=f[f'odb/{tag}/0'];blob=a[:].tobytes();assert hashlib.sha256(blob).hexdigest()==a.attrs['sha256'];bor[tag]=json.loads(blob.rstrip(b'\0'))
  assert int(meta['run_number'])==run and quality['saw_eor'] and np.all(np.diff(adc['serial'])==1);assert int(adc['samples'].sum())==quality['received_samples'];pairs=json.loads(meta['pairs_json']);assert pairs=={'TM010':[0,1],'TM011':[2,3],'TM012':[4,5]};assert meta['iq_convention']=='I-iQhardware';sc=json.loads(meta['bor_settings_json']);lo=json.loads(meta['bor_lo_json']);assert sc['Channel_range_mV'][:6]==[2000]*6 and p.fs==5e6
  full={m:dict(f['statistics/'+m].attrs) for m in p.modes};w=p.windows;assert np.all(np.diff(w['received_index'])==5000000);pd=np.diff(pps['received_index']);row.update(status='metadata_valid',ROOT_integrity='schema readable; BOR/EOR hashes verified; timing/statistics/INPT branches read; not a full-file checksum',samples=int(quality['received_samples']),duration_s=quality['received_samples']/p.fs,fs_hz=p.fs,ADC_V_per_count=4/65535,mapping=pairs,IQ_convention=meta['iq_convention'],layout=meta['midas_layout'],serial_gaps=0,utc_quality=f['timing'].attrs['utc_quality'],PPS_source=f['timing'].attrs['pps_source'],PPS_count=len(pps),PPS_intervals={str(k):int(v) for k,v in zip(*np.unique(pd,return_counts=True))},within_file_mode_index_alignment=True,channel_delay_calibration='not available',start_unix=p.time_start,stop_header_unix=p.time_stop,TWPA_flag=bor['BOR'].get('Experiment',{}).get('Run Parameters',{}).get('With_TWPA'),pump_on=lo.get('onoff Pump'),pump_frequency_hz=lo.get('freq Pump'),pump_power_setting=lo.get('power Pump'),fullrun_attributes=full,software_commit=meta['software_commit'])
  count=0
  for name,unit,ts,vs in p.temperatures():
   prefix=':'.join(name.split(':')[:2]);role=roles.get(prefix,'role not established');valid=np.isfinite(vs)&(vs>0);count+=int(valid.sum())
   for ts0,v,good in zip(ts,vs,valid):temps.append(dict(run=run,channel=name,documented_role=role,role_mapping_source='docs/v47/temperature_mapping.md; matching labels/schema, Run3 wiring not independently verified',unit=unit,time_unix=int(ts0),time_from_first_ADC_header_s=float(ts0-p.time_start),original_value=float(v),value_K=float(v)*(1e-3 if unit=='mK' else 1),sensor_value_valid=bool(good),within_ADC_header_coverage=bool(p.time_start<=ts0<p.time_stop)))
  row['positive_finite_temperature_readings']=count
 rows.append(row)
(O/'data/inventory.json').write_text(json.dumps(json_value({'runs':rows,'elapsed_s':time.perf_counter()-t,'full_raw_bytes':sum(r.get('raw_bytes',0) for r in rows),'pilot_raw_bytes':next(r['raw_bytes'] for r in rows if r['run']==1429),'scope':'inventory only; no raw decompression, science extraction or substitutions'}),indent=2))
with (O/'tables/temperatures.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(temps[0]));w.writeheader();w.writerows(temps)
fields=['run','status','raw_available','ROOT_available','raw_bytes','ROOT_bytes','samples','duration_s','serial_gaps','PPS_source','PPS_count','utc_quality','pump_on','pump_frequency_hz','TWPA_flag','positive_finite_temperature_readings']
with (O/'tables/inventory.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
print([(r['run'],r['status'],r.get('PPS_intervals')) for r in rows]);print('RAW TOTAL',sum(r.get('raw_bytes',0) for r in rows))
