"""3D 필드용 고해상도 캐릭터 그래픽 생성기 (셀 셰이딩 + 외곽선, 슈퍼샘플링).

  - 빌보드 스프라이트 시트: assets/images/sprites3d/<id>.png
      4열(걷기 프레임 0~3) x 4행(se, sw, ne, nw), 프레임 128x200
  - 스탠딩 일러스트:       assets/images/standing/stand_<id>_<emotion>.png (등신대 비율, 높이 924)

설계 좌표계(단위)에서 부위별로 그린 뒤 K배 크기로 래스터화하고 축소해 부드러운 선을 얻는다.
부위마다 '빛 반대쪽 그림자 띠'와 '외곽선'을 따로 계산해 애니메이션 셀 셰이딩 느낌을 낸다.
진짜 일러스트가 생기면 같은 파일명으로 교체하면 된다 (tools/art/process_assets.py 의 standing 카테고리).

    python tools/art/gen_hd_chars.py
"""
from __future__ import annotations

import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_SPR = os.path.join(ROOT, "assets", "images", "sprites3d")
OUT_STAND = os.path.join(ROOT, "assets", "images", "standing")

W = 64                      # 설계 캔버스 폭 (단위)
H_CHIBI = 100               # 필드 스프라이트 높이 (2.5등신)
BODY_Y = 43                 # 이 아래(몸)는 스탠딩 모드에서 세로로 늘린다 (머리·턱은 그대로)
STRETCH = 1.9
H_STAND = int(BODY_Y + (H_CHIBI - BODY_Y) * STRETCH)

SKIN = (252, 222, 198)
LINE = (58, 36, 30)


