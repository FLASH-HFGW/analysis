"""Verifiche scientifiche e del contratto di aggregazione multi-run."""
import contextlib
import copy
import importlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from iq_noise_statistics import RunStatistics, make_config, merge_moments, episodes, MODES, uniform_histogram, uniform_histogram2d
from aggregate_iq_noise import aggregate, read_inputs, create_reference


def local_moments(frames):
    result = {}
    for mode, (ci, cq) in zip(MODES, ((0, 1), (2, 3), (4, 5))):
        a = np.concatenate([np.hypot(f[:, ci], f[:, cq]) for f in frames])
        result[mode] = {'n': len(a), 'mean': float(a.mean()), 'm2': float(np.sum((a-a.mean())**2))}
    return result


def fixture(root, run, frames, config, complete=True):
    local = local_moments(frames)
    stats = RunStatistics(config, local)
    for f in frames:
        for mode, (ci, cq) in zip(MODES, ((0, 1), (2, 3), (4, 5))):
            stats.update(mode, f[:, ci], f[:, cq])
    gs, arrays = stats.export()
    n = sum(map(len, frames))
    name = 'run%05d' % run
    doc = {'input': name+'.mid.gz', 'status': 'success', 'reached_eof': complete,
           'samples': n, 'events': [{'serial': k} for k in range(len(frames))],
           'global_statistics': gs, **{key:config[key] for key in ('fs_hz','input_range_v','iq_sign')},
           'modes': {mode:{'mean_amplitude_v':v['mean'], 'amplitude_noise_rms_v':np.sqrt(v['m2']/v['n'])}
                     for mode,v in local.items()}}
    path = root/(name+'_noise.json')
    path.write_text(json.dumps(doc))
    np.savez_compressed(path.with_suffix('.npz'), **arrays)
    return path, doc


