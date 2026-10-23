"""RoleVault V2.7 Fusion: conservative temporal admission and readback gate.

Local reference implementation only: NOT a TeleAgent native backend, and
NOT proof of account-global memory separation. The authenticated TrustedSession
must come from an independent host; labels in chat text are untrusted.

This layer guards one subject/slot write at a time. It does NOT claim to
provide cross-slot atomic transactions, model semantic correctness, external
cache erasure, or a distributed compare-and-swap transaction.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Literal

from .trusted_gateway import TrustedMemoryGateway, TrustedSession
from .stateful_store import PRIVATE_KEY, PRIVATE_NUMBER, RejectedSecret

Assertion = Literal["confirmed", "planned", "rumor", "uncertain"]
Chronology = Literal["explicit_current", "historical", "unspecified"]


def parse_effective(value: str | None) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("expected_yyyy_mm_dd")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("expected_yyyy_mm_dd") from exc


def sha_state(data: dict | None) -> str:
    serialized = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FactAssessment:
    """Semantic assessment supplied by a separately verified extraction step.

    "explicit_current" means an affirmative now/has-changed statement, not
    merely text arriving in a later message. The caller is responsible for
    interpreting the natural language; this class cannot authenticate a quote.
    """
    assertion: Assertion = "confirmed"
    chronology: Chronology = "unspecified"
    effective_at: str | None = None


class FusionTemporalGatewayV27:
    def __init__(self, gateway: TrustedMemoryGateway):
        self.gateway = gateway

    def write(self, session: TrustedSession, *, subject: str, slot: str,
              value: str, turn: int, assessment: FactAssessment) -> dict:
        # Check host-supplied identity even on IGNORE/CLARIFY paths.
        self.gateway._authorize(session)
        if not isinstance(assessment, FactAssessment) or assessment.assertion not in (
            "confirmed", "planned", "rumor", "uncertain"
        ) or assessment.chronology not in ("explicit_current", "historical", "unspecified"):
            raise ValueError("invalid_semantic_assessment")
        if not subject or not slot or not isinstance(value, str) or not value or turn <= 0:
            raise ValueError("invalid_fact_fields")
        # Reject secrets before any action, including accidental attempted audit.
        if PRIVATE_KEY.search(slot) or PRIVATE_KEY.search(value) or PRIVATE_NUMBER.search(value):
            raise RejectedSecret("Sensitive credentials cannot enter long-term memory")
        next_date = parse_effective(assessment.effective_at)
        old = self.gateway.read(session, subject, slot)
        prev_hash = sha_state(old)
        def stop(reason: str) -> dict:
            return {"action": reason, "persisted": False, "readback_verified": False,
                    "pre_sha256": prev_hash, "post_sha256": prev_hash}

        if assessment.assertion == "rumor":
            return stop("IGNORE_UNVERIFIED_SOURCE")
        if assessment.assertion in ("planned", "uncertain"):
            return stop("CLARIFY" if old is not None else "IGNORE_UNCONFIRMED")
        if assessment.chronology == "historical":
            return stop("HISTORICAL_NOT_CURRENT")
        if old:
            old_turn = int(old["source_turn"])
            old_date = parse_effective(old.get("effective_at"))
            if turn < old_turn:
                return stop("STALE_TURN")
            if turn == old_turn:
                if old["value"] == value and old_date == next_date:
                    return {"action": "ALREADY_APPLIED", "persisted": True,
                            "readback_verified": True, "pre_sha256": prev_hash,
                            "post_sha256": prev_hash}
                return stop("CONFLICT_SAME_TURN")
            # The date ordering guard applies even when the textual value
            # repeats: otherwise the source date could silently move backward.
            if old_date is not None and next_date is not None:
                if next_date < old_date:
                    return stop("STALE_EFFECTIVE_TIME")
                if next_date == old_date and value != old["value"]:
                    return stop("CLARIFY_SAME_EFFECTIVE_TIME")
            if old["value"] == value:
                # Repeated identical information is not a changed fact.
                # Preserve the original effective date and source-turn watermark.
                return {"action": "NO_CHANGE", "persisted": True,
                        "readback_verified": True, "pre_sha256": prev_hash,
                        "post_sha256": prev_hash}
            # A confirmed, explicit, current owner statement can update even
            # without ISO dates; otherwise a dated old fact is protected.
            if old_date is not None and next_date is None:
                if assessment.chronology != "explicit_current":
                    return stop("CLARIFY_TIME")
            if old_date is None and next_date is None:
                if assessment.chronology != "explicit_current":
                    return stop("CLARIFY_CHRONOLOGY")
        # Rely on gateway/store's trusted role binding + SQL transaction +
        # tombstone suppression. Deliberate restore is a separate capability.
        action = self.gateway.write(session, subject=subject, slot=slot,
                                    value=value, turn=turn,
                                    effective_at=assessment.effective_at)
        after = self.gateway.read(session, subject, slot)
        valid_action = action in ("ADD", "UPDATE")
        verified = bool(valid_action and after and after["value"] == value
                        and after["source_turn"] == turn
                        and after["effective_at"] == assessment.effective_at)
        return {"action": action, "persisted": verified,
                "readback_verified": verified, "pre_sha256": prev_hash,
                "post_sha256": sha_state(after)}

    def forget(self, session: TrustedSession, *, subject: str, slot: str,
               turn: int) -> dict:
        self.gateway._authorize(session)
        if not subject or not slot or turn <= 0:
            raise ValueError("invalid_forget_fields")
        before = self.gateway.read(session, subject, slot)
        pre_hash = sha_state(before)
        deleted = self.gateway.forget(session, subject=subject, slot=slot, turn=turn)
        after = self.gateway.read(session, subject, slot)
        # No raw deleted value is emitted to audit; tombstone is stored by the
        # underlying reference store, while external caches are out of scope.
        success = bool(before is not None and deleted and after is None)
        return {"action": "FORGET" if success else "FORGET_ABSENT_OR_STALE",
                "persisted": success, "readback_verified": success,
                "active_value_absent": after is None, "pre_sha256": pre_hash,
                "post_sha256": sha_state(after)}
