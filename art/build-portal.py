"""The hive's holes that are ridden through (components/three/portal.tsx, lib/portal.ts). Nothing new to look at: one of the
hive's towers (art/build-city3.py module_tower, module_spire, dirt) with one of its lancet windows and bone surround
(module_hexwindow, at the proportions a hive tower's have), only with no honeycomb in it. It's cut through, and black.
One stands across the road, its opening on the deck, the road running in and ending in the black. Its pair has the opening
high up, facing on down the road, a dark passage behind it.
Builds nothing but public/models/portal.glb (Draco, vertex-colour dirt).
Run: /opt/homebrew/bin/blender --background --factory-startup --python art/build-portal.py
     PORTAL_RENDERS=<dir> renders stills there; none without it.

Its frame (Blender z up, metres): the road runs along +X through the tower's axis, deck top z 0, 11.8 m wide. The rider
comes from -X. lib/portal.ts ENTRY_BLACK is where the black stands (x BLACK_X); it comes out of the pair at EXIT_FROM.
Nodes: PortalEntryBone, -Surround, -Jamb, -Black; PortalExit the same.
"""
import math
import os

import bmesh
import bpy
from mathutils import Vector

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
GLB = os.path.join(ROOT_DIR, 'public', 'models', 'portal.glb')
RENDERS = os.environ.get('PORTAL_RENDERS')

R = 19.0           # the tower's radius, top height (a hive tower's: art/build-city3.py hive_tower)
TOP = 110.0
BASE = -60.0       # the floor of the mist
ENTRY_W = 15.5     # the opening, as module_hexwindow's 1 by 1.7: wide enough for the road and its surround
EXIT_W = 10.0
EXIT_SILL = 12.0
BLACK_X = -13.0    # how far in the black stands
PASSAGE_X = 3.0    # how far back the passage behind the high opening runs

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
root = bpy.data.objects.new('Portal', None)
scene.collection.objects.link(root)


def material(name, colour, roughness):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*colour, 1)
    p.inputs['Roughness'].default_value = roughness
    return m


BONE = material('PortalBone', (0.90, 0.80, 0.64), 0.66)
BLACK = material('PortalBlack', (0.0, 0.0, 0.0), 1.0)

# --- As art/build-city3.py -------------------------------------------------------------------------------------------
TOWER_PROF = [(0.75, 0.0), (0.95, 0.12), (1.0, 0.3), (0.82, 0.45), (0.92, 0.58), (0.8, 0.72), (0.62, 0.84),
              (0.42, 0.93), (0.18, 0.985), (0.0, 1.0)]
SPIRE_PROF = [(1.0, 0.0), (0.72, 0.18), (0.78, 0.26), (0.5, 0.42), (0.6, 0.48), (0.36, 0.6), (0.4, 0.68), (0.2, 0.78),
              (0.06, 0.95), (0.0, 1.0)]
GRIME = (0.40, 0.27, 0.19)


def lancet_inside(x, z, w, h):
    spring = h - w * 0.95
    if z < spring:
        return abs(x) <= w / 2
    r = w * 0.95
    return math.hypot(abs(x) - (w / 2 - r), z - spring) <= r and z <= h


def half_width(z, w=1.0, h=1.7):
    xs = [x for x in [w / 2 * t / 40 for t in range(41)] if lancet_inside(x, z, w, h)]
    return max(xs) if xs else 0.0


def lathe(bm, profile, seg, sx, sz, z0, wob=None):
    """Spun about z, closed at both ends. profile: (radius, height), both as shares, scaled by sx and sz."""
    rings = []
    for r, z in profile:
        ring = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            rr = r * (wob(a, z) if wob else 1.0) * sx
            ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z0 + z * sz)))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(list(reversed(rings[0])))
    bmesh.ops.remove_doubles(bm, verts=rings[-1], dist=1e-4)


