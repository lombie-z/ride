"""The lab corridor's shell (s 150-670, concept-core-lab): white tile, pilasters, the lit ceiling, cable bundles, the wet
walkways and the bulkhead at the far end with its door. Everything but the tanks and their consoles (art/core/tanks.py).

One side of a bay is a set of pieces, its origin on the road's centreline at the tank's s, its side at +y (yaw pi puts it
on the other side); the ceiling spans both sides and comes in a few variants. Ground plan: art/core/kit.py LAB.

The door: LabDoorL / LabDoorR (group LabDoor) slide +7.5 / -7.5 m along their local y on the site.
"""
import math
import sys

import bmesh
import numpy as np
from mathutils import Vector

WITH = ['tanks']

FLOOR_Z = 0.05          # the walkway's top, a kerb above the deck
ROAD_EDGE = 5.9
GRATE_W = 1.0
BAND = 11.5             # the tiled ceiling's half width; past it, the dark channel the cables run in
CHANNEL = 1.2           # how far the channel goes up past the ceiling
PIL_HW = 2.8            # the pilaster's half width along the road
PIL_Y = 10.8            # its face, off the centreline
LAMP = (0.0, 9.95, 6.3)  # the lamp on the pilaster, in its frame
import kit as _kit  # noqa: E402

LIFT_S = _kit.LAB['door_s'] - 33.0          # from the last pilaster but one to the end wall the ceiling steps up, for the control room
LIFT_Z = 15.2
END_FACE = _kit.LAB['door_s'] - 1.0        # the bulkhead's face; the door's leaves behind it, at door_s
SHOTS = {
    'ref': ((_kit.LAB['door_s'] - 100.0, 0.0, 1.8), (_kit.LAB['door_s'], 0.0, 21.2), 60.0),
    'ride': ((300.0, 0.0, 1.5), (400.0, 0.0, 6.0), 80.0),
    'door': ((_kit.LAB['door_s'] - 37.0, 0.0, 1.5), (_kit.LAB['door_s'], 0.0, 7.0), 70.0),
    'wall': ((404.0, -2.5, 1.5), (420.0, 13.0, 4.5), 70.0),
    'up': ((400.0, 0.0, 1.5), (420.0, 0.0, 10.0), 80.0),
    'start': ((130.0, 0.0, 1.8), (170.0, 0.0, 4.0), 75.0),
}


# --- Textures (all at most 512 px). ----------------------------------------------------------------------------------
def tex_labwall():
    """512 x 512 over 9.6 m by the wall's height: big white glazed tiles, seams, long rust runs from the joints."""
    from kit import vnoise, smoothstep
    n = 512
    cell = n // 8
    rng = np.random.default_rng(61)
    base = np.ones((n, n, 3)) * np.array([0.9, 0.9, 0.85])
    ids = rng.random((8, 8))
    for r in range(8):
        for c in range(8):
            base[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell] *= 0.86 + 0.14 * ids[r, c]
    base *= (0.86 + 0.14 * vnoise(n, 5, 62, 4))[..., None]
    for k in range(0, n, cell):
        heavy = k % (cell * 4) == 0
        wide = 3 if heavy else 2
        base[k:k + wide, :] *= 0.3 if heavy else 0.55
        base[:, k:k + wide] *= 0.3 if heavy else 0.55
    rust = np.zeros((n, n))
    stain = np.zeros((n, n))
    for k in range(120):
        r0 = int(rng.integers(0, 8)) * cell
        c0 = int(rng.integers(0, n))
        length = int(rng.integers(40, 340))
        w = int(rng.integers(2, 9))
        a = rng.uniform(0.4, 1.0)
        out = rust if k % 3 else stain
        for i in range(length):
            y = (r0 + i) % n
            x = (c0 + int(2 * math.sin(i * 0.04 + c0))) % n
            v = a * (1 - i / length) ** 1.1
            wi = max(1, int(w * (1 - 0.7 * i / length)))
            for dx in range(wi):
                out[y, (x + dx) % n] = max(out[y, (x + dx) % n], v * (0.65 + 0.35 * rng.random()))
    def soften(m):
        return (m + np.roll(m, 1, 1) + np.roll(m, -1, 1) + np.roll(m, 2, 1) + np.roll(m, -2, 1)) / 5
    patchy = 0.45 + 0.9 * vnoise(n, 10, 65, 3)
    rust = np.clip((rust * 0.4 + soften(rust) * 0.8) * patchy, 0, 1)[..., None]
    stain = np.clip((stain * 0.3 + soften(stain) * 0.7) * patchy, 0, 1)[..., None]
    base = base * (1 - 0.7 * stain)
    base = base * (1 - rust) + rust * np.array([0.3, 0.14, 0.06]) * (0.55 + 0.9 * rng.random((n, n, 1)))
    # Blotches of grime, gathered up from the floor too.
    grime = smoothstep(0.5, 0.82, vnoise(n, 6, 63, 5))[..., None]
    base *= 1 - 0.5 * grime
    low = smoothstep(0.75, 1.0, np.arange(n) / n)[:, None, None]
    base *= 1 - 0.55 * low * (0.5 + vnoise(n, 12, 64, 3)[..., None])
    return np.clip(base, 0, 1)


def tex_labceil():
    """512 x 512 over 9.6 m: the ceiling's white tile, 1.2 m, grout, big patches of dirt and damp, thin rust from its joints."""
    from kit import vnoise, smoothstep
    n = 512
    cell = n // 8
    rng = np.random.default_rng(66)
    base = np.ones((n, n, 3)) * np.array([0.9, 0.91, 0.86])
    ids = rng.random((8, 8))
    for r in range(8):
        for c in range(8):
            base[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell] *= 0.84 + 0.16 * ids[r, c]
    for k in range(0, n, cell):
        heavy = k % (cell * 4) == 0
        wide = 3 if heavy else 2
        base[k:k + wide, :] *= 0.25 if heavy else 0.5
        base[:, k:k + wide] *= 0.25 if heavy else 0.5
    damp = smoothstep(0.5, 0.8, vnoise(n, 8, 67, 4))[..., None]
    base *= 1 - 0.24 * damp
    for _ in range(40):  # rust spreading from the joints
        r0, c0 = int(rng.integers(0, 8)) * cell, int(rng.integers(0, 8)) * cell
        ln, w = int(rng.integers(20, 110)), int(rng.integers(1, 4))
        a = rng.uniform(0.3, 0.8)
        for i in range(ln):
            y, x = (r0 + i) % n, c0 % n
            base[y, x:x + w] = base[y, x:x + w] * (1 - a) + a * np.array([0.3, 0.15, 0.07])
    return np.clip(base, 0, 1)


