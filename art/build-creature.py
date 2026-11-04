# The running creature for the new zone's boost -> public/models/creature.glb
# Made from scratch: lofted biomech body, voxel remeshed into one hull, decimated, skinned to a 39 bone rig,
# with a keyframed rotary gallop solved by IK. See art/creature-LICENSE.md.
#
#   blender --background --disable-autoexec --factory-startup --python art/build-creature.py -- [--render] [--holo]
#
# Blender: z up, +X forward, +Y the creature's left, metres. Root at the origin, feet on z=0.

import math
import os
import shutil
import subprocess
import sys
import tempfile

import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.kdtree import KDTree

HERE = os.path.dirname(os.path.abspath(__file__))
GLB = os.path.join(HERE, '..', 'public', 'models', 'creature.glb')
RENDERS = os.path.join(HERE, 'renders')
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

FPS = 60
LOOP_FRAMES = 36  # 0.6 s
VOXEL = 0.0085
TARGET_TRIS = 11000

V = Vector


def rad(d):
    return math.radians(d)


# ------------------------------------------------------------------------------------------------ skeleton (rest)

# The back slopes up from a low rump to high shoulders (a hyena's line): from behind and above, that's what shows the back
SPINE_REST = [(-0.98, 0.755), (-0.70, 0.79), (-0.42, 0.82), (-0.14, 0.835), (0.14, 0.84), (0.42, 0.85), (0.66, 0.86)]
SPINE_NAMES = ['Pelvis', 'Spine1', 'Spine2', 'Spine3', 'Spine4', 'Spine5']
TAIL_LENS = [0.22, 0.21, 0.20, 0.19, 0.18, 0.17, 0.16, 0.15, 0.13, 0.11]
TAIL_NAMES = [f'Tail{i + 1}' for i in range(len(TAIL_LENS))]
TAIL_BASE = V((-1.06, 0, 0.785))
TAIL_REST_PITCH = [-3, -2, -1, 0, 0, 1, 3, 5, 7, 9]

BONES = {}  # name -> (head, tail, parent)


def bone(name, head, tail, parent):
    BONES[name] = (V(head), V(tail), parent)


bone('Root', (0, 0, 0), (0.25, 0, 0), None)
for i, n in enumerate(SPINE_NAMES):
    a, b = SPINE_REST[i], SPINE_REST[i + 1]
    bone(n, (a[0], 0, a[1]), (b[0], 0, b[1]), 'Root' if i == 0 else SPINE_NAMES[i - 1])
bone('Neck1', (0.66, 0, 0.86), (0.84, 0, 1.01), 'Spine5')
bone('Neck2', (0.84, 0, 1.01), (1.02, 0, 0.99), 'Neck1')
bone('Head', (1.02, 0, 0.99), (1.46, 0, 0.885), 'Neck2')
bone('Jaw', (1.04, 0, 0.93), (1.40, 0, 0.815), 'Head')
_h = TAIL_BASE.copy()
for i, n in enumerate(TAIL_NAMES):
    p = rad(TAIL_REST_PITCH[i])
    t = _h + V((-math.cos(p), 0, math.sin(p))) * TAIL_LENS[i]
    bone(n, _h, t, 'Pelvis' if i == 0 else TAIL_NAMES[i - 1])
    _h = t

HIP = (-0.95, 0.14, 0.70)
KNEE = (-0.70, 0.19, 0.44)
HOCK = (-1.03, 0.175, 0.24)
HBALL = (-0.90, 0.135, 0.035)
HTIP = (-0.78, 0.135, 0.02)
PIVOT = (0.50, 0.135, 0.95)
SHOULDER = (0.60, 0.225, 0.74)
ELBOW = (0.47, 0.235, 0.46)
WRIST = (0.57, 0.16, 0.13)
FBALL = (0.65, 0.125, 0.035)
FTIP = (0.76, 0.125, 0.02)


def mir(p, s):
    return (p[0], p[1] * s, p[2])


for sfx, s in (('.L', 1), ('.R', -1)):
    bone('Femur' + sfx, mir(HIP, s), mir(KNEE, s), 'Pelvis')
    bone('Tibia' + sfx, mir(KNEE, s), mir(HOCK, s), 'Femur' + sfx)
    bone('Meta' + sfx, mir(HOCK, s), mir(HBALL, s), 'Tibia' + sfx)
    bone('HToes' + sfx, mir(HBALL, s), mir(HTIP, s), 'Meta' + sfx)
    bone('Scapula' + sfx, mir(PIVOT, s), mir(SHOULDER, s), 'Spine5')
    bone('Humerus' + sfx, mir(SHOULDER, s), mir(ELBOW, s), 'Scapula' + sfx)
    bone('Forearm' + sfx, mir(ELBOW, s), mir(WRIST, s), 'Humerus' + sfx)
    bone('Paw' + sfx, mir(WRIST, s), mir(FBALL, s), 'Forearm' + sfx)
    bone('FToes' + sfx, mir(FBALL, s), mir(FTIP, s), 'Paw' + sfx)

# ------------------------------------------------------------------------------------------------ lofted parts

src_verts = []
src_faces = []
src_part = []
PARTS = []  # allowed bone lists


def catmull(pts, res):
    """Catmull-Rom through pts, res samples per span. pts are tuples/Vectors of equal length."""
    n = len(pts)
    out = []
    for i in range(n - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, n - 1)]
        for k in range(res):
            t = k / res
            t2, t3 = t * t, t * t * t
            out.append(tuple(
                0.5 * (2 * b + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (3 * b - a - 3 * c + d) * t3)
                for a, b, c, d in zip(p0, p1, p2, p3)))
    out.append(tuple(pts[-1]))
    return out