def dirt_colour(co, normal, neighbours, h):
    """art/build-city3.py dirt, for one of its shared modules: in the module's own units (radius 1, height 1)."""
    cav = sum((q - co).dot(normal) / max((q - co).length, 1e-6) for q in neighbours) / len(neighbours) if neighbours else 0.0
    c = 1.0 - 1.5 * max(0.0, cav)
    c *= 1 - 0.55 * max(0.0, 1 - h * 3) ** 1.5
    a = math.atan2(co.y, co.x)
    streak = max(0.0, math.sin(a * 7 + co.x * 0.9) * math.sin(a * 3 - co.y * 0.7))
    c *= 1 - 0.28 * streak * (1 - 0.6 * h)
    g = 0.93 + 0.07 * math.sin(co.x * 3.1 + co.y * 1.7) * math.sin(co.z * 2.3)
    v = max(0.18, min(1.0, c * g))
    return v * v


def to_object(name, bm, mat, parent, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = smooth
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    o.parent = parent
    return o


def paint(o, shade, fades=False):
    """Vertex colours into three's COLOR_0: shade(vertex) -> 0 to 1, grimed as the city's (or, fades, on down to black)."""
    me = o.data
    me.color_attributes.new('Col', 'BYTE_COLOR', 'POINT')
    me.color_attributes.active_color = me.color_attributes['Col']
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    vals = [shade(v) for v in bm.verts]
    bm.free()
    for d, v in zip(me.color_attributes['Col'].data, vals):
        d.color = (*[(GRIME[i] + (1 - GRIME[i]) * v) * (v if fades else 1) for i in range(3)], 1)


def shade_module(v):
    unit = Vector((v.co.x / R, v.co.y / R, (v.co.z - BASE) / (TOP - BASE)))
    nb = [Vector((q.x / R, q.y / R, (q.z - BASE) / (TOP - BASE))) for q in (e.other_vert(v).co for e in v.link_edges)]
    return dirt_colour(unit, v.normal, nb, min(1.0, unit.z))


def outline(w, h, sill, closed):
    """The opening's edge, (across, up), from one foot over the point to the other."""
    n = 11
    side = [(half_width(h * k / (n - 1), w, h), sill + h * k / (n - 1)) for k in range(n)]
    pts = side + [(-x, z) for x, z in reversed(side)][1:]
    if not closed:
        # (Down past the deck, so there's nothing to see through under the road.)
        pts = [(pts[0][0], sill - 3.0)] + pts + [(pts[-1][0], sill - 3.0)]
    return pts


def inside(y, z, pts):
    """Whether (y, z) is within the outline's polygon."""
    hit = False
    for (y0, z0), (y1, z1) in zip(pts, pts[1:] + pts[:1]):
        if (z0 > z) != (z1 > z) and y < y0 + (z - z0) / (z1 - z0) * (y1 - y0):
            hit = not hit
    return hit


def tower(name, parent, w, h, sill, closed, facing):
    """The body and spire, cut through toward `facing` (-1 toward the rider, 1 on down the road)."""
    bm = bmesh.new()
    lathe(bm, TOWER_PROF, 12, R, TOP - BASE, BASE, wob=lambda a, z: 1 + 0.07 * math.sin(3 * a + 6 * z))
    me = bpy.data.meshes.new('body')
    bm.to_mesh(me)
    bm.free()
    body = bpy.data.objects.new('body', me)
    scene.collection.objects.link(body)

    pts = outline(w, h, sill, closed)
    bm = bmesh.new()
    a = [bm.verts.new((0.0, y, z)) for y, z in pts]
    b = [bm.verts.new((facing * 60.0, y, z)) for y, z in pts]
    n = len(pts)
    for k in range(n):
        j = (k + 1) % n
        bm.faces.new((a[k], a[j], b[j], b[k]))
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    cm = bpy.data.meshes.new('cutter')
    bm.to_mesh(cm)
    bm.free()
    cutter = bpy.data.objects.new('cutter', cm)
    scene.collection.objects.link(cutter)
    mod = body.modifiers.new('cut', 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cutter
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)

    bm = bmesh.new()
    bm.from_mesh(me)
    # The cut's own walls go (the jamb's its own mesh): left on, their edges would smooth the tower's face.
    grown = [(y * 1.01, sill + (z - sill) * 1.01 if z > sill else z - 0.05) for y, z in pts]
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if all(inside(v.co.y, v.co.z, grown) for v in f.verts)], context='FACES')
    bpy.data.objects.remove(body, do_unlink=True)

    # module_spire, on top, as hive_tower puts it.
    lathe(bm, SPIRE_PROF, 8, R * 0.45, TOP * 0.6, TOP - (TOP - BASE) * 0.05, wob=lambda a, z: 1 + 0.12 * math.sin(4 * a) * (1 - z))
    o = to_object(name, bm, BONE, parent)
    paint(o, shade_module)
    return o


