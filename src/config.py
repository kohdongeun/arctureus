"""전역 설정과 경로."""
import os
import sys

# PyInstaller 단일 실행 파일로 실행 중이면 에셋이 풀린 임시 폴더(sys._MEIPASS)가 기준
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    ROOT = sys._MEIPASS
else:
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
ASSETS = os.path.join(ROOT, "assets")
IMAGES = os.path.join(ASSETS, "images")
SOUNDS = os.path.join(ASSETS, "sounds")
FONTS = os.path.join(ASSETS, "fonts")

SCREEN_W, SCREEN_H = 1280, 720
FPS = 60
TITLE = "황동의 심장 : 아스카론 연대기"

# 아이소메트릭 (화면 픽셀)
TILE_W, TILE_H = 64, 32
BLOCK_H = 32

# 방향: 그리드 이동량 (x 증가 = 화면 오른쪽 아래, y 증가 = 화면 왼쪽 아래)
DIRS = {"ne": (0, -1), "se": (1, 0), "sw": (0, 1), "nw": (-1, 0)}
DIR_ROW = {"se": 0, "sw": 1, "ne": 2, "nw": 3}   # 캐릭터 시트 행

# 팔레트 (story.json art_direction 과 동일)
C = {
    "brass": (181, 132, 58), "brass_light": (226, 184, 102), "copper": (176, 96, 58),
    "iron": (90, 95, 102), "soot": (42, 37, 34), "steam": (232, 228, 218),
    "ether": (95, 227, 224), "ether_deep": (42, 143, 158), "rust": (162, 74, 38),
    "parchment": (234, 219, 184), "navy": (27, 34, 56), "red": (158, 43, 43),
    "white": (250, 248, 240), "black": (12, 10, 14), "ink": (52, 36, 28),
    "hp": (214, 70, 60), "mp": (70, 190, 230), "atb": (232, 190, 90), "gray": (130, 130, 140),
}
