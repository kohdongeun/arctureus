"""3D 버전 메뉴·타이틀 화면.

Menu3D  (필드에서 X·Esc) : 상태 / 아이템 / 저장 / 불러오기 / 타이틀로 / 게임 종료
TitleUI (시작 화면)      : 새 게임 / 이어하기 / 종료  — 뒤에서는 숲 위를 카메라가 천천히 돈다

화면은 상태가 바뀔 때마다 content 엔티티를 통째로 다시 짓는 단순한 방식 (항목 수가 적어 충분히 빠름).
"""
from __future__ import annotations

import math
import os

from ursina import Entity, Text, Texture, application, camera, color, destroy

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


def hero_picture(parent, ch, x, y, h, z=-0.003):
    """주인공 그림 + 장착 무기 (필드와 같은 배치: data/weapon_pose.json). 발 기준 (x, y), 높이 h"""
    from src3d.game import FIELD_DIR, IMG, load_json, weapon_quad
    pose = load_json("weapon_pose.json").get(ch.id)
    body = os.path.join(FIELD_DIR, ch.id + "_body.png")
    wid = ch.equip.get("weapon")
    wimg = os.path.join(IMG, "equipment", f"{wid}.png") if wid else ""
    if not (pose and os.path.exists(body) and os.path.exists(wimg)):
        return picture(parent, os.path.join(FIELD_DIR, ch.id + ".png"), x, y, h, origin=(0, -0.5), z=z)
    W, H = pose["size"]
    root = Entity(parent=parent, position=(x, y), z=z)
    bw = h * W / H
    Entity(parent=root, model="quad", texture=_tex(body), origin=(0, -0.5), scale=(bw, h))
    from ursina import Mesh
    verts = [((px / W - 0.5) * bw, (1 - py / H) * h, 0) for px, py in weapon_quad(pose)]
    Entity(parent=root, model=Mesh(vertices=verts, uvs=[(0, 1), (1, 1), (1, 0), (0, 0)], triangles=[0, 2, 1, 0, 3, 2]),
           texture=_tex(wimg), double_sided=True, z=-0.0005 if pose["layer"] == "front" else 0.0005)
    return root


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
def icon_path(iid):
    from src3d.game import IMG
    return os.path.join(IMG, "icons", f"{iid}.png")


def stat_text(stats, crit=0.0, element=None):
    from src.systems.equipment import STAT_NAMES
    parts = [f"{STAT_NAMES.get(k, k)}+{v}" for k, v in stats.items()]
    if crit:
        parts.append(f"치명+{int(round(crit * 100))}%")
    if element:
        parts.append(f"{element} 속성")
    return "  ".join(parts)


def apply_field_item(state, it, target):
    """필드에서 소모품 사용. target: Character 또는 None(전체). 반환: (사용됨, 메시지)"""
    if it.get("damage"):
        return False, "전투에서만 쓸 수 있다."
    tgt = it.get("target", "ally")
    chars = state.party if tgt in ("all_allies", "all_party") else [target]
    msgs, used = [], False
    for ch in chars:
        if not ch.alive:
            if it.get("revive"):
                ch.hp = max(1, int(ch.max_hp * it["revive"]))
                msgs.append(f"{ch.name} 부활")
                used = True
            else:
                continue
        if it.get("heal_hp") and ch.hp < ch.max_hp:
            v = min(it["heal_hp"], ch.max_hp - ch.hp)
            ch.hp += v
            msgs.append(f"{ch.name} HP+{v}")
            used = True
        if it.get("heal_mp") and ch.mp < ch.max_mp:
            v = min(it["heal_mp"], ch.max_mp - ch.mp)
            ch.mp += v
            msgs.append(f"{ch.name} MP+{v}")
            used = True
        if it.get("cure"):
            used = used or tgt == "ally"
    if it.get("cure") and not msgs and used:
        msgs.append("몸 상태가 좋아졌다")
    if not used:
        return False, "지금은 효과가 없다."
    return True, ", ".join(msgs[:4])


