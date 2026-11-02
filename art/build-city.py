"""The green city the journey lands in (art/reference/concept-green-city.webp): an elevated freeway at night, the bike parked
on its wet deck, a heavy rusted gantry overhead dripping black, and a dense gothic city of towers falling away below with a
great cathedral spire beyond, an arched viaduct crossing the middle distance and a second freeway curving off right.
Builds art/city.blend from scratch and exports public/models/city.glb.
Run: blender --background --factory-startup --python art/build-city.py

World layout (Blender, z up, metres; the same space as art/micro-biome.blend, so the planter floats over the origin): the
deck's surface is at z -11. The landing shot (EYE, LOOK, LANDING_FOV, BIKE_AT, BIKE_YAW, fitted to the concept) looks
east across a straight freeway running north-east, with the bike parked at its far kerb and the planter's falls behind
the camera, well clear of every deck. The towers stand on the ground far below (z -80).

The skyline is composed in the landing camera's screen space (screen_point): the hero towers, the spire and the viaduct are
placed where the concept has them, then filler towers cluster round them, leaving sky between the clusters.

Renders (with the real bike, public/models/bike.glb): art/renders/city-landing.png (Workbench, shapes),
city-landing-eevee.png (a moody EEVEE stand-in for the site's look: fog, lit windows), city-landing-eevee-nobike.png,
city-montage.png (the concept above the EEVEE render), and *-guides.png (the concept's traced features from
art/reference/concept-guides.json over the concept and over the render, via art/guides.py). CITY_NO_EEVEE=1 skips EEVEE.
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
GUIDES = os.path.join(ROOT_DIR, 'art', 'guides.py')
BIKE_GLB = os.path.join(ROOT_DIR, 'public', 'models', 'bike.glb')

DECK_Z = -11.0
GROUND_Z = -80.0
RES = (1280, 720)
# The landing shot, fitted to the concept by art/align/ (concept-features.json extracted from the concept; optimise.py
# scored the bike's silhouette, headlight and wheels, the kerb and rail lines and the skyline against renders of this
# scene). The camera stands on the bike's right at about knee height, looking across the road at the bike three-quarter
# from the front and on over the city, a touch up. The road runs along the bike, away to the left of the frame (its
# vanishing point far off the left); the bike is parked at its far kerb, the city falling away beyond. The world is
# placed so the camera looks east with the planter's falls (the origin) behind it, 16 m off the road's line.
EYE = Vector((12.0005, -7.9659, -10.4121))
LOOK = Vector((71.9123, -5.3405, -8.4911))
LANDING_FOV = 42.979  # vertical, degrees
BIKE_AT = Vector((14.6317, -6.9347, DECK_Z))
BIKE_YAW = -113.658  # degrees about z (the bike's front is its +x)
# The road's frame: its line (abreast the bike, where the build first parked it) and heading, fixed in the world; the
# bike stands 0.19 m off that line toward the kerb, turned 1.67 deg off the road's line.
ROAD_ORIGIN = Vector((14.46, -6.85, DECK_Z))
ROAD_HEADING = math.radians(64.67)
_bf = Vector((math.cos(math.radians(BIKE_YAW)), math.sin(math.radians(BIKE_YAW)), 0))

# --- Where the landing stands in the world ------------------------------------------------------------------------------
# Everything here is built in the landing's own frame (the values above), then turned and moved as one (LANDING_M) so the
# planter's column (the world's origin, where its falls drop to the city floor) stands in the landing view: PLANTER_DIST
# metres out from the camera, PLANTER_LEFT degrees left of the view's centre, between the road and the city. The journey
# camera then pulls straight back and down from the planter to the landing. The landing is turned so its view heads
# north-east (VIEW_HEADING), the way the hero camera looks at the planter, so the opening barely swings. The shot
# relative to the bike, road and city is unchanged.
VIEW_HEADING = 45.0  # degrees about z, in the world
PLANTER_DIST, PLANTER_LEFT = 55.0, 2.5
_view = LOOK - EYE
_yaw = math.atan2(_view.y, _view.x)
LANDING_ROT = math.radians(VIEW_HEADING) - _yaw
_a = _yaw + math.radians(PLANTER_LEFT)
COLUMN_LOCAL = Vector((EYE.x + math.cos(_a) * PLANTER_DIST, EYE.y + math.sin(_a) * PLANTER_DIST, 0.0))
LANDING_M = Matrix.Rotation(LANDING_ROT, 4, 'Z') @ Matrix.Translation(-COLUMN_LOCAL)
WORLD_OFFSET = (LANDING_M @ Vector((0, 0, 0))).xy
print('landing placed: turned', round(math.degrees(LANDING_ROT), 3), 'deg about z, then offset', tuple(round(c, 4) for c in WORLD_OFFSET))

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


def ray_at_z(sx, sy, z):
    """Where the ray through pixel (sx, sy) of the landing frame meets the height z."""
    d = screen_point(sx, sy, 1.0) - EYE
    return EYE + d * ((z - EYE.z) / d.z)


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
# A long straight elevated freeway on piers, running along the bike: away to the left of the shot (ROAD_AHEAD, toward
# its vanishing point) and back past the camera's right. The bike is parked at its far kerb, a low concrete upstand
# where the deck ends over the drop; the camera stands in the lane beside it. A jersey barrier and rail line the near
# edge, behind the camera. Built in the road's frame: s along it from abreast the bike, lateral to its left (toward
# the camera; negative is the kerb, the city side).
RD = Vector((math.cos(ROAD_HEADING), math.sin(ROAD_HEADING), 0))  # along the road, away to the left of the shot
RL = Vector((-RD.y, RD.x, 0))  # to its left: the bike's right, the camera's side
KERB = -0.85  # the kerb's inner face, from the bike's centre line
KERB_W = 0.4
ROAD_NEAR = 9.0  # the near edge (behind the camera)
BARRIER = 0.6  # a jersey barrier's footprint
ROAD_BACK, ROAD_AHEAD = 140.0, 520.0
ROAD_LEN = ROAD_BACK + ROAD_AHEAD
ROAD_W = ROAD_NEAR - (KERB - KERB_W)
ROAD_MID_S = (ROAD_AHEAD - ROAD_BACK) / 2
ROAD_MID_L = (ROAD_NEAR + KERB - KERB_W) / 2


def road(s, lateral=0.0, z=0.0):
    """A point s metres along the deck from ROAD_ORIGIN, `lateral` metres left of the road's line (toward the camera)."""
    return Vector((ROAD_ORIGIN.x, ROAD_ORIGIN.y, DECK_Z)) + RD * s + RL * lateral + Vector((0, 0, z))


