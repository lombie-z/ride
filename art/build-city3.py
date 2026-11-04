"""The third city (art/reference/concept-hive-plaza.webp, concept-hive-city.webp, concept-transition-desert.webp): a coral
hive at dawn. A long causeway of polished pale stone over a pink mist runs straight at a bone-white gothic hive cathedral
with honeycomb amber windows, through its nave, then weaves through bone towers, coral and flesh dripping black ooze,
under rib arches and skybridges, to a plaza at the heart of the city: a giant glowing amber heart hung inside a ribcage
of calcified bone arches over a moat, ooze-legged platforms around it. The exit runs on out of the plaza, under the heart,
and away along a highway with the hive's edge on its left, the stone giving way to cracked asphalt and sand.
Builds art/city3.blend from scratch and exports public/models/city3.glb (Draco, GPU instancing, vertex-colour AO/dirt).
Run: /opt/homebrew/bin/blender --background --factory-startup --python art/build-city3.py
     CITY3_ROUND=r1 names the renders (default r0); CITY3_NO_EEVEE=1 skips the EEVEE renders; CITY3_NO_BAKE=1 skips
     the Cycles AO bake (dirt only); CITY3_VIEWS=arrival,approach,exit,plan picks the renders.

City3's own frame (Blender z up, metres): the road comes in along +X at City3.RoadIn (the local origin, deck top z 0,
11.8 m wide; x < 0 is the chrome city's and stays empty). A 900 m causeway (the cathedral's face at x 700, its nave to
x 860), then a weave through the hive (left 40 deg, right 80 deg, left 40 deg, all radius 300 m, 200 m straights between)
back onto heading +X, and a 250 m straight into the plaza: ~2388 m to the bike (City3.RoadPath, [x, y] every 2 m).
The bike parks heading +X (City3.BikeMark) at the moat's edge, nose to a slipway. City3.RoadOut goes on from the bike:
160 m straight over the slipway, across the heart's island under the heart, over the far moat, then right 30 deg (radius
300 m) onto a 400 m straight heading -30 deg: END / END_HEADING at its last point, where the desert takes over.

The arrival shot is fitted to the concept by art/align3/ (as art/align2/ for city2): fit_camera.py fits EYE/LOOK/FOV in
the bike's frame to the concept bike and horizon; this script composes the plaza in the arrival camera's screen space
from the features extract_concept.py measured or traced (the kerb strip, the heart, the ribs, the platforms, the
honeycomb towers, the sun); score.py scores the result (overlay + compare). The approach camera (City3.ApproachCam,
~310 m short of the cathedral) is fitted to the concept's causeway vanishing point and kerb, and the cathedral composed
in its screen space from the concept's traced skyline; score.py approach scores that too.

Renders (art/renders/): city3-arrival-<round>.png (EEVEE, with the site's bike), city3-arrival-ids-<round>.png and
city3-approach-ids-<round>.png (flat IDs for score.py), city3-approach-<round>.png, city3-exit-<round>.png,
city3-plan.png; overlays in art/align3/out/.
"""
import json
import math
import os
import random
import subprocess

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ALIGN = os.path.join(ROOT_DIR, 'art', 'align3')
BLEND = os.path.join(ROOT_DIR, 'art', 'city3.blend')
GLB = os.path.join(ROOT_DIR, 'public', 'models', 'city3.glb')
RENDERS = os.path.join(ROOT_DIR, 'art', 'renders')
BIKE_GLB = os.path.join(ROOT_DIR, 'public', 'models', 'bike.glb')
ROUND = os.environ.get('CITY3_ROUND', 'r0')
VIEWS = os.environ.get('CITY3_VIEWS', 'arrival,approach,exit,plan').split(',')
FEAT = json.load(open(os.path.join(ALIGN, 'concept-features.json')))
FEAT_A = json.load(open(os.path.join(ALIGN, 'concept-approach-features.json')))
CAMFIT = json.load(open(os.path.join(ALIGN, 'arrival-camera.json')))
APPFIT = json.load(open(os.path.join(ALIGN, 'approach-camera.json')))
RES = (1280, 720)
rnd = random.Random(11)

# --- Layout ------------------------------------------------------------------------------------------------------------
ROAD_W = 11.8
CAUSEWAY = 900.0          # RoadIn -> the weave (the cathedral's face at CATH_X, its nave through to CATH_X + 160)
CATH_X = 700.0
NAVE_END = 860.0
WEAVE_R = 300.0
TAIL = 250.0              # the last straight, into the plaza and to the bike
ROAD_SEQ = [('S', CAUSEWAY), ('A', WEAVE_R, 40), ('S', 300.0), ('A', WEAVE_R, -80), ('S', 300.0), ('A', WEAVE_R, 80), ('S', 300.0),
            ('A', WEAVE_R, -80), ('S', 300.0), ('A', WEAVE_R, 40),
            ('S', TAIL)]
OUT_SEQ = [('S', 160.0), ('A', WEAVE_R, -30), ('S', 400.0)]
MIST_Z = -60.0            # the floor of the mist the city stands in
WATER_Z = -0.04           # the plaza's moat


def trace(seq, step, x=0.0, y=0.0, h=0.0):
    """Dense points along a straights-and-arcs sequence from (x, y) heading h, ~`step` m apart (each segment divided
    evenly, its end points exact). Returns points and the final heading."""
    pts = [Vector((x, y, 0))]
    for sg in seq:
        if sg[0] == 'S':
            n = max(1, round(sg[1] / step))
            for i in range(1, n + 1):
                pts.append(Vector((x + math.cos(h) * sg[1] * i / n, y + math.sin(h) * sg[1] * i / n, 0)))
        else:
            R, d = sg[1], math.radians(sg[2])
            side = 1 if d > 0 else -1
            cx, cy = x - side * R * math.sin(h), y + side * R * math.cos(h)
            a0 = h - side * math.pi / 2
            n = max(2, round(abs(d) * R / step))
            for i in range(1, n + 1):
                a = a0 + d * i / n
                pts.append(Vector((cx + R * math.cos(a), cy + R * math.sin(a), 0)))
            h += d
        x, y = pts[-1].x, pts[-1].y
    return pts, h


def resample_exact(pts, step):
    """Points every `step` m of arc length along a polyline, plus its exact end."""
    out, acc = [pts[0]], 0.0
    for a, b in zip(pts, pts[1:]):
        seg = (b - a).length
        t0 = 0.0
        while acc + (seg - t0) >= step - 1e-9:
            t0 += step - acc
            out.append(a.lerp(b, t0 / seg))
            acc = 0.0
        acc += seg - t0
    if (out[-1] - pts[-1]).length > 1e-3:
        out.append(pts[-1])
    return out


def plen(pts):
    return sum((b - a).length for a, b in zip(pts, pts[1:]))


_in, _h = trace(ROAD_SEQ, 0.5)
BIKE_AT = _in[-1].copy()
assert abs(_h) < 1e-9 and abs(BIKE_AT.y) < 1e-3, (_h, BIKE_AT)
BIKE_AT.y = 0.0
_in[-1] = BIKE_AT.copy()
ROAD_LINE = resample_exact(_in, 2.0)
ROAD_LEN = plen(_in)
_out, OUT_H = trace(OUT_SEQ, 0.5, BIKE_AT.x, BIKE_AT.y, 0.0)
OUT_LINE = resample_exact(_out, 2.0)
OUT_LEN = plen(_out)
OUT_END = _out[-1].copy()
print('road in', round(ROAD_LEN, 1), 'm; out', round(OUT_LEN, 1), 'm; bike', BIKE_AT, 'end', OUT_END, OUT_H)
BIKE_YAW = 0.0
BIKE_M = Matrix.Translation(BIKE_AT) @ Matrix.Rotation(math.radians(BIKE_YAW), 4, 'Z')


def B(x, y, z=0.0):
    """A point in the bike's frame (the arrival composition is worked out there) -> City3."""
    return BIKE_M @ Vector((x, y, z))


# --- The arrival camera: fitted in the bike's frame, carried into City3's ------------------------------------------------
EYE = BIKE_M @ Vector(CAMFIT['EYE'])
LOOK = BIKE_M @ Vector(CAMFIT['LOOK'])
FOV = CAMFIT['FOV']


class View:
    """A pinhole camera (vertical FOV, no roll) and its screen-space helpers, 1280x720."""

    def __init__(self, eye, look, fov):
        self.eye, self.look, self.fov = Vector(eye), Vector(look), fov
        self.fwd = (self.look - self.eye).normalized()
        self.right = self.fwd.cross(Vector((0, 0, 1))).normalized()
        self.up = self.right.cross(self.fwd)
        self.tv = math.tan(math.radians(fov / 2))
        self.th = self.tv * RES[0] / RES[1]
        self.fpx = RES[1] / 2 / self.tv

    def ray(self, sx, sy):
        nx = (sx - RES[0] / 2) / (RES[0] / 2)
        ny = (RES[1] / 2 - sy) / (RES[1] / 2)
        return self.fwd + self.right * nx * self.th + self.up * ny * self.tv

    def point(self, sx, sy, depth):
        """The point at pixel (sx, sy), `depth` m along the view axis."""
        return self.eye + depth * self.ray(sx, sy)

    def at_z(self, sx, sy, z):
        d = self.ray(sx, sy)
        return self.eye + d * ((z - self.eye.z) / d.z)

    def on_plane(self, sx, sy, p0, n):
        """Where pixel (sx, sy)'s ray meets the plane through p0 with normal n."""
        d = self.ray(sx, sy)
        return self.eye + d * ((p0 - self.eye).dot(n) / d.dot(n))

    def screen(self, p):
        v = p - self.eye
        d = v.dot(self.fwd)
        return Vector((RES[0] / 2 * (1 + v.dot(self.right) / (d * self.th)),
                       RES[1] / 2 * (1 - v.dot(self.up) / (d * self.tv)))), d

    def depth(self, p):
        return (p - self.eye).dot(self.fwd)

    def m(self, px, depth):
        return px * depth / self.fpx


ARR = View(EYE, LOOK, FOV)
APP_X = CATH_X - 310.0
APP_EYE = Vector((APP_X, 0, 0)) + Vector(APPFIT['EYE'])
APP_LOOK = Vector((APP_X, 0, 0)) + Vector(APPFIT['LOOK'])
APP_FOV = APPFIT['FOV']
APP = View(APP_EYE, APP_LOOK, APP_FOV)
# The exit: the rider on the exit's last straight, looking down it (the hive on the left, the desert ahead).
_oi = int((OUT_LEN - 300.0) / 2.0)
_op, _oq = OUT_LINE[_oi], OUT_LINE[_oi + 5]
_od = (_oq - _op).normalized()
EXIT_EYE = _op + Vector((-_od.y, _od.x, 0)) * -1.8 + Vector((0, 0, 1.6))
EXIT_LOOK = EXIT_EYE + (_od * 10 + Vector((-_od.y, _od.x, 0)) * 2.2) + Vector((0, 0, -0.25))
EXIT = View(EXIT_EYE, EXIT_LOOK, 55.0)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
root = bpy.data.objects.new('City3', None)
scene.collection.objects.link(root)


# --- Textures: one small tiling stone-slab texture, made here (packed into the .blend and the glb) --------------------
def stone_texture(n=512):
    """Polished pale stone slabs: a 2x2 running-bond tile of slabs with fine joints, soft mottling, a few hairline
    cracks. Values are multipliers round 1 on the base colour (light, so the material colour stays in charge)."""
    rng = np.random.default_rng(3)
    yy, xx = np.mgrid[0:n, 0:n] / n
    img = np.ones((n, n))
    # Mottling: a few octaves of smooth noise (tileable: sums of whole-period sines).
    for k, amp in ((2, 0.05), (5, 0.035), (11, 0.02), (23, 0.012)):
        for _ in range(3):
            fx, fy = rng.integers(1, k + 1, 2)
            ph = rng.uniform(0, 2 * np.pi, 2)
            img += amp * np.sin(2 * np.pi * (fx * xx + ph[0] / 6.28)) * np.sin(2 * np.pi * (fy * yy + ph[1] / 6.28))
    # Per-slab tone: rows of two slabs, the second row offset by half (running bond).
    row = (yy * 2).astype(int)
    col = ((xx + 0.5 * row) * 2).astype(int) % 2
    tone = rng.uniform(-0.05, 0.05, (2, 2))
    img += tone[row, col]
    # Joints.
    jx = np.abs(((xx + 0.5 * row) * 2) % 1 - 0.0)
    jx = np.minimum(jx, 1 - jx)
    jy = np.abs((yy * 2) % 1)
    jy = np.minimum(jy, 1 - jy)
    j = np.minimum(jx, jy)
    img *= 1 - 0.38 * np.exp(-(j * n / 2 / 1.2) ** 2)
    # Hairline cracks: random walks.
    for _ in range(9):
        p = rng.uniform(0, 1, 2)
        ang = rng.uniform(0, 2 * np.pi)
        for _ in range(int(rng.uniform(60, 180))):
            ang += rng.normal(0, 0.35)
            p = (p + 0.0035 * np.array([np.cos(ang), np.sin(ang)])) % 1
            x, y = int(p[0] * n), int(p[1] * n)
            img[y, x] *= 0.8
            img[y, (x + 1) % n] *= 0.9
    img = np.clip(img, 0, 1.2) / 1.2
    rgba = np.ones((n, n, 4), np.float32)
    rgba[..., 0] = img
    rgba[..., 1] = img * 0.985
    rgba[..., 2] = img * 0.965
    im = bpy.data.images.new('City3StoneSlabs', n, n, alpha=False)
    im.pixels.foreach_set(rgba[::-1].ravel())
    im.pack()
    return im


STONE_IMG = stone_texture()


def heart_texture(w=512, h=256):
    """The heart's skin, wrapped (equirectangular on its UV sphere): a deep glowing amber-orange, hotter in blotches,
    under a network of dark red-brown veins (branching random walks, thick trunks from the top thinning downward).
    Used as base and emissive colour, so the veins stay dark however hard the site drives the emission."""
    rng = np.random.default_rng(9)
    yy, xx = np.mgrid[0:h, 0:w] / np.array([h, w])[:, None, None]
    glow = 0.82 + 0.1 * np.sin(2 * np.pi * (3 * xx + 0.3)) * np.sin(np.pi * 4 * yy) + 0.08 * np.sin(2 * np.pi * 7 * xx) \
        * np.cos(np.pi * 9 * yy)
    vein = np.zeros((h, w))

    def walk(x, y, ang, width, n):
        for i in range(n):
            ang += rng.normal(0, 0.28)
            x = (x + 1.6 * np.cos(ang)) % w
            y = y + 1.6 * np.sin(ang)
            if y < 0 or y >= h - 1:
                return
            r = max(0.6, width * (1 - i / n))
            x0, x1 = int(x - r - 1), int(x + r + 2)
            y0, y1 = max(0, int(y - r - 1)), min(h, int(y + r + 2))
            for yi in range(y0, y1):
                for xi in range(x0, x1):
                    d = np.hypot(xi - x, yi - y)
                    if d < r + 0.7:
                        vein[yi, xi % w] = max(vein[yi, xi % w], min(1.0, r + 0.7 - d))
            if width > 1.2 and rng.random() < 0.06:
                walk(x, y, ang + rng.choice((-1, 1)) * rng.uniform(0.5, 1.2), width * 0.6, int(n * 0.6))
    for _ in range(26):
        walk(rng.uniform(0, w), rng.uniform(2, 30), np.pi / 2 + rng.normal(0, 0.4), rng.uniform(2.2, 3.8), 150)
    for _ in range(28):
        walk(rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0, 2 * np.pi), rng.uniform(0.7, 1.2), 40)
    amber = np.stack([np.ones_like(glow) * 1.0, 0.36 * glow + 0.06, 0.05 * glow], -1) * glow[..., None]
    dark = np.array([0.22, 0.04, 0.025])
    rgb = amber * (1 - vein[..., None]) + dark * vein[..., None]
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = np.clip(rgb, 0, 1)
    im = bpy.data.images.new('City3HeartVeins', w, h, alpha=False)
    im.pixels.foreach_set(rgba[::-1].ravel())
    im.pack()
    return im


HEART_IMG = heart_texture()


# --- Materials ---------------------------------------------------------------------------------------------------------
def mix_rgba(nt, blend='MULTIPLY'):
    """A Mix node in RGBA mode and its colour sockets (A, B, Result): by name they'd be the float ones."""
    mx = nt.nodes.new('ShaderNodeMix')
    mx.data_type = 'RGBA'
    mx.blend_type = blend
    mx.inputs[0].default_value = 1.0
    a = next(i for i in mx.inputs if i.name == 'A' and i.type == 'RGBA')
    b = next(i for i in mx.inputs if i.name == 'B' and i.type == 'RGBA')
    out = next(o for o in mx.outputs if o.type == 'RGBA')
    return mx, a, b, out


def material(name, colour, roughness=0.5, metallic=0.0, emission=None, strength=0.0, coat=0.0, alpha=1.0, image=None,
             emission_image=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*colour, 1)
    p.inputs['Roughness'].default_value = roughness
    p.inputs['Metallic'].default_value = metallic
    if coat:
        p.inputs['Coat Weight'].default_value = coat
        p.inputs['Coat Roughness'].default_value = 0.08
    if alpha < 1:
        p.inputs['Alpha'].default_value = alpha
        if hasattr(m, 'surface_render_method'):
            m.surface_render_method = 'BLENDED'
    if emission:
        p.inputs['Emission Color'].default_value = (*emission, 1)
        p.inputs['Emission Strength'].default_value = strength
    if image is not None:
        # Base colour = the image x the colour (glTF: baseColorTexture x baseColorFactor).
        t = m.node_tree.nodes.new('ShaderNodeTexImage')
        t.image = image
        mix, ia, ib, io = mix_rgba(m.node_tree)
        m.node_tree.links.new(t.outputs['Color'], ia)
        ib.default_value = (*colour, 1)
        m.node_tree.links.new(io, p.inputs['Base Color'])
        if emission_image:
            # The emissive colour is the image itself (the veins dark in it): glTF emissiveTexture.
            m.node_tree.links.new(t.outputs['Color'], p.inputs['Emission Color'])
    return m


MAT = {
    'bone': material('City3Bone', (0.90, 0.80, 0.64), 0.66),
    'coral': material('City3Coral', (0.90, 0.22, 0.30), 0.8),
    'flesh': material('City3Flesh', (0.30, 0.03, 0.05), 0.35, coat=0.5),
    'stone': material('City3Stone', (0.84, 0.74, 0.64), 0.2, coat=0.35, image=STONE_IMG),
    'amber': material('City3Amber', (1.0, 0.42, 0.06), 0.4, emission=(1.0, 0.33, 0.02), strength=2.4),
    'heart': material('City3Heart', (1.0, 1.0, 1.0), 0.35, emission=(1.0, 1.0, 1.0), strength=3.2,
                      image=HEART_IMG, emission_image=True),
    'vein': material('City3Vein', (0.16, 0.03, 0.025), 0.45, coat=0.3),
    'ooze': material('City3Ooze', (0.006, 0.004, 0.005), 0.04, coat=1.0),
    'water': material('City3Water', (0.10, 0.065, 0.07), 0.03),
    'sun': material('City3Sun', (1.0, 0.85, 0.6), 1.0, emission=(1.0, 0.78, 0.5), strength=10.0),
    'lamp': material('City3Lamp', (1.0, 0.82, 0.55), 0.4, emission=(1.0, 0.62, 0.3), strength=3.0),
    'haze': material('City3Haze', (0.95, 0.62, 0.6), 1.0, alpha=0.22),
    'asphalt': material('City3Asphalt', (0.11, 0.105, 0.11), 0.85),
    'sand': material('City3Sand', (0.80, 0.58, 0.38), 0.95),
}


