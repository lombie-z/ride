"""The second city (art/reference/concept-chrome-city.webp): a Y2K futurist utopia at sunset. Pearlescent stacked saucer
terraces with glowing glass bands and palms, an elevated monorail sweeping in from the left, chrome needle spires and
ring-topped towers against a pink-violet sky with a low sun, a glass dome, a reflective lagoon, and a canted billboard
dripping black ooze over a wet plaza where the bike parks.
Builds art/city2.blend from scratch and exports public/models/city2.glb (Draco).
Run: /opt/homebrew/bin/blender --background --factory-startup --python art/build-city2.py
     CITY2_ROUND=r1 names the renders (default r0); CITY2_NO_EEVEE=1 skips the EEVEE renders.

City2's own frame (Blender z up, metres): the road comes in along +X at City2.RoadIn (the local origin, where the site's
straight road hands over; its deck top is z 0), runs 480 m with a lagoon on its right, bends right through 90 deg and
ends on the plaza (floor z 0). The bike parks there facing -Y (City2.BikeMark, its front along the empty's local +X).
The arrival camera (City2.ArrivalCam) stands low on the bike's right and looks across it, east-south-east over a canal at
the city; the low sun sits just right of the spires. City2.ApproachCam is the rider's view coming in along the road,
~420 m out: the road bending right ahead, the lagoon on the right, the city across it.

The arrival shot is fitted to the concept by art/align2/: fit_camera.py fits EYE/LOOK/FOV in the bike's frame to the
concept bike and horizon (arrival-camera.json); this script carries that into City2's frame and composes the city in the
arrival camera's screen space (screen_point) from the features extract_concept.py measured off the concept
(concept-features.json: skyline, sun, billboard screen, dome, monorail, water line). score.py scores the result.

Renders (art/renders/): city2-arrival-<round>.png (EEVEE, with the site's bike), city2-arrival-ids-<round>.png (flat
object-ID colours for score.py), city2-approach.png, and art/align2/out/<round>-overlay.png / -compare.png (from score.py).
"""
import json
import math
import os
import random
import subprocess

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ALIGN = os.path.join(ROOT_DIR, 'art', 'align2')
BLEND = os.path.join(ROOT_DIR, 'art', 'city2.blend')
GLB = os.path.join(ROOT_DIR, 'public', 'models', 'city2.glb')
RENDERS = os.path.join(ROOT_DIR, 'art', 'renders')
BIKE_GLB = os.path.join(ROOT_DIR, 'public', 'models', 'bike.glb')
ROUND = os.environ.get('CITY2_ROUND', 'r0')
FEAT = json.load(open(os.path.join(ALIGN, 'concept-features.json')))
CAMFIT = json.load(open(os.path.join(ALIGN, 'arrival-camera.json')))
RES = (1280, 720)
rnd = random.Random(7)

# --- Layout ------------------------------------------------------------------------------------------------------------
ROAD_W = 11.8              # the site's deck width (components/three/drive.tsx SLAB)
ROAD_STRAIGHT = 480.0      # RoadIn -> the start of the bend
BEND_R = 140.0             # the bend's radius (right, through 90 deg)
ROAD_TAIL = 30.0           # after the bend, heading -Y, to the bike
WATER_Z = -0.7
BIKE_AT = Vector((ROAD_STRAIGHT + BEND_R, -BEND_R - ROAD_TAIL, 0.0))
BIKE_YAW = -90.0           # the bike's front, degrees about z
BIKE_M = Matrix.Translation(BIKE_AT) @ Matrix.Rotation(math.radians(BIKE_YAW), 4, 'Z')

# --- The arrival camera: fitted in the bike's frame, carried into City2's ------------------------------------------------
EYE = BIKE_M @ Vector(CAMFIT['EYE'])
LOOK = BIKE_M @ Vector(CAMFIT['LOOK'])
FOV = CAMFIT['FOV']        # vertical, degrees
FWD = (LOOK - EYE).normalized()
RIGHT = FWD.cross(Vector((0, 0, 1))).normalized()
UP = RIGHT.cross(FWD)
TAN_V = math.tan(math.radians(FOV / 2))
TAN_H = TAN_V * RES[0] / RES[1]
FPX = RES[1] / 2 / TAN_V   # focal length in px

# The approach: the rider ~1.4 m over the road's right lane, ~420 m short of the plaza, looking a touch right.
APP_EYE = Vector((200.0, -2.6, 1.4))
APP_LOOK = APP_EYE + Vector((math.cos(math.radians(-14)), math.sin(math.radians(-14)), -0.03)) * 100
APP_FOV = 50.0


def screen_point(sx, sy, depth):
    """The local point at pixel (sx, sy) of the 1280x720 arrival frame, `depth` metres along the view axis."""
    nx = (sx - RES[0] / 2) / (RES[0] / 2)
    ny = (RES[1] / 2 - sy) / (RES[1] / 2)
    return EYE + depth * (FWD + RIGHT * nx * TAN_H + UP * ny * TAN_V)


def to_screen(p):
    v = p - EYE
    d = v.dot(FWD)
    return Vector((RES[0] / 2 * (1 + v.dot(RIGHT) / (d * TAN_H)), RES[1] / 2 * (1 - v.dot(UP) / (d * TAN_V)))), d


def ray_at_z(sx, sy, z):
    d = screen_point(sx, sy, 1.0) - EYE
    return EYE + d * ((z - EYE.z) / d.z)


def view_depth(p):
    return (p - EYE).dot(FWD)


def px_to_m(px, depth):
    return px * depth / FPX


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
root = bpy.data.objects.new('City2', None)
scene.collection.objects.link(root)


# --- Materials ---------------------------------------------------------------------------------------------------------
def material(name, colour, roughness=0.5, metallic=0.0, emission=None, strength=0.0, coat=0.0, alpha=1.0,
             transmission=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*colour, 1)
    p.inputs['Roughness'].default_value = roughness
    p.inputs['Metallic'].default_value = metallic
    if coat:
        p.inputs['Coat Weight'].default_value = coat
        p.inputs['Coat Roughness'].default_value = 0.05
    if transmission:
        p.inputs['Transmission Weight'].default_value = transmission
    if alpha < 1:
        p.inputs['Alpha'].default_value = alpha
        if hasattr(m, 'surface_render_method'):
            m.surface_render_method = 'BLENDED'
    if emission:
        p.inputs['Emission Color'].default_value = (*emission, 1)
        p.inputs['Emission Strength'].default_value = strength
    return m


