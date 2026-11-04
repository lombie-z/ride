# Music theory and composition that applies here

Marks: [S] sourced (URL given), [J] judgement or common knowledge from practice, not checked against a source here. Claims about how music makes people feel come from few studies, often small. Treat them as starting points to test by ear.

## Contents

1. Modes and their affect
2. Tritones, chromatic mediants, the octatonic
3. Consonance, roughness, beating
4. Psychoacoustics of tension: alarm roughness, Shepard, lows, inharmonicity
5. Tuning
6. Rhythm and meter
7. Leitmotif
8. Early-2000s electronic and industrial idioms
9. Horror and film technique
10. Sources

## 1. Modes and their affect

What's measured: nonmusicians heard one melody in pairs of modes and judged which was happier. Happiness fell as scale degrees were lowered, Ionian to Phrygian, except that Lydian came out less happy than Ionian. [S: Temperley & Tan, *Music Perception* 2013, https://labs.sonicfield.org/library/emotional-connotations-of-diatonic-modes; a follow-up says familiarity alone doesn't explain it, https://labs.sonicfield.org/library/perception-and-familiarity-of-diatonic-modes] Locrian wasn't in the set. Everything below beyond "darker as it goes down" is practice and culture. [J]

Semitones from the tonic:

| Scale | Steps | Colour note | Character in use [J] | Syntakt scale name [S manual] |
|---|---|---|---|---|
| Lydian | 0 2 4 6 7 9 11 | #4 | floating, wonder, not quite earthly. Vamp I to II over a pedal | LYDIAN |
| Ionian | 0 2 4 5 7 9 11 | | plain daylight; suspect in horror | IONIAN |
| Mixolydian | 0 2 4 5 7 9 10 | b7 | | MIXOLYDIAN |
| Dorian | 0 2 3 5 7 9 10 | 6 | minor with air | DORIAN |
| Aeolian | 0 2 3 5 7 8 10 | b6 | sad, ordinary | AEOLIAN |
| Phrygian | 0 1 3 5 7 8 10 | b2 | the b2 over a pedal is a threat; the basis of a lot of metal riffing | PHRYGIAN |
| Locrian | 0 1 3 5 6 8 10 | b2, b5 | no stable fifth, so the tonic won't sit. Use over a pedal or for short stretches; it's hard to hold a tonic in | LOCRIAN |
| Harmonic minor | 0 2 3 5 7 8 11 | b6 and 7 (augmented second) | gothic, old-world, classical drama | HARMONIC MINOR |
| Phrygian dominant | 0 1 4 5 7 8 10 | b2 with major 3rd | sacred, hot, ceremonial, exotic by Western habit | PHRYGIAN DOMINANT |
| Double harmonic | 0 1 4 5 7 8 11 | two augmented seconds | stronger still | DOUBLE HARMONIC MAJOR |
| Whole tone | 0 2 4 6 8 10 | no fifth, no leading tone | weightless, dreamlike, gravity off. Six transpositions collapse into two, so it can't modulate | WHOLE TONE |
| Octatonic half-whole | 0 1 3 4 6 7 9 10 | minor thirds and tritones throughout | menace with internal logic | HALF-WHOLE DIMINISHED |
| Octatonic whole-half | 0 2 3 5 6 8 9 11 | | same family, softer | WHOLE-HALF DIMINISHED |

The octatonic is Messiaen's second mode of limited transposition, with only three distinct transpositions; composers use it for tense combat cues, and it was paired with whole tone in a game score at GDC 2023. [S: https://gamasutra.com/audio/whole-tone-and-octatonic-scales-the-game-music-of-jurassic-world-primal-ops-gdc-2023-] Scholarship specifically on these scales in horror wasn't found.

## 2. Tritones, chromatic mediants, the octatonic

**The tritone.** Six semitones, half the octave. It's its own inversion, so transposing a figure by a tritone can return the same notes, and it doesn't point at one root. The "devil's interval" story is mostly lore. [S: https://www.nationalgeographic.com/science/article/black-sabbath-devils-interval calls it lore] What's usable is the harmonic fact: in tonal music it wants to resolve outward or inward by semitone, so it can be sustained as tension and let go in one note.

**The major tritone progression (MTTP).** Two major triads a tritone apart (E major to Bb major). It's "often heard to accompany the extraordinary, and that which is beyond normal human experience", tied in Hollywood to outer space since 1950s science fiction. No shared notes, no tonal ground. [S: Murphy, *Music Theory Online* 12.2, 2006, https://mtosmt.org/issues/mto.06.12.2/mto.06.12.2.murphy.html] Two major chords can be more alien than a minor one.

**Chromatic mediants.** Triads with roots a third apart that don't share a key (C major to E major or Ab major). Lehman treats this kind of chromaticism as central to producing wonder in film. [S: *Hollywood Harmony*, OUP 2018, https://www.cinemabooks.info/book/9230/hollywood-harmony; the book itself wasn't read, only its description] 

