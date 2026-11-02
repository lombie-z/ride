"""Micro to macro: the falls land in the water of a giant copy of the biome, and a shoreline garden grows around where
they land. Re-runnable (rebuilds everything named Macro.* and Garden.*, and the Pool).
Run inside Blender with art/micro-biome.blend open, after build-spill.py:
    exec(open('<repo>/art/build-macro.py').read())

The copy is linked duplicates of the micro biome (sharing its meshes, so it costs nearly nothing to download), under
one empty scaled S times and placed so the falls (which land at the world origin) come down in an open stretch of its
water: the front-right corner, with the planter's wall rising behind the splash.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

scene = bpy.context.scene
root = bpy.data.objects['MicroBiome']
S = 6.0
POOL_Z = -11.0
MICRO_WATER_Z = 0.522
# Where, in the micro planter's water, the falls come down (the most open spot, away from spires and bushes).
LANDING = Vector((0.3, -0.3))
ORIGIN = Vector((-S * LANDING.x, -S * LANDING.y, POOL_Z - S * MICRO_WATER_Z))
# Copied into the macro biome; everything below the planter (falls, sky) stays single.
COPY = ('Planter', 'Soil', 'Water', 'Spire', 'Leaf', 'Moss', 'Cloud', 'Star', 'LetterRingTilt')


def remove_tree(o):
    for c in list(o.children_recursive):
        bpy.data.objects.remove(c)
    bpy.data.objects.remove(o)


for name in [o.name for o in bpy.data.objects if o.name.startswith(('Macro.', 'Garden.')) or o.name in ('Macro', 'Pool')]:
    if name in bpy.data.objects:
        remove_tree(bpy.data.objects[name])

macro = bpy.data.objects.new('Macro', None)
scene.collection.objects.link(macro)
macro.parent = root
macro.location = ORIGIN
macro.scale = (S, S, S)


def copy_tree(o, parent, name=None):
    c = o.copy()  # linked: shares o's mesh data
    c.name = name or f'Macro.{o.name}'
    c['source'] = o.name  # the export reuses the source's frozen mesh for it
    scene.collection.objects.link(c)
    c.parent = parent
    c.matrix_parent_inverse = Matrix()
    for child in o.children:
        copy_tree(child, c)
    return c


# A pond around the splash: the copy leaves out bushes, moss and spires within this distance of where the falls land.
POND = 2.6


def in_pond(o):
    micro = o.matrix_world.translation
    world = ORIGIN + Vector((micro.x, micro.y, 0)) * S
    return Vector((world.x, world.y)).length < POND


for o in list(root.children):
    if o.name.startswith(('Leaf', 'Moss', 'Spire')) and in_pond(o):
        continue
    if o.name == 'Water':
        # The macro biome's water is the pool the falls land in.
        copy_tree(o, macro, 'Pool')
    elif o.name.startswith(COPY) and o.name != 'Planter.Source':
        copy_tree(o, macro)

# --- Shoreline garden ------------------------------------------------------------------------------------------------


def clay(name, rgb, roughness=0.35, alpha=1.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*rgb, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Coat Weight'].default_value = 0.6
    bsdf.inputs['Alpha'].default_value = alpha
    if alpha < 1:
        mat.surface_render_method = 'BLENDED'
    return mat


PAD = clay('LilyPad', (0.16, 0.5, 0.22))
REED = clay('Reed', (0.32, 0.58, 0.24))
CATTAIL = clay('Cattail', (0.42, 0.24, 0.12))
PEBBLE = clay('Pebble', (0.78, 0.72, 0.64), 0.5)
CAP = clay('MushroomCap', (0.92, 0.33, 0.28))
STALK = clay('MushroomStalk', (0.96, 0.9, 0.8))
FROG = clay('Frog', (0.36, 0.74, 0.3))
BELLY = clay('FrogBelly', (0.85, 0.92, 0.6))
EYE = clay('Eye', (0.98, 0.98, 0.96), 0.2)
PUPIL = clay('Pupil', (0.05, 0.05, 0.06), 0.2)
SHELL = clay('SnailShell', (0.86, 0.55, 0.3))
SNAIL = clay('SnailBody', (0.86, 0.76, 0.62))
DRAGON = clay('Dragonfly', (0.1, 0.58, 0.68), 0.25)
WING = clay('Wing', (0.92, 0.97, 1.0), 0.15, alpha=0.45)

rnd = random.Random(21)


def part(bm_fn, name, material, location=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1), parent=None, smooth=True, subdiv=0):
    bm = bmesh.new()
    bm_fn(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    me.materials.append(material)
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    o.parent = parent or root
    o.location, o.rotation_euler, o.scale = location, rotation, scale
    if subdiv:
        o.modifiers.new('Smooth', 'SUBSURF').levels = subdiv
    return o


def sphere(r, segments=24, rings=12):
    return lambda bm: bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=r)


def cone(r1, r2, depth, segments=16):
    return lambda bm: bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=r1, radius2=r2, depth=depth)


def lily_pad(bm, r):
    """A flat disc with the wedge notch lily pads have."""
    geom = bmesh.ops.create_circle(bm, cap_ends=True, segments=40, radius=r)
    notch = [v for v in geom['verts'] if v.co.length > 1e-6 and abs(math.atan2(v.co.y, v.co.x)) < 0.22]
    for v in notch:
        v.co *= 0.15
    bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=0.02)


def garden_object(name):
    o = bpy.data.objects.new(name, None)
    scene.collection.objects.link(o)
    o.parent = root
    return o


# The open water is the corner around the splash: inside the walls (x < 0.73, y > -0.73) and short of the bushes to
# the west and north. The camera comes down to eye level at CAMERA, looking across it toward the falls.
CAMERA = Vector((-2.4, -0.35))
FROG_PAD = Vector((-1.55, 0.05))


def open_water(p, margin):
    inside = p.x < 0.73 - margin and p.y > -0.73 + margin and p.length < POND - margin
    return inside and p.length > 1.25 and (p - CAMERA).length > 0.4 and (p - FROG_PAD).length > 0.45


# Lily pads, mostly between the camera and the splash.
pads = []
tries = 0
while len(pads) < 12 and tries < 500:
    tries += 1
    a = math.radians(rnd.uniform(100, 270))
    d = rnd.uniform(1.3, 2.5)
    r = rnd.uniform(0.12, 0.26)
    p = Vector((math.cos(a) * d, math.sin(a) * d))
    if not open_water(p, r) or any((p - q.location.xy).length < r + qr + 0.05 for q, qr in pads):
        continue
    o = part(lambda bm, r=r: lily_pad(bm, r), f'Garden.LilyPad.{len(pads)}', PAD, (p.x, p.y, POOL_Z + 0.012), (0, 0, rnd.uniform(0, 6.28)), smooth=False)
    pads.append((o, r))

# The frog sits on its own big pad in the middle of the view, facing the camera.
part(lambda bm: lily_pad(bm, 0.3), 'Garden.LilyPad.Frog', PAD, (FROG_PAD.x, FROG_PAD.y, POOL_Z + 0.012), (0, 0, 2.2), smooth=False)
frog = garden_object('Garden.Frog')
frog.location = (FROG_PAD.x, FROG_PAD.y, POOL_Z + 0.032)
frog.rotation_euler = (0, 0, math.atan2(CAMERA.y - FROG_PAD.y, CAMERA.x - FROG_PAD.x))
part(sphere(0.11), 'Garden.Frog.Body', FROG, (0, 0, 0.08), scale=(1.15, 0.95, 0.75), parent=frog)
part(sphere(0.09), 'Garden.Frog.Belly', BELLY, (0.04, 0, 0.06), scale=(1.0, 0.85, 0.6), parent=frog)
part(sphere(0.075), 'Garden.Frog.Head', FROG, (0.1, 0, 0.13), scale=(1.0, 1.1, 0.8), parent=frog)
for side in (-1, 1):
    part(sphere(0.035), f'Garden.Frog.Eye{side}', EYE, (0.13, 0.05 * side, 0.19), parent=frog)
    part(sphere(0.016), f'Garden.Frog.Pupil{side}', PUPIL, (0.158, 0.055 * side, 0.2), parent=frog)
    part(sphere(0.045), f'Garden.Frog.Leg{side}', FROG, (-0.05, 0.1 * side, 0.03), scale=(1.6, 0.8, 0.6), parent=frog)
    part(sphere(0.03), f'Garden.Frog.Arm{side}', FROG, (0.12, 0.07 * side, 0.03), scale=(1.4, 0.7, 0.6), parent=frog)

# Reeds and cattails in clumps round the pond's edge: by the bushes to the west and north, along the east and south walls.
CLUMPS = [Vector((-2.55, 0.9)), Vector((-1.05, 2.45)), Vector((0.5, 1.35)), Vector((-1.5, -0.6))]
for c, centre in enumerate(CLUMPS):
    for i in range(rnd.randint(6, 9)):
        off = Vector((rnd.gauss(0, 0.16), rnd.gauss(0, 0.16)))
        h = rnd.uniform(0.5, 1.15)
        lean = (rnd.uniform(-0.12, 0.12), rnd.uniform(-0.12, 0.12), 0)
        base = Vector((centre.x + off.x, centre.y + off.y, POOL_Z - 0.05))
        stem = part(cone(0.024, 0.008, h, 8), f'Garden.Reed.{c}.{i}', REED, base + Vector((0, 0, h / 2)), lean)
        if rnd.random() < 0.5:
            part(sphere(0.035, 12, 8), f'Garden.Cattail.{c}.{i}', CATTAIL, (0, 0, h * 0.32), scale=(1, 1, 3.2), parent=stem)

# Pebbles along the shores, half in the water.
for i in range(22):
    centre = rnd.choice(CLUMPS)
    a = rnd.uniform(0, 6.28)
    d = rnd.uniform(0.25, 0.6)
    r = rnd.uniform(0.05, 0.14)
    part(sphere(r, 16, 8), f'Garden.Pebble.{i}', PEBBLE, (centre.x + math.cos(a) * d, centre.y + math.sin(a) * d, POOL_Z + r * 0.15),
         (0, 0, rnd.uniform(0, 6.28)), (1.3, 1, 0.55))

# Mushrooms on the bush mounds rising out of the water.
MOUNDS = []
for o in bpy.data.objects:
    if o.name.startswith('Macro.Leaf.'):
        w = o.matrix_world.translation
        if (w.xy.length < 3.8) and w.z > POOL_Z - 0.1:
            MOUNDS.append(w.copy())
rnd.shuffle(MOUNDS)
for i, m in enumerate(MOUNDS[:7]):
    h = rnd.uniform(0.12, 0.26)
    top = m + Vector((rnd.uniform(-0.15, 0.15), rnd.uniform(-0.15, 0.15), 0.25))
    stalk = part(cone(0.03, 0.022, h, 12), f'Garden.Mushroom.{i}', STALK, top + Vector((0, 0, h / 2)), (rnd.uniform(-0.15, 0.15), rnd.uniform(-0.15, 0.15), 0))
    part(lambda bm: bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=10, radius=1), f'Garden.Mushroom.{i}.Cap', CAP, (0, 0, h / 2), scale=(h * 0.55, h * 0.55, h * 0.32), parent=stalk)

# A snail on a pebble at the spire's foot.
snail = garden_object('Garden.Snail')
snail.location = (CLUMPS[0].x + 0.35, CLUMPS[0].y - 0.3, POOL_Z + 0.09)
part(sphere(0.17, 16, 8), 'Garden.Pebble.Snail', PEBBLE, (snail.location.x - 0.02, snail.location.y, POOL_Z + 0.01), scale=(1.3, 1.1, 0.5))
snail.rotation_euler = (0, 0, math.radians(-40))
part(sphere(0.05, 16, 8), 'Garden.Snail.Body', SNAIL, (0, 0, 0.02), scale=(2.2, 0.8, 0.6), parent=snail)
part(lambda bm: bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.012, radius2=0.006, depth=0.06), 'Garden.Snail.Horn1', SNAIL, (0.1, 0.02, 0.06), (0, 0.5, 0), parent=snail)
part(lambda bm: bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.012, radius2=0.006, depth=0.06), 'Garden.Snail.Horn2', SNAIL, (0.1, -0.02, 0.06), (0, 0.5, 0), parent=snail)


def spiral_shell(bm):
    """A coiled shell: a tapering tube wound round on itself."""
    prev = None
    turns, steps, ring = 2.6, 70, 10
    for i in range(steps + 1):
        t = i / steps
        a = t * turns * 2 * math.pi
        rad = 0.07 * (1 - t * 0.85)
        centre = Vector((math.cos(a) * rad, 0, math.sin(a) * rad))
        tube = 0.04 * (1 - t * 0.8)
        normal = Vector((math.cos(a), 0, math.sin(a)))
        verts = [bm.verts.new(centre + normal * math.cos(k / ring * 6.283) * tube + Vector((0, 1, 0)) * math.sin(k / ring * 6.283) * tube) for k in range(ring)]
        if prev:
            for k in range(ring):
                bm.faces.new((prev[k], prev[(k + 1) % ring], verts[(k + 1) % ring], verts[k]))
        prev = verts


part(spiral_shell, 'Garden.Snail.Shell', SHELL, (-0.02, 0, 0.1), parent=snail)

# Two dragonflies hovering over the reeds (the site sets them darting about; here they're placed).
for i, centre in enumerate((CLUMPS[0], CLUMPS[2])):
    fly = garden_object(f'Garden.Dragonfly.{i}')
    fly.location = (centre.x + 0.2, centre.y - 0.25, POOL_Z + 0.75 + 0.15 * i)
    fly.rotation_euler = (0, 0, rnd.uniform(0, 6.28))
    part(cone(0.012, 0.006, 0.2, 10), f'Garden.Dragonfly.{i}.Body', DRAGON, (0, 0, 0), (0, math.pi / 2, 0), parent=fly)
    part(sphere(0.02, 12, 8), f'Garden.Dragonfly.{i}.Head', DRAGON, (0.1, 0, 0), parent=fly)
    for side in (-1, 1):
        for front, x in ((0, 0.04), (1, 0.0)):
            part(sphere(0.06, 12, 6), f'Garden.Dragonfly.{i}.Wing{side}{front}', WING, (x, 0.07 * side, 0.01), (0, 0, side * (0.25 if front == 0 else -0.2)),
                 (0.28, 1.0, 0.04), parent=fly, smooth=False)

for o in [o for o in bpy.data.objects if o.name.startswith('Garden.') and o.type == 'MESH']:
    o.data.name = o.name
