import unittest,numpy as np
from algorithms import clusters,coincidences
class Rules(unittest.TestCase):
 def test_gap_and_boundary(self):
  i=np.array([9,10,13,30]);a=np.array([1,3,2,4]);self.assertEqual([x['multiplicity'] for x in clusters(i,a,0)],[2,1,1]);self.assertEqual([x['multiplicity'] for x in clusters(i,a,2)],[3,1]);self.assertEqual(clusters(np.r_[i[:2],i[2:]],np.r_[a[:2],a[2:]],2),clusters(i,a,2))
 def test_peak_and_duration(self):
  x=clusters([4,5,8],[2,9,3],2)[0];self.assertEqual((x['peak'],x['start'],x['end'],x['duration_samples']),(5,4,8,5))
 def test_triple_range_not_pairwise_chain(self):
  p,t=coincidences([[10],[15],[20]],5);self.assertEqual(len(t),0);self.assertEqual(len(p[0,1]),1);self.assertEqual(len(p[1,2]),1)
 def test_inclusive_and_empty(self):
  p,t=coincidences([[10],[15],[12]],5);self.assertEqual(len(t),1);self.assertEqual(sum(map(len,p.values())),3);self.assertEqual(clusters([],[],0),[])
if __name__=='__main__':unittest.main()
