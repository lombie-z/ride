"""The fifth zone, inside the desert's building (art/reference/concept-core-*): a vault tunnel on from the gate, the white
specimen corridor, a vast hall of code-faced server towers, the chamber of the core. Assembled from its groups' modules
(art/core/: gate, lab, tanks, servers, chamber; art/core/kit.py is what they share, including the road), plus the road
deck itself and the contract every city has: City5.RoadPath, RoadIn, BikeMark, ArrivalCam. It's the last zone, so no
RoadOut. Builds art/city5.blend and exports art/out/city5.glb (Draco): look at it first, then copy it to public/models/ with the site's numbers
(LAB_DOOR in lib/ride.ts: it's kit.LAB door_s) in one go.
Run: /opt/homebrew/bin/blender --background --factory-startup --python art/build-city5.py
     (CITY5_ONLY=lab,tanks builds just those modules; a module not there yet is skipped.)
"""
import importlib
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'core'))
sys.dont_write_bytecode = True
import kit  # noqa: E402
import road_sections  # noqa: E402

GLB = os.path.join(kit.ROOT_DIR, 'art', 'out', 'city5.glb')
BLEND = os.path.join(HERE, 'city5.blend')
assert road_sections.HALL_X == kit.LAB_END, (road_sections.HALL_X, kit.LAB_END)
root = kit.begin()

# --- The groups ---------------------------------------------------------------------------------------------------------
ONLY = os.environ.get('CITY5_ONLY')
modules = {}
for name in ('gate', 'lab', 'tanks', 'servers', 'chamber'):
    if ONLY and name not in ONLY.split(','):
        continue
    if not os.path.exists(os.path.join(HERE, 'core', name + '.py')):
        print('module not there yet:', name)
        continue
    mod = importlib.import_module(name)
    mod.place(kit, mod.build(kit))
    modules[name] = mod

# --- The road: its deck, centre dashes, and the bike's line (the centreline, easing to its spot over the last stretch). --
chamber = modules.get('chamber')
BIKE = getattr(chamber, 'BIKE', {'d': -3.0, 'yaw_deg': -8.0})
ARRIVAL = getattr(chamber, 'ARRIVAL', None)
PARK = 60.0
END_S = kit.ROAD_LEN
bike_at = kit.along(END_S, BIKE['d'])
bike_yaw = kit.heading(END_S) + math.radians(BIKE['yaw_deg'])


def hermite(p0, h0, p1, h1, m0, m1, n):
    t0 = Vector((math.cos(h0), math.sin(h0), 0)) * m0
    t1 = Vector((math.cos(h1), math.sin(h1), 0)) * m1
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t, -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        out.append(p0 * a + t0 * b + p1 * c + t1 * d)
    return out


line = [kit.along(s) for s in kit.frange(0.0, END_S - PARK, 2.0)]
line += hermite(line[-1], kit.heading(END_S - PARK), bike_at, bike_yaw, 30.0, 16.0, 60)[1:]
ROAD_LINE = kit.resample_exact(line, 2.0)
ROAD_LEN = kit.poly_len(line)

DECK_END = END_S + 30.0
HALF = kit.ROAD_W / 2
ACROSS = [1.0, 0.5, -0.5, -1.0]
# It's in two, at the lab's doors (art/core/SECTIONS.md): the lab's part, group Road, runs on to the lip of the stairwell's long flight; the
# hall's, group RoadHall, from where the tunnel comes out (road_sections.py HALL_X), and it sinks with the hall on the site. Both are on the same
# plane and pattern, so with the hall unsunk their couple of metres' overlap doesn't show.
LIP = road_sections.LIP_X
gate = modules.get('gate')


def deck_part(name, s0, s1, grp):
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    prev = None
    rows = sorted({s0, s1, *(s for s in kit.frange(0.0, DECK_END, 6.0) if s0 < s < s1)})
    for s in rows:
        cur = [bm.verts.new(kit.along(s, HALF * d)) for d in ACROSS]
        if prev:
            for j in range(len(ACROSS) - 1):
                f = bm.faces.new((prev[0][j], prev[0][j + 1], cur[j + 1], cur[j]))
                u0, u1 = (1 - ACROSS[j]) / 2, (1 - ACROSS[j + 1]) / 2
                for lp, (u, v) in zip(f.loops, ((u0, prev[1]), (u1, prev[1]), (u1, s), (u0, s))):
                    lp[uv].uv = (u, v / 27.0)
        prev = (cur, s)
    bm.normal_update()
    deck = bpy.data.meshes.new(f'City5.{name}')
    bm.to_mesh(deck)
    bm.free()
    deck.materials.append(kit.MAT['asphalt'])
    # (The gate tunnel's lamps pool on it; past that it's the road's mirror that shows, the deck only at its very edges.)
    kit.bake_light(deck, gate.lights() if gate and hasattr(gate, 'lights') else [], ambient=(0.3, 0.32, 0.3))
    kit.static(name, deck, grp)


