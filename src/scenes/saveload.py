"""세이브/로드 슬롯 선택 창 (오버레이)."""
from __future__ import annotations

import pygame

from src import config as cfg
from src.engine.core import Scene
from src.systems import save as saves
from src.ui import widgets as ui

C = cfg.C
INK = C["ink"]
DIM = (150, 130, 110)


class SaveLoadScene(Scene):
    overlay = True

    def __init__(self, game, mode, on_load=None):
        super().__init__(game)
        self.mode = mode                 # "save" | "load"
        self.on_load = on_load
        self.t = 0.0
        self.index = 0
        self.confirm = False             # 덮어쓰기 확인 중
        self.msg = None                  # (문구, 남은 시간)
        self.refresh()
        if mode == "load":               # 가장 최근 세이브에 커서
            filled = [i for i, d in enumerate(self.slots) if d]
            if filled:
                self.index = max(filled, key=lambda i: self.slots[i].get("saved_at", ""))

    def refresh(self):
        self.slots = [saves.read(i) for i in range(saves.SLOTS)]

    def update(self, dt):
        self.t += dt
        inp, au = self.game.input, self.game.audio
        if self.msg:
            self.msg = (self.msg[0], self.msg[1] - dt)
            if self.msg[1] <= 0 or inp.was_pressed("confirm") or inp.was_pressed("cancel"):
                self.msg = None
                self.game.pop()
            return
        if self.confirm:
            if inp.was_pressed("confirm"):
                self.do_save()
            elif inp.was_pressed("cancel"):
                au.sfx("sfx_cancel")
                self.confirm = False
            return
        if inp.was_pressed("up"):
            self.index = (self.index - 1) % saves.SLOTS
            au.sfx("sfx_cursor")
        if inp.was_pressed("down"):
            self.index = (self.index + 1) % saves.SLOTS
            au.sfx("sfx_cursor")
        if inp.was_pressed("cancel"):
            au.sfx("sfx_cancel")
            self.game.pop()
        elif inp.was_pressed("confirm"):
            slot = self.slots[self.index]
            if self.mode == "save":
                au.sfx("sfx_confirm")
                if slot:
                    self.confirm = True
                else:
                    self.do_save()
            elif slot:
                au.sfx("sfx_confirm")
                self.game.emit("load", slot=self.index)
                self.game.pop()
                if self.on_load:
                    self.on_load(slot)
            else:
                au.sfx("sfx_cancel")

    def do_save(self):
        self.confirm = False
        try:
            saves.save(self.index, self.game.state)
            self.game.audio.sfx("sfx_levelup")
            text = self.game.story["system_messages"]["save"]
            self.game.emit("save", slot=self.index)
        except OSError as e:
            self.game.audio.sfx("sfx_cancel")
            text = f"저장하지 못했습니다: {e.strerror or e}"
        self.refresh()
        self.msg = (text, 1.4)

    def draw(self, surf):
        veil = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 140))
        surf.blit(veil, (0, 0))
        r = pygame.Rect(0, 0, 800, 470)
        r.center = (cfg.SCREEN_W // 2, cfg.SCREEN_H // 2)
        ui.parchment_window(surf, r)
        title = "기억을 태엽에 감기 (저장)" if self.mode == "save" else "감아둔 기억 풀기 (불러오기)"
        ui.text(surf, title, (r.centerx, r.y + 66), 26, INK, bold=True, anchor="center", shadow=False)
        story = self.game.story
        for i, d in enumerate(self.slots):
            box = pygame.Rect(r.x + 60, r.y + 100 + i * 92, r.w - 120, 80)
            sel = i == self.index
            pygame.draw.rect(surf, (246, 232, 196) if sel else (226, 208, 168), box, border_radius=8)
            pygame.draw.rect(surf, C["brass"] if sel else DIM, box, 3 if sel else 1, border_radius=8)
            ui.text(surf, f"슬롯 {i + 1}", (box.x + 18, box.y + 12), 22, INK, bold=True, shadow=False)
            if d:
                town = next((t["town_name"] for k, t in story["npc_dialogues"].items() if k == d["map_id"]), None)
                place = town or {"sewer": "지하 배수로"}.get(d["map_id"], d["map_id"])
                lead = d["party"][0]
                ui.text(surf, place, (box.x + 130, box.y + 12), 22, INK, shadow=False)
                ui.text(surf, f"루크 Lv{lead['level']}   {d.get('gold', 0)} G", (box.x + 130, box.y + 44), 18, INK, shadow=False)
                ui.text(surf, f"플레이 {saves.fmt_time(d.get('playtime', 0))}", (box.right - 18, box.y + 12), 18, INK,
                        anchor="topright", shadow=False)
                ui.text(surf, d.get("saved_at", ""), (box.right - 18, box.y + 44), 16, DIM, anchor="topright", shadow=False)
            else:
                ui.text(surf, "— 비어 있음 —", (box.x + 130, box.y + 26), 20, DIM, shadow=False)
            if sel:
                ui.gear_cursor(surf, (box.x - 22, box.centery), self.t)
        hint = "Z: 저장   X: 닫기" if self.mode == "save" else "Z: 불러오기   X: 닫기"
        ui.text(surf, hint, (r.centerx, r.bottom - 62), 18, DIM, anchor="center", shadow=False)
        if self.confirm or self.msg:
            m = pygame.Rect(0, 0, 520, 110)
            m.center = r.center
            ui.brass_window(surf, m, 245)
            s = f"슬롯 {self.index + 1}에 덮어쓸까요?   Z: 예  X: 아니오" if self.confirm else self.msg[0]
            ui.text(surf, s, m.center, 22, C["white"], anchor="center")
