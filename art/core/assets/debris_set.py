"""debris_set: six falling chunks, separate objects (debris_1 to debris_6), each with its origin at its own centre. Concrete off the
stairs (a broken piece of steps, a landing's painted edge, rubble with its rebar) and steel (a torn I-beam stub, a bent plate).

The nodes stand spread out in a cluster over z 0, tops round z 15; the one clip, debris_set, 2 s, has them tumble down past z 0, but
each works alone: take a node, drop it where it's wanted and scrub or spin it as the road likes."""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'debris_set'
DUR = 2.0
FPS = 24
GRAVITY = 12.0
SCALE = 1.25  # Bold at the scene's pixel: the biggest about 4 m across.
kit = A.begin()
M = _mats.mats(kit)
CONC, STAIN, RUST, STEEL, HAZ = range(5)
MATS = [M['wet_concrete'], M['stained_concrete'], M['rust'], M['riveted_steel'], M['hazard']]
rnd = random.Random(31)

# Each lit round itself, as a falling thing lit from two sides is: red from a strip one side, green from below, a little grey from above.
RED = (1.0, 0.07, 0.04)
GREEN = (0.2, 0.9, 0.35)
AMBIENT = (0.22, 0.23, 0.21)


def rough(bm, sizes, mat):
    """A broken block: a box's corners knocked about, some cut off, its hull. Big flat faces and hard edges, as snapped concrete has."""
    pts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                c = Vector((sx * sizes[0], sy * sizes[1], sz * sizes[2]))
                c += Vector((rnd.uniform(-0.3, 0.3) * sizes[0], rnd.uniform(-0.3, 0.3) * sizes[1], rnd.uniform(-0.3, 0.3) * sizes[2]))
                if rnd.random() < 0.6:  # Knocked off: three points, a little way in along the corner's edges.
                    k = rnd.uniform(0.25, 0.6)
                    pts.append(c - Vector((sx * sizes[0] * k, 0, 0)))
                    pts.append(c - Vector((0, sy * sizes[1] * k, 0)))
                    pts.append(c - Vector((0, 0, sz * sizes[2] * k)))
                else:
                    pts.append(c)
    vs = [bm.verts.new(p) for p in pts]
    res = bmesh.ops.convex_hull(bm, input=vs, use_existing_faces=False)
    for g in res['geom_interior'] + res['geom_unused']:
        if isinstance(g, bmesh.types.BMVert) and g.is_valid:
            bm.verts.remove(g)
    for f in bm.faces:
        f.material_index = mat


def rebar(bm, p, d, length):
    d = Vector(d).normalized()
    side = d.orthogonal().normalized()
    bend = (d + side * rnd.uniform(-0.7, 0.7) + Vector((0, 0, rnd.uniform(-0.4, 0.4)))).normalized()
    p = Vector(p)
    path = [p - d * 0.2, p + d * length * 0.55, p + d * length * 0.55 + bend * length * 0.45]
    kit.sweep(bm, path, kit.circle_profile(0.105, 3), mat=RUST, caps=False)


def steps_chunk():
    """Two broken steps with their slab: jagged prism."""
    bm = bmesh.new()
    prof = [(-1.2, 0.5), (0.0, 0.5), (0.0, 0.0), (1.2, 0.0), (1.2, -0.4), (0.75, -0.75), (-0.45, -0.65), (-1.2, -0.1)]
    ring = []
    for y, wob in ((-1.7, 0.1), (1.7, -0.15)):
        ring.append([bm.verts.new((x + wob * (0.3 if i % 3 else 1), y + rnd.uniform(-0.35, 0.35), z)) for i, (x, z) in enumerate(prof)])
    n = len(prof)
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((ring[0][i], ring[0][j], ring[1][j], ring[1][i]))
        f.material_index = CONC if i in (0, 1, 2) else STAIN
    bm.faces.new(ring[0]).material_index = STAIN
    bm.faces.new(ring[1]).material_index = STAIN
    rebar(bm, (1.0, -1.5, -0.3), (0.6, -1, -0.2), 1.3)
    rebar(bm, (0.2, 1.5, -0.3), (0.2, 1, 0.15), 1.5)
    rebar(bm, (0.9, 0.8, -0.35), (1, 0.2, -0.2), 1.0)
    return bm


