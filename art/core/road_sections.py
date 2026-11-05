"""The road through the stairwell and the flooded tunnel (art/core/ASSETS.md: the nine moments, the fixed sizes). Numpy only: runs in
Blender or plain python3 (python3 art/core/road_sections.py prints the summary and writes art/out/city5-road-sections.json).

Lengths are parameters: stair(length), flood(length, start). The flights and tube rings repeat and the moments spread over whatever's
given: every moment is placed by its share of the length. STAIR_LEN / FLOOD_LEN below, or the env vars of the same names, set them.

The format is the existing RoadPath's: `points` [x, y] every `step` 2 m, `length`, `width`, plus, per point:
  heights  the ground under it, m (z, the same frame as the points). At the gap it's the landing below, a cliff: the bike flies off it.
  roll     radians about the direction of travel, right-handed: + is the bike's top over to its right (bike.tsx's lean is the other sign).
  surface  0 floor, 1 steps, 2 wall, 3 air, 4 water
  spray    0..1, how much it throws up (tunnel), scaled by the speed on the site
  fog      0..1, how thick (stair's end)
The 2 m is along the ride's own 3D line, so ride.drive.speed is true speed on a flight or a wall.

The shaft is square, 44 x 44, and turned 45 degrees to the lab's road, because the reference looks down its diagonal (the far corner at the
top of the frame, B5 on the walls either side of it, B4 close on the right, the pipes close on the left). "Local" is the shaft's frame: (a, b)
off its centre, walls at +/-22. The long flight runs straight on from the lab's doors along that diagonal, over the void, to the far corner.
From there the road goes round clockwise, the wall on its left and the void on its right, a flight on each side and a 16 x 16 landing at
each corner. Each side has its own "canon" frame (A, B), side 0's the same as local: the flight runs along -B at A = 14, its wall at A = 22,
top at B = +6, foot at B = -6, the next landing at A, B = 14, -14.
"""
import json
import math
import os

import numpy as np

STEP = 2.0
STAIR_LEN = float(os.environ.get('STAIR_LEN', 900.0))
FLOOD_LEN = float(os.environ.get('FLOOD_LEN', 1540.0))
STAIR_SPEED = 30.0          # the local caps (m/s), what the lean and the leap are worked out for
FLOOD_SPEED = 36.0
GRAVITY = 24.0              # lib/ride.ts JUMP.gravity
ROAD_W = 11.8
# Where it hands over. Both ends are on the lab's straight, y 0, so x is its road's s there.
HALL_X = float(os.environ.get('LAB_END', 4262.0))        # where the flood ends, heading +X, so the hall and chamber only sink: kit.LAB_END, the same env var and default
DOOR_S = HALL_X - 8.0                                    # the lab's doors on its road (kit.LAB door_s)
LAB_STOP_S = DOOR_S - 20.0  # the bike halts here, shut doors ahead: the memory game opens them
BULKHEAD_STOP = 24.0        # and this far short of the shut bulkhead: lib/doors.ts stand

# --- The fixed sizes (ASSETS.md) --------------------------------------------------------------------------------------------
TREAD_RUN, FLIGHT_RUN, FLIGHT_DROP = 1.2, 12.0, 5.0
SLOPE = FLIGHT_DROP / FLIGHT_RUN
RAIL_D = 6.1
LANDING = 16.0
VOID = 6.0                  # half the central void
WALL = 22.0                 # the outer wall's face, off the shaft's centre
SIDE_A = 14.0               # a flight's centreline
LIP_X = DOOR_S + 10.0       # the top of the long flight: the lab's door frame runs 8 past the doors
CORNER_U = WALL * math.sqrt(2)
LONG_FLIGHTS = 4            # flights in the long flight
LONG_END_U = 15.0           # where it comes down, on the far landing: the V of the landing's just its 11.8 wide here
CX = LIP_X + LONG_FLIGHTS * FLIGHT_RUN - LONG_END_U  # the shaft's centre in the lab's frame
CY = 0.0
Z0 = -LONG_FLIGHTS * FLIGHT_DROP                     # the first landing
YAW = -math.pi / 4          # local to world
# The tube
TUBE_R, TUBE_ZC, WATER_UP = 9.0, 5.5, 0.35
RING = 8.0
ROOM_LEN = 70.0
DOOR_OFF = 1.5              # the gap's centre, left of the axis (the opening's 17 across, the door leaves 14 of it, hinged on the right)
HINGE = (1.7, -9.1)         # in the frame's frame, _bulkhead.HINGE; the door's disc centre 9.1 along it, free edge 17.9
DOOR_OPEN_DEG = 78.4        # -9.1 + 17.9 * cos(78.4) = -5.5: a 14 m gap to the opening's far side. Minus about z, into the room: the only way it clears the tube

