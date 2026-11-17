import copy,sys,unittest
from pathlib import Path
import numpy as np
from scipy.signal import lfilter
from numpy.testing import assert_allclose
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from iq_acquisition_metadata import extract_coordinates,resonance_centers
from resonance_filter_bank import ResonanceBank
from analyze_iq_filtered_bands import BandFilter

def fixture():return {'Equipment':{'VNA':{'vnaCalib':{'freq_mode1':8737119000.,'freq_mode2':8780842000.,'freq_mode3':8841176000.}},'LocalOscill':{'Variables':{'freq RS':8735869000.,'freq Teled Ch1':43723000.,'freq Teled Ch2':104057000.}},'NetBox':{'Settings':{'Sampling_rate_MS':'5','Channel_range_mV':[2000]*6+[5000]*2}}}}

class ResonanceTests(unittest.TestCase):
    def test_strict_metadata_and_frequency_sign(self):
        m=extract_coordinates(fixture());self.assertEqual([m['modes'][k]['center_digital_IQ_hz'] for k in m['modes']],[1250000]*3)
        neg=extract_coordinates(fixture(),1);self.assertEqual(neg['modes']['TM011']['center_digital_IQ_hz'],-1250000)
        for key in ['freq_mode1','freq_mode2','freq_mode3']:
            f=fixture();del f['Equipment']['VNA']['vnaCalib'][key]
            with self.assertRaises(ValueError):extract_coordinates(f)
        f=fixture();f['Equipment']['NetBox']['Settings']['Channel_range_mV'][1]=5000
        with self.assertRaises(ValueError):extract_coordinates(f)
        f=fixture();f['Equipment']['VNA']['vnaCalib']['freq_mode1']=float('nan')
        with self.assertRaises(ValueError):extract_coordinates(f)
    def test_independent_causal_reference_irregular_boundaries(self):
        rng=np.random.default_rng(71);z=(rng.normal(size=(3,9001))+1j*rng.normal(size=(3,9001)))*.003
        centers=np.array([[750000,1000000,1250000],[751234,1000345,1248000],[753210,1001000,1256000]],float);b=ResonanceBank(5e6,centers);pieces=[];tt=[]
        for part in np.split(z,[1,1999,2000,2001,2103,5000],axis=1):
            t,y=b.process(part);pieces.append(y);tt.append(t)
        y=np.concatenate(pieces,axis=2);times=np.concatenate(tt);idx=np.arange(2000,z.shape[1],20);assert_allclose(times,(idx-1000)/5e6,atol=0,rtol=0)
        for mi in range(3):
            for bi,c in enumerate(centers[mi]):
                n=np.arange(z.shape[1]);ref=lfilter(b.h,[1],z[mi]*np.exp(-2j*np.pi*c*n/5e6))[idx]
                assert_allclose(y[mi,bi],ref,atol=2e-14,rtol=2e-9)
    def test_shared_bank_matches_legacy_and_coherent_center_survives(self):
        fs=5e6;n=np.arange(70000);freqs=[1000000,1250000,1500000];centers=np.tile(freqs,(3,1));z=np.array([.01*np.exp(2j*np.pi*f*n/fs) for f in freqs]);b=ResonanceBank(fs,centers);t,y=b.process(z)
        for mi,f in enumerate(freqs):
            _,ref=BandFilter(fs,f,50000).process(z[mi]);assert_allclose(y[mi,mi],ref,atol=1e-12,rtol=1e-8)
            self.assertAlmostEqual(np.sqrt(np.mean(abs(y[mi,mi])**2)),.01,places=10)
            self.assertGreater(abs(np.mean(y[mi,mi])),.00999) # No output DC subtraction!
            for bi in range(3):
                if bi!=mi:self.assertLess(np.sqrt(np.mean(abs(y[mi,bi])**2)),1e-6)
    def test_negative_frequency_rejected_by_positive_bank(self):
        n=np.arange(60000);z=np.exp(-2j*np.pi*1.25e6*n/5e6)[None,:]
        _,y=ResonanceBank(5e6,[[1.25e6]]).process(z);self.assertLess(np.sqrt(np.mean(abs(y)**2)),1e-5)
    def test_all_seven_known_tones_identify_the_correct_band(self):
        fs=5e6;freqs=np.array([750000,1000000,1150000,1250000,1350000,1500000,1750000]);n=np.arange(50000)
        z=.007*np.exp(2j*np.pi*freqs[:,None]*n[None,:]/fs)
        _,y=ResonanceBank(fs,np.tile(freqs,(7,1))).process(z)
        power=np.mean(abs(y)**2,axis=2)
        self.assertEqual(np.argmax(power,axis=1).tolist(),list(range(7)))
        assert_allclose(np.diag(power),.007**2,rtol=1e-10,atol=1e-15)
        off=power.copy();np.fill_diagonal(off,0);self.assertLess(off.max(),1e-11)
    def test_metadata_survives_hdf5_roundtrip(self):
        import tempfile,json
        from iq_noise_io import save_results_h5,read_results_h5
        m=extract_coordinates(fixture())
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'coordinates.h5';save_results_h5(p,{'schema_version':1,'acquisition_metadata':m});r=read_results_h5(p)['acquisition_metadata']
        self.assertEqual(r['modes']['TM010']['center_digital_IQ_hz'],1250000)
        self.assertEqual(r['modes']['TM011']['ADC_V_per_count'],4/65535)
        self.assertEqual(json.loads(r['original_selected_ODB_JSON'])['VNA_vnaCalib']['freq_mode2'],8780842000)
    def test_bor_center_is_used_not_frozen_nominal(self):
        f=fixture();f['Equipment']['VNA']['vnaCalib']['freq_mode2']+=23000;m=extract_coordinates(f)
        self.assertEqual(resonance_centers(m)['TM011'][3],1273000)
        m['modes']['TM011']['center_digital_IQ_hz']=2490000
        with self.assertRaises(ValueError):resonance_centers(m)
if __name__=='__main__':unittest.main()
