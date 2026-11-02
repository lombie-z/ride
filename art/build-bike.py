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
VIEWS = ARGS[ARGS.index('--views') + 1].split(',') if '--views' in ARGS else None  # e.g. concept,hero

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


def chitin_textures(size=1024):
    """Tiling height field of overlapping, cracked, pitted carapace plates -> normal map, plus an ORM map
    (G roughness with wet streaks, B metallic). Generated with numpy, packed into the .blend and the glb."""
    import numpy as np
    rng = np.random.default_rng(11)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size

    def voronoi(n, seed):
        r = np.random.default_rng(seed)
        jit = (r.random((n, n, 2)) * 0.8 + 0.1).astype(np.float32)
        X, Y = xx * n, yy * n
        cx, cy = np.floor(X).astype(np.int32), np.floor(Y).astype(np.int32)
        F1 = np.full(X.shape, 9.0, np.float32)
        F2 = np.full(X.shape, 9.0, np.float32)
        cid = np.zeros(X.shape, np.int32)
        dx1 = np.zeros(X.shape, np.float32)
        dy1 = np.zeros(X.shape, np.float32)
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                nx, ny = cx + ox, cy + oy
                wx, wy = nx % n, ny % n
                px, py = nx + jit[wy, wx, 0], ny + jit[wy, wx, 1]
                ddx, ddy = X - px, Y - py
                d = np.sqrt(ddx * ddx + ddy * ddy)
                closer = d < F1
                F2 = np.where(closer, F1, np.minimum(F2, d))
                cid = np.where(closer, wy * n + wx, cid)
                dx1 = np.where(closer, ddx, dx1)
                dy1 = np.where(closer, ddy, dy1)
                F1 = np.where(closer, d, F1)
        return F1, F2, cid, dx1, dy1

    def noise(sx, sy, seed):  # tileable gaussian-filtered noise in [0, 1]
        r = np.random.default_rng(seed)
        f = np.fft.fft2(r.standard_normal((size, size)))
        fy = np.fft.fftfreq(size)[:, None]
        fx = np.fft.fftfreq(size)[None, :]
        f *= np.exp(-2 * math.pi ** 2 * ((fx * sx) ** 2 + (fy * sy) ** 2))
        out = np.real(np.fft.ifft2(f))
        return ((out - out.min()) / (out.max() - out.min())).astype(np.float32)

    def sstep(a, b, x):
        t = np.clip((x - a) / (b - a), 0, 1)
        return t * t * (3 - 2 * t)

    # big overlapping plates: each tilts (mostly along +v) so its rear edge stands proud of the next
    F1, F2, cid, dx, dy = voronoi(6, 1)
    edge = F2 - F1
    ang = (math.pi / 2 + (rng.random(36) - 0.5) * 1.2).astype(np.float32)[cid]
    amp = (0.35 + rng.random(36) * 0.35).astype(np.float32)[cid]
    plate = sstep(0.0, 0.22, edge)
    h = 0.5 * plate + amp * (dx * np.cos(ang) + dy * np.sin(ang)) * plate
    h += 0.035 * np.sin(F1 * math.tau * 4.0) * plate  # growth lines
    crack = 1 - sstep(0.0, 0.03, edge)
    h -= 0.30 * crack
    # finer scales and hairline cracks
    G1, G2, gid, _, _ = voronoi(19, 2)
    gedge = G2 - G1
    h += 0.06 * sstep(0.0, 0.3, gedge)
    fine = 1 - sstep(0.0, 0.05, gedge)
    h -= 0.05 * fine
    # pitting
    P1, _, pid, _, _ = voronoi(64, 3)
    pits = (1 - sstep(0.06, 0.26, P1)) * (rng.random(64 * 64) < 0.5).astype(np.float32)[pid]
    h -= 0.05 * pits
    h += 0.12 * noise(30, 30, 4)

    k = 5.0 * size / 1024  # slope scale
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5 * k
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5 * k
    nz = 1 / np.sqrt(gx * gx + gy * gy + 1)
    nrm = np.stack([-gx * nz * 0.5 + 0.5, -gy * nz * 0.5 + 0.5, nz * 0.5 + 0.5, np.ones_like(nz)], -1)

    rough = 0.10 + 0.06 * noise(12, 12, 5) + 0.32 * crack + 0.10 * fine + 0.15 * pits
    streak = sstep(0.56, 0.72, noise(1.5, 60, 6))  # long wet runs along v
    rough = rough * (1 - streak) + 0.05 * streak
    rough = np.clip(rough, 0.04, 0.75)
    orm = np.stack([np.ones_like(rough), rough, np.full_like(rough, 0.15), np.ones_like(rough)], -1)

    imgs = []
    for name, arr in (('BikeChitinNormal', nrm), ('BikeChitinORM', orm)):
        img = bpy.data.images.new(name, size, size, alpha=False)
        img.colorspace_settings.name = 'Non-Color'
        img.pixels.foreach_set(arr.astype(np.float32).ravel())
        img.pack()
        imgs.append(img)
    return imgs


