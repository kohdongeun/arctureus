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
from ursina import (Entity, Quad, Mesh, Text, Texture, Ursina, Vec3, application, camera, color, destroy,
                    held_keys, lerp, window)

from src3d import terrain
from src3d.shaders import (GLSL, LIGHT, check_support, lit_shader, sprite_mesh, sprite_shader, terrain_shader,
                           unlit_shader)

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


# ====================================================================== 메시 생성 헬퍼
def weapon_quad(pose, cw=1024, ch=256, x0=40, x1=984):
    """무기 그림(가로 1024x256, 손잡이 끝 x0 → 끝 x1) 네 모서리 → 캐릭터 원본 그림의 픽셀 좌표.
    tools/art/make_weapon_layers.py 의 quad_px 와 같은 계산 (그림 위쪽이 화면 위쪽을 향함)."""
    gx, gy = pose["grip"]
    tx, ty = pose["tip"]
    L = math.hypot(tx - gx, ty - gy)
    ux, uy = (tx - gx) / L, (ty - gy) / L
    nx, ny = uy, -ux
    if ny > 0:
        nx, ny = -nx, -ny
    k = L / (x1 - x0)
    th = pose.get("thick", 1.0)

    def P(cx, cy):
        a = (cx - x0) * k
        b = -(cy - ch / 2) * k * th
        return (gx + ux * a + nx * b, gy + uy * a + ny * b)
    return [P(0, 0), P(cw, 0), P(cw, ch), P(0, ch)]


def _unit_sphere(lat, lon):
    """반지름 1 구 (위→아래 행, 각도 열). 반환: 정점(=법선), uv, 삼각형 인덱스"""
    import numpy as np
    th = np.linspace(0, math.pi, lat + 1)
    ph = np.linspace(0, math.tau, lon + 1)
    T, P = np.meshgrid(th, ph, indexing="ij")
    v = np.stack([np.sin(T) * np.cos(P), np.cos(T), np.sin(T) * np.sin(P)], -1).reshape(-1, 3)
    uv = np.stack([P / math.tau, 1 - T / math.pi], -1).reshape(-1, 2)
    tris = []
    for i in range(lat):
        for j in range(lon):
            a, b = i * (lon + 1) + j, i * (lon + 1) + j + 1
            c, d = a + lon + 1, b + lon + 1
            tris += [a, c, b, b, c, d]
    return v, uv, np.array(tris, np.int64)


def _unit_cylinder(n):
    """아래 y=0, 위 y=1, 반지름 1 옆면. 반환: 정점, 법선, uv, 삼각형"""
    import numpy as np
    ang = np.linspace(0, math.tau, n + 1)
    top = np.stack([np.cos(ang), np.ones_like(ang), np.sin(ang)], -1)
    bot = np.stack([np.cos(ang), np.zeros_like(ang), np.sin(ang)], -1)
    v = np.concatenate([top, bot])
    nrm = v * [1, 0, 1]
    uv = np.concatenate([np.stack([ang / math.tau, np.ones_like(ang)], -1), np.stack([ang / math.tau, np.zeros_like(ang)], -1)])
    tris = []
    for k in range(n):
        a, b, c, d = k, k + 1, n + 1 + k, n + 2 + k
        tris += [a, c, b, b, c, d]
    return v, nrm, uv, np.array(tris, np.int64)


def _merge(parts, col_div):
    """(정점, 법선, uv, 색, 삼각형) 조각들을 한 Mesh 로"""
    import numpy as np
    vs, ns, us, cs, ts = [], [], [], [], []
    off = 0
    for v, n, uv, col, t in parts:
        vs.append(v)
        ns.append(n)
        us.append(uv)
        cs.append(np.tile(np.array(list(col) + [col_div], float) / col_div, (len(v), 1)))
        ts.append(t + off)
        off += len(v)
    V, N, U, C, T = (np.concatenate(a) for a in (vs, ns, us, cs, ts))
    N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-6)
    return Mesh(vertices=V.tolist(), triangles=T.tolist(), uvs=U.tolist(), normals=N.tolist(),
                colors=[color.rgba(*c) for c in C.tolist()], static=True)


