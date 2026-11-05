"""What the bulkhead group's four assets share (bulkhead_frame, bulkhead_door, red_room_shell, red_tank): the sizes, the mesh
builder, and the paint. On the site there are no lamps and a vertex colour only multiplies the dim diffuse, so the group's light
is painted into emission, as the lab's tanks are (art/core/tanks.py):

  - bulkhead_door and bulkhead_frame: each its own painted texture, rust and all, lit in the paint;
  - bulkhead_ramp: U = how lit, V = which surface, so everything else (hardware, the room) is lit per vertex by bake_lit();
  - bulkhead_tank: the tank's glowing far wall.

register(kit) goes before _mats.mats(kit), which adds their materials once they're registered.

How they fit (opening's frame: origin on the tube's axis at the door seat, +X down the road, so placed at z 5.5 over the deck):
"""
import math

import bpy
import numpy as np
from mathutils import Vector

R_OPEN = 8.5
CZ = 5.5                # the opening's centre over the deck
DOOR_D = 17.6
DOOR_T = 1.6
DOOR_CY = 9.1           # door's local frame: hinge at the origin, the disc's centre this far along +Y; outer face (wheel) to -X
HINGE = (1.7, -DOOR_CY, 0.0)   # the hinge, in bulkhead_frame's frame (its empty DoorHinge)
YAW_HALF = -55.0        # the door's turn about its origin, degrees: as the image shows it half open (a 6.7 m gap)
YAW_OPEN = -81.0        # and right open, leaving the road its 14 m gap
ROOM_W, ROOM_L, ROOM_H = 34.0, 70.0, 15.0
DECK_Z = 6.0            # the room's walkways and gantries, top; 5.5 underneath, clear of the road
RAIL_Y = 7.0
RIGHT_DECK_FROM = 22.0  # the right walkway starts past where the door swings
GANTRY_X = (34.0, 63.0)
TANK_BASE_Z = 4.6       # tanks' origin over the deck: their base collar goes through the walkway, top 14.6
TANKS = [(30.0, 13.0), (52.0, 11.0), (38.0, -13.0), (56.0, -11.5)]   # suggested (x, y) in the room's frame

# Door hardware, in the disc's coordinates (y from its centre toward the free edge, z up).
RING_IN = 7.15          # the raised ring round the door's face, inner radius
WHEEL = (1.5, 0.45)
WHEEL_R = 1.75
RIBS_Y = (-0.75, -4.7)
RIBS_Z = (5.1, 1.9, -2.3, -6.1)
RIB_W = 0.5

# Frame profile, front to back: (x, R), the throat telescoping from the tube's end to the opening.
FRAME_PATH = [(-8.2, 9.4), (-8.2, 8.62), (-7.6, 8.62), (-7.6, 8.95), (-4.6, 8.95), (-4.6, 8.6), (-3.9, 8.6), (-3.9, 8.85),
              (-1.9, 8.85), (-1.9, 8.55), (-1.2, 8.55), (-1.2, 8.72), (-0.5, 8.72), (-0.5, 8.5), (0.9, 8.5), (0.9, 8.9),
              (1.4, 8.9), (1.4, 13.0)]
FRAME_S = [0.0]
for _a, _b in zip(FRAME_PATH, FRAME_PATH[1:]):
    FRAME_S.append(FRAME_S[-1] + math.hypot(_b[0] - _a[0], _b[1] - _a[1]))
FRAME_LEN = FRAME_S[-1]
# Per segment of the path: how pale it's painted (0 dark .. 1 the riveted bands) and how much of the room's red reaches it.
FRAME_PALE = [0.75, 0.25, 0.05, 0.42, 1.0, 0.3, 0.05, 1.0, 0.85, 0.2, 0.05, 0.1, 0.3, 0.15, 0.1, 0.05, 0.05]
FRAME_RED = [0.0, 0.015, 0.02, 0.015, 0.02, 0.04, 0.05, 0.02, 0.07, 0.14, 0.22, 0.72, 0.36, 0.2, 0.26, 0.16, 0.08]
# The red lamp boxes on the throat: (degrees round from +Y toward the crown, x).
FRAME_LAMPS = [(52.0, -6.0), (2.0, -6.0), (153.0, -6.0)]
# The clamp blocks on the throat: (degrees round, x, wall radius, drop, across, along).
FRAME_CLAMPS = [(d, -2.9, 8.85, 0.62 if d in (10.0, 31.0, -13.0) else 0.42, 1.5 if d in (10.0, 31.0, -13.0) else 1.0, 1.5)
                for d in (10.0, 31.0, -13.0, 50.0, 72.0, 96.0, 122.0, 142.0, 168.0, 192.0, -38.0, 215.0)] + \
               [(d, -6.1, 8.95, 0.3, 1.0, 1.4) for d in (22.0, 80.0, 110.0, 190.0, -22.0)]