# --- Mesh helpers --------------------------------------------------------------------------------------------------------
TAG = [None]  # set while building something the arrival shot must not see (the leak sweep removes it if it shows)


def obj(name, me, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    if TAG[0]:
        o['approach_only'] = TAG[0]
    o.parent = parent or root
    o.location = loc
    o.rotation_euler = rot
    o.scale = scale if not isinstance(scale, (int, float)) else (scale,) * 3
    return o


def mesh_from(name, bm, mat, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return me


def lathe(bm, profile, seg=24, cx=0.0, cy=0.0, z0=0.0, cap_top=True, cap_bottom=True, wob=None):
    """Spin a (radius, z) profile about z. Profile runs bottom to top. wob(a, z) -> radius multiplier."""
    rings = []
    for r, z in profile:
        ring = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            rr = r * (wob(a, z) if wob else 1.0)
            ring.append(bm.verts.new((cx + rr * math.cos(a), cy + rr * math.sin(a), z0 + z)))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap_bottom and profile[0][0] > 1e-4:
        bm.faces.new(list(reversed(rings[0])))
    if cap_top and profile[-1][0] > 1e-4:
        bm.faces.new(rings[-1])
    return rings


def frames(path, up=Vector((0, 0, 1))):
    """Tangent, side, normal per point (side horizontal where it can be)."""
    out = []
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        u0 = up if abs(t.dot(up)) < 0.98 else Vector((1, 0, 0))
        side = t.cross(u0).normalized()
        nrm = side.cross(t).normalized()
        out.append((t, side, nrm))
    return out


def sweep(bm, path, profile, up=Vector((0, 0, 1)), caps=True, scales=None):
    """Extrude a 2-D (lateral, vertical) profile along a 3-D path (closed profile). scales: per-point profile scale."""
    rings = []
    for i, (p, (t, side, u)) in enumerate(zip(path, frames(path, up))):
        s = scales[i] if scales else 1.0
        rings.append([bm.verts.new(p + side * a * s + u * b * s) for a, b in profile])
    n = len(profile)
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if caps:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    return rings


def circle_profile(r, n=8):
    return [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def tube(bm, path, radii, seg=8, up=Vector((0, 0, 1)), caps=True):
    return sweep(bm, path, circle_profile(1.0, seg), up=up, caps=caps, scales=radii)


def rounded_rect_profile(w, h, r, n=3):
    """A closed (lateral, vertical) profile: a w x h rectangle with rounded corners, top at 0, bottom at -h."""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, -r, 0), (-w / 2 + r, -r, 90), (-w / 2 + r, -h + r, 180), (w / 2 - r, -h + r, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def polygon_slab(bm, outline, z_top, depth):
    top = [bm.verts.new((x, y, z_top)) for x, y in outline]
    bot = [bm.verts.new((x, y, z_top - depth)) for x, y in outline]
    bm.faces.new(top)
    bm.faces.new(list(reversed(bot)))
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))


def planar_uvs(me, scale=1 / 6):
    uv = me.uv_layers.new(name='UVMap')
    for loop in me.loops:
        co = me.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (co.x * scale, co.y * scale)


def oval_tube(bm, centres, axa, axb, ra, rb, seg=6, caps=True):
    """A tube along centres with an elliptic section: semi-axes ra[i] along axa[i], rb[i] along axb[i]."""
    rings = []
    for c, a, b, r1, r2 in zip(centres, axa, axb, ra, rb):
        rings.append([bm.verts.new(c + a * r1 * math.cos(2 * math.pi * k / seg) + b * r2 * math.sin(2 * math.pi * k / seg))
                      for k in range(seg)])
    for x, y in zip(rings, rings[1:]):
        for k in range(seg):
            j = (k + 1) % seg
            bm.faces.new((x[k], x[j], y[j], y[k]))
    if caps:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])


def bone_ladder(bm, pts, width, thick, plane_n=None, hole=None, flat=0.5, seg=6, taper=0.4, step=None, strut_seg=4):
    """Calcified bone with oval holes along it (the concept's ribs): two flattened rails either side of the curve in
    its own plane, joined by flattened struts; the holes between are long ovals. Wider and thicker at the feet.
    plane_n: the normal of the rib's plane (its thin direction); from the curve if None."""
    L = plen(pts)
    pts = resample(pts, step or max(0.02, L / 40))
    if plane_n is None:
        ch = pts[-1] - pts[0]
        mid = pts[len(pts) // 2] - (pts[0] + pts[-1]) / 2
        plane_n = ch.cross(mid if mid.length > 1e-6 else Vector((0, 0, 1)))
        if plane_n.length < 1e-6:
            plane_n = Vector((0, 1, 0))
        plane_n = plane_n.normalized()
    n = len(pts)
    acc = [0.0]
    for a, b in zip(pts, pts[1:]):
        acc.append(acc[-1] + (b - a).length)
    tg, inp, ws, th = [], [], [], []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        ip = plane_n.cross(t).normalized()
        u = acc[i] / max(L, 1e-6)
        k = 1 + taper * (1 - math.sin(math.pi * u))  # wider at the ends
        tg.append(t)
        inp.append(ip)
        ws.append(width * k * (1 + 0.08 * math.sin(i * 1.3)))
        th.append(thick * k)
    for side in (1, -1):
        rail = [p + ip * side * w / 2 for p, ip, w in zip(pts, inp, ws)]
        oval_tube(bm, rail, inp, [plane_n] * n, th, [x * flat for x in th], seg=seg)
    hole = hole or width * 1.7
    last = -hole * 0.5
    for i in range(1, n - 1):
        if acc[i] - last >= hole:
            last = acc[i]
            p, ip, w, t_ = pts[i], inp[i], ws[i], tg[i]
            cs = [p + ip * w / 2 * f for f in (1, 0.35, -0.35, -1)]
            oval_tube(bm, cs, [t_] * 4, [plane_n] * 4, [th[i] * x for x in (1.6, 1.0, 1.0, 1.6)],
                      [th[i] * flat * x for x in (1, 0.8, 0.8, 1)], seg=strut_seg)
    return plane_n


def wobble(bm, amp, freq=0.15, seed=0.0):
    """Organic lumps: push vertices along their normals by a smooth 3-D noise (sums of sines)."""
    bm.normal_update()
    for v in bm.verts:
        p = v.co * freq
        n = (math.sin(p.x * 1.7 + seed) * math.sin(p.y * 1.3 + 2.1 * seed) +
             math.sin(p.y * 2.3 + p.z * 1.1 + seed) * 0.6 + math.sin(p.z * 2.9 - p.x * 0.7) * 0.4)
        v.co += v.normal * amp * n


def resample(pts, step):
    out = [pts[0]]
    acc = 0.0
    for a, b in zip(pts, pts[1:]):
        seg = (b - a).length
        while acc + seg >= step:
            t = (step - acc) / seg
            a = a.lerp(b, t)
            out.append(a)
            seg = (b - a).length
            acc = 0.0
        acc += seg
    if (out[-1] - pts[-1]).length > step * 0.3:
        out.append(pts[-1])
    return out


def catmull(pts, n=6):
    """A smooth curve through the points (Catmull-Rom), n samples per span."""
    P = [pts[0] * 2 - pts[1]] + list(pts) + [pts[-1] * 2 - pts[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    out.append(pts[-1].copy())
    return out


# --- Instanced modules (one mesh, many objects: glb GPU instancing) --------------------------------------------------
def module_spire():
    """A gothic bone spire, height 1, base radius 1: a flared foot, ribbed collars, a long needle."""
    bm = bmesh.new()
    prof = [(1.0, 0.0), (0.72, 0.18), (0.78, 0.26), (0.5, 0.42), (0.6, 0.48), (0.36, 0.6), (0.4, 0.68), (0.2, 0.78),
            (0.06, 0.95), (0.0, 1.0)]
    lathe(bm, prof, seg=8, cap_top=False, wob=lambda a, z: 1 + 0.12 * math.sin(4 * a) * (1 - z))
    return mesh_from('City3.M.Spire', bm, MAT['bone'])


TOWER_PROF = [(0.75, 0.0), (0.95, 0.12), (1.0, 0.3), (0.82, 0.45), (0.92, 0.58), (0.8, 0.72), (0.62, 0.84),
              (0.42, 0.93), (0.18, 0.985), (0.0, 1.0)]


def tower_radius(f0, f1):
    """The tower module's widest radius (x its radius) between height fractions f0 and f1 (with its 7% wobble)."""
    zs, rs = [z for r, z in TOWER_PROF], [r for r, z in TOWER_PROF]
    fs = np.linspace(max(0.0, f0), min(1.0, f1), 9)
    return float(np.max(np.interp(fs, zs, rs))) * 1.07


def module_tower():
    """A hive tower body, height 1, radius 1: bulging, pinched, with a rounded crown."""
    bm = bmesh.new()
    prof = TOWER_PROF
    lathe(bm, prof, seg=12, cap_top=False, wob=lambda a, z: 1 + 0.07 * math.sin(3 * a + 6 * z))
    return mesh_from('City3.M.Tower', bm, MAT['bone'])


def hex_cells(w, h, cell):
    """Centres of a hex grid (pointy-top) filling a w x h rectangle (x across, z up, centred on x 0, from z 0)."""
    cs = []
    dx = cell * math.sqrt(3)
    dz = cell * 1.5
    for j in range(int(h / dz) + 1):
        z = cell + j * dz
        off = dx / 2 if j % 2 else 0.0
        for i in range(-int(w / dx) - 1, int(w / dx) + 2):
            x = i * dx + off
            if abs(x) + dx * 0.5 <= w / 2 + 1e-6 and z + cell <= h + 1e-6:
                cs.append((x, z))
    return cs


def lancet_inside(x, z, w, h):
    """Inside a pointed (lancet) window w wide, h tall: a rectangle below, two arcs meeting at the top."""
    spring = h - w * 0.95
    if z < spring:
        return abs(x) <= w / 2
    r = w * 0.95
    return math.hypot(abs(x) - (w / 2 - r), z - spring) <= r and z <= h


def module_hexwindow(w=1.0, h=1.7, cell=0.12, lancet=True):
    """A honeycomb window: a bone hex lattice (frame, slightly proud) over an amber glowing back. 1 wide, 1.7 tall,
    facing -Y (its front), base at z 0. Two meshes (frame, glow) for two materials; instance both with one transform."""
    fb, gb = bmesh.new(), bmesh.new()
    cells = [c for c in hex_cells(w, h, cell) if (not lancet or lancet_inside(c[0], c[1] + cell, w, h))
             and (not lancet or lancet_inside(c[0], c[1] - cell, w, h))]
    inset = 0.78
    for cx, cz in cells:
        outer, inner = [], []
        for k in range(6):
            a = math.radians(90 + 60 * k)
            outer.append(fb.verts.new((cx + cell * math.cos(a), -0.02, cz + cell * math.sin(a))))
            inner.append(fb.verts.new((cx + cell * inset * math.cos(a), -0.02, cz + cell * inset * math.sin(a))))
        for k in range(6):
            j = (k + 1) % 6
            fb.faces.new((outer[k], outer[j], inner[j], inner[k]))
        g = [gb.verts.new((cx + cell * inset * math.cos(math.radians(90 + 60 * k)), 0.015,
                           cz + cell * inset * math.sin(math.radians(90 + 60 * k)))) for k in range(6)]
        gb.faces.new(list(reversed(g)))
    # A bone surround: a thick rim round the window's outline.
    outline = []
    nk = 9 if cell < 0.2 else 5
    for k in range(nk):
        z = h * k / (nk - 1)
        xs = [x for x in [w / 2 * t / 20 for t in range(21)] if lancet_inside(x, z, w, h)] if lancet else [w / 2]
        outline.append((max(xs) if xs else 0.0, z))
    path = [Vector((x, -0.03, z)) for x, z in outline] + [Vector((-x, -0.03, z)) for x, z in reversed(outline)][1:]
    tube(fb, path, [min(cell, 0.12) * 0.8] * len(path), seg=4 if cell < 0.2 else 3, up=Vector((0, -1, 0)))
    return (mesh_from('City3.M.HexFrame', fb, MAT['bone'], smooth=False),
            mesh_from('City3.M.HexGlow', gb, MAT['amber'], smooth=False))


def branch(bm, p, d, length, r, depth, rng, tips):
    pts = [p]
    for k in range(1, 3):
        d = (d + Vector((rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25), rng.uniform(0.0, 0.2)))).normalized()
        pts.append(pts[-1] + d * length / 2)
    tube(bm, pts, [r, r * 0.85, r * 0.72], seg=4, caps=False)
    if depth == 0:
        tips.append((pts[-1], r * 1.25))
        return
    for _ in range(2 if depth < 2 else rng.choice((2, 3))):
        nd = (d + Vector((rng.uniform(-0.9, 0.9), rng.uniform(-0.9, 0.9), rng.uniform(0.1, 0.6)))).normalized()
        branch(bm, pts[-1], nd, length * 0.72, r * 0.72, depth - 1, rng, tips)


def module_coral(seed):
    """A branching coral, ~1 m tall at scale 1: tubes forking three times, knobbly tips."""
    rng = random.Random(seed)
    bm = bmesh.new()
    tips = []
    for _ in range(2):
        d = Vector((rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), 1)).normalized()
        branch(bm, Vector((rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05), 0)), d, 0.5, 0.06, 2, rng, tips)
    for p, r in tips:
        bmesh.ops.create_icosphere(bm, subdivisions=0, radius=r * 1.2, matrix=Matrix.Translation(p))
    return mesh_from(f'City3.M.Coral{seed}', bm, MAT['coral'])