deck_part('Deck', 0.0, LIP, 'Road')
deck_part('DeckHall', kit.LAB_END, DECK_END, 'RoadHall')

paint = kit.material('City5Paint', (0.72, 0.72, 0.68), 0.7, vcol=False, emission=(0.72, 0.74, 0.68), strength=0.45)
bm = bmesh.new()
kit.add_box(bm, (1.5, 0, 0), (3.0, 0.16, 0.001))
dash = kit.piece('Dash', kit.mesh_from('City5.Dash', bm, paint))
for s in kit.frange(4.0, END_S, 9.0):
    # (Standing just proud of the road's mirror, components/three/wet-road.tsx. Each on its part of the deck.)
    if s + 3.0 <= LIP or s >= kit.LAB_END:
        kit.put(dash, kit.along(s, 0.0, 0.05), kit.heading(s), grp='Road' if s < kit.LAB_END else 'RoadHall')


# --- The contract --------------------------------------------------------------------------------------------------------
def empty(name, loc, yaw=None, props=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.parent = root
    e.location = loc
    if yaw is not None:
        e.rotation_euler = (0, 0, yaw)
    for k, v in (props or {}).items():
        e[k] = v
    return e


def r4(v):
    return [round(float(c), 4) for c in v]


if ARRIVAL is None:
    # (A stand-in until the chamber's: behind the bike, looking on up the road.)
    ARRIVAL = {'eye': tuple(bike_at + Vector((-5, 1.5, 0.8))), 'look': tuple(bike_at + Vector((30, 0, 6))), 'fov': 55.0}
empty('City5.ArrivalCam', Vector(ARRIVAL['eye']), props={'EYE': r4(ARRIVAL['eye']), 'LOOK': r4(ARRIVAL['look']), 'FOV': round(ARRIVAL['fov'], 3)})
empty('City5.BikeMark', bike_at, yaw=bike_yaw, props={'YAW': math.degrees(bike_yaw)})
empty('City5.RoadIn', Vector((0, 0, 0)), yaw=0.0, props={'LENGTH': round(ROAD_LEN, 2), 'note': 'the road hands over here heading local +X'})
empty('City5.RoadPath', Vector((0, 0, 0)), props={'points': [[round(p.x, 3), round(p.y, 3)] for p in ROAD_LINE], 'length': round(ROAD_LEN, 2), 'step': 2.0, 'width': kit.ROAD_W})

# --- Stats, save, export -------------------------------------------------------------------------------------------------
meshes = [o for o in root.children_recursive if o.type == 'MESH']
uniq = {o.data.name: o.data for o in meshes}
tris_unique = sum(kit.tris(m) for m in uniq.values())
tris_drawn = sum(kit.tris(o.data) for o in meshes)
by = {}
for o in meshes:
    g = o.parent.name if o.parent else '?'
    by[g] = by.get(g, 0) + kit.tris(o.data)
print('objects', len(meshes), 'unique meshes', len(uniq), 'tris unique', tris_unique, 'drawn', tris_drawn)
print(json.dumps(by, indent=0))
os.makedirs(os.path.dirname(GLB), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
for o in bpy.context.view_layer.objects:
    o.select_set(False)
for o in root.children_recursive:
    o.select_set(True)
root.select_set(True)
bpy.ops.export_scene.gltf(filepath=GLB, export_format='GLB', use_selection=True, export_apply=True,
                          export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
                          export_draco_position_quantization=14, export_draco_normal_quantization=8,
                          export_draco_texcoord_quantization=10, export_draco_color_quantization=8,
                          export_vertex_color='ACTIVE', export_image_format='AUTO', export_image_quality=80,
                          export_gpu_instances=True,
                          export_yup=True, export_cameras=False, export_lights=False, export_extras=True)
print('exported', GLB, os.path.getsize(GLB), 'road', round(ROAD_LEN, 1))
