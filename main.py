"""황동의 심장 : 아스카론 연대기 — 실행 진입점 (3D 쿼터뷰, ursina).

    python main.py                 # 게임 실행 (타이틀 화면부터)
    python main.py --shots DIR     # 타이틀부터 보스전·세이브/로드까지 자동 진행하며 스크린샷 + 점검 (테스트용)
    python main.py --smoke         # 타이틀 → 새 게임 → 필드 진입을 확인하고 종료 코드로 알림 (빌드 검증용)
    python main2d.py               # 이전 2D(pygame) 버전
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

for _s in (sys.stdout, sys.stderr):
    if _s is not None and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


def autoplay(game, out_dir):
    """실제 게임 루프를 돌리면서 정해진 순서로 조작하고 스크린샷을 남긴다.

    타이틀 → 새 게임 → 인트로 대화 → NPC 대화 → 전투 → 메뉴(상태·아이템·저장) → 맵 이동 →
    스토리 이벤트(제단 의식 → 보스전) → 타이틀로 → 이어하기(불러오기) 순서.
    """
    from panda3d.core import Filename
    from ursina import Entity, application
    base = game.app
    os.makedirs(out_dir, exist_ok=True)
    log, checks = [], []
    n = {"shot": 0, "f": 0}

    def shot(name):
        path = os.path.join(out_dir, f"{n['shot']:02d}_{name}.png")
        base.graphicsEngine.renderFrame()
        base.win.saveScreenshot(Filename.fromOsSpecific(path))
        n["shot"] += 1
        log.append(path)

    def check(name, ok):
        checks.append((name, bool(ok)))
        print(f"  [{'OK' if ok else 'FAIL'}] {name}", flush=True)

    def key(k, wait=6):
        game.input(k)
        return wait

    def finish_dialogue(shot_name=None, every=10):
        d = game.dialogue
        k = 0
        while d.active:
            d.shown = len(d.lines[d.i]["text"])
            if shot_name and k == 1:
                yield 4
                shot(shot_name)
            d.advance()
            k += 1
            yield every

    def walk(points, stop=1.2, limit=1500):
        for tx, tz in points:
            last, stuck = None, 0
            for _ in range(limit):
                if game.fade or game.mode != "field" or game.battle or game.dialogue.active or game.event:
                    game.input_override = None
                    return
                p = game.player
                dx, dz = tx - p.x, tz - p.z
                dd = math.hypot(dx, dz)
                if dd < stop:
                    break
                game.input_override = (dx / dd, dz / dd)
                stuck = stuck + 1 if last and math.hypot(p.x - last[0], p.z - last[1]) < 0.01 else 0
                last = (p.x, p.z)
                if stuck > 40:                 # 나무에 걸리면 조금 옆으로 비켜 간다 (테스트 편의)
                    p.x, p.z = p.x + dz / dd * 0.6, p.z - dx / dd * 0.6
                    stuck = 0
                yield 1
        game.input_override = None

    def fight(tag, shots=True):
        """명령: 첫 턴은 스킬, 그 뒤로 공격. 결과 창까지 진행"""
        used_skill = False
        fx_shot = False
        seen = 0
        while game.battle is not None:
            b = game.battle
            seen += 1
            if seen > 30000:
                print("전투가 끝나지 않음")
                application.quit()
                return
            if b.ui_state == "command":
                if not used_skill:
                    used_skill = True
                    yield key("down arrow", 4)
                    yield key("z", 10)
                    if shots:
                        shot(f"{tag}_skill_menu")
                    usable = [i for i, (_, _, ok) in enumerate(b.sub) if ok]
                    for _ in range(usable[-1] if usable else 0):
                        yield key("down arrow", 4)
                    yield key("z", 6)
                    yield key("z", 6)
                else:
                    yield key("z", 4)
                    yield key("z", 4)
            elif b.ui_state == "sub":
                yield key("z", 4)
            elif b.ui_state == "target":
                yield key("z", 4)
            elif b.ui_state == "idle" and b.fx.items and not fx_shot and shots:
                fx_shot = True
                yield 6
                shot(f"{tag}_effect")
            elif b.ui_state == "result":
                yield 50
                shot(f"{tag}_result")
                yield key("z", 30)
            else:
                yield 1

    def story(tag=None, limit=60000):
        """이벤트가 끝날 때까지: 대사는 넘기고, 전투는 싸우고, 맵 이동은 기다린다"""
        shot_done = False
        for _ in range(limit):
            d = game.dialogue
            if game.battle is not None:
                yield from fight(tag or "event", shots=False)
                continue
            if d.active:
                d.shown = len(d.lines[d.i]["text"])
                yield 3
                if tag and not shot_done:
                    shot(tag)
                    shot_done = True
                d.advance()
                yield 3
                continue
            if game.event is None and game.fade is None and game.battle is None:
                return
            yield 1

    def script():
        from src.entities.party import exp_to_next
        from src.systems import save
        # ---- 타이틀
        yield 200
        shot("title")
        check("타이틀 화면", game.mode == "title" and game.title.active)
        yield key("z", 20)                          # PRESS ANY KEY
        shot("title_menu")
        yield key("z", 10)                          # 새 게임
        while game.fade or game.mode != "field":
            yield 1
        game.encounters_enabled = False             # 자동 진행 중 무작위 전투가 끼어들지 않게
        yield 30
        # ---- 굴뚝거리: 오프닝 (루크 혼자)
        yield from story("op_intro")
        check("오프닝·목표 표시", "scene:op_01" in game.state.flags and game.state.objective
              and "모르간" in game.state.objective["text"] and game.state.members == ["luke"])
        shot("town_objective")
        yield from walk([(-1, 6), (0, 11.4)], 0.5)
        game.try_talk()
        yield from story("morgan")
        check("모르간 의뢰", "event:op_morgan" in game.state.flags and game.state.items.get("item_steam_tonic", 0) >= 8)
        yield from walk([(0, 4), (0, -5)], 0.6)
        yield from story("iris_meet")
        check("아이리스 합류", "iris" in game.state.members)
        yield from walk([(0, -15.5)], 0.6)
        yield from story("dock")
        while game.fade or game.world.m["id"] != "verdan_edge":
            yield 1
        yield 20
        yield from story("forest_intro")
        check("제드 합류·숲 도착", game.state.members == ["luke", "iris", "zed"] and game.world.m["id"] == "verdan_edge")
        shot("forest_party")
        # ---- 숲: 튜토리얼 전투
        yield from walk([(-17, 2.5)], 0.6)
        yield from story("tutorial")
        check("튜토리얼 전투", game.state.battles_won >= 2 and "scene:fo_03" in game.state.flags)
        # ---- 메뉴
        game.state.party[0].hp = max(1, game.state.party[0].hp - 120)
        yield key("x", 20)
        shot("menu_main")
        check("메뉴 열림", game.menu.active)
        yield key("z", 12)                          # 상태
        shot("menu_status")
        yield key("x", 8)
        yield key("down arrow", 6)
        yield key("z", 10)                          # 장비
        shot("menu_equip")
        yield key("x", 8)
        yield key("down arrow", 6)
        yield key("z", 10)                          # 아이템
        hp0 = game.state.party[0].hp
        yield key("z", 10)
        yield key("z", 12)                          # 루크에게
        check("아이템 사용(HP 회복)", game.state.party[0].hp > hp0)
        yield key("x", 8)
        yield key("x", 8)
        yield key("down arrow", 6)
        yield key("z", 10)                          # 저장
        yield key("z", 12)                          # 슬롯 1
        d = save.read(0)
        check("슬롯 1 저장", d is not None and d["map_id"] == "verdan_edge" and d.get("members") == ["luke", "iris", "zed"])
        saved_pos = tuple(d["pos"]) if d else None
        saved_lv = game.state.party[0].level
        yield key("x", 8)
        yield key("x", 12)
        check("메뉴 닫힘", not game.menu.active)
        # ---- 엘윈 → 북쪽 출구
        yield from walk([(-10, 0), (-4, -1.6)], 0.5)
        game.try_talk()
        yield from story("elwin")
        check("엘윈 이벤트·다음 목표", "event:meet_elwin" in game.state.flags and "고목" in game.state.objective["text"])
        yield from walk([(-2, -4), (2, 6), (8, 16), (8.5, 21.5)], 1.0)
        yield from story("rumble")
        yield from walk([(10, 27), (9, 31.5)], 1.0)
        while game.fade or game.world.m["id"] != "elder_cradle":
            yield 1
        yield 30
        yield from story("cradle")
        check("맵 이동(고목의 요람)", game.world.m["id"] == "elder_cradle" and "scene:cr_01" in game.state.flags)
        yield 20
        shot("cradle_objective")
        # ---- 제단 → 보스
        for c in game.state.party:                  # 보스전을 확실히 넘기려고 레벨을 올려 둔다 (테스트 편의)
            while c.level < 9:
                c.gain_exp(exp_to_next(c.level))
            c.full_heal()
        gold0 = game.state.gold
        yield from walk([(0, -8), (-8, -5), (-15, -3)], 1.0)
        yield 10
        check("제단 이벤트 시작", game.event is not None)
        yield from story("ritual")
        check("보스 처치·제1부 완료", "ch3_clear" in game.state.flags and game.state.gold >= gold0 + 1000)
        yield 60
        shot("part1_clear")
        # ---- 타이틀로 → 이어하기
        yield key("x", 10)
        for _ in range(5):                          # 타이틀로
            yield key("down arrow", 4)
        yield key("z", 8)
        yield key("left arrow", 4)                  # 확인 창: '예'
        yield key("z", 8)
        while game.fade or game.mode != "title":
            yield 1
        yield 60
        yield key("z", 20)                          # PRESS ANY KEY
        shot("title_continue")
        check("타이틀 복귀·이어하기 커서", game.title.cur == 1)
        yield key("z", 10)
        yield key("z", 10)
        while game.fade or game.mode != "field":
            yield 1
        yield 40
        shot("loaded")
        p = game.player
        check("불러오기(맵·위치·동료)", game.world.m["id"] == "verdan_edge" and saved_pos is not None
              and math.hypot(p.x - saved_pos[0], p.z - saved_pos[1]) < 0.6 and game.state.party[0].level == saved_lv
              and len(game.followers) == 2 and "ch3_clear" not in game.state.flags)
        st = game.state
        print("\n".join(log))
        print("파티:", ", ".join(f"{c.name} Lv{c.level} HP{c.hp}/{c.max_hp}" for c in st.party), "| 승리", st.battles_won)
        print("BGM 전환:", " → ".join(getattr(game, "log_bgm", [])))
        bad = [c for c, ok in checks if not ok]
        print(f"autoplay {'OK' if not bad else 'FAIL ' + ', '.join(bad)} ({n['f']} frames, {len(checks)} checks)")
        application.quit()

    gen = script()
    wait = {"n": 0}

    def tick():
        n["f"] += 1
        if wait["n"] > 0:
            wait["n"] -= 1
            return
        try:
            wait["n"] = (next(gen) or 1) - 1
        except StopIteration:
            pass

    Entity(update=tick)


def smoke(game):
    """빌드 검증: 타이틀이 뜨고, 새 게임으로 필드(지형·파티·NPC)에 들어가는지 확인"""
    from ursina import Entity
    cnt = {"f": 0, "title": False}

    def tick():
        cnt["f"] += 1
        if cnt["f"] == 60:
            cnt["title"] = game.mode == "title" and game.title.active and game.world is not None
            game.new_game()
        if cnt["f"] == 300:
            ok = (cnt["title"] and game.mode == "field" and game.player is not None and len(game.npcs) > 0
                  and game.world.ground is not None)
            from src3d.shaders import GLSL
            print(f"smoke: {'OK' if ok else 'FAIL'} (title={cnt['title']}, mode={game.mode}, "
                  f"map={game.world.m['id'] if game.world else None}, npcs={len(game.npcs)}, "
                  f"glsl={GLSL['ok']}, renderer={GLSL['renderer']})", flush=True)
            os._exit(0 if ok else 1)
    Entity(update=tick)


def log_crash():
    """창 모드 실행 파일은 오류가 보이지 않으므로 실행 파일 옆(실패 시 홈 폴더)에 기록"""
    import traceback
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    for d in (base, os.path.expanduser("~")):
        try:
            path = os.path.join(d, "Arcturus_RPG_error.log")
            with open(path, "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
            return path
        except OSError:
            continue
    return None


def frozen_setup():
    """PyInstaller 로 묶인 실행 파일: Panda3D 가 렌더러·오디오 플러그인을 풀린 폴더에서 찾도록"""
    gl = os.environ.get("ARCTURUS_PRELOAD_GL")
    if gl and sys.platform.startswith("win"):
        # 테스트용: GPU 없는 빌드 서버에서 Mesa 소프트웨어 OpenGL(opengl32.dll)을 먼저 올려 두면
        # 이후 Panda3D 가 이름으로 불러올 때 이 DLL 이 쓰인다
        import ctypes
        ctypes.WinDLL(gl)
    if not getattr(sys, "frozen", False):
        return
    from panda3d.core import loadPrcFileData
    pdir = os.path.join(sys._MEIPASS, "panda3d")
    loadPrcFileData("", f"plugin-path {pdir}\nmodel-path {sys._MEIPASS}\nmodel-cache-dir\n")


def main():
    try:
        frozen_setup()
        from src3d.game import Game
        size = (1280, 720)
        if "--shots" in sys.argv:                   # 테스트는 빈 세이브 폴더에서
            import tempfile
            os.environ.setdefault("ARCTURUS_SAVE_DIR", tempfile.mkdtemp(prefix="arcturus_saves_"))
        game = Game(size=size, start="title")
        if "--shots" in sys.argv:
            autoplay(game, sys.argv[sys.argv.index("--shots") + 1])
        elif "--smoke" in sys.argv:
            smoke(game)
        game.run()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        import traceback
        path = log_crash()
        traceback.print_exc()
        sys.exit(f"오류가 발생했습니다. 기록: {path}")


if __name__ == "__main__":
    main()
