from .trust import score
def decide(old,new):
 if new.source_type not in ("owner_statement","owner_confirmed","verified_tool"): return "REJECT_UNTRUSTED"
 if new.confidence<old.confidence or score(new.source_type)<score(old.source_type): return "KEEP_OLD"
 return "UNCHANGED" if old.value==new.value else "UPDATE"
