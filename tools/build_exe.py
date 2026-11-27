"""단일 실행 파일 빌드.

    pip install -r requirements.txt pyinstaller
    python tools/build_exe.py

1) 루크 SD 일러스트로 아이콘(build_assets/icon.ico) 생성
2) Arcturus_RPG.spec 으로 PyInstaller 실행
결과: dist/Arcturus_RPG.exe (Windows 에서 빌드한 경우)

PyInstaller 는 크로스 컴파일을 지원하지 않으므로 .exe 는 Windows 에서 빌드해야 한다.
(이 저장소의 GitHub Actions 워크플로 .github/workflows/build-windows.yml 이 자동으로 해 준다.)
"""
import os
import subprocess
import sys

from PIL import Image

# 영어권 Windows 콘솔(cp1252)에서도 한글 출력이 죽지 않도록 UTF-8 로 고정
for stream in (sys.stdout, sys.stderr):
    if stream is not None and hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def make_icon():
    """3D 필드용 루크 SD 일러스트로 아이콘(build_assets/icon.ico) 생성"""
    out_dir = os.path.join(ROOT, "build_assets")
    os.makedirs(out_dir, exist_ok=True)
    luke = Image.open(os.path.join(ROOT, "assets", "characters", "field", "luke.png")).convert("RGBA")
    head = luke.crop((0, 0, luke.width, min(luke.height, luke.width)))     # 위쪽 정사각형 (얼굴·상반신)
    head.thumbnail((232, 232), Image.LANCZOS)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    disc = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    from PIL import ImageDraw
    ImageDraw.Draw(disc).ellipse([4, 4, 252, 252], fill=(38, 44, 66, 255), outline=(226, 184, 102, 255), width=8)
    base.alpha_composite(disc)
    base.alpha_composite(head, ((256 - head.width) // 2, 256 - head.height - 8))
    path = os.path.join(out_dir, "icon.ico")
    base.save(path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("아이콘:", path)


def main():
    make_icon()
    subprocess.check_call([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                           os.path.join(ROOT, "Arcturus_RPG.spec")], cwd=ROOT)
    name = "Arcturus_RPG.exe" if os.name == "nt" else "Arcturus_RPG"
    path = os.path.join(ROOT, "dist", name)
    print(f"\n완료: {path}  ({os.path.getsize(path) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