bm = bmesh.new()
box(bm, road(ROAD_MID_S, ROAD_MID_L, -0.6), Vector((ROAD_LEN, ROAD_W, 1.2)), ROAD_HEADING)
deck = mesh_object('City.Deck', bm, MATS['deck'])

# The drivable surface between the kerb and the near barrier, for the site's wet reflector.
DRIVE_L = ((ROAD_NEAR - BARRIER) + KERB) / 2
DRIVE_W = (ROAD_NEAR - BARRIER) - KERB
deck_top = bpy.data.objects.new('City.DeckTop', None)
scene.collection.objects.link(deck_top)
deck_top.parent = root
deck_top.location = road(ROAD_MID_S, DRIVE_L)
deck_top.rotation_euler = (0, 0, ROAD_HEADING)
deck_top['length'] = round(ROAD_LEN, 3)
deck_top['width'] = round(DRIVE_W, 3)
print('DeckTop (landing frame)', tuple(round(c, 3) for c in deck_top.location), 'heading', round(math.degrees(ROAD_HEADING), 2),
      'length', deck_top['length'], 'width', deck_top['width'])

# A jersey barrier's cross-section (a across, to the right of travel; up): outer face at a = 0, safety slope toward -a.
JERSEY = [(0.0, -0.02), (0.0, 0.9), (-0.2, 0.9), (-0.32, 0.36), (-0.55, 0.1), (-0.6, -0.02)]
bm = bmesh.new()
# The kerb on the far edge (its outer face is the deck's edge) and the barrier on the near edge.
# (The concept's proportions, measured by art/align: a ledge at its foot 0.066 m high, a parapet wall 0.20 m with a
# rounded cap, a rail just over it at 0.25 m.)
sweep(bm, [road(-ROAD_BACK, KERB - KERB_W), road(ROAD_AHEAD, KERB - KERB_W)],
      [(0.0, -0.02), (0.0, 0.18), (-0.03, 0.2), (-0.27, 0.2), (-0.3, 0.18), (-0.3, 0.066), (-KERB_W, 0.066),
       (-KERB_W, -0.02)])
sweep(bm, [road(-ROAD_BACK, ROAD_NEAR), road(ROAD_AHEAD, ROAD_NEAR)], [(-a, u) for a, u in JERSEY])
# The box girder under the slab, and piers on cross-heads down into the dark.
box(bm, road(ROAD_MID_S, ROAD_MID_L, -2.4), Vector((ROAD_LEN - 2, ROAD_W - 4, 2.4)), ROAD_HEADING)
s = -ROAD_BACK + 12
while s < ROAD_AHEAD - 4:
    for lat in (KERB - KERB_W + 2.5, ROAD_NEAR - 2.5):
        p = road(s, lat)
        box(bm, Vector((p.x, p.y, (DECK_Z - 3.6 + GROUND_Z) / 2)), Vector((2.4, 2.4, DECK_Z - 3.6 - GROUND_Z)), ROAD_HEADING)
    box(bm, road(s, ROAD_MID_L, -4.2), Vector((2.8, ROAD_W - 1.0, 1.6)), ROAD_HEADING)
    s += 32.0
mesh_object('City.DeckBeams', bm, MATS['concrete'])

# Steel guard rail on posts along the near barrier, and a low rail on short stubs along the kerb's cap (the
# concept's rail, in its proportions: it sits low).
bm = bmesh.new()
lat = KERB - KERB_W + 0.15
sweep(bm, [road(-ROAD_BACK, lat, 0.22), road(ROAD_AHEAD, lat, 0.22)], [(-0.05, -0.025), (0.05, -0.025), (0.05, 0.03), (-0.05, 0.03)])
s = -ROAD_BACK + 0.5
while s < ROAD_AHEAD:
    box(bm, road(s, lat, 0.21), Vector((0.06, 0.06, 0.03)), ROAD_HEADING)
    s += 2.0
lat = ROAD_NEAR - 0.1
for zr in (1.12, 1.42):
    sweep(bm, [road(-ROAD_BACK, lat, zr), road(ROAD_AHEAD, lat, zr)], [(-0.05, -0.07), (0.05, -0.07), (0.05, 0.07), (-0.05, 0.07)])
s = -ROAD_BACK + 0.5
while s < ROAD_AHEAD:
    box(bm, road(s, lat, 1.1), Vector((0.12, 0.12, 0.5)), ROAD_HEADING)
    s += 2.5
mesh_object('City.Rails', bm, MATS['rail'])

