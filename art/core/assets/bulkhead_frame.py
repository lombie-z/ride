"""bulkhead_frame: the huge round riveted frame round the opening, in the tube's end wall (concept-flooded-tunnel).

Origin: the opening's centre on the tube's axis, at the door's seat, so it goes at z 5.5 over the deck, +X down the road. The
opening's radius is 8.5. It's a throat of telescoping rings, x -8.2 to 1.4: it takes the place of the tube's last 8 m (so the last
tube ring ends at x -8), and within the tube's radius 9 the image's great concentric bands come from perspective. Its back wall
runs out to radius 13, closing the tube's end from the room's side. The empty DoorHinge is where bulkhead_door's origin goes.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bulkhead as H  # noqa: E402
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'bulkhead_frame'
PAINT, RAMP, GLOW, HOT = 0, 1, 2, 3
WATER_Z = 0.35 - H.CZ


def frame_uv(x, r, t, k):
    a = H.FRAME_PATH[k]
    b_ = H.FRAME_PATH[k + 1]
    ln = math.hypot(b_[0] - a[0], b_[1] - a[1])
    along = math.hypot(x - a[0], r - a[1]) / max(ln, 1e-6)
    s = H.FRAME_S[k] + along * ln
    # (Eps in from the span's ends, so a span's paint doesn't bleed its neighbour's.)
    return (t / (2 * math.pi), min(max(s / H.FRAME_LEN, 0.001), 0.999))


def build(kit, m):
    b = H.B()
    b.lathe_x(H.FRAME_PATH, seg=72, mat=PAINT, flip=True, uvf=frame_uv)

    # The clamp blocks on the throat: their faces in the frame's own paint, dark sides, bolts at the corners.
    def block_uv(band_s, x0):
        def uvf(p):
            t = math.atan2(p[2], p[1]) % (2 * math.pi)
            return (t / (2 * math.pi), min(max((band_s + p[0] - x0) / H.FRAME_LEN, 0.001), 0.999))
        return uvf

    for deg, x, wall_r, drop, across, along in H.FRAME_CLAMPS:
        a = math.radians(deg)
        er = Vector((0, math.cos(a), math.sin(a)))
        et = Vector((0, -math.sin(a), math.cos(a)))
        ex = Vector((1, 0, 0))
        c = ex * x + er * (wall_r - drop / 2)
        face = {'uvf': block_uv(H.FRAME_S[7], -3.9), 'row': None, 'lit': None}
        lit = float(H.frame_light(a)) * 0.2
        b.box(c, (along, drop, across), mat=RAMP, axes=(ex, er, et), row=H.IRON, lit=lit, skip=('+y',),
              per_face={'-y': dict(face, mat=PAINT)})
        for sx, st in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            b.rivet(c - er * (drop / 2) + ex * (sx * (along / 2 - 0.2)) + et * (st * (across / 2 - 0.18)), -er, r=0.11, h=0.09, mat=RAMP, row=H.RUST, lit=(0.05, float(H.frame_light(a)) * 0.5))

    # Rivets round the faces and the bands, down to the water.
    def row_of(x, rad, cnt, nrm, r=0.1, h=0.08, gain=0.62):
        for i in range(cnt):
            t = 2 * math.pi * (i + 0.5) / cnt
            cy, cz = rad * math.cos(t), rad * math.sin(t)
            if cz < WATER_Z - 0.5:
                continue
            lit = float(H.frame_light(t)) * gain
            n = Vector(nrm) if nrm is not None else Vector((0, -math.cos(t), -math.sin(t)))
            b.rivet((x, cy, cz), n, r=r, h=h, mat=RAMP, row=H.PALE, lit=(0.05, lit))

    row_of(-8.2, 8.84, 88, (-1, 0, 0), r=0.12, h=0.1)
    row_of(-4.6, 8.78, 60, (-1, 0, 0), r=0.1, h=0.08)
    row_of(-3.5, 8.6, 60, None, r=0.1, h=0.08, gain=0.45)
    row_of(-2.3, 8.85, 72, None, r=0.1, h=0.08, gain=0.8)
    row_of(-5.8, 8.95, 54, None, r=0.1, h=0.08, gain=0.4)
    row_of(-1.9, 8.7, 60, (-1, 0, 0), r=0.09, h=0.07, gain=0.8)

    # The red lamp boxes, on the throat as in the image: dark housing, glow, hot core.
    for deg, x in H.FRAME_LAMPS:
        a = math.radians(deg)
        er = Vector((0, math.cos(a), math.sin(a)))
        et = Vector((0, -math.sin(a), math.cos(a)))
        # Facing back up the road and inward, so they show from far off.
        nrm = (er * -0.55 + Vector((-1, 0, 0))).normalized()
        side = et
        up = side.cross(nrm).normalized()
        c = Vector((x, 0, 0)) + er * 8.56
        b.box(c, (0.3, 0.84, 0.84), mat=RAMP, axes=(nrm, side, up), row=H.IRON, lit=0.3, skip=('+x',))
        f = c + nrm * 0.18
        q = lambda s, sz: [f + side * (-sz) + up * (-s), f + side * sz + up * (-s), f + side * sz + up * s, f + side * (-sz) + up * s]
        b.poly(list(reversed(q(0.32, 0.32))), mat=GLOW)
        f = c + nrm * 0.2
        b.poly(list(reversed([f + side * (-0.15) + up * (-0.15), f + side * 0.15 + up * (-0.15), f + side * 0.15 + up * 0.15, f + side * (-0.15) + up * 0.15])), mat=HOT)

    # The image's hinge side: knuckles and the great post on the right of the throat, beside the door.
    post_y = -8.34
    b.rod((-2.7, post_y, -3.7), (-2.7, post_y, 3.4), 0.32, sides=8, mat=RAMP, row=H.IRON, lit=0.3, smooth=True)
    hinge = H.key_light((-0.8, 0.5, 0.4), 0.06, 0.34)
    for zk, sz in ((3.6, 1.2), (-3.8, 1.2)):
        yw = -math.sqrt(max(8.85 ** 2 - zk ** 2, 1.0))
        b.box((-2.7, (yw + post_y) / 2, zk), (1.5, abs(yw - post_y) + 0.3, sz), mat=RAMP, row=H.IRON, lit=0.2)
        b.rod((-2.7, post_y, zk - sz * 0.55), (-2.7, post_y, zk + sz * 0.55), 0.5, sides=8, mat=RAMP, row=H.IRON, lit=0.32, smooth=True)

    # The door's mounts on the room's side (where the door's post turns).
    hx, hy, _hz = H.HINGE
    for zk in (-4.9, 4.9):
        for dz in (-1.3, 1.3):
            b.box((hx - 0.1, hy - 0.1, zk + dz), (0.9, 1.6, 0.45), mat=RAMP, row=H.IRON, lit=0.25)

    me = b.mesh(NAME, [m['bulkhead_frame'], m['bulkhead_ramp'], m['lamp_red'], m['lamp_red_hot']], hinge)
    # (Base colour only: the hemisphere's small share. Red through the opening, green from the tunnel's lamps.)
    kit.bake_light(me, [((3.0, 0.0, 0.0), (1.0, 0.12, 0.07), 7.0, 0.7), ((-14.0, 8.0, -2.5), (0.3, 0.9, 0.35), 7.0, 0.3), ((-14.0, -8.0, -2.5), (0.3, 0.9, 0.35), 7.0, 0.3)],
                   ambient=(0.38, 0.4, 0.36))
    return me


def hinge_marker():
    e = bpy.data.objects.new('DoorHinge', None)
    bpy.context.scene.collection.objects.link(e)
    e.location = H.HINGE
    return e


if __name__ == '__main__':
    kit = A.begin()
    H.register(kit)
    m = _mats.mats(kit)
    A.obj(build(kit, m))
    hinge_marker()
    # (The rider's framing, from the image: 27 m back, a little left of the axis, 4 above the origin's plane less the opening's height.)
    A.finish(kit, NAME, budget=5000, eye=(-27.0, 2.3, 1.55 - H.CZ), look_at=(0.0, 4.87, 2.55 - H.CZ), fov=70.0)
