"""Fifth zone's bike: a low, long biomech sportbike in chipped bone-ivory steel (art/reference/concept-bike5.png, the
side view; the rider's view at the bottom of concept-core-servers.png and concept-core-gate.png; the rear three-quarter
in concept-core-plaza.png).

Builds the bike from scratch, saves art/bike5.blend and exports public/models/bike5.glb (Draco).
Run:   blender --background --factory-startup --python art/build-bike5.py
Review renders into art/renders/bike5-*.png (concept, rider, riderdash, side, hero, plaza, rear, top):
       blender --background --factory-startup --python art/build-bike5.py -- --render [--tag NAME] [--views concept,rider]
       [--samples N] [--nobake]

Same frame as bike.glb (art/build-bike.py) so the site can swap them in place: metres, Z up, front toward +X, ground
z=0, origin on the ground midway between the contacts, wheelbase 1.56 m, the same axles, the root rolled 5 deg toward
+Y onto the kickstand. Objects: Bike5 (body), Wheel5Front / Wheel5Rear (children, origin on the axle, spin about local
Y), Bike5Button + Bike5ButtonGlyph (the throttle pill on the tank, three forward chevrons), Bike5Dash (the screen, UV
0-1, u right and v up from the rider's seat), and the ButtonCentre / RiderEye empties at bike.glb's exact bike-local
transforms. The boost pod sits at runtime about ButtonCentre + (-0.015 along, 0.03 up, 0.19 to the rider's right):
that space is kept clear (main() checks it).

The concept is longer in its wheelbase than the contract's axles allow, so art/align-bike5/ maps it by eye: x and z are
scaled apart (concept-map.json: its axles land on ours, its tyres' height on ours), the fairing and the tail are
stretched on their own to keep their length, and compare.py warps a ConceptCam render back onto the concept to check it.
The parts here are traced in the concept's pixels (C(), trace()). What the anchors force away from the concept: the
tank under the pill stands higher than the concept's shoulders, and the windscreen's tip stops short of the pill.

Materials (plain Principled BSDFs, the site tunes them): Bike5Armour (the bone-ivory steel, a chipped, stained texture),
Bike5Hull (dark stained steel for the tank, the bars' blocks and the dash), Bike5Steel (polished forks, hub), Bike5Disc,
Bike5Metal (the dark mass), Bike5Spike, Bike5Hose (a striped corrugation texture), Bike5Tyre, Bike5Seat, Bike5Glass and Bike5Smoke (alpha-blended, the
site sets depthWrite), Bike5Fluid (the tank's fluid, a painted emissive texture), Bike5Vein, Bike5Tissue, Bike5Tube,
Bike5Led, Bike5Tail, Bike5Dash, Bike5Button, Bike5ButtonGlyph. Bike5 and the wheels carry baked ambient occlusion and
grime in their vertex colours (COLOR_0, per vertex, multiplied into the base colour by three). Pass --nobake to skip the
AO bake for quick geometry checks.
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
BLEND_OUT = os.path.join(HERE, 'bike5.blend')
GLB_OUT = os.path.join(ROOT, 'public', 'models', 'bike5.glb')
RENDER_DIR = os.path.join(HERE, 'renders')
ALIGN = os.path.join(HERE, 'align-bike5')

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
F_W, R_W = 0.24, 0.36
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
# the site's rider camera (components/three/journey-camera.tsx): back and down from RiderEye, 15 deg down, 70 deg fov
RIDER_CAM = Vector((0.08 - 0.22, 0.0, 1.52 - 0.07))
RIDER_PITCH, RIDER_FOV = math.radians(15), math.radians(70)
DASH_C = Vector((0.655, 0.0, 0.962))  # dash screen centre
FORK_TOP = Vector((0.585, 0.0, 0.95))
FORK_Y = 0.150
F_DISC_Y = 0.118
SWING_Y = 0.252
R_SPROCKET_Y = 0.152
R_DISC_Y = -0.205

# the concept's pixels to bike metres (art/align-bike5/concept-map.json): its axles on ours, its tyres' height on ours
_MAP = json.load(open(os.path.join(ALIGN, 'concept-map.json')))
SX, SZ, PX_F, PY_G = _MAP['sx'], _MAP['sz'], _MAP['px_front_axle'], _MAP['py_ground']


def X(px):
    return F_AXLE.x - (px - PX_F) * SX


def Z(py):
    return (PY_G - py) * SZ


def FX(px):
    """The fairing's x: stretched forward over the front tyre, its tip kept off the pill."""
    return 0.985 - (px - 212) * 0.000905


def TX(px):
    """The tail's x: its blade stretched back to the tyre's edge."""
    return X(px) if px <= 1450 else X(1450) - (px - 1450) * 0.00176


def C(px, py, y=0.0, fx=X):
    return Vector((fx(px), y, Z(py)))


def yfn(*pairs):
    """A piecewise-linear y(px)."""
    def f(px):
        if px <= pairs[0][0]:
            return pairs[0][1]
        for (a, ya), (b, yb) in zip(pairs, pairs[1:]):
            if px <= b:
                return ya + (yb - ya) * (px - a) / (b - a)
        return pairs[-1][1]
    return f


def trace(pairs, y=0.0, fx=X):
    return [C(px, py, y(px) if callable(y) else y, fx) for px, py in pairs]


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
               alpha=1.0, transmission=0.0, image=None, emit_image=None):
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
    if emit_image is not None:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = emit_image
        tex.interpolation = 'Linear'
        nt.links.new(tex.outputs['Color'], b.inputs['Emission Color'])
        b.inputs['Emission Strength'].default_value = emit_strength
    m.diffuse_color = (*base, 1)
    return m