def tex_labfloor():
    """512 x 512 over 4.8 m: dark wet tiles, 1.2 m, pale grout, chipped, stained."""
    from kit import vnoise, smoothstep, crack_walk
    n = 512
    cell = n // 4
    rng = np.random.default_rng(71)
    base = np.ones((n, n, 3)) * np.array([0.42, 0.43, 0.41])
    ids = rng.random((4, 4))
    for r in range(4):
        for c in range(4):
            base[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell] *= 0.62 + 0.5 * ids[r, c]
    base *= (0.55 + 0.75 * vnoise(n, 6, 72, 5))[..., None]
    cracks = np.zeros((n, n))
    for _ in range(9):
        crack_walk(cracks, rng, (rng.uniform(0, n), rng.uniform(0, n)), 22, 6.0, 1.0, 2, 0.5)
    base *= (1 - 0.8 * cracks)[..., None]
    for k in range(0, n, cell):
        base[k:k + 3, :] = np.array([0.08, 0.08, 0.075])
        base[:, k:k + 3] = np.array([0.08, 0.08, 0.075])
    wet = smoothstep(0.5, 0.8, vnoise(n, 4, 73, 4))[..., None]
    return np.clip(base * (1 - 0.5 * wet), 0, 1)


def tex_labgrate():
    """128 x 128, 0.74 m across (u: along the road): black slats over a deeper black."""
    n = 128
    out = np.ones((n, n, 3)) * 0.008
    for c in range(0, n, 16):
        out[:, c:c + 9] = np.array([0.075, 0.08, 0.075])
    out[:6, :] = 0.11
    out[-6:, :] = 0.11
    return out


def tex_labgrille():
    """128 x 128: grey louvres, dark gaps (rows)."""
    n = 128
    out = np.ones((n, n, 3)) * 0.02
    for r in range(0, n, 16):
        out[r:r + 10, :] = np.array([0.6, 0.6, 0.56])
        out[r + 10:r + 12, :] = np.array([0.22, 0.22, 0.2])
    return out


def tex_labbroken():
    """256 x 256, 1.85 m: a blown light panel, jagged shards of white on black running across it."""
    from kit import vnoise
    n = 256
    yy, xx = np.mgrid[0:n, 0:n] / n
    a = vnoise(n, 5, 82, 3)
    wave = 0.5 + 0.5 * np.sin(2 * math.pi * (xx * 3 + yy * 9 + a * 1.6))
    fine = vnoise(n, 32, 83, 2)
    mask = ((wave * 0.55 + a * 0.3 + fine * 0.35) > 0.62).astype(float)
    return mask[..., None] * np.array([0.95, 1.0, 0.92]) + (1 - mask[..., None]) * 0.012


def tex_labhalo():
    """128 x 128 RGBA: a soft round glow: black, its alpha all it gives (the materials' emission is the colour)."""
    n = 128
    yy, xx = np.mgrid[0:n, 0:n] + 0.5
    r = np.hypot(xx - n / 2, yy - n / 2) / (n / 2)
    a = np.clip(1 - r, 0, 1) ** 2.2
    return np.dstack([np.zeros((n, n)), np.zeros((n, n)), np.zeros((n, n)), a])


def tex_labsheen():
    """128 x 256 RGBA: a wet floor's stretched reflection, long and broken along v."""
    from kit import vnoise, smoothstep as kit_smooth
    w, h = 128, 256
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    across = np.clip(1 - np.abs(xx / w * 2 - 1), 0, 1) ** 1.4
    down = np.clip(1 - np.abs(yy / h * 2 - 1), 0, 1) ** 0.9
    n = vnoise(256, 14, 91, 3)
    rows = np.tile(np.random.default_rng(92).random(w)[None, :], (h, 1))  # streaks along it, wet, not a smear
    rows = np.array([np.convolve(r, np.ones(5) / 5, mode='same') for r in rows])
    break_up = kit_smooth(0.36, 0.62, n[:, :w] * 0.6 + rows * 0.55)
    a = across * down * break_up
    return np.dstack([np.zeros((h, w)), np.zeros((h, w)), np.zeros((h, w)), a])


def tex_labmist():
    """256 x 256 RGBA: a low bank of mist, thicker at its foot (row 255), a soft ragged top, no hard edges."""
    from kit import vnoise
    n = 256
    yy, xx = np.mgrid[0:n, 0:n] + 0.5
    across = np.clip(1 - np.abs(xx / n * 2 - 1), 0, 1) ** 0.8
    up = np.clip(yy / n, 0, 1) ** 1.5 * np.clip((n - yy) / (n * 0.08), 0, 1)
    a = across * up * (0.55 + 1.4 * vnoise(n, 5, 95, 4))
    return np.dstack([np.ones((n, n)), np.ones((n, n)), np.ones((n, n)), np.clip(a, 0, 1)])


# --- Mesh helpers. ---------------------------------------------------------------------------------------------------
def grid(bm, o, u, v, nu=1, nv=1, mat=0):
    """A flat grid from corner o along vectors u and v, facing u x v, nu x nv quads (the verts shared)."""
    o, u, v = Vector(o), Vector(u), Vector(v)
    rows = [[bm.verts.new(o + u * (i / nu) + v * (j / nv)) for i in range(nu + 1)] for j in range(nv + 1)]
    for j in range(nv):
        for i in range(nu):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i])).material_index = mat


def box(bm, x0, x1, y0, y1, z0, z1, mat=0):
    return _kit.add_box(bm, ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (x1 - x0, y1 - y0, z1 - z0), mat)


def uv_by(me, scales):
    """Box-projected UVs, each material slot its own (u, v) per metre."""
    uv = me.uv_layers.new(name='UVMap') if 'UVMap' not in me.uv_layers else me.uv_layers['UVMap']
    for poly in me.polygons:
        su, sv = scales.get(poly.material_index, (0.25, 0.25))
        n = poly.normal
        ax = max(range(3), key=lambda k: abs(n[k]))
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if ax == 0:
                a, b = co.y, co.z
            elif ax == 1:
                a, b = co.x, co.z
            else:
                a, b = co.x, co.y
            uv.data[li].uv = (a * su, b * sv)


def unit_uvs(me, slots, swap=False):
    """Each quad in these slots gets the texture once, 0..1 (`swap`: with u and v exchanged)."""
    uv = me.uv_layers['UVMap'] if 'UVMap' in me.uv_layers else me.uv_layers.new(name='UVMap')
    corners = [(0, 0), (0, 1), (1, 1), (1, 0)] if swap else [(0, 0), (1, 0), (1, 1), (0, 1)]
    for poly in me.polygons:
        if poly.material_index in slots:
            for k, li in enumerate(poly.loop_indices):
                uv.data[li].uv = corners[k % 4]


def done(name, bm, mats, uv, lights, ambient, smooth=False):
    """Finish a mesh: normals as authored, UVs, its baked light."""
    me = _kit.mesh_from(name, bm, mats, smooth=smooth, recalc=False)
    uv_by(me, uv)
    _kit.bake_light(me, lights, ambient=ambient)
    return me


_kit = None
_M = {}


