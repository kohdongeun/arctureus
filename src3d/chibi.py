"""3D SD(치비) 캐릭터: 코드로 짓는 저폴리 인형 + 뼈대 애니메이션.

- 몸: 머리(큰 구) · 머리카락(스타일별) · 얼굴(그린 텍스처를 구면에 입힘, 눈 깜빡임) · 몸통 · 팔(위팔/아래팔/손) ·
  다리(허벅지/정강이/신발) · 옷(치마·코트 자락·앞치마·망토·갑옷 조각) · 장신구(고글·스카프·외눈안경·기계 매)
- 툰 셰이더 + 뒤집은 껍질 외곽선으로 애니메이션 느낌
- 방향: 몸 전체가 이동 방향으로 부드럽게 돌아서므로 옆모습·뒷모습이 그대로 보인다
- 걷기: 허벅지·정강이(무릎 굽힘)·팔을 번갈아 흔들고 몸이 출렁임
- 전투: Motion 채널(lean/hop/arm/cast/down/off/flash)을 받아 휘두르기·시전·피격·쓰러짐 자세
- 무기: 무기 그림(1024x256)을 손에 X 자로 교차한 두 장의 판으로 붙인다 (어느 각도에서도 보임)

src3d/game.py 의 Actor 와 같은 속성·메서드를 가져 필드·전투 코드가 그대로 쓴다.
"""
from __future__ import annotations

import math
import random

from panda3d.core import TransparencyAttrib
from PIL import Image, ImageDraw, ImageFilter
from ursina import Entity, Mesh, Texture, Vec3, color, destroy

from src3d.shaders import toon_shader, unlit_shader

HEIGHT = 1.85


# ====================================================================== 메시
_geo = {}


def _sphere_geo(lat=10, lon=14, lat0=0.0, lat1=math.pi, lon0=0.0, lon1=math.tau):
    key = ("s", lat, lon, lat0, lat1, lon0, lon1)
    if key not in _geo:
        v, n, uv, t = [], [], [], []
        for i in range(lat + 1):
            th = lat0 + (lat1 - lat0) * i / lat
            for j in range(lon + 1):
                ph = lon0 + (lon1 - lon0) * j / lon
                p = (math.sin(th) * math.cos(ph), math.cos(th), math.sin(th) * math.sin(ph))
                v.append(p)
                n.append(p)
                uv.append((j / lon, 1 - i / lat))
        for i in range(lat):
            for j in range(lon):
                a, b = i * (lon + 1) + j, i * (lon + 1) + j + 1
                c, d = a + lon + 1, b + lon + 1
                t += [a, c, b, b, c, d]
        _geo[key] = (v, n, uv, t)
    return _geo[key]


def _frustum_geo(r0, r1, seg=12, cap=True):
    """아래 반지름 r0 (y=0) → 위 반지름 r1 (y=1) 원뿔대"""
    key = ("f", r0, r1, seg, cap)
    if key not in _geo:
        v, n, uv, t = [], [], [], []
        slope = r0 - r1
        for k in range(seg + 1):
            a = math.tau * k / seg
            ca, sa = math.cos(a), math.sin(a)
            nn = Vec3(ca, slope, sa).normalized()
            v += [(ca * r0, 0, sa * r0), (ca * r1, 1, sa * r1)]
            n += [tuple(nn), tuple(nn)]
            uv += [(k / seg, 0), (k / seg, 1)]
        for k in range(seg):
            a, b, c, d = 2 * k, 2 * k + 1, 2 * k + 2, 2 * k + 3
            t += [a, b, c, c, b, d]
        if cap:
            for y, r, s in ((0, r0, -1), (1, r1, 1)):
                ci = len(v)
                v.append((0, y, 0))
                n.append((0, s, 0))
                uv.append((0.5, 0.5))
                for k in range(seg + 1):
                    a = math.tau * k / seg
                    v.append((math.cos(a) * r, y, math.sin(a) * r))
                    n.append((0, s, 0))
                    uv.append((0.5, 0.5))
                for k in range(seg):
                    if s > 0:
                        t += [ci, ci + 2 + k, ci + 1 + k]
                    else:
                        t += [ci, ci + 1 + k, ci + 2 + k]
        _geo[key] = (v, n, uv, t)
    return _geo[key]


def _box_geo():
    if "box" not in _geo:
        v, n, uv, t = [], [], [], []
        faces = [((0, 0, -1), (-1, 0, 0), (0, 1, 0)), ((0, 0, 1), (1, 0, 0), (0, 1, 0)), ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
                 ((1, 0, 0), (0, 0, -1), (0, 1, 0)), ((0, 1, 0), (1, 0, 0), (0, 0, 1)), ((0, -1, 0), (1, 0, 0), (0, 0, -1))]
        for nn, u, w in faces:
            i = len(v)
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                v.append(tuple(0.5 * (nn[k] + a * u[k] * -1 + b * w[k]) for k in range(3)))
                n.append(nn)
                uv.append(((a + 1) / 2, (b + 1) / 2))
            t += [i, i + 1, i + 2, i, i + 2, i + 3]
        _geo["box"] = (v, n, uv, t)
    return _geo["box"]


def _torus_geo(R=1.0, r=0.25, seg=16, sides=8):
    key = ("t", R, r, seg, sides)
    if key not in _geo:
        v, n, uv, t = [], [], [], []
        for i in range(seg + 1):
            a = math.tau * i / seg
            for j in range(sides + 1):
                b = math.tau * j / sides
                cx, cz = math.cos(a), math.sin(a)
                v.append(((R + r * math.cos(b)) * cx, r * math.sin(b), (R + r * math.cos(b)) * cz))
                n.append((math.cos(b) * cx, math.sin(b), math.cos(b) * cz))
                uv.append((i / seg, j / sides))
        for i in range(seg):
            for j in range(sides):
                a = i * (sides + 1) + j
                b, c, d = a + 1, a + sides + 1, a + sides + 2
                t += [a, b, c, c, b, d]
        _geo[key] = (v, n, uv, t)
    return _geo[key]