def loft(pts, radii, bones, sides=10, res=3, ref=V((0, 1, 0)), scallop=None, falloff=5, bias=None):
    """A closed tube through pts. radii: (side radius along ref, other radius). Returns nothing, adds to the source."""
    keys = [tuple(p) + tuple(r) for p, r in zip(pts, radii)]
    samples = catmull(keys, res) if len(keys) > 2 else [
        tuple(keys[0][j] + (keys[1][j] - keys[0][j]) * k / res for j in range(5)) for k in range(res + 1)]
    part = len(PARTS)
    PARTS.append((bones, falloff, bias or {}))
    base = len(src_verts)
    centres = [V(s[:3]) for s in samples]
    n = len(samples)
    for i, s in enumerate(samples):
        c = centres[i]
        t = (centres[min(i + 1, n - 1)] - centres[max(i - 1, 0)]).normalized()
        side = (ref - ref.dot(t) * t)
        if side.length < 1e-4:
            side = V((1, 0, 0)) - V((1, 0, 0)).dot(t) * t
        side.normalize()
        norm = t.cross(side)
        rx, rz = max(s[3], 0.0005), max(s[4], 0.0005)
        k = 1.0
        if scallop:
            k = scallop(i / (n - 1))
        for j in range(sides):
            a = 2 * math.pi * j / sides
            src_verts.append(c + side * (math.cos(a) * rx * k) + norm * (math.sin(a) * rz * k))
            src_part.append(part)
    for i in range(n - 1):
        for j in range(sides):
            a, b = base + i * sides + j, base + i * sides + (j + 1) % sides
            src_faces.append((a, b, b + sides, a + sides))
    # caps
    for ring, flip in ((0, True), (n - 1, False)):
        idx = len(src_verts)
        src_verts.append(centres[ring])
        src_part.append(part)
        for j in range(sides):
            a, b = base + ring * sides + j, base + ring * sides + (j + 1) % sides
            src_faces.append((idx, b, a) if flip else (idx, a, b))


def spike(base, tip, r_side, r_len, bones, sides=7, bend=0.0):
    """A horn or plate: r_side across, r_len along the creature."""
    base, tip = V(base), V(tip)
    mid = (base + tip) / 2 + V((0, 0, bend))
    loft([base, base.lerp(mid, 0.5), mid, mid.lerp(tip, 0.5), tip],
         [(r_side, r_len), (r_side * 0.9, r_len * 0.85), (r_side * 0.65, r_len * 0.6),
          (r_side * 0.4, r_len * 0.32), (0.0035, 0.0035)],
         bones, sides=sides, res=1)


# The torso: x, centre z, half width, half height
TORSO = [(-1.15, 0.73, 0.03, 0.03), (-1.09, 0.735, 0.085, 0.085), (-0.97, 0.735, 0.125, 0.125), (-0.80, 0.75, 0.12, 0.12),
         (-0.56, 0.775, 0.092, 0.105), (-0.30, 0.785, 0.105, 0.135), (-0.05, 0.77, 0.145, 0.19), (0.20, 0.76, 0.175, 0.235),
         (0.42, 0.755, 0.205, 0.245), (0.60, 0.785, 0.165, 0.195), (0.74, 0.84, 0.09, 0.115)]


def torso_at(x):
    for a, b in zip(TORSO, TORSO[1:]):
        if a[0] <= x <= b[0]:
            t = (x - a[0]) / (b[0] - a[0])
            return tuple(a[i] + (b[i] - a[i]) * t for i in (1, 2, 3))
    return TORSO[-1][1:]


SPINE_B = SPINE_NAMES
loft([(s[0], 0, s[1]) for s in TORSO], [(s[2], s[3]) for s in TORSO], SPINE_B, sides=20, res=4)

# Ribs: hoops down the flanks, raked back at the belly
for side in (1, -1):
    for i in range(15):
        x0 = -0.66 + i * 0.08
        sweep = 142 if i >= 5 else 62 + 16 * i  # Short lumbar ribs, the full hoops round the chest
        pts, rs = [], []
        for k in range(7):
            f = k / 6
            th = rad(78 - sweep * f)
            x = x0 - 0.13 * f * sweep / 142
            zc, rx, rz = torso_at(x)
            pts.append((x, side * (rx + 0.004) * math.cos(th), zc + (rz + 0.004) * math.sin(th)))
            r = 0.016 * (1 - 0.45 * f)
            rs.append((r, r))
        loft(pts, rs, SPINE_B, sides=6, res=2, ref=V((1, 0, 0)))

# The column: ringed vertebrae standing proud along the whole back
col_x = [-1.10, -0.85, -0.55, -0.25, 0.05, 0.30, 0.50, 0.68]
spine_rings = 26


def spine_scallop(t):
    return 0.72 + 0.46 * abs(math.sin(math.pi * spine_rings * t)) ** 0.8


loft([(x, 0, torso_at(x)[0] + torso_at(x)[2] - 0.004) for x in col_x],
     [(0.05 if x > -0.2 else 0.044, 0.034) for x in col_x], SPINE_B, sides=10, res=12, scallop=spine_scallop)

# Dorsal plates down the spine, tallest over the shoulders
for i in range(24):
    x = -1.06 + i * 0.072
    zc, rx, rz = torso_at(x)
    top = zc + rz + 0.02
    hump = math.exp(-((x - 0.38) / 0.28) ** 2)
    hip = math.exp(-((x + 0.92) / 0.14) ** 2)
    h = 0.038 + 0.075 * hump + 0.03 * hip
    spike((x + 0.005, 0, top - 0.03), (x - h * 0.8, 0, top + h), 0.012, 0.03, SPINE_B, sides=6)

