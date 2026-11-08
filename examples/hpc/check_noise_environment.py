"""Exercise the actual IQ dependencies before any Slurm submission."""
import importlib
import io
import json
import sys


def check_environment():
    try:
        modules = {name: importlib.import_module(name)
                   for name in ('numpy', 'scipy', 'h5py', 'matplotlib', 'midas.file_reader')}
    except ImportError as exc:
        raise RuntimeError('IQ dependency unavailable. Run: bash examples/hpc/run_noise_pilot.sh setup-env') from exc
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
