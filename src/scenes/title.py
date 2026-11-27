"""타이틀 화면."""
from __future__ import annotations

import math

import pygame

from src import config as cfg
from src.engine import assets
from src.engine.core import Scene
from src.entities.party import GameState
from src.systems import save as saves
from src.ui import widgets as ui

C = cfg.C


class TitleScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        has_save = saves.any_save()
        self.menu = ui.ListMenu([("새로운 여정", True, ""), ("이어하기", has_save, ""), ("종료", True, "")], rows=3)
        if has_save:
            self.menu.index = 1          # 세이브가 있으면 '이어하기'에 커서
        self.t = 0.0
        bg = assets.image("backgrounds/bg_chimney_ward_plaza.png")
        self.bg = bg.copy()
        veil = pygame.Surface(self.bg.get_size(), pygame.SRCALPHA)
        veil.fill((8, 8, 20, 150))
        self.bg.blit(veil, (0, 0))

    def on_enter(self):
        self.game.audio.play_bgm("bgm_chimney_ward")

    def update(self, dt):
        self.t += dt
        inp, au = self.game.input, self.game.audio
        if inp.was_pressed("up"):
            self.menu.move(-1, au)
        if inp.was_pressed("down"):
            self.menu.move(1, au)
        if inp.was_pressed("confirm"):
            label, enabled, _ = self.menu.items[self.menu.index]
            if not enabled:
                au.sfx("sfx_cancel")
                return
            au.sfx("sfx_confirm")
            if self.menu.index == 0:
                from src.scenes.field import FieldScene

                def start():
                    self.game.state = GameState(self.game.story)
                    self.game.replace(FieldScene(self.game, "chimney_ward"))
                self.game.transition(start, 0.5)
            elif self.menu.index == 1:
                from src.scenes.saveload import SaveLoadScene
                self.game.push(SaveLoadScene(self.game, "load", on_load=self.load))
            else:
                self.game.running = False

    def load(self, data):
        from src.scenes.field import FieldScene

        def go():
            st = saves.apply_dict(GameState(self.game.story), data)
            self.game.state = st
            self.game.replace(FieldScene(self.game, st.map_id, st.pos, st.dir))
        self.game.transition(go, 0.5)

    def draw(self, surf):
        surf.blit(self.bg, (0, 0))
        meta = self.game.story["meta"]
        y = 190 + math.sin(self.t * 1.5) * 4
        ui.text(surf, "황동의 심장", (cfg.SCREEN_W // 2, y), 84, C["brass_light"], bold=True, anchor="center", outline=True)
        ui.text(surf, "아스카론 연대기", (cfg.SCREEN_W // 2, y + 76), 32, C["parchment"], anchor="center", outline=True)
        ui.text(surf, meta["tagline"], (cfg.SCREEN_W // 2, y + 130), 20, C["steam"], anchor="center")
        r = pygame.Rect(0, 0, 300, 180)
        r.center = (cfg.SCREEN_W // 2, 520)
        ui.parchment_window(surf, r)
        self.menu.draw(surf, r.x + 70, r.y + 42, 160, self.t, 24, 38, ink=C["ink"], dim=(150, 130, 110))
        ui.text(surf, "방향키 이동 · Z/Enter 결정 · X/Esc 취소", (cfg.SCREEN_W // 2, 680), 18, C["gray"], anchor="center")
        ui.text(surf, f"v{meta['version']} 데모", (cfg.SCREEN_W - 16, cfg.SCREEN_H - 30), 16, C["gray"], anchor="topright")
