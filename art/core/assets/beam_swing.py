"""beam_swing: a hanging beam swinging down across the road, one 1.5 s glTF clip (object transforms) to scrub by the ride's distance.

Origin: the pivot, a line across the road (Y) through the two hinge brackets, which don't move. The beam lies across the road, 14 long
and 1.4 deep like stair_beam_low, hung from the pivot by two straps, and swings in the road's plane (XZ): from up ahead (+X), down
toward the rider, past the bottom at 0.9 s, up to rest on the rider's side at the end. Stand the pivot 13 over the road: its underside
then clears the road by 5.5 at the bottom."""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'beam_swing'
DUR = 1.5
FPS = 24
HALF_LEN = 7.0
DEPTH = 1.4       # The beam, in its swing plane (z at the bottom).
FLANGE = 1.15     # Its flanges' width (x at the bottom): what the rider sees from under and in front.
ARM = 6.8         # Pivot to the beam's centre.
ROAD_BELOW_PIVOT = ARM + DEPTH / 2 + 5.5
STRAP_Y = 5.3     # Straps: outside the rider's way, over the road's edges.
START, STOP = math.radians(72), math.radians(-38)

kit = A.begin()
M = _mats.mats(kit)
RUST, STEEL, CONC, CABLE, HAZ, DARK = range(6)
MATS = [M['rust'], M['riveted_steel'], M['wet_concrete'], M['cable'], M['hazard'], M['dark']]
rnd = random.Random(4)

# Light as the beam hangs at the bottom: red from the wall strips on the rider's side, green up from below.
LIGHTS = [((-5.0, 7.0, -ARM - 1.5), (1.0, 0.08, 0.04), 6.5, 1.5), ((-5.0, -7.0, -ARM + 0.5), (1.0, 0.07, 0.04), 6.5, 1.5),
          ((-2.0, 0.0, -ROAD_BELOW_PIVOT - 2.0), (0.14, 0.7, 0.3), 7.5, 0.7), ((-7.0, 0.0, -ARM + 6.0), (0.5, 0.5, 0.42), 9.0, 0.55)]
AMBIENT = (0.55, 0.56, 0.52)


def i_beam(bm):
    """The beam: an I across the road, split along its length so the light has vertices."""
    f, d, w, t = FLANGE / 2, DEPTH / 2, 0.11, 0.17
    prof = [(-f, d), (f, d), (f, d - t), (w, d - t), (w, -d + t), (f, -d + t), (f, -d), (-f, -d), (-f, -d + t), (-w, -d + t), (-w, d - t), (-f, d - t)]
    segs = 4
    rings = []
    for s in range(segs + 1):
        y = -HALF_LEN + 2 * HALF_LEN * s / segs
        rings.append([bm.verts.new((x, y, -ARM + z)) for x, z in prof])
    for a, b in zip(rings, rings[1:]):
        for i in range(12):
            j = (i + 1) % 12
            bm.faces.new((a[i], a[j], b[j], b[i])).material_index = RUST
    bm.faces.new(rings[0]).material_index = STEEL
    bm.faces.new(rings[-1]).material_index = STEEL
    # Stiffeners in the web, to catch the eye as it swings.
    for y in (-3.5, 0.0, 3.5):
        kit.add_box(bm, (0.0, y, -ARM), (FLANGE * 0.96, 0.16, DEPTH - 2 * t), mat=STEEL)


def hazard_lip(bm):
    """A painted stripe on the bottom flange: what the eye has at the scene's pixel, the moving line of it."""
    n = 7
    w = 2 * HALF_LEN / n
    z = -ARM - DEPTH / 2 - 0.01
    for i in range(n):
        if i % 2 == 0:
            y0 = -HALF_LEN + i * w
            kit.add_quad(bm, [(-FLANGE / 2 + 0.02, y0, z), (-0.05, y0, z), (-0.05, y0 + w, z), (-FLANGE / 2 + 0.02, y0 + w, z)], mat=HAZ)


