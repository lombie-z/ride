"""The sky below the planter: a layer of big clay clouds the camera punches through, a low sun beyond it, and a
rainbow in the spray over the pool. Re-runnable (rebuilds all three). Visibility over the journey is keyed by
build-journey.py. Run inside Blender with art/micro-biome.blend open:  exec(open('<repo>/art/build-sky.py').read())"""
import math
import random

import bmesh
import bpy
from mathutils import Vector

scene = bpy.context.scene
root = bpy.data.objects['MicroBiome']
POOL_Z = -11.0
CLOUD_Z = -1.65


def fresh_object(name, me):
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old)
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    o.parent = root
    return o


# --- Cloud layer ------------------------------------------------------------------------------------------------------

# (centre, size). The first sits just off the camera's way down, so it skims past it (close, never through); the
# middle one is pierced by the falls.
CLOUDS = [
    ((1.25, -2.45, CLOUD_Z - 0.1), 1.3),
    ((0.0, 0.0, CLOUD_Z - 0.05), 1.0),
    ((-2.0, -0.8, CLOUD_Z + 0.15), 1.5),
    ((-1.0, 1.8, CLOUD_Z - 0.15), 1.4),
    ((1.9, 0.9, CLOUD_Z + 0.1), 1.3),
    ((2.6, -1.6, CLOUD_Z - 0.25), 1.0),
    ((-2.6, -2.4, CLOUD_Z - 0.1), 1.1),
    ((-0.6, -3.4, CLOUD_Z + 0.2), 0.9),
]


def cloud(name, centre, size, seed):
    """A puff of overlapping balls, rounder on top and flatter underneath, fused by a voxel remesh like the biome's
    own clouds."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    for i in range(9):
        a = rnd.uniform(0, 2 * math.pi)
        d = rnd.uniform(0.0, 0.55) * size
        r = rnd.uniform(0.28, 0.45) * size * (1.15 if d < 0.2 * size else 1)
        geom = bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=r)
        bmesh.ops.scale(bm, vec=(1, 1, 0.75), verts=geom['verts'])
        lift = rnd.uniform(0.0, 0.18) * size * (1 - d / size)
        bmesh.ops.translate(bm, vec=Vector(centre) + Vector((math.cos(a) * d, math.sin(a) * d * 0.7, lift)), verts=geom['verts'])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = fresh_object(name, me)
    fuse = o.modifiers.new('Fuse', 'REMESH')
    fuse.mode = 'VOXEL'
    fuse.voxel_size = 0.035
    fuse.use_smooth_shade = True
    soften = o.modifiers.new('Soften', 'CORRECTIVE_SMOOTH')
    soften.factor = 0.5
    soften.iterations = 10
    soften.smooth_type = 'SIMPLE'
    soften.use_only_smooth = True
    me.materials.append(bpy.data.materials['Cloud'])
    return o


def cloud_whiteout():
    """Inside a cloud (its back faces) everything glows soft white, so flying through one is a clean whiteout rather
    than a shadowed grey. Outside, the biome's cloud clay is unchanged."""
    mat = bpy.data.materials['Cloud']
    nt = mat.node_tree
    if 'Whiteout' in nt.nodes:
        nt.nodes['Whiteout'].inputs['Strength'].default_value = 2.6
        return
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    surface = out.inputs['Surface'].links[0].from_socket
    geometry = nt.nodes.new('ShaderNodeNewGeometry')
    glow = nt.nodes.new('ShaderNodeEmission')
    glow.name = 'Whiteout'
    glow.inputs['Color'].default_value = (0.97, 0.95, 0.93, 1)
    glow.inputs['Strength'].default_value = 2.6  # bright enough to read as white after the view transform
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(geometry.outputs['Backfacing'], mix.inputs['Fac'])
    nt.links.new(surface, mix.inputs[1])
    nt.links.new(glow.outputs['Emission'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    mat.use_backface_culling = False


cloud_whiteout()
for o in [o for o in bpy.data.objects if o.name.startswith('SkyCloud.')]:
    bpy.data.objects.remove(o)
for i, (centre, size) in enumerate(CLOUDS):
    cloud(f'SkyCloud.{i}', centre, size, 40 + i)

# --- Sun --------------------------------------------------------------------------------------------------------------


def emissive(name, colour, strength):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*colour, 1)
    em.inputs['Strength'].default_value = strength
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    return mat


bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=5.5)
me = bpy.data.meshes.new('Sun')
bm.to_mesh(me)
bm.free()
for poly in me.polygons:
    poly.use_smooth = True
