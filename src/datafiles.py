"""data/*.json 로더 (pygame·ursina 어느 쪽에도 의존하지 않음 — 2D/3D 공용)."""
import json
import os

from src import config as cfg

_cache: dict = {}


def load_json(rel: str):
    if rel not in _cache:
        with open(os.path.join(cfg.DATA, rel), encoding="utf-8") as f:
            _cache[rel] = json.load(f)
    return _cache[rel]
