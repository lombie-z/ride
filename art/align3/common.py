"""Shared helpers for the coral hive's arrival and approach alignment (art/align3/, adapted from art/align2/ for the third city).

Paths, the two concepts at 1280x720 (art/reference/concept-hive-plaza.webp: the arrival, where the bike stops;
concept-hive-city.webp: the approach down the causeway), the pinhole projection the cameras use (vertical FOV, no roll, LOOK via to_track_quat('-Z', 'Y')) and ellipse / circle fitting.
Everything here is in City3's own local frame (Blender z up, metres, plaza floor z 0, the road in along +X).
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(HERE, 'out')
CONCEPT = os.path.join(ROOT, 'art', 'reference', 'concept-hive-plaza.webp')
CONCEPT_APPROACH = os.path.join(ROOT, 'art', 'reference', 'concept-hive-city.webp')
FEATURES = os.path.join(HERE, 'concept-features.json')            # the arrival's (extract_concept.py)
FEATURES_APPROACH = os.path.join(HERE, 'concept-approach-features.json')
CAMERA = os.path.join(HERE, 'arrival-camera.json')  # written by fit_camera.py, read by art/build-city3.py
CAMERA_APPROACH = os.path.join(HERE, 'approach-camera.json')
BIKE_GLB = os.path.join(ROOT, 'public', 'models', 'bike.glb')
W, H = 1280, 720
SRC_W, SRC_H = 1672, 941  # the concept's own size (the brief's bike box is given in it)


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
    """Local points (N, 3) -> pixel (N, 2) and depth along the view (N,)."""
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


# --- Ellipses and circles ----------------------------------------------------------------------------------------------
def fit_ellipse(x, y):
    """Direct least-squares ellipse fit (Fitzgibbon / Halir-Flusser). Conic (a,b,c,d,e,f) or None."""
    mx, my = x.mean(), y.mean()
    sc = max(x.std(), y.std(), 1e-9)
    xs, ys = (x - mx) / sc, (y - my) / sc
    D1 = np.c_[xs * xs, xs * ys, ys * ys]
    D2 = np.c_[xs, ys, np.ones_like(xs)]
    S1, S2, S3 = D1.T @ D1, D1.T @ D2, D2.T @ D2
    try:
        T = -np.linalg.solve(S3, S2.T)
    except np.linalg.LinAlgError:
        return None
    M = S1 + S2 @ T
    M = np.array([M[2] / 2, -M[1], M[0] / 2])
    _, v = np.linalg.eig(M)
    v = np.real(v)
    cond = 4 * v[0] * v[2] - v[1] ** 2
    k = np.nonzero(cond > 0)[0]
    if len(k) == 0:
        return None
    a1 = v[:, k[0]]
    a2 = T @ a1
    A, B, C, D, E, F = (*a1, *a2)
    A2, B2, C2 = A / sc ** 2, B / sc ** 2, C / sc ** 2
    D2_ = D / sc - 2 * A2 * mx - B2 * my
    E2 = E / sc - 2 * C2 * my - B2 * mx
    F2 = F + A2 * mx ** 2 + B2 * mx * my + C2 * my ** 2 - D / sc * mx - E / sc * my
    return np.array([A2, B2, C2, D2_, E2, F2])


def conic_to_params(con):
    A, B, C, D, E, F = con
    den = B * B - 4 * A * C
    if den >= 0:
        return None
    cx = (2 * C * D - B * E) / den
    cy = (2 * A * E - B * D) / den
    M = np.array([[A, B / 2], [B / 2, C]])
    F0 = A * cx * cx + B * cx * cy + C * cy * cy + D * cx + E * cy + F
    w, v = np.linalg.eigh(M)
    if F0 == 0 or np.any(-F0 / w <= 0):
        return None
    ax = np.sqrt(-F0 / w)
    th = np.arctan2(v[1, 0], v[0, 0])
    return float(cx), float(cy), float(ax[0]), float(ax[1]), float(th)


def sampson(con, x, y):
    A, B, C, D, E, F = con
    f = A * x * x + B * x * y + C * y * y + D * x + E * y + F
    gx = 2 * A * x + B * y + D
    gy = B * x + 2 * C * y + E
    return f / np.maximum(np.hypot(gx, gy), 1e-12)


def ransac_ellipse(x, y, thr=1.5, trials=3000, accept=None, seed=0):
    rng = np.random.default_rng(seed)
    best, best_n = None, 0
    for _ in range(trials):
        idx = rng.choice(len(x), 6, replace=False)
        con = fit_ellipse(x[idx], y[idx])
        if con is None:
            continue
        p = conic_to_params(con)
        if p is None or (accept and not accept(p)):
            continue
        inl = np.abs(sampson(con, x, y)) < thr
        if inl.sum() > best_n:
            best, best_n = inl, inl.sum()
    if best is None:
        return None, None
    con = fit_ellipse(x[best], y[best])
    return conic_to_params(con), best


def ellipse_box(p):
    """(cx, cy, half_w, half_h) of an ellipse's bounding box."""
    cx, cy, a, b, th = p
    hw = np.sqrt((a * np.cos(th)) ** 2 + (b * np.sin(th)) ** 2)
    hh = np.sqrt((a * np.sin(th)) ** 2 + (b * np.cos(th)) ** 2)
    return float(cx), float(cy), float(hw), float(hh)


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
    """n points evenly spaced along a polyline's length."""
    pts = np.asarray(pts, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    s = np.r_[0, np.cumsum(seg)]
    t = np.linspace(0, s[-1], n)
    return np.c_[np.interp(t, s, pts[:, 0]), np.interp(t, s, pts[:, 1])]


def polyline_distance(a, b):
    """Mean symmetric distance (px) between two polylines (each resampled to 64 points)."""
    a, b = resample_polyline(a), resample_polyline(b)
    d = np.hypot(a[:, None, 0] - b[None, :, 0], a[:, None, 1] - b[None, :, 1])
    return float((d.min(axis=1).mean() + d.min(axis=0).mean()) / 2)
