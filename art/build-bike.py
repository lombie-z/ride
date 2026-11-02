"""Biotech motorcycle, the hero model of the ride scene.

Builds the bike from scratch, saves art/bike.blend and exports public/models/bike.glb (Draco).
Run:   blender --background --factory-startup --python art/build-bike.py
Review renders (hero, side, top) into art/renders/:
       blender --background --factory-startup --python art/build-bike.py -- --render [--tag NAME]

Blender is Z up, metres. Front wheel toward +X, ground at z=0, origin on the ground midway between
the contact points. Objects: Bike (body, leaning ~5 deg toward +Y onto its kickstand), WheelFront and
WheelRear (children of Bike, origin on the axle, spin about local Y).
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
BLEND_OUT = os.path.join(HERE, 'bike.blend')
GLB_OUT = os.path.join(ROOT, 'public', 'models', 'bike.glb')
RENDER_DIR = os.path.join(HERE, 'renders')

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
DO_RENDER = '--render' in ARGS
TAG = ARGS[ARGS.index('--tag') + 1] if '--tag' in ARGS else ''

TAU = math.tau
Y = Vector((0, 1, 0))

# ---------------------------------------------------------------- layout (bike local, metres)
WHEELBASE = 1.56
F_AXLE = Vector((WHEELBASE / 2, 0, 0.315))   # front axle, tyre radius 0.315 (120/70-17)
R_AXLE = Vector((-WHEELBASE / 2, 0, 0.325))  # rear axle, tyre radius 0.325 (200/55-17)
F_R, R_R = 0.315, 0.325
RAKE = math.radians(25)
STEER = Vector((-math.sin(RAKE), 0, math.cos(RAKE)))  # up along the steering axis
LEAN = math.radians(5)  # toward +Y (kickstand side)


# ---------------------------------------------------------------- scene / materials
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = 'METRIC'
    return s


def principled(name, base, metallic=0.0, rough=0.5, coat=0.0, coat_rough=0.03, emit=None, emit_strength=0.0, spec=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*base, 1)
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = spec
    b.inputs['Coat Weight'].default_value = coat
    b.inputs['Coat Roughness'].default_value = coat_rough
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1)
        b.inputs['Emission Strength'].default_value = emit_strength
    m.diffuse_color = (*base, 1)
    return m


def srgb(h):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return tuple(lin(int(h[i:i + 2], 16)) for i in (1, 3, 5))


def make_materials():
    return {
        'chitin': principled('BikeChitin', (0.008, 0.010, 0.009), metallic=0.25, rough=0.16, coat=1.0, coat_rough=0.02),
        'chrome': principled('BikeChrome', (0.78, 0.76, 0.70), metallic=1.0, rough=0.13),
        'glow': principled('BikeGlow', srgb('#3c8c1c'), rough=0.25, emit=srgb('#7dff4a'), emit_strength=1.8),
        'eye': principled('BikeEye', srgb('#4a5a10'), rough=0.1, emit=srgb('#dcff5a'), emit_strength=12.0),
        'tyre': principled('BikeTyre', (0.016, 0.016, 0.016), rough=0.62, spec=0.35),
        'bone': principled('BikeBone', (0.55, 0.52, 0.45), metallic=0.6, rough=0.34),
    }


# ---------------------------------------------------------------- curve maths
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


def section(w, ht, hb, n, e=2.5, eb=None, ridge=0.0, keel=0.0, a0=0.0, a1=TAU, closed=True):
    pts = []
    count = n if closed else n + 1
    for k in range(count):
        a = a0 + (a1 - a0) * k / n
        c, s = math.cos(a), math.sin(a)
        ee = e if s >= 0 else (eb or e)
        u = w * math.copysign(abs(c) ** (2 / ee), c)
        v = (ht if s >= 0 else hb) * math.copysign(abs(s) ** (2 / ee), s)
        if s > 0:
            v += ridge * s ** 16
        else:
            v -= keel * (-s) ** 16
        pts.append((u, v))
    return pts


# ---------------------------------------------------------------- mesh builders
PARTS = []


def new_obj(name, verts, faces, mat, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
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
    PARTS.append(ob)
    return ob


def rings_mesh(name, rings, mat, closed_ring=True, closed_along=False, cap0=None, cap1=None, smooth=True):
    m = len(rings[0])
    verts = [v for r in rings for v in r]
    faces = []
    nr = len(rings)
    for i in range(nr if closed_along else nr - 1):
        i2 = (i + 1) % nr
        for j in range(m if closed_ring else m - 1):
            j2 = (j + 1) % m
            faces.append((i * m + j, i * m + j2, i2 * m + j2, i2 * m + j))
    for cap, ri in ((cap0, 0), (cap1, nr - 1)):
        if cap is None:
            continue
        idx = list(range(ri * m, ri * m + m))
        if cap == 'ngon':
            faces.append(tuple(idx))
        else:  # a point: Vector tip
            verts.append(cap)
            c = len(verts) - 1
            for j in range(m):
                faces.append((idx[j], idx[(j + 1) % m], c))
    return new_obj(name, verts, faces, mat, smooth)


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
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)
    return ob


def tube(name, ctrl, radius, mat, sides=10, segs=None, cap0='ngon', cap1='ngon', squash=1.0):
    """Swept circle along a Catmull-Rom curve. radius: number, (r0, r1) or f(s)."""
    dense = catmull(ctrl, 16)
    length = sum((b - a).length for a, b in zip(dense, dense[1:]))
    segs = segs or max(6, int(length / 0.035))
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
        rings.append([p + (N * math.cos(a) * squash + B * math.sin(a)) * r for a in (TAU * k / sides for k in range(sides))])
    c0 = (path[0] - frames[0][0] * rf(0) * 0.5) if cap0 == 'point' else cap0
    c1 = (path[-1] + frames[-1][0] * rf(1) * 0.5) if cap1 == 'point' else cap1
    return rings_mesh(name, rings, mat, cap0=c0, cap1=c1)


def loft(name, keys, mat, n_along, n_around, side=Y, closed=True, cap0=None, cap1=None, solidify=0.0, subsurf=1):
    """Superellipse sections swept through keyed centres. Keys: c, w, ht, hb, e, eb, ridge, keel, a0, a1."""
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
        sd = up.cross(T).normalized()
        g = lambda f, dflt=0.0: hermite(keys, t, f, dflt)
        pts = section(max(g('w'), 1e-4), max(g('ht'), 1e-4), max(g('hb'), 1e-4), n_around, e=g('e', 2.5), eb=g('eb', g('e', 2.5)),
                      ridge=g('ridge'), keel=g('keel'), a0=g('a0', 0.0), a1=g('a1', TAU), closed=closed)
        rings.append([c + sd * u + up * v for u, v in pts])
        centres.append(c)
        tangents.append(T)
    c0 = cap0 if cap0 != 'point' else centres[0] - tangents[0] * 0.01
    c1 = cap1 if cap1 != 'point' else centres[-1] + tangents[-1] * 0.01
    ob = rings_mesh(name, rings, mat, closed_ring=closed, cap0=c0, cap1=c1)
    return bake(ob, solidify=solidify, subsurf=subsurf)


def lathe(name, prof, mat, segs, closed_prof=True, axis_y=0.0):
    rings = []
    for k in range(segs):
        ph = TAU * k / segs
        rings.append([Vector((r * math.cos(ph), y + axis_y, r * math.sin(ph))) for r, y in prof])
    # rings run around the axis; the profile is the 'ring' dimension here
    return rings_mesh(name, rings, mat, closed_ring=closed_prof, closed_along=True)


def mirror(ctrl):
    return [Vector((p[0], -p[1], p[2])) for p in ctrl]


def both_sides(fn, ctrl, *a, **kw):
    """Build a part on the right (-Y, the camera side) and its mirror on the left."""
    fn(*a[:0], ctrl=ctrl, **kw)
    fn(ctrl=mirror(ctrl), **kw)


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


def tri_count(ob):
    ob.data.calc_loop_triangles()
    return len(ob.data.loop_triangles)


# ---------------------------------------------------------------- wheel
def disc(name, r0, r1, y, mat, sectors=60, hole_rows=(1, 2)):
    radii = [r0, r0 + (r1 - r0) * 0.22, r0 + (r1 - r0) * 0.5, r0 + (r1 - r0) * 0.78, r1]
    verts, faces = [], []
    for r in radii:
        for j in range(sectors):
            ph = TAU * j / sectors
            verts.append(Vector((r * math.cos(ph), y, r * math.sin(ph))))
    for k in range(len(radii) - 1):
        for j in range(sectors):
            if (k == hole_rows[0] and j % 4 == 0) or (k == hole_rows[1] and j % 4 == 2):
                continue
            j2 = (j + 1) % sectors
            faces.append((k * sectors + j, k * sectors + j2, (k + 1) * sectors + j2, (k + 1) * sectors + j))
    ob = new_obj(name, verts, faces, mat, smooth=False)
    return bake(ob, solidify=0.006)


def build_wheel(name, radius, width, M, front):
    global PARTS
    saved, PARTS = PARTS, []
    rim_r = 0.216
    # tyre: fat superellipse section revolved about Y
    rm, hr, hw = (radius + rim_r - 0.012) / 2, (radius - rim_r + 0.012) / 2, width / 2
    prof = [(rm + v, u) for u, v in section(hw, hr, hr, 18, e=2.3 if front else 2.9)]
    lathe(name + 'Tyre', prof, M['tyre'], 48)
    # rim: dark channel with a chrome lip each side
    rw = hw * 0.82
    rim_prof = [(rim_r + 0.006, -rw), (rim_r - 0.012, -rw), (rim_r - 0.02, -rw * 0.6), (rim_r - 0.022, 0), (rim_r - 0.02, rw * 0.6),
                (rim_r - 0.012, rw), (rim_r + 0.006, rw), (rim_r - 0.004, rw * 0.7), (rim_r - 0.004, -rw * 0.7)]
    lathe(name + 'Rim', rim_prof, M['chitin'], 48)
    for sgn in (-1, 1):
        lip = [(rim_r + 0.004 + 0.005 * math.cos(a), sgn * rw + 0.005 * math.sin(a)) for a in (TAU * k / 5 for k in range(5))]
        lathe(name + 'Lip', lip, M['chrome'], 40)
    # hub
    hub = [(0.02, -0.075), (0.055, -0.07), (0.06, -0.03), (0.05, 0), (0.06, 0.03), (0.055, 0.07), (0.02, 0.075)]
    lathe(name + 'Hub', hub, M['chrome'], 20, closed_prof=False)
    # organic swept spokes, splitting in two near the rim
    n_sp = 5
    for k in range(n_sp):
        ph = TAU * k / n_sp
        for fork_off, ybase in ((-0.16, 1), (0.16, -1)):
            pts = []
            for r, d, yy in ((0.05, 0.0, 0.035), (0.10, 0.18, 0.025), (0.15, 0.34 + fork_off * 0.5, 0.012), (rim_r - 0.018, 0.40 + fork_off, 0.0)):
                a = ph + d
                pts.append(Vector((r * math.cos(a), yy * ybase, r * math.sin(a))))
            tube(name + 'Spoke', pts, (0.011, 0.007), M['chrome'], sides=6, segs=9)
    # brake discs (front: twin, rear: right side only)
    ys = (-0.085, 0.085) if front else (-0.095,)
    for y in ys:
        disc(name + 'Disc', 0.095 if front else 0.07, 0.155 if front else 0.115, y, M['bone'], sectors=32)
        for k in range(5):
            ph = TAU * k / 5 + 0.3
            tube(name + 'Carrier', [Vector((0.05 * math.cos(ph), y * 0.8, 0.05 * math.sin(ph))), Vector((0.1 * math.cos(ph + 0.15), y, 0.1 * math.sin(ph + 0.15)))],
                 0.008, M['chitin'], sides=6, segs=3)
    if not front:  # sprocket on the left
        sp = [(0.09 + (0.012 if k % 2 else 0), 0.08) for k in range(2)]
        disc(name + 'Sprocket', 0.06, 0.11, 0.075, M['chitin'], sectors=40, hole_rows=(1, 2))
    wheel = join(name, PARTS)
    PARTS = saved
    return wheel


# ---------------------------------------------------------------- body
def steer_pt(t, y=0.0):
    p = F_AXLE + STEER * t
    return Vector((p.x, y, p.z))


def build_body(M):
    ch, cr, gl, bo = M['chitin'], M['chrome'], M['glow'], M['bone']

    # --- head fairing: big swept insect head, eye at the nose
    head = [
        dict(c=Vector((0.08, 0, 0.86)), w=0.17, ht=0.09, hb=0.10, ridge=0.0, e=2.15),
        dict(c=Vector((0.30, 0, 0.885)), w=0.245, ht=0.155, hb=0.20, ridge=0.025, e=2.2),
        dict(c=Vector((0.54, 0, 0.875)), w=0.255, ht=0.185, hb=0.21, ridge=0.04, e=2.25),
        dict(c=Vector((0.76, 0, 0.85)), w=0.215, ht=0.15, hb=0.155, ridge=0.035, e=2.2),
        dict(c=Vector((0.93, 0, 0.81)), w=0.15, ht=0.105, hb=0.12, ridge=0.02, e=2.1),
        dict(c=Vector((1.02, 0, 0.785)), w=0.10, ht=0.08, hb=0.085, ridge=0.0, e=2.15),
    ]
    loft('Head', head, ch, 20, 18, cap0='ngon', cap1='ngon', subsurf=1)
    # brow: a proud plate over the top of the head that overhangs the eye
    brow = [
        dict(c=Vector((0.50, 0, 0.885)), w=0.24, ht=0.19, hb=0.05),
        dict(c=Vector((0.76, 0, 0.865)), w=0.225, ht=0.165, hb=0.05, ridge=0.04),
        dict(c=Vector((0.96, 0, 0.83)), w=0.15, ht=0.12, hb=0.04, ridge=0.02),
        dict(c=Vector((1.09, 0, 0.82)), w=0.06, ht=0.07, hb=0.02),
    ]
    for k in brow:
        k.update(a0=0.12, a1=math.pi - 0.12)
    loft('Brow', brow, ch, 12, 12, closed=False, solidify=0.014, subsurf=1)
    # mandibles: chitin tusks curling from under the eye back over the fender
    for sgn in (-1, 1):
        tube('Mandible', [(1.00, sgn * 0.07, 0.72), (0.92, sgn * 0.17, 0.675), (0.78, sgn * 0.225, 0.68), (0.62, sgn * 0.24, 0.73)],
             lambda s: 0.012 + 0.02 * math.sin(math.pi * min(1, s * 1.3)) ** 0.7, ch, sides=10, segs=18, cap0='point', cap1='point', squash=0.6)
    eye_c = Vector((1.03, 0, 0.785))
    # eye: a deep bulging lens so it still reads round from the side, chrome bezel
    lens = [(0.085 * math.cos(a), 0.065 * math.sin(a)) for a in (math.pi / 2 * k / 8 for k in range(9))]
    eye = lathe('Eye', lens, M['eye'], 32, closed_prof=False)
    eye.data.transform(Matrix.Rotation(-math.pi / 2, 4, 'Z'))
    eye.data.transform(Matrix.Translation(eye_c))
    bez = [(0.092 + 0.018 * math.cos(a), 0.016 * math.sin(a)) for a in (TAU * k / 8 for k in range(8))]
    bezel = lathe('Bezel', bez, cr, 40)
    bezel.data.transform(Matrix.Rotation(-math.pi / 2, 4, 'Z'))
    bezel.data.transform(Matrix.Translation(eye_c))

    # --- carapace over the tank: overlapping arched plates, like an insect's abdomen; ribs show beneath
    guide = [dict(t=0.0, x=0.46, zc=0.86, w=0.24, ht=0.19), dict(t=0.35, x=0.20, zc=0.86, w=0.24, ht=0.185),
             dict(t=0.7, x=-0.05, zc=0.81, w=0.21, ht=0.15), dict(t=1.0, x=-0.27, zc=0.74, w=0.165, ht=0.085)]
    n_pl = 4
    edge = (0.62, 0.30, 0.34, 0.55)  # how far each plate wraps down the sides: a curved window onto the ribs
    for i in range(n_pl):
        t0, t1 = i / n_pl - 0.03, (i + 1) / n_pl + 0.02
        keys = []
        for j, f in enumerate((0.0, 0.5, 1.0)):
            t = t0 + (t1 - t0) * f
            sc = 0.95 + 0.07 * f
            g = lambda fld: hermite(guide, min(max(t, 0), 1), fld)
            keys.append(dict(c=Vector((g('x') + (0.02 if t < 0 else 0), 0, g('zc') - 0.01 * f)), w=g('w') * sc, ht=g('ht') * sc, hb=0.07,
                             ridge=0.02, a0=-edge[i] - 0.06 * f, a1=math.pi + edge[i] + 0.06 * f))
        loft('Tank', keys, ch, 5, 11, closed=False, solidify=0.012, subsurf=1)

    # --- seat and tail cone
    seat = [
        dict(c=Vector((-0.10, 0, 0.75)), w=0.12, ht=0.04, hb=0.04, e=3),
        dict(c=Vector((-0.30, 0, 0.765)), w=0.155, ht=0.05, hb=0.05, e=3),
        dict(c=Vector((-0.48, 0, 0.79)), w=0.12, ht=0.05, hb=0.05, e=3),
    ]
    loft('Seat', seat, ch, 10, 16, cap0='ngon', cap1='ngon', subsurf=1)
    tail = [
        dict(c=Vector((-0.28, 0, 0.70)), w=0.18, ht=0.07, hb=0.11, ridge=0.0),
        dict(c=Vector((-0.55, 0, 0.77)), w=0.165, ht=0.09, hb=0.15, ridge=0.03),
        dict(c=Vector((-0.80, 0, 0.87)), w=0.095, ht=0.07, hb=0.11, ridge=0.025),
        dict(c=Vector((-0.97, 0, 0.98)), w=0.02, ht=0.02, hb=0.02),
    ]
    loft('Tail', tail, ch, 16, 14, cap0='ngon', cap1='point', subsurf=1)
    tube('TailTip', [(-0.93, 0, 0.955), (-1.0, 0, 0.995), (-1.05, 0, 1.03)], lambda s: 0.02 * (1 - s) + 0.002, cr, sides=8, segs=6, cap1='point')

    # --- fenders: open shells hugging the tyres
    def fender(name, axle, rad, th0, th1, w, wt0, wt1):
        keys = []
        for i in range(6):
            f = i / 5
            th = th0 + (th1 - th0) * f
            c = axle + Vector((math.cos(th), 0, math.sin(th))) * rad
            ww = w * min(1, 0.35 + 2.2 * min(f, 1 - f)) if True else w
            ww = w * (wt0 + (1 - wt0) * min(1, f * 3)) * (wt1 + (1 - wt1) * min(1, (1 - f) * 3))
            keys.append(dict(c=c, w=ww, ht=0.02, hb=0.05, a0=math.pi - 0.25, a1=TAU + 0.25))
        loft(name, keys, ch, 14, 10, closed=False, solidify=0.01, subsurf=1)
    fender('FenderF', F_AXLE, F_R + 0.04, math.radians(-28), math.radians(130), 0.13, 0.3, 0.6)
    fender('FenderR', R_AXLE, R_R + 0.045, math.radians(30), math.radians(185), 0.165, 0.7, 0.35)

    # --- belly / engine mass
    belly = [
        dict(c=Vector((0.36, 0, 0.36)), w=0.10, ht=0.10, hb=0.10),
        dict(c=Vector((0.12, 0, 0.32)), w=0.15, ht=0.15, hb=0.15, keel=0.02),
        dict(c=Vector((-0.18, 0, 0.36)), w=0.15, ht=0.15, hb=0.14),
        dict(c=Vector((-0.40, 0, 0.48)), w=0.09, ht=0.10, hb=0.08),
    ]
    loft('Belly', belly, ch, 14, 16, cap0='ngon', cap1='ngon', subsurf=1)

    # --- neck plates (side "cheeks" running from the head down to the belly)
    for sgn in (-1, 1):
        chest = [
            dict(c=Vector((0.52, sgn * 0.16, 0.76)), w=0.035, ht=0.10, hb=0.10),
            dict(c=Vector((0.46, sgn * 0.195, 0.56)), w=0.045, ht=0.10, hb=0.09),
            dict(c=Vector((0.36, sgn * 0.19, 0.37)), w=0.04, ht=0.08, hb=0.07),
            dict(c=Vector((0.22, sgn * 0.15, 0.24)), w=0.03, ht=0.05, hb=0.05),
        ]
        loft('Chest', chest, ch, 12, 12, cap0='ngon', cap1='ngon', subsurf=1)

    # --- ribcage: spine + glowing ribs + dark core. Ribs bow forward and sweep back at the bottom, front ribs biggest.
    spine0, spine1 = Vector((0.36, 0, 0.86)), Vector((-0.30, 0, 0.71))
    n_ribs = 14
    core = [dict(c=spine0.lerp(spine1, f) - Vector((0, 0, 0.19 - 0.04 * f)), w=0.10 + 0.02 * math.sin(math.pi * f),
                 ht=0.14, hb=0.10) for f in (0, 0.33, 0.66, 1)]
    loft('Core', core, ch, 10, 12, cap0='ngon', cap1='ngon', subsurf=1)
    for i in range(n_ribs):
        f = i / (n_ribs - 1)
        p = spine0.lerp(spine1, f)
        jit = math.sin(i * 12.9898) * 0.5  # deterministic per-rib variation so the cage doesn't read as a comb
        w = 0.20 - 0.05 * f ** 1.5 + 0.008 * jit
        h = 0.38 - 0.13 * f + 0.02 * jit
        p = p + Vector((0.006 * jit, 0, 0))
        bow, sweep = 0.06, -0.08
        for sgn in (-1, 1):
            pts = [p + Vector((0, sgn * 0.03, -0.01)),
                   p + Vector((bow * 0.5, sgn * w * 0.8, -h * 0.12)),
                   p + Vector((bow, sgn * w, -h * 0.42)),
                   p + Vector((bow * 0.3, sgn * w * 0.9, -h * 0.75)),
                   p + Vector((sweep, sgn * w * 0.5, -h))]
            tube('Rib', pts, lambda s: 0.02 * (1 - 0.4 * s), gl, sides=7, segs=14, cap1='point', squash=0.7)
    vert = lambda s: 0.022 + 0.01 * abs(math.sin(math.pi * 14 * s))
    tube('Spine', [spine0 + Vector((0.08, 0, 0.03)), spine0.lerp(spine1, 0.5) + Vector((0, 0, 0.01)), spine1 + Vector((-0.1, 0, 0.0))], vert, bo, sides=10, segs=50)

    # --- front end: forks, clamps, bars, caliper
    for sgn in (-1, 1):
        y = sgn * 0.115
        tube('ForkLower', [steer_pt(-0.02, y), steer_pt(0.36, y)], 0.026, cr, sides=16, segs=6)
        tube('ForkUpper', [steer_pt(0.32, y), steer_pt(0.74, y)], 0.031, cr, sides=16, segs=6)
        tube('AxleClamp', [steer_pt(-0.03, y) + Vector((0.015, 0, -0.02)), steer_pt(0.08, y)], 0.034, ch, sides=12, segs=4)
        cal = steer_pt(0.0, sgn * 0.085) + Vector((-0.07, 0, 0.11))
        tube('Caliper', [cal + Vector((0.04, 0, 0.03)), cal + Vector((-0.04, 0, -0.02))], 0.024, ch, sides=10, segs=4, squash=0.6)
        bar = [steer_pt(0.70, sgn * 0.07), steer_pt(0.72, sgn * 0.17) + Vector((-0.02, 0, 0.09)), steer_pt(0.70, sgn * 0.33) + Vector((-0.10, 0, 0.13))]
        tube('Bar', bar, 0.012, cr, sides=8, segs=12)
        tube('Grip', [steer_pt(0.70, sgn * 0.27) + Vector((-0.075, 0, 0.12)), steer_pt(0.70, sgn * 0.38) + Vector((-0.12, 0, 0.135))], 0.018, M['tyre'], sides=10, segs=4)
    tube('Clamp', [steer_pt(0.72, -0.14), steer_pt(0.72, 0.14)], 0.02, ch, sides=10, segs=6, squash=0.6)
    tube('Axle', [F_AXLE + Vector((0, -0.14, 0)), F_AXLE + Vector((0, 0.14, 0))], 0.012, cr, sides=8, segs=2)

    # --- rear: bone swingarm, shock, axle
    for sgn in (-1, 1):
        tube('Swingarm', [Vector((-0.18, sgn * 0.10, 0.37)), Vector((-0.48, sgn * 0.13, 0.36)), R_AXLE + Vector((0, sgn * 0.13, 0))],
             lambda s: 0.036 - 0.014 * s + 0.004 * math.sin(s * 9), bo, sides=12, segs=24)
    tube('Shock', [Vector((-0.28, 0, 0.62)), Vector((-0.42, 0, 0.42))], 0.022, cr, sides=10, segs=4)
    tube('AxleR', [R_AXLE + Vector((0, -0.15, 0)), R_AXLE + Vector((0, 0.15, 0))], 0.013, cr, sides=8, segs=2)

    # --- chrome tendons from under the head, sweeping back along the belly
    tendons = [
        ([(0.56, -0.12, 0.74), (0.52, -0.205, 0.56), (0.43, -0.235, 0.36), (0.27, -0.225, 0.19), (-0.05, -0.20, 0.14), (-0.38, -0.185, 0.21), (-0.60, -0.16, 0.32)], 0.026),
        ([(0.50, -0.15, 0.78), (0.45, -0.235, 0.60), (0.36, -0.255, 0.42), (0.21, -0.25, 0.27), (-0.05, -0.24, 0.25), (-0.30, -0.235, 0.30)], 0.022),
        ([(0.60, -0.08, 0.72), (0.57, -0.16, 0.50), (0.48, -0.19, 0.28), (0.32, -0.18, 0.14), (0.02, -0.16, 0.115), (-0.25, -0.15, 0.17)], 0.022),
        ([(0.44, -0.19, 0.74), (0.39, -0.25, 0.58), (0.30, -0.265, 0.45), (0.12, -0.26, 0.37), (-0.12, -0.25, 0.38)], 0.017),
    ]
    for ctrl, r in tendons:
        for c in (ctrl, mirror(ctrl)):
            tube('Tendon', c, lambda s, r=r: r * (1.1 - 0.35 * s), cr, sides=8)

    # --- segmented exhaust pipes, abdomen-like, ending past the rear wheel
    def exhaust_r(s, r0, r1):
        r = r0 + (r1 - r0) * s
        if s > 0.4:
            k = (s - 0.4) / 0.6
            r += 0.006 * (0.4 + k) * abs(math.sin(math.pi * 11 * k)) ** 0.6
        if s > 0.94:
            r *= 1 + 6 * (s - 0.94)
        return r
    pipes = [
        ([(0.30, -0.12, 0.30), (0.14, -0.20, 0.18), (-0.22, -0.225, 0.19), (-0.55, -0.235, 0.31), (-0.82, -0.225, 0.47), (-1.02, -0.20, 0.58)], 0.032, 0.044),
        ([(0.33, -0.13, 0.44), (0.18, -0.215, 0.32), (-0.18, -0.26, 0.31), (-0.50, -0.265, 0.42), (-0.76, -0.245, 0.55), (-0.94, -0.21, 0.66)], 0.028, 0.038),
    ]
    for ctrl, r0, r1 in pipes:
        for c in (ctrl, mirror(ctrl)):
            tube('Exhaust', c, lambda s, r0=r0, r1=r1: exhaust_r(s, r0, r1), cr, sides=10, segs=76, cap1='ngon')

    # --- glow accent lines along the carapace edge and head cheek
    for sgn in (-1, 1):
        tube('Accent', [(0.62, sgn * 0.215, 0.80), (0.40, sgn * 0.205, 0.82), (0.16, sgn * 0.205, 0.80), (-0.06, sgn * 0.18, 0.76)], 0.0045, gl, sides=6)

    # --- kickstand on the left (+Y); the foot touches the ground once the bike leans
    foot_y = 0.30
    foot_z = (0.015 + math.sin(LEAN) * foot_y) / math.cos(LEAN)
    tube('Stand', [Vector((-0.04, 0.13, 0.30)), Vector((-0.12, 0.22, 0.16)), Vector((-0.20, foot_y, foot_z))], (0.016, 0.011), cr, sides=8, segs=10)
    tube('StandFoot', [Vector((-0.23, foot_y, foot_z)), Vector((-0.17, foot_y, foot_z))], 0.015, cr, sides=8, segs=2, squash=0.6)

    # --- drips of black ooze hanging off low edges
    drips = [(0.62, -0.17, 0.72, 0.06), (0.74, -0.12, 0.71, 0.04), (0.50, -0.19, 0.74, 0.05), (0.15, -0.12, 0.18, 0.07),
             (-0.10, -0.13, 0.22, 0.05), (0.30, -0.10, 0.25, 0.06), (-0.45, -0.10, 0.62, 0.05), (-0.70, -0.06, 0.74, 0.06),
             (0.62, 0.17, 0.72, 0.05), (0.15, 0.12, 0.18, 0.06), (-0.70, 0.06, 0.74, 0.04)]
    for x, y, z, l in drips:
        tube('Drip', [Vector((x, y, z + 0.01)), Vector((x - 0.004, y, z - l * 0.75)), Vector((x - 0.006, y, z - l * 1.5))],
             lambda s: 0.011 * (1 - s) + 0.004 + 0.007 * math.exp(-((s - 0.86) / 0.09) ** 2), ch, sides=6, segs=8, cap1='point')


# ---------------------------------------------------------------- render setup (review only, not exported)
def setup_render(scene):
    # Cycles: it reflects the hidden 'city' emitters and lets the ribs light their surroundings
    scene.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    try:
        prefs.compute_device_type = 'METAL'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        scene.cycles.device = 'GPU'
    except Exception as e:  # CPU fallback
        print('GPU unavailable', e)
    scene.cycles.samples = 96
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 8
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    world = bpy.data.worlds.new('RenderWorld')
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes['Background']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    remap = nt.nodes.new('ShaderNodeMapRange')  # direction z in [-1, 1] -> [0, 1]
    remap.inputs['From Min'].default_value = -1.0
    nt.links.new(sep.outputs['Z'], remap.inputs['Value'])
    nt.links.new(remap.outputs['Result'], ramp.inputs['Fac'])
    cr_ = ramp.color_ramp
    cr_.elements[0].position, cr_.elements[0].color = 0.0, (0.004, 0.006, 0.005, 1)
    cr_.elements[1].position, cr_.elements[1].color = 1.0, (0.012, 0.018, 0.015, 1)
    for pos, c in ((0.47, (0.006, 0.009, 0.007, 1)), (0.505, (0.07, 0.10, 0.075, 1)), (0.56, (0.03, 0.045, 0.035, 1)), (0.7, (0.02, 0.03, 0.025, 1))):
        e = cr_.elements.new(pos)
        e.color = c
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.0

    col = bpy.data.collections.new('Render')
    scene.collection.children.link(col)

    def light(name, kind, loc, target, color, power, size=1.0):
        ld = bpy.data.lights.new(name, kind)
        ld.color = color
        ld.energy = power
        if kind == 'AREA':
            ld.size = size
        else:
            ld.shadow_soft_size = size
        if kind == 'SPOT':
            ld.spot_size = math.radians(42)
            ld.spot_blend = 0.6
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        col.objects.link(ob)
        return ob

    light('Key', 'SPOT', (3.0, -3.2, 3.4), (0.2, 0, 0.6), (0.72, 0.84, 1.0), 2200, 0.25)
    light('Rim', 'SPOT', (1.6, 3.4, 2.3), (0.1, 0, 0.95), (0.45, 1.0, 0.3), 3500, 0.2)
    light('RimBack', 'SPOT', (-3.2, 2.4, 2.2), (-0.4, 0, 0.9), (0.4, 1.0, 0.3), 2200, 0.2).visible_glossy = False  # it shows as a hot spot in the wet ground
    for ob in (light('Fill', 'SPOT', (0.6, -4.5, 1.0), (0.2, 0, 0.5), (0.6, 0.8, 0.7), 250, 0.3),
               light('RibGlow', 'POINT', (0.05, -0.26, 0.62), (0, 0, 0), (0.45, 1.0, 0.25), 4, 0.1)):
        ob.data.specular_factor = 0.0  # no hot spots in the wet ground
        ob.visible_glossy = False
    # long emissive strips, invisible to the camera, for streaky reflections on the gloss
    for i, (loc, sc, col_) in enumerate((((0.0, 2.5, 2.6), (4.0, 0.08), (0.5, 1.0, 0.4)), ((0.4, -2.8, 2.4), (3.5, 0.06), (0.8, 0.9, 1.0)),
                                          )):
        me = bpy.data.meshes.new('Strip')
        me.from_pydata([(-sc[0] / 2, -sc[1], 0), (sc[0] / 2, -sc[1], 0), (sc[0] / 2, sc[1], 0), (-sc[0] / 2, sc[1], 0)], [], [(0, 1, 2, 3)])
        st = bpy.data.objects.new('Strip', me)
        st.location = loc
        st.rotation_euler = (Vector((0, 0, 0.7)) - Vector(loc)).to_track_quat('Z', 'X').to_euler()
        st.visible_camera = False
        sm = bpy.data.materials.new('StripLight')
        sm.use_nodes = True
        sm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0, 0, 0, 1)
        sm.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (*col_, 1)
        sm.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 25
        me.materials.append(sm)
        col.objects.link(st)

    # a big dim 'city' panel behind the camera (invisible to it) so the chrome on the camera side has lights to reflect
    me = bpy.data.meshes.new('City')
    me.from_pydata([(-7, 0, 0), (7, 0, 0), (7, 0, 4), (-7, 0, 4)], [], [(0, 1, 2, 3)])
    city = bpy.data.objects.new('City', me)
    city.location = (1.5, -7.5, -0.5)
    city.rotation_euler = (0, 0, math.radians(-12))
    city.visible_camera = False
    cm = bpy.data.materials.new('CityLights')
    cm.use_nodes = True
    cnt = cm.node_tree
    cb = cnt.nodes['Principled BSDF']
    cb.inputs['Base Color'].default_value = (0, 0, 0, 1)
    cb.inputs['Emission Color'].default_value = (0.55, 0.85, 0.5, 1)
    vor = cnt.nodes.new('ShaderNodeTexNoise')
    vor.inputs['Scale'].default_value = 6.0
    mr = cnt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = 0.45
    mr.inputs['From Max'].default_value = 0.7
    mr.inputs['To Min'].default_value = 0.3
    mr.inputs['To Max'].default_value = 4.0
    cnt.links.new(vor.outputs['Fac'], mr.inputs['Value'])
    cnt.links.new(mr.outputs['Result'], cb.inputs['Emission Strength'])
    me.materials.append(cm)
    col.objects.link(city)

    # wet ground: dark, glossy, with a little roughness noise for puddles
    me = bpy.data.meshes.new('Ground')
    s = 12
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new('Ground', me)
    col.objects.link(g)
    gm = bpy.data.materials.new('WetGround')
    gm.use_nodes = True
    nt = gm.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.012, 0.014, 0.013, 1)
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 1.6
    ramp = nt.nodes.new('ShaderNodeMapRange')
    ramp.inputs['From Min'].default_value = 0.45
    ramp.inputs['From Max'].default_value = 0.6
    ramp.inputs['To Min'].default_value = 0.04
    ramp.inputs['To Max'].default_value = 0.35
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Value'])
    nt.links.new(ramp.outputs['Result'], b.inputs['Roughness'])
    me.materials.append(gm)

    # bloom
    ng = bpy.data.node_groups.new('Bloom', 'CompositorNodeTree')
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = ng.nodes.new('CompositorNodeRLayers')
    glare = ng.nodes.new('CompositorNodeGlare')
    glare.inputs['Type'].default_value = 'Bloom'
    glare.inputs['Threshold'].default_value = 1.2
    glare.inputs['Strength'].default_value = 0.35
    glare.inputs['Size'].default_value = 0.5
    out = ng.nodes.new('NodeGroupOutput')
    ng.links.new(rl.outputs['Image'], glare.inputs['Image'])
    ng.links.new(glare.outputs['Image'], out.inputs[0])
    scene.compositing_node_group = ng
    scene.render.use_compositing = True
    return col


def add_camera(col, name, loc, target=None, lens=28, ortho=None, rot=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    cd.clip_end = 100
    ob = bpy.data.objects.new(name, cd)
    ob.location = loc
    if rot is not None:
        ob.rotation_euler = rot
    else:
        ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    col.objects.link(ob)
    return ob


def render_views(scene, col):
    os.makedirs(RENDER_DIR, exist_ok=True)
    cams = {
        'hero': add_camera(col, 'CamHero', (2.0, -4.2, 0.55), (0.3, 0, 0.7), lens=28),
        'side': add_camera(col, 'CamSide', (0, -8, 0.62), rot=(math.pi / 2, 0, 0), ortho=2.9),
        'top': add_camera(col, 'CamTop', (0, 0, 8), rot=(0, 0, 0), ortho=2.9),
        'front': add_camera(col, 'CamFront34', (3.4, -1.9, 1.0), (0.1, 0, 0.6), lens=40),
    }
    suffix = f'-{TAG}' if TAG else ''
    for key, cam in cams.items():
        scene.camera = cam
        scene.render.filepath = os.path.join(RENDER_DIR, f'bike-{key}{suffix}.png')
        bpy.ops.render.render(write_still=True)
        print('rendered', scene.render.filepath)
    scene.camera = cams['hero']


# ---------------------------------------------------------------- main
def main():
    scene = reset()
    M = make_materials()

    build_body(M)
    per = {}
    for o in PARTS:
        per[o.name.split('.')[0]] = per.get(o.name.split('.')[0], 0) + tri_count(o)
    print('PARTS', sorted(per.items(), key=lambda kv: -kv[1]))
    body = join('Bike', PARTS)
    PARTS.clear()

    wf = build_wheel('WheelFront', F_R, 0.17, M, front=True)
    wr = build_wheel('WheelRear', R_R, 0.235, M, front=False)
    for w, axle in ((wf, F_AXLE), (wr, R_AXLE)):
        w.parent = body
        w.matrix_parent_inverse = Matrix.Identity(4)
        w.location = axle

    body.location = (0, 0, 0)
    body.rotation_euler = (-LEAN, 0, 0)  # lean toward +Y onto the kickstand

    counts = {o.name: tri_count(o) for o in (body, wf, wr)}
    print('TRIANGLES', counts, 'total', sum(counts.values()))

    col = setup_render(scene)
    scene.camera = None
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)

    bpy.ops.object.select_all(action='DESELECT')
    for o in (body, wf, wr):
        o.select_set(True)
    os.makedirs(os.path.dirname(GLB_OUT), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=GLB_OUT, export_format='GLB', use_selection=True, export_apply=True, export_yup=True,
                              export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
                              export_cameras=False, export_lights=False)
    print('GLB', GLB_OUT, os.path.getsize(GLB_OUT))

    if DO_RENDER:
        render_views(scene, col)
        bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)


main()
