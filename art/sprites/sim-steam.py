#!/usr/bin/env python3
"""3D smoke solver for the steam and fog sprites (numpy + numba, no Blender needed).

Semi-Lagrangian velocity, MacCormack density, spectral pressure projection on a
periodic box, vorticity confinement. Saves the line-of-sight density of every
output frame (not yet looped or toned; build-sprites.py does that).

    python3 art/sprites/sim-steam.py billow <cache-dir>
    python3 art/sprites/sim-steam.py rise   <cache-dir>
    python3 art/sprites/sim-steam.py fog    <cache-dir>
"""
import sys
import time

import numpy as np
import scipy.fft as sf
from numba import njit, prange

WORKERS = 12


@njit(parallel=True, fastmath=True)
def advect(q, u, v, w, dt):
    """Semi-Lagrangian trilinear advection on a periodic grid."""
    nz, ny, nx = q.shape
    out = np.empty_like(q)
    for k in prange(nz):
        for j in range(ny):
            for i in range(nx):
                x = i - dt * u[k, j, i]
                y = j - dt * v[k, j, i]
                z = k - dt * w[k, j, i]
                x0 = int(np.floor(x)); y0 = int(np.floor(y)); z0 = int(np.floor(z))
                fx = x - x0; fy = y - y0; fz = z - z0
                i0 = x0 % nx; i1 = (i0 + 1) % nx
                j0 = y0 % ny; j1 = (j0 + 1) % ny
                k0 = z0 % nz; k1 = (k0 + 1) % nz
                c00 = q[k0, j0, i0] * (1 - fx) + q[k0, j0, i1] * fx
                c01 = q[k0, j1, i0] * (1 - fx) + q[k0, j1, i1] * fx
                c10 = q[k1, j0, i0] * (1 - fx) + q[k1, j0, i1] * fx
                c11 = q[k1, j1, i0] * (1 - fx) + q[k1, j1, i1] * fx
                c0 = c00 * (1 - fy) + c01 * fy
                c1 = c10 * (1 - fy) + c11 * fy
                out[k, j, i] = c0 * (1 - fz) + c1 * fz
    return out


@njit(parallel=True, fastmath=True)
def maccormack_fix(q, fwd, back, u, v, w, dt):
    """MacCormack correction, clamped to the departure cell so it can't ring."""
    nz, ny, nx = q.shape
    out = np.empty_like(q)
    for k in prange(nz):
        for j in range(ny):
            for i in range(nx):
                x0 = int(np.floor(i - dt * u[k, j, i]))
                y0 = int(np.floor(j - dt * v[k, j, i]))
                z0 = int(np.floor(k - dt * w[k, j, i]))
                i0 = x0 % nx; i1 = (i0 + 1) % nx
                j0 = y0 % ny; j1 = (j0 + 1) % ny
                k0 = z0 % nz; k1 = (k0 + 1) % nz
                a = q[k0, j0, i0]; lo = a; hi = a
                for b in (q[k0, j0, i1], q[k0, j1, i0], q[k0, j1, i1],
                          q[k1, j0, i0], q[k1, j0, i1], q[k1, j1, i0], q[k1, j1, i1]):
                    if b < lo:
                        lo = b
                    if b > hi:
                        hi = b
                val = fwd[k, j, i] + 0.5 * (q[k, j, i] - back[k, j, i])
                out[k, j, i] = min(hi, max(lo, val))
    return out


@njit(parallel=True, fastmath=True)
def confinement(u, v, w, eps, fu, fv, fw):
    """Vorticity confinement: puts back the small curls advection smears away."""
    nz, ny, nx = u.shape
    ox = np.empty_like(u); oy = np.empty_like(u); oz = np.empty_like(u); mag = np.empty_like(u)
    for k in prange(nz):
        km = (k - 1) % nz; kp = (k + 1) % nz
        for j in range(ny):
            jm = (j - 1) % ny; jp = (j + 1) % ny
            for i in range(nx):
                im = (i - 1) % nx; ip = (i + 1) % nx
                a = 0.5 * (w[k, jp, i] - w[k, jm, i] - v[kp, j, i] + v[km, j, i])
                b = 0.5 * (u[kp, j, i] - u[km, j, i] - w[k, j, ip] + w[k, j, im])
                c = 0.5 * (v[k, j, ip] - v[k, j, im] - u[k, jp, i] + u[k, jm, i])
                ox[k, j, i] = a; oy[k, j, i] = b; oz[k, j, i] = c
                mag[k, j, i] = np.sqrt(a * a + b * b + c * c)
    for k in prange(nz):
        km = (k - 1) % nz; kp = (k + 1) % nz
        for j in range(ny):
            jm = (j - 1) % ny; jp = (j + 1) % ny
            for i in range(nx):
                im = (i - 1) % nx; ip = (i + 1) % nx
                gx = 0.5 * (mag[k, j, ip] - mag[k, j, im])
                gy = 0.5 * (mag[k, jp, i] - mag[k, jm, i])
                gz = 0.5 * (mag[kp, j, i] - mag[km, j, i])
                n = np.sqrt(gx * gx + gy * gy + gz * gz) + 1e-5
                gx /= n; gy /= n; gz /= n
                fu[k, j, i] += eps * (gy * oz[k, j, i] - gz * oy[k, j, i])
                fv[k, j, i] += eps * (gz * ox[k, j, i] - gx * oz[k, j, i])
                fw[k, j, i] += eps * (gx * oy[k, j, i] - gy * ox[k, j, i])


