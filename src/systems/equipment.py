"""장비(무기·방어구·장신구)·상점·열쇠 아이템 규칙 (그래픽과 무관 — 2D/3D 공용).

데이터: data/equipment.json (tools/data/make_equipment.py 로 생성), 소모품은 data/battle.json 의 items.
"""
from __future__ import annotations

from src import datafiles

SLOTS = ("weapon", "armor", "accessory")
SLOT_NAMES = {"weapon": "무기", "armor": "방어구", "accessory": "장신구"}
STAT_NAMES = {"hp": "HP", "mp": "MP", "atk": "공격", "def": "방어", "mag": "마력", "res": "저항", "spd": "속도"}


def data():
    return datafiles.load_json("equipment.json")


def gear(gid):
    """장비 정의 (없으면 None)"""
    if not gid:
        return None
    d = data()
    for k in ("weapons", "armors", "accessories"):
        if gid in d[k]:
            return d[k][gid]
    return None


def consumable(iid):
    return datafiles.load_json("battle.json")["items"].get(iid)


def item_def(iid):
    """상점·보물상자에 나오는 아무 물건 (장비/소모품/열쇠)"""
    g = gear(iid)
    if g:
        return g
    c = consumable(iid)
    if c:
        return {**c, "slot": "item", "id": iid}
    k = data()["key_items"].get(iid)
    if k:
        return {**k, "slot": "key", "id": iid, "price": 0}
    return None


def can_equip(cid, gid):
    g = gear(gid)
    return bool(g) and cid in g["chars"]


def bonus(ch):
    """장착 장비의 능력치 합"""
    out = {}
    for slot in SLOTS:
        g = gear(ch.equip.get(slot))
        if g:
            for k, v in g["stats"].items():
                out[k] = out.get(k, 0) + v
    return out


def crit_bonus(ch):
    return sum((gear(ch.equip.get(s)) or {}).get("crit", 0.0) for s in SLOTS)


def weapon_element(ch):
    return (gear(ch.equip.get("weapon")) or {}).get("element")


def stat_diff(ch, gid, slot):
    """gid 를 slot 에 끼우면 능력치가 얼마나 바뀌는지 {stat: 차이}"""
    cur = (gear(ch.equip.get(slot)) or {}).get("stats", {})
    new = (gear(gid) or {}).get("stats", {})
    keys = set(cur) | set(new)
    return {k: new.get(k, 0) - cur.get(k, 0) for k in keys if new.get(k, 0) != cur.get(k, 0)}


def equip(state, ch, slot, gid):
    """장착 (gid=None 이면 해제). 벗은 장비는 가방으로, 낀 장비는 가방에서 하나 뺀다."""
    old = ch.equip.get(slot)
    if gid and state.gear.get(gid, 0) <= 0:
        return False
    if old:
        state.gear[old] = state.gear.get(old, 0) + 1
    if gid:
        state.gear[gid] -= 1
        if state.gear[gid] <= 0:
            del state.gear[gid]
    ch.equip[slot] = gid
    ch.hp, ch.mp = min(ch.hp, ch.max_hp), min(ch.mp, ch.max_mp)
    return True


def give(state, iid, n=1):
    """물건을 얻는다 (종류에 따라 소모품 / 장비 가방 / 소중한 것)"""
    d = item_def(iid)
    if not d:
        return None
    if d["slot"] == "item":
        state.items[iid] = state.items.get(iid, 0) + n
    elif d["slot"] == "key":
        state.key_items.add(iid)
    else:
        state.gear[iid] = state.gear.get(iid, 0) + n
    return d


def owned(state, iid):
    d = item_def(iid)
    if not d:
        return 0
    if d["slot"] == "item":
        return state.items.get(iid, 0)
    if d["slot"] == "key":
        return int(iid in state.key_items)
    return state.gear.get(iid, 0) + sum(1 for c in state.party for s in SLOTS if c.equip.get(s) == iid)


def sell_price(iid):
    d = item_def(iid)
    return max(1, int((d or {}).get("price", 0) * 0.5)) if d and d.get("price") else 0


def unlocked(state, tier):
    """상점 입고 조건 (진행 플래그·레벨·전투 수)"""
    cond = data()["unlock"].get(str(tier), {})
    anyc = cond.get("any")
    if not anyc:
        return True
    lv = max(c.level for c in state.party)
    for c in anyc:
        if c.startswith("level>="):
            if lv >= int(c[7:]):
                return True
        elif c.startswith("battles>="):
            if state.battles_won >= int(c[9:]):
                return True
        elif c in state.flags:
            return True
    return False


def unlock_hint(tier):
    cond = data()["unlock"].get(str(tier), {}).get("any", [])
    for c in cond:
        if c.startswith("level>="):
            return f"Lv {c[7:]} 이상이 되면 입고"
    return "이야기가 진행되면 입고"


def shop_stock(state, shop_id):
    """[(id, 정의, 살 수 있음, 잠김 안내)] — 단계 순으로"""
    out = []
    for iid in data()["shops"][shop_id]["stock"]:
        d = item_def(iid)
        if not d:
            continue
        ok = unlocked(state, d.get("tier", 1))
        out.append((iid, d, ok, "" if ok else unlock_hint(d.get("tier", 1))))
    out.sort(key=lambda x: (x[1]["slot"] != "item", x[1].get("tier", 1), x[1].get("price", 0)))
    return out


def inn_price(state):
    inn = data()["inn"]
    lv = max(c.level for c in state.party)
    return max(inn["min_price"], inn["price_per_level"] * lv)