def module_flesh(seed):
    """A porous lump of flesh-coral (radius ~1, flattened): a lumpy icosphere."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    rng = random.Random(seed)
    cs = [Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))).normalized() for _ in range(9)]
    for v in bm.verts:
        n = v.co.normalized()
        bump = sum(max(0.0, n.dot(c) - 0.55) for c in cs) * 0.9
        v.co = v.co * (0.75 + bump + 0.08 * math.sin(7 * n.x + seed) * math.sin(6 * n.y))
        v.co.z *= 0.65
    return mesh_from(f'City3.M.Flesh{seed}', bm, MAT['coral'])


def module_drip():
    """A hanging ooze strand, top at z 0, length 1 down, ending in a fat drop."""
    bm = bmesh.new()
    prof = [(0.0, -1.06), (0.55, -0.95), (0.2, -0.78), (0.22, -0.3), (0.55, 0.0)]
    lathe(bm, prof, seg=5, cap_top=True, cap_bottom=False)
    return mesh_from('City3.M.Drip', bm, MAT['ooze'])


def module_puddle():
    bm = bmesh.new()
    lathe(bm, [(1.0, 0.0), (0.9, 0.03), (0.5, 0.05), (0.0, 0.05)], seg=16, cap_top=False,
          wob=lambda a, z: 1 + 0.18 * math.sin(3 * a) + 0.08 * math.sin(7 * a))
    return mesh_from('City3.M.Puddle', bm, MAT['ooze'])


def module_rib():
    """A rib arch on a half-ellipse from (-1, 0, 0) over (0, 0, 1) to (1, 0, 0): flat calcified bone with oval holes,
    its thin side along y."""
    bm = bmesh.new()
    pts = [Vector((-math.cos(math.pi * k / 30), 0, math.sin(math.pi * k / 30))) for k in range(31)]
    bone_ladder(bm, pts, 0.1, 0.034, plane_n=Vector((0, 1, 0)), hole=0.2, flat=0.55, seg=4, step=0.15, strut_seg=3)
    return mesh_from('City3.M.Rib', bm, MAT['bone'])


def module_viaduct():
    """One span of an arched bone viaduct, 1 long (x 0 -> 1), deck top z 1: a pier at x 0, a pointed arch under the deck."""
    bm = bmesh.new()
    sweep(bm, [Vector((0, 0, 1)), Vector((1, 0, 1))], rounded_rect_profile(0.32, 0.1, 0.03), caps=True)
    # pier
    lathe(bm, [(0.06, -1.5), (0.05, 0.5), (0.08, 0.72), (0.12, 0.9)], seg=6, cx=0.0)
    # arch: from the pier at z 0.55 up to the deck at mid-span and down to the next pier
    pts = [Vector((t, 0, 0.55 + 0.4 * math.sin(math.pi * t) ** 0.6)) for t in [i / 8 for i in range(9)]]
    tube(bm, pts, [0.04] * len(pts), seg=4)
    return mesh_from('City3.M.Viaduct', bm, MAT['bone'])


def module_dome():
    """A honeycomb dome, radius 1: an amber glowing cap under a bone lattice (meridians and rings)."""
    gb = bmesh.new()
    bmesh.ops.create_uvsphere(gb, u_segments=12, v_segments=6, radius=0.97)
    for v in [v for v in gb.verts if v.co.z < -0.05]:
        gb.verts.remove(v)
    rb = bmesh.new()
    for k in range(6):
        a = 2 * math.pi * k / 6
        pts = [Vector((math.cos(a) * math.cos(t), math.sin(a) * math.cos(t), math.sin(t)))
               for t in [math.radians(x) for x in range(0, 91, 30)]]
        tube(rb, pts, [0.035] * len(pts), seg=3)
    for t in (0.0, 0.5):
        rr = math.cos(math.asin(t))
        pts = [Vector((rr * math.cos(a), rr * math.sin(a), t)) for a in [2 * math.pi * k / 16 for k in range(17)]]
        tube(rb, pts, [0.04] * len(pts), seg=3)
    return (mesh_from('City3.M.DomeGlow', gb, MAT['amber']), mesh_from('City3.M.DomeRib', rb, MAT['bone']))


def module_lantern():
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    return mesh_from('City3.M.Lantern', bm, MAT['lamp'])


def module_pod():
    """A bone pod (a small round building): a squat bulb with a ring of honeycomb glow round its waist."""
    bm = bmesh.new()
    lathe(bm, [(0.7, 0.0), (1.0, 0.3), (1.02, 0.5), (0.8, 0.8), (0.4, 0.96), (0.0, 1.0)], seg=12, cap_top=False)
    return mesh_from('City3.M.Pod', bm, MAT['bone'])


def module_drape(seed, mat, name, holes=0.32, arc=90.0, tongue=0.55):
    """A sheet draped round a cylinder (radius 1, z 0 -> 1, centred on +x, arc degrees round): its lower edge ragged
    and run down in tongues, holes eaten through it (flesh-coral webbing), or none (an ooze sheet: holes 0)."""
    rng = random.Random(seed)
    nu, nv = 10, 6
    bm = bmesh.new()
    low = [rng.uniform(0.0, tongue) for _ in range(nu + 1)]
    low = [(low[max(0, i - 1)] + 2 * low[i] + low[min(nu, i + 1)]) / 4 for i in range(nu + 1)]
    top = [1.0 - rng.uniform(0.0, 0.12) for _ in range(nu + 1)]
    grid = []
    for i in range(nu + 1):
        a = math.radians(-arc / 2 + arc * i / nu)
        col = []
        for j in range(nv + 1):
            v = j / nv
            z = (1 - v) * (-low[i]) + v * top[i]
            # lumpy: swelling out in the middle, pulled in to the body at the side edges (it grows from it)
            edge = math.sin(math.pi * i / nu)
            r = 1.02 + edge * (0.1 + 0.12 * (0.5 + 0.5 * math.sin(4 * a + 7 * v + seed)) * math.sin(math.pi * v) +
                               0.06 * (1 - v))
            col.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        grid.append(col)
    ph = rng.uniform(0, 6)
    for i in range(nu):
        for j in range(nv):
            u, v = (i + 0.5) / nu, (j + 0.5) / nv
            noise = math.sin(11 * u + ph) * math.sin(9 * v + 2 * ph) + 0.6 * math.sin(23 * u - 7 * v + ph)
            if holes and 0 < i < nu - 1 and 0 < j < nv - 1 and noise > 1.0 - holes * 2.2:
                continue
            bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
    loose = [v for v in bm.verts if not v.link_faces]
    for v in loose:
        bm.verts.remove(v)
    # Round the holes: every boundary vertex inside the sheet pulls toward the faces round it.
    bm.verts.ensure_lookup_table()
    for v in [v for v in bm.verts if v.is_boundary and 0 < len(v.link_faces) < 4]:
        fc = sum((f.calc_center_median() for f in v.link_faces), Vector()) / len(v.link_faces)
        if len(v.link_faces) in (2, 3):
            v.co = v.co.lerp(fc, 0.35)
    return mesh_from(name, bm, mat)


def module_web(seed):
    """A membrane slung between two supports: a sagging sheet x -1 -> 1, its top edge at z 1, holes through it."""
    rng = random.Random(seed)
    nu, nv = 12, 6
    bm = bmesh.new()
    grid = []
    for i in range(nu + 1):
        x = -1 + 2 * i / nu
        sag = 0.55 * (1 - x * x)
        col = []
        for j in range(nv + 1):
            v = j / nv
            z = 1 - v * (0.35 + sag * 0.6) - sag * 0.4 * v * v
            col.append(bm.verts.new((x, 0.06 * math.sin(4 * x + 3 * v + seed), z)))
        grid.append(col)
    ph = rng.uniform(0, 6)
    for i in range(nu):
        for j in range(nv):
            u, v = (i + 0.5) / nu, (j + 0.5) / nv
            if 0 < i < nu - 1 and j < nv - 1 and math.sin(13 * u + ph) * math.sin(11 * v + ph) > 0.45:
                continue
            bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    return mesh_from(f'City3.M.Web{seed}', bm, MAT['coral'])


def module_spire_lo():
    bm = bmesh.new()
    lathe(bm, [(1.0, 0.0), (0.62, 0.25), (0.5, 0.48), (0.3, 0.7), (0.12, 0.88), (0.0, 1.0)], seg=6, cap_top=False)
    return mesh_from('City3.M.SpireLo', bm, MAT['bone'])


def module_tower_lo():
    bm = bmesh.new()
    lathe(bm, [(0.8, 0.0), (1.0, 0.3), (0.85, 0.55), (0.75, 0.75), (0.4, 0.93), (0.0, 1.0)], seg=8, cap_top=False)
    return mesh_from('City3.M.TowerLo', bm, MAT['bone'])


def module_coral_lo(seed):
    rng = random.Random(seed)
    bm = bmesh.new()
    tips = []
    for _ in range(2):
        d = Vector((rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), 1)).normalized()
        branch(bm, Vector((0, 0, 0)), d, 0.6, 0.07, 1, rng, tips)
    for p_, r_ in tips:
        bmesh.ops.create_icosphere(bm, subdivisions=0, radius=r_ * 1.4, matrix=Matrix.Translation(p_))
    return mesh_from(f'City3.M.CoralLo{seed}', bm, MAT['coral'])


HEXF, HEXG = module_hexwindow()
HEXF_LO, HEXG_LO = module_hexwindow(cell=0.24)
HEXF_LO.name, HEXG_LO.name = 'City3.M.HexFrameLo', 'City3.M.HexGlowLo'
DOMEG, DOMER = module_dome()
M = {
    'spire': module_spire(), 'tower': module_tower(), 'hexf': HEXF, 'hexg': HEXG, 'hexflo': HEXF_LO,
    'hexglo': HEXG_LO, 'coral1': module_coral(1),
    'coral2': module_coral(2), 'flesh1': module_flesh(1), 'flesh2': module_flesh(2), 'drip': module_drip(),
    'puddle': module_puddle(), 'rib': module_rib(), 'viaduct': module_viaduct(), 'domeg': DOMEG, 'domer': DOMER,
    'lantern': module_lantern(), 'pod': module_pod(),
    'drapec': module_drape(3, MAT['coral'], 'City3.M.DrapeCoral'),
    'drapef': module_drape(4, MAT['flesh'], 'City3.M.DrapeFlesh', holes=0.28),
    'drapeo': module_drape(5, MAT['ooze'], 'City3.M.DrapeOoze', holes=0.0, arc=70.0, tongue=0.9),
    'web1': module_web(1), 'web2': module_web(2),
    'spirelo': module_spire_lo(), 'towerlo': module_tower_lo(), 'corallo1': module_coral_lo(5),
    'corallo2': module_coral_lo(6),
}
COUNT = {}


def inst(kind, loc, scale=1.0, rot_z=0.0, parent=None, rot=None):
    COUNT[kind] = COUNT.get(kind, 0) + 1
    return obj(f'City3.{kind.capitalize()}.{COUNT[kind]:04d}', M[kind], parent, loc,
               rot if rot else (0, 0, rot_z), scale)


def hexwindow(loc, width, yaw, parent, height=None, lo=False):
    """A honeycomb window `width` m wide facing yaw (radians: the direction its front faces), base at loc. lo: the
    coarse lattice (far, or in the hive's crowd)."""
    s = (width, width, height / 1.7 if height else width)
    r = (0, 0, yaw + math.pi / 2)  # the module faces -Y; turn it to face `yaw`
    inst('hexflo' if lo else 'hexf', loc, s, parent=parent, rot=r)
    inst('hexglo' if lo else 'hexg', loc, s, parent=parent, rot=r)


def coral(loc, size, parent, lo=False):
    k = rnd.choice(('corallo1', 'corallo2') if lo else ('coral1', 'coral2'))
    inst(k, loc, size, rot_z=rnd.random() * 6.28, parent=parent)


def drape(c, r, z0, h, yaw, parent, kind=None, ooze=True):
    """A sheet of flesh-coral webbing draped round a body of radius r centred at c (from z0, h tall), facing yaw;
    with an ooze sheet run down over it and strands off its ragged edge."""
    kind = kind or rnd.choice(('drapec', 'drapec', 'drapec', 'drapef'))
    inst(kind, (c.x, c.y, z0), (r, r, h), rot_z=yaw + rnd.uniform(-0.3, 0.3), parent=parent)
    if ooze:
        inst('drapeo', (c.x, c.y, z0 + h * rnd.uniform(0.1, 0.4)), (r * 1.02, r * 1.02, h * rnd.uniform(0.5, 0.9)),
             rot_z=yaw + rnd.uniform(-0.6, 0.6), parent=parent)
    for _ in range(3):
        a = yaw + rnd.uniform(-0.8, 0.8)
        p = Vector((c.x, c.y, z0 - h * rnd.uniform(0.1, 0.4))) + Vector((math.cos(a), math.sin(a), 0)) * r * 1.06
        inst('drip', p, (max(0.15, r * 0.035), max(0.15, r * 0.035), h * rnd.uniform(0.2, 0.6)), parent=parent)


def flesh(loc, size, parent, drips=4, flat=1.0, normal=None):
    """Flesh-coral webbing spread over a surface at loc (facing `normal`, horizontal): a holed sheet curved over it,
    one small lump at its heart, ooze dripping off its edge."""
    loc = Vector(loc)
    if normal is None:
        a = rnd.random() * 6.28
        normal = Vector((math.cos(a), math.sin(a), 0))
    nh = Vector((normal.x, normal.y, 0))
    nh = nh.normalized() if nh.length > 1e-6 else Vector((1, 0, 0))
    yaw = math.atan2(nh.y, nh.x)
    c = loc - nh * size * 1.1  # the sheet is a patch of a cylinder round a centre behind the surface
    inst(rnd.choice(('drapec', 'drapec', 'drapef')), (c.x, c.y, loc.z - size * 0.9), (size * 1.1, size * 1.1, size * 1.6),
         rot_z=yaw, parent=parent)
    if rnd.random() < 0.5:
        inst('drapeo', (c.x, c.y, loc.z - size * 0.5), (size * 1.14, size * 1.14, size * 1.2),
             rot_z=yaw + rnd.uniform(-0.4, 0.4), parent=parent)
    for _ in range(drips):
        a = rnd.random() * 6.28
        p = Vector(loc) + Vector((math.cos(a), math.sin(a), 0)) * size * rnd.uniform(0.4, 0.8)
        p.z -= size * 0.3 * flat
        inst('drip', p, (size * 0.12, size * 0.12, size * rnd.uniform(0.6, 2.2)), parent=parent)


# --- Groups ---------------------------------------------------------------------------------------------------------------
def group(name, parent=None):
    e = bpy.data.objects.new(name, None)
    scene.collection.objects.link(e)
    e.parent = parent or root
    return e


G = {k: group(f'City3.{k}') for k in ('Road', 'Causeway', 'Cathedral', 'Hive', 'Plaza', 'Ribcage', 'Heart', 'Exit',
                                      'Skyline', 'Sky', 'Mist')}


# =========================================================================================================================
# The roads: deck (polished stone slabs), low parapets with amber strips in their inner faces, piers down into the mist.
# Split into ~200 m pieces (the site merges by 260 m cells: each piece stays in its part of the city).
# =========================================================================================================================
STRIP_Z, STRIP_IN = 0.32, 0.55   # as art/align3/fit_camera.py
PARAPET_H, PARAPET_W = 0.62, 0.5


def deck_piece(path, name, parent, mat='stone', parapets=(True, True), piers=True, uv_v0=0.0, caps=False):
    """One piece of road along `path` (points on the centreline at z 0). (No end caps between pieces: they'd show.)"""
    bm = bmesh.new()
    rings = sweep(bm, path, rounded_rect_profile(ROAD_W, 1.4, 0.35, 1), caps=caps)
    me = mesh_from(name + 'Deck', bm, MAT[mat], smooth=False)
    # UVs: u across (1 tile = 6 m), v along.
    uv = me.uv_layers.new(name='UVMap')
    fr = frames(path)
    acc = [uv_v0]
    for a, b in zip(path, path[1:]):
        acc.append(acc[-1] + (b - a).length)
    # (Vertices are laid out ring by ring: ring i has len(profile) vertices.)
    npf = len(rings[0])
    for loop in me.loops:
        vi = loop.vertex_index
        ring = min(vi // npf, len(path) - 1)
        co = me.vertices[vi].co
        t, side, _ = fr[ring]
        uv.data[loop.index].uv = ((co - path[ring]).dot(side) / 6.0 + 0.5, acc[ring] / 6.0)
    o = obj(name + 'Deck', me, parent)
    for side, on in zip((1, -1), parapets):
        if not on:
            continue
        pts = [p + s * side * (ROAD_W / 2 - PARAPET_W / 2) + Vector((0, 0, PARAPET_H)) for p, (t, s, n) in
               zip(path, fr)]
        bm = bmesh.new()
        sweep(bm, pts, rounded_rect_profile(PARAPET_W, PARAPET_H + 0.1, 0.12, 1), caps=caps)
        obj(f'{name}Parapet{"L" if side < 0 else "R"}', mesh_from(name + 'Parapet', bm, MAT['stone'], smooth=True),
            parent)
        # The amber strip: segments 4 m lit, 1.2 m dark, set in the parapet's inner face (a box per segment).
        bm = bmesh.new()
        sp = [p + s * side * (ROAD_W / 2 - PARAPET_W - 0.005) + Vector((0, 0, STRIP_Z + 0.045)) for p, (t, s, n) in
              zip(path, fr)]
        dense = resample(sp, 1.0)
        for i in range(0, len(dense) - 5, 5):
            sweep(bm, [dense[i], dense[i + 2], dense[i + 4]], [(0.03, 0.0), (-0.03, 0.0), (-0.03, -0.09), (0.03, -0.09)])
        obj(f'{name}Strip{"L" if side < 0 else "R"}', mesh_from(name + 'Strip', bm, MAT['amber'], smooth=False),
            parent)
    if piers:
        for p in resample(path, 60.0)[1:-1]:
            bm = bmesh.new()
            lathe(bm, [(2.6, MIST_Z - 2), (2.2, -14), (2.6, -6), (4.2, -2.2), (5.4, -1.4)], seg=10, cx=p.x, cy=p.y,
                  cap_top=True, wob=lambda a, z: 1 + 0.08 * math.sin(4 * a + z * 0.2))
            obj(name + 'Pier', mesh_from(name + 'Pier', bm, MAT['bone']), parent)
    return o


def split_path(line, piece=200.0, step=6.0):
    """A centreline (every 2 m) cut into ~piece-m runs, each resampled every `step` m; returns (points, start s)."""
    out = []
    s0 = 0.0
    pts = resample_exact(line, step)
    n_per = int(piece / step)
    i = 0
    while i < len(pts) - 1:
        j = min(i + n_per, len(pts) - 1)
        out.append((pts[i:j + 1], i * step))
        i = j
    return out


IN_PIECES = split_path(ROAD_LINE)
S_PLAZA = ROAD_LEN - 150.0     # the in-road becomes plaza floor here (150 m short of the bike)
for k, (pts, s0) in enumerate(IN_PIECES):
    if s0 >= S_PLAZA:
        break
    if s0 + plen(pts) > S_PLAZA:
        pts = [p for p in pts if p.x <= BIKE_AT.x - 148.0]
    TAG[0] = None
    deck_piece(pts, f'City3.RoadIn{k:02d}', G['Road'], uv_v0=s0, piers=not (CATH_X - 5 < pts[0].x < NAVE_END))

# The exit road: over the slipway and the heart's island it's plaza floor; from the far moat on a deck again, the last
# 230 m cracked asphalt with sand drifting over it.
OUT_PIECES = split_path(OUT_LINE)
S_OUT_DECK = 106.0
S_ASPHALT = OUT_LEN - 280.0
for k, (pts, s0) in enumerate(OUT_PIECES):
    if s0 + plen(pts) <= S_OUT_DECK:
        continue
    pts = [p for p in pts if (p - BIKE_AT).length >= S_OUT_DECK or p.x > BIKE_AT.x + S_OUT_DECK]
    if len(pts) < 2:
        continue
    if s0 >= S_ASPHALT:
        deck_piece(pts, f'City3.RoadOut{k:02d}', G['Exit'], mat='asphalt', uv_v0=s0)
    elif s0 + plen(pts) > S_ASPHALT:
        cut = int((S_ASPHALT - s0) / 6.0)
        deck_piece(pts[:cut + 1], f'City3.RoadOut{k:02d}', G['Exit'], uv_v0=s0)
        deck_piece(pts[cut:], f'City3.RoadOut{k:02d}b', G['Exit'], mat='asphalt', uv_v0=S_ASPHALT)
    else:
        deck_piece(pts, f'City3.RoadOut{k:02d}', G['Exit'], uv_v0=s0)


def line_frame(line, s):
    i = max(0, min(int(s / 2.0), len(line) - 2))
    p, t = line[i], (line[i + 1] - line[i]).normalized()
    return p, t, Vector((-t.y, t.x, 0))  # point, tangent, left normal


def road_dist(c, lines=None):
    c = Vector((c.x, c.y, 0))
    best = 1e9
    for ln in lines or (ROAD_LINE, OUT_LINE):
        for q in ln[::3]:
            d = (c - q).length_squared
            if d < best:
                best = d
    return math.sqrt(best)


# =========================================================================================================================
# The plaza (composed in the arrival camera's screen space; positions in the bike's frame through B()).
# The bike stands at the moat's edge on a quay of polished stone; the moat rings the heart's island (IC, radius
# ISLAND_R to MOAT_R) and runs back west as a canal along the in-road's left. The kerb is the concept's: its amber strip
# traced off the concept and carried onto the floor (at the strip's height) through the fitted camera.
# =========================================================================================================================
IC = Vector((52.0, -5.0, 0))            # the heart's island centre (bike frame): the heart hangs over it
ISLAND_R, MOAT_R = 32.0, 51.0
PLAZA_R = 118.0
CANAL_W = 16.0
SLIP_W = 2.2                            # the slipway: the kerb drops flush where the bike's line crosses it
KERB_H, KERB_W, KERB_STRIP_Z = 0.3, 0.5, 0.15


def kerb_path():
    """The kerb's line (bike frame, on the floor, travelling with the water on its left): the canal's south bank from
    the west, the concept's traced curve in front of the bike, then round the moat's outer circle anticlockwise
    (south, east, north) to the canal's mouth. Returns (west, traced, circle, north bank back west)."""
    traced = [ARR.at_z(x, y, KERB_STRIP_Z) for x, y in FEAT['kerb']['points']]
    traced = [Vector((p.x, p.y, 0)) - Vector((BIKE_AT.x, BIKE_AT.y, 0)) for p in traced]
    # (The strip is in the kerb's road-side face: the kerb's centre line is half its width further out.)
    out = []
    for i, p in enumerate(traced):
        t = (traced[min(i + 1, len(traced) - 1)] - traced[max(i - 1, 0)]).normalized()
        out.append(p + Vector((-t.y, t.x, 0)) * KERB_W / 2)  # left of travel: toward the water
    traced = out
    p, d = traced[0].copy(), (traced[0] - traced[1]).normalized()
    west = []
    while p.x > -CANAL_END:
        ang = math.atan2(d.y, d.x)
        ang += max(-0.03, min(0.03, (math.pi - ang)))
        d = Vector((math.cos(ang), math.sin(ang), 0))
        p = p + d * 2.5
        west.append(p.copy())
    west = list(reversed(west))
    end = traced[-1]
    t_end = (traced[-1] - traced[-2]).normalized()
    a0 = math.atan2(end.y - IC.y, end.x - IC.x)
    step = math.radians(1.5)
    circ = []
    a = a0
    while a < a0 + math.radians(CANAL_MOUTH):
        a += step
        circ.append(IC + Vector((math.cos(a), math.sin(a), 0)) * MOAT_R)
    for k in range(6):  # blend from the traced curve's heading onto the circle
        w = 1 - (k + 1) / 7
        cont = end + t_end * (k + 1) * (MOAT_R * step)
        circ[k] = circ[k] * (1 - w) + cont * w
    # The canal's north bank: from the circle's end curving west, then due west, CANAL_W north of the south bank.
    q = circ[-1].copy()
    north = [q.copy()]
    while q.x > -CANAL_END:
        target_y = max(west[0].y, 2.6) + CANAL_W
        q = q + Vector((-3.0, (target_y - q.y) * 0.08, 0))
        north.append(q.copy())
    return west, traced, circ, north


CANAL_END = 148.0     # the canal (and the plaza) reach this far back west along the in-road (bike frame -x)
CANAL_MOUTH = 318.0   # degrees of moat circle the kerb runs round before the canal's north bank
K_WEST, K_TRACED, K_CIRC, K_NORTH = kerb_path()
KERB = K_WEST + K_TRACED + K_CIRC


def kerb_pieces():
    """The kerb, with the slipway gap where the bike's line crosses it and the exit bridge's on the far side."""
    pieces, cur = [], []
    for p in KERB:
        gap = abs(p.y) < SLIP_W / 2 and -1 < p.x < 4
        gap |= abs(p.y) < ROAD_W / 2 + 0.5 and p.x > IC.x + 20  # the far side: the exit bridge
        if gap:
            if len(cur) > 1:
                pieces.append(cur)
            cur = []
        else:
            cur.append(p)
    if len(cur) > 1:
        pieces.append(cur)
    pieces.append(K_NORTH)
    pieces.append([K_NORTH[-1], K_WEST[0]])  # across the canal's west end
    return pieces


def build_kerb():
    bm, sb, cb = bmesh.new(), bmesh.new(), []
    for pc in kerb_pieces():
        # (Fine where the arrival camera looks closely, coarse elsewhere.)
        dense = []
        for a, b in zip(pc, pc[1:]):
            near = (a - Vector((0, 0, 0))).length < 25
            n = max(1, int((b - a).length / (0.25 if near else 2.0)))
            dense += [a.lerp(b, i / n) for i in range(n)]
        dense.append(pc[-1])
        pts = [B(p.x, p.y, KERB_H) for p in dense]
        sweep(bm, pts, rounded_rect_profile(KERB_W, KERB_H + 0.25, 0.06, 2))
        if pc is K_NORTH or len(pc) == 2:
            continue
        # The strip in the road-side face (right of travel = away from the water), centred at KERB_STRIP_Z.
        fr = frames(pts)
        sp = [p + s * (KERB_W / 2 + 0.004) + Vector((0, 0, KERB_STRIP_Z + 0.035 - KERB_H)) for p, (t, s, n) in
              zip(pts, fr)]
        L, run = 0.0, []
        for a, b in zip(sp, sp[1:]):
            L += (b - a).length
            if L % 3.4 < 2.7:
                run.append(a)
            elif len(run) > 1:
                sweep(sb, run, rounded_rect_profile(0.05, 0.07, 0.015, 1))
                run = []
            else:
                run = []
        if len(run) > 1:
            sweep(sb, run, rounded_rect_profile(0.05, 0.07, 0.015, 1))
        cb.append((pts[0], pts[-1]))
    obj('City3.Kerb', mesh_from('City3.Kerb', bm, MAT['bone']), G['Plaza'])
    obj('City3.KerbStrip', mesh_from('City3.KerbStrip', sb, MAT['amber'], smooth=False), G['Plaza'])


build_kerb()


def prism(name, outline, z_top, depth):
    bm = bmesh.new()
    polygon_slab(bm, outline, z_top, depth)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    return o


def boolean_cut(target, cutters):
    for c in cutters:
        mod = target.modifiers.new('cut', 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.solver = 'EXACT'
        mod.object = c
        bpy.context.view_layer.objects.active = target
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for c in cutters:
        bpy.data.objects.remove(c, do_unlink=True)


# The water's outline (bike frame): the canal's south bank, the traced kerb, round the moat, back along the north bank.
WATER_OUT = K_WEST + K_TRACED + K_CIRC + K_NORTH[1:]
WATER_OUT = [q for i, q in enumerate(WATER_OUT) if i == 0 or (q - WATER_OUT[i - 1]).length > 0.15]
# The quay: one stone slab round it all (a disc round the island and the plaza's west arm along the in-road) with the
# water and the exit road's deck cut out of it. Top z 0.
outline = []
for k in range(73):
    a = math.radians(5 * k)
    q = IC + Vector((math.cos(a), math.sin(a), 0)) * PLAZA_R
    outline.append(q)
ang_w = [q for q in outline if q.x < IC.x - PLAZA_R * 0.6]
disc = [(B(q.x, q.y).x, B(q.x, q.y).y) for q in outline[:-1]]
floor = prism('City3.PlazaFloor', disc, 0.0, 1.2)
arm = prism('arm', [(B(-CANAL_END, -40).x, B(0, -40).y), (B(IC.x - 60, 0).x, B(0, -40).y),
                    (B(IC.x - 60, 0).x, B(0, 60).y), (B(-CANAL_END, 0).x, B(0, 60).y)], 0.0, 1.2)
mod = floor.modifiers.new('arm', 'BOOLEAN')
mod.operation = 'UNION'
mod.solver = 'EXACT'
mod.object = arm
bpy.context.view_layer.objects.active = floor
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(arm, do_unlink=True)
water_cut = prism('wcut', [(B(q.x, q.y).x, B(q.x, q.y).y) for q in WATER_OUT], 1.0, 3.0)
deck_fp = []
for s_ in np.arange(S_OUT_DECK - 2, 200.0, 4.0):
    p_, t_, n_ = line_frame(OUT_LINE, s_)
    deck_fp.append((p_, n_))
deck_cut = prism('dcut', [((p_ + n_ * (ROAD_W / 2 + 0.05)).x, (p_ + n_ * (ROAD_W / 2 + 0.05)).y) for p_, n_ in deck_fp]
                 + [((p_ - n_ * (ROAD_W / 2 + 0.05)).x, (p_ - n_ * (ROAD_W / 2 + 0.05)).y)
                    for p_, n_ in reversed(deck_fp)], 1.0, 3.0)
boolean_cut(floor, [water_cut, deck_cut])
floor.parent = G['Plaza']
floor.data.materials.clear()
floor.data.materials.append(MAT['stone'])
for poly in floor.data.polygons:
    poly.material_index = 0
planar_uvs(floor.data)
floor.data.name = 'City3.PlazaFloor'

# The island: a stone disc with a low lip, top z 0.
bm = bmesh.new()
lathe(bm, [(ISLAND_R + 0.6, -1.5), (ISLAND_R + 0.6, 0.25), (ISLAND_R, 0.3), (ISLAND_R - 0.4, 0.0), (0.0, 0.0)], seg=72,
      cx=B(IC.x, IC.y).x, cy=B(IC.x, IC.y).y)
me = mesh_from('City3.Island', bm, MAT['stone'])
planar_uvs(me)
obj('City3.Island', me, G['Plaza'])
# The water: one sheet just under the floor's top, under the moat and the canal (the floor and island cover the rest).
bm = bmesh.new()
polygon_slab(bm, [(B(q.x, q.y).x, B(q.x, q.y).y) for q in WATER_OUT], WATER_Z, 0.05)
me = mesh_from('City3.Water', bm, MAT['water'], smooth=False)
planar_uvs(me, 0.05)
obj('City3.Water', me, G['Plaza'])
wc = B(IC.x, IC.y)
# The moat's floor (dark), and the ford: the slipway's slab just under the water, bike line, kerb to island.
bm = bmesh.new()
lathe(bm, [(MOAT_R + 3, -1.6), (0.0, -1.6)], seg=48, cx=wc.x, cy=wc.y, cap_top=False, cap_bottom=False)
obj('City3.MoatFloor', mesh_from('City3.MoatFloor', bm, MAT['ooze']), G['Plaza'])
bm = bmesh.new()
f0, f1 = B(0.0, 0), B(IC.x - ISLAND_R + 1, 0)
polygon_slab(bm, [(f0.x, -SLIP_W / 2), (f1.x, -SLIP_W / 2), (f1.x, SLIP_W / 2), (f0.x, SLIP_W / 2)], WATER_Z - 0.03, 1.4)
obj('City3.Ford', mesh_from('City3.Ford', bm, MAT['stone'], smooth=False), G['Plaza'])
# The far moat's bridge (the exit): a low stone deck from the island to the quay.
bm = bmesh.new()
x0, x1 = B(IC.x + ISLAND_R - 2, 0).x, B(IC.x + MOAT_R + 3, 0).x
pts = [Vector((x, 0, 0)) for x in np.linspace(x0, x1, 12)]
sweep(bm, pts, rounded_rect_profile(ROAD_W, 1.0, 0.3))
obj('City3.ExitBridge', mesh_from('City3.ExitBridge', bm, MAT['stone'], smooth=False), G['Plaza'])

# =========================================================================================================================
# The heart: an organic heart (City3Heart, emissive amber, origin at its centre), veins over it (City3Vein, children so
# they pulse with it), vessel stumps on top, tendons up to the ribs, ooze dripping off its underside.
# =========================================================================================================================
HD = 60.0
hf = FEAT['heart']
HEART_C = ARR.point(hf['cx'], hf['cy'], HD)
HEART_RX = ARR.m(hf['half_w'], HD)
HEART_RZ = ARR.m(hf['half_h'], HD)


def heart_mesh():
    bm = bmesh.new()
    bm.loops.layers.uv.new('UVMap')  # (calc_uvs writes into the active UV layer: there must be one)
    bmesh.ops.create_uvsphere(bm, u_segments=36, v_segments=24, radius=1.0, calc_uvs=True)
    for v in bm.verts:
        n = v.co.copy()
        # A heart: fuller up top on the left (the atria), tapering to an apex below, right of centre.
        lobe = 0.14 * max(0.0, n.dot(Vector((-0.5, 0.3, 0.8)).normalized())) ** 2
        apex = -0.3 * max(0.0, -n.z) ** 2.5
        bulge = 0.06 * math.sin(5 * n.x + 2) * math.sin(4 * n.y) + 0.04 * math.sin(9 * n.z)
        r = 1 + lobe + bulge
        v.co = Vector((n.x * r + apex * 0.25, n.y * r * 0.82, n.z * r * (1.0 + 0.1 * (n.z < 0))))
    bmesh.ops.scale(bm, vec=(HEART_RX * 0.85, HEART_RX / 0.82, HEART_RZ / 1.05), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(-12), 3, 'Y'))
    return bm


bm = heart_mesh()
me = mesh_from('City3Heart', bm, MAT['heart'])
heart = obj('City3Heart', me, G['Heart'], HEART_C)
heart['note'] = 'pulsed by the site: origin at its centre'
# Veins: branching tubes over the surface (in the heart's local frame), a bit proud of it.
dg_bm = bmesh.new()
dg_bm.from_mesh(me)
bvh_verts = [v.co.copy() for v in dg_bm.verts]
dg_bm.free()


def on_heart(d):
    """The heart's surface point (local) in direction d (nearest vertex direction, pushed out a touch)."""
    d = d.normalized()
    best = max(bvh_verts, key=lambda v: v.normalized().dot(d))
    return best * 1.015


vb = bmesh.new()
vr = random.Random(5)
for k in range(9):
    # trunks from the top down over the front (toward the arrival camera, -y... the heart's local -x side faces it)
    d = Vector((vr.uniform(-1, -0.1), vr.uniform(-1, 1), vr.uniform(0.3, 1.0)))
    pts = []
    for s in range(10):
        pts.append(on_heart(d))
        d = d + Vector((vr.uniform(-0.2, 0.2), vr.uniform(-0.2, 0.2), -0.24))
    pts = catmull(pts, 3)
    tube(vb, pts, [0.42 * (1 - s / (len(pts) + 1)) * HEART_RX / 11 for s in range(len(pts))], seg=5)
    for b_ in range(0):  # a branch off it
        i0 = vr.randrange(2, 6)
        d2 = (pts[i0].normalized() + Vector((vr.uniform(-0.5, 0.5), vr.uniform(-0.5, 0.5), -0.2)))
        bp = [pts[i0]]
        for s in range(5):
            d2 = d2 + Vector((vr.uniform(-0.25, 0.25), vr.uniform(-0.25, 0.25), -0.15))
            bp.append(on_heart(d2))
        tube(vb, bp, [0.3 * (1 - s / 6) * HEART_RX / 11 for s in range(len(bp))], seg=4)
obj('City3.HeartVeins', mesh_from('City3.HeartVeins', vb, MAT['vein']), heart)
# Vessel stumps on top (aorta and kin), children of the heart too.
sb = bmesh.new()
for dx, dy, r, h in ((-0.25, 0.0, 0.22, 0.55), (0.15, 0.1, 0.18, 0.5), (0.35, -0.15, 0.12, 0.4), (-0.05, -0.3, 0.1, 0.45)):
    base = on_heart(Vector((dx, dy, 1)))
    pts = [base - Vector((0, 0, 0.5))] + [base + Vector((dx * 2 * t, dy * t, h * HEART_RZ * t)) for t in (0.3, 0.7, 1.0)]
    tube(sb, pts, [r * HEART_RX] * 4, seg=10)
obj('City3.HeartVessels', mesh_from('City3.HeartVessels', sb, MAT['vein']), heart)

# =========================================================================================================================
# The ribcage: the concept's ribs (traced polylines) set in vertical planes facing the camera at chosen depths; the
# traced part fixes the shape on screen, the feet run on down to the water. The front arch is perforated (two rails and
# struts, as the concept's oval-holed bone); the others are solid tapering bone.
# =========================================================================================================================
fwd_h = Vector((ARR.fwd.x, ARR.fwd.y, 0)).normalized()


def rib_curve(trace_pts, depth, extend_feet=True):
    p0 = ARR.eye + fwd_h * depth
    pts = [ARR.on_plane(x, y, p0, fwd_h) for x, y in trace_pts]
    pts = catmull(pts, 4)
    if extend_feet:
        for end in (0, -1):
            a = pts[end]
            b = pts[1 if end == 0 else -2]
            d = (a - b).normalized()
            foot = []
            q = a.copy()
            while q.z > WATER_Z - 0.5 and len(foot) < 40:
                d = (d + Vector((0, 0, -0.35))).normalized()
                q = q + d * 1.5
                foot.append(q.copy())
            if end == 0:
                pts = list(reversed(foot)) + pts
            else:
                pts = pts + foot
    return pts


def solid_rib(name, pts, r0, r1, parent, mat='bone', solid=False, plane_n=None):
    """A rib: flat bone with oval holes (bone_ladder), r0 at the feet, r1 at the crown as its half width; solid: a
    round tapering trunk instead (roots, trunks, the spine)."""
    if not solid:
        bm = bmesh.new()
        L = plen(pts)
        bone_ladder(bm, pts, (r0 + r1), (r0 + r1) * 0.34, plane_n=plane_n if plane_n is not None else fwd_h,
                    hole=(r0 + r1) * 1.5, flat=0.55, seg=6, taper=max(0.0, r0 / max(r1, 1e-6) - 1), step=max(0.5, L / 70))
        wobble(bm, r1 * 0.06, 0.4)
        return obj(name, mesh_from(name, bm, MAT[mat]), parent)
    n = len(pts)
    rs = []
    for i in range(n):
        t = i / (n - 1)
        mid = math.sin(math.pi * t)
        rs.append((r0 * (1 - mid) + r1 * mid) * (1 + 0.12 * math.sin(i * 1.7)))
    bm = bmesh.new()
    tube(bm, pts, rs, seg=10, up=fwd_h)
    wobble(bm, r1 * 0.12, 0.4)
    return obj(name, mesh_from(name, bm, MAT[mat]), parent)


RIBS = FEAT['ribs']
RIB_DEPTH = {'front_arch': 45.0, 'right_arch': 50.0, 'heart_rib_l': 55.0}
ribs_built = {}
fa = rib_curve(RIBS['front_arch']['points'], RIB_DEPTH['front_arch'])
w_fa = ARR.m(RIBS['front_arch']['half_w'] * 2, RIB_DEPTH['front_arch'])
bm = bmesh.new()
bone_ladder(bm, fa, w_fa * 0.8, w_fa * 0.27, plane_n=fwd_h, hole=w_fa * 1.25, flat=0.5, seg=7, taper=0.35, step=0.6)
wobble(bm, w_fa * 0.03, 0.5)
ribs_built['front_arch'] = obj('City3.RibFront', mesh_from('City3.RibFront', bm, MAT['bone']), G['Ribcage'])
# The right arch: traced on its right half; mirrored about the heart to close it over the top.
ra = RIBS['right_arch']['points']
ra_full = [(2 * hf['cx'] - x, y) for x, y in reversed(ra)][:-1] + ra
ra_full = [(x, y) for x, y in ra_full]
w_ra = ARR.m(RIBS['right_arch']['half_w'] * 2, RIB_DEPTH['right_arch'])
ribs_built['right_arch'] = solid_rib('City3.RibBack', rib_curve(ra_full, RIB_DEPTH['right_arch']), w_ra * 0.65,
                                     w_ra * 0.45, G['Ribcage'])
hr = RIBS['heart_rib_l']['points']
hr_full = hr + [(2 * hf['cx'] - x, y) for x, y in reversed(hr)][1:]
w_hr = ARR.m(RIBS['heart_rib_l']['half_w'] * 2, RIB_DEPTH['heart_rib_l'])
ribs_built['heart_rib_l'] = solid_rib('City3.RibInner', rib_curve(hr_full, RIB_DEPTH['heart_rib_l']), w_hr * 0.6,
                                      w_hr * 0.4, G['Ribcage'])
# More ribs round the heart (not traced: the cage's depth), each an arch over the island, turned round its centre.
icw = B(IC.x, IC.y)
for k, (ang, span, h, r) in enumerate(((60, 30, 46, 1.4), (95, 31, 48, 1.3), (125, 29, 44, 1.2))):
    a = math.radians(ang)
    d = Vector((math.cos(a), math.sin(a), 0))
    cc = icw + Vector((16.0, 0, 0))  # (behind the heart: the traced ribs stay in front)
    pts = [cc + d * span * math.cos(t) + Vector((0, 0, h * math.sin(t) ** 0.8)) for t in
           [math.pi * i / 30 for i in range(31)]]
    pts = [p + Vector((0, 0, WATER_Z)) for p in pts]
    solid_rib(f'City3.RibCage{k}', pts, r * 1.6, r, G['Ribcage'], plane_n=Vector((-d.y, d.x, 0)))
# A spine along the cage's top, front to back.
sp = [icw + Vector((x, 0.0, 47 + 3 * math.cos(x / 14))) for x in np.linspace(-26, 30, 16)]
solid_rib('City3.RibSpine', sp, 1.0, 1.5, G['Ribcage'], solid=True)
# Tendons: the heart hung from the cage (flesh), from points over it up to the spine and the front arch.
tb = bmesh.new()
for dx, dy in ((-0.5, 0.2), (0.4, -0.2), (0.0, 0.5), (0.2, 0.4), (-0.3, -0.4)):
    top = HEART_C + Vector((dx * HEART_RX * 0.8, dy * HEART_RX * 0.8, HEART_RZ * 0.85))
    up = Vector((icw.x + dx * 18 + rnd.uniform(-4, 4), icw.y + dy * 14, 46.0))
    pts = [top + (up - top) * t + Vector((0, 0, -3 * math.sin(math.pi * t))) for t in np.linspace(0, 1, 9)]
    tube(tb, pts, [0.6, 0.55, 0.45, 0.4, 0.38, 0.4, 0.45, 0.55, 0.7], seg=6)
obj('City3.HeartTendons', mesh_from('City3.HeartTendons', tb, MAT['flesh']), G['Heart'])
# Ooze off the heart's underside and the front arch.
for k in range(14):
    a = rnd.uniform(0, 6.28)
    p = HEART_C + Vector((math.cos(a) * HEART_RX * rnd.uniform(0.2, 0.75), math.sin(a) * HEART_RX * 0.6,
                          -HEART_RZ * rnd.uniform(0.6, 0.85)))
    inst('drip', p, (0.45, 0.45, rnd.uniform(2, 9)), parent=G['Heart'])
for k in range(40):
    p = fa[rnd.randrange(len(fa) // 6, len(fa) * 5 // 6)]
    if p.z > 8:
        inst('drip', p - Vector((0, 0, w_fa * 0.3)), (0.3, 0.3, rnd.uniform(1.5, 9)), parent=G['Ribcage'])

# =========================================================================================================================
# The platforms: two round slabs on ooze legs (the concept's dripping tables), their tops traced.
# =========================================================================================================================
PLAT_DEPTH = {'upper': 38.0, 'lower': 48.0}
plats = {}
for nm, pl in FEAT['platforms'].items():
    d = PLAT_DEPTH[nm]
    c = ARR.point(pl['cx'], pl['cy'], d) - Vector((0, 0, 1.3))  # (seen from below: its rim, not its top, is traced)
    r = ARR.m(pl['half_w'], d)
    bm = bmesh.new()
    lathe(bm, [(r * 0.75, -1.4), (r * 0.97, -0.9), (r, -0.3), (r * 0.98, 0.0), (r * 0.9, 0.12), (0.0, 0.15)], seg=36,
          cx=c.x, cy=c.y, z0=c.z, wob=lambda a, z: 1 + 0.03 * math.sin(4 * a))
    plats[nm] = obj(f'City3.Platform{nm.capitalize()}', mesh_from(f'City3.Platform{nm.capitalize()}', bm,
                                                                    MAT['bone']), G['Plaza'])
    plats[nm]['centre'] = list(c)
    # Ooze sheets over the rim.
    for k in range(10):
        a = rnd.uniform(0, 6.28)
        q = c + Vector((math.cos(a), math.sin(a), 0)) * r * 0.97
        inst('drip', q - Vector((0, 0, 0.6)), (0.35, 0.35, rnd.uniform(1.0, 4.0)), parent=G['Plaza'])
# The legs: ooze columns where the concept has them (traced x at the platform's depth), thick at the top, pooling.
for dr in FEAT['drips']:
    (x0, y0), (x1, y1) = dr
    nm = 'upper' if y0 < 345 else 'lower'
    d = PLAT_DEPTH[nm]
    top = ARR.point(x0, y0, d)
    bot = ARR.at_z(x1, y1, 0.0)
    bot = ARR.eye + (bot - ARR.eye) * (d / ARR.depth(bot))  # same depth as the top: a vertical leg
    bot.z = WATER_Z
    dy = top.y - BIKE_AT.y
    if abs(dy) < 4.5:  # keep the ride's line (y 0) clear: a leg stands at least 4.5 m off it
        top.y = bot.y = BIKE_AT.y + math.copysign(4.5, dy)
    ok = abs(top.y - BIKE_AT.y) > 3.0
    pts = [top.lerp(Vector((top.x, top.y, bot.z)), t) for t in np.linspace(0, 1, 10)]
    bm = bmesh.new()
    tube(bm, pts, [1.3, 0.8, 0.55, 0.48, 0.45, 0.45, 0.5, 0.6, 0.9, 1.5], seg=10)
    wobble(bm, 0.1, 0.8)
    obj('City3.OozeLeg', mesh_from('City3.OozeLeg', bm, MAT['ooze']), G['Plaza'])
    inst('puddle', (bot.x, bot.y, WATER_Z), (2.4, 2.0, 1.0), rot_z=rnd.random() * 3, parent=G['Plaza'])
    print('leg', nm, [round(v, 1) for v in top - BIKE_AT], 'clear of the bike line' if ok else 'ON THE BIKE LINE')

# =========================================================================================================================
# The ooze mounds in the moat (the concept's black slicks with red eyes, x 200-560): low glossy humps in the water.
# =========================================================================================================================
for sx, sy, d, rx, ry, h in ((330, 452, 24.0, 7.5, 5.0, 1.6), (500, 492, 19.0, 6.0, 2.8, 1.0),
                             (250, 540, 9.0, 2.6, 1.6, 0.55), (430, 548, 8.5, 1.4, 1.0, 0.3),
                             (530, 505, 16.0, 2.0, 1.2, 0.4)):
    p = ARR.at_z(sx, sy, WATER_Z)
    p = ARR.eye + (p - ARR.eye) * (d / ARR.depth(p))
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=18, v_segments=8, radius=1.0)
    for v in bm.verts:
        v.co.z = max(v.co.z, 0) * (1 + 0.2 * math.sin(3 * v.co.x))
        v.co.x *= 1 + 0.15 * math.sin(4 * v.co.y)
    bmesh.ops.scale(bm, vec=(rx, ry, h), verts=bm.verts)
    obj('City3.OozeMound', mesh_from('City3.OozeMound', bm, MAT['ooze']), G['Plaza'], (p.x, p.y, WATER_Z))

# =========================================================================================================================
# The left foreground: a huge bone root at the canal's mouth, black ooze pouring off it into the water, coral round its
# foot (the concept's x 0-150).
# =========================================================================================================================
lt = RIBS['left_trunk']['points']
TRUNK_D = 9.0
p0 = ARR.eye + fwd_h * TRUNK_D
tpts = [ARR.on_plane(x, y, p0, fwd_h) for x, y in lt]
tpts = [Vector((p.x, p.y, max(p.z, WATER_Z - 0.5))) for p in tpts]
# Keep the trunk off the bike's line and on the water side of the kerb; its top curls back over the canal.
tpts = catmull(tpts, 4)
top = tpts[-1]
for k in range(8):
    top = top + Vector((-1.2, 0.8, 0.6))
    tpts.append(top.copy())
tw = ARR.m(RIBS['left_trunk']['half_w'], TRUNK_D)
solid_rib('City3.LeftRoot', tpts, tw * 1.25, tw * 0.95, G['Plaza'], solid=True)
for k in range(6):  # ooze pouring down it
    i = rnd.randrange(3, len(tpts) // 2)
    q = tpts[i] + (ARR.eye - tpts[i]).normalized() * tw * 0.9
    q = Vector((q.x, q.y, q.z))
    inst('drip', q, (0.3, 0.3, max(1.0, q.z - WATER_Z)), parent=G['Plaza'])
pour = [tpts[6] + (ARR.eye - tpts[6]).normalized() * tw * 0.8]
for k in range(10):
    q = pour[-1] + Vector((0.25, -0.15, -0.7))
    pour.append(Vector((q.x, q.y, max(q.z, WATER_Z))))
bm = bmesh.new()
tube(bm, pour, [0.35 + 0.08 * k for k in range(len(pour))], seg=8)
obj('City3.OozePour', mesh_from('City3.OozePour', bm, MAT['ooze']), G['Plaza'])
inst('puddle', (pour[-1].x, pour[-1].y, WATER_Z), (3.0, 2.2, 3.0), parent=G['Plaza'])
for sx, sy, d, s in ((40, 560, 4.2, 0.9), (100, 520, 5.0, 1.1), (20, 470, 6.5, 1.4), (150, 610, 3.6, 0.6),
                     (60, 640, 3.0, 0.7), (130, 480, 6.0, 0.9), (1265, 470, 6.0, 0.9), (1240, 500, 5.5, 0.6)):
    p = ARR.at_z(sx, sy, 0.0)
    p = ARR.eye + (p - ARR.eye) * (d / ARR.depth(p))
    coral((p.x, p.y, WATER_Z if (p - B(0, 0)).y > 2 else 0.0), s * 1.6, G['Plaza'])

# =========================================================================================================================
# Honeycomb towers either side (the concept's lit hex windows): bone bodies with lancet hex windows facing the camera.
# =========================================================================================================================


def ledge_ooze(view, box, n, parent, length=(1.5, 9.0), width=0.25, step=9, max_depth=600.0):
    """Black ooze hanging off bone ledges: rays from `view` over the screen box (x0, y0, x1, y1); where one meets bone
    facing up (a ledge, a sill, the top of a rib), a strand hangs from it, its width scaled with distance."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    x0, y0, x1, y1 = box
    hits = []
    for sy in range(int(y0), int(y1), step):
        for sx in range(int(x0), int(x1), step):
            hit, loc, nrm, idx, ob, mx = scene.ray_cast(dg, view.eye, view.ray(sx, sy).normalized(), distance=max_depth)
            if hit and nrm.z > 0.35 and ob.type == 'MESH' and ob.data.materials and \
                    ob.data.materials[0].name == 'City3Bone' and road_dist(loc) > ROAD_W / 2 + 2.5:
                hits.append(loc)
    rnd.shuffle(hits)
    for loc in hits[:n]:
        d = max(1.0, view.depth(loc))
        w = width * max(1.0, d / 25)
        inst('drip', loc + Vector((0, 0, 0.1)), (w, w, rnd.uniform(*length) * max(1.0, d / 40)), parent=parent)
    return len(hits[:n])


def facing(p):
    v = ARR.eye - p
    return math.atan2(v.y, v.x)


def tower(c, r, h, parent, windows=(), spire=True, base=MIST_Z, lo=False, body_lo=False):
    inst('towerlo' if body_lo else 'tower', (c.x, c.y, base), (r, r, h - base), rot_z=rnd.random() * 6.28, parent=parent)
    if spire:
        inst('spire', (c.x, c.y, h - (h - base) * 0.05), (r * 0.45, r * 0.45, h * 0.6), parent=parent)
    for (z0, z1, w, yaw) in windows:
        rr = r * tower_radius((z0 - base) / (h - base), (z1 - base) / (h - base)) + 0.15
        loc = Vector((c.x, c.y, z0)) + Vector((math.cos(yaw), math.sin(yaw), 0)) * rr
        hexwindow(loc, min(w, rr * 1.2), yaw, parent, height=z1 - z0, lo=lo)


tw_ = FEAT['towers']
x0, y0, x1, y1 = tw_['left']
d = 60.0
c = ARR.point((x0 + x1) / 2, (y0 + y1) / 2, d)
w = ARR.m(x1 - x0, d)
bot, topz = ARR.point((x0 + x1) / 2, y1, d).z, ARR.point((x0 + x1) / 2, y0, d).z
yaw = facing(c)
cc = c - Vector((math.cos(yaw), math.sin(yaw), 0)) * w * 0.9
tower(Vector((cc.x, cc.y, 0)), w * 1.05, topz + 14, G['Plaza'], windows=[(bot, topz, w, yaw)])
# The right: one huge bone building standing in the moat, two lit windows (top right, lower right), its trunk.
rt = tw_['right_top']
rl = tw_['right_low']
d_rt, d_rl = 26.0, 21.0
c_rt = ARR.point((rt[0] + rt[2]) / 2, (rt[1] + rt[3]) / 2, d_rt)
c_rl = ARR.point((rl[0] + rl[2]) / 2, (rl[1] + rl[3]) / 2, d_rl)
for (cx_, box, dd, r_, h_) in ((c_rt, rt, d_rt, 7.0, 44.0), (c_rl, rl, d_rl, 6.0, 20.0)):
    wv = ARR.m(box[2] - box[0], dd)
    z0 = ARR.point((box[0] + box[2]) / 2, box[3], dd).z
    z1 = ARR.point((box[0] + box[2]) / 2, box[1], dd).z
    yw = facing(cx_)
    core = cx_ - Vector((math.cos(yw), math.sin(yw), 0)) * r_ * 0.92
    tower(Vector((core.x, core.y, 0)), r_, h_, G['Plaza'], spire=r_ > 6.5, windows=[(z0, z1, wv, yw)])
# Its trunk: a bone column from the top right edge sweeping down into the moat (the concept's right trunk).
rtp = RIBS['right_trunk']['points'] + [(1150, 300), (1090, 400), (1060, 470)]
rt_pts = [ARR.on_plane(x, y, ARR.eye + fwd_h * 18.0, fwd_h) for x, y in rtp]
rt_pts = catmull(rt_pts, 4)
solid_rib('City3.RightTrunk', rt_pts, 1.4, 1.0, G['Plaza'], solid=True)
for sx, sy, d, s in ((1080, 150, 34, 2.0), (1110, 240, 30, 2.0), (1250, 455, 12, 1.2), (1050, 330, 28, 1.6)):
    coral(ARR.point(sx, sy, d), s * 2.2, G['Plaza'])
flesh(ARR.point(1120, 20, 32), 2.6, G['Plaza'], drips=5)

# The arched viaduct ring round the plaza (the concept's bridges behind the platforms, left and right).
VIA_R, VIA_Z = 96.0, 17.0
TAG[0] = None
for k in range(64):
    a0 = 2 * math.pi * k / 64
    a1 = 2 * math.pi * (k + 1) / 64
    p0_ = icw + Vector((math.cos(a0), math.sin(a0), 0)) * VIA_R
    p1_ = icw + Vector((math.cos(a1), math.sin(a1), 0)) * VIA_R
    # leave the west open (the canal and the in-road come in under it there: keep clear of the camera's back)
    if abs(math.degrees(a0) - 180) < 25:
        continue
    L = (p1_ - p0_).length
    yaw_ = math.atan2(p1_.y - p0_.y, p1_.x - p0_.x)
    inst('viaduct', (p0_.x, p0_.y, 0), (L, L * 0.5, VIA_Z), rot_z=yaw_, parent=G['Plaza'])
    if k % 4 == 0:
        inst('lantern', (p0_.x, p0_.y, VIA_Z + 0.5), 0.5, parent=G['Plaza'])

# =========================================================================================================================
# The sun (far, where the concept has it) and the skyline round the plaza: bone spires and towers composed against the
# concept's spire tips, hazy (far).
# =========================================================================================================================
SUN_D = 3000.0
sun = FEAT['sun']
sun_c = ARR.point(sun['centre'][0], sun['centre'][1], SUN_D)
sun_r = ARR.m(sun['radius'], SUN_D)
bm = bmesh.new()
bmesh.ops.create_circle(bm, cap_ends=True, segments=40, radius=sun_r)
sun_o = obj('City3.Sun', mesh_from('City3.Sun', bm, MAT['sun']), G['Sky'], sun_c)
sun_o.rotation_mode = 'QUATERNION'
sun_o.rotation_quaternion = (ARR.eye - sun_c).to_track_quat('Z', 'Y')
SUN_DIR = (sun_c - ARR.eye).normalized()

SPIRE_TIPS = [(355, 18, 220), (462, 58, 260), (528, 95, 300), (985, 12, 240), (1032, 2, 300), (1068, 40, 330),
              (1105, 30, 360), (905, 160, 380), (870, 150, 420), (420, 110, 380), (300, 150, 420), (250, 60, 260),
              (1010, 120, 420), (1140, 90, 460), (760, 70, 340), (205, 0, 200)]
for sx, sy, d in SPIRE_TIPS:
    tip = ARR.point(sx, sy, d)
    hgt = tip.z - MIST_Z
    r = max(3.0, hgt * rnd.uniform(0.03, 0.045))
    inst('spire', (tip.x, tip.y, MIST_Z), (r, r, hgt), rot_z=rnd.random() * 6.28, parent=G['Skyline'])
    if sx > 700 and rnd.random() < 0.7:
        inst('tower', (tip.x, tip.y, MIST_Z), (r * 1.6, r * 1.6, hgt * rnd.uniform(0.35, 0.55)), parent=G['Skyline'])
        if rnd.random() < 0.6:
            zz = hgt * 0.25 + MIST_Z
            hexwindow(Vector((tip.x, tip.y, zz)) + Vector((math.cos(facing(tip)), math.sin(facing(tip)), 0)) * r * 1.4,
                      r * 0.9, facing(tip), G['Skyline'], height=hgt * 0.15, lo=True)
# Honeycomb towers seen through the cage (the concept's lit towers beyond the platforms, 120-300 m off).
for sx, sy_top, d, wpx in ((300, 120, 160, 40), (395, 170, 200, 30), (470, 210, 240, 26), (840, 150, 210, 34),
                           (905, 240, 170, 30), (960, 110, 260, 40), (560, 250, 280, 24), (1010, 230, 150, 32),
                           (250, 210, 130, 30), (780, 260, 300, 26)):
    top = ARR.point(sx, sy_top, d)
    r = ARR.m(wpx, d) / 2
    c = Vector((top.x, top.y, 0))
    yw = facing(c)
    tower(c, r, top.z, G['Skyline'], spire=True, lo=True,
          windows=[(top.z * 0.2, top.z * 0.55, r * 1.0, yw), (top.z * 0.6, top.z * 0.8, r * 0.7, yw)])


def right_of_exit_end(c, reach=600.0):
    """Is c on the right of the exit's last ~320 m (kept low and empty for the desert), within reach?"""
    for s_ in np.arange(OUT_LEN - 330, OUT_LEN + 1, 10.0):
        p_, t_, n_ = line_frame(OUT_LINE, min(s_, OUT_LEN - 2))
        v = Vector((c.x, c.y, 0)) - p_
        if v.dot(n_) < 0 and v.length < reach:
            return True
    end_t = Vector((math.cos(OUT_H), math.sin(OUT_H), 0))
    v = Vector((c.x, c.y, 0)) - OUT_END
    return v.dot(end_t) > -50 and v.length < 2500  # ahead of the end: the desert's


print('plaza ledge ooze', ledge_ooze(ARR, (0, 0, 1280, 470), 50, G['Plaza'], length=(1.0, 6.0), width=0.12, step=8,
                                     max_depth=200.0))
# Far ring of hazy spires all round (every direction: the ride sees them too).
for k in range(70):
    a = rnd.uniform(0, 2 * math.pi)
    dist = rnd.uniform(650, 1400)
    c = icw + Vector((math.cos(a), math.sin(a), 0)) * dist
    if c.x < 200 or road_dist(c) < 60 or right_of_exit_end(c):
        continue
    h = rnd.uniform(90, 260)
    r = h * rnd.uniform(0.05, 0.08)
    inst('spirelo', (c.x, c.y, MIST_Z), (r, r, h - MIST_Z), rot_z=rnd.random() * 6.28, parent=G['Skyline'])
print('plaza composed: heart', [round(v, 1) for v in HEART_C - BIKE_AT], 'r', round(HEART_RX, 1), round(HEART_RZ, 1))

# =========================================================================================================================
# The causeway's world: a pink mist under everything (a dim floor far below, two haze sheets), the cathedral composed
# in the approach camera's screen space against the concept's traced skyline, viaducts off to the left, the big bone
# building close on the causeway's right.
# =========================================================================================================================
MAT['mist'] = material('City3Mist', (0.62, 0.36, 0.36), 1.0)
bm = bmesh.new()
polygon_slab(bm, [(-0.0, -2600), (5200, -2600), (5200, 2600), (0.0, 2600)], MIST_Z, 1.0)
obj('City3.MistFloor', mesh_from('City3.MistFloor', bm, MAT['mist'], smooth=False), G['Mist'])
for z, a in ((-5.0, 0.2), (-16.0, 0.3)):
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z)) for x, y in ((30, -900), (CATH_X - 40, -900), (CATH_X - 40, 900), (30, 900))]
    bm.faces.new(vs)
    obj('City3.HazeSheet', mesh_from('City3.HazeSheet', bm, MAT['haze'], smooth=False), G['Mist'])

CATH_D = APP.depth(Vector((CATH_X, 0, 0)))  # ~310: the facade's depth in the approach view
fwd_a = Vector((APP.fwd.x, APP.fwd.y, 0)).normalized()


def app_at(sx, sy, depth):
    return APP.point(sx, sy, depth)


TAG[0] = 'cathedral'
GC = G['Cathedral']
# The gate: a thick pointed bone arch over the road at the facade, its inner opening ~24 m tall.
GATE_W, GATE_H = 17.0, 25.0
gate = []
for k in range(41):
    t = k / 40
    a = math.pi * t
    y = -GATE_W / 2 * math.cos(a)
    z = GATE_H * (math.sin(a) ** 0.55)
    gate.append(Vector((CATH_X, y, z)))
gate = [Vector((CATH_X, -GATE_W / 2, MIST_Z + 30))] + gate + [Vector((CATH_X, GATE_W / 2, MIST_Z + 30))]
solid_rib('City3.Gate', gate, 3.2, 2.2, GC, plane_n=Vector((1, 0, 0)))
# The nave: pointed rib arches over the road every 8 m to NAVE_END, a vault skin over them, walls with hex windows
# facing in (lit: the portal's glow), lanterns.
for x in np.arange(CATH_X + 8, NAVE_END, 8.0):
    inst('rib', (x, 0, -2.0), (GATE_W / 2 + 1.5, 6.0, GATE_H + 4), rot_z=math.pi / 2, parent=GC)
bm = bmesh.new()
prof = [(-GATE_W / 2 - 3, -4.0)] + [(-(GATE_W / 2 + 2) * math.cos(a), (GATE_H + 3) * math.sin(a) ** 0.55)
                                    for a in np.linspace(0, math.pi, 17)] + [(GATE_W / 2 + 3, -4.0)]
prof = prof + [(y * 1.25, z * 1.12 + 4 if z > 0 else z) for y, z in reversed(prof)]
path = [Vector((x, 0, 0)) for x in np.linspace(CATH_X + 2, NAVE_END, 21)]
sweep(bm, path, [(a, b) for a, b in prof])
obj('City3.Nave', mesh_from('City3.Nave', bm, MAT['bone']), GC)
for x in np.arange(CATH_X + 12, NAVE_END - 4, 16.0):
    for side in (1, -1):
        hexwindow(Vector((x, side * (GATE_W / 2 + 1.8), 1.0)), 6.5, -side * math.pi / 2, GC, height=16)
        inst('lantern', (x + 8, side * (GATE_W / 2 - 0.5), 7.0), 0.5, parent=GC)
# A glowing honeycomb wall deep at the nave's end, above the road (the gate's glow seen from the causeway).
hexwindow(Vector((NAVE_END - 2, 0, 9.5)), GATE_W * 0.95, math.pi, GC, height=GATE_H - 8)

# The central tower over the nave: up off the top of the concept's frame, a huge lancet hex window facing the causeway.
ct = app_at(567, 160, CATH_D + 40)
CT = Vector((ct.x, ct.y, 0))
CT_R = APP.m(110, CATH_D + 40) / 2
bm = bmesh.new()
prof = [(CT_R * 1.1, 33.0), (CT_R * 1.1, 40), (CT_R, 80), (CT_R * 0.92, 120), (CT_R * 1.0, 150), (CT_R * 0.8, 175),
        (CT_R * 0.7, 195), (CT_R * 0.45, 215), (CT_R * 0.2, 240), (0.0, 255)]
lathe(bm, prof, seg=16, cx=CT.x, cy=CT.y, wob=lambda a, z: 1 + 0.06 * math.sin(4 * a + z * 0.05)
      + 0.1 * max(0, math.cos(4 * a)) * (z < 200))
wobble(bm, 1.2, 0.05)
obj('City3.CentralTower', mesh_from('City3.CentralTower', bm, MAT['bone']), GC)
wz0 = app_at(567, 245, CATH_D).z
wz1 = app_at(567, 95, CATH_D).z
ww = APP.m(58, CATH_D)
hexwindow(Vector((CT.x - CT_R * 0.98, CT.y, wz0)), ww, math.pi, GC, height=wz1 - wz0)
for z0, w_, hh in ((wz0 - 40, ww * 0.5, 22), (wz0 - 75, ww * 0.6, 22)):
    hexwindow(Vector((CT.x - CT_R * 1.08, CT.y, z0)), w_, math.pi, GC, height=hh)
# Ribs sweeping out from the tower to the wings (the concept's arcs, upper right and left).
for side, pts2 in ((-1, [(640, 70), (680, 45), (720, 70), (745, 120), (760, 180)]),
                   (1, [(500, 110), (470, 90), (430, 120), (400, 180), (380, 240)])):
    p0_ = Vector((CATH_X + 30, 0, 0))
    curve = [APP.on_plane(x, y, p0_, fwd_a) for x, y in pts2]
    curve = catmull(curve, 4)
    solid_rib('City3.CathRib', curve, 2.4, 1.7, GC, plane_n=fwd_a)

# The wings: towers and spires whose tips sit on the concept's traced skyline (peaks: spires; the rest: massing).
sk = FEAT_A['skyline']
cols = list(range(sk['cols'][0], sk['cols'][1]))
rows = sk['rows']
peaks = []
for x in range(sk['cols'][0] + 3, sk['cols'][1] - 3):
    if rows[x] < 330 and rows[x] <= min(rows[x - 6:x + 7]) and (not peaks or x - peaks[-1] > 9):
        peaks.append(x)
for x in peaks:
    if 505 < x < 630:
        continue  # the central tower
    d = CATH_D + rnd.uniform(10, 70)
    tip = app_at(x, rows[x], d)
    if road_dist(tip) < 26:
        d += 60
        tip = app_at(x, rows[x], d)
    hgt = tip.z - MIST_Z
    r = max(4.0, APP.m(14, d))
    inst('spire', (tip.x, tip.y, MIST_Z), (r, r, hgt), rot_z=rnd.random() * 6.28, parent=GC)
# Massing under the skyline: gothic bone shafts every 22 px of the trace (a wide spire whose shoulders sit ~30 px
# under the line), lancet windows lit in some, ribs (flying buttresses) leaning in toward the central tower.
for x in range(272, 950, 22):
    if 505 < x < 630:
        continue
    row = max(rows[max(272, x - 8):x + 9])
    d = CATH_D + rnd.uniform(20, 90)
    top = app_at(x, row + 8, d)
    if road_dist(top) < ROAD_W / 2 + 18:
        continue
    r = APP.m(rnd.uniform(26, 40), d)
    hgt = top.z - MIST_Z
    inst('spire', (top.x, top.y, MIST_Z), (r * 1.7, r * 1.7, hgt), rot_z=rnd.random() * 6.28, parent=GC)
    if rnd.random() < 0.7:
        zw = MIST_Z + hgt * rnd.uniform(0.32, 0.45)
        yw = math.pi + rnd.uniform(-0.3, 0.3)
        hexwindow(Vector((top.x, top.y, zw)) + Vector((math.cos(yw), math.sin(yw), 0)) * r * 1.7 * 0.6, r * 0.9, yw,
                  GC, height=r * 2.4, lo=True)
    if rnd.random() < 0.5:
        # a buttress rib from this shaft up toward the central tower
        a = Vector((top.x, top.y, top.z * 0.55))
        b = Vector((CT.x, CT.y + (top.y - CT.y) * 0.25, top.z * 0.85))
        pts = [a.lerp(b, u) + Vector((0, 0, 14 * math.sin(math.pi * u))) for u in np.linspace(0, 1, 10)]
        bm = bmesh.new()
        bone_ladder(bm, catmull(pts, 3), 3.4, 0.9, hole=6.0, flat=0.5, seg=4, taper=0.3, step=plen(pts) / 18,
                    strut_seg=3)
        obj('City3.Buttress', mesh_from('City3.Buttress', bm, MAT['bone']), GC)
# The facade's lower arcade either side of the gate (concept rows 330-460): stacked arches to the mist.
for side in (1, -1):
    for k in range(9):
        y = side * (GATE_W / 2 + 6 + k * 13)
        inst('rib', (CATH_X - 2 - k * 3, y, MIST_Z + 40), (6.0, 2.5, 40 + 30 * math.exp(-k / 3)),
             rot_z=math.pi / 2, parent=GC)
    bm = bmesh.new()
    ys = [side * (GATE_W / 2 + 2), side * 125]
    vs = []
    for (y, x) in ((ys[0], CATH_X + 2), (ys[1], CATH_X - 22), (ys[1], CATH_X + 120), (ys[0], CATH_X + 120)):
        vs.append((x, y))
    polygon_slab(bm, vs, 30.0, 95.0)
    wobble(bm, 2.5, 0.04)
    obj('City3.WingMass', mesh_from('City3.WingMass', bm, MAT['bone']), GC)
# Domes on the wings (the concept's honeycomb domes, left and right), coral and flesh with ooze across the facade.
for sx, sy, d, r in ((215, 340, 330, 16), (830, 238, 380, 18), (1080, 350, 420, 22), (60, 262, 520, 22),
                     (720, 455, 290, 9)):
    c = app_at(sx, sy, d)
    if road_dist(c) < ROAD_W / 2 + r + 4:
        continue
    inst('domeg', (c.x, c.y, c.z - r * 0.3), r, parent=GC)
    inst('domer', (c.x, c.y, c.z - r * 0.3), r, parent=GC)
    inst('tower', (c.x, c.y, MIST_Z), (r * 1.1, r * 1.1, c.z - r * 0.25 - MIST_Z), parent=GC)
# Flesh-coral and ooze draped over the facade: placed where the approach camera's rays at the concept's spots hit it.
bpy.context.view_layer.update()
_dg = bpy.context.evaluated_depsgraph_get()
for sx, sy, s in ((330, 300, 7), (380, 345, 8), (455, 290, 6), (650, 265, 6), (705, 300, 7), (420, 420, 6),
                  (290, 360, 6), (520, 330, 5), (600, 300, 5), (760, 330, 5), (180, 390, 7), (480, 380, 5),
                  (350, 250, 6), (690, 220, 5), (560, 380, 5), (800, 300, 6), (250, 320, 5), (440, 230, 5)):
    hit, loc, nrm_, *_ = scene.ray_cast(_dg, APP.eye, APP.ray(sx, sy).normalized(), distance=2000)
    if not hit or road_dist(loc) < ROAD_W / 2 + 4:
        continue
    d = APP.depth(loc)
    p = loc + nrm_ * APP.m(s * 1.5, d)
    flesh(p, APP.m(s * 3.6, d), GC, drips=5, flat=0.75, normal=nrm_)
    coral(p + nrm_ * APP.m(s * 2, d), APP.m(s * 6, d), GC, lo=True)
    for _ in range(3):  # ooze running down from the growth
        q = loc + nrm_ * 0.3 + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * APP.m(s * 2, d)
        inst('drip', q, (APP.m(s * 0.25, d), APP.m(s * 0.25, d), APP.m(s * rnd.uniform(3, 8), d)), parent=GC)

print('cathedral ledge ooze', ledge_ooze(APP, (150, 20, 1000, 460), 70, GC, length=(3.0, 14.0), width=0.3,
                                         step=7))

# Viaducts off to the left (the concept's arched bridges, rows ~290 and ~385), running away left from the cathedral.
GV = group('City3.Viaducts')
for (s0, s1, dd0, dd1) in (((300, 292), (0, 300), CATH_D * 0.95, 240.0), ((300, 388), (0, 395), CATH_D * 0.7, 150.0)):
    a = app_at(*s0, dd0)
    b = app_at(*s1, dd1)
    z = (a.z + b.z) / 2
    a.z = b.z = 0
    d = (b - a).normalized()
    b = b + d * 260
    a = a - d * 80
    L = (b - a).length
    n = int(L / 22)
    yaw_ = math.atan2(d.y, d.x)
    for k in range(n):
        p = a + d * (k * L / n)
        if road_dist(p) < 10:
            continue
        inst('viaduct', (p.x, p.y, 0), (L / n, L / n * 0.55, z), rot_z=yaw_, parent=GV)
    print('viaduct z', round(z, 1), 'len', round(L))

# The bone building close on the causeway's right (the concept's right third): a bulging mass, flesh-coral and ooze
# over it, a round honeycomb window.
TAG[0] = 'rightbuilding'
rb = app_at(1180, 300, 75.0)
rbc = Vector((rb.x, rb.y, 0))
off = road_dist(rbc)
rr = 24.0
if off < ROAD_W / 2 + rr + 6:
    rbc = rbc + Vector((0, -(ROAD_W / 2 + rr + 6 - off), 0))
inst('tower', (rbc.x, rbc.y, MIST_Z), (rr, rr, 95 - MIST_Z), parent=G['Causeway'])
inst('tower', (rbc.x + 30, rbc.y - 25, MIST_Z), (rr * 0.9, rr * 0.9, 120 - MIST_Z), parent=G['Causeway'])
yaw_ = math.atan2(APP.eye.y - rbc.y, APP.eye.x - rbc.x)
for zz, w_ in ((30.0, 13.0), (8.0, 9.0), (55.0, 10.0)):
    hexwindow(rbc + Vector((math.cos(yaw_), math.sin(yaw_), 0)) * rr * 0.93 + Vector((0, 0, zz)), w_, yaw_,
              G['Causeway'], height=w_ * 1.1)
for k, z in enumerate((70, 58, 46, 36, 26, 14, 82, 64, 40)):
    # flesh-coral webbing patches crusted over its face, ooze running off them
    a = yaw_ + rnd.uniform(-1.0, 1.0)
    f = (z - MIST_Z) / (95 - MIST_Z)
    nrm = Vector((math.cos(a), math.sin(a), 0))
    p = rbc + nrm * rr * tower_radius(f - 0.01, f + 0.01) * 0.97 + Vector((0, 0, z))
    flesh(p, rnd.uniform(3.5, 6.0), G['Causeway'], drips=4, normal=nrm)
    if k % 2 == 0:
        coral(p + nrm * 2 + Vector((0, 0, 3)), rnd.uniform(5, 9), G['Causeway'])

# The far left city (behind the sun's side): spires, towers, domes, 500-1100 m off.
TAG[0] = 'farleft'
for k in range(26):
    sx = rnd.uniform(-60, 330)
    d = rnd.uniform(480, 1000)
    tip = app_at(sx, rnd.uniform(60, 270), d)
    if tip.x < 150 or road_dist(tip) < 80:
        continue
    hgt = tip.z - MIST_Z
    r = max(5.0, hgt * rnd.uniform(0.05, 0.08))
    inst('spirelo', (tip.x, tip.y, MIST_Z), (r, r, hgt), rot_z=rnd.random() * 6.28, parent=G['Skyline'])
    if rnd.random() < 0.5:
        inst('domeg', (tip.x + r * 3, tip.y, hgt * 0.3 + MIST_Z), r * 2.2, parent=G['Skyline'])
        inst('domer', (tip.x + r * 3, tip.y, hgt * 0.3 + MIST_Z), r * 2.2, parent=G['Skyline'])
        inst('towerlo', (tip.x + r * 3, tip.y, MIST_Z), (r * 2.3, r * 2.3, hgt * 0.3), parent=G['Skyline'])
# Lone spires and coral stacks rising out of the mist along the causeway (both sides, off the road).
TAG[0] = 'causeway'
for k in range(30):
    x = rnd.uniform(60, CATH_X - 60)
    y = rnd.choice((1, -1)) * rnd.uniform(60, 420)
    c = Vector((x, y, 0))
    if road_dist(c) < 50:
        continue
    h = rnd.uniform(20, 110)
    r = rnd.uniform(4, 10)
    inst('spirelo', (x, y, MIST_Z), (r, r, h - MIST_Z), rot_z=rnd.random() * 6.28, parent=G['Causeway'])
    if rnd.random() < 0.4:
        coral((x, y, h * 0.35), rnd.uniform(6, 14), G['Causeway'], lo=True)

# =========================================================================================================================
# The hive: the weave from the nave to the plaza. Towers close either side of the road (honeycomb windows facing it,
# coral and flesh dripping ooze), rib arches and skybridges overhead, pods with honeycomb domes.
# =========================================================================================================================
placed = []


def free(c, r, clear=10.0):
    if road_dist(c) < ROAD_W / 2 + clear + r:
        return False
    if any((Vector((c.x, c.y, 0)) - q).length < r + qr + 6 for q, qr in placed):
        return False
    if (Vector((c.x, c.y, 0)) - B(IC.x, IC.y)).length < PLAZA_R + r + 6:
        return False
    return True


def hive_tower(c, r, h, face, tag):
    TAG[0] = tag
    placed.append((Vector((c.x, c.y, 0)), r))
    g = G['Hive']
    tower(Vector((c.x, c.y, 0)), r, h, g, spire=rnd.random() < 0.75, lo=True, body_lo=road_dist(c) > 60,
          windows=[(z, z + r * rnd.uniform(1.0, 1.7), r * rnd.uniform(0.55, 0.85), face + rnd.uniform(-0.25, 0.25))
                   for z in np.arange(rnd.uniform(2, 10), h * 0.7, r * 2.4)][:2])
    for _ in range(rnd.randint(1, 2)):
        # flesh-coral webbing draped round the body, ooze run down over it
        a = face + rnd.uniform(-1.4, 1.4)
        z0 = rnd.uniform(-10, h * 0.6)
        hz = rnd.uniform(10, 24)
        f0, f1 = (z0 - MIST_Z) / (h - MIST_Z), (z0 + hz - MIST_Z) / (h - MIST_Z)
        drape(c, r * tower_radius(f0, f1), z0, hz, a, g)
        p = Vector((c.x, c.y, z0 + hz)) + Vector((math.cos(a), math.sin(a), 0)) * r * tower_radius(f1, f1 + 0.02)
        coral(p, rnd.uniform(3, 7), g, lo=True)
    # ooze off the crown
    for _ in range(2):
        a = rnd.uniform(0, 6.28)
        zc = MIST_Z + (h - MIST_Z) * 0.8
        p = Vector((c.x, c.y, zc)) + Vector((math.cos(a), math.sin(a), 0)) * r * tower_radius(0.78, 0.82)
        inst('drip', p, (r * 0.07, r * 0.07, rnd.uniform(4, 14)), parent=g)


S0 = NAVE_END + 20
s = S0
side = 1
k = 0
while s < S_PLAZA - 40:
    p, t, n = line_frame(ROAD_LINE, s)
    side = -side
    for _ in range(14):
        r = rnd.uniform(9, 17)
        h = rnd.uniform(40, 120)
        c = p + n * side * (ROAD_W / 2 + rnd.uniform(12, 30) + r) + t * rnd.uniform(-10, 10)
        if free(c, r):
            hive_tower(c, r, h, math.atan2(-n.y * side, -n.x * side), f'hive{k}')
            k += 1
            break
    # A second row further back now and then.
    if rnd.random() < 0.45:
        for _ in range(8):
            r = rnd.uniform(12, 24)
            c = p + n * -side * (ROAD_W / 2 + rnd.uniform(50, 110) + r) + t * rnd.uniform(-30, 30)
            if free(c, r, 30):
                hive_tower(c, r, rnd.uniform(70, 170), math.atan2(n.y * side, n.x * side), f'hive{k}')
                k += 1
                break
    s += rnd.uniform(26, 40)
print('hive towers', k)
# Overhead: every ~120 m a rib arch or skybridge across the road.
s = S0 + 40
k = 0
while s < S_PLAZA - 30:
    p, t, n = line_frame(ROAD_LINE, s)
    TAG[0] = f'over{k}'
    yaw_ = math.atan2(n.y, n.x)
    if k % 2 == 0:
        span = rnd.uniform(16, 26)
        inst('rib', (p.x, p.y, MIST_Z + 50), (span, 4.0, rnd.uniform(28, 45) - MIST_Z - 50 + 50), rot_z=yaw_,
             parent=G['Hive'])
        if rnd.random() < 0.6:
            inst('rib', (p.x + t.x * 6, p.y + t.y * 6, MIST_Z + 50), (span * 1.1, 4.0, rnd.uniform(30, 50)),
                 rot_z=yaw_, parent=G['Hive'])
    else:
        # A skybridge: a bone tube on two legs, lit hex band along it, ooze drips.
        hz = rnd.uniform(16, 30)
        L = rnd.uniform(40, 70)
        a = p + n * L / 2 + Vector((0, 0, hz))
        b = p - n * L / 2 + Vector((0, 0, hz))
        pts = [a.lerp(b, u) + Vector((0, 0, 3 * math.sin(math.pi * u))) for u in np.linspace(0, 1, 14)]
        bm = bmesh.new()
        tube(bm, pts, [2.4] * len(pts), seg=10)
        wobble(bm, 0.3, 0.3)
        obj('City3.Skybridge', mesh_from('City3.Skybridge', bm, MAT['bone']), G['Hive'])
        bm = bmesh.new()
        sweep(bm, [q + Vector((0, 0, 0.2)) for q in pts], rounded_rect_profile(5.0, 1.1, 0.3))
        obj('City3.SkybridgeGlow', mesh_from('City3.SkybridgeGlow', bm, MAT['amber']), G['Hive'])
        for e in (a, b):
            inst('tower', (e.x, e.y, MIST_Z), (5.0, 5.0, hz + 6 - MIST_Z), parent=G['Hive'])
        for _ in range(5):
            q = pts[rnd.randrange(2, len(pts) - 2)]
            inst('drip', q - Vector((0, 0, 2.2)), (0.35, 0.35, rnd.uniform(1.5, 5)), parent=G['Hive'])
    k += 1
    s += rnd.uniform(100, 150)
# Pods with honeycomb domes and spires filling the weave's gaps (further out).
for k in range(45):
    s_ = rnd.uniform(S0, S_PLAZA)
    p, t, n = line_frame(ROAD_LINE, s_)
    side = rnd.choice((1, -1))
    r = rnd.uniform(8, 16)
    c = p + n * side * rnd.uniform(40, 220)
    if not free(c, r, 25):
        continue
    TAG[0] = f'pod{k}'
    placed.append((Vector((c.x, c.y, 0)), r))
    z = rnd.uniform(-10, 30)
    inst('pod', (c.x, c.y, z), (r, r, r * 1.2), parent=G['Hive'])
    inst('tower', (c.x, c.y, MIST_Z), (r * 0.6, r * 0.6, z + 2 - MIST_Z), parent=G['Hive'])
    inst('domeg', (c.x, c.y, z + r * 0.9), r * 0.6, parent=G['Hive'])
    inst('domer', (c.x, c.y, z + r * 0.9), r * 0.6, parent=G['Hive'])
    if rnd.random() < 0.5:
        inst('spirelo', (c.x + r, c.y, MIST_Z), (r * 0.5, r * 0.5, z + r * 5 - MIST_Z), parent=G['Hive'])

# The hive's mass: clusters of low-poly spires and towers rising out of the mist to fill the gaps between the weave's legs
# and round it (two to four shafts each, a lit window on some, coral and an ooze sheet on some).
def cluster(c, parent, tag, scale=1.0):
    TAG[0] = tag
    nshaft = rnd.randint(2, 4)
    for j in range(nshaft):
        q = c + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * 14 * scale
        h = rnd.uniform(25, 150) * scale
        r = rnd.uniform(5, 11) * scale
        if rnd.random() < 0.55:
            inst('spirelo', (q.x, q.y, MIST_Z), (r, r, h - MIST_Z), rot_z=rnd.random() * 6.28, parent=parent)
        else:
            inst('towerlo', (q.x, q.y, MIST_Z), (r, r, h - MIST_Z), rot_z=rnd.random() * 6.28, parent=parent)
            if rnd.random() < 0.5:
                inst('spirelo', (q.x, q.y, h - 4), (r * 0.4, r * 0.4, h * 0.5), parent=parent)
            if rnd.random() < 0.3:
                yw = rnd.uniform(0, 6.28)
                zw = MIST_Z + (h - MIST_Z) * rnd.uniform(0.45, 0.6)
                hexwindow(Vector((q.x, q.y, zw)) + Vector((math.cos(yw), math.sin(yw), 0)) * r * 0.98, r * 0.9, yw,
                          parent, height=r * 1.6, lo=True)
            if rnd.random() < 0.35:
                z0 = rnd.uniform(-20, h * 0.5)
                inst('drapeo', (q.x, q.y, z0), (r * 1.05, r * 1.05, rnd.uniform(10, 25)), rot_z=rnd.uniform(0, 6.28),
                     parent=parent)
    if rnd.random() < 0.5:
        coral((c.x, c.y, rnd.uniform(-10, 20)), rnd.uniform(6, 14) * scale, parent, lo=True)


nclu = 0
for gx in np.arange(880, 2120, 74.0):
    for gy in np.arange(-260, 420, 74.0):
        c = Vector((gx + rnd.uniform(-20, 20), gy + rnd.uniform(-20, 20), 0))
        d = road_dist(c)
        if not (26 < d < 300) or any((c - q).length < qr + 18 for q, qr in placed):
            continue
        if (c - B(IC.x, IC.y)).length < PLAZA_R + 30:
            continue
        cluster(c, G['Hive'], f'clu{nclu}', scale=1.0 if d < 120 else 1.25)
        placed.append((c, 14.0))
        nclu += 1
print('hive clusters', nclu)
# Membranes of flesh-coral slung between neighbouring towers by the road.
nweb = 0
near = [(q, r) for q, r in placed if road_dist(q) < 70]
for i, (a, ra) in enumerate(near):
    for b, rb in near[i + 1:]:
        gap = (b - a).length
        if 30 < gap < 70 and rnd.random() < 0.5 and nweb < 34:
            m = (a + b) / 2
            if road_dist(m) < ROAD_W / 2 + 8:
                continue  # never across the road
            d = (b - a).normalized()
            zt = rnd.uniform(20, 45)
            TAG[0] = f'web{nweb}'
            inst(rnd.choice(('web1', 'web2')), (m.x, m.y, zt - gap * 0.45), (gap / 2, 1.0, gap * 0.45),
                 rot_z=math.atan2(d.y, d.x), parent=G['Hive'])
            nweb += 1
print('webs', nweb)

# =========================================================================================================================
# The exit: the hive's edge on the left of the exit road (arches, spires, honeycomb towers, a viaduct sweeping
# alongside, coral grown over the left parapet), low and sparse on the right, nothing on the right for the last 300 m.
# =========================================================================================================================
TAG[0] = None
GE = G['Exit']
s = S_OUT_DECK + 10
k = 0
while s < OUT_LEN - 40:
    p, t, n = line_frame(OUT_LINE, s)
    # Left: a tower or a spire cluster, close.
    for _ in range(10):
        r = rnd.uniform(8, 16)
        c = p + n * (ROAD_W / 2 + rnd.uniform(14, 40) + r) + t * rnd.uniform(-10, 10)
        if road_dist(c, (OUT_LINE,)) > ROAD_W / 2 + 10 + r and \
                not any((c - q).length < r + qr + 5 for q, qr in placed):
            placed.append((c, r))
            fade = max(0.45, 1 - s / OUT_LEN * 0.6)  # the hive thins out toward the desert
            r *= fade
            ht = rnd.uniform(40, 130) * fade
            face = math.atan2(-n.y, -n.x)
            tower(Vector((c.x, c.y, 0)), r, ht, GE, spire=True, lo=True,
                  windows=[(z, z + r * 1.4, r * 0.8, face + rnd.uniform(-0.3, 0.3))
                           for z in (rnd.uniform(0, 8), rnd.uniform(12, 25))])
            z0 = rnd.uniform(-12, ht * 0.4)
            hz = rnd.uniform(10, 20)
            drape(c, r * tower_radius((z0 - MIST_Z) / (ht - MIST_Z), (z0 + hz - MIST_Z) / (ht - MIST_Z)), z0, hz,
                  face + rnd.uniform(-0.6, 0.6), GE)
            break
    # Rib arches leaning over the road from the left.
    if k % 3 == 1:
        yaw_ = math.atan2(n.y, n.x)
        c = p + n * (ROAD_W / 2 + 10)
        inst('rib', (c.x, c.y, MIST_Z + 40), (22, 3.5, 75), rot_z=yaw_, rot=(0.0, math.radians(-20), yaw_),
             parent=GE)
    # Coral over the left parapet.
    for _ in range(3):
        q = p + t * rnd.uniform(-15, 15) + n * (ROAD_W / 2 + rnd.uniform(-0.4, 2.5))
        coral((q.x, q.y, 0.2), rnd.uniform(1.4, 3.6), GE)
    # The right: low pods only, and none on the last 300 m.
    if s < OUT_LEN - 320 and rnd.random() < 0.5:
        r = rnd.uniform(6, 12)
        c = p - n * (ROAD_W / 2 + rnd.uniform(20, 60) + r)
        inst('pod', (c.x, c.y, -12), (r, r, r * 1.3), parent=GE)
        inst('tower', (c.x, c.y, MIST_Z), (r * 0.6, r * 0.6, -10 - MIST_Z), parent=GE)
    k += 1
    s += rnd.uniform(28, 42)
# The viaduct sweeping alongside on the left (the concept's curving elevated road), 40-70 m off, deck z 20.
vl = [p + n * (55 + 15 * math.sin(s_ / 120)) for s_, (p, t, n) in
      ((s_, line_frame(OUT_LINE, s_)) for s_ in np.arange(S_OUT_DECK, OUT_LEN - 60, 24.0))]
for a, b in zip(vl, vl[1:]):
    L = (b - a).length
    inst('viaduct', (a.x, a.y, 0), (L, L * 0.5, 20.0), rot_z=math.atan2(b.y - a.y, b.x - a.x), parent=GE)
# Fill the exit's left edge: clusters 25-220 m off the road's left, thinning toward the desert.
TAG[0] = None
for s_ in np.arange(S_OUT_DECK + 20, OUT_LEN - 30, 34.0):
    p, t, n = line_frame(OUT_LINE, s_)
    for _ in range(1):
        c = p + n * rnd.uniform(28, 220) + t * rnd.uniform(-15, 15)
        if road_dist(c) < 26 or any((c - q).length < qr + 14 for q, qr in placed):
            continue
        cluster(c, GE, None, scale=max(0.55, 1.0 - s_ / OUT_LEN * 0.4))
        placed.append((c, 12.0))
TAG[0] = None
# Sand drifting over the asphalt and against the parapets on the last stretch.
MAT_S = MAT['sand']
for s_ in np.arange(S_ASPHALT + 20, OUT_LEN, 9.0):
    p, t, n = line_frame(OUT_LINE, s_)
    for side in (1, -1):
        if rnd.random() < 0.7:
            q = p + n * side * (ROAD_W / 2 - rnd.uniform(0.5, 2.5))
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=5, radius=1.0)
            for v in bm.verts:
                v.co.z = max(v.co.z, 0)
            L = rnd.uniform(3, 9)
            bmesh.ops.scale(bm, vec=(L, rnd.uniform(1.0, 2.2), rnd.uniform(0.15, 0.4)), verts=bm.verts)
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0),
                             matrix=Matrix.Rotation(math.atan2(t.y, t.x) + rnd.uniform(-0.3, 0.3), 3, 'Z'))
            obj('City3.SandDrift', mesh_from('City3.SandDrift', bm, MAT_S), GE, (q.x, q.y, 0.0))

