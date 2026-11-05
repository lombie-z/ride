"""The lab's specimen tanks (concept-core-lab), and what's in them: art/core/kit.py's contract, build(kit) and place(kit, pieces).

No refraction: from outside in, each tank is
  - its liner (City5Liner, opaque, emissive): a closed cylinder facing inward and culled from outside, so whatever way you
    look into the tank you see only its far wall, a painted green gradient with tendrils' shadows, brighter low down;
  - the specimen, opaque, its light painted in (U of its ramp texture = how lit, so it's emissive, per vertex: the site has no
    lamps to rim-light it with), with thin kit.MAT['led'] details;
  - one see-through shell (City5TankFluid), facing out and culled from inside, so it's only ever drawn once, with the bubbles and
    flecks in its texture;
  - two thin highlights on the glass (City5StreakTankGlass).
Collars and consoles share one painted atlas (City5TankWhite), lit in the paint: lighter toward the road, green near the glass.

The specimens are signed distance fields (smooth unions of tapered chains and ellipsoids), polygonised with surface nets and
decimated, so limbs grow out of bodies. They take a few seconds to build.
"""
import math

import bpy
import numpy as np
from mathutils import Vector

kit = None  # (set by build)

TANK_Z0, TANK_Z1 = 1.4, 8.5          # the glass
COLLAR_TOP = 9.75
R_LINER, R_FLUID = 3.22, 3.3
R_COLLAR, R_BASE = 3.55, 3.62
SEG = 28
LINER_GLOW = 1.25    # (City5Liner's emission strength)
# How each specimen faces in its tank: degrees off facing straight down the road at the rider, toward the road's middle.
FACING = {'Embryo': 28.0, 'Stalker': 52.0, 'Larva': 62.0}
HEADING = {'Embryo': 0.0, 'Stalker': 0.0, 'Larva': 0.0}   # (where its face points in its own frame: the larva's is along its coil)
ORDER = ['Embryo', 'Stalker', 'Larva']
CONSOLE_BACK = -1.9   # how far ahead of the tank's middle (toward the oncoming rider) its console stands
CONSOLE_D = 8.36
CONSOLE_YAW = math.radians(30.0)


# --- Mesh builder: faces with their own UVs and material slots, wound as given. -------------------------------------------
class B:
    def __init__(self):
        self.v, self.f, self.m, self.uv, self.flat = [], [], [], [], []

    def vert(self, p):
        self.v.append((float(p[0]), float(p[1]), float(p[2])))
        return len(self.v) - 1

    def face(self, vi, mat=0, uv=None, flat=False):
        self.f.append(tuple(vi))
        self.m.append(mat)
        self.uv.append(uv if uv is not None else [(0.0, 0.0)] * len(vi))
        self.flat.append(flat)

    def poly(self, pts, mat=0, uv=None, flat=True):
        self.face([self.vert(p) for p in pts], mat, uv, flat)

    @property
    def tris(self):
        return sum(len(f) - 2 for f in self.f)

    def mesh(self, name, mats):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        for m in mats:
            me.materials.append(m)
        me.polygons.foreach_set('material_index', self.m)
        me.polygons.foreach_set('use_smooth', [not x for x in self.flat])
        uv = me.uv_layers.new(name='UVMap')
        flat_uv = [c for corners in self.uv for co in corners for c in co]
        uv.data.foreach_set('uv', flat_uv)
        me.update()
        return me


def tube(b, pts, radii, sides=5, mat=0, uvf=None, flat=False, closed_tip=True):
    """A tube along pts (Vectors), its radius from `radii` (one each, or a single value)."""
    n = len(pts)
    if isinstance(radii, (int, float)):
        radii = [radii] * n
    rings = []
    prev_side = None
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        if prev_side is None:
            s = t.cross(Vector((0.13, 0.27, 0.95)))
        else:
            s = prev_side - t * prev_side.dot(t)  # (carried along, so a tube can't twist flat)
        s.normalize()
        prev_side = s
        u = s.cross(t).normalized()
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides
            ring.append(b.vert(p + (s * math.cos(a) + u * math.sin(a)) * radii[i]))
        rings.append(ring)
    uvv = uvf if uvf is not None else (lambda i: (0.0, 0.0))
    for i, (r0, r1) in enumerate(zip(rings, rings[1:])):
        for k in range(sides):
            j = (k + 1) % sides
            b.face((r0[k], r0[j], r1[j], r1[k]), mat, [uvv(i), uvv(i), uvv(i + 1), uvv(i + 1)], flat)
    if closed_tip:
        b.face(rings[-1], mat, [uvv(n - 1)] * sides, flat)
    return rings


def spline(ctrl, per=6):
    """A Catmull-Rom through control points; returns Vectors."""
    c = [Vector(p) for p in ctrl]
    c = [c[0] * 2 - c[1]] + c + [c[-1] * 2 - c[-2]]
    out = []
    for i in range(1, len(c) - 2):
        p0, p1, p2, p3 = c[i - 1], c[i], c[i + 1], c[i + 2]
        for k in range(per):
            t = k / per
            out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3))
    out.append(c[-2])
    return out


def smooth_values(vals, per=6):
    out = []
    for a, b in zip(vals, vals[1:]):
        for k in range(per):
            t = k / per
            out.append(a + (b - a) * t * t * (3 - 2 * t))
    out.append(vals[-1])
    return out


