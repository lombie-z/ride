# ASM Hydrasynth

Marks: [M] read in the manual, [S] other source, [J] judgement, [U] unverified. No Hydrasynth was attached when this was written, so nothing here has been tried on one.

Sources for [M]: ASM's Owner's Manuals 2.2.0, linked from https://www.ashunsoundmachines.com/downloads:
- Keyboard and Desktop: https://www.mecldata.com/download/asm/Hydrasynth_KB_DR_Owners_Manual_2.2.0.pdf (the page numbers below are this one's)
- Explorer: https://www.mecldata.com/download/asm/Hydrasynth_Explorer_Owners_Manual_2.2.0.pdf
- Deluxe: https://www.mecldata.com/download/asm/Hydrasynth_Deluxe_Owners_Manual_2.2.0.pdf
- NRPN: "MIDI NRPN & CC Communication Spec, Firmware v1.5": https://www.mecldata.com/download/asm/legacy/Hydrasynth_KB_DR_MIDI_Spec_1.5.0.pdf. That's the newest found, older than the current firmware 2.2.0, and from the "legacy" folder. Test any NRPN before trusting it. [U]

Ask which model it is:

| | Voices | Keys | Ribbon | Notes |
|---|---|---|---|---|
| Keyboard | 8 | 49 polyphonic aftertouch | yes | |
| Desktop | 8 | none | no | |
| Explorer | 8 | 37 polyphonic aftertouch | no: "doesn't have a ribbon controller, but it will respond appropriately to another Hydrasynth model that does" [M Explorer] | |
| Deluxe | 16, two parts, four outputs | 73 polyphonic aftertouch | yes | MIDI page numbers are one higher; Multi mode ignores notes on the Global channel |

Voice counts: [M p.10, Deluxe p.12]. Explorer: https://www.ashunsoundmachines.com/hydrasynth-explorer

## USB and audio

- "A USB class-compliant device", available as MIDI in/out with no driver. [M p.12-13] USB port: MIDI, clock.
- **"The USB connection is not an audio output."** [M, stated in all three] It needs an audio interface, or a cable into the Syntakt's inputs. Outputs are stereo 1/4" balanced.
- Master Volume is an analog knob and also responds to CC 7. [M Deluxe p.13] So a script can set the level, and the knob sits on top of it.

## Settings to change

SYSTEM SETUP, MIDI pages (Keyboard/Desktop numbering): [M p.100-103]

**The Explorer numbers them differently**: `Clock Sync`, `Local`, `MIDI TX`, `MIDI RX` on page 7; `Param TX`, `Param RX` on page 10 (knobs 1, 2); `Overflow`, `Arp TX`, `Pgm Chg TX/RX` on page 11. [M Explorer 2.2.0, p.82-84] Notes play regardless of these, so a synth that plays but ignores patch and parameter changes needs these pages checked first. [T: seen on an Explorer]

Tried on an Explorer over USB MIDI, once `Param RX` was `NRPN` and `Pgm Chg RX` on: bank select plus program change switches patches (`B021` and back to `A001`), and loading a patch again undoes NRPN edits. Filter 1 cutoff over NRPN `40 28` responds across 0-8192, with level rising with it on that patch; 16383 is out of range and behaved unpredictably. [T]

More from the Explorer: [INIT] twice is the clean start, and only the panel can do it. Filter routing `3F 2C` = 1 for parallel; `FRate` (`40 31`-`40 33`) 0 sends a source all to Filter 1, 8192 all to Filter 2. Filter 2 morph `40 2E` 0 is low pass, 8192 high pass. The Vowel filter takes out the fundamentals, so route a sine round it through Filter 2 for weight. After init OSC3 came out an octave low until its semitone was set (`3F 11`, VV 2, WW 0). Wave numbers: count through the manual's list (p.32) in its left column then its right, Classic 0-4 to Harmon 196-218; Vokz 1-6 is 96-101. Measure a change after making it: an edit that looks harmless can silence the sound. [T]

| Page | Setting | To | Why |
|---|---|---|---|
| 4 | Clock Sync | Auto or USB when a script is the clock, else Internal | |
| 4 | Local | Off if something echoes back. Remembered through power-off, so it looks like a fault if forgotten | |
| 4 | MIDI RX | a fixed channel, e.g. 3 | |
| 4 | MIDI TX | same | |
| 5 | Mod receive | On, for CC 1 | |
| 5 | MPE | Off | it locks other settings |
| 6 | **Param RX** | **NRPN or CC** | **without this no parameters respond at all**; CC is simpler, NRPN is finer |
| 6 | Param TX | same, if reading edits back | |
| 6 | Pgm Chg RX | On | |
| 6 | Arp TX | Off unless wanted; also toggles the arp responding to incoming notes | |

Mod wheel, volume, sustain and so on ignore Param Tx/Rx. [M p.102]

## Selecting patches

