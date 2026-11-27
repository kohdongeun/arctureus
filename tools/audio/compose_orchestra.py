"""오케스트라 BGM · 효과음 제작 (FluidSynth + FluidR3_GM 사운드폰트).

    sudo apt-get install fluidsynth fluid-soundfont-gm      # FluidR3_GM.sf2 (MIT 라이선스)
    pip install soundfile
    python tools/audio/compose_orchestra.py [bgm|sfx] [이름 ...]

결과
  assets/bgm/<theme>.ogg   title, town, field, battle, tense, sad, mystery, epic (반복 재생용)
  assets/sfx/<name>.ogg    cursor, confirm, cancel, text, menu, slash, hit, magic, heal ... , victory
  assets/bgm/midi/*.mid    각 곡의 MIDI 원본 (다른 음원으로 다시 렌더링 가능)

곡은 아래 SONGS 에 조성·빠르기·화성 진행·멜로디를 직접 작곡해 두고, '역할'(현악 패드, 아르페지오,
베이스, 오스티나토, 금관 스탭, 타악기, 대선율)별 편성 규칙으로 MIDI 를 만든 뒤 FluidSynth 로 렌더링한다.
"""
from __future__ import annotations

import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile

import numpy as np
import soundfile as sf

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BGM_DIR = os.path.join(ROOT, "assets", "bgm")
SFX_DIR = os.path.join(ROOT, "assets", "sfx")
SF2_CANDIDATES = [os.environ.get("ARCTURUS_SF2", ""), "/usr/share/sounds/sf2/FluidR3_GM.sf2",
                  "/usr/share/soundfonts/FluidR3_GM.sf2"]
SR = 44100
TPQ = 480

# ------------------------------------------------------------------ 음 이름 / 화음
NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7,
        "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
QUAL = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10), "maj7": (0, 4, 7, 11),
        "sus4": (0, 5, 7), "sus2": (0, 2, 7), "dim": (0, 3, 6), "aug": (0, 4, 8), "add9": (0, 4, 7, 14),
        "m9": (0, 3, 7, 10, 14)}

# GM 악기 번호
P = {"piano": 0, "celesta": 8, "glock": 9, "marimba": 12, "guitar": 24, "bass_ac": 32, "violin": 40,
     "viola": 41, "cello": 42, "contrabass": 43, "tremolo": 44, "pizz": 45, "harp": 46, "timpani": 47,
     "strings": 48, "slow_strings": 49, "choir": 52, "orch_hit": 55, "trumpet": 56, "trombone": 57,
     "tuba": 58, "horn": 60, "brass": 61, "oboe": 68, "bassoon": 70, "clarinet": 71, "piccolo": 72,
     "flute": 73, "recorder": 74, "rev_cymbal": 119}
DRUM = {"kick": 36, "snare": 38, "snare2": 40, "tom_lo": 41, "tom_mid": 45, "tom_hi": 48, "crash": 49,
        "ride": 51, "tamb": 54, "cymbal": 57, "triangle": 81, "shaker": 82, "hat": 42}


def nn(s):
    """'C#5' → MIDI 번호"""
    name, octv = s[:-1], int(s[-1])
    return 12 * (octv + 1) + NOTE[name]


def chord(sym, octave=4):
    """'Am', 'F#m7', 'G/B' → (구성음 리스트, 베이스음)"""
    bass = None
    if "/" in sym:
        sym, b = sym.split("/")
        bass = NOTE[b]
    root = sym[0] + (sym[1] if len(sym) > 1 and sym[1] in "#b" else "")
    q = sym[len(root):]
    r = 12 * (octave + 1) + NOTE[root]
    tones = [r + i for i in QUAL[q]]
    b = (12 * (octave - 1) + (bass if bass is not None else NOTE[root]))
    return tones, b


def melody(text):
    """'D5:2 E5:1 r:1 | ...' → [(박 위치, 길이, 음 or None)]"""
    out, t = [], 0.0
    for tok in text.split():
        if tok == "|":
            continue
        n, d = tok.split(":")
        d = float(d)
        out.append((t, d, None if n == "r" else nn(n)))
        t += d
    return out


# ------------------------------------------------------------------ MIDI
class Track:
    def __init__(self, name, ch, program, vol=100, pan=64, reverb=60, chorus=0):
        self.name, self.ch, self.program = name, ch, program
        self.cc = [(0, 7, vol), (0, 10, pan), (0, 91, reverb), (0, 93, chorus), (0, 11, 127)]
        self.notes = []      # (start_beat, dur_beat, note, vel)

    def add(self, start, dur, note, vel):
        if note is None or dur <= 0:
            return
        self.notes.append((start, dur, int(note), int(max(1, min(127, vel)))))

    def expr(self, beat, value):
        self.cc.append((beat, 11, int(value)))


def vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def write_midi(path, tracks, bpm, rng, humanize=True):
    data = []
    tempo = int(60_000_000 / bpm)
    cond = b"\x00\xff\x51\x03" + tempo.to_bytes(3, "big") + b"\x00\xff\x2f\x00"
    data.append(b"MTrk" + struct.pack(">I", len(cond)) + cond)
    for tr in tracks:
        ev = []
        if tr.ch != 9:
            ev.append((0, 0, bytes([0xC0 | tr.ch, tr.program])))
        for beat, num, val in tr.cc:
            ev.append((int(beat * TPQ), 1, bytes([0xB0 | tr.ch, num, val])))
        for start, dur, note, vel in tr.notes:
            j = rng.randint(-6, 6) if humanize and tr.ch != 9 else 0
            on = max(0, int(start * TPQ) + j)
            off = max(on + 1, int((start + dur) * TPQ) + j - 4)
            v = vel + (rng.randint(-5, 5) if humanize else 0)
            ev.append((on, 3, bytes([0x90 | tr.ch, note, max(1, min(127, v))])))
            ev.append((off, 2, bytes([0x80 | tr.ch, note, 0])))
        ev.sort(key=lambda e: (e[0], e[1]))
        body = b"\x00\xff\x03" + vlq(len(tr.name)) + tr.name.encode()
        last = 0
        for tick, _, msg in ev:
            body += vlq(tick - last) + msg
            last = tick
        body += b"\x00\xff\x2f\x00"
        data.append(b"MTrk" + struct.pack(">I", len(body)) + body)
    with open(path, "wb") as f:
        f.write(b"MThd" + struct.pack(">IHHH", 6, 1, len(data), TPQ) + b"".join(data))