def wire_chitin(m, nimg, oimg):
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tn = nt.nodes.new('ShaderNodeTexImage')
    tn.image = nimg
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nm.inputs['Strength'].default_value = 1.0
    nt.links.new(tn.outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    nmc = nt.nodes.new('ShaderNodeNormalMap')  # the wet coat follows the plates, but more gently than the shell
    nmc.inputs['Strength'].default_value = 0.4
    nt.links.new(tn.outputs['Color'], nmc.inputs['Color'])
    nt.links.new(nmc.outputs['Normal'], b.inputs['Coat Normal'])
    to = nt.nodes.new('ShaderNodeTexImage')
    to.image = oimg
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(to.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs['Green'], b.inputs['Roughness'])
    nt.links.new(sep.outputs['Blue'], b.inputs['Metallic'])


def make_materials():
    M = {
        'chitin': principled('BikeChitin', (0.008, 0.010, 0.009), metallic=0.25, rough=0.16, coat=1.0, coat_rough=0.02),
        'chrome': principled('BikeChrome', (0.78, 0.76, 0.70), metallic=1.0, rough=0.13),
        'glow': principled('BikeGlow', srgb('#3c8c1c'), rough=0.25, emit=srgb('#7dff4a'), emit_strength=1.8),
        'eye': principled('BikeEye', srgb('#4a5a10'), rough=0.1, emit=srgb('#dcff5a'), emit_strength=12.0),
        'tyre': principled('BikeTyre', (0.016, 0.016, 0.016), rough=0.62, spec=0.35),
        'bone': principled('BikeBone', (0.55, 0.52, 0.45), metallic=0.6, rough=0.34),
        # translucent rib shells round the glowing cores: alpha-blended dark green glass
        'ribglass': principled('BikeRibGlass', srgb('#1a5c10'), rough=0.05, emit=srgb('#7dff4a'), emit_strength=0.12),
    }
    # the 'get on' button: glassy pale green-white glow; the glyph brighter. The site drives both intensities.
    M['button'] = principled('BikeButton', srgb('#9fd88a'), rough=0.06, coat=1.0, coat_rough=0.02, emit=srgb('#c8ffb0'), emit_strength=1.0)
    M['glyph'] = principled('BikeButtonGlyph', srgb('#e8ffe0'), rough=0.3, emit=srgb('#f0ffe6'), emit_strength=4.0)
    g = M['ribglass']
    g.node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value = 0.45
    g.surface_render_method = 'BLENDED'
    g.use_backface_culling = True
    wire_chitin(M['chitin'], *chitin_textures())
    return M


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


def new_obj(name, verts, faces, mat, smooth=True, uvs=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    layer = me.uv_layers.new(name='UVMap')
    if uvs:  # one (u, v) per face corner, in texture tiles
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
    PARTS.append(ob)
    return ob


TILE = 0.5  # metres of surface per repeat of the chitin texture


def rings_mesh(name, rings, mat, closed_ring=True, closed_along=False, cap0=None, cap1=None, smooth=True):
    m = len(rings[0])
    verts = [v for r in rings for v in r]
    faces, uvs = [], []
    nr = len(rings)
    # arc-length UVs: u around each ring, v along the sweep
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
        else:  # a point: Vector tip
            verts.append(cap)
            c = len(verts) - 1
            for j in range(m):
                faces.append((idx[j], idx[(j + 1) % m], c))
                uvs.append(((us[ri][j], vs[ri]), (us[ri][j + 1], vs[ri]), ((us[ri][j] + us[ri][j + 1]) / 2, vs[ri] + 0.02)))
    return new_obj(name, verts, faces, mat, smooth, uvs)


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
                      ridge=g('ridge'), keel=g('keel'), a0=g('a0', -math.pi / 2), a1=g('a1', 1.5 * math.pi), closed=closed)
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
    ys = (-0.108, 0.108) if front else (-0.105,)
    for y in ys:
        disc(name + 'Disc', 0.095 if front else 0.07, 0.155 if front else 0.115, y, M['chrome'], sectors=40)
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

    # --- the dome: one big bulbous carapace from behind the bars to the eye, sitting over the ribcage.
    # Profile (x, top, bottom, half-width) back-projected from the concept's traced outline through ConceptCam.
    dome = [(-0.20, 0.785, 0.745, 0.15), (0.02, 0.885, 0.765, 0.205), (0.25, 0.95, 0.745, 0.245), (0.47, 0.965, 0.70, 0.265),
            (0.62, 0.93, 0.665, 0.255), (0.72, 0.86, 0.655, 0.21), (0.80, 0.775, 0.655, 0.13)]
    x0, x1 = dome[0][0], dome[-1][0]
    head = []
    for x, top, bot, w in dome:
        rid = 0.025 if 0.0 < x < 0.76 else 0.0
        head.append(dict(t=(x - x0) / (x1 - x0), c=Vector((x, 0, (top + bot) / 2)), w=w, ht=(top - bot) / 2 - rid, hb=(top - bot) / 2, ridge=rid, e=2.05))
    loft('Head', head, ch, 26, 22, cap0='ngon', cap1='ngon', subsurf=1)

    def dome_at(x):
        t = min(max((x - x0) / (x1 - x0), 0), 1)
        return {f: hermite(head, t, f, 0.0) for f in ('w', 'ht', 'hb', 'ridge')} | {'c': hermite(head, t, 'c')}

    def shell(name, xa, xb, grow, a0, a1, n_along=5, n_around=14, lift=0.0):
        keys = []
        for f in (0.0, 0.5, 1.0):
            d = dome_at(xa + (xb - xa) * f)
            sc = grow[0] + (grow[1] - grow[0]) * f
            keys.append(dict(c=d['c'] + Vector((0, 0, lift * f)), w=d['w'] * sc, ht=d['ht'] * sc, hb=d['hb'] * sc, ridge=d['ridge'] * sc,
                             a0=a0 - 0.08 * f, a1=a1 + 0.08 * f, e=2.05))
        return loft(name, keys, ch, n_along, n_around, closed=False, solidify=0.012, subsurf=1)

    # overlapping segment plates over the rear of the dome (abdomen-like), each rear edge standing proud of the next
    for xa, xb, edge in ((-0.24, 0.06, 0.45), (0.02, 0.30, 0.30), (0.26, 0.52, 0.22)):
        shell('Tank', xa, xb, (1.02, 1.08), -edge, math.pi + edge, lift=-0.005)
    # brow over the front of the dome, overhanging the eye
    shell('Brow', 0.44, 0.83, (1.035, 1.06), 0.10, math.pi - 0.10, n_along=12)
    # cheek plates over the sides behind the eye
    for sgn in (-1, 1):
        a0, a1 = (-1.1, 0.5) if sgn > 0 else (math.pi - 0.5, math.pi + 1.1)
        shell('Cheek', 0.50, 0.79, (1.03, 1.05), a0, a1, n_along=8, n_around=8)
    # mandibles: chitin tusks along the dome's lower edge, outside the fender
    for sgn in (-1, 1):
        tube('Mandible', [(0.79, sgn * 0.08, 0.665), (0.74, sgn * 0.19, 0.65), (0.62, sgn * 0.26, 0.665), (0.48, sgn * 0.285, 0.71)],
             lambda s: 0.010 + 0.022 * math.sin(math.pi * min(1, s * 1.3)) ** 0.7, ch, sides=10, segs=20, cap0='point', cap1='point', squash=0.6)
    eye_c = Vector((0.815, 0, 0.713))
    # eye: a deep bulging lens so it still reads round from the side, chrome bezel, a thick chitin lid round it
    lens = [(0.066 * math.cos(a), 0.052 * math.sin(a)) for a in (math.pi / 2 * k / 8 for k in range(9))]
    eye = lathe('Eye', lens, M['eye'], 32, closed_prof=False)
    bez = [(0.072 + 0.013 * math.cos(a), 0.012 * math.sin(a)) for a in (TAU * k / 8 for k in range(8))]
    bezel = lathe('Bezel', bez, cr, 40)
    lid = [(0.094 + 0.02 * math.cos(a), -0.012 + 0.025 * math.sin(a)) for a in (TAU * k / 10 for k in range(10))]
    eyelid = lathe('Eyelid', lid, ch, 40)
    for ob in (eye, bezel, eyelid):
        ob.data.transform(Matrix.Rotation(-math.pi / 2, 4, 'Z'))
        ob.data.transform(Matrix.Translation(eye_c))

    # --- seat pad and a short raised tail cowl over the front of the rear wheel
    seat = [
        dict(c=Vector((-0.15, 0, 0.735)), w=0.12, ht=0.03, hb=0.03, e=3),
        dict(c=Vector((-0.30, 0, 0.745)), w=0.145, ht=0.035, hb=0.035, e=3),
        dict(c=Vector((-0.43, 0, 0.75)), w=0.11, ht=0.03, hb=0.03, e=3),
    ]
    loft('Seat', seat, ch, 10, 16, cap0='ngon', cap1='ngon', subsurf=1)
    tail = [
        dict(c=Vector((-0.17, 0, 0.695)), w=0.175, ht=0.04, hb=0.06),
        dict(c=Vector((-0.42, 0, 0.705)), w=0.165, ht=0.06, hb=0.07, ridge=0.02),
        dict(c=Vector((-0.55, 0, 0.715)), w=0.095, ht=0.045, hb=0.05, ridge=0.015),
        dict(c=Vector((-0.65, 0, 0.74)), w=0.015, ht=0.012, hb=0.012),
    ]
    loft('Tail', tail, ch, 14, 14, cap0='ngon', cap1='point', subsurf=1)
    tube('TailTip', [(-0.62, 0, 0.73), (-0.67, 0, 0.75), (-0.71, 0, 0.77)], lambda s: 0.016 * (1 - s) + 0.002, cr, sides=8, segs=6, cap1='point')

    # --- fenders: open shells hugging the tyres
    def fender(name, axle, rad, th0, th1, w, wt0, wt1):
        keys = []
        for i in range(6):
            f = i / 5
            th = th0 + (th1 - th0) * f
            c = axle + Vector((math.cos(th), 0, math.sin(th))) * rad
            ww = w * (wt0 + (1 - wt0) * min(1, f * 3)) * (wt1 + (1 - wt1) * min(1, (1 - f) * 3))
            keys.append(dict(c=c, w=ww, ht=0.02, hb=0.05, a0=math.pi - 0.25, a1=TAU + 0.25))
        loft(name, keys, ch, 14, 10, closed=False, solidify=0.01, subsurf=1)
    fender('FenderF', F_AXLE, F_R + 0.035, math.radians(46), math.radians(124), 0.155, 0.35, 0.7)
    fender('FenderR', R_AXLE, R_R + 0.04, math.radians(42), math.radians(140), 0.17, 0.75, 0.45)

    # --- belly / engine mass
    belly = [
        dict(c=Vector((0.40, 0, 0.25)), w=0.10, ht=0.12, hb=0.13),
        dict(c=Vector((0.12, 0, 0.30)), w=0.15, ht=0.15, hb=0.14, keel=0.02),
        dict(c=Vector((-0.18, 0, 0.35)), w=0.15, ht=0.14, hb=0.13),
        dict(c=Vector((-0.40, 0, 0.48)), w=0.09, ht=0.10, hb=0.08),
    ]
    loft('Belly', belly, ch, 14, 16, cap0='ngon', cap1='ngon', subsurf=1)
    # hip: the dark mass under the seat between the ribcage and the rear wheel
    hip = [
        dict(c=Vector((-0.24, 0, 0.53)), w=0.14, ht=0.13, hb=0.12),
        dict(c=Vector((-0.45, 0, 0.56)), w=0.13, ht=0.11, hb=0.10, keel=0.015),
        dict(c=Vector((-0.64, 0, 0.62)), w=0.06, ht=0.06, hb=0.05),
    ]
    loft('Hip', hip, ch, 10, 14, cap0='ngon', cap1='ngon', subsurf=1)

    # --- neck plates (side "cheeks" running from the head down to the belly)
    for sgn in (-1, 1):
        chest = [
            dict(c=Vector((0.64, sgn * 0.17, 0.66)), w=0.035, ht=0.09, hb=0.09),
            dict(c=Vector((0.57, sgn * 0.20, 0.50)), w=0.045, ht=0.09, hb=0.08),
            dict(c=Vector((0.49, sgn * 0.19, 0.34)), w=0.04, ht=0.075, hb=0.065),
            dict(c=Vector((0.41, sgn * 0.15, 0.22)), w=0.03, ht=0.05, hb=0.05),
        ]
        loft('Chest', chest, ch, 12, 12, cap0='ngon', cap1='ngon', subsurf=1)

    # --- ribcage: spine + glowing ribs + dark core. Ribs bow forward and sweep back at the bottom, front ribs biggest.
    spine0, spine1 = Vector((0.20, 0, 0.745)), Vector((-0.30, 0, 0.58))
    n_ribs = 14
    rib_hh = lambda f: (0.27 - 0.16 * f) / 2
    rib_w = lambda f: 0.19 - 0.07 * f
    core = [dict(c=spine0.lerp(spine1, f) - Vector((0, 0, rib_hh(f) + 0.01)), w=rib_w(f) * 0.55, ht=rib_hh(f) * 0.65, hb=rib_hh(f) * 0.6)
            for f in (0, 0.33, 0.66, 1)]
    loft('Core', core, ch, 10, 12, cap0='ngon', cap1='ngon', subsurf=1)
    # each rib is a near-complete ring round the body (open at the spine): a glowing core inside a translucent glass shell.
    # Spacing, size and tilt vary a little so the cage reads as grown, not machined.
    for i in range(n_ribs):
        jit = math.sin(i * 12.9898) * 0.5
        jit2 = math.sin(i * 78.233 + 1.3) * 0.5
        f = min(max(i / (n_ribs - 1) + 0.25 * jit / (n_ribs - 1), 0), 1)
        p = spine0.lerp(spine1, f)
        w = rib_w(f) + 0.012 * jit2
        hh = rib_hh(f) + 0.012 * jit
        c = p - Vector((0, 0, hh + 0.01))
        bow, sweep = 0.085 + 0.02 * jit2, -0.08
        pts = []
        for k in range(13):
            ph = math.radians(112 + (428 - 112) * k / 12)
            cy, sz = math.cos(ph), math.sin(ph)
            x = bow * cy * cy + sweep * max(0.0, -sz) ** 1.5
            pts.append(c + Vector((x, w * cy, hh * sz)))
        th = 1 - 0.25 * f
        tube('Rib', pts, lambda s, th=th: (0.019 + 0.005 * math.sin(math.pi * s)) * th, M['ribglass'], sides=8, segs=30, cap0='point', cap1='point', squash=0.8)
        tube('RibCore', pts, lambda s, th=th: (0.0105 + 0.0025 * math.sin(math.pi * s)) * th, gl, sides=5, segs=24, cap0='point', cap1='point')
    vert = lambda s: 0.022 + 0.01 * abs(math.sin(math.pi * 14 * s))
    tube('Spine', [spine0 + Vector((0.08, 0, 0.03)), spine0.lerp(spine1, 0.5) + Vector((0, 0, 0.01)), spine1 + Vector((-0.1, 0, 0.0))], vert, bo, sides=10, segs=50)

    # --- front end: forks, clamps, bars, caliper
    for sgn in (-1, 1):
        y = sgn * 0.15
        tube('ForkLower', [steer_pt(-0.02, y), steer_pt(0.36, y)], 0.026, cr, sides=16, segs=6)
        tube('ForkUpper', [steer_pt(0.32, y), steer_pt(0.68, y)], 0.031, cr, sides=16, segs=6)
        tube('AxleClamp', [steer_pt(-0.03, y) + Vector((0.015, 0, -0.02)), steer_pt(0.08, y)], 0.034, ch, sides=12, segs=4)
        cal = steer_pt(0.0, sgn * 0.105) + Vector((-0.07, 0, 0.11))
        tube('Caliper', [cal + Vector((0.04, 0, 0.03)), cal + Vector((-0.04, 0, -0.02))], 0.024, ch, sides=10, segs=4, squash=0.6)
        bar = [Vector((0.48, sgn * 0.06, 0.95)), Vector((0.44, sgn * 0.17, 0.97)), Vector((0.36, sgn * 0.29, 0.948))]
        tube('Bar', bar, 0.012, cr, sides=8, segs=12)
        tube('Grip', [Vector((0.37, sgn * 0.27, 0.95)), Vector((0.32, sgn * 0.37, 0.935))], 0.018, M['tyre'], sides=10, segs=4)
    tube('Clamp', [steer_pt(0.64, -0.17), steer_pt(0.64, 0.17)], 0.02, ch, sides=10, segs=6, squash=0.6)
    tube('Axle', [F_AXLE + Vector((0, -0.17, 0)), F_AXLE + Vector((0, 0.17, 0))], 0.012, cr, sides=8, segs=2)

    # --- rear: bone swingarm, shock, axle
    for sgn in (-1, 1):
        tube('Swingarm', [Vector((-0.18, sgn * 0.10, 0.37)), Vector((-0.48, sgn * 0.13, 0.36)), R_AXLE + Vector((0, sgn * 0.13, 0))],
             lambda s: 0.036 - 0.014 * s + 0.004 * math.sin(s * 9), bo, sides=12, segs=24)
    tube('Shock', [Vector((-0.28, 0, 0.62)), Vector((-0.42, 0, 0.42))], 0.022, cr, sides=10, segs=4)
    tube('AxleR', [R_AXLE + Vector((0, -0.15, 0)), R_AXLE + Vector((0, 0.15, 0))], 0.013, cr, sides=8, segs=2)

    # --- chrome tendons from under the head, sweeping back along the belly
    tendons = [
        ([(0.66, -0.13, 0.66), (0.60, -0.21, 0.48), (0.53, -0.235, 0.28), (0.42, -0.235, 0.17), (0.20, -0.235, 0.22), (-0.15, -0.225, 0.36), (-0.45, -0.20, 0.40), (-0.66, -0.17, 0.40)], 0.026),
        ([(0.62, -0.16, 0.68), (0.56, -0.24, 0.52), (0.48, -0.26, 0.34), (0.36, -0.26, 0.25), (0.10, -0.255, 0.30), (-0.20, -0.245, 0.42), (-0.45, -0.235, 0.45)], 0.022),
        ([(0.70, -0.09, 0.64), (0.65, -0.17, 0.46), (0.58, -0.20, 0.26), (0.48, -0.19, 0.13), (0.25, -0.18, 0.12), (0.0, -0.17, 0.20), (-0.28, -0.16, 0.28)], 0.022),
        ([(0.58, -0.20, 0.66), (0.52, -0.26, 0.54), (0.43, -0.275, 0.42), (0.25, -0.27, 0.36), (0.0, -0.265, 0.40)], 0.017),
    ]
    def ringed(base, length, pitch=0.045, depth=0.13):  # radius with thin raised rings every `pitch` metres
        n = max(1, round(length / pitch))
        return lambda s: base(s) * (1 + depth * abs(math.sin(math.pi * n * s)) ** 10)

    def path_len(ctrl):
        d = catmull(ctrl, 16)
        return sum((b - a).length for a, b in zip(d, d[1:]))

    def helix(ctrl, r_of, r_cable, turns, phase, n=None):
        dense = catmull(ctrl, 16)
        L = sum((b - a).length for a, b in zip(dense, dense[1:]))
        n = n or max(24, int(L / 0.012))
        path, _ = resample(dense, n)
        fr = transport_frames(path)
        out = []
        for i, p in enumerate(path):
            s_ = i / (n - 1)
            a = phase + TAU * turns * s_
            T, N, B = fr[i]
            out.append(p + (N * math.cos(a) + B * math.sin(a)) * (r_of(s_) + r_cable * 0.9))
        return out

    for ti, (ctrl, r) in enumerate(tendons):
        base = lambda s, r=r: r * (1.1 - 0.35 * s)
        L = path_len(ctrl)
        for c in (ctrl, mirror(ctrl)):
            tube('Tendon', c, ringed(base, L), cr, sides=9, segs=int(L / 0.013))
            if ti in (0, 2):  # a fine cable spiralling round the big tendons
                tube('Cable', helix(c, base, 0.005, L / 0.3, ti), 0.005, cr, sides=5)

    # --- the tangle round the engine: vertebral bone tubes, gut-like coils, a finned drum
    bones = [
        [(0.55, -0.13, 0.46), (0.45, -0.175, 0.28), (0.20, -0.19, 0.20), (-0.15, -0.19, 0.30), (-0.50, -0.16, 0.38)],
        [(0.50, -0.10, 0.50), (0.40, -0.15, 0.38), (0.18, -0.16, 0.33), (-0.12, -0.155, 0.37), (-0.40, -0.13, 0.44)],
        [(0.38, -0.20, 0.13), (0.12, -0.215, 0.15), (-0.22, -0.205, 0.25), (-0.55, -0.18, 0.34)],
    ]
    for ctrl in bones:
        L = path_len(ctrl)
        nv = max(4, round(L / 0.035))
        for c in (ctrl, mirror(ctrl)):
            tube('BoneTube', c, lambda s, nv=nv: 0.013 + 0.007 * abs(math.sin(math.pi * nv * s)) ** 0.5, bo, sides=8, segs=int(L / 0.009))
    for sgn in (-1, 1):
        for ph, (z0, amp) in enumerate(((0.33, 0.05), (0.27, 0.035))):
            pts = []
            for k in range(26):
                t = k / 25
                a = TAU * 3.2 * t + ph * 2.0
                pts.append(Vector((0.34 - 0.62 * t, sgn * (0.185 + 0.03 * math.cos(a)), z0 + amp * math.sin(a) + 0.09 * t - 0.03)))
            tube('Gut', pts, lambda s: 0.013 + 0.003 * math.sin(s * 40), cr if ph == 0 else bo, sides=8, segs=90)
        # finned drum (clutch/generator cover, but organic): ridged lathe on the side of the engine
        prof = [(0.0, 0.0), (0.06, 0.0)]
        for k in range(7):
            r = 0.06 + 0.035 * k / 6
            prof += [(r * 0.8, -0.002 - 0.0025 * k), (r * 0.8 + 0.006, -0.003 - 0.0025 * k)]
        prof += [(0.08, -0.02), (0.0, -0.02)]
        drum = lathe('Drum', [(r, y) for r, y in prof], cr, 28, closed_prof=False)
        if sgn > 0:
            drum.data.transform(Matrix.Scale(-1, 4, Vector((0, 1, 0))))
            drum.data.flip_normals()
        drum.data.transform(Matrix.Translation(Vector((-0.04, sgn * 0.235, 0.33))))
        tube('DrumHub', [Vector((-0.04, sgn * 0.21, 0.33)), Vector((-0.04, sgn * 0.262, 0.33))], 0.022, bo, sides=12, segs=2)

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
        ([(0.46, -0.16, 0.20), (0.30, -0.215, 0.21), (0.0, -0.245, 0.30), (-0.32, -0.255, 0.37), (-0.55, -0.245, 0.39), (-0.76, -0.22, 0.41)], 0.032, 0.046),
        ([(0.40, -0.15, 0.32), (0.22, -0.22, 0.33), (-0.05, -0.26, 0.42), (-0.35, -0.27, 0.45), (-0.55, -0.255, 0.47), (-0.72, -0.23, 0.50)], 0.028, 0.040),
    ]
    for ctrl, r0, r1 in pipes:
        for c in (ctrl, mirror(ctrl)):
            tube('Exhaust', c, lambda s, r0=r0, r1=r1: exhaust_r(s, r0, r1), cr, sides=10, segs=76, cap1='ngon')

    # --- glow accent lines along the carapace edge and head cheek
    for sgn in (-1, 1):
        tube('Accent', [dome_at(x)['c'] + Vector((0, sgn * dome_at(x)['w'] * 1.0, -dome_at(x)['hb'] * 0.3)) for x in (0.74, 0.55, 0.32, 0.10)], 0.0045, gl, sides=6)

    # --- kickstand on the left (+Y); the foot touches the ground once the bike leans
    foot_y = 0.30
    foot_z = (0.015 + math.sin(LEAN) * foot_y) / math.cos(LEAN)
    tube('Stand', [Vector((-0.04, 0.13, 0.30)), Vector((-0.12, 0.22, 0.16)), Vector((-0.20, foot_y, foot_z))], (0.016, 0.011), cr, sides=8, segs=10)
    tube('StandFoot', [Vector((-0.23, foot_y, foot_z)), Vector((-0.17, foot_y, foot_z))], 0.015, cr, sides=8, segs=2, squash=0.6)

    # --- drips of black ooze hanging off low edges
    drips = [(0.62, -0.17, 0.685, 0.05), (0.50, -0.19, 0.70, 0.05), (0.38, -0.08, 0.13, 0.07), (0.05, -0.12, 0.17, 0.06),
             (-0.20, -0.13, 0.22, 0.05), (-0.40, -0.10, 0.64, 0.05), (-0.58, -0.06, 0.67, 0.06),
             (0.62, 0.17, 0.685, 0.05), (0.15, 0.12, 0.16, 0.06), (-0.58, 0.06, 0.67, 0.04)]
    for x, y, z, l in drips:
        tube('Drip', [Vector((x, y, z + 0.01)), Vector((x - 0.004, y, z - l * 0.75)), Vector((x - 0.006, y, z - l * 1.5))],
             lambda s: 0.011 * (1 - s) + 0.004 + 0.007 * math.exp(-((s - 0.86) / 0.09) ** 2), ch, sides=6, segs=8, cap1='point')


