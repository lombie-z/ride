"""The fourth zone (art/reference/concept-desert.webp, -transition-desert.webp): the data desert at harsh noon. A cracked
asphalt highway, sand drifting over it, runs between low concrete barriers with green-lit panels, through fields of
colossal rusted server monoliths and their fans half-buried in amber dunes, cables snaking through the sand like roots
and cracked CRT terminals lying in it, under a toppled server tower and two gantries, to a fortified concrete research
facility (a bunker gate with its lamps, lattice masts and antenna clusters, a radar dish, watchtowers, stepped and
buttressed bunker walls with lit slits, an original insignia: a hexagon on its point round a vertical double helix, and
a stencilled serial plate) in front of a huge rolling sandstorm wall (umber billow bands and soft puff cards whose ends
dissolve into the haze) with lightning, a hot white sun high on the left.
Builds art/city4.blend from scratch and exports public/models/city4.glb (Draco).
Run: /opt/homebrew/bin/blender --background --factory-startup --python art/build-city4.py
     CITY4_ROUND=r1 names the renders (default r0); CITY4_NO_EEVEE=1 skips the EEVEE renders; CITY4_PLAN=0 the plan.

City4's own frame (Blender z up, metres): the road comes in along +X at City4.RoadIn (the local origin, where the
previous zone's road hands over; its deck top is z 0, 11.8 m wide). x < 0 is the previous zone's and stays empty; so
does the left (y > 0) of the first ~420 m, where zone 3's coral city stands. From there the road runs long straights and
gentle sweeps (radius 700-900 m: left, right, left, all told back to heading +X) through the server fields, under a
gantry, the toppled tower and a second gantry, onto a final ~1.1 km straight at the facility, ~2.75 km in all.
City4.RoadPath carries the bike's line as data ([x, y] every 2 m, RoadIn -> BikeMark, and its length): the road's
centreline until the last 60 m, where it eases into the right lane and turns the bike in to park, nose 23.7 deg left of
the road (as the arrival fit has it). City4.RoadOut continues it 200 m: back onto the centreline and straight in
through the facility's gate (END, END_HEADING). City4.BikeMark: the bike, its front along the empty's local +X.

The arrival shot is fitted to the concept by art/align4/: extract_concept.py traces the concept's guides
(concept-features.json: horizon, road lines, skyline, sun, storm edge, monolith and CRT boxes, the facility, its gate,
the bike), fit_camera.py fits EYE/LOOK/FOV and the bike's spot on the deck to the road's centre line, the horizon and the
bike (arrival-camera.json), this script carries that into City4's frame and composes the near monoliths, CRTs, the
facility, the storm's edge, lightning and sun in the arrival camera's screen space (screen_point) from those guides, and
score.py scores the render against them. City4.ApproachCam is the rider's view ~120 m in (concept-transition-desert:
the road straight ahead, the storm and facility far ahead, servers in the dunes on the right, zone 3 on the left).
Everything behind the arrival camera is tagged approach_only (it can't show in the arrival frame; a ray sweep checks).

Materials are plain Principled BSDFs named City4*, with a few small generated textures (asphalt with cracks and the
centre dashes, sand ripples, rust and concrete grunge, the terminal text, the storm's billows; all <= 512 px, made here
with numpy, packed) and ambient occlusion baked into each mesh's vertex colours ('AO': self-occlusion ray casts for the
modules and the facility, slope, hollows and contact shadows for the dunes). Repeated pieces (monoliths, fans, cables,
barriers, CRTs, masts) are linked duplicates, exported as GPU instances.

Renders (art/renders/): city4-arrival-<round>.png (EEVEE, with the site's bike at BikeMark), city4-arrival-ids-<round>.png
(flat object-ID colours for score.py), city4-approach-<round>.png, city4-plan.png; art/align4/out/<round>-overlay.png,
-compare.png (score.py) and approach-<round>-compare.png (approach_check.py).
"""
import json
import math
import os
import random
import subprocess

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, kdtree
from mathutils.bvhtree import BVHTree

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ALIGN = os.path.join(ROOT_DIR, 'art', 'align4')
BLEND = os.path.join(ROOT_DIR, 'art', 'city4.blend')
GLB = os.path.join(ROOT_DIR, 'public', 'models', 'city4.glb')
RENDERS = os.path.join(ROOT_DIR, 'art', 'renders')
BIKE_GLB = os.path.join(ROOT_DIR, 'public', 'models', 'bike.glb')
ROUND = os.environ.get('CITY4_ROUND', 'r0')
FEAT = json.load(open(os.path.join(ALIGN, 'concept-features.json')))
CAMFIT = json.load(open(os.path.join(ALIGN, 'arrival-camera.json')))
RES = (1280, 720)
rnd = random.Random(11)
nrng = np.random.default_rng(11)

# --- Layout ------------------------------------------------------------------------------------------------------------
ROAD_W = 11.8              # the site's deck width
BARRIER_Y = 6.3            # the barriers' inner top edge off the centreline (art/align4/common.py)
BARRIER_TOP = 0.7          # their height over the deck
FINAL_STRAIGHT = 1080.0    # the last straight, onto the bike
ROAD_SEQ = [  # ('S', length) | ('A', radius, degrees, + = left)
    ('S', 520.0),            # the first stretch: zone 3's city on the left, dunes and servers on the right
    ('A', 900.0, 10.0),      # a long left sweep
    ('S', 300.0),            # the first gantry
    ('A', 700.0, -22.0),     # right, round between the server fields
    ('S', 260.0),            # under the toppled tower
    ('A', 800.0, 12.0),      # left, back to heading +X
    ('S', FINAL_STRAIGHT),   # the second gantry, then the facility dead ahead
]
PARK_LEN = 60.0            # the bike line's last stretch: into the right lane and turned in to park
GATE_X = 170.0             # the facility's gate, metres past the arrival camera (art/align4 road frame)
ROADOUT_LEN = 200.0

# The arrival fit (art/align4/arrival-camera.json): the camera and the bike in the road frame (centreline +X, camera
# foot at x 0), and the camera in the bike's frame.
RF = CAMFIT['road']
BIKE_RX, BIKE_RY = RF['bike_xy']
BIKE_YAW = RF['bike_yaw_deg']
FOV = CAMFIT['FOV']


def frange(a, b, s):
    out, x = [], a
    while x <= b + 1e-6:
        out.append(x)
        x += s
    return out


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# =========================================================================================================================
# The road.
# =========================================================================================================================
def trace(seq, step, x=0.0, y=0.0, h=0.0):
    """Dense points along a straights-and-arcs sequence (from (x, y) heading h), ~`step` m apart."""
    pts = [Vector((x, y, 0))]
    for sg in seq:
        if sg[0] == 'S':
            n = max(1, round(sg[1] / step))
            for i in range(1, n + 1):
                pts.append(Vector((x + math.cos(h) * sg[1] * i / n, y + math.sin(h) * sg[1] * i / n, 0)))
        else:
            R, d = sg[1], math.radians(sg[2])
            side = 1 if d > 0 else -1
            cx, cy = x - side * R * math.sin(h), y + side * R * math.cos(h)
            a0 = h - side * math.pi / 2
            n = max(2, round(abs(d) * R / step))
            for i in range(1, n + 1):
                a = a0 + d * i / n
                pts.append(Vector((cx + R * math.cos(a), cy + R * math.sin(a), 0)))
            h += d
        x, y = pts[-1].x, pts[-1].y
    return pts, h


def resample_exact(pts, step):
    """Points every `step` m of arc length along a polyline, plus its exact end."""
    out, acc = [pts[0]], 0.0
    for a, b in zip(pts, pts[1:]):
        seg = (b - a).length
        t0 = 0.0
        while acc + (seg - t0) >= step - 1e-9:
            t0 += step - acc
            out.append(a.lerp(b, t0 / seg))
            acc = 0.0
        acc += seg - t0
    if (out[-1] - pts[-1]).length > 1e-3:
        out.append(pts[-1])
    return out


def poly_len(pts):
    return sum((b - a).length for a, b in zip(pts, pts[1:]))


def hermite(p0, h0, p1, h1, m0, m1, n):
    """A cubic Hermite from p0 heading h0 to p1 heading h1 (tangent lengths m0, m1), n + 1 points."""
    t0 = Vector((math.cos(h0), math.sin(h0), 0)) * m0
    t1 = Vector((math.cos(h1), math.sin(h1), 0)) * m1
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t, -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        out.append(p0 * a + t0 * b + p1 * c + t1 * d)
    return out


_centre, _hend = trace(ROAD_SEQ, 0.5)
assert abs(_hend) < 1e-9, _hend
P_END = _centre[-1].copy()                         # the final straight ends level with the bike
Y_F = P_END.y                                      # the final straight's y
X_BIKE = P_END.x
X_CAM = X_BIKE - BIKE_RX                           # the arrival camera's road-frame origin (its foot)
BIKE_AT = Vector((X_BIKE, Y_F + BIKE_RY, 0.0))


def road_to_city(x, y, z=0.0):
    return Vector((X_CAM + x, Y_F + y, z))


# The bike line: the centreline to PARK_LEN short of the bike, then eased into the lane and turned in.
_park0 = Vector((X_BIKE - PARK_LEN, Y_F, 0))
_bike_line = [p for p in _centre if p.x < _park0.x - 0.1 or abs(p.y - Y_F) > 1e-6]
_bike_line.append(_park0)
_bike_line += hermite(_park0, 0.0, BIKE_AT, math.radians(BIKE_YAW), 40.0, 22.0, 120)[1:]
ROAD_LINE = resample_exact(_bike_line, 2.0)        # City4.RoadPath, RoadIn -> BikeMark, every 2 m
ROAD_LEN = poly_len(_bike_line)
# Where the facility's gate stands (its opening's centre column, concept-features.json, at the view depth the facility
# is composed at below): a little right of the road's line, as in the concept, where the far road bends right to it.
# Past the arrival camera the deck eases over (an S over 130 m, radius > 400 m) to run straight in through it.
def _gate_y():
    eye, look = road_to_city(*RF['EYE']), road_to_city(*RF['LOOK'])
    f = (look - eye).normalized()
    r = f.cross(Vector((0, 0, 1))).normalized()
    th = math.tan(math.radians(FOV / 2)) * 1280 / 720
    g = FEAT['boxes']['gate']
    nx = ((g[0] + g[2]) / 2 - 640) / 640
    return (eye + 172.0 * (f + r * nx * th)).y


GATE_DY = _gate_y() - Y_F


def deck_offset(xr):
    """The deck centreline's offset (+ left) at road-frame x past the arrival camera."""
    return GATE_DY * float(smoothstep(20.0, 150.0, xr))


DECK_END_X = X_CAM + GATE_X + 36.0
_tail = [Vector((x, Y_F + deck_offset(x - X_CAM), 0)) for x in frange(X_BIKE + 2.0, DECK_END_X, 2.0)]
DECK_LINE = resample_exact(_centre + _tail, 4.0)
# RoadOut: from the bike, back onto the deck's centreline (70 m on), along it through the gate, on into the tunnel.
_q0 = Vector((X_CAM + 70.0, Y_F + deck_offset(70.0), 0))
_qh = math.atan2(deck_offset(71.0) - deck_offset(69.0), 2.0)
_out = hermite(BIKE_AT, math.radians(BIKE_YAW), _q0, _qh, 22.0, 30.0, 100)
_out += [Vector((x, Y_F + deck_offset(x - X_CAM), 0)) for x in frange(_q0.x + 2.0, _q0.x + 400.0, 2.0)]
_cum, _cut = 0.0, len(_out)
for i in range(1, len(_out)):
    _cum += (_out[i] - _out[i - 1]).length
    if _cum >= ROADOUT_LEN:
        _cut = i + 1
        seg = (_out[i] - _out[i - 1]).length
        _out[i] = _out[i - 1].lerp(_out[i], (seg - (_cum - ROADOUT_LEN)) / seg)  # exactly ROADOUT_LEN
        break
_out = _out[:_cut]
OUT_LINE = resample_exact(_out, 2.0)
OUT_LEN = poly_len(_out)
print('road', round(ROAD_LEN, 1), 'm,', len(ROAD_LINE), 'path points; out', round(OUT_LEN, 1), 'm; bike', BIKE_AT,
      'camera foot', road_to_city(0, 0))

# Arc length lookup along the deck centreline (for placing things "s metres along, d metres left").
_DL = DECK_LINE
_DS = [0.0]
for a, b in zip(_DL, _DL[1:]):
    _DS.append(_DS[-1] + (b - a).length)
KD_ROAD = kdtree.KDTree(len(_DL))
for i, p in enumerate(_DL):
    KD_ROAD.insert(p, i)
KD_ROAD.balance()


def road_frame(s):
    """Point, tangent and left normal s metres along the deck's centreline."""
    i = max(0, min(int(np.searchsorted(_DS, s)) - 1, len(_DL) - 2))
    t = (s - _DS[i]) / max(_DS[i + 1] - _DS[i], 1e-9)
    p = _DL[i].lerp(_DL[i + 1], min(max(t, 0.0), 1.0))
    tan = (_DL[i + 1] - _DL[i]).normalized()
    return p, tan, Vector((-tan.y, tan.x, 0))


def along(s, d, z=0.0):
    p, t, n = road_frame(s)
    return Vector((p.x + n.x * d, p.y + n.y * d, z))


def road_coords(x, y):
    """(s along the deck, signed distance left of its centreline) of a point."""
    co, i, dist = KD_ROAD.find(Vector((x, y, 0)))
    j = min(i, len(_DL) - 2)
    tan = (_DL[j + 1] - _DL[j]).normalized()
    v = Vector((x, y, 0)) - _DL[i]
    lat = tan.x * v.y - tan.y * v.x
    return _DS[i] + tan.dot(v), lat


S_CAM = road_coords(X_CAM, Y_F)[0]
print('arrival camera at s', round(S_CAM, 1))

# --- The arrival camera, in City4's frame ---------------------------------------------------------------------------------
EYE = road_to_city(*RF['EYE'])
LOOK = road_to_city(*RF['LOOK'])
FWD = (LOOK - EYE).normalized()
RIGHT = FWD.cross(Vector((0, 0, 1))).normalized()
UP = RIGHT.cross(FWD)
TAN_V = math.tan(math.radians(FOV / 2))
TAN_H = TAN_V * RES[0] / RES[1]
FPX = RES[1] / 2 / TAN_V
BIKE_M = Matrix.Translation(BIKE_AT) @ Matrix.Rotation(math.radians(BIKE_YAW), 4, 'Z')

# The approach: a chase view ~120 m in (concept-transition-desert: behind and above the rider, looking a touch right of
# the road, so the road runs off to the left of centre and the hero server stands close on the right).
APP_EYE = Vector((120.0, -0.5, 2.4))
APP_LOOK = APP_EYE + Vector((100.0, -20.3, -2.0))
APP_FOV = 52.0


def screen_point(sx, sy, depth):
    """The point at pixel (sx, sy) of the 1280x720 arrival frame, `depth` metres along the view axis."""
    nx = (sx - RES[0] / 2) / (RES[0] / 2)
    ny = (RES[1] / 2 - sy) / (RES[1] / 2)
    return EYE + depth * (FWD + RIGHT * nx * TAN_H + UP * ny * TAN_V)


def to_screen(p):
    v = p - EYE
    d = v.dot(FWD)
    return Vector((RES[0] / 2 * (1 + v.dot(RIGHT) / (d * TAN_H)), RES[1] / 2 * (1 - v.dot(UP) / (d * TAN_V)))), d


def px_to_m(px, depth):
    return px * depth / FPX


def px_to_m_inv(m, depth):
    """Metres at view depth `depth` in pixels."""
    return m * FPX / depth


def ground_at_depth(sx, depth):
    """Where screen column sx is, `depth` metres along the view axis (the horizontal position, z 0)."""
    p = screen_point(sx, RES[1] / 2, depth)
    return Vector((p.x, p.y, 0.0))


def row_of_z(sx, depth, z):
    """The screen row of height z at screen column sx and view depth `depth`."""
    p = ground_at_depth(sx, depth)
    p.z = z
    return to_screen(p)[0].y


def z_of_row(sx, sy, depth):
    return screen_point(sx, sy, depth).z


def face_yaw(dirn):
    """Yaw (radians about z) that turns a module's front (its local -Y) to face along dirn."""
    return math.atan2(dirn.x, -dirn.y)


def yaw_to_eye(p):
    v = EYE - p
    v.z = 0
    return face_yaw(v.normalized())


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
root = bpy.data.objects.new('City4', None)
scene.collection.objects.link(root)


# =========================================================================================================================
# Textures: small, generated here with numpy, packed into the .blend (and the glb).
# =========================================================================================================================
def vnoise(n, cells, seed, octaves=1, gain=0.5):
    """Tileable fractal value noise, n x n, in 0..1."""
    rng = np.random.default_rng(seed)
    out = np.zeros((n, n))
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        c = cells * 2 ** o
        g = rng.random((c, c))
        t = np.arange(n) * c / n
        i0 = np.floor(t).astype(int)
        f = t - i0
        f = f * f * (3 - 2 * f)
        i1 = (i0 + 1) % c
        a = g[np.ix_(i0, i0)] * (1 - f)[None, :] + g[np.ix_(i0, i1)] * f[None, :]
        b = g[np.ix_(i1, i0)] * (1 - f)[None, :] + g[np.ix_(i1, i1)] * f[None, :]
        out += amp * (a * (1 - f)[:, None] + b * f[:, None])
        tot += amp
        amp *= gain
    return out / tot


