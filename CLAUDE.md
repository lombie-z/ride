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
components/three/speed-blur.ts        # Motion blur + the zone features' looks: iridescence, heartbeat veins, flames
components/three/ride.tsx             # The ride: button entrance, getting on, driving, zones, features, morphs, map timing
components/three/zone-city.tsx        # Loads/places each city after the green one (city2.glb, city3.glb, city4.glb)
components/three/holomap.tsx, holomap-materials.ts  # The map terminal in the rider's hands (hands.glb): 3D land, way back, ride on
components/three/precompile.ts        # Compiles a model's shaders ahead of time, for the post's linear buffer
components/three/throttle-track.ts    # The throttle pill's slingshot track on the tank
components/ride-button.tsx            # The DOM hit areas over the 3D button and the map; gestures per zone
lib/journey.ts                        # Scroll progress, beats, shared per-frame state
lib/ride.ts                           # Ride state, the chrome city's road helpers, muck, constants
lib/course.ts                         # ZONES (green, chrome, hive, desert: city, bike, feature, speed) and the course
lib/look.ts                           # Each zone's light (sky, sun, fog, grade, fill), blended across changes
art/micro-biome.blend                 # Planter, falls and JourneyCam (FogDrog's canyon objects are still in it, hidden on the site)
art/build-journey.py, export-journey.py  # Key JourneyCam, export public/journey.json
art/build-city.py                     # The city from scratch -> art/city.blend, public/models/city.glb
art/build-bike.py                     # The bike from scratch -> art/bike.blend, public/models/bike.glb
art/build-city{2,3,4}.py, build-bike{2,3,4}.py  # Each later zone's city and bike (same contract: RoadIn/RoadPath/RoadOut,
                                      # BikeMark, ArrivalCam; bikes in bike.glb's frame), fitted via art/align*/
art/reference/                        # Concept art (concept-green-city is the landing's target)
```

## World

Blender z up, metres; three's (x, y, z) is Blender's (x, z, -y). The planter floats over the origin and its black falls drop past it to the city floor (z -80). The landing is east of the falls: a straight freeway deck (surface z -11, its wet top placed from the glb's `City.DeckTop` marker), the camera at handlebar height beside the bike looking east across the road at the city. Its framing is fitted to the concept: `art/reference/concept-guides.json` (the shot) and `concept-bike-guides.json` (the bike's parts) trace it, and `python3 art/guides.py render.png out.png [--guides ...]` draws them over a render to check. Blender runs headless from scripts only.

## Zones

The ride runs through zones (lib/course.ts ZONES): the green city, then the chrome city (placed down the street once it's
loaded and the ride's gone on a while), then the hive and the desert, each placed at the end of the one before's
RoadOut when the visitor picks it on the map. Each zone has its own bike (morphed into), cruising speed and throttle
feature: start / surge (hold) / heartbeat (tap on the beat) / slingshot (drag back, let go). Dev: `?feature=` puts a
feature on everywhere; `j` jumps near the plaza ahead, `n` rides on from one.
