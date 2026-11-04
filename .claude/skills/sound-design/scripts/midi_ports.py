#!/usr/bin/env python3
"""List MIDI ports and say which of the three synths each looks like. Sends nothing.

    python midi_ports.py [--json]
"""
import argparse
import json

import mido

from synth_maps import PORT_MATCH


def identify(name):
    low = name.lower()
    for synth, needles in PORT_MATCH.items():
        if any(n in low for n in needles):
            return synth
    return None


def ports():
    mido.set_backend("mido.backends.rtmidi")
    return {
        "in": [{"name": n, "synth": identify(n)} for n in mido.get_input_names()],
        "out": [{"name": n, "synth": identify(n)} for n in mido.get_output_names()],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    p = ports()
    if a.json:
        print(json.dumps(p, indent=2))
        return
    for direction in ("out", "in"):
        print(f"MIDI {direction}:")
        for port in p[direction] or [{"name": "(none)", "synth": None}]:
            print(f"  {port['name']}" + (f"   <- {port['synth']}" if port["synth"] else ""))
    found = {x["synth"] for x in p["out"] if x["synth"]}
    missing = set(PORT_MATCH) - found
    if missing:
        print("Not seen:", ", ".join(sorted(missing)))


if __name__ == "__main__":
    main()