# --- The second freeway, lower, beyond the kerb -------------------------------------------------------------------------
# A carriageway alongside ours and FW_DROP lower: its near jersey barrier and rail are the barrier the concept shows
# running across behind the bike and down to the right edge (fitted: rail and base lines of concept-guides.json). A
# branch leaves it and curves away into the city on the right, climbing a little.
FW_W = 13.0
half = FW_W / 2
FW_NEAR = -4.9  # its near barrier's outer face, from the bike's line
FW_LAT = FW_NEAR - half
FW_DROP = 4.65
FW_Z = DECK_Z - FW_DROP
FW_PROFILE = [(-half, -1.2), (half, -1.2), (half, 0.9), (half - 0.2, 0.9), (half - 0.32, 0.36), (half - 0.55, 0.1),
              (half - 0.6, 0.0), (-half + 0.6, 0.0), (-half + 0.55, 0.1), (-half + 0.32, 0.36), (-half + 0.2, 0.9),
              (-half, 0.9)]


def branch_path(step=6.0):
    """The branch: from beside the lower carriageway, back toward the camera's right, curving away into the city."""
    pts = []
    straight = 200.0
    s, lat, a = 180.0, FW_LAT - FW_W - 1.0, 0.0
    radius, turn, tail = 140.0, math.radians(78), 200.0
    t = 0.0
    total = straight + radius * turn + tail
    while t <= total:
        p = road(s, lat)
        p.z = FW_Z + 3.0 * min(1.0, t / total)
        pts.append(p)
        if t >= straight:
            a = min(turn, (t - straight) / radius)
        s -= math.cos(a) * step
        lat -= math.sin(a) * step
        t += step
    return pts


FW = [road(s, FW_LAT, -FW_DROP) for s in range(int(-ROAD_BACK), int(ROAD_AHEAD) + 1, 10)]
BRANCH = branch_path()
bm = bmesh.new()
for path in (FW, BRANCH):
    sweep(bm, path, FW_PROFILE)
    sweep(bm, [p + Vector((0, 0, -1.2)) for p in path], [(-4.5, 0), (4.5, 0), (3.5, -2.4), (-3.5, -2.4)])
    for i, p in enumerate(path):
        if i % 4 == 2:
            t = path[min(i + 1, len(path) - 1)] - path[i - 1]
            box(bm, Vector((p.x, p.y, (p.z - 3.6 + GROUND_Z) / 2)), Vector((3.0, 3.0, p.z - 3.6 - GROUND_Z)))
            box(bm, Vector((p.x, p.y, p.z - 4.0)), Vector((3.6, 10.0, 1.6)), math.atan2(t.y, t.x))
mesh_object('City.Freeway2', bm, MATS['concrete'])

bm = bmesh.new()
for path in (FW, BRANCH):
    for a in (-half + 0.1, half - 0.1):
        rail_path = []
        for i, p in enumerate(path):
            t = path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]
            t.z = 0
            t.normalize()
            rail_path.append(p + Vector((t.y, -t.x, 0)) * a)
        for zr in (1.12, 1.42):
            sweep(bm, [q + Vector((0, 0, zr)) for q in rail_path], [(-0.05, -0.07), (0.05, -0.07), (0.05, 0.07), (-0.05, 0.07)])
        for i in range(len(rail_path) - 1):
            n_posts = max(1, int((rail_path[i + 1] - rail_path[i]).length / 2.5))
            for k in range(n_posts):
                box(bm, rail_path[i].lerp(rail_path[i + 1], k / n_posts) + Vector((0, 0, 1.1)), Vector((0.12, 0.12, 0.5)))
mesh_object('City.Freeway2Rails', bm, MATS['rail'])

# --- The gantry overhead (top left of the landing shot), dripping black -----------------------------------------------
# A heavy steel deck over the lower carriageway beyond the kerb, looming in the top left: its front edge faces the
# camera (a fascia of arch-topped rusted plates over a heavy bottom flange), girders and strip lights beneath, a truss
# and a lattice mast on top, a massive concrete pier under its left. Black ooze pours over the fascia and hangs from it
# in long strands. Placed from the concept's extracted lines (art/align/concept-features.json): the fascia's underside
# falls ~10 deg to its right corner at (398, 177), its soffit barely showing behind; the pier stands at x 110, the ooze
# tips run (150, 300) -> (380, 260), a strip light at (40, 178); nothing of it stands right of x ~400. Built in its own
# frame: t along the front edge (0 at its right end, negative off to the left), l back into the deck, away from us.
FASCIA_LOW = DECK_Z + 3.5  # the fascia's underside
_gl, _gr = ray_at_z(0, 104.6, FASCIA_LOW), ray_at_z(398, 177.2, FASCIA_LOW)
GE = _gr - _gl
GE.z = 0
_edge = GE.length
GE.normalize()
GANTRY_HEADING = math.atan2(GE.y, GE.x)
GL = Vector((-GE.y, GE.x, 0))
if GL.dot(_gr - EYE) < 0:
    GL = -GL
GANTRY_F = Vector((_gr.x, _gr.y, 0))
GANTRY_T = (-(_edge + 18.0), 0.0)  # t extent (on out of frame to the left)
GANTRY_D = 2.5  # l depth (a walkway: its soffit barely shows behind the fascia, as in the concept)
GANTRY_U = FASCIA_LOW + 1.0  # underside of the slab (everything under it stops at the flange's foot, FASCIA_LOW)
GANTRY_TOP = GANTRY_U + 0.6
FASCIA_L = -0.15  # the fascia plates' plane, a little proud of the slab's edge
FASCIA_HIGH = GANTRY_TOP + 1.0
print('gantry: edge', tuple(round(c, 2) for c in _gl), '->', tuple(round(c, 2) for c in _gr), 'heading', round(math.degrees(GANTRY_HEADING), 1))


