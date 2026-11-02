"""The green city the journey lands in (art/reference/concept-green-city.webp): an elevated freeway at night, the bike parked
on its wet deck, a heavy rusted gantry overhead dripping black, and a dense gothic city of towers falling away below with a
great cathedral spire beyond, an arched viaduct crossing the middle distance and a second freeway curving off right.
Builds art/city.blend from scratch and exports public/models/city.glb.
Run: blender --background --factory-startup --python art/build-city.py

World layout (Blender, z up, metres; the same space as art/micro-biome.blend, so the planter floats over the origin): the
deck's surface is at z -11, where FogDrog's lake was. The landing camera stands at eye level near its west end looking
east (+x); screen right is -y. The deck ends at an overlook rail before the drop, and the planter's black streams pour
down past it into the city. The towers stand on the ground far below (z -80).

The skyline is composed in the landing camera's screen space (screen_point): the hero towers, the spire and the viaduct are
placed where the concept has them, then filler towers cluster round them, leaving sky between the clusters.

Renders: art/renders/city-landing.png (Workbench, shapes), city-landing-eevee.png (a moody EEVEE stand-in for the site's
look: fog, lit windows), city-landing-eevee-nobike.png (the same without the bike stand-in) and city-montage.png (the
concept above the EEVEE render). CITY_NO_EEVEE=1 skips the EEVEE renders.
"""
import math
import os
import random
import subprocess

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BLEND = os.path.join(ROOT_DIR, 'art', 'city.blend')
GLB = os.path.join(ROOT_DIR, 'public', 'models', 'city.glb')
RENDER = os.path.join(ROOT_DIR, 'art', 'renders', 'city-landing.png')
RENDER_EEVEE = os.path.join(ROOT_DIR, 'art', 'renders', 'city-landing-eevee.png')
MONTAGE = os.path.join(ROOT_DIR, 'art', 'renders', 'city-montage.png')
CONCEPT = os.path.join(ROOT_DIR, 'art', 'reference', 'concept-green-city.webp')

DECK_Z = -11.0
GROUND_Z = -80.0
# The landing camera (art/build-journey.py's landing shot) and where the bike stands in front of it.
EYE = Vector((-27.0, -2.5, -10.55))
LOOK = Vector((40.0, -6.0, 1.0))
LANDING_FOV = 46.0
BIKE_AT = Vector((-23.8, -1.6, DECK_Z))
BIKE_YAW = -110.0
# Where the site actually parks the bike (the BikeMark is informational); the renders' stand-in goes here.
SITE_BIKE = Vector((-24.0, -2.3, DECK_Z))
RES = (1280, 720)

rnd = random.Random(11)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
root = bpy.data.objects.new('City', None)
scene.collection.objects.link(root)

# --- The landing camera's screen, for composing the skyline -------------------------------------------------------------
FWD = (LOOK - EYE).normalized()
RIGHT = FWD.cross(Vector((0, 0, 1))).normalized()
UP = RIGHT.cross(FWD)
TAN_V = math.tan(math.radians(LANDING_FOV / 2))
TAN_H = TAN_V * RES[0] / RES[1]


def screen_point(sx, sy, depth):
    """The world point at pixel (sx, sy) of the 1280x720 landing frame, `depth` metres along the view axis."""
    nx = (sx - RES[0] / 2) / (RES[0] / 2)
    ny = (RES[1] / 2 - sy) / (RES[1] / 2)
    return EYE + depth * (FWD + RIGHT * nx * TAN_H + UP * ny * TAN_V)


def to_screen(p):
    v = p - EYE
    d = v.dot(FWD)
    return (RES[0] / 2 * (1 + v.dot(RIGHT) / (d * TAN_H)), RES[1] / 2 * (1 - v.dot(UP) / (d * TAN_V)))


def material(name, colour, roughness=0.8, metallic=0.0, emission=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*colour, 1)
    p.inputs['Roughness'].default_value = roughness
    p.inputs['Metallic'].default_value = metallic
    if emission:
        p.inputs['Emission Color'].default_value = (*emission, 1)
        p.inputs['Emission Strength'].default_value = strength
    return m


MATS = {
    'deck': material('CityDeck', (0.02, 0.022, 0.022), 0.35),
    'concrete': material('CityConcrete', (0.05, 0.055, 0.052), 0.9),
    'steel': material('CitySteel', (0.06, 0.06, 0.055), 0.55, 0.8),
    'rail': material('CityRail', (0.09, 0.095, 0.09), 0.4, 0.9),
    'tower': material('CityTower', (0.025, 0.03, 0.028), 0.7),
    'spire': material('CitySpire', (0.02, 0.025, 0.022), 0.6, emission=(0.35, 1.0, 0.3), strength=0.0),
    'lamp': material('CityLamp', (0.8, 1.0, 0.7), 0.5, emission=(0.75, 1.0, 0.55), strength=6.0),
    'ooze': material('CityOoze', (0.004, 0.004, 0.005), 0.08),
    # New: the gantry's rusted plate fascia, a dark oxidised brown, rough, barely metallic.
    'rust': material('CityRust', (0.07, 0.042, 0.028), 0.85, 0.3),
}


