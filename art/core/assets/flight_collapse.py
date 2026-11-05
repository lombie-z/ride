"""flight_collapse: a flight breaking away and falling, one 2 s glTF clip (object transforms) to scrub by the ride's distance.

Origin: the top step's back edge, road centre, on its tread, as stair_flight_12: at the clip's start this is that flight, with the same
chipped steps, and its rails (so don't also place rail_12 here). The break runs from the far end back toward the rider, and the
pieces go over toward -Y, the road's right, where the shaft is. Each piece's origin is its own centre."""
import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'flight_collapse'
DUR = 2.0
FPS = 24
STEPS, TREAD, RISE, HALF = 10, 1.2, 0.5, 5.9
STR_OUT, STR_TOP, STR_BOT, SOFFIT = 6.3, 0.1, -1.0, -0.7
LEN = STEPS * TREAD
RAIL_Y, RAIL_H = 6.1, 1.1
GRAVITY = 15.0
kit = A.begin()
m = _mats.mats(kit)
mats = [m['wet_concrete'], m['stained_concrete'], m['riveted_steel'], m['rust'], m['hazard']]
WET, STAINED, STEEL, RUST, HAZ = range(5)
PALE = 3.2  # (A fresh break's vertex colour gain, over the flight's dim light: pale, against the wet dark tops.)


def line(x):
    return -RISE / TREAD * x


solid = bmesh.new()
gain_layer = solid.faces.layers.float.new('gain')


def face(vs, mat, g=1.0):
    f = solid.faces.new(vs)
    f.material_index = mat
    f[gain_layer] = g
    return f


# The steps: stair_flight_12's own columns and chips (its seed, in its order), but one closed solid, so that a break can be capped.
rng = np.random.default_rng(12)
YS = [-HALF, -4.5, -2.3, 0.0, 2.3, 4.5, HALF]
cols = [[] for _ in YS]  # Each column's profile, top step to the far end, then back along the soffit.
wets = []
for i in range(STEPS):
    xb, xn, z = i * TREAD, (i + 1) * TREAD, -i * RISE
    ch = 0.09 + 0.1 * rng.random(len(YS))
    dz = 0.07 + 0.09 * rng.random(len(YS))
    for k in rng.choice(len(YS), 2, replace=False):
        ch[k] += 0.16
        dz[k] += 0.1
    wets.append(0.72 + 0.34 * rng.random(len(YS) - 1))
    for j, y in enumerate(YS):
        cols[j].extend([(xb, y, z), (xn - ch[j], y, z), (xn, y, z - dz[j]), ])
ze = -STEPS * RISE
for j, y in enumerate(YS):
    cols[j].append((LEN, y, ze))
    for x in (LEN, 6.0, 0.0):
        cols[j].append((x, y, line(x) + SOFFIT))
rows = [[solid.verts.new(p) for p in c] for c in cols]
n_prof = len(rows[0])
for j in range(len(YS) - 1):
    a, b = rows[j], rows[j + 1]
    for k in range(n_prof):
        q = (a[k], b[k], b[(k + 1) % n_prof], a[(k + 1) % n_prof])
        if k < STEPS * 3:
            step, part = k // 3, k % 3
            if part == 0:
                face(q, WET, float(wets[step][j]))    # Tread: wet.
            elif part == 1:
                face(q, WET, 1.3)                     # The worn edge: bare and pale.
            else:
                face(q, STAINED, 0.42)                # Riser.
        else:
            face(q, STAINED, 0.7)                     # The soffit and the ends.
face(rows[0], STAINED, 0.5)
face(list(reversed(rows[-1])), STAINED, 0.5)

# The stringers: deep sloped beams each side, closed.
for s in (-1, 1):
    n = 4
    rings = []
    for i in range(n + 1):
        x = LEN * i / n
        rings.append([solid.verts.new((x, s * y, line(x) + dz)) for y, dz in ((HALF, STR_TOP), (STR_OUT, STR_TOP), (STR_OUT, STR_BOT), (HALF, STR_BOT))])
    for a, b in zip(rings, rings[1:]):
        for k, g in enumerate((0.9, 1.0, 0.6, 0.6)):
            face((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]), STAINED, g)
    face(rings[0], STAINED, 0.6)
    face(list(reversed(rings[-1])), STAINED, 0.6)


def prism(profile, y0, mat, mat_edges=None, g=1.0):
    """A closed (y, height over the slope) section down the whole flight, as rail_12's."""
    rs = [[solid.verts.new((x, y0 + y, line(x) + dz)) for y, dz in profile] for x in (0.0, LEN)]
    n = len(profile)
    for k in range(n):
        j = (k + 1) % n
        face((rs[0][k], rs[0][j], rs[1][j], rs[1][k]), mat_edges[k] if mat_edges else mat, g)
    face(rs[0], mat, g)
    face(list(reversed(rs[1])), mat, g)


