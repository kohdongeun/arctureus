"""3D 필드 텍스처 · 고해상도 UI 이미지 생성기.

  assets/images/textures3d/terrain_<map>.jpg  잔디 + 흙길 + 나무 그늘이 구워진 지형 텍스처 (3072²)
  assets/images/textures3d/leaves.png, bark.png, rock.png, tuft.png, flower.png, shadow.png
  assets/images/ui3d/dialog_panel.png, banner.png, next.png, bubble.png

    python tools/art/gen_textures3d.py [map_id ...]
"""
from __future__ import annotations

import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from src3d import terrain  # noqa: E402

TEX = os.path.join(ROOT, "assets", "images", "textures3d")
UI = os.path.join(ROOT, "assets", "images", "ui3d")


def noise(n, scales=((8, 0.5), (32, 0.3), (128, 0.2)), seed=0):
    """여러 옥타브의 부드러운 값 노이즈 (0~1)"""
    rng = np.random.default_rng(seed)
    acc = np.zeros((n, n), np.float32)
    for cells, w in scales:
        g = (rng.random((cells, cells)) * 255).astype(np.uint8)
        up = np.asarray(Image.fromarray(g).resize((n, n), Image.BICUBIC), np.float32) / 255
        acc += up * w
    acc -= acc.min()
    return acc / max(acc.max(), 1e-6)


def lerp_col(a, b, t):
    a, b = np.array(a, np.float32), np.array(b, np.float32)
    return a + (b - a) * t[..., None]


# ---------------------------------------------------------------- 지형
def terrain_texture(map_id, n=3072):
    m = terrain.load_map(map_id)
    S = m["size"]
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    wx = (xs / n - 0.5) * S
    wz = (0.5 - ys / n) * S                       # 이미지 위쪽 = +z
    nz1 = noise(n, seed=1)
    nz2 = noise(n, ((64, 0.6), (256, 0.4)), seed=2)
    # 길 경계를 노이즈로 흔들어 자연스럽게
    d = terrain.path_distance(m, wx, wz) + (nz2 - 0.5) * 1.4
    dirt_t = np.clip(0.5 - d / 0.9, 0, 1)
    grass = lerp_col((62, 112, 40), (118, 162, 62), nz1 * 0.85 + nz2 * 0.15)
    dryness = np.clip(1 - np.abs(d - 1.2) / 2.2, 0, 1) * 0.35        # 길 가장자리는 살짝 마른 풀
    grass = grass * (1 - dryness[..., None]) + np.array([150, 150, 80], np.float32) * dryness[..., None]
    dirt = lerp_col((176, 146, 98), (220, 194, 142), noise(n, ((48, 0.5), (300, 0.5)), seed=3))
    img = grass * (1 - dirt_t[..., None]) + dirt * dirt_t[..., None]
    # 나무 그림자: 해 방향(src3d/shaders.py LIGHT)의 반대쪽으로 비켜 찍은 수관 그림자 + 밑동 그늘
    sc = terrain.scatter(m)
    sun = (0.45, -0.8, 0.4)
    ao = np.zeros((n, n), np.float32)

    def blob(x, z, r, strength, squash=1.0):
        cx, cy = (x / S + 0.5) * n, (0.5 - z / S) * n
        rr = r / S * n
        x0, x1 = int(max(0, cx - rr)), int(min(n, cx + rr))
        y0, y1 = int(max(0, cy - rr)), int(min(n, cy + rr))
        if x1 <= x0 or y1 <= y0:
            return
        yy, xx = np.mgrid[y0:y1, x0:x1]
        dd = np.hypot(xx - cx, (yy - cy) / squash) / rr
        ao[y0:y1, x0:x1] = np.maximum(ao[y0:y1, x0:x1], np.clip(1 - dd, 0, 1) ** 1.2 * strength)

    for x, z, s, _ in sc["tree"]:
        k = 4.0 * s / -sun[1]                     # 수관 높이에서 땅까지 빛이 이동하는 수평 거리
        blob(x + sun[0] * k, z + sun[2] * k, 3.4 * s, 0.5)
        blob(x, z, 1.6 * s, 0.35)
    for x, z, s, _ in sc["bush"]:
        blob(x + sun[0] * 0.6, z + sun[2] * 0.6, 1.4 * s, 0.35)
    for x, z, s, _ in sc["rock"]:
        blob(x + sun[0] * 0.6 * s, z + sun[2] * 0.6 * s, 1.5 * s, 0.4)
    img = img * (1 - ao[..., None])
    out = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")
    # 풀잎 획과 조약돌
    dr = ImageDraw.Draw(out)
    rnd = random.Random(5)
    dmask = dirt_t
    for _ in range(int(n * n / 90)):
        x, y = rnd.randrange(n), rnd.randrange(n)
        if dmask[y, x] > 0.6:
            continue
        L = rnd.randint(3, 7)
        a = rnd.uniform(-0.6, 0.6) - math.pi / 2
        base = out.getpixel((x, y))
        k = rnd.choice((0.84, 0.9, 1.08, 1.14))
        col = tuple(max(0, min(255, int(c * k))) for c in base)
        dr.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], fill=col, width=2)
    for _ in range(int(n * n / 2600)):
        x, y = rnd.randrange(n), rnd.randrange(n)
        if dmask[y, x] < 0.7:
            continue
        r = rnd.uniform(1.2, 3.2)
        base = out.getpixel((x, y))
        k = rnd.uniform(0.82, 1.08)
        dr.ellipse([x - r, y - r * 0.7, x + r, y + r * 0.7], fill=tuple(int(c * k) for c in base),
                   outline=tuple(int(c * 0.72) for c in base))
    out = out.filter(ImageFilter.SMOOTH)
    path = os.path.join(TEX, f"terrain_{map_id}.jpg")
    out.save(path, quality=90, optimize=True)
    print("  textures3d/" + os.path.basename(path))


