"""Back-project the traced concept guides through ConceptCam3 onto a bike-local plane (the root's 5 deg lean undone),
to read the concept's shapes in metres.
  python3 backproject.py y 0        -> (x, z) on the plane y = 0 (side profile)
  python3 backproject.py x -0.85    -> (y, z) on the plane x = -0.85 (a cross-section, e.g. the tail hood's face)
  python3 backproject.py z 0.95     -> (x, y) on the plane z = 0.95 (plan)
  add 'plaza' to use plaza-cam3.json and the plaza guides."""
import json, math, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
PLAZA = 'plaza' in sys.argv
G = json.load(open(os.path.join(HERE, 'concept-bike3-plaza-guides.json' if PLAZA else 'concept-bike3-guides.json')))
C = json.load(open(os.path.join(HERE, 'plaza-cam3.json' if PLAZA else 'concept-cam3.json')))
W, H = C['size']
eye, look = np.array(C['location']), np.array(C['look'])
f = (look - eye) / np.linalg.norm(look - eye); r = np.cross(f, [0, 0, 1.0]); r /= np.linalg.norm(r); u = np.cross(r, f)
tv = math.tan(math.radians(C['vfov']) / 2); th = tv * W / H
L = math.radians(5)
ROT = np.array([[1, 0, 0], [0, math.cos(L), math.sin(L)], [0, -math.sin(L), math.cos(L)]])  # local -> world
AX = {'x': 0, 'y': 1, 'z': 2}


def ray(px, py):
    d = f + r * ((px / (W / 2) - 1) * th) + u * ((1 - py / (H / 2)) * tv)
    return d / np.linalg.norm(d)


def on_plane(px, py, axis, val):
    nl = np.zeros(3); nl[AX[axis]] = 1
    n = ROT @ nl; p0 = ROT @ (nl * val)
    d = ray(px, py); t = (p0 - eye) @ n / (d @ n)
    return ROT.T @ (eye + d * t)


if __name__ == '__main__':
    a = [s for s in sys.argv[1:] if s != 'plaza']
    axis, val = (a[0], float(a[1])) if a else ('y', 0.0)
    keep = [i for i in range(3) if i != AX[axis]]
    for kind in ('polygons', 'lines', 'points'):
        for name, pts in G.get(kind, {}).items():
            if kind == 'points':
                pts = [pts]
            out = [tuple(np.round(on_plane(px, py, axis, val)[keep], 3)) for px, py in pts]
            print(kind[:-1], name, ' '.join(f'({a:+.3f},{b:+.3f})' for a, b in out))