def mul(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


class Painter:
    def __init__(self, k, stand=False, emotion="normal"):
        self.k = k
        self.stand = stand
        self.emotion = emotion
        h = H_STAND if stand else H_CHIBI
        self.size = (W * k, h * k)
        self.img = Image.new("RGBA", self.size, (0, 0, 0, 0))
        self.lw = max(3, int(k * 0.55) | 1)      # 외곽선 두께(홀수 px)

    # ----- 좌표 변환 (스탠딩 모드: 몸통 아래를 세로로 늘림)
    def ty(self, y):
        if self.stand and y > BODY_Y:
            y = BODY_Y + (y - BODY_Y) * STRETCH
        return y * self.k

    def pt(self, x, y):
        return (x * self.k, self.ty(y))

    def shape(self, d, s, v):
        kind = s[0]
        if kind == "e":                                  # 타원 (cx, cy, rx, ry)
            _, cx, cy, rx, ry = s
            y0, y1 = self.ty(cy - ry), self.ty(cy + ry)
            d.ellipse([(cx - rx) * self.k, y0, (cx + rx) * self.k, y1], fill=v)
        elif kind == "p":                                # 다각형
            d.polygon([self.pt(x, y) for x, y in s[1]], fill=v)
        elif kind == "r":                                # 둥근 사각형 (x0,y0,x1,y1,r)
            _, x0, y0, x1, y1, r = s
            d.rounded_rectangle([x0 * self.k, self.ty(y0), x1 * self.k, self.ty(y1)], radius=r * self.k, fill=v)
        elif kind == "l":                                # 굵은 선 (pts, width)
            _, pts, w = s
            d.line([self.pt(x, y) for x, y in pts], fill=v, width=max(1, int(w * self.k)), joint="curve")

    def mask(self, shapes):
        m = Image.new("L", self.size, 0)
        d = ImageDraw.Draw(m)
        for s in shapes:
            self.shape(d, s, 255)
        return m

    def part(self, shapes, color, shade=0.74, band=2.0, line=True, alpha=255, light=(-0.55, -0.85), hi=None):
        """셀 셰이딩된 부위 하나를 합성"""
        m = self.mask(shapes)
        if alpha < 255:
            m = m.point(lambda v: v * alpha // 255)
        layer = Image.new("RGBA", self.size, (0, 0, 0, 0))
        layer.paste(color[:3] + (255,), (0, 0), m)
        if shade:
            dx, dy = int(light[0] * band * self.k), int(light[1] * band * self.k)
            moved = ImageChops.offset(m, dx, dy)
            shadow = ImageChops.subtract(m, moved).filter(ImageFilter.GaussianBlur(self.k * 0.25))
            shadow = ImageChops.multiply(shadow, m)
            layer.paste(mul(color, shade) + (255,), (0, 0), shadow)
            if hi:
                moved2 = ImageChops.offset(m, -dx // 2, -dy // 2)
                light_band = ImageChops.multiply(ImageChops.subtract(m, moved2), m)
                layer.paste(mul(color, hi) + (255,), (0, 0), light_band.filter(ImageFilter.GaussianBlur(self.k * 0.2)))
        if line:
            edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(self.lw)))
            layer.paste(mul(color, 0.42) + (255,), (0, 0), edge)
        self.img.alpha_composite(layer)

    def flat(self, shapes, color, alpha=255):
        m = self.mask(shapes)
        if alpha < 255:
            m = m.point(lambda v: v * alpha // 255)
        layer = Image.new("RGBA", self.size, (0, 0, 0, 0))
        layer.paste(color[:3] + (255,), (0, 0), m)
        self.img.alpha_composite(layer)

    def final(self, out_w, out_h):
        # 전체 외곽선(진한 테두리) 한 겹 + 축소
        a = self.img.getchannel("A")
        outer = ImageChops.subtract(a.filter(ImageFilter.MaxFilter(self.lw)), a)
        base = Image.new("RGBA", self.size, (0, 0, 0, 0))
        base.paste(LINE + (255,), (0, 0), outer)
        base.alpha_composite(self.img)
        return base.resize((out_w, out_h), Image.LANCZOS)


# ============================================================ 캐릭터 정의
HEROES = {
    "luke": dict(hair=(150, 66, 38), style="spiky", eyes=(110, 70, 40), coat=(184, 98, 56), trim=(226, 184, 102),
                 pants=(70, 58, 54), boots=(96, 62, 40), extras=["goggles", "sword", "pauldron", "belt"]),
    "iris": dict(hair=(240, 232, 206), style="long", eyes=(40, 160, 170), coat=(244, 244, 246), trim=(95, 227, 224),
                 pants=(244, 244, 246), boots=(120, 92, 70), skirt=(42, 120, 132), extras=["gear", "cape", "blush"]),
    "zed": dict(hair=(40, 38, 52), style="swept", eyes=(110, 116, 140), coat=(34, 42, 72), trim=(226, 184, 102),
                pants=(46, 44, 56), boots=(50, 40, 36), long_coat=True, extras=["monocle", "rifle", "hawk", "buttons"]),
    "elwin": dict(hair=(236, 206, 120), style="hood", eyes=(70, 140, 80), coat=(84, 132, 70), trim=(196, 170, 110),
                  pants=(110, 84, 60), boots=(90, 64, 44), hood=(64, 104, 58), extras=["ears", "quiver", "belt"]),
    "mirel": dict(hair=(190, 186, 176), style="hood", eyes=(255, 170, 110), coat=(130, 128, 120), trim=(160, 150, 140),
                  pants=(110, 106, 100), boots=(90, 86, 80), hood=(112, 110, 104), extras=["ears"], ghost=True),
}


def draw_human(p: Painter, c, front=True, frame=0):
    ex = c["extras"]
    step = frame in (1, 3)
    lead = frame == 1                 # 왼발 앞
    bob = -1.0 if step else 0.0
    fx = 2.0 if front else 0.0        # 3/4 시점: 얼굴 요소가 오른쪽으로 쏠림
    ghost = 205 if c.get("ghost") else 255
    hair, coat, trim = c["hair"], c["coat"], c["trim"]
    hy = bob                          # 머리/몸 전체 상하 흔들림

    # --- 등 뒤 레이어 (정면일 때 뒤에 있는 것들)
    if "cape" in ex:
        p.part([("p", [(18, 44 + hy), (46, 44 + hy), (50, 86), (14, 86)])], (40, 120, 132), alpha=ghost)
    if c["style"] == "long":
        p.part([("p", [(13, 24 + hy), (51, 24 + hy), (55, 74), (32, 78), (9, 74)])], hair, hi=1.08, alpha=ghost)
    if c["style"] == "hood":
        p.part([("e", 32, 25 + hy, 18.5, 18)], c["hood"], alpha=ghost)
    if front and "sword" in ex:
        p.part([("p", [(43, 41 + hy), (47, 41 + hy), (52, 24 + hy), (49, 23 + hy)])], (150, 156, 166))
        p.part([("r", 46, 20 + hy, 54, 24 + hy, 1)], trim)
    if front and "rifle" in ex:
        p.part([("l", [(15, 30 + hy), (22, 70)], 2.4)], (96, 70, 48))
        p.part([("l", [(14, 27 + hy), (16, 33 + hy)], 2.0)], (90, 95, 102))
    if front and "quiver" in ex:
        p.part([("p", [(42, 30 + hy), (48, 32 + hy), (40, 62), (35, 60)])], (120, 80, 50))
        for i in range(3):
            p.part([("l", [(43 + i * 2, 31 + hy), (46 + i * 2, 24 + hy)], 0.8)], (230, 230, 220), shade=0, line=False)

    # --- 다리
    for lx, fwd in ((25.5, lead), (34.5, step and not lead)):
        top, bottom = 64 + hy, 93 - (2.5 if fwd else 0)
        shift = (-1.2 if fwd else 0.6) if step else 0
        p.part([("r", lx + shift, top, lx + 6.5 + shift, bottom - 4, 2.5)], c["pants"], alpha=ghost)
        p.part([("r", lx - 0.8 + shift, bottom - 7, lx + 7.3 + shift, bottom + 1, 2.8)], c["boots"], hi=1.2, alpha=ghost)

    # --- 몸통
    if c.get("long_coat"):
        p.part([("p", [(21, 44 + hy), (43, 44 + hy), (46, 84), (18, 84)])], coat, hi=1.25, alpha=ghost)
    else:
        p.part([("p", [(21, 44 + hy), (43, 44 + hy), (41, 67 + hy), (23, 67 + hy)])], coat, hi=1.12, alpha=ghost)
    if "skirt" in c:
        p.part([("p", [(23, 60 + hy), (41, 60 + hy), (46, 76), (18, 76)])], c["skirt"], hi=1.2)
    if front:
        p.part([("l", [(32 + fx * 0.5, 45 + hy), (32 + fx * 0.5, 66 + hy if not c.get("long_coat") else 83)], 1.6)],
               trim, shade=0, line=False)
        p.part([("p", [(26, 44 + hy), (38, 44 + hy), (32 + fx * 0.5, 51 + hy)])], mul(coat, 0.8), shade=0)   # 칼라
    if "belt" in ex:
        p.part([("r", 22, 58 + hy, 42, 61.5 + hy, 0.6)], (80, 54, 36), shade=0)
        if front:
            p.part([("r", 30 + fx * 0.5, 57.6 + hy, 34.6 + fx * 0.5, 62 + hy, 0.6)], trim, shade=0)
    if "buttons" in ex and front:
        for i in range(4):
            p.part([("e", 35 + fx * 0.4, 50 + i * 7 + hy, 1.2, 1.2)], trim, shade=0, line=False)

    # --- 팔 (다리와 반대로 흔들림)
    swing = (3.0 if lead else -3.0) if step else 0.0
    for sx, sgn in ((20.5, -1), (43.5, 1)):
        hx = sx + sgn * 2.5 + (swing if sgn < 0 else -swing) * 0.7
        p.part([("l", [(sx, 46 + hy), (hx, 62 + hy)], 5.2)], mul(coat, 0.92), alpha=ghost)
        p.part([("e", hx, 63.5 + hy, 2.8, 2.8)], SKIN, shade=0.85, alpha=ghost)
    if "pauldron" in ex:
        for sx in (20, 44):
            p.part([("e", sx, 45 + hy, 5.5, 4.2)], trim, hi=1.25)
            p.part([("e", sx, 45.5 + hy, 2.2, 1.6)], (90, 95, 102), shade=0)
    if "hawk" in ex and front:                       # 왼쪽 어깨 위 기계 매 '핀'
        p.part([("e", 17, 40 + hy, 5.5, 4.2)], (190, 140, 66), hi=1.3)
        p.part([("e", 14.5, 34.5 + hy, 3.4, 3.2)], (226, 184, 102), hi=1.2)
        p.part([("p", [(11.5, 34 + hy), (8.5, 35.5 + hy), (11.5, 36.5 + hy)])], (90, 95, 102), shade=0)
        p.part([("e", 13.6, 33.8 + hy, 0.9, 0.9)], (95, 227, 224), shade=0, line=False)

    # --- 목과 머리
    p.part([("r", 29, 37 + hy, 35, 46 + hy, 1)], mul(SKIN, 0.9), shade=0, alpha=ghost)
    if front:
        p.part([("e", 32, 25 + hy, 14.5, 14.5), ("p", [(18.5, 29 + hy), (45.5, 29 + hy), (33 + fx * 0.6, 41.5 + hy)])],
               SKIN, shade=0.9, band=1.4, alpha=ghost)
        if "ears" in ex:
            for s in (-1, 1):
                p.part([("p", [(32 + s * 13, 27 + hy), (32 + s * 22, 19 + hy), (32 + s * 13.5, 32 + hy)])],
                       SKIN, shade=0.85, alpha=ghost)
        face(p, c, fx, hy)
    else:
        p.part([("e", 32, 25 + hy, 14.5, 14.5)], SKIN, alpha=ghost)
        if "ears" in ex:
            for s in (-1, 1):
                p.part([("p", [(32 + s * 13, 27 + hy), (32 + s * 22, 19 + hy), (32 + s * 13.5, 32 + hy)])],
                       SKIN, shade=0.85, alpha=ghost)

    # --- 앞머리 / 뒷머리 덮개
    hair_front(p, c, front, fx, hy, ghost)

    # --- 머리 장식 / 등 뒤 소품 (후면)
    if "goggles" in ex and front:
        p.part([("l", [(17.5, 15 + hy), (46.5, 15 + hy)], 2.0)], (80, 54, 40), shade=0)
        for gx in (26 + fx * 0.6, 38 + fx * 0.6):
            p.part([("e", gx, 14.5 + hy, 4.6, 4.2)], c["trim"], hi=1.25)
            p.part([("e", gx, 14.5 + hy, 2.9, 2.6)], (95, 227, 224), shade=0.7, hi=1.3)
    if "gear" in ex:
        gx, gy = (41, 10 + hy) if front else (23, 10 + hy)
        teeth = []
        for i in range(10):
            a = i * math.pi / 5
            teeth.append(("e", gx + math.cos(a) * 5.4, gy + math.sin(a) * 5.4, 1.4, 1.4))
        p.part(teeth + [("e", gx, gy, 5, 5)], (196, 146, 66), hi=1.3)
        p.part([("e", gx, gy, 2, 2)], (95, 227, 224), shade=0)
    if "monocle" in ex and front:
        mx, my = 38 + fx, 29 + hy
        p.part([("e", mx, my, 4.6, 4.6)], (226, 184, 102), shade=0)
        p.flat([("e", mx, my, 3.5, 3.5)], (200, 240, 245), alpha=60)
        p.part([("l", [(mx + 4, my + 2), (45, 43 + hy)], 0.5)], (226, 184, 102), shade=0, line=False)
    if not front:
        if "sword" in ex:
            p.part([("p", [(41, 34 + hy), (45, 36 + hy), (24, 80), (21, 78)])], (160, 166, 176), hi=1.2)
            p.part([("r", 39, 31 + hy, 47, 35 + hy, 1)], trim)
        if "rifle" in ex:
            p.part([("l", [(46, 32 + hy), (20, 78)], 2.6)], (96, 70, 48))
        if "quiver" in ex:
            p.part([("p", [(36, 34 + hy), (44, 36 + hy), (34, 66), (27, 64)])], (120, 80, 50))
        if "hawk" in ex:
            p.part([("e", 47, 40 + hy, 5.5, 4.2)], (190, 140, 66), hi=1.3)
            p.part([("e", 50, 35 + hy, 3.3, 3.1)], (226, 184, 102))


def hair_front(p, c, front, fx, hy, ghost):
    hair, style = c["hair"], c["style"]
    if not front:
        p.part([("e", 32, 23 + hy, 15.5, 15.5)], hair, hi=1.1, alpha=ghost)
        if style == "spiky":
            pts = []
            for i in range(9):
                x = 17 + i * 3.75
                pts.append(("p", [(x - 2, 30 + hy), (x + 2, 30 + hy), (x, 38 + hy)]))
            p.part(pts, hair, alpha=ghost)
        elif style == "long":
            p.part([("p", [(17, 26 + hy), (47, 26 + hy), (50, 72), (32, 76), (14, 72)])], hair, hi=1.08)
        elif style == "swept":
            p.part([("p", [(29, 34 + hy), (35, 34 + hy), (34, 58), (30, 58)])], hair)            # 포니테일
            p.part([("r", 29, 33 + hy, 35, 36 + hy, 1)], (226, 184, 102), shade=0)
        elif style == "hood":
            p.part([("e", 32, 24 + hy, 18, 17.5)], c["hood"], alpha=ghost)
            p.part([("p", [(18, 34 + hy), (46, 34 + hy), (40, 46 + hy), (24, 46 + hy)])], c["hood"], alpha=ghost)
        return
    if style == "spiky":
        p.part([("e", 32, 18 + hy, 16, 11.5),
                ("p", [(15.5, 28 + hy), (17, 13 + hy), (24, 5 + hy), (40, 5 + hy), (47, 13 + hy), (48.5, 28 + hy),
                       (45, 24 + hy), (42, 19 + hy), (39, 25 + hy), (35.5 + fx, 18 + hy), (32 + fx, 26 + hy),
                       (28, 18 + hy), (24, 25 + hy), (20, 19 + hy)]),
                ("p", [(20, 9 + hy), (14, 3 + hy), (25, 6 + hy)]), ("p", [(40, 6 + hy), (50, 2 + hy), (45, 11 + hy)])],
               hair, hi=1.18)
    elif style == "long":
        p.part([("e", 32, 18 + hy, 16.5, 11.5),
                ("p", [(16, 30 + hy), (17, 14 + hy), (32, 7 + hy), (47, 14 + hy), (48, 30 + hy), (44, 23 + hy),
                       (39 + fx, 26 + hy), (35 + fx, 19 + hy), (30 + fx, 26 + hy), (25, 19 + hy), (20, 25 + hy)])],
               hair, hi=1.1)
        for s in (-1, 1):            # 앞으로 내린 옆머리
            x = 32 + s * 15.5
            p.part([("p", [(x - 2.5, 22 + hy), (x + 2.5, 22 + hy), (x + s * 2, 60), (x - s * 1, 62)])], hair, hi=1.1)
    elif style == "swept":
        p.part([("e", 32, 18 + hy, 16, 11.5),
                ("p", [(16, 30 + hy), (17, 13 + hy), (30, 6 + hy), (46, 12 + hy), (48, 33 + hy), (44, 29 + hy),
                       (40 + fx, 20 + hy), (33, 21 + hy), (26, 17 + hy), (20, 25 + hy)])], hair, hi=1.25)
    elif style == "hood":
        p.part([("p", [(22, 22 + hy), (26, 15 + hy), (38, 15 + hy), (42, 22 + hy), (37 + fx, 19 + hy), (32 + fx, 23 + hy),
                       (27, 19 + hy)])], hair, hi=1.15, alpha=ghost)
        p.part([("p", [(14, 34 + hy), (15, 15 + hy), (32, 4 + hy), (49, 15 + hy), (50, 34 + hy), (46, 30 + hy),
                       (44, 17 + hy), (32, 11 + hy), (20, 17 + hy), (18, 30 + hy)])], c["hood"], hi=1.15, alpha=ghost)


def face(p, c, fx, hy):
    emo = p.emotion
    eye_c = c["eyes"]
    ey = 29 + hy
    for i, ex in enumerate((25.5 + fx, 38.5 + fx)):
        far = i == 1
        rx = 3.2 if far else 3.8
        if emo == "smile":
            p.part([("l", [(ex - rx, ey + 0.5), (ex, ey - 2.2), (ex + rx, ey + 0.5)], 1.2)], LINE, shade=0, line=False)
            continue
        ry = 4.8 if emo != "angry" else 3.6
        if emo == "surprised":
            ry = 5.2
        p.part([("e", ex, ey, rx, ry)], (255, 255, 255), shade=0.9, line=False)
        ir = 0.55 if emo == "surprised" else 0.78
        p.part([("e", ex + (0.6 if not far else 0.3), ey + 0.4, rx * ir, ry * 0.8)], eye_c, shade=0.6, band=1.6,
               light=(0, -1), line=False)
        p.part([("e", ex + 0.6, ey + 0.8, rx * 0.35, ry * 0.38)], mul(eye_c, 0.35), shade=0, line=False)
        p.part([("e", ex - 0.9, ey - 1.6, 1.1, 1.1)], (255, 255, 255), shade=0, line=False)
        # 속눈썹(윗선)
        p.part([("l", [(ex - rx - 0.6, ey - ry * 0.55), (ex, ey - ry - 0.4), (ex + rx + 0.5, ey - ry * 0.7)], 1.3)],
               LINE, shade=0, line=False)
        # 눈썹
        bx = ex
        if emo == "angry":
            pts = [(bx - 3, ey - 8 + (-1 if not far else 1.5)), (bx + 3, ey - 8 + (1.5 if not far else -1))]
            if far:
                pts = [(bx - 3, ey - 6.6), (bx + 3, ey - 8.6)]
            else:
                pts = [(bx - 3, ey - 8.6), (bx + 3, ey - 6.6)]
        elif emo == "sad":
            pts = [(bx - 3, ey - 7), (bx + 3, ey - 8.6)] if not far else [(bx - 3, ey - 8.6), (bx + 3, ey - 7)]
        else:
            pts = [(bx - 3, ey - 8), (bx, ey - 8.8), (bx + 3, ey - 8)]
        p.part([("l", pts, 0.9)], mul(c["hair"], 0.5), shade=0, line=False)
    if "blush" in c["extras"] or emo in ("smile", "shy"):
        for bx in (24 + fx, 40 + fx):
            p.flat([("e", bx, ey + 5, 2.8, 1.2)], (255, 150, 150), alpha=90)
    mx, my = 32 + fx * 1.1, 37.2 + hy
    if emo == "smile":
        p.part([("p", [(mx - 2.6, my - 0.6), (mx + 2.6, my - 0.6), (mx, my + 2)])], (200, 90, 90), shade=0)
    elif emo == "surprised":
        p.part([("e", mx, my + 0.4, 1.4, 1.8)], (170, 70, 70), shade=0)
    elif emo == "sad":
        p.part([("l", [(mx - 2, my + 0.8), (mx, my - 0.3), (mx + 2, my + 0.8)], 0.6)], (150, 70, 70), shade=0, line=False)
    elif emo == "angry":
        p.part([("l", [(mx - 2.2, my + 0.4), (mx + 2.2, my - 0.2)], 0.7)], (150, 70, 70), shade=0, line=False)
    else:
        p.part([("l", [(mx - 1.6, my), (mx + 1.6, my)], 0.6)], (160, 80, 80), shade=0, line=False)


def draw_robot(p: Painter, front=True, frame=0):
    """버려진 채굴 로봇 B-7"""
    step = frame in (1, 3)
    lead = frame == 1
    rust, brass, iron = (168, 84, 46), (196, 146, 66), (96, 100, 108)
    for lx, fwd in ((24, lead), (36, step and not lead)):
        b = 94 - (2.5 if fwd else 0)
        p.part([("r", lx, 70, lx + 5, b - 4, 1)], iron)
        p.part([("r", lx - 1.5, b - 5, lx + 6.5, b, 1.5)], rust)
    p.part([("r", 16, 40, 48, 72, 4)], rust, hi=1.25)
    p.part([("r", 20, 46, 44, 64, 2)], mul(rust, 0.8), shade=0)
    for sx in (13, 51):
        p.part([("l", [(sx, 44), (sx, 66)], 4)], iron)
        p.part([("e", sx, 68, 3, 3)], brass)
    p.part([("r", 20, 16, 44, 40, 5)], brass, hi=1.3)
    if front:
        p.part([("e", 34, 28, 6, 6)], (30, 30, 36), shade=0)
        p.part([("e", 34, 28, 3.6, 3.6)], (95, 227, 224), shade=0.7, hi=1.4)
    p.part([("l", [(26, 16), (24, 7)], 1)], iron, shade=0)
    p.part([("e", 24, 6, 1.8, 1.8)], (255, 110, 90), shade=0)


SPRITES = ["luke", "iris", "zed", "elwin", "mirel", "b7"]
DIRS = ["se", "sw", "ne", "nw"]
FRAME_W, FRAME_H = 128, 200


def render(cid, front, frame, k=8, stand=False, emotion="normal"):
    p = Painter(k, stand, emotion)
    if cid == "b7":
        draw_robot(p, front, frame)
    else:
        draw_human(p, HEROES[cid], front, frame)
    return p


def sprite_sheet(cid):
    sheet = Image.new("RGBA", (FRAME_W * 4, FRAME_H * 4), (0, 0, 0, 0))
    for row, d in enumerate(DIRS):
        front = d in ("se", "sw")
        for fr in range(4):
            img = render(cid, front, fr).final(FRAME_W, FRAME_H)
            if d in ("sw", "nw"):
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            sheet.paste(img, (fr * FRAME_W, row * FRAME_H))
    path = os.path.join(OUT_SPR, f"{cid}.png")
    sheet.save(path)
    print("  sprites3d/" + os.path.basename(path))


def standing(cid, emotion):
    k = 12
    p = render(cid, True, 0, k, stand=True, emotion=emotion)
    h = 924
    img = p.final(int(W * k * h / (H_STAND * k)), h)
    path = os.path.join(OUT_STAND, f"stand_{cid}_{emotion}.png")
    img.save(path)
    print("  standing/" + os.path.basename(path))


if __name__ == "__main__":
    os.makedirs(OUT_SPR, exist_ok=True)
    os.makedirs(OUT_STAND, exist_ok=True)
    for cid in SPRITES:
        sprite_sheet(cid)
    for cid in ("luke", "iris", "zed"):
        for emo in ("normal", "smile", "angry", "sad", "surprised", "serious"):
            standing(cid, emo)
    for cid in ("elwin", "mirel", "b7"):
        standing(cid, "normal")
    print("완료")