def mesh_object(name, bm, mat, parent=None, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = smooth
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    o.parent = parent or root
    return o


def bare_layer(bm):
    """A face flag for parts that must not get windows (pinnacles, merlons, ledges): wall_uvs gives them (-1, -1)."""
    return bm.faces.layers.int.get('bare') or bm.faces.layers.int.new('bare')


def box(bm, centre, size, rot_z=0.0, bare=False):
    """Add an axis-aligned (then turned about z) box to bm; returns its new faces."""
    layer = bare_layer(bm)  # (before any geometry: adding a layer later invalidates face references)
    r = bmesh.ops.create_cube(bm, size=1.0)
    verts = r['verts']
    bmesh.ops.scale(bm, vec=size, verts=verts)
    if rot_z:
        bmesh.ops.rotate(bm, cent=Vector(), matrix=Matrix.Rotation(rot_z, 3, 'Z'), verts=verts)
    bmesh.ops.translate(bm, vec=centre, verts=verts)
    faces = list({f for v in verts for f in v.link_faces})
    if bare:
        for f in faces:
            f[layer] = 1
    return faces


def beam(bm, p0, p1, t, bare=True):
    """A square bar of side t from p0 to p1, any direction."""
    v = p1 - p0
    layer = bare_layer(bm)
    r = bmesh.ops.create_cube(bm, size=1.0)
    verts = r['verts']
    bmesh.ops.scale(bm, vec=Vector((t, t, v.length)), verts=verts)
    q = Vector((0, 0, 1)).rotation_difference(v.normalized())
    bmesh.ops.rotate(bm, cent=Vector(), matrix=q.to_matrix(), verts=verts)
    bmesh.ops.translate(bm, vec=(p0 + p1) / 2, verts=verts)
    if bare:
        for f in {f for v in verts for f in v.link_faces}:
            f[layer] = 1


def spike(bm, cx, cy, z0, half, length, rot=0.0, sides=4):
    """A pinnacle: a pyramid (or cone of `sides`) of base half-width `half`, apex `length` above z0. No windows."""
    layer = bare_layer(bm)
    r = half * (math.sqrt(2) if sides == 4 else 1.0)
    ring = [bm.verts.new((cx + math.cos(rot + math.pi / 4 + 2 * math.pi * k / sides) * r,
                          cy + math.sin(rot + math.pi / 4 + 2 * math.pi * k / sides) * r, z0)) for k in range(sides)]
    apex = bm.verts.new((cx, cy, z0 + length))
    for k in range(sides):
        f = bm.faces.new((ring[k], ring[(k + 1) % sides], apex))
        f[layer] = 1


def prism(bm, outline, origin, u, n, width):
    """Extrude a 2D outline [(s, z)] (s along u, z up) `width` across n, centred on origin. Returns the faces."""
    up = Vector((0, 0, 1))
    front = [bm.verts.new(origin + u * s + up * z - n * width / 2) for s, z in outline]
    back = [bm.verts.new(origin + u * s + up * z + n * width / 2) for s, z in outline]
    faces = [bm.faces.new(front), bm.faces.new(list(reversed(back)))]
    m = len(outline)
    for k in range(m):
        faces.append(bm.faces.new((front[k], back[k], back[(k + 1) % m], front[(k + 1) % m])))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def sweep(bm, path, profile, cap=True):
    """Sweep a closed profile [(a, up)] (a across to the right of travel, up = +z) along a 3D path."""
    n = len(path)
    rings = []
    for i, p in enumerate(path):
        t = path[min(i + 1, n - 1)] - path[max(i - 1, 0)]
        t.z = 0
        t.normalize()
        side = Vector((t.y, -t.x, 0))
        rings.append([bm.verts.new(p + side * a + Vector((0, 0, up))) for a, up in profile])
    m = len(profile)
    faces = []
    for i in range(n - 1):
        for k in range(m):
            faces.append(bm.faces.new((rings[i][k], rings[i][(k + 1) % m], rings[i + 1][(k + 1) % m], rings[i + 1][k])))
    if cap:
        faces.append(bm.faces.new(rings[0]))
        faces.append(bm.faces.new(list(reversed(rings[-1]))))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def wall_uvs(bm):
    """Metre-scaled UVs for the window pattern: u along each wall, v up it. Roofs, floors and bare parts get (-1, -1)."""
    bm.normal_update()
    uv = bm.loops.layers.uv.verify()
    bare = bm.faces.layers.int.get('bare')
    for f in bm.faces:
        n = f.normal
        if abs(n.z) > 0.5 or (bare and f[bare]):
            for loop in f.loops:
                loop[uv].uv = (-1, -1)
            continue
        t = Vector((-n.y, n.x, 0)).normalized()
        for loop in f.loops:
            p = loop.vert.co
            loop[uv].uv = (p.dot(t), p.z - GROUND_Z)


def offset(x, y, dx, dy, rot):
    c, s = math.cos(rot), math.sin(rot)
    return x + dx * c - dy * s, y + dx * s + dy * c


# --- The freeway deck -----------------------------------------------------------------------------------------------
# A long straight elevated freeway running away from the camera, angled ROAD_HEADING to the right of +x (toward -y), on
# piers down to the ground, fading into the city. Jersey barriers with steel guard rails along both edges; the right one
# recedes toward the vanishing point right of centre, as in the concept. The camera and the bike stand on it with room
# to spare; its left edge passes well to the right of the planter's falls (which drop at the origin).
ROAD_HEADING = math.radians(-22.0)
RD = Vector((math.cos(ROAD_HEADING), math.sin(ROAD_HEADING), 0))  # along the road
RL = Vector((-RD.y, RD.x, 0))  # to its left
ROAD_LEFT, ROAD_RIGHT = 6.8, 5.0  # the deck's edges, left and right of the camera
ROAD_W = ROAD_LEFT + ROAD_RIGHT
ROAD_BACK, ROAD_AHEAD = 45.0, 560.0  # how far it runs behind and ahead of the camera
ROAD_C = Vector((EYE.x, EYE.y, DECK_Z)) + RL * (ROAD_LEFT - ROAD_RIGHT) / 2  # on the centre line, abreast of the camera
ROAD_LEN = ROAD_BACK + ROAD_AHEAD
ROAD_MID = ROAD_C + RD * (ROAD_AHEAD - ROAD_BACK) / 2
BARRIER = 0.6  # a jersey barrier's footprint


def road(s, lateral=0.0, z=0.0):
    """A point s metres along the deck from abreast the camera, `lateral` metres left of its centre line."""
    return ROAD_C + RD * s + RL * lateral + Vector((0, 0, z))


bm = bmesh.new()
box(bm, ROAD_MID - Vector((0, 0, 0.6)), Vector((ROAD_LEN, ROAD_W, 1.2)), ROAD_HEADING)
deck = mesh_object('City.Deck', bm, MATS['deck'])

# The drivable surface between the barriers, for the site's wet reflector.
deck_top = bpy.data.objects.new('City.DeckTop', None)
scene.collection.objects.link(deck_top)
deck_top.parent = root
deck_top.location = ROAD_MID
deck_top.rotation_euler = (0, 0, ROAD_HEADING)
deck_top['length'] = ROAD_LEN
deck_top['width'] = round(ROAD_W - 2 * BARRIER, 3)
print('DeckTop', tuple(round(c, 3) for c in ROAD_MID), 'heading', math.degrees(ROAD_HEADING), 'length', ROAD_LEN, 'width', ROAD_W - 2 * BARRIER)

# A jersey barrier's cross-section (a across, to the right of travel; up): outer face at a = 0, safety slope toward -a.
JERSEY = [(0.0, -0.02), (0.0, 0.9), (-0.2, 0.9), (-0.32, 0.36), (-0.55, 0.1), (-0.6, -0.02)]
bm = bmesh.new()
sweep(bm, [road(-ROAD_BACK, -ROAD_W / 2), road(ROAD_AHEAD, -ROAD_W / 2)], JERSEY)
sweep(bm, [road(-ROAD_BACK, ROAD_W / 2), road(ROAD_AHEAD, ROAD_W / 2)], [(-a, u) for a, u in JERSEY])
# The box girder under the slab, and piers on cross-heads down into the dark.
box(bm, ROAD_MID - Vector((0, 0, 2.4)), Vector((ROAD_LEN - 2, ROAD_W - 4, 2.4)), ROAD_HEADING)
s = -ROAD_BACK + 12
while s < ROAD_AHEAD - 4:
    for lat in (-ROAD_W / 2 + 2.5, ROAD_W / 2 - 2.5):
        p = road(s, lat)
        box(bm, Vector((p.x, p.y, (DECK_Z - 3.6 + GROUND_Z) / 2)), Vector((2.4, 2.4, DECK_Z - 3.6 - GROUND_Z)), ROAD_HEADING)
    p = road(s)
    box(bm, Vector((p.x, p.y, DECK_Z - 4.2)), Vector((2.8, ROAD_W - 1.0, 1.6)), ROAD_HEADING)
    s += 32.0
mesh_object('City.DeckBeams', bm, MATS['concrete'])

# Steel guard rails on posts along both barriers.
bm = bmesh.new()
for lat in (-ROAD_W / 2 + 0.1, ROAD_W / 2 - 0.1):
    for zr in (1.12, 1.42):
        sweep(bm, [road(-ROAD_BACK, lat, zr), road(ROAD_AHEAD, lat, zr)], [(-0.05, -0.07), (0.05, -0.07), (0.05, 0.07), (-0.05, 0.07)])
    s = -ROAD_BACK + 0.5
    while s < ROAD_AHEAD:
        box(bm, road(s, lat, 1.1), Vector((0.12, 0.12, 0.5)), ROAD_HEADING)
        s += 2.5
mesh_object('City.Rails', bm, MATS['rail'])

# --- A second freeway, lower, off to the right: it runs alongside, then curves away right and climbs ------------------


def fw_path(step=6.0):
    """Centre line of the second freeway, in the deck's frame (s along, lateral) then placed in the world."""
    pts = []
    s0, lat0 = -80.0, -24.0
    straight, radius, turn, tail = 210.0, 170.0, math.radians(72), 170.0
    total = straight + radius * turn + tail
    t = 0.0
    while t <= total + 0.01:
        if t <= straight:
            s, lat = s0 + t, lat0
        elif t <= straight + radius * turn:
            a = (t - straight) / radius
            s, lat = s0 + straight + radius * math.sin(a), lat0 - radius * (1 - math.cos(a))
        else:
            es, el = s0 + straight + radius * math.sin(turn), lat0 - radius * (1 - math.cos(turn))
            s, lat = es + math.cos(turn) * (t - straight - radius * turn), el - math.sin(turn) * (t - straight - radius * turn)
        k = min(1.0, max(0.0, (t - 150) / (total - 150)))
        p = road(s, lat)
        p.z = DECK_Z + 1.5 + 24.0 * k * k * (3 - 2 * k)
        pts.append(p)
        t += step
    return pts


FW = fw_path()
FW_W = 13.0
half = FW_W / 2
FW_PROFILE = [(-half, -1.2), (half, -1.2), (half, 0.9), (half - 0.2, 0.9), (half - 0.32, 0.36), (half - 0.55, 0.1),
              (half - 0.6, 0.0), (-half + 0.6, 0.0), (-half + 0.55, 0.1), (-half + 0.32, 0.36), (-half + 0.2, 0.9),
              (-half, 0.9)]
bm = bmesh.new()
sweep(bm, FW, FW_PROFILE)
sweep(bm, [p + Vector((0, 0, -1.2)) for p in FW], [(-4.5, 0), (4.5, 0), (3.5, -2.4), (-3.5, -2.4)])
for i, p in enumerate(FW):
    if i % 6 == 3:
        t = FW[min(i + 1, len(FW) - 1)] - FW[i - 1]
        box(bm, Vector((p.x, p.y, (p.z - 3.6 + GROUND_Z) / 2)), Vector((3.0, 3.0, p.z - 3.6 - GROUND_Z)))
        box(bm, Vector((p.x, p.y, p.z - 4.0)), Vector((3.6, 10.0, 1.6)), math.atan2(t.y, t.x))
mesh_object('City.Freeway2', bm, MATS['concrete'])

bm = bmesh.new()
for a in (-half + 0.1, half - 0.1):
    rail_path = []
    for i, p in enumerate(FW):
        t = FW[min(i + 1, len(FW) - 1)] - FW[max(i - 1, 0)]
        t.z = 0
        t.normalize()
        rail_path.append(p + Vector((t.y, -t.x, 0)) * a)
    for zr in (1.12, 1.42):
        sweep(bm, [q + Vector((0, 0, zr)) for q in rail_path], [(-0.05, -0.07), (0.05, -0.07), (0.05, 0.07), (-0.05, 0.07)])
    for i in range(len(rail_path) - 1):
        for f in (0.0, 0.5):
            box(bm, rail_path[i].lerp(rail_path[i + 1], f) + Vector((0, 0, 1.1)), Vector((0.12, 0.12, 0.5)))
mesh_object('City.Freeway2Rails', bm, MATS['rail'])


# --- The gantry overhead (top left of the landing shot), dripping black -----------------------------------------------
# A heavy steel deck on concrete legs beside the road's left edge, overhanging the top left of the shot: its front edge
# runs diagonally away from the camera (as the concept's does, so its fascia of arch-topped rusted plates faces us),
# with girders and a lit doorway beneath and a lattice mast on top. Black ooze pours over the fascia and hangs from it
# in long strands. Built in its own frame: t along the front edge (0 at the far end, negative toward the camera), l
# back into the deck (left). Placed from the concept: the fascia's far bottom corner sits at screen (398, 168), its edge
# leaving the frame top left. Clear of the journey camera's descent (art/build-journey.py: x -9 -> -27 at y -1.6 ->
# -2.5, z -6.4 -> -10.55) and of the planter's falls at the origin.
GANTRY_HEADING = math.radians(-34.7)
GE = Vector((math.cos(GANTRY_HEADING), math.sin(GANTRY_HEADING), 0))  # along the front edge, away from the camera
GL = Vector((-GE.y, GE.x, 0))  # back into the deck
GANTRY_F = Vector((-12.6, 1.03, 0))  # the front edge's far end
GANTRY_T = (-24.0, 0.0)  # t extent
GANTRY_D = 15.0  # l depth
GANTRY_U = -4.3  # underside of the slab
GANTRY_TOP = GANTRY_U + 0.6
FASCIA_L = -0.15  # the fascia plates' plane, a little proud of the slab's edge
FASCIA_LOW = GANTRY_U - 0.35
FASCIA_HIGH = GANTRY_TOP + 1.0


def g(t, l, z):
    return GANTRY_F + GE * t + GL * l + Vector((0, 0, z))


def gbox(bm, t, l, z, size, bare=False):
    box(bm, g(t, l, z), size, GANTRY_HEADING, bare)


gt_mid = (GANTRY_T[0] + GANTRY_T[1]) / 2
gt_len = GANTRY_T[1] - GANTRY_T[0]
bm = bmesh.new()
# Slab, cross I-beams (across the edge) and girders along it.
gbox(bm, gt_mid, GANTRY_D / 2, GANTRY_U + 0.3, Vector((gt_len, GANTRY_D, 0.6)))
t = GANTRY_T[0] + 1.0
while t < GANTRY_T[1]:
    gbox(bm, t, GANTRY_D / 2, GANTRY_U - 0.4, Vector((0.3, GANTRY_D - 0.4, 0.8)))
    gbox(bm, t, GANTRY_D / 2, GANTRY_U - 0.78, Vector((0.7, GANTRY_D - 0.4, 0.08)))
    t += 3.0
for l in (0.5, 4.5, 9.0, 13.5):
    gbox(bm, gt_mid, l, GANTRY_U - 0.55, Vector((gt_len, 0.4, 1.1)))
    gbox(bm, gt_mid, l, GANTRY_U - 1.1, Vector((gt_len, 0.9, 0.1)))
# The fascia's frame: a heavy bottom flange, a cap rail, stiffener posts between the plates.
gbox(bm, gt_mid, FASCIA_L + 0.05, FASCIA_LOW - 0.2, Vector((gt_len, 0.7, 0.45)))
gbox(bm, gt_mid, FASCIA_L + 0.3, FASCIA_HIGH, Vector((gt_len, 0.3, 0.25)))
PANEL = 2.4
t = GANTRY_T[0]
while t <= GANTRY_T[1] + 0.01:
    gbox(bm, t, FASCIA_L + 0.05, (FASCIA_LOW + FASCIA_HIGH) / 2, Vector((0.28, 0.4, FASCIA_HIGH - FASCIA_LOW)))
    t += PANEL
# A lattice mast standing near the far end, up out of frame.
MAST = g(-2.5, 3.5, GANTRY_TOP)
for dx in (-1.2, 1.2):
    for dy in (-1.2, 1.2):
        beam(bm, MAST + Vector((dx, dy, 0)), MAST + Vector((dx * 0.6, dy * 0.6, 22)), 0.28)
for k in range(8):
    z0, z1 = MAST.z + k * 2.75, MAST.z + (k + 1) * 2.75
    s0, s1 = 1.2 - 0.6 * k / 8, 1.2 - 0.6 * (k + 1) / 8
    for (ax, ay), (bx, by) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
        beam(bm, Vector((MAST.x + ax * s0, MAST.y + ay * s0, z0)), Vector((MAST.x + bx * s1, MAST.y + by * s1, z1)), 0.12)
        beam(bm, Vector((MAST.x + ax * s1, MAST.y + ay * s1, z1)), Vector((MAST.x + bx * s1, MAST.y + by * s1, z1)), 0.12)
# A Warren truss along the edge above the fascia.
TRUSS_LOW, TRUSS_HIGH = FASCIA_HIGH + 0.2, FASCIA_HIGH + 2.6
for k in range(int(gt_len / 2.0)):
    ta = GANTRY_T[1] - 0.5 - k * 2.0
    beam(bm, g(ta, 1.0, TRUSS_LOW), g(ta - 2.0, 1.0, TRUSS_HIGH), 0.16)
    beam(bm, g(ta - 2.0, 1.0, TRUSS_HIGH), g(ta - 2.0, 1.0, TRUSS_LOW), 0.16)
beam(bm, g(GANTRY_T[1] - 0.5, 1.0, TRUSS_HIGH), g(GANTRY_T[0], 1.0, TRUSS_HIGH), 0.3)
beam(bm, g(GANTRY_T[1] - 0.5, 1.0, TRUSS_LOW), g(GANTRY_T[0], 1.0, TRUSS_LOW), 0.3)
mesh_object('City.Gantry', bm, MATS['steel'])

# Rusted plates on the fascia: arch-topped, set between the stiffeners.
bm = bmesh.new()
r_top = PANEL / 2 - 0.16
h_plate = FASCIA_HIGH - FASCIA_LOW - r_top - 0.15
arch = [(-r_top, 0.0), (r_top, 0.0)] + [(math.cos(math.pi * k / 8) * r_top, h_plate + math.sin(math.pi * k / 8) * r_top) for k in range(9)]
t = GANTRY_T[0] + PANEL / 2
while t < GANTRY_T[1]:
    prism(bm, arch, g(t, FASCIA_L, FASCIA_LOW), GE, GL, 0.18)
    t += PANEL
mesh_object('City.GantryPanels', bm, MATS['rust'])

# The legs stand on a platform of their own beside the road (lower than the deck), down to the ground; a wall between
# the front legs has a lit doorway in it (the light under the gantry).
PLAT_Z = DECK_Z - 0.3
bm = bmesh.new()
gbox(bm, gt_mid + 0.5, GANTRY_D / 2 - 0.5, PLAT_Z - 0.6, Vector((gt_len + 1.0, GANTRY_D + 1.0, 1.2)))
for t in (GANTRY_T[0] + 3, GANTRY_T[1] - 3):
    gbox(bm, t, GANTRY_D / 2, (PLAT_Z - 1.2 + GROUND_Z) / 2, Vector((2.4, 2.4, PLAT_Z - 1.2 - GROUND_Z)))
LEGS_T = (-2.0, -9.0, -16.0, -23.0)
for t in LEGS_T:
    for l in (2.2, 12.0):
        gbox(bm, t, l, (PLAT_Z + GANTRY_U - 1.1) / 2, Vector((1.5, 1.5, GANTRY_U - 1.1 - PLAT_Z)))
        gbox(bm, t, l, GANTRY_U - 1.6, Vector((2.1, 2.1, 0.9)))
gbox(bm, -5.5, 2.2, PLAT_Z + 1.2, Vector((5.5, 0.6, 2.4)))
gbox(bm, -5.5, 2.2, GANTRY_U - 2.6, Vector((5.5, 0.6, 1.4)))
for t in (-7.6, -3.4):
    gbox(bm, t, 2.2, (PLAT_Z + GANTRY_U - 1.9) / 2, Vector((1.0, 0.6, GANTRY_U - 1.9 - PLAT_Z)))
mesh_object('City.GantryPiers', bm, MATS['concrete'])

bm = bmesh.new()
# Strip lights under the slab, between the beams, and the doorway's glow.
for t in (-2.5, -8.5, -14.5):
    gbox(bm, t, 6.0, GANTRY_U - 0.12, Vector((0.25, 3.0, 0.12)))
gbox(bm, -5.5, 2.6, PLAT_Z + 1.25, Vector((3.2, 0.1, 2.3)))
gbox(bm, -5.5, 1.85, PLAT_Z + 2.55, Vector((3.0, 0.15, 0.2)))
mesh_object('City.GantryLamps', bm, MATS['lamp'])


# Ooze: thick strands pouring over the fascia and hanging from its lip and the girders, tapering, with a bead at the tip.
def strand(bm, top, length, r0, sides=7, sway=Vector()):
    ts = (0.0, 0.05, 0.14, 0.28, 0.46, 0.64, 0.76, 0.86, 0.93, 0.975, 1.0)
    rs = (1.7, 1.25, 0.95, 0.78, 0.62, 0.48, 0.42, 0.62, 0.8, 0.55, 0.0)
    rings = []
    for t, rr in zip(ts, rs):
        c = top + Vector((0, 0, -length * t)) + sway * math.sin(t * math.pi)
        if rr == 0:
            rings.append([bm.verts.new(c)])
            continue
        rings.append([bm.verts.new(c + Vector((math.cos(2 * math.pi * k / sides), math.sin(2 * math.pi * k / sides), 0)) * r0 * rr)
                      for k in range(sides)])
    faces = []
    for a, b in zip(rings, rings[1:]):
        for k in range(sides):
            if len(b) == 1:
                faces.append(bm.faces.new((a[k], a[(k + 1) % sides], b[0])))
            else:
                faces.append(bm.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k])))
    faces.append(bm.faces.new(list(reversed(rings[0]))))
    bmesh.ops.recalc_face_normals(bm, faces=faces)