# =========================================================================================================================
# The leak sweep: ray-cast the arrival frame every 3 px; any approach-only piece that shows goes (a whole tagged group
# at a time), until none shows. (City2's; here almost all of it is behind the arrival camera anyway.)
# =========================================================================================================================
TAG[0] = None


def leak_sweep():
    for sweep_pass in range(4):
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        leaks = set()
        for sy in range(0, RES[1], 3):
            for sx in range(0, RES[0], 3):
                d = ARR.ray(sx + 0.5, sy + 0.5).normalized()
                hit, loc, nrm_, idx, ob, mtx = scene.ray_cast(dg, ARR.eye, d, distance=8000)
                if hit and ob.get('approach_only'):
                    leaks.add(ob['approach_only'])
        print('leak sweep', sweep_pass, sorted(leaks))
        if not leaks:
            break
        for o in [o for o in scene.objects if o.get('approach_only') in leaks]:
            bpy.data.objects.remove(o, do_unlink=True)


leak_sweep()

# =========================================================================================================================
# Markers.
# =========================================================================================================================


def empty(name, loc, rot_quat=None, yaw=None, props=None, size=1.0):
    e = bpy.data.objects.new(name, None)
    scene.collection.objects.link(e)
    e.parent = root
    e.empty_display_size = size
    e.location = loc
    if rot_quat is not None:
        e.rotation_mode = 'QUATERNION'
        e.rotation_quaternion = rot_quat
    elif yaw is not None:
        e.rotation_euler = (0, 0, math.radians(yaw))
    for k_, v in (props or {}).items():
        e[k_] = v
    return e


