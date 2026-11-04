#!/usr/bin/env python3
"""The zones' drum lines (.claude/skills/sound-design/references/ride-bible.md), as performances for the Syntakt.

    python lines.py <outdir>     # writes <zone>.json for capture.py, each pattern played twice

Written to the kit on the Syntakt now, measured by note. Digital: 1 long sub, 2 kick, 3 clap, 4 closed hat, 5 low tom, 6 high
perc, 7 noisy perc, 8 tone. Analog: 9 kick, 10 snare, 11 tom, 12 cymbal. A different kit means different sounds in these roles.

It's meant to be played, not stepped: velocities move with the phrase and from hit to hit, with ghost notes and accents, and
the time's loose where the zone wants it. FX are moved live over CC: sends thrown on single hits, hats opening and closing,
the FX track's filter and drive riding the phrase. That edits the kit's working copy on the machine: reload the kit to get
it back (and don't save over it, if that matters). Both passes are identical; the loop's cut from the second.

Written with the drummer skill (.claude/skills/drummer), which holds the tools and the FX's safe ceilings.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".claude", "skills", "drummer", "scripts"))
from drumline import DECAY, DELAY_FEEDBACK, DELAY_MIX, DELAY_SEND, FILTER, FX, FX_DRIVE, REVERB_DECAY, REVERB_MIX, REVERB_SEND, Line, euclid  # noqa: E402

SUB, KICK, CLAP, HAT, TOM, PERC, NOISE, TONE, AKICK, SNARE, ATOM, CYM = range(1, 13)

def green():
    """80, half-time: a slow walk over a fast bike. Everything laid back, the snare late, in a big cold room; hats loose, opening now and then."""
    L = Line(1)
    L.start(FX, REVERB_DECAY, 88)
    L.start(FX, REVERB_MIX, 76)
    L.start(FX, DELAY_FEEDBACK, 56)
    L.start(FX, DELAY_MIX, 60)
    L.start(FX, FX_DRIVE, 25)
    L.start(HAT, REVERB_SEND, 24)
    L.start(HAT, DELAY_SEND, 0)
    L.start(HAT, DECAY, 40)
    L.start(HAT, FILTER, 95)
    L.start(SNARE, REVERB_SEND, 95)
    L.start(SNARE, DELAY_SEND, 0)
    L.start(PERC, DELAY_SEND, 0)
    L.start(KICK, REVERB_SEND, 8)
    L.start(AKICK, REVERB_SEND, 8)
    L.ramp(0, HAT, FILTER, 95, 124, 16)
    L.ramp(16, HAT, FILTER, 124, 95, 16)
    for bar in range(8):
        b = bar * 4
        lift = (0, -5, 2, -3, 3, -4, 6, 8)[bar]
        L.hit(b, KICK, 118 + lift, spread=3)
        L.hit(b + 0.004, AKICK, 88 + lift, spread=4)
        L.hit(b + 2 + 0.012, SNARE, 110 + lift, 0.004, 4)
        # A ghost before the backbeat, not every bar.
        if bar % 2 == 1:
            L.hit(b + 1.75, SNARE, 34, 0.008)
        for s, v in ((0, 66), (1, 44), (1.5, 60), (2.5, 40), (3, 54), (3.5, 48)):
            if s == 2.5 and bar % 2 == 0:
                continue
            L.hit(b + s, HAT, v + lift, 0.014, 8)
        # Now and then one left open.
        if bar in (1, 5):
            L.cc(b + 3.45, HAT, DECAY, 92)
            L.cc(b + 3.9, HAT, DECAY, 40)
        if bar % 2 == 1:
            L.hit(b + 2.75, AKICK, 78, 0.006)
        if bar % 2 == 0:
            L.hit(b + 1.75, NOISE, 34, 0.01)
    # A far tom thrown into the delay, and a fill to turn round on.
    L.throw(3 * 4 + 3.5, PERC, DELAY_SEND, 88, 0)
    L.hit(3 * 4 + 3.5, PERC, 70)
    L.hit(7 * 4 + 3.5, CYM, 58)
    b = 7 * 4
    L.throw(b + 3.75, SNARE, DELAY_SEND, 84, 0, 0.2)
    L.hit(b + 3.0, TOM, 92)
    for s, v in ((3.25, 54), (3.5, 76), (3.75, 100)):
        L.hit(b + s, SNARE, v, 0.004, 3)
    return L.perf(80, 32)


def chrome():
    """95, four on the floor, glossy and on the grid, too clean: but the hats breathe, and the claps go up into the delay."""
    L = Line(2)
    L.start(FX, REVERB_DECAY, 70)
    L.start(FX, REVERB_MIX, 66)
    L.start(FX, DELAY_FEEDBACK, 58)
    L.start(FX, DELAY_MIX, 62)
    L.start(FX, FX_DRIVE, 8)
    L.start(CLAP, REVERB_SEND, 60)
    L.start(CLAP, DELAY_SEND, 0)
    L.start(HAT, REVERB_SEND, 14)
    L.start(HAT, DELAY_SEND, 16)
    L.start(HAT, DECAY, 34)
    L.start(HAT, FILTER, 100)
    L.start(PERC, DELAY_SEND, 48)
    L.start(KICK, REVERB_SEND, 0)
    L.ramp(0, HAT, FILTER, 100, 127, 28)
    L.ramp(28, HAT, FILTER, 127, 100, 4)
    for bar in range(8):
        b = bar * 4
        build = bar * 2
        for q in range(4):
            L.hit(b + q, KICK, (118 if q % 2 == 0 else 110) + build // 2, spread=2)
            L.hit(b + q, HAT, 50 + build, spread=4)
            L.hit(b + q + 0.25, HAT, 30 + build, spread=5)
            L.hit(b + q + 0.5, HAT, 82 + build, spread=4)
            L.hit(b + q + 0.75, HAT, 40 + build, spread=6)
        L.hit(b + 1, CLAP, 102 + build, spread=3)
        L.hit(b + 3, CLAP, 106 + build, spread=3)
        if bar % 2 == 1:
            L.hit(b + 0.5, CYM, 44)
            L.hit(b + 2.5, CYM, 48)
        for s in (3, 6, 11, 14):
            L.hit(b + s / 4, PERC, 40 + build, spread=5)
    L.throw(3 * 4 + 3, CLAP, DELAY_SEND, 88, 0, 0.4)
    b = 7 * 4
    L.throw(b + 3.75, CLAP, DELAY_SEND, 90, 0, 0.2)
    for i in range(4):
        L.hit(b + 3 + i / 4, CLAP, 50 + 20 * i, spread=2)
    return L.perf(95, 32)


def hive():
    """The grid at 110: no backbeat. Insects and coral knocks on Euclidean patterns, in a wet, enormous space that opens and closes; the heart's its own."""
    L = Line(3)
    L.start(FX, REVERB_DECAY, 92)
    L.start(FX, REVERB_MIX, 80)
    L.start(FX, DELAY_FEEDBACK, 60)
    L.start(FX, DELAY_MIX, 64)
    L.start(FX, FX_DRIVE, 0)
    L.start(NOISE, REVERB_SEND, 80)
    L.start(NOISE, DELAY_SEND, 40)
    L.start(PERC, REVERB_SEND, 80)
    L.start(PERC, DELAY_SEND, 56)
    L.start(TONE, REVERB_SEND, 88)
    L.start(HAT, DECAY, 14)
    L.start(HAT, FILTER, 110)
    L.start(HAT, REVERB_SEND, 30)
    L.ramp(0, HAT, FILTER, 110, 70, 16)
    L.ramp(16, HAT, FILTER, 70, 110, 16)
    k5, k7, k3 = euclid(5, 16), euclid(7, 16, 2), euclid(3, 16, 5)
    for bar in range(8):
        b = bar * 4
        swell = (0, 4, 8, 12, 16, 12, 8, 4)[bar]
        for s in range(16):
            t = b + s / 4
            if k5[s]:
                L.hit(t, NOISE, 66 + swell, 0.008, 10)
            if k7[s]:
                L.hit(t, PERC, 30 + swell, 0.008, 7)
            if k3[s] and bar % 2 == 1:
                L.hit(t, TONE, 44 + swell, 0.008, 6)
            # Insects: skittering, some missing.
            if L.r.random() > 0.14:
                L.hit(t, HAT, 18 + 9 * (s % 4 == 2), 0.006, 5)
    return L.perf(110, 32)


