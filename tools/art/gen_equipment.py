"""장비 그림 생성 (Pillow): 무기 착용 그림 + 상점·메뉴 아이콘.

    python tools/art/gen_equipment.py

data/equipment.json 의 무기 art 값으로 그린다.
- assets/images/equipment/<무기 id>.png : 가로로 누운 무기 (1024x256, 손잡이 끝 x=40 → 끝 x=984, 축 y=128)
  → 3D 캐릭터의 손 위치에 맞춰 붙인다 (src3d/game.py WEAPON_POSE)
- assets/images/icons/<id>.png : 128x128 아이콘 (무기는 대각선, 방어구·장신구·소모품·열쇠는 그림)
모두 2배 크기로 그린 뒤 줄여 가장자리를 부드럽게 한다.
"""
from __future__ import annotations

import json
import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_W = os.path.join(ROOT, "assets", "images", "equipment")
OUT_I = os.path.join(ROOT, "assets", "images", "icons")
S = 2                       # 슈퍼샘플링 배율
CW, CH = 1024 * S, 256 * S
CY = CH // 2
X0, X1 = 40 * S, 984 * S    # 손잡이 끝 → 끝

METAL = {"steel": ((196, 204, 214), (110, 118, 132)), "iron": ((150, 154, 162), (72, 76, 86)),
         "brass": ((236, 196, 110), (150, 104, 40)), "gold": ((255, 222, 120), (176, 120, 30)),
         "dark": ((92, 96, 118), (34, 36, 50)), "rust": ((170, 104, 70), (90, 50, 34)),
         "ice": ((214, 240, 255), (120, 170, 210)), "silver": ((226, 230, 238), (138, 144, 160))}
GEM = {"amber": (255, 170, 40), "cyan": (80, 230, 255), "ruby": (240, 50, 60), "jade": (70, 220, 130),
       "violet": (190, 110, 255), "white": (255, 255, 240)}
GLOW = {"cyan": (90, 220, 255), "orange": (255, 140, 40), "gold": (255, 210, 100), "white": (220, 240, 255),
        "violet": (180, 110, 255), "green": (110, 255, 150), "amber": (255, 180, 60)}
WOOD = {"walnut": ((140, 86, 50), (78, 44, 24)), "oak": ((186, 136, 82), (110, 74, 40)),
        "dark": ((88, 60, 46), (40, 26, 20)), "red": ((160, 58, 40), (84, 24, 20)), "wood": ((150, 104, 62), (84, 54, 30))}
OUTLINE = (24, 18, 22, 255)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def shaded_poly(img, pts, light, dark, axis_y=None, outline=True, width=5 * S):
    """금속 느낌: 위쪽은 밝고 아래쪽은 어두운 그라디언트 + 가장자리 하이라이트 + 외곽선"""
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    ys = [p[1] for p in pts]
    y0, y1 = min(ys), max(ys)
    grad = Image.new("RGBA", img.size)
    gd = ImageDraw.Draw(grad)
    mid = axis_y if axis_y is not None else (y0 + y1) / 2
    for y in range(int(y0), int(y1) + 1):
        if y < mid:
            t = (y - y0) / max(1, mid - y0)
            c = lerp(lerp(light, (255, 255, 255), 0.35), light, t)
        else:
            t = (y - mid) / max(1, y1 - mid)
            c = lerp(light, dark, min(1.0, t * 1.1))
        gd.line([(0, y), (img.size[0], y)], fill=c + (255,))
    img.paste(grad, (0, 0), mask)
    if outline:
        ImageDraw.Draw(img).line(pts + [pts[0]], fill=OUTLINE, width=width, joint="curve")


def gem(img, x, y, r, color):
    d = ImageDraw.Draw(img)
    d.ellipse([x - r - 3 * S, y - r - 3 * S, x + r + 3 * S, y + r + 3 * S], fill=OUTLINE)
    for k in range(r, 0, -1):
        t = k / r
        d.ellipse([x - k, y - k, x + k, y + k], fill=lerp((255, 255, 255), color, min(1, t * 1.3)) + (255,))
    d.ellipse([x - r * 0.55, y - r * 0.7, x - r * 0.1, y - r * 0.25], fill=(255, 255, 255, 220))


def add_glow(img, color, radius=14 * S, strength=1.6):
    """그림 둘레에 빛 번짐"""
    a = img.getchannel("A")
    g = Image.new("RGBA", img.size, color + (0,))
    g.putalpha(a.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: min(255, int(v * strength))))
    return Image.alpha_composite(g, img)


