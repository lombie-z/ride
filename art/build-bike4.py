"""Desert bike, the fourth hero bike: a heavy, rugged biotech machine (art/reference/concept-desert.webp, the bike lower
right, a rear three-quarter parked on its kickstand).

Builds the bike from scratch, saves art/bike4.blend and exports public/models/bike4.glb (Draco).
Run:   blender --background --factory-startup --python art/build-bike4.py
Review renders into art/renders/bike4-*.png (concept, rider, riderdash, side, hero, rear, top):
       blender --background --factory-startup --python art/build-bike4.py -- --render [--tag NAME] [--views concept,side]

Same frame as bike.glb (art/build-bike.py) so the site can swap them in place: metres, Z up, front toward +X, ground
z=0, origin on the ground midway between the contacts, wheelbase 1.56 m, the same axles, the root rolled 5 deg toward
+Y onto the kickstand. Objects: Bike4 (body), Wheel4Front / Wheel4Rear (children, origin on the axle, spin about local
Y), Bike4Button + Bike4ButtonGlyph (the throttle pill on the tank, three forward chevrons), Bike4Dash (the small CRT
screen, UV 0-1, u right and v up from the rider's seat), and the ButtonCentre / RiderEye empties at bike.glb's exact
bike-local transforms.

The tank under the slingshot track is conformed to bike.glb's (art/align-bike4/bike1-tank.json, sampled by
art/align-bike4/dump_tank.py), and the profile actually built is stored on ButtonCentre: TRACK_D (m back along the
bike), TRACK_CENTRE and TRACK_SIDE (the tank surface's height along ButtonCentre's normal, on the centre line and at
+-0.066 m, the button meshes excluded).

The concept fit (art/align-bike4/): concept-bike4-guides.json traces the concept's parts, fit_camera.py fits
ConceptCam4 to the tyres/contacts/bars, backproject.py reads the concept's parts back onto bike-local planes, and
compare.py overlays the guides on a ConceptCam4 render.

Materials (plain Principled BSDFs, the site tunes them): Bike4Armour (gunmetal, a small scoured-paint texture),
Bike4Rust (a small rust texture), Bike4Glass (alpha-blended, set depthWrite on the site), Bike4Fluid (emissive green),
Bike4Vein (dark red, inside the glass), Bike4Tube (emissive ribbed green glass), Bike4Hose, Bike4Tyre, Bike4Tail
(emissive red), Bike4Dash, Bike4Button, Bike4ButtonGlyph (emissive hot amber). Bike4 and the wheels carry baked
ambient occlusion (with a faint warm sand tint) in their vertex colours (COLOR_0, per vertex, multiplied into the base
colour by three); the grime, scratches and rust blooms live in the two 256 px textures (exported as JPEG). Pass
--nobake to skip the AO bake for quick geometry checks.
"""
import json
import math
import os
import random
import sys
import tempfile

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector, noise
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
BLEND_OUT = os.path.join(HERE, 'bike4.blend')
GLB_OUT = os.path.join(ROOT, 'public', 'models', 'bike4.glb')
RENDER_DIR = os.path.join(HERE, 'renders')
ALIGN = os.path.join(HERE, 'align-bike4')

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
F_W, R_W = 0.24, 0.36  # tyre widths (art/align-bike4/fit_camera.py uses the same): a chunky wide rear
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
TRACK_D = [-0.16, -0.12, -0.08, -0.04, 0, 0.04, 0.08, 0.12, 0.16, 0.2, 0.24]
TRACK_RAIL = 0.066
DASH_C = Vector((0.645, 0.0, 1.03))  # CRT screen centre
# the drive side (+Y, as the concept): the rear sprocket and disc sit outboard of the wide tyre, the swingarm outside them
R_SPROCKET_Y, R_DISC_Y, SWING_Y = 0.20, 0.224, 0.252
F_DISC_Y, FORK_Y = 0.118, 0.165


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
               alpha=1.0, transmission=0.0, image=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*base, 1)
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = spec
    b.inputs['Coat Weight'].default_value = coat
    b.inputs['Coat Roughness'].default_value = coat_rough
    b.inputs['Transmission Weight'].default_value = transmission
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1)
        b.inputs['Emission Strength'].default_value = emit_strength
    if alpha < 1.0:
        b.inputs['Alpha'].default_value = alpha
        m.surface_render_method = 'BLENDED'
    if image is not None:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = image
        tex.interpolation = 'Linear'
        nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
    m.diffuse_color = (*base, 1)
    return m


def fbm(x, y, octaves=5, seed=0):
    v, a, f = 0.0, 0.5, 1.0
    for o in range(octaves):
        v += a * noise.noise(Vector((x * f + seed * 17.1, y * f - seed * 9.3, o * 3.7 + seed)))
        a *= 0.5
        f *= 2.03
    return v


def make_textures():
    """Two 256 px tiling-ish textures, generated: scoured gunmetal paint for the armour (scratches, pits, rust bleeding
    from them, sand in the low spots) and rust for the rust parts. Packed into the .blend; exported as JPEG."""
    import numpy as np
    n = 256
    xs = np.linspace(0, 1, n, endpoint=False)

    def field(scale, octaves, seed):
        out = np.zeros((n, n))
        for j, yv in enumerate(xs):
            for i, xv in enumerate(xs):
                # sample on a torus so the texture tiles
                a, b = xv * TAU, yv * TAU
                p = Vector((math.cos(a) * scale, math.sin(a) * scale, math.cos(b) * scale + seed * 13.0))
                q = math.sin(b) * scale
                v, amp, f = 0.0, 0.5, 1.0
                for o in range(octaves):
                    v += amp * noise.noise(Vector((p.x * f, p.y * f, p.z * f + q * f * 0.7 + o * 5.1)))
                    amp *= 0.5
                    f *= 2.0
                out[j, i] = v
        return out

    rng = np.random.default_rng(4)
    big = field(1.6, 4, 1)
    fine = field(6.0, 3, 2)
    # armour: gunmetal paint, scoured lighter on the high spots, scratches, rust blooms in the pits
    base = np.array(srgb('#3e4142'))
    scour = np.array(srgb('#66625a'))
    rust = np.array(srgb('#4e2a16'))
    dust = np.array(srgb('#6e5236'))
    t_scour = np.clip((big * 0.9 + fine * 0.6 + 0.05) * 2.2, 0, 1) ** 2 * 0.4
    t_rust = np.clip((fine * 1.2 - big * 0.4 - 0.22) * 2.5, 0, 1) * 0.75
    t_dust = np.clip((-big * 1.0 - 0.15) * 2.0, 0, 1) * 0.35
    img = base[None, None] * (1 - t_scour[..., None]) + scour[None, None] * t_scour[..., None]
    img = img * (1 - t_rust[..., None]) + rust[None, None] * t_rust[..., None]
    img = img * (1 - t_dust[..., None]) + dust[None, None] * t_dust[..., None]
    # scratches: short bright strokes, mostly along u (the direction the sand blew)
    for _ in range(220):
        x0, y0 = rng.integers(0, n, 2)
        L = rng.integers(6, 40)
        ang = rng.normal(0, 0.35)
        br = rng.uniform(0.08, 0.25)
        for k in range(L):
            x = int(x0 + k * math.cos(ang)) % n
            y = int(y0 + k * math.sin(ang)) % n
            img[y, x] = img[y, x] * (1 - br) + scour * br
    armour = img
    # rust: orange to deep brown, flaky, with darker pits
    r1, r2, r3 = np.array(srgb('#5e3016')), np.array(srgb('#33190d')), np.array(srgb('#7c4420'))
    t = np.clip(big * 0.8 + fine * 0.6 + 0.45, 0, 1)[..., None]
    img = r2 * (1 - t) + r1 * t
    flake = np.clip((fine * 1.6 - 0.1) * 2.5, 0, 1)[..., None] * 0.35
    img = img * (1 - flake) + r3 * flake
    pits = np.clip((-fine * 1.5 - 0.25) * 3, 0, 1)[..., None] * 0.6
    img = img * (1 - pits) + np.array(srgb('#22100a')) * pits
    rustimg = img

    out = {}
    for name, arr in (('Bike4ArmourTex', armour), ('Bike4RustTex', rustimg)):
        im = bpy.data.images.new(name, n, n, alpha=False)
        px = np.ones((n, n, 4), dtype=np.float32)
        lin = np.clip(arr, 0, 1)
        px[..., :3] = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)  # byte images hold sRGB
        im.pixels.foreach_set(px.ravel())
        im.update()
        im.filepath_raw = os.path.join(tempfile.gettempdir(), name + '.png')
        im.file_format = 'PNG'
        im.save()
        im.pack()
        out[name] = im
    return out


def make_materials():
    tex = make_textures()
    M = {
        'armour': principled('Bike4Armour', srgb('#55585a'), metallic=0.6, rough=0.42, image=tex['Bike4ArmourTex']),
        'rust': principled('Bike4Rust', srgb('#4e2814'), metallic=0.3, rough=0.8, image=tex['Bike4RustTex']),
        'glass': principled('Bike4Glass', (0.85, 0.95, 0.88), rough=0.03, coat=1.0, coat_rough=0.02, transmission=1.0, alpha=0.2),
        'fluid': principled('Bike4Fluid', srgb('#4f7a1e'), rough=0.2, emit=srgb('#86d634'), emit_strength=0.32),
        'vein': principled('Bike4Vein', srgb('#5a0b0d'), rough=0.35, coat=0.6, coat_rough=0.1),
        'tube': principled('Bike4Tube', srgb('#8aff5a'), rough=0.08, coat=1.0, coat_rough=0.02, emit=srgb('#62ff2a'), emit_strength=1.2),
        'hose': principled('Bike4Hose', srgb('#16130f'), rough=0.55, coat=0.2, coat_rough=0.3),
        'tyre': principled('Bike4Tyre', srgb('#1c1915'), rough=0.88, spec=0.3),
        'tail': principled('Bike4Tail', srgb('#5a0804'), rough=0.2, emit=srgb('#ff2a12'), emit_strength=10.0),
        # the CRT: dark green glass that glows; the site draws the speed and logo into it
        'dash': principled('Bike4Dash', (0.01, 0.03, 0.012), rough=0.08, coat=1.0, coat_rough=0.02, emit=srgb('#2cff5a'), emit_strength=0.6),
        # the throttle pill: hot amber glass for the zone's flame boost; the glyph brighter. The site drives both.
        'button': principled('Bike4Button', srgb('#ff8a26'), rough=0.06, coat=1.0, coat_rough=0.02, emit=srgb('#ff7a1a'), emit_strength=1.0),
        'glyph': principled('Bike4ButtonGlyph', srgb('#ffe2a0'), rough=0.3, emit=srgb('#ffc060'), emit_strength=4.0),
    }
    return M


