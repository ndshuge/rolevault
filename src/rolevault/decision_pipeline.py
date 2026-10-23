"""Authenticated write pipeline. Model action is advisory, never authority."""
from .provenance_guard import enforce
from .stateful_store import NotAuthorized

def apply_decision(gateway, session, *, source, action, subject, slot, value=None, turn):
    gateway._authorize(session)
    if source not in ("owner","authenticated_owner"):
        return "REJECT"
    decision=enforce(source,action)
    if decision=="REJECT": return "REJECT"
    if decision in ("IGNORE","CLARIFY"):return decision
    if decision=="FORGET":
        gateway.forget(session,subject=subject,slot=slot,turn=turn)
        return "FORGET"
    if decision in ("ADD","UPDATE"):
        if not value:raise ValueError("nonempty value required")
        # Neither a model-predicted UPDATE nor ADD may bypass a tombstone.
        return gateway.write(session,subject=subject,slot=slot,value=value,turn=turn)
    raise NotAuthorized("Unsupported action")
