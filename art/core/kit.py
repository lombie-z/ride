"""The kit every part of the fifth zone (art/build-city5.py: inside the desert's building) is built with: the road, the
sections, the shared materials and textures, mesh helpers (from art/build-city4.py), baked light, and how pieces are
placed. One module per group of objects (art/core/gate.py, lab.py, tanks.py, servers.py, chamber.py), each:

    def build(kit) -> dict   # its pieces, each made once with kit.piece(name, mesh) (origin at its base, +X along the road)
    def place(kit, pieces)   # lays its section out in the city's frame with kit.put(...) and kit.static(...)

The frame (Blender, z up, metres): the road comes in along +X at the origin (where the desert's way out ends), its deck
top z 0, 11.8 m wide, built by art/build-city5.py (deck, dashes): nothing else goes on |d| < 5.9 except where said.
The site lights it with a dim hemisphere, an environment map and fog: no lamps. So all light is painted in: emissive
materials, plus kit.bake_light (vertex colours multiply the base colour) for the spill on walls and floors.

Run a module alone: blender --background --factory-startup --python art/core/preview.py -- <module> <shot> [tag]
(renders art/renders/core-<module>-<shot>-<tag>.png from the module's SHOTS = {shot: (eye, look, fov)}).
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(HERE, '..', '..'))
RENDERS = os.path.join(ROOT_DIR, 'art', 'renders')
TEX_DIR = os.path.join(HERE, 'tex')
PREFIX = 'City5'
ROAD_W = 11.8

# The road: where each section runs (s, metres along the road).
SECTIONS = {
    'gate': (0.0, 150.0),         # the vault tunnel on from the desert's gate (concept-core-gate)
    'lab': (150.0, 1400.0),       # the white specimen corridor (concept-core-lab), a bulkhead door at its far end
    'servers': (1400.0, 0.0),     # the server hall (concept-core-servers), long gentle sweeps; ends at the chamber's mouth, below
    'core': (0.0, 0.0),           # the bridge into the core's chamber (concept-core-plaza)
}
ROAD_SEQ = [  # ('S', length) | ('A', radius, degrees, + = left)
    ('S', 1400.0),           # gate and lab, dead straight
    ('S', 900.0),
    ('A', 1100.0, 9.0),
    ('S', 700.0),
    ('A', 1000.0, -16.0),
    ('S', 900.0),
    ('A', 1200.0, 10.0),
    ('S', 600.0),
    ('A', 1100.0, -10.0),
    ('S', 800.0),
    ('A', 1100.0, 7.0),      # back to heading +X
    ('S', 1030.0),           # the last straight, on through the chamber's mouth to the bike's spot
]
# The lab's plan (m off the centreline; the lab and tanks modules share it).
LAB = {'gutter': 6.3, 'walk': 7.2, 'tank_y': 12.2, 'tank_r': 3.3, 'tank_every': 18.0, 'tank_from': 170.0, 'wall_y': 17.0, 'height': 10.5, 'door_s': 1392.0}


def frange(a, b, s):
    out, x = [], a
    while x <= b + 1e-6:
        out.append(x)
        x += s
    return out


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def trace(seq, step, x=0.0, y=0.0, h=0.0):
    """Dense points along a straights-and-arcs sequence (from (x, y) heading h), ~`step` m apart."""
    pts = [Vector((x, y, 0))]
    for sg in seq:
        if sg[0] == 'S':
            n = max(1, round(sg[1] / step))
            for i in range(1, n + 1):
                pts.append(Vector((x + math.cos(h) * sg[1] * i / n, y + math.sin(h) * sg[1] * i / n, 0)))
        else:
            R, d = sg[1], math.radians(sg[2])
            side = 1 if d > 0 else -1
            cx, cy = x - side * R * math.sin(h), y + side * R * math.cos(h)
            a0 = h - side * math.pi / 2
            n = max(2, round(abs(d) * R / step))
            for i in range(1, n + 1):
                a = a0 + d * i / n
                pts.append(Vector((cx + R * math.cos(a), cy + R * math.sin(a), 0)))
            h += d
        x, y = pts[-1].x, pts[-1].y
    return pts, h


def resample_exact(pts, step):
    """Points every `step` m of arc length along a polyline, plus its exact end."""
    out, acc = [pts[0]], 0.0
    for a, b in zip(pts, pts[1:]):
        seg = (b - a).length
        t0 = 0.0
        while acc + (seg - t0) >= step - 1e-9:
            t0 += step - acc
            out.append(a.lerp(b, t0 / seg))
            acc = 0.0
        acc += seg - t0
    if (out[-1] - pts[-1]).length > 1e-3:
        out.append(pts[-1])
    return out


def poly_len(pts):
    return sum((b - a).length for a, b in zip(pts, pts[1:]))


_pts, _h = trace(ROAD_SEQ, 2.0)
assert abs(_h) < 1e-9, _h
_DL = _pts
_DS = [0.0]
for a, b in zip(_DL, _DL[1:]):
    _DS.append(_DS[-1] + (b - a).length)
ROAD_LEN = _DS[-1]
# The chamber's mouth, this far short of the bike's spot; its bridge beyond.
MOUTH = ROAD_LEN - 130.43
SECTIONS['servers'] = (1400.0, MOUTH)
SECTIONS['core'] = (MOUTH, ROAD_LEN - 6.0)


def frame(s):
    """Point, tangent and left normal s metres along the road's centreline."""
    i = max(0, min(int(np.searchsorted(_DS, s)) - 1, len(_DL) - 2))
    t = (s - _DS[i]) / max(_DS[i + 1] - _DS[i], 1e-9)
    p = _DL[i].lerp(_DL[i + 1], min(max(t, 0.0), 1.0))
    tan = (_DL[i + 1] - _DL[i]).normalized()
    return p, tan, Vector((-tan.y, tan.x, 0))


