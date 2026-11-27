"""별이 지는 해 : 레비안 연대기 - 진입점 (엔진 구현 전 임시 버전)."""
import json
import os
import sys

import pygame

ROOT = os.path.dirname(os.path.abspath(__file__))
SCREEN_SIZE = (1280, 720)


def load_story():
    with open(os.path.join(ROOT, "data", "story.json"), encoding="utf-8") as f:
        return json.load(f)


def main():
    story = load_story()
    pygame.init()
    screen = pygame.display.set_mode(SCREEN_SIZE)
    pygame.display.set_caption(story["meta"]["title"])
    clock = pygame.time.Clock()

    # --smoke: 몇 프레임만 돌고 종료 (CI/헤드리스 확인용)
    frames = 3 if "--smoke" in sys.argv else None
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        screen.fill((12, 14, 32))
        pygame.display.flip()
        clock.tick(60)
        if frames is not None:
            frames -= 1
            running = frames > 0
    pygame.quit()
    print(f"OK: '{story['meta']['title']}' - 챕터 {len(story['chapters'])}개 로드")


if __name__ == "__main__":
    main()
