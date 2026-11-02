"""The landing: a pink rock canyon round a still lake, where the big fall comes down out of the sky in front of the cliffs.
Replaces the giant clay planter (art/build-macro.py): the clay biome stays a toy floating far above, and below it is
the real world. Re-runnable (rebuilds everything named Landing.*, and the lake as Pool).
Run inside Blender with art/micro-biome.blend open, after build-spill.py:
    exec(open('<repo>/art/build-landing.py').read())

World layout (Blender, z up): the falls land at the origin on the lake (z -11). The camera lands at eye level to the
west (-x), looking east at the fall; the cliffs wrap round the far side, tallest behind the fall and to the right
(south), lower to the left (north) with a gap toward the low sun and distant mountains.
"""
import math
import random

import bmesh
import bpy
from mathutils import Color, Vector, noise

scene = bpy.context.scene
root = bpy.data.objects['MicroBiome']
LAKE_Z = -11.0
LAKE_CENTRE = Vector((-5.0, 0.0))
rnd = random.Random(8)

# Clear the giant planter copy and its garden, and any earlier landing.
for name in [o.name for o in bpy.data.objects if o.name.startswith(('Macro.', 'Garden.', 'Landing.')) or o.name in ('Macro', 'Pool')]:
    if name in bpy.data.objects:
        o = bpy.data.objects[name]
        for c in list(o.children_recursive):
            bpy.data.objects.remove(c)
        bpy.data.objects.remove(o)


def link(name, me, parent=None):
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    o.parent = parent or root
    return o