def add_drops(M, n=320, seed=5):
    """Beads of water on the upward-facing chitin: low hemispheres raycast onto the top surfaces, some drawn out into runs."""
    import random
    from mathutils.bvhtree import BVHTree
    rnd = random.Random(seed)
    dg = bpy.context.evaluated_depsgraph_get()
    tops = [o for o in PARTS if o.name.split('.')[0] in ('Head', 'HeadPlate', 'Brow', 'Tank', 'Tail', 'Seat', 'FenderF', 'FenderR', 'Cheek')]
    trees = [BVHTree.FromObject(o, dg) for o in tops]
    # unit low dome: rings at elevations 0, 30, 60 degrees + apex
    seg = 8
    dome_v = [Vector((math.cos(TAU * j / seg) * math.cos(e), math.sin(TAU * j / seg) * math.cos(e), math.sin(e) - 0.15))
              for e in (0.0, math.radians(32), math.radians(62)) for j in range(seg)] + [Vector((0, 0, 0.85))]
    dome_f = [(r * seg + j, r * seg + (j + 1) % seg, (r + 1) * seg + (j + 1) % seg, (r + 1) * seg + j) for r in range(2) for j in range(seg)]
    dome_f += [(2 * seg + j, 2 * seg + (j + 1) % seg, 3 * seg) for j in range(seg)]
    verts, faces = [], []
    placed = 0
    tries = 0
    while placed < n and tries < n * 20:
        tries += 1
        x, y = rnd.uniform(-1.0, 1.1), rnd.uniform(-0.3, 0.3)
        if abs(x - BUTTON_X) < BUTTON_LEN / 2 + 0.02 and abs(y) < BUTTON_WID / 2 + 0.02:
            continue
        best = None
        for t in trees:
            hit = t.ray_cast(Vector((x, y, 2.0)), Vector((0, 0, -1)))
            if hit[0] is not None and (best is None or hit[0].z > best[0].z):
                best = hit
        if best is None or best[1].z < 0.3:
            continue
        loc, nrm = best[0], best[1].normalized()
        r = 0.0025 + 0.0065 * rnd.random() ** 2.0
        down = (Vector((0, 0, -1)) - nrm * (-nrm.z)).normalized() if abs(nrm.z) < 0.999 else Vector((1, 0, 0))
        side = nrm.cross(down).normalized()
        run = 1.0 + (2.2 * rnd.random() if rnd.random() < 0.3 and abs(nrm.z) < 0.95 else 0.0)
        basis = Matrix((side, down, nrm)).transposed()  # columns: x=side, y=down slope, z=normal
        mat = Matrix.Translation(loc) @ basis.to_4x4() @ Matrix.Diagonal((r, r * run, r * 0.55, 1))
        o = len(verts)
        verts += [mat @ v for v in dome_v]
        faces += [tuple(o + i for i in f) for f in dome_f]
        placed += 1
    ob = new_obj('Drops', verts, faces, M['chitin'])
    return ob


