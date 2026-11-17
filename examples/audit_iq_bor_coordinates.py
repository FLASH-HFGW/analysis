"""Read BOR only for a campaign; never reconstruct SPEC or assert physical drift."""
from pathlib import Path
import argparse,collections,json
from concurrent.futures import ThreadPoolExecutor
from iq_acquisition_metadata import read_bor_coordinates,MODES
from iq_noise_io import save_results_h5

def configuration_states(records):
    """Summarize all selected original VNA controls and LO variables, excluding ODB key bookkeeping."""
    blocks=[json.loads(r['original_selected_ODB_JSON']) for r in records]
    result={}
    for block in ['VNA_vnaCalib','LocalOscill_Variables']:
        keys=sorted(set().union(*(set(r[block]) for r in blocks)))
        result[block]={key:[json.loads(value) for value in sorted(set(json.dumps(r[block].get(key),sort_keys=True) for r in blocks))] for key in keys if '/key' not in key}
    result['scope']='Selected VNA reference/control fields and all LocalOscill variables; bookkeeping timestamps excluded. Recorded state stability is not a physical resonance-drift measurement.'
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--raw-dir',type=Path,required=True);p.add_argument('--first',type=int,default=680);p.add_argument('--last',type=int,default=939);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    paths=[a.raw_dir/f'run{i:05d}.mid.gz' for i in range(a.first,a.last+1)]
    with ThreadPoolExecutor(max_workers=4) as pool:records=list(pool.map(read_bor_coordinates,paths))
    fields=['RF_nominal_VNA_hz','LO_primary_hz','LO_secondary_hz','center_digital_IQ_hz'];states={}
    for m in MODES:
        states[m]={k:sorted(set(r['modes'][m][k] for r in records)) for k in fields}
    states['sampling_hz']=sorted(set(r['fs_hz'] for r in records));states['ADC_peak_V_by_channel']=sorted(set(tuple(r['ADC_peak_V_by_channel']) for r in records))
    summary={'runs':len(records),'first':a.first,'last':a.last,'BOR_only':True,'SPEC_events_read':0,'distinct_states':states,'interpretation':'Changes, if present, are changes of recorded nominal references/settings. They are not measured physical resonance drift.'}
    save_results_h5(a.output,{'schema_version':1,'product_version':'acquisition-metadata-audit-v1','summary':summary,'acquisition_metadata':{f'run{i:05d}':r for i,r in zip(range(a.first,a.last+1),records)}})
    a.output.with_suffix('.configuration_states.json').write_text(json.dumps(configuration_states(records),indent=2)+'\n')
    a.output.with_suffix('.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
