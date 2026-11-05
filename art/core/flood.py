"""The flooded tunnel (art/core/ASSETS.md: moments 8 and 9), laid along art/core/road_sections.py, by the table's names: each piece's glb if it's
landed in art/out/assets, else its grey stand-in (art/core/blockout.py). Exports art/out/city5-flood.glb.

  blender --background --factory-startup --python art/core/flood.py        (STAIR_LEN, FLOOD_LEN, LAB_DOOR_S, HALL_X: road_sections.py)

The door's its own node, City5.BulkheadDoor, shut in the glb, an empty on the hinge with its parts under it: the site turns it about its up axis by
-open_deg once the memory game's solved. DOOR_OPEN=1 in the env exports it at the image's half-open.
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import blockout as B  # noqa: E402
import road_sections as R  # noqa: E402
import stair as ST  # noqa: E402

ROAD = None
EVENTS = []
LAMPS = []
SHOTS = {}
RED, GREEN, WHITE = (1.0, 0.1, 0.05), (0.25, 1.0, 0.35), (0.9, 1.0, 0.92)
DOOR = {}
TANKS = [(39.0, 13.0), (52.0, 11.0), (16.0, 13.2), (40.0, -13.0), (56.0, -11.5)]   # the room's frame: art/core/assets/_bulkhead.py
TANK_Z = 4.6


def build(kit):
    global ROAD
    a = R.stair()
    ROAD = R.flood(start=a['end'], heading=a['heading_out'], deck=a['deck'])
    return {}


def _wall_mat(h, side, phi):
    """On the tube's wall `phi` from straight down, side +1 left, -1 right: X along the tube, Y into the tube, Z what's left."""
    t = Vector((math.cos(h), math.sin(h), 0))
    left = Vector((-math.sin(h), math.cos(h), 0))
    n = (-left * side * math.sin(phi) + Vector((0, 0, 1)) * math.cos(phi)).normalized()
    z = t.cross(n)
    return Matrix((t, n, z)).transposed()


def _wall_pos(ax, ay, h, deck, side, phi, r=R.TUBE_R):
    left = np.array((-math.sin(h), math.cos(h)))
    d = r * math.sin(phi) * side
    return (ax + left[0] * d, ay + left[1] * d, deck + R.TUBE_ZC - r * math.cos(phi))


def place(kit, _pieces):
    road = ROAD
    LAMPS.clear()
    EVENTS.clear()
    deck = road['deck']
    door_a = road['door_sa']
    p = lambda name: B.piece(kit, name)  # noqa: E731
    G = 'Flood'
    # The wall moment's stretch, on the axis: nothing stands proud on the right's lower wall there.
    wa = np.interp(road['wall_s'], road['fx'], road['sa'])

    def clear(a, side, phi):
        return wa[0] - 12 <= a <= wa[1] + 12 and side < 0 and phi < math.radians(100)

    # The back of the first rings: the stair's way out comes down into them.
    last_ring = door_a - R.RING     # bulkhead_frame takes the place of the tube's last 8 m
    n_rings = int(last_ring // R.RING)
    ring_a = [i * R.RING for i in range(-2, n_rings)]
    # Land the rings' end exactly on the frame.
    ring_a = [a + (last_ring - (n_rings * R.RING)) for a in ring_a]
    pts = []
    for i, a in enumerate(ring_a):
        ax0, ay0, h0 = _axis(road, a)
        _ax1, _ay1, h1 = _axis(road, a + R.RING)
        h = (h0 + h1) / 2
        name = 'tube_ring_riveted' if (i + 2) % 7 == 3 or a > door_a - 60 else 'tube_ring_8'
        p(name).put((ax0, ay0, deck), B.yaw(h), grp=G)
        pts.append((ax0, ay0, h0))
        am = a + R.RING / 2
        ax, ay, hm = _axis(road, am)
        # The image's left and right: green caged lamps, low; white work lights, high; thick cables along both walls; the big pipe on the left.
        if i % 2 == 0:
            for side in (1, -1):
                ph = math.radians(84)
                if not clear(am, side, ph):
                    p('light_green_cage').put(_wall_pos(ax, ay, hm, deck, side, ph), _wall_mat(hm, side, ph), grp=G)
                    q = _wall_pos(ax, ay, hm, deck, side, ph, 7.8)
                    LAMPS.append((q[0], q[1], q[2], GREEN, 320))
        if i % 2 == 1:
            for side in (1, -1):
                ph = math.radians(128)
                p('light_white_cage').put(_wall_pos(ax, ay, hm, deck, side, ph), _wall_mat(hm, side, ph), grp=G)
                q = _wall_pos(ax, ay, hm, deck, side, ph, 7.4)
                LAMPS.append((q[0], q[1], q[2], WHITE, 240))
        if i % 5 == 2:
            p('tube_cross_grate').put((ax, ay, deck + R.TUBE_ZC + R.TUBE_R), B.yaw(hm), grp=G)
        if i % 9 == 4:
            ph = math.radians(118)
            p('tube_side_duct').put(_wall_pos(ax, ay, hm, deck, 1, ph), _wall_mat(hm, 1, ph), grp=G)
        if i % 11 == 7:
            ph = math.radians(70)
            if not clear(am, 1, ph):
                p('cable_bundle_arc').put(_wall_pos(ax, ay, hm, deck, 1, ph, 8.6), _wall_mat(hm, 1, ph), grp=G)
    # Runs along the wall, by distance: bundles both sides, the big pipe and tray on the left. (The image's left: pipe at shoulder height, cables over it.)
    a = ring_a[0]
    while a < last_ring - 11.0:
        ax, ay, h0 = _axis(road, a)
        _a1, _b1, h1 = _axis(road, a + 12.0)
        h = (h0 + h1) / 2
        for side, ph in ((1, 110), (1, 118), (-1, 104), (-1, 112), (-1, 120)):
            r_ph = math.radians(ph)
            p('cable_bundle_12').put(_wall_pos(ax, ay, h, deck, side, r_ph, 8.6), _wall_mat(h, side, r_ph), grp=G)
        r_ph = math.radians(97)
        if not clear(a, 1, r_ph):
            p('pipe_big_12').put(_wall_pos(ax, ay, h, deck, 1, r_ph, 8.0), B.yaw(h), grp=G)
        a += 12.0
    # The walkway on the left, long stretches of it, into the bulkhead as in the image's lower left.
    for i, a in enumerate(ring_a):
        if a > door_a - 60 or (i // 12) % 3 == 1:
            ax, ay, h = _axis(road, a)
            left = (-math.sin(h), math.cos(h))
            p('tube_walkway_8').put((ax + left[0] * 6.2, ay + left[1] * 6.2, deck), B.yaw(h), grp=G)
    # The water, from before the first ring to the door's sill.
    pts.append(_axis(road, last_ring))
    pts.append(_axis(road, door_a + 1.5))
    half = math.sqrt(R.TUBE_R ** 2 - (R.TUBE_ZC - R.WATER_UP) ** 2) + 0.2
    B.water_ribbon(kit, 'City5.Water', pts, half, deck + R.WATER_UP, G)
    # The back of it shut: what's behind's the stair's, not loaded for long.
    ax, ay, h = _axis(road, ring_a[0])
    lf = (-math.sin(h) * 10, math.cos(h) * 10)
    B.card(kit, 'City5.SealBack', [(ax + lf[0], ay + lf[1], deck - 5), (ax - lf[0], ay - lf[1], deck - 5), (ax - lf[0], ay - lf[1], deck + 16), (ax + lf[0], ay + lf[1], deck + 16)], kit.MAT['dark'], G)

    # --- The bulkhead and the room. The frame, the door on its hinge, the room behind, its tanks: the opening's frame is on +X, on y 0.
    bx, by, bh = _axis(road, door_a)
    F = B.yaw(bh)
    p('bulkhead_frame').put((bx, by, deck + R.TUBE_ZC), F, grp=G)
    hx = bx + math.cos(bh) * R.HINGE[0] - math.sin(bh) * R.HINGE[1]
    hy = by + math.sin(bh) * R.HINGE[0] + math.cos(bh) * R.HINGE[1]
    # The door's parts hang off one empty on the hinge, so it's one thing to turn.
    hinge = bpy.data.objects.new('City5.BulkheadDoor', None)
    bpy.context.scene.collection.objects.link(hinge)
    hinge.parent = kit.group(G)
    H0 = Matrix.Translation((hx, hy, deck + R.TUBE_ZC)) @ Matrix.Rotation(bh, 4, 'Z')
    hinge.matrix_basis = H0
    hinge['open_deg'] = R.DOOR_OPEN_DEG
    objs = p('bulkhead_door').put((hx, hy, deck + R.TUBE_ZC), B.yaw(bh), grp=G, named='City5.BulkheadDoorPart')
    for o in objs:
        m = o.matrix_basis.copy()
        o.parent = hinge
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.matrix_basis = H0.inverted() @ m
    DOOR.update({'hinge_obj': hinge, 'H0': H0, 'hinge': (hx, hy, deck + R.TUBE_ZC)})
    if os.environ.get('DOOR_OPEN') == '1':
        hinge.matrix_basis = H0 @ Matrix.Rotation(-math.radians(R.DOOR_OPEN_DEG), 4, 'Z')
    p('red_room_shell').put((bx, by, deck), F, grp=G)
    for tx, ty in TANKS:
        x = bx + math.cos(bh) * tx - math.sin(bh) * ty
        y = by + math.sin(bh) * tx + math.cos(bh) * ty
        p('red_tank').put((x, y, deck + TANK_Z), F, grp=G)
    LAMPS.append((bx + 2, by, deck + 8.0, RED, 300))
    # Red alarm beacons either side of the frame, on the tube's wall, as in the image.
    for side in (1, -1):
        ax, ay, h = _axis(road, door_a - 10.0)
        ph = math.radians(85)
        rot = _wall_mat(h, side, ph) @ Matrix.Rotation(-math.pi / 2, 3, 'X')
        p('light_beacon_red').put(_wall_pos(ax, ay, h, deck, side, ph), rot, grp=G)
        q = _wall_pos(ax, ay, h, deck, side, ph, 8.0)
        LAMPS.append((q[0], q[1], q[2], RED, 120))
    # The seal: the servers, through the far wall's opening, are the hall's, loaded by then.
    ex, ey = bx + math.cos(bh) * (R.ROOM_LEN + 0.7), by + math.sin(bh) * (R.ROOM_LEN + 0.7)
    lf = (-math.sin(bh) * 7.2, math.cos(bh) * 7.2)
    B.card(kit, 'City5.SealFar', [(ex + lf[0], ey + lf[1], deck), (ex - lf[0], ey - lf[1], deck), (ex - lf[0], ey - lf[1], deck + 9.2), (ex + lf[0], ey + lf[1], deck + 9.2)], kit.MAT['dark'], G)
    # Spray settles at the stop.
    EVENTS.append({'kind': 'stop', 's': round(road['stop_s'], 1), 'what': 'bulkhead'})
    SHOTS.update(_shots(road))


def _axis(road, a):
    ax, ay, ah, sa = road['axis']
    if a < 0:
        # Back along the heading it starts on, up the way out.
        return float(ax[0] + math.cos(ah[0]) * a), float(ay[0] + math.sin(ah[0]) * a), float(ah[0])
    return R.axis_at(road, a)


def _shots(road):
    w = road['wall_s']
    door = road['door_s']
    return {
        'm8a': {'s': 36.0, 'title': '8 in the water, the ribbed tube'},
        'm8b': {'s': (w[0] + w[1]) / 2, 'title': '8 up the curve of the wall'},
        'm9stop': {'s': road['stop_s'], 'parked': True, 'title': '9 halted, the bulkhead shut', 'door': 0.0},
        'm9open': {'s': road['stop_s'], 'parked': True, 'title': '9 the same, swung open: the image', 'door': 1.0},
        'm9gap': {'s': door - 4.0, 'title': '9 through the gap', 'door': 1.0},
        'm9room': {'s': door + 34.0, 'title': '9 the red room, on to the servers', 'door': 1.0},
    }


def payload(s0):
    road = ROAD
    pay = R.payload(road, s0)
    pay['water'] = {'level': round(road['deck'] + R.WATER_UP, 3), 'to_s': round(s0 + road['water_to_s'], 1)}
    pay['stop'] = {'s': round(s0 + road['stop_s'], 1), 'door_s': round(s0 + road['door_s'], 1)}
    pay['door'] = {'open_deg': R.DOOR_OPEN_DEG, 'hinge': [round(float(v), 3) for v in DOOR['hinge']]}
    pay['wall'] = [round(s0 + v, 1) for v in road['wall_s']]
    pay['events'] = [dict(e, s=round(e['s'] + s0, 1)) for e in EVENTS]
    return pay


def main():
    import kit
    kit.begin()
    a = R.stair()
    place(kit, build(kit))
    ST.road_empty(kit, payload(R.DOOR_S + a['length']))
    out = os.path.join(kit.ROOT_DIR, 'art', 'out', 'city5-flood.glb')
    ST.export(kit, out)
    ST.report(kit, 'flood', out)


if __name__ == '__main__':
    main()
