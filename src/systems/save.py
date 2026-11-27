"""세이브/로드 (슬롯 3개, JSON).

저장 위치 (exe 안은 실행할 때마다 임시 폴더에 풀리므로 사용자 폴더에 저장):
  Windows : %APPDATA%\\Arcturus_RPG\\saves
  macOS   : ~/Library/Application Support/Arcturus_RPG/saves
  Linux   : ~/.local/share/Arcturus_RPG/saves  (XDG_DATA_HOME 우선)
환경변수 ARCTURUS_SAVE_DIR 로 바꿀 수 있다 (자동 테스트용).
"""
from __future__ import annotations

import json
import os
import sys
import time

from src import config as cfg
from src import datafiles as assets      # pygame 없이 (2D/3D 공용)

SLOTS = 3
VERSION = 1
APP = "Arcturus_RPG"


def save_dir() -> str:
    if os.environ.get("ARCTURUS_SAVE_DIR"):
        d = os.environ["ARCTURUS_SAVE_DIR"]
    elif sys.platform.startswith("win"):
        d = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP, "saves")
    elif sys.platform == "darwin":
        d = os.path.expanduser(f"~/Library/Application Support/{APP}/saves")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        d = os.path.join(base, APP, "saves")
    os.makedirs(d, exist_ok=True)
    return d


def slot_path(slot: int) -> str:
    return os.path.join(save_dir(), f"slot{slot + 1}.sav")


def to_dict(st) -> dict:
    return {
        "version": VERSION,
        "saved_at": time.strftime("%Y-%m-%d %H:%M"),
        "playtime": round(st.playtime, 1),
        "map_id": st.map_id,
        "pos": list(st.pos),
        "dir": st.dir,
        "gold": st.gold,
        "items": dict(st.items),
        "flags": sorted(st.flags),
        "battles_won": st.battles_won,
        "gear": dict(getattr(st, "gear", {})),
        "key_items": sorted(getattr(st, "key_items", set())),
        "party": [{"id": c.id, "level": c.level, "exp": c.exp, "hp": c.hp, "mp": c.mp, "steam": c.steam,
                   "equip": dict(getattr(c, "equip", {}))} for c in st.party],
    }


def apply_dict(st, d: dict):
    """새로 만든 GameState 에 저장 내용을 덮어쓴다 (모르는 캐릭터/아이템은 무시)."""
    st.playtime = float(d.get("playtime", 0))
    st.map_id = d["map_id"]
    st.pos = tuple(d["pos"])
    st.dir = d.get("dir", "se")
    st.gold = int(d.get("gold", 0))
    known_items = assets.load_json("battle.json")["items"]
    st.items = {k: int(v) for k, v in d.get("items", {}).items() if k in known_items}
    st.flags = set(d.get("flags", []))
    st.battles_won = int(d.get("battles_won", 0))
    from src.systems import equipment
    if "gear" in d:                       # 장비가 생기기 전 세이브는 시작 장비 그대로
        st.gear = {k: int(v) for k, v in d["gear"].items() if equipment.gear(k)}
    st.key_items = {k for k in d.get("key_items", []) if equipment.item_def(k)}
    by_id = {c.id: c for c in st.party}
    for p in d.get("party", []):
        c = by_id.get(p["id"])
        if not c:
            continue
        c.level = max(1, int(p["level"]))
        c.exp = int(p["exp"])
        for slot, gid in p.get("equip", {}).items():
            if slot in c.equip and (gid is None or equipment.can_equip(c.id, gid)):
                c.equip[slot] = gid
        c.hp = max(0, min(c.max_hp, int(p["hp"])))
        c.mp = max(0, min(c.max_mp, int(p["mp"])))
        c.steam = int(p.get("steam", 0))
    return st


def save(slot: int, st) -> str:
    path = slot_path(slot)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(to_dict(st), f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)          # 저장 중 꺼져도 기존 세이브가 깨지지 않도록 교체 방식
    return path


def read(slot: int) -> dict | None:
    """슬롯 내용. 없거나 손상되었으면 None."""
    try:
        with open(slot_path(slot), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) and "party" in d and "map_id" in d else None
    except (OSError, ValueError):
        return None


def any_save() -> bool:
    return any(read(i) for i in range(SLOTS))


def map_exists_3d(map_id) -> bool:
    return bool(map_id) and os.path.exists(os.path.join(cfg.DATA, "maps3d", f"{map_id}.json"))


def map_name(map_id) -> str:
    for sub in ("maps3d", "maps"):
        p = os.path.join(cfg.DATA, sub, f"{map_id}.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f).get("name", map_id)
    return str(map_id)


def fmt_time(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"
