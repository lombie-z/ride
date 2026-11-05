"""The server hall (kit.SECTIONS['servers'], concept-core-servers): a vast dark hall, colossal rust-streaked towers of falling green
code either side of the road, cables swagged across overhead, fanning from the plinths to the floor.

Pieces are instanced along the road by s, so everything follows its bends. All light is painted: green from the code on
the plinths and cables, red near the beacons, green round the kerb's lights on the kerb and the floor."""
import math
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector

PREVIEW = any('preview.py' in a for a in sys.argv)

import kit as _kit  # noqa: E402

S0, S1 = _kit.SECTIONS['servers']
TOWER_D = 41.5       # the front row's centres, m off the road
REAR_D = 84.0        # the row behind
KX, KY = 0.95, 1.3   # a tower's plan: narrower along the road than across it (built square, then stretched)
WALL_D = 150.0       # the hall's far walls
ROOF_Z = 120.0
KERB_EVERY = 13.0
CODE_U = 1 / 6       # code tiles per metre across
FOG = (0.016, 0.042, 0.022)

M = {}


# --- Textures ----------------------------------------------------------------------------------------------------------
def tex_plate():
    """512 x 512 over 8 m: riveted plates, their seams, rust streaking down from the seams. Bright: the baked vertex colours
    do the darkening (the site's ambient is dim, so base x colour has to leave room for the green to show)."""
    import kit
    n = 512
    rng = np.random.default_rng(71)
    noise = kit.vnoise(n, 6, 72, 5)
    fine = kit.vnoise(n, 48, 73, 2)
    v = 0.34 + 0.22 * noise + 0.08 * fine
    # Plates: 4 rows of staggered widths.
    seams = np.zeros((n, n))
    rivets = np.zeros((n, n))
    rows = [0, 128, 256, 384]
    tones = rng.random((4, 6))
    for ri, r0 in enumerate(rows):
        r1 = r0 + 128
        cuts = [(ri % 2) * 64 + k * 128 for k in range(4)]
        for ci, c in enumerate(cuts):
            c1 = c + 128
            cols = np.arange(c, c1) % n
            v[np.ix_(np.arange(r0, r1), cols)] *= 0.92 + 0.14 * tones[ri, ci]
            seams[np.ix_(np.arange(r0, r1), [c % n, (c + 1) % n])] = 1
            for k in range(8):  # rivets along its vertical seam
                y = r0 + 8 + k * 16
                for dx in (5, -5):
                    x = (c + dx) % n
                    rivets[max(y - 2, 0):y + 3, (x - 2) % n:(x - 2) % n + 5] = 1
        seams[r0:r0 + 2, :] = 1
        for x in range(4, n, 16):  # and along its top seam
            for dy in (5,):
                rivets[r0 + dy - 2:r0 + dy + 3, x:x + 5] = 1
    # Rust running down from the seams and rivets.
    streak_src = np.clip(seams + rivets, 0, 1) * (kit.vnoise(n, 64, 74, 2) > 0.5)
    streak = streak_src.copy()
    for _ in range(70):
        streak = np.maximum(streak, np.roll(streak, 2, 0) * 0.98)
    wash = kit.vnoise(n, 5, 75, 4)
    colw = np.tile(rng.random(n)[None, :], (n, 1))
    colw = np.apply_along_axis(lambda r: np.convolve(r, np.ones(6) / 6, mode='same'), 1, colw)
    rust = np.clip(streak * (0.5 + 0.8 * colw) + kit.smoothstep(0.52, 0.72, wash) * 0.75 * (0.4 + colw), 0, 1)
    steel = np.array([0.50, 0.50, 0.47])
    orange = np.array([0.98, 0.48, 0.18])
    c = (v[..., None] * steel / 0.45) * (1 - rust[..., None]) + (v[..., None] * orange / 0.45) * rust[..., None]
    c *= (1 - 0.7 * seams)[..., None]
    # The rivets: a lit top, a dark foot.
    c = c * (1 - rivets[..., None]) + rivets[..., None] * c * 1.5
    foot = np.roll(rivets, 3, 0) * (1 - rivets)
    c *= (1 - 0.6 * foot)[..., None]
    return np.clip(c, 0, 1)


def tex_rib():
    """64 x 64 (3 m of cable along v): the ribs of a corrugated cable."""
    n = 64
    rows = np.arange(n)
    rib = 0.5 + 0.5 * np.cos(2 * math.pi * rows * 8 / n)
    v = 0.05 + 0.5 * rib ** 2
    return np.tile(v[:, None, None], (1, n, 3)) * np.array([1.0, 1.0, 0.94])


def tex_grille():
    """128 x 128: lit slats, a vent's green through a grille."""
    n = 128
    out = np.zeros((n, n, 3))
    slats = 6
    for k in range(slats):
        r0 = 6 + k * (n - 12) // slats
        out[r0 + 3:r0 + 13] = np.array([0.55, 1.0, 0.45])
    cols = np.ones(n)
    cols[::21] = 0.1
    cols[1::21] = 0.1
    out *= cols[None, :, None]
    edge = np.minimum(np.arange(n), np.arange(n)[::-1]) / 6.0
    out *= np.clip(edge, 0, 1)[None, :, None]
    return out


def tex_rack():
    """256 x 256: far racks, rows of small green lights in the dark."""
    n = 256
    rng = np.random.default_rng(81)
    out = np.zeros((n, n, 3))
    for r in range(4, n, 16):
        on = rng.random(32) < 0.55
        for c in range(32):
            if on[c]:
                out[r:r + 5, c * 8 + 1:c * 8 + 7] = np.array([0.3, 1.0, 0.4]) * rng.uniform(0.3, 1.0)
    return out


def _soft(n, m, seed, power=1.0):
    """m x n soft-edged alpha, a bank of mist: fades to nothing at its edges and top."""
    import kit
    yy = np.linspace(0, 1, m)[:, None]   # row 0 is its top
    xx = np.linspace(0, 1, n)[None, :]
    across = np.sin(np.pi * xx) ** 1.2
    up = kit.smoothstep(0.05, 0.85, yy) ** 1.4 * (1 - kit.smoothstep(0.8, 1.0, yy))
    no = kit.vnoise(max(n, m), 5, seed, 4)[:m, :n]
    a = across * up * (0.25 + 0.8 * kit.smoothstep(0.3, 0.75, no))
    return np.clip(a * 0.95, 0, 1) ** power


def tex_mist():
    a = _soft(256, 128, 91)
    out = np.ones((128, 256, 4))
    out[..., :3] = np.array([0.42, 0.72, 0.46])
    out[..., 3] = a
    return out


def tex_flare():
    """128 x 128: a red glow with a long horizontal streak."""
    n = 128
    yy, xx = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    r = np.sqrt(xx * xx + yy * yy)
    glow = np.clip(1 - r, 0, 1) ** 4
    streak = np.clip(1 - np.abs(xx), 0, 1) ** 1.5 * np.exp(-(yy / (0.02 + 0.09 * np.abs(xx))) ** 2)
    out = np.ones((n, n, 4))
    out[..., 0] = 1.0
    out[..., 1] = 0.12
    out[..., 2] = 0.07
    out[..., 3] = np.clip(glow * 1.2 + streak * 0.9, 0, 1)
    return out


