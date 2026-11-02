"""Sample bike.glb's tank surface around ButtonCentre (art/bike.blend, the button meshes excluded) so build-bike3.py can
match it: heights along ButtonCentre's normal on a grid in its frame (d back along -X, s sideways along +Y).
Run: blender --background --factory-startup art/bike.blend --python art/align-bike3/dump_tank.py
-> art/align-bike3/bike1-tank.json"""
import bpy, json, os
from mathutils import Vector
from mathutils.bvhtree import BVHTree
body = bpy.data.objects['Bike']
dg = bpy.context.evaluated_depsgraph_get()
print('Bike children', [c.name for c in body.children])
skip = {'BikeButton', 'BikeButtonGlyph'}
trees = []
for o in bpy.data.objects:
    if o.type == 'MESH' and o.name not in skip and (o == body or o.parent == body) and not o.name.startswith('Wheel'):
        # in bike-local space
        me = o.evaluated_get(dg).to_mesh()
        M = body.matrix_world.inverted() @ o.matrix_world
        verts = [M @ v.co for v in me.vertices]
        polys = [tuple(p.vertices) for p in me.polygons]
        trees.append((o.name, BVHTree.FromPolygons(verts, polys)))
        o.evaluated_get(dg).to_mesh_clear()
BC = bpy.data.objects['ButtonCentre'].matrix_local
o, X, Yv, N = BC.translation, BC.col[0].xyz.normalized(), BC.col[1].xyz.normalized(), BC.col[2].xyz.normalized()
ds = [round(-0.30 + 0.02 * i, 3) for i in range(33)]   # -0.30 .. +0.34 (positive = back, -X)
ss = [round(-0.12 + 0.012 * j, 3) for j in range(21)]  # -0.12 .. +0.12
grid = []
for d in ds:
    row = []
    for s in ss:
        p = o - X * d + Yv * s + N * 0.3
        best = None
        for name, t in trees:
            h = t.ray_cast(p, -N)
            if h[0] is not None and (best is None or h[3] < best[1]):
                best = (name, h[3])
        row.append(None if best is None else round(0.3 - best[1], 5))
    grid.append(row)
out = {'_': 'bike.glb tank height (m) along ButtonCentre normal, rows d (back, -X), cols s (+Y)', 'd': ds, 's': ss, 'h': grid,
       'centre': [r[len(ss) // 2] for r in grid]}
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bike1-tank.json'), 'w'))
for d, r in zip(ds, grid):
    print(d, r[len(ss)//2], r[len(ss)//2 - 5], r[len(ss)//2 + 5], r[0], r[-1])
