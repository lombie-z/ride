"""The core's chamber (kit.SECTIONS['core'], concept-core-plaza): the zone's arrival. A cylinder 130 m in radius and 180 m
tall, reached from the servers' end by a flaring throat; a wide wet bridge over a misty pit; a broad stair up to a
plinth; and, hanging over it all, the sphere: 42 m in radius, panelled and riveted, its eye turned down at the bridge head.

Everything's laid out in a frame at the road's end: u on along the road, v to its left, z up (`_w` turns it into the city's).
The sphere's own frame: A the way the eye looks, L to the left, T up across its face. Its panels, bands and girdle run like
lines of longitude between poles at the left and right clamps: `_sph(phi, lam)`, phi up from the eye, lam from the left pole.

All the light's painted in: Heart (bands, eye), Led, Red, Panel and the racks' Screen are emissive, and kit.bake_light
paints what they'd throw on the sphere, walls and wet floor into vertex colours.
"""
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit as _kit  # noqa: E402

_END = _kit.along(_kit.ROAD_LEN)


def _w(u, v=0.0, z=0.0):
    """The road's-end frame (u along the road, v to its left) to the city's."""
    return (_END.x + u, _END.y + v, z)


# The bike's parking, for art/build-city5.py: at s = kit.ROAD_LEN, d metres left of the centreline, turned yaw_deg left.
BIKE = {'d': -3.0, 'yaw_deg': -8.0}
# The arrival shot, fitted to concept-core-plaza: low behind the bike, pitched up at the sphere (the city's frame).
_PITCH = 22.0
_EYE = (-3.4, -0.4, 0.6)
ARRIVAL = {
    'eye': _w(*_EYE),
    'look': _w(_EYE[0] + 100 * math.cos(math.radians(_PITCH)), _EYE[1], _EYE[2] + 100 * math.sin(math.radians(_PITCH))),
    'fov': 76.0,
}
SHOTS = {
    'arrival': (ARRIVAL['eye'], ARRIVAL['look'], ARRIVAL['fov']),
    'approach': (tuple(_kit.along(_kit.MOUTH - 16.0, 0.0, 1.5)), tuple(_kit.along(_kit.MOUTH + 84.0, 0.0, 6.0)), 70.0),
    'midway': (_w(-40.0, 0.0, 1.5), _w(60.0, 0.0, 30.0), 70.0),
    'wall': (_w(30.0, 0.0, 3.0), _w(92.0, 95.0, 60.0), 50.0),
    'sphere': (_w(10.0, 0.0, 3.0), _w(92.0, 0.0, 62.0), 52.0),
}

# The plan.
U = 92.0             # the chamber's axis and the sphere's centre, this far beyond the road's end
R_CH = 130.0         # the chamber's radius
S_R = 42.0           # the sphere's
S_Z = 66.6           # the height of its centre
TILT = 37.0          # how far down its eye looks
ROOF_Z = 180.0
PIT_Z = -32.0
WALL_U = U - R_CH    # where the far side of the wall crosses the road
W_BRIDGE = 13.0      # the bridge's half width
STAIR_U0, STAIR_U1 = 50.0, 70.0
STAIR_Z = 11.2
STAIR_W = 8.5        # half width
WELL_LIP, WELL_Z, WELL_R = 148.0, 172.0, 20.0   # the oculus: a light well in a funnel hanging from the roof
PORTAL_A = 25.0      # half the arc of the wall the throat comes through (degrees)
PORTAL_Z = 72.0
MOUTH_U = _kit.MOUTH - _kit.ROAD_LEN
TIERS = (-24.0, 8.0, 40.0, 72.0, 104.0, 136.0)

C = Vector((U, 0.0, S_Z))
_t = math.radians(TILT)
A = Vector((-math.cos(_t), 0.0, -math.sin(_t)))
L = Vector((0.0, 1.0, 0.0))
T = Vector((-math.sin(_t), 0.0, math.cos(_t)))
EYE_S = 0.88         # the eye's modelled at 42 m radius, then scaled down and seated on the hull
EYE_M = Matrix.Translation(A * 6.3) @ Matrix((L, T, A)).transposed().to_4x4() @ Matrix.Scale(EYE_S, 4)
_PREVIEW = any('preview' in os.path.basename(a) for a in sys.argv if a.endswith('.py'))
M = {}


def _dir(phi, lam):
    """A unit vector out of the sphere: phi degrees up from the eye, lam from the left pole."""
    p, l = math.radians(phi), math.radians(lam)
    return (A * math.cos(p) + T * math.sin(p)) * math.sin(l) + L * math.cos(l)


def _sph(phi, lam, r=S_R):
    return C + _dir(phi, lam) * r


def _ring_dir(theta, psi):
    """A unit vector theta degrees off the eye's axis, psi round it (0 to the left, 90 up)."""
    t, s = math.radians(theta), math.radians(psi)
    return A * math.cos(t) + (L * math.cos(s) + T * math.sin(s)) * math.sin(t)


def _off_eye(d):
    return math.degrees(math.acos(max(-1.0, min(1.0, d.dot(A)))))


def _frame_at(d):
    """A rotation whose z is the outward direction d, its x toward the poles' axis."""
    n = d.normalized()
    x = L - n * L.dot(n)
    if x.length < 1e-3:
        x = T - n * T.dot(n)
    x.normalize()
    return Matrix((x, n.cross(x), n)).transposed()


# --- Textures. --------------------------------------------------------------------------------------------------------
def _tex_hull():
    """512 x 512, 4 x 4 plates: dark worn steel, rust running down from rivets round each plate's edge."""
    n = 512
    rng = np.random.default_rng(61)
    cell = n // 4
    steel = np.array([0.62, 0.66, 0.6])
    rust = np.array([0.6, 0.36, 0.2])
    a = _kit.vnoise(n, 6, 62, 5)
    b = _kit.vnoise(n, 28, 63, 2)
    base = steel * (0.55 + 0.7 * a * (0.8 + 0.4 * b))[..., None]
    streak = _kit.vnoise(n, 48, 64, 2)
    streak = np.repeat(streak[:1], n, axis=0) * (0.5 + 0.5 * _kit.vnoise(n, 5, 65, 2))
    r = _kit.smoothstep(0.42, 0.68, a * 0.6 + streak * 0.5)[..., None]
    base = base * (1 - r * 0.45) + rust * r * 0.45 * (0.5 + b[..., None])
    for i in range(4):
        for j in range(4):
            y0, x0 = i * cell, j * cell
            base[y0:y0 + cell, x0:x0 + cell] *= 0.7 + 0.5 * rng.random()
            # A hatch or stiffener on some.
            if rng.random() < 0.35:
                s = rng.integers(24, 48)
                base[y0 + s:y0 + cell - s, x0 + s:x0 + s + 2] *= 0.35
                base[y0 + s:y0 + cell - s, x0 + cell - s:x0 + cell - s + 2] *= 0.35
                base[y0 + s:y0 + s + 2, x0 + s:x0 + cell - s] *= 0.35
                base[y0 + cell - s:y0 + cell - s + 2, x0 + s:x0 + cell - s] *= 0.35
            for k in range(1, 8):
                p = k * cell // 8
                for ry, rx in ((y0 + 7, x0 + p), (y0 + cell - 8, x0 + p), (y0 + p, x0 + 7), (y0 + p, x0 + cell - 8)):
                    base[ry - 3:ry + 4, rx - 3:rx + 4] *= 0.35
                    base[ry - 2:ry + 1, rx - 2:rx + 1] = np.array([0.72, 0.75, 0.68])
                    base[ry + 3:ry + 16, rx - 1:rx + 1] = base[ry + 3:ry + 16, rx - 1:rx + 1] * 0.7 + rust * 0.25
    return np.clip(base, 0, 1)


def _tex_heart():
    """256 x 256: the left half the eye, white hot to green; the right half one module of a lit band."""
    n = 256
    img = np.zeros((n, n, 3))
    yy, xx = np.mgrid[0:n, 0:n] + 0.5
    r = np.hypot((xx - 64) / 62, (yy - 128) / 124)
    ang = np.arctan2((yy - 128) / 124, (xx - 64) / 62)
    rays = 0.82 + 0.18 * np.cos(ang * 24)
    hot = np.array([1.0, 1.0, 0.95])
    pale = np.array([0.2, 0.32, 0.24])
    green = np.array([0.03, 0.13, 0.06])
    t0 = _kit.smoothstep(0.2, 0.52, r)[..., None]
    t1 = _kit.smoothstep(0.55, 1.0, r)[..., None]
    eye = hot * (1 - t0) + pale * t0 * rays[..., None]
    eye = eye * (1 - t1) + green * t1
    img[:, :128] = eye[:, :128]
    v = np.arange(n)[:, None] / n
    across = 0.62 + 0.38 * np.exp(-((v - 0.5) / 0.22) ** 2)
    along = (np.arange(128)[None, :] - 64) / 64
    bars = 1 - 0.7 * _kit.smoothstep(0.8, 0.95, np.abs(along))
    band = (across * bars)[..., None] * np.array([0.09, 0.5, 0.12])
    img[:, 128:] = band
    return np.clip(img, 0, 1)