Bank select needs both CC 0 and CC 32 as well as a program change, "or else the Hydrasynth will only select patches within the current bank". [M Deluxe p.109] CC 0 = 0; CC 32 = 0-7 for banks A-H (the Keyboard, Desktop and Explorer's spec says range 0-4 for firmware 1.5). [M, S spec]

Sysex: Send Patch and Send All Patches over MIDI or USB. The format isn't published in what was read; ASM Manager (free) is the supported way to store them. [M p.102] Microtuning has its own sysex path, below.

## CC chart [M p.116-119]; all models the same (Keyboard vs Deluxe compared by script, identical)

| CC | Parameter | CC | Parameter | CC | Parameter |
|---|---|---|---|---|---|
| 1 | Mod wheel | 43 | Ring mod depth | 74 | Filter 1 cutoff |
| 3 | Noise vol | 44, 46, 48 | OSC1, 2, 3 vol | 75, 76 | LFO3 gain, rate |
| 5 | Glide time | 45, 47, 49 | OSC1, 2, 3 pan | 77, 78 | LFO4 gain, rate |
| 7 | Master volume | 50 | Filter 1 drive | 79, 80 | LFO5 gain, rate |
| 8 | Noise pan | 51 | Filter 1 keytrack | 81-84 | ENV1 ADSR |
| 9, 10 | Ring mod vol, pan | 52 | Filter 1 LFO1 amount | 85-88 | ENV2 ADSR |
| 11 | Expression | 53 | Filter 1 vel env | 89, 90, 96, 97 | ENV3 ADSR |
| 12, 13 | Pre-FX param 1, 2 | 54 | Filter 1 ENV1 amount | 25, 27, 125, 124 | ENV4 ADSR |
| 14, 15 | Delay feedback, time | 55, 56, 57 | Filter 2 cutoff, res, type | 102-105 | ENV5 ADSR |
| 16-23 | **Macro 1-8** | 58-61 | Filter 2 keytrack, LFO1, vel, ENV1 | 91 | Reverb wet |
| 24 | OSC1 WaveScan | 62 | Amp LFO2 amount | 92 | Delay wet |
| 26 | OSC2 WaveScan | 63 | Delay wet tone | 93, 94 | Pre-FX, Post-FX mix |
| 28 | LFO2 gain | 64 | Sustain | 95 | Detune |
| 29, 30, 31 | Mutator 1 ratio, depth, wet | 65 | Reverb time | 106-110 | Arp division, gate, mode, ratchet, chance |
| 33, 34, 35 | Mutator 2 | 66 | Glide | 111-113 | OSC1-3 cent |
| 36, 37, 39 | Mutator 3 | 67 | Reverb tone | 114-116, 118, 119 | FRate of OSC3, noise, ring, OSC1, OSC2 |
| 40, 41, 42 | Mutator 4 | 68, 69 | Post-FX param 1, 2 | 117 | Stereo width |
| 0, 32 | Bank MSB, LSB | 70, 71, 72, 73 | LFO1 gain, F1 res, LFO1 rate, LFO2 rate | 120, 122, 123 | Arp octave, length, all notes off |

## NRPN [S spec, firmware 1.5]

CC 99, 98 for the parameter, then CC 6, 38 for the value. Value = VV×128+WW, default range 0 to 8192 unless noted. Some parameters share one NRPN and use VV as an index. Hydrasynth's replies use CC 6/38 too. [S: https://kyma.symbolicsound.com/qa/6503/]. A worked example: OSC1 to WaveScan is `CC99=63 CC98=24 CC6=0 CC38=1`. [S: https://cycling74.com/forums/controlling-the-hydrasynth-with-max8-via-midi-nrpn]

| Parameter | NRPN hex | Value |
|---|---|---|
| OSC mode | 3F 18 | VV = osc 0-2, WW = Single/WaveScan |
| OSC semi | 3F 11 | VV = osc 0-2; WW > 64 means WW-128 |
| OSC1, 2, 3 type | 3F 19, 3F 1A, 3F 0D | 0-218 (the waveform) |
| OSC1, 2, 3 cent | 41 01, 41 02, 41 03 | above 4096 means value-8192 |
| All OSC cent | 41 04 | |
| OSC1, 2 WavScan | 41 2A, 41 2B | |
| WaveScan wav 1-8, OSC1 | 3F 60 to 3F 67 | 0-218 |
| WaveScan wav 1-8, OSC2 | 3F 68 to 3F 6F | 0-218 |
| Mutator 1 ratio, depth, wet | 41 2C, 40 1F, 40 22 | |
| Mutator 2 | 41 2D, 40 20, 40 23 | |
| Mutator 3 | 41 2E, 40 21, 40 24 | |
| Mutator 4 | 41 2F, 40 16, 40 17 | |
| Mutator 1 feedback, window, warp 1-8 | 40 25, 40 1C, 40 60-67 | |
| Mutator mode | 3F 21 | see the spec |
| Mutator FM source | 3F 24 | WW 0-12: Sine, Triangle, OSC1-3, RingMod, Noise, Mutators |
| Noise type | 3F 27 | 0-6: White, Pink, Brown, Red, Blue, Violet, Grey |
| Ring mod vol, depth | 40 01, 40 03 | |
| OSC1, 2, 3 vol | 40 07, 40 09, 40 0B | |
| Noise vol | 40 0D | |
| Filter 1 cutoff, res, drive | 40 28, 40 29, 40 2B | |
| Filter 2 cutoff, res, morph | 40 2C, 40 2D, 40 2E | |
| Reverb time | 41 79 | |
| Detune, stereo width | 3F 39, 3F 44 | 0-127 |
| Density | 3F 3C | 1-8 |
| Glide, time | 3F 12, 3F 15 | |
| Pitch bend range | 3F 41 | 0-24 |
| Macro 1 target, depth 1-8 | 3E 30-37, 36 30-37 | see the spec |
| Mod matrix 32 depth | 41 5F | see the spec |
| Ribbon mode, key span, octave, quantise, glide | 3F 3B | VV = 00, 01, 02, 03, 11 (hex) |

The whole table's in the spec; this is the useful part. Since these reach the waveform choice and mutator modes, a script can build a patch from nothing over NRPN. Slow, but it means patches can live as text in the repo. [J] Firmware caveat above applies: the spec's own example users had filter NRPNs failing on v1.4. [S: https://www.elektronauts.com/t/hydrasynth-octatrack-nrpn-issue/131033]

Practical rule: set up a patch by hand with macros assigned, then automate Macro 1-8 (CC 16-23). Any mod-matrix destination can also take a CC as its source. [S: https://www.elektronauts.com/t/hydrasynth-from-asm-tips-tricks-and-queries/119081?page=17]

## Tuning

The only one of the three with real microtuning. Voice module, page 3 selects a scale; the Microtuning menu holds 32 slots. [M Deluxe p.106, 119]

Preset slots: 1/4 Tone, 19 Tone, 31 Tone, Al-Farabi SynChrom, Arabic 12-tone, Archytas Chromatic, Archytas Enharmonic, Belafon Singapore, Belafon W. Africa, Bendeler Well-Tempered, Bohlen 11-tone, Chinese 300 B.C., Chinese DiziFlute, Crysanthos Byzantine, Dekany 1 3 5 11-3, Dekany 1 3 5 7 11, Diaphonic 12-tone, Eikosany 1 3-11, Greek Aeolic, H. Partch 43-note, Harmonic A 1-60, Hexany 1 3 5 9, Hexany 1 3 7 11, Hexany 13 11 13, Indian Raga, Japanese Koto, Just Major C, Just Minor C, Mean tone C, Pelog/Slendro, Sk8board 17-65, W. Carlos Harmonic.

Your own: make a scale in Scala, export an MTS (MIDI Tuning Standard) sysex file, press Receive Scale (button 3), and send it. Only the first 16 characters of the name are kept; in Scala the name comes from the scale's Description. [M p.98] (So `perform.py --allow-sysex` could send it, but it's a device-state change: ask.) The scale key is set separately on the same page. Presets stay "Just Major C", so transpose by playing, or by making your own tuned to the zone's tonic. [J]

## Engines

3 oscillators per voice, 219 waveforms, WaveScan on OSC1 and 2 morphing through 8 waves; 4 Mutants, noise, ring mod, 2 filters in series or parallel, 5 LFOs, 5 envelopes (loopable with delay and hold), macros, 32-slot mod matrix. [M p.10, 37-45]

**Mutants** (two for each of OSC1 and 2): [M p.38-41]

| Mode | Does | Use it for [J] |
|---|---|---|
| FM-Lin | linear FM from itself, another Mutant, or any of the waves | any wave as carrier and modulator, so FM beyond sines |
| WavStack | phase-shifted copies, like many oscillators from one | a wide pad or a single-voice supersaw |
| OSC Sync | hard-syncs harmonics | tearing leads, screaming sweeps |
| PW-Orig | classic pulse width | |
| PW-Sqeez | time-compressed PWM | |
| PW-ASM | PWM via FM over chosen sections of the wave | |
| Harmonic | emphasises single harmonics, others fade | a voice singing partials; the angels |
| PhazDiff | difference of the wave and an inverted, shifted copy | hollow, vocal movement |

Filter 1: 16 types including LP Ladder 12/24, LP Fat, LP Gate, MS-20, 3-Ler, 8-Pole 48 dB, and **Vowel**, a formant filter with its own Control. Filter 2: state-variable, morph. [M p.45]

FX: Delay (5 types, including reverse), Reverb (4 types, up to 90 s, plus **Freeze**), Pre and Post FX: Chorus, Flanger, Rotary, Phaser, Lo-Fi, Tremolo, EQ, Compressor, Distortion. [M p.10]

**Polyphonic aftertouch**: per-note pressure as a mod source, sent and received on MIDI as `polytouch`. A script can send it, so a chord's notes can swell independently in a take. **Ribbon** (Keyboard and Deluxe): Pitch Bend, Theremin (mono, with key and scale), or Mod Only (RbnAbs, RbnAbs+, RbnRel). The ribbon transmits pitch bend or NRPN (setting on MIDI page 5), and any model responds to that data, so its movement should be scriptable without one, once its NRPN number has been read off a Keyboard or the spec. [U] [M p.75-76, p.101]

Best at: anything that has to breathe and sing. Pads, choirs, evolving drones, sirens that aren't just sine waves, cinematic swells, all through macros. It's the sound of the living things here.
