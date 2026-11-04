"""The vault tunnel on from the desert's gate (s 0-150, concept-core-gate): an octagonal concrete vault 16 m wide and 11 m
tall, repeated bay by bay (instances): ribs, ceiling pipes and light panels, cable trays, wall lamps, kerbs with green
lights. Sand blown in beside the road thins to nothing by s 60. A bulkhead at s 146-150 closes the gap round a 16 x 9 m
opening into the lab's end wall. art/build-city4.py's tunnel ends at this section's s 0 with the same PROFILE.

The deck is built elsewhere; gate.lights() gives the lamps in the city's frame, for kit.bake_light on it."""
import math
import random
import sys

import bmesh
from mathutils import Vector

HALF_W, HEIGHT, EAVE, CROWN = 8.0, 11.0, 7.4, 5.4
PROFILE = [(-HALF_W, -0.4), (-HALF_W, EAVE), (-CROWN, HEIGHT), (CROWN, HEIGHT), (HALF_W, EAVE), (HALF_W, -0.4)]
END_S = 146.0                # where the bays stop and the bulkhead starts
N_BAYS = 12
BAY = END_S / N_BAYS
RIB_W = 2.2
PANEL_X = RIB_W + (BAY - RIB_W) / 2   # a ceiling panel mid-bay
PANEL_Z = 9.5
LAMP_Z = 5.4
RIB_PROUD = (0.85, 1.3)
SAND_END = 60.0
KERB_LEDS = (5.3, 9.4)
OPEN_HALF, OPEN_H = 8.0, 9.0  # the opening in the bulkhead
BH_HALF, BH_TOP = 17.6, 11.8  # the bulkhead's outline (past the lab's 34 x 10.5)

GREEN = (0.3, 1.0, 0.38)
PANEL_GREEN = (0.6, 1.0, 0.66)
WARM = (1.0, 0.6, 0.28)       # daylight from the gate, reaching the first bays
AMBIENT = (0.03, 0.045, 0.035)
RIB_AMBIENT = (0.085, 0.11, 0.09)

SHOTS = {
    'entry': ((1.0, -1.6, 1.5), (40.0, -1.0, 2.6), 80),
    'mid': ((64.0, -1.6, 1.5), (110.0, -1.0, 2.8), 80),
    'end': ((122.0, -1.6, 1.5), (150.0, -0.6, 3.6), 80),
    'back': ((92.0, 1.6, 1.5), (40.0, 1.0, 2.6), 80),
    'lab': ((176.0, 2.0, 1.8), (146.0, 0.0, 4.6), 80),
    'wide': ((30.0, -6.0, 8.0), (80.0, 2.0, 3.0), 70),
}


def _lamps_at(x):
    """A bay's lamps, x being its start."""
    out = [((x + PANEL_X, 0.0, PANEL_Z - 0.5), PANEL_GREEN, 4.6, 1.5)]
    for side in (1, -1):
        out.append(((x + RIB_W / 2, side * 6.35, LAMP_Z), GREEN, 2.0, 1.0))
        out.append(((x + PANEL_X, side * 7.4, 2.5), GREEN, 1.5, 0.6))
        for kx in KERB_LEDS:
            out.append(((x + kx, side * 5.7, 0.5), GREEN, 1.1, 0.55))
    return out


def _bay_lights(extra=()):
    """The lamps of a bay and its neighbours, in the bay's frame."""
    out = list(extra)
    for j in range(-2, 3):
        x = j * BAY
        out += _lamps_at(x)
    return out


def lights(kit=None):
    """Every lamp of the section, in the city's frame: ((x, y, z), colour, radius, power), for kit.bake_light."""
    out = []
    for i in range(N_BAYS):
        out += _lamps_at(i * BAY)
    out.append(((END_S - 1.0, 0.0, 9.6), PANEL_GREEN, 5.0, 1.0))
    out.append(((END_S + 6.0, 0.0, 4.5), (0.85, 1.0, 0.85), 6.0, 1.3))
    return out


def _inward(bm):
    """Turns a shell's faces to look at the vault's axis."""
    for f in bm.faces:
        c = f.calc_center_median()
        if f.normal.dot(Vector((0, -c.y, 5.0 - c.z))) < 0:
            f.normal_flip()


