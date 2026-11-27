"""3D 전투 화면: 필드 지형 위에서 벌이는 빌보드 ATB 전투.

규칙은 src/systems/battle_core.py (2D 와 같은 수치), 여기는 연출·입력·UI 만 담당한다.
- 인카운트 지점에서 카메라가 전투 구도로 이동, 파티(필드의 빌보드 그대로)와 적이 마주 선다
- 명령 창(공격/스킬/방어/아이템/도주) → 대상 지정 → 행동 연출(돌진·이펙트·대미지 숫자·피격)
- 이펙트: 가산 합성 빛 입자, 바닥 링, 광선, 칼 궤적, 빛기둥, 시계 고리
- 결과 창: EXP·골드·레벨업·새 스킬
"""
from __future__ import annotations

import math
import os
import random

from panda3d.core import ColorBlendAttrib, TransparencyAttrib
from ursina import Entity, Quad, Text, Texture, Vec3, camera, color, destroy, lerp

from src.systems.battle_core import BattleCore, STATUS_NAMES
from src3d.shaders import sprite_mesh, sprite_shader, unlit_shader

UI_DARK = color.rgba(0.06, 0.07, 0.12, 0.86)
GOLD = color.rgba32(226, 184, 102)
INK = color.rgba32(58, 40, 26)


def rgb(c, a=255):
    return color.rgba32(c[0], c[1], c[2], a)


# ====================================================================== UI 부품
class Panel(Entity):
    def __init__(self, w, h, x, y, z=0.0, fill=UI_DARK, border=GOLD, parent=None):
        super().__init__(parent=parent or camera.ui, position=(x, y), z=z)
        Entity(parent=self, model=Quad(radius=0.012, aspect=(w + 0.008) / (h + 0.008)), scale=(w + 0.008, h + 0.008),
               color=border, z=0.002)
        Entity(parent=self, model=Quad(radius=0.01, aspect=w / h), scale=(w, h), color=fill, z=0.001)


class Bar(Entity):
    def __init__(self, parent, x, y, w, h, col):
        super().__init__(parent=parent, position=(x, y), z=-0.001)
        self.w = w
        Entity(parent=self, model="quad", origin=(-0.5, 0), scale=(w, h), color=color.rgba(0, 0, 0, 0.6))
        self.fill = Entity(parent=self, model="quad", origin=(-0.5, 0), scale=(w, h * 0.7), color=col, z=-0.001)

    def set(self, ratio):
        self.fill.scale_x = max(0.0001, self.w * max(0.0, min(1.0, ratio)))


def label(parent, text, x, y, scale=0.85, col=color.white, origin=(-0.5, 0), font=None):
    t = Text(parent=parent, text=text, position=(x, y), origin=origin, scale=scale, color=col, z=-0.002)
    if font:
        t.font = font
    return t


# ====================================================================== 이펙트
class FX:
    """가산 합성 빛 입자들. update 에서 움직이고 수명이 다하면 사라진다."""

    def __init__(self, tex):
        self.tex = tex
        self.items = []

    def _make(self, pos, scale, col, billboard=True, tex=None, additive=True):
        e = Entity(model="quad", texture=tex or self.tex, position=pos, scale=scale, billboard=billboard,
                   color=col, shader=unlit_shader)
        e.setTransparency(TransparencyAttrib.MAlpha)
        if additive:
            e.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha,
                                              ColorBlendAttrib.OOne))
        e.setDepthWrite(False)
        e.setBin("fixed", 50)
        e.hide(0b0001)
        return e

    def particle(self, pos, vel, life, size, col, grav=0.0, grow=0.0, additive=True):
        e = self._make(pos, size, col, additive=additive)
        self.items.append({"e": e, "v": Vec3(*vel), "life": life, "max": life, "g": grav, "size": size, "grow": grow,
                           "col": col})

    def burst(self, pos, n, col, speed=(1.5, 4.5), life=(0.35, 0.8), size=(0.12, 0.32), up=0.0, grav=0.0):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            el = random.uniform(-0.6, 1.1)
            s = random.uniform(*speed)
            v = (math.cos(a) * math.cos(el) * s, math.sin(el) * s + up, math.sin(a) * math.cos(el) * s)
            self.particle(pos, v, random.uniform(*life), random.uniform(*size), col, grav)

    def dust(self, pos, rgb_, n=5):
        """발밑 흙먼지 (일반 알파 합성 — 빛나지 않게)"""
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(0.4, 1.0)
            self.particle(pos + Vec3(math.cos(a) * 0.15, 0, math.sin(a) * 0.15),
                          (math.cos(a) * sp, random.uniform(0.3, 0.8), math.sin(a) * sp), random.uniform(0.35, 0.55),
                          random.uniform(0.18, 0.3), color.rgba(rgb_[0], rgb_[1], rgb_[2], 0.55), grav=1.5,
                          grow=0.6, additive=False)

    def ring(self, pos, col, r0=0.3, r1=2.6, life=0.5, ground=True, tex=None):
        e = self._make(pos + Vec3(0, 0.06, 0), r0 * 2, col, billboard=not ground, tex=tex)
        if ground:
            e.rotation_x = 90
        self.items.append({"e": e, "v": Vec3(0, 0, 0), "life": life, "max": life, "g": 0, "size": r0 * 2,
                           "grow": (r1 - r0) * 2 / life, "col": col, "ring": True})

    def beam(self, a, b, col, n=18, size=0.22):
        for i in range(n):
            p = lerp(a, b, i / (n - 1))
            self.particle(p, (0, 0, 0), 0.12 + i * 0.012, size, col)

    def pillar(self, pos, col, h=3.2, n=26):
        for _ in range(n):
            p = pos + Vec3(random.uniform(-0.35, 0.35), random.uniform(0, 0.4), random.uniform(-0.35, 0.35))
            self.particle(p, (0, random.uniform(2, 4.5), 0), random.uniform(0.5, 0.9), random.uniform(0.12, 0.26), col)
        e = self._make(pos + Vec3(0, h / 2, 0), (0.9, h), col)
        self.items.append({"e": e, "v": Vec3(0, 0, 0), "life": 0.7, "max": 0.7, "g": 0, "size": None, "grow": 0,
                           "col": col})

    def slash(self, pos, col, n=1, cam_right=Vec3(1, 0, 0)):
        for k in range(n):
            for i in range(14):
                t = i / 13
                ang = math.radians(-60 + 130 * t + k * 25)
                p = pos + cam_right * (math.cos(ang) * 0.9) + Vec3(0, math.sin(ang) * 0.9 + 0.2 * k, 0)
                self.particle(p, (0, 0, 0), 0.18 + t * 0.12, 0.24, col)

    def clock(self, pos, col):
        for i in range(12):
            a = i * math.tau / 12
            p = pos + Vec3(math.cos(a) * 0.9, math.sin(a) * 0.9, 0)
            self.particle(p, (math.cos(a) * 0.3, math.sin(a) * 0.3, 0), 0.9, 0.2, col)
        self.ring(pos, col, 0.2, 1.1, 0.8, ground=False)

    def update(self, dt):
        keep = []
        for it in self.items:
            it["life"] -= dt
            e = it["e"]
            if it["life"] <= 0:
                destroy(e)
                continue
            it["v"].y -= it["g"] * dt
            e.position += it["v"] * dt
            k = it["life"] / it["max"]
            if it.get("ring"):
                s = e.scale_x + it["grow"] * dt
                e.scale = (s, s, s)
            elif it["size"]:
                s = it["size"] * ((1 + it["grow"] * (1 - k)) if it["grow"] else (0.4 + 0.6 * k))
                e.scale = (s, s, s)
            c = it["col"]
            e.color = color.rgba(c.r, c.g, c.b, max(0.0, k) * c.a)
            keep.append(it)
        self.items = keep

    def clear(self):
        for it in self.items:
            destroy(it["e"])
        self.items = []


