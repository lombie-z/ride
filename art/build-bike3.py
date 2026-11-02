"""Bone bike, the third hero bike: the coral hive zone's ribbed exoskeleton bike (art/reference/concept-hive-city.webp,
checked against concept-hive-plaza.webp; the rider on it in concept-transition-desert.webp).

Builds the bike from scratch, saves art/bike3.blend and exports public/models/bike3.glb (Draco).
Run:   blender --background --factory-startup --python art/build-bike3.py
Review renders into art/renders/bike3-*.png (concept, plaza, rider, side, hero, top):
       blender --background --factory-startup --python art/build-bike3.py -- --render [--tag NAME] [--views concept,side]
Overlay check: python3 art/align-bike3/compare.py art/renders/bike3-concept-r1.png r1 [art/renders/bike3-plaza-r1.png]

Same frame as bike.glb (art/build-bike.py) and bike2.glb so the site can morph between them in place: metres, Z up,
front toward +X, ground z=0, origin on the ground midway between the contacts, wheelbase 1.56 m, the same axles, the
root rolled 5 deg toward +Y onto the kickstand. Objects: Bike3 (body), Wheel3Front / Wheel3Rear (children, origin on
the axle, spin about local Y), Bike3Button + Bike3ButtonGlyph (the throttle pill on the tank, three forward chevrons),
Bike3Dash (curved display, UV 0-1, u right and v up from the rider's seat), and the ButtonCentre / RiderEye empties at
bike.glb's exact bike-local transforms. The tank under and around the button is conformed to bike.glb's
(art/align-bike3/bike1-tank.json) so the site's throttle track sits on it; ButtonCentre carries the measured profile:
TRACK_D (m back along -X), TRACK_CENTRE and TRACK_SIDE (tank height along ButtonCentre's normal on the centre line and
at +-0.066 m, button meshes excluded).

The bone is one fused skin: overlapping lofts and tubes (tank carapace, ribcage, keel, swingarm claws, tail hood with
its vertebrae, nose cowl), voxel-remeshed, holes cut, remeshed again and smoothed so every join is a fillet.

Materials (plain Principled BSDFs, the site tunes them): Bike3Bone, Bike3Tendon, Bike3Metal, Bike3Tyre. Alpha-blended
(set depthWrite on the site): Bike3Smoke. Emissive: Bike3Tail, Bike3Vein, Bike3Dash, Bike3Button, Bike3ButtonGlyph.
"""
import json
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector, noise
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
BLEND_OUT = os.path.join(HERE, 'bike3.blend')
GLB_OUT = os.path.join(ROOT, 'public', 'models', 'bike3.glb')
RENDER_DIR = os.path.join(HERE, 'renders')
ALIGN = os.path.join(HERE, 'align-bike3')

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
DO_RENDER = '--render' in ARGS
TAG = ARGS[ARGS.index('--tag') + 1] if '--tag' in ARGS else ''
VIEWS = ARGS[ARGS.index('--views') + 1].split(',') if '--views' in ARGS else None
SAMPLES = int(ARGS[ARGS.index('--samples') + 1]) if '--samples' in ARGS else 64

TAU = math.tau
Y = Vector((0, 1, 0))

# ---------------------------------------------------------------- layout (bike local, metres) -- identical to bike.glb
WHEELBASE = 1.56
F_AXLE = Vector((WHEELBASE / 2, 0, 0.315))
R_AXLE = Vector((-WHEELBASE / 2, 0, 0.325))
F_R, R_R = 0.315, 0.325
F_W, R_W = 0.20, 0.34          # tyre widths     (art/align-bike3/fit_camera.py uses the same)
F_RIM, R_RIM = 0.201, 0.191    # rim radii: the tyres' section heights 0.114 / 0.134 (fit_camera's hr = half of it)
LEAN = math.radians(5)  # toward +Y (kickstand side)

# bike.glb's anchors, bike-local (art/align-bike2/bike1-anchors.json)
BUTTON_CENTRE = Matrix(((0.9996989965438843, -9.723816261734963e-14, -0.02453269064426422, 0.4049460291862488),
                        (-9.327195584774017e-07, 1.0, -3.8020312786102295e-05, -8.195638656616211e-08),
                        (0.02453269250690937, 3.802776336669922e-05, 0.999699056148529, 0.9743461012840271),
                        (0.0, 0.0, 0.0, 1.0)))
RIDER_EYE = Matrix(((-1.6292067073209182e-07, 0.9902679920196533, 0.13917315006256104, 0.07999999821186066),
                    (-1.0, -1.6205012798309326e-07, -2.2351741790771484e-08, 0.0),
                    (-7.450580596923828e-09, -0.13917316496372223, 0.9902679920196533, 1.5200001001358032),
                    (0.0, 0.0, 0.0, 1.0)))
BUTTON_X, BUTTON_LEN, BUTTON_WID = 0.405, 0.24, 0.11
BC_O = BUTTON_CENTRE.translation
BC_X = BUTTON_CENTRE.col[0].xyz.normalized()
BC_Y = BUTTON_CENTRE.col[1].xyz.normalized()
BC_N = BUTTON_CENTRE.col[2].xyz.normalized()
TRACK_D = [-0.16, -0.12, -0.08, -0.04, 0, 0.04, 0.08, 0.12, 0.16, 0.2, 0.24]
TRACK_S = 0.066
DASH_C = Vector((0.625, 0.0, 1.0))
TAIL_C, TAIL_TILT = Vector((-1.02, 0.0, 0.80)), math.radians(56)  # the tail-light face under the hood's tip


# ---------------------------------------------------------------- scene / materials
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = 'METRIC'
    return s


def srgb(h):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return tuple(lin(int(h[i:i + 2], 16)) for i in (1, 3, 5))


def principled(name, base, metallic=0.0, rough=0.5, coat=0.0, coat_rough=0.03, emit=None, emit_strength=0.0, spec=0.5,
               alpha=1.0, sheen=0.0, sheen_tint=(1, 1, 1)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*base, 1)
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = spec
    b.inputs['Coat Weight'].default_value = coat
    b.inputs['Coat Roughness'].default_value = coat_rough
    b.inputs['Sheen Weight'].default_value = sheen
    b.inputs['Sheen Tint'].default_value = (*sheen_tint, 1)
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1)
        b.inputs['Emission Strength'].default_value = emit_strength
    if alpha < 1.0:
        b.inputs['Alpha'].default_value = alpha
        m.surface_render_method = 'BLENDED'
    m.diffuse_color = (*base, 1)
    return m


def make_materials():
    return {
        # bone: warm off-white, satin
        'bone': principled('Bike3Bone', srgb('#cfc1a8'), rough=0.42, coat=0.15, coat_rough=0.35),
        # tendon and muscle: dark red, wet
        'tendon': principled('Bike3Tendon', srgb('#5c121a'), rough=0.3, coat=0.7, coat_rough=0.08, sheen=0.3, sheen_tint=srgb('#e0909a')),
        'metal': principled('Bike3Metal', srgb('#24201f'), metallic=0.9, rough=0.32),
        'tyre': principled('Bike3Tyre', (0.016, 0.015, 0.016), rough=0.68, spec=0.35),
        # smoked visor: dark red-brown tinted glass
        'smoke': principled('Bike3Smoke', srgb('#2e1012'), rough=0.03, coat=1.0, coat_rough=0.01, alpha=0.6),
        'tail': principled('Bike3Tail', srgb('#8a3a08'), rough=0.25, emit=srgb('#ff8a22'), emit_strength=14.0),
        'vein': principled('Bike3Vein', srgb('#a8301c'), rough=0.3, emit=srgb('#ff5a2c'), emit_strength=1.6),
        # the dash: dark glass glowing amber; the site draws the speed and logo into it
        'dash': principled('Bike3Dash', srgb('#140b07'), rough=0.05, coat=1.0, coat_rough=0.01, emit=srgb('#b8642c'), emit_strength=1.0),
        # the throttle pill: warm peach glow; the glyph brighter. The site drives both intensities.
        'button': principled('Bike3Button', srgb('#ffc89a'), rough=0.06, coat=1.0, coat_rough=0.02, emit=srgb('#ffb072'), emit_strength=1.0),
        'glyph': principled('Bike3ButtonGlyph', srgb('#fff0de'), rough=0.3, emit=srgb('#ffe2c0'), emit_strength=4.0),
    }


# ---------------------------------------------------------------- curve maths (as build-bike2.py)
def catmull(pts, per_seg=14):
    P = [Vector(p) for p in pts]
    if len(P) == 2:
        return [P[0].lerp(P[1], i / per_seg) for i in range(per_seg + 1)]
    P = [P[0] + (P[0] - P[1])] + P + [P[-1] + (P[-1] - P[-2])]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for j in range(per_seg):
            t = j / per_seg
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-2])
    return out


def resample(pts, n):
    d = [0.0]
    for a, b in zip(pts, pts[1:]):
        d.append(d[-1] + (b - a).length)
    total = d[-1]
    out, k = [], 0
    for i in range(n):
        s = total * i / (n - 1)
        while k < len(d) - 2 and d[k + 1] < s:
            k += 1
        t = (s - d[k]) / max(d[k + 1] - d[k], 1e-9)
        out.append(pts[k].lerp(pts[k + 1], min(max(t, 0), 1)))
    return out, total