# --- The first corner: stair_wall_ramp, mirrored to bank to the left, the wall's side: the asset's own section, so the rider's on its surface.
RAMP_B = WALL               # its origin's b: it starts at the far wall, on the first landing, at A = 14, and runs along -B
RAMP_LEN, RAMP_HALF, RAMP_WALL = 24.0, 5.9, 7.6
RAMP_R0, RAMP_RM = RAMP_WALL - RAMP_HALF, RAMP_WALL
WALL_RUN = 3.0
HUG = -3.6                  # moment 4's line: 2.5 off the rail on the flights, 1.4 at the landing's inner corner


def ramp_surface(t, lat):
    """stair_wall_ramp's section t m along, lat m toward the wall: (height, tilt)."""
    u = np.clip(t / RAMP_LEN, 0.0, 1.0)
    r = RAMP_R0 + (RAMP_RM - RAMP_R0) * np.sin(math.pi * u) ** 2
    g = np.clip((lat - (RAMP_WALL - r)) / r, 0.0, 1.0)
    ang = np.arcsin(g)
    return r * (1 - np.cos(ang)), ang


def world(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    c, s = math.cos(YAW), math.sin(YAW)
    return CX + a * c - b * s, CY + a * s + b * c


def canon_to_local(k, A, B):
    """Side k's canon frame to the shaft's: a quarter turn clockwise per side."""
    A, B = np.asarray(A, float), np.asarray(B, float)
    m = k % 4
    if m == 0:
        return A, B
    if m == 1:
        return B, -A
    if m == 2:
        return -A, -B
    return -B, A


def canon_world(k, A, B):
    return world(*canon_to_local(k, A, B))


def canon_yaw(k, yaw=0.0):
    """World yaw of a yaw in side k's canon frame."""
    return yaw - k * math.pi / 2 + YAW


def z_side(k):
    """The landing at the top of side k (L0 the far corner the long flight comes down on)."""
    return Z0 - FLIGHT_DROP * k


def smooth(a, sigma, dx):
    k = int(4 * sigma / dx)
    if k < 1:
        return np.asarray(a, float).copy()
    w = np.exp(-0.5 * (np.arange(-k, k + 1) * dx / sigma) ** 2)
    w /= w.sum()
    return np.convolve(np.pad(a, k, mode='edge'), w, mode='valid')


def _ramp01(x):
    return np.clip(x, 0.0, 1.0)


def _drop(t):
    """How far down a flight's run it's come (0..1), t m past its top: the wheels ride the steps' noses, the line through them 1.2 on from the flight's
    inner corners (rail_12's line), so it reaches the foot's level 1.2 past the foot."""
    return np.clip((np.asarray(t, float) - TREAD_RUN) / FLIGHT_RUN, 0.0, 1.0)


def _seg(p0, p1, dx=0.25):
    n = max(1, int(round(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / dx)))
    t = np.arange(n) / n
    return p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t


def _resample(cols, stepline):
    """Every STEP m of 3D length along `stepline`: index * STEP is metres on the site."""
    d = np.sqrt(np.sum(np.diff(stepline, axis=0) ** 2, axis=1))
    s = np.concatenate([[0.0], np.cumsum(d)])
    n = int(round(s[-1] / STEP))
    si = np.linspace(0.0, s[-1], n + 1)
    return {k: np.interp(si, s, v) for k, v in cols.items()}, s, si


# --- The stairwell ------------------------------------------------------------------------------------------------------------
def moments(n):
    """Which sides the moments fall on, spread by share of the sides. Corner k joins side k to side k + 1."""
    hug = max(3, round(n * 0.2))            # moment 4: the rail on the right round a landing
    jump = max(hug + 3, round(n * 0.33))    # moment 5: the corner before the torn side
    tight = max(jump + 3, round(n * 0.5))   # moment 6: from this side on
    return {'hug': hug, 'jump': jump, 'torn': jump + 1, 'tight': tight, 'n': n}


def _corners(n, mo):
    """(d_in, d_out, R) per corner: how far left of the flight's centre it comes in and leaves (m), and the arc."""
    std = 3.5
    out = [(std, std, 14.0) for _k in range(n - 1)]
    out[0] = (4.0, std, 7.5)                 # after the wall, down on the flight's far end
    h = mo['hug']
    out[h - 1] = (std, HUG, 9.0)
    out[h] = (HUG, HUG, 8.0)                 # (clears the corner of the rails by 1.4)
    out[h + 1] = (HUG, std, 9.0)
    j = mo['jump']
    out[j] = (std, 4.0, 7.0)                 # onto the gap's line, 4 m straight at the edge, with the gap in view
    out[j + 1] = (4.0, 5.0, 5.0)             # the thump, then the corner in what's left of the landing
    out[j + 2] = (5.0, std, 14.0)
    if n - 2 not in (j, j + 1, j + 2):
        out[n - 2] = (std, 0.0, 14.0)        # square on to the way out
    return out


def _z_corner(k, A, B, mo):
    """The ground in corner k's canon frame: its side's flight, the landing, the next flight. The torn side's a cliff at the edge."""
    top = z_side(k)
    if k == mo['torn']:
        fb = (B < VOID).astype(float)
    else:
        fb = _drop(VOID - B)
    if k == mo['jump']:
        fa = (A < VOID).astype(float)
    else:
        fa = _drop(VOID - A)
    return top - FLIGHT_DROP * fb - FLIGHT_DROP * fa


def _stair_line(n, m_out):
    mo = moments(n)
    corners = _corners(n, mo)
    dx = 0.25
    X, Y, Z, RL, TAG = [], [], [], [], []   # world x, y, ground z, the surface's own tilt, 0/1/2 (flat/steps/wall)

    def add(x, y, z, rl=None, tag=0):
        X.append(np.asarray(x, float))
        Y.append(np.asarray(y, float))
        Z.append(np.asarray(z, float))
        RL.append(np.zeros(np.size(x)) if rl is None else np.asarray(rl, float))
        TAG.append(np.full(np.size(x), tag, float))

    # 1. Out of the lab's doors: level to the lip, then the long flight.
    x = np.arange(DOOR_S, LIP_X, dx)
    add(x, np.zeros_like(x), np.zeros_like(x))
    x = np.arange(LIP_X, LIP_X + LONG_FLIGHTS * FLIGHT_RUN, dx)
    add(x, np.zeros_like(x), -np.maximum(x - LIP_X - TREAD_RUN, 0.0) * SLOPE, tag=1)
    s_long_end = sum(np.size(a) for a in X)

    # 3. The first corner: no turn. A right-hand arc that's all on the ramp's rise, its tilt the ramp's, then down to the flight's far end.
    p0 = LONG_END_U / math.sqrt(2)
    A_WALL = SIDE_A + RAMP_WALL   # on the ramp's road where it's reached the wall, 90 degrees over
    R = (A_WALL - p0) / (1 + math.sqrt(0.5))
    cen = (p0 + R * math.sqrt(0.5), p0 - R * math.sqrt(0.5))
    th = np.arange(0.0, 1.0, dx / (R * 3 * math.pi / 4)) * (3 * math.pi / 4)
    # (From heading (1, 1)/root2 turning right: the centre's to the right, the start at angle 135 degrees from it.)
    a0 = 3 * math.pi / 4
    ar_a = cen[0] + R * np.cos(a0 - th)
    ar_b = cen[1] + R * np.sin(a0 - th)
    h, ang = ramp_surface(RAMP_B - ar_b, ar_a - SIDE_A)
    wx, wy = world(ar_a, ar_b)
    add(wx, wy, Z0 + h, ang, tag=2)
    # On the wall, past the stencil, a few metres of it.
    a1, b1, z1 = ar_a[-1], ar_b[-1], Z0 + h[-1]
    b_off = b1 - WALL_RUN
    bw = np.arange(b1, b_off, -dx)
    zw = z1 - 0.8 * (b1 - bw) / WALL_RUN
    wx, wy = world(np.full_like(bw, a1), bw)
    add(wx, wy, zw, np.full_like(bw, ang[-1]), tag=2)
    # The dive: off the wall, over where the flight's outer rail's left off, down onto the flight's foot.
    z1, r1 = zw[-1], ang[-1]
    a2, b2 = SIDE_A + 4.0, -VOID - 2.0
    z2 = Z0 - FLIGHT_DROP
    L = math.hypot(a2 - a1, b2 - b_off)
    u = np.arange(0.0, 1.0, dx / L)
    k = (b_off - b2) / 3
    pa = [a1, a1, a2, a2]
    pb = [b_off, b_off - k, b2 + k, b2]
    bz = lambda c: (1 - u) ** 3 * c[0] + 3 * (1 - u) ** 2 * u * c[1] + 3 * (1 - u) * u ** 2 * c[2] + u ** 3 * c[3]  # noqa: E731
    da, db = bz(pa), bz(pb)
    s3 = u * u * (3 - 2 * u)
    dz = z1 + (z2 - z1) * s3
    wx, wy = world(da, db)
    add(wx, wy, dz, r1 * (1 - s3), tag=2)

    # The ring: corner by corner, each from the middle of its side to the middle of the next. (Corner 0 from where the dive lands.)
    ring0 = sum(np.size(a) for a in X)
    air = []
    for k in range(n - 1):
        d_in, d_out, Rk = corners[k]
        A_in = SIDE_A + d_in
        b_out = -SIDE_A - d_out
        pts_a, pts_b = [], []
        start = (A_in, -VOID - 2.0) if k == 0 else (A_in, 0.0)
        arc_s = (A_in, b_out + Rk)
        if start[1] > arc_s[1]:
            sa, sb = _seg(start, arc_s)
            pts_a.append(sa)
            pts_b.append(sb)
        nn = max(4, int(Rk * (math.pi / 2) / dx))
        al = np.arange(nn) / nn * (math.pi / 2)
        cA, cB = A_in - Rk, b_out + Rk
        pts_a.append(cA + Rk * np.cos(al))
        pts_b.append(cB - Rk * np.sin(al))
        sa, sb = _seg((A_in - Rk, b_out), (0.0, b_out))
        pts_a.append(sa)
        pts_b.append(sb)
        A, B = np.concatenate(pts_a), np.concatenate(pts_b)
        zz = _z_corner(k, A, B, mo)
        wx, wy = canon_world(k, A, B)
        tag = np.where(((B < VOID) & (B > -VOID) & (A > 0)) | ((A < VOID) & (A > -VOID) & (B < 0)), 1.0, 0.0)
        add(wx, wy, zz)
        TAG[-1] = tag
    # 7. The last side, on across the landing and through the wall: the way out, a chain of flights down to the deck.
    k = n - 1
    d = corners[n - 2][1]
    B_end = -WALL - m_out * FLIGHT_RUN - TREAD_RUN
    B = np.arange(0.0, B_end, -dx)
    A = np.full_like(B, SIDE_A + d)
    # (d's eased out to the centre over the landing.)
    A = SIDE_A + d * (1 - _ramp01((-B - VOID) / LANDING))
    zz = z_side(k) - FLIGHT_DROP * _drop(VOID - B) - np.maximum(-B - WALL - TREAD_RUN, 0.0) * SLOPE
    wx, wy = canon_world(k, A, B)
    add(wx, wy, zz)
    TAG[-1] = np.where(((B < VOID) & (B > -VOID)) | (B < -WALL), 1.0, 0.0)
    xe, ye = canon_world(k, SIDE_A, B_end)
    deck = z_side(k) - FLIGHT_DROP - m_out * FLIGHT_DROP
    add(np.array([xe]), np.array([ye]), np.array([deck]))

    x, y, z, rl, tag = (np.concatenate(v) for v in (X, Y, Z, RL, TAG))
    # Plan smoothed a little from the first landing on (the kinks of arc to straight), so the heading's continuous.
    sx, sy = smooth(x, 1.2, dx), smooth(y, 1.2, dx)
    w = _ramp01((np.arange(len(x)) - (ring0 - 30)) / 30.0)
    x, y = x * (1 - w) + sx * w, y * (1 - w) + sy * w
    raw_x, raw_y = np.concatenate(X), np.concatenate(Y)
    x[:s_long_end], y[:s_long_end] = raw_x[:s_long_end], raw_y[:s_long_end]
    x[-40:], y[-40:] = raw_x[-40:], raw_y[-40:]   # (the way out's straight, and ends exactly where the flood starts)

    # The leap: off the landing's edge level, under JUMP.gravity at the local cap, down to where it meets the landing below.
    fly = z.copy()
    plan = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])
    drops = np.nonzero(np.diff(z[ring0:]) < -1.0)[0]
    if len(drops):
        i0 = ring0 + drops[0]
        d_ = plan - plan[i0]
        tr = z[i0] - 0.5 * GRAVITY * (d_ / STAIR_SPEED) ** 2
        j = i0 + 1
        while j < len(z) and tr[j] > z[j]:
            fly[j] = tr[j]
            j += 1
        air.append((i0, j))
        tag[i0:j] = 3
    res, _s, si = _resample({'x': x, 'y': y, 'z': z, 'fly': fly, 'rl': rl, 'tag': tag, 'plan': plan}, np.stack([x, y, fly], axis=1))
    # Roll: the surface's tilt on the wall; on the flat, leaning into the turn, 14 degrees at most (the camera goes with it).
    hx, hy = res['x'], res['y']
    head = np.unwrap(np.arctan2(np.gradient(hy), np.gradient(hx)))
    ds = np.maximum(np.hypot(np.gradient(hx), np.gradient(hy)), 1e-3)
    kappa = smooth(-np.gradient(head) / ds, 2.0, STEP)   # + is a right-hand turn
    lean = np.clip(np.arctan(STAIR_SPEED ** 2 * kappa / 9.8), -math.radians(14), math.radians(14))
    lean = smooth(lean, 2.0, STEP)
    onwall = res['tag'] == 2
    roll = smooth(np.maximum(res['rl'], lean * ~onwall), 1.0, STEP)
    roll[res['tag'] == 3] *= 0.3
    length = STEP * (len(si) - 1)
    # Surface. Where it came out at the resample.
    surf = np.where(res['tag'] > 2.5, 3, np.where(res['tag'] > 1.5, 2, np.where(res['tag'] > 0.5, 1, 0))).astype(int)
    road = dict(res)
    road.update({'length': length, 'n': n, 'm_out': m_out, 'mo': mo, 'corners': corners, 'roll': roll, 'surface': surf,
                 'deck': deck, 'fx': np.arange(len(si)) * STEP, 'heading_out': canon_yaw(n - 1, -math.pi / 2), 'end': (float(xe), float(ye))})
    # Fog: the last eighth thickens to the water; the level's own fog before that.
    road['fog'] = _ramp01((road['fx'] / length - 0.86) / 0.14)
    # Air, in metres.
    road['air'] = []
    if surf.max() == 3:
        idx = np.nonzero(surf == 3)[0]
        road['air'].append([float(idx[0] * STEP), float((idx[-1] + 1) * STEP)])
    return road


