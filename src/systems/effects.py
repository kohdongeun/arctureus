"""스킬 이펙트, 파티클, 대미지 숫자.

각 이펙트는 draw(surf, glow) 에서 일반 레이어(surf)와 가산 합성 레이어(glow)에 그린다.
glow 레이어는 매 프레임 검게 지운 뒤 BLEND_RGB_ADD 로 화면에 얹는다.
"""
from __future__ import annotations

import math
import random

import pygame

from src import config as cfg
from src.ui import widgets as ui

C = cfg.C
rnd = random.Random(7)


def lerp(a, b, t):
    return a + (b - a) * t


def ease_out(t):
    return 1 - (1 - t) ** 3


class Effect:
    duration = 0.6

    def __init__(self, pos, target=None, color=None):
        self.pos = pygame.Vector2(pos)
        self.target = pygame.Vector2(target) if target is not None else None
        self.t = 0.0
        self.color = color

    @property
    def p(self):
        return min(1.0, self.t / self.duration)

    def update(self, dt):
        self.t += dt
        return self.t < self.duration

    def draw(self, surf, glow):
        pass


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max", "size", "color", "grav", "glow")

    def __init__(self, x, y, vx, vy, life, size, color, grav=0.0, glow=True):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max = life
        self.size, self.color, self.grav, self.glow = size, color, grav, glow


class Particles(Effect):
    def __init__(self, parts, duration=None):
        super().__init__((0, 0))
        self.parts = parts
        self.duration = duration or max((p.life for p in parts), default=0.1)

    def update(self, dt):
        self.t += dt
        for p in self.parts:
            p.life -= dt
            p.vy += p.grav * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
        return any(p.life > 0 for p in self.parts)

    def draw(self, surf, glow):
        for p in self.parts:
            if p.life <= 0:
                continue
            k = p.life / p.max
            r = max(1, int(p.size * (0.4 + 0.6 * k)))
            col = tuple(int(c * k) for c in p.color) if p.glow else p.color
            pygame.draw.circle(glow if p.glow else surf, col, (int(p.x), int(p.y)), r)


def burst(pos, n, color, speed=(80, 260), life=(0.3, 0.7), size=(3, 7), grav=0.0, up=0.0, glow=True, spread=math.tau):
    parts = []
    for _ in range(n):
        a = rnd.uniform(-spread / 2, spread / 2) - math.pi / 2 if spread < math.tau else rnd.uniform(0, math.tau)
        s = rnd.uniform(*speed)
        parts.append(Particle(pos[0], pos[1], math.cos(a) * s, math.sin(a) * s - up, rnd.uniform(*life),
                              rnd.uniform(*size), color, grav, glow))
    return Particles(parts)


# ------------------------------------------------------------------ 개별 이펙트
class Slash(Effect):
    duration = 0.32

    def __init__(self, pos, color=C["steam"], flip=False, n=1):
        super().__init__(pos)
        self.color, self.flip, self.n = color, flip, n

    def draw(self, surf, glow):
        for k in range(self.n):
            p = min(1, self.p * 1.6 - k * 0.25)
            if p <= 0:
                continue
            r = 70
            a0 = math.radians(200 if not self.flip else -20) + k * 0.5
            pts = []
            for i in range(12):
                a = a0 + (math.radians(140) * (i / 11)) * (1 if not self.flip else -1) * ease_out(p)
                pts.append((self.pos.x + math.cos(a) * r, self.pos.y + math.sin(a) * r * 0.7 - 30 + k * 14))
            fade = 1 - max(0, (self.p - 0.5) * 2)
            col = tuple(int(c * fade) for c in self.color)
            if len(pts) > 1:
                pygame.draw.lines(glow, col, False, pts, 9)
                pygame.draw.lines(glow, tuple(int(255 * fade) for _ in range(3)), False, pts, 3)


