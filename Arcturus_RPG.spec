# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 빌드 설정 (3D 버전: ursina + Panda3D): 그래픽·사운드·폰트·데이터를 단일 실행 파일에 포함
#   python tools/build_exe.py   (아이콘 생성 후 이 spec 으로 빌드)
# 결과: dist/Arcturus_RPG.exe (Windows) / dist/Arcturus_RPG (Linux·macOS)
#
# Panda3D·ursina 용 PyInstaller 훅이 따로 없으므로 여기서 직접 모은다:
#   - panda3d 의 렌더러/오디오 플러그인(libpandagl, p3openal_audio …)은 실행 중에 동적으로 불러오므로
#     panda3d/ 폴더 구조 그대로 binaries 에 넣고, main.py 의 frozen_setup() 이 plugin-path 를 지정한다
#   - ursina 의 기본 모델·셰이더·폰트 파일, 동적으로 import 되는 prefab 모듈
import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = os.path.abspath(SPECPATH)

SKIP_DIRS = {os.path.join("assets", "bgm", "midi")}      # 작곡 원본(MIDI)은 게임에 필요 없음

datas = []
for top in ("assets", "data"):
    for dirpath, _, files in os.walk(os.path.join(ROOT, top)):
        rel = os.path.relpath(dirpath, ROOT)
        if any(rel == d or rel.startswith(d + os.sep) for d in SKIP_DIRS):
            continue
        for f in files:
            if f.startswith("."):
                continue
            datas.append((os.path.join(dirpath, f), rel))

datas += collect_data_files("ursina", excludes=["**/__pycache__", "**/*.blend", "**/*.blend1"])
datas += collect_data_files("panda3d", includes=["etc/*", "models/**"])
binaries = collect_dynamic_libs("panda3d")


def _keep(name):
    return not any(k in name for k in (".editor", ".test", "_test", ".samples"))


hiddenimports = (collect_submodules("ursina", filter=_keep) + collect_submodules("direct", filter=_keep)
                 + ["panda3d.core", "panda3d.direct", "panda3d.physics", "panda3d.fx", "panda3d.egg"])

icon = os.path.join(ROOT, "build_assets", "icon.ico")

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "unittest", "pydoc", "test", "pygame", "rembg", "onnxruntime", "scipy", "matplotlib",
              "IPython", "ursina.editor"],
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