def _shell(kit, mat, light_list):
    """A bay's concrete: walls, chamfers, roof, the floor strips beside the deck. One-sided layers facing in."""
    bm = bmesh.new()
    for (y0, z0), (y1, z1) in zip(PROFILE, PROFILE[1:]):
        kit.add_quad(bm, [(0, y0, z0), (BAY, y0, z0), (BAY, y1, z1), (0, y1, z1)])
    for side in (1, -1):
        kit.add_quad(bm, [(0, side * 5.85, -0.02), (BAY, side * 5.85, -0.02), (BAY, side * HALF_W, -0.02), (0, side * HALF_W, -0.02)])
    kit.dice(bm, 1.6)
    bm.normal_update()
    _inward(bm)
    me = kit.mesh_from('GateShell', bm, mat, recalc=False)
    kit.box_uvs(me, 0.22)
    kit.bake_light(me, light_list, ambient=AMBIENT)
    return me


def _offset_profile(p):
    """The vault's outline moved p metres in (the chamfer keeps its slope)."""
    h, e, c = HALF_W - p, EAVE - 0.322 * p, CROWN - 0.51 * p
    return [(-h, -0.2), (-h, e), (-c, HEIGHT - p), (c, HEIGHT - p), (h, e), (h, -0.2)]


def _ribs(kit, mat, light_list):
    """The frame at the bay's start: two stepped layers of concrete, a plinth each side."""
    bm = bmesh.new()
    for proud, x0, x1 in ((RIB_PROUD[0], 0.0, RIB_W), (RIB_PROUD[1], 0.45, RIB_W - 0.45)):
        outer, inner = PROFILE, _offset_profile(proud)
        for a in range(len(PROFILE) - 1):
            q = [outer[a], outer[a + 1], inner[a + 1], inner[a]]
            v0 = [bm.verts.new((x0, y, z)) for y, z in q]
            v1 = [bm.verts.new((x1, y, z)) for y, z in q]
            for i in range(4):
                j = (i + 1) % 4
                bm.faces.new((v0[i], v0[j], v1[j], v1[i]))
            bm.faces.new(v0)
            bm.faces.new(list(reversed(v1)))
    for side in (1, -1):
        kit.add_box(bm, (RIB_W / 2, side * 7.25, 1.4), (RIB_W + 1.0, 1.6, 2.8))
    kit.dice(bm, 1.9)
    me = kit.mesh_from('GateRibs', bm, mat)
    kit.box_uvs(me, 0.22)
    kit.bake_light(me, light_list, ambient=RIB_AMBIENT)
    return me


def _kerbs(kit, mat, light_list):
    """Low concrete kerbs between the ribs, in two blocks a side."""
    bm = bmesh.new()
    x0, x1 = RIB_W + 0.4, BAY - 0.4
    mid = (x0 + x1) / 2
    for side in (1, -1):
        for a, b in ((x0, mid - 0.1), (mid + 0.1, x1)):
            kit.add_box(bm, ((a + b) / 2, side * 6.58, 0.42), (b - a, 1.06, 0.84))
            kit.add_box(bm, ((a + b) / 2, side * 6.62, 0.91), (b - a + 0.1, 1.2, 0.14))
    kit.dice(bm, 2.4)
    me = kit.mesh_from('GateKerbs', bm, mat)
    kit.box_uvs(me, 0.3)
    kit.bake_light(me, light_list, ambient=RIB_AMBIENT)
    return me


PIPES = [(y, 9.45 - 0.16 * k, r) for k, (y, r) in enumerate(((2.65, 0.2), (3.3, 0.15), (3.85, 0.24), (4.55, 0.15)))]


