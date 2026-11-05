"""red_tank: the glowing red cylinder tank with base and cap (concept-flooded-tunnel): glass radius 3.3, 10 high.

Origin: base centre. As the lab's tanks do (art/core/tanks.py), no refraction: a liner facing inward and culled from outside, so you
see only its far wall, painted glowing; a hot filament up the middle; one faint glass shell and two highlights over them.
"""
import math
import os
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bulkhead as H  # noqa: E402
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'red_tank'
LINER, RAMP, GLASS, HOT = 0, 1, 2, 3
SEG = 20
Z0, Z1 = 1.05, 8.55
R = 3.3


def ring_uv(z):
    return min(max((z - Z0) / (Z1 - Z0), 0.002), 0.998)


def build(kit, m):
    liner = m['bulkhead_tank']
    liner.use_backface_culling = True
    b = H.B()
    # The liner: faces in. Its roof and floor glow too, seen through the glass from below.
    for i in range(SEG):
        a0, a1 = 2 * math.pi * i / SEG, 2 * math.pi * (i + 1) / SEG
        u0, u1 = (i / SEG) * 2, ((i + 1) / SEG) * 2
        ri = R - 0.08
        b.poly([(ri * math.cos(a0), ri * math.sin(a0), Z0), (ri * math.cos(a0), ri * math.sin(a0), Z1),
                (ri * math.cos(a1), ri * math.sin(a1), Z1), (ri * math.cos(a1), ri * math.sin(a1), Z0)],
               mat=LINER, uv=[(u0, 0.002), (u0, 0.998), (u1, 0.998), (u1, 0.002)], smooth=True)
    # The filament.
    b.rod((0, 0, Z0), (0, 0, Z1), 0.09, sides=5, mat=HOT, caps=False)
    # The shell of glass.
    for i in range(SEG):
        a0, a1 = 2 * math.pi * i / SEG, 2 * math.pi * (i + 1) / SEG
        b.poly([(R * math.cos(a0), R * math.sin(a0), Z0), (R * math.cos(a1), R * math.sin(a1), Z0),
                (R * math.cos(a1), R * math.sin(a1), Z1), (R * math.cos(a0), R * math.sin(a0), Z1)], mat=GLASS, smooth=True)

    # Base and cap, lathed about z: dark steel catching the glow, a burning lip where each meets the glass.
    rim_lit = lambda p, n: 0.2
    def lathe(profile, row, lit_by_index):
        for k, ((r0, z0), (r1, z1)) in enumerate(zip(profile, profile[1:])):
            for i in range(SEG):
                a0, a1 = 2 * math.pi * i / SEG, 2 * math.pi * (i + 1) / SEG
                lit = lit_by_index[k]
                # (Some side of it nearer the room's light: a hint of a highlight round the ring.)
                b.poly([(r0 * math.cos(a0), r0 * math.sin(a0), z0), (r0 * math.cos(a1), r0 * math.sin(a1), z0),
                        (r1 * math.cos(a1), r1 * math.sin(a1), z1), (r1 * math.cos(a0), r1 * math.sin(a0), z1)],
                       mat=RAMP, row=row, lit=lit, smooth=True)

    lathe([(3.72, 0.0), (3.72, 0.72), (3.42, Z0 - 0.05)], H.DARK, [0.3, 0.55])
    lathe([(3.4, Z0 - 0.05), (3.32, Z0)], H.EMBER, [0.92])
    lathe([(3.4, Z1), (3.4, Z1 + 0.08)], H.EMBER, [1.0])
    lathe([(3.4, Z1 + 0.08), (3.72, Z1 + 0.16), (3.72, Z1 + 0.62), (1.5, 9.72), (0.45, 9.8)], H.DARK, [0.34, 0.26, 0.16, 0.07])
    # The cap's underside, over the liner, seen through the glass.
    for i in range(SEG):
        a0, a1 = 2 * math.pi * i / SEG, 2 * math.pi * (i + 1) / SEG
        b.poly([(0, 0, Z1 - 0.01), (3.25 * math.cos(a1), 3.25 * math.sin(a1), Z1 - 0.01), (3.25 * math.cos(a0), 3.25 * math.sin(a0), Z1 - 0.01)],
               mat=RAMP, row=H.EMBER, lit=(0.3, 0.62, 0.62))
    # The stub to the ceiling.
    b.rod((0, 0, 9.75), (0, 0, 10.0), 0.42, sides=8, mat=RAMP, row=H.DARK, lit=0.16, caps=True, smooth=True)
    # Two struts of the cage, hardly there, tying cap to base.
    for deg in (35.0, 155.0, 275.0):
        a = math.radians(deg)
        p = Vector((3.48 * math.cos(a), 3.48 * math.sin(a), 0))
        b.rod(p + Vector((0, 0, Z0 - 0.1)), p + Vector((0, 0, Z1 + 0.1)), 0.09, sides=4, mat=RAMP, row=H.DARK, lit=0.34, caps=False)
    _ = rim_lit
    me = b.mesh(NAME, [liner, m['bulkhead_ramp'], m['red_tank_glass'], m['lamp_red_hot']], lambda p, n: 0.2)
    kit.bake_light(me, [((0, 0, 5.0), (1.0, 0.14, 0.09), 6.0, 0.7)], ambient=(0.35, 0.3, 0.3))
    return me


if __name__ == '__main__':
    kit = A.begin()
    H.register(kit)
    m = _mats.mats(kit)
    A.obj(build(kit, m))
    A.finish(kit, NAME, budget=500, eye=(-15.0, -3.0, 1.45), look_at=(0.0, 0.0, 5.0), fov=55.0)