def runes(img, x0, x1, y, h, color, seed=1):
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img)
    x = x0
    while x < x1:
        w = rnd.randint(8, 16) * S
        kind = rnd.randint(0, 3)
        if kind == 0:
            d.rectangle([x, y - h / 2, x + w * 0.3, y + h / 2], fill=color + (255,))
        elif kind == 1:
            d.line([(x, y - h / 2), (x + w * 0.6, y + h / 2)], fill=color + (255,), width=3 * S)
        elif kind == 2:
            d.ellipse([x, y - h / 3, x + h * 0.6, y + h / 3], outline=color + (255,), width=2 * S)
        else:
            d.line([(x, y), (x + w * 0.6, y)], fill=color + (255,), width=3 * S)
            d.line([(x + w * 0.3, y - h / 2), (x + w * 0.3, y + h / 2)], fill=color + (255,), width=2 * S)
        x += w + 6 * S


# ---------------------------------------------------------------- 대검
def draw_sword(a, seed):
    img = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    light, dark = METAL[a.get("metal", "steel")]
    width = int(118 * S * a.get("width", 1.0))
    shape = a.get("shape", "straight")
    gx = X0 + 330 * S                    # 가드 위치
    bx0, bx1 = gx + 22 * S, X1
    hw = width // 2
    # 칼날 모양
    if shape == "cleaver":
        pts = [(bx0, CY - hw), (bx1 - 120 * S, CY - hw - 26 * S), (bx1, CY - hw + 10 * S), (bx1 - 40 * S, CY + hw + 6 * S),
               (bx0, CY + hw)]
    elif shape == "serrated":
        pts = [(bx0, CY - hw)]
        n = 14
        for i in range(n):
            x = bx0 + (bx1 - 160 * S - bx0) * (i + 0.5) / n
            pts += [(x, CY - hw - 18 * S), (x + (bx1 - 160 * S - bx0) / n / 2, CY - hw)]
        pts += [(bx1 - 160 * S, CY - hw), (bx1, CY), (bx1 - 160 * S, CY + hw), (bx0, CY + hw)]
    elif shape == "flame":
        pts = []
        n = 9
        for i in range(n + 1):
            x = bx0 + (bx1 - 200 * S - bx0) * i / n
            pts.append((x, CY - hw - (16 * S if i % 2 else 0)))
        pts += [(bx1, CY - 10 * S)]
        for i in range(n, -1, -1):
            x = bx0 + (bx1 - 200 * S - bx0) * i / n
            pts.append((x, CY + hw + (16 * S if i % 2 == 0 else 0)))
    elif shape == "fang":
        pts = [(bx0, CY - hw * 0.8), (bx1 - 300 * S, CY - hw - 20 * S), (bx1, CY + hw * 0.2), (bx1 - 260 * S, CY + hw * 0.7),
               (bx0, CY + hw * 0.8)]
    elif shape == "holy":
        pts = [(bx0, CY - hw - 8 * S), (bx0 + 90 * S, CY - hw + 6 * S), (bx1 - 220 * S, CY - hw + 6 * S), (bx1, CY),
               (bx1 - 220 * S, CY + hw - 6 * S), (bx0 + 90 * S, CY + hw - 6 * S), (bx0, CY + hw + 8 * S)]
    else:                                 # straight / piston
        pts = [(bx0, CY - hw), (bx1 - 150 * S, CY - hw), (bx1, CY), (bx1 - 150 * S, CY + hw), (bx0, CY + hw)]
    shaded_poly(img, pts, light, dark, axis_y=CY)
    # 날 하이라이트 + 홈(풀러)
    d.line([(bx0 + 20 * S, CY - hw + 9 * S), (bx1 - 170 * S, CY - hw + 9 * S)], fill=(255, 255, 255, 150), width=5 * S)
    d.rounded_rectangle([bx0 + 40 * S, CY - 9 * S, bx1 - 360 * S, CY + 9 * S], radius=8 * S, fill=lerp(dark, (0, 0, 0), 0.3) + (220,))
    if a.get("runes"):
        runes(img, bx0 + 60 * S, bx1 - 400 * S, CY, 14 * S, GLOW.get(a.get("glow"), (255, 220, 140)), seed)
    if a.get("rivets") or shape == "piston":
        for i in range(6):
            x = bx0 + 40 * S + i * 70 * S
            for yy in (CY - hw + 22 * S, CY + hw - 22 * S):
                d.ellipse([x - 7 * S, yy - 7 * S, x + 7 * S, yy + 7 * S], fill=(230, 210, 150, 255), outline=OUTLINE, width=2 * S)
    if a.get("pipes") or shape == "piston":   # 칼날 위 피스톤
        px0, px1 = bx0 + 10 * S, bx0 + 300 * S
        shaded_poly(img, [(px0, CY - hw - 26 * S), (px1, CY - hw - 26 * S), (px1, CY - hw + 4 * S), (px0, CY - hw + 4 * S)],
                    (236, 196, 110), (130, 90, 34))
        for i in range(4):
            x = px0 + 30 * S + i * 66 * S
            d.rectangle([x, CY - hw - 34 * S, x + 14 * S, CY - hw + 8 * S], fill=(120, 84, 30, 255), outline=OUTLINE, width=2 * S)
    # 가드
    guard = a.get("guard", "bar")
    gl, gd_ = METAL["brass" if a.get("hilt") in ("brass", "gold") else "iron"]
    if a.get("hilt") == "gold":
        gl, gd_ = METAL["gold"]
    if guard == "gear":
        r = 92 * S
        teeth = []
        for i in range(24):
            ang = i * math.tau / 24
            rr = r if i % 2 else r - 18 * S
            teeth.append((gx + math.cos(ang) * rr * 0.45, CY + math.sin(ang) * rr))
        shaded_poly(img, teeth, gl, gd_)
        d.ellipse([gx - 16 * S, CY - 16 * S, gx + 16 * S, CY + 16 * S], fill=gd_ + (255,), outline=OUTLINE, width=3 * S)
    elif guard == "wing":
        pts = [(gx - 20 * S, CY - 30 * S), (gx + 34 * S, CY - 112 * S), (gx + 10 * S, CY - 26 * S), (gx + 24 * S, CY),
               (gx + 10 * S, CY + 26 * S), (gx + 34 * S, CY + 112 * S), (gx - 20 * S, CY + 30 * S)]
        shaded_poly(img, pts, gl, gd_)
    else:
        shaded_poly(img, [(gx - 18 * S, CY - 96 * S), (gx + 18 * S, CY - 96 * S), (gx + 18 * S, CY + 96 * S), (gx - 18 * S, CY + 96 * S)],
                    gl, gd_)
    # 손잡이
    hc = {"leather": ((120, 72, 42), (60, 34, 20)), "brass": ((176, 120, 60), (90, 56, 24)),
          "silver": ((180, 186, 200), (90, 96, 110)), "gold": ((220, 170, 80), (130, 86, 30))}[a.get("hilt", "leather")]
    shaded_poly(img, [(X0 + 40 * S, CY - 24 * S), (gx - 18 * S, CY - 24 * S), (gx - 18 * S, CY + 24 * S), (X0 + 40 * S, CY + 24 * S)], *hc)
    for i in range(9):                    # 감은 끈
        x = X0 + 60 * S + i * 28 * S
        d.line([(x, CY - 22 * S), (x + 18 * S, CY + 22 * S)], fill=lerp(hc[1], (0, 0, 0), 0.3) + (255,), width=5 * S)
    # 폼멜 + 보석
    d.ellipse([X0, CY - 40 * S, X0 + 80 * S, CY + 40 * S], fill=gl + (255,), outline=OUTLINE, width=5 * S)
    if a.get("gem"):
        gem(img, X0 + 40 * S, CY, 20 * S, GEM[a["gem"]])
        gem(img, gx, CY, 18 * S, GEM[a["gem"]])
    if a.get("glow"):
        img = add_glow(img, GLOW[a["glow"]])
    return img


