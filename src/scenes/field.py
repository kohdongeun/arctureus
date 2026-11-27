"""필드: 아이소메트릭 맵 렌더링, 이동, NPC 대화, 맵 이동, 인카운트, 보스 이벤트."""
from __future__ import annotations

import math
import random

import pygame

from src import config as cfg
from src.engine import assets
from src.engine.core import Scene
from src.scenes.dialogue import Dialogue
from src.ui import widgets as ui

C = cfg.C
HW, HH = cfg.TILE_W // 2, cfg.TILE_H // 2
KEY_DIR = {"up": "ne", "right": "se", "down": "sw", "left": "nw"}
WALK_SPEED = 5.0  # 타일/초
SIGN_TEXT = "← 모르간 수리점 (증기 기기 수리)   ↓ 남쪽 끝: 지하 배수로 입구"


def iso(x, y):
    """그리드 → 월드 픽셀 (타일 윗꼭짓점 기준)"""
    return (x - y) * HW, (x + y) * HH


class Walker:
    def __init__(self, x, y, d, sheet, npc=None):
        self.x, self.y = x, y
        self.fx, self.fy = float(x), float(y)
        self.dir = d
        self.sheet = sheet
        self.moving = False
        self.src = (x, y)
        self.prog = 0.0
        self.anim = 0.0
        self.npc = npc
        self.home = (x, y)
        self.wait = random.uniform(1.0, 3.0)
        self.talks = 0

    def start_move(self, d):
        dx, dy = cfg.DIRS[d]
        self.dir = d
        self.src = (self.x, self.y)
        self.x, self.y = self.x + dx, self.y + dy
        self.prog = 0.0
        self.moving = True

    def update(self, dt):
        if not self.moving:
            return False
        self.prog = min(1.0, self.prog + WALK_SPEED * dt)
        self.anim += WALK_SPEED * dt * 2
        self.fx = self.src[0] + (self.x - self.src[0]) * self.prog
        self.fy = self.src[1] + (self.y - self.src[1]) * self.prog
        if self.prog >= 1.0:
            self.moving = False
            self.fx, self.fy = float(self.x), float(self.y)
            return True   # 한 칸 이동 완료
        return False

    def frame(self):
        return int(self.anim) % 4 if self.moving else 0

    def depth(self):
        return max(self.x + self.y, self.src[0] + self.src[1]) if self.moving else self.x + self.y