def g(t, l, z):
    return GANTRY_F + GE * t + GL * l + Vector((0, 0, z))


def gbox(bm, t, l, z, size, bare=False):
    box(bm, g(t, l, z), size, GANTRY_HEADING, bare)


def t_at_screen_x(sx, l=0.0, z=FASCIA_LOW):
    lo, hi = GANTRY_T[0], GANTRY_T[1]
    for _ in range(40):
        mid = (lo + hi) / 2
        if to_screen(g(mid, l, z))[0] < sx:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


gt_mid = (GANTRY_T[0] + GANTRY_T[1]) / 2
gt_len = GANTRY_T[1] - GANTRY_T[0]
bm = bmesh.new()
# Slab, cross beams (across the edge) and girders along it: shallow, so the soffit reads above the fascia's foot.
gbox(bm, gt_mid, GANTRY_D / 2, GANTRY_U + 0.3, Vector((gt_len, GANTRY_D, 0.6)))
t = GANTRY_T[0] + 1.0
while t < GANTRY_T[1]:
    gbox(bm, t, GANTRY_D / 2, GANTRY_U - 0.15, Vector((0.3, GANTRY_D - 0.4, 0.3)))
    t += 3.0
for l in (0.4, 1.3, 2.2):
    gbox(bm, gt_mid, l, GANTRY_U - 0.15, Vector((gt_len, 0.3, 0.3)))
# The fascia's frame: a heavy bottom flange, a cap rail, stiffener posts between the plates.
gbox(bm, gt_mid, FASCIA_L + 0.05, FASCIA_LOW + 0.225, Vector((gt_len, 0.7, 0.45)))
gbox(bm, gt_mid, FASCIA_L + 0.3, FASCIA_HIGH, Vector((gt_len, 0.3, 0.25)))
PANEL = 2.4
t = GANTRY_T[0]
while t <= GANTRY_T[1] + 0.01:
    gbox(bm, t, FASCIA_L + 0.05, (FASCIA_LOW + FASCIA_HIGH) / 2, Vector((0.28, 0.4, FASCIA_HIGH - FASCIA_LOW)))
    t += PANEL
# A lattice mast standing near the far end, up out of frame.
MAST = g(t_at_screen_x(290, 1.25), 1.25, GANTRY_TOP)  # left of x ~400 even at its top
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
h_plate = FASCIA_HIGH - FASCIA_LOW - 0.45 - r_top - 0.15
arch = [(-r_top, 0.0), (r_top, 0.0)] + [(math.cos(math.pi * k / 8) * r_top, h_plate + math.sin(math.pi * k / 8) * r_top) for k in range(9)]
t = GANTRY_T[0] + PANEL / 2
while t < GANTRY_T[1]:
    prism(bm, arch, g(t, FASCIA_L, FASCIA_LOW + 0.45), GE, GL, 0.18)
    t += PANEL
mesh_object('City.GantryPanels', bm, MATS['rust'])

# The legs: a massive pier under the left of the edge (where the concept has it), and lighter ones behind, all the way
# down to the ground.



PIER_T = t_at_screen_x(110, 1.25)
bm = bmesh.new()
gbox(bm, PIER_T, 1.25, (GROUND_Z + GANTRY_U - 1.1) / 2, Vector((2.6, 2.6, GANTRY_U - 1.1 - GROUND_Z)))
gbox(bm, PIER_T, 1.25, GANTRY_U - 1.7, Vector((3.4, 3.4, 1.2)))
for z in range(int(GROUND_Z) + 6, int(GANTRY_U) - 3, 7):
    gbox(bm, PIER_T, 1.25, z, Vector((2.9, 2.9, 0.5)), bare=True)
for t in (PIER_T - 10.0, PIER_T - 20.0):
    gbox(bm, t, 1.25, (GROUND_Z + GANTRY_U - 1.1) / 2, Vector((1.6, 1.6, GANTRY_U - 1.1 - GROUND_Z)))
mesh_object('City.GantryPiers', bm, MATS['concrete'])

bm = bmesh.new()
# Strip lights under the slab, between the beams; the first where the concept's warm light is.
_sl = ray_at_z(40, 178, GANTRY_U - 0.15)
_sl_t = (Vector((_sl.x, _sl.y, 0)) - GANTRY_F).dot(GE)
_sl_l = (Vector((_sl.x, _sl.y, 0)) - GANTRY_F).dot(GL)
for dt in (0.0, -6.0, -12.0):
    gbox(bm, _sl_t + dt, min(GANTRY_D - 0.3, max(0.3, _sl_l)), GANTRY_U - 0.12, Vector((3.0, 0.3, 0.12)))
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




def tip_z(top, target_y):
    """The height below `top` that the landing camera sees at screen y `target_y`."""
    lo, hi = GROUND_Z, top.z
    for _ in range(40):
        mid = (lo + hi) / 2
        if to_screen(Vector((top.x, top.y, mid)))[1] > target_y:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def ooze_tip_y(sx):
    f = min(1.0, max(0.0, (sx - 150) / 230))
    return 300 + (260 - 300) * f


bm = bmesh.new()
# Down the fascia's face and off its lip, the tips along the concept's ooze line, a few ropes hanging much lower.
T_LEFT = t_at_screen_x(-40)
for i in range(30):
    t = T_LEFT + (GANTRY_T[1] - 0.3 - T_LEFT) * (i + rnd.uniform(0.1, 0.9)) / 30
    over = rnd.random() < 0.4  # some pour over the cap and down the plates; most hang from the lip
    top = g(t, FASCIA_L - 0.16 - rnd.random() * 0.05, FASCIA_HIGH - 0.1 if over else FASCIA_LOW - 0.15)
    target = ooze_tip_y(to_screen(top)[0]) + rnd.uniform(-30, 25) + (rnd.random() < 0.15) * rnd.uniform(50, 140)
    length = max(0.5, top.z - tip_z(top, target))
    strand(bm, top, length, 0.08 + rnd.random() ** 2 * 0.2, sway=-GL * 0.15 * rnd.random())