def _mesh(geo):
    v, n, uv, t = geo
    return Mesh(vertices=v, normals=n, uvs=uv, triangles=t, static=True)


def _flip_winding(geo):
    v, n, uv, t = geo
    t2 = []
    for i in range(0, len(t), 3):
        t2 += [t[i], t[i + 2], t[i + 1]]
    return v, n, uv, t2


# ====================================================================== 얼굴 텍스처
FACE_LON = 72          # 얼굴 텍스처가 덮는 범위: 가로 ±72°, 세로 -48°(턱) ~ +34°(이마)
FACE_LAT0, FACE_LAT1 = -48, 34


def _face_xy(lon, lat, n=512):
    u = (lon + FACE_LON) / (2 * FACE_LON)
    v = (lat - FACE_LAT0) / (FACE_LAT1 - FACE_LAT0)
    return u * n, (1 - v) * n


def draw_face(spec, closed=False, n=512):
    """눈·눈썹·입·볼터치 (투명 배경)"""
    f = spec.get("face", {})
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    style = f.get("eyes", "normal")
    iris = tuple(f.get("iris", (90, 60, 40)))
    sep = f.get("sep", 24)
    elat = f.get("lat", -3)
    ink = (40, 26, 26, 255)
    for side in (-1, 1):
        cx, cy = _face_xy(side * sep, elat, n)
        ew, eh = f.get("size", (66, 84))
        if style == "sharp":
            eh *= 0.72
        if style == "lazy":
            eh *= 0.86
        if closed or style == "kind":
            d.arc([cx - ew * 0.55, cy - eh * 0.25, cx + ew * 0.55, cy + eh * 0.35], 200, 340, fill=ink, width=7)
        else:
            d.ellipse([cx - ew / 2, cy - eh / 2, cx + ew / 2, cy + eh / 2], fill=(255, 255, 255, 255))
            ix = cx + side * -3
            d.ellipse([ix - ew * 0.36, cy - eh * 0.4, ix + ew * 0.36, cy + eh * 0.46], fill=iris + (255,))
            dark = tuple(int(c * 0.45) for c in iris)
            d.ellipse([ix - ew * 0.36, cy - eh * 0.4, ix + ew * 0.36, cy - eh * 0.02], fill=dark + (255,))
            d.ellipse([ix - ew * 0.16, cy - eh * 0.12, ix + ew * 0.16, cy + eh * 0.2], fill=(20, 14, 16, 255))
            d.ellipse([ix - ew * 0.3, cy - eh * 0.32, ix - ew * 0.04, cy - eh * 0.06], fill=(255, 255, 255, 255))
            d.ellipse([ix + ew * 0.1, cy + eh * 0.12, ix + ew * 0.24, cy + eh * 0.26], fill=(255, 255, 255, 230))
            # 윗눈꺼풀: 나른한 눈(lazy)·날카로운 눈(sharp)은 피부색으로 위를 덮고, 큰 눈은 속눈썹 곡선만
            skin = tuple(spec.get("skin", (255, 222, 196))) + (255,)
            lid = {"lazy": 0.05, "sharp": -0.12}.get(style)
            if lid is not None:
                d.polygon([(cx - ew * 0.62, cy - eh * 0.7), (cx + ew * 0.62, cy - eh * 0.7),
                           (cx + ew * 0.62, cy + eh * lid + (side * 4 if style == "sharp" else 0)),
                           (cx - ew * 0.62, cy + eh * lid - (side * 4 if style == "sharp" else 0))], fill=skin)
                d.line([(cx - ew * 0.58, cy + eh * lid - (side * 4 if style == "sharp" else 0)),
                        (cx + ew * 0.58, cy + eh * lid + (side * 4 if style == "sharp" else 0))], fill=ink, width=9)
            else:
                d.arc([cx - ew / 2 - 3, cy - eh / 2 - 3, cx + ew / 2 + 3, cy + eh / 2 + 3], 195, 345, fill=ink, width=10)
            d.line([(cx + side * ew * 0.48, cy - eh * (0.32 if lid is None else -lid)),
                    (cx + side * ew * 0.66, cy - eh * (0.46 if lid is None else -lid + 0.12))], fill=ink, width=6)
        # 눈썹
        by = cy - eh * (0.85 if style != "lazy" else 0.62)
        tilt = {"sharp": 10, "lazy": -4, "kind": -6}.get(style, 0)
        d.line([(cx - ew * 0.45, by + side * tilt * 0.5 * -1 + (tilt if side > 0 else 0)),
                (cx + ew * 0.45, by + (tilt if side < 0 else 0))], fill=tuple(f.get("brow", (60, 36, 28))) + (255,), width=7)
        if f.get("blush", True):
            bx, byy = _face_xy(side * (sep + 10), elat - 17, n)
            d.ellipse([bx - 30, byy - 12, bx + 30, byy + 12], fill=(255, 140, 140, 90))
    if f.get("monocle"):
        cx, cy = _face_xy(-sep, elat, n)
        lens = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(lens).ellipse([cx - 34, cy - 34, cx + 34, cy + 34], fill=(160, 225, 255, 70))
        img.alpha_composite(lens)
        d = ImageDraw.Draw(img)
        d.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], outline=(200, 150, 60, 255), width=9)
        d.line([(cx - 38, cy + 10), (cx - 70, cy + 90)], fill=(200, 150, 60, 255), width=4)
    # 입
    mx, my = _face_xy(0, -25, n)
    mouth = f.get("mouth", "smile")
    if mouth == "smirk":
        d.line([(mx - 18, my + 4), (mx + 4, my + 2), (mx + 20, my - 8)], fill=ink, width=6, joint="curve")
    elif mouth == "open":
        d.chord([mx - 16, my - 10, mx + 16, my + 16], 0, 180, fill=(150, 50, 60, 255), outline=ink, width=4)
    elif mouth == "flat":
        d.line([(mx - 14, my), (mx + 14, my)], fill=ink, width=6)
    else:
        d.arc([mx - 18, my - 14, mx + 18, my + 8], 20, 160, fill=ink, width=6)
    if f.get("beard"):
        pass
    return img.filter(ImageFilter.SMOOTH)


