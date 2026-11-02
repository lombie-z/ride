"""Liquid-chrome bike, the second hero bike (art/reference/concept-chrome-city.webp, rider view concept-transition.webp).

Builds the bike from scratch, saves art/bike2.blend and exports public/models/bike2.glb (Draco).
Run:   blender --background --factory-startup --python art/build-bike2.py
Review renders into art/renders/bike2-*.png (concept, rider, side, hero):
       blender --background --factory-startup --python art/build-bike2.py -- --render [--tag NAME] [--views concept,side]

Same frame as bike.glb (art/build-bike.py) so the site can swap them in place: metres, Z up, front toward +X, ground
z=0, origin on the ground midway between the contacts, wheelbase 1.56 m, the same axles, the root rolled 5 deg toward
+Y onto the kickstand. Objects: Bike2 (body), Wheel2Front / Wheel2Rear (children, origin on the axle, spin about local
Y), Bike2Button + Bike2ButtonGlyph (the throttle pill on the tank), Bike2Dash (curved glass display, UV 0-1, u right and
v up from the rider's seat), and the ButtonCentre / RiderEye empties at bike.glb's exact bike-local transforms.

Materials (plain Principled BSDFs, the site tunes them). Alpha-blended (set depthWrite on the site): Bike2Glass,
Bike2Smoke. Emissive: Bike2Vein, Bike2Led, Bike2Tail, Bike2Dash, Bike2Button, Bike2ButtonGlyph.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
BLEND_OUT = os.path.join(HERE, 'bike2.blend')
GLB_OUT = os.path.join(ROOT, 'public', 'models', 'bike2.glb')
RENDER_DIR = os.path.join(HERE, 'renders')
ALIGN = os.path.join(HERE, 'align-bike2')

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
F_W, R_W = 0.22, 0.30  # tyre widths (art/align-bike2/fit_camera.py uses the same)
LEAN = math.radians(5)  # toward +Y (kickstand side)

# bike.glb's anchors, bike-local (read from art/bike.blend by art/align-bike2/dump_anchors.py -> bike1-anchors.json)
BUTTON_CENTRE = Matrix(((0.9996989965438843, -9.723816261734963e-14, -0.02453269064426422, 0.4049460291862488),
                        (-9.327195584774017e-07, 1.0, -3.8020312786102295e-05, -8.195638656616211e-08),
                        (0.02453269250690937, 3.802776336669922e-05, 0.999699056148529, 0.9743461012840271),
                        (0.0, 0.0, 0.0, 1.0)))
RIDER_EYE = Matrix(((-1.6292067073209182e-07, 0.9902679920196533, 0.13917315006256104, 0.07999999821186066),
                    (-1.0, -1.6205012798309326e-07, -2.2351741790771484e-08, 0.0),
                    (-7.450580596923828e-09, -0.13917316496372223, 0.9902679920196533, 1.5200001001358032),
                    (0.0, 0.0, 0.0, 1.0)))
BUTTON_X, BUTTON_LEN, BUTTON_WID = 0.405, 0.24, 0.11


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
               alpha=1.0, transmission=0.0, sheen=0.0, sheen_tint=(1, 1, 1)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*base, 1)
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = spec
    b.inputs['Coat Weight'].default_value = coat
    b.inputs['Coat Roughness'].default_value = coat_rough
    b.inputs['Transmission Weight'].default_value = transmission
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
    M = {
        'chrome': principled('Bike2Chrome', (0.96, 0.96, 0.98), metallic=1.0, rough=0.05),
        'black': principled('Bike2Black', (0.008, 0.008, 0.010), rough=0.12, coat=1.0, coat_rough=0.03),
        # clear glass for the wheel hubs: alpha-blended, a hint of cool tint
        'glass': principled('Bike2Glass', (0.85, 0.88, 1.0), rough=0.02, coat=1.0, coat_rough=0.01, alpha=0.25),
        # smoked canopy: dark tinted glass
        'smoke': principled('Bike2Smoke', (0.018, 0.016, 0.026), rough=0.03, coat=1.0, coat_rough=0.01, alpha=0.55),
        'heart': principled('Bike2Heart', srgb('#3b0f22'), rough=0.3, coat=0.6, coat_rough=0.12, sheen=0.5, sheen_tint=srgb('#d9a0c8')),
        'vein': principled('Bike2Vein', srgb('#a46bff'), rough=0.3, emit=srgb('#a46bff'), emit_strength=6.0),
        'led': principled('Bike2Led', (0.9, 0.92, 1.0), rough=0.2, emit=(1.0, 1.0, 1.0), emit_strength=25.0),
        'tail': principled('Bike2Tail', srgb('#8a0a10'), rough=0.2, emit=srgb('#ff1a24'), emit_strength=12.0),
        'tyre': principled('Bike2Tyre', (0.018, 0.018, 0.02), rough=0.62, spec=0.35),
        'seat': principled('Bike2Seat', (0.014, 0.012, 0.012), rough=0.42, coat=0.25, coat_rough=0.3, sheen=0.3),
        # the throttle pill: violet-white glass glow; the glyph brighter. The site drives both intensities.
        'button': principled('Bike2Button', srgb('#c9b0ff'), rough=0.06, coat=1.0, coat_rough=0.02, emit=srgb('#d8c4ff'), emit_strength=1.0),
        'glyph': principled('Bike2ButtonGlyph', srgb('#f3ecff'), rough=0.3, emit=srgb('#f6f0ff'), emit_strength=4.0),
        # the dash: dark glass that glows; the site draws the speed and logo into it
        'dash': principled('Bike2Dash', (0.02, 0.016, 0.04), rough=0.05, coat=1.0, coat_rough=0.01, emit=srgb('#5a3a9a'), emit_strength=1.0),
    }
    return M


# ---------------------------------------------------------------- curve maths (as art/build-bike.py)
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
    from mathutils import Euler
    me.transform(Matrix.Translation(Vector(c)) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Diagonal((*radii, 1)))
    me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    if track:
        PARTS.append(ob)
    return ob


def mirror(ctrl):
    return [Vector((p[0], -p[1], p[2])) for p in ctrl]


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


def fuse(name, parts, voxel, smooth_iter=12, smooth_lambda=0.8, target_tris=None, mat=None):
    """Weld overlapping closed parts into one seamless skin: voxel remesh, Laplacian smoothing (rounds the joins into
    fillets, like poured metal), then decimate to a triangle budget."""
    ob = join(name, parts)
    for p in parts:
        if p in PARTS and p is not ob:
            PARTS.remove(p)
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
    apply_mods(ob)
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


# ---------------------------------------------------------------- wheel
def build_wheel(name, radius, width, M, front):
    global PARTS
    saved, PARTS = PARTS, []
    hw = width / 2
    rim_r = radius - (0.068 if front else 0.072)
    # fat low-profile tyre: squarish superellipse section revolved about Y, the tread a touch rounder
    rm, hr = (radius + rim_r) / 2, (radius - rim_r) / 2 + 0.004
    prof = [(rm + v, u) for u, v in section(hw, hr, hr, 28, e=3.2, eb=2.6)]
    lathe(name + 'Tyre', prof, M['tyre'], 72)
    # chrome rim lips each side, a rolled bead the glass seats into
    yl = hw * 0.86
    for sgn in (-1, 1):
        lip = [(rim_r + 0.006 + 0.011 * math.cos(a), sgn * yl + 0.009 * math.sin(a)) for a in (TAU * k / 10 for k in range(10))]
        lathe(name + 'Lip', lip, M['chrome'], 72)
    # clear glass discs: shallow domes bulging out past the sidewalls, both sides
    bulge = 0.062
    for sgn in (-1, 1):
        dome = []
        for k in range(15):
            th = (math.pi / 2) * (1 - k / 14)  # edge -> apex
            dome.append((rim_r * math.sin(th) + 1e-4, sgn * (yl + bulge * math.cos(th) ** 0.9)))
        ob = lathe(name + 'Glass', dome, M['glass'], 64, closed_prof=False)
        if sgn < 0:
            ob.data.flip_normals()
    # inside the glass: a chrome hub and a swept turbine of blades, violet light threading them
    tube(name + 'Hub', [Vector((0, -yl * 0.9, 0)), Vector((0, yl * 0.9, 0))], 0.045, M['chrome'], sides=24, segs=4)
    for sgn in (-1, 1):
        cap = [(0.0, sgn * (yl + bulge + 0.012)), (0.03, sgn * (yl + bulge + 0.006)), (0.036, sgn * (yl + bulge - 0.004)),
               (0.03, sgn * (yl + bulge - 0.012)), (0.0, sgn * (yl + bulge - 0.012))]
        lathe(name + 'Cap', cap, M['chrome'], 24, closed_prof=False)
        tube(name + 'Axle', [Vector((0, sgn * yl * 0.8, 0)), Vector((0, sgn * (yl + bulge - 0.006), 0))], 0.012, M['chrome'], sides=10, segs=2)
    n_bl = 7
    for k in range(n_bl):
        ph0 = TAU * k / n_bl
        verts, faces = [], []
        ns, nv = 14, 6
        for i in range(ns + 1):
            s = i / ns
            r = 0.045 + (rim_r - 0.055) * s
            ph = ph0 + 0.9 * s ** 1.3
            for j in range(nv + 1):
                v = -1 + 2 * j / nv
                half = yl * (0.82 - 0.35 * s)
                verts.append(Vector((r * math.cos(ph + 0.12 * v * s), v * half, r * math.sin(ph + 0.12 * v * s))))
        for i in range(ns):
            for j in range(nv):
                a = i * (nv + 1) + j
                faces.append((a, a + 1, a + nv + 2, a + nv + 1))
        bl = new_obj(name + 'Blade', verts, faces, M['chrome'])
        bake(bl, solidify=0.008, subsurf=1)
    # violet light inside: a glowing ring round the hub and fine filaments curling between the blades
    for sgn in (-1, 1):
        ring = [(0.062 + 0.004 * math.cos(a), sgn * yl * 0.55 + 0.004 * math.sin(a)) for a in (TAU * k / 6 for k in range(6))]
        lathe(name + 'Glow', ring, M['vein'], 40)
    for k in range(5):
        ph0 = TAU * k / 5 + 0.4
        pts = []
        for i in range(9):
            s = i / 8
            r = 0.07 + (rim_r - 0.09) * s
            ph = ph0 + 1.4 * s + 0.15 * math.sin(s * 9 + k)
            pts.append(Vector((r * math.cos(ph), (0.5 * math.sin(s * 5 + k * 1.7)) * yl * 0.6, r * math.sin(ph))))
        tube(name + 'Filament', pts, lambda s: 0.0028 + 0.0015 * math.sin(math.pi * s), M['vein'], sides=6, segs=30)
    wheel = join(name, PARTS)
    PARTS = saved
    return wheel


# ---------------------------------------------------------------- body
def key(x, z, w, ht, hb, y=0.0, **kw):
    return dict(c=Vector((x, y, z)), w=w, ht=ht, hb=hb, **kw)


# The hull: one long body from the nose tip over the tank, under the seat, and up into the tail cowl.
# Profile back-projected from the concept's silhouette through ConceptCam2 (art/align-bike2/backproject.py).
HULL = [
    key(0.885, 0.678, 0.006, 0.006, 0.006, e=2.2),
    key(0.84, 0.684, 0.045, 0.022, 0.03, e=2.2),
    key(0.76, 0.703, 0.10, 0.045, 0.055, e=2.2),
    key(0.66, 0.745, 0.150, 0.080, 0.085, e=2.3),
    key(0.54, 0.810, 0.180, 0.112, 0.105, e=2.3),
    key(0.40, 0.858, 0.190, 0.110, 0.095, e=2.3),
    key(0.22, 0.850, 0.180, 0.098, 0.085, e=2.3),
    key(0.02, 0.808, 0.160, 0.082, 0.075, e=2.3),
    key(-0.18, 0.745, 0.140, 0.055, 0.070, e=2.4),
    key(-0.36, 0.685, 0.125, 0.040, 0.075, e=2.6),
    key(-0.54, 0.680, 0.120, 0.050, 0.080, e=2.6),
    key(-0.70, 0.715, 0.095, 0.060, 0.060, e=2.4),
    key(-0.84, 0.722, 0.055, 0.042, 0.038, e=2.2),
    key(-0.935, 0.712, 0.010, 0.010, 0.010, e=2.2),
]


def hull_at(x):
    """Hull section (centre z, w, ht, hb) at bike x, by bisection on the hermite centre curve."""
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if hermite(HULL, mid, 'c').x > x:
            lo = mid
        else:
            hi = mid
    t = (lo + hi) / 2
    return hermite(HULL, t, 'c'), hermite(HULL, t, 'w'), hermite(HULL, t, 'ht'), hermite(HULL, t, 'hb')


def build_body(M):
    ch, bk = M['chrome'], M['black']
    for k in HULL:
        k.pop('t', None)
    chrome_parts = []
    chrome_parts.append(loft('Hull', HULL, ch, 70, 32, cap0='point', cap1='point', subsurf=0, track=False))

    # side swoops: broad S bands of poured chrome from under the nose, down in front of the heart, round the bottom
    # and back into the exhaust pods; and a second S from the tank down behind the heart
    for sgn in (-1, 1):
        sw = [
            key(0.80, 0.672, 0.02, 0.020, 0.020, y=sgn * 0.035),
            key(0.68, 0.700, 0.034, 0.045, 0.045, y=sgn * 0.125),
            key(0.53, 0.705, 0.045, 0.085, 0.085, y=sgn * 0.185),
            key(0.43, 0.610, 0.048, 0.090, 0.090, y=sgn * 0.205),
            key(0.395, 0.470, 0.046, 0.080, 0.080, y=sgn * 0.21),
            key(0.375, 0.330, 0.044, 0.072, 0.072, y=sgn * 0.205),
            key(0.32, 0.215, 0.042, 0.066, 0.066, y=sgn * 0.195),
            key(0.20, 0.150, 0.040, 0.060, 0.060, y=sgn * 0.18),
            key(0.04, 0.160, 0.040, 0.055, 0.055, y=sgn * 0.175),
            key(-0.10, 0.215, 0.036, 0.045, 0.045, y=sgn * 0.17),
        ]
        chrome_parts.append(loft('Swoop', sw, ch, 60, 16, cap0='point', cap1='point', subsurf=0, track=False))
        sw2 = [
            key(0.16, 0.835, 0.03, 0.040, 0.040, y=sgn * 0.13),
            key(0.02, 0.775, 0.036, 0.060, 0.060, y=sgn * 0.165),
            key(-0.11, 0.660, 0.040, 0.065, 0.065, y=sgn * 0.18),
            key(-0.17, 0.520, 0.040, 0.060, 0.060, y=sgn * 0.185),
            key(-0.16, 0.390, 0.040, 0.055, 0.055, y=sgn * 0.19),
            key(-0.10, 0.300, 0.036, 0.045, 0.045, y=sgn * 0.195),
        ]
        chrome_parts.append(loft('SwoopRear', sw2, ch, 40, 16, cap0='point', cap1='point', subsurf=0, track=False))
        # exhaust pod: a fat teardrop, nose low at the front, its round end under the engine
        pod = [
            key(0.36, 0.170, 0.02, 0.02, 0.02, y=sgn * 0.175),
            key(0.26, 0.215, 0.050, 0.048, 0.050, y=sgn * 0.205),
            key(0.10, 0.275, 0.068, 0.062, 0.062, y=sgn * 0.22),
            key(-0.08, 0.315, 0.066, 0.058, 0.058, y=sgn * 0.215),
            key(-0.19, 0.325, 0.042, 0.040, 0.040, y=sgn * 0.20),
            key(-0.225, 0.325, 0.006, 0.006, 0.006, y=sgn * 0.19),
        ]
        chrome_parts.append(loft('Pod', pod, ch, 40, 20, cap0='point', cap1='point', subsurf=0, track=False))
        # swingarm: a flattened chrome S from under the seat to the rear hub, outside the glass
        ry = R_W / 2 * 0.86 + 0.062 + 0.012 + 0.02
        arm = [
            key(-0.18, 0.40, 0.045, 0.06, 0.06, y=sgn * 0.17),
            key(-0.36, 0.45, 0.032, 0.058, 0.058, y=sgn * 0.20),
            key(-0.55, 0.43, 0.024, 0.048, 0.048, y=sgn * (ry - 0.005)),
            key(-0.70, 0.365, 0.022, 0.040, 0.040, y=sgn * ry),
            key(-0.785, 0.325, 0.022, 0.036, 0.036, y=sgn * ry),
            key(-0.82, 0.318, 0.004, 0.006, 0.006, y=sgn * ry),
        ]
        chrome_parts.append(loft('Swingarm', arm, ch, 40, 16, cap0='point', cap1='point', subsurf=0, track=False))
        # exhaust run: a tapering chrome pipe from under the pod back along the arm to the rear hub
        chrome_parts.append(tube('Exhaust', [(0.0, sgn * 0.205, 0.22), (-0.22, sgn * 0.215, 0.28), (-0.42, sgn * 0.23, 0.34),
                                             (-0.60, sgn * (ry - 0.005), 0.335), (-0.74, sgn * ry, 0.30)],
                                 lambda s: 0.034 - 0.014 * s, ch, sides=16, segs=50, track=False))
        # front arm: hub-centre steering, a chrome sweep from the swoop's foot to the front hub, outside the glass
        fy = F_W / 2 * 0.86 + 0.062 + 0.012 + 0.018
        farm = [
            key(0.36, 0.230, 0.04, 0.05, 0.05, y=sgn * 0.195),
            key(0.50, 0.270, 0.024, 0.042, 0.042, y=sgn * fy),
            key(0.66, 0.305, 0.020, 0.035, 0.035, y=sgn * fy),
            key(0.78, 0.315, 0.020, 0.034, 0.034, y=sgn * fy),
            key(0.815, 0.315, 0.004, 0.006, 0.006, y=sgn * fy),
        ]
        chrome_parts.append(loft('FrontArm', farm, ch, 30, 16, cap0='point', cap1='point', subsurf=0, track=False))
    # keel: the low cradle joining both swoops and pods under the heart
    keel = [key(0.42, 0.20, 0.03, 0.03, 0.03), key(0.30, 0.155, 0.13, 0.05, 0.045), key(0.0, 0.165, 0.16, 0.06, 0.05),
            key(-0.20, 0.27, 0.14, 0.07, 0.05), key(-0.30, 0.36, 0.08, 0.05, 0.05)]
    chrome_parts.append(loft('Keel', keel, ch, 30, 20, cap0='point', cap1='point', subsurf=0, track=False))
    # hip: under the seat, from the tank's rear down to the swingarm pivot
    hip = [key(-0.10, 0.62, 0.10, 0.08, 0.08), key(-0.25, 0.52, 0.15, 0.09, 0.09), key(-0.38, 0.52, 0.13, 0.08, 0.07),
           key(-0.52, 0.59, 0.10, 0.06, 0.05), key(-0.64, 0.64, 0.04, 0.03, 0.03)]
    chrome_parts.append(loft('Hip', hip, ch, 30, 20, cap0='point', cap1='point', subsurf=0, track=False))
    # the dash cowl: a chrome pedestal rising off the tank's nose to carry the dash
    chrome_parts.append(loft('DashCowl', [key(0.67, 0.84, 0.03, 0.03, 0.03), key(0.63, 0.90, 0.11, 0.05, 0.06),
                                          key(0.585, 0.945, 0.15, 0.045, 0.06), key(0.555, 0.96, 0.12, 0.03, 0.05)],
                             ch, 20, 24, cap0='point', cap1='ngon', subsurf=0, track=False))
    body = fuse('ChromeBody', chrome_parts, voxel=0.0042, smooth_iter=14, smooth_lambda=0.9, target_tris=62000, mat=ch)
    PARTS.append(body)

    # --- the dark interior: a black core filling the frame between the swoops so the recesses read deep
    core = [key(0.50, 0.62, 0.07, 0.08, 0.08), key(0.38, 0.55, 0.12, 0.18, 0.22), key(0.16, 0.55, 0.115, 0.20, 0.24),
            key(-0.08, 0.52, 0.11, 0.17, 0.20), key(-0.30, 0.50, 0.09, 0.10, 0.12), key(-0.45, 0.55, 0.05, 0.05, 0.05)]
    core_ob = loft('Core', core, bk, 24, 20, cap0='point', cap1='point', subsurf=1)
    # --- engine-like ribbed chrome forms behind the heart: two finned barrels and a ribbed side drum each side
    for i, (x, z, tilt) in enumerate(((-0.06, 0.47, -0.35), (-0.17, 0.43, -0.6))):
        prof = [(0.0, -0.11)]
        n = 11
        for k in range(n):
            y0 = -0.10 + 0.20 * k / (n - 1)
            prof += [(0.052, y0 - 0.006), (0.066, y0 - 0.0035), (0.066, y0 + 0.0035), (0.052, y0 + 0.006)]
        prof += [(0.0, 0.11)]
        ob = lathe('Barrel', prof, ch, 32, closed_prof=False)
        ob.data.transform(Matrix.Translation(Vector((x, 0, z))) @ Matrix.Rotation(tilt, 4, 'Y') @ Matrix.Rotation(math.pi / 2, 4, 'X'))
        ob.data.transform(Matrix.Translation(Vector((0, 0, 0))))
    for sgn in (-1, 1):
        prof = [(0.0, 0.0), (0.075, 0.0)]
        for k in range(6):
            r = 0.075 - 0.011 * k
            prof += [(r, 0.004 + 0.006 * k), (r - 0.004, 0.006 + 0.006 * k)]
        prof += [(0.012, 0.044), (0.0, 0.046)]
        drum = lathe('Drum', prof, ch, 40, closed_prof=False)
        if sgn < 0:
            drum.data.transform(Matrix.Scale(-1, 4, Vector((0, 1, 0))))
            drum.data.flip_normals()
        drum.data.transform(Matrix.Translation(Vector((-0.10, sgn * 0.135, 0.36))))

    # --- the heart, cradled in the frame: a lumpy anatomical heart, its great vessels arching up into the tank
    build_heart(M)

    # --- arteries: black and chrome tubes wrapping the heart, flowing back to the engine and up to the tank
    arteries = [
        ([(0.24, 0.05, 0.74), (0.30, 0.10, 0.80), (0.38, 0.13, 0.78), (0.44, 0.15, 0.66), (0.46, 0.16, 0.50), (0.44, 0.16, 0.35)], 0.024, bk),
        ([(0.10, 0.10, 0.72), (0.02, 0.15, 0.70), (-0.06, 0.16, 0.62), (-0.10, 0.17, 0.50), (-0.06, 0.18, 0.38)], 0.022, bk),
        ([(0.30, 0.10, 0.48), (0.36, 0.16, 0.42), (0.34, 0.18, 0.30), (0.22, 0.18, 0.24), (0.05, 0.17, 0.28), (-0.12, 0.16, 0.36)], 0.020, ch),
        ([(0.14, 0.13, 0.42), (0.10, 0.17, 0.33), (-0.02, 0.18, 0.30), (-0.20, 0.17, 0.42), (-0.30, 0.15, 0.55)], 0.018, bk),
        ([(0.33, 0.06, 0.70), (0.40, 0.12, 0.70), (0.42, 0.17, 0.60), (0.40, 0.19, 0.45)], 0.016, ch),
        ([(-0.02, 0.08, 0.66), (-0.12, 0.14, 0.64), (-0.24, 0.15, 0.60), (-0.36, 0.14, 0.62), (-0.48, 0.12, 0.64)], 0.020, ch),
    ]
    for ctrl, r, mat in arteries:
        for c in (ctrl, mirror(ctrl)):
            tube('Artery', c, lambda s, r=r: r * (1.0 - 0.25 * s) * (1 + 0.12 * abs(math.sin(math.pi * 9 * s)) ** 8), mat, sides=12)
    # the black ribbed hose from under the nose into the front hub (concept: curling into the glass)
    fy = F_W / 2 * 0.86 + 0.062 + 0.012
    for sgn in (-1, 1):
        tube('Hose', [(0.60, sgn * 0.16, 0.66), (0.66, sgn * 0.205, 0.56), (0.72, sgn * 0.215, 0.45), (0.77, sgn * (fy + 0.02), 0.37),
                      (0.78, sgn * (fy + 0.02), 0.33)],
             lambda s: 0.021 * (1 + 0.14 * abs(math.sin(math.pi * 16 * s)) ** 6), bk, sides=12, segs=60)

    # --- violet veins glowing in the dark recesses, laid onto the black core and the heart's flanks
    core_tree = bvh([core_ob])
    import random
    rnd = random.Random(7)
    for sgn in (-1, 1):
        for k in range(9):
            x0 = rnd.uniform(-0.35, 0.40)
            z0 = rnd.uniform(0.30, 0.72)
            pts = []
            for i in range(8):
                s = i / 7
                x = x0 + (rnd.uniform(-0.03, 0.03) + 0.30 * s * (1 if k % 2 else -1)) * 0.8
                z = z0 + 0.12 * math.sin(s * 4 + k) + rnd.uniform(-0.02, 0.02)
                h = cast(core_tree, (x, sgn * 0.6, z), (0, -sgn, 0))
                if h:
                    pts.append(h[0] + Vector((0, sgn * 0.004, 0)))
            if len(pts) >= 4:
                tube('Vein', pts, lambda s: 0.0045 * (1 - 0.6 * s) + 0.0015, M['vein'], sides=6, cap1='point')
    return core_ob


def build_heart(M):
    """Anatomical heart from overlapping ellipsoids and vessel stubs, fused and smoothed into one lumpy wet muscle,
    with violet coronary veins laid over it."""
    hm = M['heart']
    C = Vector((0.175, 0.0, 0.575))
    tilt = -0.42  # apex points down and forward
    R = Matrix.Rotation(tilt, 4, 'Y')

    def at(v):
        return C + (R @ Vector(v))
    parts = [
        ellipsoid('H', at((0.0, 0.0, 0.0)), (0.105, 0.115, 0.125), hm, rot=(0, tilt, 0)),           # ventricles
        ellipsoid('H', at((0.02, 0.035, -0.09)), (0.065, 0.07, 0.075), hm, rot=(0, tilt - 0.3, 0)),  # apex
        ellipsoid('H', at((0.035, 0.05, 0.02)), (0.08, 0.075, 0.10), hm, rot=(0, tilt, 0.3)),      # right ventricle bulge
        ellipsoid('H', at((-0.055, -0.04, 0.10)), (0.07, 0.075, 0.06), hm),                          # left atrium
        ellipsoid('H', at((0.03, 0.07, 0.10)), (0.06, 0.055, 0.055), hm),                            # right atrium
        ellipsoid('H', at((-0.02, 0.0, 0.135)), (0.06, 0.06, 0.045), hm),
    ]
    # great vessels: aorta arching back, pulmonary trunk forward, venae cavae
    parts.append(tube('H', [at((-0.01, 0.0, 0.10)), at((0.0, 0.0, 0.19)), at((-0.05, 0.0, 0.24)), at((-0.12, -0.01, 0.21)), at((-0.15, -0.01, 0.15))],
                      0.036, hm, sides=16, segs=30, track=False))
    parts.append(tube('H', [at((0.04, 0.03, 0.10)), at((0.06, 0.03, 0.18)), at((0.10, 0.0, 0.215))], 0.03, hm, sides=16, segs=16, track=False))
    parts.append(tube('H', [at((0.03, 0.08, 0.12)), at((0.02, 0.10, 0.20)), at((0.0, 0.10, 0.25))], 0.024, hm, sides=12, segs=12, track=False))
    for i in range(3):  # aortic arch branches
        parts.append(tube('H', [at((-0.03 - 0.03 * i, 0.0, 0.24)), at((-0.03 - 0.035 * i, 0.0, 0.29))], 0.012, hm, sides=10, segs=6, track=False))
    for p in parts:
        if p in PARTS:
            PARTS.remove(p)
    heart = fuse('Heart', parts, voxel=0.0035, smooth_iter=10, smooth_lambda=0.9, target_tris=None, mat=hm)
    # lumpy, wet muscle: low-frequency bulges plus fine striation along the ventricles
    from mathutils import noise
    me = heart.data
    for v in me.vertices:
        p = v.co
        n = v.normal
        d = 0.006 * noise.noise(p * 14.0) + 0.0025 * noise.noise(p * 40.0 + Vector((3, 1, 2))) + 0.0012 * math.sin((R.inverted() @ (p - C)).z * 260)
        v.co = p + n * d
    dm = heart.modifiers.new('dec', 'DECIMATE')
    dm.ratio = min(1.0, 16000 / tri_count(heart))
    apply_mods(heart)
    heart.data.shade_smooth()
    PARTS.append(heart)
    # coronary veins: walk over the surface, raycasting back onto it
    tree = bvh([heart])
    import random
    rnd = random.Random(3)
    for k in range(16):
        a = rnd.uniform(0, TAU)
        b = rnd.uniform(-0.2, 0.9)
        pts = []
        for i in range(10):
            s = i / 9
            aa = a + 0.6 * math.sin(s * 3 + k) * 0.5 + rnd.uniform(-0.05, 0.05)
            bb = b - 1.1 * s
            d = R @ Vector((math.cos(aa) * math.cos(bb), math.sin(aa) * math.cos(bb), math.sin(bb)))
            h = cast(tree, C + d * 0.4, -d)
            if h:
                pts.append(h[0] + h[1] * 0.0015)
        if len(pts) >= 5:
            tube('Coronary', pts, lambda s: 0.0042 * (1 - 0.7 * s) + 0.001, M['vein'] if k % 3 else M['black'], sides=6, cap1='point')
    return heart


def build_canopy(M):
    """Smoked glass bubble over the nose: rises from the LED seam over the nose and flows back to the bars, a cockpit
    notch cut out of its rear so the rider sees the dash. Columns run over the top (angle a), rows run back along x."""
    def top(x):  # canopy crown height (concept silhouette, back-projected)
        pts = [(0.86, 0.69), (0.83, 0.755), (0.79, 0.815), (0.73, 0.875), (0.66, 0.925), (0.58, 0.965), (0.50, 0.99), (0.44, 1.0)]
        for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
            if x1 <= x <= x0:
                f = (x - x0) / (x1 - x0)
                f = f * f * (3 - 2 * f) * 0.3 + f * 0.7
                return z0 + (z1 - z0) * f
        return pts[-1][1]

    def seam(x):  # where it sits on the hull: the LED line
        c, w, ht, hb = hull_at(x)
        return c.z + ht * 0.15, w * 1.02

    x_nose = 0.862
    nr, na = 36, 40
    verts = []
    for i in range(nr + 1):
        for j in range(na + 1):
            a = math.pi * j / na  # 0 = -Y side ... pi = +Y side
            sa = math.sin(a)
            x_end = 0.50 + 0.13 * sa ** 8
            t = i / nr
            x = x_nose + (x_end - x_nose) * (t ** 0.85)
            zs, ws = seam(x)
            zt = top(x)
            w = max(ws * 1.12 + 0.02 * smoothstep(0.86, 0.6, x), 1e-4)
            hh = max(zt - zs, 1e-4)
            c = -math.cos(a)
            u = w * math.copysign(abs(c) ** (2 / 2.3), c)
            v = hh * abs(sa) ** (2 / 2.3)
            verts.append(Vector((x, u, zs + v)))
    faces = []
    for i in range(nr):
        for j in range(na):
            a = i * (na + 1) + j
            faces.append((a, a + 1, a + na + 2, a + na + 1))
    ob = new_obj('Canopy', verts, faces, M['smoke'])
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.to_mesh(ob.data)
    bm.free()
    bake(ob, solidify=0.005, subsurf=1)
    # a black bay under the glass (the headlight cavity), so the smoke reads dark like the concept's
    bay = [key(0.85, 0.70, 0.01, 0.01, 0.01), key(0.78, 0.74, 0.07, 0.05, 0.02), key(0.68, 0.80, 0.13, 0.08, 0.03),
           key(0.58, 0.85, 0.15, 0.08, 0.03), key(0.52, 0.86, 0.12, 0.05, 0.02)]
    loft('Bay', bay, M['black'], 20, 18, cap0='point', cap1='ngon', subsurf=1)
    # the LED slit: a thin bright line along the seam, wrapping round the nose
    pts = []
    for k in range(13):
        s = -1 + 2 * k / 12
        x = 0.862 - 0.25 * abs(s) ** 1.2
        zs, ws = seam(x)
        pts.append(Vector((x + 0.004, math.copysign(ws * 1.06 + 0.002, s) * min(1, abs(s) * 3), zs + 0.004)))
    tube('Led', pts, 0.0042, M['led'], sides=8, segs=80, squash=0.55)
    return ob


def build_dash(M):
    """Bike2Dash: a curved glass display between the bars, just ahead of the button, facing the rider's eye.
    UV 0-1: u to the rider's right (-Y), v up."""
    eye = RIDER_EYE.translation
    D = Vector((0.585, 0.0, 1.0))
    N = (eye - D)
    N.y = 0
    N.normalize()
    U = Vector((-N.z, 0, N.x)).normalized()  # up the panel, leaning forward
    if U.z < 0:
        U = -U
    Rt = Vector((0, -1, 0))
    width, height, Rc, corner = 0.27, 0.085, 0.32, 0.30
    nu, nv = 40, 10
    verts, faces, uvs = [], [], []
    for j in range(nv + 1):
        for i in range(nu + 1):
            u, v = i / nu, j / nv
            th = (u - 0.5) * width / Rc
            # rounded ends: shrink the column's height near the ends (a stadium)
            e = abs(2 * u - 1)
            k = 1.0 if e < 1 - corner else math.sqrt(max(0.0, 1 - ((e - (1 - corner)) / corner) ** 2))
            vv = (v - 0.5) * k + 0.5
            p = D + Rt * (math.sin(th) * Rc) - N * ((1 - math.cos(th)) * Rc) + U * ((vv - 0.5) * height)
            verts.append(p)
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))
            uvs.append(((i / nu, j / nv), ((i + 1) / nu, j / nv), ((i + 1) / nu, (j + 1) / nv), (i / nu, (j + 1) / nv)))
    dash = new_obj('Bike2Dash', verts, faces, M['dash'], uvs=uvs, track=False)
    if sum(p.normal.dot(N) for p in dash.data.polygons) < 0:
        dash.data.flip_normals()
    # a chrome bezel behind it: the same panel grown a little and thickened back
    bverts = []
    for j in range(nv + 1):
        for i in range(nu + 1):
            u, v = i / nu, j / nv
            th = (u - 0.5) * (width + 0.03) / Rc
            e = abs(2 * u - 1)
            k = 1.0 if e < 1 - corner else math.sqrt(max(0.0, 1 - ((e - (1 - corner)) / corner) ** 2))
            vv = (v - 0.5) * k + 0.5
            p = D - N * 0.004 + Rt * (math.sin(th) * Rc) - N * ((1 - math.cos(th)) * Rc) + U * ((vv - 0.5) * (height + 0.028))
            bverts.append(p)
    bez = new_obj('Bezel', bverts, faces, M['chrome'])
    if sum(p.normal.dot(N) for p in bez.data.polygons) < 0:
        bez.data.flip_normals()
    bake(bez, solidify=0.03, subsurf=1, solid_offset=-1)
    return dash, (D, N, U)


