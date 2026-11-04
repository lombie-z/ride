# Writing lines that feel played

All of this is judgement, and the numbers are starting points that came out of the first lines for Ride. The user's ears overrule them.

## A body plays it

Think about who could play the line. It doesn't have to be possible, but a line with no idea of a body reads as a sequencer.

- Two hands and two feet. A dense line with a hat on every sixteenth, snare and fills needs the hat to drop out where the fill's hands went.
- Hats alternate strong and weak: on the beat firmer, the offbeat often firmest in dance music, the sixteenths between lighter.
- Kick and snare stay steady. They carry the time, so they wander least. Most of the looseness is in hats and ghosts.

## Velocity

Three layers, set per hit:

| Layer | What | Rough velocity |
|---|---|---|
| Shape in the bar | accent pattern, stronger and weaker beats | 30 to 125 |
| Shape of the phrase | a line that builds over 8 bars, or a bar that sits back; `lift` or `build` by bar | ±8 |
| Each hit | no two the same; `spread` in `Line.hit` | ±2 to 3 for kicks and snares, ±6 to 10 for hats and percussion |

- **Ghost notes:** velocity 28 to 45, on the sixteenth before or after a backbeat, not every bar.
- **Builds:** into a fill or a new section, rise over the bars before. Don't only jump at the fill.
- Check the machine responds: some tracks may not have velocity mapped. Look at the peaks across a take if a line seems flat.

## Time

`drift` is in beats, so the same value is less time at a faster tempo. 0.012 beats at 80 BPM is 9 ms.

| Feel | Move |
|---|---|
| Laid back | backbeat late: +0.01 to 0.02 beats, hats looser than the rest |
| On the grid, machine | no drift: looseness elsewhere would read as a mistake |
| Pushing | a small negative `push` on the whole line, or kick early against the hats |
| Limping | odd grouping (4 + 3), an extra kick placed just late |

Layered hits (a digital kick with an analog one under it) sit 2 to 6 ms apart, so they thicken rather than flam. Larger gaps start to read as two hits.

## Across the 8 bars

- Don't play the same bar eight times. Vary on 2s and 4s: a ghost, a kick pickup, an opened hat.
- Bar 4 turns slightly. Bar 8 turns properly, with a fill that leads into bar 1, because it's a loop and bar 1 comes next.
- Keep fills short: the last beat or two. Rising velocity, no need for many notes.
- Leave holes. A missing hat is more human than one more. The hive's insect hats just drop 14% at random.
- **Euclidean patterns** (`euclid(5, 16)`) give evenly spread off-kilter rhythm that doesn't read as a backbeat. Several lengths over each other (5, 7, 11) make machinery. Good for data and insects, less so for a body.

## FX as playing

FX should move the way hands would, not stand still.

| Move | How | When |
|---|---|---|
| Throw | `L.throw` opens a delay send for one hit and shuts it | ends of phrases: a last hit flying off |
| Hats opening | raise track decay (CC 81) for one hit, set it back | now and then, before a turnaround |
| Hats breathing | `L.ramp` on filter (CC 74) over 16 or more beats | across a whole phrase, up and back, so the loop still meets |
| Drive riding | `L.ramp` on the FX channel's drive | gusts, or climbing into a fill |
| Room per sound | reverb send per track, by role | snare in the room, kick nearly dry |

A ramp must end where the loop starts, or the second pass jumps; `L.start` sets every control again at the top of each pass.

Set a control with `L.start` before using it. Its starting value on the machine is unknown, and setting it makes the take repeatable. FX values: stay under `CEILING` in `drumline.py`.

### Rooms by feel

| Feel | Reverb decay, mix | Delay feedback, mix | Drive |
|---|---|---|---|
| Big cold room | 88, 76 | 56, 60 | low |
| Glossy, clean | 70, 66 | 58, 62 | very low |
| Huge and wet | 92, 80 | 60, 64 | none |
| Dry and harsh | mix 0 | 30, 50, throws only | high, riding |
| Hard and tight | 48, 60 | 56, 62 | high, climbing |

## Syntakt control numbers used here

Per track, on its channel: amp decay 81, filter 74, delay send 84, reverb send 85. On the FX channel (13 on this machine, set under `MIDI CONFIG > CHANNELS`, so check): drive 15, FX filter 70, delay feedback 24, delay mix 28, reverb decay 30, reverb mix 92. Full table in sound-design's `references/hardware-syntakt.md`.

The FX filter's type is whatever's on the kit: check before sweeping it. A hit is `note 60` on the track's own channel, at the machine's default pitch.
