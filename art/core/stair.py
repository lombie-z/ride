"""The stairwell (art/core/ASSETS.md: moments 1 to 7), laid along art/core/road_sections.py, by the table's names: each piece's glb if it's
landed in art/out/assets, else its grey stand-in (art/core/blockout.py). So a re-run picks up whatever's arrived. Exports art/out/city5-stair.glb.

  blender --background --factory-startup --python art/core/stair.py        (STAIR_LEN, FLOOD_LEN, LAB_DOOR_S, HALL_X: road_sections.py)

The moving pieces aren't in the glb: they're empties, City5.Moving.<name>.<i>, each with the asset, its place and the stretch of road its
clip's scrubbed over. Shared meshes export as GPU instances.
"""
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import assetkit  # noqa: E402
import blockout as B  # noqa: E402
import road_sections as R  # noqa: E402

SLOPE_A = math.atan(R.SLOPE)
ROAD = None
STOPS = {}
EVENTS = []
MOVING = []
LAMPS = []         # (x, y, z, colour, power): for the stills only (the site paints its light in)
RED, GREEN, WHITE = (1.0, 0.1, 0.05), (0.25, 1.0, 0.35), (0.9, 1.0, 0.92)
SHOTS = {}


def build(kit):
    global ROAD
    ROAD = R.stair()
    return {}


def _p(k, A, Bc, z):
    x, y = R.canon_world(k, A, Bc)
    return (float(x), float(y), float(z))


def _level(z, drop):
    """B4 at the top, B12 at the foot."""
    return min(12, 4 + int(-z / (drop / 9.0)))


def _lamp(loc, col, power):
    LAMPS.append((loc[0], loc[1], loc[2], col, power))