class Project:
    def __init__(self, shape):
        nz, ny, nx = shape
        kz = sf.fftfreq(nz).astype(np.float32).reshape(-1, 1, 1)
        ky = sf.fftfreq(ny).astype(np.float32).reshape(1, -1, 1)
        kx = sf.rfftfreq(nx).astype(np.float32).reshape(1, 1, -1)
        self.kx, self.ky, self.kz = kx, ky, kz
        k2 = kx * kx + ky * ky + kz * kz
        k2[0, 0, 0] = 1
        self.k2 = k2

    def __call__(self, u, v, w):
        U = sf.rfftn(u, workers=WORKERS)
        V = sf.rfftn(v, workers=WORKERS)
        W = sf.rfftn(w, workers=WORKERS)
        d = (U * self.kx + V * self.ky + W * self.kz) / self.k2
        U -= d * self.kx
        V -= d * self.ky
        W -= d * self.kz
        s = u.shape
        return (sf.irfftn(U, s=s, workers=WORKERS).astype(np.float32),
                sf.irfftn(V, s=s, workers=WORKERS).astype(np.float32),
                sf.irfftn(W, s=s, workers=WORKERS).astype(np.float32))


def blob(shape, p, r):
    """Gaussian around p (x, y, z), returned as a small slice plus its values."""
    nz, ny, nx = shape
    R = int(r * 3)
    x0, y0, z0 = int(p[0]), int(p[1]), int(p[2])
    xs = np.arange(max(0, x0 - R), min(nx, x0 + R + 1))
    ys = np.arange(max(0, y0 - R), min(ny, y0 + R + 1))
    zs = np.arange(max(0, z0 - R), min(nz, z0 + R + 1))
    g = (np.exp(-((zs - p[2]) ** 2) / (2 * r * r)).reshape(-1, 1, 1)
         * np.exp(-((ys - p[1]) ** 2) / (2 * r * r)).reshape(1, -1, 1)
         * np.exp(-((xs - p[0]) ** 2) / (2 * r * r)).reshape(1, 1, -1)).astype(np.float32)
    return (slice(zs[0], zs[-1] + 1), slice(ys[0], ys[-1] + 1), slice(xs[0], xs[-1] + 1)), g


def band_noise(rng, shape, kx, ky, kz):
    """Band-limited noise: kx, ky, kz are (low, high) cycles per box along each axis."""
    nz, ny, nx = shape
    fz = np.abs(sf.fftfreq(nz, 1 / nz)).reshape(-1, 1, 1)
    fy = np.abs(sf.fftfreq(ny, 1 / ny)).reshape(1, -1, 1)
    fx = np.abs(sf.rfftfreq(nx, 1 / nx)).reshape(1, 1, -1)
    keep = ((fx >= kx[0]) & (fx <= kx[1])) & ((fy >= ky[0]) & (fy <= ky[1])) & ((fz >= kz[0]) & (fz <= kz[1]))
    spec = keep * np.exp(1j * rng.uniform(0, 2 * np.pi, keep.shape))
    out = sf.irfftn(spec, s=shape, workers=WORKERS).astype(np.float32)
    return out / out.std()


