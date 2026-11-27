"""ATB 전투 규칙 (그래픽·입력과 무관한 순수 로직 — 3D 전투 화면이 사용).

2D 전투(src/scenes/battle.py)와 같은 규칙·수치(data/battle.json):
게이지 충전(속도 비례), 웨이트 모드 명령, 대미지·약점·내성·치명타·방어, 상태이상(화상·정지·실명·도발·
방어↑·약점노출), 루크 증기압(MAX 시 1.5배 → 다음 턴 과열), 보스 폭주, 적 AI, 아이템, 도주, 경험치·레벨업.

행동은 제너레이터로 진행되며 '연출 이벤트' dict 를 yield 한다. 화면 쪽이 순서대로 재생한다.
  {"t": "say", "text"}                 상단 배너
  {"t": "lunge", "who", "to", "dist"}  돌진 (dist 가 있으면 그만큼만)
  {"t": "back", "who"}                 제자리로
  {"t": "fx", "fx", "src", "dst", "big"}
  {"t": "sfx", "id"}
  {"t": "float", "who", "text", "color", "size"}
  {"t": "hit", "who"}                  피격 반짝임/흔들림
  {"t": "die", "who"}
  {"t": "flash", "color"}
  {"t": "wait", "s"}                   다음 이벤트까지 대기(초)
  {"t": "skill", "who", "tier", "name", "targets"}   스킬 발동 (tier 1~6: 상위 스킬일수록 큰 연출)
  {"t": "crit", "who", "to", "cutin"}  치명타 (cutin=True 면 아군 컷인 — 공격 동작 전에 미리 판정)
"""
from __future__ import annotations

import random

from src import datafiles

STATUS_NAMES = {"overheat": "과열", "burn": "화상", "stop": "정지", "blind": "실명", "def_up": "방어↑",
                "taunt": "도발", "exposed": "약점노출", "guard": "방어"}
WHITE, PARTY_DMG, HEAL, MP, GOLD, ETHER, GRAY, ORANGE = ((255, 255, 255), (255, 140, 130), (120, 255, 170),
                                                          (70, 190, 230), (255, 220, 90), (95, 227, 224),
                                                          (150, 150, 160), (255, 160, 90))


class Fighter:
    def __init__(self, name, stats, hp, mp, max_hp, max_mp, party, slot, ref=None, enemy=None):
        self.name, self.stats = name, stats
        self.hp, self.mp, self.max_hp, self.max_mp = hp, mp, max_hp, max_mp
        self.party, self.slot, self.ref, self.enemy = party, slot, ref, enemy
        self.atb = random.uniform(10, 45) if party else random.uniform(0, 30)
        self.status: dict[str, int] = {}
        self.boost = False
        self.raged = False
        self.view = None          # 화면 쪽 객체 (빌보드 등)

    @property
    def alive(self):
        return self.hp > 0

    @property
    def id(self):
        return self.ref.id if self.party else self.enemy["id"]

    def stat(self, k):
        v = self.stats[k]
        if k == "def" and "def_up" in self.status:
            v *= 1.5
        if k == "def" and self.enemy and self.raged:
            v *= self.enemy["rage"]["def_mult"]
        return v

    def speed(self):
        s = self.stats["spd"]
        if self.enemy and self.raged:
            s *= self.enemy["rage"]["spd_mult"]
        return s


