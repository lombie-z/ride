#!/usr/bin/env python3
"""A drum line, as a person might play it: for the Syntakt, one hit at a time, with its FX moved live. See ../SKILL.md.

Builds a performance for sound-design's perform.py and capture.py (and ../scripts/take.py). Same seed, same line: its wandering
is random but repeatable, and both passes of a take are identical, so the loop can be cut from the second.
"""
import random

FX = 13  # FX CONTROL CH: 13 on the machine this was written on. Check it (MIDI CONFIG > CHANNELS)
# Per track.
DECAY, FILTER, DELAY_SEND, REVERB_SEND = 81, 74, 84, 85
# On the FX channel.
FX_DRIVE, FX_FILTER = 15, 70
DELAY_FEEDBACK, DELAY_MIX, REVERB_DECAY, REVERB_MIX = 24, 28, 30, 92

# Past these (delay feedback 70, send 105, reverb decay 112, mix 95) the Syntakt's FX blew up into full-scale static, on a hit that
# had been fine a pass earlier, and stayed stuck until it was power cycled. So nothing here goes near them.
CEILING_FX = {DELAY_FEEDBACK: 62, DELAY_MIX: 70, REVERB_DECAY: 92, REVERB_MIX: 80}
CEILING_THROW = 90


def _safe(track, control, value):
    """Refuses a value past the FX ceilings: that takes real speakers to full-scale noise."""
    if track == FX and value > CEILING_FX.get(control, 127):
        raise ValueError(f"FX control {control} at {value}: over its ceiling, {CEILING_FX[control]}. See the note on CEILING_FX.")
    if track != FX and control == DELAY_SEND and value > CEILING_THROW:
        raise ValueError(f"delay send at {value} on track {track}: over its ceiling, {CEILING_THROW}.")


def euclid(pulses, steps, rot=0):
    out = [(i * pulses) % steps < pulses for i in range(steps)]
    return [out[(i - rot) % steps] for i in range(steps)]


class Line:
    def __init__(self, seed, push=0.0):
        self.hits = []
        self.ccs = []
        self.setup = []
        self.r = random.Random(seed)
        self.push = push

    def hit(self, t, track, vel, drift=0.0, spread=6):
        """At beat t, on a track, with a velocity that wanders by about `spread` and up to `drift` beats of slop in time."""
        v = vel + self.r.gauss(0, spread)
        t = max(0.0, t + self.push + self.r.uniform(-drift, drift))
        self.hits.append((t, track, max(1, min(127, round(v)))))

    def cc(self, t, track, control, value):
        _safe(track, control, value)
        self.ccs.append({"t": round(t, 5), "synth": "syntakt", "channel": track, "cc": control, "table": "syntakt", "value": int(value)})

    def ramp(self, t, track, control, a, b, beats):
        _safe(track, control, max(a, b))
        self.ccs.append({"t": round(t, 5), "synth": "syntakt", "channel": track, "ramp": control, "table": "syntakt", "from": a, "to": b, "dur": beats})

    def throw(self, t, track, send, amount, back, length=0.5):
        """A send opened just for one hit, and shut again: the way you'd reach over and throw one into the delay."""
        self.cc(t - 0.03, track, send, amount)
        self.cc(t + length, track, send, back)

    def start(self, track, control, value):
        """Where a control starts: set before the first hit, and again at the top of each pass."""
        _safe(track, control, value)
        self.setup.append((track, control, value))

    def perf(self, bpm, beats):
        events = [{"t": -1.0 + i * 0.002, "synth": "syntakt", "channel": tr, "cc": c, "table": "syntakt", "value": v} for i, (tr, c, v) in enumerate(self.setup)]
        for p in (0, 1):
            if p:
                events += [{"t": beats - 0.04, "synth": "syntakt", "channel": tr, "cc": c, "table": "syntakt", "value": v} for tr, c, v in self.setup]
            for t, track, vel in self.hits:
                events.append({"t": round(t + p * beats, 5), "synth": "syntakt", "channel": track, "note": 60, "vel": vel, "dur": 0.05})
            for ev in self.ccs:
                events.append({**ev, "t": round(ev["t"] + p * beats, 5)})
        return {"bpm": bpm, "beats": beats * 2, "pattern_beats": beats, "events": events}