def _materials(kit):
    kit.register_texture('labwall', tex_labwall)
    kit.register_texture('labceil', tex_labceil)
    kit.register_texture('labfloor', tex_labfloor)
    kit.register_texture('labgrate', tex_labgrate)
    kit.register_texture('labgrille', tex_labgrille)
    kit.register_texture('labbroken', tex_labbroken)
    kit.register_texture('labhalo', tex_labhalo, jpeg=False)
    kit.register_texture('labsheen', tex_labsheen, jpeg=False)
    kit.register_texture('labmist', tex_labmist, jpeg=False)
    P = kit.PREFIX
    m = kit.material
    _M.update({
        # (The site's hemisphere only lifts vertex colours so far: a low emission keeps the white tile white in the dark.)
        'wall': m(f'{P}LabWall', (0.9, 0.9, 0.85), 0.32, tex='labwall', spec=0.6, emission=(1, 1, 1), strength=0.15, emit_tex=True),
        'side': m(f'{P}LabWallSide', (0.9, 0.9, 0.85), 0.36, tex='labwall', spec=0.5, emission=(1, 1, 1), strength=0.08, emit_tex=True),
        'back': m(f'{P}LabBackWall', (0.9, 0.9, 0.85), 0.4, tex='labwall', spec=0.5, emission=(1, 1, 1), strength=0.05, emit_tex=True),
        'ceil': m(f'{P}LabCeil', (0.9, 0.9, 0.86), 0.34, tex='labceil', spec=0.5, emission=(1, 1, 1), strength=0.13, emit_tex=True),
        'lamp': m(f'{P}LabLampRed', (1.0, 0.05, 0.03), 0.35, vcol=False, emission=(1.0, 0.035, 0.02), strength=4.0),
        'floor': m(f'{P}LabFloor', (0.4, 0.4, 0.4), 0.12, tex='labfloor', spec=0.8, emission=(1, 1, 1), strength=0.16, emit_tex=True),
        'grate': m(f'{P}LabGrate', (0.05, 0.05, 0.05), 0.5, 0.4, tex='labgrate'),
        'grille': m(f'{P}LabGrille', (0.5, 0.5, 0.5), 0.5, 0.3, tex='labgrille'),
        'broken': m(f'{P}LabBrokenPanel', (0.0, 0.0, 0.0), 0.4, vcol=False, tex='labbroken', emission=(1, 1, 1), strength=3.0, emit_tex=True),
        'door': m(f'{P}LabDoor', (0.62, 0.63, 0.6), 0.42, 0.2, emission=(0.62, 0.63, 0.6), strength=0.26),
        'frame': m(f'{P}LabDoorFrame', (0.36, 0.37, 0.36), 0.5, 0.3, emission=(0.36, 0.37, 0.36), strength=0.32),
        'teal': m(f'{P}LabRoom', (0.02, 0.1, 0.1), 0.6, vcol=False, emission=(0.08, 0.55, 0.52), strength=0.2),
        'monitor': m(f'{P}LabMonitorScreen', (0.05, 0.4, 0.4), 0.3, vcol=False, emission=(0.22, 1.0, 0.9), strength=1.5),
        'halo': m(f'{P}LabHaloMist', (0.0, 0.0, 0.0), 1.0, vcol=False, tex='labhalo', emission=(1.0, 0.06, 0.04), strength=1.0, alpha_tex=True, spec=0.0),
        'wash_green': m(f'{P}LabWashGreenMist', (0.0, 0.0, 0.0), 1.0, vcol=False, tex='labhalo', emission=(0.16, 1.0, 0.26), strength=0.42, alpha_tex=True, spec=0.0),
        'wash_white': m(f'{P}LabWashWhiteMist', (0.0, 0.0, 0.0), 1.0, vcol=False, tex='labhalo', emission=(1.0, 1.0, 0.94), strength=0.95, alpha_tex=True, spec=0.0),
        'sheen_red': m(f'{P}LabSheenRedMist', (0.0, 0.0, 0.0), 1.0, vcol=False, tex='labsheen', emission=(1.0, 0.07, 0.05), strength=0.34, alpha_tex=True, spec=0.0),
        'sheen_green': m(f'{P}LabSheenGreenMist', (0.0, 0.0, 0.0), 1.0, vcol=False, tex='labsheen', emission=(0.2, 1.0, 0.3), strength=0.25, alpha_tex=True, spec=0.0),
        'sheen_white': m(f'{P}LabSheenWhiteMist', (0.0, 0.0, 0.0), 1.0, vcol=False, tex='labsheen', emission=(0.9, 1.0, 0.92), strength=0.5, alpha_tex=True, spec=0.0),
        'mist': m(f'{P}LabFloorMist', (0.7, 0.78, 0.72), 1.0, vcol=False, tex='labmist', emission=(0.72, 0.8, 0.74), strength=0.42, alpha_tex=True, spec=0.0),
    })


# Slots' UV scales: tiles over 9.6 m by the wall's height; everything else by what its texture covers.
WALL_UV = (1 / 9.6, 1 / (10.5 + CHANNEL))
FLOOR_UV = (1 / 4.8, 1 / 4.8)
WALL_UV_CEIL = (1 / 9.6, 1 / 9.6)
GRATE_UV = (1 / 0.74, 1 / GRATE_W)
GRILLE_UV = (1 / 1.0, 1 / 1.0)
BROKEN_UV = (1 / 1.85, 1 / 1.85)


def tank_s(kit):
    """Where the tanks stand (as art/core/tanks.py places them: on until one would touch the door's wall)."""
    L = kit.LAB
    return kit.frange(L['tank_from'], L['door_s'] - 1.0 - 3.62, L['tank_every'])


def shell_lights(H, x0=-9.0, x1=9.0, tank=True):
    """One side's spill: the panels overhead, the tank's green, the red lamps on the pilasters each end, the floor strips."""
    out = []
    for x in (-4.5, 4.5):
        out.append(((x, 3.7, H - 1.2), (0.95, 1.0, 0.93), 9.0, 0.42))
        out.append(((x, 8.4, H - 1.2), (0.95, 1.0, 0.93), 6.0, 0.22))
    if tank:
        out.append(((0.0, 12.2, 3.0), (0.1, 1.0, 0.22), 6.0, 1.15))
        out.append(((0.0, 8.0, 1.0), (0.1, 1.0, 0.22), 4.0, 0.5))
        for x in (-4.8, 4.8):
            out.append(((x, 8.6, 0.6), (0.95, 1.0, 0.95), 2.0, 0.8))
    for x in (x0, x1):
        out.append(((x, LAMP[1] - 0.5, LAMP[2]), (1.0, 0.07, 0.04), 5.0, 1.2))
    return out