class BattleCore:
    def __init__(self, state, enemy_ids, boss=False):
        self.B = datafiles.load_json("battle.json")
        self.state = state
        self.boss = boss
        self.party = []
        for i, ch in enumerate(state.party):
            stats = {k: ch.stat(k) for k in ("atk", "def", "mag", "res", "spd")}
            self.party.append(Fighter(ch.name, stats, ch.hp, ch.mp, ch.max_hp, ch.max_mp, True, i, ref=ch))
        self.enemies = []
        counts = {}
        for i, eid in enumerate(enemy_ids):
            e = self.B["enemies"][eid]
            counts[eid] = counts.get(eid, 0) + 1
            name = e["name"] + ("" if enemy_ids.count(eid) == 1 else " " + "ABC"[counts[eid] - 1])
            stats = {k: e[k] for k in ("atk", "def", "mag", "res", "spd")}
            self.enemies.append(Fighter(name, stats, e["hp"], 0, e["hp"], 0, False, i, enemy={**e, "id": eid}))
        self.phase = "running"        # running / command / action / victory / defeat / escaped
        self.ready: list[Fighter] = []
        self.actor: Fighter | None = None
        self.seq = None
        self.result = None
        self.pending: list[dict] = []   # 턴 시작 처리 등에서 나온 이벤트

    # ------------------------------------------------------------ 조회
    def living(self, party):
        return [f for f in (self.party if party else self.enemies) if f.alive]

    def commands(self):
        return [("공격", True), ("스킬", True), ("방어", True),
                ("아이템", any(v > 0 for v in self.state.items.values())), ("도주", not self.boss)]

    def skills(self, f):
        out = []
        for s in f.ref.skills():
            ok = f.mp >= s["mp"]
            extra = f"MP {s['mp']}" if s["mp"] else ""
            if s.get("steam_cost"):
                ok, extra = f.ref.steam >= s["steam_cost"], "증기압 100"
            out.append((s, ok, extra))
        return out

    def items(self):
        return [(k, self.B["items"][k], n) for k, n in self.state.items.items() if n > 0]

    def targets_for(self, tkind):
        """('single'|'all'|'self', 후보 목록, 기본 인덱스)"""
        if tkind == "self":
            return "self", [self.actor], 0
        if tkind == "all_enemies":
            return "all", self.living(False), 0
        if tkind == "all_allies":
            return "all", self.living(True), 0
        if tkind == "all_party":
            return "all", list(self.party), 0
        if tkind == "dead_ally":
            c = [f for f in self.party if not f.alive]
            return ("single", c, 0) if c else ("single", [], 0)
        if tkind == "ally":
            c = self.living(True)
            return "single", c, min(range(len(c)), key=lambda i: c[i].hp / c[i].max_hp)
        return "single", self.living(False), 0

    # ------------------------------------------------------------ 진행
    def tick(self, dt):
        """running 상태에서 게이지 충전. 명령이 필요하면 phase='command', 적 행동이면 phase='action'."""
        if self.phase != "running":
            return
        A = self.B["atb"]
        for f in self.party + self.enemies:
            if not f.alive or f in self.ready:
                continue
            rate = 40 if "stop" in f.status else A["base"] + f.speed() * A["fill_per_spd"]
            f.atb = min(A["max"], f.atb + rate * dt)
            if f.atb >= A["max"]:
                self.ready.append(f)
        while self.ready and self.phase == "running":
            f = self.ready.pop(0)
            if not f.alive:
                continue
            if not self.turn_start(f):
                continue
            self.actor = f
            if f.party:
                self.phase = "command"
            else:
                self.seq = self.enemy_turn(f)
                self.phase = "action"

    def turn_start(self, f):
        f.status.pop("guard", None)
        if "burn" in f.status:
            dmg = max(1, int(f.max_hp * 0.06))
            self.damage(f, dmg, quiet=True, out=self.pending)
            self.pending.append({"t": "float", "who": f, "text": str(dmg), "color": ORANGE, "size": 30})
        expired = [k for k in list(f.status) if f.status[k] - 1 <= 0]
        for k in list(f.status):
            f.status[k] -= 1
        stopped = "stop" in f.status or "stop" in expired
        overheated = "overheat" in expired
        for k in expired:
            f.status.pop(k, None)
        if not f.alive:
            self.check_end()
            return False
        if stopped or overheated:
            f.atb = 0
            self.pending.append({"t": "float", "who": f, "text": "과열! 행동 불가" if overheated else "정지 중…",
                                 "color": ORANGE if overheated else ETHER, "size": 22})
            if overheated:
                self.pending += [{"t": "fx", "fx": "steam", "src": f, "dst": f, "big": False}, {"t": "sfx", "id": "steam"}]
            return False
        return True

    def commit(self, payload, targets):
        self.phase = "action"
        self.seq = self.party_action(self.actor, payload, targets)

    def next_event(self):
        """행동 제너레이터에서 다음 연출 이벤트. 행동이 끝나면 None"""
        if self.pending:
            return self.pending.pop(0)
        if not self.seq:
            return None
        try:
            return next(self.seq)
        except StopIteration:
            self.seq = None
            if self.actor:
                self.actor.atb = 0
            self.actor = None
            if self.phase == "action":
                self.phase = "running"
            self.check_end()
            return None

    # ------------------------------------------------------------ 행동
    CRIT_PARTY, CRIT_ENEMY = 0.12, 0.05

    def roll_crit(self, a, bonus=0.0):
        if a.party:                                   # 장비의 치명타 보정 (렌즈·명검 등)
            from src.systems import equipment
            bonus += equipment.crit_bonus(a.ref)
        return random.random() < (self.CRIT_PARTY if a.party else self.CRIT_ENEMY) + bonus

    def skill_tier(self, ch, sk):
        """캐릭터 스킬 목록에서 몇 번째 스킬인지 (1~6) — 상위 스킬일수록 연출이 커진다"""
        ids = [x["id"] for x in ch.profile["skills"]]
        return ids.index(sk["id"]) + 1 if sk["id"] in ids else 1

    def party_action(self, a, payload, targets):
        kind, data = payload
        ch = a.ref
        if kind == "guard":
            a.status["guard"] = 1
            yield {"t": "sfx", "id": "guard"}
            yield {"t": "fx", "fx": "buff", "src": a, "dst": a, "big": False}
            yield {"t": "float", "who": a, "text": "방어", "color": GOLD, "size": 24}
            yield {"t": "wait", "s": 0.5}
        elif kind == "escape":
            if random.random() < 0.7:
                yield {"t": "sfx", "id": "escape"}
                yield {"t": "say", "text": "무사히 도망쳤다!"}
                yield {"t": "wait", "s": 0.9}
                self.phase = "escaped"
                self.result = {"kind": "escape"}
                return
            yield {"t": "say", "text": "도망칠 수 없었다!"}
            yield {"t": "wait", "s": 0.8}
        elif kind == "item":
            item = self.B["items"][data]
            self.state.items[data] -= 1
            yield {"t": "say", "text": item["name"]}
            yield {"t": "wait", "s": 0.2}
            yield {"t": "sfx", "id": item["sfx"]}
            for t in targets:
                yield {"t": "fx", "fx": item["fx"], "src": a, "dst": t, "big": len(targets) > 1, "tier": 0}
            yield {"t": "wait", "s": 0.3}
            for t in targets:
                if item.get("damage") and not t.party:
                    if t.alive:
                        out = []
                        self.damage(t, int(item["damage"] * random.uniform(0.95, 1.05)), out=out)
                        for e in out:
                            yield e
                    continue
                if item.get("revive") and not t.alive:
                    t.hp = max(1, int(t.max_hp * item["revive"]))
                    t.atb = 0
                    yield {"t": "revive", "who": t}
                    yield {"t": "float", "who": t, "text": "부활!", "color": HEAL, "size": 30, "rise": True}
                if not t.alive:
                    continue
                if "heal_hp" in item:
                    yield from self.heal(t, item["heal_hp"])
                if "heal_mp" in item:
                    before = t.mp
                    t.mp = min(t.max_mp, t.mp + item["heal_mp"])
                    yield {"t": "float", "who": t, "text": f"MP +{t.mp - before}", "color": MP, "size": 28}
                if item.get("cure"):
                    for k in ("burn", "blind", "stop"):
                        t.status.pop(k, None)
                    yield {"t": "float", "who": t, "text": "상태 회복", "color": HEAL, "size": 24, "rise": True}
            yield {"t": "wait", "s": 0.5}
        elif kind == "attack":
            spec = self.B["attack"][ch.id]
            t = targets[0]
            ranged = spec.get("ranged") or spec.get("stat") == "mag"
            crit = self.roll_crit(a)
            yield {"t": "lunge", "who": a, "to": t, "dist": 1.2 if ranged else None}
            if crit:
                yield {"t": "crit", "who": a, "to": t, "cutin": True}
            yield {"t": "sfx", "id": spec["sfx"]}
            yield {"t": "fx", "fx": spec["fx"], "src": a, "dst": t, "big": crit, "tier": 0}
            yield {"t": "wait", "s": 0.12}
            from src.systems import equipment
            element = equipment.weapon_element(ch) or spec["element"]
            yield from self.hit(a, t, "mag" if spec.get("stat") == "mag" else "phys", spec["power"], element,
                                crit=crit)
            yield {"t": "wait", "s": 0.2}
            yield {"t": "back", "who": a}
            yield {"t": "wait", "s": 0.25}
        elif kind == "skill":
            sk = data
            if sk.get("steam_cost"):
                ch.steam = 0
            else:
                a.mp -= sk["mp"]
            tier = self.skill_tier(ch, sk)
            yield {"t": "say", "text": sk["name"]}
            yield {"t": "skill", "who": a, "tier": tier, "name": sk["name"], "targets": list(targets)}
            yield {"t": "wait", "s": 0.25}
            main = targets[0]
            single = len(targets) == 1 and sk["kind"] in ("phys", "mag")
            crit = self.roll_crit(a, sk.get("crit_bonus", 0)) if single else None
            if sk["target"] == "enemy" and sk["kind"] == "phys" and ch.id == "luke":
                yield {"t": "lunge", "who": a, "to": main, "dist": None}
            elif sk["target"] not in ("self", "ally", "all_allies"):
                yield {"t": "lunge", "who": a, "to": main, "dist": 1.4}
            if crit:
                yield {"t": "crit", "who": a, "to": main, "cutin": tier < 5}      # 5단계 이상은 스킬 컷인이 이미 나옴
            yield {"t": "sfx", "id": sk["sfx"]}
            if sk["target"] in ("all_enemies", "all_allies") and len(targets) > 1:
                for t in targets:
                    yield {"t": "fx", "fx": sk["fx"], "src": a, "dst": t, "big": sk["fx"] == "ultimate", "tier": tier}
            else:
                yield {"t": "fx", "fx": sk["fx"], "src": a, "dst": main, "big": True, "tier": tier}
            yield {"t": "wait", "s": 0.3}
            for t in targets:
                if not t.alive and sk["kind"] != "heal":
                    continue
                if sk["kind"] in ("phys", "mag"):
                    yield from self.hit(a, t, sk["kind"], sk["power"], sk.get("element"), sk.get("crit_bonus", 0),
                                        crit=crit if t is main else None)
                    for k, v in sk.get("status", {}).items():
                        if t.alive:
                            yield from self.add_status(t, k, v)
                    if t.alive and "status_if_mech" in sk and "기계" in t.enemy.get("tags", []):
                        for k, v in sk["status_if_mech"].items():
                            yield from self.add_status(t, k, v)
                elif sk["kind"] == "heal" and t.alive:
                    yield from self.heal(t, int(a.stat("mag") * sk["power"] * random.uniform(0.95, 1.05) + 10))
                    if sk.get("cleanse"):
                        for k in ("burn", "blind", "stop"):
                            t.status.pop(k, None)
                elif sk["kind"] in ("buff", "debuff"):
                    for k, v in sk["status"].items():
                        yield from self.add_status(t, k, v)
                yield {"t": "wait", "s": 0.08}
            if sk.get("reset_steam"):
                ch.steam = 0
            yield {"t": "wait", "s": 0.25}
            yield {"t": "back", "who": a}
            yield {"t": "wait", "s": 0.3}

    def enemy_turn(self, e):
        spec = e.enemy
        if spec.get("rage") and not e.raged and e.hp <= e.max_hp * spec["rage"]["hp_ratio"]:
            e.raged = True
            yield {"t": "say", "text": spec["rage"]["line"]}
            yield {"t": "flash", "color": (255, 80, 60)}
            yield {"t": "fx", "fx": "rage", "src": e, "dst": e, "big": True}
            yield {"t": "sfx", "id": "steam"}
            yield {"t": "wait", "s": 1.0}
        acts = spec["actions"]
        act = random.choices(acts, weights=[x["weight"] for x in acts])[0]
        alive = self.living(True)
        if not alive:
            return
        taunters = [p for p in alive if "taunt" in p.status]
        targets = alive if act.get("target") == "all" else [taunters[0] if taunters else random.choice(alive)]
        yield {"t": "say", "text": act["name"]}
        yield {"t": "wait", "s": 0.3}
        yield {"t": "lunge", "who": e, "to": targets[0], "dist": 1.6}
        yield {"t": "sfx", "id": "slash" if act["fx"] == "claw" else "fire"}
        for t in targets:
            yield {"t": "fx", "fx": act["fx"], "src": e, "dst": t, "big": e.enemy.get("boss", False), "tier": 0}
        yield {"t": "wait", "s": 0.15}
        for t in targets:
            yield from self.hit(e, t, act["kind"], act["power"], None)
            if t.alive:
                for k, v in act.get("status", {}).items():
                    if random.random() < 0.5:
                        yield from self.add_status(t, k, v)
                if act.get("drain_mp"):
                    t.mp = max(0, t.mp - act["drain_mp"])
                    yield {"t": "float", "who": t, "text": f"MP -{act['drain_mp']}", "color": MP, "size": 24}
        yield {"t": "wait", "s": 0.2}
        yield {"t": "back", "who": e}
        yield {"t": "wait", "s": 0.3}

    # ------------------------------------------------------------ 계산
    def hit(self, a, t, kind, power, element, crit_bonus=0.0, crit=None):
        if kind == "phys" and "blind" in a.status and random.random() < 0.5:
            yield {"t": "float", "who": t, "text": "MISS", "color": GRAY, "size": 28}
            return
        if kind == "phys":
            base = a.stat("atk") * power
            dmg = base * random.uniform(0.9, 1.1) - t.stat("def") * 0.55
        else:
            base = a.stat("mag") * power
            dmg = base * random.uniform(0.9, 1.1) - t.stat("res") * 0.45
        dmg = max(dmg, base * 0.15)
        tags = []
        if a.party and a.ref.id == "luke" and a.boost:
            dmg *= self.B["steam_pressure"]["power_bonus"]
            a.boost = False
            a.status["overheat"] = 1
            tags.append(("증기압 해방!", ORANGE))
        if t.enemy and element:
            if element in t.enemy.get("weak", []):
                dmg *= 1.5
                tags.append(("약점!", GOLD))
            elif element in t.enemy.get("resist", []):
                dmg *= 0.6
                tags.append(("내성", GRAY))
        if "exposed" in t.status:
            dmg *= 1.3
        if crit is None:                       # 미리 판정하지 않은 경우(전체 공격의 다른 대상, 적의 공격)
            crit = self.roll_crit(a, crit_bonus)
            if crit:
                yield {"t": "crit", "who": a, "to": t, "cutin": False}
        if crit:
            dmg *= 1.6
            tags.append(("치명타!", (255, 120, 90)))
        if "guard" in t.status:
            dmg *= 0.5
        out = []
        self.damage(t, max(1, int(dmg)), out=out)
        for e in out:
            yield e
        for s, col in tags:
            yield {"t": "float", "who": t, "text": s, "color": col, "size": 22, "rise": True}
        sp = self.B["steam_pressure"]
        for f, gain in ((a, sp["on_hit_dealt"]), (t, sp["on_hit_taken"])):
            if f.party and f.ref.id == "luke" and kind == "phys" and f.alive:
                before = f.ref.steam
                f.ref.steam = min(sp["max"], f.ref.steam + gain)
                if before < sp["max"] <= f.ref.steam:
                    f.boost = True
                    f.ref.steam = 0
                    yield {"t": "float", "who": f, "text": "증기압 MAX!", "color": ORANGE, "size": 24, "rise": True}
                    yield {"t": "fx", "fx": "steam", "src": f, "dst": f, "big": False}

    def damage(self, t, dmg, quiet=False, out=None):
        out = out if out is not None else self.pending
        t.hp = max(0, t.hp - dmg)
        out.append({"t": "hit", "who": t})
        if not quiet:
            out.append({"t": "float", "who": t, "text": str(dmg), "color": PARTY_DMG if t.party else WHITE, "size": 36})
            out.append({"t": "sfx", "id": "hit"})
        if not t.alive:
            t.status.clear()
            t.atb = 0
            if t in self.ready:
                self.ready.remove(t)
            out.append({"t": "die", "who": t})
            if not t.party:
                out.append({"t": "sfx", "id": "enemy_die"})

    def heal(self, t, amount):
        before = t.hp
        t.hp = min(t.max_hp, t.hp + amount)
        yield {"t": "float", "who": t, "text": f"+{t.hp - before}", "color": HEAL, "size": 34}

    def add_status(self, t, k, v):
        t.status[k] = max(t.status.get(k, 0), v)
        if k == "stop":
            t.atb = 0
        yield {"t": "float", "who": t, "text": STATUS_NAMES.get(k, k), "color": GOLD if t.party else ETHER,
               "size": 22, "rise": True}

    # ------------------------------------------------------------ 종료
    def check_end(self):
        if self.phase in ("victory", "defeat", "escaped"):
            return
        if not self.living(False):
            self.victory()
        elif not self.living(True):
            self.phase = "defeat"
            self.result = {"kind": "defeat"}

    def victory(self):
        self.phase = "victory"
        exp = sum(e.enemy["exp"] for e in self.enemies)
        gold = sum(e.enemy["gold"] for e in self.enemies)
        st = self.state
        st.gold += gold
        st.battles_won += 1
        ups = {}
        for f in self.party:
            ch = f.ref
            ch.hp, ch.mp = f.hp, f.mp
            if f.alive:
                u = ch.gain_exp(exp)
                if u:
                    ups[ch.id] = u
                    f.hp, f.mp, f.max_hp, f.max_mp = ch.hp, ch.mp, ch.max_hp, ch.max_mp
            else:
                ch.hp = 1
        self.result = {"kind": "victory", "exp": exp, "gold": gold, "ups": ups}

    def write_back(self):
        """전투 결과(HP/MP)를 파티 데이터에 반영"""
        for f in self.party:
            f.ref.hp, f.ref.mp = max(1, f.hp), f.mp
