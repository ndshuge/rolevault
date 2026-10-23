import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from rolevault.provenance_guard import enforce
class ProvenanceTests(unittest.TestCase):
 def test_owner(self):self.assertEqual(enforce("owner","ADD"),"ADD")
 def test_outsider_update(self):self.assertEqual(enforce("third_party","UPDATE"),"REJECT")
 def test_outsider_forget(self):self.assertEqual(enforce("third_party","FORGET"),"REJECT")
 def test_rumor(self):self.assertEqual(enforce("rumor","IGNORE"),"REJECT")
 def test_web(self):self.assertEqual(enforce("web","ADD"),"REJECT")
 def test_unknown(self):self.assertEqual(enforce("fake_owner","ADD"),"REJECT")
 def test_invalid(self):self.assertEqual(enforce("owner","GRANT"),"REJECT")