def desert():
    """125 in 7/8, 4 + 3: kick on 1 and 5, it limps. Dry, driven hard; two fan ticks every 7 and every 5 sixteenths; the machine sticking."""
    L = Line(4)
    L.start(FX, REVERB_MIX, 0)
    L.start(FX, DELAY_MIX, 50)
    L.start(FX, DELAY_FEEDBACK, 30)
    L.start(FX, FX_DRIVE, 92)
    L.start(SNARE, REVERB_SEND, 0)
    L.start(SNARE, DELAY_SEND, 0)
    L.start(HAT, REVERB_SEND, 0)
    L.start(HAT, DECAY, 22)
    L.start(PERC, REVERB_SEND, 0)
    L.start(TONE, REVERB_SEND, 0)
    L.start(KICK, REVERB_SEND, 0)
    L.start(AKICK, REVERB_SEND, 0)
    bar_beats = 3.5
    # The drive rides up and back, a gust.
    L.ramp(0, FX, FX_DRIVE, 92, 118, 14)
    L.ramp(14, FX, FX_DRIVE, 118, 92, 14)
    for bar in range(8):
        b = bar * bar_beats
        L.hit(b, KICK, 122, spread=3)
        L.hit(b + 0.006, AKICK, 96, spread=4)
        L.hit(b + 2.0, KICK, 104, spread=6)
        L.hit(b + 1.0, ATOM, 86, 0.008, 8)
        L.hit(b + 3.0, SNARE, 108, 0.008, 6)
        if bar % 2 == 1:
            L.hit(b + 2.75, AKICK, 72, 0.006)
        if bar % 4 == 2:
            L.hit(b + 2.5, SNARE, 40, 0.006)
        for e in range(7):
            L.hit(b + e / 2, HAT, 52 if e in (0, 4) else 28, 0.01, 8)
    for bar, track in ((3, SNARE), (7, NOISE)):
        b = bar * bar_beats + 3.0
        L.throw(b + 0.375, track, DELAY_SEND, 90, 0, 0.1)
        for i in range(4):
            L.hit(b + i / 8, track, 62 + 16 * i, spread=3)
    n = int(8 * bar_beats * 4)
    for s in range(n):
        if s % 7 == 0:
            L.hit(s / 4, TONE, 38, 0.006, 8)
        if s % 5 == 0:
            L.hit(s / 4, PERC, 28, 0.006, 7)
    return L.perf(125, 8 * bar_beats)


