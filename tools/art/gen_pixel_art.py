"""필드용 도트(픽셀 아트) 생성기.

저해상도 캔버스에 픽셀 단위로 그린 뒤 최근접 보간으로 2배 확대해 저장한다.
  - 캐릭터: 24x36 → 48x72, 4방향(se, sw, ne, nw) x 걷기 4프레임 시트
  - 타일:   32x16 → 64x32 아이소메트릭 바닥
  - 블록:   32x32 → 64x64 (높이 1칸 = 32px)
  - 소품:   가로등, 통, 상자, 굴뚝 파이프, 녹슨 나무 등

    python tools/art/gen_pixel_art.py

출력: assets/images/characters/chr_<id>.png  (행: se, sw, ne, nw / 열: 프레임 0~3)
      assets/images/tiles/tile_*.png, block_*.png, prop_*.png
"""
from __future__ import annotations

import json
import os
import random

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_CHR = os.path.join(ROOT, "assets", "images", "characters")
OUT_TILE = os.path.join(ROOT, "assets", "images", "tiles")
SCALE = 2
CW, CH = 24, 36          # 캐릭터 프레임 (저해상도)
TW, TH = 32, 16          # 타일
DIRS = ["se", "sw", "ne", "nw"]

with open(os.path.join(ROOT, "data", "story.json"), encoding="utf-8") as f:
    PAL = {k: tuple(int(v[i:i + 2], 16) for i in (1, 3, 5))
           for k, v in json.load(f)["art_direction"]["palette"].items()}

OUTLINE = (24, 18, 20)
SKIN = (246, 206, 170)
SKIN_SH = (214, 164, 130)