def stair(length=None):
    """The stairwell at (about) this length: as many laps as fit, and the way out's flights make up the rest."""
    length = STAIR_LEN if length is None else length
    best = None
    n0 = int((length - 60.0) / 29.0)
    for n in range(max(10, n0 - 8), n0 + 9):
        if n % 4 != 2:      # (side n - 1 must be a south one, heading out through the west wall: the tube's way back to the hall)
            continue
        for m in range(3, 13):
            r = _stair_line(n, m)
            e = abs(r['length'] - length)
            if best is None or e < best[0]:
                best = (e, r)
    return best[1]


def s_of_side(road, k, B=0.0, d=0.0):
    """How far along the road side k's canon (SIDE_A + d, B) is."""
    x, y = canon_world(k, SIDE_A + d, B)
    z = z_side(k) - FLIGHT_DROP * _drop(VOID - B)
    p = np.stack([road['x'], road['y'], road['z']], axis=1)
    return float(np.argmin(np.sum((p - np.array([x, y, z])) ** 2, axis=1)) * STEP)


# --- The flood ------------------------------------------------------------------------------------------------------------------
def _seq_trace(seq, x, y, h, step=0.25):
    xs, ys, hs = [x], [y], [h]
    for sg in seq:
        if sg[0] == 'S':
            n = max(1, round(abs(sg[1]) / step))
            for _i in range(n):
                x += sg[1] / n * math.cos(h)
                y += sg[1] / n * math.sin(h)
                xs.append(x)
                ys.append(y)
                hs.append(h)
        else:
            R, d = sg[1], math.radians(sg[2])
            n = max(2, round(abs(d) * R / step))
            st = d / n
            ln = 2 * R * math.sin(abs(st) / 2)
            for _i in range(n):
                h += st / 2
                x += ln * math.cos(h)
                y += ln * math.sin(h)
                h += st / 2
                xs.append(x)
                ys.append(y)
                hs.append(h)
    return np.array(xs), np.array(ys), np.array(hs)


