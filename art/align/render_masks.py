"""The scene side of the landing-shot alignment: runs inside Blender on art/city.blend with public/models/bike.glb imported
(in memory only; nothing is saved over the .blend files).

  blender --background art/city.blend --python art/align/render_masks.py -- --export [pose.json]
      Writes art/align/scene-geometry.npz: everything score.py needs to project the scene analytically, without Blender:
        bike_pts      area-weighted surface samples of the bike (bike frame: origin on the ground between the wheels,
                      +x forward, z up, the 5 deg kickstand lean included), for the silhouette
        headlight     the lens's centre (the BikeEye faces) and its radius
        wheel_*       each tyre's axle centre, spin axis, outer radius and half width (from the BikeTyre faces)
        sky_pts       points sampled along the edges of everything that can stand against the sky (towers, spire,
                      viaduct, lamps, gantry), pruned to those near the upper envelope seen from round the landing eye
        gantry_pts    points along the gantry's edges (no ooze, no piers), for its lower boundary
        (ALIGN_SCENE=path overrides the output; pose.json prunes the sky points round that pose's eye)
        lines         3-D segments of the deck's long edges (kerb, kerb rail, the lower carriageway's barrier and rails),
                      read off the meshes in the road's frame and checked against them
  blender --background art/city.blend --python art/align/render_masks.py -- --render pose.json out/prefix
      Renders 1280x720 Workbench passes for a pose ({"EYE", "LOOK", "FOV", "BIKE_AT", "BIKE_YAW"}):
        prefix-ids.png     flat object colours: bike red, gantry green, deck/kerb/rails blue, the rest of the city
                           white, sky black (bike mask, sky mask and so the skyline)
        prefix-shaded.png  studio-lit greys, for the render's edge map in the onion skins
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
BIKE_GLB = os.path.join(ROOT, 'public', 'models', 'bike.glb')
SCENE_NPZ = os.environ.get('ALIGN_SCENE', os.path.join(HERE, 'scene-geometry.npz'))
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
EYE0 = np.array([11.5, -7.71, -10.02])
LOOK0 = np.array([71.18, -10.84, -15.33])


def import_bike():
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=BIKE_GLB)
    objs = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    bpy.context.view_layer.update()
    return objs


def mesh_arrays(o):
    """World-space vertices, triangles (with material index) of an evaluated mesh."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    M = np.array(o.matrix_world)
    co = co @ M[:3, :3].T + M[:3, 3]
    nt = len(me.loop_triangles)
    tri = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get('vertices', tri)
    mat = np.empty(nt, np.int64)
    me.loop_triangles.foreach_get('material_index', mat)
    ne = len(me.edges)
    ed = np.empty(ne * 2, np.int64)
    me.edges.foreach_get('vertices', ed)
    names = [m.name if m else '' for m in o.data.materials]
    ev.to_mesh_clear()
    return co, tri.reshape(-1, 3), mat, ed.reshape(-1, 2), names