# --- Fields: smooth unions of primitives on a grid, then surface nets. ----------------------------------------------------
class Field:
    def __init__(self, lo, hi, h):
        self.h = h
        self.lo = np.asarray(lo, float)
        self.n = np.ceil((np.asarray(hi, float) - self.lo) / h).astype(int) + 1
        self.x = [self.lo[a] + np.arange(self.n[a]) * h for a in range(3)]
        self.f = np.full(self.n, 2.0, np.float32)

    def box(self, lo, hi):
        i0 = np.clip(np.floor((np.asarray(lo) - self.lo) / self.h).astype(int), 0, self.n - 1)
        i1 = np.clip(np.ceil((np.asarray(hi) - self.lo) / self.h).astype(int) + 1, 1, self.n)
        s = (slice(i0[0], i1[0]), slice(i0[1], i1[1]), slice(i0[2], i1[2]))
        X = self.x[0][s[0]][:, None, None]
        Y = self.x[1][s[1]][None, :, None]
        Z = self.x[2][s[2]][None, None, :]
        return s, X, Y, Z

    def blend(self, s, d, k, cut=False):
        a = self.f[s]
        if cut:  # (a smooth subtraction)
            e = -d
            w = np.maximum(k - np.abs(a - e), 0.0) / k
            self.f[s] = np.maximum(a, e) + w * w * k * 0.25
        elif k <= 0:
            self.f[s] = np.minimum(a, d)
        else:
            w = np.maximum(k - np.abs(a - d), 0.0) / k
            self.f[s] = np.minimum(a, d) - w * w * k * 0.25

    def chain(self, ctrl, radii, k=0.1, per=6, rib=None, cut=False):
        """A tapering limb through control points, smooth-unioned in with blend radius k. rib(arc metres) -> radius multiplier."""
        pts = np.array([tuple(p) for p in spline(ctrl, per)])
        rad = np.array(smooth_values(list(radii), per))
        seg = np.linalg.norm(pts[1:] - pts[:-1], axis=1)
        arc = np.concatenate([[0.0], np.cumsum(seg)])
        amp = 1.25 if rib is not None else 1.0
        pad = rad.max() * amp + k + 3 * self.h
        s_all, _, _, _ = self.box(pts.min(0) - pad, pts.max(0) + pad)
        tmp = np.full(self.f[s_all].shape, 2.0, np.float32)
        off = np.array([sl.start for sl in s_all])
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            pp = max(rad[i], rad[i + 1]) * amp + k + 3 * self.h
            s, X, Y, Z = self.box(np.minimum(a, b) - pp, np.maximum(a, b) + pp)
            ba = b - a
            ll = float(ba @ ba) + 1e-9
            px, py, pz = X - a[0], Y - a[1], Z - a[2]
            t = np.clip((px * ba[0] + py * ba[1] + pz * ba[2]) / ll, 0.0, 1.0)
            d = np.sqrt((px - t * ba[0]) ** 2 + (py - t * ba[1]) ** 2 + (pz - t * ba[2]) ** 2)
            r = rad[i] + (rad[i + 1] - rad[i]) * t
            if rib is not None:
                r = r * rib(arc[i] + t * seg[i])
            d = d - r
            sub = tuple(slice(s[a2].start - off[a2], s[a2].stop - off[a2]) for a2 in range(3))
            tmp[sub] = np.minimum(tmp[sub], d)
        self.blend(s_all, tmp, k, cut)

    def ball(self, c, r, k=0.1, rot=None, cut=False):
        """An ellipsoid: radii r (one, or three), turned by the 3 x 3 rot."""
        r3 = np.array([r, r, r] if isinstance(r, (int, float)) else r, float)
        pad = r3.max() + k + 3 * self.h
        s, X, Y, Z = self.box(np.asarray(c) - pad, np.asarray(c) + pad)
        px, py, pz = X - c[0], Y - c[1], Z - c[2]
        if rot is not None:
            R = np.asarray(rot)  # (columns are its local axes)
            px, py, pz = (px * R[0, 0] + py * R[1, 0] + pz * R[2, 0], px * R[0, 1] + py * R[1, 1] + pz * R[2, 1],
                          px * R[0, 2] + py * R[1, 2] + pz * R[2, 2])
        k0 = np.sqrt((px / r3[0]) ** 2 + (py / r3[1]) ** 2 + (pz / r3[2]) ** 2)
        k1 = np.sqrt((px / r3[0] ** 2) ** 2 + (py / r3[1] ** 2) ** 2 + (pz / r3[2] ** 2) ** 2)
        d = k0 * (k0 - 1.0) / (k1 + 1e-6)
        self.blend(s, np.broadcast_to(d, self.f[s].shape).astype(np.float32), k, cut)

    def lump(self, amp, freq, seed):
        """Roughens the surface with a sum of sines: soft lumps, amp metres, about 1 / freq metres across."""
        rng = np.random.default_rng(seed)
        X, Y, Z = (self.x[0].astype(np.float32)[:, None, None], self.x[1].astype(np.float32)[None, :, None], self.x[2].astype(np.float32)[None, None, :])
        out = np.zeros(self.f.shape, np.float32)
        for k in range(7):
            d = rng.normal(size=3)
            d = d / np.linalg.norm(d) * freq * 2 * math.pi * rng.uniform(0.6, 1.8)
            out += np.sin(X * d[0] + Y * d[1] + Z * d[2] + rng.uniform(0, 6.3))
        self.f += amp * out / 2.0

    def sample(self, p):
        """Trilinear lookups at points n x 3."""
        q = (np.asarray(p) - self.lo) / self.h
        i = np.clip(np.floor(q).astype(int), 0, self.n - 2)
        t = np.clip(q - i, 0.0, 1.0)
        f = self.f
        out = 0.0
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    w = ((t[:, 0] if dx else 1 - t[:, 0]) * (t[:, 1] if dy else 1 - t[:, 1]) * (t[:, 2] if dz else 1 - t[:, 2]))
                    out = out + w * f[i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz]
        return out

    def surface(self):
        """Surface nets: (vertices m x 3, quads q x 4)."""
        f = self.f
        inside = f < 0
        # The cells with both signs at their corners.
        c = np.zeros(np.array(f.shape) - 1, np.int8)
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    c += inside[dx:f.shape[0] - 1 + dx, dy:f.shape[1] - 1 + dy, dz:f.shape[2] - 1 + dz].astype(np.int8)
        active = (c > 0) & (c < 8)
        idx = np.full(active.shape, -1, np.int32)
        cells = np.argwhere(active)
        idx[active] = np.arange(len(cells))
        pos = np.zeros((len(cells), 3))
        cnt = np.zeros(len(cells))
        corners = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1)]
        edges = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
        for a, b in edges:
            ca, cb = np.array(corners[a]), np.array(corners[b])
            va = f[cells[:, 0] + ca[0], cells[:, 1] + ca[1], cells[:, 2] + ca[2]]
            vb = f[cells[:, 0] + cb[0], cells[:, 1] + cb[1], cells[:, 2] + cb[2]]
            hit = (va < 0) != (vb < 0)
            t = va[hit] / (va[hit] - vb[hit])
            pos[hit] += ca + (cb - ca) * t[:, None]
            cnt[hit] += 1
        pos = cells + pos / np.maximum(cnt, 1)[:, None]
        verts = self.lo + pos * self.h
        quads = []
        for ax in range(3):
            u, w = [(1, 2), (0, 2), (0, 1)][ax]
            hi = [None, None, None]
            hi[ax] = slice(1, None)
            lo = [None, None, None]
            lo[ax] = slice(None, -1)
            ins_lo = inside[tuple(slice(None) if s is None else s for s in lo)]
            ins_hi = inside[tuple(slice(None) if s is None else s for s in hi)]
            cross = ins_lo != ins_hi
            # Not on the grid's outer edges (no cell either side).
            e = np.argwhere(cross)
            e = e[(e[:, u] > 0) & (e[:, w] > 0) & (e[:, u] < f.shape[u] - 1) & (e[:, w] < f.shape[w] - 1)]
            if not len(e):
                continue
            flip = ins_lo[e[:, 0], e[:, 1], e[:, 2]]
            def cell(du, dw):
                c2 = e.copy()
                c2[:, u] += du
                c2[:, w] += dw
                return idx[c2[:, 0], c2[:, 1], c2[:, 2]]
            q = np.stack([cell(-1, -1), cell(0, -1), cell(0, 0), cell(-1, 0)], 1)
            # (Wound outward: the sign of the crossing, and which axis it's along.)
            want = flip if ax != 1 else ~flip
            q[want] = q[want][:, ::-1]
            quads.append(q)
        quads = np.concatenate(quads)
        return verts, quads[(quads >= 0).all(1)]


