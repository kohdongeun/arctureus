"""Pollinations 이미지 API 로 캐릭터·텍스처 원본을 생성한다.

    python tools/art/gen_ai_assets.py field [id ...]      → assets_src/characters/field/<id>.png
    python tools/art/gen_ai_assets.py portrait [id ...]   → assets_src/characters/portrait/<id>.png
    python tools/art/gen_ai_assets.py texture [name ...]  → assets/images/textures3d/tile_<name>.jpg (이음매 없이 가공)

프롬프트: data/art_prompts/field_chars.json
- 무료 API 한도(503/429)에 걸리면 기다렸다가 다시 시도한다.
- 무료 API 는 오른쪽 아래에 워터마크를 넣는다. 캐릭터는 누끼 단계(prepare_field_chars.py)에서
  그 영역 안에만 있는 떨어진 조각을 지우고, 텍스처는 아래 띠를 잘라 낸다.
- 텍스처는 반쯤 밀어 겹친 사본을 가장자리에서 섞어 이음매 없이 타일링되게 만든다.
- 생성 결과(시드·프롬프트)는 같은 폴더의 generation_log.json 에 남는다.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROMPTS = os.path.join(ROOT, "data", "art_prompts", "field_chars.json")
API = "https://image.pollinations.ai/prompt/"
SEEDS = {"field": 1200, "portrait": 3400, "texture": 5600}


def fetch(prompt, w, h, seed, tries=12):
    q = urllib.parse.urlencode({"width": w, "height": h, "seed": seed, "model": "flux", "nologo": "true",
                                "enhance": "false"})
    url = API + urllib.parse.quote(prompt) + "?" + q
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "game-asset-tool"}),
                                        timeout=240) as r:
                data = r.read()
                if r.headers.get("Content-Type", "").startswith("image/"):
                    return Image.open(io.BytesIO(data)).convert("RGB")
                err = data[:160]
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            err = repr(e)[:160]
        wait = 12 + i * 6
        print(f"    재시도 {i + 1}/{tries} ({err}) {wait}초 대기", flush=True)
        time.sleep(wait)
    raise RuntimeError("이미지 생성 실패: " + prompt[:60])


def whiten_watermark(img: Image.Image) -> Image.Image:
    """오른쪽 아래 워터마크 영역을 흰색으로 (캐릭터는 프롬프트로 가운데에 배치)"""
    w, h = img.size
    d = ImageDraw.Draw(img)
    d.rectangle([int(w * 0.62), int(h * 0.90), w, h], fill=(255, 255, 255))
    return img


def make_seamless(img: Image.Image, blend=0.22) -> Image.Image:
    a = np.asarray(img, np.float32)
    h, w, _ = a.shape
    b = np.roll(np.roll(a, h // 2, axis=0), w // 2, axis=1)
    # 가장자리로 갈수록 반쯤 민 사본(b)의 비중을 높인다 → 사본의 가운데(이음매 없는 부분)가 가장자리를 채움
    yy = np.minimum(np.arange(h), h - 1 - np.arange(h)) / (h * blend)
    xx = np.minimum(np.arange(w), w - 1 - np.arange(w)) / (w * blend)
    m = np.clip(np.minimum(yy[:, None], xx[None, :]), 0, 1)[..., None]
    out = a * m + b * (1 - m)
    return Image.fromarray(out.astype(np.uint8))


def main():
    kind = sys.argv[1]
    names = sys.argv[2:]
    with open(PROMPTS, encoding="utf-8") as f:
        P = json.load(f)
    if kind in ("field", "portrait"):
        out_dir = os.path.join(ROOT, "assets_src", "characters", kind)
        items = {k: v["description"] for k, v in P["characters"].items()}
    elif kind == "texture":
        out_dir = os.path.join(ROOT, "assets", "images", "textures3d")
        items = P["textures"]
    else:
        sys.exit("kind: field | portrait | texture")
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir if kind != "texture" else out_dir, "generation_log.json")
    log = json.load(open(log_path, encoding="utf-8")) if os.path.exists(log_path) else {}
    for i, (name, desc) in enumerate(items.items()):
        if names and name not in names:
            continue
        seed = SEEDS[kind] + i
        if kind == "field":
            # 무료 모델은 앞쪽 단어를 강하게 따르므로 SD 비율을 맨 앞에 둔다 (스타일 문구는 뒤에 그대로 포함)
            prompt = (f"super deformed chibi figure, big head, tiny body, 3 heads tall, cute SD anime game character, "
                      f"{desc}, full body standing, single character centered, {P['style']}")
            w, h = 1024, 1024
        elif kind == "portrait":
            desc = desc.replace("full body", "").replace("three-quarter view facing right", "").replace(
                "three-quarter view facing left", "")
            prompt = f"{P['portrait_style']}, {desc}, single character, upper body centered"
            w, h = 1024, 1024
        else:
            prompt = desc
            w, h = 1024, 1024
        print(f"  [{kind}] {name} (seed {seed}) 생성 중...", flush=True)
        t0 = time.time()
        img = fetch(prompt, w, h, seed)
        if kind == "texture":
            # 워터마크가 있는 아래 띠를 잘라 낸 뒤 이음매 없이
            img = img.crop((0, 0, w, int(h * 0.88))).resize((w, h), Image.LANCZOS)
            img = make_seamless(img)
            path = os.path.join(out_dir, f"tile_{name}.jpg")
            img.save(path, quality=92)
        else:
            path = os.path.join(out_dir, f"{name}.png")
            img.save(path)
        log[name] = {"seed": seed, "prompt": prompt, "model": "flux", "seconds": round(time.time() - t0, 1)}
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=1)
        print(f"    → {os.path.relpath(path, ROOT)} ({time.time() - t0:.0f}초)", flush=True)
        time.sleep(4)


if __name__ == "__main__":
    main()
