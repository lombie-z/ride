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
components/three/sky.tsx              # Night sky dome, green smog fog, the city's rim light
components/three/effects.tsx, grade.ts  # Post: bloom, grade (cold green), grain, pixel sweep
lib/journey.ts                        # Scroll progress, beats, shared per-frame state
art/micro-biome.blend                 # Planter, falls and JourneyCam (FogDrog's canyon objects are still in it, hidden on the site)
art/build-journey.py, export-journey.py  # Key JourneyCam, export public/journey.json
art/build-city.py                     # The city from scratch -> art/city.blend, public/models/city.glb
art/build-bike.py                     # The bike from scratch -> art/bike.blend, public/models/bike.glb
art/reference/                        # Concept art (concept-green-city is the landing's target)
```

## World

Blender z up, metres; three's (x, y, z) is Blender's (x, z, -y). The planter floats over the origin and its black falls drop past it to the city floor (z -80). The landing is east of the falls: a straight freeway deck (surface z -11, its wet top placed from the glb's `City.DeckTop` marker), the camera at handlebar height beside the bike looking east across the road at the city. Its framing is fitted to the concept: `art/reference/concept-guides.json` (the shot) and `concept-bike-guides.json` (the bike's parts) trace it, and `python3 art/guides.py render.png out.png [--guides ...]` draws them over a render to check. Blender runs headless from scripts only.