# ---------------------------------------------------------------- 오브젝트 텍스처
def leaves():
    n = 512
    img = Image.new("RGB", (n, n), (38, 78, 30))
    d = ImageDraw.Draw(img)
    rnd = random.Random(2)
    for _ in range(2600):
        x, y = rnd.uniform(0, n), rnd.uniform(0, n)
        a = rnd.uniform(0, math.pi)
        L, W = rnd.uniform(10, 20), rnd.uniform(5, 9)
        g = rnd.uniform(0.75, 1.35)
        col = (int(58 * g), int(118 * g), int(44 * g))
        pts = []
        for t in range(12):
            u = t / 11 * 2 * math.pi
            px, py = math.cos(u) * L, math.sin(u) * W * (0.6 + 0.4 * math.cos(u))
            pts.append((x + px * math.cos(a) - py * math.sin(a), y + px * math.sin(a) + py * math.cos(a)))
        for ox in (-n, 0, n):                      # 이음매 없는 타일
            for oy in (-n, 0, n):
                d.polygon([(px + ox, py + oy) for px, py in pts], fill=col)
                d.line([(x + ox - math.cos(a) * L * 0.8, y + oy - math.sin(a) * L * 0.8),
                        (x + ox + math.cos(a) * L * 0.8, y + oy + math.sin(a) * L * 0.8)],
                       fill=tuple(int(c * 0.75) for c in col), width=1)
    img.save(os.path.join(TEX, "leaves.png"))