# Strands from the girders under the slab.
for i in range(6):
    strand(bm, g(rnd.uniform(T_LEFT, -1.0), rnd.choice((0.4, 1.3, 2.2)), GANTRY_U - 0.3), 0.6 + rnd.random() ** 2 * 3.0,
           0.04 + rnd.random() * 0.04)
# A thick roll of ooze along the fascia's cap, where it spills over.
lip = [g(GANTRY_T[0] + i * 1.0, FASCIA_L - 0.05, FASCIA_HIGH + 0.05 * math.sin(i * 1.7)) for i in range(int(gt_len) + 1)]
sweep(bm, lip, [(math.cos(2 * math.pi * k / 7) * 0.22, math.sin(2 * math.pi * k / 7) * 0.16) for k in range(7)])
drips = mesh_object('City.Drips', bm, MATS['ooze'], smooth=True)

# Black pools on the deck by the bike, as the concept's slick.
bm = bmesh.new()
for centre, rx, ry, seg in ((road(-1.4, 1.5, 0.01), 2.6, 0.9, 40), (road(3.5, 0.6, 0.01), 1.8, 0.5, 32)):
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
    elif crown == 'flat':  # just the last tier's parapet, a few short pinnacles
        for sx in (-1, 1):
            for sy in (-1, 1):
                px, py = offset(x, y, sx * w * 0.45, sy * d * 0.45, rot)
                spike(bm, px, py, z + merlon * 1.4, max(0.6, merlon * 0.6), merlon * rnd.uniform(2, 4), rot)
    else:  # stepped
        h1 = m * 0.6
        box(bm, Vector((x, y, z + h1 / 2)), Vector((m * 0.6, m * 0.6, h1)), rot)
        box(bm, Vector((x, y, z + h1 + h1 * 0.3)), Vector((m * 0.35, m * 0.35, h1 * 0.6)), rot)
        spike(bm, x, y, z + h1 * 1.6, m * 0.17, m * 1.2, rot)


def horizontal(p):
    return math.hypot(p.x - EYE.x, p.y - EYE.y)


def clear_of_view(x, y, radius=0.0):
    """Keep clear of the planter's falls (the world's origin: COLUMN_LOCAL in this frame), the freeways and the viaduct."""
    if (Vector((x, y, 0)) - COLUMN_LOCAL).length < radius + 12:
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
# The arched viaduct, fitted to the concept's viaduct deck line (640, 300) -> (1280, 265): it crosses the middle
# distance on the right, nearer and higher toward the right edge (climbing gently), below the camera's eye.
VIADUCT_SX, VIADUCT_SY, VIADUCT_DEPTH = (640, 1280), (300, 265), (420, 250)
VA = screen_point(VIADUCT_SX[0], VIADUCT_SY[0], VIADUCT_DEPTH[0])
VB = screen_point(VIADUCT_SX[1], VIADUCT_SY[1], VIADUCT_DEPTH[1])
_vd = (VB - VA).normalized()
VA, VB = VA - _vd * 70, VB + _vd * 90
print('viaduct deck', tuple(round(c, 1) for c in VA), '->', tuple(round(c, 1) for c in VB))
KEEP_CLEAR = [[road(-ROAD_BACK), road(ROAD_AHEAD)], FW, BRANCH, [VA - _vd * 20, VB + _vd * 20]]

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
    height = (p.z - GROUND_Z) * (0.86 if crown in (None, 'needle', 'cluster', 'antenna') else 0.97 if crown == 'crenel' else 0.99)  # the crown makes up the rest
    band = band_of(r)
    tower(band_bm[band], p.x, p.y, width, d, height, rnd.uniform(-0.3, 0.3), DETAIL[band], r, crown)
    placed.append((p.x, p.y, radius))
    return True


# Heroes, where the concept has them (tops from art/align's extracted skyline): (screen x, top y, depth along the
# view, width m, crown).
HEROES = [
    (1250, 72, 330, 30, 'flat'),  # the right tower, off the right edge
    (450, 124, 420, 50, 'crenel'),  # the dark lit blocks left of centre
    (522, 137, 580, 44, 'crenel'),
    (598, 76, 540, 40, 'crenel'),
    (628, 58, 580, 36, 'flat'),
    (650, 30, 600, 50, 'crenel'),  # the tall one left of the spire
    (692, 77, 660, 28, 'needle'),
    (742, 76, 640, 32, 'crenel'),
    (955, 112, 760, 30, 'flat'),
    (990, 121, 560, 44, 'crenel'),
    (1022, 130, 600, 34, 'cluster'),
    (1085, 179, 700, 30, 'flat'),
    (1150, 208, 760, 28, 'flat'),
    (1180, 202, 700, 26, 'flat'),
    (395, 190, 760, 34, 'cluster'),  # behind the gantry
    (300, 225, 680, 30, 'antenna'),
    (232, 200, 720, 30, 'needle'),
    (160, 240, 620, 28, 'crenel'),
    (60, 190, 520, 40, 'crenel'),
    # The spire's attendant needles.
    (930, 104, 930, 24, 'needle'),
    (905, 91, 960, 22, 'needle'),
    (778, 87, 940, 28, 'crenel'),
    (762, 78, 880, 30, 'flat'),
]
for sx, top, depth, width, crown in HEROES:
    # Forced past the spacing check, but kept off the roads and the viaduct: nudged sideways until clear.
    for dsx in (0, -30, 30, -60, 60, -90, 90):
        p = screen_point(sx + dsx, top, depth)
        if clear_of_view(p.x, p.y, width / 2):
            tower_at(sx + dsx, top, depth, width, crown, force=True)
            if dsx:
                print('hero nudged', sx, 'by', dsx)
            break
    else:
        print('hero skipped', sx, top, depth)