def _pipes(kit, mat, light_list):
    """The ceiling's pipes, in two bundles, and the big conduits on the chamfers; they run on through every bay."""
    bm = bmesh.new()
    xs = [Vector((BAY * t / 3, 0, 0)) for t in range(4)]
    for side in (1, -1):
        for y, z, r in PIPES:
            kit.sweep(bm, [p + Vector((0, side * y, z)) for p in xs], kit.circle_profile(r, 6), caps=False)
        kit.sweep(bm, [p + Vector((0, side * 6.3, 8.1)) for p in xs], kit.circle_profile(0.3, 6), caps=False)
        for y, z, r in PIPES:  # a collar and a hanger at the rib
            kit.add_box(bm, (RIB_W / 2, side * y, z), (0.3, 2.3 * r + 0.1, 2.3 * r + 0.1))
        kit.add_box(bm, (RIB_W / 2, side * 3.6, 9.72), (0.3, 2.7, 0.14))
    me = kit.mesh_from('GatePipes', bm, mat, recalc=False)
    kit.bake_light(me, light_list, ambient=AMBIENT)
    return me


def _fittings(kit, mat, light_list):
    """Dark housings: the panels' frames, lamp boxes, the cable trays along the walls."""
    bm = bmesh.new()
    kit.add_box(bm, (PANEL_X, 0, PANEL_Z + 0.16), (3.0, 3.8, 0.3))
    for yy in (-1.5, 1.5):  # its drop rods
        kit.add_box(bm, (PANEL_X, yy, (PANEL_Z + HEIGHT) / 2), (0.14, 0.14, HEIGHT - PANEL_Z))
    for side in (1, -1):
        kit.add_box(bm, (RIB_W / 2, side * 6.62, LAMP_Z), (1.5, 0.16, 0.75))
        kit.add_box(bm, (PANEL_X, side * 7.88, 2.5), (0.9, 0.22, 0.42))
        for z in (6.3,):  # the tray: a floor and a lip
            kit.add_box(bm, (BAY / 2, side * 7.42, z), (BAY, 1.12, 0.07))
            kit.add_box(bm, (BAY / 2, side * 6.88, z + 0.1), (BAY, 0.05, 0.22))
        for kx in KERB_LEDS:
            kit.add_box(bm, (kx, side * 6.03, 0.45), (1.75, 0.05, 0.42))
    kit.dice(bm, 3.1)
    me = kit.mesh_from('GateFittings', bm, mat)
    kit.bake_light(me, light_list, ambient=AMBIENT)
    return me


def _cables(kit, mat, light_list):
    """Cables in the trays and a bunch down each wall behind the plinth."""
    bm = bmesh.new()
    xs = [Vector((BAY * t / 2, 0, 0)) for t in range(3)]
    for side in (1, -1):
        for y, r in ((7.15, 0.09), (7.42, 0.12), (7.72, 0.1)):
            kit.sweep(bm, [p + Vector((0, side * y, 6.33 + r)) for p in xs], kit.circle_profile(r, 5), caps=False)
    me = kit.mesh_from('GateCables', bm, mat, recalc=False)
    kit.bake_light(me, light_list, ambient=AMBIENT)
    return me


def _panel(kit, mat):
    """The ceiling panel's lit cells: 4 across by 2 along, dark bars between them, the grid the concept has."""
    bm = bmesh.new()
    cw, cl = 0.82, 1.28
    for a in range(4):
        for b in range(2):
            y = (a - 1.5) * 0.9
            x = PANEL_X + (b - 0.5) * 1.36
            z = PANEL_Z
            kit.add_quad(bm, [(x - cl / 2, y - cw / 2, z), (x - cl / 2, y + cw / 2, z), (x + cl / 2, y + cw / 2, z), (x + cl / 2, y - cw / 2, z)])
    return kit.mesh_from('GatePanelCells', bm, mat, recalc=False)


def _leds(kit, mat):
    """The lamps' lit faces: on each rib, low on the wall, and the green strips in the kerbs."""
    bm = bmesh.new()
    for side in (1, -1):
        y = side * 6.53
        kit.add_quad(bm, [(RIB_W / 2 - 0.62, y, LAMP_Z - 0.28), (RIB_W / 2 + 0.62, y, LAMP_Z - 0.28), (RIB_W / 2 + 0.62, y, LAMP_Z + 0.28), (RIB_W / 2 - 0.62, y, LAMP_Z + 0.28)])
        y = side * 7.76
        kit.add_quad(bm, [(PANEL_X - 0.36, y, 2.34), (PANEL_X + 0.36, y, 2.34), (PANEL_X + 0.36, y, 2.66), (PANEL_X - 0.36, y, 2.66)])
        y = side * 6.0
        for kx in KERB_LEDS:
            for z0, z1 in ((0.32, 0.42), (0.48, 0.58)):
                kit.add_quad(bm, [(kx - 0.75, y, z0), (kx + 0.75, y, z0), (kx + 0.75, y, z1), (kx - 0.75, y, z1)])
    return kit.mesh_from('GateLamps', bm, mat, recalc=False)