class StatisticsTests(unittest.TestCase):
    def test_uniform_histogram_preserves_edges_and_counts(self):
        rng=np.random.default_rng(42)
        for low,high,bins in ((0.,7.0712,65536),(-np.pi,np.pi,1024),(.03,.21,1024)):
            edges=np.linspace(low,high,bins+1)
            values=np.r_[edges,np.nextafter(edges,-np.inf),np.nextafter(edges,np.inf),
                         rng.uniform(low-1,high+1,100000)]
            np.testing.assert_array_equal(uniform_histogram(values,edges),np.histogram(values,bins=edges)[0])

    def test_uniform_iq_histogram_preserves_boundaries(self):
        rng=np.random.default_rng(27)
        for low,high in ((-5.001,5.001),(-.001,.21)):
            edges=np.linspace(low,high,257)
            boundaries=np.r_[edges,np.nextafter(edges,-np.inf),np.nextafter(edges,np.inf)]
            x=np.r_[boundaries,rng.uniform(low-1,high+1,100000),np.nan,np.inf]
            y=np.r_[boundaries[::-1],rng.uniform(low-1,high+1,100000),0.,0.]
            expected=np.histogram2d(x,y,bins=(edges,edges))[0]
            np.testing.assert_array_equal(uniform_histogram2d(x,y,edges,edges),expected)

    def test_unit_phasor_circular_sums_match_angle_formula(self):
        rng=np.random.default_rng(19)
        phase=rng.uniform(-np.pi,np.pi,5000)
        amplitude=rng.uniform(.0001,1.,5000); amplitude[::37]=0
        i=amplitude*np.cos(phase);q=amplitude*np.sin(phase)
        f=np.zeros((len(i),8));f[:,0]=i;f[:,1]=q
        for ci,cq in ((2,3),(4,5)):f[:,ci]=i;f[:,cq]=q
        config=make_config(5e6,5,-1,[1,10,100])
        stats=RunStatistics(config,local_moments([f]))
        for mode in MODES:stats.update(mode,i,q)
        valid=np.hypot(i,q)>0; phi=np.arctan2(q,i)
        summary,_=stats.export()
        for lag in (1,10,100):
            good=valid[lag:]&valid[:-lag]
            delta=(phi[lag:][good]-phi[:-lag][good]+np.pi)%(2*np.pi)-np.pi
            actual=summary['modes']['TM010']['delta_circular'][str(lag)]
            self.assertEqual(actual['pairs'],len(delta))
            np.testing.assert_allclose([actual['cos_sum'],actual['sin_sum']],
                [np.cos(delta).sum(),np.sin(delta).sum()],rtol=1e-12,atol=1e-11)

    def test_weighted_merge(self):
        x=np.array([1.,2.,3.]); y=np.array([10.,20.,30.,40.,50.])
        n,mean,m2=merge_moments(len(x),x.mean(),((x-x.mean())**2).sum(),len(y),y.mean(),((y-y.mean())**2).sum())
        full=np.r_[x,y]
        self.assertEqual(n,len(full)); self.assertAlmostEqual(mean,full.mean())
        self.assertAlmostEqual(m2/n,full.var())

    def test_episodes(self):
        a=np.array([0.,2.,3.,0.,4.,0.])
        stat=episodes(a>1,a)
        self.assertEqual((stat['samples_above'],stat['episodes'],stat['longest_samples']),(3,2,2))
        self.assertEqual(stat['peak_v'],4)

    def test_delta_phase_and_event_boundaries(self):
        config=make_config(1000,5,1,[1,3,50])
        theta=np.arange(10)*.2
        f=np.zeros((10,8))
        for i,q in ((0,1),(2,3),(4,5)):
            f[:,i]=np.cos(theta); f[:,q]=np.sin(theta)
        local=local_moments([f,f])
        stats=RunStatistics(config,local)
        for _ in range(2):
            for mode,(i,q) in zip(MODES,((0,1),(2,3),(4,5))):stats.update(mode,f[:,i],f[:,q])
        doc,z=stats.export()
        for mode in MODES:
            d=doc['modes'][mode]['delta_circular']
            self.assertEqual(d['1']['pairs'],19) # confine SPEC incluso
            self.assertEqual(d['3']['pairs'],17)
            self.assertEqual(d['50']['pairs'],0)
            self.assertAlmostEqual(d['1']['sin_sum'],18*np.sin(.2)+np.sin(-1.8))
            self.assertEqual(z['global_'+mode+'_iq'].sum(),20)

    def test_null_phase_and_no_episode_join(self):
        ref={'schema':1,'fs_hz':1.,'input_range_v':5.,'iq_sign':1,
             'modes':{m:{'mean_amplitude_v':0.,'amplitude_noise_rms_v':.1} for m in MODES}}
        f=np.zeros((4,8)); f[:,0::2]=np.array([0,1,1,1])[:,None]
        local=local_moments([f,f]); stats=RunStatistics(make_config(1,5,1,[1],ref),local)
        for _ in range(2):
            for mode in MODES:stats.update(mode,f[:,0],f[:,1])
        doc,z=stats.export()
        st=doc['modes']['TM010']
        self.assertEqual(st['valid_phase'],6)
        self.assertEqual(st['delta_circular']['1']['pairs'],4)
        ep=st['exceedances']['reference']['7']
        self.assertEqual((ep['episodes'],ep['samples_above'],ep['longest_samples']),(2,6,3))

    def test_chunking_invariance_including_short_chunks_and_episodes(self):
        rng = np.random.default_rng(63)
        f = rng.normal(size=(81, 8)) * .5
        f[8:23, :6:2] = 2
        f[8:23, 1:6:2] = 0
        f[[0, 27, 80], :6] = 0
        ref = {'schema':1, 'fs_hz':1., 'input_range_v':5., 'iq_sign':1,
               'modes':{m:{'mean_amplitude_v':0., 'amplitude_noise_rms_v':.1} for m in MODES}}
        config = make_config(1,5,1,[1,3,10,100],ref)
        local = local_moments([f])
        whole, chunks = RunStatistics(config,local), RunStatistics(config,local)
        for stats, blocks in ((whole,[f]),(chunks,np.split(f,[1,9,10,13,20,35,79]))):
            for block in blocks:
                for mode,(i,q) in zip(MODES,((0,1),(2,3),(4,5))):
                    stats.update(mode,block[:,i],block[:,q])
        a, za = whole.export(); b, zb = chunks.export()
        for key in za: np.testing.assert_array_equal(za[key],zb[key])
        for mode in MODES:
            self.assertEqual(a['modes'][mode]['exceedances'],b['modes'][mode]['exceedances'])
            for lag in ('1','3','10','100'):
                for key in ('pairs','cos_sum','sin_sum'):
                    self.assertAlmostEqual(a['modes'][mode]['delta_circular'][lag][key],
                                           b['modes'][mode]['delta_circular'][lag][key])

    def test_boundary_repair_matches_full_reconstruction(self):
        from correct_iq_noise_continuity import repair_boundary
        from iq_noise_statistics import merge_episodes, empty_episodes
        rng=np.random.default_rng(38)
        f=rng.normal(size=(51,8))*.4
        f[7:32,:6:2]=2;f[7:32,1:6:2]=0;f[[4,41],:6]=0
        blocks=np.split(f,[1,8,13,19,20,31,48])
        ref={'schema':1,'fs_hz':1.,'input_range_v':5.,'iq_sign':1,
             'modes':{m:{'mean_amplitude_v':0.,'amplitude_noise_rms_v':.1} for m in MODES}}
        config=make_config(1,5,1,[1,3,10,100],ref);local=local_moments([f])
        full=RunStatistics(config,local)
        for mode,(i,q) in zip(MODES,((0,1),(2,3),(4,5))):full.update(mode,f[:,i],f[:,q])
        expected,zfull=full.export();old=copy.deepcopy(expected);arrays={k:np.zeros_like(v) for k,v in zfull.items()}
        for mode in MODES:
            st=old['modes'][mode]
            for stat in st['delta_circular'].values():stat.update(pairs=0,cos_sum=0.,sin_sum=0.)
            for kind,values in st['exceedances'].items():
                for k in values:values[k]=empty_episodes()
        for block in blocks:
            stats=RunStatistics(config,local)
            for mode,(i,q) in zip(MODES,((0,1),(2,3),(4,5))):stats.update(mode,block[:,i],block[:,q])
            chunk,zc=stats.export()
            for mode in MODES:
                for lag,v in chunk['modes'][mode]['delta_circular'].items():
                    arrays['global_'+mode+'_delta_'+lag]+=zc['global_'+mode+'_delta_'+lag]
                    for key in v:old['modes'][mode]['delta_circular'][lag][key]+=v[key]
                for kind,values in chunk['modes'][mode]['exceedances'].items():
                    for k,v in values.items():merge_episodes(old['modes'][mode]['exceedances'][kind][k],v)
        history={};tails={}
        for block in blocks:
            for mode,(i,q) in zip(MODES,((0,1),(2,3),(4,5))):
                repair_boundary(old['modes'][mode],arrays,mode,block[:,i],block[:,q],
                                np.hypot(block[:,i],block[:,q]),history,tails,zfull['phase_edges_rad'])
        for mode in MODES:
            self.assertEqual(old['modes'][mode]['exceedances'],expected['modes'][mode]['exceedances'])
            for lag,v in expected['modes'][mode]['delta_circular'].items():
                np.testing.assert_array_equal(arrays['global_'+mode+'_delta_'+lag],zfull['global_'+mode+'_delta_'+lag])
                for key in v:self.assertAlmostEqual(old['modes'][mode]['delta_circular'][lag][key],v[key])

    def test_continuous_unwrap_and_reset(self):
        from analyze_midas_iq_noise import analyze_mode
        theta = np.arange(150)*1.3
        i,q = np.cos(theta),np.sin(theta)
        state = {}
        pieces = [analyze_mode(i[a:b],q[a:b],phase_state=state)[2]
                  for a,b in ((0,1),(1,13),(13,87),(87,150))]
        np.testing.assert_allclose(np.concatenate(pieces),np.unwrap(np.arctan2(q,i)),atol=1e-11)
        self.assertAlmostEqual(analyze_mode(i[87:],q[87:],phase_state={})[2][0],np.arctan2(q[87],i[87]))
        i[13]=q[13]=0
        state={}
        pieces=[analyze_mode(i[:14],q[:14],phase_state=state)[2],
                analyze_mode(i[14:],q[14:],phase_state=state)[2]]
        self.assertTrue(np.isnan(pieces[0][-1]))
        np.testing.assert_allclose(np.r_[pieces[0][:13],pieces[1]], np.unwrap(np.arctan2(q[i!=0],i[i!=0])),atol=1e-11)

    def test_aggregate_and_rejections(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); config=make_config(1000,5,1,[1,2])
            a=np.zeros((10,8)); a[:,0::2]=.1
            b=np.zeros((30,8)); b[:,0::2]=.3
            p1,d1=fixture(root,1,[a],config); p2,d2=fixture(root,2,[b],config)
            rows=read_inputs([p1,p2])
            with mock.patch('aggregate_iq_noise.plot_results'):
                aggregate(rows,root/'global')
            result=json.loads((root/'global/global_noise.json').read_text())
            self.assertAlmostEqual(result['modes']['TM010']['mean'],.25)
            self.assertAlmostEqual(result['modes']['TM010']['amplitude_noise_rms_v'],np.std(np.r_[np.full(10,.1),np.full(30,.3)]))
            with np.load(root/'global/global_noise.npz') as z:
                self.assertEqual(z['global_TM010_amp'].sum(),40)
                self.assertEqual(z['global_TM010_delta_1'].sum(),38)
            create_reference(rows,root/'ref.json')
            self.assertAlmostEqual(json.loads((root/'ref.json').read_text())['modes']['TM010']['mean_amplitude_v'],.25)
            with self.assertRaisesRegex(ValueError,'duplicato'):read_inputs([p1,p1])
            partial=copy.deepcopy(rows); partial[0][1]['reached_eof']=False
            with self.assertRaisesRegex(ValueError,'incompleto'):aggregate(partial,root/'fail')
            bad=copy.deepcopy(rows); bad[1][1]['global_statistics']['config']['fs_hz']=2000
            with self.assertRaisesRegex(ValueError,'firma'):aggregate(bad,root/'fail')
            manifest=root/'runs.txt';manifest.write_text('1\n2\n3\n')
            with self.assertRaisesRegex(ValueError,'mancanti'):aggregate(rows,root/'fail',expected_runs=manifest)

    def test_filtered_checks_keep_pairs_across_spec(self):
        from analyze_midas_iq_noise import FilteredBandChecks
        args = types.SimpleNamespace(fs=5e6, input_range=5., iq_sign=-1,
            band_offsets_hz=[100e3], band_centers_hz=[0., 0., 0.],
            band_width_hz=50e3, band_taps=101, band_decimation=20)
        theta = 2*np.pi*102e3*np.arange(8000)/args.fs
        frames = np.zeros((8000, 8), dtype=np.int16)
        for ci, cq in ((0, 1), (2, 3), (4, 5)):
            frames[:, ci] = np.rint(10000*np.cos(theta))
            frames[:, cq] = -np.rint(10000*np.sin(theta))
        checks = FilteredBandChecks(args)
        for index, part in enumerate(np.split(frames, [50, 2003])):
            checks.update(part, index, index+1, 100+index)
        result = checks.export()['modes']['TM010']['band_02']['events']
        # Initial SPEC is wholly inside the FIR transient. Subsequent pairs
        # include the boundary pair, so total pairs equals total samples - 1.
        self.assertEqual(result['event_index'].tolist(), [1, 2])
        self.assertEqual(result['increment_pairs'].sum(), result['n'].sum()-1)
        np.testing.assert_allclose(result['increment_mean_rad'],
                                   2*np.pi*2000*20/args.fs, atol=1e-5)

    def test_full_analysis_two_runs(self):
        analysis=importlib.import_module('analyze_midas_iq_noise')
        theta=np.arange(40)*.3
        f=np.zeros((40,8),np.int16)
        for i,q in ((0,1),(2,3),(4,5)):
            f[:,i]=np.rint(1000*np.cos(theta)); f[:,q]=np.rint(1000*np.sin(theta))
        header=types.SimpleNamespace(serial_number=1,timestamp=0,is_midas_internal_event=lambda:False)
        event=types.SimpleNamespace(header=header,banks={'SPEC':types.SimpleNamespace(data=f.view(np.uint16).ravel())})
        reader=types.ModuleType('midas.file_reader'); reader.MidasFile=lambda path, **kwargs:iter([event])
        midas=types.ModuleType('midas'); midas.file_reader=reader
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules,{'midas':midas,'midas.file_reader':reader}):
            root=Path(directory)
            for run in (1,2):
                source=root/('run%05d.mid'%run);source.touch()
                argv=['noise',str(source),'--out-dir',str(root),'--phase-lags','1','3','--plot-points','10','--mode-workers',str(1 if run==1 else 3), '--filtered-bands', '--band-taps', '21']
                if run == 2:
                    argv.append('--h5-only')
                argv.extend(['--product-version', 'v1'])
                with mock.patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):analysis.main()
            from iq_noise_io import read_results_h5, flattened_arrays, read_summary
            parallel = flattened_arrays(read_results_h5(root/'run00002_noise.h5'))
            with np.load(root/'run00001_noise.npz') as serial:
                self.assertEqual(set(serial.files), set(parallel))
                for key in serial.files:
                    np.testing.assert_array_equal(serial[key], parallel[key], err_msg=key)
            self.assertEqual([p.name for p in root.glob('run00002_noise*')], ['run00002_noise.h5'])
            self.assertEqual(read_summary(root/'run00002_noise.h5')['samples'], 40)
            self.assertEqual(read_summary(root/'run00002_noise.h5')['product_version'], 'v1')
            self.assertEqual(read_results_h5(root/'run00002_noise.h5')['product_version'], 'v1')
            import h5py
            with h5py.File(root/'run00001_noise.h5', 'r') as output:
                self.assertEqual(output['summary/samples'][()], 40)
                self.assertTrue(output['summary/reached_eof'][()])
                png = output['figures/run00001_noise/data'][:].tobytes()
                self.assertTrue(png.startswith(b'\x89PNG\r\n\x1a\n'))
                self.assertEqual(output['filtered_bands/modes/TM010/band_00/events/n'][0], 1)
                with np.load(root/'run00001_noise.npz') as saved:
                    np.testing.assert_array_equal(output['modes/TM010/amplitude_v'][:], saved['TM010_amplitude_v'])
                    np.testing.assert_array_equal(output['arrays/global_TM010_amp'][:], saved['global_TM010_amp'])
            # Remove legacy sidecars: aggregation must use the HDF5 files alone.
            (root/'run00001_noise.json').unlink()
            (root/'run00001_noise.npz').unlink()
            (root/'run00002_noise.h5').rename(root/'run00002_noise_v0.h5')
            rows=read_inputs([root])
            self.assertTrue(all(path.suffix == '.h5' for path, _, _ in rows))
            with contextlib.redirect_stdout(io.StringIO()):aggregate(rows,root/'global')
            summary=json.loads((root/'global/global_noise.json').read_text())
            self.assertEqual(summary['runs'],['run00001','run00002'])
            self.assertEqual(summary['modes']['TM010']['n'],80)
            for name in ('global_distributions.png','run_trends.png','runs.csv'):
                self.assertTrue((root/'global'/name).is_file())


if __name__=='__main__':
    unittest.main()
