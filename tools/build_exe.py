"""단일 실행 파일 빌드.

    pip install -r requirements.txt pyinstaller
    python tools/build_exe.py

1) 루크 도트 스프라이트로 아이콘(build_assets/icon.ico) 생성
2) Arcturus_RPG.spec 으로 PyInstaller 실행
결과: dist/Arcturus_RPG.exe (Windows 에서 빌드한 경우)

PyInstaller 는 크로스 컴파일을 지원하지 않으므로 .exe 는 Windows 에서 빌드해야 한다.
(이 저장소의 GitHub Actions 워크플로 .github/workflows/build-windows.yml 이 자동으로 해 준다.)
"""
import os
import subprocess
import sys

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def make_icon():
    out_dir = os.path.join(ROOT, "build_assets")
    os.makedirs(out_dir, exist_ok=True)
    sheet = Image.open(os.path.join(ROOT, "assets", "images", "characters", "chr_luke.png")).convert("RGBA")
    frame = sheet.crop((0, 0, 48, 72)).crop((0, 0, 48, 48))      # 남동 방향 정면, 상반신
    base = Image.new("RGBA", (48, 48), (27, 34, 56, 255))
    base.alpha_composite(frame)
    big = base.resize((256, 256), Image.NEAREST)
    path = os.path.join(out_dir, "icon.ico")
    big.save(path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
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