**Minor-third axes.** E, G, Bb, Db divide the octave evenly. Moving a centre around that axis keeps the harmonic world related while the key changes, and all four sit in one octatonic. [J]

**The all-interval cell [0167]**: two semitones a tritone apart (E F Bb B). Transposed by a tritone it maps to itself as a set. It's dense in dissonance and stable as an object. Bartók-ish, generic, nobody's tune. [J]

## 3. Consonance, roughness, beating

Maximum unpleasantness between two sine tones comes at about a quarter of a critical bandwidth (Plomp & Levelt 1965), or about 40% by Greenwood's later estimate. Consonance of complex tones is roughly the sum over all pairs of partials, giving minima at 1:1, 2:1, 3:2, 5:3, 4:3, 6:5, 5:4 for harmonic spectra. [S: https://www.mpi.nl/publications/item66382/tonal-consonance-and-critical-bandwidth; summaries and Greenwood at https://auditory.org/postings/1999/234.html, https://auditory.org/postings/1999/289.html]

What follows in practice: [J]

- A critical band is about 100 Hz wide below 500 Hz, then about 15-20% of the frequency above. So the same interval is rougher low down. A third at E2 and G#2 turns to mud; a tritone there is growling. Keep intervals below about 150 Hz to fifths and octaves unless the mud is the point.
- Two tones Δf apart: under about 15-20 Hz you hear beats, then roughness, then two pitches once Δf passes the critical band.
- Detuning multiplies with the harmonic number. Two saws Δf apart at the fundamental are nΔf apart at harmonic n. That's why a detuned bass breathes at the bottom while its top end is rough.
- Δf for a detune of c cents is f(2^(c/1200) - 1): 20 cents at E2 (82.4 Hz) is 0.95 Hz at the fundamental, 9.5 Hz at harmonic 10.

## 4. Psychoacoustics of tension

**Roughness as alarm.** Human screams concentrate modulation between about 30 and 150 Hz, a band speech leaves alone (speech modulates around 4-5 Hz), and artificial alarms are there too. It boosts detection and it's rated disturbing. [S: Arnal et al., *Current Biology* 2015, https://archive-ouverte.unige.ch/unige:75898, and https://pure.mpg.de/pubman/item/item_2173158_7] Scream-like film music imitates that roughness. [S: Trevor, Arnal & Frühholz, JASA 2020, https://labs.sonicfield.org/library/terrifying-film-music-mimics-alarming-acoustic-feature-of-human-screams]