# The ramp's rows.
DARK, RUST, BRASS, COLD, EMBER, PALE, IRON = range(7)
_ROWS = 8
_STOPS = {
    DARK: [(0.0, (3, 2, 2)), (0.3, (40, 7, 6)), (0.7, (135, 15, 11)), (1.0, (235, 42, 28))],
    RUST: [(0.0, (8, 5, 4)), (0.35, (62, 30, 15)), (0.7, (165, 85, 30)), (1.0, (232, 150, 62))],
    BRASS: [(0.0, (12, 9, 4)), (0.3, (52, 38, 13)), (0.65, (122, 90, 32)), (1.0, (226, 186, 100))],
    COLD: [(0.0, (5, 7, 5)), (0.45, (42, 50, 40)), (0.8, (105, 112, 92)), (1.0, (178, 180, 150))],
    EMBER: [(0.0, (4, 1, 1)), (0.35, (70, 5, 4)), (0.7, (190, 16, 11)), (1.0, (255, 60, 38))],
    PALE: [(0.0, (8, 7, 5)), (0.35, (52, 45, 30)), (0.7, (118, 100, 66)), (1.0, (190, 165, 110))],
    IRON: [(0.0, (3, 3, 3)), (0.4, (24, 20, 18)), (0.8, (72, 58, 48)), (1.0, (140, 112, 88))],
}


def rowv(row):
    return 1.0 - (row + 0.5) / _ROWS


def frame_light(theta):
    """How much light reaches the frame's riveted bands, round the ring (radians from +Y, the image's left, toward the crown)."""
    d = lambda c, w: np.exp(-(np.angle(np.exp(1j * (theta - math.radians(c)))) / math.radians(w)) ** 2)
    return 0.24 + 0.72 * d(5.0, 55.0) + 0.22 * d(62.0, 26.0) + 0.1 * d(150.0, 30.0)