# Iliac crests on the pelvis
for side in (1, -1):
    spike((-0.86, side * 0.085, 0.82), (-1.14, side * 0.17, 0.95), 0.02, 0.045, ['Pelvis'], bend=-0.012)

# Neck: ringed vertebrae
NECK_B = ['Spine5', 'Neck1', 'Neck2', 'Head']
neck_rings = 7


def neck_scallop(t):
    return 0.86 + 0.20 * abs(math.sin(math.pi * neck_rings * t)) ** 0.7


loft([(0.58, 0, 0.815), (0.72, 0, 0.90), (0.86, 0, 0.995), (1.02, 0, 0.995), (1.10, 0, 0.975)],
     [(0.10, 0.125), (0.074, 0.088), (0.056, 0.066), (0.056, 0.064), (0.05, 0.055)],
     NECK_B, sides=12, res=8, scallop=neck_scallop)
for i in range(6):
    x = 0.74 + i * 0.058
    z = 0.985 + 0.07 * min(1.0, (x - 0.72) / 0.14)
    spike((x, 0, z - 0.03), (x - 0.06, 0, z + 0.035 - 0.002 * i), 0.01, 0.02, ['Neck1', 'Neck2'], sides=6)

# Skull: long, narrow wedge, the crown running back over the neck
skull_from = len(src_verts)
HEAD_B = ['Head']
loft([(0.93, 0, 0.985), (1.01, 0, 0.975), (1.10, 0, 0.945), (1.21, 0, 0.905), (1.33, 0, 0.865), (1.43, 0, 0.838), (1.475, 0, 0.822)],
     [(0.016, 0.022), (0.054, 0.052), (0.068, 0.066), (0.052, 0.05), (0.033, 0.034), (0.022, 0.024), (0.008, 0.008)],
     HEAD_B, sides=14, res=4)
# Forked crest: two prongs sweeping back above the neck
for side in (1, -1):
    loft([(1.09, side * 0.03, 0.965), (0.97, side * 0.05, 1.0), (0.83, side * 0.075, 1.03), (0.70, side * 0.095, 1.045), (0.58, side * 0.11, 1.05)],
         [(0.03, 0.04), (0.03, 0.038), (0.022, 0.026), (0.013, 0.015), (0.004, 0.004)],
         HEAD_B, sides=8, res=4)
    # Cheek spur
    spike((1.15, side * 0.05, 0.895), (0.97, side * 0.115, 0.87), 0.014, 0.022, HEAD_B)
    # Brow ridge
    loft([(1.17, side * 0.042, 0.945), (1.09, side * 0.058, 0.985), (1.00, side * 0.052, 1.015)],
         [(0.008, 0.012), (0.012, 0.016), (0.004, 0.004)], HEAD_B, sides=6, res=3)
    # Upper teeth
    for i in range(5):
        x = 1.40 - i * 0.052
        z = 0.822 + i * 0.016
        spike((x, side * (0.018 + i * 0.006), z + 0.006), (x - 0.008, side * (0.02 + i * 0.006), z - 0.042 - 0.006 * (i == 1)),
              0.008, 0.009, HEAD_B, sides=5)
# Lower jaw, hanging slightly open
loft([(1.04, 0, 0.862), (1.15, 0, 0.828), (1.28, 0, 0.785), (1.38, 0, 0.752), (1.415, 0, 0.738)],
     [(0.042, 0.022), (0.04, 0.02), (0.028, 0.016), (0.018, 0.012), (0.007, 0.006)],
     ['Jaw'], sides=10, res=3)
for side in (1, -1):
    for i in range(4):
        x = 1.37 - i * 0.06
        z = 0.76 + i * 0.019
        spike((x, side * (0.012 + i * 0.006), z), (x + 0.004, side * (0.014 + i * 0.006), z + 0.038), 0.007, 0.008, ['Jaw'], sides=5)

for i in range(skull_from, len(src_verts)):
    src_verts[i] = src_verts[i] + V((0, 0, 0.07))

# Tail: the ribbed serpent's, ringed all the way down
tail_pts = [BONES[TAIL_NAMES[0]][0]] + [BONES[n][1] for n in TAIL_NAMES]
tail_len = sum(TAIL_LENS)
cum = [0]
for l in TAIL_LENS:
    cum.append(cum[-1] + l)
tail_r = [0.058 * (1 - c / tail_len) ** 1.25 + 0.009 for c in cum]
tail_r[-1] = 0.006
tail_rings = 30


def tail_scallop(t):
    # Rings shrink in length towards the tip; the sine runs on a warped t
    w = 1 - (1 - t) ** 1.45
    return 0.84 + 0.30 * abs(math.sin(math.pi * tail_rings * w)) ** 0.65


loft([tuple(p) for p in tail_pts], [(r, r) for r in tail_r], ['Pelvis'] + TAIL_NAMES, sides=9, res=14, scallop=tail_scallop)
for i in range(30):
    t = (i + 0.5) / 30
    s = t * tail_len * 0.97
    j = next(k for k in range(len(TAIL_LENS)) if cum[k + 1] >= s)
    f = (s - cum[j]) / TAIL_LENS[j]
    p = tail_pts[j].lerp(tail_pts[j + 1], f)
    r = 0.058 * (1 - s / tail_len) ** 1.25 + 0.009
    h = 0.012 + r * 0.7
    spike(p + V((0, 0, r * 0.6)), p + V((-h * 0.95, 0, r + h)), 0.0075 + r * 0.1, 0.009 + r * 0.32, TAIL_NAMES[max(j - 1, 0):j + 2], sides=5)


