#!/usr/bin/env python3
"""Play a performance file (JSON) out to the synths. Dry run unless --send is given.

    python perform.py perf.json                 # prints every message with its time, opens no port
    python perform.py perf.json --send          # really sends: only with the user's go-ahead
    python perform.py perf.json --send --port hydrasynth="Some Port Name"

Performance file:

    {"bpm": 110, "beats": 16, "clock": ["syntakt"], "start": ["syntakt"],
     "defaults": {"opsix": {"channel": 1}},
     "events": [
       {"t": 0, "synth": "opsix", "cc": "filter.cutoff", "value": 40},
       {"t": 0, "synth": "opsix", "note": 40, "vel": 110, "dur": 1.5},
       {"t": 0, "synth": "hydrasynth", "nrpn": "f1.cutoff", "value": 4096},
       {"t": 4, "synth": "syntakt", "channel": 9, "note": 0, "vel": 127, "dur": 0.1},
       {"t": 8, "synth": "hydrasynth", "program": 12, "bank": 1},
       {"t": 0, "synth": "opsix", "ramp": "filter.cutoff", "from": 20, "to": 110, "dur": 8},
       {"t": 2, "synth": "hydrasynth", "polytouch": 110, "note": 67},
       {"t": 0, "synth": "hydrasynth", "sysex": [67, 0], "note_": "needs --allow-sysex"}
     ]}

`t` and `dur` are in beats; a seconds field `sec`/`dur_sec` can stand in for them. `ramp` makes CC messages at --ramp-hz.
`clock` lists synths to send MIDI clock to (24 PPQN) for the whole run plus --clock-preroll beats; `start` lists synths
to send Start to at beat 0 and Stop to at the end. Notes that are still on are released on exit, however it ends.
"""
import argparse
import json
import signal
import sys
import time

import mido

from midi_ports import identify
from synth_maps import DEFAULT_CHANNEL, resolve_cc, resolve_nrpn


SPIN = 0.02


def _beats(ev, key, sec_key, bpm, default=None):
    if sec_key in ev:
        return float(ev[sec_key])
    if key in ev:
        return float(ev[key]) * 60.0 / bpm
    if default is None:
        raise ValueError(f"event needs {key!r} or {sec_key!r}: {ev}")
    return default


def _nrpn_msgs(channel, msb, lsb, value):
    """CC 99, 98 (parameter), then 6, 38 (value MSB, LSB): the order the Syntakt and Hydrasynth documents describe."""
    value = max(0, min(16383, int(value)))
    return [
        mido.Message("control_change", channel=channel, control=99, value=msb),
        mido.Message("control_change", channel=channel, control=98, value=lsb),
        mido.Message("control_change", channel=channel, control=6, value=value >> 7),
        mido.Message("control_change", channel=channel, control=38, value=value & 127),
    ]


def expand(perf, ramp_hz=60.0, allow_sysex=False):
    """Turns a performance into a sorted list of (seconds, synth, mido message)."""
    bpm = float(perf["bpm"])
    defaults = perf.get("defaults", {})
    out = []

    def channel_of(ev):
        synth = ev["synth"]
        ch = ev.get("channel", defaults.get(synth, {}).get("channel", DEFAULT_CHANNEL.get(synth, 1)))
        if not 1 <= ch <= 16:
            raise ValueError(f"channel out of range: {ev}")
        return ch - 1

    for ev in perf.get("events", []):
        t = _beats(ev, "t", "sec", bpm)
        synth = ev["synth"]
        ch = channel_of(ev)
        if "polytouch" in ev:
            out.append((t, synth, mido.Message("polytouch", channel=ch, note=int(ev["note"]), value=int(ev["polytouch"]))))
        elif "aftertouch" in ev:
            out.append((t, synth, mido.Message("aftertouch", channel=ch, value=int(ev["aftertouch"]))))
        elif "note" in ev:
            dur = _beats(ev, "dur", "dur_sec", bpm)
            note, vel = int(ev["note"]), int(ev.get("vel", 100))
            out.append((t, synth, mido.Message("note_on", channel=ch, note=note, velocity=vel)))
            out.append((t + dur, synth, mido.Message("note_off", channel=ch, note=note, velocity=0)))
        elif "cc" in ev:
            table = ev.get("table", synth)
            out.append((t, synth, mido.Message("control_change", channel=ch, control=resolve_cc(table, ev["cc"]), value=int(ev["value"]))))
        elif "ramp" in ev:
            table = ev.get("table", synth)
            cc = resolve_cc(table, ev["ramp"])
            dur = _beats(ev, "dur", "dur_sec", bpm)
            a, b = float(ev["from"]), float(ev["to"])
            steps = max(1, int(dur * ramp_hz))
            last = None
            for i in range(steps + 1):
                v = int(round(a + (b - a) * i / steps))
                if v != last:
                    out.append((t + dur * i / steps, synth, mido.Message("control_change", channel=ch, control=cc, value=v)))
                    last = v
        elif "nrpn" in ev:
            msb, lsb = resolve_nrpn(synth, ev["nrpn"])
            for i, m in enumerate(_nrpn_msgs(ch, msb, lsb, ev["value"])):
                out.append((t + i * 1e-6, synth, m))
        elif "program" in ev:
            if "bank" in ev:
                out.append((t, synth, mido.Message("control_change", channel=ch, control=0, value=int(ev.get("bank_msb", 0)))))
                out.append((t + 1e-6, synth, mido.Message("control_change", channel=ch, control=32, value=int(ev["bank"]))))
            out.append((t + 2e-6, synth, mido.Message("program_change", channel=ch, program=int(ev["program"]))))
        elif "bend" in ev:
            out.append((t, synth, mido.Message("pitchwheel", channel=ch, pitch=int(ev["bend"]))))
        elif "sysex" in ev:
            if not allow_sysex:
                raise ValueError("sysex in the performance: pass --allow-sysex (it can overwrite patches on the device)")
            out.append((t, synth, mido.Message("sysex", data=[int(x) for x in ev["sysex"]])))
        else:
            raise ValueError(f"don't know this event: {ev}")

    end = max([x[0] for x in out], default=0.0)
    if "beats" in perf:
        end = max(end, float(perf["beats"]) * 60.0 / bpm)
    for synth in perf.get("start", []):
        out.append((0.0, synth, mido.Message("start")))
        out.append((end, synth, mido.Message("stop")))
    return sorted(out, key=lambda x: x[0]), end