# ---------------------------------------------------------------- curve maths (as art/build-bike2.py)
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
TILE = 0.35


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


def path_length(ctrl):
    d = catmull(ctrl, 16)
    return sum((b - a).length for a, b in zip(d, d[1:]))


def hose(name, ctrl, r, mat, pitch=0.018, sides=6, track=True):
    """Corrugated hose: the radius ribbed every `pitch` metres."""
    L = path_length(ctrl)
    n = max(4, int(L / pitch))
    return tube(name, ctrl, lambda s: r * (1 + 0.16 * abs(math.sin(math.pi * n * s)) ** 3), mat, sides=sides,
                segs=max(12, n * 3), track=track)


def loft(name, keys, mat, n_along, n_around, side=Y, closed=True, cap0=None, cap1=None, solidify=0.0, subsurf=1, track=True):
    """Superellipse sections swept through keyed centres. Keys: c, w, ht, hb, e, eb, a0, a1, roll.
    Keys run front to back (toward -X): the section's up is side x tangent (+Z there), so ht is the top."""
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
        up = side.cross(T).normalized()
        sd = T.cross(up).normalized()
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


AXIS_X = Matrix.Rotation(-math.pi / 2, 4, 'Z')  # lathe's Y axis -> X


def lathe_x(name, prof, mat, segs, at, closed_prof=True, track=True, mirror_y=False):
    """Lathe about the bike's X axis through `at`: profile (r, x-offset)."""
    ob = lathe(name, prof, mat, segs, closed_prof=closed_prof, track=track)
    ob.data.transform(Matrix.Translation(Vector(at)) @ AXIS_X)
    return ob


def lathe_y(name, prof, mat, segs, at, track=True):
    ob = lathe(name, prof, mat, segs, closed_prof=False, track=track)
    ob.data.transform(Matrix.Translation(Vector(at)))
    return ob


def ellipsoid(name, c, radii, mat, rot=(0, 0, 0), segs=24, rings=12, track=True):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0)
    bm.to_mesh(me)
    bm.free()
    me.transform(Matrix.Translation(Vector(c)) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Diagonal((*radii, 1)))
    me.shade_smooth()
    me.uv_layers.new(name='UVMap')
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    if track:
        PARTS.append(ob)
    return ob


def box(name, centre, size, mat, rot=Matrix.Identity(3), bevel=0.0, track=True):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=2, affect='EDGES', profile=0.5)
    bm.to_mesh(me)
    bm.free()
    me.transform(Matrix.Translation(Vector(centre)) @ rot.to_4x4())
    me.uv_layers.new(name='UVMap')
    me.shade_flat()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    if track:
        PARTS.append(ob)
    return ob


def mirror(ctrl):
    return [Vector((p[0], -p[1], p[2])) for p in ctrl]


def mirror_obj(ob, name=None):
    me = ob.data.copy()
    me.transform(Matrix.Scale(-1, 4, Vector((0, 1, 0))))
    me.flip_normals()
    o2 = bpy.data.objects.new(name or ob.name, me)
    bpy.context.scene.collection.objects.link(o2)
    if ob in PARTS:
        PARTS.append(o2)
    return o2


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


def key(x, z, w, ht, hb, y=0.0, **kw):
    return dict(c=Vector((x, y, z)), w=w, ht=ht, hb=hb, **kw)


def keyed_at(keys, x):
    """Section (centre, w, ht, hb, e) of a front-to-back loft at bike x, by bisection on its centre curve."""
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if hermite(keys, mid, 'c').x > x:
            lo = mid
        else:
            hi = mid
    t = (lo + hi) / 2
    return hermite(keys, t, 'c'), hermite(keys, t, 'w'), hermite(keys, t, 'ht'), hermite(keys, t, 'hb'), hermite(keys, t, 'e', 2.5)


class Studs:
    """Many small identical domes (rivets, bolt heads) collected into one mesh per material."""

    def __init__(self):
        self.verts, self.faces = {}, {}

    def add(self, p, n, mat, r=0.0055, h=0.0035, sides=5):
        V = self.verts.setdefault(mat, [])
        F = self.faces.setdefault(mat, [])
        n = Vector(n).normalized()
        a = Vector((1, 0, 0)) if abs(n.x) < 0.9 else Vector((0, 1, 0))
        u = n.cross(a).normalized()
        v = n.cross(u)
        base = len(V)
        prof = [(r, -0.001), (r * 0.75, h * 0.75)]
        for rr, hh in prof:
            for k in range(sides):
                ph = TAU * k / sides
                V.append(Vector(p) + n * hh + (u * math.cos(ph) + v * math.sin(ph)) * rr)
        V.append(Vector(p) + n * h)
        top = len(V) - 1
        for i in range(len(prof) - 1):
            for k in range(sides):
                k2 = (k + 1) % sides
                F.append((base + i * sides + k, base + i * sides + k2, base + (i + 1) * sides + k2, base + (i + 1) * sides + k))
        last = base + (len(prof) - 1) * sides
        for k in range(sides):
            F.append((last + k, last + (k + 1) % sides, top))

    def objects(self, name):
        out = []
        for mat, V in self.verts.items():
            ob = new_obj(name, V, self.faces[mat], mat, smooth=True)
            out.append(ob)
        return out


STUDS = Studs()


def rivet_line(trees, pts, outward, mat, spacing=0.035, r=0.0055, lift=0.0):
    """Rivets along a polyline, each dropped onto the nearest surface by casting back along `outward` (a vector or a
    function of the point)."""
    dense = catmull(pts, 12) if len(pts) > 2 else [Vector(pts[0]).lerp(Vector(pts[1]), i / 12) for i in range(13)]
    path, L = resample(dense, max(2, int(path_length(pts) / spacing) + 1))
    for p in path:
        o = outward(p) if callable(outward) else Vector(outward)
        h = cast(trees, p + o * 0.12, -o)
        if h and h[3] < 0.2:
            STUDS.add(h[0] + h[1] * lift, h[1], mat, r=r)


# ---------------------------------------------------------------- wheels
def tyre(name, radius, width, rim_r, mat, n_around, n_prof, grooves, chevron, depth=0.006):
    """A chunky tyre: squarish superellipse section revolved about Y, with a cut tread (diagonal grooves from the centre
    rib out to each shoulder)."""
    hw = width / 2
    rm, hr = (radius + rim_r) / 2, (radius - rim_r) / 2
    prof = section(hw, hr, hr, n_prof, e=3.4, eb=2.4, closed=True)
    rings = []
    for k in range(n_around):
        ph = TAU * k / n_around
        ring = []
        for u, v in prof:
            rr = rm + v
            g = 0.0
            if v > hr * 0.55:  # tread band
                a = abs(u) / hw
                if 0.1 < a < 0.97:
                    P = ph * grooves / TAU + chevron * a + (0.5 if u < 0 else 0.0)
                    f = P - math.floor(P)
                    g = smoothstep(0.0, 0.06, f) * (1 - smoothstep(0.22, 0.30, f)) * smoothstep(0.1, 0.2, a) * (1 - smoothstep(0.88, 0.97, a))
                    g *= smoothstep(hr * 0.55, hr * 0.8, v)
            rr -= depth * g
            ring.append(Vector((rr * math.cos(ph), u, rr * math.sin(ph))))
        rings.append(ring)
    return rings_mesh(name, rings, mat, closed_ring=True, closed_along=True)