def r4(v):
    return [round(float(c), 4) for c in v]


def three(v):
    """City3's Blender frame -> the site's (three: x along the road in, y up, z to its right)."""
    return [round(float(v[0]), 4), round(float(v[2]), 4), round(float(-v[1]), 4)]


empty('City3.ArrivalCam', EYE, (LOOK - EYE).to_track_quat('-Z', 'Y'),
      props={'EYE': r4(EYE), 'LOOK': r4(LOOK), 'FOV': round(FOV, 3),
             'note': 'Blender local frame (z up); FOV vertical degrees; the empty looks down its -Z like a camera'})
empty('City3.ApproachCam', APP_EYE, (APP_LOOK - APP_EYE).to_track_quat('-Z', 'Y'),
      props={'EYE': r4(APP_EYE), 'LOOK': r4(APP_LOOK), 'FOV': APP_FOV})
empty('City3.ExitCam', EXIT_EYE, (EXIT_LOOK - EXIT_EYE).to_track_quat('-Z', 'Y'),
      props={'EYE': r4(EXIT_EYE), 'LOOK': r4(EXIT_LOOK), 'FOV': 55.0})
empty('City3.BikeMark', BIKE_AT, yaw=BIKE_YAW, props={'YAW': BIKE_YAW, 'note': 'bike front along local +X'})
empty('City3.RoadIn', Vector((0, 0, 0)), yaw=0.0,
      props={'note': 'the road hands over here heading local +X, deck top z 0; width 11.8; its line is City3.RoadPath',
             'LENGTH': round(ROAD_LEN, 2)})
