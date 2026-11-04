# Elektron Syntakt

Marks: [M] read in the manual, [S] other source, [T] seen on this Mac, [J] judgement, [U] unverified. A Syntakt appeared on the Mac late in the writing of this: its name and channels were read, nothing sent or recorded. So nothing here has been tried on one.

Source for all [M]: Syntakt User Manual, OS 1.42, 2026-09-30, https://www.elektron.se/wp-content/uploads/2026/10/Syntakt-User-Manual_ENG_OS1.42_260930.pdf (index: https://elektron.se/support-downloads/syntakt). Section numbers below are that manual's.

## USB and audio

- Class compliant, no driver needed. [M 7.15]
- USB CONFIG picks one of three modes, and picking one turns off the others (SETTINGS > SYSTEM > USB CONFIG): [M 14.9.1]
  - USB MIDI: MIDI only.
  - USB AUDIO/MIDI: audio and MIDI to a class-compliant host. This is the one for headless capture: no driver, no Overbridge.
  - OVERBRIDGE: needs Elektron's software.
- In USB AUDIO/MIDI, USB OUT sets what the Mac records: [M 14.6.5]
  - MAIN (end of the signal path, with effects)
  - TRACK 9-12: one analog track, or two as L and R
  - EXT: INPUT L/R, straight through
  - OFF

  So class-compliant capture gets you the main mix or the analog tracks, not the digital tracks on their own. For one digital track, mute the rest. On the Mac it shows as MIDI port and audio input `Elektron Syntakt`, 2 in and 2 out at 48 kHz. [T]
