"""Optional V2.6 reference wrapper for dated role-memory writes.

Inspired by temporal-memory invalidation and write-then-readback verification.
Does not modify existing TeleAgent rules, role output, or live account memory.
Requires an independently authenticated TrustedSession; not a stand-in for auth.
This wrapper is a reference QA tool, not an atomic cross-process CAS system.
"""
from __future__ import annotations

from datetime import date
import hashlib
import json

from .trusted_gateway import TrustedMemoryGateway, TrustedSession


class TemporalGuardV26:
    def __init__(self, gateway: TrustedMemoryGateway):
        self.gateway = gateway

    @staticmethod
    def _parse_effective(value: str | None) -> date | None:
        if value is None:
            return None
        if not isinstance(value, str) or len(value) != 10:
            raise ValueError("expected_yyyy_mm_dd")
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("expected_yyyy_mm_dd") from exc

    @staticmethod
    def _hash(value: dict | None) -> str:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def write_confirmed(self, session: TrustedSession, *, subject: str, slot: str,
                        value: str, turn: int, effective_at: str | None) -> dict:
        # Read uses gateway's independently configured actor-role binding.
        old = self.gateway.read(session, subject, slot)
        next_date = self._parse_effective(effective_at)
        old_date = self._parse_effective(old.get("effective_at")) if old else None
        if old and old.get("value") != value:
            if old_date is not None and next_date is None:
                return {"action": "CLARIFY_TIME", "persisted": False}
            if old_date is not None and next_date is not None:
                if next_date < old_date:
                    return {"action": "STALE_EFFECTIVE_TIME", "persisted": False}
                if next_date == old_date:
                    return {"action": "CONFLICT_SAME_EFFECTIVE_TIME", "persisted": False}
        # Default gateway.write never sets restore=True. Tombstones cannot be
        # cleared merely because untrusted text claims to be "system".
        action = self.gateway.write(session, subject=subject, slot=slot,
                                    value=value, turn=turn, effective_at=effective_at)
        after = self.gateway.read(session, subject, slot)
        expected_action = action in {"ADD", "UPDATE", "NO_CHANGE"}
        verified = bool(expected_action and after and
                        after["value"] == value and after["source_turn"] == turn
                        and after["effective_at"] == effective_at)
        return {
            "action": action,
            "persisted": verified,
            "pre_sha256": self._hash(old),
            "post_sha256": self._hash(after),
            "readback_verified": verified,
        }

    def forget_confirmed(self, session: TrustedSession, *, subject: str,
                         slot: str, turn: int) -> dict:
        old = self.gateway.read(session, subject, slot)
        deleted = self.gateway.forget(session, subject=subject, slot=slot, turn=turn)
        after = self.gateway.read(session, subject, slot)
        return {
            "action": "FORGET" if deleted else "FORGET_OR_STALE",
            "persisted": bool(deleted and old and after is None),
            "active_value_absent": after is None,
            "pre_sha256": self._hash(old),
            "post_sha256": self._hash(after),
        }