# ---------------------------------------------------------------- the "get on" button
BUTTON_X, BUTTON_LEN, BUTTON_WID = 0.405, 0.24, 0.11  # centre (bike-local x) and size of the pill on the dome
ANCHORS = {}


def build_button(M):
    """BikeButton: a pill with a raised lip on top of the dome between the grips, conformed to the carapace;
    BikeButtonGlyph: three forward chevrons lying on it; ButtonCentre and RiderEye empties.
    Returns the new objects (not part of the joined Bike mesh)."""
    import numpy as np
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    tops = [o for o in PARTS if o.name.split('.')[0] in ('Head', 'Tank', 'Brow', 'Cheek')]
    trees = [BVHTree.FromObject(o, dg) for o in tops]

    def hit_z(x, y):
        best = None
        for t in trees:
            h = t.ray_cast(Vector((x, y, 2.0)), Vector((0, 0, -1)))
            if h[0] is not None and (best is None or h[0].z > best):
                best = h[0].z
        return best

    # fit a smooth quadric to the carapace under the footprint, then lift it to clear every plate edge by 3 mm
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
    print('BUTTON fit lift (m):', round(lift, 4), 'carapace z at centre:', round(coef[0], 4))

    def base(x, y):  # point on the conformed base surface and its normal
        dx = x - BUTTON_X
        c0, c1, c2, c3, c4, c5 = coef
        z = c0 + c1 * dx + c2 * y + c3 * dx * dx + c4 * dx * y + c5 * y * y + lift
        n = Vector((-(c1 + 2 * c3 * dx + c4 * y), -(c2 + c4 * dx + 2 * c5 * y), 1)).normalized()
        return Vector((x, y, z)), n

    # stadium outline, inset in rings: skirt (tucked under), lip ramp, lip top, back down to a slightly recessed face
    straight = a - r
    n_cap, n_side = 14, 10

    def outline(rr):
        pts = []
        for k in range(n_cap):  # front cap (+x), from +y round to -y
            t = math.pi / 2 - math.pi * k / n_cap
            pts.append((BUTTON_X + straight + rr * math.cos(t), rr * math.sin(t)))
        for k in range(n_side):  # right side, front to back
            pts.append((BUTTON_X + straight - 2 * straight * k / n_side, -rr))
        for k in range(n_cap):  # back cap
            t = -math.pi / 2 - math.pi * k / n_cap
            pts.append((BUTTON_X - straight + rr * math.cos(t), rr * math.sin(t)))
        for k in range(n_side):  # left side, back to front
            pts.append((BUTTON_X - straight + 2 * straight * k / n_side, rr))
        return pts
    profile = [(-0.0015, -0.004), (0.0, 0.0), (0.0025, 0.0035), (0.0055, 0.0055), (0.009, 0.005), (0.0125, 0.0028), (0.016, 0.0022)]
    d = 0.016
    while r - d > 0.012:
        d += 0.008
        profile.append((d, 0.0022))
    profile.append((r, 0.0022))  # the last ring collapses onto the centre line; welded below, so no long n-gon on the face
    FACE_H = 0.0022
    rings = []
    for inset, h in profile:
        ring = []
        for x, y in outline(r - inset):
            p, n = base(x, y)
            ring.append(p + n * h)
        rings.append(ring)
    btn = rings_mesh('BikeButton', rings, M['button'])
    PARTS.remove(btn)
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

    # three nested chevrons pointing forward (+x), centred on the pill; flat 0.6 mm plates, conformed like the face
    W_, L_, STROKE, PITCH = 0.036, 0.030, 0.0062, 0.031  # arm half-span, arm length along x, stroke (perpendicular), spacing
    d_ = STROKE * math.hypot(L_, W_) / W_  # stroke measured along x
    span = 2 * PITCH + L_ + d_
    bm = bmesh.new()
    for k in range(3):
        tip = BUTTON_X + span / 2 - k * PITCH
        outline = [(tip, 0), (tip - L_, W_), (tip - L_ - d_, W_), (tip - d_, 0), (tip - L_ - d_, -W_), (tip - L_, -W_)]
        face = bm.faces.new([bm.verts.new((u, v, 0.0)) for u, v in outline])
        ext = bmesh.ops.extrude_face_region(bm, geom=[face])
        bmesh.ops.translate(bm, verts=[e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)], vec=(0, 0, 0.0006))
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method='BEAUTY', ngon_method='BEAUTY')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    gme = bpy.data.meshes.new('BikeButtonGlyph')
    bm.to_mesh(gme)
    bm.free()
    for v in gme.vertices:
        x, y, tz = v.co.x, v.co.y, v.co.z
        p, n = base(x, y)
        v.co = p + n * (FACE_H + 0.0015 + tz)
    gme.materials.append(M['glyph'])
    gme.shade_flat()
    glyph = bpy.data.objects.new('BikeButtonGlyph', gme)
    bpy.context.scene.collection.objects.link(glyph)
    print('BUTTON chevrons: span along x', round(span, 4), 'width', 2 * W_, 'stroke', STROKE)

    # anchors. Blender axes: ButtonCentre +Z = surface normal (glTF/three: +Y). RiderEye +Y = view direction, +Z = up
    # (glTF/three: -Z view, +Y up, so its world transform can be copied straight onto a camera).
    pc, nc = base(BUTTON_X, 0.0)
    pc = pc + nc * FACE_H
    fx = (Vector((1, 0, 0)) - nc * nc.x).normalized()
    centre = bpy.data.objects.new('ButtonCentre', None)
    centre.empty_display_type, centre.empty_display_size = 'ARROWS', 0.05
    centre.matrix_world = Matrix.Translation(pc) @ Matrix((fx, nc.cross(fx), nc)).transposed().to_4x4()
    centre['button_size_m'] = [BUTTON_LEN, BUTTON_WID]
    seat_top = 0.78
    eye_p = Vector((0.08, 0.0, seat_top + 0.74))
    pitch = math.radians(8)
    fwd = Vector((math.cos(pitch), 0, -math.sin(pitch)))
    up = Vector((math.sin(pitch), 0, math.cos(pitch)))
    eye = bpy.data.objects.new('RiderEye', None)
    eye.empty_display_type, eye.empty_display_size = 'ARROWS', 0.08
    eye.matrix_world = Matrix.Translation(eye_p) @ Matrix((fwd.cross(up), fwd, up)).transposed().to_4x4()
    eye['view'] = 'local +Y forward in Blender; glTF/three local -Z forward, +Y up'
    for ob in (centre, eye):
        bpy.context.scene.collection.objects.link(ob)
    ANCHORS.update(centre=pc.copy(), normal=nc.copy(), eye=eye_p.copy())
    return [btn, glyph, centre, eye]


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
        # solved so the tyres and ground contacts land on the concept's traced ones (art/reference/concept-bike-guides.json)
        'concept': add_camera(col, 'ConceptCam', (1.662, -1.962, 1.027), (1.265, -0.857, 0.84), lens=24),
        # close-up of the button from the rider's eye (RiderEye), aimed at ButtonCentre
        'rider': add_camera(col, 'RiderCam', bpy.data.objects['RiderEye'].matrix_world.translation.copy(),
                            bpy.data.objects['ButtonCentre'].matrix_world.translation.copy(), lens=50),
    }
    suffix = f'-{TAG}' if TAG else ''
    for key, cam in cams.items():
        if VIEWS and key not in VIEWS:
            continue
        scene.camera = cam
        scene.render.resolution_x, scene.render.resolution_y = (1280, 720) if key == 'concept' else (1920, 1080)
        scene.render.filepath = os.path.join(RENDER_DIR, f'bike-{key}{suffix}.png')
        bpy.ops.render.render(write_still=True)
        print('rendered', scene.render.filepath)
    scene.camera = cams['hero']


