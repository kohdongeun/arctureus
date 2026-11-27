"""황동의 심장 : 아스카론 연대기 — 이전 2D(pygame) 버전 진입점. 본편은 main.py (3D).

    python main2d.py            # 2D 버전 실행
    python main2d.py --smoke    # 타이틀 → 새 게임 → 필드 진입까지 자동 확인 후 종료 (빌드 검증용)
    python tools/autotest.py  # 자동 플레이 테스트 (스크린샷 저장)
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 영어권 Windows 콘솔(cp1252)에서 한글 출력 때문에 죽지 않도록 UTF-8 로 고정
# (PyInstaller 로 묶인 exe 는 PYTHONUTF8 환경변수를 따르지 않음)
for _s in (sys.stdout, sys.stderr):
    if _s is not None and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

import pygame  # noqa: E402

from src.engine.core import Game  # noqa: E402
from src.scenes.title import TitleScene  # noqa: E402


def init():
    pygame.mixer.pre_init(44100, -16, 2, 1024)
    pygame.init()
    try:
        pygame.mixer.init(44100, -16, 2, 1024)
    except pygame.error:
        pass  # 사운드 장치가 없어도 게임은 실행


def smoke():
    """창 없이도 돌 수 있는 빌드 검증: 에셋 로드·장면 전환이 되는지 확인"""
    from src.scenes.field import FieldScene
    game = Game()
    game.push(TitleScene(game))
    for i in range(240):
        game.input.begin_frame()
        pygame.event.pump()
        if i == 60:
            game.input.press("confirm")
        game.tick(1 / 60)
    ok = any(isinstance(s, FieldScene) for s in game.scenes)
    n_img = len(os.listdir(os.path.join(sys.modules["src.config"].IMAGES, "tiles")))
    print(f"smoke: {'OK' if ok else 'FAIL'} (field={ok}, tiles={n_img}, audio={game.audio.enabled})")
    return 0 if ok else 1


def log_crash():
    """창 모드 실행 파일은 오류 메시지가 보이지 않으므로 실행 파일 옆(실패 시 홈 폴더)에 기록"""
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    for d in (base, os.path.expanduser("~")):
        try:
            path = os.path.join(d, "Arcturus_RPG_error.log")
            with open(path, "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
            return path
        except OSError:
            continue
    return None


def main():
    try:
        init()
        if "--smoke" in sys.argv:
            code = smoke()
            pygame.quit()
            sys.exit(code)
        game = Game()
        game.push(TitleScene(game))
        game.run()
        pygame.quit()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        path = log_crash()
        traceback.print_exc()
        sys.exit(f"오류가 발생했습니다. 기록: {path}")


if __name__ == "__main__":
    main()