def material(name, roughness=0.85):
    """Vertex-coloured, matte: the colour lives in the 'Col' attribute."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = roughness
    attr = nt.nodes.new('ShaderNodeVertexColor')
    attr.layer_name = 'Col'
    nt.links.new(attr.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# --- Canyon terrain ---------------------------------------------------------------------------------------------------


def shore_radius(theta):
    """Distance from the lake centre to the foot of the cliffs, by direction (theta 0 = east, behind the fall)."""
    # 7.6 behind the fall, opening out westward into a long lake the camera looks up from far down.
    base = 7.6 + 22 * ((1 - math.cos(theta)) * 0.5) ** 1.6
    base += 2.5 * max(0.0, math.sin(theta)) - 0.5 * max(0.0, -math.sin(theta))  # roomier to the north, tighter south
    base += 16 * math.exp(-(((theta - 1.1) / 0.35) ** 2))  # a wide bay toward the sun: the reference's open left side
    return base + noise.noise(Vector((math.cos(theta) * 2, math.sin(theta) * 2, 3.3))) * 0.9


def cliff_height(theta):
    """How high the cliffs rise above the lake, by direction. As the reference, seen from the landing: a tall wooded
    hill on the far left, a low saddle where the sun sets over distant mountains, then a tall spur of cliffs rising to
    the fall, and the highest walls behind it and to the right."""
    behind = math.exp(-((theta / (0.7 if theta < 0 else 0.45)) ** 2))  # falling away quickly to the north (left)
    south = math.exp(-(((theta + 1.2) / 0.9) ** 2))
    north = math.exp(-(((theta - 1.52) / 0.15) ** 2))
    spur = math.exp(-(((theta - 0.55) / 0.15) ** 2))
    gap = math.exp(-(((theta - 1.15) / 0.3) ** 2))  # the saddle toward the sun and the mountains
    h = 2.5 + 10.5 * behind + 8.5 * south + 8.0 * north + 7.0 * spur
    # Pinnacles along the skyline.
    h += max(0.0, noise.noise(Vector((math.cos(theta) * 6, math.sin(theta) * 6, 9.1)))) * 3.5 * (behind + south + north + spur)
    return h * (1 - 0.45 * gap)


def fbm(p, octaves=4):
    total, amp, freq = 0.0, 1.0, 1.0
    for _ in range(octaves):
        total += noise.noise(p * freq) * amp
        amp *= 0.5
        freq *= 2.1
    return total


def height(x, y):
    d = Vector((x, y)) - LAKE_CENTRE
    theta = math.atan2(d.y, d.x)
    beyond = d.length - shore_radius(theta)
    if beyond < 0:
        return LAKE_Z - 0.6 - 0.02 * min(-beyond, 10)  # lake bed
    rise = cliff_height(theta)
    # A steep wall in a few terraces, levelling into a rolling top.
    t = 1 - math.exp(-beyond / 0.9)
    h = rise * t
    step = 1.8
    terraced = math.floor(h / step) * step + step * smoothstep(0.55, 1.0, (h / step) % 1.0)
    h = 0.55 * h + 0.45 * terraced
    h += fbm(Vector((x * 0.08, y * 0.08, 1.7)), 3) * 1.4 * t + max(0.0, beyond - 4) * 0.08
    return LAKE_Z - 0.15 + h


SIZE, N = 84.0, 300
step = SIZE / N
bm = bmesh.new()
grid = []
for i in range(N + 1):
    row = []
    for j in range(N + 1):
        x = -SIZE / 2 + i * step - 2
        y = -SIZE / 2 + j * step
        row.append(bm.verts.new((x, y, height(x, y))))
    grid.append(row)
for i in range(N):
    for j in range(N):
        bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
bm.normal_update()
# Rock: push the steep faces in and out along their normals (heights alone can't make a craggy wall): tall vertical
# columns and fractures (noise stretched up the face), horizontal strata, and finer crags on top.
for v in bm.verts:
    steep = 1 - abs(v.normal.z)
    if steep > 0.2:
        p = v.co
        columns = noise.noise(Vector((p.x * 0.7, p.y * 0.7, p.z * 0.12))) * 1.1
        fractures = -abs(noise.noise(Vector((p.x * 1.6, p.y * 1.6, p.z * 0.25)))) * 0.7
        strata = noise.noise(Vector((p.x * 0.1, p.y * 0.1, p.z * 1.4))) * 0.35
        crags = fbm(p * 0.9, 3) * 0.3
        # Blocks: tall columns standing proud or set back by whole slabs (cells of a Voronoi pattern stretched up the
        # face, each pushed by its own amount), so the walls break into the reference's pillars with sharp edges.
        _, points = noise.voronoi(Vector((p.x * 0.42, p.y * 0.42, p.z * 0.13)))
        blocks = noise.noise(points[0] * 7.1) * 1.1
        v.co += v.normal * (columns * 0.6 + fractures + strata + crags + blocks) * smoothstep(0.2, 0.6, steep)
bm.normal_update()

# Colour: pink rock, peachy where the light catches the upper faces, darker in the cracks; green on ledges and tops;
# pale sand at the waterline.
col = bm.loops.layers.color.new('Col')
ROCK = Color((0.86, 0.55, 0.5))
ROCK_LIGHT = Color((0.97, 0.76, 0.63))
ROCK_DARK = Color((0.6, 0.36, 0.37))
GRASS = Color((0.36, 0.52, 0.26))
GRASS_DARK = Color((0.22, 0.38, 0.2))
SAND = Color((0.92, 0.8, 0.68))


def mix(a, b, t):
    return Color((a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t))


for f in bm.faces:
    for loop in f.loops:
        v = loop.vert
        above = v.co.z - LAKE_Z
        n = noise.noise(v.co * 0.5)
        c = mix(ROCK, ROCK_LIGHT, smoothstep(1, 9, above) * 0.7 + 0.2 * n)
        c = mix(c, ROCK_DARK, smoothstep(0.1, 0.6, -n) * 0.6)
        flat = smoothstep(0.72, 0.9, v.normal.z)
        if above > 0.4:
            c = mix(c, mix(GRASS, GRASS_DARK, 0.5 + 0.5 * noise.noise(v.co * 0.9)), flat * 0.85)
        c = mix(c, SAND, smoothstep(0.5, 0.0, abs(above - 0.1)) * 0.8)
        loop[col] = (c.r, c.g, c.b, 1.0)

me = bpy.data.meshes.new('Landing.Canyon')
bm.to_mesh(me)
bm.free()
for p in me.polygons:
    p.use_smooth = True
me.materials.append(material('Canyon'))
canyon = link('Landing.Canyon', me)

# --- The fall's ledge -------------------------------------------------------------------------------------------------
# A rock shelf jutting from the cliff just under the floating planter: the planter's streams land on it, and the real
# waterfall pours over its front lip (x LEDGE_LIP) down to the lake. Its lip sits just inside the top of the landing
# frame.
LEDGE_TOP, LEDGE_LIP = -0.7, -1.0
# A squashed, lumpy dome half sunk into the cliff: its front curves round into the rock at both ends (a horseshoe lip,
# as water wears one), its top a rough shelf, its underside bulging back into the wall.
LEDGE_CENTRE = Vector((2.0, 0.0))
LEDGE_REACH = (3.0, 2.7)  # half-extent out from the cliff (x) and along it (y)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=1.0)
for v in bm.verts:
    n = v.co.copy()
    below = max(0.0, -n.z)
    # The front lip (the equator, just under the top) is the most forward point: below it the rock is undercut,
    # stepping back into the cliff, so the water falls clear of it.
    reach = 1.0 - 0.55 * below
    x = LEDGE_CENTRE.x + n.x * LEDGE_REACH[0] * reach
    y = n.y * LEDGE_REACH[1] * (1.0 - 0.25 * below)
    # Top flattened into the shelf; below, a deep bulge tucked back into the cliff.
    z = LEDGE_TOP - 0.08 + n.z * 0.12 if n.z > 0 else LEDGE_TOP - 0.1 + n.z * (1.0 + 0.9 * max(0.0, n.x))
    p_ = Vector((x, y, z))
    # Lumpy rock: free on the top, only ever inward below the lip (nothing juts out in front of the falling water).
    bump = fbm(p_ * 0.9, 4) * 0.28 + noise.noise(p_ * 2.6) * 0.06
    p_ += n * (bump if n.z > 0.1 else -abs(bump))
    v.co = p_
bm.normal_update()
col = bm.loops.layers.color.new('Col')
for f in bm.faces:
    for loop in f.loops:
        v = loop.vert
        n = noise.noise(v.co * 0.6)
        c = mix(ROCK, ROCK_LIGHT, 0.45 + 0.3 * n)
        c = mix(c, ROCK_DARK, smoothstep(0.2, -0.8, v.normal.z) * 0.6)  # the underside in shadow
        c = mix(c, GRASS_DARK, smoothstep(0.75, 0.95, v.normal.z) * smoothstep(0.0, 0.4, noise.noise(v.co * 1.4 + Vector((5, 5, 5)))) * 0.8)
        loop[col] = (c.r, c.g, c.b, 1.0)
me = bpy.data.meshes.new('Landing.Ledge')
bm.to_mesh(me)
bm.free()
for p_ in me.polygons:
    p_.use_smooth = True
me.materials.append(material('Canyon'))
link('Landing.Ledge', me)

# --- Greenery on the ledges and tops ----------------------------------------------------------------------------------

dg = bpy.context.evaluated_depsgraph_get()
# (None round the fall's ledge and the planter above it, which the camera passes right by.)
spots = [(v.co.copy(), v.normal.copy()) for v in me.vertices if v.normal.z > 0.6 and v.co.z > LAKE_Z + 0.6
         and not (v.co.xy.length < 7 and v.co.z > -4)]
rnd.shuffle(spots)


def blob_cluster(bm, centre, radius, colour, col_layer, parts=4, squash=0.8):
    for _ in range(parts):
        r = radius * rnd.uniform(0.55, 1.0)
        off = Vector((rnd.gauss(0, radius * 0.5), rnd.gauss(0, radius * 0.5), rnd.uniform(0, radius * 0.6)))
        geom = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r)
        for v in geom['verts']:
            v.co.z *= squash
            v.co += v.co.normalized() * noise.noise(v.co * 3 + centre) * r * 0.18
            v.co += centre + off
        shade = rnd.uniform(0.85, 1.1)
        for f in {f for v in geom['verts'] for f in v.link_faces}:
            for loop in f.loops:
                loop[col_layer] = (colour.r * shade, colour.g * shade, colour.b * shade, 1.0)


bm = bmesh.new()
col = bm.loops.layers.color.new('Col')
SHRUB = Color((0.27, 0.45, 0.22))
for co, n in spots[:700]:
    blob_cluster(bm, co, rnd.uniform(0.15, 0.45), SHRUB if rnd.random() < 0.75 else Color((0.4, 0.55, 0.28)), col, parts=rnd.randint(2, 4))
me = bpy.data.meshes.new('Landing.Shrubs')
bm.to_mesh(me)
bm.free()
for p in me.polygons:
    p.use_smooth = True
me.materials.append(material('Shrubs'))
link('Landing.Shrubs', me)

# Blossom: low flowering bushes scattered over the slopes and ledges (not lollipop trees), thickest near the lake.
bm = bmesh.new()
col = bm.loops.layers.color.new('Col')
BLOSSOM = Color((0.97, 0.66, 0.74))
BLOSSOM_DEEP = Color((0.9, 0.5, 0.62))
bushes = 0
for co, n in spots[700:]:
    d = (co.xy - LAKE_CENTRE).length
    if d > 30 or bushes >= 220:
        continue
    blob_cluster(bm, co + Vector((0, 0, 0.1)), rnd.uniform(0.2, 0.5), BLOSSOM if rnd.random() < 0.6 else BLOSSOM_DEEP, col, parts=rnd.randint(3, 5), squash=0.7)
    bushes += 1
me = bpy.data.meshes.new('Landing.Blossom')
bm.to_mesh(me)
bm.free()
for p in me.polygons:
    p.use_smooth = True
me.materials.append(material('Blossom'))
link('Landing.Blossom', me)

# --- Distant mountains ------------------------------------------------------------------------------------------------

# A ring of soft ridges far out, highest toward the sun, that the haze turns into layered silhouettes.
bm = bmesh.new()
col = bm.loops.layers.color.new('Col')
FAR = Color((0.78, 0.6, 0.62))
FAR_FOOT = Color((0.62, 0.48, 0.56))
FAR_LIT = Color((0.95, 0.72, 0.58))
def ridged(p, octaves=6):
    """Ridged noise: sharp crests and steep valleys, as eroded peaks."""
    total, amp, freq, weight = 0.0, 0.6, 1.0, 1.0
    for _ in range(octaves):
        n = (1 - abs(noise.noise(p * freq))) ** 2
        total += n * amp * weight
        weight = min(1.0, n * 1.6)
        amp *= 0.5
        freq *= 2.05
    return total


# Four ranges, each a curtain of peaks: jagged ridged crests over rows that lean back as they rise (so the slopes
# shade), the farther ones taller and fainter in the haze.
ROWS = 6
for layer, (radius, top) in enumerate(((50, 13), (64, 22), (82, 32), (105, 44))):
    segs = 640
    grid = []
    for k in range(segs + 1):
        a = 2 * math.pi * k / segs
        toward_sun = max(0.0, math.cos(a - math.radians(75))) ** 2
        crest = top * (0.3 + 0.7 * toward_sun) * (0.35 + 0.9 * ridged(Vector((math.cos(a) * 3.5, math.sin(a) * 3.5, layer * 7.0))))
        column = []
        for j in range(ROWS + 1):
            t = j / ROWS
            r = radius + layer * 4 + t * top * 0.6
            h = (max(crest, 1.0) + 2) * t ** 0.85
            column.append(bm.verts.new((math.cos(a) * r, math.sin(a) * r, LAKE_Z - 2 + h)))
        grid.append(column)
    for k in range(segs):
        for j in range(ROWS):
            f = bm.faces.new((grid[k][j], grid[k + 1][j], grid[k + 1][j + 1], grid[k][j + 1]))
            for loop in f.loops:
                # Lit gold along the crests toward the sun, cooler mauve in the folds and at the foot.
                v = loop.vert.co
                up = smoothstep(LAKE_Z - 2, LAKE_Z + top + 2, v.z)
                c = mix(FAR_FOOT, FAR, up)
                c = mix(c, FAR_LIT, up * max(0.0, math.cos(math.atan2(v.y, v.x) - math.radians(75))) * 0.6)
                loop[col] = (c.r, c.g, c.b, 1.0)
me = bpy.data.meshes.new('Landing.Mountains')
bm.to_mesh(me)
bm.free()
me.materials.append(material('Mountains', 1.0))
link('Landing.Mountains', me)

# --- The lake ---------------------------------------------------------------------------------------------------------

bm = bmesh.new()
bmesh.ops.create_circle(bm, cap_ends=True, segments=128, radius=45)
bmesh.ops.triangulate(bm, faces=bm.faces)
bmesh.ops.translate(bm, vec=(LAKE_CENTRE.x, LAKE_CENTRE.y, LAKE_Z), verts=bm.verts)
me = bpy.data.meshes.new('Pool')
bm.to_mesh(me)
bm.free()
me.materials.append(bpy.data.materials['Water'])
link('Pool', me)

# --- Foreground garden ------------------------------------------------------------------------------------------------
# Laid out from the reference image (art/reference/landing-pov): each piece is placed by its pixel position in that
# 1536x1024 frame, cast back from the landing camera (JourneyCam at frame 770, art/build-journey.py) onto the water.

# Its own random stream, so rebuilding the canyon doesn't reshuffle the foreground.
rnd = random.Random(21)
scene.frame_set(770)
VIEW = bpy.data.objects['JourneyCam'].matrix_world.copy()
EYE = VIEW.translation.copy()
FORWARD = (VIEW.to_3x3() @ Vector((0, 0, -1))).normalized()
FOV = math.radians(38.0)
REF_W, REF_H = 1536, 1024


def ray(px, py):
    t = math.tan(FOV / 2)
    return (VIEW.to_3x3() @ Vector(((px / REF_W * 2 - 1) * t * REF_W / REF_H, (1 - py / REF_H * 2) * t, -1))).normalized()


def at(px, py, z=LAKE_Z):
    """The point on the plane at height z seen at pixel (px, py) of the reference."""
    d = ray(px, py)
    return EYE + d * ((z - EYE.z) / d.z)


def px_size(point, pixels):
    """How many metres `pixels` spans at `point`'s depth."""
    depth = (point - EYE).dot(FORWARD)
    return pixels * 2 * depth * math.tan(FOV / 2) / REF_H


