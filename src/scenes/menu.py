"""필드 메뉴: 파티 상태 / 스킬 / 아이템 (양피지 창)."""
from __future__ import annotations

import pygame

from src import config as cfg
from src.engine import assets
from src.engine.core import Scene
from src.entities.party import exp_to_next
from src.ui import widgets as ui

C = cfg.C
INK = C["ink"]
DIM = (150, 130, 110)


class MenuScene(Scene):
    overlay = True

    def __init__(self, game):
        super().__init__(game)
        self.tabs = ui.ListMenu([("상태", True, ""), ("스킬", True, ""), ("아이템", True, ""), ("저장", True, ""),
                                 ("닫기", True, "")], rows=5)
        self.member = 0
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        inp, au = self.game.input, self.game.audio
        if inp.was_pressed("up"):
            self.tabs.move(-1, au)
        if inp.was_pressed("down"):
            self.tabs.move(1, au)
        if inp.was_pressed("left"):
            self.member = (self.member - 1) % len(self.game.state.party); au.sfx("sfx_cursor")
        if inp.was_pressed("right"):
            self.member = (self.member + 1) % len(self.game.state.party); au.sfx("sfx_cursor")
        if inp.was_pressed("confirm") and self.tabs.index == 3:
            from src.scenes.saveload import SaveLoadScene
            au.sfx("sfx_confirm")
            self.game.push(SaveLoadScene(self.game, "save"))
        elif inp.was_pressed("cancel") or (inp.was_pressed("confirm") and self.tabs.index == 4):
            au.sfx("sfx_cancel")
            self.game.pop()

    def draw(self, surf):
        veil = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 120))
        surf.blit(veil, (0, 0))
        st = self.game.state
        left = pygame.Rect(40, 40, 240, 300)
        ui.parchment_window(surf, left)
        self.tabs.draw(surf, left.x + 40, left.y + 46, 150, self.t, 24, 42, ink=INK, dim=DIM)
        info = pygame.Rect(40, 360, 240, 180)
        ui.parchment_window(surf, info)
        ui.text(surf, f"{st.gold} G", (info.x + 40, info.y + 42), 22, INK, shadow=False)
        ui.text(surf, f"승리 {st.battles_won}회", (info.x + 40, info.y + 80), 20, INK, shadow=False)
        from src.systems.save import fmt_time
        ui.text(surf, f"플레이 {fmt_time(st.playtime)}", (info.x + 40, info.y + 114), 18, INK, shadow=False)

        main = pygame.Rect(300, 40, 940, 640)
        ui.parchment_window(surf, main)
        ch = st.party[self.member]
        tab = self.tabs.index
        # 파티원 탭
        for i, c in enumerate(st.party):
            r = pygame.Rect(main.x + 50 + i * 150, main.y + 36, 140, 34)
            pygame.draw.rect(surf, C["brass_light"] if i == self.member else (200, 180, 140), r, border_radius=6)
            pygame.draw.rect(surf, INK, r, 2, border_radius=6)
            ui.text(surf, c.name.split()[0], r.center, 18, INK, anchor="center", shadow=False)
        ui.text(surf, "◀ ▶ 파티원 전환", (main.right - 50, main.y + 44), 16, DIM, anchor="topright", shadow=False)

        por = f"portraits/portrait_{ch.id}_normal.png"
        if assets.has_image(por):
            img = pygame.transform.smoothscale(assets.image(por), (220, 220))
            frame = pygame.Rect(main.x + 50, main.y + 90, 228, 228)
            pygame.draw.rect(surf, C["navy"], frame, border_radius=8)
            surf.blit(img, (frame.x + 4, frame.y + 4))
            pygame.draw.rect(surf, C["brass"], frame, 4, border_radius=8)
        x0, y0 = main.x + 310, main.y + 96
        if tab in (0, 3, 4):
            ui.text(surf, ch.name, (x0, y0), 30, INK, bold=True, shadow=False)
            ui.text(surf, f"{ch.cls}   Lv {ch.level}", (x0, y0 + 42), 22, INK, shadow=False)
            ui.text(surf, "HP", (x0, y0 + 86), 20, INK, shadow=False)
            ui.gauge(surf, (x0 + 50, y0 + 88, 260, 18), ch.hp / ch.max_hp, C["hp"], border=INK)
            ui.text(surf, f"{ch.hp}/{ch.max_hp}", (x0 + 330, y0 + 86), 20, INK, shadow=False)
            ui.text(surf, "MP", (x0, y0 + 118), 20, INK, shadow=False)
            ui.gauge(surf, (x0 + 50, y0 + 120, 260, 18), ch.mp / ch.max_mp, C["mp"], border=INK)
            ui.text(surf, f"{ch.mp}/{ch.max_mp}", (x0 + 330, y0 + 118), 20, INK, shadow=False)
            ui.text(surf, "EXP", (x0, y0 + 150), 20, INK, shadow=False)
            ui.gauge(surf, (x0 + 50, y0 + 152, 260, 18), ch.exp / exp_to_next(ch.level), C["atb"], border=INK)
            ui.text(surf, f"{ch.exp}/{exp_to_next(ch.level)}", (x0 + 330, y0 + 150), 20, INK, shadow=False)
            names = {"atk": "공격", "def": "방어", "mag": "마력", "res": "저항", "spd": "속도"}
            for i, k in enumerate(names):
                ui.text(surf, f"{names[k]}  {ch.stat(k)}", (x0 + (i % 3) * 170, y0 + 196 + (i // 3) * 34), 22, INK, shadow=False)
            prof = ch.profile
            if "unique_mechanic" in prof:
                um = prof["unique_mechanic"]
                ui.text(surf, f"고유: {um['name']}", (main.x + 50, main.y + 350), 22, C["copper"], bold=True, shadow=False)
                for i, row in enumerate(ui.wrap(um["description"], main.w - 100, 18)[:2]):
                    ui.text(surf, row, (main.x + 50, main.y + 382 + i * 26), 18, INK, shadow=False)
            for i, row in enumerate(ui.wrap(prof["personality"], main.w - 100, 18)[:4]):
                ui.text(surf, row, (main.x + 50, main.y + 450 + i * 28), 18, INK, shadow=False)
        elif tab == 1:
            ui.text(surf, f"{ch.name}의 스킬", (x0, y0), 26, INK, bold=True, shadow=False)
            for i, s in enumerate(ch.skills(all_=True)):
                y = main.y + 340 + i * 46
                learned = s["level"] <= ch.level
                col = INK if learned else DIM
                cost = f"MP {s['mp']}" if s["mp"] else ("증기압 100" if s.get("steam_cost") else "-")
                ui.text(surf, ("" if learned else f"[Lv{s['level']}] ") + s["name"], (main.x + 50, y), 20, col, bold=learned, shadow=False)
                ui.text(surf, cost, (main.x + 330, y), 18, col, shadow=False)
                ui.text(surf, ui.wrap(s["description"], 480, 16)[0], (main.x + 430, y + 2), 16, col, shadow=False)
            ui.text(surf, "전투에서 [스킬] 명령으로 사용합니다.", (x0, y0 + 44), 18, DIM, shadow=False)
        elif tab == 2:
            items = assets.load_json("battle.json")["items"]
            ui.text(surf, "소지품", (x0, y0), 26, INK, bold=True, shadow=False)
            for i, (k, n) in enumerate(st.items.items()):
                ui.text(surf, f"{items[k]['name']}  x{n}", (x0, y0 + 50 + i * 40), 22, INK, shadow=False)
                ui.text(surf, items[k]["desc"], (x0 + 300, y0 + 52 + i * 40), 18, DIM, shadow=False)
