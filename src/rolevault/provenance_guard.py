"""Fail-closed provenance guard applied before any model action is accepted.
This is a reference policy: source labels must be supplied by a trusted host.
"""
VALID={"ADD","UPDATE","FORGET","REJECT","IGNORE","CLARIFY"}
TRUSTED={"owner","authenticated_owner"}
UNTRUSTED={"third_party","rumor","web","tool_unverified"}
def enforce(source, proposed_action):
    if source not in TRUSTED:
        return "REJECT"
    if proposed_action not in VALID:
        return "REJECT"
    return proposed_action
