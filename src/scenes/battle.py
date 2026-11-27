"""게이지 기반 턴제(ATB) 전투.

- 모든 전투원의 ATB 게이지가 속도(spd)에 비례해 차고, 가득 차면 행동한다.
- 아군 게이지가 차면 명령 창이 열리고 그동안 시간이 멈춘다(웨이트 모드).
- 행동 연출은 제너레이터(yield 대기시간)로 순서대로 재생한다.
"""
from __future__ import annotations

import math
import random

import pygame

from src import config as cfg
from src.engine import assets
from src.engine.core import Scene
from src.entities.party import exp_to_next
from src.systems import effects as fx
from src.ui import widgets as ui

C = cfg.C
B = None  # battle.json (지연 로드)

PARTY_POS = [(850, 455), (990, 385), (1120, 460)]
ENEMY_POS = [(380, 360), (520, 280), (240, 445)]
BOSS_POS = [(400, 400)]
STATUS_NAMES = {"overheat": "과열", "burn": "화상", "stop": "정지", "blind": "실명", "def_up": "방어↑", "taunt": "도발",
                "exposed": "약점노출", "guard": "방어"}


class Fighter:
    def __init__(self, name, stats, hp, mp, max_hp, max_mp, party, pos, ref=None, enemy=None):
        self.name = name
        self.stats = stats
        self.hp, self.mp, self.max_hp, self.max_mp = hp, mp, max_hp, max_mp
        self.party = party
        self.home = pygame.Vector2(pos)
        self.offset = pygame.Vector2()
        self.ref = ref            # 아군: Character
        self.enemy = enemy        # 적: battle.json 정의
        self.atb = random.uniform(10, 45) if party else random.uniform(0, 30)
        self.status: dict[str, int] = {}
        self.flash = 0.0
        self.shake = 0.0
        self.dead_t = 0.0
        self.boost = False        # 증기압 MAX 보너스 대기
        self.raged = False

    @property
    def alive(self):
        return self.hp > 0

    @property
    def pos(self):
        sx = math.sin(self.shake * 60) * 8 * self.shake if self.shake > 0 else 0
        return self.home + self.offset + pygame.Vector2(sx, 0)

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

    def center(self):
        """이펙트 기준점 (몸통 가운데)"""
        h = 90 if self.party else (150 if self.enemy.get("boss") else 70)
        return self.pos + pygame.Vector2(0, -h)