def build_wheel(name, radius, width, M, front):
    global PARTS
    saved, PARTS = PARTS, []
    hw = width / 2
    rim_r = 0.214
    if front:
        tyre(name + 'Tyre', radius, width, rim_r, M['tyre'], 132, 26, grooves=22, chevron=0.55)
    else:
        tyre(name + 'Tyre', radius, width, rim_r, M['tyre'], 156, 30, grooves=26, chevron=0.7, depth=0.007)
    # heavy dished disc wheel: rusted rim lip, a dark armour face dished in to a big hub
    yl = hw * 0.80
    prof = [(rim_r + 0.012, yl + 0.004), (rim_r + 0.004, yl + 0.012), (rim_r - 0.012, yl + 0.008), (rim_r - 0.02, yl - 0.01)]
    ob = lathe(name + 'Lip', prof, M['rust'], 72, closed_prof=False)
    ob2 = lathe(name + 'Lip', [(r, -y) for r, y in prof], M['rust'], 72, closed_prof=False)
    ob2.data.flip_normals()
    for sgn in (-1, 1):
        face = [(rim_r - 0.016, sgn * (yl - 0.012)), (rim_r - 0.04, sgn * (yl - 0.03)), (0.15, sgn * (yl * 0.55)),
                (0.095, sgn * (yl * 0.52)), (0.085, sgn * (yl * 0.62)), (0.06, sgn * (yl * 0.72)), (0.0, sgn * (yl * 0.74))]
        f = lathe(name + 'Face', face, M['armour'], 48, closed_prof=False)
        if sgn < 0:
            f.data.flip_normals()
        # a ring of bolt heads round the hub and a second on the dish
        for k in range(8):
            ph = TAU * k / 8 + 0.2
            STUDS_W.add(Vector((0.072 * math.cos(ph), sgn * yl * 0.69, 0.072 * math.sin(ph))), Vector((0, sgn, 0)), M['rust'], r=0.0075, h=0.006)
        for k in range(14):
            ph = TAU * k / 14
            rr = rim_r - 0.045
            STUDS_W.add(Vector((rr * math.cos(ph), sgn * (yl - 0.036), rr * math.sin(ph))), Vector((0, sgn, -0)), M['armour'], r=0.0055, h=0.004)
    # axle and nuts, out past the fork legs / swingarm
    ny = (FORK_Y if front else SWING_Y) + 0.03
    tube(name + 'Axle', [Vector((0, -ny, 0)), Vector((0, ny, 0))], 0.016, M['rust'], sides=8, segs=2)
    for sgn in (-1, 1):
        lathe_y(name + 'Nut', [(0.0, sgn * (ny + 0.012)), (0.024, sgn * (ny + 0.012)), (0.027, sgn * ny), (0.027, sgn * (ny - 0.014))], M['rust'], 6, (0, 0, 0))
    # brake disc (and on the rear, the chain sprocket inboard of it), on the +Y (kickstand / chain) side, as the concept
    dy = F_DISC_Y if front else R_DISC_Y
    disc_r0, disc_r1 = (0.075, 0.135) if front else (0.07, 0.115)
    prof = [(disc_r0, dy - 0.003), (disc_r1, dy - 0.003), (disc_r1, dy + 0.003), (disc_r0, dy + 0.003)]
    lathe(name + 'Disc', prof, M['armour'], 64)
    nh = 18 if front else 14
    for k in range(nh):
        ph = TAU * k / nh
        rr = (disc_r0 + disc_r1) / 2 + (0.012 if k % 2 else -0.008)
        STUDS_W.add(Vector((rr * math.cos(ph), dy + 0.002, rr * math.sin(ph))), Vector((0, 1, 0)), M['hose'], r=0.0055, h=0.0012, sides=6)
    tube(name + 'Carrier', [Vector((0, yl * 0.7, 0)), Vector((0, dy, 0))], 0.07, M['armour'], sides=16, segs=2)
    if not front:
        sy = R_SPROCKET_Y
        teeth = 38
        bm = bmesh.new()
        ol = []
        for k in range(teeth * 4):
            ph = TAU * k / (teeth * 4)
            rr = 0.138 if (k % 4) in (1, 2) else 0.126
            ol.append((rr * math.cos(ph), rr * math.sin(ph)))
        f = bm.faces.new([bm.verts.new((x, sy - 0.003, z)) for x, z in ol])
        ext = bmesh.ops.extrude_face_region(bm, geom=[f])
        bmesh.ops.translate(bm, verts=[e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)], vec=(0, 0.006, 0))
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new(name + 'Sprocket')
        bm.to_mesh(me)
        bm.free()
        me.uv_layers.new(name='UVMap')
        me.materials.append(M['rust'])
        sp = bpy.data.objects.new(name + 'Sprocket', me)
        bpy.context.scene.collection.objects.link(sp)
        PARTS.append(sp)
        tube(name + 'SprocketHub', [Vector((0, yl * 0.7, 0)), Vector((0, sy, 0))], 0.09, M['armour'], sides=16, segs=2)
        # lightening holes in the sprocket: dark dots
        for k in range(6):
            ph = TAU * k / 6
            STUDS_W.add(Vector((0.105 * math.cos(ph), sy + 0.003, 0.105 * math.sin(ph))), Vector((0, 1, 0)), M['hose'], r=0.014, h=0.001, sides=8)
    for ob in STUDS_W.objects(name + 'Studs'):
        pass
    STUDS_W.verts.clear()
    STUDS_W.faces.clear()
    wheel = join(name, PARTS)
    PARTS = saved
    return wheel


STUDS_W = Studs()


# ---------------------------------------------------------------- the body
# Tank: a big rounded drum, its top under the throttle track conformed to bike.glb's (conform_tank).
TANK = [
    key(0.745, 0.872, 0.012, 0.012, 0.012, e=2.2),
    key(0.715, 0.865, 0.085, 0.055, 0.07, e=2.2),
    key(0.66, 0.84, 0.145, 0.095, 0.13, e=2.2),
    key(0.565, 0.818, 0.178, 0.134, 0.16, e=2.2),
    key(0.405, 0.826, 0.19, 0.142, 0.18, e=2.2),
    key(0.25, 0.817, 0.19, 0.138, 0.18, e=2.2),
    key(0.165, 0.803, 0.185, 0.132, 0.17, e=2.2),
    key(0.05, 0.783, 0.17, 0.12, 0.15, e=2.3),
    key(-0.08, 0.768, 0.13, 0.08, 0.10, e=2.4),
    key(-0.16, 0.762, 0.03, 0.02, 0.03, e=2.4),
]
# The tail: a long armoured cowl rising behind the seat to a wide flat top, hooking down at its end over the light.
TAIL = [
    key(-0.18, 0.775, 0.08, 0.03, 0.05, e=2.6),
    key(-0.30, 0.780, 0.15, 0.05, 0.10, e=2.6),
    key(-0.43, 0.790, 0.185, 0.07, 0.135, e=2.8),
    key(-0.57, 0.802, 0.195, 0.085, 0.12, e=3.0),
    key(-0.70, 0.812, 0.195, 0.085, 0.105, e=3.0),
    key(-0.80, 0.815, 0.19, 0.08, 0.095, e=3.0),
    key(-0.855, 0.810, 0.18, 0.07, 0.085, e=3.0),
    key(-0.885, 0.800, 0.17, 0.06, 0.075, e=3.2),
]
TAIL_END = -0.885


def build_tank(M):
    for k in TANK:
        k.pop('t', None)
    tank = loft('Tank', TANK, M['armour'], 88, 64, cap0='point', cap1='point', subsurf=0, track=False)
    tank.name = tank.data.name = 'Tank'
    return tank


def tank_band(name, x0, x1, grow, mat, a0=-math.pi / 2, a1=1.5 * math.pi, closed=True, n=48):
    keys = []
    for x in (x0, (x0 + x1) / 2, x1):
        c, w, ht, hb, e = keyed_at(TANK, x)
        keys.append(dict(c=c, w=w + grow, ht=ht + grow, hb=hb + grow, e=e, a0=a0, a1=a1))
    keys[1]['w'] += 0.004
    keys[1]['ht'] += 0.004
    keys[1]['hb'] += 0.004
    return loft(name, keys, mat, 5, n, closed=closed, cap0='ngon' if closed else None, cap1='ngon' if closed else None, subsurf=0,
                solidify=0.0 if closed else 0.006)


def build_armour(M, tank):
    """Riveted plates over the tank and the front: hoops round the tank's ends, side plates, the nose shrouds over the
    capsules' fronts, the fender, the dash's pedestal."""
    A, R = M['armour'], M['rust']
    plates = []
    # hoops: dark bands round the tank; the rear one crosses the top behind the track, the front one ahead of it
    plates.append(tank_band('Hoop', 0.135, 0.09, 0.012, A))
    plates.append(tank_band('Hoop', 0.03, -0.015, 0.012, A))
    plates.append(tank_band('Hoop', 0.70, 0.655, 0.010, A))
    # side plates: rusted panels over the tank's flanks, below the track
    for sgn in (-1, 1):
        a0, a1 = (-0.15, 0.62) if sgn > 0 else (math.pi - 0.62, math.pi + 0.15)
        keys = []
        for x in (0.60, 0.50, 0.38, 0.26, 0.16):
            c, w, ht, hb, e = keyed_at(TANK, x)
            keys.append(dict(c=c, w=w + 0.005, ht=ht + 0.005, hb=hb + 0.005, e=e, a0=a0, a1=a1))
        p = loft('SidePlate', keys, A, 18, 16, closed=False, subsurf=0, solidify=0.006, track=False)
        plates.append(p)
    # nose shrouds: heavy plates curving from the tank's front down and forward over each capsule's front cap
    for sgn in (-1, 1):
        sh = [key(0.71, 0.86, 0.02, 0.05, 0.04, y=sgn * 0.13, e=3.0),
              key(0.64, 0.79, 0.022, 0.085, 0.07, y=sgn * 0.22, e=3.0),
              key(0.57, 0.69, 0.022, 0.08, 0.07, y=sgn * 0.29, e=3.0),
              key(0.52, 0.61, 0.02, 0.05, 0.05, y=sgn * 0.32, e=3.0)]
        plates.append(loft('Shroud', sh, A, 36, 28, cap0='ngon', cap1='ngon', subsurf=0, track=False))
    # front fender: an armoured arc hugging the front tyre's top
    fy = F_W / 2 + 0.03
    pts = []
    for k in range(9):
        a = math.radians(25 + 115 * k / 8)
        pts.append(F_AXLE + Vector((math.cos(a) * (F_R + 0.045), 0, math.sin(a) * (F_R + 0.045))))
    fk = [dict(c=p, w=fy, ht=0.012, hb=0.012, e=4.0) for p in pts]
    plates.append(loft('Fender', fk, A, 30, 24, cap0='ngon', cap1='ngon', subsurf=0, track=False))
    rib = [dict(c=p + (p - F_AXLE).normalized() * 0.012, w=0.025, ht=0.01, hb=0.01, e=2.5) for p in pts[1:-1]]
    plates.append(loft('FenderRib', rib, R, 24, 10, cap0='point', cap1='point', subsurf=0, track=False))
    ttree = bvh([tank])
    for sgn in (-1, 1):
        pts = []
        for i in range(15):
            x = 0.60 - 0.44 * i / 14
            h = cast(ttree, (x, sgn * 0.128, 1.5), (0, 0, -1))
            if h:
                pts.append(h[0] + h[1] * 0.004)
        plates.append(tube('TankRail', pts, 0.011, A, sides=8, squash=0.45, track=False))
    for p in plates:
        PARTS.append(p)
    trees = bvh(plates + [tank])
    for sgn in (-1, 1):
        rivet_line(trees, [(0.585, sgn * 0.128, 1.0), (0.38, sgn * 0.128, 1.0), (0.175, sgn * 0.128, 1.0)], Vector((0, 0, 1)), R, spacing=0.04, r=0.005)
    # rivets: round the hoops, along the side plates' edges, down the shrouds, along the fender
    for x in (0.112, 0.006, 0.677):
        c, w, ht, hb, e = keyed_at(TANK, x)
        for k in range(28):
            a = TAU * k / 28
            sa, ca = math.sin(a), math.cos(a)
            if x > 0.6 and sa > 0.75:
                continue
            o = Vector((0, ca, sa))
            STUDS.add(c + Vector((0, ca * (w + 0.018), sa * (ht if sa > 0 else hb) + sa * 0.018)), o, R if x > 0.05 else A, r=0.006)
    for sgn in (-1, 1):
        rivet_line(trees, [(0.59, sgn * 0.20, 0.90), (0.38, sgn * 0.215, 0.905), (0.17, sgn * 0.205, 0.89)], Vector((0, sgn, 0.6)), R, spacing=0.04)
        rivet_line(trees, [(0.59, sgn * 0.19, 0.72), (0.38, sgn * 0.205, 0.70), (0.17, sgn * 0.195, 0.705)], Vector((0, sgn, -0.3)), R, spacing=0.04)
        rivet_line(trees, [(0.68, sgn * 0.19, 0.83), (0.62, sgn * 0.25, 0.75), (0.56, sgn * 0.31, 0.66)],
                   Vector((0, sgn, 0)), R, spacing=0.035)
        rivet_line(trees, [F_AXLE + Vector((0.2, sgn * (fy - 0.012), 0.33)), F_AXLE + Vector((-0.05, sgn * (fy - 0.012), 0.36)),
                           F_AXLE + Vector((-0.28, sgn * (fy - 0.012), 0.21))], Vector((0, sgn, 0)), R, spacing=0.04)
    return plates


