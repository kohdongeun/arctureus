"""data/equipment.json 생성 (장비 목록 원본). 수치·가격·그림 파라미터를 한곳에서 관리.

    python tools/data/make_equipment.py
"""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PRICE = {0: 0, 1: 180, 2: 520, 3: 1300, 4: 2900, 5: 6200, 6: 11500}


def W(id_, name, char, tier, stats, art, desc, price=None, src="shop", element=None, crit=0.0):
    d = {"id": id_, "name": name, "slot": "weapon", "chars": [char], "tier": tier, "stats": stats, "art": art,
         "desc": desc, "price": PRICE[tier] if price is None else price, "source": src}
    if element:
        d["element"] = element
    if crit:
        d["crit"] = crit
    return d


weapons = [
    # ---------------- 루크: 대검 (atk)
    W("w_ashbringer_raw", "애쉬브링어(미완성)", "luke", 0, {"atk": 8}, {"type": "sword", "shape": "straight", "metal": "steel", "guard": "bar", "hilt": "leather", "gem": None}, "아버지의 부러진 기사검을 7년 동안 고쳐 만든 증기 대검.", src="start"),
    W("w_broadsword", "강철 브로드소드", "luke", 1, {"atk": 10}, {"type": "sword", "shape": "straight", "metal": "steel", "guard": "bar", "hilt": "leather", "gem": None, "width": 0.85}, "굴뚝거리 대장간의 기본 대검. 튼튼하고 정직하다."),
    W("w_rivet_claymore", "리벳 클레이모어", "luke", 2, {"atk": 18, "def": 2}, {"type": "sword", "shape": "straight", "metal": "iron", "guard": "wing", "hilt": "leather", "gem": None, "rivets": True}, "리벳으로 덧댄 철판이 무게를 더한다."),
    W("w_piston_blade", "증기 피스톤 블레이드", "luke", 3, {"atk": 28}, {"type": "sword", "shape": "piston", "metal": "steel", "guard": "gear", "hilt": "brass", "gem": "amber", "pipes": True}, "피스톤이 칼날을 밀어내 일격의 무게를 더한다. 증기 속성.", element="증기"),
    W("w_gear_greatsword", "황동 톱니 대검", "luke", 4, {"atk": 38, "spd": 2}, {"type": "sword", "shape": "serrated", "metal": "brass", "guard": "gear", "hilt": "brass", "gem": "amber"}, "톱니 칼날이 기계의 이음새를 물어뜯는다."),
    W("w_ether_buster", "에테르 버스터", "luke", 5, {"atk": 52, "mag": 6}, {"type": "sword", "shape": "cleaver", "metal": "dark", "guard": "wing", "hilt": "brass", "gem": "cyan", "glow": "cyan", "runes": True}, "칼날 속 에테르 관이 푸르게 빛난다."),
    W("w_furnace_zanbato", "용광로 참마도", "luke", 6, {"atk": 66}, {"type": "sword", "shape": "flame", "metal": "dark", "guard": "gear", "hilt": "brass", "gem": "ruby", "glow": "orange", "runes": True}, "용광로의 열을 품은 거대한 참마도. 증기 속성.", element="증기", crit=0.05),
    W("w_rusted_knight", "녹슨 기사의 대검", "luke", 3, {"atk": 26, "res": 6}, {"type": "sword", "shape": "straight", "metal": "rust", "guard": "wing", "hilt": "leather", "gem": "jade"}, "숲에 잠든 옛 서약 기사의 검. 녹 아래 서약의 문장이 보인다.", price=900, src="chest"),
    W("w_frost_fang", "서리 송곳니", "luke", 4, {"atk": 40, "spd": 3}, {"type": "sword", "shape": "fang", "metal": "ice", "guard": "wing", "hilt": "silver", "gem": "cyan", "glow": "white"}, "차가운 공명이 깃든 검. 공명 속성.", price=2000, src="chest", element="공명", crit=0.04),
    W("w_oath_oscar", "서약검 오스카", "luke", 7, {"atk": 110, "def": 10}, {"type": "sword", "shape": "holy", "metal": "gold", "guard": "wing", "hilt": "gold", "gem": "white", "glow": "gold", "runes": True}, "마지막 서약 기사 오스카의 진짜 검. 맹세의 빛이 녹을 태운다. 맹세 속성.", price=30000, src="legend", element="맹세", crit=0.1),
    # ---------------- 아이리스: 지팡이 (mag)
    W("w_tuning_fork", "공명 소리굽쇠", "iris", 0, {"mag": 8}, {"type": "staff", "head": "fork", "shaft": "iron", "gem": None}, "아이리스가 처음부터 들고 있던 소리굽쇠 지팡이.", src="start"),
    W("w_oak_staff", "참나무 지팡이", "iris", 1, {"mag": 10, "mp": 10}, {"type": "staff", "head": "knot", "shaft": "wood", "gem": "jade"}, "숲 참나무로 깎은 소박한 지팡이."),
    W("w_bronze_rod", "청동 공명봉", "iris", 2, {"mag": 18, "res": 3}, {"type": "staff", "head": "ring", "shaft": "brass", "gem": "cyan"}, "고리가 맑게 울린다."),
    W("w_crystal_fork", "수정 소리굽쇠", "iris", 3, {"mag": 28, "mp": 20}, {"type": "staff", "head": "crystal_fork", "shaft": "silver", "gem": "cyan", "glow": "cyan"}, "수정 갈래가 공명을 증폭한다."),
    W("w_clock_scepter", "시계태엽 셉터", "iris", 4, {"mag": 38, "spd": 2}, {"type": "staff", "head": "gear", "shaft": "brass", "gem": "amber", "glow": "amber"}, "끝에서 작은 태엽이 쉬지 않고 돈다."),
    W("w_ether_harp", "에테르 하프 스태프", "iris", 5, {"mag": 52, "res": 8}, {"type": "staff", "head": "harp", "shaft": "silver", "gem": "violet", "glow": "violet"}, "에테르 현이 바람에 노래한다."),
    W("w_constellation", "성좌의 지휘봉", "iris", 6, {"mag": 66, "mp": 40}, {"type": "staff", "head": "star", "shaft": "gold", "gem": "white", "glow": "gold"}, "별자리를 지휘하듯 공명을 다룬다.", crit=0.03),
    W("w_elder_branch", "고목의 가지", "iris", 3, {"mag": 26, "hp": 40}, {"type": "staff", "head": "leaf", "shaft": "wood", "gem": "jade", "glow": "green"}, "고목이 스스로 내어 준 가지. 생명이 깃들어 있다.", price=900, src="chest"),
    W("w_moon_rod", "달빛 공명봉", "iris", 4, {"mag": 40, "res": 6}, {"type": "staff", "head": "crescent", "shaft": "silver", "gem": "white", "glow": "white"}, "달빛을 머금은 초승달 지팡이.", price=2000, src="chest", crit=0.05),
    W("w_eleion", "천년의 공명봉 엘레이온", "iris", 7, {"mag": 110, "mp": 80, "res": 15}, {"type": "staff", "head": "halo", "shaft": "gold", "gem": "cyan", "glow": "cyan"}, "천 년 전 대마도사가 녹안개를 봉인할 때 쓴 지팡이.", price=30000, src="legend", crit=0.06),
    # ---------------- 제드: 소총 (atk)
    W("w_old_rifle", "구식 에테르 소총", "zed", 0, {"atk": 8}, {"type": "rifle", "wood": "walnut", "metal": "iron", "barrels": 2, "scope": False}, "제드가 오래 써 온 에테르 소총.", src="start"),
    W("w_musket", "사냥용 머스킷", "zed", 1, {"atk": 10}, {"type": "rifle", "wood": "oak", "metal": "iron", "barrels": 1, "scope": False}, "흔한 사냥총이지만 잘 맞는다."),
    W("w_double_barrel", "쌍열 엽총", "zed", 2, {"atk": 17, "spd": 2}, {"type": "rifle", "wood": "walnut", "metal": "steel", "barrels": 2, "scope": False, "short": True}, "두 발을 연달아 쏜다."),
    W("w_brass_sniper", "황동 저격총", "zed", 3, {"atk": 27}, {"type": "rifle", "wood": "walnut", "metal": "brass", "barrels": 1, "scope": True}, "황동 망원 조준경이 달린 저격총.", crit=0.05),
    W("w_steam_repeater", "스팀 리피터", "zed", 4, {"atk": 37, "spd": 3}, {"type": "rifle", "wood": "dark", "metal": "brass", "barrels": 1, "scope": False, "drum": True, "pipes": True}, "증기압으로 연사하는 회전 탄창 소총."),
    W("w_ether_railgun", "에테르 레일건", "zed", 5, {"atk": 51, "mag": 6}, {"type": "rifle", "wood": "dark", "metal": "dark", "barrels": 1, "scope": True, "coils": True, "glow": "cyan"}, "에테르 코일이 탄환을 가속한다. 공명 속성.", element="공명"),
    W("w_sky_hunter", "천공의 사냥꾼", "zed", 6, {"atk": 65}, {"type": "rifle", "wood": "red", "metal": "gold", "barrels": 1, "scope": True, "coils": True, "glow": "gold", "bayonet": True}, "하늘해적들 사이에서 전설로 불리는 장총.", crit=0.08),
    W("w_pirate_king", "해적왕의 장총", "zed", 3, {"atk": 29, "spd": 4}, {"type": "rifle", "wood": "red", "metal": "gold", "barrels": 1, "scope": False, "bayonet": True}, "옛 해적왕의 금박 장총.", price=900, src="chest", crit=0.03),
    W("w_hawk_eye", "매의 눈", "zed", 4, {"atk": 40}, {"type": "rifle", "wood": "oak", "metal": "silver", "barrels": 1, "scope": True, "glow": "white"}, "핀의 시야와 연결되는 조준경.", price=2000, src="chest", crit=0.1),
    W("w_albatross_nova", "알바트로스 노바", "zed", 7, {"atk": 108, "spd": 10}, {"type": "rifle", "wood": "dark", "metal": "gold", "barrels": 2, "scope": True, "coils": True, "glow": "violet", "bayonet": True}, "알바트로스호의 주포를 줄여 만든 전설의 장총.", price=30000, src="legend", crit=0.12),
]