def draw_line(img, p0, p1, val, w=1):
    """Draw a line (rows, cols) into a 2-D array, wrapping (tileable)."""
    (y0, x0), (y1, x1) = p0, p1
    n = int(max(abs(x1 - x0), abs(y1 - y0)) * 1.5) + 1
    h, wd = img.shape[:2]
    for t in np.linspace(0, 1, n):
        y, x = y0 + (y1 - y0) * t, x0 + (x1 - x0) * t
        for dy in range(-(w // 2), w - w // 2):
            for dx in range(-(w // 2), w - w // 2):
                img[int(y + dy) % h, int(x + dx) % wd] = val


def crack_walk(img, rng, start, steps, step_len, val, w=1, wander=0.5):
    y, x = start
    a = rng.uniform(0, 2 * math.pi)
    for _ in range(steps):
        a += rng.normal(0, wander)
        ny, nx = y + math.sin(a) * step_len, x + math.cos(a) * step_len
        draw_line(img, (y, x), (ny, nx), val, w)
        y, x = ny, nx
        if rng.random() < 0.08:
            crack_walk(img, rng, (y, x), steps // 3, step_len * 0.8, val, 1, wander)


def make_image(name, rgba, jpeg=True):
    h, w = rgba.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=not jpeg)
    px = np.ones((h, w, 4), np.float32)
    px[..., :rgba.shape[2]] = rgba
    img.pixels.foreach_set(px[::-1].ravel())  # Blender's rows run bottom up
    img.file_format = 'JPEG' if jpeg else 'PNG'
    img.filepath_raw = f'//tex/{name}.{"jpg" if jpeg else "png"}'
    img.pack()
    return img


def tex_asphalt():
    """512 x 512 over 12 m across (u, columns) by 27 m along (v, rows): grainy dark asphalt, patches, cracks, sand dust,
    worn centre dashes (3 m on, 6 m off)."""
    n = 512
    rng = np.random.default_rng(3)
    g = 0.55 + 0.45 * vnoise(n, 8, 1, 4)
    grain = rng.random((n, n)) * 0.25 + 0.75
    base = (g * grain)[..., None] * np.array([0.25, 0.215, 0.19])
    patch = vnoise(n, 4, 2, 3)
    base *= (0.8 + 0.4 * smoothstep(0.45, 0.7, patch))[..., None]
    cracks = np.zeros((n, n))
    for _ in range(26):
        crack_walk(cracks, rng, (rng.uniform(0, n), rng.uniform(0, n)), 46, 5.0, 1.0, 3, 0.45)
    base *= (1 - 0.88 * cracks)[..., None]
    # The centre dashes (u 0.5, 0.15 m wide = 6.4 px), worn.
    paint = np.zeros((n, n))
    c0 = n // 2
    for k in range(3):
        r0 = int(k * n / 3)
        paint[r0:r0 + int(n * 3 / 27), c0 - 3:c0 + 4] = 1.0
    paint *= (vnoise(n, 32, 5, 2) > 0.38) * (1 - cracks)
    base = base * (1 - paint[..., None]) + paint[..., None] * np.array([0.62, 0.56, 0.46]) * grain[..., None]
    # Sand dust blown over it, heavier toward the edges (u near 0 and 1).
    edge = smoothstep(0.32, 0.5, np.abs(np.arange(n) / n - 0.5))[None, :]
    dust = smoothstep(0.4, 0.7, vnoise(n, 6, 7, 4)) * 0.8 + edge * 0.8 * vnoise(n, 10, 8, 3)
    dust = np.clip(dust, 0, 1)[..., None]
    return base * (1 - dust) + dust * np.array([0.62, 0.42, 0.24]) * grain[..., None]


def tex_sand():
    """256 x 256, ~8 m tile: wind ripples, warm amber."""
    n = 256
    yy, xx = np.mgrid[0:n, 0:n] / n
    warp = vnoise(n, 4, 21, 3)
    rip = 0.5 + 0.5 * np.sin(2 * math.pi * (yy * 24 + xx * 3 + warp * 3.0))
    rip = rip ** 2.5
    v = 0.82 + 0.12 * vnoise(n, 8, 22, 3) + 0.10 * rip
    grain = np.random.default_rng(4).random((n, n)) * 0.08 + 0.96
    return (v * grain)[..., None] * np.array([0.78, 0.50, 0.27])


def tex_rust():
    """256 x 256: dark rusted metal, streaks running down (rows), pitting."""
    n = 256
    rng = np.random.default_rng(31)
    a = vnoise(n, 6, 32, 5)
    cols = rng.random(n)
    streak = np.tile(cols[None, :], (n, 1))
    streak = np.convolve(streak[0], np.ones(5) / 5, mode='same')[None, :] * np.ones((n, 1))
    streak *= 0.6 + 0.4 * vnoise(n, 4, 35, 2)
    rust = smoothstep(0.35, 0.75, a * 0.6 + streak * 0.5)
    dark = np.array([0.15, 0.125, 0.105])
    orange = np.array([0.46, 0.22, 0.09])
    c = dark * (1 - rust[..., None]) + orange * rust[..., None]
    pits = (rng.random((n, n)) > 0.985)
    c[pits] *= 0.5
    return c * (0.85 + 0.3 * vnoise(n, 16, 36, 2))[..., None]


def tex_concrete():
    """256 x 256: weathered concrete, stains and water marks running down."""
    n = 256
    a = vnoise(n, 5, 41, 5)
    b = vnoise(n, 24, 42, 2)
    streak = np.tile(np.random.default_rng(43).random(n)[None, :], (n, 1))
    streak = np.array([np.convolve(r, np.ones(7) / 7, mode='same') for r in streak])
    v = 0.78 + 0.18 * a + 0.06 * b - 0.18 * smoothstep(0.55, 0.9, streak) * vnoise(n, 3, 44, 2)
    return v[..., None] * np.array([0.66, 0.56, 0.45])


# A 5 x 7 bitmap font for the terminals' text (only what they say).
FONT = {
    'A': '01110100011000111111100011000110001', 'B': '11110100011000111110100011000111110',
    'C': '01110100011000010000100001000101110', 'D': '11110100011000110001100011000111110',
    'E': '11111100001000011110100001000011111', 'F': '11111100001000011110100001000010000',
    'G': '01110100011000010111100011000101111', 'H': '10001100011000111111100011000110001',
    'I': '01110001000010000100001000010001110', 'K': '10001100101010011000101001001010001',
    'L': '10000100001000010000100001000011111', 'M': '10001110111010110101100011000110001',
    'N': '10001110011010110011100011000110001', 'O': '01110100011000110001100011000101110',
    'P': '11110100011000111110100001000010000', 'R': '11110100011000111110101001001010001',
    'S': '01111100001000001110000010000111110', 'T': '11111001000010000100001000010000100',
    'U': '10001100011000110001100011000101110', 'V': '10001100011000110001100010101000100',
    'W': '10001100011000110101101011101110001', 'X': '10001100010101000100010101000110001',
    'Y': '10001100010101000100001000010000100', 'Q': '01110100011000110001101011001001101',
    '0': '01110100011001110101110011000101110', '1': '00100011000010000100001000010001110',
    '2': '01110100010000100010001000100011111', '3': '11110000010000101110000010000111110',
    '4': '00010001100101010010111110001000010', '5': '11111100001111000001000011000101110',
    '6': '00110010001000011110100011000101110', '7': '11111000010001000100010000100001000',
    '8': '01110100011000101110100011000101110', '9': '01110100011000101111000010001001100',
    '>': '10000010000010000010001000100010000', '.': '00000000000000000000000000110001100',
    ':': '00000011000110000000011000110000000', '_': '00000000000000000000000000000011111',
    '-': '00000000000000011111000000000000000', '[': '01110010000100001000010000100001110',
    ']': '01110000100001000010000100001001110', '/': '00001000010001000100010001000010000',
    '%': '11001110010001000100010001001110011', ' ': '0' * 35,
}
TERMINAL = ['> BOOT SEQ 4F2', '> NODE 12 OFFLINE', '> CORE TEMP: 71.3', '> SECTOR DATA [LOST]', '> UPLINK.... FAILED',
            '> MEM 0% / 0%', '> AWAIT INPUT_']


def tex_screen():
    """512 x 256: green terminal text on a dark CRT, scan lines, vignette, a crack."""
    w, h = 512, 256
    img = np.zeros((h, w))
    s = 3  # px per font pixel
    for li, line in enumerate(TERMINAL):
        y0 = 14 + li * 33
        for ci, ch in enumerate(line):
            glyph = FONT.get(ch, FONT[' '])
            x0 = 18 + ci * 6 * s
            for k, bit in enumerate(glyph):
                if bit == '1':
                    r, c = divmod(k, 5)
                    img[y0 + r * s:y0 + r * s + s, x0 + c * s:x0 + c * s + s] = 1.0
    glow = img.copy()
    for _ in range(3):
        glow = (glow + np.roll(glow, 1, 0) + np.roll(glow, -1, 0) + np.roll(glow, 1, 1) + np.roll(glow, -1, 1)) / 5
    v = np.clip(img * 0.9 + glow * 0.8, 0, 1)
    scan = 0.75 + 0.25 * (np.arange(h) % 3 != 0)[:, None]
    yy, xx = np.mgrid[0:h, 0:w]
    vig = 1 - 0.55 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) ** 1.5
    bg = 0.10 + 0.06 * vnoise(256, 6, 51, 2)[np.ix_(np.arange(h) % 256, np.arange(w) % 256)]
    lum = np.clip((bg + v) * scan * np.clip(vig, 0.2, 1), 0, 1.2)
    rgb = lum[..., None] * np.array([0.35, 1.0, 0.45])
    crack = np.zeros((h, w))
    crack_walk(crack, np.random.default_rng(52), (h * 0.3, w * 0.78), 26, 6.0, 1.0, 1, 0.6)
    rgb = rgb * (1 - 0.85 * crack[..., None]) + crack[..., None] * np.array([0.25, 0.3, 0.25])
    return np.clip(rgb, 0, 1)


def paint_billows(w, h, discs, lit, shadow, grain, wrap=True):
    """Soft round puffs painted back to front (higher ones first): each lit on its top, shadowed underneath."""
    col = np.zeros((h, w, 3))
    alpha = np.zeros((h, w))
    for cx, cy, r in sorted(discs, key=lambda d: d[1]):
        y0, y1 = max(0, int(cy - r - 2)), min(h, int(cy + r + 2))
        xs = np.arange(int(cx - r - 2), int(cx + r + 3))
        if not wrap:
            xs = xs[(xs >= 0) & (xs < w)]
        ys = np.arange(y0, y1)
        if len(ys) == 0 or len(xs) == 0:
            continue
        X, Y = np.meshgrid(xs, ys)
        dist = np.hypot(X - cx, (Y - cy) * 1.1)
        inside = smoothstep(r, r * 0.72, dist)
        shade = np.clip(0.5 + 0.6 * (cy - Y) / r - 0.15 * (X - cx) / r, 0, 1) ** 1.5
        xi = X % w
        c = shadow[None, None, :] * (1 - shade[..., None]) + lit[None, None, :] * shade[..., None]
        c *= (0.82 + 0.36 * grain[Y % grain.shape[0], xi % grain.shape[1]])[..., None]
        a = inside[..., None]
        col[Y, xi] = col[Y, xi] * (1 - a) + c * a
        alpha[Y, xi] = np.maximum(alpha[Y, xi], inside)
    return col, alpha


def tex_storm():
    """512 x 512 RGBA, two parts (rows run top down):
    rows 0-255 (v 1-0.5): the wall's band, tiling across: cauliflower billows on top (its fringe, rows 0-115, ~0.96 m a
      pixel as mapped), dense dark umber body below, darkest at its base; tan where the sun catches the tops.
    rows 256-511 (v 0.5-0): a single puff cluster, its alpha dissolving to nothing at every edge (the cards that roll
      along the wall's edge, round its body and off its ends into the haze)."""
    w = 512
    rng = np.random.default_rng(61)
    lit = np.array([0.70, 0.49, 0.31])
    shadow = np.array([0.13, 0.075, 0.042])
    grain = vnoise(512, 24, 66, 3)
    # The band.
    h = 256
    discs = []
    for tier in range(9):
        cy0 = 52 + tier * 24
        for _ in range(16 + tier * 3):
            discs.append((rng.uniform(0, w), cy0 + rng.normal(0, 8), rng.uniform(22, 46) * (1 + 0.05 * tier)))
    col, alpha = paint_billows(w, h, discs, lit, shadow, grain)
    yy = np.mgrid[0:h, 0:w][0]
    body = smoothstep(140, 225, yy)
    cols = vnoise(512, 10, 68, 3)[:1, :] * np.ones((h, 1))
    bodyc = shadow * (0.7 + 0.8 * cols * (0.6 + 0.6 * vnoise(512, 6, 67, 4)[:h, :]))[..., None]
    col = col * (1 - body[..., None] * (1 - alpha[..., None])) + bodyc * body[..., None] * (1 - alpha[..., None])
    col *= (1 - 0.45 * smoothstep(150, 255, yy))[..., None]  # darker at its base
    alpha = np.maximum(alpha, body)
    band = np.concatenate([col, alpha[..., None]], axis=2)
    # The puff.
    discs = []
    for _ in range(80):
        a = rng.uniform(0, 2 * math.pi)
        rr = math.sqrt(rng.uniform(0, 1))
        discs.append((256 + 190 * rr * math.cos(a), 140 + 70 * rr * math.sin(a) + 20 * rr, rng.uniform(26, 58)))
    pcol, palpha = paint_billows(w, h, discs, lit * 1.05, shadow, grain, wrap=False)
    Y, X = np.mgrid[0:h, 0:w]
    fall = smoothstep(1.0, 0.45, ((X - 256) / 250.0) ** 2 + ((Y - 135) / 125.0) ** 2)
    palpha *= fall * (0.85 + 0.15 * grain[:h, :])
    pcol *= (1 - 0.4 * smoothstep(150, 250, Y))[..., None]
    puff = np.concatenate([pcol, palpha[..., None]], axis=2)
    out = np.concatenate([band, puff], axis=0)
    out[..., :3] = np.clip(out[..., :3], 0, 1)
    out[..., 3] = np.clip(out[..., 3], 0, 1)
    return out


TEX = {
    'asphalt': make_image('City4AsphaltTex', tex_asphalt()),
    'sand': make_image('City4SandTex', tex_sand()),
    'rust': make_image('City4RustTex', tex_rust()),
    'concrete': make_image('City4ConcreteTex', tex_concrete()),
    'screen': make_image('City4ScreenTex', tex_screen()),
    'storm': make_image('City4StormTex', tex_storm(), jpeg=False),
}


# =========================================================================================================================
# Materials: plain Principled BSDFs (a texture, times the mesh's baked AO vertex colour where it has one).
# =========================================================================================================================
def material(name, colour, roughness=0.6, metallic=0.0, tex=None, vcol=True, emission=None, strength=0.0,
             emit_tex=False, alpha_tex=False, alpha=1.0, spec=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*colour, 1)
    p.inputs['Roughness'].default_value = roughness
    p.inputs['Metallic'].default_value = metallic
    if 'Specular IOR Level' in p.inputs:
        p.inputs['Specular IOR Level'].default_value = spec
    col_out = None
    if tex is not None:
        it = nt.nodes.new('ShaderNodeTexImage')
        it.image = TEX[tex]
        uvn = nt.nodes.new('ShaderNodeUVMap')
        uvn.uv_map = 'UVMap'
        nt.links.new(uvn.outputs['UV'], it.inputs['Vector'])
        col_out = it.outputs['Color']
        if alpha_tex:
            nt.links.new(it.outputs['Alpha'], p.inputs['Alpha'])
    if vcol:
        ca = nt.nodes.new('ShaderNodeVertexColor')
        ca.layer_name = 'AO'
        if col_out is not None:
            mix = nt.nodes.new('ShaderNodeMix')
            mix.data_type = 'RGBA'
            mix.blend_type = 'MULTIPLY'
            mix.inputs['Factor'].default_value = 1.0
            nt.links.new(col_out, mix.inputs['A'])
            nt.links.new(ca.outputs['Color'], mix.inputs['B'])
            nt.links.new(mix.outputs['Result'], p.inputs['Base Color'])
        else:
            mix = nt.nodes.new('ShaderNodeMix')
            mix.data_type = 'RGBA'
            mix.blend_type = 'MULTIPLY'
            mix.inputs['Factor'].default_value = 1.0
            mix.inputs['A'].default_value = (*colour, 1)
            nt.links.new(ca.outputs['Color'], mix.inputs['B'])
            nt.links.new(mix.outputs['Result'], p.inputs['Base Color'])
    elif col_out is not None:
        nt.links.new(col_out, p.inputs['Base Color'])
    if emission:
        p.inputs['Emission Color'].default_value = (*emission, 1)
        p.inputs['Emission Strength'].default_value = strength
        if emit_tex and col_out is not None:
            nt.links.new(col_out, p.inputs['Emission Color'])
    if alpha < 1 or alpha_tex:
        if not alpha_tex:
            p.inputs['Alpha'].default_value = alpha
        if hasattr(m, 'surface_render_method'):
            m.surface_render_method = 'BLENDED'
        m.use_backface_culling = False
    return m


MAT = {
    'sand': material('City4Sand', (0.80, 0.52, 0.28), 0.95, tex='sand', spec=0.3),
    'asphalt': material('City4Asphalt', (0.25, 0.215, 0.19), 0.85, tex='asphalt', spec=0.35),
    'concrete': material('City4Concrete', (0.62, 0.53, 0.43), 0.9, tex='concrete', spec=0.3),
    'rust': material('City4Rust', (0.2, 0.14, 0.1), 0.72, 0.35, tex='rust'),
    'fan': material('City4Fan', (0.09, 0.075, 0.065), 0.6, 0.7, tex='rust'),
    'screen': material('City4Screen', (0.05, 0.25, 0.08), 0.35, tex='screen', emission=(0.3, 1.0, 0.4),
                       strength=2.2, emit_tex=True),
    'led': material('City4Led', (0.25, 1.0, 0.35), 0.4, emission=(0.35, 1.0, 0.3), strength=9.0),
    'glass': material('City4Glass', (0.05, 0.07, 0.06), 0.15, 0.2, emission=(0.45, 0.85, 0.35),
                      strength=0.6),
    'sun': material('City4Sun', (1.0, 0.97, 0.88), 1.0, vcol=False, emission=(1.0, 0.95, 0.82), strength=30.0),
    'cable': material('City4Cable', (0.045, 0.04, 0.035), 0.8, 0.0),
    'storm': material('City4Storm', (0.72, 0.46, 0.27), 1.0, tex='storm', vcol=False, alpha_tex=True, spec=0.0),
    'lightning': material('City4Lightning', (0.85, 0.75, 1.0), 1.0, vcol=False, emission=(0.85, 0.72, 1.0),
                          strength=40.0),
}


# =========================================================================================================================
# Mesh helpers.
# =========================================================================================================================
TAG = [None]          # set while building approach-only pieces
IDS = {}              # object name -> score.py ID key (the arrival's composed features)


def obj(name, me, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), ident=None):
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    if TAG[0]:
        o['approach_only'] = TAG[0]
    o.parent = parent or root
    o.location = loc
    o.rotation_euler = rot
    o.scale = scale if not isinstance(scale, (int, float)) else (scale,) * 3
    if ident:
        IDS[o.name] = ident
    return o


def mesh_from(name, bm, mats, smooth=False, recalc=True):
    me = bpy.data.meshes.new(name)
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for m in (mats if isinstance(mats, (list, tuple)) else [mats]):
        me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = smooth
    return me


def add_box(bm, c, size, mat=0, rot=None):
    """An axis-aligned box (centre c, size (x, y, z)), optionally rotated about its centre; returns its faces."""
    res = bmesh.ops.create_cube(bm, size=1.0)
    vs = res['verts']
    M = Matrix.Translation(Vector(c))
    if rot is not None:
        M = M @ rot.to_4x4()
    M = M @ Matrix.Diagonal((*size, 1.0))
    bmesh.ops.transform(bm, matrix=M, verts=vs)
    faces = list({f for v in vs for f in v.link_faces})
    for f in faces:
        f.material_index = mat
    return faces


def add_quad(bm, corners, mat=0):
    f = bm.faces.new([bm.verts.new(c) for c in corners])
    f.material_index = mat
    return f


def lathe(bm, profile, seg=24, cx=0.0, cy=0.0, z0=0.0, cap_top=True, cap_bottom=True, mat=0):
    rings = []
    for r, z in profile:
        rings.append([bm.verts.new((cx + r * math.cos(2 * math.pi * i / seg), cy + r * math.sin(2 * math.pi * i / seg),
                                    z0 + z)) for i in range(seg)])
    for a, b in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((a[i], a[j], b[j], b[i])).material_index = mat
    if cap_bottom and profile[0][0] > 1e-4:
        bm.faces.new(list(reversed(rings[0]))).material_index = mat
    if cap_top and profile[-1][0] > 1e-4:
        bm.faces.new(rings[-1]).material_index = mat
    return rings


def sweep(bm, path, profile, up=Vector((0, 0, 1)), mat=0, caps=True):
    """Extrude a closed 2-D (lateral, vertical) profile along a 3-D path."""
    rings = []
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        side = t.cross(up)
        if side.length < 1e-6:
            side = t.cross(Vector((1, 0, 0)))
        side.normalize()
        u = side.cross(t).normalized()
        rings.append([bm.verts.new(p + side * a + u * b) for a, b in profile])
    n = len(profile)
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i])).material_index = mat
    if caps:
        bm.faces.new(list(reversed(rings[0]))).material_index = mat
        bm.faces.new(rings[-1]).material_index = mat
    return rings


