"""What each asset script (art/core/assets/<name>.py) shares: the contract in art/core/ASSETS.md, done for you.

    import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import _common as A
    kit = A.begin()                 # a fresh scene on the kit: its materials (kit.MAT), helpers, textures
    ... make meshes, each with kit.material(f'{kit.PREFIX}...') slots; A.obj(mesh) links one in ...
    A.finish(kit, 'stair_pipe_stub', budget=300)   # checks it, exports art/out/assets/<name>.glb, renders art/renders/assets/<name>.png and <name>-px7.png

Run: blender --background --factory-startup --python art/core/assets/<name>.py
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..')))
sys.dont_write_bytecode = True
import kit as _kit  # noqa: E402

OUT = os.path.join(_kit.ROOT_DIR, 'art', 'out', 'assets')
STILLS = os.path.join(_kit.ROOT_DIR, 'art', 'renders', 'assets')


def begin():
    _kit.begin()
    return _kit


def obj(me, name=None, loc=(0, 0, 0)):
    o = bpy.data.objects.new(name or me.name, me)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    return o


def _meshes():
    return [o for o in bpy.context.scene.objects if o.type == 'MESH']


def _check(kit, name, budget):
    ms = _meshes()
    if not ms:
        raise RuntimeError('nothing to export')
    tris = sum(kit.tris(o.data) for o in ms)
    if budget and tris > budget:
        raise RuntimeError(f'{name}: {tris} tris over its budget of {budget}')
    for o in ms:
        for m in o.data.materials:
            if not m or not m.name.startswith(kit.PREFIX):
                raise RuntimeError(f'{name}: material {m.name if m else None} must be named {kit.PREFIX}...')
        if 'AO' not in o.data.color_attributes:
            for m in o.data.materials:
                # (Kit materials multiply by the AO attribute: without it they render black.)
                if any(n.type == 'VERTEX_COLOR' for n in m.node_tree.nodes):
                    raise RuntimeError(f'{name}: {o.name} needs its vertex colours: kit.bake_light(me, [], ambient=(1, 1, 1)) or lights')
        if 'UVMap' not in o.data.uv_layers:
            for m in o.data.materials:
                if any(n.type == 'TEX_IMAGE' for n in m.node_tree.nodes):
                    raise RuntimeError(f'{name}: {o.name} has a textured slot, no UVMap')
    return tris


def export(name, animations=False):
    os.makedirs(OUT, exist_ok=True)
    for o in bpy.context.scene.objects:
        o.select_set(True)
    path = os.path.join(OUT, name + '.glb')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_apply=not animations, export_animations=animations,
                              export_vertex_color='ACTIVE', export_image_format='AUTO', export_image_quality=85,
                              export_yup=True, export_cameras=False, export_lights=False, export_extras=True)
    return path


def still(name, dist=None, look_at=None, eye=None, fov=70.0, ambient=(0.1, 0.13, 0.11)):
    """A rider-height still, lit as the site is (no lamps: emission, baked vertex light, a dim ambient), and the same at the scene's pixel."""
    os.makedirs(STILLS, exist_ok=True)
    scene = bpy.context.scene
    ms = _meshes()
    pts = [o.matrix_world @ Vector(c) for o in ms for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    c = (lo + hi) / 2
    r = max((hi - lo).length / 2, 0.5)
    look = Vector(look_at) if look_at else c
    # Rider's eye: 1.45 up from the road (z of the origin), a three-quarter view from up the road.
    e = Vector(eye) if eye else Vector((c.x - 1.6 * r - 0.5, c.y - 0.9 * r, 1.45))
    cam = bpy.data.objects.new('StillCam', bpy.data.cameras.new('StillCam'))
    scene.collection.objects.link(cam)
    cam.location = e
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (look - e).normalized().to_track_quat('-Z', 'Y')
    cam.data.sensor_fit = 'VERTICAL'
    cam.data.angle_y = math.radians(fov)
    cam.data.clip_start = 0.02
    scene.camera = cam
    w = bpy.data.worlds.new('Ambient')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (*ambient, 1)
    scene.world = w
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.render.image_settings.file_format = 'PNG'
    p = os.path.join(STILLS, name + '.png')
    scene.render.filepath = p
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(p)
    W, H = img.size
    px = np.array(img.pixels[:], np.float32).reshape(H, W, 4)
    k = 7
    idx_y = (np.arange(H) // k) * k
    idx_x = (np.arange(W) // k) * k
    out = px[np.ix_(idx_y, idx_x)]
    im2 = bpy.data.images.new(name + '-px7', W, H)
    im2.pixels.foreach_set(out.ravel())
    im2.filepath_raw = os.path.join(STILLS, name + '-px7.png')
    im2.file_format = 'PNG'
    im2.save()
    bpy.data.objects.remove(cam)


def finish(kit, name, budget=None, animations=False, **still_args):
    tris = _check(kit, name, budget)
    still(name, **still_args)
    path = export(name, animations=animations)
    print(f'ASSET {name}: {tris} tris (budget {budget}), {os.path.getsize(path)} bytes -> {path}')