def A(id_, name, kind, chars, tier, stats, desc, price=None, src="shop", color=None):
    return {"id": id_, "name": name, "slot": "armor", "kind": kind, "chars": chars, "tier": tier, "stats": stats,
            "desc": desc, "price": PRICE[tier] - 20 if price is None else price, "source": src, "color": color}


L, I, Z = ["luke"], ["iris"], ["zed"]
ALL = ["luke", "iris", "zed"]
armors = [
    A("a_old_oath_plate", "낡은 서약 흉갑", "heavy", L, 0, {"def": 6}, "아버지의 흉갑에 피스톤 견갑을 덧댔다.", src="start", color="brass"),
    A("a_padded_plate", "가죽 덧댐 흉갑", "heavy", L, 1, {"def": 8, "hp": 10}, "가죽을 덧대 충격을 줄인다.", color="leather"),
    A("a_rivet_armor", "리벳 강철 갑옷", "heavy", L, 2, {"def": 15, "hp": 20}, "리벳으로 짠 강철 갑옷.", color="steel"),
    A("a_steam_plate", "증기 판금 갑옷", "heavy", L, 3, {"def": 24, "hp": 50}, "증기 완충 장치가 든 판금 갑옷.", color="steel"),
    A("a_brass_guard_mail", "황동 근위 갑주", "heavy", L, 4, {"def": 34, "res": 6}, "근위대 장교용 갑주.", color="brass"),
    A("a_ether_plate", "에테르 강화 갑주", "heavy", L, 5, {"def": 46, "hp": 120}, "에테르 결계가 흐르는 갑주.", color="cyan"),
    A("a_rusted_knight_mail", "녹슨 기사의 갑옷", "heavy", L, 3, {"def": 22, "res": 10}, "옛 서약 기사의 갑옷.", price=850, src="chest", color="rust"),
    A("a_oath_holy_plate", "서약 기사의 성갑", "heavy", L, 7, {"def": 80, "res": 30, "hp": 300}, "서약의 빛이 깃든 성갑. 녹이 닿지 못한다.", price=28000, src="legend", color="gold"),
    A("a_lab_coat", "연구원 가운", "robe", I, 0, {"def": 3, "res": 6}, "기술원 연구복.", src="start", color="white"),
    A("a_novice_robe", "견습 로브", "robe", I, 1, {"def": 4, "res": 8}, "마법 견습생의 로브.", color="cyan"),
    A("a_resonance_cloak", "공명 망토", "robe", I, 2, {"def": 7, "res": 14}, "공명을 부드럽게 흘려보내는 망토.", color="teal"),
    A("a_silk_robe", "은사 로브", "robe", I, 3, {"def": 10, "res": 22, "mp": 20}, "은실로 짠 로브.", color="silver"),
    A("a_clockwork_dress", "태엽 수호복", "robe", I, 4, {"def": 14, "res": 30}, "작은 태엽 방어구가 달린 옷.", color="brass"),
    A("a_starlight_robe", "별빛 로브", "robe", I, 5, {"def": 18, "res": 42, "mp": 40}, "밤하늘을 짠 듯한 로브.", color="violet"),
    A("a_elf_robe", "고대 엘프의 로브", "robe", I, 3, {"def": 11, "res": 26, "hp": 60}, "녹색 서약회가 보관하던 로브.", price=850, src="chest", color="green"),
    A("a_archmage_vestment", "대마도사의 성의", "robe", I, 7, {"def": 40, "res": 80, "mp": 100}, "엘레이온 대마도사의 성의.", price=28000, src="legend", color="gold"),
    A("a_captain_coat", "선장 코트", "light", Z, 0, {"def": 5}, "남색 선장 코트.", src="start", color="navy"),
    A("a_quilted_vest", "누빔 조끼", "light", Z, 1, {"def": 7, "spd": 1}, "가볍고 질긴 조끼.", color="leather"),
    A("a_sky_pirate_coat", "하늘해적 코트", "light", Z, 2, {"def": 12, "spd": 2}, "바람을 가르는 해적 코트.", color="red"),
    A("a_reinforced_coat", "강화 가죽 코트", "light", Z, 3, {"def": 20, "hp": 30}, "철판을 숨긴 가죽 코트.", color="leather"),
    A("a_flight_suit", "방탄 비행복", "light", Z, 4, {"def": 29, "spd": 3}, "비행사용 방탄복.", color="olive"),
    A("a_storm_coat", "폭풍 망토 코트", "light", Z, 5, {"def": 40, "res": 10}, "폭풍 속에서도 펄럭이지 않는다.", color="navy"),
    A("a_shadow_cloak", "그림자 망토", "light", Z, 3, {"def": 18, "spd": 6}, "그림자처럼 몸을 감춘다.", price=850, src="chest", color="dark"),
    A("a_albatross_captain", "알바트로스 함장복", "light", Z, 7, {"def": 70, "spd": 12, "res": 25}, "알바트로스호 초대 함장의 제복.", price=28000, src="legend", color="gold"),
    A("a_traveler_cloak", "여행자의 망토", "light", ALL, 1, {"def": 5, "res": 5}, "누구나 걸칠 수 있는 망토.", price=150, color="green"),
    A("a_mithril_mail", "미스릴 사슬옷", "light", ALL, 4, {"def": 26, "res": 20}, "드워프가 짠 가벼운 사슬옷.", price=3200, color="silver"),
]


