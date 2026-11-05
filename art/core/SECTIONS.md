# The stairwell and tunnel: what the site needs

Built by `art/core/road_sections.py` (the road), `stair.py`, `flood.py` (the pieces, by ASSETS.md's names), to `art/out/city5-stair.glb`, `city5-flood.glb`.
Re-run: `blender --background --factory-startup --python art/core/stair.py`, the same for `flood.py`. Env `STAIR_LEN`, `FLOOD_LEN`, `LAB_END` (art/core/kit.py's, the doors 8 m short of it) move
everything: flights and rings repeat, moments go by share of the length. Stills: `render_sections.py -- both all`, then `python3 art/core/sheet_sections.py`.

## The road

Each glb's `City5.RoadPath` has RoadPath's format (`points` [x, y], `step` 2, `length`, `width`) plus, per point, `heights`, `roll`, `surface` (0 floor, 1 steps, 2 wall, 3 air, 4 water), `fog`, and in the tunnel `spray`.
The 2 m is along the ride's 3D line, not its plan, so `speed` stays true on a flight or a wall. `s0` is where it starts on the core's road.

With the doors where they are today (s 4254; all of this moves with `LAB_END`):

| | s on the road | m | |
|---|---|---|---|
| Stairwell | 4254 to 5156 | 902 | drops 170, 26 sides (6.5 laps), long flight in, 4 flights out |
| Tunnel | 5156 to 6694 | 1538 | level, z -170 |
| Lab door stop | 4234 | | 20 short of the doors (lib/doors.ts stand) |
| Bulkhead stop | 6600 | | 24 short of its seat at 6624 |
| Hall | from 6694 | | kit s + 2432; the plan's the same, ends at (HALL_X, 0) heading +X, so sink its groups by 170 |

Joins are exact: door (4254, 0, 0) heading +X; stair's end = flood's start; flood's end (LAB_END 4262, 0, -170) heading +X.

## Speeds and the boost

- Stairwell: about 30 m/s. Boost off for all of it, s 4254 to 5156 (the moving pieces). ghostLocked() needs this range.
- Tunnel: about 36 m/s, boost about 150 m/s (its local cap). No boost from about 90 m short of the bulkhead stop, so it's shed in time (150 m/s at BRAKE * GHOST_SHED takes 57 m).
- The core's `cruise` is 56: both need a local cap by s, and ride.tsx's bend limiter (the `curve` lookahead) off here, or it brakes to 6 m/s at every corner. Its corners are R 7 to 14.

## Stops: closed doors stop the ride

Both in `lib/doors.ts`' table. Set the bulkhead's `at` to 6624 (the flood glb's `stop.door_s`), stand 24.
- Lab doors: brakes to a halt at s 4234, game, leaves open, on over the lip at s 4264.
- Bulkhead: halts in the water at s 6600, spray settled (spray's scaled by speed, so it dies with it). Game, then the door swings, then on through the gap. Nothing stands between the stop and the door.
- The door is `City5.BulkheadDoor`, an empty on the hinge with its parts under it, shut in the glb. Open it by turning that empty about its up axis by `-open_deg` (78.4): that's the 14 m gap, swinging into the room, the only way it clears the tube. So core-doors.tsx mustn't draw leaves here (`width`, `height` 0).

## Riding it

- **Heights:** `groundAt` works, but the bike must stick to the ground in these sections except on `air` (one range, the gap, s 4622 to 4642: a cliff in `heights`; it flies and lands on JUMP.gravity, drive.land's thump). As is, it'd fly off every flight's top: a flight falls 11.5 m/s, and free fall takes 0.5 s to reach that.
- **Pitch:** drive.pitch follows, as now. It's level at the lip, which is what makes the first shot.
- **Roll:** `roll` is radians about the direction of travel, + the bike's top to its right. Apply to bike and camera. Wall: stair's first corner to 88 degrees (+), tunnel's bend to 80 (-). Corners on the flat lean 14 at most, tunnel 25. It replaces bike.tsx's lean here (which has the opposite sign).
- **Camera:** the stills use pitch 8 and fov 82, not the site's 15 and 70 + 12 * pace^2. At 15 the top of the bulkhead and the upper half of the stair shot are out of frame. It puts the dash and the road's vanishing point where the images have them, so ease RIDER_PITCH to 8 here.
- **Rattle:** on `surface` 1. Thump at `air`'s end. Hiss on 2.
- **wet-road.tsx's** flat mirror has to be off in both. The images' wet shine on flights isn't in the models; a reflection or sheen on `City5WetConcrete` would be the site's to add.

## Water, spray, fog, steam

- `City5Water`: the water surface in both glbs, level `water.level` (deck + 0.35), UVs in metres / 8. Give it the shader by name (`art/core/fx/water-normal.png`), red and green reflections off the lamps and the room. It ends at the door's sill, `water.to_s`, s 6625.
- Spray (`art/core/fx/spray.png`): `spray` by speed, up both sides. Off on the wall, in the room and at rest.
- Fog: `fog` thickens over the stair's last 14%, from s 5030; it and the green glow (`City5ShaftGlow`, the shaft's floor) grow to the water. Tunnel's own light, as in the image.
- Steam (`fx/steam-burst.png`): stair's `events` kind `steam`, each with `s`, `at`, `dir`, from a sheared pipe across the road. Four of them, moment 6.

## Moving pieces

Not in the glb. Empties `City5.Moving.<asset>.<i>`: place and yaw, extras `asset`, `s0`, `s1` (metres along this section, add `s0` of the road). Load `art/out/assets/<asset>.glb` and scrub its clip from s0 to s1:
flight_collapse (the torn flight; it topples to the road's right, the shaft's side, as modelled), debris_set, three beam_swings, one shutter_slam. flight_collapse's clip starts whole, over stair_flight_torn's stump: show it until its clip's done, the stump after.

## Loading, a section at a time

Each glb stands alone, in the core's frame. Hold two at most, around a join; the swap is unseen in both:
- Lab to stair: load from the lab's last stretch; show from when its doors start opening; drop the lab 40 m past them. Hide its Hall group: the sink moves it.
- Stair to flood: the stair's glb has the flood's first 80 m of tube and water, sealed black. Load the flood during the stair, swap at s 2294. `City5.SealBack` shuts its back.
- Flood to hall: load during the tunnel. `City5.SealFar` is the room's far opening: hide it once the hall's shown. Drop the flood 40 m into the hall.
- Hall and shaft overlap in plan (the hall's sunk through it): only ever one at a time.
- city5.glb's deck and dashes are in two at the lab's door: group `Road` runs to the lip (door + 10), group `RoadHall` from LAB_END (door + 8), both unsunk in the glb. Sink `Hall`, `Core` and `RoadHall` together (zone-city.tsx, by lib/sections.ts hallSink()).
- Size: stair 760 objects, 163k tris drawn, 1.1 MB; flood 1427 objects, 480k drawn, 0.8 MB (37 and 23 unique meshes, instanced). Cables are most of the flood's: thin them if it's slow.