# ------------------------------------------------------------------ 편성(역할) 생성기
def bars_of(section):
    """화성 진행 문자열 → [(마디 시작 박, 길이 박, 화음 기호)]  (한 마디에 '/' 없이 공백 두 개 화음이면 반씩)"""
    out = []
    for b, bar in enumerate(section["chords"].split("|")):
        syms = bar.split()
        seg = 4 / len(syms)
        for k, s in enumerate(syms):
            out.append((b * 4 + k * seg, seg, s))
    return out


def role_pad(tr, harm, base, vel, octave=4, spread=True):
    for t, d, s in harm:
        tones, _ = chord(s, octave)
        voicing = [tones[0], tones[1] + (12 if spread else 0), tones[2]] + tones[3:]
        for n in voicing:
            tr.add(base + t, d + 0.05, n, vel)


def role_bass(tr, harm, base, vel, octave=3, pattern=(0,), dur=None, fifth=False):
    for t, d, s in harm:
        _, b = chord(s, octave)
        b += 12
        for k, off in enumerate(pattern):
            if off >= d:
                continue
            n = b + (7 if fifth and k % 2 else 0)
            tr.add(base + t + off, dur or (d - off if len(pattern) == 1 else min(d - off, pattern[1] - pattern[0] if len(pattern) > 1 else d)), n, vel)


def role_arp(tr, harm, base, vel, octave=4, step=0.5, shape="updown", span=2):
    for t, d, s in harm:
        tones, _ = chord(s, octave)
        seq = tones[:3] + [tones[0] + 12, tones[1] + 12, tones[2] + 12][:span + 1]
        if shape == "updown":
            seq = seq + seq[-2:0:-1]
        k, x = 0, 0.0
        while x < d - 1e-6:
            tr.add(base + t + x, step * 1.6, seq[k % len(seq)], vel - (0 if k % 4 == 0 else 8))
            k += 1
            x += step


def role_ostinato(tr, harm, base, vel, octave=3, step=0.25, accent=4, pattern=None):
    for t, d, s in harm:
        tones, b = chord(s, octave)
        root = tones[0]
        pat = pattern or [root, root, root + 7, root]
        k, x = 0, 0.0
        while x < d - 1e-6:
            n = pat[k % len(pat)] if pattern is None else root + pat[k % len(pat)]
            tr.add(base + t + x, step * 0.8, n, vel + (12 if k % accent == 0 else 0))
            k += 1
            x += step


def role_stabs(tr, harm, base, vel, octave=4, beats=(0, 2.5)):
    for t, d, s in harm:
        tones, _ = chord(s, octave)
        for off in beats:
            if off < d:
                for n in tones[:3]:
                    tr.add(base + t + off, 0.45, n, vel)


def role_melody(tr, mel, base, vel, transpose=0, legato=1.0):
    for t, d, n in mel:
        if n is not None:
            tr.add(base + t, d * legato, n + transpose, vel + (6 if d >= 2 else 0))


def role_counter(tr, mel, harm, base, vel, below=True):
    """멜로디 음 아래(또는 위)의 가장 가까운 화성음으로 대선율"""
    def chord_at(x):
        for t, d, s in harm:
            if t <= x < t + d:
                return chord(s, 4)[0]
        return chord(harm[-1][2], 4)[0]
    for t, d, n in mel:
        if n is None or d < 1:
            continue
        cands = []
        for c in chord_at(t):
            for o in (-24, -12, 0, 12):
                cands.append(c + o)
        cands = [c for c in cands if (c < n - 2 if below else c > n + 2)]
        if cands:
            tr.add(base + t, d, max(cands) if below else min(cands), vel)


def role_drums(tr, bars, base, kind, vel):
    for b in range(bars):
        t = base + b * 4
        if kind == "battle":
            for x in (0, 1.5, 2, 3.5):
                tr.add(t + x, 0.2, DRUM["kick"], vel)
            for x in (1, 3):
                tr.add(t + x, 0.2, DRUM["snare"], vel - 10)
            for x in np.arange(0, 4, 0.5):
                tr.add(t + x, 0.1, DRUM["hat"], vel - 40)
            if b % 4 == 0:
                tr.add(t, 1, DRUM["crash"], vel - 10)
            if b % 4 == 3:
                for k, x in enumerate((3, 3.25, 3.5, 3.75)):
                    tr.add(t + x, 0.2, [DRUM["tom_hi"], DRUM["tom_mid"], DRUM["tom_mid"], DRUM["tom_lo"]][k], vel - 6)
        elif kind == "tense":
            for x in (0, 0.75, 1.5, 2, 2.75, 3.5):
                tr.add(t + x, 0.2, DRUM["tom_lo"], vel - (0 if x in (0, 2) else 18))
            tr.add(t + 3, 0.2, DRUM["snare2"], vel - 20)
        elif kind == "march":
            tr.add(t, 0.3, DRUM["kick"], vel)
            tr.add(t + 2, 0.3, DRUM["kick"], vel - 10)
            for x in (1, 3):
                tr.add(t + x, 0.2, DRUM["snare"], vel - 25)
            for x in (3.5, 3.75):
                tr.add(t + x, 0.1, DRUM["snare"], vel - 35)
        elif kind == "light":
            for x in (1, 3):
                tr.add(t + x, 0.2, DRUM["tamb"], vel - 30)
            tr.add(t, 0.2, DRUM["shaker"], vel - 40)
            tr.add(t + 2, 0.2, DRUM["shaker"], vel - 40)
        elif kind == "epic":
            tr.add(t, 0.3, DRUM["kick"], vel)
            if b % 2 == 1:
                tr.add(t + 3, 1, DRUM["cymbal"], vel - 25)
            if b % 8 == 0:
                tr.add(t, 2, DRUM["crash"], vel - 5)