# The rails, as rail_12 draws them, in one length each side: the breaks cut them.
RAIL_GAIN = 3.4
for s in (-1, 1):
    R = 0.085
    prism([(c, RAIL_H - R + q * 1.083) for c, q in kit.circle_profile(R, 6)], s * RAIL_Y, STEEL, g=RAIL_GAIN)
    prism([(-0.04, 0.58), (0.04, 0.58), (0.04, 0.68), (-0.04, 0.68)], s * RAIL_Y, STEEL, g=RAIL_GAIN)
    T = 0.055
    prism([(T, -0.45), (T, 0.32), (-T, 0.32), (-T, -0.45)], s * RAIL_Y, RUST, mat_edges=[RUST, HAZ, RUST, RUST], g=RAIL_GAIN)
    W = 0.11
    for i in range(8):
        x = W / 2 + (LEN - W) * i / 7
        z0, z1 = line(x) - 0.1, line(x) + RAIL_H - 0.085
        c = [(x - W / 2, -W / 2), (x + W / 2, -W / 2), (x + W / 2, W / 2), (x - W / 2, W / 2)]
        low = [solid.verts.new((cx, s * RAIL_Y + cy, z0)) for cx, cy in c]
        top = [solid.verts.new((cx, s * RAIL_Y + cy, z1)) for cx, cy in c]
        for k in range(4):
            j = (k + 1) % 4
            face((low[k], low[j], top[j], top[k]), STEEL, RAIL_GAIN)

# Where the breaks go: Voronoi cells of these seeds (x along, y across, an offset off the slope), so the pieces interlock.
SEEDS = [(0.9, -2.8, 0.1), (1.3, 3.2, -0.2), (3.7, 0.2, 0.15), (5.2, -4.3, -0.1), (5.6, 4.1, 0.2), (7.0, -0.5, -0.25),
         (9.0, 3.2, 0.1), (9.4, -3.4, 0.25), (11.2, 0.3, -0.1)]
seeds = [Vector((x, y, line(x) - 0.3 + dz)) for x, y, dz in SEEDS]
RED = (1.0, 0.07, 0.04)
GREEN = (0.3, 1.0, 0.42)
lights = [((x, s * 6.0, line(x) + 1.0), RED, 3.6, 2.6) for x, s in ((2.5, 1), (9.5, 1), (2.5, -1), (9.5, -1))]
lights.append(((LEN + 8, 0, line(LEN) - 2.0), GREEN, 16.0, 0.8))
lights.append(((6.5, 0.8, line(6.5) + 7.0), (0.72, 0.8, 0.72), 7.0, 0.8))
AMBIENT = (0.2, 0.215, 0.2)
rnd = random.Random(7)


def rebar(bm, layer, p, d, length):
    """A bent bar out of a break: thick for the scene's pixel."""
    side = d.orthogonal().normalized()
    bend = (d + side * rnd.uniform(-0.6, 0.6) + Vector((0, 0, rnd.uniform(-0.5, 0.2)))).normalized()
    path = [p - d * 0.15, p + d * length * 0.55, p + d * length * 0.55 + bend * length * 0.45]
    kit.sweep(bm, path, kit.circle_profile(0.075, 3), mat=RUST, caps=False)
    for f in bm.faces:
        if f[layer] == 0.0:  # (Only the new faces haven't one yet.)
            f[layer] = RAIL_GAIN