def digits(ball, tip, side, bones, claw=0.075):
    ball, tip = V(ball), V(tip)
    d = tip - ball
    for o, l in ((-0.036, 0.9), (0.0, 1.15), (0.036, 0.95)):
        a = ball + V((0, o * 0.25 * side, 0.0))
        b = ball + V((d.x * l, o * side, d.z * l))
        loft([a, a.lerp(b, 0.5), b], [(0.021, 0.021), (0.016, 0.016), (0.012, 0.012)], bones, sides=7, res=2)
        spike(b, b + V((claw, 0, -0.014)), 0.0085, 0.009, bones, sides=5)


for sfx, s in (('.L', 1), ('.R', -1)):
    f, t, m, ht = 'Femur' + sfx, 'Tibia' + sfx, 'Meta' + sfx, 'HToes' + sfx
    hip, knee, hock, hball, htip = (V(mir(p, s)) for p in (HIP, KNEE, HOCK, HBALL, HTIP))
    # Haunch: a big teardrop, narrowing fast into the shin
    a = hip + V((-0.04, -s * 0.03, 0.08))
    loft([a, hip.lerp(knee, 0.22) + V((-0.02, 0, 0)), hip.lerp(knee, 0.6), knee],
         [(0.055, 0.08), (0.07, 0.098), (0.05, 0.062), (0.036, 0.04)], ['Pelvis', f, t], sides=12, res=4,
         falloff=3.5, bias={'Pelvis': 1.3})
    loft([knee, knee.lerp(hock, 0.3), knee.lerp(hock, 0.7), hock],
         [(0.036, 0.042), (0.034, 0.05), (0.022, 0.03), (0.021, 0.024)], [f, t, m], sides=9, res=3)
    loft([hock, hock.lerp(hball, 0.5), hball], [(0.022, 0.024), (0.018, 0.02), (0.021, 0.021)], [t, m, ht], sides=8, res=3)
    spike(hock + V((0.01, 0, 0)), hock + V((-0.15, s * 0.006, 0.045)), 0.012, 0.018, [m])
    spike(knee + V((-0.015, s * 0.012, 0.01)), knee + V((-0.14, s * 0.06, 0.08)), 0.012, 0.018, [f])
    digits(hball, htip, s, [ht])

    sc, hu, fo, pa, ft = 'Scapula' + sfx, 'Humerus' + sfx, 'Forearm' + sfx, 'Paw' + sfx, 'FToes' + sfx
    pivot, sh, el, wr, fball, ftip = (V(mir(p, s)) for p in (PIVOT, SHOULDER, ELBOW, WRIST, FBALL, FTIP))
    # Shoulder blade: a flat plate riding proud of the ribs, its top a spine over the back
    loft([pivot + V((-0.02, 0, 0.03)), pivot.lerp(sh, 0.45) + V((0.0, s * 0.012, 0)), sh],
         [(0.022, 0.09), (0.03, 0.125), (0.05, 0.08)], [sc], sides=10, res=4)
    spike(pivot + V((0.02, 0, -0.02)), pivot + V((-0.24, s * 0.13, 0.19)), 0.02, 0.05, [sc], bend=-0.012)
    # Upper arm, forearm, wrist
    loft([sh, sh.lerp(el, 0.45), el], [(0.062, 0.085), (0.06, 0.075), (0.034, 0.042)], [sc, hu, fo], sides=11, res=4)
    loft([el, el.lerp(wr, 0.3), el.lerp(wr, 0.7), wr],
         [(0.034, 0.042), (0.036, 0.046), (0.022, 0.028), (0.02, 0.022)], [hu, fo, pa], sides=9, res=3)
    loft([wr, wr.lerp(fball, 0.5), fball], [(0.019, 0.021), (0.019, 0.019), (0.021, 0.021)], [fo, pa, ft], sides=8, res=2)
    spike(el + V((0.012, 0, -0.012)), el + V((-0.15, s * 0.03, -0.012)), 0.012, 0.018, [fo])
    digits(fball, ftip, s, [ft])

# ------------------------------------------------------------------------------------------------ mesh

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 0, LOOP_FRAMES

me_src = bpy.data.meshes.new('CreatureSrc')
me_src.from_pydata([tuple(v) for v in src_verts], [], src_faces)
me_src.update()
hull = bpy.data.objects.new('Creature', me_src)
scene.collection.objects.link(hull)
bpy.context.view_layer.objects.active = hull
hull.select_set(True)

rem = hull.modifiers.new('rem', 'REMESH')
rem.mode = 'VOXEL'
rem.voxel_size = VOXEL
rem.adaptivity = 0.0
rem.use_smooth_shade = True
bpy.ops.object.modifier_apply(modifier=rem.name)
print('remeshed', len(hull.data.polygons), 'faces')

dec = hull.modifiers.new('dec', 'DECIMATE')
dec.decimate_type = 'COLLAPSE'
dec.ratio = TARGET_TRIS / (len(hull.data.polygons) * 2)
dec.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier=dec.name)
mesh = hull.data
mesh.name = 'Creature'
print('mesh repaired:', mesh.validate(verbose=False))
mesh.calc_loop_triangles()
print('decimated', len(mesh.loop_triangles), 'tris', len(mesh.vertices), 'verts')
for p in mesh.polygons:
    p.use_smooth = True

mat = bpy.data.materials.new('Creature')
mat.use_nodes = True
mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.05, 0.25, 0.1, 1)
mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.5
mesh.materials.clear()
mesh.materials.append(mat)

# ------------------------------------------------------------------------------------------------ armature