def sample_surface(co, tri, n, rng):
    a, b, c = co[tri[:, 0]], co[tri[:, 1]], co[tri[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    k = rng.choice(len(tri), n, p=area / area.sum())
    u, v = rng.random(n), rng.random(n)
    flip = u + v > 1
    u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    return a[k] + (b[k] - a[k]) * u[:, None] + (c[k] - a[k]) * v[:, None], area.sum()


def sample_edges(co, ed, step_rad=0.0004, eye=None):
    """Points along mesh edges at about step_rad of angle as seen from `eye`."""
    eye = EYE0 if eye is None else eye
    p, q = co[ed[:, 0]], co[ed[:, 1]]
    L = np.linalg.norm(q - p, axis=1)
    dist = np.maximum(np.linalg.norm((p + q) / 2 - eye, axis=1), 1.0)
    n = np.clip(np.ceil(L / (dist * step_rad)).astype(int), 1, 4000) + 1
    idx = np.repeat(np.arange(len(ed)), n)
    t = np.concatenate([np.linspace(0, 1, k) for k in n]) if len(n) < 20000 else None
    if t is None:  # vectorised ramps
        start = np.repeat(np.cumsum(n) - n, n)
        t = (np.arange(n.sum()) - start) / np.repeat(n - 1, n)
    return p[idx] + (q[idx] - p[idx]) * t[:, None]


def export():
    rng = np.random.default_rng(1)
    out = {}
    # --- The bike, in its own frame (imported at the origin, unrotated: exactly the glb's frame).
    bike = import_bike()
    pts, area = [], 0.0
    eye_v = []
    for o in bike:
        co, tri, mat, ed, names = mesh_arrays(o)
        pts.append((co, tri))
        area += 0.5 * np.linalg.norm(np.cross(co[tri[:, 1]] - co[tri[:, 0]], co[tri[:, 2]] - co[tri[:, 0]]), axis=1).sum()
        if 'BikeEye' in names:
            k = names.index('BikeEye')
            vi = np.unique(tri[mat == k])
            eye_v.append(co[vi])
        if o.name.startswith('Wheel'):
            ax = np.array(o.matrix_world.to_3x3() @ Vector((0, 1, 0)))
            ax /= np.linalg.norm(ax)
            c = np.array(o.matrix_world.translation)
            k = names.index('BikeTyre')
            tv = co[np.unique(tri[mat == k])]
            d = tv - c
            along = d @ ax
            radial = np.linalg.norm(d - along[:, None] * ax, axis=1)
            key = 'wheel_front' if 'Front' in o.name else 'wheel_rear'
            out[key] = np.r_[c, ax, radial.max(), np.abs(along).max()]
            print(key, 'axle', c.round(3), 'axis', ax.round(3), 'r', radial.max().round(3), 'half width', np.abs(along).max().round(3))
    n_total = 320000
    samples = []
    for co, tri in pts:
        a = 0.5 * np.linalg.norm(np.cross(co[tri[:, 1]] - co[tri[:, 0]], co[tri[:, 2]] - co[tri[:, 0]]), axis=1).sum()
        s, _ = sample_surface(co, tri, max(2000, int(n_total * a / area)), rng)
        samples.append(s)
    out['bike_pts'] = np.concatenate(samples).astype(np.float32)
    ev = np.concatenate(eye_v)
    # The lens is a dome facing out of the head: its centre is the mean of its rim, its radius the rim's spread.
    c = ev.mean(axis=0)
    u, s, vt = np.linalg.svd(ev - c)
    normal = vt[2]
    if normal[0] < 0:
        normal = -normal
    h = (ev - c) @ normal
    rim = ev[h < np.percentile(h, 30)]
    rc = rim.mean(axis=0)
    rr = np.linalg.norm(rim - rc, axis=1).max()
    apex = ev[np.argmax(h)]
    out['headlight'] = np.r_[rc, normal, rr, apex]
    print('headlight rim centre', rc.round(3), 'normal', normal.round(3), 'radius', round(float(rr), 3), 'apex', apex.round(3))
    print('bike samples', len(out['bike_pts']), 'area m2', round(area, 2), 'bbox', out['bike_pts'].min(0).round(2), out['bike_pts'].max(0).round(2))
    for o in bike:
        bpy.data.objects.remove(o)

    # --- The city: points along edges that can stand against the sky.
    fwd = (LOOK0 - EYE0) / np.linalg.norm(LOOK0 - EYE0)
    sky_objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('City.') and o.name not in (
        'City.Deck', 'City.DeckBeams', 'City.Rails', 'City.Puddle', 'City.Freeway2', 'City.Freeway2Rails')]
    allp, alli = [], []
    for i, o in enumerate(sky_objs):
        co, tri, mat, ed, names = mesh_arrays(o)
        p = sample_edges(co, ed)
        allp.append(p)
        alli.append(np.full(len(p), i, np.int16))
        print('edges', o.name, len(ed), '->', len(p))
    P = np.concatenate(allp)
    I = np.concatenate(alli)
    v = P - EYE0
    dist = np.linalg.norm(v, axis=1)
    az = np.degrees(np.arctan2(v[:, 1], v[:, 0]))
    el = np.degrees(np.arcsin(v[:, 2] / dist))
    az0 = np.degrees(np.arctan2(fwd[1], fwd[0]))
    keep = np.abs(((az - az0 + 180) % 360) - 180) < 60
    P, I, az, el, dist = P[keep], I[keep], az[keep], el[keep], dist[keep]
    b = np.floor(az / 0.03).astype(int)
    b -= b.min()
    top = np.full(b.max() + 1, -90.0)
    np.maximum.at(top, b, el)
    margin = np.where(dist < 60, 30.0, np.where(dist < 200, 6.0, 2.5))
    keep = el >= top[b] - margin
    out['sky_pts'] = P[keep].astype(np.float32)
    out['sky_obj'] = I[keep]
    out['sky_obj_names'] = np.array([o.name for o in sky_objs])
    print('sky points', len(P), '->', keep.sum())

    g = []
    for name in ('City.Gantry', 'City.GantryPanels', 'City.GantryLamps'):
        co, tri, mat, ed, names = mesh_arrays(bpy.data.objects[name])
        g.append(sample_edges(co, ed, step_rad=0.0008))
    out['gantry_pts'] = np.concatenate(g).astype(np.float32)
    print('gantry points', len(out['gantry_pts']))

    # --- The deck's long edges, in the road frame: s along the road (RD), lateral to its left (RL), z off the deck. The
    # frame is the build's: origin abreast the bike's mark, heading from the DeckTop marker.
    mark = bpy.data.objects['City.BikeMark']
    top_ = bpy.data.objects['City.DeckTop']
    heading = top_.matrix_world.to_euler().z
    RD = np.array([math.cos(heading), math.sin(heading), 0.0])
    RL = np.array([-RD[1], RD[0], 0.0])
    # DeckTop sits at road(ROAD_MID_S, DRIVE_L) (build-city.py: (ROAD_AHEAD - ROAD_BACK) / 2 = 190 along, midway
    # between the kerb face and the near barrier's foot = 3.775 across), so the frame survives the bike moving off
    # its build-time mark (rebuild_scratch.py keeps the deck where it is).
    O = np.array(top_.matrix_world.translation) - RD * 190.0 - RL * ((9.0 - 0.6 - 0.85) / 2)
    print('road origin', O.round(3), 'bike mark', np.array(mark.matrix_world.translation).round(3))
    # (lateral, z) of each line, from build-city.py's profiles; verified below against the meshes' vertices.
    LINES = {
        'kerb foot': ('City.DeckBeams', -0.85, 0.0),  # where the deck meets the kerb's inner face
        'kerb inner top': ('City.DeckBeams', -0.85, 0.12),
        'kerb top': ('City.DeckBeams', -0.95, 0.22),  # the kerb's flat top, inner edge
        'kerb outer top': ('City.DeckBeams', -1.25, 0.22),
        'kerb rail top': ('City.Rails', -1.08, 0.44),  # the low W-beam rail on stubby posts (centre 0.36)
        'kerb rail bottom': ('City.Rails', -1.08, 0.28),
        'deck outer bottom': ('City.Deck', -1.25, -1.2),
        'fw2 barrier top': ('City.Freeway2', -4.9, -4.65 + 0.9),
        'fw2 barrier top inner': ('City.Freeway2', -5.1, -4.65 + 0.9),
        'fw2 barrier foot': ('City.Freeway2', -5.5, -4.65 + 0.0),
        'fw2 rail high': ('City.Freeway2Rails', -4.95, -4.65 + 1.42 + 0.07),
        'fw2 rail high bottom': ('City.Freeway2Rails', -4.95, -4.65 + 1.42 - 0.07),
        'fw2 rail low': ('City.Freeway2Rails', -4.95, -4.65 + 1.12 + 0.07),
    }
    s0, s1 = -140.0, 520.0
    lines = {}
    cache = {}
    for name, (obj, lat, z) in LINES.items():
        if obj not in cache:
            co = mesh_arrays(bpy.data.objects[obj])[0]
            d = co - O
            cache[obj] = np.c_[d @ RD, d @ RL, d[:, 2]]
        loc = cache[obj]
        near = (np.abs(loc[:, 1] - lat) < 0.012) & (np.abs(loc[:, 2] - z) < 0.012)
        ok = int(near.sum())
        print(f'line {name:22s} lat {lat:7.3f} z {z:7.3f}  mesh verts on it: {ok}')
        a = O + RD * s0 + RL * lat + np.array([0, 0, z])
        b = O + RD * s1 + RL * lat + np.array([0, 0, z])
        lines[name] = np.r_[a, b, ok]
    out['line_names'] = np.array(list(lines.keys()))
    out['lines'] = np.array(list(lines.values()))
    out['road_frame'] = np.r_[O, RD, RL]
    out['deck'] = np.array([-0.85, 9.0 - 0.6, top_.matrix_world.translation.z])  # drivable lateral range, deck z
    np.savez_compressed(SCENE_NPZ, **out)
    print('wrote', SCENE_NPZ)


def setup_render(pose):
    scene = bpy.context.scene
    bike = import_bike()
    rig = bpy.data.objects.new('BikeRig', None)
    scene.collection.objects.link(rig)
    rig.location = pose['BIKE_AT']
    rig.rotation_euler = (0, 0, math.radians(pose['BIKE_YAW']))
    for o in bike:
        if o.parent is None:
            o.parent = rig
    cam = bpy.data.objects.get('LandingCam')
    eye, look = Vector(pose['EYE']), Vector(pose['LOOK'])
    cam.location = eye
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (look - eye).to_track_quat('-Z', 'Y')
    cam.data.sensor_fit = 'VERTICAL'
    cam.data.sensor_height = 24
    cam.data.lens = 12 / math.tan(math.radians(pose['FOV'] / 2))
    cam.data.clip_start = 0.05
    cam.data.clip_end = 5000
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.render.resolution_percentage = 100
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.film_transparent = False
    scene.view_settings.view_transform = 'Standard'
    scene.display_settings.display_device = 'sRGB'
    scene.render.image_settings.file_format = 'PNG'
    sh = scene.display.shading
    sh.show_cavity = False
    sh.show_object_outline = False
    sh.show_shadows = False
    sh.show_specular_highlight = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new('W')
    scene.world.color = (0, 0, 0)
    scene.render.filter_size = 0.0  # crisp masks
    scene.render.dither_intensity = 0.0
    return bike


def render(pose_path, prefix):
    with open(pose_path) as f:
        pose = json.load(f)
    bike = setup_render(pose)
    scene = bpy.context.scene
    sh = scene.display.shading
    sh.light = 'FLAT'
    sh.color_type = 'OBJECT'
    sh.background_type = 'WORLD'
    bike_set = set(bike)
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        if o in bike_set:
            o.color = (1, 0, 0, 1)
        elif o.name.startswith('City.Gantry') and o.name != 'City.GantryPiers':
            o.color = (0, 1, 0, 1)
        elif o.name in ('City.Deck', 'City.DeckBeams', 'City.Rails', 'City.Puddle', 'City.Freeway2', 'City.Freeway2Rails'):
            o.color = (0, 0, 1, 1)
        else:
            o.color = (1, 1, 1, 1)
    scene.render.filepath = prefix + '-ids.png'
    bpy.ops.render.render(write_still=True)
    sh.light = 'STUDIO'
    sh.color_type = 'SINGLE'
    sh.single_color = (0.8, 0.8, 0.8)
    scene.render.filter_size = 1.5
    scene.render.filepath = prefix + '-shaded.png'
    bpy.ops.render.render(write_still=True)
    print('rendered', prefix)


if '--export' in ARGS:
    i = ARGS.index('--export')
    if len(ARGS) > i + 1:  # prune the sky points round another eye (a pose json)
        with open(ARGS[i + 1]) as f:
            _p = json.load(f)
        EYE0, LOOK0 = np.array(_p['EYE']), np.array(_p['LOOK'])
    export()
elif '--render' in ARGS:
    i = ARGS.index('--render')
    render(ARGS[i + 1], ARGS[i + 2])