def paint_door(kit):
    def fn():
        n = 512
        rng = np.random.default_rng(71)
        col = (np.arange(n) + 0.5) / n
        y = (col[None, :] - 0.5) * DOOR_D * np.ones((n, 1))
        z = (0.5 - col[:, None]) * DOOR_D * np.ones((1, n))
        r = np.hypot(y, z)
        a, b, c = kit.vnoise(n, 5, 101, 5), kit.vnoise(n, 16, 102, 4), kit.vnoise(n, 48, 103, 2)
        a2, b2 = kit.vnoise(n, 8, 106, 4), kit.vnoise(n, 32, 107, 3)
        lerp = lambda u, v, t: u * (1 - t[..., None]) + v * t[..., None]
        steel = np.array([0.3, 0.31, 0.25]) * (0.5 + 0.75 * a)[..., None]
        # Runs of rust down the plates, from columns of noise.
        cols = np.convolve(rng.random(n), np.ones(5) / 5, mode='same')
        run = kit.smoothstep(0.56, 0.72, cols)[None, :] * (0.25 + 0.75 * kit.vnoise(n, 4, 105, 2))
        rm = np.maximum(kit.smoothstep(0.45, 0.6, a * 0.55 + b * 0.45), run * 0.85)
        rc = lerp(np.array([0.1, 0.058, 0.036]), np.array([0.55, 0.31, 0.11]), kit.smoothstep(0.34, 0.7, b))
        face = lerp(steel, rc, rm)
        # Paint flaked to pale metal, toward the free edge above the wheel, as in the image.
        flake = kit.smoothstep(0.54, 0.66, c * 0.35 + a * 0.65) * np.exp(-(((y - 3.6) / 3.2) ** 2 + ((z - 3.0) / 4.2) ** 2))
        face = lerp(face, np.array([0.66, 0.65, 0.53]), np.clip(flake * 1.5, 0, 1))
        # Each panel a little different.
        ye = np.searchsorted(np.sort(RIBS_Y), y)
        ze = np.searchsorted(np.sort(RIBS_Z), z)
        face = face * (0.84 + 0.3 * rng.random((4, 6))[ye, ze])[..., None]
        # The tunnel's light: strongest toward the free edge, the hinge side going to dark green.
        light = 0.26 + 0.85 * np.exp(-(((y - 3.8) / 5.2) ** 2 + ((z - 1.0) / 6.5) ** 2))
        light = light * (0.62 + 0.38 * kit.smoothstep(-8.5, -2.5, z))
        face = face * light[..., None]
        face = face * lerp(np.array([1.0, 1.0, 1.0]), np.array([0.88, 1.03, 0.86]), kit.smoothstep(1.0, -6.0, y))
        # The raised ring: rusted amber, bright down the free edge where the room's light catches it, dark steel by the hinge.
        rr = lerp(np.array([0.24, 0.16, 0.09]), np.array([0.76, 0.45, 0.14]), kit.smoothstep(0.34, 0.62, a2 * 0.7 + b2 * 0.3))
        lr = 0.16 + 1.1 * kit.smoothstep(-1.0, 5.5, y) * (0.5 + 0.5 * kit.smoothstep(-8.5, -2.0, z))
        pits = kit.smoothstep(0.66, 0.72, b2)
        ringc = rr * lr[..., None] * (1 - 0.86 * pits)[..., None]
        ringc = ringc + kit.smoothstep(-2.5, -8.5, z)[..., None] * kit.smoothstep(-1.0, 5.0, y)[..., None] * np.array([0.14, 0.012, 0.006])
        ringt = kit.smoothstep(RING_IN - 0.02, RING_IN + 0.12, r)
        out = lerp(face, ringc, ringt)
        # What the ribs and the ring shade.
        ao = np.ones((n, n))
        ao *= 1 - 0.72 * np.exp(-(np.clip(RING_IN - r, 0, None) / 0.28) ** 2) * (r < RING_IN)
        ao *= 1 - 0.5 * np.exp(-((r - 8.1) / 0.05) ** 2)
        for yr in RIBS_Y:
            d = np.abs(y - yr) - RIB_W / 2
            top = d < 0
            out = np.where((top & (r < RING_IN))[..., None], out * 1.0 + np.array([0.026, 0.015, 0.007]), out)
            ao *= 1 - 0.62 * np.exp(-(np.clip(d, 0, None) / 0.3) ** 2) * (~top)
        for zr in RIBS_Z:
            d = np.abs(z - zr) - RIB_W / 2
            top = d < 0
            out = np.where((top & (r < RING_IN))[..., None], out * 1.0 + np.array([0.026, 0.015, 0.007]), out)
            below = (z < zr) * 0.4 + 0.3
            ao *= 1 - (below + 0.1) * np.exp(-(np.clip(d, 0, None) / 0.42) ** 2) * (~top)
            # Rust running down from each rib.
            streak = np.exp(-(np.clip(zr - z, 0, None) / 1.8)) * (z < zr) * kit.smoothstep(0.42, 0.7, cols)[None, :]
            out = lerp(out, np.array([0.26, 0.14, 0.07]) * light[..., None], np.clip(streak * 0.7, 0, 1) * (r < RING_IN))
        wd = np.hypot(y - WHEEL[0], z - WHEEL[1])
        ao *= 1 - 0.62 * np.exp(-(wd / 2.1) ** 2)
        # The rivets' dark rings, where the rivets stand.
        for rad, cnt in ((8.56, 72), (7.32, 54)):
            for i in range(cnt):
                th = 2 * math.pi * (i + 0.5) / cnt
                py, pz = rad * math.cos(th), rad * math.sin(th)
                ci, ri = int((py / DOOR_D + 0.5) * n), int((0.5 - pz / DOOR_D) * n)
                out[max(ri - 3, 0):ri + 3, max(ci - 3, 0):ci + 3] *= 0.45
        grain = 0.9 + 0.2 * kit.vnoise(n, 128, 108, 1)
        return np.clip(out * ao[..., None] * grain[..., None], 0, 1)
    return fn


