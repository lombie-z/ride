"""Grey stand-ins for art/core/ASSETS.md's table, at each asset's size, origin and axes, for art/core/stair.py and flood.py until its glb's
landed. Also what the sections put in that isn't a table asset: the water ribbon, the shaft's glow, the seals.

    A = blockout.pieces(kit)        # a function by name: piece('rail_12') -> assetkit.Piece, the glb's if it's there, else the grey
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

import assetkit

M = {}


def _m(kit):
    if not M:
        M['grey'] = kit.material('City5Blockout', (0.3, 0.31, 0.29), 0.7, vcol=False)
        M['dark'] = kit.material('City5BlockoutDark', (0.06, 0.065, 0.06), 0.7, vcol=False)
        M['hazard'] = kit.material('City5BlockoutHazard', (0.55, 0.42, 0.08), 0.7, vcol=False)
        M['red'] = kit.MAT['red']
        M['green'] = kit.MAT['led']
        M['white'] = kit.MAT['light']
        M['rust'] = kit.material('City5BlockoutRust', (0.3, 0.17, 0.09), 0.6, vcol=False)
    return M


def _mesh(kit, name, bm, mat):
    return kit.mesh_from(name, bm, [mat], recalc=True)


def _boxes(kit, name, boxes, mat='grey'):
    """boxes: (x0, x1, y0, y1, z0, z1)."""
    bm = bmesh.new()
    for x0, x1, y0, y1, z0, z1 in boxes:
        kit.add_box(bm, ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (x1 - x0, y1 - y0, z1 - z0))
    return _mesh(kit, name, bm, _m(kit)[mat])


def _pipe(bm, kit, path, r, n=10):
    kit.sweep(bm, [Vector(p) for p in path], kit.circle_profile(r, n))


def _beam(bm, p0, p1, w, h):
    """A box from p0 to p1, w across, h deep."""
    a, b = Vector(p0), Vector(p1)
    d = b - a
    q = d.to_track_quat('X', 'Z')
    res = bmesh.ops.create_cube(bm, size=1.0)
    mat = Matrix.Translation((a + b) / 2) @ q.to_matrix().to_4x4() @ Matrix.Diagonal((d.length, w, h, 1.0))
    bmesh.ops.transform(bm, matrix=mat, verts=res['verts'])


def _rail(kit, name, drop, length):
    bm = bmesh.new()
    _beam(bm, (0, 0, 1.05), (length, 0, 1.05 - drop), 0.08, 0.08)
    _beam(bm, (0, 0, 0.5), (length, 0, 0.5 - drop), 0.04, 0.04)
    _beam(bm, (0, 0, 0.05), (length, 0, 0.05 - drop), 0.03, 0.45)
    for i in range(int(length // 2) + 1):
        x = min(i * 2.0, length)
        z = -drop * x / length
        _beam(bm, (x, 0, z), (x, 0.0001, z + 1.1), 0.06, 0.06) if False else kit.add_box(bm, (x, 0, z + 0.55), (0.06, 0.06, 1.1))
    return _mesh(kit, name, bm, _m(kit)['grey'])


def _flight(kit, name, steps):
    return _boxes(kit, name, [(i * 1.2, (i + 1) * 1.2, -5.9, 5.9, -0.5 * i - 1.0, -0.5 * i) for i in range(steps)])


def _ramp(kit, name):
    bm = bmesh.new()
    rows = []
    for i in range(25):
        t = i / 24
        s = t * t * (3 - 2 * t)
        a = s * math.pi / 2
        c = Vector((24 * t, -7.6 * s, 7.6 * s))
        y = Vector((0, math.cos(a), math.sin(a)))
        rows.append([bm.verts.new(c + y * 5.9), bm.verts.new(c - y * 5.9)])
    for p, q in zip(rows, rows[1:]):
        bm.faces.new((p[0], p[1], q[1], q[0]))
    return _mesh(kit, name, bm, _m(kit)['grey'])


def _ring(kit, name):
    bm = bmesh.new()
    n = 32
    a = [bm.verts.new((0, 9 * math.sin(2 * math.pi * i / n), 5.5 - 9 * math.cos(2 * math.pi * i / n))) for i in range(n)]
    b = [bm.verts.new((8, 9 * math.sin(2 * math.pi * i / n), 5.5 - 9 * math.cos(2 * math.pi * i / n))) for i in range(n)]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    return kit.mesh_from(name, bm, [_m(kit)['grey']], recalc=False)


def _light(kit, name, w, h, mat):
    bm = bmesh.new()
    kit.add_box(bm, (0, 0.06, 0), (w, 0.12, h))
    return _mesh(kit, name, bm, _m(kit)[mat])


def _frame(kit, name):
    """Round the opening, radius 8.5 to 13, x -8.2 to 1.4."""
    bm = bmesh.new()
    n = 48
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        for ro, ri in ((13.0, 8.5),):
            q = [(ri, a0), (ro, a0), (ro, a1), (ri, a1)]
            bm.faces.new([bm.verts.new((1.4, r * math.cos(a), r * math.sin(a))) for r, a in q])
        q = [(-8.2, a0), (1.4, a0), (1.4, a1), (-8.2, a1)]
        bm.faces.new([bm.verts.new((x, 8.5 * math.cos(a), 8.5 * math.sin(a))) for x, a in q])
    return kit.mesh_from(name, bm, [_m(kit)['rust']], recalc=False)


def _door(kit, name):
    """Hinge at the origin, shut: the disc along +Y to 17.9, centre 9.1, wheel side to -X, 1.6 thick."""
    bm = bmesh.new()
    kit.lathe(bm, [(8.8, -0.8), (8.8, 0.8)], seg=32)
    bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Y'), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0, 9.1, 0), verts=bm.verts)
    kit.add_box(bm, (-1.2, 9.1, 0), (0.8, 3.0, 3.0))
    return _mesh(kit, name, bm, _m(kit)['rust'])


def _room(kit, name):
    return _boxes(kit, name, [(0, 70, -17, 17, -0.6, -0.02), (0, 70, 17, 17.6, 0, 15), (0, 70, -17.6, -17, 0, 15), (0, 70, -17, 17, 15, 15.6),
                              (0, 70, 7, 17, 5.6, 6), (22, 70, -17, -7, 5.6, 6),
                              (70, 70.6, 7, 17.6, 0, 15), (70, 70.6, -17.6, -7, 0, 15), (70, 70.6, -7, 7, 9, 15)], 'rust')


def _tank(kit, name):
    bm = bmesh.new()
    kit.lathe(bm, [(3.3, 0), (3.3, 10)], seg=16)
    return _mesh(kit, name, bm, _m(kit)['red'])


def _pipes(kit, name, paths, r=0.65):
    bm = bmesh.new()
    for p, rr in paths:
        _pipe(bm, kit, p, rr or r)
    return _mesh(kit, name, bm, _m(kit)['dark'])


def _arc_path():
    return [(0, 8.6 * math.sin(a) * -1 + 0.0 + 0.0 if False else 8.6 - 8.6 * math.cos(a), 8.6 * math.sin(a)) for a in np.linspace(0, 8 / 8.6, 9)]


B = {
    'stair_flight_12': lambda k, n: _flight(k, n, 10),
    'stair_landing': lambda k, n: _boxes(k, n, [(-8, 8, -8, 8, -1, 0)]),
    'stair_wall_panel': lambda k, n: _boxes(k, n, [(-8, 8, -0.6, 0, 0, 16)]),
    'stair_wall_ramp': _ramp,
    'stair_beam_low': lambda k, n: _boxes(k, n, [(-0.5, 0.5, -7, 7, -0.7, 0.7)]),
    'stair_flight_torn': lambda k, n: _flight(k, n, 7),
    'rail_12': lambda k, n: _rail(k, n, 5.0, 12.0),
    'rail_flat_16': lambda k, n: _rail(k, n, 0.0, 16.0),
    'rail_bent': lambda k, n: _rail(k, n, 0.0, 7.4),
    'hazard_trim': lambda k, n: _boxes(k, n, [(0, 12, -0.65, 0.65, 0, 0.02)], 'hazard'),
    'wall_ladder': lambda k, n: _boxes(k, n, [(-0.34, 0.34, 0, 0.4, 0, 12)]),
    'pipe_big_12': lambda k, n: _pipes(k, n, [([(0, 0, 0), (12, 0, 0)], 0.65)]),
    'pipe_elbow': lambda k, n: _pipes(k, n, [([(0, 0, 0), (1.4, 0, 0.6), (2, 0, 2)], 0.65)]),
    'pipe_cluster_12': lambda k, n: _pipes(k, n, [([(0, 0.7, 0.7), (12, 0.7, 0.7)], 0.55), ([(0, 0.6, -0.7), (12, 0.6, -0.7)], 0.45), ([(0, 1.4, 0.0), (12, 1.4, 0.0)], 0.3)]),
    'pipe_valve': lambda k, n: _pipes(k, n, [([(-1.5, 0, 0), (1.5, 0, 0)], 0.65), ([(0, 0, 0), (0, 2.3, 0)], 0.15)]),
    'pipe_broken': lambda k, n: _pipes(k, n, [([(0, 0, 0), (3.2, 0, 0)], 0.65)]),
    'cable_tray_12': lambda k, n: _boxes(k, n, [(0, 12, 0.2, 1.2, 0, 0.5)], 'dark'),
    'cable_bundle_12': lambda k, n: _boxes(k, n, [(0, 12, -0.4, 0.5, -0.65, 0.65)], 'dark'),
    'cable_bundle_arc': lambda k, n: _pipes(k, n, [(_arc_path(), 0.6)]),
    'light_red_strip': lambda k, n: _light(k, n, 2.8, 0.25, 'red'),
    'light_green_cage': lambda k, n: _light(k, n, 1.3, 1.0, 'green'),
    'light_white_cage': lambda k, n: _light(k, n, 2.4, 0.8, 'white'),
    'light_ceiling_tube': lambda k, n: _boxes(k, n, [(-1.5, 1.5, -0.2, 0.2, -0.5, -0.3)], 'white'),
    'light_beacon_red': lambda k, n: _boxes(k, n, [(-0.2, 0.2, -0.2, 0.2, 0, 0.5)], 'red'),
    'panel_green_data': lambda k, n: _light(k, n, 2.0, 2.6, 'green'),
    'wall_fan': lambda k, n: _boxes(k, n, [(-2, 2, 0, 0.6, -2, 2)], 'dark'),
    'door_steel': lambda k, n: _boxes(k, n, [(-2, 2, 0, 0.3, 0, 6)], 'dark'),
    'junction_box': lambda k, n: _boxes(k, n, [(-0.6, 0.6, 0, 0.4, -0.7, 0.7)]),
    'tube_ring_8': _ring,
    'tube_ring_riveted': _ring,
    'tube_walkway_8': lambda k, n: _boxes(k, n, [(0, 8, 0, 2.6, -1, 0.95)]),
    'tube_side_duct': lambda k, n: _boxes(k, n, [(-1.7, 1.7, 0, 0.55, -1.35, 1.35)], 'dark'),
    'tube_cross_grate': lambda k, n: _boxes(k, n, [(-4, 4, -1.5, 1.5, -1.3, -1.0)], 'dark'),
    'bulkhead_frame': _frame,
    'bulkhead_door': _door,
    'red_room_shell': _room,
    'red_tank': _tank,
}


def piece(kit, name):
    return assetkit.use(kit, name, lambda: B[name](kit, name))


def stencil(kit, level):
    """stencil_B4 and so on: one object of the stencil_levels glb, or a 3 x 3 plate of paint."""
    name = f'stencil_B{level}'
    key = '_' + name
    if key in assetkit._pieces:
        return assetkit._pieces[key]
    p = None
    if assetkit.have('stencil_levels'):
        whole = assetkit.use(kit, 'stencil_levels', lambda: None)
        parts = [q for q in whole.parts if q[2] == name or q[2].startswith(name + '.')]
        if parts:
            p = assetkit.Piece(kit, name, parts, 'asset')
    if p is None:
        p = assetkit.Piece(kit, name, [(_light(kit, name, 3.0, 3.0, 'grey'), Matrix.Identity(4), name)], 'blockout')
    assetkit._pieces[key] = p
    return p


def yaw(a, pitch=0.0, roll=0.0):
    """Turned a about z, tipped `pitch` (+ is +X going down), rolled about its own X."""
    return Matrix.Rotation(a, 3, 'Z') @ Matrix.Rotation(pitch, 3, 'Y') @ Matrix.Rotation(roll, 3, 'X')


def water_ribbon(kit, name, axis_pts, half, z, grp):
    """The water surface along an axis: (x, y, heading) samples, half wide. City5Water: black, glossy; the site's shader takes it by name."""
    mat = bpy.data.materials.get('City5Water') or kit.material('City5Water', (0.008, 0.011, 0.011), 0.06, 0.5, vcol=False, spec=0.9)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    prev = None
    run = 0.0
    last = None
    for x, y, h in axis_pts:
        nx, ny = -math.sin(h), math.cos(h)
        if last is not None:
            run += math.hypot(x - last[0], y - last[1])
        last = (x, y)
        row = (bm.verts.new((x + nx * half, y + ny * half, z)), bm.verts.new((x - nx * half, y - ny * half, z)), run)
        if prev:
            f = bm.faces.new((prev[0], prev[1], row[1], row[0]))
            for lp, (u, v) in zip(f.loops, ((0, prev[2]), (1, prev[2]), (1, run), (0, run))):
                lp[uv].uv = (u * 2 * half / 8, v / 8)
        prev = row
    me = kit.mesh_from(name, bm, [mat], recalc=False)
    return kit.static(name.split('.')[-1], me, grp)


def card(kit, name, corners, mat, grp):
    """A one-off quad."""
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(c) for c in corners])
    me = kit.mesh_from(name, bm, [mat], recalc=False)
    return kit.static(name.split('.')[-1], me, grp)