bm = bmesh.new()
# Down the fascia's face and off its lip, thickest and longest near the camera (the concept's foreground strands).
for i in range(72):
    t = rnd.uniform(GANTRY_T[0] + 4, GANTRY_T[1] - 0.3)
    near = max(0.0, min(1.0, -t / 14.0))
    length = (FASCIA_HIGH - FASCIA_LOW) + 0.3 + rnd.random() ** 1.4 * (1.8 + 3.5 * near)
    r = 0.06 + rnd.random() * 0.07 + 0.06 * near
    top = g(t, FASCIA_L - 0.14 - rnd.random() * 0.05, FASCIA_HIGH - 0.1 - rnd.random() * 0.6)
    strand(bm, top, length, r, sway=-GL * 0.12 * rnd.random())
# Long ropes from the lip nearest the camera, some all the way down.
for t, length in ((-14.0, 6.4), (-12.6, 4.6), (-11.0, 6.1), (-9.4, 3.6), (-7.9, 5.2), (-6.2, 2.8), (-4.4, 4.2), (-17.0, 6.0)):
    strand(bm, g(t, FASCIA_L - 0.3, FASCIA_LOW - 0.3), length, 0.1, sway=-GL * 0.25)
# Strands from the girders under the slab.
for i in range(18):
    strand(bm, g(rnd.uniform(-20.0, -1.0), rnd.choice((0.5, 4.5, 9.0)), GANTRY_U - 1.1), 0.6 + rnd.random() ** 2 * 3.0,
           0.04 + rnd.random() * 0.04)
