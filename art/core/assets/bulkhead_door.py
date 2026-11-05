"""bulkhead_door: the round rusted door, 17.6 across, 1.6 thick, with ribs and a brass wheel (concept-flooded-tunnel).

Origin: on the hinge's axis, at the disc's centre height, so it goes at z 5.5 over the deck, at bulkhead_frame's DoorHinge. Modelled
shut, as it starts: the disc's centre at +Y 9.1, its wheel side facing -X (up the road, at the rider), free edge at +Y 17.9. Turn it
about z to open it: minus swings the free edge away down the road into the room, -55 degrees as the image shows it half open, -81
right open, leaving the road its 14 m gap (_bulkhead.YAW_HALF, YAW_OPEN). Painted lit (art/core/assets/_bulkhead.py).

Children of the door, so they swing with it:
  bulkhead_wheel: the brass wheel, origin at its centre. Turn it about its local x, a step at each win.
  bulkhead_lamp_1 to 4: the win lamps round the ring, each its own material (City5BulkheadLamp<n>Red), off as exported, in the brass
    look's colours (lib/doors.ts). The site lights one by raising that material's emissiveIntensity, or swapping its material.
"""
import math
import os
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bulkhead as H  # noqa: E402
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'bulkhead_door'
PAINT, RAMP = 0, 1
T = H.DOOR_T / 2
CY = H.DOOR_CY
X_FACE = -0.42     # the recessed face, under the raised ring at -T
X_RIB = -0.74
X_RIM = -2.05    # the wheel's plane
LAMP_R = (7.62, 8.4)
LAMP_SPAN = 34.0
# The win lamps, in order, left to right as the rider faces the door (degrees round from +Y, the free edge, toward the crown); all clear of the water.
LAMP_AT = (-18.0, 55.0, 125.0, 198.0)


def uv_door(p):
    # (A touch of x, so the rim isn't one stretched line of the paint.)
    return ((p[1] - CY) / H.DOOR_D + 0.5 + p[0] * 0.004, p[2] / H.DOOR_D + 0.5 + p[0] * 0.012)