- **It can be the audio interface for the other two.** Run the opsix or Hydrasynth into INPUT L/R (1/4" mono plugs, unbalanced, +15 dBu, 11 kohm, 48 kHz 24-bit A/D) and set USB OUT to EXT, or to MAIN to put them through the analog drive and filter. EXTERNAL IN can treat L and R as two mono inputs, so the opsix on L and the Hydrasynth on R is possible. [M 3.2, 14.6.1, 18] That's from reading the routing, not from trying it. [J]
- USB IN sets where audio from the Mac comes in (PRE-FX, POST-FX, OFF), so it can reamp a file through the analog FX block. [M 14.6.4]
- INT TO MAIN and USB TO MAIN set whether streaming also reaches the physical outputs. [M 14.6.6-7]
- USB is high-speed USB 2.0, electrically isolated; the converters are 48 kHz, 24-bit. [M 18]

### Overbridge (when you want every track)

- 2.26.10 at time of writing; macOS 11 or later, native on Apple Silicon; needs Syntakt OS 1.41 or later. [S: https://elektron.se/support-downloads/overbridge]
- The macOS install adds Core Audio and HAL drivers, the Engine and a Control Panel, and on macOS 15 or later its driver extension may need enabling in System Settings > General > Login Items & Extensions. That's a system-wide install: ask first. [S: same page]
- Tracks 1-12 each stream separately, always dry, and still stream if routed away from MAIN; "Audio from the TRACK OUTPUTS is always without any effects" [M 14.6.8]. Delay, reverb and the analog FX block are only on the main output. [S: https://www.elektronauts.com/t/connect-syntakt-to-ableton-with-each-channel-separate-and-be-able-to-use-all-the-effects-included-routing-tracks-effects/243785]
- PRE/POST FADER decides whether the track streams sit before or after track level. [M 14.6.8]
- The standalone plug-ins have built-in multitrack recording. [S: https://www.elektron.se/overbridge]
- [U] Whether ffmpeg's avfoundation input can record every Overbridge channel: not tested. The exact channel map and stream format aren't in anything read here (forum reports only). Use class-compliant stereo for headless work; use Overbridge standalone when the user is at the machine.
- Elektron's Overbridge manual was over the fetch size limit and wasn't read: https://www.elektron.se/wp-content/uploads/2026/08/Overbridge-User-Manual_260826.pdf

## Settings to change (SETTINGS > MIDI CONFIG)

| Where | Setting | To |
|---|---|---|
| SYSTEM > USB CONFIG | mode | USB AUDIO/MIDI |
| PORT CONFIG | INPUT FROM | USB (or MIDI+USB) |
| PORT CONFIG | OUTPUT TO | USB, if it should send anything; the manual warns MIDI+USB limits USB speed |
| PORT CONFIG | RECEIVE NOTES | on |
| PORT CONFIG | RECEIVE CC/NRPN | on |
| SYNC | CLOCK RECEIVE, TRANSPORT RECEIVE | on, if a script is the clock |
| SYNC | PRG CH RECEIVE | on, to select patterns from a script |
| CHANNELS | TRACK 1-12 | 1-12, the default the manual assumes |
| CHANNELS | FX CONTROL CH | note it (a forum report says 13 by default [S: https://www.elektronauts.com/t/help-with-sending-midi-cc-to-syntakt/219704], [U] on the device) |
| CHANNELS | AUTO CHANNEL | a free channel, not 1-12 |

## Notes and programs

- Program change 0-127 selects pattern 1-128 (A01-H16), on PROGRAM CHG IN CH. [M 7.12]
- Note 0-11 triggers track 1-12 "provided they are set to their default channels", whichever track is active. [M 7.12]
- Notes 12-84 play the active track chromatically in 73 variations. [M 7.12] The manual's octave numbering has note 60 as C5.
- To play a track chromatically from a script: send to AUTO CHANNEL, or use each track's channel; on the track's own channel the manual's wording is about playing via the MIDI CHANNELS assignment [M 8.2.1], so confirm the note range there on the device. [U]
- A track is audio or MIDI, not both. Any track given the MIDI machine sends notes and CCs out DIN or USB. [M 6.3.2]

## Parameters [M Appendix B]

Per-track, on that track's channel. CC/NRPN MSB,LSB. Knob A-H on SYN means whatever the machine has there.

| Parameter | CC | NRPN | | Parameter | CC | NRPN |
|---|---|---|---|---|---|---|
| Mute | 94 | 1,101 | | Amp attack | 79 | 1,48 |
| Track level | 95 | 1,100 | | Amp hold | 80 | 1,25 |
| Note | 3 | 3,0 | | Amp decay | 81 | 1,26 |
| Velocity | 4 | 3,1 | | Amp sustain | 82 | 1,49 |
| Length | 5 | 3,2 | | Amp release | 83 | 1,24 |
| Porta time | 9 | 3,7 | | Delay send | 84 | 1,28 |
| Porta on/off | 65 | 3,8 | | Reverb send | 85 | 1,29 |
| SYN knob A-H | 17-24 | 1,1 to 1,8 | | Pan | 10 | 1,30 |
| Filter freq | 74 | 1,20 | | Volume | 7 | 1,31 |
| Resonance | 75 | 1,21 | | LFO1 speed | 102 (LSB 60) | 1,32 |
| Filter type | 76 | 1,22 | | LFO1 mult | 103 | 1,33 |
| Filter attack | 70 | 1,16 | | LFO1 fade | 104 | 1,34 |
| Filter decay | 71 | 1,17 | | LFO1 dest | 105 | 1,35 |
| Filter sustain | 72 | 1,18 | | LFO1 wave | 106 | 1,36 |
| Filter release | 73 | 1,19 | | LFO1 phase | 107 | 1,37 |
| Env depth | 77 | 1,23 | | LFO1 mode | 108 | 1,38 |
| Env delay | 78 | 1,52 | | LFO1 depth | 109 (LSB 61) | 1,39 |
| Base | 26 | 1,50 | | LFO2 | 112-119 (speed LSB 62, depth LSB 63) | 1,40-47 |
| Width | 27 | 1,51 | | Pattern mute | 110 | 1,104 |

FX CONTROL channel:

| Delay | CC | NRPN | | Reverb | CC | NRPN | | FX track | CC | NRPN |
|---|---|---|---|---|---|---|---|---|---|---|
| Time | 21 | 2,0 | | Predelay | 29 | 2,8 | | Drive | 15 | 1,29 |
| Pingpong | 22 | 2,1 | | Decay | 30 | 2,9 | | Filter freq | 70 | 1,20 |
| Width | 23 | 2,2 | | Shelf freq | 31 | 2,10 | | Resonance | 71 | 1,21 |
| Feedback | 24 | 2,3 | | Shelf gain | 89 | 2,11 | | Type | 72 | 1,22 |
| HPF | 25 | 2,4 | | HPF | 90 | 2,12 | | Env depth | 73 | |
| LPF | 26 | 2,5 | | LPF | 91 | 2,13 | | Env delay | 74 | |
| Reverb send | 27 | 2,6 | | Mix | 92 | 2,15 | | Filter ADSR | 75-78 | |
| Mix | 28 | 2,7 | | Input LR | 16 | 2,30 | | Filter pan | 93 | |

Input balance 17 (2,32), input delay send 18 (2,33), input reverb send 19 (2,35), input FX routing 20 (2,38). FX amp: attack 79, hold 80, decay 81, sustain 82, release 83, delay send 84, reverb send 85, pan 10, volume 7, env depth 86, mode 87, env reset 88.

The appendix's FX amp NRPN LSBs differ from the audio tracks' (1,24 attack and so on); check that table before using NRPN there.

Sysex: projects, patterns and sounds can be dumped and received (SETTINGS > SYSEX DUMP); the format isn't published in the manual. [M 14.5] Parameter control is CC/NRPN.

## Engines: what each is for

Tracks 1-8 digital, 9-11 analog drum, 12 analog cymbal; every track can also be a MIDI track. [M A.1] Each voice has a filter and amp; analog drive, multimode filter and amp sit in the Analog FX block with its own track. [M 5.4]

Digital (tracks 1-8): [M A.2]

| Machine | What's there | Use it for [J] |
|---|---|---|
| BD MODERN | pitch sweep, punch, square and triangle mod, mod env | clean heavy kick, modern |
| SD BASIC, SD VINTAGE | snares | backbeat |
| PC CARBON | percussion | metal hits |
| CP VINTAGE | noise and FM body | claps, and gates slamming if pitched down |
| CY ALLOY | digital cymbal | |
| SY BITS | two oscillators, noise, sample rate and bit reduction down to 2 bits | dead modems, the desert's corrupted data |
| SY TONE | two operators with ratio, feedback, mod env | small FM; pings, UI |
| SY CHORD | wavetable sweep, chord types, unison detune, filter env | stabs; a one-finger chord |
| SY TOY | FORM moves the operator ratios to imitate materials, IMP is the strike, PAR decays the partials | glass tanks, metal, UI, anything struck. Probably the most useful single machine here |
| SY SWARM | six detuned oscillators with noise mod and detune animation | a wall of saws, a Reese-like bass, swarm |
| SP TWINSHOT | two samples, each forward or reverse; the manual suggests a transient in one and body in the other | your own layers, 16-bit 48 kHz mono [M 6, A.2] |

Analog drum (9-11) and cymbal (12): [M A.3, A.4]

| Machine | Use it for [J] |
|---|---|
| BD HARD, BD CLASSIC, BD SILKY, BD SHARP, BD ACOUSTIC | kicks of different weight |
| BD FM, SD FM | analog FM: the metallic, unstable hits |
| BD PLASTIC | FM plus ring mod |
| SD NATURAL, SD CLASSIC, SD HARD, SD ACOUSTIC, RS HARD, RS CLASSIC | snares and rimshots |
| SY DUAL VCO | two oscillators with mix, ring, linear FM, each with its own decay; BEND adds a pitch envelope and a transient. It "does not pitch track 100%" in FM modes, which is fine for hits | 
| SY RAW | two analog oscillators plus noise, ring mod via osc 2's wave; the raw analog bass or drone |
| SY CHIP | fast internal arpeggio between notes, a home-computer chord; also good for drums and data chatter |
| CH/OH CLASSIC, CH/OH METALLIC, HH BASIC, HH LAB, CY CLASSIC, CY METALLIC, CY RIDE | hats and cymbals; METALLIC for industrial |

The analog FX block (drive, multimode filter, amp) over the whole mix is why this is the box to glue a drum bus through. [J]

## Sequencer features worth using here

- Per-track length and time signature (PER TRACK mode), micro timing, retrigs, trig conditions, parameter locks, a Euclidean sequencer. [M 9] Polymeter and polyrhythm come easily.
- Keyboard scales include Phrygian, Locrian, Lydian, Whole Tone, Whole-Half and Half-Whole Diminished (the octatonics), Harmonic Minor, Phrygian Dominant, Double Harmonic Major, Super Locrian. [M Appendix E]
- No microtuning is documented in the manual. Detune inside a machine (DET on SY RAW, SY DUAL VCO, SY BITS, SY SWARM) is the way to beating and roughness. [M A; absence by search]

## Firmware

The manual is OS 1.42; Overbridge 2.26 wants OS 1.41 or later. Check the unit's OS first. The CC table above comes from the 1.42 manual.
