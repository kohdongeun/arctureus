"""레트로 JRPG 풍 BGM / 효과음 합성기 (numpy).

곡은 아래 SONGS 에 음표 데이터로 직접 작곡되어 있고, 같은 데이터로
  - assets/sounds/bgm/<id>.mid : 표준 MIDI 파일 (다른 음원/DAW 에서 편곡용)
  - assets/sounds/bgm/<id>.wav : 칩튠 합성 결과 (게임에서 재생)
을 만든다. 효과음은 assets/sounds/sfx/<id>.wav.

pygame 은 MIDI 재생에 시스템 신시사이저가 필요해 환경마다 소리가 다르므로,
게임은 직접 합성한 WAV 를 재생한다.

    python tools/audio/gen_audio.py
"""
from __future__ import annotations

import os
import struct
import wave

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BGM = os.path.join(ROOT, "assets", "sounds", "bgm")
SFX = os.path.join(ROOT, "assets", "sounds", "sfx")
SR = 22050

NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6,
        "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def midi_num(name: str) -> int:
    name, octv = name[:-1], int(name[-1])
    return 12 * (octv + 1) + NOTE[name]


def freq(m: int) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def parse(seq: str):
    """'F5:3 E5:1 r:2' → [(midi or None, 8분음표 길이)]"""
    out = []
    for tok in seq.split():
        if tok == "|":
            continue
        n, d = tok.split(":")
        out.append((None if n == "r" else midi_num(n), float(d)))
    return out


CHORDS = {  # 근음 기준 구성음 (반음)
    "": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10), "sus": (0, 5, 7),
}


def chord_notes(sym: str, octave: int):
    root = sym[0] + (sym[1] if len(sym) > 1 and sym[1] in "#b" else "")
    qual = sym[len(root):]
    base = midi_num(root + str(octave))
    return [base + i for i in CHORDS[qual]], base


# ===================================================================== 작곡
# 길이 단위: 8분음표. 한 마디 = 8.  chords: 마디별 코드 (반 마디 단위는 공백 대신 '/' 로 구분)
SONGS = {
    "bgm_chimney_ward": dict(
        title="굴뚝거리의 아침", bpm=100, loop=True, arp="up", drums="town",
        melody="""
            F5:3 E5:1 D5:2 C5:2 | A4:4 C5:4 | Bb4:3 A4:1 G4:2 A4:2 | F4:8 |
            D5:3 C5:1 Bb4:2 A4:2 | G4:2 A4:2 Bb4:2 D5:2 | C5:3 Bb4:1 A4:2 G4:2 | A4:4 C5:4 |
            F5:3 E5:1 D5:2 C5:2 | A4:4 C5:4 | D5:2 E5:2 F5:2 G5:2 | A5:6 G5:2 |
            F5:3 D5:1 C5:2 A4:2 | Bb4:2 D5:2 G4:2 Bb4:2 | A4:3 G4:1 F4:2 E4:2 | F4:8 |
        """,
        chords="F Dm Bb F Bb Gm C C7 F Dm Bb F Dm Gm C F",
    ),
    "bgm_sewer": dict(
        title="녹슨 지하수로", bpm=84, loop=True, arp="slow", drums="drip",
        melody="""
            D5:4 F5:2 E5:2 | D5:6 A4:2 | Bb4:4 A4:2 G4:2 | A4:8 |
            D5:4 F5:2 G5:2 | A5:6 G5:2 | F5:2 E5:2 D5:2 C#5:2 | D5:8 |
            r:4 A4:2 Bb4:2 | C5:4 Bb4:2 A4:2 | G4:4 F4:2 E4:2 | F4:4 E4:4 |
            D4:2 F4:2 A4:2 D5:2 | C5:4 Bb4:4 | A4:2 G4:2 F4:2 E4:2 | D4:8 |
        """,
        chords="Dm Dm Bb A Dm F Gm/A Dm Dm F C Dm Dm Bb Gm/A Dm",
    ),
    "bgm_battle": dict(
        title="녹슨 것들과의 전투", bpm=152, loop=True, arp="fast", drums="battle",
        melody="""
            A4:2 C5:2 E5:2 A5:2 | G5:3 F5:1 E5:4 | F5:2 E5:2 D5:2 C5:2 | B4:2 G#4:2 E4:4 |
            A4:2 C5:2 E5:2 A5:2 | B5:3 A5:1 G5:4 | F5:2 G5:2 A5:2 F5:2 | E5:8 |
            C6:4 B5:2 A5:2 | G5:4 E5:4 | F5:2 E5:2 D5:2 F5:2 | E5:6 r:2 |
            A5:4 G5:2 F5:2 | E5:2 D5:2 C5:2 E5:2 | D5:2 B4:2 G#4:2 B4:2 | A4:8 |
        """,
        chords="Am C Dm E Am G F E F C Dm E F C E Am",
    ),
    "bgm_victory": dict(
        title="승리의 팡파르", bpm=138, loop=False, arp="up", drums="fanfare",
        melody="""
            G4:1 C5:1 E5:1 G5:3 E5:1 G5:1 | A5:2 G5:2 F5:2 E5:2 | D5:2 E5:2 F5:2 D5:2 | C5:8 |
        """,
        chords="C F G C",
    ),
}