def make_textures():
    """Generated, tiling: the chipped, stained bone-ivory steel (512 px), the dark stained steel of the tank and the bars'
    blocks (256), and the tank's fluid (256, planar: x along the tank, z up it: bright at the bottom, murky above, a tree
    of veins through it). Packed into the .blend; exported as JPEG."""
    import numpy as np

    def tile_noise(n, beta, seed, stretch=(1.0, 1.0)):
        """Tiling 1/f^beta noise, unit variance. `stretch` shortens the waves across one axis (streaks along the other)."""
        r = np.random.default_rng(seed)
        fy = np.fft.fftfreq(n)[:, None] * stretch[0]
        fx = np.fft.rfftfreq(n)[None, :] * stretch[1]
        f = np.sqrt(fx * fx + fy * fy)
        f[0, 0] = 1.0
        spec = (r.normal(size=f.shape) + 1j * r.normal(size=f.shape)) / f ** beta
        spec[0, 0] = 0
        out = np.fft.irfft2(spec, s=(n, n))
        return out / out.std()

    def mix(a, b, t):
        t = np.clip(t, 0, 1)[..., None]
        return a * (1 - t) + b * t

    def lines(img, rng, count, colour, n, len_range=(8, 60), ang_sd=0.5, strength=(0.2, 0.6), width=1):
        for _ in range(count):
            x0, y0 = rng.integers(0, n, 2)
            L = rng.integers(*len_range)
            ang = rng.normal(0, ang_sd) + rng.choice((0.0, math.pi / 2))
            br = rng.uniform(*strength)
            for k in range(L):
                x = int(x0 + k * math.cos(ang)) % n
                y = int(y0 + k * math.sin(ang)) % n
                for w in range(width):
                    img[(y + w) % n, x] = img[(y + w) % n, x] * (1 - br) + colour * br

    def erode(mask):
        return mask & np.roll(mask, 1, 0) & np.roll(mask, -1, 0) & np.roll(mask, 1, 1) & np.roll(mask, -1, 1)

    n = 512
    rng = np.random.default_rng(5)
    big, mid, fine = tile_noise(n, 1.9, 1), tile_noise(n, 1.4, 2), tile_noise(n, 0.9, 3)
    # bone: pale ivory steel, clouded
    img = mix(np.array(srgb('#8c8876')), np.array(srgb('#c4c0ad')), big * 0.22 + mid * 0.1 + 0.55)
    # stains: long olive-brown runs, along v, gathered in patches
    runs = tile_noise(n, 1.5, 4, stretch=(0.18, 1.0))
    patches = tile_noise(n, 2.2, 5)
    img = mix(img, np.array(srgb('#6a5a35')), np.clip(runs * 0.8 + patches * 0.6 - 1.15, 0, 1) * 0.62)
    # scratches, fine and dark
    lines(img, rng, 90, np.array(srgb('#4a4232')), n, (10, 70), strength=(0.25, 0.6))
    lines(img, rng, 40, np.array(srgb('#efe9d6')), n, (8, 40), strength=(0.15, 0.4))
    # chips: dark bare metal, a rust halo round each, in clusters
    cluster = tile_noise(n, 2.0, 6)
    chipf = tile_noise(n, 1.0, 7)
    chips = chipf + cluster * 0.4 > 2.0
    halo = chipf + cluster * 0.4 > 1.8
    img = mix(img, np.array(srgb('#4c3218')), halo.astype(float) * 0.75)
    img = mix(img, np.array(srgb('#17130f')), chips.astype(float) * 0.97)
    specks = fine + cluster * 0.3 > 2.8
    img = mix(img, np.array(srgb('#1c1712')), specks.astype(float) * 0.9)
    armour = img

    n2 = 256
    big, mid, fine = tile_noise(n2, 1.9, 11), tile_noise(n2, 1.3, 12), tile_noise(n2, 0.9, 13)
    img = mix(np.array(srgb('#26221d')), np.array(srgb('#4b4338')), big * 0.3 + mid * 0.2 + 0.45)
    img = mix(img, np.array(srgb('#4a2a20')), np.clip(mid * 0.7 + big * 0.6 - 1.0, 0, 1) * 0.65)  # rust, a little red
    img = mix(img, np.array(srgb('#7a7263')), np.clip(fine * 0.8 + mid * 0.4 - 1.1, 0, 1) * 0.7)  # worn through
    lines(img, rng, 40, np.array(srgb('#6a6254')), n2, (6, 24), strength=(0.15, 0.35))
    hull = img

    # the fluid: warped cells, bright low down
    n3 = 512
    a, b = tile_noise(n3, 1.7, 21), tile_noise(n3, 1.7, 22)
    yy, xx = np.mgrid[0:n3, 0:n3]
    wx = ((xx + a * 28) % n3).astype(int)
    wy = ((yy + b * 28) % n3).astype(int)
    swirl = tile_noise(n3, 1.35, 23)[wy, wx]
    v = yy / (n3 - 1)  # row 0 is the image's top: v=0 here is up the tank
    glow = np.clip((v - 0.68) / 0.27, 0, 1) ** 1.4
    img = mix(np.array(srgb('#030906')), np.array(srgb('#124212')), swirl * 0.3 + 0.08 + v * 0.42)
    img = mix(img, np.array(srgb('#9ad828')), glow * (0.9 + swirl * 0.15))
    # tissue: convoluted, red-brown, through the upper part towards the front
    u = xx / (n3 - 1)
    folds = 1 - np.abs(tile_noise(n3, 1.8, 24)[wy, wx]) * 2.4
    where = np.exp(-(((u - 0.38) / 0.3) ** 2 + ((v - 0.34) / 0.26) ** 2))
    img = mix(img, np.array(srgb('#3a2018')), np.clip(folds, 0, 1) * where * 1.1)
    img = mix(img, np.array(srgb('#142c10')), np.clip(-folds, 0, 1) * where * 0.5)

    # veins: a tree up from the bottom, dark red-brown through the glow
    def stroke(x, y, ang, life, width, depth):
        while life > 0:
            ang += rng.normal(0, 0.28)
            x += math.cos(ang) * 4.4
            y += math.sin(ang) * 4.4
            life -= 1
            iw = max(1, int(round(width)))
            ix, iy = int(x), int(y)
            for ox in range(-iw // 2, iw // 2 + 1):
                for oy in range(-iw // 2, iw // 2 + 1):
                    if 0 <= iy + oy < n3:
                        img[iy + oy, (ix + ox) % n3] = np.array(srgb('#3a0a07'))
            width = max(1.4, width * 0.985)
            if depth > 0 and rng.random() < 0.14:
                stroke(x, y, ang + rng.choice((-1, 1)) * rng.uniform(0.4, 1.0), life * rng.uniform(0.5, 0.9), width * 0.65, depth - 1)
    for sx_ in (35, 80, 125, 165, 210):
        stroke(sx_ * 2, n3 - 24, -math.pi / 2 + rng.normal(0, 0.3), 70, 6.0, 5)
    # (The site lights it at 2.2, untonemapped.)
    fluid = img * 0.8

    # the hoses' corrugation, across v: a dark valley and a lit ridge, 24 to the texture's length
    n4 = 96
    stripe = 0.5 + 0.5 * np.cos(np.arange(n4) / n4 * TAU * 24)
    hose = np.ones((n4, 8, 3)) * (np.array(srgb('#050504'))[None, None] + (np.array(srgb('#2c2721')) - np.array(srgb('#050504')))[None, None] * (stripe ** 2)[:, None, None])

    out = {}
    for name, arr in (('Bike5ArmourTex', armour), ('Bike5HullTex', hull), ('Bike5FluidTex', fluid), ('Bike5HoseTex', hose)):
        h, w = arr.shape[:2]
        im = bpy.data.images.new(name, w, h, alpha=False)
        px = np.ones((h, w, 4), dtype=np.float32)
        lin = np.clip(arr, 0, 1)[::-1]  # (Blender's rows run bottom-up)
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
    # (The site sets each glow's intensity by its kind, BIKE_GLOWS, over the exported colour: these are exported at 1,
    # so the factor stays what's written here, and setup_render puts the site's numbers on for the review.)
    M = {
        'armour': principled('Bike5Armour', srgb('#c4c1b2'), metallic=0.42, rough=0.34, coat=0.25, coat_rough=0.16, image=tex['Bike5ArmourTex']),
        'hull': principled('Bike5Hull', srgb('#3a342c'), metallic=0.65, rough=0.42, image=tex['Bike5HullTex']),
        'steel': principled('Bike5Steel', srgb('#94928a'), metallic=0.95, rough=0.22),
        'disc': principled('Bike5Disc', srgb('#57554f'), metallic=0.9, rough=0.5),
        'metal': principled('Bike5Metal', srgb('#191816'), metallic=0.7, rough=0.48),
        'spike': principled('Bike5Spike', srgb('#141310'), metallic=0.6, rough=0.24, coat=0.4, coat_rough=0.1),
        'hose': principled('Bike5Hose', srgb('#26231f'), metallic=0.35, rough=0.32, coat=0.3, coat_rough=0.2, image=tex['Bike5HoseTex']),
        'tyre': principled('Bike5Tyre', srgb('#211f1d'), rough=0.52, spec=0.45),
        'seat': principled('Bike5Seat', srgb('#141312'), rough=0.58, coat=0.1, coat_rough=0.4),
        'glass': principled('Bike5Glass', (0.1, 0.15, 0.11), rough=0.04, coat=0.6, coat_rough=0.04, alpha=0.16),
        'smoke': principled('Bike5Smoke', srgb('#14170f'), rough=0.05, coat=1.0, coat_rough=0.02, alpha=0.5),
        'fluid': principled('Bike5Fluid', srgb('#17300f'), rough=0.25, emit=(1, 1, 1), emit_strength=2.2, emit_image=tex['Bike5FluidTex']),
        'vein': principled('Bike5Vein', srgb('#2e0807'), rough=0.35, coat=0.4, coat_rough=0.15, emit=srgb('#1a0403'), emit_strength=1.0),
        'tissue': principled('Bike5Tissue', srgb('#4a2b20'), rough=0.6),
        'tube': principled('Bike5Tube', srgb('#2a6a18'), rough=0.1, coat=0.8, coat_rough=0.03, emit=srgb('#5fd81e'), emit_strength=1.0),
        'led': principled('Bike5Led', srgb('#6cc632'), rough=0.2, emit=(0.06, 0.45, 0.015), emit_strength=1.0),
        'tail': principled('Bike5Tail', srgb('#5a0804'), rough=0.2, emit=srgb('#ff2412'), emit_strength=4.0),
        # dark green glass that glows; the site draws the speed and logo into it
        'dash': principled('Bike5Dash', (0.01, 0.03, 0.012), rough=0.08, coat=1.0, coat_rough=0.02, emit=srgb('#2cff5a'), emit_strength=0.3),
        # the throttle pill: green glass; the glyph brighter. The site drives both.
        'button': principled('Bike5Button', srgb('#1c4a12'), rough=0.06, coat=1.0, coat_rough=0.02, emit=srgb('#46e02a'), emit_strength=0.3),
        'glyph': principled('Bike5ButtonGlyph', srgb('#d8ffb0'), rough=0.3, emit=srgb('#b0ff70'), emit_strength=4.0),
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


M_NICK = [None]


def hose2(name, ctrl, r, mat, pitch=0.021, sides=6, track=True, ribs=True):
    """A corrugated hose: its material's stripes, and (if `ribs`, up close) two rings a rib in the mesh as well."""
    L = path_length(ctrl)
    if not ribs:
        return tube(name, ctrl, r, mat, sides=sides, segs=max(6, int(L / 0.035)), track=track)
    n = max(4, int(L / pitch))
    return tube(name, ctrl, lambda s: r * (1 - 0.12 * abs(math.cos(math.pi * n * s))), mat, sides=sides, segs=n * 2, track=track)


# (across a blade's face: position, height. Flat in the middle, a tight bevel at the rims.)
BLADE_FACE = ((0.0, 0.0), (0.04, 0.5), (0.16, 0.86), (0.5, 1.0), (0.84, 0.86), (0.96, 0.5), (1.0, 0.0))


def blade(name, upper, lower, mat, n=26, m=4, bulge=0.012, back=0.004, out=1, track=True, nicks=0):
    """A long armour blade between two traced edges, running together at its tips: a flat crowned face with tight rims, a
    flatter back. `out` is the sign of y its face turns to. Its width runs across the rings, its length along them. Its rim
    vertices are marked Wear, for the grime."""
    du, _ = resample(catmull(upper, 12), n + 1)
    dl, _ = resample(catmull(lower, 12), n + 1)
    mids = [a.lerp(b, 0.5) for a, b in zip(du, dl)]
    rings = []
    rim = []
    for i in range(n + 1):
        U, L = du[i], dl[i]
        W = L - U
        wl = W.length
        if wl < 0.003:
            d = W.normalized() if wl > 1e-6 else Vector((0, 0, 1))
            U, L = mids[i] - d * 0.0015, mids[i] + d * 0.0015
            W = L - U
            wl = 0.003
        T = (mids[min(i + 1, n)] - mids[max(i - 1, 0)]).normalized()
        Nv = T.cross(W)
        Nv = Nv.normalized() if Nv.length > 1e-9 else Vector((0, out, 0))
        if Nv.y * out < 0:
            Nv = -Nv
        k = min(1.0, wl / 0.04)
        ring = [U.lerp(L, u) + Nv * bulge * k * h for u, h in BLADE_FACE]
        ring.append(U.lerp(L, 0.5) - Nv * back * k)
        rings.append(ring)
        rim += [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        if nicks and 2 < i < n - 2 and i % nicks == 0:
            # little dark studs along its edges, as if it were tacked on
            stud2(U.lerp(L, 0.09) + Nv * bulge * k * 0.75, Nv, M_NICK[0], r=0.0048, h=0.003)
            if i % (2 * nicks) == 0:
                stud2(U.lerp(L, 0.91) + Nv * bulge * k * 0.75, Nv, M_NICK[0], r=0.0042, h=0.003)
    ob = rings_mesh(name, rings, mat, closed_ring=True, cap0='ngon', cap1='ngon', track=track)
    wear = ob.data.attributes.new('Wear', 'FLOAT', 'POINT')
    wear.data.foreach_set('value', rim + [0.0] * (len(ob.data.vertices) - len(rim)))
    return ob


def both(ob):
    mirror_obj(ob)
    return ob


def stud2(p, n, mat, r=0.0055, h=0.0035):
    """A stud and its mirror across the centre line."""
    p, n = Vector(p), Vector(n)
    STUDS.add(p, n, mat, r=r, h=h)
    STUDS.add(Vector((p.x, -p.y, p.z)), Vector((n.x, -n.y, n.z)), mat, r=r, h=h)


# ---------------------------------------------------------------- wheels
def arc_strip(name, r0, r1, y0, y1, a0, a1, mat, segs=8):
    """A lit segment on a wheel's face, from (r0, y0) to (r1, y1) across and a0 to a1 round, a little proud in the middle."""
    rings = []
    for i in range(segs + 1):
        a = a0 + (a1 - a0) * i / segs
        c, s = math.cos(a), math.sin(a)
        rm, ym = (r0 + r1) / 2, (y0 + y1) / 2 + (0.003 if y0 > 0 else -0.003)
        rings.append([Vector((r * c, y, r * s)) for r, y in ((r0, y0), (rm, ym), (r1, y1))])
    return rings_mesh(name, rings, mat, closed_ring=False, cap0=None, cap1=None)


def lit_arcs(name, M, yl, rim_r, sgn, phase):
    """Three groups of two glowing dashes round the rim's shoulder."""
    r0, r1 = rim_r - 0.031, rim_r - 0.019
    y0, y1 = sgn * (yl - 0.0205), sgn * (yl - 0.0115)
    for g in range(3):
        a = phase + TAU * g / 3
        for k in range(2):
            a0 = a + k * math.radians(24)
            arc_strip(name + 'Arc', r0, r1, y0, y1, a0, a0 + math.radians(22), M['led'])


def build_wheel(name, radius, width, M, front):
    global PARTS
    saved, PARTS = PARTS, []
    hw = width / 2
    rim_r = 0.208
    if front:
        tyre(name + 'Tyre', radius, width, rim_r, M['tyre'], 110, 18, grooves=11, chevron=0.9, depth=0.004)
    else:
        tyre(name + 'Tyre', radius, width, rim_r, M['tyre'], 120, 20, grooves=12, chevron=1.0, depth=0.005)
    yl = hw * 0.80
    # the rim's lip, a thin bright line, and the dark dished wheel inside it
    prof = [(rim_r + 0.010, yl + 0.002), (rim_r + 0.003, yl + 0.009), (rim_r - 0.01, yl + 0.006), (rim_r - 0.016, yl - 0.009)]
    lathe(name + 'Lip', prof, M['steel'], 64, closed_prof=False)
    ob2 = lathe(name + 'Lip', [(r, -y) for r, y in prof], M['steel'], 64, closed_prof=False)
    ob2.data.flip_normals()
    for sgn in (-1, 1):
        face = [(rim_r - 0.016, sgn * (yl - 0.009)), (rim_r - 0.04, sgn * (yl - 0.028)), (0.145, sgn * (yl * 0.5)),
                (0.09, sgn * (yl * 0.46)), (0.078, sgn * (yl * 0.58)), (0.05, sgn * (yl * 0.66)), (0.0, sgn * (yl * 0.68))]
        f = lathe(name + 'Face', face, M['metal'], 40, closed_prof=False)
        if sgn < 0:
            f.data.flip_normals()
        lit_arcs(name, M, yl, rim_r, sgn, 0.5 if front else 2.1)
        # spokes: dark ribs across the dish
        for k in range(6):
            ph = TAU * k / 6 + 0.3
            d = Vector((math.cos(ph), 0, math.sin(ph)))
            a, b = d * 0.08 + Vector((0, sgn * yl * 0.6, 0)), d * 0.17 + Vector((0, sgn * (yl - 0.03), 0))
            tube(name + 'Spoke', [a, b], 0.009, M['spike'], sides=5, segs=2, squash=0.6)
    # axle and nuts, out past the fork legs / swingarm
    ny = (FORK_Y if front else SWING_Y) + 0.03
    tube(name + 'Axle', [Vector((0, -ny, 0)), Vector((0, ny, 0))], 0.016, M['steel'], sides=8, segs=2)
    for sgn in (-1, 1):
        lathe_y(name + 'Nut', [(0.0, sgn * (ny + 0.012)), (0.024, sgn * (ny + 0.012)), (0.027, sgn * ny), (0.027, sgn * (ny - 0.014))], M['steel'], 6, (0, 0, 0))
    if front:
        # big drilled discs, one each side
        for sgn in (-1, 1):
            dy = sgn * F_DISC_Y
            r0, r1 = 0.086, 0.172
            f_ = dy + sgn * 0.003
            prof = [(r0, dy - sgn * 0.003), (r1, dy - sgn * 0.003), (r1, dy), (r1 - 0.0015, f_), (r1 - 0.004, f_), (r0 + 0.004, f_), (r0 + 0.0015, f_), (r0, dy)]
            lathe(name + 'Disc', prof, M['disc'], 48)
            for ring, count in ((0.105, 18), (0.130, 22), (0.155, 26)):
                for k in range(count):
                    ph = TAU * k / count + ring * 7
                    STUDS_W.add(Vector((ring * math.cos(ph), dy + sgn * 0.0028, ring * math.sin(ph))), Vector((0, sgn, 0)), M['hose'], r=0.0068, h=0.0008, sides=5)
            tube(name + 'Carrier', [Vector((0, sgn * yl * 0.6, 0)), Vector((0, dy, 0))], 0.075, M['metal'], sides=16, segs=2)
            lathe_y(name + 'Hub', [(0.086, dy), (0.07, dy + sgn * 0.004), (0.045, dy + sgn * 0.012), (0.0, dy + sgn * 0.014)], M['spike'], 20, (0, 0, 0))
            for k in range(5):
                ph = TAU * k / 5
                STUDS_W.add(Vector((0.072 * math.cos(ph), dy + sgn * 0.004, 0.072 * math.sin(ph))), Vector((0, sgn, 0)), M['steel'], r=0.007, h=0.004)
    else:
        # the big polished hub, a dome out to the swingarm, the sprocket behind it, on the chain side
        dome = [(0.158, yl * 0.5), (0.156, 0.13), (0.146, 0.172), (0.125, 0.203), (0.09, 0.223), (0.05, 0.232), (0.0, 0.234)]
        lathe_y(name + 'Dome', dome, M['steel'], 48, (0, 0, 0))
        sy = R_SPROCKET_Y
        teeth = 40
        ol = []
        for k in range(teeth * 2):
            ph = TAU * k / (teeth * 2)
            rr = 0.170 if k % 2 else 0.160
            ol.append((rr * math.cos(ph), rr * math.sin(ph)))
        bm = bmesh.new()
        f = bm.faces.new([bm.verts.new((x, sy - 0.003, z)) for x, z in ol])
        ext = bmesh.ops.extrude_face_region(bm, geom=[f])
        bmesh.ops.translate(bm, verts=[e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)], vec=(0, 0.006, 0))
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new(name + 'Sprocket')
        bm.to_mesh(me)
        bm.free()
        me.uv_layers.new(name='UVMap')
        me.materials.append(M['metal'])
        sp = bpy.data.objects.new(name + 'Sprocket', me)
        bpy.context.scene.collection.objects.link(sp)
        PARTS.append(sp)
        # the plain dish on the other side, and its disc
        lathe_y(name + 'Dish', [(r, -y) for r, y in dome[:5]] + [(0.0, -0.205)], M['metal'], 32, (0, 0, 0)).data.flip_normals()
        dy = R_DISC_Y
        lathe(name + 'Disc', [(0.09, dy - 0.003), (0.145, dy - 0.003), (0.145, dy + 0.003), (0.09, dy + 0.003)], M['disc'], 40)
        # bolts round the hub's crown
        for k in range(10):
            ph = TAU * k / 10
            STUDS_W.add(Vector((0.1 * math.cos(ph), 0.216, 0.1 * math.sin(ph))), Vector((0.4 * math.cos(ph), 1, 0.4 * math.sin(ph))), M['metal'], r=0.006, h=0.004)
    STUDS_W.objects(name + 'Studs')
    STUDS_W.verts.clear()
    STUDS_W.faces.clear()
    wheel = join(name, PARTS)
    PARTS = saved
    return wheel


STUDS_W = Studs()


# ---------------------------------------------------------------- the tank under the pill
TANK = [
    key(0.635, 0.885, 0.010, 0.010, 0.010, e=2.2),
    key(0.615, 0.885, 0.05, 0.035, 0.05, e=2.2),
    key(0.57, 0.875, 0.10, 0.075, 0.12, e=2.2),
    key(0.50, 0.845, 0.16, 0.115, 0.12, e=2.2),
    key(0.405, 0.826, 0.19, 0.142, 0.115, e=2.2),
    key(0.30, 0.822, 0.19, 0.13, 0.11, e=2.2),
    key(0.22, 0.82, 0.17, 0.108, 0.09, e=2.2),
    key(0.13, 0.822, 0.125, 0.078, 0.06, e=2.3),
    key(0.05, 0.825, 0.07, 0.04, 0.03, e=2.4),
    key(0.01, 0.825, 0.012, 0.012, 0.012, e=2.4),
]


def build_tank(M):
    for k in TANK:
        k.pop('t', None)
    tank = loft('Tank', TANK, M['hull'], 60, 40, cap0='point', cap1='point', subsurf=0, track=False)
    tank.name = tank.data.name = 'Tank'
    return tank


def tank_band(name, x0, x1, grow, mat, a0=-math.pi / 2, a1=1.5 * math.pi, closed=True, n=36):
    keys = []
    for x in (x0, (x0 + x1) / 2, x1):
        c, w, ht, hb, e = keyed_at(TANK, x)
        keys.append(dict(c=c, w=w + grow, ht=ht + grow, hb=hb + grow, e=e, a0=a0, a1=a1))
    keys[1]['w'] += 0.004
    keys[1]['ht'] += 0.004
    keys[1]['hb'] += 0.004
    return loft(name, keys, mat, 4, n, closed=closed, cap0='ngon' if closed else None, cap1='ngon' if closed else None, subsurf=0,
                solidify=0.0 if closed else 0.005)


def build_tank_dressing(M, tank):
    """What the rider sees of the tank: the lit well the pill sits in, ridged bands either end of it, rivets."""
    H, S, T = M['hull'], M['steel'], M['tube']
    # the well: a green-lit inlay under the pill, a little wider and longer than it
    keys = []
    for x, half in ((0.548, 0.012), (0.535, 0.045), (0.505, 0.068), (0.405, 0.074), (0.31, 0.074), (0.285, 0.066), (0.268, 0.045), (0.255, 0.012)):
        c, w, ht, hb, e = keyed_at(TANK, x)
        a = math.acos(min(1.0, (half / (w + 0.003)) ** (e / 2)))  # section(): y = w cos^(2/e)
        keys.append(dict(c=c, w=w + 0.003, ht=ht + 0.003, hb=hb + 0.003, e=e, a0=a, a1=math.pi - a))
    PARTS.append(loft('Well', keys, T, 26, 10, closed=False, subsurf=0))
    # a dark lip round it
    trees0 = bvh([tank])
    lip = []
    for k in keys:
        ang = k['a0']
        cs, sn = math.cos(ang), math.sin(ang)
        lip.append((k['c'].x, (k['w'] + 0.002) * cs ** (2 / k['e'])))
    ring = [(x, y) for x, y in lip] + [(x, -y) for x, y in reversed(lip)]
    ring.append(ring[0])
    pts = []
    for x, y in ring:
        h = cast(trees0, (x, y, 1.5), (0, 0, -1))
        if h:
            pts.append(h[0] + h[1] * 0.004)
    tube('WellLip', pts, 0.0058, M['metal'], sides=6, segs=48)
    for g_ in (0.03,):
        pts = []
        for x, y in ring:
            h = cast(trees0, (x + (0.018 if x > 0.405 else -0.018), y + math.copysign(g_ * (1 if abs(y) > 0.01 else 0), y), 1.5), (0, 0, -1))
            if h:
                pts.append(h[0] + h[1] * 0.002)
        tube('WellRidge', pts, 0.0042, M['hull'], sides=5, segs=40)
    # the well's riveted frame, dark bands across the tank either end, stepping down
    for x0, x1, g in ((0.575, 0.562, 0.010), (0.598, 0.586, 0.007), (0.21, 0.195, 0.010), (0.175, 0.16, 0.007), (0.135, 0.12, 0.005)):
        PARTS.append(tank_band('TankBand', x0, x1, g, M['metal'], n=28))
    trees = bvh([tank])
    for sgn in (-1, 1):
        for i in range(11):
            x = 0.53 - 0.32 * i / 10
            h = cast(trees, (x, sgn * 0.097, 1.5), (0, 0, -1))
            if h:
                STUDS.add(h[0], h[1], M['metal'], r=0.0058, h=0.0035)
    for x, cnt in ((0.57, 16), (0.2, 22), (0.162, 20)):
        c, w, ht, hb, e = keyed_at(TANK, x)
        for k in range(cnt):
            a = math.pi * (k + 0.5) / cnt
            cs, sn = math.cos(a), math.sin(a)
            yy = (w + 0.012) * math.copysign(abs(cs) ** (2 / e), cs)
            zz = (ht + 0.012) * abs(sn) ** (2 / e)
            STUDS.add(c + Vector((0, yy, zz)), Vector((0, cs, sn)), M['metal'], r=0.005, h=0.0035)


# ---------------------------------------------------------------- the front: fairing, screen, forks, dash, bars
SCREEN_EDGE = [(0.985, 0.75), (0.90, 0.837), (0.822, 0.87), (0.75, 0.90), (0.672, 0.945), (0.60, 1.075)]
SCREEN_CROWN = [C(*p, fx=FX) for p in ((212, 290), (250, 250), (300, 195), (350, 160), (400, 135), (450, 118), (500, 103), (560, 92), (632, 75))]


def piecewise(tab, x):
    tab = sorted(tab)
    if x <= tab[0][0]:
        return tab[0][1]
    for (a, ya), (b, yb) in zip(tab, tab[1:]):
        if x <= b:
            return ya + (yb - ya) * (x - a) / (b - a)
    return tab[-1][1]


SCREEN_WIDE, SCREEN_AT = 0.30, 0.77


def screen_w(x):
    """The screen's half-width at bike x: a pointed nose ahead of its widest, a parabola back to the rim's tip."""
    if x >= SCREEN_AT:
        return SCREEN_WIDE * max(0.0, (0.985 - x) / (0.985 - SCREEN_AT)) ** 0.8
    return SCREEN_WIDE * max(0.0, (x - 0.60) / (SCREEN_AT - 0.60)) ** 0.5


def build_screen(M):
    crown = [(p.x, p.z) for p in SCREEN_CROWN]
    rings = []
    nx, ny = 26, 14
    for i in range(nx + 1):
        x = 0.985 - (0.985 - 0.60) * i / nx
        w = max(screen_w(x), 0.0015)
        ze, zc = piecewise(SCREEN_EDGE, x), piecewise(crown, x)
        zc = max(zc, ze + 0.001)
        ring = []
        for j in range(ny + 1):
            s = -1 + 2 * j / ny
            ring.append(Vector((x, s * w, ze + (zc - ze) * (1 - s * s) ** 0.62)))
        rings.append(ring)
    rings_mesh('Screen', rings, M['smoke'], closed_ring=False)
    # its rim: a thin bright line round the back edge, the arch the rider sees
    rim = []
    for i in range(21):
        x = 0.60 + (SCREEN_AT - 0.60) * (i / 20) ** 1.6
        rim.append(Vector((x, screen_w(x), piecewise(SCREEN_EDGE, x))))
    rim[0].y = 0.0
    tube('ScreenRim', list(reversed([Vector((p.x, -p.y, p.z)) for p in rim[1:]])) + rim, 0.0032, M['steel'], sides=5, segs=44)


def build_fairing(M):
    A, Me, Sp = M['armour'], M['metal'], M['spike']
    nose = 212

    def yw(extra):
        return lambda px: max(0.002, screen_w(FX(px)) + extra * min(1.0, (px - nose) / 80))
    both(blade('FairingTop', trace([(212, 290), (300, 232), (400, 195), (500, 172), (552, 163)], yw(-0.003), FX),
               trace([(212, 290), (290, 284), (360, 268), (430, 240), (500, 195), (552, 163)], yw(0.03), FX), A, n=26, bulge=0.012, nicks=7))
    # the cheek behind the slit, down to its spur
    both(blade('FairingCheek', trace([(360, 266), (342, 318), (375, 352), (417, 384)], yfn((340, 0.27), (420, 0.235)), FX),
               trace([(445, 240), (423, 292), (413, 340), (417, 384)], yfn((410, 0.235), (450, 0.25)), FX), A, n=14, bulge=0.012))
    # the chin under the slit, and the slit itself: the slim green headlight
    both(blade('FairingChin', trace([(214, 296), (300, 288), (362, 272)], yw(0.022), FX),
               trace([(224, 322), (300, 326), (372, 350)], yw(0.0), FX), Me, n=14, bulge=0.008))
    both(blade('Slit', trace([(222, 298), (290, 289), (358, 268)], yw(0.034), FX),
               trace([(228, 312), (295, 304), (352, 285)], yw(0.034), FX), M['led'], n=14, bulge=0.004, back=0.001))
    # the mass behind it all, closing the nose
    keys = []
    for x in (0.97, 0.92, 0.84, 0.76, 0.68):
        wd = screen_w(x)
        ze = piecewise(SCREEN_EDGE, x)
        keys.append(key(x, ze - 0.05, max(wd * 0.86, 0.01), 0.03, 0.07 + (0.97 - x) * 0.25, e=2.6))
    loft('Nacelle', keys, Me, 14, 16, cap0='point', cap1='ngon', subsurf=0)


def build_forks(M):
    A, S, Me, Ho = M['armour'], M['steel'], M['metal'], M['hose']
    top = FORK_TOP
    axis = (F_AXLE - top).normalized()
    L = (F_AXLE - top).length
    fy = FORK_Y
    for sgn in (-1, 1):
        t0 = top + Vector((0, sgn * fy, 0))
        tube('ForkUpper', [t0 - axis * 0.02, t0 + axis * L * 0.46], 0.038, Me, sides=14, segs=5)
        tube('ForkCollar', [t0 + axis * L * 0.46, t0 + axis * L * 0.52], 0.042, S, sides=14, segs=2)
        tube('ForkSlider', [t0 + axis * L * 0.50, t0 + axis * L * 0.76], 0.027, S, sides=14, segs=4)
        tube('ForkSeal', [t0 + axis * L * 0.76, t0 + axis * L * 0.80], 0.038, S, sides=14, segs=2)
        tube('ForkFoot', [t0 + axis * L * 0.80, t0 + axis * L * 1.03], (0.031, 0.026), Ho, sides=12, segs=3)
        # the axle clamp, a steel plate reaching back to the caliper
        a0 = F_AXLE + Vector((0, sgn * fy, 0))
        tube('AxleClamp', [a0 + Vector((0, 0, -0.03)), a0 + Vector((0, 0, 0.04))], 0.034, S, sides=10, segs=2)
        blade('CaliperArm', [a0 + Vector((0.02, sgn * 0.002, 0.03)), a0 + Vector((-0.15, sgn * -0.02, 0.04))],
              [a0 + Vector((0.02, sgn * 0.002, -0.04)), a0 + Vector((-0.15, sgn * -0.02, 0.0))], S, n=6, bulge=0.008, back=0.008, out=sgn)
        box('Caliper', F_AXLE + Vector((-0.135, sgn * F_DISC_Y, 0.02)), (0.05, 0.034, 0.075), Me, rot=Matrix.Rotation(0.45, 3, 'Y'), bevel=0.006)
    # the clamps
    for d in (0.0, 0.2):
        box('Clamp', top + axis * d + Vector((0.005, 0, -0.008)), (0.085, 2 * fy + 0.09, 0.032), Me,
            rot=Matrix.Rotation(-math.atan2(axis.x, -axis.z), 3, 'Y'), bevel=0.007)
    tube('Headstock', [top + axis * 0.05, top + axis * 0.24], 0.04, Me, sides=12, segs=3)
    # front fender: a bone arc over the tyre, and a guard hanging each side of it
    fy2 = F_W / 2 + 0.018
    pts = []
    for k in range(9):
        a = math.radians(48 + 88 * k / 8)
        pts.append(F_AXLE + Vector((math.cos(a) * (F_R + 0.022), 0, math.sin(a) * (F_R + 0.022))))
    fk = [dict(c=p, w=fy2 * (0.72 + 0.28 * math.sin(math.pi * i / 8)), ht=0.008, hb=0.008, e=3.5) for i, p in enumerate(pts)]
    loft('Fender', fk, A, 20, 16, side=Vector((0, -1, 0)), cap0='ngon', cap1='ngon', subsurf=0)
    yf = fy2 + 0.008
    both(blade('FenderGuard', trace([(258, 360), (280, 372), (295, 400), (302, 470), (298, 548)], yf),
               trace([(258, 360), (315, 362), (362, 432), (345, 482), (298, 548)], yf), A, n=18, bulge=0.01))
    both(blade('FenderTip', trace([(150, 396), (205, 368), (262, 358)], yf - 0.01),
               trace([(150, 396), (215, 382), (270, 370)], yf - 0.01), A, n=8, bulge=0.008))


def build_bars(M):
    H, Ho, S, Me = M['hull'], M['hose'], M['steel'], M['metal']
    for sgn in (-1, 1):
        bar = [Vector((0.60, 0.0, 0.962)), Vector((0.595, sgn * 0.06, 0.968)), Vector((0.565, sgn * 0.17, 0.985)), Vector((0.49, sgn * 0.30, 0.985)), Vector((0.405, sgn * 0.40, 0.96))]
        tube('Bar', bar, 0.019, Me, sides=10, segs=14)
        # the grip: thick, ribbed, running back and out to the corner of the rider's view
        g0, g1 = Vector((0.405, sgn * 0.40, 0.96)), Vector((0.28, sgn * 0.56, 0.905))
        n = 30
        tube('Grip', [g0, g1], lambda s, n=n: 0.0295 * (1 - 0.07 * abs(math.cos(math.pi * n * s))), Ho, sides=10, segs=n * 2)
        tube('GripCollar', [g0 + (g1 - g0) * -0.08, g0 + (g1 - g0) * 0.05], 0.037, H, sides=10, segs=2)
        tube('BarEnd', [g1, g1 + (g1 - g0).normalized() * 0.022], 0.034, Me, sides=10, segs=2, cap1='point')
        # the switch block: a studded lump with a lit green button on its top, facing the rider
        c = Vector((0.445, sgn * 0.355, 0.982))
        rot = Matrix.Rotation(-sgn * 0.85, 3, 'Z')
        box('Switch', c, (0.09, 0.075, 0.07), H, rot=rot, bevel=0.008)
        box('SwitchCheek', c + rot @ Vector((0, sgn * 0.046, -0.012)), (0.06, 0.03, 0.05), Me, rot=rot, bevel=0.005)
        box('SwitchLid', c + Vector((-0.002, 0, 0.039)), (0.074, 0.06, 0.012), Me, rot=rot, bevel=0.003)
        lit = Vector((-0.006, 0, 0.0465))
        box('SwitchLit', c + rot @ lit, (0.042, 0.034, 0.005), M['led'], rot=rot, bevel=0.0015)
        for ox, oy in ((-0.04, -0.032), (0.04, -0.032), (-0.04, 0.032), (0.04, 0.032)):
            STUDS.add(c + rot @ Vector((ox, oy, 0.037)), Vector((0, 0, 1)), S, r=0.006, h=0.004)
        for ox in (-0.036, -0.012, 0.012, 0.036):
            STUDS.add(c + rot @ Vector((ox, -sgn * 0.038, 0.012)), rot @ Vector((0, -sgn, 0)), S, r=0.0055, h=0.0035)
            STUDS.add(c + rot @ Vector((ox, -sgn * 0.038, -0.016)), rot @ Vector((0, -sgn, 0)), S, r=0.0055, h=0.0035)
        # lever ahead of the grip
        tube('Lever', [Vector((0.47, sgn * 0.39, 0.975)), Vector((0.435, sgn * 0.44, 0.985)), Vector((0.40, sgn * 0.49, 0.965))], 0.0065, Me, sides=6, segs=8)
        # studs along the bar
        for t, (a_, b_) in ((k / 6, (bar[1], bar[3])) for k in range(1, 6)):
            q = a_.lerp(b_, t)
            for ang in (-0.9, 0.9):
                nn = Vector((math.sin(ang) * 0.6, math.sin(ang) * 0.6 * sgn, math.cos(ang))).normalized()
                STUDS.add(q + nn * 0.018, nn, S, r=0.0045, h=0.003)
        # ribbed hoses off the block, arcing into the neck, and the big one along the top of the tank's flank
        hose2('BarHose', [Vector((0.49, sgn * 0.33, 0.98)), Vector((0.55, sgn * 0.29, 0.95)), Vector((0.625, sgn * 0.20, 0.925)), Vector((0.665, sgn * 0.08, 0.90))], 0.024, Ho, sides=8)
        hose2('BarHose', [Vector((0.49, sgn * 0.36, 0.955)), Vector((0.55, sgn * 0.30, 0.90)), Vector((0.60, sgn * 0.20, 0.87)), Vector((0.65, sgn * 0.09, 0.84))], 0.021, Ho, sides=8)
        hose2('TankHose', [Vector((0.635, sgn * 0.05, 0.935)), Vector((0.585, sgn * 0.135, 0.935)), Vector((0.50, sgn * 0.175, 0.925)),
                           Vector((0.38, sgn * 0.178, 0.925)), Vector((0.27, sgn * 0.165, 0.90)), Vector((0.20, sgn * 0.135, 0.868))], 0.0235, Ho, pitch=0.016, sides=8)
        tube('Cable', [Vector((0.50, sgn * 0.33, 0.985)), Vector((0.55, sgn * 0.22, 0.99)), Vector((0.60, sgn * 0.10, 0.95))], 0.0048, Ho, sides=5, segs=10)
    # the reservoir on the kickstand side, as the concept's
    box('Reservoir', (0.525, 0.215, 1.022), (0.05, 0.036, 0.026), Me, bevel=0.005)
    box('ReservoirCap', (0.525, 0.215, 1.037), (0.04, 0.028, 0.006), S, bevel=0.002)
    tube('ReservoirStem', [Vector((0.525, 0.215, 1.01)), Vector((0.53, 0.22, 0.99))], 0.008, Me, sides=6, segs=2)
    # the neck under the dash, a dark cowl over the clamps between the tank and the housing
    neck = [key(0.70, 0.93, 0.03, 0.02, 0.03, e=3), key(0.655, 0.935, 0.125, 0.032, 0.05, e=3), key(0.60, 0.94, 0.125, 0.044, 0.06, e=3), key(0.555, 0.935, 0.075, 0.03, 0.05, e=3), key(0.525, 0.925, 0.02, 0.008, 0.01, e=3)]
    loft('DashNeck', neck, Me, 14, 18, cap0='point', cap1='point', subsurf=0)
    for ox in (-0.09, -0.045, 0.0, 0.045, 0.09):
        STUDS.add((0.583, ox, 0.984 - abs(ox) * 0.2), (0, 0, 1), S, r=0.0055, h=0.004)


def build_dash(M):
    """Bike5Dash: the little wide screen in a boxy dark housing with a sun hood, above the bars, facing the rider's eye.
    UV 0-1: u to the rider's right (-Y), v up."""
    eye = RIDER_CAM
    D = DASH_C
    N = (eye - D)
    N.y = 0
    N.normalize()
    U = Vector((-N.z, 0, N.x)).normalized()
    if U.z < 0:
        U = -U
    Rt = Vector((0, -1, 0))
    width, height, bulge = 0.205, 0.082, 0.008
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
    dash = new_obj('Bike5Dash', verts, faces, M['dash'], uvs=uvs, track=False)
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
    shell = loft('DashHousing', hk, M['hull'], 10, 32, side=-side if U.dot(side.cross(back)) < 0 else side, cap0=None, cap1='ngon', subsurf=0)
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
    for depth, grow in ((0.008, 0.0), (0.02, 0.0), (0.02, 0.026), (0.006, 0.03)):
        rings.append([D + N * depth + Rt * (uu * (1 + grow / (width / 2))) + U * (vv * (1 + grow / (height / 2))) for uu, vv in fr])
    rings_mesh('DashFrame', rings, M['hull'], closed_along=True)
    # sun hood: a plate over the top, reaching toward the rider
    hood = [dict(c=D + U * (height / 2 + 0.02) - N * 0.06, w=width / 2 + 0.026, ht=0.006, hb=0.006, e=6.0),
            dict(c=D + U * (height / 2 + 0.017) + N * 0.045, w=width / 2 + 0.024, ht=0.005, hb=0.005, e=6.0)]
    loft('DashHood', hood, M['hull'], 6, 24, side=Vector((0, 1, 0)) if (Vector((0, 1, 0)).cross(N).dot(U) > 0) else Vector((0, -1, 0)),
         cap0='ngon', cap1='ngon', subsurf=0)
    for sgn in (-1, 1):
        for vv in (-1, 1):
            STUDS.add(D + N * 0.017 + Rt * (sgn * (width / 2 + 0.011)) + U * (vv * (height / 2 + 0.008)), N, M['steel'], r=0.0045)
    for sgn in (-1, 1):
        a = D + Rt * (sgn * (width / 2 + 0.03)) - U * (height / 2 + 0.03)
        b = D + Rt * (sgn * (width / 2 + 0.012)) + U * (height / 2 + 0.03)
        blade('DashCheek', [a + N * 0.02 - Rt * sgn * 0.005, b + N * 0.02], [a + N * 0.0 + Rt * sgn * 0.022, b + N * 0.0 + Rt * sgn * 0.03], M['hull'], n=4, m=2, bulge=0.006, back=0.006, out=-sgn)
    return dash


# ---------------------------------------------------------------- the glass tank mid-frame
# (px, top, bottom, half-width): the concept's outline, front to back
GLASS = [(748, 372, 402, 0.05), (756, 335, 426, 0.11), (770, 310, 446, 0.15), (800, 296, 463, 0.174), (860, 302, 480, 0.18), (920, 320, 492, 0.18),
         (980, 345, 497, 0.172), (1040, 372, 495, 0.15), (1100, 400, 482, 0.118), (1130, 425, 462, 0.07), (1140, 442, 450, 0.02)]


def glass_keys(grow):
    out = []
    for px, top, bot, w in GLASS:
        zt, zb = Z(top), Z(bot)
        out.append(key(X(px), (zt + zb) / 2, max(w + grow, 0.004), max((zt - zb) / 2 + grow, 0.004), max((zt - zb) / 2 + grow, 0.004), e=2.5))
    return out


def build_glass_tank(M):
    G, F, V, Me, Sp = M['glass'], M['fluid'], M['vein'], M['metal'], M['spike']
    glass = glass_keys(0.0)
    loft('TankGlass', glass, G, 32, 28, cap0='point', cap1='point', subsurf=0)
    fluid_keys = glass_keys(-0.009)
    fluid = loft('TankFluid', fluid_keys, F, 24, 24, cap0='point', cap1='point', subsurf=0, track=False)
    # planar UVs for the painted fluid: x along the tank, z up it
    x0, x1, z0, z1 = X(1145), X(745), Z(500), Z(292)
    me = fluid.data
    layer = me.uv_layers[0]
    for p in me.polygons:
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            c, w, ht, hb, e = keyed_at(fluid_keys, min(max(co.x, X(1139)), X(749)))
            # (v by the section's own height: the bright crescent follows the tank's bottom)
            layer.data[li].uv = ((x1 - co.x) / (x1 - x0), min(max((co.z - (c.z - hb)) / max(ht + hb, 0.01), 0.0), 1.0))
    PARTS.append(fluid)
    tree = bvh([fluid])
    rnd = random.Random(23)

    def on_fluid(x, z, sgn, lift=0.0015):
        h = cast(tree, (x, sgn * 0.5, z), (0, -sgn, 0))
        return (h[0] + h[1] * lift) if h else None

    def branch(x, z, ang, life, r, sgn, depth):
        pts = []
        p = on_fluid(x, z, sgn)
        if p is None:
            return
        pts.append(p)
        for _ in range(life):
            ang += rnd.uniform(-0.42, 0.42)
            x += math.cos(ang) * 0.021
            z += math.sin(ang) * 0.021
            p = on_fluid(x, z, sgn)
            if p is None:
                break
            pts.append(p)
            if depth > 0 and rnd.random() < 0.38:
                branch(x, z, ang + rnd.choice((-1, 1)) * rnd.uniform(0.5, 1.1), max(3, life - 3), r * 0.62, sgn, depth - 1)
        if len(pts) >= 2:
            tube('Vein', pts, lambda s, r=r: r * (1 - 0.65 * s) + 0.0006, V, sides=3, cap1='point', segs=max(3, len(pts)))
    for sgn in (-1, 1):
        for px, py, a in ((900, 478, 1.75), (840, 470, 2.1), (965, 490, 1.35), (1040, 482, 1.8), (790, 455, 1.5)):
            branch(X(px), Z(py), a, 11, 0.0036, sgn, 3)
        # tissue: knotted lumps pressed against the glass, up where it's murky
        for k in range(8):
            px, py = rnd.uniform(790, 940), rnd.uniform(322, 400)
            p = on_fluid(X(px), Z(py), sgn, lift=-0.014)
            if p is None:
                continue
            ob = ellipsoid('Tissue', p, (rnd.uniform(0.014, 0.03), 0.017, rnd.uniform(0.012, 0.022)), M['tissue'], rot=(0, rnd.uniform(-0.8, 0.8), 0), segs=10, rings=7)
            for v in ob.data.vertices:
                v.co += v.normal * 0.012 * noise.noise(v.co * 80)
    # ridged dark collars at each end
    for px, g in ((735, 0.012), (743, 0.012), (751, 0.004)):
        c = C(px, 388)
        kk = [dict(c=c + Vector((0.006, 0, 0)), w=0.135 + g, ht=0.085 + g, hb=0.085 + g, e=2.5), dict(c=c - Vector((0.006, 0, 0)), w=0.135 + g, ht=0.085 + g, hb=0.085 + g, e=2.5)]
        loft('TankCollar', kk, M['steel'] if px == 743 else Sp, 3, 24, cap0='ngon', cap1='ngon', subsurf=0)
    for px, g in ((1090, 0.006), (1106, 0.006), (1122, 0.005)):
        c, w, ht, hb, e = keyed_at(glass, X(px))
        kk = [dict(c=c + Vector((0.006, 0, 0)), w=w + g, ht=ht + g, hb=hb + g, e=e), dict(c=c - Vector((0.006, 0, 0)), w=w + g, ht=ht + g, hb=hb + g, e=e)]
        loft('TankCollar', kk, Sp, 3, 24, cap0='ngon', cap1='ngon', subsurf=0)
    lathe_x('TankEnd', [(0.06, -0.03), (0.075, 0.0), (0.05, 0.05), (0.0, 0.06)], Sp, 20, (X(1142), 0, Z(446)), closed_prof=False)


# ---------------------------------------------------------------- the frame: long sweeping blades
def build_frame(M):
    A, Me, Sp = M['armour'], M['metal'], M['spike']
    side = yfn((555, 0.218), (640, 0.228), (720, 0.222), (800, 0.19), (870, 0.07))
    # the shoulder: a bat-wing over the tank's front, a spike at its tail, two horns forward
    top = yfn((585, 0.205), (640, 0.18), (700, 0.152), (760, 0.14), (810, 0.12), (869, 0.07))
    both(blade('Shoulder', trace([(585, 290), (640, 222), (700, 188), (760, 182), (810, 188), (869, 163)], top),
               trace([(612, 380), (640, 322), (690, 284), (750, 258), (810, 236), (869, 163)], side), A, n=30, m=6, bulge=0.016, nicks=7))
    both(blade('HornTop', trace([(555, 320), (585, 298), (620, 276)], side), trace([(555, 320), (600, 345), (632, 330)], side), A, n=10, bulge=0.01))
    both(blade('HornLow', trace([(537, 452), (590, 400), (626, 340)], side), trace([(537, 452), (604, 428), (642, 345)], side), A, n=12, bulge=0.01))
    # the long blade: over the tank and down to the rear axle
    main = yfn((740, 0.212), (900, 0.198), (1100, 0.212), (1300, 0.238), (1450, 0.25), (1592, 0.258))
    both(blade('MainBlade', trace([(735, 238), (800, 226), (850, 234), (900, 264), (950, 294), (1000, 319), (1100, 358), (1200, 408), (1300, 465), (1350, 493), (1450, 524), (1550, 550), (1594, 572)], main),
               trace([(735, 264), (800, 252), (850, 258), (900, 295), (950, 322), (1000, 346), (1100, 383), (1200, 442), (1260, 472), (1310, 505), (1350, 530), (1450, 550), (1550, 570), (1594, 577)], main),
               A, n=70, bulge=0.015, nicks=7))
    # the sweep under the tank's back, roofing the hole over the swingarm
    sweep = yfn((1000, 0.20), (1200, 0.225), (1350, 0.24))
    both(blade('Sweep', trace([(1012, 500), (1100, 472), (1200, 455), (1270, 468), (1352, 528)], sweep),
               trace([(1012, 515), (1100, 492), (1200, 474), (1255, 486), (1352, 528)], sweep), A, n=30, bulge=0.012))
    # the swingarm's lower blade, a spur reaching forward under the hub
    low = yfn((1170, 0.2), (1350, 0.24), (1592, 0.258))
    both(blade('SwingLow', trace([(1172, 632), (1280, 588), (1318, 548), (1352, 528), (1450, 548), (1594, 574)], low),
               trace([(1172, 632), (1250, 612), (1300, 596), (1350, 580), (1450, 560), (1594, 578)], low), A, n=34, bulge=0.014, nicks=6))
    # struts across the tank: the concept's rib, and the arc closing its back
    both(blade('TankRib', trace([(945, 300), (975, 400), (1012, 498)], 0.188), trace([(972, 318), (1002, 400), (1056, 500)], 0.188), A, n=14, bulge=0.012))
    both(blade('TankArc', trace([(1112, 382), (1148, 438), (1128, 482)], 0.17), trace([(1098, 382), (1128, 438), (1100, 482)], 0.17), A, n=12, bulge=0.008))
    # the cradle under the tank, and the spur off its back
    cradle = yfn((760, 0.14), (1000, 0.19))
    both(blade('Cradle', trace([(760, 448), (850, 484), (950, 500), (1012, 506)], cradle), trace([(760, 470), (850, 505), (950, 522), (1012, 512)], cradle), Sp, n=14, bulge=0.012))
    both(blade('CradleSpur', trace([(972, 505), (1030, 500), (1072, 488)], 0.2), trace([(972, 505), (1025, 532), (1068, 570)], 0.2), A, n=10, bulge=0.012))
    # the belly: a long blade low down, the dark pan under it with its lit slashes
    belly = yfn((655, 0.11), (760, 0.165), (950, 0.17), (1020, 0.15))
    both(blade('Belly', trace([(655, 702), (690, 622), (722, 580), (762, 546), (800, 538), (850, 552), (900, 564), (960, 570), (1040, 568)], belly),
               trace([(655, 702), (700, 655), (760, 620), (850, 592), (950, 580), (1040, 568)], belly), A, n=30, bulge=0.014, nicks=6))
    both(blade('BellyPan', trace([(655, 702), (760, 625), (850, 596), (960, 582)], lambda p: belly(p) - 0.006),
               trace([(655, 702), (760, 700), (850, 690), (960, 640)], lambda p: belly(p) - 0.03), Me, n=14, bulge=0.012))
    for px, py in ((700, 684), (738, 674), (778, 664), (815, 654)):
        yy = belly(px) + 0.003
        both(blade('Vent', [C(px + 11, py - 22, yy), C(px - 12, py + 18, yy)], [C(px + 28, py - 20, yy), C(px + 5, py + 20, yy)], M['led'], n=2, m=2, bulge=0.003, back=0.001))
    # the chin spear: bone rims, a dark grille between them, under the front of the frame
    spear = yfn((500, 0.012), (560, 0.085), (610, 0.125))
    both(blade('SpearFront', trace([(500, 716), (522, 680), (540, 620), (552, 565)], spear), trace([(500, 716), (533, 680), (552, 625), (566, 570)], spear), A, n=12, bulge=0.008))
    both(blade('SpearBack', trace([(500, 716), (548, 700), (585, 660), (602, 612)], spear), trace([(500, 716), (558, 708), (598, 668), (616, 615)], spear), A, n=12, bulge=0.008))
    both(blade('SpearPan', trace([(510, 700), (535, 640), (556, 585)], lambda p: spear(p) - 0.004), trace([(530, 700), (575, 660), (597, 615)], lambda p: spear(p) - 0.004), Me, n=8, bulge=0.004))
    # the radiator: a dark slab behind the forks, its fins
    rc = C(525, 492)
    box('Radiator', rc, (0.05, 0.25, 0.22), Me, rot=Matrix.Rotation(0.25, 3, 'Y'), bevel=0.004)
    for k in range(14):
        z = -0.1 + 0.2 * k / 13
        q = Matrix.Rotation(0.25, 3, 'Y')
        box('Fin', rc + q @ Vector((0.028, 0, z)), (0.006, 0.24, 0.005), M['disc'], rot=q)


def build_engine(M):
    Me, Sp, Ho, S, T = M['metal'], M['spike'], M['hose'], M['steel'], M['tube']
    core = [key(0.50, 0.40, 0.04, 0.08, 0.08, e=3), key(0.42, 0.40, 0.115, 0.26, 0.22, e=3.5), key(0.20, 0.34, 0.13, 0.19, 0.20, e=3.5),
            key(-0.10, 0.36, 0.12, 0.16, 0.21, e=3.5), key(-0.28, 0.40, 0.09, 0.12, 0.16, e=3), key(-0.36, 0.42, 0.03, 0.04, 0.04, e=3)]
    loft('Engine', core, Me, 20, 22, cap0='point', cap1='point', subsurf=0)
    # the neck between the fork and the tank: dark mass with a ribbed collar ahead of the glass
    neck = [key(0.56, 0.80, 0.04, 0.06, 0.08, e=3), key(0.47, 0.72, 0.13, 0.11, 0.14, e=3), key(0.36, 0.64, 0.15, 0.10, 0.16, e=3), key(0.27, 0.60, 0.13, 0.09, 0.14, e=3)]
    loft('Neck', neck, Me, 12, 18, cap0='point', cap1='ngon', subsurf=0)
    for i in range(6):
        x = 0.31 + 0.038 * i
        c = Vector((x, 0, 0.56 + 0.012 * i))
        lathe_x('EngineRib', [(0.10, -0.01), (0.148 - 0.004 * i, -0.008), (0.152 - 0.004 * i, 0.0), (0.148 - 0.004 * i, 0.008), (0.10, 0.01)], Sp, 24, c, closed_prof=False)
    # crank covers low down and the swingarm's hub: a dark dome each side, a broken green ring in it
    for sgn in (-1, 1):
        prof = [(0.0, 0.0), (0.1, 0.0), (0.104, 0.012), (0.095, 0.026), (0.06, 0.036), (0.0, 0.038)]
        if sgn < 0:
            prof = [(r, -y) for r, y in prof]
        ob = lathe_y('Crankcase', prof, Sp, 28, (0.12, sgn * 0.11, 0.25))
        if sgn < 0:
            ob.data.flip_normals()
        for k in range(8):
            a = TAU * k / 8
            STUDS.add(Vector((0.12 + 0.085 * math.cos(a), sgn * 0.135, 0.25 + 0.085 * math.sin(a))), Vector((0, sgn, 0)), S, r=0.006)
    hub = C(1150, 555)
    for sgn in (-1, 1):
        y0 = sgn * 0.215
        prof = [(0.0, y0 - sgn * 0.05), (0.085, y0 - sgn * 0.05), (0.09, y0 - sgn * 0.01), (0.085, y0 + sgn * 0.006), (0.066, y0 + sgn * 0.016), (0.058, y0 + sgn * 0.012),
                (0.036, y0 + sgn * 0.012), (0.03, y0 + sgn * 0.022), (0.0, y0 + sgn * 0.024)]
        ob = lathe_y('Hub', prof, Sp, 36, hub)
        if sgn < 0:
            ob.data.flip_normals()
        for k in range(4):
            a0 = math.radians(14) + TAU * k / 4
            for piece in ob_arc_piece(hub, y0 + sgn * 0.0135, 0.043, 0.052, a0, a0 + math.radians(70), T):
                pass
        for k in range(10):
            a = TAU * k / 10
            STUDS.add(hub + Vector((0.077 * math.cos(a), y0 + sgn * 0.012, 0.077 * math.sin(a))), Vector((0.5 * math.cos(a), sgn, 0.5 * math.sin(a))), Sp, r=0.0045, h=0.003)
    # chain from the hub's sprocket back to the rear wheel's
    cy = R_SPROCKET_Y + 0.003
    fs = Vector((hub.x, cy, hub.z))
    rs = R_AXLE + Vector((0, cy, 0))
    d = (rs - fs).normalized()
    nrm = Vector((-d.z, 0, d.x))
    for side, r0, r1 in ((1, 0.055, 0.163), (-1, 0.055, 0.163)):
        tube('Chain', [fs + nrm * side * r0, rs + nrm * side * r1], 0.0065, Sp, sides=4, segs=6, squash=0.6)
    # a finned block down low, between the hoses
    for k in range(14):
        x = X(830) - k * 0.019
        box('EngineFin', (x, 0.0, Z(625)), (0.008, 0.27, 0.1 + 0.02 * math.sin(k * 0.5)), Sp)
    # ribbed black hoses, sweeping under the tank, either side
    for sgn in (-1, 1):
        y1, y2 = sgn * 0.17, sgn * 0.14
        hose2('Hose', [C(600, 642, sgn * 0.09), C(590, 560, sgn * 0.13), C(615, 490, y1), C(660, 455, y1), C(720, 445, y1), C(800, 462, y1), C(900, 490, y1), C(1000, 516, y1)], 0.023, Ho, sides=8, ribs=False)
        hose2('Hose', [C(650, 628, sgn * 0.10), C(640, 552, y2), C(670, 496, y2 * 1.1), C(730, 480, y1 * 0.95), C(820, 498, y1), C(920, 524, y1), C(1040, 545, y1 * 0.9)], 0.019, Ho, sides=8, ribs=False)
        hose2('Hose', [C(700, 590, y2), C(780, 548, y2), C(880, 538, y1), C(980, 558, y1), C(1060, 590, y2)], 0.017, Ho, sides=8, ribs=False)
        hose2('Hose', [C(880, 610, y2), C(960, 626, y1), C(1060, 628, y1), C(1120, 608, y1 * 1.1), C(1150, 596, y1 * 1.1)], 0.018, Ho, sides=8, ribs=False)
        hose2('Hose', [C(860, 640, y2), C(960, 656, y2), C(1060, 650, y1), C(1140, 630, y1), C(1190, 590, y1)], 0.016, Ho, sides=8, ribs=False)
        tube('Cable', [C(1040, 530, y1), C(1120, 530, y1), C(1200, 505, sgn * 0.19), C(1260, 500, sgn * 0.2)], 0.006, Ho, sides=5, segs=10)
        # vertical hoses up the neck, behind the shoulder
        hose2('Hose', [C(690, 460, sgn * 0.14), C(668, 420, sgn * 0.17), C(690, 350, sgn * 0.175), C(735, 305, sgn * 0.14)], 0.016, Ho, sides=8, ribs=False)


def ob_arc_piece(hub, y, r0, r1, a0, a1, mat, segs=8):
    """A lit arc in the hub's face, about Y through `hub`, at y."""
    rings = []
    for i in range(segs + 1):
        a = a0 + (a1 - a0) * i / segs
        c, s = math.cos(a), math.sin(a)
        rings.append([hub + Vector((r * c, y, r * s)) for r in (r0, r1)])
    return [rings_mesh('HubRing', rings, mat, closed_ring=False)]


def build_spine(M):
    """The back: a glowing core down from the tank to the seat, dark tilted vertebrae over it, the green showing in
    the slits between them, a curved spike on each."""
    T, Sp, Me = M['tube'], M['spike'], M['metal']
    a, b = C(872, 238), C(1098, 316)
    axis = (b - a).normalized()
    # the core
    keys = [dict(c=a, w=0.058, ht=0.056, hb=0.056, e=2.4), dict(c=a.lerp(b, 0.5), w=0.058, ht=0.054, hb=0.054, e=2.4), dict(c=b, w=0.05, ht=0.048, hb=0.048, e=2.4)]
    loft('SpineCore', keys, Me, 12, 16, cap0='ngon', cap1='ngon', subsurf=0)
    # the bed it lies on, filling across to the blades
    bed = [key(0.22, 0.76, 0.17, 0.02, 0.03, e=3.5), key(0.05, 0.745, 0.185, 0.02, 0.03, e=3.5), key(-0.10, 0.68, 0.19, 0.02, 0.03, e=3.5), key(-0.24, 0.625, 0.17, 0.02, 0.03, e=3.5)]
    loft('SpineBed', bed, Me, 10, 16, cap0='ngon', cap1='ngon', subsurf=0)
    d = Vector((-0.81, 0, 0.58)).normalized()
    # the vertebrae: the gaps between them fall on the concept's slits
    for px in (848, 925, 990, 1048, 1092):
        t = (px - 872) / (1098 - 872)
        c = a.lerp(b, t)
        r = 0.074 - 0.008 * max(t, 0)
        hw = 0.021
        kk = [dict(c=c - d * hw, w=r, ht=r, hb=r, e=2.4), dict(c=c + d * hw, w=r * 1.04, ht=r * 1.04, hb=r * 1.04, e=2.4)]
        loft('Vertebra', kk, Sp, 3, 16, cap0='ngon', cap1='ngon', subsurf=0)
    # the lit slits, in the gaps: thin glowing hoops, slanted as the concept's, wrapping over the top
    for px in (887, 958, 1019, 1070):
        t = (px - 872) / (1098 - 872)
        c = a.lerp(b, t)
        r = 0.0645 - 0.006 * t
        kk = [dict(c=c - d * 0.0055, w=r, ht=r, hb=r, e=2.4), dict(c=c + d * 0.0055, w=r, ht=r, hb=r, e=2.4)]
        loft('SpineSlit', kk, T, 2, 18, cap0=None, cap1=None, subsurf=0)
    spikes = [((905, 235), (915, 205), (922, 188), (937, 175)), ((968, 250), (977, 222), (984, 206), (998, 196)), ((1030, 270), (1038, 240), (1043, 228), (1052, 226)), ((1075, 292), (1082, 272), (1085, 260), (1092, 252))]
    for sp in spikes:
        for y in (0.0, 0.06, -0.06):
            pts = trace(sp, y)
            if y:
                pts = [p.lerp(pts[0], 0.22) for p in pts]
            tube('Spike', pts, lambda s, k=(0.034 if not y else 0.02): k * (1 - s) ** 0.8 + 0.0008, Sp, sides=6, segs=9, cap1='point', squash=0.55)
    # the ribs: a tall dark plate each side under each spike, shingled, a long lit slit down its face
    ribs = (((843, 203), (907, 270), (897, 197), (957, 283), (875, 212), (913, 251)),
            ((923, 213), (987, 290), (967, 210), (1020, 297), (947, 224), (983, 270)),
            ((987, 240), (1037, 317), (1020, 237), (1067, 323), (1010, 248), (1041, 295)),
            ((1037, 267), (1073, 330), (1063, 260), (1107, 343), (1063, 279), (1087, 315)))
    for a0, a1, b0, b1, s0, s1 in ribs:
        y0, y1 = 0.052, 0.088
        both(blade('Rib', [C(*a0, y0), C(*a1, y1)], [C(*b0, y0), C(*b1, y1)], Sp, n=5, bulge=0.012, back=0.006))
        w = 8
        yk = lambda t: y0 + (y1 - y0) * t + 0.0135
        both(blade('RibSlit', [C(s0[0], s0[1], yk(0.1)), C(s1[0], s1[1], yk(0.85))], [C(s0[0] + w, s0[1] - 2, yk(0.1)), C(s1[0] + w, s1[1] - 2, yk(0.85))], T, n=4, bulge=0.002, back=0.001))


def build_rear(M):
    A, Me, Sp, Ho, Se = M['armour'], M['metal'], M['spike'], M['hose'], M['seat']
    # the seat: long, a dip, rising to the pillion's hump
    top = [(1072, 276), (1100, 272), (1150, 293), (1200, 302), (1250, 297), (1300, 278), (1340, 238), (1380, 205), (1440, 190), (1500, 172)]
    bot = [(1072, 350), (1100, 358), (1150, 352), (1200, 342), (1250, 334), (1300, 325), (1340, 300), (1380, 268), (1440, 232), (1500, 195)]
    wid = [0.06, 0.125, 0.155, 0.165, 0.16, 0.145, 0.125, 0.11, 0.095, 0.03]
    keys = []
    for (px, t), (_, b), w in zip(top, bot, wid):
        zt, zb = Z(t), Z(b)
        keys.append(key(X(px), (zt + zb) / 2, w, (zt - zb) / 2, (zt - zb) / 2, e=3.0))
    seat = loft('Seat', keys, Se, 44, 22, cap0='point', cap1='point', subsurf=0)
    for v in seat.data.vertices:
        v.co += v.normal * 0.008 * noise.noise(Vector((v.co.x * 24, v.co.y * 30, v.co.z * 24)))
    # seams across the seat
    for px, py in ((1140, 289), (1230, 298), (1320, 258), (1400, 197)):
        i = 0.11 if px > 1300 else 0.145
        tube('SeatSeam', [C(px + 8, py + 34, -i), C(px, py + 1, 0.0), C(px + 8, py + 34, i)], 0.0035, Ho, sides=4, segs=14)
    # under the seat: the dark subframe, the struts, a thin lit line, and the fins over the tyre
    sub = 0.115
    both(blade('SubFrame', trace([(1100, 362), (1200, 345), (1300, 328), (1362, 305)], sub), trace([(1150, 398), (1250, 402), (1305, 382), (1366, 310)], sub), Sp, n=14, bulge=0.012))
    both(tube('TailStrut', [C(1200, 432, 0.16), C(1290, 372, 0.15), C(1370, 318, 0.11)], 0.015, Me, sides=8, segs=8))
    both(tube('TailStrutLit', [C(1215, 432, 0.18), C(1300, 372, 0.165), C(1345, 335, 0.13)], 0.004, M['tube'], sides=4, segs=8))
    hug = 0.205
    both(blade('HuggerFin', trace([(1298, 440), (1360, 398), (1410, 368), (1442, 352)], hug), trace([(1298, 452), (1362, 442), (1420, 396), (1442, 352)], hug), Sp, n=14, bulge=0.012))
    both(blade('HuggerFin2', trace([(1260, 455), (1310, 430), (1362, 405), (1392, 392)], hug - 0.01), trace([(1270, 480), (1330, 455), (1375, 420), (1392, 392)], hug - 0.01), Sp, n=10, bulge=0.01))
    # the shock, from the swingarm up under the seat
    for sgn in (-1, 1):
        s0, s1 = C(1270, 540, sgn * 0.21), C(1215, 360, sgn * 0.09)
        tube('Shock', [s0, s1], 0.016, M['steel'], sides=8, segs=3)
        pts = [s0.lerp(s1, 0.12 + 0.62 * i / 40) + Vector((0.026 * math.cos(i * 0.9), 0.026 * math.sin(i * 0.9), 0)) for i in range(41)]
        tube('Spring', pts, 0.005, Me, sides=4, segs=48)
    # the tail: a wide, flat, long blade, thin from the side and wide from behind; the bone strake up to it
    tw = yfn((1480, 0.16), (1560, 0.17), (1640, 0.13), (1680, 0.07), (1707, 0.012))
    cowl = []
    for px in (1470, 1500, 1540, 1590, 1640, 1680, 1707):
        ztop = Z({1470: 178, 1500: 168, 1540: 162, 1590: 163, 1640: 168, 1680: 174, 1707: 180}[px])
        zbot = Z({1470: 215, 1500: 200, 1540: 190, 1590: 180, 1640: 176, 1680: 178, 1707: 181}[px])
        cowl.append(dict(c=Vector((TX(px), 0, (ztop + zbot) / 2)), w=tw(px), ht=(ztop - zbot) / 2, hb=(ztop - zbot) / 2, e=3.2))
    loft('TailCowl', cowl, A, 26, 22, cap0='ngon', cap1='point', subsurf=0)
    for px in (1500, 1540, 1580, 1620):
        stud2(C(px, {1500: 168, 1540: 162, 1580: 163, 1620: 166}[px] - 1, tw(px) * 0.78, TX), (0, 0.3, 1), M['spike'], r=0.0055, h=0.0035)
    # the strake: a sliver up from under the seat, sweeping into the cowl's flank, an opening behind it
    st = yfn((1370, 0.10), (1460, 0.135), (1530, 0.16))
    both(blade('TailStrake', trace([(1370, 312), (1440, 276), (1465, 240), (1490, 205), (1530, 176)], st, TX), trace([(1370, 316), (1450, 294), (1482, 262), (1510, 226), (1545, 190)], st, TX), A, n=22, bulge=0.012))
    both(blade('TailRoot', trace([(1440, 200), (1470, 178), (1510, 168)], 0.125, TX), trace([(1450, 262), (1482, 230), (1530, 188)], 0.15, TX), A, n=10, bulge=0.01))
    # under the cowl: a dark housing and the red light across it, along the flanks and round behind
    body = []
    for px, zt, zb, w in ((1490, 200, 262, 0.14), (1540, 190, 238, 0.145), (1600, 182, 218, 0.13), (1650, 180, 202, 0.095), (1672, 182, 194, 0.04)):
        ztop, zbot = Z(zt), Z(zb)
        body.append(dict(c=Vector((TX(px), 0, (ztop + zbot) / 2)), w=w, ht=(ztop - zbot) / 2, hb=(ztop - zbot) / 2, e=3.0))
    loft('TailBody', body, Sp, 14, 16, cap0='ngon', cap1='ngon', subsurf=0)
    light = [C(1525, 228, 0.142, TX), C(1590, 212, 0.138, TX), C(1630, 200, 0.118, TX), C(1656, 194, 0.07, TX), C(1668, 192, 0.0, TX)]
    tube('TailLight', light + [Vector((p.x, -p.y, p.z)) for p in reversed(light[:-1])], 0.0088, M['tail'], sides=6, segs=52, squash=0.7)
    # kickstand on +Y: a segmented steel leg, a flat foot
    foot_y = 0.46
    foot_z = (0.012 + math.sin(LEAN) * foot_y) / math.cos(LEAN)
    k0 = C(975, 592, 0.20)
    f0 = Vector((X(900), foot_y, foot_z + 0.012))
    tube('StandKnuckle', [k0 + Vector((0, -0.04, 0)), k0 + Vector((0, 0.03, 0))], 0.03, M['steel'], sides=10, segs=2)
    tube('Stand', [k0, k0.lerp(f0, 0.5), f0], (0.02, 0.012), M['steel'], sides=8, segs=6)
    for t in (0.3, 0.46, 0.62, 0.78):
        p, q = k0.lerp(f0, t - 0.012), k0.lerp(f0, t + 0.012)
        tube('StandCollar', [p, q], 0.0215 - 0.008 * t, Me, sides=8, segs=1)
    box('StandFoot', (X(900), foot_y, foot_z), (0.085, 0.05, 0.012), M['steel'], bevel=0.003)


# ---------------------------------------------------------------- the throttle button
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
    btn = rings_mesh('Bike5Button', rings, M['button'], track=False)
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
    gme = bpy.data.meshes.new('Bike5ButtonGlyph')
    bm.to_mesh(gme)
    bm.free()
    for v in gme.vertices:
        x, y, tz = v.co.x, v.co.y, v.co.z
        p, n = base(x, y)
        v.co = p + n * (FACE_H + 0.0015 + tz)
    gme.materials.append(M['glyph'])
    gme.shade_flat()
    glyph = bpy.data.objects.new('Bike5ButtonGlyph', gme)
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


# ---------------------------------------------------------------- ambient occlusion + grime into vertex colours
NO_GRIME = {'Bike5Glass', 'Bike5Smoke', 'Bike5Fluid', 'Bike5Tube', 'Bike5Led', 'Bike5Tail', 'Bike5Vein', 'Bike5Tissue'}


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
        nv = len(me.vertices)
        acc = [0.0] * nv
        cnt = [0] * nv
        clean = [False] * nv
        for li, lp in enumerate(me.loops):
            m = mats[pmat[loop_poly[li]]]
            vi = lp.vertex_index
            if m in NO_GRIME:
                clean[vi] = True
            acc[vi] += (0.3 + 0.7 * cols[li * 4]) if ok else 1.0
            cnt[vi] += 1
        me.color_attributes.remove(attr)
        pt = me.color_attributes.new('Col', 'BYTE_COLOR', 'POINT')
        val = [acc[i] / max(cnt[i], 1) for i in range(nv)]
        # relax the bake's noise over the mesh's edges
        nbr = [[] for _ in range(nv)]
        for e in me.edges:
            a_, b_ = e.vertices
            nbr[a_].append(b_)
            nbr[b_].append(a_)
        for _ in range(4):
            val = [0.5 * val[i] + 0.5 * (sum(val[j] for j in nbr[i]) / len(nbr[i])) if nbr[i] else val[i] for i in range(nv)]
        # grime: oily brown in the creases and in blotches across the open steel; the blades' rims nicked dark
        wa = me.attributes.get('Wear')
        wear = [0.0] * nv
        if wa is not None and len(wa.data) == nv:
            wa.data.foreach_get('value', wear)
        flat = []
        for i, v_ in enumerate(val):
            if clean[i]:
                flat += [1.0, 1.0, 1.0, 1.0]
                continue
            co = me.vertices[i].co
            g = min(1.0, max(0.0, noise.noise(co * 3.5) * 1.5 + (1.0 - v_) * 1.1 - 0.12))
            g = round(g * 3) / 3  # coarse steps compress far better and read the same
            q = round(v_ * 14) / 14
            if wear[i] > 0.5:
                q *= 0.52 if noise.noise(co * 16.0) > -0.2 else 0.85
            flat += [q * (1 - 0.26 * g), q * (1 - 0.36 * g), q * (1 - 0.5 * g), 1.0]
        pt.data.foreach_set('color', flat)
        me.color_attributes.active_color = pt
        me.attributes.active_color = pt
        me.update()
        print('VCOL', ob.name, 'baked' if ok else 'grime only')


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
    scene.view_settings.view_transform = 'Khronos PBR Neutral'
    scene.view_settings.look = 'None'
    # the glows as the site lights them (components/three/bike.tsx BIKE_GLOWS)
    for name, k in (('Bike5Led', 7.0), ('Bike5Tube', 1.3), ('Bike5Vein', 2.2)):
        bpy.data.materials[name].node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = k
    # a dark studio with a little green coming up off the floor, for the concept's look
    world = bpy.data.worlds.new('CoreWorld')
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
    cr.elements[0].position, cr.elements[0].color = 0.0, (0.008, 0.01, 0.008, 1)
    cr.elements[1].position, cr.elements[1].color = 1.0, (0.02, 0.021, 0.02, 1)
    e = cr.elements.new(0.5)
    e.color = (0.012, 0.014, 0.012, 1)
    e = cr.elements.new(0.58)
    e.color = (0.016, 0.018, 0.016, 1)
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.0
    world.light_settings.distance = 0.12
    col = bpy.data.collections.new('Render')
    scene.collection.children.link(col)
    # big soft panels: overhead, and either side, picking out the long blades
    for loc, size, colr, s in (((0, 0.5, 4.0), (6, 3), (1.0, 0.98, 0.92), 3.2), ((0.6, 5.0, 1.8), (7, 2.0), (1.0, 0.98, 0.94), 2.6),
                               ((0.6, -5.0, 1.8), (7, 2.0), (1.0, 0.98, 0.94), 2.6), ((4.5, 0.0, 1.8), (3, 2), (0.9, 1.0, 0.85), 1.5),
                               ((-4.5, 0.0, 1.8), (3, 2), (0.9, 1.0, 0.85), 1.5), ((0.0, 4.5, 0.45), (8, 1.2), (0.95, 1.0, 0.92), 3.0), ((0.0, -4.5, 0.45), (8, 1.2), (0.95, 1.0, 0.92), 3.0)):
        me = bpy.data.meshes.new('Panel')
        me.from_pydata([(-size[0] / 2, -size[1] / 2, 0), (size[0] / 2, -size[1] / 2, 0), (size[0] / 2, size[1] / 2, 0), (-size[0] / 2, size[1] / 2, 0)], [], [(0, 1, 2, 3)])
        p = bpy.data.objects.new('Panel', me)
        p.location = loc
        p.rotation_euler = (Vector(loc) - Vector((0, 0, 0.6))).to_track_quat('Z', 'Y').to_euler()
        p.visible_camera = False
        pm = bpy.data.materials.new('PanelLight')
        pm.use_nodes = True
        pb = pm.node_tree.nodes['Principled BSDF']
        pb.inputs['Base Color'].default_value = (0, 0, 0, 1)
        pb.inputs['Emission Color'].default_value = (*colr, 1)
        pb.inputs['Emission Strength'].default_value = s
        me.materials.append(pm)
        col.objects.link(p)
    # the wet deck, a white line up its middle for the rider's view
    me = bpy.data.meshes.new('Ground')
    s = 60
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new('Ground', me)
    col.objects.link(g)
    gm = bpy.data.materials.new('WetDeck')
    gm.use_nodes = True
    b = gm.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.008, 0.009, 0.008, 1)
    b.inputs['Roughness'].default_value = 0.55
    b.inputs['Specular IOR Level'].default_value = 0.15
    me.materials.append(gm)
    lm = bpy.data.materials.new('RoadLine')
    lm.use_nodes = True
    lm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.7, 0.7, 0.65, 1)
    for k in range(10):
        x = 2.2 + k * 5.0
        me = bpy.data.meshes.new('Line')
        me.from_pydata([(x, -0.07, 0.003), (x + 2.2, -0.07, 0.003), (x + 2.2, 0.07, 0.003), (x, 0.07, 0.003)], [], [(0, 1, 2, 3)])
        me.materials.append(lm)
        col.objects.link(bpy.data.objects.new('Line', me))
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
    if '--nobake' in ARGS:
        return
    for m in bpy.data.materials:
        if not m.name.startswith('Bike5') or m.name in NO_GRIME:
            continue
        if m.name in ('Bike5Dash', 'Bike5Button', 'Bike5ButtonGlyph'):
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
    look = RIDER_CAM + Vector((math.cos(RIDER_PITCH), 0, -math.sin(RIDER_PITCH))) * 10
    # (The site's fov is vertical; a 36 mm sensor's width takes the horizontal, at 16:9.)
    rider_lens = 18 / (math.tan(RIDER_FOV / 2) * 1672 / 941)
    cams = {
        # from +Y, as the concept (front to the left); art/align-bike5/compare.py warps it onto the concept
        'concept': (add_camera(col, 'ConceptCam5', (0, 8, 0.62), rot=(math.pi / 2, 0, math.pi), ortho=2.9), (1920, 1080), False),
        # the site's rider camera, upright (it rides upright)
        'rider': (add_camera(col, 'RiderCam5', RIDER_CAM, look, lens=rider_lens), (1672, 941), True),
        'riderdash': (add_camera(col, 'RiderDashCam5', RIDER_CAM, (0.5, 0.0, 0.93), lens=30), (1672, 941), True),
        'side': (add_camera(col, 'CamSide5', (0, -8, 0.62), rot=(math.pi / 2, 0, 0), ortho=2.9), (1920, 1080), False),
        'hero': (add_camera(col, 'CamHero5', (2.5, 3.4, 0.8), (0.0, 0, 0.58), lens=32), (1920, 1080), False),
        # low behind, from the kickstand's side, as the plaza concept
        'plaza': (add_camera(col, 'CamPlaza5', (-2.6, 1.15, 0.42), (0.1, 0.05, 0.62), lens=30), (1672, 941), False),
        'rear': (add_camera(col, 'CamRear5', (-3.0, -2.6, 1.1), (0.0, 0.0, 0.55), lens=32), (1920, 1080), False),
        'top': (add_camera(col, 'CamTop5', (0, 0, 8), rot=(0, 0, 0), ortho=2.9), (1920, 1080), False),
    }
    suffix = f'-{TAG}' if TAG else ''
    for k, (cam, res, upright) in cams.items():
        if VIEWS and k not in VIEWS:
            continue
        body.rotation_euler = (0, 0, 0) if upright else (-LEAN, 0, 0)
        bpy.context.view_layer.update()
        scene.camera = cam
        scene.render.resolution_x, scene.render.resolution_y = res
        scene.render.filepath = os.path.join(RENDER_DIR, f'bike5-{k}{suffix}.png')
        bpy.ops.render.render(write_still=True)
        print('rendered', scene.render.filepath)
    body.rotation_euler = (-LEAN, 0, 0)


# ---------------------------------------------------------------- main
POD = dict(x=(0.26, 0.48), y=(-0.28, -0.10), z=0.955)  # (the boost pod's space, ButtonCentre + (-0.015, -0.19, 0.03), its slide included)


def check_pod(parts):
    """Nothing may stand in the boost pod's space, or stick up through it."""
    bad = {}
    for o in parts:
        for v in o.data.vertices:
            c = v.co
            if POD['x'][0] < c.x < POD['x'][1] and POD['y'][0] < c.y < POD['y'][1] and c.z > POD['z']:
                n = o.name.split('.')[0]
                bad[n] = bad.get(n, 0) + 1
    print('POD space clear' if not bad else f'POD space HIT {bad}')


def main():
    scene = reset()
    M = make_materials()
    M_NICK[0] = M['spike']
    tank = build_tank(M)
    PARTS.append(tank)
    build_tank_dressing(M, tank)
    build_screen(M)
    build_fairing(M)
    build_forks(M)
    build_bars(M)
    dash = build_dash(M)
    build_glass_tank(M)
    build_frame(M)
    build_engine(M)
    build_spine(M)
    build_rear(M)
    STUDS.objects('Rivets')

    extras = build_button(M, tank)
    check_pod(PARTS)
    per = {}
    for o in PARTS:
        per[o.name.split('.')[0]] = per.get(o.name.split('.')[0], 0) + tri_count(o)
    print('PARTS', sorted(per.items(), key=lambda kv: -kv[1]))
    body = join('Bike5', PARTS)
    PARTS.clear()

    wf = build_wheel('Wheel5Front', F_R, F_W, M, front=True)
    wr = build_wheel('Wheel5Rear', R_R, R_W, M, front=False)
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
    xs = [(body.matrix_world @ v.co).x for v in body.data.vertices]
    print('EXTENT x', round(min(xs), 3), round(max(xs), 3))

    # (Only the textured materials need UVs: the rest compress to nothing, and stop splitting vertices at their seams.)
    for ob in (body, wf, wr):
        me = ob.data
        textured = [bool(m) and m.name in ('Bike5Armour', 'Bike5Hull', 'Bike5Hose', 'Bike5Fluid') for m in me.materials]
        layer = me.uv_layers[0]
        for pl in me.polygons:
            if not textured[pl.material_index]:
                for li in pl.loop_indices:
                    layer.data[li].uv = (0.0, 0.0)

    scene.camera = None
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)

    bpy.ops.object.select_all(action='DESELECT')
    for o in (body, wf, wr, dash, *extras):
        o.select_set(True)
    os.makedirs(os.path.dirname(GLB_OUT), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=GLB_OUT, export_format='GLB', use_selection=True, export_apply=True, export_yup=True,
                              export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
                              export_draco_position_quantization=13, export_draco_normal_quantization=9,
                              export_draco_texcoord_quantization=10, export_draco_color_quantization=6,
                              export_vertex_color='ACTIVE', export_image_format='JPEG', export_jpeg_quality=80,
                              export_cameras=False, export_lights=False, export_extras=True)
    print('GLB', GLB_OUT, os.path.getsize(GLB_OUT))
    if DO_RENDER:
        col = setup_render(scene)
        show_vertex_colours()
        render_views(scene, col, body)


main()
