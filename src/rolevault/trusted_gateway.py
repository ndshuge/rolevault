"""Trusted boundary for RoleVault SQLite memory operations.

Only a host adapter that has already authenticated the caller may mint a session.
Never construct one from model-produced role/source labels.
"""
from dataclasses import dataclass
from .stateful_store import StatefulRoleStore, NotAuthorized

@dataclass(frozen=True)
class TrustedSession:
    actor: str
    role: str
    provenance: str
    def __post_init__(self):
        if not self.actor or not self.role or self.provenance not in ("authenticated_owner", "authenticated_delegate"):
            raise NotAuthorized("Authenticated identity and trusted provenance required")

class TrustedMemoryGateway:
    def __init__(self, store: StatefulRoleStore, *, trusted_actor_roles: dict[str, str]):
        self._store=store
        self._roles=dict(trusted_actor_roles)

    def _authorize(self, session: TrustedSession):
        if not isinstance(session, TrustedSession) or self._roles.get(session.actor)!=session.role:
            raise NotAuthorized("Caller has no verified role binding")
        # The store performs an independent authorization check.
        self._store._check(session.role, session.actor)

    def read(self, session: TrustedSession, subject: str, slot: str):
        self._authorize(session)
        return self._store.get(role=session.role, actor=session.actor, subject=subject, slot=slot)

    def snapshot(self, session: TrustedSession):
        self._authorize(session)
        return self._store.snapshot(role=session.role, actor=session.actor)

    def write(self, session: TrustedSession, *, subject: str, slot: str, value: str, turn: int,
              effective_at: str | None=None, restore: bool=False):
        self._authorize(session)
        # Source is determined by trusted session, not from untrusted text.
        return self._store.upsert(role=session.role, actor=session.actor, subject=subject,
            slot=slot, value=value, turn=turn, effective_at=effective_at,
            evidence_type="owner_statement", explicit_restore=restore)

    def forget(self, session: TrustedSession, *, subject: str, slot: str, turn: int):
        self._authorize(session)
        return self._store.forget(role=session.role, actor=session.actor, subject=subject, slot=slot, turn=turn)

    def audit(self, session: TrustedSession):
        self._authorize(session)
        return self._store.audit(role=session.role, actor=session.actor)
