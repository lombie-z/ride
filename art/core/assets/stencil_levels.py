"""The sprayed level codes, B4 to B12, each with its bar beneath (the table's "slash"; the image's B4 and B5): one object per level, named
stencil_B4 and so on, a 3 x 3 m plate of worn paint with soft edges and overspray, all sharing one alpha texture (one 3 x 3 atlas).
Each is at the origin, its back centre on the wall's plane (the plate stands off it 4 cm so it can't fight the wall), width along X,
height along Z, facing +Y. Laid out on a context wall for the stills only: the wall isn't exported, and the objects go back to the origin."""
import os
import sys

import bmesh
import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'stencil_levels'
LEVELS = ['B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'B10', 'B11', 'B12']
SIZE = 3.0
OFF_WALL = 0.04
EACH = 40
kit = A.begin()


# --- The stencil font: blocky, chamfered, with bridges (the gaps a cut stencil leaves), on a 5 x 7 box. y up. ---
def _mirror(p):
    return [(5 - x, y) for x, y in p]


def _turn(p):
    return [(5 - x, 7 - y) for x, y in p]


_SIX = [
    [(0, 6.1), (0.9, 7), (4.6, 7), (4.6, 5.6), (1.5, 5.6), (1.5, 0), (0.9, 0), (0, 0.9)],
    [(1.72, 4.1), (3.95, 4.1), (5, 3.1), (5, 0.95), (4, 0), (1.72, 0), (1.72, 1.3), (3.35, 1.3), (3.55, 1.5), (3.55, 2.6), (3.35, 2.8), (1.72, 2.8)],
]
_EIGHT_L = [(2.39, 7), (0.9, 7), (0.1, 6.15), (0.1, 4.5), (0.75, 3.75), (0, 3), (0, 0.9), (0.9, 0), (2.39, 0), (2.39, 1.3), (1.65, 1.3), (1.45, 1.5), (1.45, 2.75),
            (1.65, 2.95), (2.39, 2.95), (2.39, 4.1), (1.75, 4.1), (1.55, 4.3), (1.55, 5.5), (1.75, 5.7), (2.39, 5.7)]
_ZERO_L = [(2.39, 7), (0.9, 7), (0, 6.1), (0, 0.9), (0.9, 0), (2.39, 0), (2.39, 1.35), (1.65, 1.35), (1.45, 1.55), (1.45, 5.45), (1.65, 5.65), (2.39, 5.65)]
GLYPHS = {
    # B reads as a B, not 13: closed, its counters' only bridges thin slits through the top and bottom bars.
    'B': [[(0, 0), (0, 7), (2.05, 7), (2.05, 5.75), (1.5, 5.75), (1.5, 4.05), (3.25, 4.05), (3.45, 4.25), (3.45, 5.55), (3.25, 5.75), (2.27, 5.75), (2.27, 7),
           (3.95, 7), (4.8, 6.1), (4.8, 4.5), (4.1, 3.7), (5, 2.95), (5, 0.95), (4.05, 0), (2.27, 0), (2.27, 1.25), (3.35, 1.25), (3.55, 1.45), (3.55, 2.75), (3.35, 2.95),
           (1.5, 2.95), (1.5, 1.25), (2.05, 1.25), (2.05, 0)]],
    '0': [_ZERO_L, _mirror(_ZERO_L)],
    '1': [[(2.0, 0), (3.5, 0), (3.5, 7), (2.0, 7)], [(0.5, 4.7), (1.78, 5.1), (1.78, 7), (1.2, 7), (0.5, 6.2)]],
    '2': [[(0.1, 4.8), (0.1, 6.1), (1, 7), (4, 7), (4.9, 6.1), (4.9, 4.2), (2.65, 1.6), (0.6, 1.6), (3.4, 4.7), (3.4, 5.45), (3.2, 5.65), (1.8, 5.65), (1.6, 5.45), (1.6, 4.8)],
          [(0.1, 0), (4.9, 0), (4.9, 1.35), (0.1, 1.35)]],
    '4': [[(2.53, 7), (2.53, 5.0), (1.5, 3.15), (2.53, 3.15), (2.53, 1.75), (0, 1.75), (0, 3.25), (2.0, 7)],
          [(2.75, 0), (4.25, 0), (4.25, 1.75), (5, 1.75), (5, 3.15), (4.25, 3.15), (4.25, 7), (2.75, 7)]],
    '5': [[(0.3, 7), (4.6, 7), (4.6, 5.65), (1.7, 5.65), (1.7, 4.35), (0.3, 4.35)],
          [(0.3, 4.1), (3.95, 4.1), (5, 3.1), (5, 0.95), (4, 0), (0.1, 0), (0.1, 1.3), (3.35, 1.3), (3.55, 1.5), (3.55, 2.55), (3.35, 2.75), (0.3, 2.75)]],
    '6': _SIX,
    '7': [[(0.1, 7), (4.9, 7), (4.9, 5.75), (0.1, 5.75)], [(4.9, 5.5), (2.65, 0), (1.1, 0), (3.25, 5.5)]],
    '8': [_EIGHT_L, _mirror(_EIGHT_L)],
    '9': [_turn(p) for p in _SIX],
}
GAP = 0.55
CELL = 3     # the atlas: 3 x 3 plates, row 0 at the top
N = 512
SS = 2       # glyphs drawn at twice the size, then box-filtered


def fill(mask, poly, x0, y0, sx, sy):
    """Even-odd fill of a polygon (glyph units) into a mask: x0, y0 the glyph's origin in pixels; sx, sy pixels per unit (rows go down)."""
    pts = [(x0 + x * sx, y0 - y * sy) for x, y in poly]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    c0, c1 = int(min(xs)), int(max(xs)) + 2
    r0, r1 = int(min(ys)), int(max(ys)) + 2
    cc, rr = np.meshgrid(np.arange(c0, c1) + 0.5, np.arange(r0, r1) + 0.5)
    inside = np.zeros(cc.shape, bool)
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        cond = (ay > rr) != (by > rr)
        xint = (bx - ax) * (rr - ay) / (by - ay + 1e-9) + ax
        inside ^= cond & (cc < xint)
    mask[r0:r1, c0:c1] = np.maximum(mask[r0:r1, c0:c1], inside.astype(np.float32))


def blur(a, passes):
    out = a
    for _ in range(passes):
        out = (out * 2 + np.roll(out, 1, 0) + np.roll(out, -1, 0) + np.roll(out, 1, 1) + np.roll(out, -1, 1)) / 6
    return out


def tex_stencil():
    """512 x 512 RGBA: the nine plates' paint. Worn pale paint, soft sprayed edges, flecks of overspray, chips and scrapes, a card's faint ghost,
    old yellow left in the bars. Rows run top down."""
    H = N * SS
    px = H / CELL / SIZE                          # hi-res pixels per metre of plate
    glyph = np.zeros((H, H), np.float32)
    bar = np.zeros((H, H), np.float32)
    card = np.zeros((H, H), np.float32)
    TEXT_W, TEXT_H, BAR_W, BAR_H = 2.72, 2.02, 2.76, 0.3
    TOP = 0.16
    for idx, level in enumerate(LEVELS):
        cx, cy = (idx % CELL) * H / CELL, (idx // CELL) * H / CELL   # the cell's top-left, hi-res px
        ws = [max(x for p in GLYPHS[ch] for x, _ in p) - (min(x for p in GLYPHS[ch] for x, _ in p)) for ch in level]
        total = sum(ws) + GAP * (len(level) - 1)
        sx = min(TEXT_W / total, TEXT_H / 7 * 0.95) * px
        sy = TEXT_H / 7 * px
        pen = cx + (SIZE * px - total * sx) / 2
        base = cy + (TOP + TEXT_H) * px
        for ch, w in zip(level, ws):
            lo = min(x for p in GLYPHS[ch] for x, _ in p)
            for poly in GLYPHS[ch]:
                fill(glyph, poly, pen - lo * sx, base, sx, sy)
            pen += (w + GAP) * sx
        bx0, by0 = cx + (SIZE - BAR_W) / 2 * px, base + 0.24 * px
        bar[int(by0):int(by0 + BAR_H * px), int(bx0):int(bx0 + BAR_W * px)] = 1.0
        m = 0.06 * px
        card[int(cy + m):int(cy + SIZE * px - m), int(cx + m):int(cx + SIZE * px - m)] = 1.0

    def down(a):
        return a.reshape(N, SS, N, SS).mean(axis=(1, 3))

    glyph, bar, card = down(glyph), down(bar), down(card)
    paint = np.clip(glyph + bar, 0, 1)
    rng = np.random.default_rng(404)

    # The sprayed edge: a little soft; the fog of overspray close round it; flecks further out.
    soft = blur(paint, 2)
    fog = blur(paint, 16)
    specks = (rng.random((N, N)) < np.clip(fog * 0.55, 0, 0.5)).astype(np.float32)
    specks = blur(specks, 1)

    # The wear: big blotches where the wall shows through, chips, long diagonal scrapes, rain lines running down.
    blotch = kit.vnoise(N, 14, 71, 4)
    fine = kit.vnoise(N, 48, 72, 2)
    wear = np.clip(1.0 - 1.1 * kit.smoothstep(0.69, 0.79, blotch) - 0.9 * kit.smoothstep(0.7, 0.78, fine), 0, 1)
    wear *= 0.78 + 0.22 * kit.vnoise(N, 28, 76, 3)   # Thinner and thicker, as a can leaves it.
    scrapes = np.zeros((N, N), np.float32)
    for _ in range(46):
        r, c = rng.uniform(0, N), rng.uniform(0, N)
        ln = rng.uniform(10, 42)
        a = rng.choice([-1, 1]) * rng.uniform(0.5, 1.1)
        kit.draw_line(scrapes, (r, c), (r + np.sin(a) * ln, c + np.cos(a) * ln), 1.0, 1)
    runs = np.zeros((N, N), np.float32)
    for _ in range(110):
        c = int(rng.uniform(0, N))
        r0 = int(rng.uniform(0, N))
        runs[r0:r0 + int(rng.uniform(14, 62)), c] = rng.uniform(0.3, 0.9)
    wear *= (1 - 0.85 * scrapes) * (1 - 0.7 * runs)

    # A few drips from the bottoms of the strokes, where it was laid on thick.
    drips = np.zeros((N, N), np.float32)
    edge = np.clip(paint - np.roll(paint, -1, 0), 0, 1)     # the last row of a stroke
    rows, cols = np.nonzero(edge > 0.5)
    pick = rng.choice(len(rows), size=34, replace=False)
    for r, c in zip(rows[pick], cols[pick]):
        drips[r:r + int(rng.uniform(4, 15)), c] = rng.uniform(0.35, 0.7)

    alpha = np.clip(soft, 0, 1) * wear * 0.96
    alpha = np.maximum(alpha, fog * 0.2 * (0.45 + 0.55 * kit.vnoise(N, 24, 73, 2)))
    alpha = np.maximum(alpha, specks * 0.42 * (1 - soft))
    alpha = np.maximum(alpha, drips * 0.8)
    alpha = np.maximum(alpha, blur(card, 3) * 0.05 * (0.4 + 0.6 * blotch))

    # The colour: a pale, warm paint, dirtied, old yellow in the bars (toward their left ends, as on the image's B4).
    dirt = 0.82 + 0.3 * kit.vnoise(N, 16, 74, 3)
    rgb = np.array([0.8, 0.77, 0.7], np.float32) * dirt[..., None]
    yellow = kit.smoothstep(0.5, 0.62, kit.vnoise(N, 14, 75, 3))
    yellow = yellow * (blur(bar, 1) > 0.2)
    rgb = rgb * (1 - yellow[..., None]) + np.array([0.68, 0.53, 0.11], np.float32) * yellow[..., None]
    return np.clip(np.dstack([rgb, alpha]), 0, 1)


kit.register_texture('stencil', tex_stencil, jpeg=False)
m = _mats.mats(kit)      # The 'stencil' line in _mats.py is only made once the texture's registered, above.

# --- The plates: one 4 x 4 grid each (32 tris), so the baked light has somewhere to show. ---
INSET = 1.5 / N
GRID = 4
LIGHTS = {  # Dim, as the shaft's: red strips low and to one side, the green from far down below.
    'red': ((0.8, 2.2, -2.6), (1.0, 0.1, 0.06), 3.0, 0.55),
    'green': ((-1.4, 2.6, -1.8), (0.25, 1.0, 0.35), 2.4, 0.22),
}
objs = []
for idx, level in enumerate(LEVELS):
    c, r = idx % CELL, idx // CELL
    u0, u1 = c / CELL + INSET, (c + 1) / CELL - INSET
    v0, v1 = 1 - (r + 1) / CELL + INSET, 1 - r / CELL - INSET
    name = f'stencil_{level}'
    bm = bmesh.new()
    vs = [[bm.verts.new((-SIZE / 2 + SIZE * i / GRID, OFF_WALL, -SIZE / 2 + SIZE * j / GRID)) for j in range(GRID + 1)] for i in range(GRID + 1)]
    for i in range(GRID):
        for j in range(GRID):
            f = bm.faces.new((vs[i][j], vs[i][j + 1], vs[i + 1][j + 1], vs[i + 1][j]))   # Its normal's +Y.
            f.material_index = 0
    me = kit.mesh_from(name, bm, [m['stencil']], recalc=False)
    uv = me.uv_layers.new(name='UVMap')
    for loop in me.loops:
        co = me.vertices[loop.vertex_index].co
        # Viewed from +Y, +X is on the viewer's left: u runs against x, or the code would read backwards.
        uv.data[loop.index].uv = (u0 + (SIZE / 2 - co.x) / SIZE * (u1 - u0), v0 + (co.z + SIZE / 2) / SIZE * (v1 - v0))
    kit.bake_light(me, list(LIGHTS.values()), ambient=(0.8, 0.8, 0.76))
    if kit.tris(me) > EACH:
        raise RuntimeError(f'{name}: {kit.tris(me)} tris over {EACH}')
    objs.append(A.obj(me, name=name))


def context_wall():
    b = bmesh.new()
    for i in range(30):
        for j in range(30):
            x0, x1 = -30 + 2 * i, -28 + 2 * i
            z0, z1 = -30 + 2 * j, -28 + 2 * j
            f = b.faces.new([b.verts.new(p) for p in ((x0, 0, z0), (x0, 0, z1), (x1, 0, z1), (x1, 0, z0))])
            f.material_index = 0
    w = kit.mesh_from('ContextWall', b, [m['stained_concrete']], recalc=False)
    kit.box_uvs(w, 0.25)
    kit.bake_light(w, [((3, 3, -1), (1.0, 0.1, 0.06), 6.0, 0.45)], ambient=(0.5, 0.52, 0.46))
    return A.obj(w), w


tris = A._check(kit, NAME, EACH * len(LEVELS))
wo, wm = context_wall()
# All nine on the wall, viewed from a little off square, and the big B4 as a rider passes it.
for k, o in enumerate(objs):
    o.location = (3.5 - (k % 3) * 3.5, 0, 8.4 - (k // 3) * 3.5)
A.still(NAME, eye=(2.2, 8.2, 3.5), look_at=(0, 0, 5.0), fov=70.0)
for o in objs:
    o.location = (40, 0, 0)
objs[0].location = (0, 0, 2.6)
A.still(NAME + '-B4', eye=(-1.7, 3.1, 1.6), look_at=(0, 0, 2.6))
bpy.data.objects.remove(wo)
bpy.data.meshes.remove(wm)
for o in objs:
    o.location = (0, 0, 0)
path = A.export(NAME)
print(f'ASSET {NAME}: {tris} tris ({kit.tris(objs[0].data)} each, budget {EACH} each), {os.path.getsize(path)} bytes -> {path}')