# A thick roll of ooze along the fascia's cap, where it spills over.
lip = [g(GANTRY_T[0] + i * 1.0, FASCIA_L - 0.05, FASCIA_HIGH + 0.05 * math.sin(i * 1.7)) for i in range(int(gt_len) + 1)]
sweep(bm, lip, [(math.cos(2 * math.pi * k / 7) * 0.22, math.sin(2 * math.pi * k / 7) * 0.16) for k in range(7)])
drips = mesh_object('City.Drips', bm, MATS['ooze'], smooth=True)

# A black pool spreading over the road's left lanes, between the camera and the bike, and one under the ropes.
bm = bmesh.new()
for centre, rx, ry, seg in ((Vector((-20.0, -0.4, DECK_Z + 0.01)), 4.0, 1.2, 48), (g(-9.0, 1.2, PLAT_Z + 0.01), 4.5, 1.2, 40)):
    res = bmesh.ops.create_circle(bm, cap_ends=True, segments=seg, radius=1.0)
    for v in res['verts']:
        a = math.atan2(v.co.y, v.co.x)
        k = 1 + 0.25 * math.sin(a * 3 + 1) + 0.15 * math.sin(a * 7)
        v.co.x *= rx * k
        v.co.y *= ry * k
    bmesh.ops.rotate(bm, cent=Vector(), matrix=Matrix.Rotation(ROAD_HEADING, 3, 'Z'), verts=res['verts'])
    bmesh.ops.translate(bm, vec=centre, verts=res['verts'])
mesh_object('City.Puddle', bm, MATS['ooze'], smooth=True)


# --- The city below --------------------------------------------------------------------------------------------------
# Gothic towers: a base block and setback tiers, crenellated parapets, corner turrets and buttress piers ending in
# pinnacles, and a crown (needle, pinnacle cluster, antennae). Merged by distance band so the site draws them in a few
# calls (and can fade the far ones into the fog). Detail drops with distance.

placed = []  # (x, y, radius) footprints, to keep towers from swallowing each other


def crenellate(bm, x, y, w, d, z, rot, merlon):
    """A parapet with merlons round a w x d roof at height z."""
    for side, (length, nx, ny) in enumerate(((w, 0, 1), (d, 1, 0), (w, 0, -1), (d, -1, 0))):
        off = (d if nx == 0 else w) / 2
        along = (1, 0) if nx == 0 else (0, 1)
        cx, cy = offset(x, y, nx * off, ny * off, rot)
        size = Vector((length if nx == 0 else merlon * 0.6, merlon * 0.6 if nx == 0 else length, merlon * 0.7))
        box(bm, Vector((cx, cy, z + merlon * 0.35)), size, rot, bare=True)
        n = max(2, int(length / (merlon * 2.6)))
        for i in range(n):
            f = (i + 0.5) / n - 0.5
            mx, my = offset(x, y, nx * off + along[0] * f * length, ny * off + along[1] * f * length, rot)
            box(bm, Vector((mx, my, z + merlon * 1.05)), Vector((merlon, merlon, merlon * 0.7)), rot, bare=True)