# ===================================================================== 신시사이저
def env(n, a=0.005, d=0.08, s=0.6, r=0.05):
    t = np.arange(n) / SR
    dur = n / SR
    e = np.where(t < a, t / max(a, 1e-6), 1.0)
    e = np.where((t >= a) & (t < a + d), 1 - (1 - s) * (t - a) / d, e)
    e = np.where(t >= a + d, s, e)
    rel = np.clip((dur - t) / r, 0, 1)
    return e * rel


def osc(kind, f, n, duty=0.5, vib=0.0):
    t = np.arange(n) / SR
    ph = f * t + (vib * np.sin(2 * np.pi * 5.5 * t) * np.clip(t - 0.15, 0, None) * 4 if vib else 0)
    ph = ph % 1.0
    if kind == "square":
        return np.where(ph < duty, 1.0, -1.0)
    if kind == "tri":
        return 4 * np.abs(ph - 0.5) - 1
    if kind == "saw":
        return 2 * ph - 1
    if kind == "sine":
        return np.sin(2 * np.pi * ph)
    raise ValueError(kind)


def noise(n, seed=0):
    return np.random.default_rng(seed).uniform(-1, 1, n)


def lowpass(x, k=0.2):
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += k * (v - acc)
        y[i] = acc
    return y


def drum(kind, seed=0):
    if kind == "kick":
        n = int(0.16 * SR)
        t = np.arange(n) / SR
        f = 120 * np.exp(-t * 25) + 45
        ph = np.cumsum(f) / SR
        return np.sin(2 * np.pi * ph) * np.exp(-t * 18) * 0.9
    if kind == "snare":
        n = int(0.14 * SR)
        t = np.arange(n) / SR
        return (noise(n, seed) * 0.6 + np.sin(2 * np.pi * 190 * t) * 0.4) * np.exp(-t * 22) * 0.55
    if kind == "hat":
        n = int(0.04 * SR)
        x = noise(n, seed)
        x = x - lowpass(x, 0.5)
        return x * np.exp(-np.arange(n) / SR * 90) * 0.35
    if kind == "drip":
        n = int(0.18 * SR)
        t = np.arange(n) / SR
        f = 900 + 700 * np.exp(-t * 40)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 30) * 0.25
    raise ValueError(kind)