def X(id_, name, tier, stats, icon, desc, price=None, src="shop", crit=0.0):
    d = {"id": id_, "name": name, "slot": "accessory", "chars": ALL, "tier": tier, "stats": stats, "icon": icon,
         "desc": desc, "price": price if price is not None else {1: 140, 2: 460, 3: 1150, 4: 2700, 5: 6000}[tier],
         "source": src}
    if crit:
        d["crit"] = crit
    return d


accessories = [
    X("x_copper_ring", "구리 반지", 1, {"hp": 30}, "ring", "HP가 조금 오른다."),
    X("x_leather_gloves", "가죽 장갑", 1, {"atk": 4}, "glove", "손에 착 붙는다."),
    X("x_brass_watch", "황동 회중시계", 2, {"spd": 3}, "watch", "시간 감각이 예민해진다."),
    X("x_crystal_pendant", "수정 펜던트", 2, {"mp": 20, "res": 4}, "pendant", "에테르를 머금은 수정."),
    X("x_steel_bracer", "강철 손목보호대", 2, {"def": 6}, "bracer", "단단한 손목보호대."),
    X("x_pressure_gauge", "증기 압력계", 3, {"atk": 8}, "gauge", "힘을 쓸 때를 알려 준다.", crit=0.03),
    X("x_ether_earring", "에테르 귀걸이", 3, {"mag": 10}, "earring", "마력이 귓가에 맴돈다."),
    X("x_gear_brooch", "기어 브로치", 4, {"def": 10, "res": 10}, "brooch", "톱니 모양 부적."),
    X("x_hawk_feather", "매의 깃털", 4, {"spd": 6}, "feather", "몸이 가벼워진다.", crit=0.04),
    X("x_life_cog", "생명의 톱니", 5, {"hp": 200}, "cog", "심장처럼 고동치는 톱니."),
    X("x_sage_glasses", "현자의 안경", 5, {"mag": 20, "mp": 50}, "glasses", "보이지 않던 것이 보인다."),
    X("x_lucky_nut", "토비의 행운 너트", 3, {"spd": 2}, "nut", "토비가 숨겨 둔 행운의 너트.", price=600, src="chest", crit=0.06),
    X("x_elf_dew", "엘프의 이슬 목걸이", 3, {"hp": 80, "res": 8}, "pendant", "마르지 않는 이슬이 담겼다.", price=800, src="chest"),
    X("x_b7_core", "B-7의 코어", 4, {"atk": 6, "mag": 6, "def": 6, "spd": 3}, "cog", "버려진 로봇이 남긴 따뜻한 코어.", price=1500, src="chest"),
]

