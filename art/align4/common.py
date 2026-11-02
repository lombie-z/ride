"""Shared helpers for the data desert's arrival-shot alignment (art/align4/, after art/align2/).

Paths, the concept image (art/reference/concept-desert.webp at 1280x720), the pinhole projection the arrival camera uses
(vertical FOV, no roll, LOOK via to_track_quat('-Z', 'Y')), and circle fitting.
Frames:
  road   the arrival's road: the deck's centreline along +X, its left edge at +Y, deck top z 0, the camera's foot at x 0
         (fit_camera.py fits the camera and the bike in it; art/build-city4.py lines this up with City4's last straight)
  bike   the bike at the origin on the deck, its front along +X (City4.BikeMark): arrival-camera.json's EYE/LOOK
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(HERE, 'out')
CONCEPT = os.path.join(ROOT, 'art', 'reference', 'concept-desert.webp')
CONCEPT_APPROACH = os.path.join(ROOT, 'art', 'reference', 'concept-transition-desert.webp')
FEATURES = os.path.join(HERE, 'concept-features.json')
APPROACH_FEATURES = os.path.join(HERE, 'approach-features.json')
CAMERA = os.path.join(HERE, 'arrival-camera.json')  # written by fit_camera.py, read by art/build-city4.py
BIKE_GLB = os.path.join(ROOT, 'public', 'models', 'bike.glb')
W, H = 1280, 720
ROAD_W = 11.8          # the site's deck width
BARRIER_Y = 6.3        # the jersey barriers' inner top edge, either side of the centreline (build-city4.py BARRIER_*)
BARRIER_TOP = 0.7      # their height over the deck (low concrete blocks, sand drifted against them)


def concept_rgb(path=CONCEPT):
    from PIL import Image
    im = Image.open(path).convert('RGB').resize((W, H), Image.LANCZOS)
    return np.asarray(im).astype(np.float64) / 255.0


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, 'w') as f:
        json.dump(obj, f, indent=1)


# --- Camera ----------------------------------------------------------------------------------------------------------
def cam_basis(eye, look):
    """Blender's to_track_quat('-Z', 'Y'): forward to LOOK, right = forward x z-up, no roll."""
    eye, look = np.asarray(eye, float), np.asarray(look, float)
    f = look - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, [0.0, 0.0, 1.0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return f, r, u


def project(P, eye, look, fov_deg, w=W, h=H):
    """Points (N, 3) -> pixel (N, 2) and depth along the view (N,)."""
    f, r, u = cam_basis(eye, look)
    v = np.asarray(P, float) - np.asarray(eye, float)
    d = v @ f
    tv = np.tan(np.radians(fov_deg) / 2)
    th = tv * w / h
    dd = np.where(np.abs(d) < 1e-9, 1e-9, d)
    sx = w / 2 * (1 + (v @ r) / (dd * th))
    sy = h / 2 * (1 - (v @ u) / (dd * tv))
    return np.c_[sx, sy], d


def horizon_row(eye, look, fov_deg, h=H):
    """The row where the plane at eye height (the true horizon) crosses the frame's centre column."""
    f, r, u = cam_basis(eye, look)
    pitch = np.arcsin(f[2])
    return h / 2 * (1 + np.tan(pitch) / np.tan(np.radians(fov_deg) / 2))


def road_line(eye, look, fov, y, z, x0=2.0, x1=400.0, n=80):
    """A line along the road (x from x0 to x1 ahead of the camera, at lateral y and height z) projected: pixel points,
    only those in front of the camera."""
    xs = np.geomspace(x0, x1, n)
    P = np.c_[xs, np.full(n, y), np.full(n, z)]
    uv, d = project(P, eye, look, fov)
    return uv[d > 0.1]


# --- Fitting ---------------------------------------------------------------------------------------------------------
def fit_circle(x, y):
    """Algebraic (Kasa) circle fit: (cx, cy, r)."""
    A = np.c_[2 * x, 2 * y, np.ones_like(x)]
    b = x * x + y * y
    (cx, cy, c), *_ = np.linalg.lstsq(A, b, rcond=None)
    return float(cx), float(cy), float(np.sqrt(c + cx * cx + cy * cy))


def ransac_circle(x, y, thr=1.5, trials=2000, accept=None, seed=0):
    rng = np.random.default_rng(seed)
    best, best_n = None, 0
    for _ in range(trials):
        idx = rng.choice(len(x), 3, replace=False)
        try:
            c = fit_circle(x[idx], y[idx])
        except Exception:
            continue
        if not np.isfinite(c[2]) or (accept and not accept(c)):
            continue
        inl = np.abs(np.hypot(x - c[0], y - c[1]) - c[2]) < thr
        if inl.sum() > best_n:
            best, best_n = inl, inl.sum()
    if best is None:
        return None, None
    return fit_circle(x[best], y[best]), best


def resample_polyline(pts, n=64):
    pts = np.asarray(pts, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    s = np.r_[0, np.cumsum(seg)]
    t = np.linspace(0, s[-1], n)
    return np.c_[np.interp(t, s, pts[:, 0]), np.interp(t, s, pts[:, 1])]


def point_to_polyline(p, line):
    """Distance (px) from points (N, 2) to a polyline."""
    p = np.asarray(p, float)
    a, b = np.asarray(line[:-1], float), np.asarray(line[1:], float)
    ab = b - a
    t = np.clip(((p[:, None, :] - a[None]) * ab[None]).sum(-1) / np.maximum((ab * ab).sum(-1), 1e-9)[None], 0, 1)
    q = a[None] + t[..., None] * ab[None]
    return np.hypot(*(p[:, None, :] - q).transpose(2, 0, 1)).min(axis=1)


def rows_of(polyline, x0, x1):
    """A polyline's row at each column x0..x1-1 (interpolated; it must run left to right)."""
    p = np.asarray(polyline, float)
    xs = np.arange(x0, x1)
    return np.interp(xs, p[:, 0], p[:, 1], left=np.nan, right=np.nan)


def box_iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    area = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / area if area > 0 else 0.0