def height_at(base, py):
    """How high above `base` a point must stand to appear at row py (for the reeds' tips and the cattail heads)."""
    lo, hi = 0.0, 6.0
    for _ in range(40):
        mid = (lo + hi) / 2
        p = base + Vector((0, 0, mid))
        v = VIEW.inverted() @ p
        row = (1 - (v.y / -v.z) / math.tan(FOV / 2)) * REF_H / 2
        lo, hi = (mid, hi) if row > py else (lo, mid)
    return lo


def rotate_z(v, a):
    c, s = math.cos(a), math.sin(a)
    return Vector((v.x * c - v.y * s, v.x * s + v.y * c, v.z))


def colour_faces(bm, geom_verts, layer, colour_fn):
    for f in {f for v in geom_verts for f in v.link_faces}:
        for loop in f.loops:
            c = colour_fn(loop.vert.co)
            loop[layer] = (c.r, c.g, c.b, 1.0)


def finish(name, bm, mat, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    me.materials.append(mat)
    return link(name, me)


# Lily pads: broad, notched, the rim lifting a little; yellow-green where the low sun comes through, a gold rim.
PAD = Color((0.16, 0.33, 0.05))
PAD_LIT = Color((0.42, 0.56, 0.12))
PAD_VEIN = Color((0.55, 0.66, 0.24))
PAD_EDGE = Color((0.78, 0.55, 0.14))
# (px, py, half-width in px) in the reference.
PADS = [(520, 852, 330), (130, 765, 130), (150, 722, 95), (385, 722, 115), (80, 838, 120), (300, 674, 135), (430, 646, 60),
        (545, 641, 40), (205, 652, 55), (1150, 738, 95), (1235, 746, 55), (1245, 653, 40), (90, 965, 210), (330, 925, 110),
        (640, 650, 45), (40, 700, 60)]
# Where the frog sits (as below), so its pad can carry the frog's soft contact shadow.
FROG_SPOT_AT = at(530, 828)
FROG_SHADOW_R = px_size(FROG_SPOT_AT, 95)
bm = bmesh.new()
col = bm.loops.layers.color.new('Col')
pad_centres = []
for k, (px, py, half) in enumerate(PADS):
    centre = at(px, py) + Vector((0, 0, 0.012))
    r = px_size(centre, half)
    spin = rnd.uniform(0, 6.28)
    pad_centres.append((centre, r))
    # Concentric rings of quads round a centre vertex, so the rim can curl up and carry its gold edge; the notch is a
    # wedge pinched in to the centre.
    SEGS, RINGS = 72, 7
    hub = bm.verts.new((0, 0, 0))
    rings = []
    for k in range(1, RINGS + 1):
        rr = (k / RINGS) ** 0.8
        ring = []
        for j in range(SEGS):
            a = 2 * math.pi * j / SEGS
            notch = smoothstep(0.2, 0.08, min(a, 2 * math.pi - a))
            ring.append(bm.verts.new((math.cos(a) * rr * (1 - 0.94 * notch), math.sin(a) * rr * (1 - 0.94 * notch), 0)))
        rings.append(ring)
    for j in range(SEGS):
        bm.faces.new((hub, rings[0][j], rings[0][(j + 1) % SEGS]))
        for k in range(RINGS - 1):
            bm.faces.new((rings[k][j], rings[k + 1][j], rings[k + 1][(j + 1) % SEGS], rings[k][(j + 1) % SEGS]))
    verts = [hub] + [v for ring in rings for v in ring]
    for v in verts:
        d = v.co.xy.length
        v.co.z = smoothstep(0.82, 1.0, d) * 0.05 + noise.noise(v.co * 2.5 + centre) * 0.025
        v.co = rotate_z(v.co * r, spin) + centre

    def pad_colour(co, centre=centre, r=r, spin=spin):
        d = (co - centre).xy
        t = d.length / r
        vein = abs(math.sin(math.atan2(d.y, d.x) * 11 - spin * 11)) ** 30
        lit = smoothstep(-0.3, 0.6, noise.noise(co * 1.7 + centre)) * 0.6 + 0.4 * smoothstep(0.3, 1.0, -d.y / r)
        c = mix(PAD, PAD_LIT, lit)
        c = mix(c, PAD_VEIN, vein * 0.6 * smoothstep(0.1, 0.4, t))
        c = mix(c, PAD_EDGE, smoothstep(0.88, 1.0, t) * 0.85)
        # Occlusion under the frog: darkest at its feet, fading out over its own length, stretched away from the sun.
        off = co.xy - FROG_SPOT_AT.xy
        shade = 1 - smoothstep(0.0, FROG_SHADOW_R, (Vector((off.x * 0.8, off.y * 1.3))).length)
        return mix(c, Color((0.04, 0.07, 0.02)), shade * 0.75)

    colour_faces(bm, verts, col, pad_colour)
finish('Landing.Pads', bm, material('Pad', 0.4))

# Water lilies: pointed petals in three rings, white flushing pink, cupped up round a yellow heart.
PETAL = Color((0.99, 0.95, 0.95))
PETAL_TIP = Color((0.97, 0.66, 0.78))
HEART = Color((1.0, 0.78, 0.25))
bm = bmesh.new()
col = bm.loops.layers.color.new('Col')
for px, py, half in ((88, 700, 78), (365, 637, 24), (462, 641, 22), (528, 637, 18), (700, 645, 15)):
    centre = at(px, py) + Vector((0, 0, 0.02))
    size = px_size(centre, half)
    # Three rings of petals, the outer spreading, the inner standing up into a cup round the heart.
    for ring, (count, length, tilt) in enumerate(((11, 1.0, 0.3), (10, 0.9, 0.75), (8, 0.75, 1.15), (6, 0.55, 1.4))):
        for k in range(count):
            a = 2 * math.pi * (k + 0.5 * ring) / count + rnd.uniform(-0.1, 0.1)
            L = length * size * rnd.uniform(0.9, 1.05)
            geom = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=1)
            for v in geom['verts']:
                # A pointed, cupped petal: long, narrow at the tip, curling up at its edges.
                x = v.co.x * 0.5 + 0.5
                w = math.sin(math.pi * min(x, 0.999) ** 0.8) * 0.2
                local = Vector((x * L, v.co.y * L * w, v.co.z * L * 0.03 + (v.co.y * w) ** 2 * L * 1.2))
                c, s = math.cos(tilt), math.sin(tilt)
                local = Vector((local.x * c - local.z * s, local.y, local.x * s + local.z * c))
                v.co = rotate_z(local, a) + centre
            colour_faces(bm, geom['verts'], col, lambda co, c=centre, L=L: mix(PETAL, PETAL_TIP, smoothstep(0.55, 1.0, (co - c).length / L) * 0.8))
    geom = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=size * 0.18)
    for v in geom['verts']:
        v.co.z *= 0.7
        v.co += centre + Vector((0, 0, size * 0.15))
    colour_faces(bm, geom['verts'], col, lambda co: HEART)
