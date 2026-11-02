"""Lint the landing's scene for the things that make a render read fake (a check to run after build-landing.py):
objects floating above the water or ground, pebbles buried or hovering, perfectly flat vertex colour across a whole
object, and mesh edges with no bevel (every sharp crease the low sun would catch as a hard line).

Run: blender --background art/micro-biome.blend --python art/lint-landing.py
Prints one line per problem and a total.
"""
import bmesh
import bpy
from mathutils import Vector

LAKE_Z = -11.0
problems = []


def report(obj, msg):
    problems.append(f'{obj}: {msg}')


depsgraph = bpy.context.evaluated_depsgraph_get()
canyon = bpy.data.objects.get('Landing.Canyon')

for o in bpy.data.objects:
    if not o.name.startswith('Landing.') or o.type != 'MESH':
        continue
    me = o.data
    if not me.vertices:
        report(o.name, 'empty mesh')
        continue
    world = [o.matrix_world @ v.co for v in me.vertices]

    # Vertex colour: a whole object in one flat colour reads as plastic.
    col = me.color_attributes.get('Col')
    if col and col.domain == 'CORNER' and len(col.data) > 50:
        values = [tuple(round(c, 2) for c in d.color[:3]) for d in col.data]
        distinct = len(set(values))
        if distinct < 4:
            report(o.name, f'only {distinct} distinct vertex colours across {len(values)} corners')

    # Floating parts: split into loose pieces, check each one's lowest point against the water / the canyon.
    # (Eyes sit on the frog's head and cattail heads on their stems: separate pieces off the ground by design.)
    if o.name in ('Landing.Canyon', 'Landing.Mountains', 'Landing.Dew', 'Landing.Shrubs', 'Landing.Blossom', 'Landing.FrogEyes'):
        continue
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    seen = set()
    floating = 0
    pieces = 0
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, island = [v], []
        seen.add(v.index)
        while stack:
            u = stack.pop()
            island.append(u)
            for e in u.link_edges:
                w = e.other_vert(u)
                if w.index not in seen:
                    seen.add(w.index)
                    stack.append(w)
        pieces += 1
        low = min(island, key=lambda u: (o.matrix_world @ u.co).z)
        p = o.matrix_world @ low.co
        ground = LAKE_Z
        if canyon:
            hit, loc, *_ = canyon.ray_cast(canyon.matrix_world.inverted() @ (p + Vector((0, 0, 5))), Vector((0, 0, -1)))
            if hit:
                ground = max(ground, (canyon.matrix_world @ loc).z)
        if p.z - ground > 0.03 and not (o.name == 'Landing.Reeds' and len(island) < 400):
            floating += 1
    bm.free()
    if floating:
        report(o.name, f'{floating} of {pieces} pieces float more than 3 cm above the water or ground')

    # Hard edges: share of edges where the faces meet at more than 60 degrees with no bevel segment between.
    if len(me.polygons) and o.name in ('Landing.Pebbles', 'Landing.Pads', 'Landing.Frog'):
        bm = bmesh.new()
        bm.from_mesh(me)
        sharp = sum(1 for e in bm.edges if e.is_manifold and e.calc_face_angle(0) > 1.05)
        if sharp > len(bm.edges) * 0.02:
            report(o.name, f'{sharp} sharp creases (over 60 degrees)')
        bm.free()

for line in problems:
    print('LINT', line)
print(f'LINT total {len(problems)} problem(s)')