MAT = {
    'pearl': material('City2Pearl', (0.70, 0.68, 0.76), 0.22, 0.1, coat=0.8),
    'glass': material('City2Glass', (0.02, 0.3, 0.4), 0.08, 0.0, emission=(0.1, 0.8, 1.0), strength=1.3),
    'warm': material('City2GlassWarm', (0.7, 0.5, 0.3), 0.1, 0.0, emission=(1.0, 0.7, 0.4), strength=1.6),
    'chrome': material('City2Chrome', (0.62, 0.6, 0.72), 0.12, 1.0),
    'floor': material('City2Floor', (0.10, 0.09, 0.12), 0.06, 0.2, coat=1.0),
    'water': material('City2Water', (0.06, 0.05, 0.10), 0.02, 0.0),
    'ooze': material('City2Ooze', (0.004, 0.004, 0.006), 0.04, 0.0, coat=1.0),
    'screen': material('City2Screen', (0.12, 0.08, 0.4), 0.3, 0.0, emission=(0.28, 0.16, 0.95), strength=0.8),
    'palm': material('City2Palm', (0.05, 0.12, 0.06), 0.7, 0.0),
    'lamp': material('City2Lamp', (1.0, 0.92, 0.8), 0.4, 0.0, emission=(1.0, 0.88, 0.7), strength=12.0),
    'sun': material('City2Sun', (1.0, 0.75, 0.55), 1.0, 0.0, emission=(1.0, 0.72, 0.5), strength=6.0),
    'dome': material('City2DomeGlass', (0.8, 0.75, 0.95), 0.05, 0.0, alpha=0.35, emission=(0.55, 0.35, 1.0),
                     strength=0.8),
}


# --- Mesh helpers --------------------------------------------------------------------------------------------------------
def obj(name, me, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    o.parent = parent or root
    o.location = loc
    o.rotation_euler = rot
    o.scale = scale if not isinstance(scale, (int, float)) else (scale,) * 3
    return o


def mesh_from(name, bm, mat, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return me


def lathe(bm, profile, seg=40, cx=0.0, cy=0.0, z0=0.0, cap_top=True, cap_bottom=True):
    """Spin a (radius, z) profile about z. Profile runs bottom to top."""
    rings = []
    for r, z in profile:
        ring = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            ring.append(bm.verts.new((cx + r * math.cos(a), cy + r * math.sin(a), z0 + z)))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap_bottom and profile[0][0] > 1e-4:
        bm.faces.new(list(reversed(rings[0])))
    if cap_top and profile[-1][0] > 1e-4:
        bm.faces.new(rings[-1])
    return rings


def sweep(bm, path, profile, up=Vector((0, 0, 1))):
    """Extrude a 2-D (lateral, vertical) profile along a 3-D path (closed profile, open ends capped)."""
    rings = []
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        side = t.cross(up).normalized()
        u = side.cross(t).normalized()
        rings.append([bm.verts.new(p + side * a + u * b) for a, b in profile])
    n = len(profile)
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])


def rounded_rect_profile(w, h, r, n=4):
    """A closed (lateral, vertical) profile: a w x h rectangle with rounded corners, centred on (0, -h/2)."""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, -r, 0), (-w / 2 + r, -r, 90), (-w / 2 + r, -h + r, 180), (w / 2 - r, -h + r, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def polygon_slab(bm, outline, z_top, depth):
    """A flat slab from a closed outline (list of (x, y)), top at z_top."""
    top = [bm.verts.new((x, y, z_top)) for x, y in outline]
    bot = [bm.verts.new((x, y, z_top - depth)) for x, y in outline]
    bm.faces.new(top)
    bm.faces.new(list(reversed(bot)))
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))


def planar_uvs(me, scale=0.1):
    uv = me.uv_layers.new(name='UVMap')
    for loop in me.loops:
        co = me.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (co.x * scale, co.y * scale)