arm_data = bpy.data.armatures.new('CreatureRig')
arm = bpy.data.objects.new('CreatureRig', arm_data)
scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
for o in bpy.data.objects:
    o.select_set(o is arm)
bpy.ops.object.mode_set(mode='EDIT')
for name, (h, t, par) in BONES.items():
    eb = arm_data.edit_bones.new(name)
    eb.head, eb.tail = h, t
    eb.use_connect = False
    eb.use_deform = True
for name, (h, t, par) in BONES.items():
    if par:
        arm_data.edit_bones[name].parent = arm_data.edit_bones[par]
bpy.ops.object.mode_set(mode='OBJECT')
print('bones', len(arm_data.bones))

# ------------------------------------------------------------------------------------------------ weights


def seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.dot(ab), 1e-9)))
    return (p - (a + ab * t)).length


# Weights are worked out on the source parts, where a leg is known to be a leg, then carried over to the hull
src_w = []
for v, part in zip(src_verts, src_part):
    w = {}
    bones_, falloff, bias = PARTS[part]
    for b in bones_:
        h, t, _ = BONES[b]
        w[b] = bias.get(b, 1.0) / (seg_dist(v, h, t) + 0.015) ** falloff
    tot = sum(w.values())
    src_w.append({k: x / tot for k, x in w.items()})

kd = KDTree(len(src_verts))
for i, v in enumerate(src_verts):
    kd.insert(v, i)
kd.balance()

names = list(BONES.keys())
idx = {n: i for i, n in enumerate(names)}
nv = len(mesh.vertices)
vw = []
for mv in mesh.vertices:
    acc = {}
    near = kd.find_n(mv.co, 8)
    dmin = near[0][2] if near else 0
    for co, i, d in near:
        k = 1.0 / (d - dmin + 0.004) ** 2
        for b, x in src_w[i].items():
            acc[b] = acc.get(b, 0) + x * k
    vw.append(acc)

# Smooth across the hull so joins bend rather than crease
neigh = [[] for _ in range(nv)]
for e in mesh.edges:
    a, b = e.vertices
    neigh[a].append(b)
    neigh[b].append(a)
for it in range(3):
    nw = []
    for i in range(nv):
        acc = {}
        for b, x in vw[i].items():
            acc[b] = acc.get(b, 0) + x / max(sum(vw[i].values()), 1e-9)
        for j in neigh[i]:
            s = max(sum(vw[j].values()), 1e-9)
            for b, x in vw[j].items():
                acc[b] = acc.get(b, 0) + x / s / max(len(neigh[i]), 1)
        nw.append(acc)
    vw = nw

for n in names:
    hull.vertex_groups.new(name=n)
for i, acc in enumerate(vw):
    top = sorted(acc.items(), key=lambda kv: -kv[1])[:4]
    top = [(b, x) for b, x in top if x > 0]
    s = sum(x for _, x in top)
    for b, x in top:
        hull.vertex_groups[b].add([i], x / s, 'REPLACE')

hull.parent = arm
mod = hull.modifiers.new('Armature', 'ARMATURE')
mod.object = arm

# ------------------------------------------------------------------------------------------------ gallop

TAU = 2 * math.pi

# Local leg phase keys: t, ball x, ball lift z, foot angle (deg, + = the joint above trails behind the ball), toe angle
HIND = [
    (0.00, -0.30, 0.00, 34, 0),
    (0.12, -0.70, 0.00, 14, 0),
    (0.24, -1.10, 0.00, -26, -12),
    (0.35, -1.38, 0.16, -72, -135),
    (0.52, -1.10, 0.17, -20, -115),
    (0.70, -0.60, 0.13, 48, -60),
    (0.87, -0.20, 0.12, 46, -20),
]
FRONT = [
    (0.00, 0.98, 0.00, 20, 0),
    (0.12, 0.56, 0.00, 6, 0),
    (0.24, 0.12, 0.00, -44, -15),
    (0.35, -0.02, 0.20, -85, -130),
    (0.53, 0.36, 0.42, -75, -120),
    (0.72, 0.90, 0.40, -6, -60),
    (0.88, 1.16, 0.15, 24, -15),
]
# Rotary gallop: hinds land, push, the long flight; fronts land, pull, the gathered flight
PHASE = {'HL': 0.00, 'HR': 0.07, 'FR': 0.50, 'FL': 0.58}
SPINE_FLEX = 6.5  # degrees per joint, +/- across the stride
BODY_DROP = 0.018
FOOT_CLEAR = -0.013  # Sets the stance foot's height, fitted so the lowest claw over the loop sits on the floor


def cyc(keys, u):
    u = u % 1.0
    n = len(keys)
    ts = [k[0] for k in keys]
    i = n - 1
    for j in range(n):
        nxt = ts[j + 1] if j + 1 < n else 1.0
        if ts[j] <= u < nxt:
            i = j
            break
    a, b = keys[i], keys[(i + 1) % n]
    p, q = keys[(i - 1) % n], keys[(i + 2) % n]
    t0 = a[0]
    t1 = b[0] if i + 1 < n else b[0] + 1.0
    tp = p[0] if i > 0 else p[0] - 1.0
    tq = q[0] + (1.0 if (i + 2) >= n else 0.0)
    dt = t1 - t0
    s = (u - t0) / dt
    s2, s3 = s * s, s * s * s
    res = []
    for c in range(1, len(a)):
        m0 = (b[c] - p[c]) / (t1 - tp) * dt
        m1 = (q[c] - a[c]) / (tq - t0) * dt
        res.append((2 * s3 - 3 * s2 + 1) * a[c] + (s3 - 2 * s2 + s) * m0 + (-2 * s3 + 3 * s2) * b[c] + (s3 - s2) * m1)
    return res


