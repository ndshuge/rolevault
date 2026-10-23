"""S3 regression: explicit forgetting cannot be silently undone by stale citations."""
import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from rolevault.core import RoleMemory,AccessDenied,ROLE,OWNER
class ForgettingSuppressionTests(unittest.TestCase):
    def test_stale_reappearance_suppressed(self):
        db=RoleMemory()
        db.upsert("training.plan","考资格考试",1)
        self.assertTrue(db.forget("training.plan",2))
        self.assertEqual(db.upsert("training.plan","考资格考试",3),"SUPPRESSED_FORGOTTEN")
        self.assertNotIn("training.plan",db.snapshot())
        self.assertIn((ROLE,"training.plan"),db.tombstones)
        self.assertNotIn("考资格考试",repr(db.audit))
    def test_explicit_verified_reauthorization_restores(self):
        db=RoleMemory()
        db.upsert("plan","旧安排",1)
        db.forget("plan",2)
        self.assertEqual(db.upsert("plan","新安排",3,explicit_restore=True),"ADD")
        self.assertEqual(db.snapshot()["plan"]["value"],"新安排")
        self.assertNotIn((ROLE,"plan"),db.tombstones)
    def test_restoration_flag_cannot_override_auth(self):
        db=RoleMemory()
        db.upsert("plan","秘密安排",1)
        db.forget("plan",2)
        with self.assertRaises(AccessDenied):
            db.upsert("plan","攻击者安排",3,actor="stranger",explicit_restore=True)
        self.assertNotIn("plan",db.snapshot())
    def test_per_role_tombstone_is_scoped(self):
        db=RoleMemory()
        db.register_role("OTHER","owner:other",actor="admin:trusted")
        db.upsert("goal","role-one",1)
        db.upsert("goal","role-two",1,actor="owner:other",role="OTHER")
        db.forget("goal",2)
        self.assertEqual(db.snapshot("OTHER","owner:other")["goal"]["value"],"role-two")
        self.assertEqual(db.upsert("goal","role-one",3),"SUPPRESSED_FORGOTTEN")
        self.assertIn("goal",db.snapshot("OTHER","owner:other"))