# ---------------------------------------------------------------- 지팡이
def draw_staff(a, seed):
    img = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    shaft = a.get("shaft", "wood")
    light, dark = WOOD["wood"] if shaft == "wood" else METAL.get(shaft, METAL["iron"])
    hx = X1 - 230 * S                      # 머리 시작
    shaded_poly(img, [(X0 + 10 * S, CY - 15 * S), (hx, CY - 18 * S), (hx, CY + 18 * S), (X0 + 10 * S, CY + 15 * S)], light, dark)
    bl, bd = METAL["brass"] if shaft != "gold" else METAL["gold"]
    for x in (X0 + 10 * S, X0 + 300 * S, X0 + 560 * S, hx - 40 * S):       # 고리 장식
        shaded_poly(img, [(x, CY - 24 * S), (x + 30 * S, CY - 24 * S), (x + 30 * S, CY + 24 * S), (x, CY + 24 * S)], bl, bd)
    gcol = GEM.get(a.get("gem") or "cyan")
    head = a.get("head", "fork")
    hc = hx + 120 * S
    if head in ("fork", "crystal_fork"):
        col = METAL["iron"] if head == "fork" else ((220, 250, 255), (110, 180, 220))
        for yy in (-1, 1):
            pts = [(hx, CY + yy * 10 * S), (hx + 40 * S, CY + yy * 58 * S), (X1, CY + yy * 60 * S), (X1, CY + yy * 34 * S),
                   (hx + 60 * S, CY + yy * 30 * S), (hx + 30 * S, CY + yy * 2 * S)]
            shaded_poly(img, pts, *col)
        if head == "crystal_fork":
            gem(img, hx + 30 * S, CY, 20 * S, gcol)
    elif head in ("ring", "halo"):
        r = 84 * S if head == "ring" else 100 * S
        d.ellipse([hc - r, CY - r, hc + r, CY + r], outline=OUTLINE, width=30 * S)
        d.ellipse([hc - r + 4 * S, CY - r + 4 * S, hc + r - 4 * S, CY + r - 4 * S], outline=bl + (255,), width=20 * S)
        if head == "halo":
            for i in range(8):
                ang = i * math.tau / 8
                x, y = hc + math.cos(ang) * (r + 14 * S), CY + math.sin(ang) * (r + 14 * S)
                d.polygon([(x + math.cos(ang) * 26 * S, y + math.sin(ang) * 26 * S),
                           (x + math.cos(ang + 1.6) * 9 * S, y + math.sin(ang + 1.6) * 9 * S),
                           (x + math.cos(ang - 1.6) * 9 * S, y + math.sin(ang - 1.6) * 9 * S)], fill=bl + (255,), outline=OUTLINE)
        gem(img, hc, CY, 34 * S, gcol)
    elif head == "gear":
        teeth = []
        for i in range(28):
            ang = i * math.tau / 28
            rr = 100 * S if i % 2 else 80 * S
            teeth.append((hc + math.cos(ang) * rr, CY + math.sin(ang) * rr))
        shaded_poly(img, teeth, bl, bd)
        d.ellipse([hc - 50 * S, CY - 50 * S, hc + 50 * S, CY + 50 * S], fill=bd + (255,), outline=OUTLINE, width=4 * S)
        gem(img, hc, CY, 28 * S, gcol)
    elif head == "harp":
        d.arc([hx, CY - 110 * S, X1 + 20 * S, CY + 110 * S], -90, 90, fill=OUTLINE, width=26 * S)
        d.arc([hx + 4 * S, CY - 106 * S, X1 + 16 * S, CY + 106 * S], -90, 90, fill=METAL["silver"][0] + (255,), width=16 * S)
        for i in range(5):
            y = CY - 80 * S + i * 40 * S
            d.line([(hx + 20 * S, y), (X1 - 20 * S - abs(i - 2) * 30 * S, y)], fill=GLOW["violet"] + (255,), width=4 * S)
        gem(img, hx + 20 * S, CY, 24 * S, gcol)
    elif head == "star":
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            rr = 110 * S if i % 2 == 0 else 46 * S
            pts.append((hc + math.cos(ang) * rr, CY + math.sin(ang) * rr))
        shaded_poly(img, pts, *METAL["gold"])
        gem(img, hc, CY, 26 * S, gcol)
    elif head == "crescent":
        d.ellipse([hc - 100 * S, CY - 100 * S, hc + 100 * S, CY + 100 * S], fill=OUTLINE)
        d.ellipse([hc - 92 * S, CY - 92 * S, hc + 92 * S, CY + 92 * S], fill=(230, 236, 255, 255))
        d.ellipse([hc - 40 * S, CY - 110 * S, hc + 150 * S, CY + 110 * S], fill=(0, 0, 0, 0))
        gem(img, hx + 10 * S, CY, 22 * S, gcol)
    elif head == "leaf":
        for k, (ang, ln) in enumerate(((-0.5, 140), (0, 170), (0.5, 140))):
            cx, cy = hx + 20 * S + math.cos(ang) * ln * S / 2, CY + math.sin(ang) * ln * S / 2
            pts = [(hx + 20 * S, CY)]
            for i in range(13):
                t = i / 12
                w = math.sin(t * math.pi) * 34 * S
                bx, by = hx + 20 * S + math.cos(ang) * ln * S * t, CY + math.sin(ang) * ln * S * t
                pts.append((bx - math.sin(ang) * w, by + math.cos(ang) * w))
            for i in range(12, -1, -1):
                t = i / 12
                w = math.sin(t * math.pi) * 34 * S
                bx, by = hx + 20 * S + math.cos(ang) * ln * S * t, CY + math.sin(ang) * ln * S * t
                pts.append((bx + math.sin(ang) * w, by - math.cos(ang) * w))
            shaded_poly(img, pts, (120, 220, 110), (40, 120, 50))
        gem(img, hx + 20 * S, CY, 22 * S, gcol)
    else:                                  # knot (옹이 지팡이)
        d.ellipse([hx - 10 * S, CY - 60 * S, hx + 150 * S, CY + 60 * S], fill=OUTLINE)
        d.ellipse([hx - 4 * S, CY - 54 * S, hx + 144 * S, CY + 54 * S], fill=WOOD["oak"][0] + (255,))
        gem(img, hx + 70 * S, CY, 26 * S, gcol)
    if a.get("glow"):
        img = add_glow(img, GLOW[a["glow"]], 18 * S, 2.0)
    return img


