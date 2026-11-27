"""자동 플레이 테스트.

화면 없이(SDL dummy) 게임을 실행하고, 키 입력을 주입해 실제 플레이처럼 진행한다:
타이틀 → 마을 인트로 대화 → NPC 대화 → 메뉴 → 배수로 이동 → 랜덤 전투(스킬 전부 사용, 레벨업)
→ 보스전 → 엔딩 대사. 단계마다 스크린샷을 저장하고 마지막에 검증 결과를 출력한다.

    python tools/autotest.py [스크린샷 폴더] [--seed N]
"""
from __future__ import annotations

import collections
import os
import random
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from src import config as cfg  # noqa: E402
from src.engine.core import Game  # noqa: E402
from src.scenes.battle import BattleScene  # noqa: E402
from src.scenes.dialogue import Dialogue  # noqa: E402
from src.scenes.field import FieldScene, KEY_DIR  # noqa: E402
from src.scenes.menu import MenuScene  # noqa: E402
from src.scenes.title import TitleScene  # noqa: E402

DT = 1 / 60
DIR_KEY = {v: k for k, v in KEY_DIR.items()}


class Pilot:
    def __init__(self, game, shots):
        self.g = game
        self.shots = shots
        self.events = collections.Counter()
        self.log = []
        self.levelups = []
        self.skills_used = collections.Counter()
        self.shot_names = []
        self.frame = 0
        game.listeners.append(self.on_event)

    def on_event(self, ev, data):
        self.events[ev] += 1
        if ev == "victory" and data["levelups"]:
            self.levelups.append(data["levelups"])
        if ev == "action" and data.get("kind") == "skill":
            self.skills_used[data["skill"]] += 1
        if ev in ("map_enter", "encounter", "victory", "defeat", "battle_end", "talk"):
            self.log.append(f"[{self.frame / 60:6.1f}s] {ev} {data}")

    def shot(self, name):
        path = os.path.join(self.shots, f"{len(self.shot_names):02d}_{name}.png")
        pygame.image.save(self.g.screen, path)
        self.shot_names.append(path)

    # ---------------------------------------------------------------- 기본 동작
    def frames(self, n):
        for _ in range(n):
            yield

    def press(self, action, gap=4):
        self.g.input.press(action)
        yield
        yield from self.frames(gap)

    def until(self, cond, limit=60 * 30):
        for _ in range(limit):
            if cond():
                return True
            yield
        raise TimeoutError("조건 대기 시간 초과")

    @property
    def scene(self):
        return self.g.scene

    def field(self):
        return next((s for s in reversed(self.g.scenes) if isinstance(s, FieldScene)), None)

    def advance_dialogue(self, shot_at=None):
        i = 0
        while isinstance(self.scene, Dialogue) or self.g.fade:
            if isinstance(self.scene, Dialogue):
                d = self.scene
                d.shown = len(d.line["text"])     # 타자기 효과 건너뛰기 (실제 입력으로도 가능)
                yield
                if shot_at and i in shot_at:
                    self.shot(shot_at[i])
                yield from self.press("confirm", 2)
                i += 1
            else:
                yield

    # ---------------------------------------------------------------- 필드 이동
    def path(self, goal, adjacent=False):
        f = self.field()
        m, p = f.map, f.player
        start = (p.x, p.y)
        prev = {start: None}
        q = collections.deque([start])
        goals = {goal} if not adjacent else {(goal[0] + dx, goal[1] + dy) for dx, dy in cfg.DIRS.values()}
        while q:
            cur = q.popleft()
            if cur in goals:
                out = []
                while prev[cur] is not None:
                    out.append(prev[cur][1])
                    cur = prev[cur][0]
                return out[::-1]
            for d, (dx, dy) in cfg.DIRS.items():
                nx, ny = cur[0] + dx, cur[1] + dy
                if (nx, ny) not in prev and m.walkable(nx, ny) and not f.occupied(nx, ny, p) \
                        and ((nx, ny) not in m.exits or (nx, ny) == goal):
                    prev[(nx, ny)] = (cur, d)
                    q.append((nx, ny))
        return None

    def step(self, d):
        f = self.field()
        p = f.player
        before = (p.x, p.y)
        self.g.input.injected_held = {DIR_KEY[d]}
        for _ in range(40):
            yield
            if p.moving or (p.x, p.y) != before or self.scene is not f:
                break
        self.g.input.injected_held = set()
        while p.moving and self.scene is f:
            yield

    def walk_to(self, goal, adjacent=False, stop_on_scene_change=True):
        for _ in range(200):
            f = self.field()
            if self.scene is not f or self.g.fade:
                if stop_on_scene_change:
                    return False
                yield
                continue
            p = f.player
            if (adjacent and abs(p.x - goal[0]) + abs(p.y - goal[1]) == 1) or (p.x, p.y) == tuple(goal):
                return True
            route = self.path(tuple(goal), adjacent)
            if not route:
                yield from self.frames(20)   # NPC 가 길을 막고 있으면 잠시 대기
                continue
            yield from self.step(route[0])
        return False

    def face(self, target):
        p = self.field().player
        dx, dy = target[0] - p.x, target[1] - p.y
        d = next(k for k, v in cfg.DIRS.items() if v == (dx, dy))
        self.g.input.injected_held = {DIR_KEY[d]}
        yield from self.frames(2)
        self.g.input.injected_held = set()
        yield from self.frames(2)

    def talk(self, npc_id, shot_name=None):
        f = self.field()
        n = next(w for w in f.npcs if w.npc["id"] == npc_id)
        for _ in range(10):
            yield from self.walk_to((n.x, n.y), adjacent=True)
            p = f.player
            if abs(p.x - n.x) + abs(p.y - n.y) == 1 and not n.moving:
                break
            yield from self.frames(30)
        yield from self.face((n.x, n.y))
        yield from self.press("confirm")
        yield from self.until(lambda: isinstance(self.scene, Dialogue), 120)
        yield from self.advance_dialogue({0: shot_name} if shot_name else None)

    # ---------------------------------------------------------------- 전투
    def battle_plan(self, b: BattleScene):
        a = b.actor
        ch = a.ref
        st = self.g.state
        low = [p for p in b.living(True) if p.hp / p.max_hp < 0.4]
        skills = ch.skills()
        # 1) 위험한 아군이 있으면 회복 (아이리스 스킬 → 아이템)
        if low:
            heal = next((s for s in skills if s["kind"] == "heal" and s["target"] == "ally" and a.mp >= s["mp"]), None)
            if heal:   # 대상은 게임이 자동으로 HP 비율이 가장 낮은 아군에 커서를 둔다
                return (1, skills.index(heal), None)
            if st.items.get("item_steam_tonic"):
                ids = [k for k, v in st.items.items() if v > 0]
                return (3, ids.index("item_steam_tonic"), None)
        # 2) 아직 안 써 본 스킬을 우선 사용 (모든 이펙트 검증)
        for i, s in enumerate(skills):
            if self.skills_used[s["id"]] == 0 and a.mp >= s["mp"] and not s.get("steam_cost"):
                if s["kind"] == "heal" and not any(p.hp < p.max_hp for p in b.living(True)):
                    continue
                return (1, i, 0)
        # 3) MP 가 넉넉하면 공격 스킬, 아니면 일반 공격
        atk = [i for i, s in enumerate(skills) if s["kind"] in ("phys", "mag") and a.mp >= s["mp"] * 3
               and not s.get("steam_cost")]
        if atk and random.random() < 0.5:
            return (1, random.choice(atk), 0)
        return (0, None, 0)

    def fight(self, shoot=False):
        yield from self.until(lambda: isinstance(self.scene, BattleScene), 600)
        b = self.scene
        shot_menu = shoot
        shot_fx = shoot
        while self.scene is b and b.state not in ("victory", "defeat"):
            if b.state == "command" and b.menu and not b.sub and not b.target_mode:
                cmd, sub, tgt = self.battle_plan(b)
                for _ in range(cmd):
                    yield from self.press("down", 2)
                yield from self.press("confirm", 3)
                if sub is not None:
                    for _ in range(sub):
                        yield from self.press("down", 2)
                    if shot_menu:
                        self.shot("battle_skill_menu")
                        shot_menu = False
                    yield from self.press("confirm", 3)
                if b.target_mode:
                    if shot_fx:
                        self.shot("battle_target")
                    yield from self.press("confirm", 1)
                if shot_fx and b.seq:
                    yield from self.frames(34)
                    self.shot("battle_effect")
                    shot_fx = False
            else:
                yield
        if self.scene is b:
            yield from self.frames(50)
            self.shot("battle_result_" + b.state)
            won = b.state == "victory"
            yield from self.press("confirm", 2)
            yield from self.until(lambda: not isinstance(self.scene, BattleScene) and not self.g.fade, 300)
            return won
        return True   # 도주

    # ---------------------------------------------------------------- 시나리오
    def script(self):
        yield from self.frames(40)
        self.shot("title")
        yield from self.press("confirm")
        yield from self.until(lambda: isinstance(self.scene, (FieldScene, Dialogue)) and not self.g.fade)
        yield from self.frames(10)
        yield from self.advance_dialogue({0: "intro_narration", 2: "intro_zed_portrait", 3: "intro_luke_portrait",
                                          4: "intro_iris_portrait"})
        yield from self.frames(20)
        self.shot("town_field")

        yield from self.talk("morgan", "npc_morgan")
        yield from self.talk("granny_bess", "npc_bess")
        yield from self.walk_to((11, 16))
        self.shot("town_walk_south")

        yield from self.press("cancel")
        yield from self.until(lambda: isinstance(self.scene, MenuScene), 60)
        yield from self.frames(10)
        self.shot("menu_status")
        yield from self.press("right")
        yield from self.press("down")
        yield from self.frames(5)
        self.shot("menu_skills")
        yield from self.press("cancel")

        yield from self.walk_to((11, 23), stop_on_scene_change=True)
        yield from self.until(lambda: self.field() and self.field().map.id == "sewer" and not self.g.fade, 300)
        yield from self.frames(30)
        self.shot("sewer_field")

        # --- 랜덤 전투: 레벨업이 일어나고 최소 3회 이길 때까지
        spots = [(6, 9), (13, 10), (6, 11), (12, 8)]
        wins = 0
        k = 0
        while (wins < 3 or not self.levelups) and wins < 14:
            yield from self.walk_to(spots[k % len(spots)])
            k += 1
            if isinstance(self.scene, BattleScene) or (self.g.fade and self.events["encounter"] > wins):
                first = self.events["battle_start"] == 0
                won = yield from self.fight(shoot=first)
                if self.events["defeat"]:
                    self.log.append("전멸 → 마을에서 재시작")
                    return
                wins += 1 if won else 0
                yield from self.until(lambda: not self.g.fade and isinstance(self.scene, (FieldScene, Dialogue)), 300)
        self.shot("sewer_after_battles")

        # --- 보스
        for c in self.g.state.party:          # 보스 전 정비 (여관 대신)
            c.full_heal()
        # 보스 트리거(x>=22)까지 전진. 가는 길의 랜덤 전투는 먼저 처리한다.
        for _ in range(60):
            if isinstance(self.scene, Dialogue):
                break
            if isinstance(self.scene, BattleScene) or (self.g.fade and not isinstance(self.scene, Dialogue)):
                if isinstance(self.scene, BattleScene) or self.g.fade:
                    yield from self.until(lambda: isinstance(self.scene, (BattleScene, FieldScene, Dialogue))
                                          and not self.g.fade, 300)
                if isinstance(self.scene, BattleScene):
                    yield from self.fight()
                    yield from self.until(lambda: not self.g.fade and isinstance(self.scene, (FieldScene, Dialogue)), 300)
                continue
            yield from self.walk_to((22, 3))
            yield
        assert isinstance(self.scene, Dialogue), "보스 대사가 시작되지 않음"
        self.log.append("보스 조우")
        yield from self.advance_dialogue({1: "boss_pre_dialogue"})
        won = yield from self.fight(shoot=True)
        self.log.append(f"보스전 결과: {'승리' if won else '패배'}")
        yield from self.until(lambda: isinstance(self.scene, (Dialogue, FieldScene)) and not self.g.fade, 300)
        yield from self.frames(5)
        if isinstance(self.scene, Dialogue) or self.field().pending_dialogue:
            yield from self.frames(5)
            yield from self.advance_dialogue({0: "boss_post_dialogue"})
        yield from self.frames(20)
        self.shot("ending_field")