# ====================================================================== 적 빌보드
class EnemyView:
    def __init__(self, game, f, pos):
        from src3d.game import Motion
        # 1순위: 생성한 일러스트 assets/characters/monster/<적 id>.png (오른쪽=파티 쪽을 바라봄), 없으면 예전 2D 그림
        new = os.path.join(game_root(game), "assets", "characters", "monster", f.enemy["id"] + ".png")
        img = new if os.path.exists(new) else os.path.join(game_root(game), "assets", "images", f.enemy["sprite"])
        t = Texture(img)
        t.filtering = "mipmap"
        h = f.enemy.get("height", 3.0 if f.enemy.get("boss") else 1.6)
        w = h * t.width / t.height
        self.h, self.w = h, w
        self.boss = bool(f.enemy.get("boss"))
        self.floaty = "망각" in f.enemy.get("tags", [])           # 홀로우처럼 떠다니는 적
        y = game.world.h(pos.x, pos.z)
        self.home = Vec3(pos.x, y, pos.z)
        self.pos = Vec3(self.home)
        self.mo = Motion()
        self.shadow = Entity(model="quad", texture=game_tex(game, "textures3d/shadow.png"), rotation_x=90,
                             scale=(w * 0.9, w * 0.45), color=color.rgba(1, 1, 1, 0.65), shader=unlit_shader)
        self.shadow.setTransparency(TransparencyAttrib.MAlpha)
        self.body = Entity(model=sprite_mesh(), texture=t, billboard=True, scale=(w, h), double_sided=True,
                           shader=sprite_shader)
        self.body.setTransparency(TransparencyAttrib.MDual)
        for e in (self.shadow, self.body):
            e.hide(0b0001)
        self.alpha = 0.0
        self.dead_t = -1.0
        self.flash = 0.0
        self.t = random.uniform(0, 5)
        self.sync()

    def sync(self):
        mo = self.mo
        float_y = (0.25 + math.sin(self.t * 1.8) * 0.12) if self.floaty else 0.0
        breath = math.sin(self.t * (1.6 if self.boss else 2.4))
        dead = max(0.0, self.dead_t)
        p = self.pos + mo.off
        self.body.position = p + Vec3(0, float_y, 0)
        self.shadow.position = Vec3(p.x, self.home.y + 0.05, p.z)
        sink = 1 - min(1.0, dead / 0.7)                 # 쓰러지면 납작해지며 사라짐
        self.body.scale = (self.w * mo.sx * (1 + 0.25 * (1 - sink)), self.h * mo.sy * (1 + 0.02 * breath) * sink)
        b = self.body
        b.set_shader_input("lean", mo.lean + 0.02 * breath)
        b.set_shader_input("hop", mo.hop / max(0.01, self.h))
        b.set_shader_input("flash", max(self.flash * 3, mo.flash, 1.0 if 0 <= self.dead_t < 0.15 else 0.0))
        a = self.alpha * sink if self.dead_t >= 0 else self.alpha
        self.body.color = color.rgba(1, 1, 1, a)
        self.shadow.color = color.rgba(1, 1, 1, 0.65 * a)

    def head(self):
        return self.pos + self.mo.off + Vec3(0, self.h * 0.75, 0)

    def destroy(self):
        destroy(self.body)
        destroy(self.shadow)


def game_root(game):
    from src3d.game import ROOT
    return ROOT


def game_tex(game, rel):
    from src3d.game import tex
    return tex(rel)


# ====================================================================== 컷인
class CutIn:
    """화면을 가로지르는 띠 + 반신 일러스트 + 큰 글씨 (치명타·상위 스킬). 실제 시간으로 움직이고 그동안 전투는 멈춘다."""

    def __init__(self, f, title, sub="", col=(255, 196, 90), dur=1.05):
        from src3d.game import FIELD_DIR, FONT_TEXT, PORTRAIT_DIR
        self.dur, self.t = dur, 0.0
        self.root = Entity(parent=camera.ui, z=-0.7)
        self.dim = Entity(parent=self.root, model="quad", scale=(4, 2), color=color.rgba(0, 0, 0, 0), z=0.02)
        self.band = Entity(parent=self.root, rotation_z=-7)
        Entity(parent=self.band, model="quad", scale=(3.4, 0.36), color=color.rgba(0.07, 0.05, 0.09, 0.94), z=0.01)
        for y in (0.185, -0.185):
            Entity(parent=self.band, model="quad", y=y, scale=(3.4, 0.012), color=rgb(col), z=0.005)
        self.lines = []
        for _ in range(18):
            ln = Entity(parent=self.band, model="quad", position=(random.uniform(-1.7, 1.7), random.uniform(-0.16, 0.16)),
                        scale=(random.uniform(0.15, 0.6), random.uniform(0.002, 0.006)),
                        color=color.rgba(1, 1, 1, random.uniform(0.25, 0.7)), z=0.008)
            self.lines.append((ln, random.uniform(3.5, 7.0)))
        cid = f.ref.id if f.party else f.enemy["id"]
        path = next((p for p in (os.path.join(PORTRAIT_DIR, cid + ".png"), os.path.join(FIELD_DIR, cid + ".png"))
                     if os.path.exists(p)), None)
        self.pic = None
        if path:
            t = Texture(path)
            h = 0.62
            self.pic = Entity(parent=self.band, model="quad", texture=t, scale=(h * t.width / t.height, h),
                              position=(-1.6, 0.04), z=0.0)
        self.title = Text(parent=self.band, text=title, origin=(0, 0), position=(0.32, 0.03), scale=4.2, font=FONT_TEXT,
                          color=rgb(col), z=-0.01)
        self.title_sh = Text(parent=self.band, text=title, origin=(0, 0), position=(0.326, 0.024), scale=4.2,
                             font=FONT_TEXT, color=color.rgba(0, 0, 0, 0.8), z=-0.005)
        self.sub = Text(parent=self.band, text=sub, origin=(0, 0), position=(0.32, -0.09), scale=1.3,
                        color=color.rgba(1, 1, 1, 0.9), z=-0.01)
        self.update(0)

    @property
    def done(self):
        return self.t >= self.dur

    def update(self, dt):
        self.t += dt
        t, d = self.t, self.dur
        k_in = min(1.0, t / 0.16)
        k_out = max(0.0, (t - (d - 0.2)) / 0.2)
        ease = 1 - (1 - k_in) ** 3
        self.band.scale_y = ease * (1 - k_out)
        self.dim.color = color.rgba(0, 0, 0, 0.45 * ease * (1 - k_out))
        if self.pic:
            self.pic.x = -1.6 + 1.05 * ease + 0.08 * min(1, t / d) + 1.2 * k_out ** 2
        self.title.x = 0.95 - 0.63 * ease - 0.04 * min(1, t / d) - 1.4 * k_out ** 2
        self.title_sh.x = self.title.x + 0.006
        self.sub.x = self.title.x
        for ln, sp in self.lines:
            ln.x -= sp * dt
            if ln.x < -1.8:
                ln.x = 1.8

    def destroy(self):
        destroy(self.root)


