import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from rolevault.stateful_store import StatefulRoleStore,NotAuthorized,RejectedSecret
from rolevault.trusted_gateway import TrustedMemoryGateway,TrustedSession
from rolevault.decision_pipeline import apply_decision
class PipelineTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.store=StatefulRoleStore(Path(self.tmp.name)/"db.sqlite",{"A":"alice","B":"bob"})
  self.g=TrustedMemoryGateway(self.store,trusted_actor_roles={"alice":"A","bob":"B"})
  self.a=TrustedSession("alice","A","authenticated_owner")
  self.b=TrustedSession("bob","B","authenticated_owner")
 def tearDown(self):self.store.close();self.tmp.cleanup()
 def run_action(self,session=None,source="owner",action="ADD",value="engineer",turn=1):
  return apply_decision(self.g,session or self.a,source=source,action=action,subject="self",slot="job",value=value,turn=turn)
 def test_add(self):self.assertEqual(self.run_action(),"ADD")
 def test_update(self):
  self.run_action()
  self.assertEqual(self.run_action(action="UPDATE",value="architect",turn=2),"UPDATE")
  self.assertEqual(self.g.read(self.a,"self","job")["value"],"architect")
 def test_external_update(self):
  self.run_action()
  self.assertEqual(self.run_action(source="third_party",action="UPDATE",value="fake",turn=2),"REJECT")
  self.assertEqual(self.g.read(self.a,"self","job")["value"],"engineer")
 def test_external_forget(self):
  self.run_action()
  self.assertEqual(self.run_action(source="rumor",action="FORGET",turn=2),"REJECT")
  self.assertIsNotNone(self.g.read(self.a,"self","job"))
 def test_unknown_source(self):self.assertEqual(self.run_action(source="model_claim_owner"),"REJECT")
 def test_secret(self):
  with self.assertRaises(RejectedSecret):self.run_action(value="reset token: blue-river")
 def test_forget(self):
  self.run_action()
  self.assertEqual(self.run_action(action="FORGET",turn=2),"FORGET")
  self.assertIsNone(self.g.read(self.a,"self","job"))
 def test_no_revival(self):
  self.run_action();self.run_action(action="FORGET",turn=2)
  self.assertEqual(self.run_action(turn=3),"SUPPRESSED")
 def test_cross_role(self):
  with self.assertRaises(NotAuthorized):
   self.run_action(session=TrustedSession("alice","B","authenticated_owner"))
 def test_other_role_untouched(self):
  self.run_action();self.run_action(session=self.b,value="designer")
  self.run_action(action="FORGET",turn=2)
  self.assertEqual(self.g.read(self.b,"self","job")["value"],"designer")
 def test_ignore(self):self.assertEqual(self.run_action(action="IGNORE"),"IGNORE")
 def test_clarify(self):self.assertEqual(self.run_action(action="CLARIFY"),"CLARIFY")
 def test_audit_no_value(self):
  self.run_action(value="special-profession")
  self.assertNotIn("special-profession",str(self.g.audit(self.a)))