class FieldMap:
    def __init__(self, map_id):
        d = assets.load_json(f"maps/{map_id}.json")
        self.d = d
        self.id = map_id
        self.name = d["name"]
        self.w, self.h = d["size"]
        g = d["ground"]
        self.ground = [[g["fill"]] * self.w for _ in range(self.h)]
        for r in g["rects"]:
            for y in range(r["y"], r["y"] + r["h"]):
                for x in range(r["x"], r["x"] + r["w"]):
                    if 0 <= x < self.w and 0 <= y < self.h:
                        self.ground[y][x] = r["tile"]
        blocked_tiles = set(d.get("blocked_tiles", []))
        self.blocked = {(x, y) for y in range(self.h) for x in range(self.w) if self.ground[y][x] in blocked_tiles}
        # 건물 → 블록 쌓기
        self.blocks = []   # (x, y, z, image)
        for b in d.get("buildings", []):
            wall, roof = b["wall"], b.get("roof", "roof")
            door = tuple(b["door"]) if "door" in b else None
            for y in range(b["y"], b["y"] + b["l"]):
                for x in range(b["x"], b["x"] + b["w"]):
                    self.blocked.add((x, y))
                    for z in range(b["h"]):
                        if z == b["h"] - 1 and b["h"] > 1:
                            name = roof
                        elif (x, y) == door and z == 0:
                            name = f"{wall}_door" if assets.has_image(f"tiles/block_{wall}_door.png") else wall
                        elif z >= 1 and (x + y + z) % 2 == 0 and assets.has_image(f"tiles/block_{wall}_window.png"):
                            name = f"{wall}_window"
                        else:
                            name = wall
                        self.blocks.append((x, y, z, name))
        self.props = d.get("props", [])
        for p in self.props:
            if p["type"] != "exit":
                self.blocked.add((p["x"], p["y"]))
        self.exits = {}
        for e in d.get("exits", []):
            for t in e["tiles"]:
                self.exits[tuple(t)] = e
        self.lights = [tuple(l) for l in d.get("lights", [])] + [(p["x"], p["y"]) for p in self.props if p["type"] == "lamp"]

    def walkable(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h and (x, y) not in self.blocked


class FieldScene(Scene):
    def __init__(self, game, map_id, pos=None, d=None):
        super().__init__(game)
        self.load_map(map_id, pos, d)
        self.t = 0.0
        self.glow = pygame.Surface((cfg.SCREEN_W, cfg.SCREEN_H))
        self._light = self._make_light(150)

    # ------------------------------------------------------------ 맵 로드
    def load_map(self, map_id, pos=None, d=None):
        st = self.game.state
        self.map = FieldMap(map_id)
        start = self.map.d["start"]
        pos = pos or start["pos"]
        d = d or start["dir"]
        self.player = Walker(pos[0], pos[1], d, "characters/chr_luke.png")
        self.npcs = []
        story_town = self.game.story["npc_dialogues"].get(map_id, {"npcs": []})
        for n in self.map.d.get("npcs", []):
            prof = next((p for p in story_town["npcs"] if p["id"] == n["id"]), None)
            w = Walker(n["x"], n["y"], n["dir"], f"characters/chr_{n['sprite']}.png", npc={**n, "profile": prof})
            self.npcs.append(w)
        self.boss = None
        b = self.map.d.get("boss")
        if b and b["flag"] not in st.flags:
            self.boss = b
            self.map.blocked.add((b["x"], b["y"]))
        self.steps = 0
        self.banner_t = 0.0
        st.map_id, st.pos, st.dir = map_id, (self.player.x, self.player.y), d
        self.game.audio.play_bgm(self.map.d["bgm"])
        self.game.emit("map_enter", map=map_id)
        flag = f"entered_{map_id}"
        if self.map.d.get("on_first_enter") and flag not in st.flags:
            st.flags.add(flag)
            self.pending_dialogue = self.map.d["on_first_enter"]
        else:
            self.pending_dialogue = None

    def on_enter(self):
        self._flush_pending()

    def on_resume(self):
        self.game.audio.play_bgm(self.map.d["bgm"])

    def _flush_pending(self):
        if self.pending_dialogue:
            lines, self.pending_dialogue = self.pending_dialogue, None
            self.game.push(Dialogue(self.game, lines))

    # ------------------------------------------------------------ 업데이트
    def occupied(self, x, y, ignore=None):
        if (self.player.x, self.player.y) == (x, y) and ignore is not self.player:
            return True
        return any((n.x, n.y) == (x, y) for n in self.npcs if n is not ignore)

    def update(self, dt):
        self.t += dt
        self.banner_t += dt
        if self.pending_dialogue:
            self._flush_pending()
            return
        inp = self.game.input
        p = self.player
        if p.update(dt):
            self.on_step()
            if self.game.scene is not self:
                return
        if not p.moving:
            want = next((KEY_DIR[k] for k in ("up", "right", "down", "left") if inp.is_held(k)), None)
            if want:
                dx, dy = cfg.DIRS[want]
                if self.map.walkable(p.x + dx, p.y + dy) and not self.occupied(p.x + dx, p.y + dy, p):
                    p.start_move(want)
                else:
                    p.dir = want
            elif inp.was_pressed("confirm"):
                self.interact()
            elif inp.was_pressed("cancel"):
                from src.scenes.menu import MenuScene
                self.game.audio.sfx("sfx_menu")
                self.game.push(MenuScene(self.game))
        for n in self.npcs:
            self.update_npc(n, dt)

    def update_npc(self, n, dt):
        n.update(dt)
        radius = n.npc.get("wander", 0)
        if not radius or n.moving:
            return
        n.wait -= dt
        if n.wait <= 0:
            n.wait = random.uniform(1.5, 4.0)
            d = random.choice(list(cfg.DIRS))
            dx, dy = cfg.DIRS[d]
            tx, ty = n.x + dx, n.y + dy
            if (abs(tx - n.home[0]) <= radius and abs(ty - n.home[1]) <= radius
                    and self.map.walkable(tx, ty) and not self.occupied(tx, ty, n) and (tx, ty) not in self.map.exits):
                n.start_move(d)

    def on_step(self):
        p = self.player
        st = self.game.state
        st.pos, st.dir = (p.x, p.y), p.dir
        self.steps += 1
        self.game.emit("step", pos=(p.x, p.y), map=self.map.id)
        if (p.x, p.y) in self.map.exits:
            e = self.map.exits[(p.x, p.y)]
            self.game.audio.sfx("sfx_door")
            self.game.transition(lambda: self.load_map(e["to"], e["pos"], e["dir"]))
            return
        b = self.boss
        if b and p.x >= b["trigger_x_from"]:
            self.start_boss()
            return
        enc = self.map.d.get("encounters")
        if enc and self.steps >= enc["min_steps"] and p.x >= enc.get("safe_x_below", 0):
            if random.random() < enc["rate"]:
                self.steps = 0
                table = assets.load_json("battle.json")["encounters"][enc["table"]]
                group = random.choices(table, weights=[g["weight"] for g in table])[0]
                self.start_battle(group["enemies"])

    def start_battle(self, enemy_ids, boss=False, on_win=None):
        from src.scenes.battle import BattleScene
        self.game.audio.sfx("sfx_encounter")
        self.game.emit("encounter", enemies=enemy_ids)
        floor = self.map.d.get("battle_floor", "cobble")

        def go():
            self.game.push(BattleScene(self.game, enemy_ids, floor, boss=boss, on_win=on_win, on_lose=self.on_defeat))
        self.game.transition(go, 0.3, (255, 255, 255))

    def start_boss(self):
        b = self.boss
        scene = next(s for c in self.game.story["chapters"] for s in c["scenes"] if s["id"] == b["pre_scene"])
        lines = [l for l in scene["dialogue"] if l["speaker"] not in ("masked_knight",)]

        def win():
            self.game.state.flags.add(b["flag"])
            self.map.blocked.discard((b["x"], b["y"]))
            self.boss = None
            self.pending_dialogue = b["post"]

        self.game.push(Dialogue(self.game, lines, on_finish=lambda: self.start_battle([b["id"]], True, win)))

    def on_defeat(self):
        st = self.game.state
        for c in st.party:
            c.full_heal()
        st.flags.discard("entered_chimney_ward")
        self.pending_dialogue = None
        self.load_map("chimney_ward", (4, 7), "se")
        self.pending_dialogue = [{"speaker": "narration", "text": "……정신을 차려 보니 모르간 수리점 앞이었다. 모두 기운을 되찾았다."}]

    def interact(self):
        p = self.player
        dx, dy = cfg.DIRS[p.dir]
        tx, ty = p.x + dx, p.y + dy
        for n in self.npcs:
            if (n.x, n.y) == (tx, ty) and not n.moving:
                n.dir = {"ne": "sw", "sw": "ne", "se": "nw", "nw": "se"}[p.dir]
                prof = n.npc["profile"]
                pool = []
                for k in n.npc["keys"]:
                    pool += prof["dialogues"].get(k, []) if prof else []
                if not pool:
                    return
                line = pool[n.talks % len(pool)]
                n.talks += 1
                self.game.audio.sfx("sfx_confirm")
                self.game.emit("talk", npc=n.npc["id"])
                self.game.push(Dialogue(self.game, [{"speaker": n.npc["id"], "text": line}],
                                        npc_sprites={n.npc["id"]: n.sheet}))
                return
        for pr in self.map.props:
            if (pr["x"], pr["y"]) == (tx, ty) and pr["type"] == "sign":
                self.game.push(Dialogue(self.game, [{"speaker": "system", "text": SIGN_TEXT}]))
                return

    # ------------------------------------------------------------ 그리기
    def camera(self):
        wx, wy = iso(self.player.fx, self.player.fy)
        return cfg.SCREEN_W // 2 - wx, cfg.SCREEN_H // 2 - wy - 40

    def _make_light(self, r):
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        for i in range(r, 0, -3):
            a = int(255 * (1 - i / r) ** 1.4)
            pygame.draw.circle(s, (0, 0, 0, a), (r, r), i)
        return s

    _shadow = None

    def draw(self, surf):
        if FieldScene._shadow is None:
            FieldScene._shadow = pygame.Surface((32, 12), pygame.SRCALPHA)
            pygame.draw.ellipse(FieldScene._shadow, (0, 0, 0, 90), (0, 0, 32, 12))
        surf.fill((14, 12, 18))
        ox, oy = self.camera()
        m = self.map
        # 1) 바닥
        for y in range(m.h):
            for x in range(m.w):
                sx, sy = iso(x, y)
                sx, sy = sx + ox, sy + oy
                if -70 < sx < cfg.SCREEN_W + 70 and -40 < sy < cfg.SCREEN_H + 40:
                    surf.blit(assets.image(f"tiles/tile_{m.ground[y][x]}.png"), (sx - HW, sy))
                    if (x, y) in m.exits:
                        surf.blit(assets.image("tiles/prop_exit.png"), (sx - HW, sy))
        # 2) 깊이 정렬된 물체
        items = []
        for (x, y, z, name) in m.blocks:
            items.append((x + y, 0, z, ("block", x, y, z, name)))
        for pr in m.props:
            items.append((pr["x"] + pr["y"], 1, 0, ("prop", pr)))
        for n in self.npcs:
            items.append((n.depth(), 2, 0, ("walker", n)))
        items.append((self.player.depth(), 2, 0, ("walker", self.player)))
        if self.boss:
            items.append((self.boss["x"] + self.boss["y"], 2, 0, ("boss", self.boss)))
        items.sort(key=lambda it: (it[0], it[1], it[2]))
        for _, _, _, it in items:
            kind = it[0]
            if kind == "block":
                _, x, y, z, name = it
                sx, sy = iso(x, y)
                sx, sy = sx + ox, sy + oy
                if -80 < sx < cfg.SCREEN_W + 80 and -200 < sy < cfg.SCREEN_H + 80:
                    surf.blit(assets.image(f"tiles/block_{name}.png"), (sx - HW, sy - cfg.BLOCK_H * (z + 1)))
            elif kind == "prop":
                pr = it[1]
                img = assets.image(f"tiles/prop_{pr['type']}.png")
                sx, sy = iso(pr["x"], pr["y"])
                surf.blit(img, img.get_rect(midbottom=(sx + ox, sy + oy + HH + 6)))
            elif kind == "walker":
                w = it[1]
                sx, sy = iso(w.fx, w.fy)
                surf.blit(FieldScene._shadow, (sx + ox - 16, sy + oy + HH - 6))
                sheet = assets.image(w.sheet)
                surf.blit(sheet, (sx + ox - 24, sy + oy + HH - 70),
                          pygame.Rect(w.frame() * 48, cfg.DIR_ROW[w.dir] * 72, 48, 72))
            elif kind == "boss":
                b = it[1]
                img = assets.image(f"monsters/{b['id']}.png", 0.75)
                sx, sy = iso(b["x"], b["y"])
                bob = math.sin(self.t * 2) * 3
                surf.blit(img, img.get_rect(midbottom=(sx + ox, sy + oy + HH + 10 + bob)))
        # 3) 조명: 어두운 맵은 빛 구멍을 뚫은 어둠을 덮고, 에테르 가로등은 가산 합성 광원
        if m.d.get("dark"):
            dark = pygame.Surface((cfg.SCREEN_W, cfg.SCREEN_H), pygame.SRCALPHA)
            dark.fill((8, 10, 22, m.d["dark"]))
            light_points = [(self.player.fx, self.player.fy, 1.3)] + [(lx, ly, 1.0) for lx, ly in m.lights]
            for lx, ly, k in light_points:
                sx, sy = iso(lx, ly)
                L = self._light if k == 1.0 else pygame.transform.scale(self._light, (int(300 * k), int(300 * k)))
                dark.blit(L, L.get_rect(center=(sx + ox, sy + oy)), special_flags=pygame.BLEND_RGBA_SUB)
            surf.blit(dark, (0, 0))
        self.glow.fill((0, 0, 0))
        for lx, ly in m.lights:
            sx, sy = iso(lx, ly)
            pulse = 0.85 + 0.15 * math.sin(self.t * 5 + lx)
            for r, a in ((52, 10), (32, 22), (15, 55)):
                pygame.draw.circle(self.glow, tuple(int(c * a / 100 * pulse) for c in C["ether"]),
                                   (sx + ox, sy + oy - 66), r)
        surf.blit(self.glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        # 4) 맵 이름 배너
        if self.banner_t < 2.6:
            a = min(1, self.banner_t * 3, (2.6 - self.banner_t) * 2)
            band = pygame.Surface((520, 64), pygame.SRCALPHA)
            band.fill((10, 12, 24, int(190 * a)))
            surf.blit(band, (cfg.SCREEN_W // 2 - 260, 40))
            ui.text(surf, m.name, (cfg.SCREEN_W // 2, 72), 30, C["brass_light"], bold=True, anchor="center")
        ui.text(surf, f"{m.name}", (16, 12), 18, C["parchment"])
        ui.text(surf, "X: 메뉴", (cfg.SCREEN_W - 16, 12), 18, C["parchment"], anchor="topright")
