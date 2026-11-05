"""The stills of art/core/stair.py and flood.py from the rider's eye, as the site has it (bike5.glb; eye 1.45 up, 0.14 back; 8 degrees down and fov 82, the framing that puts the references' dash and road in the same place: SECTIONS.md):
  blender --background --factory-startup --python art/core/render_sections.py -- [stair|flood|both] [shot,shot|all] [tag]
Beauty and a fog pass into art/renders/sections/raw; python3 art/core/sheet_sections.py then adds the site's fog and bloom and makes the sheet.
The only thing that isn't the site's: faint lamps at the fixtures (each section's LAMPS), standing in for the light the stand-ins haven't baked. LAMPS_K scales them."""
import importlib
import json
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
import kit  # noqa: E402
import road_sections as R  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
which = args[0] if args else 'both'
only = args[1].split(',') if len(args) > 1 and args[1] != 'all' else None
RES = (1280, 720)
RAW = os.path.join(kit.ROOT_DIR, 'art', 'renders', 'sections', 'raw')
os.makedirs(RAW, exist_ok=True)
LAMPS_K = float(os.environ.get('LAMPS_K', '0.9'))
NEAR_LAMPS = 150.0
PITCH = math.radians(float(os.environ.get('RIDER_PITCH', '8')))   # the site's 15 cuts the image's upper half off; see SECTIONS.md
BACK, UP = 0.14, 1.45


def fog_material(near, far):
    m = bpy.data.materials.new('FogPass')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    cam = nt.nodes.new('ShaderNodeCameraData')
    a = nt.nodes.new('ShaderNodeMapRange')
    a.inputs['From Min'].default_value = near
    a.inputs['From Max'].default_value = far
    a.clamp = True
    e = nt.nodes.new('ShaderNodeEmission')
    o = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(cam.outputs['View Distance'], a.inputs['Value'])
    nt.links.new(a.outputs['Result'], e.inputs['Color'])
    nt.links.new(e.outputs['Emission'], o.inputs['Surface'])
    return m


def bike_frame(road, spec):
    """The bike's frame at the shot: (contact, x, y, z). `level`: just before the lip, or parked on the flat: its pitch hasn't followed."""
    c, f, t, up, _r = R.at(road, spec['s'])
    if spec.get('level') or spec.get('parked'):
        t = np.array([t[0], t[1], 0.0])
        t /= np.linalg.norm(t)
        up = np.array([0, 0, 1.0])
    xx = Vector(t).normalized()
    zz = (Vector(up) - xx * Vector(up).dot(xx)).normalized()
    yy = zz.cross(xx)
    return Vector(f), xx, yy, zz


def run(name, modname, near, far):
    kit._groups.clear()
    kit._tex.clear()
    B.M.clear()
    import assetkit
    assetkit.reset()
    kit.begin()
    mod = importlib.import_module(modname)
    mod.place(kit, mod.build(kit))
    road = mod.ROAD
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.taa_render_samples = 24
    scene.eevee.use_raytracing = True
    scene.eevee.ray_tracing_options.resolution_scale = '2'
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.view_settings.look = 'None'
    w = bpy.data.worlds.new('Ambient')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.07, 0.058, 1)
    scene.world = w
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    scene.collection.objects.link(cam)
    cam.data.clip_start = 0.05
    cam.data.clip_end = 1500
    cam.data.sensor_fit = 'VERTICAL'
    scene.camera = cam
    # The bike.
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(kit.ROOT_DIR, 'public', 'models', 'bike5.glb'))
    imported = set(bpy.data.objects) - before
    bike = bpy.data.objects.new('BikeRoot', None)
    scene.collection.objects.link(bike)
    for o in imported:
        if o.parent is None:
            o.parent = bike
    # The stand-in lamps.
    lamps = []
    for i, (x, y, z, col, power) in enumerate(mod.LAMPS):
        o = bpy.data.objects.new(f'L{i}', bpy.data.lights.new(f'L{i}', 'POINT'))
        scene.collection.objects.link(o)
        o.location = (x, y, z)
        o.data.color = col
        o.data.energy = power * LAMPS_K
        o.data.shadow_soft_size = 0.6
        o.data.use_shadow = False
        lamps.append(o)
    fogm = fog_material(near, far)
    vl = bpy.context.view_layer
    for shot, spec in mod.SHOTS.items():
        if only and shot not in only:
            continue
        if 'door' in spec and hasattr(mod, 'DOOR'):
            set_door(mod, spec['door'])
        f, xx, yy, zz = bike_frame(road, spec)
        m = Matrix((xx, yy, zz)).transposed().to_4x4()
        m.translation = f
        bike.matrix_world = m
        # The camera, in the bike's frame.
        eye = f + zz * UP - xx * BACK
        d = xx * math.cos(PITCH) - zz * math.sin(PITCH)
        u = zz * math.cos(PITCH) + xx * math.sin(PITCH)
        zc = -d
        xc = u.cross(zc)
        cm = Matrix((xc, u, zc)).transposed().to_4x4()
        cm.translation = eye
        cam.matrix_world = cm
        cam.data.angle_y = math.radians(spec.get('fov', 82.0))
        for o in lamps:
            o.hide_render = (o.location - eye).length > NEAR_LAMPS
        vl.update()
        scene.view_settings.view_transform = 'Standard'
        vl.material_override = None
        scene.render.image_settings.file_format = 'PNG'
        scene.render.image_settings.color_mode = 'RGB'
        scene.render.filepath = os.path.join(RAW, f'{shot}.png')
        bpy.ops.render.render(write_still=True)
        scene.view_settings.view_transform = 'Raw'
        vl.material_override = fogm
        for o in lamps:
            o.hide_render = True
        scene.render.filepath = os.path.join(RAW, f'{shot}-fog.png')
        bpy.ops.render.render(write_still=True)
        vl.material_override = None
    with open(os.path.join(RAW, f'{name}-titles.json'), 'w') as fh:
        json.dump({k: v['title'] for k, v in mod.SHOTS.items()}, fh)
    import stair as ST
    ST.report(kit, name, '')


def set_door(mod, t):
    mod.DOOR['hinge_obj'].matrix_basis = mod.DOOR['H0'] @ Matrix.Rotation(-t * math.radians(R.DOOR_OPEN_DEG), 4, 'Z')


if which in ('stair', 'both'):
    run('stair', 'stair', 18.0, 170.0)
if which in ('flood', 'both'):
    run('flood', 'flood', 10.0, 200.0)
