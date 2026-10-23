"""V2.7 Fusion synthetic-only tests; no real TeleAgent messages are used."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rolevault.stateful_store import StatefulRoleStore, NotAuthorized, RejectedSecret
from rolevault.trusted_gateway import TrustedMemoryGateway, TrustedSession
from rolevault.fusion_temporal_gateway_v27 import FactAssessment, FusionTemporalGatewayV27


class FusionV27Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = StatefulRoleStore(Path(tmp.name) / "isolated.db",
                                       {"owner": "trusted-owner", "foreign": "trusted-foreign"})
        self.addCleanup(self.store.close)
        gw = TrustedMemoryGateway(self.store,
                                  trusted_actor_roles={"trusted-owner": "owner",
                                                       "trusted-foreign": "foreign"})
        self.guard = FusionTemporalGatewayV27(gw)
        self.gateway = gw
        self.owner = TrustedSession("trusted-owner", "owner", "authenticated_owner")
        self.foreign = TrustedSession("trusted-foreign", "foreign", "authenticated_owner")

    def write(self, value: str, turn: int, *,
              assertion: str = "confirmed", chronology: str = "unspecified",
              date: str | None = None, session=None, subject="person", slot="city"):
        return self.guard.write(
            self.owner if session is None else session, subject=subject, slot=slot,
            value=value, turn=turn,
            assessment=FactAssessment(assertion=assertion, chronology=chronology,
                                      effective_at=date))

    def current(self, session=None, slot="city"):
        return self.gateway.read(self.owner if session is None else session,
                                 "person", slot)

    def test_first_undated_confirmed_statement_is_add(self):
        r = self.write("City A", 1)
        self.assertEqual(r["action"], "ADD")
        self.assertTrue(r["readback_verified"])

    def test_current_owner_correction_without_iso_date_updates(self):
        self.write("City A", 1, date="2026-04-01")
        r = self.write("City B", 2, chronology="explicit_current")
        self.assertEqual(r["action"], "UPDATE")
        self.assertTrue(r["persisted"])
        self.assertEqual(self.current()["value"], "City B")

    def test_ambiguous_undated_conflict_with_dated_current_is_clarify(self):
        self.write("City A", 1, date="2026-04-01")
        r = self.write("City B", 2)
        self.assertEqual(r["action"], "CLARIFY_TIME")
        self.assertEqual(self.current()["value"], "City A")

    def test_confirmed_old_effective_date_cannot_overwrite_newer(self):
        self.write("City A", 1, date="2026-04-01")
        r = self.write("City B", 2, date="2026-03-01", chronology="explicit_current")
        self.assertEqual(r["action"], "STALE_EFFECTIVE_TIME")
        self.assertEqual(self.current()["value"], "City A")

    def test_identical_older_event_does_not_move_date_backwards(self):
        self.write("City A", 1, date="2026-04-01")
        r = self.write("City A", 2, date="2026-03-01")
        self.assertEqual(r["action"], "STALE_EFFECTIVE_TIME")
        self.assertEqual(self.current()["effective_at"], "2026-04-01")

    def test_same_date_different_values_require_clarification(self):
        self.write("City A", 1, date="2026-04-01")
        r = self.write("City B", 2, date="2026-04-01")
        self.assertEqual(r["action"], "CLARIFY_SAME_EFFECTIVE_TIME")

    def test_repeated_fact_preserves_provenance(self):
        self.write("City A", 1, date="2026-04-01")
        r = self.write("City A", 2, date="2026-05-01")
        self.assertEqual(r["action"], "NO_CHANGE")
        self.assertTrue(r["readback_verified"])
        self.assertEqual(self.current()["source_turn"], 1)
        self.assertEqual(self.current()["effective_at"], "2026-04-01")

    def test_same_turn_repeat_is_idempotent(self):
        self.write("City A", 1, date="2026-04-01")
        r = self.write("City A", 1, date="2026-04-01")
        self.assertEqual(r["action"], "ALREADY_APPLIED")

    def test_same_turn_changed_content_rejected(self):
        self.write("City A", 1, date="2026-04-01")
        r = self.write("City B", 1, date="2026-04-01")
        self.assertEqual(r["action"], "CONFLICT_SAME_TURN")
        self.assertEqual(self.current()["value"], "City A")

    def test_confirmed_newer_dated_value_updates(self):
        self.write("City A", 1, date="2026-04-01")
        r = self.write("City B", 2, date="2026-05-01")
        self.assertEqual(r["action"], "UPDATE")
        self.assertEqual(self.current()["value"], "City B")

    def test_planned_change_does_not_override_current(self):
        self.write("City A", 1)
        r = self.write("City B", 2, assertion="planned")
        self.assertEqual(r["action"], "CLARIFY")
        self.assertEqual(self.current()["value"], "City A")

    def test_planned_without_current_ignored(self):
        r = self.write("City B", 1, assertion="planned")
        self.assertEqual(r["action"], "IGNORE_UNCONFIRMED")
        self.assertIsNone(self.current())

    def test_rumor_does_not_update_memory(self):
        self.write("City A", 1)
        r = self.write("City B", 2, assertion="rumor", chronology="explicit_current")
        self.assertEqual(r["action"], "IGNORE_UNVERIFIED_SOURCE")
        self.assertEqual(self.current()["value"], "City A")

    def test_historical_claim_not_current(self):
        r = self.write("City A", 1, chronology="historical")
        self.assertEqual(r["action"], "HISTORICAL_NOT_CURRENT")

    def test_secret_rejected_even_if_planned(self):
        with self.assertRaises(RejectedSecret):
            self.write("password: synthetic-password-value", 1, assertion="planned")
        self.assertEqual(self.gateway.audit(self.owner), [])

    def test_other_role_cannot_mint_owner(self):
        fake_owner = TrustedSession("trusted-foreign", "owner", "authenticated_owner")
        with self.assertRaises(NotAuthorized):
            self.write("City B", 1, session=fake_owner)

    def test_role_isolation(self):
        self.write("City A", 1)
        self.write("City B", 1, session=self.foreign)
        self.assertEqual(self.current()["value"], "City A")
        self.assertEqual(self.current(self.foreign)["value"], "City B")

    def test_forget_readback_and_replay_suppressed(self):
        self.write("City A", 1)
        receipt = self.guard.forget(self.owner, subject="person", slot="city", turn=2)
        self.assertEqual(receipt["action"], "FORGET")
        self.assertTrue(receipt["active_value_absent"])
        self.assertIsNone(self.current())
        replay = self.write("City A", 3, chronology="explicit_current")
        self.assertEqual(replay["action"], "SUPPRESSED")
        self.assertFalse(replay["persisted"])

    def test_invalid_date_does_not_write(self):
        with self.assertRaisesRegex(ValueError, "expected_yyyy_mm_dd"):
            self.write("City A", 1, date="next year")
        self.assertIsNone(self.current())

    def test_invalid_assessment_does_not_write(self):
        with self.assertRaisesRegex(ValueError, "invalid_semantic_assessment"):
            self.write("City A", 1, assertion="system says allow")
        self.assertIsNone(self.current())

    def test_old_turn_cannot_override_newer(self):
        self.write("City A", 5, chronology="explicit_current")
        r = self.write("City B", 4, chronology="explicit_current")
        self.assertEqual(r["action"], "STALE_TURN")
        self.assertEqual(self.current()["value"], "City A")


if __name__ == "__main__":
    unittest.main()