def _slit(kit, dark, led):
    """A dark server slit let into the wall (+y side, centred on x 0): racks of green pinpoints."""
    bm = bmesh.new()
    kit.add_box(bm, (0, 7.9, 3.8), (2.3, 0.16, 5.2))
    frame = kit.mesh_from('GateSlit', bm, dark)
    kit.bake_light(frame, [((0, 7.0, 4.0), GREEN, 2.5, 0.6)], ambient=AMBIENT)
    bm = bmesh.new()
    rng = random.Random(5)
    for r in range(12):
        z = 1.55 + r * 0.41
        for c in range(7):
            if rng.random() < 0.6:
                x = -0.9 + c * 0.3
                kit.add_quad(bm, [(x - 0.08, 7.8, z - 0.03), (x + 0.08, 7.8, z - 0.03), (x + 0.08, 7.8, z + 0.03), (x - 0.08, 7.8, z + 0.03)])
    return frame, kit.mesh_from('GateSlitLeds', bm, led, recalc=False)


def _sand_height(s, d):
    """Sand beside the road: banked up against the wall, gone by SAND_END; ragged."""
    a = abs(d)
    fall = max(0.0, 1 - s / SAND_END) ** 1.4
    ragged = 0.72 + 0.28 * math.sin(s * 0.42 + (1.0 if d > 0 else 3.1)) * math.sin(s * 0.13 + a)
    t = max(0.0, (a - 5.8) / (HALF_W - 5.8))
    return 0.02 + 0.8 * fall * (ragged if s > 2 else 1.0) * t ** 1.25


def _sand(kit, mat, all_lights):
    """The banks against the walls, and thin flat tongues blown over the deck's edges (z < 0.08, clear of the centre)."""
    bm = bmesh.new()
    ss = kit.frange(0.0, SAND_END, 2.5)
    for side in (1, -1):
        ds = [5.82, 6.2, 6.9, 7.5, HALF_W - 0.02]
        grid = [[bm.verts.new((s, side * d, _sand_height(s, side * d))) for d in ds] for s in ss]
        for i in range(len(ss) - 1):
            for j in range(len(ds) - 1):
                if max(grid[i][j].co.z, grid[i + 1][j].co.z, grid[i][j + 1].co.z, grid[i + 1][j + 1].co.z) < 0.045:
                    continue
                bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
    rng = random.Random(23)
    # (s, length, reach onto the deck) of each tongue; shorter and thinner further in.
    for side in (1, -1):
        s = 0.0 + (0.0 if side > 0 else 3.5)
        while s < SAND_END - 6:
            fall = 1 - s / SAND_END
            length = rng.uniform(5.0, 11.0) * (0.5 + fall)
            reach = min(3.8, rng.uniform(1.2, 3.6) * (0.35 + fall))
            z = 0.018 + 0.05 * fall * rng.uniform(0.6, 1.0)
            n = 9
            phase = rng.uniform(0, 6.3)
            edge = []
            for i in range(n + 1):
                t = i / n
                w = math.sin(math.pi * t) ** 0.7 * (0.82 + 0.26 * math.sin(i * 1.3 + phase))
                edge.append((s + length * t + 1.6 * w, side * (5.95 - min(reach * w, 4.1))))
            top = [bm.verts.new((sx, dy, z)) for sx, dy in edge]
            root = [bm.verts.new((s + length * i / n, side * 5.95, z * 0.5)) for i in range(n + 1)]
            for i in range(n):
                bm.faces.new((root[i], root[i + 1], top[i + 1], top[i]))
            s += length * rng.uniform(0.75, 1.3)
    me = kit.mesh_from('GateSand', bm, mat, smooth=True, recalc=False)
    for p in me.polygons:
        if p.normal.z < 0:
            p.flip()
    kit.planar_uvs(me, 1 / 8.0)
    kit.bake_light(me, all_lights, ambient=(0.1, 0.1, 0.08))
    return me


