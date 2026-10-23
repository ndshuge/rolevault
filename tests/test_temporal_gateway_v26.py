"""Synthetic-only tests for temporal update / post-write readback behavior."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rolevault.temporal_gateway_v26 import TemporalGuardV26
from rolevault.trusted_gateway import TrustedMemoryGateway, TrustedSession
from rolevault.stateful_store import StatefulRoleStore, NotAuthorized, RejectedSecret


class TemporalWriterV26Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = StatefulRoleStore(Path(self.tmp.name) / "role.db",
                                       {"OWNER_A": "trusted-A", "OWNER_B": "trusted-B"})
        self.addCleanup(self.store.close)
        gate = TrustedMemoryGateway(self.store,
                                    trusted_actor_roles={"trusted-A": "OWNER_A",
                                                         "trusted-B": "OWNER_B"})
        self.writer = TemporalGuardV26(gate)
        self.owner = TrustedSession("trusted-A", "OWNER_A", "authenticated_owner")

    def put(self, value, turn=1, date="2026-01-01"):
        return self.writer.write_confirmed(
            self.owner, subject="person", slot="city",
            value=value, turn=turn, effective_at=date)

    def test_first_add_is_actually_written_and_readback_verified(self):
        got = self.put("City A")
        self.assertEqual(got["action"], "ADD")
        self.assertTrue(got["persisted"])
        self.assertTrue(got["readback_verified"])
        self.assertNotEqual(got["pre_sha256"], got["post_sha256"])

    def test_later_confirmed_state_replaces_old(self):
        self.put("City A")
        got = self.put("City B", 2, "2026-03-01")
        self.assertEqual(got["action"], "UPDATE")
        self.assertTrue(got["persisted"])
        self.assertEqual(self.store.get(role="OWNER_A", actor="trusted-A",
                                        subject="person", slot="city")["value"], "City B")

    def test_late_arriving_old_event_cannot_override_new_state(self):
        self.put("Current", 1, "2026-03-01")
        got = self.put("Past", 2, "2026-02-01")
        self.assertEqual(got["action"], "STALE_EFFECTIVE_TIME")
        self.assertFalse(got["persisted"])
        self.assertEqual(self.store.get(role="OWNER_A", actor="trusted-A",
                                        subject="person", slot="city")["value"], "Current")

    def test_equal_effective_date_conflict_blocks_write(self):
        self.put("Current", 1, "2026-03-01")
        got = self.put("Conflict", 2, "2026-03-01")
        self.assertEqual(got["action"], "CONFLICT_SAME_EFFECTIVE_TIME")
        self.assertFalse(got["persisted"])

    def test_undated_conflict_preserves_dated_fact(self):
        self.put("Current", 1, "2026-03-01")
        got = self.put("Undated", 2, None)
        self.assertEqual(got["action"], "CLARIFY_TIME")
        self.assertFalse(got["persisted"])

    def test_forget_removes_and_old_replay_cannot_resurrect(self):
        self.put("City A")
        receipt = self.writer.forget_confirmed(
            self.owner, subject="person", slot="city", turn=2)
        self.assertTrue(receipt["persisted"])
        self.assertTrue(receipt["active_value_absent"])
        again = self.put("City A", 3, "2026-04-01")
        self.assertEqual(again["action"], "SUPPRESSED")
        self.assertFalse(again["persisted"])

    def test_credentials_fail_before_storage(self):
        with self.assertRaises(RejectedSecret):
            self.put("API key: demo", 1, "2026-01-01")
        self.assertEqual(self.store.snapshot(role="OWNER_A", actor="trusted-A"), [])

    def test_foreign_role_cannot_read_or_write(self):
        forged = TrustedSession("trusted-B", "OWNER_A", "authenticated_owner")
        with self.assertRaises(NotAuthorized):
            self.writer.write_confirmed(forged, subject="person", slot="city",
                                        value="no", turn=1, effective_at="2026-01-01")

    def test_invalid_date_is_not_silently_accepted(self):
        with self.assertRaisesRegex(ValueError, "expected_yyyy_mm_dd"):
            self.put("City A", date="next spring")


if __name__ == "__main__":
    unittest.main()