# --- Mesh helpers ------------------------------------------------------------------------------------------------------
def chamfer_ring(a, c, z, sub=False):
    """A chamfered square at height z (half-width a, chamfer c), counter-clockwise from above; `sub`: with a midpoint on each
    straight side, for the baked light."""
    pts = []
    for k in range(4):
        ca, sa = [(1, 0), (0, 1), (-1, 0), (0, -1)][k]
        for x, y in ([(a, -(a - c)), (a, 0.0), (a, a - c)] if sub else [(a, -(a - c)), (a, a - c)]):
            pts.append((ca * x - sa * y, sa * x + ca * y, z))
    return pts


def loft(bm, rings, mat=0):
    """Quads between rings of equal length (counter-clockwise, going up: outward faces)."""
    vr = [[bm.verts.new(p) for p in r] for r in rings]
    for a, b in zip(vr, vr[1:]):
        n = len(a)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i])).material_index = mat
    return vr


def quad(bm, a, b, c, d, mat=0):
    f = bm.faces.new([bm.verts.new(p) for p in (a, b, c, d)])
    f.material_index = mat
    return f


def _uv_layer(bm):
    """The bmesh's UV layer, named what the kit's materials read."""
    return bm.loops.layers.uv.get('UVMap') or bm.loops.layers.uv.new('UVMap')


def rot(k, x, y, z=None):
    ca, sa = [(1, 0), (0, 1), (-1, 0), (0, -1)][k % 4]
    if z is None:
        return (ca * x - sa * y, sa * x + ca * y)
    return (ca * x - sa * y, sa * x + ca * y, z)


def face_uvs(bm, plate=0, code=None, grille=None, plate_scale=1 / 12, seed=0, grille2=None):
    """Box-projected UVs: the plate's and the code's in metres (the code's V running up, 1 tile per 6 m), a grille's 0..1."""
    bm.normal_update()
    uv = _uv_layer(bm)
    rng = np.random.default_rng(seed)
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda k: abs(n[k]))
        if f.material_index in (grille, grille2):
            cos = [l.vert.co for l in f.loops]
            zs = [c.z for c in cos]
            z0, z1 = min(zs), max(zs)
            first = (cos[1] - cos[0])
            first.z = 0
            if first.length < 1e-6:
                first = cos[2] - cos[1]
                first.z = 0
            first.normalize()
            ts = [c.dot(first) for c in cos]
            t0, t1 = min(ts), max(ts)
            for l, c, t in zip(f.loops, cos, ts):
                l[uv].uv = ((t - t0) / max(t1 - t0, 1e-6), (c.z - z0) / max(z1 - z0, 1e-6) if z1 - z0 > 1e-6 else 0.0)
            continue
        off = (0.0, 0.0)
        s = plate_scale
        su = s
        if f.material_index == code:
            s, su = 1 / 6, CODE_U
            off = (rng.random(), rng.random())
        for l in f.loops:
            co = l.vert.co
            if ax == 0:
                u, v = co.y, co.z
            elif ax == 1:
                u, v = co.x, co.z
            else:
                u, v = co.x, co.y
            l[uv].uv = (u * su + off[0], v * s + off[1])


def tube(bm, path, r, sides=5, mat=0, tile=3.0, up=Vector((0, 0, 1))):
    """A cable: a sweep round a path, its V running along it, 1 tile per `tile` m (the ribs). Round it's shaded smooth."""
    import kit
    prof = kit.circle_profile(r, sides)
    rings = kit.sweep(bm, path, prof, up=up, mat=mat, caps=False)  # (Their ends are buried in floor and tower.)
    uv = _uv_layer(bm)
    dist = {}
    acc = 0.0
    for i, ring in enumerate(rings):
        if i:
            acc += (path[i] - path[i - 1]).length
        for v in ring:
            dist[v] = acc / tile
    for ring in rings:
        for v in ring:
            for l in v.link_loops:
                l[uv].uv = (0.5, dist[v])


def bezier(p0, p1, p2, p3, n):
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        out.append(p0 * (u * u * u) + p1 * (3 * u * u * t) + p2 * (3 * u * t * t) + p3 * (t * t * t))
    return out


# --- Pieces ------------------------------------------------------------------------------------------------------------
def body_a(z):
    return 9.6 + (7.2 - 9.6) * (z - 14.0) / (56.0 - 14.0)