# --- Instanced modules (linked duplicates: one mesh, many objects) --------------------------------------------------------
def module_slab():
    """A saucer terrace: a thin rounded disc, radius 1 (scale it uniformly), with a lip."""
    bm = bmesh.new()
    prof = [(0.0, -0.05), (0.80, -0.05), (0.93, -0.035), (0.99, -0.01), (1.0, 0.01), (0.985, 0.035), (0.95, 0.05),
            (0.0, 0.05)]
    lathe(bm, prof, seg=56, cap_top=False, cap_bottom=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    return mesh_from('City2.M.Slab', bm, MAT['pearl'])


def module_cyl(name, mat, seg=40, caps=True):
    bm = bmesh.new()
    lathe(bm, [(1.0, 0.0), (1.0, 1.0)], seg=seg, cap_top=caps, cap_bottom=caps)
    return mesh_from(name, bm, mat)


def module_needle():
    """A chrome needle spire, height 1, base radius 1 (scale x/y for width, z for height)."""
    bm = bmesh.new()
    prof = [(1.0, 0.0), (0.95, 0.45), (0.8, 0.62), (0.9, 0.66), (0.62, 0.70), (0.5, 0.82), (0.62, 0.85),
            (0.4, 0.88), (0.25, 0.95), (0.12, 0.995), (0.0, 1.0)]
    lathe(bm, prof, seg=16, cap_top=False)
    return mesh_from('City2.M.Needle', bm, MAT['chrome'])


def module_bulb():
    """A tower with a rounded bulb crown, height 1, radius 1."""
    bm = bmesh.new()
    prof = [(1.0, 0.0), (0.9, 0.6), (1.1, 0.74), (1.12, 0.78), (0.9, 0.82), (0.75, 0.88), (0.8, 0.9),
            (0.5, 0.95), (0.2, 0.985), (0.0, 1.0)]
    lathe(bm, prof, seg=20, cap_top=False)
    return mesh_from('City2.M.Bulb', bm, MAT['chrome'])


def module_band_tower():
    """A slender glass tower segment (height 1, radius 1) to wrap tower cores with glowing bands."""
    return module_cyl('City2.M.GlassBand', MAT['glass'], seg=24, caps=False)


def module_ring():
    """A torus ring, radius 1 (a small circle spun about z)."""
    bm = bmesh.new()
    prof = [(1.0 + 0.12 * math.cos(math.radians(a)), 0.12 * math.sin(math.radians(a))) for a in range(-90, 271, 30)]
    lathe(bm, prof, seg=48, cap_top=False, cap_bottom=False)
    return mesh_from('City2.M.Ring', bm, MAT['chrome'])


def module_palm():
    """A palm, 1 unit ~ 1 m: a curved trunk 7 m tall and nine drooping fronds."""
    bm = bmesh.new()
    path = [Vector((0.25 * math.sin(t * 1.3) * t, 0, 7.0 * t)) for t in [i / 8 for i in range(9)]]
    sweep(bm, path, [(0.22 * math.cos(a), 0.22 * math.sin(a)) for a in [i * 2 * math.pi / 6 for i in range(6)]])
    top = path[-1]
    for k in range(9):
        a = 2 * math.pi * k / 9 + 0.3
        d = Vector((math.cos(a), math.sin(a), 0))
        side = d.cross(Vector((0, 0, 1)))
        pts = [top + d * (3.4 * t) + Vector((0, 0, 0.9 * t - 2.6 * t * t)) for t in (0, 0.33, 0.66, 1.0)]
        ws = [0.12, 0.65, 0.55, 0.05]
        vs = []
        for p, w in zip(pts, ws):
            vs.append((bm.verts.new(p + side * w), bm.verts.new(p - side * w), bm.verts.new(p + Vector((0, 0, 0.12)))))
        for (a1, b1, c1), (a2, b2, c2) in zip(vs, vs[1:]):
            bm.faces.new((a1, c1, c2, a2))
            bm.faces.new((c1, b1, b2, c2))
    me = mesh_from('City2.M.Palm', bm, MAT['palm'], smooth=False)
    return me


def module_lamp():
    bm = bmesh.new()
    lathe(bm, [(0.16, 0.0), (0.16, 0.05), (0.12, 0.09), (0.0, 0.1)], seg=12, cap_top=False)
    return mesh_from('City2.M.Lamp', bm, MAT['lamp'])


def module_drip():
    """A hanging ooze strand, top at z 0, length 1 down, ending in a fat drop."""
    bm = bmesh.new()
    prof = [(0.0, -1.06), (0.45, -1.03), (0.62, -0.96), (0.5, -0.88), (0.22, -0.8), (0.18, -0.4), (0.3, -0.08),
            (0.55, 0.0)]
    lathe(bm, prof, seg=10, cap_top=True, cap_bottom=False)
    return mesh_from('City2.M.Drip', bm, MAT['ooze'])


def module_puddle():
    bm = bmesh.new()
    lathe(bm, [(1.0, 0.0), (0.9, 0.02), (0.5, 0.03), (0.0, 0.03)], seg=24, cap_top=False)
    return mesh_from('City2.M.Puddle', bm, MAT['ooze'])


M = {
    'slab': module_slab(),
    'core': module_cyl('City2.M.Core', MAT['pearl']),
    'band': module_band_tower(),
    'warm': module_cyl('City2.M.WarmBand', MAT['warm'], seg=40, caps=False),
    'needle': module_needle(),
    'bulb': module_bulb(),
    'ring': module_ring(),
    'palm': module_palm(),
    'lamp': module_lamp(),
    'drip': module_drip(),
    'puddle': module_puddle(),
    'pylon': module_cyl('City2.M.Pylon', MAT['chrome'], seg=16),
}
COUNT = {}


def inst(kind, loc, scale=1.0, rot_z=0.0, parent=None, rot=None):
    COUNT[kind] = COUNT.get(kind, 0) + 1
    return obj(f'City2.{kind.capitalize()}.{COUNT[kind]:03d}', M[kind], parent, loc,
               rot if rot else (0, 0, rot_z), scale)


# --- Groups ---------------------------------------------------------------------------------------------------------------
def group(name):
    e = bpy.data.objects.new(name, None)
    scene.collection.objects.link(e)
    e.parent = root
    return e


G = {k: group(f'City2.{k}') for k in ('Road', 'Plaza', 'Terraces', 'Monorail', 'Spires', 'Towers', 'Dome',
                                      'Billboard', 'Water', 'Palms', 'Lamps', 'Sky', 'Shore')}


def saucer_tower(name, centre, radius, levels, core_r, parent, band='band', palms=True, crown=None, base_z=WATER_Z,
                 top_core=6.0):
    """Stacked saucer terraces round a core: slabs at the given z levels (radius may taper per level), a glowing glass
    band under each slab, planters with palms on the slab edges."""
    g = group(f'City2.{name}')
    g.parent = parent
    zs = [lv[0] for lv in levels]
    inst('core', (centre.x, centre.y, base_z), (core_r, core_r, zs[-1] + top_core - base_z), parent=g)
    prev = base_z
    for k, (z, r) in enumerate(levels):
        inst('slab', (centre.x, centre.y, z), r, rot_z=rnd.random(), parent=g)
        # The glass band below the slab: a ring of glowing glass set in from the edge.
        br = r * rnd.uniform(0.62, 0.8)
        h = min(z - prev - 0.5, 5.0)
        if h > 1.0:
            inst(band if k % 2 == 0 else 'warm', (centre.x, centre.y, z - h), (br, br, h), parent=g)
        prev = z
        if palms and k < len(levels) - 1:
            n = max(5, int(r * 0.55))
            for i in range(n):
                a = 2 * math.pi * (i + rnd.random() * 0.5) / n
                p = Vector((centre.x + math.cos(a) * r * 0.86, centre.y + math.sin(a) * r * 0.86, z + 0.05 * r))
                inst('palm', p, rnd.uniform(0.45, 0.7) * min(1.0, r / 14), rot_z=rnd.random() * 6.28, parent=G['Palms'])
    if crown == 'ring':
        inst('ring', (centre.x, centre.y, zs[-1] + top_core), core_r * 2.4, parent=g)
    return g


# =========================================================================================================================
# The road: RoadIn -> straight -> right bend -> plaza.
# =========================================================================================================================
def road_path(step=6.0):
    pts = [Vector((x, 0, 0)) for x in frange(0, ROAD_STRAIGHT, step)]
    c = Vector((ROAD_STRAIGHT, -BEND_R, 0))
    n = int(BEND_R * math.pi / 2 / step)
    for i in range(n + 1):
        a = math.pi / 2 - (math.pi / 2) * i / n
        pts.append(c + Vector((BEND_R * math.cos(a), BEND_R * math.sin(a), 0)))
    end = pts[-1]
    for s in frange(step, ROAD_TAIL - 4, step):
        pts.append(end + Vector((0, -s, 0)))
    return pts


def frange(a, b, s):
    out, x = [], a
    while x <= b + 1e-6:
        out.append(x)
        x += s
    return out


ROAD = road_path()
bm = bmesh.new()
sweep(bm, ROAD, rounded_rect_profile(ROAD_W, 1.2, 0.3))
me = mesh_from('City2.RoadDeck', bm, MAT['floor'])
planar_uvs(me, 0.05)
obj('City2.RoadDeck', me, G['Road'])
for side in (1, -1):  # kerbs with a lit strip
    bm = bmesh.new()
    pts = []
    for i, p in enumerate(ROAD):
        t = (ROAD[min(i + 1, len(ROAD) - 1)] - ROAD[max(i - 1, 0)]).normalized()
        pts.append(p + t.cross(Vector((0, 0, 1))) * side * (ROAD_W / 2 - 0.25) + Vector((0, 0, 0.55)))
    sweep(bm, pts, rounded_rect_profile(0.5, 0.6, 0.12))
    obj(f'City2.RoadKerb{"R" if side > 0 else "L"}', mesh_from('City2.RoadKerb', bm, MAT['pearl']), G['Road'])
    bm = bmesh.new()
    sweep(bm, [p + Vector((0, 0, 0.32)) - (t * 0) for p in pts], rounded_rect_profile(0.52, 0.06, 0.02, 1))
    obj(f'City2.RoadStrip{"R" if side > 0 else "L"}', mesh_from('City2.RoadStrip', bm, MAT['lamp']), G['Road'])
for i, p in enumerate(ROAD[::7]):  # piers into the lagoon
    inst('pylon', (p.x, p.y, WATER_Z - 1), (1.6, 1.6, 1 - WATER_Z - 1.2 + 1), parent=G['Road'])

# =========================================================================================================================
# The plaza: a rounded wet floor round the bike, a raised lit platform front-right, a podium step front-left.
# =========================================================================================================================
PLAZA_C = BIKE_AT + Vector((1.5, -1.0, 0))
outline = []
for i in range(48):
    a = 2 * math.pi * i / 48
    r = 13.0 + 3.0 * math.cos(a - math.radians(20))
    outline.append((PLAZA_C.x + r * math.cos(a), PLAZA_C.y + r * math.sin(a)))
bm = bmesh.new()
polygon_slab(bm, outline, 0.0, 1.4)
me = mesh_from('City2.PlazaFloor', bm, MAT['floor'], smooth=False)
planar_uvs(me, 0.08)
obj('City2.PlazaFloor', me, G['Plaza'])

# The raised platform (concept x 850-1090, y 520-560): a rounded plinth just beyond the bike's front, its lit edge.
plat_c = ray_at_z(985, 545, 0.0)
plat_r = px_to_m(150, view_depth(plat_c))
bm = bmesh.new()
lathe(bm, [(plat_r, -0.2), (plat_r, 0.22), (plat_r - 0.08, 0.3), (0.0, 0.3)], seg=40, cx=plat_c.x, cy=plat_c.y)
obj('City2.Platform', mesh_from('City2.Platform', bm, MAT['pearl']), G['Plaza'])
for k in range(9):
    a = math.radians(140 + k * 22)
    inst('lamp', (plat_c.x + math.cos(a) * (plat_r - 0.25), plat_c.y + math.sin(a) * (plat_r - 0.25), 0.3), 1.0,
         parent=G['Lamps'])

# =========================================================================================================================
# The left terraces (concept x 0-235): a big saucer stack whose slab rims reach x ~228 at y ~190 and ~345.
# =========================================================================================================================
T_DEPTH = 24.0
rim = screen_point(228, 345, T_DEPTH)
# The rim's rightmost silhouette point: the centre lies away from the camera's right, perpendicular to the ray.
ray_h = (rim - EYE)
ray_h.z = 0
ray_h.normalize()
perp = Vector((-ray_h.y, ray_h.x, 0))  # left of the ray
T_R = 17.0
T_C = rim + perp * T_R
T_C.z = 0
z2 = rim.z
z1 = screen_point(228, 190, T_DEPTH).z
dz = z1 - z2
levels = [(z2 - dz, T_R * 0.98), (z2, T_R), (z1, T_R * 0.97), (z1 + dz, T_R * 0.9), (z1 + 2 * dz, T_R * 0.78),
          (z1 + 3 * dz, T_R * 0.62)]
levels = [lv for lv in levels if lv[0] > 1.5]
saucer_tower('TerraceL', T_C, T_R, levels, T_R * 0.45, G['Terraces'], crown=None, base_z=-1.0)
# Its island and the podium step at its foot, joined to the plaza.
bm = bmesh.new()
lathe(bm, [(T_R + 0.5, -1.4), (T_R + 0.5, 0.0), (0.0, 0.0)], seg=56, cx=T_C.x, cy=T_C.y, cap_bottom=True)
obj('City2.TerraceIsland', mesh_from('City2.TerraceIsland', bm, MAT['floor']), G['Plaza'])
pod_c = ray_at_z(40, 556, 0.0)
bm = bmesh.new()
lathe(bm, [(3.2, -0.2), (3.2, 0.38), (3.05, 0.45), (0.0, 0.45)], seg=32, cx=pod_c.x + 1.5, cy=pod_c.y + 1.5)
obj('City2.Planter', mesh_from('City2.Planter', bm, MAT['pearl']), G['Plaza'])
# Palms in a bed in front of the terraces (concept x 0-90, y 380-470): small, ~14 m out.
for k, (sx, sy) in enumerate(((20, 480), (60, 470), (100, 482), (-20, 470), (140, 476))):
    p = ray_at_z(sx, sy + 20, 0.0)
    p = EYE + (p - EYE) * (14.0 / view_depth(p))
    inst('palm', (p.x, p.y, 0.3), rnd.uniform(0.32, 0.4), rot_z=rnd.random() * 6.28, parent=G['Palms'])
inst('lamp', (pod_c.x - 0.6, pod_c.y - 0.4, 0.45), 1.2, parent=G['Lamps'])

# A second, taller saucer tower behind the terraces (concept x 190-410, y 0-270: discs, a cyan glass core).
c2 = screen_point(300, 120, 150.0)
c2.z = 0
saucer_tower('TowerL2', c2, 26.0, [(30, 18.0), (52, 26.0), (74, 20.0), (104, 24.0), (128, 16.0)], 8.0, G['Towers'],
             palms=True, top_core=24)
inst('band', (c2.x, c2.y, 52), (12.0, 12.0, 22), parent=G['Towers'])
# And the tall glass tower left of centre that runs off the top (concept x 410-470).
c3 = screen_point(450, 200, 220.0)
c3.z = 0
inst('core', (c3.x, c3.y, WATER_Z), (7.0, 7.0, 300), parent=G['Towers'])
for z in range(20, 290, 32):
    inst('band', (c3.x, c3.y, z), (7.3, 7.3, 14), parent=G['Towers'])
    inst('slab', (c3.x, c3.y, z + 22), 9.0, parent=G['Towers'])

# =========================================================================================================================
# The monorail: its beam's underside follows the concept's traced curve at MONO_Z, extended past both ends.
# =========================================================================================================================
MONO_Z = 25.0
mpts = [ray_at_z(x, y, MONO_Z) for x, y in FEAT['monorail']['points']]
# Smooth and resample along length.


def resample(pts, step):
    out = [pts[0]]
    acc = 0.0
    for a, b in zip(pts, pts[1:]):
        seg = (b - a).length
        while acc + seg >= step:
            t = (step - acc) / seg
            a = a.lerp(b, t)
            out.append(a)
            seg = (b - a).length
            acc = 0.0
        acc += seg
    return out


mpts = resample(mpts, 4.0)
t0 = (mpts[0] - mpts[3]).normalized()
t1 = (mpts[-1] - mpts[-4]).normalized()
head = [mpts[0] + t0 * s for s in frange(4, 160, 4)][::-1]
tail = []
p, d = mpts[-1], t1
for s in range(70):
    d = (Matrix.Rotation(math.radians(-0.5), 3, 'Z') @ d).normalized()
    p = p + d * 4.0
    tail.append(p.copy())
MONO = head + mpts + tail
bm = bmesh.new()
sweep(bm, [p + Vector((0, 0, 0.8)) for p in MONO], rounded_rect_profile(2.4, 1.6, 0.5))
obj('City2.MonorailBeam', mesh_from('City2.MonorailBeam', bm, MAT['pearl']), G['Monorail'])
for p in MONO[::12]:
    inst('pylon', (p.x, p.y, WATER_Z), (1.0, 1.0, MONO_Z - WATER_Z), parent=G['Monorail'])

# The train: three capsule cars on the beam, spanning concept x ~255-550 (front at the right).


def car_mesh():
    bm = bmesh.new()
    L, R = 10.0, 1.5
    prof = [(0.0, -L / 2)] + [(R * math.sin(math.radians(a)), -L / 2 + 2.2 * (1 - math.cos(math.radians(a))))
                              for a in range(15, 91, 15)] + \
           [(R, L / 2 - 2.2)] + [(R * math.cos(math.radians(a)), L / 2 - 2.2 + 2.2 * math.sin(math.radians(a)))
                                 for a in range(15, 91, 15)]
    lathe(bm, prof, seg=20, cap_top=False, cap_bottom=False)
    bmesh.ops.scale(bm, vec=(1.0, 1.15, 1.0), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, 'Y'))
    car = mesh_from('City2.M.Car', bm, MAT['pearl'])
    bm = bmesh.new()
    lathe(bm, [(R * 1.02, -L / 2 + 1.6), (R * 1.02, L / 2 - 1.6)], seg=20, cap_top=False, cap_bottom=False)
    bmesh.ops.scale(bm, vec=(1.0, 1.15, 0.45), verts=bm.verts)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 0.0))
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, 'Y'))
    win = mesh_from('City2.M.CarWindows', bm, MAT['warm'])
    return car, win


