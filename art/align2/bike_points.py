"""Dump the site's bike (public/models/bike.glb: origin on the ground between the wheels, front +x) as points for
fit_camera.py: art/align2/out/bike-points.npz (a vertex sample, the wheel centres and radii).
Run: /opt/homebrew/bin/blender --background --factory-startup --python art/align2/bike_points.py
"""
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import BIKE_GLB, OUT  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=BIKE_GLB)
pts = []
for o in bpy.data.objects:
    if o.type == 'MESH':
        m = o.matrix_world
        pts += [tuple(m @ v.co) for v in o.data.vertices]
pts = np.array(pts)
rng = np.random.default_rng(0)
pts = pts[rng.choice(len(pts), min(8000, len(pts)), replace=False)]
wheels = {}
for n in ('WheelFront', 'WheelRear'):
    o = bpy.data.objects[n]
    wheels[n] = np.r_[np.array(o.matrix_world.translation), o.dimensions.z / 2]
os.makedirs(OUT, exist_ok=True)
np.savez(os.path.join(OUT, 'bike-points.npz'), pts=pts, front=wheels['WheelFront'], rear=wheels['WheelRear'])
print('bike points', pts.shape, wheels)