def build_tower(kit, beacon=False):
    """A front-row tower, centre at its origin: a flared plinth, four faces of code between heavy chamfered corner posts,
    a stepped cap. Four-fold symmetric, so it serves either side of the road."""
    bm = bmesh.new()
    PLATE, CODE, GRILLE, DARK, DIM = 0, 1, 2, 3, 4
    INSET, POST_W, POST_C = 0.9, 3.8, 2.4
    # The plinth.
    plinth = [(15.2, 4.8, 0.0), (15.0, 4.8, 1.0), (11.9, 3.4, 9.0), (12.1, 3.4, 9.0 + 0.9), (11.1, 3.0, 10.4), (11.1, 3.0, 13.0), (9.8, 2.4, 14.2)]
    loft(bm, [chamfer_ring(a, c, z, sub=True) for a, c, z in plinth], PLATE)
    # The corner posts, between them the faces.
    zs = [14.0, 18.0, 26.0, 40.0, 56.0]
    zb, zt = 15.6, 52.0
    for k in range(4):
        rings = []
        for z in zs:
            a = body_a(z)
            pts = [(a - INSET, a - POST_W), (a, a - POST_W), (a, a - POST_C), (a - POST_C, a), (a - POST_W, a), (a - POST_W, a - INSET)]
            rings.append([rot(k, x, y, z) for x, y in pts])
        vr = [[bm.verts.new(p) for p in r] for r in rings]
        for a, b in zip(vr, vr[1:]):
            for i in range(5):
                bm.faces.new((a[i], a[i + 1], b[i + 1], b[i])).material_index = PLATE
        # Its face: three bays of code between ribs. (The +X side, turned.)
        ab, at = body_a(zb), body_a(zt)
        hb, ht = ab - POST_W, at - POST_W
        xb, xt = ab - INSET, at - INSET
        bays = [-1.0, -1 / 3, 1 / 3, 1.0]
        rib = 0.28
        for i in range(3):
            pad0 = rib if i else 0.0
            pad1 = rib if i < 2 else 0.0
            y0b, y1b = hb * bays[i] + pad0, hb * bays[i + 1] - pad1
            y0t, y1t = ht * bays[i] + pad0, ht * bays[i + 1] - pad1
            quad(bm, rot(k, xb, y0b, zb), rot(k, xb, y1b, zb), rot(k, xt, y1t, zt), rot(k, xt, y0t, zt), CODE)
        for i in (1, 2):
            yb, yt = hb * bays[i], ht * bays[i]
            d = 0.35
            # (Front, then its two sides.)
            quad(bm, rot(k, xb + d, yb - rib, zb), rot(k, xb + d, yb + rib, zb), rot(k, xt + d, yt + rib, zt), rot(k, xt + d, yt - rib, zt), PLATE)
            quad(bm, rot(k, xb, yb - rib, zb), rot(k, xb + d, yb - rib, zb), rot(k, xt + d, yt - rib, zt), rot(k, xt, yt - rib, zt), DARK)
            quad(bm, rot(k, xb + d, yb + rib, zb), rot(k, xb, yb + rib, zb), rot(k, xt, yt + rib, zt), rot(k, xt + d, yt + rib, zt), DARK)
        # Over the face (its header, the soffit), under it (the sill, the ledge the code's light falls on).
        a14, a56 = body_a(14.0), body_a(56.0)
        hh = a56 - POST_W
        hhb = a14 - POST_W
        quad(bm, rot(k, at, ht, zt), rot(k, at, -ht, zt), rot(k, xt, -ht, zt), rot(k, xt, ht, zt), PLATE)
        quad(bm, rot(k, at, -ht, zt), rot(k, at, ht, zt), rot(k, a56, hh, 56.0), rot(k, a56, -hh, 56.0), PLATE)
        quad(bm, rot(k, a14, -hhb, 14.0), rot(k, a14, hhb, 14.0), rot(k, ab, hb, zb), rot(k, ab, -hb, zb), PLATE)
        quad(bm, rot(k, ab, -hb, zb), rot(k, ab, hb, zb), rot(k, xb, hb, zb), rot(k, xb, -hb, zb), PLATE)
        # A vent on the skirt: a dark surround, a lit grille.
        skirt = lambda z: 15.0 - (z - 1.0) * (15.0 - 11.9) / 8.0  # noqa: E731
        z0, z1 = 3.2, 6.6
        quad(bm, rot(k, skirt(z0 - 0.35) + 0.04, -3.5, z0 - 0.35), rot(k, skirt(z0 - 0.35) + 0.04, 3.5, z0 - 0.35), rot(k, skirt(z1 + 0.35) + 0.04, 3.5, z1 + 0.35), rot(k, skirt(z1 + 0.35) + 0.04, -3.5, z1 + 0.35), DARK)
        quad(bm, rot(k, skirt(z0) + 0.08, -3.1, z0), rot(k, skirt(z0) + 0.08, 3.1, z0), rot(k, skirt(z1) + 0.08, 3.1, z1), rot(k, skirt(z1) + 0.08, -3.1, z1), GRILLE)
        # A vent on the post's chamfer, facing the corner.
        for z0, z1, w, m, out in ((24.6, 30.4, 1.2, DARK, 0.04), (25.0, 30.0, 0.95, DIM, 0.08)):
            a0, a1 = body_a(z0), body_a(z1)
            cx0, cx1 = a0 - POST_C / 2 + out, a1 - POST_C / 2 + out
            s = w / math.sqrt(2)
            quad(bm, rot(k, cx0 + s, cx0 - s, z0), rot(k, cx0 - s, cx0 + s, z0), rot(k, cx1 - s, cx1 + s, z1), rot(k, cx1 + s, cx1 - s, z1), m)
    # Fins down the skirt, a heavy wedge on each corner, straps round the posts.
    for k in range(4):
        for yy in (-7.2, 7.2):
            w, off = 0.32, 0.45
            pts = [(11.4 + off, yy - w, 9.8), (11.4 + off, yy + w, 9.8), (15.0 + off, yy + w, 0.0), (15.0 + off, yy - w, 0.0)]
            base = [(11.4, yy - w, 9.8), (11.4, yy + w, 9.8), (15.0, yy + w, 0.0), (15.0, yy - w, 0.0)]
            quad(bm, rot(k, *pts[3]), rot(k, *pts[2]), rot(k, *pts[1]), rot(k, *pts[0]), PLATE)
            quad(bm, rot(k, *base[3]), rot(k, *pts[3]), rot(k, *pts[0]), rot(k, *base[0]), DARK)
            quad(bm, rot(k, *pts[2]), rot(k, *base[2]), rot(k, *base[1]), rot(k, *pts[1]), DARK)
        # The corner's buttress, standing on the skirt's chamfer: its slope, its two cheeks, its top.
        def wedge(diag, w, z):
            return rot(k, diag + w / math.sqrt(2), diag - w / math.sqrt(2), z)
        quad(bm, wedge(14.8, 2.2, 0.0), wedge(14.8, -2.2, 0.0), wedge(10.7, -1.3, 10.0), wedge(10.7, 1.3, 10.0), PLATE)
        quad(bm, wedge(12.7, 2.2, 0.0), wedge(14.8, 2.2, 0.0), wedge(10.7, 1.3, 10.0), wedge(10.1, 1.3, 10.0), PLATE)
        quad(bm, wedge(14.8, -2.2, 0.0), wedge(12.7, -2.2, 0.0), wedge(10.1, -1.3, 10.0), wedge(10.7, -1.3, 10.0), PLATE)
        quad(bm, wedge(10.7, 1.3, 10.0), wedge(10.7, -1.3, 10.0), wedge(10.1, -1.3, 10.0), wedge(10.1, 1.3, 10.0), PLATE)
        for z, hh in ((36.0, 1.1), (47.0, 0.8)):
            a = body_a(z)
            out = 0.22
            pts = [(a + out, a - POST_W, z), (a + out, a - POST_C, z), (a - POST_C, a + out, z), (a - POST_W, a + out, z)]
            up = [(p[0], p[1], z + hh) for p in pts]
            for i in range(3):
                quad(bm, rot(k, *pts[i]), rot(k, *pts[i + 1]), rot(k, *up[i + 1]), rot(k, *up[i]), DARK if i == 1 else PLATE)
            quad(bm, rot(k, *up[0]), rot(k, *up[1]), rot(k, *up[2]), rot(k, *up[3]), DARK)
    # The stepped cap.
    a56 = body_a(56.0)
    cap = [(a56 + 0.7, 2.2, 56.0), (a56 + 0.7, 2.2, 57.8), (a56 - 0.9, 1.8, 58.8), (4.8, 1.3, 62.2), (3.8, 1.0, 63.2)]
    vr = loft(bm, [chamfer_ring(a, c, z) for a, c, z in cap], PLATE)
    bm.faces.new(list(reversed(vr[0]))).material_index = DARK
    bm.faces.new(vr[-1]).material_index = PLATE
    for v in bm.verts:
        v.co.x *= KX
        v.co.y *= KY
    face_uvs(bm, PLATE, CODE, GRILLE, seed=7 if beacon else 3, grille2=DIM)
    me = kit.mesh_from('HallTowerMesh' + ('B' if beacon else ''), bm, [M['plate'], kit.MAT['code'], M['grille'], kit.MAT['dark'], M['grille_dim']], recalc=False)
    # The code's light on what's round it: its posts' reveals, the ledge, the plinth under it, fading away up the cap.
    lights = []
    for k in range(4):
        for z, p in ((20.0, 0.42), (34.0, 0.3), (48.0, 0.22)):
            lights.append((rot(k, 9.0, 0.0, z), (0.14, 1.0, 0.26), 8.5, p))
        lights.append((rot(k, 12.6, 0.0, 16.5), (0.12, 1.0, 0.22), 8.0, 1.0))   # pooled on the ledge and upper skirt
        lights.append((rot(k, 16.0, 0.0, 3.0), (0.14, 1.0, 0.25), 5.5, 0.34))    # the vent's own, low on the skirt
        lights.append((rot(k, 15.2, 15.2, 2.0), (0.10, 0.65, 0.18), 7.0, 0.2))  # the floor fog on its corners
    if beacon:
        lights.append(((0.0, 0.0, 68.5), (1.0, 0.06, 0.04), 8.0, 2.4))
    lights = [((p[0] * KX, p[1] * KY, p[2]), c, r, w) for p, c, r, w in lights]
    kit.bake_light(me, lights, ambient=(0.2, 0.2, 0.18))
    return me