def surround(bm, w, h, sill, front, facing):
    """module_hexwindow's bone surround: a thick rim, flat-shaded, four-sided, on the same nine points each side."""
    nk = 9
    side = [(half_width(h * k / (nk - 1), w, h), sill + h * k / (nk - 1)) for k in range(nk)]
    pts = side + [(-x, z) for x, z in reversed(side)][1:]
    path = [Vector((front + facing * 0.03 * w, y, z)) for y, z in pts]
    r = 0.096 * w
    rings = []
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        out = Vector((facing, 0, 0))
        side_ = t.cross(out).normalized()
        rings.append([bm.verts.new(p + (side_ * math.cos(math.pi / 2 * k + math.pi / 4) + out * math.sin(math.pi / 2 * k + math.pi / 4)) * r) for k in range(4)])
    for ra, rb in zip(rings, rings[1:]):
        for k in range(4):
            j = (k + 1) % 4
            bm.faces.new((ra[k], ra[j], rb[j], rb[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])


def jamb(bm, pts, front, back):
    """The opening's depth, from its face back to the black."""
    n = len(pts)
    steps = 5
    # (A hair inside the cut, clear of what's left of the tower's surface there.)
    low = min(z for y, z in pts)
    rings = [[bm.verts.new((front + (back - front) * s / steps, y * 0.99, z + 0.08 if z - low < 1e-3 else z - 0.03)) for y, z in pts] for s in range(steps + 1)]
    for ra, rb in zip(rings, rings[1:]):
        for k in range(n):
            j = (k + 1) % n
            bm.faces.new((ra[k], ra[j], rb[j], rb[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)


def plate(pts, x, facing, name, parent):
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z)) for y, z in pts]
    f = bm.faces.new(vs)
    bm.normal_update()
    if f.normal.x * facing < 0:
        bmesh.ops.reverse_faces(bm, faces=[f])
    bmesh.ops.triangulate(bm, faces=[f])
    return to_object(name, bm, BLACK, parent, smooth=False)


def front_of(w, h, sill):
    """Where the opening's face stands: as the city's windows, a hair proud of the tower's widest at that height."""
    f0 = (sill - BASE) / (TOP - BASE)
    f1 = (sill + h - BASE) / (TOP - BASE)
    best = 0.0
    for k in range(9):
        f = f0 + (f1 - f0) * k / 8
        for (r0, z0), (r1, z1) in zip(TOWER_PROF, TOWER_PROF[1:]):
            if z0 <= f <= z1:
                best = max(best, r0 + (r1 - r0) * (f - z0) / (z1 - z0))
    return R * best * 1.07 + 0.15


# --- Ridden into -----------------------------------------------------------------------------------------------------
entry = bpy.data.objects.new('PortalEntry', None)
scene.collection.objects.link(entry)
entry.parent = root
h_in = ENTRY_W * 1.7
tower('PortalEntryBone', entry, ENTRY_W, h_in, 0.0, False, -1)
front_in = -front_of(ENTRY_W, h_in, 0.0)
pts_in = outline(ENTRY_W, h_in, 0.0, False)
bm = bmesh.new()
surround(bm, ENTRY_W, h_in, 0.0, front_in, -1)
o_rim = to_object('PortalEntrySurround', bm, BONE, entry, smooth=False)
paint(o_rim, lambda v: dirt_colour(Vector((v.co.y / ENTRY_W, 0, v.co.z / ENTRY_W)), v.normal, [], (v.co.z / h_in)))
bm = bmesh.new()
jamb(bm, pts_in, front_in, BLACK_X)
o_jamb = to_object('PortalEntryJamb', bm, BONE, entry, smooth=False)
paint(o_jamb, lambda v: 0.75 * (1 - (v.co.x - front_in) / (BLACK_X - front_in)) ** 1.5, fades=True)
plate(pts_in, BLACK_X, -1, 'PortalEntryBlack', entry)