def two_bone(a, c, l1, l2, pole):
    """Returns the middle joint and the (possibly clamped) end."""
    d = c - a
    dist = d.length
    lo, hi = abs(l1 - l2) + 0.01, l1 + l2 - 0.004
    if dist > hi:
        c = a + d * (hi / dist)
    elif dist < lo:
        c = a + d * (lo / dist)
    d = c - a
    dist = d.length
    ax = d / dist
    x = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
    h = math.sqrt(max(l1 * l1 - x * x, 0))
    perp = pole - pole.dot(ax) * ax
    perp.normalize()
    return a + ax * x + perp * h, c


def toe_dir(lift, toe):
    """The toes' direction, curled by toe degrees but never through the floor: claws reach about 0.24 m."""
    t = rad(toe)
    z = max(math.sin(t) - 0.12, -(max(lift, 0.0) + 0.02) / 0.24)
    z = max(z, -1.0)
    return V((math.copysign(math.sqrt(1 - z * z), math.cos(t)), 0, z))


rest = {n: arm_data.bones[n].matrix_local.copy() for n in names}
rest_inv = {n: m.inverted() for n, m in rest.items()}
lens = {n: (BONES[n][1] - BONES[n][0]).length for n in names}
rest_dir = {n: (BONES[n][1] - BONES[n][0]).normalized() for n in names}


def target(name, head, direction, roll=0.0):
    r = rest[name].to_quaternion()
    q = rest_dir[name].rotation_difference(direction.normalized())
    if roll:
        q = Quaternion(direction.normalized(), roll) @ q
    return Matrix.Translation(head) @ (q @ r).to_matrix().to_4x4()


def from_parent(mats, parent, point):
    return mats[parent] @ rest_inv[parent] @ point


def pose_at(ph):
    """All bones' armature-space matrices at stride phase ph."""
    m = {'Root': rest['Root'].copy()}

    # Flexed (gathered) near 0.92, stretched near 0.42
    flex = math.cos(TAU * (ph - 0.92))
    pitch = rad(4.5) * math.cos(TAU * (ph - 0.14))
    heave = 0.035 * math.cos(2 * TAU * (ph - 0.40)) - BODY_DROP
    roll_p = rad(5) * math.sin(TAU * (ph - 0.18))
    roll_c = rad(5) * math.sin(TAU * (ph - 0.68))

    n = len(SPINE_NAMES)
    pts = [None] * (n + 1)
    rest_pts = [V((s[0], 0, s[1])) for s in SPINE_REST]
    pts[3] = rest_pts[3] + V((0, 0, heave))
    dirs = []
    for i in range(n):
        rd = rest_pts[i + 1] - rest_pts[i]
        th = math.atan2(rd.z, rd.x) + pitch - rad(SPINE_FLEX) * flex * (i - 2.5)
        psi = rad(2.8) * math.sin(TAU * (ph - 0.25) + i * 0.55)
        dirs.append(V((math.cos(th) * math.cos(psi), math.sin(psi) * math.cos(th), math.sin(th))))
    for i in range(3, n):
        pts[i + 1] = pts[i] + dirs[i] * rd_len[i]
    for i in range(2, -1, -1):
        pts[i] = pts[i + 1] - dirs[i] * rd_len[i]
    for i, nm in enumerate(SPINE_NAMES):
        f = i / (n - 1)
        m[nm] = target(nm, pts[i], dirs[i], roll_p + (roll_c - roll_p) * f)

    # Head: holds its line while the body works under it
    rest_end = rest_pts[-1]
    drift = pts[-1] - rest_end
    head_at = BONES['Head'][0] + V((drift.x * 0.55, drift.y * 0.3, drift.z * 0.30))
    n_mid, n_end = two_bone(pts[-1], head_at, lens['Neck1'], lens['Neck2'], V((0, 0, 1)))
    m['Neck1'] = target('Neck1', pts[-1], n_mid - pts[-1])
    m['Neck2'] = target('Neck2', n_mid, n_end - n_mid)
    head_pitch = rad(1.5) * math.sin(TAU * (ph - 0.3))
    q = Quaternion(V((0, 1, 0)), head_pitch)
    m['Head'] = target('Head', n_end, q @ rest_dir['Head'])
    jaw_h = from_parent(m, 'Head', BONES['Jaw'][0])
    jaw_o = rad(3) * (1 + math.sin(TAU * (ph - 0.1)))
    m['Jaw'] = target('Jaw', jaw_h, q @ Quaternion(V((0, 1, 0)), jaw_o) @ rest_dir['Jaw'])

    # Tail: a travelling wave, growing to the tip. Lateral whip plus a smaller vertical one
    t_h = from_parent(m, 'Pelvis', TAIL_BASE)
    pel_pitch = math.atan2(dirs[0].z, dirs[0].x) - math.atan2(rest_pts[1].z - rest_pts[0].z, rest_pts[1].x - rest_pts[0].x)
    for i, nm in enumerate(TAIL_NAMES):
        ay = 3.0 + 3.5 * i
        az = 2.0 + 1.3 * i
        psi = rad(ay) * (math.sin(TAU * (ph - 0.05 - i * 0.085)) + 0.28 * math.sin(2 * TAU * (ph - i * 0.07)))
        th = rad(TAIL_REST_PITCH[i]) + rad(az) * math.sin(TAU * (ph - 0.22 - i * 0.07)) - pel_pitch * max(0, 1 - i / 4)
        d = V((-math.cos(th) * math.cos(psi), math.sin(psi) * math.cos(th), math.sin(th)))
        m[nm] = target(nm, t_h, d)
        t_h = t_h + d * lens[nm]

    # Hind legs
    for sfx, side, ph0 in (('.L', 1, PHASE['HL']), ('.R', -1, PHASE['HR'])):
        x, z, a, toe = cyc(HIND, ph - ph0)
        z = max(z, 0.0)
        y = side * (0.135 + 0.12 * z)  # Feet track in on the ground, swing wide: they show past the hips from behind
        ball = V((x, y, z + HBALL[2] + FOOT_CLEAR))
        a_r = rad(a)
        hip = from_parent(m, 'Pelvis', V(mir(HIP, side)))
        hock_want = ball + V((-math.sin(a_r), side * 0.09, math.cos(a_r))).normalized() * lens['Meta' + sfx]
        knee, hock = two_bone(hip, hock_want, lens['Femur' + sfx], lens['Tibia' + sfx], V((1, side * 0.12, -0.35)))
        m['Femur' + sfx] = target('Femur' + sfx, hip, knee - hip)
        m['Tibia' + sfx] = target('Tibia' + sfx, knee, hock - knee)
        m['Meta' + sfx] = target('Meta' + sfx, hock, ball - hock)
        b2 = hock + (ball - hock).normalized() * lens['Meta' + sfx]
        m['HToes' + sfx] = target('HToes' + sfx, b2, toe_dir(b2.z - HBALL[2] - FOOT_CLEAR, toe))

    # Front legs
    for sfx, side, ph0 in (('.L', 1, PHASE['FL']), ('.R', -1, PHASE['FR'])):
        x, z, a, toe = cyc(FRONT, ph - ph0)
        z = max(z, 0.0)
        y = side * (0.135 + 0.2 * z)
        ball = V((x, y, z + FBALL[2] + FOOT_CLEAR))
        a_r = rad(a)
        pivot = from_parent(m, 'Spine5', V(mir(PIVOT, side)))
        # The blade swings with the leg: this is what reads from above
        rd = rest_dir['Scapula' + sfx]
        swing = rad(30) * math.tanh((x - 0.55) / 0.5) + rad(5) * math.cos(TAU * (ph - 0.5))
        ang = math.atan2(rd.x, -rd.z) + swing
        sd = V((math.sin(ang), rd.y, -math.cos(ang))).normalized()
        m['Scapula' + sfx] = target('Scapula' + sfx, pivot, sd)
        sh = pivot + sd * lens['Scapula' + sfx]
        wrist_want = ball + V((-math.sin(a_r), side * 0.09, math.cos(a_r))).normalized() * lens['Paw' + sfx]
        elbow, wrist = two_bone(sh, wrist_want, lens['Humerus' + sfx], lens['Forearm' + sfx], V((-1, side * 0.12, 0)))
        m['Humerus' + sfx] = target('Humerus' + sfx, sh, elbow - sh)
        m['Forearm' + sfx] = target('Forearm' + sfx, elbow, wrist - elbow)
        m['Paw' + sfx] = target('Paw' + sfx, wrist, ball - wrist)
        b2 = wrist + (ball - wrist).normalized() * lens['Paw' + sfx]
        m['FToes' + sfx] = target('FToes' + sfx, b2, toe_dir(b2.z - FBALL[2] - FOOT_CLEAR, toe))
    return m


