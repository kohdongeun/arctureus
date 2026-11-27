"""주인공 일러스트에서 원래 그려진 무기를 지우고(몸 밖으로 나온 부분), 새 무기를 붙일 자세를 기록한다.

    python tools/art/make_weapon_layers.py [--preview DIR]

- assets/characters/field/<id>_body.png : 무기를 지운 몸 (원본은 그대로 둠)
- data/weapon_pose.json : 무기 그림(1024x256, 손잡이 끝 x=40 → 끝 x=984)을 원본 그림 좌표에 놓는 방법
    grip/tip : 원본 픽셀 좌표 (손잡이 끝, 무기 끝)   thick : 굵기 배율   layer : front(몸 앞) / back(몸 뒤)
게임(src3d/game.py)은 이 자세대로 무기 사각형을 캐릭터 빌보드에 붙여 함께 움직인다.
"""
from __future__ import annotations

import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FIELD = os.path.join(ROOT, "assets", "characters", "field")

POSE = {
    # 대검: 몸 뒤로 비스듬히 (손잡이는 오른쪽 어깨 위, 칼끝은 왼쪽 아래)
    "luke": {"grip": [792, 288], "tip": [0, 950], "thick": 1.15, "layer": "back",
             "erase": [[[0, 862], [258, 660], [274, 702], [302, 778], [140, 970], [0, 970]],
                       [[598, 404], [716, 282], [792, 262], [792, 366], [700, 404], [646, 470], [606, 474]],
                       [[556, 416], [604, 424], [652, 502], [644, 540], [612, 536], [596, 486], [566, 460]]]},
    # 소리굽쇠 지팡이: 왼손에 세워 듦 (몸 뒤, 손이 앞)
    "iris": {"grip": [122, 672], "tip": [20, 386], "thick": 2.3, "layer": "back",
             "erase": [[[4, 382], [56, 382], [60, 466], [88, 574], [64, 578], [34, 482], [4, 474]],
                       [[98, 626], [124, 624], [130, 672], [104, 672]]]},
    # 소총: 어깨에 멘 채 몸 앞으로 (개머리판 왼쪽 아래, 총구 오른쪽 위)
    "zed": {"grip": [16, 734], "tip": [862, 290], "thick": 0.8, "layer": "front",
            "erase": [[[0, 596], [196, 532], [206, 652], [140, 704], [72, 776], [0, 778]],
                      [[612, 344], [864, 240], [864, 302], [800, 350], [662, 402], [618, 412]]]},
}


def quad_px(pose, cw=1024, ch=256, x0=40, x1=984):
    """무기 그림 네 모서리 → 원본 픽셀 좌표 (손잡이 끝·끝 맞춤, 그림의 위쪽이 화면 위쪽을 향하게)"""
    gx, gy = pose["grip"]
    tx, ty = pose["tip"]
    L = math.hypot(tx - gx, ty - gy)
    ux, uy = (tx - gx) / L, (ty - gy) / L
    nx, ny = uy, -ux                                       # 위쪽(y 음수)을 향하는 수직
    if ny > 0:
        nx, ny = -nx, -ny
    k = L / (x1 - x0)
    th = pose.get("thick", 1.0)

    def P(cx, cy):
        a = (cx - x0) * k
        b = -(cy - ch / 2) * k * th
        return (gx + ux * a + nx * b, gy + uy * a + ny * b)
    return [P(0, 0), P(cw, 0), P(cw, ch), P(0, ch)]


def composite(body, weapon, pose):
    """미리보기: 몸 + 무기 합성 (게임과 같은 배치)"""
    W, H = body.size
    q = quad_px(pose)
    # 무기 그림을 사각형에 맞게 변형 (QUAD 변환: 출력 좌표 → 입력 좌표 역사상이 필요해 아핀으로 근사)
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = q
    ww, wh = weapon.size
    # 아핀: 입력 (u,v) → 출력 (x,y) = O + u*A + v*B
    ax, ay = (x1 - x0) / ww, (y1 - y0) / ww
    bx, by = (x3 - x0) / wh, (y3 - y0) / wh
    det = ax * by - ay * bx
    ia, ib, ic, id_ = by / det, -bx / det, -ay / det, ax / det
    data = (ia, ib, -(ia * x0 + ib * y0), ic, id_, -(ic * x0 + id_ * y0))
    layer = weapon.transform((W, H), Image.AFFINE, data, resample=Image.BICUBIC)
    out = Image.new("RGBA", (W, H))
    if pose["layer"] == "back":
        out.alpha_composite(layer)
        out.alpha_composite(body)
    else:
        out.alpha_composite(body)
        out.alpha_composite(layer)
    return out


def main():
    poses = {}
    for cid, pose in POSE.items():
        src = Image.open(os.path.join(FIELD, cid + ".png")).convert("RGBA")
        mask = Image.new("L", src.size, 0)
        d = ImageDraw.Draw(mask)
        for poly in pose["erase"]:
            d.polygon([tuple(p) for p in poly], fill=255)
        mask = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
        a = src.getchannel("A")
        from PIL import ImageChops
        a = ImageChops.subtract(a, mask)
        body = src.copy()
        body.putalpha(a)
        body.save(os.path.join(FIELD, cid + "_body.png"), optimize=True)
        poses[cid] = {k: v for k, v in pose.items() if k != "erase"} | {"size": list(src.size)}
    with open(os.path.join(ROOT, "data", "weapon_pose.json"), "w", encoding="utf-8") as f:
        json.dump(poses, f, ensure_ascii=False, indent=1)
    print("몸 그림·자세 저장:", ", ".join(poses))
    if "--preview" in sys.argv:
        out = sys.argv[sys.argv.index("--preview") + 1]
        os.makedirs(out, exist_ok=True)
        eq = json.load(open(os.path.join(ROOT, "data", "equipment.json"), encoding="utf-8"))
        for cid in POSE:
            body = Image.open(os.path.join(FIELD, cid + "_body.png")).convert("RGBA")
            ws = [w for w, d in eq["weapons"].items() if cid in d["chars"]]
            tiles = []
            for w in ws[:10]:
                wim = Image.open(os.path.join(ROOT, "assets", "images", "equipment", w + ".png")).convert("RGBA")
                c = composite(body, wim, POSE[cid])
                bg = Image.new("RGBA", c.size, (60, 90, 60, 255))
                bg.alpha_composite(c)
                bg.thumbnail((300, 360))
                tiles.append(bg)
            bodyv = Image.new("RGBA", body.size, (60, 90, 60, 255))
            bodyv.alpha_composite(body)
            bodyv.thumbnail((300, 360))
            tiles.insert(0, bodyv)
            sheet = Image.new("RGB", (300 * 6, 360 * 2), (30, 30, 30))
            for i, t in enumerate(tiles):
                sheet.paste(t.convert("RGB"), ((i % 6) * 300, (i // 6) * 360))
            sheet.save(os.path.join(out, f"pose_{cid}.png"))


if __name__ == "__main__":
    main()
