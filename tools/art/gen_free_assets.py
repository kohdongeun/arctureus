"""무료(키·잔액 불필요) 이미지 생성: 구버전 Pollinations 공개 엔드포인트 image.pollinations.ai/prompt/...

    python tools/art/gen_free_assets.py field [id ...]      → assets_src/characters/field/<id>.png
    python tools/art/gen_free_assets.py portrait [id ...]   → assets_src/characters/portrait/<id>.png
    python tools/art/gen_free_assets.py monster [id ...]    → assets_src/monsters/<id>.png
    python tools/art/gen_free_assets.py prompts             → 무료 웹 AI 에 직접 붙여 넣을 프롬프트 목록 출력

- 유료 엔드포인트(gen.pollinations.ai)는 쓰지 않는다.
- 무료 엔드포인트는 768px, 오른쪽 아래 워터마크, 배경 도형·잘린 구도가 섞여 나오므로
  캐릭터마다 후보를 최대 3장 만들고 '테두리가 흰색인지 + 배경 제거 후 인물이 잘리지 않았는지'로 가장 나은 것을 고른다.
- 그림체 통일 키워드: anime style, 2d game character sprite, clean lineart, solid white background
- 워터마크는 prepare_field_chars.py 가 오른쪽 아래 영역의 떨어진 조각으로 보고 지운다.
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
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROMPTS = os.path.join(ROOT, "data", "art_prompts", "field_chars.json")
API = "https://image.pollinations.ai/prompt/"
KEYWORDS = "anime style, 2d game character sprite, clean lineart, solid white background"
NEG_HINT = "isolated on plain white, simple background, no scenery, no shapes behind, no text"
HEROES = ("luke", "iris", "zed")


def prompt_for(kind, desc, hint=""):
    if kind == "monster":
        return (f"anime style, 2000s JRPG battle monster sprite, {desc}, full body entirely visible, centered, "
                f"clean dark lineart, cel shading, dramatic colors, single monster only, {NEG_HINT}")
    if hint and kind == "portrait":
        desc = f"{hint}, {desc}"
    desc = desc.replace(", three-quarter view facing right", "").replace(", three-quarter view facing left", "")
    if kind == "field":
        return (f"{KEYWORDS}, cute chibi, big head small body, 3 heads tall, SD anime character, {desc}, "
                f"full body standing with feet visible, flat cel shading, vibrant colors, {NEG_HINT}")
    desc = desc.replace("full body", "")
    return (f"{KEYWORDS}, 2000s anime RPG character portrait, half body waist-up, beautiful detailed anime face, "
            f"{desc}, soft cel shading, facing slightly left, {NEG_HINT}")


def fetch(prompt, seed, tries=14):
    q = urllib.parse.urlencode({"width": 1024, "height": 1024, "seed": seed, "model": "flux", "nologo": "true"})
    url = API + urllib.parse.quote(prompt) + "?" + q
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "game-asset-tool"})
            with urllib.request.urlopen(req, timeout=240) as r:
                if r.headers.get("Content-Type", "").startswith("image/"):
                    return Image.open(io.BytesIO(r.read())).convert("RGB")
                err = "non-image"
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            err = repr(e)[:80]
        wait = min(60, 10 + i * 5)
        print(f"      무료 한도 대기 {i + 1}/{tries} ({err}) {wait}초", flush=True)
        time.sleep(wait)
    return None


_session = None


def score(img, kind):
    """높을수록 좋음: 테두리 흰색 비율 + 인물이 가장자리에 잘리지 않음"""
    global _session
    from rembg import new_session, remove
    if _session is None:
        _session = new_session("isnet-anime")
    a = np.asarray(img, np.float32)
    h, w, _ = a.shape
    border = np.concatenate([a[:8].reshape(-1, 3), a[-int(h * 0.12):-int(h * 0.1)].reshape(-1, 3),
                             a[:, :8].reshape(-1, 3), a[:, -8:].reshape(-1, 3)])
    white = float(np.mean(border.min(axis=1) > 225))
    m = np.asarray(remove(img, session=_session, only_mask=True), np.float32) / 255 > 0.5
    ys, xs = np.where(m)
    if len(xs) < 2000:
        return -1.0, "인물 없음"
    edge = 0.02
    cut = [xs.min() < w * edge, xs.max() > w * (1 - edge), ys.min() < h * edge]
    if kind == "field":
        cut.append(ys.max() > h * 0.86)            # 발이 워터마크 띠까지 내려오면 잘린 것으로
    fill = m.mean()
    s = white * 1.0 - sum(cut) * 0.6 - (0.4 if fill > 0.55 else 0)
    return s, f"흰테두리 {white:.0%}, 잘림 {sum(cut)}, 차지 {fill:.0%}"


def main():
    kind = sys.argv[1]
    with open(PROMPTS, encoding="utf-8") as f:
        P = json.load(f)
    chars = P["monsters"] if kind == "monster" else P["characters"]
    if kind == "prompts":
        for k in ("field", "portrait"):
            print(f"\n## {k}  (파일명: assets_src/characters/{k}/<id>.png, 1024x1024, 흰 배경)")
            for cid, c in chars.items():
                print(f"- {cid}.png  [{c['name']}]\n  {prompt_for(k, c['description'])}")
        return
    names = sys.argv[2:] or [c for c in chars if not (kind == "field" and c in HEROES)]
    out_dir = os.path.join(ROOT, "assets_src", "monsters" if kind == "monster" else "characters/" + kind)
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir, "generation_log.json")
    log = json.load(open(log_path, encoding="utf-8")) if os.path.exists(log_path) else {}
    base = {"field": 7100, "portrait": 8300, "monster": 9100}[kind] + int(os.environ.get("SEED_SHIFT", "0"))
    for idx, cid in enumerate(chars):
        if cid not in names:
            continue
        prompt = prompt_for(kind, chars[cid]["description"], chars[cid].get("portrait_hint", ""))
        best = None
        for cand in range(3):
            seed = base + idx * 10 + cand
            print(f"  [{kind}] {cid} 후보 {cand + 1} (seed {seed})", flush=True)
            img = fetch(prompt, seed)
            if img is None:
                continue
            s, why = score(img, kind)
            print(f"      점수 {s:.2f} ({why})", flush=True)
            if best is None or s > best[0]:
                best = (s, seed, img, why)
            if s >= 0.8:                              # 충분히 좋으면 더 만들지 않음
                break
            time.sleep(3)
        if not best:
            print(f"    ✗ {cid}: 생성 실패", flush=True)
            continue
        s, seed, img, why = best
        img.save(os.path.join(out_dir, f"{cid}.png"))
        log[cid] = {"seed": seed, "prompt": prompt, "endpoint": "image.pollinations.ai (free)", "score": round(s, 2),
                    "why": why}
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=1)
        print(f"    ✓ {cid}.png (점수 {s:.2f})", flush=True)


if __name__ == "__main__":
    main()
