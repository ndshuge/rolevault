from .memory import MemoryStatus
from .timeline import expired
from .conflict import decide
class MemoryLifecycleEngine:
 def __init__(self): self.memories=[];self.tombstones=set()
 def key(self,m): return (m.role_id,m.subject,m.attribute)
 def add(self,m,explicit_restore=False):
  k=self.key(m)
  if m.source_type not in ("owner_statement","owner_confirmed","verified_tool"): return "REJECT_UNTRUSTED"
  if k in self.tombstones and not explicit_restore:return "SUPPRESSED_FORGOTTEN"
  active=[x for x in self.memories if self.key(x)==k and x.status==MemoryStatus.ACTIVE]
  if len(active)>1:raise RuntimeError("duplicate active")
  if active:
   old=active[0];decision=decide(old,m)
   if decision!="UPDATE":return decision
   old.status=MemoryStatus.SUPERSEDED;old.replaced_by=m.value
  m.status=MemoryStatus.ACTIVE;self.memories.append(m)
  if explicit_restore:self.tombstones.discard(k)
  return "UPDATE" if active else "ADD"
 def forget(self,role,subject,attribute):
  k=(role,subject,attribute);self.tombstones.add(k);n=0
  for m in self.memories:
   if self.key(m)==k and m.status==MemoryStatus.ACTIVE:
    m.status=MemoryStatus.FORGOTTEN;m.value="[REDACTED]";n+=1
  return n
 def expire(self,now):
  n=0
  for m in self.memories:
   if m.status==MemoryStatus.ACTIVE and expired(m,now):m.status=MemoryStatus.EXPIRED;n+=1
  return n
 def active(self,role):return [m for m in self.memories if m.role_id==role and m.status==MemoryStatus.ACTIVE]
