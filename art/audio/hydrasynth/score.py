#!/usr/bin/env python3
"""A first piece for each zone, on existing Hydrasynth patches: three parts each, recorded one at a time and laid over the zone's
drum line (art/audio/drums). Keys, tempos and the motif come from .claude/skills/sound-design/references/ride-bible.md: two
heartbeats a tritone apart, each dub a sixteenth after its lub. These are first drafts, to be heard and argued with.

    python score.py <outdir>     # writes <zone>_<part>.json and parts.json

Patches are (bank, slot as listed): banks A, B, C, D are 0, 1, 2, 3. Nothing's saved to the synth.
"""
import json
import os
import random
import sys

E1, F1, G1, A1, Bb1, B1 = 28, 29, 31, 33, 34, 35
Db1 = 25
Ab1 = 32
E2, F2, G2, A2, Bb2, B2 = 40, 41, 43, 45, 46, 47
Db2, Ab2 = 37, 44
C3, Db3, D3, E3, F3, Fs3, G3, Ab3, A3, Bb3, B3 = 48, 49, 50, 52, 53, 54, 55, 56, 57, 58, 59
C4, Cs4, D4, E4, F4, Fs4, Gb4, G4, Ab4, A4, Bb4, B4 = 60, 61, 62, 64, 65, 66, 66, 67, 68, 69, 70, 71
C5, Cs5, Db5, D5, E5, F5, Fs5, Gb5, G5, Gs5, A5, Bb5, B5 = 72, 73, 73, 74, 76, 77, 78, 78, 79, 80, 81, 82, 83
Cs6, D6 = 85, 86


class Part:
    def __init__(self, zone, name, patch, role, seed, xfade=0.03):
        self.zone, self.name, self.patch, self.role, self.xfade = zone, name, patch, role, xfade
        self.ev = []
        self.r = random.Random(seed)

    def n(self, t, note, vel, dur, slop=0.008, spread=5):
        t = max(0.0, t + self.r.uniform(-slop, slop))
        self.ev.append({"t": round(t, 4), "synth": "hydrasynth", "channel": 1, "note": note, "vel": max(1, min(127, round(vel + self.r.gauss(0, spread)))), "dur": dur})

    def chord(self, t, notes, vel, dur, roll=0.012):
        for i, note in enumerate(notes):
            self.n(t + i * roll, note, vel - i * 3, dur)

    def mod(self, t, a, b, beats):
        """The mod wheel, riding: whatever the patch has on it."""
        self.ev.append({"t": t, "synth": "hydrasynth", "channel": 1, "ramp": 1, "table": "hydrasynth", "from": a, "to": b, "dur": beats})

    def perf(self, bpm, beats):
        bank, slot = self.patch
        head = {"sec": -1.5, "synth": "hydrasynth", "channel": 1, "program": slot - 1, "bank": bank}
        events = [head]
        for p in (0, 1):
            for ev in self.ev:
                events.append({**ev, "t": round(ev["t"] + p * beats, 4)})
        return {"bpm": bpm, "beats": beats * 2, "pattern_beats": beats, "events": events, "part": self.name, "zone": self.zone, "role": self.role, "xfade": self.xfade, "patch": self.patch}


def green():
    """E Phrygian, 80: a church in the rain with a machine in the crypt. Open fifths; F the one wrong note; the bell tolls the motif."""
    bpm, bars = 80, 8
    bed = Part("green", "bed", (3, 52), "bed", 11, 0.4)  # Washed Organ
    bed.chord(0, [E2, B2, E3, B3], 84, 15.5)
    bed.n(8.0, F4, 40, 7.5)
    bed.chord(16, [E2, B2, E3, G3, B3], 78, 15.5)
    bed.n(24.0, F4, 46, 4.0)
    bed.n(28.0, E4, 40, 3.5)
    bed.mod(0, 0, 50, 16)
    bed.mod(16, 50, 0, 16)
    bell = Part("green", "bell", (0, 12), "lead", 12, 0.3)  # Tubular
    for bar, (a, b), v in ((0, (E4, F4), 92), (2, (Bb4, B4), 84), (4, (E4, F4), 84), (6, (Bb4, B4), 96)):
        bell.n(bar * 4, a, v, 2.5)
        bell.n(bar * 4 + 0.25, b, v * 0.6, 2.5)
    bass = Part("green", "bass", (2, 31), "bass", 13)  # DeepBass
    for bar in range(bars):
        bass.n(bar * 4, E1, 104 if bar % 2 == 0 else 92, 2.6, 0.012)
        if bar % 4 == 3:
            bass.n(bar * 4 + 3, F1, 86, 0.95, 0.012)
        elif bar % 2 == 1:
            bass.n(bar * 4 + 2.75, E1, 66, 0.4, 0.012)
    return bpm, bars * 4, [bed, bell, bass]


