"""이미지·폰트·사운드 로더 (캐시) 와 오디오 관리자."""
from __future__ import annotations

import os

import pygame

from src import config as cfg
from src import datafiles as _datafiles

_images: dict = {}
_fonts: dict = {}
_sounds: dict = {}
_json: dict = {}


def load_json(rel: str):
    """data/*.json (src/datafiles.py 와 같은 캐시를 공유)"""
    return _datafiles.load_json(rel)


def image(rel: str, scale: float = 1.0) -> pygame.Surface:
    """assets/images 기준 상대경로. 없으면 눈에 띄는 대체 이미지를 돌려준다."""
    key = (rel, scale)
    if key not in _images:
        path = os.path.join(cfg.IMAGES, rel)
        if os.path.exists(path):
            surf = pygame.image.load(path)
            surf = surf.convert_alpha() if pygame.display.get_surface() else surf
        else:
            surf = pygame.Surface((32, 32), pygame.SRCALPHA)
            surf.fill((255, 0, 255, 180))
        if scale != 1.0:
            w, h = surf.get_size()
            surf = pygame.transform.scale(surf, (int(w * scale), int(h * scale)))
        _images[key] = surf
    return _images[key]


def has_image(rel: str) -> bool:
    return os.path.exists(os.path.join(cfg.IMAGES, rel))


def font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _fonts:
        name = "Galmuri11-Bold.ttf" if bold else "Galmuri11.ttf"
        path = os.path.join(cfg.FONTS, name)
        if os.path.exists(path):
            _fonts[key] = pygame.font.Font(path, size)
        else:  # 폰트 파일이 없으면 시스템의 한글 폰트를 찾는다
            sysname = pygame.font.match_font("nanumgothic,malgungothic,applegothic,notosanscjkkr,unifont")
            _fonts[key] = pygame.font.Font(sysname, size)
    return _fonts[key]


class Audio:
    """BGM 은 mixer.music 으로 스트리밍, 효과음은 Sound 캐시. 오디오 장치가 없으면 조용히 비활성."""

    def __init__(self):
        self.enabled = pygame.mixer.get_init() is not None
        self.current = None
        self.music_volume = 0.55
        self.sfx_volume = 0.7

    @staticmethod
    def _path(name):
        """테마 이름(town, battle ...) → assets/bgm/<name>.ogg, 짧은 곡(victory)은 assets/sfx 에서도 찾는다"""
        name = name.replace("bgm_", "")
        for d in (cfg.BGM, cfg.SFX):
            p = os.path.join(d, name + ".ogg")
            if os.path.exists(p):
                return p
        return None

    def play_bgm(self, bgm_id: str, loop: bool = True, fade_ms: int = 400):
        if not self.enabled or bgm_id == self.current:
            return
        path = self._path(bgm_id)
        if not path:
            return
        self.current = bgm_id
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(self.music_volume)
        pygame.mixer.music.play(-1 if loop else 0, fade_ms=fade_ms)

    def stop_bgm(self, fade_ms: int = 300):
        if self.enabled:
            pygame.mixer.music.fadeout(fade_ms)
        self.current = None

    def sfx(self, sfx_id: str):
        if not self.enabled or not sfx_id:
            return
        if sfx_id not in _sounds:
            path = os.path.join(cfg.SFX, sfx_id.replace("sfx_", "") + ".ogg")
            _sounds[sfx_id] = pygame.mixer.Sound(path) if os.path.exists(path) else None
            if _sounds[sfx_id]:
                _sounds[sfx_id].set_volume(self.sfx_volume)
        if _sounds[sfx_id]:
            _sounds[sfx_id].play()