class Ring(Effect):
    def __init__(self, pos, color, r0=10, r1=110, width=6, duration=0.45, squash=0.55):
        super().__init__(pos)
        self.color, self.r0, self.r1, self.w, self.duration, self.squash = color, r0, r1, width, duration, squash

    def draw(self, surf, glow):
        r = lerp(self.r0, self.r1, ease_out(self.p))
        fade = 1 - self.p
        col = tuple(int(c * fade) for c in self.color)
        rect = pygame.Rect(0, 0, r * 2, r * 2 * self.squash)
        rect.center = (self.pos.x, self.pos.y)
        if rect.w > 2 and rect.h > 2:
            pygame.draw.ellipse(glow, col, rect, max(1, int(self.w * fade) + 1))


class Beam(Effect):
    duration = 0.22

    def __init__(self, a, b, color=C["brass_light"], width=5):
        super().__init__(a, b)
        self.color, self.width = color, width

    def draw(self, surf, glow):
        fade = 1 - self.p
        head = self.pos.lerp(self.target, min(1, self.p * 3))
        pygame.draw.line(glow, tuple(int(c * fade) for c in self.color), self.pos, head, self.width)
        pygame.draw.line(glow, (int(255 * fade),) * 3, self.pos, head, max(1, self.width // 3))


class Flash(Effect):
    duration = 0.18

    def __init__(self, color=(255, 255, 255), strength=120):
        super().__init__((0, 0))
        self.color, self.strength = color, strength

    def draw(self, surf, glow):
        a = int(self.strength * (1 - self.p))
        glow.fill(tuple(min(255, int(c * a / 255)) for c in self.color), special_flags=pygame.BLEND_RGB_ADD)


class ClockStop(Effect):
    duration = 0.9

    def draw(self, surf, glow):
        fade = 1 - max(0, (self.p - 0.6) / 0.4)
        r = 60
        col = tuple(int(c * fade) for c in C["ether"])
        pygame.draw.circle(glow, col, self.pos, r, 4)
        for k in range(12):
            a = k * math.pi / 6
            pygame.draw.circle(glow, col, (self.pos.x + math.cos(a) * (r + 10), self.pos.y + math.sin(a) * (r + 10)), 4)
        ang = -math.pi / 2 + self.p * math.tau * 1.5
        pygame.draw.line(glow, col, self.pos, (self.pos.x + math.cos(ang) * r * 0.85, self.pos.y + math.sin(ang) * r * 0.85), 4)
        pygame.draw.line(glow, col, self.pos, (self.pos.x + math.cos(ang / 12) * r * 0.5, self.pos.y + math.sin(ang / 12) * r * 0.5), 6)


class Pillar(Effect):
    """레벨업/버프용 빛 기둥"""
    duration = 0.9

    def __init__(self, pos, color=C["brass_light"], width=70, height=260):
        super().__init__(pos)
        self.color, self.width, self.height = color, width, height

    def draw(self, surf, glow):
        k = math.sin(self.p * math.pi)
        w = int(self.width * k)
        if w < 2:
            return
        for i in range(6):
            ww = int(w * (1 - i / 6))
            col = tuple(int(c * k * 0.22) for c in self.color)
            pygame.draw.rect(glow, col, (self.pos.x - ww // 2, self.pos.y - self.height, ww, self.height))


class FloatText(Effect):
    duration = 0.95

    def __init__(self, pos, s, color=C["white"], size=30, rise=60, bounce=True):
        super().__init__(pos)
        self.s, self.color, self.size, self.rise, self.bounce = s, color, size, rise, bounce

    def draw(self, surf, glow):
        if self.bounce:
            y = self.pos.y - abs(math.sin(min(self.p * 2.2, 1) * math.pi)) * 34 - self.p * 10
        else:
            y = self.pos.y - ease_out(self.p) * self.rise
        if self.p > 0.8:
            alpha_skip = int((self.p - 0.8) * 50) % 2
            if alpha_skip:
                return
        ui.text(surf, self.s, (self.pos.x, y), self.size, self.color, bold=True, anchor="center", outline=True)


# ------------------------------------------------------------------ 스킬 이름 → 이펙트 묶음
def make(fx: str, src, dst, big=False):
    """src: 시전자 화면 위치, dst: 대상 화면 위치(가운데). 이펙트 리스트를 돌려준다."""
    sx, sy = src
    x, y = dst
    s = 1.6 if big else 1.0
    out = []
    if fx in ("slash", "claw"):
        col = C["steam"] if fx == "slash" else (255, 110, 90)
        out += [Slash((x, y), col, n=1 if fx == "slash" else 3), burst((x, y), 14, col, size=(2, 5))]
    elif fx == "piston":
        out += [Ring((x, y + 30), C["brass_light"], 10, 120 * s, 10), Flash((255, 200, 120), 90),
                burst((x, y), 28, C["brass_light"], (120, 360), grav=500, size=(2, 6)),
                burst((x, y), 16, C["steam"], (40, 120), life=(0.5, 0.9), size=(8, 14), up=60, glow=False)]
    elif fx == "steam":
        out += [burst((x, y + 20), 40, (200, 200, 205), (60, 200), (0.6, 1.1), (10, 22), up=40, glow=False),
                burst((x, y), 20, (255, 140, 70), (100, 240), size=(2, 5)), Ring((x, y + 30), (255, 150, 90), 10, 150, 6)]
    elif fx == "wrench":
        out += [Slash((x, y), C["brass_light"], flip=True), burst((x, y), 20, C["ether"], (100, 260), size=(2, 4)),
                FloatText((x, y - 90), "오작동!", C["ether"], 22, bounce=False)]
    elif fx in ("charge", "ultimate"):
        out += [Flash((255, 160, 80), 170), Ring((x, y), (255, 170, 90), 20, 260, 14, 0.6),
                burst((x, y), 70, (255, 180, 100), (150, 500), size=(3, 8), grav=200),
                Slash((x, y), (255, 220, 160), n=3)]
    elif fx == "wave_small":
        out += [Ring((x, y), C["ether"], 10, 80, 5, 0.4), burst((x, y), 10, C["ether"], size=(2, 4))]
    elif fx == "wave":
        out += [Ring((x, y), C["ether"], 10 + i * 6, 140, 6, 0.55 + i * 0.12) for i in range(3)]
        out += [Beam((sx, sy - 40), (x, y), C["ether"], 8), burst((x, y), 24, C["ether"], (80, 260), size=(2, 5))]
    elif fx == "shot":
        out += [Beam((sx - 20, sy - 8), (x, y), C["brass_light"], 6), Flash((255, 230, 180), 60),
                burst((x, y), 16, (255, 220, 140), (120, 340), size=(2, 4))]
    elif fx == "pellets":
        for i in range(5):
            tx, ty = x + rnd.uniform(-60, 60), y + rnd.uniform(-40, 40)
            out += [Beam((sx - 20, sy - 8), (tx, ty), (255, 200, 120), 3), burst((tx, ty), 6, (255, 210, 140), size=(2, 3))]
    elif fx == "hawk":
        out += [Beam((sx, sy - 80), (x, y - 20), C["brass_light"], 10), Slash((x, y), C["brass_light"], n=2),
                burst((x, y), 18, C["brass"], (80, 220), grav=300, size=(2, 5))]
    elif fx == "rust":
        out += [burst((x, y), 34, (200, 110, 50), (80, 280), (0.4, 0.8), (3, 7), grav=600, up=120, glow=False),
                burst((x, y), 12, (255, 140, 60), size=(3, 6))]
    elif fx == "heal":
        out += [Pillar((x, y + 40), (120, 255, 200), 90, 200), Ring((x, y + 40), (120, 255, 200), 10, 90, 5, 0.6),
                burst((x, y + 20), 26, (150, 255, 220), (30, 90), (0.6, 1.0), (2, 5), up=120)]
    elif fx == "stop":
        out += [ClockStop((x, y)), Ring((x, y), C["ether"], 10, 120, 4, 0.8)]
    elif fx == "buff":
        out += [Pillar((x, y + 40), C["brass_light"], 80, 220), Ring((x, y + 40), C["brass_light"], 60, 10, 6, 0.5),
                burst((x, y + 30), 18, C["brass_light"], (20, 60), (0.6, 1.0), (2, 4), up=140)]
    elif fx == "levelup":
        out += [Pillar((x, y + 40), (255, 230, 140), 100, 320), Ring((x, y + 40), (255, 230, 140), 10, 140, 8, 0.7),
                burst((x, y), 40, (255, 230, 150), (40, 160), (0.7, 1.2), (2, 5), up=180)]
    return out
