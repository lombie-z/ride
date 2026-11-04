#!/usr/bin/env python3
"""Record an audio input while a performance plays, and file it as a numbered take. Dry run unless --send.

    python capture.py --list-inputs
    python capture.py perf.json --input Syntakt --name core_alarm --dir takes/ --tail 3 --send
    python capture.py perf.json --dry-run-audio --name test --dir /tmp/x         # no MIDI, no device: a test tone stands in

It starts recording through Core Audio, waits --preroll seconds (frames go missing as a stream starts, and it gives a stretch
of noise floor), plays the performance, then records --tail more seconds for the tails. Takes go to DIR/NAME_t001.wav and a line in
DIR/takes.jsonl says what made them (performance, a hash of it, input, levels). Nothing's ever overwritten.

Cut the take to musical time afterwards with `audio_tools.py cut --onset` (see references/workflow.md). A take that
measures as digital silence is flagged: on macOS that's what capture does with no microphone permission, with no error.
"""
import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time

import mido

import audio_tools
import perform


WATCHDOG_RMS = 0.5
WATCHDOG_SECONDS = 0.15
# On the Syntakt's FX channel (13 on this machine): delay mix, reverb mix.
SYNTAKT_FX_OFF = (28, 92)


def list_inputs():
    p = subprocess.run(["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                       capture_output=True, text=True)
    audio = False
    out = []
    for line in p.stderr.splitlines():
        if "audio devices" in line:
            audio = True
        elif audio:
            m = re.search(r"\[(\d+)\] (.+)$", line)
            if m:
                out.append((int(m.group(1)), m.group(2)))
    return out


def find_input(needle):
    inputs = list_inputs()
    if needle.isdigit():
        return int(needle), dict(inputs).get(int(needle), "?")
    hits = [(i, n) for i, n in inputs if needle.lower() in n.lower()]
    if not hits:
        sys.exit(f"No audio input matching {needle!r}. Inputs: {inputs}")
    return hits[0]


def next_take(directory, name):
    os.makedirs(directory, exist_ok=True)
    n = 1
    while os.path.exists(os.path.join(directory, f"{name}_t{n:03d}.wav")):
        n += 1
    return os.path.join(directory, f"{name}_t{n:03d}.wav"), n


def record_core_audio(needle, pick, preroll, tail, path, play):
    """Records through Core Audio (PortAudio), plays the performance over it and writes the take. Tested on the Syntakt: not
    ffmpeg's avfoundation input, which delivered about 12% too few frames all the way through, so a take came out shorter and
    its hits closer together than played, with no error. Returns (the performance's worst lateness, overruns)."""
    import numpy as np
    import sounddevice as sd
    import soundfile as sf

    devices = sd.query_devices()
    hits = [i for i, d in enumerate(devices) if needle.lower() in d["name"].lower() and d["max_input_channels"] > 0]
    if not hits:
        sys.exit(f"No audio input matching {needle!r}. Inputs: {[d['name'] for d in devices if d['max_input_channels'] > 0]}")
    device = devices[hits[0]]
    chans = [int(c) - 1 for c in pick.split(",")] if pick else list(range(min(2, device["max_input_channels"])))
    blocks = []
    overruns = [0]

    # The watchdog: a synth's FX can run away into full-scale noise, loud and sudden in the room. This loud for this long isn't
    # music: stop playing, and let the caller pull the FX down.
    hot = [0.0]
    tripped = [False]

    def callback(data, frames, when, status):
        if status:
            overruns[0] += 1
        blocks.append(data[:, chans].copy())
        rms = float(np.sqrt(np.mean(data[:, chans] ** 2)))
        hot[0] = hot[0] + frames / 48000 if rms > WATCHDOG_RMS else 0.0
        if hot[0] > WATCHDOG_SECONDS and not tripped[0]:
            tripped[0] = True
            os.kill(os.getpid(), signal.SIGINT)

    with sd.InputStream(device=hits[0], samplerate=48000, channels=max(chans) + 1, dtype="float32", latency="high", callback=callback):
        time.sleep(preroll)
        if tripped[0]:
            sys.exit("Static before anything was played: it's stuck. Power cycle the synth. Nothing was sent.")
        late = play()
        if not tripped[0]:
            time.sleep(tail)
    sf.write(path, np.concatenate(blocks), 48000, subtype="PCM_24")
    return late, overruns[0], tripped[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("performance", nargs="?")
    ap.add_argument("--list-inputs", action="store_true")
    ap.add_argument("--input", help="audio input: part of its name, or its index from --list-inputs")
    ap.add_argument("--name", help="zone_kind_thing, e.g. core_sfx_alarm")
    ap.add_argument("--dir", default="takes")
    ap.add_argument("--preroll", type=float, default=3.0, help="seconds before the performance: frames go missing in the first second or two of a stream")
    ap.add_argument("--tail", type=float, default=2.0)
    ap.add_argument("--pick", help="input channels to keep, from 1, e.g. 3,4: for a multichannel interface (ffmpeg would otherwise record or remix them all)")
    ap.add_argument("--send", action="store_true", help="really send MIDI and record")
    ap.add_argument("--allow-sysex", action="store_true")
    ap.add_argument("--port", action="append", default=[], metavar="SYNTH=NAME")
    ap.add_argument("--virtual-target", help="send all MIDI to this port (for tests)")
    ap.add_argument("--dry-run-audio", action="store_true", help="record ffmpeg's test tone instead of a device; sends no MIDI")
    a = ap.parse_args()

    if a.list_inputs:
        for i, n in list_inputs():
            print(f"[{i}] {n}")
        return
    if not (a.performance and a.name):
        ap.error("a performance and --name are needed")

    with open(a.performance, "rb") as f:
        blob = f.read()
    perf = json.loads(blob)
    events, end = perform.expand(perf, allow_sysex=a.allow_sysex)
    events = sorted(events + perform.clock_events(perf, end, 4.0), key=lambda x: x[0])
    length = a.preroll + max(0.0, -events[0][0] if events else 0.0) + end + a.tail
    path, take = next_take(a.dir, a.name)

    if a.dry_run_audio:
        source = ["-re", "-f", "lavfi", "-i", f"sine=frequency=220:sample_rate=48000:duration={length:.3f}"]
        input_name = "lavfi test tone"
    elif a.send:
        if not a.input:
            ap.error("--input is needed with --send")
        input_name = a.input
    else:
        print(f"would record {length:.2f}s to {path}, playing {len(events)} messages. Nothing done. Add --send.")
        return

    late = None
    overruns = None
    if a.dry_run_audio:
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *source, "-t", f"{length:.3f}", "-c:a", "pcm_s24le", path]
        subprocess.run(cmd, stdin=subprocess.DEVNULL, check=True)
    else:
        ports, opened = perform.open_ports(sorted({e[1] for e in events}), dict(p.split("=", 1) for p in a.port), a.virtual_target)
        try:
            late, overruns, tripped = record_core_audio(a.input, a.pick, a.preroll, a.tail, path, lambda: perform.run(events, ports))
            if tripped:
                # Pull the Syntakt's FX down, if that's what it is, before saying so.
                for port in [p for name, p in ports.items() if name.startswith("syntakt")]:
                    for control in SYNTAKT_FX_OFF:
                        port.send(mido.Message("control_change", channel=12, control=control, value=0))
                sys.exit(f"WATCHDOG: sustained full-scale audio, stopped the performance and pulled the FX down. See {path}. If it's still noise, power cycle the synth.")
        finally:
            for p in opened.values():
                p.close()

    m = audio_tools.measure(path)
    entry = {
        "take": take, "file": os.path.basename(path), "name": a.name, "performance": os.path.basename(a.performance),
        "performance_sha1": hashlib.sha1(blob).hexdigest()[:12], "bpm": perf.get("bpm"), "input": input_name,
        "preroll_s": a.preroll, "tail_s": a.tail, "overruns": overruns, "worst_midi_lateness_ms": None if late is None else round(late * 1000, 2),
        "measure": m, "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if m["sample_peak_db"] is None or m["sample_peak_db"] < -90:
        entry["warning"] = "digital silence: check the macOS microphone permission, then the routing"
    if m["sample_peak_db"] is not None and m["sample_peak_db"] > -0.1:
        entry["warning"] = "clipped: bring the level down and take it again"
    with open(os.path.join(a.dir, "takes.jsonl"), "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(json.dumps(entry, indent=2))


if __name__ == "__main__":
    main()