def core():
    """140, the servers: a hard driven pulse pushing ahead of the beat, the data as Euclidean 5, 7 and 11 over 16. It's woken up."""
    L = Line(5)
    L.start(FX, REVERB_DECAY, 48)
    L.start(FX, REVERB_MIX, 60)
    L.start(FX, DELAY_FEEDBACK, 56)
    L.start(FX, DELAY_MIX, 62)
    L.start(FX, FX_DRIVE, 74)
    L.start(SNARE, REVERB_SEND, 56)
    L.start(SNARE, DELAY_SEND, 0)
    L.start(CLAP, REVERB_SEND, 30)
    L.start(HAT, REVERB_SEND, 6)
    L.start(HAT, DECAY, 20)
    L.start(HAT, FILTER, 84)
    L.start(PERC, DELAY_SEND, 58)
    L.start(KICK, REVERB_SEND, 0)
    L.start(AKICK, REVERB_SEND, 0)
    L.ramp(0, HAT, FILTER, 84, 127, 24)
    L.ramp(24, HAT, FILTER, 127, 84, 8)
    L.ramp(24, FX, FX_DRIVE, 74, 112, 8)
    k5, k7, k11 = euclid(5, 16), euclid(7, 16, 3), euclid(11, 16, 1)
    for bar in range(8):
        b = bar * 4
        build = bar
        for q in range(4):
            L.hit(b + q, KICK, 122 + build // 2, spread=2)
            L.hit(b + q + 0.002, AKICK, 94 + build, spread=3)
            L.hit(b + q + 0.75, AKICK, 52 + build, 0.006, 8)
        L.hit(b + 1, SNARE, 112 + build, 0.004, 3)
        L.hit(b + 1.002, CLAP, 76 + build, spread=4)
        L.hit(b + 3, SNARE, 116 + build, 0.004, 3)
        L.hit(b + 3.002, CLAP, 80 + build, spread=4)
        for s in range(16):
            t = b + s / 4
            if k5[s]:
                L.hit(t, HAT, 76 + build * 2, spread=6)
            if k7[s]:
                L.hit(t, PERC, 36 + build, spread=6)
            if k11[s]:
                L.hit(t, HAT, 28 + build, spread=7)
            if bar >= 4 and s % 8 == 3:
                L.hit(t, NOISE, 58, 0.004, 8)
        if bar % 4 == 3:
            L.hit(b + 3.5, CYM, 70)
    L.throw(3 * 4 + 3, SNARE, DELAY_SEND, 88, 0, 0.3)
    b = 7 * 4
    for i in range(8):
        L.hit(b + 2 + i / 4, SNARE if i % 2 else TOM, 54 + 9 * i, spread=3)
    return L.perf(140, 32)


def heart():
    """The heart, resting at 73.3 a minute: lub, and 0.28 of a period later the dub at 0.6 of its strength. For hearing: in the game it's one-shots."""
    L = Line(6)
    L.start(AKICK, REVERB_SEND, 12)
    L.start(TOM, REVERB_SEND, 12)
    L.start(FX, REVERB_DECAY, 60)
    L.start(FX, REVERB_MIX, 60)
    L.start(FX, FX_DRIVE, 10)
    for i in range(8):
        L.hit(i, AKICK, 110, spread=4)
        L.hit(i + 0.28, TOM, 66, spread=4)
    return L.perf(73.3, 8)


ZONES = {"green": green, "chrome": chrome, "hive": hive, "desert": desert, "core": core, "heart": heart}

if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for name, fn in ZONES.items():
        with open(os.path.join(out, name + ".json"), "w") as f:
            json.dump(fn(), f)
        print(name, "written")