def build_rear(kit):
    """The row behind: a cheap taller stand-in, seen through the gaps, half lost in the fog."""
    bm = bmesh.new()
    PLATE, CODE = 0, 1
    vr = loft(bm, [chamfer_ring(a, c, z) for a, c, z in ((16.5, 5.0, 0.0), (12.2, 3.6, 12.0), (11.4, 3.0, 13.5), (8.6, 2.0, 66.0), (9.2, 2.2, 67.5), (5.0, 1.4, 71.0))], PLATE)
    bm.faces.new(vr[-1]).material_index = PLATE
    for k in range(4):
        z0, z1 = 15.0, 62.0
        a0 = 11.4 + (8.6 - 11.4) * (z0 - 13.5) / 52.5
        a1 = 11.4 + (8.6 - 11.4) * (z1 - 13.5) / 52.5
        h0, h1 = a0 - 3.2, a1 - 2.4
        quad(bm, rot(k, a0 + 0.06, -h0, z0), rot(k, a0 + 0.06, h0, z0), rot(k, a1 + 0.06, h1, z1), rot(k, a1 + 0.06, -h1, z1), CODE)
    face_uvs(bm, PLATE, CODE, seed=11)
    me = kit.mesh_from('HallRearMesh', bm, [M['plate'], kit.MAT['code']], recalc=False)
    lights = []
    for k in range(4):
        lights.append((rot(k, 16.0, 0.0, 16.0), (0.12, 1.0, 0.22), 9.0, 0.5))
    kit.bake_light(me, lights, ambient=(0.24, 0.24, 0.22))
    return me


def build_fan(kit, side):
    """The cables out of a tower's road-side, rider-side corner, down its plinth, fanning out over the floor. `side`: +1 for a
    tower left of the road (the road on its -Y), -1 for one to the right."""
    bm = bmesh.new()
    n = 5
    for i in range(n):
        t = i / (n - 1)
        o = t - 0.5
        p0 = Vector((-8.6 - 0.4 * o, -8.6 + 1.9 * o, 24.0 - 0.5 * o))
        p1 = Vector((-10.5 - 0.6 * o, -10.2 + 2.8 * o, 14.0))
        p2 = Vector((-13.8 - 0.8 * o, -8.0 + 9.0 * t, 2.4))
        p3 = Vector((-21.5 - 2.0 * t, -7.0 + 20.0 * t ** 1.1, -0.1))
        path = [Vector((q.x * KX, q.y * KY, q.z)) for q in bezier(p0, p1, p2, p3, 6)]
        if side < 0:
            path = [Vector((q.x, -q.y, q.z)) for q in path]
        tube(bm, path, 0.62 - 0.1 * (i % 2), sides=5, mat=0)
    # Two clamps round the run, where they're still together.
    for t, w in ((0.2, 4.0), (0.46, 5.6)):
        c = bezier(Vector((-8.6, -8.6, 24.0)), Vector((-10.5, -10.2, 14.0)), Vector((-13.8, -3.5, 2.4)), Vector((-22.5, 3.0, -0.1)), 100)
        c = [Vector((q.x * KX, q.y * KY, q.z)) for q in c]
        p = c[int(t * 100)]
        tan = c[int(t * 100) + 2] - c[int(t * 100) - 2]
        if side < 0:
            p = Vector((p.x, -p.y, p.z))
            tan = Vector((tan.x, -tan.y, tan.z))
        q = tan.normalized().to_track_quat('X', 'Z')
        kit.add_box(bm, p, (0.55, w, 1.9), 1, rot=q.to_matrix())
    uv = _uv_layer(bm)
    for f in bm.faces:
        if f.material_index == 1:
            for l in f.loops:
                l[uv].uv = (l.vert.co.x / 8, l.vert.co.z / 8)
    me = kit.mesh_from('HallFanMesh' + ('L' if side > 0 else 'R'), bm, [M['cable'], M['plate']], smooth=True)
    sy = 1 if side > 0 else -1
    lights = [
        ((-11.0, -10.0 * sy, 26.0), (0.12, 1.0, 0.24), 8.0, 0.9),
        ((-20.0, 0.0, 12.0), (0.12, 1.0, 0.24), 9.0, 0.45),
        ((-13.0, -14.0 * sy, 8.0), (0.12, 1.0, 0.22), 6.0, 0.6),
        ((-26.0, 8.0 * sy, 2.5), (0.10, 0.8, 0.2), 6.0, 0.4),
    ]
    kit.bake_light(me, lights, ambient=(0.16, 0.18, 0.16))
    return me


def build_swag(kit, span=31.0, z_end=48.0, z_low=28.0, name='HallSwag'):
    """A catenary across the road, two cables and two clamps (origin on the centreline, on the floor, running along Y)."""
    bm = bmesh.new()
    segs = 8
    k = 2.1
    for off, r, zo in ((0.0, 0.8, 0.0), (0.0, 0.62, -1.5)):
        path = []
        for i in range(segs + 1):
            t = i / segs * 2 - 1
            sag = (math.cosh(k * t) - 1) / (math.cosh(k) - 1)
            path.append(Vector((off, t * span, z_low + zo + (z_end - z_low) * sag)))
        tube(bm, path, r, sides=5, mat=0)
    for t in (-0.62, 0.62):
        sag = (math.cosh(k * t) - 1) / (math.cosh(k) - 1)
        z = z_low + (z_end - z_low) * sag
        ang = math.atan(2 * (z_end - z_low) * k * math.sinh(k * t) / ((math.cosh(k) - 1) * 2 * span))
        q = Vector((0, math.cos(ang), math.sin(ang))).to_track_quat('X', 'Z')
        kit.add_box(bm, (0, t * span, z - 0.6), (1.9, 1.8, 3.8), 1)
    uv = _uv_layer(bm)
    for f in bm.faces:
        if f.material_index == 1:
            for l in f.loops:
                l[uv].uv = (l.vert.co.y / 8, l.vert.co.z / 8)
    me = kit.mesh_from(name + 'Mesh', bm, [M['cable'], M['plate']], smooth=True)
    # Green from the code at either end, dying toward the sag.
    lights = []
    for y in (-span, span):
        lights.append(((-4.0, y * 0.96, z_end - 2), (0.14, 1.0, 0.26), 8.0, 0.5))
    kit.bake_light(me, lights, ambient=(0.12, 0.15, 0.13))
    return me


