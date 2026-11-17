"""Strict BOR-derived acquisition coordinates; no arbitrary resonance defaults."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
MODES=('TM010','TM011','TM012')
PAIRS={'TM010':(0,1),'TM011':(2,3),'TM012':(4,5)}

def number(value,name,positive=True):
    if isinstance(value,bool):raise ValueError('Boolean instead of '+name)
    x=float(value)
    if not np.isfinite(x) or (positive and x<=0):raise ValueError('Invalid '+name)
    return x

def extract_coordinates(odb,iq_sign=-1,source=None,bor_timestamp=None):
    if iq_sign not in (-1,1):raise ValueError('iq_sign must be +/-1')
    try:
        e=odb['Equipment'];v=e['VNA']['vnaCalib'];lo=e['LocalOscill']['Variables'];adc=e['NetBox']['Settings']
        fs=number(adc['Sampling_rate_MS'],'Sampling_rate_MS')*1e6
        ranges=np.asarray(adc['Channel_range_mV'],float)/1000
        if len(ranges)<6 or not np.isfinite(ranges).all() or np.any(ranges<=0):raise ValueError('Invalid ADC channel ranges')
        first=number(lo['freq RS'],'freq RS');second=[0.,number(lo['freq Teled Ch1'],'freq Teled Ch1'),number(lo['freq Teled Ch2'],'freq Teled Ch2')]
        rf=[number(v['freq_mode'+str(i)],'freq_mode'+str(i)) for i in (1,2,3)]
    except (KeyError,TypeError,ValueError) as ex:raise ValueError('Missing/invalid BOR coordinate metadata: '+str(ex)) from ex
    original={'VNA_vnaCalib':{k:x for k,x in v.items() if k.startswith('freq_mode') or k in ['Auto_detect','Auto_detect_status']},'LocalOscill_Variables':lo,'NetBox_Settings':{k:x for k,x in adc.items() if k.startswith(('Sampling_rate_MS','Channel_range_mV','Channels_enabled'))}}
    raw=json.dumps(original,sort_keys=True,ensure_ascii=False)
    modes={}
    for i,m in enumerate(MODES):
        ci,cq=PAIRS[m]
        if ranges[ci]!=ranges[cq]:raise ValueError('Unequal I/Q ADC ranges for '+m)
        final=rf[i]-first-second[i]
        modes[m]={'RF_nominal_VNA_hz':rf[i],'LO_primary_hz':first,'LO_secondary_hz':second[i],'IF_primary_hz':rf[i]-first,'IF_final_analog_main_hz':final,'center_digital_IQ_hz':-iq_sign*final,'I_channel_zero_based':ci,'Q_channel_zero_based':cq,'ADC_peak_V':float(ranges[ci]),'ADC_V_per_count':float(2*ranges[ci]/65535),'RF_reference_provenance':'/Equipment/VNA/vnaCalib/freq_mode'+str(i+1),'LO_secondary_provenance':'no secondary mixer' if i==0 else '/Equipment/LocalOscill/Variables/freq Teled Ch'+str(i)}
    out={'schema':'iq-acquisition-coordinates-v1','source':str(source) if source else 'synthetic ODB fixture','BOR_timestamp_unix':bor_timestamp,'fs_hz':fs,'ADC_peak_V_by_channel':ranges.tolist(),'ADC_count_denominator':65535,'iq_sign':iq_sign,'IQ_convention':'I-iQhardware' if iq_sign==-1 else 'I+iQhardware','frequency_convention':'numpy forward FFT exp(-i omega t); main calibrated upper-RF branch; conjugation reverses sign','RF_reference_kind':'nominal VNA value recorded in BOR; not an in-run resonance fit/drift measurement','original_selected_ODB_JSON':raw,'selected_ODB_sha256':hashlib.sha256(raw.encode()).hexdigest(),'hash_scope':'selected acquisition/VNA/LO fields, not full MIDAS','modes':modes,'provenance':{'sampling':'/Equipment/NetBox/Settings/Sampling_rate_MS (MS/s)','ADC_range':'/Equipment/NetBox/Settings/Channel_range_mV (mV peak)','LO_primary':'/Equipment/LocalOscill/Variables/freq RS (Hz)','iq_sign':'explicit analysis convention validated against existing coherent-tone audit'}}
    if source:
        st=Path(source).stat();out['source_size_bytes']=st.st_size;out['source_mtime_ns']=st.st_mtime_ns
    return out

def read_bor_coordinates(path,iq_sign=-1):
    sys.path.insert(0,'/cvmfs/sft-flash.infn.it/package/midas/python')
    import midas.file_reader
    r=midas.file_reader.MidasFile(str(path),use_numpy=True)
    try:
        odb=r.get_bor_odb_dump().data
        return extract_coordinates(odb,iq_sign,path,int(r.event.header.timestamp))
    finally:r.file.close()

def resonance_centers(metadata,offsets=(-500000,-250000,-100000,0,100000,250000,500000),width=50000):
    fs=metadata['fs_hz'];result={}
    for m in MODES:
        center=metadata['modes'][m]['center_digital_IQ_hz']
        if any(abs(center+o)+width/2>=fs/2 for o in offsets):raise ValueError('Resonance bank outside Nyquist: '+m)
        result[m]=[float(center+o) for o in offsets]
    return result