empty('City3.RoadPath', Vector((0, 0, 0)),
      props={'points': [[round(p.x, 3), round(p.y, 3)] for p in ROAD_LINE], 'length': round(ROAD_LEN, 2),
             'step': 2.0, 'width': ROAD_W,
             'note': f'the bike line, RoadIn (0,0) -> BikeMark ({BIKE_AT.x:.1f},{BIKE_AT.y:.1f}), [x, y] in City3 local '
                     'Blender frame (z up; three: x, -y as z), every 2 m of arc length (last step shorter); the deck '
                     'top is z 0 on this line, ROAD_W wide'})
empty('City3.RoadOut', Vector((0, 0, 0)),
      props={'points': [[round(p.x, 3), round(p.y, 3)] for p in OUT_LINE], 'length': round(OUT_LEN, 2), 'step': 2.0,
             'width': ROAD_W, 'END': [round(OUT_END.x, 3), round(OUT_END.y, 3)], 'END_HEADING': round(OUT_H, 6),
             'note': 'the exit, BikeMark -> END, [x, y] in City3 local Blender frame every 2 m; it leaves the bike '
                     'straight over the slipway (the moat\'s ford, water just over it) and the heart\'s island, under '
                     'the heart, then bends right onto a 400 m straight; END_HEADING radians anticlockwise from +x; '
                     'the next zone goes on from END straight along END_HEADING'})
