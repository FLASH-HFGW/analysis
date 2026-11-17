"""Quarantine ambiguous archived PSD coordinates; never repair signs by power matching.

Input products are immutable. Eight signed overlap windows in all three modes
are used as an audit, not as a fitted hardware response or a sign correction.
"""
from pathlib import Path
import argparse, copy, csv, json, shutil
import h5py
import numpy as np
from resonance_reference_and_campaign import MODES, OFFSETS, WORK, correlations, sha, read_rows


def reflection_candidates(archived, historical):
    """Return clear reflection diagnostics; DC excluded due different mean removal."""
    indices = [0,1,2,3,5,6,7,8]
    direct = np.sqrt(np.mean((archived[:,indices]/historical[:,indices]-1)**2,axis=1))
    reflected = np.sqrt(np.mean((archived[:,indices]/historical[:,::-1][:,indices]-1)**2,axis=1))
    # Diagnostic only. No axis is flipped even if this test is positive.
    candidate = (reflected < direct*.4) & (direct > .0008)
    return direct, reflected, candidate


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    a.output.mkdir(parents=True)
    result=json.loads((a.input/'results.json').read_text());runs=np.array(result['runs'])
    masks=[];diagnostics={}
    with h5py.File(a.input/'expectations_and_campaign.h5') as h:
        for m in MODES:
            direct, reflected, mask=reflection_candidates(h[m+'/archived_electronic_power_ADC_V2'][:],h[m+'/electronic_power_ADC_V2'][:])
            masks.append(mask);diagnostics[m]={'direct_eight_band_RMS_relative_error':direct.tolist(),'reflected_eight_band_RMS_relative_error':reflected.tolist(),'candidate_runs':runs[mask].tolist()}
        ambiguous=np.logical_and.reduce(masks)
        assert all(np.array_equal(x,ambiguous) for x in masks),'Mode-specific coordinate disagreement needs separate review'
        valid=~ambiguous;clock=h['time_unix'][:]
        table=read_rows(WORK/'simulation/step7/dc_longterm_diagnostic/longterm.csv')
        result['correlations']={}
        result['between_mode_correlations']={}
        for m in MODES:
            rows=sorted([r for r in table if r['mode']==m],key=lambda r:int(r['run']))
            power=h[m+'/power_ADC_V2'][:]
            result['correlations'][m]={f'offset_{int(off)}':{f'T{s}':correlations(power[valid,bi],np.array([float(r[f't{s}_mK']) for r in rows])[valid],clock[valid]) for s in [15,16,17]} for bi,off in enumerate(OFFSETS)}
            error=h[m+'/shared_window_power_relative_error'][:][valid]
            v=result['validation'][m]
            v['signed_coordinate_selected_n']=int(valid.sum())
            v['selected_max_abs_power_error_percent']=float(100*np.max(abs(error)))
            v['selected_median_power_error_percent']=float(100*np.median(error))
            v['selected_first_last_difference_percentage_points']=float(100*(error[-1]-error[0]))
            v['selected_error_vs_time']=correlations(error,clock[valid],clock[valid])['raw']
            v['qualified_descriptive_use']=bool(np.max(abs(error))<.0011)
            v['decision']='Use only signed-overlap-compatible runs for resonance trends/correlations; quarantine reflection candidates, do not relabel frequencies or repair their PSDs. Original all260 strict-screen result retained.'
        for bank in ['resonance','electronic']:
            arr={m:h[m+'/power_ADC_V2' if bank=='resonance' else m+'/electronic_power_ADC_V2'][:] for m in MODES}
            keep=valid if bank=='resonance' else np.ones(len(valid),bool);ci=3 if bank=='resonance' else 4
            result['between_mode_correlations'][bank]={x+'_'+y:correlations(arr[x][keep,ci],arr[y][keep,ci],clock[keep]) for x,y in [('TM010','TM011'),('TM010','TM012'),('TM011','TM012')]}
    result['coordinate_audit']={'available_runs':260,'included_n':int(valid.sum()),'included_runs':runs[valid].tolist(),'quarantined_runs':runs[ambiguous].tolist(),
        'classification':'Empirical signed-overlap agreement with known historical I-iQ products; original NPZ lacks IQ-sign provenance.',
        'reflection_is_proven':False,'sign_correction_applied':False,
        'reason':'All eight nonzero electronic windows in all three modes match much better after reflection for the same seven runs. No independent NPZ execution-sign metadata was found. Reflection remains a hypothesis; these runs are excluded rather than corrected.',
        'scope':'Full-band/electronic historical results still260runs; resonance trends/correlations253runs with seven explicit gaps.',
        'diagnostics':diagnostics}
    result['scope']='260 archived PSDs audited; resonance power trends on253signed-overlap-compatible runs; seven coordinate-ambiguous runs quarantined; run680analyticreference.'
    result['limitations'].append('Seven NPZ files have coordinate ambiguity and are excluded from resonance conclusions, not silently reflected. Their uncorrected integrals are retained only as diagnostic candidates.')
    result['input_sha256'].update({str(a.input/'results.json'):sha(a.input/'results.json'),str(a.input/'expectations_and_campaign.h5'):sha(a.input/'expectations_and_campaign.h5'),str(Path(__file__).resolve()):sha(__file__)})
    shutil.copy2(a.input/'expectations_and_campaign.h5',a.output/'expectations_and_campaign.h5')
    with h5py.File(a.output/'expectations_and_campaign.h5','r+') as h:
        h.create_dataset('valid_signed_coordinate_mask',data=valid)
        h.attrs['scope']=result['scope'];h.attrs['coordinate_audit_json']=json.dumps(result['coordinate_audit'])
    with open(a.input/'campaign_band_powers.csv') as f:rows=list(csv.DictReader(f))
    for r in rows:r['signed_coordinate_validated']=bool(valid[int(r['run'])-680])
    with open(a.output/'campaign_band_powers.csv','w') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    (a.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result['coordinate_audit'].items() if k!='diagnostics'},indent=2))
if __name__=='__main__':main()