def role_timpani(tr, harm, base, vel, pattern=(0,), roll_last=False):
    for i, (t, d, s) in enumerate(harm):
        _, b = chord(s, 2)
        b = b + 12 if b < 38 else b
        for off in pattern:
            if off < d:
                tr.add(base + t + off, 0.8, b, vel)
    if roll_last and harm:
        t, d, s = harm[-1]
        _, b = chord(s, 2)
        for k in range(16):
            tr.add(base + t + k * d / 16, d / 16, b + 12 if b < 38 else b, vel - 30 + k * 3)


# ------------------------------------------------------------------ 작곡 (8곡)
# section: chords("|"로 마디 구분), mel(멜로디), roles(이 구간에서 연주하는 역할과 세기)
SONGS = {
    "title": dict(bpm=72, desc="신비롭고 서정적인 타이틀", sections=[
        dict(chords="Dm | Bb | F | C | Dm | Bb | Gm | A", mel="r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4",
             roles={"harp_arp": 70, "pad": 52, "celesta": 50, "bass": 55}),
        dict(chords="Dm | Bb | F | C | Dm | Bb | Gm | A",
             mel="D5:2 E5:1 F5:1 | A5:3 G5:1 | F5:2 E5:1 D5:1 | C5:4 | D5:2 F5:1 A5:1 | D6:3 C6:1 | Bb5:2 A5:1 G5:1 | A5:4",
             roles={"harp_arp": 66, "pad": 62, "bass": 60, "flute": 86}),
        dict(chords="Bb | F | Gm | Dm | Bb | F | Gm | A7",
             mel="Bb5:2 A5:2 | G5:2 F5:2 | A5:2 G5:2 | F5:2 E5:2 | D5:2 F5:1 E5:1 | D5:2 A4:2 | Bb4:2 C5:1 E5:1 | D5:4",
             roles={"harp_arp": 66, "pad": 72, "bass": 64, "flute": 84, "choir": 58, "counter_cello": 70}),
        dict(chords="Dm | Bb | F | C | Gm | A | Dm | Dm",
             mel="D5:2 E5:1 F5:1 | A5:3 G5:1 | F5:2 E5:1 D5:1 | C5:4 | Bb4:2 D5:1 G5:1 | E5:2 C#5:2 | D5:4 | r:4",
             roles={"harp_arp": 60, "pad": 60, "bass": 58, "violin": 80, "celesta": 44}),
    ]),
    "town": dict(bpm=108, desc="밝고 경쾌한 기타·플루트의 마을", sections=[
        dict(chords="G | Em | C | D | G | Em | Am D | G", mel="r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4",
             roles={"guitar": 76, "pizz_bass": 70, "drums_light": 70}),
        dict(chords="G | Em | C | D | G | Em | Am D | G",
             mel="B4:1 D5:1 G5:1 D5:1 | E5:2 D5:1 B4:1 | C5:1 E5:1 G5:1 E5:1 | D5:4 | B4:1 D5:1 G5:1 B5:1 | A5:2 G5:1 E5:1 | C5:1 E5:1 D5:1 F#5:1 | G5:4",
             roles={"guitar": 72, "pizz_bass": 72, "flute": 90, "drums_light": 70}),
        dict(chords="C | D | G | Em | C | D | G | G",
             mel="E5:1 F#5:1 G5:2 | B5:2 A5:2 | G5:1 F#5:1 E5:2 | D5:4 | C5:1 D5:1 E5:2 | A5:2 G5:2 | F#5:1 E5:1 D5:1 F#5:1 | G5:4",
             roles={"guitar": 72, "pizz_bass": 72, "clarinet": 84, "flute_counter": 70, "pad": 46, "drums_light": 74}),
        dict(chords="G | Em | C | D | G | Em | Am D | G",
             mel="B4:1 D5:1 G5:1 D5:1 | E5:2 D5:1 B4:1 | C5:1 E5:1 G5:1 E5:1 | D5:4 | B4:1 D5:1 G5:1 B5:1 | A5:2 G5:1 E5:1 | C5:1 E5:1 D5:1 F#5:1 | G5:4",
             roles={"guitar": 72, "pizz_bass": 72, "flute": 88, "oboe_counter": 66, "pad": 50, "drums_light": 74, "glock": 50}),
    ]),
    "field": dict(bpm=120, desc="넓고 희망찬 모험 필드", sections=[
        dict(chords="D | A | Bm | G | D | A | G A | D", mel="r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4",
             roles={"str_ostinato": 72, "bass": 76, "timpani": 70, "drums_march": 68, "horn_pad": 58}),
        dict(chords="D | A | Bm | G | D | A | G A | D",
             mel="A4:1 D5:1 F#5:1 A5:1 | A5:2 G5:1 F#5:1 | F#5:1 E5:1 D5:1 F#5:1 | E5:4 | A4:1 D5:1 F#5:1 A5:1 | B5:2 A5:1 F#5:1 | G5:1 F#5:1 E5:2 | D5:4",
             roles={"str_ostinato": 70, "bass": 76, "timpani": 70, "drums_march": 68, "horn": 92, "violin_double": 76}),
        dict(chords="G | D | Em | A | G | D | Em A | D",
             mel="B5:2 A5:2 | F#5:2 D5:2 | E5:1 F#5:1 G5:2 | A5:4 | B5:2 A5:1 G5:1 | F#5:2 D5:2 | E5:2 A4:2 | D5:4",
             roles={"str_ostinato": 74, "bass": 78, "timpani": 74, "drums_march": 72, "trumpet": 92, "pad": 66,
                    "counter_horn": 74, "flute_double": 70}),
        dict(chords="D | A | Bm | G | D | A | G A | D",
             mel="A4:1 D5:1 F#5:1 A5:1 | A5:2 G5:1 F#5:1 | F#5:1 E5:1 D5:1 F#5:1 | E5:4 | A4:1 D5:1 F#5:1 A5:1 | B5:2 A5:1 F#5:1 | G5:1 F#5:1 E5:2 | D5:4",
             roles={"str_ostinato": 74, "bass": 80, "timpani": 78, "drums_march": 74, "horn": 94, "trumpet_double": 80,
                    "pad": 70, "timp_roll": 80}),
    ]),
    "battle": dict(bpm=152, desc="웅장한 금관·타악기 전투", sections=[
        dict(chords="Cm | Cm | Ab | G", mel="r:4 | r:4 | r:4 | r:4",
             roles={"str_ostinato": 84, "low_brass": 90, "timpani8": 86, "drums_battle": 92}),
        dict(chords="Cm | Ab | Bb | G | Cm | Ab | Fm G | Cm",
             mel="C5:1.5 G4:0.5 C5:1 Eb5:1 | D5:1.5 Bb4:0.5 C5:2 | Eb5:1 F5:1 G5:1 Bb5:1 | Ab5:2 G5:2 | C6:1.5 Bb5:0.5 Ab5:1 G5:1 | F5:1.5 Eb5:0.5 F5:2 | Ab5:1 G5:1 F5:1 D5:1 | C5:4",
             roles={"str_ostinato": 84, "low_brass": 86, "timpani8": 86, "drums_battle": 92, "trumpet": 100,
                    "horn_double": 88, "brass_stabs": 84}),
        dict(chords="Ab | Eb | Bb | Cm | Ab | Eb | F | G",
             mel="Eb5:2 C5:2 | G5:3 F5:1 | D5:2 Bb4:2 | C5:4 | Eb5:1 F5:1 G5:2 | Bb5:2 G5:2 | F5:1 Eb5:1 D5:1 C5:1 | B4:4",
             roles={"str_ostinato": 86, "low_brass": 88, "timpani8": 88, "drums_battle": 94, "violin": 92,
                    "horn": 90, "choir": 70, "brass_stabs": 86}),
        dict(chords="Cm | Ab | Bb | G | Cm | Ab | Fm G | Cm",
             mel="C5:1.5 G4:0.5 C5:1 Eb5:1 | D5:1.5 Bb4:0.5 C5:2 | Eb5:1 F5:1 G5:1 Bb5:1 | Ab5:2 G5:2 | C6:1.5 Bb5:0.5 Ab5:1 G5:1 | F5:1.5 Eb5:0.5 F5:2 | Ab5:1 G5:1 F5:1 D5:1 | C5:4",
             roles={"str_ostinato": 88, "low_brass": 90, "timpani8": 90, "drums_battle": 96, "trumpet": 104,
                    "horn_double": 92, "violin_double": 84, "brass_stabs": 88, "orch_hit": 90}),
    ]),
    "tense": dict(bpm=164, desc="빠르고 긴박한 위기", sections=[
        dict(chords="Em | Em | C | B | Em | Em | F | B", mel="r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4",
             roles={"str_16": 86, "bass_pulse": 84, "drums_tense": 88, "tremolo_hi": 60}),
        dict(chords="Em | Em | C | B | Em | Em | F | B",
             mel="E4:2 G4:1 F#4:1 | E4:2 B3:2 | E4:1 G4:1 C5:2 | B4:4 | E5:2 D5:1 C5:1 | B4:2 G4:2 | F4:1 A4:1 C5:2 | B4:4",
             roles={"str_16": 86, "bass_pulse": 86, "drums_tense": 90, "low_brass_mel": 98, "brass_stabs_tense": 84,
                    "timpani_hits": 92}),
        dict(chords="Am | Em | F | B | Am | Em | C | B7",
             mel="A4:1 C5:1 E5:2 | B4:2 G4:2 | A4:1 C5:1 F5:2 | D#5:4 | E5:1 F5:1 E5:1 C5:1 | B4:2 E4:2 | G4:1 A4:1 C5:2 | B4:4",
             roles={"str_16": 88, "bass_pulse": 86, "drums_tense": 92, "trumpet": 96, "tremolo_hi": 66,
                    "timpani_hits": 94, "orch_hit": 86}),
    ]),
    "sad": dict(bpm=64, desc="피아노와 첼로의 슬픈 이별", sections=[
        dict(chords="Am | F | C | G | Am | F | Dm E | Am", mel="r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4",
             roles={"piano_arp": 72}),
        dict(chords="Am | F | C | G | Am | F | Dm E | Am",
             mel="E4:2 C4:1 B3:1 | A3:3 C4:1 | G3:2 E3:1 G3:1 | B3:4 | A3:2 C4:1 E4:1 | F4:3 E4:1 | D4:2 B3:2 | A3:4",
             roles={"piano_arp": 66, "cello_mel": 92, "pad": 44}),
        dict(chords="F | C | Dm | Am | F | C | Dm E | Am",
             mel="A5:2 G5:1 F5:1 | E5:3 C5:1 | D5:2 F5:1 E5:1 | C5:4 | A5:2 B5:1 C6:1 | G5:3 E5:1 | F5:2 E5:1 D5:1 | E5:4",
             roles={"piano_arp": 64, "violin": 86, "counter_cello": 74, "pad": 56}),
        dict(chords="Am | F | C | G | Am | F | Dm E | Am",
             mel="E5:2 C5:1 B4:1 | A4:3 C5:1 | G4:2 E4:1 G4:1 | B4:4 | A4:2 C5:1 E5:1 | F5:3 E5:1 | D5:2 B4:2 | A4:4",
             roles={"piano_mel": 82, "piano_arp": 56, "cello_counter_soft": 64, "pad": 48}),
    ]),
    "mystery": dict(bpm=76, desc="어둡고 신비로운 음모·유적", sections=[
        dict(chords="Dm | Eb | Dm | Db | Bb | A | Dm | A", mel="r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4",
             roles={"drone": 62, "celesta_arp": 52, "choir": 48}),
        dict(chords="Dm | Eb | Dm | Db | Bb | A | Dm | A",
             mel="A4:3 Bb4:1 | A4:2 G4:2 | F4:3 E4:1 | D4:4 | F4:2 E4:1 D4:1 | C#4:3 E4:1 | D4:2 F4:1 A4:1 | G#4:4",
             roles={"drone": 62, "celesta_arp": 50, "choir": 54, "oboe": 80, "harp_low": 56}),
        dict(chords="Gm | Ab | Gm | F#dim | Eb | D | Gm | A",
             mel="D5:3 Eb5:1 | D5:2 C5:2 | Bb4:3 A4:1 | G4:4 | Bb4:2 A4:1 G4:1 | F#4:3 A4:1 | G4:2 Bb4:1 D5:1 | C#5:4",
             roles={"drone": 66, "celesta_arp": 50, "choir": 58, "flute_low": 78, "tremolo_hi": 46, "timp_soft": 60}),
    ]),
    "epic": dict(bpm=84, desc="웅장하고 감동적인 결의", sections=[
        dict(chords="C | G/B | Am | F | C | G | F G | C", mel="r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4",
             roles={"pad": 66, "bass": 70, "harp_arp": 60, "choir": 56, "timp_roll": 60}),
        dict(chords="C | G/B | Am | F | C | G | F G | C",
             mel="G4:1 C5:1 E5:2 | D5:2 B4:2 | C5:1 E5:1 A5:2 | F5:4 | E5:1 G5:1 C6:2 | B5:2 G5:2 | A5:1 G5:1 F5:1 D5:1 | C5:4",
             roles={"pad": 72, "bass": 76, "horn": 96, "violin_double": 78, "timpani": 70, "drums_epic": 74, "harp_arp": 56}),
        dict(chords="Am | F | C | G | Am | F | Dm G | C",
             mel="A5:2 G5:1 E5:1 | F5:2 C5:2 | E5:1 F5:1 G5:2 | D5:4 | E5:1 F5:1 A5:2 | C6:2 A5:2 | F5:1 G5:1 A5:1 B5:1 | C6:4",
             roles={"pad": 82, "bass": 82, "trumpet": 100, "horn_double": 90, "violin_double": 86, "choir": 80,
                    "timpani": 80, "drums_epic": 84, "brass_stabs_epic": 80}),
        dict(chords="F | G | Em | Am | F | G | C | C",
             mel="A5:2 B5:2 | C6:2 D6:2 | B5:2 G5:2 | A5:4 | F5:1 A5:1 C6:2 | D6:2 B5:2 | C6:4 | r:4",
             roles={"pad": 86, "bass": 84, "trumpet": 104, "horn_double": 94, "violin_double": 90, "choir": 88,
                    "timpani": 84, "drums_epic": 88, "timp_roll": 86, "orch_hit_end": 92}),
    ]),
}


