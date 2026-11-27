"""대화창 (오버레이 장면): 타자기 효과, 감정별 초상화 일러스트, 화자 명판."""
from __future__ import annotations

import pygame

from src import config as cfg
from src.engine import assets
from src.engine.core import Scene
from src.ui import widgets as ui

C = cfg.C
BOX_Y = cfg.SCREEN_H - 233
CPS = 42  # 초당 글자 수


def speaker_name(story, sid):
    if sid in story["meta"]["speaker_ids"]:
        return story["meta"]["speaker_ids"][sid]
    for town in story["npc_dialogues"].values():
        for n in town["npcs"]:
            if n["id"] == sid:
                return n["name"]
    for m in story["major_characters"]:
        if m["id"] == sid:
            return m["name"]
    return sid


class Dialogue(Scene):
    overlay = True

    def __init__(self, game, lines, on_finish=None, npc_sprites=None):
        super().__init__(game)
        self.lines = [l for l in lines if l.get("speaker") != "choice"]
        self.i = 0
        self.shown = 0.0
        self.on_finish = on_finish
        self.npc_sprites = npc_sprites or {}   # speaker id → 캐릭터 시트 경로
        self.box = assets.image("ui/ui_dialogue_box.png")
        self.t = 0.0
        self.blip = 0

    def on_enter(self):
        self.game.emit("dialogue_open", speaker=self.lines[0]["speaker"] if self.lines else None)
        if self.lines:
            self.apply_mood(self.lines[0])

    def apply_mood(self, line):
        """대사 줄의 bgm_mood 태그로 BGM 전환 (default = 현재 맵의 기본 곡). 대화가 끝나면 필드가 맵 곡으로 되돌린다."""
        mood = line.get("bgm_mood")
        if not mood:
            return
        if mood == "default":
            field = next((s for s in reversed(self.game.scenes) if hasattr(s, "map")), None)
            mood = field.map.d.get("bgm") if field else None
        if mood:
            self.game.audio.play_bgm(mood, fade_ms=900)
            self.game.emit("bgm_mood", mood=mood)

    @property
    def line(self):
        return self.lines[self.i]

    def update(self, dt):
        self.t += dt
        full = len(self.line["text"])
        if self.shown < full:
            self.shown = min(full, self.shown + CPS * dt)
        if self.game.input.was_pressed("confirm") or self.game.input.was_pressed("cancel"):
            if self.shown < full:
                self.shown = full
            else:
                self.i += 1
                self.shown = 0
                if self.i < len(self.lines):
                    self.apply_mood(self.lines[self.i])
                if self.i >= len(self.lines):
                    self.game.pop()
                    self.game.emit("dialogue_close")
                    if self.on_finish:
                        self.on_finish()

    # ------------------------------------------------------------ 그리기
    def portrait(self, sid, emotion):
        for emo in (emotion, "normal"):
            rel = f"portraits/portrait_{sid}_{emo}_large.png"
            if assets.has_image(rel):
                return assets.image(rel)
        return None

    def draw(self, surf):
        if self.i >= len(self.lines):
            return
        line = self.line
        sid = line["speaker"]
        dim = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 70))
        surf.blit(dim, (0, 0))

        text_x = 70
        img = self.portrait(sid, line.get("emotion", "normal"))
        if img is not None:
            h = 430
            p = pygame.transform.smoothscale(img, (int(img.get_width() * h / img.get_height()), h))
            surf.blit(p, (30, BOX_Y + 40 - h))
        surf.blit(self.box, (0, BOX_Y))

        if sid in self.npc_sprites:
            # 일러스트가 없는 NPC: 도트 스프라이트를 확대해 초상화 칸에 표시
            frame = pygame.Rect(56, BOX_Y + 40, 140, 150)
            ui.brass_window(surf, frame, 255)
            sheet = assets.image(self.npc_sprites[sid])
            spr = sheet.subsurface((0, 0, 48, 72))
            spr = pygame.transform.scale(spr, (48 * 2, 72 * 2)).subsurface((0, 0, 96, 124))
            surf.blit(spr, spr.get_rect(midbottom=(frame.centerx, frame.bottom - 6)))
            text_x = 230

        if sid not in ("narration", "system"):
            name = speaker_name(self.game.story, sid)
            plate = pygame.Rect(text_x - 14, BOX_Y - 16, max(150, assets.font(22, True).size(name)[0] + 40), 40)
            pygame.draw.rect(surf, C["brass_light"], plate, border_radius=6)
            pygame.draw.rect(surf, C["ink"], plate, 3, border_radius=6)
            ui.text(surf, name, plate.center, 22, C["ink"], bold=True, shadow=False, anchor="center")

        s = line["text"][: int(self.shown)]
        color = C["white"]
        if sid == "narration":
            color = (210, 220, 235)
        elif sid == "system":
            color = C["brass_light"]
        width = cfg.SCREEN_W - text_x - 90
        for k, row in enumerate(ui.wrap(s, width, 24)[:4]):
            ui.text(surf, row, (text_x, BOX_Y + 50 + k * 36), 24, color)

        if self.shown >= len(line["text"]) and int(self.t * 3) % 2 == 0:
            ui.gear_cursor(surf, (cfg.SCREEN_W - 80, cfg.SCREEN_H - 50), self.t)