def straps(bm):
    """Two heavy flat straps up to the pivot, and the pins they turn on."""
    for s in (-1, 1):
        y = s * STRAP_Y
        for k in range(2):
            h = (ARM - DEPTH / 2) / 2
            kit.add_box(bm, (0.0, y, -h * (k + 0.5)), (0.72, 0.3, h), mat=RUST)
        # Its pin: an octagon on the pivot's line.
        path = [Vector((0, y - 0.35, 0)), Vector((0, y + 0.35, 0))]
        kit.sweep(bm, path, kit.circle_profile(0.34, 6), up=Vector((1, 0, 0)), mat=RUST)


def lump(bm, centre, size, n=11):
    """A piece of the ceiling it tore out of, still on it: a rough hull."""
    vs = []
    for _ in range(n):
        d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
        if d.length > 0:
            d.normalize()
        vs.append(bm.verts.new(Vector(centre) + Vector((d.x * size[0], d.y * size[1], d.z * size[2]))))
    res = bmesh.ops.convex_hull(bm, input=vs, use_existing_faces=False)
    for g in res['geom_interior']:
        if isinstance(g, bmesh.types.BMVert):
            bm.verts.remove(g)
    for f in {f for v in vs if v.is_valid for f in v.link_faces}:
        f.material_index = CONC


beam_bm = bmesh.new()
i_beam(beam_bm)
hazard_lip(beam_bm)
straps(beam_bm)
lump(beam_bm, (0.25, -4.9, -ARM + 0.95), (1.05, 1.5, 0.62))
lump(beam_bm, (-0.2, 3.1, -ARM + 0.82), (0.8, 1.05, 0.45), n=9)
beam_me = kit.mesh_from('beam', beam_bm, MATS)
kit.box_uvs(beam_me, 0.14)
kit.bake_light(beam_me, LIGHTS, ambient=AMBIENT)
ca = beam_me.color_attributes['AO']
for poly in beam_me.polygons:
    if poly.material_index == HAZ:  # The paint's old: not the brightest thing on it.
        for li in poly.loop_indices:
            col = ca.data[li].color
            ca.data[li].color = (col[0] * 0.6, col[1] * 0.6, col[2] * 0.6, 1.0)

# The brackets: stubs of the ceiling's steel, fixed, one to a pin.
b = bmesh.new()
for s in (-1, 1):
    y = s * STRAP_Y
    kit.add_box(b, (0.0, y, 0.75), (1.5, 1.3, 0.5), mat=STEEL)
    for side in (-1, 1):
        kit.add_box(b, (0.0, y + side * 0.42, 0.15), (0.9, 0.12, 1.1), mat=RUST)
bracket_me = kit.mesh_from('beam_brackets', b, MATS[:2])
kit.box_uvs(bracket_me, 0.2)
kit.bake_light(bracket_me, [((-4.0, 0.0, -2.0), (1.0, 0.1, 0.05), 6.0, 1.0)], ambient=AMBIENT)
A.obj(bracket_me, 'beam_brackets')

# A torn strap off its far end: it trails the swing.
c = bmesh.new()
pts = [Vector((0.0, 0.0, -2.6 * k / 5)) + Vector((0.14 * math.sin(k * 1.6), 0.08 * math.cos(k * 2.1), 0)) for k in range(6)]
kit.sweep(c, pts, kit.circle_profile(0.16, 3), up=Vector((1, 0, 0)), mat=0, caps=False)
cable_me = kit.mesh_from('beam_strap_torn', c, [M['rust']])
kit.box_uvs(cable_me, 0.4)
kit.bake_light(cable_me, [((-3.0, 0.0, -1.5), (1.0, 0.1, 0.05), 3.0, 1.2)], ambient=AMBIENT)
CABLE_AT = Vector((0.0, -6.2, -ARM - DEPTH / 2 + 0.1))


