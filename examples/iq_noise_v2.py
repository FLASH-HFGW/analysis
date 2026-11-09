"""Stable complex moments and explicit nominal input-referred v2 quantities."""
import hashlib
import json
import numpy as np


def load_calibration(path):
    raw = path.read_bytes()
    config = json.loads(raw)
    stages = list(config['stages_db'].values())
    if (config['schema'] != 'iq-nominal-gain-v1' or not stages
            or not np.isfinite(stages).all() or not np.isfinite(config['total_db'])
            or not np.isclose(sum(stages), config['total_db'], rtol=0, atol=1e-9)
            or config['frequency_response_applied'] is not False):
        raise ValueError('Invalid or double-counted nominal gain calibration')
    gain = float(10. ** (config['total_db'] / 20.))
    if not np.isfinite(gain) or gain <= 0:
        raise ValueError('Invalid voltage gain')
    return dict(configuration=config, sha256=hashlib.sha256(raw).hexdigest(),
                voltage_gain=gain, squared_voltage_gain=gain*gain,
                units='nominal input-referred equivalent complex volts; not watts')


class ComplexMoments:
    """Population variance E|z-Ez|², merged without raw power subtraction."""
    def __init__(self):
        self.n = 0
        self.mean = 0j
        self.m2 = 0.

    def update(self, z):
        z = np.asarray(z)
        if not z.size:
            return
        if not np.isfinite(z).all():
            raise ValueError('Nonfinite IQ samples')
        count = z.size
        mean = complex(np.mean(z))
        delta = mean-self.mean
        residual = z-mean
        total = self.n+count
        self.m2 += float(np.vdot(residual, residual).real) + abs(delta)**2*self.n*count/total
        self.mean += delta*count/total
        self.n = total

    def export(self, gain=1.):
        if not self.n:
            raise ValueError('No IQ samples')
        ac = max(0., self.m2/self.n)
        dc = abs(self.mean)**2
        return dict(n=self.n, mean_i_v=self.mean.real, mean_q_v=self.mean.imag,
                    dc_squared_v2=dc, ac_squared_v2=ac, total_squared_v2=dc+ac,
                    ac_rms_v=float(np.sqrt(ac)), total_rms_v=float(np.sqrt(dc+ac)),
                    mean_i_input_v=self.mean.real/gain, mean_q_input_v=self.mean.imag/gain,
                    dc_squared_input_v2=dc/gain**2, ac_squared_input_v2=ac/gain**2,
                    total_squared_input_v2=(dc+ac)/gain**2,
                    ac_rms_input_v=float(np.sqrt(ac))/gain,
                    total_rms_input_v=float(np.sqrt(dc+ac))/gain)


def trend_diagnostics(values, temperatures, times):
    """Residual association after a linear time trend, descriptive only."""
    y, t, x = map(lambda a: np.asarray(a, dtype=float), (values, temperatures, times))
    valid = np.isfinite(y) & np.isfinite(t) & np.isfinite(x)
    y, t, x = y[valid], t[valid], x[valid]
    result = dict(n=len(y), method='OLS residuals after intercept and linear acquisition time; no p-values',
                  r_temperature=None, r_time=None, r_temperature_after_linear_time=None,
                  design_condition_number=None)
    def correlation(a, b):
        if len(a) < 3 or np.std(a) <= 1e-12 or np.std(b) <= 1e-12:
            return None
        return float(np.corrcoef(a, b)[0, 1])
    if len(y) < 4 or any(np.std(a) == 0 for a in (x,t,y)):
        return result
    y, t, x = [(a-a.mean())/a.std() for a in (y,t,x)]
    result.update(r_temperature=correlation(y,t), r_time=correlation(y,x))
    design = np.column_stack([np.ones(len(x)),x])
    yr = y-design@np.linalg.lstsq(design,y,rcond=None)[0]
    tr = t-design@np.linalg.lstsq(design,t,rcond=None)[0]
    result['r_temperature_after_linear_time'] = correlation(yr,tr)
    result['design_condition_number'] = float(np.linalg.cond(np.column_stack([design,t])))
    return result


def plot_decomposition(modes, path):
    import matplotlib.pyplot as plt
    names = list(modes)
    x = np.arange(len(names))
    fig, axes = plt.subplots(1,2,figsize=(11,4))
    for shift,key,label in [(-.25,'total_rms_v','Raw RMS'),(0.,'dc_squared_v2','|mean IQ|'),(.25,'ac_rms_v','AC RMS')]:
        y = [np.sqrt(modes[m][key]) if key=='dc_squared_v2' else modes[m][key] for m in names]
        axes[0].bar(x+shift,np.array(y)*1e3,width=.25,label=label)
    axes[0].set(ylabel='ADC-equivalent complex voltage [mV]',xticks=x,xticklabels=names)
    axes[0].legend()
    axes[1].bar(x,[modes[m]['ac_rms_input_v']*1e9 for m in names],color='#007F86')
    axes[1].set(ylabel='Nominal input-referred AC RMS [nV]',xticks=x,xticklabels=names)
    fig.suptitle('v2: one complex run mean removed; nominal scalar gain (see metadata)')
    fig.tight_layout()
    fig.savefig(path,dpi=160)
    plt.close(fig)