empty('City3.DeckTop', Vector((0, 0, 0)), props={'note': 'deck top z 0 (RoadIn); the plaza floor is z 0 too'})

# --- Stats ---------------------------------------------------------------------------------------------------------------
meshes = [o for o in root.children_recursive if o.type == 'MESH']
uniq = {o.data.name: o.data for o in meshes}


def tris(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


TRI_UNIQUE = sum(tris(me) for me in uniq.values())
_grp = {}
for o in meshes:
    g_ = o
    while g_.parent and g_.parent != root:
        g_ = g_.parent
    _grp[g_.name] = _grp.get(g_.name, 0) + tris(o.data)
print('drawn tris by group', sorted(_grp.items(), key=lambda kv: -kv[1]))
print('modules (tris x instances)', sorted(((k, tris(m_), m_.users) for k, m_ in M.items()), key=lambda r: -r[1] * r[2]))
TRI_TOTAL = sum(tris(o.data) for o in meshes)
MIN_X = min((o.matrix_world @ Vector(c)).x for o in meshes for c in o.bound_box)
print('min x of anything', round(MIN_X, 2))
print('objects', len(meshes), 'unique meshes', len(uniq), 'unique tris', TRI_UNIQUE, 'drawn tris', TRI_TOTAL)
print('arrival EYE', r4(EYE), 'LOOK', r4(LOOK), 'FOV', FOV, '| three', three(EYE), three(LOOK))
print('approach EYE', r4(APP_EYE), 'LOOK', r4(APP_LOOK), '| exit END', r4(OUT_END), 'heading', OUT_H)

# =========================================================================================================================
# Vertex colours ('Col', per point): dirt (crevices and feet darker, a little grime) on everything, and Cycles AO baked
# on the unique meshes in place (unless CITY3_NO_BAKE). The glb carries it as COLOR_0 (three multiplies it in).
# =========================================================================================================================
NO_COL = {'City3Sun', 'City3Amber', 'City3Heart', 'City3Lamp', 'City3Haze', 'City3Water', 'City3Mist'}


def dirt(o, base_dark=0.35):
    """Grime per vertex (0-1): crevices dark (concavity), the foot of each piece dark, streaks running down, and on the
    unique pieces placed in the world, a dark band where they meet the floor or the water (z ~ 0)."""
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    zs = [v.co.z for v in bm.verts] or [0]
    z0, z1 = min(zs), max(zs)
    world = me.users == 1
    mw = o.matrix_world
    out = []
    for v in bm.verts:
        nb = [e.other_vert(v).co for e in v.link_edges]
        cav = 0.0
        if nb:
            cav = sum((q - v.co).dot(v.normal) / max((q - v.co).length, 1e-6) for q in nb) / len(nb)
        c = 1.0 - 1.5 * max(0.0, cav)              # concave -> darker
        h = (v.co.z - z0) / max(z1 - z0, 1e-6)
        c *= 1 - base_dark * max(0.0, 1 - h * 3) ** 1.5   # the lower third darkens toward the foot
        # streaks running down (vertical bands round the piece, stronger low)
        a = math.atan2(v.co.y, v.co.x)
        streak = max(0.0, math.sin(a * 7 + v.co.x * 0.9) * math.sin(a * 3 - v.co.y * 0.7))
        c *= 1 - 0.28 * streak * (1 - 0.6 * h)
        if world:
            wz = (mw @ v.co).z
            c *= 0.5 + 0.5 * min(1.0, max(0.0, (wz - 0.0) / 3.0)) if wz > -1.5 else 0.5
        g = 0.93 + 0.07 * math.sin(v.co.x * 3.1 + v.co.y * 1.7) * math.sin(v.co.z * 2.3)
        out.append(max(0.18, min(1.0, c * g)))
    bm.free()
    return out


GRIME = (0.40, 0.27, 0.19)  # crevice colour: warm brown-black (three multiplies COLOR_0 into the base colour)


def grime(v):
    return tuple(GRIME[i] + (1 - GRIME[i]) * v for i in range(3)) if v < 1 else (1.0, 1.0, 1.0)


def ensure_col(me):
    if 'Col' not in me.color_attributes:
        me.color_attributes.new('Col', 'BYTE_COLOR', 'POINT')
    me.color_attributes.active_color = me.color_attributes['Col']
    return me.color_attributes['Col']


done = set()
for o in meshes:
    me = o.data
    if me.name in done:
        continue
    done.add(me.name)
    col = ensure_col(me)
    if me.materials[0].name in NO_COL:
        for d in col.data:
            d.color = (1, 1, 1, 1)
        continue
    vals = dirt(o, 0.55 if me.users > 1 else 0.35)
    for d, v in zip(col.data, vals):
        d.color = (*grime(v * v), 1)

if os.environ.get('CITY3_NO_BAKE') != '1':
    # AO on the unique meshes (one user: their own place in the city), multiplied into the dirt.
    bake = [o for o in meshes if o.data.users == 1 and o.data.materials[0].name not in NO_COL
            and len(o.data.vertices) > 30]
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 24
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'METAL'
        prefs.get_devices()
        for dv in prefs.devices:
            dv.use = True
        scene.cycles.device = 'GPU'
    except Exception as exc:
        print('cycles gpu:', exc)
    scene.world = scene.world or bpy.data.worlds.new('City3BakeWorld')
    scene.world.light_settings.distance = 6.0
    keep = {}
    for o in bake:
        me = o.data
        keep[me.name] = [tuple(d.color) for d in me.color_attributes['Col'].data]
        ao = me.color_attributes.new('AO', 'BYTE_COLOR', 'POINT')
        me.color_attributes.active_color = ao
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in bake:
        o.select_set(True)
    bpy.context.view_layer.objects.active = bake[0]
    import time
    t0 = time.time()
    bpy.ops.object.bake(type='AO', target='VERTEX_COLORS')
    print('ao bake', len(bake), 'meshes', round(time.time() - t0, 1), 's')
    for o in bake:
        me = o.data
        ao = me.color_attributes['AO']
        col = me.color_attributes['Col']
        for d, c0, a in zip(col.data, keep[me.name], ao.data):
            f = 0.3 + 0.7 * a.color[0] ** 1.3
            d.color = (c0[0] * f, c0[1] * f, c0[2] * f, 1)
        me.color_attributes.remove(ao)
        me.color_attributes.active_color = me.color_attributes['Col']

# --- Save and export ----------------------------------------------------------------------------------------------------
os.makedirs(os.path.dirname(GLB), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
for o in bpy.context.view_layer.objects:
    o.select_set(False)
for o in root.children_recursive:
    o.select_set(True)
root.select_set(True)
bpy.ops.export_scene.gltf(filepath=GLB, export_format='GLB', use_selection=True, export_apply=True,
                          export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
                          export_draco_position_quantization=14, export_draco_normal_quantization=8,
                          export_draco_texcoord_quantization=10, export_draco_color_quantization=8,
                          export_vertex_color='ACTIVE', export_image_format='JPEG', export_jpeg_quality=85,
                          export_gpu_instances=True,
                          export_yup=True, export_cameras=False, export_lights=False, export_extras=True)
GLB_SIZE = os.path.getsize(GLB)
print('exported', GLB, GLB_SIZE)


# =========================================================================================================================
# Renders.
# =========================================================================================================================
def add_bike():
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=BIKE_GLB)
    imported = set(bpy.data.objects) - before
    rig = bpy.data.objects.new('BikeRig', None)
    scene.collection.objects.link(rig)
    rig.matrix_world = BIKE_M
    for o in imported:
        if o.parent is None:
            o.parent = rig
    return [o for o in imported if o.type == 'MESH']


bike_objs = add_bike()
os.makedirs(RENDERS, exist_ok=True)
cam = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
scene.collection.objects.link(cam)
scene.camera = cam


def set_cam(v):
    cam.location = v.eye
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (v.look - v.eye).to_track_quat('-Z', 'Y')
    cam.data.type = 'PERSP'
    cam.data.sensor_fit = 'VERTICAL'
    cam.data.sensor_height = 24
    cam.data.lens = 12 / math.tan(math.radians(v.fov / 2))
    cam.data.clip_start = 0.05
    cam.data.clip_end = 9000
    scene.render.resolution_x, scene.render.resolution_y = RES


# For the renders the vertex colours go into the materials (the glb carries them as COLOR_0; three multiplies them in).
for m in bpy.data.materials:
    if not m.name.startswith('City3') or m.name in NO_COL or not m.use_nodes:
        continue
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    attr = nt.nodes.new('ShaderNodeVertexColor')
    attr.layer_name = 'Col'
    mul, ia, ib, io = mix_rgba(nt)
    src = p.inputs['Base Color'].links[0].from_socket if p.inputs['Base Color'].links else None
    if src:
        nt.links.new(src, ia)
    else:
        ia.default_value = p.inputs['Base Color'].default_value
    nt.links.new(attr.outputs['Color'], ib)
    nt.links.new(io, p.inputs['Base Color'])

# The world: a dawn sky (rose overhead, hot pink-orange low, gold round the sun) and, for the EEVEE renders, a pink haze
# in the air that the sun's light scatters in (god rays through the ribs).
world = bpy.data.worlds.new('City3Dawn')
world.use_nodes = True
nt = world.node_tree
nodes, links = nt.nodes, nt.links
bg = nodes['Background']
tc = nodes.new('ShaderNodeTexCoord')
sep = nodes.new('ShaderNodeSeparateXYZ')
links.new(tc.outputs['Generated'], sep.inputs[0])
ramp = nodes.new('ShaderNodeValToRGB')
cr = ramp.color_ramp
cr.elements[0].position, cr.elements[0].color = 0.0, (1.0, 0.5, 0.22, 1)
cr.elements[1].position, cr.elements[1].color = 0.62, (0.42, 0.12, 0.18, 1)
e = cr.elements.new(0.1)
e.color = (0.95, 0.36, 0.22, 1)
e = cr.elements.new(0.3)
e.color = (0.75, 0.24, 0.26, 1)
links.new(sep.outputs['Z'], ramp.inputs['Fac'])
dot = nodes.new('ShaderNodeVectorMath')
dot.operation = 'DOT_PRODUCT'
links.new(tc.outputs['Generated'], dot.inputs[0])
dot.inputs[1].default_value = SUN_DIR
pw = nodes.new('ShaderNodeMath')
pw.operation = 'POWER'
pw.use_clamp = True
links.new(dot.outputs['Value'], pw.inputs[0])
pw.inputs[1].default_value = 10.0
mix, ia, ib, io = mix_rgba(nt, 'ADD')
links.new(pw.outputs[0], mix.inputs[0])
links.new(ramp.outputs['Color'], ia)
ib.default_value = (1.4, 0.85, 0.4, 1)
links.new(io, bg.inputs['Color'])
bg.inputs['Strength'].default_value = 1.4
vol = nodes.new('ShaderNodeVolumePrincipled')
vol.inputs['Color'].default_value = (1.0, 0.55, 0.38, 1)
vol.inputs['Density'].default_value = float(os.environ.get('CITY3_HAZE', '0.0006'))
vol.inputs['Anisotropy'].default_value = 0.55
out_w = nodes['World Output']
scene.world = world
# The haze: a volume box round the views (renders only; the site has its own fog). (A world volume blacked out the sky.)
hm = bpy.data.materials.new('RenderHaze')
hm.use_nodes = True
hn = hm.node_tree
hn.nodes.remove(hn.nodes['Principled BSDF'])
hv = hn.nodes.new('ShaderNodeVolumePrincipled')
hv.inputs['Color'].default_value = vol.inputs['Color'].default_value
hv.inputs['Density'].default_value = vol.inputs['Density'].default_value
hv.inputs['Anisotropy'].default_value = 0.6
hn.links.new(hv.outputs['Volume'], hn.nodes['Material Output'].inputs['Volume'])
bpy.ops.mesh.primitive_cube_add(size=2.0)
haze_box = bpy.context.active_object
haze_box.name = 'RenderHaze'
haze_box.data.materials.append(hm)
haze_box.hide_render = True


def haze_round(v, size=700.0):
    haze_box.location = v.eye + Vector((0, 0, size * 0.25))
    haze_box.scale = (size, size, size * 0.4)
    # A soft warm fill from behind the camera (the concept's bounce light: faces toward us aren't black).
    cf.rotation_mode = 'QUATERNION'
    cf.rotation_quaternion = (v.fwd + Vector((0, 0, -0.35))).normalized().to_track_quat('-Z', 'Y')


cfl = bpy.data.lights.new('CamFill', 'SUN')
cfl.energy = 1.3
cfl.color = (1.0, 0.58, 0.42)
cfl.angle = math.radians(30)
if hasattr(cfl, 'use_shadow'):
    cfl.use_shadow = False
cf = bpy.data.objects.new('CamFill', cfl)
scene.collection.objects.link(cf)

# 1. Object IDs (flat colours) for score.py.
ID = {'sun': (1, 1, 0), 'bike': (1, 0, 0), 'heart': (1, 0.5, 0), 'kerb': (0, 1, 1), 'rib_front': (0, 1, 0),
      'rib_back': (0, 0.5, 0), 'rib_inner': (0.5, 1, 0.5), 'plat_upper': (0.5, 0, 1), 'plat_lower': (1, 0, 0.5),
      'water': (0, 0, 1), 'glow': (1, 0, 1), 'other': (0.5, 0.5, 0.5)}


def id_of(o):
    n = o.name
    if o in bike_objs:
        return 'bike'
    if n == 'City3.Sun':
        return 'sun'
    if n == 'City3Heart':
        return 'heart'
    if n == 'City3.KerbStrip':
        return 'kerb'
    if n == 'City3.RibFront':
        return 'rib_front'
    if n == 'City3.RibBack':
        return 'rib_back'
    if n == 'City3.RibInner':
        return 'rib_inner'
    if n == 'City3.PlatformUpper':
        return 'plat_upper'
    if n == 'City3.PlatformLower':
        return 'plat_lower'
    if n == 'City3.Water':
        return 'water'
    if o.data and o.data.name == 'City3.M.HexGlow' and o.parent == G['Plaza']:
        return 'glow'
    return 'other'


def render_ids(view, path):
    for o in scene.objects:
        if o.type == 'MESH':
            o.color = (*ID[id_of(o)], 1)
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'FLAT'
    scene.display.shading.color_type = 'OBJECT'
    scene.display.shading.show_cavity = False
    scene.display.shading.show_object_outline = False
    scene.display.shading.show_specular_highlight = False
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = 'RGBA'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    hide = [o for o in scene.objects if o.name.startswith('City3.HazeSheet') or o.name == 'City3.MistFloor']
    for o in hide:
        o.hide_render = True
    set_cam(view)
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    for o in hide:
        o.hide_render = False
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = 'RGB'


def eevee():
    scene.render.engine = 'BLENDER_EEVEE'
    ee = scene.eevee
    ee.taa_render_samples = int(os.environ.get('CITY3_SAMPLES', '48'))
    for k_, v in (('use_raytracing', True), ('volumetric_end', 900.0), ('volumetric_tile_size', '4'),
                  ('volumetric_samples', 64), ('use_volumetric_shadows', True), ('volumetric_shadow_samples', 16),
                  ('use_shadows', True), ('shadow_ray_count', 2), ('shadow_step_count', 8)):
        if hasattr(ee, k_):
            try:
                setattr(ee, k_, v)
            except Exception as exc:
                print('eevee', k_, exc)
    haze_box.hide_render = False
    scene.view_settings.view_transform = 'AgX'
    for look in ('AgX - Punchy', 'AgX - Medium High Contrast'):
        try:
            scene.view_settings.look = look
            break
        except Exception:
            pass
    scene.view_settings.exposure = float(os.environ.get('CITY3_EXPOSURE', '-0.25'))
    # Bloom round the sun, the heart and the honeycomb (the site's post does its own).
    try:
        ng = bpy.data.node_groups.new('City3Comp', 'CompositorNodeTree')
        ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        rl = ng.nodes.new('CompositorNodeRLayers')
        gl = ng.nodes.new('CompositorNodeGlare')
        go = ng.nodes.new('NodeGroupOutput')
        gl.inputs['Type'].default_value = 'Bloom'
        gl.inputs['Threshold'].default_value = 0.9
        gl.inputs['Strength'].default_value = 0.55
        gl.inputs['Size'].default_value = 0.8
        ng.links.new(rl.outputs['Image'], gl.inputs['Image'])
        ng.links.new(gl.outputs['Image'], go.inputs['Image'])
        scene.compositing_node_group = ng
        scene.render.use_compositing = True
    except Exception as exc:
        print('compositor:', exc)


sl = bpy.data.lights.new('SunKey', 'SUN')
sl.energy = 8.0
sl.color = (1.0, 0.6, 0.36)
sl.angle = math.radians(1.5)
so = bpy.data.objects.new('SunKey', sl)
scene.collection.objects.link(so)
so.rotation_mode = 'QUATERNION'
so.rotation_quaternion = (-SUN_DIR).to_track_quat('-Z', 'Y')
fl = bpy.data.lights.new('SkyFill', 'SUN')
fl.energy = 1.2
fl.color = (1.0, 0.62, 0.58)
fo = bpy.data.objects.new('SkyFill', fl)
scene.collection.objects.link(fo)
fo.rotation_euler = (math.radians(40), 0, math.radians(200))
if hasattr(fl, 'use_shadow'):
    fl.use_shadow = False
# A warm point light inside the heart (the site pulses it; in Blender its glow should light the cage round it).
hl = bpy.data.lights.new('HeartGlow', 'POINT')
hl.energy = 2.5e5
hl.color = (1.0, 0.5, 0.18)
hl.shadow_soft_size = HEART_RX * 0.8
ho = bpy.data.objects.new('HeartGlow', hl)
scene.collection.objects.link(ho)
ho.location = HEART_C

if 'arrival' in VIEWS:
    render_ids(ARR, os.path.join(RENDERS, f'city3-arrival-ids-{ROUND}.png'))
if 'approach' in VIEWS:
    for o in bike_objs:
        o.hide_render = True
    render_ids(APP, os.path.join(RENDERS, f'city3-approach-ids-{ROUND}.png'))
    for o in bike_objs:
        o.hide_render = False

if os.environ.get('CITY3_NO_EEVEE') != '1':
    eevee()
    if 'arrival' in VIEWS:
        set_cam(ARR)
        haze_round(ARR, 260.0)
        scene.render.filepath = os.path.join(RENDERS, f'city3-arrival-{ROUND}.png')
        bpy.ops.render.render(write_still=True)
    for o in bike_objs:
        o.hide_render = True
    if 'approach' in VIEWS:
        set_cam(APP)
        haze_round(APP, 650.0)
        scene.render.filepath = os.path.join(RENDERS, f'city3-approach-{ROUND}.png')
        bpy.ops.render.render(write_still=True)
    if 'exit' in VIEWS:
        set_cam(EXIT)
        haze_round(EXIT, 650.0)
        scene.render.filepath = os.path.join(RENDERS, f'city3-exit-{ROUND}.png')
        bpy.ops.render.render(write_still=True)
    for o in bike_objs:
        o.hide_render = False

# The plan: straight down, orthographic; the roads, BikeMark, RoadIn, END and the cameras drawn over it.
if 'plan' in VIEWS:
    haze_box.hide_render = True
    for o in bike_objs:
        o.hide_render = True
    hide = [o for o in scene.objects if o.name in ('City3.Sun', 'City3.MistFloor') or o.name.startswith('City3.Haze')]
    for o in hide:
        o.hide_render = True
    PLAN_C, PLAN_S, PLAN_PX = Vector((1450.0, 0.0)), 3200.0, 1600
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = PLAN_S
    cam.data.sensor_fit = 'AUTO'
    cam.location = (PLAN_C.x, PLAN_C.y, 1500)
    cam.rotation_mode = 'XYZ'
    cam.rotation_euler = (0, 0, 0)
    cam.data.clip_end = 5000
    scene.render.resolution_x = scene.render.resolution_y = PLAN_PX
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'MATERIAL'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    plan = os.path.join(RENDERS, 'city3-plan.png')
    scene.render.filepath = plan
    bpy.ops.render.render(write_still=True)

    def px(v):
        return [round((v[0] - PLAN_C.x) / PLAN_S * PLAN_PX + PLAN_PX / 2, 1),
                round(PLAN_PX / 2 - (v[1] - PLAN_C.y) / PLAN_S * PLAN_PX, 1)]

    marks = {'line': [px(p) for p in ROAD_LINE], 'out': [px(p) for p in OUT_LINE], 'bike': px(BIKE_AT),
             'roadin': px((0, 0)), 'end': px(OUT_END), 'arrival': px(EYE),
             'arrival_look': px(EYE + (LOOK - EYE).normalized() * 120), 'approach': px(APP_EYE),
             'approach_look': px(APP_EYE + (APP_LOOK - APP_EYE).normalized() * 120), 'exit': px(EXIT_EYE),
             'exit_look': px(EXIT_EYE + (EXIT_LOOK - EXIT_EYE).normalized() * 120),
             'title': f'City3 plan: road in {ROAD_LEN:.0f} m, out {OUT_LEN:.0f} m; 1 px = {PLAN_S / PLAN_PX:.2f} m'}
    draw = """
import json, sys
from PIL import Image, ImageDraw
m = json.load(open(sys.argv[2]))
im = Image.open(sys.argv[1]).convert('RGB')
d = ImageDraw.Draw(im)
d.line([tuple(p) for p in m['line']], fill=(255, 40, 40), width=2)
d.line([tuple(p) for p in m['out']], fill=(255, 160, 0), width=2)
for k, col in (('arrival', (0, 255, 255)), ('approach', (255, 255, 0)), ('exit', (120, 255, 120))):
    d.line([tuple(m[k]), tuple(m[k + '_look'])], fill=col, width=3)
    d.ellipse([m[k][0] - 5, m[k][1] - 5, m[k][0] + 5, m[k][1] + 5], outline=col, width=2)
for k, col in (('bike', (255, 0, 255)), ('roadin', (0, 255, 0)), ('end', (255, 255, 255))):
    d.ellipse([m[k][0] - 7, m[k][1] - 7, m[k][0] + 7, m[k][1] + 7], fill=col)
d.rectangle([0, 0, 1600, 26], fill=(0, 0, 0))
d.text((8, 7), m['title'] + '   red: RoadPath  orange: RoadOut  green: RoadIn  magenta: BikeMark  white: END  '
       'cyan: ArrivalCam  yellow: ApproachCam  light green: ExitCam', fill=(255, 255, 255))
im.save(sys.argv[1])
"""
    mj = os.path.join(ALIGN, 'out', 'plan-marks.json')
    with open(mj, 'w') as f:
        json.dump(marks, f)
    try:
        subprocess.run(['python3', '-c', draw, plan, mj], check=True)
    except Exception as exc:
        print('plan overlay skipped:', exc)

stats = {'road_in_m': round(ROAD_LEN, 2), 'road_out_m': round(OUT_LEN, 2), 'end': r4(OUT_END),
         'end_heading': round(OUT_H, 6), 'bike': r4(BIKE_AT), 'arrival_three': {'eye': three(EYE), 'look': three(LOOK),
                                                                                'fov': round(FOV, 3)},
         'approach_three': {'eye': three(APP_EYE), 'look': three(APP_LOOK), 'fov': APP_FOV},
         'glb_bytes': GLB_SIZE, 'min_x': round(MIN_X, 2), 'tris_unique': TRI_UNIQUE, 'tris_drawn': TRI_TOTAL, 'objects': len(meshes)}
with open(os.path.join(ALIGN, 'out', 'build-stats.json'), 'w') as f:
    json.dump(stats, f, indent=1)
print('STATS', stats)
if 'arrival' in VIEWS or 'approach' in VIEWS:
    try:
        subprocess.run(['python3', os.path.join(ALIGN, 'score.py'), ROUND], check=True, cwd=ALIGN)
    except Exception as exc:
        print('score skipped:', exc)