rd_len = [(V((SPINE_REST[i + 1][0], 0, SPINE_REST[i + 1][1])) - V((SPINE_REST[i][0], 0, SPINE_REST[i][1]))).length
          for i in range(len(SPINE_NAMES))]

if arm.animation_data is None:
    arm.animation_data_create()
action = bpy.data.actions.new('Run')
arm.animation_data.action = action
for pb in arm.pose.bones:
    pb.rotation_mode = 'QUATERNION'
prev = {}
for f in range(LOOP_FRAMES + 1):
    ph = (f % LOOP_FRAMES) / LOOP_FRAMES
    mats = pose_at(ph)
    for n in names:
        pb = arm.pose.bones[n]
        par = BONES[n][2]
        if par:
            bind = mats[par] @ rest_inv[par] @ rest[n]
        else:
            bind = rest[n]
        basis = bind.inverted() @ mats[n]
        loc, rot, _ = basis.decompose()
        if n in prev:
            rot.make_compatible(prev[n])
        prev[n] = rot
        pb.location = loc
        pb.rotation_quaternion = rot
        pb.scale = (1, 1, 1)
        pb.keyframe_insert('location', frame=f, group=n)
        pb.keyframe_insert('rotation_quaternion', frame=f, group=n)
action.name = 'Run'
action.use_frame_range = True
action.frame_start, action.frame_end = 0, LOOP_FRAMES
scene.frame_set(0)

# ------------------------------------------------------------------------------------------------ measure


