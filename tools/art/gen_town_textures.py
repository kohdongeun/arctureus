"""마을 건물·보물상자 텍스처 (Pillow 로 그림).

    python tools/art/gen_town_textures.py

assets/images/town/ 에 저장:
  wall_brick.jpg, wall_plaster.jpg, wall_wood.jpg   벽 (1m = 텍스처 1/2 반복 기준)
  roof_red.jpg, roof_slate.jpg, roof_copper.jpg     지붕 기와
  wood_trim.jpg, metal.jpg                          목재 테두리, 금속(파이프·굴뚝 테)
  door.png, window.png                              문, 불 켜진 창문
  sign_<종류>.png                                   간판 (아이콘 + 한글 이름)
  chest_wood.jpg, chest_band.jpg                    보물상자
"""
from __future__ import annotations

import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "assets", "images", "town")
FONT = os.path.join(ROOT, "assets", "fonts", "NanumGothic-Bold.ttf")
FONT_SERIF = os.path.join(ROOT, "assets", "fonts", "NanumMyeongjo-Bold.ttf")


def noise_img(n, base, var, seed, blur=1.5):
    rnd = random.Random(seed)
    img = Image.new("RGB", (n, n), base)
    px = img.load()
    for y in range(n):
        for x in range(n):
            k = rnd.uniform(-var, var)
            px[x, y] = tuple(max(0, min(255, int(c + k))) for c in base)
    return img.filter(ImageFilter.GaussianBlur(blur))


def brick(n=512, seed=1):
    rnd = random.Random(seed)
    img = Image.new("RGB", (n, n), (90, 78, 70))
    d = ImageDraw.Draw(img)
    rows, cols = 8, 4
    bh, bw = n / rows, n / cols
    for r in range(rows):
        off = (bw / 2) if r % 2 else 0
        for c in range(-1, cols + 1):
            x0 = c * bw + off + 3
            y0 = r * bh + 3
            base = rnd.choice([(150, 72, 52), (164, 86, 60), (136, 64, 48), (170, 96, 70), (120, 60, 46)])
            d.rectangle([x0, y0, x0 + bw - 6, y0 + bh - 6], fill=base)
            for _ in range(30):                 # 얼룩·그을음
                xx, yy = rnd.uniform(x0, x0 + bw - 6), rnd.uniform(y0, y0 + bh - 6)
                k = rnd.uniform(0.75, 1.15)
                d.point((xx, yy), fill=tuple(int(v * k) for v in base))
            d.line([(x0, y0), (x0 + bw - 6, y0)], fill=tuple(min(255, int(v * 1.2)) for v in base), width=2)
    soot = noise_img(n, (0, 0, 0), 40, seed + 5, 18).convert("L")
    img = Image.composite(Image.new("RGB", (n, n), (40, 34, 32)), img, soot.point(lambda v: int(max(0, v - 10) * 1.6)))
    return img.filter(ImageFilter.SMOOTH)