# ====================================================================== 월드
class World:
    def __init__(self, map_id):
        self.m = terrain.load_map(map_id)
        self.half = self.m["size"] / 2
        self.sc = terrain.scatter(self.m)
        self.colliders = terrain.colliders(self.m, self.sc)
        self.rng = random.Random(self.m.get("seed", 1))
        self.ents = []
        self.build_terrain()
        self.build_trees()
        self.build_rocks()
        self.build_grass()
        self.build_town()
        self.chests = []
        self.altars = []

    def build_town(self):
        """건물·가로등·상자 소품 (src3d/buildings.py)"""
        from src3d import buildings
        self.rects, self.chimneys = [], []
        if not (self.m.get("buildings") or self.m.get("lamps") or self.m.get("crates")):
            return
        ents, self.rects, self.chimneys = buildings.build(self.m, self.h, tex)
        self.ents += ents

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
        if GLSL["ok"] and all(os.path.exists(os.path.join(IMG, v)) for v in list(tiles.values()) + [splat]):
            # 잔디·흙길·돌바닥 타일 텍스처를 월드 좌표로 반복 + 분포 맵으로 섞기 (가까이서도 선명)
            self.ground = Entity(model=mesh, texture=tex(splat), shader=terrain_shader)
            for k, v in tiles.items():
                self.ground.set_shader_input(f"{k}_tex", tex(v)._texture)
            self.ground.set_shader_input("tile", 4.5)
        else:
            self.ground = Entity(model=mesh, texture=tex(f"textures3d/terrain_{self.m['id']}.jpg"),
                                 shader=lit_shader)
        self.ents.append(self.ground)

    def build_trees(self):
        """나무·덤불을 numpy 로 바로 한 메시에 쌓는다.
        (구 엔티티 수천 개를 만든 뒤 combine 하면 RAM 이 3GB 가까이 들어서, 저해상도 구·원기둥을 직접 생성)"""
        import numpy as np
        sph_v, sph_uv, sph_t = _unit_sphere(7, 11)
        cyl_v, cyl_n, cyl_uv, cyl_t = _unit_cylinder(7)
        trunk_parts, leaf_parts = [], []

        def cyl(base, d, r, h, col):
            d = np.asarray(d, float)
            d /= np.linalg.norm(d)
            u = np.cross(d, [0.0, 0.0, 1.0] if abs(d[2]) < 0.9 else [1.0, 0.0, 0.0])
            u /= np.linalg.norm(u)
            w = np.cross(u, d)
            loc = cyl_v * [r, h, r]
            pos = base + loc[:, :1] * u + loc[:, 1:2] * d + loc[:, 2:3] * w
            nrm = cyl_n[:, :1] * u + cyl_n[:, 2:3] * w
            trunk_parts.append((pos, nrm, cyl_uv, col, cyl_t))

        def blob(center, scale, col):
            leaf_parts.append((sph_v * scale + center, sph_v, sph_uv, col, sph_t))

        for x, z, s, rot in self.sc["tree"]:
            y = self.h(x, z) - 0.3
            base = np.array([x, y, z])
            cyl(base, (0, 1, 0), 0.32 * s, 3.4 * s, (150, 110, 80))
            for k in range(3):            # 굵은 가지
                a = math.radians(rot + k * 120)
                d = (math.cos(a) * math.sin(math.radians(40)), math.cos(math.radians(40)), math.sin(a) * math.sin(math.radians(40)))
                cyl(base + [0, 2.3 * s, 0], d, 0.12 * s, 1.4 * s, (140, 100, 72))
            blobs = 11 + self.rng.randint(0, 4)
            for i in range(blobs):
                a = self.rng.uniform(0, math.tau)
                r = self.rng.uniform(0.4, 2.0) * s
                hgt = self.rng.uniform(3.0, 5.4) * s
                sz = self.rng.uniform(1.1, 2.0) * s
                g = self.rng.uniform(0.7, 1.12) * (0.85 + 0.15 * (hgt / (5.4 * s)))
                blob((x + math.cos(a) * r, y + hgt, z + math.sin(a) * r), np.array([sz * 1.15, sz * 0.9, sz * 1.15]) / 2,
                     (0.78 * g, 0.95 * g, 0.7 * g))
        for x, z, s, rot in self.sc["bush"]:
            y = self.h(x, z)
            for i in range(3):
                a = self.rng.uniform(0, math.tau)
                blob((x + math.cos(a) * 0.5 * s, y + 0.45 * s, z + math.sin(a) * 0.5 * s),
                     np.array([1.3 * s, 0.9 * s, 1.3 * s]) / 2, (0.7, 0.9, 0.62))
        trunks = Entity(model=_merge(trunk_parts, 255), texture=tex("textures3d/bark.png"), shader=lit_shader)
        leaves = Entity(model=_merge(leaf_parts, 1), texture=tex("textures3d/leaves.png"), shader=lit_shader)
        leaves.texture_scale = (3, 3)
        self.trunks, self.leaves = trunks, leaves
        self.ents += [trunks, leaves]

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
        self.ents.append(rocks)

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
            self.ents.append(e)

    def destroy(self):
        for e in self.ents:
            destroy(e)
        self.ents = []
        for c in self.chests + self.altars:
            c.destroy()
        self.chests, self.altars = [], []

    def blocked(self, x, z, r=0.45):
        if abs(x) > self.half - 7 or abs(z) > self.half - 7:
            return True
        if any(abs(x - rx) < hw + r and abs(z - rz) < hd + r for rx, rz, hw, hd in getattr(self, "rects", [])):
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


def _chest_tex(key):
    return tex({"wood": "town/chest_wood.jpg", "metal": "town/chest_band.jpg", "stone": "textures3d/tile_stone.jpg",
                "gold": "town/metal.jpg"}[key])


class Chest:
    """보물상자: 몸통 + 경첩으로 열리는 뚜껑. 열면 안의 물건을 얻는다 (플래그로 기억)."""
    W, H, D = 1.15, 0.62, 0.74

    def __init__(self, world, data, opened):
        from src3d.buildings import MeshBuilder
        self.data = data
        self.x, self.z = data["pos"]
        self.opened = opened
        self.t = 1.0 if opened else 0.0
        y = world.h(self.x, self.z)
        self.root = Entity(position=(self.x, y, self.z), rotation_y=data.get("rot", 0))
        w, h, d = self.W, self.H, self.D
        same = lambda a, b, c: (a, b, c)  # noqa: E731
        mb = MeshBuilder()
        mb.box("wood", (0, h / 2, 0), (w, h, d), same, 0.7)
        for bx in (-w * 0.34, w * 0.34):
            mb.box("metal", (bx, h / 2, 0), (0.13, h + 0.02, d + 0.03), same, 0.5)
        mb.box("gold", (0, h * 0.62, -d / 2 - 0.03), (0.2, 0.24, 0.06), same, 0.3)
        for e in mb.entities(_chest_tex):
            e.parent = self.root
        # 뚜껑: 뒤쪽 위 모서리가 경첩
        self.lid = Entity(parent=self.root, position=(0, h, d / 2))
        lb = MeshBuilder()
        lb.box("wood", (0, 0.14, -d / 2), (w + 0.04, 0.28, d + 0.04), same, 0.7)
        for bx in (-w * 0.34, w * 0.34):
            lb.box("metal", (bx, 0.15, -d / 2), (0.14, 0.3, d + 0.06), same, 0.5)
        for e in lb.entities(_chest_tex):
            e.parent = self.lid
        self.sync()

    def sync(self):
        k = 1 - (1 - self.t) ** 3
        self.lid.rotation_x = -108 * k

    def destroy(self):
        destroy(self.root)


class Altar:
    """잊힌 서약의 사당: 돌 제단 + 인장 조각을 끼우는 홈 3개 (가진 조각만큼 빛남)"""

    def __init__(self, world, data):
        from src3d.buildings import MeshBuilder
        self.data = data
        self.x, self.z = data["pos"]
        y = world.h(self.x, self.z)
        self.root = Entity(position=(self.x, y, self.z))
        same = lambda a, b, c: (a, b, c)  # noqa: E731
        mb = MeshBuilder()
        mb.box("stone", (0, 0.2, 0), (3.2, 0.4, 2.4), same, 1.0)
        mb.box("stone", (0, 0.75, 0), (2.2, 0.7, 1.2), same, 1.0)
        mb.box("stone", (0, 1.2, 0), (2.6, 0.2, 1.5), same, 1.0)
        for sx in (-1.4, 1.4):                       # 양쪽 돌기둥
            mb.box("stone", (sx, 1.3, 0.9), (0.5, 2.6, 0.5), same, 1.0)
        for e in mb.entities(_chest_tex):
            e.parent = self.root
        self.sockets = []
        for i, sx in enumerate((-0.7, 0, 0.7)):
            s = Entity(parent=self.root, model="sphere", position=(sx, 1.38, 0), scale=0.3, shader=unlit_shader,
                       color=color.rgb(0.25, 0.25, 0.3))
            self.sockets.append(s)
        self.lit = -1

    def set_lit(self, n):
        if n == self.lit:
            return
        self.lit = n
        for i, s in enumerate(self.sockets):
            s.color = color.rgb(0.5, 0.95, 1.0) if i < n else color.rgb(0.25, 0.25, 0.3)

    def destroy(self):
        destroy(self.root)