def boulder():
    bm = bmesh.new()
    rough(bm, (1.5, 1.2, 1.0), CONC)
    rebar(bm, (0.9, 0.5, 0.3), (1, 0.4, 0.3), 1.5)
    rebar(bm, (-0.8, -0.4, 0.4), (-0.9, -0.3, 0.5), 1.2)
    rebar(bm, (0.2, -0.8, -0.2), (0.2, -1, -0.3), 1.0)
    return bm


def rubble():
    bm = bmesh.new()
    rough(bm, (1.05, 0.8, 0.6), STAIN)
    rebar(bm, (0.5, 0.2, 0.3), (0.8, 0.3, 0.6), 1.1)
    return bm


def i_stub():
    """A torn I-beam stub, 3 long, twisted a little at the torn end."""
    bm = bmesh.new()
    f, d, w, t = 0.55, 0.7, 0.1, 0.15
    prof = [(-f, d), (f, d), (f, d - t), (w, d - t), (w, -d + t), (f, -d + t), (f, -d), (-f, -d), (-f, -d + t), (-w, -d + t), (-w, d - t), (-f, d - t)]
    rings = []
    for s, (x, tw, sc) in enumerate(((-1.6, 0.0, 1.0), (0.3, 0.0, 1.0), (1.35, 0.22, 0.93))):
        c, n_ = math.cos(tw), math.sin(tw)
        rings.append([bm.verts.new((x + (0.18 * (1 if k % 3 == 0 else -1) if s == 2 else 0.0), sc * (a * c - b * n_), sc * (a * n_ + b * c))) for k, (a, b) in enumerate(prof)])
    for a, b in zip(rings, rings[1:]):
        for i in range(12):
            j = (i + 1) % 12
            bm.faces.new((a[i], a[j], b[j], b[i])).material_index = RUST
    bm.faces.new(rings[0]).material_index = STEEL
    bm.faces.new(rings[-1]).material_index = STEEL
    return bm


def bent_plate():
    """A steel plate folded by the fall, its bolted edge torn."""
    bm = bmesh.new()
    xs = [(-1.5, 0.0, 1.0), (-0.55, 0.0, 1.1), (0.35, 0.3, 0.95), (1.25, 0.95, 0.7)]
    rings = []
    for x, z, h in xs:
        rings.append([bm.verts.new(p) for p in ((x, -h, z + 0.08), (x, h + 0.1 * x, z + 0.08), (x, h + 0.1 * x, z - 0.08), (x, -h, z - 0.08))])
    for a, b in zip(rings, rings[1:]):
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((a[i], a[j], b[j], b[i])).material_index = STEEL if i == 0 else RUST
    bm.faces.new(rings[0]).material_index = RUST
    bm.faces.new(rings[-1]).material_index = RUST
    # A rib down it, reading at the scene's pixel as a shape.
    kit.add_box(bm, (-0.95, 0.0, 0.2), (0.3, 1.5, 0.28), mat=RUST)
    return bm


def landing_edge():
    """A slab of landing with its painted hazard edge."""
    bm = bmesh.new()
    poly = [(-1.7, -1.0), (1.7, -1.0), (1.9, 0.1), (1.1, 0.6), (0.95, 1.25), (-0.4, 1.0), (-1.1, 1.3), (-1.85, 0.2)]
    top = [bm.verts.new((x, y, 0.2)) for x, y in poly]
    low = [bm.verts.new((x, y, -0.22 + rnd.uniform(-0.1, 0.1))) for x, y in poly]
    f = bm.faces.new(top)
    f.material_index = CONC
    bm.faces.new(list(reversed(low))).material_index = STAIN
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((top[i], low[i], low[j], top[j]))
        f.material_index = HAZ if i == 0 else CONC
    # The paint carries over onto the top: a strip along that edge.
    kit.add_quad(bm, [(-1.7, -1.0, 0.205), (1.7, -1.0, 0.205), (1.72, -0.55, 0.205), (-1.72, -0.55, 0.205)], mat=HAZ)
    rebar(bm, (1.3, 0.3, 0.0), (1, 0.5, 0.1), 1.2)
    rebar(bm, (-0.7, 1.0, 0.0), (-0.2, 1, 0.1), 1.3)
    return bm