# The great spire: right of centre, far off, rising out of frame. A cathedral: a stepped core ringed with pinnacles on
# every setback, corner towers and flanking spires climbing its shoulders, a needle out of the top. Lit ribs (site).
SPIRE_K = 0.54  # its width (art/align: the concept's spire is 0.54 as wide at this distance)
spire_at = screen_point(840, 360, 920)
SPIRE = Vector((spire_at.x, spire_at.y))
placed.append((SPIRE.x, SPIRE.y, 150 * SPIRE_K))
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
TIERS = tuple((w * SPIRE_K, d * SPIRE_K, h) for w, d, h in
              ((200, 150, 200), (172, 126, 160), (146, 106, 140), (122, 88, 120), (100, 72, 110), (80, 58, 100), (60, 44, 90), (40, 30, 80)))
for t, (w, d, h) in enumerate(TIERS):
    box(bm, Vector((SPIRE.x, SPIRE.y, z + h / 2)), Vector((w, d, h)))
    # Front buttress fins (the vertical ribs facing the camera) and the corner towers, taller than the tier.
    for k in (-0.3, -0.1, 0.1, 0.3):
        box(bm, Vector((SPIRE.x - w / 2 - 1.5, SPIRE.y + k * d, z + h * 0.52)), Vector((3.0, 3.2, h * 1.04)))
    ct = max(4.0, w * 0.13)
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
            fy = SPIRE.y + sy * (d / 2 + 10 * SPIRE_K)
            fw = (18 - t * 2) * SPIRE_K
            fh = h * rnd.uniform(1.3, 1.8)
            box(bm, Vector((SPIRE.x - w * 0.15, fy, z + fh / 2)), Vector((fw, fw, fh)))
            pinnacle_ring(bm, SPIRE.x - w * 0.15, fy, fw, fw, z + fh, fw / 2, 4.0)
            spike(bm, SPIRE.x - w * 0.15, fy, z + fh, fw * 0.45, fh * rnd.uniform(0.4, 0.7))
    z += h
spike(bm, SPIRE.x, SPIRE.y, z, 14.0 * SPIRE_K, 300)
wall_uvs(bm)
mesh_object('City.Spire', bm, MATS['spire'])

# Filler: clustered round the heroes (peaks) with a lower mass between, so sky shows between the clusters.
CLUSTERS = [60, 232, 395, 450, 522, 650, 840, 990, 1085, 1150, 1250]
FILL = {'Near': (50, 230, 380, 240, 420), 'Mid': (100, 380, 650, 200, 380), 'Far': (150, 650, 1000, 180, 330),
        'Back': (170, 1000, 1700, 170, 290)}
# The concept's skyline, extracted per column by art/align/extract_concept.py: filler towers stay under it, so only the
# heroes and the spire make the silhouette.
try:
    CONCEPT_SKY = __import__('json').load(open(os.path.join(ROOT_DIR, 'art', 'align', 'concept-features.json')))['skyline']['rows']
except (OSError, KeyError, ValueError):
    CONCEPT_SKY = None
rnd_city = rnd
rnd = random.Random(23)  # the filler draws from its own stream, so changes elsewhere don't reshuffle it
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
        if CONCEPT_SKY and 420 <= sx < RES[0]:
            half_px = width / (TAN_H / (RES[0] / 2) * depth) / 2
            span = CONCEPT_SKY[max(420, int(sx - half_px)):min(RES[0], int(sx + half_px) + 1)]
            if span:
                top = max(top, max(span) + 10)
        if tower_at(sx, top, depth, width):
            made += 1

for band, bm in band_bm.items():
    wall_uvs(bm)
    mesh_object(f'City.Towers{band}', bm, MATS['tower'])

# --- The arched viaduct crossing the middle distance on the right ----------------------------------------------------
# Big round arches on tall piers (a tie beam closes each opening's foot), a solid spandrel wall over the arches, a
# cornice and parapets, and lamp posts along it.
bm = bmesh.new()
along = VB - VA
along.z = 0
span_len = along.length
u = along.normalized()
n = Vector((-u.y, u.x, 0))
rot_v = math.atan2(u.y, u.x)


def vz(s):
    """The viaduct deck's height s metres along it from VA."""
    return VA.z + (VB.z - VA.z) * s / span_len


def vp(s, side=0.0):
    p = VA + u * s + n * side
    return Vector((p.x, p.y, vz(s)))