def build(kit, m):
    b = H.B()
    # The disc, centre of the face out round the rim to the back. The path's faces point left of travel: outward.
    r = H.DOOR_D / 2
    path = [(X_FACE, H.RING_IN), (-0.62, H.RING_IN + 0.04), (-T, H.RING_IN + 0.2), (-T, 8.06), (-T + 0.08, 8.1), (-T, 8.14),
            (-T, r - 0.3), (-T + 0.2, r), (T - 0.15, r), (T, r - 0.2), (T, 7.9), (T - 0.3, 7.7)]
    b.lathe_x(path, CY, 0.0, seg=72, mat=PAINT, uvf=lambda x, rr, t, k: uv_door((x, CY + rr * math.cos(t), rr * math.sin(t))))
    n = 48
    circ = lambda x, rr: [(x, CY + rr * math.cos(2 * math.pi * i / n), rr * math.sin(2 * math.pi * i / n)) for i in range(n)]
    # (Wound to face -X and +X.)
    b.poly(circ(X_FACE, H.RING_IN), mat=PAINT, uvf=uv_door)
    b.poly(list(reversed(circ(T - 0.3, 7.7))), mat=PAINT, uvf=uv_door)

    rib_hi = X_RIB
    rib_h = X_FACE - rib_hi
    # The ribs, a grid across the face, ends in the ring.
    for yr in H.RIBS_Y:
        half = math.sqrt(H.RING_IN ** 2 - yr ** 2) - 0.05
        b.box((X_FACE - rib_h / 2, CY + yr, 0), (rib_h, H.RIB_W, 2 * half), mat=PAINT, uvf=uv_door, skip=('+x',))
    for zr in H.RIBS_Z:
        half = math.sqrt(H.RING_IN ** 2 - zr ** 2) - 0.05
        b.box((X_FACE - rib_h / 2, CY, zr), (rib_h, 2 * half, H.RIB_W), mat=PAINT, uvf=uv_door, skip=('+x',))
    # The ribs on the back, plainer.
    for yr in (-4.0, 0.0, 4.0):
        half = math.sqrt(7.6 ** 2 - yr ** 2)
        b.box((T - 0.22, CY + yr, 0), (0.45, 0.45, 2 * half), mat=RAMP, row=H.IRON, lit=0.28, skip=('-x',))
    for zr in (-4.0, 0.0, 4.0):
        half = math.sqrt(7.6 ** 2 - zr ** 2)
        b.box((T - 0.22, CY, zr), (0.45, 2 * half, 0.45), mat=RAMP, row=H.IRON, lit=0.28, skip=('-x',))
    # Gusset plates where they cross.
    key = H.key_light((-0.5, 0.75, 0.45), 0.2, 0.42)
    for yr in H.RIBS_Y:
        for zr in H.RIBS_Z:
            if yr * yr + zr * zr < 6.9 ** 2:
                b.box((rib_hi - 0.05, CY + yr, zr), (0.1, 0.95, 0.95), mat=PAINT, uvf=uv_door, skip=('+x',))

    rust = key
    # Rivets: two rows round the ring, along the ribs.
    for rad, cnt in ((8.56, 72), (7.32, 54)):
        for i in range(cnt):
            th = 2 * math.pi * (i + 0.5) / cnt
            cy, cz = rad * math.cos(th), rad * math.sin(th)
            bright = 0.55 + 0.35 * max(cy / rad, 0)
            b.rivet((-T, CY + cy, cz), (-1, 0, 0), r=0.13, h=0.1, mat=RAMP, row=H.RUST, lit=(0.1, bright))
    for yr in H.RIBS_Y:
        half = math.sqrt(H.RING_IN ** 2 - yr ** 2) - 0.3
        steps = int(2 * half / 1.7)
        for k in range(steps + 1):
            b.rivet((rib_hi, CY + yr, -half + 2 * half * k / max(steps, 1)), (-1, 0, 0), r=0.1, h=0.07, mat=RAMP, row=H.RUST, lit=(0.07, 0.45))
    for zr in H.RIBS_Z:
        half = math.sqrt(H.RING_IN ** 2 - zr ** 2) - 0.3
        steps = int(2 * half / 1.7)
        for k in range(steps + 1):
            b.rivet((rib_hi, CY - half + 2 * half * k / max(steps, 1), zr), (-1, 0, 0), r=0.1, h=0.07, mat=RAMP, row=H.RUST, lit=(0.07, 0.45))

    # The wheel's boss and shaft stay on the door; the wheel's its own object (build_wheel).
    wy, wz = CY + H.WHEEL[0], H.WHEEL[1]
    x_rim = X_RIM
    boss = [(X_FACE, 1.0), (X_FACE - 0.18, 1.0), (X_FACE - 0.3, 0.62), (X_FACE - 0.82, 0.42), (x_rim + 0.25, 0.3)]
    for k, ((x0, r0), (x1, r1)) in enumerate(zip(boss, boss[1:])):
        for i in range(12):
            a0, a1 = 2 * math.pi * i / 12, 2 * math.pi * (i + 1) / 12
            b.poly([(x0, wy + r0 * math.cos(a0), wz + r0 * math.sin(a0)), (x0, wy + r0 * math.cos(a1), wz + r0 * math.sin(a1)),
                    (x1, wy + r1 * math.cos(a1), wz + r1 * math.sin(a1)), (x1, wy + r1 * math.cos(a0), wz + r1 * math.sin(a0))],
                   mat=RAMP, row=H.IRON, gain=1.0, smooth=True)
    # The latch: a bracket bolted on the ring at the free edge, its bar back to the wheel's shaft, as in the image.
    bx = -T - 0.24
    by = CY + 7.85
    b.box((bx, by, wz), (0.5, 1.15, 2.7), mat=RAMP, row=H.IRON, gain=1.15)
    b.box((bx - 0.32, by - 0.08, wz), (0.2, 0.62, 1.5), mat=RAMP, row=H.IRON, gain=1.2)
    b.rod((x_rim + 0.75, by - 0.2, wz), (x_rim + 0.75, wy, wz), 0.26, sides=6, mat=RAMP, row=H.IRON, gain=1.2, smooth=True)
    for sy, sz in ((-0.4, -1.1), (0.4, -1.1), (-0.4, 1.1), (0.4, 1.1), (-0.4, 0), (0.4, 0)):
        b.rivet((bx - 0.25, by + sy, wz + sz), (-1, 0, 0), r=0.12, h=0.1, mat=RAMP, row=H.BRASS, lit=(0.08, 0.5))

    # Dogs on the ring: chunky clamps round the rim.
    for deg in (20.0, 90.0, 160.0, 228.0, 270.0, 312.0):
        a = math.radians(deg)
        er = Vector((0, math.cos(a), math.sin(a)))
        et = Vector((0, -math.sin(a), math.cos(a)))
        c = Vector((-T - 0.22, CY, 0)) + er * 8.2
        b.box(c, (0.44, 0.9, 1.5), mat=RAMP, axes=(Vector((1, 0, 0)), er, et), row=H.IRON, gain=1.0)
    # The hinge: post on the axis, two straps across the ring to the disc.
    b.rod((0, 0, -6.4), (0, 0, 6.4), 0.42, sides=8, mat=RAMP, row=H.IRON, gain=1.0, smooth=True)
    for sz in (-4.9, 4.9):
        chord = CY - math.sqrt(r ** 2 - sz ** 2)
        b.box((-T - 0.14, (chord + 1.6) / 2, sz), (0.3, chord + 1.6, 1.0), mat=RAMP, row=H.IRON, gain=1.0)
        b.box((0.0, chord / 2, sz), (1.5, chord + 0.3, 0.7), mat=RAMP, row=H.IRON, gain=0.85)
        b.rod((0, 0, sz - 1.0), (0, 0, sz + 1.0), 0.62, sides=8, mat=RAMP, row=H.IRON, gain=1.1, smooth=True)

    _ = rust
    lamp_housings(b)
    me = b.mesh(NAME, [m['bulkhead_door'], m['bulkhead_ramp']], key)
    # (Base colour only: the hemisphere's small share. Red from the room on the free edge.)
    kit.bake_light(me, [((-3.0, 22.0, 0.0), (1.0, 0.2, 0.1), 7.0, 0.6)], ambient=(0.4, 0.42, 0.38))
    return me