def transport_frames(path):
    n = len(path)
    T = [(path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized() for i in range(n)]
    ref = Vector((0, 0, 1)) if abs(T[0].z) < 0.9 else Vector((1, 0, 0))
    N = (ref - T[0] * ref.dot(T[0])).normalized()
    frames = []
    for i in range(n):
        if i:
            N = T[i - 1].rotation_difference(T[i]) @ N
            N = (N - T[i] * N.dot(T[i])).normalized()
        frames.append((T[i], N, T[i].cross(N)))
    return frames


def hermite(keys, t, field, default=None):
    ts = [k['t'] for k in keys]
    vs = [k.get(field, default) for k in keys]
    if t <= ts[0]:
        return vs[0]
    if t >= ts[-1]:
        return vs[-1]
    i = max(j for j in range(len(ts) - 1) if ts[j] <= t)

    def slope(j):
        a, b = max(j - 1, 0), min(j + 1, len(ts) - 1)
        return (vs[b] - vs[a]) * (1.0 / (ts[b] - ts[a]))
    h = ts[i + 1] - ts[i]
    u = (t - ts[i]) / h
    h00, h10, h01, h11 = 2 * u**3 - 3 * u**2 + 1, u**3 - 2 * u**2 + u, -2 * u**3 + 3 * u**2, u**3 - u**2
    return vs[i] * h00 + slope(i) * (h10 * h) + vs[i + 1] * h01 + slope(i + 1) * (h11 * h)


def section(w, ht, hb, n, e=2.5, eb=None, a0=0.0, a1=TAU, closed=True):
    pts = []
    count = n if closed else n + 1
    for k in range(count):
        a = a0 + (a1 - a0) * k / n
        c, s = math.cos(a), math.sin(a)
        ee = e if s >= 0 else (eb or e)
        u = w * math.copysign(abs(c) ** (2 / ee), c)
        v = (ht if s >= 0 else hb) * math.copysign(abs(s) ** (2 / ee), s)
        pts.append((u, v))
    return pts


def smoothstep(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- mesh builders
PARTS = []


def new_obj(name, verts, faces, mat, smooth=True, uvs=None, track=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    layer = me.uv_layers.new(name='UVMap')
    if uvs:
        flat = [c for f in uvs for uv in f for c in uv]
        layer.data.foreach_set('uv', flat)
    me.validate()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    if track:
        PARTS.append(ob)
    return ob


TILE = 0.5


def rings_mesh(name, rings, mat, closed_ring=True, closed_along=False, cap0=None, cap1=None, smooth=True, track=True):
    m = len(rings[0])
    verts = [v for r in rings for v in r]
    faces, uvs = [], []
    nr = len(rings)
    us = []
    for r in rings:
        u = [0.0]
        for j in range(m if closed_ring else m - 1):
            u.append(u[-1] + (r[(j + 1) % m] - r[j]).length)
        us.append([x / TILE for x in u])
    vs = [0.0]
    for i in range(nr if closed_along else nr - 1):
        a, b = rings[i], rings[(i + 1) % nr]
        vs.append(vs[-1] + sum((b[j] - a[j]).length for j in range(m)) / m)
    vs = [x / TILE for x in vs]
    for i in range(nr if closed_along else nr - 1):
        i2 = (i + 1) % nr
        for j in range(m if closed_ring else m - 1):
            j2 = (j + 1) % m
            faces.append((i * m + j, i * m + j2, i2 * m + j2, i2 * m + j))
            uvs.append(((us[i][j], vs[i]), (us[i][j + 1], vs[i]), (us[i2][j + 1], vs[i + 1]), (us[i2][j], vs[i + 1])))
    for cap, ri in ((cap0, 0), (cap1, nr - 1)):
        if cap is None:
            continue
        idx = list(range(ri * m, ri * m + m))
        if cap == 'ngon':
            faces.append(tuple(idx))
            uvs.append(tuple((verts[k].x / TILE, verts[k].z / TILE) for k in idx))
        else:
            verts.append(cap)
            c = len(verts) - 1
            for j in range(m):
                faces.append((idx[j], idx[(j + 1) % m], c))
                uvs.append(((us[ri][j], vs[ri]), (us[ri][j + 1], vs[ri]), ((us[ri][j] + us[ri][j + 1]) / 2, vs[ri] + 0.02)))
    return new_obj(name, verts, faces, mat, smooth, uvs, track=track)


def apply_mods(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)
    return ob


def bake(ob, solidify=0.0, subsurf=0, solid_offset=0.0):
    if solidify:
        md = ob.modifiers.new('solid', 'SOLIDIFY')
        md.thickness = solidify
        md.offset = solid_offset
        md.use_even_offset = True
    if subsurf:
        md = ob.modifiers.new('sub', 'SUBSURF')
        md.levels = md.render_levels = subsurf
    if not ob.modifiers:
        return ob
    return apply_mods(ob)


def tube(name, ctrl, radius, mat, sides=10, segs=None, cap0='ngon', cap1='ngon', squash=1.0, track=True, twist=0.0):
    dense = catmull(ctrl, 16)
    length = sum((b - a).length for a, b in zip(dense, dense[1:]))
    segs = segs or max(6, int(length / 0.03))
    path, _ = resample(dense, segs + 1)
    frames = transport_frames(path)
    if isinstance(radius, (int, float)):
        rf = lambda s, r=radius: r
    elif isinstance(radius, tuple):
        rf = lambda s, r=radius: r[0] + (r[1] - r[0]) * s
    else:
        rf = radius
    rings = []
    for i, p in enumerate(path):
        s = i / segs
        T, N, B = frames[i]
        r = rf(s)
        rings.append([p + (N * math.cos(a) * squash + B * math.sin(a)) * r for a in (TAU * k / sides + twist for k in range(sides))])
    c0 = (path[0] - frames[0][0] * rf(0) * 0.5) if cap0 == 'point' else cap0
    c1 = (path[-1] + frames[-1][0] * rf(1) * 0.5) if cap1 == 'point' else cap1
    return rings_mesh(name, rings, mat, cap0=c0, cap1=c1, track=track)


def loft(name, keys, mat, n_along, n_around, side=Y, closed=True, cap0=None, cap1=None, solidify=0.0, subsurf=1, track=True):
    """Superellipse sections swept through keyed centres. Keys: c, w, ht, hb, e, eb, a0, a1, roll."""
    if 't' not in keys[0]:
        d = [0.0]
        for a, b in zip(keys, keys[1:]):
            d.append(d[-1] + (b['c'] - a['c']).length)
        for k, di in zip(keys, d):
            k['t'] = di / d[-1]
    rings, centres, tangents = [], [], []
    for i in range(n_along):
        t = i / (n_along - 1)
        c = hermite(keys, t, 'c')
        dc = hermite(keys, min(t + 0.01, 1), 'c') - hermite(keys, max(t - 0.01, 0), 'c')
        T = dc.normalized()
        up = T.cross(side).normalized()
        if up.z < 0:  # keys running toward -X would flip it: keep ht on top
            up = -up
        sd = up.cross(T).normalized()
        roll = hermite(keys, t, 'roll', 0.0)
        if roll:
            q = Matrix.Rotation(roll, 3, T)
            up, sd = q @ up, q @ sd
        g = lambda f, dflt=0.0: hermite(keys, t, f, dflt)
        pts = section(max(g('w'), 1e-4), max(g('ht'), 1e-4), max(g('hb'), 1e-4), n_around, e=g('e', 2.5), eb=g('eb', g('e', 2.5)),
                      a0=g('a0', -math.pi / 2), a1=g('a1', 1.5 * math.pi), closed=closed)
        rings.append([c + sd * u + up * v for u, v in pts])
        centres.append(c)
        tangents.append(T)
    c0 = cap0 if cap0 != 'point' else centres[0] - tangents[0] * 0.003
    c1 = cap1 if cap1 != 'point' else centres[-1] + tangents[-1] * 0.003
    ob = rings_mesh(name, rings, mat, closed_ring=closed, cap0=c0, cap1=c1, track=track)
    return bake(ob, solidify=solidify, subsurf=subsurf)


def lathe(name, prof, mat, segs, closed_prof=True, track=True):
    """Profile (r, y) revolved about the Y axis."""
    rings = []
    for k in range(segs):
        ph = TAU * k / segs
        rings.append([Vector((r * math.cos(ph), y, r * math.sin(ph))) for r, y in prof])
    return rings_mesh(name, rings, mat, closed_ring=closed_prof, closed_along=True, track=track)


def ellipsoid(name, c, radii, mat, rot=(0, 0, 0), segs=32, rings=16, track=True):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0)
    bm.to_mesh(me)
    bm.free()
    me.transform(Matrix.Translation(Vector(c)) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Diagonal((*radii, 1)))
    me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    if track:
        PARTS.append(ob)
    return ob


def box(name, M4, mat, track=False):
    """Unit cube (-1..1) through the 4x4 matrix M4."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bm.to_mesh(me)
    bm.free()
    me.transform(M4)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    if track:
        PARTS.append(ob)
    return ob


def mirror(ctrl):
    return [Vector((p[0], -p[1], p[2])) for p in ctrl]


def both(ctrl):
    return [[Vector(p) for p in ctrl], mirror(ctrl)]


def join(name, parts):
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def untrack(parts):
    for p in parts:
        if p in PARTS:
            PARTS.remove(p)


def tri_count(ob):
    ob.data.calc_loop_triangles()
    return len(ob.data.loop_triangles)


def remesh(ob, voxel, smooth_iter=0, smooth_lambda=0.8):
    md = ob.modifiers.new('remesh', 'REMESH')
    md.mode = 'VOXEL'
    md.voxel_size = voxel
    md.adaptivity = 0.0
    if smooth_iter:
        sm = ob.modifiers.new('smooth', 'LAPLACIANSMOOTH')
        sm.iterations = smooth_iter
        sm.lambda_factor = smooth_lambda
        sm.use_volume_preserve = True
        sm.use_normalized = True
    return apply_mods(ob)


def fuse(name, parts, voxel, cutters=(), smooth_iter=12, smooth_lambda=0.8, target_tris=None, mat=None, post=None):
    """Weld overlapping closed parts into one seamless skin: voxel remesh; carve the cutters out (exact boolean), remesh
    again and Laplacian-smooth so the joins and the cut rims round into fillets; `post` adjusts the dense skin; then
    decimate to a triangle budget."""
    untrack(parts)
    ob = join(name, parts)
    if cutters:
        remesh(ob, voxel)
        cut = join(name + 'Cut', list(cutters))
        md = ob.modifiers.new('cut', 'BOOLEAN')
        md.operation = 'DIFFERENCE'
        md.solver = 'EXACT'
        md.object = cut
        apply_mods(ob)
        bpy.data.objects.remove(cut)
    remesh(ob, voxel, smooth_iter, smooth_lambda)
    if post:
        post(ob)
    before = tri_count(ob)
    if target_tris and before > target_tris:
        dm = ob.modifiers.new('dec', 'DECIMATE')
        dm.ratio = target_tris / before
        dm.use_collapse_triangulate = True
        apply_mods(ob)
    ob.data.shade_smooth()
    if mat:
        ob.data.materials.clear()
        ob.data.materials.append(mat)
    print('FUSE', name, 'remesh tris', before, '->', tri_count(ob))
    return ob


def bvh(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    return [BVHTree.FromObject(o, dg) for o in objs]


def cast(trees, origin, direction):
    best = None
    for t in trees:
        h = t.ray_cast(Vector(origin), Vector(direction).normalized())
        if h[0] is not None and (best is None or h[3] < best[3]):
            best = h
    return best


def ribbed(r, n, amp=0.14, sharp=6):
    return lambda s: r * (1 + amp * abs(math.sin(math.pi * n * s)) ** sharp)


# ---------------------------------------------------------------- wheel
def build_wheel(name, radius, width, rim_r, M, front):
    """Fat dark tyre on a dark metal rim with split spokes, a big hub, brake disc(s) and (rear) a sprocket."""
    global PARTS
    saved, PARTS = PARTS, []
    hw = width / 2
    mt = M['metal']
    # tyre: squarish superellipse section revolved about Y, a rounder crown, a bead line at the rim
    rm, hr = (radius + rim_r) / 2, (radius - rim_r) / 2
    prof = [(rm + v, u) for u, v in section(hw, hr, hr, 32, e=2.5, eb=3.4)]
    tyre = lathe(name + 'Tyre', prof, M['tyre'], 120 if not front else 96)
    # rim: dark metal well with flanges
    fl = hw * 0.80
    rim = [(rim_r + 0.004, -fl), (rim_r - 0.012, -fl), (rim_r - 0.02, -fl * 0.6), (rim_r - 0.03, 0), (rim_r - 0.02, fl * 0.6),
           (rim_r - 0.012, fl), (rim_r + 0.004, fl), (rim_r + 0.002, fl * 0.85), (rim_r - 0.006, 0), (rim_r + 0.002, -fl * 0.85)]
    lathe(name + 'Rim', rim, mt, 96)
    # hub: a fat drum
    hub_hw = hw * (0.72 if not front else 0.85)
    hub = [(0.0, -hub_hw - 0.01), (0.045, -hub_hw - 0.01), (0.062, -hub_hw), (0.07, -hub_hw * 0.6), (0.06, 0), (0.07, hub_hw * 0.6),
           (0.062, hub_hw), (0.045, hub_hw + 0.01), (0.0, hub_hw + 0.01)]
    lathe(name + 'Hub', hub, mt, 40, closed_prof=False)
    # split spokes: five pairs, swept a little, from the hub to the rim well
    for k in range(5):
        ph0 = TAU * k / 5
        for side in (-1, 1):
            pts = []
            for i in range(5):
                s = i / 4
                r = 0.062 + (rim_r - 0.085) * s
                ph = ph0 + side * 0.09 * (1 - s) + 0.18 * s
                pts.append(Vector((r * math.cos(ph), side * (hub_hw * 0.55) * (1 - s) + side * 0.012 * s, r * math.sin(ph))))
            tube(name + 'Spoke', pts, lambda s: 0.011 - 0.003 * s, mt, sides=8, segs=10, squash=0.6)
    # brake discs: rear one on -Y, front both sides; a scalloped steel ring on a carrier
    discs = (-1, 1) if front else (-1,)
    dr0, dr1 = (0.105, 0.155) if front else (0.09, 0.12)
    for sgn in discs:
        y = sgn * (hub_hw + 0.012)
        ring = []
        n = 72
        for k in range(n):
            ph = TAU * k / n
            r1 = dr1 - 0.004 * (1 + math.cos(ph * 12)) / 2
            ring.append((ph, r1))
        rings = []
        for yy in (y - 0.0025, y + 0.0025):
            rings.append([Vector((r * math.cos(ph), yy, r * math.sin(ph))) for ph, r in ring])
            rings.append([Vector((dr0 * math.cos(ph), yy, dr0 * math.sin(ph))) for ph, r in ring])
        rr = [rings[0], rings[2], rings[3], rings[1]]
        rings_mesh(name + 'Disc', rr, mt, closed_along=True)
        for k in range(6):
            ph = TAU * k / 6
            a = Vector((0.065 * math.cos(ph), y, 0.065 * math.sin(ph)))
            b = Vector(((dr0 + 0.008) * math.cos(ph + 0.2), y, (dr0 + 0.008) * math.sin(ph + 0.2)))
            tube(name + 'Carrier', [a, b], 0.008, mt, sides=6, segs=2, squash=0.5)
    if not front:
        # sprocket on +Y: a toothed ring
        y = hub_hw + 0.012
        n = 84
        outline = []
        for k in range(n):
            ph = TAU * k / n
            r = 0.135 if (k % 2 == 0) else 0.123
            outline.append((ph, r))
        rings = []
        for yy in (y - 0.003, y + 0.003):
            rings.append([Vector((r * math.cos(ph), yy, r * math.sin(ph))) for ph, r in outline])
            rings.append([Vector((0.08 * math.cos(ph), yy, 0.08 * math.sin(ph))) for ph, r in outline])
        rings_mesh(name + 'Sprocket', [rings[0], rings[2], rings[3], rings[1]], mt, closed_along=True)
    wheel = join(name, PARTS)
    PARTS = saved
    return wheel


# ---------------------------------------------------------------- body
def key(x, z, w, ht, hb, y=0.0, **kw):
    return dict(c=Vector((x, y, z)), w=w, ht=ht, hb=hb, **kw)


# The tank carapace: a broad beetle dome over the ribcage; under the button it is conformed to bike.glb's tank.
TANK = [
    key(0.78, 0.845, 0.010, 0.010, 0.010, e=2.2),
    key(0.74, 0.845, 0.075, 0.040, 0.050, e=2.2),
    key(0.68, 0.828, 0.140, 0.090, 0.090, e=2.2),
    key(0.58, 0.808, 0.185, 0.142, 0.110, e=2.2, eb=2.6),
    key(0.46, 0.800, 0.205, 0.166, 0.120, e=2.2, eb=2.6),
    key(0.34, 0.800, 0.210, 0.165, 0.120, e=2.2, eb=2.6),
    key(0.21, 0.792, 0.200, 0.152, 0.115, e=2.2, eb=2.6),
    key(0.08, 0.782, 0.172, 0.124, 0.100, e=2.2, eb=2.6),
    key(-0.06, 0.765, 0.140, 0.095, 0.080, e=2.3),
    key(-0.16, 0.752, 0.100, 0.066, 0.060, e=2.3),
    key(-0.21, 0.750, 0.010, 0.010, 0.010, e=2.3),
]

# The tail hood: an arched carapace over the rear tyre, its flanks dropping deep at the front; x, arc base z (c),
# half width (w), arch height (ht), flank depth below c (fd)
HOOD = [
    dict(x=-0.30, c=0.795, w=0.13, ht=0.040, fd=0.06),
    dict(x=-0.42, c=0.825, w=0.19, ht=0.075, fd=0.20),
    dict(x=-0.52, c=0.850, w=0.210, ht=0.095, fd=0.26),
    dict(x=-0.66, c=0.865, w=0.215, ht=0.095, fd=0.20),
    dict(x=-0.80, c=0.860, w=0.195, ht=0.085, fd=0.085),
    dict(x=-0.94, c=0.848, w=0.160, ht=0.068, fd=0.045),
    dict(x=-1.05, c=0.83, w=0.13, ht=0.05, fd=0.04),
    dict(x=-1.14, c=0.82, w=0.108, ht=0.032, fd=0.036),
]


def hood_param():
    d = [0.0]
    for a, b in zip(HOOD, HOOD[1:]):
        d.append(d[-1] + abs(b['x'] - a['x']))
    for k, di in zip(HOOD, d):
        k['t'] = di / d[-1]


def hood_at(t):
    g = lambda f: hermite(HOOD, t, f)
    return g('x'), g('c'), g('w'), g('ht'), g('fd')


def hood_point(t, s, out=0.0):
    """Point on the hood's outer surface: t along (0 front .. 1 tip), s across: -1..-0.5 down the -Y flank (s=-1 its
    bottom edge), -0.5..0.5 over the arch, 0.5..1 down the +Y flank. `out` pushes it outward along the section normal."""
    x, c, w, ht, fd = hood_at(t)
    if abs(s) <= 0.5:
        return _arch(x, c, w, ht, 2.6, s, out)
    f = (abs(s) - 0.5) / 0.5  # 0 at the arch's foot, 1 at the flank's bottom edge
    sg = math.copysign(1, s)
    y = sg * (w - 0.028 * f * f)
    return Vector((x, y + sg * out, c - fd * f))


def _arch(x, c, w, ht, e, s, out):
    a = math.pi / 2 - s * math.pi  # s=-0.5 -> a=pi -> -Y ; s=+0.5 -> a=0 -> +Y
    ca, sa = math.cos(a), math.sin(a)
    u = w * math.copysign(abs(ca) ** (2 / e), ca)
    v = ht * abs(sa) ** (2 / e)
    # outward normal of the superellipse |u/w|^e + |v/ht|^e = 1
    nu = math.copysign(abs(u / w) ** (e - 1), u) / w if w > 1e-5 else 0.0
    nv = (abs(v / ht) ** (e - 1)) / ht if ht > 1e-5 else 1.0
    n = Vector((0, nu, nv))
    n = n.normalized() if n.length > 1e-9 else Vector((0, 0, 1))
    return Vector((x, u, c + v)) + n * out


def build_hood(M):
    hood_param()
    na, ns = 70, 44
    rings = []
    for i in range(na):
        t = i / (na - 1)
        ring = []
        for j in range(ns + 1):
            s = -1 + 2 * j / ns
            ring.append(hood_point(t, s))
        rings.append(ring)
    ob = rings_mesh('Hood', rings, M['bone'], closed_ring=False, track=False)
    bake(ob, solidify=0.024, subsurf=0)
    return ob


RIB_X = (0.63, 0.535, 0.44, 0.345, 0.25, 0.155, 0.06)


def rib_path(x, i):
    """A rib on the +Y side: out of the dome's flank, bulging out, sweeping back and down to the keel / claw."""
    top = 0.80 - 0.012 * math.sin(math.pi * (i + 0.5) / len(RIB_X))
    drop = 0.43 - 0.018 * i
    sw = 0.25 - 0.02 * i  # the front ribs sweep further back: a fan converging on the claw
    return [(x + 0.01, 0.175, top), (x - 0.005, 0.232, top - 0.07), (x - 0.04 - 0.1 * sw, 0.246, top - 0.19), (x - sw * 0.6, 0.238, top - drop * 0.72),
            (x - sw, 0.205, top - drop)]


def build_bone(M):
    """Everything bone, fused into one skin. Returns the fused object (in PARTS)."""
    bn = M['bone']
    parts = []
    for k in TANK:
        k.pop('t', None)
    parts.append(loft('Tank', TANK, bn, 60, 36, cap0='point', cap1='point', subsurf=0, track=False))
    tank_tree = bvh([parts[0]])

    def on_tank(x, y, out=0.004):
        h = cast(tank_tree, (x, y, 2.0), (0, 0, -1))
        return h[0] + h[1] * out if h else None
    for sgn in (-1, 1):
        seam = [on_tank(x, sgn * (0.135 + 0.02 * smoothstep(0.3, 0.65, x) - 0.03 * smoothstep(0.2, -0.1, x)))
                for x in (0.66, 0.58, 0.48, 0.38, 0.28, 0.18, 0.08, -0.02, -0.10)]
        parts.append(tube('Seam', [p for p in seam if p], lambda s: 0.010 + 0.005 * math.sin(math.pi * s), bn, sides=8, segs=40,
                          cap0='point', cap1='point', track=False))
    spine = [on_tank(x, 0.0, 0.002) for x in (0.045, -0.02, -0.09, -0.15)]
    parts.append(tube('TankSpine', [p for p in spine if p], lambda s: 0.006 + 0.010 * math.sin(math.pi * min(s * 1.4, 1)), bn, sides=8,
                      segs=16, cap0='point', cap1='point', track=False))
    # beetle lip: the carapace's rolled lower edge, flaring out over the ribs
    for sgn in (-1, 1):
        lip = [key(0.74, 0.80, 0.03, 0.010, 0.010, y=sgn * 0.12), key(0.64, 0.775, 0.04, 0.018, 0.018, y=sgn * 0.19),
               key(0.50, 0.785, 0.045, 0.02, 0.02, y=sgn * 0.218), key(0.34, 0.80, 0.045, 0.02, 0.02, y=sgn * 0.222),
               key(0.18, 0.805, 0.042, 0.018, 0.018, y=sgn * 0.21), key(0.04, 0.792, 0.035, 0.016, 0.016, y=sgn * 0.18),
               key(-0.10, 0.765, 0.022, 0.012, 0.012, y=sgn * 0.13)]
        parts.append(loft('Lip', lip, bn, 40, 14, cap0='point', cap1='point', subsurf=0, track=False))
    # ribcage: ribs sweep from under the lip, out and down and back to the keel
    for sgn in (-1, 1):
        for i, x in enumerate(RIB_X):
            c = [Vector((p[0], sgn * p[1], p[2])) for p in rib_path(x, i)]
            k = (1.0, 0.82, 1.08, 0.88, 1.04, 0.84, 0.96)[i]
            parts.append(tube('Rib', c, lambda s, k=k: k * (0.022 - 0.011 * s + 0.004 * math.sin(math.pi * s)), bn, sides=10, segs=28,
                              cap0='point', cap1='point', track=False))
        # keel: the lower rail the ribs land on, from the front down-tube back to the swingarm pivot
        keel = [(0.56, 0.11, 0.62), (0.47, 0.16, 0.42), (0.36, 0.18, 0.28), (0.18, 0.185, 0.235), (-0.02, 0.185, 0.25),
                (-0.16, 0.19, 0.32), (-0.24, 0.19, 0.42)]
        parts.append(tube('Keel', [Vector((p[0], sgn * p[1], p[2])) for p in keel], lambda s: 0.028 - 0.006 * s, bn, sides=12,
                          segs=40, cap0='point', cap1='point', track=False))
        # the swingarm claw: a broad bone plate from under the engine back to the rear axle, outside the tyre
        claw = [key(0.10, 0.165, 0.020, 0.006, 0.006, y=sgn * 0.205, e=3.5), key(0.03, 0.225, 0.022, 0.075, 0.075, y=sgn * 0.207, e=3.5),
                key(-0.10, 0.31, 0.024, 0.155, 0.155, y=sgn * 0.21, e=3.5), key(-0.28, 0.315, 0.024, 0.145, 0.145, y=sgn * 0.215, e=3.5),
                key(-0.48, 0.325, 0.024, 0.115, 0.115, y=sgn * 0.218, e=3.5), key(-0.66, 0.325, 0.024, 0.075, 0.075, y=sgn * 0.222, e=3.5),
                key(-0.78, 0.325, 0.026, 0.05, 0.05, y=sgn * 0.225, e=3.5), key(-0.86, 0.33, 0.02, 0.02, 0.02, y=sgn * 0.222, e=3.5)]
        parts.append(loft('Claw', claw, bn, 50, 24, cap0='point', cap1='point', subsurf=0, track=False))
        # the claw's rolled upper edge, sweeping up into a point at its front
        edge = [(0.02, 0.215, 0.29), (-0.08, 0.22, 0.45), (-0.13, 0.225, 0.485), (-0.30, 0.225, 0.462), (-0.50, 0.228, 0.44),
                (-0.68, 0.232, 0.40), (-0.80, 0.235, 0.37)]
        parts.append(tube('ClawEdge', [Vector((p[0], sgn * p[1], p[2])) for p in edge], lambda s: 0.016 + 0.006 * math.sin(math.pi * s),
                          bn, sides=10, segs=40, cap0='point', cap1='point', track=False))
        # front fork guards: bone sleeves down the forks to a claw over the axle
        guard = []
        for z in (0.86, 0.76, 0.64, 0.53, 0.45):
            x = 0.56 + 0.4452 * (0.84 - z)
            guard.append((x, 0.138, z))
        guard += [(0.80, 0.142, 0.395), (0.835, 0.142, 0.37)]
        parts.append(tube('ForkGuard', [Vector((p[0], sgn * p[1], p[2])) for p in guard],
                          lambda s: 0.036 * (1 - 0.6 * s ** 1.3), bn, sides=12, segs=30, squash=1.5, cap0='point', cap1='point', track=False))
        # rear vertebral struts: from the hood's flank down to the claw, behind the seat
        for k, (x0, x1) in enumerate(((-0.40, -0.18), (-0.47, -0.32))):
            strut = [(x0, 0.19, 0.70), (x0 + 0.04, 0.215, 0.58), ((x0 + x1) / 2, 0.222, 0.48), (x1, 0.215, 0.43)]
            parts.append(tube('Strut', [Vector((p[0], sgn * p[1], p[2])) for p in strut], (0.022, 0.016), bn, sides=10, segs=20,
                              cap0='point', cap1='point', track=False))
    # nose cowl round the headstock, the visor's seat
    nose = [key(0.58, 0.80, 0.155, 0.09, 0.10), key(0.70, 0.80, 0.165, 0.085, 0.085), key(0.80, 0.79, 0.14, 0.08, 0.075),
            key(0.87, 0.77, 0.09, 0.055, 0.055), key(0.905, 0.76, 0.015, 0.012, 0.012)]
    parts.append(loft('Nose', nose, bn, 30, 28, cap0='ngon', cap1='point', subsurf=0, track=False))
    # dash cowl: a bone pedestal off the tank's nose, behind the dash
    parts.append(loft('DashCowl', [key(0.74, 0.86, 0.05, 0.03, 0.03), key(0.70, 0.93, 0.13, 0.05, 0.05),
                                   key(0.668, 0.97, 0.15, 0.04, 0.045), key(0.652, 0.985, 0.12, 0.025, 0.03)],
                      bn, 20, 24, cap0='point', cap1='ngon', subsurf=0, track=False))
    # sub-frame under the seat, from the tank's tail into the hood
    parts.append(loft('SubFrame', [key(-0.02, 0.73, 0.10, 0.05, 0.07), key(-0.20, 0.72, 0.125, 0.05, 0.07),
                                   key(-0.36, 0.73, 0.13, 0.06, 0.08), key(-0.50, 0.76, 0.10, 0.05, 0.06)],
                      bn, 24, 20, cap0='point', cap1='point', subsurf=0, track=False))
    # the hood, its rolled rim, and vertebrae over its back
    hood = build_hood(M)
    parts.append(hood)
    for sgn in (-1, 1):
        rim = [hood_point(t, sgn * 1.0) + Vector((0, -sgn * 0.004, 0)) for t in (0.0, 0.1, 0.2, 0.3, 0.42, 0.55, 0.68, 0.8, 0.9, 1.0)]
        parts.append(tube('HoodRim', rim, lambda s: 0.017 * (1 - 0.5 * s ** 2), bn, sides=10, segs=48, cap0='point', cap1='point', track=False))
        # side ridges along the arch's shoulders
        ridge = [hood_point(t, sgn * 0.33, out=0.004) for t in (0.08, 0.2, 0.35, 0.5, 0.65, 0.8, 0.92)]
        parts.append(tube('HoodRidge', ridge, lambda s: 0.012 + 0.006 * math.sin(math.pi * s), bn, sides=8, segs=36,
                          cap0='point', cap1='point', track=False))
    spine = [hood_point(t, 0.0, out=0.004) for t in (0.05, 0.18, 0.32, 0.48, 0.62, 0.76, 0.88, 1.0)]
    # the mouth: a thick rolled rim round the hood's open rear end, over the light face
    mouth = [hood_point(1.0, s, out=-0.006) + Vector((0.004, 0, 0)) for s in (-1.0, -0.8, -0.6, -0.45, -0.25, 0.0, 0.25, 0.45, 0.6, 0.8, 1.0)]
    parts.append(tube('Mouth', mouth, 0.019, bn, sides=10, segs=40, cap0='point', cap1='point', track=False))
    lipb = [hood_point(1.0, -1.0) + Vector((0.01, 0.01, 0.004)), hood_point(1.0, 1.0) + Vector((0.01, -0.01, 0.004))]
    parts.append(tube('MouthLip', [lipb[0], (lipb[0] + lipb[1]) / 2 + Vector((0.01, 0, -0.012)), lipb[1]], 0.016, bn, sides=10, segs=16,
                      cap0='point', cap1='point', track=False))
    parts.append(tube('HoodSpine', spine, lambda s: 0.013 + 0.008 * math.sin(math.pi * s), bn, sides=10, segs=40,
                      cap0='point', cap1='point', track=False))
    for t in (0.18, 0.30, 0.42, 0.54, 0.66):
        arc = [hood_point(t, s, out=0.003) for s in (-0.72, -0.5, -0.25, 0.0, 0.25, 0.5, 0.72)]
        parts.append(tube('Vertebra', arc, lambda s: 0.009 + 0.006 * math.sin(math.pi * s), bn, sides=8, segs=30,
                          cap0='point', cap1='point', track=False))
    # the tail-light face under the hood's rear: a bone grille, slits cut through it
    tilt = TAIL_TILT
    face_c = TAIL_C
    parts.append(ellipsoid('TailFace', face_c, (0.105, 0.118, 0.02), bn, rot=(0, tilt, 0), segs=40, rings=16, track=False))
    A = Vector((-math.cos(tilt), 0, math.sin(tilt)))   # along the face, front-low to back-high
    Nf = Vector((math.sin(tilt), 0, math.cos(tilt)))   # into the hood (up-forward)
    cutters = []
    for q in (-0.069, -0.023, 0.023, 0.069):
        D = (A * math.cos(math.radians(22)) + Y * math.sin(math.radians(22))).normalized()
        P = Nf.cross(D).normalized()  # (D, P, Nf) right-handed, or the box comes out inside-out and cuts nothing
        Mx = Matrix.Identity(4)
        for r_, v_ in enumerate((D * 0.068, P * 0.0115, Nf * 0.05)):
            Mx[0][r_], Mx[1][r_], Mx[2][r_] = v_
        Mx.translation = face_c + Y * q
        cutters.append(box('Slit', Mx, bn))
    # holes: the claw's big window and a small one behind it, vents in the nose, ports in the hood's flanks
    for sgn in (-1, 1):
        cutters.append(ellipsoid('Hole', (-0.32, sgn * 0.215, 0.305), (0.14, 0.05, 0.072), bn, track=False))
        cutters.append(ellipsoid('Hole', (-0.63, sgn * 0.222, 0.33), (0.065, 0.05, 0.034), bn, track=False))
        cutters.append(ellipsoid('Hole', (0.03, sgn * 0.207, 0.235), (0.045, 0.05, 0.03), bn, rot=(0, 0.5, 0), track=False))
        cutters.append(ellipsoid('Hole', (0.76, sgn * 0.16, 0.785), (0.035, 0.05, 0.016), bn, rot=(0, 0.15, 0), track=False))
        cutters.append(ellipsoid('Hole', (-0.60, sgn * 0.215, 0.72), (0.075, 0.05, 0.042), bn, rot=(0, 0.25, 0), track=False))
        cutters.append(ellipsoid('Hole', (-0.79, sgn * 0.20, 0.80), (0.045, 0.05, 0.022), bn, rot=(0, 0.2, 0), track=False))
    bone = fuse('Bone', parts, voxel=0.0042, cutters=cutters, smooth_iter=12, smooth_lambda=0.85, target_tris=58000, mat=bn,
                post=None if '--noconform' in ARGS else conform_tank)
    conform_tank(bone, normals=True)  # again on the decimated skin: exact heights, and the field's own normals (no creases)
    PARTS.append(bone)
    return bone


# ---------------------------------------------------------------- the tank under the button: bike.glb's surface
def tank_field():
    """bike.glb's tank height along ButtonCentre's normal, h(d, s), as a smooth polynomial fitted to
    art/align-bike3/bike1-tank.json (d back along -X, s along +Y)."""
    import numpy as np
    J = json.load(open(os.path.join(ALIGN, 'bike1-tank.json')))
    rows, hs = [], []
    terms = [(i, j) for i in range(6) for j in (0, 2, 4)]
    for d, row in zip(J['d'], J['h']):
        for s, h in zip(J['s'], row):
            if h is None or abs(s) > 0.121:
                continue
            rows.append([d ** i * s ** j for i, j in terms])
            hs.append(h)
    A, H = np.array(rows), np.array(hs)
    coef, *_ = np.linalg.lstsq(A, H, rcond=None)
    res = H - A @ coef
    keep = np.abs(res) < 0.006  # drop stray hits (a rib under the ray)
    coef, *_ = np.linalg.lstsq(A[keep], H[keep], rcond=None)
    res = H[keep] - A[keep] @ coef
    print('TANK FIELD fit rms', round(float(np.sqrt((res ** 2).mean())), 5), 'max', round(float(np.abs(res).max()), 5), 'dropped', int((~keep).sum()))
    return lambda d, s: float(sum(c * d ** i * s ** j for c, (i, j) in zip(coef, terms)))


def conform_tank(ob, normals=False):
    """Bring the bone skin's tank top onto bike.glb's around the button: fully over the track's footprint, easing out
    over 6 cm. Only the upward-facing tank surface near the target moves (not the dash cowl or the ribs). With
    `normals`, the patch also takes the height field's analytic normals (custom normals, exported to the glb), so the
    decimated triangles there shade as one smooth dome."""
    h1 = tank_field()
    me = ob.data
    moved, worst = 0, 0.0
    field_n = {}
    for v in me.vertices:
        rel = v.co - BC_O
        d, s, h = -rel.dot(BC_X), rel.dot(BC_Y), rel.dot(BC_N)
        if not (-0.24 < d < 0.36 and abs(s) < 0.15):
            continue
        if v.normal.dot(BC_N) < 0.55:
            continue
        target = h1(min(max(d, -0.30), 0.34), max(min(s, 0.12), -0.12))
        delta = target - h
        if abs(delta) > 0.045:
            continue
        wd = smoothstep(-0.23, -0.17, d) * (1 - smoothstep(0.29, 0.35, d))
        ws = 1 - smoothstep(0.09, 0.14, abs(s))
        w = wd * ws
        if w <= 0:
            continue
        v.co += BC_N * (delta * w)
        moved += 1
        worst = max(worst, abs(delta))
        if normals:
            e = 0.002
            dc, sc = min(max(d, -0.30), 0.34), max(min(s, 0.12), -0.12)
            hd = (h1(dc + e, sc) - h1(dc - e, sc)) / (2 * e)
            hs = (h1(dc, sc + e) - h1(dc, sc - e)) / (2 * e)
            fn = (BC_X * hd - BC_Y * hs + BC_N).normalized()
            field_n[v.index] = (fn, w)
    me.update()
    if normals:
        vn = []
        for v in me.vertices:
            n = v.normal.copy()
            if v.index in field_n:
                fn, w = field_n[v.index]
                n = n.lerp(fn, w).normalized()
            vn.append(n)
        me.normals_split_custom_set_from_vertices(vn)
    print('CONFORM tank verts moved', moved, 'largest correction (m)', round(worst, 4))


# ---------------------------------------------------------------- tendon, muscle, veins
def build_flesh(M, bone):
    td = M['tendon']
    # the muscle mass inside the ribcage: one lumpy wet body, fibres running down-back like the ribs
    mass = [key(0.68, 0.70, 0.05, 0.06, 0.08), key(0.58, 0.64, 0.165, 0.15, 0.17), key(0.42, 0.62, 0.188, 0.17, 0.18),
            key(0.22, 0.60, 0.19, 0.17, 0.17), key(0.04, 0.585, 0.175, 0.15, 0.15), key(-0.14, 0.59, 0.145, 0.12, 0.12),
            key(-0.30, 0.62, 0.07, 0.06, 0.07)]
    ob = loft('Muscle', mass, td, 44, 36, cap0='point', cap1='point', subsurf=1, track=True)
    fib = Vector((1, 0, -0.38)).normalized()
    for v in ob.data.vertices:
        p = v.co
        n = v.normal
        d = 0.009 * noise.noise(p * 7.0) + 0.003 * noise.noise(p * 22.0 + Vector((2, 5, 1))) + 0.0018 * math.sin(p.dot(fib) * 260)
        v.co = p + n * d
    ob.data.update()
    # seat: a muscle saddle, fibres along it
    seat = [key(-0.07, 0.79, 0.09, 0.022, 0.04, e=3), key(-0.18, 0.796, 0.13, 0.03, 0.05, e=3), key(-0.30, 0.80, 0.14, 0.03, 0.05, e=3),
            key(-0.41, 0.815, 0.125, 0.03, 0.05, e=3), key(-0.47, 0.83, 0.05, 0.02, 0.03, e=3)]
    st = loft('Seat', seat, td, 22, 24, cap0='point', cap1='point', subsurf=1, track=True)
    for v in st.data.vertices:
        p = v.co
        if v.normal.z > 0.3:
            v.co = p + v.normal * (0.0022 * math.sin(p.y * 190) + 0.002 * noise.noise(p * 15))
    st.data.update()
    # tendon cords across the rib gaps, and bundles from under the hood down to the claws
    rnd = random.Random(11)
    for sgn in (-1, 1):
        for i in range(len(RIB_X) - 1):
            a, b = rib_path(RIB_X[i], i), rib_path(RIB_X[i + 1], i + 1)
            for j in range(2):
                f = 0.35 + 0.3 * j + rnd.uniform(-0.05, 0.05)
                ctrl = [(pa[0] * (1 - f) + pb[0] * f, pa[1] - 0.018, pa[2]) for pa, pb in zip(a, b)]
                tube('Cord', [Vector((p[0], sgn * p[1], p[2])) for p in ctrl[1:]], lambda s: 0.0075 + 0.003 * math.sin(math.pi * s),
                     td, sides=7, segs=20)
        for k in range(4):
            x0 = -0.40 - 0.045 * k
            ctrl = [(x0, 0.15, 0.78), (x0 - 0.01, 0.185, 0.66), (x0 + 0.03 + 0.02 * k, 0.198, 0.55), (x0 + 0.10 + 0.03 * k, 0.205, 0.45)]
            tube('Sinew', [Vector((p[0], sgn * p[1], p[2])) for p in ctrl], lambda s: 0.012 * (1 - 0.3 * math.sin(math.pi * s)),
                 td, sides=8, segs=20)
        # a bundle under the tank's lip back into the seat
        for k in range(3):
            ctrl = [(0.55, 0.15 + 0.012 * k, 0.74 - 0.02 * k), (0.30, 0.175 + 0.01 * k, 0.72 - 0.015 * k), (0.05, 0.16, 0.71 - 0.01 * k),
                    (-0.18, 0.13, 0.72)]
            tube('Band', [Vector((p[0], sgn * p[1], p[2])) for p in ctrl], 0.008, td, sides=7, segs=30)
    # glowing veins over the muscle's flanks (Bike3Vein)
    tree = bvh([ob])
    rnd = random.Random(5)
    for sgn in (-1, 1):
        for k in range(12):
            x0 = rnd.uniform(-0.12, 0.55)
            z0 = rnd.uniform(0.48, 0.74)
            pts = []
            for i in range(8):
                s = i / 7
                x = x0 - 0.12 * s + rnd.uniform(-0.01, 0.01)
                z = z0 - 0.18 * s + 0.03 * math.sin(s * 5 + k)
                h = cast(tree, (x, sgn * 0.6, z), (0, -sgn, 0))
                if h:
                    pts.append(h[0] + h[1] * 0.002)
            if len(pts) >= 4:
                tube('Vein', pts, lambda s: 0.0026 * (1 - 0.6 * s) + 0.001, M['vein'], sides=6, cap1='point')


# ---------------------------------------------------------------- dark metal: engine, hoses, forks, bars, stand
def build_metal(M):
    mt = M['metal']
    # crankcase and two finned cylinders in the ribcage's floor
    loft('Crankcase', [key(0.40, 0.31, 0.04, 0.05, 0.05, e=3), key(0.34, 0.30, 0.12, 0.10, 0.10, e=3), key(0.0, 0.29, 0.13, 0.11, 0.09, e=3),
                       key(-0.16, 0.33, 0.12, 0.09, 0.08, e=3), key(-0.22, 0.34, 0.03, 0.03, 0.03, e=3)], mt, 24, 24, cap0='point', cap1='point', subsurf=0)
    for (x, z, tilt) in ((0.30, 0.40, 0.55), (0.04, 0.42, -0.45)):
        prof = [(0.0, -0.002)]
        for k in range(9):
            y0 = 0.02 * k
            prof += [(0.06, y0), (0.078, y0 + 0.004), (0.078, y0 + 0.010), (0.06, y0 + 0.014)]
        prof += [(0.05, 0.19), (0.0, 0.195)]
        ob = lathe('Cylinder', prof, mt, 24, closed_prof=False)
        ob.data.transform(Matrix.Translation(Vector((x, 0, z))) @ Matrix.Rotation(tilt, 4, 'Y') @ Matrix.Rotation(-math.pi / 2, 4, 'X'))
    # ribbed hoses coiling through the lower frame, both sides
    hoses = [
        ([(0.46, 0.08, 0.50), (0.46, 0.165, 0.38), (0.38, 0.19, 0.27), (0.22, 0.19, 0.215), (0.06, 0.175, 0.24), (-0.06, 0.15, 0.30)], 0.022, 22),
        ([(0.30, 0.10, 0.47), (0.22, 0.188, 0.38), (0.10, 0.19, 0.33), (-0.04, 0.18, 0.36), (-0.14, 0.16, 0.44)], 0.019, 18),
        ([(0.14, 0.09, 0.45), (0.04, 0.17, 0.41), (-0.08, 0.17, 0.47), (-0.20, 0.16, 0.56), (-0.28, 0.13, 0.64)], 0.017, 16),
        ([(0.52, 0.06, 0.56), (0.55, 0.13, 0.46), (0.50, 0.17, 0.32), (0.44, 0.15, 0.22)], 0.016, 14),
    ]
    for ctrl, r, n in hoses:
        for c in both(ctrl):
            tube('Hose', c, ribbed(r, n), mt, sides=10, segs=n * 4)
    # exhaust: twin pipes low under the belly
    for c in both([(0.40, 0.09, 0.36), (0.36, 0.12, 0.20), (0.16, 0.13, 0.15), (-0.06, 0.13, 0.16), (-0.18, 0.12, 0.22)]):
        tube('Exhaust', c, lambda s: 0.026 + 0.004 * s, mt, sides=14, segs=40, cap1='ngon')
    # rear monoshock: a coil spring round a damper, under the seat
    a, b = Vector((-0.10, 0, 0.60)), Vector((-0.40, 0, 0.47))
    tube('Damper', [a, b], 0.016, mt, sides=10, segs=4)
    ax = (b - a)
    L = ax.length
    T = ax.normalized()
    U = T.cross(Y).normalized()
    V = T.cross(U)
    pts = []
    turns = 8
    for i in range(turns * 16 + 1):
        s = i / (turns * 16)
        ph = TAU * turns * s
        pts.append(a + T * (0.03 + (L - 0.06) * s) + (U * math.cos(ph) + V * math.sin(ph)) * 0.034)
    tube('Spring', pts, 0.006, mt, sides=6, segs=len(pts))
    # front fork legs along the steering axis, axle nuts, calipers
    for sgn in (-1, 1):
        top, bot = Vector((0.56, sgn * 0.125, 0.84)), Vector((0.785, sgn * 0.125, 0.335))
        tube('Fork', [top, bot], lambda s: 0.022 + 0.006 * smoothstep(0.55, 0.65, s), mt, sides=14, segs=12)
        tube('Axle', [Vector((0.78, sgn * 0.10, 0.315)), Vector((0.78, sgn * 0.158, 0.315))], 0.018, mt, sides=12, segs=2)
        ellipsoid('Caliper', (0.70, sgn * 0.128, 0.42), (0.045, 0.02, 0.03), mt, rot=(0, -0.7, 0), segs=16, rings=8)
        # rear axle caps through the claws
        tube('Axle', [Vector((-0.78, sgn * 0.17, 0.325)), Vector((-0.78, sgn * 0.258, 0.325))], 0.022, mt, sides=14, segs=2)
        tube('AxleNut', [Vector((-0.78, sgn * 0.255, 0.325)), Vector((-0.78, sgn * 0.272, 0.325))], 0.03, mt, sides=6, segs=1)
    # clip-on bars from the fork tops out through the carapace's flanks, rubber grips, bar ends
    for sgn in (-1, 1):
        bar = [Vector((0.54, sgn * 0.11, 0.87)), Vector((0.49, sgn * 0.22, 0.862)), Vector((0.45, sgn * 0.30, 0.852)), Vector((0.43, sgn * 0.33, 0.849))]
        tube('Bar', bar, 0.014, mt, sides=12, segs=20)
        grip = [Vector((0.435, sgn * 0.322, 0.85)), Vector((0.40, sgn * 0.415, 0.843))]
        tube('Grip', grip, ribbed(0.019, 12, 0.06, 2), M['tyre'], sides=14, segs=24)
        tube('BarEnd', [Vector((0.40, sgn * 0.415, 0.843)), Vector((0.396, sgn * 0.427, 0.842))], 0.021, mt, sides=14, segs=2)
        ellipsoid('Switch', (0.448, sgn * 0.305, 0.863), (0.028, 0.02, 0.026), mt, segs=16, rings=8)
        lever = [Vector((0.455, sgn * 0.31, 0.846)), Vector((0.47, sgn * 0.37, 0.839)), Vector((0.465, sgn * 0.42, 0.833))]
        tube('Lever', lever, 0.006, mt, sides=8, segs=12, squash=0.5)
    # kickstand on +Y (as bike.glb's: the foot touches the ground once the bike leans)
    foot_y = 0.30
    foot_z = (0.015 + math.sin(LEAN) * foot_y) / math.cos(LEAN)
    tube('Stand', [Vector((-0.04, 0.17, 0.25)), Vector((-0.12, 0.235, 0.15)), Vector((-0.20, foot_y, foot_z))], (0.016, 0.011), mt, sides=10, segs=12)
    tube('StandFoot', [Vector((-0.23, foot_y, foot_z)), Vector((-0.17, foot_y, foot_z))], 0.015, mt, sides=10, segs=2, squash=0.6)


# ---------------------------------------------------------------- visor, tail lights
def build_visor(M):
    nr, nc = 16, 30
    verts = []
    for i in range(nr + 1):
        v = i / nr
        for j in range(nc + 1):
            u = -1 + 2 * j / nc
            B = Vector((0.82 - 0.16 * u * u, 0.17 * u, 0.868 + 0.03 * u * u))
            T = Vector((0.66 - 0.05 * u * u, 0.14 * u, 1.13 - 0.05 * u * u))
            p = B.lerp(T, v) + Vector((0.035 * math.sin(math.pi * v) * (1 - 0.4 * u * u), 0, 0))
            verts.append(p)
    faces = []
    for i in range(nr):
        for j in range(nc):
            a = i * (nc + 1) + j
            faces.append((a, a + 1, a + nc + 2, a + nc + 1))
    ob = new_obj('Visor', verts, faces, M['smoke'])
    bake(ob, solidify=0.004, subsurf=0)
    return ob


def build_tail_light(M):
    Nf = Vector((math.sin(TAIL_TILT), 0, math.cos(TAIL_TILT)))
    ellipsoid('TailLight', TAIL_C + Nf * 0.02, (0.098, 0.11, 0.007), M['tail'], rot=(0, TAIL_TILT, 0), segs=32, rings=10)


# ---------------------------------------------------------------- dash (as build-bike2.py)
def build_dash(M):
    """Bike3Dash: a curved display between the bars, just ahead of the button, facing the rider's eye.
    UV 0-1: u to the rider's right (-Y), v up."""
    eye = RIDER_EYE.translation
    D = DASH_C
    N = (eye - D)
    N.y = 0
    N.normalize()
    U = Vector((-N.z, 0, N.x)).normalized()
    if U.z < 0:
        U = -U
    Rt = Vector((0, -1, 0))
    width, height, Rc, corner = 0.28, 0.09, 0.30, 0.30
    nu, nv = 32, 8

    def panel(w, h, off):
        out = []
        for j in range(nv + 1):
            for i in range(nu + 1):
                u, v = i / nu, j / nv
                th = (u - 0.5) * w / Rc
                e = abs(2 * u - 1)
                k = 1.0 if e < 1 - corner else math.sqrt(max(0.0, 1 - ((e - (1 - corner)) / corner) ** 2))
                vv = (v - 0.5) * k + 0.5
                out.append(D - N * off + Rt * (math.sin(th) * Rc) - N * ((1 - math.cos(th)) * Rc) + U * ((vv - 0.5) * h))
        return out
    faces, uvs = [], []
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))
            uvs.append(((i / nu, j / nv), ((i + 1) / nu, j / nv), ((i + 1) / nu, (j + 1) / nv), (i / nu, (j + 1) / nv)))
    dash = new_obj('Bike3Dash', panel(width, height, 0.0), faces, M['dash'], uvs=uvs, track=False)
    if sum(p.normal.dot(N) for p in dash.data.polygons) < 0:
        dash.data.flip_normals()
    bez = new_obj('Bezel', panel(width + 0.03, height + 0.028, 0.004), faces, M['bone'])
    if sum(p.normal.dot(N) for p in bez.data.polygons) < 0:
        bez.data.flip_normals()
    bake(bez, solidify=0.03, subsurf=0, solid_offset=-1)
    return dash