def swing():
    """theta(t): a damped pendulum, the stiffness and damping searched so that from rest at START it comes to rest at STOP just at the end."""
    def run(k, c, h):
        th, w = START, 0.0
        out = [th]
        for _ in range(round(DUR / h)):
            w += (-k * math.sin(th) - c * w) * h
            th += w * h
            out.append(th)
        return out, w

    best, best_e = None, 1e9
    for ki in range(120):
        for ci in range(30):
            k, c = 2.0 + ki * 0.1, ci * 0.05
            tr, w = run(k, c, 1 / 120)
            e = abs(tr[-1] - STOP) + 0.3 * abs(w)
            if e < best_e:
                best, best_e = (k, c), e
    return run(*best, 1 / 480)[0], best, best_e


TRACE, PARAMS, ERR = swing()
print('SWING params', PARAMS, 'err', ERR, 'bottom at', next(i for i, th in enumerate(TRACE) if th < 0) / (len(TRACE) - 1) * DUR, 'end', math.degrees(TRACE[-1]))


def theta(t):
    u = max(0.0, min(1.0, t / DUR)) * (len(TRACE) - 1)
    i = min(int(u), len(TRACE) - 2)
    f = u - i
    return TRACE[i] * (1 - f) + TRACE[i + 1] * f


def beam_pose(t):
    """About the pivot (Y); a slight roll about the road's axis, one strap taking up before the other, gone at the bottom."""
    th = theta(t)
    roll = math.radians(4.5) * math.sin(th) * (1.0 if th > 0 else 0.4)
    return Quaternion((0, 1, 0), th) @ Quaternion((1, 0, 0), roll)


beam = A.obj(beam_me, 'beam')
beam.rotation_mode = 'QUATERNION'
cable = A.obj(cable_me, 'beam_strap_torn')
cable.rotation_mode = 'QUATERNION'

scene = bpy.context.scene
scene.render.fps = FPS
frames = round(DUR * FPS)
scene.frame_start, scene.frame_end = 0, frames
action = bpy.data.actions.new(NAME)  # One action, a slot per object: the exporter makes that one clip, named as the asset.
for o in (beam, cable):
    ad = o.animation_data_create()
    ad.action = action
    ad.action_slot = action.slots.new('OBJECT', o.name)
prev_b = prev_c = None
for f in range(frames + 1):
    t = f / FPS
    q = beam_pose(t)
    if prev_b is not None and prev_b.dot(q) < 0:
        q = -q
    prev_b = q.copy()
    beam.rotation_quaternion = q
    beam.keyframe_insert('rotation_quaternion', frame=f)
    # It hangs off the beam's end, its own angle a moment behind.
    lag = Quaternion((0, 1, 0), theta(t - 0.16) * 0.8 if t > 0 else START * 0.8)
    if prev_c is not None and prev_c.dot(lag) < 0:
        lag = -lag
    prev_c = lag.copy()
    cable.location = q @ CABLE_AT
    cable.rotation_quaternion = lag
    cable.keyframe_insert('location', frame=f)
    cable.keyframe_insert('rotation_quaternion', frame=f)

# Rider's eye on the road, coming on: pivot's z is ROAD_BELOW_PIVOT above the road.
EYE = (-13.0, -2.5, -ROAD_BELOW_PIVOT + 1.45)
LOOK = (0.0, 0.0, -3.5)
scene.frame_set(frames // 2)
A.finish(kit, NAME, budget=400, animations=True, eye=EYE, look_at=LOOK)

# The stills again against the shaft's dark (not exported): start, middle, end.
wbm = bmesh.new()
kit.add_box(wbm, (0.0, 0.0, -2.0), (70.0, 60.0, 50.0), mat=0)
bmesh.ops.reverse_faces(wbm, faces=wbm.faces[:])
wme = kit.mesh_from('backdrop', wbm, [M['dark']], recalc=False)
kit.bake_light(wme, [], ambient=(0.3, 0.3, 0.3))
A.obj(wme, 'backdrop')
for label, f in (('start', 0), ('mid', frames // 2), ('end', frames)):
    scene.frame_set(f)
    A.still(f'{NAME}-{label}', eye=EYE, look_at=LOOK)
scene.frame_set(frames // 2)
A.still(NAME, eye=EYE, look_at=LOOK)