# Profiles: every number is in cells and cells per step, at a 256 cell frame.
PROFILES = {
    # Short jets out of a low centre, each a vortex ring that rolls outward carrying its steam
    # and is eaten by the dissipation, so the puff keeps one size while its lobes keep turning.
    "billow": dict(
        scale=1.5, nx=384, ny=384, nz=192, steps_per_frame=2, warm=200, frames=64 + 48,
        centre=(128, 100, 64), burst_every=6, burst_len=20, burst_r=8, burst_speed=0.28,
        burst_density=0.085, burst_offset=8, burst_travel=40, burst_jitter=(24, 12, 18), core=0.010, core_r=20,
        buoy=0.0014, conf=0.42,
        dissipate=0.984, kill_r0=70, kill_r1=112, seed=11,
    ),
    # A steady buoyant source with a wandering nozzle: rises, shears, dissolves on the way up.
    "rise": dict(
        scale=1.5, nx=384, ny=384, nz=192, steps_per_frame=2, warm=220, frames=64 + 32,
        nozzle=(128, 6, 64), nozzle_r=11, source=0.10, jet=0.075, buoy=0.0052, conf=0.20,
        wander=6.0, dissipate=0.9965, thin_from=90, thin_over=150, thin=0.05, seed=23,
    ),
    # A real shear layer on a wide box (one frame is 4:1 here, so the frame's x is squeezed 4x):
    # a layer of fog is kept topped up low down, wind slides over it and rolls wisps off its top.
    "fog": dict(
        scale=1.0, nx=512, ny=128, nz=128, steps_per_frame=2, warm=420, frames=64 + 48,
        layer_y=36, layer_h=13, slab=20, refill=0.03, buoy=0.0016, conf=0.3,
        wind_low=0.3, wind_high=2.6, wind_y0=24, wind_y1=64,
        stir=0.034, stir_every=30, dissipate=0.992, seed=37,
    ),
}


