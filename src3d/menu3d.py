"""3D 버전 메뉴·타이틀 화면.

Menu3D  (필드에서 X·Esc) : 상태 / 아이템 / 저장 / 불러오기 / 타이틀로 / 게임 종료
TitleUI (시작 화면)      : 새 게임 / 이어하기 / 종료  — 뒤에서는 숲 위를 카메라가 천천히 돈다

화면은 상태가 바뀔 때마다 content 엔티티를 통째로 다시 짓는 단순한 방식 (항목 수가 적어 충분히 빠름).
"""
from __future__ import annotations

import math
import os

from ursina import Entity, Texture, application, camera, color, destroy

from src3d.battle3d import GOLD, Bar, Panel, label

UP = ("up arrow", "w")
DOWN = ("down arrow", "s")
LEFT = ("left arrow", "a")
RIGHT = ("right arrow", "d")
OK = ("z", "enter", "space")
BACK = ("x", "escape", "backspace", "tab")

DIM = color.rgba(0.62, 0.6, 0.56, 1)
CREAM = color.rgba32(244, 232, 204)
HP_COL = color.rgba32(96, 196, 104)
MP_COL = color.rgba32(92, 150, 236)
EXP_COL = color.rgba32(232, 190, 90)
STEAM_COL = color.rgba32(236, 140, 70)
SEL_FILL = color.rgba32(226, 184, 102, 70)

_img_cache = {}


def _tex(path):
    if path not in _img_cache:
        t = Texture(path)
        t.filtering = "mipmap"
        _img_cache[path] = t
    return _img_cache[path]


def picture(parent, path, x, y, h, origin=(0, 0), z=-0.003):
    """이미지를 높이 h 에 맞춰 비율 그대로 놓는다"""
    if not path or not os.path.exists(path):
        return None
    t = _tex(path)
    return Entity(parent=parent, model="quad", texture=t, position=(x, y), z=z, origin=origin,
                  scale=(h * t.width / t.height, h))


def shadow_label(parent, text, x, y, scale, col, origin=(0, 0), font=None, off=0.003):
    sh = label(parent, text, x + off, y - off, scale, color.rgba(0, 0, 0, 0.75), origin, font)
    sh.z = -0.0015
    t = label(parent, text, x, y, scale, col, origin, font)
    t.z = -0.004                       # 그림자보다 확실히 앞에
    return t


def slot_rows(parent, game, cursor, mode, x=0.12, y0=0.2):
    """세이브 슬롯 3칸. mode: save / load. 반환: 슬롯별 사용 가능 여부"""
    from src.systems import save
    usable = []
    for i in range(save.SLOTS):
        d = save.read(i)
        y = y0 - i * 0.17
        sel = i == cursor
        Panel(1.08, 0.145, x, y, parent=parent, fill=color.rgba(0.1, 0.09, 0.12, 0.92) if not sel else
              color.rgba(0.22, 0.17, 0.1, 0.95), border=GOLD if sel else color.rgba(0.45, 0.38, 0.26, 1))
        label(parent, f"슬롯 {i + 1}", x - 0.5, y + 0.035, 1.0, GOLD)
        if not d:
            label(parent, "— 비어 있음 —", x - 0.5, y - 0.025, 0.9, DIM)
            usable.append(mode == "save")
            continue
        ok3d = save.map_exists_3d(d["map_id"])
        luke = next((p for p in d.get("party", []) if p["id"] == "luke"), d["party"][0])
        label(parent, save.map_name(d["map_id"]), x - 0.33, y + 0.035, 1.0, CREAM)
        label(parent, f"루크 Lv {luke['level']}    플레이 {save.fmt_time(d.get('playtime', 0))}    "
                      f"GOLD {d.get('gold', 0)}", x - 0.5, y - 0.025, 0.85, CREAM)
        label(parent, d.get("saved_at", ""), x + 0.5, y + 0.035, 0.75, DIM, origin=(0.5, 0))
        if not ok3d:
            label(parent, "이전(2D) 버전 세이브 — 3D 에서는 불러올 수 없음", x + 0.5, y - 0.025, 0.7,
                  color.rgba32(220, 120, 100), origin=(0.5, 0))
        usable.append(mode == "save" or ok3d)
    return usable