def arrange(song, rng):
    tracks = {}

    def T(name, ch, prog, vol=100, pan=64, reverb=70, chorus=0):
        if name not in tracks:
            tracks[name] = Track(name, ch, prog, vol, pan, reverb, chorus)
        return tracks[name]

    base = 0.0
    for sec in song["sections"]:
        harm = bars_of(sec)
        nbars = len(sec["chords"].split("|"))
        mel = melody(sec["mel"])
        for role, v in sec["roles"].items():
            if role == "pad":
                role_pad(T("strings", 0, P["slow_strings"], 96, 64, 90), harm, base, v)
            elif role == "horn_pad":
                role_pad(T("horn_pad", 1, P["horn"], 90, 50, 80), harm, base, v, 3)
            elif role == "choir":
                role_pad(T("choir", 2, P["choir"], 92, 70, 100), harm, base, v)
            elif role == "drone":
                for t, d, s in harm:
                    _, b = chord(s, 2)
                    T("drone", 3, P["contrabass"], 100, 50, 90).add(base + t, d + 0.1, b + 12, v)
                    T("drone_vla", 4, P["slow_strings"], 80, 76, 100).add(base + t, d + 0.1, b + 24, v - 10)
            elif role == "bass":
                role_bass(T("bass", 3, P["contrabass"], 100, 54, 70), harm, base, v)
                role_bass(T("cello_bass", 4, P["cello"], 90, 70, 70), harm, base, v - 10, pattern=(0, 2))
            elif role == "pizz_bass":
                role_bass(T("pizz", 3, P["pizz"], 104, 58, 60), harm, base, v, pattern=(0, 1, 2, 3), dur=0.5, fifth=True)
            elif role == "bass_pulse":
                role_ostinato(T("bass_pulse", 3, P["contrabass"], 104, 60, 50), harm, base, v, 2, 0.5, 2,
                              pattern=[0, 0, 0, 0])
            elif role == "harp_arp":
                role_arp(T("harp", 5, P["harp"], 96, 40, 90), harm, base, v, 4, 0.5)
            elif role == "harp_low":
                role_arp(T("harp", 5, P["harp"], 96, 40, 90), harm, base, v, 3, 1.0, "up", 1)
            elif role == "celesta":
                role_arp(T("celesta", 6, P["celesta"], 80, 90, 100), harm, base, v, 5, 1.0, "up", 1)
            elif role == "celesta_arp":
                role_arp(T("celesta", 6, P["celesta"], 80, 90, 100), harm, base, v, 5, 0.75, "updown", 2)
            elif role == "glock":
                role_arp(T("glock", 6, P["glock"], 70, 90, 90), harm, base, v, 5, 2.0, "up", 1)
            elif role == "guitar":
                role_arp(T("guitar", 5, P["guitar"], 104, 46, 50), harm, base, v, 3, 0.5, "updown", 2)
            elif role == "piano_arp":
                role_arp(T("piano", 7, P["piano"], 100, 60, 70), harm, base, v, 3, 0.5, "updown", 3)
            elif role == "piano_mel":
                role_melody(T("piano", 7, P["piano"], 100, 60, 70), mel, base, v)
            elif role == "str_ostinato":
                role_ostinato(T("str_ost", 8, P["strings"], 92, 72, 60), harm, base, v, 3, 0.5, 2)
            elif role == "str_16":
                role_ostinato(T("str_16", 8, P["strings"], 92, 72, 50), harm, base, v, 3, 0.25, 4,
                              pattern=[0, 0, 12, 0, 0, 1, 0, 12])
            elif role == "tremolo_hi":
                role_pad(T("tremolo", 10, P["tremolo"], 70, 80, 90), harm, base, v, 5, spread=False)
            elif role == "low_brass":
                role_stabs(T("low_brass", 11, P["trombone"], 96, 56, 60), harm, base, v, 3, (0, 1.5, 3))
            elif role in ("brass_stabs", "brass_stabs_tense", "brass_stabs_epic"):
                beats = {"brass_stabs": (0, 2.5), "brass_stabs_tense": (0, 0.75, 1.5), "brass_stabs_epic": (0, 2)}[role]
                role_stabs(T("brass", 12, P["brass"], 96, 70, 70), harm, base, v, 4, beats)
            elif role == "low_brass_mel":
                role_melody(T("trombone_mel", 11, P["trombone"], 100, 56, 60), mel, base, v)
                role_melody(T("tuba_mel", 13, P["tuba"], 90, 60, 60), mel, base, v - 10, -12)
            elif role in ("timpani", "timpani8", "timp_soft", "timpani_hits", "timp_roll"):
                pat = {"timpani": (0,), "timpani8": (0, 0.5, 1.5, 2, 3), "timp_soft": (0,), "timpani_hits": (0, 2.75),
                       "timp_roll": ()}[role]
                role_timpani(T("timpani", 14, P["timpani"], 110, 64, 70), harm, base, v, pat,
                             roll_last=role == "timp_roll")
            elif role.startswith("drums_"):
                role_drums(T("drums", 9, 0, 100, 64, 50), nbars, base, role[6:], v)
            elif role in ("orch_hit", "orch_hit_end"):
                tr = T("orch_hit", 15, P["orch_hit"], 100, 64, 80)
                points = [harm[0][0]] if role == "orch_hit" else [harm[-1][0]]
                for t in points:
                    for n in chord(harm[0][2] if role == "orch_hit" else harm[-1][2], 4)[0][:3]:
                        tr.add(base + t, 1.0, n, v)
            else:
                # 멜로디 계열: flute, clarinet, oboe, horn, trumpet, violin, cello_mel, flute_low ...
                inst = {"flute": "flute", "flute_low": "flute", "clarinet": "clarinet", "oboe": "oboe",
                        "horn": "horn", "trumpet": "trumpet", "violin": "violin", "cello_mel": "cello"}
                doubles = {"violin_double": ("violin", 0), "flute_double": ("flute", 12), "horn_double": ("horn", -12),
                           "trumpet_double": ("trumpet", 0)}
                counters = {"counter_cello": "cello", "counter_horn": "horn", "flute_counter": "flute",
                            "oboe_counter": "oboe", "cello_counter_soft": "cello"}
                chmap = {"flute": 1, "clarinet": 2, "oboe": 2, "horn": 1, "trumpet": 10, "violin": 13,
                         "cello": 4}
                if role in inst:
                    name = inst[role]
                    tp = -12 if role == "flute_low" else 0
                    role_melody(T(name + "_mel", chmap[name], P[name], 104, 60, 80), mel, base, v, tp, 0.98)
                elif role in doubles:
                    name, tp = doubles[role]
                    role_melody(T(name + "_dbl", chmap[name], P[name], 96, 80, 80), mel, base, v, tp, 0.98)
                elif role in counters:
                    name = counters[role]
                    role_counter(T(name + "_ctr", chmap[name], P[name], 92, 44, 80), mel, harm, base, v)
        base += nbars * 4
    return list(tracks.values()), base