me.materials.append(emissive('Sun', (1.0, 0.6, 0.25), 8.0))
sun = fresh_object('Sun', me)
# Low and off to one side of the falls (never straight behind them, where it would show through the water), in view
# from the shots below the clouds.
sun.location = (60, 20, -0.5)

# --- Rainbow ----------------------------------------------------------------------------------------------------------


def rainbow_material():
    """Spectral bands across the arc (UV u: 0 outer red -> 1 inner violet), glowing faintly, mostly see-through."""
    mat = bpy.data.materials.get('Rainbow') or bpy.data.materials.new('Rainbow')
    mat.use_nodes = True
    mat.surface_render_method = 'BLENDED'
    mat.use_backface_culling = False
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    uv = nt.nodes.new('ShaderNodeUVMap')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(uv.outputs['UV'], sep.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    bands = [(1.0, 0.25, 0.25), (1.0, 0.6, 0.2), (1.0, 0.92, 0.3), (0.35, 0.85, 0.4), (0.3, 0.6, 1.0), (0.6, 0.4, 1.0)]
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = 0.0, (*bands[0], 1)
    ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = 1.0, (*bands[-1], 1)
    for i, rgb in enumerate(bands[1:-1], start=1):
        ramp.color_ramp.elements.new(i / (len(bands) - 1)).color = (*rgb, 1)
    nt.links.new(sep.outputs['X'], ramp.inputs['Fac'])
    # Soft edges across the band and fading out toward the feet of the arc.
    edge = nt.nodes.new('ShaderNodeMath')
    edge.operation = 'SINE'
    pi_x = nt.nodes.new('ShaderNodeMath')
    pi_x.operation = 'MULTIPLY'
    pi_x.inputs[1].default_value = math.pi
    nt.links.new(sep.outputs['X'], pi_x.inputs[0])
    nt.links.new(pi_x.outputs['Value'], edge.inputs[0])
    feet = nt.nodes.new('ShaderNodeMath')
    feet.operation = 'SINE'
    pi_y = nt.nodes.new('ShaderNodeMath')
    pi_y.operation = 'MULTIPLY'
    pi_y.inputs[1].default_value = math.pi
    nt.links.new(sep.outputs['Y'], pi_y.inputs[0])
    nt.links.new(pi_y.outputs['Value'], feet.inputs[0])
    alpha = nt.nodes.new('ShaderNodeMath')
    alpha.operation = 'MULTIPLY'
    nt.links.new(edge.outputs['Value'], alpha.inputs[0])
    nt.links.new(feet.outputs['Value'], alpha.inputs[1])
    strength = nt.nodes.new('ShaderNodeMath')
    strength.operation = 'MULTIPLY'
    strength.inputs[1].default_value = 0.8
    strength.label = 'bow'  # build-journey.py keys its fade-in
    nt.links.new(alpha.outputs['Value'], strength.inputs[0])
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = 1.7
    nt.links.new(ramp.outputs['Color'], em.inputs['Color'])
    clear = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(strength.outputs['Value'], mix.inputs['Fac'])
    nt.links.new(clear.outputs['BSDF'], mix.inputs[1])
    nt.links.new(em.outputs['Emission'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return mat


# An arch over the pool, the big fall pouring through its middle, facing the way the camera lands.
RADIUS, WIDTH, SEGMENTS = 4.6, 0.6, 128
bm = bmesh.new()
uv_layer = bm.loops.layers.uv.new('UVMap')
rows = []
for i in range(SEGMENTS + 1):
    a = math.radians(8 + 164 * i / SEGMENTS)
    rows.append([bm.verts.new((math.cos(a) * (RADIUS - WIDTH * k), 0, math.sin(a) * (RADIUS - WIDTH * k))) for k in (0, 1)])
for i in range(SEGMENTS):
    face = bm.faces.new((rows[i][0], rows[i + 1][0], rows[i + 1][1], rows[i][1]))
    for loop, uv in zip(face.loops, ((0, i / SEGMENTS), (0, (i + 1) / SEGMENTS), (1, (i + 1) / SEGMENTS), (1, i / SEGMENTS)), strict=True):
        loop[uv_layer].uv = uv
me = bpy.data.meshes.new('Rainbow')
bm.to_mesh(me)
bm.free()
me.materials.append(rainbow_material())
bow = fresh_object('Rainbow', me)
bow.location = (0.4, -2.2, POOL_Z - 0.4)
bow.rotation_euler = (0, 0, math.radians(-86))  # faces the landing camera, arcing off to the right of the fall
