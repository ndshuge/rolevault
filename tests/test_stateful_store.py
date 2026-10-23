"""Stateful multi-turn memory quality and security: isolated SQLite reference store.

Never implies native TeleAgent persistence/isolation has passed these tests.
"""
import json, sqlite3, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from rolevault.stateful_store import StatefulRoleStore, NotAuthorized, RejectedSecret

OWNERS={"LIMING":"authenticated:owner-1","ALICE":"authenticated:owner-2"}
def owner(store,role="LIMING"):
    return {"role":role,"actor":OWNERS[role]}
class StatefulRoleStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.dbpath=Path(self.temp.name)/"role.sqlite3"
        self.s=StatefulRoleStore(self.dbpath,OWNERS)
    def tearDown(self):
        self.s.close()
        self.temp.cleanup()
    def up(self,slot,value,n,role="LIMING",subject="self",**extras):
        return self.s.upsert(subject=subject,slot=slot,value=value,turn=n,**owner(self.s,role),**extras)
    def read(self,slot,role="LIMING",subject="self"):
        return self.s.get(subject=subject,slot=slot,**owner(self.s,role))
    def test_multi_turn_work_home_qualification_and_deletion(self):
        self.assertEqual(self.up("work.employer","海松软件",1),"ADD")
        self.up("work.title","后端工程师",1)
        self.up("home.area","松山区",2)
        self.up("commute.route","驾车走滨江大道",2)
        self.up("learning.goal","准备PMP证书",3)
        self.assertEqual(self.up("work.employer","辰光科技",4),"UPDATE")
        self.up("work.title","高级架构师",4)
        self.assertEqual(self.up("home.area","海湾新区",5),"UPDATE")
        self.assertEqual(self.up("commute.route","地铁2号线",5),"UPDATE")
        self.up("credential.award_name","PMP认证",6)  # ordinary credential? Sensitive regex might reject.
        self.s.forget(subject="self",slot="learning.goal",turn=6,**owner(self.s))
        self.assertEqual(self.read("work.employer")["value"],"辰光科技")
        self.assertEqual(self.read("commute.route")["value"],"地铁2号线")
        self.assertNotIn("海松软件",repr(self.s.snapshot(**owner(self.s))))
        self.assertNotIn("驾车走滨江大道",repr(self.s.snapshot(**owner(self.s))))
        self.assertIsNone(self.read("learning.goal"))
    def test_forget_then_stale_source_does_not_reappear(self):
        self.up("pending.interview","下周联系面试官",1)
        self.assertTrue(self.s.forget(subject="self",slot="pending.interview",turn=2,**owner(self.s)))
        self.assertEqual(self.up("pending.interview","下周联系面试官",3),"SUPPRESSED")
        self.assertIsNone(self.read("pending.interview"))
        self.assertEqual(self.up("pending.interview","新机会已经主人明确重新授权",4,explicit_restore=True),"ADD")
        self.assertIn("重新授权",self.read("pending.interview")["value"])
    def test_cross_role_negative_and_own_facts(self):
        self.up("spouse.work","设计师",1,role="ALICE")
        self.up("spouse.work","产品总监",1,role="LIMING")
        self.assertEqual(self.read("spouse.work","ALICE")["value"],"设计师")
        self.assertNotIn("设计师",repr(self.s.snapshot(**owner(self.s,"LIMING"))))
        with self.assertRaises(NotAuthorized):
            self.s.snapshot(role="LIMING",actor="authenticated:owner-2")
        with self.assertRaises(NotAuthorized):
            self.s.get(role="ALICE",actor="authenticated:owner-1",subject="self",slot="spouse.work")
        with self.assertRaises(NotAuthorized):
            self.s.upsert(role="ALICE",actor="authenticated:owner-1",subject="self",slot="spouse.work",value="劫持",turn=2)
    def test_secret_rejection_before_storage_and_audit(self):
        for key,value in (("profile.password","small-secret"),("personal.bank_card","not-a-number"),
                          ("credential.api_key","sk-example-string"),
                          ("notes","登录密码是SyntheticPass123!"),
                          ("notes","身份证号11010119900101001X")):
            with self.assertRaises(RejectedSecret):
                self.up(key,value,3)
        self.assertEqual(self.s.snapshot(**owner(self.s)),[])
        self.assertEqual(self.s.audit(**owner(self.s)),[])
    def test_untrusted_source_rejected_even_if_actor_is_owner(self):
        with self.assertRaises(ValueError):
            self.up("work.title","传闻博士",2,evidence_type="forwarded_web")
        self.assertIsNone(self.read("work.title"))
    def test_forgotten_data_not_in_active_db_or_audit(self):
        self.up("pending.offer","不得复活的职位机会",1)
        self.s.forget(subject="self",slot="pending.offer",turn=2,**owner(self.s))
        self.assertNotIn("不得复活的职位机会",repr(self.s.snapshot(**owner(self.s))))
        self.assertNotIn("不得复活的职位机会",repr(self.s.audit(**owner(self.s))))
        self.assertNotIn("不得复活的职位机会",repr(list(self.s.db.execute("SELECT * FROM tombstone"))))
    def test_persistence_and_role_boundaries_after_restart(self):
        self.up("work.title","架构师",1)
        self.up("work.title","平面设计师",1,role="ALICE")
        self.s.close()
        self.s=StatefulRoleStore(self.dbpath,OWNERS)
        self.assertEqual(self.read("work.title")["value"],"架构师")
        self.assertEqual(self.read("work.title",role="ALICE")["value"],"平面设计师")
    def test_irrelevant_interference_does_not_mutate_target_slot(self):
        self.up("work.title","系统工程师",1)
        for i in range(2,82):
            self.up(f"interest.item_{i}","同主体的其他互不相干的事实",i)
        self.assertEqual(self.read("work.title")["value"],"系统工程师")
        self.assertEqual(len(self.s.snapshot(**owner(self.s))),81)
    def test_no_actor_is_not_owner_by_default(self):
        with self.assertRaises(NotAuthorized):
            self.s.snapshot(role="LIMING",actor=None)
        with self.assertRaises(NotAuthorized):
            self.s.upsert(role="LIMING",actor=None,subject="self",slot="x",value="y",turn=1)
    def test_failed_credential_operation_preserves_prior_value(self):
        self.up("work.title","现任工程师",1)
        with self.assertRaises(RejectedSecret):
            self.up("work.title","银行密码是123456",2)
        self.assertEqual(self.read("work.title")["value"],"现任工程师")
if __name__=="__main__":unittest.main()