# ---------------------------------------------------------------- 소총
def draw_rifle(a, seed):
    img = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    wl, wd = WOOD[a.get("wood", "walnut")]
    ml, md = METAL[a.get("metal", "iron")]
    short = a.get("short")
    rx0 = X0 + 420 * S                     # 기관부 시작
    rx1 = rx0 + 300 * S
    bx1 = X1 - (140 * S if short else 0)
    # 개머리판 (두껍게: 원래 그림의 개머리판을 덮도록)
    stock = [(X0, CY - 30 * S), (X0 + 40 * S, CY - 78 * S), (rx0, CY - 40 * S), (rx0, CY + 34 * S), (X0 + 220 * S, CY + 58 * S),
             (X0 + 30 * S, CY + 96 * S), (X0, CY + 80 * S)]
    shaded_poly(img, stock, wl, wd, axis_y=CY - 20 * S)
    d.line([(X0 + 60 * S, CY - 52 * S), (rx0 - 30 * S, CY - 30 * S)], fill=lerp(wl, (255, 255, 255), 0.3) + (180,), width=6 * S)
    d.rectangle([X0, CY - 34 * S, X0 + 22 * S, CY + 88 * S], fill=md + (255,), outline=OUTLINE, width=3 * S)     # 개머리 덧판
    # 총열 (위·아래 두 줄 가능)
    barrels = a.get("barrels", 1)
    for k in range(barrels):
        y = CY - 26 * S - k * 34 * S
        shaded_poly(img, [(rx1 - 20 * S, y - 15 * S), (bx1, y - 13 * S), (bx1, y + 13 * S), (rx1 - 20 * S, y + 15 * S)], ml, md)
        d.rectangle([bx1 - 40 * S, y - 18 * S, bx1, y + 18 * S], fill=md + (255,), outline=OUTLINE, width=3 * S)   # 총구
    # 총열 아래 나무 덮개
    shaded_poly(img, [(rx1 - 30 * S, CY - 12 * S), (rx1 + 340 * S, CY - 12 * S), (rx1 + 380 * S, CY + 14 * S), (rx1 - 30 * S, CY + 22 * S)],
                wl, wd)
    for x in (rx1 + 60 * S, rx1 + 300 * S, bx1 - 160 * S):      # 총열 띠
        d.rectangle([x, CY - 48 * S - (barrels - 1) * 34 * S, x + 18 * S, CY + 10 * S], fill=ml + (255,), outline=OUTLINE, width=3 * S)
    # 기관부
    shaded_poly(img, [(rx0 - 10 * S, CY - 50 * S), (rx1, CY - 50 * S), (rx1, CY + 26 * S), (rx0 - 10 * S, CY + 30 * S)],
                *METAL["brass" if a.get("metal") in ("brass", "gold") else a.get("metal", "iron")])
    d.ellipse([rx0 + 40 * S, CY - 34 * S, rx0 + 80 * S, CY + 6 * S], fill=md + (255,), outline=OUTLINE, width=3 * S)
    d.arc([rx0 + 60 * S, CY + 6 * S, rx0 + 160 * S, CY + 80 * S], 0, 180, fill=OUTLINE, width=8 * S)           # 방아쇠울
    d.polygon([(rx0 + 20 * S, CY - 50 * S), (rx0 + 36 * S, CY - 86 * S), (rx0 + 56 * S, CY - 50 * S)], fill=md + (255,), outline=OUTLINE)
    if a.get("drum"):                      # 회전 탄창
        d.ellipse([rx0 + 120 * S, CY - 4 * S, rx0 + 250 * S, CY + 100 * S], fill=OUTLINE)
        d.ellipse([rx0 + 126 * S, CY + 2 * S, rx0 + 244 * S, CY + 94 * S], fill=METAL["brass"][0] + (255,))
        for i in range(6):
            ang = i * math.tau / 6
            cx, cy = rx0 + 185 * S + math.cos(ang) * 30 * S, CY + 48 * S + math.sin(ang) * 30 * S
            d.ellipse([cx - 9 * S, cy - 9 * S, cx + 9 * S, cy + 9 * S], fill=METAL["brass"][1] + (255,))
    if a.get("pipes"):
        d.line([(rx0, CY - 60 * S), (rx1 + 200 * S, CY - 64 * S)], fill=OUTLINE, width=14 * S)
        d.line([(rx0, CY - 60 * S), (rx1 + 200 * S, CY - 64 * S)], fill=METAL["brass"][0] + (255,), width=8 * S)
    if a.get("scope"):
        sx0, sx1, sy = rx0 + 40 * S, rx0 + 470 * S, CY - 86 * S - (barrels - 1) * 30 * S
        shaded_poly(img, [(sx0, sy - 18 * S), (sx1, sy - 18 * S), (sx1, sy + 18 * S), (sx0, sy + 18 * S)], *METAL["brass"])
        d.ellipse([sx1 - 20 * S, sy - 26 * S, sx1 + 20 * S, sy + 26 * S], fill=GEM["cyan"] + (255,), outline=OUTLINE, width=4 * S)
        for x in (sx0 + 120 * S, sx1 - 140 * S):
            d.rectangle([x, sy + 16 * S, x + 16 * S, CY - 46 * S], fill=md + (255,), outline=OUTLINE, width=2 * S)
    if a.get("coils"):
        gc = GLOW.get(a.get("glow"), (90, 220, 255))
        for i in range(5):
            x = rx1 + 420 * S + i * 46 * S
            d.ellipse([x, CY - 50 * S - (barrels - 1) * 34 * S, x + 24 * S, CY + 2 * S], outline=gc + (255,), width=6 * S)
    if a.get("bayonet"):
        y = CY - 26 * S
        shaded_poly(img, [(bx1 - 30 * S, y + 14 * S), (bx1 + 30 * S, y + 22 * S), (min(CW - 4 * S, bx1 + 170 * S), y + 26 * S),
                          (bx1 + 30 * S, y + 36 * S), (bx1 - 30 * S, y + 32 * S)], *METAL["silver"])
    if a.get("glow"):
        img = add_glow(img, GLOW[a["glow"]], 12 * S, 1.4)
    return img


