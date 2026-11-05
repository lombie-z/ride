"""shutter_slam: a steel shutter dropping part way, a 0.5 s glTF clip (object transforms) to scrub by the ride's distance.

Origin: top centre of the housing. The shutter's plane is YZ, across the road (+X). Stand the origin 12.5 over the road: the guides
then reach the road and the slammed curtain's bottom edge stops at z -7, the road's 5.5 clearance. A chain of slats, so that it's one
unbroken curtain at any point of the clip. The housing and guides don't move."""
import os
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'shutter_slam'
DUR = 0.5
FPS = 48
ROAD_TO_ORIGIN = 12.5
HOUSING_H = 1.5
SLATS = 5
SLAT_H = 1.0
BAR_H = 0.55
HALF_W = 6.75     # the curtain's half width: past the rails at 6.1
STOW_TOP = -0.25  # a stowed slat's top, inside the housing
BAR_PEEK = -1.72  # the bar's bottom edge when up: just out of the housing
HIT = 0.3         # when the bar lands

kit = A.begin()
M = _mats.mats(kit)

# Lit by what's round it: the section's red wall strips low on both sides, the green glow rising from below, all on the rider's side.
LIGHTS = [((-3.0, 6.4, -7.5), (1.0, 0.1, 0.05), 5.0, 1.5), ((-3.0, -6.4, -8.5), (1.0, 0.08, 0.04), 5.0, 1.4),
          ((-5.0, 0.0, -14.0), (0.12, 0.6, 0.25), 11.0, 0.65), ((-4.0, 0.0, 2.5), (0.5, 0.5, 0.42), 5.0, 0.32)]
AMBIENT = (0.62, 0.63, 0.58)


def finish_mesh(name, bm, mats, uv=0.12):
    me = kit.mesh_from(name, bm, mats)
    kit.box_uvs(me, uv)
    return me


def strip(bm, top, height, depth, mat, segs=3):
    """One slat: a ribbed strip across the road, from z top down, its middle standing proud toward the rider."""
    def profile(y):
        h = height
        return [(0.1, y, top), (-depth, y, top - 0.16 * h), (-depth, y, top - 0.84 * h), (0.1, y, top - h)]
    rows = []
    for s in range(segs + 1):
        rows.append([bm.verts.new(p) for p in profile(-HALF_W + 2 * HALF_W * s / segs)])
    for a, b in zip(rows, rows[1:]):
        for i in range(4):
            bm.faces.new((a[i], a[(i + 1) % 4], b[(i + 1) % 4], b[i])).material_index = mat
    bm.faces.new(rows[0]).material_index = mat
    bm.faces.new(rows[-1]).material_index = mat


def slat_mesh(i):
    bm = bmesh.new()
    strip(bm, 0.0, SLAT_H, 0.16, 0)
    return finish_mesh(f'shutter_slat_{i}', bm, [M['rust']])


def bar_mesh():
    """The bottom bar: heavy, with the yellow and black the images paint on edges, so it reads as the moving edge at the scene's pixel."""
    bm = bmesh.new()
    kit.add_box(bm, (0.0, 0.0, -BAR_H / 2), (0.34, 2 * HALF_W, BAR_H), mat=1)
    n = 8
    w = 2 * HALF_W / n
    for i in range(n):
        y0 = -HALF_W + i * w
        lean = 0.3
        mat = 0 if i % 2 == 0 else 1
        kit.add_quad(bm, [(-0.18, y0 + lean, -0.02), (-0.18, y0 + w + lean, -0.02), (-0.18, y0 + w - lean, -BAR_H + 0.02), (-0.18, y0 - lean, -BAR_H + 0.02)], mat=mat)
    me = kit.mesh_from('shutter_bar', bm, [M['hazard'], M['dark']], recalc=False)
    for p in me.polygons:
        p.use_smooth = False
    kit.box_uvs(me, 0.25)
    return me


def frame_mesh():
    bm = bmesh.new()
    # Housing, split so its light has vertices to land on.
    x = 0.8
    seg = 4
    for s in range(seg):
        y0 = -7.3 + 14.6 * s / seg
        kit.add_box(bm, (0.0, y0 + 14.6 / seg / 2, -HOUSING_H / 2), (2 * x, 14.6 / seg, HOUSING_H), mat=0)
    # A heavy lip along its underside.
    kit.add_box(bm, (-0.72, 0.0, -HOUSING_H + 0.1), (0.3, 14.8, 0.34), mat=0)
    # The images' red strips, on its face: all that's bright on it as it comes down.
    for y in (-3.6, 3.6):
        kit.add_quad(bm, [(-0.82, y - 1.4, -0.42), (-0.82, y + 1.4, -0.42), (-0.82, y + 1.4, -0.67), (-0.82, y - 1.4, -0.67)], mat=2)
    # Guides, down to the road, the curtain's ends running in them.
    for sign in (-1, 1):
        for s in range(2):
            h = (ROAD_TO_ORIGIN - HOUSING_H) / 2
            zc = -HOUSING_H - h * (s + 0.5)
            kit.add_box(bm, (0.0, sign * 7.0, zc), (0.86, 0.66, h), mat=1)
    return finish_mesh('shutter_frame', bm, [M['riveted_steel'], M['rust'], M['lamp_red']])