def build_kerb(kit):
    """One bay of kerb on the left of the road, its origin mid-bay on the road's centreline, with its inset light: a
    wedge of two bright rectangles facing the rider, green spilled on the kerb round it. One for each side of the road: the
    wedge only faces one way."""
    pieces = {}
    for side in (1, -1):
        bm = bmesh.new()
        prof = [(6.0, 0.0), (6.08, 0.14), (6.85, 0.36), (8.3, 0.4), (8.42, 0.0)]
        L = KERB_EVERY / 2 + 0.02
        rows = [-L, -1.6, 1.6, L]
        vr = [[bm.verts.new((x, side * d, z)) for d, z in prof] for x in rows]
        for a, b in zip(vr, vr[1:]):
            for i in range(len(prof) - 1):
                f = (a[i], a[i + 1], b[i + 1], b[i])
                bm.faces.new(f if side > 0 else f[::-1]).material_index = 0
        # Its wedge: dark sides, the lit face leaning back toward the rider.
        d0, d1 = 7.0, 8.2
        z_at = lambda d: (0.14 + (d - 6.08) * (0.22 / 0.77)) if d < 6.85 else (0.36 + (d - 6.85) * (0.04 / 1.45))  # noqa: E731
        mid = (d0 + d1) / 2
        ztop = 0.68
        xf, xb = -0.26, 0.1
        for da, db, m in ((d0, mid - 0.05, 2), (mid + 0.05, d1, 2)):
            pts = [(xf, side * da, z_at(da) + 0.02), (xf, side * db, z_at(db) + 0.02), (xb, side * db, ztop), (xb, side * da, ztop)]
            f = quad(bm, *(pts if side > 0 else pts[::-1]), m)
        # (The bar between them, the top and the sides, dark.)
        pts = [(xf, side * (mid - 0.05), z_at(mid) + 0.015), (xf, side * (mid + 0.05), z_at(mid) + 0.015), (xb, side * (mid + 0.05), ztop - 0.005), (xb, side * (mid - 0.05), ztop - 0.005)]
        quad(bm, *(pts if side > 0 else pts[::-1]), 1)
        for dd, flip in ((d0, 1), (d1, -1)):
            pts = [(xf, side * dd, z_at(dd)), (xb, side * dd, z_at(dd)), (xb, side * dd, ztop)]
            f = bm.faces.new([bm.verts.new(p) for p in (pts if flip * side > 0 else pts[::-1])])
            f.material_index = 1
        pts = [(xb, side * d0, ztop), (xb, side * d1, ztop), (xb + 0.2, side * d1, z_at(d1)), (xb + 0.2, side * d0, z_at(d0))]
        quad(bm, *(pts if side > 0 else pts[::-1]), 1)
        uv = _uv_layer(bm)
        for f in bm.faces:
            for l in f.loops:
                l[uv].uv = (l.vert.co.x / 6, l.vert.co.y / 6)
        me = kit.mesh_from('HallKerbMesh' + ('L' if side > 0 else 'R'), bm, [kit.MAT['concrete'], kit.MAT['dark'], kit.MAT['led']], recalc=False)
        kit.bake_light(me, [((-1.4, side * 7.5, 1.0), (0.14, 1.0, 0.25), 2.2, 0.9)], ambient=(0.07, 0.085, 0.075))
        pieces[side] = me
    return pieces


def build_ceiling_cluster(kit):
    """A cluster of small green-white lights under the roof."""
    bm = bmesh.new()
    kit.add_box(bm, (0, 0, ROOF_Z - 1.0), (6.6, 11.5, 2.0), 0)
    z = ROOF_Z - 2.02
    for row in (-1, 1):
        for c in (-1.5, -0.5, 0.5, 1.5):
            x0, x1 = row * 1.55 - 1.2, row * 1.55 + 1.2
            y0, y1 = c * 2.6 - 1.05, c * 2.6 + 1.05
            quad(bm, (x0, y0, z), (x0, y1, z), (x1, y1, z), (x1, y0, z), 1)
    me = kit.mesh_from('HallCeilClusterMesh', bm, [kit.MAT['dark'], M['ceil']], recalc=False)
    kit.bake_light(me, [((0, 0, ROOF_Z - 5.0), (0.3, 1.0, 0.4), 8.0, 1.0)], ambient=(0.3, 0.32, 0.3))
    return me


def build_beam(kit):
    """A girder across under the roof, wall to wall, a little light on it where the clusters are."""
    bm = bmesh.new()
    kit.add_box(bm, (0, 0, ROOF_Z - 3.0), (3.0, 2 * WALL_D + 2, 6.0), 0)
    kit.dice(bm, 40.0)
    me = kit.mesh_from('HallBeamMesh', bm, kit.MAT['dark'], recalc=False)
    kit.bake_light(me, [((0, 0, ROOF_Z - 10.0), (0.2, 1.0, 0.3), 26.0, 2.0)], ambient=(0.26, 0.3, 0.27))
    return me


def build_beacon(kit):
    """A stubby mast, a red lamp: stands on a tower's cap."""
    bm = bmesh.new()
    kit.lathe(bm, [(1.5, 0.0), (0.7, 0.8), (0.45, 4.2), (0.9, 4.4), (0.9, 4.8)], seg=6, mat=0)
    kit.lathe(bm, [(0.6, 4.8), (0.7, 5.5), (0.3, 6.4)], seg=6, mat=1)
    uv = _uv_layer(bm)
    for f in bm.faces:
        for l in f.loops:
            l[uv].uv = (l.vert.co.x / 8, l.vert.co.z / 8)
    me = kit.mesh_from('HallBeaconMesh', bm, [M['plate'], kit.MAT['red']])
    kit.bake_light(me, [((0, 0, 5.6), (1.0, 0.07, 0.05), 2.2, 2.0)], ambient=(0.22, 0.2, 0.2))
    return me


def _card(kit, name, mat, w, h, z0=0.0, x=0.0):
    """A soft card facing the rider (-X), its centre foot at the origin. UVs 0..1, row 0 up."""
    bm = bmesh.new()
    f = quad(bm, (x, w / 2, z0), (x, -w / 2, z0), (x, -w / 2, z0 + h), (x, w / 2, z0 + h), 0)
    uv = _uv_layer(bm)
    for l in f.loops:
        l[uv].uv = (0.5 - l.vert.co.y / w, (l.vert.co.z - z0) / h)
    return kit.mesh_from(name, bm, mat, recalc=False)