def build_wheel(kit, m):
    """The wheel, in its own frame: origin at its centre, turning about x."""
    b = H.B()
    wy, wz = 0.0, 0.0
    x_rim = 0.0
    hub = [(x_rim + 0.28, 0.42), (x_rim + 0.1, 0.46), (x_rim - 0.12, 0.34), (x_rim - 0.2, 0.0)]
    for (x0, r0), (x1, r1) in zip(hub, hub[1:]):
        for i in range(12):
            a0, a1 = 2 * math.pi * i / 12, 2 * math.pi * (i + 1) / 12
            b.poly([(x0, wy + r0 * math.cos(a0), wz + r0 * math.sin(a0)), (x0, wy + r0 * math.cos(a1), wz + r0 * math.sin(a1)),
                    (x1, wy + r1 * math.cos(a1), wz + r1 * math.sin(a1)), (x1, wy + r1 * math.cos(a0), wz + r1 * math.sin(a0))],
                   mat=RAMP, row=H.BRASS, smooth=True)
    # Rim: a flattened ring, lit per vertex by its own round normal.
    L = Vector((-0.45, 0.72, 0.52)).normalized()
    seg, side = 40, 6
    verts = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        er = Vector((0, math.cos(a), math.sin(a)))
        for j in range(side):
            s = 2 * math.pi * j / side
            nrm = er * math.cos(s) + Vector((-1, 0, 0)) * math.sin(s)
            p = Vector((x_rim, wy, wz)) + er * (H.WHEEL_R + 0.17 * math.cos(s)) + Vector((-1, 0, 0)) * 0.13 * math.sin(s)
            lit = 0.3 + 0.62 * max(nrm.dot(L), 0.0) ** 1.6 + 0.1 * math.sin(a * 3.0 + 1.0)
            verts.append((b.vert(p), lit))
    for i in range(seg):
        i2 = (i + 1) % seg
        for j in range(side):
            j2 = (j + 1) % side
            q = [(i, j), (i2, j), (i2, j2), (i, j2)]
            ids = [verts[a * side + c] for a, c in q]
            b.face(tuple(k[0] for k in ids), mat=RAMP, row=H.BRASS, lit=[k[1] for k in ids], smooth=True)
    # Spokes.
    brass = H.key_light((-0.45, 0.72, 0.52), 0.42, 0.45)
    for i in range(9):
        a = 2 * math.pi * (i + 0.3) / 9
        d = Vector((0, math.cos(a), math.sin(a)))
        c = Vector((x_rim, wy, wz))
        b.rod(c + d * 0.3, c + d * (H.WHEEL_R - 0.05), 0.075, sides=4, mat=RAMP, caps=False, row=H.BRASS, gain=1.0)

    me = b.mesh('bulkhead_wheel', [m['bulkhead_ramp']], H.key_light((-0.45, 0.72, 0.52), 0.42, 0.45))
    return me