class Menu3D:
    COMMANDS = ["상태", "장비", "아이템", "저장", "불러오기", "타이틀로", "게임 종료"]
    ROWS = 8                       # 아이템 목록 한 화면 줄 수

    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-0.3, enabled=False)
        self.content = None
        self.page = "main"
        self.cur = {"main": 0, "status": 0, "items": 0, "target": 0, "save": 0, "load": 0, "confirm": 1,
                    "equip": 0, "eslot": 0, "elist": 0}
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
        self.game.refresh_weapons()

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
            self.page = {"target": "items", "elist": "equip"}.get(p, "main")
            self.msg = ""
            self.render()
            return
        n = self.count()
        if key in UP + DOWN and n:
            k = "eslot" if p == "equip" else p
            self.cur[k] = (self.cur[k] + (1 if key in DOWN else -1)) % n
            g.sfx("sfx_cursor")
            self.render()
        elif key in LEFT + RIGHT and p == "confirm":
            self.cur[p] = 1 - self.cur[p]
            g.sfx("sfx_cursor")
            self.render()
        elif key in LEFT + RIGHT and p in ("status", "equip"):
            self.cur[p] = (self.cur[p] + (1 if key in RIGHT else -1)) % len(g.state.party)
            g.sfx("sfx_cursor")
            self.render()
        elif key in OK:
            self.choose()

    def count(self):
        st = self.game.state
        return {"main": len(self.COMMANDS), "status": len(st.party), "items": len(self.item_list()),
                "target": len(st.party), "save": 3, "load": 3, "confirm": 2, "equip": 3,
                "elist": len(self.equip_choices())}[self.page]

    def item_list(self):
        """소모품 + 소중한 것 [(id, 정의, 개수, 종류)]"""
        from src.datafiles import load_json
        from src.systems import equipment
        defs = load_json("battle.json")["items"]
        out = [(k, defs[k], n, "item") for k, n in self.game.state.items.items() if n > 0 and k in defs]
        for k in sorted(self.game.state.key_items):
            d = equipment.item_def(k)
            if d:
                out.append((k, d, 1, "key"))
        return out

    def equip_choices(self):
        """지금 고른 캐릭터·칸에 낄 수 있는 가방 속 장비 + 해제"""
        from src.systems import equipment
        ch = self.game.state.party[self.cur["equip"]]
        slot = equipment.SLOTS[self.cur["eslot"]]
        out = [(gid, equipment.gear(gid), n) for gid, n in sorted(self.game.state.gear.items())
               if n > 0 and equipment.gear(gid) and equipment.gear(gid)["slot"] == slot and equipment.can_equip(ch.id, gid)]
        out.sort(key=lambda x: (-x[1]["tier"], x[1]["name"]))
        if ch.equip.get(slot) and slot != "weapon":
            out.append((None, {"name": "(장비 해제)", "stats": {}}, 0))
        return out

    def choose(self):
        g = self.game
        p = self.page
        c = self.cur["eslot"] if p == "equip" else self.cur[p]
        if p == "main":
            g.sfx("sfx_confirm")
            cmd = self.COMMANDS[c]
            self.msg = ""
            if cmd == "상태":
                self.page = "status"
            elif cmd == "장비":
                self.page = "equip"
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
        elif p == "equip":
            g.sfx("sfx_confirm")
            self.page, self.cur["elist"] = "elist", 0
            if not self.equip_choices():
                self.page = "equip"
                self.msg = "바꿀 수 있는 장비가 없다."
            self.render()
        elif p == "elist":
            from src.systems import equipment
            ch = g.state.party[self.cur["equip"]]
            slot = equipment.SLOTS[self.cur["eslot"]]
            gid, gd, _ = self.equip_choices()[c]
            equipment.equip(g.state, ch, slot, gid)
            g.sfx("sfx_buff")
            self.msg = f"{ch.name}: {gd['name']} 장착" if gid else f"{ch.name}: 장비 해제"
            self.page = "equip"
            g.refresh_weapons()
            self.render()
        elif p == "items":
            items = self.item_list()
            if not items:
                return
            k, it, n, kind = items[c]
            if kind == "key":
                g.sfx("sfx_cancel")
                self.msg = "소중한 것 — 사용할 수 없다."
                self.render()
                return
            if it.get("target") in ("all_allies", "all_party"):
                self.use_item(None)
                return
            g.sfx("sfx_confirm")
            self.page = "target"
            self.render()
        elif p == "target":
            self.use_item(g.state.party[c])
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

    def use_item(self, target):
        g = self.game
        items = self.item_list()
        if not items:
            self.page = "items"
            self.render()
            return
        key, it, _, _ = items[min(self.cur["items"], len(items) - 1)]
        ok, msg = apply_field_item(g.state, it, target)
        self.msg = msg
        if not ok:
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
        Entity(parent=c, model="quad", scale=(4, 2), color=color.rgba(0, 0, 0, 0.45), z=0.01)
        Panel(0.3, 0.66, -0.7, 0.1, parent=c)
        shadow_label(c, "MENU", -0.7, 0.39, 1.3, GOLD, font="NanumMyeongjo-Bold.ttf")
        for i, cmd in enumerate(self.COMMANDS):
            y = 0.31 - i * 0.07
            sel = i == self.cur["main"]
            if sel:
                Entity(parent=c, model="quad", position=(-0.7, y), scale=(0.27, 0.058), color=SEL_FILL, z=-0.001)
                label(c, "▶", -0.835, y, 0.8, GOLD)
            label(c, cmd, -0.8, y, 1.08, CREAM if (sel or self.page == "main") else DIM)
        from src.systems import save
        Panel(0.3, 0.17, -0.7, -0.36, parent=c)
        label(c, f"GOLD  {st.gold}", -0.83, -0.31, 0.95, CREAM)
        label(c, f"시간  {save.fmt_time(st.playtime)}", -0.83, -0.36, 0.9, CREAM)
        label(c, g.world.m["name"] if g.world else "", -0.83, -0.41, 0.8, DIM)
        page = self.page
        if page in ("main", "target"):
            self.party_cards(c, sel=self.cur["target"] if page == "target" else None)
            if page == "target":
                items = self.item_list()
                key, it, n, _ = items[self.cur["items"]] if items else (None, {}, 0, "")
                Panel(1.12, 0.08, 0.16, -0.43, parent=c)
                label(c, f"{it.get('name', '')} ({n}) — 누구에게 사용할까?", -0.38, -0.43, 0.95, GOLD)
        elif page == "status":
            self.status_page(c, st.party[self.cur["status"]])
        elif page in ("equip", "elist"):
            self.equip_page(c)
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
            Panel(0.9, 0.07, 0.16, 0.45, parent=c, z=-0.02)
            m = label(c, self.msg, 0.16, 0.45, 0.9, CREAM, origin=(0, 0))
            m.z = -0.03

    def party_cards(self, c, sel=None):
        from src.entities.party import exp_to_next

        for i, ch in enumerate(self.game.state.party):
            y = 0.27 - i * 0.235
            hi = sel == i
            Panel(1.12, 0.205, 0.16, y, parent=c, border=GOLD if hi or sel is None else color.rgba(0.4, 0.34, 0.24, 1),
                  fill=color.rgba(0.22, 0.17, 0.1, 0.95) if hi else color.rgba(0.06, 0.07, 0.12, 0.86))
            hero_picture(c, ch, -0.33, y - 0.095, 0.19)
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
        from src.systems import equipment
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
        crit = equipment.crit_bonus(ch)
        label(c, f"치명타 {int(round((0.12 + crit) * 100))}%", -0.4, 0.22 - 7 * 0.05, 0.85, DIM)
        label(c, "스킬", -0.05, 0.22, 0.95, GOLD)
        for i, sk in enumerate(ch.skills(all_=True)[:7]):
            y = 0.17 - i * 0.05
            learned = sk["level"] <= ch.level
            cost = f"MP {sk['mp']}" if sk["mp"] else (f"증기 {sk['steam_cost']}" if sk["steam_cost"] else "")
            label(c, sk["name"] if learned else f"{sk['name']} (Lv {sk['level']})", -0.05, y, 0.82,
                  CREAM if learned else DIM)
            label(c, cost, 0.2, y, 0.72, DIM, origin=(0.5, 0))
        for i, slot in enumerate(equipment.SLOTS):          # 장착 장비
            gd = equipment.gear(ch.equip.get(slot))
            y = -0.25 - i * 0.055
            label(c, equipment.SLOT_NAMES[slot], -0.4, y, 0.8, DIM)
            if gd:
                picture(c, icon_path(gd["id"]), -0.27, y, 0.05)
            label(c, gd["name"] if gd else "—", -0.24, y, 0.85, CREAM)

    def equip_page(self, c):

        from src.systems import equipment
        g = self.game
        ch = g.state.party[self.cur["equip"]]
        Panel(1.16, 0.86, 0.14, 0.0, parent=c)
        hero_picture(c, ch, 0.52, -0.4, 0.5, z=-0.001)
        shadow_label(c, ch.name, -0.4, 0.37, 1.4, CREAM, origin=(-0.5, 0), font="NanumMyeongjo-Bold.ttf")
        label(c, "◀ ▶ 동료 바꾸기", 0.68, 0.39, 0.7, DIM, origin=(0.5, 0))
        for i, slot in enumerate(equipment.SLOTS):
            y = 0.27 - i * 0.075
            gd = equipment.gear(ch.equip.get(slot))
            sel = i == self.cur["eslot"]
            if sel:
                Entity(parent=c, model="quad", position=(-0.1, y), scale=(0.62, 0.064), color=SEL_FILL, z=-0.001)
                label(c, "▶", -0.43, y, 0.8, GOLD)
            label(c, equipment.SLOT_NAMES[slot], -0.4, y, 0.9, DIM)
            if gd:
                picture(c, icon_path(gd["id"]), -0.27, y, 0.06)
            label(c, gd["name"] if gd else "—", -0.23, y, 1.0, CREAM if sel else DIM)
        rows = [("atk", "공격"), ("def", "방어"), ("mag", "마력"), ("res", "저항"), ("spd", "속도"), ("hp", "HP"), ("mp", "MP")]
        diff = {}
        if self.page == "elist":
            opts = self.equip_choices()
            gid, gd, n = opts[self.cur["elist"]] if opts else (None, {}, 0)
            diff = equipment.stat_diff(ch, gid, equipment.SLOTS[self.cur["eslot"]])
            # 후보 목록
            Panel(0.62, 0.42, -0.1, -0.2, parent=c, fill=color.rgba(0.1, 0.09, 0.07, 0.96), z=-0.004)
            top = max(0, self.cur["elist"] - 4)
            for r, (oid, od, on) in enumerate(opts[top:top + 6]):
                i = top + r
                y = -0.03 - r * 0.062
                sel = i == self.cur["elist"]
                if sel:
                    Entity(parent=c, model="quad", position=(-0.1, y), scale=(0.6, 0.056), color=SEL_FILL, z=-0.006)
                if oid:
                    picture(c, icon_path(oid), -0.36, y, 0.05, z=-0.007)
                t = label(c, od["name"] + (f"  ×{on}" if on > 1 else ""), -0.33, y, 0.88, GOLD if sel else CREAM)
                t.z = -0.008
            if gd:
                d = label(c, stat_text(gd.get("stats", {}), gd.get("crit", 0), gd.get("element")), -0.4, -0.45, 0.75, CREAM)
                d.z = -0.008
        for i, (k, name) in enumerate(rows):                 # 능력치 (바뀔 값 미리보기)
            y = 0.04 - i * 0.045 if self.page == "equip" else 0.27 - i * 0.045
            x = -0.4 if self.page == "equip" else 0.25
            if self.page == "elist" and i >= 7:
                break
            v = ch.stat(k) if k not in ("hp", "mp") else (ch.max_hp if k == "hp" else ch.max_mp)
            label(c, name, x, y, 0.82, DIM)
            label(c, str(v), x + 0.18, y, 0.85, CREAM, origin=(0.5, 0))
            dv = diff.get(k, 0)
            if dv:
                label(c, f"→ {v + dv}", x + 0.21, y, 0.85, color.rgba32(120, 230, 140) if dv > 0 else color.rgba32(240, 110, 100))

    def items_page(self, c):
        items = self.item_list()
        Panel(1.16, 0.86, 0.14, 0.0, parent=c)
        shadow_label(c, "아이템", -0.4, 0.37, 1.3, GOLD, origin=(-0.5, 0), font="NanumMyeongjo-Bold.ttf")
        if not items:
            label(c, "가진 아이템이 없다.", -0.4, 0.25, 1.0, DIM)
            return
        cur = self.cur["items"]
        top = max(0, min(cur - self.ROWS // 2, len(items) - self.ROWS))
        for r, (k, it, n, kind) in enumerate(items[top:top + self.ROWS]):
            i = top + r
            y = 0.28 - r * 0.068
            sel = i == cur
            if sel:
                Entity(parent=c, model="quad", position=(0.14, y), scale=(1.1, 0.06), color=SEL_FILL, z=-0.001)
                label(c, "▶", -0.43, y, 0.8, GOLD)
            picture(c, icon_path(k), -0.37, y, 0.058)
            label(c, it["name"], -0.33, y, 1.0, CREAM if kind == "item" else color.rgba32(140, 220, 255))
            label(c, f"× {n}" if kind == "item" else "소중한 것", 0.66, y, 0.9, CREAM, origin=(0.5, 0))
        if top > 0:
            label(c, "▲", 0.66, 0.34, 0.8, DIM, origin=(0.5, 0))
        if top + self.ROWS < len(items):
            label(c, "▼", 0.66, 0.28 - self.ROWS * 0.068 + 0.03, 0.8, DIM, origin=(0.5, 0))
        it = items[min(cur, len(items) - 1)][1]
        Panel(1.08, 0.09, 0.14, -0.37, parent=c, fill=color.rgba(0.12, 0.1, 0.08, 0.95))
        label(c, it.get("desc", ""), -0.38, -0.37, 0.9, CREAM)


# ====================================================================== 상점·여관
class ShopUI:
    """상점(사기/팔기) + 여관. 왼쪽 목록, 오른쪽 상세(아이콘·설명·능력치·동료별 비교)."""
    ROWS = 9

    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-0.35, enabled=False)
        self.content = None
        self.shop_id = None
        self.page = "mode"           # mode / buy / sell / inn
        self.cur = {"mode": 0, "buy": 0, "sell": 0, "inn": 0}
        self.msg = ""

    @property
    def active(self):
        return self.root.enabled

    def open(self, shop_id):
        self.shop_id = shop_id
        self.page, self.msg = "mode", ""
        self.cur = {"mode": 0, "buy": 0, "sell": 0, "inn": 0}
        self.root.enabled = True
        self.game.hint.enabled = False
        self.render()

    def open_inn(self):
        self.shop_id = None
        self.page, self.msg = "inn", ""
        self.cur["inn"] = 0
        self.root.enabled = True
        self.game.hint.enabled = False
        self.render()

    def close(self):
        self.root.enabled = False
        if self.content:
            destroy(self.content)
            self.content = None
        self.game.hint.enabled = self.game.mode == "field"
        self.game.refresh_weapons()

    # ------------------------------------------------------------ 데이터
    def buy_list(self):
        from src.systems import equipment
        return equipment.shop_stock(self.game.state, self.shop_id)

    def sell_list(self):
        from src.systems import equipment
        st = self.game.state
        out = [(k, equipment.item_def(k), n) for k, n in st.items.items() if n > 0 and equipment.sell_price(k)]
        out += [(k, equipment.item_def(k), n) for k, n in sorted(st.gear.items()) if n > 0]
        return [x for x in out if x[1]]

    # ------------------------------------------------------------ 입력
    def input(self, key):
        g = self.game
        p = self.page
        if key in BACK:
            g.sfx("sfx_cancel")
            if p in ("mode", "inn"):
                self.close()
            else:
                self.page, self.msg = "mode", ""
                self.render()
            return
        n = {"mode": lambda: 3, "buy": lambda: len(self.buy_list()), "sell": lambda: len(self.sell_list()),
             "inn": lambda: 2}[p]()
        if key in UP + DOWN + LEFT + RIGHT and n:
            self.cur[p] = (self.cur[p] + (1 if key in DOWN + RIGHT else -1)) % n
            g.sfx("sfx_cursor")
            self.render()
        elif key in OK:
            self.choose()

    def choose(self):
        from src.systems import equipment
        g = self.game
        st = g.state
        p = self.page
        c = self.cur[p]
        if p == "mode":
            if c == 2:
                g.sfx("sfx_cancel")
                self.close()
                return
            g.sfx("sfx_confirm")
            self.page, self.msg = ("buy", "sell")[c], ""
            self.cur[self.page] = 0
        elif p == "buy":
            iid, d, ok, hint = self.buy_list()[c]
            if not ok:
                g.sfx("sfx_cancel")
                self.msg = f"아직 들어오지 않은 물건이다. ({hint})"
            elif st.gold < d["price"]:
                g.sfx("sfx_cancel")
                self.msg = "골드가 모자란다."
            else:
                st.gold -= d["price"]
                equipment.give(st, iid)
                g.sfx("sfx_confirm")
                self.msg = f"「{d['name']}」을(를) 샀다.  (-{d['price']} G)"
        elif p == "sell":
            items = self.sell_list()
            if not items:
                return
            iid, d, n = items[c]
            price = equipment.sell_price(iid)
            if d["slot"] == "item":
                st.items[iid] -= 1
            else:
                st.gear[iid] -= 1
                if st.gear[iid] <= 0:
                    del st.gear[iid]
            st.gold += price
            g.sfx("sfx_confirm")
            self.msg = f"「{d['name']}」을(를) 팔았다.  (+{price} G)"
            self.cur["sell"] = min(self.cur["sell"], max(0, len(self.sell_list()) - 1))
        elif p == "inn":
            if c == 1:
                g.sfx("sfx_cancel")
                self.close()
                return
            price = equipment.inn_price(st)
            if st.gold < price:
                g.sfx("sfx_cancel")
                self.msg = "골드가 모자란다."
            else:
                st.gold -= price
                self.close()

                def rest():
                    for ch in st.party:
                        ch.full_heal()
                    g.show_toast("푹 쉬었다! 모두의 HP·MP가 회복되었다.", 2.6)
                    g.sfx("heal")
                g.fade_to(rest, 0.8)
                return
        self.render()

    # ------------------------------------------------------------ 그리기
    def render(self):
        from src.systems import equipment
        if self.content:
            destroy(self.content)
        c = self.content = Entity(parent=self.root)
        g = self.game
        st = g.state
        Entity(parent=c, model="quad", scale=(4, 2), color=color.rgba(0, 0, 0, 0.5), z=0.01)
        if self.page == "inn":
            inn = equipment.data()["inn"]
            price = equipment.inn_price(st)
            Panel(0.8, 0.34, 0, 0.02, parent=c)
            shadow_label(c, inn["name"], 0, 0.13, 1.6, GOLD, font="NanumMyeongjo-Bold.ttf")
            label(c, f"하룻밤 {price} 골드입니다. 묵고 가시겠어요?", 0, 0.05, 1.0, CREAM, origin=(0, 0))
            label(c, f"(가진 골드: {st.gold})", 0, 0.0, 0.85, DIM, origin=(0, 0))
            for i, opt in enumerate(("묵는다", "그만둔다")):
                x = -0.12 + i * 0.24
                sel = i == self.cur["inn"]
                if sel:
                    Entity(parent=c, model="quad", position=(x, -0.08), scale=(0.2, 0.06), color=SEL_FILL, z=-0.001)
                label(c, opt, x, -0.08, 1.05, GOLD if sel else DIM, origin=(0, 0))
            if self.msg:
                label(c, self.msg, 0, -0.2, 0.95, color.rgba32(240, 130, 110), origin=(0, 0))
            return
        shop = equipment.data()["shops"][self.shop_id]
        Panel(1.7, 0.09, 0, 0.44, parent=c)
        shadow_label(c, shop["name"], -0.8, 0.44, 1.4, GOLD, origin=(-0.5, 0), font="NanumMyeongjo-Bold.ttf")
        label(c, f"GOLD  {st.gold}", 0.8, 0.44, 1.1, CREAM, origin=(0.5, 0))
        if self.page == "mode":
            Panel(0.4, 0.3, 0, 0.0, parent=c)
            for i, opt in enumerate(("사기", "팔기", "나가기")):
                y = 0.08 - i * 0.08
                sel = i == self.cur["mode"]
                if sel:
                    Entity(parent=c, model="quad", position=(0, y), scale=(0.34, 0.064), color=SEL_FILL, z=-0.001)
                label(c, opt, 0, y, 1.2, GOLD if sel else CREAM, origin=(0, 0))
            return
        items = self.buy_list() if self.page == "buy" else [(k, d, True, "", n) for k, d, n in self.sell_list()]
        Panel(0.9, 0.78, -0.42, -0.04, parent=c)
        label(c, "사기" if self.page == "buy" else "팔기", -0.84, 0.32, 0.95, GOLD)
        cur = self.cur[self.page]
        if not items:
            label(c, "팔 수 있는 물건이 없다.", -0.8, 0.24, 1.0, DIM)
        top = max(0, min(cur - self.ROWS // 2, len(items) - self.ROWS))
        for r, it in enumerate(items[top:top + self.ROWS]):
            iid, d, ok = it[0], it[1], it[2]
            i = top + r
            y = 0.25 - r * 0.068
            sel = i == cur
            if sel:
                Entity(parent=c, model="quad", position=(-0.42, y), scale=(0.88, 0.06), color=SEL_FILL, z=-0.001)
            picture(c, icon_path(iid), -0.8, y, 0.058)
            name = d["name"] if ok else "？？？"
            col = CREAM if ok else DIM
            if d.get("source") == "legend":
                col = color.rgba32(255, 210, 110)
            label(c, name, -0.76, y, 0.95, col)
            if self.page == "buy":
                price = f"{d['price']} G" if ok else "입고 예정"
                pc = CREAM if ok and st.gold >= d["price"] else (DIM if not ok else color.rgba32(220, 110, 100))
                label(c, price, 0.0, y, 0.9, pc, origin=(0.5, 0))
            else:
                label(c, f"×{it[4]}  {equipment.sell_price(iid)} G", 0.0, y, 0.85, CREAM, origin=(0.5, 0))
        if items:
            self.detail(c, items[min(cur, len(items) - 1)])
        if self.msg:
            Panel(1.2, 0.07, 0, -0.46, parent=c, z=-0.02)
            m = label(c, self.msg, 0, -0.46, 0.95, CREAM, origin=(0, 0))
            m.z = -0.03

    def detail(self, c, it):
        from src.systems import equipment
        st = self.game.state
        iid, d, ok = it[0], it[1], it[2]
        Panel(0.74, 0.78, 0.5, -0.04, parent=c)
        if not ok:
            label(c, "아직 들어오지 않은 물건", 0.5, 0.2, 1.0, DIM, origin=(0, 0))
            label(c, it[3], 0.5, 0.13, 0.9, GOLD, origin=(0, 0))
            return
        picture(c, icon_path(iid), 0.24, 0.24, 0.13)
        label(c, d["name"], 0.33, 0.27, 1.1, GOLD)
        kind = {"weapon": "무기", "armor": "방어구", "accessory": "장신구", "item": "소모품", "key": "소중한 것"}[d["slot"]]
        label(c, f"{kind}    보유 {equipment.owned(st, iid)}", 0.33, 0.21, 0.8, DIM)
        t = Text(parent=c, text=d.get("desc", ""), position=(0.16, 0.13), origin=(-0.5, 0.5), scale=0.85,
                 color=CREAM, wordwrap=26, z=-0.002)
        t.line_height = 1.2
        if d["slot"] in ("weapon", "armor", "accessory"):
            label(c, stat_text(d["stats"], d.get("crit", 0), d.get("element")), 0.16, -0.02, 0.82, color.rgba32(140, 220, 255))
            label(c, "동료별 비교", 0.16, -0.09, 0.85, GOLD)
            for i, ch in enumerate(st.party):
                y = -0.15 - i * 0.065
                label(c, ch.name.split()[0], 0.16, y, 0.85, CREAM)
                if not equipment.can_equip(ch.id, iid):
                    label(c, "장비 불가", 0.33, y, 0.8, DIM)
                    continue
                diff = equipment.stat_diff(ch, iid, d["slot"])
                if not diff:
                    label(c, "변화 없음", 0.33, y, 0.8, DIM)
                    continue
                x = 0.33
                for k, v in list(diff.items())[:3]:
                    s = f"{equipment.STAT_NAMES[k]}{'+' if v > 0 else ''}{v}"
                    label(c, s, x, y, 0.8, color.rgba32(120, 230, 140) if v > 0 else color.rgba32(240, 110, 100))
                    x += 0.12


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