def build(kit):
    kit.register_texture('hallplate', tex_plate)
    kit.register_texture('hallrib', tex_rib)
    kit.register_texture('hallgrille', tex_grille)
    kit.register_texture('hallrack', tex_rack)
    kit.register_texture('hallmist', tex_mist, jpeg=False)
    kit.register_texture('hallflare', tex_flare, jpeg=False)
    p = kit.PREFIX
    M['plate'] = kit.material(f'{p}HallPlate', (0.5, 0.42, 0.36), 0.6, 0.1, tex='hallplate', spec=0.5)
    M['cable'] = kit.material(f'{p}HallCable', (0.1, 0.1, 0.1), 0.42, tex='hallrib', spec=0.6)
    M['grille'] = kit.material(f'{p}HallGrille', (0, 0, 0), 0.5, vcol=False, tex='hallgrille', emission=(1, 1, 1), strength=2.2, emit_tex=True)
    M['grille_dim'] = kit.material(f'{p}HallGrilleDim', (0, 0, 0), 0.5, vcol=False, tex='hallgrille', emission=(1, 1, 1), strength=0.55, emit_tex=True)
    M['ceil'] = kit.material(f'{p}HallCeilPanel', (0.55, 1.0, 0.55), 0.5, vcol=False, emission=(0.45, 1.0, 0.42), strength=3.2)
    M['floor'] = kit.material(f'{p}HallFloor', (0.2, 0.2, 0.2), 0.16, tex='concrete', spec=0.7)
    M['mist'] = kit.material(f'{p}HallMist', (0.42, 0.72, 0.46), 1.0, vcol=False, tex='hallmist', alpha_tex=True, spec=0.0, emission=(0.2, 0.55, 0.26), strength=0.3)
    M['flare'] = kit.material(f'{p}FlareMist', (1.0, 0.12, 0.07), 1.0, vcol=False, tex='hallflare', alpha_tex=True, spec=0.0, emission=(1.0, 0.035, 0.02), strength=5.0)
    M['rack'] = kit.material(f'{p}HallRack', (0, 0, 0), 0.6, vcol=False, tex='hallrack', emission=(1, 1, 1), strength=0.5, emit_tex=True)

    pieces = {}
    pieces['tower'] = kit.piece('HallTower', build_tower(kit))
    pieces['tower_b'] = kit.piece('HallTowerBeacon', build_tower(kit, beacon=True))
    pieces['rear'] = kit.piece('HallRear', build_rear(kit))
    pieces['fan_l'] = kit.piece('HallFanL', build_fan(kit, 1))
    pieces['fan_r'] = kit.piece('HallFanR', build_fan(kit, -1))
    pieces['swag'] = kit.piece('HallSwag', build_swag(kit))
    pieces['swag_hi'] = kit.piece('HallSwagHigh', build_swag(kit, z_end=54.0, z_low=41.0, name='HallSwagHigh'))
    kerb = build_kerb(kit)
    pieces['kerb_l'] = kit.piece('HallKerbL', kerb[1])
    pieces['kerb_r'] = kit.piece('HallKerbR', kerb[-1])
    pieces['cluster'] = kit.piece('HallCeilCluster', build_ceiling_cluster(kit))
    pieces['beam'] = kit.piece('HallBeam', build_beam(kit))
    pieces['beacon'] = kit.piece('HallBeacon', build_beacon(kit))
    pieces['mist'] = kit.piece('HallMistCard', _card(kit, 'HallMistCardMesh', M['mist'], 46.0, 8.0))
    pieces['flare'] = kit.piece('HallFlare', _card(kit, 'HallFlareMesh', M['flare'], 13.0, 13.0, z0=-6.5))
    bm = bmesh.new()
    f = quad(bm, (0, -30, 0), (0, 30, 0), (0, 30, 80), (0, -30, 80), 0)
    face_uvs(bm, seed=2, plate_scale=1 / 24)
    pieces['rack'] = kit.piece('HallRack', kit.mesh_from('HallRackMesh', bm, M['rack'], recalc=False))
    if PREVIEW:
        print('tris:', {k: kit.tris(v.data) for k, v in pieces.items()})
    return pieces


# --- The hall itself: floor, walls, roof, the two ends. --------------------------------------------------------------
TOWERS = []   # (s, d, scale z, beacon?)


def plan_towers():
    """Where the towers go: pairs from 50 m into the hall, spaced 37 to 43 m."""
    if TOWERS:
        return TOWERS
    rng = np.random.default_rng(2024)
    s = (S0 + 50.0)
    k = 0
    while s < (S1 - 61.0):
        sz = float(rng.choice([0.94, 1.0, 1.0, 1.06, 1.12]))
        sz2 = float(rng.choice([0.94, 1.0, 1.0, 1.06, 1.12]))
        beacon = k % 7 == 3
        TOWERS.append((s, sz, sz2, beacon))
        s += float(rng.uniform(37.0, 43.0))
        k += 1
    return TOWERS


def _ribbon(kit, name, rows, d_list, z_fn, mat, uv_scale, lights=None, ambient=(0.1, 0.1, 0.1), up=True, grp='Hall'):
    """A strip following the road: rows of s, across d_list, height z_fn(s, d)."""
    bm = bmesh.new()
    uv = _uv_layer(bm)
    vr = [[bm.verts.new(kit.along(s, d, z_fn(s, d))) for d in d_list] for s in rows]
    for i in range(len(rows) - 1):
        for j in range(len(d_list) - 1):
            f = bm.faces.new((vr[i][j], vr[i + 1][j], vr[i + 1][j + 1], vr[i][j + 1]) if up else (vr[i][j], vr[i][j + 1], vr[i + 1][j + 1], vr[i + 1][j]))
            for l, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)) if up else ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j))):
                l[uv].uv = (rows[a] * uv_scale, d_list[b] * uv_scale)
    me = kit.mesh_from(name, bm, mat, recalc=False)
    kit.bake_light(me, lights or [], ambient=ambient)
    kit.static(name, me, grp=grp)
    return me


def build_shell(kit):
    """Floor, far walls and roof in ~260 m chunks (the site merges by cells and culls), both ends."""
    towers = plan_towers()
    chunks = max(1, round((S1 - S0) / 260.0))
    edges = [S0 + (S1 - S0) * i / chunks for i in range(chunks + 1)]
    for ci in range(chunks):
        s0, s1 = edges[ci], edges[ci + 1]
        # (Rows on the kerb's lights, so the floor's spill sits by them.)
        first = math.ceil((s0 - (S0 + 6.0)) / KERB_EVERY)
        rows = [s0] + [(S0 + 6.0) + k * KERB_EVERY for k in range(first, 400) if s0 < (S0 + 6.0) + k * KERB_EVERY < s1] + [s1]
        lights = []
        for s, _a, _b, _bk in towers:
            if s0 - 60 < s < s1 + 60:
                for d in (TOWER_D, -TOWER_D):
                    # Pooled round the plinth on the rider's side, and between the plinth and the road.
                    p = kit.along(s - 18, d, 6.0)
                    lights.append((tuple(p), (0.14, 1.0, 0.26), 11.0, 0.9))
                    p = kit.along(s, d - math.copysign(19.0, d), 5.0)
                    lights.append((tuple(p), (0.14, 1.0, 0.26), 10.0, 0.75))
        for row in rows[1:-1]:
            for d in (7.5, -7.5):
                p = kit.along(row - 1.0, d * 1.2, 1.0)
                lights.append((tuple(p), (0.2, 1.0, 0.3), 2.6, 0.8))
        ds = [5.7, 8.4, 11.0, 15.0, 20.0, 27.0, 36.0, 48.0, 62.0, 80.0, 105.0, WALL_D]
        for sgn, tag in ((1, 'L'), (-1, 'R')):
            dl = [sgn * d for d in ds]
            _ribbon(kit, f'HallFloor{tag}{ci}', rows, dl, lambda s, d: -0.02, M['floor'], 1 / 14, lights=lights, ambient=(0.09, 0.14, 0.1), up=sgn > 0)
        # The walls and the roof: dark, a few rows, the glow near the floor.
        wrows = kit.frange(s0, s1 + 0.1, (s1 - s0) / 6)
        for sgn, tag in ((1, 'L'), (-1, 'R')):
            bm = bmesh.new()
            zs = [0.0, 16.0, 50.0, ROOF_Z]
            vr = [[bm.verts.new(kit.along(s, sgn * WALL_D, z)) for z in zs] for s in wrows]
            for i in range(len(wrows) - 1):
                for j in range(len(zs) - 1):
                    f = (vr[i][j], vr[i + 1][j], vr[i + 1][j + 1], vr[i][j + 1])
                    bm.faces.new(f if sgn < 0 else f[::-1]).material_index = 0
            me = kit.mesh_from(f'HallWall{tag}{ci}', bm, kit.MAT['dark'], recalc=False)
            cols = np.array([[0.5, 1.0, 0.6] if v.co.z < 1 else [0.5, 0.6, 0.52] for v in me.vertices])
            kit.set_vcol_rgb(me, cols)
            kit.static(f'HallWall{tag}{ci}', me, grp='Hall')
        rows_r = wrows
        _ribbon(kit, f'HallRoof{ci}', rows_r, [-WALL_D, -60.0, 60.0, WALL_D], lambda s, d: ROOF_Z, kit.MAT['dark'], 1 / 30, ambient=(0.5, 0.6, 0.52), up=False)