def paint_frame(kit):
    def fn():
        n = 512
        th = (np.arange(n) + 0.5) / n * 2 * math.pi
        s = (1 - (np.arange(n) + 0.5) / n) * FRAME_LEN
        seg = np.clip(np.searchsorted(FRAME_S, s) - 1, 0, len(FRAME_PALE) - 1)
        pale = np.array(FRAME_PALE)[seg][:, None] * np.ones((1, n))
        red = np.array(FRAME_RED)[seg][:, None] * np.ones((1, n))
        a, b = kit.vnoise(n, 7, 121, 5), kit.vnoise(n, 28, 122, 3)
        lerp = lambda u, v, t: u * (1 - t[..., None]) + v * t[..., None]
        dark = np.array([0.07, 0.066, 0.055]) * (0.5 + 0.85 * a)[..., None]
        olive = np.array([0.27, 0.24, 0.165]) * (0.45 + 0.85 * a)[..., None]
        rust = lerp(np.array([0.13, 0.072, 0.04]), np.array([0.44, 0.26, 0.1]), kit.smoothstep(0.35, 0.65, b))
        c = lerp(dark, olive, pale)
        c = lerp(c, rust, kit.smoothstep(0.46, 0.62, a * 0.5 + b * 0.5) * (0.4 + 0.6 * pale))
        c = c * (1 - 0.8 * kit.smoothstep(0.7, 0.75, b))[..., None]
        # Plates: a dark seam every 30 degrees on the bands.
        seam = np.abs(((th / math.radians(30.0) + 0.5) % 1) - 0.5) * math.radians(30.0) * 8.8
        c = c * (1 - 0.75 * np.exp(-(seam / 0.09) ** 2)[None, :] * (pale > 0.3))[..., None]
        light = frame_light(th)[None, :] * np.ones((n, 1))
        c = c * light[..., None]
        # Dark where each ring shades the band behind it, lit where it faces the tunnel.
        for sb in FRAME_S:
            c = c * (1 - 0.5 * np.exp(-(np.clip(s - sb, 0, None) / 0.28) ** 2) * (s > sb))[..., None]
        # The tunnel's green, low on both sides.
        low = np.exp(-(np.angle(np.exp(1j * (th + math.radians(25.0)))) / math.radians(28.0)) ** 2) + \
            np.exp(-(np.angle(np.exp(1j * (th - math.radians(205.0)))) / math.radians(28.0)) ** 2)
        c = c + (low[None, :] * (1 - red))[..., None] * np.array([0.012, 0.075, 0.022])
        # The room's red, strongest at the seat, round the opening.
        roomred = 0.62 + 0.38 * np.exp(-(np.angle(np.exp(1j * (th - math.radians(70.0)))) / math.radians(110.0)) ** 2)
        c = c + (red * roomred[None, :] * (0.72 + 0.4 * b))[..., None] * np.array([0.95, 0.07, 0.04])
        # The lamp boxes' spill.
        for deg, x in FRAME_LAMPS:
            sl = FRAME_S[3] + (x + 7.6)
            dth = np.angle(np.exp(1j * (th - math.radians(deg)))) * 8.9
            d2 = dth[None, :] ** 2 + (s[:, None] - sl) ** 2
            c = c + np.exp(-d2 / (1.05 ** 2))[..., None] * np.array([0.5, 0.025, 0.018])
        # What each clamp shades.
        for deg, x, _w, _dp, across, along in FRAME_CLAMPS:
            sl = (FRAME_S[3] + x + 7.6) if x < -4.6 else (FRAME_S[7] + x + 3.9)
            dth = np.abs(np.angle(np.exp(1j * (th - math.radians(deg))))) * 8.9 - across / 2
            ds = np.abs(s[:, None] - sl) - along / 2
            near = np.maximum(np.clip(dth[None, :], 0, None), np.clip(ds, 0, None))
            c = c * (1 - 0.68 * np.exp(-(near / 0.4) ** 2))[..., None]
        return np.clip(c * (0.92 + 0.16 * kit.vnoise(n, 128, 123, 1))[..., None], 0, 1)
    return fn


def paint_ramp():
    n = 128
    out = np.zeros((n, n, 3))
    cell = n // _ROWS
    u = (np.arange(n) + 0.5) / n
    for row, stops in _STOPS.items():
        xs = [s[0] for s in stops]
        for ch in range(3):
            v = np.interp(u, xs, [s[1][ch] / 255 for s in stops])
            out[row * cell:(row + 1) * cell, :, ch] = v
    return out