CAR, WIN = car_mesh()
M['car'], M['carwin'] = CAR, WIN
# Arc-length along MONO, and where the train's ends project.
proj = [to_screen(p)[0].x for p in MONO]
i_front = min(range(len(MONO)), key=lambda i: abs(proj[i] - 550))
s = 0.0
i = i_front
for k in range(3):
    # walk back along the beam ~24.8 m per car
    j = i
    acc = 0.0
    while j > 0 and acc < 5.2:
        acc += (MONO[j] - MONO[j - 1]).length
        j -= 1
    centre = MONO[j]
    tdir = (MONO[min(j + 1, len(MONO) - 1)] - MONO[max(j - 1, 0)]).normalized()
    yaw = math.atan2(tdir.y, tdir.x)
    pos = centre + Vector((0, 0, 1.6 + 0.8 + 0.7))
    inst('car', pos, 1.0, rot_z=yaw, parent=G['Monorail'])
    print('car', k, [round(v) for v in to_screen(pos)[0]], round(to_screen(pos)[1]))
    inst('carwin', pos + Vector((0, 0, 0.35)), 1.0, rot_z=yaw, parent=G['Monorail'])
    acc = 0.0
    while j > 0 and acc < 5.3:
        acc += (MONO[j] - MONO[j - 1]).length
        j -= 1
    i = j