# ---------------------------------------------------------------- the throttle button (as build-bike2.py)
def build_button(M, body):
    import numpy as np
    tree = bvh([body])

    def hit_z(x, y):
        h = cast(tree, (x, y, 2.0), (0, 0, -1))
        return h[0].z if h else None
    a, r = BUTTON_LEN / 2, BUTTON_WID / 2
    rows, zs = [], []
    for x in np.linspace(BUTTON_X - a - 0.01, BUTTON_X + a + 0.01, 17):
        for y in np.linspace(-r - 0.01, r + 0.01, 9):
            z = hit_z(x, y)
            if z is not None:
                dx = x - BUTTON_X
                rows.append([1, dx, y, dx * dx, dx * y, y * y])
                zs.append(z)
    A, Z = np.array(rows), np.array(zs)
    coef, *_ = np.linalg.lstsq(A, Z, rcond=None)
    lift = float((Z - A @ coef).max()) + 0.003
    FACE_H = 0.0022
    pin = BUTTON_CENTRE.translation.z - FACE_H - (coef[0] + lift)
    print('BUTTON fit lift (m):', round(lift, 4), 'pin offset (m):', round(pin, 5))
    lift += pin

    def base(x, y):
        dx = x - BUTTON_X
        c0, c1, c2, c3, c4, c5 = coef
        z = c0 + c1 * dx + c2 * y + c3 * dx * dx + c4 * dx * y + c5 * y * y + lift
        n = Vector((-(c1 + 2 * c3 * dx + c4 * y), -(c2 + c4 * dx + 2 * c5 * y), 1)).normalized()
        return Vector((x, y, z)), n

    straight = a - r
    n_cap, n_side = 14, 10

    def outline(rr):
        pts = []
        for k in range(n_cap):
            t = math.pi / 2 - math.pi * k / n_cap
            pts.append((BUTTON_X + straight + rr * math.cos(t), rr * math.sin(t)))
        for k in range(n_side):
            pts.append((BUTTON_X + straight - 2 * straight * k / n_side, -rr))
        for k in range(n_cap):
            t = -math.pi / 2 - math.pi * k / n_cap
            pts.append((BUTTON_X - straight + rr * math.cos(t), rr * math.sin(t)))
        for k in range(n_side):
            pts.append((BUTTON_X - straight + 2 * straight * k / n_side, rr))
        return pts
    profile = [(-0.0015, -0.004), (0.0, 0.0), (0.0025, 0.0035), (0.0055, 0.0055), (0.009, 0.005), (0.0125, 0.0028), (0.016, 0.0022)]
    d = 0.016
    while r - d > 0.012:
        d += 0.008
        profile.append((d, 0.0022))
    profile.append((r, 0.0022))
    rings = []
    for inset, h in profile:
        ring = []
        for x, y in outline(r - inset):
            p, n = base(x, y)
            ring.append(p + n * h)
        rings.append(ring)
    btn = rings_mesh('Bike3Button', rings, M['button'], track=False)
    me = btn.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    me.update()
    if sum(p.normal.z for p in me.polygons) < 0:
        me.flip_normals()

    W_, L_, STROKE, PITCH = 0.036, 0.030, 0.0062, 0.031
    d_ = STROKE * math.hypot(L_, W_) / W_
    span = 2 * PITCH + L_ + d_
    bm = bmesh.new()
    for k in range(3):
        tip = BUTTON_X + span / 2 - k * PITCH
        ol = [(tip, 0), (tip - L_, W_), (tip - L_ - d_, W_), (tip - d_, 0), (tip - L_ - d_, -W_), (tip - L_, -W_)]
        face = bm.faces.new([bm.verts.new((u, v, 0.0)) for u, v in ol])
        ext = bmesh.ops.extrude_face_region(bm, geom=[face])
        bmesh.ops.translate(bm, verts=[e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)], vec=(0, 0, 0.0006))
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method='BEAUTY', ngon_method='BEAUTY')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    gme = bpy.data.meshes.new('Bike3ButtonGlyph')
    bm.to_mesh(gme)
    bm.free()
    for v in gme.vertices:
        x, y, tz = v.co.x, v.co.y, v.co.z
        p, n = base(x, y)
        v.co = p + n * (FACE_H + 0.0015 + tz)
    gme.materials.append(M['glyph'])
    gme.shade_flat()
    glyph = bpy.data.objects.new('Bike3ButtonGlyph', gme)
    bpy.context.scene.collection.objects.link(glyph)

    pc, nc = base(BUTTON_X, 0.0)
    pc = pc + nc * FACE_H
    print('BUTTON face centre', tuple(round(c, 5) for c in pc), 'ButtonCentre', tuple(round(c, 5) for c in BUTTON_CENTRE.translation),
          'normal', tuple(round(c, 4) for c in nc))
    centre = bpy.data.objects.new('ButtonCentre', None)
    centre.empty_display_type, centre.empty_display_size = 'ARROWS', 0.05
    centre.matrix_world = BUTTON_CENTRE
    centre['button_size_m'] = [BUTTON_LEN, BUTTON_WID]
    eye = bpy.data.objects.new('RiderEye', None)
    eye.empty_display_type, eye.empty_display_size = 'ARROWS', 0.08
    eye.matrix_world = RIDER_EYE
    eye['view'] = 'local +Y forward in Blender; glTF/three local -Z forward, +Y up'
    for ob in (centre, eye):
        bpy.context.scene.collection.objects.link(ob)
    return [btn, glyph, centre, eye]