# ---------------------------------------------------------------- main
def main():
    scene = reset()
    M = make_materials()

    build_body(M)
    add_drops(M)
    extras = build_button(M)
    per = {}
    for o in PARTS:
        per[o.name.split('.')[0]] = per.get(o.name.split('.')[0], 0) + tri_count(o)
    print('PARTS', sorted(per.items(), key=lambda kv: -kv[1]))
    body = join('Bike', PARTS)
    PARTS.clear()

    wf = build_wheel('WheelFront', F_R, 0.22, M, front=True)
    wr = build_wheel('WheelRear', R_R, 0.25, M, front=False)
    for w, axle in ((wf, F_AXLE), (wr, R_AXLE)):
        w.parent = body
        w.matrix_parent_inverse = Matrix.Identity(4)
        w.location = axle

    for ob in extras:  # built in bike-local coordinates
        mw = ob.matrix_world.copy()
        ob.parent = body
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.matrix_basis = mw
    body.location = (0, 0, 0)
    body.rotation_euler = (-LEAN, 0, 0)  # lean toward +Y onto the kickstand

    counts = {o.name: tri_count(o) for o in (body, wf, wr, *[e for e in extras if e.type == 'MESH'])}
    print('TRIANGLES', counts, 'total', sum(counts.values()))

    col = setup_render(scene)
    scene.camera = None
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)

    bpy.ops.object.select_all(action='DESELECT')
    for o in (body, wf, wr, *extras):
        o.select_set(True)
    os.makedirs(os.path.dirname(GLB_OUT), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=GLB_OUT, export_format='GLB', use_selection=True, export_apply=True, export_yup=True,
                              export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
                              export_draco_texcoord_quantization=14, export_image_format='WEBP', export_image_quality=88,
                              export_cameras=False, export_lights=False, export_extras=True)
    print('GLB', GLB_OUT, os.path.getsize(GLB_OUT))

    if DO_RENDER:
        render_views(scene, col)
        bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)


main()