# =========================================================================================================================
# The far bridge (concept y 355-380, x 640-1000), arching over the water toward the right.
# =========================================================================================================================
bpts = [screen_point(x, y, d) for x, y, d in ((600, 372, 150), (700, 366, 140), (800, 366, 128), (900, 372, 118),
                                                (1000, 382, 104), (1100, 392, 92))]
BZ = sum(p.z for p in bpts) / len(bpts)
bpts = resample([Vector((p.x, p.y, BZ)) for p in bpts], 4.0)
bm = bmesh.new()
sweep(bm, bpts, rounded_rect_profile(7.0, 1.6, 0.6))
obj('City2.Bridge', mesh_from('City2.Bridge', bm, MAT['pearl']), G['Towers'])
for p in bpts[::7]:
    inst('pylon', (p.x, p.y, WATER_Z), (1.6, 1.6, BZ - WATER_Z - 0.8), parent=G['Towers'])

# =========================================================================================================================
# The sun, the dome, the spires (the skyline, composed from the concept's).
# =========================================================================================================================
SUN_D = 2500.0
sun = FEAT['sun']
sun_c = screen_point(sun['centre'][0], sun['centre'][1], SUN_D)
sun_r = px_to_m(sun['radius'], SUN_D)
bm = bmesh.new()
bmesh.ops.create_circle(bm, cap_ends=True, segments=48, radius=sun_r)
sun_o = obj('City2.Sun', mesh_from('City2.Sun', bm, MAT['sun']), G['Sky'], sun_c)
sun_o.rotation_mode = 'QUATERNION'
sun_o.rotation_quaternion = (EYE - sun_c).to_track_quat('Z', 'Y')

DOME_D = 160.0
dm = FEAT['dome']
dome_c = screen_point(dm['cx'], dm['cy'], DOME_D)
dome_r = px_to_m(dm['half_w'], DOME_D)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=20, radius=dome_r)
dome_o = obj('City2.DomeGlass', mesh_from('City2.DomeGlass', bm, MAT['dome']), G['Dome'], dome_c)
bm = bmesh.new()
for lat in (-0.3, 0.0, 0.35, 0.65):  # chrome ribs
    rr = dome_r * math.cos(math.asin(lat))
    lathe(bm, [(rr * 1.005, dome_r * lat - 0.25), (rr * 1.01, dome_r * lat + 0.25)], seg=40, cap_top=False,
          cap_bottom=False)
obj('City2.DomeRibs', mesh_from('City2.DomeRibs', bm, MAT['chrome']), G['Dome'], dome_c)
# Its pedestal: a pearl drum from the water to the dome's waist, a planted deck round the dome's foot.
deck_z = dome_c.z - dome_r * 0.55
inst('core', (dome_c.x, dome_c.y, WATER_Z), (dome_r * 0.55, dome_r * 0.55, deck_z - WATER_Z), parent=G['Dome'])
inst('slab', (dome_c.x, dome_c.y, deck_z), dome_r * 1.25, parent=G['Dome'])
inst('warm', (dome_c.x, dome_c.y, deck_z - 7), (dome_r * 0.8, dome_r * 0.8, 6.0), parent=G['Dome'])
for k in range(10):
    a = 2 * math.pi * k / 10
    inst('palm', (dome_c.x + math.cos(a) * dome_r * 1.08, dome_c.y + math.sin(a) * dome_r * 1.08, deck_z + 0.6),
         rnd.uniform(0.9, 1.3), rot_z=rnd.random() * 6.28, parent=G['Palms'])

