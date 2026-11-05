"""tube_side_duct: a dark duct mouth in the tube's wall with its louvres, as above the image's left pipes (art/core/ASSETS.md).

Origin: back centre, on the wall's surface; it faces +Y, x along the tube, z up the wall. Mouth 2.76 x 2.1, flange 3.4 x 2.7,
standing 0.55 off the wall, its skirt running 0.3 behind the origin to bury itself in the curve.
"""
import math
import os
import sys

import bmesh
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'tube_side_duct'
# The frame's rings, front to back: half width (x), half height (z), y.
RINGS = [(1.96, 1.62, -0.3), (1.84, 1.5, 0.34), (1.7, 1.35, 0.55), (1.46, 1.13, 0.55), (1.38, 1.05, 0.02)]
# The lights in its frame (it's placed low on the wall, between the white work light above and a green lamp below).
LIGHTS = [((0.0, 1.5, 4.2), (1.0, 0.95, 0.78), 3.8, 1.1), ((0.0, 1.8, -2.8), (0.2, 1.0, 0.24), 3.0, 0.8)]


def ring_verts(bm, hw, hh, y, per_side):
    """A rectangle's perimeter, per_side segments on each side, starting at (-hw, -hh), going up +z then along +x, so it runs CW from +Y."""
    pts = []
    corners = [(-hw, -hh), (-hw, hh), (hw, hh), (hw, -hh)]
    for i in range(4):
        (ax, az), (bx, bz) = corners[i], corners[(i + 1) % 4]
        for k in range(per_side):
            t = k / per_side
            pts.append(bm.verts.new((ax + (bx - ax) * t, y, az + (bz - az) * t)))
    return pts


def bolt(bm, x, y, z, mat):
    """A hex-ish boss, 5 sided, standing out of the flange."""
    r = 0.075
    base = [bm.verts.new((x + r * math.cos(2 * math.pi * k / 5), y, z + r * math.sin(2 * math.pi * k / 5))) for k in range(5)]
    tip = bm.verts.new((x, y + 0.06, z))
    for k in range(5):
        bm.faces.new((base[k], base[(k + 1) % 5], tip)).material_index = mat


def build(kit, m):
    bm = bmesh.new()
    rust, dark, steel = 0, 1, 2
    rings = [ring_verts(bm, hw, hh, y, 2) for hw, hh, y in RINGS]
    for a, b in zip(rings, rings[1:]):
        n = len(a)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i])).material_index = rust
    # The black behind the louvres.
    hw, hh = RINGS[-1][0], RINGS[-1][1]
    y = RINGS[-1][2]
    add = [bm.verts.new(c) for c in ((-hw, y, -hh), (hw, y, -hh), (hw, y, hh), (-hw, y, hh))]
    bm.faces.new(add).material_index = dark
    # The louvres: thin and deep, their front edges up, so from the road below you look between them into the black.
    slats = 8
    tilt = Matrix.Rotation(math.radians(-32), 3, 'X')
    pitch = 2 * hh / slats
    for k in range(slats):
        z = -hh + pitch * (k + 0.5)
        kit.add_box(bm, (0, 0.28, z), (2 * hw, 0.32, 0.055), steel, rot=tilt)
    # Two mullions holding them.
    for x in (-0.46, 0.46):
        kit.add_box(bm, (x, 0.42, 0), (0.1, 0.12, 2 * hh), rust)
    # The flange's bolts.
    for x in (-1.58, -0.53, 0.53, 1.58):
        for z in (-1.24, 1.24):
            bolt(bm, x, 0.55, z, steel)
    for z in (-0.42, 0.42):
        for x in (-1.58, 1.58):
            bolt(bm, x, 0.55, z, steel)
    me = kit.mesh_from(NAME, bm, [m['rust'], m['dark'], m['pipe_metal']], smooth=False)
    kit.box_uvs(me, 0.3)
    kit.bake_light(me, LIGHTS, ambient=(0.2, 0.22, 0.2))
    return me


if __name__ == '__main__':
    kit = A.begin()
    m = _mats.mats(kit)
    A.obj(build(kit, m))
    A.finish(kit, NAME, budget=500, eye=(-5.5, 7.0, -2.5), look_at=(0, 0.2, 0.0), fov=50.0)
