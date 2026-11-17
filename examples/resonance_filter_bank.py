"""Continuous complex FIR bank, sharing one input FFT across mode/band centers.

Exactly the same h, group delay, transient and sample grid as BandFilter.
LPF[z exp(-iwn)] = exp(-iwn) * ((h exp(iwk)) convolved with z).
Only retained output instants require an oscillator. No output centering occurs.
"""
import numpy as np
from scipy.fft import fft,ifft,next_fast_len
from scipy.signal import firwin

class ResonanceBank:
    def __init__(self,fs,centers,width=50000,taps=2001,decimation=20,workers=1):
        centers=np.asarray(centers,float)
        if centers.ndim!=2 or not np.isfinite(centers).all():raise ValueError('centers must be mode x band')
        if taps<3 or taps%2!=1 or decimation<1 or not 0<width/2<fs/(2*decimation):raise ValueError('Invalid FIR/decimation')
        if np.any(abs(centers)+width/2>=fs/2):raise ValueError('Bank outside Nyquist')
        self.fs=float(fs);self.centers=centers;self.h=firwin(taps,width/2,fs=fs,window=('kaiser',8.6));self.decimation=decimation;self.workers=workers;self.n=0;self.tail=np.zeros((centers.shape[0],taps-1),complex);self._kernels={}
    def _phase(self,indices,freq):
        # Exact modular integer arithmetic avoids large-angle phase precision loss.
        if float(freq).is_integer() and self.fs.is_integer() and (not len(indices) or max(abs(indices[0]),abs(indices[-1]))*abs(freq)<2**62):
            turns=(indices*np.int64(round(freq)))%np.int64(round(self.fs));return np.exp(-2j*np.pi*turns/self.fs)
        return np.exp(-2j*np.pi*np.remainder(indices*freq/self.fs,1))
    def process(self,z):
        z=np.asarray(z,complex)
        if z.ndim!=2 or z.shape[0]!=self.centers.shape[0]:raise ValueError('Expected mode x input samples')
        size=z.shape[1]
        if not size:return np.empty(0),np.empty((z.shape[0],self.centers.shape[1],0),complex)
        start=self.n;first=max(start,len(self.h)-1);first+=(-first)%self.decimation;take=np.arange(first-start,size,self.decimation,dtype=np.int64);indices=start+take
        extended=np.concatenate([self.tail,z],axis=1);length=next_fast_len(extended.shape[1]+len(self.h)-1);X=fft(extended,length,axis=1,workers=self.workers)
        if length not in self._kernels:
            k=np.arange(len(self.h));kernels=[]
            for bi in range(self.centers.shape[1]):
                mod=np.array([self.h*np.exp(2j*np.pi*f*k/self.fs) for f in self.centers[:,bi]])
                kernels.append(fft(mod,length,axis=1,workers=self.workers))
            # Bound caches if a final irregular chunk changes transform length.
            self._kernels={length:kernels}
        out=np.empty((z.shape[0],self.centers.shape[1],len(take)),complex);phases={}
        for bi,kernel in enumerate(self._kernels[length]):
            c=ifft(X*kernel,axis=1,workers=self.workers)
            for mi,f in enumerate(self.centers[:,bi]):
                if f not in phases:phases[f]=self._phase(indices,f)
                out[mi,bi]=c[mi,len(self.h)-1+take]*phases[f]
        self.tail=extended[:,-len(self.tail[0]):].copy();self.n+=size
        return (indices-(len(self.h)-1)/2)/self.fs,out