def plaster(n=512, seed=2, base=(214, 200, 172)):
    img = noise_img(n, base, 14, seed, 2.5)
    d = ImageDraw.Draw(img)
    rnd = random.Random(seed)
    for _ in range(14):                         # 벗겨진 회벽 사이로 보이는 벽돌
        x, y = rnd.randrange(n), rnd.randrange(n)
        w, h = rnd.randint(30, 70), rnd.randint(16, 30)
        d.rectangle([x, y, x + w, y + h], fill=(150, 84, 62))
        d.rectangle([x, y, x + w, y + h], outline=(120, 104, 90), width=3)
    # 나무 기둥 (하프팀버)
    for x in (0, n // 2):
        d.rectangle([x, 0, x + 26, n], fill=(96, 62, 40))
    d.rectangle([0, n - 30, n, n], fill=(96, 62, 40))
    d.line([(26, n - 30), (n // 2, 60)], fill=(96, 62, 40), width=22)
    return img


def planks(n=512, seed=3, base=(130, 88, 56)):
    rnd = random.Random(seed)
    img = Image.new("RGB", (n, n), base)
    d = ImageDraw.Draw(img)
    w = n // 8
    for i in range(8):
        kk = rnd.uniform(0.82, 1.12)
        c = tuple(int(v * kk) for v in base)
        d.rectangle([i * w, 0, i * w + w - 3, n], fill=c)
        for _ in range(6):
            y = rnd.randrange(n)
            d.line([(i * w + 4, y), (i * w + w - 7, y + rnd.randint(-6, 6))], fill=tuple(int(v * 0.8) for v in c), width=2)
        d.line([(i * w + w - 3, 0), (i * w + w - 3, n)], fill=(50, 32, 20), width=3)
        for y in (40, n - 40):
            d.ellipse([i * w + w / 2 - 4, y - 4, i * w + w / 2 + 4, y + 4], fill=(60, 50, 44))
    return img


def roof(n=512, seed=4, base=(150, 60, 46)):
    rnd = random.Random(seed)
    img = Image.new("RGB", (n, n), tuple(int(v * 0.5) for v in base))
    d = ImageDraw.Draw(img)
    rows = 10
    h = n / rows
    for r in range(rows):
        off = (n / 16) if r % 2 else 0
        for c in range(-1, 9):
            x = c * n / 8 + off
            kk = rnd.uniform(0.8, 1.15)
            col = tuple(max(0, min(255, int(v * kk))) for v in base)
            d.rounded_rectangle([x + 2, r * h, x + n / 8 - 2, r * h + h * 1.25], radius=10, fill=col)
            d.line([(x + 4, r * h + h * 1.2), (x + n / 8 - 4, r * h + h * 1.2)], fill=tuple(int(v * 0.6) for v in col), width=4)
    return img


def metal(n=256):
    img = noise_img(n, (120, 104, 80), 12, 9, 1)
    d = ImageDraw.Draw(img)
    for y in range(0, n, 64):
        d.rectangle([0, y, n, y + 10], fill=(176, 140, 70))
        for x in range(8, n, 32):
            d.ellipse([x - 4, y + 1, x + 4, y + 9], fill=(220, 190, 110))
    return img


def door(w=256, h=384):
    img = planks(256, 7, (110, 70, 44)).resize((w, h))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline=(50, 32, 20), width=14)
    for y in (70, h - 90):
        d.rectangle([14, y, w - 14, y + 22], fill=(70, 60, 54))
        for x in (30, w - 30):
            d.ellipse([x - 7, y + 4, x + 7, y + 18], fill=(170, 150, 120))
    d.ellipse([w - 60, h // 2 - 14, w - 32, h // 2 + 14], fill=(220, 180, 90), outline=(80, 60, 30), width=4)
    d.arc([60, 10, w - 60, 110], 180, 360, fill=(200, 170, 110), width=6)
    return img.convert("RGBA")


def window(w=256, h=256):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, h], fill=(80, 52, 34, 255))
    inner = [18, 18, w - 18, h - 18]
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for k in range(40):
        t = k / 40
        gd.rectangle([18 + k, 18 + k, w - 18 - k, h - 18 - k], fill=(int(255 - 40 * (1 - t)), int(200 - 60 * (1 - t)), int(110 - 50 * (1 - t)), 255))
    img.alpha_composite(glow)
    d.line([(w / 2, 18), (w / 2, h - 18)], fill=(80, 52, 34, 255), width=14)
    d.line([(18, h / 2), (w - 18, h / 2)], fill=(80, 52, 34, 255), width=14)
    d.rectangle(inner, outline=(60, 38, 24, 255), width=6)
    d.rectangle([0, h - 26, w, h], fill=(110, 74, 48, 255))       # 창턱
    return img


def icon(kind, size=180):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = size / 2
    gold, dark = (240, 200, 110, 255), (40, 28, 20, 255)
    if kind == "weapon":                         # 엇갈린 두 검 + 모루
        for s in (-1, 1):
            ang = math.radians(45 * s)
            dx, dy = math.sin(ang), -math.cos(ang)
            p0 = (c - dx * 70, c - dy * 70)
            p1 = (c + dx * 70, c + dy * 70)
            d.line([p0, p1], fill=dark, width=26)
            d.line([p0, p1], fill=(220, 226, 236, 255), width=16)
            gx, gy = c + dx * 32, c + dy * 32
            d.line([(gx - dy * 26, gy + dx * 26), (gx + dy * 26, gy - dx * 26)], fill=gold, width=12)
        d.polygon([(c - 60, c + 52), (c + 60, c + 52), (c + 40, c + 74), (c - 40, c + 74)], fill=dark)
    elif kind == "item":                         # 물약 + 톱니
        for i in range(16):
            ang = i * math.tau / 16
            r = 62 if i % 2 else 50
            d.line([(c, c), (c + math.cos(ang) * r, c + math.sin(ang) * r)], fill=gold, width=20)
        d.ellipse([c - 46, c - 46, c + 46, c + 46], fill=gold)
        d.polygon([(c - 18, c - 50), (c + 18, c - 50), (c + 18, c - 20), (c + 40, c + 10), (c + 40, c + 52), (c - 40, c + 52),
                   (c - 40, c + 10), (c - 18, c - 20)], fill=dark)
        d.polygon([(c - 32, c + 14), (c + 32, c + 14), (c + 32, c + 44), (c - 32, c + 44)], fill=(230, 80, 70, 255))
    else:                                        # inn: 침대 + 머그
        d.rounded_rectangle([c - 70, c - 10, c + 70, c + 40], radius=10, fill=dark)
        d.rounded_rectangle([c - 64, c - 4, c + 64, c + 30], radius=8, fill=(230, 220, 200, 255))
        d.rounded_rectangle([c - 64, c - 26, c - 24, c + 4], radius=10, fill=(250, 246, 236, 255), outline=dark, width=4)
        d.rectangle([c - 70, c + 40, c - 58, c + 66], fill=dark)
        d.rectangle([c + 58, c + 40, c + 70, c + 66], fill=dark)
        d.text((c + 10, c - 66), "Zz", fill=gold, font=ImageFont.truetype(FONT, 40))
    return img


def clock(n=512):
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = n / 2
    d.ellipse([4, 4, n - 4, n - 4], fill=(60, 44, 28, 255))
    d.ellipse([24, 24, n - 24, n - 24], fill=(220, 180, 90, 255))
    d.ellipse([44, 44, n - 44, n - 44], fill=(246, 236, 210, 255))
    for i in range(12):
        a = math.radians(i * 30)
        r0, r1 = c - 70, c - 50
        d.line([(c + math.sin(a) * r0, c - math.cos(a) * r0), (c + math.sin(a) * r1, c - math.cos(a) * r1)], fill=(40, 28, 20, 255),
               width=12 if i % 3 == 0 else 6)
    d.line([(c, c), (c + 90, c - 60)], fill=(40, 28, 20, 255), width=14)
    d.line([(c, c), (c - 30, c - 150)], fill=(40, 28, 20, 255), width=10)
    d.ellipse([c - 18, c - 18, c + 18, c + 18], fill=(176, 120, 40, 255))
    return img


def sign(kind, text, w=640, h=260):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=26, fill=(60, 40, 26, 255))
    board = planks(512, 11, (150, 104, 62)).resize((w - 28, h - 28))
    img.paste(board, (14, 14))
    d.rounded_rectangle([14, 14, w - 15, h - 15], radius=18, outline=(220, 180, 90, 255), width=8)
    for x, y in ((30, 30), (w - 30, 30), (30, h - 30), (w - 30, h - 30)):
        d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=(230, 200, 120, 255), outline=(60, 40, 20, 255), width=3)
    ic = icon(kind, 180)
    img.alpha_composite(ic, (30, (h - 180) // 2))
    font = ImageFont.truetype(FONT_SERIF, 84 if len(text) <= 4 else 64)
    tw = d.textlength(text, font=font)
    x = 220 + (w - 240 - tw) / 2
    d.text((x + 4, h / 2 - 44 + 4), text, font=font, fill=(40, 24, 14, 255))
    d.text((x, h / 2 - 44), text, font=font, fill=(255, 236, 190, 255))
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    brick().save(os.path.join(OUT, "wall_brick.jpg"), quality=88)
    plaster().save(os.path.join(OUT, "wall_plaster.jpg"), quality=88)
    planks(512, 5, (120, 84, 56)).save(os.path.join(OUT, "wall_wood.jpg"), quality=88)
    roof(512, 4, (156, 62, 46)).save(os.path.join(OUT, "roof_red.jpg"), quality=88)
    roof(512, 6, (70, 78, 96)).save(os.path.join(OUT, "roof_slate.jpg"), quality=88)
    roof(512, 8, (70, 140, 120)).save(os.path.join(OUT, "roof_copper.jpg"), quality=88)
    planks(256, 12, (100, 66, 42)).save(os.path.join(OUT, "wood_trim.jpg"), quality=88)
    metal().save(os.path.join(OUT, "metal.jpg"), quality=88)
    door().save(os.path.join(OUT, "door.png"))
    window().save(os.path.join(OUT, "window.png"))
    clock().save(os.path.join(OUT, "clock.png"))
    sign("inn", "여관").save(os.path.join(OUT, "sign_inn.png"))
    sign("item", "잡화점").save(os.path.join(OUT, "sign_item.png"))
    sign("weapon", "무기점").save(os.path.join(OUT, "sign_weapon.png"))
    planks(256, 21, (150, 96, 50)).save(os.path.join(OUT, "chest_wood.jpg"), quality=90)
    metal(128).save(os.path.join(OUT, "chest_band.jpg"), quality=90)
    print("마을 텍스처 →", OUT)


if __name__ == "__main__":
    main()
