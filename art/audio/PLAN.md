# Ride: what the sound needs

The working list. The full reasoning, patches and code hooks are in `.claude/skills/sound-design/references/ride-bible.md`. Status: the first take of the drum lines is in `drums/` (`lines.py` writes them, for the kit that's on the Syntakt), and first drafts for all five zones, three Hydrasynth parts each on existing patches, are in `hydrasynth/` (`score.py` writes them, `mix.py` lays them over the drums; previews in `previews/`). Everything in `art/audio/*.ogg` is placeholder.

## Compositions (looping stems, by zone)

| Zone | Key, mode | Tempo, meter | Stems |
|---|---|---|---|
| Green city | E Phrygian | 80, half-time | drums, bass, organ-choir bed, bell (motif) |
| Chrome city | G Lydian | 95, 4/4 | drums, bass, glass arpeggio, pad, chord stabs |
| Coral hive | Db, just intonation | grid 110, free heart | ticks and knocks, choir, tar; heart as one-shots |
| Data desert | Bb whole tone | 125, 7/8 | drums, pedal, storm, data chatter |
| Core: gate, lab | E Locrian | no beat | gate bed, lab bed, specimen hearts |
| Core: servers, plaza | E Locrian, then Phrygian | 140, 4/4 | drums, data hats, brass polychords, plaza choir |
| Boss (not built) | E and Bb together | 140 4/4, 140 7/8, 160 4/4 | 3 phases x 4 layers, plus broken versions |

The motif, in every zone in a different form: two heartbeats, a tritone apart (E F, Bb B).

## Sound effects

- **Bike:** engine per zone, 3 speed bands (5 x 3); wind; heart lub, dub
- **Chrome trace:** press ping, Risset riser (code), on-star shimmer, off-star warning (code), let go, lost
- **Hive:** 6 chord notes (perfect, good), bell, ring tick, miss knock, wrong-moment click, 666 sub drop, eyes opening, whisper choir, glare tone (code), eye button blink
- **Desert:** slingshot stretch (code), release snap and sub, flame roar, leaving a crest, landing thump, lightning
- **Core:** denied relay, ghost out, Mach crack, ghost run layer, creature heart and claws, ghost back boom, cool tone, ready ping, tank glass passes, lab doors, fluorescent buzz, bubbling
- **Boss run:** tritone siren, relays, gate slams, trap telegraph and strike, voice of the place
- **Fight:** best, good, miss, damage taken, boss hurt, kill
- **UI:** ticket tear, pill click, getting on and off, map open, map beeps, map pick

## Order

1. **Drum lines (now):** one 8-bar line per zone on the Syntakt, plus the heart.
2. Bike hearts and engines.
3. The motif on the opsix, then basses.
4. Hive chord and its effects, wired into the game with an audio clock.
5. Beds and the rest, zone by zone.