def build_front(M):
    """Heavy upside-down forks, clamps, the headstock, and the CRT dash's pedestal."""
    A, R = M['armour'], M['rust']
    top = Vector((0.625, 0, 0.935))
    axis = (F_AXLE - top).normalized()
    fy = FORK_Y
    for sgn in (-1, 1):
        t0 = top + Vector((0, sgn * fy, 0))
        a0 = F_AXLE + Vector((0, sgn * fy, 0))
        tube('ForkUpper', [t0 - axis * 0.01, t0 + axis * 0.30], 0.037, A, sides=16, segs=6)
        tube('ForkLower', [t0 + axis * 0.27, a0 + axis * 0.02], 0.029, R, sides=14, segs=8)
        tube('ForkSeal', [t0 + axis * 0.27, t0 + axis * 0.30], 0.041, M['hose'], sides=16, segs=2)
        # fork guard: a plate in front of each lower leg
        g0, g1 = t0 + axis * 0.33, a0 - axis * 0.06
        n_fwd = Vector((axis.z, 0, -axis.x)).normalized()
        if n_fwd.x < 0:
            n_fwd = -n_fwd
        gk = [dict(c=g0 + n_fwd * 0.03, w=0.035, ht=0.012, hb=0.008, e=3.0), dict(c=(g0 + g1) / 2 + n_fwd * 0.036, w=0.04, ht=0.014, hb=0.008, e=3.0),
              dict(c=g1 + n_fwd * 0.03, w=0.03, ht=0.01, hb=0.008, e=3.0)]
        loft('ForkGuard', gk, A, 12, 12, cap0='ngon', cap1='ngon', subsurf=0)
        # axle clamp
        tube('AxleClamp', [a0 + Vector((0, 0, -0.035)), a0 + Vector((0, 0, 0.04))], 0.036, A, sides=12, segs=2)
        # brake caliper on the +Y leg, gripping the disc behind the axle
        if sgn > 0:
            box('Caliper', F_AXLE + Vector((-0.10, F_DISC_Y, 0.075)), (0.07, 0.03, 0.05), R, rot=Matrix.Rotation(0.6, 3, 'Y'))
    # triple clamps
    for z, ww in ((0.0, 1.0), (0.17, 0.9)):
        c = top + axis * (z / axis.length)
        box('Clamp', c + Vector((0.01, 0, -0.01)), (0.09, 2 * fy + 0.09, 0.035), A, rot=Matrix.Rotation(-math.atan2(axis.x, -axis.z), 3, 'Y'), bevel=0.008)
    tube('Headstock', [top + Vector((0, 0, 0.01)), top + axis * 0.2], 0.04, A, sides=14, segs=4)
    # the dash's pedestal: a short stalk off the top clamp
    tube('DashStalk', [top + Vector((0.0, 0, 0.0)), DASH_C + Vector((0.02, 0, -0.05))], 0.018, A, sides=10, segs=4)