def _bulkhead(kit, concrete, steel, hazard, led, panel, all_lights):
    """The frame closing the gap between the tunnel and the lab's end wall at s 146-150, round the opening."""
    bm = bmesh.new()
    x0, x1 = END_S, END_S + 4.0
    xc = (x0 + x1) / 2
    for side in (1, -1):
        kit.add_box(bm, (xc, side * (OPEN_HALF + BH_HALF) / 2, (BH_TOP - 0.4) / 2), (x1 - x0, BH_HALF - OPEN_HALF, BH_TOP + 0.4))
    kit.add_box(bm, (xc, 0, (OPEN_H + BH_TOP) / 2), (x1 - x0, 2 * OPEN_HALF, BH_TOP - OPEN_H))
    kit.dice(bm, 2.0)
    me = kit.mesh_from('GateBulkhead', bm, concrete)
    kit.box_uvs(me, 0.22)
    kit.bake_light(me, all_lights, ambient=AMBIENT)

    bm = bmesh.new()
    t, w = 0.45, 0.9
    for x in (x0 - t / 2, x1 + t / 2):
        kit.add_box(bm, (x, 0, OPEN_H + w / 2), (t, 2 * OPEN_HALF + 2 * w, w))
        for side in (1, -1):
            kit.add_box(bm, (x, side * (OPEN_HALF + w / 2), OPEN_H / 2), (t, w, OPEN_H))
    for side in (1, -1):  # brackets round the collar, big readable blocks
        for z in (1.6, 4.5, 7.4):
            kit.add_box(bm, (x0 - 0.65, side * (OPEN_HALF + 0.55), z), (0.5, 1.5, 1.1))
    for y in (-5.6, 0.0, 5.6):
        kit.add_box(bm, (x0 - 0.65, y, OPEN_H + 0.55), (0.5, 1.2, 1.5))
    kit.add_box(bm, (x0 - 0.1, 0, 10.0), (0.2, 7.8, 0.5))   # the header's backing
    steel_me = kit.mesh_from('GateCollar', bm, steel)
    kit.bake_light(steel_me, all_lights, ambient=AMBIENT)

    bm = bmesh.new()  # hazard stripes up the jambs on the tunnel's side
    for side in (1, -1):
        for k in range(6):
            z = 0.1 + k * 1.5
            y = side * (OPEN_HALF + 0.92)
            for xx in (x0 - 0.46,):
                kit.add_quad(bm, [(xx, y, z), (xx, y - side * 0.92, z + 0.55), (xx, y - side * 0.92, z + 1.1), (xx, y, z + 0.55)])
    hz = kit.mesh_from('GateHazard', bm, hazard, recalc=False)
    kit.bake_light(hz, all_lights, ambient=(0.3, 0.3, 0.25))

    bm = bmesh.new()  # the header strips, the lab's side and the tunnel's
    for x, half in ((x0 - 0.22, 3.6), (x1 + 0.47, 6.5)):
        z = 10.0 if x < xc else OPEN_H + 1.25
        kit.add_quad(bm, [(x, -half, z - 0.14), (x, half, z - 0.14), (x, half, z + 0.14), (x, -half, z + 0.14)])
    for side in (1, -1):
        for z in (2.6, 5.6):
            y = side * (OPEN_HALF + 1.55)
            kit.add_quad(bm, [(x0 - 0.03, y - 0.2, z - 0.42), (x0 - 0.03, y + 0.2, z - 0.42), (x0 - 0.03, y + 0.2, z + 0.42), (x0 - 0.03, y - 0.2, z + 0.42)])
    glow = kit.mesh_from('GateBulkheadLeds', bm, led, recalc=False)
    return me, steel_me, hz, glow


