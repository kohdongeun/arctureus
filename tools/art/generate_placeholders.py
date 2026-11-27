"""임시(플레이스홀더) 원본 이미지 생성기.

진짜 일러스트가 준비되기 전까지 게임을 개발·테스트할 수 있도록,
data/story.json 의 art_direction 팔레트로 단순한 이미지를 그려
assets_src/raw/ 에 저장한다. AI 생성 이미지처럼 '평평한 배경 위의 대상'
형태로 만들어 process_assets.py 의 누끼 처리를 그대로 시험할 수 있다.

진짜 일러스트를 같은 파일명으로 덮어쓰고 process_assets.py 만 다시 돌리면
게임 쪽 코드는 바꿀 필요가 없다.

    python tools/art/generate_placeholders.py
    python tools/art/process_assets.py
"""
from __future__ import annotations

import json
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "assets_src", "raw")
with open(os.path.join(ROOT, "data", "story.json"), encoding="utf-8") as f:
    STORY = json.load(f)
P = {k: tuple(int(v[i:i + 2], 16) for i in (1, 3, 5)) for k, v in STORY["art_direction"]["palette"].items()}
PAPER_BG = (244, 241, 234)  # 생성 AI 결과물에 흔한 밝은 단색 배경을 흉내


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def save(img, cat, name):
    os.makedirs(os.path.join(OUT, cat), exist_ok=True)
    img.save(os.path.join(OUT, cat, name + ".png"))
    print(f"  assets_src/raw/{cat}/{name}.png")


