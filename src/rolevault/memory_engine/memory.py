from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

class MemoryStatus(str, Enum):
    ACTIVE='ACTIVE'
    SUPERSEDED='SUPERSEDED'
    FORGOTTEN='FORGOTTEN'
    EXPIRED='EXPIRED'

@dataclass
class MemoryObject:
    role_id: str
    subject: str
    attribute: str
    value: str
    source_type: str = 'owner_statement'
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    valid_until: str | None = None
    status: MemoryStatus = MemoryStatus.ACTIVE
    replaced_by: str | None = None
