import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from rolevault.memory_engine.memory import MemoryObject,MemoryStatus
from rolevault.memory_engine.lifecycle import MemoryLifecycleEngine
class TestLifecycle(unittest.TestCase):
 def setUp(self):self.e=MemoryLifecycleEngine()
 def m(self,v="engineer",role="A",subject="self",attribute="job",source_type="owner_statement",confidence=1.0,valid_until=None):
  return MemoryObject(role,subject,attribute,v,source_type,confidence,valid_until=valid_until)
 def test_add(self):self.assertEqual(self.e.add(self.m()),"ADD")
 def test_update(self):self.e.add(self.m());self.assertEqual(self.e.add(self.m("architect")),"UPDATE")
 def test_old_superseded(self):self.e.add(self.m());self.e.add(self.m("architect"));self.assertEqual(self.e.memories[0].status,MemoryStatus.SUPERSEDED)
 def test_current(self):self.e.add(self.m());self.e.add(self.m("architect"));self.assertEqual(self.e.active("A")[0].value,"architect")
 def test_link(self):self.e.add(self.m());self.e.add(self.m("architect"));self.assertEqual(self.e.memories[0].replaced_by,"architect")
 def test_unchanged(self):self.e.add(self.m());self.assertEqual(self.e.add(self.m()),"UNCHANGED")
 def test_no_duplicate(self):self.e.add(self.m());self.e.add(self.m());self.assertEqual(len(self.e.memories),1)
 def test_low_trust(self):self.e.add(self.m());self.assertEqual(self.e.add(self.m("x",confidence=.1)),"KEEP_OLD")
 def test_rumor(self):self.assertEqual(self.e.add(self.m(source_type="rumor")),"REJECT_UNTRUSTED")
 def test_external(self):self.assertEqual(self.e.add(self.m(source_type="third_party")),"REJECT_UNTRUSTED")
 def test_role(self):self.e.add(self.m());self.e.add(self.m("x",role="B"));self.assertEqual(len(self.e.active("A")),1)
 def test_subject(self):self.e.add(self.m());self.e.add(self.m("x",subject="other"));self.assertEqual(len(self.e.active("A")),2)
 def test_attribute(self):self.e.add(self.m());self.e.add(self.m("x",attribute="home"));self.assertEqual(len(self.e.active("A")),2)
 def test_forget(self):self.e.add(self.m());self.assertEqual(self.e.forget("A","self","job"),1)
 def test_forget_empty(self):self.assertEqual(self.e.forget("A","self","job"),0)
 def test_hidden(self):self.e.add(self.m());self.e.forget("A","self","job");self.assertEqual(self.e.active("A"),[])
 def test_redacted(self):self.e.add(self.m());self.e.forget("A","self","job");self.assertEqual(self.e.memories[0].value,"[REDACTED]")
 def test_no_revival(self):self.e.forget("A","self","job");self.assertEqual(self.e.add(self.m()),"SUPPRESSED_FORGOTTEN")
 def test_restore(self):self.e.forget("A","self","job");self.assertEqual(self.e.add(self.m(),True),"ADD")
 def test_expire(self):self.e.add(self.m(valid_until="2026-01-01T00:00:00Z"));self.assertEqual(self.e.expire("2026-02-01T00:00:00Z"),1)
 def test_future(self):self.e.add(self.m(valid_until="2027-01-01T00:00:00Z"));self.assertEqual(self.e.expire("2026-02-01T00:00:00Z"),0)
 def test_expired_hidden(self):self.e.add(self.m(valid_until="2026-01-01T00:00:00Z"));self.e.expire("2026-02-01T00:00:00Z");self.assertEqual(self.e.active("A"),[])
 def test_expire_idempotent(self):self.e.add(self.m(valid_until="2026-01-01T00:00:00Z"));self.e.expire("2026-02-01T00:00:00Z");self.assertEqual(self.e.expire("2026-02-01T00:00:00Z"),0)
 def test_forget_role_scoped(self):self.e.add(self.m());self.e.add(self.m("x",role="B"));self.e.forget("A","self","job");self.assertEqual(len(self.e.active("B")),1)