def build_bars(M):
    ch = M['chrome']
    for sgn in (-1, 1):
        bar = [Vector((0.52, sgn * 0.10, 0.925)), Vector((0.49, sgn * 0.20, 0.965)), Vector((0.44, sgn * 0.29, 0.975)), Vector((0.41, sgn * 0.33, 0.975))]
        tube('Bar', bar, 0.013, ch, sides=12, segs=20)
        tube('Grip', [Vector((0.415, sgn * 0.32, 0.975)), Vector((0.375, sgn * 0.43, 0.97))],
             lambda s: 0.019 * (1 + 0.05 * abs(math.sin(math.pi * 10 * s))), M['black'], sides=14, segs=16)
        tube('BarEnd', [Vector((0.375, sgn * 0.43, 0.97)), Vector((0.371, sgn * 0.442, 0.97))], 0.021, ch, sides=14, segs=2)
        # switch pods at the inner ends of the grips (concept-transition)
        ellipsoid('Switch', (0.43, sgn * 0.305, 0.985), (0.03, 0.022, 0.028), M['black'], segs=20, rings=10)
        # mirror: a curved stalk rising outward to a small round chrome head facing back
        stalk = [Vector((0.47, sgn * 0.24, 0.97)), Vector((0.50, sgn * 0.30, 1.04)), Vector((0.505, sgn * 0.35, 1.10)), Vector((0.495, sgn * 0.38, 1.125))]
        tube('Stalk', stalk, (0.009, 0.006), ch, sides=10, segs=20)
        head = lathe('Mirror', [(0.0, -0.014), (0.042, -0.012), (0.05, -0.002), (0.046, 0.008), (0.0, 0.006)], ch, 28, closed_prof=False)
        head.data.transform(Matrix.Translation(Vector((0.49, sgn * 0.39, 1.135))) @ Matrix.Rotation(sgn * 0.25, 4, 'Z') @ Matrix.Rotation(-math.pi / 2, 4, 'Z'))
        glass = lathe('MirrorGlass', [(0.0, -0.0145), (0.040, -0.0125)], ch, 28, closed_prof=False)
        glass.data.transform(Matrix.Translation(Vector((0.49, sgn * 0.39, 1.135))) @ Matrix.Rotation(sgn * 0.25, 4, 'Z') @ Matrix.Rotation(-math.pi / 2, 4, 'Z'))


