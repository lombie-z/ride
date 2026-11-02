"""Shared helpers for the landing-shot alignment pipeline (art/align/): paths, the concept image, ellipse fitting and the
pinhole projection the scene's landing camera uses (vertical FOV, no roll, LOOK via to_track_quat('-Z', 'Y'))."""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(HERE, 'out')
CONCEPT = os.path.join(ROOT, 'art', 'reference', 'concept-green-city.webp')
FEATURES = os.path.join(HERE, 'concept-features.json')
SCENE = os.environ.get('ALIGN_SCENE', os.path.join(HERE, 'scene-geometry.npz'))  # written by render_masks.py --export
W, H = 1280, 720

# The landing as built (art/build-city.py).
CURRENT = {
    'EYE': [-37.1575, -40.5503, -10.4121],
    'LOOK': [5.2472, 1.8544, -8.4911],
    'FOV': 42.979,
    'BIKE_AT': [-35.9138, -38.0126, -11.0],
    'BIKE_YAW': -71.167,
}
DECK_Z = -11.0


def concept_rgb():
    from PIL import Image
    im = Image.open(CONCEPT).convert('RGB').resize((W, H), Image.LANCZOS)
    return np.asarray(im).astype(np.float64) / 255.0


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, 'w') as f:
        json.dump(obj, f, indent=1)


# --- Ellipses --------------------------------------------------------------------------------------------------------
def fit_ellipse(x, y):
    """Direct least-squares ellipse fit (Fitzgibbon, Halir & Flusser's stable form). Returns the conic (a,b,c,d,e,f) of
    a x^2 + b xy + c y^2 + d x + e y + f = 0, or None."""
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
    w, v = np.linalg.eig(M)
    v = np.real(v)
    cond = 4 * v[0] * v[2] - v[1] ** 2
    k = np.nonzero(cond > 0)[0]
    if len(k) == 0:
        return None
    a1 = v[:, k[0]]
    a2 = T @ a1
    A, B, C, D, E, F = (*a1, *a2)
    # Undo the normalisation: x' = (x - mx) / sc.
    A2, B2, C2 = A / sc ** 2, B / sc ** 2, C / sc ** 2
    D2_ = D / sc - 2 * A2 * mx - B2 * my
    E2 = E / sc - 2 * C2 * my - B2 * mx
    F2 = F + A2 * mx ** 2 + B2 * mx * my + C2 * my ** 2 - D / sc * mx - E / sc * my
    return np.array([A2, B2, C2, D2_, E2, F2])


def conic_to_params(con):
    """(cx, cy, semi-axis along theta, other semi-axis, theta) of an ellipse conic, or None."""
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
    n = len(x)
    for _ in range(trials):
        idx = rng.choice(n, 6, replace=False)
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
    for _ in range(3):  # refit on the inliers
        con = fit_ellipse(x[best], y[best])
        if con is None:
            break
        best2 = np.abs(sampson(con, x, y)) < thr
        if best2.sum() < best.sum() * 0.9:
            break
        best = best2
    con = fit_ellipse(x[best], y[best])
    return conic_to_params(con), best


def ellipse_points(p, n=180):
    cx, cy, a, b, th = p
    t = np.linspace(0, 2 * np.pi, n)
    return (cx + a * np.cos(t) * np.cos(th) - b * np.sin(t) * np.sin(th),
            cy + a * np.cos(t) * np.sin(th) + b * np.sin(t) * np.cos(th))


def ellipse_summary(p):
    """Centre, the semi-axes as (horizontal-ish, vertical-ish) half extents, and the bounding half-width/height."""
    cx, cy, a, b, th = p
    hw = np.sqrt((a * np.cos(th)) ** 2 + (b * np.sin(th)) ** 2)
    hh = np.sqrt((a * np.sin(th)) ** 2 + (b * np.cos(th)) ** 2)
    major, minor = max(a, b), min(a, b)
    ang = np.degrees(th if a >= b else th + np.pi / 2) % 180
    return {'centre': [round(cx, 2), round(cy, 2)], 'half_w': round(float(hw), 2), 'half_h': round(float(hh), 2),
            'major': round(float(major), 2), 'minor': round(float(minor), 2), 'major_angle_deg': round(float(ang), 2)}


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
    """World points (N, 3) -> pixel (N, 2) and depth along the view (N,)."""
    f, r, u = cam_basis(eye, look)
    v = np.asarray(P, float) - np.asarray(eye, float)
    d = v @ f
    tv = np.tan(np.radians(fov_deg) / 2)
    th = tv * w / h
    dd = np.where(np.abs(d) < 1e-9, 1e-9, d)
    sx = w / 2 * (1 + (v @ r) / (dd * th))
    sy = h / 2 * (1 - (v @ u) / (dd * tv))
    return np.c_[sx, sy], d


def bike_to_world(Pb, at, yaw_deg):
    c, s = np.cos(np.radians(yaw_deg)), np.sin(np.radians(yaw_deg))
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    return np.asarray(Pb, float) @ R.T + np.asarray(at, float)


def clip_line_to_frame(p0, p1, w=W, h=H):
    """Liang-Barsky clip of a 2-D segment to the frame; None if outside."""
    x0, y0 = p0
    dx, dy = p1[0] - x0, p1[1] - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0), (dx, w - x0), (-dy, y0), (dy, h - y0)):
        if p == 0:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
    if t0 > t1:
        return None
    return (x0 + t0 * dx, y0 + t0 * dy), (x0 + t1 * dx, y0 + t1 * dy)
