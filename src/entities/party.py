"""파티, 캐릭터 성장(레벨업), 인벤토리, 진행 플래그."""
from __future__ import annotations

from src import datafiles as assets      # pygame 없이도 쓰도록 (3D 버전 공용)

STATS = ("hp", "mp", "atk", "def", "mag", "res", "spd")


def exp_to_next(level: int) -> int:
    c = assets.load_json("battle.json")["exp_curve"]
    return int(c["base"] * level ** c["power"])


class Character:
    def __init__(self, profile: dict, level: int):
        self.id = profile["id"]
        self.name = profile["name"]
        self.cls = profile["class"]
        self.profile = profile
        self.base = profile["base_stats"]
        self.growth = assets.load_json("battle.json")["growth"][self.id]
        self.level = level
        self.exp = 0
        self.hp = self.max_hp
        self.mp = self.max_mp
        self.steam = 0          # 루크 전용 증기압 게이지

    def stat(self, k):
        return int(self.base[k] + self.growth[k] * (self.level - 1))

    @property
    def max_hp(self):
        return self.stat("hp")

    @property
    def max_mp(self):
        return self.stat("mp")

    @property
    def alive(self):
        return self.hp > 0

    def skills(self, all_=False):
        """습득한 스킬 (story.json 정의 + battle.json 동작)"""
        mech = assets.load_json("battle.json")["skills"]
        out = []
        for sk in self.profile["skills"]:
            if sk["id"] in mech and (all_ or sk["level"] <= self.level):
                out.append({**sk, **mech[sk["id"]], "mp": sk.get("cost", {}).get("mp", 0),
                            "steam_cost": sk.get("cost", {}).get("steam_pressure", 0)})
        return out

    def gain_exp(self, amount):
        """레벨업 내역 리스트를 돌려준다: [{level, diffs, learned}]"""
        self.exp += amount
        ups = []
        while self.exp >= exp_to_next(self.level):
            self.exp -= exp_to_next(self.level)
            before = {k: self.stat(k) for k in STATS}
            known = {s["id"] for s in self.skills()}
            self.level += 1
            diffs = {k: self.stat(k) - before[k] for k in STATS}
            learned = [s["name"] for s in self.skills() if s["id"] not in known]
            self.hp = min(self.max_hp, self.hp + diffs["hp"])
            self.mp = min(self.max_mp, self.mp + diffs["mp"])
            ups.append({"level": self.level, "diffs": diffs, "learned": learned})
        return ups

    def full_heal(self):
        self.hp, self.mp, self.steam = self.max_hp, self.max_mp, 0


class GameState:
    def __init__(self, story):
        battle = assets.load_json("battle.json")
        lv = battle["start_level"]
        self.party = [Character(p, lv) for p in story["protagonists"]]
        self.items = dict(battle["start_items"])
        self.gold = 120
        self.flags: set[str] = set()
        self.map_id = None
        self.pos = None
        self.dir = "se"
        self.battles_won = 0
        self.playtime = 0.0       # 초 (세이브 슬롯에 표시)

    def member(self, cid):
        return next(c for c in self.party if c.id == cid)