WALL_R = 100.0     # the bend it goes up the wall on (lateral 13 m/s2 at 36: banked 53 degrees; 4.6 degrees a ring, the rings hold 5)
EASY_R = 220.0


def _flood_seq(L1, start, h0, EASY_R=EASY_R):
    """From the stair's way out (north-west) round to the left, away from the hall, south and back east along y 0: nothing crosses. The first
    straight's given; the south leg brings it down to y 0 and the last straight runs on to the hall."""
    a_wall = 70.0
    a_easy = 270.0 - math.degrees(h0) - a_wall
    seq = [['S', L1], ['A', EASY_R, a_easy], ['A', WALL_R, a_wall], ['S', 0.0], ['A', EASY_R, 90.0], ['S', 0.0]]
    xs, ys, _h = _seq_trace(seq, start[0], start[1], h0)
    seq[3][1] = float(ys[-1])
    seq[5][1] = float(HALL_X - xs[-1])
    return seq


def flood(length=None, start=None, heading=None, deck=None):
    """The tube at this length, from the stair's foot, ending at the hall's start. The first straight takes up the length."""
    length = FLOOD_LEN if length is None else length
    if start is None:
        r = stair()
        start, heading, deck = r['end'], r['heading_out'], r['deck']
    h0 = heading % (2 * math.pi)

    def tot(L1, easy):
        seq = _flood_seq(L1, start, h0, easy)
        return sum(s[1] if s[0] == 'S' else abs(math.radians(s[2])) * s[1] for s in seq), seq

    extra = 10.0   # (what the line up the wall and through the gap adds to the axis)
    seq = None
    for easy in (EASY_R, 180.0, 150.0, 120.0, 100.0):   # (a shorter tube, tighter easy bends: the rings hold 5 degrees, so no tighter than the wall's)
        lo, hi = 0.0, 4000.0
        for _i in range(50):
            mid = (lo + hi) / 2
            t, _seq = tot(mid, easy)
            if t + extra < length:
                lo = mid
            else:
                hi = mid
        _t, cand = tot(hi, easy)
        if cand[3][1] >= 0 and cand[5][1] >= ROOM_LEN + BULKHEAD_STOP + 60.0:
            seq = cand
            break
    if seq is None:
        raise ValueError(f'flood at {length} m: too short for its bends, the stop and the room')
    ax, ay, ah = _seq_trace(seq, start[0], start[1], h0)
    sa = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(ax), np.diff(ay)))])
    # The bends' extents.
    marks = []
    a = 0.0
    for sg in seq:
        ln = sg[1] if sg[0] == 'S' else abs(math.radians(sg[2])) * sg[1]
        marks.append((a, a + ln, sg))
        a += ln
    wall_a = marks[2]
    L_axis = sa[-1]
    door = L_axis - ROOM_LEN
    # 8: up the wall on the R 100 bend (a left-hander: the outside's its right): the tilt climbs the tube's circle to 80 degrees and back.
    c = (wall_a[0] + wall_a[1]) / 2
    half = (wall_a[1] - wall_a[0]) / 2
    q = _ramp01(1 - np.abs(sa - c) / (half + 10.0))
    q = q * q * (3 - 2 * q)
    phi = q * math.radians(80.0)
    # In the deck's flat part (under water) it slides across to the wall's foot; the roll's the same q.
    # (Riding on the ribs' tops, 0.6 inside the wall, so its radius 8.4.)
    rr = TUBE_R - 0.6
    phi1 = math.acos(TUBE_ZC / rr)
    dlat = np.where(phi < phi1, phi / phi1 * rr * math.sin(phi1), rr * np.sin(phi))
    hup = np.where(phi < phi1, 0.0, TUBE_ZC - rr * np.cos(phi))
    # (On a road with a line through the gap: left of the axis on the way up to the door, back to the centre in the room.)
    thread = _ramp01((sa - (door - 90.0)) / 40.0) * (1 - _ramp01((sa - (door + 12.0)) / 40.0))
    dline = -dlat + DOOR_OFF * thread * thread * (3 - 2 * thread)
    nx, ny = -np.sin(ah), np.cos(ah)
    sill = 0.6 * _ramp01((sa - (door - 8.0)) / 8.0) * (1 - _ramp01((sa - (door + 4.0)) / 30.0))
    X = ax + nx * dline
    Y = ay + ny * dline
    Z = deck + hup + sill
    res, _s, si = _resample({'x': X, 'y': Y, 'z': Z, 'phi': phi, 'sa': sa, 'hup': hup, 'sill': sill}, np.stack([X, Y, Z], axis=1))
    fx = np.arange(len(si)) * STEP
    head = np.unwrap(np.arctan2(np.gradient(res['y']), np.gradient(res['x'])))
    ds = np.maximum(np.hypot(np.gradient(res['x']), np.gradient(res['y'])), 1e-3)
    kappa = smooth(-np.gradient(head) / ds, 3.0, STEP)
    lean = np.clip(np.arctan(FLOOD_SPEED ** 2 * kappa / 9.8), -math.radians(25), math.radians(25))
    roll = smooth(np.minimum(-res['phi'], lean), 2.0, STEP)
    water_top = deck + WATER_UP
    wet = (res['z'] < water_top) & (res['sa'] < door + 1.5)
    surface = np.where(res['phi'] > math.radians(40), 2, np.where(wet, 4, 0)).astype(int)
    spray = _ramp01(1 - (res['z'] - water_top + 0.1) / 0.9) * (res['sa'] < door + 1.5)
    door_s = float(np.interp(door, res['sa'], fx))
    road = dict(res)
    road.update({'length': STEP * (len(si) - 1), 'fx': fx, 'roll': roll, 'surface': surface, 'spray': spray, 'deck': deck,
                 'axis': (ax, ay, ah, sa), 'seq': seq, 'door_sa': door, 'door_s': door_s, 'stop_s': door_s - BULKHEAD_STOP, 'L_axis': L_axis,
                 'wall_s': [float(np.interp(wall_a[0] - 10, res['sa'], fx)), float(np.interp(wall_a[1] + 10, res['sa'], fx))],
                 'water_to_s': float(np.interp(door + 1.5, res['sa'], fx)), 'fog': np.zeros_like(fx)})
    return road