def along(s, d=0.0, z=0.0):
    """The point s metres along the road, d metres left of its centreline, z up."""
    p, t, n = frame(s)
    return Vector((p.x + n.x * d, p.y + n.y * d, z))


def heading(s):
    """The road's heading s metres along (radians about z, from +X): a piece's yaw to run along it."""
    _, t, _n = frame(s)
    return math.atan2(t.y, t.x)


def vnoise(n, cells, seed, octaves=1, gain=0.5):
    """Tileable fractal value noise, n x n, in 0..1."""
    rng = np.random.default_rng(seed)
    out = np.zeros((n, n))
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        c = cells * 2 ** o
        g = rng.random((c, c))
        t = np.arange(n) * c / n
        i0 = np.floor(t).astype(int)
        f = t - i0
        f = f * f * (3 - 2 * f)
        i1 = (i0 + 1) % c
        a = g[np.ix_(i0, i0)] * (1 - f)[None, :] + g[np.ix_(i0, i1)] * f[None, :]
        b = g[np.ix_(i1, i0)] * (1 - f)[None, :] + g[np.ix_(i1, i1)] * f[None, :]
        out += amp * (a * (1 - f)[:, None] + b * f[:, None])
        tot += amp
        amp *= gain
    return out / tot


def draw_line(img, p0, p1, val, w=1):
    """Draw a line (rows, cols) into a 2-D array, wrapping (tileable)."""
    (y0, x0), (y1, x1) = p0, p1
    n = int(max(abs(x1 - x0), abs(y1 - y0)) * 1.5) + 1
    h, wd = img.shape[:2]
    for t in np.linspace(0, 1, n):
        y, x = y0 + (y1 - y0) * t, x0 + (x1 - x0) * t
        for dy in range(-(w // 2), w - w // 2):
            for dx in range(-(w // 2), w - w // 2):
                img[int(y + dy) % h, int(x + dx) % wd] = val


def crack_walk(img, rng, start, steps, step_len, val, w=1, wander=0.5):
    y, x = start
    a = rng.uniform(0, 2 * math.pi)
    for _ in range(steps):
        a += rng.normal(0, wander)
        ny, nx = y + math.sin(a) * step_len, x + math.cos(a) * step_len
        draw_line(img, (y, x), (ny, nx), val, w)
        y, x = ny, nx
        if rng.random() < 0.08:
            crack_walk(img, rng, (y, x), steps // 3, step_len * 0.8, val, 1, wander)


def make_image(name, rgba, jpeg=True):
    h, w = rgba.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=not jpeg)
    px = np.ones((h, w, 4), np.float32)
    px[..., :rgba.shape[2]] = rgba
    img.pixels.foreach_set(px[::-1].ravel())  # Blender's rows run bottom up
    img.file_format = 'JPEG' if jpeg else 'PNG'
    img.filepath_raw = f'//tex/{name}.{"jpg" if jpeg else "png"}'
    img.pack()
    return img
def tex_asphalt():
    """512 x 512 over 12 m across (u, columns) by 27 m along (v, rows): grainy dark asphalt, patches, cracks, sand dust,
    worn centre dashes (3 m on, 6 m off)."""
    n = 512
    rng = np.random.default_rng(3)
    g = 0.55 + 0.45 * vnoise(n, 8, 1, 4)
    grain = rng.random((n, n)) * 0.25 + 0.75
    base = (g * grain)[..., None] * np.array([0.25, 0.215, 0.19])
    patch = vnoise(n, 4, 2, 3)
    base *= (0.8 + 0.4 * smoothstep(0.45, 0.7, patch))[..., None]
    cracks = np.zeros((n, n))
    for _ in range(26):
        crack_walk(cracks, rng, (rng.uniform(0, n), rng.uniform(0, n)), 46, 5.0, 1.0, 3, 0.45)
    base *= (1 - 0.88 * cracks)[..., None]
    # The centre dashes (u 0.5, 0.15 m wide = 6.4 px), worn.
    paint = np.zeros((n, n))
    c0 = n // 2
    for k in range(3):
        r0 = int(k * n / 3)
        paint[r0:r0 + int(n * 3 / 27), c0 - 3:c0 + 4] = 1.0
    paint *= (vnoise(n, 32, 5, 2) > 0.38) * (1 - cracks)
    base = base * (1 - paint[..., None]) + paint[..., None] * np.array([0.62, 0.56, 0.46]) * grain[..., None]
    # Sand dust blown over it, heavier toward the edges (u near 0 and 1).
    edge = smoothstep(0.32, 0.5, np.abs(np.arange(n) / n - 0.5))[None, :]
    dust = smoothstep(0.4, 0.7, vnoise(n, 6, 7, 4)) * 0.8 + edge * 0.8 * vnoise(n, 10, 8, 3)
    dust = np.clip(dust, 0, 1)[..., None]
    return base * (1 - dust) + dust * np.array([0.62, 0.42, 0.24]) * grain[..., None]


def tex_sand():
    """256 x 256, ~8 m tile: wind ripples, warm amber."""
    n = 256
    yy, xx = np.mgrid[0:n, 0:n] / n
    warp = vnoise(n, 4, 21, 3)
    rip = 0.5 + 0.5 * np.sin(2 * math.pi * (yy * 24 + xx * 3 + warp * 3.0))
    rip = rip ** 2.5
    v = 0.82 + 0.12 * vnoise(n, 8, 22, 3) + 0.10 * rip
    grain = np.random.default_rng(4).random((n, n)) * 0.08 + 0.96
    return (v * grain)[..., None] * np.array([0.78, 0.50, 0.27])


def tex_rust():
    """256 x 256: dark rusted metal, streaks running down (rows), pitting."""
    n = 256
    rng = np.random.default_rng(31)
    a = vnoise(n, 6, 32, 5)
    cols = rng.random(n)
    streak = np.tile(cols[None, :], (n, 1))
    streak = np.convolve(streak[0], np.ones(5) / 5, mode='same')[None, :] * np.ones((n, 1))
    streak *= 0.6 + 0.4 * vnoise(n, 4, 35, 2)
    rust = smoothstep(0.35, 0.75, a * 0.6 + streak * 0.5)
    dark = np.array([0.15, 0.125, 0.105])
    orange = np.array([0.46, 0.22, 0.09])
    c = dark * (1 - rust[..., None]) + orange * rust[..., None]
    pits = (rng.random((n, n)) > 0.985)
    c[pits] *= 0.5
    return c * (0.85 + 0.3 * vnoise(n, 16, 36, 2))[..., None]


def tex_concrete():
    """256 x 256: weathered concrete, stains and water marks running down."""
    n = 256
    a = vnoise(n, 5, 41, 5)
    b = vnoise(n, 24, 42, 2)
    streak = np.tile(np.random.default_rng(43).random(n)[None, :], (n, 1))
    streak = np.array([np.convolve(r, np.ones(7) / 7, mode='same') for r in streak])
    v = 0.78 + 0.18 * a + 0.06 * b - 0.18 * smoothstep(0.55, 0.9, streak) * vnoise(n, 3, 44, 2)
    return v[..., None] * np.array([0.66, 0.56, 0.45])


# A 5 x 7 bitmap font for the terminals' text (only what they say).
FONT = {
    'A': '01110100011000111111100011000110001', 'B': '11110100011000111110100011000111110',
    'C': '01110100011000010000100001000101110', 'D': '11110100011000110001100011000111110',
    'E': '11111100001000011110100001000011111', 'F': '11111100001000011110100001000010000',
    'G': '01110100011000010111100011000101111', 'H': '10001100011000111111100011000110001',
    'I': '01110001000010000100001000010001110', 'K': '10001100101010011000101001001010001',
    'L': '10000100001000010000100001000011111', 'M': '10001110111010110101100011000110001',
    'N': '10001110011010110011100011000110001', 'O': '01110100011000110001100011000101110',
    'P': '11110100011000111110100001000010000', 'R': '11110100011000111110101001001010001',
    'S': '01111100001000001110000010000111110', 'T': '11111001000010000100001000010000100',
    'U': '10001100011000110001100011000101110', 'V': '10001100011000110001100010101000100',
    'W': '10001100011000110101101011101110001', 'X': '10001100010101000100010101000110001',
    'Y': '10001100010101000100001000010000100', 'Q': '01110100011000110001101011001001101',
    '0': '01110100011001110101110011000101110', '1': '00100011000010000100001000010001110',
    '2': '01110100010000100010001000100011111', '3': '11110000010000101110000010000111110',
    '4': '00010001100101010010111110001000010', '5': '11111100001111000001000011000101110',
    '6': '00110010001000011110100011000101110', '7': '11111000010001000100010000100001000',
    '8': '01110100011000101110100011000101110', '9': '01110100011000101111000010001001100',
    '>': '10000010000010000010001000100010000', '.': '00000000000000000000000000110001100',
    ':': '00000011000110000000011000110000000', '_': '00000000000000000000000000000011111',
    '-': '00000000000000011111000000000000000', '[': '01110010000100001000010000100001110',
    ']': '01110000100001000010000100001001110', '/': '00001000010001000100010001000010000',
    '%': '11001110010001000100010001001110011', ' ': '0' * 35,
}
TERMINAL = ['> BOOT SEQ 4F2', '> NODE 12 OFFLINE', '> CORE TEMP: 71.3', '> SECTOR DATA [LOST]', '> UPLINK.... FAILED',
            '> MEM 0% / 0%', '> AWAIT INPUT_']


def tex_screen():
    """512 x 256: green terminal text on a dark CRT, scan lines, vignette, a crack."""
    w, h = 512, 256
    img = np.zeros((h, w))
    s = 3  # px per font pixel
    for li, line in enumerate(TERMINAL):
        y0 = 14 + li * 33
        for ci, ch in enumerate(line):
            glyph = FONT.get(ch, FONT[' '])
            x0 = 18 + ci * 6 * s
            for k, bit in enumerate(glyph):
                if bit == '1':
                    r, c = divmod(k, 5)
                    img[y0 + r * s:y0 + r * s + s, x0 + c * s:x0 + c * s + s] = 1.0
    glow = img.copy()
    for _ in range(3):
        glow = (glow + np.roll(glow, 1, 0) + np.roll(glow, -1, 0) + np.roll(glow, 1, 1) + np.roll(glow, -1, 1)) / 5
    v = np.clip(img * 0.9 + glow * 0.8, 0, 1)
    scan = 0.75 + 0.25 * (np.arange(h) % 3 != 0)[:, None]
    yy, xx = np.mgrid[0:h, 0:w]
    vig = 1 - 0.55 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) ** 1.5
    bg = 0.10 + 0.06 * vnoise(256, 6, 51, 2)[np.ix_(np.arange(h) % 256, np.arange(w) % 256)]
    lum = np.clip((bg + v) * scan * np.clip(vig, 0.2, 1), 0, 1.2)
    rgb = lum[..., None] * np.array([0.35, 1.0, 0.45])
    crack = np.zeros((h, w))
    crack_walk(crack, np.random.default_rng(52), (h * 0.3, w * 0.78), 26, 6.0, 1.0, 1, 0.6)
    rgb = rgb * (1 - 0.85 * crack[..., None]) + crack[..., None] * np.array([0.25, 0.3, 0.25])
    return np.clip(rgb, 0, 1)




_tex = {}
_gen = {'asphalt': tex_asphalt, 'sand': tex_sand, 'rust': tex_rust, 'concrete': tex_concrete, 'screen': tex_screen}


def register_texture(name, fn, jpeg=True):
    """A generated texture a module adds (fn() -> rows x cols x 3 or 4, 0..1, at most 512 px); then material(tex=name)."""
    _gen[name] = (fn, jpeg)


def TEX(name):
    """A texture by name: art/core/tex/<name>.jpg if there is one (dropped in by the textures group), else generated."""
    if name in _tex:
        return _tex[name]
    path = os.path.join(TEX_DIR, name + '.jpg')
    if os.path.exists(path):
        img = bpy.data.images.load(path)
        img.name = f'{PREFIX}{name.capitalize()}Tex'
        img.pack()
    else:
        g = _gen[name]
        fn, jpeg = g if isinstance(g, tuple) else (g, True)
        img = make_image(f'{PREFIX}{name.capitalize()}Tex', fn(), jpeg=jpeg)
    _tex[name] = img
    return img


def material(name, colour, roughness=0.6, metallic=0.0, tex=None, vcol=True, emission=None, strength=0.0,
             emit_tex=False, alpha_tex=False, alpha=1.0, spec=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*colour, 1)
    p.inputs['Roughness'].default_value = roughness
    p.inputs['Metallic'].default_value = metallic
    if 'Specular IOR Level' in p.inputs:
        p.inputs['Specular IOR Level'].default_value = spec
    col_out = None
    if tex is not None:
        it = nt.nodes.new('ShaderNodeTexImage')
        it.image = TEX(tex)
        uvn = nt.nodes.new('ShaderNodeUVMap')
        uvn.uv_map = 'UVMap'
        nt.links.new(uvn.outputs['UV'], it.inputs['Vector'])
        col_out = it.outputs['Color']
        if alpha_tex:
            nt.links.new(it.outputs['Alpha'], p.inputs['Alpha'])
    if vcol:
        ca = nt.nodes.new('ShaderNodeVertexColor')
        ca.layer_name = 'AO'
        if col_out is not None:
            mix = nt.nodes.new('ShaderNodeMix')
            mix.data_type = 'RGBA'
            mix.blend_type = 'MULTIPLY'
            mix.inputs['Factor'].default_value = 1.0
            nt.links.new(col_out, mix.inputs['A'])
            nt.links.new(ca.outputs['Color'], mix.inputs['B'])
            nt.links.new(mix.outputs['Result'], p.inputs['Base Color'])
        else:
            mix = nt.nodes.new('ShaderNodeMix')
            mix.data_type = 'RGBA'
            mix.blend_type = 'MULTIPLY'
            mix.inputs['Factor'].default_value = 1.0
            mix.inputs['A'].default_value = (*colour, 1)
            nt.links.new(ca.outputs['Color'], mix.inputs['B'])
            nt.links.new(mix.outputs['Result'], p.inputs['Base Color'])
    elif col_out is not None:
        nt.links.new(col_out, p.inputs['Base Color'])
    if emission:
        p.inputs['Emission Color'].default_value = (*emission, 1)
        p.inputs['Emission Strength'].default_value = strength
        if emit_tex and col_out is not None:
            nt.links.new(col_out, p.inputs['Emission Color'])
    if alpha < 1 or alpha_tex:
        if not alpha_tex:
            p.inputs['Alpha'].default_value = alpha
        if hasattr(m, 'surface_render_method'):
            m.surface_render_method = 'BLENDED'
        m.use_backface_culling = False
    return m


def tex_tile():
    """512 x 512 over 4.8 m: white glazed tiles, 0.6 m, dark grout, rust runs and grime (the lab's walls and ceiling)."""
    n = 512
    rng = np.random.default_rng(21)
    cell = n // 8
    grime = vnoise(n, 6, 22, 4)
    base = np.ones((n, n, 3)) * np.array([0.78, 0.79, 0.74])
    ids = rng.random((8, 8))
    for r in range(8):
        for c in range(8):
            base[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell] *= 0.88 + 0.12 * ids[r, c]
    base[::cell, :] *= 0.25
    base[1::cell, :] *= 0.45
    base[:, ::cell] *= 0.25
    base[:, 1::cell] *= 0.45
    runs = vnoise(n, 40, 23, 2)
    runs = np.repeat(runs[:1], n, axis=0) * smoothstep(0.2, 1.0, 1 - np.arange(n)[:, None] / n)
    base *= (1 - 0.55 * smoothstep(0.55, 0.85, grime))[..., None]
    rust = smoothstep(0.62, 0.8, runs)[..., None]
    base = base * (1 - rust) + rust * np.array([0.3, 0.17, 0.09]) * base
    return np.clip(base, 0, 1)


def tex_code():
    """256 x 256, tiling, scrolled up on the site: sparse long thin streaks of falling green, broken a little, a bright head
    to each, on black (concept-core-servers)."""
    n = 256
    rng = np.random.default_rng(31)
    out = np.zeros((n, n, 3))
    cols = 26
    w = n // cols
    for c in range(cols):
        if rng.random() < 0.28:
            continue
        for _ in range(rng.integers(1, 3)):
            head = rng.integers(0, n)
            length = rng.integers(70, 210)
            gap = rng.integers(0, 3)
            x0 = c * w + rng.integers(2, max(3, w - 3))
            for i in range(length):
                y = (head + i) % n
                if gap and (i // 9) % 5 == gap:
                    continue
                b = (1 - i / length) ** 1.3
                out[y, x0:x0 + 2] = np.maximum(out[y, x0:x0 + 2], np.array([0.22, 1.0, 0.28]) * b + (np.array([0.75, 0.5, 0.7]) if i < 5 else 0))
    return np.clip(out, 0, 1)


_gen['tile'] = tex_tile
_gen['code'] = tex_code

# The shared materials (add a module's own with kit.material(f'{kit.PREFIX}Name', ...)). By their name's ending the site
# treats them (components/three/zone-city.tsx): Led, Red, Panel, Screen, Fluid, Heart past white for the bloom; Code
# scrolls; Fluid, TankGlass and Mist draw see-through without writing depth.
MAT = {}


def _mats():
    MAT.update({
        'asphalt': material('City5Asphalt', (0.11, 0.115, 0.11), 0.42, tex='asphalt', spec=0.5),
        'tile': material('City5Tile', (0.86, 0.87, 0.82), 0.38, tex='tile', spec=0.6),
        'concrete': material('City5Concrete', (0.42, 0.42, 0.38), 0.85, tex='concrete', spec=0.3),
        'rust': material('City5Rust', (0.34, 0.23, 0.16), 0.68, 0.4, tex='rust'),
        'steel': material('City5Steel', (0.15, 0.16, 0.15), 0.5, 0.75),
        'panel': material('City5PanelBody', (0.74, 0.75, 0.71), 0.5, 0.1, tex='concrete'),
        'dark': material('City5Dark', (0.022, 0.026, 0.024), 0.7, 0.3),
        'cable': material('City5Cable', (0.02, 0.022, 0.02), 0.55, 0.1),
        'sand': material('City5Sand', (0.72, 0.46, 0.25), 0.95, tex='sand', spec=0.3),
        'led': material('City5Led', (0.25, 1.0, 0.35), 0.4, vcol=False, emission=(0.35, 1.0, 0.3), strength=4.0),
        'red': material('City5Red', (1.0, 0.1, 0.06), 0.4, vcol=False, emission=(1.0, 0.1, 0.06), strength=5.0),
        'light': material('City5Panel', (0.95, 1.0, 0.92), 0.4, vcol=False, emission=(0.95, 1.0, 0.9), strength=3.0),
        'screen': material('City5Screen', (0.05, 0.25, 0.08), 0.35, vcol=False, tex='screen', emission=(0.3, 1.0, 0.4), strength=2.2, emit_tex=True),
        'code': material('City5Code', (0.0, 0.0, 0.0), 0.5, vcol=False, tex='code', emission=(1, 1, 1), strength=2.6, emit_tex=True),
        'fluid': material('City5Fluid', (0.2, 0.9, 0.3), 0.2, vcol=False, emission=(0.25, 1.0, 0.3), strength=0.7, alpha=0.42),
        'glass': material('City5TankGlass', (0.7, 0.9, 0.75), 0.06, 0.1, vcol=False, alpha=0.14, spec=0.8),
        'flesh': material('City5Flesh', (0.05, 0.13, 0.05), 0.5),
        'mist': material('City5Mist', (0.72, 0.8, 0.74), 1.0, vcol=False, alpha=0.2, spec=0.0),
        'hazard': material('City5Hazard', (0.55, 0.42, 0.08), 0.7),
    })


def mesh_from(name, bm, mats, smooth=False, recalc=True):
    me = bpy.data.meshes.new(name)
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for m in (mats if isinstance(mats, (list, tuple)) else [mats]):
        me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = smooth
    return me


def add_box(bm, c, size, mat=0, rot=None):
    """An axis-aligned box (centre c, size (x, y, z)), optionally rotated about its centre; returns its faces."""
    res = bmesh.ops.create_cube(bm, size=1.0)
    vs = res['verts']
    M = Matrix.Translation(Vector(c))
    if rot is not None:
        M = M @ rot.to_4x4()
    M = M @ Matrix.Diagonal((*size, 1.0))
    bmesh.ops.transform(bm, matrix=M, verts=vs)
    faces = list({f for v in vs for f in v.link_faces})
    for f in faces:
        f.material_index = mat
    return faces


def add_quad(bm, corners, mat=0):
    f = bm.faces.new([bm.verts.new(c) for c in corners])
    f.material_index = mat
    return f


def lathe(bm, profile, seg=24, cx=0.0, cy=0.0, z0=0.0, cap_top=True, cap_bottom=True, mat=0):
    rings = []
    for r, z in profile:
        rings.append([bm.verts.new((cx + r * math.cos(2 * math.pi * i / seg), cy + r * math.sin(2 * math.pi * i / seg),
                                    z0 + z)) for i in range(seg)])
    for a, b in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((a[i], a[j], b[j], b[i])).material_index = mat
    if cap_bottom and profile[0][0] > 1e-4:
        bm.faces.new(list(reversed(rings[0]))).material_index = mat
    if cap_top and profile[-1][0] > 1e-4:
        bm.faces.new(rings[-1]).material_index = mat
    return rings


def sweep(bm, path, profile, up=Vector((0, 0, 1)), mat=0, caps=True):
    """Extrude a closed 2-D (lateral, vertical) profile along a 3-D path."""
    rings = []
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        side = t.cross(up)
        if side.length < 1e-6:
            side = t.cross(Vector((1, 0, 0)))
        side.normalize()
        u = side.cross(t).normalized()
        rings.append([bm.verts.new(p + side * a + u * b) for a, b in profile])
    n = len(profile)
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i])).material_index = mat
    if caps:
        bm.faces.new(list(reversed(rings[0]))).material_index = mat
        bm.faces.new(rings[-1]).material_index = mat
    return rings


def circle_profile(r, n=6):
    return [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def box_uvs(me, scale=0.25):
    """Box-projected UVs (by each face's dominant normal axis), `scale` UV units per metre."""
    uv = me.uv_layers.new(name='UVMap') if 'UVMap' not in me.uv_layers else me.uv_layers['UVMap']
    for poly in me.polygons:
        n = poly.normal
        ax = max(range(3), key=lambda k: abs(n[k]))
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if ax == 0:
                u, v = co.y, co.z
            elif ax == 1:
                u, v = co.x, co.z
            else:
                u, v = co.x, co.y
            uv.data[li].uv = (u * scale, v * scale)


def planar_uvs(me, scale=0.1):
    uv = me.uv_layers.new(name='UVMap')
    for loop in me.loops:
        co = me.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (co.x * scale, co.y * scale)


def set_vcol(me, values):
    """Per-vertex AO values (0..1) into the 'AO' corner colour attribute (sRGB bytes)."""
    if 'AO' in me.color_attributes:
        me.color_attributes.remove(me.color_attributes['AO'])
    ca = me.color_attributes.new('AO', 'BYTE_COLOR', 'CORNER')
    vi = np.zeros(len(me.loops), np.int64)
    me.loops.foreach_get('vertex_index', vi)
    v = np.asarray(values, np.float32)[vi]
    cols = np.repeat(v[:, None], 4, axis=1)
    cols[:, 3] = 1.0
    ca.data.foreach_set('color', cols.ravel())
    me.color_attributes.active_color = ca


def bake_ao(me, rays=14, dist=None, floor=0.5, extra=None):
    """Self-occlusion ambient occlusion into vertex colours: hemisphere rays from each vertex against the mesh itself
    (plus an optional ground plane at z `extra`), mapped to floor..1."""
    verts = [v.co.copy() for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    if not polys:
        return
    bvh = BVHTree.FromPolygons(verts, polys)
    size = max((Vector(me.vertices[0].co) - v.co).length for v in me.vertices) if dist is None else dist
    dist = dist or max(0.5, size * 0.6)
    rng = np.random.default_rng(5)
    dirs = rng.normal(size=(rays, 3))
    dirs /= np.linalg.norm(dirs, axis=1)[:, None]
    out = np.ones(len(verts))
    for i, v in enumerate(me.vertices):
        n = v.normal
        o = v.co + n * 0.01
        hits = 0
        for d in dirs:
            d = Vector(d)
            if d.dot(n) < 0:
                d = -d
            d = (d + n * 0.3).normalized()
            if bvh.ray_cast(o, d, dist)[0] is not None:
                hits += 1
            elif extra is not None and d.z < -0.05 and (extra - o.z) / d.z < dist:
                hits += 1
        out[i] = 1 - hits / rays
    set_vcol(me, floor + (1 - floor) * out)




def set_vcol_rgb(me, values):
    """Per-vertex colours (n x 3, 0..1) into the 'AO' corner colour attribute: they multiply the material's base colour."""
    if 'AO' in me.color_attributes:
        me.color_attributes.remove(me.color_attributes['AO'])
    ca = me.color_attributes.new('AO', 'BYTE_COLOR', 'CORNER')
    vi = np.zeros(len(me.loops), np.int64)
    me.loops.foreach_get('vertex_index', vi)
    v = np.clip(np.asarray(values, np.float32), 0, 1)[vi]
    cols = np.concatenate([v, np.ones((len(v), 1), np.float32)], axis=1)
    ca.data.foreach_set('color', cols.ravel())
    me.color_attributes.active_color = ca


def bake_light(me, lights, ambient=(0.2, 0.22, 0.2), rays=0, dist=6.0, floor=0.55, m=None):
    """Paints light into a mesh's vertex colours: ambient plus, for each light ((x, y, z), (r, g, b), radius, power) in its
    local frame, a soft N.L falloff; times hemisphere ray AO if rays > 0. Needs vertices where the gradient should show
    (subdivide flat walls to a metre or two first: kit.dice). `m`: the object's world matrix if the lights are given in
    the city's frame rather than the mesh's."""
    n = len(me.vertices)
    co = np.zeros(n * 3)
    no = np.zeros(n * 3)
    me.vertices.foreach_get('co', co)
    me.vertex_normals.foreach_get('vector', no)
    co, no = co.reshape(-1, 3), no.reshape(-1, 3)
    if m is not None:
        R = np.array(m.to_3x3())
        T = np.array(m.to_translation())
        co = co @ R.T + T
        no = no @ R.T
    out = np.tile(np.asarray(ambient, float), (n, 1))
    for pos, col, radius, power in lights:
        d = np.asarray(pos, float) - co
        r2 = (d * d).sum(1)
        nl = np.clip((d * no).sum(1) / np.sqrt(r2 + 1e-6), 0, 1) * 0.8 + 0.2
        out += np.outer(power * nl / (1 + r2 / (radius * radius)) ** 1.5, np.asarray(col, float))
    if rays:
        verts = [v.co.copy() for v in me.vertices]
        bvh = BVHTree.FromPolygons(verts, [tuple(p.vertices) for p in me.polygons])
        rng = np.random.default_rng(5)
        dirs = rng.normal(size=(rays, 3))
        dirs /= np.linalg.norm(dirs, axis=1)[:, None]
        for i, v in enumerate(me.vertices):
            nv = v.normal
            o = v.co + nv * 0.01
            hits = 0
            for d in dirs:
                d = Vector(d)
                if d.dot(nv) < 0:
                    d = -d
                if bvh.ray_cast(o, (d + nv * 0.3).normalized(), dist)[0] is not None:
                    hits += 1
            out[i] *= floor + (1 - floor) * (1 - hits / rays)
    set_vcol_rgb(me, out)


def dice(bm, size=1.5):
    """Subdivides a bmesh's long edges so vertex-colour light has somewhere to show."""
    for _ in range(8):
        long_edges = [e for e in bm.edges if e.calc_length() > size]
        if not long_edges:
            break
        bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=1, use_grid_fill=True)


def circle_profile_up(r, n=6):
    return circle_profile(r, n)


# --- The scene: pieces, placing them, the city's root. ---------------------------------------------------------------
root = None
_modules = None
_groups = {}


def begin():
    """A fresh scene with the City5 root (art/build-city5.py and art/core/preview.py call this once)."""
    global root, _modules
    bpy.ops.wm.read_factory_settings(use_empty=True)
    root = bpy.data.objects.new('City5', None)
    bpy.context.scene.collection.objects.link(root)
    _modules = bpy.data.collections.new('Modules')  # never linked to the scene: pieces exist only as what's placed
    _mats()
    return root


def group(name):
    if name not in _groups:
        e = bpy.data.objects.new(f'{PREFIX}.{name}', None)
        bpy.context.scene.collection.objects.link(e)
        e.parent = root
        _groups[name] = e
    return _groups[name]


def piece(name, me):
    """A repeated piece, made once; its mesh is shared by everything placed from it. Bake its AO or light first."""
    o = bpy.data.objects.new(f'{PREFIX}.{name}', me)
    _modules.objects.link(o)
    return o


def put(p, loc, yaw=0.0, scale=1.0, grp='Parts', tilt=(0.0, 0.0)):
    """A linked duplicate of a piece (exported as a GPU instance): at loc, turned yaw radians about z."""
    o = bpy.data.objects.new(p.name + '.i', p.data)
    bpy.context.scene.collection.objects.link(o)
    o.parent = group(grp)
    o.location = loc
    o.rotation_euler = (tilt[0], tilt[1], yaw)
    o.scale = scale if not isinstance(scale, (int, float)) else (scale,) * 3
    return o


def static(name, me, grp='Parts', loc=(0, 0, 0)):
    """A one-off mesh in the city's frame."""
    o = bpy.data.objects.new(f'{PREFIX}.{name}', me)
    bpy.context.scene.collection.objects.link(o)
    o.parent = group(grp)
    o.location = loc
    return o


def tris(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def render(eye, look, fov, path, res=(1280, 720), samples=16):
    """A quick EEVEE look: the site's dim ambient, emission only (no lamps, as on the site; it adds fog and bloom)."""
    scene = bpy.context.scene
    cam = bpy.data.objects.get('PreviewCam')
    if cam is None:
        cam = bpy.data.objects.new('PreviewCam', bpy.data.cameras.new('PreviewCam'))
        scene.collection.objects.link(cam)
    cam.location = eye
    d = (Vector(look) - Vector(eye)).normalized()
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = d.to_track_quat('-Z', 'Y')
    cam.data.sensor_fit = 'VERTICAL'
    cam.data.angle_y = math.radians(fov)
    cam.data.clip_start = 0.05
    cam.data.clip_end = 6000
    scene.camera = cam
    w = bpy.data.worlds.new('Ambient')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.1, 0.13, 0.11, 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
    scene.world = w
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.taa_render_samples = samples
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
