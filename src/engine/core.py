"""게임 루프, 장면 스택, 입력."""
from __future__ import annotations

import pygame

from src import config as cfg
from src.engine import assets

KEYMAP = {
    pygame.K_UP: "up", pygame.K_DOWN: "down", pygame.K_LEFT: "left", pygame.K_RIGHT: "right",
    pygame.K_w: "up", pygame.K_s: "down", pygame.K_a: "left", pygame.K_d: "right",
    pygame.K_z: "confirm", pygame.K_RETURN: "confirm", pygame.K_SPACE: "confirm", pygame.K_KP_ENTER: "confirm",
    pygame.K_x: "cancel", pygame.K_ESCAPE: "cancel", pygame.K_BACKSPACE: "cancel",
}


class Input:
    def __init__(self):
        self.held: set[str] = set()
        self.pressed: set[str] = set()
        self.injected_held: set[str] = set()   # 자동 테스트용

    def begin_frame(self):
        self.pressed = set()

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in KEYMAP:
            a = KEYMAP[ev.key]
            self.held.add(a)
            self.pressed.add(a)
        elif ev.type == pygame.KEYUP and ev.key in KEYMAP:
            self.held.discard(KEYMAP[ev.key])

    def press(self, action):        # 자동 테스트: 한 번 누름
        self.pressed.add(action)

    def is_held(self, a):
        return a in self.held or a in self.injected_held

    def was_pressed(self, a):
        return a in self.pressed


class Scene:
    """update(dt) 와 draw(surf) 를 구현. overlay=True 면 아래 장면도 그린다."""
    overlay = False

    def __init__(self, game: "Game"):
        self.game = game

    def on_enter(self):
        pass

    def on_resume(self):
        pass

    def update(self, dt):
        pass

    def draw(self, surf):
        pass


class Fade:
    def __init__(self, duration=0.35, color=(0, 0, 0), on_mid=None):
        self.t = 0.0
        self.d = duration
        self.color = color
        self.on_mid = on_mid
        self.mid_done = False

    def update(self, dt):
        self.t += dt
        if not self.mid_done and self.t >= self.d:
            self.mid_done = True
            if self.on_mid:
                self.on_mid()
        return self.t < self.d * 2

    def alpha(self):
        x = self.t / self.d
        return int(255 * (x if x < 1 else max(0.0, 2 - x)))


class Game:
    def __init__(self, headless=False):
        self.screen = pygame.display.set_mode((cfg.SCREEN_W, cfg.SCREEN_H))
        pygame.display.set_caption(cfg.TITLE)
        self.clock = pygame.time.Clock()
        self.input = Input()
        self.audio = assets.Audio()
        self.scenes: list[Scene] = []
        self.fade: Fade | None = None
        self.running = True
        self.headless = headless
        self.time = 0.0
        self.frame = 0
        self.state = None          # 파티/플래그 등 진행 상황 (src.entities.party.GameState)
        self.listeners = []        # 자동 테스트가 이벤트를 관찰
        self.story = assets.load_json("story.json")

    # --- 장면 스택
    @property
    def scene(self):
        return self.scenes[-1] if self.scenes else None

    def push(self, scene):
        self.scenes.append(scene)
        scene.on_enter()

    def pop(self):
        s = self.scenes.pop()
        if self.scene:
            self.scene.on_resume()
        return s

    def replace(self, scene):
        if self.scenes:
            self.scenes.pop()
        self.push(scene)

    def transition(self, fn, duration=0.35, color=(0, 0, 0)):
        """화면을 어둡게 한 뒤 fn() 실행 후 다시 밝힘"""
        self.fade = Fade(duration, color, fn)

    def emit(self, event, **data):
        for cb in self.listeners:
            cb(event, data)

    # --- 루프
    def step(self, dt):
        self.input.begin_frame()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.running = False
            self.input.handle(ev)
        self.tick(dt)

    def tick(self, dt):
        self.time += dt
        self.frame += 1
        if self.state is not None:
            self.state.playtime += dt
        if self.fade:
            if not self.fade.update(dt):
                self.fade = None
        elif self.scene:
            self.scene.update(dt)
        self.draw()

    def draw(self):
        # 오버레이 장면이면 아래 장면부터 그림
        start = len(self.scenes) - 1
        while start > 0 and self.scenes[start].overlay:
            start -= 1
        for s in self.scenes[start:]:
            s.draw(self.screen)
        if self.fade:
            veil = pygame.Surface(self.screen.get_size())
            veil.fill(self.fade.color)
            veil.set_alpha(self.fade.alpha())
            self.screen.blit(veil, (0, 0))

    def run(self):
        while self.running and self.scenes:
            dt = min(self.clock.tick(cfg.FPS) / 1000.0, 1 / 20)
            self.step(dt)
            pygame.display.flip()