def axis_at(road, a):
    ax, ay, ah, sa = road['axis']
    return float(np.interp(a, sa, ax)), float(np.interp(a, sa, ay)), float(np.interp(a, sa, ah))


# --- Reading a line --------------------------------------------------------------------------------------------------------------
def at(road, s):
    """(contact, flying point, direction of travel, up, right) at s, numpy vectors. Up and right carry the roll."""
    fx = road['fx']
    f = road.get('fly', road['z'])
    g = lambda r: np.array([np.interp(r, fx, road['x']), np.interp(r, fx, road['y']), np.interp(r, fx, f)])  # noqa: E731
    p = g(s)
    t = g(s + 3.0) - g(s - 3.0)
    t /= max(np.linalg.norm(t), 1e-6)
    right0 = np.cross(t, [0, 0, 1.0])
    right0 /= max(np.linalg.norm(right0), 1e-6)
    up0 = np.cross(right0, t)
    r = float(np.interp(s, fx, road['roll']))
    up = up0 * math.cos(r) + right0 * math.sin(r)
    right = right0 * math.cos(r) - up0 * math.sin(r)
    c = np.array([p[0], p[1], np.interp(s, fx, road['z'])])
    return c, p, t, up, right


def payload(road, s0):
    fx_step = STEP
    out = {
        'points': [[round(float(a), 3), round(float(b), 3)] for a, b in zip(road['x'], road['y'])],
        'length': round(float(road['length']), 2),
        'step': fx_step,
        'width': ROAD_W,
        'heights': [round(float(z), 3) for z in road['z']],
        'roll': [round(float(r), 4) for r in road['roll']],
        'surface': [int(v) for v in road['surface']],
        'fog': [round(float(v), 2) for v in road['fog']],
        's0': round(float(s0), 2),
    }
    if 'spray' in road:
        out['spray'] = [round(float(v), 2) for v in road['spray']]
    if 'air' in road:
        out['air'] = [[round(a + s0, 1), round(b + s0, 1)] for a, b in road['air']]
    return out


