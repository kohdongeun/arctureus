"""텍스트, 창(9-slice), 게이지, 커서, 목록 메뉴."""
from __future__ import annotations

import math

import pygame

from src import config as cfg
from src.engine import assets

C = cfg.C


def text(surf, s, pos, size=22, color=C["white"], bold=False, shadow=True, anchor="topleft", outline=False):
    f = assets.font(size, bold)
    img = f.render(str(s), False, color)
    rect = img.get_rect(**{anchor: pos})
    if outline:
        o = f.render(str(s), False, C["black"])
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
            surf.blit(o, rect.move(dx, dy))
    elif shadow:
        sh = f.render(str(s), False, (0, 0, 0) if color != C["ink"] else (200, 180, 140))
        surf.blit(sh, rect.move(2, 2))
    surf.blit(img, rect)
    return rect


def wrap(s, width, size=22, bold=False):
    """한글은 어절 단위로 줄바꿈하되 너무 긴 어절은 글자 단위로 자른다."""
    f = assets.font(size, bold)
    lines = []
    for para in str(s).split("\n"):
        cur = ""
        for word in para.split(" "):
            cand = (cur + " " + word) if cur else word
            if f.size(cand)[0] <= width:
                cur = cand
                continue
            if cur:
                lines.append(cur)
            cur = ""
            for ch in word:
                if f.size(cur + ch)[0] > width:
                    lines.append(cur)
                    cur = ch
                else:
                    cur += ch
        lines.append(cur)
    return lines


class NineSlice:
    def __init__(self, rel, border_src, scale=1.0):
        img = assets.image(rel)
        if scale != 1.0:
            img = pygame.transform.smoothscale(img, (int(img.get_width() * scale), int(img.get_height() * scale)))
        self.img = img
        self.b = int(border_src * scale)

    def draw(self, surf, rect):
        rect = pygame.Rect(rect)
        b, img = self.b, self.img
        w, h = img.get_size()
        b = min(b, rect.w // 2, rect.h // 2)
        src = {
            "tl": (0, 0, self.b, self.b), "tr": (w - self.b, 0, self.b, self.b),
            "bl": (0, h - self.b, self.b, self.b), "br": (w - self.b, h - self.b, self.b, self.b),
            "t": (self.b, 0, w - 2 * self.b, self.b), "b": (self.b, h - self.b, w - 2 * self.b, self.b),
            "l": (0, self.b, self.b, h - 2 * self.b), "r": (w - self.b, self.b, self.b, h - 2 * self.b),
            "c": (self.b, self.b, w - 2 * self.b, h - 2 * self.b),
        }
        dst = {
            "tl": (rect.x, rect.y, b, b), "tr": (rect.right - b, rect.y, b, b),
            "bl": (rect.x, rect.bottom - b, b, b), "br": (rect.right - b, rect.bottom - b, b, b),
            "t": (rect.x + b, rect.y, rect.w - 2 * b, b), "b": (rect.x + b, rect.bottom - b, rect.w - 2 * b, b),
            "l": (rect.x, rect.y + b, b, rect.h - 2 * b), "r": (rect.right - b, rect.y + b, b, rect.h - 2 * b),
            "c": (rect.x + b, rect.y + b, rect.w - 2 * b, rect.h - 2 * b),
        }
        for k in ("c", "t", "b", "l", "r", "tl", "tr", "bl", "br"):
            d = pygame.Rect(dst[k])
            if d.w <= 0 or d.h <= 0:
                continue
            piece = img.subsurface(pygame.Rect(src[k]))
            if piece.get_size() != d.size:
                piece = pygame.transform.scale(piece, d.size)
            surf.blit(piece, d)


_parchment = None


def parchment_window(surf, rect):
    """2단계 UI 일러스트(황동 테두리 + 양피지)를 9-slice 로 사용"""
    global _parchment
    if _parchment is None:
        _parchment = NineSlice("ui/ui_window_menu.png", border_src=84, scale=0.5)
    _parchment.draw(surf, rect)


def brass_window(surf, rect, alpha=225):
    """어두운 유리판 + 황동 테두리 (전투 HUD 용)"""
    rect = pygame.Rect(rect)
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(panel, (*C["navy"], alpha), panel.get_rect(), border_radius=10)
    for y in range(0, rect.h, 4):   # 은은한 스캔라인
        pygame.draw.line(panel, (255, 255, 255, 8), (8, y), (rect.w - 8, y))
    surf.blit(panel, rect)
    pygame.draw.rect(surf, C["brass"], rect, 4, border_radius=10)
    pygame.draw.rect(surf, C["brass_light"], rect.inflate(-8, -8), 1, border_radius=8)
    for (x, y) in (rect.topleft, rect.topright, rect.bottomleft, rect.bottomright):
        pygame.draw.circle(surf, C["brass_light"], (x + (6 if x == rect.x else -6), y + (6 if y == rect.y else -6)), 4)


def gauge(surf, rect, ratio, color, back=(30, 26, 30), border=C["brass"], glow=False):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surf, back, rect, border_radius=3)
    fill = rect.inflate(-4, -4)
    fill.w = max(0, int(fill.w * max(0.0, min(1.0, ratio))))
    if fill.w:
        pygame.draw.rect(surf, color, fill, border_radius=2)
        hi = fill.copy()
        hi.h = max(1, fill.h // 3)
        pygame.draw.rect(surf, tuple(min(255, c + 60) for c in color), hi, border_radius=2)
    pygame.draw.rect(surf, border, rect, 2, border_radius=3)
    if glow and ratio >= 1:
        pygame.draw.rect(surf, C["white"], rect.inflate(4, 4), 2, border_radius=4)


def gear_cursor(surf, pos, t, color=C["brass_light"], r=9):
    """회전하는 톱니 커서 (art_direction.ui_style.cursor)"""
    x, y = pos
    for k in range(8):
        a = t * 4 + k * math.pi / 4
        pygame.draw.circle(surf, color, (int(x + math.cos(a) * r), int(y + math.sin(a) * r)), 3)
    pygame.draw.circle(surf, color, (int(x), int(y)), r - 2)
    pygame.draw.circle(surf, C["ether"], (int(x), int(y)), 3)


class ListMenu:
    """세로 목록 메뉴. items: [(label, enabled, extra_text)]"""

    def __init__(self, items, rows=6):
        self.items = items
        self.index = 0
        self.rows = rows
        self.scroll = 0

    def move(self, d, audio=None):
        if not self.items:
            return
        self.index = (self.index + d) % len(self.items)
        if self.index < self.scroll:
            self.scroll = self.index
        if self.index >= self.scroll + self.rows:
            self.scroll = self.index - self.rows + 1
        if audio:
            audio.sfx("sfx_cursor")

    def draw(self, surf, x, y, w, t, size=22, line=34, ink=C["white"], dim=C["gray"]):
        for i in range(self.scroll, min(len(self.items), self.scroll + self.rows)):
            label, enabled, extra = self.items[i]
            yy = y + (i - self.scroll) * line
            col = ink if enabled else dim
            text(surf, label, (x + 28, yy), size, col, shadow=(ink != C["ink"]))
            if extra:
                text(surf, extra, (x + w, yy), size - 2, col, anchor="topright", shadow=(ink != C["ink"]))
            if i == self.index:
                gear_cursor(surf, (x + 10, yy + size // 2 + 1), t)
