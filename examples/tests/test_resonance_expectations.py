"""Independent scientific checks for analytic band powers and coordinate quarantine."""
from pathlib import Path
import sys, unittest
import numpy as np
from scipy.signal import firwin
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from resonance_reference_and_campaign import FS, response_power, reference_psd
from assess_archived_psd_coordinates import reflection_candidates

class AnalyticBandTests(unittest.TestCase):
    def test_white_noise_power_is_fir_energy_at_every_center(self):
        taps=firwin(2001,25000,fs=FS,window=('kaiser',8.6))
        centers=[750000,1000000,1150000,1250000,1350000,1500000,1750000]
        H=response_power(taps,centers,65536)
        np.testing.assert_allclose(H.mean(axis=1),np.sum(taps*taps),rtol=2e-14)
        # Narrow coherent tones must land at the stated positive input centers.
        for i,c in enumerate(centers):
            f=np.fft.fftfreq(65536,1/FS);ii=np.argmin(abs(f-c))
            self.assertEqual(np.argmax(H[:,ii]),i)

    def test_cavity_uses_physical_fit_not_nominal_bank_center(self):
        cfg={'LF_data_over_cal_amplitude':1.,'RF_gain_db':0.,'primary_LO_hz':800000.,'secondary_LO_hz':{'X':50000.},'resistance_ohm':50.,'receiver_Tn_K':2.}
        phys={'mode_results':{'X':{'f0_hz':1000000.,'q0':100.,'kappa1':.1,'kappa2':.5,'temperature_k':.1}}}
        cal={'curves':{'X':[{'rf_hz':-1e7,'kz_integrated':1.},{'rf_hz':1e7,'kz_integrated':1.}]},'comparison':{'X':{'rf_if_offset_hz':0.}}}
        freq=np.arange(100000.,200001.,100.)
        thermal,electronic=reference_psd(freq,'X',cfg,phys,cal)
        self.assertEqual(freq[np.argmax(thermal)],150000.)
        np.testing.assert_allclose(electronic,electronic[0])
        cfg['receiver_Tn_K']*=2
        thermal2,electronic2=reference_psd(freq,'X',cfg,phys,cal)
        np.testing.assert_array_equal(thermal2,thermal)
        np.testing.assert_allclose(electronic2,2*electronic)

    def test_reflection_is_flagged_without_changing_input(self):
        old=np.tile(np.array([1.,2.,3.,4.,5.,6.,7.,8.,9.]),(2,1))
        archived=old.copy();archived[1]=old[1,::-1]
        original=archived.copy()
        direct,reflected,flag=reflection_candidates(archived,old)
        np.testing.assert_array_equal(flag,[False,True])
        np.testing.assert_array_equal(archived,original)
        self.assertEqual(direct[0],0);self.assertEqual(reflected[1],0)

if __name__=='__main__':unittest.main()