def circle_profile(r, n=6):
    return [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def box_uvs(me, scale=0.25):
    """Box-projected UVs (by each face's dominant normal axis), `scale` UV units per metre."""
    uv = me.uv_layers.new(name='UVMap') if 'UVMap' not in me.uv_layers else me.uv_layers['UVMap']
    for poly in me.polygons:
        n = poly.normal
        ax = max(range(3), key=lambda k: abs(n[k]))
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if ax == 0:
                u, v = co.y, co.z
            elif ax == 1:
                u, v = co.x, co.z
            else:
                u, v = co.x, co.y
            uv.data[li].uv = (u * scale, v * scale)


def planar_uvs(me, scale=0.1):
    uv = me.uv_layers.new(name='UVMap')
    for loop in me.loops:
        co = me.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (co.x * scale, co.y * scale)


def set_vcol(me, values):
    """Per-vertex AO values (0..1) into the 'AO' corner colour attribute (sRGB bytes)."""
    if 'AO' in me.color_attributes:
        me.color_attributes.remove(me.color_attributes['AO'])
    ca = me.color_attributes.new('AO', 'BYTE_COLOR', 'CORNER')
    vi = np.zeros(len(me.loops), np.int64)
    me.loops.foreach_get('vertex_index', vi)
    v = np.asarray(values, np.float32)[vi]
    cols = np.repeat(v[:, None], 4, axis=1)
    cols[:, 3] = 1.0
    ca.data.foreach_set('color', cols.ravel())
    me.color_attributes.active_color = ca


def bake_ao(me, rays=14, dist=None, floor=0.5, extra=None):
    """Self-occlusion ambient occlusion into vertex colours: hemisphere rays from each vertex against the mesh itself
    (plus an optional ground plane at z `extra`), mapped to floor..1."""
    verts = [v.co.copy() for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    if not polys:
        return
    bvh = BVHTree.FromPolygons(verts, polys)
    size = max((Vector(me.vertices[0].co) - v.co).length for v in me.vertices) if dist is None else dist
    dist = dist or max(0.5, size * 0.6)
    rng = np.random.default_rng(5)
    dirs = rng.normal(size=(rays, 3))
    dirs /= np.linalg.norm(dirs, axis=1)[:, None]
    out = np.ones(len(verts))
    for i, v in enumerate(me.vertices):
        n = v.normal
        o = v.co + n * 0.01
        hits = 0
        for d in dirs:
            d = Vector(d)
            if d.dot(n) < 0:
                d = -d
            d = (d + n * 0.3).normalized()
            if bvh.ray_cast(o, d, dist)[0] is not None:
                hits += 1
            elif extra is not None and d.z < -0.05 and (extra - o.z) / d.z < dist:
                hits += 1
        out[i] = 1 - hits / rays
    set_vcol(me, floor + (1 - floor) * out)


# --- Groups ---------------------------------------------------------------------------------------------------------------
def group(name, parent=None):
    e = bpy.data.objects.new(name, None)
    scene.collection.objects.link(e)
    e.parent = parent or root
    if TAG[0]:
        e['approach_only'] = TAG[0]
    return e


G = {k: group(f'City4.{k}') for k in ('Road', 'Barriers', 'Drifts', 'Dunes', 'Servers', 'Fans', 'Cables', 'Screens',
                                      'Facility', 'Gantries', 'Storm', 'Sky', 'Arrival')}


# =========================================================================================================================
# Modules (one mesh each, instanced). Monoliths, CRTs and fans face their local -Y; their base sits at z 0.
# =========================================================================================================================
def module_fan():
    """A fan, radius 1, facing -Y: a square housing round a ring, seven twisted blades, a hub, a guard cross."""
    bm = bmesh.new()
    seg = 12
    # Housing: a square frame (outer half-size 1.12) round a 12-gon opening (radius 1), 0.25 deep.
    outer = [Vector((1.12 * math.cos(math.pi / 4 + k * math.pi / 2) * math.sqrt(2), 0,
                     1.12 * math.sin(math.pi / 4 + k * math.pi / 2) * math.sqrt(2))) for k in range(4)]
    ring = [Vector((math.cos(2 * math.pi * k / seg), 0, math.sin(2 * math.pi * k / seg))) for k in range(seg)]
    fo = [bm.verts.new(p + Vector((0, -0.12, 0))) for p in ring]
    bo = [bm.verts.new(p + Vector((0, 0.13, 0))) for p in ring]
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((fo[i], fo[j], bo[j], bo[i]))  # the ring's inner wall
    co = [bm.verts.new(Vector((max(-1.12, min(1.12, p.x * 1.6)), -0.12, max(-1.12, min(1.12, p.z * 1.6)))))
          for p in ring]
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((fo[j], fo[i], co[i], co[j]))  # the housing's front, square outside, round inside
    # Blades: twisted quads from the hub (r 0.28) to the rim (r 0.95), set back in the ring.
    for k in range(7):
        a = 2 * math.pi * k / 7
        vs = []
        for r, da, tw in ((0.28, 0.0, 0.32), (0.95, 0.42, 0.12)):
            c1, s1 = math.cos(a + da), math.sin(a + da)
            c2, s2 = math.cos(a + da + 0.55), math.sin(a + da + 0.55)
            vs.append((bm.verts.new((r * c1, 0.02 - tw, r * s1)), bm.verts.new((r * c2, 0.02 + tw, r * s2))))
        (a0, a1), (b0, b1) = vs
        bm.faces.new((a0, a1, b1, b0))
    add_box(bm, (0, -0.06, 0), (0.56, 0.2, 0.56))  # the hub
    # Guard: a cross of thin bars over the front.
    for ang in (45, 135):
        add_box(bm, (0, -0.16, 0), (2.1, 0.04, 0.05), rot=Matrix.Rotation(math.radians(ang), 3, 'Y'))
    me = mesh_from('City4.M.Fan', bm, MAT['fan'])
    box_uvs(me, 0.4)
    return me


def rack_face(bm, x0, x1, z0, z1, y, rows, led_rows=True, mat=0, led=1, rng=None):
    """Rack units across a face at depth y (facing -Y): protruding slot rails and LED dots."""
    rng = rng or random.Random(1)
    h = (z1 - z0) / rows
    for r in range(rows):
        zc = z0 + h * (r + 0.5)
        add_box(bm, ((x0 + x1) / 2, y - 0.06, zc - h * 0.38), (x1 - x0, 0.12, h * 0.12), mat)
        if led_rows and rng.random() < 0.85:
            n = rng.randint(3, 9)
            for k in range(n):
                xc = x0 + (x1 - x0) * rng.uniform(0.05, 0.95)
                s = (x1 - x0) * 0.012 + 0.03
                add_quad(bm, [(xc - s, y - 0.13, zc - s * 0.6), (xc + s, y - 0.13, zc - s * 0.6),
                              (xc + s, y - 0.13, zc + s * 0.6), (xc - s, y - 0.13, zc + s * 0.6)], led)


def module_monolith(kind):
    """Server monoliths. 'tower': 9 x 6 x 24 m, a rack half and a column of three fan bays (the arrival's near-left
    one); 'slab': 12 x 5 x 20 m, rack units over the front, four fans down its right side; 'fanwall': 10 x 5 x 12 m,
    two by two fans and a terminal screen above. Returns the mesh and its fan mounts (local position, radius,
    facing: 'front' or 'side')."""
    rng = random.Random(hash(kind) % 1000)
    bm = bmesh.new()
    fans = []
    if kind == 'tower':
        W, D, Hh = 9.0, 6.0, 24.0
    elif kind == 'slab':
        W, D, Hh = 12.0, 5.0, 20.0
    else:
        W, D, Hh = 10.0, 5.0, 12.0
    # Body, a cap and a plinth band.
    add_box(bm, (0, 0, Hh / 2 - 2), (W, D, Hh + 4))
    add_box(bm, (0, 0, Hh + 0.25), (W + 0.5, D + 0.5, 0.5))
    add_box(bm, (0, 0, Hh * 0.62), (W + 0.25, D + 0.25, 0.35))
    fy = -D / 2
    if kind == 'tower':
        rack_face(bm, -W / 2 + 0.4, -0.2, 0.5, Hh - 0.6, fy, 16, rng=rng)
        for k, zc in enumerate((Hh * 0.18, Hh * 0.47, Hh * 0.77)):
            r = 1.9
            add_box(bm, (W * 0.25, fy - 0.1, zc), (r * 2.4, 0.2, 0.3))
            add_box(bm, (W * 0.25, fy - 0.1, zc + r * 1.25), (r * 2.4, 0.2, 0.25))
            fans.append(((W * 0.25, fy - 0.35, zc + 0.1), r, 'front'))
        # Side vents (+X face).
        for k in range(10):
            add_box(bm, (W / 2 + 0.05, 0, 1.5 + k * 2.1), (0.12, D * 0.8, 0.25))
    elif kind == 'slab':
        rack_face(bm, -W / 2 + 0.5, W / 2 - 0.5, 0.5, Hh - 0.6, fy, 14, rng=rng)
        for k in range(4):
            zc = 2.4 + k * 4.4
            fans.append(((W / 2 + 0.3, -D * 0.1, zc), 1.7, 'side'))
            add_box(bm, (W / 2 + 0.1, -D * 0.1, zc + 2.05), (0.2, 4.0, 0.25))
    else:
        for i, xc in enumerate((-W * 0.24, W * 0.24)):
            for j, zc in enumerate((Hh * 0.22, Hh * 0.55)):
                fans.append(((xc, fy - 0.35, zc), 2.0, 'front'))
                add_box(bm, (xc, fy - 0.08, zc + 2.3), (4.6, 0.18, 0.25))
        # The terminal: a screen panel in a frame, top centre.
        sz = Hh * 0.82
        add_box(bm, (0, fy - 0.15, sz), (W * 0.62, 0.3, Hh * 0.2))
        f = add_quad(bm, [(-W * 0.28, fy - 0.31, sz - Hh * 0.085), (W * 0.28, fy - 0.31, sz - Hh * 0.085),
                          (W * 0.28, fy - 0.31, sz + Hh * 0.085), (-W * 0.28, fy - 0.31, sz + Hh * 0.085)], 2)
        rack_face(bm, -W / 2 + 0.4, W / 2 - 0.4, 0.4, Hh * 0.07, fy, 2, rng=rng)
    me = mesh_from(f'City4.M.{kind.capitalize()}', bm, [MAT['rust'], MAT['led'], MAT['screen']])
    box_uvs(me, 0.12)
    # The screen face's UVs 0-1 (it's the only material-2 face).
    uv = me.uv_layers['UVMap']
    for poly in me.polygons:
        if poly.material_index == 2:
            for li, c in zip(poly.loop_indices, ((0, 0), (1, 0), (1, 1), (0, 1))):
                uv.data[li].uv = c
    return me, fans


def module_crt():
    """A CRT terminal, 1 m wide: a tapering tube behind a bezel, the screen (UVs 0-1) facing -Y, base at z 0."""
    bm = bmesh.new()
    add_box(bm, (0, 0.05, 0.38), (1.0, 0.22, 0.76))                    # bezel
    add_box(bm, (0, 0.42, 0.38), (0.8, 0.55, 0.6))                     # tube housing
    add_box(bm, (0, 0.78, 0.38), (0.5, 0.3, 0.38))                     # neck
    f = add_quad(bm, [(-0.42, -0.065, 0.08), (0.42, -0.065, 0.08), (0.42, -0.065, 0.68), (-0.42, -0.065, 0.68)], 1)
    me = mesh_from('City4.M.Crt', bm, [MAT['rust'], MAT['screen']])
    box_uvs(me, 1.0)
    uv = me.uv_layers['UVMap']
    for poly in me.polygons:
        if poly.material_index == 1:
            for li, c in zip(poly.loop_indices, ((0, 0), (1, 0), (1, 1), (0, 1))):
                uv.data[li].uv = c
    return me


def module_barrier():
    """A 6 m concrete barrier block, its road face toward -Y: a jersey profile 0.7 m over the deck (sunk 0.3), a green
    lit panel on the road face."""
    bm = bmesh.new()
    prof = [(-0.30, -0.3), (0.30, -0.3), (0.30, 0.05), (0.27, 0.12), (0.10, 0.70), (-0.10, 0.70), (-0.27, 0.12),
            (-0.30, 0.05)]
    L = 2.95
    a = [bm.verts.new((-L, y, z)) for y, z in prof]
    b = [bm.verts.new((L, y, z)) for y, z in prof]
    n = len(prof)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    # The panel on the road face's slope (between z 0.12 at y -0.27 and z 0.70 at y -0.10).
    def on_slope(z):
        return -0.27 + (z - 0.12) / 0.58 * 0.17 - 0.012
    add_quad(bm, [(-0.9, on_slope(0.26), 0.26), (0.9, on_slope(0.26), 0.26), (0.9, on_slope(0.4), 0.4),
                  (-0.9, on_slope(0.4), 0.4)], 1)
    me = mesh_from('City4.M.Barrier', bm, [MAT['concrete'], MAT['led']])
    box_uvs(me, 0.3)
    return me


def module_mast():
    """A three-legged lattice mast, 30 m, tapering, with a beacon; base at z 0."""
    bm = bmesh.new()
    H, r0, r1 = 30.0, 1.6, 0.35
    legs = [(math.cos(a), math.sin(a)) for a in (0, 2 * math.pi / 3, 4 * math.pi / 3)]

    def leg_pt(k, z):
        r = r0 + (r1 - r0) * z / H
        return Vector((legs[k][0] * r, legs[k][1] * r, z))
    for k in range(3):
        sweep(bm, [leg_pt(k, 0), leg_pt(k, H)], [(0.09, -0.09), (0.09, 0.09), (-0.09, 0.09), (-0.09, -0.09)])
    zs = frange(0, H, 3.0)
    for k in range(3):
        k2 = (k + 1) % 3
        for i, (z0, z1) in enumerate(zip(zs, zs[1:])):
            p0, p1 = (leg_pt(k, z0), leg_pt(k2, z1)) if i % 2 == 0 else (leg_pt(k2, z0), leg_pt(k, z1))
            sweep(bm, [p0, p1], [(0.05, -0.05), (0.05, 0.05), (-0.05, 0.05), (-0.05, -0.05)], caps=False)
    add_box(bm, (0, 0, H + 1.0), (0.12, 0.12, 2.0))
    add_box(bm, (0, 0, H + 2.1), (0.35, 0.35, 0.3), 1)
    me = mesh_from('City4.M.Mast', bm, [MAT['rust'], MAT['led']])
    box_uvs(me, 0.5)
    return me


M = {
    'fan': module_fan(),
    'crt': module_crt(),
    'barrier': module_barrier(),
    'mast': module_mast(),
}
FAN_MOUNTS = {}
for k in ('tower', 'slab', 'fanwall'):
    M[k], FAN_MOUNTS[k] = module_monolith(k)
COUNT = {}


def inst(kind, loc, scale=1.0, rot=(0, 0, 0), parent=None, ident=None, name=None):
    COUNT[kind] = COUNT.get(kind, 0) + 1
    return obj(name or f'City4.{kind.capitalize()}.{COUNT[kind]:03d}', M[kind], parent, loc, rot, scale, ident)


def place_monolith(kind, pos, yaw, scale, tilt=(0.0, 0.0), parent=None, ident=None, name=None):
    """A monolith at pos (its base centre), turned by yaw (its front, local -Y, then faces along face_yaw's dirn),
    leaning by tilt (x, y radians), uniformly scaled; its fans placed with it."""
    sc = (scale,) * 3 if isinstance(scale, (int, float)) else tuple(scale)
    rot = (tilt[0], tilt[1], yaw)
    o = inst(kind, pos, sc, rot, parent or G['Servers'], ident, name)
    R = Matrix.Translation(pos) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(tilt[1], 4, 'Y') @ \
        Matrix.Rotation(tilt[0], 4, 'X')
    Mo = R @ Matrix.Diagonal((*sc, 1))
    fs = min(sc[0], sc[2])
    for (mx, my, mz), r, facing in FAN_MOUNTS[kind]:
        Mf = Matrix.Translation(Mo @ Vector((mx, my, mz))) @ R.to_3x3().to_4x4()
        if facing == 'side':
            Mf = Mf @ Matrix.Rotation(math.radians(90), 4, 'Z')
        Mf = Mf @ Matrix.Diagonal((r * fs, r * fs, r * fs, 1))
        loc, q, fsc = Mf.decompose()
        f = inst('fan', loc, fsc.x, q.to_euler(), G['Fans'], ident=ident)
        f['spin_axis'] = 'local -Y'
    return o


# =========================================================================================================================
# The arrival, composed in its camera's screen space from the concept's guides (art/align4/concept-features.json).
# =========================================================================================================================
BOXES = FEAT['boxes']
MOUNDS = []   # (x, y, radius, z): the dunes are set to z round these (a monolith's buried base, a CRT's bed)
HOLLOWS = []  # (x, y, radius): kept low (sightlines to the facility)
DIMS = {'tower': (9.0, 6.0, 24.0), 'slab': (12.0, 5.0, 20.0), 'fanwall': (10.0, 5.0, 12.0), 'crt': (1.0, 1.0, 0.76)}


def module_corners(kind):
    W, D, Hh = DIMS[kind]
    if kind == 'crt':
        return [Vector((x, y, z)) for x in (-0.5, 0.5) for y in (-0.06, 0.16) for z in (0.0, 0.76)]
    return [Vector((x, y, z)) for x in (-W / 2, W / 2) for y in (-D / 2, D / 2) for z in (0.0, Hh)]


def projected_box(kind, pos, yaw, tilt, sc):
    R = Matrix.Translation(pos) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(tilt[1], 4, 'Y') @ \
        Matrix.Rotation(tilt[0], 4, 'X') @ Matrix.Diagonal((*sc, 1))
    pts = [to_screen(R @ c)[0] for c in module_corners(kind)]
    return [min(p.x for p in pts), min(p.y for p in pts), max(p.x for p in pts), max(p.y for p in pts)]


def fit_to_box(kind, box, depth, yaw_off, tilt, fixed=None, aspect=None):
    """Place a module so its projected bounding box matches a concept box: solve its screen column, base height and
    scale (x/y and z) by Gauss-Newton on the box's edges (only those inside the frame: an edge on the frame's border is
    clipped there). fixed=(sx, sz) holds the scale (the near monolith runs off the frame's top and left)."""
    tx0, ty0, tx1, ty1 = box
    use = [tx0 > 2, ty0 > 2, tx1 < RES[0] - 2, ty1 < RES[1] - 2]
    W = DIMS[kind][0]
    xc = (tx0 + tx1) / 2
    zb = z_of_row(xc, ty1, depth)
    s0 = px_to_m(tx1 - tx0, depth) / W
    p = np.array([xc, zb, s0, s0 if aspect is None else s0 * aspect] if fixed is None else [xc, zb])

    def build(p):
        pos = ground_at_depth(p[0], depth)
        pos.z = p[1]
        sx, sz = (p[2], p[3]) if fixed is None else fixed
        yaw = yaw_to_eye(pos) + math.radians(yaw_off)
        return pos, yaw, (sx, sx, sz)

    def res(p):
        pos, yaw, sc = build(p)
        b = projected_box(kind, pos, yaw, tilt, sc)
        return np.array([b[i] - box[i] for i in range(4) if use[i]])
    for _ in range(30):
        r = res(p)
        J = np.zeros((len(r), len(p)))
        for k in range(len(p)):
            dp = np.zeros(len(p))
            dp[k] = max(1e-3, abs(p[k]) * 1e-3)
            J[:, k] = (res(p + dp) - r) / dp[k]
        step, *_ = np.linalg.lstsq(J, -r, rcond=None)
        p = p + 0.8 * step
        if fixed is None:
            p[2:] = np.clip(p[2:], 0.05, 20)
        if np.abs(r).max() < 0.5:
            break
    pos, yaw, sc = build(p)
    return pos, yaw, sc, float(np.abs(res(p)).max()) if len(res(p)) else 0.0


TAG[0] = None
COMPOSE = [  # key, kind, view depth, yaw offset (deg, from facing the eye), tilt (deg about x, y), fixed scale
    ('LN', 'tower', 22.0, -12.0, (0.0, 0.0), (1.25, 1.0)),
    ('L2', 'slab', 110.0, -30.0, (-3.0, 5.0), None),
    ('L3', 'fanwall', 190.0, -20.0, (2.0, -4.0), None),
    ('L4', 'slab', 250.0, 15.0, (0.0, 3.0), None),
    ('R1', 'tower', 125.0, 35.0, (3.0, -6.0), None),
    ('R2', 'slab', 160.0, 38.0, (-2.0, 6.0), None),
    ('R3', 'fanwall', 215.0, 22.0, (0.0, -4.0), None),
]
COMPOSED = {}
for key, kind, depth, yo, tilt, fixed in COMPOSE:
    tilt_r = (math.radians(tilt[0]), math.radians(tilt[1]))
    pos, yaw, sc, err = fit_to_box(kind, BOXES[key], depth, yo, tilt_r, fixed)
    COMPOSED[key] = (kind, pos, yaw, sc, tilt_r)
    W, D, Hh = DIMS[kind]
    MOUNDS.append((pos.x, pos.y, max(W, D) * sc[0] * 0.75 + 10.0, pos.z + 0.4))
    print('compose', key, kind, 'base', [round(v, 1) for v in pos], 'scale', [round(v, 2) for v in sc],
          'box err px', round(err, 1))
# Two far, small ones (concept x ~605 and ~920, on the dune line).
for key, sx, depth in (('L5', 605, 320.0), ('R4', 920, 300.0)):
    pos = ground_at_depth(sx, depth)
    pos.z = z_of_row(sx, 316, depth)
    COMPOSED[key] = ('slab', pos, yaw_to_eye(pos) + 0.3, (0.55, 0.55, 0.6), (0.0, 0.05))
    MOUNDS.append((pos.x, pos.y, 18.0, pos.z + 0.3))
for key, (kind, pos, yaw, sc, tilt_r) in COMPOSED.items():
    place_monolith(kind, pos, yaw, sc, tilt_r, parent=G['Arrival'], ident=key, name=f'City4.Arrival.{key}')

# The CRTs: big terminals lying in the sand. The left two on a drift over the left lane (the concept's road is
# narrower than ours: its left-hand ground lands on our left lane), the right two on the right shoulder.
CRT_SET = [  # key, view depth, yaw offset, tilt back (deg)
    ('CRT_L', 7.6, 24.0, -22.0), ('CRT_M', 16.5, 10.0, -16.0), ('CRT_R', 9.6, -18.0, -18.0),
    ('CRT_R2', 13.8, -8.0, -14.0),
]
for key, depth, yo, tb in CRT_SET:
    pos, yaw, sc, err = fit_to_box('crt', BOXES[key], depth, yo, (math.radians(tb), 0.0), None, aspect=1.0)
    inst('crt', pos, sc, (math.radians(tb), 0.0, yaw), G['Arrival'], ident=key, name=f'City4.Arrival.{key}')
    COMPOSED[key] = ('crt', pos, yaw, sc, None)
    print('compose', key, 'base', [round(v, 2) for v in pos], 'scale', round(sc[0], 2), 'err', round(err, 1))


# --- The facility: blocks composed in the arrival frame (each a front at a view depth, sized off the concept) --------------
FAC_Z = 0.0
FAC = []  # (name, centre, yaw, w, d, h) for the plan and the sightline hollow


def facade_frame(sx, depth):
    """A facade's base centre at screen column sx, view depth `depth`, on the compound's floor, and its yaw (its
    front, local -Y, facing back down the road at the arrival)."""
    p = ground_at_depth(sx, depth)
    p.z = FAC_Z
    return p, 0.0 + math.radians(-90)  # local -Y -> world -X: facing back down the road


def fac_block(bm, sx0, sx1, top, depth, deep, mat=0, batter=0.0, crenel=False, steps=0):
    """A concrete block whose front spans screen columns sx0-sx1 at view depth `depth`, up to screen row `top`; `deep`
    metres back. batter: its front face leans back by that fraction of its height (a bunker wall); with steps, it
    steps back in that many tiers instead (the same outline), a slit window along each tier's face."""
    pc, _ = facade_frame((sx0 + sx1) / 2, depth)
    w = px_to_m(sx1 - sx0, depth)
    h = z_of_row((sx0 + sx1) / 2, top, depth) - FAC_Z
    # Fronts face -X (back down the road): build in world axes, x back, y across.
    x0, x1 = pc.x, pc.x + deep
    y0, y1 = pc.y - w / 2, pc.y + w / 2
    z0, z1 = FAC_Z - 1.0, FAC_Z + h
    if steps:
        for k in range(steps):
            za, zb = FAC_Z + h * k / steps - (1.0 if k == 0 else 0.0), FAC_Z + h * (k + 1) / steps
            xs = x0 + batter * h * (k + 0.5) / steps
            wk = w * (1 - 0.06 * k)
            add_box(bm, ((xs + x1) / 2, pc.y, (za + zb) / 2), (x1 - xs, wk, zb - za), mat)
            n = max(2, int(wk / 7))
            for j in range(n):  # ribs between bays; slit windows, lit, on the top tier only
                yc = pc.y - wk / 2 + wk * (j + 0.5) / n
                if k == steps - 1 and j % 2 == 0:
                    zc = (za + zb) / 2 + (zb - za) * 0.15
                    add_quad(bm, [(xs - 0.05, yc - wk / n * 0.25, zc - 0.14), (xs - 0.05, yc + wk / n * 0.25, zc - 0.14),
                                  (xs - 0.05, yc + wk / n * 0.25, zc + 0.14), (xs - 0.05, yc - wk / n * 0.25, zc + 0.14)],
                             1)
                add_box(bm, (xs - 0.5, yc + wk / n * 0.5, (za + zb) / 2), (1.0, 0.9, zb - za), mat)  # rib
        FAC.append((pc, w, deep, h))
        return pc, w, h
    v = [bm.verts.new(c) for c in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                   (x0 + batter * h, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0 + batter * h, y1, z1))]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        bm.faces.new([v[i] for i in f]).material_index = mat
    if crenel:
        n = max(2, int(w / 3.0))
        for k in range(n):
            if k % 2 == 0:
                yc = y0 + (k + 0.5) * w / n
                add_box(bm, (x0 + batter * h + 0.6, yc, z1 + 0.6), (1.2, w / n, 1.2), mat)
    FAC.append((pc, w, deep, h))
    return pc, w, h


def windows(bm, pc, w, h, rows, z_from, z_to, mat, cols=None, x_off=-0.06):
    """Strips of windows across a facade's front (at pc.x + x_off)."""
    for r in range(rows):
        z = FAC_Z + z_from + (z_to - z_from) * (r + 0.5) / rows
        if cols:
            for c in range(cols):
                yc = pc.y - w / 2 + w * (c + 0.5) / cols
                add_quad(bm, [(pc.x + x_off, yc - w / cols * 0.3, z - 0.5), (pc.x + x_off, yc + w / cols * 0.3, z - 0.5),
                              (pc.x + x_off, yc + w / cols * 0.3, z + 0.5), (pc.x + x_off, yc - w / cols * 0.3, z + 0.5)],
                         mat)
        else:
            add_quad(bm, [(pc.x + x_off, pc.y - w * 0.42, z - 0.35), (pc.x + x_off, pc.y + w * 0.42, z - 0.35),
                          (pc.x + x_off, pc.y + w * 0.42, z + 0.35), (pc.x + x_off, pc.y - w * 0.42, z + 0.35)], mat)


def buttresses(bm, pc, w, h, every=7.0, out=1.6, frac=0.82):
    """Sloped concrete buttresses down a facade's front (it faces -X at pc.x)."""
    n = max(2, int(w / every))
    for k in range(n + 1):
        yc = pc.y - w / 2 + w * k / n
        b = bmesh.ops.create_cube(bm, size=1.0)['verts']
        bmesh.ops.transform(bm, verts=b, matrix=Matrix.Translation((pc.x - out / 2, yc, FAC_Z + h * frac / 2 - 0.5)) @
                            Matrix.Diagonal((out, 1.1, h * frac + 1.0, 1)))
        for v_ in b:  # slope its face back toward the top
            if v_.co.x < pc.x - out * 0.9 and v_.co.z > FAC_Z + h * frac * 0.5:
                v_.co.x = pc.x - out * 0.25


def vents(bm, pc, w, h, n, rng, z_lo=0.25, z_hi=0.7):
    """Dark steel vent grilles set on a facade's front."""
    for k in range(n):
        yc = pc.y - w / 2 + w * rng.uniform(0.1, 0.9)
        zc = FAC_Z + h * rng.uniform(z_lo, z_hi)
        add_box(bm, (pc.x - 0.12, yc, zc), (0.25, rng.uniform(1.2, 2.6), rng.uniform(0.8, 1.6)), 3)
        for j in range(3):
            add_box(bm, (pc.x - 0.28, yc, zc - 0.4 + 0.4 * j), (0.08, 1.0, 0.08), 3)


def antennas(bm, pc, w, h, deep, n, rng, hmax=4.0):
    """A cluster of thin masts and a small box or two on a block's roof."""
    for k in range(n):
        x = pc.x + deep * rng.uniform(0.25, 0.8)
        y = pc.y + w * rng.uniform(-0.35, 0.35)
        hh = rng.uniform(0.4, 1.0) * hmax
        add_box(bm, (x, y, FAC_Z + h + hh / 2), (0.16, 0.16, hh), 3)
        if rng.random() < 0.4:
            add_box(bm, (x, y, FAC_Z + h + hh * 0.8), (0.08, 1.4, 0.08), 3)
    for k in range(2):
        add_box(bm, (pc.x + deep * rng.uniform(0.3, 0.7), pc.y + w * rng.uniform(-0.3, 0.3), FAC_Z + h + 0.6),
                (rng.uniform(1.5, 3.0), rng.uniform(1.5, 3.0), 1.2), 3)


def watchtower(bm, sx, top, depth):
    pc, _ = facade_frame(sx, depth)
    h = z_of_row(sx, top, depth) - FAC_Z
    r = px_to_m(9, depth)
    lathe(bm, [(r * 0.7, -1.0), (r * 0.6, h * 0.72)], seg=8, cx=pc.x, cy=pc.y, z0=FAC_Z)
    lathe(bm, [(r * 1.25, h * 0.72), (r * 1.25, h * 0.86), (r * 1.4, h * 0.88), (r * 0.3, h * 0.97)], seg=8,
          cx=pc.x, cy=pc.y, z0=FAC_Z)
    lathe(bm, [(r * 1.27, h * 0.76), (r * 1.27, h * 0.83)], seg=8, cx=pc.x, cy=pc.y, z0=FAC_Z, cap_top=False,
          cap_bottom=False, mat=1)
    add_box(bm, (pc.x, pc.y, FAC_Z + h * 0.985), (0.6, 0.6, 0.6), 2)
    return pc, h


def dish(bm, centre, radius, aim):
    """A radar dish: a shallow paraboloid of `radius` at `centre`, opening along `aim`, a feed on struts."""
    q = aim.normalized().to_track_quat('Z', 'Y').to_matrix().to_4x4()
    T = Matrix.Translation(centre) @ q
    prof = [(radius * t, 0.35 * radius * t * t) for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
    rings = lathe(bm, [(max(r, 1e-3), z) for r, z in prof], seg=16, cap_top=False, cap_bottom=False)
    for ring in rings:
        for v in ring:
            v.co = T @ v.co
    feed = T @ Vector((0, 0, radius * 0.55))
    sweep(bm, [T @ Vector((0, 0, 0.1)), feed], circle_profile(radius * 0.05, 4))
    for a in (0, 2.1, 4.2):
        sweep(bm, [T @ Vector((radius * 0.9 * math.cos(a), radius * 0.9 * math.sin(a), 0.3 * radius)), feed],
              circle_profile(radius * 0.02, 4), caps=False)


TAG[0] = None
bm = bmesh.new()
# Perimeter walls, left and right (low, crenellated), and a back wall filling between the buildings.
frng = random.Random(404)
for args in ((515, 650, 238, 250.0, 6.0), (948, 1072, 227, 250.0, 6.0)):
    pcw, ww, hw = fac_block(bm, *args, crenel=True)
    buttresses(bm, pcw, ww, hw, every=6.0, out=1.4)
pcbw, wbw, hbw = fac_block(bm, 640, 960, 236, 265.0, 8.0)
vents(bm, pcbw, wbw, hbw, 8, frng, 0.4, 0.8)
# The bunker walls either side of the gate: stepped back in three tiers, ribbed, slit windows lit along each.
for args in ((600, 712, 222, 200.0, 26.0), (845, 968, 230, 192.0, 26.0)):
    pcs, ws, hs = fac_block(bm, *args, batter=0.55, steps=3)
    vents(bm, Vector((pcs.x + 0.55 * hs * 0.17, pcs.y, pcs.z)), ws, hs, 3, frng, 0.05, 0.25)
# The buildings: the dish house (left), the right block and the long right building with its lit strip.
pcd, wd, hd = fac_block(bm, 706, 782, 192, 205.0, 24.0)
windows(bm, pcd, wd, hd, 3, hd * 0.45, hd * 0.9, 1)
vents(bm, pcd, wd, hd, 3, frng, 0.1, 0.35)
antennas(bm, pcd, wd, hd, 24.0, 4, frng, 3.0)
pcb, wb, hb = fac_block(bm, 838, 882, 200, 208.0, 18.0)
windows(bm, pcb, wb, hb, 4, hb * 0.35, hb * 0.92, 1, cols=3)
antennas(bm, pcb, wb, hb, 18.0, 3, frng, 4.0)
pcl, wl, hl = fac_block(bm, 876, 952, 212, 218.0, 20.0)
windows(bm, pcl, wl, hl, 1, hl * 0.66, hl * 0.66, 2)
windows(bm, pcl, wl, hl, 2, hl * 0.25, hl * 0.5, 1)
antennas(bm, pcl, wl, hl, 20.0, 5, frng, 3.5)
# The central tower behind the gate, a column of windows, a stepped crown.
pct, wt, ht = fac_block(bm, 784, 837, 172, 200.0, 20.0)
windows(bm, pct, wt * 0.4, ht, 9, ht * 0.38, ht * 0.95, 1)
vents(bm, pct, wt, ht, 4, frng, 0.15, 0.35)
add_box(bm, (pct.x - 0.5, pct.y, FAC_Z + ht * 0.36), (1.2, wt + 1.0, 1.0))
# The gate block: two piers and a lintel round the gate's opening, a tunnel through, blast doors at its end.
GATE = BOXES['gate']
gd = 172.0
pg, _ = facade_frame((GATE[0] + GATE[2]) / 2, gd)
g_w = px_to_m(GATE[2] - GATE[0], gd)
g_h = z_of_row((GATE[0] + GATE[2]) / 2, GATE[1], gd) - FAC_Z
blk_w = px_to_m(852 - 705, gd)
blk_h = z_of_row(778, 236, gd) - FAC_Z
pier = (blk_w - g_w) / 2
for side in (1, -1):
    yc = pg.y + side * (g_w / 2 + pier / 2)
    add_box(bm, (pg.x + 9, yc, FAC_Z + blk_h / 2 - 0.5), (18, pier, blk_h + 1))
add_box(bm, (pg.x + 9, pg.y, FAC_Z + g_h + (blk_h - g_h) / 2), (18, g_w + 0.2, blk_h - g_h))
for side in (1, -1):  # the tunnel's walls and roof, on to the doors
    add_box(bm, (pg.x + 18 + 16, pg.y + side * (g_w / 2 + 0.6), FAC_Z + g_h / 2), (32, 1.2, g_h + 0.4))
add_box(bm, (pg.x + 18 + 16, pg.y, FAC_Z + g_h + 0.6), (32, g_w + 2.4, 1.2))
for side in (1, -1):  # the piers' buttresses and a heavy coping over the lintel
    buttresses(bm, Vector((pg.x, pg.y + side * (g_w / 2 + pier * 0.75), FAC_Z)), pier * 0.5, blk_h, every=10.0, out=2.2,
               frac=0.9)
add_box(bm, (pg.x - 0.4, pg.y, FAC_Z + blk_h - 0.5), (1.2, blk_w + 1.0, 1.0))
add_box(bm, (pg.x - 0.3, pg.y, FAC_Z + g_h + 0.2), (0.8, g_w + 1.6, 0.4))
FAC.append((pg, blk_w, 18.0, blk_h))
fac_me = mesh_from('City4.Facility', bm, [MAT['concrete'], MAT['glass'], MAT['led'], MAT['rust']])
box_uvs(fac_me, 0.08)
obj('City4.Facility', fac_me, G['Facility'], ident='facility')
print('gate', [round(v, 1) for v in pg], 'opening', round(g_w, 1), 'x', round(g_h, 1), 'block', round(blk_w, 1), 'x',
      round(blk_h, 1))

# The blast doors deep in the tunnel (dark steel), a light bar over the opening, the insignia on the lintel.
bm = bmesh.new()
add_box(bm, (pg.x + 50.5, pg.y, FAC_Z + g_h / 2), (1.0, g_w, g_h))
add_box(bm, (pg.x + 50.0, pg.y, FAC_Z + g_h * 0.5), (0.4, 0.3, g_h * 0.95), 1)
gate_me = mesh_from('City4.GateDoors', bm, [MAT['rust'], MAT['led']])
box_uvs(gate_me, 0.2)
obj('City4.GateDoors', gate_me, G['Facility'], ident='gate')
# The gate's dark opening (score.py's 'gate' feature): a matte black card just inside the opening.
bm = bmesh.new()
add_quad(bm, [(pg.x + 1.0, pg.y - g_w / 2, FAC_Z), (pg.x + 1.0, pg.y + g_w / 2, FAC_Z),
              (pg.x + 1.0, pg.y + g_w / 2, FAC_Z + g_h), (pg.x + 1.0, pg.y - g_w / 2, FAC_Z + g_h)])
dark = material('City4GateShadow', (0.02, 0.02, 0.018), 1.0, vcol=False)
gsh = obj('City4.GateShadow', mesh_from('City4.GateShadow', bm, dark), G['Facility'], ident='gate')
gsh['note'] = 'the shadow in the gate opening; hide it if the site lights the tunnel'
bm = bmesh.new()
add_box(bm, (pg.x - 0.15, pg.y, FAC_Z + g_h + 0.6), (0.2, g_w * 0.9, 0.35))       # the light bar
for k in range(-3, 4):                                                          # lamps in the opening's jambs
    for side in (1, -1):
        add_box(bm, (pg.x + 3 + abs(k) * 4, pg.y + side * (g_w / 2 - 0.1), FAC_Z + g_h * 0.8), (0.6, 0.15, 0.3))
# The insignia (original): a hexagon standing on its point round a vertical double helix (two strands, four rungs),
# green-lit on the lintel; and a stencilled serial plate, D4, on the left pier.
ic = Vector((pg.x - 0.12, pg.y, FAC_Z + g_h + (blk_h - g_h) * 0.55))
ir = min((blk_h - g_h) * 0.4, g_w * 0.3)
FACE_UP = Vector((1, 0, 0))
hexp = [ic + Vector((0, ir * math.cos(math.radians(90 + 60 * k)), ir * math.sin(math.radians(90 + 60 * k))))
        for k in range(7)]
sweep(bm, hexp, [(0.0, -0.16), (0.0, 0.16), (0.2, 0.16), (0.2, -0.16)], up=FACE_UP)
for ph in (0.0, math.pi):
    strand = [ic + Vector((0, ir * 0.34 * math.sin(ph + 2 * math.pi * 1.75 * t), ir * (0.7 * (2 * t - 1))))
              for t in [i / 24 for i in range(25)]]
    sweep(bm, strand, [(0.0, -0.08), (0.0, 0.08), (0.2, 0.08), (0.2, -0.08)], up=FACE_UP)
for t in (0.07, 0.21, 0.36, 0.5, 0.64, 0.79, 0.93):
    yv = ir * 0.34 * math.sin(2 * math.pi * 1.75 * t)
    if abs(yv) > ir * 0.08:
        add_box(bm, (ic.x - 0.02, ic.y, ic.z + ir * 0.7 * (2 * t - 1)), (0.2, abs(yv) * 2, 0.09))
# The serial plate: a dark steel plate, the code in lit stencil pixels.
plate_c = Vector((pg.x - 0.3, pg.y + g_w / 2 + pier * 0.5, FAC_Z + g_h * 0.62))
code = 'D4'
px_m = 0.5
add_box(bm, (plate_c.x + 0.12, plate_c.y, plate_c.z), (0.15, px_m * (len(code) * 6 + 2), px_m * 10), 1)
for ci, ch in enumerate(code):
    for k, bit in enumerate(FONT[ch]):
        if bit == '1':
            r_, c_ = divmod(k, 5)
            yy = plate_c.y + px_m * (len(code) * 3 - ci * 6 - c_ - 0.5)  # (its front faces -X: +y reads leftward)
            add_box(bm, (plate_c.x, yy, plate_c.z + px_m * (3 - r_)), (0.08, px_m * 0.82, px_m * 0.82))
# Floodlights on the piers and warning lamps along the lintel's top.
for side in (1, -1):
    add_box(bm, (pg.x - 0.5, pg.y + side * (g_w / 2 + pier * 0.5), FAC_Z + blk_h - 1.2), (0.8, 1.6, 0.5))
for k in range(9):
    add_box(bm, (pg.x - 0.1, pg.y - blk_w * 0.42 + blk_w * 0.84 * k / 8, FAC_Z + blk_h + 0.25), (0.3, 0.35, 0.35))
ins_me = mesh_from('City4.Insignia', bm, [MAT['led'], MAT['rust']])
ins = obj('City4.Insignia', ins_me, G['Facility'])
ins['note'] = ('original insignia: a hexagon (on its point) round a vertical double helix; serial plate D4 on the '
               'left pier; the gate\'s lamps')
# Watchtowers, masts, the dish.
bm = bmesh.new()
watchtower(bm, 566, 203, 248.0)
watchtower(bm, 1022, 192, 252.0)
dish_c = screen_point(738, 177, 212.0)
dish(bm, dish_c, px_to_m(18, 212.0), Vector((-0.6, 0.25, 0.75)))
add_box(bm, (dish_c.x + 1.0, dish_c.y, (dish_c.z + FAC_Z + hd) / 2), (1.2, 1.2, max(1.0, dish_c.z - FAC_Z - hd)))
tw_me = mesh_from('City4.FacilityTowers', bm, [MAT['concrete'], MAT['glass'], MAT['led']])
box_uvs(tw_me, 0.15)
obj('City4.FacilityTowers', tw_me, G['Facility'], ident='facility')
for sx, top, depth, base_top in ((680, 165, 225.0, None), (810, 132, 202.0, 172), (829, 137, 206.0, 172)):
    base = ground_at_depth(sx, depth)
    base.z = FAC_Z if base_top is None else z_of_row(sx, base_top, depth)
    h = z_of_row(sx, top, depth) - base.z
    inst('mast', base, (h / 32.0, h / 32.0, h / 32.0), (0, 0, rnd.random()), G['Facility'], ident='facility')


# --- The sky: the sun, the storm wall, lightning ---------------------------------------------------------------------------
SUN_D = 3000.0
sun_f = FEAT['sun']
sun_c = screen_point(sun_f['centre'][0], sun_f['centre'][1], SUN_D)
sun_r = px_to_m(sun_f['radius'], SUN_D)
bm = bmesh.new()
bmesh.ops.create_circle(bm, cap_ends=True, segments=40, radius=sun_r)
sun_o = obj('City4.Sun', mesh_from('City4.Sun', bm, MAT['sun']), G['Sky'], sun_c, ident='sun')
sun_o.rotation_mode = 'QUATERNION'
sun_o.rotation_quaternion = (EYE - sun_c).to_track_quat('Z', 'Y')
sun_o['note'] = 'the sun disc, fitted to the arrival frame; the noon light comes from high above it (SUN_LIGHT_DIR)'
# The light: from the sun's bearing, but high (harsh noon): elevation 58 deg.
_sb = (sun_c - EYE)
SUN_AZ = math.atan2(_sb.y, _sb.x)
SUN_EL = math.radians(68.0)
SUN_LIGHT_DIR = Vector((math.cos(SUN_EL) * math.cos(SUN_AZ), math.cos(SUN_EL) * math.sin(SUN_AZ), math.sin(SUN_EL)))
sun_o['SUN_LIGHT_DIR'] = [round(v, 4) for v in SUN_LIGHT_DIR]

STORM_EDGE = FEAT['storm_edge']['points']
_edge_x = [p[0] for p in STORM_EDGE]
_edge_y = [p[1] for p in STORM_EDGE]


def storm_top_row(sx):
    """The storm's top in the arrival frame at column sx: the traced edge where it shows, else well above the frame."""
    if sx < _edge_x[0]:
        return None
    if sx <= _edge_x[-1]:
        return float(np.interp(sx, _edge_x, _edge_y))
    return max(-160.0, _edge_y[-1] - 0.8 * (sx - _edge_x[-1]))  # rising on at the edge's slope (no step)


def bearing_dir(b):
    return Vector((math.cos(b), math.sin(b), 0))


def column_bearing(sx):
    d = screen_point(sx, 300, 1.0) - EYE
    return math.atan2(d.y, d.x)


STORM_FRINGE_H = 110.0      # the billows' height over each band's top (m): tex_storm's fringe rows at ~0.96 m/px
STORM_TILE = 490.0          # metres of arc per texture repeat (the same ~0.96 m/px across)


def storm_layer(name, R, row_drop, bottom=-60.0, fringe=0.55, haze=False, ident='storm', far_right=-1.35,
                left_col=440.0):
    """A band of storm billboards on an arc of radius R round the arrival eye: from screen column left_col round to
    bearing far_right (beyond the frame's right, for the approach), its top on the storm's edge (row_drop px lower)."""
    b0 = column_bearing(left_col) + (math.radians(12) if not haze else 0.0)
    b_edge = column_bearing(left_col)
    bs = []
    b = b0
    while b > far_right:
        bs.append(b)
        b -= math.radians(1.2)
    bs.append(far_right)
    body = bmesh.new()
    fr = bmesh.new()
    uvb = body.loops.layers.uv.new('UVMap')
    uvf = fr.loops.layers.uv.new('UVMap')
    cols = []
    for b in bs:
        P = EYE + bearing_dir(b) * R
        P.z = 0
        sp, d = to_screen(Vector((P.x, P.y, EYE.z)))
        sx = sp.x
        row = storm_top_row(sx) if 0 <= sx <= RES[0] else -160.0
        if row is None:
            row = 300.0
        z_top = z_of_row(sx, row + row_drop, d) if 0 <= sx <= RES[0] else z_of_row(RES[0], -160 + row_drop, d)
        if sx > RES[0]:  # beyond the frame: keep rising gently
            z_top = max(z_top, 0.0) * (1.0 + 0.1 * (column_bearing(RES[0]) - b))
        if b > b_edge:  # left of where the arrival frame sees it end: tapering down to the dunes
            P_e = EYE + bearing_dir(b_edge) * R
            sp_e, d_e = to_screen(Vector((P_e.x, P_e.y, EYE.z)))
            z_e = z_of_row(sp_e.x, storm_top_row(_edge_x[0]) + row_drop, d_e)
            z_top = z_e * (1 - smoothstep(0.0, 1.0, (b - b_edge) / (b0 - b_edge))) - 40.0 * \
                smoothstep(0.0, 1.0, (b - b_edge) / (b0 - b_edge))
        z_top = max(z_top, 12.0 if b <= b_edge else -30.0)
        cols.append((P, z_top, R * (b0 - b)))
    for (P0, z0, u0), (P1, z1, u1) in zip(cols, cols[1:]):
        if haze:
            vs = [Vector((P0.x, P0.y, bottom)), Vector((P1.x, P1.y, bottom)), Vector((P1.x, P1.y, z1)),
                  Vector((P0.x, P0.y, z0))]
            f = body.faces.new([body.verts.new(v) for v in vs])
            for lp, (u, v) in zip(f.loops, ((u0, 0.62), (u1, 0.62), (u1, 0.97), (u0, 0.97))):
                lp[uvb].uv = (u / STORM_TILE, 0.5 + 0.5 * v)
            continue
        vs = [Vector((P0.x, P0.y, bottom)), Vector((P1.x, P1.y, bottom)), Vector((P1.x, P1.y, z1)),
              Vector((P0.x, P0.y, z0))]
        f = body.faces.new([body.verts.new(v) for v in vs])
        for lp, (u, v) in zip(f.loops, ((u0, 0.0), (u1, 0.0), (u1, fringe), (u0, fringe))):
            lp[uvb].uv = (u / STORM_TILE, 0.5 + 0.5 * v)
        h0 = h1 = STORM_FRINGE_H * R / 1500.0
        vs = [Vector((P0.x, P0.y, z0)), Vector((P1.x, P1.y, z1)), Vector((P1.x, P1.y, z1 + h1)),
              Vector((P0.x, P0.y, z0 + h0))]
        f = fr.faces.new([fr.verts.new(v) for v in vs])
        for lp, (u, v) in zip(f.loops, ((u0, fringe), (u1, fringe), (u1, 1.0), (u0, 1.0))):
            lp[uvf].uv = (u / STORM_TILE, 0.5 + 0.5 * v)
    o = obj(f'City4.{name}', mesh_from(f'City4.{name}', body, MAT['storm'], recalc=False), G['Storm'], ident=ident)
    if not haze:
        of = obj(f'City4.{name}Fringe', mesh_from(f'City4.{name}Fringe', fr, MAT['storm'], recalc=False), G['Storm'])
        of['ids_hide'] = 1
    else:
        fr.free()
    return o


storm_layer('StormFront', 1500.0, 12.0)
storm_layer('StormMid', 1850.0, 26.0)
storm_layer('StormBack', 2300.0, 40.0)
hz = storm_layer('DustHaze', 760.0, 0.0, bottom=-20.0, haze=True, ident=None, left_col=-400.0, far_right=-1.9)
hz['ids_hide'] = 1


def puff_card(bm, uvl, c, wdt, hgt, flip=False):
    """A puff card (the texture's lower half), its centre c, facing the arrival eye across the ground."""
    n = Vector((EYE.x - c.x, EYE.y - c.y, 0)).normalized()
    side = Vector((-n.y, n.x, 0)) * (wdt / 2)
    up = Vector((0, 0, hgt / 2))
    f = bm.faces.new([bm.verts.new(c + side - up), bm.verts.new(c - side - up), bm.verts.new(c - side + up),
                      bm.verts.new(c + side + up)])
    us = (1.0, 0.0) if flip else (0.0, 1.0)
    for lp, uv in zip(f.loops, ((us[0], 0.0), (us[1], 0.0), (us[1], 0.5), (us[0], 0.5))):
        lp[uvl].uv = uv


def puff_mesh(name, cards):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    for c, wdt, hgt, flip in cards:
        puff_card(bm, uvl, c, wdt, hgt, flip)
    o = obj(f'City4.{name}', mesh_from(f'City4.{name}', bm, MAT['storm'], recalc=False), G['Storm'])
    o['ids_hide'] = 1
    return o


prng = random.Random(512)
b_edge_col = column_bearing(_edge_x[0])
# 1. Along the wall's edge where it meets the clear sky (concept x 445-760): puffs whose soft tops roll just over it.
edge_cards = []
for sx in frange(450.0, 1000.0, 34.0):
    R = prng.uniform(1380, 1470)
    P = EYE + bearing_dir(column_bearing(sx)) * R
    sp, d = to_screen(Vector((P.x, P.y, EYE.z)))
    hgt = prng.uniform(260, 420)
    wdt = hgt * prng.uniform(1.3, 1.9)
    left = max(_edge_x[0], sx - px_to_m_inv(wdt * 0.35, d))  # where its soft shoulder reaches
    row = storm_top_row(left) if sx <= _edge_x[-1] + 120 else prng.uniform(-60, 40)
    top = z_of_row(sp.x, row - prng.uniform(2, 10), d) + hgt * 0.12
    edge_cards.append((Vector((P.x, P.y, top - hgt / 2)), wdt, hgt, prng.random() < 0.5))
# 2. Over the body: rolling masses in front of the wall, below its edge.
for k in range(22):
    sx = prng.uniform(520, 1500)
    R = prng.uniform(1250, 1450)
    P = EYE + bearing_dir(column_bearing(sx)) * R
    sp, d = to_screen(Vector((P.x, P.y, EYE.z)))
    edge_row = storm_top_row(sx) if sx <= _edge_x[-1] else -100.0
    lo_row = max(edge_row + 40, 60)
    row = prng.uniform(lo_row, 285)
    hgt = prng.uniform(200, 380)
    zc = z_of_row(min(sp.x, RES[0]), row, d)
    edge_cards.append((Vector((P.x, P.y, zc)), hgt * prng.uniform(1.4, 2.0), hgt, prng.random() < 0.5))
# 3. Above the frame (only the approach sees the wall's top there): a rolling crest instead of a straight top.
for b in frange(-1.35, column_bearing(760), 0.05):
    P = EYE + bearing_dir(b) * prng.uniform(1480, 1560)
    hgt = prng.uniform(300, 520)
    ztop = 700.0 + 90 * math.sin(b * 9) + prng.uniform(-60, 60)
    sp, d = to_screen(Vector((P.x, P.y, ztop - hgt * 0.3)))
    if 0 <= sp.x <= RES[0] and sp.y > -10:
        continue  # would show in the arrival frame
    edge_cards.append((Vector((P.x, P.y, ztop - hgt * 0.3)), hgt * 1.6, hgt, prng.random() < 0.5))
puff_mesh('StormPuffs', edge_cards)
# 4. The ends, tapering off into the haze: left of where the arrival sees the wall end (kept under row ~272 in its
#    frame), and round past its right.
tail_cards = []
for t in frange(0.0, 1.0, 0.05):
    b = b_edge_col + math.radians(4 + 44 * t)
    P = EYE + bearing_dir(b) * prng.uniform(1450, 1750)
    sp, d = to_screen(Vector((P.x, P.y, EYE.z)))
    hgt = max(0.0, 1 - t) ** 1.2 * prng.uniform(200, 320) + 40
    if sp.x >= -50 and d > 0:
        top = min(z_of_row(max(sp.x, 0.0), 272, d), hgt * 0.9)
    else:
        top = hgt * 0.9
    if top < 15:
        continue
    tail_cards.append((Vector((P.x, P.y, top - hgt * 0.45)), hgt * prng.uniform(1.6, 2.4), hgt, prng.random() < 0.5))
for t in frange(0.0, 1.0, 0.1):
    b = -1.35 - math.radians(3 + 25 * t)
    P = EYE + bearing_dir(b) * prng.uniform(1450, 1650)
    hgt = max(0.0, 1 - t) * 520 + 80
    tail_cards.append((Vector((P.x, P.y, hgt * 0.4)), hgt * 1.8, hgt, prng.random() < 0.5))
puff_mesh('StormEnds', tail_cards)
print('storm puffs', len(edge_cards), '+', len(tail_cards))
# The haze's top: only ~45 m.
for v in hz.data.vertices:
    if v.co.z > 0:
        v.co.z = 46.0 + 14.0 * math.sin(v.co.x * 0.01 + v.co.y * 0.013)


def bolt(bm, pts, width, branches=2, rng=None):
    rng = rng or random.Random(3)
    path = []
    for a, b in zip(pts, pts[1:]):
        for k in range(3):
            t = k / 3
            j = (b - a).length * 0.06
            path.append(a.lerp(b, t) + Vector((rng.uniform(-j, j), rng.uniform(-j, j), 0)))
    path.append(pts[-1])
    view = (EYE - path[0]).normalized()
    for a, b in zip(path, path[1:]):
        side = (b - a).cross(view).normalized() * width / 2
        add_quad(bm, [a - side, b - side * 0.8, b + side * 0.8, a + side])
    for _ in range(branches):
        i = rng.randrange(1, len(path) - 2)
        a = path[i]
        d = (path[i + 1] - path[i])
        b = a + Matrix.Rotation(rng.uniform(0.5, 0.9) * rng.choice((-1, 1)), 3, view) @ d * rng.uniform(1.2, 2.0)
        side = (b - a).cross(view).normalized() * width * 0.3
        add_quad(bm, [a - side, b, b, a + side])


bm = bmesh.new()
for k, guide in enumerate(FEAT['lightning']):
    d = 1420.0
    bolt(bm, [screen_point(x, y, d) for x, y in guide], px_to_m(3.0, d), rng=random.Random(k))
lt = obj('City4.Lightning', mesh_from('City4.Lightning', bm, MAT['lightning'], recalc=False), G['Storm'],
         ident='lightning')
lt['note'] = 'the arrival frame\'s two bolts; the site flashes City4Lightning'
bm = bmesh.new()
for k, b in enumerate((-0.62, -0.8, -1.0, -1.2)):  # more, round to the right (the approach sees them)
    top = EYE + bearing_dir(b) * 1450
    top.z = 420 + 80 * k
    pts = [top + Vector((0, 0, -60 * i)) + bearing_dir(b + 1.57) * random.Random(k * 7 + i).uniform(-25, 25)
           for i in range(6)]
    bolt(bm, pts, 5.0, 3, random.Random(k + 10))
lt2 = obj('City4.LightningFar', mesh_from('City4.LightningFar', bm, MAT['lightning'], recalc=False), G['Storm'])


# =========================================================================================================================
# The dunes: a height field round the road (finer under the arrival), and a coarse far floor out to the storm.
# =========================================================================================================================
def hash2(ix, iy, seed):
    h = np.sin(ix * 127.1 + iy * 311.7 + seed * 74.7) * 43758.5453
    return h - np.floor(h)


def vnoise2(x, y, seed):
    ix, iy = np.floor(x), np.floor(y)
    fx, fy = x - ix, y - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = hash2(ix, iy, seed), hash2(ix + 1, iy, seed)
    c, d = hash2(ix, iy + 1, seed), hash2(ix + 1, iy + 1, seed)
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm2(x, y, seed, octaves=4):
    out, amp, tot, f = 0.0, 1.0, 0.0, 1.0
    for o in range(octaves):
        out = out + amp * vnoise2(x * f, y * f, seed + o)
        tot += amp
        amp *= 0.5
        f *= 2.03
    return out / tot


def dune_field(x, y):
    """0..1: transverse dune ridges across the wind (the storm blows from +X): long gentle windward slopes, short
    steep slip faces, their crests warped and broken by noise; broad swells and small dunes over them."""
    warp = 70 * (fbm2(x / 320, y / 320, 3, 3) - 0.5) + 0.18 * y
    phase = (x + warp) / 140.0 + 0.6 * fbm2(x / 900 + 3, y / 900, 4, 2)
    t = phase - np.floor(phase)
    ridge = np.where(t < 0.78, smoothstep(0.0, 0.78, t), 1 - smoothstep(0.78, 1.0, t))
    crest = 0.5 + 0.5 * smoothstep(0.3, 0.7, fbm2(x / 260, y / 180, 5, 3))  # crests break up along their length
    big = fbm2(x / 900, y / 900, 7, 2)
    small = fbm2(x / 55, y / 80, 8, 2)
    return 0.72 * ridge * crest + 0.16 * big + 0.12 * small


def road_coords_many(X, Y):
    S, L = np.zeros(len(X)), np.zeros(len(X))
    for i, (x, y) in enumerate(zip(X, Y)):
        S[i], L[i] = road_coords(float(x), float(y))
    return S, L


def terrain_h(X, Y):
    X, Y = np.asarray(X, float), np.asarray(Y, float)
    S, L = road_coords_many(X, Y)
    d = np.abs(L)
    amp = smoothstep(9.0, 32.0, d) * (11.0 + 26.0 * smoothstep(30.0, 450.0, d))
    h = -0.15 + 0.5 * np.exp(-((d - 8.6) / 2.0) ** 2) + amp * dune_field(X, Y)
    # Zone 3's side: left of the first ~420 m stays low and flat (its city stands there).
    w3 = (L > 0) * (1 - smoothstep(380.0, 470.0, S)) * smoothstep(6.8, 10.0, d)
    h = h * (1 - w3) - 1.2 * w3
    # The very start (x near 0) eases down to meet the zone before.
    h = h * smoothstep(0.0, 60.0, X) - 0.6 * (1 - smoothstep(0.0, 60.0, X))
    # The arrival's corridor: the road ahead to the facility stays low, its compound flat.
    xr, yr = X - X_CAM, Y - Y_F
    corridor = smoothstep(-20.0, 10.0, xr) * (1 - smoothstep(60.0, 110.0, np.abs(yr) - 0.25 * np.maximum(xr, 0)))
    h = h * (1 - 0.75 * corridor)
    # Wind ripples near the road: low sand waves 26 m apart either side of it, fading out by ~150 m.
    rip_w = smoothstep(7.5, 13.0, d) * (1 - smoothstep(70.0, 150.0, d)) * (1 - 0.45 * corridor)
    rip = (0.5 + 0.5 * np.sin(2 * np.pi * ((X * 0.85 + Y * 0.35) / 26.0 + 2.5 * fbm2(X / 90, Y / 90, 11, 2)))) ** 2
    h = h + rip_w * 0.95 * rip * (0.6 + 0.4 * fbm2(X / 40, Y / 40, 12, 2))
    comp = smoothstep(130.0, 150.0, xr) * (1 - smoothstep(300.0, 330.0, xr)) * (1 - smoothstep(85.0, 110.0, np.abs(yr)))
    h = h * (1 - comp) + (FAC_Z - 0.15) * comp
    for (mx, my, r, z) in MOUNDS:
        dist = np.hypot(X - mx, Y - my)
        w = smoothstep(r, r * 0.35, dist)
        h = h * (1 - w) + (z + 0.5 * (1 - dist / r).clip(0, 1)) * w
    return h


# --- The approach, planned before the dunes are made (its monoliths and the toppled tower heap sand round them) ----------
GANTRY_S = (820.0, 2050.0)
TOPPLED_S = 1380.0
PLANNED = []   # (kind, pos (base), yaw, scale, tilt, tag)
FOOT = []      # (x, y, r): footprints taken
for key, (kind, pos, yaw, sc, tilt) in COMPOSED.items():
    FOOT.append((pos.x, pos.y, max(DIMS[kind][0], DIMS[kind][1]) * sc[0] * 0.7 + 4))


def foot_free(x, y, r):
    return all(math.hypot(x - fx, y - fy) > r + fr + 8 for fx, fy, fr in FOOT)


def base_dune(x, y):
    return float(terrain_h(np.array([x]), np.array([y]))[0])


def plan_monolith(kind, x, y, scale, yaw, tilt, tag, sink_k=0.12):
    W, D, Hh = DIMS[kind]
    zb = base_dune(x, y)
    sink = sink_k * Hh * scale
    MOUNDS.append((x, y, max(W, D) * scale * 0.8 + 9.0, zb + 0.5 * scale))
    FOOT.append((x, y, max(W, D) * scale * 0.7))
    PLANNED.append((kind, Vector((x, y, zb + 0.5 * scale - sink)), yaw, scale, tilt, tag))


# The toppled tower: a tower module 2.6x as long, fallen across the road at 55 deg, its fans facing down onto the road,
# its ends on dunes either side; the road passes ~9 m under it.
_tp, _tt, _tn = road_frame(TOPPLED_S)
TOPPLED_DIR = (Matrix.Rotation(math.radians(55), 3, 'Z') @ _tt).normalized()
TOPPLED_SC = (1.6, 1.6, 2.6)
_tlen = DIMS['tower'][2] * TOPPLED_SC[2]
_tz = 14.0
TOPPLED_BASE = Vector((_tp.x, _tp.y, _tz)) - TOPPLED_DIR * (_tlen * 0.45)
TOPPLED_BASE.z = _tz - math.sin(math.radians(6)) * _tlen * 0.45
for t, zz in ((0.1, 8.0), (0.92, 11.5)):
    e = TOPPLED_BASE + TOPPLED_DIR * (_tlen * t)
    MOUNDS.append((e.x, e.y, 34.0, zz))
    FOOT.append((e.x, e.y, 22.0))
FOOT.append((_tp.x, _tp.y, 30.0))
for gs in GANTRY_S:
    gp, _, _ = road_frame(gs)
    FOOT.append((gp.x, gp.y, 16.0))

# The hero server close on the right at the start (concept-transition-desert's: fans and a terminal, leaning).
_hp = along(176.0, -25.0)
plan_monolith('fanwall', _hp.x, _hp.y, 1.45, face_yaw((APP_EYE - _hp).normalized()) - math.radians(8),
              (math.radians(-5), math.radians(5)), 'hero', sink_k=0.02)
# Server fields: clusters every ~70 m, either side (not the left of the first 450 m), 26-200 m off the road.
for s in frange(60.0, S_CAM - 40.0, 70.0):
    for side in (-1, 1):
        if side > 0 and s < 470:
            continue
        if rnd.random() > 0.78:
            continue
        n = rnd.choice((1, 2, 2, 3, 3, 4))
        for _ in range(n):
            for _try in range(20):
                ss = s + rnd.uniform(-40, 40)
                lat = side * rnd.uniform(26, 200)
                kind = rnd.choices(('tower', 'slab', 'fanwall'), (0.35, 0.4, 0.25))[0]
                scale = rnd.uniform(0.45, 1.3) * (1.0 + 0.004 * max(0.0, abs(lat) - 60))
                W, D, Hh = DIMS[kind]
                r = max(W, D) * scale * 0.7
                if abs(lat) < ROAD_W / 2 + 18 + r:
                    continue
                p = along(ss, lat)
                if p.x < 20 or p.x > X_CAM - 20 or not foot_free(p.x, p.y, r):
                    continue
                to_road = (along(ss, 0) - p).normalized()
                yaw = face_yaw((Matrix.Rotation(rnd.uniform(-0.9, 0.9), 3, 'Z') @ to_road).normalized())
                tilt = (math.radians(rnd.uniform(-9, 9)), math.radians(rnd.uniform(-9, 9)))
                plan_monolith(kind, p.x, p.y, scale, yaw, tilt, f'field{int(s)}')
                break
# Close by the road: half-buried, leaning monoliths every ~46 m, alternating sides, 15-45 m off the deck, so the ride
# threads between them.
side = -1
for s in frange(90.0, S_CAM - 45.0, 46.0):
    side = -side if rnd.random() < 0.75 else side
    sd = side if not (side > 0 and s < 480) else -1
    if rnd.random() > 0.8:
        continue
    for _try in range(15):
        kind = rnd.choices(('tower', 'slab', 'fanwall'), (0.4, 0.35, 0.25))[0]
        scale = rnd.uniform(0.4, 0.85)
        W, D, Hh = DIMS[kind]
        r = max(W, D) * scale * 0.7
        lat = sd * (ROAD_W / 2 + rnd.uniform(9.0, 30.0) + r)
        ss = s + rnd.uniform(-12, 12)
        p = along(ss, lat)
        if p.x < 20 or p.x > X_CAM - 25 or not foot_free(p.x, p.y, r):
            continue
        to_road = (along(ss, 0) - p).normalized()
        yaw = face_yaw((Matrix.Rotation(rnd.uniform(-1.0, 1.0), 3, 'Z') @ to_road).normalized())
        tilt = (math.radians(rnd.uniform(-16, 16)), math.radians(rnd.uniform(-16, 16)))
        plan_monolith(kind, p.x, p.y, scale, yaw, tilt, f'near{int(s)}', sink_k=rnd.uniform(0.28, 0.5))
        break
# Far silhouettes: big ones out in the dunes, 280-900 m off the road.
for k in range(44):
    for _try in range(30):
        ss = rnd.uniform(0, S_CAM - 60)
        side = rnd.choice((-1, 1))
        if side > 0 and ss < 520:
            side = -1
        lat = side * rnd.uniform(280, 900)
        p = along(ss, lat)
        kind = rnd.choice(('tower', 'slab', 'slab', 'fanwall'))
        scale = rnd.uniform(1.4, 2.6)
        r = max(DIMS[kind][0], DIMS[kind][1]) * scale * 0.7
        if p.x < 40 or p.x > X_CAM - 40 or not foot_free(p.x, p.y, r):
            continue
        tilt = (math.radians(rnd.uniform(-12, 12)), math.radians(rnd.uniform(-12, 12)))
        plan_monolith(kind, p.x, p.y, scale, rnd.uniform(0, 6.28), tilt, f'far{k}', sink_k=0.2)
        break
print('planned monoliths', len(PLANNED))


TAG[0] = None
X_MAX = DECK_END_X + 420.0
BAND = 380.0
TILE = 260.0


def grid_mesh(name, x0, x1, y0, y1, step, keep, parent, ident=None, sink=None):
    nx, ny = int(round((x1 - x0) / step)) + 1, int(round((y1 - y0) / step)) + 1
    xs, ys = np.linspace(x0, x1, nx), np.linspace(y0, y1, ny)
    GX, GY = np.meshgrid(xs, ys)
    GX, GY = GX.ravel(), GY.ravel()
    k = keep(GX, GY)
    if not k.any():
        return None
    Z = np.full(len(GX), np.nan)
    Z[k] = terrain_h(GX[k], GY[k])
    if sink is not None:
        Z[k] -= sink(GX[k], GY[k])
    bm = bmesh.new()
    vid = {}
    for i in np.nonzero(k)[0]:
        vid[i] = bm.verts.new((GX[i], GY[i], Z[i]))
    for j in range(ny - 1):
        for i in range(nx - 1):
            a, b, c, d = j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i
            if a in vid and b in vid and c in vid and d in vid:
                bm.faces.new((vid[a], vid[b], vid[c], vid[d]))
    if not bm.faces:
        bm.free()
        return None
    me = mesh_from(name, bm, MAT['sand'], smooth=True, recalc=False)
    for poly in me.polygons:
        if poly.normal.z < 0:
            poly.flip()
    planar_uvs(me, 1 / 8.0)
    return obj(name, me, parent, ident=ident)


# The arrival's own patch: 3 m cells from just behind the camera to past the facility.
AR_X0, AR_X1 = X_CAM - 24.0, X_CAM + 336.0
AR_Y0, AR_Y1 = Y_F - 168.0, Y_F + 168.0


def in_arrival(X, Y):
    return (X >= AR_X0) & (X <= AR_X1) & (Y >= AR_Y0) & (Y <= AR_Y1)


def off_deck(X, Y, margin=0.0):
    S, L = road_coords_many(X, Y)
    return np.abs(L) > ROAD_W / 2 - 1.0 - margin


xs_line = np.array([p.x for p in DECK_LINE])
ys_line = np.array([p.y for p in DECK_LINE])
terrain_objs = []
for tx in frange(0.0, X_MAX - 1, TILE):
    near = (xs_line > tx - BAND) & (xs_line < tx + TILE + BAND)
    ty0, ty1 = ys_line[near].min() - BAND, ys_line[near].max() + BAND
    ty0, ty1 = math.floor(ty0 / 8) * 8, math.ceil(ty1 / 8) * 8

    def keep(X, Y, tx=tx):
        S, L = road_coords_many(X, Y)
        cell = (X >= tx - 1e-6) & (X <= tx + TILE + 1e-6) & (X >= 0)
        inside_ar = (X > AR_X0 + 8) & (X < AR_X1 - 8) & (Y > AR_Y0 + 8) & (Y < AR_Y1 - 8)
        return cell & (np.abs(L) < BAND) & ~inside_ar
    o = grid_mesh(f'City4.Dunes.{int(tx // TILE):02d}', tx, tx + TILE, ty0, ty1, 8.0, keep, G['Dunes'])
    if o:
        terrain_objs.append(o)
for k, (ax0, ax1) in enumerate(((AR_X0, AR_X0 + 180.0), (AR_X0 + 180.0, AR_X1))):
    o = grid_mesh(f'City4.Dunes.Arrival{k}', ax0, ax1, AR_Y0, AR_Y1, 3.0, lambda X, Y: np.ones(len(X), bool),
                  G['Dunes'], ident='ground')
    terrain_objs.append(o)
# The far floor: 80 m cells, out to the storm, sunk where the band covers it.
FAR_X1 = X_CAM + 2200.0
FAR_Y = 3200.0


def far_keep(X, Y):
    return X >= 0


def far_sink(X, Y):
    S, L = road_coords_many(X, Y)
    return 3.0 * (1 - smoothstep(BAND - 60, BAND + 40, np.abs(L)))


for k, fx in enumerate(frange(0.0, FAR_X1 - 1, 1040.0)):
    o = grid_mesh(f'City4.DunesFar.{k:02d}', fx, min(fx + 1040.0, FAR_X1), Y_F - FAR_Y, Y_F + FAR_Y, 80.0, far_keep,
                  G['Dunes'], sink=far_sink)
    if o:
        terrain_objs.append(o)
print('terrain objects', len(terrain_objs), 'tris', sum(len(o.data.polygons) * 2 for o in terrain_objs))


# =========================================================================================================================
# The deck (cracked asphalt, its texture's v along the road), drifts over it, the barriers.
# =========================================================================================================================
def deck_piece(pts, s0, name):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    across = [-ROAD_W / 2, -ROAD_W / 4, 0.0, ROAD_W / 4, ROAD_W / 2]
    rows = []
    s = s0
    for i, p in enumerate(pts):
        if i:
            s += (p - pts[i - 1]).length
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        n = Vector((-t.y, t.x, 0))
        top = [bm.verts.new(p + n * a) for a in across]
        lo = [bm.verts.new(p + n * across[0] + Vector((0, 0, -0.6))), bm.verts.new(p + n * across[-1] + Vector((0, 0, -0.6)))]
        rows.append((top, lo, s))
    for (ta, la, sa), (tb, lb, sb) in zip(rows, rows[1:]):
        for k in range(len(across) - 1):
            f = bm.faces.new((ta[k], tb[k], tb[k + 1], ta[k + 1]))
            for lp, (u, v) in zip(f.loops, ((k / 4, sa), (k / 4, sb), ((k + 1) / 4, sb), ((k + 1) / 4, sa))):
                lp[uvl].uv = (1 - u, v / 27.0)
        for side, (ti, li) in enumerate(((0, 0), (len(across) - 1, 1))):
            f = bm.faces.new((ta[ti], la[li], lb[li], tb[ti]))
            for lp, (u, v) in zip(f.loops, ((0.0, sa), (0.05, sa), (0.05, sb), (0.0, sb))):
                lp[uvl].uv = (u, v / 27.0)
    me = mesh_from(name, bm, MAT['asphalt'], recalc=False)
    for poly in me.polygons:
        c = poly.center
        if abs(poly.normal.z) > 0.5 and poly.normal.z < 0:
            poly.flip()
    return obj(name, me, G['Road'])


TAG[0] = None
_k, _s0 = 0, 0.0
_step_pts = DECK_LINE
for i0 in range(0, len(_step_pts) - 1, 65):  # 65 x 4 m = 260 m pieces
    piece = _step_pts[i0:i0 + 66]
    deck_piece(piece, _DS[i0], f'City4.Deck.{_k:02d}')
    _k += 1


def drift(bm, s0, s1, l0, l1, hmax, seed, ns=None, nl=None, skew=0.0):
    """A thin drift of sand over the deck: a smooth heap between s0-s1 along and l0-l1 across (left +), ragged."""
    r = random.Random(seed)
    ns = ns or max(4, int((s1 - s0) / 2.0))
    nl = nl or max(3, int(abs(l1 - l0) / 1.0))
    grid = {}
    reach = [0.5 + 0.5 * (0.5 + 0.5 * math.sin(i * 0.9 + r.random() * 6) * math.sin(i * 0.37 + 1.3)) for i in
             range(ns + 1)]
    for i in range(ns + 1):
        for j in range(nl + 1):
            u, v = i / ns, j / nl
            shape = math.sin(math.pi * u) ** 0.6 * max(0.0, 1 - v / reach[i]) ** 1.2 * (0.65 + 0.7 * r.random())
            s = s0 + (s1 - s0) * u + skew * v * (s1 - s0)
            lat = l0 + (l1 - l0) * v
            p = along(s, lat)
            p.z = 0.02 + hmax * max(0.0, shape)
            grid[i, j] = (p, shape)
    vs = {k: bm.verts.new(p) for k, (p, sh) in grid.items()}
    for i in range(ns):
        for j in range(nl):
            if max(grid[i, j][1], grid[i + 1, j][1], grid[i, j + 1][1], grid[i + 1, j + 1][1]) < 0.12:
                continue
            bm.faces.new((vs[i, j], vs[i + 1, j], vs[i + 1, j + 1], vs[i, j + 1]))


# Drifts every so often down the road, from one side or the other (the bike line stays clear: at most 1.5 m from the
# centre); heavier toward the facility. The arrival's left lane is under a big one, the CRTs lying in it.
drift_cells = {}
for k, s in enumerate(frange(90.0, S_CAM - 60, 55.0)):
    if rnd.random() < 0.55:
        side = rnd.choice((-1, 1))
        L = rnd.uniform(10, 34)
        reach = rnd.uniform(2.5, 4.4)
        drift_cells.setdefault(int(along(s, 0).x // TILE), []).append(
            (s, s + L, side * (ROAD_W / 2 + 0.3), side * (ROAD_W / 2 - reach), rnd.uniform(0.04, 0.09), k,
             rnd.uniform(-0.3, 0.3)))
for (s0, s1, l0, l1, hm) in ((S_CAM - 30, S_CAM + 34, ROAD_W / 2 + 0.3, 1.6, 0.16),
                              (S_CAM + 20, S_CAM + 95, ROAD_W / 2 + 0.3, 2.2, 0.12),
                              (S_CAM + 2, S_CAM + 40, -ROAD_W / 2 - 0.3, -3.6, 0.10),
                              (S_CAM + 60, S_CAM + 130, -ROAD_W / 2 - 0.3, -2.6, 0.09)):
    drift_cells.setdefault(int(along(s0, 0).x // TILE), []).append((s0, s1, l0, l1, hm, int(s0), 0.1))
for cell, lst in drift_cells.items():
    bm = bmesh.new()
    for (s0, s1, l0, l1, hm, seed, skew) in lst:
        drift(bm, s0, s1, l0, l1, hm, seed, skew=skew)
    me = mesh_from(f'City4.Drifts.{cell:02d}', bm, MAT['sand'], smooth=True, recalc=False)
    for poly in me.polygons:
        if poly.normal.z < 0:
            poly.flip()
    planar_uvs(me, 1 / 8.0)
    obj(f'City4.Drifts.{cell:02d}', me, G['Drifts'])

# Beds for the arrival's CRTs where they lie above the deck (heaps of sand under them).
bm = bmesh.new()
for key in ('CRT_L', 'CRT_M', 'CRT_R', 'CRT_R2'):
    kind, pos, yaw, sc, _ = COMPOSED[key]
    if pos.z > 0.03:
        r = sc[0] * 0.9
        lathe(bm, [(r * 1.9, -0.05), (r * 1.2, pos.z * 0.75), (r * 0.6, pos.z + 0.02), (0.0, pos.z + 0.05)], seg=14,
              cx=pos.x, cy=pos.y, cap_bottom=False)
me = mesh_from('City4.CrtBeds', bm, MAT['sand'], smooth=True)
planar_uvs(me, 1 / 8.0)
obj('City4.CrtBeds', me, G['Drifts'])

# Barriers: 6 m blocks along both edges (the right from 150 m in, the left once zone 3's city is behind, at 440 m),
# a few missing or knocked askew; unbroken through the arrival; stopping short of the facility's apron.
S_BAR_END = S_CAM + 150.0
CRT_GAPS = []
for side, s_start in ((-1, 150.0), (1, 440.0)):
    for s in frange(s_start, S_BAR_END, 6.15):
        if any(abs(s - g) < 12 for g in GANTRY_S) or abs(s - TOPPLED_S) < 10:
            continue
        arrival = s > S_CAM - 40
        if not arrival and rnd.random() < 0.1:
            continue
        p, t, n = road_frame(s)
        lat = side * (BARRIER_Y + 0.1)
        pos = Vector((p.x + n.x * lat, p.y + n.y * lat, 0.0))
        yaw = math.atan2(t.y, t.x) + (0.0 if side > 0 else math.pi)
        tilt = (0.0, 0.0)
        if not arrival and rnd.random() < 0.06:
            yaw += rnd.uniform(-0.35, 0.35)
            tilt = (side * rnd.uniform(0.1, 0.4), 0.0)
        inst('barrier', pos, 1.0, (tilt[0], tilt[1], yaw), G['Barriers'])


# =========================================================================================================================
# The approach: the server fields, gantries, the toppled tower, CRTs, cables.
# =========================================================================================================================
for kind, pos, yaw, scale, tilt, tag in PLANNED:
    TAG[0] = 'behind' if pos.x < X_CAM - 3 else None
    place_monolith(kind, pos, yaw, scale, tilt)
TAG[0] = 'behind'
# The toppled tower.
_e1 = Vector((0, 0, 1)).cross(TOPPLED_DIR).normalized()
_rotm = Matrix((_e1, Vector((0, 0, 1)), TOPPLED_DIR)).transposed()  # columns: local X, Y, Z in world
_tilt = Matrix.Rotation(math.radians(-6), 3, _e1)  # (the far end up)
_rotm = _tilt @ _rotm
_up = _rotm @ Vector((0, 1, 0))
if _up.z < 0:
    _rotm = _rotm @ Matrix.Diagonal((-1, -1, 1))
_q = _rotm.to_quaternion()
_tt_o = inst('tower', TOPPLED_BASE, TOPPLED_SC, (0, 0, 0), G['Servers'], name='City4.ToppledTower')
_tt_o.rotation_mode = 'QUATERNION'
_tt_o.rotation_quaternion = _q
_Mo = Matrix.Translation(TOPPLED_BASE) @ _q.to_matrix().to_4x4() @ Matrix.Diagonal((*TOPPLED_SC, 1))
_R = Matrix.Translation(TOPPLED_BASE) @ _q.to_matrix().to_4x4()
for (mx, my, mz), r, facing in FAN_MOUNTS['tower']:
    Mf = Matrix.Translation(_Mo @ Vector((mx, my, mz))) @ _q.to_matrix().to_4x4() @ \
        Matrix.Diagonal((r * 1.6, r * 1.6, r * 1.6, 1))
    loc, q, fsc = Mf.decompose()
    f = inst('fan', loc, fsc.x, q.to_euler(), G['Fans'])
_ax = (_tp - TOPPLED_BASE).dot(_q.to_matrix() @ Vector((0, 0, 1)))
_mid = TOPPLED_BASE + (_q.to_matrix() @ Vector((0, 0, 1))) * _ax
TOPPLED_CLEAR = _mid.z - DIMS['tower'][1] * TOPPLED_SC[1] / 2 - 0.35 * 1.6 * 1.9
print('toppled tower: its fans clear the deck by', round(TOPPLED_CLEAR, 1), 'm at s', TOPPLED_S)


def gantry(s, name):
    """A rusted steel gantry over the road at s: lattice legs either side, a truss beam, dead signs hanging (screens)."""
    p, t, n = road_frame(s)
    bm = bmesh.new()
    span = BARRIER_Y + 3.0
    hb = 9.0
    sq = [(0.18, -0.18), (0.18, 0.18), (-0.18, 0.18), (-0.18, -0.18)]
    thin = [(0.07, -0.07), (0.07, 0.07), (-0.07, 0.07), (-0.07, -0.07)]
    for side in (1, -1):
        for dt in (-0.9, 0.9):
            base = p + n * side * span + t * dt
            sweep(bm, [base + Vector((0, 0, -0.5)), base + Vector((0, 0, hb + 1.4))], sq)
        for z in frange(0.6, hb, 1.6):
            a = p + n * side * span + t * -0.9 + Vector((0, 0, z))
            b = p + n * side * span + t * 0.9 + Vector((0, 0, z + 1.6))
            sweep(bm, [a, b], thin, caps=False)
    for z in (hb, hb + 1.4):
        for dt in (-0.9, 0.9):
            sweep(bm, [p + n * span + t * dt + Vector((0, 0, z)), p - n * span + t * dt + Vector((0, 0, z))], sq)
    for k in range(13):
        lat = span - 2 * span * k / 12
        lat2 = span - 2 * span * (k + 1) / 12
        sweep(bm, [p + n * lat + Vector((0, 0, hb)), p + n * lat2 + Vector((0, 0, hb + 1.4))], thin, caps=False)
    # Two signs (dark boxes, screens on their road faces) and a hanging cable.
    for lat in (-3.2, 3.4):
        c = p + n * lat + Vector((0, 0, hb - 1.2))
        add_box(bm, c, (0.4, 4.2, 2.0), rot=Matrix.Rotation(math.atan2(t.y, t.x), 3, 'Z'))
        f = add_quad(bm, [c - t * 0.21 + n * 1.9 + Vector((0, 0, -0.8)), c - t * 0.21 - n * 1.9 + Vector((0, 0, -0.8)),
                          c - t * 0.21 - n * 1.9 + Vector((0, 0, 0.8)), c - t * 0.21 + n * 1.9 + Vector((0, 0, 0.8))], 2)
    cab = [p + n * (span - 0.3) + Vector((0, 0, hb)), p + n * (span - 3) + Vector((0, 0, hb - 3.2)),
           p + n * (span - 5.5) + Vector((0, 0, hb - 3.6)), p + n * (span - 7) + Vector((0, 0, hb - 2.4)),
           p + n * (span - 8) + Vector((0, 0, hb - 0.2))]
    sweep(bm, cab, circle_profile(0.12, 5), mat=1)
    for side in (1, -1):
        add_box(bm, p + n * side * span + Vector((0, 0, hb + 1.7)), (0.3, 0.3, 0.3), 3)
    me = mesh_from(name, bm, [MAT['rust'], MAT['cable'], MAT['screen'], MAT['led']])
    box_uvs(me, 0.3)
    uv = me.uv_layers['UVMap']
    for poly in me.polygons:
        if poly.material_index == 2:
            for li, c in zip(poly.loop_indices, ((0, 0), (1, 0), (1, 1), (0, 1))):
                uv.data[li].uv = c
    return obj(name, me, G['Gantries'])


for k, gs in enumerate(GANTRY_S):
    gantry(gs, f'City4.Gantry.{k + 1}')

# CRTs: by monolith bases near the road, and along the shoulders.
crt_spots = []
for kind, pos, yaw, scale, tilt, tag in PLANNED:
    s, lat = road_coords(pos.x, pos.y)
    if abs(lat) < 90 and rnd.random() < 0.55:
        to_road = Vector((-1 if lat > 0 else 1, 0, 0))
        _, t, n = road_frame(s)
        dirn = (-n if lat > 0 else n)
        off = DIMS[kind][1] * scale * 0.5 + rnd.uniform(3, 7)
        c = pos + dirn * off + t * rnd.uniform(-6, 6)
        crt_spots.append((c, rnd.uniform(1.4, 3.4), face_yaw(dirn) + rnd.uniform(-0.6, 0.6)))
for s in frange(170.0, S_CAM - 50, 95.0):
    if rnd.random() < 0.6:
        side = rnd.choice((-1, 1)) if s > 470 else -1
        c = along(s + rnd.uniform(-20, 20), side * rnd.uniform(9, 16))
        _, t, n = road_frame(s)
        crt_spots.append((c, rnd.uniform(0.9, 1.8), face_yaw(-n * side) + rnd.uniform(-0.8, 0.8)))
_cz = terrain_h(np.array([c.x for c, _, _ in crt_spots]), np.array([c.y for c, _, _ in crt_spots]))
for (c, sc, yaw), z in zip(crt_spots, _cz):
    TAG[0] = 'behind' if c.x < X_CAM - 3 else None
    inst('crt', Vector((c.x, c.y, z - 0.12 * sc)), sc, (rnd.uniform(-0.45, -0.1), rnd.uniform(-0.2, 0.2), yaw),
         G['Screens'])
TAG[0] = None


# Cables: from each monolith's foot out over the sand like roots, half sunk in it (one mesh per 260 m cell).
def cable_path(start, dirn, length, rng, z_off=-0.1):
    pts = []
    a = math.atan2(dirn.y, dirn.x)
    p = Vector((start.x, start.y, 0))
    n = max(6, int(length / 2.2))
    for i in range(n + 1):
        pts.append(p.copy())
        a += rng.gauss(0, 0.22)
        p += Vector((math.cos(a), math.sin(a), 0)) * (length / n)
    for i, q in enumerate(pts):  # never over the deck: cut where it reaches the road's shoulder
        if abs(road_coords(q.x, q.y)[1]) < ROAD_W / 2 + 1.5:
            pts = pts[:i]
            break
    if len(pts) < 4:
        return None
    n = len(pts) - 1
    xs = np.array([q.x for q in pts])
    ys = np.array([q.y for q in pts])
    zs = terrain_h(xs, ys)
    out = []
    for i, (q, z) in enumerate(zip(pts, zs)):
        t = i / n
        lift = max(0.0, start.z - z) * (1 - t) ** 6  # drops from its socket at the monolith's foot
        out.append(Vector((q.x, q.y, max(z + z_off + 0.22 * math.sin(i * 1.3 + rng.random()), z - 0.25) + lift)))
    return out


CABLE_CELLS = {}


def add_cables(base, yaw, scale, kind, count, rng, reach=(10, 28), radius=(0.2, 0.45)):
    W, D, Hh = DIMS[kind]
    fwd = Vector((math.sin(yaw), -math.cos(yaw), 0))   # the module's front (local -Y)
    side = Vector((math.cos(yaw), math.sin(yaw), 0))
    for k in range(count):
        u = rng.uniform(-0.45, 0.45)
        st = base + fwd * (D * scale * 0.5 + 0.2) + side * (W * scale * u)
        st.z = base.z + rng.uniform(0.2, 1.0) * scale + 0.5
        d = (fwd * 1.0 + side * rng.uniform(-1.6, 1.6)).normalized()
        path = cable_path(st, d, rng.uniform(*reach) * (0.6 + 0.5 * scale), rng)
        if path is None:
            continue
        cell = int(st.x // TILE)
        CABLE_CELLS.setdefault(cell, []).append((path, rng.uniform(*radius) * (0.6 + 0.6 * scale)))


crng = random.Random(77)
for key, (kind, pos, yaw, sc, tilt) in COMPOSED.items():
    if kind == 'crt':
        continue
    add_cables(pos, yaw, sc[0], kind, 10 if key in ('LN', 'L2', 'R1') else 5, crng, reach=(14, 40), radius=(0.16, 0.3))
for kind, pos, yaw, scale, tilt, tag in PLANNED:
    s, lat = road_coords(pos.x, pos.y)
    n = 4 if abs(lat) < 120 else (1 if abs(lat) < 400 else 0)
    if n:
        add_cables(pos, yaw, scale, kind, n, crng)
cable_objs = []
for cell, lst in CABLE_CELLS.items():
    bm = bmesh.new()
    for path, r in lst:
        sweep(bm, path, circle_profile(r, 5))
    TAG[0] = 'behind' if (cell + 1) * TILE < X_CAM - 3 else None
    me = mesh_from(f'City4.Cables.{cell:02d}', bm, MAT['cable'], smooth=True)
    box_uvs(me, 0.5)
    cable_objs.append(obj(f'City4.Cables.{cell:02d}', me, G['Cables']))
TAG[0] = None
print('cables', sum(len(v) for v in CABLE_CELLS.values()), 'in', len(CABLE_CELLS), 'cells')


# =========================================================================================================================
# Ambient occlusion into the vertex colours.
# =========================================================================================================================
for key in ('fan', 'crt', 'barrier', 'mast', 'tower', 'slab', 'fanwall'):
    bake_ao(M[key], rays=16, floor=0.42)
for o in [o for o in root.children_recursive if o.type == 'MESH']:
    nm = o.name
    if nm.startswith(('City4.Facility', 'City4.Gantry', 'City4.GateDoors')):
        bake_ao(o.data, rays=14, floor=0.4, dist=8.0, extra=FAC_Z - 0.05 if 'Facility' in nm else None)
    elif nm.startswith(('City4.Cables', 'City4.Drifts', 'City4.CrtBeds')):
        set_vcol(o.data, np.full(len(o.data.vertices), 0.92 if 'Cables' not in nm else 0.8))
    elif nm.startswith('City4.Deck'):
        set_vcol(o.data, np.full(len(o.data.vertices), 1.0))

for me in {o.data for o in root.children_recursive if o.type == 'MESH'}:
    if 'AO' not in me.color_attributes and not me.name.startswith(('City4.Storm', 'City4.Dust', 'City4.Sun',
                                                                     'City4.Lightning', 'City4.GateShadow')):
        set_vcol(me, np.ones(len(me.vertices)))

# The dunes: hollows and lee slopes darker, crests lighter, and a contact shadow round every monolith's foot.
feet = []
for kind, pos, yaw, sc, *_ in COMPOSED.values():
    feet.append((pos.x, pos.y, max(DIMS[kind][0], DIMS[kind][1]) * sc[0] * 0.6))
for kind, pos, yaw, scale, *_ in PLANNED:
    feet.append((pos.x, pos.y, max(DIMS[kind][0], DIMS[kind][1]) * scale * 0.6))
FX = np.array([f[0] for f in feet])
FY = np.array([f[1] for f in feet])
FR = np.array([f[2] for f in feet])
for o in terrain_objs:
    me = o.data
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    nz = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get('normal', nz)
    nz = nz.reshape(-1, 3)
    X, Y, Z = co[:, 0], co[:, 1], co[:, 2]
    # Slope facing the sun (lit) vs away (lee): a soft bake of the noon light's shading, kept subtle.
    lit = np.clip(nz @ np.array(SUN_LIGHT_DIR), 0, 1)
    ao = 0.78 + 0.22 * lit
    # Hollows: lower than the local average (a cheap curvature from the height's neighbourhood in a coarse grid).
    ao *= 0.9 + 0.1 * smoothstep(-2.0, 2.0, Z - (terrain_h(X + 25, Y) + terrain_h(X - 25, Y) + terrain_h(X, Y + 25) +
                                               terrain_h(X, Y - 25)) / 4)
    for fx, fy, fr in zip(FX, FY, FR):
        sel = (np.abs(X - fx) < fr * 3) & (np.abs(Y - fy) < fr * 3)
        if sel.any():
            dd = np.hypot(X[sel] - fx, Y[sel] - fy)
            ao[sel] *= 0.55 + 0.45 * smoothstep(fr * 0.8, fr * 2.6, dd)
    # Darker under the barriers and the deck's edges (sand piled in the shade).
    S, L = road_coords_many(X, Y)
    ao *= 0.8 + 0.2 * smoothstep(6.0, 9.5, np.abs(L))
    set_vcol(me, np.clip(ao, 0.3, 1.0))

# =========================================================================================================================
# Tagging and the leak sweep: everything behind the arrival camera is approach_only; nothing approach-only may show in
# the arrival frame (a ray every 4 px).
# =========================================================================================================================
bpy.context.view_layer.update()
for o in root.children_recursive:
    if o.type != 'MESH' or o.get('approach_only'):
        continue
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    if max(v.x for v in bb) < X_CAM - 3:
        o['approach_only'] = 'behind'
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
leaks = {}
for sy in range(0, RES[1], 4):
    for sx in range(0, RES[0], 4):
        d = (screen_point(sx + 0.5, sy + 0.5, 1.0) - EYE).normalized()
        hit, loc, nrm_, idx, ob, mtx = scene.ray_cast(dg, EYE, d, distance=6000)
        if hit and ob.get('approach_only'):
            leaks[ob.name] = leaks.get(ob.name, 0) + 1
print('leak sweep (approach-only pieces seen from the arrival):', leaks or 'none')

# =========================================================================================================================
# Markers.
# =========================================================================================================================


def empty(name, loc, rot_quat=None, yaw=None, props=None, size=1.0):
    e = bpy.data.objects.new(name, None)
    scene.collection.objects.link(e)
    e.parent = root
    e.empty_display_size = size
    e.location = loc
    if rot_quat is not None:
        e.rotation_mode = 'QUATERNION'
        e.rotation_quaternion = rot_quat
    elif yaw is not None:
        e.rotation_euler = (0, 0, math.radians(yaw))
    for k, v in (props or {}).items():
        e[k] = v
    return e


def r4(v):
    return [round(float(c), 4) for c in v]


OUT_END = OUT_LINE[-1]
empty('City4.ArrivalCam', EYE, (LOOK - EYE).to_track_quat('-Z', 'Y'),
      props={'EYE': r4(EYE), 'LOOK': r4(LOOK), 'FOV': round(FOV, 3),
             'note': 'Blender local frame (z up); FOV vertical degrees; the empty looks down its -Z like a camera; '
                     'fitted to concept-desert by art/align4/'})
empty('City4.ApproachCam', APP_EYE, (APP_LOOK - APP_EYE).to_track_quat('-Z', 'Y'),
      props={'EYE': r4(APP_EYE), 'LOOK': r4(APP_LOOK), 'FOV': APP_FOV})
empty('City4.BikeMark', BIKE_AT, yaw=BIKE_YAW, props={'YAW': BIKE_YAW, 'note': 'bike front along local +X'})
empty('City4.RoadIn', Vector((0, 0, 0)), yaw=0.0,
      props={'note': 'the road hands over here heading local +X, deck top z 0; width 11.8; its line is City4.RoadPath; '
                     'x < 0 is the zone before\'s, and so is the left (y > 0) of the first ~420 m',
             'LENGTH': round(ROAD_LEN, 2)})
empty('City4.RoadPath', Vector((0, 0, 0)),
      props={'points': [[round(p.x, 3), round(p.y, 3)] for p in ROAD_LINE], 'length': round(ROAD_LEN, 2),
             'step': 2.0, 'width': ROAD_W,
             'note': f'the bike line, RoadIn (0,0) -> BikeMark ({BIKE_AT.x:.1f},{BIKE_AT.y:.1f}), [x, y] in City4 local '
                     'Blender frame (z up; three: x, -y as z), every 2 m of arc length (last step shorter); the deck '
                     'top is z 0 on this line, ROAD_W wide; the road\'s centreline until its last 60 m, where it eases '
                     f'into the right lane and turns in to park ({BIKE_YAW:.1f} deg left of the road)'})
empty('City4.RoadOut', Vector((0, 0, 0)),
      props={'points': [[round(p.x, 3), round(p.y, 3)] for p in OUT_LINE], 'length': round(OUT_LEN, 2), 'step': 2.0,
             'width': ROAD_W, 'END': [round(OUT_END.x, 3), round(OUT_END.y, 3)], 'END_HEADING': 0.0,
             'note': 'the way on, BikeMark -> END, [x, y] in City4 local Blender frame every 2 m: back onto the '
                     'centreline and straight in through the facility\'s gate (its tunnel runs on to blast doors '
                     '~50 m in); END_HEADING radians anticlockwise from +x'})
empty('City4.DeckTop', Vector((0, 0, 0)), props={'note': 'deck top z 0 (RoadIn)'})

# --- Stats, save, export -----------------------------------------------------------------------------------------------
meshes = [o for o in root.children_recursive if o.type == 'MESH']
uniq = {o.data.name: o.data for o in meshes}


def tris(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


TRI_UNIQUE = sum(tris(me) for me in uniq.values())
TRI_DRAWN = sum(tris(o.data) for o in meshes)
print('objects', len(meshes), 'unique meshes', len(uniq), 'unique tris', TRI_UNIQUE, 'drawn tris', TRI_DRAWN)
print('arrival EYE', r4(EYE), 'LOOK', r4(LOOK), 'FOV', FOV, 'bike', r4(BIKE_AT), BIKE_YAW)
print('arrival three: eye', [round(EYE.x, 4), round(EYE.z, 4), round(-EYE.y, 4)], 'look',
      [round(LOOK.x, 4), round(LOOK.z, 4), round(-LOOK.y, 4)])

cam = bpy.data.objects.new('ArrivalCamera', bpy.data.cameras.new('ArrivalCamera'))
scene.collection.objects.link(cam)


def set_cam(eye, look, fov):
    cam.location = eye
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (look - eye).to_track_quat('-Z', 'Y')
    cam.data.type = 'PERSP'
    cam.data.sensor_fit = 'VERTICAL'
    cam.data.sensor_height = 24
    cam.data.lens = 12 / math.tan(math.radians(fov / 2))
    cam.data.clip_start = 0.05
    cam.data.clip_end = 8000


set_cam(EYE, LOOK, FOV)
scene.camera = cam
scene.render.resolution_x, scene.render.resolution_y = RES

# The world (for the renders; the site has its own sky): hazy amber, whiter round the sun, a dusty horizon.
world = bpy.data.worlds.new('City4Noon')
world.use_nodes = True
nt = world.node_tree
nodes, links = nt.nodes, nt.links
bg = nodes['Background']
tc = nodes.new('ShaderNodeTexCoord')
nrm = nodes.new('ShaderNodeVectorMath')
nrm.operation = 'NORMALIZE'
links.new(tc.outputs['Generated'], nrm.inputs[0])
sep = nodes.new('ShaderNodeSeparateXYZ')
links.new(nrm.outputs['Vector'], sep.inputs[0])
ramp = nodes.new('ShaderNodeValToRGB')
cr = ramp.color_ramp
cr.elements[0].position, cr.elements[0].color = 0.0, (1.0, 0.42, 0.13, 1)
cr.elements[1].position, cr.elements[1].color = 0.65, (0.5, 0.18, 0.05, 1)
e = cr.elements.new(0.12)
e.color = (0.85, 0.35, 0.1, 1)
links.new(sep.outputs['Z'], ramp.inputs['Fac'])
sun_dir = (sun_c - EYE).normalized()
dot = nodes.new('ShaderNodeVectorMath')
dot.operation = 'DOT_PRODUCT'
links.new(nrm.outputs['Vector'], dot.inputs[0])
dot.inputs[1].default_value = sun_dir
mx0 = nodes.new('ShaderNodeMath')
mx0.operation = 'MAXIMUM'
links.new(dot.outputs['Value'], mx0.inputs[0])
mx0.inputs[1].default_value = 0.0
pw = nodes.new('ShaderNodeMath')
pw.operation = 'POWER'
links.new(mx0.outputs[0], pw.inputs[0])
pw.inputs[1].default_value = 90.0   # a tight hot glow round the disc
pw2 = nodes.new('ShaderNodeMath')
pw2.operation = 'POWER'
links.new(mx0.outputs[0], pw2.inputs[0])
pw2.inputs[1].default_value = 5.0    # and a broad warm one
mix = nodes.new('ShaderNodeMix')
mix.data_type = 'RGBA'
mix.blend_type = 'ADD'
links.new(pw.outputs[0], mix.inputs['Factor'])
links.new(ramp.outputs['Color'], mix.inputs['A'])
mix.inputs['B'].default_value = (1.5, 1.25, 0.9, 1)
mix2 = nodes.new('ShaderNodeMix')
mix2.data_type = 'RGBA'
mix2.blend_type = 'ADD'
links.new(pw2.outputs[0], mix2.inputs['Factor'])
links.new(mix.outputs['Result'], mix2.inputs['A'])
mix2.inputs['B'].default_value = (0.3, 0.13, 0.03, 1)
links.new(mix2.outputs['Result'], bg.inputs['Color'])
# Lighting sees it bright (an amber ambient under the noon sun); the camera sees it darker, so it keeps its colour.
lp_ = nodes.new('ShaderNodeLightPath')
smix = nodes.new('ShaderNodeMath')
smix.operation = 'MULTIPLY_ADD'
links.new(lp_.outputs['Is Camera Ray'], smix.inputs[0])
smix.inputs[1].default_value = -0.85
smix.inputs[2].default_value = 1.5
links.new(smix.outputs[0], bg.inputs['Strength'])
scene.world = world

os.makedirs(os.path.dirname(GLB), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
for o in bpy.context.view_layer.objects:
    o.select_set(False)
for o in root.children_recursive:
    o.select_set(True)
root.select_set(True)
bpy.ops.export_scene.gltf(filepath=GLB, export_format='GLB', use_selection=True, export_apply=True,
                          export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
                          export_draco_position_quantization=14, export_draco_normal_quantization=8,
                          export_draco_texcoord_quantization=10, export_draco_color_quantization=8,
                          export_vertex_color='ACTIVE', export_image_format='AUTO', export_image_quality=80,
                          export_gpu_instances=True,
                          export_yup=True, export_cameras=False, export_lights=False, export_extras=True)
GLB_SIZE = os.path.getsize(GLB)
print('exported', GLB, GLB_SIZE)


# --- Renders -------------------------------------------------------------------------------------------------------------
def add_bike():
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=BIKE_GLB)
    imported = set(bpy.data.objects) - before
    rig = bpy.data.objects.new('BikeRig', None)
    scene.collection.objects.link(rig)
    rig.matrix_world = BIKE_M
    for o in imported:
        if o.parent is None:
            o.parent = rig
    return [o for o in imported if o.type == 'MESH']


bike_objs = add_bike()
os.makedirs(RENDERS, exist_ok=True)

# 1. Object IDs (flat colours) for score.py: sky transparent; see art/align4/score.py IDS.
ID_COL = json.load(open(os.path.join(ALIGN, 'ids.json')))
hidden_ids = []
for o in scene.objects:
    if o.type != 'MESH':
        continue
    k = 'other'
    if o in bike_objs:
        k = 'bike'
    elif o.get('ids_hide'):
        o.hide_render = True
        hidden_ids.append(o)
        continue
    else:
        k = IDS.get(o.name, 'other')
    if k is None:
        o.hide_render = True
        hidden_ids.append(o)
        continue
    o.color = (*ID_COL.get(k, ID_COL['other']), 1)
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'FLAT'
scene.display.shading.color_type = 'OBJECT'
scene.display.shading.show_cavity = False
scene.display.shading.show_object_outline = False
scene.display.shading.show_specular_highlight = False
scene.render.film_transparent = True
scene.render.image_settings.color_mode = 'RGBA'
scene.view_settings.view_transform = 'Standard'
scene.render.filepath = os.path.join(RENDERS, f'city4-arrival-ids-{ROUND}.png')
bpy.ops.render.render(write_still=True)
scene.render.film_transparent = False
scene.render.image_settings.color_mode = 'RGB'
for o in hidden_ids:
    o.hide_render = False

# 2. EEVEE: the noon sun high over the disc's bearing, a warm sky fill, the haze, the storm and glows.
if os.environ.get('CITY4_NO_EEVEE') != '1':
    scene.render.engine = 'BLENDER_EEVEE'
    ee = scene.eevee
    ee.taa_render_samples = 32
    try:
        ee.volumetric_end = 2600.0
        ee.volumetric_start = 0.5
        ee.volumetric_tile_size = '8'
        ee.volumetric_samples = 48
        ee.volumetric_sample_distribution = 0.95
    except Exception as exc:
        print('volumetrics:', exc)
    if hasattr(ee, 'use_raytracing'):
        ee.use_raytracing = True
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Punchy'
    scene.view_settings.exposure = -0.2
    # The haze: a big volume round the camera (render only; EEVEE's world volume swallows the sky).
    hb = bmesh.new()
    bmesh.ops.create_icosphere(hb, subdivisions=3, radius=2700.0)
    haze_me = bpy.data.meshes.new('RenderHaze')
    hb.to_mesh(haze_me)
    hb.free()
    hm = bpy.data.materials.new('RenderHaze')
    hm.use_nodes = True
    hn = hm.node_tree
    hn.nodes.remove(hn.nodes['Principled BSDF'])
    hv = hn.nodes.new('ShaderNodeVolumePrincipled')
    hv.inputs['Color'].default_value = (1.0, 0.52, 0.22, 1)
    hv.inputs['Density'].default_value = float(os.environ.get('CITY4_HAZE', '0.00028'))
    hv.inputs['Anisotropy'].default_value = 0.1
    hn.links.new(hv.outputs[0], hn.nodes['Material Output'].inputs['Volume'])
    htr = hn.nodes.new('ShaderNodeBsdfTransparent')  # (no surface of its own: an unlinked one draws grey)
    hn.links.new(htr.outputs[0], hn.nodes['Material Output'].inputs['Surface'])
    haze_me.materials.append(hm)
    haze_o = bpy.data.objects.new('RenderHaze', haze_me)
    scene.collection.objects.link(haze_o)
    haze_o.location = EYE
    haze_o.scale = (1.0, 1.0, 0.18)
    sl = bpy.data.lights.new('SunKey', 'SUN')
    sl.energy = 5.0
    sl.color = (1.0, 0.9, 0.75)
    sl.angle = math.radians(1.5)
    so = bpy.data.objects.new('SunKey', sl)
    scene.collection.objects.link(so)
    so.rotation_mode = 'QUATERNION'
    so.rotation_quaternion = (-SUN_LIGHT_DIR).to_track_quat('-Z', 'Y')
    scene.render.filepath = os.path.join(RENDERS, f'city4-arrival-{ROUND}.png')
    bpy.ops.render.render(write_still=True)
    if os.environ.get('CITY4_APPROACH', '1') == '1':
        for o in bike_objs:
            o.hide_render = True
        set_cam(APP_EYE, APP_LOOK, APP_FOV)
        haze_o.location = APP_EYE
        scene.render.filepath = os.path.join(RENDERS, f'city4-approach-{ROUND}.png')
        bpy.ops.render.render(write_still=True)
        set_cam(EYE, LOOK, FOV)

# 3. The plan: straight down, orthographic, the road's line, BikeMark, RoadIn and the cameras drawn over it.
if os.environ.get('CITY4_PLAN', '1') == '1':
    for o in bike_objs:
        o.hide_render = True
    for o in scene.objects:
        if o.name.startswith(('City4.Storm', 'City4.DustHaze', 'City4.Lightning', 'City4.Sun', 'City4.DunesFar')):
            o.hide_render = True
    PLAN_C, PLAN_S, PLAN_PX = Vector(((X_CAM + 200) / 2, Y_F / 2)), X_CAM + 520, 1600
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = PLAN_S
    cam.data.sensor_fit = 'AUTO'
    cam.location = (PLAN_C.x, PLAN_C.y, 1500)
    cam.rotation_mode = 'XYZ'
    cam.rotation_euler = (0, 0, 0)
    cam.data.clip_end = 4000
    scene.render.resolution_x = scene.render.resolution_y = PLAN_PX
    scene.render.engine = 'BLENDER_WORKBENCH'
    if 'RenderHaze' in bpy.data.objects:
        bpy.data.objects['RenderHaze'].hide_render = True
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'MATERIAL'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    plan = os.path.join(RENDERS, 'city4-plan.png')
    scene.render.filepath = plan
    bpy.ops.render.render(write_still=True)

    def px(v):
        return [round((v[0] - PLAN_C.x) / PLAN_S * PLAN_PX + PLAN_PX / 2, 1),
                round(PLAN_PX / 2 - (v[1] - PLAN_C.y) / PLAN_S * PLAN_PX, 1)]

    marks = {'line': [px(p) for p in ROAD_LINE], 'out': [px(p) for p in OUT_LINE], 'bike': px(BIKE_AT),
             'roadin': px((0, 0)), 'arrival': px(EYE), 'arrival_look': px(EYE + (LOOK - EYE).normalized() * 120),
             'approach': px(APP_EYE), 'approach_look': px(APP_EYE + (APP_LOOK - APP_EYE).normalized() * 120),
             'end': px(OUT_END),
             'title': f'City4 plan: road {ROAD_LEN:.0f} m, {len(ROAD_LINE)} path points (every 2 m), RoadOut '
                      f'{OUT_LEN:.0f} m; 1 px = {PLAN_S / PLAN_PX:.2f} m'}
    draw = """
import json, sys
from PIL import Image, ImageDraw
m = json.load(open(sys.argv[2]))
im = Image.open(sys.argv[1]).convert('RGB')
d = ImageDraw.Draw(im)
d.line([tuple(p) for p in m['line']], fill=(255, 40, 40), width=2)
d.line([tuple(p) for p in m['out']], fill=(255, 150, 0), width=2)
for k, col in (('arrival', (0, 255, 255)), ('approach', (255, 255, 0))):
    d.line([tuple(m[k]), tuple(m[k + '_look'])], fill=col, width=3)
    d.ellipse([m[k][0] - 5, m[k][1] - 5, m[k][0] + 5, m[k][1] + 5], outline=col, width=2)
for k, col in (('bike', (255, 0, 255)), ('roadin', (0, 255, 0)), ('end', (255, 255, 255))):
    d.ellipse([m[k][0] - 6, m[k][1] - 6, m[k][0] + 6, m[k][1] + 6], fill=col)
d.rectangle([0, 0, im.size[0], 26], fill=(0, 0, 0))
d.text((8, 7), m['title'] + '   red: RoadPath  orange: RoadOut  green: RoadIn  magenta: BikeMark  white: END  cyan: '
       'ArrivalCam  yellow: ApproachCam', fill=(255, 255, 255))
im.save(sys.argv[1])
"""
    mj = os.path.join(ALIGN, 'out', 'plan-marks.json')
    with open(mj, 'w') as f:
        json.dump(marks, f)
    try:
        subprocess.run(['python3', '-c', draw, plan, mj], check=True)
    except Exception as exc:
        print('plan overlay skipped:', exc)

json.dump({'round': ROUND, 'road_length': round(ROAD_LEN, 2), 'roadout_length': round(OUT_LEN, 2),
           'glb_bytes': GLB_SIZE, 'tris_unique': TRI_UNIQUE, 'tris_drawn': TRI_DRAWN,
           'arrival_blender': {'EYE': r4(EYE), 'LOOK': r4(LOOK), 'FOV': round(FOV, 3)},
           'arrival_three': {'eye': [round(EYE.x, 4), round(EYE.z, 4), round(-EYE.y, 4)],
                             'look': [round(LOOK.x, 4), round(LOOK.z, 4), round(-LOOK.y, 4)], 'fov': round(FOV, 3)},
           'bike': r4(BIKE_AT), 'bike_yaw': BIKE_YAW, 'end': r4(OUT_END), 'leaks': leaks},
          open(os.path.join(ALIGN, 'out', f'build-{ROUND}.json'), 'w'), indent=1)
for script in (['score.py', ROUND], ['approach_check.py', ROUND]):
    try:
        subprocess.run(['python3', os.path.join(ALIGN, script[0]), *script[1:]], check=True, cwd=ALIGN)
    except Exception as exc:
        print(script[0], 'skipped:', exc)
