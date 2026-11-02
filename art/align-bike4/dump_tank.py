"""Sample bike.glb's tank surface around its ButtonCentre (excluding the button meshes) so bike4's tank can be conformed
to it, and so the slingshot track's profile can be checked. Heights are along ButtonCentre's normal (its local +Z),
relative to it; d is metres back along the bike (-X), s sideways (+Y).
Run: blender --background --factory-startup art/bike.blend --python art/align-bike4/dump_tank.py
Writes art/align-bike4/bike1-tank.json"""
import json
import os

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

body = bpy.data.objects['Bike']
dg = bpy.context.evaluated_depsgraph_get()
ev = body.evaluated_get(dg)
me = ev.to_mesh()
tree = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])  # bike-local
C = bpy.data.objects['ButtonCentre'].matrix_local
o, X, Yv, Z = C.translation, C.col[0].xyz.normalized(), C.col[1].xyz.normalized(), C.col[2].xyz.normalized()


def height(d, s):
    p = o + X * (-d) + Yv * s + Z * 0.3
    h = tree.ray_cast(p, -Z)
    return None if h[0] is None else round((h[0] - o).dot(Z), 5)


D = [round(-0.22 + 0.01 * i, 3) for i in range(55)]
S = [round(-0.12 + 0.01 * i, 3) for i in range(25)]
grid = [[height(d, s) for s in S] for d in D]
TD = [-0.16, -0.12, -0.08, -0.04, 0, 0.04, 0.08, 0.12, 0.16, 0.2, 0.24]
out = {'_': __doc__, 'd': D, 's': S, 'h': grid, 'TRACK_D': TD,
       'TRACK_CENTRE': [height(d, 0) for d in TD],
       'TRACK_SIDE': [round((height(d, 0.066) + height(d, -0.066)) / 2, 5) for d in TD]}
# the bars: the chrome's widest points up high
vs = [v.co for v in me.vertices if v.co.z > 0.8]
far = sorted(vs, key=lambda v: -abs(v.y))[:6]
out['bar_ends'] = [[round(c, 3) for c in v] for v in far]
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bike1-tank.json')
json.dump(out, open(p, 'w'))
print('TRACK_CENTRE', out['TRACK_CENTRE'])
print('TRACK_SIDE', out['TRACK_SIDE'])
print('BARS', out['bar_ends'])
