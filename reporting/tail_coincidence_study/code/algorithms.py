"""Offline index-domain grouping; never independent physical-event counting."""
import itertools
import numpy as np

def clusters(indices,amplitudes,gap):
 indices=np.asarray(indices,dtype=np.int64);amplitudes=np.asarray(amplitudes)
 if not len(indices):return []
 if len(indices)!=len(amplitudes) or np.any(np.diff(indices)<=0):raise ValueError('sorted unique paired indices required')
 cuts=np.r_[0,np.flatnonzero(np.diff(indices)-1>gap)+1,len(indices)];out=[]
 for lo,hi in zip(cuts[:-1],cuts[1:]):
  peak=lo+int(np.argmax(amplitudes[lo:hi]));out.append(dict(start=int(indices[lo]),end=int(indices[hi-1]),peak=int(indices[peak]),multiplicity=int(hi-lo),maximum=float(amplitudes[peak]),duration_samples=int(indices[hi-1]-indices[lo]+1)))
 return out

def coincidences(peaks,window):
 """All peak tuples with max-minus-min <= window; tuples may share clusters."""
 peaks=[np.asarray(x,dtype=np.int64) for x in peaks];pairs={};triples=[]
 for a,b in itertools.combinations(range(3),2):
  out=[]
  for i,t in enumerate(peaks[a]):
   lo=np.searchsorted(peaks[b],t-window);hi=np.searchsorted(peaks[b],t+window,side='right')
   out.extend((i,j) for j in range(lo,hi))
  pairs[a,b]=out
 for a,b in pairs[0,1]:
  t,u=peaks[0][a],peaks[1][b];lo=np.searchsorted(peaks[2],max(t,u)-window);hi=np.searchsorted(peaks[2],min(t,u)+window,side='right');triples.extend((a,b,c) for c in range(lo,hi))
 return pairs,triples
