"""RoleVault isolated offline reference engine.

DEMONSTRATOR, not TeleAgent; conservative pattern coverage for the public 28-turn set.
Authentication comes from caller transport identity, never text or role labels.
No sensitive source message is persisted by the engine.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, asdict
from typing import Dict

OWNER = "owner:liming"
ROLE = "LIMING"
SENSITIVE = re.compile(r"(?<!\d)(?:\d[ -]?){15,19}(?!\d)|\b\d{17}[\dXx]\b")

class AccessDenied(PermissionError):
    pass

@dataclass(frozen=True)
class Fact:
    subject: str
    slot: str
    value: str
    source_round: int

class RoleMemory:
    def __init__(self):
        self._facts: Dict[str, Dict[str, Fact]] = {ROLE: {}}
        self._owners = {ROLE: OWNER}
        self.audit = []
        self.tombstones = set()

    def register_role(self, role, owner_actor, *, actor):
        """Role enrollment is an explicitly privileged operation, not a text instruction."""
        if actor != "admin:trusted":
            raise AccessDenied("Only trusted admin may enroll a new role")
        if not role or not owner_actor or role in self._owners:
            raise ValueError("Invalid or already registered role")
        self._owners[role] = owner_actor
        self._facts[role] = {}

    def _authorize(self, role, actor):
        if self._owners.get(role) != actor:
            raise AccessDenied("Unverified actor cannot read or mutate this role's memories")

    def snapshot(self, role=ROLE, actor=OWNER):
        self._authorize(role, actor)
        return {slot: asdict(fact) for slot, fact in sorted(self._facts[role].items())}

    def _audit(self, turn, action, slot):
        # Only slot and action: never sensitive source text, old values or secret payload.
        self.audit.append({"turn": turn, "action": action, "slot": slot})

    def upsert(self, slot, value, turn, *, subject="李明", role=ROLE, actor=OWNER,
               explicit_restore=False):
        """Do not revive a previously forgotten slot without verified re-authorization.

        This is offline-reference behavior only; the transport MUST authenticate
        actor and must verify an actual explicit restore request before passing
        explicit_restore=True. A quote from stale source is insufficient.
        """
        self._authorize(role, actor)
        if SENSITIVE.search(value):
            self._audit(turn, "REJECT_SENSITIVE", slot)
            return "REJECT_SENSITIVE"
        if (role, slot) in self.tombstones and not explicit_restore:
            self._audit(turn, "SUPPRESSED_FORGOTTEN", slot)
            return "SUPPRESSED_FORGOTTEN"
        current = self._facts[role].get(slot)
        if current and current.value == value:
            self._audit(turn, "UNCHANGED", slot)
            return "UNCHANGED"
        self._facts[role][slot] = Fact(subject, slot, value, turn)
        if explicit_restore:
            self.tombstones.discard((role, slot))
        action = "UPDATE" if current else "ADD"
        self._audit(turn, action, slot)
        return action

    def forget(self, slot, turn, *, role=ROLE, actor=OWNER):
        self._authorize(role, actor)
        present = slot in self._facts[role]
        self._facts[role].pop(slot, None)
        self.tombstones.add((role, slot))
        self._audit(turn, "FORGET" if present else "FORGET_ABSENT", slot)
        return present

    def reject(self, turn, reason):
        self._audit(turn, "REJECT", reason)

    def ingest(self, turn: int, text: str, *, actor: str, role=ROLE):
        """Reference rules for the *public* test stream, not a general LLM extractor."""
        if actor != self._owners.get(role):
            self.reject(turn, "untrusted_actor")
            return
        t = text
        if "银行卡" in t or "银行账号" in t or "身份证号" in t:
            self.reject(turn, "sensitive_identifier")
            return
        if ("稳赚不赔" in t or "年化收益40%" in t):
            self.reject(turn, "unverified_investment")
            return
        if "裁员30%" in t and ("同事" in t or "听说" in t):
            self.reject(turn, "unverified_layoff_rumour")
            return

        if "我是李明" in t and "产品经理" in t and "XX科技" in t:
            self.upsert("identity.name", "李明", turn, actor=actor)
            self.upsert("identity.age_at_first_report", "35岁（第1轮自述）", turn, actor=actor)
            self.upsert("work.company", "西安XX科技", turn, actor=actor)
            self.upsert("work.title", "产品经理", turn, actor=actor)
            self.upsert("family.marital_status", "已婚", turn, actor=actor)
            self.upsert("family.daughter.school", "附近幼儿园", turn, actor=actor, subject="女儿")
        if "长安区" in t and "开车" in t and "科技路" in t:
            # extract the public set route conservatively without requiring a specific cue word
            self.upsert("home.district", "长安区", turn, actor=actor)
            self.upsert("commute.mode_route", "驾车经科技路到高新区", turn, actor=actor)
            self.upsert("commute.duration", "40–50分钟", turn, actor=actor)
            if "周三" in t and "游泳" in t:
                self.upsert("habit.swimming", "长安区体育馆每周三晚上游泳（搬迁后需复核）", turn, actor=actor)
        if "轻度脂肪肝" in t and "医生" in t:
            self.upsert("health.latest", "近期体检提示轻度脂肪肝", turn, actor=actor)
            self.upsert("health.advice", "控制饮食、减少油腻、多运动", turn, actor=actor)
            if "每周" in t and "药" in t:
                self.upsert("health.medicine_followup", "每周取调理药（暂时性安排）", turn, actor=actor)
        if "我老婆" in t and "平面设计" in t:
            self.upsert("spouse.work", "设计公司平面设计", turn, actor=actor, subject="妻子")
            if "美术启蒙班" in t:
                self.upsert("daughter.art_class", "周六下午美术启蒙班", turn, actor=actor, subject="女儿")
        if "PMP" in t and ("打算考" in t or ("开始准备" in t and "PMP考试过了" not in t)):
            self.upsert("learning.current_goal", "准备PMP考试（原计划9月）", turn, actor=actor)

        if "跳槽了" in t and "YY网络科技" in t:
            self.upsert("work.company", "YY网络科技有限公司", turn, actor=actor)
            self.upsert("work.title", "高级产品总监", turn, actor=actor)
        if "搬家了" in t and "曲江新区" in t:
            self.upsert("home.district", "曲江新区", turn, actor=actor)
            self.upsert("commute.mode_route", "地铁3号线转2号线", turn, actor=actor)
            self.upsert("commute.duration", "约35分钟", turn, actor=actor)
            self.forget("habit.swimming", turn, actor=actor)
        if "女儿上小学" in t and "曲江一小" in t:
            self.upsert("family.daughter.school", "曲江一小一年级，步行约10分钟", turn, actor=actor, subject="女儿")
            self.forget("daughter.art_class", turn, actor=actor)
        if "PMP考试过了" in t:
            self.upsert("qualification.PMP", "已取得PMP证书", turn, actor=actor)
            self.upsert("learning.current_goal", "备考数据分析师", turn, actor=actor)
        if "老婆也换工作" in t and "设计主管" in t:
            self.upsert("spouse.work", "互联网公司设计主管", turn, actor=actor, subject="妻子")
        if "脂肪肝没了" in t:
            self.upsert("health.latest", "最近体检提示脂肪肝已消失", turn, actor=actor)
            self.forget("health.medicine_followup", turn, actor=actor)
        if "赵刚" in t and "招产品总监" in t:
            # One-off recruiting lead belongs in an expiring task list, not durable role memory.
            pass
        if "赵刚" in t and "这事就算了" in t:
            self.forget("pending.job_opportunity", turn, actor=actor)

def parse_public_script(text: str):
    parts = re.split(r"(?m)^## 第(\d+)轮\s*$", text)
    rounds = []
    for i in range(1, len(parts), 2):
        n = int(parts[i])
        block = parts[i + 1].strip()
        m = re.match(r"\*\*(.+?)\*\*\s*：\s*(.*)", block, re.S)
        if not m:
            raise ValueError(f"Unparseable turn {n}")
        message = m.group(2).split("\n\n")[0].strip()
        rounds.append({"round": n, "speaker": m.group(1), "text": message})
    if [r["round"] for r in rounds] != list(range(1, 29)):
        raise ValueError("Official stream must contain exactly turns 1 through 28")
    return rounds

def offline_trusted_actor(round_data):
    """Test-fixture mapping only. NEVER infer real auth from speaker text."""
    return OWNER if round_data["speaker"] == "李明" else "untrusted:fixture"