BAY, PIER, ARCH_R, VW = 40.0, 8.0, 16.0, 13.0
CROWN_GAP = 5.0
bays = int(span_len / BAY)
start = (span_len - bays * BAY) / 2
for i in range(bays + 1):
    s0 = start + i * BAY
    c = vp(s0)
    box(bm, Vector((c.x, c.y, (c.z - 1.2 + GROUND_Z) / 2)), Vector((PIER, VW, c.z - 1.2 - GROUND_Z)), rot_v)
    # A pilaster on the face, proud of the wall.
    box(bm, Vector((c.x, c.y, (c.z + GROUND_Z) / 2)), Vector((PIER * 0.5, VW + 2.0, c.z - GROUND_Z)), rot_v)
    if i < bays:
        # The spandrel over this arch: the wall from pier to pier (its top following the deck) over a round opening.
        spring = vz(s0 + BAY / 2) - 1.2 - CROWN_GAP - ARCH_R
        top_l, top_r = vz(s0 + PIER / 2) - 1.2 - spring, vz(s0 + BAY - PIER / 2) - 1.2 - spring
        outline = [(BAY / 2 + ARCH_R, 0.0), (BAY - PIER / 2, 0.0), (BAY - PIER / 2, top_r), (PIER / 2, top_l), (PIER / 2, 0.0),
                   (BAY / 2 - ARCH_R, 0.0)]
        outline += [(BAY / 2 - math.cos(math.pi * k / 12) * ARCH_R, math.sin(math.pi * k / 12) * ARCH_R) for k in range(1, 12)]
        prism(bm, outline, Vector((c.x, c.y, spring)), u, n, VW)
        # The tie beam closing the tall opening's foot, and a lower arcade under it where there's room.
        m = vp(s0 + BAY / 2)
        tie = max(spring - 34, GROUND_Z + 6)
        box(bm, Vector((m.x, m.y, tie)), Vector((BAY - PIER, VW * 0.8, 4.0)), rot_v)
        lo_spring = tie - 2.0 - ARCH_R * 0.8 - 3
        if lo_spring - 6 > GROUND_Z:
            lo = [(BAY / 2 + ARCH_R * 0.8, 0.0), (BAY - PIER / 2, 0.0), (BAY - PIER / 2, ARCH_R * 0.8 + 3), (PIER / 2, ARCH_R * 0.8 + 3),
                  (PIER / 2, 0.0), (BAY / 2 - ARCH_R * 0.8, 0.0)]
            lo += [(BAY / 2 - math.cos(math.pi * k / 10) * ARCH_R * 0.8, math.sin(math.pi * k / 10) * ARCH_R * 0.8) for k in range(1, 10)]
            prism(bm, lo, Vector((c.x, c.y, lo_spring)), u, n, VW * 0.8)
ends = [vp(start - 2), vp(start + bays * BAY + 2)]
sweep(bm, ends, [(-VW / 2 - 0.5, -1.2), (VW / 2 + 0.5, -1.2), (VW / 2 + 0.5, 0.0), (-VW / 2 - 0.5, 0.0)])
sweep(bm, ends, [(-VW / 2 - 1.2, -3.0), (VW / 2 + 1.2, -3.0), (VW / 2 + 1.2, -1.4), (-VW / 2 - 1.2, -1.4)])
for side in (-1, 1):
    sweep(bm, ends, [(side * VW / 2 - 0.3, 0.0), (side * VW / 2 + 0.3, 0.0), (side * VW / 2 + 0.3, 1.2), (side * VW / 2 - 0.3, 1.2)])
wall_uvs(bm)
mesh_object('City.Viaduct', bm, MATS['concrete'])

# Lamp heads along the viaduct and the second freeway's median (bloom picks these out).
bm = bmesh.new()
lamps_steel = bmesh.new()
for i in range(bays * 2 + 1):
    p = vp(start + i * BAY / 2, -(VW / 2 - 0.5))
    box(lamps_steel, p + Vector((0, 0, 4)), Vector((0.5, 0.5, 8)))
    box(bm, p + Vector((0, 0, 8.2)), Vector((1.4, 1.4, 0.7)))
for i, p in enumerate(FW):
    if i % 6 == 0 and 0 < i < len(FW) - 1:
        t = FW[i + 1] - FW[i - 1]
        t.z = 0
        t.normalize()
        side = Vector((t.y, -t.x, 0))
        base = p + side * (half - 0.5) + Vector((0, 0, 0.9))
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

# Into the world: turn and move the whole landing (meshes baked, markers moved), and the landing's values with it.
for o in root.children:
    if o.type == 'MESH':
        o.data.transform(LANDING_M)
    else:
        o.matrix_basis = LANDING_M @ o.matrix_basis  # (parented to the root, which stays at the identity)
bpy.context.view_layer.update()
EYE_LOCAL, BIKE_LOCAL = EYE.copy(), BIKE_AT.copy()
EYE = LANDING_M @ EYE
LOOK = LANDING_M @ LOOK
BIKE_AT = LANDING_M @ BIKE_AT
BIKE_YAW = BIKE_YAW + math.degrees(LANDING_ROT)
_bf = Vector((math.cos(math.radians(BIKE_YAW)), math.sin(math.radians(BIKE_YAW)), 0))
print('LANDING', 'EYE', tuple(round(c, 4) for c in EYE), 'LOOK', tuple(round(c, 4) for c in LOOK), 'FOV', LANDING_FOV,
      'BIKE_AT', tuple(round(c, 4) for c in BIKE_AT), 'BIKE_YAW', round(BIKE_YAW, 3))
_dt = bpy.data.objects['City.DeckTop']
print('DeckTop', tuple(round(c, 3) for c in _dt.matrix_world.translation), 'heading', round(math.degrees(_dt.matrix_world.to_euler().z), 3),
      'length', _dt['length'], 'width', _dt['width'])

# Checks: nothing within 4 m of the falls' column (z -80 .. +3), and the straight flight from the planter (0, 0, 0.5)
# to the landing eye clear by 1 m.
from mathutils.bvhtree import BVHTree  # noqa: E402
_dg = bpy.context.evaluated_depsgraph_get()
_trees = {o.name: BVHTree.FromObject(o, _dg) for o in root.children if o.type == 'MESH'}
for _name, _tree in _trees.items():
    _hit = [z for z in range(-80, 4) if _tree.find_nearest(Vector((0, 0, z)), 4.0)[0] is not None]
    if _hit:
        print('COLUMN CLASH', _name, 'z', _hit[0], '..', _hit[-1])
    _p0, _p1 = Vector((0, 0, 0.5)), EYE
    _fl = [k for k in range(101) if _tree.find_nearest(_p0.lerp(_p1, k / 100), 1.0)[0] is not None]
    if _fl:
        print('FLIGHT CLASH', _name, 'at', _fl[0], '..', _fl[-1], '% of the way to the eye')
