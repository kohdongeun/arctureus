"""2.5D 쿼터뷰 3D 필드 (ursina).

- 풀 3D 지형(언덕·흙길·잔디) + 입체 나무·덤불·바위 + 풀포기, 실시간 그림자
- 캐릭터는 항상 카메라를 바라보는 빌보드 스프라이트 + 발밑 그림자, 동료 2명이 뒤따라 걷는다
- 쿼터뷰 추적 카메라 (Q/E 회전, 휠 확대/축소)
- 반투명 양피지 대화창 + 우측 하단 대형 스탠딩 일러스트
"""
from __future__ import annotations

import json
import math
import os
import random
import sys

from panda3d.core import Filename, TransparencyAttrib
from ursina import (Cylinder, Entity, Mesh, Text, Texture, Ursina, Vec3, application, camera, color, destroy,
                    held_keys, lerp, window)

from src3d import terrain
from src3d.shaders import LIGHT, lit_shader, terrain_shader, unlit_shader

ROOT = getattr(sys, "_MEIPASS", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
IMG = os.path.join(ROOT, "assets", "images")
FONTS = os.path.join(ROOT, "assets", "fonts")
FONT_TEXT = "NanumMyeongjo-Bold.ttf"   # ursina 는 폰트를 fonts_folder 안에서 파일 이름으로 찾는다
FONT_UI = "NanumGothic-Bold.ttf"
EMO_MAP = {"determined": "serious", "hurt": "sad", "tired": "sad", "shy": "smile", "smirk": "smile"}

_tex_cache = {}


def tex(rel, mipmap=True):
    if rel not in _tex_cache:
        t = Texture(rel if os.path.isabs(rel) else os.path.join(IMG, rel))
        t.filtering = "mipmap" if mipmap else "bilinear"
        _tex_cache[rel] = t
    return _tex_cache[rel]


def load_json(rel):
    with open(os.path.join(ROOT, "data", rel), encoding="utf-8") as f:
        return json.load(f)


def font(name):
    return name


def rgb(r, g, b, a=255):
    return color.rgba32(r, g, b, a)


# ====================================================================== 월드
class World:
    def __init__(self, map_id):
        self.m = terrain.load_map(map_id)
        self.half = self.m["size"] / 2
        self.sc = terrain.scatter(self.m)
        self.colliders = terrain.colliders(self.m, self.sc)
        self.rng = random.Random(self.m.get("seed", 1))
        self.build_terrain()
        self.build_trees()
        self.build_rocks()
        self.build_grass()

    def h(self, x, z):
        return float(terrain.height(self.m, x, z))

    def build_terrain(self, n=150):
        import numpy as np
        S = self.m["size"]
        xs = np.linspace(-S / 2, S / 2, n + 1)
        X, Z = np.meshgrid(xs, xs)
        Hm = terrain.height(self.m, X, Z)
        gz, gx = np.gradient(Hm, xs, xs)
        N = np.dstack([-gx, np.ones_like(Hm), -gz])
        N /= np.linalg.norm(N, axis=2, keepdims=True)
        verts = list(zip(X.ravel(), Hm.ravel(), Z.ravel()))
        uvs = list(zip((X.ravel() / S + 0.5), (Z.ravel() / S + 0.5)))
        norms = [tuple(v) for v in N.reshape(-1, 3)]
        tris = []
        w = n + 1
        for j in range(n):
            for i in range(n):
                a, b, c, d = j * w + i, j * w + i + 1, (j + 1) * w + i, (j + 1) * w + i + 1
                tris += [a, b, c, b, d, c]      # 위에서 볼 때 앞면이 되도록 감김 방향 지정
        mesh = Mesh(vertices=verts, triangles=tris, uvs=uvs, normals=norms, static=True)
        tiles = {k: f"textures3d/tile_{k}.jpg" for k in ("grass", "dirt", "stone")}
        splat = f"textures3d/terrain_{self.m['id']}_splat.png"
        if all(os.path.exists(os.path.join(IMG, v)) for v in list(tiles.values()) + [splat]):
            # 잔디·흙길·돌바닥 타일 텍스처를 월드 좌표로 반복 + 분포 맵으로 섞기 (가까이서도 선명)
            self.ground = Entity(model=mesh, texture=tex(splat), shader=terrain_shader)
            for k, v in tiles.items():
                self.ground.set_shader_input(f"{k}_tex", tex(v)._texture)
            self.ground.set_shader_input("tile", 4.5)
        else:
            self.ground = Entity(model=mesh, texture=tex(f"textures3d/terrain_{self.m['id']}.jpg"),
                                 shader=lit_shader)

    def build_trees(self):
        trunks = Entity()
        leaves = Entity(texture=tex("textures3d/leaves.png"), shader=lit_shader)
        for x, z, s, rot in self.sc["tree"]:
            y = self.h(x, z) - 0.3
            Entity(parent=trunks, model=Cylinder(7, radius=0.32 * s, height=3.4 * s, start=0), position=(x, y, z),
                   color=rgb(150, 110, 80))
            for k in range(3):            # 굵은 가지
                a = math.radians(rot + k * 120)
                Entity(parent=trunks, model=Cylinder(5, radius=0.12 * s, height=1.4 * s, start=0),
                       position=(x, y + 2.3 * s, z), rotation=(math.degrees(0.8) * math.sin(a), rot + k * 120, 40),
                       color=rgb(140, 100, 72))
            blobs = 11 + self.rng.randint(0, 4)
            for i in range(blobs):
                a = self.rng.uniform(0, math.tau)
                r = self.rng.uniform(0.4, 2.0) * s
                hgt = self.rng.uniform(3.0, 5.4) * s
                sz = self.rng.uniform(1.1, 2.0) * s
                g = self.rng.uniform(0.7, 1.12) * (0.85 + 0.15 * (hgt / (5.4 * s)))
                Entity(parent=leaves, model="sphere", position=(x + math.cos(a) * r, y + hgt, z + math.sin(a) * r),
                       scale=(sz * 1.15, sz * 0.9, sz * 1.15), color=color.rgb(0.78 * g, 0.95 * g, 0.7 * g))
        for x, z, s, rot in self.sc["bush"]:
            y = self.h(x, z)
            for i in range(3):
                a = self.rng.uniform(0, math.tau)
                Entity(parent=leaves, model="sphere", position=(x + math.cos(a) * 0.5 * s, y + 0.45 * s, z + math.sin(a) * 0.5 * s),
                       scale=(1.3 * s, 0.9 * s, 1.3 * s), color=color.rgb(0.7, 0.9, 0.62))
        trunks.texture = tex("textures3d/bark.png")
        trunks.shader = lit_shader
        trunks.combine(include_normals=True)
        leaves.combine(include_normals=True)
        leaves.texture_scale = (3, 3)
        self.trunks, self.leaves = trunks, leaves

    def rock_mesh(self, rng):
        """노이즈로 찌그러뜨린 구 메시"""
        lat, lon = 8, 12
        verts, uvs, tris, norms = [], [], [], []
        bumps = [rng.uniform(0.75, 1.2) for _ in range(lon)]
        for i in range(lat + 1):
            th = math.pi * i / lat
            for j in range(lon + 1):
                ph = 2 * math.pi * j / lon
                r = bumps[j % lon] * (0.9 + 0.2 * rng.random())
                v = (math.sin(th) * math.cos(ph) * r, math.cos(th) * 0.62 * r, math.sin(th) * math.sin(ph) * r)
                verts.append(v)
                norms.append(Vec3(*v).normalized())
                uvs.append((j / lon, i / lat))
        for i in range(lat):
            for j in range(lon):
                a, b = i * (lon + 1) + j, i * (lon + 1) + j + 1
                c, d = a + lon + 1, b + lon + 1
                tris += [a, c, b, b, c, d]
        return Mesh(vertices=verts, triangles=tris, uvs=uvs, normals=norms, static=True)

    def build_rocks(self):
        rocks = Entity(texture=tex("textures3d/rock.png"), shader=lit_shader)
        rng = random.Random(3)
        for x, z, s, rot in self.sc["rock"]:
            Entity(parent=rocks, model=self.rock_mesh(rng), position=(x, self.h(x, z) + 0.15 * s, z),
                   scale=(1.3 * s, 1.0 * s, 1.0 * s), rotation_y=rot, color=color.rgb(0.95, 0.95, 0.92))
        rocks.combine(include_normals=True)
        self.rocks = rocks

    def build_grass(self):
        """풀포기·꽃: 교차한 사각형 두 장씩을 한 메시에 몰아 넣는다 (알파 테스트)"""
        for kind, file, size in (("tuft", "tuft.png", 0.9), ("flower", "flower.png", 0.75)):
            verts, uvs, tris, cols = [], [], [], []
            for x, z, s, rot in self.sc[kind]:
                y = self.h(x, z) - 0.03
                w, hh = size * s, size * s * 0.9
                for k in range(2):
                    a = math.radians(rot + k * 90)
                    dx, dz = math.cos(a) * w / 2, math.sin(a) * w / 2
                    i0 = len(verts)
                    verts += [(x - dx, y, z - dz), (x + dx, y, z + dz), (x + dx, y + hh, z + dz), (x - dx, y + hh, z - dz)]
                    uvs += [(0, 0), (1, 0), (1, 1), (0, 1)]
                    shade = 0.8 + 0.2 * ((x * 7 + z * 3) % 1)
                    cols += [color.rgb(shade * 0.75, shade * 0.85, shade * 0.7)] * 2 + [color.rgb(shade, shade, shade)] * 2
                    tris += [i0, i0 + 1, i0 + 2, i0, i0 + 2, i0 + 3]
            e = Entity(model=Mesh(vertices=verts, triangles=tris, uvs=uvs, colors=cols, static=True),
                       texture=tex("textures3d/" + file), double_sided=True, shader=unlit_shader)
            e.setTransparency(TransparencyAttrib.MBinary)
            e.hide(0b0001)

    def blocked(self, x, z, r=0.45):
        if abs(x) > self.half - 7 or abs(z) > self.half - 7:
            return True
        return any((x - cx) ** 2 + (z - cz) ** 2 < (cr + r) ** 2 for cx, cz, cr in self.colliders)


# ====================================================================== 빌보드 캐릭터
ROW = {"se": 0, "sw": 1, "ne": 2, "nw": 3}


FIELD_DIR = os.environ.get("ARCTURUS_FIELD_DIR") or os.path.join(ROOT, "assets", "characters", "field")
PORTRAIT_DIR = os.path.join(ROOT, "assets", "characters", "portrait")


def field_manifest():
    try:
        with open(os.path.join(FIELD_DIR, "manifest.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


class Actor:
    HEIGHT = 1.85                 # 참고 스크린샷 비율: 나무(수관 지름 4~6) 대비 아담한 3~3.5등신
    _manifest = None

    def __init__(self, world, sprite, x, z, facing="se", name=""):
        self.world = world
        self.x, self.z = x, z
        self.facing = facing
        self.face_dir = None          # 월드 기준 바라보는 방향 (카메라가 돌면 스프라이트 방향도 다시 계산)
        self.cam_yaw = 0.0
        self.anim = 0.0
        self.t = random.uniform(0, 6)
        self.moving = False
        self.name = name
        if Actor._manifest is None:
            Actor._manifest = field_manifest()
        info = Actor._manifest.get(sprite, {})
        self.h = self.HEIGHT * info.get("height_scale", 1.0)
        path = os.path.join(FIELD_DIR, sprite + ".png")
        self.single = os.path.exists(path)
        if self.single:
            # 생성한 SD 전신 일러스트 한 장 (tools/art/prepare_field_chars.py 결과)
            t = Texture(path)
            t.filtering = "mipmap"
            self.native = info.get("faces", "front")
            self.w = self.h * t.width / t.height
            self.body = Entity(model="quad", texture=t, billboard=True, origin_y=-0.5, scale=(self.w, self.h),
                               double_sided=True, shader=unlit_shader)
        else:
            # 아직 일러스트가 없으면 4방향 시트 스프라이트
            self.w = self.h * 0.64
            self.body = Entity(model="quad", texture=tex(f"sprites3d/{sprite}.png", mipmap=False), billboard=True,
                               origin_y=-0.5, scale=(self.w, self.h), texture_scale=(0.25, 0.25), shader=unlit_shader)
        self.body.setTransparency(TransparencyAttrib.MDual)
        self.body.hide(0b0001)
        # 발밑 반투명 원형 그림자
        sw = max(0.9, self.w * (0.72 if self.single else 0.95))
        self.shadow = Entity(model="quad", texture=tex("textures3d/shadow.png"), rotation_x=90, scale=(sw, sw * 0.55),
                             color=color.rgba(1, 1, 1, 0.62), shader=unlit_shader)
        self.shadow.setTransparency(TransparencyAttrib.MAlpha)
        self.shadow.hide(0b0001)
        self.sync()

    def sync(self, dt=0.0):
        self.t += dt
        if self.face_dir:
            self._pick_row(*self.face_dir)
        y = self.world.h(self.x, self.z)
        self.shadow.position = (self.x, y + 0.04, self.z)
        if self.single:
            left = self.facing in ("sw", "nw")
            flip = left != (self.native == "left") if self.native != "front" else left
            if self.moving:
                ph = self.anim * math.pi / 2
                bob = abs(math.sin(ph)) * 0.07 * self.h
                sq = 1 + 0.035 * math.sin(ph * 2)
            else:
                bob, sq = 0.0, 1 + 0.012 * math.sin(self.t * 2.4)      # 숨쉬기
            self.body.scale = (-self.w if flip else self.w, self.h * sq)
            self.body.position = (self.x, y - 0.03 + bob, self.z)
            self.shadow.scale_x = self.shadow.scale_y / 0.55 * (1 - bob / self.h)
            return
        self.body.position = (self.x, y - 0.05, self.z)
        frame = int(self.anim) % 4 if self.moving else 0
        row = ROW[self.facing]
        self.body.texture_offset = (frame * 0.25, 1 - (row + 1) * 0.25)

    def face_vector(self, vx, vz, cam_yaw):
        self.cam_yaw = cam_yaw
        if abs(vx) > 1e-4 or abs(vz) > 1e-4:
            self.face_dir = (vx, vz)
        self._pick_row(vx, vz)

    def _pick_row(self, vx, vz):
        """월드 방향 벡터 → 카메라 기준 화면 방향으로 스프라이트 행 선택"""
        r = math.radians(self.cam_yaw)
        right = vx * math.cos(r) - vz * math.sin(r)
        fwd = vx * math.sin(r) + vz * math.cos(r)
        if abs(right) < 1e-4 and abs(fwd) < 1e-4:
            return
        back = fwd > 0.15
        self.facing = ("ne" if right >= 0 else "nw") if back else ("se" if right >= 0 else "sw")

    def step(self, vx, vz, dt, cam_yaw, speed):
        self.cam_yaw = cam_yaw
        self.moving = bool(vx or vz)
        if self.moving:
            self.face_vector(vx, vz, cam_yaw)
            self.anim += dt * speed * 1.6
        self.sync(dt)


# ====================================================================== 대화 UI
class DialogueUI:
    PANEL = (1.24, 0.29)

    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, enabled=False)
        self.art = Entity(parent=self.root, model="quad", origin=(0, -0.5), position=(0.6, -0.5), z=-0.2)
        self.panel = Entity(parent=self.root, model="quad", texture=tex("ui3d/dialog_panel.png"),
                            scale=self.PANEL, position=(-0.13, -0.335), z=0)
        self.name = Text(parent=self.root, text="", font=font(FONT_UI), origin=(-0.5, 0.5), position=(-0.69, -0.215),
                         z=-0.1, scale=1.15, color=rgb(122, 66, 30))
        self.body = Text(parent=self.root, text=" ", font=font(FONT_TEXT), origin=(-0.5, 0.5), position=(-0.69, -0.262),
                         z=-0.1, scale=1.22, color=rgb(58, 40, 26), wordwrap=34)
        self.body.line_height = 1.25
        self.next = Entity(parent=self.root, model="quad", texture=tex("ui3d/next.png"), scale=0.035,
                           position=(0.32, -0.44), z=-0.1)
        self.lines, self.i, self.shown, self.t = [], 0, 0.0, 0.0
        self.on_done = None
        self.art_from = 0.0

    @property
    def active(self):
        return self.root.enabled

    def open(self, lines, on_done=None):
        self.lines = [l for l in lines if l.get("speaker") != "choice"]
        self.i, self.shown, self.on_done = 0, 0.0, on_done
        self.root.enabled = True
        self.show_line()

    def show_line(self):
        line = self.lines[self.i]
        sid = line["speaker"]
        g = self.game
        if line.get("bgm_mood"):                 # 대사 분위기에 따라 BGM 전환
            g.set_bgm(g.world.m.get("bgm") if line["bgm_mood"] == "default" else line["bgm_mood"])
        self.shown = 0.0
        self.body.text = ""
        self.body.color = rgb(58, 40, 26) if sid != "system" else rgb(130, 80, 20)
        if sid in ("narration", "system"):
            self.name.text = ""
        else:
            self.name.text = f"[{g.speaker_name(sid)}]"
        art = g.standing_art(sid, line.get("emotion", "normal"))
        if art:
            t = tex(art)
            aspect = t.width / t.height
            h = 0.92 if aspect < 0.62 else 0.8          # 반신 일러스트(가로가 넓음)는 조금 작게
            w = h * aspect
            self.art_x = min(0.6, 0.875 - w / 2)          # 화면 오른쪽 밖으로 잘리지 않게
            prev = self.art.texture
            self.art.texture = t
            self.art.scale = (w, h)
            self.art.enabled = True
            if prev is None or getattr(prev, "path", None) != t.path:
                self.art_from = 0.0          # 다른 인물이면 슬라이드 인
        else:
            self.art.enabled = False
        g.sfx("sfx_text")

    def advance(self):
        full = len(self.lines[self.i]["text"])
        if self.shown < full:
            self.shown = full
            return
        self.i += 1
        if self.i >= len(self.lines):
            self.root.enabled = False
            self.art.texture = None
            self.game.set_bgm(self.game.world.m.get("bgm"))     # 대화가 끝나면 맵 기본 곡으로
            if self.on_done:
                self.on_done()
            return
        self.show_line()

    def update(self, dt):
        if not self.active:
            return
        self.t += dt
        line = self.lines[self.i]
        full = len(line["text"])
        if self.shown < full:
            self.shown = min(full, self.shown + 38 * dt)
            self.body.text = line["text"][: int(self.shown)]
        self.next.enabled = self.shown >= full
        self.next.y = -0.44 + abs(math.sin(self.t * 5)) * 0.008
        self.art_from = min(1.0, self.art_from + dt * 4)
        k = 1 - (1 - self.art_from) ** 3
        self.art.x = getattr(self, "art_x", 0.6) + (1 - k) * 0.12
        self.art.alpha = k


class Banner:
    def __init__(self, title, subtitle):
        self.root = Entity(parent=camera.ui)
        self.bg = Entity(parent=self.root, model="quad", texture=tex("ui3d/banner.png"), scale=(1.1, 0.13), y=0.36)
        self.t1 = Text(parent=self.root, text=title, font=font(FONT_TEXT), origin=(0, 0), y=0.372, scale=2.0,
                       color=rgb(244, 220, 160))
        self.t2 = Text(parent=self.root, text=subtitle, font=font(FONT_TEXT), origin=(0, 0), y=0.33, scale=0.95,
                       color=rgb(230, 220, 200))
        self.t = 0.0

    def update(self, dt):
        if self.root is None:
            return
        self.t += dt
        a = min(1, self.t * 2, max(0, (3.6 - self.t) * 1.5))
        for e in (self.bg, self.t1, self.t2):
            e.alpha = a
        if self.t > 3.6:
            destroy(self.root)
            self.root = None


# ====================================================================== 게임
class Game:
    def __init__(self, map_id="verdan_edge", size=(1280, 720)):
        self.app = Ursina(title="황동의 심장 : 아스카론 연대기 (3D)", size=size, development_mode=False,
                          borderless=False, vsync=True)
        window.color = rgb(150, 182, 210)
        window.fps_counter.enabled = False
        window.exit_button.enabled = False
        Texture.default_filtering = "mipmap"
        from pathlib import Path
        application.fonts_folder = Path(FONTS)
        Text.default_resolution = 1440 * Text.size
        self.story = load_json("story.json")
        self.world = World(map_id)
        m = self.world.m
        # 조명·안개는 src3d/shaders.py 의 자체 셰이더가 계산 (그림자는 지형 텍스처에 구워 둠)
        window.color = color.rgb(*LIGHT["fog_color"])
        # 파티 (루크가 앞장서고 아이리스·제드가 뒤따름)
        sx, sz = m["start"]
        self.player = Actor(self.world, "luke", sx, sz, m.get("start_dir", "ne"), "luke")
        self.followers = [Actor(self.world, "iris", sx, sz - 1.5, "ne", "iris"),
                          Actor(self.world, "zed", sx, sz - 3.0, "ne", "zed")]
        self.trail = [(sx, sz - i * 0.125) for i in range(160)]     # 처음엔 뒤로 한 줄 대열
        # NPC
        self.npcs = []
        for n in m.get("npcs", []):
            a = Actor(self.world, n["sprite"], n["pos"][0], n["pos"][1], n.get("dir", "se"), n["id"])
            a.data = n
            a.talks = 0
            self.npcs.append(a)
            self.world.colliders.append((a.x, a.z, 0.6))
        self.bubble = Entity(model="quad", texture=tex("ui3d/bubble.png"), billboard=True, scale=0.75,
                             shader=unlit_shader, enabled=False)
        self.bubble.setTransparency(TransparencyAttrib.MAlpha)
        self.bubble.hide(0b0001)
        # 카메라
        self.yaw, self.yaw_goal = 35.0, 35.0
        self.pitch, self.dist = 50.0, 36.0
        camera.fov = 30
        self.cam_target = Vec3(self.player.x, self.world.h(self.player.x, self.player.z), self.player.z)
        # UI
        self.dialogue = DialogueUI(self)
        self.banner = Banner(m["name"], m.get("subtitle", ""))
        self.hint = Text(parent=camera.ui, text="WASD·방향키 이동   Z·Space 대화   Q/E 시점 회전   휠 확대",
                         font=font(FONT_UI), origin=(-0.5, 0.5), position=(-0.87, 0.485), scale=0.85,
                         color=color.rgba(1, 1, 1, 0.85))
        self.hint.create_background(padding=0.012, radius=0.008, color=color.rgba(0.08, 0.06, 0.04, 0.55))
        self.input_override = None        # 자동 테스트: (x, z) 이동 입력
        self.bgm = None
        self._audio(m.get("bgm"))
        Entity(update=self.update, input=self.input)
        self.update_camera(1.0)
        intro = m.get("intro_scene")
        if intro:
            scene_ = next((s for c in self.story["chapters"] for s in c["scenes"] if s["id"] == intro), None)
            if scene_:
                self.dialogue.open(scene_["dialogue"])

    # ------------------------------------------------------------ 데이터
    def speaker_name(self, sid):
        meta = self.story["meta"]["speaker_ids"]
        if sid in meta:
            return meta[sid]
        for town in self.story["npc_dialogues"].values():
            for n in town["npcs"]:
                if n["id"] == sid:
                    return n["name"]
        return sid

    def standing_art(self, sid, emotion):
        sprite = self.world.m.get("standing", {}).get(sid, sid)
        emotion = EMO_MAP.get(emotion, emotion)
        # 1순위: 생성한 반신 일러스트 assets/characters/portrait/<id>[_<감정>].png
        for name in (f"{sprite}_{emotion}.png", f"{sprite}.png"):
            p = os.path.join(PORTRAIT_DIR, name)
            if os.path.exists(p):
                return p
        for emo in (emotion, "normal"):
            rel = f"standing/stand_{sprite}_{emo}.png"
            if os.path.exists(os.path.join(IMG, rel)):
                return rel
        return None

    # ------------------------------------------------------------ 소리
    BGM_VOLUME = 0.5

    def _audio(self, bgm):
        """ursina Audio 는 절대 경로를 못 받으므로 Panda3D 로더로 직접 불러온다"""
        self._sfx = {}
        self._music = {}
        self.bgm, self.bgm_name, self.fading = None, None, []
        self.set_bgm(bgm, fade=0.0)

    def set_bgm(self, name, fade=1.0):
        """BGM 교체: 이전 곡은 fade 초 동안 줄이고 새 곡은 키운다 (크로스페이드)"""
        if not name or name == self.bgm_name:
            return
        try:
            if name not in self._music:
                path = os.path.join(ROOT, "assets", "bgm", name + ".ogg")
                if not os.path.exists(path):
                    return
                self._music[name] = self.app.loader.loadMusic(Filename.fromOsSpecific(path))
                self._music[name].setLoop(True)
            snd = self._music[name]
        except Exception:  # noqa: BLE001 - 사운드 장치가 없어도 진행
            return
        if self.bgm is not None:
            self.fading.append([self.bgm, self.bgm.getVolume()])
        self.fading = [f for f in self.fading if f[0] is not snd]
        snd.setVolume(0.0 if fade else self.BGM_VOLUME)
        snd.play()
        self.bgm, self.bgm_name, self.bgm_fade = snd, name, fade
        self.log_bgm = getattr(self, "log_bgm", []) + [name]

    def _update_music(self, dt):
        if self.bgm is None:
            return
        f = getattr(self, "bgm_fade", 0.0)
        step = dt / f if f else 1.0
        self.bgm.setVolume(min(self.BGM_VOLUME, self.bgm.getVolume() + self.BGM_VOLUME * step))
        keep = []
        for snd, v in self.fading:
            v = max(0.0, v - self.BGM_VOLUME * step)
            snd.setVolume(v)
            if v > 0:
                keep.append([snd, v])
            else:
                snd.stop()
        self.fading = keep

    def sfx(self, name):
        try:
            if name not in self._sfx:
                self._sfx[name] = self.app.loader.loadSfx(
                    Filename.fromOsSpecific(os.path.join(ROOT, "assets", "sfx", name.replace("sfx_", "") + ".ogg")))
                self._sfx[name].setVolume(0.6)
            self._sfx[name].play()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ 입력/갱신
    def input(self, key):
        if self.dialogue.active:
            if key in ("z", "space", "enter", "left mouse down"):
                self.dialogue.advance()
            return
        if key in ("z", "space", "enter"):
            self.try_talk()
        elif key == "q":
            self.yaw_goal -= 45
        elif key == "e":
            self.yaw_goal += 45
        elif key == "scroll up":
            self.dist = max(20, self.dist - 3)
        elif key == "scroll down":
            self.dist = min(50, self.dist + 3)
        elif key == "escape":
            application.quit()

    def move_vector(self):
        if self.input_override is not None:
            return self.input_override
        ix = (held_keys["d"] or held_keys["right arrow"]) - (held_keys["a"] or held_keys["left arrow"])
        iz = (held_keys["w"] or held_keys["up arrow"]) - (held_keys["s"] or held_keys["down arrow"])
        if not ix and not iz:
            return 0.0, 0.0
        r = math.radians(self.yaw)
        fx, fz = math.sin(r), math.cos(r)            # 카메라가 바라보는 수평 방향
        rx, rz = math.cos(r), -math.sin(r)
        vx, vz = fx * iz + rx * ix, fz * iz + rz * ix
        n = math.hypot(vx, vz)
        return vx / n, vz / n

    def update(self):
        from ursina import time as utime
        dt = min(utime.dt, 1 / 20)
        self._update_music(dt)
        self.clock = getattr(self, "clock", 0.0) + dt
        self.dialogue.update(dt)
        self.banner.update(dt)
        speed = 5.2
        vx, vz = (0.0, 0.0) if self.dialogue.active else self.move_vector()
        p = self.player
        if vx or vz:
            nx, nz = p.x + vx * speed * dt, p.z + vz * speed * dt
            if not self.world.blocked(nx, p.z):
                p.x = nx
            if not self.world.blocked(p.x, nz):
                p.z = nz
            if math.hypot(p.x - self.trail[0][0], p.z - self.trail[0][1]) > 0.12:
                self.trail.insert(0, (p.x, p.z))
                self.trail = self.trail[:160]
        p.step(vx, vz, dt, self.yaw, speed)
        # 동료: 발자취를 따라 일정 간격 뒤에서 걷는다
        for i, f in enumerate(self.followers):
            tx, tz = self.trail[min(len(self.trail) - 1, (i + 1) * 12)]
            dx, dz = tx - f.x, tz - f.z
            d = math.hypot(dx, dz)
            if d > 0.08:
                k = min(1.0, speed * 1.05 * dt / d)
                f.x += dx * k
                f.z += dz * k
                f.step(dx / d, dz / d, dt, self.yaw, speed)
            else:
                f.step(0, 0, dt, self.yaw, speed)
        for n in self.npcs:
            n.step(0, 0, dt, self.yaw, speed)
        # 말 걸 수 있는 NPC 표시
        near = self.nearest_npc()
        self.bubble.enabled = bool(near) and not self.dialogue.active
        if near:
            self.bubble.position = (near.x, self.world.h(near.x, near.z) + near.h + 0.55 + math.sin(self.clock * 4) * 0.08,
                                    near.z)
        self.update_camera(dt)

    def update_camera(self, dt):
        self.yaw = lerp(self.yaw, self.yaw_goal, min(1, dt * 6))
        p = self.player
        goal = Vec3(p.x, self.world.h(p.x, p.z) + 0.9, p.z)
        self.cam_target = lerp(self.cam_target, goal, min(1, dt * 6))
        r, pr = math.radians(self.yaw), math.radians(self.pitch)
        hd = math.cos(pr) * self.dist
        camera.position = self.cam_target + Vec3(-math.sin(r) * hd, math.sin(pr) * self.dist, -math.cos(r) * hd)
        camera.look_at(self.cam_target)

    def nearest_npc(self, reach=2.6):
        p = self.player
        best, bd = None, reach
        for n in self.npcs:
            d = math.hypot(n.x - p.x, n.z - p.z)
            if d < bd:
                best, bd = n, d
        return best

    def try_talk(self):
        n = self.nearest_npc()
        if not n:
            return
        d = n.data
        town = self.story["npc_dialogues"].get(d["town"], {"npcs": []})
        prof = next((x for x in town["npcs"] if x["id"] == d["id"]), None)
        pool = []
        for k in d.get("keys", ["default"]):
            pool += (prof or {}).get("dialogues", {}).get(k, [])
        if not pool:
            return
        line = pool[n.talks % len(pool)]
        n.talks += 1
        # 서로 마주 보기
        n.face_vector(self.player.x - n.x, self.player.z - n.z, self.yaw)
        self.player.face_vector(n.x - self.player.x, n.z - self.player.z, self.yaw)
        self.sfx("sfx_confirm")
        self.dialogue.open([{"speaker": d["id"], "text": line}])

    def run(self):
        self.app.run()
