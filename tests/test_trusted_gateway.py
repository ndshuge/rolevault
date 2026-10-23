import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from rolevault.stateful_store import StatefulRoleStore,NotAuthorized
from rolevault.trusted_gateway import TrustedSession,TrustedMemoryGateway
class GatewayTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.store=StatefulRoleStore(Path(self.tmp.name)/"a.db",{"A":"alice","B":"bob"})
  self.g=TrustedMemoryGateway(self.store,trusted_actor_roles={"alice":"A","bob":"B"})
  self.a=TrustedSession("alice","A","authenticated_owner")
  self.b=TrustedSession("bob","B","authenticated_owner")
 def tearDown(self):self.store.close();self.tmp.cleanup()
 def test_owner_write_read(self):
  self.assertEqual(self.g.write(self.a,subject="self",slot="job",value="engineer",turn=1),"ADD")
  self.assertEqual(self.g.read(self.a,"self","job")["value"],"engineer")
 def test_cross_role_rejected(self):
  with self.assertRaises(NotAuthorized):self.g.snapshot(TrustedSession("alice","B","authenticated_owner"))
 def test_missing_session(self):
  with self.assertRaises(NotAuthorized):self.g.snapshot(None)
 def test_untrusted_provenance(self):
  with self.assertRaises(NotAuthorized):TrustedSession("alice","A","model_claim")
 def test_role_separation(self):
  self.g.write(self.a,subject="self",slot="job",value="Ajob",turn=1)
  self.g.write(self.b,subject="self",slot="job",value="Bjob",turn=1)
  self.assertEqual(self.g.snapshot(self.a)[0]["value"],"Ajob")
  self.assertEqual(self.g.snapshot(self.b)[0]["value"],"Bjob")
 def test_forget(self):
  self.g.write(self.a,subject="self",slot="job",value="engineer",turn=1)
  self.g.forget(self.a,subject="self",slot="job",turn=2)
  self.assertIsNone(self.g.read(self.a,"self","job"))
 def test_tombstone(self):
  self.g.forget(self.a,subject="self",slot="job",turn=1)
  self.assertEqual(self.g.write(self.a,subject="self",slot="job",value="engineer",turn=2),"SUPPRESSED")
 def test_audit_no_value(self):
  self.g.write(self.a,subject="self",slot="job",value="engineer",turn=1)
  self.assertNotIn("engineer",str(self.g.audit(self.a)))