def chrome():
    """G Lydian, 95: beautiful and slightly too clean. I to II over a G pedal; glass arpeggio, the motif widened on top."""
    bpm, bars = 95, 8
    pad = Part("chrome", "pad", (2, 82), "bed", 21, 0.3)  # Poly6 Pad
    for bar, notes in ((0, [G2, D3, G3, B3, D4]), (2, [G2, A3, Cs4, E4, A4]), (4, [G2, D3, G3, B3, Fs4]), (6, [G2, A3, Cs4, E4, Cs5])):
        pad.chord(bar * 4, notes, 78, 7.7)
    pad.mod(0, 10, 70, 28)
    pad.mod(28, 70, 10, 4)
    glass = Part("chrome", "glass", (1, 16), "lead", 22)  # Glocken Tams
    runs = {0: [G4, B4, D5, Fs5], 2: [A4, Cs5, E5, G5], 4: [G4, B4, D5, A5], 6: [A4, Cs5, E5, A5]}
    for bar in range(bars):
        run = runs[bar - bar % 2]
        for s in range(16):
            note = run[(s * 3 + (s // 8)) % 4]
            v = 72 if s % 4 == 0 else 48 if s % 2 == 0 else 34
            glass.n(bar * 4 + s / 4, note, v + bar * 2, 0.22, 0.0, 4)
    # The motif, up top: G A, C# D.
    for bar, (a, b) in ((1, (G5, A5)), (3, (Cs6, D6)), (5, (G5, A5)), (7, (Cs6, D6))):
        glass.n(bar * 4 + 3, a, 104, 0.5, 0.0, 2)
        glass.n(bar * 4 + 3.25, b, 86, 0.7, 0.0, 2)
    bass = Part("chrome", "bass", (2, 22), "bass", 23)  # Bob Bass
    for bar in range(bars):
        b = bar * 4
        for s, note, v in ((0, G1, 104), (0.75, G1, 62), (1.5, G2, 78), (2, G1, 96), (2.75, G1, 60), (3.5, G2, 84)):
            bass.n(b + s, note, v, 0.42, 0.0, 3)
    return bpm, bars * 4, [pad, glass, bass]


def hive():
    """Db, Phrygian dominant, 110: an angel choir inside a body. The chord gathers its strange notes, the voice sings the motif, tar bubbles."""
    bpm, bars = 110, 8
    choir = Part("hive", "choir", (2, 87), "bed", 31, 0.5)  # DAMNED CHOIR
    choir.chord(0, [Db2, Ab2, Db3, F3], 82, 7.7, 0.03)
    choir.chord(8, [Db2, Ab2, F3, Ab3, B3], 80, 7.7, 0.03)
    choir.chord(16, [Db2, Ab2, F3, B3, D4], 84, 7.7, 0.03)
    choir.chord(24, [Db2, Ab2, Ab3, D4, G4], 88, 7.7, 0.03)
    choir.mod(0, 0, 90, 24)
    choir.mod(24, 90, 0, 8)
    voice = Part("hive", "voice", (3, 79), "lead", 32, 0.4)  # VOCAL SHADERS
    for bar, (a, b), dur in ((1, (Db5, D5), 5.0), (3, (F5, Gb5), 5.0), (5, (Db5, D5), 5.0), (7, (F5, Gb5), 3.0)):
        voice.n(bar * 4, a, 74, 0.5, 0.02)
        voice.n(bar * 4 + 0.25, b, 60, dur, 0.02)
    tar = Part("hive", "tar", (1, 104), "bass", 33, 0.2)  # SwampLegend
    r = random.Random(7)
    hits = [(b * 4 + s / 4) for b in range(bars) for s in (0, 3, 6, 11, 14) if r.random() > 0.35]
    for t in hits:
        tar.n(t, r.choice([Db1, Db1, Db2, Ab1]), 44 + r.random() * 44, 0.6, 0.02, 6)
    return bpm, bars * 4, [choir, voice, tar]


def desert():
    """Bb, whole tone, 125 in 7/8 (4 + 3): machines dying in the heat. A limping pedal, a mirage line, the motif's first pair breaking off."""
    bpm, bars, bar = 125, 8, 3.5
    pedal = Part("desert", "pedal", (3, 14), "bass", 41)  # Dirty Machine
    for b in range(bars):
        t = b * bar
        pedal.chord(t, [Bb1, F2], 108, 1.7, 0.0)
        pedal.chord(t + 2.0, [Bb1, F2], 88, 1.2, 0.0)
        if b % 2 == 1:
            pedal.n(t + 3.25, E2, 70, 0.22)
    pedal.mod(0, 0, 80, 14)
    pedal.mod(14, 80, 0, 14)
    # Whole tone: Bb C D E F# G#. Nothing to lean on; E keeps turning up on top.
    mirage = Part("desert", "mirage", (3, 98), "lead", 42, 0.3)  # VHS Warbler
    line = [(0, Bb3, 3.0), (3.5, D4, 2.0), (5.5, E4, 1.5), (7, Fs4, 3.0), (10.5, E4, 3.5), (14, Gs5 - 12, 2.0), (16, Fs4, 1.5), (17.5, E4, 3.5), (21, D4, 2.0), (23, C4, 1.5), (24.5, E4, 3.0)]
    for t, note, dur in line:
        mirage.n(t, note, 68, dur, 0.03, 8)
    data = Part("desert", "data", (3, 114), "top", 43)  # Gl'tc# Arp$
    for b, cut in ((1, False), (3, True), (5, False), (6, True), (7, False)):
        t = b * bar + 3.0
        data.n(t, Bb4, 92, 0.2, 0.0, 6)
        if not cut:  # (Sometimes the dub never comes: it drops out mid-word.)
            data.n(t + 0.25, B4, 70, 0.22, 0.0, 6)
    return bpm, int(bars * bar), [pedal, mirage, data]


def core():
    """E, 140: it wakes up. Stacked, pulsing polychords on E F then Bb B; a driving low E; the motif at full force."""
    bpm, bars = 140, 8
    brass = Part("core", "brass", (1, 58), "bed", 51, 0.05)  # DRAMABRASS
    chords = {0: [E3, G3, B3, F4, Ab4, C5], 2: [Bb3, D4, F4, B4, D5, Fs5], 4: [E3, G3, B3, F4, Ab4, C5], 6: [Bb3, D4, F4, B4, D5, Fs5]}
    for b in range(bars):
        notes = chords[b - b % 2]
        for e in range(8):
            if e % 8 in (0, 3, 6) or (b % 2 == 1 and e in (1, 4, 7)):
                brass.chord(b * 4 + e / 2, notes, (104 if e == 0 else 82) + b, 0.34, 0.0)
    brass.mod(24, 0, 100, 8)
    bass = Part("core", "bass", (2, 33), "bass", 52)  # Dragon Bass
    for b in range(bars):
        low = E1 if b // 2 % 2 == 0 else Bb1
        for s in range(16):
            if s % 4 == 0 or s in (3, 6, 10, 14):
                bass.n(b * 4 + s / 4, low + (1 if s == 14 else 0), 110 if s % 8 == 0 else 80, 0.2, 0.0, 4)
    lead = Part("core", "lead", (3, 102), "lead", 53, 0.1)  # DOOM 4
    for bar, (a, b), v in ((0, (E4, F4), 100), (2, (Bb4, B4), 104), (4, (E4, F4), 104), (6, (Bb4, B4), 112)):
        lead.n(bar * 4, a, v, 0.24, 0.0, 2)
        lead.n(bar * 4 + 0.25, b, v * 0.8, 3.4, 0.0, 2)
    return bpm, bars * 4, [brass, bass, lead]


ZONES = [green, chrome, hive, desert, core]

if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    index = []
    for fn in ZONES:
        bpm, beats, parts = fn()
        for p in parts:
            name = f"{p.zone}_{p.name}"
            with open(os.path.join(out, name + ".json"), "w") as f:
                json.dump(p.perf(bpm, beats), f)
            index.append(name)
    with open(os.path.join(out, "parts.json"), "w") as f:
        json.dump(index, f)
    print(len(index), "parts")