def place(kit, _pieces):
    road = ROAD
    EVENTS.clear()
    MOVING.clear()
    LAMPS.clear()
    n, mo = road['n'], road['mo']
    deck = road['deck']
    drop = -deck
    p = lambda name: B.piece(kit, name)  # noqa: E731
    G = 'Stair'
    Y = R.canon_yaw

    # --- The long flight (moments 1, 2): out of the lab's door frame, straight on along the shaft's diagonal, over the void to the far landing.
    x0 = R.LIP_X
    for i in range(R.LONG_FLIGHTS):
        x = x0 + i * R.FLIGHT_RUN
        z = -i * R.FLIGHT_DROP
        p('stair_flight_12').put((x, 0, z), B.yaw(0.0), grp=G)
        for d in (1, -1):
            p('rail_12').put((x, d * R.RAIL_D, z), B.yaw(0.0), grp=G)
            # Red strips on the rails' kick plates, streaking past.
            for t in (3.0, 9.0):
                zs = z - t * R.SLOPE + 0.5
                rot = B.yaw(0.0, SLOPE_A) if d < 0 else B.yaw(math.pi, -SLOPE_A)
                p('light_red_strip').put((x + t, d * (R.RAIL_D + 0.02) if d < 0 else d * (R.RAIL_D - 0.02), zs), rot, grp=G)
                _lamp((x + t, d * 5.2, zs + 0.5), RED, 55)
        # The big pipes on the left, on down the flight, close over the rail.
        p('pipe_big_12').put((x, 7.4, z + 1.5), B.yaw(0.0, SLOPE_A), grp=G)
        p('pipe_big_12').put((x, 8.5, z + 3.1), B.yaw(0.0, SLOPE_A), grp=G)
    # The corridor's walls, from the door frame to where the shaft opens: pipes left, B4 and its window right.
    CW = 9.0
    cor_end = R.CX - (R.WALL * math.sqrt(2) - CW)     # the walls meet the shaft's, CW either side of its corner
    span = cor_end - (R.DOOR_S + 8.0)
    xm = (cor_end + R.DOOR_S + 8.0) / 2
    for zb in (-32.0, -16.0, 0.0, 16.0):
        p('stair_wall_panel').put((xm, -CW, zb), B.yaw(0.0), (span / 16.0, 1.0, 1.0), grp=G)
        p('stair_wall_panel').put((xm, CW, zb), B.yaw(math.pi), (span / 16.0, 1.0, 1.0), grp=G)
    B.stencil(kit, 4).put((cor_end - 1.8, -CW + 0.05, 5.6), B.yaw(0.0), grp=G)
    p('panel_green_data').put((cor_end - 2.2, -CW, 2.0), B.yaw(0.0), grp=G)
    p('junction_box').put((cor_end - 4.6, -CW, 1.6), B.yaw(0.0), grp=G)
    p('light_red_strip').put((cor_end - 6.0, -CW, 0.9), B.yaw(0.0), grp=G)
    _lamp((cor_end - 2.2, -CW + 1.2, 2.5), GREEN, 40)
    _lamp((cor_end - 5.5, -CW + 1, 1.4), RED, 60)
    p('pipe_cluster_12').put((cor_end, CW, 2.0), B.yaw(math.pi), grp=G)
    p('pipe_cluster_12').put((cor_end, CW, 5.4), B.yaw(math.pi), grp=G)
    # A big riser and its elbow, as in the image's left.
    for zb in (-8.0, 4.0):
        p('pipe_big_12').put((cor_end - 2.0, CW - 1.2, zb), B.yaw(0.0, -math.pi / 2), grp=G)
    p('pipe_elbow').put((cor_end - 2.0, CW - 1.2, 16.0), B.yaw(0.0, -math.pi / 2, 0.0), grp=G)
    _lamp((x0 + 4, 5.2, 3.0), RED, 260)
    _lamp((x0 + 22, 5.2, -5.0), RED, 200)

    # --- The shaft's walls: 3 panels a side (they overlap at the joins), stacked down to under the last landing. The corridor cuts the two near walls'
    # corner panels for its height.
    top = 16.0
    rows = []
    z = top
    while z > R.z_side(n) - 32.0:
        rows.append(z)
        z -= 16.0
    for w in range(4):
        for zb in rows:
            for Bc in (-14.0, 0.0, 14.0):
                b = Bc
                if zb >= -16.0:
                    if w == 1 and Bc == -14.0:   # the south wall, by the corner the corridor's through
                        continue
                    if w == 2 and Bc == 14.0:
                        continue
                    if w == 1 and Bc == 0.0:
                        b = -1.3
                    if w == 2 and Bc == 0.0:
                        b = 1.3
                # The way out, through the wall ahead of the last side.
                z_out = R.z_side(n - 1) - R.FLIGHT_DROP
                if w == n % 4 and Bc == 14.0 and zb + 16.0 > z_out - 10.0 and zb < z_out + 12.0:
                    continue
                p('stair_wall_panel').put(_p(w, R.WALL, b, zb), B.yaw(Y(w, math.pi / 2)), grp=G)
    # Its lid.
    for A_ in (-14.0, 0.0, 14.0):
        for B_ in (-22.0, -8.0, 6.0):
            x, y = R.world(A_, B_)
            p('stair_wall_panel').put((float(x) , float(y), 32.0), B.yaw(R.YAW) @ B.yaw(0.0, 0.0, -math.pi / 2), grp=G)

    # --- Above the road, what the first shot looks across: the flights it never rides, the far corner's apex at the top of the frame.
    def dress_landing(k, z_):
        p('stair_landing').put(_p(k, R.SIDE_A, -R.SIDE_A, z_), B.yaw(Y(k)), grp=G)

    for k, zt in ((-1, 5.0), (0, 0.0)):
        p('stair_flight_12').put(_p(k, R.SIDE_A, R.VOID, zt), B.yaw(Y(k, -math.pi / 2)), grp=G)
        p('rail_12').put(_p(k, R.SIDE_A - R.RAIL_D, R.VOID, zt), B.yaw(Y(k, -math.pi / 2)), grp=G)
        dress_landing(k, zt - R.FLIGHT_DROP)
    p('stair_landing').put(_p(3, R.SIDE_A, R.SIDE_A, 5.0), B.yaw(Y(3)), grp=G)   # (the north-west one, at the top of that flight)
    # On the far walls either side of the apex: B5 as in the image, its door, its tube, its fan, its window.
    B.stencil(kit, 5).put(_p(3, R.WALL - 0.05, -6.0, -6.0), B.yaw(Y(3, math.pi / 2)), grp=G)
    B.stencil(kit, 5).put(_p(0, R.WALL - 0.05, 12.0, -6.0), B.yaw(Y(0, math.pi / 2)), grp=G)
    p('door_steel').put(_p(3, R.WALL, -13.0, 0.0), B.yaw(Y(3, math.pi / 2)), grp=G)
    p('wall_fan').put(_p(0, R.WALL, 16.0, 4.0), B.yaw(Y(0, math.pi / 2)), grp=G)
    p('panel_green_data').put(_p(3, R.WALL, -2.0, -2.5), B.yaw(Y(3, math.pi / 2)), grp=G)
    p('light_ceiling_tube').put(_p(3, R.WALL - 0.4, -13.0, 8.0), B.yaw(Y(3, math.pi / 2)) @ B.yaw(0.0, 0.0, math.pi / 2), grp=G)
    _lamp(_p(3, R.WALL - 3, -13.0, 7.0), WHITE, 500)
    _lamp(_p(3, R.WALL - 1.5, -2.0, -2.5), GREEN, 50)
    # (Red strips on those far walls, and the dressed flights' own, as the image's run round the ring.)
    for k, zt in ((-1, 5.0), (0, 0.0)):
        for b_ in (-4.0, 4.0):
            zs = zt - (R.VOID - b_) * R.SLOPE
            p('light_red_strip').put(_p(k, R.WALL, b_, zs + 3.0), B.yaw(Y(k, math.pi / 2), -SLOPE_A), grp=G)
            p('light_red_strip').put(_p(k, R.SIDE_A - R.RAIL_D + 0.03, b_, zs + 0.5), B.yaw(Y(k, -math.pi / 2), SLOPE_A), grp=G)
            _lamp(_p(k, R.WALL - 2.0, b_, zs + 3.0), RED, 160)

    # --- The ring: per side, its flight, rails, the landing it comes down on, the wall's dressing.
    torn, tight = mo['torn'], mo['tight']
    p('stair_landing').put(_p(0, R.SIDE_A, R.SIDE_A, R.Z0), B.yaw(Y(0)), grp=G)
    # Moment 3: the ramp, mirrored to bank to its left (the asset banks right; here the wall's on the left, the void's on the right).
    p('stair_wall_ramp').put(_p(0, R.SIDE_A, R.RAMP_B, R.Z0), B.yaw(Y(0, -math.pi / 2)), (1.0, -1.0, 1.0), grp=G)
    B.stencil(kit, 5).put(_p(0, R.WALL - 0.05, -2.0, R.Z0 + 3.0), B.yaw(Y(0, math.pi / 2)), grp=G)
    _lamp(_p(0, R.WALL - 4.0, 2.0, R.Z0 + 5.0), RED, 500)
    for k in range(n):
        zt = R.z_side(k)
        zf = zt - R.FLIGHT_DROP
        h = Y(k, -math.pi / 2)
        tighter = k >= tight
        last = k == n - 1
        if k == torn:
            p('stair_flight_torn').put(_p(k, R.SIDE_A, R.VOID, zt), B.yaw(h), grp=G)
            MOVING.append({'name': 'flight_collapse', 'loc': _p(k, R.SIDE_A, R.VOID, zt), 'yaw': h, 's': _s_window(road, k, -70.0, -8.0)})
            MOVING.append({'name': 'debris_set', 'loc': _p(k, R.SIDE_A, 0.0, zt - 8.0), 'yaw': h, 's': _s_window(road, k, -50.0, 40.0)})
            # The landing's free edges, and the wrecked rail.
            # (Out over the gap on the void's side, clear of the line off the edge.)
            p('rail_bent').put(_p(k, R.SIDE_A - R.RAIL_D, R.VOID, zt), B.yaw(Y(k)), (1.0, -1.0, 1.0), grp=G)
        else:
            p('stair_flight_12').put(_p(k, R.SIDE_A, R.VOID, zt), B.yaw(h), grp=G)
            p('rail_12').put(_p(k, R.SIDE_A - R.RAIL_D, R.VOID, zt), B.yaw(h), grp=G)
            if k != 0:   # (the wall's dive comes down over it on the first)
                p('rail_12').put(_p(k, R.SIDE_A + R.RAIL_D, R.VOID, zt), B.yaw(h), grp=G)
        p('stair_landing').put(_p(k, R.SIDE_A, -R.SIDE_A, zf), B.yaw(Y(k)), grp=G)
        p('hazard_trim').put(_p(k, 8.0, -R.WALL + 1.2, zf), B.yaw(Y(k)), grp=G)
        # The rail round the landing's inner corner: the 2 m of edge a flight leaves free on each side.
        if not last and k + 1 != torn:
            p('rail_flat_16').put(_p(k, R.VOID, -R.VOID, zf), B.yaw(Y(k)), (2.1 / 16.0, 1.0, 1.0), grp=G)
            p('rail_flat_16').put(_p(k, R.VOID, -R.VOID, zf), B.yaw(h), (2.1 / 16.0, 1.0, 1.0), grp=G)

        # The left wall: pipes down the flight, close by the rail, red strips over them.
        if k != 0 and k != torn:
            p('pipe_cluster_12').put(_p(k, R.WALL, -R.VOID, zf + 1.9), B.yaw(Y(k, math.pi / 2), -SLOPE_A), grp=G)
        if k != 0:
            for b in (-3.0, 3.0):
                zs = zt - (R.VOID - b) * R.SLOPE
                # On the left rail's kick and on the wall over the pipes.
                p('light_red_strip').put(_p(k, R.WALL, b, zs + 4.0), B.yaw(Y(k, math.pi / 2), -SLOPE_A), grp=G)
                if k != torn:
                    p('light_red_strip').put(_p(k, R.SIDE_A - R.RAIL_D + 0.03, b, zs + 0.3), B.yaw(h, SLOPE_A), grp=G)
                    p('light_red_strip').put(_p(k, R.SIDE_A + R.RAIL_D - 0.03, b, zs + 0.3), B.yaw(Y(k, math.pi / 2), -SLOPE_A), grp=G)
            _lamp(_p(k, R.WALL - 1.5, 0.0, zt - 2.5 + 3.0), RED, 120)
        # The landing's walls, turn about: the level's plate facing up the flight; a window, a door or a fan on the left wall.
        lvl = _level(zf, drop)
        if k % 2 == 0:
            B.stencil(kit, lvl).put(_p(k, R.SIDE_A + 1.0, -R.WALL + 0.05, zf + 5.2), B.yaw(Y(k)), grp=G)
            _lamp(_p(k, R.SIDE_A + 1.0, -R.WALL + 3.0, zf + 6.0), WHITE, 60)
        if k % 4 == 1:
            p('panel_green_data').put(_p(k, R.WALL, -13.0, zf + 2.4), B.yaw(Y(k, math.pi / 2)), grp=G)
            p('junction_box').put(_p(k, R.WALL, -9.5, zf + 2.0), B.yaw(Y(k, math.pi / 2)), grp=G)
            _lamp(_p(k, R.WALL - 2.0, -13.0, zf + 2.5), GREEN, 80)
        elif k % 4 == 3:
            p('door_steel').put(_p(k, R.WALL, -14.0, zf), B.yaw(Y(k, math.pi / 2)), grp=G)
            p('light_ceiling_tube').put(_p(k, R.WALL - 0.4, -14.0, zf + 8.0), B.yaw(Y(k, math.pi / 2)) @ B.yaw(0.0, 0.0, math.pi / 2), grp=G)
            _lamp(_p(k, R.WALL - 3, -14.0, zf + 7.0), WHITE, 300)
        elif k % 8 == 2:
            p('wall_fan').put(_p(k, R.WALL, -14.0, zf + 5.0), B.yaw(Y(k, math.pi / 2)), grp=G)
        elif k % 8 == 6:
            p('wall_ladder').put(_p(k, R.WALL, -9.0, zf), B.yaw(Y(k, math.pi / 2)), grp=G)

        # Moment 6: tighter. A beam over each flight and each landing's way on, pipes overhead and on the void's side, cables, beacons, steam.
        if tighter and not last:
            zm = zt - R.FLIGHT_DROP / 2
            p('stair_beam_low').put(_p(k, R.SIDE_A, 0.0, zm + 1.0 + 5.5 + 0.7), B.yaw(h), grp=G)
            p('stair_beam_low').put(_p(k, R.SIDE_A, -R.VOID - 1.0, zf + 1.0 + 5.5 + 0.7), B.yaw(h), grp=G)
            p('pipe_big_12').put(_p(k, R.SIDE_A + 3.5, R.VOID, zt + 7.0), B.yaw(h, SLOPE_A), grp=G)
            p('pipe_big_12').put(_p(k, R.SIDE_A - 6.8, R.VOID, zt + 1.6), B.yaw(h, SLOPE_A), grp=G)
            p('cable_tray_12').put(_p(k, R.WALL, -R.VOID, zf + 5.0), B.yaw(Y(k, math.pi / 2), -SLOPE_A), grp=G)
            p('light_beacon_red').put(_p(k, R.WALL - 0.05, 2.0, zm + 3.4), B.yaw(Y(k, math.pi / 2)) @ B.yaw(0.0, 0.0, -math.pi / 2), grp=G)
            _lamp(_p(k, R.SIDE_A, 0.0, zm + 4.5), RED, 90)
            if (k - tight) % 3 == 0:
                # A sheared pipe at the wall, its mouth across the road.
                loc = _p(k, R.WALL - 0.6, 1.0, zm + 3.0)
                p('pipe_broken').put(loc, B.yaw(Y(k, math.pi)), grp=G)
                EVENTS.append({'kind': 'steam', 's': round(R.s_of_side(road, k, 1.0, 3.5), 1), 'at': [round(v, 2) for v in loc], 'dir': round(Y(k, math.pi), 4)})
            if (k - tight) % 3 == 1:
                p('pipe_valve').put(_p(k, R.WALL - 1.4, -R.VOID - 3.0, zf + 7.0), B.yaw(Y(k, -math.pi / 2)), grp=G)
            if (k - tight) % 4 == 2:
                MOVING.append({'name': 'beam_swing', 'loc': _p(k, R.SIDE_A, 0.0, zm + 13.0), 'yaw': h, 's': _s_window(road, k, -55.0, -5.0)})
            if (k - tight) == 5:
                MOVING.append({'name': 'shutter_slam', 'loc': _p(k, R.SIDE_A, 0.0, zm + 12.5), 'yaw': h, 's': _s_window(road, k, -24.0, -8.0)})

    # --- Moment 7: the way out. The last side's landing, on through the wall: flights between walls, under a lid, down into the water, into the tube.
    k = n - 1
    zt = R.z_side(k) - R.FLIGHT_DROP
    m = road['m_out']
    h = Y(k, -math.pi / 2)
    B0 = -R.WALL
    for i in range(m):
        Bc = B0 - i * R.FLIGHT_RUN
        zi = zt - i * R.FLIGHT_DROP
        p('stair_flight_12').put(_p(k, R.SIDE_A, Bc, zi), B.yaw(h), grp=G)
        for d in (1, -1):
            p('rail_12').put(_p(k, R.SIDE_A + d * R.RAIL_D, Bc, zi), B.yaw(h), grp=G)
        # Walls and lid, at the slope; green caged lamps, the glow growing.
        for d, face in ((1, math.pi), (-1, 0.0)):
            for up in (0.0, 8.0):
                p('stair_wall_panel').put(_p(k, R.SIDE_A + d * 8.0, Bc - 8.0, zi - 8.0 - up), B.yaw(h + face), grp=G)
            p('light_green_cage').put(_p(k, R.SIDE_A + d * 7.9, Bc - 6.0, zi + 1.0), B.yaw(h + face), grp=G)
            _lamp(_p(k, R.SIDE_A + d * 6.5, Bc - 6.0, zi + 1.0), GREEN, 160 + 90 * i)
        # (A panel laid flat: its 16 high runs across, from the right wall to the left, its face down.)
        p('stair_wall_panel').put(_p(k, R.SIDE_A - 8.0, Bc - 6.0, zi - 2.5 + 9.0), B.yaw(h, SLOPE_A) @ B.yaw(0.0, 0.0, -math.pi / 2), grp=G)
    # The tube's first rings, as the flood's (its own glb takes over at the join; black beyond them).
    xe, ye = road['end']
    he = road['heading_out']
    cs, sn = math.cos(he), math.sin(he)
    pts = []
    RINGS = 10
    for i in range(-2, RINGS):
        x, y = xe + cs * i * R.RING, ye + sn * i * R.RING
        p('tube_ring_8').put((x, y, deck), B.yaw(he), grp=G)
        pts.append((x, y, he))
    pts.append((xe + cs * RINGS * R.RING, ye + sn * RINGS * R.RING, he))
    half = math.sqrt(R.TUBE_R ** 2 - (R.TUBE_ZC - R.WATER_UP) ** 2) + 0.2
    B.water_ribbon(kit, 'City5.Water', pts, half, deck + R.WATER_UP, G)
    ex, ey = xe + cs * RINGS * R.RING, ye + sn * RINGS * R.RING
    nx, ny = -sn * 10, cs * 10
    B.card(kit, 'City5.Seal', [(ex + nx, ey + ny, deck - 5), (ex - nx, ey - ny, deck - 5), (ex - nx, ey - ny, deck + 16), (ex + nx, ey + ny, deck + 16)], kit.MAT['dark'], G)
    # The shaft's foot: its glow, what the fog goes green from.
    glow = bpy.data.materials.get('City5ShaftGlow') or kit.material('City5ShaftGlow', (0.05, 0.4, 0.15), 0.5, vcol=False, emission=(0.2, 1.0, 0.4), strength=1.3)
    w0, w1 = R.world(-R.WALL, -R.WALL), R.world(R.WALL, -R.WALL)
    w2, w3 = R.world(R.WALL, R.WALL), R.world(-R.WALL, R.WALL)
    zg = rows[-1] + 2.0
    B.card(kit, 'City5.ShaftGlow', [(float(w0[0]), float(w0[1]), zg), (float(w1[0]), float(w1[1]), zg), (float(w2[0]), float(w2[1]), zg), (float(w3[0]), float(w3[1]), zg)], glow, G)
    for i in range(8):
        LAMPS.append((R.CX, R.CY, zg + 8.0 + i * 16.0, GREEN, 900))

    # The stops, and what moves.
    STOPS.update({'lab_doors': {'s': R.LAB_STOP_S, 'doors_s': R.DOOR_S}})
    for i, mv in enumerate(MOVING):
        e = bpy.data.objects.new(f'City5.Moving.{mv["name"]}.{i}', None)
        bpy.context.scene.collection.objects.link(e)
        e.parent = kit.group(G)
        e.location = mv['loc']
        e.rotation_euler = (0, 0, mv['yaw'])
        e['asset'] = mv['name']
        e['s0'], e['s1'] = mv['s']
    SHOTS.update(_shots(road))