_face_cache = {}


def face_textures(cid, spec):
    if cid not in _face_cache:
        _face_cache[cid] = (Texture(draw_face(spec)), Texture(draw_face(spec, closed=True)))
    return _face_cache[cid]


# ====================================================================== 캐릭터 정의
# 색은 0~255, 머리 스타일: spiky / bob / ponytail / bun / short / bald / long
SPECS = {
    "luke": {"skin": (255, 222, 196), "hair": (196, 78, 40), "hair_style": "spiky",
             "face": {"eyes": "lazy", "iris": (150, 70, 40), "brow": (150, 60, 30), "mouth": "smirk"},
             "top": (222, 104, 46), "pants": (40, 48, 72), "boots": (110, 66, 38),
             "extras": ["goggles", "breastplate", "pauldrons", "scarf", "belt"], "weapon_kind": "sword"},
    "iris": {"skin": (255, 232, 214), "hair": (238, 232, 214), "hair_style": "bob", "elf_ears": True,
             "face": {"eyes": "big", "iris": (40, 190, 180), "brow": (200, 180, 150), "mouth": "open", "size": (74, 94)},
             "top": (246, 246, 240), "skirt": (44, 150, 150), "skirt_len": 0.3, "legs": (240, 240, 245), "boots": (60, 60, 70),
             "extras": ["cape", "gear_pin", "belt_dark"], "weapon_kind": "staff"},
    "zed": {"skin": (250, 222, 200), "hair": (34, 36, 52), "hair_style": "ponytail",
            "face": {"eyes": "sharp", "iris": (90, 90, 100), "brow": (30, 30, 40), "mouth": "flat", "monocle": True},
            "top": (40, 56, 110), "coat": (40, 56, 110), "coat_len": 0.42, "pants": (30, 30, 36), "boots": (90, 60, 40),
            "extras": ["collar", "belt", "hawk"], "weapon_kind": "rifle"},
    # ---- NPC
    "elwin": {"skin": (255, 228, 205), "hair": (240, 210, 110), "hair_style": "short", "elf_ears": True,
              "face": {"eyes": "big", "iris": (60, 150, 70)}, "top": (246, 246, 236), "skirt": (60, 140, 70),
              "skirt_len": 0.2, "legs": (236, 236, 230), "boots": (150, 120, 70), "extras": ["cape_green"]},
    "mirel": {"skin": (236, 236, 240), "hair": (210, 212, 220), "hair_style": "hood", "elf_ears": True,
              "face": {"eyes": "kind", "iris": (150, 150, 170), "mouth": "flat", "blush": False},
              "top": (200, 202, 210), "skirt": (190, 192, 200), "skirt_len": 0.46, "boots": (170, 170, 180)},
    "silvaen": {"skin": (250, 230, 214), "hair": (240, 244, 240), "hair_style": "long", "elf_ears": True,
                "face": {"eyes": "kind", "iris": (90, 150, 90)}, "top": (236, 240, 230), "skirt": (80, 140, 80),
                "skirt_len": 0.5, "boots": (120, 100, 70), "extras": ["staff_hold"]},
    "morgan": {"skin": (240, 206, 180), "hair": (170, 170, 176), "hair_style": "bun",
               "face": {"eyes": "kind", "iris": (100, 80, 60), "mouth": "smirk"}, "top": (150, 110, 80),
               "pants": (100, 80, 60), "boots": (90, 60, 40), "extras": ["apron_leather", "belt"]},
    "kid_tobi": {"skin": (255, 220, 190), "hair": (110, 70, 40), "hair_style": "cap", "scale": 0.78,
                 "face": {"eyes": "big", "iris": (110, 70, 40), "mouth": "open"}, "top": (230, 230, 220),
                 "pants": (90, 100, 120), "boots": (70, 50, 40), "extras": ["overalls"]},
    "worker_hank": {"skin": (236, 196, 160), "hair": (60, 40, 30), "hair_style": "helmet", "scale": 1.05,
                    "face": {"eyes": "normal", "iris": (70, 50, 40), "mouth": "flat", "beard": True},
                    "top": (190, 140, 50), "pants": (70, 60, 50), "boots": (60, 40, 30), "extras": ["beard"]},
    "granny_bess": {"skin": (246, 214, 190), "hair": (200, 200, 205), "hair_style": "bun", "scale": 0.9,
                    "face": {"eyes": "kind", "iris": (100, 90, 80)}, "top": (90, 110, 170), "skirt": (240, 240, 236),
                    "skirt_len": 0.44, "boots": (80, 60, 50), "extras": ["apron_white", "headscarf"]},
    "guard_rookie": {"skin": (252, 222, 196), "hair": (90, 60, 40), "hair_style": "guard_helmet",
                     "face": {"eyes": "big", "iris": (80, 110, 160), "mouth": "flat"}, "top": (240, 240, 236),
                     "pants": (240, 240, 236), "boots": (90, 80, 70), "extras": ["belt", "pauldrons_gold"]},
    "innkeeper": {"skin": (255, 224, 204), "hair": (200, 70, 50), "hair_style": "bun",
                  "face": {"eyes": "big", "iris": (110, 160, 80), "mouth": "open"}, "top": (70, 140, 90),
                  "skirt": (70, 140, 90), "skirt_len": 0.4, "boots": (80, 60, 50), "extras": ["apron_white"]},
    "blacksmith": {"skin": (226, 170, 130), "hair": (30, 24, 22), "hair_style": "bald", "scale": 1.08,
                   "face": {"eyes": "sharp", "iris": (60, 40, 30), "mouth": "flat", "brow": (30, 24, 22)},
                   "top": (110, 110, 100), "pants": (40, 36, 34), "boots": (60, 40, 30),
                   "extras": ["beard_big", "apron_leather", "goggles"]},
    "torbin": {"skin": (230, 180, 140), "hair": (180, 50, 30), "hair_style": "short", "scale": 1.0,
               "face": {"eyes": "sharp", "iris": (80, 60, 40)}, "top": (200, 200, 190), "pants": (80, 60, 50),
               "boots": (60, 40, 30), "extras": ["beard_big", "belt"]},
    "lina": {"skin": (240, 236, 240), "hair": (24, 24, 30), "hair_style": "long",
             "face": {"eyes": "kind", "iris": (60, 60, 70), "mouth": "flat"}, "top": (240, 240, 244),
             "skirt": (30, 30, 34), "skirt_len": 0.36, "legs": (240, 240, 244), "boots": (30, 30, 34)},
    "cecil": {"skin": (255, 228, 210), "hair": (240, 200, 110), "hair_style": "short",
              "face": {"eyes": "sharp", "iris": (70, 120, 200), "mouth": "flat"}, "top": (240, 240, 236),
              "pants": (240, 240, 236), "boots": (200, 170, 90), "extras": ["breastplate_white", "pauldrons_gold", "cape_white"]},
    "b7": {"robot": True},
}