def bark():
    n = 256
    a = noise(n, ((4, 0.3), (64, 0.7)), seed=8)
    stretch = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((n // 8, n)).resize((n, n)), np.float32) / 255
    img = lerp_col((70, 48, 32), (132, 96, 64), stretch)
    Image.fromarray(img.astype(np.uint8)).save(os.path.join(TEX, "bark.png"))


def rock():
    n = 512
    a = noise(n, ((6, 0.4), (40, 0.35), (200, 0.25)), seed=9)
    img = lerp_col((92, 94, 98), (170, 168, 160), a)
    out = Image.fromarray(img.astype(np.uint8))
    d = ImageDraw.Draw(out)
    rnd = random.Random(3)
    for _ in range(26):
        x, y = rnd.uniform(0, n), rnd.uniform(0, n)
        pts = [(x, y)]
        for _ in range(6):
            x += rnd.uniform(-30, 30)
            y += rnd.uniform(-30, 30)
            pts.append((x, y))
        d.line(pts, fill=(70, 70, 74), width=2)
    moss = noise(n, ((10, 1.0),), seed=10)
    arr = np.asarray(out, np.float32)
    mm = np.clip((moss - 0.62) * 4, 0, 1)[..., None]
    arr = arr * (1 - mm) + np.array([84, 120, 52], np.float32) * mm
    Image.fromarray(arr.astype(np.uint8)).save(os.path.join(TEX, "rock.png"))


def tuft(flowers=False):
    n = 256
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rnd = random.Random(4 if flowers else 6)
    for _ in range(46):
        x0 = n / 2 + rnd.uniform(-60, 60)
        a = rnd.uniform(-0.5, 0.5) - math.pi / 2
        L = rnd.uniform(90, 230)
        g = rnd.uniform(0.75, 1.3)
        col = (int(70 * g), int(130 * g), int(48 * g), 255)
        tip = (x0 + math.cos(a) * L, n - 2 + math.sin(a) * L)
        d.polygon([(x0 - 5, n - 1), (x0 + 5, n - 1), tip], fill=col)
    if flowers:
        for _ in range(9):
            x, y = n / 2 + rnd.uniform(-70, 70), rnd.uniform(40, 150)
            c = rnd.choice([(255, 250, 240), (255, 214, 90), (240, 150, 190), (180, 170, 255)])
            for k in range(5):
                u = k * 2 * math.pi / 5
                d.ellipse([x + math.cos(u) * 9 - 7, y + math.sin(u) * 9 - 7, x + math.cos(u) * 9 + 7, y + math.sin(u) * 9 + 7],
                          fill=c + (255,))
            d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(250, 200, 60, 255))
    img.save(os.path.join(TEX, "flower.png" if flowers else "tuft.png"))


def shadow():
    n = 256
    yy, xx = np.mgrid[0:n, 0:n]
    r = np.hypot(xx - n / 2, yy - n / 2) / (n / 2)
    a = np.clip(1 - r, 0, 1) ** 1.6 * 170
    img = np.zeros((n, n, 4), np.uint8)
    img[..., 3] = a.astype(np.uint8)
    Image.fromarray(img, "RGBA").save(os.path.join(TEX, "shadow.png"))


# ---------------------------------------------------------------- UI
def dialog_panel():
    """반투명 양피지 대화창 (2400x560)"""
    w, h = 2400, 560
    nz = noise(512, ((6, 0.5), (60, 0.5)), seed=12)
    nz = np.asarray(Image.fromarray((nz * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255
    base = lerp_col((236, 222, 186), (250, 242, 216), nz)
    # 가장자리로 갈수록 살짝 그을린 색
    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.minimum(np.minimum(xx, w - xx) / 120, np.minimum(yy, h - yy) / 80)
    burn = np.clip(1 - edge, 0, 1) ** 2 * 0.25
    base = base * (1 - burn[..., None]) + np.array([170, 130, 80], np.float32) * burn[..., None]
    rgb = Image.fromarray(base.astype(np.uint8), "RGB")
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=56, fill=228)   # 약 90% 불투명
    panel = rgb.convert("RGBA")
    panel.putalpha(mask)
    d = ImageDraw.Draw(panel)
    gold, ink = (170, 124, 58, 255), (120, 84, 44, 255)
    d.rounded_rectangle([22, 22, w - 23, h - 23], radius=40, outline=gold, width=5)
    d.rounded_rectangle([38, 38, w - 39, h - 39], radius=30, outline=ink, width=2)
    for cx, cy, sx, sy in ((38, 38, 1, 1), (w - 39, 38, -1, 1), (38, h - 39, 1, -1), (w - 39, h - 39, -1, -1)):
        d.polygon([(cx + sx * 8, cy + sy * 8), (cx + sx * 40, cy + sy * 8), (cx + sx * 8, cy + sy * 40)], fill=gold)
        d.arc([cx + sx * 20 - 26, cy + sy * 20 - 26, cx + sx * 20 + 26, cy + sy * 20 + 26], 0, 360, fill=ink, width=3)
    # 상단 중앙 장식
    cx = w // 2
    d.line([(cx - 260, 22), (cx + 260, 22)], fill=gold, width=7)
    d.polygon([(cx, 6), (cx + 18, 22), (cx, 38), (cx - 18, 22)], fill=gold, outline=ink)
    panel.save(os.path.join(UI, "dialog_panel.png"))


def name_plate():
    w, h = 720, 120
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, w - 5, h - 5], radius=28, fill=(78, 52, 34, 235), outline=(214, 170, 92, 255), width=5)
    d.rounded_rectangle([16, 16, w - 17, h - 17], radius=20, outline=(160, 120, 64, 255), width=2)
    img.save(os.path.join(UI, "name_plate.png"))


def banner():
    w, h = 1800, 200
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    a = np.zeros((h, w), np.float32)
    xx = np.linspace(-1, 1, w)
    a[:] = np.clip(1 - np.abs(xx) ** 3, 0, 1)[None, :] * 170
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = 22, 18, 14
    arr[..., 3] = a.astype(np.uint8)
    img = Image.fromarray(arr, "RGBA")
    d = ImageDraw.Draw(img)
    for y in (18, h - 19):
        for x in range(w):
            t = 1 - abs(x / w * 2 - 1) ** 2
            if t > 0:
                d.point((x, y), fill=(226, 184, 102, int(255 * t)))
    img.save(os.path.join(UI, "banner.png"))


def next_icon():
    n = 128
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(24, 40), (104, 40), (64, 100)], fill=(176, 120, 56, 255), outline=(90, 60, 30, 255))
    d.polygon([(40, 48), (88, 48), (64, 84)], fill=(236, 196, 110, 255))
    img.save(os.path.join(UI, "next.png"))


def bubble():
    n = 128
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 10, 120, 88], radius=26, fill=(255, 250, 236, 245), outline=(90, 64, 40, 255), width=5)
    d.polygon([(46, 86), (70, 86), (50, 116)], fill=(255, 250, 236, 245), outline=(90, 64, 40, 255))
    d.line([(48, 87), (68, 87)], fill=(255, 250, 236, 245), width=6)
    for x in (40, 64, 88):
        d.ellipse([x - 8, 42, x + 8, 58], fill=(110, 80, 50, 255))
    img.save(os.path.join(UI, "bubble.png"))


if __name__ == "__main__":
    os.makedirs(TEX, exist_ok=True)
    os.makedirs(UI, exist_ok=True)
    maps = sys.argv[1:] or ["verdan_edge"]
    for mid in maps:
        terrain_texture(mid)
    leaves(); bark(); rock(); tuft(False); tuft(True); shadow()
    dialog_panel(); name_plate(); banner(); next_icon(); bubble()
    print("  textures3d/*.png, ui3d/*.png")