# The skyline: the concept's topmost non-sky row per column, between the left towers and the billboard. A spire per
# window of columns, its tip at the window's highest row; hero shapes where the concept has them.
rows = FEAT['skyline']['rows']
HERO = {  # concept column -> (kind, width px, depth m)
    680: ('ring', 46, 330), 625: ('needle', 16, 360), 875: ('needle', 14, 380), 552: ('bulb', 30, 300),
}
SKY_WIN = 12
for x0 in range(470, 962, SKY_WIN):
    win = rows[x0:x0 + SKY_WIN]
    top = min(win)
    if top >= 330:
        continue
    xc = x0 + win.index(top)
    hero = next((v for k, v in HERO.items() if abs(k - xc) < 8), None)
    tip_w = sum(1 for r in rows[max(0, xc - 8):xc + 8] if r < top + 12)
    body_w = sum(1 for r in rows[max(0, xc - 14):xc + 14] if r < top + 60)
    if hero:
        kind, wpx, depth = hero
    elif tip_w <= 5:
        kind, wpx, depth = 'needle', max(8, min(body_w, 16)), rnd.uniform(280, 460)
    else:
        # A crowned tower as wide as the columns that actually reach near the window's top.
        occ = [x0 + i for i, r in enumerate(win) if r <= top + 10]
        kind, wpx, depth = 'bulb', max(6, len(occ)) * 1.1, rnd.uniform(260, 440)
        xc = sum(occ) / len(occ)
    tip = screen_point(xc, top + (0 if kind != 'ring' else 6), depth)
    base = Vector((tip.x, tip.y, WATER_Z))
    hgt = tip.z - WATER_Z
    r = px_to_m(wpx / 2, depth)
    if kind == 'needle':
        inst('needle', base, (r * 1.4, r * 1.4, hgt), parent=G['Spires'])
        inst('band', (base.x, base.y, hgt * 0.2), (r * 0.98, r * 0.98, hgt * 0.4), parent=G['Spires'])
    elif kind == 'bulb':
        inst('bulb', base, (r, r, hgt), parent=G['Spires'])
        inst('band', (base.x, base.y, hgt * 0.35), (r * 1.01, r * 1.01, hgt * 0.3), parent=G['Spires'])
    else:  # ring tower: a slim chrome shaft, a ring crown (concept x 655-710, y 95-115)
        inst('core', base, (r * 0.35, r * 0.35, hgt - r * 0.2), parent=G['Spires'])
        inst('band', (base.x, base.y, hgt * 0.5), (r * 0.37, r * 0.37, hgt * 0.4), parent=G['Spires'])
        inst('ring', (base.x, base.y, tip.z - r * 0.1), r * 0.95, parent=G['Spires'])
        inst('slab', (base.x, base.y, tip.z - r * 0.35), r * 0.6, parent=G['Spires'])

# Mid-distance saucer towers below the skyline (concept x 480-960, y 120-420): glowing cores, stacked discs.
KEEP_CLEAR = [(860, 975, 0, 350), (725, 845, 0, 290)]  # the dome; the sun's disc (columns, rows to keep clear)
for k in range(14):
    xc = rnd.uniform(480, 950)
    while any(a <= xc <= b for a, b, _, _ in KEEP_CLEAR):
        xc = rnd.uniform(480, 950)
    floor_row = max(rows[int(xc) - 10:int(xc) + 10]) if min(rows[int(xc) - 10:int(xc) + 10]) < 720 else 330
    top = rnd.uniform(max(150, min(rows[int(xc) - 10:int(xc) + 10]) + 30), 300)
    depth = rnd.uniform(140, 230)
    tip = screen_point(xc, top, depth)
    c = Vector((tip.x, tip.y, 0))
    r = px_to_m(rnd.uniform(20, 45), depth)
    lv = []
    z = tip.z * rnd.uniform(0.35, 0.5)
    while z < tip.z - 2:
        lv.append((z, r * rnd.uniform(1.4, 2.2)))
        z += rnd.uniform(12, 26)
    if lv:
        saucer_tower(f'Mid{k:02d}', c, r, lv, r * 0.5, G['Towers'], band='band', palms=False, top_core=tip.z - lv[-1][0])

# The far shore at the water line (concept y 440-475): low pearl blocks with lit strips.
for x in range(560, 1280, 70):
    d = rnd.uniform(200, 280)
    p = ray_at_z(x, 470, 0)
    p = EYE + (p - EYE).normalized() * d
    inst('core', (p.x, p.y, WATER_Z), (rnd.uniform(8, 18), rnd.uniform(8, 18), rnd.uniform(4, 10)), parent=G['Shore'])
    inst('lamp', (p.x, p.y, 4.0), 6.0, parent=G['Shore'])

# A flyer crossing the sky (concept x ~805, y ~170).
fly = screen_point(805, 170, 140)
bm = bmesh.new()
lathe(bm, [(0.0, -0.4), (2.6, -0.1), (3.0, 0.0), (1.4, 0.4), (0.0, 0.6)], seg=20)
obj('City2.Flyer', mesh_from('City2.Flyer', bm, MAT['chrome']), G['Sky'], fly, scale=(1.0, 0.45, 0.6))

# =========================================================================================================================
# The billboard: a canted screen in a chrome frame, its legs and frame running with black ooze (concept x 965-1245).
# =========================================================================================================================
bb_floor = ray_at_z(1110, 515, 0.0)
BB_D = view_depth(bb_floor)
quad = [(985, 72), (1221, 4), FEAT['screen']['quad'][2], FEAT['screen']['quad'][3]]  # tl, tr (eyeballed; see align2)
C = [screen_point(x, y, BB_D) for x, y in quad]
tl, tr, br, bl = C
ux = ((tr - tl) + (br - bl)) / 2
uy = ((tl - bl) + (tr - br)) / 2
centre = (tl + tr + br + bl) / 4
nrm = ux.cross(uy).normalized()
if nrm.dot(EYE - centre) < 0:
    nrm = -nrm
bm = bmesh.new()
vs = [bm.verts.new(p) for p in (bl, br, tr, tl)]
f = bm.faces.new(vs)
uvl = bm.loops.layers.uv.new('UVMap')
for loop, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
    loop[uvl].uv = uv
screen_me = mesh_from('City2.Screen', bm, MAT['screen'], smooth=False)
screen_o = obj('City2.Screen', screen_me, G['Billboard'])
screen_o['note'] = 'UVs 0-1 across the screen (u right, v up as seen from the arrival camera); the site puts the logo here'
# The frame: a rounded tube round the screen, set back a touch, and a back panel.
fw = ux.length * 0.05
ring = [bl, br, tr, tl, bl]
fpts = []
for a, b in zip(ring, ring[1:]):
    for t in (0.0, 0.25, 0.5, 0.75):
        fpts.append(a.lerp(b, t))
fpts.append(bl)
bm = bmesh.new()
sweep(bm, [p - nrm * 0.05 + (p - centre).normalized() * fw * 0.7 for p in fpts],
      rounded_rect_profile(fw * 2, fw * 2, fw * 0.8, 2), up=nrm)
obj('City2.BillboardFrame', mesh_from('City2.BillboardFrame', bm, MAT['ooze']), G['Billboard'])
bm = bmesh.new()
back = [p - nrm * 0.35 + (p - centre).normalized() * fw for p in (bl, br, tr, tl)]
bm.faces.new([bm.verts.new(p) for p in reversed(back)])
bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=0.3)
obj('City2.BillboardBack', mesh_from('City2.BillboardBack', bm, MAT['chrome'], smooth=False), G['Billboard'])
# Legs: two thick ooze-sheathed posts from the frame's foot to the floor (concept x ~1020 and ~1170).
for sx in (1025, 1170):
    t = (sx - quad[3][0]) / (quad[2][0] - quad[3][0])
    top = bl.lerp(br, t)
    foot = Vector((top.x, top.y, -0.4))
    bm = bmesh.new()
    path = [top.lerp(foot, k / 8) + Vector((0.08 * math.sin(k), 0, 0)) for k in range(9)]
    prof = [(0.3 * math.cos(a), 0.3 * math.sin(a)) for a in [i * 2 * math.pi / 12 for i in range(12)]]
    sweep(bm, path, prof, up=nrm)
    obj('City2.OozeLeg', mesh_from('City2.OozeLeg', bm, MAT['ooze']), G['Billboard'])
    inst('puddle', (foot.x, foot.y, 0.005), (1.8, 1.4, 1.0), parent=G['Billboard'])