print('planter on the landing screen', [round(c) for c in (lambda v, d: (640 * (1 + v.dot((LOOK - EYE).normalized().cross(Vector((0, 0, 1))).normalized()) / (d * TAN_H)), 360 * (1 - v.dot((LOOK - EYE).normalized().cross(Vector((0, 0, 1))).normalized().cross((LOOK - EYE).normalized())) / (d * TAN_V))))(Vector((0, 0, 0.5)) - EYE, (Vector((0, 0, 0.5)) - EYE).dot((LOOK - EYE).normalized()))],
      'at', round((Vector((0, 0, 0.5)) - EYE).length, 1), 'm')

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


world = bpy.data.worlds.new('Night')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.03, 0.06, 0.04, 1)
scene.world = world
scene.render.resolution_x, scene.render.resolution_y = RES
os.makedirs(os.path.dirname(RENDER), exist_ok=True)

bpy.ops.wm.save_as_mainfile(filepath=BLEND)
for o in bpy.context.view_layer.objects:
    o.select_set(o == root or o.parent == root)
os.makedirs(os.path.dirname(GLB), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=GLB, export_format='GLB', use_selection=True, export_apply=True,
                          export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
                          export_draco_position_quantization=14, export_draco_normal_quantization=8,
                          export_yup=True, export_cameras=False, export_lights=False, export_extras=True)
print('exported', GLB, os.path.getsize(GLB))


def add_bike():
    """The real bike (public/models/bike.glb: origin on the ground between the wheels, front +x) at its landing pose."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=BIKE_GLB)
    imported = set(bpy.data.objects) - before
    rig = bpy.data.objects.new('BikeRig', None)
    scene.collection.objects.link(rig)
    rig.location = BIKE_AT
    rig.rotation_euler = (0, 0, math.radians(BIKE_YAW))
    for o in imported:
        if o.parent is None:
            o.parent = rig
    return rig


def guides(src, out):
    """The concept's traced features over a render (art/guides.py), and that over the concept's own."""
    try:
        subprocess.run(['python3', GUIDES, src, out], check=True)
        subprocess.run(['python3', GUIDES, CONCEPT, out + '.concept.png'], check=True)
        subprocess.run(['magick', out + '.concept.png', out, '-append', out], check=True)
        os.remove(out + '.concept.png')
    except Exception as exc:
        print('guides skipped:', exc)


bike = add_bike()
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'MATERIAL'
scene.display.shading.show_cavity = True
scene.render.filepath = RENDER
bpy.ops.render.render(write_still=True)
guides(RENDER, RENDER.replace('.png', '-guides.png'))

# --- A moody EEVEE look, for judging against the concept (not saved: the .blend and glb are already written) ----------
# Approximates the site: a dark green sky lighter at the horizon, depth fog that thickens low down, lit windows from the
# wall UVs (the same grid and hashing idea as components/three/city.tsx), glowing spire ribs, a wet deck.
if os.environ.get('CITY_NO_EEVEE') != '1':
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

    light('Moon', 'SUN', (0, 0, 0), 0.6, (0.55, 1.0, 0.6), rot=(math.radians(70), 0, math.radians(-95) + LANDING_ROT))
    light('UnderGantry', 'POINT', LANDING_M @ g(_sl_t + 3.0, 1.25, GANTRY_U - 0.8), 1500, (1.0, 0.85, 0.55), size=1.0)
    # Stand-ins for the planter (a clay block over the origin) and its black falls (a column down to the city floor), to
    # see where they land in the shot; not part of the city.
    _bm = bmesh.new()
    box(_bm, Vector((0, 0, 0.9)), Vector((3.2, 3.2, 1.8)))
    mesh_object('PlanterStandIn', _bm, material('StandInClay', (0.55, 0.5, 0.45), 0.8), parent=None)
    _bm = bmesh.new()
    _r = bmesh.ops.create_cone(_bm, cap_ends=True, segments=16, radius1=1.15, radius2=1.15, depth=80.0)
    bmesh.ops.translate(_bm, vec=Vector((0, 0, -40.0)), verts=_r['verts'])
    mesh_object('FallsStandIn', _bm, MATS['ooze'], parent=None)
    light('DeckFill', 'POINT', BIKE_AT + Vector((0, 0, 6)), 300, (0.5, 1.0, 0.55), size=3.0)
    light('BikeKey', 'AREA', EYE + Vector((0, 0, 2.5)) - _bf * 1.0, 120, (0.7, 1.0, 0.75), size=3.0)
    light('KerbGlow', 'POINT', LANDING_M @ road(-7.0, -4.0, 3.0), 250, (0.6, 1.0, 0.65), size=2.0)
    bpy.ops.render.render(write_still=True)
    # And once without the stand-in, to judge the city behind it.
    guides(RENDER_EEVEE, RENDER_EEVEE.replace('.png', '-guides.png'))
    for o in [bike, *bike.children_recursive]:
        o.hide_render = True
    scene.render.filepath = RENDER_EEVEE.replace('.png', '-nobike.png')
    bpy.ops.render.render(write_still=True)
    try:
        subprocess.run(['magick', CONCEPT, '-resize', f'{RES[0]}x{RES[1]}!', RENDER_EEVEE, '-append', MONTAGE], check=True)
    except Exception as exc:  # magick missing: the renders are still there
        print('montage skipped:', exc)