def antenna(bm, x, y, z, length, t):
    box(bm, Vector((x, y, z + length / 2)), Vector((t, t, length)), bare=True)
    for k in range(2):
        zc = z + length * (0.35 + 0.25 * k)
        box(bm, Vector((x, y, zc)), Vector((t * 5, t * 0.8, t * 0.8)), bare=True)


def tower(bm, x, y, w, d, height, rot, detail, dist, crown=None):
    """A gothic tower on the ground at (x, y). detail 2: near (parapets on every tier), 1: mid, 0: far (blocks + crown)."""
    thin = max(0.5, dist * 0.0022)  # antennae/needles stay at least ~1.5 px wide from the landing camera
    z = GROUND_Z
    tiers = rnd.choice((2, 3, 3, 4)) if detail else rnd.choice((1, 2, 2, 3))
    fr = [rnd.uniform(0.85, 1.15) * 0.62 ** t for t in range(tiers)]
    fr[0] *= 1.4
    hs = [height * f / sum(fr) for f in fr]
    merlon = max(1.2, min(w, d) * 0.07, dist * 0.003)
    for t, h in enumerate(hs):
        last = t == tiers - 1
        box(bm, Vector((x, y, z + h / 2)), Vector((w, d, h)), rot)
        top = z + h
        if detail >= 1 and t == 0 and rnd.random() < 0.4:
            # Corner buttress piers, a little proud of the walls and above the roof, each ending in a pinnacle.
            pw = max(1.0, min(w, d) * 0.11)
            spiky = rnd.random() < 0.5
            ph = h * rnd.uniform(1.02, 1.12) if not last else h + merlon * 2
            for sx in (-1, 1):
                for sy in (-1, 1):
                    px, py = offset(x, y, sx * (w / 2 - pw * 0.3), sy * (d / 2 - pw * 0.3), rot)
                    box(bm, Vector((px, py, z + ph / 2)), Vector((pw, pw, ph)), rot, bare=True)
                    if spiky:
                        spike(bm, px, py, z + ph, pw * 0.55, pw * rnd.uniform(3, 6), rot)
        if (detail >= 1 and last) or (detail >= 2 and rnd.random() < 0.35) or (last and rnd.random() < 0.4):
            crenellate(bm, x, y, w, d, top, rot, merlon)
        elif not last and rnd.random() < 0.6:
            # A plain ledge at the setback.
            box(bm, Vector((x, y, top + merlon * 0.3)), Vector((w * 1.02, d * 1.02, merlon * 0.6)), rot, bare=True)
        z = top
        if not last:
            w *= rnd.uniform(0.62, 0.8)
            d *= rnd.uniform(0.62, 0.8)
    crown = crown or rnd.choice(('needle', 'needle', 'cluster', 'crenel', 'crenel', 'crenel', 'antenna', 'stepped', 'stepped'))
    m = min(w, d)
    if crown == 'needle':
        box(bm, Vector((x, y, z + m * 0.25)), Vector((m * 0.6, m * 0.6, m * 0.5)), rot)
        spike(bm, x, y, z + m * 0.5, m * 0.3, height * rnd.uniform(0.18, 0.4), rot)
        for sx in (-1, 1):
            for sy in (-1, 1):
                px, py = offset(x, y, sx * m * 0.4, sy * m * 0.4, rot)
                spike(bm, px, py, z, max(0.6, m * 0.06), m * rnd.uniform(0.6, 1.1), rot)
    elif crown == 'cluster':
        for sx in (-1, 1):
            for sy in (-1, 1):
                px, py = offset(x, y, sx * m * 0.38, sy * m * 0.38, rot)
                th = m * rnd.uniform(0.4, 0.8)
                box(bm, Vector((px, py, z + th / 2)), Vector((m * 0.16, m * 0.16, th)), rot, bare=True)
                spike(bm, px, py, z + th, m * 0.1, m * rnd.uniform(0.9, 1.6), rot)
        th = m * rnd.uniform(0.6, 1.1)
        box(bm, Vector((x, y, z + th / 2)), Vector((m * 0.4, m * 0.4, th)), rot)
        spike(bm, x, y, z + th, m * 0.22, m * rnd.uniform(1.8, 3.2), rot)
    elif crown == 'crenel':
        for k in range(rnd.choice((1, 2, 3))):
            px, py = offset(x, y, rnd.uniform(-0.35, 0.35) * w, rnd.uniform(-0.35, 0.35) * d, rot)
            antenna(bm, px, py, z, height * rnd.uniform(0.08, 0.2), thin)
        if rnd.random() < 0.5:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    px, py = offset(x, y, sx * w * 0.45, sy * d * 0.45, rot)
                    spike(bm, px, py, z + merlon * 1.4, max(0.6, merlon * 0.6), merlon * rnd.uniform(3, 6), rot)
    elif crown == 'antenna':
        box(bm, Vector((x, y, z + m * 0.2)), Vector((m * 0.5, m * 0.5, m * 0.4)), rot)
        antenna(bm, x, y, z + m * 0.4, height * rnd.uniform(0.2, 0.35), thin * 1.4)
    else:  # stepped
        h1 = m * 0.6
        box(bm, Vector((x, y, z + h1 / 2)), Vector((m * 0.6, m * 0.6, h1)), rot)
        box(bm, Vector((x, y, z + h1 + h1 * 0.3)), Vector((m * 0.35, m * 0.35, h1 * 0.6)), rot)
        spike(bm, x, y, z + h1 * 1.6, m * 0.17, m * 1.2, rot)


def horizontal(p):
    return math.hypot(p.x - EYE.x, p.y - EYE.y)


def clear_of_view(x, y, radius=0.0):
    """Keep a channel open around the falls and the deck (nothing built right in front of the overlook), and keep the
    freeways and the viaduct clear."""
    if x < 25 + radius and -40 - radius < y < 40 + radius:
        return False
    for line in KEEP_CLEAR:
        for a, b in zip(line, line[1:]):
            ab = b - a
            ab.z = 0
            t = max(0.0, min(1.0, (Vector((x, y, 0)) - Vector((a.x, a.y, 0))).dot(ab) / ab.length_squared))
            q = Vector((a.x, a.y, 0)) + ab * t
            if (Vector((x, y, 0)) - q).length < radius + 14:
                return False
    return True


def free_spot(x, y, radius, slack=0.75):
    return all(math.hypot(x - px, y - py) > (radius + pr) * slack for px, py, pr in placed)


# The arched viaduct: level, from left of centre in the far middle distance to off the right edge, nearer there.
VIADUCT_Z = 84.0
VIADUCT_SX, VIADUCT_DEPTH = (560, 1360), (480, 360)
va = screen_point(VIADUCT_SX[0], 360, VIADUCT_DEPTH[0])
vb = screen_point(VIADUCT_SX[1], 360, VIADUCT_DEPTH[1])
VA, VB = Vector((va.x, va.y, VIADUCT_Z)), Vector((vb.x, vb.y, VIADUCT_Z))
VIADUCT_SY = (to_screen(VA)[1], to_screen(VB)[1])
print('viaduct deck on screen', [tuple(round(c) for c in to_screen(p)) for p in (VA, VB)])
KEEP_CLEAR = [[road(-ROAD_BACK), road(ROAD_AHEAD)], FW, [VA - (VB - VA).normalized() * 40, VB + (VB - VA).normalized() * 60]]

bands = {'Near': (0, 380), 'Mid': (380, 650), 'Far': (650, 1000), 'Back': (1000, 2000)}
band_bm = {b: bmesh.new() for b in bands}
DETAIL = {'Near': 2, 'Mid': 2, 'Far': 1, 'Back': 0}


def band_of(r):
    for b, (r0, r1) in bands.items():
        if r0 <= r < r1:
            return b
    return 'Back'