def build_rear(M):
    # low black leather seat, scooped, sitting into the hull
    seat = [key(-0.25, 0.735, 0.07, 0.025, 0.04, e=3), key(-0.32, 0.752, 0.135, 0.03, 0.05, e=3), key(-0.46, 0.742, 0.15, 0.028, 0.05, e=3),
            key(-0.58, 0.756, 0.125, 0.03, 0.05, e=3), key(-0.64, 0.765, 0.07, 0.02, 0.04, e=3)]
    loft('Seat', seat, M['seat'], 24, 24, cap0='point', cap1='point', subsurf=1)
    # tuck lines across the seat (shallow black ridges)
    for x in (-0.36, -0.42, -0.48, -0.54):
        c, w, ht, hb = 0.0, 0.12, 0, 0
        tube('Tuck', [Vector((x, -0.11, 0.765)), Vector((x - 0.01, 0.0, 0.777)), Vector((x, 0.11, 0.765))], 0.004, M['seat'], sides=6, segs=12)
    # tail light: a small red sliver at the cowl's tip
    tube('TailLight', [Vector((-0.925, -0.022, 0.716)), Vector((-0.935, 0.0, 0.718)), Vector((-0.925, 0.022, 0.716))], 0.008, M['tail'], sides=10, segs=12, squash=0.6)
    # kickstand on +Y (as bike.glb's: the foot touches the ground once the bike leans)
    foot_y = 0.30
    foot_z = (0.015 + math.sin(LEAN) * foot_y) / math.cos(LEAN)
    tube('Stand', [Vector((-0.04, 0.16, 0.26)), Vector((-0.12, 0.23, 0.15)), Vector((-0.20, foot_y, foot_z))], (0.016, 0.011), M['chrome'], sides=10, segs=12)
    tube('StandFoot', [Vector((-0.23, foot_y, foot_z)), Vector((-0.17, foot_y, foot_z))], 0.015, M['chrome'], sides=10, segs=2, squash=0.6)


