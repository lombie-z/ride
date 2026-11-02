"""Back-project the traced concept guides through ConceptCam4 onto a bike-local plane (the root's 5 deg lean undone),
to read the concept's parts in metres: python3 backproject.py y=0.2 | x=-1.0 | z=0 [name ...]
Prints bike-local (x, y, z) per traced point."""
import json, math, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
G = json.load(open(os.path.join(HERE, 'concept-bike4-guides.json')))
C = json.load(open(os.path.join(HERE, 'concept-cam4.json')))
W, H = C['size']
eye, look = np.array(C['location']), np.array(C['look'])
f = (look - eye) / np.linalg.norm(look - eye); r = np.cross(f, [0, 0, 1.0]); r /= np.linalg.norm(r); u = np.cross(r, f)
tv = math.tan(math.radians(C['vfov']) / 2); th = tv * W / H
L = math.radians(5)
ROT = np.array([[1, 0, 0], [0, math.cos(-L), -math.sin(-L)], [0, math.sin(-L), math.cos(-L)]])  # local -> world


def ray(px, py):
    d = f + r * ((px / (W / 2) - 1) * th) + u * ((1 - py / (H / 2)) * tv)
    return d / np.linalg.norm(d)


def on_plane(px, py, axis, val):
    n_loc = np.eye(3)[axis]
    n = ROT @ n_loc; p0 = ROT @ (n_loc * val)
    d = ray(px, py); t = (p0 - eye) @ n / (d @ n)
    return ROT.T @ (eye + d * t)


if __name__ == '__main__':
    ax, val = sys.argv[1].split('=')
    axis, val = 'xyz'.index(ax), float(val)
    names = sys.argv[2:]
    for kind in ('polygons', 'lines', 'points'):
        for name, pts in G[kind].items():
            if names and name not in names:
                continue
            if kind == 'points':
                pts = [pts]
            out = [tuple(np.round(on_plane(px, py, axis, val), 3)) for px, py in pts]
            print(kind[:-1], name, ' '.join(f'({a:+.3f},{b:+.3f},{c:.3f})' for a, b, c in out))