def tower_at(sx, top_sy, depth, width, crown=None, aspect=None, force=False):
    if not force and VIADUCT_SX[0] - 30 < sx < VIADUCT_SX[1]:
        # In front of the viaduct, stay below its deck so its arches read against the city behind.
        f = (sx - VIADUCT_SX[0]) / (VIADUCT_SX[1] - VIADUCT_SX[0])
        if depth < VIADUCT_DEPTH[0] + (VIADUCT_DEPTH[1] - VIADUCT_DEPTH[0]) * f + 30:
            top_sy = max(top_sy, VIADUCT_SY[0] + (VIADUCT_SY[1] - VIADUCT_SY[0]) * f + 70)
    p = screen_point(sx, top_sy, depth)
    r = horizontal(p)
    if r < 200:
        return False
    d = width * (aspect or rnd.uniform(0.75, 1.25))
    radius = max(width, d) / 2
    if not force and (not clear_of_view(p.x, p.y, radius) or not free_spot(p.x, p.y, radius)):
        return False
    height = (p.z - GROUND_Z) * 0.86  # the crown makes up the rest
    band = band_of(r)
    tower(band_bm[band], p.x, p.y, width, d, height, rnd.uniform(-0.3, 0.3), DETAIL[band], r, crown)
    placed.append((p.x, p.y, radius))
    return True


# Heroes, where the concept has them: (screen x, top y, depth along the view, width m, crown).
HEROES = [
    (1262, 50, 330, 64, 'crenel'),  # the giant on the right edge
    (470, 120, 410, 58, 'crenel'),  # the dark lit block left of centre
    (560, 150, 440, 50, 'cluster'),
    (650, 40, 600, 52, 'crenel'),  # the tall slender one left of the spire
    (727, 185, 640, 22, 'needle'),
    (1012, 120, 560, 50, 'crenel'),
    (1062, 185, 660, 26, 'cluster'),
    (1102, 170, 780, 22, 'needle'),
    (1142, 215, 840, 26, 'antenna'),
    (1185, 185, 800, 22, 'needle'),
    (1168, 250, 640, 32, 'crenel'),
    (395, 165, 760, 34, 'cluster'),
    (300, 225, 680, 30, 'antenna'),
    (232, 185, 720, 30, 'needle'),
    (160, 240, 620, 28, 'crenel'),
    (60, 150, 520, 40, 'crenel'),
    # The spire's attendant needles.
    (935, 60, 930, 24, 'needle'),
    (905, 110, 905, 20, 'needle'),
    (782, 95, 940, 22, 'needle'),
    (757, 140, 900, 20, 'cluster'),
]
for h in HEROES:
    tower_at(*h, force=True)

# The great spire: right of centre, far off, rising out of frame. A cathedral: a stepped core ringed with pinnacles on
# every setback, corner towers and flanking spires climbing its shoulders, a needle out of the top. Lit ribs (site).
spire_at = screen_point(850, 320, 960)
SPIRE = Vector((spire_at.x, spire_at.y))
placed.append((SPIRE.x, SPIRE.y, 150))
bm = bmesh.new()


def pinnacle_ring(bm, cx, cy, w, d, z, step, tall):
    for (length, nx, ny) in ((w, 0, 1), (d, 1, 0), (w, 0, -1), (d, -1, 0)):
        n = max(2, int(length / step))
        off = (d if nx == 0 else w) / 2
        for i in range(n + 1):
            f = i / n - 0.5
            px = cx + nx * off + (f * length if nx == 0 else 0)
            py = cy + ny * off + (f * length if nx != 0 else 0)
            th = tall * rnd.uniform(0.5, 1.0)
            box(bm, Vector((px, py, z + th / 2)), Vector((2.6, 2.6, th)), bare=True)
            spike(bm, px, py, z + th, 1.6, tall * rnd.uniform(1.0, 2.0))


z = GROUND_Z
TIERS = ((200, 150, 200), (172, 126, 160), (146, 106, 140), (122, 88, 120), (100, 72, 110), (80, 58, 100), (60, 44, 90), (40, 30, 80))
for t, (w, d, h) in enumerate(TIERS):
    box(bm, Vector((SPIRE.x, SPIRE.y, z + h / 2)), Vector((w, d, h)))
    # Front buttress fins (the vertical ribs facing the camera) and the corner towers, taller than the tier.
    for k in (-0.3, -0.1, 0.1, 0.3):
        box(bm, Vector((SPIRE.x - w / 2 - 1.5, SPIRE.y + k * d, z + h * 0.52)), Vector((3.0, 3.2, h * 1.04)))
    ct = max(6.0, w * 0.13)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = SPIRE.x + sx * (w / 2 - ct * 0.2), SPIRE.y + sy * (d / 2 - ct * 0.2)
            th = h * rnd.uniform(1.15, 1.4)
            box(bm, Vector((cx, cy, z + th / 2)), Vector((ct, ct, th)))
            pinnacle_ring(bm, cx, cy, ct, ct, z + th, ct, 4.0)
            spike(bm, cx, cy, z + th + 4, ct * 0.42, th * rnd.uniform(0.3, 0.5))
    pinnacle_ring(bm, SPIRE.x, SPIRE.y, w, d, z + h, 9.0 if t < 3 else 7.0, 7.0 if t < 3 else 5.0)
    # Flanking spires climbing the shoulders on the tiers low down.
    if t < 4:
        for sy in (-1, 1):
            fy = SPIRE.y + sy * (d / 2 + 10)
            fw = 18 - t * 2
            fh = h * rnd.uniform(1.3, 1.8)
            box(bm, Vector((SPIRE.x - w * 0.15, fy, z + fh / 2)), Vector((fw, fw, fh)))
            pinnacle_ring(bm, SPIRE.x - w * 0.15, fy, fw, fw, z + fh, fw / 2, 4.0)
            spike(bm, SPIRE.x - w * 0.15, fy, z + fh, fw * 0.45, fh * rnd.uniform(0.4, 0.7))
    z += h
spike(bm, SPIRE.x, SPIRE.y, z, 14.0, 300)
wall_uvs(bm)
mesh_object('City.Spire', bm, MATS['spire'])

# Filler: clustered round the heroes (peaks) with a lower mass between, so sky shows between the clusters.
CLUSTERS = [60, 232, 395, 520, 650, 850, 1012, 1140, 1262]
FILL = {'Near': (50, 230, 380, 240, 420), 'Mid': (100, 380, 650, 200, 380), 'Far': (150, 650, 1000, 180, 330),
        'Back': (170, 1000, 1700, 170, 290)}
for band, (count, d0, d1, sy0, sy1) in FILL.items():
    made = 0
    for _ in range(count * 30):
        if made >= count:
            break
        if rnd.random() < 0.6:
            sx = rnd.gauss(rnd.choice(CLUSTERS), 55)
            top = rnd.uniform(sy0, sy1)
        else:
            sx = rnd.uniform(-160, 1440)
            top = rnd.uniform((sy0 + sy1) / 2, sy1 + 40)
        depth = rnd.uniform(d0, d1)
        width_px = rnd.uniform(26, 75) if band in ('Near', 'Mid') else rnd.uniform(22, 60)
        width = min(75.0, max(14.0, width_px * TAN_H / 640 * depth))
        if tower_at(sx, top, depth, width):
            made += 1

for band, bm in band_bm.items():
    wall_uvs(bm)
    mesh_object(f'City.Towers{band}', bm, MATS['tower'])

