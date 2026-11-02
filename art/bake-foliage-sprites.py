"""Render scanned trees and shrubs (Poly Haven, CC0) into sprites for the landing's cliffs: each model from a few
angles, side-on and orthographic, lit as the landing is (a low gold sun from the left and behind, a rosy sky fill), on
a transparent background. The site draws thousands of these as camera-facing cards (components/three/foliage.tsx),
so the cliffs get real trees for the cost of one texture.

Run: blender --background --factory-startup --python art/bake-foliage-sprites.py -- <models dir> <out dir>
<models dir> holds Poly Haven glTF downloads, one folder per asset (e.g. island_tree_01/island_tree_01_1k.gltf).
Writes <out dir>/<asset>[_pink]_<view>.png at 512 px; art/pack-foliage-atlas.py packs them into one atlas.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

models_dir, out_dir = sys.argv[sys.argv.index('--') + 1:][:2]
os.makedirs(out_dir, exist_ok=True)

# (asset, views, pink, apart): pink renders a blossom variant (leaves hue-shifted to the reference's pink); apart
# renders each plant in the file on its own (Poly Haven's shrub files lay several out side by side).
ASSETS = [('island_tree_01', 3, True, False), ('island_tree_02', 3, False, False), ('shrub_04', 1, False, True),
          ('shrub_02', 1, True, True)]
SIZE = 512


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 96
    scene.cycles.use_denoising = True
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'METAL'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        scene.cycles.device = 'GPU'
    except Exception:
        pass
    scene.render.resolution_x = scene.render.resolution_y = SIZE
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.view_settings.view_transform = 'Standard'
    # Rosy sky fill, as the landing's.
    world = bpy.data.worlds.new('Sky')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.85, 0.66, 0.68, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.55
    scene.world = world
    return scene


def pinken(objects):
    """Shift leaf colours from green to blossom pink."""
    for o in objects:
        for slot in o.material_slots:
            mat = slot.material
            if not mat or not mat.use_nodes:
                continue
            nt = mat.node_tree
            bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if not bsdf or not bsdf.inputs['Base Color'].links:
                continue
            link = bsdf.inputs['Base Color'].links[0]
            # Only foliage: leaf materials use alpha cut-outs.
            if not bsdf.inputs['Alpha'].links and 'leaf' not in mat.name.lower() and 'leaves' not in mat.name.lower():
                continue
            hue = nt.nodes.new('ShaderNodeHueSaturation')
            hue.inputs['Hue'].default_value = 0.27
            hue.inputs['Saturation'].default_value = 0.6
            hue.inputs['Value'].default_value = 2.1
            nt.links.new(link.from_socket, hue.inputs['Color'])
            nt.links.new(hue.outputs['Color'], bsdf.inputs['Base Color'])


def bounds(objects):
    corners = [o.matrix_world @ Vector(c) for o in objects for c in o.bound_box]
    lo = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    hi = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    return lo, hi


def render_views(scene, objects, views, name):
    lo, hi = bounds(objects)
    centre = (lo + hi) / 2
    span = max(hi.x - lo.x, hi.y - lo.y, hi.z - lo.z) * 1.04
    cam_data = bpy.data.cameras.new('Cam')
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = span
    cam = bpy.data.objects.new('Cam', cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    sun_data = bpy.data.lights.new('Sun', 'SUN')
    sun_data.energy = 4.5
    sun_data.color = (1.0, 0.76, 0.5)
    sun_data.angle = math.radians(2)
    sun = bpy.data.objects.new('Sun', sun_data)
    scene.collection.objects.link(sun)
    for v in range(views):
        a = 2 * math.pi * v / views
        direction = Vector((math.cos(a), math.sin(a), 0))
        cam.location = centre - direction * span * 3
        cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
        # The low sun from the camera's left and a little behind the plant, 20 degrees up.
        left = Vector((-direction.y, direction.x, 0))
        light_from = (left * 0.8 + direction * 0.45).normalized() + Vector((0, 0, 0.36))
        sun.rotation_euler = (-light_from).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(out_dir, f'{name}_{v}.png')
        bpy.ops.render.render(write_still=True)
        print('rendered', f'{name}_{v}', flush=True)
    bpy.data.objects.remove(cam)
    bpy.data.objects.remove(sun)


for asset, views, pink, apart in ASSETS:
    gltf = os.path.join(models_dir, asset, f'{asset}_1k.gltf')
    for variant in ([False, True] if pink else [False]):
        scene = reset()
        bpy.ops.import_scene.gltf(filepath=gltf)
        objects = [o for o in scene.objects if o.type == 'MESH']
        if variant:
            pinken(objects)
        name = f'{asset}{"_pink" if variant else ""}'
        if not apart:
            render_views(scene, objects, views, name)
            continue
        for k, o in enumerate(objects):
            for other in objects:
                other.hide_render = other is not o
            render_views(scene, [o], views, f'{name}_{chr(97 + k)}')
