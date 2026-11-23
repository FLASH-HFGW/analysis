"""Extract and cross-check archived ODB settings and LOSC records, with no raw reads."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np

from stream_longitudinal import MODES, STUDY, csv_write, open_product, write_json
from iq_acquisition_metadata import extract_coordinates

TABLES = STUDY/'tables/run1670'
VALIDATION = STUDY/'validation/run1670'
ROOTS = Path('/home/mazzitel/flash-data/analysis/autoreco/Run3')
VARS = ('freq RS','power RS','freq Teled Ch1','Vpp Teled Ch1',
        'freq Teled Ch2','Vpp Teled Ch2','freq Pump','power Pump')
LO = ('freq RS','freq Teled Ch1','freq Teled Ch2')
FLAGS = ('onoff RS','onoff Teled Ch1','onoff Teled Ch2','onoff Pump','hasChanged')


def iso(ts):
    return datetime.fromtimestamp(int(ts),timezone.utc).isoformat()


def save(name, rows):
    csv_write(TABLES/f'{name}.csv',list(rows[0]),rows)


def main():
    timeline, config, comparisons, receipt = [], [], [], []
    windows = []
    timestamps = {}
    settings = {}
    for run in (1429,1669,1670,1671):
        with open_product(ROOTS/f'run{run:05d}_iq_v3.1.root') as p:
            obj = p.file
            aux = obj['midas_aux']
            ev = aux['events'][:]
            payload = aux['payload'][:]
            bank = aux['banks'][:]
            snaps = {}
            for label in ('BOR','EOR'):
                a = obj[f'odb/{label}/0']
                blob = a[:].tobytes()
                digest = hashlib.sha256(blob).hexdigest()
                assert digest == a.attrs['sha256']
                event = ev[a.attrs['event_index']]
                assert event['event_id'] == {'BOR':0x8000,'EOR':0x8001}[label]
                odb = json.loads(blob.rstrip(b'\0'))
                ts = int(event['time_unix'])
                timestamps[run,label] = ts
                snapshots = odb['Equipment']['LocalOscill']['Variables']
                snaps[label] = snapshots
                for key in (*VARS,*FLAGS):
                    timeline.append(dict(run=run,snapshot=label,event_utc=iso(ts),
                                         key='/Equipment/LocalOscill/Variables/'+key,
                                         value=snapshots[key],
                                         last_written_utc=iso(snapshots[key+'/key']['last_written'])))
                vna = odb['Equipment']['VNA']['vnaCalib']
                for key in ('freq_mode1','freq_mode2','freq_mode3','Auto_detect','Auto_detect_status'):
                    timeline.append(dict(run=run,snapshot=label,event_utc=iso(ts),
                        key='/Equipment/VNA/vnaCalib/'+key,value=vna[key],
                        last_written_utc=iso(vna[key+'/key']['last_written'])))
                coords = extract_coordinates(odb)
                adc=odb['Equipment']['NetBox']['Settings']
                params=odb['Experiment']['Run Parameters']
                settings[run,label] = {f'NetBox/Settings/{key}':value for key,value in adc.items()
                                       if not key.endswith('/key')}
                settings[run,label].update({f'Run Parameters/{key}':value for key,value in params.items()
                                             if key in ('With_LO','With_TWPA')})
                for mode in MODES:
                    m=coords['modes'][mode]
                    config.append(dict(run=run,snapshot=label,mode=mode,With_LO=params.get('With_LO'),
                        With_TWPA=params.get('With_TWPA'),sample_rate_Hz=coords['fs_hz'],
                        IQ=coords['IQ_convention'],channel_I=m['I_channel_zero_based'],
                        channel_Q=m['Q_channel_zero_based'],range_mV=adc['Channel_range_mV'][m['I_channel_zero_based']],
                        rf_nominal_Hz=m['RF_nominal_VNA_hz'],primary_LO_Hz=m['LO_primary_hz'],
                        secondary_LO_Hz=m['LO_secondary_hz'],IF_primary_Hz=m['IF_primary_hz'],
                        digital_center_Hz=m['center_digital_IQ_hz'],
                        ADC_enabled=adc.get('Channels_enabled',''),
                        VNA_autodetect=odb['Equipment']['VNA']['vnaCalib'].get('Auto_detect')))
                receipt.append(dict(run=run,snapshot=label,sha256=digest,event_utc=iso(ts)))
            losc = bank[bank['name']==b'LOSC']
            assert len(losc)==1
            for item in losc:
                assert item['tid']==10 and item['bytes']==8*len(VARS) and item['offset']>=0
                start=int(item['offset'])
                numbers=np.frombuffer(payload[start:start+int(item['bytes'])].tobytes(),'<f8')
                ts=int(ev[item['event_index']]['time_unix'])
                assert timestamps[run,'BOR']<=ts<=timestamps[run,'EOR']
                for key,v in zip(VARS,numbers):
                    assert v==snaps['BOR'][key]==snaps['EOR'][key]
                    timeline.append(dict(run=run,snapshot='LOSC',event_utc=iso(ts),
                        key='/Equipment/LocalOscill/Variables/'+key,value=v,last_written_utc=''))
            for mode in MODES:
                d=dict(obj[f'statistics/{mode}'].attrs)
                seconds=obj[f'statistics/{mode}'][:]
                assert len(seconds)==len(p.windows)==209
                windows.extend(dict(run=run,mode=mode,second=int(ix/5e6),RMS_V=float(rms))
                               for ix,rms in zip(p.windows['received_index'],seconds['rms_V']))
                comparisons.append(dict(run=run,mode=mode,first_adc_utc=iso(p.time_start),
                    last_adc_utc=iso(p.time_stop-1),RMS_V=d['rms_V'],mean_I_V=d['mean_I_V'],
                    mean_Q_V=-d['mean_Qhardware_V'],var_I_V2=d['var_I_V2'],var_Q_V2=d['var_Q_V2'],
                    cov_I_Q_V2=-d['cov_I_Qhardware_V2'],
                    properness_ratio=np.hypot(d['var_I_V2']-d['var_Q_V2'],2*d['cov_I_Qhardware_V2'])/
                        (d['var_I_V2']+d['var_Q_V2'])))
            if run==1670:
                assert all(timestamps[1669,'EOR']<
                           snaps['BOR'][k+'/key']['last_written']<timestamps[1670,'BOR'] for k in LO)
    changes=[]
    for before,after in (((1669,'EOR'),(1670,'BOR')),((1670,'BOR'),(1670,'EOR')),
                         ((1670,'EOR'),(1671,'BOR'))):
        a,b=settings[before],settings[after]
        for key in sorted(a.keys()|b.keys()):
            if a.get(key)!=b.get(key):
                changes.append(dict(before_run=before[0],before_snapshot=before[1],
                    after_run=after[0],after_snapshot=after[1],
                    key=key,previous=json.dumps(a.get(key)),current=json.dumps(b.get(key))))
    if changes:
        save('digitizer_setting_changes',changes)
    else:
        csv_write(TABLES/'digitizer_setting_changes.csv',
                  ['before_run','before_snapshot','after_run','after_snapshot','key','previous','current'],[])
    save('LO_chronology',timeline)
    save('RF_configuration',config)
    save('ROOT_comparison',comparisons)
    save('ROOT_neighbor_RMS',windows)
    source=STUDY.parent/'run3b_longitudinal/data/LocalOscill_reference.py'
    write_json(VALIDATION/'chronology.json',dict(snapshots=receipt,frequency_write_order=list(LO),
        evidence='SHA256-verified archived BOR/EOR snapshots, one LOSC TID_DOUBLE record/run with the same frequencies',
        controller_reference=str(source.relative_to(STUDY.parents[1])),controller_SHA256=hashlib.sha256(source.read_bytes()).hexdigest(),
        actor_identified=False,in_run_frequency_monitor=False,digitizer_or_selected_flag_changes=changes))
    print([(r['run'],r['snapshot'],r['event_utc']) for r in receipt])
    print([(r['key'],r['last_written_utc']) for r in timeline if r['run']==1670 and r['snapshot']=='BOR' and
                                                      r['key'].rsplit('/',1)[-1] in LO])


if __name__=='__main__':
    main()