# ====================================================================== 전투
class Battle3D:
    def __init__(self, game, enemy_ids, boss=False, on_end=None):
        self.game = game
        self.core = BattleCore(game.state, enemy_ids, boss)
        self.on_end = on_end
        self.t = 0.0
        self.wait = 0.0
        self.tweens = []
        self.floats = []
        self.fx = FX(game_tex(game, "textures3d/fx_glow.png"))
        self.ring_tex = game_tex(game, "textures3d/fx_ring.png")
        self.ui_state = "intro"          # intro / idle / command / sub / target / result
        self.banner_t = 0.0
        self.menu_i = 0
        self.sub = None
        self.sub_i = 0
        self.target = None
        self.ended = False
        # 연출 상태
        self.anims = []            # 동작 (웅크림·돌진·내리치기·피격 등) — 매 프레임 Motion 채널에 합산
        self.ghosts = []           # 잔상
        self.circles = []          # 바닥 마법진
        self.freeze = 0.0          # 히트스톱/컷인 동안 전투 시간 정지 (초)
        self.slow = 0.0            # 슬로 모션 남은 시간
        self.shake = 0.0           # 카메라 흔들림 세기
        self.focus = None          # (위치, 남은 시간) — 카메라가 다가가 비춤
        self.tier = 0              # 진행 중인 스킬 단계 (0 = 일반 공격)
        self.crit_hit = False      # 다음 피격을 치명타로 크게
        self.cutin = None
        self.tint_goal = 0.0
        self.circle_tex = game_tex(game, "textures3d/fx_circle.png")
        cx, cz = game.battle_spot()        # 카메라 앞을 가리는 나무가 없는 가까운 자리
        self.center = Vec3(cx, game.world.h(cx, cz), cz)
        r = math.radians(game.yaw)
        self.R = Vec3(math.cos(r), 0, -math.sin(r))      # 화면 오른쪽
        self.F = Vec3(math.sin(r), 0, math.cos(r))       # 화면 안쪽
        # 파티: 필드의 빌보드를 그대로 전투 위치로 (앞쪽 오른편)
        self.party_views = [game.player] + game.followers
        for i, f in enumerate(self.core.party):
            v = self.party_views[i]
            home = self.center + self.R * (1.3 + i * 1.0) + self.F * (0.1 + i * 1.0)   # 오른쪽 대각선 대열
            f.view = v
            v.home = Vec3(home.x, 0, home.z)
            v.x, v.z = home.x, home.z
        # 적: 뒤쪽 왼편
        slots = [(-1.7, 2.2), (-0.5, 3.4), (-2.9, 1.0)] if not boss else [(-1.6, 3.0)]
        for i, f in enumerate(self.core.enemies):
            rx, fz = slots[i % len(slots)]
            pos = self.center + self.R * rx + self.F * fz
            f.view = EnemyView(game, f, pos)
        for f in self.core.party:
            self.face(f, self.core.enemies[0])
        for n in game.npcs:
            n.body.enabled = n.shadow.enabled = False
        game.bubble.enabled = False
        self.build_ui()
        names = ", ".join(e.name for e in self.core.enemies)
        self.say(f"{names} 이(가) 나타났다!", 1.6)
        game.sfx("encounter")
        game.set_bgm("tense" if boss else "battle", fade=0.3)
        self.flash_ui(color.white, 0.5)

    # ------------------------------------------------------------ 카메라
    def camera_goal(self):
        """전투 구도: 양 진영 사이를 조금 더 멀리, 낮은 각도로"""
        # 하단 상태창에 가리지 않도록 초점을 카메라 쪽으로 당겨 전투가 화면 위쪽에 오게 한다
        mid = self.center + self.F * 0.2
        if self.core.boss:                 # 큰 보스는 머리까지 들어오도록 조금 멀리·높게
            goal, pitch, dist = mid + self.F * 0.6 + Vec3(0, 1.5, 0), 36.0, 25.0
        else:
            goal, pitch, dist = mid + self.F * 0.7 + Vec3(0, 0.9, 0), 40.0, 20.5
        if self.focus:                     # 스킬 시전자·치명타 대상에게 다가감
            goal = lerp(goal, self.focus[0] + Vec3(0, 0.8, 0), 0.55)
            dist *= 0.72
            pitch -= 6
        return goal, pitch, dist

    def shake_offset(self):
        if self.shake <= 0.001:
            return Vec3(0, 0, 0)
        a = self.shake
        return Vec3(random.uniform(-a, a), random.uniform(-a, a) * 0.6, random.uniform(-a, a))

    # ------------------------------------------------------------ UI
    def build_ui(self):
        self.ui = Entity(parent=camera.ui)
        # 파티 상태창 (오른쪽 아래)
        self.party_panel = Panel(0.92, 0.25, 0.39, -0.355, parent=self.ui)
        label(self.party_panel, "HP", -0.2, 0.105, 0.7, GOLD)
        label(self.party_panel, "MP", 0.04, 0.105, 0.7, GOLD)
        label(self.party_panel, "ATB", 0.22, 0.105, 0.7, GOLD)
        self.rows = []
        for i, f in enumerate(self.core.party):
            y = 0.06 - i * 0.068
            row = {"name": label(self.party_panel, f.name.split()[0], -0.43, y, 1.0),
                   "lv": label(self.party_panel, "", -0.29, y, 0.75, color.light_gray),
                   "hp": Bar(self.party_panel, -0.2, y, 0.2, 0.022, color.rgba32(214, 70, 60)),
                   "hpt": label(self.party_panel, "", -0.1, y - 0.026, 0.62, color.white, (0, 0)),
                   "mp": Bar(self.party_panel, 0.04, y, 0.14, 0.022, color.rgba32(70, 190, 230)),
                   "mpt": label(self.party_panel, "", 0.11, y - 0.026, 0.62, color.white, (0, 0)),
                   "atb": Bar(self.party_panel, 0.22, y, 0.2, 0.022, color.rgba32(232, 190, 90)),
                   "st": label(self.party_panel, "", -0.43, y - 0.028, 0.6, color.rgba32(95, 227, 224))}
            if f.ref.id == "luke":
                row["steam"] = Bar(self.party_panel, 0.22, y - 0.022, 0.2, 0.01, color.rgba32(255, 150, 80))
            self.rows.append(row)
        # 적 목록 (왼쪽 위)
        n = len(self.core.enemies)
        self.enemy_panel = Panel(0.46, 0.04 + 0.045 * n, -0.62, 0.43 - 0.0225 * n, parent=self.ui)
        self.erows = []
        for i, e in enumerate(self.core.enemies):
            y = 0.0225 * (n - 1) - i * 0.045
            self.erows.append((label(self.enemy_panel, e.name, -0.21, y, 0.85),
                               Bar(self.enemy_panel, 0.03, y, 0.17, 0.018, color.rgba32(214, 70, 60))))
        # 배너 (위 가운데)
        self.banner = Panel(0.5, 0.065, 0.0, 0.43, parent=self.ui)
        self.banner_text = label(self.banner, "", 0, 0, 1.25, color.white, (0, 0))
        self.banner.enabled = False
        # 명령 창 (왼쪽 아래)
        self.cmd_panel = Panel(0.26, 0.3, -0.73, -0.33, fill=color.rgba32(238, 224, 190, 235), border=color.rgba32(150, 104, 50),
                               parent=self.ui)
        self.cmd_items = [label(self.cmd_panel, t, -0.07, 0.11 - i * 0.055, 1.05, INK) for i, (t, _) in
                          enumerate(self.core.commands())]
        self.cmd_cursor = label(self.cmd_panel, "▶", -0.11, 0.11, 1.0, color.rgba32(176, 96, 58))
        self.cmd_panel.enabled = False
        self.sub_panel = Panel(0.36, 0.3, -0.41, -0.33, fill=color.rgba32(238, 224, 190, 235), border=color.rgba32(150, 104, 50),
                               parent=self.ui)
        self.sub_items = [label(self.sub_panel, "", -0.15, 0.135 - i * 0.051, 0.92, INK) for i in range(6)]
        self.sub_extra = [label(self.sub_panel, "", 0.16, 0.135 - i * 0.051, 0.78, INK, (0.5, 0)) for i in range(6)]
        self.sub_cursor = label(self.sub_panel, "▶", -0.17, 0.135, 0.9, color.rgba32(176, 96, 58))
        self.desc = Panel(0.9, 0.055, -0.2, -0.15, parent=self.ui)
        self.desc_text = label(self.desc, "", -0.43, 0, 0.85)
        self.sub_panel.enabled = self.desc.enabled = False
        self.arrow = Text(parent=camera.ui, text="▼", origin=(0, 0), scale=2.2, color=GOLD, enabled=False)
        self.flash_q = Entity(parent=camera.ui, model="quad", scale=(3, 2), color=color.rgba(1, 1, 1, 0), z=-0.5)
        # 궁극기 때 화면을 어둡게 (UI 보다 뒤, 월드보다 앞)
        self.tint = Entity(parent=camera.ui, model="quad", scale=(4, 2), color=color.rgba(0.04, 0.02, 0.1, 0), z=0.5)
        self.result_ui = None

    def refresh_hud(self):
        maxatb = self.core.B["atb"]["max"]
        for f, row in zip(self.core.party, self.rows):
            active = f is self.core.actor and self.ui_state in ("command", "sub", "target")
            row["name"].color = GOLD if active else (color.white if f.alive else color.gray)
            row["lv"].text = f"Lv{f.ref.level}"
            row["hp"].set(f.hp / f.max_hp)
            row["hpt"].text = f"{f.hp}/{f.max_hp}"
            row["mp"].set(f.mp / max(1, f.max_mp))
            row["mpt"].text = f"{f.mp}/{f.max_mp}"
            row["atb"].set(f.atb / maxatb)
            st = " ".join(STATUS_NAMES.get(k, k) for k in f.status)
            if "steam" in row:
                row["steam"].set(f.ref.steam / self.core.B["steam_pressure"]["max"])
                if f.boost:
                    st = (st + " 증기압MAX").strip()
            row["st"].text = st
        for e, (lab, bar) in zip(self.core.enemies, self.erows):
            bar.set(e.hp / e.max_hp)
            lab.color = color.white if e.alive else color.gray

    def say(self, text, dur=1.2):
        self.banner_text.text = text
        self.banner.enabled = True
        self.banner_t = dur

    def flash_ui(self, col, strength=0.6):
        self.flash_q.color = color.rgba(col.r, col.g, col.b, strength)

    def float_text(self, f, text, col, size=30, rise=False):
        world = self.head(f)
        holder = Entity(position=world)
        sp = holder.screen_position
        destroy(holder)
        # 상태·태그 글자(rise)는 대미지 숫자보다 위에서 시작해 겹치지 않게
        sp = sp + Vec3(random.uniform(-0.02, 0.02), 0.075 if rise else 0.02, 0)
        shadow = Text(parent=camera.ui, text=text, origin=(0, 0), position=sp + Vec3(0.003, -0.003, 0), scale=size / 22,
                      color=color.rgba(0, 0, 0, 0.8), z=-0.3)
        t = Text(parent=camera.ui, text=text, origin=(0, 0), position=sp, scale=size / 22, color=rgb(col), z=-0.31)
        self.floats.append({"t": t, "s": shadow, "life": 1.0, "y0": sp.y, "rise": rise})

    # ------------------------------------------------------------ 위치/연출
    def view_pos(self, f):
        v = f.view
        if f.party:
            return Vec3(v.x, self.game.world.h(v.x, v.z), v.z)
        return Vec3(v.pos)

    def head(self, f):
        return self.view_pos(f) + Vec3(0, (f.view.h if f.party else f.view.h) * (0.6 if f.party else 0.55), 0)

    def face(self, f, other):
        if f.party:
            d = self.view_pos(other) - self.view_pos(f)
            f.view.face_vector(d.x, d.z, self.game.yaw)

    def tween(self, f, goal, dur, delay=0.0, ghost=False):
        start = self.view_pos(f)
        self.tweens.append({"f": f, "a": Vec3(start.x, 0, start.z), "b": Vec3(goal.x, 0, goal.z), "t": -delay,
                            "d": dur, "ghost": ghost, "gt": 0.0})
        self.wait = max(self.wait, dur + delay)

    # ------------------------------------------------------------ 동작(모션)
    def anim(self, f, kind, dur, **kw):
        self.anims.append({"f": f, "k": kind, "t": 0.0, "d": dur, **kw})

    def style(self, f):
        """공격 방식: 근접(루크·적) / 원거리(제드) / 마법(아이리스)"""
        if not f.party:
            return "melee"
        return {"zed": "ranged", "iris": "magic"}.get(f.ref.id, "melee")

    def dir_to(self, a, b):
        d = self.view_pos(b) - self.view_pos(a)
        d.y = 0
        return d.normalized() if d.length() > 1e-4 else self.R

    def _apply_anims(self, dt):
        for f in self.core.party + self.core.enemies:
            f.view.mo.reset()
        keep = []
        for a in self.anims:
            a["t"] += dt
            k = min(1.0, a["t"] / a["d"])
            mo = a["f"].view.mo
            kind = a["k"]
            sw = math.sin(k * math.pi)
            if kind == "windup":            # 뒤로 젖히며 웅크림 (힘 모으기)
                mo.lean -= 0.22 * sw
                mo.sy *= 1 - 0.12 * sw
                mo.sx *= 1 + 0.07 * sw
            elif kind == "dash":            # 앞으로 숙이고 달림
                mo.lean += 0.3 * min(1.0, k * 5)
                mo.walk = 1.0
            elif kind == "strike":          # 내리치기: 확 숙였다가 복귀 + 늘어남
                c = k / 0.18 if k < 0.18 else (1 - k) / 0.82
                mo.lean += 0.5 * c * a.get("amp", 1.0)
                mo.sx *= 1 + 0.14 * c
                mo.sy *= 1 - 0.08 * c
            elif kind == "hop":             # 점프 (포물선)
                mo.hop += a["h"] * 4 * k * (1 - k)
                mo.sy *= 1 + 0.08 * sw
            elif kind == "recoil":          # 사격 반동
                c = (1 - k) ** 2
                mo.lean -= 0.32 * c
                mo.off -= a["dir"] * 0.3 * c
            elif kind == "cast":            # 마법: 떠오르며 몸을 펴고 떨림
                rise = min(1.0, k * 5) * min(1.0, (1 - k) * 6)
                mo.hop += 0.32 * rise * a.get("amp", 1.0)
                mo.sy *= 1 + 0.05 * rise
                mo.lean -= 0.08 * rise
                mo.off += self.R * math.sin(a["t"] * 55) * 0.015 * rise
            elif kind == "knock":           # 피격: 밀려남 + 흔들림 + 번쩍
                c = 1 - k
                amp = a["amp"]
                mo.off += a["dir"] * amp * math.sin(min(1.0, k * 2.5) * math.pi * 0.5) * c
                mo.off += self.R * math.sin(a["t"] * 75) * 0.07 * c * min(1.5, amp / 0.3)
                mo.lean -= 0.3 * c * min(1.5, amp / 0.3)
                mo.flash = max(mo.flash, 1 - k * 3.5)
            elif kind == "victory":         # 승리: 통통 뛰기
                mo.hop += 0.45 * abs(math.sin(k * math.pi * 3))
                mo.sy *= 1 + 0.06 * abs(math.sin(k * math.pi * 3))
            if k < 1.0:
                keep.append(a)
        self.anims = keep
        # 지속 자세: 쓰러짐 / 빈사(무릎) / 방어
        for f in self.core.party:
            mo = f.view.mo
            if not f.alive:
                mo.sy *= 0.42
                mo.sx *= 1.3
                mo.lean += 0.25
            elif f.hp < f.max_hp * 0.25:
                mo.sy *= 0.9
                mo.lean += 0.12
            if f.alive and "guard" in f.status:
                mo.sy *= 0.93
                mo.sx *= 1.04
                mo.lean -= 0.06

    def ghost(self, f):
        """잔상: 지금 모습 그대로 반투명 사본을 남긴다"""
        b = f.view.body
        g = Entity(model=b.model, texture=b.texture, position=b.world_position, scale=b.world_scale, billboard=True,
                   double_sided=True, shader=unlit_shader, color=color.rgba(0.6, 0.85, 1.0, 0.5))
        g.setTransparency(TransparencyAttrib.MAlpha)
        g.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
        g.setDepthWrite(False)
        g.hide(0b0001)
        self.ghosts.append([g, 0.3])

    def magic_circle(self, f, col, size, life):
        p = self.view_pos(f) + Vec3(0, 0.08, 0)
        e = Entity(model="quad", texture=self.circle_tex, position=p, rotation_x=90, scale=0.1, color=col,
                   shader=unlit_shader)
        e.setTransparency(TransparencyAttrib.MAlpha)
        e.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
        e.setDepthWrite(False)
        e.setBin("fixed", 40)
        e.hide(0b0001)
        self.circles.append({"e": e, "t": 0.0, "life": life, "size": size, "col": col})

    def converge(self, f, col, n, radius, life):
        """기 모으기: 사방에서 시전자 가슴으로 빛 입자가 빨려 들어감"""
        c = self.head(f) - Vec3(0, 0.35, 0)
        for _ in range(n):
            a, el = random.uniform(0, math.tau), random.uniform(-0.3, 1.0)
            off = Vec3(math.cos(a) * math.cos(el), math.sin(el) * 0.7 + 0.2, math.sin(a) * math.cos(el)) * radius
            lf = random.uniform(life * 0.6, life)
            self.fx.particle(c + off, -off / lf, lf, random.uniform(0.1, 0.22), col)

    def tier_color(self, f):
        if not f.party:
            return rgb((255, 110, 80))
        return rgb({"luke": (255, 170, 90), "iris": (95, 227, 224), "zed": (255, 220, 140)}.get(f.ref.id, (255, 255, 255)))

    def set_pos(self, f, p):
        if f.party:
            f.view.x, f.view.z = p.x, p.z
            f.view.moving = True
        else:
            f.view.pos = Vec3(p.x, self.game.world.h(p.x, p.z), p.z)

    def home_of(self, f):
        return f.view.home

    def play(self, ev):
        k = ev["t"]
        core = self.core
        if k == "say":
            self.say(ev["text"])
        elif k == "wait":
            self.wait = max(self.wait, ev["s"])
        elif k == "sfx":
            self.game.sfx(ev["id"])
        elif k == "skill":
            self.start_skill(ev["who"], ev["tier"], ev["name"])
        elif k == "crit":
            self.crit_hit = True
            a = ev["who"]
            if ev.get("cutin") and a.party:
                self.cutin = CutIn(a, "CRITICAL!", a.name, (255, 120, 80), 0.95)
                self.game.sfx("slash", 0.8)
                self.flash_ui(color.white, 0.5)
        elif k == "lunge":
            a, t = ev["who"], ev["to"]
            pa, pt = self.view_pos(a), self.view_pos(t)
            d = Vec3(pt.x - pa.x, 0, pt.z - pa.z)
            dist = d.length()
            goal = pa + d.normalized() * (ev["dist"] if ev["dist"] else max(0.0, dist - 1.3))
            self.face(a, t)
            self._attacker = a
            st = self.style(a)
            big = self.tier >= 3 or self.crit_hit
            if st == "magic":                      # 마법: 제자리에서 떠올라 시전
                self.anim(a, "cast", 0.55 + 0.1 * self.tier, amp=1.0 + 0.15 * self.tier)
                self.tween(a, pa + d.normalized() * 0.4, 0.25)
            elif st == "ranged":                   # 원거리: 한 발 내디뎌 겨눔
                self.anim(a, "windup", 0.22)
                self.tween(a, pa + d.normalized() * 0.6, 0.2, delay=0.1)
            else:                                  # 근접: 웅크렸다가 돌진 (상위 스킬·치명타는 잔상 + 도약)
                self.anim(a, "windup", 0.16)
                self.anim(a, "dash", 0.16 + 0.24)
                if self.tier >= 5 and a.party:
                    self.anim(a, "hop", 0.55, h=1.5)
                self.tween(a, goal, 0.24, delay=0.14, ghost=big)
        elif k == "back":
            f = ev["who"]
            if self.style(f) == "melee":
                self.anim(f, "hop", 0.3, h=0.35)   # 뒤로 폴짝
            self.tween(f, self.home_of(f), 0.26)
            if f.party:
                self.tier = 0
                self.focus = None
                self.tint_goal = 0.0
        elif k == "fx":
            a, t = ev["src"], ev["dst"]
            tier = ev.get("tier", 0)
            if a is not t and a.alive:            # 공격하는 쪽 동작 (한 번만)
                if not getattr(self, "_struck", None) is a:
                    self._struck = a
                    st = self.style(a)
                    if st == "ranged":
                        self.anim(a, "recoil", 0.3, dir=self.dir_to(a, t))
                    elif st == "magic":
                        self.anim(a, "strike", 0.35, amp=0.6)
                    else:
                        self.anim(a, "strike", 0.34, amp=1.0 + 0.1 * tier)
            self.spawn_fx(ev["fx"], a, t, ev.get("big"), tier)
        elif k == "float":
            self.float_text(ev["who"], ev["text"], ev["color"], ev.get("size", 30), ev.get("rise", False))
        elif k == "hit":
            f = ev["who"]
            self._struck = None
            src = getattr(self, "_attacker", None)
            src = src if src is not None and src is not f else None
            d = self.dir_to(src, f) if src else (self.R if not f.party else -self.R)
            heavy = self.crit_hit
            amp = 0.75 if heavy else (0.32 + 0.06 * self.tier)
            self.anim(f, "knock", 0.5 if heavy else 0.36, dir=d, amp=amp)
            self.shake = max(self.shake, 0.32 if heavy else 0.06 + 0.035 * self.tier + (0.08 if f.party else 0))
            if heavy:
                self.freeze = max(self.freeze, 0.13)      # 히트스톱
                self.crit_hit = False
                self.fx.burst(self.head(f) - Vec3(0, 0.2, 0), 40, rgb((255, 230, 180)), (3, 8), size=(0.08, 0.2))
                self.fx.ring(self.view_pos(f), rgb((255, 150, 90)), 0.3, 3.5, 0.45, tex=self.ring_tex)
            if f.party:
                f.view.hurt = 0.3
            else:
                f.view.flash = 0.25
        elif k == "die":
            f = ev["who"]
            if f.party:
                f.view.body.color = color.rgba(0.45, 0.45, 0.55, 0.8)
            else:
                f.view.dead_t = 0.0
                self.fx.burst(f.view.head(), 40, rgb((255, 170, 100)), up=1.0)
                self.fx.burst(f.view.head() - Vec3(0, 0.4, 0), 30, rgb((200, 200, 220)), (0.5, 2), (0.6, 1.0),
                              (0.2, 0.4), up=1.5)
                self.shake = max(self.shake, 0.2 if f.view.boss else 0.08)
        elif k == "flash":
            self.flash_ui(rgb(ev["color"]), 0.45)
        return core

    def start_skill(self, a, tier, name):
        """스킬 발동 연출: 단계가 높을수록 길고 크게"""
        self.tier = tier
        col = self.tier_color(a)
        if tier >= 5:                               # 궁극기: 컷인 + 화면 어둡게 + 거대한 마법진 + 기 모으기
            self.cutin = CutIn(a, name, f"{a.name}  —  {'궁극기' if tier >= 6 else '오의'}", (255, 214, 120), 1.25)
            self.tint_goal = 0.55
            self.magic_circle(a, col, 5.5, 1.6)
            self.converge(a, col, 70, 3.2, 0.9)
            self.anim(a, "cast", 1.0, amp=1.4)
            self.focus = (self.view_pos(a), 1.1)
            self.wait = max(self.wait, 1.0)
            self.game.sfx("magic", 0.9)
        elif tier >= 3:                             # 상위 스킬: 마법진 + 기 모으기 + 카메라 접근
            self.magic_circle(a, col, 3.4, 1.0)
            self.converge(a, col, 36, 2.2, 0.6)
            self.anim(a, "cast", 0.65, amp=1.0)
            self.focus = (self.view_pos(a), 0.7)
            self.wait = max(self.wait, 0.6)
            self.game.sfx("buff", 0.7)
        else:                                       # 기본 스킬: 작은 빛 고리
            self.fx.ring(self.view_pos(a), col, 0.2, 1.6, 0.4, tex=self.ring_tex)
            self.converge(a, col, 14, 1.4, 0.35)
            self.wait = max(self.wait, 0.3)
        self.flash_ui(col, 0.12 + 0.05 * tier)

    def spawn_fx(self, name, src, dst, big=False, tier=0):
        self._spawn_base(name, src, dst, big, tier)
        F = self.fx
        p = self.head(dst) - Vec3(0, 0.25, 0)
        ground = self.view_pos(dst)
        col = self.tier_color(src)
        reps = 1 + (tier >= 3) + (tier >= 5)        # 상위 스킬은 같은 효과를 겹쳐 더 크고 화려하게
        for r in range(1, reps):
            self._spawn_base(name, src, dst, True, tier, jitter=0.35 * r)
        if tier >= 3:                               # 충격파 + 불꽃 + 흔들림
            F.ring(ground, col, 0.3, 3.2 + tier * 0.5, 0.55, tex=self.ring_tex)
            F.ring(ground, rgb((255, 255, 255)), 0.2, 2.0 + tier * 0.3, 0.35, tex=self.ring_tex)
            F.burst(p, 20 + tier * 8, col, (2, 6 + tier), size=(0.1, 0.26), up=1.5)
            self.shake = max(self.shake, 0.12 + 0.03 * tier)
        if tier >= 5:                               # 궁극기: 빛기둥 + 섬광 + 슬로 모션 + 거대 충격파
            F.pillar(ground, col, 7.0, 46)
            F.pillar(ground, rgb((255, 255, 255)), 5.0, 20)
            F.ring(ground, col, 0.5, 8.0, 0.9, tex=self.ring_tex)
            F.burst(p, 80, rgb((255, 240, 210)), (3, 10), (0.5, 1.1), (0.1, 0.3), up=2.0, grav=3)
            self.flash_ui(color.white, 0.5)
            self.slow = max(self.slow, 0.55)
            self.shake = max(self.shake, 0.42)
        if big and tier == 0:                       # 치명타 일반 공격
            F.burst(p, 26, rgb((255, 200, 150)), (3, 8), size=(0.08, 0.2))

    def _spawn_base(self, name, src, dst, big=False, tier=0, jitter=0.0):
        F = self.fx
        p = self.head(dst) - Vec3(0, 0.25, 0) + Vec3(random.uniform(-jitter, jitter), random.uniform(0, jitter),
                                                    random.uniform(-jitter, jitter))
        ground = self.view_pos(dst)
        sp = self.head(src) - Vec3(0, 0.3, 0)
        s = (1.0 + 0.3 * max(0, tier - 1)) if tier else (1.5 if big else 1.0)
        C = lambda *c: rgb(c)  # noqa: E731
        if name in ("slash", "claw"):
            F.slash(p, C(240, 240, 255) if name == "slash" else C(255, 120, 100), 1 if name == "slash" else 3, self.R)
            F.burst(p, 14, C(255, 240, 220), size=(0.08, 0.18))
        elif name == "piston":
            F.ring(ground, C(255, 210, 130), 0.2, 2.8 * s, 0.5, tex=self.ring_tex)
            F.burst(p, 34, C(255, 200, 120), (2, 6), grav=9, up=1.5)
            self.flash_ui(rgb((255, 200, 120)), 0.3)
        elif name == "steam":
            F.burst(p, 40, C(170, 170, 180), (0.8, 2.5), (0.6, 1.1), (0.3, 0.6), up=1.0)
            F.ring(ground, C(255, 160, 100), 0.2, 3.0, 0.6, tex=self.ring_tex)
        elif name == "wrench":
            F.slash(p, C(240, 200, 120), 1, self.R)
            F.burst(p, 20, C(95, 227, 224), size=(0.08, 0.2))
        elif name in ("charge", "ultimate"):
            self.flash_ui(rgb((255, 170, 90)), 0.5)
            F.ring(ground, C(255, 170, 90), 0.4, 5.0, 0.7, tex=self.ring_tex)
            F.burst(p, 70, C(255, 180, 100), (2, 7), grav=4)
            F.slash(p, C(255, 230, 170), 3, self.R)
        elif name == "wave_small":
            F.ring(p, C(95, 227, 224), 0.2, 1.4, 0.4, ground=False, tex=self.ring_tex)
            F.burst(p, 10, C(95, 227, 224), size=(0.08, 0.18))
        elif name == "wave":
            for i in range(3):
                F.ring(p, C(95, 227, 224), 0.2 + i * 0.2, 2.2, 0.5 + i * 0.12, ground=False, tex=self.ring_tex)
            F.beam(sp, p, C(95, 227, 224), 20, 0.24)
            F.burst(p, 24, C(140, 240, 240), size=(0.08, 0.22))
        elif name == "shot":
            F.beam(sp, p, C(255, 220, 150), 22, 0.16)
            F.burst(p, 18, C(255, 220, 150), (2, 5), size=(0.06, 0.16))
            self.flash_ui(rgb((255, 230, 180)), 0.2)
        elif name == "pellets":
            for _ in range(5):
                q = p + Vec3(random.uniform(-0.8, 0.8), random.uniform(-0.5, 0.5), random.uniform(-0.8, 0.8))
                F.beam(sp, q, C(255, 200, 120), 12, 0.1)
                F.burst(q, 6, C(255, 210, 140), size=(0.06, 0.12))
        elif name == "hawk":
            F.beam(sp + Vec3(0, 0.6, 0), p, C(226, 184, 102), 20, 0.28)
            F.slash(p, C(240, 200, 120), 2, self.R)
        elif name == "rust":
            F.burst(p, 34, C(210, 110, 50), (1, 4), (0.4, 0.8), (0.12, 0.28), up=2.5, grav=9)
        elif name == "heal":
            F.pillar(ground, C(120, 255, 200))
            F.ring(ground, C(120, 255, 200), 0.2, 1.6, 0.6, tex=self.ring_tex)
        elif name == "stop":
            F.clock(p, C(95, 227, 224))
            F.ring(ground, C(95, 227, 224), 0.2, 2.0, 0.8, tex=self.ring_tex)
        elif name in ("buff", "levelup"):
            col = C(255, 230, 140) if name == "levelup" else C(226, 184, 102)
            F.pillar(ground, col, 4.0 if name == "levelup" else 3.0)
            F.ring(ground, col, 1.6, 0.2, 0.6, tex=self.ring_tex)
        elif name == "rage":
            F.ring(ground, C(255, 90, 60), 0.3, 4.0, 0.7, tex=self.ring_tex)
            F.burst(p, 40, C(255, 90, 60), (2, 6))

    # ------------------------------------------------------------ 입력
    def input(self, key):
        core = self.core
        up = key in ("up arrow", "w", "up arrow hold")
        down = key in ("down arrow", "s")
        left, right = key in ("left arrow", "a"), key in ("right arrow", "d")
        ok = key in ("z", "enter", "space")
        cancel = key in ("x", "escape", "backspace")
        g = self.game
        if self.ui_state == "result":
            if ok and self.t - self.result_t > 0.6:
                self.finish()
            return
        if self.ui_state == "command":
            if up or down:
                self.menu_i = (self.menu_i + (1 if down else -1)) % 5
                g.sfx("cursor")
            elif ok:
                label_, enabled = core.commands()[self.menu_i]
                if not enabled:
                    g.sfx("cancel")
                    return
                g.sfx("confirm")
                if label_ == "공격":
                    self.choose_target("enemy", ("attack", None))
                elif label_ == "스킬":
                    self.open_sub("skill")
                elif label_ == "방어":
                    self.commit(("guard", None), [core.actor])
                elif label_ == "아이템":
                    self.open_sub("item")
                elif label_ == "도주":
                    self.commit(("escape", None), [core.actor])
        elif self.ui_state == "sub":
            n = len(self.sub)
            if up or down:
                self.sub_i = (self.sub_i + (1 if down else -1)) % n
                g.sfx("cursor")
            elif cancel:
                g.sfx("cancel")
                self.ui_state = "command"
            elif ok:
                kind, data, enabled = self.sub[self.sub_i]
                if not enabled:
                    g.sfx("cancel")
                    return
                g.sfx("confirm")
                if kind == "skill":
                    self.choose_target(data["target"], ("skill", data))
                else:
                    self.choose_target(core.B["items"][data]["target"], ("item", data))
        elif self.ui_state == "target":
            mode, cands, idx, payload, back = self.target
            if mode == "single" and (left or right or up or down):
                idx = (idx + (1 if (right or down) else -1)) % len(cands)
                self.target = (mode, cands, idx, payload, back)
                g.sfx("cursor")
            elif cancel:
                g.sfx("cancel")
                self.ui_state = back
            elif ok:
                g.sfx("confirm")
                self.commit(payload, [cands[idx]] if mode == "single" else cands)

    def open_sub(self, kind):
        core = self.core
        if kind == "skill":
            self.sub = [("skill", s, ok) for s, ok, extra in core.skills(core.actor)]
            extras = [extra for _, _, extra in core.skills(core.actor)]
            names = [s["name"] for s, _, _ in core.skills(core.actor)]
        else:
            items = core.items()
            self.sub = [("item", k, True) for k, _, _ in items]
            extras = [f"x{n}" for _, _, n in items]
            names = [it["name"] for _, it, _ in items]
        for i in range(6):
            self.sub_items[i].text = names[i] if i < len(names) else ""
            self.sub_extra[i].text = extras[i] if i < len(extras) else ""
            if i < len(self.sub):
                self.sub_items[i].color = INK if self.sub[i][2] else color.rgba32(150, 130, 110)
        self.sub_i = 0
        self.ui_state = "sub"

    def choose_target(self, tkind, payload):
        mode, cands, idx = self.core.targets_for(tkind)
        if mode == "self":
            self.commit(payload, cands)
            return
        self.target = (mode, cands, idx, payload, self.ui_state)
        self.ui_state = "target"

    def commit(self, payload, targets):
        self.core.commit(payload, targets)
        self.ui_state = "idle"

    # ------------------------------------------------------------ 갱신
    def update(self, dt):
        rdt = dt                                   # 실제 시간 (컷인·섬광·카메라 흔들림)
        if self.cutin:
            self.cutin.update(rdt)
            if self.cutin.done:
                self.cutin.destroy()
                self.cutin = None
        if self.cutin or self.freeze > 0:          # 컷인·히트스톱 동안 전투 정지
            self.freeze = max(0.0, self.freeze - rdt)
            dt = 0.0
        elif self.slow > 0:
            self.slow -= rdt
            dt *= 0.35
        self.shake = max(0.0, self.shake - rdt * 1.4)
        if self.focus:
            self.focus = (self.focus[0], self.focus[1] - dt)
            if self.focus[1] <= 0:
                self.focus = None
        a = self.tint.color.a
        self.tint.color = color.rgba(0.04, 0.02, 0.1, a + (self.tint_goal - a) * min(1.0, rdt * 5))
        self.t += dt
        core = self.core
        self.fx.update(dt)
        keep = []                                  # 잔상
        for g in self.ghosts:
            g[1] -= rdt
            if g[1] <= 0:
                destroy(g[0])
                continue
            g[0].color = color.rgba(0.6, 0.85, 1.0, 0.5 * g[1] / 0.3)
            keep.append(g)
        self.ghosts = keep
        keep = []                                  # 마법진: 커지며 돌다가 사라짐
        for c in self.circles:
            c["t"] += dt
            k = c["t"] / c["life"]
            if k >= 1:
                destroy(c["e"])
                continue
            grow = 1 - (1 - min(1.0, k * 3)) ** 3
            c["e"].scale = c["size"] * grow
            c["e"].rotation_y += dt * 90
            col = c["col"]
            c["e"].color = color.rgba(col.r, col.g, col.b, min(1.0, (1 - k) * 2.5))
            keep.append(c)
        self.circles = keep
        # 숫자 떠오르기
        keep = []
        for fl in self.floats:
            fl["life"] -= dt
            if fl["life"] <= 0:
                destroy(fl["t"])
                destroy(fl["s"])
                continue
            p = 1 - fl["life"]
            y = fl["y0"] + (p * 0.06 if fl["rise"] else abs(math.sin(min(p * 2.2, 1) * math.pi)) * 0.04 + p * 0.015)
            for e in (fl["t"], fl["s"]):
                e.y = y - (0.003 if e is fl["s"] else 0)
                e.alpha = min(1, fl["life"] * 3)
            keep.append(fl)
        self.floats = keep
        # 화면 섬광
        if self.flash_q.color.a > 0:
            c = self.flash_q.color
            self.flash_q.color = color.rgba(c.r, c.g, c.b, max(0, c.a - dt * 2.2))
        if self.banner_t > 0:
            self.banner_t -= dt
            self.banner.enabled = self.banner_t > 0
        # 이동 연출
        keep = []
        for tw in self.tweens:
            tw["t"] += dt
            if tw["t"] < 0:                       # 지연 (웅크리는 동안)
                keep.append(tw)
                continue
            if tw["ghost"]:
                tw["gt"] -= dt
                if tw["gt"] <= 0:
                    tw["gt"] = 0.035
                    self.ghost(tw["f"])
            k = min(1.0, tw["t"] / tw["d"])
            self.set_pos(tw["f"], lerp(tw["a"], tw["b"], 1 - (1 - k) ** 2))
            if k < 1:
                keep.append(tw)
            elif tw["f"].party:
                tw["f"].view.moving = False
        self.tweens = keep
        # 동작 채널 계산 → 빌보드 갱신
        self._apply_anims(dt)
        for f in core.party:
            v = f.view
            v.anim += dt * 11 if v.moving else 0
            hurt = getattr(v, "hurt", 0)
            if hurt > 0:
                v.hurt = hurt - dt
            v.sync(dt)
            if f.alive:
                v.body.color = color.rgba(1, 0.75, 0.75, 1) if getattr(v, "hurt", 0) > 0 else color.white
        for e in core.enemies:
            v = e.view
            v.t += dt
            v.alpha = min(1.0, v.alpha + dt * 2.5)
            v.flash = max(0.0, v.flash - dt)
            if v.dead_t >= 0:
                v.dead_t += dt
            v.sync()
        # 진행
        if self.ui_state == "intro":
            if self.t > 1.2:
                self.ui_state = "idle"
        elif self.ui_state == "idle":
            self.wait -= dt
            while self.wait <= 0 and not self.tweens and not self.cutin and self.freeze <= 0:
                ev = core.next_event()
                if ev is None:
                    break
                self.play(ev)
            if (self.wait <= 0 and not self.tweens and not core.seq and not core.pending and not self.cutin
                    and self.freeze <= 0):
                if core.phase == "running":
                    core.tick(dt)
                if core.phase == "command":
                    self.ui_state, self.menu_i = "command", 0
                    self.game.sfx("menu")
                    self.game.emit("command_open", actor=core.actor.id)
                elif core.phase in ("victory", "defeat", "escaped"):
                    self.show_result()
        self.update_ui()

    def update_ui(self):
        core = self.core
        self.refresh_hud()
        cmd = self.ui_state in ("command", "sub", "target") and core.actor is not None
        self.cmd_panel.enabled = cmd
        if cmd:
            for i, (t, en) in enumerate(core.commands()):
                self.cmd_items[i].color = INK if en else color.rgba32(150, 130, 110)
            self.cmd_cursor.y = 0.11 - self.menu_i * 0.055
        self.sub_panel.enabled = self.ui_state == "sub" or (self.ui_state == "target" and self.target[4] == "sub")
        self.desc.enabled = self.ui_state == "sub"
        if self.ui_state == "sub":
            self.sub_cursor.y = 0.135 - self.sub_i * 0.051
            kind, data, _ = self.sub[self.sub_i]
            self.desc_text.text = data["description"] if kind == "skill" else core.B["items"][data]["desc"]
        # 대상 화살표 (여러 대상이면 깜빡이며 순환)
        if self.ui_state == "target":
            mode, cands, idx, _, _ = self.target
            f = cands[idx] if mode == "single" else cands[int(self.t * 3) % len(cands)]
            holder = Entity(position=self.head(f) + Vec3(0, 0.9 + abs(math.sin(self.t * 6)) * 0.2, 0))
            self.arrow.position = holder.screen_position
            destroy(holder)
            self.arrow.enabled = True
        else:
            self.arrow.enabled = False
        # 현재 행동 중인 아군 표시
        for f, row in zip(core.party, self.rows):
            pass

    # ------------------------------------------------------------ 결과
    def show_result(self):
        core = self.core
        res = core.result
        self.ui_state = "result"
        self.result_t = self.t
        self.game.emit(res["kind"], **({k: v for k, v in res.items() if k != "kind"} if res["kind"] == "victory" else {}))
        if res["kind"] == "escaped" or res["kind"] == "escape":
            self.finish()
            return
        from src3d.game import FONT_TEXT, FONT_UI, font, tex
        from src.entities.party import exp_to_next
        r = Entity(parent=camera.ui, z=-0.4, y=0.06)
        self.party_panel.enabled = self.enemy_panel.enabled = False
        Entity(parent=r, model="quad", texture=tex("ui3d/dialog_panel.png"), scale=(1.0, 0.62 if res["kind"] == "victory" else 0.26))
        self.result_ui = r
        if res["kind"] == "defeat":
            self.game.stop_bgm()
            label(r, "전멸했다……", 0, 0.03, 2.2, color.rgba32(158, 43, 43), (0, 0), font(FONT_TEXT))
            label(r, "Z: 다시 일어선다", 0, -0.06, 0.95, INK, (0, 0), font(FONT_UI))
            return
        self.game.stop_bgm()
        self.game.sfx("victory")
        for f in core.party:
            if f.alive:
                self.anim(f, "victory", 1.6)
        label(r, "승리!", 0, 0.24, 2.4, INK, (0, 0), font(FONT_TEXT))
        label(r, f"EXP +{res['exp']}     GOLD +{res['gold']}", 0, 0.17, 1.1, INK, (0, 0), font(FONT_UI))
        for i, f in enumerate(core.party):
            ch = f.ref
            y = 0.08 - i * 0.095
            label(r, ch.name, -0.42, y, 1.05, INK, (-0.5, 0), font(FONT_UI))
            label(r, f"Lv {ch.level}", -0.12, y, 1.0, INK, (-0.5, 0), font(FONT_UI))
            Bar(r, 0.0, y, 0.2, 0.02, color.rgba32(232, 190, 90)).set(ch.exp / exp_to_next(ch.level))
            label(r, f"다음 Lv까지 {exp_to_next(ch.level) - ch.exp}", 0.0, y - 0.03, 0.7, INK, (-0.5, 0))
            if ch.id in res["ups"]:
                u = res["ups"][ch.id][-1]
                label(r, "LEVEL UP!", 0.24, y + 0.005, 1.15, color.rgba32(176, 50, 40), (-0.5, 0), font(FONT_UI))
                d = u["diffs"]
                label(r, f"HP+{d['hp']} 공+{d['atk']} 마+{d['mag']}", 0.24, y - 0.03, 0.7, INK, (-0.5, 0))
                learned = [n for up in res["ups"][ch.id] for n in up["learned"]]
                if learned:
                    label(r, "새 스킬: " + ", ".join(learned), -0.42, y - 0.03, 0.7, color.rgba32(42, 120, 140), (-0.5, 0))
                self.spawn_fx("levelup", f, f)
                self.game.sfx("levelup")
        label(r, "Z: 계속", 0, -0.24, 0.85, INK, (0, 0), font(FONT_UI))

    def finish(self):
        if self.ended:
            return
        self.ended = True
        core = self.core
        kind = core.result["kind"] if core.result else "escape"
        if kind != "defeat":
            core.write_back()
        for e in core.enemies:
            e.view.destroy()
        self.fx.clear()
        for fl in self.floats:
            destroy(fl["t"])
            destroy(fl["s"])
        destroy(self.ui)
        destroy(self.arrow)
        destroy(self.flash_q)
        if self.result_ui:
            destroy(self.result_ui)
        for g in self.ghosts:
            destroy(g[0])
        for c in self.circles:
            destroy(c["e"])
        if self.cutin:
            self.cutin.destroy()
        destroy(self.tint)
        for v in self.party_views:
            v.body.color = color.white
            v.moving = False
            v.mo.reset()
        if self.on_end:
            self.on_end(kind)