finish('Landing.Lilies', bm, material('Lily', 0.5))

# The frog: one smooth body, sitting up on the big pad side-on, looking right toward the fall. Built as a skeleton of
# tapering limbs (chains of spheres), fused into one skin by a voxel remesh and smoothed so the joins flow.
FROG_BACK = Color((0.5, 0.46, 0.24))
FROG_SIDE = Color((0.6, 0.55, 0.32))
FROG_SPOT = Color((0.27, 0.24, 0.11))
FROG_BELLY = Color((0.93, 0.88, 0.74))
FROG_RIDGE = Color((0.66, 0.6, 0.38))
FROG_BASE = at(530, 828) + Vector((0, 0, 0.018))
FROG_FACING = math.radians(-62)  # nose toward the fall, a little away from the camera
FROG_SIZE = px_size(FROG_BASE, 170) / 0.36  # the reference's frog is about 170 px long; the model is 0.36 m

# (start, start radius, end, end radius) in the frog's frame: x forward (nose), y left, z up.
FROG_LIMBS = [
    # Sitting up as the reference's: back sloping steeply from the rump to the shoulders, head held high.
    ((-0.1, 0, 0.06), 0.068, (0.04, 0, 0.14), 0.08),  # body, rising to the shoulders
    ((-0.05, 0, 0.05), 0.06, (0.06, 0, 0.09), 0.062),  # belly
    ((0.04, 0, 0.14), 0.078, (0.11, 0, 0.19), 0.062),  # shoulders into the head
    ((0.11, 0, 0.19), 0.062, (0.185, 0, 0.175), 0.03),  # the broad head narrowing to the snout
    ((0.09, 0, 0.145), 0.058, (0.16, 0, 0.152), 0.033),  # throat and jaw
]
for side in (-1, 1):
    FROG_LIMBS += [
        ((0.115, 0.045 * side, 0.222), 0.034, (0.124, 0.05 * side, 0.232), 0.031),  # eye bulge
        ((-0.02, 0.052 * side, 0.175), 0.016, (-0.09, 0.05 * side, 0.1), 0.014),  # dorsolateral ridge
        ((-0.1, 0.055 * side, 0.055), 0.05, (0.0, 0.095 * side, 0.06), 0.034),  # thigh, forward to the knee
        ((0.0, 0.095 * side, 0.06), 0.032, (-0.075, 0.105 * side, 0.022), 0.022),  # shin, back to the ankle
        ((-0.075, 0.105 * side, 0.018), 0.02, (0.03, 0.14 * side, 0.01), 0.011),  # long hind foot, splayed forward
        ((0.03, 0.14 * side, 0.01), 0.011, (0.06, 0.16 * side, 0.008), 0.007),  # toes
        ((0.09, 0.05 * side, 0.13), 0.026, (0.14, 0.06 * side, 0.015), 0.017),  # front leg, straight down
        ((0.14, 0.06 * side, 0.012), 0.016, (0.18, 0.08 * side, 0.008), 0.008),  # hand
    ]
