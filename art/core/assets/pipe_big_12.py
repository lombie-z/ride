"""pipe_big_12: the 1.3 m bore run, flanges at both ends and a bolted collar halfway, x 0..12 along +X, origin on the pipe's axis
at its x = 0 end. Runs tile end to end. Also holds the round-section helpers the group's other scripts import (importing
this file makes nothing)."""
import math
import os
import sys

import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

BORE = 0.65       # the pipe's radius, the group's one size
FLANGE = 0.86     # the flanges' radius, big enough to read at the scene's pixel
FLANGE_T = 0.2


def ring_x(bm, x, r, seg, y=0.0, z=0.0, phase=0.0):
    return [bm.verts.new((x, y + r * math.cos(phase + 2 * math.pi * i / seg), z + r * math.sin(phase + 2 * math.pi * i / seg))) for i in range(seg)]


def ring_frame(bm, c, u, v, r, seg, phase=0.0):
    """A ring round c in the plane of u and v (u x v is the way it runs: join() then faces outward)."""
    return [bm.verts.new(c + (u * math.cos(phase + 2 * math.pi * i / seg) + v * math.sin(phase + 2 * math.pi * i / seg)) * r) for i in range(seg)]


def join(bm, a, b, mat=0, smooth=True):
    """Faces between two rings; outward if b is further along the ring's axis (ring angles run counter-clockwise from there)."""
    n = len(a)
    out = []
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((a[i], a[j], b[j], b[i]))
        f.material_index = mat
        f.smooth = smooth
        out.append(f)
    return out


def cap(bm, ring, mat=0, flip=False):
    f = bm.faces.new(list(reversed(ring)) if flip else ring)
    f.material_index = mat
    return f


def turned(bm, profile, seg, y=0.0, z=0.0, mat=0, phase=0.0):
    """A turned part along +X from (x, r) points walking the +X way: each step has its own rings, so every corner's hard."""
    for (x0, r0), (x1, r1) in zip(profile, profile[1:]):
        join(bm, ring_x(bm, x0, r0, seg, y, z, phase), ring_x(bm, x1, r1, seg, y, z, phase), mat)


def flange(x0, r=FLANGE, t=FLANGE_T, bore=BORE, out=1):
    """A flange's (x, r) points, from its mating face at x0 back along the pipe (out = 1: the pipe runs on to +X)."""
    if out > 0:
        return [(x0, r), (x0 + t, r), (x0 + t, bore)]
    return [(x0 - t, bore), (x0 - t, r), (x0, r)]


def collar(x, half=0.2, r=0.8, bore=BORE):
    return [(x - half, bore), (x - half, r), (x + half, r), (x + half, bore)]


def stud(bm, c, normal, size=0.09, h=0.07, mat=0):
    """A bolt head on a surface: three sides and a top (7 tris), its base buried."""
    n = Vector(normal).normalized()
    u = n.orthogonal().normalized()
    v = n.cross(u)
    c = Vector(c)
    base = [bm.verts.new(c - n * 0.02 + (u * math.cos(k * 2.094) + v * math.sin(k * 2.094)) * size) for k in range(3)]
    top = [bm.verts.new(c + n * h + (u * math.cos(k * 2.094) + v * math.sin(k * 2.094)) * size) for k in range(3)]
    for i in range(3):
        j = (i + 1) % 3
        f = bm.faces.new((base[i], base[j], top[j], top[i]))
        f.material_index = mat
    t = bm.faces.new(top)
    t.material_index = mat


def bolt_ring(bm, x, r, n, normal_x, mat=0, phase=0.3):
    for k in range(n):
        a = phase + 2 * math.pi * k / n
        stud(bm, (x, r * math.cos(a), r * math.sin(a)), (normal_x, 0, 0), mat=mat)


def box(bm, kit, c, size, mat=0):
    return kit.add_box(bm, c, size, mat=mat)


def make(kit, name, bm, mats):
    """kit.mesh_from, keeping each face's own smooth flag (round parts smooth, boxes flat). Windings are built right: no recalc."""
    flags = [f.smooth for f in bm.faces]
    bm.normal_update()
    me = kit.mesh_from(name, bm, mats, recalc=False)
    for p, s in zip(me.polygons, flags):
        p.use_smooth = s
    return me


def stair_lights(xs, r=BORE, y=0.0, z=0.0, side=-1):
    """The stairwell's light on a pipe along +X, per ring: a long wet highlight up top (cold) and a red sheen from the strips
    below on the road's side (`side`, -Y by default). Painted close in, so each is a band along the pipe, not a wash; base colour can't go past
    its material, so metals need these to show at all."""
    out = []
    for x in xs:
        out.append(((x, y + side * r * 0.75, z + r * 1.25), (0.85, 1.0, 0.85), r * 0.5, 3.0))
        out.append(((x, y + side * r * 1.25, z - r * 0.9), (1.0, 0.08, 0.04), r * 0.7, 2.2))
    return out


STAIR_AMBIENT = (0.26, 0.26, 0.25)


def main():
    kit = A.begin()
    m = _mats.mats(kit)
    bm = bmesh.new()
    seg = 14
    prof = flange(0.0) + collar(6.0) + flange(12.0, out=-1)
    # Rust-brown body, near-black flanges and collar, as on the tunnel's pipe: the joints read at the scene's pixel.
    turned(bm, [prof[2], prof[3]], seg, mat=0)
    turned(bm, [prof[6], prof[7]], seg, mat=0)
    turned(bm, prof[:3], seg, mat=1)
    turned(bm, prof[3:7], seg, mat=1)
    turned(bm, prof[7:10], seg, mat=1)
    cap(bm, ring_x(bm, 0.0, FLANGE, seg), mat=1, flip=True)
    cap(bm, ring_x(bm, 12.0, FLANGE, seg), mat=1)
    bolt_ring(bm, FLANGE_T, 0.76, 5, 1, mat=0)
    bolt_ring(bm, 12.0 - FLANGE_T, 0.76, 5, -1, mat=0, phase=0.9)
    me = make(kit, 'pipe_big_12', bm, [m['pipe_metal'], m['dark']])
    kit.box_uvs(me, 0.25)
    kit.bake_light(me, stair_lights((0.2, 5.8, 6.2, 11.8)), ambient=STAIR_AMBIENT)
    A.obj(me)
    A.finish(kit, 'pipe_big_12', budget=350, eye=(0.0, -6.5, -1.6), look_at=(6.0, 0.0, 0.2), fov=60.0)


if __name__ == '__main__':
    main()