# ====================================================================== 필드 메뉴
class Menu3D:
    COMMANDS = ["상태", "아이템", "저장", "불러오기", "타이틀로", "게임 종료"]

    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-0.3, enabled=False)
        self.content = None
        self.page = "main"
        self.cur = {"main": 0, "status": 0, "items": 0, "target": 0, "save": 0, "load": 0, "confirm": 1}
        self.confirm_kind = None
        self.t = 0.0
        self.msg = ""

    @property
    def active(self):
        return self.root.enabled

    def open(self):
        if self.game.mode != "field":
            return
        self.root.enabled = True
        self.page = "main"
        self.cur["main"] = 0
        self.msg = ""
        self.game.hint.enabled = False
        self.render()

    def close(self):
        if not self.root.enabled:
            return
        self.root.enabled = False
        if self.content:
            destroy(self.content)
            self.content = None
        self.game.hint.enabled = self.game.mode == "field"

    def update(self, dt):
        self.t += dt

    # ------------------------------------------------------------ 입력
    def input(self, key):
        g = self.game
        p = self.page
        if key in BACK:
            g.sfx("sfx_cancel")
            if p == "main":
                self.close()
                return
            self.page = {"target": "items"}.get(p, "main")
            self.msg = ""
            self.render()
            return
        n = self.count()
        if key in UP + DOWN and n:
            self.cur[p] = (self.cur[p] + (1 if key in DOWN else -1)) % n
            g.sfx("sfx_cursor")
            self.render()
        elif key in LEFT + RIGHT and p == "confirm":
            self.cur[p] = 1 - self.cur[p]
            g.sfx("sfx_cursor")
            self.render()
        elif key in LEFT + RIGHT and p == "status":
            self.cur[p] = (self.cur[p] + (1 if key in RIGHT else -1)) % len(g.state.party)
            g.sfx("sfx_cursor")
            self.render()
        elif key in OK:
            self.choose()

    def count(self):
        st = self.game.state
        return {"main": len(self.COMMANDS), "status": len(st.party), "items": len(self.item_list()),
                "target": len(st.party), "save": 3, "load": 3, "confirm": 2}[self.page]

    def item_list(self):
        from src.datafiles import load_json
        defs = load_json("battle.json")["items"]
        return [(k, defs[k], n) for k, n in self.game.state.items.items() if n > 0 and k in defs]

    def choose(self):
        g = self.game
        p = self.page
        c = self.cur[p]
        if p == "main":
            g.sfx("sfx_confirm")
            cmd = self.COMMANDS[c]
            self.msg = ""
            if cmd == "상태":
                self.page = "status"
            elif cmd == "아이템":
                self.page = "items"
                self.cur["items"] = min(self.cur["items"], max(0, len(self.item_list()) - 1))
            elif cmd == "저장":
                self.page = "save"
            elif cmd == "불러오기":
                self.page = "load"
            elif cmd in ("타이틀로", "게임 종료"):
                self.page, self.confirm_kind, self.cur["confirm"] = "confirm", cmd, 1
            self.render()
        elif p == "items":
            if not self.item_list():
                return
            g.sfx("sfx_confirm")
            self.page = "target"
            self.render()
        elif p == "target":
            self.use_item(c)
        elif p == "save":
            g.save_slot(c)
            g.sfx("sfx_levelup")
            self.msg = f"슬롯 {c + 1}에 저장했습니다."
            self.render()
        elif p == "load":
            if g.load_slot(c):
                g.sfx("sfx_confirm")
            else:
                g.sfx("sfx_cancel")
                self.msg = "불러올 수 없는 슬롯입니다."
                self.render()
        elif p == "confirm":
            if c == 1:
                g.sfx("sfx_cancel")
                self.page = "main"
                self.render()
                return
            g.sfx("sfx_confirm")
            if self.confirm_kind == "타이틀로":
                g.to_title()
            else:
                application.quit()

    def use_item(self, idx):
        g = self.game
        items = self.item_list()
        if not items:
            self.page = "items"
            self.render()
            return
        key, it, _ = items[min(self.cur["items"], len(items) - 1)]
        ch = g.state.party[idx]
        if not ch.alive:
            self.msg = f"{ch.name}은(는) 쓰러져 있어 사용할 수 없다."
        elif it.get("heal_hp") and ch.hp < ch.max_hp:
            v = min(it["heal_hp"], ch.max_hp - ch.hp)
            ch.hp += v
            self.msg = f"{ch.name}의 HP가 {v} 회복되었다."
        elif it.get("heal_mp") and ch.mp < ch.max_mp:
            v = min(it["heal_mp"], ch.max_mp - ch.mp)
            ch.mp += v
            self.msg = f"{ch.name}의 MP가 {v} 회복되었다."
        else:
            self.msg = "지금은 효과가 없다."
            g.sfx("sfx_cancel")
            self.render()
            return
        g.state.items[key] -= 1
        g.sfx("sfx_heal")
        if g.state.items[key] <= 0:
            self.page = "items"
            self.cur["items"] = 0
        self.render()

    # ------------------------------------------------------------ 그리기
    def render(self):
        if self.content:
            destroy(self.content)
        c = self.content = Entity(parent=self.root)
        g = self.game
        st = g.state
        # 전체를 살짝 어둡게
        Entity(parent=c, model="quad", scale=(4, 2), color=color.rgba(0, 0, 0, 0.45), z=0.01)
        # 왼쪽 명령 목록
        Panel(0.3, 0.6, -0.7, 0.13, parent=c)
        shadow_label(c, "MENU", -0.7, 0.39, 1.3, GOLD, font="NanumMyeongjo-Bold.ttf")
        for i, cmd in enumerate(self.COMMANDS):
            y = 0.3 - i * 0.075
            sel = i == self.cur["main"]
            if sel:
                Entity(parent=c, model="quad", position=(-0.7, y), scale=(0.27, 0.06), color=SEL_FILL, z=-0.001)
                label(c, "▶", -0.835, y, 0.8, GOLD)
            label(c, cmd, -0.8, y, 1.1, CREAM if (sel or self.page == "main") else DIM)
        # 왼쪽 아래 정보
        from src.systems import save
        Panel(0.3, 0.2, -0.7, -0.33, parent=c)
        label(c, f"GOLD  {st.gold}", -0.83, -0.27, 0.95, CREAM)
        label(c, f"시간  {save.fmt_time(st.playtime)}", -0.83, -0.325, 0.95, CREAM)
        label(c, g.world.m["name"] if g.world else "", -0.83, -0.38, 0.85, DIM)
        page = self.page
        if page in ("main", "target"):
            self.party_cards(c, sel=self.cur["target"] if page == "target" else None)
            if page == "target":
                key, it, n = self.item_list()[self.cur["items"]] if self.item_list() else (None, {}, 0)
                Panel(1.12, 0.08, 0.16, -0.43, parent=c)
                label(c, f"{it.get('name', '')} ({n}) — 누구에게 사용할까?", -0.38, -0.43, 0.95, GOLD)
        elif page == "status":
            self.status_page(c, st.party[self.cur["status"]])
        elif page == "items":
            self.items_page(c)
        elif page in ("save", "load"):
            Panel(1.16, 0.64, 0.14, 0.03, parent=c)
            shadow_label(c, "저장할 슬롯을 고르세요" if page == "save" else "불러올 슬롯을 고르세요", 0.14, 0.3, 1.1, GOLD)
            slot_rows(c, g, self.cur[page], page, x=0.14, y0=0.16)
        elif page == "confirm":
            self.party_cards(c)
            Panel(0.72, 0.24, 0.16, 0.0, z=-0.01, parent=c)
            q = ("타이틀 화면으로 돌아갈까요?\n저장하지 않은 진행은 사라집니다." if self.confirm_kind == "타이틀로"
                 else "게임을 종료할까요?\n저장하지 않은 진행은 사라집니다.")
            t = label(c, q, 0.16, 0.05, 0.95, CREAM, origin=(0, 0))
            t.z = -0.02
            for i, opt in enumerate(("예", "아니오")):
                x = 0.06 + i * 0.2
                sel = i == self.cur["confirm"]
                if sel:
                    Entity(parent=c, model="quad", position=(x, -0.06), scale=(0.14, 0.055), color=SEL_FILL, z=-0.02)
                o = label(c, opt, x, -0.06, 1.05, GOLD if sel else DIM, origin=(0, 0))
                o.z = -0.03
        if self.msg:
            Panel(0.8, 0.07, 0.16, 0.45, parent=c, z=-0.02)
            m = label(c, self.msg, 0.16, 0.45, 0.95, CREAM, origin=(0, 0))
            m.z = -0.03

    def party_cards(self, c, sel=None):
        from src.entities.party import exp_to_next
        from src3d.game import FIELD_DIR
        for i, ch in enumerate(self.game.state.party):
            y = 0.27 - i * 0.235
            hi = sel == i
            Panel(1.12, 0.205, 0.16, y, parent=c, border=GOLD if hi or sel is None else color.rgba(0.4, 0.34, 0.24, 1),
                  fill=color.rgba(0.22, 0.17, 0.1, 0.95) if hi else color.rgba(0.06, 0.07, 0.12, 0.86))
            picture(c, os.path.join(FIELD_DIR, ch.id + ".png"), -0.33, y - 0.095, 0.19, origin=(0, -0.5))
            label(c, ch.name, -0.22, y + 0.065, 1.15, CREAM if ch.alive else color.rgba32(200, 90, 80))
            label(c, f"{ch.cls}", -0.22, y + 0.02, 0.8, DIM)
            label(c, f"Lv {ch.level}", 0.08, y + 0.065, 1.1, GOLD)
            for k, (name, val, mx, col) in enumerate((("HP", ch.hp, ch.max_hp, HP_COL), ("MP", ch.mp, ch.max_mp, MP_COL))):
                yy = y - 0.025 - k * 0.05
                label(c, name, -0.22, yy, 0.8, DIM)
                Bar(c, -0.17, yy, 0.3, 0.022, col).set(val / max(1, mx))
                label(c, f"{val} / {mx}", 0.15, yy, 0.8, CREAM)
            label(c, "EXP", 0.36, y + 0.065, 0.8, DIM)
            Bar(c, 0.43, y + 0.065, 0.24, 0.018, EXP_COL).set(ch.exp / exp_to_next(ch.level))
            label(c, f"다음 레벨까지 {exp_to_next(ch.level) - ch.exp}", 0.36, y + 0.02, 0.75, CREAM)
            if ch.id == "luke":
                label(c, "증기압", 0.36, y - 0.035, 0.75, DIM)
                Bar(c, 0.45, y - 0.035, 0.22, 0.018, STEAM_COL).set(ch.steam / 100)
            if hi:
                label(c, "◀", 0.7, y, 1.0, GOLD)

    def status_page(self, c, ch):
        from src3d.game import FIELD_DIR, PORTRAIT_DIR
        Panel(1.16, 0.86, 0.14, 0.0, parent=c)
        art = os.path.join(PORTRAIT_DIR, ch.id + ".png")
        if not os.path.exists(art):
            art = os.path.join(FIELD_DIR, ch.id + ".png")
        picture(c, art, 0.49, -0.43, 0.6, origin=(0, -0.5), z=-0.001)
        shadow_label(c, ch.name, -0.4, 0.36, 1.6, CREAM, origin=(-0.5, 0), font="NanumMyeongjo-Bold.ttf")
        label(c, f"{ch.cls}    Lv {ch.level}", -0.4, 0.3, 0.95, GOLD)
        label(c, "◀ ▶ 동료 바꾸기", 0.68, 0.39, 0.7, DIM, origin=(0.5, 0))
        rows = [("HP", f"{ch.hp} / {ch.max_hp}"), ("MP", f"{ch.mp} / {ch.max_mp}"), ("공격", ch.stat("atk")),
                ("방어", ch.stat("def")), ("마력", ch.stat("mag")), ("저항", ch.stat("res")), ("속도", ch.stat("spd"))]
        for i, (k, v) in enumerate(rows):
            y = 0.22 - i * 0.05
            label(c, k, -0.4, y, 0.9, DIM)
            label(c, str(v), -0.15, y, 0.9, CREAM, origin=(0.5, 0))
        label(c, "스킬", -0.05, 0.22, 0.95, GOLD)
        for i, sk in enumerate(ch.skills(all_=True)[:7]):
            y = 0.17 - i * 0.05
            learned = sk["level"] <= ch.level
            cost = f"MP {sk['mp']}" if sk["mp"] else (f"증기 {sk['steam_cost']}" if sk["steam_cost"] else "")
            label(c, sk["name"] if learned else f"{sk['name']} (Lv {sk['level']})", -0.05, y, 0.82,
                  CREAM if learned else DIM)
            label(c, cost, 0.2, y, 0.72, DIM, origin=(0.5, 0))

    def items_page(self, c):
        items = self.item_list()
        Panel(1.16, 0.86, 0.14, 0.0, parent=c)
        shadow_label(c, "아이템", -0.4, 0.37, 1.3, GOLD, origin=(-0.5, 0), font="NanumMyeongjo-Bold.ttf")
        if not items:
            label(c, "가진 아이템이 없다.", -0.4, 0.25, 1.0, DIM)
            return
        for i, (k, it, n) in enumerate(items):
            y = 0.27 - i * 0.07
            sel = i == self.cur["items"]
            if sel:
                Entity(parent=c, model="quad", position=(0.14, y), scale=(1.1, 0.058), color=SEL_FILL, z=-0.001)
                label(c, "▶", -0.43, y, 0.8, GOLD)
            label(c, it["name"], -0.4, y, 1.05, CREAM)
            label(c, f"× {n}", 0.66, y, 1.0, CREAM, origin=(0.5, 0))
        it = items[min(self.cur["items"], len(items) - 1)][1]
        Panel(1.08, 0.09, 0.14, -0.36, parent=c, fill=color.rgba(0.12, 0.1, 0.08, 0.95))
        label(c, it.get("desc", ""), -0.38, -0.36, 0.95, CREAM)