def sim(name, out_dir):
    P = PROFILES[name]
    S = P["scale"]      # the numbers above are for a 256 cell frame
    rng = np.random.default_rng(P["seed"])
    shape = (P["nz"], P["ny"], P["nx"])
    nz, ny, nx = shape
    u = np.zeros(shape, np.float32); v = u.copy(); w = u.copy(); d = u.copy()
    project = Project(shape)
    zz, yy, xx = np.meshgrid(np.arange(nz), np.arange(ny), np.arange(nx), indexing="ij")

    # Sponge at the walls of the periodic box so nothing wraps around.
    def ramp(a, n, m):
        e = np.minimum(a, n - 1 - a) / m
        return np.clip(e, 0, 1)
    if name == "fog":
        wall = ramp(yy, ny, 14).astype(np.float32)     # x and z really are periodic
    else:
        wall = (ramp(xx, nx, 24 * S) * ramp(yy, ny, 24 * S) * ramp(zz, nz, 16 * S)).astype(np.float32)
    damp_v = (0.90 + 0.10 * wall).astype(np.float32)
    wind = np.zeros(ny, np.float32)
    shear = np.zeros(ny, np.float32)

    if name == "billow":
        c = np.array(P["centre"], np.float32) * S
        # Flattened: it's floor steam, wider than it is tall.
        r = np.sqrt((xx - c[0]) ** 2 + (1.25 * (yy - c[1])) ** 2 + (zz - c[2]) ** 2)
        t = np.clip((r / S - P["kill_r0"]) / (P["kill_r1"] - P["kill_r0"]), 0, 1)
        kill = (P["dissipate"] * (1 - t * t * (3 - 2 * t) * 0.25) * wall).astype(np.float32)
    elif name == "rise":
        h = np.clip((yy / S - P["thin_from"]) / P["thin_over"], 0, 1)
        kill = (P["dissipate"] * (1 - P["thin"] * h ** 1.5) * wall).astype(np.float32)
    else:
        y = np.arange(ny, dtype=np.float32)
        t = np.clip((y - P["wind_y0"]) / (P["wind_y1"] - P["wind_y0"]), 0, 1)
        wind = (P["wind_low"] + (P["wind_high"] - P["wind_low"]) * t * t * (3 - 2 * t)).astype(np.float32)
        shear = np.gradient(wind).astype(np.float32)
        high = np.clip((yy - 60) / 50.0, 0, 1)
        kill = (P["dissipate"] * (1 - 0.035 * high) * wall).astype(np.float32)
        # Only a thin slab in depth is fed: a deep one would average the wisps away in projection.
        layer = np.exp(-(((yy - P["layer_y"]) / P["layer_h"]) ** 2)
                       - ((zz - nz / 2) / P["slab"]) ** 2).astype(np.float32)
        stir_mask = np.exp(-(((yy - P["layer_y"] - 14) / 26.0) ** 2)).astype(np.float32)

        def stir_fields():
            return [band_noise(rng, shape, (6, 30), (2, 9), (1, 8)) * stir_mask for _ in range(3)]
        sa, sb = stir_fields(), stir_fields()
        pa = band_noise(rng, (nz, 1, nx), (2, 9), (0, 0), (1, 6))
        pb = band_noise(rng, (nz, 1, nx), (2, 9), (0, 0), (1, 6))

    bursts = []
    total = P["warm"] + P["frames"] * P["steps_per_frame"]
    frames = []
    wander_phase = rng.uniform(0, 6.28, 6)
    t0 = time.time()
    for step in range(total):
        fu = np.zeros(shape, np.float32); fv = fu.copy(); fw = fu.copy()
        fv += P["buoy"] * S * d
        confinement(u, v, w, P["conf"], fu, fv, fw)

        if name == "billow":
            if step % P["burst_every"] == 0:
                # Mostly sideways and a little up; the floor is under it, so never straight down.
                a = rng.uniform(0, 2 * np.pi)
                e = rng.uniform(-0.3, 0.85)
                dr = np.array([np.cos(a) * np.cos(e), np.sin(e), np.sin(a) * np.cos(e)], np.float32)
                # From all over the core, not one point, so it doesn't read as a fountain.
                o = c + rng.uniform(-1, 1, 3) * np.array(P["burst_jitter"], np.float32) * S
                bursts.append(dict(t=step, d=dr, o=o, s=rng.uniform(0.6, 1.3)))
            sl, g = blob(shape, c, P["core_r"] * S)
            d[sl] += P["core"] * g
            live = []
            for b in bursts:
                age = (step - b["t"]) / P["burst_len"]
                if age >= 1:
                    continue
                live.append(b)
                amp = np.sin(np.pi * age) ** 2 * b["s"]
                pos = b["o"] + b["d"] * S * (P["burst_offset"] + P["burst_travel"] * age)
                sl, g = blob(shape, pos, P["burst_r"] * S)
                fu[sl] += P["burst_speed"] * S * amp * b["d"][0] * g
                fv[sl] += P["burst_speed"] * S * amp * b["d"][1] * g
                fw[sl] += P["burst_speed"] * S * amp * b["d"][2] * g
                d[sl] += P["burst_density"] * amp * g
            bursts = live
        elif name == "rise":
            tt = step * 0.035
            nx0, ny0, nz0 = [q * S for q in P["nozzle"]]
            px = nx0 + S * P["wander"] * (np.sin(tt + wander_phase[0]) + 0.6 * np.sin(2.3 * tt + wander_phase[1]))
            pz = nz0 + S * P["wander"] * (np.sin(1.3 * tt + wander_phase[2]) + 0.6 * np.sin(2.9 * tt + wander_phase[3]))
            amp = 0.75 + 0.25 * np.sin(1.9 * tt + wander_phase[4])
            sl, g = blob(shape, (px, ny0 + 28 * S, pz), P["nozzle_r"] * S)
            d[sl] += P["source"] * amp * g
            fv[sl] += P["jet"] * S * amp * g
            fu[sl] += P["jet"] * S * 0.5 * np.sin(0.8 * tt + wander_phase[5]) * g
        else:
            # Winds' shear term, a slowly changing stir, and the low layer topped up in patches.
            fu -= v * shear.reshape(1, -1, 1)
            ph = step % P["stir_every"]
            if ph == 0 and step:
                sa, sb = sb, stir_fields()
            m = ph / P["stir_every"]
            fu += P["stir"] * ((1 - m) * sa[0] + m * sb[0])
            fv += P["stir"] * 0.6 * ((1 - m) * sa[1] + m * sb[1])
            fw += P["stir"] * ((1 - m) * sa[2] + m * sb[2])
            q = (step % 90) / 90.0
            if step % 90 == 0 and step:
                pa, pb = pb, band_noise(rng, (nz, 1, nx), (2, 9), (0, 0), (1, 6))
            patch = np.clip(0.42 + 0.62 * ((1 - q) * pa + q * pb), 0.0, 1.3)
            d += P["refill"] * (layer * patch - d) * (layer > 0.05)

        u += fu; v += fv; w += fw
        u, v, w = project(u, v, w)
        ua = u + wind.reshape(1, -1, 1)   # advecting velocity, wind included
        u2 = advect(u, ua, v, w, 1.0)
        v2 = advect(v, ua, v, w, 1.0)
        w2 = advect(w, ua, v, w, 1.0)
        fwd = advect(d, ua, v, w, 1.0)
        back = advect(fwd, ua, v, w, -1.0)
        d = maccormack_fix(d, fwd, back, ua, v, w, 1.0)
        d *= kill
        u, v, w = u2 * damp_v, v2 * damp_v, w2 * damp_v
        u, v, w = project(u, v, w)

        if step >= P["warm"] and (step - P["warm"]) % P["steps_per_frame"] == 0:
            tau = d.sum(axis=0)[::-1]  # y up in the sim, row 0 is the top in an image
            frames.append(tau.astype(np.float32))
        if step % 50 == 0:
            print(name, step, "/", total, f"{time.time() - t0:.0f}s dmax {d.max():.2f} "
                  f"vmax {np.sqrt(u * u + v * v + w * w).max():.2f}", flush=True)
    out = f"{out_dir}/sim-{name}.npy"
    np.save(out, np.stack(frames))
    print("saved", out, len(frames), f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    sim(sys.argv[1], sys.argv[2])