# --- The arched viaduct crossing the middle distance on the right ----------------------------------------------------
# Big round arches on tall piers (a tie beam closes each opening's foot), a solid spandrel wall over the arches, a
# cornice and parapets, and lamp posts along it.
bm = bmesh.new()
along = (VB - VA)
span_len = along.length
u = along.normalized()
n = Vector((-u.y, u.x, 0))
rot_v = math.atan2(u.y, u.x)
BAY, PIER, ARCH_R, VW = 40.0, 8.0, 16.0, 13.0
CROWN_GAP = 5.0
spring = VIADUCT_Z - 1.2 - CROWN_GAP - ARCH_R
bays = int(span_len / BAY) + 1
start = -((bays * BAY - span_len) / 2)
for i in range(bays + 1):
    s = start + i * BAY
    c = VA + u * s
    box(bm, Vector((c.x, c.y, (spring + GROUND_Z) / 2)), Vector((PIER, VW, spring - GROUND_Z)), rot_v)
    # A pilaster on the face and a buttress at the foot.
    box(bm, Vector((c.x, c.y, (VIADUCT_Z + GROUND_Z) / 2)), Vector((PIER * 0.5, VW + 2.0, VIADUCT_Z - GROUND_Z)), rot_v)
    if i < bays:
        # The spandrel over this arch: the wall from pier to pier with a semicircular opening under it.
        top_z = VIADUCT_Z - 1.2 - spring
        outline = [(BAY / 2 + ARCH_R, 0.0), (BAY - PIER / 2, 0.0), (BAY - PIER / 2, top_z), (PIER / 2, top_z), (PIER / 2, 0.0),
                   (BAY / 2 - ARCH_R, 0.0)]
        outline += [(BAY / 2 - math.cos(math.pi * k / 12) * ARCH_R, math.sin(math.pi * k / 12) * ARCH_R) for k in range(1, 12)]
        prism(bm, outline, Vector((c.x, c.y, spring)), u, n, VW)
        # The tie beam closing the opening's foot, far below.
        m = c + u * (BAY / 2)
        box(bm, Vector((m.x, m.y, spring - 30)), Vector((BAY - PIER, VW * 0.8, 4.0)), rot_v)
        # A lower arcade: a smaller arch springing from the tie beam (the concept's arches stack).
        lo = [(BAY / 2 + ARCH_R * 0.8, 0.0), (BAY - PIER / 2, 0.0), (BAY - PIER / 2, ARCH_R * 0.8 + 3), (PIER / 2, ARCH_R * 0.8 + 3),
              (PIER / 2, 0.0), (BAY / 2 - ARCH_R * 0.8, 0.0)]
        lo += [(BAY / 2 - math.cos(math.pi * k / 10) * ARCH_R * 0.8, math.sin(math.pi * k / 10) * ARCH_R * 0.8) for k in range(1, 10)]
        prism(bm, lo, Vector((c.x, c.y, spring - 30 - 2.0 - ARCH_R * 0.8 - 3)), u, n, VW * 0.8)
mid = (VA + VB) / 2
box(bm, Vector((mid.x, mid.y, VIADUCT_Z - 0.6)), Vector((bays * BAY + 4, VW + 1.0, 1.2)), rot_v)
box(bm, Vector((mid.x, mid.y, VIADUCT_Z - 2.2)), Vector((bays * BAY + 4, VW + 2.4, 1.6)), rot_v)
for side in (-1, 1):
    p = mid + n * side * (VW / 2)
    box(bm, Vector((p.x, p.y, VIADUCT_Z + 0.6)), Vector((bays * BAY + 4, 0.6, 1.2)), rot_v)
wall_uvs(bm)
mesh_object('City.Viaduct', bm, MATS['concrete'])

# Lamp heads along the viaduct and the second freeway's median (bloom picks these out).
bm = bmesh.new()
lamps_steel = bmesh.new()
for i in range(bays * 2 + 1):
    p = VA + u * (start + i * BAY / 2) - n * (VW / 2 - 0.5)
    box(lamps_steel, Vector((p.x, p.y, VIADUCT_Z + 4)), Vector((0.5, 0.5, 8)))
    box(bm, Vector((p.x, p.y, VIADUCT_Z + 8.2)), Vector((1.4, 1.4, 0.7)))
for i, p in enumerate(FW):
    if i % 6 == 0 and p.x > 0:
        t = FW[min(i + 1, len(FW) - 1)] - FW[i - 1]
        t.z = 0
        t.normalize()
        side = Vector((t.y, -t.x, 0))
        base = p + side * (-half + 0.5) + Vector((0, 0, 0.9))
        box(lamps_steel, base + Vector((0, 0, 4.5)), Vector((0.3, 0.3, 9.0)))
        for sgn in (-1, 1):
            arm = base + side * sgn * 1.4 + Vector((0, 0, 9.0))
            beam(lamps_steel, base + Vector((0, 0, 8.8)), arm, 0.2, bare=False)
            box(bm, arm - Vector((0, 0, 0.2)), Vector((1.0, 0.5, 0.25)))
mesh_object('City.Lamps', bm, MATS['lamp'])
mesh_object('City.LampPosts', lamps_steel, MATS['steel'])

# The bike's mark, for placing it on the site (an empty).
mark = bpy.data.objects.new('City.BikeMark', None)
scene.collection.objects.link(mark)
mark.parent = root
mark.location = BIKE_AT
mark.rotation_euler = (0, 0, math.radians(BIKE_YAW))

for o in root.children:
    if o.type == 'MESH':
        print(f'{o.name:22s} {sum(len(p.vertices) - 2 for p in o.data.polygons):8d} tris')
print('total tris', sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in root.children if o.type == 'MESH'))

# --- A look from the landing camera, to hold against the concept -------------------------------------------------------
cam = bpy.data.objects.new('LandingCam', bpy.data.cameras.new('LandingCam'))
scene.collection.objects.link(cam)
cam.location = EYE
cam.rotation_mode = 'QUATERNION'
cam.rotation_quaternion = (LOOK - EYE).to_track_quat('-Z', 'Y')
cam.data.sensor_fit = 'VERTICAL'
cam.data.sensor_height = 24
cam.data.lens = 12 / math.tan(math.radians(LANDING_FOV / 2))
cam.data.clip_start = 0.1
cam.data.clip_end = 3000
scene.camera = cam


def add_stand_in():
    """A stand-in for the bike: a low dark capsule of its size where the site parks it."""
    bm = bmesh.new()
    box(bm, Vector((0, 0, 0.75)), Vector((2.2, 0.55, 0.7)))
    for x in (-0.8, 0.8):
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.36, radius2=0.36, depth=0.22)
        bmesh.ops.rotate(bm, cent=Vector(), matrix=Matrix.Rotation(math.pi / 2, 3, 'X'), verts=r['verts'])
        bmesh.ops.translate(bm, vec=Vector((x, 0, 0.36)), verts=r['verts'])
    o = mesh_object('BikeStandIn', bm, MATS['rail'], parent=None)
    o.location = SITE_BIKE
    o.rotation_euler = (0, 0, math.radians(BIKE_YAW))
    return o


stand_in = add_stand_in()
world = bpy.data.worlds.new('Night')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.03, 0.06, 0.04, 1)
scene.world = world
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'MATERIAL'
scene.display.shading.show_cavity = True
scene.render.resolution_x, scene.render.resolution_y = RES
scene.render.filepath = RENDER
os.makedirs(os.path.dirname(RENDER), exist_ok=True)
bpy.ops.render.render(write_still=True)
bpy.data.objects.remove(stand_in)

bpy.ops.wm.save_as_mainfile(filepath=BLEND)
for o in bpy.context.view_layer.objects:
    o.select_set(o == root or o.parent == root)
os.makedirs(os.path.dirname(GLB), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=GLB, export_format='GLB', use_selection=True, export_apply=True,
                          export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
                          export_draco_position_quantization=14, export_draco_normal_quantization=8,
                          export_yup=True, export_cameras=False, export_lights=False, export_extras=True)
print('exported', GLB, os.path.getsize(GLB))