DRAW = {"sword": draw_sword, "staff": draw_staff, "rifle": draw_rifle}


def finish(img, size):
    return img.resize(size, Image.LANCZOS)


def weapon_icon(full):
    """누운 무기 → 대각선 아이콘 (128)"""
    bbox = full.getbbox()
    w = full.crop(bbox)
    w = w.rotate(38, expand=True, resample=Image.BICUBIC)
    w.thumbnail((118, 118), Image.LANCZOS)
    icon = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    icon.alpha_composite(w, ((128 - w.width) // 2, (128 - w.height) // 2))
    return icon


# ---------------------------------------------------------------- 방어구·장신구·소모품 아이콘
ARMOR_COL = {"brass": (214, 170, 80), "leather": (150, 96, 56), "steel": (176, 184, 196), "cyan": (90, 200, 230),
             "rust": (168, 96, 60), "gold": (250, 210, 100), "white": (236, 236, 228), "teal": (60, 170, 170),
             "silver": (210, 214, 224), "violet": (150, 110, 220), "green": (90, 170, 100), "navy": (54, 70, 130),
             "red": (176, 56, 50), "olive": (120, 130, 70), "dark": (60, 56, 72)}


def icon_canvas():
    return Image.new("RGBA", (256, 256), (0, 0, 0, 0))


def armor_icon(a):
    img = icon_canvas()
    c = ARMOR_COL.get(a.get("color"), (180, 180, 180))
    dk = lerp(c, (0, 0, 0), 0.45)
    if a["kind"] == "heavy":
        body = [(64, 52), (98, 40), (128, 54), (158, 40), (192, 52), (204, 112), (180, 214), (128, 236), (76, 214), (52, 112)]
        shaded_poly(img, body, c, dk, width=8)
        for p in ((40, 60, 96, 110), (160, 60, 216, 110)):        # 견갑
            ImageDraw.Draw(img).ellipse(p, fill=lerp(c, (255, 255, 255), 0.15) + (255,), outline=OUTLINE, width=6)
        ImageDraw.Draw(img).line([(128, 70), (128, 220)], fill=dk + (255,), width=6)
    elif a["kind"] == "robe":
        body = [(96, 40), (160, 40), (176, 90), (214, 230), (42, 230), (80, 90)]
        shaded_poly(img, body, c, dk, width=8)
        ImageDraw.Draw(img).polygon([(108, 40), (148, 40), (128, 120)], fill=lerp(c, (255, 255, 255), 0.4) + (255,), outline=OUTLINE)
        ImageDraw.Draw(img).line([(60, 200), (196, 200)], fill=(240, 210, 120, 255), width=8)
    else:
        body = [(78, 44), (110, 38), (128, 70), (146, 38), (178, 44), (206, 220), (128, 236), (50, 220)]
        shaded_poly(img, body, c, dk, width=8)
        for y in (110, 150, 190):
            ImageDraw.Draw(img).ellipse([118, y - 7, 134, y + 7], fill=(240, 210, 120, 255), outline=OUTLINE, width=3)
    if a.get("source") == "legend":
        img = add_glow(img, (255, 220, 120), 10, 1.8)
    return img.resize((128, 128), Image.LANCZOS)


def acc_icon(x):
    img = icon_canvas()
    d = ImageDraw.Draw(img)
    k = x.get("icon")
    gold, gdk = METAL["brass"]
    if k == "ring":
        d.ellipse([60, 80, 196, 216], outline=OUTLINE, width=34)
        d.ellipse([64, 84, 192, 212], outline=(200, 120, 70, 255), width=24)
        gem(img, 128, 82, 26, GEM["ruby"])
    elif k in ("glove", "bracer"):
        shaded_poly(img, [(80, 60), (176, 60), (186, 200), (70, 200)], (150, 96, 56) if k == "glove" else METAL["steel"][0],
                    (80, 50, 28) if k == "glove" else METAL["steel"][1], width=8)
        for i in range(4):
            d.rounded_rectangle([82 + i * 24, 20, 102 + i * 24, 76], radius=10, fill=(150, 96, 56, 255) if k == "glove" else METAL["steel"][0] + (255,), outline=OUTLINE, width=5)
    elif k in ("watch", "gauge"):
        d.ellipse([44, 54, 212, 222], fill=OUTLINE)
        d.ellipse([54, 64, 202, 212], fill=gold + (255,))
        d.ellipse([70, 80, 186, 196], fill=(246, 238, 214, 255))
        d.line([(128, 138), (128, 92)], fill=OUTLINE, width=8)
        d.line([(128, 138), (164, 150)], fill=(200, 40, 40, 255) if k == "gauge" else OUTLINE, width=6)
        d.rectangle([116, 30, 140, 58], fill=gold + (255,), outline=OUTLINE, width=5)
    elif k in ("pendant", "earring"):
        d.line([(60, 30), (128, 120), (196, 30)], fill=gold + (255,), width=8)
        gem(img, 128, 160, 44, GEM["cyan"] if k == "pendant" else GEM["violet"])
    elif k in ("brooch", "cog", "nut"):
        n = 6 if k == "nut" else 12
        pts = []
        for i in range(n * 2 if k != "nut" else n):
            ang = i * math.tau / (n * 2 if k != "nut" else n)
            rr = (96 if i % 2 else 76) if k != "nut" else 90
            pts.append((128 + math.cos(ang) * rr, 128 + math.sin(ang) * rr))
        shaded_poly(img, pts, gold if k != "nut" else METAL["steel"][0], gdk if k != "nut" else METAL["steel"][1], width=8)
        d.ellipse([92, 92, 164, 164], fill=(0, 0, 0, 0) if k == "nut" else gdk + (255,), outline=OUTLINE, width=6)
        if k == "cog":
            gem(img, 128, 128, 26, GEM["ruby"])
        if k == "brooch":
            gem(img, 128, 128, 26, GEM["jade"])
    elif k == "feather":
        pts = [(70, 220), (110, 120), (170, 40), (196, 56), (150, 140), (90, 214)]
        shaded_poly(img, pts, (240, 220, 190), (150, 110, 70), width=8)
        d.line([(76, 216), (184, 48)], fill=(120, 80, 50, 255), width=6)
    elif k == "glasses":
        for x in (40, 136):
            d.ellipse([x, 90, x + 80, 170], outline=OUTLINE, width=14)
            d.ellipse([x + 6, 96, x + 74, 164], fill=(180, 230, 255, 180), outline=gold + (255,), width=6)
        d.arc([110, 100, 146, 140], 200, 340, fill=gold + (255,), width=8)
    return img.resize((128, 128), Image.LANCZOS)


def item_icon(iid, it):
    img = icon_canvas()
    d = ImageDraw.Draw(img)
    if "damage" in it:                   # 폭탄
        d.ellipse([52, 72, 204, 224], fill=OUTLINE)
        d.ellipse([60, 80, 196, 216], fill=(70, 72, 84, 255))
        d.ellipse([84, 96, 120, 132], fill=(160, 164, 180, 255))
        d.rectangle([112, 44, 144, 82], fill=METAL["brass"][0] + (255,), outline=OUTLINE, width=5)
        d.line([(128, 44), (150, 18)], fill=(255, 180, 60, 255), width=8)
        if it["damage"] > 200:
            img = add_glow(img, (255, 140, 40), 10, 1.6)
        return img.resize((128, 128), Image.LANCZOS)
    if it.get("revive"):                 # 태엽
        d.ellipse([60, 60, 196, 196], outline=OUTLINE, width=26)
        d.ellipse([64, 64, 192, 192], outline=METAL["gold"][0] + (255,), width=18)
        d.rectangle([118, 20, 138, 128], fill=METAL["gold"][0] + (255,), outline=OUTLINE, width=5)
        d.ellipse([96, 4, 160, 48], fill=METAL["gold"][0] + (255,), outline=OUTLINE, width=5)
        if it.get("revive", 0) >= 1:
            img = add_glow(img, (255, 230, 150), 12, 2.0)
        return img.resize((128, 128), Image.LANCZOS)
    col = (240, 90, 80) if "heal_hp" in it and "heal_mp" not in it else (80, 160, 250) if "heal_mp" in it and "heal_hp" not in it else \
        (250, 220, 90) if "heal_hp" in it else (120, 220, 120)
    big = it.get("tier", 1) >= 3
    bottle = [(100, 40), (156, 40), (156, 80), (196, 130), (196, 214), (60, 214), (60, 130), (100, 80)] if big else \
        [(108, 50), (148, 50), (148, 92), (180, 132), (180, 214), (76, 214), (76, 132), (108, 92)]
    shaded_poly(img, bottle, (230, 236, 244), (150, 160, 176), width=8)
    liquid = [(p[0], max(p[1], 140)) for p in bottle[3:]]
    liquid = [(bottle[3][0] - 2, 140), (bottle[4][0] - 6, 208), (bottle[5][0] + 6, 208), (bottle[6][0] + 2, 140)]
    shaded_poly(img, liquid, col, lerp(col, (0, 0, 0), 0.4), outline=False)
    d.rectangle([bottle[0][0] - 6, bottle[0][1] - 22, bottle[1][0] + 6, bottle[0][1] + 4], fill=(150, 100, 60, 255), outline=OUTLINE, width=5)
    if it.get("target") in ("all_allies", "all_party"):
        img = add_glow(img, col, 10, 1.6)
    return img.resize((128, 128), Image.LANCZOS)


def key_icon(k):
    img = icon_canvas()
    sym = {"key_oath_seal_1": "sword", "key_oath_seal_2": "shield", "key_oath_seal_3": "flame"}[k]
    pts = [(128, 24), (220, 90), (190, 214), (66, 214), (36, 90)]
    shaded_poly(img, pts, (170, 176, 186), (90, 94, 104), width=8)
    d = ImageDraw.Draw(img)
    c = (120, 230, 255, 255)
    if sym == "sword":
        d.line([(128, 60), (128, 180)], fill=c, width=12)
        d.line([(100, 150), (156, 150)], fill=c, width=10)
    elif sym == "shield":
        d.polygon([(96, 70), (160, 70), (160, 130), (128, 180), (96, 130)], outline=c, width=10)
    else:
        d.polygon([(128, 56), (160, 120), (150, 180), (128, 160), (106, 180), (96, 120)], outline=c, width=10)
    img = add_glow(img, (120, 230, 255), 8, 1.2)
    return img.resize((128, 128), Image.LANCZOS)


def main():
    os.makedirs(OUT_W, exist_ok=True)
    os.makedirs(OUT_I, exist_ok=True)
    with open(os.path.join(ROOT, "data", "equipment.json"), encoding="utf-8") as f:
        E = json.load(f)
    with open(os.path.join(ROOT, "data", "battle.json"), encoding="utf-8") as f:
        B = json.load(f)
    for i, (wid, w) in enumerate(E["weapons"].items()):
        big = DRAW[w["art"]["type"]](w["art"], i + 1)
        if w.get("source") == "legend":    # 전설 무기는 한 번 더 빛나게
            big = add_glow(big, GLOW.get(w["art"].get("glow"), (255, 220, 120)), 26 * S, 1.2)
        img = finish(big, (1024, 256))
        img.save(os.path.join(OUT_W, wid + ".png"), optimize=True)
        weapon_icon(img).save(os.path.join(OUT_I, wid + ".png"))
    for aid, a in E["armors"].items():
        armor_icon(a).save(os.path.join(OUT_I, aid + ".png"))
    for xid, x in E["accessories"].items():
        acc_icon(x).save(os.path.join(OUT_I, xid + ".png"))
    for iid, it in B["items"].items():
        item_icon(iid, it).save(os.path.join(OUT_I, iid + ".png"))
    for k in E["key_items"]:
        key_icon(k).save(os.path.join(OUT_I, k + ".png"))
    print(f"무기 {len(E['weapons'])}, 아이콘 {len(os.listdir(OUT_I))}개 → assets/images/equipment, assets/images/icons")


if __name__ == "__main__":
    main()
