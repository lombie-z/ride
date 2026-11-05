"""Puts the stairwell and tunnel on the site: python3 art/core/publish_sections.py (after art/core/stair.py and flood.py).
Copies art/out/city5-stair.glb, city5-flood.glb and the moving pieces to public/models/sections/, and lifts each glb's City5.RoadPath out into
public/models/sections/road.json, which is what the core's road is spliced from (lib/sections.ts), read before either glb is loaded."""
import json
import os
import shutil
import struct

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = os.path.join(ROOT, 'art', 'out')
SITE = os.path.join(ROOT, 'public', 'models', 'sections')
MOVING = ['flight_collapse', 'debris_set', 'beam_swing', 'shutter_slam']


def road_of(path):
    with open(path, 'rb') as fh:
        fh.seek(12)
        size = struct.unpack('<I', fh.read(4))[0]
        fh.read(4)
        gltf = json.loads(fh.read(size))
    return next(n['extras'] for n in gltf['nodes'] if n.get('name') == 'City5.RoadPath')


os.makedirs(SITE, exist_ok=True)
road = {}
for name in ('stair', 'flood'):
    src = os.path.join(OUT, f'city5-{name}.glb')
    road[name] = road_of(src)
    shutil.copyfile(src, os.path.join(SITE, f'{name}.glb'))
for name in MOVING:
    shutil.copyfile(os.path.join(OUT, 'assets', f'{name}.glb'), os.path.join(SITE, f'{name}.glb'))
with open(os.path.join(SITE, 'road.json'), 'w') as fh:
    json.dump(road, fh, separators=(',', ':'))
print('stair s0', road['stair']['s0'], 'length', road['stair']['length'], 'flood s0', road['flood']['s0'], 'length', road['flood']['length'], 'door', road['flood']['stop'])