class BattleScene(Scene):
    def __init__(self, game, enemy_ids, floor="cobble", boss=False, on_win=None, on_lose=None):
        super().__init__(game)
        global B
        B = assets.load_json("battle.json")
        self.floor = floor
        self.boss = boss
        self.on_win, self.on_lose = on_win, on_lose
        st = game.state
        self.party = []
        for i, ch in enumerate(st.party):
            stats = {k: ch.stat(k) for k in ("atk", "def", "mag", "res", "spd")}
            f = Fighter(ch.name, stats, ch.hp, ch.mp, ch.max_hp, ch.max_mp, True, PARTY_POS[i], ref=ch)
            self.party.append(f)
        self.enemies = []
        slots = BOSS_POS if boss else ENEMY_POS
        counts = {}
        for i, eid in enumerate(enemy_ids):
            e = B["enemies"][eid]
            counts[eid] = counts.get(eid, 0) + 1
            name = e["name"] + ("" if enemy_ids.count(eid) == 1 else " " + "ABC"[counts[eid] - 1])
            stats = {k: e[k] for k in ("atk", "def", "mag", "res", "spd")}
            f = Fighter(name, stats, e["hp"], 0, e["hp"], 0, False, slots[i], enemy={**e, "id": eid})
            f.offset = pygame.Vector2(-500, 0)       # 등장 연출
            self.enemies.append(f)
        self.effects: list = []
        self.glow = pygame.Surface((cfg.SCREEN_W, cfg.SCREEN_H))
        self.state = "intro"
        self.t = 0.0
        self.seq = None
        self.wait = 0.0
        self.ready: list[Fighter] = []
        self.actor = None
        self.menu = None
        self.sub = None           # ("skill"|"item", ListMenu, data)
        self.target_mode = None   # (kind, candidates, index, payload)
        self.banner = None        # (text, t)
        self.log = ""
        self.result = None
        self.bg = self._make_bg()
        names = ", ".join(e.name for e in self.enemies)
        self.say(f"{names} 이(가) 나타났다!", 1.6)

    def on_enter(self):
        self.game.audio.play_bgm("tense" if self.boss else "battle", fade_ms=200)
        self.game.emit("battle_start", enemies=[e.enemy["id"] for e in self.enemies])

    # ------------------------------------------------------------ 유틸
    def say(self, s, dur=1.2):
        self.banner = (s, dur)

    def living(self, party):
        return [f for f in (self.party if party else self.enemies) if f.alive]

    def float_text(self, f, s, color, size=30):
        self.effects.append(fx.FloatText(f.center() + pygame.Vector2(random.uniform(-14, 14), -20), s, color, size))

    def _make_bg(self):
        s = pygame.Surface((cfg.SCREEN_W, cfg.SCREEN_H))
        for y in range(cfg.SCREEN_H):
            k = y / cfg.SCREEN_H
            s.fill((int(20 + 40 * k), int(16 + 22 * k), int(30 + 14 * k)), (0, y, cfg.SCREEN_W, 1))
        tile = assets.image(f"tiles/tile_{self.floor}.png")
        cx, cy = 660, 150
        for y in range(-7, 8):
            for x in range(-7, 8):
                sx = cx + (x - y) * 32
                sy = cy + (x + y) * 16 + 7 * 16
                s.blit(tile, (sx - 32, sy))
        vign = pygame.Surface((cfg.SCREEN_W, cfg.SCREEN_H), pygame.SRCALPHA)
        for i in range(60):
            a = int(200 * (i / 60) ** 2)
            pygame.draw.rect(vign, (0, 0, 0, a // 6), (i * 6, i * 4, cfg.SCREEN_W - i * 12, cfg.SCREEN_H - i * 8), 8)
        s.blit(vign, (0, 0))
        dark = pygame.Surface((cfg.SCREEN_W, cfg.SCREEN_H), pygame.SRCALPHA)
        dark.fill((0, 0, 0, 60))
        s.blit(dark, (0, 0))
        return s

    # ------------------------------------------------------------ 업데이트
    def update(self, dt):
        self.t += dt
        self.effects = [e for e in self.effects if e.update(dt)]
        for f in self.party + self.enemies:
            f.flash = max(0, f.flash - dt)
            f.shake = max(0, f.shake - dt * 2.5)
            if not f.alive:
                f.dead_t += dt
        if self.banner:
            self.banner = (self.banner[0], self.banner[1] - dt)
            if self.banner[1] <= 0:
                self.banner = None

        if self.state == "intro":
            for e in self.enemies:
                e.offset.x = min(0, e.offset.x + 1400 * dt)
            if self.t > 1.0:
                self.state = "running"
            return
        if self.state in ("victory", "defeat"):
            if self.game.input.was_pressed("confirm") and self.t - self.result["t"] > 0.6:
                self.finish()
            return
        if self.seq:
            self.run_seq(dt)
            return
        if self.state == "command":
            self.update_command()
            return
        # running: 게이지 충전
        for f in self.party + self.enemies:
            if f.alive and "stop" not in f.status and f not in self.ready:
                f.atb = min(B["atb"]["max"], f.atb + (B["atb"]["base"] + f.speed() * B["atb"]["fill_per_spd"]) * dt)
        for f in self.party + self.enemies:
            if f.alive and f.atb >= B["atb"]["max"] and f not in self.ready:
                self.ready.append(f)
            if f.alive and "stop" in f.status and f.atb < B["atb"]["max"]:
                f.atb = min(B["atb"]["max"], f.atb + 40 * dt)   # 정지 상태도 턴은 돌아오되 행동은 건너뜀
                if f.atb >= B["atb"]["max"] and f not in self.ready:
                    self.ready.append(f)
        if self.ready:
            f = self.ready.pop(0)
            if not f.alive:
                return
            if not self.turn_start(f):
                return
            if f.party:
                self.open_command(f)
            else:
                self.seq = self.enemy_turn(f)
                self.wait = 0

    def turn_start(self, f):
        """턴 시작 시 상태이상 처리. 행동 불가면 False."""
        f.status.pop("guard", None)
        if "burn" in f.status:
            dmg = max(1, int(f.max_hp * 0.06))
            self.apply_damage(f, dmg, None, quiet=True)
            self.float_text(f, f"{dmg}", (255, 150, 80))
            self.effects.append(fx.burst(f.center(), 10, (255, 140, 60), size=(2, 4)))
        expired = []
        for k in list(f.status):
            f.status[k] -= 1
            if f.status[k] <= 0:
                expired.append(k)
        stopped = "stop" in f.status or "stop" in expired
        overheated = "overheat" in expired
        for k in expired:
            f.status.pop(k, None)
        if not f.alive:
            self.check_end()
            return False
        if stopped or overheated:
            f.atb = 0
            self.float_text(f, "과열! 행동 불가" if overheated else "정지 중…", (255, 150, 80) if overheated else C["ether"], 22)
            if overheated:
                self.effects += fx.make("steam", f.center(), f.center())
                self.game.audio.sfx("sfx_steam")
            return False
        return True

    # ------------------------------------------------------------ 명령 입력
    def open_command(self, f):
        self.actor = f
        self.state = "command"
        self.menu = ui.ListMenu([("공격", True, ""), ("스킬", True, ""), ("방어", True, ""),
                                 ("아이템", any(self.game.state.items.values()), ""),
                                 ("도주", not self.boss, "")], rows=5)
        self.sub = None
        self.target_mode = None
        self.game.audio.sfx("sfx_menu")
        self.game.emit("command_open", actor=f.ref.id)

    def update_command(self):
        inp, au = self.game.input, self.game.audio
        if self.target_mode:
            kind, cands, idx, payload = self.target_mode
            if kind == "single":
                if inp.was_pressed("left") or inp.was_pressed("up"):
                    idx = (idx - 1) % len(cands); au.sfx("sfx_cursor")
                if inp.was_pressed("right") or inp.was_pressed("down"):
                    idx = (idx + 1) % len(cands); au.sfx("sfx_cursor")
                self.target_mode = (kind, cands, idx, payload)
            if inp.was_pressed("confirm"):
                au.sfx("sfx_confirm")
                targets = [cands[idx]] if kind == "single" else cands
                self.commit(payload, targets)
            elif inp.was_pressed("cancel"):
                au.sfx("sfx_cancel")
                self.target_mode = None
            return
        menu = self.sub[1] if self.sub else self.menu
        if inp.was_pressed("up"):
            menu.move(-1, au)
        if inp.was_pressed("down"):
            menu.move(1, au)
        if inp.was_pressed("cancel") and self.sub:
            au.sfx("sfx_cancel")
            self.sub = None
            return
        if not inp.was_pressed("confirm"):
            return
        label, enabled, _ = menu.items[menu.index]
        if not enabled:
            au.sfx("sfx_cancel")
            return
        au.sfx("sfx_confirm")
        a = self.actor
        if self.sub:
            kind, _, data = self.sub
            choice = data[menu.index]
            if kind == "skill":
                self.choose_target(choice["target"], ("skill", choice))
            else:
                self.choose_target(B["items"][choice]["target"], ("item", choice))
            return
        if label == "공격":
            self.choose_target("enemy", ("attack", None))
        elif label == "스킬":
            skills = a.ref.skills()
            items = []
            for s in skills:
                ok = a.mp >= s["mp"]
                extra = f"MP {s['mp']}" if s["mp"] else ""
                if s.get("steam_cost"):
                    ok = a.ref.steam >= s["steam_cost"]
                    extra = "증기압 100"
                items.append((s["name"], ok, extra))
            self.sub = ("skill", ui.ListMenu(items, rows=5), skills)
        elif label == "방어":
            self.commit(("guard", None), [a])
        elif label == "아이템":
            ids = [k for k, v in self.game.state.items.items() if v > 0]
            self.sub = ("item", ui.ListMenu([(B["items"][k]["name"], True, f"x{self.game.state.items[k]}") for k in ids],
                                            rows=5), ids)
        elif label == "도주":
            self.commit(("escape", None), [a])

    def choose_target(self, tkind, payload):
        if tkind in ("self",):
            self.commit(payload, [self.actor])
        elif tkind == "all_enemies":
            self.target_mode = ("all", self.living(False), 0, payload)
        elif tkind == "all_allies":
            self.target_mode = ("all", self.living(True), 0, payload)
        elif tkind == "ally":
            cands = self.living(True)
            idx = min(range(len(cands)), key=lambda i: cands[i].hp / cands[i].max_hp)
            self.target_mode = ("single", cands, idx, payload)
        else:
            self.target_mode = ("single", self.living(False), 0, payload)

    def commit(self, payload, targets):
        a = self.actor
        self.state = "running"
        self.menu = self.sub = self.target_mode = None
        self.seq = self.party_action(a, payload, targets)
        self.wait = 0

    # ------------------------------------------------------------ 연출 시퀀스
    def run_seq(self, dt):
        self.wait -= dt
        while self.wait <= 0 and self.seq:
            try:
                self.wait += next(self.seq)
            except StopIteration:
                self.seq = None
                self.check_end()

    def lunge(self, f, target, dist=None, dur=0.16):
        """f 를 target 쪽으로 이동시키는 시퀀스 조각"""
        start = pygame.Vector2(f.offset)
        if dist is None:
            goal = (target.home - f.home) * 0.75
        else:
            d = (target.home - f.home)
            goal = d.normalize() * dist if d.length() else pygame.Vector2()
        steps = 6
        for i in range(1, steps + 1):
            f.offset = start.lerp(goal, i / steps)
            yield dur / steps

    def back(self, f, dur=0.16):
        start = pygame.Vector2(f.offset)
        for i in range(1, 7):
            f.offset = start.lerp(pygame.Vector2(), i / 6)
            yield dur / 6

    def party_action(self, a, payload, targets):
        kind, data = payload
        ch = a.ref
        self.game.emit("action", actor=ch.id, kind=kind, skill=(data or {}).get("id") if isinstance(data, dict) else data)
        if kind == "guard":
            a.status["guard"] = 1
            self.game.audio.sfx("sfx_guard")
            self.effects += fx.make("buff", a.center(), a.center())
            self.float_text(a, "방어", C["brass_light"], 24)
            yield 0.5
        elif kind == "escape":
            if random.random() < 0.7:
                self.game.audio.sfx("sfx_escape")
                self.say("무사히 도망쳤다!", 1.0)
                for f in self.party:
                    f.offset = pygame.Vector2(200, 0)
                yield 0.9
                self.result = {"kind": "escape", "t": self.t}
                self.finish()
                return
            self.say("도망칠 수 없었다!", 1.0)
            yield 0.8
        elif kind == "item":
            item = B["items"][data]
            self.game.state.items[data] -= 1
            t = targets[0]
            self.say(item["name"], 0.9)
            yield 0.2
            self.game.audio.sfx(item["sfx"])
            self.effects += fx.make(item["fx"], a.center(), t.center())
            yield 0.3
            if "heal_hp" in item and t.alive:
                self.apply_heal(t, item["heal_hp"])
            if "heal_mp" in item:
                t.mp = min(t.max_mp, t.mp + item["heal_mp"])
                self.float_text(t, f"MP +{item['heal_mp']}", C["mp"])
            yield 0.5
        elif kind == "attack":
            spec = B["attack"][ch.id]
            t = targets[0]
            ranged = spec.get("ranged") or spec.get("stat") == "mag"
            yield from self.lunge(a, t, 40 if ranged else None)
            self.game.audio.sfx(spec["sfx"])
            self.effects += fx.make(spec["fx"], a.center(), t.center())
            yield 0.12
            self.hit(a, t, "mag" if spec.get("stat") == "mag" else "phys", spec["power"], spec["element"])
            yield 0.2
            yield from self.back(a)
            yield 0.25
        elif kind == "skill":
            sk = data
            if sk.get("steam_cost"):
                ch.steam = 0
            else:
                a.mp -= sk["mp"]
            self.say(sk["name"], 1.1)
            yield 0.25
            melee = sk["kind"] == "phys" and ch.id == "luke"
            main = targets[0]
            if sk["target"] in ("enemy",) and melee:
                yield from self.lunge(a, main)
            elif sk["target"] not in ("self", "ally", "all_allies"):
                yield from self.lunge(a, main, 50)
            self.game.audio.sfx(sk["sfx"])
            if sk["target"] in ("all_enemies", "all_allies") and len(targets) > 1:
                for t in targets:
                    self.effects += fx.make(sk["fx"], a.center(), t.center(), big=sk["fx"] == "ultimate")
            else:
                self.effects += fx.make(sk["fx"], a.center(), main.center(), big=True)
            yield 0.3
            for t in targets:
                if not t.alive and sk["kind"] != "heal":
                    continue
                if sk["kind"] in ("phys", "mag"):
                    self.hit(a, t, sk["kind"], sk["power"], sk.get("element"), sk.get("crit_bonus", 0))
                    for k, v in sk.get("status", {}).items():
                        if t.alive:
                            self.add_status(t, k, v)
                    if t.alive and "status_if_mech" in sk and "기계" in t.enemy.get("tags", []):
                        for k, v in sk["status_if_mech"].items():
                            self.add_status(t, k, v)
                elif sk["kind"] == "heal" and t.alive:
                    self.apply_heal(t, int(a.stat("mag") * sk["power"] * random.uniform(0.95, 1.05) + 10))
                    if sk.get("cleanse"):
                        for k in ("burn", "blind", "stop"):
                            t.status.pop(k, None)
                elif sk["kind"] in ("buff", "debuff"):
                    for k, v in sk["status"].items():
                        self.add_status(t, k, v)
                yield 0.08
            if sk.get("reset_steam"):
                ch.steam = 0
            yield 0.25
            yield from self.back(a)
            yield 0.3
        a.atb = 0
        self.game.emit("action_done", actor=ch.id)

    def enemy_turn(self, e):
        spec = e.enemy
        if spec.get("rage") and not e.raged and e.hp <= e.max_hp * spec["rage"]["hp_ratio"]:
            e.raged = True
            self.say(spec["rage"]["line"], 1.4)
            self.effects += [fx.Flash((255, 80, 60), 120), fx.Ring(e.center(), (255, 90, 60), 20, 220, 10, 0.6)]
            self.game.audio.sfx("sfx_steam")
            yield 1.0
        acts = spec["actions"]
        act = random.choices(acts, weights=[x["weight"] for x in acts])[0]
        alive = self.living(True)
        if not alive:
            return
        taunters = [p for p in alive if "taunt" in p.status]
        if act.get("target") == "all":
            targets = alive
        else:
            targets = [taunters[0] if taunters else random.choice(alive)]
        self.say(act["name"], 1.0)
        yield 0.3
        yield from self.lunge(e, targets[0], 90)
        self.game.audio.sfx("sfx_slash" if act["fx"] == "claw" else "sfx_fire")
        for t in targets:
            self.effects += fx.make(act["fx"], e.center(), t.center())
        yield 0.15
        for t in targets:
            self.hit(e, t, act["kind"], act["power"], None)
            if t.alive:
                for k, v in act.get("status", {}).items():
                    if random.random() < 0.5:
                        self.add_status(t, k, v)
                if act.get("drain_mp"):
                    t.mp = max(0, t.mp - act["drain_mp"])
                    self.float_text(t, f"MP -{act['drain_mp']}", C["mp"], 22)
        yield 0.2
        yield from self.back(e)
        yield 0.3
        e.atb = 0

    # ------------------------------------------------------------ 대미지 계산
    def hit(self, a, t, kind, power, element, crit_bonus=0.0):
        if kind == "phys" and "blind" in a.status and random.random() < 0.5:
            self.float_text(t, "MISS", C["gray"], 26)
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
            dmg *= B["steam_pressure"]["power_bonus"]
            a.boost = False
            a.status["overheat"] = 1          # story.json: 과열 상태가 되면 다음 턴 행동 불가
            tags.append(("증기압 해방!", (255, 170, 90)))
        if t.enemy and element:
            if element in t.enemy.get("weak", []):
                dmg *= 1.5
                tags.append(("약점!", (255, 220, 90)))
            elif element in t.enemy.get("resist", []):
                dmg *= 0.6
                tags.append(("내성", C["gray"]))
        if "exposed" in t.status:
            dmg *= 1.3
        if random.random() < 0.08 + crit_bonus:
            dmg *= 1.6
            tags.append(("치명타!", (255, 120, 90)))
        if "guard" in t.status:
            dmg *= 0.5
        dmg = max(1, int(dmg))
        self.apply_damage(t, dmg, a)
        for i, (s, col) in enumerate(tags):
            self.effects.append(fx.FloatText(t.center() + pygame.Vector2(0, -50 - i * 26), s, col, 20, bounce=False))
        # 루크 증기압
        sp = B["steam_pressure"]
        for f, gain in ((a, sp["on_hit_dealt"]), (t, sp["on_hit_taken"])):
            if f.party and f.ref.id == "luke" and kind == "phys" and f.alive:
                before = f.ref.steam
                f.ref.steam = min(sp["max"], f.ref.steam + gain)
                if before < sp["max"] <= f.ref.steam:
                    f.boost = True
                    f.ref.steam = 0
                    self.float_text(f, "증기압 MAX!", (255, 170, 90), 24)
                    self.effects += fx.make("steam", f.center(), f.center())

    def apply_damage(self, t, dmg, src, quiet=False):
        t.hp = max(0, t.hp - dmg)
        t.flash = 0.18
        t.shake = 0.35
        if not quiet:
            self.float_text(t, str(dmg), C["white"] if not t.party else (255, 140, 130), 34)
            self.game.audio.sfx("sfx_hit")
        self.game.emit("damage", target=t.name, amount=dmg)
        if not t.alive:
            t.status.clear()
            t.atb = 0
            if t in self.ready:
                self.ready.remove(t)
            if not t.party:
                self.game.audio.sfx("sfx_enemy_die")
                self.effects.append(fx.burst(t.center(), 40, (255, 160, 90), (80, 300), size=(3, 7)))

    def apply_heal(self, t, amount):
        before = t.hp
        t.hp = min(t.max_hp, t.hp + amount)
        self.float_text(t, f"+{t.hp - before}", (120, 255, 170), 32)

    def add_status(self, t, k, v):
        t.status[k] = max(t.status.get(k, 0), v)
        if k == "stop":
            t.atb = 0
        self.effects.append(fx.FloatText(t.center() + pygame.Vector2(0, -70), STATUS_NAMES.get(k, k),
                                         C["ether"] if t.party == False else C["brass_light"], 20, bounce=False))

    # ------------------------------------------------------------ 종료 처리
    def check_end(self):
        if self.state in ("victory", "defeat"):
            return
        if not self.living(False):
            self.victory()
        elif not self.living(True):
            self.defeat()

    def victory(self):
        self.state = "victory"
        self.game.audio.play_bgm("victory", loop=False, fade_ms=0)
        exp = sum(e.enemy["exp"] for e in self.enemies)
        gold = sum(e.enemy["gold"] for e in self.enemies)
        st = self.game.state
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
                    self.effects += fx.make("levelup", f.center(), f.center())
            else:
                ch.hp = 1          # 전투 후 1로 부활
        if ups:
            self.game.audio.sfx("sfx_levelup")
        self.result = {"kind": "victory", "exp": exp, "gold": gold, "ups": ups, "t": self.t}
        self.game.emit("victory", exp=exp, gold=gold, levelups={k: [u["level"] for u in v] for k, v in ups.items()})

    def defeat(self):
        self.state = "defeat"
        self.game.audio.stop_bgm()
        self.result = {"kind": "defeat", "t": self.t}
        self.game.emit("defeat")

    def finish(self):
        kind = self.result["kind"]
        if kind != "defeat":
            for f in self.party:
                f.ref.hp, f.ref.mp = max(f.hp, 1 if kind == "victory" else f.hp), f.mp
                if f.ref.hp <= 0:
                    f.ref.hp = 1

        def done():
            self.game.pop()
            self.game.emit("battle_end", result=kind)
            if kind == "victory" and self.on_win:
                self.on_win()
            elif kind == "defeat" and self.on_lose:
                self.on_lose()
        self.game.transition(done, 0.35)

    # ------------------------------------------------------------ 그리기
    def draw(self, surf):
        surf.blit(self.bg, (0, 0))
        self.glow.fill((0, 0, 0))
        # 적 (뒤쪽부터)
        for e in sorted(self.enemies, key=lambda f: f.home.y):
            self.draw_enemy(surf, e)
        for p in sorted(self.party, key=lambda f: f.home.y):
            self.draw_member(surf, p)
        for e in self.effects:
            if not isinstance(e, fx.FloatText):
                e.draw(surf, self.glow)
        surf.blit(self.glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        for e in self.effects:
            if isinstance(e, fx.FloatText):
                e.draw(surf, self.glow)
        self.draw_targets(surf)
        self.draw_hud(surf)
        if self.banner:
            s = self.banner[0]
            w = assets.font(26, True).size(s)[0] + 80
            r = pygame.Rect(0, 0, w, 52)
            r.midtop = (cfg.SCREEN_W // 2, 24)
            ui.brass_window(surf, r, 230)
            ui.text(surf, s, r.center, 26, C["white"], bold=True, anchor="center")
        if self.state in ("victory", "defeat"):
            self.draw_result(surf)

    def draw_enemy(self, surf, e):
        if not e.alive and e.dead_t > 0.6:
            return
        img = assets.image(e.enemy["sprite"])
        bob = math.sin(self.t * 2.4 + e.home.x) * 4
        pos = e.pos + pygame.Vector2(0, bob)
        sh = pygame.Surface((img.get_width(), 30), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 100), sh.get_rect())
        surf.blit(sh, sh.get_rect(center=(e.pos.x, e.pos.y)))
        if e.flash > 0 or not e.alive or e.raged:
            img = img.copy()
            if e.flash > 0:
                img.fill((200, 200, 200), special_flags=pygame.BLEND_RGB_ADD)
            if e.raged:
                img.fill((60, 0, 0), special_flags=pygame.BLEND_RGB_ADD)
            if not e.alive:
                img.set_alpha(int(255 * max(0, 1 - e.dead_t / 0.6)))
        surf.blit(img, img.get_rect(midbottom=(pos.x, pos.y + 10 + (e.dead_t * 40 if not e.alive else 0))))
        if "stop" in e.status:
            ui.text(surf, "정지", (pos.x, pos.y - img.get_height() - 4), 18, C["ether"], anchor="center", outline=True)

    def draw_member(self, surf, p):
        sheet = assets.image("characters/chr_" + p.ref.id + ".png", 1.5)
        fw, fh = 72, 108
        moving = p.offset.length() > 2
        frame = int(self.t * 8) % 4 if moving else 0
        row = cfg.DIR_ROW["nw"]
        spr = sheet.subsurface((frame * fw, row * fh, fw, fh))
        sh = pygame.Surface((56, 18), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 110), sh.get_rect())
        surf.blit(sh, sh.get_rect(center=(p.pos.x, p.pos.y)))
        if not p.alive:
            spr = pygame.transform.rotate(spr, 90)
            spr.fill((90, 90, 110), special_flags=pygame.BLEND_RGB_MULT)
            surf.blit(spr, spr.get_rect(midbottom=(p.pos.x, p.pos.y + 6)))
            return
        if p.flash > 0:
            spr = spr.copy()
            spr.fill((180, 80, 80), special_flags=pygame.BLEND_RGB_ADD)
        surf.blit(spr, spr.get_rect(midbottom=(p.pos.x, p.pos.y + 4)))
        if p is self.actor and self.state == "command":
            ui.gear_cursor(surf, (p.pos.x, p.pos.y - fh - 14), self.t)

    def draw_targets(self, surf):
        if not self.target_mode:
            return
        kind, cands, idx, _ = self.target_mode
        sel = [cands[idx]] if kind == "single" else cands
        for f in sel:
            top = f.center() + pygame.Vector2(0, -60 - abs(math.sin(self.t * 6)) * 10)
            pygame.draw.polygon(surf, C["brass_light"], [(top.x - 12, top.y - 16), (top.x + 12, top.y - 16), (top.x, top.y)])
            pygame.draw.polygon(surf, C["ink"], [(top.x - 12, top.y - 16), (top.x + 12, top.y - 16), (top.x, top.y)], 2)
            ui.text(surf, f.name, (top.x, top.y - 34), 18, C["white"], anchor="center", outline=True)

    def draw_hud(self, surf):
        # 파티 상태창
        r = pygame.Rect(540, 548, 724, 160)
        ui.brass_window(surf, r)
        for i, p in enumerate(self.party):
            y = r.y + 16 + i * 46
            active = p is self.actor and self.state == "command"
            col = C["brass_light"] if active else (C["white"] if p.alive else C["gray"])
            ui.text(surf, p.name.split()[0], (r.x + 22, y + 6), 20, col, bold=active)
            ui.text(surf, f"Lv{p.ref.level}", (r.x + 150, y + 8), 16, C["parchment"])
            ui.gauge(surf, (r.x + 225, y + 6, 160, 16), p.hp / p.max_hp, C["hp"])
            ui.text(surf, f"{p.hp:>4}/{p.max_hp}", (r.x + 305, y + 24), 16, C["white"], anchor="midtop")
            ui.gauge(surf, (r.x + 400, y + 6, 110, 16), p.mp / max(1, p.max_mp), C["mp"])
            ui.text(surf, f"{p.mp:>3}/{p.max_mp}", (r.x + 455, y + 24), 16, C["white"], anchor="midtop")
            ui.gauge(surf, (r.x + 526, y + 6, 170, 16), p.atb / B["atb"]["max"], C["atb"], glow=True)
            st = " ".join(STATUS_NAMES.get(k, k) for k in p.status)
            if p.ref.id == "luke":
                ui.gauge(surf, (r.x + 526, y + 26, 170, 10), p.ref.steam / B["steam_pressure"]["max"],
                         (255, 150, 80), border=C["copper"])
                if p.boost:
                    st = (st + " 증기압 MAX").strip()
            if st:
                ui.text(surf, st, (r.x + 22, y + 28), 14, C["ether"])
        ui.text(surf, "HP", (r.x + 225, r.y - 2), 14, C["parchment"])
        ui.text(surf, "MP", (r.x + 400, r.y - 2), 14, C["parchment"])
        ui.text(surf, "ATB", (r.x + 526, r.y - 2), 14, C["parchment"])
        # 적 HP (간단 표시)
        er = pygame.Rect(16, 16, 300, 22 + 30 * len(self.enemies))
        ui.brass_window(surf, er, 190)
        for i, e in enumerate(self.enemies):
            y = er.y + 12 + i * 30
            ui.text(surf, e.name, (er.x + 16, y), 18, C["white"] if e.alive else C["gray"])
            ui.gauge(surf, (er.x + 170, y + 4, 110, 12), e.hp / e.max_hp, C["hp"])
        # 명령 창
        if self.state == "command" and self.menu:
            cr = pygame.Rect(16, 456, 250, 254)
            ui.parchment_window(surf, cr)
            self.menu.draw(surf, cr.x + 40, cr.y + 52, cr.w - 80, self.t, 22, 32, ink=C["ink"], dim=(150, 130, 110))
            if self.sub:
                kind, m, data = self.sub
                sr = pygame.Rect(266, 430, 300, 280)
                ui.parchment_window(surf, sr)
                m.draw(surf, sr.x + 40, sr.y + 52, sr.w - 84, self.t, 20, 34, ink=C["ink"], dim=(150, 130, 110))
                d = data[m.index]
                desc = d["description"] if kind == "skill" else B["items"][d]["desc"]
                dr = pygame.Rect(330, 86, 620, 56)
                ui.brass_window(surf, dr, 230)
                ui.text(surf, ui.wrap(desc, dr.w - 30, 18)[0], (dr.x + 16, dr.y + 18), 18, C["white"])

    def draw_result(self, surf):
        res = self.result
        r = pygame.Rect(250, 90, 780, 410 if res["kind"] == "victory" else 200)
        ui.parchment_window(surf, r)
        if res["kind"] == "defeat":
            ui.text(surf, "전멸했다……", (r.centerx, r.y + 84), 34, C["red"], bold=True, anchor="center", shadow=False)
            ui.text(surf, "Z: 계속", (r.centerx, r.y + 130), 20, C["ink"], anchor="center", shadow=False)
            return
        ui.text(surf, "승리!", (r.centerx, r.y + 78), 34, C["ink"], bold=True, anchor="center", shadow=False)
        ui.text(surf, f"EXP +{res['exp']}    GOLD +{res['gold']}", (r.centerx, r.y + 118), 22, C["ink"],
                anchor="center", shadow=False)
        for i, f in enumerate(self.party):
            ch = f.ref
            y = r.y + 160 + i * 66
            ui.text(surf, ch.name, (r.x + 56, y), 22, C["ink"], bold=True, shadow=False)
            ui.text(surf, f"Lv {ch.level}", (r.x + 250, y), 22, C["ink"], shadow=False)
            ui.gauge(surf, (r.x + 330, y + 4, 190, 14), ch.exp / exp_to_next(ch.level), C["atb"], border=C["ink"])
            ui.text(surf, f"다음 Lv까지 {exp_to_next(ch.level) - ch.exp}", (r.x + 330, y + 24), 16, C["ink"], shadow=False)
            if ch.id in res["ups"]:
                u = res["ups"][ch.id][-1]
                blink = int(self.t * 4) % 2 == 0
                ui.text(surf, "LEVEL UP!", (r.x + 545, y - 2), 22, C["red"] if blink else C["copper"], bold=True, shadow=False)
                d = u["diffs"]
                ui.text(surf, f"HP+{d['hp']} 공+{d['atk']} 마+{d['mag']}", (r.x + 545, y + 24), 14, C["ink"], shadow=False)
                learned = [n for up in res["ups"][ch.id] for n in up["learned"]]
                if learned:
                    ui.text(surf, "새 스킬: " + ", ".join(learned), (r.x + 56, y + 26), 16, C["ether_deep"], shadow=False)
        ui.text(surf, "Z: 계속", (r.centerx, r.bottom - 58), 18, C["ink"], anchor="center", shadow=False)