bm = bmesh.new()
for a, ra, b, rb in FROG_LIMBS:
    a, b = Vector(a), Vector(b)
    steps = max(2, int((b - a).length / (min(ra, rb) * 0.35)) + 1)
    for k in range(steps + 1):
        t = k / steps
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=ra + (rb - ra) * t,
                                  matrix=__import__('mathutils').Matrix.Translation(a.lerp(b, t)))
me = bpy.data.meshes.new('FrogParts')
bm.to_mesh(me)
bm.free()
parts = bpy.data.objects.new('FrogParts', me)
scene.collection.objects.link(parts)
remesh = parts.modifiers.new('Remesh', 'REMESH')
remesh.mode = 'VOXEL'
remesh.voxel_size = 0.004
smooth = parts.modifiers.new('Smooth', 'CORRECTIVE_SMOOTH')
smooth.iterations = 12
smooth.use_only_smooth = True
smooth.smooth_type = 'LENGTH_WEIGHTED'
bpy.context.view_layer.update()
frog_me = bpy.data.meshes.new_from_object(parts.evaluated_get(bpy.context.evaluated_depsgraph_get()))
bpy.data.objects.remove(parts)
bpy.data.meshes.remove(me)

bm = bmesh.new()
bm.from_mesh(frog_me)
bpy.data.meshes.remove(frog_me)
col = bm.loops.layers.color.new('Col')