def decimated(verts, quads, target):
    """Surface-nets output down to about `target` triangles, by Blender's collapse decimator: (vertices, faces, normals)."""
    me = bpy.data.meshes.new('tmp')
    me.from_pydata(verts.tolist(), [], quads.tolist())
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    me.update()
    ob = bpy.data.objects.new('tmp', me)
    bpy.context.scene.collection.objects.link(ob)
    sm = ob.modifiers.new('s', 'SMOOTH')
    sm.factor, sm.iterations = 0.6, 3
    mod = ob.modifiers.new('d', 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = target / max(1, 2 * len(quads))
    mod.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    done = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.context.scene.collection.objects.unlink(ob)
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    n = len(done.vertices)
    co, no = np.zeros(n * 3), np.zeros(n * 3)
    done.vertices.foreach_get('co', co)
    done.vertex_normals.foreach_get('vector', no)
    faces = [tuple(p.vertices) for p in done.polygons]
    bpy.data.meshes.remove(done)
    return co.reshape(-1, 3), faces, no.reshape(-1, 3)


def paint(field, co, no, rim_dir=(0.0, -1.0, 0.0), gain=1.0):
    """How lit each vertex is, 0..1: the tank's glow from all round it, stronger low down and underneath, a rim, the creases dark."""
    z = co[:, 2]
    low = kit.smoothstep(6.5, 1.5, z)
    top = kit.smoothstep(5.5, 8.4, z)
    b = 0.09 + 0.55 * low * (0.42 - 0.58 * no[:, 2]).clip(0, 1) + 0.28 * top * (0.45 + 0.55 * no[:, 2])
    rd = np.asarray(rim_dir, float)
    rd = rd / np.linalg.norm(rd)
    facing = no @ rd
    b += 0.5 * (1 - np.abs(facing)) ** 2.6 + 0.14 * np.clip(facing, 0, 1) ** 1.5
    # Creases: how soon the field closes up along the normal, near and further off.
    near = field.sample(co + no * 0.08) / 0.08
    far = field.sample(co + no * 0.3) / 0.3
    cav = np.clip(near, 0, 1) * 0.45 + np.clip(far, 0, 1) * 0.55
    return np.clip(b * (0.3 + 0.7 * cav ** 1.5) * gain, 0, 1)


def smoothed(vals, faces, rounds=2):
    """Evens per-vertex values out over a mesh's edges (a decimated mesh's vertices are too uneven to take them raw)."""
    e = np.array([(f[i], f[(i + 1) % len(f)]) for f in faces for i in range(len(f))])
    for _ in range(rounds):
        tot, cnt = np.zeros(len(vals)), np.zeros(len(vals))
        np.add.at(tot, e[:, 0], vals[e[:, 1]])
        np.add.at(cnt, e[:, 0], 1)
        vals = 0.45 * vals + 0.55 * tot / np.maximum(cnt, 1)
    return vals


def assemble(name, field, target, extra, mats, rim_dir=(0.0, -1.0, 0.0), gain=1.0, tube_lit=0.2):
    """The specimen's piece: its field's surface plus `extra`'s tubes and lights. `extra` slot 0 is the specimen's own material."""
    verts, quads = field.surface()
    co, faces, no = decimated(verts, quads, target - extra.tris)
    if (field.sample(co + no * 0.06) > 0).mean() < 0.5:  # (outward, whatever the nets wound)
        no = -no
        faces = [f[::-1] for f in faces]
    lit = smoothed(paint(field, co, no, rim_dir, gain), faces)
    b = B()
    for p in co:
        b.vert(p)
    for f in faces:
        b.face(f, 0, [(float(lit[i]), float(co[i][2] * 0.31 + co[i][0] * 0.17)) for i in f])
    base = len(co)
    b.v.extend(extra.v)
    for f, m, uv, fl in zip(extra.f, extra.m, extra.uv, extra.flat):
        b.face([i + base for i in f], m, uv, fl)
    me = b.mesh(f'{kit.PREFIX}{name}', mats)
    # The same light in the vertex colours (they multiply the base colour, which the site's hemisphere and env map light).
    all_lit = np.concatenate([lit, np.full(len(extra.v), tube_lit)])
    kit.set_vcol_rgb(me, np.outer(0.35 + 0.65 * all_lit, (0.75, 1.0, 0.75)))
    return me


# --- The specimens. All in a tank's frame: floor z 0, its axis at the origin, facing +x; inside r < 3.2, z 1.4..8.5. ----------
def tethers(b, routes, r=0.07, per=3, sides=4, lit=0.16):
    uv = lambda i: (lit, i * 0.1)
    for ctrl in routes:
        pts = spline(ctrl, per)
        tube(b, pts, r if not isinstance(r, list) else r, sides, 0, uv)


def diamond(b, c, axis, length, w, mat):
    """A little elongated octahedron: a lit node."""
    axis = Vector(axis).normalized()
    side = axis.cross(Vector((0.21, 0.37, 0.9))).normalized()
    up = side.cross(axis).normalized()
    c = Vector(c)
    top, bot = b.vert(c + axis * length), b.vert(c - axis * length)
    ring = [b.vert(c + side * w), b.vert(c + up * w), b.vert(c - side * w), b.vert(c - up * w)]
    for i in range(4):
        j = (i + 1) % 4
        b.face((top, ring[i], ring[j]), mat, flat=True)
        b.face((bot, ring[j], ring[i]), mat, flat=True)


def plated(b, path, radii, wave, dorsal, sides=12, mat=0, flare=1.12, tuck=0.8, squash=0.1):
    """A loft of overlapping plates along `path` (tail to head): each flares at its rear edge and tucks under the next, with
    exact rings, so the ribs stay crisp at any budget. wave(radius) = a plate's length; dorsal(point) = which way is up.
    Returns (a light multiplier per vertex added, plates [(arc, point, tangent, up, radius)])."""
    seg = [(q - p).length for p, q in zip(path, path[1:])]
    arc = np.concatenate([[0.0], np.cumsum(seg)])

    def at(s):
        i = max(min(int(np.searchsorted(arc, s)), len(path) - 1), 1)
        t = min(max((s - arc[i - 1]) / max(arc[i] - arc[i - 1], 1e-9), 0.0), 1.0)
        return path[i - 1].lerp(path[i], t), (path[i] - path[i - 1]).normalized(), radii[i - 1] + (radii[i] - radii[i - 1]) * t

    crease, plates, rings = [], [], []
    s0 = 0.0
    while s0 < arc[-1] - 1e-3:
        _, _, r = at(s0)
        ln = min(wave(r), arc[-1] - s0)
        for t, sf, c in ((0.0, flare, 1.3), (1.0, tuck, 0.3)):
            p, tan, r = at(s0 + ln * t)
            up = dorsal(p)
            up = (up - tan * up.dot(tan)).normalized()
            side = tan.cross(up).normalized()
            ring = []
            for k in range(sides):
                a = 2 * math.pi * k / sides
                # (Flattened a little under the belly, a keel along the back.)
                keel = 1.0 + squash * max(math.cos(a), 0.0) ** 6 - squash * 0.7 * max(-math.cos(a), 0.0) ** 2
                ring.append(b.vert(p + (up * math.cos(a) + side * math.sin(a)) * r * sf * keel))
                crease.append(c)
            rings.append(ring)
        p, tan, r = at(s0 + ln * 0.42)
        up = dorsal(p)
        plates.append((s0 + ln * 0.42, p, tan, (up - tan * up.dot(tan)).normalized(), r))
        s0 += ln
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(sides):
            j = (k + 1) % sides
            b.face((r0[k], r0[j], r1[j], r1[k]), mat)
    b.face(rings[0], mat)
    b.face(rings[-1][::-1], mat)
    return crease, plates


def vnormals(v, faces):
    v = np.asarray(v)
    n = np.zeros_like(v)
    for f in faces:
        fv = v[list(f)]
        n[list(f)] += np.cross(fv[1] - fv[0], fv[-1] - fv[0])
    return n / (np.linalg.norm(n, axis=1)[:, None] + 1e-9)


def lit_uvs(b, field, n0=0, f0=0, crease=None, rim_dir=(0.0, -1.0, 0.0), gain=1.0):
    """Fills in b's faces' UVs from face f0 on, from how lit their vertices (from n0 on) are."""
    co = np.array(b.v[n0:])
    faces = [tuple(i - n0 for i in f) for f in b.f[f0:]]
    no = vnormals(co, faces)
    if (field.sample(co + no * 0.06) > field.sample(co - no * 0.06)).mean() < 0.5:
        no = -no
    lit = paint(field, co, no, rim_dir, gain)
    if crease is not None:
        c = np.ones(len(co))
        c[:len(crease)] = crease
        lit = np.clip(lit * c, 0, 1)
    for k, f in enumerate(faces):
        b.uv[f0 + k] = [(float(lit[i]), float(co[i][2] * 0.31 + co[i][0] * 0.17)) for i in f]
    return lit


def make_embryo(mats):
    """Curled up under its own head: a skull as big as its body, long and smooth and swept back, a groove down it, a pinched
    little face tucked in; arms and legs drawn up tight, spider-thin below the joint, long fingers."""
    f = Field((-3.0, -1.95, 1.5), (2.0, 1.95, 8.45), 0.042)
    back = [(0.8, 0, 2.02), (0.15, 0, 1.84), (-0.58, 0, 2.0), (-1.22, 0, 2.7), (-1.58, 0, 3.6), (-1.52, 0, 4.45), (-1.18, 0, 5.1), (-0.66, 0, 5.52)]
    rad = [0.05, 0.2, 0.5, 0.8, 0.92, 0.88, 0.7, 0.56]
    f.chain(back, rad, 0.2)
    f.ball((-0.55, 0, 3.22), (1.02, 0.92, 1.12), 0.45)   # the belly
    f.ball((-0.86, 0, 4.48), (0.8, 0.86, 0.86), 0.36)    # the chest
    # The spine, standing out of the back, off the curve's outside.
    bp = spline(back, 6)
    br = smooth_values(rad, 6)
    for i in range(9, len(bp) - 3, 2):
        t = (bp[i + 1] - bp[i - 1]).normalized()
        out = Vector((-t.z, 0, t.x))
        if out.x > 0:
            out = -out
        f.ball(tuple(bp[i] + out * br[i] * 1.02), (0.22, 0.14, 0.2), 0.07)
    # The skull.
    skull = [(0.36, 0, 5.4), (-0.18, 0, 5.98), (-0.88, 0, 6.62), (-1.52, 0, 7.14), (-2.0, 0, 7.46)]
    f.chain(skull, [0.5, 0.86, 1.04, 0.92, 0.6], 0.3, per=8)
    f.chain([(-0.5, 0, 7.7), (-1.3, 0, 8.1), (-2.2, 0, 8.05), (-2.55, 0, 7.75)], [0.07, 0.09, 0.08, 0.05], 0.16, cut=True)  # its groove
    # The face: a brow, a blade of a snout, hollow eyes, two little mandibles.
    f.chain([(0.62, 0, 5.72), (0.96, 0, 5.36), (1.2, 0, 4.92), (1.28, 0, 4.56)], [0.36, 0.27, 0.15, 0.05], 0.2)
    for sy in (-1, 1):
        f.ball((1.0, sy * 0.3, 5.54), (0.22, 0.16, 0.13), 0.08, cut=True)
        f.chain([(0.62, sy * 0.3, 5.12), (0.98, sy * 0.26, 4.68), (1.06, sy * 0.1, 4.28)], [0.13, 0.08, 0.035], 0.08)
    # Arms, then fingers curling in toward the face.
    for sy, w in ((-1, 0.0), (1, 0.14)):
        f.chain([(-0.72, sy * 0.8, 4.78), (0.12, sy * 1.28, 3.72), (0.98, sy * 0.92, 3.86 + w)], [0.24, 0.13, 0.1], 0.16)
        for a in (-0.3, 0.0, 0.3):
            f.chain([(0.98, sy * 0.92, 3.86 + w), (1.36, sy * (0.92 + a * 0.55), 4.02 + w + a * 0.2), (1.6, sy * (0.86 + a * 0.9), 3.82 + w + a * 0.3)],
                    [0.075, 0.06, 0.035], 0.03, per=4)
    # Legs: the knee up to the elbow, a thin shin back under, long toes.
    for sy in (-1, 1):
        f.chain([(-0.78, sy * 0.66, 2.72), (1.02, sy * 0.98, 3.34), (0.22, sy * 0.76, 2.2)], [0.38, 0.16, 0.1], 0.22)
        for a in (-0.28, 0.0, 0.28):
            f.chain([(0.22, sy * 0.76, 2.2), (0.72, sy * (0.76 + a), 1.96), (1.16, sy * (0.76 + a * 1.5), 2.16)], [0.08, 0.06, 0.03], 0.03, per=4)
    f.lump(0.016, 1.7, 7)
    x = B()
    # Its tethers: the navel, the skull, the spine; up to the top collar and down to the base.
    cord = [(0.3, 0.0, 3.0), (1.2, -0.5, 2.7), (1.7, -1.4, 3.6), (1.1, -2.0, 5.2), (0.6, -2.2, 7.0), (0.7, -2.25, 8.5)]
    cp = spline(cord, 4)
    for i in range(3, len(cp) - 1, 5):
        diamond(x, cp[i], cp[i + 1] - cp[i - 1], 0.13, 0.085, 1)
    tethers(x, [cord,
                [(-0.9, 0.42, 7.62), (-0.55, 0.85, 7.98), (-0.72, 1.3, 8.5)],
                [(-2.2, -0.28, 7.82), (-2.1, -0.7, 8.08), (-2.25, -1.05, 8.5)],
                [(-2.0, 0.3, 4.4), (-2.45, 1.0, 5.4), (-2.3, 1.45, 6.8), (-1.85, 1.6, 8.5)],
                [(-1.2, 0.25, 2.5), (-1.85, 0.55, 2.0), (-2.2, 1.2, 1.7), (-2.35, 1.45, 1.42)],
                [(-1.6, -0.5, 3.1), (-2.35, -0.95, 3.05), (-2.55, -1.25, 2.0), (-2.5, -1.5, 1.42)]], r=0.06, per=4)
    return assemble('SpecimenEmbryo', f, 2960, x, mats, rim_dir=(0.45, -0.9, 0.0), gain=1.5, tube_lit=0.1)


def ribs(wave, depth, sharp=1.0):
    """A radius multiplier: rings every `wave` metres, cresting by `depth`."""
    return lambda s: 1.0 + depth * (np.abs(np.sin(np.pi * s / wave)) ** sharp * 2 - 1)


def make_stalker(mats):
    """Standing, far too tall: a lantern of a rib cage round a little lit core, hock-jointed legs, hands down past its knees
    (one reaching for the glass), and for a head a long ringed horn, two mandibles under it, no face to speak of."""
    f = Field((-1.85, -1.75, 1.5), (1.95, 1.75, 8.45), 0.036)
    # Legs.
    for sy in (-1, 1):
        f.chain([(-0.02, sy * 0.32, 4.15), (0.48, sy * 0.55, 3.2), (-0.2, sy * 0.62, 2.42), (0.3, sy * 0.6, 1.86)], [0.27, 0.14, 0.095, 0.075], 0.12)
        for a in (-0.28, 0.0, 0.28):
            f.chain([(0.3, sy * 0.6, 1.86), (0.68, sy * 0.6 + a * 0.7, 1.66), (1.08, sy * 0.6 + a * 1.2, 1.72)], [0.07, 0.05, 0.03], 0.03, per=3)
    f.ball((-0.04, 0, 4.26), (0.32, 0.5, 0.25), 0.14)   # the pelvis
    # The spine, thin and ringed, with a hump.
    spine = [(-0.08, 0, 4.25), (-0.28, 0, 4.72), (-0.4, 0, 5.25), (-0.27, 0, 5.72), (-0.06, 0, 6.08)]
    f.chain(spine, [0.13, 0.12, 0.13, 0.13, 0.1], 0.05, rib=ribs(0.17, 0.2))
    # The rib cage: hoops off the spine to a keel, nothing inside but the core.
    for i, zr in enumerate(np.linspace(4.88, 5.6, 5)):
        w = 0.36 + 0.36 * math.sin(math.pi * (i + 1.0) / 5.8)
        for sy in (-1, 1):
            f.chain([(-0.38, sy * 0.05, zr + 0.06), (-0.22, sy * w, zr), (0.16, sy * w * 0.95, zr - 0.1), (0.42, sy * 0.07, zr - 0.15)],
                    [0.07, 0.065, 0.058, 0.05], 0.035, per=4)
    f.chain([(0.43, 0, 4.66), (0.49, 0, 5.2), (0.36, 0, 5.62)], [0.06, 0.085, 0.07], 0.04)
    # Shoulders, high and hunched.
    f.chain([(-0.3, -0.92, 5.82), (-0.3, 0, 5.72), (-0.3, 0.92, 5.82)], [0.2, 0.15, 0.2], 0.12)
    # The hanging arm, right.
    f.chain([(-0.3, -0.92, 5.82), (-0.46, -1.22, 4.5), (-0.1, -1.32, 3.32), (0.05, -1.3, 2.88)], [0.17, 0.11, 0.08, 0.07], 0.08)
    for a in (-0.24, 0.0, 0.24):
        f.chain([(0.05, -1.3, 2.88), (0.16 + a * 0.5, -1.3 + a * 0.6, 2.38), (0.34 + a, -1.24 + a * 0.8, 1.78)], [0.06, 0.05, 0.03], 0.03, per=3)
    # The reaching arm, left: toward the glass, fingers out.
    f.chain([(-0.3, 0.92, 5.82), (0.04, 1.3, 4.72), (0.86, 1.28, 5.26), (1.2, 1.15, 5.56)], [0.17, 0.11, 0.08, 0.07], 0.08)
    for a in (-0.32, 0.0, 0.32):
        f.chain([(1.2, 1.15, 5.56), (1.52, 1.15 + a * 0.55, 5.94 + a * 0.3), (1.72, 1.15 + a, 6.44 + a * 0.2)], [0.06, 0.05, 0.03], 0.03, per=3)
    # The neck, the jaw, the mandibles.
    f.chain([(-0.06, 0, 6.06), (0.14, 0, 6.22), (0.32, 0, 6.28)], [0.11, 0.15, 0.2], 0.08)
    for sy in (-1, 1):
        f.chain([(0.32, sy * 0.16, 6.2), (0.68, sy * 0.25, 5.86), (0.6, sy * 0.1, 5.42)], [0.1, 0.075, 0.03], 0.06, per=4)
    # Quills down its back.
    for i in range(6):
        zq = 4.5 + i * 0.25
        xq = -0.42 - 0.1 * math.sin(i * 0.5)
        f.chain([(xq, 0, zq), (xq - 0.26, 0, zq + 0.03), (xq - 0.54, 0, zq + 0.16)], [0.07, 0.045, 0.02], 0.04, per=3)
    # The horn's core, for the neck to grow into it.
    horn = spline([(0.34, 0, 6.22), (0.32, 0, 6.66), (0.12, 0, 7.22), (-0.24, 0, 7.72), (-0.72, 0, 8.08), (-1.3, 0, 8.3)], 4)
    hr = smooth_values([0.24, 0.38, 0.44, 0.38, 0.25, 0.05], 4)
    f.chain(horn, [r * 0.62 for r in hr], 0.1, per=1)
    f.lump(0.012, 5.0, 11)
    x = B()
    # The horn: rings all the way up, each a hard ridge.
    n0, f0 = len(x.v), len(x.f)
    crease, _ = plated(x, horn, hr, lambda r: 0.13 + 0.16 * r, lambda p: Vector((-0.7, 0, 0.7)), sides=10, flare=1.1, tuck=0.84, squash=0.04)
    lit_uvs(x, f, n0, f0, crease, rim_dir=(0.7, -0.7, 0.0), gain=1.5)
    # Tethers.
    tethers(x, [[(-0.95, 0.15, 8.0), (-1.45, 0.5, 8.2), (-1.7, 0.7, 8.5)],
                [(-0.3, 0.2, 7.5), (0.25, 0.75, 7.95), (0.55, 0.95, 8.5)],
                [(-0.45, 0.0, 5.2), (-1.25, -0.6, 5.7), (-1.85, -0.95, 6.9), (-1.7, -1.3, 8.5)],
                [(-0.38, 0.0, 4.72), (-1.35, 0.7, 4.0), (-2.15, 1.15, 4.9), (-2.35, 1.25, 6.7), (-2.15, 1.55, 8.5)],
                [(-0.12, 0.25, 4.2), (-0.95, 0.8, 3.1), (-1.55, 1.05, 2.2), (-1.85, 1.2, 1.42)]], r=0.05, per=4)
    # Its core, in the cage, and lights down the spine.
    diamond(x, (0.02, 0, 5.2), (0, 0, 1), 0.28, 0.075, 1)
    sp = spline(spine, 3)
    for i in range(6):
        diamond(x, sp[int((i + 0.5) / 6 * 12)] + Vector((-0.16, 0, 0)), (0, 0, 1), 0.07, 0.04, 1)
    return assemble('SpecimenStalker', f, 2970, x, mats, rim_dir=(0.7, -0.7, 0.0), gain=1.45, tube_lit=0.1)


def make_larva(mats):
    """A great segmented grub winding up the tank, its plates overlapping, a fin and a lit node on each one's back and a pair of
    hooks under every other; a blunt crescent of a head at the top, feelers."""
    turns = 1.15
    n = 40
    ctrl, rad = [], []
    for i in range(n + 1):
        t = i / n
        th = -2 * math.pi * turns * (1 - t) + 0.1
        R = 0.55 + 1.0 * float(kit.smoothstep(0.0, 0.22, t)) - 0.75 * float(kit.smoothstep(0.8, 1.0, t))
        z = 1.9 + 5.0 * t ** 0.95 + 0.3 * float(kit.smoothstep(0.84, 1.0, t))
        ctrl.append((R * math.cos(th), R * math.sin(th), z))
        rad.append(0.1 + 0.72 * float(kit.smoothstep(0.0, 0.42, t)) ** 0.7 - 0.2 * float(kit.smoothstep(0.66, 1.0, t)))
    pts = spline(ctrl, 2)
    rads = smooth_values(rad, 2)

    def dorsal(p):
        o = Vector((p.x, p.y, 0.0))
        o = o.normalized() if o.length > 1e-3 else Vector((1, 0, 0))
        return (o + Vector((0, 0, 0.5))).normalized()

    # A coarse field of its body, for the light in the coils' shadows.
    coarse = Field((-3.2, -3.2, 1.45), (3.2, 3.2, 8.45), 0.07)
    coarse.chain(pts, rads, 0.0, per=1)
    x = B()
    n0, f0 = len(x.v), len(x.f)
    crease, plates = plated(x, pts, rads, lambda r: 0.22 + 0.3 * r, dorsal, sides=12, flare=1.09, tuck=0.87, squash=0.05)
    # Fins and hooks.
    extra_c = []

    def flesh_tube(path, radii, sides=3):
        k0 = len(x.v)
        tube(x, path, radii, sides, 0)
        extra_c.extend([1.0] * (len(x.v) - k0))

    nodes = []
    for k, (a, p, tan, up, r) in enumerate(plates):
        side = tan.cross(up).normalized()
        if k % 3 == 0 and r > 0.3:
            for sy in (-1, 1):
                root = p - up * r * 0.7 + side * sy * r * 0.42
                flesh_tube([root, root - up * r * 0.34 + side * sy * r * 0.3, root - up * r * 0.62 + side * sy * r * 0.2 - tan * r * 0.32], [r * 0.15, r * 0.09, 0.012])
        nodes.append((p, up, tan, r))
    lit = lit_uvs(x, coarse, n0, f0, crease + extra_c, rim_dir=(0.6, -0.8, 0.0), gain=1.7)
    # The glow along its back: brightest round each node.
    co = np.array(x.v[n0:])
    no = vnormals(co, x.f[f0:] if n0 == 0 else [tuple(i - n0 for i in fc) for fc in x.f[f0:]])
    if (coarse.sample(co + no * 0.06) > coarse.sample(co - no * 0.06)).mean() < 0.5:
        no = -no
    ax = np.array([tuple(dorsal(Vector(c))) for c in co])
    lit = np.clip(lit + 0.62 * np.clip((no * ax).sum(1), 0, 1) ** 7 * np.array((crease + extra_c)).clip(0.25, 1), 0, 1)
    for k, fc in enumerate(x.f[f0:]):
        x.uv[f0 + k] = [(float(lit[i - n0]), float(co[i - n0][2] * 0.31 + co[i - n0][0] * 0.17)) for i in fc]
    # The head, as a surface of its own: a crescent shield, lobes curling forward, a blunt muzzle under it.
    hp, ht = pts[-1], (pts[-1] - pts[-5]).normalized()
    HEADING['Larva'] = math.atan2(ht.y, ht.x)
    hs = ht.cross(Vector((0, 0, 1))).normalized()
    hu = hs.cross(ht).normalized()
    R = np.array([[ht.x, hs.x, hu.x], [ht.y, hs.y, hu.y], [ht.z, hs.z, hu.z]])
    c = np.array(tuple(hp))
    f = Field(c - 2.4, c + 2.4, 0.045)
    f.ball(tuple(hp + ht * 0.08 + hu * 0.1), (0.78, 0.92, 0.62), 0.2, rot=R)
    f.ball(tuple(hp - ht * 0.4), 0.56, 0.2)
    for sy in (-1, 1):
        a = hp + hs * sy * 0.62 + ht * 0.12 + hu * 0.2
        f.chain([a, a + hs * sy * 0.5 + ht * 0.14, a + hs * sy * 0.8 + ht * 0.62, a + hs * sy * 0.55 + ht * 1.12 - hu * 0.1], [0.34, 0.25, 0.14, 0.04], 0.16, per=4)
        f.chain([hp + ht * 0.56 - hu * 0.15 + hs * sy * 0.18, hp + ht * 1.02 - hu * 0.3 + hs * sy * 0.24, hp + ht * 1.1 - hu * 0.76 + hs * sy * 0.1], [0.17, 0.11, 0.03], 0.09, per=4)
    f.ball(tuple(hp + ht * 0.62 - hu * 0.05), 0.3, 0.18)
    # Ridges across the shield.
    for q in (-0.2, 0.1, 0.4):
        f.chain([hp + ht * q + hu * 0.52 - hs * 0.55, hp + ht * (q + 0.1) + hu * 0.7, hp + ht * q + hu * 0.52 + hs * 0.55], [0.08, 0.12, 0.08], 0.07, per=4)
    eyes = []
    for sy, q in ((-1, 0.3), (1, 0.3), (-1, 0.62), (1, 0.62)):
        e = hp + ht * (0.78 - q * 0.3) + hu * 0.32 + hs * sy * q
        f.ball(tuple(e), 0.09, 0.07, cut=True)
        eyes.append(e)
    f.lump(0.012, 5.0, 13)
    # Tethers, feelers (the tubes keep their own light).
    tethers(x, [[hp - ht * 0.3 + hu * 0.4, hp - ht * 0.7 + hu * 0.8 - hs * 0.5, Vector((hp.x - 1.1, hp.y - 0.9, 8.5))],
                [pts[-22] + Vector((0, 0, 0.5)), pts[-22] * 0.75 + Vector((0.2, 0.3, 2.4)), Vector((pts[-22].x * 0.5, pts[-22].y * 0.5, 8.5))],
                [pts[6] + Vector((0, 0, -0.08)), Vector((pts[6].x * 1.6 + 0.3, pts[6].y * 1.6 - 0.3, 1.8)), Vector((pts[6].x * 2.2 + 0.7, pts[6].y * 2.2 - 0.6, 1.42))]], r=0.055, per=4)
    uv = lambda i: (0.18, i * 0.1)
    for sy, q in ((-1, 0.22), (1, 0.22), (-1, 0.5), (1, 0.5)):
        a = hp + ht * 0.86 - hu * 0.2 + hs * sy * q * 0.8
        fp = spline([a, a + ht * 0.45 + hs * sy * q - hu * 0.3, a + ht * 0.55 + hs * sy * q * 1.6 - hu * 0.95], 3)
        tube(x, fp, [0.06 - 0.05 * i / (len(fp) - 1) for i in range(len(fp))], 3, 0, uv)
    # The lit spine.
    for p, up, tan, r in nodes:
        diamond(x, p + up * (r * 1.06), tan, max(0.07, r * 0.24), max(0.035, r * 0.075), 1)
    for e in eyes:
        diamond(x, e, (0, 0, 1), 0.07, 0.06, 1)
    return assemble('SpecimenLarva', f, 2970, x, mats, rim_dir=(0.6, -0.8, 0.0), gain=2.1, tube_lit=0.1)


# --- Textures. ---------------------------------------------------------------------------------------------------------------
def phi_to_u(deg):
    """Round the collars, the road's side gets most of the atlas: deg off facing the road -> u."""
    x = abs(deg) / 180.0
    sign = 1 if deg >= 0 else -1
    a = x / 0.6 * 0.85 if x <= 0.6 else 0.85 + (x - 0.6) / 0.4 * 0.15
    return 0.5 + 0.5 * sign * a


def u_to_phi(u):
    a = np.abs(u - 0.5) * 2
    x = np.where(a <= 0.85, a / 0.85 * 0.6, 0.6 + (a - 0.85) / 0.15 * 0.4)
    return np.sign(u - 0.5) * x * 180.0


# Atlas bands, in v (up): the top collar, the base collar, the console.
BAND_TOP = (0.62, 1.0)
BAND_BASE = (0.24, 0.6)
BAND_CONSOLE = (0.0, 0.22)


def louvres(img, r0, r1, c0, c1, n):
    """A black grille: slats catching a little light."""
    img[r0:r1, c0:c1] = np.array([0.03, 0.035, 0.035])
    h = max(1, (r1 - r0) // n)
    for k in range(n):
        r = r0 + k * (r1 - r0) // n
        img[r + h // 2:r + h // 2 + max(1, h // 3), c0 + 2:c1 - 2] = np.array([0.17, 0.18, 0.17])
    # Its frame.
    for rr in (r0 - 2, r0 - 1, r1, r1 + 1):
        img[rr, c0 - 2:c1 + 2] = np.array([0.25, 0.25, 0.23])
    for cc in (c0 - 2, c0 - 1, c1, c1 + 1):
        img[r0 - 2:r1 + 2, cc] = np.array([0.25, 0.25, 0.23])


def rust_runs(img, rng, starts, length, width=2, strength=0.8):
    """Rust and dirt running down from points (row, col)."""
    h, w = img.shape[:2]
    for r0, c0 in starts:
        ln = int(rng.uniform(0.35, 1.0) * length)
        for i in range(ln):
            fade = (1 - i / ln) ** 1.3 * strength
            wd = max(1, int(width * (1 - i / ln * 0.6) + rng.uniform(-0.5, 0.8)))
            c = (c0 + int(np.sin(i * 0.06 + c0) * 1.2)) % w
            r = r0 + i
            if r >= h:
                break
            img[r, c:c + wd] = img[r, c:c + wd] * (1 - fade) + fade * np.array([0.3, 0.14, 0.05]) * rng.uniform(0.6, 1.2)


def tex_atlas():
    n = 512
    rng = np.random.default_rng(71)
    img = np.ones((n, n, 3)) * np.array([0.8, 0.81, 0.77])
    grime = kit.vnoise(n, 7, 72, 5)
    fine = kit.vnoise(n, 48, 73, 2)
    img *= (0.72 + 0.36 * grime + 0.1 * fine)[..., None]
    u = (np.arange(n) + 0.5) / n
    phi = u_to_phi(u)
    shade = 0.3 + 0.72 * np.clip(np.cos(np.radians(phi) * 0.82), 0, 1) ** 1.25
    col = lambda deg: int(phi_to_u(deg) * n)
    row = lambda v: int((1 - v) * n)

    # The top collar. Top of the band is the collar's top.
    r0, r1 = row(BAND_TOP[1]), row(BAND_TOP[0])
    H = r1 - r0
    band = img[r0:r1]
    vv = (np.arange(H) + 0.5) / H
    light = 0.82 + 0.3 * vv * (1 - vv) * 2  # (a little off the ceiling above, and it curves away)
    band *= light[:, None, None]
    band[int(H * 0.2):int(H * 0.215)] *= 0.25        # a seam
    band[int(H * 0.215):int(H * 0.23)] *= 1.15
    for deg in (-90, -54, -18, 18, 54, 90):           # panel joints
        c = col(deg)
        band[:, c:c + 2] *= 0.35
        band[:, c + 2:c + 3] *= 1.12
    louvres(band, int(H * 0.29), int(H * 0.68), col(-13), col(13), 8)  # the vents
    louvres(band, int(H * 0.33), int(H * 0.64), col(-45), col(-27), 6)
    louvres(band, int(H * 0.33), int(H * 0.64), col(27), col(45), 6)
    starts = [(0, int(c)) for c in rng.integers(0, n, 28)] + [(int(H * 0.68), int(c)) for c in np.linspace(col(-13), col(13), 7)]
    starts += [(int(H * 0.64), col(-45) + int(k)) for k in rng.integers(0, col(-27) - col(-45), 3)] + [(int(H * 0.64), col(27) + int(k)) for k in rng.integers(0, col(45) - col(27), 3)]
    rust_runs(band, rng, starts, H, 3, 0.85)
    # Its lower lip: a black gasket, then the green off the glass.
    spill = kit.smoothstep(0.74, 0.93, vv)[:, None, None] * np.array([0.08, 0.4, 0.1])
    band += spill
    band[int(H * 0.915):] = np.array([0.035, 0.05, 0.04])
    band[int(H * 0.965):] = np.array([0.06, 0.32, 0.1])
    band *= shade[None, :, None]

    # The base collar. Top of the band is the glass.
    r0, r1 = row(BAND_BASE[1]), row(BAND_BASE[0])
    H = r1 - r0
    band = img[r0:r1]
    vv = (np.arange(H) + 0.5) / H
    band *= (1.02 - 0.24 * vv)[:, None, None]
    band[int(H * 0.17):int(H * 0.185)] *= 0.25
    for deg in (-72, -36, 0, 36, 72):
        c = col(deg)
        band[int(H * 0.18):, c:c + 2] *= 0.4
    louvres(band, int(H * 0.36), int(H * 0.66), col(-24), col(-5), 7)
    louvres(band, int(H * 0.36), int(H * 0.66), col(5), col(24), 7)
    rust_runs(band, rng, [(0, int(c)) for c in rng.integers(0, n, 30)] + [(int(H * 0.66), col(-20)), (int(H * 0.66), col(-10)), (int(H * 0.66), col(14))], H, 3, 0.9)
    band += kit.smoothstep(0.26, 0.0, vv)[:, None, None] * np.array([0.1, 0.42, 0.12])
    band[:int(H * 0.05)] = np.array([0.16, 0.78, 0.22])  # the lip the glass stands in
    band[int(H * 0.05):int(H * 0.085)] = np.array([0.03, 0.05, 0.04])
    band *= (1 - 0.72 * kit.smoothstep(0.86, 1.0, vv))[:, None, None]  # down to the floor
    band *= shade[None, :, None]

    # The console: front (u 0..0.3), side (u 0.3..0.55), top and slope (u 0.55..0.8).
    r0, r1 = row(BAND_CONSOLE[1]), row(BAND_CONSOLE[0])
    H = r1 - r0
    band = img[r0:r1]
    c0, c1 = int(0.3 * n), int(0.55 * n)
    # Front: bright, the grille low down, a seam, rust.
    band[:, :c0] *= 0.98
    louvres(band, int(H * 0.5), int(H * 0.82), int(c0 * 0.18), int(c0 * 0.82), 7)
    band[int(H * 0.2):int(H * 0.215), :c0] *= 0.35
    rust_runs(band, rng, [(0, int(c)) for c in rng.integers(0, c0, 8)] + [(int(H * 0.82), int(c0 * 0.3)), (int(H * 0.82), int(c0 * 0.65))], H, 2, 0.8)
    # Side, a little dimmer: a dark bent pipe channel down it.
    band[:, c0:c1] *= 0.68
    w = c1 - c0
    for i in range(H):
        t = i / H
        cc = c0 + int(w * (0.28 + 0.34 * kit.smoothstep(0.32, 0.5, t)))
        band[i, cc:cc + 6] = np.array([0.05, 0.05, 0.05])
    rust_runs(band, rng, [(0, c0 + int(c)) for c in rng.integers(0, w, 6)], H, 2, 0.8)
    # The slope, top: lighter, the ceiling's on them.
    band[:, c1:int(0.8 * n)] *= 1.1
    rust_runs(band, rng, [(0, c1 + int(c)) for c in rng.integers(0, int(0.25 * n), 6)], H, 2, 0.5)
    band[:, :int(0.8 * n)] *= (1 - 0.5 * kit.smoothstep(0.88, 1.0, (np.arange(H) + 0.5) / H))[:, None, None]
    return np.clip(img, 0, 1)


def tex_liner():
    """256 x 256, twice round the tank, up the glass: bright low, dim above, a band under the top; tendrils' shadows, light through."""
    w, h = 256, 256
    rng = np.random.default_rng(81)
    v = 1 - (np.arange(h) + 0.5) / h   # (up the wall)
    # Brightness up the wall.
    b = 0.36 + 0.48 * kit.smoothstep(0.5, 0.0, v) ** 1.4 + 0.2 * kit.smoothstep(0.82, 0.96, v) * (1 - kit.smoothstep(0.96, 1.0, v))
    b = b[:, None] * (0.86 + 0.28 * kit.vnoise(256, 5, 82, 3))
    # Shafts of lighter fluid.
    sh = np.tile(kit.vnoise(256, 24, 83, 2)[0][None, :], (h, 1))
    b *= 0.78 + 0.5 * kit.smoothstep(0.45, 0.8, sh)
    # Tendrils, hanging from the top, dark.
    dark = np.zeros((h, w))
    for _ in range(30):
        x, y = rng.uniform(0, w), 0.0
        a = rng.normal(0, 0.1)
        length = rng.uniform(70, 240)
        wd = rng.integers(1, 4)
        while y < length:
            a += rng.normal(0, 0.09)
            a *= 0.96
            nx, ny = x + math.sin(a) * 3, y + math.cos(a) * 3
            kit.draw_line(dark, (y, x), (ny, nx), 1.0, int(wd))
            x, y = nx, ny
    soft = dark.copy()
    for _ in range(2):
        soft = (soft + np.roll(soft, 1, 0) + np.roll(soft, -1, 0) + np.roll(soft, 1, 1) + np.roll(soft, -1, 1)) / 5
    b *= 1 - 0.62 * soft
    rgb = b[..., None] * np.array([0.42, 1.0, 0.42])
    hot = np.clip(b - 0.75, 0, 1)
    rgb += hot[..., None] * np.array([0.9, 0.5, 0.7])
    return np.clip(rgb, 0, 1)


def tex_fluid():
    """256 x 256 RGBA, tiling, five times round the tank: a thin green film, with bubbles and flecks in it, opaque-ish and lit."""
    n = 256
    rng = np.random.default_rng(91)
    yy, xx = np.mgrid[0:n, 0:n]
    film = 0.75 + 0.5 * kit.vnoise(n, 5, 92, 3)
    rgb = film[..., None] * np.array([0.022, 0.085, 0.032])
    alpha = np.full((n, n), 0.3) + 0.08 * kit.vnoise(n, 7, 93, 2)
    def dot(cx, cy, r, ring):
        dx = (xx - cx + n / 2) % n - n / 2
        dy = (yy - cy + n / 2) % n - n / 2
        d = np.sqrt(dx * dx + dy * dy)
        return (1 - kit.smoothstep(r - 1.0, r + 0.5, d)) * (ring + (1 - ring) * kit.smoothstep(r * 0.45, r, d))
    # Bubbles, in rising strings.
    for _ in range(9):
        cx, cy = rng.uniform(0, n), rng.uniform(0, n)
        for i in range(rng.integers(3, 8)):
            r = rng.uniform(0.9, 2.7)
            m = dot(cx + rng.normal(0, 2.2), cy - i * rng.uniform(8, 22), r, 0.18)
            rgb = rgb * (1 - m[..., None]) + m[..., None] * np.array([0.3, 0.33, 0.26])
            alpha = np.maximum(alpha, m * 0.9)
    # Flecks.
    for _ in range(320):
        cx, cy = rng.integers(0, n, 2)
        v = rng.uniform(0.1, 0.34)
        rgb[cy, cx] = np.array([0.45, 1.0, 0.5]) * v
        alpha[cy, cx] = 0.85
    return np.clip(np.dstack([rgb, alpha]), 0, 1)


def tex_ramp():
    """128 x 128: U is how lit, V tiles a mottle and veins that the light brings up."""
    n = 128
    u = (np.arange(n) + 0.5) / n
    stops = [(0.0, (0.006, 0.022, 0.012)), (0.25, (0.022, 0.085, 0.04)), (0.5, (0.06, 0.25, 0.1)), (0.75, (0.22, 0.66, 0.25)), (1.0, (0.76, 1.0, 0.64))]
    ramp = np.stack([np.interp(u, [s[0] for s in stops], [s[1][c] for s in stops]) for c in range(3)], 1)
    img = np.tile(ramp[None], (n, 1, 1))
    m = kit.vnoise(n, 6, 95, 4)
    veins = 1 - np.abs(kit.vnoise(n, 7, 96, 3) - 0.5) * 2
    veins = kit.smoothstep(0.86, 0.98, veins)
    img *= (0.84 + 0.32 * m)[..., None]
    img = img * (1 - veins[..., None] * 0.22)
    return np.clip(img, 0, 1)


# --- The tank and its console. ----------------------------------------------------------------------------------------------
def band_uv(deg, z, z0, z1, band):
    """An atlas UV on a collar: deg off facing the road, z through the band (z1 at its top)."""
    t = (z - z0) / (z1 - z0)
    return (phi_to_u(deg), band[0] + (band[1] - band[0]) * t)


def ring_band(b, prof, band, z0, z1, mat, seg=SEG):
    """A lathed collar: profile (r, z) bottom up; the seam at the back, away from the road."""
    for (r0, z_0), (r1, z_1) in zip(prof, prof[1:]):
        for i in range(seg):
            # (deg runs from +180 at the back, down through the road's side, to -180: seen from outside, u runs left to right.)
            a0, a1 = 360.0 * i / seg, 360.0 * (i + 1) / seg
            d0, d1 = a0 - 180.0, a1 - 180.0
            # The point at deg off the road's side (-y): x = sin deg, y = -cos deg.
            def P(r, d, z):
                t = math.radians(d)
                return (r * math.sin(t), -r * math.cos(t), z)
            pts = [P(r0, d0, z_0), P(r0, d1, z_0), P(r1, d1, z_1), P(r1, d0, z_1)]
            uvs = [band_uv(d0, z_0, z0, z1, band), band_uv(d1, z_0, z0, z1, band), band_uv(d1, z_1, z0, z1, band), band_uv(d0, z_1, z0, z1, band)]
            # (Facing out: seen from -y, +x is to the right and +z up, so this order is anticlockwise.)
            b.poly(pts, mat, uvs, flat=False)


def strip(b, deg0, deg1, r, z0, z1, mat, n=4):
    """A lit strip on a collar's curve, facing out."""
    for i in range(n):
        a, c = deg0 + (deg1 - deg0) * i / n, deg0 + (deg1 - deg0) * (i + 1) / n
        ta, tc = math.radians(a), math.radians(c)
        b.poly([(r * math.sin(ta), -r * math.cos(ta), z0), (r * math.sin(tc), -r * math.cos(tc), z0),
                (r * math.sin(tc), -r * math.cos(tc), z1), (r * math.sin(ta), -r * math.cos(ta), z1)], mat, [(0, 0), (1, 0), (1, 1), (0, 1)], True)


def make_tank():
    """Slots: 0 the white atlas, 1 liner, 2 fluid, 3 cable, 4 strip light, 5 glass highlight."""
    WHITE, LINER, FLUID, CABLE, LIGHT, HIGH = range(6)
    b = B()
    # The collars. Their profile's top, the band's top.
    ring_band(b, [(R_BASE, 0.0), (R_BASE, 0.14), (R_COLLAR, 0.16), (R_COLLAR, 1.14), (3.42, 1.36), (R_FLUID + 0.02, 1.4)], BAND_BASE, 0.0, 1.4, WHITE)
    ring_band(b, [(R_FLUID + 0.02, TANK_Z1), (3.5, 8.56), (R_COLLAR, 8.72), (R_COLLAR, 9.46), (3.28, COLLAR_TOP)], BAND_TOP, TANK_Z1, COLLAR_TOP, WHITE)
    # The liner: faces in, culled from outside; its wall, its floor and its ceiling.
    for i in range(SEG):
        a0, a1 = 2 * math.pi * i / SEG, 2 * math.pi * (i + 1) / SEG
        c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
        u0, u1 = 2.0 * i / SEG, 2.0 * (i + 1) / SEG
        b.poly([(R_LINER * c1, R_LINER * s1, TANK_Z0), (R_LINER * c0, R_LINER * s0, TANK_Z0), (R_LINER * c0, R_LINER * s0, TANK_Z1), (R_LINER * c1, R_LINER * s1, TANK_Z1)],
               LINER, [(u1, 0.0), (u0, 0.0), (u0, 1.0), (u1, 1.0)], flat=False)
    floor_uv = [(0.5, 0.16)] * SEG
    b.poly([(R_LINER * math.cos(2 * math.pi * i / SEG), R_LINER * math.sin(2 * math.pi * i / SEG), TANK_Z0 + 0.01) for i in range(SEG)], LINER, floor_uv, True)
    top_uv = [(0.5, 0.74)] * SEG
    b.poly([(R_LINER * math.cos(-2 * math.pi * i / SEG), R_LINER * math.sin(-2 * math.pi * i / SEG), TANK_Z1 - 0.01) for i in range(SEG)], LINER, top_uv, True)
    # Glowing foam round the foot of the glass, a lumpy skyline against the wall.
    rng_f = np.random.default_rng(67)
    hs = rng_f.uniform(0.1, 0.5, SEG)
    for i in range(SEG):
        j = (i + 1) % SEG
        a0, a1 = 2 * math.pi * i / SEG, 2 * math.pi * (i + 1) / SEG
        rr = R_LINER - 0.05
        ri = rr - 0.5
        pts = [(ri * math.cos(a1), ri * math.sin(a1), TANK_Z0 + 0.02), (ri * math.cos(a0), ri * math.sin(a0), TANK_Z0 + 0.02),
               (rr * math.cos(a0), rr * math.sin(a0), TANK_Z0 + hs[i]), (rr * math.cos(a1), rr * math.sin(a1), TANK_Z0 + hs[j])]
        b.poly(pts, LINER, [(0.5, 0.16), (0.5, 0.16), (0.5, 0.02), (0.5, 0.02)], True)
    # A ring of light on the ceiling.
    for i in range(SEG):
        a0, a1 = -2 * math.pi * i / SEG, -2 * math.pi * (i + 1) / SEG
        ra, rb = 2.46, 2.56
        b.poly([(rb * math.cos(a0), rb * math.sin(a0), TANK_Z1 - 0.02), (rb * math.cos(a1), rb * math.sin(a1), TANK_Z1 - 0.02),
                (ra * math.cos(a1), ra * math.sin(a1), TANK_Z1 - 0.02), (ra * math.cos(a0), ra * math.sin(a0), TANK_Z1 - 0.02)], LINER, [(0.5, 0.07)] * 4, True)
    # The fluid: one shell, facing out, culled from inside.
    FS = SEG
    for i in range(FS):
        a0, a1 = 2 * math.pi * i / FS, 2 * math.pi * (i + 1) / FS
        c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
        u0, u1 = 5.0 * i / FS, 5.0 * (i + 1) / FS
        vh = (TANK_Z1 - TANK_Z0) / (2 * math.pi * R_FLUID / 5.0)
        b.poly([(R_FLUID * c0, R_FLUID * s0, TANK_Z0), (R_FLUID * c1, R_FLUID * s1, TANK_Z0), (R_FLUID * c1, R_FLUID * s1, TANK_Z1), (R_FLUID * c0, R_FLUID * s0, TANK_Z1)],
               FLUID, [(u0, 0.0), (u1, 0.0), (u1, vh), (u0, vh)], flat=False)
    # Highlights on the glass: long thin lights down it.
    for d0, d1 in ((-52.0, -50.6), (40.0, 40.8)):
        strip(b, d0, d1, R_FLUID + 0.012, TANK_Z0 + 0.3, TANK_Z1 - 0.12, HIGH, 1)
    # The base's strip light.
    strip(b, -24.0, 24.0, R_BASE + 0.015, 0.16, 0.36, LIGHT, 3)
    # Cables in the fluid: from the ceiling, trailing down near the wall, thinning out.
    rng = np.random.default_rng(61)
    for deg, r0, bottom in ((-152, 2.75, 1.7), (-112, 2.85, 3.9), (168, 2.9, 2.4), (124, 2.85, 1.6), (70, 2.95, 3.3), (-68, 2.95, 4.6)):
        t = math.radians(deg)
        ctrl = []
        for k in range(5):
            a = t + rng.normal(0, 0.05) * (k > 0)
            rr = r0 - 0.14 * math.sin(k * 1.3) * (k > 0)
            ctrl.append(Vector((rr * math.sin(a), -rr * math.cos(a), TANK_Z1 + (bottom - TANK_Z1) * k / 4 - 0.01)))
        pts = spline(ctrl, 2)
        tube(b, pts, [0.04 - 0.032 * (i / (len(pts) - 1)) ** 1.5 for i in range(len(pts))], 4, CABLE, None, False)
    # Above: short risers out of the collar's top to the ceiling (the lab's bundles come down round them).
    for dg, rr in ((-34, 2.7), (-14, 2.9), (10, 2.75), (31, 2.85)):
        t = math.radians(dg)
        p0 = Vector((rr * math.sin(t), -rr * math.cos(t), COLLAR_TOP - 0.1))
        p1 = p0 + Vector((math.sin(t) * 0.25, -math.cos(t) * 0.25, 0.28))
        p2 = p0 + Vector((math.sin(t) * 0.25, 0.4, 0.62))
        p3 = p0 + Vector((0, 1.0, 0.9))
        tube(b, spline([p0, p1, p2, p3], 1), 0.09, 4, CABLE, None, False, closed_tip=False)
    return b


def make_console():
    """Facing -y (the road, then turned to the oncoming rider): a hexagonal profile swept across, its screen on the slope."""
    WHITE, SCREEN, DARK = 0, 1, 2
    b = B()
    w = 0.85
    prof = [(-0.8, 0.0), (-0.8, 1.14), (-0.74, 1.2), (0.02, 1.96), (0.8, 2.06), (0.8, 0.0)]   # (y, z), base up the front, over, down the back
    b0 = BAND_CONSOLE
    # The sides.
    ch = b0[1] - b0[0]
    def side_uv(y, z, sx):
        return (0.3 + 0.25 * ((y + 0.8) / 1.6 if sx < 0 else 1 - (y + 0.8) / 1.6), b0[0] + ch * min(z / 2.06, 1.0))
    for sx in (-1, 1):
        pts = [(sx * w, y, z) for y, z in prof]
        uvs = [side_uv(y, z, sx) for y, z in prof]
        if sx < 0:
            pts, uvs = pts[::-1], uvs[::-1]
        b.poly(pts, WHITE, uvs, True)
    # Round the profile: front, chamfer, slope, top, back.
    faces = [(prof[0], prof[1], (0.0, 0.3), (0.0, 1.0)), (prof[1], prof[2], (0.56, 0.8), (0.0, 0.1)), (prof[2], prof[3], (0.56, 0.8), (0.1, 0.62)),
             (prof[3], prof[4], (0.56, 0.8), (0.62, 1.0)), (prof[4], prof[5], (0.3, 0.55), (0.0, 1.0))]
    for (a, c, (u0, u1), (v0, v1)) in faces:
        y0, z0 = a
        y1, z1 = c
        b.poly([(-w, y0, z0), (w, y0, z0), (w, y1, z1), (-w, y1, z1)], WHITE,
               [(u0, b0[0] + ch * v0), (u1, b0[0] + ch * v0), (u1, b0[0] + ch * v1), (u0, b0[0] + ch * v1)], True)
    # The screen on the slope, in a dark bezel, standing just proud.
    def on_slope(t, x, up):
        y = prof[2][0] + (prof[3][0] - prof[2][0]) * t
        z = prof[2][1] + (prof[3][1] - prof[2][1]) * t
        # Its normal, up and toward the road.
        ln = math.hypot(prof[3][0] - prof[2][0], prof[3][1] - prof[2][1])
        ny, nz = -(prof[3][1] - prof[2][1]) / ln, (prof[3][0] - prof[2][0]) / ln
        return (x, y + ny * up, z + nz * up)
    b.poly([on_slope(0.06, -0.74, 0.02), on_slope(0.06, 0.74, 0.02), on_slope(0.96, 0.74, 0.02), on_slope(0.96, -0.74, 0.02)], DARK, None, True)
    b.poly([on_slope(0.12, -0.66, 0.035), on_slope(0.12, 0.66, 0.035), on_slope(0.9, 0.66, 0.035), on_slope(0.9, -0.66, 0.035)], SCREEN,
           [(0, 0), (1, 0), (1, 1), (0, 1)], True)
    return b


def build(_kit):
    global kit
    kit = _kit
    kit.register_texture('tankatlas', tex_atlas)
    kit.register_texture('tankliner', tex_liner)
    kit.register_texture('tankfluid', tex_fluid, jpeg=False)
    kit.register_texture('specramp', tex_ramp)
    white = kit.material(f'{kit.PREFIX}TankWhite', (1, 1, 1), 0.36, 0.05, tex='tankatlas', emission=(1, 1, 1), strength=1.0, emit_tex=True)
    liner = kit.material(f'{kit.PREFIX}Liner', (0.05, 0.2, 0.08), 0.6, vcol=False, tex='tankliner', emission=(1, 1, 1), strength=LINER_GLOW, emit_tex=True)
    liner.use_backface_culling = True
    # (Designed at the site's 3 x for names ending Fluid, so this preview shows what the site will.)
    fluid = kit.material(f'{kit.PREFIX}TankFluid', (0.2, 0.9, 0.3), 0.15, vcol=False, tex='tankfluid', emission=(1, 1, 1), strength=3.0, emit_tex=True, alpha_tex=True)
    fluid.use_backface_culling = True
    high = kit.material(f'{kit.PREFIX}StreakTankGlass', (0.8, 1.0, 0.85), 0.1, vcol=False, emission=(0.8, 1.0, 0.85), strength=1.2, alpha=0.16)
    high.use_backface_culling = True
    flesh = kit.material(f'{kit.PREFIX}Specimen', (1, 1, 1), 0.5, tex='specramp', emission=(1, 1, 1), strength=1.0, emit_tex=True)

    tb = make_tank()
    tank_me = tb.mesh(f'{kit.PREFIX}Tank', [white, liner, fluid, kit.MAT['cable'], kit.MAT['light'], high])
    kit.set_vcol(tank_me, np.ones(len(tank_me.vertices)))
    cb = make_console()
    con_me = cb.mesh(f'{kit.PREFIX}TankConsole', [white, kit.MAT['screen'], kit.MAT['dark']])
    kit.set_vcol(con_me, np.ones(len(con_me.vertices)))

    mats = [flesh, kit.MAT['led']]
    out = {'tank': kit.piece('Tank', tank_me), 'console': kit.piece('TankConsole', con_me)}
    for name, fn in (('Embryo', make_embryo), ('Stalker', make_stalker), ('Larva', make_larva)):
        me = fn(mats)
        out[name] = kit.piece(f'Specimen{name}', me)
    for k, p in out.items():
        print(f'tanks: {k}: {kit.tris(p.data)} tris')
    print(f'tanks: tank + console: {kit.tris(tank_me) + kit.tris(con_me)} tris')
    return out



def tanks():
    """(s, side +1 left / -1 right, which specimen) for every tank. Across the road and along the row, never the same one."""
    lab = kit.LAB
    out = []
    i = 0
    s = lab['tank_from']
    while s + R_BASE < lab['door_s'] - 1.0:
        out.append((s, 1, ORDER[i % 3]))
        out.append((s, -1, ORDER[(i + 1) % 3]))
        s += lab['tank_every']
        i += 1
    return out


def place(_kit, pieces):
    global kit
    kit = _kit
    rng = np.random.default_rng(55)
    y = kit.LAB['tank_y']
    for s, side, name in tanks():
        h = kit.heading(s)
        c = kit.along(s, side * y)
        # (The tank's -y to the road: as made on the left, turned round on the right.)
        kit.put(pieces['tank'], c, h if side > 0 else h + math.pi, grp='Tanks')
        # Facing the oncoming rider, turned toward the road's middle; each a little different.
        off = math.radians(FACING[name] + rng.uniform(-14, 14))
        yaw = h + math.pi + side * off - HEADING[name]   # (its face, down the road back at the rider, then toward the middle)
        kit.put(pieces[name], c, yaw, scale=float(rng.uniform(0.95, 1.03)), grp='Tanks')
        # Its console, toward the road and turned to the rider.
        cc = kit.along(s + CONSOLE_BACK, side * CONSOLE_D)
        cy = h - CONSOLE_YAW if side > 0 else h + math.pi + CONSOLE_YAW
        kit.put(pieces['console'], cc, cy, grp='Tanks')
        reach = 0.85 * abs(math.sin(CONSOLE_YAW)) + 0.8 * abs(math.cos(CONSOLE_YAW))
        assert CONSOLE_D - reach > 7.2, CONSOLE_D - reach


# The tanks of each, on the left of the road: kit.LAB tank_from + tank_every i, in ORDER.
def _close(i, eye_back=7.0, eye_d=1.5, z=1.5, fov=58):
    s = 170.0 + 18.0 * i
    return ((s - eye_back, eye_d, z), (s + 0.3, 12.2, 4.75), fov)


SHOTS = {
    'row': ((152.0, 0.0, 1.15), (250.0, 0.0, 7.2), 58),
    'embryo': _close(0),
    'stalker': _close(1),
    'larva': _close(2),
    'far': ((165.0, 2.0, 1.2), (230.0, 12.0, 5.0), 34),
    'look-embryo': ((170.0, 5.0, 4.9), (170.0, 12.2, 4.9), 62),
    'look-stalker': ((188.0, 5.0, 4.9), (188.0, 12.2, 4.9), 62),
    'look-larva': ((206.0, 5.0, 4.9), (206.0, 12.2, 4.9), 62),
    'side-embryo': ((170.0, 2.0, 2.0), (170.0, 12.2, 4.8), 66),
    'side-stalker': ((188.0, 2.0, 2.0), (188.0, 12.2, 4.8), 66),
    'side-larva': ((206.0, 2.0, 2.0), (206.0, 12.2, 4.8), 66),
}

WITH = ['lab']