def side_shell(name, x0, x1, H, tank=True):
    """One side of a stretch of corridor: walkway, drain, back wall, the dark channel overhead, the low plinths and strips."""
    kit = _kit
    M = _M
    mats = [M['wall'], M['floor'], M['grate'], kit.MAT['dark'], kit.MAT['light'], kit.MAT['steel'], M['back'], M['wash_green']]
    bm = bmesh.new()
    L = kit.LAB
    wall_y = L['wall_y']
    length = x1 - x0
    nx = max(2, round(length / 2.25))
    # The walkway (y rising away from the road), its kerb, the long drain.
    grid(bm, (x0, ROAD_EDGE, FLOOR_Z), (length, 0, 0), (0, wall_y - ROAD_EDGE, 0), nx, 6, 1)
    grid(bm, (x0, ROAD_EDGE, 0), (length, 0, 0), (0, 0, FLOOR_Z), 1, 1, 5)
    g0 = L['gutter'] + 0.15 - GRATE_W / 2
    grid(bm, (x0, g0, FLOOR_Z + 0.008), (length, 0, 0), (0, GRATE_W, 0), 1, 1, 2)
    # The back wall, facing the road.
    top = H + CHANNEL
    grid(bm, (x1, wall_y, 0), (-length, 0, 0), (0, 0, top), max(2, nx // 2 + 1), 4, 6)
    # The channel above the tanks: its roof, the fascia on the tiled band, a lip, two long conduits.
    grid(bm, (x1, BAND, top), (-length, 0, 0), (0, wall_y - BAND, 0), 1, 1, 3)
    grid(bm, (x1, BAND, H), (-length, 0, 0), (0, 0, CHANNEL), 1, 1, 3)
    box(bm, x0, x1, BAND - 0.3, BAND + 0.1, H - 0.34, H + 0.02, 5)
    box(bm, x0, x1, 12.8, 13.3, top - 0.75, top - 0.25, 5)
    box(bm, x0, x1, 15.2, 15.8, top - 0.8, top - 0.2, 5)
    if tank:
        # The low plinths either side of the tank and the strips of white on them (the bay's foot).
        for x in (-4.85, 4.85):
            box(bm, x - 1.3, x + 1.3, 8.7, 10.6, 0, 0.82, 0)
            box(bm, x - 1.15, x + 1.15, 8.64, 8.72, 0.32, 0.56, 4)
        # The tank's green on the wall behind it.
        grid(bm, (8.0, wall_y - 0.04, -1.0), (-16.0, 0, 0), (0, 0, 12.0), 1, 1, 7)
    me = done(name, bm, mats, {0: WALL_UV, 1: FLOOR_UV, 2: GRATE_UV, 6: WALL_UV}, shell_lights(H, x0, x1, tank), (0.42, 0.43, 0.41))
    unit_uvs(me, (7,))
    return me


def pilaster(name):
    """The chunky column between bays, with its flared foot, a vent, the caged red lamp on a bracket, the glow round it."""
    kit = _kit
    M = _M
    H = kit.LAB['height']
    wall_y = kit.LAB['wall_y']
    mats = [M['wall'], M['grille'], kit.MAT['dark'], M['lamp'], M['halo'], kit.MAT['steel'], M['wash_green'], M['side']]
    bm = bmesh.new()

    def section(hw, fy):
        c = 0.85
        return [(-hw, wall_y), (-hw, fy + c), (-hw + c, fy), (0.0, fy), (hw - c, fy), (hw, fy + c), (hw, wall_y)]

    rings = [(0.0, 3.15, 9.55), (0.55, 3.15, 9.55), (1.25, 3.05, 9.72), (2.2, 2.9, 10.25), (3.2, PIL_HW, PIL_Y),
             (4.8, PIL_HW, PIL_Y), (6.4, PIL_HW, PIL_Y), (8.0, PIL_HW, PIL_Y), (9.6, PIL_HW, PIL_Y), (H + CHANNEL, PIL_HW, PIL_Y)]
    made = []
    for z, hw, fy in rings:
        made.append([bm.verts.new((x, y, z)) for x, y in section(hw, fy)])
    for a, b in zip(made, made[1:]):
        for i in range(6):
            bm.faces.new((a[i], a[i + 1], b[i + 1], b[i])).material_index = 7 if i in (0, 5) else 0
    # The vents on its sides, facing along the road.
    for sx in (-1, 1):
        x = sx * (PIL_HW + 0.32)
        if sx < 0:
            grid(bm, (x, 13.6, 0.75), (0, -2.0, 0), (0, 0, 1.5), 1, 1, 1)
        else:
            grid(bm, (x, 11.6, 0.75), (0, 2.0, 0), (0, 0, 1.5), 1, 1, 1)
    # The lamp: a bracket off the face, the glass, its cage.
    x, y, z = LAMP
    box(bm, x - 0.16, x + 0.16, y, PIL_Y + 0.05, z - 0.18, z + 0.18, 5)
    box(bm, x - 0.3, x + 0.3, PIL_Y - 0.12, PIL_Y + 0.05, z - 0.55, z + 0.55, 5)
    kit.lathe(bm, [(0.3, 0.0), (0.3, 1.15)], seg=6, cx=x, cy=y - 0.25, z0=z - 0.6, mat=3)
    kit.lathe(bm, [(0.43, 0.0), (0.43, 0.14)], seg=6, cx=x, cy=y - 0.25, z0=z - 0.72, mat=2)
    kit.lathe(bm, [(0.43, 0.0), (0.43, 0.14)], seg=6, cx=x, cy=y - 0.25, z0=z + 0.55, mat=2)
    kit.lathe(bm, [(0.37, 0.0), (0.37, 0.07)], seg=6, cx=x, cy=y - 0.25, z0=z - 0.05, cap_top=False, cap_bottom=False, mat=2)
    for a in (0.0, 2.09, 4.19):
        cx = x + 0.4 * math.cos(a + 0.5)
        cy = y - 0.25 + 0.4 * math.sin(a + 0.5)
        box(bm, cx - 0.03, cx + 0.03, cy - 0.03, cy + 0.03, z - 0.6, z + 0.55, 2)
    # The glow: crossed cards through the lamp.
    r = 1.7
    cy = y - 0.25
    grid(bm, (x - r, cy, z - r), (2 * r, 0, 0), (0, 0, 2 * r), 1, 1, 4)
    grid(bm, (x, cy + r, z - r), (0, -2 * r, 0), (0, 0, 2 * r), 1, 1, 4)
    # And on the face behind it.
    grid(bm, (x - 2.6, PIL_Y - 0.03, z - 2.6), (5.2, 0, 0), (0, 0, 5.2), 1, 1, 4)
    # The tanks' green on its sides: on the flat of them only, above the foot and behind the chamfer.
    gx = PIL_HW + 0.03
    gy0, gy1, gz0, gz1 = PIL_Y + 0.85, wall_y, 3.2, H
    grid(bm, (-gx, gy1, gz0), (0, gy0 - gy1, 0), (0, 0, gz1 - gz0), 1, 1, 6)
    grid(bm, (gx, gy0, gz0), (0, gy1 - gy0, 0), (0, 0, gz1 - gz0), 1, 1, 6)
    me = done(name, bm, mats, {0: WALL_UV, 7: WALL_UV, 1: GRILLE_UV},
              [((x, y - 0.3, z), (1.0, 0.06, 0.03), 2.2, 2.4), ((x, 8.0, 2.0), (0.3, 0.95, 0.35), 4.0, 0.25),
               ((0, 3.7, H - 1), (0.95, 1, 0.93), 9.0, 0.4)], (0.5, 0.51, 0.49))
    unit_uvs(me, (4,))
    # (The green's a crop of the round glow, centred on the tank's height and side.)
    uv = me.uv_layers['UVMap']
    for poly in me.polygons:
        if poly.material_index == 6:
            for li in poly.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                uv.data[li].uv = (0.5 + (co.y - 12.2) / 12.0, 0.5 + (co.z - 6.3) / 10.0)
    return me


# The ceiling's fixtures: B bright, X blown, V a black vent, G a grille, . nothing. Columns: y = +3.7, -3.7, +8.4, -8.4.
CEIL_VARIANTS = {
    'A': (('B', 'V', 'G', 'X'), ('B', 'G', 'V', 'V')),
    'B': (('B', 'X', 'V', 'V'), ('B', 'V', '.', 'B')),
    'C': (('X', 'V', 'V', 'G'), ('B', 'B', 'G', 'V')),
    'D': (('B', 'G', 'V', 'X'), ('B', 'V', 'V', 'B')),
}
COLS = (3.7, -3.7, 8.4, -8.4)
PANEL = 3.7


def fixture(bm, kind, x, y, z, SL):
    """A ceiling fixture on the plane at z, facing down. SL: slots (light, broken, dark, steel, grille)."""
    h = PANEL / 2
    def down(xa, xb, ya, yb, zz, mat):
        grid(bm, (xa, ya, zz), (0, yb - ya, 0), (xb - xa, 0, 0), 1, 1, mat)
    if kind == 'G':
        down(x - 1.3, x + 1.3, y - 0.9, y + 0.9, z - 0.03, SL[4])
        return
    down(x - h, x + h, y - h, y + h, z - 0.03, SL[2] if kind != 'V' else SL[3])
    mat = {'B': SL[0], 'X': SL[1], 'V': SL[2]}[kind]
    gap = 0.08
    for ax in (0, 1):
        for ay in (0, 1):
            xa = x - h + 0.12 if ax == 0 else x + gap
            xb = x - gap if ax == 0 else x + h - 0.12
            ya = y - h + 0.12 if ay == 0 else y + gap
            yb = y - gap if ay == 0 else y + h - 0.12
            down(xa, xb, ya, yb, z - 0.06, mat)


def ceiling(name, rows_x, layout, x0, x1, z=None, rib=True):
    """The tiled band across the corridor from x0 to x1 and its fixtures, with the lit tile baked round the bright ones."""
    kit = _kit
    H = z if z is not None else kit.LAB['height']
    mats = [_M['ceil'], kit.MAT['light'], _M['broken'], kit.MAT['dark'], kit.MAT['steel'], _M['grille'], _M['wash_white'], _M['halo']]
    SL = (1, 2, 3, 4, 5)
    bm = bmesh.new()
    nx, ny = max(2, round((x1 - x0) / 2.25)), 11
    grid(bm, (x0, -BAND, H), (0, 2 * BAND, 0), (x1 - x0, 0, 0), ny, nx, 0)
    lights = []
    for x, row in zip(rows_x, layout):
        for y, kind in zip(COLS, row):
            if kind == '.':
                continue
            fixture(bm, kind, x, y, H, SL)
            if kind in 'BX':
                lights.append(((x, y, H - 1.8), (1.0, 1.0, 0.95), 3.4, 1.0 if kind == 'B' else 0.5))
                r = 6.2 if kind == 'B' else 3.8
                ya, yb = max(y - r, -BAND + 0.05), min(y + r, BAND - 0.05)
                grid(bm, (x - r, ya, H - 0.02), (0, yb - ya, 0), (2 * r, 0, 0), 1, 1, 6)
    if rib:
        # The cross rib, on the bay's joint, dropping below the tile.
        box(bm, x1 - 0.6, x1 + 0.6, -BAND, BAND, H - 0.5, H, 0)
    for sx in (-9.0, 9.0):
        for sy in (-1, 1):
            if x0 - 2 <= sx <= x1 + 2:
                lights.append(((sx, sy * 10.0, LAMP[2]), (1.0, 0.06, 0.03), 4.0, 0.9))
                # The lamp's red, thrown up on the tile's edge.
                ya, yb = sorted((sy * 11.45, sy * 7.0))
                grid(bm, (sx - 3.2, ya, H - 0.025), (0, yb - ya, 0), (6.4, 0, 0), 1, 1, 7)
    me = done(name, bm, mats, {0: WALL_UV_CEIL, 2: BROKEN_UV, 5: GRILLE_UV}, lights, (0.55, 0.56, 0.53))
    unit_uvs(me, (6, 7))
    return me


def cables(name):
    """The black bundles of a bay's side: down from the channel by each pilaster, sagging clear of the glass and up into
    the tank's top collar, with a few straight drops from the ceiling onto its top."""
    kit = _kit
    bm = bmesh.new()
    H = kit.LAB['height']
    top = H + CHANNEL - 0.3
    tank_y = kit.LAB['tank_y']
    collar = 3.4   # just inside the collar's radius
    in_z = 9.2     # the height they enter it at
    spec = [  # (side, from y, low point's z, angle round the collar in degrees off the road's axis, radius)
        (-1, 12.2, 8.0, -14, 0.24), (-1, 11.8, 7.1, -2, 0.2), (-1, 13.5, 9.2, 16, 0.27),
        (1, 12.0, 7.7, -12, 0.23), (1, 12.8, 6.8, 3, 0.19), (1, 14.0, 9.0, 18, 0.25),
    ]
    for side, y0, low, ang, r in spec:
        a = math.radians(ang)
        end = Vector((side * collar * math.cos(a), tank_y + collar * math.sin(a), in_z))
        start = Vector((side * 6.3, y0, top))
        path = []
        n = 8
        for i in range(n + 1):
            t = i / n
            # Across evenly, its height a curve from the channel down to `low` and back up to the collar.
            x = start.x + (end.x - start.x) * t
            y = start.y + (end.y - start.y) * t
            zl = start.z + (end.z - start.z) * t
            path.append(Vector((x, y, zl - (((start.z + end.z) / 2) - low) * 4 * t * (1 - t))))
        kit.sweep(bm, path, kit.circle_profile(r, 4), mat=0, caps=False)
    for x, y, r in ((-1.4, 11.0, 0.14), (0.3, 10.6, 0.17), (1.6, 11.2, 0.13), (-0.6, 9.9, 0.12)):
        kit.sweep(bm, [Vector((x, y, H)), Vector((x + 0.05, y, H - 0.5)), Vector((x, y, 9.6))], kit.circle_profile(r, 3), mat=0, caps=False)
    me = kit.mesh_from(name, bm, [kit.MAT['cable']], smooth=True, recalc=False)
    kit.box_uvs(me)
    kit.bake_light(me, [], ambient=(1, 1, 1))
    return me


def floor_cards(name):
    """The wet floor's reflections, lying on the walkway: the lamps' red long down the floor below them, the tank's green,
    the strips' white; and the mist round the bay's feet."""
    kit = _kit
    M = _M
    mats = [M['sheen_red'], M['sheen_green'], M['sheen_white'], M['mist']]
    bm = bmesh.new()
    z = FLOOR_Z + 0.015

    def lying(x, y, sx, sy, mat):
        grid(bm, (x - sx / 2, y - sy / 2, z), (sx, 0, 0), (0, sy, 0), 1, 1, mat)
    for x in (-9.0, 9.0):
        lying(x, 7.9, 8.0, 2.5, 0)
    lying(0.0, 7.5, 11.0, 2.8, 1)
    for x in (-4.85, 4.85):
        lying(x, 8.0, 4.0, 1.0, 2)
    me = kit.mesh_from(name, bm, mats, recalc=False)
    unit_uvs(me, (0, 1, 2), swap=True)
    return me


def mist_card(name):
    """Mist: a few crossed soft cards at a bay's foot."""
    kit = _kit
    bm = bmesh.new()
    cards = [((-5.0, 8.4), (0.9, 5.2), 2.6), ((-4.8, 8.5), (3.4, 1.4), 2.0), ((-6.8, 8.0), (-0.6, 3.8), 1.9)]
    for (x, y), (dx, dy), h in cards:
        grid(bm, (x - dx / 2, y - dy / 2, FLOOR_Z), (dx, dy, 0), (0, 0, h), 1, 1, 0)
    me = kit.mesh_from(name, bm, [_M['mist']], recalc=False)
    unit_uvs(me, (0,))
    return me


def door_leaf(side):
    """One leaf (its origin on the road's centreline at the door's s, 0..7 m along +y for the left, -y for the right; its
    face toward the rider, -x): grey plate, raised panels, a hazard band, the seam."""
    kit = _kit
    M = _M
    mats = [M['door'], kit.MAT['hazard'], kit.MAT['dark'], M['frame']]
    bm = bmesh.new()
    y0, y1 = (0.02, 7.1) if side > 0 else (-7.1, -0.02)
    t = 0.4
    # The plate (its face diced for the red over it).
    grid(bm, (-t, y0, 0), (0, y1 - y0, 0), (0, 0, 8.2), 4, 4, 0)
    box(bm, -t + 0.01, 0, y0, y1, 0, 8.2, 3)
    # Raised panels, above and below the hazard band.
    py0, py1 = (0.5, 6.4) if side > 0 else (-6.4, -0.5)
    box(bm, -t - 0.09, -t, py0, py1, 3.6, 7.6, 0)
    box(bm, -t - 0.09, -t, py0, py1, 0.35, 1.3, 0)
    # A vertical stiffener at the seam, dark gaps across.
    sy0, sy1 = (0.02, 0.32) if side > 0 else (-0.32, -0.02)
    box(bm, -t - 0.13, -t, sy0, sy1, 0, 8.2, 3)
    # The hazard band, with its dark diagonals.
    hz0, hz1 = 1.7, 3.0
    grid(bm, (-t - 0.05, py0, hz0), (0, py1 - py0, 0), (0, 0, hz1 - hz0), 1, 1, 1)
    for zs in (1.46, 3.2, 3.52, 7.6, 1.3, 0.28):
        grid(bm, (-t - 0.1, py0 - 0.07, zs), (0, py1 - py0 + 0.14, 0), (0, 0, 0.08), 1, 1, 2)
    for ya in (py0 - 0.07, py1):
        grid(bm, (-t - 0.1, ya, 3.52), (0, 0.07, 0), (0, 0, 4.16), 1, 1, 2)
    w = 0.55
    y = py0 + 0.1
    while y + w + (hz1 - hz0) <= py1:
        add = [(y, hz0), (y + w, hz0), (y + w + hz1 - hz0, hz1), (y + hz1 - hz0, hz1)]
        kit.add_quad(bm, [(-t - 0.065, a, b) for a, b in add], 2)
        y += 2 * w + 0.2
    return done(f'LabDoor{"L" if side > 0 else "R"}', bm, mats, {0: (1 / 8.0, 1 / 8.0)},
                [((-1.5, 0.0, 8.5), (1.0, 0.1, 0.06), 3.5, 1.0), ((-8, 4 * side, 12), (0.95, 1, 0.93), 12.0, 0.8)], (0.5, 0.51, 0.5))


def end_wall():
    """The bulkhead (its face at END_FACE): white tile, a chamfered door surround, the control room's window above with its
    teal monitors and chair backs, red lamps and strip, the pockets the leaves slide into, the dark frame on to s 670."""
    kit = _kit
    M = _M
    L = kit.LAB
    H = L['height']
    wy = L['wall_y']
    top = H + CHANNEL
    mats = [M['wall'], M['frame'], kit.MAT['dark'], M['lamp'], M['teal'], M['monitor'], kit.MAT['glass'], kit.MAT['hazard'], M['halo'], kit.MAT['steel']]
    bm = bmesh.new()
    X = END_FACE
    D = L['door_s']
    win_hw, win0, win1 = 10.4, 9.5, 13.5

    def face(y0, y1, z0, z1, nu=1, nv=1, x=X, mat=0):
        grid(bm, (x, y1, z0), (0, y0 - y1, 0), (0, 0, z1 - z0), nu, nv, mat)   # facing -x
    # The wall round the door and the window.
    for s in (-1, 1):
        a, b = sorted((s * 8.2, s * wy))
        face(a, b, 0, win0, 5, 5)
        a, b = sorted((s * win_hw, s * wy))
        face(a, b, win0, top, 4, 1)
        a, b = sorted((s * win_hw, s * BAND))
        face(a, b, top, LIFT_Z, 1, 2)
    face(-8.2, 8.2, 8.9, win0, 8, 1)
    face(-BAND, BAND, win1, LIFT_Z, 12, 1)
    # Heavy panels either side of the door, standing proud.
    for s in (-1, 1):
        a, b = sorted((s * 9.0, s * 12.8))
        box(bm, X - 0.35, X, a, b, 0, 8.6, 0)
    # The door's surround: jambs, a head, the opening's top corners chamfered off.
    for s_ in (-1, 1):
        a, b = sorted((s_ * 7.0, s_ * 8.2))
        box(bm, X - 0.5, X + 0.45, a, b, 0, 8.0, 1)
        corner = [(X - 0.46, s_ * 7.0, 6.9), (X - 0.46, s_ * 7.0, 8.0), (X - 0.46, s_ * 5.9, 8.0)]
        kit.add_quad(bm, corner if s_ < 0 else corner[::-1], 1)
    box(bm, X - 0.5, X + 0.45, -8.2, 8.2, 8.0, 8.95, 1)
    # Hazard stripes on the jambs' feet.
    for s in (-1, 1):
        a, b = sorted((s * 7.25, s * 7.95))
        grid(bm, (X - 0.52, b, 0.3), (0, a - b, 0), (0, 0, 2.9), 1, 1, 7)
        for k in range(4):
            z = 0.55 + k * 0.7
            kit.add_quad(bm, [(X - 0.53, b, z), (X - 0.53, a, z + 0.28), (X - 0.53, a, z + 0.6), (X - 0.53, b, z + 0.32)], 2)
    # The red strip over the door, and the lamps either side.
    box(bm, X - 0.62, X - 0.45, -4.6, 4.6, 8.35, 8.62, 3)
    for s in (-1, 1):
        a, b = sorted((s * 8.45, s * 8.95))
        box(bm, X - 0.3, X, a, b, 4.9, 6.9, 3)
        y = s * 8.7
        grid(bm, (X - 0.33, y + 2.0, 3.9), (0, -4.0, 0), (0, 0, 4.0), 1, 1, 8)
    # A control box on the panel to the door's right, a light on it.
    box(bm, X - 0.55, X - 0.35, -11.0, -9.8, 3.1, 5.1, 1)
    grid(bm, (X - 0.56, -10.1, 4.5), (0, -0.6, 0), (0, 0, 0.3), 1, 1, 3)
    # The window: reveal, frame, mullions, glass.
    for (y0, y1, z0, z1) in [(-win_hw - 0.3, win_hw + 0.3, win0 - 0.3, win0), (-win_hw - 0.3, win_hw + 0.3, win1, win1 + 0.3),
                             (-win_hw - 0.3, -win_hw, win0, win1), (win_hw, win_hw + 0.3, win0, win1)]:
        box(bm, X - 0.18, X + 1.2, y0, y1, z0, z1, 1)
    for y in kit.frange(-win_hw + 3.5, win_hw - 3.4, 3.47):
        box(bm, X + 0.02, X + 0.14, y - 0.07, y + 0.07, win0, win1, 2)
    box(bm, X + 0.02, X + 0.14, -win_hw, win_hw, win1 - 0.75, win1 - 0.65, 2)
    grid(bm, (X + 0.16, win_hw, win0), (0, -2 * win_hw, 0), (0, 0, win1 - win0), 1, 1, 6)
    # The room: teal back wall, ceiling strip, desks, monitors, chairs in silhouette.
    back = X + 4.6
    grid(bm, (back, win_hw, win0), (0, -2 * win_hw, 0), (0, 0, win1 - win0), 1, 1, 4)
    grid(bm, (X + 1.2, win_hw, win1), (0, -2 * win_hw, 0), (back - X - 1.2, 0, 0), 1, 1, 2)
    box(bm, back - 1.9, back - 0.9, -win_hw, win_hw, win0, win0 + 1.05, 2)
    for y in kit.frange(-win_hw + 1.5, win_hw - 1.4, 2.6):
        grid(bm, (back - 1.3, y + 0.85, win0 + 1.2), (0, -1.7, 0), (0, 0, 1.1), 1, 1, 5)
    for y in kit.frange(-win_hw + 2.8, win_hw - 2.7, 5.2):
        # A chair's back and its seat and post, flat, against the light.
        grid(bm, (X + 1.9, y + 0.45, win0 + 1.05), (0, -0.9, 0), (0, 0, 1.1), 1, 1, 2)
        grid(bm, (X + 1.9, y + 0.55, win0 + 0.8), (0, -1.1, 0), (0, 0, 0.2), 1, 1, 2)
        grid(bm, (X + 1.9, y + 0.09, win0), (0, -0.18, 0), (0, 0, 0.8), 1, 1, 2)
    # Behind the face: the pockets the leaves slide into, the dark frame to s 670.
    PB = D + 0.2
    for s in (-1, 1):
        a, b = sorted((s * 7.0, s * 15.6))
        box(bm, PB, PB + 0.3, a, b, 0, 9.3, 2)
        a, b = sorted((s * 7.25, s * 7.75))
        box(bm, PB, _kit.LAB['door_s'] + 8.0, a, b, 0, 9.3, 2)
        a, b = sorted((s * ROAD_EDGE, s * 7.3))
        box(bm, X - 0.5, _kit.LAB['door_s'] + 8.0, a, b, -0.3, FLOOR_Z, 2)
    box(bm, PB, _kit.LAB['door_s'] + 8.0, -7.75, 7.75, 8.6, 9.3, 2)
    lights = [((X - 2.0, 0.0, 8.4), (1.0, 0.1, 0.05), 3.5, 1.1)]
    for s in (-1, 1):
        lights.append(((X - 1.0, s * 8.7, 5.9), (1.0, 0.08, 0.04), 3.0, 1.6))
    lights.append(((X - 6, 0.0, LIFT_Z - 1.5), (0.95, 1, 0.93), 11.0, 0.9))
    lights.append(((X - 6, 8.4, H - 1.5), (0.95, 1, 0.93), 7.0, 0.35))
    lights.append(((X - 6, -8.4, H - 1.5), (0.95, 1, 0.93), 7.0, 0.35))
    lights.append(((X - 1, 0.0, win0 + 1.5), (0.1, 0.65, 0.6), 7.0, 0.4))
    me = kit.mesh_from('LabEndWall', bm, mats, recalc=False)
    uv_by(me, {0: WALL_UV})
    unit_uvs(me, (8,))
    kit.bake_light(me, lights, ambient=(0.6, 0.61, 0.58))
    return me


def lift_shell():
    """The tall stretch before the end wall: the band's walls carried up to the raised ceiling, the step at its start."""
    kit = _kit
    H = kit.LAB['height']
    bm = bmesh.new()
    length = END_FACE - LIFT_S
    for s in (-1, 1):
        if s > 0:
            grid(bm, (END_FACE, BAND, H - 0.3), (-length, 0, 0), (0, 0, LIFT_Z - H + 0.3), 9, 3, 0)
        else:
            grid(bm, (LIFT_S, -BAND, H - 0.3), (length, 0, 0), (0, 0, LIFT_Z - H + 0.3), 9, 3, 0)
    grid(bm, (LIFT_S, BAND, H - 0.3), (0, -2 * BAND, 0), (0, 0, LIFT_Z - H + 0.3), 8, 2, 0)
    lights = []
    for x in (_kit.LAB['door_s'] - 22.0, _kit.LAB['door_s'] - 10.0):
        for y in (-3.7, 3.7):
            lights.append(((x, y, LIFT_Z - 1.5), (1, 1, 0.95), 5.0, 0.8))
    for s in (-1, 1):
        lights.append(((_kit.LAB['door_s'] - 15.0, s * 10.0, LAMP[2]), (1.0, 0.06, 0.03), 4.0, 0.7))
    return done('LabLift', bm, [_M['wall']], {0: WALL_UV}, lights, (0.33, 0.34, 0.32))


def start_wall():
    """The bulkhead at s 150, wall to wall, round the gate's 16 x 9 m opening (the gate's own frame closes the rest on its
    side); it faces into the lab, and from the gate only its opening shows."""
    kit = _kit
    L = kit.LAB
    wy = L['wall_y']
    top = L['height'] + CHANNEL
    S = kit.SECTIONS['lab'][0]
    hw, ho = 8.0, 9.0
    bm = bmesh.new()
    for s in (-1, 1):
        y0, y1 = sorted((s * hw, s * wy))
        grid(bm, (S, y0, 0), (0, y1 - y0, 0), (0, 0, top), 3, 3, 0)
    grid(bm, (S, -hw, ho), (0, 2 * hw, 0), (0, 0, top - ho), 6, 1, 0)
    return done('LabStartWall', bm, [_M['wall']], {0: WALL_UV}, [], (0.5, 0.51, 0.49))


# --- The module's two entry points. ----------------------------------------------------------------------------------
def build(kit):
    global _kit
    _kit = kit
    _materials(kit)
    H = kit.LAB['height']
    p = {}
    p['shell'] = kit.piece('LabBayShell', side_shell('LabBayShell', -9.0, 9.0, H))
    p['pilaster'] = kit.piece('LabPilaster', pilaster('LabPilaster'))
    p['cables'] = kit.piece('LabCables', cables('LabCables'))
    p['floor'] = kit.piece('LabFloorCards', floor_cards('LabFloorCards'))
    p['mist'] = kit.piece('LabMistCards', mist_card('LabMistCards'))
    for k, layout in CEIL_VARIANTS.items():
        p[f'ceil{k}'] = kit.piece(f'LabCeil{k}', ceiling(f'LabCeil{k}', (-4.5, 4.5), layout, -9.0, 9.0))
    return p


def place(kit, pieces):
    L = kit.LAB
    S0 = kit.SECTIONS['lab'][0]
    H = L['height']
    D = L['door_s']
    first_tank = L['tank_from']
    every = L['tank_every']
    tanks = tank_s(kit)
    grp = 'Lab'
    order = 'ABCADBACDB'
    for i, s in enumerate(tanks):
        at = kit.along(s)
        for yaw in (0.0, math.pi):
            kit.put(pieces['shell'], at, yaw=yaw, grp=grp)
            kit.put(pieces['cables'], at, yaw=yaw, grp=grp)
            kit.put(pieces['floor'], at, yaw=yaw, grp=grp)
        # Mist at each bay's foot, on one side or the other, now and then both.
        kit.put(pieces['mist'], at, yaw=0.0 if i % 2 == 0 else math.pi, grp=grp)
        if i % 3 == 0:
            kit.put(pieces['mist'], at, yaw=math.pi if i % 2 == 0 else 0.0, grp=grp)
        if s + 9.0 <= LIFT_S:
            kit.put(pieces[f'ceil{order[i % len(order)]}'], at, grp=grp)
    # The pilasters, at the joints: one before the first tank's bay, one after each (but the last: its bay runs on through
    # the end wall, its far part hidden behind it).
    joints = [first_tank - every / 2] + [s + every / 2 for s in tanks if s + every / 2 < END_FACE]
    for s in joints:
        at = kit.along(s)
        kit.put(pieces['pilaster'], at, grp=grp)
        kit.put(pieces['pilaster'], at, yaw=math.pi, grp=grp)
    # The short stretch from the gate to the first bay, one-off, both sides.
    first_joint = joints[0]
    me = side_shell('LabShellStart', -(first_joint - S0) / 2, (first_joint - S0) / 2, H, tank=False)
    mid = (S0 + first_joint) / 2
    kit.static('LabShellStartL', me, grp=grp, loc=kit.along(mid))
    o = kit.static('LabShellStartR', me, grp=grp, loc=kit.along(mid))
    o.rotation_euler = (0, 0, math.pi)
    # The ceiling over the start.
    me = ceiling('LabCeilStart', (-1.5,), [('B', 'V', 'V', 'G')], -(first_joint - S0) / 2, (first_joint - S0) / 2)
    kit.static('LabCeilStart', me, grp=grp, loc=kit.along((S0 + first_joint) / 2))
    # The raised ceiling up to the end wall.
    mid = (LIFT_S + END_FACE) / 2
    half = (END_FACE - LIFT_S) / 2
    me = ceiling('LabCeilLift', (_kit.LAB['door_s'] - 22.0 - mid, _kit.LAB['door_s'] - 10.0 - mid), [('B', 'B', 'V', 'X'), ('B', 'V', 'G', 'B')], -half, half, z=LIFT_Z, rib=False)
    kit.static('LabCeilLift', me, grp=grp, loc=kit.along(mid))
    kit.static('LabLift', lift_shell(), grp=grp)
    kit.static('LabEndWall', end_wall(), grp=grp)
    kit.static('LabStartWall', start_wall(), grp=grp)
    # The door's leaves, at the door's s.
    door = kit.along(D)
    kit.static('LabDoorL', door_leaf(1), grp='LabDoor', loc=door)
    kit.static('LabDoorR', door_leaf(-1), grp='LabDoor', loc=door)
    if any('preview.py' in a for a in sys.argv):
        report(kit)
        _preview_deck(kit)


def report(kit):
    import bpy
    total = 0
    uses = {}
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.users_scene and o.name != 'PreviewDeck' and 'Lab' in o.data.name:
            t = kit.tris(o.data)
            total += t
            n = uses.setdefault(o.data.name, [0, t])
            n[0] += 1
    for k, (c, t) in sorted(uses.items(), key=lambda kv: -kv[1][0] * kv[1][1]):
        print(f'  {k}: {c} x {t} = {c * t}')
    print('LAB TRIS DRAWN', total)


def _preview_deck(kit):
    """Preview only (never in the city's build): a stand-in for the road's deck and dashes, built elsewhere, so the shot reads."""
    import bpy
    bm = bmesh.new()
    S0, S1 = kit.SECTIONS['lab']
    grid(bm, (S0, -ROAD_EDGE, 0), (S1 - S0, 0, 0), (0, 2 * ROAD_EDGE, 0), 1, 1, 0)
    for s in kit.frange(S0, S1, 9.0):
        grid(bm, (s, -0.1, 0.01), (3.0, 0, 0), (0, 0.2, 0), 1, 1, 1)
    m = kit.material('PreviewDeck', (0.025, 0.027, 0.026), 0.05, vcol=False, spec=1.0)
    d = kit.material('PreviewDash', (0.7, 0.7, 0.68), 0.4, vcol=False, emission=(0.6, 0.6, 0.58), strength=0.7)
    me = kit.mesh_from('PreviewDeck', bm, [m, d], recalc=False)
    o = bpy.data.objects.new('PreviewDeck', me)
    bpy.context.scene.collection.objects.link(o)
    bpy.context.scene.eevee.use_raytracing = True