def summary():
    a = stair()
    b = flood(start=a['end'], heading=a['heading_out'], deck=a['deck'])
    return {
        'stair': {'length': a['length'], 'seconds_at_30': a['length'] / STAIR_SPEED, 'sides': a['n'], 'laps': a['n'] / 4, 'way_out_flights': a['m_out'],
                  'drop': -a['deck'], 'moments': a['mo'], 'air_m': a['air'], 'max_roll_deg': float(np.degrees(a['roll'].max())),
                  'share_wall': float(np.mean(a['surface'] == 2)), 'end': a['end'], 'heading_out_deg': math.degrees(a['heading_out'])},
        'flood': {'length': b['length'], 'seconds_at_36': b['length'] / FLOOD_SPEED, 'door_s': b['door_s'], 'stop_s': b['stop_s'], 'wall_s': b['wall_s'],
                  'seq': b['seq'], 'max_roll_deg': float(np.degrees(np.abs(b['roll']).max())), 'share_wall': float(np.mean(b['surface'] == 2)),
                  'end': (float(b['x'][-1]), float(b['y'][-1]), float(b['z'][-1]))},
        'joins': {'door_start': (float(a['x'][0]), float(a['y'][0]), float(a['z'][0])), 'stair_end': (float(a['x'][-1]), float(a['y'][-1]), float(a['z'][-1])),
                  'flood_start': (float(b['x'][0]), float(b['y'][0]), float(b['z'][0]))},
    }


if __name__ == '__main__':
    import sys
    print(json.dumps(summary(), indent=1, default=float))
    _ = sys
