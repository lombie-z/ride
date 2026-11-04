"""Parameter maps for the three synths, from their manuals (see references/hardware-*.md for sources and caveats).

Names are what a performance file (assets/performances/*.json) uses as "param". Only what's useful for sound design is
here; the full tables are in the references. CC numbers are decimal. NRPN pairs are (MSB, LSB) in decimal.
"""

# Match against the port name, lower-cased. The Syntakt's is seen on the real thing ("Elektron Syntakt"). The other two are
# guesses at how they name themselves over USB: check `midi_ports.py` with them plugged in and correct these if needed.
PORT_MATCH = {
    "syntakt": ["syntakt"],
    "opsix": ["opsix"],
    "hydrasynth": ["hydrasynth", "asm"],
}

# Elektron Syntakt: OS 1.42 manual, Appendix B. Per-track parameters go on that track's channel (default 1-12);
# delay/reverb/FX-track parameters go on the FX CONTROL channel. Knobs A-H on SYN mean different things per machine.
SYNTAKT_TRACK_CC = {
    "mute": 94, "level": 95,
    "note": 3, "velocity": 4, "length": 5, "filter_trig": 13, "lfo_trig": 14, "porta_time": 9, "porta_on": 65,
    "syn.a": 17, "syn.b": 18, "syn.c": 19, "syn.d": 20, "syn.e": 21, "syn.f": 22, "syn.g": 23, "syn.h": 24,
    "filter.freq": 74, "filter.res": 75, "filter.type": 76,
    "filter.attack": 70, "filter.decay": 71, "filter.sustain": 72, "filter.release": 73,
    "filter.env_depth": 77, "filter.env_delay": 78, "filter.base": 26, "filter.width": 27,
    "amp.attack": 79, "amp.hold": 80, "amp.decay": 81, "amp.sustain": 82, "amp.release": 83,
    "amp.delay_send": 84, "amp.reverb_send": 85, "amp.pan": 10, "amp.volume": 7,
    "lfo1.speed": 102, "lfo1.mult": 103, "lfo1.fade": 104, "lfo1.dest": 105, "lfo1.wave": 106, "lfo1.phase": 107,
    "lfo1.mode": 108, "lfo1.depth": 109,
    "lfo2.speed": 112, "lfo2.mult": 113, "lfo2.fade": 114, "lfo2.dest": 115, "lfo2.wave": 116, "lfo2.phase": 117,
    "lfo2.mode": 118, "lfo2.depth": 119,
    "pattern_mute": 110,
}
SYNTAKT_TRACK_NRPN = {
    "mute": (1, 101), "level": (1, 100),
    "syn.a": (1, 1), "syn.b": (1, 2), "syn.c": (1, 3), "syn.d": (1, 4),
    "syn.e": (1, 5), "syn.f": (1, 6), "syn.g": (1, 7), "syn.h": (1, 8),
    "filter.freq": (1, 20), "filter.res": (1, 21), "filter.type": (1, 22), "filter.env_depth": (1, 23),
    "lfo1.depth": (1, 39), "lfo2.depth": (1, 47),
}
SYNTAKT_FX_CC = {
    "delay.time": 21, "delay.pingpong": 22, "delay.width": 23, "delay.feedback": 24, "delay.hpf": 25, "delay.lpf": 26,
    "delay.reverb_send": 27, "delay.mix": 28,
    "reverb.predelay": 29, "reverb.decay": 30, "reverb.shelf_freq": 31, "reverb.shelf_gain": 89, "reverb.hpf": 90,
    "reverb.lpf": 91, "reverb.mix": 92,
    "ext.level": 16, "ext.balance": 17, "ext.delay_send": 18, "ext.reverb_send": 19, "ext.fx_route": 20,
    "drive": 15, "fx.filter.freq": 70, "fx.filter.res": 71, "fx.filter.type": 72, "fx.filter.env_depth": 73,
    "fx.filter.env_delay": 74, "fx.filter.attack": 75, "fx.filter.decay": 76, "fx.filter.sustain": 77,
    "fx.filter.release": 78, "fx.filter.pan": 93,
    "fx.amp.attack": 79, "fx.amp.hold": 80, "fx.amp.decay": 81, "fx.amp.sustain": 82, "fx.amp.release": 83,
    "fx.amp.delay_send": 84, "fx.amp.reverb_send": 85, "fx.amp.pan": 10, "fx.amp.volume": 7,
    "fx.amp.env_depth": 86, "fx.amp.mode": 87, "fx.amp.env_reset": 88,
}