def _s_window(road, k, a, b):
    s = R.s_of_side(road, k)
    return [round(s + a, 1), round(s + b, 1)]


def _shots(road):
    mo, n = road['mo'], road['n']
    air = road['air'][0]
    s_hug = R.s_of_side(road, mo['hug'], -R.SIDE_A + 0.0, -4.9)
    shots = {
        'm1': {'s': R.LIP_X - R.DOOR_S - 0.4, 'level': True, 'title': '1 doors open, the top of the long flight'},
        'm2': {'s': 36.0, 'title': '2 down the steps, pipes on the left'},
        'm3': {'s': 80.0, 'title': '3 on the wall, past B5'},
        'm4': {'s': R.s_of_side(road, mo['hug']) - 2.0, 'title': '4 by the rail round a landing'},
        'm5a': {'s': air[0] - 3.0, 'title': '5 the torn flight, the gap ahead'},
        'm5b': {'s': air[0] + 8.0, 'title': '5 over the gap'},
        'm6': {'s': R.s_of_side(road, mo['tight'] + 3, 4.0), 'title': '6 tighter: beams, pipes, steam'},
        'm7': {'s': road['length'] - 58.0, 'title': '7 fog, the glow, the last flight'},
        'm7b': {'s': road['length'] - 14.0, 'title': '7 into the black water'},
    }
    _ = s_hug, n
    return shots