def main():
    shots = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else os.path.join(ROOT, "saves", "autotest")
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 3
    random.seed(seed)
    os.makedirs(shots, exist_ok=True)
    pygame.mixer.pre_init(22050, -16, 1, 512)
    pygame.init()
    try:
        pygame.mixer.init(22050, -16, 1, 512)
    except pygame.error:
        pass
    game = Game(headless=True)
    game.push(TitleScene(game))
    pilot = Pilot(game, shots)
    script = pilot.script()
    t0 = time.time()
    error = None
    try:
        while game.running:
            game.input.begin_frame()
            pygame.event.pump()
            try:
                next(script)
            except StopIteration:
                break
            game.tick(DT)
            pilot.frame += 1
            if pilot.frame > 60 * 60 * 20:
                raise TimeoutError("20분(게임 시간) 초과")
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        error = e
        pilot.shot("error")

    st = game.state
    print("\n".join(pilot.log))
    print(f"\n게임 시간 {pilot.frame / 60:.0f}초 / 실제 {time.time() - t0:.0f}초, 오디오 {'켜짐' if game.audio.enabled else '꺼짐'}")
    if st:
        print("파티:", ", ".join(f"{c.name} Lv{c.level} HP{c.hp}/{c.max_hp}" for c in st.party))
    print("사용한 스킬:", dict(pilot.skills_used))
    checks = {
        "타이틀→필드 진입": pilot.events["map_enter"] >= 1,
        "대화창 열림(일러스트/NPC)": pilot.events["dialogue_open"] >= 3,
        "NPC 대화": pilot.events["talk"] >= 2,
        "맵 이동(마을→배수로)": any("'map': 'sewer'" in l for l in pilot.log),
        "랜덤 인카운트": pilot.events["encounter"] >= 1,
        "ATB 명령 입력": pilot.events["command_open"] >= 3,
        "스킬 사용(이펙트)": sum(pilot.skills_used.values()) >= 3,
        "전투 승리": pilot.events["victory"] >= 1,
        "레벨업": bool(pilot.levelups),
        "보스 격파": bool(st and "boss_rusted_claw_defeated" in st.flags),
        "오류 없음": error is None,
    }
    for k, v in checks.items():
        print(f"  [{'OK' if v else 'FAIL'}] {k}")
    print("레벨업 기록:", pilot.levelups)
    print(f"스크린샷 {len(pilot.shot_names)}장 → {shots}")
    pygame.quit()
    sys.exit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