def render_song(song):
    eighth = 60.0 / song["bpm"] / 2
    melody = parse(song["melody"])
    total_8 = sum(d for _, d in melody)
    n_total = int(total_8 * eighth * SR) + (int(1.2 * SR) if not song["loop"] else 0)
    mix = np.zeros(n_total)
    events = {"lead": [], "harm": [], "bass": [], "drum": []}

    def add(buf_start, sig, gain):
        end = min(n_total, buf_start + len(sig))
        if buf_start < end:
            mix[buf_start:end] += sig[: end - buf_start] * gain

    # 멜로디: 25% 사각파 + 약한 비브라토, 한 옥타브 위 12.5% 사각파로 살짝 겹침
    pos = 0.0
    for m, d in melody:
        if m is not None:
            n = int(d * eighth * SR)
            s = osc("square", freq(m), n, 0.25, vib=0.004 * freq(m)) * env(n, d=0.12, s=0.55, r=0.04)
            s += osc("square", freq(m + 12), n, 0.125) * env(n, d=0.05, s=0.2, r=0.03) * 0.25
            add(int(pos * eighth * SR), s, 0.20)
            events["lead"].append((pos, d, m))
        pos += d

    # 코드: 아르페지오(12.5% 사각파) + 베이스(삼각파)
    bars = song["chords"].split()
    for bi, bar in enumerate(bars):
        parts = bar.split("/")
        seg = 8 / len(parts)
        for pi, sym in enumerate(parts):
            start8 = bi * 8 + pi * seg
            notes, root = chord_notes(sym, 4)
            bass_root = root - 24
            # 베이스 패턴
            pattern = {"town": [(0, 2, 0), (2, 2, 7), (4, 2, 12), (6, 2, 7)],
                       "drip": [(0, 8, 0)],
                       "battle": [(i, 1, 0 if i % 2 == 0 else 12) for i in range(8)],
                       "fanfare": [(0, 4, 0), (4, 4, 7)]}[song["drums"]]
            for (o, d, iv) in pattern:
                if o >= seg:
                    continue
                d = min(d, seg - o)
                n = int(d * eighth * SR)
                s = osc("tri", freq(bass_root + iv), n) * env(n, d=0.1, s=0.8, r=0.03)
                add(int((start8 + o) * eighth * SR), s, 0.32)
                events["bass"].append((start8 + o, d, bass_root + iv))
            # 아르페지오
            step = {"up": 1, "slow": 2, "fast": 0.5}[song["arp"]]
            seq = notes + [notes[1] + 12] if song["arp"] != "slow" else notes + notes[1:2]
            k, t8 = 0, 0.0
            while t8 < seg - 1e-6:
                m = seq[k % len(seq)]
                n = int(step * eighth * SR)
                s = osc("square", freq(m), n, 0.125) * env(n, d=0.06, s=0.3, r=0.02)
                add(int((start8 + t8) * eighth * SR), s, 0.09)
                events["harm"].append((start8 + t8, step, m))
                k += 1
                t8 += step

    # 드럼
    style = song["drums"]
    for b in range(len(bars)):
        for e8 in range(8):
            t = int((b * 8 + e8) * eighth * SR)
            hits = []
            if style == "town":
                if e8 in (0, 4):
                    hits.append(("kick", 0.8))
                if e8 % 2 == 1:
                    hits.append(("hat", 0.6))
            elif style == "battle":
                if e8 in (0, 3, 4):
                    hits.append(("kick", 1.0))
                if e8 in (2, 6):
                    hits.append(("snare", 1.0))
                hits.append(("hat", 0.5))
            elif style == "drip":
                if (b * 8 + e8) % 11 == 3:
                    hits.append(("drip", 1.0))
                if e8 == 0 and b % 2 == 0:
                    hits.append(("kick", 0.45))
            elif style == "fanfare":
                if e8 in (0, 3, 6) and b < 3:
                    hits.append(("snare", 0.7))
                if e8 == 0:
                    hits.append(("kick", 1.0))
            for kind, g in hits:
                add(t, drum(kind, seed=b * 8 + e8), g * 0.5)
                events["drum"].append((b * 8 + e8, 1, {"kick": 36, "snare": 38, "hat": 42, "drip": 76}[kind]))

    # 마스터: 살짝 저역 통과 + 노멀라이즈
    mix = np.tanh(mix * 1.4) * 0.85
    return mix, events, eighth


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    data = (x * 32767).astype("<i2").tobytes()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data)


# ===================================================================== MIDI 내보내기
def vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def write_midi(path, song, events):
    tpq = 480
    t8 = tpq // 2

    def track(evs, ch, program, name):
        msgs = []
        for start, dur, m in evs:
            msgs.append((int(start * t8), 1, bytes([0x90 | ch, m, 96])))
            msgs.append((int((start + dur) * t8) - 1, 0, bytes([0x80 | ch, m, 0])))
        msgs.sort(key=lambda e: (e[0], e[1]))
        body = b"\x00\xff\x03" + vlq(len(name.encode())) + name.encode()
        if ch != 9:
            body += b"\x00" + bytes([0xC0 | ch, program])
        last = 0
        for tick, _, data in msgs:
            body += vlq(max(0, tick - last)) + data
            last = max(last, tick)
        body += b"\x00\xff\x2f\x00"
        return b"MTrk" + struct.pack(">I", len(body)) + body

    tempo = int(60_000_000 / song["bpm"])
    conductor = b"\x00\xff\x51\x03" + tempo.to_bytes(3, "big") + b"\x00\xff\x2f\x00"
    tracks = [b"MTrk" + struct.pack(">I", len(conductor)) + conductor,
              track(events["lead"], 0, 80, "Lead"),
              track(events["harm"], 1, 81, "Arp"),
              track(events["bass"], 2, 38, "Bass"),
              track(events["drum"], 9, 0, "Drums")]
    with open(path, "wb") as f:
        f.write(b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), tpq) + b"".join(tracks))