class Motion:
    """빌보드 한 장에 얹는 연출 채널 (전투 동작이 매 프레임 채워 넣고, Actor/EnemyView 가 셰이더로 반영)"""
    __slots__ = ("lean", "hop", "sx", "sy", "flash", "off", "walk")

    def __init__(self):
        self.reset()

    def reset(self):
        self.lean, self.hop, self.sx, self.sy, self.flash = 0.0, 0.0, 1.0, 1.0, 0.0
        self.off = Vec3(0, 0, 0)
        self.walk = None                # None 이면 이동 여부로 자동


class Actor:
    HEIGHT = 1.85                 # 참고 스크린샷 비율: 나무(수관 지름 4~6) 대비 아담한 3~3.5등신
    TURN_TIME = 0.16              # 좌우 방향 전환(종이 뒤집기) 시간
    _manifest = None

    def __init__(self, world, sprite, x, z, facing="se", name=""):
        self.world = world
        self.x, self.z = x, z
        self.facing = facing
        self.face_dir = None          # 월드 기준 바라보는 방향 (카메라가 돌면 스프라이트 방향도 다시 계산)
        self.cam_yaw = 0.0
        self.anim = 0.0               # 걸음 위상 (π 마다 한 걸음)
        self.walk_amt = 0.0           # 걷기 동작 세기 (멈추면 부드럽게 0으로)
        self.t = random.uniform(0, 6)
        self.moving = False
        self.name = name
        self.on_step = None           # 발이 땅에 닿을 때마다 호출 (발소리·먼지)
        self.mo = Motion()
        self.sprite = sprite
        self.weapon = None            # 장착 무기 그림 (몸 앞/뒤에 붙는 사각형)
        self.weapon_id = None
        if Actor._manifest is None:
            Actor._manifest = field_manifest()
        info = Actor._manifest.get(sprite, {})
        self.h = self.HEIGHT * info.get("height_scale", 1.0)
        path = os.path.join(FIELD_DIR, sprite + ".png")
        self.single = os.path.exists(path)
        if self.single:
            # 생성한 SD 전신 일러스트 한 장 (tools/art/prepare_field_chars.py 결과) + 종이 인형 리그
            t = Texture(path)
            t.filtering = "mipmap"
            self.native = info.get("faces", "front")
            self.w = self.h * t.width / t.height
            self.body = Entity(model=sprite_mesh(), texture=t, billboard=True, scale=(self.w, self.h),
                               double_sided=True, shader=sprite_shader)
        else:
            # 아직 일러스트가 없으면 4방향 시트 스프라이트
            self.native = "front"
            self.w = self.h * 0.64
            self.body = Entity(model="quad", texture=tex(f"sprites3d/{sprite}.png", mipmap=False), billboard=True,
                               origin_y=-0.5, scale=(self.w, self.h), texture_scale=(0.25, 0.25), shader=unlit_shader)
        self.sx = self.w if not self._flip() else -self.w        # 화면상 가로 배율 (뒤집기 애니메이션용)
        self.body.setTransparency(TransparencyAttrib.MDual)
        self.body.hide(0b0001)
        # 발밑 반투명 원형 그림자
        sw = max(0.9, self.w * (0.72 if self.single else 0.95))
        self.shadow_w = sw
        self.shadow = Entity(model="quad", texture=tex("textures3d/shadow.png"), rotation_x=90, scale=(sw, sw * 0.55),
                             color=color.rgba(1, 1, 1, 0.62), shader=unlit_shader)
        self.shadow.setTransparency(TransparencyAttrib.MAlpha)
        self.shadow.hide(0b0001)
        self.sync()

    def set_weapon(self, weapon_id):
        """장착 무기를 캐릭터 그림에 붙인다: 원래 그려진 무기를 지운 몸 그림 + 무기 그림 (data/weapon_pose.json)"""
        if not self.single or weapon_id == self.weapon_id:
            return
        pose = load_json("weapon_pose.json").get(self.sprite)
        wimg = os.path.join(IMG, "equipment", f"{weapon_id}.png") if weapon_id else None
        body_img = os.path.join(FIELD_DIR, f"{self.sprite}_body.png")
        if not pose or not wimg or not os.path.exists(wimg) or not os.path.exists(body_img):
            return
        self.weapon_id = weapon_id
        if self.weapon is None:
            self.body.texture = tex(body_img)
            W, H = pose["size"]
            q = weapon_quad(pose)
            verts = [(x / W - 0.5, 1 - y / H, 0) for x, y in q]
            mesh = Mesh(vertices=verts, uvs=[(0, 1), (1, 1), (1, 0), (0, 0)], triangles=[0, 2, 1, 0, 3, 2])
            self.weapon = Entity(parent=self.body, model=mesh, double_sided=True, shader=sprite_shader,
                                 z=-0.004 if pose["layer"] == "front" else 0.004)
            self.weapon.setTransparency(TransparencyAttrib.MDual)
            self.weapon.hide(0b0001)
        self.weapon.texture = tex(wimg)

    def _flip(self):
        left = self.facing in ("sw", "nw")
        if self.native == "front":
            return left
        return left != (self.native == "left")

    @property
    def forward_sign(self):
        """모델 좌표 +x 가 화면에서 바라보는 쪽이면 1 (기울이기 방향 보정)"""
        return -1.0 if self.native == "left" else 1.0

    def sync(self, dt=0.0):
        self.t += dt
        if self.face_dir:
            self._pick_row(*self.face_dir)
        mo = self.mo
        y = self.world.h(self.x, self.z)
        px, pz = self.x + mo.off.x, self.z + mo.off.z
        self.shadow.position = (px, self.world.h(px, pz) + 0.04, pz)
        if not self.single:
            self.body.position = (px, y - 0.05 + mo.hop, pz)
            frame = int(self.anim) % 4 if self.moving else 0
            self.body.texture_offset = (frame * 0.25, 1 - (ROW[self.facing] + 1) * 0.25)
            return
        # 좌우 전환: 가로 배율이 0 을 지나 반대로 (종이 인형을 뒤집듯)
        target = -self.w if self._flip() else self.w
        step = 2 * self.w / self.TURN_TIME * dt if dt else 2 * self.w
        self.sx = target if abs(target - self.sx) <= step else self.sx + math.copysign(step, target - self.sx)
        # 걷기: 위상이 π 를 지날 때마다 한 걸음
        goal = (1.0 if self.moving else 0.0) if mo.walk is None else mo.walk
        self.walk_amt += (goal - self.walk_amt) * min(1.0, dt * 10)
        if self.walk_amt < 0.02 and not self.moving:
            self.anim = 0.0
        breath = 1 + 0.012 * math.sin(self.t * 2.4) * (1 - self.walk_amt)       # 가만히 있을 땐 숨쉬기
        turn = abs(self.sx) / self.w                                              # 뒤집는 중엔 얇아짐
        self.body.scale = (self.sx * mo.sx, self.h * breath * mo.sy)
        self.body.position = (px, y - 0.03, pz)
        b = self.body
        b.set_shader_input("walk", self.walk_amt)
        b.set_shader_input("phase", self.anim)
        b.set_shader_input("lean", mo.lean * self.forward_sign)
        b.set_shader_input("hop", mo.hop / max(0.01, self.h))
        b.set_shader_input("flash", mo.flash)
        if self.weapon is not None:                 # 무기 층도 같은 동작 (같은 좌표계)
            wp = self.weapon
            for k in ("walk", "phase", "lean", "hop", "flash"):
                wp.set_shader_input(k, b.get_shader_input(k))
        bob = abs(math.cos(self.anim)) * 0.035 * self.h * self.walk_amt + mo.hop
        self.shadow.scale = (self.shadow_w * (1 - min(0.5, bob / self.h)) * (0.85 + 0.15 * turn),
                             self.shadow_w * 0.55 * (1 - min(0.5, bob / self.h)))

    def destroy(self):
        destroy(self.body)
        destroy(self.shadow)

    def set_visible(self, on):
        self.body.enabled = self.shadow.enabled = on

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
        if abs(right) < 0.2:                       # 거의 위/아래로만 움직이면 좌우는 그대로
            is_right = self.facing in ("ne", "se")
        else:
            is_right = right > 0
        self.facing = ("ne" if is_right else "nw") if back else ("se" if is_right else "sw")

    def step(self, vx, vz, dt, cam_yaw, speed):
        self.cam_yaw = cam_yaw
        self.moving = bool(vx or vz)
        if self.moving:
            self.face_vector(vx, vz, cam_yaw)
            before = int(self.anim / math.pi)
            self.anim += dt * speed * 1.25          # 걸음 위상 (속도 5.2 기준 초당 약 2걸음)
            if int(self.anim / math.pi) != before and self.on_step:
                self.on_step(self)                  # 발이 땅에 닿음
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
        flags = self.game.state.flags
        self.lines = [l for l in lines if l.get("speaker") != "choice"
                      and (not l.get("condition") or l["condition"] in flags)]
        if not self.lines:
            if on_done:
                on_done()
            return
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
    """모드: title(타이틀) → field(필드) ⇄ menu(메뉴) / dialogue / battle. 맵 이동은 페이드 아웃 → 교체 → 페이드 인."""

    FIELD_HINT = "WASD·방향키 이동   Z·Space 대화/조사   X·Esc 메뉴   Q/E 시점 회전   휠 확대"

    def __init__(self, map_id="verdan_edge", size=(1280, 720), start="title"):
        self.app = Ursina(title="황동의 심장 : 아스카론 연대기", size=size, development_mode=False,
                          borderless=False, vsync=True)
        check_support(self.app)          # GLSL 미지원 환경이면 셰이더 없이 그리도록
        window.color = rgb(150, 182, 210)
        window.fps_counter.enabled = False
        window.exit_button.enabled = False
        Texture.default_filtering = "mipmap"
        from pathlib import Path
        application.fonts_folder = Path(FONTS)
        Text.default_font = FONT_UI          # 기본 폰트에 한글이 없으므로 모든 Text 기본값을 나눔고딕으로
        Text.default_resolution = 1440 * Text.size
        self.story = load_json("story.json")
        from src.entities.party import GameState      # 파티 성장·인벤토리 (2D 와 공용)
        self.state = GameState(self.story)
        self.first_map = map_id
        self.battle = None
        self.listeners = []
        self.walked = 0.0
        self.encounters_enabled = True
        self.world, self.player, self.followers, self.npcs = None, None, [], []
        self.mode = "boot"
        self.event = None                 # 진행 중인 맵 이벤트 (대화 → 전투 → 대화 …)
        self.battle_cb = None
        self.fade = None
        self.banner = None
        self.input_override = None        # 자동 테스트: (x, z) 이동 입력
        window.color = color.rgb(*LIGHT["fog_color"])
        # 카메라
        self.yaw, self.yaw_goal = 35.0, 35.0
        self.pitch, self.dist = 50.0, 36.0
        self.zoom = 36.0                  # 필드에서 플레이어가 고른 카메라 거리 (휠)
        camera.fov = 30
        self.cam_target = Vec3(0, 0, 0)
        # 공용 UI
        self.bubble = Entity(model="quad", texture=tex("ui3d/bubble.png"), billboard=True, scale=0.75,
                             shader=unlit_shader, enabled=False)
        self.bubble.setTransparency(TransparencyAttrib.MAlpha)
        self.bubble.hide(0b0001)
        self.dialogue = DialogueUI(self)
        self.hint = Text(parent=camera.ui, text=self.FIELD_HINT, font=font(FONT_UI), origin=(-0.5, 0.5),
                         position=(-0.87, 0.485), scale=0.85, color=color.rgba(1, 1, 1, 0.85))
        self.hint.create_background(padding=0.012, radius=0.008, color=color.rgba(0.08, 0.06, 0.04, 0.55))
        # 알림 (보물상자·상점·여관 등): 화면 위쪽 가운데, 어두운 반투명 띠 위에 글씨
        self.toast_bg = Entity(parent=camera.ui, model=Quad(radius=0.012), y=0.3, z=-0.49, color=color.rgba(0.05, 0.04, 0.06, 0),
                               scale=(0.5, 0.08))
        self.toast = Text(parent=camera.ui, text="", origin=(0, 0), y=0.3, scale=1.15, z=-0.5,
                          color=color.rgba32(255, 236, 190))
        self.toast_t = 0.0
        from src3d.battle3d import FX
        self.field_fx = FX(tex("textures3d/fx_glow.png"))
        self.fader = Entity(parent=camera.ui, model="quad", scale=(4, 2), color=color.rgba(0, 0, 0, 0), z=-0.98)
        from src3d.menu3d import Menu3D, ShopUI, TitleUI
        self.menu = Menu3D(self)
        self.shop = ShopUI(self)
        self.title = TitleUI(self)
        self.bgm = None
        self._audio(None)
        Entity(update=self.update, input=self.input)
        if start == "title":
            self.show_title()
        else:
            self.load_map(map_id)

    # ------------------------------------------------------------ 맵 불러오기/비우기
    def unload_map(self):
        self.field_fx.clear()
        if self.world:
            self.world.destroy()
        for a in ([self.player] if self.player else []) + self.followers + self.npcs:
            a.destroy()
        self.world, self.player, self.followers, self.npcs = None, None, [], []
        self.bubble.enabled = False
        if self.banner and self.banner.root:
            destroy(self.banner.root)
        self.banner = None

    def load_map(self, map_id, pos=None, facing=None, party=True):
        """맵을 새로 짓고 파티·NPC 를 배치한다. party=False 는 타이틀 배경용 (사람 없이 풍경만)."""
        self.unload_map()
        self.world = World(map_id)
        m = self.world.m
        sx, sz = pos or m["start"]
        if pos and self.world.blocked(sx, sz):
            # 세이브 이후 맵이 바뀌어 저장 위치에 나무·바위가 생겼으면 가장 가까운 빈 자리로 (없으면 시작 지점)
            sx, sz = next(((sx + math.cos(a) * r, sz + math.sin(a) * r) for r in (1, 2, 3, 4, 6)
                           for a in (k * math.tau / 12 for k in range(12))
                           if not self.world.blocked(sx + math.cos(a) * r, sz + math.sin(a) * r)), m["start"])
        facing = facing or m.get("start_dir", "ne")
        if party:
            # 파티 (루크가 앞장서고 아이리스·제드가 뒤따름)
            self.player = Actor(self.world, "luke", sx, sz, facing, "luke")
            self.player.on_step = self.footstep
            self.followers = [Actor(self.world, "iris", sx, sz - 1.5, facing, "iris"),
                              Actor(self.world, "zed", sx, sz - 3.0, facing, "zed")]
            self.line_up()
            for n in m.get("npcs", []):
                sprite = n["sprite"]
                if not os.path.exists(os.path.join(FIELD_DIR, sprite + ".png")) and not os.path.exists(
                        os.path.join(IMG, "sprites3d", sprite + ".png")):
                    sprite = n.get("fallback", "morgan")          # 아직 그림이 없는 NPC
                a = Actor(self.world, sprite, n["pos"][0], n["pos"][1], n.get("dir", "se"), n["id"])
                a.data = n
                a.talks = 0
                self.npcs.append(a)
                self.world.colliders.append((a.x, a.z, 0.6))
            for c in m.get("chests", []):
                ch = Chest(self.world, c, f"chest:{m['id']}:{c['id']}" in self.state.flags)
                self.world.chests.append(ch)
                self.world.colliders.append((ch.x, ch.z, 0.75))
            for a_ in m.get("altars", []):
                al = Altar(self.world, a_)
                self.world.altars.append(al)
                self.world.colliders.append((al.x, al.z, 1.5))
            self.refresh_weapons()
            self.state.map_id = m["id"]
            self.state.pos = (sx, sz)
            self.banner = Banner(m["name"], m.get("subtitle", ""))
            self.mode = "field"
            self.hint.text = self.FIELD_HINT
            self.hint.enabled = True
            self.cam_target = Vec3(sx, self.world.h(sx, sz) + 0.9, sz)
            self.pitch, self.dist = 50.0, self.zoom
            self.set_bgm(m.get("bgm"), fade=0.6)
            self.walked = 0.0
            self.inside_exit = True        # 도착 지점에서 곧바로 다시 나가지 않게, 출구 밖으로 한 번 나가야 작동
            self.update_camera(1.0)
            intro = m.get("intro_scene")
            if intro and f"scene:{intro}" not in self.state.flags:
                self.play_scene(intro)

    def refresh_weapons(self):
        """장착 무기를 필드·전투 캐릭터 그림에 반영"""
        if not self.player:
            return
        for actor, ch in zip([self.player] + self.followers, self.state.party):
            actor.set_weapon(ch.equip.get("weapon"))

    def footstep(self, actor):
        """발이 땅에 닿을 때: 작은 발소리 + 흙먼지"""
        self.sfx("step", 0.22)
        on_path = float(terrain.path_distance(self.world.m, actor.x, actor.z)) < 0.5
        self.field_fx.dust(Vec3(actor.x, self.world.h(actor.x, actor.z) + 0.05, actor.z),
                           (0.62, 0.52, 0.38) if on_path else (0.55, 0.62, 0.42))

    def line_up(self):
        """동료를 루크 뒤로 한 줄 세운다"""
        p = self.player
        r = math.radians(self.yaw)
        bx, bz = -math.sin(r), -math.cos(r)            # 화면 아래쪽(카메라 쪽)
        self.trail = [(p.x + bx * i * 0.125, p.z + bz * i * 0.125) for i in range(160)]
        for i, f in enumerate(self.followers):
            f.x, f.z = self.trail[(i + 1) * 12]
            f.sync()

    def fade_to(self, action, dur=0.4):
        """화면을 검게 덮은 뒤 action 실행, 다시 밝힌다"""
        if self.fade:
            return
        self.fade = {"t": 0.0, "dur": dur, "action": action, "done": False}

    def _update_fade(self, dt):
        f = self.fade
        if not f:
            return
        f["t"] += dt
        if not f["done"]:
            a = min(1.0, f["t"] / f["dur"])
            if a >= 1.0:
                f["done"] = True
                f["t"] = 0.0
                f["action"]()
        else:
            a = max(0.0, 1 - f["t"] / f["dur"])
            if a <= 0:
                self.fade = None
        self.fader.color = color.rgba(0, 0, 0, a)

    # ------------------------------------------------------------ 타이틀/새 게임/세이브
    def show_title(self):
        self.mode = "title"
        self.dialogue.root.enabled = False
        self.menu.close()
        self.load_map(self.first_map, party=False)
        self.hint.enabled = False
        self.pitch, self.dist = 34.0, 72.0
        self.set_bgm("title", fade=0.8)
        self.title.open()

    def new_game(self):
        from src.entities.party import GameState
        self.title.close()

        def go():
            self.state = GameState(self.story)
            self.load_map(self.first_map)
        self.fade_to(go, 0.6)

    def save_slot(self, slot):
        from src.systems import save
        st = self.state
        st.pos = (round(self.player.x, 2), round(self.player.z, 2))
        st.dir = self.player.facing
        return save.save(slot, st)

    def load_slot(self, slot):
        from src.entities.party import GameState
        from src.systems import save
        d = save.read(slot)
        if not d or not save.map_exists_3d(d["map_id"]):
            return False
        self.title.close()
        self.menu.close()

        def go():
            self.battle = None
            self.event = None
            self.dialogue.root.enabled = False
            self.state = save.apply_dict(GameState(self.story), d)
            self.load_map(d["map_id"], tuple(d["pos"]), d.get("dir"))
        self.fade_to(go, 0.5)
        return True

    def to_title(self):
        self.menu.close()
        self.fade_to(self.show_title, 0.5)

    def show_toast(self, text, dur=1.6):
        self.toast.text = text
        self.toast_t = dur
        lines = text.split("\n")
        self.toast_bg.scale = (max(0.3, max(len(x) for x in lines) * 0.026 + 0.08), 0.045 * len(lines) + 0.04)

    # ------------------------------------------------------------ 이벤트 (스토리 장면·보스전)
    def scene_lines(self, scene_id):
        sc = next((s for c in self.story["chapters"] for s in c["scenes"] if s["id"] == scene_id), None)
        return sc["dialogue"] if sc else []

    def play_scene(self, scene_id, on_done=None):
        def done():
            self.state.flags.add(f"scene:{scene_id}")
            if on_done:
                on_done()
        self.dialogue.open(self.scene_lines(scene_id), done)

    def run_event(self, ev):
        self.event = {"ev": ev, "i": 0}
        self.input_override = None
        self._next_step()

    def _next_step(self):
        e = self.event
        if e is None:
            return
        steps = e["ev"]["steps"]
        if e["i"] >= len(steps):
            self.state.flags.add(f"event:{e['ev']['id']}")
            self.event = None
            return
        st = steps[e["i"]]
        e["i"] += 1
        if "scene" in st:
            if f"scene:{st['scene']}" in self.state.flags and not st.get("repeat"):
                return self._next_step()
            self.play_scene(st["scene"], self._next_step)
        elif "battle" in st:
            self.battle_cb = self._event_battle_end
            self.start_battle(st["battle"], st.get("boss", False))
        elif "lines" in st:
            self.dialogue.open(st["lines"], self._next_step)
        elif "give" in st:
            from src.systems import equipment
            got = [equipment.give(self.state, iid) for iid in st["give"]]
            names = [g["name"] for g in got if g]
            self.sfx("levelup")
            self.show_toast("획득!\n" + "\n".join(names), 4.0)
            self.refresh_weapons()
            self._next_step()
        elif "flag" in st:
            self.state.flags.add(st["flag"])
            self._next_step()
        elif "banner" in st:
            self.banner = Banner(*st["banner"])
            self._next_step()
        else:
            self._next_step()

    def _event_battle_end(self, kind):
        if kind == "victory":
            self._next_step()
        else:
            self.event = None             # 패배/도주: 이벤트를 처음부터 다시 (본 장면은 건너뜀)

    def requires_ok(self, ev):
        return all(r in self.state.flags for r in ev.get("requires", []))

    def check_triggers(self):
        """출구·구역 이벤트"""
        p = self.player
        m = self.world.m
        in_exit = None
        for ex in m.get("exits", []):
            if math.hypot(p.x - ex["pos"][0], p.z - ex["pos"][1]) < ex.get("r", 2.5):
                in_exit = ex
        if in_exit and not self.inside_exit:
            self.inside_exit = True
            self.input_override = None
            self.sfx("sfx_door")
            def go(ex=in_exit):
                self.load_map(ex["to"], tuple(ex["spawn"]), ex.get("dir"))
                if ex.get("travel"):
                    self.show_toast(ex["travel"], 2.6)
            self.fade_to(go)
            return True
        self.inside_exit = bool(in_exit)
        near_any = False
        for ev in m.get("events", []):
            if ev.get("type") != "zone" or f"event:{ev['id']}" in self.state.flags or not self.requires_ok(ev):
                continue
            if math.hypot(p.x - ev["pos"][0], p.z - ev["pos"][1]) < ev.get("r", 2.5):
                need = ev.get("requires_items", [])
                have = [k for k in need if k in self.state.key_items]
                if len(have) < len(need):                 # 열쇠 아이템이 모자라면 안내만 (구역에 들어올 때 한 번)
                    near_any = True
                    if not getattr(self, "_hinted", False):
                        self._hinted = True
                        self.show_toast(ev.get("missing_text", "무언가가 더 필요하다…").format(have=len(have), need=len(need)), 3.0)
                    continue
                self.run_event(ev)
                return True
        if not near_any:
            self._hinted = False
        return False

    @property
    def busy(self):
        return (self.mode != "field" or self.dialogue.active or self.event is not None or self.fade is not None
                or self.menu.active or self.shop.active)

    # ------------------------------------------------------------ 데이터
    def speaker_name(self, sid):
        meta = self.story["meta"]["speaker_ids"]
        if sid in meta:
            return meta[sid]
        for town in self.story["npc_dialogues"].values():
            for n in town["npcs"]:
                if n["id"] == sid:
                    return n["name"]
        if self.world:                       # 맵에만 있는 NPC (여관 주인·대장장이 등)
            for n in self.world.m.get("npcs", []):
                if n["id"] == sid and n.get("name"):
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
        f = getattr(self, "bgm_fade", 0.0)
        step = dt / f if f else 1.0
        if self.bgm is not None:
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

    def sfx(self, name, volume=0.6):
        try:
            if name not in self._sfx:
                self._sfx[name] = self.app.loader.loadSfx(
                    Filename.fromOsSpecific(os.path.join(ROOT, "assets", "sfx", name.replace("sfx_", "") + ".ogg")))
            self._sfx[name].setVolume(volume)
            self._sfx[name].play()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ 입력/갱신
    def emit(self, event, **data):
        for cb in self.listeners:
            cb(event, data)

    def input(self, key):
        if self.fade:
            return
        if self.mode == "title":
            self.title.input(key)
            return
        if self.battle:
            self.battle.input(key)
            return
        if self.dialogue.active:
            if key in ("z", "space", "enter", "left mouse down"):
                self.dialogue.advance()
            return
        if self.menu.active:
            self.menu.input(key)
            return
        if self.shop.active:
            self.shop.input(key)
            return
        if self.event is not None:
            return
        if key in ("z", "space", "enter"):
            self.try_talk()
        elif key in ("x", "escape", "tab"):
            self.input_override = None
            self.sfx("sfx_menu")
            self.menu.open()
        elif key == "q":
            self.yaw_goal -= 45
        elif key == "e":
            self.yaw_goal += 45
        elif key == "scroll up":
            self.zoom = max(20, self.zoom - 3)
        elif key == "scroll down":
            self.zoom = min(50, self.zoom + 3)

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
        self._update_fade(dt)
        self.clock = getattr(self, "clock", 0.0) + dt
        if self.toast_t > 0:
            self.toast_t -= dt
            self.toast.alpha = min(1.0, self.toast_t * 3)
            self.toast_bg.color = color.rgba(0.05, 0.04, 0.06, 0.78 * min(1.0, self.toast_t * 3))
        if self.mode == "title":
            self.title.update(dt)
            self.update_camera(dt)
            return
        if self.world is None or self.player is None:
            return
        self.dialogue.update(dt)
        self.menu.update(dt)
        if self.banner:
            self.banner.update(dt)
        self.field_fx.update(dt)
        if self.battle:
            self.battle.update(dt)
            self.update_camera(dt)
            return
        if not self.menu.active:
            self.state.playtime += dt
        speed = 5.2
        vx, vz = (0.0, 0.0) if self.busy else self.move_vector()
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
            self.walked += speed * dt
            if self.check_triggers() or self.check_encounter(speed * dt):
                return
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
        chest = self.nearest_chest()
        self.bubble.enabled = bool(near or chest) and not self.busy
        if chest and (not near or math.hypot(chest.x - p.x, chest.z - p.z) < 1.4):
            self.bubble.position = (chest.x, self.world.h(chest.x, chest.z) + 1.6 + math.sin(self.clock * 4) * 0.08, chest.z)
        elif near:
            self.bubble.position = (near.x, self.world.h(near.x, near.z) + near.h + 0.55 + math.sin(self.clock * 4) * 0.08,
                                    near.z)
        self.update_props(dt)
        self.update_camera(dt)

    def update_props(self, dt):
        """상자 뚜껑, 반짝임, 굴뚝 연기, 제단 홈"""
        w = self.world
        self._prop_t = getattr(self, "_prop_t", 0.0) + dt
        tick = self._prop_t > 0.22
        if tick:
            self._prop_t = 0.0
        for c in w.chests:
            if c.opened and c.t < 1:
                c.t = min(1.0, c.t + dt * 2.2)
                c.sync()
            elif not c.opened and tick and random.random() < 0.6:
                self.field_fx.particle(Vec3(c.x + random.uniform(-0.5, 0.5), w.h(c.x, c.z) + random.uniform(0.6, 1.1),
                                            c.z + random.uniform(-0.4, 0.4)), (0, 0.6, 0), 0.7, 0.14,
                                       color.rgb(1.0, 0.88, 0.45))
        if tick:
            for ch in w.chimneys:
                self.field_fx.particle(ch + Vec3(random.uniform(-0.15, 0.15), 0, random.uniform(-0.15, 0.15)),
                                       (random.uniform(-0.1, 0.3), random.uniform(0.8, 1.3), random.uniform(-0.1, 0.2)),
                                       random.uniform(2.2, 3.0), random.uniform(0.5, 0.7),
                                       color.rgba(0.55, 0.55, 0.58, 0.45), grow=1.8, additive=False)
        for a in w.altars:
            a.set_lit(sum(1 for k in a.data.get("keys", []) if k in self.state.key_items))

    def update_camera(self, dt):
        if self.mode == "title":           # 타이틀: 숲 위를 천천히 도는 카메라
            self.yaw_goal += dt * 4
            self.yaw = self.yaw_goal
            goal = Vec3(0, self.world.h(0, 0) + 1.0, 0) if self.world else Vec3(0, 0, 0)
            self.cam_target = goal
            r, pr = math.radians(self.yaw), math.radians(self.pitch)
            hd = math.cos(pr) * self.dist
            camera.position = goal + Vec3(-math.sin(r) * hd, math.sin(pr) * self.dist, -math.cos(r) * hd)
            camera.look_at(goal)
            return
        self.yaw = lerp(self.yaw, self.yaw_goal, min(1, dt * 6))
        p = self.player
        goal = Vec3(p.x, self.world.h(p.x, p.z) + 0.9, p.z)
        pitch_goal, dist_goal = 50.0, self.zoom
        if self.battle:
            goal, pitch_goal, dist_goal = self.battle.camera_goal()
        self.pitch = lerp(self.pitch, pitch_goal, min(1, dt * 3))
        self.dist = lerp(self.dist, dist_goal, min(1, dt * 3))
        self.cam_target = lerp(self.cam_target, goal, min(1, dt * (3 if self.battle else 6)))
        r, pr = math.radians(self.yaw), math.radians(self.pitch)
        hd = math.cos(pr) * self.dist
        camera.position = self.cam_target + Vec3(-math.sin(r) * hd, math.sin(pr) * self.dist, -math.cos(r) * hd)
        camera.look_at(self.cam_target)
        if self.battle:                       # 타격감: 카메라 흔들림
            camera.position += self.battle.shake_offset()

    # ------------------------------------------------------------ 전투
    def check_encounter(self, meters):
        enc = self.world.m.get("encounters")
        if not enc or not self.encounters_enabled or self.walked < enc.get("min_meters", 12):
            return False
        sx, sz = self.world.m["start"]
        if math.hypot(self.player.x - sx, self.player.z - sz) < enc.get("safe_radius", 0):
            return False
        if random.random() < enc.get("chance_per_meter", 0.02) * meters:
            from src.datafiles import load_json as lj
            table = lj("battle.json")["encounters"][enc["table"]]
            group = random.choices(table, weights=[g["weight"] for g in table])[0]
            self.start_battle(group["enemies"])
            return True
        return False

    def battle_spot(self):
        """전투 자리: 플레이어 근처에서 카메라와 전투 사이를 가리는 나무·덤불이 가장 적은 곳"""
        p = self.player
        r = math.radians(self.yaw)
        fx, fz = math.sin(r), math.cos(r)              # 화면 안쪽
        rx, rz = math.cos(r), -math.sin(r)             # 화면 오른쪽
        cols = list(self.world.colliders)
        for rx, rz, hw, hd in getattr(self.world, "rects", []):     # 건물은 크고 높아 더 넓게 가린다
            cols.append((rx, rz, max(hw, hd) + 3.0))
        best, best_score = (p.x, p.z), None
        rng_ = range(-14, 15, 2) if getattr(self.world, "rects", None) else range(-8, 9, 2)
        for dx in rng_:
            for dz in rng_:
                cx, cz = p.x + dx, p.z + dz
                if self.world.blocked(cx, cz, 1.2) or abs(cx) > self.world.half - 10 or abs(cz) > self.world.half - 10:
                    continue
                score = math.hypot(dx, dz) * 0.15
                for ox, oz, orad in cols:
                    vx, vz = ox - cx, oz - cz
                    b = -(vx * fx + vz * fz)               # 카메라 쪽으로 얼마나
                    lat = abs(vx * rx + vz * rz)
                    if -4.5 < b < 10 and lat < 4.2 + orad:
                        score += 3.0 if b > 0 else 1.5     # 카메라와 전투 사이 / 전투 대열 자리 위
                if best_score is None or score < best_score:
                    best, best_score = (cx, cz), score
        return best

    def start_battle(self, enemy_ids, boss=False):
        from src3d.battle3d import Battle3D
        self.walked = 0.0
        self.input_override = None
        self.menu.close()
        self.emit("encounter", enemies=enemy_ids)
        self.hint.enabled = False
        self.battle = Battle3D(self, enemy_ids, boss, on_end=self.end_battle)
        self.emit("battle_start", enemies=enemy_ids)

    def end_battle(self, kind):
        self.battle = None
        self.hint.enabled = True
        p = self.player
        if kind == "defeat":
            for c in self.state.party:
                c.full_heal()
            p.x, p.z = self.world.m["start"]
            self.show_toast("정신을 차려 보니 숲 입구였다…", 2.4)
        # 동료를 다시 루크 뒤로 줄 세우고 NPC 표시 복구
        self.line_up()
        for n in self.npcs:
            n.set_visible(True)
        self.set_bgm(self.world.m.get("bgm"), fade=0.8)
        self.emit("battle_end", result=kind)
        cb, self.battle_cb = self.battle_cb, None
        if cb:
            cb(kind)

    def stop_bgm(self):
        if self.bgm is not None:
            self.fading.append([self.bgm, self.bgm.getVolume()])
            self.bgm_fade = 0.5
        self.bgm, self.bgm_name = None, None

    def nearest_npc(self, reach=2.9):
        p = self.player
        best, bd = None, reach
        for n in self.npcs:
            d = math.hypot(n.x - p.x, n.z - p.z)
            if d < bd:
                best, bd = n, d
        return best

    def nearest_chest(self, reach=1.9):
        p = self.player
        best, bd = None, reach
        for c in self.world.chests:
            dd = math.hypot(c.x - p.x, c.z - p.z)
            if not c.opened and dd < bd:
                best, bd = c, dd
        return best

    def open_chest(self, c):
        from src.systems import equipment
        c.opened = True
        self.state.flags.add(f"chest:{self.world.m['id']}:{c.data['id']}")
        self.sfx("levelup", 0.7)
        names = []
        for iid in c.data.get("items", []):
            g = equipment.give(self.state, iid)
            if g:
                names.append(g["name"])
        if c.data.get("gold"):
            self.state.gold += c.data["gold"]
            names.append(f"{c.data['gold']} 골드")
        top = Vec3(c.x, self.world.h(c.x, c.z) + 0.9, c.z)
        self.field_fx.burst(top, 40, color.rgb(1.0, 0.85, 0.4), (1.5, 4.5), up=2.5, grav=4)
        self.field_fx.pillar(top - Vec3(0, 0.8, 0), color.rgb(1.0, 0.9, 0.55), 3.0, 20)
        self.show_toast("보물상자를 열었다!\n" + "\n".join(f"「{x}」을(를) 얻었다" for x in names), 3.6)

    def try_talk(self):
        c = self.nearest_chest()
        if c and (not self.nearest_npc() or math.hypot(c.x - self.player.x, c.z - self.player.z) < 1.4):
            self.player.face_vector(c.x - self.player.x, c.z - self.player.z, self.yaw)
            self.open_chest(c)
            return
        n = self.nearest_npc()
        if not n:
            return
        d = n.data
        if d.get("shop") or d.get("inn"):                 # 상점 주인·여관 주인
            n.face_vector(self.player.x - n.x, self.player.z - n.z, self.yaw)
            self.player.face_vector(n.x - self.player.x, n.z - self.player.z, self.yaw)
            self.sfx("sfx_confirm")
            greet = d.get("greeting")
            then = (lambda: self.shop.open(d["shop"])) if d.get("shop") else self.shop.open_inn
            if greet:
                self.dialogue.open([{"speaker": d["id"], "text": greet}], then)
            else:
                then()
            return
        # 서로 마주 보기
        n.face_vector(self.player.x - n.x, self.player.z - n.z, self.yaw)
        self.player.face_vector(n.x - self.player.x, n.z - self.player.z, self.yaw)
        for ev in self.world.m.get("events", []):       # 이 NPC 에게 걸린 스토리 이벤트가 먼저
            if (ev.get("type") == "talk" and ev.get("npc") == d["id"] and f"event:{ev['id']}" not in self.state.flags
                    and self.requires_ok(ev)):
                self.sfx("sfx_confirm")
                self.run_event(ev)
                return
        town = self.story["npc_dialogues"].get(d["town"], {"npcs": []})
        prof = next((x for x in town["npcs"] if x["id"] == d["id"]), None)
        pool = []
        for k in d.get("keys", ["default"]):
            pool += (prof or {}).get("dialogues", {}).get(k, [])
        if not pool:
            return
        line = pool[n.talks % len(pool)]
        n.talks += 1
        self.sfx("sfx_confirm")
        self.dialogue.open([{"speaker": d["id"], "text": line}])

    def run(self):
        self.app.run()
