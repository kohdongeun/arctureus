"""마을 건물 (스팀펑크 벽돌집·회벽집·목조집) 을 직접 메시로 짓는다.

맵 JSON 의 "buildings":
  {"pos": [x, z], "size": [가로, 세로], "height": 벽 높이, "rot": 0|90|180|270,
   "wall": "brick"|"plaster"|"wood", "roof": "red"|"slate"|"copper", "floors": 1|2,
   "chimney": true, "pipes": true, "sign": "inn"|"item"|"weapon"}
정면(문·간판)은 회전 전 기준 -z 쪽 (기본 카메라를 향함).
같은 텍스처끼리 한 메시로 합쳐 그린다 (lit_shader).
"""
from __future__ import annotations

import math
import os

from panda3d.core import TransparencyAttrib
from ursina import Entity, Mesh, Vec3, color

from src3d.shaders import lit_shader, unlit_shader


class MeshBuilder:
    def __init__(self):
        self.parts = {}

    def quad(self, key, p0, p1, p2, p3, uv=(0, 0, 1, 1), col=(1, 1, 1, 1)):
        """p0 왼아래, p1 오른아래, p2 오른위, p3 왼위 (바깥에서 볼 때 반시계)"""
        v, u, n, t, c = self.parts.setdefault(key, ([], [], [], [], []))
        a = Vec3(*p1) - Vec3(*p0)
        b = Vec3(*p3) - Vec3(*p0)
        nn = b.cross(a).normalized()          # 왼손 좌표계(ursina): 바깥을 향하는 법선
        i = len(v)
        v += [tuple(p0), tuple(p1), tuple(p2), tuple(p3)]
        u0, v0, u1, v1 = uv
        u += [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        n += [tuple(nn)] * 4
        c += [col] * 4
        t += [i, i + 2, i + 1, i, i + 3, i + 2]

    def tri(self, key, p0, p1, p2, uv0, uv1, uv2):
        v, u, n, t, c = self.parts.setdefault(key, ([], [], [], [], []))
        a = Vec3(*p1) - Vec3(*p0)
        b = Vec3(*p2) - Vec3(*p0)
        nn = b.cross(a).normalized()          # 왼손 좌표계(ursina): 바깥을 향하는 법선
        i = len(v)
        v += [tuple(p0), tuple(p1), tuple(p2)]
        u += [uv0, uv1, uv2]
        n += [tuple(nn)] * 3
        c += [(1, 1, 1, 1)] * 3
        t += [i, i + 2, i + 1]

    def box(self, key, center, size, xf, rep=2.0, top=True):
        """축 정렬 상자 (지역 좌표 → xf 로 월드 변환). rep: 텍스처 1장이 덮는 길이(m)"""
        cx, cy, cz = center
        sx, sy, sz = size[0] / 2, size[1] / 2, size[2] / 2
        P = lambda x, y, z: xf(cx + x, cy + y, cz + z)  # noqa: E731
        faces = [((-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz), size[0], size[1]),   # 앞(-z)
                 ((sx, -sy, sz), (-sx, -sy, sz), (-sx, sy, sz), (sx, sy, sz), size[0], size[1]),       # 뒤
                 ((-sx, -sy, sz), (-sx, -sy, -sz), (-sx, sy, -sz), (-sx, sy, sz), size[2], size[1]),   # 왼
                 ((sx, -sy, -sz), (sx, -sy, sz), (sx, sy, sz), (sx, sy, -sz), size[2], size[1])]       # 오른
        if top:
            faces.append(((-sx, sy, -sz), (sx, sy, -sz), (sx, sy, sz), (-sx, sy, sz), size[0], size[2]))
        for a, b, c_, d, w, h in faces:
            self.quad(key, P(*a), P(*b), P(*c_), P(*d), (0, 0, w / rep, h / rep))

    def entities(self, textures, shader=lit_shader):
        out = []
        for key, (v, u, n, t, c) in self.parts.items():
            if not v:
                continue
            e = Entity(model=Mesh(vertices=v, uvs=u, normals=n, triangles=t, colors=[color.rgba(*x) for x in c],
                                  static=True), texture=textures(key), shader=shader, double_sided=True)
            if key in ("door", "window", "sign", "clock"):
                e.setTransparency(TransparencyAttrib.MAlpha)
            out.append(e)
        return out


def make_xf(x, z, y0, rot):
    r = math.radians(rot)
    cr, sr = math.cos(r), math.sin(r)

    def xf(lx, ly, lz):
        return (x + lx * cr + lz * sr, y0 + ly, z - lx * sr + lz * cr)
    return xf


def footprint(b):
    """월드 기준 반폭 (회전 90/270 이면 가로·세로가 바뀜)"""
    w, d = b["size"]
    if int(b.get("rot", 0)) % 180 == 90:
        w, d = d, w
    return b["pos"][0], b["pos"][1], w / 2, d / 2


def build(m, height_fn, tex_fn):
    """맵의 건물·가로등·상자 소품을 짓는다. 반환: (엔티티 목록, 충돌 사각형 목록, 굴뚝 꼭대기 위치 목록, 간판 엔티티)"""
    mb = MeshBuilder()
    rects, chimneys, extra = [], [], []
    for b in m.get("buildings", []):
        x, z = b["pos"]
        w, d = b["size"]
        H = b.get("height", 3.6)
        rot = b.get("rot", 0)
        fx, fz, hw, hd = footprint(b)
        ys = [height_fn(fx + sx * hw, fz + sz * hd) for sx in (-1, 1) for sz in (-1, 1)]
        y0 = min(ys) - 0.15
        xf = make_xf(x, z, y0, rot)
        wall = "wall_" + b.get("wall", "brick")
        # 받침돌 + 벽
        mb.box("stone", (0, 0.25, 0), (w + 0.3, 0.6, d + 0.3), xf, 1.5)
        mb.box(wall, (0, 0.5 + H / 2, 0), (w, H, d), xf, 2.4, top=False)
        # 모서리 기둥·층 띠 (목재)
        for sx in (-1, 1):
            for sz in (-1, 1):
                mb.box("wood", (sx * (w / 2 - 0.05), 0.5 + H / 2, sz * (d / 2 - 0.05)), (0.28, H, 0.28), xf, 1.0)
        if b.get("floors", 1) >= 2:
            mb.box("wood", (0, 0.5 + H * 0.5, 0), (w + 0.12, 0.22, d + 0.12), xf, 1.0, top=False)
        # 박공 지붕 (용마루는 가로 방향), 처마 0.45m
        top = 0.5 + H
        rh = min(2.4, d * 0.5)
        ov = 0.45
        roof = "roof_" + b.get("roof", "red")
        L = math.hypot(d / 2 + ov, rh + 0.25)
        for s in (-1, 1):                     # 앞·뒤 경사면 (s=-1 앞)
            a = xf(-w / 2 - ov, top - 0.25, s * (d / 2 + ov))
            bb = xf(w / 2 + ov, top - 0.25, s * (d / 2 + ov))
            c = xf(w / 2 + ov, top + rh, 0)
            dd = xf(-w / 2 - ov, top + rh, 0)
            if s < 0:
                mb.quad(roof, a, bb, c, dd, (0, 0, (w + 2 * ov) / 2.2, L / 2.2))
            else:
                mb.quad(roof, bb, a, dd, c, (0, 0, (w + 2 * ov) / 2.2, L / 2.2))
        for s in (-1, 1):                     # 박공 삼각형
            p0 = xf(s * w / 2, top, -s * d / 2)
            p1 = xf(s * w / 2, top, s * d / 2)
            p2 = xf(s * w / 2, top + rh - 0.05, 0)
            mb.tri(wall, p0, p1, p2, (0, 0), (d / 2.4, 0), (d / 4.8, rh / 2.4))
        mb.box("wood", (0, top + rh, 0), (w + 2 * ov + 0.1, 0.18, 0.3), xf, 1.0)        # 용마루
        # 굴뚝
        if b.get("chimney", True):
            cx = w * 0.28
            ch_top = top + rh + 1.1
            mb.box("wall_brick", (cx, (top + ch_top) / 2, d * 0.12), (0.75, ch_top - top, 0.75), xf, 1.2)
            mb.box("metal", (cx, ch_top + 0.08, d * 0.12), (0.9, 0.18, 0.9), xf, 1.0)
            chimneys.append(Vec3(*xf(cx, ch_top + 0.3, d * 0.12)))
        # 증기 파이프 (옆벽을 타고 올라감)
        if b.get("pipes"):
            for k, px in enumerate((w / 2 + 0.16, w / 2 + 0.16)):
                pz = -d * 0.25 + k * 0.5
                mb.box("metal", (px, 0.5 + H * 0.55, pz), (0.18, H * 1.1, 0.18), xf, 0.8)
                mb.box("metal", (px - 0.1, 0.5 + H * (0.3 + 0.35 * k), pz), (0.36, 0.26, 0.26), xf, 0.8)
        # 문 + 창문 (정면), 옆면 창문
        door_w, door_h = 1.25, 2.1
        z_front = -d / 2 - 0.03
        if b.get("door", True):
            mb.quad("door", xf(-door_w / 2, 0.5, z_front), xf(door_w / 2, 0.5, z_front),
                    xf(door_w / 2, 0.5 + door_h, z_front), xf(-door_w / 2, 0.5 + door_h, z_front))
            mb.box("wood", (0, 0.5 + door_h + 0.08, z_front - 0.02), (door_w + 0.4, 0.16, 0.12), xf, 1.0)
        floors = b.get("floors", 1)
        win = 0.95
        for f in range(floors if b.get("windows", True) else 0):
            wy = 0.5 + 1.15 + f * H / floors if floors > 1 else 0.5 + 1.25
            if floors > 1:
                wy = 0.5 + (f + 0.5) * H / floors - win / 2 + (0.1 if f == 0 else 0)
            xs = [-w * 0.32, w * 0.32] if f == 0 else [-w * 0.32, 0, w * 0.32]
            for wx in xs:
                if f == 0 and abs(wx) < door_w and b.get("door", True):
                    continue
                mb.quad("window", xf(wx - win / 2, wy, z_front), xf(wx + win / 2, wy, z_front),
                        xf(wx + win / 2, wy + win, z_front), xf(wx - win / 2, wy + win, z_front))
            for s in (-1, 1):                 # 옆면 창
                xs_ = s * (w / 2 + 0.03)
                if s < 0:
                    mb.quad("window", xf(xs_, wy, d * 0.18 + win / 2), xf(xs_, wy, d * 0.18 - win / 2),
                            xf(xs_, wy + win, d * 0.18 - win / 2), xf(xs_, wy + win, d * 0.18 + win / 2))
                else:
                    mb.quad("window", xf(xs_, wy, d * 0.18 - win / 2), xf(xs_, wy, d * 0.18 + win / 2),
                            xf(xs_, wy + win, d * 0.18 + win / 2), xf(xs_, wy + win, d * 0.18 - win / 2))
        if b.get("clock"):
            cy_ = 0.5 + H - 1.6
            r = min(w, 2.6) * 0.42
            mb.quad("clock", xf(-r, cy_ - r, z_front - 0.02), xf(r, cy_ - r, z_front - 0.02),
                    xf(r, cy_ + r, z_front - 0.02), xf(-r, cy_ + r, z_front - 0.02))
        # 간판 (문 위, 앞으로 살짝 튀어나옴) — 글씨가 잘 보이게 그림자 없는 셰이더
        if b.get("sign"):
            sw, sh = 2.6, 1.05
            sy = 0.5 + door_h + 0.35
            p = [xf(-sw / 2, sy, z_front - 0.12), xf(sw / 2, sy, z_front - 0.12), xf(sw / 2, sy + sh, z_front - 0.12),
                 xf(-sw / 2, sy + sh, z_front - 0.12)]
            sm = MeshBuilder()
            sm.quad("sign", *p)
            e = sm.entities(lambda k, s=b["sign"]: tex_fn(f"town/sign_{s}.png"), shader=unlit_shader)
            extra += e
            mb.box("metal", (-sw / 2 + 0.2, sy + sh + 0.05, z_front - 0.06), (0.06, 0.4, 0.06), xf, 1.0)
            mb.box("metal", (sw / 2 - 0.2, sy + sh + 0.05, z_front - 0.06), (0.06, 0.4, 0.06), xf, 1.0)
        rects.append((fx, fz, hw + 0.3, hd + 0.3))
    # 소품: 나무 상자·통
    for px, pz, s in m.get("crates", []):
        y = height_fn(px, pz)
        xf = make_xf(px, pz, y, 0)
        mb.box("wood", (0, s / 2, 0), (s, s, s), xf, s)
        rects.append((px, pz, s / 2 + 0.1, s / 2 + 0.1))
    # 가로등: 금속 기둥 + 빛나는 등
    lamps = []
    for px, pz in m.get("lamps", []):
        y = height_fn(px, pz)
        xf = make_xf(px, pz, y, 0)
        mb.box("metal", (0, 1.6, 0), (0.16, 3.2, 0.16), xf, 0.6)
        mb.box("metal", (0, 3.25, 0), (0.5, 0.12, 0.5), xf, 0.6)
        mb.box("metal", (0, 0.1, 0), (0.45, 0.2, 0.45), xf, 0.6)
        lamps.append(Vec3(px, y + 2.95, pz))
        rects.append((px, pz, 0.25, 0.25))
    tex_map = {"stone": "textures3d/tile_stone.jpg", "wood": "town/wood_trim.jpg", "metal": "town/metal.jpg",
               "door": "town/door.png", "window": "town/window.png", "clock": "town/clock.png"}

    def tex_for(key):
        if key in tex_map:
            return tex_fn(tex_map[key])
        if key.startswith("wall_") or key.startswith("roof_"):
            return tex_fn(f"town/{key}.jpg")
        return None
    ents = mb.entities(tex_for)
    # 창문·등은 밤에도 빛나 보이게 조명 무시
    for e in ents:
        if e.texture and os.path.basename(str(e.texture.path)) == "window.png":
            e.shader = unlit_shader
    for p in lamps:
        g = Entity(model="sphere", position=p, scale=0.42, color=color.rgb(1.0, 0.86, 0.55), shader=unlit_shader)
        extra.append(g)
    return ents + extra, rects, chimneys