def build(kit):
    con = kit.material(f'{kit.PREFIX}GateConcrete', (0.86, 0.86, 0.8), 0.85, tex='concrete', spec=0.3)
    green = kit.material(f'{kit.PREFIX}GateGreen', (0.12, 0.8, 0.2), 0.4, vcol=False, emission=(0.14, 1.0, 0.22), strength=1.7)
    M = kit.MAT
    every = lights()
    variants = {'': _bay_lights(), 'End': _bay_lights([((BAY + 5.0, 0.0, 4.5), (0.85, 1.0, 0.85), 5.5, 1.5)])}
    for i in range(3):  # the first bays: what daylight reaches in from the gate
        variants[f'Day{i}'] = _bay_lights([((-i * BAY - 9.0, 0.0, 4.0), WARM, 13.0, 1.5)])
    p = {}
    for tag, ll in variants.items():
        p['shell' + tag] = kit.piece('GateShell' + tag, _shell(kit, con, ll))
        p['ribs' + tag] = kit.piece('GateRibs' + tag, _ribs(kit, con, ll))
        p['kerbs' + tag] = kit.piece('GateKerbs' + tag, _kerbs(kit, con, ll))
        p['pipes' + tag] = kit.piece('GatePipes' + tag, _pipes(kit, M['steel'], ll))
        p['fittings' + tag] = kit.piece('GateFittings' + tag, _fittings(kit, M['dark'], ll))
        p['cables' + tag] = kit.piece('GateCables' + tag, _cables(kit, M['cable'], ll))
    p['panel'] = kit.piece('GatePanelCells', _panel(kit, M['light']))
    p['lamps'] = kit.piece('GateLamps', _leds(kit, green))
    slit_f, slit_l = _slit(kit, M['dark'], green)
    p['slit'] = kit.piece('GateSlit', slit_f)
    p['slit_leds'] = kit.piece('GateSlitLeds', slit_l)
    p['sand'] = _sand(kit, M['sand'], every + [((-9.0, 0.0, 4.0), WARM, 16.0, 2.2)])
    p['bulkhead'] = _bulkhead(kit, con, M['steel'], M['hazard'], green, M['light'], every)
    return p


def place(kit, pieces):
    grp = 'Gate'
    for i in range(N_BAYS):
        s = i * BAY
        tag = 'End' if i == N_BAYS - 1 else f'Day{i}' if i < 3 else ''
        for key in ('shell', 'ribs', 'kerbs', 'pipes', 'fittings', 'cables'):
            kit.put(pieces[key + tag], kit.along(s), grp=grp)
        kit.put(pieces['panel'], kit.along(s), grp=grp)
        kit.put(pieces['lamps'], kit.along(s), grp=grp)
        if i % 3 == 1:  # a server slit now and then, in alternate walls
            side = 1 if i % 2 else -1
            yaw = 0.0 if side > 0 else math.pi
            for key in ('slit', 'slit_leds'):
                kit.put(pieces[key], kit.along(s + 4.3), yaw=yaw, grp=grp)
    kit.static('GateSand', pieces['sand'], grp=grp)
    for me in pieces['bulkhead']:
        kit.static(me.name, me, grp=grp)
    if any('preview.py' in a for a in sys.argv):  # (the deck is art/build-city5.py's; a stand-in to judge the shots by)
        bm = bmesh.new()
        kit.add_quad(bm, [(-4, -5.9, -0.005), (154, -5.9, -0.005), (154, 5.9, -0.005), (-4, 5.9, -0.005)])
        kit.dice(bm, 1.5)
        me = kit.mesh_from('PreviewDeck', bm, kit.MAT['asphalt'], recalc=False)
        for poly in me.polygons:
            if poly.normal.z < 0:
                poly.flip()
        uv = me.uv_layers.new(name='UVMap')
        for loop in me.loops:
            co = me.vertices[loop.vertex_index].co
            uv.data[loop.index].uv = ((co.y + 6.0) / 12.0, co.x / 27.0)
        kit.bake_light(me, lights(), ambient=(0.12, 0.13, 0.12))
        kit.static('PreviewDeck', me, grp='Preview')
    import bpy
    gate = bpy.data.objects.get(f'{kit.PREFIX}.{grp}')
    tot = sum(kit.tris(o.data) for o in gate.children if o.type == 'MESH')
    uniq = sum(kit.tris(m) for m in {o.data for o in gate.children if o.type == 'MESH'})
    print(f'gate: {tot} triangles drawn, {uniq} unique')