def frog_colour(co):
    # co is in the frog's local frame (before placing it). Cream belly and throat up the lower flank (a line rising
    # toward the head), olive-brown back with dark blotches, a pale ridge down each side, a dark mask behind the eye
    # over the eardrum, and a pale lip line.
    line = 0.06 + 0.5 * max(co.x + 0.06, 0.0)
    belly = smoothstep(0.012, -0.012, co.z - line)
    # (Not on the legs: banded olive like the back.)
    leg = smoothstep(0.062, 0.078, abs(co.y)) * smoothstep(0.05, 0.02, co.x)
    belly *= 1.0 - leg
    c = mix(FROG_SIDE, FROG_BACK, smoothstep(line, line + 0.08, co.z))
    spots = smoothstep(0.28, 0.48, noise.noise(co * 30 + Vector((3, 1, 7))))
    c = mix(c, FROG_SPOT, spots * 0.7 * smoothstep(line, line + 0.03, co.z))
    ridge = smoothstep(0.012, 0.0, abs(abs(co.y) - 0.062)) * smoothstep(-0.1, -0.05, co.x) * smoothstep(0.06, 0.0, co.x) * smoothstep(0.08, 0.12, co.z)
    c = mix(c, FROG_RIDGE, ridge * 0.7)
    mask = smoothstep(0.018, 0.0, abs(co.z - 0.205 + 0.35 * (co.x - 0.1))) * smoothstep(0.0, 0.03, 0.06 - abs(co.x - 0.07)) * smoothstep(0.035, 0.055, abs(co.y))
    c = mix(c, FROG_SPOT, mask * 0.65)
    lip = smoothstep(0.006, 0.0, abs(co.z - (0.165 - 0.12 * (co.x - 0.12)))) * smoothstep(0.1, 0.13, co.x)
    c = mix(c, FROG_BELLY, lip * 0.8)
    bands = smoothstep(0.35, 0.6, math.sin(co.x * 90 + co.z * 40) * 0.5 + 0.5 + noise.noise(co * 40) * 0.3)
    c = mix(c, mix(FROG_SIDE, FROG_SPOT, bands * 0.35), leg)
    return mix(c, FROG_BELLY, belly * 0.9)


for f in bm.faces:
    for loop in f.loops:
        c = frog_colour(loop.vert.co)
        loop[col] = (c.r, c.g, c.b, 1.0)