def measure_track(body, centre):
    """The tank's profile behind/ahead of the button along ButtonCentre's normal (button meshes excluded): the body's
    own mesh, bike-local."""
    me = body.data
    tree = BVHTree.FromPolygons([v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    h1 = tank_field()

    def h_at(d, s):
        p = BC_O - BC_X * d + BC_Y * s + BC_N * 0.3
        hit = tree.ray_cast(p, -BC_N)
        return round(0.3 - hit[3], 5) if hit[0] is not None else None
    centre_h = [h_at(d, 0.0) for d in TRACK_D]
    sp = [h_at(d, TRACK_S) for d in TRACK_D]
    sm = [h_at(d, -TRACK_S) for d in TRACK_D]
    side = [round((a + b) / 2, 5) for a, b in zip(sp, sm)]
    centre['TRACK_D'] = TRACK_D
    centre['TRACK_CENTRE'] = centre_h
    centre['TRACK_SIDE'] = side
    worst = 0.0
    for d in [-0.15 + 0.01 * i for i in range(41)]:
        for s in (-0.07, -0.035, 0.0, 0.035, 0.07):
            h = h_at(d, s)
            if h is not None:
                worst = max(worst, abs(h - h1(d, s)))
    print('TRACK_D', TRACK_D)
    print('TRACK_CENTRE', centre_h)
    print('TRACK_SIDE', side, 'asym', [round(a - b, 4) for a, b in zip(sp, sm)])
    print('TRACK bike1 centre', [round(h1(d, 0), 5) for d in TRACK_D])
    print('TRACK worst |bike3 - bike1| over -0.15..+0.25 x +-0.07 (m):', round(worst, 4))


# ---------------------------------------------------------------- render setup (review only, not exported)
def setup_render(scene):
    scene.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    try:
        prefs.compute_device_type = 'METAL'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        scene.cycles.device = 'GPU'
    except Exception as e:
        print('GPU unavailable', e)
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 10
    scene.cycles.transparent_max_bounces = 16
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    # hive sunset: rose overhead, a hot peach band at the horizon, warm dusk below
    world = bpy.data.worlds.new('HiveWorld')
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes['Background']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    remap = nt.nodes.new('ShaderNodeMapRange')
    remap.inputs['From Min'].default_value = -1.0
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    nt.links.new(sep.outputs['Z'], remap.inputs['Value'])
    nt.links.new(remap.outputs['Result'], ramp.inputs['Fac'])
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, (0.05, 0.025, 0.025, 1)
    cr.elements[1].position, cr.elements[1].color = 1.0, (0.30, 0.10, 0.12, 1)
    for pos, c in ((0.48, (0.16, 0.07, 0.06, 1)), (0.50, (1.5, 0.62, 0.40, 1)), (0.53, (1.1, 0.48, 0.42, 1)), (0.65, (0.65, 0.25, 0.26, 1))):
        e = cr.elements.new(pos)
        e.color = c
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.0
    col = bpy.data.collections.new('Render')
    scene.collection.children.link(col)
    # low warm sun ahead-left of the bike (as the concept: the sun over the city, the bike backlit)
    sd = bpy.data.lights.new('Sun', 'SUN')
    sd.color = (1.0, 0.62, 0.42)
    sd.energy = 3.5
    sd.angle = math.radians(3)
    sun = bpy.data.objects.new('Sun', sd)
    sun.rotation_euler = (Vector((0.8, 0.55, 0.28)).to_track_quat('Z', 'Y')).to_euler()
    col.objects.link(sun)
    # warm stone 'architecture' panels around, unseen by the camera, for soft fill and reflections
    for loc, size, colr, s in (((0, 6, 3.5), (14, 4), (1.0, 0.82, 0.72), 1.6), ((-3, -5, 3.5), (10, 3), (1.0, 0.7, 0.62), 1.2),
                               ((-6, 1, 2.5), (6, 3), (1.0, 0.75, 0.6), 1.4), ((0, 0, 6), (6, 3), (1.0, 0.8, 0.75), 1.0)):
        me = bpy.data.meshes.new('Panel')
        me.from_pydata([(-size[0] / 2, -size[1] / 2, 0), (size[0] / 2, -size[1] / 2, 0), (size[0] / 2, size[1] / 2, 0), (-size[0] / 2, size[1] / 2, 0)], [], [(0, 1, 2, 3)])
        p = bpy.data.objects.new('Panel', me)
        p.location = loc
        p.rotation_euler = (Vector((0, 0, 0.6)) - Vector(loc)).to_track_quat('Z', 'Y').to_euler()
        p.visible_camera = False
        pm = bpy.data.materials.new('PanelLight')
        pm.use_nodes = True
        pb = pm.node_tree.nodes['Principled BSDF']
        pb.inputs['Base Color'].default_value = (0, 0, 0, 1)
        pb.inputs['Emission Color'].default_value = (*colr, 1)
        pb.inputs['Emission Strength'].default_value = s
        me.materials.append(pm)
        col.objects.link(p)
    # wet stone deck
    me = bpy.data.meshes.new('Ground')
    s = 30
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new('Ground', me)
    col.objects.link(g)
    gm = bpy.data.materials.new('WetStone')
    gm.use_nodes = True
    gnt = gm.node_tree
    b = gnt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.16, 0.12, 0.11, 1)
    nz = gnt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 1.4
    mr = gnt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = 0.45
    mr.inputs['From Max'].default_value = 0.6
    mr.inputs['To Min'].default_value = 0.1
    mr.inputs['To Max'].default_value = 0.4
    gnt.links.new(nz.outputs['Fac'], mr.inputs['Value'])
    gnt.links.new(mr.outputs['Result'], b.inputs['Roughness'])
    me.materials.append(gm)
    ng = bpy.data.node_groups.new('Bloom', 'CompositorNodeTree')
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = ng.nodes.new('CompositorNodeRLayers')
    glare = ng.nodes.new('CompositorNodeGlare')
    glare.inputs['Type'].default_value = 'Bloom'
    glare.inputs['Threshold'].default_value = 1.5
    glare.inputs['Strength'].default_value = 0.3
    glare.inputs['Size'].default_value = 0.5
    out = ng.nodes.new('NodeGroupOutput')
    ng.links.new(rl.outputs['Image'], glare.inputs['Image'])
    ng.links.new(glare.outputs['Image'], out.inputs[0])
    scene.compositing_node_group = ng
    scene.render.use_compositing = True
    return col


def add_camera(col, name, loc, target=None, lens=28, ortho=None, rot=None, matrix=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36
    cd.clip_start = 0.02
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    cd.clip_end = 200
    ob = bpy.data.objects.new(name, cd)
    if matrix is not None:
        ob.matrix_world = matrix
    else:
        ob.location = loc
        if rot is not None:
            ob.rotation_euler = rot
        else:
            ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    col.objects.link(ob)
    return ob


def render_views(scene, col, body):
    os.makedirs(RENDER_DIR, exist_ok=True)
    cc = json.load(open(os.path.join(ALIGN, 'concept-cam3.json')))
    pc = json.load(open(os.path.join(ALIGN, 'plaza-cam3.json')))
    eye_w = body.matrix_world @ RIDER_EYE
    cams = {
        # fitted so our tyres, hubs and contacts land on the concepts' (art/align-bike3/fit_camera.py); not exported
        'concept': (add_camera(col, 'ConceptCam3', cc['location'], cc['look'], lens=cc['lens']), tuple(cc['size'])),
        'plaza': (add_camera(col, 'PlazaCam3', pc['location'], pc['look'], lens=pc['lens']), tuple(pc['size'])),
        # from the rider's eye, aimed between the button and the dash
        'rider': (add_camera(col, 'RiderCam3', eye_w.translation, body.matrix_world @ Vector((0.50, 0.0, 0.96)), lens=15), (1672, 941)),
        'side': (add_camera(col, 'CamSide3', (0, 8, 0.62), rot=(math.pi / 2, 0, math.pi), ortho=2.9), (1920, 1080)),
        'hero': (add_camera(col, 'CamHero3', (2.5, 3.5, 0.8), (0.05, 0, 0.58), lens=32), (1920, 1080)),
        'rear': (add_camera(col, 'CamRear3', (-3.6, 0.5, 1.25), (-0.4, 0, 0.62), lens=35), (1920, 1080)),
        'top': (add_camera(col, 'CamTop3', (0, 0, 8), rot=(0, 0, 0), ortho=2.9), (1920, 1080)),
    }
    suffix = f'-{TAG}' if TAG else ''
    for k, (cam, res) in cams.items():
        if VIEWS and k not in VIEWS:
            continue
        scene.camera = cam
        scene.render.resolution_x, scene.render.resolution_y = res
        scene.render.filepath = os.path.join(RENDER_DIR, f'bike3-{k}{suffix}.png')
        bpy.ops.render.render(write_still=True)
        print('rendered', scene.render.filepath)


# ---------------------------------------------------------------- main
def main():
    scene = reset()
    M = make_materials()
    bone = build_bone(M)
    build_flesh(M, bone)
    build_metal(M)
    build_visor(M)
    build_tail_light(M)
    dash = build_dash(M)
    extras = build_button(M, bone)
    per = {}
    for o in PARTS:
        per[o.name.split('.')[0]] = per.get(o.name.split('.')[0], 0) + tri_count(o)
    print('PARTS', sorted(per.items(), key=lambda kv: -kv[1]))
    body = join('Bike3', PARTS)
    PARTS.clear()
    measure_track(body, extras[2])

    wf = build_wheel('Wheel3Front', F_R, F_W, F_RIM, M, front=True)
    wr = build_wheel('Wheel3Rear', R_R, R_W, R_RIM, M, front=False)
    for w, axle in ((wf, F_AXLE), (wr, R_AXLE)):
        w.parent = body
        w.matrix_parent_inverse = Matrix.Identity(4)
        w.location = axle
    for ob in (*extras, dash):
        mw = ob.matrix_world.copy()
        ob.parent = body
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.matrix_basis = mw
    body.location = (0, 0, 0)
    body.rotation_euler = (-LEAN, 0, 0)
    bpy.context.view_layer.update()

    meshes = (body, wf, wr, dash, *[e for e in extras if e.type == 'MESH'])
    counts = {o.name: tri_count(o) for o in meshes}
    print('TRIANGLES', counts, 'total', sum(counts.values()))
    for n in ('ButtonCentre', 'RiderEye'):
        print('ANCHOR', n, [list(map(lambda v: round(v, 6), r)) for r in bpy.data.objects[n].matrix_local])

    col = setup_render(scene)
    scene.camera = None
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)

    bpy.ops.object.select_all(action='DESELECT')
    for o in (body, wf, wr, dash, *extras):
        o.select_set(True)
    os.makedirs(os.path.dirname(GLB_OUT), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=GLB_OUT, export_format='GLB', use_selection=True, export_apply=True, export_yup=True,
                              export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
                              export_draco_position_quantization=14, export_draco_normal_quantization=12,
                              export_draco_texcoord_quantization=12, export_cameras=False, export_lights=False, export_extras=True)
    print('GLB', GLB_OUT, os.path.getsize(GLB_OUT))
    if DO_RENDER:
        render_views(scene, col, body)
        bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)


main()