# Drips off the frame's bottom and corners, and drops on the floor.
for k in range(16):
    t = rnd.random()
    top = bl.lerp(br, t) - nrm * 0.05
    L = rnd.uniform(0.3, 2.2) * (1.6 if rnd.random() < 0.3 else 1.0)
    inst('drip', top, (0.12, 0.12, L), parent=G['Billboard'])
for k in range(8):
    t = rnd.uniform(0.4, 1.0)
    top = tl.lerp(bl, t) - nrm * 0.05 - ux.normalized() * fw * 1.5  # down the frame's left side, outside the screen
    inst('drip', top, (0.1, 0.1, rnd.uniform(0.3, 1.5)), parent=G['Billboard'])
for k in range(14):
    p = ray_at_z(rnd.uniform(1000, 1280), rnd.uniform(520, 700), 0.0)
    inst('puddle', (p.x, p.y, 0.004), (rnd.uniform(0.3, 1.2), rnd.uniform(0.3, 0.9), 1.0), rot_z=rnd.random() * 3,
         parent=G['Billboard'])

# The building behind the billboard (concept x 965-1280, y 0-520): a big saucer stack off to the right with an arcade.
# Composed like the left terraces: its top slab's leftmost rim stands at concept (945, 40), over the billboard.
RB_R = 26.0
RB_LV = [(6.5, RB_R * 0.55), (13.5, RB_R * 0.62), (20.5, RB_R * 0.74), (27.5, RB_R)]  # flaring up: the dome shows under it
rb = ray_at_z(945, 40, RB_LV[-1][0])
ray_h = (rb - EYE)
ray_h.z = 0
ray_h.normalize()
RB_C = rb + Vector((ray_h.y, -ray_h.x, 0)) * RB_LV[-1][1]  # right of the ray: rb is the slab's leftmost point
RB_C.z = 0
saucer_tower('TerraceR', RB_C, RB_R, RB_LV, RB_R * 0.55, G['Terraces'], base_z=WATER_Z)
print('terrace R centre', [round(v, 2) for v in RB_C], 'depth', round(view_depth(rb), 1))
for k in range(22):  # the arcade: pylons round the base under the first slab
    a = 2 * math.pi * k / 22
    inst('pylon', (RB_C.x + math.cos(a) * RB_R * 0.9, RB_C.y + math.sin(a) * RB_R * 0.9, WATER_Z),
         (0.7, 0.7, 6.5 - WATER_Z), parent=G['Terraces'])

# =========================================================================================================================
# The lagoon: one water sheet under everything (south of the road, and east of the bend).
# =========================================================================================================================
bm = bmesh.new()
outline = [(100, -ROAD_W / 2 - 1), (ROAD_STRAIGHT, -ROAD_W / 2 - 1), (ROAD_STRAIGHT + 60, 120), (2600, 120),
           (2600, -2200), (100, -2200)]
polygon_slab(bm, outline, WATER_Z, 0.1)
me = mesh_from('City2.WaterSurface', bm, MAT['water'], smooth=False)
planar_uvs(me, 0.02)
obj('City2.WaterSurface', me, G['Water'])

# Lamps along the plaza's rim and the canal edge.
for i in range(18):
    a = 2 * math.pi * i / 18
    r = 13.0 + 3.0 * math.cos(a - math.radians(20)) - 0.5
    inst('lamp', (PLAZA_C.x + r * math.cos(a), PLAZA_C.y + r * math.sin(a), 0.0), 1.0, parent=G['Lamps'])

# =========================================================================================================================
# Markers.
# =========================================================================================================================


def empty(name, loc, rot_quat=None, yaw=None, props=None, size=1.0):
    e = bpy.data.objects.new(name, None)
    scene.collection.objects.link(e)
    e.parent = root
    e.empty_display_size = size
    e.location = loc
    if rot_quat is not None:
        e.rotation_mode = 'QUATERNION'
        e.rotation_quaternion = rot_quat
    elif yaw is not None:
        e.rotation_euler = (0, 0, math.radians(yaw))
    for k, v in (props or {}).items():
        e[k] = v
    return e


def r4(v):
    return [round(float(c), 4) for c in v]


empty('City2.ArrivalCam', EYE, (LOOK - EYE).to_track_quat('-Z', 'Y'),
      props={'EYE': r4(EYE), 'LOOK': r4(LOOK), 'FOV': round(FOV, 3),
             'note': 'Blender local frame (z up); FOV vertical degrees; the empty looks down its -Z like a camera'})
empty('City2.ApproachCam', APP_EYE, (APP_LOOK - APP_EYE).to_track_quat('-Z', 'Y'),
      props={'EYE': r4(APP_EYE), 'LOOK': r4(APP_LOOK), 'FOV': APP_FOV})
empty('City2.BikeMark', BIKE_AT, yaw=BIKE_YAW, props={'YAW': BIKE_YAW, 'note': 'bike front along local +X'})
empty('City2.RoadIn', Vector((0, 0, 0)), yaw=0.0,
      props={'note': 'the road hands over here heading local +X, deck top z 0; width 11.8',
             'ROAD_STRAIGHT': ROAD_STRAIGHT, 'BEND_R': BEND_R, 'ROAD_TAIL': ROAD_TAIL})

# --- Stats, save, export -----------------------------------------------------------------------------------------------
meshes = [o for o in root.children_recursive if o.type == 'MESH']
uniq = {o.data.name: o.data for o in meshes}
print('objects', len(meshes), 'unique meshes', len(uniq),
      'unique tris', sum(sum(len(p.vertices) - 2 for p in me.polygons) for me in uniq.values()))
print('arrival EYE', r4(EYE), 'LOOK', r4(LOOK), 'FOV', FOV, 'bike', r4(BIKE_AT), BIKE_YAW)
print('terrace centre', r4(T_C), 'levels', [(round(z, 2), round(r, 2)) for z, r in levels])
print('billboard depth', round(BB_D, 2), 'dome', r4(dome_c), round(dome_r, 2))

cam = bpy.data.objects.new('ArrivalCamera', bpy.data.cameras.new('ArrivalCamera'))
scene.collection.objects.link(cam)