def slat_rest(i):
    """A slat's top when slammed."""
    return -HOUSING_H - i * SLAT_H


FINAL_BAR_TOP = slat_rest(SLATS)
BAR_DROP = (FINAL_BAR_TOP - BAR_H - BAR_PEEK) * -1


def leader(t):
    """How far the bar has come down at t: falling, a hard landing, two bounces, still by the end."""
    if t <= HIT:
        return BAR_DROP * (t / HIT) ** 2
    rest = BAR_DROP
    u = t - HIT
    if u < 0.11:
        return rest - 0.62 * 4 * (u / 0.11) * (1 - u / 0.11)
    if u < 0.17:
        v = (u - 0.11) / 0.06
        return rest - 0.14 * 4 * v * (1 - v)
    return rest


frame = A.obj(frame_mesh(), 'shutter_frame')
pieces = []
for i in range(SLATS):
    final = slat_rest(i)
    travel = STOW_TOP - final
    gap = BAR_DROP - travel
    o = A.obj(slat_mesh(i), f'shutter_slat_{i}')
    pieces.append((o, final, travel, gap))
bar_travel = BAR_DROP
bar = A.obj(bar_mesh(), 'shutter_bar')
pieces.append((bar, FINAL_BAR_TOP, bar_travel, 0.0))

# Light each at its slammed place, so the curtain's light runs on across its slats.
for o, final, _travel, _gap in pieces:
    me = o.data
    kit.bake_light(me, [((p[0], p[1], p[2] - final), c, r, w) for p, c, r, w in LIGHTS], ambient=AMBIENT)
    if o is bar:
        continue
    # Each slat's lower edge in its own shadow: bands, that hold at the scene's pixel.
    ca = me.color_attributes['AO']
    for loop in me.loops:
        if me.vertices[loop.vertex_index].co.z < -0.5 * SLAT_H:
            col = ca.data[loop.index].color
            ca.data[loop.index].color = (col[0] * 0.3, col[1] * 0.3, col[2] * 0.3, 1.0)
kit.bake_light(frame.data, LIGHTS, ambient=AMBIENT)

scene = bpy.context.scene
scene.render.fps = FPS
frames = round(DUR * FPS)
scene.frame_start, scene.frame_end = 0, frames
# One action with a slot per object: the exporter merges by action, so it's one clip, named as the asset.
action = bpy.data.actions.new(NAME)
for o, final, travel, gap in pieces:
    ad = o.animation_data_create()
    ad.action = action
    ad.action_slot = action.slots.new('OBJECT', o.name)
    for f in range(frames + 1):
        t = f / FPS
        d = max(0.0, leader(t) - gap)
        o.location = (0.0, 0.0, final + travel - d)
        o.keyframe_insert('location', frame=f)

EYE = (-12.0, -4.0, -ROAD_TO_ORIGIN + 1.45)
LOOK = (0.0, 0.0, -5.5)
scene.frame_set(frames // 2)
A.finish(kit, NAME, budget=300, animations=True, eye=EYE, look_at=LOOK, fov=70.0)

# The stills again against the shaft's dark (not exported): start, middle, end.
wbm = bmesh.new()
kit.add_box(wbm, (0.0, 0.0, -6.0), (60.0, 50.0, 13.0 + 26.0), mat=0)
bmesh.ops.reverse_faces(wbm, faces=wbm.faces[:])
wme = kit.mesh_from('backdrop', wbm, [M['dark']], recalc=False)
kit.bake_light(wme, [], ambient=(0.3, 0.3, 0.3))
A.obj(wme, 'backdrop')
for label, f in (('start', 0), ('mid', frames // 2), ('end', frames)):
    scene.frame_set(f)
    A.still(f'{NAME}-{label}', eye=EYE, look_at=LOOK, fov=70.0)
scene.frame_set(frames // 2)
A.still(NAME, eye=EYE, look_at=LOOK, fov=70.0)
