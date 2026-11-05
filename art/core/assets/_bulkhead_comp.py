"""The bulkhead group together, in the image's framing, to set against art/reference/concept-flooded-tunnel.webp. Not an asset: nothing
exported. The tube's the tube group's real ring; the water and lamps are stand-ins. Renders art/renders/assets/bulkhead-comp-<tag>.png.

    blender --background --factory-startup --python art/core/assets/_bulkhead_comp.py -- <tag> <yaw degrees> [hinge x] [eye x] [lamps on, e.g. 12]
Yaw as the door's script says: minus into the room. Prints the gap it leaves.
"""
import importlib
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bulkhead as H  # noqa: E402
import _common as A  # noqa: E402
import _mats  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
TAG = argv[0] if argv else 'gap14'
YAW = float(argv[1]) if len(argv) > 1 else -81.5
HX = float(argv[2]) if len(argv) > 2 else H.HINGE[0]
EYE_X = float(argv[3]) if len(argv) > 3 else -27.0
LAMPS_ON = [int(c) for c in argv[4]] if len(argv) > 4 else []

kit = A.begin()
H.register(kit)
m = _mats.mats(kit)


def tex_water():
    n = 256
    u = (np.arange(n) + 0.5) / n
    rows = np.linspace(1, 0, n)
    out = np.zeros((n, n, 3))
    ripple = kit.vnoise(n, 40, 3, 3)
    ripple2 = np.repeat(kit.vnoise(n, 6, 4, 3)[:, :1], n, axis=1)
    fade = rows[:, None] ** 1.2
    streak = np.exp(-((u[None, :] - 0.55) / 0.09) ** 2) * fade * (0.45 + 0.9 * ripple)
    out[..., 0] = np.clip(0.035 + 0.3 * streak * (0.6 + ripple2), 0, 1)
    out[..., 1] = 0.04 + 0.03 * ripple
    out[..., 2] = 0.035 + 0.02 * ripple
    return out


kit.register_texture('mockwater', tex_water)
water = kit.material('City5MockWater', (0, 0, 0), 1.0, vcol=False, tex='mockwater', emission=(1, 1, 1), strength=1.0, emit_tex=True, spec=0.0)

for name in ('bulkhead_frame', 'bulkhead_door', 'red_room_shell', 'red_tank', 'tube_ring_8'):
    globals()[name] = importlib.import_module(name)

frame = A.obj(bulkhead_frame.build(kit, m), 'bulkhead_frame', (0, 0, H.CZ))
door = bulkhead_door.place(kit, m, (HX, H.HINGE[1], H.CZ), math.radians(YAW))
for i in LAMPS_ON:
    mat = m[f'bulkhead_lamp_{i}']
    mat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 4.0
A.obj(red_room_shell.build(kit, m), 'red_room_shell')
tank_me = red_tank.build(kit, m)
for i, (x, y) in enumerate(H.TANKS):
    A.obj(tank_me, f'red_tank{i}', (x, y, H.TANK_BASE_Z))
ring = tube_ring_8.build(kit, m)
for k in range(1, 8):
    A.obj(ring, f'ring{k}', (-8.0 * (k + 0), 0, 0))

# Stand-ins: water, the tunnel's lamps.
wm = bpy.data.meshes.new('water')
wm.from_pydata([(-60, -9, 0.35), (3, -9, 0.35), (3, 9, 0.35), (-60, 9, 0.35)], [], [(0, 1, 2, 3)])
uv = wm.uv_layers.new(name='UVMap')
uv.data.foreach_set('uv', [0.2, 0.2, 1, 0.2, 1, 0.8, 0.2, 0.8])
wm.materials.append(water)
A.obj(wm, 'water_mock')
# (Black past the room's far opening, where the servers will be.)
bk = bpy.data.meshes.new('beyond')
bk.from_pydata([(70.6, 9, 0), (70.6, -9, 0), (70.6, -9, 9), (70.6, 9, 9)], [], [(0, 1, 2, 3)])
bk.materials.append(kit.material('City5MockBlack', (0, 0, 0), 1.0, vcol=False, spec=0.0))
A.obj(bk, 'beyond')
for s, x, z in ((1, -14.0, 3.6), (-1, -14.0, 3.6), (1, -22.0, 3.6), (-1, -22.0, 3.6)):
    y = s * 8.3
    me = bpy.data.meshes.new('lampg')
    me.from_pydata([(x, y, z), (x + 0.9, y - s * 0.4, z), (x + 0.9, y - s * 0.4, z + 1.1), (x, y, z + 1.1)], [], [(0, 1, 2, 3)])
    me.materials.append(m['lamp_green'])
    A.obj(me, 'lamp')

# How wide a gap: the road's side of the door, at its free edge.
yaw = math.radians(YAW)
free = 2 * H.DOOR_D / 2 + (H.DOOR_CY - H.DOOR_D / 2)
fx, fy = HX - math.sin(yaw) * free, H.HINGE[1] + math.cos(yaw) * free
nx, ny = -math.cos(yaw), -math.sin(yaw)
corner = max(fy, fy + ny * H.DOOR_T / 2)
print(f'COMP {TAG}: free edge ({fx:.1f}, {fy:.1f}), road-side corner y {corner:.2f}, gap to y +8.5: {8.5 - corner:.2f}')

scene = bpy.context.scene
eye = Vector((EYE_X, 2.3 if EYE_X == -27.0 else 0.0, 1.55))
look = Vector((0.0, 4.87, 2.55)) if EYE_X == -27.0 else Vector((0.0, 0.0, 4.6))
scene.render.resolution_percentage = 100
tmp = A.STILLS
A.still(f'bulkhead-comp-{TAG}', eye=eye, look_at=look, fov=70.0)
