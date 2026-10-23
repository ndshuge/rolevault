from datetime import datetime,timezone
def parse_time(v):
 d=datetime.fromisoformat(v.replace("Z","+00:00"))
 return (d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d).astimezone(timezone.utc)
def expired(m,now):
 return m.valid_until is not None and parse_time(now)>=parse_time(m.valid_until)
