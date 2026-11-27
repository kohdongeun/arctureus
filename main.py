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

    def script():
        # ---- 타이틀
        yield 90
        shot("title")
        check("타이틀 화면", game.mode == "title" and game.title.active)
        yield key("z", 10)                          # 새 게임 (세이브 없음 → 커서가 '새 게임')
        while game.fade or game.mode != "field":
            yield 1
        game.encounters_enabled = False             # 자동 진행 중 무작위 전투가 끼어들지 않게
        yield 40
        shot("intro_dialogue")
        yield from finish_dialogue("intro_2", 10)
        yield 30
        shot("field_start")
        npc = {a.data["id"]: a for a in game.npcs}
        # ---- 엘윈: 첫 대화는 스토리 장면 ch3_02
        yield from walk([(npc["elwin"].x, npc["elwin"].z)], 2.0)
        yield 10
        shot("near_npc_bubble")
        game.try_talk()
        yield 40
        shot("elwin_event")
        yield from finish_dialogue(None, 6)
        check("엘윈 이벤트(ch3_02)", "scene:ch3_02" in game.state.flags)
        yield 20
        # ---- 전투 (레벨업 확인용으로 경험치를 직전까지)
        from src.entities.party import exp_to_next
        for c in game.state.party:
            c.exp = exp_to_next(c.level) - 5
        game.start_battle(["hollow", "rust_crawler"])
        yield 70
        shot("battle_start")
        yield from fight("battle")
        while game.battle:
            yield 1
        yield 40
        check("전투 승리·레벨업", game.state.battles_won == 1 and game.state.party[0].level == 4)
        # ---- 메뉴
        game.state.party[0].hp -= 120
        yield key("x", 20)
        shot("menu_main")
        check("메뉴 열림", game.menu.active)
        yield key("z", 12)                          # 상태
        shot("menu_status")
        yield key("right arrow", 12)
        shot("menu_status_iris")
        yield key("x", 8)
        yield key("down arrow", 6)
        yield key("z", 10)                          # 아이템
        shot("menu_items")
        hp0 = game.state.party[0].hp
        yield key("z", 10)                          # 증기 강장제 → 대상 선택
        shot("menu_item_target")
        yield key("z", 12)                          # 루크에게
        check("아이템 사용(HP 회복)", game.state.party[0].hp > hp0)
        shot("menu_item_used")
        yield key("x", 8)
        yield key("x", 8)
        yield key("down arrow", 6)
        yield key("z", 10)                          # 저장
        yield key("z", 12)                          # 슬롯 1
        shot("menu_saved")
        from src.systems import save
        d = save.read(0)
        check("슬롯 1 저장", d is not None and d["map_id"] == "verdan_edge")
        saved_pos = tuple(d["pos"]) if d else None
        yield key("x", 8)
        yield key("x", 12)
        check("메뉴 닫힘", not game.menu.active)
        # ---- 북쪽 출구 → 고목의 요람
        yield from walk([(2, 6), (8, 16), (10, 27), (9, 31.5)], 1.0, 2500)
        while game.fade or game.world.m["id"] != "elder_cradle":
            yield 1
        yield 50
        shot("map_elder_cradle")
        check("맵 이동(고목의 요람)", game.world.m["id"] == "elder_cradle")
        yield from finish_dialogue("silvaen_scene", 6)
        yield 30
        shot("elder_tree")
        # ---- 공명의 제단 → 의식 → 보스전
        for c in game.state.party:                  # 보스전을 확실히 넘기려고 레벨을 올려 둔다 (테스트 편의)
            while c.level < 9:
                c.gain_exp(exp_to_next(c.level))
            c.full_heal()
        yield from walk([(0, -8), (-8, -5), (-15, -3)], 1.0, 2500)
        yield 30
        check("제단 이벤트 시작", game.event is not None)
        yield from finish_dialogue("ritual_scene", 6)       # ch3_04
        yield 10
        yield from finish_dialogue("boss_pre", 6)            # ch3_05
        while game.battle is None:
            yield 1
        yield 80
        shot("boss_start")
        yield from fight("boss")
        while game.battle:
            yield 1
        yield 30
        yield from finish_dialogue("boss_post", 6)           # ch3_06
        yield 40
        shot("chapter_clear")
        check("보스 처치·제3장 완료", "ch3_clear" in game.state.flags and "event:ritual" in game.state.flags)
        # ---- 타이틀로 → 이어하기
        yield key("x", 10)
        for _ in range(4):
            yield key("down arrow", 4)
        yield key("z", 8)
        yield key("left arrow", 4)                  # 확인 창: '예'
        yield key("z", 8)
        while game.fade or game.mode != "title":
            yield 1
        yield 60
        shot("title_continue")
        check("타이틀 복귀·이어하기 커서", game.title.cur == 1)
        yield key("z", 10)
        shot("title_slots")
        yield key("z", 10)
        while game.fade or game.mode != "field":
            yield 1
        yield 40
        shot("loaded")
        p = game.player
        check("불러오기(맵·위치·레벨)", game.world.m["id"] == "verdan_edge" and saved_pos is not None
              and math.hypot(p.x - saved_pos[0], p.z - saved_pos[1]) < 0.1 and game.state.party[0].level == 4
              and "ch3_clear" not in game.state.flags)
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
