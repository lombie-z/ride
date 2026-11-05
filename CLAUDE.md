@AGENTS.md

# Ride

A scroll journey from the blog's clay micro biome (../blog) down into a green gothic city at night, where a biotech bike waits on a wet freeway. Forked from FogDrog (../microbiome): the hero, pixel sweep, ticket and camera scrubbing are its, restyled (black liquid, black lettering, a black-and-green ticket). Next 16, React 19, react-three-fiber 9, drei 10, three 0.186, Tailwind 4, Lenis, Biome. No CMS: copy lives in the code.

`pnpm dev --port 3004` (or the "ride" launch config), `pnpm lint`, `pnpm build`. `?pixel=1` turns off the pixel look; `?nocity`, `?nobike`, `?nofx` and the other `devFlag`s isolate parts in dev.

## File map

```
app/layout.tsx, page.tsx              # Fonts, metadata; the scroll track
components/journey.tsx                # Loading still + lazy canvas + ticket
components/ticket.tsx                 # The ticket in the top right that tears away on the first scroll
components/three/journey-canvas.tsx   # The one fixed canvas
components/three/journey-camera.tsx   # Hero framing, then public/journey.json scrubbed by scroll
components/three/biome.tsx            # The planter glb (micro-biome.glb), its black falls and lighting
components/three/water.ts             # The black oil shader for the planter's liquid
components/three/city.tsx             # city.glb: window facades, wet deck reflector, light beams
components/three/bike.tsx             # bike.glb parked on the deck, night reflections
components/three/sky.tsx              # Night sky dome, green smog fog, the city's rim light; each zone's sky after
components/three/effects.tsx, grade.ts  # Post: bloom, grade (cold green), grain, pixel sweep
components/three/speed-blur.ts        # Motion blur + the zone features' looks: the surge's edge (its look's own), heartbeat veins, flames
components/three/ride.tsx             # The ride: button entrance, getting on, driving, zones, features, morphs, map timing
components/three/drive.tsx, lib/street.ts  # The green city's endless street, its phases by tile: open, side streets, halls through towers, canyon
components/three/street-riders.tsx    # Other riders on it: streaks of light that pass, peel off down the side streets, cross the overpasses
components/three/zone-city.tsx        # Loads/places each city after the green one (city2.glb, city3.glb, city4.glb)
components/three/holomap.tsx, holomap-materials.ts  # The map terminal in the rider's hands (hands.glb): 3D land, way back, ride on
components/three/precompile.ts        # Compiles a model's shaders ahead of time, for the post's linear buffer
components/three/pill-glyph.ts        # The pill's play/pause symbol (over the glbs' modelled chevrons)
components/three/boost-pod.tsx        # The boost button: a rocket on a pod beside the tank, its look per zone, the desert's rail, the core's recharge arc
components/three/digital-ghost.tsx    # The core's boost: the bike into blocks of light, the creature (creature.glb) running in its place
components/three/road-join.tsx        # Where one city's road meets the next: the next's surface reaching back in blotches
components/ride-button.tsx            # The DOM hit areas over the pill, the boost button and the map; gestures per zone
components/rhythm-overlay.tsx, lib/rhythm.ts  # The hive's boost: circles 111 to 666 on the heart's beat, then the boost
components/rhythm-looks/                # Its looks: flesh.ts the hive's, brand.ts kept for the boss (self-contained), ooze, bone and the old classic.ts up for comparing; `?rhythm=a|b|c|d|0`, `y` cycles them in dev
components/memory-overlay.tsx, lib/memory.ts  # A memory lock: tiles in a cross that light in an order, then twist; `ENCRYPTION: SIGILS` or `CHROMA` says what to remember
components/three/section-fx.tsx, section-fx-water.ts, lib/section-fx.ts  # The stairwell's and tunnel's effects: black water (a look-up in the frame so far), spray and splash, steam, sparks, drips; lib/section-audio.ts their sound (`sectionImpact` for what moves)
lib/doors.ts, components/three/core-doors.tsx  # The core's doors, all in one table: a stop on its road, a memory lock to open it, a look; `?door=1..4` plays one, `?memory=a|b|c|d` compares rules
lib/sections.ts, components/three/core-sections.tsx  # The core's stairwell and flooded tunnel (art/core/SECTIONS.md): spliced into its road, speeds in one table, each its own glb (public/models/sections, art/core/publish_sections.py) loaded ahead and dropped after, the bulkhead and moving pieces
components/three/portal.tsx, lib/portal.ts  # The hive's holes: towers across its road (portal.glb), the fall through the dark with eyes, out of another
lib/music.ts                          # The music: each zone's loop, crossfaded over the road, from the press that gets on the bike (public/audio)
lib/journey.ts                        # Scroll progress, beats, shared per-frame state
lib/ride.ts                           # Ride state, the chrome city's road helpers, muck, constants
lib/course.ts                         # ZONES (green, chrome, hive, desert, core: city, bike, feature, speed) and the course
lib/look.ts                           # Each zone's light (sky, sun, fog, grade, fill), blended across changes
art/micro-biome.blend                 # Planter, falls and JourneyCam (FogDrog's canyon objects are still in it, hidden on the site)
art/build-journey.py, export-journey.py  # Key JourneyCam, export public/journey.json
art/build-city.py                     # The city from scratch -> art/city.blend, public/models/city.glb
art/build-bike.py                     # The bike from scratch -> art/bike.blend, public/models/bike.glb
art/build-city{2,3,4}.py, build-bike{2,3,4}.py  # Each later zone's city and bike (same contract: RoadIn/RoadPath/RoadOut,
                                      # BikeMark, ArrivalCam; bikes in bike.glb's frame), fitted via art/align*/
art/build-city5.py, art/core/          # The core: assembled from its groups' modules (gate, lab, tanks, servers, chamber) on art/core/kit.py
art/build-bike5.py, art/build-creature.py  # The core's bike and the thing that runs in its place
art/build-portal.py                   # One of the hive's towers with its lancet opening cut through and black -> public/models/portal.glb
art/audio/                            # The sound: PLAN.md, drums/ (Syntakt), hydrasynth/ (score.py, mix.py, chrome_dream.py), previews/
art/reference/                        # Concept art (concept-green-city is the landing's target)
```