# --- Fallen out of ---------------------------------------------------------------------------------------------------
outlet = bpy.data.objects.new('PortalExit', None)
scene.collection.objects.link(outlet)
outlet.parent = root
h_out = EXIT_W * 1.7
tower('PortalExitBone', outlet, EXIT_W, h_out, EXIT_SILL, True, 1)
front_out = front_of(EXIT_W, h_out, EXIT_SILL)
pts_out = outline(EXIT_W, h_out, EXIT_SILL, True)
bm = bmesh.new()
surround(bm, EXIT_W, h_out, EXIT_SILL, front_out, 1)
x_rim = to_object('PortalExitSurround', bm, BONE, outlet, smooth=False)
paint(x_rim, lambda v: 0.6)
bm = bmesh.new()
jamb(bm, pts_out, front_out, PASSAGE_X)
x_jamb = to_object('PortalExitJamb', bm, BONE, outlet, smooth=False)
paint(x_jamb, lambda v: 0.75 * (1 - (v.co.x - front_out) / (PASSAGE_X - front_out)) ** 2, fades=True)
plate(pts_out, PASSAGE_X, 1, 'PortalExitBlack', outlet)

for o in root.children_recursive:
    if o.type == 'MESH':
        print(o.name, len(o.data.polygons), 'polys')
print('faces: entry', round(front_in, 2), 'exit', round(front_out, 2))

# --- Export ----------------------------------------------------------------------------------------------------------
for o in bpy.context.view_layer.objects:
    o.select_set(False)
for o in root.children_recursive:
    o.select_set(True)
root.select_set(True)
bpy.ops.export_scene.gltf(filepath=GLB, export_format='GLB', use_selection=True, export_apply=True,
                          export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
                          export_draco_position_quantization=14, export_draco_normal_quantization=8,
                          export_draco_color_quantization=8,
                          export_vertex_color='ACTIVE', export_texcoords=False,
                          export_yup=True, export_cameras=False, export_lights=False, export_extras=False)
print('exported', GLB, os.path.getsize(GLB))

# --- Stills ----------------------------------------------------------------------------------------------------------
if RENDERS:
    os.makedirs(RENDERS, exist_ok=True)
    bm = bmesh.new()
    for x0, x1 in ((-800.0, 800.0),):
        vs = [bm.verts.new((x0, -5.9, 0)), bm.verts.new((x1, -5.9, 0)), bm.verts.new((x1, 5.9, 0)), bm.verts.new((x0, 5.9, 0))]
        bm.faces.new(vs)
    to_object('StillRoad', bm, material('StillStone', (0.6, 0.45, 0.42), 0.3), root)
    nt_mats = (BONE,)
    for m_ in nt_mats:
        nt = m_.node_tree
        p_ = nt.nodes['Principled BSDF']
        at_ = nt.nodes.new('ShaderNodeVertexColor')
        at_.layer_name = 'Col'
        nt.links.new(at_.outputs['Color'], p_.inputs['Base Color'])
    world = bpy.data.worlds.new('Dawn')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.8, 0.45, 0.4, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.9
    scene.world = world
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    scene.collection.objects.link(sun)
    sun.data.energy = 4.0
    sun.data.color = (1.0, 0.78, 0.6)
    sun.rotation_euler = Vector((-0.8, 0.45, 0.4)).to_track_quat('-Z', 'Y').to_euler()
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.taa_render_samples = 32
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.view_settings.view_transform = 'Standard'
    cam.data.sensor_fit = 'VERTICAL'
    cam.data.angle = math.radians(70)
    cam.data.clip_end = 3000
    ins = list(entry.children)
    outs = list(outlet.children)

    def still(name, eye, look, show_exit=False):
        for o in ins:
            o.hide_render = show_exit
        for o in outs:
            o.hide_render = not show_exit
        cam.location = eye
        cam.rotation_euler = (Vector(look) - Vector(eye)).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(RENDERS, f'hole-{name}.png')
        bpy.ops.render.render(write_still=True)

    still('approach', (-150, 0, 1.5), (0, 0, 22))
    still('near', (-52, 0, 1.5), (0, 0, 10))
    still('out', (6, 0, 16.5), (40, 0, 8), show_exit=True)