# Korg opsix/SE/module: MIDI implementation chart 3.1.0 (2023-01-17), manual E6. No NRPN in the chart.
OPSIX_CC = {
    "bank_msb": 0, "bank_lsb": 32, "mod": 1, "glide_time": 5, "volume": 7, "pan": 10, "expression": 11,
    "damper": 64, "glide_mode": 65, "sostenuto": 66, "soft": 67,
    "algorithm": 70, "filter.res": 71, "attack": 73, "filter.cutoff": 74, "decay_release": 79,
    "fx1": 81, "fx2": 82, "fx3": 83,
    "op1.level": 102, "op2.level": 103, "op3.level": 104, "op4.level": 105, "op5.level": 106, "op6.level": 107,
    "op1.ratio": 108, "op2.ratio": 109, "op3.ratio": 110, "op4.ratio": 111, "op5.ratio": 112, "op6.ratio": 113,
    "all_sound_off": 120, "reset_controllers": 121,
}

# ASM Hydrasynth: CC charts from the 2.2.0 manuals; NRPN from the MIDI spec for firmware 1.5 (the newest ASM publishes;
# re-check on 2.x). NRPN value is VV*128+WW, default range 0..8192 (0x2000) unless the table in the reference says
# otherwise. CCs and NRPNs are only received if System > MIDI "Param RX" is set to match.
HYDRA_CC = {
    "bank_msb": 0, "mod": 1, "noise.vol": 3, "glide_time": 5, "volume": 7, "noise.pan": 8, "rm.vol": 9, "rm.pan": 10,
    "expression": 11, "prefx.p1": 12, "prefx.p2": 13, "delay.feedback": 14, "delay.time": 15,
    "macro1": 16, "macro2": 17, "macro3": 18, "macro4": 19, "macro5": 20, "macro6": 21, "macro7": 22, "macro8": 23,
    "osc1.wavscan": 24, "env4.attack": 25, "osc2.wavscan": 26, "env4.decay": 27, "lfo2.gain": 28,
    "mut1.ratio": 29, "mut1.depth": 30, "mut1.wet": 31, "bank_lsb": 32, "mut2.ratio": 33, "mut2.depth": 34,
    "mut2.wet": 35, "mut3.ratio": 36, "mut3.depth": 37, "mut3.wet": 39, "mut4.ratio": 40, "mut4.depth": 41,
    "mut4.wet": 42, "rm.depth": 43, "osc1.vol": 44, "osc1.pan": 45, "osc2.vol": 46, "osc2.pan": 47, "osc3.vol": 48,
    "osc3.pan": 49, "f1.drive": 50, "f1.keytrack": 51, "f1.lfo1": 52, "f1.vel": 53, "f1.env1": 54,
    "f2.cutoff": 55, "f2.res": 56, "f2.type": 57, "f2.keytrack": 58, "f2.lfo1": 59, "f2.vel": 60, "f2.env1": 61,
    "amp.lfo2": 62, "delay.tone": 63, "sustain": 64, "reverb.time": 65, "glide": 66, "reverb.tone": 67,
    "postfx.p1": 68, "postfx.p2": 69, "lfo1.gain": 70, "f1.res": 71, "lfo1.rate": 72, "lfo2.rate": 73, "f1.cutoff": 74,
    "lfo3.gain": 75, "lfo3.rate": 76, "lfo4.gain": 77, "lfo4.rate": 78, "lfo5.gain": 79, "lfo5.rate": 80,
    "env1.attack": 81, "env1.decay": 82, "env1.sustain": 83, "env1.release": 84,
    "env2.attack": 85, "env2.decay": 86, "env2.sustain": 87, "env2.release": 88,
    "env3.attack": 89, "env3.decay": 90, "reverb.wet": 91, "delay.wet": 92, "prefx.mix": 93, "postfx.mix": 94,
    "detune": 95, "env3.sustain": 96, "env3.release": 97,
    "env5.attack": 102, "env5.decay": 103, "env5.sustain": 104, "env5.release": 105,
    "arp.division": 106, "arp.gate": 107, "arp.mode": 108, "arp.ratchet": 109, "arp.chance": 110,
    "osc1.cent": 111, "osc2.cent": 112, "osc3.cent": 113, "osc3.frate": 114, "noise.frate": 115, "rm.frate": 116,
    "stereo_width": 117, "osc1.frate": 118, "osc2.frate": 119, "arp.octave": 120, "arp.length": 122,
    "all_notes_off": 123, "env4.release": 124, "env4.sustain": 125,
}
HYDRA_NRPN = {
    "f1.cutoff": (0x40, 0x28), "f1.res": (0x40, 0x29), "f1.drive": (0x40, 0x2B),
    "f2.cutoff": (0x40, 0x2C), "f2.res": (0x40, 0x2D), "f2.morph": (0x40, 0x2E),
    "osc1.cent": (0x41, 0x01), "osc2.cent": (0x41, 0x02), "osc3.cent": (0x41, 0x03), "all_osc_cent": (0x41, 0x04),
    "osc1.wavscan": (0x41, 0x2A), "osc2.wavscan": (0x41, 0x2B),
    "osc1.type": (0x3F, 0x19), "osc2.type": (0x3F, 0x1A), "osc3.type": (0x3F, 0x0D),
    "mut1.ratio": (0x41, 0x2C), "mut1.depth": (0x40, 0x1F), "mut1.wet": (0x40, 0x22),
    "mut2.ratio": (0x41, 0x2D), "mut2.depth": (0x40, 0x20), "mut2.wet": (0x40, 0x23),
    "mut3.ratio": (0x41, 0x2E), "mut3.depth": (0x40, 0x21), "mut3.wet": (0x40, 0x24),
    "mut4.ratio": (0x41, 0x2F), "mut4.depth": (0x40, 0x16), "mut4.wet": (0x40, 0x17),
    "rm.depth": (0x40, 0x03), "rm.vol": (0x40, 0x01), "noise.vol": (0x40, 0x0D),
    "osc1.vol": (0x40, 0x07), "osc2.vol": (0x40, 0x09), "osc3.vol": (0x40, 0x0B),
    "reverb.time": (0x41, 0x79),
    "detune": (0x3F, 0x39),
}

CC = {"syntakt": SYNTAKT_TRACK_CC, "syntakt_fx": SYNTAKT_FX_CC, "opsix": OPSIX_CC, "hydrasynth": HYDRA_CC}
NRPN = {"syntakt": SYNTAKT_TRACK_NRPN, "hydrasynth": HYDRA_NRPN}

# Defaults: the Syntakt's track channels are 1-12 per its manual; its FX CONTROL channel default comes only from a forum
# report (13), so confirm it on the device. The other two are whatever you've set on them.
DEFAULT_CHANNEL = {"syntakt": 1, "syntakt_fx": 13, "opsix": 1, "hydrasynth": 1}


def resolve_cc(synth, param):
    table = CC.get(synth)
    if table is None:
        raise KeyError(f"no CC table for {synth!r}")
    if isinstance(param, int):
        return param
    if param not in table:
        raise KeyError(f"{synth}: no CC named {param!r}")
    return table[param]


def resolve_nrpn(synth, param):
    table = NRPN.get(synth)
    if table is None:
        raise KeyError(f"no NRPN table for {synth!r}")
    if isinstance(param, (list, tuple)):
        return tuple(param)
    if param not in table:
        raise KeyError(f"{synth}: no NRPN named {param!r}")
    return table[param]