def set_cam(eye, look, fov):
    cam.location = eye
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (look - eye).to_track_quat('-Z', 'Y')
    cam.data.sensor_fit = 'VERTICAL'
    cam.data.sensor_height = 24
    cam.data.lens = 12 / math.tan(math.radians(fov / 2))
    cam.data.clip_start = 0.05
    cam.data.clip_end = 6000


set_cam(EYE, LOOK, FOV)
scene.camera = cam
scene.render.resolution_x, scene.render.resolution_y = RES

# The world: a sunset gradient (blue-violet overhead, pink, orange at the horizon) with a glow round the sun.
world = bpy.data.worlds.new('City2Sunset')
world.use_nodes = True
nt = world.node_tree
nodes, links = nt.nodes, nt.links
bg = nodes['Background']
tc = nodes.new('ShaderNodeTexCoord')
sep = nodes.new('ShaderNodeSeparateXYZ')
links.new(tc.outputs['Generated'], sep.inputs[0])
ramp = nodes.new('ShaderNodeValToRGB')
cr = ramp.color_ramp
cr.elements[0].position, cr.elements[0].color = 0.0, (1.0, 0.42, 0.32, 1)
cr.elements[1].position, cr.elements[1].color = 0.55, (0.1, 0.1, 0.42, 1)
e = cr.elements.new(0.07)
e.color = (0.95, 0.32, 0.45, 1)
e = cr.elements.new(0.22)
e.color = (0.5, 0.22, 0.6, 1)
links.new(sep.outputs['Z'], ramp.inputs['Fac'])
sun_dir = (sun_c - EYE).normalized()
dot = nodes.new('ShaderNodeVectorMath')
dot.operation = 'DOT_PRODUCT'
links.new(tc.outputs['Generated'], dot.inputs[0])
dot.inputs[1].default_value = sun_dir
pw = nodes.new('ShaderNodeMath')
pw.operation = 'POWER'
links.new(dot.outputs['Value'], pw.inputs[0])
pw.inputs[1].default_value = 14.0
mix = nodes.new('ShaderNodeMix')
mix.data_type = 'RGBA'
mix.blend_type = 'ADD'
links.new(pw.outputs[0], mix.inputs['Factor'])
links.new(ramp.outputs['Color'], mix.inputs['A'])
mix.inputs['B'].default_value = (0.9, 0.42, 0.2, 1)
links.new(mix.outputs['Result'], bg.inputs['Color'])
bg.inputs['Strength'].default_value = 1.0
scene.world = world

os.makedirs(os.path.dirname(GLB), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
for o in bpy.context.view_layer.objects:
    o.select_set(False)
for o in root.children_recursive:
    o.select_set(True)
root.select_set(True)
bpy.ops.export_scene.gltf(filepath=GLB, export_format='GLB', use_selection=True, export_apply=True,
                          export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
                          export_draco_position_quantization=14, export_draco_normal_quantization=8,
                          export_draco_texcoord_quantization=10,
                          export_gpu_instances=True,
                          export_yup=True, export_cameras=False, export_lights=False, export_extras=True)
print('exported', GLB, os.path.getsize(GLB))


# --- Renders -------------------------------------------------------------------------------------------------------------
def add_bike():
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=BIKE_GLB)
    imported = set(bpy.data.objects) - before
    rig = bpy.data.objects.new('BikeRig', None)
    scene.collection.objects.link(rig)
    rig.matrix_world = BIKE_M
    for o in imported:
        if o.parent is None:
            o.parent = rig
    return [o for o in imported if o.type == 'MESH']


bike_objs = add_bike()
os.makedirs(RENDERS, exist_ok=True)

# 1. Object IDs (flat colours) for score.py: sky = transparent, sun yellow, bike red, screen magenta, dome green,
#    monorail beam orange, water blue, everything else grey.
ID = {'sun': (1, 1, 0), 'bike': (1, 0, 0), 'screen': (1, 0, 1), 'dome': (0, 1, 0), 'mono': (1, 0.5, 0),
      'water': (0, 0, 1), 'other': (0.5, 0.5, 0.5)}
for o in scene.objects:
    if o.type != 'MESH':
        continue
    k = 'other'
    if o in bike_objs:
        k = 'bike'
    elif o.name == 'City2.Sun':
        k = 'sun'
    elif o.name == 'City2.Screen':
        k = 'screen'
    elif o.name in ('City2.DomeGlass', 'City2.DomeRibs'):
        k = 'dome'
    elif o.name == 'City2.MonorailBeam':
        k = 'mono'
    elif o.name == 'City2.WaterSurface':
        k = 'water'
    o.color = (*ID[k], 1)
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'FLAT'
scene.display.shading.color_type = 'OBJECT'
scene.display.shading.show_cavity = False
scene.display.shading.show_object_outline = False
scene.display.shading.show_specular_highlight = False
scene.render.film_transparent = True
scene.render.image_settings.color_mode = 'RGBA'
scene.view_settings.view_transform = 'Standard'
scene.render.filepath = os.path.join(RENDERS, f'city2-arrival-ids-{ROUND}.png')
bpy.ops.render.render(write_still=True)
scene.render.film_transparent = False
scene.render.image_settings.color_mode = 'RGB'

# 2. EEVEE: sunset world, a warm low sun from the sun's direction, the emissive bands.
if os.environ.get('CITY2_NO_EEVEE') != '1':
    scene.render.engine = 'BLENDER_EEVEE'
    ee = scene.eevee
    ee.taa_render_samples = 48
    if hasattr(ee, 'use_raytracing'):
        ee.use_raytracing = True
        try:
            ee.ray_tracing_options.resolution_scale = '1'
            ee.ray_tracing_method = 'SCREEN'
        except Exception:
            pass
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = -0.6
    sl = bpy.data.lights.new('SunKey', 'SUN')
    sl.energy = 3.0
    sl.color = (1.0, 0.62, 0.45)
    sl.angle = math.radians(2)
    so = bpy.data.objects.new('SunKey', sl)
    scene.collection.objects.link(so)
    so.rotation_mode = 'QUATERNION'
    so.rotation_quaternion = (-sun_dir).to_track_quat('-Z', 'Y')
    fl = bpy.data.lights.new('SkyFill', 'SUN')
    fl.energy = 0.35
    fl.color = (0.6, 0.55, 1.0)
    fo = bpy.data.objects.new('SkyFill', fl)
    scene.collection.objects.link(fo)
    fo.rotation_euler = (math.radians(30), 0, math.radians(200))
    scene.render.filepath = os.path.join(RENDERS, f'city2-arrival-{ROUND}.png')
    bpy.ops.render.render(write_still=True)
    if os.environ.get('CITY2_APPROACH', '1') == '1':
        for o in bike_objs:
            o.hide_render = True
        set_cam(APP_EYE, APP_LOOK, APP_FOV)
        scene.render.filepath = os.path.join(RENDERS, 'city2-approach.png')
        bpy.ops.render.render(write_still=True)

try:
    subprocess.run(['python3', os.path.join(ALIGN, 'score.py'), ROUND], check=True, cwd=ALIGN)
except Exception as exc:
    print('score skipped:', exc)