def build_dash(M):
    """Bike4Dash: a small CRT screen in a boxy armoured housing with a sun hood, above the bars, facing the rider's eye.
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
    width, height, bulge = 0.165, 0.115, 0.012
    nu, nv = 16, 12
    verts, faces, uvs = [], [], []
    for j in range(nv + 1):
        for i in range(nu + 1):
            u, v = i / nu, j / nv
            su, sv = 2 * u - 1, 2 * v - 1
            p = D + Rt * (su * width / 2) + U * (sv * height / 2) + N * (bulge * (1 - su * su * 0.85) * (1 - sv * sv * 0.85))
            verts.append(p)
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))
            uvs.append(((i / nu, j / nv), ((i + 1) / nu, j / nv), ((i + 1) / nu, (j + 1) / nv), (i / nu, (j + 1) / nv)))
    dash = new_obj('Bike4Dash', verts, faces, M['dash'], uvs=uvs, track=False)
    if sum(p.normal.dot(N) for p in dash.data.polygons) < 0:
        dash.data.flip_normals()
    # housing: a boxy shell behind the screen, its face a frame proud of the glass, and a hood over the top
    side = Vector((0, 1, 0))
    back = -N
    hk = [dict(c=D + N * 0.008, w=width / 2 + 0.018, ht=height / 2 + 0.016, hb=height / 2 + 0.016, e=6.0),
          dict(c=D - N * 0.02, w=width / 2 + 0.022, ht=height / 2 + 0.02, hb=height / 2 + 0.02, e=6.0),
          dict(c=D - N * 0.085, w=width / 2 + 0.005, ht=height / 2 + 0.0, hb=height / 2 + 0.0, e=5.0),
          dict(c=D - N * 0.11, w=width / 2 - 0.02, ht=height / 2 - 0.02, hb=height / 2 - 0.02, e=4.0)]
    # loft runs from the screen face backward (away from the rider): its section up must be U
    shell = loft('DashHousing', hk, M['armour'], 10, 32, side=-side if U.dot(side.cross(back)) < 0 else side, cap0=None, cap1='ngon', subsurf=0)
    # a frame lip in front of the screen face (an open ring) so the glass sits recessed
    fr = []
    for k in range(40):
        a = TAU * k / 40
        c, s = math.cos(a), math.sin(a)
        e = 6.0
        uu = (width / 2 + 0.006) * math.copysign(abs(c) ** (2 / e), c)
        vv = (height / 2 + 0.006) * math.copysign(abs(s) ** (2 / e), s)
        fr.append((uu, vv))
    rings = []
    for depth, grow in ((0.008, 0.0), (0.016, 0.0), (0.016, 0.014), (0.008, 0.016)):
        rings.append([D + N * depth + Rt * (uu * (1 + grow / (width / 2))) + U * (vv * (1 + grow / (height / 2))) for uu, vv in fr])
    rings_mesh('DashFrame', rings, M['armour'], closed_along=True)
    # sun hood: a plate over the top, reaching toward the rider
    hood = [dict(c=D + U * (height / 2 + 0.02) - N * 0.06, w=width / 2 + 0.026, ht=0.006, hb=0.006, e=6.0),
            dict(c=D + U * (height / 2 + 0.017) + N * 0.045, w=width / 2 + 0.024, ht=0.005, hb=0.005, e=6.0)]
    loft('DashHood', hood, M['armour'], 6, 24, side=Vector((0, 1, 0)) if (Vector((0, 1, 0)).cross(N).dot(U) > 0) else Vector((0, -1, 0)),
         cap0='ngon', cap1='ngon', subsurf=0)
    for sgn in (-1, 1):
        for vv in (-1, 1):
            STUDS.add(D + N * 0.017 + Rt * (sgn * (width / 2 + 0.011)) + U * (vv * (height / 2 + 0.008)), N, M['rust'], r=0.0045)
    return dash


def build_bars(M):
    A = M['armour']
    for sgn in (-1, 1):
        bar = [Vector((0.625, sgn * 0.06, 0.955)), Vector((0.585, sgn * 0.17, 0.968)), Vector((0.47, sgn * 0.29, 0.958)), Vector((0.40, sgn * 0.335, 0.948))]
        tube('Bar', bar, 0.0135, A, sides=12, segs=20)
        tube('Grip', [Vector((0.405, sgn * 0.33, 0.948)), Vector((0.345, sgn * 0.43, 0.94))],
             lambda s: 0.019 * (1 + 0.06 * abs(math.sin(math.pi * 9 * s)) ** 2), M['hose'], sides=12, segs=18)
        tube('BarEnd', [Vector((0.345, sgn * 0.43, 0.94)), Vector((0.34, sgn * 0.442, 0.94))], 0.021, M['rust'], sides=12, segs=2)
        box('Switch', (0.43, sgn * 0.30, 0.958), (0.05, 0.032, 0.04), A, rot=Matrix.Rotation(sgn * 0.5, 3, 'Z'), bevel=0.006)
        # lever ahead of each grip
        tube('Lever', [Vector((0.44, sgn * 0.31, 0.955)), Vector((0.41, sgn * 0.37, 0.965)), Vector((0.385, sgn * 0.43, 0.965))], 0.006, M['rust'], sides=8, segs=10)
        # cables from the switch gear arcing into the headstock
        tube('Cable', [Vector((0.44, sgn * 0.29, 0.95)), Vector((0.52, sgn * 0.22, 0.97)), Vector((0.60, sgn * 0.12, 0.93)),
                       Vector((0.66, sgn * 0.06, 0.86))], 0.0055, M['hose'], sides=6, segs=20)


# ---------------------------------------------------------------- the biotech: capsules, ribbed tubes, the engine
CAPS_X0, CAPS_X1, CAPS_Y, CAPS_Z, CAPS_R = 0.30, -0.33, 0.205, 0.50, 0.112


def build_capsules(M):
    """The big glass capsule along each side: a glass cylinder full of glowing green fluid with dark red veins and
    organ lumps floating against the glass, held in riveted armour collars and end caps."""
    G, F, V, A, R = M['glass'], M['fluid'], M['vein'], M['armour'], M['rust']
    L = CAPS_X0 - CAPS_X1
    xm = (CAPS_X0 + CAPS_X1) / 2
    rnd = random.Random(11)
    for sgn in (-1, 1):
        at = Vector((xm, sgn * CAPS_Y, CAPS_Z))
        h = L / 2
        lathe_x('CapsuleGlass', [(CAPS_R, -h + 0.03 + (L - 0.06) * i / 8) for i in range(9)], G, 48, at, closed_prof=False)
        lathe_x('CapsuleFluid', [(0.0, -h + 0.04), (CAPS_R - 0.007, -h + 0.04), (CAPS_R - 0.007, h - 0.04), (0.0, h - 0.04)], F, 40, at, closed_prof=False)
        # collars and end caps
        for end in (-1, 1):
            x0 = end * (h - 0.045)
            col = [(CAPS_R - 0.004, x0 - end * 0.03), (CAPS_R + 0.016, x0 - end * 0.028), (CAPS_R + 0.02, x0 - end * 0.012),
                   (CAPS_R + 0.02, x0 + end * 0.03), (CAPS_R + 0.008, x0 + end * 0.045)]
            ob = lathe_x('Collar', col, A, 40, at, closed_prof=False)
            cap = [(CAPS_R + 0.008, x0 + end * 0.045), (CAPS_R - 0.01, x0 + end * 0.07), (0.07, x0 + end * 0.09), (0.03, x0 + end * 0.097), (0.0, x0 + end * 0.098)]
            lathe_x('EndCap', cap, R if end > 0 else A, 40, at, closed_prof=False)
            for k in range(14):
                a = TAU * k / 14
                n = Vector((0, math.cos(a), math.sin(a)))
                STUDS.add(at + Vector((x0 + end * 0.008, 0, 0)) + n * (CAPS_R + 0.02), n, R, r=0.006)
        # a strap round the middle of the glass
        lathe_x('Strap', [(CAPS_R + 0.0015, -0.015), (CAPS_R + 0.007, -0.012), (CAPS_R + 0.007, 0.012), (CAPS_R + 0.0015, 0.015)], R, 40,
                at + Vector((0.02, 0, 0)), closed_prof=False)
        # mounts from the frame to the collars
        for end in (-1, 1):
            p = at + Vector((end * (h - 0.045), 0, 0))
            tube('CapsuleMount', [p + Vector((0, -sgn * 0.08, 0.03)), p + Vector((0, -sgn * 0.14, 0.09))], 0.016, A, sides=8, segs=3)
        # veins: branching walks over the fluid's surface, under the glass; mostly on the outboard face
        rv = CAPS_R - 0.0065

        def surf(xl, th):
            return at + Vector((xl, math.cos(th) * rv, math.sin(th) * rv))
        for k in range(20):
            th = (0.0 if sgn > 0 else math.pi) + rnd.uniform(-1.6, 1.6)
            xl = rnd.uniform(-h + 0.07, h - 0.07)
            dx = rnd.choice((-1, 1)) * 0.022
            dth = rnd.uniform(-0.25, 0.25)
            pts = []
            for i in range(10):
                pts.append(surf(xl, th))
                xl = max(-h + 0.05, min(h - 0.05, xl + dx + rnd.uniform(-0.01, 0.01)))
                th += dth + rnd.uniform(-0.18, 0.18)
            rr = rnd.uniform(0.002, 0.004)
            tube('Vein', pts, lambda s, rr=rr: rr * (1 - 0.6 * s) + 0.0008, V, sides=3, cap1='point', segs=10)
            # side branches
            for b in range(rnd.choice((1, 2))):
                i0 = rnd.randrange(2, 8)
                x0, t0 = (pts[i0] - at).x, math.atan2((pts[i0] - at).z, (pts[i0] - at).y)
                bp = [surf(x0, t0)]
                for i in range(4):
                    x0 += rnd.uniform(-0.02, 0.02)
                    t0 += rnd.uniform(-0.25, 0.25)
                    bp.append(surf(x0, t0))
                tube('Vein', bp, lambda s, rr=rr: rr * 0.6 * (1 - 0.7 * s) + 0.0006, V, sides=3, cap1='point', segs=6)
        # organ lumps: knotted red masses pressed against the glass
        for k in range(3):
            th = (0.0 if sgn > 0 else math.pi) + rnd.uniform(-1.0, 1.0)
            xl = rnd.uniform(-h + 0.12, h - 0.12)
            c = at + Vector((xl, math.cos(th) * (rv - 0.022), math.sin(th) * (rv - 0.022)))
            ob = ellipsoid('Organ', c, (rnd.uniform(0.035, 0.06), 0.03, 0.028), V, rot=(th, rnd.uniform(-0.4, 0.4), 0), segs=12, rings=8)
            for v in ob.data.vertices:
                v.co += v.normal * 0.008 * noise.noise(v.co * 60)


def bellows_profile(r_in, r_out, length, ribs):
    prof = [(0.0, -length / 2), (r_in, -length / 2)]
    for k in range(ribs):
        y0 = -length / 2 + length * (k + 0.5) / ribs
        q = length / ribs / 2
        prof += [(r_in, y0 - q * 0.8), (r_out, y0 - q * 0.35), (r_out, y0 + q * 0.35), (r_in, y0 + q * 0.8)]
    prof += [(r_in, length / 2), (0.0, length / 2)]
    return prof


def build_bay(M):
    """The engine bay: a dark armoured block, the ribbed green glass tubes (a bellows each side under the seat, a coil
    round the crankcase, tubes snaking between), the low glowing canister, hoses, the chain and the exhaust."""
    A, R, T, H = M['armour'], M['rust'], M['tube'], M['hose']
    # engine block between the capsules
    core = [key(0.48, 0.42, 0.05, 0.05, 0.05, e=3), key(0.40, 0.42, 0.105, 0.18, 0.24, e=3.5), key(0.15, 0.44, 0.12, 0.22, 0.27, e=3.5),
            key(-0.10, 0.48, 0.11, 0.20, 0.24, e=3.5), key(-0.25, 0.52, 0.08, 0.13, 0.15, e=3), key(-0.32, 0.55, 0.03, 0.04, 0.04, e=3)]
    loft('Engine', core, A, 24, 28, cap0='point', cap1='point', subsurf=0)
    # crankcase covers each side, low down
    for sgn in (-1, 1):
        prof = [(0.0, 0.0), (0.105, 0.0), (0.108, 0.012), (0.1, 0.026), (0.07, 0.034), (0.03, 0.036), (0.0, 0.036)]
        if sgn < 0:
            prof = [(r, -y) for r, y in prof]
        ob = lathe_y('Crankcase', prof, R if sgn > 0 else A, 36, (0.12, sgn * 0.09, 0.27))
        if sgn < 0:
            ob.data.flip_normals()
        for k in range(10):
            a = TAU * k / 10
            STUDS.add(Vector((0.12 + 0.09 * math.cos(a), sgn * (0.09 + 0.03), 0.27 + 0.09 * math.sin(a))), Vector((0, sgn, 0)), A, r=0.006)
    # bellows: a ribbed glowing glass drum each side under the seat (the concept's green ribs behind the tank)
    for sgn in (-1, 1):
        at = Vector((-0.17, sgn * 0.14, 0.745))
        prof = bellows_profile(0.064, 0.078, 0.40, 9)
        ob = lathe_x('Bellows', prof, T, 24, at, closed_prof=False)
        # dark armour hoops between the ribs, heavier at the ends: the green shows in the gaps
        for i in range(10):
            xo = -0.20 + 0.40 * i / 9
            t = 0.012 if i in (0, 9) else 0.008
            lathe_x('BellowsHoop', [(0.062, xo - t), (0.084, xo - t), (0.088, xo), (0.084, xo + t), (0.062, xo + t)], A, 24, at, closed_prof=False)
            if i not in (0, 9):
                continue
            for k in range(8):
                a = TAU * k / 8
                n = Vector((0, math.cos(a), math.sin(a)))
                STUDS.add(at + Vector((xo, 0, 0)) + n * 0.092, n, R, r=0.005)
    # the coil: a ribbed glowing tube wound round the crankcase, between the capsules
    pts = []
    for i in range(60):
        s = i / 59
        ph = TAU * 2.2 * s + 0.6
        pts.append(Vector((0.30 - 0.36 * s, 0.145 * math.cos(ph), 0.27 + 0.145 * math.sin(ph))))
    hose('Coil', pts, 0.012, T, pitch=0.016, sides=7)
    # snaking ribbed tubes: from the bellows down past the capsule ends, and from the tank's underside into the capsules
    for sgn in (-1, 1):
        hose('GlowTube', [(0.03, sgn * 0.16, 0.73), (0.12, sgn * 0.17, 0.66), (0.22, sgn * 0.13, 0.64), (0.33, sgn * 0.12, 0.60),
                          (0.44, sgn * 0.17, 0.53), (CAPS_X0 + 0.05, sgn * CAPS_Y, CAPS_Z)], 0.017, T, pitch=0.013)
        hose('GlowTube', [(-0.36, sgn * 0.14, 0.74), (-0.38, sgn * 0.17, 0.64), (-0.36, sgn * 0.205, 0.55), (CAPS_X1 - 0.05, sgn * CAPS_Y, CAPS_Z)],
             0.016, T, pitch=0.013)
    # canister: a smaller glowing cylinder low on the +Y side ahead of the rear wheel (the concept's)
    at = Vector((-0.37, 0.28, 0.26))
    lathe_x('Canister', [(0.0, -0.09), (0.052, -0.09), (0.052, 0.09), (0.0, 0.09)], T, 28, at, closed_prof=False)
    for end in (-1, 1):
        lathe_x('CanisterCap', [(0.045, end * 0.07), (0.062, end * 0.072), (0.064, end * 0.1), (0.04, end * 0.115), (0.0, end * 0.118)], A, 28, at,
                closed_prof=False)
    lathe_x('CanisterBand', [(0.052, -0.012), (0.058, -0.01), (0.058, 0.01), (0.052, 0.012)], R, 28, at, closed_prof=False)
    tube('CanisterMount', [at + Vector((0, -0.05, 0.04)), at + Vector((0.03, -0.12, 0.10))], 0.014, A, sides=8, segs=3)
    # hoses: corrugated black lines from the capsules down round the bottom to the canister and the engine
    hose('Hose', [(CAPS_X0 + 0.07, 0.21, 0.48), (0.48, 0.25, 0.36), (0.40, 0.27, 0.22), (0.22, 0.26, 0.14), (0.0, 0.25, 0.13),
                  (-0.20, 0.28, 0.22), (-0.275, 0.28, 0.26)], 0.022, H)
    hose('Hose', [(CAPS_X1 - 0.07, 0.21, 0.47), (-0.40, 0.25, 0.40), (-0.48, 0.31, 0.33), (-0.475, 0.28, 0.26)], 0.019, H)
    hose('Hose', [(0.08, 0.20, 0.42), (0.02, 0.27, 0.34), (-0.12, 0.29, 0.30), (-0.26, 0.29, 0.30), (-0.33, 0.27, 0.27)], 0.016, H)
    hose('Hose', [(0.60, 0.12, 0.84), (0.66, 0.19, 0.70), (0.72, 0.20, 0.55), (0.76, 0.19, 0.42)], 0.013, H)
    for c in ([(CAPS_X0 + 0.07, -0.21, 0.48), (0.47, -0.25, 0.36), (0.38, -0.25, 0.22), (0.20, -0.22, 0.14), (-0.05, -0.20, 0.15)],
              [(CAPS_X1 - 0.07, -0.21, 0.47), (-0.38, -0.23, 0.36), (-0.30, -0.21, 0.25), (-0.15, -0.17, 0.20)],
              [(0.60, -0.12, 0.84), (0.66, -0.19, 0.70), (0.72, -0.20, 0.55), (0.76, -0.19, 0.42)]):
        hose('Hose', c, 0.018, H)
    # thin cables
    for sgn in (-1, 1):
        tube('Cable', [(0.30, sgn * 0.20, 0.66), (0.20, sgn * 0.25, 0.62), (0.05, sgn * 0.265, 0.64), (-0.12, sgn * 0.23, 0.66)], 0.005, H, sides=6)
    # exhaust on -Y: a rusted header from the engine's front, back under the capsule to a heat-shielded can under the tail
    ex = [(0.40, -0.10, 0.22), (0.36, -0.21, 0.15), (0.10, -0.25, 0.13), (-0.25, -0.27, 0.22), (-0.48, -0.29, 0.38), (-0.62, -0.30, 0.48)]
    tube('Header', ex, 0.026, A, sides=12)
    can = [key(-0.58, 0.47, 0.055, 0.055, 0.055, y=-0.30, e=2.2), key(-0.72, 0.53, 0.068, 0.068, 0.068, y=-0.305, e=2.2),
           key(-0.94, 0.61, 0.064, 0.064, 0.064, y=-0.30, e=2.2), key(-0.99, 0.63, 0.04, 0.04, 0.04, y=-0.30, e=2.2)]
    loft('Muffler', can, A, 24, 20, cap0='ngon', cap1='ngon', subsurf=0)
    shield = [dict(c=c['c'] + Vector((0, -0.012, 0.008)), w=c['w'] + 0.012, ht=c['ht'] + 0.012, hb=c['hb'] + 0.012, e=2.2, a0=-0.3 + math.pi * 0.5, a1=math.pi * 1.35)
              for c in can[1:3]]
    loft('Shield', shield, A, 10, 16, closed=False, solidify=0.004, subsurf=0)
    tube('Tip', [Vector((-0.985, -0.30, 0.627)), Vector((-1.02, -0.30, 0.64))], 0.03, R, sides=14, segs=2, cap1=None)
    # chain on +Y: two straight runs round the front sprocket and the wheel's (the wheel's sprocket is on Wheel4Rear)
    cy = R_SPROCKET_Y + 0.003
    fs = Vector((-0.17, cy, 0.38))
    rs = R_AXLE + Vector((0, cy, 0))
    lathe_y('FrontSprocket', [(0.0, cy - 0.004), (0.052, cy - 0.004), (0.052, cy + 0.004), (0.0, cy + 0.004)], R, 18, fs)
    d = rs - fs
    d.y = 0
    L = d.length
    dn = d.normalized()
    nrm = Vector((-dn.z, 0, dn.x))
    r0, r1 = 0.056, 0.132
    ang = math.asin((r1 - r0) / L)
    for side in (1, -1):
        n2 = (Matrix.Rotation(-side * ang, 3, 'Y') @ nrm) * side
        a, b = fs + n2 * r0, rs + n2 * r1
        tube('Chain', [a, b], lambda s: 0.0065 * (1 + 0.25 * abs(math.sin(math.pi * 40 * s)) ** 2), R, sides=5, segs=80, squash=0.6)
    # swingarm: boxy armoured beams from the pivot to the rear axle, outboard of the disc
    for sgn in (-1, 1):
        sy = SWING_Y
        arm = [key(-0.16, 0.39, 0.03, 0.05, 0.05, y=sgn * 0.15, e=3.5), key(-0.36, 0.385, 0.026, 0.055, 0.05, y=sgn * (sy - 0.01), e=3.5),
               key(-0.60, 0.35, 0.022, 0.045, 0.04, y=sgn * sy, e=3.5), key(-0.76, 0.327, 0.022, 0.04, 0.04, y=sgn * sy, e=3.5),
               key(-0.83, 0.322, 0.02, 0.03, 0.03, y=sgn * sy, e=3.5)]
        loft('Swingarm', arm, A, 30, 16, cap0='ngon', cap1='ngon', subsurf=0)
        tube('AxleBlock', [R_AXLE + Vector((0, sgn * (sy - 0.02), 0)), R_AXLE + Vector((0, sgn * (sy + 0.03), 0))], 0.03, R, sides=6, segs=2)
        tube('Pivot', [Vector((-0.16, sgn * 0.11, 0.39)), Vector((-0.16, sgn * 0.19, 0.39))], 0.032, R, sides=10, segs=2)
        # shock: a coil-over from the swingarm up into the tail
        sh0, sh1 = Vector((-0.50, sgn * (sy - 0.015), 0.38)), Vector((-0.40, sgn * 0.16, 0.70))
        tube('Shock', [sh0, sh1], 0.016, A, sides=10, segs=4)
        pts = [sh0.lerp(sh1, 0.15 + 0.6 * i / 60) + Vector((0, 0.028 * math.cos(i * 0.7), 0.028 * math.sin(i * 0.7))) for i in range(61)]
        tube('Spring', pts, 0.0055, M['rust'], sides=5, segs=80)
    # caliper on the +Y swingarm gripping the rear disc
    box('Caliper', R_AXLE + Vector((0.075, R_DISC_Y, 0.075)), (0.075, 0.03, 0.05), R, rot=Matrix.Rotation(-0.7, 3, 'Y'))


def build_rear(M):
    A, R, H = M['armour'], M['rust'], M['hose']
    for k in TAIL:
        k.pop('t', None)
    tail = loft('Tail', TAIL, A, 50, 40, cap0='point', cap1='ngon', subsurf=0)
    # the hooked lip: a heavy brow over the light, the cowl's top running on past the rear face and turning down
    E = TAIL_END
    lip = [key(E + 0.05, 0.884, 0.182, 0.010, 0.012, e=3.0), key(E - 0.025, 0.876, 0.175, 0.010, 0.012, e=3.0),
           key(E - 0.052, 0.856, 0.165, 0.009, 0.011, e=3.0), key(E - 0.057, 0.832, 0.15, 0.008, 0.01, e=3.0)]
    loft('TailLip', lip, A, 12, 24, cap0='ngon', cap1='ngon', subsurf=0)
    # side plates on the tail, rusted, riveted
    for sgn in (-1, 1):
        keys = []
        for x in (-0.36, -0.48, -0.60, -0.72, -0.84):
            c, w, ht, hb, e = keyed_at(TAIL, x)
            a0, a1 = (-0.75, 0.3) if sgn > 0 else (math.pi - 0.3, math.pi + 0.75)
            keys.append(dict(c=c, w=w + 0.005, ht=ht + 0.005, hb=hb + 0.005, e=e, a0=a0, a1=a1))
        loft('TailPlate', keys, A, 20, 10, closed=False, solidify=0.006, subsurf=0)
    # the tail light: a long red bar across the rear face, tucked under the hooked lip
    tube('TailLight', [Vector((E - 0.004, -0.13, 0.80)), Vector((E - 0.010, 0.0, 0.80)), Vector((E - 0.004, 0.13, 0.80))], 0.013, M['tail'],
         sides=10, segs=20, squash=0.55)
    tube('TailBezel', [Vector((E + 0.017, -0.145, 0.80)), Vector((E + 0.012, 0.0, 0.80)), Vector((E + 0.017, 0.145, 0.80))], 0.02, H,
         sides=12, segs=24, squash=0.45)
    # skirts: heavy side plates dropping from the cowl in front of the rear tyre (the concept's hooked flank)
    for sgn in (-1, 1):
        sk = [key(-0.26, 0.72, 0.012, 0.05, 0.07, y=sgn * 0.17, e=3.5), key(-0.36, 0.70, 0.013, 0.09, 0.13, y=sgn * 0.205, e=3.5),
              key(-0.50, 0.70, 0.013, 0.10, 0.12, y=sgn * 0.215, e=3.5), key(-0.63, 0.73, 0.013, 0.08, 0.07, y=sgn * 0.215, e=3.5),
              key(-0.72, 0.77, 0.012, 0.04, 0.03, y=sgn * 0.21, e=3.5)]
        loft('Skirt', sk, A, 30, 16, cap0='ngon', cap1='ngon', subsurf=0)
    # hugger: an armour arc over the rear tyre, hooking down behind it toward the tread
    hy = R_W / 2 + 0.022
    pts = []
    for k in range(9):
        a = math.radians(72 + 58 * k / 8)
        pts.append(R_AXLE + Vector((math.cos(a) * (R_R + 0.032), 0, math.sin(a) * (R_R + 0.032))))
    pts = list(reversed(pts))
    hk = [dict(c=p, w=hy, ht=0.01, hb=0.01, e=4.0) for p in pts]
    loft('Hugger', hk, A, 30, 24, cap0='ngon', cap1='ngon', subsurf=0)
    # struts from the tail's underside down to the swingarm ends: the 'hook' the concept shows at the tail's back
    for sgn in (-1, 1):
        tube('TailStrut', [Vector((-0.83, sgn * 0.15, 0.74)), Vector((-0.96, sgn * 0.205, 0.62)), Vector((-0.86, sgn * 0.20, 0.46)),
                           R_AXLE + Vector((-0.04, sgn * SWING_Y, 0.03))], 0.017, R, sides=8)
    # seat: a low black pad between the tank and the tail
    seat = [key(-0.06, 0.80, 0.06, 0.03, 0.04, e=3), key(-0.13, 0.818, 0.135, 0.035, 0.05, e=3), key(-0.27, 0.812, 0.145, 0.032, 0.05, e=3),
            key(-0.38, 0.832, 0.13, 0.03, 0.05, e=3), key(-0.44, 0.845, 0.06, 0.02, 0.04, e=3)]
    loft('Seat', seat, H, 26, 28, cap0='point', cap1='point', subsurf=0)
    for x in (-0.16, -0.22, -0.28, -0.34):
        tube('Tuck', [Vector((x, -0.12, 0.835)), Vector((x - 0.008, 0.0, 0.853)), Vector((x, 0.12, 0.84))], 0.004, H, sides=6, segs=12)
    # kickstand on +Y (as bike.glb's: the foot touches the ground once the bike leans)
    foot_y = 0.56
    foot_z = (0.015 + math.sin(LEAN) * foot_y) / math.cos(LEAN)
    tube('Stand', [Vector((-0.10, 0.17, 0.25)), Vector((-0.17, 0.36, 0.15)), Vector((-0.26, foot_y, foot_z))], (0.019, 0.012), R, sides=10, segs=12)
    tube('StandFoot', [Vector((-0.30, foot_y, foot_z)), Vector((-0.22, foot_y, foot_z))], 0.016, R, sides=10, segs=2, squash=0.5)
    return tail


def build_lamps(M):
    """Front: two small green lamps under the shrouds' brows (the zone's glow), in armoured cups."""
    for sgn in (-1, 1):
        at = Vector((0.74, sgn * 0.075, 0.80))
        lathe_x('LampCup', [(0.0, -0.03), (0.034, -0.03), (0.04, 0.0), (0.036, 0.012), (0.03, 0.006)], M['armour'], 20, at, closed_prof=False)
        lathe_x('Lamp', [(0.03, 0.006), (0.024, 0.014), (0.0, 0.017)], M['tube'], 20, at, closed_prof=False)


# ---------------------------------------------------------------- the throttle track and button
def load_tank_field():
    t = json.load(open(os.path.join(ALIGN, 'bike1-tank.json')))
    return t['d'], t['s'], t['h']


def conform_tank(tank):
    """Blend the tank's top onto bike.glb's surface under the slingshot track (heights sampled along ButtonCentre's
    normal, art/align-bike4/bike1-tank.json): exact in the track's footprint, easing back to the loft outside it."""
    D, S, Hh = load_tank_field()
    C = BUTTON_CENTRE
    Ci = C.inverted()

    def field(d, s):
        fi = (d - D[0]) / (D[1] - D[0])
        fj = (s - S[0]) / (S[1] - S[0])
        i = min(max(int(fi), 0), len(D) - 2)
        j = min(max(int(fj), 0), len(S) - 2)
        u, v = min(max(fi - i, 0), 1), min(max(fj - j, 0), 1)
        return (Hh[i][j] * (1 - u) * (1 - v) + Hh[i + 1][j] * u * (1 - v) + Hh[i][j + 1] * (1 - u) * v + Hh[i + 1][j + 1] * u * v)
    me = tank.data
    worst_before = 0.0
    for v in me.vertices:
        if v.normal.z < 0.3:
            continue
        q = Ci @ v.co
        d, s = -q.x, q.y
        if not (D[0] <= d <= D[-1] and S[0] <= s <= S[-1]):
            continue
        wd = smoothstep(D[0], -0.19, d) * (1 - smoothstep(0.28, D[-1], d))
        ws = 1 - smoothstep(0.085, S[-1], abs(s))
        w = wd * ws
        target = field(d, s)
        if wd * ws > 0.99:
            worst_before = max(worst_before, abs(q.z - target))
        q.z = q.z + (target - q.z) * w
        v.co = C @ q
    me.update()
    print('TANK conform: loft vs bike.glb in the footprint, worst (m):', round(worst_before, 4))