def bbox_eval(frame):
    scene.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = hull.evaluated_get(dg)
    me = ev.to_mesh()
    cs = [v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return cs


low = []
for f in range(LOOP_FRAMES):
    cs = bbox_eval(f)
    zs = [c.z for c in cs]
    xs = [c.x for c in cs]
    low.append(min(zs))
    print(f'frame {f:2d} minZ {min(zs):+.3f} maxX {max(xs):+.3f} minX {min(xs):+.3f} maxZ {max(zs):+.3f} tailY {max(abs(c.y) for c in cs if c.x < -1.6):.3f}')
print('lowest', min(low), 'at frame', low.index(min(low)), 'highest low', max(low))
arm.data.pose_position = 'REST'
bpy.context.view_layer.update()
print('rest bbox', [round(min(v.co[i] for v in mesh.vertices), 3) for i in range(3)], [round(max(v.co[i] for v in mesh.vertices), 3) for i in range(3)])
arm.data.pose_position = 'POSE'
scene.frame_set(0)

# ------------------------------------------------------------------------------------------------ export

os.makedirs(os.path.dirname(GLB), exist_ok=True)
for o in bpy.data.objects:
    o.select_set(o in (arm, hull))
bpy.context.view_layer.objects.active = arm
bpy.ops.export_scene.gltf(
    filepath=GLB, export_format='GLB', use_selection=True, export_apply=True,
    export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
    export_draco_position_quantization=14, export_draco_normal_quantization=8,
    export_draco_texcoord_quantization=10, export_draco_color_quantization=8,
    export_yup=True, export_cameras=False, export_lights=False, export_extras=False,
    export_skins=True, export_def_bones=True, export_animations=True, export_animation_mode='ACTIONS',
    export_force_sampling=True, export_frame_step=1, export_optimize_animation_size=True,
    export_materials='EXPORT', export_texcoords=False, export_vertex_color='NONE')
print('exported', os.path.abspath(GLB), os.path.getsize(GLB))

# ------------------------------------------------------------------------------------------------ renders


def camera(name, loc, look, angle_y=None, lens=None):
    cam = bpy.data.cameras.new(name)
    cam_o = bpy.data.objects.new(name, cam)
    scene.collection.objects.link(cam_o)
    cam_o.location = loc
    cam.sensor_fit = 'VERTICAL'
    if angle_y:
        cam.angle_y = rad(angle_y)
    if lens:
        cam.lens = lens
    cam_o.rotation_euler = (V(look) - V(loc)).to_track_quat('-Z', 'Y').to_euler()
    return cam_o


if '--render' in ARGS or '--holo' in ARGS:
    os.makedirs(RENDERS, exist_ok=True)
    floor_me = bpy.data.meshes.new('floor')
    floor_me.from_pydata([(-30, -30, 0), (30, -30, 0), (30, 30, 0), (-30, 30, 0)], [], [(0, 1, 2, 3)])
    floor = bpy.data.objects.new('floor', floor_me)
    scene.collection.objects.link(floor)
    world = bpy.data.worlds.new('w')
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs[0].default_value = (0.012, 0.018, 0.016, 1)
    behind = camera('Behind', (-3.5, 0, 1.6), (0, 0, 0.9), angle_y=70)
    side = camera('Side', (-0.65, -6.5, 1.0), (-0.65, 0, 0.72), lens=58)
    above = camera('Above', (-2.2, -2.6, 3.1), (0.1, 0, 0.6), lens=30)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'

if '--render' in ARGS:
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'SINGLE'
    sh.single_color = (0.62, 0.72, 0.66)
    sh.show_shadows = True
    sh.show_cavity = True
    sh.cavity_type = 'WORLD'
    sh.background_type = 'WORLD'
    sets = {'behind': behind, 'side': side}
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
    outputs = {k: [] for k in sets}
    for key, cam_o in sets.items():
        scene.camera = cam_o
        for i in range(8):
            scene.frame_set(int(round(i * LOOP_FRAMES / 8)))
            p = os.path.join(RENDERS, f'creature-{key}-{i}.png')
            scene.render.filepath = p
            bpy.ops.render.render(write_still=True)
            outputs[key].append(p)
    scene.camera = above
    scene.frame_set(9)
    p = os.path.join(RENDERS, 'creature-above.png')
    scene.render.filepath = p
    bpy.ops.render.render(write_still=True)
    # Contact sheets: the behind view is cropped in on the creature, since FOV 70 leaves it small in the frame
    tool = shutil.which('magick')
    if tool:
        for key, files in outputs.items():
            crop = ['-crop', '400x330+280+120', '+repage'] if key == 'behind' else ['-resize', '480x270']
            with tempfile.TemporaryDirectory() as tmp:
                crops = []
                for i, f in enumerate(files):
                    c = os.path.join(tmp, f'{i}.png')
                    subprocess.run([tool, f, *crop, c], check=True)
                    crops.append(c)
                subprocess.run([tool, 'montage', *crops, '-tile', '4x2', '-geometry', '+2+2', '-background', '#111',
                                os.path.join(RENDERS, f'creature-contact-{key}.png')], check=True)

if '--holo' in ARGS:
    # A rough stand-in for the runtime look: fresnel code-green on black, no floor
    floor.hide_render = True
    scene.render.engine = 'BLENDER_EEVEE'
    world.node_tree.nodes['Background'].inputs[0].default_value = (0, 0, 0, 1)
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    lw = nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs[0].default_value = 0.35
    ramp = nt.nodes.new('ShaderNodeMapRange')
    ramp.inputs['From Min'].default_value = 0.0
    ramp.inputs['From Max'].default_value = 1.0
    ramp.inputs['To Min'].default_value = 0.08
    ramp.inputs['To Max'].default_value = 3.0
    nt.links.new(lw.outputs['Facing'], ramp.inputs['Value'])
    nt.links.new(ramp.outputs[0], em.inputs['Strength'])
    em.inputs['Color'].default_value = (0.1, 1.0, 0.3, 1)
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
    scene.eevee.taa_render_samples = 16
    for key, cam_o, frames in (('behind', behind, (0, 9, 18, 27)), ('side', side, (9, 27))):
        scene.camera = cam_o
        for f in frames:
            scene.frame_set(f)
            scene.render.filepath = os.path.join(RENDERS, f'creature-holo-{key}-{f:02d}.png')
            bpy.ops.render.render(write_still=True)