def _rack(n, cabs, cols, seed, pitch, dot, gain):
    """Cabinets of small status lights on black, in long runs that are lit or dark, a few white."""
    rng = np.random.default_rng(seed)
    img = np.ones((n, n, 3)) * np.array([0.0012, 0.0025, 0.0016])
    cab_w = n // cabs
    for cab in range(cabs):
        x0 = cab * cab_w
        img[:, x0:x0 + max(2, cab_w // 12)] = 0.001
        gap = (cab_w - cab_w // 12) // cols
        for col in range(cols):
            cx = x0 + cab_w // 12 + 2 + col * gap
            y = 2
            while y < n - pitch:
                run = rng.integers(3, 16)
                on = rng.random() < 0.62
                level = rng.uniform(0.25, 1.0)
                for _ in range(run):
                    if y >= n - pitch:
                        break
                    if on and rng.random() < 0.8:
                        c = np.array([0.2, 1.0, 0.28]) * gain * level * rng.uniform(0.5, 1.0)
                        if rng.random() < 0.015:
                            c = np.array([0.8, 1.0, 0.82]) * gain
                        img[y:y + dot, cx:cx + dot + 2] = c
                    y += pitch
    return np.clip(img, 0, 1)


def _tex_rack():
    """512 x 512, about 12 m across: the towers' racks, up close."""
    return _rack(512, 3, 6, 71, 15, 7, 0.62)


def _tex_rack_far():
    """256 x 256: the walls' racks, further off in the mist: finer and dimmer."""
    return _rack(256, 4, 5, 72, 8, 4, 0.34)


def _tex_floor():
    """512 x 512: black wet concrete and asphalt, cracked, puddled lighter; no paint or dust (the road's own has both)."""
    n = 512
    rng = np.random.default_rng(81)
    v = 0.34 + 0.4 * _kit.vnoise(n, 6, 82, 5)
    grain = rng.random((n, n)) * 0.2 + 0.9
    cracks = np.zeros((n, n))
    for _ in range(14):
        _kit.crack_walk(cracks, rng, (rng.uniform(0, n), rng.uniform(0, n)), 40, 6.0, 1.0, 2, 0.5)
    v = v * grain * (1 - 0.92 * cracks)
    return v[..., None] * np.array([0.82, 0.86, 0.82])


def _tex_sign():
    """256 x 64: kerb signage in the terminals' letters."""
    w, h = 256, 64
    img = np.zeros((h, w))
    text = 'CORE ACCESS'
    s = 4
    x0 = 8
    for ci, ch in enumerate(text):
        g = _kit.FONT.get(ch, _kit.FONT[' '])
        for k, bit in enumerate(g):
            if bit == '1':
                r, c = divmod(k, 5)
                y, x = 18 + r * s, x0 + ci * 22 + c * s
                img[y:y + s, x:x + s] = 1.0
    bg = 0.12
    rgb = (bg + img * 0.88)[..., None] * np.array([0.3, 1.0, 0.36])
    return np.clip(rgb, 0, 1)


def _tex_puff():
    """256 x 256 RGBA: the left half a soft billow of mist; the right a wisp rising, thick at its foot, torn as it thins."""
    n = 256
    out = np.ones((n, n, 4))
    out[..., :3] = np.array([0.66, 0.75, 0.7])
    yy, xx = np.mgrid[0:n, 0:n // 2]
    x, y = (xx + 0.5) / (n // 2), (yy + 0.5) / n
    noise = _kit.vnoise(n, 4, 91, 5)[:, :n // 2]
    edge = np.clip(1 - np.hypot(x - 0.5, y - 0.5) * 2.2, 0, 1)
    out[:, :n // 2, 3] = edge ** 1.3 * (0.45 + 0.75 * _kit.smoothstep(0.25, 0.75, noise)) * 0.85
    # (Rows run top down: t is 0 at the wisp's foot, 1 at its top. Noise drawn out up the wisp, so it reads as rising.)
    t = 1 - y
    drawn = _kit.vnoise(n, 6, 94, 4)
    wob = drawn[:, 3][:, None]
    streak = _kit.vnoise(n, 10, 95, 4)
    streak = streak[np.ix_((np.arange(n) // 2) % n, np.arange(n // 2))]
    centre = 0.5 + (0.17 * np.sin(t * 7.0 + 0.8) + 0.08 * np.sin(t * 17.0)) * t ** 0.6 + (wob - 0.5) * 0.3 * t
    width = 0.07 + 0.2 * t
    body = np.exp(-(((x - centre) / width) ** 2))
    fade = _kit.smoothstep(0.0, 0.07, t) * (1 - t) ** 1.3
    out[:, n // 2:, 3] = np.clip(body * fade * (0.08 + 1.5 * _kit.smoothstep(0.38, 0.7, streak)), 0, 1) * 0.72
    return np.clip(out, 0, 1)


def _tex_shaft():
    """128 x 256 RGBA: the light falling from the oculus, strongest at the top and down its middle."""
    h, w = 256, 128
    yy, xx = np.mgrid[0:h, 0:w]
    across = np.exp(-(((xx + 0.5) / w - 0.5) / 0.3) ** 2)
    down = (1 - yy / (h - 1)) ** 1.5
    streaks = 0.7 + 0.3 * _kit.vnoise(256, 24, 92, 2)[:h, :w][0][None, :]
    out = np.ones((h, w, 4))
    out[..., :3] = np.array([0.72, 1.0, 0.8])
    out[..., 3] = np.clip(across * down * streaks * 0.5, 0, 1)
    return out


def _tex_glow(col):
    """64 x 128 RGBA: a reflection on the wet floor, its top (v 1) where it meets what throws it."""
    def f():
        h, w = 128, 64
        yy, xx = np.mgrid[0:h, 0:w]
        across = np.exp(-(((xx + 0.5) / w - 0.5) / 0.26) ** 2)
        along = (1 - yy / (h - 1)) ** 0.0 * _kit.smoothstep(0.0, 0.25, yy / (h - 1)) * (1 - yy / (h - 1)) ** 1.1
        wob = 0.7 + 0.3 * _kit.vnoise(128, 8, 93, 2)[:h, :w]
        out = np.ones((h, w, 4))
        out[..., :3] = np.array(col)
        out[..., 3] = np.clip(across * along * wob * 1.8, 0, 1)
        return out
    return f


def _materials(kit):
    kit.register_texture('corehull', _tex_hull)
    kit.register_texture('coreheart', _tex_heart)
    kit.register_texture('corerack', _tex_rack)
    kit.register_texture('corefloor', _tex_floor)
    kit.register_texture('corerackfar', _tex_rack_far)
    kit.register_texture('coresign', _tex_sign)
    kit.register_texture('corepuff', _tex_puff, jpeg=False)
    kit.register_texture('coreshaft', _tex_shaft, jpeg=False)
    kit.register_texture('coregreen', _tex_glow((0.3, 1.0, 0.38)), jpeg=False)
    kit.register_texture('corered', _tex_glow((1.0, 0.12, 0.08)), jpeg=False)
    kit.register_texture('corepale', _tex_glow((0.42, 0.62, 0.48)), jpeg=False)
    p = kit.PREFIX
    M.update({
        'hull': kit.material(f'{p}CoreHull', (0.5, 0.5, 0.5), 0.46, 0.2, tex='corehull'),
        'seam': kit.material(f'{p}CoreSeam', (0.03, 0.035, 0.03), 0.8, 0.2),
        'metal': kit.material(f'{p}CoreMetal', (0.2, 0.22, 0.2), 0.48, 0.25, tex='corehull'),
        'cable': kit.material(f'{p}CoreCable', (0.05, 0.055, 0.05), 0.5, 0.0, spec=0.25),
        'wet': kit.material(f'{p}CoreWet', (0.5, 0.5, 0.5), 0.42, 0.0, tex='corefloor', spec=0.3),
        'heart': kit.material(f'{p}Heart', (0.2, 0.9, 0.3), 0.4, vcol=False, tex='coreheart', emission=(1, 1, 1), strength=4.5, emit_tex=True),
        'oculus': kit.material(f'{p}OculusPanel', (0.6, 0.9, 0.7), 0.4, vcol=False, emission=(0.5, 0.82, 0.6), strength=1.0),
        'rack': kit.material(f'{p}RackScreen', (0.0, 0.0, 0.0), 0.75, vcol=False, tex='corerack', emission=(1, 1, 1), strength=3.0, emit_tex=True, spec=0.1),
        'rackfar': kit.material(f'{p}RackFarScreen', (0.0, 0.0, 0.0), 0.75, vcol=False, tex='corerackfar', emission=(1, 1, 1), strength=3.0, emit_tex=True, spec=0.1),
        'dimled': kit.material(f'{p}CoreLed', (0.1, 0.4, 0.14), 0.4, vcol=False, emission=(0.1, 0.42, 0.13), strength=4.0),
        'void': kit.material(f'{p}CoreVoid', (0.004, 0.005, 0.0045), 1.0, 0.0, spec=0.0),
        'lamp': kit.material(f'{p}CoreRed', (0.5, 0.02, 0.01), 0.4, vcol=False, emission=(0.75, 0.03, 0.02), strength=5.0),
        'sign': kit.material(f'{p}SignLed', (0.1, 0.4, 0.15), 0.4, vcol=False, tex='coresign', emission=(1, 1, 1), strength=3.5, emit_tex=True),
        'smoke': kit.material(f'{p}SmokeMist', (0.5, 0.6, 0.53), 1.0, vcol=False, tex='corepuff', alpha_tex=True, emission=(1, 1, 1), strength=0.2, emit_tex=True, spec=0.0),
        'shaft': kit.material(f'{p}ShaftMist', (0.7, 1.0, 0.8), 1.0, vcol=False, tex='coreshaft', alpha_tex=True, emission=(1, 1, 1), strength=1.2, emit_tex=True, spec=0.0),
        'wash': kit.material(f'{p}WashMist', (0.2, 0.3, 0.24), 1.0, vcol=False, tex='corepale', alpha_tex=True, emission=(1, 1, 1), strength=1.0, emit_tex=True, spec=0.0),
        'gleam': kit.material(f'{p}GleamMist', (0.1, 0.4, 0.15), 1.0, vcol=False, tex='coregreen', alpha_tex=True, emission=(1, 1, 1), strength=1.1, emit_tex=True, spec=0.0),
        'redgleam': kit.material(f'{p}RedGleamMist', (0.4, 0.05, 0.03), 1.0, vcol=False, tex='corered', alpha_tex=True, emission=(1, 1, 1), strength=1.6, emit_tex=True, spec=0.0),
    })


# --- Mesh helpers. ----------------------------------------------------------------------------------------------------
def _flip_out(faces, out):
    """Turns faces so their normals agree with `out` (a vector, or a function of the face's centre)."""
    for f in faces:
        f.normal_update()
        d = out(f.calc_center_median()) if callable(out) else out
        if f.normal.dot(d) < 0:
            f.normal_flip()


def _strip(bm, dirs, prof, mat=0, centre=C, r=S_R):
    """Runs an open profile (across, above the surface) along a path of unit vectors out of the sphere. Returns its faces."""
    rings = []
    n = len(dirs)
    for i, d in enumerate(dirs):
        t = (dirs[min(i + 1, n - 1)] - dirs[max(i - 1, 0)]).normalized()
        s = t.cross(d).normalized()
        rings.append([bm.verts.new(centre + d * (r + b) + s * a) for a, b in prof])
    faces = []
    for a, b in zip(rings, rings[1:]):
        for i in range(len(prof) - 1):
            f = bm.faces.new((a[i], a[i + 1], b[i + 1], b[i]))
            f.material_index = mat
            faces.append(f)
    _flip_out(faces, lambda c: c - centre)
    return faces


def _rivet(bm, p, n, size=0.3, mat=0):
    """A four-sided rivet head: base corners sitting on the surface, its point proud."""
    x = n.orthogonal().normalized()
    y = n.cross(x)
    top = bm.verts.new(p + n * size * 0.9)
    base = [bm.verts.new(p + (x * math.cos(k * math.pi / 2) + y * math.sin(k * math.pi / 2)) * size) for k in range(4)]
    for k in range(4):
        f = bm.faces.new((base[k], base[(k + 1) % 4], top))
        f.material_index = mat
    return top


def _cable(bm, path, radius, sides=6, mat=0, taper=1.0):
    """A round tube along a path, by parallel transport (so it doesn't pinch or twist where it runs straight up)."""
    n = len(path)
    t = (path[1] - path[0]).normalized()
    u = t.orthogonal().normalized()
    rings = []
    for i, p in enumerate(path):
        tn = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
        u = (u - tn * u.dot(tn)).normalized()
        v = tn.cross(u)
        r = radius * (1 + (taper - 1) * i / max(n - 1, 1))
        rings.append([bm.verts.new(p + (u * math.cos(2 * math.pi * k / sides) + v * math.sin(2 * math.pi * k / sides)) * r)
                      for k in range(sides)])
    for a, b in zip(rings, rings[1:]):
        for k in range(sides):
            j = (k + 1) % sides
            bm.faces.new((a[k], a[j], b[j], b[k])).material_index = mat


def _bez(p0, p1, p2, p3, n=20):
    out = []
    for i in range(n + 1):
        t = i / n
        s = 1 - t
        out.append(p0 * (s ** 3) + p1 * (3 * s * s * t) + p2 * (3 * s * t * t) + p3 * (t ** 3))
    return out


def _grid(bm, u0, u1, v0, v1, z, step, mat=0):
    """A flat, upward facing grid, so baked light has vertices."""
    nu = max(1, round((u1 - u0) / step))
    nv = max(1, round((v1 - v0) / step))
    vs = [[bm.verts.new((u0 + (u1 - u0) * i / nu, v0 + (v1 - v0) * j / nv, z)) for j in range(nv + 1)] for i in range(nu + 1)]
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((vs[i][j], vs[i + 1][j], vs[i + 1][j + 1], vs[i][j + 1])).material_index = mat


def _quad(bm, a, b, c, d, mat=0, out=None):
    f = bm.faces.new([bm.verts.new(x) for x in (a, b, c, d)])
    f.material_index = mat
    if out is not None:
        _flip_out([f], out)
    return f


def _tint(me, values):
    """Multiplies a mesh's baked vertex colours by a value per vertex (crisp seams and plate-to-plate variation)."""
    ca = me.color_attributes['AO']
    n = len(me.loops)
    cols = np.zeros(n * 4, np.float32)
    ca.data.foreach_get('color', cols)
    cols = cols.reshape(-1, 4)
    vi = np.zeros(n, np.int64)
    me.loops.foreach_get('vertex_index', vi)
    cols[:, :3] *= np.asarray(values, np.float32)[vi, None]
    ca.data.foreach_set('color', cols.ravel())


# The light the sphere and everything round it is painted with, in the road's-end frame.
GREEN = (0.45, 1.0, 0.55)
WHITE = (0.8, 1.0, 0.85)


def _band_defs():
    """The lit bands: (phi, width m, lam from, lam to)."""
    return [(33.8, 1.25, 14, 166), (36.6, 1.25, 16, 164), (-39.0, 1.7, 14, 166), (-42.6, 1.7, 16, 164), (58.0, 1.0, 20, 160), (-63.0, 1.5, 22, 158),
            (12.5, 1.0, 12, 52), (12.5, 1.0, 128, 168), (-14.0, 1.0, 12, 50), (-14.0, 1.0, 130, 168), (76.0, 1.0, 30, 150)]


def _sphere_lights():
    out = [(tuple(C + A * (S_R + 8)), WHITE, 18.0, 1.1),
           (tuple(C + A * (S_R + 2)), GREEN, 34.0, 0.45),
           ((U - 8, 0.0, STAIR_Z + 3), WHITE, 42.0, 2.2),   # up from the plinth's glow
           ((U - 40, 0.0, 6.0), GREEN, 50.0, 1.0),
           ((U - 30, 0.0, ROOF_Z), WHITE, 90.0, 1.5)]       # down from the oculus: the dome's sheen
    for phi, w, l0, l1 in _band_defs():
        for lam in range(int(l0), int(l1) + 1, 14):
            if _off_eye(_dir(phi, lam)) > 30:
                out.append((tuple(_sph(phi, lam, S_R + 5)), GREEN, 8.0, 0.8))
    return out


_AMB_SPHERE = (0.08, 0.1, 0.085)


# --- The sphere. ------------------------------------------------------------------------------------------------------
def _hull(kit):
    """The dark under-sphere, then the riveted plates over its front, brick-laid along lines of longitude."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    rng = np.random.default_rng(101)
    # The dark under-sphere, its rings round the eye's axis, holed where the eye's throat goes in.
    rings = []
    seg = 44
    for th in list(range(22, 180, 8)):
        rings.append([bm.verts.new(C + _ring_dir(th, k * 360 / seg) * (S_R - 0.1)) for k in range(seg)])
    for a, b in zip(rings, rings[1:]):
        for k in range(seg):
            j = (k + 1) % seg
            f = bm.faces.new((a[k], a[j], b[j], b[k]))
            f.material_index = 1
            _flip_out([f], lambda c: c - C)
    tints = {}

    def plate(p0, p1, l0, l1, kind):
        g = 0.14
        h = rng.uniform(0.22, 0.5) + (0.35 if kind == 2 else 0.0)
        e = 0.28
        outer = [_sph(p0 + g, l0 + g), _sph(p0 + g, l1 - g), _sph(p1 - g, l1 - g), _sph(p1 - g, l0 + g)]
        inner = [_sph(p0 + e, l0 + e, S_R + h), _sph(p0 + e, l1 - e, S_R + h), _sph(p1 - e, l1 - e, S_R + h), _sph(p1 - e, l0 + e, S_R + h)]
        vo = [bm.verts.new(x) for x in outer]
        vi = [bm.verts.new(x) for x in inner]
        i, j = rng.integers(0, 4, 2)
        cols = max(1, min(4 - j, round((l1 - l0) / 9)))
        rect = lambda a, b: ((j + (0.0 if a == 0 else cols)) / 4, (i + (0.0 if b == 0 else 1.0)) / 4)
        uv = [rect(0, 0), rect(1, 0), rect(1, 1), rect(0, 1)]
        fs = []
        for k in range(4):
            m = (k + 1) % 4
            f = bm.faces.new((vo[k], vo[m], vi[m], vi[k]))
            f.material_index = 0
            fs.append(f)
            for lp in f.loops:
                lp[uvl].uv = uv[k] if lp.vert in (vo[k], vi[k]) else uv[m]
        top = bm.faces.new(vi)
        top.material_index = 2 if kind == 1 else 0
        for lp, u in zip(top.loops, uv):
            lp[uvl].uv = u
        fs.append(top)
        _flip_out(fs, lambda c: c - C)
        shade = rng.uniform(0.74, 1.0)
        for v in vo:
            tints[v] = shade * 0.55
        for v in vi:
            tints[v] = shade
        # Its rivets, in geometry: round the plate's edge.
        for a, b in ((0.1, 0.1), (0.5, 0.1), (0.9, 0.1), (0.9, 0.5), (0.9, 0.9), (0.5, 0.9), (0.1, 0.9), (0.1, 0.5)):
            ph, la = p0 + (p1 - p0) * a, l0 + (l1 - l0) * b
            d = _dir(ph, la)
            _rivet(bm, C + d * (S_R + h - 0.03), d, 0.21)

    step = 8
    for ri, phi0 in enumerate(range(-112, 112, step)):
        lam = 9 + (ri % 2) * 4.0
        while lam < 171:
            w = rng.choice([8.0, 8.0, 10.0, 12.0])
            lam1 = min(lam + w, 171.0)
            s = math.sin(math.radians((lam + lam1) / 2))
            span = 2 if s < 0.34 else 1
            if ri % span == 0:
                mid = _dir(phi0 + step * span / 2, (lam + lam1) / 2)
                if _off_eye(mid) > 28.0:
                    r = rng.random()
                    kind = 1 if r < 0.04 else 2 if r < 0.14 else 0
                    plate(phi0, phi0 + step * span, lam, lam1, kind)
            lam = lam1
    bm.verts.index_update()
    vals = np.ones(len(bm.verts))
    for v, s in tints.items():
        vals[v.index] = s
    # (Its faces already look outward, and the under-sphere's lathe is closed.)
    me = kit.mesh_from('CoreHull', bm, [M['hull'], M['seam'], M['seam']], recalc=False)
    kit.bake_light(me, _sphere_lights(), ambient=_AMB_SPHERE)
    _tint(me, vals)
    return me


def _clamp(bm, d, rng, size=1.0, mat=0, led=1, lift=0.0, spin=0.0):
    """A heavy block bolted to the hull: base plate, stepped housing, gussets, straps, rivets and a few status lights."""
    R0 = _frame_at(d)
    if spin:
        R0 = R0 @ Matrix.Rotation(math.radians(spin), 3, 'Z')
    x, y, n = R0.col[0], R0.col[1], R0.col[2]
    base = C + d * (S_R + lift)
    s = size

    def box(a, b, h0, sx, sy, sz, m=mat):
        _box(bm, base + x * (a * s) + y * (b * s) + n * (h0 * s + sz * s / 2), (sx * s, sy * s, sz * s), m, R0)

    box(0, 0, 0.0, 16, 11, 1.5)
    box(0, 0, 1.5, 13, 8.6, 3.0)
    box(0, 0, 4.5, 9.5, 6.5, 2.0)
    box(0, 0, 6.5, 6.0, 4.0, 1.0)
    for sx in (-1, 1):
        box(sx * 7.2, 0, 1.5, 1.2, 8.0, 2.2)
        box(sx * 4.8, 4.9, 1.5, 2.2, 1.0, 2.8)
        box(sx * 4.8, -4.9, 1.5, 2.2, 1.0, 2.8)
        box(sx * 3.2, 0, 4.5, 0.7, 7.4, 2.6)
    # Status lights on its flank and top.
    for k in range(-2, 3):
        box(k * 1.2, -4.34, 3.4, 0.8, 0.06, 0.45, led)
        box(k * 1.2, 4.34, 3.4, 0.8, 0.06, 0.45, led)
    box(0, -3.28, 5.5, 3.0, 0.06, 0.5, led)
    for k in range(-3, 4):
        for side in (-1, 1):
            _rivet(bm, base + x * (k * 2.1 * s) + y * (side * 5.0 * s) + n * (1.5 * s), n, 0.32 * s, mat)
    for k in (-1, 1):
        for b in (-3, -1, 1, 3):
            _rivet(bm, base + x * (k * 7.4 * s) + y * (b * s) + n * (1.5 * s), n, 0.32 * s, mat)


def _box(bm, c, size, mat, rot):
    _kit.add_box(bm, c, size, mat, rot=rot)


def _armour(kit):
    """What's bolted over the plates: the girdle, the spine, the eye's collar and gear, the lit bands' housings, clamps."""
    bm = bmesh.new()
    rng = np.random.default_rng(111)
    belt = [(-2.9, 0.0), (-2.6, 1.3), (-1.5, 1.45), (-1.3, 1.0), (1.3, 1.0), (1.5, 1.45), (2.6, 1.3), (2.9, 0.0)]
    # The girdle (through the poles and the eye's level), and the spine (over the eye, top to bottom).
    girdle = [[_dir(0, x) for x in np.arange(6, 66, 2.5)], [_dir(0, x) for x in np.arange(114, 174.5, 2.5)]]
    spine = [[_dir(x, 90) for x in np.arange(25, 125, 2.5)], [_dir(x, 90) for x in np.arange(-125, -25, 2.5)]]
    for run in girdle + spine:
        _strip(bm, run, belt)
        step = 2
        for i in range(1, len(run) - 1, step):
            t = (run[i + 1] - run[i - 1]).normalized()
            s = t.cross(run[i]).normalized()
            for a in (-2.2, 2.2):
                _rivet(bm, C + run[i] * (S_R + 1.2) + s * a, run[i], 0.34)
    # A narrower raised rib down each side of the eye (the stiffeners the reference's panels run into).
    for phi in (-92.0, 92.0, 47.0, -51.0, 70.0):
        _strip(bm, [_dir(phi, x) for x in np.arange(30, 151, 3)], [(-1.0, 0.0), (-0.8, 0.9), (0.8, 0.9), (1.0, 0.0)])
    # The lit bands' housings.
    for phi, w, l0, l1 in _band_defs():
        hw = w / 2 + 0.55
        prof = [(-hw - 0.25, 0.0), (-hw, 1.45), (-w / 2 - 0.05, 1.35), (-w / 2 - 0.05, 0.95), (w / 2 + 0.05, 0.95), (w / 2 + 0.05, 1.35), (hw, 1.45), (hw + 0.25, 0.0)]
        rns = []
        cur = []
        for x in np.arange(l0, l1 + 0.1, 2.5):
            d = _dir(phi, x)
            if _off_eye(d) > 30.0:
                cur.append(d)
            elif cur:
                rns.append(cur)
                cur = []
        if cur:
            rns.append(cur)
        for run in rns:
            if len(run) > 1:
                _strip(bm, run, prof)
                for i in range(0, len(run), 3):
                    t = (run[min(i + 1, len(run) - 1)] - run[max(i - 1, 0)]).normalized()
                    s = t.cross(run[i]).normalized()
                    for a in (-hw, hw):
                        _rivet(bm, C + run[i] * (S_R + 1.4) + s * a, run[i], 0.26)
    # The dashes' ring round the eye.
    _ring_run = [_ring_dir(31.0, a) for a in np.arange(0, 361, 4.5)]
    _strip(bm, _ring_run, [(-1.2, 0.0), (-0.95, 1.3), (-0.55, 1.25), (-0.55, 0.9), (0.55, 0.9), (0.55, 1.25), (0.95, 1.3), (1.2, 0.0)])
    # The clamps: the big pair at the girdle's ends, the spine's stack, the shoulders, under the eye.
    for lam, side in ((22.0, 1), (158.0, -1)):
        _clamp(bm, _dir(0, lam), rng, size=1.45, led=1, lift=1.0)
        _clamp(bm, _dir(0, lam + side * 26), rng, size=0.66, led=1, lift=1.0)
    for phi, s in ((37.0, 0.85), (53.0, 0.7), (68.0, 0.8), (82.0, 0.62)):
        _clamp(bm, _dir(phi, 90), rng, size=s, led=1, lift=1.0, spin=90.0)
    for phi, s in ((-46.0, 0.62), (-62.0, 0.66), (-78.0, 0.56)):
        _clamp(bm, _dir(phi, 90), rng, size=s, led=1, lift=1.0, spin=90.0)
    for phi, lam in ((58.0, 42.0), (58.0, 138.0), (-52.0, 40.0), (-52.0, 140.0)):
        _clamp(bm, _dir(phi, lam), rng, size=0.8, led=1, lift=0.3)
    # Small things: vents, junction boxes, pipes tracing the hull.
    for _ in range(70):
        phi, lam = rng.uniform(-100, 100), rng.uniform(16, 164)
        d = _dir(phi, lam)
        if _off_eye(d) < 32:
            continue
        _box(bm, C + d * (S_R + 0.8), (rng.uniform(1.4, 3.6), rng.uniform(1.0, 2.2), rng.uniform(0.8, 1.6)), 0, _frame_at(d))
    for phi, l0, l1 in ((41.0, 22, 158), (-47.0, 24, 156), (19.0, 18, 62), (19.0, 118, 162), (-22.0, 18, 62), (-22.0, 118, 162)):
        run = [_dir(phi, x) for x in np.arange(l0, l1 + 0.1, 4)]
        run = [d for d in run if _off_eye(d) > 31]
        if len(run) > 1:
            _cable(bm, [C + d * (S_R + 0.95) for d in run], 0.42, sides=5, mat=2)
    # The crown and the collar under it: stepped drums where the cables go in.
    kit.lathe(bm, [(19, 36.5), (19.5, 38.2), (15, 39.4), (14.5, 42), (11, 43), (10.5, 46.5), (7, 47)], seg=32, cx=C.x, cy=C.y, z0=C.z)
    kit.lathe(bm, [(7, -47), (9.5, -46.2), (10, -44), (14, -43.2), (14.5, -40.5), (17.5, -39.6), (18, -37)], seg=36, cx=C.x, cy=C.y, z0=C.z)
    me = kit.mesh_from('CoreArmour', bm, [M['metal'], kit.MAT['led'], M['cable']], recalc=False)
    kit.box_uvs(me, 0.055)
    kit.bake_light(me, _sphere_lights(), ambient=(0.08, 0.1, 0.085))
    # Dark where it meets the hull, catching the light where it stands proud.
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    h = np.linalg.norm(co.reshape(-1, 3) - np.array(C), axis=1) - S_R
    _tint(me, np.clip(0.3 + h * 0.34, 0.3, 1.0))
    return me


def _eye(kit):
    """The ring gear round the eye: collar, teeth, stepped throat, the lens's mullions and heavy cross. Modelled on +z, then
    turned to A."""
    bm = bmesh.new()
    col = [(19.8, 36.2), (19.8, 39.0), (19.0, 39.9), (17.6, 40.0), (17.1, 38.4), (16.3, 38.2), (15.9, 35.6), (15.0, 35.2), (14.6, 32.6)]
    kit.lathe(bm, col, seg=84, cap_top=False, cap_bottom=False)
    # A second raised ring out on the hull.
    kit.lathe(bm, [(23.2, 34.7), (23.1, 35.6), (22.2, 36.0), (21.0, 36.4), (20.2, 36.2)], seg=84, cap_top=False, cap_bottom=False)
    # Teeth.
    nt = 60
    for k in range(nt):
        a = 2 * math.pi * k / nt
        R0 = Matrix.Rotation(a, 3, 'Z')
        _kit.add_box(bm, (20.5 * math.cos(a), 20.5 * math.sin(a), 37.6), (1.5, 1.05, 2.3), 0, rot=R0)
    for k in range(30):
        a = 2 * math.pi * (k + 0.5) / 30
        R0 = Matrix.Rotation(a, 3, 'Z')
        _kit.add_box(bm, (18.3 * math.cos(a), 18.3 * math.sin(a), 40.1), (0.8, 0.8, 0.5), 0, rot=R0)
    for k in range(40):
        a = 2 * math.pi * k / 40
        _rivet(bm, Vector((21.7 * math.cos(a), 21.7 * math.sin(a), 36.3)), Vector((0, 0, 1)), 0.32)
    # Fins down the throat.
    for k in range(32):
        a = 2 * math.pi * k / 32
        R0 = Matrix.Rotation(a, 3, 'Z')
        _kit.add_box(bm, (15.4 * math.cos(a), 15.4 * math.sin(a), 35.8), (1.1, 0.32, 1.6), 0, rot=R0)
    # The lens's frame over the glow: rings, thin mullions, a heavy cross.
    for r0, r1, z in ((13.2, 14.6, 33.0), (9.7, 10.4, 33.0), (5.6, 6.1, 33.0)):
        kit.lathe(bm, [(r1, z - 0.3), (r1, z + 0.4), (r0, z + 0.4), (r0, z - 0.3)], seg=48, cap_top=False, cap_bottom=False)
    for k in range(16):
        a = 2 * math.pi * (k + 0.5) / 16
        R0 = Matrix.Rotation(a, 3, 'Z')
        _kit.add_box(bm, (10.0 * math.cos(a), 10.0 * math.sin(a), 33.1), (8.2, 0.32, 0.5), 0, rot=R0)
    for k in range(4):
        a = math.pi / 2 * k
        R0 = Matrix.Rotation(a, 3, 'Z')
        _kit.add_box(bm, (9.6 * math.cos(a), 9.6 * math.sin(a), 33.4), (10.4, 1.1, 1.1), 0, rot=R0)
        _kit.add_box(bm, (17.9 * math.cos(a), 17.9 * math.sin(a), 39.0), (5.2, 3.6, 3.0), 0, rot=R0)
    bmesh.ops.transform(bm, matrix=Matrix.Translation(C) @ EYE_M, verts=bm.verts)
    me = kit.mesh_from('CoreEye', bm, [M['metal']], recalc=False)
    kit.box_uvs(me, 0.07)
    lights = [(tuple(C + A * 34.0), WHITE, 13.0, 2.6), (tuple(C + A * 47.0), GREEN, 18.0, 0.7)]
    kit.bake_light(me, lights, ambient=(0.14, 0.18, 0.15))
    return me


def _heart(kit):
    """Everything lit that pulses, the eye and the bands, as one mesh on City5Heart, its origin at the sphere's centre."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    rng = np.random.default_rng(121)

    def band_quad(d0, d1, w, h):
        t = (d1 - d0).normalized()
        s0 = t.cross(d0).normalized()
        s1 = t.cross(d1).normalized()
        r = S_R + h
        a, b, c, e = d0 * r - s0 * (w / 2), d1 * r - s1 * (w / 2), d1 * r + s1 * (w / 2), d0 * r + s0 * (w / 2)
        f = bm.faces.new([bm.verts.new(x) for x in (a, b, c, e)])
        for lp, uv in zip(f.loops, ((0.52, 0.04), (0.98, 0.04), (0.98, 0.96), (0.52, 0.96))):
            lp[uvl].uv = uv
        if f.normal.dot(d0) < 0:
            f.normal_flip()

    for phi, w, l0, l1 in _band_defs():
        lam = float(l0)
        while lam < l1:
            seg = rng.uniform(16, 38) if abs(phi) < 45 and w > 0.9 else rng.uniform(4, 13)
            end = min(lam + seg, l1)
            x = lam
            while x < end - 0.1:
                x1 = min(x + 2.5, end)
                d0, d1 = _dir(phi, x), _dir(phi, x1)
                if _off_eye(d0) > 30.5 and _off_eye(d1) > 30.5:
                    band_quad(d0, d1, w, 1.03)
                x = x1
            lam = end + (rng.uniform(1.0, 3.5) if abs(phi) < 45 and w > 0.9 else rng.uniform(3, 11))
    # The dashes round the eye.
    for k in range(36):
        a0 = k * 10 + 2
        band_quad(_ring_dir(31.0, a0), _ring_dir(31.0, a0 + 5.5), 1.0, 0.98)
    # Arcs on the gear's collar.
    R0 = EYE_M
    for k in range(8):
        a0 = k * 45 + 12
        for j in range(3):
            s0, s1 = math.radians(a0 + j * 7), math.radians(a0 + (j + 1) * 7)
            r0, r1, z = 18.05, 18.65, 40.06
            cs = [(r0, s0), (r1, s0), (r1, s1), (r0, s1)]
            f = bm.faces.new([bm.verts.new(R0 @ Vector((r * math.cos(s), r * math.sin(s), z))) for r, s in cs])
            for lp, uv in zip(f.loops, ((0.52, 0.04), (0.52, 0.96), (0.98, 0.96), (0.98, 0.04))):
                lp[uvl].uv = uv
            if f.normal.dot(A) < 0:
                f.normal_flip()
    # The eye's glow: a disc behind the mullions, its texture white hot in the middle, and a bright boss at its centre.
    rings = [(0.0, 32.0), (2.0, 32.1), (4.5, 32.2), (7.0, 32.2), (10.0, 32.3), (12.5, 32.3), (15.0, 32.4)]
    seg = 48
    tex = lambda r, a: (0.25 + r / 15.0 * 0.242 * math.cos(a), 0.5 + r / 15.0 * 0.484 * math.sin(a))
    verts = []
    for r, z in rings:
        verts.append([bm.verts.new(R0 @ Vector((r * math.cos(2 * math.pi * k / seg), r * math.sin(2 * math.pi * k / seg), z)))
                      for k in range(seg)])
    for ir in range(len(rings) - 1):
        for k in range(seg):
            j = (k + 1) % seg
            f = bm.faces.new((verts[ir][k], verts[ir][j], verts[ir + 1][j], verts[ir + 1][k]) if ir else (verts[0][k], verts[1][k], verts[1][j]))
            for lp in f.loops:
                p = R0.inverted() @ lp.vert.co
                lp[uvl].uv = tex(math.hypot(p.x, p.y), math.atan2(p.y, p.x))
    for f in bm.faces:
        f.normal_update()
    me = kit.mesh_from('CoreHeart', bm, [M['heart']], recalc=False)
    return me


def _cables(kit):
    """The black cables: up into the oculus, up and out to the roof's edge, across to the walls, down to the plinth."""
    bm = bmesh.new()
    rng = np.random.default_rng(131)
    J = lambda s: Vector((rng.uniform(-s, s), rng.uniform(-s, s), rng.uniform(-s, s)))

    # Straight up from the crown, into the oculus.
    for k in range(12):
        a = 2 * math.pi * k / 12
        r0, r1 = rng.uniform(4, 9), rng.uniform(5, 16)
        p0 = Vector((U + r0 * math.cos(a), r0 * math.sin(a), C.z + 46))
        p3 = Vector((U + r1 * math.cos(a), r1 * math.sin(a), WELL_Z + 3))
        _cable(bm, _bez(p0, p0 + Vector((0, 0, 20)), p3 + Vector((0, 0, -24)) + J(3), p3, 14), rng.uniform(0.5, 1.1))
    # Up and out from the shoulders, to the roof's edge.
    for phi, lam, target in ((58, 42, (42.0, 104.0)), (58, 138, (42.0, -104.0)), (72, 58, (85.0, 112.0)), (72, 122, (85.0, -112.0)),
                             (42, 22, (20.0, 92.0)), (42, 158, (20.0, -92.0))):
        d = _dir(phi, lam)
        for k in range(6):
            p0 = C + d * (S_R + 3) + J(3.5)
            tu, tv = target
            p3 = Vector((tu + rng.uniform(-10, 10), tv + rng.uniform(-10, 10), ROOF_Z - 8 + rng.uniform(-6, 6)))
            sag = rng.uniform(26, 44)
            p1 = p0 + d * 26 + Vector((0, 0, -6))
            p2 = p3 + Vector((0, 0, -sag)) + (Vector((U, 0, p3.z)) - p3).normalized() * 12
            _cable(bm, _bez(p0, p1, p2, p3, 20), rng.uniform(0.8, 1.5))
    # From the girdle's clamps, slung across to the walls and falling into the mist.
    for sign, lam in ((1, 22.0), (-1, 158.0)):
        d = _dir(0, lam)
        for k in range(9):
            p0 = C + d * (S_R + 7) + J(4.0)
            if k < 3:
                # Slung up to a balcony.
                a = math.radians(rng.uniform(62, 102))
                z = rng.uniform(70, 120)
                p3 = Vector((U + 126 * math.cos(a), sign * 126 * math.sin(a), z))
                p1 = p0 + d * 16 + Vector((0, 0, -24))
                p2 = p3 + Vector((-3, -sign * 22, -34))
            else:
                # Down into the pit.
                p3 = Vector((rng.uniform(34, 70), sign * rng.uniform(52, 92), PIT_Z + 4))
                p1 = p0 + d * 12 + Vector((0, 0, -22))
                p2 = p3 + Vector((0, 0, 42))
            _cable(bm, _bez(p0, p1, p2, p3, 20), rng.uniform(1.1, 1.9))
    # From the lower hemisphere, hanging legs down to the plinth, and the collar's thinner ones.
    for k in range(18):
        s = -1 if k % 2 else 1
        lam = 90 - s * rng.uniform(16, 74)
        phi = rng.uniform(-82, -30)
        d = _dir(phi, lam)
        p0 = C + d * (S_R + 0.5)
        a = math.atan2(d.y, d.x * 0.6)
        r = rng.uniform(38, 52)
        p3 = Vector((max(U - abs(math.cos(a)) * r * 0.55, STAIR_U1 + 3), s * min(abs(math.sin(a) * r + 14), 46.0), STAIR_Z))
        _cable(bm, _bez(p0, p0 + d * 12, p3 + Vector((0, 0, 26)), p3, 16), rng.uniform(0.5, 1.15))
    for k in range(10):
        a = 2 * math.pi * k / 10
        p0 = Vector((U + 16 * math.cos(a), 16 * math.sin(a), C.z - 38))
        p3 = Vector((U + 21 * math.cos(a), 21 * math.sin(a), STAIR_Z))
        _cable(bm, _bez(p0, p0 + Vector((math.cos(a) * 2, math.sin(a) * 2, -9)), p3 + Vector((0, 0, 9)), p3, 10), rng.uniform(0.6, 1.0))
    me = kit.mesh_from('CoreCables', bm, [M['cable']], smooth=True, recalc=False)
    lights = _sphere_lights()[:4] + [((U, 0, ROOF_Z), WHITE, 34.0, 0.7)]
    kit.bake_light(me, lights, ambient=(0.1, 0.13, 0.11))
    return me


# --- The bay, the towers, the small repeated things. ----------------------------------------------------------------------
BAY_W = 2 * R_CH * math.sin(math.radians(7.5))


def _bay(kit, lit, seed):
    """One balcony bay: its origin on the wall at the slab's top, +x along the wall, +y into the chamber. Racks stand on it,
    black against a black recess; the balcony's pale edge and railing read in front of them."""
    bm = bmesh.new()
    rng = np.random.default_rng(seed)
    w = BAY_W
    add = _kit.add_box
    _quad(bm, (-w / 2, 0.1, -2.2), (w / 2, 0.1, -2.2), (w / 2, 0.1, 30.0), (-w / 2, 0.1, 30.0), 4, out=Vector((0, 1, 0)))
    add(bm, (0, 3.6, -0.6), (w, 7.8, 1.2), 0)
    add(bm, (0, 7.1, -1.7), (w, 0.8, 1.0), 0)
    add(bm, (w / 2, 1.8, 15), (1.6, 3.6, 32), 5)
    add(bm, (0, 7.3, 1.15), (w, 0.12, 0.12), 0)
    add(bm, (0, 7.3, 0.62), (w, 0.08, 0.08), 0)
    for k in range(7):
        add(bm, (-w / 2 + k * w / 6, 7.3, 0.6), (0.12, 0.12, 1.2), 0)
    for x in (-12.0, -4.2, 4.2, 12.0):
        h = rng.uniform(19, 27)
        x += rng.uniform(-0.8, 0.8)
        add(bm, (x, 1.7, h / 2), (6.4, 3.4, h), 4)
        y = 3.42
        _quad(bm, (x - 3.0, y, 0.8), (x + 3.0, y, 0.8), (x + 3.0, y, h - 0.8), (x - 3.0, y, h - 0.8), 1, out=Vector((0, 1, 0)))
    # A short green strip on the fascia.
    x = rng.uniform(-12, 12)
    add(bm, (x, 7.52, -1.7), (2.4, 0.05, 0.16), 3)
    me = kit.mesh_from(f'CoreBay{seed}', bm, [kit.MAT['panel'], M['rackfar'], kit.MAT['light'], M['dimled'], M['void'], kit.MAT['concrete']], recalc=False)
    kit.box_uvs(me, 0.07)
    amb = tuple(c * (0.75 + 0.35 * lit) for c in (0.13, 0.16, 0.14))
    kit.bake_light(me, [((0, 6, 2), GREEN, 7.0, 0.4 * lit), ((0, 34, 6), WHITE, 34.0, 1.3 * lit)], ambient=amb)
    return me


def _tower(kit, h, seed):
    """A freestanding tower of racks: its origin at the base's centre, h tall, 13 m square, slabs every so often."""
    bm = bmesh.new()
    rng = np.random.default_rng(seed)
    add = _kit.add_box
    S = 13.0
    add(bm, (0, 0, h / 2), (S, S, h), 0)
    add(bm, (0, 0, h + 0.5), (S + 0.8, S + 0.8, 1.0), 0)
    z = 0.0
    rows = []
    while z < h - 6:
        z1 = min(z + rng.uniform(14, 20), h - 1)
        rows.append((z, z1))
        add(bm, (0, 0, z1), (S + 0.5, S + 0.5, 0.7), 0)
        z = z1
    # Two tall panels of racks on each face, inside a dark frame; here and there one's dark.
    for (z0, z1) in rows:
        for fx, fy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for side in (-1, 1):
                a, b = side * 0.9, side * (S / 2 - 1.3)
                za, zb = z0 + 1.0, z1 - 1.0
                if rng.random() < 0.14:
                    continue
                d = S / 2 + 0.03
                if fx:
                    _quad(bm, (fx * d, a, za), (fx * d, b, za), (fx * d, b, zb), (fx * d, a, zb), 1, out=Vector((fx, 0, 0)))
                else:
                    _quad(bm, (a, fy * d, za), (b, fy * d, za), (b, fy * d, zb), (a, fy * d, zb), 1, out=Vector((0, fy, 0)))
    me = kit.mesh_from(f'CoreTower{seed}', bm, [kit.MAT['concrete'], M['rack']], recalc=False)
    kit.box_uvs(me, 0.062)
    kit.bake_light(me, [], ambient=(0.035, 0.045, 0.038))
    return me


def _rail(kit):
    """4 m of railing, along +x: posts and two rails."""
    bm = bmesh.new()
    _kit.add_box(bm, (2, 0, 1.2), (4, 0.12, 0.12))
    _kit.add_box(bm, (2, 0, 0.7), (4, 0.07, 0.07))
    _kit.add_box(bm, (0, 0, 0.6), (0.14, 0.14, 1.2))
    me = kit.mesh_from('CoreRail', bm, [kit.MAT['steel']], recalc=False)
    kit.bake_light(me, [], ambient=(0.5, 0.62, 0.54))
    return me


def _worklight(kit):
    """A white work light under a balcony."""
    bm = bmesh.new()
    _kit.add_box(bm, (0, 0, 0), (3.2, 0.5, 0.16), 0)
    return kit.mesh_from('CoreWorkLight', bm, [kit.MAT['light']], recalc=False)


def _beacon(kit):
    """A short post with a red lamp on it."""
    bm = bmesh.new()
    _kit.add_box(bm, (0, 0, 0.5), (0.36, 0.36, 1.0))
    _kit.add_box(bm, (0, 0, 1.05), (0.5, 0.5, 0.12))
    _kit.add_box(bm, (0, 0, 1.3), (0.34, 0.34, 0.4), 1)
    _kit.add_box(bm, (0, 0, 1.55), (0.44, 0.44, 0.08))
    me = kit.mesh_from('CoreBeacon', bm, [kit.MAT['steel'], M['lamp']], recalc=False)
    kit.bake_light(me, [((0, 0, 1.3), (1.0, 0.25, 0.2), 0.8, 0.8)], ambient=(0.3, 0.36, 0.32))
    return me


# --- The chamber's shell and the ground. ----------------------------------------------------------------------------------
def _wall_lights():
    return [(tuple(C + A * (S_R + 10)), GREEN, 100.0, 0.5),
            ((U, 0, ROOF_Z - 10), WHITE, 90.0, 0.4),
            ((U, 0, 0), GREEN, 100.0, 0.25)]


def _shell(kit):
    """The wall (holed where the throat comes in), the pit's floor, the domed roof with its stepped funnel and oculus."""
    bm = bmesh.new()
    zs = [PIT_Z, -14, 0, 14, 28, 42, PORTAL_Z - 15, PORTAL_Z, 86, 100, 114, 128, 142, 156, ROOF_Z - 8]
    da = 5
    n = 360 // da
    vs = {}

    def vert(i, j):
        k = (i % n, j)
        if k not in vs:
            a = math.radians(i * da)
            vs[k] = bm.verts.new((U + R_CH * math.cos(a), R_CH * math.sin(a), zs[j]))
        return vs[k]

    for i in range(n):
        a = i * da + da / 2
        for j in range(len(zs) - 1):
            if abs(a - 180) < PORTAL_A and 0 <= zs[j] < PORTAL_Z:
                continue
            f = bm.faces.new((vert(i, j), vert(i, j + 1), vert(i + 1, j + 1), vert(i + 1, j)))
            f.material_index = 0
    # Ribs up the wall between the bays.
    for k in range(24):
        a = math.radians(k * 15)
        if abs(math.degrees(a) - 180) < PORTAL_A + 2:
            zr0 = PORTAL_Z
        else:
            zr0 = PIT_Z
        h = ROOF_Z - 6 - zr0
        _kit.add_box(bm, (U + (R_CH - 2.5) * math.cos(a), (R_CH - 2.5) * math.sin(a), zr0 + h / 2), (5.0, 3.0, h), 0, rot=Matrix.Rotation(a, 3, 'Z'))
    # The pit's floor.
    for i in range(0, 12):
        a0, a1 = math.radians(i * 30), math.radians((i + 1) * 30)
        rs = [0, 45, 90, R_CH]
        for r0, r1 in zip(rs, rs[1:]):
            c = lambda r, a: (U + r * math.cos(a), r * math.sin(a), PIT_Z)
            _quad(bm, c(r0, a0), c(r1, a0), c(r1, a1), c(r0, a1), 1, out=Vector((0, 0, 1)))
    # The roof: built from the centre out, so its faces look down.
    # (From the well's top, down its inside to the lip, then out and up the funnel's steps to the dome.)
    roof = [(WELL_R, WELL_Z), (WELL_R, WELL_LIP + 5), (WELL_R + 1.2, WELL_LIP + 4.6), (WELL_R + 1.2, WELL_LIP), (WELL_R + 5, WELL_LIP - 1.2), (WELL_R + 8, WELL_LIP + 0.5), (WELL_R + 9, WELL_LIP + 7),
            (WELL_R + 17, WELL_LIP + 8), (WELL_R + 19, WELL_LIP + 16), (WELL_R + 30, WELL_LIP + 17), (WELL_R + 33, ROOF_Z - 6), (82, ROOF_Z + 3), (106, ROOF_Z - 1), (R_CH + 1, ROOF_Z - 9)]
    ring = _kit.lathe(bm, list(reversed(roof)), seg=48, cx=U, cap_top=False, cap_bottom=False, mat=0)
    for k in range(16):
        a = 2 * math.pi * k / 16
        for r0, r1, z0, z1 in ((62, 104, ROOF_Z - 1, ROOF_Z - 3), (104, 128, ROOF_Z - 3, ROOF_Z - 12)):
            mid = (r0 + r1) / 2
            ln = math.hypot(r1 - r0, z1 - z0)
            pitch = math.atan2(z1 - z0, r1 - r0)
            rot = Matrix.Rotation(a, 3, 'Z') @ Matrix.Rotation(-pitch, 3, 'Y')
            _kit.add_box(bm, (U + mid * math.cos(a), mid * math.sin(a), (z0 + z1) / 2 - 1.2), (ln, 3.0, 2.4), 0, rot=rot)
    # The grate across the well, under its light.
    _kit.lathe(bm, [(11.0, WELL_Z - 3.0), (12.6, WELL_Z - 3.0), (12.6, WELL_Z - 1.0), (11.0, WELL_Z - 1.0)], seg=32, cx=U, cap_top=False, cap_bottom=False, mat=1)
    for k in range(8):
        a = math.pi * k / 4 + 0.2
        _kit.add_box(bm, (U + 13 * math.cos(a), 13 * math.sin(a), WELL_Z - 2), (17, 1.0, 1.4), 1, rot=Matrix.Rotation(a, 3, 'Z'))
    me = kit.mesh_from('CoreShell', bm, [kit.MAT['concrete'], kit.MAT['dark']], recalc=False)
    kit.box_uvs(me, 0.05)
    # The wall's a surface seen from inside.
    bmv = bmesh.new()
    bmv.from_mesh(me)
    _flip_out([f for f in bmv.faces if abs(math.hypot(f.calc_center_median().x - U, f.calc_center_median().y) - R_CH) < 0.5],
              lambda c: Vector((U - c.x, -c.y, 0)))
    bmv.to_mesh(me)
    bmv.free()
    kit.bake_light(me, _wall_lights() + [((U, 0, WELL_Z - 4), WHITE, 14.0, 2.6), ((U, 0, WELL_LIP - 8), WHITE, 34.0, 0.9)], ambient=(0.11, 0.14, 0.12))
    return me


def _oculus(kit):
    """The lit parts of the roof's funnel: the white-green disc, and broken arcs round its steps."""
    bm = bmesh.new()
    _kit.lathe(bm, [(0.0, WELL_Z), (WELL_R + 0.2, WELL_Z)], seg=48, cx=U, cap_top=False, cap_bottom=False, mat=0)
    # Lit rings up the well's inside.
    for z in (WELL_LIP + 8, WELL_LIP + 14):
        _kit.lathe(bm, [(WELL_R - 0.05, z + 0.7), (WELL_R - 0.05, z)], seg=48, cx=U, cap_top=False, cap_bottom=False, mat=0)
    rng = np.random.default_rng(141)
    for r, z, w, n, on in ((WELL_R + 5.2, WELL_LIP - 1.35, 0.8, 22, 0.7), (WELL_R + 13.0, WELL_LIP + 7.3, 0.8, 26, 0.65), (WELL_R + 24.5, WELL_LIP + 16.3, 0.8, 34, 0.55)):
        for k in range(n):
            if rng.random() > on:
                continue
            a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 0.72) / n
            r0, r1 = r - w / 2, r + w / 2
            c = lambda rr, a: (U + rr * math.cos(a), rr * math.sin(a), z)
            _quad(bm, c(r0, a0), c(r1, a0), c(r1, a1), c(r0, a1), 1, out=Vector((0, 0, -1)))
    return kit.mesh_from('CoreOculus', bm, [M['oculus'], M['dimled']], recalc=False)


def _throat(kit):
    """From the servers' end (the mouth, 40 m wide, 30 m tall) flaring out to the hole in the wall. Its floor to either side
    of the road, its walls and roof ribbed, with racks down its flanks."""
    bm = bmesh.new()
    u0, u1 = MOUTH_U, U - R_CH * math.cos(math.radians(PORTAL_A))
    v0, v1 = 21.0, R_CH * math.sin(math.radians(PORTAL_A))
    z0, z1 = 31.0, PORTAL_Z
    n = 8
    ease = lambda t: t * t * (3 - 2 * t) * 0.35 + t * 0.65
    us = [u0 + (u1 - u0) * i / n for i in range(n + 1)]
    vw = [v0 + (v1 - v0) * ease(i / n) for i in range(n + 1)]
    zh = [z0 + (z1 - z0) * ease(i / n) for i in range(n + 1)]
    for i in range(n):
        for side in (-1, 1):
            # Flank, in rows, the upper rows darker.
            rows = 4
            for r in range(rows):
                za, zb = zh[i] * r / rows, zh[i] * (r + 1) / rows
                zc, zd = zh[i + 1] * r / rows, zh[i + 1] * (r + 1) / rows
                _quad(bm, (us[i], side * vw[i], za), (us[i + 1], side * vw[i + 1], zc), (us[i + 1], side * vw[i + 1], zd), (us[i], side * vw[i], zb), 0, out=Vector((0, -side, 0)))
            # Roof, half and half.
            _quad(bm, (us[i], 0, zh[i]), (us[i + 1], 0, zh[i + 1]), (us[i + 1], side * vw[i + 1], zh[i + 1]), (us[i], side * vw[i], zh[i]), 0, out=Vector((0, 0, -1)))
            # Rack panels, standing proud of the flank, and a green strip along the floor's edge.
            pad = 0.4
            for r in (0, 1):
                t0, t1 = 0.08 + r * 0.42, 0.44 + r * 0.42
                inset = lambda vv: side * (vv - pad)
                _quad(bm, (us[i] + 1, inset(vw[i]), zh[i] * t0), (us[i + 1] - 1, inset(vw[i + 1]), zh[i + 1] * t0), (us[i + 1] - 1, inset(vw[i + 1]), zh[i + 1] * t1), (us[i] + 1, inset(vw[i]), zh[i] * t1), 1, out=Vector((0, -side, 0)))
            _quad(bm, (us[i] + 0.5, side * (vw[i] - 0.6), 0.3), (us[i + 1] - 0.5, side * (vw[i + 1] - 0.6), 0.3), (us[i + 1] - 0.5, side * (vw[i + 1] - 0.6), 0.5), (us[i] + 0.5, side * (vw[i] - 0.6), 0.5), 2, out=Vector((0, -side, 0)))
        # A rib round each step: flanks and over the top.
        # (From the second on: the mouth itself stays clear.)
        if i:
            hv, hz = vw[i], zh[i]
            for side in (-1, 1):
                _kit.add_box(bm, (us[i], side * (hv - 1.0), hz / 2), (2.2, 2.0, hz), 0)
            _kit.add_box(bm, (us[i], 0, hz - 0.9), (2.2, hv * 2, 1.8), 0)
    # The collar round the mouth, facing back down the hall (closing off anything past the hall's own end).
    O, H = 90.0, 90.0
    for side in (-1, 1):
        _quad(bm, (u0, side * v0, -2), (u0, side * O, -2), (u0, side * O, H), (u0, side * v0, H), 0, out=Vector((-1, 0, 0)))
    _quad(bm, (u0, -v0, z0), (u0, v0, z0), (u0, v0, H), (u0, -v0, H), 0, out=Vector((-1, 0, 0)))
    me = kit.mesh_from('CoreThroat', bm, [kit.MAT['concrete'], M['rack'], M['dimled']], recalc=False)
    kit.box_uvs(me, 0.062)
    lights = [((u1 + 20, 0, 40), WHITE, 70.0, 0.7), ((u0, 0, 14), GREEN, 26.0, 0.25)]
    kit.bake_light(me, lights, ambient=(0.1, 0.13, 0.11))
    return me


def _floor_lights():
    out = [((STAIR_U0 + 6, 0, 3.0), WHITE, 13.0, 1.5),      # the stair's wash on the wet floor
           ((STAIR_U0 - 4, 0, 2.0), GREEN, 22.0, 0.9),
           ((U, 0, S_Z - 30), WHITE, 90.0, 0.34)]            # the eye, from high up
    for side in (-1, 1):
        for u in (4.0, 16.0, 28.0, 40.0):
            out.append(((u, side * (W_BRIDGE - 1.5), 0.8), GREEN, 2.8, 0.55))
        out.append(((BEACON_U[0], side * (W_BRIDGE - 1.0), 0.9), (1.0, 0.14, 0.1), 3.2, 0.5))
        out.append(((BEACON_U[1], side * (W_BRIDGE - 1.0), 0.9), (1.0, 0.14, 0.1), 3.2, 0.6))
    return out


BEACON_U = (22.0, 44.0)


def _ground(kit):
    """The wet floor either side of the road, on past its end to the stair; the throat's floor; the kerbs and their signs;
    the stair and plinth; the piers."""
    bm = bmesh.new()
    step = 2.0
    for side in (-1, 1):
        a, b = sorted((side * 5.9, side * W_BRIDGE))
        _grid(bm, WALL_U + 12, 30.0, a, b, 0.0, step)
    # On past the road's deck, to the stair and under it.
    _grid(bm, 30.0, STAIR_U1 + 2, -W_BRIDGE, W_BRIDGE, 0.0, step)
    # The throat's floor, either side of the road, out to the flanks.
    v1 = R_CH * math.sin(math.radians(PORTAL_A))
    for side in (-1, 1):
        a, b = sorted((side * 5.9, side * v1))
        _grid(bm, MOUTH_U, WALL_U + 12, a, b, 0.0, 6.0)
    me = kit.mesh_from('CoreFloor', bm, [M['wet']], recalc=False)
    kit.planar_uvs(me, 0.05)
    kit.bake_light(me, _floor_lights(), ambient=(0.12, 0.16, 0.13))

    bm = bmesh.new()
    add = _kit.add_box
    # The kerbs: a wall each side from the wall's hole to the stair's foot, with the bridge's flank dropping into the pit.
    u0, u1 = WALL_U + 12, BEACON_U[1] + 1
    for side in (-1, 1):
        n = 22
        for i in range(n):
            ua, ub = u0 + (u1 - u0) * i / n, u0 + (u1 - u0) * (i + 1) / n
            add(bm, ((ua + ub) / 2, side * (W_BRIDGE + 0.5), 0.55), (ub - ua, 1.0, 1.1), 0)
        add(bm, ((u0 + u1) / 2, side * (W_BRIDGE + 0.55), (PIT_Z) / 2 - 0.1), (u1 - u0, 0.9, -PIT_Z), 0)
        # Piers under the bridge's edge.
        for u in np.arange(u0, u1, 22.0):
            add(bm, (u, side * (W_BRIDGE + 2.2), PIT_Z / 2), (3.0, 3.2, -PIT_Z), 0)
    # The plinth: its front wall either side of the stair, and its top.
    P = 50.0
    for side in (-1, 1):
        va, vb = STAIR_W + 1.6, P
        add(bm, (STAIR_U1 + 1.0, side * (va + vb) / 2, (STAIR_Z + PIT_Z) / 2), (2.0, vb - va, STAIR_Z - PIT_Z), 0)
    _grid(bm, STAIR_U1, U + 75, -P, P, STAIR_Z, 6.0, 0)
    # The plinth's sides, down to the pit.
    for side in (-1, 1):
        add(bm, ((STAIR_U1 + U + 75) / 2, side * P, (STAIR_Z + PIT_Z) / 2), (U + 75 - STAIR_U1, 1.0, STAIR_Z - PIT_Z), 0)
    # Joint lines on the plinth's front.
    for side in (-1, 1):
        for vv in np.arange(STAIR_W + 4, P, 9.0):
            add(bm, (STAIR_U1 - 0.1, side * vv, -8), (0.4, 0.8, 38), 0)
        add(bm, (STAIR_U1 - 0.2, side * (STAIR_W + P) / 2, 8.5), (0.4, P - STAIR_W, 0.5), 0)
    # The stair.
    n = int(round(STAIR_Z / 0.35))
    run = (STAIR_U1 - STAIR_U0) / n
    rise = STAIR_Z / n
    for k in range(n):
        ua = STAIR_U0 + k * run
        _quad(bm, (ua, -STAIR_W, k * rise), (ua, STAIR_W, k * rise), (ua, STAIR_W, (k + 1) * rise), (ua, -STAIR_W, (k + 1) * rise), 0, out=Vector((-1, 0, 0)))
        _quad(bm, (ua, -STAIR_W, (k + 1) * rise), (ua, STAIR_W, (k + 1) * rise), (ua + run, STAIR_W, (k + 1) * rise), (ua + run, -STAIR_W, (k + 1) * rise), 0, out=Vector((0, 0, 1)))
    # Its cheeks, rising with it.
    for side in (-1, 1):
        for vo, vi in ((STAIR_W + 1.6, STAIR_W),):
            a = (STAIR_U0 - 1.4, side * vo, 0.0)
            b = (STAIR_U1 + 0.2, side * vo, 0.0)
            c = (STAIR_U1 + 0.2, side * vo, STAIR_Z + 1.5)
            e = (STAIR_U0 - 1.4, side * vo, 1.3)
            _quad(bm, a, b, c, e, 0, out=Vector((0, side, 0)))
            a2, b2, c2, e2 = [(p[0], side * vi, p[2]) for p in (a, b, c, e)]
            _quad(bm, a2, b2, c2, e2, 0, out=Vector((0, -side, 0)))
            _quad(bm, e, c, c2, e2, 0, out=Vector((0, 0, 1)))
            _quad(bm, a, e, e2, a2, 0, out=Vector((-1, 0, 0)))
    # The piers either side at the top, and the smaller ones at the foot.
    for side in (-1, 1):
        for u, v, z0, z1, wd in ((STAIR_U1 + 0.5, 22.0, -2.0, STAIR_Z + 3.8, 3.6), (STAIR_U1 + 0.5, 38.0, -2.0, STAIR_Z + 2.8, 2.8), (STAIR_U0 - 2.0, STAIR_W + 1.0, 0.0, 2.6, 2.2)):
            add(bm, (u, side * v, (z0 + z1) / 2), (wd, wd, z1 - z0), 0)
            add(bm, (u, side * v, z1 + 0.2), (wd + 0.5, wd + 0.5, 0.4), 0)
    me2 = kit.mesh_from('CoreKerbs', bm, [kit.MAT['concrete']], recalc=False)
    kit.box_uvs(me2, 0.12)
    kit.bake_light(me2, _floor_lights() + [((STAIR_U1 - 2, 0, 12), WHITE, 22.0, 0.9), ((U - 4, 0, 18), WHITE, 34.0, 0.8)], ambient=(0.13, 0.17, 0.14))

    bm = bmesh.new()
    # The treads' green lights: a strip under each nosing in three runs, and the cheeks' tops.
    for k in range(0, n):
        ua = STAIR_U0 + k * run
        z = (k + 1) * rise
        for x0, x1 in ((-STAIR_W + 0.15, -STAIR_W + 1.0), (-0.45, 0.45), (STAIR_W - 1.0, STAIR_W - 0.15)):
            _quad(bm, (ua - 0.01, x0, z - 0.04), (ua - 0.01, x1, z - 0.04), (ua - 0.01, x1, z - 0.12), (ua - 0.01, x0, z - 0.12), 0, out=Vector((-1, 0, 0)))
    for side in (-1, 1):
        y0, y1 = side * (STAIR_W + 0.55), side * (STAIR_W + 1.05)
        ca, cb = Vector((STAIR_U0 - 1.2, 0, 1.34)), Vector((STAIR_U1, 0, STAIR_Z + 1.54))
        for k in range(9):
            t0, t1 = k / 9 + 0.01, (k + 0.45) / 9
            p, q = ca.lerp(cb, t0), ca.lerp(cb, t1)
            _quad(bm, (p.x, y0, p.z), (q.x, y0, q.z), (q.x, y1, q.z), (p.x, y1, p.z), 0, out=Vector((0, 0, 1)))
        # Kerb lamps along the bridge, low on its inner face.
        for u in (4.0, 16.0, 28.0, 40.0):
            _quad(bm, (u - 0.6, side * (W_BRIDGE - 0.01), 0.55), (u + 0.6, side * (W_BRIDGE - 0.01), 0.55), (u + 0.6, side * (W_BRIDGE - 0.01), 0.7), (u - 0.6, side * (W_BRIDGE - 0.01), 0.7), 0, out=Vector((0, -side, 0)))
    led = kit.mesh_from('CoreStairLed', bm, [M['dimled']], recalc=False)

    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    for side, us in ((1, (11.0,)), (-1, (24.0,)), (1, (30.0,))):
        for u in us:
            l, h = (1.6, 0.34) if u > 20 else (2.6, 0.56)
            a = (u - l / 2, side * (W_BRIDGE - 0.02), 0.2)
            b = (u + l / 2, side * (W_BRIDGE - 0.02), 0.2)
            c = (u + l / 2, side * (W_BRIDGE - 0.02), 0.2 + h)
            e = (u - l / 2, side * (W_BRIDGE - 0.02), 0.2 + h)
            f = bm.faces.new([bm.verts.new(p) for p in ((a, b, c, e) if side > 0 else (b, a, e, c))])
            for lp, uv in zip(f.loops, ((0, 0.1), (1, 0.1), (1, 0.9), (0, 0.9))):
                lp[uvl].uv = uv
    sign = kit.mesh_from('CoreSigns', bm, [M['sign']], recalc=False)
    return me, me2, led, sign


def _stem(kit):
    """The machinery under the sphere: stepped drums, struts, pipework, and the glowing door at the stair's head."""
    bm = bmesh.new()
    z0 = STAIR_Z
    top = S_Z - S_R
    _kit.lathe(bm, [(19, 0.0), (19, 1.0), (17.5, 1.6), (17, 4.2), (13.5, 4.8), (13, 8.0), (9.5, 8.8), (9, 13.8)], seg=40, cx=U, z0=z0, cap_top=False, cap_bottom=False)
    add = _kit.add_box
    for k in range(12):
        a = 2 * math.pi * k / 12
        p0 = Vector((U + 17.0 * math.cos(a), 17.0 * math.sin(a), z0 + 2.5))
        r1 = 13.5
        p1 = Vector((U + r1 * math.cos(a), r1 * math.sin(a), S_Z - math.sqrt(S_R ** 2 - r1 ** 2) + 0.5))
        _cable(bm, [p0, p0.lerp(p1, 0.5), p1], 0.62, sides=5)
        rot = Matrix.Rotation(a, 3, 'Z')
        add(bm, (U + 16.5 * math.cos(a), 16.5 * math.sin(a), z0 + 2.8), (4.2, 2.8, 2.6), 0, rot=rot)
        add(bm, (U + 12.4 * math.cos(a), 12.4 * math.sin(a), z0 + 6.2), (2.8, 2.2, 3), 0, rot=rot)
    # Pipework round the middle drum.
    for k in range(4):
        z = z0 + 8.8 + k * 1.1
        r = 9.9 + k * 0.05
        path = [Vector((U + r * math.cos(t), r * math.sin(t), z)) for t in np.linspace(0, 2 * math.pi, 21)]
        _cable(bm, path, 0.26, sides=5)
    # The door's frame and porch, at the stair's head.
    du = STAIR_U1 + 1.0
    for side in (-1, 1):
        add(bm, (du + 2.0, side * 4.6, z0 + 3), (4.5, 1.6, 6), 0)
    add(bm, (du + 2.0, 0, z0 + 6.5), (4.5, 10.8, 1.0), 0)
    add(bm, (du + 3.2, 0, z0 + 3), (0.3, 0.3, 6), 0)
    me = kit.mesh_from('CoreStem', bm, [M['metal']], recalc=False)
    kit.box_uvs(me, 0.07)
    kit.bake_light(me, [((du - 2, 0, z0 + 3), WHITE, 9.0, 1.8), ((U - 18, 0, z0 + 2), WHITE, 16.0, 0.9), ((U, 0, top - 3), GREEN, 13.0, 0.7)], ambient=(0.13, 0.17, 0.14))

    bm = bmesh.new()
    _quad(bm, (du + 3.6, -3.8, z0 + 0.1), (du + 3.6, 3.8, z0 + 0.1), (du + 3.6, 3.8, z0 + 6), (du + 3.6, -3.8, z0 + 6), 0, out=Vector((-1, 0, 0)))
    door = kit.mesh_from('CoreDoor', bm, [M['oculus']], recalc=False)
    return me, door


def _mist(kit):
    """Sheets of mist and the oculus's light, each turned to the arrival's eye, and the wet floor's painted reflections."""
    eye = Vector(_EYE)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    rng = np.random.default_rng(161)

    def card(c, w, h, mat, uvr=(0, 0, 1, 1)):
        c = Vector(c)
        to = c - eye
        r = Vector((-to.y, to.x, 0)).normalized()
        up = Vector((0, 0, 1))
        cs = [c - r * (w / 2) - up * (h / 2), c + r * (w / 2) - up * (h / 2), c + r * (w / 2) + up * (h / 2), c - r * (w / 2) + up * (h / 2)]
        f = bm.faces.new([bm.verts.new(p) for p in cs])
        f.material_index = mat
        for lp, uv in zip(f.loops, ((uvr[0], uvr[1]), (uvr[2], uvr[1]), (uvr[2], uvr[3]), (uvr[0], uvr[3]))):
            lp[uvl].uv = uv
        _flip_out([f], -to)

    BILLOW, WISP = (0, 0, 0.5, 1), (0.5, 0, 1, 1)
    for side in (-1, 1):
        # Low over the pit in front of the plinth, under its balustrade.
        for k in range(8):
            card((rng.uniform(46, 66), side * rng.uniform(17, 46), rng.uniform(-1, 2)), rng.uniform(24, 40), rng.uniform(5, 8), 0, BILLOW)
        for k in range(10):
            card((rng.uniform(4, 46), side * rng.uniform(19, 50), rng.uniform(0, 5)), rng.uniform(22, 38), rng.uniform(8, 13), 0, BILLOW)
        # Higher to either side, hiding the towers' feet.
        for k in range(9):
            card((rng.uniform(16, 100), side * rng.uniform(48, 104), rng.uniform(3, 9)), rng.uniform(30, 56), rng.uniform(13, 22), 0, BILLOW)
        # Behind the balustrade.
        for k in range(5):
            card((rng.uniform(76, 108), side * rng.uniform(14, 44), rng.uniform(13, 18)), rng.uniform(24, 40), rng.uniform(6, 10), 0, BILLOW)
        # Wisps climbing round the towers.
        for u, v, z, w, h in ((36, 44, 20, 14, 38), (24, 76, 30, 18, 52), (66, 80, 26, 16, 44), (84, 54, 22, 13, 28), (54, 96, 44, 20, 58)):
            card((u, side * v, z), w, h, 0, WISP)
    # The light down from the oculus.
    card((U, 0, WELL_LIP - 20), 38, 50, 1)
    card((U + 12, 4, WELL_LIP - 14), 24, 46, 1)
    # A green halo round the door at the stair's head.
    card((STAIR_U1 + 2.5, 0, STAIR_Z + 3), 22, 14, 2, (0, 1, 1, 0))
    # A haze at the plinth, behind the stair's head.
    card((U - 10, 0, STAIR_Z + 7), 38, 11, 0, BILLOW)
    me = kit.mesh_from('CoreMist', bm, [M['smoke'], M['shaft'], M['wash']], recalc=False)

    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')

    def streak(u, v, ln, wd, mat):
        """A reflection on the floor from (u, v) back toward the eye."""
        base = Vector((u, v, 0.04))
        to = (Vector((eye.x, eye.y, 0.04)) - base)
        to.normalize()
        s = Vector((-to.y, to.x, 0))
        cs = [base + to * ln - s * (wd / 2), base + to * ln + s * (wd / 2), base + s * (wd / 2), base - s * (wd / 2)]
        f = bm.faces.new([bm.verts.new(p) for p in cs])
        f.material_index = mat
        for lp, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            lp[uvl].uv = uv
        _flip_out([f], Vector((0, 0, 1)))

    for side in (-1, 1):
        y = side * (W_BRIDGE - 0.4)
        for u in (16.0, 28.0, 40.0):
            # (Each stops short of the road: |d| < 5.9 is the deck's. The streak runs toward the eye, so that's a share of its way there.)
            streak(u, y, (u - eye.x) * 0.44, 0.9, 0)
        su = 11.0 if side > 0 else 24.0
        streak(su, y, (su - eye.x) * 0.4, 2.8, 0)
        streak(BEACON_U[0], y, (BEACON_U[0] - eye.x) * 0.44, 0.7, 1)
        streak(BEACON_U[1], y, (BEACON_U[1] - eye.x) * 0.44, 0.9, 1)
    # The stair's wash on the wet floor, past the road's end.
    streak(STAIR_U0 - 0.5, 0.0, 18.0, 19.0, 2)
    gleam = kit.mesh_from('CoreGleam', bm, [M['gleam'], M['redgleam'], M['wash']], recalc=False)
    return me, gleam


def build(kit):
    _materials(kit)
    # (Pieces reuse MAT's materials, which read the 'AO' colours; all of them are baked.)
    p = {
        'bay0': kit.piece('CoreBay0', _bay(kit, 1.0, 201)),
        'bay1': kit.piece('CoreBay1', _bay(kit, 1.0, 202)),
        'bay2': kit.piece('CoreBay2', _bay(kit, 0.6, 203)),
        'tall': kit.piece('CoreTowerTall', _tower(kit, 92.0, 211)),
        'mid': kit.piece('CoreTowerMid', _tower(kit, 60.0, 212)),
        'rail': kit.piece('CoreRail', _rail(kit)),
        'beacon': kit.piece('CoreBeacon', _beacon(kit)),
        'worklight': kit.piece('CoreWorkLight', _worklight(kit)),
    }
    return p


def place(kit, pieces):
    e = tuple(_END)
    g = 'Core'
    for name, me in (('CoreHull', _hull(kit)), ('CoreArmour', _armour(kit)), ('CoreEye', _eye(kit)), ('CoreCables', _cables(kit)),
                     ('CoreShell', _shell(kit)), ('CoreOculus', _oculus(kit)), ('CoreThroat', _throat(kit))):
        kit.static(name, me, grp=g, loc=e)
    for me in _ground(kit):
        kit.static(me.name, me, grp=g, loc=e)
    for me in _stem(kit):
        kit.static(me.name, me, grp=g, loc=e)
    for me in _mist(kit):
        kit.static(me.name, me, grp=g, loc=e)
    # The pulsing parts, their origin at the sphere's centre.
    kit.static('CoreHeart', _heart(kit), grp=g, loc=_w(*C))

    # Balcony bays round the wall, leaving out the arc behind the road's end (only ever at the rider's back).
    for ti, z in enumerate(TIERS):
        for k in range(24):
            a = k * 15.0 + 7.5
            a = a if a <= 180 else a - 360
            if abs(a) > 118 or (abs(a) > 180 - PORTAL_A and z < PORTAL_Z):
                continue
            ar = math.radians(a)
            p = pieces['bay2'] if z > 100 else pieces['bay0'] if (k + ti) % 2 else pieces['bay1']
            kit.put(p, _w(U + R_CH * math.cos(ar), R_CH * math.sin(ar), z), yaw=ar + math.pi / 2, grp=g)
    # A few work lights.
    for a, z in ((62.0, 40.0), (-44.0, 40.0), (40.0, 72.0), (-66.0, 72.0), (-30.0, 104.0), (26.0, 8.0), (-22.0, 8.0), (72.0, 104.0)):
        ar = math.radians(a)
        rr = R_CH - 5.0
        kit.put(pieces['worklight'], _w(U + rr * math.cos(ar), rr * math.sin(ar), z + 29.0), yaw=ar + math.pi / 2, grp=g)
    # Towers of racks standing out of the pit (the big pairs framing the shot).
    for u, v, name, z in ((41.6, 64.6, 'tall', -44.5), (66.6, 69.0, 'mid', -27.0), (81.6, 67.0, 'mid', -25.0),
                          (112.0, 72.0, 'mid', -12.0), (0.0, 84.0, 'tall', -40.0)):
        for side in (-1, 1):
            kit.put(pieces[name], _w(u, side * v, z), yaw=math.radians(4.0 * side), grp=g)
    # The bridge's railings, and along the plinth either side of the stair.
    for side in (-1, 1):
        y = side * (W_BRIDGE + 0.5)
        for u in np.arange(WALL_U + 12, BEACON_U[1], 4.0):
            kit.put(pieces['rail'], _w(float(u), y, 1.1), grp=g)
        for v in np.arange(STAIR_W + 1.6, 47.0, 4.0):
            yaw = math.pi / 2 if side > 0 else -math.pi / 2
            kit.put(pieces['rail'], _w(STAIR_U1 - 0.4, side * float(v), STAIR_Z), yaw=yaw, grp=g)
        for u in BEACON_U:
            kit.put(pieces['beacon'], _w(u, side * (W_BRIDGE + 0.5), 1.1), grp=g)
        kit.put(pieces['beacon'], _w(STAIR_U1 + 0.5, side * 22.0, STAIR_Z + 4.0), grp=g, scale=1.6)
        kit.put(pieces['beacon'], _w(STAIR_U1 + 0.5, side * 38.0, STAIR_Z + 3.0), grp=g, scale=1.3)
        kit.put(pieces['beacon'], _w(STAIR_U0 - 2.0, side * (STAIR_W + 1.0), 2.8), grp=g)

    if _PREVIEW:
        _preview_props(kit)
    total = sum(kit.tris(o.data) for o in bpy.context.scene.objects if o.type == 'MESH' and not o.name.startswith('City5.Preview'))
    print('CORE TRIS', total)
    by = {}
    for o in bpy.context.scene.objects:
        if o.type == 'MESH':
            by[o.data.name] = by.get(o.data.name, 0) + kit.tris(o.data)
    print('CORE BY', sorted(by.items(), key=lambda kv: -kv[1]))


def _preview_props(kit):
    """For previews only: the road's deck (art/build-city5.py builds the real one) and a box where the bike parks."""
    bm = bmesh.new()
    _grid(bm, MOUTH_U - 40, 30.0, -5.9, 5.9, 0.0, 4.0)
    me = kit.mesh_from('PreviewDeck', bm, [M['wet']], recalc=False)
    kit.planar_uvs(me, 0.05)
    kit.bake_light(me, _floor_lights(), ambient=(0.12, 0.16, 0.13))
    kit.static('PreviewDeck', me, loc=tuple(_END))
    body = kit.material('PreviewBike', (0.2, 0.22, 0.2), 0.5, vcol=False)
    bm = bmesh.new()
    kit.add_box(bm, (0, 0, 0.65), (2.2, 0.7, 1.3))
    me = kit.mesh_from('PreviewBike', bm, [body])
    o = kit.static('PreviewBike', me, loc=_w(0.0, BIKE['d'], 0.0))
    o.rotation_euler = (0, 0, math.radians(BIKE['yaw_deg']))