def macro_gap():
    """머리카락 옆·뒤 조각이 얼굴 쪽(-z, 경도 270°)을 비우는 범위: 경도 -10° ~ 190° 만 덮는다"""
    return 10


def spec_for(cid):
    return SPECS.get(cid)


# ====================================================================== 3D 캐릭터
def _rgb(c, k=1.0):
    return color.rgb(min(1, c[0] / 255 * k), min(1, c[1] / 255 * k), min(1, c[2] / 255 * k))


class _Tint:
    """전투 코드가 view.body.color 로 색을 바꾸면 3D 캐릭터 전체 틴트로 반영"""

    def __init__(self, owner):
        self._o = owner

    @property
    def color(self):
        return self._o.tint

    @color.setter
    def color(self, c):
        self._o.tint = c

    @property
    def world_position(self):
        return self._o.root.world_position


class Chibi:
    """Actor 와 같은 겉모습 인터페이스를 가진 3D 캐릭터"""
    TURN_SPEED = 720.0           # 초당 회전 각도 (도)

    def __init__(self, world, cid, x, z, facing="se", name=""):
        from src3d.game import Motion
        self.world = world
        self.cid = cid
        self.spec = SPECS[cid]
        self.x, self.z = x, z
        self.name = name
        self.facing = facing
        self.mo = Motion()
        self.moving = False
        self.anim = 0.0
        self.walk_amt = 0.0
        self.t = random.uniform(0, 6)
        self.on_step = None
        self.weapon_id = None
        self.weapon = None
        self.single = True
        self.native = "front"
        self.forward_sign = 1.0
        sc = self.spec.get("scale", 1.0)
        self.h = HEIGHT * sc
        self.w = 0.9 * sc
        self.yaw = {"se": 215, "sw": 145, "ne": 325, "nw": 35}.get(facing, 180)
        self.yaw_goal = self.yaw
        self.blink_t = random.uniform(1.5, 4)
        self.parts = []
        # 뼈대
        self.root = Entity(position=(x, world.h(x, z), z), scale=sc)
        self.tint = color.white
        self.body = _Tint(self)                     # 전투 코드 호환 (body.color = 틴트)
        self.hips = Entity(parent=self.root, y=0.5)
        self.torso = Entity(parent=self.hips)
        self.head = Entity(parent=self.torso, y=0.62)
        self.arm = {}
        self.fore = {}
        self.thigh = {}
        self.shin = {}
        if self.spec.get("robot"):
            self._build_robot()
        else:
            self._build()
        # 발밑 그림자
        from src3d.game import tex
        self.shadow = Entity(model="quad", texture=tex("textures3d/shadow.png"), rotation_x=90, scale=(0.95 * sc, 0.6 * sc),
                             color=color.rgba(1, 1, 1, 0.6), shader=unlit_shader)
        self.shadow.setTransparency(TransparencyAttrib.MAlpha)
        # 처음 바라보는 방향: 기본 카메라(35°) 기준 se/sw/ne/nw
        r = math.radians(35)
        fx, fz, rx, rz = math.sin(r), math.cos(r), math.cos(r), -math.sin(r)
        dv = {"se": (-fx + rx, -fz + rz), "sw": (-fx - rx, -fz - rz), "ne": (fx + rx, fz + rz), "nw": (fx - rx, fz - rz)}
        self.face_vector(*dv.get(facing, dv["se"]), 35)
        self.yaw = self.yaw_goal
        self.sync()

    # ------------------------------------------------------------ 부품
    def part(self, parent, geo, pos, scale, col, rot=(0, 0, 0), outline=0.035, tex=None, cull=True):
        e = Entity(parent=parent, model=_mesh(geo), position=pos, scale=scale, rotation=rot, color=_rgb(col) if col else color.white,
                   shader=toon_shader)
        if tex is not None:
            e.texture = tex
            e.set_shader_input("use_tex", 1.0)
            e.setTransparency(TransparencyAttrib.MAlpha)
        if not cull:
            e.double_sided = True
        self.parts.append(e)
        return e

    def sphere(self, parent, pos, r, col, **kw):
        return self.part(parent, _sphere_geo(), pos, _vec3(r), col, **kw)

    def limb(self, parent, length, r0, r1, col, down=True, **kw):
        """관절에서 아래(-y)로 뻗는 팔다리 (원뿔대 + 양끝 구)"""
        e = self.part(parent, _frustum_geo(r0 / max(r0, r1), r1 / max(r0, r1), 10), (0, -length if down else 0, 0),
                      (max(r0, r1), length, max(r0, r1)), col, **kw)
        self.sphere(parent, (0, -length, 0), r0 * 1.02, col, outline=0.02)
        return e

    def box(self, parent, pos, size, col, rot=(0, 0, 0), **kw):
        return self.part(parent, _box_geo(), pos, size, col, rot=rot, **kw)

    # ------------------------------------------------------------ 조립
    def _build(self):
        s = self.spec
        skin, hair = s["skin"], s["hair"]
        top = s.get("top", (200, 200, 200))
        pants = s.get("pants", s.get("legs", (60, 60, 70)))
        boots = s.get("boots", (80, 60, 40))
        legs = s.get("legs", pants)
        ex = s.get("extras", [])
        # 몸통 (위로 갈수록 넓은 달걀꼴) + 목
        self.part(self.torso, _sphere_geo(), (0, 0.24, 0), (0.25, 0.3, 0.18), top)
        self.sphere(self.torso, (0, 0.5, 0), (0.08, 0.08, 0.08), skin, outline=0)
        # 다리: 허벅지 → 정강이(무릎) → 신발
        for side in (-1, 1):
            th = Entity(parent=self.hips, position=(side * 0.1, 0.0, 0))
            self.limb(th, 0.22, 0.085, 0.095, pants)
            sh = Entity(parent=th, y=-0.22)
            self.limb(sh, 0.22, 0.075, 0.085, legs)
            self.part(sh, _sphere_geo(), (0, -0.25, -0.05), (0.1, 0.075, 0.15), boots)
            self.thigh[side], self.shin[side] = th, sh
        # 치마·코트 자락
        if s.get("skirt"):
            L = s.get("skirt_len", 0.3)
            self.part(self.hips, _frustum_geo(1.0, 0.62, 14), (0, -L + 0.04, 0), (0.3, L, 0.24), s["skirt"], cull=False)
        if s.get("coat"):
            L = s.get("coat_len", 0.4)
            self.part(self.hips, _frustum_geo(1.0, 0.7, 14), (0, -L + 0.05, 0.02), (0.29, L, 0.24), s["coat"], cull=False)
        # 팔: 어깨 → 위팔 → 팔꿈치 → 아래팔 → 손
        for side in (-1, 1):
            sh = Entity(parent=self.torso, position=(side * 0.25, 0.42, 0))
            self.sphere(sh, (0, 0, 0), 0.085, top, outline=0.02)
            self.limb(sh, 0.18, 0.07, 0.08, top)
            fo = Entity(parent=sh, y=-0.18)
            self.limb(fo, 0.16, 0.06, 0.068, top)
            self.sphere(fo, (0, -0.2, 0), 0.07, skin, outline=0.02)
            self.arm[side], self.fore[side] = sh, fo
        # 머리 (+얼굴 구면 텍스처)
        self.sphere(self.head, (0, 0, 0), 0.4, skin)
        f_open, f_closed = face_textures(self.cid, s)
        self.face_tex = (f_open, f_closed)
        geo = _sphere_geo(10, 14, math.radians(90 - FACE_LAT1), math.radians(90 - FACE_LAT0),
                          math.radians(90 - FACE_LON), math.radians(90 + FACE_LON))
        # 정면(-z)을 향하도록: 경도 90° 가 -z 쪽이 되게 회전
        self.face = self.part(self.head, geo, (0, 0, 0), 0.405, None, rot=(0, 180, 0), outline=0, tex=f_open)
        self.face.setDepthOffset(1)
        if s.get("elf_ears"):
            for side in (-1, 1):
                self.part(self.head, _frustum_geo(1.0, 0.05, 8), (side * 0.36, 0.0, 0.02), (0.07, 0.2, 0.05), skin,
                          rot=(0, 0, -side * 70))
        self._hair(s["hair_style"], hair)
        self._extras(ex, s)

    def _hair(self, style, col):
        H = self.head
        dark = tuple(int(c * 0.8) for c in col)
        if style in ("spiky", "bob", "ponytail", "short", "long", "bun", "hood", "cap", "helmet", "guard_helmet"):
            # 뒤·위를 덮는 머리 껍질 (앞얼굴은 비움)
            # 정수리 덮개 (이마 위까지) + 옆·뒤 (얼굴 쪽 -z 로 ±80° 는 비움)
            cap = (0.43, 0.44, 0.43) if style != "hood" else (0.47, 0.48, 0.47)
            low = 122 if style != "hood" else 140
            self.part(H, _sphere_geo(6, 16, 0, math.radians(56)), (0, 0.02, 0.01), cap, col, cull=False)
            self.part(H, _sphere_geo(8, 14, math.radians(56), math.radians(low), math.radians(-macro_gap()), math.radians(180 + macro_gap())),
                      (0, 0.02, 0.01), cap, col, cull=False)
            # 앞머리
            for k in range(-2, 3):
                ang = math.radians(k * 17)
                self.part(H, _sphere_geo(6, 8), (math.sin(ang) * 0.3, 0.24 - abs(k) * 0.02, -math.cos(ang) * 0.3),
                          (0.11, 0.17, 0.08), col, rot=(-25, -k * 17, 0), outline=0.02)
        if style == "spiky":
            rnd = random.Random(7)
            for i in range(14):
                yaw = rnd.uniform(-170, 170)
                pitch = rnd.uniform(-35, 55)
                d = Vec3(math.sin(math.radians(yaw)) * math.cos(math.radians(pitch)), math.sin(math.radians(pitch)) + 0.4,
                         math.cos(math.radians(yaw)) * math.cos(math.radians(pitch)))
                if d.z < -0.3 and d.y < 0.5:
                    continue
                d = d.normalized()
                pos = d * 0.34
                e = self.part(H, _frustum_geo(1.0, 0.05, 6), tuple(pos), (0.09, 0.26, 0.07), col, outline=0.02)
                e.look_at(e.world_position + Vec3(*tuple(d)) * 10, axis="up")
            for k in (-1, 1):                   # 옆으로 뻗친 머리
                e = self.part(H, _frustum_geo(1.0, 0.05, 6), (k * 0.36, 0.08, 0.05), (0.08, 0.22, 0.06), col,
                              rot=(0, 0, -k * 110), outline=0.02)
        elif style == "bob":
            for k in (-1, 1):
                self.part(H, _sphere_geo(), (k * 0.3, -0.12, 0.04), (0.16, 0.3, 0.26), col)
            self.part(H, _sphere_geo(), (0, -0.08, 0.2), (0.34, 0.3, 0.2), col)
            e = self.part(H, _frustum_geo(1.0, 0.05, 6), (0, 0.42, -0.05), (0.04, 0.22, 0.03), col, rot=(-30, 0, 0), outline=0.015)
        elif style == "ponytail":
            for k in (-1, 1):
                self.part(H, _sphere_geo(), (k * 0.3, -0.12, -0.02), (0.11, 0.28, 0.15), col)
            prev = Vec3(0, -0.05, 0.36)
            for i in range(5):
                p = prev + Vec3(0.02 * i, -0.13, 0.05 - i * 0.02)
                self.part(H, _sphere_geo(), tuple(p), (0.12 - i * 0.012, 0.16, 0.11 - i * 0.01), col, outline=0.02)
                prev = p
        elif style == "long":
            self.part(H, _sphere_geo(), (0, -0.3, 0.2), (0.36, 0.5, 0.22), col)
            for k in (-1, 1):
                self.part(H, _sphere_geo(), (k * 0.3, -0.24, 0.04), (0.12, 0.38, 0.18), col)
        elif style == "bun":
            self.sphere(H, (0, 0.38, 0.16), 0.17, dark)
        elif style == "short":
            for k in (-1, 1):
                self.part(H, _sphere_geo(), (k * 0.3, -0.06, 0.04), (0.1, 0.2, 0.18), col)
        elif style == "cap":
            self.part(H, _sphere_geo(10, 14, 0, math.radians(90)), (0, 0.06, 0), (0.45, 0.42, 0.45), (40, 40, 46), cull=False)
            self.part(H, _frustum_geo(1, 1, 16), (0, 0.06, -0.25), (0.3, 0.03, 0.25), (40, 40, 46))
        elif style in ("helmet", "guard_helmet"):
            c = (230, 180, 60) if style == "helmet" else (240, 240, 236)
            self.part(H, _sphere_geo(10, 14, 0, math.radians(95)), (0, 0.05, 0), (0.46, 0.46, 0.46), c, cull=False)
            self.part(H, _frustum_geo(1, 1, 16), (0, 0.04, 0), (0.5, 0.03, 0.5), c)
            if style == "helmet":
                self.sphere(H, (0, 0.28, -0.4), 0.07, (255, 250, 200), outline=0.015)
            else:
                self.part(H, _frustum_geo(1, 0.1, 8), (0, 0.45, 0), (0.06, 0.18, 0.06), (220, 60, 60))
        elif style == "bald":
            pass

    def _extras(self, ex, s):
        T, H = self.torso, self.head
        brass, gold = (220, 170, 70), (240, 200, 90)
        for e in ex:
            if e == "goggles":
                self.part(H, _torus_geo(1.0, 0.18), (0, 0.22, 0), (0.42, 0.42, 0.42), (70, 50, 40), rot=(-8, 0, 0), outline=0.01)
                for k in (-1, 1):
                    self.part(H, _frustum_geo(1, 1, 12), (k * 0.13, 0.3, -0.31), (0.09, 0.08, 0.09), brass, rot=(-60, 0, 0))
                    self.part(H, _sphere_geo(), (k * 0.13, 0.34, -0.36), (0.075, 0.03, 0.075), (110, 200, 200), rot=(-60, 0, 0), outline=0)
            elif e in ("breastplate", "breastplate_white"):
                c = brass if e == "breastplate" else (236, 236, 240)
                self.part(T, _sphere_geo(), (0, 0.27, -0.07), (0.22, 0.22, 0.13), c)
            elif e in ("pauldrons", "pauldrons_gold"):
                for k in (-1, 1):
                    self.part(T, _sphere_geo(8, 12, 0, math.radians(100)), (k * 0.27, 0.45, 0), (0.15, 0.13, 0.15),
                              brass if e == "pauldrons" else gold, cull=False)
            elif e == "scarf":
                self.part(T, _torus_geo(1.0, 0.35), (0, 0.5, 0), (0.16, 0.16, 0.16), (200, 50, 40))
                self.part(T, _box_geo(), (0.08, 0.36, 0.18), (0.08, 0.22, 0.03), (200, 50, 40), rot=(12, 0, 10))
            elif e in ("belt", "belt_dark"):
                self.part(T, _torus_geo(1.0, 0.12), (0, 0.04, 0), (0.25, 0.3, 0.19), (110, 70, 40) if e == "belt" else (40, 40, 44))
                self.box(T, (0, 0.04, -0.19), (0.07, 0.06, 0.02), brass)
            elif e in ("cape", "cape_green", "cape_white"):
                c = {"cape": (40, 150, 150), "cape_green": (60, 140, 70), "cape_white": (240, 240, 236)}[e]
                self.box(T, (0, 0.18, 0.19), (0.46, 0.62, 0.03), c, rot=(-8, 0, 0))
                self.part(T, _torus_geo(1.0, 0.3), (0, 0.48, 0), (0.18, 0.18, 0.18), c)
            elif e == "gear_pin":
                self.part(H, _torus_geo(1.0, 0.35, 10, 6), (0.28, 0.26, -0.18), (0.07, 0.07, 0.07), brass, rot=(80, 30, 0), outline=0.01)
            elif e == "collar":
                self.part(T, _frustum_geo(1.0, 1.2, 12), (0, 0.42, 0), (0.17, 0.12, 0.15), (240, 240, 236), cull=False)
            elif e == "hawk":
                hk = Entity(parent=self.arm[-1], position=(0, 0.13, 0))
                self.sphere(hk, (0, 0.06, 0), (0.07, 0.07, 0.1), (190, 150, 80), outline=0.015)
                self.sphere(hk, (0, 0.13, -0.06), 0.05, (200, 160, 90), outline=0.015)
                self.part(hk, _frustum_geo(1, 0.1, 6), (0, 0.13, -0.11), (0.02, 0.05, 0.02), (240, 200, 80), rot=(-90, 0, 0), outline=0)
                for k in (-1, 1):
                    self.box(hk, (k * 0.07, 0.07, 0.02), (0.02, 0.06, 0.14), (160, 120, 60), rot=(0, 0, k * 20))
            elif e == "overalls":
                self.box(T, (0, 0.14, -0.15), (0.3, 0.3, 0.05), (90, 110, 150))
            elif e in ("apron_white", "apron_leather"):
                c = (246, 246, 240) if e == "apron_white" else (110, 70, 40)
                self.box(self.hips, (0, -0.12, -0.2), (0.36, 0.42, 0.03), c, rot=(4, 0, 0))
                self.box(T, (0, 0.2, -0.17), (0.28, 0.26, 0.03), c)
            elif e == "headscarf":
                self.part(H, _sphere_geo(10, 14, 0, math.radians(100)), (0, 0.04, 0.02), (0.45, 0.45, 0.45), (170, 60, 60), cull=False)
            elif e in ("beard", "beard_big"):
                big = e == "beard_big"
                self.part(H, _sphere_geo(), (0, -0.28, -0.22), (0.26 if big else 0.2, 0.24 if big else 0.16, 0.15),
                          self.spec["hair"])
            elif e == "staff_hold":
                pass

    def _build_robot(self):
        """버려진 채굴 로봇 B-7: 상자 몸 + 둥근 외눈 + 안테나 + 피스톤 다리"""
        rust, brass = (190, 110, 60), (220, 170, 80)
        self.box(self.torso, (0, 0.25, 0), (0.6, 0.5, 0.46), rust)
        self.box(self.head, (0, -0.1, 0), (0.56, 0.4, 0.46), brass)
        self.part(self.head, _sphere_geo(), (0, -0.1, -0.23), (0.13, 0.13, 0.05), (80, 230, 255), outline=0.01)
        self.part(self.head, _frustum_geo(1, 1, 8), (0.14, 0.1, 0), (0.02, 0.25, 0.02), (90, 90, 90), outline=0)
        self.sphere(self.head, (0.14, 0.36, 0), 0.05, (240, 60, 50), outline=0.01)
        for side in (-1, 1):
            th = Entity(parent=self.hips, position=(side * 0.17, 0.0, 0))
            self.limb(th, 0.2, 0.06, 0.07, (120, 120, 126))
            sh = Entity(parent=th, y=-0.2)
            self.limb(sh, 0.2, 0.06, 0.07, (120, 120, 126))
            self.box(sh, (0, -0.24, -0.04), (0.16, 0.08, 0.24), rust)
            self.thigh[side], self.shin[side] = th, sh
            a = Entity(parent=self.torso, position=(side * 0.34, 0.42, 0))
            self.limb(a, 0.16, 0.05, 0.06, (120, 120, 126))
            f = Entity(parent=a, y=-0.16)
            self.limb(f, 0.14, 0.05, 0.06, (120, 120, 126))
            self.box(f, (0, -0.2, 0), (0.1, 0.1, 0.1), brass)
            self.arm[side], self.fore[side] = a, f
        self.face_tex = None

    # ------------------------------------------------------------ 무기
    def set_weapon(self, weapon_id):
        """무기 그림을 오른손에 X 자로 교차한 두 장의 판으로 든다"""
        if weapon_id == self.weapon_id or 1 not in self.fore:
            return
        from src3d.game import IMG, tex
        import os
        path = os.path.join(IMG, "equipment", f"{weapon_id}.png") if weapon_id else ""
        if not os.path.exists(path):
            return
        self.weapon_id = weapon_id
        if self.weapon:
            destroy(self.weapon)
        kind = self.spec.get("weapon_kind", "sword")
        L = {"sword": 1.25, "staff": 1.35, "rifle": 1.15}[kind]
        # 손에서 무기 방향: 칼은 앞으로 비스듬히 아래, 지팡이는 위로, 총은 앞으로 수평
        rot = {"sword": (-120, 0, 0), "staff": (-8, 0, 0), "rifle": (-90, 0, 0)}[kind]
        grip = {"sword": 0.07, "staff": 0.45, "rifle": 0.32}[kind]
        holder = Entity(parent=self.fore[1], position=(0, -0.2, 0), rotation=rot)
        th = L * 256 / 944
        k = 40 / 944 * L
        t = tex(path)
        for r in (0, 90):
            q = Entity(parent=holder, model="quad", texture=t, rotation=(0, r, 90), scale=(L * 1024 / 944, th),
                       position=(0, L * 1024 / 944 / 2 - k - grip * L, 0), double_sided=True, shader=unlit_shader)
            q.setTransparency(TransparencyAttrib.MAlpha)
        self.weapon = holder

    # ------------------------------------------------------------ Actor 호환
    def face_vector(self, vx, vz, cam_yaw=0.0):
        if abs(vx) < 1e-4 and abs(vz) < 1e-4:
            return
        # 모델 정면은 -z. rotation_y = θ 일 때 정면 방향 = (-sinθ, -cosθ)
        self.yaw_goal = math.degrees(math.atan2(-vx, -vz))
        r = math.radians(cam_yaw)
        right = vx * math.cos(r) - vz * math.sin(r)
        fwd = vx * math.sin(r) + vz * math.cos(r)
        is_right = right > 0 if abs(right) > 0.2 else self.facing in ("ne", "se")
        self.facing = ("ne" if is_right else "nw") if fwd > 0.15 else ("se" if is_right else "sw")

    def step(self, vx, vz, dt, cam_yaw, speed):
        self.moving = bool(vx or vz)
        if self.moving:
            self.face_vector(vx, vz, cam_yaw)
            before = int(self.anim / math.pi)
            self.anim += dt * speed * 1.45
            if int(self.anim / math.pi) != before and self.on_step:
                self.on_step(self)
        self.sync(dt)

    def make_ghost(self):
        """잔상: 지금 자세 그대로 복사한 반투명 노드"""
        from ursina import scene
        np_ = self.root.copyTo(scene)
        np_.setTransparency(TransparencyAttrib.MAlpha)
        np_.setColorScale(0.6, 0.85, 1.0, 0.45)
        np_.setDepthWrite(False)
        return np_

    def set_visible(self, on):
        self.root.enabled = self.shadow.enabled = on

    def destroy(self):
        destroy(self.root)
        destroy(self.shadow)

    @property
    def body_color(self):
        return self.root.color

    def sync(self, dt=0.0):
        self.t += dt
        mo = self.mo
        # 몸 돌리기 (가장 짧은 쪽으로)
        diff = (self.yaw_goal - self.yaw + 540) % 360 - 180
        stepv = self.TURN_SPEED * dt if dt else 360
        self.yaw += max(-stepv, min(stepv, diff))
        goal = (1.0 if self.moving else 0.0) if mo.walk is None else mo.walk
        self.walk_amt += (goal - self.walk_amt) * min(1.0, dt * 10) if dt else goal - self.walk_amt
        w = self.walk_amt
        ph = self.anim
        s = math.sin(ph)
        y = self.world.h(self.x, self.z)
        px, pz = self.x + mo.off.x, self.z + mo.off.z
        bob = abs(math.cos(ph)) * 0.05 * w
        breath = math.sin(self.t * 2.2) * 0.012 * (1 - w)
        self.root.position = (px, y + mo.hop + bob, pz)
        self.root.rotation_y = self.yaw
        sc = self.spec.get("scale", 1.0)
        self.root.scale = (sc * mo.sx, sc * mo.sy, sc * mo.sx)
        # 쓰러짐: 뒤로 눕기
        self.root.rotation_x = -80 * mo.down
        # 다리 (무릎은 발을 앞으로 내밀 때 굽힘)
        for side in (-1, 1):
            if side not in self.thigh:
                continue
            ss = s * side
            self.thigh[side].rotation_x = -34 * ss * w
            self.shin[side].rotation_x = 46 * max(0.0, ss) * w + (8 * mo.down)
        # 몸통·머리
        self.torso.rotation_x = -mo.lean * 55 + 6 * w
        self.torso.rotation_y = 7 * s * w
        self.torso.y = breath
        self.head.rotation_x = -9 - 4 * w + mo.lean * 12          # 살짝 고개를 들어 위쪽 카메라에 얼굴이 보이게
        self.head.rotation_z = 3 * math.sin(ph * 0.5) * w
        # 팔: 걸을 때 반대로 흔들기 + 전투 동작 (arm: +내리치기/-치켜들기, cast: 양팔 들기)
        for side in (-1, 1):
            if side not in self.arm:
                continue
            a = 30 * s * side * w
            fold = 18
            if side == 1:
                a += -150 * max(0.0, -mo.arm) + 60 * max(0.0, mo.arm) - 150 * mo.cast
                fold += 40 * max(0.0, -mo.arm)
            else:
                a += -110 * mo.cast
            self.arm[side].rotation_x = a
            self.arm[side].rotation_z = side * (8 + 6 * mo.cast)
            self.fore[side].rotation_x = -fold
        # 눈 깜빡임
        if getattr(self, "face_tex", None):
            self.blink_t -= dt
            if self.blink_t < 0:
                self.face.texture = self.face_tex[1]
                if self.blink_t < -0.12:
                    self.face.texture = self.face_tex[0]
                    self.blink_t = random.uniform(2.0, 5.0)
        # 틴트 (피격 붉은빛·쓰러짐 회색) + 번쩍
        tc = self.tint
        k = 1 + mo.flash * 2.5
        self.root.setColorScale(tc.r * k, tc.g * k, tc.b * k, tc.a)
        self.shadow.position = (px, self.world.h(px, pz) + 0.04, pz)
        self.shadow.scale = (0.95 * sc * (1 - bob), 0.6 * sc * (1 - bob))


def _vec3(s):
    if isinstance(s, (int, float)):
        return (s, s, s)
    return tuple(s)