# ===================================================================== 효과음
def sfx_all():
    def tone_seq(notes, dur, kind="square", duty=0.5, gain=0.5):
        parts = []
        for m in notes:
            n = int(dur * SR)
            parts.append(osc(kind, freq(m), n, duty) * env(n, d=0.03, s=0.6, r=0.02))
        return np.concatenate(parts) * gain

    def sweep(f0, f1, dur, kind="square", gain=0.5):
        n = int(dur * SR)
        f = np.linspace(f0, f1, n)
        ph = np.cumsum(f) / SR % 1.0
        sig = {"square": np.where(ph < 0.5, 1.0, -1.0), "sine": np.sin(2 * np.pi * ph),
               "tri": 4 * np.abs(ph - 0.5) - 1}[kind]
        return sig * env(n, a=0.002, d=dur * 0.5, s=0.5, r=dur * 0.3) * gain

    def noise_burst(dur, k=0.5, decay=20, gain=0.6, seed=1):
        n = int(dur * SR)
        x = noise(n, seed)
        if k < 1:
            x = lowpass(x, k)
        return x * np.exp(-np.arange(n) / SR * decay) * gain

    s = {}
    s["sfx_cursor"] = tone_seq([84], 0.035, duty=0.25, gain=0.35)
    s["sfx_confirm"] = tone_seq([79, 86], 0.05, duty=0.25, gain=0.4)
    s["sfx_cancel"] = tone_seq([74, 67], 0.05, duty=0.5, gain=0.35)
    s["sfx_text"] = tone_seq([91], 0.015, duty=0.25, gain=0.12)
    s["sfx_menu"] = tone_seq([72, 76, 79], 0.04, duty=0.25, gain=0.35)
    s["sfx_hit"] = noise_burst(0.12, 0.6, 30, 0.7) + np.concatenate(
        [sweep(220, 60, 0.12, "square", 0.35), np.zeros(0)])[: int(0.12 * SR)]
    s["sfx_slash"] = noise_burst(0.18, 0.9, 16, 0.4) * np.linspace(0.2, 1, int(0.18 * SR)) ** 0.5
    sl = s["sfx_slash"]
    s["sfx_slash"] = sl + sweep(1400, 300, 0.18, "sine", 0.2)[: len(sl)]
    s["sfx_steam"] = noise_burst(0.5, 0.7, 5, 0.45, seed=3)
    s["sfx_fire"] = noise_burst(0.45, 0.12, 6, 0.9, seed=4) + sweep(110, 50, 0.45, "tri", 0.3)
    s["sfx_shot"] = np.concatenate([noise_burst(0.04, 1.0, 60, 0.9, seed=5),
                                    noise_burst(0.2, 0.15, 14, 0.6, seed=6)])
    s["sfx_magic"] = tone_seq([84, 88, 91, 96, 91, 96], 0.045, "sine", gain=0.4)
    s["sfx_heal"] = tone_seq([72, 76, 79, 84, 88], 0.07, "tri", gain=0.45)
    s["sfx_wave"] = sweep(300, 1200, 0.35, "sine", 0.35) + sweep(310, 1210, 0.35, "sine", 0.25)
    s["sfx_buff"] = tone_seq([67, 72, 79], 0.06, "square", 0.125, 0.35)
    s["sfx_enemy_die"] = sweep(600, 40, 0.5, "square", 0.35) + noise_burst(0.5, 0.3, 6, 0.4)
    s["sfx_encounter"] = np.concatenate([sweep(200, 1600, 0.25, "square", 0.3), sweep(1600, 200, 0.25, "square", 0.3)])
    s["sfx_levelup"] = np.concatenate([tone_seq([72, 76, 79], 0.07, duty=0.25, gain=0.45),
                                       tone_seq([84], 0.35, duty=0.25, gain=0.45)])
    s["sfx_guard"] = tone_seq([55, 60], 0.06, "square", 0.5, 0.35)
    s["sfx_escape"] = sweep(800, 2000, 0.3, "tri", 0.35)
    s["sfx_step"] = noise_burst(0.03, 0.4, 80, 0.15)
    s["sfx_door"] = tone_seq([60, 67], 0.08, "tri", gain=0.4)
    return s


if __name__ == "__main__":
    os.makedirs(BGM, exist_ok=True)
    os.makedirs(SFX, exist_ok=True)
    for sid, song in SONGS.items():
        audio, events, eighth = render_song(song)
        write_wav(os.path.join(BGM, sid + ".wav"), audio)
        write_midi(os.path.join(BGM, sid + ".mid"), song, events)
        print(f"  bgm/{sid}.wav + .mid  ({len(audio) / SR:.1f}초, {song['title']})")
    for sid, x in sfx_all().items():
        write_wav(os.path.join(SFX, sid + ".wav"), x / max(1.0, np.abs(x).max() / 0.9))
        print(f"  sfx/{sid}.wav")
    print("오디오 생성 완료")