def build_button(M, tank):
    import numpy as np
    tree = bvh([tank])

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
    btn = rings_mesh('Bike4Button', rings, M['button'], track=False)
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
    gme = bpy.data.meshes.new('Bike4ButtonGlyph')
    bm.to_mesh(gme)
    bm.free()
    for v in gme.vertices:
        x, y, tz = v.co.x, v.co.y, v.co.z
        p, n = base(x, y)
        v.co = p + n * (FACE_H + 0.0015 + tz)
    gme.materials.append(M['glyph'])
    gme.shade_flat()
    glyph = bpy.data.objects.new('Bike4ButtonGlyph', gme)
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


def track_profile(body_parts):
    """The tank surface under the track as built (button meshes excluded), along ButtonCentre's normal: casts start
    8 cm above the surface so the bars and dash overhead don't count."""
    trees = bvh(body_parts)
    C = BUTTON_CENTRE
    o, X, Yv, Z = C.translation, C.col[0].xyz.normalized(), C.col[1].xyz.normalized(), C.col[2].xyz.normalized()

    def height(d, s):
        p = o + X * (-d) + Yv * s + Z * 0.08
        h = cast(trees, p, -Z)
        return None if h is None else round((h[0] - o).dot(Z), 5)
    centre = [height(d, 0.0) for d in TRACK_D]
    side = [round((height(d, TRACK_RAIL) + height(d, -TRACK_RAIL)) / 2, 5) for d in TRACK_D]
    return centre, side


