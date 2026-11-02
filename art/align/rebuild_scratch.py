"""Rebuild the city for a new landing pose in a scratch directory, without touching art/build-city.py or its outputs.

  python3 art/align/rebuild_scratch.py POSE.json OUTDIR

build-city.py composes the skyline, spire, viaduct and gantry in the landing camera's screen space, so a new camera needs
a rebuild before its skyline can be judged. This writes OUTDIR/build-city-align.py, a copy of art/build-city.py with:
  - the landing (EYE, LOOK, LANDING_FOV, BIKE_AT, BIKE_YAW) set to POSE.json's
  - the deck kept exactly where it is now (road origin and heading frozen at the current build's), so the bike's
    optimised offset and yaw on the deck carry over
  - every output path (city.blend, city.glb, renders) redirected into OUTDIR, EEVEE skipped
then runs it in Blender headless. OUTDIR/city.blend is the scratch city; score it with render_masks.py on that file and
ALIGN_SCENE=OUTDIR/scene-geometry.npz.
"""
import json
import math
import os
import re
import subprocess
import sys

from common import CURRENT, ROOT

BLENDER = '/opt/homebrew/bin/blender'


def main():
    pose = json.load(open(sys.argv[1]))
    out = os.path.abspath(sys.argv[2])
    os.makedirs(os.path.join(out, 'renders'), exist_ok=True)
    src = open(os.path.join(ROOT, 'art', 'build-city.py')).read()
    road_heading = CURRENT['BIKE_YAW'] + 180.0
    o = CURRENT['BIKE_AT']
    v = [pose['LOOK'][i] - pose['EYE'][i] for i in range(3)]
    print('pose', pose, 'view yaw', round(math.degrees(math.atan2(v[1], v[0])), 3))

    def sub(pattern, repl, count=1):
        nonlocal src
        src, n = re.subn(pattern, repl, src, count=count, flags=re.M)
        assert n == count, pattern

    sub(r"^ROOT_DIR = .*$", f"ROOT_DIR = {ROOT!r}")
    sub(r"^BLEND = .*$", f"BLEND = {os.path.join(out, 'city.blend')!r}")
    sub(r"^GLB = .*$", f"GLB = {os.path.join(out, 'city.glb')!r}")
    sub(r"^RENDER = .*$", f"RENDER = {os.path.join(out, 'renders', 'city-landing.png')!r}")
    sub(r"^RENDER_EEVEE = .*$", f"RENDER_EEVEE = {os.path.join(out, 'renders', 'city-landing-eevee.png')!r}")
    sub(r"^MONTAGE = .*$", f"MONTAGE = {os.path.join(out, 'renders', 'city-montage.png')!r}")
    sub(r"^GUIDES = .*$", f"GUIDES = {os.path.join(ROOT, 'art', 'guides.py')!r}")
    sub(r"^print\('LANDING'", (
        "# --- art/align overrides\n"
        f"EYE = Vector({tuple(pose['EYE'])!r})\n"
        f"LOOK = Vector({tuple(pose['LOOK'])!r})\n"
        f"LANDING_FOV = {pose['FOV']!r}\n"
        f"BIKE_AT = Vector({tuple(pose['BIKE_AT'])!r})\n"
        f"BIKE_YAW = {pose['BIKE_YAW']!r}\n"
        "_bf = Vector((math.cos(math.radians(BIKE_YAW)), math.sin(math.radians(BIKE_YAW)), 0))\n"
        "_bl = Vector((-_bf.y, _bf.x, 0))\n"
        f"_ROAD_O = Vector({tuple(o)!r})\n"
        "print('LANDING'"))
    sub(r"^ROAD_HEADING = math\.radians\(BIKE_YAW \+ 180\.0\)", f"ROAD_HEADING = math.radians({road_heading!r})")
    sub(r"Vector\(\(BIKE_AT\.x, BIKE_AT\.y, DECK_Z\)\) \+ RD \* s", "Vector((_ROAD_O.x, _ROAD_O.y, DECK_Z)) + RD * s")
    path = os.path.join(out, 'build-city-align.py')
    open(path, 'w').write(src)
    env = dict(os.environ, CITY_NO_EEVEE='1')
    r = subprocess.run([BLENDER, '--background', '--factory-startup', '--python', path], env=env, capture_output=True,
                       text=True, cwd=ROOT)
    for line in r.stdout.splitlines():
        if line.startswith(('LANDING', 'DeckTop', 'gantry', 'viaduct', 'hero skipped', 'total tris', 'Error', 'Traceback')):
            print(line)
    if r.returncode:
        print(r.stdout[-3000:], r.stderr[-3000:])
        sys.exit(r.returncode)


if __name__ == '__main__':
    main()