def clock_events(perf, end, preroll_beats):
    """MIDI clock from before beat 0 to the end, computed from the start time rather than added up, so it can't drift."""
    bpm = float(perf["bpm"])
    tick = 60.0 / bpm / 24
    n0 = -int(preroll_beats * 24)
    n1 = int(end / tick) + 1
    out = []
    for synth in perf.get("clock", []):
        out += [(n * tick, synth, mido.Message("clock")) for n in range(n0, n1)]
    return out


def open_ports(synths, overrides, virtual=None):
    mido.set_backend("mido.backends.rtmidi")
    names = mido.get_output_names()
    ports = {}
    for synth in synths:
        base = synth.split("_")[0]
        if virtual:
            name = virtual
        elif base in overrides:
            name = overrides[base]
        else:
            hits = [n for n in names if identify(n) == base]
            if not hits:
                raise SystemExit(f"No MIDI port for {base}. Ports: {names}. Plug it in, or use --port {base}=NAME.")
            name = hits[0]
        ports[synth] = name
    opened = {name: mido.open_output(name) for name in set(ports.values())}
    return {synth: opened[name] for synth, name in ports.items()}, opened


def run(events, ports, on_start=None):
    """Plays the events on the clock. Sleeps most of the wait and spins the last SPIN seconds: macOS timers can oversleep
    by 10 ms or more, more than enough to hear between layers."""
    held = {}
    t0 = time.perf_counter() - min(0.0, events[0][0] if events else 0.0) + 0.02
    if on_start:
        on_start(t0)

    stop = {"now": False}

    def handler(*_):
        stop["now"] = True

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
    late = 0.0
    try:
        for t, synth, msg in events:
            target = t0 + t
            while True:
                if stop["now"]:
                    return late
                left = target - time.perf_counter()
                if left <= 0:
                    break
                if left > SPIN:
                    time.sleep(min(left - SPIN, 0.05))
            late = max(late, time.perf_counter() - target)
            ports[synth].send(msg)
            if msg.type == "note_on" and msg.velocity > 0:
                held[(synth, msg.channel, msg.note)] = True
            elif msg.type in ("note_off", "note_on"):
                held.pop((synth, msg.channel, msg.note), None)
        return late
    finally:
        for (synth, ch, note) in held:
            ports[synth].send(mido.Message("note_off", channel=ch, note=note, velocity=0))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("performance")
    ap.add_argument("--send", action="store_true", help="really send MIDI; otherwise a dry run that opens no port")
    ap.add_argument("--allow-sysex", action="store_true")
    ap.add_argument("--port", action="append", default=[], metavar="SYNTH=NAME")
    ap.add_argument("--virtual-target", help="send everything to this one port instead (for tests against a virtual port)")
    ap.add_argument("--ramp-hz", type=float, default=60.0)
    ap.add_argument("--clock-preroll", type=float, default=4.0, help="beats of clock before beat 0")
    a = ap.parse_args()

    with open(a.performance) as f:
        perf = json.load(f)
    events, end = expand(perf, a.ramp_hz, a.allow_sysex)
    events = sorted(events + clock_events(perf, end, a.clock_preroll), key=lambda x: x[0])
    if not a.send:
        for t, synth, msg in events:
            if msg.type != "clock":
                print(f"{t:9.4f}s  {synth:12s} {msg}")
        clocks = sum(1 for e in events if e[2].type == "clock")
        print(f"dry run: {len(events)} messages ({clocks} clock), {end:.3f}s. Nothing sent. Add --send to play it.")
        print("(mido counts channels from 0, so channel=12 above is MIDI channel 13.)")
        return
    overrides = dict(p.split("=", 1) for p in a.port)
    ports, opened = open_ports(sorted({e[1] for e in events}), overrides, a.virtual_target)
    try:
        late = run(events, ports)
        print(f"sent {len(events)} messages over {end:.3f}s; worst lateness {late * 1000:.2f} ms", file=sys.stderr)
    finally:
        for p in opened.values():
            p.close()


if __name__ == "__main__":
    main()
