"""원본 이미지 → 게임용 에셋 변환 파이프라인.

assets_src/raw/<카테고리>/ 에 넣은 이미지를
  1) (카테고리에 따라) 배경 제거(누끼) → 투명 PNG
  2) data/story.json 의 art_direction 규격에 맞게 리사이징
  3) assets/images/<카테고리>/ 에 저장
하고 assets/images/manifest.json 을 갱신한다.

사용법:
    python tools/art/process_assets.py                 # 전체 처리
    python tools/art/process_assets.py --only portraits
    python tools/art/process_assets.py --tolerance 40  # 허용치 수동 지정 (기본: 자동)

배경 제거 방식:
  - 기본: 테두리 픽셀로 배경색을 추정하고, 테두리와 연결된 비슷한 색 영역만
    지운다(flood fill). 캐릭터 안쪽의 흰 옷 등은 테두리와 끊겨 있으면 보존된다.
    가장자리는 부드럽게 페더링하고 배경색 번짐(halo)을 제거한다.
  - rembg 가 설치되어 있으면 --rembg 옵션으로 AI 누끼를 쓸 수 있다
    (pip install rembg; 첫 실행 시 모델 다운로드 필요).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "assets_src", "raw")
DST = os.path.join(ROOT, "assets", "images")
EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")

# 카테고리별 규격. mode: fit(비율 유지, 박스 안), cover(꽉 채우고 잘라냄), height(높이 맞춤)
CATEGORIES = {
    # 대화창 초상화: art_direction.portrait_spec = 256x256
    "portraits": {"remove_bg": True, "outputs": [
        {"suffix": "", "mode": "fit", "size": (256, 256)},
        {"suffix": "_large", "mode": "height", "size": (None, 640)},  # 컷신용 상반신
    ]},
    # 3D 버전 대화창 스탠딩 일러스트 (우측 하단, 높이 924) → 파일명 stand_<id>_<emotion>
    "standing": {"remove_bg": True, "outputs": [
        {"suffix": "", "mode": "height", "size": (None, 924)},
    ]},
    # 쿼터뷰 배경: 내부 해상도 1280x720
    "backgrounds": {"remove_bg": False, "outputs": [
        {"suffix": "", "mode": "cover", "size": (1280, 720)},
    ]},
    # 몬스터: 일반 128, 보스 256 (파일명에 boss_ 가 있으면 보스 규격)
    "monsters": {"remove_bg": True, "outputs": [
        {"suffix": "", "mode": "fit", "size": (128, 128), "boss_size": (256, 256)},
    ]},
    # UI 창: 투명화 후 원본 비율 유지, 최대 1280x720 안에 맞춤
    "ui": {"remove_bg": True, "outputs": [
        {"suffix": "", "mode": "fit", "size": (1280, 720), "no_upscale": True},
    ]},
}


# ---------------------------------------------------------------- 배경 제거
def estimate_bg(rgb: np.ndarray) -> np.ndarray:
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    return np.median(border, axis=0)


def auto_tolerance(rgb: np.ndarray, bg: np.ndarray) -> float:
    """테두리 픽셀이 배경색에서 얼마나 흔들리는지(노이즈, JPEG 손실, 그라데이션)로 허용치를 정한다.
    단색 배경이면 작게 잡혀 배경과 비슷한 밝은 옷/머리카락이 지워지지 않는다.
    대상(옷자락 등)이 테두리에 닿아 있어도 흔들리지 않도록 중앙값 기준으로 계산한다."""
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    bd = np.sqrt(((border - bg) ** 2).sum(axis=-1))
    return float(np.clip(np.median(bd) * 4 + 8, 8, 60))


def remove_background(img: Image.Image, tolerance: float | None = None, feather: float = 0.7) -> Image.Image:
    img = img.convert("RGBA")
    arr = np.asarray(img).astype(np.float32)
    rgb, alpha = arr[..., :3], arr[..., 3]
    h, w = alpha.shape

    # 이미 투명 배경이면 그대로
    if (alpha < 250).mean() > 0.05:
        return img

    bg = estimate_bg(rgb)
    if tolerance is None:
        tolerance = auto_tolerance(rgb, bg)
    dist = np.sqrt(((rgb - bg) ** 2).sum(axis=-1))

    # 1) 배경 후보(색이 비슷한 픽셀) 마스크 → 테두리에서 flood fill 로 연결 영역만 선택
    # .copy() 필수: Pillow 13의 fromarray 는 numpy 버퍼를 공유하는 읽기 전용 이미지를 돌려주며,
    # 그 위에 floodfill 하면 오류 없이 아무것도 칠해지지 않는다.
    cand = Image.fromarray(np.where(dist <= tolerance, 255, 0).astype(np.uint8), "L").copy()
    for x in range(0, w, max(1, w // 64)):
        for y in (0, h - 1):
            if cand.getpixel((x, y)) == 255:
                ImageDraw.floodfill(cand, (x, y), 128)
    for y in range(0, h, max(1, h // 64)):
        for x in (0, w - 1):
            if cand.getpixel((x, y)) == 255:
                ImageDraw.floodfill(cand, (x, y), 128)
    connected = np.asarray(cand) == 128

    # 2) 배경 영역은 완전 투명. 그 바깥 경계 띠(안티에일리어싱으로 배경색이 섞인 픽셀)만
    #    (3px: JPEG 압축 잔상까지 포함) 색 거리에 비례해 반투명으로 → 노이즈 얼룩 없이 부드러운 가장자리
    conn_img = Image.fromarray(connected.astype(np.uint8) * 255, "L").copy()
    band = (np.asarray(conn_img.filter(ImageFilter.MaxFilter(7))) > 0) & ~connected
    edge_alpha = np.clip((dist - tolerance) / (tolerance * 3), 0.0, 1.0)
    a = np.where(connected, 0.0, np.where(band, edge_alpha, 1.0))

    # 3) 가장자리 페더링 (배경 영역은 다시 0으로 고정)
    if feather > 0:
        a_img = Image.fromarray((a * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(feather))
        a = np.minimum(np.asarray(a_img).astype(np.float32) / 255.0, np.where(band, 1.0, a))
        a = np.where(connected, 0.0, a)

    # 4) 배경색 번짐 제거: c = (c - (1-a)*bg) / a
    safe = np.maximum(a, 1e-3)[..., None]
    rgb_out = np.clip((rgb - (1 - a[..., None]) * bg) / safe, 0, 255)
    rgb_out = np.where(a[..., None] > 0.02, rgb_out, 0)

    out = np.dstack([rgb_out, a * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def remove_background_rembg(img: Image.Image) -> Image.Image:
    from rembg import remove  # 선택 의존성
    return remove(img.convert("RGBA"))


def trim(img: Image.Image, pad: int = 4) -> Image.Image:
    bbox = img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if not bbox:
        return img
    l, t, r, b = bbox
    return img.crop((max(0, l - pad), max(0, t - pad), min(img.width, r + pad), min(img.height, b + pad)))


# ---------------------------------------------------------------- 리사이징
def resize(img: Image.Image, mode: str, size, no_upscale: bool = False) -> Image.Image:
    tw, th = size
    if mode == "height":
        scale = th / img.height
    elif mode == "cover":
        scale = max(tw / img.width, th / img.height)
    else:  # fit
        scale = min(tw / img.width, th / img.height)
    if no_upscale:
        scale = min(scale, 1.0)
    nw, nh = max(1, round(img.width * scale)), max(1, round(img.height * scale))
    out = img.resize((nw, nh), Image.LANCZOS)

    if mode == "cover":
        l, t = (nw - tw) // 2, (nh - th) // 2
        out = out.crop((l, t, l + tw, t + th))
    elif mode == "fit" and not no_upscale:
        # 정사각 캔버스 중앙 하단 정렬 (초상화/몬스터 발 위치 통일)
        canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        canvas.paste(out, ((tw - nw) // 2, th - nh), out)
        out = canvas
    return out


# ---------------------------------------------------------------- 메인
def process(only=None, tolerance=None, use_rembg=False):
    manifest_path = os.path.join(DST, "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

    count = 0
    for cat, spec in CATEGORIES.items():
        if only and cat not in only:
            continue
        src_dir = os.path.join(SRC, cat)
        if not os.path.isdir(src_dir):
            continue
        dst_dir = os.path.join(DST, cat)
        os.makedirs(dst_dir, exist_ok=True)

        for name in sorted(os.listdir(src_dir)):
            if not name.lower().endswith(EXTS):
                continue
            stem = os.path.splitext(name)[0]
            img = Image.open(os.path.join(src_dir, name))
            img.load()

            if spec["remove_bg"]:
                img = remove_background_rembg(img) if use_rembg else remove_background(img, tolerance)
                img = trim(img)
            else:
                img = img.convert("RGB")

            for o in spec["outputs"]:
                size = o.get("boss_size", o["size"]) if stem.startswith("boss_") and "boss_size" in o else o["size"]
                out = resize(img, o["mode"], size, o.get("no_upscale", False))
                rel = f"{cat}/{stem}{o['suffix']}.png"
                out.save(os.path.join(DST, rel), optimize=True)
                manifest[rel] = {"category": cat, "size": list(out.size), "source": f"assets_src/raw/{cat}/{name}",
                                 "transparent": spec["remove_bg"]}
                print(f"  {rel:48s} {out.size[0]}x{out.size[1]}")
                count += 1

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(manifest.items())), f, ensure_ascii=False, indent=2)
    print(f"완료: {count}개 파일 → assets/images/ (manifest.json 갱신)")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", nargs="*", choices=list(CATEGORIES))
    p.add_argument("--tolerance", type=float, default=None, help="배경색 판정 허용치 (기본: 배경 노이즈로 자동 계산, 6~60)")
    p.add_argument("--rembg", action="store_true", help="rembg AI 누끼 사용 (별도 설치 필요)")
    a = p.parse_args()
    if a.rembg:
        try:
            import rembg  # noqa: F401
        except ImportError:
            sys.exit("rembg 미설치: pip install rembg")
    process(a.only, a.tolerance, a.rembg)
