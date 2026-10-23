"""P1 stale-write and temporal-order regression tests."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from rolevault.stateful_store import StatefulRoleStore
class OrderingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.s=StatefulRoleStore(Path(self.tmp.name)/"db.sqlite",{"A":"alice"})
  self.auth={"role":"A","actor":"alice","subject":"self","slot":"job"}
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def put(self,v,n,**kw):return self.s.upsert(value=v,turn=n,**self.auth,**kw)
 def forget(self,n):return self.s.forget(turn=n,**self.auth)
 def value(self):
  r=self.s.get(**self.auth)
  return r["value"] if r else None
 def test_older_write_ignored(self):
  self.put("new",8);self.assertEqual(self.put("old",4),"STALE");self.assertEqual(self.value(),"new")
 def test_equal_turn_conflict_ignored(self):
  self.put("new",8);self.assertEqual(self.put("old",8),"STALE");self.assertEqual(self.value(),"new")
 def test_newer_write_accepted(self):
  self.put("old",4);self.assertEqual(self.put("new",8),"UPDATE")
 def test_stale_replay_after_forget(self):
  self.put("old",4);self.forget(8);self.assertEqual(self.put("old",3),"STALE");self.assertIsNone(self.value())
 def test_newer_replay_after_forget_suppressed(self):
  self.put("old",4);self.forget(8);self.assertEqual(self.put("old",9),"SUPPRESSED")
 def test_restore_requires_explicit(self):
  self.put("old",4);self.forget(8);self.assertEqual(self.put("new",9,explicit_restore=True),"ADD")
 def test_same_value_reaffirmation_advances_watermark(self):
  self.put("new",4)
  self.assertEqual(self.put("new",10),"NO_CHANGE")
  self.assertEqual(self.s.get(**self.auth)["source_turn"],10)
  self.assertEqual(self.put("stale_conflict",8),"STALE")
  self.assertFalse(self.forget(9))
  self.assertEqual(self.value(),"new")
 def test_stale_forget_must_not_erase_new_value(self):
  self.put("new",8);self.assertFalse(self.forget(4));self.assertEqual(self.value(),"new")
