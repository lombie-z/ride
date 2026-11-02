"""Export JourneyCam as the site's scroll track: public/journey.json, one sample per frame in three.js space (y up).
Each sample is [x, y, z, qx, qy, qz, qw, fov]: position, orientation, vertical field of view in degrees.
Run: blender --background art/micro-biome.blend --python art/export-journey.py"""
import json
import math
import os

import bpy
from mathutils import Quaternion

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(bpy.data.filepath), '..'))
OUT = os.path.join(ROOT_DIR, 'public', 'journey.json')

scene = bpy.context.scene
cam = bpy.data.objects['JourneyCam']
# Blender is z up, three.js y up (as glTF): (x, y, z) -> (x, z, -y), and the same turn for orientations.
TO_Y_UP = Quaternion((1, 0, 0), math.radians(-90))

samples = []
for f in range(scene.frame_start, scene.frame_end + 1):
    scene.frame_set(f)
    loc, rot, _ = cam.matrix_world.decompose()
    q = TO_Y_UP @ rot
    fov = math.degrees(2 * math.atan(cam.data.sensor_height / 2 / cam.data.lens))
    samples.append([round(v, 4) for v in (loc.x, loc.z, -loc.y, q.x, q.y, q.z, q.w, fov)])

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w') as fh:
    json.dump({'frames': samples}, fh, separators=(',', ':'))
print(f'Wrote {len(samples)} samples to {OUT}')
