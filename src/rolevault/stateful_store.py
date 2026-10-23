"""RoleVault role-isolated, stateful SQLite reference store.

Local proof of a *possible* enforcement layer, NOT the TeleAgent platform backend.
Caller-provided principal mapping MUST come from a trusted auth service in production.

Privacy: audit stores only operation/slot/turn; revoked and rejected values never
stored in audit or tombstones. SQLite secure_delete mitigates but DOES NOT prove
deletion from backups, filesystem snapshots, logs or external model caches.
"""
from __future__ import annotations
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

PRIVATE_KEY = re.compile(
    r"password|passwd|secret|bank.?account|bank.?card|account_number|"
    r"api.?key|access.?token|reset[ _-]?token|recovery[ _-]?codes?|backup[ _-]?codes?|one[ _-]?time[ _-]?codes?|验证码|身份证|银行卡|银行账号|卡号|密码|私钥|密钥|口令|令牌",
    re.I,
)
PRIVATE_NUMBER = re.compile(r"(?<!\d)(?:\d[ -]?){16,19}(?!\d)|(?<!\d)\d{17}[\dXx](?!\w)")

class NotAuthorized(PermissionError):
    pass

class RejectedSecret(ValueError):
    pass

class ForgottenMemory(ValueError):
    pass

class StatefulRoleStore:
    def __init__(self, db_file: str | Path, trusted_owners: dict[str,str]):
        if not trusted_owners or any(not role or not actor for role,actor in trusted_owners.items()):
            raise ValueError("Explicit trusted role/actor mapping is required")
        self._owner_map=dict(trusted_owners)
        self.db=sqlite3.connect(str(db_file),isolation_level=None,timeout=5)
        self.db.row_factory=sqlite3.Row
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS active_memory(
          role_id TEXT NOT NULL, subject TEXT NOT NULL, slot TEXT NOT NULL,
          value TEXT NOT NULL, source_turn INTEGER NOT NULL,
          effective_at TEXT, evidence_type TEXT NOT NULL,
          PRIMARY KEY(role_id, subject, slot));
        CREATE TABLE IF NOT EXISTS tombstone(
          role_id TEXT NOT NULL, subject TEXT NOT NULL, slot TEXT NOT NULL,
          forgotten_turn INTEGER NOT NULL,
          PRIMARY KEY(role_id, subject, slot));
        CREATE TABLE IF NOT EXISTS action_audit(
          role_id TEXT NOT NULL, subject TEXT NOT NULL, slot TEXT NOT NULL,
          turn_no INTEGER NOT NULL, action TEXT NOT NULL);
        """)
    def __enter__(self):return self
    def __exit__(self,*exc):self.close()
    def close(self):self.db.close()
    @contextmanager
    def _transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
        except BaseException:
            self.db.execute('ROLLBACK')
            raise
        else:
            self.db.execute('COMMIT')
    def _check(self,role:str,actor:str):
        if not role or not actor or self._owner_map.get(role)!=actor:
            raise NotAuthorized("Authenticated actor is not authorized for the role")
    def _record(self,role,subject,slot,turn,action):
        # No original values in audit: a forced cancellation cannot be reconstructed here.
        self.db.execute("INSERT INTO action_audit VALUES(?,?,?,?,?)",
            (role,subject,slot,turn,action))
    def get(self,*,role:str,actor:str,subject:str,slot:str):
        self._check(role,actor)
        row=self.db.execute(
          "SELECT value,source_turn,effective_at,evidence_type FROM active_memory WHERE role_id=? AND subject=? AND slot=?",
          (role,subject,slot)).fetchone()
        return dict(row) if row else None
    def snapshot(self,*,role:str,actor:str):
        self._check(role,actor)
        rows=self.db.execute(
          "SELECT subject,slot,value,source_turn,effective_at,evidence_type "
          "FROM active_memory WHERE role_id=? ORDER BY subject,slot",(role,)).fetchall()
        return [dict(x) for x in rows]
    def upsert(self,*,role:str,actor:str,subject:str,slot:str,value:str,
               turn:int,effective_at:str|None=None,evidence_type:str="owner_statement",
               explicit_restore:bool=False):
        self._check(role,actor)
        if not all([subject,slot,value]) or turn<=0:
            raise ValueError("subject, slot, nonempty value and positive turn required")
        if PRIVATE_KEY.search(slot) or PRIVATE_KEY.search(value) or PRIVATE_NUMBER.search(value):
            # Reject *before* any SQL insert, including audit, to avoid secret persistence.
            raise RejectedSecret("Sensitive credentials cannot enter long-term memory")
        if evidence_type not in ("owner_statement","verified_external"):
            raise ValueError("Untrusted source cannot update role memory")
        with self._transaction():
            forgotten=self.db.execute("SELECT forgotten_turn FROM tombstone WHERE role_id=? AND subject=? AND slot=?",
                (role,subject,slot)).fetchone()
            prev_turn=self.db.execute("SELECT source_turn FROM active_memory WHERE role_id=? AND subject=? AND slot=?",
                (role,subject,slot)).fetchone()
            if (prev_turn and turn<=prev_turn["source_turn"]) or (forgotten and turn<=forgotten["forgotten_turn"]):
                self._record(role,subject,slot,turn,"STALE")
                return "STALE"
            if forgotten and not explicit_restore:
                self._record(role,subject,slot,turn,"SUPPRESSED")
                return "SUPPRESSED"
            prev=self.db.execute("SELECT value FROM active_memory WHERE role_id=? AND subject=? AND slot=?",
                (role,subject,slot)).fetchone()
            if prev is not None and prev["value"]==value:
                # A later trusted reaffirmation advances the causal watermark.
                self.db.execute("""UPDATE active_memory SET source_turn=?,
                    effective_at=?, evidence_type=?
                    WHERE role_id=? AND subject=? AND slot=?""",
                    (turn,effective_at,evidence_type,role,subject,slot))
                self._record(role,subject,slot,turn,"NO_CHANGE")
                return "NO_CHANGE"
            self.db.execute("""INSERT INTO active_memory(role_id,subject,slot,value,source_turn,effective_at,evidence_type)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(role_id,subject,slot) DO UPDATE SET
                value=excluded.value,source_turn=excluded.source_turn,
                effective_at=excluded.effective_at,evidence_type=excluded.evidence_type
                """,(role,subject,slot,value,turn,effective_at,evidence_type))
            if explicit_restore:
                self.db.execute("DELETE FROM tombstone WHERE role_id=? AND subject=? AND slot=?",
                    (role,subject,slot))
            action="UPDATE" if prev is not None else "ADD"
            self._record(role,subject,slot,turn,action)
            return action
    def forget(self,*,role:str,actor:str,subject:str,slot:str,turn:int):
        self._check(role,actor)
        if not subject or not slot or turn<=0:
            raise ValueError("subject, slot and positive turn required")
        with self._transaction():
            active=self.db.execute("SELECT source_turn FROM active_memory WHERE role_id=? AND subject=? AND slot=?", (role,subject,slot)).fetchone()
            tomb=self.db.execute("SELECT forgotten_turn FROM tombstone WHERE role_id=? AND subject=? AND slot=?", (role,subject,slot)).fetchone()
            if (active and turn<=active["source_turn"]) or (tomb and turn<=tomb["forgotten_turn"]):
                self._record(role,subject,slot,turn,"STALE")
                return False
            cur=self.db.execute("DELETE FROM active_memory WHERE role_id=? AND subject=? AND slot=?",
                (role,subject,slot))
            self.db.execute("""INSERT INTO tombstone VALUES(?,?,?,?)
              ON CONFLICT(role_id,subject,slot) DO UPDATE SET forgotten_turn=excluded.forgotten_turn
              """,(role,subject,slot,turn))
            self._record(role,subject,slot,turn,"FORGET" if cur.rowcount else "FORGET_ABSENT")
            return cur.rowcount==1
    def audit(self,*,role:str,actor:str):
        self._check(role,actor)
        return [dict(x) for x in self.db.execute(
           "SELECT subject,slot,turn_no,action FROM action_audit WHERE role_id=? ORDER BY rowid",(role,))]