To make it: AM or a detuned pair at 40-100 Hz on a tone in the 500-3000 Hz range. Ring mod does it directly (opsix Ring Mod mode, Syntakt's SY RAW ring wave, Hydrasynth ring mod). [J]

**Noise and downward pitch.** Adding noise or a sudden pitch downshift to synth music made listeners rate it more negative and, in music alone, more arousing. Paired with benign video the arousal effect faded. [S: Blumstein, Bryant & Kaye, *Biology Letters* 2012, https://eprints.kingston.ac.uk/id/eprint/24741, https://lifesciences.ucla.edu/2012/06/dissonant-music-brings-out-the-animal-in-us] So a saw into distortion plus a sudden drop is a small, measured thing.

**Terror versus anxiety.** One line of work found that terrifying music is loud, brash and dense, while anxious music is more varied. [S: https://www.scientificamerican.com/article/how-composers-make-horror-movie-music-sound-terrifying] That's a useful distinction for pacing: anxious on the way in, terrifying when it arrives. [J]

**Shepard and Risset.** Octave-spaced partials under a fixed bell-shaped spectral envelope make a scale that rises forever; a continuous glide is Risset's version. [S: Shepard, JASA 1964, https://scilit.com/publications/115831fe1fae080a4c20a3a141be2b5b; https://resource.isvr.soton.ac.uk/spcg/tutorial/tutorial/Tutorial_files/Web-hearing-Shepard.htm; https://deutsch.ucsd.edu/psychology/pages.php?i=213] For a build of unknown length, it's ideal: it never runs out of room. Easiest done as Web Audio oscillators, since it has to respond to the game. See adaptive.md. [J]

**Infrasound-adjacent lows.** A 2003 concert experiment found 22% more people reporting odd feelings when a 17.5 Hz tone was mixed in. [S: https://www.sarahangliss.com/?p=27293, https://www.nbcnews.com/news/amp/wbna3077192] It's press-reported, and a tone from a 7 m pipe in a hall. Laptops and phones can't play it. What's usable: [J] energy at 30-60 Hz for those with headphones or subs, with harmonics (saturation) so small speakers imply the fundamental, and a high-pass at 25-30 Hz so nothing's wasted. Don't claim physical effects you can't deliver.

**Inharmonicity.** Partials not at integer ratios read as metal, glass, bell, broken. FM with non-integer carrier-to-modulator ratios makes them cheaply [J: Chowning 1973, *JAES*]. And dissonance depends on timbre: for an inharmonic spectrum the consonant intervals move, so a scale can be built to suit a timbre, or a timbre to clash with a scale. [S: Sethares, *Tuning, Timbre, Spectrum, Scale*, reported in https://www.scitepress.org/PublishedPapers/2007/21388/21388.pdf; the book wasn't read]

## 5. Tuning

| Ratio | Cents | Off 12-TET by | Use [J] |
|---|---|---|---|
| 16/15 | 112 | +12 | a wider, keener semitone |
| 5/4 | 386 | -14 | a still, pure major third, audibly unlike a piano's |
| 4/3 | 498 | -2 | |
| 45/32 | 590 | -10 | a just tritone |
| 7/5 | 583 | -17 | a softer tritone, on the harmonic series |
| 11/8 | 551 | -49 | between fourth and tritone, neither |
| 3/2 | 702 | +2 | |
| 8/5 | 814 | +14 | |
| 13/8 | 841 | -59 | neutral sixth; strange and sweet |
| 7/4 | 969 | -31 | harmonic seventh, the barbershop one. Blends, won't resolve |

Pure intervals on a sustained, harmonically rich tone stop beating, and that stillness is striking against equal-tempered material. [J]

**The rig:** only the Hydrasynth has microtuning, with 32 slots, presets including Just Major C, Just Minor C, Harmonic A 1-60, W. Carlos Harmonic, Partch 43-note, Bohlen 11, hexanies and more, and imported MTS sysex made in Scala. [S: its manual] Syntakt: no microtuning in the manual, only detune inside machines. opsix: no scales; operators can be fixed in Hz or tuned by ratio and cents, which suits partials, not scales. [S: its manual]

MTS: a bulk dump gives each of 128 notes its own frequency. [S: https://en.wikipedia.org/wiki/MIDI_tuning_standard] Its spec is in the MIDI 1.0 documents, https://midi.org/community/midi-specifications/the-midi-tuning-standard; check it before writing a generator, as secondary listings disagree on sub-IDs.

## 6. Rhythm and meter

**Tempo and the body.** In one small study, faster tempi raised breathing, blood pressure and heart rate, whatever the style, and a silent pause brought them below baseline. [S: Bernardi et al., *Heart* 2006, https://heart.bmj.com/content/92/4/433] Preferred tempo sits around 100-120 BPM. [S: McKinney & Moelants, cited in https://link.springer.com/content/pdf/10.3758/s13421-024-01543-6.pdf] So above about 120 reads as urgent, and pauses are powerful. Resting heart rates are about 60-100. A tempo at or under that feels like a body at rest. [J]

**Speed.** Pre-rendered stems can't follow continuous speed without a time-stretcher or a pitch change. Map tempo to zones in steps, and use continuous things for continuous speed: engine, wind, filter, pitch of non-musical layers. [J]

**Polyrhythm and polymeter.** Polyrhythm divides one span two ways at once (3:2, 4:3, 5:4). Polymeter runs different bar lengths on one pulse, drifting and realigning: a 7-step and a 16-step line realign every 112 steps. Machinery feel comes easily from polymeter, the Syntakt's per-track lengths do it directly. [J; S: its manual]

**Odd meter.** 7/8 as 2+2+3 or 4+3 feels like a beat missing: unbalance with a pattern. In 5/4 the limp is slower. Odd meter is hard to dance to and easy to ride to as long as the downbeat is strong. [J]

**Metric modulation.** Hold one duration while renaming what it is. Example with exact frames: a 7/8 bar at quarter = 140 and a 4/4 bar at quarter = 160 last the same 1.5 s (72,000 frames at 48 kHz). The beat changes without the bar line moving. [J: arithmetic]

**Euclidean rhythms.** Distribute k onsets across n steps as evenly as possible; many traditional patterns turn up. The Syntakt has a Euclidean sequencer. [S: manual 9.4]

**Silence.** Sudden absence before a shock heightens it. [S: Ireland, https://theconversation.com/what-makes-a-film-score-frightening-expert-explains-the-techniques-that-build-tension-and-make-us-jump-216121]

## 7. Leitmotif

A leitmotif is the union of a theme and an association. [S: Bribitzer-Stull, *Understanding the Leitmotif*, CUP 2015, https://cambridge.org/core/books/understanding-the-leitmotif/9D11CE0FCA4C9965F5BC07550CDBBBD7; the description rather than the book] It works if it's recognisable when changed, so it needs a strong outline, such as a rhythm or one defining interval, in few notes. [J]

Ways to change it, gentlest to most drastic: [J]
- timbre and register
- harmonisation under it: same notes, new meaning
- modal mutation: same contour, different steps
- interval widening or narrowing
- rhythmic augmentation, diminution
- fragmentation: only its first gesture
- inversion, retrograde
- canon with itself

Establish it clearly before transforming it. Bring it back plainly at the end.

## 8. Early-2000s electronic and industrial idioms

Techniques, not anyone's tracks. All [J] unless noted.

- **Reese bass**: two saws slightly detuned, then chorus, flange, filter, resampling. The movement is phase beating, faster up the keyboard. [S: https://splice.com/blog/reese-bass-history/, https://www.attackmagazine.com/technique/tutorials/reese-bass-redux/] The Syntakt's SY SWARM, or SY RAW with two saws, or the Hydrasynth's detune with WavStack.
- **Breakbeat and drum and bass**: chopped break at 160-180, half-time weight. Syntakt with retrigs and micro timing, or samples via SP TWINSHOT.
- **Big-beat and industrial drums**: a compressed kit, overdriven, through one bus. The Syntakt's analog FX block is exactly this.
- **Nu-metal and industrial riffing**: palm-muted root, b2, tritone on a drop tuning, syncopated with kick unison. Sub-200 Hz chugs. As synth: BD HARD plus SY RAW plus saturation. No guitars in the rig: drive the Hydrasynth with Pre-FX Distortion, or the opsix's Wave Folder.
- **Trance gate and supersaw**: gated pad in 16ths, detuned stack. WavStack with Amp LFO in steps.
- **Acid**: resonant saw or square with accent and slide; not this project's main colour but a fine tool in the desert.
- **Glitch and lo-fi digital**: bit reduction, sample-rate reduction, cut-up buffers, tape stops, data as sound. SY BITS, Hydrasynth Lo-Fi, opsix Decimator, Sine 8bit.
- **Brass polychords**: one film score associated with this look used a pulsing brass polychord, trumpets above and horns below, and an unusually large brass section, with avant-garde techniques blended with Hollywood language. [S: review at https://www.filmtracks.com/titles/matrix.html, publisher's note https://www.schott-music.com/en/blog/the-matrix] As a technique: two triads stacked a tritone or semitone apart, pulsing together. FM brass or Hydrasynth.
- **Choir plus machine**: gothic pad under cold drums. Religious association comes with organ and hymn-like voice-leading. [S: Ireland]
- **Sidechain pump**: pads breathing around the kick; a mix sound of the era and an easy read of the pulse.
- **Survival-horror pacing**: long tense quiet between events, a safe calm room as relief. Contrast is the whole thing.

## 9. Horror and film technique

From Ireland's survey, a scholar at Leeds: drones; silence; stingers; tremolo; short repeated melodies; escalation by adding instruments, level, or rising sequence; dissonance that doesn't resolve; high string lines imitating screams; voices and heartbeats; electronic sound design; incongruous cheerful music; organ, music box, hymn and lullaby associations. [S]

A stinger is a sharply attacked, not necessarily loud chord that reinforces a surprise. Don't overuse; expectation of it is half the effect. Huron's *Sweet Anticipation* (MIT 2006) lays out the five response systems (imagination, tension, prediction, reaction, appraisal), so the idea that the wait does much of the work has a theory behind it. [S: https://libcat.library.tamu.edu/Record/in00004601179/Description; the book wasn't read]

Clusters and sound mass: Penderecki's string writing avoids normal playing for dense clusters, microtones and glissandi, and came into horror through film. [S: https://bigthink.com/high-culture/horrifying-classical-music/, https://nofilmschool.com/how-exorcist-changed-sound-horror] On a synth: many detuned voices, glide, slow divergence. A cluster closing or opening by glide is a strong gesture. [J]

Techniques for synths that come out of this: [J]
- Slow divergence: start unison, each voice drifts apart. Hydrasynth Detune macro, Syntakt SY SWARM DET.
- Stacked semitones at high register with tremolo.
- Low unison swell with noise rising, cut dead.
- A tune that's almost a lullaby, in thin FM: the music box association.

## 10. Sources

Linked inline. Books whose descriptions, not contents, were read: Lehman, Bribitzer-Stull, Huron, Sethares. Further reading, not read for this: Lerner (ed.), *Music in the Horror Film*, Routledge 2010.