def payload(s0=R.DOOR_S):
    road = ROAD
    pay = R.payload(road, s0)
    pay['events'] = [dict(e, s=round(e['s'] + s0, 1)) for e in EVENTS]
    pay['moments'] = road['mo']
    return pay


def export(kit, path):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in kit.root.children_recursive:
        o.select_set(True)
    kit.root.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_apply=True,
                              export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
                              export_draco_position_quantization=14, export_draco_normal_quantization=8,
                              export_draco_texcoord_quantization=10, export_draco_color_quantization=8,
                              export_vertex_color='ACTIVE', export_image_format='AUTO', export_image_quality=80,
                              export_gpu_instances=True, export_yup=True, export_cameras=False, export_lights=False, export_extras=True)


def road_empty(kit, pay):
    e = bpy.data.objects.new('City5.RoadPath', None)
    bpy.context.scene.collection.objects.link(e)
    e.parent = kit.root
    for k, v in pay.items():
        e[k] = v


def report(kit, name, path):
    meshes = [o for o in kit.root.children_recursive if o.type == 'MESH']
    uniq = {o.data.name: o.data for o in meshes}
    cs = assetkit.counts()
    grey = sorted(k for k, v in cs.items() if v['source'] == 'blockout')
    print(name.upper(), 'objects', len(meshes), 'unique', len(uniq), 'tris drawn', sum(kit.tris(o.data) for o in meshes), 'tris unique', sum(kit.tris(m) for m in uniq.values()),
          'glb', os.path.getsize(path) if os.path.exists(path) else None)
    print('still grey:', grey)
    print('placements:', {k: v['n'] for k, v in sorted(cs.items())})


def main():
    import kit
    kit.begin()
    place(kit, build(kit))
    road_empty(kit, payload())
    out = os.path.join(kit.ROOT_DIR, 'art', 'out', 'city5-stair.glb')
    export(kit, out)
    report(kit, 'stair', out)


if __name__ == '__main__':
    main()