MAKERS = [steps_chunk, boulder, rubble, i_stub, bent_plate, landing_edge]
# Their places in the cluster (none overlaps), when each one lets go, and how it turns.
PLACES = [(-1.5, -5.0, 16.0), (4.0, 1.0, 17.5), (-6.0, 3.0, 13.5), (0.5, 5.5, 15.0), (-5.0, -1.5, 19.0), (2.5, -3.5, 12.0)]
DELAYS = [0.0, 0.3, 0.12, 0.45, 0.2, 0.05]
pieces = []
for i, (make, place) in enumerate(zip(MAKERS, PLACES)):
    bm = make()
    bmesh.ops.scale(bm, vec=(SCALE, SCALE, SCALE), verts=bm.verts)
    bmesh.ops.split_edges(bm, edges=bm.edges[:])  # Each face on its own vertices, so the light picks out its facets.
    me = kit.mesh_from(f'debris_{i + 1}', bm, MATS)
    kit.box_uvs(me, 0.3)
    # Its origin exactly at its own centre (the bounding box's).
    pts = [v.co for v in me.vertices]
    lo = Vector([min(p[k] for p in pts) for k in range(3)])
    hi = Vector([max(p[k] for p in pts) for k in range(3)])
    me.transform(Matrix.Translation(-(lo + hi) / 2))
    me.update()
    s = rnd.choice((-1, 1))
    lights = [((-3.0, s * 2.4, 0.4), RED, 5.0, 3.6), ((1.5, -s * 1.5, -3.5), GREEN, 4.5, 0.75), ((0.4, 0.3, 3.5), (0.62, 0.62, 0.56), 4.0, 0.3)]
    kit.bake_light(me, lights, ambient=AMBIENT)
    o = A.obj(me, f'debris_{i + 1}', loc=place)
    o.rotation_mode = 'QUATERNION'
    axis = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.5, 0.5))).normalized()
    pieces.append((o, Vector(place), DELAYS[i], axis, math.radians(rnd.uniform(110, 240)), rnd.uniform(-1.2, 1.2), rnd.uniform(-1.2, 1.2)))

scene = bpy.context.scene
scene.render.fps = FPS
frames = round(DUR * FPS)
scene.frame_start, scene.frame_end = 0, frames
action = bpy.data.actions.new(NAME)  # One action, a slot per object: the exporter makes that one clip, named as the asset.
for o, place, delay, axis, spin, vx, vy in pieces:
    ad = o.animation_data_create()
    ad.action = action
    ad.action_slot = action.slots.new('OBJECT', o.name)
    prev = None
    for f in range(frames + 1):
        t = f / FPS
        u = max(0.0, t - delay)
        o.location = place + Vector((vx * u, vy * u, -0.5 * GRAVITY * u * u))
        q = Quaternion(axis, spin * u)
        if prev is not None and prev.dot(q) < 0:
            q = -q
        prev = q.copy()
        o.rotation_quaternion = q
        o.keyframe_insert('location', frame=f)
        o.keyframe_insert('rotation_quaternion', frame=f)

EYE = (-14.5, -1.0, 2.5)
LOOK = (0.0, 0.0, 5.5)
scene.frame_set(frames // 2)
A.finish(kit, NAME, budget=500, animations=True, eye=EYE, look_at=LOOK, fov=88.0)

# The stills again against the shaft's dark (not exported): start, middle, end.
wbm = bmesh.new()
kit.add_box(wbm, (0.0, 0.0, 5.0), (80.0, 70.0, 80.0), mat=0)
bmesh.ops.reverse_faces(wbm, faces=wbm.faces[:])
wme = kit.mesh_from('backdrop', wbm, [M['dark']], recalc=False)
kit.bake_light(wme, [], ambient=(0.3, 0.3, 0.3))
A.obj(wme, 'backdrop')
for label, f in (('start', 0), ('mid', frames // 2), ('end', frames)):
    scene.frame_set(f)
    A.still(f'{NAME}-{label}', eye=EYE, look_at=LOOK, fov=88.0)
scene.frame_set(frames // 2)
A.still(NAME, eye=EYE, look_at=LOOK, fov=88.0)
