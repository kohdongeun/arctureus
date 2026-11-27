"""황동의 심장 : 아스카론 연대기 — 실행 진입점.

    python main.py            # 게임 실행
    python tools/autotest.py  # 자동 플레이 테스트 (스크린샷 저장)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame  # noqa: E402

from src.engine.core import Game  # noqa: E402
from src.scenes.title import TitleScene  # noqa: E402


def main():
    pygame.mixer.pre_init(22050, -16, 1, 512)
    pygame.init()
    try:
        pygame.mixer.init(22050, -16, 1, 512)
    except pygame.error:
        pass  # 사운드 장치가 없어도 게임은 실행
    game = Game()
    game.push(TitleScene(game))
    game.run()
    pygame.quit()


if __name__ == "__main__":
    main()