def paint_tank(kit):
    def fn():
        n = 256
        rng = np.random.default_rng(83)
        h = 1 - (np.arange(n) + 0.5) / n
        a, b = kit.vnoise(n, 6, 131, 4), kit.vnoise(n, 20, 132, 3)
        # Columns of plume, stretched up the tank by sampling the noise's columns down the rows.
        cols = kit.vnoise(n, 18, 133, 3)
        plume = cols[(np.arange(n) // 7)[:, None] % n, np.arange(n)[None, :]]
        v = 0.38 + 0.25 * a + 0.45 * kit.smoothstep(0.55, 0.8, plume)
        v = v * (0.72 + 0.28 * kit.smoothstep(0.0, 0.25, h)[:, None]) + 0.5 * np.exp(-(h / 0.07) ** 2)[:, None] + 0.22 * np.exp(-((1 - h) / 0.05) ** 2)[:, None]
        dark = kit.smoothstep(0.62, 0.76, b * 0.6 + plume * 0.4) * 0.45
        v = v * (1 - dark)
        out = np.zeros((n, n, 3))
        out[..., 0] = np.clip(v * 1.15, 0, 1)
        out[..., 1] = np.clip((v - 0.62) * 0.72, 0.005, 1)
        out[..., 2] = np.clip((v - 0.62) * 0.52, 0.004, 1)
        _ = rng
        return out
    return fn


def register(kit):
    kit.register_texture('bulkhead_door', paint_door(kit))
    kit.register_texture('bulkhead_frame', paint_frame(kit))
    kit.register_texture('bulkhead_ramp', paint_ramp, jpeg=False)
    kit.register_texture('bulkhead_tank', paint_tank(kit))


class B:
    """Faces, each with its own material and either painted UVs (uvf(co) or per-corner) or the ramp's (row, lit)."""

    def __init__(self):
        self.v, self.f = [], []

    def vert(self, p):
        self.v.append((float(p[0]), float(p[1]), float(p[2])))
        return len(self.v) - 1

    def face(self, vi, mat=0, uv=None, uvf=None, row=None, lit=None, gain=1.0, smooth=False):
        self.f.append({'vi': tuple(vi), 'mat': mat, 'uv': uv, 'uvf': uvf, 'row': row, 'lit': lit, 'gain': gain, 'smooth': smooth})

    def poly(self, pts, **kw):
        self.face([self.vert(p) for p in pts], **kw)

    def box(self, c, size, mat=0, axes=None, skip=(), per_face=None, **kw):
        """A box: centre c, size along its axes (default x, y, z). skip: which of '-x +x -y +y -z +z' to leave off."""
        ax = axes or (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
        c = Vector(c)
        h = [ax[i] * size[i] / 2 for i in range(3)]
        vs = [self.vert(c + h[0] * sx + h[1] * sy + h[2] * sz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        faces = {'-x': (0, 1, 3, 2), '+x': (4, 6, 7, 5), '-y': (0, 4, 5, 1), '+y': (2, 3, 7, 6), '-z': (0, 2, 6, 4), '+z': (1, 5, 7, 3)}
        for k, idx in faces.items():
            if k in skip:
                continue
            args = dict(kw, mat=mat)
            if per_face and k in per_face:
                args.update(per_face[k])
            self.face([vs[i] for i in idx], **args)

    def rod(self, p0, p1, r, sides=4, mat=0, caps=True, a0=None, **kw):
        p0, p1 = Vector(p0), Vector(p1)
        d = (p1 - p0).normalized()
        u = d.cross(Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))).normalized()
        w = d.cross(u)
        off = math.pi / sides if a0 is None else a0
        ang = [off + 2 * math.pi * i / sides for i in range(sides)]
        ra = [self.vert(p0 + (u * math.cos(t) + w * math.sin(t)) * r) for t in ang]
        rb = [self.vert(p1 + (u * math.cos(t) + w * math.sin(t)) * r) for t in ang]
        for i in range(sides):
            j = (i + 1) % sides
            self.face((ra[i], ra[j], rb[j], rb[i]), mat=mat, **kw)
        if caps:
            self.face(tuple(reversed(ra)), mat=mat, **kw)
            self.face(tuple(rb), mat=mat, **kw)

    def rivet(self, c, n, r=0.09, h=0.08, sides=5, mat=0, row=RUST, lit=(0.08, 0.6)):
        c, n = Vector(c), Vector(n).normalized()
        u = n.cross(Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))).normalized()
        w = n.cross(u)
        base = [self.vert(c + (u * math.cos(2 * math.pi * i / sides) + w * math.sin(2 * math.pi * i / sides)) * r) for i in range(sides)]
        tip = self.vert(c + n * h)
        for i in range(sides):
            j = (i + 1) % sides
            self.face((base[i], base[j], tip), mat=mat, row=row, lit=(lit[0], lit[0], lit[1]))

    def grid(self, p0, du, dv, nu, nv, mat=0, **kw):
        """A flat grid over p0 + i du + j dv, wound by du x dv."""
        p0, du, dv = Vector(p0), Vector(du), Vector(dv)
        idx = [[self.vert(p0 + du * (i / nu) + dv * (j / nv)) for j in range(nv + 1)] for i in range(nu + 1)]
        for i in range(nu):
            for j in range(nv):
                self.face((idx[i][j], idx[i + 1][j], idx[i + 1][j + 1], idx[i][j + 1]), mat=mat, smooth=True, **kw)

    def lathe_x(self, path, cy=0.0, cz=0.0, seg=72, mat=0, flip=False, uvf=None, smooth=True, spans=None, a0=0.0):
        """Round the x axis through (cy, cz): each span of path [(x, r)...] its own ring of faces, hard between spans.
        Faces point to the left of the path's travel, or the right with flip. uvf(x, r, theta, span_index, along): the UVs."""
        for k, ((x0, r0), (x1, r1)) in enumerate(zip(path, path[1:])):
            if spans is not None and k not in spans:
                continue
            for i in range(seg):
                t0, t1 = a0 + 2 * math.pi * i / seg, a0 + 2 * math.pi * (i + 1) / seg
                pts = [(x0, r0, t0), (x0, r0, t1), (x1, r1, t1), (x1, r1, t0)]
                vi = [self.vert((x, cy + r * math.cos(t), cz + r * math.sin(t))) for x, r, t in pts]
                uv = [uvf(x, r, t, k) for x, r, t in pts] if uvf else None
                self.face(tuple(reversed(vi)) if flip else tuple(vi), mat=mat, uv=list(reversed(uv)) if (flip and uv) else uv, smooth=smooth)

    @property
    def tris(self):
        return sum(len(f['vi']) - 2 for f in self.f)

    def mesh(self, name, mats, litfn=None):
        v = np.array(self.v, float)
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], [f['vi'] for f in self.f])
        for m in mats:
            me.materials.append(m)
        me.polygons.foreach_set('material_index', [f['mat'] for f in self.f])
        me.polygons.foreach_set('use_smooth', [f['smooth'] for f in self.f])
        uvs = []
        for f in self.f:
            pts = v[list(f['vi'])]
            if f['uv'] is not None:
                uvs += [c for co in f['uv'] for c in co]
            elif f['uvf'] is not None:
                uvs += [c for p in pts for c in f['uvf'](p)]
            elif f['row'] is not None:
                n = np.cross(pts[1] - pts[0], pts[-1] - pts[0])
                n = n / max(np.linalg.norm(n), 1e-9)
                for k, p in enumerate(pts):
                    if f['lit'] is None:
                        lit = litfn(p, n) * f['gain']
                    elif isinstance(f['lit'], (int, float)):
                        lit = f['lit']
                    else:
                        lit = f['lit'][k]
                    uvs += [min(max(float(lit), 0.004), 0.996), rowv(f['row'])]
            else:
                uvs += [0.0, 0.0] * len(pts)
        layer = me.uv_layers.new(name='UVMap')
        layer.data.foreach_set('uv', uvs)
        me.update()
        return me


def spill(lamps):
    """A lit-amount function for the ramp, from lamps (position, radius, power) as kit.bake_light's falloff, N.L softened."""
    def fn(p, n):
        tot = 0.0
        for pos, radius, power in lamps:
            d = np.asarray(pos, float) - p
            r2 = float((d * d).sum())
            nl = max(float((d * n).sum()) / math.sqrt(r2 + 1e-6), 0.0) * 0.8 + 0.2
            tot += power * nl / (1 + r2 / (radius * radius)) ** 1.5
        return tot
    return fn


def key_light(direction, floor=0.2, gain=0.6):
    """A lit-amount function for small hardware: a floor plus one soft direction."""
    d = np.asarray(direction, float)
    d = d / np.linalg.norm(d)

    def fn(p, n):
        return floor + gain * max(float((n * d).sum()), 0.0)
    return fn
