"""Chip the planter rim, cut three spill gaps, and build the waterfalls and the pool basin they land in.
Re-runnable: it rebuilds the cutters, falls and basin each time; the planter keeps its modifier stack.
Run inside Blender with art/micro-biome.blend open:  exec(open('<repo>/art/build-spill.py').read())"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

scene = bpy.context.scene
root = bpy.data.objects['MicroBiome']
planter = bpy.data.objects['Planter']

WATER_Z = 0.522  # surface of the water in the planter
WATER_HALF = 0.43  # the surface runs just into the inner walls (at 0.422) so no wall shows below the waterline
POOL_Z = -11.0  # surface of the pool the falls land in
# The falls join into one without a twist: below the lip each stream eases sideways into its own slot along a single
# line across the view (a comb, not a funnel), flattening out wide as it goes, until neighbours overlap into one
# curtain by JOIN_Z. The big fall begins there as a flat curtain of the same width, and the two crossfade while
# they're aligned, so there's no join to see.
JOIN_TOP, JOIN_Z = -0.7, -3.6
MAIN_TOP = -3.2
CURTAIN_TOP_HALF, CURTAIN_BOTTOM_HALF = 1.7, 2.9  # the curtain's half-width across the view (y) at its top and foot
STREAMS_FADE = (-3.4, -4.6)  # streams go from opaque to gone between these heights
MAIN_FADE = (-3.2, -4.3)  # the big fall goes from gone to opaque
# (name, outward face normal, position along the face, half-width, gap floor z). A and B face the hero camera; C is
# on the back and turns up while the camera circles.
GAPS = [
    ('A', Vector((0, -1, 0)), 0.17, 0.12, 0.497),
    ('B', Vector((-1, 0, 0)), -0.14, 0.095, 0.502),
    ('C', Vector((1, 0, 0)), -0.24, 0.085, 0.505),
]
# Smaller trickles between them: narrower, shallower gaps (cut after the rim chips, from their own random stream, so
# adding them left the rim as it was).
SMALL_GAPS = [
    ('D', Vector((0, -1, 0)), -0.22, 0.055, 0.508),
    ('E', Vector((-1, 0, 0)), 0.27, 0.045, 0.51),
    ('F', Vector((0, 1, 0)), 0.1, 0.06, 0.507),
    ('G', Vector((0, 1, 0)), -0.27, 0.045, 0.51),
    ('H', Vector((1, 0, 0)), 0.2, 0.05, 0.509),
]
ALL_GAPS = GAPS + SMALL_GAPS


def trickle(hw):
    """1 for the three main gaps; less for the small ones (thinner shoulders, columns, and a closer fall)."""
    return 1.0 if hw >= 0.08 else hw / 0.09


def along_axis(n):
    return Vector((-n.y, n.x, 0))


def gap_centre(n, along):
    return n * 0.46 + along_axis(n) * along


def fresh_object(name, me, collection=None):
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old)
    o = bpy.data.objects.new(name, me)
    (collection or scene.collection).objects.link(o)
    return o


# --- Planter cuts -----------------------------------------------------------------------------------------------------

cutters = bpy.data.collections.get('Cutters') or bpy.data.collections.new('Cutters')
if cutters.name not in scene.collection.children:
    scene.collection.children.link(cutters)
for o in list(cutters.objects):
    bpy.data.objects.remove(o)


def cutter(name, bm, matrix=Matrix()):
    bmesh.ops.transform(bm, matrix=matrix, verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = fresh_object(name, me, cutters)
    o.display_type = 'WIRE'
    o.hide_render = True
    return o


def cone(name, centre, axis, r, length, tilt=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=40, radius1=r, radius2=r * 1.25, depth=length)
    rot = Vector((0, 0, 1)).rotation_difference(axis).to_matrix().to_4x4()
    return cutter(name, bm, Matrix.Translation(centre) @ Matrix.Rotation(tilt, 4, axis) @ rot)


def box(name, centre, size, rot=Matrix()):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    return cutter(name, bm, Matrix.Translation(centre) @ rot)


def ball(name, centre, r, squash=(1, 1, 1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=28, v_segments=14, radius=r)
    bmesh.ops.scale(bm, vec=squash, verts=bm.verts)
    return cutter(name, bm, Matrix.Translation(centre))


def cut_gap(name, n, along, hw, zb, rnd):
    t = along_axis(n)
    c = gap_centre(n, along)
    small = trickle(hw)
    # Uneven U: the round bottom flares outward (worn wider on the outside) with a slight tilt.
    cone(f'Cut.{name}.Round', Vector((c.x, c.y, zb + hw)), n, hw, 0.36, tilt=rnd.uniform(-0.25, 0.25))
    slot_size = (abs(n.x) * 0.4 + abs(t.x) * 2 * hw, abs(n.y) * 0.4 + abs(t.y) * 2 * hw, 0.5)
    box(f'Cut.{name}.Slot', Vector((c.x, c.y, zb + hw + 0.25)), slot_size, Matrix.Rotation(rnd.uniform(-0.08, 0.08), 4, n))
    # Broken shoulders, one bigger than the other.
    for side, r in ((-1, rnd.uniform(0.045, 0.07) * small), (1, rnd.uniform(0.03, 0.05) * small)):
        ball(f'Cut.{name}.Chip{side}', Vector((c.x, c.y, 0.62)) + t * side * (hw + r * 0.45) + n * 0.03, r, (1, 1, rnd.uniform(0.8, 1.2)))
    # Water-worn scoop on the outer lip where it pours over.
    ball(f'Cut.{name}.Lip', Vector((c.x, c.y, zb + 0.005)) + n * 0.07, hw * 0.9, (1.3 if n.y else 0.6, 0.6 if n.y else 1.3, 0.55))


random.seed(11)
for gap in GAPS:
    cut_gap(*gap, random)


def near_gap(p):
    return any((p - gap_centre(n, along)).length < hw + 0.11 for _, n, along, hw, _ in ALL_GAPS)


# Irregular rim: shallow chips along the top, clear of the gaps.
for i in range(40):
    side = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
    s = random.uniform(-0.44, 0.44)
    p = Vector((side[0] * 0.46 + (s if side[0] == 0 else 0), side[1] * 0.46 + (s if side[1] == 0 else 0), 0))
    r = random.uniform(0.025, 0.06)
    out = random.uniform(0.0, 0.05)
    lift = random.uniform(0.25, 0.7)
    if near_gap(p):
        continue
    ball(f'Cut.Rim.{i}', Vector((p.x + side[0] * out, p.y + side[1] * out, 0.62 + r * lift)), r, (1.8 if side[1] else 1, 1.8 if side[0] else 1, 1))

small_rnd = random.Random(29)
for gap in SMALL_GAPS:
    cut_gap(*gap, small_rnd)

# Bevelled box -> boolean the cutters -> voxel remesh + smooth, so every cut reads as soft clay.
if 'Cuts' not in planter.modifiers:
    cuts = planter.modifiers.new('Cuts', 'BOOLEAN')
    cuts.operation = 'DIFFERENCE'
    cuts.operand_type = 'COLLECTION'
    cuts.solver = 'EXACT'
    remesh = planter.modifiers.new('Remesh', 'REMESH')
    remesh.mode = 'VOXEL'
    remesh.voxel_size = 0.006
    remesh.use_smooth_shade = True
    soften = planter.modifiers.new('Soften', 'CORRECTIVE_SMOOTH')
    soften.factor = 0.5
    soften.iterations = 6
    soften.smooth_type = 'SIMPLE'
    soften.use_only_smooth = True
planter.modifiers['Cuts'].collection = cutters

# Box water: widen the surface to the walls (it was 0.792 across, leaving a strip of wall visible under the waterline).
box_water = bpy.data.objects['Water'].data
half = max(abs(v.co.x) for v in box_water.vertices)
for v in box_water.vertices:
    v.co.x *= WATER_HALF / half
    v.co.y *= WATER_HALF / half

# --- Waterfalls -------------------------------------------------------------------------------------------------------


def water_materials():
    """Stylised water that ports straight to a web shader: a deep blue core paling to the edges (facing ratio), glossy,
    slightly see-through, with lengthwise ridges in the normals. The falls mix in broken white water from their 'foam'
    attribute (the lip and the splash) and thin streaks running down them. One look for planter, falls and pool."""

    def setup(mat, cull=True):
        mat.use_nodes = True
        mat.surface_render_method = 'BLENDED'
        mat.use_backface_culling = cull
        mat.node_tree.nodes.clear()
        return mat.node_tree

    def glossy(nt, alpha):
        bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.inputs['Roughness'].default_value = 0.04
        bsdf.inputs['Coat Weight'].default_value = 1.0
        bsdf.inputs['Coat Roughness'].default_value = 0.02
        bsdf.inputs['Specular IOR Level'].default_value = 0.7
        bsdf.inputs['Alpha'].default_value = alpha
        return bsdf

    def edge_ramp(nt, stops, blend):
        facing = nt.nodes.new('ShaderNodeLayerWeight')
        facing.inputs['Blend'].default_value = blend
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = stops[0][0], (*stops[0][1], 1)
        ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = stops[-1][0], (*stops[-1][1], 1)
        for pos, rgb in stops[1:-1]:
            ramp.color_ramp.elements.new(pos).color = (*rgb, 1)
        nt.links.new(facing.outputs['Facing'], ramp.inputs['Fac'])
        return ramp

    def noise(nt, scale, uv_stretch=None, detail=2.0):
        tex = nt.nodes.new('ShaderNodeTexNoise')
        tex.inputs['Scale'].default_value = scale
        tex.inputs['Detail'].default_value = detail
        if uv_stretch:
            uv = nt.nodes.new('ShaderNodeUVMap')
            mapping = nt.nodes.new('ShaderNodeMapping')
            mapping.inputs['Scale'].default_value = uv_stretch
            nt.links.new(uv.outputs['UV'], mapping.inputs['Vector'])
            nt.links.new(mapping.outputs['Vector'], tex.inputs['Vector'])
        return tex

    def bump(nt, tex, strength, bsdf):
        node = nt.nodes.new('ShaderNodeBump')
        node.inputs['Strength'].default_value = strength
        nt.links.new(tex.outputs['Fac'], node.inputs['Height'])
        nt.links.new(node.outputs['Normal'], bsdf.inputs['Normal'])
        nt.links.new(node.outputs['Normal'], bsdf.inputs['Coat Normal'])

    deep, mid, pale = (0.02, 0.22, 0.8), (0.1, 0.45, 1.0), (0.72, 0.9, 1.0)

    # Still water: planter and pool.
    still = bpy.data.materials['Water']
    nt = setup(still)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = glossy(nt, 0.95)
    ramp = edge_ramp(nt, [(0.0, deep), (0.9, mid), (1.0, pale)], 0.15)
    nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bump(nt, noise(nt, 9.0), 0.15, bsdf)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    # Falling water. In the channel ('flow' 0) it matches the still water exactly; ridges, streaks and the paler
    # falling-water edges come in with 'flow'.
    falling = bpy.data.materials.get('Waterfall') or bpy.data.materials.new('Waterfall')
    nt = setup(falling)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = glossy(nt, 0.9)
    flow = nt.nodes.new('ShaderNodeAttribute')
    flow.attribute_name = 'flow'
    still_ramp = edge_ramp(nt, [(0.0, deep), (0.9, mid), (1.0, pale)], 0.15)
    fall_ramp = edge_ramp(nt, [(0.0, deep), (0.55, mid), (1.0, pale)], 0.3)
    blend = nt.nodes.new('ShaderNodeMix')
    blend.data_type = 'RGBA'
    nt.links.new(flow.outputs['Fac'], blend.inputs['Factor'])
    nt.links.new(still_ramp.outputs['Color'], blend.inputs['A'])
    nt.links.new(fall_ramp.outputs['Color'], blend.inputs['B'])
    still_ripples = noise(nt, 9.0)
    ridges = noise(nt, 2.5, uv_stretch=(10, 0.7, 1))
    height = nt.nodes.new('ShaderNodeMix')
    height.data_type = 'FLOAT'
    nt.links.new(flow.outputs['Fac'], height.inputs['Factor'])
    nt.links.new(still_ripples.outputs['Fac'], height.inputs['A'])
    nt.links.new(ridges.outputs['Fac'], height.inputs['B'])
    strength = nt.nodes.new('ShaderNodeMapRange')
    strength.inputs['To Min'].default_value = 0.15
    strength.inputs['To Max'].default_value = 0.45
    nt.links.new(flow.outputs['Fac'], strength.inputs['Value'])
    bump_node = nt.nodes.new('ShaderNodeBump')
    nt.links.new(strength.outputs['Result'], bump_node.inputs['Strength'])
    nt.links.new(height.outputs['Result'], bump_node.inputs['Height'])
    nt.links.new(bump_node.outputs['Normal'], bsdf.inputs['Normal'])
    nt.links.new(bump_node.outputs['Normal'], bsdf.inputs['Coat Normal'])
    alpha = nt.nodes.new('ShaderNodeMapRange')
    alpha.inputs['To Min'].default_value = 0.95
    alpha.inputs['To Max'].default_value = 0.85
    nt.links.new(flow.outputs['Fac'], alpha.inputs['Value'])
    # 'fade' crossfades the streams into the big fall.
    fade = nt.nodes.new('ShaderNodeAttribute')
    fade.attribute_name = 'fade'
    faded = nt.nodes.new('ShaderNodeMath')
    faded.operation = 'MULTIPLY'
    nt.links.new(alpha.outputs['Result'], faded.inputs[0])
    nt.links.new(fade.outputs['Fac'], faded.inputs[1])
    nt.links.new(faded.outputs['Value'], bsdf.inputs['Alpha'])
    # White: the brightest ridges once falling, and the foam attribute broken up by finer noise.
    streak = nt.nodes.new('ShaderNodeMapRange')
    streak.inputs['From Min'].default_value = 0.58
    streak.inputs['From Max'].default_value = 0.72
    streak.inputs['To Max'].default_value = 0.6
    nt.links.new(ridges.outputs['Fac'], streak.inputs['Value'])
    streak_flow = nt.nodes.new('ShaderNodeMath')
    streak_flow.operation = 'MULTIPLY'
    nt.links.new(streak.outputs['Result'], streak_flow.inputs[0])
    nt.links.new(flow.outputs['Fac'], streak_flow.inputs[1])
    foam = nt.nodes.new('ShaderNodeAttribute')
    foam.attribute_name = 'foam'
    breakup = nt.nodes.new('ShaderNodeMapRange')
    breakup.inputs['From Min'].default_value = 0.4
    breakup.inputs['From Max'].default_value = 0.6
    nt.links.new(noise(nt, 6.0, uv_stretch=(8, 3, 1)).outputs['Fac'], breakup.inputs['Value'])
    broken = nt.nodes.new('ShaderNodeMath')
    broken.operation = 'MULTIPLY'
    nt.links.new(foam.outputs['Fac'], broken.inputs[0])
    nt.links.new(breakup.outputs['Result'], broken.inputs[1])
    white = nt.nodes.new('ShaderNodeMath')
    white.operation = 'MAXIMUM'
    nt.links.new(streak_flow.outputs['Value'], white.inputs[0])
    nt.links.new(broken.outputs['Value'], white.inputs[1])
    tint = nt.nodes.new('ShaderNodeMix')
    tint.data_type = 'RGBA'
    tint.inputs['B'].default_value = (0.95, 0.98, 1.0, 1)
    nt.links.new(white.outputs['Value'], tint.inputs['Factor'])
    nt.links.new(blend.outputs['Result'], tint.inputs['A'])
    nt.links.new(tint.outputs['Result'], bsdf.inputs['Base Color'])
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    # White water for the splash crowns.
    spray = bpy.data.materials.get('Foam') or bpy.data.materials.new('Foam')
    nt = setup(spray, cull=False)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = glossy(nt, 0.92)
    bsdf.inputs['Base Color'].default_value = (0.92, 0.97, 1.0, 1)
    bsdf.inputs['Roughness'].default_value = 0.25
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return falling, spray


def channel_radius(hw, d):
    """Radius of a gap's round bottom at distance d from the centre (the cutter cone flares from hw at 0.28 to 1.25 hw
    at 0.64), inset a little so the water stays clear of the softened clay."""
    return hw * (1 + 0.25 * (d - 0.28) / 0.36) * 0.92


def channel_section(hw, zb, d, h, ring):
    """Cross-section of the water in a gap at distance d, surface at height h: a flat top across the round-bottomed
    channel, as (across, height) pairs. Ordered like the falling ring: the top from +across to -across, then the
    bottom arc back round to +across."""
    r = channel_radius(hw, d)
    zc = zb + hw
    h = max(h, zc - r + 0.006)
    half = math.sqrt(max(r * r - (zc - h) ** 2, 1e-6))
    top = [(half - 2 * half * k / (ring // 2), h) for k in range(ring // 2)]
    left, right = math.atan2(h - zc, -half), math.atan2(h - zc, half)
    if left > 0:
        left -= 2 * math.pi
    arc = []
    for k in range(ring - ring // 2):
        theta = left + (right - left) * k / (ring - ring // 2)
        arc.append((r * math.cos(theta), zc + r * math.sin(theta)))
    return top + arc


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def waterfall(name, n, along, hw, zb, seed, material, ring=24):
    """One spill: water level with the box's water, running out through the gap's channel, curling over the lip, then a
    falling column down to the pool, rippled lengthwise. UV u runs around it, v is metres along it (for the scrolling
    flow on the web). Point attributes: 'flow' (0 in the still channel, 1 once falling; ridges and streaks follow it)
    and 'foam' (white water at the lip and the splash)."""
    t = along_axis(n)
    c = t * along
    rings, centres = [], []

    # Through the gap: starting where the box's water surface ends so the two see-through layers never stack, level
    # with it, then dropping toward the lip.
    start = WATER_HALF - 0.002
    channel = [start + (0.5 - start) * i / 14 for i in range(15)]
    lip_floor = zb + hw - channel_radius(hw, 0.5)
    for d in channel:
        h = WATER_Z - 0.0015 - (WATER_Z - 0.0015 - (lip_floor + 0.016)) * ease((d - 0.42) / 0.08)
        section = channel_section(hw, zb, d, h, ring)
        rings.append([c + n * d + t * x + Vector((0, 0, z)) for x, z in section])
        centres.append(c + n * d + Vector((0, 0, sum(z for _, z in section) / ring)))
    lip_section = [(x, z - centres[-1].z) for x, z in channel_section(hw, zb, 0.5, lip_floor + 0.016, ring)]
    lip = centres[-1]

    # Over the lip and down.
    k = 34.0 / trickle(hw)  # outward reach: x = sqrt(drop / k); trickles fall closer to the wall
    path = []
    x = 0.0
    while x < 0.06:
        x += 0.006
        path.append(c + n * (0.5 + x) + Vector((0, 0, lip.z - k * x * x)))
    z = path[-1].z
    # Then each stream eases into its slot on the curtain line (x = 0): spread out along y in the same order the gaps sit
    # round the planter, so no two cross. They start turning at slightly different heights.
    rnd = random.Random(seed)
    top = JOIN_TOP - rnd.uniform(0.0, 0.4)
    end_z = STREAMS_FADE[1] - 0.1
    lip_xy = (c + n * 0.5).xy
    slot = Vector((lip_xy.x * 0.12, lip_xy.y * 2.6 + lip_xy.x * 0.4))
    merging = [0.0] * len(path)
    while z > end_z:
        z = max(z - 0.04, end_z)
        drop = lip.z - z
        m = ease((top - z) / (top - JOIN_Z))
        wander = noise.noise(Vector((drop * 0.9, seed, 0))) * 0.05 * min(1, drop) * (1 - m)
        p = c + n * (0.5 + math.sqrt(drop / k)) + t * wander + Vector((0, 0, z))
        p.xy = p.xy.lerp(slot, m)
        path.append(p)
        merging.append(m)
    full = [*centres, *path]
    lengths = [0.0]
    for i in range(1, len(full)):
        lengths.append(lengths[-1] + (full[i] - full[i - 1]).length)
    total = lengths[-1]
    lip_length = lengths[len(centres) - 1]

    flow = [0.0] * len(centres)
    for i, p in enumerate(path, start=len(centres)):
        tangent = (full[min(i + 1, len(full) - 1)] - full[i - 1]).normalized()
        m = merging[i - len(centres)]
        # Turning to lie flat along the curtain line as it joins, facing across the lake.
        across = t.lerp(Vector((0, 1 if t.y >= 0 else -1, 0)), m)
        side = (across - tangent * across.dot(tangent)).normalized()
        up = tangent.cross(side).normalized()
        after = lengths[i] - lip_length
        f = after / (total - lip_length)
        width = hw * 0.8 * (1 + 0.45 * f) * (1 + 0.08 * noise.noise(Vector((lengths[i] * 1.5, seed, 1))))
        thick = (0.022 + 0.05 * min(1, f * 3)) * trickle(hw)
        # Spreading into a flat ribbon wide enough to overlap its neighbours by the join.
        width = lerp(width, 0.3, m)
        thick = lerp(thick, 0.035, m)
        # The channel's shape morphs into the falling column over the first 25 cm.
        morph = ease(after / 0.25)
        fl = ease(after / 0.3)
        ring_verts = []
        for j in range(ring):
            a = 2 * math.pi * j / ring
            ridge = 1 + 0.3 * fl * noise.noise(Vector((math.cos(a) * 1.6, math.sin(a) * 1.6, lengths[i] * 0.7 + seed)))
            ex, ez = math.cos(a) * width * (0.92 + 0.08 * ridge), math.sin(a) * thick * ridge
            sx, sz = lip_section[j]
            ring_verts.append(p + side * (sx + (ex - sx) * morph) + up * (sz + (ez - sz) * morph))
        rings.append(ring_verts)
        flow.append(fl)

    fade = [1.0 - ease((STREAMS_FADE[0] - p.z) / (STREAMS_FADE[0] - STREAMS_FADE[1])) for p in full]
    foam = []
    for i in range(len(full)):
        after = lengths[i] - lip_length
        # White water just past the lip, where it breaks over the curl, rather than a line on the edge itself.
        white = 0.75 * max(0.0, 1 - abs(after - 0.08) / 0.12)
        foam.append(min(1.0, white))

    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new('UVMap')
    verts = [[bm.verts.new(v) for v in r] for r in rings]
    for i in range(len(verts) - 1):
        for j in range(ring):
            quad = (verts[i][j], verts[i][(j + 1) % ring], verts[i + 1][(j + 1) % ring], verts[i + 1][j])
            face = bm.faces.new(quad)
            uvs = ((j / ring, lengths[i]), ((j + 1) / ring, lengths[i]), ((j + 1) / ring, lengths[i + 1]), (j / ring, lengths[i + 1]))
            for loop, uv in zip(face.loops, uvs, strict=True):
                loop[uv_layer].uv = uv
    bm.normal_update()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    for attr_name, values in (('flow', flow), ('foam', foam), ('fade', fade)):
        attr = me.attributes.new(attr_name, 'FLOAT', 'POINT')
        attr.data.foreach_set('value', [values[i // ring] for i in range(len(me.vertices))])
    me.materials.append(material)
    o = fresh_object(name, me)
    o.parent = root
    return o, full[-1]


def main_fall(name, material, ring=64):
    """The one big fall the streams join into: a flat curtain across the view, as wide as the streams' comb where they
    meet and widening a little toward the pool, a little deeper as it falls, rippled lengthwise."""
    bottom = POOL_Z - 0.15
    rings, lengths, foam, fade = [], [], [], []
    z = MAIN_TOP
    length = 0.0
    while True:
        u = (MAIN_TOP - z) / (MAIN_TOP - bottom)
        half_width = lerp(CURTAIN_TOP_HALF, CURTAIN_BOTTOM_HALF, ease(u))
        half_depth = lerp(0.12, 0.9, ease(min(1.0, u * 2)))
        centre = Vector((noise.noise(Vector((z * 0.6, 4.2, 0))) * 0.04, noise.noise(Vector((z * 0.6, 7.7, 0))) * 0.04, z))
        ring_verts = []
        for j in range(ring):
            a = 2 * math.pi * j / ring
            ridge = 1 + 0.06 * noise.noise(Vector((math.cos(a) * 2.2, math.sin(a) * 2.2, z * 0.7)))
            ring_verts.append(centre + Vector((math.cos(a) * half_depth, math.sin(a) * half_width, 0)) * ridge)
        rings.append(ring_verts)
        lengths.append(length)
        foam.append(max(0.0, 1 - (z - bottom) / 0.35))
        fade.append(ease((MAIN_FADE[0] - z) / (MAIN_FADE[0] - MAIN_FADE[1])))
        if z <= bottom:
            break
        z = max(z - 0.06, bottom)
        length += 0.06
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new('UVMap')
    verts = [[bm.verts.new(v) for v in r] for r in rings]
    for i in range(len(verts) - 1):
        for j in range(ring):
            face = bm.faces.new((verts[i][j], verts[i + 1][j], verts[i + 1][(j + 1) % ring], verts[i][(j + 1) % ring]))
            uvs = ((j / ring, lengths[i]), (j / ring, lengths[i + 1]), ((j + 1) / ring, lengths[i + 1]), ((j + 1) / ring, lengths[i]))
            for loop, uv in zip(face.loops, uvs, strict=True):
                loop[uv_layer].uv = uv
    bm.normal_update()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    for attr_name, values in (('flow', [1.0] * len(rings)), ('foam', foam), ('fade', fade)):
        attr = me.attributes.new(attr_name, 'FLOAT', 'POINT')
        attr.data.foreach_set('value', [values[i // ring] for i in range(len(me.vertices))])
    me.materials.append(material)
    o = fresh_object(name, me)
    o.parent = root
    return o


def lerp(a, b, t):
    return a + (b - a) * t


def splash(name, at, seed, material, scale=1.0):
    """Where a fall lands: a crown of white-water beads and rings spreading on the pool."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    for k in range(22 if scale == 1 else 60):
        a = rnd.uniform(0, 2 * math.pi)
        r = rnd.uniform(0.08, 0.24) * scale
        size = rnd.uniform(0.03, 0.075) * (1 + 0.4 * (scale - 1))
        geom = bmesh.ops.create_icosphere(bm, subdivisions=1 if scale == 1 else 2, radius=size)
        bmesh.ops.translate(bm, vec=at + Vector((math.cos(a) * r, math.sin(a) * r, rnd.uniform(0.0, 0.12) * scale)), verts=geom['verts'])
    for radius in (0.26 * scale, 0.42 * scale, 0.6 * scale):
        geom = bmesh.ops.create_circle(bm, segments=64, radius=radius)
        ring_edges = [e for e in bm.edges if all(v in geom['verts'] for v in e.verts)]
        tube = bmesh.ops.extrude_edge_only(bm, edges=ring_edges)
        new = [v for v in tube['geom'] if isinstance(v, bmesh.types.BMVert)]
        bmesh.ops.scale(bm, vec=(1 + 0.03 / radius, 1 + 0.03 / radius, 1), verts=new)
        bmesh.ops.translate(bm, vec=at + Vector((0, 0, 0.004)), verts=geom['verts'] + new)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    me.materials.append(material)
    o = fresh_object(name, me)
    o.parent = root
    return o


water_fall, foam_material = water_materials()
for o in [o for o in bpy.data.objects if o.name.startswith('Splash.')]:
    bpy.data.objects.remove(o)
for i, (name, n, along, hw, zb) in enumerate(ALL_GAPS):
    waterfall(f'Fall.{name}', n, along, hw, zb, i * 7.3, water_fall)
main_fall('Fall.Main', water_fall)
splash('Splash', Vector((0, 0, POOL_Z)), 0, foam_material, scale=4.5)


# --- Pool --------------------------------------------------------------------------------------------------------------

# The pool the falls land in is now the macro biome's water (art/build-macro.py); the old clay basin is retired.
for name in ('Basin', 'Pool'):
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name])
if 'Basin.Hollow' in bpy.data.objects:
    bpy.data.objects.remove(bpy.data.objects['Basin.Hollow'])
