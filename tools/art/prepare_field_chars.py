"""생성한 SD 전신 캐릭터 이미지(흰 배경) → 3D 필드용 투명 PNG.

    assets_src/characters/field/<id>.png  (1024x1024, 흰 배경)
        │  python tools/art/prepare_field_chars.py [--method rembg|white] [id ...]
        ▼
    assets/characters/field/<id>.png      (배경 투명, 여백 없이 잘라냄)
    assets/characters/field/manifest.json (크기·바라보는 방향)

처리 단계
 1) rembg 의 애니메이션 전용 모델(isnet-anime)로 전경 마스크 추출
    (설치: pip install "rembg[cpu]", 첫 실행 시 모델 176MB 자동 다운로드)
    --method white 를 주면 모델 없이 '테두리와 이어진 흰색' 을 지우는 방식만 사용
 2) 흰 배경이 반투명 경계에 섞여 생기는 흰 테두리 제거 (색 복원: c = (c - (1-a)·흰색) / a)
 3) 몸에서 떨어져 나온 작은 얼룩 제거 (가장 큰 덩어리 기준 1.5% 미만 삭제)
 4) 알파 기준으로 여백을 딱 맞게 잘라냄 (패딩 2px)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "assets_src", "characters", "field")
DST = os.path.join(ROOT, "assets", "characters", "field")
PROMPTS = os.path.join(ROOT, "data", "art_prompts", "field_chars.json")

_session = None


def mask_rembg(img: Image.Image) -> np.ndarray:
    global _session
    from rembg import new_session, remove
    if _session is None:
        _session = new_session("isnet-anime")
    m = remove(img.convert("RGB"), session=_session, only_mask=True, post_process_mask=False)
    return np.asarray(m, np.float32) / 255.0


def mask_white(img: Image.Image, tol=18.0) -> np.ndarray:
    """테두리와 연결된 흰색 영역만 배경으로 (캐릭터 안의 흰 옷·눈 하이라이트는 보존)"""
    sys.path.insert(0, os.path.join(ROOT, "tools", "art"))
    from process_assets import remove_background
    return np.asarray(remove_background(img, tolerance=tol), np.float32)[..., 3] / 255.0


def refine(rgb: np.ndarray, a: np.ndarray) -> np.ndarray:
    from scipy import ndimage
    # 생성 이미지의 바닥 그림자 제거: 캐릭터 아래쪽 14% 띠에서 '무채색이면서 반투명'인 픽셀 (게임이 그림자를 따로 깐다)
    rows = np.where((a > 0.5).any(axis=1))[0]
    if len(rows):
        top, bot = rows[0], rows[-1]
        band = np.zeros_like(a, bool)
        band[int(top + (bot - top) * 0.86):] = True
        neutral = (rgb.max(axis=2) - rgb.min(axis=2)) < 22
        a = np.where(band & neutral & (a < 0.9), 0.0, a)
    # 모델이 천·머리카락 안쪽을 반투명으로 판단해 배경이 비치는 것을 막는다 (가장자리 부드러움은 유지)
    a = np.clip((a - 0.12) / 0.5, 0, 1)
    # 3) 떨어진 얼룩 제거
    solid = a > 0.5
    lab, n = ndimage.label(solid)
    if n > 1:
        sizes = ndimage.sum(solid, lab, range(1, n + 1))
        keep = np.zeros(n + 1, bool)
        keep[1:] = sizes >= sizes.max() * 0.015        # 몸과 떨어진 작은 소품·얼룩 제거
        a = a * ndimage.binary_dilation(keep[lab], iterations=3)
    # 다리 사이·팔과 몸 사이처럼 몸에 둘러싸인 배경 구멍: 순백(≥252)이면서 일정 크기 이상인 덩어리는 배경
    # (눈 하이라이트처럼 작은 흰색, 음영이 들어간 흰 옷은 순백이 아니거나 작아서 남는다)
    pure = (rgb.min(axis=2) >= 252) & (a > 0.5)
    lab, n = ndimage.label(pure)
    if n:
        sizes = ndimage.sum(pure, lab, range(1, n + 1))
        min_area = a.size * 0.0006            # 1024² 기준 약 630px
        holes = np.zeros(n + 1, bool)
        holes[1:] = sizes >= min_area
        hole_mask = ndimage.binary_dilation(holes[lab], iterations=1)
        a = np.where(hole_mask, 0.0, a)
    # 생성 API 워터마크: 오른쪽 아래 영역 안에 '통째로' 들어 있는 조각만 지운다 (캐릭터 발과 이어져 있으면 보존)
    h, w = a.shape
    lab, n = ndimage.label(a > 0.3)
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        if sl and sl[0].start >= h * 0.86 and sl[1].start >= w * 0.55:
            a = np.where(lab == i, 0.0, a)
    # 순수 흰 배경에 가까운 거의-투명 픽셀은 완전 투명으로
    whiteness = rgb.min(axis=2) / 255.0
    a = np.where((a < 0.08) | ((a < 0.5) & (whiteness > 0.97)), 0.0, a)
    # 2) 흰 테두리 색 복원
    safe = np.maximum(a, 1e-3)[..., None]
    rgb = np.clip((rgb - (1 - a[..., None]) * 255.0) / safe, 0, 255)
    rgb = np.where(a[..., None] > 0, rgb, 0)
    return np.dstack([rgb, a * 255]).astype(np.uint8)


def trim(img: Image.Image, pad=2) -> Image.Image:
    bbox = img.getchannel("A").point(lambda v: 255 if v > 10 else 0).getbbox()
    if not bbox:
        return img
    l, t, r, b = bbox
    return img.crop((max(0, l - pad), max(0, t - pad), min(img.width, r + pad), min(img.height, b + pad)))


def process(cid, method, src_dir, dst_dir, crop_bottom=0.0):
    path = next((os.path.join(src_dir, cid + ext) for ext in (".png", ".jpg", ".jpeg", ".webp")
                 if os.path.exists(os.path.join(src_dir, cid + ext))), None)
    if not path:
        return None
    img = Image.open(path).convert("RGB")
    if crop_bottom > 0:      # 반신 초상화: 아래쪽 워터마크 띠를 통째로 잘라낸다 (몸과 붙어 있어도 확실히 제거)
        img = img.crop((0, 0, img.width, int(img.height * (1 - crop_bottom))))
    rgb = np.asarray(img, np.float32)
    a = mask_rembg(img) if method == "rembg" else mask_white(img)
    out = trim(Image.fromarray(refine(rgb, a), "RGBA"))
    os.makedirs(dst_dir, exist_ok=True)
    out.save(os.path.join(dst_dir, cid + ".png"), optimize=True)
    edge = np.asarray(out)[..., 3]
    print(f"  {cid:10s} {img.size[0]}x{img.size[1]} → {out.size[0]}x{out.size[1]}  (불투명 {np.mean(edge > 250):.0%})")
    return out.size


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--method", choices=["rembg", "white"], default="rembg")
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=DST)
    ap.add_argument("--crop-bottom", type=float, default=0.0, help="원본 아래쪽을 이 비율만큼 잘라냄 (초상화 0.06)")
    a = ap.parse_args()
    with open(PROMPTS, encoding="utf-8") as f:
        P = json.load(f)
        chars = {**P["characters"], **P.get("monsters", {})}
    ids = a.ids or list(chars)
    man_path = os.path.join(a.out, "manifest.json")
    manifest = {}
    if os.path.exists(man_path):
        with open(man_path, encoding="utf-8") as f:
            manifest = json.load(f)
    done, missing = [], []
    for cid in ids:
        size = process(cid, a.method, a.src, a.out, a.crop_bottom)
        if size is None:
            missing.append(cid)
            continue
        desc = chars.get(cid, {}).get("description", "")
        faces = "left" if "facing left" in desc else "right" if "facing right" in desc else "front"
        manifest[cid] = {"size": list(size), "faces": faces}
        done.append(cid)
    if done:
        with open(man_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"처리 {len(done)}개 → {a.out}")
    if missing:
        print(f"원본 없음 ({len(missing)}): {', '.join(missing)}  ← {a.src}/<id>.png 로 넣어 주세요")


if __name__ == "__main__":
    main()