def cell(i):
    """Everything in seed i's cell, its breaks capped and given bars."""
    bm = solid.copy()
    layer = bm.faces.layers.float['gain']
    caps = []
    me_seed = seeds[i]
    for j, other in enumerate(seeds):
        if j == i:
            continue
        n = (other - me_seed).normalized()
        co = (other + me_seed) / 2
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        res = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-4, plane_co=co, plane_no=n, clear_outer=True)
        cut = [e for e in res['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
        if not cut:
            continue
        filled = bmesh.ops.edgeloop_fill(bm, edges=cut)
        for f in filled['faces']:
            f.material_index = WET
            f[layer] = PALE
            caps.append((f, n))
    live = [(f, n) for f, n in caps if f.is_valid]
    bars = []
    for f, n in live:
        if f.calc_area() < 0.28:
            continue
        cen = f.calc_center_median()
        vs = [v.co.copy() for v in f.verts]
        for _ in range(2 if f.calc_area() > 1.2 else 1):
            target = rnd.choice(vs)
            bars.append((cen + (target - cen) * rnd.uniform(0.15, 0.55), (n + Vector((rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), rnd.uniform(-0.2, 0.3)))).normalized(), rnd.uniform(0.7, 1.5)))
    for p, d, length in bars[:3]:
        rebar(bm, layer, p, d, length)
    me = bpy.data.meshes.new(f'flight_piece_{i}')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for mat in mats:
        me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = False
    kit.box_uvs(me, 0.25)
    kit.bake_light(me, lights, ambient=AMBIENT)
    # Each face's gain over the light, per corner: a break's edge can then be pale beside its dark tread.
    ca = me.color_attributes['AO']
    vi = np.zeros(len(me.loops), np.int64)
    me.loops.foreach_get('vertex_index', vi)
    cols_now = np.zeros(len(me.loops) * 4, np.float32)
    ca.data.foreach_get('color', cols_now)
    cols_now = cols_now.reshape(-1, 4)
    gains = me.attributes['gain'].data
    for poly in me.polygons:
        g = gains[poly.index].value
        for li in poly.loop_indices:
            cols_now[li, :3] = np.clip(cols_now[li, :3] * g, 0, 1)
    ca.data.foreach_set('color', cols_now.ravel())
    me.attributes.remove(me.attributes['gain'])
    # Its origin at its own centre.
    pts = [v.co for v in me.vertices]
    c = sum(pts, Vector()) / len(pts)
    me.transform(Matrix.Translation(-c))
    me.update()
    return A.obj(me, f'flight_piece_{i}', loc=c), c


pieces = []
for i in range(len(seeds)):
    o, c = cell(i)
    o.rotation_mode = 'QUATERNION'
    pieces.append((o, c))
solid.free()


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


LEAD = 0.28  # A piece's crack opening before it goes.
motions = []
rm = random.Random(21)
for o, c in pieces:
    # The far end first, the wave reaching the top step last; the shaft side of each band a little ahead.
    delay = 0.12 + 0.95 * (LEN - c.x) / LEN + 0.07 * (c.y + 6) / 12 + rm.uniform(-0.03, 0.03)
    # Whole-body tumble: over toward the shaft (+X axis), with some pitch.
    axis = Vector((1.0, rm.uniform(-0.55, 0.55), rm.uniform(-0.35, 0.35))).normalized()
    spin = math.radians(rm.uniform(45, 105))
    side = -rm.uniform(1.2, 6.2)
    along = rm.uniform(-1.0, 3.4)
    crack_axis = Vector((rm.uniform(-1, 1), rm.uniform(-1, 1), rm.uniform(-0.3, 0.3))).normalized()
    motions.append((delay, axis, spin, side, along, crack_axis))


def pose(i, t):
    c = pieces[i][1]
    delay, axis, spin, side, along, crack_axis = motions[i]
    pre = smooth((t - (delay - LEAD)) / LEAD)
    q = Quaternion(crack_axis, math.radians(2.6) * pre)
    loc = c + Vector((0.08, 0.0, -0.14)) * pre
    u = max(0.0, t - delay)
    if u > 0:
        loc = loc + Vector((along * u, side * u, -0.5 * GRAVITY * u * u))
        q = Quaternion(axis, spin * u) @ q
    return loc, q


scene = bpy.context.scene
scene.render.fps = FPS
frames = round(DUR * FPS)
scene.frame_start, scene.frame_end = 0, frames
action = bpy.data.actions.new(NAME)  # One action, a slot per piece: the exporter makes that one clip, named as the asset.
for i, (o, _c) in enumerate(pieces):
    ad = o.animation_data_create()
    ad.action = action
    ad.action_slot = action.slots.new('OBJECT', o.name)
    prev = None
    for f in range(frames + 1):
        loc, q = pose(i, f / FPS)
        if prev is not None and prev.dot(q) < 0:
            q = -q
        prev = q.copy()
        o.location = loc
        o.rotation_quaternion = q
        o.keyframe_insert('location', frame=f)
        o.keyframe_insert('rotation_quaternion', frame=f)

EYE = (-4.0, 1.0, 5.6)
LOOK = (8.0, -2.0, -7.5)
scene.frame_set(frames // 2)
A.finish(kit, NAME, budget=1800, animations=True, eye=EYE, look_at=LOOK)

# The stills again against the shaft's dark (not exported), since a clear background hides nothing: start, middle, end.
wbm = bmesh.new()
kit.add_box(wbm, (10.0, -8.0, -25.0), (90.0, 60.0, 80.0), mat=0)
bmesh.ops.reverse_faces(wbm, faces=wbm.faces[:])
wme = kit.mesh_from('backdrop', wbm, [m['dark']], recalc=False)
kit.bake_light(wme, [], ambient=(0.3, 0.3, 0.3))
A.obj(wme, 'backdrop')
for label, f in (('start', 0), ('mid', frames // 2), ('end', frames)):
    scene.frame_set(f)
    A.still(f'{NAME}-{label}', eye=EYE, look_at=LOOK)
scene.frame_set(frames // 2)
A.still(NAME, eye=EYE, look_at=LOOK)