for v in bm.verts:
    v.co = rotate_z(v.co * FROG_SIZE, FROG_FACING) + FROG_BASE
finish('Landing.Frog', bm, material('Frog', 0.3))

# Its eyes: gold, glossy, with a black horizontal pupil looking out to the side.
EYE_GOLD = Color((0.78, 0.68, 0.36))
EYE_RIM = Color((0.35, 0.22, 0.06))
PUPIL = Color((0.02, 0.015, 0.01))
bm = bmesh.new()
col = bm.loops.layers.color.new('Col')
for side in (-1, 1):
    centre_local = Vector((0.124, 0.06 * side, 0.236))
    r = 0.028
    geom = bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=1)
    out = Vector((0.35, side * 1.0, 0.25)).normalized()
    for v in geom['verts']:
        n = v.co.normalized()
        facing = n.dot(out)
        v.co = rotate_z((centre_local + n * r) * FROG_SIZE, FROG_FACING) + FROG_BASE
        v.normal = n
    for f in {f for v in geom['verts'] for f in v.link_faces}:
        for loop in f.loops:
            n = rotate_z(loop.vert.co - FROG_BASE, -FROG_FACING) / FROG_SIZE - centre_local
            n.normalize()
            facing = n.dot(out)
            # The pupil: a horizontal slot round the outward axis.
            up = Vector((0, 0, 1))
            vert = abs(n.dot(up) - out.dot(up) * facing)
            pupil = smoothstep(0.86, 0.9, facing) * smoothstep(0.2, 0.12, vert) + smoothstep(0.94, 0.97, facing)
            c = mix(EYE_GOLD, EYE_RIM, smoothstep(0.55, 0.2, facing))
            c = mix(c, PUPIL, min(1.0, pupil))
            loop[col] = (c.r, c.g, c.b, 1.0)
finish('Landing.FrogEyes', bm, material('FrogEye', 0.08))

# Reeds and cattails, towering up the right of the frame from a bed at the water's edge.
REED = Color((0.12, 0.3, 0.06))
REED_LIGHT = Color((0.32, 0.55, 0.12))
REED_TIP = Color((0.62, 0.6, 0.22))
CATTAIL = Color((0.5, 0.31, 0.14))
CATTAIL_LIT = Color((0.82, 0.58, 0.3))
bm = bmesh.new()
col = bm.loops.layers.color.new('Col')
REED_BED = at(1420, 770)
# The pebbles (placed below) by pixel position in the reference, defined here so the reeds can root between them.
PEBBLES = [(1300, 745, 55), (1490, 788, 70), (1080, 1005, 115), (1235, 965, 95), (1405, 905, 90), (1525, 880, 60),
           (930, 1015, 95), (1355, 1015, 105), (1180, 885, 55), (1050, 905, 42), (1530, 985, 75), (1280, 880, 40),
           # The heap behind and between, smaller stones climbing toward the reeds.
           (1340, 820, 38), (1440, 830, 45), (1230, 820, 30), (1500, 740, 50), (1400, 770, 35), (1120, 845, 32),
           (990, 960, 50), (1460, 960, 55), (1160, 960, 45), (1300, 940, 45), (860, 1000, 60), (1420, 1000, 60)]


def in_pebble(point):
    """Whether a point on the water lies under one of the pebbles (with a little margin)."""
    for px, py, half in PEBBLES:
        c = at(px, py)
        if (point.xy - c.xy).length < px_size(c, half) * 1.15:
            return True
    return False


edge_layer = bm.verts.layers.float.new('_edge')


def blade(base, height, width, lean, bend_dir, shade):
    """A grass blade: broad, keeled down a midrib (three verts across, the middle raised), tapering to a point and
    arching over toward bend_dir. Turned mostly broadside to the camera, so its width reads."""
    segs = 18
    to_eye = (EYE - base)
    to_eye.z = 0
    to_eye.normalize()
    face = Vector((-to_eye.y, to_eye.x, 0))
    twist = rnd.uniform(-0.5, 0.5)
    side = (face * math.cos(twist) + to_eye * math.sin(twist)).normalized()
    keel = to_eye * width * 0.35
    base_colour = mix(REED, REED_LIGHT, shade)
    prev = None
    for k in range(segs + 1):
        t = k / segs
        w = width * (1 - t ** 1.4) * (0.75 + 0.25 * math.sin(math.pi * min(t * 2.2, 1.0)))
        centre = base + Vector((0, 0, height * t * (1 - 0.35 * lean * t))) + bend_dir * lean * height * t ** 1.8
        row = (bm.verts.new(centre - side * w), bm.verts.new(centre + keel * (1 - t)), bm.verts.new(centre + side * w))
        # Margins marked (the site's '_edge' attribute): -1 one side, 1 the other, 0 the midrib, so the site can tell
        # which margin faces the sun.
        row[0][edge_layer] = -1.0
        row[2][edge_layer] = 1.0
        if prev:
            for j in range(2):
                f = bm.faces.new((prev[j], prev[j + 1], row[j + 1], row[j]))
                for loop in f.loops:
                    c = mix(base_colour, REED_TIP, smoothstep(0.45, 1.0, t) * 0.6)
                    loop[col] = (c.r, c.g, c.b, 1.0)
        prev = row