def wheel_at():
    return (X_RIM, CY + H.WHEEL[0], H.WHEEL[1])


def build_lamp(kit, m, i):
    """One win lamp: a curved bar on the ring, in the door's frame (so it sits where it's parented)."""
    b = H.B()
    deg = LAMP_AT[i - 1]
    r0, r1 = LAMP_R
    n = 7
    x = -T - 0.2
    ring = lambda r, t: (x, CY + r * math.cos(t), r * math.sin(t))
    for k in range(n):
        t0 = math.radians(deg - LAMP_SPAN / 2 + LAMP_SPAN * k / n)
        t1 = math.radians(deg - LAMP_SPAN / 2 + LAMP_SPAN * (k + 1) / n)
        b.poly([ring(r0, t1), ring(r1, t1), ring(r1, t0), ring(r0, t0)], mat=0)
    return b.mesh(f'bulkhead_lamp_{i}', [m[f'bulkhead_lamp_{i}']], None)


def lamp_housings(b):
    """Dark steel round each lamp's bar, part of the door, so an unlit lamp still reads as a fitting."""
    r0, r1 = LAMP_R[0] - 0.14, LAMP_R[1] + 0.14
    x0, x1 = -T, -T - 0.18
    n = 7
    for deg in LAMP_AT:
        span = LAMP_SPAN + 3.0
        for k in range(n):
            t0 = math.radians(deg - span / 2 + span * k / n)
            t1 = math.radians(deg - span / 2 + span * (k + 1) / n)
            for ra, xa, rb, xb, lit in ((r0, x0, r0, x1, 0.3), (r1, x0, r1, x1, 0.3), (r0, x1, r1, x1, 0.14)):
                b.poly([(xa, CY + ra * math.cos(t0), ra * math.sin(t0)), (xa, CY + ra * math.cos(t1), ra * math.sin(t1)),
                        (xb, CY + rb * math.cos(t1), rb * math.sin(t1)), (xb, CY + rb * math.cos(t0), rb * math.sin(t0))],
                       mat=RAMP, row=H.IRON, lit=lit)
        for sgn in (-1, 1):
            t = math.radians(deg + sgn * span / 2)
            b.poly([(x0, CY + r0 * math.cos(t), r0 * math.sin(t)), (x0, CY + r1 * math.cos(t), r1 * math.sin(t)),
                    (x1, CY + r1 * math.cos(t), r1 * math.sin(t)), (x1, CY + r0 * math.cos(t), r0 * math.sin(t))],
                   mat=RAMP, row=H.IRON, lit=0.22)


def place(kit, m, loc=(0, 0, 0), yaw=0.0):
    """The door and its children into the scene."""
    door = A.obj(build(kit, m), NAME, loc)
    door.rotation_euler = (0, 0, yaw)
    wheel = A.obj(build_wheel(kit, m), 'bulkhead_wheel', wheel_at())
    wheel.parent = door
    for i in (1, 2, 3, 4):
        lamp = A.obj(build_lamp(kit, m, i), f'bulkhead_lamp_{i}')
        lamp.parent = door
    return door


if __name__ == '__main__':
    kit = A.begin()
    H.register(kit)
    m = _mats.mats(kit)
    place(kit, m)
    # (Square on from 15 m, as the rider stops in front of it.)
    A.finish(kit, NAME, budget=5000, eye=(-16.0, 9.1, -3.95), look_at=(0.0, 9.1, -1.0), fov=70.0)
