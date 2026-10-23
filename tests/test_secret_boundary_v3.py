import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from rolevault.stateful_store import StatefulRoleStore,RejectedSecret
class SecretBoundaryTests(unittest.TestCase):
 def test_sensitive_non_numeric_codes(self):
  with tempfile.TemporaryDirectory() as d:
   with StatefulRoleStore(Path(d)/"store.db",{"r":"owner"}) as s:
    for i,value in enumerate(["email recovery code: blue-forest","reset token: abcxyz","backup code: word-word","one time code: word"],1):
     with self.subTest(value=value),self.assertRaises(RejectedSecret):
      s.upsert(role="r",actor="owner",subject="self",slot="note",value=value,turn=i)
    self.assertEqual(s.snapshot(role="r",actor="owner"),[])
 def test_professional_certificate_allowed(self):
  with tempfile.TemporaryDirectory() as d:
   with StatefulRoleStore(Path(d)/"store.db",{"r":"owner"}) as s:
    self.assertEqual(s.upsert(role="r",actor="owner",subject="self",slot="qualification",value="professional certification completed",turn=1),"ADD")
