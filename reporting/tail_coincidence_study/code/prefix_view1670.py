"""Fine I/Q display for the same v50 prefix; no whole-run reread."""
import json
from pathlib import Path
import time

import numpy as np

from diagnose1670 import PREFIX, MODES, TABLES, STUDY, SCALE, save
from stream_longitudinal import decode, MidasFile, proc_io


def main():
    first=proc_io()
    started=time.monotonic()
    raw='/home/mazzitel/flash-data/data/LNF/run01670.mid.gz'
    hist=np.zeros((3,256,256),dtype=np.int64)
    n=0
    events=0
    with MidasFile(raw,use_numpy=True) as reader:
        assert int(reader.get_bor_odb_dump().data['Runinfo']['Run number'])==1670
        for ev in reader:
            if ev.header.event_id!=1:
                continue
            layout,ch=decode(ev.banks)
            assert layout=='SPE'
            take=min(len(ch[0]),PREFIX-n)
            if events:
                assert ev.header.serial_number==previous+1
            previous=ev.header.serial_number
            for j in range(3):
                idx=np.floor(ch[2*j][:take]*SCALE/0.001+128).astype(np.int32)
                qdx=np.floor(-ch[2*j+1][:take].astype(np.int32)*SCALE/0.001+128).astype(np.int32)
                good=(idx>=0)&(idx<256)&(qdx>=0)&(qdx<256)
                hist[j]+=np.bincount(256*idx[good]+qdx[good],minlength=256**2).reshape(256,256)
            n+=take
            events+=1
            if n==PREFIX:
                break
    assert n==PREFIX and events==5
    rows=[]
    for j,mode in enumerate(MODES):
        for i,q in np.argwhere(hist[j]):
            rows.append(dict(mode=mode,I_mV=i-127.5,Q_mV=q-127.5,count=int(hist[j,i,q])))
    save('prefix_IQ',rows)
    end=proc_io()
    dest=STUDY/'validation/run1670/prefix_view.json'
    dest.write_text(json.dumps(dict(samples=n,events=events,raw_scope='first five ADC events, no full pass',
        process_io={k:end[k]-first[k] for k in end},wall_s=time.monotonic()-started,
        outside_128mV=[int(n-m.sum()) for m in hist]),indent=2)+'\n')


if __name__=='__main__':
    main()
