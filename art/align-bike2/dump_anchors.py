"""Dump bike.blend's root/wheel/anchor transforms (bike-local) to art/align-bike2/bike1-anchors.json.
Run: blender --background art/bike.blend --python art/align-bike2/dump_anchors.py"""
import bpy, json, os
from mathutils import Vector
out = {}
body = bpy.data.objects['Bike']
out['Bike'] = {'location': list(body.location), 'rotation_euler': list(body.rotation_euler)}
for n in ('WheelFront', 'WheelRear', 'ButtonCentre', 'RiderEye', 'BikeButton', 'BikeButtonGlyph'):
    o = bpy.data.objects[n]
    out[n] = {'parent': o.parent.name if o.parent else None, 'matrix_local': [list(r) for r in o.matrix_local],
              'matrix_world': [list(r) for r in o.matrix_world]}
    if o.type == 'MESH':
        vs = [v.co for v in o.data.vertices]
        out[n]['bbox'] = [[min(v[i] for v in vs) for i in range(3)], [max(v[i] for v in vs) for i in range(3)]]
    out[n].update({k: (list(v) if hasattr(v, '__len__') and not isinstance(v, str) else v) for k, v in o.items()})
me = body.data
vs = [v.co for v in me.vertices]
out['Bike']['bbox'] = [[min(v[i] for v in vs) for i in range(3)], [max(v[i] for v in vs) for i in range(3)]]
for n in ('WheelFront', 'WheelRear'):
    vs = [v.co for v in bpy.data.objects[n].data.vertices]
    out[n]['bbox'] = [[min(v[i] for v in vs) for i in range(3)], [max(v[i] for v in vs) for i in range(3)]]
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bike1-anchors.json')
json.dump(out, open(p, 'w'), indent=1, default=str)
print('WROTE', p)