# --- A moody EEVEE look, for judging against the concept (not saved: the .blend and glb are already written) ----------
# Approximates the site: a dark green sky lighter at the horizon, depth fog that thickens low down, lit windows from the
# wall UVs (the same grid and hashing idea as components/three/city.tsx), glowing spire ribs, a wet deck.
if os.environ.get('CITY_NO_EEVEE') != '1':
    stand_in = add_stand_in()
    scene.render.engine = 'BLENDER_EEVEE'
    ee = scene.eevee
    ee.taa_render_samples = 32
    if hasattr(ee, 'use_raytracing'):
        ee.use_raytracing = True
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Punchy'
    scene.view_settings.exposure = 0.6
    scene.render.filepath = RENDER_EEVEE
    FOG = (0.07, 0.14, 0.085)

    def link(nt, a, b):
        nt.links.new(a, b)

    def node(nt, kind, **kw):
        nd = nt.nodes.new(kind)
        for k, v in kw.items():
            setattr(nd, k, v)
        return nd

    def math_(nt, op, a, b=None):
        nd = node(nt, 'ShaderNodeMath', operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                nd.inputs[i].default_value = v
            else:
                link(nt, v, nd.inputs[i])
        return nd.outputs[0]

    def vec(nt, x, y, z):
        nd = node(nt, 'ShaderNodeCombineXYZ')
        for i, v in enumerate((x, y, z)):
            if isinstance(v, (int, float)):
                nd.inputs[i].default_value = v
            else:
                link(nt, v, nd.inputs[i])
        return nd.outputs[0]

    def noise(nt, v):
        nd = node(nt, 'ShaderNodeTexWhiteNoise', noise_dimensions='3D')
        link(nt, v, nd.inputs['Vector'])
        return nd.outputs['Value']

    def look(mat, windows=False, ribs=False, rough=None, glow=None):
        nt = mat.node_tree
        p = nt.nodes['Principled BSDF']
        out = nt.nodes['Material Output']
        if rough is not None:
            p.inputs['Roughness'].default_value = rough
        geo = node(nt, 'ShaderNodeNewGeometry')
        pos = node(nt, 'ShaderNodeSeparateXYZ')
        link(nt, geo.outputs['Position'], pos.inputs[0])
        if windows:
            uvn = node(nt, 'ShaderNodeUVMap')
            uvs = node(nt, 'ShaderNodeSeparateXYZ')
            link(nt, uvn.outputs['UV'], uvs.inputs[0])
            u_, v_ = uvs.outputs[0], uvs.outputs[1]
            cu, cv = math_(nt, 'FLOOR', math_(nt, 'DIVIDE', u_, 2.2)), math_(nt, 'FLOOR', math_(nt, 'DIVIDE', v_, 2.8))
            fu, fv = math_(nt, 'FRACT', math_(nt, 'DIVIDE', u_, 2.2)), math_(nt, 'FRACT', math_(nt, 'DIVIDE', v_, 2.8))
            bld = math_(nt, 'ADD', math_(nt, 'FLOOR', math_(nt, 'DIVIDE', pos.outputs[0], 9)),
                        math_(nt, 'MULTIPLY', math_(nt, 'FLOOR', math_(nt, 'DIVIDE', pos.outputs[1], 9)), 17))
            h = noise(nt, vec(nt, cu, cv, bld))
            floor_lit = math_(nt, 'GREATER_THAN', noise(nt, vec(nt, cv, bld, 3.0)), 0.45)
            lit = math_(nt, 'ADD', math_(nt, 'MULTIPLY', math_(nt, 'GREATER_THAN', h, 0.62), floor_lit), math_(nt, 'GREATER_THAN', h, 0.93))
            pane = math_(nt, 'MULTIPLY', math_(nt, 'MULTIPLY', math_(nt, 'GREATER_THAN', fu, 0.22), math_(nt, 'LESS_THAN', fu, 0.78)),
                         math_(nt, 'MULTIPLY', math_(nt, 'GREATER_THAN', fv, 0.28), math_(nt, 'LESS_THAN', fv, 0.8)))
            has = math_(nt, 'GREATER_THAN', u_, -0.5)
            bright = math_(nt, 'ADD', 0.5, math_(nt, 'MULTIPLY', noise(nt, vec(nt, cu, cv, 9.0)), 1.6))
            e = math_(nt, 'MULTIPLY', math_(nt, 'MULTIPLY', lit, pane), math_(nt, 'MULTIPLY', has, bright))
            if ribs:
                rib = math_(nt, 'LESS_THAN', math_(nt, 'ABSOLUTE', math_(nt, 'SUBTRACT', math_(nt, 'FRACT', math_(nt, 'DIVIDE', u_, 9.0)), 0.5)), 0.04)
                e = math_(nt, 'ADD', e, math_(nt, 'MULTIPLY', math_(nt, 'MULTIPLY', rib, has), math_(nt, 'ADD', 0.6, math_(nt, 'MULTIPLY', v_, 0.006))))
            p.inputs['Emission Color'].default_value = (0.62, 1.0, 0.42, 1)
            link(nt, math_(nt, 'MULTIPLY', e, 5.0), p.inputs['Emission Strength'])
        if glow is not None:
            p.inputs['Emission Strength'].default_value = glow
        # Fog: thicker with distance and low down (the mist lying in the streets), over everything.
        cd = node(nt, 'ShaderNodeCameraData')
        low = math_(nt, 'EXPONENT', math_(nt, 'DIVIDE', math_(nt, 'SUBTRACT', GROUND_Z, pos.outputs[2]), 140.0))
        dens = math_(nt, 'MULTIPLY', math_(nt, 'ADD', 0.45, math_(nt, 'MULTIPLY', low, 2.2)), 0.0011)
        fac = math_(nt, 'SUBTRACT', 1.0, math_(nt, 'EXPONENT', math_(nt, 'MULTIPLY', math_(nt, 'MULTIPLY', cd.outputs['View Distance'], dens), -1.0)))
        em = node(nt, 'ShaderNodeEmission')
        em.inputs['Color'].default_value = (*FOG, 1)
        mix = node(nt, 'ShaderNodeMixShader')
        link(nt, fac, mix.inputs[0])
        link(nt, p.outputs[0], mix.inputs[1])
        link(nt, em.outputs[0], mix.inputs[2])
        link(nt, mix.outputs[0], out.inputs['Surface'])

    look(MATS['tower'], windows=True)
    look(MATS['spire'], windows=True, ribs=True)
    look(MATS['deck'], rough=0.12)
    look(MATS['concrete'])
    look(MATS['steel'])
    look(MATS['rust'])
    look(MATS['rail'])
    look(MATS['ooze'])
    look(MATS['lamp'], glow=25.0)
    MATS['ooze'].node_tree.nodes['Principled BSDF'].inputs['Coat Weight'].default_value = 1.0

    # Sky: dark at the zenith, a sickly green glow toward the horizon, cloud mottling.
    wn = world.node_tree
    bg = wn.nodes['Background']
    tc = node(wn, 'ShaderNodeTexCoord')
    sep = node(wn, 'ShaderNodeSeparateXYZ')
    link(wn, tc.outputs['Generated'], sep.inputs[0])
    ramp = node(wn, 'ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.11, 0.19, 0.12, 1)
    ramp.color_ramp.elements[1].position = 0.45
    ramp.color_ramp.elements[1].color = (0.018, 0.03, 0.022, 1)
    clouds = node(wn, 'ShaderNodeTexNoise')
    clouds.inputs['Scale'].default_value = 3.0
    clouds.inputs['Detail'].default_value = 8.0
    link(wn, tc.outputs['Generated'], clouds.inputs['Vector'])
    zc = math_(wn, 'ADD', sep.outputs[2], math_(wn, 'MULTIPLY', math_(wn, 'SUBTRACT', clouds.outputs['Fac'], 0.5), 0.35))
    link(wn, zc, ramp.inputs[0])
    link(wn, ramp.outputs[0], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.0

    # Light: a cold green backlight from beyond the city, warm light under the gantry, a dim fill on the deck.
    def light(name, kind, loc, energy, colour, rot=None, size=None):
        ld = bpy.data.lights.new(name, kind)
        ld.energy = energy
        ld.color = colour
        if size is not None:
            ld.shadow_soft_size = size
        lo = bpy.data.objects.new(name, ld)
        scene.collection.objects.link(lo)
        lo.location = loc
        if rot:
            lo.rotation_euler = rot
        return lo

    light('Moon', 'SUN', (0, 0, 0), 0.6, (0.55, 1.0, 0.6), rot=(math.radians(70), 0, math.radians(-95)))
    light('UnderGantry', 'POINT', g(-6.0, 5.0, GANTRY_U - 0.6), 350, (1.0, 0.85, 0.55), size=1.0)
    light('Door', 'POINT', g(-5.5, 1.0, PLAT_Z + 2.0), 150, (1.0, 0.8, 0.5), size=0.5)
    light('DeckFill', 'POINT', (-18.0, -4.0, DECK_Z + 6), 400, (0.5, 1.0, 0.55), size=3.0)
    bpy.ops.render.render(write_still=True)
    # And once without the stand-in, to judge the city behind it.
    stand_in.hide_render = True
    scene.render.filepath = RENDER_EEVEE.replace('.png', '-nobike.png')
    bpy.ops.render.render(write_still=True)
    try:
        subprocess.run(['magick', CONCEPT, '-resize', f'{RES[0]}x{RES[1]}!', RENDER_EEVEE, '-append', MONTAGE], check=True)
    except Exception as exc:  # magick missing: the renders are still there
        print('montage skipped:', exc)