key_items = {
    "key_oath_seal_1": {"name": "서약의 인장 조각 (검)", "desc": "검이 새겨진 돌 조각. 잊힌 서약의 사당과 관련 있는 듯하다."},
    "key_oath_seal_2": {"name": "서약의 인장 조각 (방패)", "desc": "방패가 새겨진 돌 조각."},
    "key_oath_seal_3": {"name": "서약의 인장 조각 (불꽃)", "desc": "불꽃이 새겨진 돌 조각."},
}

shops = {
    "weapon_shop": {"name": "톱니 대장간", "keeper": "blacksmith",
                    "stock": [w["id"] for w in weapons if w["source"] == "shop"]},
    "item_shop": {"name": "모르간 수리점", "keeper": "morgan",
                  "stock": ["item_steam_tonic", "item_ether_flask", "item_antidote_oil", "item_high_tonic",
                            "item_wakeup_spring", "item_steam_bomb", "item_field_kit", "item_dense_ether",
                            "item_big_bomb", "item_elixir_distill", "item_mega_ether"]
                  + [a["id"] for a in armors if a["source"] == "shop"]
                  + [x["id"] for x in accessories if x["source"] == "shop"]},
}
# 상점 입고 조건: 단계(tier)별 — 진행·레벨이 오를수록 비싸고 좋은 물건이 들어온다
unlock = {"1": {}, "2": {"any": ["scene:ch3_02", "battles>=3", "level>=5"]}, "3": {"any": ["ch3_clear", "level>=8"]},
          "4": {"any": ["level>=12"]}, "5": {"any": ["level>=18"]}, "6": {"any": ["level>=24"]}}

start = {"luke": {"weapon": "w_ashbringer_raw", "armor": "a_old_oath_plate", "accessory": None},
         "iris": {"weapon": "w_tuning_fork", "armor": "a_lab_coat", "accessory": None},
         "zed": {"weapon": "w_old_rifle", "armor": "a_captain_coat", "accessory": None}}

out = {"_note": "python tools/data/make_equipment.py 로 생성. 무기 그림은 tools/art/gen_equipment.py 가 art 값으로 그린다.",
       "weapons": {w["id"]: w for w in weapons}, "armors": {a["id"]: a for a in armors},
       "accessories": {x["id"]: x for x in accessories}, "key_items": key_items, "shops": shops,
       "unlock": unlock, "start": start, "inn": {"name": "증기 주전자 여관", "price_per_level": 4, "min_price": 20}}
with open(os.path.join(ROOT, "data", "equipment.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(len(weapons), "weapons", len(armors), "armors", len(accessories), "accessories")
