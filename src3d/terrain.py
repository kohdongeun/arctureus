"""지형 정의: 높이맵, 흙길 마스크, 나무·바위 배치 (numpy 만 사용, ursina 에 의존하지 않음).

텍스처를 굽는 도구(tools/art/gen_textures3d.py)와 게임 엔진이 같은 함수를 써서
지형 모양과 텍스처의 흙길/나무 그늘 위치가 정확히 일치한다.
"""
from __future__ import annotations

import json
import math
import os

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load_map(map_id):
    import sys
    base = getattr(sys, "_MEIPASS", ROOT)
    with open(os.path.join(base, "data", "maps3d", f"{map_id}.json"), encoding="utf-8") as f:
        return json.load(f)


def _seg_dist(px, pz, ax, az, bx, bz):
    vx, vz = bx - ax, bz - az
    t = np.clip(((px - ax) * vx + (pz - az) * vz) / max(1e-9, vx * vx + vz * vz), 0, 1)
    return np.hypot(px - (ax + t * vx), pz - (az + t * vz))


def path_distance(m, x, z):
    """모든 흙길 폴리라인까지의 최소 거리(배열 지원)"""
    x, z = np.asarray(x, float), np.asarray(z, float)
    d = np.full(np.broadcast(x, z).shape, 1e9)
    for path in m["paths"]:
        pts = path["points"]
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            d = np.minimum(d, _seg_dist(x, z, ax, az, bx, bz) - (path.get("width", 4.5) / 2))
    for cx, cz, r in m.get("clearings", []):
        d = np.minimum(d, np.hypot(x - cx, z - cz) - r)
    return d   # 0 이하 = 길 위


def path_mask(m, x, z, soft=1.6):
    d = path_distance(m, x, z)
    return np.clip(0.5 - d / soft, 0, 1)


def height(m, x, z):
    x, z = np.asarray(x, float), np.asarray(z, float)
    h = 0.55 * np.sin(x * 0.09 + 1.3) * np.cos(z * 0.07 - 0.4) + 0.35 * np.sin((x + z) * 0.05)
    h = h * m.get("flat", 1.0)                 # 마을처럼 평평한 맵
    for hx, hz, r, hh in m.get("hills", []):
        h = h + hh * np.exp(-((x - hx) ** 2 + (z - hz) ** 2) / (2 * r * r))
    # 맵 가장자리는 언덕으로 막아 자연스러운 경계를 만든다
    half = m["size"] / 2
    edge = np.clip((np.maximum(np.abs(x), np.abs(z)) - (half - 9)) / 9, 0, 1)
    h = h + edge ** 2 * 6.0
    # 흙길은 평평하게 다진다
    pm = path_mask(m, x, z, 3.0)
    return h * (1 - 0.75 * pm) - 0.05 * pm


def scatter(m):
    """나무·덤불·바위·풀 위치 (시드 고정). 반환: dict(kind → [(x, z, scale, rot)])"""
    rng = np.random.default_rng(m.get("seed", 7))
    half = m["size"] / 2 - 2
    out = {"tree": [], "bush": [], "rock": [], "tuft": [], "flower": []}
    keep_clear = [(n["pos"][0], n["pos"][1]) for n in m.get("npcs", [])] + [tuple(m["start"])]
    keep_clear += [tuple(e["pos"]) for e in m.get("exits", []) + m.get("events", []) + m.get("chests", []) if "pos" in e]
    keep_clear += [tuple(p[:2]) for p in m.get("lamps", []) + m.get("crates", [])]
    rects = []
    for b in m.get("buildings", []):
        w, d = b["size"]
        if int(b.get("rot", 0)) % 180 == 90:
            w, d = d, w
        rects.append((b["pos"][0], b["pos"][1], w / 2 + 2.2, d / 2 + 2.2))

    def in_rect(x, z):
        return any(abs(x - rx) < hw and abs(z - rz) < hd for rx, rz, hw, hd in rects)

    def free(x, z, gap):
        if path_distance(m, x, z) < gap or in_rect(x, z):
            return False
        return all(math.hypot(x - a, z - b) > 3.0 for a, b in keep_clear)

    # 랜드마크 거목 (위치·크기 고정) → 일반 나무는 이를 피해 배치
    trees = [(float(x), float(z), float(sc), 0.0) for x, z, sc in m.get("landmark_trees", [])]
    tries = 0
    n_land = len(trees)
    while len(trees) < m.get("trees", 70) + n_land and tries < 6000:
        tries += 1
        x, z = rng.uniform(-half, half, 2)
        if free(x, z, 2.6) and all(math.hypot(x - a, z - b) > 4.2 * max(1.0, s * 0.8) for a, b, s, _ in trees):
            trees.append((float(x), float(z), float(rng.uniform(0.85, 1.35)), float(rng.uniform(0, 360))))
    out["tree"] = trees
    for kind, n, gap in (("bush", m.get("bushes", 40), 1.2), ("rock", m.get("rocks", 18), 1.5)):
        tries = 0
        while len(out[kind]) < n and tries < 5000:
            tries += 1
            x, z = rng.uniform(-half, half, 2)
            if free(x, z, gap) and all(math.hypot(x - a, z - b) > 2.2 for a, b, *_ in trees):
                out[kind].append((float(x), float(z), float(rng.uniform(0.7, 1.4)), float(rng.uniform(0, 360))))
    for kind, n in (("tuft", m.get("tufts", 500)), ("flower", m.get("flowers", 120))):
        while len(out[kind]) < n:
            x, z = rng.uniform(-half, half, 2)
            d = float(path_distance(m, x, z))
            # 풀은 길 가장자리에 몰리게 (건물 안에는 안 남)
            if d > 0.2 and (d < 3.5 or rng.random() < 0.35) and not in_rect(x, z):
                out[kind].append((float(x), float(z), float(rng.uniform(0.6, 1.2)), float(rng.uniform(0, 180))))
    return out


def colliders(m, sc=None):
    """(x, z, 반지름) 충돌 원 목록"""
    sc = sc or scatter(m)
    out = [(x, z, 1.0 * s) for x, z, s, _ in sc["tree"]]
    out += [(x, z, 0.8 * s) for x, z, s, _ in sc["rock"]]
    out += [(x, z, 0.6 * s) for x, z, s, _ in sc["bush"]]
    return out