def sh(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = [[None] * w for _ in range(h)]

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h and c is not None:
            self.px[y][x] = c

    def get(self, x, y):
        return self.px[y][x] if 0 <= x < self.w and 0 <= y < self.h else None

    def rect(self, x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.set(x, y, c)

    def hline(self, x0, x1, y, c):
        self.rect(x0, y, x1, y, c)

    def outline(self, col=OUTLINE):
        add = []
        for y in range(self.h):
            for x in range(self.w):
                if self.px[y][x] is None and any(
                        self.get(x + dx, y + dy) not in (None, col)
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    add.append((x, y))
        for x, y in add:
            self.px[y][x] = col

    def image(self):
        img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        for y in range(self.h):
            for x in range(self.w):
                c = self.px[y][x]
                if c is not None:
                    img.putpixel((x, y), tuple(c[:3]) + ((c[3],) if len(c) == 4 else (255,)))
        return img


def up(img):
    return img.resize((img.width * SCALE, img.height * SCALE), Image.NEAREST)


# ===================================================================== 캐릭터
# spec 키: hair, hair_style, coat, coat2(옷 밑단/바지), trim, boots, eyes, extras(list), kid, long_coat
CHARACTERS = {
    "luke": dict(hair=(140, 62, 34), hair_style="spiky", coat=PAL["copper"], pants=(70, 58, 52),
                 trim=PAL["brass"], boots=(60, 40, 32), eyes=(70, 40, 24), extras=["goggles", "sword"]),
    "iris": dict(hair=(238, 228, 196), hair_style="long", coat=(236, 238, 240), pants=(88, 96, 120),
                 trim=PAL["ether_cyan"], boots=(110, 90, 70), eyes=PAL["ether_deep"], extras=["gear", "cape"]),
    "zed": dict(hair=(34, 32, 44), hair_style="ponytail", coat=PAL["night_navy"], pants=(40, 40, 52),
                trim=PAL["brass"], boots=(36, 30, 30), eyes=(80, 84, 100), extras=["monocle", "rifle", "hawk"],
                long_coat=True),
    # --- NPC
    "morgan": dict(hair=(200, 200, 205), hair_style="bun", coat=(120, 84, 60), pants=(80, 60, 48),
                   trim=(200, 180, 140), boots=(60, 45, 35), eyes=(60, 50, 40), extras=["apron"]),
    "tobi": dict(hair=(90, 60, 40), hair_style="short", coat=(170, 120, 60), pants=(80, 70, 60),
                 trim=(220, 200, 150), boots=(70, 50, 40), eyes=(50, 40, 30), extras=[], kid=True),
    "hank": dict(hair=(70, 50, 40), hair_style="short", coat=(90, 96, 104), pants=(60, 60, 64),
                 trim=PAL["brass"], boots=(40, 34, 30), eyes=(50, 40, 30), extras=["helmet_lamp"]),
    "bess": dict(hair=(220, 215, 205), hair_style="kerchief", coat=(150, 70, 70), pants=(110, 60, 60),
                 trim=(230, 210, 180), boots=(70, 50, 40), eyes=(60, 50, 40), extras=["apron"]),
    "peter": dict(hair=(200, 160, 90), hair_style="short", coat=(236, 232, 220), pants=(200, 190, 170),
                  trim=PAL["brass_light"], boots=(140, 110, 60), eyes=(60, 70, 90), extras=["helmet"]),
    "villager": dict(hair=(60, 44, 36), hair_style="short", coat=(110, 120, 90), pants=(70, 66, 60),
                     trim=(160, 150, 120), boots=(60, 45, 35), eyes=(50, 40, 30), extras=[]),
}


def draw_character(spec, front: bool, frame: int) -> Image.Image:
    """front=True: 남동(se) 방향 3/4 정면, False: 북동(ne) 방향 3/4 후면. 서쪽은 좌우 반전으로 만든다."""
    c = Canvas(CW, CH)
    kid = spec.get("kid", False)
    step = frame in (1, 3)                      # 걷기 동작 프레임
    bob = 1 if step else 0                      # 발을 디딜 때 몸이 1px 내려감
    leg_a = frame == 1                          # 왼발 앞
    top = (8 if kid else 3) + bob               # 머리 꼭대기 y
    head_h = 12
    torso_top = top + head_h
    torso_bot = 28 if not kid else 29
    coat, coat_sh = spec["coat"], sh(spec["coat"], 0.72)
    face_dx = 1 if front else -1                # 얼굴이 향하는 쪽으로 1px 쏠림

    # --- 다리
    for lx, forward in ((8, leg_a), (13, step and not leg_a)):
        y_end = 35 - (1 if forward else 0)
        c.rect(lx, torso_bot, lx + 2, y_end - 2, spec["pants"])
        c.rect(lx, y_end - 1, lx + 2, y_end, spec["boots"])
    # --- 몸통 (긴 코트는 다리를 덮음)
    bot = torso_bot + (4 if spec.get("long_coat") else 0)
    c.rect(6, torso_top, 17, bot, coat)
    c.rect(6, torso_top, 7, bot, coat_sh)                          # 그늘진 왼쪽
    if front:
        c.rect(11, torso_top + 1, 12, bot, spec["trim"])           # 앞섶 장식선
        c.hline(6, 17, torso_top + 7, sh(spec["trim"], 0.8))       # 벨트
    else:
        c.rect(11, torso_top + 1, 12, bot, coat_sh)                # 등 솔기
    if "apron" in spec["extras"] and front:
        c.rect(8, torso_top + 3, 15, bot, sh(spec["trim"], 1.0))
    if "cape" in spec["extras"]:
        cape = PAL["ether_deep"]
        if front:
            c.rect(5, torso_top, 5, bot + 2, cape)
            c.rect(18, torso_top, 18, bot + 2, cape)
        else:
            c.rect(6, torso_top, 17, bot + 3, cape)
            c.rect(7, torso_top + 2, 16, torso_top + 2, PAL["ether_cyan"])
    # --- 팔 (다리와 반대로 흔들림)
    swing_l = -1 if leg_a else (1 if step else 0)
    for ax, s in ((4, swing_l), (18, -swing_l)):
        c.rect(ax, torso_top + 1 + s, ax + 1, torso_top + 8 + s, coat_sh if ax == 4 else coat)
        c.rect(ax, torso_top + 9 + s, ax + 1, torso_top + 10 + s, SKIN)
    # --- 머리
    hx0, hx1 = 6, 17
    hy0, hy1 = top, top + head_h - 1
    c.rect(hx0 + 1, hy0, hx1 - 1, hy1, SKIN)
    c.rect(hx0, hy0 + 1, hx1, hy1 - 1, SKIN)
    c.rect(hx0, hy0 + 6, hx0 + 1, hy1 - 1, SKIN_SH)
    hair, hair_sh = spec["hair"], sh(spec["hair"], 0.72)
    style = spec["hair_style"]
    if front:
        # 앞머리
        c.rect(hx0, hy0, hx1, hy0 + 3, hair)
        c.rect(hx0, hy0, hx0 + 1, hy0 + 8, hair_sh)
        if style == "spiky":
            for x in range(hx0, hx1 + 1, 3):
                c.set(x, hy0 + 4, hair)
                c.set(x + 1, hy0 + 4, hair)
                c.set(x + 1, hy0 + 5, hair)
            c.set(hx0 + 2, hy0 - 1, hair)
            c.set(hx0 + 7, hy0 - 1, hair)
            c.set(hx1 - 1, hy0 - 1, hair)
        elif style == "long":
            c.rect(hx0 - 1, hy0 + 2, hx0, hy1 + 9, hair)
            c.rect(hx1, hy0 + 2, hx1 + 1, hy1 + 9, hair)
            c.rect(hx0 + 2, hy0 + 4, hx1 - 4, hy0 + 4, hair)
        elif style == "ponytail":
            c.rect(hx0, hy0 + 4, hx0 + 3, hy0 + 4, hair)
            c.rect(hx1 - 1, hy0 + 2, hx1, hy0 + 6, hair)
        elif style == "bun":
            c.rect(hx0 + 3, hy0 - 3, hx1 - 3, hy0, hair)
        elif style == "kerchief":
            c.rect(hx0, hy0, hx1, hy0 + 3, spec["coat"])
            c.rect(hx0 + 1, hy0 + 4, hx1 - 1, hy0 + 4, hair)
        # 눈
        ey = hy0 + 6
        for ex in (9 + face_dx, 14 + face_dx):
            c.rect(ex, ey, ex + 1, ey + 2, spec["eyes"])
            c.set(ex, ey, (250, 250, 250))
        c.set(12 + face_dx, ey + 4, SKIN_SH)          # 코 그림자
        c.hline(11 + face_dx, 13 + face_dx, ey + 5 + (0 if frame != 2 else 0), (170, 90, 90))
    else:
        c.rect(hx0, hy0, hx1, hy1 - 1, hair)
        c.rect(hx1 - 2, hy0 + 1, hx1, hy1 - 1, hair_sh)
        if style == "long":
            c.rect(hx0, hy1, hx1, hy1 + 9, hair)
            c.rect(hx0 + 2, hy1 + 2, hx0 + 2, hy1 + 9, hair_sh)
        elif style == "ponytail":
            c.rect(11, hy1, 13, hy1 + 8, hair)
            c.rect(11, hy1, 13, hy1, PAL["brass"])
        elif style == "bun":
            c.rect(hx0 + 3, hy0 - 3, hx1 - 3, hy0 + 1, hair)
        elif style == "kerchief":
            c.rect(hx0, hy0, hx1, hy0 + 6, spec["coat"])
            c.rect(10, hy0 + 7, 13, hy0 + 9, spec["coat"])
        elif style == "spiky":
            for x in range(hx0, hx1 + 1, 3):
                c.set(x, hy1, hair)
                c.set(x + 1, hy1 + 1, hair)

    ex = spec["extras"]
    if "goggles" in ex:
        gy = hy0 + 2
        for gx in (8, 13):
            c.rect(gx, gy, gx + 2, gy + 2, PAL["brass"])
            if front:
                c.set(gx + 1, gy + 1, PAL["ether_cyan"])
        c.hline(hx0, hx1, gy + 1, (70, 50, 40)) if not front else None
    if "gear" in ex:
        gx, gy = (14, hy0 - 2) if front else (8, hy0 - 2)
        c.rect(gx, gy, gx + 3, gy + 3, PAL["brass"])
        c.set(gx - 1, gy + 1, PAL["brass"])
        c.set(gx + 4, gy + 2, PAL["brass"])
        c.set(gx + 1, gy - 1, PAL["brass"])
        c.set(gx + 2, gy + 4, PAL["brass"])
        c.rect(gx + 1, gy + 1, gx + 2, gy + 2, PAL["ether_cyan"])
    if "monocle" in ex and front:
        mx, my = 14 + face_dx, hy0 + 5
        for dx, dy in ((0, 0), (1, 0), (2, 1), (2, 2), (1, 3), (0, 3), (-1, 2), (-1, 1)):
            c.set(mx + dx, my + dy, PAL["brass"])
    if "helmet" in ex:
        c.rect(hx0, hy0 - 1, hx1, hy0 + 3, PAL["brass_light"])
        c.rect(11, hy0 - 3, 12, hy0 - 1, PAL["blood_red"])
    if "helmet_lamp" in ex:
        c.rect(hx0, hy0 - 1, hx1, hy0 + 3, (200, 170, 60))
        if front:
            c.rect(11, hy0, 12, hy0 + 1, (255, 250, 200))
    if "sword" in ex:
        # 등에 멘 대검: 오른쪽 어깨 위로 손잡이, 후면에선 칼날이 보임
        if front:
            c.rect(17, torso_top - 4, 18, torso_top, PAL["iron"])
            c.rect(16, torso_top - 1, 19, torso_top - 1, PAL["brass"])
        else:
            for i in range(14):
                c.set(7 + i // 2 + 2, torso_top - 3 + i, PAL["iron"])
                c.set(8 + i // 2 + 2, torso_top - 3 + i, sh(PAL["iron"], 1.3))
            c.rect(8, torso_top - 5, 9, torso_top - 3, PAL["brass"])
    if "rifle" in ex:
        if front:
            c.rect(4, torso_top - 5, 4, torso_top + 2, (90, 70, 50))
        else:
            for i in range(16):
                c.set(16 - i // 2, torso_top - 4 + i, (90, 70, 50))
            c.set(16, torso_top - 5, PAL["iron"])
    if "hawk" in ex:
        bx, by = (4, torso_top - 4) if front else (16, torso_top - 4)
        c.rect(bx, by, bx + 3, by + 2, PAL["brass"])
        c.rect(bx + (3 if front else -1), by - 1, bx + (4 if front else 0), by, PAL["brass_light"])
        c.set(bx + (4 if front else 0), by - 1, PAL["ether_cyan"])

    c.outline()
    return c.image()


def build_character_sheet(cid, spec):
    sheet = Image.new("RGBA", (CW * 4, CH * 4), (0, 0, 0, 0))
    for row, d in enumerate(DIRS):
        front = d in ("se", "sw")
        mirror = d in ("sw", "nw")
        for fr in range(4):
            img = draw_character(spec, front, fr)
            if mirror:
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            sheet.paste(img, (fr * CW, row * CH))
    up(sheet).save(os.path.join(OUT_CHR, f"chr_{cid}.png"))
    print(f"  characters/chr_{cid}.png")


# ===================================================================== 타일
def diamond_mask(w=TW, h=TH):
    m = []
    for y in range(h):
        half = (y + 0.5) * (w / h) if y < h / 2 else (h - y - 0.5) * (w / h)
        m.append((w / 2 - half, w / 2 + half))
    return m


def tile(name, base, texture, seed=0):
    rnd = random.Random(seed)
    c = Canvas(TW, TH)
    m = diamond_mask()
    for y in range(TH):
        x0, x1 = m[y]
        for x in range(TW):
            if x0 <= x + 0.5 <= x1:
                c.set(x, y, texture(x, y, base, rnd))
    # 아래쪽 두 변에 어두운 테두리로 입체감
    for y in range(TH):
        x0, x1 = m[y]
        if y >= TH // 2:
            c.set(int(x0), y, sh(base, 0.6))
            c.set(int(x1 - 0.5), y, sh(base, 0.6))
    up(c.image()).save(os.path.join(OUT_TILE, f"tile_{name}.png"))
    print(f"  tiles/tile_{name}.png")


def tex_cobble(x, y, base, rnd):
    cell = ((x // 4) + (y // 2) * 3) % 5
    edge = (x % 4 == 0) or (y % 2 == 0 and (x // 4 + y // 2) % 2 == 0)
    return sh(base, 0.68) if edge else sh(base, 0.9 + cell * 0.05 + rnd.random() * 0.05)


def tex_noise(amount):
    def f(x, y, base, rnd):
        return sh(base, 1 - amount / 2 + rnd.random() * amount)
    return f


def tex_moss(x, y, base, rnd):
    r = rnd.random()
    if r < 0.08:
        return sh(base, 1.35)
    if r < 0.15:
        return sh(base, 0.7)
    return sh(base, 0.95 + rnd.random() * 0.1)


def tex_grate(x, y, base, rnd):
    if (x + y * 2) % 6 in (0, 1):
        return sh(base, 0.45)
    return sh(base, 0.95 + rnd.random() * 0.1)


def tex_rust(x, y, base, rnd):
    r = rnd.random()
    if r < 0.12:
        return sh(PAL["rust"], 1.2)
    if (x * 7 + y * 13) % 17 == 0:
        return sh(base, 0.6)
    return sh(base, 0.85 + rnd.random() * 0.2)


def tex_water(x, y, base, rnd):
    if (x + y * 3) % 9 == 0:
        return sh(PAL["ether_cyan"], 0.9)
    return sh(base, 0.9 + rnd.random() * 0.15)


def tex_plank(x, y, base, rnd):
    if (x + 2 * y) % 8 == 0:
        return sh(base, 0.6)
    return sh(base, 0.9 + rnd.random() * 0.12)


# ===================================================================== 블록 (높이 1칸)
BW, BH = 32, 32


def block(name, top_col, side_col, face=None, seed=0):
    """side 텍스처: brick / stone / metal / plank. face 함수로 창문 등을 덧그린다."""
    rnd = random.Random(seed)
    c = Canvas(BW, BH)
    m = diamond_mask()
    # 윗면
    for y in range(TH):
        x0, x1 = m[y]
        for x in range(BW):
            if x0 <= x + 0.5 <= x1:
                c.set(x, y, sh(top_col, 0.92 + rnd.random() * 0.12))
    # 옆면: 왼쪽(밝음), 오른쪽(어두움)
    for x in range(BW):
        left = x < BW // 2
        y_top = 8 + (x // 2 if left else (BW - 1 - x) // 2)
        for y in range(y_top, y_top + 16):
            lx = x if left else x - BW // 2
            ly = y - y_top
            base = sh(side_col, 1.0 if left else 0.72)
            col = side_texture(name, lx, ly, base, rnd)
            c.set(x, y, col)
    if face:
        face(c)
    up(c.image()).save(os.path.join(OUT_TILE, f"block_{name}.png"))
    print(f"  tiles/block_{name}.png")


def side_texture(name, lx, ly, base, rnd):
    kind = name.split("_")[0]
    if kind == "brick":
        mortar = ly % 4 == 3 or (lx + (4 if (ly // 4) % 2 else 0)) % 8 == 0
        return sh(base, 0.62) if mortar else sh(base, 0.9 + rnd.random() * 0.15)
    if kind == "stone":
        mortar = ly % 5 == 4 or (lx + (3 if (ly // 5) % 2 else 0)) % 6 == 0
        return sh(base, 0.7) if mortar else sh(base, 0.92 + rnd.random() * 0.1)
    if kind == "metal":
        if lx % 8 in (0,) or ly in (0, 15):
            return sh(base, 0.6)
        if (lx % 8 == 2 and ly % 6 == 2):
            return PAL["brass_light"]
        return sh(base, 0.95 + rnd.random() * 0.06)
    if kind == "plank":
        return sh(base, 0.62) if ly % 4 == 0 else sh(base, 0.9 + rnd.random() * 0.12)
    return base


def window_face(c: Canvas):
    # 왼쪽 면 창문 (에테르 불빛)
    for x in range(5, 11):
        yt = 8 + x // 2
        for y in range(yt + 4, yt + 10):
            c.set(x, y, PAL["ether_cyan"] if (x + y) % 5 else (220, 255, 250))
        c.set(x, yt + 3, OUTLINE)
        c.set(x, yt + 10, OUTLINE)
    # 오른쪽 면 창문 (주황 불빛)
    for x in range(21, 27):
        yt = 8 + (BW - 1 - x) // 2
        for y in range(yt + 4, yt + 10):
            c.set(x, y, (240, 170, 80) if (x + y) % 4 else (255, 220, 140))
        c.set(x, yt + 3, OUTLINE)
        c.set(x, yt + 10, OUTLINE)


def door_face(c: Canvas):
    for x in range(6, 12):
        yt = 8 + x // 2
        for y in range(yt + 5, yt + 16):
            c.set(x, y, (90, 60, 40) if x not in (6, 11) else (60, 40, 30))
    c.set(10, 8 + 5 + 10, PAL["brass_light"])


# ===================================================================== 소품
def prop_lamp():
    c = Canvas(16, 48)
    c.rect(7, 14, 8, 46, PAL["iron"])
    c.rect(5, 45, 10, 47, sh(PAL["iron"], 0.7))
    c.rect(4, 6, 11, 13, PAL["brass"])
    c.rect(5, 7, 10, 12, PAL["ether_cyan"])
    c.rect(6, 8, 7, 10, (230, 255, 255))
    c.rect(6, 3, 9, 5, PAL["brass"])
    c.outline()
    return c


def prop_barrel():
    c = Canvas(16, 20)
    for y in range(2, 20):
        w = 6 if 4 < y < 17 else 5
        for x in range(8 - w, 8 + w):
            c.set(x, y, sh((120, 80, 50), 0.8 + (0.25 if x < 8 else 0)))
    for y in (5, 15):
        c.hline(2, 13, y, PAL["iron"])
    for x in range(3, 13):
        c.set(x, 2, (90, 60, 40))
    c.outline()
    return c


def prop_crate():
    c = Canvas(20, 20)
    c.rect(1, 4, 18, 19, (150, 110, 60))
    c.rect(1, 4, 18, 6, (180, 140, 80))
    for i in range(14):
        c.set(2 + i, 6 + i * 13 // 14, (110, 80, 44))
    c.rect(1, 4, 1, 19, (110, 80, 44))
    c.rect(18, 4, 18, 19, (110, 80, 44))
    c.outline()
    return c


def prop_pipe():
    c = Canvas(14, 56)
    c.rect(3, 6, 10, 55, PAL["copper"])
    c.rect(3, 6, 4, 55, sh(PAL["copper"], 1.25))
    c.rect(9, 6, 10, 55, sh(PAL["copper"], 0.7))
    for y in (6, 20, 38):
        c.rect(2, y, 11, y + 2, PAL["brass"])
    c.rect(1, 2, 12, 5, sh(PAL["iron"], 0.9))
    c.outline()
    return c


def prop_tree():
    rnd = random.Random(5)
    c = Canvas(32, 52)
    c.rect(14, 28, 17, 51, (90, 60, 44))
    c.rect(14, 28, 14, 51, (120, 80, 56))
    for _ in range(260):
        x, y = rnd.randint(4, 27), rnd.randint(2, 32)
        if (x - 16) ** 2 / 150 + (y - 17) ** 2 / 230 < 1:
            r = rnd.random()
            c.set(x, y, PAL["rust"] if r < 0.35 else (sh(PAL["moss"], 0.9 + r * 0.3)))
    c.outline()
    return c


def prop_sign():
    c = Canvas(20, 28)
    c.rect(9, 12, 10, 27, (100, 70, 48))
    c.rect(2, 3, 17, 12, (170, 130, 80))
    c.hline(4, 15, 6, (90, 60, 40))
    c.hline(4, 12, 9, (90, 60, 40))
    c.outline()
    return c


def prop_vent():
    c = Canvas(24, 16)
    c.rect(2, 6, 21, 15, sh(PAL["iron"], 0.8))
    c.rect(2, 6, 21, 8, PAL["iron"])
    for x in range(4, 20, 3):
        c.rect(x, 10, x, 14, sh(PAL["iron"], 0.45))
    c.outline()
    return c


def prop_exit():
    """맵 이동 지점 표시: 바닥의 빛나는 화살표 문양"""
    c = Canvas(TW, TH)
    m = diamond_mask()
    for y in range(TH):
        x0, x1 = m[y]
        for x in range(TW):
            if x0 + 4 <= x + 0.5 <= x1 - 4 and (abs(x - 16) + abs(y - 8) * 2) % 6 < 2:
                c.set(x, y, PAL["ether_cyan"] + (200,))
    return c


def save_prop(name, canvas):
    up(canvas.image()).save(os.path.join(OUT_TILE, f"prop_{name}.png"))
    print(f"  tiles/prop_{name}.png")


if __name__ == "__main__":
    os.makedirs(OUT_CHR, exist_ok=True)
    os.makedirs(OUT_TILE, exist_ok=True)
    for cid, spec in CHARACTERS.items():
        build_character_sheet(cid, spec)

    tile("cobble", (128, 120, 116), tex_cobble, 1)
    tile("road", (110, 104, 100), tex_noise(0.12), 2)
    tile("moss", PAL["moss"], tex_moss, 3)
    tile("dirt", (120, 92, 66), tex_noise(0.18), 4)
    tile("grate", PAL["iron"], tex_grate, 5)
    tile("rust", (120, 96, 80), tex_rust, 6)
    tile("water", (40, 90, 100), tex_water, 7)
    tile("plank", (130, 96, 60), tex_plank, 8)

    block("brick", sh(PAL["rust"], 0.9), PAL["copper"], seed=11)
    block("brick_window", sh(PAL["rust"], 0.9), PAL["copper"], window_face, seed=12)
    block("brick_door", sh(PAL["rust"], 0.9), PAL["copper"], door_face, seed=13)
    block("stone", (140, 134, 126), (120, 114, 108), seed=14)
    block("stone_window", (140, 134, 126), (120, 114, 108), window_face, seed=15)
    block("metal", PAL["iron"], sh(PAL["iron"], 1.1), seed=16)
    block("roof", (96, 52, 40), (80, 44, 34), seed=17)
    block("plank_wall", (130, 96, 60), (120, 86, 56), seed=18)

    save_prop("lamp", prop_lamp())
    save_prop("barrel", prop_barrel())
    save_prop("crate", prop_crate())
    save_prop("pipe", prop_pipe())
    save_prop("tree", prop_tree())
    save_prop("sign", prop_sign())
    save_prop("vent", prop_vent())
    save_prop("exit", prop_exit())
    print("도트 그래픽 생성 완료")
