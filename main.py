"""황동의 심장 : 아스카론 연대기 — 실행 진입점.

    python main.py            # 게임 실행
    python main.py --smoke    # 타이틀 → 새 게임 → 필드 진입까지 자동 확인 후 종료 (빌드 검증용)
    python tools/autotest.py  # 자동 플레이 테스트 (스크린샷 저장)
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame  # noqa: E402

from src.engine.core import Game  # noqa: E402
from src.scenes.title import TitleScene  # noqa: E402


def init():
    pygame.mixer.pre_init(22050, -16, 1, 512)
    pygame.init()
    try:
        pygame.mixer.init(22050, -16, 1, 512)
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
    print(f"smoke: {'OK' if ok else 'FAIL'} (필드 진입={ok}, 타일 이미지 {n_img}개, 오디오={game.audio.enabled})")
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