# ---------------------------------------------------------------- the throttle button (as art/build-bike.py)
def conform_tank(body):
    """Ease the chrome hull's top so that, under the button's footprint, it sits exactly where bike.glb's carapace did:
    a smooth local lift/sink that brings the pill's face onto ButtonCentre."""
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
    want = BUTTON_CENTRE.translation.z - 0.0022 - lift
    delta = want - coef[0]
    print('TANK under button: z', round(coef[0], 4), 'want', round(want, 4), 'delta', round(delta, 4))
    me = body.data
    for v in me.vertices:
        p = v.co
        if v.normal.z > 0.2 and p.z > 0.8:
            d2 = ((p.x - BUTTON_X) / 0.22) ** 2 + (p.y / 0.16) ** 2
            if d2 < 4:
                v.co.z += delta * math.exp(-d2)
    me.update()


def build_button(M, body):
    import numpy as np
    tree = bvh([body])

    def hit_z(x, y):
        h = cast(tree, (x, y, 2.0), (0, 0, -1))
        return h[0].z if h else None
    a, r = BUTTON_LEN / 2, BUTTON_WID / 2
    xs = np.linspace(BUTTON_X - a - 0.01, BUTTON_X + a + 0.01, 17)
    ys = np.linspace(-r - 0.01, r + 0.01, 9)
    rows, zs = [], []
    for x in xs:
        for y in ys:
            z = hit_z(x, y)
            if z is not None:
                dx = x - BUTTON_X
                rows.append([1, dx, y, dx * dx, dx * y, y * y])
                zs.append(z)
    A, Z = np.array(rows), np.array(zs)
    coef, *_ = np.linalg.lstsq(A, Z, rcond=None)
    lift = float((Z - A @ coef).max()) + 0.003
    FACE_H = 0.0022
    # pin the face centre onto bike.glb's ButtonCentre (conform_tank has already brought the tank to within a hair)
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
    btn = rings_mesh('Bike2Button', rings, M['button'], track=False)
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
    gme = bpy.data.meshes.new('Bike2ButtonGlyph')
    bm.to_mesh(gme)
    bm.free()
    for v in gme.vertices:
        x, y, tz = v.co.x, v.co.y, v.co.z
        p, n = base(x, y)
        v.co = p + n * (FACE_H + 0.0015 + tz)
    gme.materials.append(M['glyph'])
    gme.shade_flat()
    glyph = bpy.data.objects.new('Bike2ButtonGlyph', gme)
    bpy.context.scene.collection.objects.link(glyph)

    pc, nc = base(BUTTON_X, 0.0)
    pc = pc + nc * FACE_H
    print('BUTTON face centre', tuple(round(c, 5) for c in pc), 'ButtonCentre', tuple(round(c, 5) for c in BUTTON_CENTRE.translation),
          'normal', tuple(round(c, 4) for c in nc))
    # anchors: bike.glb's exact bike-local transforms
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
    # sunset sky: violet overhead, pink, then a hot orange band at the horizon; dark plum below
    world = bpy.data.worlds.new('SunsetWorld')
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
    cr.elements[0].position, cr.elements[0].color = 0.0, (0.02, 0.012, 0.03, 1)
    cr.elements[1].position, cr.elements[1].color = 1.0, (0.10, 0.07, 0.32, 1)
    for pos, c in ((0.48, (0.08, 0.04, 0.09, 1)), (0.50, (1.6, 0.55, 0.32, 1)), (0.53, (1.1, 0.42, 0.62, 1)), (0.62, (0.55, 0.30, 0.85, 1)),
                   (0.80, (0.22, 0.15, 0.55, 1))):
        e = cr.elements.new(pos)
        e.color = c
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.0
    col = bpy.data.collections.new('Render')
    scene.collection.children.link(col)
    # low orange sun behind the bike (from the -Y side, as in the concept), raking across
    sd = bpy.data.lights.new('Sun', 'SUN')
    sd.color = (1.0, 0.55, 0.3)
    sd.energy = 4.0
    sd.angle = math.radians(2)
    sun = bpy.data.objects.new('Sun', sd)
    sun.rotation_euler = (Vector((0.3, 1.0, 0.12)).to_track_quat('Z', 'Y')).to_euler()
    col.objects.link(sun)
    # bright white/violet 'architecture' panels around, unseen by the camera, for the chrome to reflect
    for i, (loc, size, colr, s) in enumerate((((0, -6, 2.0), (14, 3), (0.9, 0.85, 1.0), 2.5), ((-3, 5, 1.5), (10, 2.5), (0.85, 0.75, 1.0), 2.0),
                                               ((6, 1, 1.2), (6, 2), (1.0, 0.8, 0.9), 2.0), ((0, 0, 6), (6, 3), (0.7, 0.6, 1.0), 1.5))):
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
    # wet plaza floor
    me = bpy.data.meshes.new('Ground')
    s = 30
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new('Ground', me)
    col.objects.link(g)
    gm = bpy.data.materials.new('WetGround')
    gm.use_nodes = True
    gnt = gm.node_tree
    b = gnt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.03, 0.025, 0.035, 1)
    noise = gnt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 1.4
    mr = gnt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = 0.45
    mr.inputs['From Max'].default_value = 0.6
    mr.inputs['To Min'].default_value = 0.03
    mr.inputs['To Max'].default_value = 0.4
    gnt.links.new(noise.outputs['Fac'], mr.inputs['Value'])
    gnt.links.new(mr.outputs['Result'], b.inputs['Roughness'])
    me.materials.append(gm)
    # bloom
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
    import json
    os.makedirs(RENDER_DIR, exist_ok=True)
    cc = json.load(open(os.path.join(ALIGN, 'concept-cam2.json')))
    eye_w = body.matrix_world @ RIDER_EYE
    cams = {
        # fitted so our tyres and contacts land on the concept's (art/align-bike2/fit_camera.py); not exported
        'concept': (add_camera(col, 'ConceptCam2', cc['location'], cc['look'], lens=cc['lens']), tuple(cc['size'])),
        'rider': (add_camera(col, 'RiderCam2', None, lens=16, matrix=eye_w @ Matrix.Rotation(math.pi / 2, 4, 'X')), (1672, 941)),
        'side': (add_camera(col, 'CamSide2', (0, -8, 0.62), rot=(math.pi / 2, 0, 0), ortho=2.9), (1920, 1080)),
        'hero': (add_camera(col, 'CamHero2', (2.6, -3.4, 0.75), (0.1, 0, 0.6), lens=32), (1920, 1080)),
        'top': (add_camera(col, 'CamTop2', (0, 0, 8), rot=(0, 0, 0), ortho=2.9), (1920, 1080)),
    }
    suffix = f'-{TAG}' if TAG else ''
    for k, (cam, res) in cams.items():
        if VIEWS and k not in VIEWS:
            continue
        scene.camera = cam
        scene.render.resolution_x, scene.render.resolution_y = res
        scene.render.filepath = os.path.join(RENDER_DIR, f'bike2-{k}{suffix}.png')
        bpy.ops.render.render(write_still=True)
        print('rendered', scene.render.filepath)


# ---------------------------------------------------------------- main
def main():
    scene = reset()
    M = make_materials()
    core = build_body(M)
    body_chrome = [o for o in PARTS if o.name.startswith('ChromeBody')][0]
    conform_tank(body_chrome)
    build_canopy(M)
    build_bars(M)
    build_rear(M)
    dash, _ = build_dash(M)
    extras = build_button(M, body_chrome)
    per = {}
    for o in PARTS:
        per[o.name.split('.')[0]] = per.get(o.name.split('.')[0], 0) + tri_count(o)
    print('PARTS', sorted(per.items(), key=lambda kv: -kv[1]))
    body = join('Bike2', PARTS)
    PARTS.clear()

    wf = build_wheel('Wheel2Front', F_R, F_W, M, front=True)
    wr = build_wheel('Wheel2Rear', R_R, R_W, M, front=False)
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