def build_ends(kit):
    """The two ends: a splayed throat from the lab's 14 x 8 door opening to the hall 30 m on, and the deep frame round the
    chamber's 40 x 30 mouth, its last 26 m."""
    def wall_with_hole(name, s, hw, h, face):
        """A wall across the hall at s, hole hw either side, up to h. face: +1 faces on along the road, -1 back."""
        bm = bmesh.new()
        x = lambda d, z: kit.along(s, d, z)  # noqa: E731
        ds = [-WALL_D, -hw, hw, WALL_D]
        zs = [0.0, h, ROOF_Z]
        vr = [[bm.verts.new(x(d, z)) for z in zs] for d in ds]
        for i in range(3):
            for j in range(2):
                if i == 1 and j == 0:
                    continue
                f = (vr[i][j], vr[i + 1][j], vr[i + 1][j + 1], vr[i][j + 1])
                bm.faces.new(f if face < 0 else f[::-1]).material_index = 0
        me = kit.mesh_from(name, bm, kit.MAT['dark'], recalc=False)
        kit.set_vcol_rgb(me, np.array([[0.6, 0.8, 0.65]] * len(me.vertices)))
        kit.static(name, me, grp='Hall')

    def throat(name, s0, s1, hw0, h0, hw1, h1, mat):
        """The four walls of a passage from one opening to another, facing in, diced for the light."""
        bm = bmesh.new()
        p = lambda s, d, z: kit.along(s, d, z)  # noqa: E731
        a, b = (s0, hw0, h0), (s1, hw1, h1)
        for (d0, z0), (d1, z1) in (((-1, 0), (-1, 1)), ((-1, 1), (1, 1)), ((1, 1), (1, 0))):
            quad(bm, p(a[0], d0 * a[1], z0 * a[2]), p(b[0], d0 * b[1], z0 * b[2]), p(b[0], d1 * b[1], z1 * b[2]), p(a[0], d1 * a[1], z1 * a[2]), 0)
        kit.dice(bm, 5.0)
        face_uvs(bm, seed=5)
        return kit.mesh_from(name, bm, mat, recalc=False)

    # The lab's end.
    wall_with_hole('HallEndIn', S0, 7.0, 8.0, 1)
    wall_with_hole('HallEndIn2', (S0 + 30.0), 26.0, 20.0, 1)
    me = throat('HallThroatIn', S0, (S0 + 30.0), 7.0, 8.0, 26.0, 20.0, M['plate'])
    # (Dark toward the lab's door, lit by the hall's glow at its mouth.)
    pos = np.array([v.co.x for v in me.vertices])
    t = np.clip((pos - kit.along(S0).x) / 30.0, 0, 1)[:, None]
    kit.set_vcol_rgb(me, np.array([[0.03, 0.05, 0.04]]) * (1 - t) + np.array([[0.12, 0.6, 0.2]]) * t ** 2)
    kit.static('HallThroatIn', me, grp='Hall')
    # The chamber's mouth: a thick wall with the 40 x 30 opening, frame ribs round it.
    wall_with_hole('HallEndOut', (S1 - 26.0), 20.0, 30.0, -1)
    wall_with_hole('HallEndOutBack', S1, 20.0, 30.0, 1)
    me = throat('HallMouth', (S1 - 26.0), S1, 20.0, 30.0, 20.0, 30.0, M['plate'])
    pos = np.array([v.co.x for v in me.vertices])
    t = np.clip((pos - kit.along((S1 - 26.0)).x) / 26.0, 0, 1)[:, None]
    kit.set_vcol_rgb(me, np.array([[0.14, 0.4, 0.2]]) * (1 - t) + np.array([[0.05, 0.1, 0.07]]) * t)
    kit.static('HallMouth', me, grp='Hall')
    # A stepped frame round the mouth, on the hall's side.
    bm = bmesh.new()
    for (d, z, sd, sz) in ((-23.5, 17.0, 7.0, 34.0), (23.5, 17.0, 7.0, 34.0), (0.0, 33.5, 54.0, 7.0)):
        kit.add_box(bm, kit.along(S1 - 28.0, d, z), (4.0, sd, sz), 0)
    face_uvs(bm, seed=4)
    me = kit.mesh_from('HallMouthFrame', bm, M['plate'], recalc=False)
    kit.bake_light(me, [(tuple(kit.along(S1 - 41.0, 0.0, 25.0)), (0.14, 1.0, 0.26), 28.0, 0.5)], ambient=(0.16, 0.18, 0.16))
    kit.static('HallMouthFrame', me, grp='Hall')


