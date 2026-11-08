"""Exercise the actual IQ dependencies before any Slurm submission."""
import importlib
import io
import json
import os
from pathlib import Path
import sys


def check_environment():
    try:
        modules = {name: importlib.import_module(name)
                   for name in ('numpy', 'scipy', 'h5py', 'matplotlib', 'midas.file_reader')}
    except ImportError as exc:
        raise RuntimeError('IQ dependency unavailable in CVMFS. Check FLASH repository propagation, then rerun check-env.') from exc
    if os.environ.get('HFGW_NOISE_CVMFS_ONLY') == '1':
        root = Path(os.environ['HFGW_CVMFS_ROOT']).resolve()
        for name, module in modules.items():
            if not Path(module.__file__).resolve().is_relative_to(root):
                raise RuntimeError(f'{name} was loaded outside FLASH CVMFS: {module.__file__}')
    from scipy.signal import fftconvolve, firwin
    from scipy.stats import rankdata
    import numpy as np
    import h5py
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    filtered = fftconvolve(np.arange(16, dtype=float), firwin(5, .2))
    assert np.isfinite(filtered).all()
    np.testing.assert_equal(rankdata([3, 1, 2]), [3, 1, 2])
    with h5py.File(io.BytesIO(), 'w') as output:
        output.create_dataset('filtered', data=filtered, compression='gzip')
    fig, ax = plt.subplots()
    ax.plot(filtered)
    png = io.BytesIO()
    fig.savefig(png, format='png')
    plt.close(fig)
    assert png.getvalue().startswith(b'\x89PNG')
    info = dict(python=sys.executable, python_version=sys.version.split()[0],
                modules={name: dict(version=getattr(module, '__version__', None), path=module.__file__)
                         for name, module in modules.items()})
    print(json.dumps(info, indent=2), flush=True)
    print('IQ environment check passed; no jobs submitted by this check.', flush=True)
    return info


if __name__ == '__main__':
    check_environment()