def flat_bg(size):
    img = Image.new("RGB", size, PAPER_BG)
    # 약한 노이즈 (단색이 아닌 실제 이미지 배경 흉내)
    px = img.load()
    rnd = random.Random(1)
    for _ in range(size[0] * size[1] // 40):
        x, y = rnd.randrange(size[0]), rnd.randrange(size[1])
        d = rnd.randint(-4, 4)
        px[x, y] = tuple(v + d for v in PAPER_BG)
    return img


# ------------------------------------------------------------- 초상화
def portrait(cid, emotion="normal"):
    S = 1024
    img = flat_bg((S, S))
    d = ImageDraw.Draw(img)
    skin = (240, 205, 178)
    looks = {
        "luke": {"hair": (128, 60, 36), "cloth": P["copper"], "trim": P["brass"]},
        "iris": {"hair": (236, 226, 196), "cloth": (232, 236, 238), "trim": P["ether_cyan"]},
        "zed": {"hair": (30, 30, 38), "cloth": P["night_navy"], "trim": P["brass"]},
    }[cid]
    cx = S // 2
    # 어깨/상반신
    d.polygon([(cx - 360, S), (cx - 300, 700), (cx - 120, 610), (cx + 120, 610), (cx + 300, 700), (cx + 360, S)],
              fill=looks["cloth"], outline=shade(looks["cloth"], 0.6), width=8)
    d.line([(cx, 620), (cx, S)], fill=looks["trim"], width=14)
    # 목, 얼굴
    d.rectangle([cx - 50, 520, cx + 50, 640], fill=shade(skin, 0.92))
    d.ellipse([cx - 160, 230, cx + 160, 600], fill=skin, outline=shade(skin, 0.75), width=6)
    # 눈 (감정 반영)
    eye_c = {"luke": (90, 60, 40), "iris": P["ether_deep"], "zed": (70, 75, 90)}[cid]
    for ex in (cx - 70, cx + 70):
        if emotion == "smile":
            d.arc([ex - 34, 400, ex + 34, 450], 200, 340, fill=eye_c, width=10)
        else:
            d.ellipse([ex - 26, 395, ex + 26, 455], fill=(255, 255, 255))
            d.ellipse([ex - 16, 405, ex + 16, 450], fill=eye_c)
            if emotion == "angry":
                d.line([(ex - 40, 370 + (10 if ex < cx else -10)), (ex + 40, 370 - (10 if ex < cx else -10))],
                       fill=looks["hair"], width=12)
    mouth = {"smile": (195, 15, 165), "sad": (15, 195, 165)}.get(emotion)
    if mouth:
        d.arc([cx - 50, 480 - mouth[0] // 20, cx + 50, 540], mouth[0], mouth[0] + mouth[2], fill=(150, 70, 70), width=8)
    else:
        d.line([(cx - 30, 520), (cx + 30, 520)], fill=(150, 70, 70), width=8)
    # 머리카락 & 캐릭터별 소품
    h = looks["hair"]
    if cid == "luke":
        d.pieslice([cx - 190, 170, cx + 190, 520], 180, 360, fill=h)
        for i in range(7):
            x = cx - 180 + i * 60
            d.polygon([(x, 330), (x + 60, 330), (x + 30, 400)], fill=h)
        d.rectangle([cx - 180, 290, cx + 180, 330], fill=(70, 50, 40))  # 고글 밴드
        for gx in (cx - 70, cx + 70):
            d.ellipse([gx - 50, 255, gx + 50, 355], fill=P["brass"], outline=shade(P["brass"], 0.5), width=10)
            d.ellipse([gx - 32, 273, gx + 32, 337], fill=P["ether_cyan"])
    elif cid == "iris":
        d.pieslice([cx - 200, 180, cx + 200, 560], 180, 360, fill=h)
        d.rectangle([cx - 200, 370, cx - 140, 720], fill=h)
        d.rectangle([cx + 140, 370, cx + 200, 720], fill=h)
        # 머리 위 태엽 장식
        gx, gy = cx + 90, 210
        for k in range(12):
            a = k * math.pi / 6
            d.rectangle([gx + 70 * math.cos(a) - 14, gy + 70 * math.sin(a) - 14,
                         gx + 70 * math.cos(a) + 14, gy + 70 * math.sin(a) + 14], fill=P["brass"])
        d.ellipse([gx - 64, gy - 64, gx + 64, gy + 64], fill=P["brass"], outline=shade(P["brass"], 0.5), width=8)
        d.ellipse([gx - 22, gy - 22, gx + 22, gy + 22], fill=P["ether_cyan"])
    else:  # zed
        d.pieslice([cx - 180, 190, cx + 180, 500], 180, 360, fill=h)
        d.rectangle([cx + 150, 330, cx + 200, 700], fill=h)  # 묶은 장발
        d.ellipse([cx + 30, 380, cx + 110, 470], outline=P["brass"], width=12)  # 단안경
        d.line([(cx + 110, 425), (cx + 170, 560)], fill=P["brass"], width=5)
        # 어깨 위 기계 매 '핀'
        bx, by = cx - 280, 640
        d.ellipse([bx - 70, by - 60, bx + 70, by + 60], fill=P["brass"], outline=shade(P["brass"], 0.5), width=6)
        d.ellipse([bx - 40, by - 130, bx + 40, by - 50], fill=P["brass_light"])
        d.polygon([(bx + 30, by - 95), (bx + 75, by - 85), (bx + 30, by - 70)], fill=P["iron"])
        d.ellipse([bx - 5, by - 105, bx + 15, by - 85], fill=P["ether_cyan"])
    save(img, "portraits", f"portrait_{cid}_{emotion}")


# ------------------------------------------------------------- 몬스터
def monster(mid):
    S = 1024
    img = flat_bg((S, S))
    d = ImageDraw.Draw(img)
    if mid == "mon_rust_crawler":  # 녹슨 기계 벌레
        for i in range(5):
            x = 260 + i * 110
            d.ellipse([x - 90, 520, x + 90, 700], fill=shade(P["rust"], 0.9 + i * 0.04), outline=P["soot"], width=6)
        for i in range(6):
            x = 230 + i * 100
            d.line([(x, 680), (x - 30, 800)], fill=P["iron"], width=14)
        d.ellipse([750, 470, 900, 640], fill=P["iron"], outline=P["soot"], width=6)
        d.ellipse([815, 520, 855, 560], fill=P["ether_cyan"])
    elif mid == "boss_rusted_claw":  # 1장 보스
        d.rounded_rectangle([280, 380, 740, 760], 60, fill=P["rust"], outline=P["soot"], width=10)
        for side in (-1, 1):
            x0 = 512 + side * 230
            d.line([(x0, 480), (x0 + side * 160, 300)], fill=P["iron"], width=40)
            d.polygon([(x0 + side * 160, 300), (x0 + side * 260, 200), (x0 + side * 200, 340)], fill=P["iron"])
            d.polygon([(x0 + side * 160, 300), (x0 + side * 120, 170), (x0 + side * 210, 260)], fill=P["iron"])
        for ex in (430, 594):
            d.ellipse([ex - 40, 470, ex + 40, 550], fill=P["blood_red"])
        for lx in (330, 450, 574, 694):
            d.rectangle([lx - 20, 760, lx + 20, 900], fill=P["iron"])
    elif mid == "boss_grinder":  # 3장 보스 채굴기
        d.rectangle([220, 420, 760, 780], fill=P["brass"], outline=P["soot"], width=10)
        d.polygon([(760, 470), (960, 600), (760, 730)], fill=P["iron"], outline=P["soot"])
        for k in range(5):
            d.line([(780 + k * 35, 490 + k * 22), (780 + k * 35, 710 - k * 22)], fill=P["soot"], width=6)
        d.rounded_rectangle([280, 300, 480, 420], 30, fill=P["ether_deep"])
        d.rounded_rectangle([300, 320, 460, 400], 20, fill=P["ether_cyan"])
        for wx in (320, 520, 680):
            d.ellipse([wx - 70, 740, wx + 70, 880], fill=P["soot"], outline=P["iron"], width=14)
    elif mid == "mon_hollow":  # 녹안개 홀로우
        d.polygon([(512, 200), (700, 450), (650, 880), (374, 880), (324, 450)], fill=P["rust_fog"])
        d.ellipse([412, 260, 612, 460], fill=shade(P["rust_fog"], 0.8))
        for ex in (470, 554):
            d.ellipse([ex - 18, 340, ex + 18, 376], fill=(255, 190, 120))
    save(img, "monsters", mid)


# ------------------------------------------------------------- 쿼터뷰 마을 배경
def iso_point(gx, gy, gz, ox, oy, tw=128, th=64, zh=32):
    return ox + (gx - gy) * tw / 2, oy + (gx + gy) * th / 2 - gz * zh


def background_chimney_ward():
    W, H = 2560, 1440  # 2배로 그린 뒤 파이프라인이 1280x720 으로 축소
    img = Image.new("RGB", (W, H), P["night_navy"])
    d = ImageDraw.Draw(img, "RGBA")
    # 노을진 연기 하늘
    for y in range(H):
        t = y / H
        c = tuple(int(P["soot"][i] * (1 - t) + P["copper"][i] * t * 0.6 + P["rust"][i] * t * 0.2) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)
    ox, oy = W // 2, 180
    N = 16
    rnd = random.Random(7)
    # 바닥 타일 (자갈길)
    for gx in range(N):
        for gy in range(N):
            pts = [iso_point(gx, gy, 0, ox, oy), iso_point(gx + 1, gy, 0, ox, oy),
                   iso_point(gx + 1, gy + 1, 0, ox, oy), iso_point(gx, gy + 1, 0, ox, oy)]
            road = 6 <= gx <= 8 or 6 <= gy <= 8
            base = P["iron"] if road else shade(P["soot"], 1.5)
            d.polygon(pts, fill=shade(base, 0.9 + rnd.random() * 0.2), outline=shade(base, 0.7))

    def building(gx, gy, w, l, hgt, wall, roof):
        top = [iso_point(gx, gy, hgt, ox, oy), iso_point(gx + w, gy, hgt, ox, oy),
               iso_point(gx + w, gy + l, hgt, ox, oy), iso_point(gx, gy + l, hgt, ox, oy)]
        left = [iso_point(gx, gy + l, 0, ox, oy), iso_point(gx + w, gy + l, 0, ox, oy),
                iso_point(gx + w, gy + l, hgt, ox, oy), iso_point(gx, gy + l, hgt, ox, oy)]
        right = [iso_point(gx + w, gy, 0, ox, oy), iso_point(gx + w, gy + l, 0, ox, oy),
                 iso_point(gx + w, gy + l, hgt, ox, oy), iso_point(gx + w, gy, hgt, ox, oy)]
        d.polygon(left, fill=wall, outline=shade(wall, 0.6))
        d.polygon(right, fill=shade(wall, 0.75), outline=shade(wall, 0.5))
        d.polygon(top, fill=roof, outline=shade(roof, 0.6))
        # 창문 (에테르 불빛)
        for k in range(w):
            for z in range(1, hgt, 2):
                a = iso_point(gx + k + 0.3, gy + l, z + 0.4, ox, oy)
                b = iso_point(gx + k + 0.7, gy + l, z + 1.2, ox, oy)
                d.rectangle([a[0], b[1], b[0], a[1]], fill=P["ether_cyan"] + (210,))
        # 굴뚝 + 증기
        cxp = iso_point(gx + w * 0.7, gy + l * 0.3, hgt, ox, oy)
        d.rectangle([cxp[0] - 18, cxp[1] - 120, cxp[0] + 18, cxp[1]], fill=P["copper"], outline=P["soot"])
        for s in range(5):
            r = 30 + s * 16
            d.ellipse([cxp[0] - r + s * 20, cxp[1] - 150 - s * 70 - r, cxp[0] + r + s * 20, cxp[1] - 150 - s * 70 + r],
                      fill=P["steam"] + (60 - s * 10,))

    # 뒤쪽부터 그려 겹침 순서 유지
    for (gx, gy, w, l, hgt) in [(1, 1, 3, 3, 5), (10, 1, 4, 3, 6), (1, 10, 3, 4, 4), (10, 10, 4, 4, 5),
                                (4, 1, 2, 2, 3), (1, 4, 2, 2, 3), (12, 5, 2, 1, 3)]:
        building(gx, gy, w, l, hgt, shade(P["copper"], 0.8 + rnd.random() * 0.3), shade(P["rust"], 0.9))

    # 에테르 가로등 + 빛 번짐
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for gx, gy in [(6, 5), (9, 5), (6, 10), (9, 10), (5, 7), (10, 7)]:
        x, y = iso_point(gx, gy, 0, ox, oy)
        d.line([(x, y), (x, y - 140)], fill=P["iron"], width=10)
        d.ellipse([x - 18, y - 170, x + 18, y - 134], fill=P["ether_cyan"])
        gd.ellipse([x - 110, y - 260, x + 110, y - 40], fill=P["ether_cyan"] + (90,))
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(40))).convert("RGB")
    save(img, "backgrounds", "bg_chimney_ward_plaza")


# ------------------------------------------------------------- 메뉴 UI 창
def ui_window():
    W, H = 1600, 1000
    img = flat_bg((W + 120, H + 120))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = 60, 60, 60 + W, 60 + H
    # 황동 테두리 (여러 겹 베벨)
    for i, f in enumerate([0.45, 0.8, 1.15, 0.95, 0.6]):
        d.rounded_rectangle([x0 + i * 8, y0 + i * 8, x1 - i * 8, y1 - i * 8], 40 - i * 4, fill=shade(P["brass"], f))
    # 양피지 영역
    d.rounded_rectangle([x0 + 56, y0 + 56, x1 - 56, y1 - 56], 18, fill=P["parchment"], outline=shade(P["brass"], 0.5), width=6)
    px = img.load()
    rnd = random.Random(3)
    for _ in range(40000):
        x, y = rnd.randint(x0 + 60, x1 - 60), rnd.randint(y0 + 60, y1 - 60)
        c = px[x, y]
        px[x, y] = shade(c, 0.94 + rnd.random() * 0.05)
    # 리벳
    for x in range(x0 + 30, x1 - 20, 120):
        for y in (y0 + 28, y1 - 28):
            d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=P["brass_light"], outline=shade(P["brass"], 0.4), width=3)
    for y in range(y0 + 150, y1 - 100, 120):
        for x in (x0 + 28, x1 - 28):
            d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=P["brass_light"], outline=shade(P["brass"], 0.4), width=3)
    # 모서리 톱니 장식
    for (cx, cy) in [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]:
        for k in range(10):
            a = k * math.pi / 5
            d.ellipse([cx + 52 * math.cos(a) - 12, cy + 52 * math.sin(a) - 12,
                       cx + 52 * math.cos(a) + 12, cy + 52 * math.sin(a) + 12], fill=shade(P["brass"], 0.8))
        d.ellipse([cx - 50, cy - 50, cx + 50, cy + 50], fill=P["brass"], outline=shade(P["brass"], 0.4), width=6)
        d.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=P["ether_cyan"])
    # 상단 명판
    d.rounded_rectangle([W // 2 - 200 + 60, y0 - 30, W // 2 + 200 + 60, y0 + 50], 14, fill=P["brass_light"],
                        outline=shade(P["brass"], 0.4), width=6)
    save(img, "ui", "ui_window_menu")

    # 대화창 (1280x200 비율)
    W2, H2 = 2560, 400
    img = flat_bg((W2 + 80, H2 + 80))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([40, 40, 40 + W2, 40 + H2], 30, fill=shade(P["brass"], 0.6))
    d.rounded_rectangle([52, 52, 28 + W2, 28 + H2], 24, fill=P["brass"])
    d.rounded_rectangle([80, 80, W2, H2], 16, fill=shade(P["night_navy"], 1.1), outline=P["brass_light"], width=4)
    save(img, "ui", "ui_dialogue_box")


if __name__ == "__main__":
    random.seed(0)
    for cid in ("luke", "iris", "zed"):
        for emo in ("normal", "smile", "angry", "sad"):
            portrait(cid, emo)
    for mid in ("mon_rust_crawler", "mon_hollow", "boss_rusted_claw", "boss_grinder"):
        monster(mid)
    background_chimney_ward()
    ui_window()
    print("플레이스홀더 생성 완료. 다음: python tools/art/process_assets.py")