def place(kit, pieces):
    grp = 'Hall'
    towers = plan_towers()
    rng = np.random.default_rng(99)
    for s, sz_l, sz_r, beacon in towers:
        yaw = kit.heading(s)
        for d, sz, fan in ((TOWER_D, sz_l, pieces['fan_l']), (-TOWER_D, sz_r, pieces['fan_r'])):
            p = kit.along(s, d)
            kit.put(pieces['tower_b'] if beacon else pieces['tower'], p, yaw, scale=(1, 1, sz), grp=grp)
            kit.put(fan, p, yaw, grp=grp)
            if beacon:
                top = 63.2 * sz
                kit.put(pieces['beacon'], p + Vector((0, 0, top)), yaw, grp=grp)
                f = kit.along(s - 6.5, d - math.copysign(1.5, d), top + 2.2)  # (Ahead of the cap, so it can't cut it; a little in and down, as nearer.)
                kit.put(pieces['flare'], f, yaw, grp=grp)
        # A swag across the road at the far post of each pair, every other one a high one too.
        ss = s + 6.0
        kit.put(pieces['swag'], kit.along(ss), kit.heading(ss), scale=(1, 1, float(rng.uniform(0.96, 1.04))), grp=grp)
        if rng.random() < 0.45:
            ss = s - 6.0
            kit.put(pieces['swag_hi'], kit.along(ss), kit.heading(ss), grp=grp)
    # The row behind, irregular.
    for sgn in (1, -1):
        s = S0 + 45.0 + float(rng.uniform(0, 20))
        while s < S1 - 66.0:
            kit.put(pieces['rear'], kit.along(s, sgn * (REAR_D + float(rng.uniform(-3, 4)))), kit.heading(s), scale=(1, 1, float(rng.uniform(0.9, 1.15))), grp=grp)
            s += float(rng.uniform(30.0, 52.0))
    # The kerb.
    s = (S0 + 6.0)
    while s < (S1 - 26.0) - KERB_EVERY / 2:
        y = kit.heading(s)
        kit.put(pieces['kerb_l'], kit.along(s), y, grp=grp)
        kit.put(pieces['kerb_r'], kit.along(s), y, grp=grp)
        s += KERB_EVERY
    # The roof: its girders, and the line of lights over the road.
    s = (S0 + 50.0)
    while s < (S1 - 31.0):
        kit.put(pieces['beam'], kit.along(s), kit.heading(s), grp=grp)
        s += 46.0
    s = (S0 + 70.0)
    while s < (S1 - 31.0):
        kit.put(pieces['cluster'], kit.along(s), kit.heading(s), grp=grp)
        s += float(rng.uniform(55.0, 72.0))
    # Floor fog: a few soft low cards, wide ones through the gaps between the plinths (clear of them, or they'd cut a hard
    # line), narrow ones between the plinths' feet and the kerb (always clear of the road).
    for a, b in zip(towers, towers[1:]):
        mid = a[0] + 16.5  # (just past the plinth's buttress, clear of the next one's fan)
        for sgn in (1, -1):
            if rng.random() < 0.4:
                kit.put(pieces['mist'], kit.along(mid, sgn * float(rng.uniform(34.0, 38.0))), kit.heading(mid), scale=(1, 1, float(rng.uniform(0.8, 1.3))), grp=grp)
            if rng.random() < 0.6:
                s = a[0] + float(rng.uniform(0, 30))
                kit.put(pieces['mist'], kit.along(s, sgn * float(rng.uniform(15.0, 16.0))), kit.heading(s), scale=(1, 0.3, float(rng.uniform(0.6, 1.0))), grp=grp)
    # Far racks on the far walls, a dim glow behind the rows.
    s = S0 + 90.0
    while s < S1 - 56.0:
        for sgn in (1, -1):
            if rng.random() < 0.8:
                kit.put(pieces['rack'], kit.along(s + float(rng.uniform(-15, 15)), sgn * (WALL_D - 1.0)), kit.heading(s) + (math.pi / 2 if sgn > 0 else -math.pi / 2), grp=grp)
        s += float(rng.uniform(65.0, 90.0))
    build_shell(kit)
    build_ends(kit)
    if PREVIEW:
        _report(kit)
        _preview_extras(kit)


def _report(kit):
    """Triangle totals: everything, and within the site's 1.2 km draw distance of the worst place on the road."""
    items = []
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or o.name.startswith('City5.Preview'):
            continue
        c = sum((Vector(b) for b in o.bound_box), Vector()) / 8
        items.append((np.array(o.matrix_world @ c if o.parent is None else o.location + c), kit.tris(o.data)))
    pos = np.array([i[0][:2] for i in items])
    tri = np.array([i[1] for i in items])
    worst = 0
    for s in kit.frange(S0, S1, 100.0):
        p = np.array(kit.along(s))[:2]
        worst = max(worst, int(tri[np.linalg.norm(pos - p, axis=1) < 1200.0].sum()))
    print(f'total tris {tri.sum()} in {len(items)} objects; worst within 1.2 km {worst}')


def _preview_extras(kit):
    """Only under preview.py, never exported: a stand-in deck, the site's fog (the compositor, from depth, linear like three's)
    and a touch of bloom."""
    bm = bmesh.new()
    uv = _uv_layer(bm)
    rows = kit.frange(S0, S1, 10.0)
    vr = [[bm.verts.new(kit.along(s, d, 0.0)) for d in (-5.9, 5.9)] for s in rows]
    for i in range(len(rows) - 1):
        f = bm.faces.new((vr[i][0], vr[i + 1][0], vr[i + 1][1], vr[i][1]))
        for l, (a, b) in zip(f.loops, ((i, 0), (i + 1, 0), (i + 1, 1), (i, 1))):
            l[uv].uv = (b, rows[a] / 27.0)
    me = kit.mesh_from('PreviewDeck', bm, kit.MAT['asphalt'], recalc=False)
    kit.set_vcol_rgb(me, np.ones((len(me.vertices), 3)) * 0.7)
    kit.static('PreviewDeck', me, grp='Preview')
    kit.MAT['asphalt'].node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.12
    scene = bpy.context.scene
    scene.eevee.use_raytracing = True
    scene.eevee.ray_tracing_options.resolution_scale = '1'
    vl = scene.view_layers[0]
    vl.use_pass_z = True
    tree = bpy.data.node_groups.new('PreviewFog', 'CompositorNodeTree')
    scene.compositing_node_group = tree
    tree.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = tree.nodes.new('CompositorNodeRLayers')
    sub = tree.nodes.new('ShaderNodeMath')
    sub.operation = 'SUBTRACT'
    sub.inputs[1].default_value = 40.0
    div = tree.nodes.new('ShaderNodeMath')
    div.operation = 'DIVIDE'
    div.inputs[1].default_value = 860.0
    div.use_clamp = True
    tree.links.new(rl.outputs['Depth'], sub.inputs[0])
    tree.links.new(sub.outputs[0], div.inputs[0])
    mix = tree.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs['B'].default_value = (*FOG, 1)
    tree.links.new(div.outputs[0], mix.inputs['Factor'])
    tree.links.new(rl.outputs['Image'], mix.inputs['A'])
    glare = tree.nodes.new('CompositorNodeGlare')
    glare.inputs['Type'].default_value = 'Bloom'
    glare.inputs['Threshold'].default_value = 0.75
    glare.inputs['Strength'].default_value = 0.55
    glare.inputs['Size'].default_value = 0.6
    tree.links.new(mix.outputs['Result'], glare.inputs['Image'])
    out = tree.nodes.new('NodeGroupOutput')
    tree.links.new(glare.outputs['Image'], out.inputs[0])


def _shots():
    """The camera's on the first straight, dead along +X, where it can be; elsewhere from the kit's frame at import."""
    import kit as K
    out = {}
    # Fitted to the reference: on the centreline, the near pair just ahead, looking a little up.
    near = next(t[0] for t in plan_towers() if t[0] >= S0 + 370.0)
    out['ref'] = ((near - 51.0, 0.0, 1.5), (near + 49.0, 0.0, 18.0), 70.0)
    a = K.hall_stretch(2)[0] + 50.0
    e, l = K.along(a, 0.0, 1.5), K.along(a + 110.0, 0.0, 6.0)
    out['straight2'] = (tuple(e), tuple(l), 66.0)
    a = K.hall_stretch(3)[0] + 80.0
    e, l = K.along(a, 0.0, 1.5), K.along(a + 110.0, 0.0, 12.0)
    out['bend'] = (tuple(e), tuple(l), 70.0)
    e, l = K.along(S0 + 2.0, 0.0, 1.5), K.along(S0 + 110.0, 0.0, 10.0)
    out['in'] = (tuple(e), tuple(l), 70.0)
    e, l = K.along(S1 - 156.0, 0.0, 1.5), K.along(S1 - 16.0, 0.0, 16.0)
    out['mouth'] = (tuple(e), tuple(l), 70.0)
    out['high'] = ((S0 + 330.0, 60.0, 90.0), (S0 + 450.0, 0.0, 12.0), 60.0)
    out['low'] = ((near - 34.0, 16.0, 2.0), (near - 10.0, 34.0, 12.0), 70.0)
    return out


SHOTS = _shots()