# ====================================================================== 타이틀
class TitleUI:
    ITEMS = ["새 게임", "이어하기", "종료"]

    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-0.3, enabled=False)
        self.content = None
        self.page = "main"
        self.cur = 0
        self.slot = 0
        self.t = 0.0
        self.msg = ""

    @property
    def active(self):
        return self.root.enabled

    def has_save(self):
        from src.systems import save
        return any((d := save.read(i)) and save.map_exists_3d(d["map_id"]) for i in range(save.SLOTS))

    def open(self):
        self.root.enabled = True
        self.page = "main"
        self.cur = 1 if self.has_save() else 0
        self.t = 0.0
        self.render()

    def close(self):
        self.root.enabled = False
        if self.content:
            destroy(self.content)
            self.content = None

    def input(self, key):
        g = self.game
        if not self.active:
            return
        if self.page == "slots":
            if key in BACK:
                g.sfx("sfx_cancel")
                self.page = "main"
            elif key in UP + DOWN:
                self.slot = (self.slot + (1 if key in DOWN else -1)) % 3
                g.sfx("sfx_cursor")
            elif key in OK:
                if not g.load_slot(self.slot):
                    g.sfx("sfx_cancel")
                    self.msg = "불러올 수 없는 슬롯입니다."
                else:
                    g.sfx("sfx_confirm")
                    return
            self.render()
            return
        if key in UP + DOWN:
            self.cur = (self.cur + (1 if key in DOWN else -1)) % len(self.ITEMS)
            g.sfx("sfx_cursor")
            self.render()
        elif key in OK:
            item = self.ITEMS[self.cur]
            if item == "새 게임":
                g.sfx("sfx_confirm")
                g.new_game()
            elif item == "이어하기":
                if not self.has_save():
                    g.sfx("sfx_cancel")
                    return
                g.sfx("sfx_confirm")
                self.page, self.msg = "slots", ""
                self.render()
            else:
                application.quit()

    def update(self, dt):
        self.t += dt
        if self.content:
            self.logo.y = 0.2 + math.sin(self.t * 1.2) * 0.005

    def render(self):
        if self.content:
            destroy(self.content)
        c = self.content = Entity(parent=self.root)
        # 위·아래 어둡게 (글씨가 숲 위에서도 읽히도록)
        Entity(parent=c, model="quad", scale=(4, 2), color=color.rgba(0.03, 0.04, 0.06, 0.38), z=0.01)
        Panel(0.42, 0.3, 0, -0.195, parent=c, fill=color.rgba(0.05, 0.05, 0.08, 0.6),
              border=color.rgba32(226, 184, 102, 140)) if self.page == "main" else None
        self.logo = Entity(parent=c, y=0.2)
        shadow_label(self.logo, "황동의 심장", 0, 0.02, 5.0, color.rgba32(246, 214, 140), font="NanumMyeongjo-Bold.ttf",
                     off=0.006)
        shadow_label(self.logo, "— 아스카론 연대기 —", 0, -0.075, 1.6, CREAM, font="NanumMyeongjo-Bold.ttf")
        if self.page == "main":
            can = self.has_save()
            for i, it in enumerate(self.ITEMS):
                y = -0.12 - i * 0.075
                sel = i == self.cur
                if sel:
                    Entity(parent=c, model="quad", position=(0, y), scale=(0.34, 0.06), color=SEL_FILL, z=-0.001)
                col = GOLD if sel else CREAM
                if it == "이어하기" and not can:
                    col = DIM
                shadow_label(c, ("▶  " if sel else "") + it + ("  ◀" if sel else ""), 0, y, 1.3, col)
        else:
            Panel(1.16, 0.58, 0.0, -0.2, parent=c)
            label(c, "불러올 슬롯을 고르세요   (X: 돌아가기)", 0, 0.05, 0.95, GOLD, origin=(0, 0))
            slot_rows(c, self.game, self.slot, "load", x=0.0, y0=-0.05)
            if self.msg:
                label(c, self.msg, 0, -0.47, 0.9, color.rgba32(230, 130, 110), origin=(0, 0))
        if self.page == "main":
            shadow_label(c, "↑↓ 선택    Z·Enter 결정", 0, -0.46, 0.8, DIM)