# ------------------------------------------------------------------ 렌더링
def sf2_path():
    for p in SF2_CANDIDATES:
        if p and os.path.exists(p):
            return p
    sys.exit("사운드폰트(FluidR3_GM.sf2)를 찾을 수 없습니다: sudo apt-get install fluid-soundfont-gm")


def render(mid, wav, gain=0.6):
    if not shutil.which("fluidsynth"):
        sys.exit("fluidsynth 가 필요합니다: sudo apt-get install fluidsynth")
    subprocess.run(["fluidsynth", "-ni", "-q", "-g", str(gain), "-r", str(SR),
                    "-o", "synth.reverb.room-size=0.72", "-o", "synth.reverb.width=0.9", "-o", "synth.reverb.level=0.8",
                    "-o", "synth.chorus.active=0", "-F", wav, sf2_path(), mid], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    a, sr = sf.read(wav, dtype="float32")
    return a if a.ndim == 2 else np.stack([a, a], 1)


def master(a, target_rms=0.12, peak=0.95):
    rms = float(np.sqrt(np.mean(a ** 2))) + 1e-9
    a = a * (target_rms / rms)
    # 부드러운 리미터
    a = np.tanh(a / peak) * peak
    return a


def save_ogg(path, a, quality=0.5):
    """libsndfile 은 긴 오디오를 OGG 로 한 번에 쓰면 세그폴트가 나므로 작은 덩어리로 나눠 쓴다"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    a = np.ascontiguousarray(a, dtype=np.float32)
    with sf.SoundFile(path, "w", SR, a.shape[1], format="OGG", subtype="VORBIS",
                      compression_level=1 - quality) as f:
        for i in range(0, len(a), 4096):
            f.write(a[i:i + 4096])


def build_bgm(names):
    rng = random.Random(7)
    midi_dir = os.path.join(BGM_DIR, "midi")
    os.makedirs(midi_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, song in SONGS.items():
            if names and name not in names:
                continue
            tracks, beats = arrange(song, rng)
            mid = os.path.join(midi_dir, name + ".mid")
            write_midi(mid, tracks, song["bpm"], rng)
            a = render(mid, os.path.join(tmp, name + ".wav"))
            # 반복 재생: 곡 길이(박 수)로 자르고 잔향 꼬리를 앞부분에 겹쳐 이음매를 부드럽게
            n = int(beats * 60 / song["bpm"] * SR)
            body, tail = a[:n].copy(), a[n:n + SR * 3]
            if len(tail):
                fade = np.linspace(1, 0, len(tail))[:, None]
                body[:len(tail)] += tail * fade
            a = master(body)
            save_ogg(os.path.join(BGM_DIR, name + ".ogg"), a)
            print(f"  bgm/{name}.ogg  {len(a) / SR:5.1f}초  ({song['desc']}, {len(tracks)}트랙)")


# ------------------------------------------------------------------ 효과음
def tone_midi(path, notes, program, bpm=120, ch=0, drum=False):
    tr = Track("sfx", 9 if drum else ch, program, 110, 64, 70)
    for start, dur, note, vel in notes:
        tr.add(start, dur, note, vel)
    write_midi(path, [tr], bpm, random.Random(1), humanize=False)


def inst(tmp, name, notes, program, bpm=120, drum=False, length=None):
    mid = os.path.join(tmp, name + ".mid")
    tone_midi(mid, notes, program, bpm, drum=drum)
    a = render(mid, os.path.join(tmp, name + ".wav"), gain=0.8)
    if length:
        a = a[:int(length * SR)]
    return trim_silence(a)


def trim_silence(a, thr=1e-3):
    idx = np.where(np.abs(a).max(axis=1) > thr)[0]
    return a[: idx[-1] + 1] if len(idx) else a


def noise(n, seed=0):
    return np.random.default_rng(seed).standard_normal(n).astype(np.float32)


def bandpass_sweep(n, f0, f1, q=6.0, seed=0):
    """주파수가 움직이는 공명 필터를 거친 노이즈 (바람 가르는 소리)"""
    x = noise(n, seed)
    y = np.zeros(n, np.float32)
    f = np.geomspace(f0, f1, n)
    b1 = b2 = 0.0
    for i in range(n):
        w = 2 * np.pi * f[i] / SR
        r = 1 - w / q
        y[i] = x[i] * (1 - r) + 2 * r * np.cos(w) * b1 - r * r * b2
        b2, b1 = b1, y[i]
    return y / (np.abs(y).max() + 1e-9)


def ring(n, freqs, decay):
    t = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * f * t) * np.exp(-t * decay * (1 + k * 0.3)) for k, f in enumerate(freqs)) / len(freqs)


def env(n, a=0.005, decay=8.0):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t * decay)


def stereo(x, width=0.0):
    x = x.astype(np.float32)
    if width:
        d = int(width * SR)
        r = np.concatenate([np.zeros(d, np.float32), x[:-d]]) if d else x
        return np.stack([x, r], 1)
    return np.stack([x, x], 1)


def mix(*parts):
    n = max(len(p) for p, _ in parts)
    out = np.zeros((n, 2), np.float32)
    for p, g in parts:
        out[:len(p)] += p * g
    return out


def lowpass(x, k):
    y = np.zeros_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += k * (v - acc)
        y[i] = acc
    return y


def build_sfx(names):
    os.makedirs(SFX_DIR, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        I = lambda *a, **k: inst(tmp, *a, **k)  # noqa: E731
        S = {}
        # --- UI: 맑고 짧은 악기음
        S["cursor"] = I("cursor", [(0, 0.12, nn("E6"), 70)], P["celesta"])
        S["confirm"] = I("confirm", [(0, 0.2, nn("G5"), 92), (0.12, 0.35, nn("D6"), 96)], P["harp"])
        S["cancel"] = I("cancel", [(0, 0.15, nn("D4"), 96), (0.14, 0.25, nn("A3"), 90)], P["pizz"])
        S["text"] = I("text", [(0, 0.08, nn("A5"), 54)], P["marimba"], length=0.25)
        S["menu"] = I("menu", [(0, 0.3, nn("C5"), 80), (0.08, 0.3, nn("E5"), 80), (0.16, 0.3, nn("G5"), 84),
                               (0.24, 0.5, nn("C6"), 88)], P["harp"])
        # --- 전투
        n = int(0.55 * SR)
        whoosh = bandpass_sweep(int(0.22 * SR), 600, 5200, 9, 1) * np.linspace(0.2, 1, int(0.22 * SR)) ** 2
        blade = ring(n, [2350, 3720, 5180, 7400], 9) * env(n, 0.002, 6)
        S["slash"] = mix((stereo(np.concatenate([whoosh, np.zeros(n - len(whoosh), np.float32)]), 0.004), 0.7),
                         (stereo(np.concatenate([np.zeros(int(0.16 * SR), np.float32), blade[:n - int(0.16 * SR)]]), 0.002), 0.55))
        n = int(0.7 * SR)
        thump = np.sin(2 * np.pi * np.cumsum(np.geomspace(140, 45, n)) / SR) * env(n, 0.002, 7)
        crack = lowpass(noise(n, 3) * env(n, 0.001, 30), 0.35)
        timp = I("hit_timp", [(0, 0.5, nn("G2"), 120)], P["timpani"])
        S["hit"] = mix((stereo(thump), 0.9), (stereo(crack), 0.6), (timp, 0.7))
        S["shot"] = mix((stereo(lowpass(noise(int(0.08 * SR), 5), 0.9) * env(int(0.08 * SR), 0.0005, 40)), 0.9),
                        (stereo(np.sin(2 * np.pi * np.cumsum(np.geomspace(220, 50, int(0.5 * SR))) / SR) * env(int(0.5 * SR), 0.001, 9)), 0.8),
                        (I("shot_timp", [(0, 0.3, nn("C3"), 110)], P["timpani"]), 0.4))
        n = int(1.1 * SR)
        S["steam"] = stereo(lowpass(noise(n, 7), 0.25) * np.minimum(1, np.arange(n) / (0.06 * SR)) * np.exp(-np.arange(n) / SR * 2.6), 0.01)
        n = int(1.2 * SR)
        rumble = lowpass(noise(n, 8), 0.04) * env(n, 0.03, 2.5) * 4
        crackle = (np.random.default_rng(9).random(n) > 0.997).astype(np.float32) * noise(n, 10) * env(n, 0.01, 3)
        S["fire"] = mix((stereo(rumble), 0.8), (stereo(crackle, 0.003), 0.6),
                        (I("fire_rev", [(0, 1.0, nn("C4"), 90)], P["rev_cymbal"], length=1.0), 0.35))
        S["guard"] = mix((I("guard_brass", [(0, 0.4, nn("C3"), 104), (0, 0.4, nn("G3"), 100)], P["brass"]), 0.8),
                         (stereo(ring(int(0.6 * SR), [880, 1420, 2210], 10) * env(int(0.6 * SR), 0.001, 8)), 0.4))
        S["enemy_die"] = mix((I("die_brass", [(0, 0.5, nn("E3"), 100), (0.4, 0.8, nn("C3"), 96), (0.9, 1.4, nn("A2"), 92)],
                                P["trombone"]), 0.8),
                             (I("die_timp", [(0, 0.6, nn("A2"), 118)], P["timpani"]), 0.7))
        # --- 마법
        S["magic"] = mix((I("magic_harp", [(i * 0.06, 0.6, nn(x), 86) for i, x in enumerate(
                             ["C5", "E5", "G5", "B5", "D6", "E6", "G6"])], P["harp"]), 0.8),
                         (I("magic_cel", [(0.3, 0.8, nn("E6"), 80), (0.3, 0.8, nn("B6"), 74)], P["celesta"]), 0.6),
                         (I("magic_rev", [(0, 0.8, nn("C5"), 80)], P["rev_cymbal"], length=0.8), 0.4))
        S["heal"] = mix((I("heal_glock", [(i * 0.1, 0.8, nn(x), 84) for i, x in enumerate(["C6", "E6", "G6", "C7"])],
                           P["glock"]), 0.6),
                        (I("heal_choir", [(0, 1.4, nn(x), 70) for x in ("C5", "E5", "G5")], P["choir"]), 0.7))
        S["wave"] = mix((I("wave_choir", [(0, 1.0, nn(x), 84) for x in ("D5", "A5")], P["choir"]), 0.7),
                        (I("wave_trem", [(0, 0.9, nn(x), 80) for x in ("D6", "A6")], P["tremolo"]), 0.5))
        S["buff"] = mix((I("buff_brass", [(0, 0.25, nn("C4"), 96), (0, 0.25, nn("E4"), 96), (0.22, 0.6, nn("G4"), 104),
                                          (0.22, 0.6, nn("C5"), 104)], P["brass"]), 0.8),
                        (I("buff_harp", [(0.2 + i * 0.05, 0.5, nn(x), 80) for i, x in enumerate(["C5", "E5", "G5", "C6"])],
                           P["harp"]), 0.5))
        # --- 진행
        S["encounter"] = mix((I("enc_hit", [(0, 0.6, nn(x), 120) for x in ("C4", "Eb4", "G4")], P["orch_hit"]), 0.9),
                             (I("enc_trem", [(0.1, 0.8, nn(x), 96) for x in ("C3", "C4")], P["tremolo"]), 0.6),
                             (I("enc_timp", [(0, 0.3, nn("C3"), 120)], P["timpani"]), 0.6))
        S["levelup"] = I("levelup", [(0, 0.2, nn("C5"), 100), (0.18, 0.2, nn("E5"), 100), (0.36, 0.2, nn("G5"), 104),
                                     (0.54, 0.9, nn("C6"), 110), (0.54, 0.9, nn("G5"), 100), (0.54, 0.9, nn("E5"), 100)],
                         P["trumpet"], bpm=60)
        S["escape"] = I("escape", [(i * 0.05, 0.12, nn(x), 86) for i, x in enumerate(
            ["C5", "D5", "E5", "F5", "G5", "A5", "B5", "C6"])], P["flute"])
        n = int(0.12 * SR)
        S["step"] = stereo(lowpass(noise(n, 11), 0.15) * env(n, 0.002, 40) * 3)
        S["door"] = mix((I("door_timp", [(0, 0.4, nn("D2"), 100)], P["timpani"]), 0.6),
                        (stereo(lowpass(noise(int(0.3 * SR), 12), 0.05) * env(int(0.3 * SR), 0.002, 12) * 6), 0.5))
        # 승리 팡파르 (전투 승리 시 음악 대신 재생)
        fan = [(0, 0.3, "G4"), (0.33, 0.3, "C5"), (0.66, 0.3, "E5"), (1.0, 1.0, "G5"), (2.0, 0.5, "E5"), (2.5, 1.5, "G5"),
               (4.0, 0.5, "A5"), (4.5, 0.5, "G5"), (5.0, 0.5, "F5"), (5.5, 0.5, "E5"), (6.0, 0.5, "D5"), (6.5, 0.5, "E5"),
               (7.0, 0.5, "F5"), (7.5, 0.5, "D5"), (8.0, 2.5, "C5")]
        tmp_tracks = [Track("tp", 0, P["trumpet"], 110, 64, 80), Track("hn", 1, P["horn"], 100, 50, 80),
                      Track("st", 2, P["strings"], 90, 80, 90), Track("ti", 3, P["timpani"], 110, 64, 70),
                      Track("dr", 9, 0, 100, 64, 50)]
        for t, d, x in fan:
            tmp_tracks[0].add(t, d, nn(x), 108)
            tmp_tracks[1].add(t, d, nn(x) - 12, 96)
        for t, s in ((0, "C"), (2, "C"), (4, "F"), (6, "G"), (8, "C")):
            for n_ in chord(s, 4)[0]:
                tmp_tracks[2].add(t, 2 if t < 8 else 2.5, n_, 90)
            tmp_tracks[3].add(t, 0.5, chord(s, 2)[1] + 12, 112)
        tmp_tracks[4].add(0, 1, DRUM["crash"], 100)
        tmp_tracks[4].add(8, 1, DRUM["crash"], 110)
        mid = os.path.join(tmp, "victory.mid")
        write_midi(mid, tmp_tracks, 132, random.Random(2))
        S["victory"] = trim_silence(render(mid, os.path.join(tmp, "victory.wav"), 0.7))

        for name, a in S.items():
            if names and name not in names:
                continue
            a = np.asarray(a, np.float32)
            pk = np.abs(a).max() + 1e-9
            # 잔향 꼬리: 피크 대비 -45dB 아래는 자르고, UI 음은 짧게 (빠르게 넘겨도 겹치지 않게)
            loud = np.where(np.abs(a).max(axis=1) > pk * 0.0056)[0]
            cap = {"cursor": 0.35, "text": 0.22, "confirm": 0.7, "cancel": 0.6, "menu": 0.9, "step": 0.12, "victory": 10}.get(name, 3.5)
            a = a[: min(loud[-1] + 1 if len(loud) else len(a), int(cap * SR))]
            a = a / pk * (0.9 if name not in ("text", "cursor", "step") else 0.55)
            fade = min(len(a), int(0.02 * SR))
            a[-fade:] *= np.linspace(1, 0, fade)[:, None]
            save_ogg(os.path.join(SFX_DIR, name + ".ogg"), a, 0.6)
            print(f"  sfx/{name}.ogg  {len(a) / SR:4.2f}초")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    rest = sys.argv[2:]
    if what in ("bgm", "all"):
        build_bgm(rest)
    if what in ("sfx", "all"):
        build_sfx(rest)