# ---------------------------------------------------------------- ambient occlusion + grime into vertex colours
NO_GRIME = {'Bike4Glass', 'Bike4Fluid', 'Bike4Tube', 'Bike4Tail'}


def bake_vertex_colours(obs, samples=48):
    scene = bpy.context.scene
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
    scene.cycles.samples = samples
    if scene.world is None:
        scene.world = bpy.data.worlds.new('BakeWorld')
    scene.world.light_settings.distance = 0.12
    for ob in obs:
        me = ob.data
        attr = me.color_attributes.new('Col', 'BYTE_COLOR', 'CORNER')
        me.color_attributes.active_color = attr
        me.attributes.active_color = attr
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        try:
            bpy.ops.object.bake(type='AO', target='VERTEX_COLORS')
            ok = True
        except Exception as e:
            print('AO bake failed', ob.name, e)
            ok = False
        cols = [0.0] * (len(me.loops) * 4)
        if ok:
            attr.data.foreach_get('color', cols)
        mats = [m.name if m else '' for m in me.materials]
        loop_poly = [0] * len(me.loops)
        for p in me.polygons:
            for li in p.loop_indices:
                loop_poly[li] = p.index
        pmat = [p.material_index for p in me.polygons]
        vco = [v.co.copy() for v in me.vertices]
        vn = [v.normal.copy() for v in me.vertices]
        mw = ob.matrix_world.to_3x3()
        for li, lp in enumerate(me.loops):
            m = mats[pmat[loop_poly[li]]]
            if m in NO_GRIME:
                c = (1.0, 1.0, 1.0)
            else:
                ao = cols[li * 4] if ok else 1.0
                k = 0.3 + 0.7 * ao
                c = (k, k, k)
            cols[li * 4:li * 4 + 4] = [*c, 1.0]
        # average onto the vertices: a corner-domain colour would split vertices on export
        nv = len(me.vertices)
        acc = [[0.0, 0.0, 0.0, 0] for _ in range(nv)]
        for li, lp in enumerate(me.loops):
            a_ = acc[lp.vertex_index]
            a_[0] += cols[li * 4]
            a_[1] += cols[li * 4 + 1]
            a_[2] += cols[li * 4 + 2]
            a_[3] += 1
        me.color_attributes.remove(attr)
        pt = me.color_attributes.new('Col', 'BYTE_COLOR', 'POINT')
        val = [a_[0] / max(a_[3], 1) for a_ in acc]
        # relax the bake's noise over the mesh's edges, then a warm sand tint where it's open (multiplied on the site)
        nbr = [[] for _ in range(nv)]
        for e in me.edges:
            a_, b_ = e.vertices
            nbr[a_].append(b_)
            nbr[b_].append(a_)
        for _ in range(4):
            val = [0.5 * val[i] + 0.5 * (sum(val[j] for j in nbr[i]) / len(nbr[i])) if nbr[i] else val[i] for i in range(nv)]
        flat = []
        for i, v_ in enumerate(val):
            q = round(v_ * 24) / 24  # coarse steps compress far better and read the same
            flat += [q, q * 0.97, q * 0.93, 1.0]
        pt.data.foreach_set('color', flat)
        me.color_attributes.active_color = pt
        me.attributes.active_color = pt
        me.update()
        print('VCOL', ob.name, 'baked' if ok else 'grime only')


