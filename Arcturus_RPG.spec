# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 빌드 설정: 모든 그래픽·사운드·폰트·데이터를 단일 실행 파일에 포함
#   python tools/build_exe.py   (아이콘 생성 후 이 spec 으로 빌드)
# 결과: dist/Arcturus_RPG.exe (Windows) / dist/Arcturus_RPG (Linux·macOS)
import os
import sys

ROOT = os.path.abspath(SPECPATH)

datas = []
for top in ("assets", "data"):
    for dirpath, _, files in os.walk(os.path.join(ROOT, top)):
        for f in files:
            if f.startswith(".") or f == "manifest.json" and "images" not in dirpath:
                continue
            src = os.path.join(dirpath, f)
            datas.append((src, os.path.relpath(dirpath, ROOT)))

icon = os.path.join(ROOT, "build_assets", "icon.ico")

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    datas=datas,
    hiddenimports=[],
    excludes=["numpy", "PIL", "tkinter", "unittest", "pydoc", "test"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Arcturus_RPG",
    console=False,          # 더블클릭 시 검은 콘솔 창 없이 게임 창만
    icon=icon if os.path.exists(icon) else None,
    upx=False,
    strip=False,
    runtime_tmpdir=None,
)
