"""황동의 심장 — 3D 쿼터뷰 버전 (ursina) 진입점.

    python main3d.py                 # 실행
    python main3d.py --shots DIR     # 자동 진행하며 스크린샷 저장 후 종료 (테스트용)
    python main3d.py --smoke         # 몇 초 실행 후 정상 여부를 종료 코드로 알림
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
    """실제 게임 루프를 돌리면서 정해진 순서로 조작하고 스크린샷을 남긴다"""
    from panda3d.core import Filename
    from ursina import Entity, application
    base = game.app

    os.makedirs(out_dir, exist_ok=True)
    state = {"f": 0, "step": 0, "wait": 0, "n": 0}
    log = []

    def shot(name):
        path = os.path.join(out_dir, f"{state['n']:02d}_{name}.png")
        base.graphicsEngine.renderFrame()
        base.win.saveScreenshot(Filename.fromOsSpecific(path))
        state["n"] += 1
        log.append(path)

    def walk_to(tx, tz, stop=2.0):
        p = game.player
        dx, dz = tx - p.x, tz - p.z
        d = math.hypot(dx, dz)
        if d < stop:
            game.input_override = None
            return True
        game.input_override = (dx / d, dz / d)
        return False

    npc = {n.data["id"]: n for n in game.npcs}

    def tick():
        state["f"] += 1
        if state["wait"] > 0:
            state["wait"] -= 1
            return
        s = state["step"]
        d = game.dialogue
        if s == 0:                                  # 인트로 대화
            state["wait"], state["step"] = 40, 1
        elif s == 1:
            shot("intro_dialogue")
            state["step"] = 2
        elif s == 2:
            if d.active:
                d.shown = len(d.lines[d.i]["text"])
                if d.i == 1 and not getattr(d, "_shot1", False):
                    d._shot1 = True
                    shot("intro_zed")
                d.advance()
                state["wait"] = 12
            else:
                state["step"], state["wait"] = 3, 30
        elif s == 3:
            shot("field_start")
            state["step"] = 4
        elif s == 4:                                # 엘윈에게 걸어감
            if state["f"] % 90 == 0:
                shot("walking")
            if walk_to(npc["elwin"].x, npc["elwin"].z, 2.0):
                state["step"], state["wait"] = 5, 20
        elif s == 5:
            shot("near_npc_bubble")
            game.try_talk()
            state["step"], state["wait"] = 6, 50
        elif s == 6:
            d.shown = len(d.lines[d.i]["text"])
            state["wait"], state["step"] = 6, 7
        elif s == 7:
            shot("npc_dialogue")
            d.advance()
            state["step"], state["wait"] = 8, 20
        elif s == 8:                                # 시점 회전
            game.yaw_goal += 90
            state["step"], state["wait"] = 9, 70
        elif s == 9:
            shot("camera_rotated")
            game.yaw_goal -= 90
            state["step"], state["wait"] = 10, 40
        elif s == 10:                               # 로봇에게
            if walk_to(npc["abandoned_robot"].x, npc["abandoned_robot"].z, 2.2):
                state["step"], state["wait"] = 11, 20
            elif state["f"] > 6000:
                state["step"] = 11
        elif s == 11:
            game.try_talk()
            state["step"], state["wait"] = 12, 50
        elif s == 12:
            d.shown = len(d.lines[d.i]["text"]) if d.active else 0
            state["wait"], state["step"] = 6, 13
        elif s == 13:
            shot("robot_dialogue")
            print("\n".join(log))
            print(f"autoplay OK ({state['f']} frames)")
            application.quit()

    Entity(update=tick)


def main():
    from src3d.game import Game
    size = (1280, 720)
    game = Game(size=size)
    if "--shots" in sys.argv:
        autoplay(game, sys.argv[sys.argv.index("--shots") + 1])
    elif "--smoke" in sys.argv:
        from ursina import Entity, application
        cnt = {"f": 0}

        def tick():
            cnt["f"] += 1
            if cnt["f"] == 120:
                ok = game.world.ground is not None and len(game.npcs) > 0
                print(f"smoke3d: {'OK' if ok else 'FAIL'}")
                application.quit()
        Entity(update=tick)
    game.run()


if __name__ == "__main__":
    main()