## World

Blender z up, metres; three's (x, y, z) is Blender's (x, z, -y). The planter floats over the origin and its black falls drop past it to the city floor (z -80). The landing is east of the falls: a straight freeway deck (surface z -11, its wet top placed from the glb's `City.DeckTop` marker), the camera at handlebar height beside the bike looking east across the road at the city. Its framing is fitted to the concept: `art/reference/concept-guides.json` (the shot) and `concept-bike-guides.json` (the bike's parts) trace it, and `python3 art/guides.py render.png out.png [--guides ...]` draws them over a render to check. Blender runs headless from scripts only.

## Zones

The ride runs through zones (lib/course.ts ZONES): the green city, then the chrome city (placed down the street once it's
loaded and the ride's gone on a while), then the hive, the desert and the core, each placed at the end of the one before's
RoadOut when the visitor picks it on the map. Each zone has its own bike (morphed into), cruising speed and boost
feature, on the rocket button (the pill's play and pause): start / surge (hold on and keep the pointer on a moving point: lib/trace.ts, components/trace-overlay.tsx; four looks up for choosing in components/trace-looks, `?trace=a|b|c|d`, `t` cycles them in dev) / heartbeat (click the circles, 111 to
666, on the beat) / slingshot (drag back, let go) / ghost (press: lib/ride.ts ride.ghost, a few seconds as data at far greater speed, then a recharge; sealed through the gate). `?at=chrome|hive|desert|core` starts at that zone's plaza, `&s=1300` that far along its road, riding (components/three/start-at.tsx; live too). Dev: `?feature=` puts a feature on everywhere; `j` jumps near the plaza ahead, `n`
rides on from one. Every change between zones is one change, centred on the join (where the next city's road takes over):
sky and light over TRANSITION_LEAD before it to TRANSITION_TAIL after, the bike's morph crossing it as the bike does.

A city's RoadPath can carry `heights` (the desert's, from art/build-city4.py: where a dune crosses the road): the ride
goes up them and flies off their crests (components/three/ride.tsx, lib/ride.ts JUMP).

The core's road stops at its shut doors (lib/doors.ts DOORS, the gate, the lab's, the tunnel's bulkhead, the chamber's mouth): the ride brakes to a halt, even as the ghost, and the door's game opens by itself. Each win in an unbroken run lights a segment; all lit, it opens and the ride goes on. Shut again on a new ride.

Three times on the hive's road (lib/portal.ts PORTALS) a tower stands across it and the road ends in the black of its lancet opening: the
bike rides in, falls for a few seconds through the dark past eyes (the camera on one layer: the world's not drawn at all), and comes out of a hole high in another tower down the road, landing on it. `?noportal` leaves them out.