# Broad blades in a clump, the tallest arching out over the water to the left (as in the reference), and thinner
# ones between.
for i in range(85):
    base = REED_BED + Vector((rnd.gauss(0.15, 0.3), rnd.gauss(-0.1, 0.35), -0.05))
    while in_pebble(base):
        base = REED_BED + Vector((rnd.gauss(0.15, 0.3), rnd.gauss(-0.1, 0.35), -0.05))
    top = height_at(base, rnd.uniform(-60, 520))
    broad = rnd.random() < 0.55
    lean = rnd.uniform(0.15, 0.7) if broad else rnd.uniform(0.0, 0.3)
    # Mostly leaning left in the frame (toward +y, Blender) and a little toward the camera.
    bend = Vector((rnd.uniform(-0.8, 0.2), rnd.uniform(0.2, 1.0), 0)).normalized()
    blade(base, top * (0.9 if broad else 1.0), rnd.uniform(0.025, 0.05) if broad else rnd.uniform(0.008, 0.018), lean, bend, rnd.random())
# Cattails: tall stems with a brown velvet head and a thin spike above (heads as in the reference).
for hx, head_top, head_bottom in ((1462, 105, 195), (1425, 210, 300), (1420, 318, 420), (1500, 260, 335), (1385, 420, 480)):
    base = at(hx, 775) + Vector((rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), -0.05))
    z0, z1 = height_at(base, head_bottom), height_at(base, head_top)
    stem_top = z1 + (z1 - z0) * 0.6
    geom = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.006, radius2=0.002, depth=stem_top)
    for v in geom['verts']:
        v.co += base + Vector((0, 0, stem_top / 2))
    colour_faces(bm, geom['verts'], col, lambda co: REED)
    radius = px_size(base, 11)
    geom = bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=12, radius=1)
    for v in geom['verts']:
        # A sausage, not an egg: round in section, straight-sided along its length.
        h = math.hypot(v.co.x, v.co.y)
        fill = (1 - abs(v.co.z) ** 4) ** 0.25 / h if h > 1e-6 else 0.0
        v.co = Vector((v.co.x * fill * radius, v.co.y * fill * radius, v.co.z * (z1 - z0) / 2)) + base + Vector((0, 0, (z0 + z1) / 2))
    # Fibrous, lit gold on the sun's side (+y, the frame's left).
    colour_faces(bm, geom['verts'], col, lambda co, b=base: mix(CATTAIL, CATTAIL_LIT, min(1.0, smoothstep(-0.2, 0.6, noise.noise(co * 60)) * 0.5 + smoothstep(-0.02, 0.03, (co - b).y) * 0.5)))
finish('Landing.Reeds', bm, material('Reed', 0.45))

# Pebbles: wet grey-brown granite (speckled and glittering on the site), heaped in the bottom right (out of focus,
# close to the camera) and climbing to the reeds, a couple by the pads. Irregular river stones, not eggs.
STONE = Color((0.74, 0.66, 0.58))
STONE_WARM = Color((0.78, 0.64, 0.52))
STONE_GREY = Color((0.64, 0.62, 0.6))
bm = bmesh.new()
col = bm.loops.layers.color.new('Col')
for px, py, half in PEBBLES:
    contact = at(px, py)
    r = px_size(contact, half)
    centre = contact + Vector((0, 0, r * 0.1))
    tone = rnd.uniform(0, 1)
    base = mix(mix(STONE, STONE_WARM, tone), STONE_GREY, rnd.uniform(0, 0.6))
    geom = bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=20, radius=1)
    sx, sy, sz = rnd.uniform(0.85, 1.2), rnd.uniform(0.7, 1.0), rnd.uniform(0.5, 0.75)
    spin = rnd.uniform(0, 6.28)
    seed = Vector((rnd.uniform(0, 50), rnd.uniform(0, 50), rnd.uniform(0, 50)))
    for v in geom['verts']:
        n = v.co.copy()
        # Lumpy and a little faceted: low-frequency bulges, sunk a little into the shallows.
        bulge = noise.noise(n * 1.3 + seed) * 0.16 + noise.noise(n * 3.1 + seed) * 0.05
        local = Vector((n.x * sx, n.y * sy, n.z * sz)) * (1 + bulge)
        v.co = rotate_z(local * r, spin) + centre
    colour_faces(bm, geom['verts'], col, lambda co, c=base: c)
finish('Landing.Pebbles', bm, material('Pebble', 0.45))

# Dew: beads on the pads, a few big ones as in the reference, glinting in the low sun ('Dew' on the site).
bm = bmesh.new()
for centre, r in pad_centres:
    for i in range(int(10 + 70 * min(r, 1.0))):
        a = rnd.uniform(0, 6.28)
        d = r * math.sqrt(rnd.uniform(0.02, 0.85))
        spot = centre + Vector((math.cos(a) * d, math.sin(a) * d, 0.0))
        if (spot.xy - FROG_BASE.xy).length < 0.12 * FROG_SIZE * 1.4:
            continue
        size = r * rnd.choice((0.005, 0.007, 0.01, 0.014, 0.02, 0.035))
        geom = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=size)
        for v in geom['verts']:
            v.co.z *= 0.55
            v.co += spot + Vector((0, 0, size * 0.35 + 0.005))
me = bpy.data.meshes.new('Landing.Dew')
bm.to_mesh(me)
bm.free()
for p in me.polygons:
    p.use_smooth = True
dew = bpy.data.materials.get('Dew') or bpy.data.materials.new('Dew')
me.materials.append(dew)
link('Landing.Dew', me)
