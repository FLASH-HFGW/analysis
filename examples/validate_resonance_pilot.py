"""Read-only checks of the produced pilot and immutable electronic/physical references."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np,h5py
from scipy.signal import firwin
from iq_acquisition_metadata import MODES

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--bor-audit',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();checks={}
    with h5py.File(a.input,'r') as h,h5py.File(a.bor_audit,'r') as audit:
        assert h['summary/reached_eof'][()] and h['summary/events_SPEC'][()]==1000 and h['summary/samples'][()]==1048576000
        assert not h['summary/post_demodulation_mean_subtraction'][()] and h['summary/coherent_band_center_signal_retained'][()]
        assert h['summary/acquired_duration_s'][()]==209.7152
        assert audit['summary/runs'][()]==260 and audit['summary/SPEC_events_read'][()]==0
        for run in range(680,940):
            for m in MODES:
                path=f'acquisition_metadata/run{run:05d}/modes/{m}/center_digital_IQ_hz';assert audit[path][()]==1250000
        old=Path(h['filter_banks/electronic_DC_reference/source_HDF5'].asstr()[()]);assert sha(old)==h['filter_banks/electronic_DC_reference/source_sha256'].asstr()[()]
        physical=Path(h['physical_reference_thesis_fit/source'].asstr()[()]);assert sha(physical)==h['physical_reference_thesis_fit/sha256'].asstr()[()]
        for name,node in h['provenance/analysis_source_sha256'].items():assert sha(Path(__file__).parent/name)==node.asstr()[()]
        original=json.loads(h['acquisition_metadata/original_selected_ODB_JSON'].asstr()[()]);assert original['VNA_vnaCalib']['freq_mode2']==8780842000
        cfg=h['filter_banks/resonance_ROI/configuration'];coeff=cfg['FIR_coefficients'][:];assert np.array_equal(coeff,firwin(2001,25000,fs=5e6,window=('kaiser',8.6)))
        with h5py.File(old,'r') as ref:
            for m in MODES:
                assert h[f'acquisition_metadata/modes/{m}/ADC_peak_V'][()]==2
                assert h[f'acquisition_metadata/modes/{m}/center_digital_IQ_hz'][()]==1250000
                expected=float(ref[f'filtered_bands/modes/{m}/band_08/complex_moments/total_squared_v2'][()])*.16
                for bi,off in enumerate([-500000,-250000,-100000,0,100000,250000,500000]):
                    g=h[f'filter_banks/resonance_ROI/modes/{m}/band_{bi:02d}'];mm=g['moments_ADC'];assert g['input_center_hz'][()]==1250000+off
                    n=int(mm['n'][()]);assert n==52428700 and g['amplitude_counts'][:].sum()==n
                    P=float(mm['total_squared_v2'][()]);assert np.isclose(P,mm['ac_squared_v2'][()]+mm['dc_squared_v2'][()],rtol=1e-13)
                    eventn=g['events/samples'][:];assert eventn.sum()==n and len(eventn)==1000
                    eventpower=np.average(g['events/RMS_ADC_V'][:]**2,weights=eventn);assert np.isclose(P,eventpower,rtol=1e-12)
                    z=g['selected_first5SPEC_output_V'][:];assert len(z)==262044
                    cv=g['selected_total_autocovariance_V2'][:];assert np.isclose(cv[0].real,np.mean(abs(z)**2),rtol=1e-12)
                    assert np.allclose(np.diff(g['selected_lag_s'][:]),4e-6,atol=1e-18,rtol=0)
                    assert abs(g['selected_total_g1'][0]-1)<1e-12
                    freq=g['PSD_frequency_baseband_hz'][:];psd=g['PSD_total_V2_Hz'][:];integral=float(psd.sum()*(freq[1]-freq[0]));assert abs(integral/P-1)<.01
                    if bi==1:assert abs(P/expected-1)<1e-8
                assert h[f'consistency_with_electronic_bank/{m}/passed'][()]
                checks[m]={'shared_window_max_perSPEC_relative_error':float(h[f'consistency_with_electronic_bank/{m}/max_perSPEC_RMS_relative_difference'][()]),'samples_per_band':52428700,'full_run_histograms_conserve_counts':True,'selected_covariance_preserves_total_power':True,'PSD_integral_matches_full_run_power_within_1pct':True}
    result={'status':'passed','checks':checks,'BOR_audit_runs':260,'resonance_reconstructed_runs':[680],'old_electronic_product_and_frozen_physical_reference_unchanged':True,'source_hashes_verified':True,'no_output_mean_subtraction':True,'sample_interval_filtered_s':4e-6,'no_longterm_SPEC_reconstruction':True}
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