# ---------------------------------------------------------------- render setup (review only, not exported)
def setup_render(scene):
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 10
    scene.cycles.transparent_max_bounces = 16
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    # desert storm sky: hazy orange at the horizon, dusty ochre above, warm sand below
    world = bpy.data.worlds.new('DesertWorld')
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
    cr.elements[0].position, cr.elements[0].color = 0.0, (0.12, 0.07, 0.035, 1)
    cr.elements[1].position, cr.elements[1].color = 1.0, (0.55, 0.36, 0.2, 1)
    for pos, c in ((0.48, (0.30, 0.17, 0.08, 1)), (0.50, (1.5, 0.85, 0.45, 1)), (0.56, (1.1, 0.62, 0.32, 1)), (0.75, (0.75, 0.47, 0.26, 1))):
        e = cr.elements.new(pos)
        e.color = c
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.4
    world.light_settings.distance = 0.12
    col = bpy.data.collections.new('Render')
    scene.collection.children.link(col)
    # hazy sun ahead of the bike and high (the concept's sun over the road), so the concept view is half back-lit
    sd = bpy.data.lights.new('Sun', 'SUN')
    sd.color = (1.0, 0.78, 0.52)
    sd.energy = 3.5
    sd.angle = math.radians(6)
    sun = bpy.data.objects.new('Sun', sd)
    sun.rotation_euler = (Vector((0.75, -0.35, 0.75)).to_track_quat('Z', 'Y')).to_euler()
    col.objects.link(sun)
    # dusty key from high on the camera side (+Y, behind), soft
    kd = bpy.data.lights.new('Key', 'SUN')
    kd.color = (1.0, 0.82, 0.62)
    kd.energy = 2.2
    kd.angle = math.radians(20)
    ko = bpy.data.objects.new('Key', kd)
    ko.rotation_euler = (Vector((-0.45, 0.75, 0.7)).to_track_quat('Z', 'Y')).to_euler()
    col.objects.link(ko)
    # warm bounce from the sand, low on the camera side
    for loc, size, colr, s in (((-3, 4, 1.0), (6, 2), (1.0, 0.7, 0.45), 1.6), ((2, -5, 1.5), (8, 2.5), (1.0, 0.75, 0.5), 1.4),
                               ((-5, -1, 2.5), (5, 3), (1.0, 0.8, 0.6), 1.2)):
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
    # cracked asphalt dusted with sand
    me = bpy.data.meshes.new('Ground')
    s = 30
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new('Ground', me)
    col.objects.link(g)
    gm = bpy.data.materials.new('SandRoad')
    gm.use_nodes = True
    gnt = gm.node_tree
    b = gnt.nodes['Principled BSDF']
    nz = gnt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 3.0
    rp = gnt.nodes.new('ShaderNodeValToRGB')
    rp.color_ramp.elements[0].color = (0.10, 0.08, 0.065, 1)
    rp.color_ramp.elements[1].color = (0.42, 0.25, 0.12, 1)
    rp.color_ramp.elements[0].position, rp.color_ramp.elements[1].position = 0.42, 0.62
    gnt.links.new(nz.outputs['Fac'], rp.inputs['Fac'])
    gnt.links.new(rp.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.9
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


def show_vertex_colours():
    """Review renders only: multiply the baked vertex colours into each material's base colour (three does this itself
    for COLOR_0)."""
    for m in bpy.data.materials:
        if not m.name.startswith('Bike4') or m.name in NO_GRIME:
            continue
        nt = m.node_tree
        b = nt.nodes.get('Principled BSDF')
        if b is None:
            continue
        ca = nt.nodes.new('ShaderNodeVertexColor')
        ca.layer_name = 'Col'
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.blend_type = 'MULTIPLY'
        mix.inputs['Factor'].default_value = 1.0
        link = next((l for l in nt.links if l.to_socket == b.inputs['Base Color']), None)
        if link:
            nt.links.new(link.from_socket, mix.inputs['A'])
        else:
            mix.inputs['A'].default_value = b.inputs['Base Color'].default_value
        nt.links.new(ca.outputs['Color'], mix.inputs['B'])
        nt.links.new(mix.outputs['Result'], b.inputs['Base Color'])


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
    cc = json.load(open(os.path.join(ALIGN, 'concept-cam4.json')))
    eye_w = body.matrix_world @ RIDER_EYE
    cams = {
        # fitted so our tyres and contacts land on the concept's (art/align-bike4/fit_camera.py); not exported
        'concept': (add_camera(col, 'ConceptCam4', cc['location'], cc['look'], lens=cc['lens']), tuple(cc['size'])),
        'rider': (add_camera(col, 'RiderCam4', None, lens=12, matrix=eye_w @ Matrix.Rotation(math.pi / 2, 4, 'X')), (1672, 941)),
        'riderdash': (add_camera(col, 'RiderDashCam4', eye_w.translation, body.matrix_world @ Vector((0.52, 0.0, 0.99)), lens=14), (1672, 941)),
        'side': (add_camera(col, 'CamSide4', (0, -8, 0.62), rot=(math.pi / 2, 0, 0), ortho=2.9), (1920, 1080)),
        'hero': (add_camera(col, 'CamHero4', (2.6, -3.4, 0.75), (0.1, 0, 0.6), lens=32), (1920, 1080)),
        'rear': (add_camera(col, 'CamRear4', (-3.0, 2.6, 1.1), (0.0, 0.0, 0.55), lens=32), (1920, 1080)),
        'top': (add_camera(col, 'CamTop4', (0, 0, 8), rot=(0, 0, 0), ortho=2.9), (1920, 1080)),
    }
    suffix = f'-{TAG}' if TAG else ''
    for k, (cam, res) in cams.items():
        if VIEWS and k not in VIEWS:
            continue
        scene.camera = cam
        scene.render.resolution_x, scene.render.resolution_y = res
        scene.render.filepath = os.path.join(RENDER_DIR, f'bike4-{k}{suffix}.png')
        bpy.ops.render.render(write_still=True)
        print('rendered', scene.render.filepath)


# ---------------------------------------------------------------- main
def main():
    scene = reset()
    M = make_materials()
    tank = build_tank(M)
    conform_tank(tank)
    PARTS.append(tank)
    build_armour(M, tank)
    build_front(M)
    build_bars(M)
    dash = build_dash(M)
    build_capsules(M)
    build_bay(M)
    tail = build_rear(M)
    build_lamps(M)
    # rivets along the tail's plates and ridge
    trees = bvh([tail] + [o for o in PARTS if o.name.startswith('Skirt')])
    for sgn in (-1, 1):
        rivet_line(trees, [(-0.36, sgn * 0.19, 0.80), (-0.55, sgn * 0.21, 0.83), (-0.72, sgn * 0.21, 0.84), (-0.84, sgn * 0.20, 0.835)],
                   Vector((0, sgn, 0.2)), M['rust'], spacing=0.045)
        rivet_line(trees, [(-0.40, sgn * 0.12, 0.86), (-0.62, sgn * 0.13, 0.90), (-0.84, sgn * 0.12, 0.89)], Vector((0, 0, 1)), M['armour'], spacing=0.05)
        rivet_line(trees, [(-0.30, sgn * 0.21, 0.66), (-0.45, sgn * 0.23, 0.60), (-0.60, sgn * 0.23, 0.68)], Vector((0, sgn, 0)), M['armour'], spacing=0.04)
    STUDS.objects('Rivets')

    extras = build_button(M, tank)
    body_parts = list(PARTS)
    centre_prof, side_prof = track_profile(body_parts)
    cen = bpy.data.objects['ButtonCentre']
    cen['TRACK_D'] = TRACK_D
    cen['TRACK_CENTRE'] = centre_prof
    cen['TRACK_SIDE'] = side_prof
    ref = json.load(open(os.path.join(ALIGN, 'bike1-tank.json')))
    print('TRACK_CENTRE', centre_prof)
    print('TRACK_SIDE  ', side_prof)
    print('TRACK vs bike.glb max |diff| centre', round(max(abs(a - b) for a, b in zip(centre_prof, ref['TRACK_CENTRE'])), 4),
          'side', round(max(abs(a - b) for a, b in zip(side_prof, ref['TRACK_SIDE'])), 4))

    per = {}
    for o in PARTS:
        per[o.name.split('.')[0]] = per.get(o.name.split('.')[0], 0) + tri_count(o)
    print('PARTS', sorted(per.items(), key=lambda kv: -kv[1]))
    body = join('Bike4', PARTS)
    PARTS.clear()

    wf = build_wheel('Wheel4Front', F_R, F_W, M, front=True)
    wr = build_wheel('Wheel4Rear', R_R, R_W, M, front=False)
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

    if '--nobake' not in ARGS:
        bake_vertex_colours([body, wf, wr])

    meshes = (body, wf, wr, dash, *[e for e in extras if e.type == 'MESH'])
    counts = {o.name: tri_count(o) for o in meshes}
    print('TRIANGLES', counts, 'total', sum(counts.values()))
    for n in ('ButtonCentre', 'RiderEye'):
        print('ANCHOR', n, [list(map(lambda v: round(v, 6), r)) for r in bpy.data.objects[n].matrix_local])

    scene.camera = None
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)

    bpy.ops.object.select_all(action='DESELECT')
    for o in (body, wf, wr, dash, *extras):
        o.select_set(True)
    os.makedirs(os.path.dirname(GLB_OUT), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=GLB_OUT, export_format='GLB', use_selection=True, export_apply=True, export_yup=True,
                              export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
                              export_draco_position_quantization=13, export_draco_normal_quantization=10,
                              export_draco_texcoord_quantization=10, export_draco_color_quantization=8,
                              export_vertex_color='ACTIVE', export_image_format='JPEG', export_jpeg_quality=80,
                              export_cameras=False, export_lights=False, export_extras=True)
    print('GLB', GLB_OUT, os.path.getsize(GLB_OUT))
    if DO_RENDER:
        col = setup_render(scene)
        show_vertex_colours()
        render_views(scene, col, body)


main()
